from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from services.constants import TRACKED_ENZYMES as ENZYMES

@dataclass
class GameTheoryMetrics:
    ideal_clearances: dict[str, float]
    effective_clearances: dict[str, float]
    clearance_reduction_pct: dict[str, float]
    social_cost: float
    price_of_anarchy: float
    enzyme_competition_matrix: dict[str, dict[str, float]]
    substitution_recommendations: list[dict]

class EnzymeCompetitionGame:
    ENZYMES = ENZYMES

    def __init__(self, drug_data: list[dict], cyp_profiles: list[dict]):
        self.drugs = drug_data
        self._drug_names = [d['name'] for d in drug_data]
        self._fm: dict[str, dict[str, float]] = {d['name']: {} for d in drug_data}
        self._inhibits: dict[str, dict[str, float]] = {d['name']: {} for d in drug_data}
        potency_map = {'strong': 0.3, 'moderate': 0.6, 'weak': 0.8}
        for cp in cyp_profiles:
            dname = cp.get('drug_name', '')
            enz = cp.get('enzyme', '')
            role = cp.get('role', '').lower()
            if dname not in self._fm:
                continue
            if role == 'substrate':
                self._fm[dname][enz] = float(cp.get('fraction_metabolized', 0.0))
            elif role == 'inhibitor':
                self._inhibits[dname][enz] = potency_map.get(cp.get('potency', 'moderate'), 0.6)

    def compute_ideal_clearances(self) -> dict[str, float]:
        return {d['name']: d.get('clearance_l_per_h', 1.0) for d in self.drugs}

    def compute_effective_clearances(self) -> dict[str, float]:
        effective: dict[str, float] = {}
        for drug in self.drugs:
            name = drug['name']
            cl_base = drug.get('clearance_l_per_h', 1.0)
            cl_eff = 0.0
            for enz in self.ENZYMES:
                fm = self._fm.get(name, {}).get(enz, 0.0)
                if fm <= 0:
                    continue
                inhibition_factor = 1.0
                for other in self.drugs:
                    if other['name'] == name:
                        continue
                    inh_effect = self._inhibits.get(other['name'], {}).get(enz)
                    if inh_effect is not None:
                        inhibition_factor *= inh_effect
                cl_eff += fm * cl_base * inhibition_factor
            renal_frac = 1.0 - sum(self._fm.get(name, {}).values())
            cl_eff += max(0, renal_frac) * cl_base
            effective[name] = max(cl_eff, 0.01)
        return effective

    def social_cost(self) -> float:
        ideal = self.compute_ideal_clearances()
        eff = self.compute_effective_clearances()
        return sum(((ideal[n] / eff[n] - 1) ** 2 for n in self._drug_names))

    def price_of_anarchy(self) -> float:
        sc = self.social_cost()
        return 1.0 + sc

    def enzyme_competition_matrix(self) -> dict[str, dict[str, float]]:
        result: dict[str, dict[str, float]] = {}
        for drug in self.drugs:
            name = drug['name']
            result[name] = {}
            for enz in self.ENZYMES:
                fm = self._fm.get(name, {}).get(enz, 0.0)
                result[name][enz] = fm
        return result

    def recommend_substitutions(self, alternatives: list[dict], alt_profiles: list[dict]) -> list[dict]:
        base_sc = self.social_cost()
        recommendations: list[dict] = []
        for drug in self.drugs:
            best_alt = None
            best_sc = base_sc
            for alt in alternatives:
                if alt['name'] in self._drug_names:
                    continue
                trial_drugs = [d for d in self.drugs if d['name'] != drug['name']] + [alt]
                trial_profiles = [cp for cp in self._flatten_profiles() if cp['drug_name'] != drug['name']] + [cp for cp in alt_profiles if cp['drug_name'] == alt['name']]
                trial_game = EnzymeCompetitionGame(trial_drugs, trial_profiles)
                trial_sc = trial_game.social_cost()
                if trial_sc < best_sc:
                    best_sc = trial_sc
                    best_alt = alt
            if best_alt and best_sc < base_sc * 0.8:
                recommendations.append({'replace': drug['name'], 'with': best_alt['name'], 'cost_reduction_pct': round((1 - best_sc / base_sc) * 100, 1)})
        return recommendations

    def _flatten_profiles(self) -> list[dict]:
        result = []
        for name in self._drug_names:
            for enz, fm in self._fm.get(name, {}).items():
                result.append({'drug_name': name, 'enzyme': enz, 'role': 'substrate', 'fraction_metabolized': fm})
            for enz, _ in self._inhibits.get(name, {}).items():
                result.append({'drug_name': name, 'enzyme': enz, 'role': 'inhibitor'})
        return result

    def compute_all(self) -> GameTheoryMetrics:
        ideal = self.compute_ideal_clearances()
        eff = self.compute_effective_clearances()
        reduction: dict[str, float] = {}
        for n in self._drug_names:
            reduction[n] = round((1 - eff[n] / ideal[n]) * 100, 1) if ideal[n] > 0 else 0.0
        return GameTheoryMetrics(ideal_clearances=ideal, effective_clearances={k: round(v, 3) for k, v in eff.items()}, clearance_reduction_pct=reduction, social_cost=round(self.social_cost(), 4), price_of_anarchy=round(self.price_of_anarchy(), 3), enzyme_competition_matrix=self.enzyme_competition_matrix(), substitution_recommendations=[])
