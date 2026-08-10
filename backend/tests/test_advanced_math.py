from __future__ import annotations
import math
import numpy as np
import pytest
from services.monte_carlo import MonteCarloSimulator
from services.pk_simulator import DrugConfig, SimulationConfig
from services.enzyme_kinetics import EnzymeParams
from services.dose_scheduler import DoseEvent, MedicationSchedule

def _basic_drug_config(name: str='testdrug', idx: int=0) -> DrugConfig:
    return DrugConfig(index=idx, generic_name=name, ka=1.0, bioavailability=0.8, vd_l=70.0, clearance_l_per_h=5.0, renal_clearance_fraction=0.1, enzyme_substrates=[], enzyme_inhibitions=[], metabolite=None)

def _basic_schedule(name: str='testdrug', dose_mg: float=20.0) -> MedicationSchedule:
    return MedicationSchedule(medication_index=0, generic_name=name, bioavailability=0.8, events=[{'event_type': 'start', 'day': 0, 'dose_mg': dose_mg, 'frequency': 'daily'}])

class TestMonteCarlo:

    def test_instantiation(self):
        mc = MonteCarloSimulator(n_iterations=10, seed=0)
        assert mc.n_iterations == 10

    def test_perturb_varies_params(self):
        mc = MonteCarloSimulator(n_iterations=5, seed=0)
        drug = _basic_drug_config()
        sched = _basic_schedule()
        config = SimulationConfig(drugs=[drug], schedules=[sched], horizon_days=7)
        p1 = mc._perturb_config(config)
        p2 = mc._perturb_config(config)
        assert p1.drugs[0].clearance_l_per_h != p2.drugs[0].clearance_l_per_h

    def test_run_returns_result(self):
        mc = MonteCarloSimulator(n_iterations=5, seed=42)
        drug = _basic_drug_config()
        sched = _basic_schedule()
        config = SimulationConfig(drugs=[drug], schedules=[sched], horizon_days=7)
        result = mc.run(config)
        assert result.n_iterations > 0
        assert 'testdrug' in result.drug_stats
        stats = result.drug_stats['testdrug']
        assert len(stats['mean']) == len(result.time_hours)

    def test_ci_ordering(self):
        mc = MonteCarloSimulator(n_iterations=10, seed=42)
        drug = _basic_drug_config()
        sched = _basic_schedule()
        config = SimulationConfig(drugs=[drug], schedules=[sched], horizon_days=7)
        result = mc.run(config)
        stats = result.drug_stats['testdrug']
        ci5 = np.array(stats['ci_5'])
        ci25 = np.array(stats['ci_25'])
        median = np.array(stats['median'])
        ci75 = np.array(stats['ci_75'])
        ci95 = np.array(stats['ci_95'])
        assert np.all(ci5 <= ci25 + 1e-09)
        assert np.all(ci25 <= ci75 + 1e-09)
        assert np.all(ci75 <= ci95 + 1e-09)

    def test_toxicity_probability(self):
        mc = MonteCarloSimulator(n_iterations=20, seed=42)
        drug = _basic_drug_config()
        sched = _basic_schedule()
        config = SimulationConfig(drugs=[drug], schedules=[sched], horizon_days=7)
        result = mc.run(config, toxic_thresholds={'testdrug': 0.0})
        stats = result.drug_stats['testdrug']
        assert 'p_toxic' in stats
        p_toxic = np.array(stats['p_toxic'])
        assert np.all((p_toxic >= 0) & (p_toxic <= 1))
from services.optimal_control import TaperOptimizer, AVAILABLE_DOSES

class TestTaperOptimizer:

    def test_basic_taper(self):
        opt = TaperOptimizer()
        plan = opt.optimize('fluoxetine', start_dose=40.0, target_dose=0.0, duration_days=28)
        assert len(plan.steps) > 0
        assert plan.steps[-1].doses['fluoxetine'] == 0.0

    def test_titration_up(self):
        opt = TaperOptimizer()
        plan = opt.optimize('sertraline', start_dose=0.0, target_dose=200.0, duration_days=42)
        assert plan.steps[0].doses['sertraline'] == 0.0
        assert plan.steps[-1].doses['sertraline'] >= 150.0

    def test_dose_levels_in_available(self):
        opt = TaperOptimizer()
        plan = opt.optimize('aripiprazole', start_dose=30.0, target_dose=5.0, duration_days=28)
        valid = set(AVAILABLE_DOSES['aripiprazole'])
        for step in plan.steps:
            assert step.doses['aripiprazole'] in valid

    def test_recommendations_generated(self):
        opt = TaperOptimizer()
        plan = opt.optimize('fluoxetine', start_dose=40.0, target_dose=0.0, duration_days=28)
        assert len(plan.recommendations) > 0
        assert any(('fluoxetine' in r.lower() for r in plan.recommendations))

    def test_no_change_if_already_at_target(self):
        opt = TaperOptimizer()
        plan = opt.optimize('escitalopram', start_dose=10.0, target_dose=10.0, duration_days=14)
        assert all((s.doses['escitalopram'] == 10.0 for s in plan.steps))

    def test_risk_timeline_exists(self):
        opt = TaperOptimizer()
        plan = opt.optimize('clonazepam', start_dose=2.0, target_dose=0.0, duration_days=56)
        assert len(plan.risk_timeline) == len(plan.steps)

    def test_zero_duration_no_crash(self):
        opt = TaperOptimizer()
        plan = opt.optimize('fluoxetine', start_dose=40.0, target_dose=0.0, duration_days=0)
        assert len(plan.steps) == 0
