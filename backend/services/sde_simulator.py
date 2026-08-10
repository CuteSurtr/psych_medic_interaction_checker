from __future__ import annotations
import numpy as np
from dataclasses import dataclass

@dataclass
class SDEResult:
    time_hours: list[float]
    paths: dict[str, list[list[float]]]
    n_paths: int
    method: str

class SDESimulator:

    def __init__(self, method: str='milstein', dt_hours: float=0.5):
        self.method = method
        self.dt = dt_hours

    def simulate(self, drug_configs: list[dict], dose_schedules: dict[str, list[tuple[float, float]]], duration_days: int=56, n_paths: int=200, seed: int=42) -> SDEResult:
        rng = np.random.default_rng(seed)
        n_steps = int(duration_days * 24 / self.dt)
        t = np.linspace(0, duration_days * 24, n_steps)
        sqrt_dt = np.sqrt(self.dt)
        all_paths: dict[str, list[list[float]]] = {d['name']: [] for d in drug_configs}
        for _ in range(n_paths):
            concs = {d['name']: np.zeros(n_steps) for d in drug_configs}
            a_gut = {d['name']: 0.0 for d in drug_configs}
            for drug in drug_configs:
                for dose_t, dose_mg in dose_schedules.get(drug['name'], []):
                    if dose_t == 0.0:
                        a_gut[drug['name']] += drug.get('F', 1.0) * dose_mg
            for step in range(1, n_steps):
                current_t = t[step]
                for drug in drug_configs:
                    name = drug['name']
                    ka = drug['ka']
                    vd = drug['vd']
                    cl = drug['cl']
                    sigma = drug.get('sigma', 0.1)
                    for dose_t, dose_mg in dose_schedules.get(name, []):
                        if t[step - 1] < dose_t <= current_t:
                            a_gut[name] += drug.get('F', 1.0) * dose_mg
                    c_prev = concs[name][step - 1]
                    absorption = ka * a_gut[name] / vd
                    elimination = cl * c_prev / vd
                    drift = absorption - elimination
                    a_gut[name] *= np.exp(-ka * self.dt)
                    Z = rng.standard_normal()
                    if self.method == 'milstein':
                        diffusion = sigma * c_prev * sqrt_dt * Z
                        correction = 0.5 * sigma ** 2 * c_prev * self.dt * (Z ** 2 - 1)
                        concs[name][step] = max(0.0, c_prev + drift * self.dt + diffusion + correction)
                    else:
                        diffusion = sigma * c_prev * sqrt_dt * Z
                        concs[name][step] = max(0.0, c_prev + drift * self.dt + diffusion)
            for drug in drug_configs:
                all_paths[drug['name']].append((concs[drug['name']] * 1000.0).tolist())
        return SDEResult(time_hours=t.tolist(), paths=all_paths, n_paths=n_paths, method=self.method)
