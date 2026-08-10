from __future__ import annotations
import math
import numpy as np
import pytest
from services.dose_scheduler import MedicationSchedule
from services.pk_simulator import DrugConfig, SimulationConfig, run_simulation

def _one_comp_drug() -> DrugConfig:
    return DrugConfig(index=0, generic_name='test_1c', ka=1.0, bioavailability=1.0, vd_l=50.0, clearance_l_per_h=5.0, renal_clearance_fraction=1.0, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None)

def _two_comp_drug(k12: float=0.3, k21: float=0.1, peripheral_vd_l: float=100.0) -> DrugConfig:
    return DrugConfig(index=0, generic_name='test_2c', ka=1.0, bioavailability=1.0, vd_l=50.0, clearance_l_per_h=5.0, renal_clearance_fraction=1.0, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None, peripheral_vd_l=peripheral_vd_l, k12_per_h=k12, k21_per_h=k21)

def _schedule(name: str, dose_mg: float=100.0) -> MedicationSchedule:
    return MedicationSchedule(medication_index=0, generic_name=name, bioavailability=1.0, events=[{'event_type': 'start', 'day': 0, 'dose_mg': dose_mg, 'frequency': 'daily'}])

class TestOneCompartmentBackwardCompat:

    def test_no_peripheral_output_for_1c_drug(self):
        drug = _one_comp_drug()
        sched = _schedule(drug.generic_name)
        config = SimulationConfig(drugs=[drug], schedules=[sched], horizon_days=3)
        result = run_simulation(config)
        assert drug.generic_name not in result.peripheral_concentrations

    def test_is_two_compartment_flag(self):
        assert _one_comp_drug().is_two_compartment is False
        assert _two_comp_drug().is_two_compartment is True
        partial = DrugConfig(index=0, generic_name='p', ka=1.0, bioavailability=1.0, vd_l=50.0, clearance_l_per_h=5.0, renal_clearance_fraction=1.0, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None, peripheral_vd_l=100.0)
        assert partial.is_two_compartment is False

class TestTwoCompartmentBehavior:

    def test_peripheral_compartment_populates(self):
        drug = _two_comp_drug()
        sched = _schedule(drug.generic_name)
        config = SimulationConfig(drugs=[drug], schedules=[sched], horizon_days=7)
        result = run_simulation(config)
        assert drug.generic_name in result.peripheral_concentrations
        periph = result.peripheral_concentrations[drug.generic_name]
        assert periph[0] == pytest.approx(0.0, abs=1e-09)
        assert periph[len(periph) // 2] > 0.0

    def test_distribution_phase_slows_central_decline(self):
        d1 = _one_comp_drug()
        d2 = _two_comp_drug(k12=0.5, k21=0.08, peripheral_vd_l=200.0)
        s1 = _schedule(d1.generic_name)
        s2 = _schedule(d2.generic_name)
        c1 = run_simulation(SimulationConfig(drugs=[d1], schedules=[s1], horizon_days=14))
        c2 = run_simulation(SimulationConfig(drugs=[d2], schedules=[s2], horizon_days=14))
        conc1 = c1.concentrations['test_1c']
        conc2 = c2.concentrations['test_2c']
        p1 = conc1 / conc1.max()
        p2 = conc2 / conc2.max()
        late_mask = c1.time_hours >= 120.0
        if np.any(late_mask):
            assert p2[late_mask].mean() > p1[late_mask].mean()

    def test_mass_balance_never_exceeds_dose(self):
        drug = DrugConfig(index=0, generic_name='conservative', ka=1.0, bioavailability=1.0, vd_l=40.0, clearance_l_per_h=0.0, renal_clearance_fraction=0.0, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None, peripheral_vd_l=80.0, k12_per_h=0.4, k21_per_h=0.15)
        sched = _schedule(drug.generic_name, dose_mg=50.0)
        result = run_simulation(SimulationConfig(drugs=[drug], schedules=[sched], horizon_days=4))
        central = result.concentrations[drug.generic_name] / 1000.0 * drug.vd_l
        periph = result.peripheral_concentrations[drug.generic_name] / 1000.0 * drug.peripheral_vd_l
        total_in_body = central + periph
        total_dose = sum((e['dose_mg'] for e in result.dose_events))
        assert total_in_body.max() <= total_dose + 0.5

    def test_k12_k21_ratio_sets_distribution_volume(self):
        k12, k21 = (0.4, 0.1)
        drug = DrugConfig(index=0, generic_name='ratio', ka=5.0, bioavailability=1.0, vd_l=10.0, clearance_l_per_h=0.0, renal_clearance_fraction=0.0, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None, peripheral_vd_l=10.0, k12_per_h=k12, k21_per_h=k21)
        sched = _schedule(drug.generic_name, dose_mg=10.0)
        result = run_simulation(SimulationConfig(drugs=[drug], schedules=[sched], horizon_days=14))
        central_mg = result.concentrations[drug.generic_name][-1] / 1000.0 * drug.vd_l
        periph_mg = result.peripheral_concentrations[drug.generic_name][-1] / 1000.0 * drug.peripheral_vd_l
        assert math.isclose(periph_mg / central_mg, k12 / k21, rel_tol=0.05)

class TestStateSize:

    def test_mixed_regimen_1c_and_2c(self):
        d1 = _one_comp_drug()
        d2 = DrugConfig(index=1, generic_name='test_2c', ka=1.0, bioavailability=1.0, vd_l=40.0, clearance_l_per_h=3.0, renal_clearance_fraction=1.0, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None, peripheral_vd_l=60.0, k12_per_h=0.2, k21_per_h=0.1)
        s1 = _schedule('test_1c', dose_mg=100.0)
        s2 = MedicationSchedule(medication_index=1, generic_name='test_2c', bioavailability=1.0, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 80.0, 'frequency': 'daily'}])
        result = run_simulation(SimulationConfig(drugs=[d1, d2], schedules=[s1, s2], horizon_days=5))
        assert 'test_1c' not in result.peripheral_concentrations
        assert 'test_2c' in result.peripheral_concentrations
        assert 'test_1c' in result.concentrations
        assert 'test_2c' in result.concentrations
