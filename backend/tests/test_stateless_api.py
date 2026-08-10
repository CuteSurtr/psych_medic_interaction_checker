"""API-level tests for the database-free deployment path.

These cover the behaviour the serverless deployment depends on: the schema has
to build on SQLite, the reference data has to seed itself, and every endpoint
the UI calls has to work from a request body alone, with nothing persisted
between calls.
"""

import pytest
from fastapi.testclient import TestClient

from database.seed_db import create_tables, seed_if_empty
from main import app


@pytest.fixture(scope="module")
def client():
    create_tables()
    seed_if_empty()
    return TestClient(app)


@pytest.fixture(scope="module")
def med_ids(client):
    ids = []
    for name in ("fluoxetine", "bupropion"):
        hits = client.get(f"/api/medications/search?q={name}").json()
        assert hits, f"{name} missing from the seeded data"
        ids.append(hits[0]["id"])
    return ids


def _spec(med_ids, horizon_days=14):
    return {
        "patient_weight_kg": 70,
        "smoking_status": False,
        "cyp2d6_phenotype": "normal",
        "cyp2c19_phenotype": "normal",
        "horizon_days": horizon_days,
        "dose_schedules": [
            {
                "medication_id": mid,
                "event_type": "start",
                "event_day": 0,
                "dose_mg": 20,
                "frequency": "daily",
            }
            for mid in med_ids
        ],
    }


# ------------------------------------------------------------ schema + seed


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_reference_data_is_seeded(client):
    assert client.get("/api/medications/search?q=fluoxetine").json()


def test_brand_name_search_works_without_postgres_array_functions(client):
    """Brand search used array_to_string, which only exists on PostgreSQL."""
    hits = client.get("/api/medications/search?q=prozac").json()
    assert any(h["generic_name"] == "fluoxetine" for h in hits)


def test_brand_names_round_trip_as_a_list(client, med_ids):
    detail = client.get(f"/api/medications/{med_ids[0]}").json()
    assert isinstance(detail["brand_names"], list)


# ------------------------------------------------- stateless simulation run


def test_stateless_run_returns_a_full_result(client, med_ids):
    r = client.post("/api/simulation/run", json=_spec(med_ids))
    assert r.status_code == 200
    body = r.json()
    for key in (
        "time_hours",
        "concentrations",
        "metabolite_concentrations",
        "dose_events",
        "enzyme_activity",
        "steady_state_info",
    ):
        assert key in body
    assert len(body["time_hours"]) > 0
    assert set(body["concentrations"]) == {"fluoxetine", "bupropion"}


def test_stateless_run_needs_no_prior_request(client, med_ids):
    """Two independent calls must both succeed: nothing is carried over."""
    a = client.post("/api/simulation/run", json=_spec(med_ids))
    b = client.post("/api/simulation/run", json=_spec(med_ids))
    assert a.status_code == b.status_code == 200
    assert a.json()["time_hours"] == b.json()["time_hours"]


def test_stateless_run_horizon_controls_length(client, med_ids):
    short = client.post("/api/simulation/run", json=_spec(med_ids, 7)).json()
    long = client.post("/api/simulation/run", json=_spec(med_ids, 28)).json()
    assert len(long["time_hours"]) > len(short["time_hours"])


def test_stateless_run_rejects_empty_schedule(client):
    spec = {"horizon_days": 14, "dose_schedules": []}
    assert client.post("/api/simulation/run", json=spec).status_code == 400


def test_stateless_run_rejects_unknown_medication(client):
    spec = _spec([999999])
    r = client.post("/api/simulation/run", json=spec)
    assert r.status_code == 400
    assert "unknown medication" in r.json()["detail"].lower()


# ------------------------------------------- advanced endpoints, inline spec


@pytest.mark.parametrize(
    "endpoint,extra",
    [
        ("/api/advanced/receptor-occupancy", {"use_f_unbound": True}),
        ("/api/advanced/tissue-pde", {}),
    ],
)
def test_advanced_endpoints_accept_an_inline_simulation(client, med_ids, endpoint, extra):
    r = client.post(endpoint, json={"simulation": _spec(med_ids), **extra})
    assert r.status_code == 200


def test_hepatic_extraction_accepts_an_inline_simulation(client, med_ids):
    r = client.post(
        "/api/advanced/hepatic-extraction",
        json={"medication_ids": med_ids, "simulation": _spec(med_ids)},
    )
    assert r.status_code == 200


def test_advanced_endpoint_errors_without_a_simulation_source(client):
    r = client.post("/api/advanced/receptor-occupancy", json={})
    assert r.status_code == 400
    assert "simulation" in r.json()["detail"].lower()


def test_advanced_endpoint_reports_a_missing_persisted_simulation(client):
    r = client.post("/api/advanced/receptor-occupancy", json={"simulation_id": 987654})
    assert r.status_code == 404


# -------------------------------------------------- persisted path still ok


def test_create_then_run_still_works_against_a_live_database(client, med_ids):
    """The two-step flow is retained for deployments with durable storage."""
    created = client.post("/api/simulation/create", json=_spec(med_ids))
    assert created.status_code == 200
    sim_id = created.json()["simulation_id"]
    run = client.get(f"/api/simulation/{sim_id}/run")
    assert run.status_code == 200
    assert set(run.json()["concentrations"]) == {"fluoxetine", "bupropion"}


def test_persisted_and_stateless_paths_agree(client, med_ids):
    spec = _spec(med_ids)
    stateless = client.post("/api/simulation/run", json=spec).json()
    sim_id = client.post("/api/simulation/create", json=spec).json()["simulation_id"]
    persisted = client.get(f"/api/simulation/{sim_id}/run").json()
    assert stateless["time_hours"] == persisted["time_hours"]
    for drug, series in stateless["concentrations"].items():
        assert series == pytest.approx(persisted["concentrations"][drug])
