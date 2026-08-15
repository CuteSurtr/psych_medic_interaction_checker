"""Error metrics for comparing NeuroTrace predictions against published data.

Deliberately plain functions over arrays or scalars so a scenario can report
whichever metrics its endpoint actually supports. An AUC ratio reported as a
single number does not get a spurious RMSE.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

Number = float | int
ArrayLike = Number | list[Number] | np.ndarray


def _arr(x: ArrayLike) -> np.ndarray:
    return np.atleast_1d(np.asarray(x, dtype=float))


def absolute_error(observed: ArrayLike, predicted: ArrayLike) -> float:
    return float(np.mean(np.abs(_arr(predicted) - _arr(observed))))


def relative_error(observed: ArrayLike, predicted: ArrayLike) -> float:
    o, p = _arr(observed), _arr(predicted)
    with np.errstate(divide='ignore', invalid='ignore'):
        return float(np.mean(np.where(o != 0, (p - o) / o, np.nan)))


def percent_error(observed: ArrayLike, predicted: ArrayLike) -> float:
    """Signed. Positive means the model over-predicts."""
    return 100.0 * relative_error(observed, predicted)


def mean_absolute_percentage_error(observed: ArrayLike, predicted: ArrayLike) -> float:
    o, p = _arr(observed), _arr(predicted)
    with np.errstate(divide='ignore', invalid='ignore'):
        return float(100.0 * np.mean(np.abs(np.where(o != 0, (p - o) / o, np.nan))))


def root_mean_squared_error(observed: ArrayLike, predicted: ArrayLike) -> float:
    return float(np.sqrt(np.mean((_arr(predicted) - _arr(observed)) ** 2)))


def bias(observed: ArrayLike, predicted: ArrayLike) -> float:
    """Mean signed deviation. Distinguishes systematic offset from scatter."""
    return float(np.mean(_arr(predicted) - _arr(observed)))


def coverage_of_observed_range(
    observed_low: float,
    observed_high: float,
    predicted_low: float | None,
    predicted_high: float | None,
) -> float:
    """Fraction of the published interval covered by the predicted interval.

    1.0 means the prediction spans the whole observed range. 0.0 means no
    overlap. Returns nan when the model produced no interval, rather than
    pretending to a coverage of zero.
    """
    if predicted_low is None or predicted_high is None:
        return float('nan')
    width = observed_high - observed_low
    if width <= 0:
        return 1.0 if predicted_low <= observed_low <= predicted_high else 0.0
    overlap = min(observed_high, predicted_high) - max(observed_low, predicted_low)
    return float(max(0.0, overlap) / width)


@dataclass
class EndpointResult:
    """One endpoint compared against literature."""

    name: str
    units: str
    observed: float | None
    predicted: float | None
    observed_low: float | None = None
    observed_high: float | None = None
    predicted_low: float | None = None
    predicted_high: float | None = None
    acceptance: str = ''
    status: str = 'NOT_RUN'
    reason: str = ''
    metrics: dict[str, float] = field(default_factory=dict)
    source_key: str = ''

    def compute(self) -> None:
        if self.observed is None or self.predicted is None:
            return
        self.metrics['absolute_error'] = absolute_error(self.observed, self.predicted)
        self.metrics['percent_error'] = percent_error(self.observed, self.predicted)
        self.metrics['mean_absolute_percentage_error'] = mean_absolute_percentage_error(
            self.observed, self.predicted
        )
        self.metrics['bias'] = bias(self.observed, self.predicted)
        if self.observed_low is not None and self.observed_high is not None:
            self.metrics['coverage_of_observed_range'] = coverage_of_observed_range(
                self.observed_low, self.observed_high,
                self.predicted_low, self.predicted_high,
            )


def aggregate(results: list[EndpointResult]) -> dict[str, float | int]:
    """Suite-level statistics. Includes failures; nothing is filtered out."""
    scored = [r for r in results if 'mean_absolute_percentage_error' in r.metrics]
    apes = [r.metrics['mean_absolute_percentage_error'] for r in scored]
    apes = [a for a in apes if not np.isnan(a)]
    passed = sum(1 for r in results if r.status == 'PASS')
    total_judged = sum(1 for r in results if r.status in ('PASS', 'FAIL'))
    return {
        'n_endpoints': len(results),
        'n_judged': total_judged,
        'n_pass': passed,
        'n_fail': sum(1 for r in results if r.status == 'FAIL'),
        'n_not_run': sum(1 for r in results if r.status not in ('PASS', 'FAIL')),
        'median_absolute_percent_error': float(np.median(apes)) if apes else float('nan'),
        'mean_absolute_percent_error': float(np.mean(apes)) if apes else float('nan'),
        'max_absolute_percent_error': float(np.max(apes)) if apes else float('nan'),
        'fraction_within_acceptance': (passed / total_judged) if total_judged else float('nan'),
    }
