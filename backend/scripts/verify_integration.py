from __future__ import annotations
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

def _patch_array_for_sqlite() -> None:
    import sqlalchemy
    from sqlalchemy import JSON

    def array_shim(*args, **kwargs):
        return JSON()
    sqlalchemy.ARRAY = array_shim
    original_func_getattr = type(sqlalchemy.func).__getattr__

    def func_getattr(self, name: str):
        if name == 'array_to_string':

            def _stub(_col, _sep, _default=''):
                return sqlalchemy.literal('')
            return _stub
        return original_func_getattr(self, name)
    type(sqlalchemy.func).__getattr__ = func_getattr

def _setup_env() -> Path:
    tmp = Path(tempfile.gettempdir()) / 'neurotrace_verify.sqlite'
    if tmp.exists():
        tmp.unlink()
    os.environ['DATABASE_URL'] = f'sqlite:///{tmp.as_posix()}'
    backend = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend))
    return tmp

def _summary(ok: list, fail: list) -> int:
    print('\n' + '=' * 70)
    print(f'PASSED: {len(ok)}')
    for name in ok:
        print(f'  OK  {name}')
    print(f'\nFAILED: {len(fail)}')
    for name, err in fail:
        print(f'  XX  {name}: {err}')
    print('=' * 70)
    return 0 if not fail else 1

