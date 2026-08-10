from __future__ import annotations
import numpy as np
from dataclasses import dataclass
AVAILABLE_DOSES: dict[str, list[float]] = {'fluoxetine': [0, 10, 20, 40, 60], 'sertraline': [0, 25, 50, 100, 150, 200], 'paroxetine': [0, 10, 20, 30, 40], 'citalopram': [0, 10, 20, 40], 'escitalopram': [0, 5, 10, 20], 'venlafaxine': [0, 37.5, 75, 150, 225], 'duloxetine': [0, 20, 30, 60, 90, 120], 'aripiprazole': [0, 2, 5, 10, 15, 20, 30], 'quetiapine': [0, 25, 50, 100, 200, 300, 400, 600, 800], 'olanzapine': [0, 2.5, 5, 10, 15, 20], 'clozapine': [0, 25, 50, 100, 200, 300, 400, 500, 600], 'lamotrigine': [0, 25, 50, 100, 150, 200, 300, 400], 'lithium': [0, 150, 300, 450, 600, 900, 1200], 'clonazepam': [0, 0.25, 0.5, 1.0, 1.5, 2.0], 'diazepam': [0, 2, 5, 10, 15, 20], 'alprazolam': [0, 0.25, 0.5, 1.0, 2.0]}

@dataclass
class TaperStep:
    day: int
    doses: dict[str, float]
    description: str

@dataclass
class TaperPlan:
    steps: list[TaperStep]
    recommendations: list[str]
    total_cost: float
    risk_timeline: list[dict]

class TaperOptimizer:

    def __init__(self, alpha: float=1.0, beta: float=1.0, delta: float=0.5):
        self.alpha = alpha
        self.beta = beta
        self.delta = delta

    def _step_cost(self, dose: float, prev_dose: float, target_dose: float, day: int, total_days: int) -> float:
        deviation = (dose - target_dose) ** 2
        jump = abs(dose - prev_dose)
        progress_weight = day / max(total_days, 1)
        return self.alpha * deviation * progress_weight + self.delta * jump

    def optimize(self, drug_name: str, start_dose: float, target_dose: float, duration_days: int=56, constraints: dict | None=None) -> TaperPlan:
        doses = AVAILABLE_DOSES.get(drug_name.lower(), [])
        if not doses:
            doses = sorted(set([0, start_dose, target_dose]))
        max_step = float('inf')
        if constraints:
            max_step = constraints.get('max_daily_reduction', float('inf'))
            min_step_days = constraints.get('min_step_duration_days', 7)
        else:
            min_step_days = 7
        schedule: list[TaperStep] = []
        recommendations: list[str] = []
        risk_timeline: list[dict] = []
        current_dose = start_dose
        total_cost = 0.0
        if duration_days <= 0:
            return TaperPlan(steps=[], recommendations=[], total_cost=0.0, risk_timeline=[])
        change_days = list(range(0, duration_days, min_step_days))
        if not change_days:
            change_days = [0]
        if change_days[-1] != duration_days - 1:
            change_days.append(duration_days - 1)
        for i, day in enumerate(change_days):
            progress = day / max(duration_days - 1, 1)
            ideal_dose = start_dose + (target_dose - start_dose) * progress
            valid = [d for d in doses if abs(d - current_dose) <= max_step or d == current_dose]
            if not valid:
                valid = doses
            best_dose = min(valid, key=lambda d: abs(d - ideal_dose))
            cost = self._step_cost(best_dose, current_dose, target_dose, day, duration_days)
            total_cost += cost
            desc = ''
            if best_dose != current_dose:
                if best_dose == 0:
                    desc = f'Day {day}: Stop {drug_name}'
                elif current_dose == 0:
                    desc = f'Day {day}: Start {drug_name} {best_dose}mg'
                else:
                    direction = 'Increase' if best_dose > current_dose else 'Decrease'
                    desc = f'Day {day}: {direction} {drug_name} from {current_dose}mg to {best_dose}mg'
                recommendations.append(desc)
            else:
                desc = f'Day {day}: Continue {drug_name} {best_dose}mg'
            schedule.append(TaperStep(day=day, doses={drug_name: best_dose}, description=desc))
            risk_timeline.append({'day': day, 'risk': abs(best_dose - ideal_dose) / max(start_dose, 1)})
            current_dose = best_dose
        return TaperPlan(steps=schedule, recommendations=recommendations, total_cost=total_cost, risk_timeline=risk_timeline)
