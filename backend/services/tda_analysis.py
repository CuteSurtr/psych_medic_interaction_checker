from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from services.constants import SEVERITY_WEIGHT

@dataclass
class PersistenceFeature:
    dimension: int
    birth: float
    death: float
    persistence: float

@dataclass
class TDAMetrics:
    persistence_features: list[dict]
    betti_0_at_threshold: int
    betti_1_count: int
    has_feedback_loops: bool
    total_persistence: float
    drug_names: list[str]

class TopologicalAnalyzer:

    def __init__(self, drug_names: list[str], interactions: list[dict]):
        self.drug_names = drug_names
        self.n = len(drug_names)
        self._name_to_idx = {name: i for i, name in enumerate(drug_names)}
        self.D = np.full((self.n, self.n), np.inf)
        np.fill_diagonal(self.D, 0.0)
        for inter in interactions:
            i = self._name_to_idx.get(inter.get('drug_a_name', ''))
            j = self._name_to_idx.get(inter.get('drug_b_name', ''))
            if i is None or j is None or i == j:
                continue
            sev = inter.get('severity', 'minor').lower()
            w = SEVERITY_WEIGHT.get(sev, 1)
            d = 1.0 / w
            self.D[i, j] = min(self.D[i, j], d)
            self.D[j, i] = min(self.D[j, i], d)

    def compute_persistence(self, max_dim: int=1) -> TDAMetrics:
        if self.n < 2:
            return TDAMetrics([], self.n, 0, False, 0.0, self.drug_names)
        edges: list[tuple[float, int, int]] = []
        for i in range(self.n):
            for j in range(i + 1, self.n):
                if self.D[i, j] < np.inf:
                    edges.append((self.D[i, j], i, j))
        edges.sort()
        parent = list(range(self.n))
        rank = [0] * self.n

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> bool:
            rx, ry = (find(x), find(y))
            if rx == ry:
                return False
            if rank[rx] < rank[ry]:
                rx, ry = (ry, rx)
            parent[ry] = rx
            if rank[rx] == rank[ry]:
                rank[rx] += 1
            return True
        features: list[PersistenceFeature] = []
        loop_count = 0
        component_births = {i: 0.0 for i in range(self.n)}
        for eps, u, v in edges:
            ru, rv = (find(u), find(v))
            if ru != rv:
                merged = union(u, v)
                if merged:
                    dying_root = rv if find(u) == ru else ru
                    birth = max(component_births.get(ru, 0.0), component_births.get(rv, 0.0))
                    features.append(PersistenceFeature(0, birth, eps, eps - birth))
            else:
                features.append(PersistenceFeature(1, eps, np.inf, np.inf))
                loop_count += 1
        n_components = len(set((find(i) for i in range(self.n))))
        total_pers = sum((f.persistence for f in features if f.persistence < np.inf))
        feat_dicts = [{'dimension': f.dimension, 'birth': f.birth, 'death': f.death if f.death < np.inf else None, 'persistence': f.persistence if f.persistence < np.inf else None} for f in features]
        return TDAMetrics(persistence_features=feat_dicts, betti_0_at_threshold=n_components, betti_1_count=loop_count, has_feedback_loops=loop_count > 0, total_persistence=round(total_pers, 4), drug_names=self.drug_names)
