from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Any
from services.pk_simulator import DrugConfig, SimulationConfig, run_simulation
from services.dose_scheduler import MedicationSchedule
CYP2D6_MIXTURE = [(0.1, 0.07), (0.5, 0.15), (1.0, 0.7), (2.0, 0.08)]

@dataclass
class MonteCarloResult:
    time_hours: list[float]
    drug_stats: dict[str, dict[str, Any]]
    n_iterations: int

class MonteCarloSimulator:

    def __init__(self, n_iterations: int=1000, seed: int=42):
        self.n_iterations = n_iterations
        self.rng = np.random.default_rng(seed)

    def _perturb_config(self, config: SimulationConfig, drug_cv_map: dict[str, tuple[float, float]] | None=None, ka_cv: float=0.4) -> SimulationConfig:
        new_drugs: list[DrugConfig] = []
        for drug in config.drugs:
            if drug_cv_map and drug.generic_name in drug_cv_map:
                cl_cv, vd_cv = drug_cv_map[drug.generic_name]
            else:
                cl_cv, vd_cv = (0.35, 0.25)
            cl_factor = np.exp(self.rng.normal(0, cl_cv))
            vd_factor = np.exp(self.rng.normal(0, vd_cv))
            ka_factor = np.exp(self.rng.normal(0, ka_cv))
            new_drug = DrugConfig(index=drug.index, generic_name=drug.generic_name, ka=drug.ka * ka_factor, bioavailability=drug.bioavailability, vd_l=drug.vd_l * vd_factor, clearance_l_per_h=drug.clearance_l_per_h * cl_factor, renal_clearance_fraction=drug.renal_clearance_fraction, enzyme_substrates=drug.enzyme_substrates, enzyme_inhibitions=drug.enzyme_inhibitions, metabolite=drug.metabolite, mbi_effects=drug.mbi_effects, induction_effects=drug.induction_effects)
            new_drugs.append(new_drug)
        return SimulationConfig(drugs=new_drugs, schedules=config.schedules, horizon_days=config.horizon_days, cyp2d6_phenotype=config.cyp2d6_phenotype, cyp2c19_phenotype=config.cyp2c19_phenotype, smoking=config.smoking)

    def run(self, base_config: SimulationConfig, therapeutic_ranges: dict[str, tuple[float, float]] | None=None, toxic_thresholds: dict[str, float] | None=None, drug_cv_map: dict[str, tuple[float, float]] | None=None) -> MonteCarloResult:
        all_concs: dict[str, list[np.ndarray]] = {}
        ref_time: np.ndarray | None = None
        for _ in range(self.n_iterations):
            perturbed = self._perturb_config(base_config, drug_cv_map=drug_cv_map)
            try:
                result = run_simulation(perturbed)
            except (RuntimeError, ValueError, OverflowError, FloatingPointError):
                continue
            if ref_time is None:
                ref_time = result.time_hours
                for name in result.concentrations:
                    all_concs[name] = []
            for name, conc in result.concentrations.items():
                if name in all_concs:
                    if len(conc) == len(ref_time):
                        all_concs[name].append(conc)
        if ref_time is None:
            return MonteCarloResult([], {}, 0)
        drug_stats: dict[str, dict[str, Any]] = {}
        for name, conc_list in all_concs.items():
            if not conc_list:
                continue
            arr = np.array(conc_list)
            K = arr.shape[0]
            stats: dict[str, Any] = {'mean': np.mean(arr, axis=0).tolist(), 'median': np.median(arr, axis=0).tolist(), 'ci_5': np.percentile(arr, 5, axis=0).tolist(), 'ci_25': np.percentile(arr, 25, axis=0).tolist(), 'ci_75': np.percentile(arr, 75, axis=0).tolist(), 'ci_95': np.percentile(arr, 95, axis=0).tolist()}
            if toxic_thresholds and name in toxic_thresholds:
                thresh = toxic_thresholds[name]
                stats['p_toxic'] = np.mean(arr > thresh, axis=0).tolist()
            if therapeutic_ranges and name in therapeutic_ranges:
                lo, hi = therapeutic_ranges[name]
                stats['p_subtherapeutic'] = np.mean(arr < lo, axis=0).tolist()
                stats['p_supratherapeutic'] = np.mean(arr > hi, axis=0).tolist()
                stats['p_therapeutic'] = np.mean((arr >= lo) & (arr <= hi), axis=0).tolist()
            n_keep = min(100, K)
            stats['sample_trajectories'] = arr[:n_keep].tolist()
            drug_stats[name] = stats
        return MonteCarloResult(time_hours=ref_time.tolist(), drug_stats=drug_stats, n_iterations=sum((len(v) for v in all_concs.values())) // max(len(all_concs), 1))
