from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from scipy.integrate import solve_ivp
_DEFAULT_P_EFF_CM_PER_H: dict[str, float] = {'fluoxetine': 0.25, 'sertraline': 0.3, 'paroxetine': 0.22, 'citalopram': 0.18, 'escitalopram': 0.2, 'venlafaxine': 0.12, 'duloxetine': 0.18, 'aripiprazole': 0.15, 'quetiapine': 0.1, 'olanzapine': 0.22, 'risperidone': 0.08, 'clozapine': 0.3, 'haloperidol': 0.2, 'lithium': 0.004, 'valproic acid': 0.08, 'lamotrigine': 0.09, 'carbamazepine': 0.18, 'diazepam': 0.55, 'alprazolam': 0.3, 'clonazepam': 0.25}
_DEFAULT_F_UNBOUND: dict[str, float] = {'fluoxetine': 0.05, 'sertraline': 0.02, 'paroxetine': 0.05, 'citalopram': 0.2, 'escitalopram': 0.44, 'venlafaxine': 0.73, 'duloxetine': 0.05, 'aripiprazole': 0.01, 'quetiapine': 0.17, 'olanzapine': 0.07, 'risperidone': 0.1, 'clozapine': 0.05, 'haloperidol': 0.08, 'lithium': 1.0, 'valproic acid': 0.1, 'lamotrigine': 0.45, 'carbamazepine': 0.24, 'diazepam': 0.02, 'alprazolam': 0.2, 'clonazepam': 0.15}
DEFAULT_D_BRAIN_CM2_PER_H: float = 0.0072
DEFAULT_KE_TISSUE_PER_H: float = 0.01
DEFAULT_SLAB_DEPTH_CM: float = 1.0

@dataclass
class TissuePDEParams:
    drug_name: str
    p_eff_cm_per_h: float
    f_unbound: float
    d_tissue_cm2_per_h: float = DEFAULT_D_BRAIN_CM2_PER_H
    k_e_tissue_per_h: float = DEFAULT_KE_TISSUE_PER_H
    slab_depth_cm: float = DEFAULT_SLAB_DEPTH_CM
    n_nodes: int = 41

    @classmethod
    def for_drug(cls, drug_name: str) -> TissuePDEParams:
        key = drug_name.lower()
        p_eff = _DEFAULT_P_EFF_CM_PER_H.get(key, 0.1)
        f_u = _DEFAULT_F_UNBOUND.get(key, 0.2)
        return cls(drug_name=drug_name, p_eff_cm_per_h=p_eff, f_unbound=f_u)

@dataclass
class TissuePDEResult:
    time_hours: np.ndarray
    x_cm: np.ndarray
    concentration: np.ndarray
    surface_concentration: np.ndarray
    mean_concentration: np.ndarray
    deep_concentration: np.ndarray
    plasma_unbound: np.ndarray
    time_to_80pct_h: float | None

def _build_rhs(params: TissuePDEParams, t_plasma: np.ndarray, c_plasma: np.ndarray, source: np.ndarray | None):
    n = params.n_nodes
    dx = params.slab_depth_cm / (n - 1)
    D = params.d_tissue_cm2_per_h
    k_e = params.k_e_tissue_per_h
    p_eff = params.p_eff_cm_per_h
    f_u = params.f_unbound
    two_D_over_dx2 = 2.0 * D / (dx * dx)
    D_over_dx2 = D / (dx * dx)
    two_p_over_dx = 2.0 * p_eff / dx

    def plasma_u(t: float) -> float:
        return f_u * float(np.interp(t, t_plasma, c_plasma))

    def rhs(t: float, y: np.ndarray) -> np.ndarray:
        dydt = np.empty_like(y)
        c_plasma_u_t = plasma_u(t)
        dydt[0] = two_D_over_dx2 * (y[1] - y[0]) + two_p_over_dx * (c_plasma_u_t - y[0]) - k_e * y[0]
        dydt[1:-1] = D_over_dx2 * (y[2:] - 2.0 * y[1:-1] + y[:-2]) - k_e * y[1:-1]
        dydt[-1] = two_D_over_dx2 * (y[-2] - y[-1]) - k_e * y[-1]
        if source is not None:
            dydt += source
        return dydt
    return rhs

