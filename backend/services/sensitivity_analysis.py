"""Variance-based global sensitivity analysis (Sobol indices).

The Monte Carlo module answers "how much does the predicted concentration
vary?". This one answers "*which* parameter's uncertainty is responsible?",
which is the question that tells you what to measure.

One-at-a-time sensitivity, the usual informal approach, only probes a single
point in parameter space and cannot see interactions at all. Sobol indices
decompose the output variance over the whole input distribution:

    Var(Y) = sum_i V_i + sum_{i<j} V_ij + ... + V_{1..k}

giving a first-order index S_i (the variance removed by learning X_i alone)
and a total index S_Ti (the variance remaining if everything except X_i were
learned). The gap S_Ti - S_i is exactly the share of variance that X_i carries
through interactions rather than on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np


@dataclass
class SobolResult:
    parameter_names: list[str]
    first_order: dict[str, float]
    total_order: dict[str, float]
    interaction: dict[str, float]
    first_order_ci95: dict[str, tuple[float, float]]
    total_order_ci95: dict[str, tuple[float, float]]
    output_mean: float
    output_variance: float
    n_base_samples: int
    n_model_evaluations: int
    sum_first_order: float
    converged: bool
    warnings: list[str]


def saltelli_sample(
    bounds: Sequence[tuple[float, float]],
    n_base: int,
    seed: int | None = 0,
    log_scale: bool = True,
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    """Saltelli's cross-sampling scheme.

    Two independent matrices A and B of shape (n_base, k), plus k matrices
    AB_i which are A with column i replaced by B's. Total cost is
    n_base * (k + 2) model evaluations.

    PK parameters are positive and span orders of magnitude, so by default the
    sampling is uniform in log space: that treats "clearance doubles" and
    "clearance halves" as equally sized perturbations, which is how
    inter-individual variability actually behaves.
    """
    rng = np.random.default_rng(seed)
    k = len(bounds)
    lo = np.array([b[0] for b in bounds], dtype=float)
    hi = np.array([b[1] for b in bounds], dtype=float)
    if np.any(hi <= lo):
        raise ValueError("each bound must have hi > lo")
    if log_scale:
        if np.any(lo <= 0):
            raise ValueError("log-scale sampling requires strictly positive bounds")
        lo, hi = np.log(lo), np.log(hi)

    A = lo + (hi - lo) * rng.random((n_base, k))
    B = lo + (hi - lo) * rng.random((n_base, k))
    AB = []
    for i in range(k):
        ab = A.copy()
        ab[:, i] = B[:, i]
        AB.append(np.exp(ab) if log_scale else ab)
    return (np.exp(A) if log_scale else A, np.exp(B) if log_scale else B, AB)


def _bootstrap_ci(
    numerator_terms: np.ndarray, denominator: float, n_boot: int, rng: np.random.Generator
) -> tuple[float, float]:
    """Percentile CI for an index that is a mean of per-sample terms over Var(Y)."""
    if denominator <= 0 or numerator_terms.size == 0:
        return (float("nan"), float("nan"))
    n = numerator_terms.size
    idx = rng.integers(0, n, size=(n_boot, n))
    est = numerator_terms[idx].mean(axis=1) / denominator
    return (float(np.percentile(est, 2.5)), float(np.percentile(est, 97.5)))


def sobol_indices(
    model: Callable[[np.ndarray], np.ndarray],
    parameter_names: Sequence[str],
    bounds: Sequence[tuple[float, float]],
    n_base: int = 256,
    seed: int | None = 0,
    log_scale: bool = True,
    n_boot: int = 200,
) -> SobolResult:
    """First-order and total-effect Sobol indices.

    `model` maps an (n, k) array of parameter sets to an (n,) array of scalar
    outputs, so it is evaluated in batches rather than per sample.

    Estimators are the standard ones (Saltelli 2010, Jansen for the total
    index), which are unbiased and well behaved when an index is near zero:

        S_i   = mean( f_B * (f_ABi - f_A) ) / Var(Y)
        S_Ti  = mean( (f_A - f_ABi)^2 ) / (2 Var(Y))

    Jansen's total-order form is used because the alternative
    1 - mean(f_B f_ABi)/Var(Y) is a difference of similar quantities and loses
    precision exactly where the index is small.
    """
    k = len(parameter_names)
    if len(bounds) != k:
        raise ValueError("bounds and parameter_names must have the same length")
    if n_base < 8:
        raise ValueError("n_base must be at least 8 for a usable estimate")

    A, B, AB = saltelli_sample(bounds, n_base, seed=seed, log_scale=log_scale)
    f_A = np.asarray(model(A), dtype=float).ravel()
    f_B = np.asarray(model(B), dtype=float).ravel()
    f_AB = [np.asarray(model(ab), dtype=float).ravel() for ab in AB]

    all_out = np.concatenate([f_A, f_B])
    var_y = float(np.var(all_out, ddof=1))
    mean_y = float(np.mean(all_out))

    rng = np.random.default_rng((seed or 0) + 991)
    first, total, inter = {}, {}, {}
    first_ci, total_ci = {}, {}

    for i, name in enumerate(parameter_names):
        s_terms = f_B * (f_AB[i] - f_A)
        t_terms = 0.5 * (f_A - f_AB[i]) ** 2
        s_i = float(np.mean(s_terms) / var_y) if var_y > 0 else 0.0
        t_i = float(np.mean(t_terms) / var_y) if var_y > 0 else 0.0
        # Indices are variance shares, so clip the estimator noise that can
        # push a near-zero index slightly negative.
        first[name] = float(np.clip(s_i, 0.0, 1.0))
        total[name] = float(np.clip(t_i, 0.0, 1.0))
        inter[name] = float(max(total[name] - first[name], 0.0))
        first_ci[name] = _bootstrap_ci(s_terms, var_y, n_boot, rng)
        total_ci[name] = _bootstrap_ci(t_terms, var_y, n_boot, rng)

    sum_first = float(sum(first.values()))

    # Convergence diagnostics. Under-sampling does not announce itself: the
    # estimator simply returns confident nonsense. Two identities have to hold
    # for any valid decomposition, and violating either means the sample is too
    # small rather than the model being strange.
    #
    #   S_Ti >= S_i          a factor cannot explain more alone than in total
    #   sum_i S_i <= 1       first-order shares cannot exceed the whole variance
    #
    # Both are checked against a tolerance, and the widest bootstrap interval is
    # reported, so a noisy result is labelled instead of being taken at face
    # value. This was not hypothetical: at n_base = 512 the fluoxetine trough
    # case reported first-order indices summing to 1.48.
    warnings: list[str] = []
    tol = 0.05
    for name in parameter_names:
        if total[name] < first[name] - tol:
            warnings.append(
                f"total-order index for {name} fell below its first-order index "
                f"({total[name]:.3f} < {first[name]:.3f}); increase n_base"
            )
    if sum_first > 1.0 + tol:
        warnings.append(
            f"first-order indices sum to {sum_first:.3f} > 1; increase n_base"
        )
    widest = 0.0
    for name in parameter_names:
        for lo_hi in (first_ci[name], total_ci[name]):
            if all(np.isfinite(lo_hi)):
                widest = max(widest, lo_hi[1] - lo_hi[0])
    if widest > 0.5:
        warnings.append(
            f"widest 95% bootstrap interval spans {widest:.2f} of the variance; "
            "the ranking is not yet resolved"
        )
    if var_y <= 0:
        warnings.append("output variance is zero; the model is constant over the sampled range")

    converged = (
        var_y > 0
        and not warnings
        and all(np.isfinite(v) for v in list(first.values()) + list(total.values()))
    )

    return SobolResult(
        parameter_names=list(parameter_names),
        first_order=first,
        total_order=total,
        interaction=inter,
        first_order_ci95=first_ci,
        total_order_ci95=total_ci,
        output_mean=mean_y,
        output_variance=var_y,
        n_base_samples=n_base,
        n_model_evaluations=int(n_base * (k + 2)),
        sum_first_order=sum_first,
        converged=bool(converged),
        warnings=warnings,
    )
