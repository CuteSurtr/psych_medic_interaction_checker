"""Identifiability analysis.

The cases here have known answers by construction: duplicated sampling times
must give a rank-deficient sensitivity matrix, a schedule confined to one
kinetic phase must be collinear, and a schedule spanning absorption through
elimination must resolve all three parameters.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from database.seed_db import create_tables, seed_if_empty
from main import app
from services.identifiability import (
    analyse,
    profile_likelihood,
    structural_identifiability,
)
from services.optimal_design import PARAM_NAMES, concentration

DOSE, CL, VD, KA = 100.0, 5.0, 50.0, 1.2
RICH = [0.5, 1.0, 2.0, 4.0, 8.0, 18.0]


@pytest.fixture(scope="module")
def client():
    create_tables()
    seed_if_empty()
    return TestClient(app)


def observed(times, seed=0, sigma=0.1):
    rng = np.random.default_rng(seed)
    t = np.asarray(times, dtype=float)
    return concentration(t, DOSE, CL, VD, KA) * (1 + sigma * rng.standard_normal(t.size))


# ------------------------------------------------------------- structural


def test_rich_design_is_structurally_identifiable():
    s = structural_identifiability(RICH, DOSE, CL, VD, KA)
    assert s.rank == s.n_parameters == len(PARAM_NAMES)
    assert s.structurally_identifiable
    assert s.collinearity_index < 20


def test_duplicated_sampling_times_are_rank_deficient():
    """Three samples at the same instant carry the information of one."""
    s = structural_identifiability([24.0, 24.0, 24.0], DOSE, CL, VD, KA)
    assert s.rank == 1
    assert not s.structurally_identifiable
    assert any("rank 1" in n for n in s.notes)


def test_samples_confined_to_one_phase_are_collinear():
    """Early-only sampling cannot separate the parameters even at full rank."""
    s = structural_identifiability([0.5, 0.6, 0.7], DOSE, CL, VD, KA)
    assert s.rank == len(PARAM_NAMES)
    assert s.collinearity_index > 20
    assert not s.structurally_identifiable
    assert any("collinearity index" in n for n in s.notes)


def test_worst_direction_is_a_unit_vector_over_the_parameters():
    s = structural_identifiability(RICH, DOSE, CL, VD, KA)
    assert set(s.worst_direction) == set(PARAM_NAMES)
    norm = np.linalg.norm(list(s.worst_direction.values()))
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_singular_values_are_ordered_and_nonnegative():
    s = structural_identifiability(RICH, DOSE, CL, VD, KA)
    sv = s.singular_values
    assert all(a >= b - 1e-12 for a, b in zip(sv, sv[1:]))
    assert min(sv) >= -1e-12


def test_adding_a_distinct_time_cannot_reduce_rank():
    a = structural_identifiability([2.0, 8.0], DOSE, CL, VD, KA)
    b = structural_identifiability([2.0, 8.0, 18.0], DOSE, CL, VD, KA)
    assert b.rank >= a.rank


# --------------------------------------------------------------- practical


def test_rich_design_gives_two_sided_confidence_intervals():
    obs = observed(RICH)
    res = analyse(RICH, obs, DOSE, (CL, VD, KA), n_grid=15)
    assert res.practically_identifiable
    for p in res.profiles:
        assert p.ci_lower is not None and p.ci_upper is not None
        assert p.ci_lower < p.mle < p.ci_upper


def test_trough_only_design_is_not_practically_identifiable():
    """The clinical point: real samples, real needles, no information."""
    times = [22.0, 23.0, 24.0]
    res = analyse(times, observed(times), DOSE, (CL, VD, KA), n_grid=15)
    assert not res.practically_identifiable
    assert any(not p.identifiable for p in res.profiles)


def test_profile_is_minimised_at_the_mle():
    obs = observed(RICH)
    p = profile_likelihood("log_CL", RICH, obs, DOSE, (CL, VD, KA), n_grid=15)
    assert min(p.profile_nll) == pytest.approx(0.0, abs=1e-6)
    centre = int(np.argmin(np.abs(np.array(p.grid) - p.mle)))
    assert p.profile_nll[centre] == pytest.approx(0.0, abs=1e-6)


def test_profile_is_non_negative_everywhere():
    """It is a delta against the optimum, so it cannot go below zero."""
    p = profile_likelihood("log_Vd", RICH, observed(RICH), DOSE, (CL, VD, KA), n_grid=15)
    assert min(p.profile_nll) >= -1e-8


def test_profile_rejects_an_unknown_parameter():
    with pytest.raises(ValueError):
        profile_likelihood("log_nonsense", RICH, observed(RICH), DOSE, (CL, VD, KA))


def test_structural_only_mode_skips_profiling():
    res = analyse(RICH, observed(RICH), DOSE, (CL, VD, KA), run_profiles=False)
    assert res.profiles == []


def test_noisier_data_widens_the_intervals():
    a = profile_likelihood("log_CL", RICH, observed(RICH, sigma=0.05), DOSE,
                           (CL, VD, KA), sigma_prop=0.05, n_grid=21)
    b = profile_likelihood("log_CL", RICH, observed(RICH, sigma=0.30), DOSE,
                           (CL, VD, KA), sigma_prop=0.30, n_grid=21)
    if all(v is not None for v in (a.ci_lower, a.ci_upper, b.ci_lower, b.ci_upper)):
        assert (b.ci_upper - b.ci_lower) > (a.ci_upper - a.ci_lower)


# ---------------------------------------------------------------- endpoint


def test_endpoint_simulates_observations_when_none_are_supplied(client):
    r = client.post("/api/advanced/identifiability", json={
        "dose_mg": DOSE, "cl_l_per_h": CL, "vd_l": VD, "ka_per_h": KA,
        "sampling_times_h": RICH,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["observations_were_simulated"] is True
    assert len(body["observations"]) == len(RICH)
    assert body["structurally_identifiable"] is True


def test_endpoint_flags_a_degenerate_schedule(client):
    body = client.post("/api/advanced/identifiability", json={
        "dose_mg": DOSE, "cl_l_per_h": CL, "vd_l": VD, "ka_per_h": KA,
        "sampling_times_h": [24.0, 24.0, 24.0],
    }).json()
    assert body["rank"] == 1
    assert body["structurally_identifiable"] is False
    assert body["collinearity_index_is_infinite"] is True
    assert body["collinearity_index"] is None


def test_endpoint_response_contains_no_non_finite_numbers(client):
    """JSON has no infinity; a silent null is the shape that crashed the UI."""
    import json

    body = client.post("/api/advanced/identifiability", json={
        "dose_mg": DOSE, "cl_l_per_h": CL, "vd_l": VD, "ka_per_h": KA,
        "sampling_times_h": [24.0, 24.0, 24.0],
    }).json()
    text = json.dumps(body)
    for token in ("Infinity", "-Infinity", "NaN"):
        assert token not in text


def test_endpoint_rejects_mismatched_observations(client):
    r = client.post("/api/advanced/identifiability", json={
        "dose_mg": DOSE, "cl_l_per_h": CL, "vd_l": VD, "ka_per_h": KA,
        "sampling_times_h": [1.0, 2.0], "observations_ng_ml": [5.0],
    })
    assert r.status_code == 400


def test_endpoint_uses_formulary_parameters(client):
    r = client.post("/api/advanced/identifiability",
                    json={"medication_id": 1, "run_profiles": False})
    assert r.status_code == 200
    assert r.json()["drug_name"]


def test_endpoint_404s_on_unknown_medication(client):
    assert client.post("/api/advanced/identifiability",
                       json={"medication_id": 999999}).status_code == 404
