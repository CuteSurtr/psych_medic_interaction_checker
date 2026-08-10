from __future__ import annotations
import numpy as np
import networkx as nx
from dataclasses import dataclass
POTENCY_SCORE: dict[str, int] = {'strong': 3, 'moderate': 2, 'weak': 1}

@dataclass
class BipartiteMetrics:
    drug_names: list[str]
    enzyme_names: list[str]
    biadjacency_matrix: list[list[float]]
    singular_values: list[float]
    drug_clusters: list[list[float]]
    enzyme_clusters: list[list[float]]
    conflicts_per_enzyme: dict[str, int]
    total_conflicts: int
    minimum_cover: list[str]
    cover_resolves_n_conflicts: int

class CYP450BipartiteAnalyzer:

    def __init__(self, drug_names: list[str], cyp_profiles: list[dict]):
        self.drug_names = drug_names
        self._drug_idx = {name: i for i, name in enumerate(drug_names)}
        enzyme_set: set[str] = set()
        for p in cyp_profiles:
            enzyme_set.add(p['enzyme'])
        self.enzyme_names = sorted(enzyme_set)
        self._enz_idx = {name: i for i, name in enumerate(self.enzyme_names)}
        n = len(drug_names)
        m = len(self.enzyme_names)
        self.M = np.zeros((n, m))
        self._substrates: dict[str, set[str]] = {e: set() for e in self.enzyme_names}
        self._inhibitors: dict[str, set[str]] = {e: set() for e in self.enzyme_names}
        self._inducers: dict[str, set[str]] = {e: set() for e in self.enzyme_names}
        for p in cyp_profiles:
            dname = p.get('drug_name', '')
            ename = p.get('enzyme', '')
            di = self._drug_idx.get(dname)
            ei = self._enz_idx.get(ename)
            if di is None or ei is None:
                continue
            role = p.get('role', 'substrate').lower()
            if role == 'substrate':
                fm = p.get('fraction_metabolized', 0.5)
                self.M[di, ei] = float(fm)
                self._substrates[ename].add(dname)
            elif role == 'inhibitor':
                potency = POTENCY_SCORE.get(p.get('potency', 'moderate'), 2)
                self.M[di, ei] = -potency
                self._inhibitors[ename].add(dname)
            elif role == 'inducer':
                potency = POTENCY_SCORE.get(p.get('potency', 'moderate'), 2)
                self.M[di, ei] = potency
                self._inducers[ename].add(dname)

    def build_biadjacency_matrix(self) -> np.ndarray:
        return self.M.copy()

    def compute_svd(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self.M.shape[0] == 0 or self.M.shape[1] == 0:
            return (np.array([[]]), np.array([]), np.array([[]]))
        U, sigma, Vt = np.linalg.svd(self.M, full_matrices=False)
        return (U, sigma, Vt)

    def count_conflicts_per_enzyme(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for ename in self.enzyme_names:
            n_sub = len(self._substrates[ename])
            n_inh = len(self._inhibitors[ename])
            result[ename] = n_sub * n_inh
        return result

    def total_conflicts(self) -> int:
        return sum(self.count_conflicts_per_enzyme().values())

    def minimum_vertex_cover(self) -> tuple[list[str], int]:
        conflict_graph = nx.Graph()
        conflicts_by_drug: dict[str, int] = {}
        for ename in self.enzyme_names:
            for sub in self._substrates[ename]:
                for inh in self._inhibitors[ename]:
                    if sub != inh:
                        conflict_graph.add_edge(sub, inh, enzyme=ename)
                        conflicts_by_drug[sub] = conflicts_by_drug.get(sub, 0) + 1
                        conflicts_by_drug[inh] = conflicts_by_drug.get(inh, 0) + 1
        if conflict_graph.number_of_edges() == 0:
            return ([], 0)
        cover: list[str] = []
        g = conflict_graph.copy()
        total_resolved = 0
        while g.number_of_edges() > 0:
            degrees = dict(g.degree())
            max_node = max(degrees, key=lambda k: degrees[k])
            resolved = degrees[max_node]
            total_resolved += resolved
            cover.append(max_node)
            g.remove_node(max_node)
        return (cover, total_resolved)

    def compute_all(self) -> BipartiteMetrics:
        U, sigma, Vt = self.compute_svd()
        conflicts = self.count_conflicts_per_enzyme()
        cover, resolved = self.minimum_vertex_cover()
        drug_clusters: list[list[float]] = []
        enzyme_clusters: list[list[float]] = []
        if U.size > 0 and U.shape[1] >= 2:
            drug_clusters = U[:, :2].tolist()
        elif U.size > 0 and U.shape[1] == 1:
            drug_clusters = np.column_stack([U[:, 0], np.zeros(U.shape[0])]).tolist()
        if Vt.size > 0 and Vt.shape[0] >= 2:
            enzyme_clusters = Vt[:2, :].T.tolist()
        elif Vt.size > 0 and Vt.shape[0] == 1:
            enzyme_clusters = np.column_stack([Vt[0, :], np.zeros(Vt.shape[1])]).tolist()
        return BipartiteMetrics(drug_names=self.drug_names, enzyme_names=self.enzyme_names, biadjacency_matrix=self.M.tolist(), singular_values=sigma.tolist() if sigma.size > 0 else [], drug_clusters=drug_clusters, enzyme_clusters=enzyme_clusters, conflicts_per_enzyme=conflicts, total_conflicts=sum(conflicts.values()), minimum_cover=cover, cover_resolves_n_conflicts=resolved)
