"""Validation scenario loading, acceptance evaluation and reporting.

Acceptance criteria are per-endpoint and, wherever possible, are the published
range itself rather than an invented tolerance. A scenario may only use a bare
percent-error threshold if it supplies a written justification, so an arbitrary
"PASS if error < 10%" cannot be introduced silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from metrics import EndpointResult, aggregate

VALIDATION_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_DIR = VALIDATION_ROOT / 'scenarios'
REPORT_DIR = VALIDATION_ROOT / 'reports'


class AcceptanceError(ValueError):
    pass


@dataclass
class Endpoint:
    name: str
    units: str
    acceptance: dict[str, Any]
    observed: float | None = None
    observed_low: float | None = None
    observed_high: float | None = None
    source_key: str = ''
    note: str = ''

    def evaluate(self, predicted: float | None,
                 predicted_low: float | None = None,
                 predicted_high: float | None = None) -> EndpointResult:
        r = EndpointResult(
            name=self.name, units=self.units,
            observed=self.observed, predicted=predicted,
            observed_low=self.observed_low, observed_high=self.observed_high,
            predicted_low=predicted_low, predicted_high=predicted_high,
            source_key=self.source_key,
        )
        if predicted is None:
            r.status = 'NOT_RUN'
            r.reason = 'model produced no value for this endpoint'
            return r

        kind = self.acceptance.get('type')

        if kind == 'within_literature_range':
            lo = float(self.acceptance['low'])
            hi = float(self.acceptance['high'])
            r.acceptance = f'within published range {lo} to {hi} {self.units}'
            ok = lo <= predicted <= hi
            r.status = 'PASS' if ok else 'FAIL'
            r.reason = (
                f'{predicted:.4g} {"lies within" if ok else "falls outside"} '
                f'the published range {lo}-{hi}'
            )

        elif kind == 'direction':
            expected = self.acceptance['expected']
            ref = float(self.acceptance.get('reference', 0.0))
            r.acceptance = f'direction {expected} relative to {ref}'
            ok = (predicted > ref) if expected == 'increase' else (predicted < ref)
            r.status = 'PASS' if ok else 'FAIL'
            r.reason = (
                f'predicted {predicted:.4g} vs reference {ref:.4g}: '
                f'{"correct" if ok else "WRONG"} direction'
            )

        elif kind == 'percent_error':
            just = self.acceptance.get('justification', '').strip()
            if not just:
                raise AcceptanceError(
                    f'Endpoint {self.name!r} uses a percent_error threshold with no '
                    f'justification. Either cite a published range via '
                    f'within_literature_range, or state why this tolerance is '
                    f'scientifically defensible.'
                )
            tol = float(self.acceptance['tolerance_percent'])
            r.acceptance = f'|percent error| <= {tol}% ({just})'
            r.compute()
            err = abs(r.metrics.get('percent_error', float('inf')))
            r.status = 'PASS' if err <= tol else 'FAIL'
            r.reason = f'|percent error| {err:.1f}% vs tolerance {tol}%'

        else:
            raise AcceptanceError(
                f'Endpoint {self.name!r}: unknown acceptance type {kind!r}'
            )

        r.compute()
        return r


@dataclass
class Scenario:
    key: str
    title: str
    description: str
    validation_type: str
    driver: str
    endpoints: list[Endpoint]
    evidence_file: str = ''
    parameterisation_sources: list[str] = field(default_factory=list)
    validation_sources: list[str] = field(default_factory=list)
    regimen: dict[str, Any] = field(default_factory=dict)
    population: str = ''
    limitations: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> Scenario:
        raw = yaml.safe_load(path.read_text(encoding='utf-8'))
        eps = [
            Endpoint(
                name=e['name'], units=e.get('units', ''),
                acceptance=e['acceptance'], observed=e.get('observed'),
                observed_low=e.get('observed_low'), observed_high=e.get('observed_high'),
                source_key=e.get('source_key', ''), note=e.get('note', ''),
            )
            for e in raw['endpoints']
        ]
        return cls(
            key=raw['key'], title=raw['title'], description=raw.get('description', ''),
            validation_type=raw.get('validation_type', 'unspecified'),
            driver=raw['driver'], endpoints=eps,
            evidence_file=raw.get('evidence_file', ''),
            parameterisation_sources=raw.get('parameterisation_sources', []),
            validation_sources=raw.get('validation_sources', []),
            regimen=raw.get('regimen', {}), population=raw.get('population', ''),
            limitations=raw.get('limitations', []),
        )


def load_all(directory: Path = SCENARIO_DIR) -> list[Scenario]:
    return [Scenario.load(p) for p in sorted(directory.glob('*.yaml'))]


def run_scenario(scenario: Scenario, drivers: dict[str, Callable]) -> list[EndpointResult]:
    driver = drivers.get(scenario.driver)
    if driver is None:
        raise KeyError(f'No driver registered named {scenario.driver!r}')
    predictions = driver(scenario)
    results: list[EndpointResult] = []
    for ep in scenario.endpoints:
        pred = predictions.get(ep.name)
        if isinstance(pred, dict):
            results.append(ep.evaluate(pred.get('value'), pred.get('low'), pred.get('high')))
        else:
            results.append(ep.evaluate(pred))
    return results


def render_report(scenarios: list[tuple[Scenario, list[EndpointResult]]]) -> str:
    lines: list[str] = ['# NeuroTrace Validation Report', '']
    all_results = [r for _, rs in scenarios for r in rs]
    agg = aggregate(all_results)

    lines += [
        '## Aggregate', '',
        f'- Scenarios: {len(scenarios)}',
        f'- Endpoints: {agg["n_endpoints"]}  (judged {agg["n_judged"]}, '
        f'not run {agg["n_not_run"]})',
        f'- PASS: {agg["n_pass"]}   FAIL: {agg["n_fail"]}',
        f'- Median absolute percent error: {agg["median_absolute_percent_error"]:.1f}%',
        f'- Mean absolute percent error: {agg["mean_absolute_percent_error"]:.1f}%',
        f'- Max absolute percent error: {agg["max_absolute_percent_error"]:.1f}%',
        f'- Fraction within acceptance: {agg["fraction_within_acceptance"]:.2f}',
        '',
        'Failed and not-run endpoints are listed below alongside passes. '
        'Nothing is filtered from this report.',
        '',
    ]

    lines += ['## Endpoints', '',
              '| Scenario | Endpoint | Observed | Predicted | % error | Status |',
              '|---|---|---:|---:|---:|---|']
    for sc, rs in scenarios:
        for r in rs:
            obs = f'{r.observed:.4g}' if r.observed is not None else '-'
            pred = f'{r.predicted:.4g}' if r.predicted is not None else '-'
            pe = r.metrics.get('percent_error')
            pes = f'{pe:+.1f}%' if pe is not None else '-'
            lines.append(f'| {sc.key} | {r.name} | {obs} | {pred} | {pes} | **{r.status}** |')
    lines.append('')

    for sc, rs in scenarios:
        lines += [f'## {sc.title}', '',
                  f'*{sc.description.strip()}*', '',
                  f'- Validation type: **{sc.validation_type}**',
                  f'- Population: {sc.population}',
                  f'- Parameterised from: {", ".join(sc.parameterisation_sources) or "n/a"}',
                  f'- Validated against: {", ".join(sc.validation_sources) or "n/a"}',
                  f'- Evidence map: `{sc.evidence_file}`', '']
        for r in rs:
            lines += [f'### {r.name}  [{r.status}]', '',
                      f'- Acceptance: {r.acceptance}',
                      f'- Observed: {r.observed} {r.units}' if r.observed is not None
                      else '- Observed: not applicable',
                      f'- Predicted: {r.predicted} {r.units}' if r.predicted is not None
                      else '- Predicted: none produced',
                      f'- Verdict: {r.reason}']
            if r.metrics:
                lines.append('- Metrics: ' + ', '.join(
                    f'{k}={v:.4g}' for k, v in r.metrics.items()))
            if r.source_key:
                lines.append(f'- Source: {r.source_key}')
            lines.append('')
        if sc.limitations:
            lines += ['**Limitations**', '']
            lines += [f'- {l}' for l in sc.limitations]
            lines.append('')
    return '\n'.join(lines)
