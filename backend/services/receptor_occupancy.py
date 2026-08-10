from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ReceptorBinding:
    target: str
    k_d_nm: float
    mechanism: str
_BINDING_PROFILES: dict[str, list[ReceptorBinding]] = {'fluoxetine': [ReceptorBinding('SERT', 0.8, 'inhibitor'), ReceptorBinding('NET', 240.0, 'inhibitor')], 'sertraline': [ReceptorBinding('SERT', 0.3, 'inhibitor'), ReceptorBinding('DAT', 25.0, 'inhibitor')], 'paroxetine': [ReceptorBinding('SERT', 0.1, 'inhibitor'), ReceptorBinding('NET', 40.0, 'inhibitor'), ReceptorBinding('M1', 108.0, 'antagonist')], 'citalopram': [ReceptorBinding('SERT', 1.2, 'inhibitor')], 'escitalopram': [ReceptorBinding('SERT', 1.1, 'inhibitor')], 'fluvoxamine': [ReceptorBinding('SERT', 2.2, 'inhibitor')], 'venlafaxine': [ReceptorBinding('SERT', 82.0, 'inhibitor'), ReceptorBinding('NET', 2480.0, 'inhibitor')], 'duloxetine': [ReceptorBinding('SERT', 0.8, 'inhibitor'), ReceptorBinding('NET', 7.5, 'inhibitor')], 'desvenlafaxine': [ReceptorBinding('SERT', 40.2, 'inhibitor'), ReceptorBinding('NET', 558.0, 'inhibitor')], 'aripiprazole': [ReceptorBinding('D2', 0.34, 'partial_agonist'), ReceptorBinding('5-HT2A', 3.4, 'antagonist'), ReceptorBinding('5-HT1A', 1.7, 'partial_agonist')], 'quetiapine': [ReceptorBinding('D2', 160.0, 'antagonist'), ReceptorBinding('5-HT2A', 295.0, 'antagonist'), ReceptorBinding('H1', 11.0, 'antagonist')], 'olanzapine': [ReceptorBinding('D2', 11.0, 'antagonist'), ReceptorBinding('5-HT2A', 4.0, 'antagonist'), ReceptorBinding('H1', 7.0, 'antagonist'), ReceptorBinding('M1', 1.9, 'antagonist')], 'risperidone': [ReceptorBinding('D2', 3.3, 'antagonist'), ReceptorBinding('5-HT2A', 0.2, 'antagonist'), ReceptorBinding('α1', 1.4, 'antagonist')], 'clozapine': [ReceptorBinding('D2', 126.0, 'antagonist'), ReceptorBinding('5-HT2A', 8.9, 'antagonist'), ReceptorBinding('M1', 1.8, 'antagonist'), ReceptorBinding('H1', 6.0, 'antagonist')], 'lurasidone': [ReceptorBinding('D2', 1.7, 'antagonist'), ReceptorBinding('5-HT2A', 2.0, 'antagonist'), ReceptorBinding('5-HT7', 0.5, 'antagonist')], 'ziprasidone': [ReceptorBinding('D2', 5.0, 'antagonist'), ReceptorBinding('5-HT2A', 0.4, 'antagonist')], 'paliperidone': [ReceptorBinding('D2', 2.8, 'antagonist'), ReceptorBinding('5-HT2A', 1.2, 'antagonist')], 'haloperidol': [ReceptorBinding('D2', 1.4, 'antagonist')], 'chlorpromazine': [ReceptorBinding('D2', 10.0, 'antagonist'), ReceptorBinding('H1', 3.0, 'antagonist'), ReceptorBinding('α1', 2.2, 'antagonist')], 'amitriptyline': [ReceptorBinding('SERT', 4.3, 'inhibitor'), ReceptorBinding('NET', 35.0, 'inhibitor'), ReceptorBinding('H1', 1.1, 'antagonist'), ReceptorBinding('M1', 18.0, 'antagonist')], 'nortriptyline': [ReceptorBinding('NET', 4.4, 'inhibitor'), ReceptorBinding('SERT', 18.0, 'inhibitor')], 'clomipramine': [ReceptorBinding('SERT', 0.3, 'inhibitor'), ReceptorBinding('NET', 38.0, 'inhibitor')], 'bupropion': [ReceptorBinding('NET', 52000.0, 'inhibitor'), ReceptorBinding('DAT', 526.0, 'inhibitor')], 'mirtazapine': [ReceptorBinding('α2', 20.0, 'antagonist'), ReceptorBinding('5-HT2A', 69.0, 'antagonist'), ReceptorBinding('H1', 0.14, 'antagonist')], 'trazodone': [ReceptorBinding('5-HT2A', 35.0, 'antagonist'), ReceptorBinding('SERT', 367.0, 'inhibitor')]}
_MW_G_PER_MOL: dict[str, float] = {'fluoxetine': 309.3, 'sertraline': 306.2, 'paroxetine': 329.4, 'citalopram': 324.4, 'escitalopram': 324.4, 'fluvoxamine': 318.3, 'venlafaxine': 277.4, 'duloxetine': 297.4, 'desvenlafaxine': 263.4, 'amitriptyline': 277.4, 'nortriptyline': 263.4, 'clomipramine': 314.9, 'aripiprazole': 448.4, 'quetiapine': 383.5, 'olanzapine': 312.4, 'risperidone': 410.5, 'ziprasidone': 412.9, 'clozapine': 326.8, 'lurasidone': 492.7, 'paliperidone': 426.5, 'haloperidol': 375.9, 'chlorpromazine': 318.9, 'bupropion': 239.7, 'trazodone': 371.9, 'mirtazapine': 265.4}
_CLINICAL_WINDOWS: dict[str, dict[str, tuple[float, float]]] = {'SERT': {'therapeutic': (80.0, 100.0)}, 'NET': {'therapeutic': (50.0, 100.0)}, 'DAT': {'therapeutic': (50.0, 100.0)}, 'D2': {'therapeutic': (60.0, 80.0), 'eps_risk': (80.0, 100.0)}, '5-HT2A': {'therapeutic': (50.0, 100.0)}}