from services.sde_simulator import SDESimulator

class TestSDESimulator:

    def _drug(self) -> list[dict]:
        return [{'name': 'testdrug', 'ka': 1.0, 'F': 0.8, 'vd': 70.0, 'cl': 5.0, 'sigma': 0.1}]

    def _sched(self) -> dict:
        return {'testdrug': [(24 * d, 20.0) for d in range(7)]}

    def test_milstein(self):
        sim = SDESimulator(method='milstein', dt_hours=1.0)
        result = sim.simulate(self._drug(), self._sched(), duration_days=7, n_paths=10)
        assert len(result.paths['testdrug']) == 10
        assert result.method == 'milstein'

    def test_euler_maruyama(self):
        sim = SDESimulator(method='euler-maruyama', dt_hours=1.0)
        result = sim.simulate(self._drug(), self._sched(), duration_days=7, n_paths=10)
        assert len(result.paths['testdrug']) == 10

    def test_paths_non_negative(self):
        sim = SDESimulator(method='milstein', dt_hours=1.0)
        result = sim.simulate(self._drug(), self._sched(), duration_days=7, n_paths=20)
        for path in result.paths['testdrug']:
            assert all((c >= 0 for c in path))

    def test_dose_at_t0_absorbed(self):
        drugs = [{'name': 'd', 'ka': 1.0, 'F': 1.0, 'vd': 70.0, 'cl': 5.0, 'sigma': 0.0}]
        sched = {'d': [(0.0, 100.0)]}
        sim = SDESimulator(method='milstein', dt_hours=1.0)
        result = sim.simulate(drugs, sched, duration_days=1, n_paths=1)
        arr = np.array(result.paths['d'])
        assert np.max(arr) > 0, 'Dose at t=0 should be absorbed'

    def test_paths_differ(self):
        sim = SDESimulator(method='milstein', dt_hours=1.0)
        result = sim.simulate(self._drug(), self._sched(), duration_days=7, n_paths=5)
        arr = np.array(result.paths['testdrug'])
        stds = np.std(arr, axis=0)
        assert np.any(stds > 0), 'Expected variability between stochastic paths'

    def test_zero_sigma_deterministic(self):
        drugs = [{'name': 'd', 'ka': 1.0, 'F': 0.8, 'vd': 70.0, 'cl': 5.0, 'sigma': 0.0}]
        sched = {'d': [(0, 20.0)]}
        sim = SDESimulator(method='milstein', dt_hours=1.0)
        result = sim.simulate(drugs, sched, duration_days=3, n_paths=3)
        arr = np.array(result.paths['d'])
        assert np.allclose(arr[0], arr[1], atol=1e-12), 'σ=0 should give identical paths'
        assert np.max(arr[0]) > 0, 'Dose at t=0 should produce non-zero concentrations'
from services.entropy_analysis import MetabolicEntropyAnalyzer

