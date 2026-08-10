import numpy as np
import pytest
from services.dose_scheduler import MedicationSchedule
from services.enzyme_kinetics import CYP_KDEG, EnzymeParams, InhibitorParams, MBIParams, InductionParams, competitive_inhibition_rate, enzyme_activity_factor, enzyme_pool_derivative, michaelis_menten_rate
from services.metabolite_tracker import MetaboliteParams
from services.pk_simulator import DrugConfig, SimulationConfig, run_simulation

def test_michaelis_menten_rate():
    vmax, km, c = (12.0, 4.0, 6.0)
    expected = vmax * c / (km + c)
    assert michaelis_menten_rate(c, vmax, km) == pytest.approx(expected)

def test_competitive_inhibition_reduces_rate():
    c_sub, vmax, km = (15.0, 40.0, 10.0)
    base = michaelis_menten_rate(c_sub, vmax, km)
    reduced = competitive_inhibition_rate(c_sub, vmax, km, inhibitor_concentrations=[20.0], ki_values=[10.0])
    assert reduced < base
    apparent_km = km * (1.0 + 20.0 / 10.0)
    assert reduced == pytest.approx(vmax * c_sub / (apparent_km + c_sub))

def test_dose_scheduler_daily():
    sched = MedicationSchedule(medication_index=0, generic_name='x', bioavailability=1.0, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 10, 'frequency': 'daily'}])
    events = sched.generate_dose_events(horizon_days=7)
    assert len(events) == 7

def test_dose_scheduler_bid():
    sched = MedicationSchedule(medication_index=0, generic_name='x', bioavailability=1.0, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 10, 'frequency': 'BID'}])
    events = sched.generate_dose_events(horizon_days=7)
    assert len(events) == 14

def test_dose_scheduler_stop():
    sched = MedicationSchedule(medication_index=0, generic_name='x', bioavailability=1.0, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 10, 'frequency': 'daily'}, {'event_type': 'stop', 'day': 3}])
    events = sched.generate_dose_events(horizon_days=7)
    assert len(events) == 3
    assert {e.time_h for e in events} == {0.0, 24.0, 48.0}

def test_dose_scheduler_dose_change():
    sched = MedicationSchedule(medication_index=0, generic_name='x', bioavailability=1.0, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 100, 'frequency': 'daily'}, {'event_type': 'dose_change', 'day': 2, 'dose_mg': 50, 'frequency': 'daily'}])
    events = sched.generate_dose_events(horizon_days=7)
    assert all((e.dose_mg == 100 for e in events if e.time_h < 48.0))
    assert all((e.dose_mg == 50 for e in events if e.time_h >= 48.0))

def test_single_drug_simulation():
    config = SimulationConfig(drugs=[DrugConfig(index=0, generic_name='test_drug', ka=0.5, bioavailability=0.8, vd_l=100.0, clearance_l_per_h=5.0, renal_clearance_fraction=0.2, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None)], schedules=[MedicationSchedule(medication_index=0, generic_name='test_drug', bioavailability=0.8, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 100, 'frequency': 'daily'}])], horizon_days=14)
    result = run_simulation(config)
    assert len(result.time_hours) > 0
    assert 'test_drug' in result.concentrations
    conc = result.concentrations['test_drug']
    assert float(np.max(conc)) > 0.0
    tail = conc[-min(48, len(conc)):]
    assert tail.size > 4
    rel_spread = float(np.std(tail) / (np.mean(tail) + 1e-12))
    assert rel_spread < 0.35

def test_enzyme_activity_factor():
    assert enzyme_activity_factor([], []) == pytest.approx(1.0)
    assert enzyme_activity_factor([100.0], [50.0]) < 1.0

