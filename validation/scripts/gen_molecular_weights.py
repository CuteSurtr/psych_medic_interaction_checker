"""Regenerate backend/services/molecular_weights.py from PubChem.

    python validation/scripts/gen_molecular_weights.py            # rewrite
    python validation/scripts/gen_molecular_weights.py --verify   # check only

Molecular weight is a fixed chemical constant, so unlike an uncertain
pharmacokinetic parameter it should never be estimated. This script retrieves
every value from PubChem by name lookup and records the CID alongside it, so
any number in the generated module can be traced back and re-checked.

The module is generated rather than hand-edited because transcribing 114
numbers is exactly the step that introduces the errors this project keeps
finding. Edit this script, not the output.

Free-base (neutral) weights are used throughout. That is correct here because
plasma concentrations are reported as the active moiety rather than the
administered salt.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / 'backend'
OUT = BACKEND / 'services' / 'molecular_weights.py'

sys.path.insert(0, str(BACKEND))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PUBCHEM = ('https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{}'
           '/property/MolecularWeight,MolecularFormula/JSON')

# Not a single chemical species, or the PK-relevant species differs from what a
# name lookup returns. Resolved by hand with the reasoning recorded, not by API.
MANUAL: dict[str, dict] = {
    'lithium': {
        'cid': 3028194, 'mw': 6.94, 'formula': 'Li',
        'why': 'lithium ion, not lithium carbonate (73.89)',
    },
}

UNRESOLVABLE_NOTES: dict[str, str] = {
    'ethinyl estradiol with norethindrone':
        'combination product; the two components have different molecular '
        'weights and no single value is meaningful',
}


def medication_names() -> list[str]:
    from database.connection import SessionLocal
    from database.seed_db import create_tables, seed_if_empty
    from models import Medication
    create_tables()
    seed_if_empty()
    db = SessionLocal()
    try:
        return sorted({(m.generic_name or '').strip()
                       for m in db.query(Medication).all() if m.generic_name})
    finally:
        db.close()


def fetch(name: str) -> dict | None:
    try:
        with urllib.request.urlopen(
                PUBCHEM.format(urllib.parse.quote(name)), timeout=30) as r:
            props = json.load(r)['PropertyTable']['Properties'][0]
        return {'cid': props.get('CID'), 'mw': float(props['MolecularWeight']),
                'formula': props.get('MolecularFormula', '')}
    except (urllib.error.HTTPError, urllib.error.URLError, KeyError, ValueError):
        return None


def collect(names: list[str]) -> tuple[dict, list[str]]:
    resolved: dict[str, dict] = {}
    unresolved: list[str] = []
    for i, name in enumerate(names, 1):
        key = name.lower()
        if key in UNRESOLVABLE_NOTES:
            unresolved.append(key)
            print(f'{i:3}/{len(names)}  {name:<40} SKIPPED (not one species)')
            continue
        if key in MANUAL:
            resolved[key] = dict(MANUAL[key])
            print(f'{i:3}/{len(names)}  {name:<40} manual  {MANUAL[key]["mw"]:>8.2f}')
            continue
        rec = fetch(name)
        if rec is None:
            unresolved.append(key)
            print(f'{i:3}/{len(names)}  {name:<40} LOOKUP FAILED')
        else:
            resolved[key] = rec
            print(f'{i:3}/{len(names)}  {name:<40} CID {rec["cid"]:<10} '
                  f'{rec["mw"]:>8.2f}  {rec["formula"]}')
        time.sleep(0.22)  # PubChem permits 5 requests/second

    # Mixed amphetamine salts: the measured moiety is the amphetamine free base.
    # PubChem has no compound under that product name, so it resolves via
    # dextroamphetamine and is removed from the unresolved list.
    if 'amphetamine salts' in {n.lower() for n in names} and 'dextroamphetamine' in resolved:
        resolved['amphetamine salts'] = dict(resolved['dextroamphetamine'])
        if 'amphetamine salts' in unresolved:
            unresolved.remove('amphetamine salts')
    return resolved, unresolved


def render(resolved: dict, unresolved: list[str]) -> str:
    today = date.today().isoformat()
    parts = [f'''"""Molecular weights for every medication in the formulary.

Used to convert Ki and Km between uM and mg/L. Audit finding F-25: 79 of the
115 medications previously had no molecular weight and fell back to a guessed
350 g/mol, so their interaction magnitudes were computed against a number
nobody had checked.

Molecular weight is a fixed chemical constant rather than an uncertain
pharmacokinetic quantity, so unlike clearance or volume of distribution there
is no defensible reason to estimate it. Every value here is the free-base
(neutral) form retrieved from PubChem on {today}, recorded with its CID so it
can be re-checked. Free base rather than salt is correct because plasma
concentrations are reported as the active moiety.

