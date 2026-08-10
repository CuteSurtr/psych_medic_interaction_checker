"""Identifiability analysis: can these parameters be recovered at all?

Fitting always returns numbers. Whether those numbers mean anything is a
separate question, and it is the one this module answers before any estimate is
reported as a result.

Two distinct failures are diagnosed:

**Structural** - the model itself cannot distinguish two parameter sets, no
matter how good the data. Detected from the rank and conditioning of the
sensitivity matrix, and localised with a collinearity index that names the
offending combination.

**Practical** - the model could distinguish them in principle, but this
particular sampling schedule and noise level cannot. Detected by profiling the
likelihood: a parameter whose profile stays flat as it is moved away from the
optimum has no confidence bound in that direction.

The distinction matters clinically. Structural non-identifiability is fixed by
changing the model; practical non-identifiability is fixed by drawing a
different sample, which is exactly what section XVII computes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize, minimize_scalar

from services.optimal_design import PARAM_NAMES, concentration, sensitivity_matrix


@dataclass
class ProfileResult:
    parameter: str
    grid: list[float]
    profile_nll: list[float]
    mle: float
    ci_lower: float | None
    ci_upper: float | None
    identifiable: bool
    verdict: str


@dataclass
class IdentifiabilityResult:
    parameter_names: list[str]
    rank: int
    n_parameters: int
    structurally_identifiable: bool
    condition_number: float
    singular_values: list[float]
    collinearity_index: float
    worst_direction: dict[str, float]
    profiles: list[ProfileResult] = field(default_factory=list)
    practically_identifiable: bool = True
    notes: list[str] = field(default_factory=list)


def _normalised_sensitivity(times_h, dose_mg, cl, vd, ka) -> np.ndarray:
    """Sensitivity matrix with each column scaled to unit length.

    Columns are normalised so the collinearity index measures the *angle*
    between parameter effects rather than their relative magnitudes: two
    parameters can have very different influence and still be perfectly
    distinguishable, or nearly identical influence and be hopeless.
    """
    S = sensitivity_matrix(np.asarray(times_h, dtype=float), dose_mg, cl, vd, ka)
    norms = np.linalg.norm(S, axis=0)
    norms = np.where(norms > 0, norms, 1.0)
    return S / norms


def structural_identifiability(
    times_h, dose_mg: float, cl: float, vd: float, ka: float, tol: float = 1e-8
) -> IdentifiabilityResult:
    """Rank, conditioning and collinearity of the sensitivity matrix.

    The collinearity index is gamma = 1/sqrt(lambda_min) of the normalised
    S^T S. Brun et al. (2001) treat gamma above roughly 10 to 20 as the point
    where parameter combinations stop being separable in practice; gamma is
    unbounded and diverges as the columns become linearly dependent.
    """
    Sn = _normalised_sensitivity(times_h, dose_mg, cl, vd, ka)
    svals = np.linalg.svd(Sn, compute_uv=False)
    rank = int(np.sum(svals > tol * max(svals.max(), 1.0)))
    cond = float(svals.max() / svals.min()) if svals.min() > 0 else float("inf")

    eigvals, eigvecs = np.linalg.eigh(Sn.T @ Sn)
    lam_min = float(max(eigvals.min(), 0.0))
    gamma = float(1.0 / np.sqrt(lam_min)) if lam_min > 1e-15 else float("inf")
    # The eigenvector of the smallest eigenvalue is the direction in parameter
    # space the data constrains least, which is the combination to report.
    worst = eigvecs[:, int(np.argmin(eigvals))]
    worst_direction = {n: float(w) for n, w in zip(PARAM_NAMES, worst)}

    notes: list[str] = []
    if rank < len(PARAM_NAMES):
        notes.append(
            f"sensitivity matrix is rank {rank} for {len(PARAM_NAMES)} parameters: "
            "at least one parameter combination has no effect on the prediction"
        )
    if gamma > 20:
        dominant = sorted(worst_direction.items(), key=lambda kv: -abs(kv[1]))[:2]
        combo = " and ".join(f"{k} ({v:+.2f})" for k, v in dominant)
        notes.append(
            f"collinearity index {gamma:.1f} exceeds 20; the data mainly "
            f"constrains a combination of {combo} rather than each separately"
        )

    return IdentifiabilityResult(
        parameter_names=list(PARAM_NAMES),
        rank=rank,
        n_parameters=len(PARAM_NAMES),
        structurally_identifiable=bool(rank == len(PARAM_NAMES) and gamma <= 20),
        condition_number=cond,
        singular_values=svals.tolist(),
        collinearity_index=gamma,
        worst_direction=worst_direction,
        notes=notes,
    )


def _nll(theta_log, times, obs, dose, sigma_prop) -> float:
    """Negative log-likelihood under a proportional error model."""
    cl, vd, ka = np.exp(theta_log)
    pred = concentration(times, dose, cl, vd, ka)
    pred = np.maximum(pred, 1e-12)
    sd = np.maximum(sigma_prop * pred, 1e-12)
    return float(0.5 * np.sum(((obs - pred) / sd) ** 2 + 2.0 * np.log(sd)))


def fit_mle(times, obs, dose_mg: float, start, sigma_prop: float = 0.2) -> np.ndarray:
    """Maximum-likelihood parameters in log space, starting from `start`.

    The profile must be measured against the *actual* maximum of the
    likelihood for this data, not against the parameters that generated it.
    With noisy observations the two differ, and using the generating values as
    the reference makes the profile dip below zero and shifts every confidence
    interval, because the chi-squared threshold is defined relative to the
    attained maximum.
    """
    theta0 = np.log(np.asarray(start, dtype=float))
    res = minimize(
        _nll, theta0, args=(np.asarray(times, float), np.asarray(obs, float), dose_mg, sigma_prop),
        method="Nelder-Mead",
        options={"xatol": 1e-10, "fatol": 1e-12, "maxiter": 5000},
    )
    return res.x if res.success else theta0


def profile_likelihood(
    parameter: str,
    times_h,
    observations,
    dose_mg: float,
    mle: tuple[float, float, float],
    sigma_prop: float = 0.2,
    n_grid: int = 25,
    span: float = 1.5,
    delta_threshold: float = 1.92,
) -> ProfileResult:
    """Profile the likelihood for one parameter, re-optimising the others.

    At each fixed value of the parameter of interest the remaining parameters
    are re-fitted, which is what distinguishes a profile from a naive slice: a
    slice can look sharply curved simply because the other parameters were held
    at values that no longer fit.

    The threshold is the standard chi-squared bound, delta NLL = 1.92 for a 95%
    interval on one parameter. A profile that never crosses it on one side has
    **no confidence bound** in that direction, which is the signature of
    practical non-identifiability.
    """
    if parameter not in PARAM_NAMES:
        raise ValueError(f"parameter must be one of {PARAM_NAMES}")
    idx = PARAM_NAMES.index(parameter)
    times = np.asarray(times_h, dtype=float)
    obs = np.asarray(observations, dtype=float)
    theta_hat = fit_mle(times, obs, dose_mg, mle, sigma_prop)
    nll_hat = _nll(theta_hat, times, obs, dose_mg, sigma_prop)

    others = [j for j in range(len(PARAM_NAMES)) if j != idx]
    grid = np.linspace(theta_hat[idx] - span, theta_hat[idx] + span, n_grid)
    profile = []
    for value in grid:
        theta = theta_hat.copy()
        theta[idx] = value

        # Re-optimise the nuisance parameters one at a time. Coordinate descent
        # over two parameters converges quickly here and avoids depending on a
        # multivariate optimiser's starting point.
        for _ in range(6):
            for j in others:
                def obj(x, j=j, theta=theta):
                    trial = theta.copy()
                    trial[j] = x
                    return _nll(trial, times, obs, dose_mg, sigma_prop)

                res = minimize_scalar(
                    obj, bounds=(theta[j] - 3.0, theta[j] + 3.0), method="bounded"
                )
                if res.success:
                    theta[j] = res.x
        profile.append(_nll(theta, times, obs, dose_mg, sigma_prop) - nll_hat)

    profile_arr = np.array(profile)
    centre = int(np.argmin(np.abs(grid - theta_hat[idx])))

    def crossing(side: str) -> float | None:
        rng = range(centre, -1, -1) if side == "lower" else range(centre, len(grid))
        for i in rng:
            if profile_arr[i] >= delta_threshold:
                return float(np.exp(grid[i]))
        return None

    lower, upper = crossing("lower"), crossing("upper")
    identifiable = lower is not None and upper is not None
    if identifiable:
        verdict = "identifiable: the profile is bounded on both sides"
    elif lower is None and upper is None:
        verdict = "not identifiable: the profile is flat in both directions"
    else:
        missing = "upper" if upper is None else "lower"
        verdict = f"one-sided: no {missing} bound within the searched range"

    return ProfileResult(
        parameter=parameter,
        grid=[float(np.exp(g)) for g in grid],
        profile_nll=profile_arr.tolist(),
        mle=float(np.exp(theta_hat[idx])),
        ci_lower=lower,
        ci_upper=upper,
        identifiable=identifiable,
        verdict=verdict,
    )


def analyse(
    times_h,
    observations,
    dose_mg: float,
    mle: tuple[float, float, float],
    sigma_prop: float = 0.2,
    run_profiles: bool = True,
    n_grid: int = 21,
) -> IdentifiabilityResult:
    """Structural diagnosis, then practical diagnosis by profiling."""
    cl, vd, ka = mle
    result = structural_identifiability(times_h, dose_mg, cl, vd, ka)
    if not run_profiles:
        return result

    for name in PARAM_NAMES:
        result.profiles.append(
            profile_likelihood(
                name, times_h, observations, dose_mg, mle,
                sigma_prop=sigma_prop, n_grid=n_grid,
            )
        )
    result.practically_identifiable = all(p.identifiable for p in result.profiles)
    for p in result.profiles:
        if not p.identifiable:
            result.notes.append(f"{p.parameter}: {p.verdict}")
    return result
