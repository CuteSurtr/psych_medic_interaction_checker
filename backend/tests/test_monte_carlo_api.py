"""Monte Carlo endpoint, plus the limiting behaviour documented in section XVI.

The Monte Carlo simulator was implemented and unit-tested but never exposed
through the API, so the capability was unreachable from the application. These
cover the endpoint and pin the well-stirred asymptotics that the hepatic
extraction write-up relies on.
"""

import pytest
from fastapi.testclient import TestClient

from database.seed_db import create_tables, seed_if_empty
from main import app
from services.hepatic_extraction import EnzymePathway, compute_hepatic_clearance


@pytest.fixture(scope="module")
def client():
    create_tables()
    seed_if_empty()
    return TestClient(app)


@pytest.fixture(scope="module")
def spec(client):
    ids = []
    for name in ("fluoxetine", "bupropion"):
        ids.append(client.get(f"/api/medications/search?q={name}").json()[0]["id"])
    return {
        "patient_weight_kg": 70,
        "horizon_days": 7,
        "dose_schedules": [
            {
                "medication_id": mid,
                "event_type": "start",
                "event_day": 0,
                "dose_mg": 20,
                "frequency": "daily",
            }
            for mid in ids
        ],
    }


# ------------------------------------------------------------ Monte Carlo API


def test_monte_carlo_returns_percentile_bands(client, spec):
    r = client.post("/api/advanced/monte-carlo", json={"simulation": spec, "n_iterations": 25})
    assert r.status_code == 200
    body = r.json()
    assert body["time_hours"]
    stats = body["drug_stats"]["fluoxetine"]
    for key in ("mean", "median", "ci_5", "ci_25", "ci_75", "ci_95"):
        assert len(stats[key]) == len(body["time_hours"])


def test_monte_carlo_percentiles_are_ordered(client, spec):
    body = client.post(
        "/api/advanced/monte-carlo", json={"simulation": spec, "n_iterations": 40}
    ).json()
    s = body["drug_stats"]["fluoxetine"]
    for lo, hi in (("ci_5", "ci_25"), ("ci_25", "ci_75"), ("ci_75", "ci_95")):
        assert all(a <= b + 1e-9 for a, b in zip(s[lo], s[hi])), f"{lo} must not exceed {hi}"


def test_monte_carlo_reports_therapeutic_probabilities(client, spec):
    body = client.post(
        "/api/advanced/monte-carlo", json={"simulation": spec, "n_iterations": 25}
    ).json()
    s = body["drug_stats"]["fluoxetine"]
    if "p_therapeutic" in s:
        for a, b, c in zip(s["p_subtherapeutic"], s["p_therapeutic"], s["p_supratherapeutic"]):
            assert a + b + c == pytest.approx(1.0, abs=1e-6)


def test_monte_carlo_caps_iterations_to_stay_inside_the_timeout(client, spec):
    body = client.post(
        "/api/advanced/monte-carlo", json={"simulation": spec, "n_iterations": 100000}
    ).json()
    assert body["capped"] is True
    assert body["n_iterations"] == body["iteration_cap"] < 100000


def test_monte_carlo_is_reproducible_for_a_fixed_seed(client, spec):
    a = client.post(
        "/api/advanced/monte-carlo", json={"simulation": spec, "n_iterations": 20, "seed": 7}
    ).json()
    b = client.post(
        "/api/advanced/monte-carlo", json={"simulation": spec, "n_iterations": 20, "seed": 7}
    ).json()
    assert a["drug_stats"]["fluoxetine"]["median"] == b["drug_stats"]["fluoxetine"]["median"]


def test_monte_carlo_requires_a_simulation_source(client):
    assert client.post("/api/advanced/monte-carlo", json={}).status_code == 400


# --------------------------------------- well-stirred asymptotics (section XVI)


def _clearance(vmax, km, f_u, q=81.0):
    return compute_hepatic_clearance(
        [EnzymePathway(enzyme="CYP2D6", vmax_mg_per_h=vmax, km_mg_per_l=km)],
        f_unbound=f_u,
        q_hepatic_l_per_h=q,
    )


def test_low_extraction_clearance_approaches_fu_times_clint():
    """f_u*CL_int << Q_H  =>  CL_H ~ f_u*CL_int, so clearance tracks enzyme activity."""
    res = _clearance(vmax=1.0, km=1.0, f_u=0.01)  # f_u*CL_int = 0.01 vs Q_H = 81
    assert res.cl_hepatic_l_per_h == pytest.approx(0.01, rel=1e-3)
    assert res.extraction_ratio < 0.01


def test_high_extraction_clearance_approaches_hepatic_blood_flow():
    """f_u*CL_int >> Q_H  =>  CL_H ~ Q_H, so clearance is perfusion-limited."""
    res = _clearance(vmax=1.0e6, km=1.0, f_u=1.0)
    assert res.cl_hepatic_l_per_h == pytest.approx(81.0, rel=1e-3)
    assert res.extraction_ratio > 0.99


def test_inhibition_moves_clearance_more_in_the_low_extraction_regime():
    """The documented reason the same inhibitor matters more for low-E drugs."""
    from services.hepatic_extraction import InhibitorTerm

    inhibitor = [
        InhibitorTerm(enzyme="CYP2D6", ki_mg_per_l=1.0, unbound_concentration_mg_per_l=9.0)
    ]  # 10-fold intrinsic clearance reduction

    low = compute_hepatic_clearance(
        [EnzymePathway(enzyme="CYP2D6", vmax_mg_per_h=1.0, km_mg_per_l=1.0)],
        f_unbound=0.01,
        inhibitors=inhibitor,
    )
    high = compute_hepatic_clearance(
        [EnzymePathway(enzyme="CYP2D6", vmax_mg_per_h=1.0e6, km_mg_per_l=1.0)],
        f_unbound=1.0,
        inhibitors=inhibitor,
    )
    low_drop = 1 - low.cl_hepatic_inhibited_l_per_h / low.cl_hepatic_l_per_h
    high_drop = 1 - high.cl_hepatic_inhibited_l_per_h / high.cl_hepatic_l_per_h
    assert low_drop > 0.85, "low-extraction clearance should fall nearly in proportion"
    assert high_drop < 0.15, "high-extraction clearance is buffered by perfusion"


def test_first_pass_bioavailability_is_one_minus_extraction_ratio():
    res = _clearance(vmax=500.0, km=1.0, f_u=0.5)
    assert res.bioavailability_hepatic == pytest.approx(1.0 - res.extraction_ratio)
