"""Regression tests tied to published pharmacology.

These assert biological directionality first and magnitude second, and where
the literature supplies a range they test against that range rather than an
invented tolerance. Each test names the source it encodes.

See validation/AUDIT.md (F-1, F-2, F-10, F-22) and
evidence/clozapine_smoking.yaml.
"""
from __future__ import annotations

import numpy as np
import pytest

from services.dose_scheduler import MedicationSchedule
from services.enzyme_kinetics import (
    CYP_KDEG, EnzymeParams, InhibitorParams, enzyme_pool_derivative,
)
from services.metabolite_tracker import MetaboliteParams
from services.pk_simulator import DrugConfig, SimulationConfig, run_simulation
from services.provenance import REGISTRY, EvidenceClass, Parameter, assumption
from services.sourced_params import (
    CLOZAPINE_CYP1A2_KM_MG_L,
    CLOZAPINE_FM_CYP1A2,
    CYP1A2_TURNOVER_HALFLIFE_H,
    FLUOXETINE_CYP2D6_KI_MG_L,
    NORFLUOXETINE_CYP2D6_KI_MG_L,
    SMOKING_CYP1A2_INDUCTION_RATIO,
    _racemic_tdi,
    documented_tdi,
    smoking_induction_term,
)


def _fluoxetine_aripiprazole_sim():
    """Fluoxetine 20 mg daily for 28 days, stopped; aripiprazole 10 mg throughout."""
    km, cl_ari = 0.5, 3.9
    fluox = DrugConfig(
        index=0, generic_name='fluoxetine', ka=0.7, bioavailability=0.72,
        vd_l=2500.0, clearance_l_per_h=0.693 * 2500 / (4 * 24),
        renal_clearance_fraction=0.05, enzyme_substrates=[],
        enzyme_inhibitions=[InhibitorParams('CYP2D6', FLUOXETINE_CYP2D6_KI_MG_L.value, 0)],
        metabolite=MetaboliteParams(
            parent_drug_index=0, metabolite_name='norfluoxetine',
            formation_fraction=0.8, ke_metabolite=0.693 / 240.0,
            vd_metabolite_l=2500.0, is_enzyme_inhibitor=True,
            inhibited_enzyme='CYP2D6', ki_nm=NORFLUOXETINE_CYP2D6_KI_MG_L.value),
    )
    arip = DrugConfig(
        index=1, generic_name='aripiprazole', ka=1.0, bioavailability=0.87,
        vd_l=300.0, clearance_l_per_h=cl_ari, renal_clearance_fraction=0.05,
        enzyme_substrates=[EnzymeParams('CYP2D6', cl_ari * km, km, 0.35),
                           EnzymeParams('CYP3A4', cl_ari * km, km, 0.60)],
        enzyme_inhibitions=[], metabolite=None,
    )
    return run_simulation(SimulationConfig(
        drugs=[fluox, arip], horizon_days=70,
        schedules=[
            MedicationSchedule(0, 'fluoxetine', 0.72, [
                {'event_type': 'start', 'day': 0, 'dose_mg': 20, 'frequency': 'daily'},
                {'event_type': 'stop', 'day': 28}]),
            MedicationSchedule(1, 'aripiprazole', 0.87, [
                {'event_type': 'start', 'day': 0, 'dose_mg': 10, 'frequency': 'daily'}]),
        ]))

# Flanagan 2024 (PMID 39173038): nonsmoker vs smoker plasma clozapine differed
# by 34% to 76% across dose bands and sexes.
CLOZAPINE_RISE_LOW = 1.34
CLOZAPINE_RISE_HIGH = 1.76


def _clozapine() -> DrugConfig:
    cl = 0.693 * 700.0 / 12.0
    km = CLOZAPINE_CYP1A2_KM_MG_L.value
    fm = CLOZAPINE_FM_CYP1A2.value
    return DrugConfig(
        index=0, generic_name='clozapine', ka=0.6, bioavailability=0.5,
        vd_l=700.0, clearance_l_per_h=cl, renal_clearance_fraction=0.05,
        enzyme_substrates=[
            EnzymeParams('CYP1A2', cl * km, km, fm),
            EnzymeParams('CYP3A4', cl * km, km, max(0.0, 1.0 - fm - 0.10)),
            EnzymeParams('CYP2D6', cl * km, km, 0.10),
        ],
        enzyme_inhibitions=[], metabolite=None,
    )