def solve_tissue_pde(params: TissuePDEParams, plasma_time_hours: np.ndarray, plasma_concentration_mg_per_l: np.ndarray, t_eval: np.ndarray | None=None, source: np.ndarray | None=None, initial_concentration: np.ndarray | None=None) -> TissuePDEResult:
    if params.n_nodes < 5:
        raise ValueError('n_nodes must be ≥ 5 for a meaningful diffusion grid')
    if params.slab_depth_cm <= 0.0:
        raise ValueError('slab_depth_cm must be positive')
    if params.d_tissue_cm2_per_h <= 0.0:
        raise ValueError('d_tissue_cm2_per_h must be positive')
    plasma_time_hours = np.asarray(plasma_time_hours, dtype=float)
    plasma_concentration_mg_per_l = np.asarray(plasma_concentration_mg_per_l, dtype=float)
    if plasma_time_hours.shape != plasma_concentration_mg_per_l.shape:
        raise ValueError('plasma time and concentration arrays must match in shape')
    if plasma_time_hours.size < 2:
        raise ValueError('plasma trajectory must contain at least 2 samples')
    x = np.linspace(0.0, params.slab_depth_cm, params.n_nodes)
    if initial_concentration is None:
        y0 = np.zeros(params.n_nodes)
    else:
        y0 = np.asarray(initial_concentration, dtype=float).copy()
        if y0.shape != (params.n_nodes,):
            raise ValueError('initial_concentration must have shape (n_nodes,)')
    if source is not None:
        source = np.asarray(source, dtype=float)
        if source.shape != (params.n_nodes,):
            raise ValueError('source must have shape (n_nodes,)')
    rhs = _build_rhs(params, plasma_time_hours, plasma_concentration_mg_per_l, source)
    if t_eval is None:
        t_eval = plasma_time_hours
    t_eval = np.asarray(t_eval, dtype=float)
    t_start = float(t_eval[0])
    t_end = float(t_eval[-1])
    sol = solve_ivp(rhs, (t_start, t_end), y0, method='LSODA', t_eval=t_eval, rtol=1e-06, atol=1e-09, max_step=np.inf)
    if not sol.success:
        raise RuntimeError(f'Tissue PDE solver failed: {sol.message}')
    concentration = np.maximum(sol.y, 0.0)
    plasma_unbound = params.f_unbound * np.interp(sol.t, plasma_time_hours, plasma_concentration_mg_per_l)
    surface = concentration[0, :]
    deep = concentration[-1, :]
    mean_c = concentration.mean(axis=0)
    target_final = float(plasma_unbound[-1])
    time_to_80pct: float | None = None
    if target_final > 1e-12:
        threshold = 0.8 * target_final
        mask = deep >= threshold
        if np.any(mask):
            time_to_80pct = float(sol.t[np.argmax(mask)])
    return TissuePDEResult(time_hours=sol.t, x_cm=x, concentration=concentration, surface_concentration=surface, mean_concentration=mean_c, deep_concentration=deep, plasma_unbound=plasma_unbound, time_to_80pct_h=time_to_80pct)

@dataclass
class MultiDrugTissueResult:
    time_hours: np.ndarray
    x_cm: np.ndarray
    per_drug: dict[str, TissuePDEResult] = field(default_factory=dict)

def solve_tissue_pde_for_regimen(plasma_time_hours: np.ndarray, drug_concentrations_mg_per_l: dict[str, np.ndarray], drug_params: dict[str, TissuePDEParams] | None=None) -> MultiDrugTissueResult:
    drug_params = drug_params or {}
    results: dict[str, TissuePDEResult] = {}
    x_grid: np.ndarray | None = None
    for name, c_plasma in drug_concentrations_mg_per_l.items():
        params = drug_params.get(name) or TissuePDEParams.for_drug(name)
        res = solve_tissue_pde(params, plasma_time_hours, c_plasma)
        results[name] = res
        if x_grid is None:
            x_grid = res.x_cm
    return MultiDrugTissueResult(time_hours=np.asarray(plasma_time_hours, dtype=float), x_cm=x_grid if x_grid is not None else np.array([]), per_drug=results)
