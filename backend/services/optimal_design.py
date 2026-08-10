"""Optimal experimental design for therapeutic drug monitoring.

The Bayesian PK module answers "given these levels, what are this patient's
parameters?". This module answers the question that comes first: *when should
the levels be drawn?*

A trough-only sampling schedule, which is what routine TDM usually collects,
is close to uninformative about absorption and only weakly informative about
volume of distribution. Two samples placed well can identify parameters that
six badly placed samples cannot, which matters when every sample is a needle.

The criterion is D-optimality: maximise the determinant of the Fisher
information matrix, equivalently minimise the volume of the joint confidence
ellipsoid for the parameter estimates.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np

# Parameters the design is optimised for, in the order used by every matrix
# below. Optimising in log space matches how the Bayesian module parameterises
# the model and makes the information matrix scale-free, so a determinant
# comparison is not dominated by the units of one parameter.
PARAM_NAMES = ("log_CL", "log_Vd", "log_ka")


@dataclass
class DesignResult:
    sampling_times_h: list[float]
    fisher_information: list[list[float]]
    d_criterion: float
    log_det_fim: float
    parameter_names: list[str]
    relative_standard_errors_pct: dict[str, float]
    correlation_matrix: list[list[float]]
    condition_number: float
    d_efficiency_vs_reference_pct: float | None = None
    reference_times_h: list[float] | None = None
    candidate_grid_h: list[float] = field(default_factory=list)
    grid_step_h: float = 0.0


def concentration(t: np.ndarray, dose_mg: float, cl: float, vd: float, ka: float, f: float = 1.0) -> np.ndarray:
    """One-compartment oral (Bateman) concentration in mg/L."""
    t = np.asarray(t, dtype=float)
    ke = cl / vd
    if abs(ka - ke) < 1e-9:
        # Degenerate flip-flop case: the Bateman limit as ka -> ke.
        return (f * dose_mg / vd) * ke * t * np.exp(-ke * t)
    return (f * dose_mg * ka) / (vd * (ka - ke)) * (np.exp(-ke * t) - np.exp(-ka * t))


def sensitivity_matrix(
    times_h: np.ndarray,
    dose_mg: float,
    cl: float,
    vd: float,
    ka: float,
    f: float = 1.0,
    step: float = 1e-5,
) -> np.ndarray:
    """d c / d theta at each sampling time, theta = (log CL, log Vd, log ka).

    Central differences in log space. A closed form exists for the Bateman
    equation, but differencing keeps this correct if the structural model is
    later swapped for the full coupled simulator.
    """
    times_h = np.asarray(times_h, dtype=float)
    theta = np.log(np.array([cl, vd, ka], dtype=float))
    S = np.zeros((times_h.size, theta.size))
    for j in range(theta.size):
        up, dn = theta.copy(), theta.copy()
        up[j] += step
        dn[j] -= step
        c_up = concentration(times_h, dose_mg, *np.exp(up), f=f)
        c_dn = concentration(times_h, dose_mg, *np.exp(dn), f=f)
        S[:, j] = (c_up - c_dn) / (2.0 * step)
    return S


def fisher_information(
    times_h,
    dose_mg: float,
    cl: float,
    vd: float,
    ka: float,
    sigma_prop: float = 0.2,
    sigma_add_mg_l: float = 0.0,
    f: float = 1.0,
) -> np.ndarray:
    """FIM for independent observations with a combined error model.

    With c_i observed as c(t_i) + eps_i and Var(eps_i) = (sigma_prop*c_i)^2 +
    sigma_add^2, the information contributed by sample i is
    s_i s_i^T / Var_i, so noisier samples are down-weighted automatically.
    That is what stops the optimiser from stacking samples at the peak, where
    the signal is largest but proportional error is largest too.
    """
    times_h = np.atleast_1d(np.asarray(times_h, dtype=float))
    S = sensitivity_matrix(times_h, dose_mg, cl, vd, ka, f=f)
    c = concentration(times_h, dose_mg, cl, vd, ka, f=f)
    var = (sigma_prop * c) ** 2 + sigma_add_mg_l**2
    var = np.maximum(var, 1e-12)
    return (S / var[:, None]).T @ S


def _summarise(fim: np.ndarray) -> tuple[float, dict[str, float], list[list[float]], float]:
    """log|FIM|, relative standard errors, parameter correlations, conditioning."""
    sign, logdet = np.linalg.slogdet(fim)
    if sign <= 0 or not np.isfinite(logdet):
        return float("-inf"), {p: float("inf") for p in PARAM_NAMES}, [], float("inf")

    cov = np.linalg.inv(fim)
    sd = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    # Parameters are in log space, so the standard error is already relative.
    rse = {name: float(100.0 * s) for name, s in zip(PARAM_NAMES, sd)}
    outer = np.outer(sd, sd)
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.where(outer > 0, cov / outer, 0.0)
    eig = np.linalg.eigvalsh(fim)
    cond = float(eig.max() / eig.min()) if eig.min() > 0 else float("inf")
    return float(logdet), rse, corr.tolist(), cond


def evaluate_design(
    times_h,
    dose_mg: float,
    cl: float,
    vd: float,
    ka: float,
    sigma_prop: float = 0.2,
    sigma_add_mg_l: float = 0.0,
) -> DesignResult:
    """Score a given sampling schedule."""
    times = sorted(float(t) for t in times_h)
    fim = fisher_information(times, dose_mg, cl, vd, ka, sigma_prop, sigma_add_mg_l)
    logdet, rse, corr, cond = _summarise(fim)
    return DesignResult(
        sampling_times_h=times,
        fisher_information=fim.tolist(),
        d_criterion=float(np.exp(logdet / len(PARAM_NAMES))) if np.isfinite(logdet) else 0.0,
        log_det_fim=logdet,
        parameter_names=list(PARAM_NAMES),
        relative_standard_errors_pct=rse,
        correlation_matrix=corr,
        condition_number=cond,
    )


def optimize_sampling_times(
    dose_mg: float,
    cl: float,
    vd: float,
    ka: float,
    n_samples: int = 3,
    horizon_h: float = 24.0,
    grid_step_h: float = 0.5,
    min_time_h: float = 0.25,
    sigma_prop: float = 0.2,
    sigma_add_mg_l: float = 0.0,
    reference_times_h=None,
) -> DesignResult:
    """D-optimal sampling times on a discrete grid.

    The design space is a grid of candidate times, and the search is exhaustive
    over combinations. That is exponential in `n_samples`, but the realistic
    range is two to four samples on a grid of tens of points, which is a few
    thousand determinant evaluations of a 3x3 matrix. An exact answer on the
    grid is worth more here than a fast approximate one, and it removes any
    question of a local optimum.
    """
    if n_samples < 1:
        raise ValueError("n_samples must be at least 1")
    if n_samples > 6:
        raise ValueError("n_samples above 6 is beyond the intended design space")
    if horizon_h <= min_time_h:
        raise ValueError("horizon_h must exceed min_time_h")

    grid = np.arange(min_time_h, horizon_h + 1e-9, grid_step_h)
    if grid.size < n_samples:
        raise ValueError("grid is too coarse for the requested number of samples")

    # The exhaustive search is C(|grid|, n_samples), which grows fast enough to
    # blow a request timeout at four or more samples on a fine grid. Coarsen the
    # grid until the count is affordable rather than silently taking minutes;
    # the chosen step is reported so the resolution is never a hidden detail.
    max_combinations = 60_000
    while (
        math.comb(grid.size, n_samples) > max_combinations
        and grid.size > n_samples + 1
    ):
        grid_step_h *= 2.0
        grid = np.arange(min_time_h, horizon_h + 1e-9, grid_step_h)

    best_logdet, best_times = float("-inf"), None
    for combo in itertools.combinations(grid.tolist(), n_samples):
        fim = fisher_information(combo, dose_mg, cl, vd, ka, sigma_prop, sigma_add_mg_l)
        sign, logdet = np.linalg.slogdet(fim)
        if sign > 0 and logdet > best_logdet:
            best_logdet, best_times = logdet, combo

    if best_times is None:
        # Fewer samples than parameters leaves the FIM singular by construction;
        # report the schedule rather than pretending it is identifiable.
        best_times = tuple(np.linspace(min_time_h, horizon_h, n_samples).tolist())

    result = evaluate_design(
        best_times, dose_mg, cl, vd, ka, sigma_prop, sigma_add_mg_l
    )
    result.candidate_grid_h = grid.tolist()
    result.grid_step_h = float(grid_step_h)

    if reference_times_h:
        ref = evaluate_design(
            reference_times_h, dose_mg, cl, vd, ka, sigma_prop, sigma_add_mg_l
        )
        result.reference_times_h = ref.sampling_times_h
        # D-efficiency compares designs on a per-parameter scale, so a value of
        # 50% means the reference needs roughly twice the information to match.
        if np.isfinite(ref.log_det_fim) and np.isfinite(result.log_det_fim):
            ratio = np.exp((ref.log_det_fim - result.log_det_fim) / len(PARAM_NAMES))
            result.d_efficiency_vs_reference_pct = float(100.0 * ratio)
        else:
            result.d_efficiency_vs_reference_pct = 0.0

    return result