def _steady_state(smoking: bool, days: int = 42) -> float:
    res = run_simulation(SimulationConfig(
        drugs=[_clozapine()],
        schedules=[MedicationSchedule(
            medication_index=0, generic_name='clozapine', bioavailability=0.5,
            events=[{'event_type': 'start', 'day': 0, 'dose_mg': 200, 'frequency': 'BID'}])],
        horizon_days=days, smoking=smoking))
    conc = res.concentrations['clozapine']
    return float(np.mean(conc[res.time_hours >= (days - 7) * 24]))


class TestDirectionality:
    """Qualitative pharmacology. If these fail, magnitude is meaningless."""

    def test_smoking_cessation_increases_clozapine_exposure(self):
        smoking = _steady_state(True)
        non_smoking = _steady_state(False)
        assert non_smoking > smoking, (
            'Losing CYP1A2 induction must reduce clearance and raise exposure. '
            f'Got smoking={smoking:.1f}, non-smoking={non_smoking:.1f} ng/mL'
        )

    def test_smoking_raises_cyp1a2_activity_above_baseline(self):
        term = smoking_induction_term()
        kd = CYP_KDEG['CYP1A2']
        lo, hi = 0.5, 5.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if enzyme_pool_derivative(mid, kd, [term], []) > 0:
                lo = mid
            else:
                hi = mid
        assert (lo + hi) / 2 > 1.0, 'Smoking must induce CYP1A2 above baseline'

    def test_cyp1a2_returns_toward_baseline_after_cessation(self):
        kd = CYP_KDEG['CYP1A2']
        E = SMOKING_CYP1A2_INDUCTION_RATIO.value
        # Integrate ~10 half-lives (386 h). At 5 half-lives roughly 1.5% of the
        # induced excess still remains, which is correct behaviour rather than
        # a modelling error, so the horizon has to be long enough to test decay
        # to baseline rather than the tolerance.
        steps, dt = 40000, 0.01
        for _ in range(steps):
            E += enzyme_pool_derivative(E, kd, [], []) * dt
        assert E == pytest.approx(1.0, abs=0.01), (
            f'Enzyme pool must relax to baseline once the inducer stops, got {E:.4f}'
        )

    def test_cyp1a2_decay_follows_published_half_life(self):
        """Faber & Fuhr fitted a monoexponential decay to a residual value."""
        kd = CYP_KDEG['CYP1A2']
        E = SMOKING_CYP1A2_INDUCTION_RATIO.value
        target = 1.0 + (E - 1.0) / 2.0
        t, dt = 0.0, 0.005
        while E > target and t < 1000:
            E += enzyme_pool_derivative(E, kd, [], []) * dt
            t += dt
        assert CYP1A2_TURNOVER_HALFLIFE_H.ci_low <= t <= CYP1A2_TURNOVER_HALFLIFE_H.ci_high, (
            f'Modelled de-induction half-life {t:.1f} h outside published CI'
        )


