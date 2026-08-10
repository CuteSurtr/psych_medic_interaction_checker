from __future__ import annotations
import importlib.util
import pathlib
import sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
PSYCH_SEED = ROOT / 'psychrx-guard' / 'backend' / 'database' / 'seed_data.py'
NEURO_SEED = ROOT / 'neurotrace' / 'backend' / 'database' / 'seed_data.py'

def load(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module
MECH_MAP = {'pharmacokinetic': 'PK', 'pharmacodynamic': 'PD', 'both': 'PK+PD'}
EVIDENCE_MAP = {'well-established': 'strong', 'probable': 'moderate', 'theoretical': 'moderate'}

def py_repr(v):
    if v is None:
        return 'None'
    if isinstance(v, str):
        return '"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"'
    if isinstance(v, bool):
        return 'True' if v else 'False'
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return '[' + ', '.join((py_repr(x) for x in v)) + ']'
    raise TypeError(type(v))

def main() -> None:
    out_path = pathlib.Path(__file__).with_name('ported_seed_additions.py')
    fh = out_path.open('w', encoding='utf-8', newline='\n')

    def emit(line: str='') -> None:
        fh.write(line + '\n')
    sys.path.insert(0, str(PSYCH_SEED.parent))
    sys.path.insert(0, str(NEURO_SEED.parent))
    psych_src = PSYCH_SEED.read_text(encoding='utf-8')
    neuro_src = NEURO_SEED.read_text(encoding='utf-8')
    psych_ns: dict = {}
    neuro_ns: dict = {}
    exec(compile(psych_src, str(PSYCH_SEED), 'exec'), psych_ns)
    exec(compile(neuro_src, str(NEURO_SEED), 'exec'), neuro_ns)
    psych_meds = psych_ns['MEDICATION_ROWS']
    psych_cyp = psych_ns['CYP_ROWS']
    psych_ix = psych_ns['INTERACTION_ROWS']
    neuro_meds = neuro_ns['MEDICATION_ROWS']
    neuro_cyp = neuro_ns['CYP_ROWS']
    neuro_ix = neuro_ns['INTERACTION_ROWS']
    neuro_med_names = {row[0].lower() for row in neuro_meds}
    neuro_cyp_keys = {(r[0].lower(), r[1], r[2]) for r in neuro_cyp}
    neuro_ix_keys = {tuple(sorted((r[0].lower(), r[1].lower()))) for r in neuro_ix}
    emit('# ===========================================================')
    emit('# PORTED FROM psychrx-guard/backend/database/seed_data.py')
    emit('# Attribute fields (class, half-life, risk flags, notes) are')
    emit('# filled in from psychrx-guard. PK fields (Vd, CL, ka, tmax,')
    emit('# protein_binding, CVs, therapeutic ranges, metabolite data)')
    emit('# are left as None — fill in per-drug from FDA labels as needed.')
    emit('# ===========================================================')
    emit()
    emit('PORTED_MEDICATION_ROWS = [')
    ported_med_count = 0
    for row in psych_meds:
        generic, brands, drug_class, sub_class, half_life, preg, qtc, ach, sero, cns, beers, dose_range, notes = row
        if generic.lower() in neuro_med_names:
            continue
        ported_med_count += 1
        out = (generic, brands, drug_class, sub_class, None, None, None, float(half_life) if half_life is not None else None, None, None, None, 30, 25, None, None, None, False, None, None, None, bool(qtc), int(ach) if ach is not None else 0, int(sero) if sero is not None else 0, int(cns) if cns is not None else 0, bool(beers), preg if isinstance(preg, str) else None, dose_range, None, None, None, notes)
        assert len(out) == 31
        emit('    (')
        emit('        ' + ', '.join((py_repr(v) for v in out[:4])) + ',')
        emit('        ' + ', '.join((py_repr(v) for v in out[4:11])) + ',')
        emit('        ' + ', '.join((py_repr(v) for v in out[11:13])) + ',')
        emit('        ' + ', '.join((py_repr(v) for v in out[13:16])) + ',')
        emit('        ' + ', '.join((py_repr(v) for v in out[16:20])) + ',')
        emit('        ' + ', '.join((py_repr(v) for v in out[20:24])) + ',')
        emit('        ' + ', '.join((py_repr(v) for v in out[24:26])) + ',')
        emit('        ' + ', '.join((py_repr(v) for v in out[26:30])) + ',')
        emit('        ' + py_repr(out[30]) + ',')
        emit('    ),')
    emit(']')
    emit()
    sys.stderr.write(f'# {ported_med_count} new medications\n')
    emit()
    emit('PORTED_CYP_ROWS = [')
    ported_cyp_count = 0
    for row in psych_cyp:
        name, enzyme, role, potency = row
        key = (name.lower(), enzyme, role)
        if key in neuro_cyp_keys:
            continue
        ported_cyp_count += 1
        out = (name, enzyme, role, potency, None, None, None, None)
        emit('    (' + ', '.join((py_repr(v) for v in out)) + '),')
    emit(']')
    sys.stderr.write(f'# {ported_cyp_count} new CYP profiles\n')
    emit()
    emit('PORTED_INTERACTION_ROWS = [')
    ported_ix_count = 0
    for row in psych_ix:
        a, b, sev, mech_raw, mech_detail, clin, rec, evid_raw = row
        if tuple(sorted((a.lower(), b.lower()))) in neuro_ix_keys:
            continue
        ported_ix_count += 1
        mech = MECH_MAP.get(mech_raw, mech_raw)
        evid = EVIDENCE_MAP.get(evid_raw, evid_raw)
        out = (a, b, sev, mech, mech_detail, clin, rec, evid)
        emit('    (')
        emit('        ' + ', '.join((py_repr(v) for v in out[:4])) + ',')
        emit('        ' + py_repr(out[4]) + ',')
        emit('        ' + py_repr(out[5]) + ',')
        emit('        ' + py_repr(out[6]) + ',')
        emit('        ' + py_repr(out[7]) + ',')
        emit('    ),')
    emit(']')
    sys.stderr.write(f'# {ported_ix_count} new interactions\n')
    fh.close()
    sys.stderr.write(f'wrote {out_path}\n')
if __name__ == '__main__':
    main()