GENERATED FILE. Edit validation/scripts/gen_molecular_weights.py and re-run it;
do not edit this module by hand.
"""
from __future__ import annotations

from services.provenance import Citation

PUBCHEM_RETRIEVED = {today!r}


''']
    for label, key, fmt in [('MOLECULAR_WEIGHTS: dict[str, float]', 'mw', repr),
                            ('PUBCHEM_CID: dict[str, int]', 'cid', repr),
                            ('MOLECULAR_FORMULA: dict[str, str]', 'formula', repr)]:
        parts.append(f'{label} = {{\n')
        for k in sorted(resolved):
            parts.append(f'    {k!r}: {fmt(resolved[k][key])},\n')
        parts.append('}\n\n')

    parts.append('# Entries that are not a single chemical species. Recorded rather than\n'
                 '# given a number, so the engine keeps flagging them instead of quietly\n'
                 '# using a value that does not mean anything.\n')
    parts.append('UNRESOLVABLE: dict[str, str] = {\n')
    for k in sorted(unresolved):
        parts.append(f'    {k!r}:\n        {UNRESOLVABLE_NOTES.get(k, "no single molecular weight")!r},\n')
    parts.append('}\n\n')

    parts.append('# Single weights that exist but need explaining.\n')
    parts.append('SPECIAL_CASES: dict[str, str] = {\n')
    parts.append("    'lithium':\n"
                 "        'value is the lithium ion (6.94), not lithium carbonate (73.89). '\n"
                 "        'Lithium is renally cleared with no CYP involvement, so this weight '\n"
                 "        'drives no Ki or Km conversion. Note separately that lithium is '\n"
                 "        'reported clinically in mmol/L, not ng/mL, which the engine does '\n"
                 "        'not currently handle.',\n")
    parts.append("    'amphetamine salts':\n"
                 "        'mixed amphetamine salts are dextroamphetamine and amphetamine as '\n"
                 "        'sulfate, saccharate and aspartate. The value is the amphetamine '\n"
                 "        'free base, the active moiety measured in plasma.',\n")
    parts.append('}\n\n')

    parts.append('''
def molecular_weight(generic_name: str) -> float | None:
    """Molecular weight in g/mol, or None if not resolvable.

    Returning None is deliberate: callers must record a substitution rather
    than silently receive a default.
    """
    return MOLECULAR_WEIGHTS.get((generic_name or '').strip().lower())


def pubchem_citation(generic_name: str) -> Citation | None:
    """Traceable source for a molecular weight."""
    key = (generic_name or '').strip().lower()
    cid = PUBCHEM_CID.get(key)
    if cid is None:
        return None
    return Citation(
        source_db='PubChem CID', accession=str(cid),
        source_url=f'https://pubchem.ncbi.nlm.nih.gov/compound/{cid}',
        title=f'{key} ({MOLECULAR_FORMULA.get(key, "")})',
        verified=True,
    )
''')
    return ''.join(parts)


def main() -> int:
    verify_only = '--verify' in sys.argv
    names = medication_names()
    print(f'{len(names)} medications in the seeded formulary\n')
    resolved, unresolved = collect(names)

    print(f'\nresolved   : {len(resolved)}')
    print(f'unresolved : {len(unresolved)}  {unresolved}')

    if verify_only:
        from services.molecular_weights import MOLECULAR_WEIGHTS
        drift = [(k, MOLECULAR_WEIGHTS.get(k), v['mw']) for k, v in resolved.items()
                 if k in MOLECULAR_WEIGHTS
                 and abs(MOLECULAR_WEIGHTS[k] - v['mw']) / v['mw'] > 0.01]
        missing = sorted(set(resolved) - set(MOLECULAR_WEIGHTS))
        for k, stored, live in drift:
            print(f'  DRIFT   {k}: stored {stored} vs PubChem {live}')
        for k in missing:
            print(f'  MISSING {k} is absent from the generated module')
        print(f'\ndrift: {len(drift)}  missing: {len(missing)}')
        return 1 if (drift or missing) else 0

    # A transient network failure must not silently delete entries. PubChem
    # lookups fail intermittently, and a rewrite that drops a drug would remove
    # a sourced value and quietly restore the guessed default in its place.
    try:
        from services.molecular_weights import MOLECULAR_WEIGHTS as existing
    except ImportError:
        existing = {}
    lost = sorted(set(existing) - set(resolved))
    if lost:
        print(f'\nREFUSING TO WRITE: this run resolved fewer entries than the '
              f'existing module.\nWould lose {len(lost)}: {lost}\n'
              f'Most likely a transient PubChem failure. Re-run before writing.')
        return 1

    OUT.write_text(render(resolved, unresolved), encoding='utf-8')
    print(f'\nwrote {OUT.relative_to(REPO)}  ({len(resolved)} entries)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
