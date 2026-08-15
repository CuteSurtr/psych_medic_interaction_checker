"""Run the validation suite and write a report.

    python validation/scripts/run_validation.py

Exit code is non-zero if any endpoint FAILs, so this can gate CI. Failures stay
in the report rather than being filtered out.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from drivers import DRIVERS  # noqa: E402
from framework import REPORT_DIR, load_all, render_report, run_scenario  # noqa: E402


def main() -> int:
    scenarios = load_all()
    if not scenarios:
        print('No validation scenarios found.')
        return 1

    collected = []
    for sc in scenarios:
        print(f'Running {sc.key} ...', flush=True)
        results = run_scenario(sc, DRIVERS)
        collected.append((sc, results))
        for r in results:
            print(f'  [{r.status:8}] {r.name}: {r.reason}')

    report = render_report(collected)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / 'validation_report.md'
    out.write_text(report, encoding='utf-8')
    print(f'\nReport written to {out}')

    failures = [r for _, rs in collected for r in rs if r.status == 'FAIL']
    print(f'{len(failures)} endpoint(s) failed.')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
