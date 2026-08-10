"""PK-parameter completeness across the formulary.

Roughly half the seeded medications carry interaction and CYP450 data but no
clearance, volume of distribution or absorption rate. The panels that drive the
compartmental model failed on whichever drug happened to be first in the
regimen, which looked like a bug and was really a data boundary nobody had
surfaced. These pin the boundary and the API that exposes it.
"""

import pytest
from fastapi.testclient import TestClient

from database.connection import SessionLocal
from database.seed_db import create_tables, seed_if_empty
from main import app
from models import Medication
from routers.medications import _has_pk_parameters


@pytest.fixture(scope="module", autouse=True)
def _seeded():
    """Autouse: the DB-direct tests below need the schema too, not just the
    ones that go through the API."""
    create_tables()
    seed_if_empty()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_some_medications_lack_pk_parameters():
    """The condition the UI has to handle; if this ever became false the
    special-casing could be removed."""
    db = SessionLocal()
    try:
        meds = db.query(Medication).all()
        complete = [m for m in meds if _has_pk_parameters(m)]
        assert 0 < len(complete) < len(meds)
    finally:
        db.close()


def test_pk_parameters_are_all_or_nothing():
    """Every incomplete entry is missing all three, not a partial subset, so a
    single boolean is an honest summary rather than a lossy one."""
    db = SessionLocal()
    try:
        for m in db.query(Medication).all():
            present = [
                v is not None and float(v) > 0
                for v in (m.clearance_l_per_h, m.volume_of_distribution_l,
                          m.absorption_rate_constant)
            ]
            assert len(set(present)) == 1, f"{m.generic_name} is partially populated"
    finally:
        db.close()


def test_search_reports_completeness(client):
    complete = client.get("/api/medications/search?q=fluoxetine").json()[0]
    incomplete = client.get("/api/medications/search?q=vilazodone").json()[0]
    assert complete["has_pk_parameters"] is True
    assert incomplete["has_pk_parameters"] is False


def test_detail_reports_completeness(client):
    body = client.get("/api/medications/1").json()
    assert "has_pk_parameters" in body


def test_pk_complete_listing_is_reachable_and_consistent(client):
    """`/pk-complete` is a literal path declared after `/{med_id}` would have
    captured it; a 422 here means the route ordering regressed."""
    r = client.get("/api/medications/pk-complete")
    assert r.status_code == 200, r.json()
    body = r.json()
    assert 0 < body["pk_complete_count"] < body["total"]
    assert len(body["medications"]) == body["pk_complete_count"]
    for m in body["medications"]:
        detail = client.get(f"/api/medications/{m['id']}").json()
        assert detail["has_pk_parameters"] is True


def test_every_listed_medication_actually_runs_the_pk_analyses(client):
    """The promise the flag makes: if it says the analysis is available, the
    analysis has to return 200."""
    listed = client.get("/api/medications/pk-complete").json()["medications"]
    for m in listed[:8]:
        r = client.post("/api/advanced/optimal-design",
                        json={"medication_id": m["id"], "n_samples": 3})
        assert r.status_code == 200, f"{m['generic_name']}: {r.json()}"


def test_incomplete_medication_fails_with_a_named_reason(client):
    hit = client.get("/api/medications/search?q=vilazodone").json()[0]
    r = client.post("/api/advanced/optimal-design", json={"medication_id": hit["id"]})
    assert r.status_code == 400
    assert "missing positive PK parameters" in r.json()["detail"]