class TestPublishedMagnitudes:
    """Quantitative agreement with literature ranges."""

    def test_cyp1a2_turnover_within_faber_fuhr_interval(self):
        """Faber & Fuhr 2004: apparent half-life 38.6 h (95% CI 27.4-54.4)."""
        t_half = float(np.log(2) / CYP_KDEG['CYP1A2'])
        assert CYP1A2_TURNOVER_HALFLIFE_H.ci_low <= t_half <= CYP1A2_TURNOVER_HALFLIFE_H.ci_high, (
            f'CYP1A2 turnover half-life {t_half:.1f} h outside published CI '
            f'{CYP1A2_TURNOVER_HALFLIFE_H.ci_low}-{CYP1A2_TURNOVER_HALFLIFE_H.ci_high} h'
        )

    def test_clozapine_rise_within_flanagan_range(self):
        """Flanagan 2024: 34% to 76% difference across dose bands and sexes."""
        ratio = _steady_state(False) / _steady_state(True)
        assert CLOZAPINE_RISE_LOW <= ratio <= CLOZAPINE_RISE_HIGH, (
            f'Predicted clozapine rise {ratio:.3f}x outside the published '
            f'{CLOZAPINE_RISE_LOW}-{CLOZAPINE_RISE_HIGH}x range'
        )

    def test_clozapine_stays_in_linear_kinetic_regime(self):
        """Guards audit finding F-22.

        The seed Km of 0.16 mg/L put therapeutic clozapine at C/Km 3.7-7.8,
        which inflated the predicted smoking effect from 1.38x to 2.08x. Every
        published Km (13-120 uM) places therapeutic concentrations well below
        Km, so C/Km must stay small.
        """
        c_mg_l = _steady_state(False) / 1000.0
        ratio = c_mg_l / CLOZAPINE_CYP1A2_KM_MG_L.value
        assert ratio < 0.5, (
            f'C/Km = {ratio:.2f}: clozapine has drifted into the saturated '
            f'regime, which no published Km supports at therapeutic doses'
        )


class TestProvenanceIntegrity:
    """The provenance layer must not let unsourced values look established."""

    def test_literature_class_requires_a_citation(self):
        with pytest.raises(ValueError, match='no citation'):
            Parameter(
                value=1.0, unit='hour', name='bogus',
                evidence_class=EvidenceClass.LITERATURE_DERIVED,
            )

    def test_assumption_requires_a_rationale(self):
        with pytest.raises(ValueError, match='rationale'):
            Parameter(
                value=1.0, unit='hour', name='bogus',
                evidence_class=EvidenceClass.MODELING_ASSUMPTION,
            )

    def test_assumption_helper_marks_value_unsourced(self):
        p = assumption(0.5, 'fraction', 'chosen for want of data', name='x')
        assert p.is_assumption and not p.is_sourced

    def test_fm_cyp1a2_is_still_flagged_as_unsourced(self):
        """Deliberate: this conflicts with Olesen & Linnet 2001 (30% in vitro).

        It must stay visible as an assumption until the discrepancy is resolved.
        """
        assert CLOZAPINE_FM_CYP1A2.is_assumption
        assert not CLOZAPINE_FM_CYP1A2.is_sourced

    def test_sourced_params_carry_verified_citations(self):
        for key in ('CYP1A2_TURNOVER_HALFLIFE_H', 'SMOKING_CYP1A2_INDUCTION_RATIO',
                    'CLOZAPINE_CYP1A2_KM_MG_L'):
            param = REGISTRY.get(key)
            assert param.citations, f'{key} must carry a citation'
            assert all(c.verified for c in param.citations), (
                f'{key} cites an unverified reference'
            )

    def test_parameter_sampling_respects_published_bounds(self):
        rng = np.random.default_rng(0)
        draws = [SMOKING_CYP1A2_INDUCTION_RATIO.sample(rng) for _ in range(500)]
        assert min(draws) > 1.0, 'induction ratio must stay above 1.0'
        assert np.median(draws) == pytest.approx(
            SMOKING_CYP1A2_INDUCTION_RATIO.value, rel=0.10)

    def test_parameter_without_range_yields_no_fake_variability(self):
        rng = np.random.default_rng(0)
        p = assumption(0.42, 'fraction', 'no interval reported', name='y')
        assert {p.sample(rng) for _ in range(20)} == {0.42}