def _fluoxetine_config(include_metabolite: bool=False) -> DrugConfig:
    ki_mg_l = 70.0 * 309.3 / 1000000.0
    met = None
    if include_metabolite:
        met = MetaboliteParams(parent_drug_index=0, metabolite_name='norfluoxetine', formation_fraction=0.8, ke_metabolite=0.693 / 240.0, vd_metabolite_l=2500.0, is_enzyme_inhibitor=True, inhibited_enzyme='CYP2D6', ki_nm=ki_mg_l)
    return DrugConfig(index=0, generic_name='fluoxetine', ka=0.8, bioavailability=0.72, vd_l=2500.0, clearance_l_per_h=25.0, renal_clearance_fraction=0.0, enzyme_substrates=[], enzyme_inhibitions=[InhibitorParams(enzyme_name='CYP2D6', ki=ki_mg_l, drug_index=0)], metabolite=met)

def _aripiprazole_config(index: int=1) -> DrugConfig:
    cl = 46.0
    km_2d6 = 2000.0 * 448.4 / 1000000.0
    km_3a4 = 8000.0 * 448.4 / 1000000.0
    return DrugConfig(index=index, generic_name='aripiprazole', ka=0.3, bioavailability=0.87, vd_l=4900.0, clearance_l_per_h=cl, renal_clearance_fraction=0.0, enzyme_substrates=[EnzymeParams(enzyme_name='CYP2D6', vmax=cl * km_2d6, km=km_2d6, fraction_metabolized=0.35), EnzymeParams(enzyme_name='CYP3A4', vmax=cl * km_3a4, km=km_3a4, fraction_metabolized=0.65)], enzyme_inhibitions=[], metabolite=None)

def _clozapine_config(index: int=0) -> DrugConfig:
    cl = 40.0
    mw = 326.8
    km_1a2 = 5000.0 * mw / 1000000.0
    km_3a4 = 10000.0 * mw / 1000000.0
    km_2d6 = 7000.0 * mw / 1000000.0
    return DrugConfig(index=index, generic_name='clozapine', ka=0.6, bioavailability=0.5, vd_l=700.0, clearance_l_per_h=cl, renal_clearance_fraction=0.05, enzyme_substrates=[EnzymeParams(enzyme_name='CYP1A2', vmax=cl * km_1a2, km=km_1a2, fraction_metabolized=0.7), EnzymeParams(enzyme_name='CYP3A4', vmax=cl * km_3a4, km=km_3a4, fraction_metabolized=0.15), EnzymeParams(enzyme_name='CYP2D6', vmax=cl * km_2d6, km=km_2d6, fraction_metabolized=0.1)], enzyme_inhibitions=[], metabolite=None)

class TestSingleDrugSteadyState:

    def test_concentration_starts_zero_and_increases(self):
        drug = DrugConfig(index=0, generic_name='fluoxetine_simple', ka=0.8, bioavailability=0.72, vd_l=2500.0, clearance_l_per_h=25.0, renal_clearance_fraction=0.6, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None)
        config = SimulationConfig(drugs=[drug], schedules=[MedicationSchedule(medication_index=0, generic_name='fluoxetine_simple', bioavailability=0.72, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 20, 'frequency': 'daily'}])], horizon_days=42)
        result = run_simulation(config)
        conc = result.concentrations['fluoxetine_simple']
        assert conc[0] == pytest.approx(0.0, abs=0.1)
        assert float(np.max(conc)) > 0.0

    def test_concentration_plateaus(self):
        drug = DrugConfig(index=0, generic_name='fluoxetine_simple', ka=0.8, bioavailability=0.72, vd_l=2500.0, clearance_l_per_h=25.0, renal_clearance_fraction=0.6, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None)
        config = SimulationConfig(drugs=[drug], schedules=[MedicationSchedule(medication_index=0, generic_name='fluoxetine_simple', bioavailability=0.72, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 20, 'frequency': 'daily'}])], horizon_days=56)
        result = run_simulation(config)
        conc = result.concentrations['fluoxetine_simple']
        t = result.time_hours
        week4_mask = (t >= 21 * 24) & (t <= 28 * 24)
        week8_mask = (t >= 49 * 24) & (t <= 56 * 24)
        if np.any(week4_mask) and np.any(week8_mask):
            mean_w4 = float(np.mean(conc[week4_mask]))
            mean_w8 = float(np.mean(conc[week8_mask]))
            if mean_w4 > 0:
                ratio = mean_w8 / mean_w4
                assert ratio < 1.3, f'Concentration still rising significantly: week8/week4 = {ratio:.2f}'

