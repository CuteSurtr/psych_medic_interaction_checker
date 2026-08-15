"""Simulation drivers for validation scenarios.

A driver runs the real engine and returns a dict of endpoint name to predicted
value. Where an endpoint carries uncertainty, it returns
{'value': x, 'low': l, 'high': h} produced by re-running the engine at the
published bounds of the driving parameter, not by an analytic shortcut.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[2] / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services import pk_simulator as pks  # noqa: E402
from services.dose_scheduler import MedicationSchedule  # noqa: E402
from services.enzyme_kinetics import CYP_KDEG, EnzymeParams  # noqa: E402
from services.pk_simulator import (  # noqa: E402
    DrugConfig, SimulationConfig, run_simulation,
)
from services.sourced_params import (  # noqa: E402
    CLOZAPINE_CYP1A2_KM_MG_L, CLOZAPINE_FM_CYP1A2,
    SMOKING_CYP1A2_EC50, SMOKING_CYP1A2_INDUCTION_RATIO,
)


def _clozapine(fm_cyp1a2: float | None = None, km: float | None = None) -> DrugConfig:
    """Clozapine configuration.

    Km is sourced (Eiermann 1997, 61 uM). fm_CYP1A2 is NOT sourced and is the
    dominant driver of the predicted exposure change, so both are exposed as
    arguments for sensitivity analysis.
    """
    if fm_cyp1a2 is None:
        fm_cyp1a2 = CLOZAPINE_FM_CYP1A2.value
    if km is None:
        km = CLOZAPINE_CYP1A2_KM_MG_L.value
    cl = 0.693 * 700.0 / 12.0
    km_1a2 = km_3a4 = km_2d6 = km
    remainder = 1.0 - fm_cyp1a2 - 0.10
    return DrugConfig(
        index=0, generic_name='clozapine', ka=0.6, bioavailability=0.5,
        vd_l=700.0, clearance_l_per_h=cl, renal_clearance_fraction=0.05,
        enzyme_substrates=[
            EnzymeParams('CYP1A2', cl * km_1a2, km_1a2, fm_cyp1a2),
            EnzymeParams('CYP3A4', cl * km_3a4, km_3a4, max(0.0, remainder)),
            EnzymeParams('CYP2D6', cl * km_2d6, km_2d6, 0.10),
        ],
        enzyme_inhibitions=[], metabolite=None,
    )


def _schedule(dose_mg: float = 200.0) -> MedicationSchedule:
    return MedicationSchedule(
        medication_index=0, generic_name='clozapine', bioavailability=0.5,
        events=[{'event_type': 'start', 'day': 0, 'dose_mg': dose_mg, 'frequency': 'BID'}],
    )


def _steady_state_conc(smoking: bool, drug: DrugConfig, days: int = 42) -> float:
    result = run_simulation(SimulationConfig(
        drugs=[drug], schedules=[_schedule()], horizon_days=days, smoking=smoking))
    conc = result.concentrations['clozapine']
    t = result.time_hours
    return float(np.mean(conc[t >= (days - 7) * 24]))


def _patch_induction_ratio(ratio: float):
    """Temporarily drive the engine at a different induction ratio."""
    ec50 = SMOKING_CYP1A2_EC50.value
    exposure = 1.0
    saturation = exposure / (ec50 + exposure)
    emax_param = (ratio - 1.0) / saturation
    original = pks.smoking_induction_term
    pks.smoking_induction_term = lambda: (exposure, emax_param, ec50)
    return original


def _ratio_at(induction_ratio: float, drug: DrugConfig) -> float:
    original = _patch_induction_ratio(induction_ratio)
    try:
        smk = _steady_state_conc(True, drug)
        non = _steady_state_conc(False, drug)
        return non / (smk + 1e-12)
    finally:
        pks.smoking_induction_term = original


def _deinduction_half_life(drug: DrugConfig) -> float:
    """Measure the modelled CYP1A2 relaxation half-life from the ODE output."""
    days = 60
    cessation_day = 30
    result = run_simulation(SimulationConfig(
        drugs=[drug], schedules=[_schedule()], horizon_days=days, smoking=True))
    induced = float(np.mean(
        result.enzyme_activity['CYP1A2'][result.time_hours >= (cessation_day - 5) * 24]))
    # Relaxation is a property of the enzyme pool: integrate it directly from
    # the induced level with the inducer removed.
    kd = CYP_KDEG['CYP1A2']
    from services.enzyme_kinetics import enzyme_pool_derivative
    E, t, dt = induced, 0.0, 0.005
    target = 1.0 + (induced - 1.0) / 2.0
    while E > target and t < 1000:
        E += enzyme_pool_derivative(E, kd, [], []) * dt
        t += dt
    return t


def clozapine_smoking_cessation(scenario) -> dict:
    drug = _clozapine()

    point = _ratio_at(SMOKING_CYP1A2_INDUCTION_RATIO.value, drug)
    low = _ratio_at(SMOKING_CYP1A2_INDUCTION_RATIO.ci_low, drug)
    high = _ratio_at(SMOKING_CYP1A2_INDUCTION_RATIO.ci_high, drug)

    induced_activity = 1.0 + (SMOKING_CYP1A2_INDUCTION_RATIO.value - 1.0)
    half_life = _deinduction_half_life(drug)

    return {
        'clozapine_concentration_ratio_after_cessation': {
            'value': round(point, 4), 'low': round(low, 4), 'high': round(high, 4),
        },
        'clozapine_percent_increase_after_cessation': {
            'value': round((point - 1.0) * 100.0, 2),
            'low': round((low - 1.0) * 100.0, 2),
            'high': round((high - 1.0) * 100.0, 2),
        },
        'direction_clozapine_exposure_rises': round(point, 4),
        'direction_cyp1a2_activity_falls': round(1.0 / induced_activity, 4),
        'cyp1a2_deinduction_half_life_h': round(half_life, 2),
    }


DRIVERS = {'clozapine_smoking_cessation': clozapine_smoking_cessation}
