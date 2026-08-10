"""Sobol global sensitivity analysis.

Validated against two references with known answers: the Ishigami function,
whose indices are analytic and which is the standard benchmark because it has a
factor with zero main effect but a large interaction effect, and AUC to
infinity, which depends on clearance alone by construction.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from database.seed_db import create_tables, seed_if_empty
from main import app
from services.optimal_design import concentration
from services.sensitivity_analysis import saltelli_sample, sobol_indices

A_ISH, B_ISH = 7.0, 0.1


def ishigami(X: np.ndarray) -> np.ndarray:
    x1, x2, x3 = X[:, 0], X[:, 1], X[:, 2]
    return np.sin(x1) + A_ISH * np.sin(x2) ** 2 + B_ISH * (x3**4) * np.sin(x1)


def ishigami_analytic():
    """Sobol and Levitan's decomposition for x_i ~ U(-pi, pi)."""
    a, b, pi = A_ISH, B_ISH, np.pi
    D = a**2 / 8 + b * pi**4 / 5 + b**2 * pi**8 / 18 + 0.5
    D1 = b * pi**4 / 5 + b**2 * pi**8 / 50 + 0.5
    D2 = a**2 / 8
    D13 = b**2 * pi**8 * (1 / 18 - 1 / 50)
    return (
        {"x1": D1 / D, "x2": D2 / D, "x3": 0.0},
        {"x1": (D1 + D13) / D, "x2": D2 / D, "x3": D13 / D},
    )


@pytest.fixture(scope="module")
def client():
    create_tables()
    seed_if_empty()
    return TestClient(app)


# ------------------------------------------------------------------ sampling


def test_saltelli_matrices_have_the_right_shapes():
    A, B, AB = saltelli_sample([(1.0, 2.0)] * 3, n_base=32)
    assert A.shape == B.shape == (32, 3)
    assert len(AB) == 3
    assert all(m.shape == (32, 3) for m in AB)


def test_ab_matrix_differs_from_a_in_exactly_one_column():
    A, B, AB = saltelli_sample([(1.0, 2.0)] * 3, n_base=16, log_scale=False)
    for i, ab in enumerate(AB):
        differing = [j for j in range(3) if not np.allclose(ab[:, j], A[:, j])]
        assert differing == [i]
        assert np.allclose(ab[:, i], B[:, i])


def test_samples_respect_bounds():
    A, B, _ = saltelli_sample([(2.0, 5.0), (10.0, 20.0)], n_base=64)
    for M in (A, B):
        assert M[:, 0].min() >= 2.0 and M[:, 0].max() <= 5.0
        assert M[:, 1].min() >= 10.0 and M[:, 1].max() <= 20.0


def test_log_scale_sampling_rejects_nonpositive_bounds():
    with pytest.raises(ValueError):
        saltelli_sample([(-1.0, 1.0)], n_base=16, log_scale=True)


# ------------------------------------------------- Ishigami analytic benchmark


def test_ishigami_first_and_total_order_match_analytic_values():
    S, ST = ishigami_analytic()
    r = sobol_indices(
        ishigami, ["x1", "x2", "x3"], [(-np.pi, np.pi)] * 3,
        n_base=16384, log_scale=False, n_boot=40,
    )
    for name in ("x1", "x2", "x3"):
        assert r.first_order[name] == pytest.approx(S[name], abs=0.03)
        assert r.total_order[name] == pytest.approx(ST[name], abs=0.03)


def test_ishigami_x3_has_no_main_effect_but_a_large_interaction():
    """The property that makes Ishigami the standard benchmark: x3 alone
    explains nothing, yet removing it would change the variance substantially."""
    r = sobol_indices(
        ishigami, ["x1", "x2", "x3"], [(-np.pi, np.pi)] * 3,
        n_base=16384, log_scale=False, n_boot=40,
    )
    assert r.first_order["x3"] < 0.03
    assert r.total_order["x3"] > 0.15
    assert r.interaction["x3"] > 0.15


def test_ishigami_first_order_sum_is_below_one_because_of_interactions():
    r = sobol_indices(
        ishigami, ["x1", "x2", "x3"], [(-np.pi, np.pi)] * 3,
        n_base=16384, log_scale=False, n_boot=40,
    )
    assert 0.7 < r.sum_first_order < 0.85


# -------------------------------------------------------- PK analytic benchmark