class TestInhibitionEffect:

    def test_aripiprazole_auc_increases_with_fluoxetine(self):
        arip_alone = _aripiprazole_config(index=0)
        config_alone = SimulationConfig(drugs=[arip_alone], schedules=[MedicationSchedule(medication_index=0, generic_name='aripiprazole', bioavailability=0.87, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 10, 'frequency': 'daily'}])], horizon_days=42)
        result_alone = run_simulation(config_alone)
        conc_alone = result_alone.concentrations['aripiprazole']
        t = result_alone.time_hours
        ss_mask = t >= 35 * 24
        auc_alone = float(np.trapezoid(conc_alone[ss_mask], t[ss_mask]))
        flx = _fluoxetine_config(include_metabolite=False)
        arip_with = _aripiprazole_config(index=1)
        config_with = SimulationConfig(drugs=[flx, arip_with], schedules=[MedicationSchedule(medication_index=0, generic_name='fluoxetine', bioavailability=0.72, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 40, 'frequency': 'daily'}]), MedicationSchedule(medication_index=1, generic_name='aripiprazole', bioavailability=0.87, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 10, 'frequency': 'daily'}])], horizon_days=42)
        result_with = run_simulation(config_with)
        conc_with = result_with.concentrations['aripiprazole']
        t2 = result_with.time_hours
        ss_mask2 = t2 >= 35 * 24
        auc_with = float(np.trapezoid(conc_with[ss_mask2], t2[ss_mask2]))
        ratio = auc_with / (auc_alone + 1e-12)
        assert ratio >= 1.3, f'Aripiprazole AUC with fluoxetine should be at least 1.3x higher, got {ratio:.2f}x'

class TestDrugDiscontinuationWashout:

    def test_fluoxetine_decays_after_stop(self):
        drug = DrugConfig(index=0, generic_name='fluoxetine_washout', ka=0.8, bioavailability=0.72, vd_l=2500.0, clearance_l_per_h=25.0, renal_clearance_fraction=0.6, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None)
        config = SimulationConfig(drugs=[drug], schedules=[MedicationSchedule(medication_index=0, generic_name='fluoxetine_washout', bioavailability=0.72, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 20, 'frequency': 'daily'}, {'event_type': 'stop', 'day': 14}])], horizon_days=42)
        result = run_simulation(config)
        conc = result.concentrations['fluoxetine_washout']
        t = result.time_hours
        ss_mask = (t >= 12 * 24) & (t <= 14 * 24)
        post_mask = (t >= 28 * 24) & (t <= 35 * 24)
        if np.any(ss_mask) and np.any(post_mask):
            peak_at_stop = float(np.max(conc[ss_mask]))
            level_post = float(np.mean(conc[post_mask]))
            if peak_at_stop > 0:
                decay_ratio = level_post / peak_at_stop
                assert decay_ratio < 0.5, f'Fluoxetine should decay to <50% by 2 weeks after stop, got {decay_ratio:.2f}'

    def test_norfluoxetine_persists_longer_than_parent(self):
        drug = _fluoxetine_config(include_metabolite=True)
        config = SimulationConfig(drugs=[drug], schedules=[MedicationSchedule(medication_index=0, generic_name='fluoxetine', bioavailability=0.72, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 40, 'frequency': 'daily'}, {'event_type': 'stop', 'day': 28}])], horizon_days=56)
        result = run_simulation(config)
        assert 'norfluoxetine' in result.metabolite_concentrations
        met_conc = result.metabolite_concentrations['norfluoxetine']
        parent_conc = result.concentrations['fluoxetine']
        t = result.time_hours
        day42_mask = (t >= 42 * 24) & (t <= 43 * 24)
        if np.any(day42_mask):
            parent_at_42 = float(np.mean(parent_conc[day42_mask]))
            met_at_42 = float(np.mean(met_conc[day42_mask]))
            assert met_at_42 > parent_at_42, 'Norfluoxetine should persist longer than fluoxetine after discontinuation'

