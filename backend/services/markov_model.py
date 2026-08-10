from __future__ import annotations
import numpy as np
from dataclasses import dataclass
STATES = ['Stable', 'Partial Response', 'Relapse', 'Adverse Event', 'Hospitalized', 'Remission']
P_BASELINE = np.array([[0.6, 0.2, 0.1, 0.05, 0.03, 0.02], [0.15, 0.5, 0.2, 0.05, 0.05, 0.05], [0.05, 0.1, 0.55, 0.1, 0.15, 0.05], [0.1, 0.1, 0.15, 0.4, 0.2, 0.05], [0.05, 0.1, 0.1, 0.1, 0.6, 0.05], [0.7, 0.1, 0.05, 0.05, 0.02, 0.08]])
_STATE_ABBREV: dict[str, int] = {'Stable': 0, 'Partial': 1, 'Relapse': 2, 'AE': 3, 'Hosp': 4, 'Remission': 5}
DRUG_CLASS_EFFECTS: dict[str, dict[str, float]] = {'SSRI': {(0, 5): 0.08, (1, 0): 0.1, (2, 1): 0.1, 'AE_bump': 0.03}, 'SNRI': {(0, 5): 0.07, (1, 0): 0.08, (2, 1): 0.09, 'AE_bump': 0.04}, 'atypical_antipsychotic': {(2, 0): 0.15, (1, 0): 0.08, 'AE_bump': 0.05}, 'mood_stabilizer': {(0, 5): 0.05, (2, 1): 0.12, 'AE_bump': 0.02}, 'benzodiazepine': {(0, 0): 0.05, 'AE_bump': 0.06}}
IDX = {s: i for i, s in enumerate(STATES)}

@dataclass
class MarkovResult:
    transition_matrix: list[list[float]]
    stationary_distribution: dict[str, float]
    first_passage_times: dict[str, dict[str, float]]
    trajectory_summary: dict[str, float] | None

class PatientStateMarkovModel:

    def build_transition_matrix(self, drug_classes: list[str]) -> np.ndarray:
        P = P_BASELINE.copy()
        ae_idx = IDX['Adverse Event']
        for dc in drug_classes:
            effects = DRUG_CLASS_EFFECTS.get(dc, {})
            for key, delta in effects.items():
                if key == 'AE_bump':
                    for i in range(len(STATES)):
                        P[i, ae_idx] += delta
                elif isinstance(key, tuple) and len(key) == 2:
                    si, di = key
                    P[si, di] += delta
        P = np.maximum(P, 0.0)
        P = P / P.sum(axis=1, keepdims=True)
        return P

    def stationary_distribution(self, P: np.ndarray) -> dict[str, float]:
        eigenvalues, eigenvectors = np.linalg.eig(P.T)
        idx = int(np.argmin(np.abs(eigenvalues - 1.0)))
        pi = np.real(eigenvectors[:, idx])
        pi = np.abs(pi)
        pi = pi / pi.sum()
        return {s: round(float(pi[i]), 4) for i, s in enumerate(STATES)}

    def expected_first_passage(self, P: np.ndarray, target: str) -> dict[str, float]:
        j = IDX[target]
        n = len(STATES)
        indices = [i for i in range(n) if i != j]
        Q = P[np.ix_(indices, indices)]
        m = np.linalg.solve(np.eye(len(indices)) - Q, np.ones(len(indices)))
        result: dict[str, float] = {}
        k = 0
        for i, s in enumerate(STATES):
            if i == j:
                result[s] = 0.0
            else:
                result[s] = round(float(m[k]), 2)
                k += 1
        return result

    def simulate_trajectories(self, P: np.ndarray, initial: str, n_weeks: int=52, n_sims: int=1000, seed: int=42) -> dict[str, float]:
        rng = np.random.default_rng(seed)
        state_counts = np.zeros(len(STATES))
        s_idx = IDX[initial]
        total_steps = 0
        for _ in range(n_sims):
            current = s_idx
            for _ in range(n_weeks):
                current = rng.choice(len(STATES), p=P[current])
                state_counts[current] += 1
                total_steps += 1
        fractions = state_counts / max(total_steps, 1)
        return {s: round(float(fractions[i]), 4) for i, s in enumerate(STATES)}

    def compute_all(self, drug_classes: list[str], initial_state: str='Partial Response', n_weeks: int=52) -> MarkovResult:
        P = self.build_transition_matrix(drug_classes)
        stat = self.stationary_distribution(P)
        fpt: dict[str, dict[str, float]] = {}
        for target in ['Remission', 'Hospitalized']:
            fpt[target] = self.expected_first_passage(P, target)
        traj = self.simulate_trajectories(P, initial_state, n_weeks)
        return MarkovResult(transition_matrix=P.tolist(), stationary_distribution=stat, first_passage_times=fpt, trajectory_summary=traj)