class TestMechanismCorrectness:
    """Sager 2014 reports NO time-dependent inactivation of CYP2D6 by
    fluoxetine or norfluoxetine. Persistent CYP2D6 inhibition after fluoxetine
    is stopped must therefore emerge from norfluoxetine's long half-life
    sustaining reversible inhibition, not from enzyme destruction.

    These tests are a falsification check: they fail if the engine reverts to
    inventing mechanism-based inactivation.
    """

    def test_no_time_dependent_inhibition_of_cyp2d6_by_fluoxetine(self):
        assert documented_tdi('fluoxetine', 'CYP2D6') is None, (
            'Sager 2014 reports reversible CYP2D6 inhibition only; TDI must not '
            'be fabricated for this pair'
        )

    def test_documented_tdi_is_used_where_it_exists(self):
        """CYP2C19 and CYP3A4 TDI by fluoxetine are reported and must be used."""
        for enzyme in ('CYP2C19', 'CYP3A4'):
            tdi = documented_tdi('fluoxetine', enzyme)
            assert tdi is not None, f'fluoxetine {enzyme} TDI is documented'
            k_i_conc, k_inact = tdi
            assert k_i_conc > 0 and k_inact > 0

    def test_undocumented_pairs_get_no_invented_tdi(self):
        """Absence of evidence must yield None, never a guessed k_inact."""
        for drug, enzyme in [('paroxetine', 'CYP2D6'), ('sertraline', 'CYP2D6'),
                             ('made_up_drug', 'CYP3A4')]:
            assert documented_tdi(drug, enzyme) is None

    def test_racemic_tdi_reproduces_both_asymptotes(self):
        ki_eff, kinact_eff = _racemic_tdi([(1.8, 1.02), (55.0, 3.3)])
        assert kinact_eff == pytest.approx(1.02 + 3.3)
        low_c_efficiency = kinact_eff / ki_eff
        expected = 1.02 / (2 * 1.8) + 3.3 / (2 * 55.0)
        assert low_c_efficiency == pytest.approx(expected)

    def test_cyp2d6_inhibition_persists_after_fluoxetine_stops(self):
        """The central claim of Demo 1, with MBI removed.

        Substrate exposure must still be decaying slowly weeks after the parent
        drug has effectively cleared, driven by the metabolite.
        """
        result = _fluoxetine_aripiprazole_sim()
        t = result.time_hours

        def window(arr, d0, d1):
            m = (t >= d0 * 24) & (t < d1 * 24)
            return float(np.mean(arr[m]))

        fluox = window(result.concentrations['fluoxetine'], 42, 46)
        norflux = window(result.metabolite_concentrations['norfluoxetine'], 42, 46)
        on_treatment = window(result.concentrations['aripiprazole'], 24, 28)
        two_weeks_after = window(result.concentrations['aripiprazole'], 42, 46)

        assert norflux > 10 * fluox, (
            'Norfluoxetine must outlast fluoxetine; got norfluoxetine='
            f'{norflux:.2f}, fluoxetine={fluox:.2f} ng/mL'
        )
        assert two_weeks_after > 0.9 * on_treatment, (
            'Aripiprazole exposure must remain near on-treatment levels two '
            f'weeks after fluoxetine stops; got {two_weeks_after:.1f} vs '
            f'{on_treatment:.1f} ng/mL'
        )

    def test_cyp2d6_enzyme_pool_is_not_depleted_by_fluoxetine(self):
        """Reversible inhibition must not consume the enzyme pool.

        This is the observable that distinguishes the two mechanisms: MBI
        depletes the pool, competitive inhibition leaves it at baseline and
        acts through apparent Km instead.
        """
        result = _fluoxetine_aripiprazole_sim()
        pool = result.enzyme_activity['CYP2D6']
        assert float(np.min(pool)) > 0.99, (
            'CYP2D6 pool must stay at baseline under purely reversible '
            f'inhibition; minimum was {float(np.min(pool)):.4f}'
        )


class TestUnitConsistency:
    def test_km_conversion_from_micromolar(self):
        """61 uM clozapine at MW 326.8 is 19.93 mg/L."""
        assert CLOZAPINE_CYP1A2_KM_MG_L.value == pytest.approx(19.93, abs=0.01)

    def test_concentrations_are_non_negative(self):
        res = run_simulation(SimulationConfig(
            drugs=[_clozapine()],
            schedules=[MedicationSchedule(
                medication_index=0, generic_name='clozapine', bioavailability=0.5,
                events=[{'event_type': 'start', 'day': 0, 'dose_mg': 200, 'frequency': 'BID'},
                        {'event_type': 'stop', 'day': 20}])],
            horizon_days=40, smoking=True))
        assert np.all(res.concentrations['clozapine'] >= 0.0)
        assert np.all(res.enzyme_activity['CYP1A2'] > 0.0)