def test_auc_to_infinity_depends_only_on_clearance():
    """AUC_0-inf = F*Dose/CL exactly, so CL must take all the variance."""
    t = np.linspace(0, 4000, 20001)

    def auc(X):
        return np.array(
            [np.trapezoid(concentration(t, 100.0, X[r, 0], X[r, 1], X[r, 2]), t)
             for r in range(X.shape[0])]
        )

    r = sobol_indices(auc, ["CL", "Vd", "ka"], [(2.0, 10.0), (30.0, 80.0), (0.5, 2.0)],
                      n_base=256, n_boot=30)
    assert r.first_order["CL"] > 0.95
    assert r.first_order["Vd"] < 0.05
    assert r.first_order["ka"] < 0.05
    assert r.total_order["CL"] > 0.95


def test_constant_model_is_flagged_rather_than_divided_by_zero():
    r = sobol_indices(lambda X: np.ones(X.shape[0]), ["a", "b"],
                      [(1.0, 2.0)] * 2, n_base=32, n_boot=10)
    assert r.output_variance == pytest.approx(0.0, abs=1e-12)
    assert not r.converged
    assert any("constant" in w for w in r.warnings)


# ---------------------------------------------------------------- diagnostics


def test_indices_are_bounded_to_the_unit_interval():
    r = sobol_indices(ishigami, ["x1", "x2", "x3"], [(-np.pi, np.pi)] * 3,
                      n_base=512, log_scale=False, n_boot=20)
    for d in (r.first_order, r.total_order, r.interaction):
        assert all(0.0 <= v <= 1.0 for v in d.values())


def test_undersampling_is_reported_rather_than_returned_silently():
    """The failure this guards against: at small n_base the fluoxetine trough
    case reported first-order indices summing to 1.48 with no complaint."""
    t = np.linspace(0, 24, 241)

    def trough(X):
        return np.array(
            [concentration(t, 20.0, X[r, 0], X[r, 1], X[r, 2])[-1] for r in range(X.shape[0])]
        )

    noisy = sobol_indices(trough, ["CL", "Vd", "ka"],
                          [(12.8, 48.7), (1543.0, 4051.0), (0.38, 1.70)],
                          n_base=16, n_boot=20)
    settled = sobol_indices(trough, ["CL", "Vd", "ka"],
                            [(12.8, 48.7), (1543.0, 4051.0), (0.38, 1.70)],
                            n_base=4096, n_boot=20)
    assert not noisy.converged and noisy.warnings
    assert settled.converged, settled.warnings


def test_model_evaluation_count_matches_the_saltelli_scheme():
    r = sobol_indices(ishigami, ["x1", "x2", "x3"], [(-np.pi, np.pi)] * 3,
                      n_base=128, log_scale=False, n_boot=10)
    assert r.n_model_evaluations == 128 * (3 + 2)


def test_results_are_reproducible_for_a_fixed_seed():
    args = (ishigami, ["x1", "x2", "x3"], [(-np.pi, np.pi)] * 3)
    a = sobol_indices(*args, n_base=256, log_scale=False, seed=11, n_boot=10)
    b = sobol_indices(*args, n_base=256, log_scale=False, seed=11, n_boot=10)
    assert a.first_order == b.first_order
    assert a.total_order == b.total_order


# ------------------------------------------------------------------- endpoint


def test_endpoint_ranks_parameters_for_each_metric(client):
    for metric in ("cmax", "auc", "trough", "tmax"):
        r = client.post("/api/advanced/sensitivity",
                        json={"medication_id": 1, "metric": metric})
        assert r.status_code == 200, metric
        body = r.json()
        assert body["dominant_parameter"] in ("CL", "Vd", "ka")
        assert body["ranking"][0] == body["dominant_parameter"]
        assert body["converged"] is True, body["warnings"]


def test_tmax_is_driven_by_absorption_rate(client):
    """Time to peak is set by ka; a sensitivity analysis that says otherwise
    would be wrong on a case with a known answer."""
    body = client.post("/api/advanced/sensitivity",
                       json={"medication_id": 1, "metric": "tmax"}).json()
    assert body["dominant_parameter"] == "ka"
    assert body["total_order"]["ka"] > 0.5


def test_endpoint_rejects_an_unknown_metric(client):
    assert client.post("/api/advanced/sensitivity",
                       json={"medication_id": 1, "metric": "nope"}).status_code == 400


def test_endpoint_requires_pk_parameters(client):
    assert client.post("/api/advanced/sensitivity", json={"dose_mg": 20}).status_code == 400