class TestSmokingCessationClozapine:

    def test_clozapine_levels_rise_after_smoking_cessation(self):
        drug = _clozapine_config()
        config_smoking = SimulationConfig(drugs=[drug], schedules=[MedicationSchedule(medication_index=0, generic_name='clozapine', bioavailability=0.5, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 200, 'frequency': 'BID'}])], horizon_days=42, smoking=True)
        result_smoking = run_simulation(config_smoking)
        conc_s = result_smoking.concentrations['clozapine']
        t_s = result_smoking.time_hours
        ss_mask_s = t_s >= 35 * 24
        css_smoking = float(np.mean(conc_s[ss_mask_s]))
        config_nonsmoking = SimulationConfig(drugs=[drug], schedules=[MedicationSchedule(medication_index=0, generic_name='clozapine', bioavailability=0.5, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 200, 'frequency': 'BID'}])], horizon_days=42, smoking=False)
        result_nonsmoking = run_simulation(config_nonsmoking)
        conc_ns = result_nonsmoking.concentrations['clozapine']
        t_ns = result_nonsmoking.time_hours
        ss_mask_ns = t_ns >= 35 * 24
        css_nonsmoking = float(np.mean(conc_ns[ss_mask_ns]))
        ratio = css_nonsmoking / (css_smoking + 1e-12)
        assert ratio >= 1.2, f'Clozapine Css after smoking cessation should be >= 1.2x Css while smoking, got {ratio:.2f}x'

class TestEnzymePoolDerivative:

    def test_steady_state_without_perturbation(self):
        k_deg = CYP_KDEG['CYP2D6']
        deriv = enzyme_pool_derivative(1.0, k_deg, [], [])
        assert deriv == pytest.approx(0.0, abs=1e-10)

    def test_induction_increases_synthesis(self):
        k_deg = CYP_KDEG['CYP1A2']
        deriv = enzyme_pool_derivative(1.0, k_deg, induction_terms=[(1.0, 1.0, 1.0)], mbi_terms=[])
        assert deriv > 0.0

    def test_mbi_depletes_enzyme(self):
        k_deg = CYP_KDEG['CYP2D6']
        deriv = enzyme_pool_derivative(1.0, k_deg, induction_terms=[], mbi_terms=[(0.05, 0.1, 0.02)])
        assert deriv < 0.0

    def test_induction_steady_state_value(self):
        k_deg = CYP_KDEG['CYP1A2']
        c, e_max, ec50 = (1.0, 1.0, 1.0)
        expected_ss = 1.0 + e_max * c / (ec50 + c)
        deriv = enzyme_pool_derivative(expected_ss, k_deg, [(c, e_max, ec50)], [])
        assert deriv == pytest.approx(0.0, abs=1e-10)