def main() -> int:
    _setup_env()
    _patch_array_for_sqlite()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    from fastapi.testclient import TestClient
    from main import app
    ok: list[str] = []
    fail: list[tuple[str, str]] = []

    def run(name: str, fn):
        try:
            fn()
            ok.append(name)
            print(f'  OK  {name}')
        except Exception as e:
            tb = traceback.format_exc(limit=4)
            fail.append((name, f'{e}\n{tb}'))
            print(f'  XX  {name}: {e}')
    print('Booting app (create_tables + seed_if_empty)…')
    with TestClient(app) as client:

        def health():
            r = client.get('/health')
            assert r.status_code == 200, r.text
            assert r.json() == {'status': 'ok'}

        def medication_catalog():
            from database.connection import SessionLocal
            from models import Medication
            db = SessionLocal()
            try:
                total = db.query(Medication).count()
                assert total >= 100, f'expected >=100 meds after seed, got {total}'
                names = {m.generic_name.lower() for m in db.query(Medication).all()}
            finally:
                db.close()
            for ported in ['phenelzine', 'vortioxetine', 'atomoxetine', 'modafinil', 'triazolam', 'pimozide']:
                assert ported in names, f"ported drug '{ported}' missing after seed"

        def medication_detail():
            from database.connection import SessionLocal
            from models import Medication
            db = SessionLocal()
            try:
                m = db.query(Medication).filter(Medication.generic_name == 'fluoxetine').first()
            finally:
                db.close()
            assert m is not None, 'fluoxetine missing from seed'
            r2 = client.get(f'/api/medications/{m.id}')
            assert r2.status_code == 200, r2.text
            d = r2.json()
            assert d['generic_name'] == 'fluoxetine'
            assert d['has_active_metabolite'] is True
            assert any((e['enzyme'] == 'CYP2D6' for e in d.get('cyp450', [])))
        run('GET /health', health)
        run('GET /api/medications/search (catalog has ported meds)', medication_catalog)
        run('GET /api/medications/{id} (fluoxetine detail + CYP profile)', medication_detail)

        def id_of(name: str) -> int:
            from database.connection import SessionLocal
            from models import Medication
            db = SessionLocal()
            try:
                m = db.query(Medication).filter(Medication.generic_name == name).first()
            finally:
                db.close()
            assert m is not None, f'{name} missing from seed'
            return int(m.id)
        ids: dict[str, int] = {}
        for n in ['fluoxetine', 'aripiprazole', 'phenelzine', 'venlafaxine', 'haloperidol', 'lithium']:
            try:
                ids[n] = id_of(n)
            except Exception as e:
                fail.append((f'lookup {n}', str(e)))

        def interaction_fluox_ari():
            r = client.post('/api/interactions/check', json={'medication_ids': [ids['fluoxetine'], ids['aripiprazole']]})
            assert r.status_code == 200, r.text
            body = r.json()
            assert 'interactions' in body
            found = [ix for ix in body['interactions'] if {ix['drug_a_name'], ix['drug_b_name']} == {'fluoxetine', 'aripiprazole'}]
            assert found, f"expected fluoxetine-aripiprazole interaction; got {body['interactions'][:2]}"

        def interaction_ported_maoi():
            r = client.post('/api/interactions/check', json={'medication_ids': [ids['phenelzine'], ids['venlafaxine']]})
            assert r.status_code == 200
            body = r.json()
            critical = [ix for ix in body['interactions'] if ix['severity'] == 'critical']
            assert critical, f"expected ported MAOI+SNRI critical interaction, got {body['interactions'][:3]}"
        run('POST /api/interactions/check (fluoxetine + aripiprazole)', interaction_fluox_ari)
        run('POST /api/interactions/check (phenelzine + venlafaxine — ported)', interaction_ported_maoi)

        def risk_summary():
            r = client.post('/api/risk-summary', json={'medication_ids': [ids['fluoxetine'], ids['phenelzine']]})
            assert r.status_code == 200, r.text
            s = r.json()
            assert s['serotonin_risk'] in ('Critical', 'High'), s
        run('POST /api/risk-summary (fluoxetine + phenelzine → serotonin risk)', risk_summary)
        ids_csv = ','.join((str(ids[n]) for n in ['fluoxetine', 'aripiprazole', 'haloperidol']))

        def graph_metrics():
            r = client.get(f'/api/analysis/graph-metrics?medication_ids={ids_csv}')
            assert r.status_code == 200, r.text
            body = r.json()
            assert 'fiedler_value' in body

        def topology():
            r = client.get(f'/api/advanced/topology?medication_ids={ids_csv}')
            assert r.status_code == 200, r.text
            assert 'betti_0' in r.json()

        def entropy():
            r = client.get(f'/api/advanced/entropy?medication_ids={ids_csv}')
            assert r.status_code == 200
            assert 'cdi' in r.json()

        def game_theory():
            r = client.post('/api/advanced/game-theory', json={'medication_ids': [ids['fluoxetine'], ids['aripiprazole']]})
            assert r.status_code == 200
            assert 'price_of_anarchy' in r.json()
        run('GET /api/analysis/graph-metrics', graph_metrics)
        run('GET /api/advanced/topology', topology)
        run('GET /api/advanced/entropy', entropy)
        run('POST /api/advanced/game-theory', game_theory)

        def simulation():
            create = client.post('/api/simulation/create', json={'patient_weight_kg': 70, 'horizon_days': 28, 'cyp2d6_phenotype': 'normal', 'cyp2c19_phenotype': 'normal', 'dose_schedules': [{'medication_id': ids['fluoxetine'], 'event_type': 'start', 'event_day': 0, 'dose_mg': 40.0, 'frequency': 'daily'}]})
            assert create.status_code == 200, create.text
            sim_id = create.json()['simulation_id']
            run_resp = client.get(f'/api/simulation/{sim_id}/run')
            assert run_resp.status_code == 200, run_resp.text
            body = run_resp.json()
            assert 'fluoxetine' in body['concentrations']
            assert len(body['time_hours']) > 100, 'expected multi-day time grid'
            peak = max(body['concentrations']['fluoxetine'])
            assert peak > 0, 'fluoxetine never rose above zero'
            return sim_id
        sim_id = None
        try:
            sim_id = simulation()
            ok.append('POST /api/simulation/create + GET /run (fluoxetine)')
            print('  OK  POST /api/simulation/create + GET /run (fluoxetine)')
        except Exception as e:
            fail.append(('POST /api/simulation/create + GET /run', f'{e}\n{traceback.format_exc(limit=3)}'))
            print(f'  XX  simulation: {e}')
        if sim_id is not None:

            def tissue_pde():
                r = client.post('/api/advanced/tissue-pde', json={'simulation_id': sim_id})
                assert r.status_code == 200, r.text
                body = r.json()
                assert 'fluoxetine' in body['per_drug']
                per = body['per_drug']['fluoxetine']
                assert len(per['surface_ng_ml']) == len(body['time_hours'])
                assert max(per['surface_ng_ml']) > 0

            def occupancy():
                r = client.post('/api/advanced/receptor-occupancy', json={'simulation_id': sim_id, 'use_f_unbound': True})
                assert r.status_code == 200, r.text
                body = r.json()
                assert 'fluoxetine' in body['per_drug']
                traj = body['per_drug']['fluoxetine']['trajectories']
                sert = next((t for t in traj if t['target'] == 'SERT'))
                assert sert['peak_occupancy_pct'] > 0

            def hepatic():
                r = client.post('/api/advanced/hepatic-extraction', json={'medication_ids': [ids['fluoxetine'], ids['aripiprazole']], 'simulation_id': sim_id})
                assert r.status_code == 200, r.text
                body = r.json()
                assert body['per_drug'], f'empty response: {body}'
                for drug, d in body['per_drug'].items():
                    assert 0.0 <= d['extraction_ratio'] <= 1.0
                    assert 0.0 <= d['first_pass_fraction'] <= 1.0

            def bayesian():
                r = client.post('/api/advanced/bayesian-pk', json={'observations': [{'time_h': 4.0, 'concentration_ng_ml': 100.0}, {'time_h': 12.0, 'concentration_ng_ml': 60.0}, {'time_h': 24.0, 'concentration_ng_ml': 25.0}], 'doses': [{'time_h': 0.0, 'dose_mg': 100.0}], 'mu_log_cl': 1.609, 'sigma_log_cl': 0.3, 'mu_log_vd': 3.912, 'sigma_log_vd': 0.3, 'ka_per_h': 1.0, 'bioavailability': 0.8, 'sigma_obs': 0.2})
                assert r.status_code == 200, r.text
                body = r.json()
                assert body['map_cl_l_per_h'] > 0
                assert body['ci95_cl_l_per_h'][0] < body['map_cl_l_per_h'] < body['ci95_cl_l_per_h'][1]
            run('POST /api/advanced/tissue-pde', tissue_pde)
            run('POST /api/advanced/receptor-occupancy', occupancy)
            run('POST /api/advanced/hepatic-extraction', hepatic)
            run('POST /api/advanced/bayesian-pk', bayesian)

        def sde():
            r = client.post('/api/advanced/simulation/stochastic', json={'drugs': [{'name': 'fluoxetine', 'ka': 0.8, 'vd': 2500, 'cl': 25, 'F': 0.72, 'sigma': 0.1}], 'dose_schedules': {'fluoxetine': [[0.0, 20.0]]}, 'duration_days': 7, 'n_paths': 20})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body['n_paths'] > 0

        def markov():
            r = client.post('/api/advanced/markov', json={'drug_classes': ['SSRI'], 'initial_state': 'Partial Response', 'n_weeks': 12})
            assert r.status_code == 200, r.text
            body = r.json()
            assert 'stationary_distribution' in body

        def taper():
            r = client.post('/api/advanced/optimizer/taper', json={'drug_name': 'fluoxetine', 'start_dose': 40.0, 'target_dose': 0.0, 'duration_days': 28})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body['steps']
        run('POST /api/advanced/simulation/stochastic', sde)
        run('POST /api/advanced/markov', markov)
        run('POST /api/advanced/optimizer/taper', taper)
    return _summary(ok, fail)
if __name__ == '__main__':
    sys.exit(main())