def ng_ml_to_nm(conc_ng_ml: np.ndarray | float, mw_g_per_mol: float) -> np.ndarray | float:
    return np.asarray(conc_ng_ml, dtype=float) * 1000.0 / mw_g_per_mol

def fractional_occupancy(conc_nm: np.ndarray | float, k_d_nm: float) -> np.ndarray | float:
    c = np.asarray(conc_nm, dtype=float)
    c = np.maximum(c, 0.0)
    return c / (c + k_d_nm)

def emax_response(conc: np.ndarray | float, e0: float, e_max: float, ec50: float, gamma: float=1.0) -> np.ndarray | float:
    c = np.maximum(np.asarray(conc, dtype=float), 0.0)
    c_gamma = np.power(c, gamma)
    return e0 + e_max * c_gamma / (np.power(ec50, gamma) + c_gamma)

def classify_occupancy(target: str, occupancy_pct: float) -> str:
    windows = _CLINICAL_WINDOWS.get(target, {})
    if 'eps_risk' in windows and windows['eps_risk'][0] <= occupancy_pct <= windows['eps_risk'][1]:
        return 'EPS / side-effect risk'
    if 'therapeutic' in windows and windows['therapeutic'][0] <= occupancy_pct <= windows['therapeutic'][1]:
        return 'therapeutic'
    if occupancy_pct < windows.get('therapeutic', (50.0, 0.0))[0]:
        return 'subtherapeutic'
    return 'supratherapeutic'

@dataclass
class OccupancyTrajectory:
    drug_name: str
    target: str
    k_d_nm: float
    mechanism: str
    occupancy_pct: np.ndarray
    peak_occupancy_pct: float
    trough_occupancy_pct: float
    time_to_threshold_h: float | None
    steady_state_label: str

@dataclass
class DrugOccupancyResult:
    drug_name: str
    mw_g_per_mol: float
    time_hours: np.ndarray
    trajectories: list[OccupancyTrajectory] = field(default_factory=list)

def compute_receptor_occupancy(drug_name: str, time_hours: np.ndarray, plasma_concentration_ng_ml: np.ndarray, bindings: list[ReceptorBinding] | None=None, mw_g_per_mol: float | None=None, fraction_unbound: float=1.0) -> DrugOccupancyResult:
    key = drug_name.lower()
    bindings = bindings if bindings is not None else _BINDING_PROFILES.get(key, [])
    if mw_g_per_mol is None:
        mw_g_per_mol = _MW_G_PER_MOL.get(key, 350.0)
    time_hours = np.asarray(time_hours, dtype=float)
    c_ng_ml = np.asarray(plasma_concentration_ng_ml, dtype=float) * fraction_unbound
    c_nm = ng_ml_to_nm(c_ng_ml, mw_g_per_mol)
    trajectories: list[OccupancyTrajectory] = []
    for b in bindings:
        occ_frac = fractional_occupancy(c_nm, b.k_d_nm)
        occ_pct = 100.0 * occ_frac
        peak = float(np.max(occ_pct)) if occ_pct.size else 0.0
        tail_mask = time_hours >= float(time_hours[-1]) - 24.0 if time_hours.size else None
        if tail_mask is not None and np.any(tail_mask):
            trough = float(np.min(occ_pct[tail_mask]))
        else:
            trough = float(np.min(occ_pct)) if occ_pct.size else 0.0
        windows = _CLINICAL_WINDOWS.get(b.target, {})
        therapeutic_min = windows.get('therapeutic', (None, None))[0]
        t_to_threshold: float | None = None
        if therapeutic_min is not None:
            above = occ_pct >= therapeutic_min
            if np.any(above):
                t_to_threshold = float(time_hours[int(np.argmax(above))])
        trajectories.append(OccupancyTrajectory(drug_name=drug_name, target=b.target, k_d_nm=b.k_d_nm, mechanism=b.mechanism, occupancy_pct=occ_pct, peak_occupancy_pct=peak, trough_occupancy_pct=trough, time_to_threshold_h=t_to_threshold, steady_state_label=classify_occupancy(b.target, peak)))
    return DrugOccupancyResult(drug_name=drug_name, mw_g_per_mol=mw_g_per_mol, time_hours=time_hours, trajectories=trajectories)

def compute_regimen_occupancy(time_hours: np.ndarray, concentrations_ng_ml: dict[str, np.ndarray], fraction_unbound: dict[str, float] | None=None) -> dict[str, DrugOccupancyResult]:
    fraction_unbound = fraction_unbound or {}
    out: dict[str, DrugOccupancyResult] = {}
    for name, series in concentrations_ng_ml.items():
        out[name] = compute_receptor_occupancy(name, time_hours, series, fraction_unbound=fraction_unbound.get(name, 1.0))
    return out

def get_known_drugs() -> list[str]:
    return sorted(_BINDING_PROFILES.keys())