class TestEnzymePoolSimulation:

    def test_enzyme_pools_stable_without_perturbation(self):
        drug = _aripiprazole_config(index=0)
        config = SimulationConfig(drugs=[drug], schedules=[MedicationSchedule(medication_index=0, generic_name='aripiprazole', bioavailability=0.87, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 10, 'frequency': 'daily'}])], horizon_days=28)
        result = run_simulation(config)
        for enz_name, enz_vals in result.enzyme_activity.items():
            assert np.allclose(enz_vals, 1.0, atol=0.01), f'Enzyme {enz_name} should remain at 1.0 without perturbation'

    def test_smoking_raises_cyp1a2_pool(self):
        drug = _clozapine_config()
        config = SimulationConfig(drugs=[drug], schedules=[MedicationSchedule(medication_index=0, generic_name='clozapine', bioavailability=0.5, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 200, 'frequency': 'BID'}])], horizon_days=42, smoking=True)
        result = run_simulation(config)
        assert 'CYP1A2' in result.enzyme_activity
        cyp1a2 = result.enzyme_activity['CYP1A2']
        t = result.time_hours
        ss_mask = t >= 35 * 24
        cyp1a2_ss = float(np.mean(cyp1a2[ss_mask]))
        assert cyp1a2_ss >= 1.3, f'CYP1A2 at SS with smoking should be >= 1.3, got {cyp1a2_ss:.3f}'

    def test_mbi_depletes_enzyme_in_simulation(self):
        mbi_drug = DrugConfig(index=0, generic_name='mbi_inhibitor', ka=1.0, bioavailability=0.9, vd_l=300.0, clearance_l_per_h=10.0, renal_clearance_fraction=0.5, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None, mbi_effects=[MBIParams(enzyme_name='CYP2D6', k_inact=0.1, k_i_conc=0.01)])
        substrate = _aripiprazole_config(index=1)
        config_with_mbi = SimulationConfig(drugs=[mbi_drug, substrate], schedules=[MedicationSchedule(medication_index=0, generic_name='mbi_inhibitor', bioavailability=0.9, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 20, 'frequency': 'daily'}]), MedicationSchedule(medication_index=1, generic_name='aripiprazole', bioavailability=0.87, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 10, 'frequency': 'daily'}])], horizon_days=42)
        result = run_simulation(config_with_mbi)
        cyp2d6 = result.enzyme_activity.get('CYP2D6')
        assert cyp2d6 is not None, 'CYP2D6 should be tracked'
        t = result.time_hours
        ss_mask = t >= 28 * 24
        cyp2d6_ss = float(np.mean(cyp2d6[ss_mask]))
        assert cyp2d6_ss < 0.7, f'CYP2D6 pool should be depleted by MBI drug, got {cyp2d6_ss:.3f}'

    def test_enzyme_recovery_after_mbi_drug_stopped(self):
        mbi_drug = DrugConfig(index=0, generic_name='mbi_drug', ka=1.0, bioavailability=0.9, vd_l=300.0, clearance_l_per_h=10.0, renal_clearance_fraction=0.5, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None, mbi_effects=[MBIParams(enzyme_name='CYP2D6', k_inact=0.1, k_i_conc=0.01)])
        substrate = _aripiprazole_config(index=1)
        config = SimulationConfig(drugs=[mbi_drug, substrate], schedules=[MedicationSchedule(medication_index=0, generic_name='mbi_drug', bioavailability=0.9, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 20, 'frequency': 'daily'}, {'event_type': 'stop', 'day': 21}]), MedicationSchedule(medication_index=1, generic_name='aripiprazole', bioavailability=0.87, events=[{'event_type': 'start', 'day': 0, 'dose_mg': 10, 'frequency': 'daily'}])], horizon_days=56)
        result = run_simulation(config)
        cyp2d6 = result.enzyme_activity['CYP2D6']
        t = result.time_hours
        depleted_mask = (t >= 18 * 24) & (t <= 21 * 24)
        recovery_mask = (t >= 42 * 24) & (t <= 49 * 24)
        if np.any(depleted_mask) and np.any(recovery_mask):
            depleted_level = float(np.mean(cyp2d6[depleted_mask]))
            recovered_level = float(np.mean(cyp2d6[recovery_mask]))
            assert recovered_level > depleted_level, f'CYP2D6 should recover after MBI drug stopped: depleted={depleted_level:.3f}, recovered={recovered_level:.3f}'
            assert recovered_level > 0.85, f'CYP2D6 should be mostly recovered by 3-4 weeks post-stop (t½_deg ≈ 51h), got {recovered_level:.3f}'
