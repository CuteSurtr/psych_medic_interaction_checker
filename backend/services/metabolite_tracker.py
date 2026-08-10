from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass
class MetaboliteParams:
    parent_drug_index: int
    metabolite_name: str
    formation_fraction: float
    ke_metabolite: float
    vd_metabolite_l: float
    is_enzyme_inhibitor: bool
    inhibited_enzyme: str | None
    ki_nm: float | None

    @classmethod
    def from_medication_data(cls, parent_index: int, med_data: dict) -> MetaboliteParams | None:
        if not med_data.get('has_active_metabolite', False):
            return None
        met = med_data.get('metabolite', {})
        t_half_h = met.get('t_half_h', 24.0)
        ke = 0.693 / t_half_h if t_half_h > 0 else 0.0
        return cls(parent_drug_index=parent_index, metabolite_name=met.get('name', f'metabolite_of_{parent_index}'), formation_fraction=met.get('formation_fraction', 0.5), ke_metabolite=ke, vd_metabolite_l=met.get('vd_l', med_data.get('vd_l', 100.0)), is_enzyme_inhibitor=met.get('is_enzyme_inhibitor', False), inhibited_enzyme=met.get('inhibited_enzyme'), ki_nm=met.get('ki_nm'))

def build_metabolite_ode_terms(metabolites: list[MetaboliteParams], parent_elimination_rates: list[float], state_vector: np.ndarray, n_parent_drugs: int) -> np.ndarray:
    n_met = len(metabolites)
    derivatives = np.zeros(n_met)
    for m_idx, met in enumerate(metabolites):
        state_idx = 2 * n_parent_drugs + m_idx
        a_met = max(state_vector[state_idx], 0.0)
        parent_elim = parent_elimination_rates[met.parent_drug_index]
        formation = met.formation_fraction * parent_elim
        elimination = met.ke_metabolite * a_met
        derivatives[m_idx] = formation - elimination
    return derivatives
