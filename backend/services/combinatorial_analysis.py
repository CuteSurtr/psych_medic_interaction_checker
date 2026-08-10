from __future__ import annotations
from math import comb, prod
from dataclasses import dataclass
from itertools import combinations
THREE_DRUG_INTERACTIONS: list[dict] = [{'drug_classes': [['carbamazepine'], ['quetiapine', 'lurasidone'], ['fluconazole', 'ketoconazole']], 'description': 'CYP3A4 inducer + CYP3A4 substrate + CYP3A4 inhibitor. Net effect on substrate levels is unpredictable and depends on relative doses and timing.', 'recommendation': 'Avoid this triple combination. Monitor substrate levels closely if unavoidable.', 'severity': 'major'}, {'drug_classes': [['lithium'], ['ibuprofen', 'naproxen', 'celecoxib'], ['lisinopril', 'enalapril', 'ramipril']], 'description': 'Triple whammy: NSAIDs reduce renal prostaglandins, ACE inhibitors reduce angiotensin II. Combined effect dramatically reduces lithium clearance.', 'recommendation': 'High risk of lithium toxicity. Avoid concurrent use of all three.', 'severity': 'critical'}, {'drug_classes': [['fluoxetine', 'sertraline', 'paroxetine', 'citalopram', 'escitalopram', 'fluvoxamine', 'venlafaxine', 'duloxetine'], ['tramadol'], ['ondansetron']], 'description': 'Additive serotonergic effect from SSRI/SNRI + tramadol, compounded by ondansetron (5-HT3 antagonist) which may mask early serotonin syndrome symptoms.', 'recommendation': 'Monitor carefully. Consider alternative antiemetic.', 'severity': 'moderate'}, {'drug_classes': [['fluoxetine', 'paroxetine'], ['aripiprazole', 'risperidone'], ['carbamazepine']], 'description': "Strong CYP2D6 inhibitor + CYP2D6 substrate + CYP3A4 inducer. CYP2D6 pathway blocked while CYP3A4 pathway is induced — net effect depends on substrate's enzyme fraction split.", 'recommendation': 'Requires therapeutic drug monitoring. Dose adjustment likely needed.', 'severity': 'major'}]

@dataclass
class CombinatoricMetrics:
    n_drugs: int
    pairwise_checks: int
    triple_checks: int
    detected_three_drug_interactions: list[dict]
    conflict_probability_pct: float | None

class PolypharmacyCombinatorics:

    def __init__(self, drug_names: list[str]):
        self.drug_names = [d.lower() for d in drug_names]
        self.n = len(drug_names)

    def interaction_pair_count(self) -> int:
        return comb(self.n, 2)

    def triple_interaction_count(self) -> int:
        return comb(self.n, 3)

    def check_three_drug_interactions(self) -> list[dict]:
        if self.n < 3:
            return []
        detected: list[dict] = []
        for rule in THREE_DRUG_INTERACTIONS:
            classes = rule['drug_classes']
            matches = [[d for d in self.drug_names if d in group] for group in classes]
            if all((len(m) > 0 for m in matches)):
                detected.append({'drugs': [m[0] for m in matches], 'description': rule['description'], 'recommendation': rule['recommendation'], 'severity': rule['severity']})
        return detected

    def conflict_probability(self, formulary_size: int, n_substrates_per_enzyme: dict[str, int], n_inhibitors_per_enzyme: dict[str, int]) -> float:
        if formulary_size < 2:
            return 0.0
        total_pairs = comb(formulary_size, 2)
        if total_pairs == 0:
            return 0.0
        prob_no_conflict = 1.0
        for ename in set(n_substrates_per_enzyme) | set(n_inhibitors_per_enzyme):
            n_sub = n_substrates_per_enzyme.get(ename, 0)
            n_inh = n_inhibitors_per_enzyme.get(ename, 0)
            conflict_pairs = n_sub * n_inh
            p_enzyme = min(conflict_pairs / total_pairs, 1.0)
            prob_no_conflict *= 1.0 - p_enzyme
        return (1.0 - prob_no_conflict) * 100.0

    def compute_all(self, formulary_size: int=50, n_substrates_per_enzyme: dict[str, int] | None=None, n_inhibitors_per_enzyme: dict[str, int] | None=None) -> CombinatoricMetrics:
        three_drug = self.check_three_drug_interactions()
        conflict_prob = None
        if n_substrates_per_enzyme and n_inhibitors_per_enzyme:
            conflict_prob = self.conflict_probability(formulary_size, n_substrates_per_enzyme, n_inhibitors_per_enzyme)
        return CombinatoricMetrics(n_drugs=self.n, pairwise_checks=self.interaction_pair_count(), triple_checks=self.triple_interaction_count(), detected_three_drug_interactions=three_drug, conflict_probability_pct=conflict_prob)