class TestEntropyAnalysis:

    def test_single_enzyme(self):
        analyzer = MetabolicEntropyAnalyzer()
        drugs = [{'name': 'A', 'clearance_l_per_h': 5.0}]
        profiles = [{'drug_name': 'A', 'enzyme': 'CYP2D6', 'role': 'substrate', 'fraction_metabolized': 1.0}]
        result = analyzer.compute(drugs, profiles)
        assert result.cdi < 0.2
        assert result.dominant_enzyme == 'CYP2D6'

    def test_uniform_distribution(self):
        analyzer = MetabolicEntropyAnalyzer()
        drugs = [{'name': f'D{i}', 'clearance_l_per_h': 1.0} for i in range(6)]
        enzymes = ['CYP2D6', 'CYP3A4', 'CYP1A2', 'CYP2C19', 'CYP2C9', 'UGT1A4']
        profiles = [{'drug_name': f'D{i}', 'enzyme': enzymes[i], 'role': 'substrate', 'fraction_metabolized': 1.0} for i in range(6)]
        result = analyzer.compute(drugs, profiles)
        assert result.cdi > 0.9

    def test_kl_divergence_zero_when_uniform(self):
        analyzer = MetabolicEntropyAnalyzer()
        drugs = [{'name': f'D{i}', 'clearance_l_per_h': 1.0} for i in range(6)]
        enzymes = ['CYP2D6', 'CYP3A4', 'CYP1A2', 'CYP2C19', 'CYP2C9', 'UGT1A4']
        profiles = [{'drug_name': f'D{i}', 'enzyme': enzymes[i], 'role': 'substrate', 'fraction_metabolized': 1.0} for i in range(6)]
        result = analyzer.compute(drugs, profiles)
        assert abs(result.kl_divergence) < 0.01

    def test_no_metabolism(self):
        analyzer = MetabolicEntropyAnalyzer()
        drugs = [{'name': 'lithium', 'clearance_l_per_h': 1.0}]
        result = analyzer.compute(drugs, [])
        assert result.cdi == 1.0

    def test_interpretation_concentrated(self):
        analyzer = MetabolicEntropyAnalyzer()
        drugs = [{'name': 'A', 'clearance_l_per_h': 10.0}, {'name': 'B', 'clearance_l_per_h': 10.0}]
        profiles = [{'drug_name': 'A', 'enzyme': 'CYP2D6', 'role': 'substrate', 'fraction_metabolized': 1.0}, {'drug_name': 'B', 'enzyme': 'CYP2D6', 'role': 'substrate', 'fraction_metabolized': 1.0}]
        result = analyzer.compute(drugs, profiles)
        assert 'concentrated' in result.interpretation.lower() or result.cdi < 0.3
from services.markov_model import PatientStateMarkovModel, STATES, P_BASELINE

class TestMarkovModel:

    def test_baseline_rows_sum_to_one(self):
        sums = P_BASELINE.sum(axis=1)
        np.testing.assert_allclose(sums, 1.0, atol=1e-10)

    def test_build_transition_preserves_stochastic(self):
        model = PatientStateMarkovModel()
        P = model.build_transition_matrix(['SSRI', 'atypical_antipsychotic'])
        sums = P.sum(axis=1)
        np.testing.assert_allclose(sums, 1.0, atol=1e-10)

    def test_stationary_sums_to_one(self):
        model = PatientStateMarkovModel()
        P = model.build_transition_matrix(['SSRI'])
        pi = model.stationary_distribution(P)
        assert abs(sum(pi.values()) - 1.0) < 1e-08

    def test_first_passage_positive(self):
        model = PatientStateMarkovModel()
        P = model.build_transition_matrix(['SSRI'])
        fpt = model.expected_first_passage(P, 'Remission')
        for state, weeks in fpt.items():
            assert weeks >= 0, f'Expected non-negative FPT from {state}'

    def test_treatment_improves_remission(self):
        model = PatientStateMarkovModel()
        P_none = model.build_transition_matrix([])
        P_ssri = model.build_transition_matrix(['SSRI'])
        pi_none = model.stationary_distribution(P_none)
        pi_ssri = model.stationary_distribution(P_ssri)
        assert pi_ssri['Remission'] >= pi_none['Remission'] - 0.01

    def test_simulate_trajectories(self):
        model = PatientStateMarkovModel()
        P = model.build_transition_matrix(['SSRI'])
        traj = model.simulate_trajectories(P, 'Partial Response', n_weeks=26, n_sims=100)
        assert sum(traj.values()) > 0.99

    def test_ssri_increases_partial_to_stable(self):
        model = PatientStateMarkovModel()
        P_none = model.build_transition_matrix([])
        P_ssri = model.build_transition_matrix(['SSRI'])
        assert P_ssri[1, 0] > P_none[1, 0], 'SSRI should boost Partial Response → Stable'

    def test_ssri_increases_relapse_to_partial(self):
        model = PatientStateMarkovModel()
        P_none = model.build_transition_matrix([])
        P_ssri = model.build_transition_matrix(['SSRI'])
        assert P_ssri[2, 1] > P_none[2, 1], 'SSRI should boost Relapse → Partial Response'

    def test_compute_all_returns_all_fields(self):
        model = PatientStateMarkovModel()
        result = model.compute_all(['SSRI'], initial_state='Relapse')
        assert result.transition_matrix is not None
        assert result.stationary_distribution is not None
        assert 'Remission' in result.first_passage_times
        assert result.trajectory_summary is not None
from services.tda_analysis import TopologicalAnalyzer

