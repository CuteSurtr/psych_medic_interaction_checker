from __future__ import annotations
import numpy as np
import pytest
from services.receptor_occupancy import DrugOccupancyResult, ReceptorBinding, classify_occupancy, compute_receptor_occupancy, compute_regimen_occupancy, emax_response, fractional_occupancy, get_known_drugs, ng_ml_to_nm

class TestCoreMath:

    def test_occupancy_half_at_kd(self):
        assert fractional_occupancy(10.0, 10.0) == pytest.approx(0.5)

    def test_occupancy_saturates(self):
        assert fractional_occupancy(1000000000.0, 1.0) == pytest.approx(1.0, abs=1e-06)

    def test_occupancy_zero_at_zero(self):
        assert fractional_occupancy(0.0, 5.0) == pytest.approx(0.0)

    def test_occupancy_monotone(self):
        cs = np.linspace(0.0, 100.0, 101)
        occ = fractional_occupancy(cs, 5.0)
        assert np.all(np.diff(occ) >= -1e-12)

    def test_occupancy_clips_negative(self):
        assert fractional_occupancy(-0.1, 10.0) == pytest.approx(0.0)

class TestEmax:

    def test_emax_at_zero_returns_e0(self):
        assert emax_response(0.0, e0=5.0, e_max=10.0, ec50=1.0) == pytest.approx(5.0)

    def test_emax_saturates_to_e0_plus_emax(self):
        result = emax_response(1000000000.0, e0=2.0, e_max=20.0, ec50=1.0)
        assert result == pytest.approx(22.0, abs=1e-06)

    def test_emax_half_at_ec50(self):
        result = emax_response(1.0, e0=0.0, e_max=100.0, ec50=1.0)
        assert result == pytest.approx(50.0)

    def test_emax_hill_coefficient(self):
        c = np.array([0.5, 1.0, 2.0])
        gentle = emax_response(c, 0.0, 100.0, 1.0, gamma=1.0)
        steep = emax_response(c, 0.0, 100.0, 1.0, gamma=4.0)
        assert steep[0] < gentle[0]
        assert steep[2] > gentle[2]
        assert gentle[1] == pytest.approx(steep[1])

class TestUnitConversion:

    def test_ng_ml_to_nm_fluoxetine(self):
        out = ng_ml_to_nm(1.0, mw_g_per_mol=309.3)
        assert out == pytest.approx(1000.0 / 309.3, rel=1e-06)

    def test_array_conversion(self):
        arr = np.array([0.0, 10.0, 100.0])
        out = ng_ml_to_nm(arr, 250.0)
        assert out.shape == arr.shape
        np.testing.assert_allclose(out, arr * 4.0)

class TestClinicalThresholds:

    def test_ssri_at_therapeutic_plasma_hits_80pct(self):
        t = np.linspace(0.0, 24.0, 25)
        c = np.full_like(t, 200.0)
        result = compute_receptor_occupancy('fluoxetine', t, c, fraction_unbound=0.05)
        sert = next((tj for tj in result.trajectories if tj.target == 'SERT'))
        assert sert.peak_occupancy_pct > 80.0

    def test_haloperidol_d2_occupancy_in_therapeutic_range(self):
        t = np.linspace(0.0, 24.0, 25)
        c = np.full_like(t, 10.0)
        result = compute_receptor_occupancy('haloperidol', t, c, fraction_unbound=0.08)
        d2 = next((tj for tj in result.trajectories if tj.target == 'D2'))
        assert 30.0 < d2.peak_occupancy_pct < 95.0

    def test_classification_labels(self):
        assert classify_occupancy('SERT', 90.0) == 'therapeutic'
        assert classify_occupancy('SERT', 40.0) == 'subtherapeutic'
        assert classify_occupancy('D2', 70.0) == 'therapeutic'
        assert classify_occupancy('D2', 85.0) == 'EPS / side-effect risk'
        assert classify_occupancy('D2', 20.0) == 'subtherapeutic'

class TestTrajectoryShape:

    def test_result_contains_every_binding_target(self):
        t = np.linspace(0.0, 48.0, 49)
        c = np.linspace(0.0, 100.0, 49)
        result = compute_receptor_occupancy('aripiprazole', t, c)
        targets = {tj.target for tj in result.trajectories}
        assert {'D2', '5-HT2A', '5-HT1A'} <= targets

    def test_occupancy_pct_bounded(self):
        t = np.linspace(0.0, 48.0, 49)
        c = np.linspace(0.0, 1000.0, 49)
        result = compute_receptor_occupancy('fluoxetine', t, c)
        for tj in result.trajectories:
            assert np.all(tj.occupancy_pct >= 0.0)
            assert np.all(tj.occupancy_pct <= 100.0)

    def test_custom_bindings_override(self):
        t = np.linspace(0.0, 24.0, 25)
        c = np.full_like(t, 50.0)
        custom = [ReceptorBinding(target='XYZ', k_d_nm=1.0, mechanism='inhibitor')]
        result = compute_receptor_occupancy('unknown_drug', t, c, bindings=custom, mw_g_per_mol=300.0)
        assert len(result.trajectories) == 1
        assert result.trajectories[0].target == 'XYZ'

class TestRegimen:

    def test_regimen_runs_per_drug(self):
        t = np.linspace(0.0, 168.0, 169)
        concs = {'fluoxetine': 100.0 * (1 - np.exp(-t / 12.0)), 'aripiprazole': 50.0 * (1 - np.exp(-t / 24.0))}
        f_u = {'fluoxetine': 0.05, 'aripiprazole': 0.01}
        out = compute_regimen_occupancy(t, concs, f_u)
        assert set(out.keys()) == {'fluoxetine', 'aripiprazole'}
        assert all((isinstance(v, DrugOccupancyResult) for v in out.values()))

    def test_unknown_drug_returns_empty_profile(self):
        t = np.linspace(0.0, 24.0, 25)
        c = np.full_like(t, 10.0)
        result = compute_receptor_occupancy('totally_made_up', t, c)
        assert result.trajectories == []

    def test_known_drugs_list_populated(self):
        known = get_known_drugs()
        assert 'fluoxetine' in known
        assert 'aripiprazole' in known
        assert len(known) > 10
