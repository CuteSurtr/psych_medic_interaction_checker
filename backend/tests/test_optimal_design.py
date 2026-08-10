"""D-optimal sampling design.

The properties worth pinning are the ones that make the design meaningful:
the information matrix has to behave like an information matrix (additive,
positive semi-definite, singular when under-sampled), and the optimiser has to
actually beat the schedules it is meant to argue against.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from database.seed_db import create_tables, seed_if_empty
from main import app
from services.optimal_design import (
    PARAM_NAMES,
    concentration,
    evaluate_design,
    fisher_information,
    optimize_sampling_times,
    sensitivity_matrix,
)

# A drug with a clearly resolved absorption phase inside the window, so the
# design problem is not degenerate.
PK = dict(dose_mg=100.0, cl=5.0, vd=50.0, ka=1.2)


@pytest.fixture(scope="module")
def client():
    create_tables()
    seed_if_empty()
    return TestClient(app)


# ------------------------------------------------------------ structural model


def test_concentration_starts_at_zero_and_returns_to_zero():
    c = concentration(np.array([0.0, 4.0, 500.0]), **PK)
    assert c[0] == pytest.approx(0.0, abs=1e-12)
    assert c[1] > 0
    assert c[2] == pytest.approx(0.0, abs=1e-6)


def test_concentration_peaks_at_the_analytic_tmax():
    ke = PK["cl"] / PK["vd"]
    tmax = np.log(PK["ka"] / ke) / (PK["ka"] - ke)
    grid = np.linspace(0.01, 24, 4000)
    assert grid[np.argmax(concentration(grid, **PK))] == pytest.approx(tmax, rel=0.02)


def test_flip_flop_limit_is_continuous():
    """ka -> ke is a removable singularity; the branch must not jump."""
    ke = PK["cl"] / PK["vd"]
    t = np.array([1.0, 5.0, 12.0])
    near = concentration(t, PK["dose_mg"], PK["cl"], PK["vd"], ke * (1 + 1e-7))
    at = concentration(t, PK["dose_mg"], PK["cl"], PK["vd"], ke)
    assert np.allclose(near, at, rtol=1e-3)


def test_doubling_dose_doubles_concentration_but_not_information_shape():
    t = np.array([1.0, 5.0, 12.0])
    c1 = concentration(t, **PK)
    c2 = concentration(t, **{**PK, "dose_mg": 2 * PK["dose_mg"]})
    assert np.allclose(c2, 2 * c1)
    # With purely proportional error the FIM is dose-invariant: the noise scales
    # with the signal, so a bigger dose does not buy information.
    f1 = fisher_information(t, **PK, sigma_prop=0.2)
    f2 = fisher_information(t, **{**PK, "dose_mg": 2 * PK["dose_mg"]}, sigma_prop=0.2)
    assert np.allclose(f1, f2, rtol=1e-6)


# ------------------------------------------------------- Fisher information


def test_fim_is_symmetric_and_positive_semidefinite():
    fim = fisher_information([0.5, 2.0, 6.0, 18.0], **PK)
    assert np.allclose(fim, fim.T)
    assert np.linalg.eigvalsh(fim).min() >= -1e-9


def test_fim_is_additive_over_independent_samples():
    """Independent observations contribute additively, by construction."""
    a = fisher_information([1.0, 3.0], **PK)
    b = fisher_information([9.0, 20.0], **PK)
    both = fisher_information([1.0, 3.0, 9.0, 20.0], **PK)
    assert np.allclose(both, a + b, rtol=1e-8)


def test_fim_is_singular_with_fewer_samples_than_parameters():
    """Two samples cannot identify three parameters."""
    fim = fisher_information([2.0, 8.0], **PK)
    assert fim.shape == (3, 3)
    assert abs(np.linalg.det(fim)) < 1e-6


def test_more_samples_never_lose_information():
    """Adding an observation cannot decrease the determinant."""
    base = evaluate_design([0.5, 4.0, 18.0], **PK)
    more = evaluate_design([0.5, 4.0, 18.0, 9.0], **PK)
    assert more.log_det_fim >= base.log_det_fim - 1e-9


def test_sensitivity_matrix_shape_and_nonzero():
    S = sensitivity_matrix(np.array([0.5, 4.0, 18.0]), **PK)
    assert S.shape == (3, len(PARAM_NAMES))
    assert np.abs(S).sum() > 0


# --------------------------------------------------------------- optimisation


def test_optimal_design_beats_trough_only_and_even_spacing():
    opt = optimize_sampling_times(**PK, n_samples=3, horizon_h=24)
    for label, times in (
        ("trough only", [24.0, 24.0, 24.0]),
        ("even spacing", [8.0, 16.0, 24.0]),
        ("all early", [0.5, 1.0, 1.5]),
    ):
        alt = evaluate_design(times, **PK)
        assert opt.log_det_fim >= alt.log_det_fim - 1e-9, f"optimal lost to {label}"


def test_optimal_design_spans_absorption_and_elimination():
    """A D-optimal 3-point design places samples across distinct phases rather
    than clustering, which is the whole reason it beats trough-only."""
    opt = optimize_sampling_times(**PK, n_samples=3, horizon_h=24)
    t = opt.sampling_times_h
    assert min(t) < 4.0, "needs an early sample to see absorption"
    assert max(t) > 12.0, "needs a late sample to see elimination"
    assert max(t) - min(t) > 8.0, "samples should not cluster"


def test_trough_only_is_near_zero_efficiency():
    opt = optimize_sampling_times(
        **PK, n_samples=3, horizon_h=24, reference_times_h=[24.0, 24.0, 24.0]
    )
    assert opt.d_efficiency_vs_reference_pct is not None
    assert opt.d_efficiency_vs_reference_pct < 5.0


def test_reported_grid_step_coarsens_for_large_designs():
    """The exhaustive search is capped by coarsening, and says so."""
    fine = optimize_sampling_times(**PK, n_samples=2, horizon_h=24, grid_step_h=0.5)
    big = optimize_sampling_times(**PK, n_samples=6, horizon_h=24, grid_step_h=0.5)
    assert fine.grid_step_h == pytest.approx(0.5)
    assert big.grid_step_h > 0.5


def test_optimizer_rejects_impossible_requests():
    with pytest.raises(ValueError):
        optimize_sampling_times(**PK, n_samples=0)
    with pytest.raises(ValueError):
        optimize_sampling_times(**PK, n_samples=7)
    with pytest.raises(ValueError):
        optimize_sampling_times(**PK, n_samples=3, horizon_h=0.1, min_time_h=0.25)


def test_rse_and_correlation_are_well_formed():
    d = evaluate_design([0.5, 4.0, 18.0], **PK)
    assert set(d.relative_standard_errors_pct) == set(PARAM_NAMES)
    assert all(v > 0 for v in d.relative_standard_errors_pct.values())
    corr = np.array(d.correlation_matrix)
    assert np.allclose(np.diag(corr), 1.0, atol=1e-6)
    assert np.abs(corr).max() <= 1.0 + 1e-6


# ------------------------------------------------------------------- endpoint


def test_endpoint_uses_formulary_parameters(client):
    r = client.post("/api/advanced/optimal-design", json={"medication_id": 1, "n_samples": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["drug_name"]
    assert len(body["optimal_times_h"]) == 3
    assert body["d_efficiency_of_reference_pct"] < 100.0


def test_endpoint_accepts_explicit_parameters(client):
    r = client.post(
        "/api/advanced/optimal-design",
        json={"dose_mg": 100, "cl_l_per_h": 5, "vd_l": 50, "ka_per_h": 1.2, "n_samples": 3},
    )
    assert r.status_code == 200
    assert len(r.json()["optimal_times_h"]) == 3


def test_endpoint_rejects_missing_parameters(client):
    r = client.post("/api/advanced/optimal-design", json={"dose_mg": 100})
    assert r.status_code == 400
    assert "missing positive PK parameters" in r.json()["detail"]


def test_endpoint_404s_on_unknown_medication(client):
    assert client.post(
        "/api/advanced/optimal-design", json={"medication_id": 999999}
    ).status_code == 404