class TestTDAAnalysis:

    def test_empty_interactions(self):
        tda = TopologicalAnalyzer(['A', 'B', 'C'], [])
        result = tda.compute_persistence()
        assert result.betti_0_at_threshold == 3
        assert result.betti_1_count == 0

    def test_fully_connected(self):
        interactions = [{'drug_a_name': 'A', 'drug_b_name': 'B', 'severity': 'major'}, {'drug_a_name': 'B', 'drug_b_name': 'C', 'severity': 'major'}, {'drug_a_name': 'A', 'drug_b_name': 'C', 'severity': 'major'}]
        tda = TopologicalAnalyzer(['A', 'B', 'C'], interactions)
        result = tda.compute_persistence()
        assert result.betti_0_at_threshold == 1

    def test_loop_detected(self):
        interactions = [{'drug_a_name': 'A', 'drug_b_name': 'B', 'severity': 'critical'}, {'drug_a_name': 'B', 'drug_b_name': 'C', 'severity': 'critical'}, {'drug_a_name': 'A', 'drug_b_name': 'C', 'severity': 'critical'}]
        tda = TopologicalAnalyzer(['A', 'B', 'C'], interactions)
        result = tda.compute_persistence()
        assert result.has_feedback_loops

    def test_single_edge_no_loop(self):
        interactions = [{'drug_a_name': 'A', 'drug_b_name': 'B', 'severity': 'moderate'}]
        tda = TopologicalAnalyzer(['A', 'B', 'C'], interactions)
        result = tda.compute_persistence()
        assert not result.has_feedback_loops

    def test_stronger_interaction_shorter_distance(self):
        interactions = [{'drug_a_name': 'A', 'drug_b_name': 'B', 'severity': 'critical'}, {'drug_a_name': 'B', 'drug_b_name': 'C', 'severity': 'moderate'}]
        tda = TopologicalAnalyzer(['A', 'B', 'C'], interactions)
        assert tda.D[0, 1] < tda.D[1, 2]
from services.game_theory import EnzymeCompetitionGame

class TestGameTheory:

    def _setup(self):
        drugs = [{'name': 'fluoxetine', 'clearance_l_per_h': 25.0}, {'name': 'aripiprazole', 'clearance_l_per_h': 5.0}]
        profiles = [{'drug_name': 'fluoxetine', 'enzyme': 'CYP2D6', 'role': 'substrate', 'fraction_metabolized': 0.7}, {'drug_name': 'fluoxetine', 'enzyme': 'CYP2D6', 'role': 'inhibitor', 'potency': 'strong'}, {'drug_name': 'aripiprazole', 'enzyme': 'CYP2D6', 'role': 'substrate', 'fraction_metabolized': 0.35}, {'drug_name': 'aripiprazole', 'enzyme': 'CYP3A4', 'role': 'substrate', 'fraction_metabolized': 0.65}]
        return (drugs, profiles)

    def test_ideal_clearances(self):
        drugs, profiles = self._setup()
        game = EnzymeCompetitionGame(drugs, profiles)
        ideal = game.compute_ideal_clearances()
        assert ideal['fluoxetine'] == 25.0
        assert ideal['aripiprazole'] == 5.0

    def test_inhibition_reduces_clearance(self):
        drugs, profiles = self._setup()
        game = EnzymeCompetitionGame(drugs, profiles)
        ideal = game.compute_ideal_clearances()
        eff = game.compute_effective_clearances()
        assert eff['aripiprazole'] < ideal['aripiprazole']

    def test_social_cost_non_negative(self):
        drugs, profiles = self._setup()
        game = EnzymeCompetitionGame(drugs, profiles)
        assert game.social_cost() >= 0

    def test_poa_at_least_one(self):
        drugs, profiles = self._setup()
        game = EnzymeCompetitionGame(drugs, profiles)
        assert game.price_of_anarchy() >= 1.0

    def test_no_inhibition_no_overhead(self):
        drugs = [{'name': 'A', 'clearance_l_per_h': 5.0}, {'name': 'B', 'clearance_l_per_h': 5.0}]
        profiles = [{'drug_name': 'A', 'enzyme': 'CYP2D6', 'role': 'substrate', 'fraction_metabolized': 1.0}, {'drug_name': 'B', 'enzyme': 'CYP3A4', 'role': 'substrate', 'fraction_metabolized': 1.0}]
        game = EnzymeCompetitionGame(drugs, profiles)
        assert game.social_cost() < 0.01

    def test_competition_matrix(self):
        drugs, profiles = self._setup()
        game = EnzymeCompetitionGame(drugs, profiles)
        matrix = game.enzyme_competition_matrix()
        assert 'fluoxetine' in matrix
        assert 'CYP2D6' in matrix['fluoxetine']

    def test_compute_all_fields(self):
        drugs, profiles = self._setup()
        game = EnzymeCompetitionGame(drugs, profiles)
        metrics = game.compute_all()
        assert metrics.social_cost >= 0
        assert metrics.price_of_anarchy >= 1.0
        assert 'aripiprazole' in metrics.clearance_reduction_pct
