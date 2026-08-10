from __future__ import annotations
import numpy as np
import networkx as nx
from dataclasses import dataclass, field
from itertools import combinations
from services.constants import SEVERITY_WEIGHT

@dataclass
class GraphMetrics:
    drug_names: list[str]
    adjacency_matrix: list[list[float]]
    laplacian_eigenvalues: list[float]
    fiedler_value: float
    fiedler_vector: list[float]
    spectral_radius: float
    perron_vector: list[float]
    chromatic_number: int
    independence_number: int
    max_safe_subset: list[str]
    bridge_drug: str | None
    independence_polynomial_coefficients: list[int]

class InteractionGraphAnalyzer:

    def __init__(self, drug_names: list[str], interactions: list[dict]):
        self.drug_names = drug_names
        self.n = len(drug_names)
        self._name_to_idx = {name: i for i, name in enumerate(drug_names)}
        self.W = np.zeros((self.n, self.n))
        self._nx_graph = nx.Graph()
        self._nx_graph.add_nodes_from(range(self.n))
        self._conflict_graph = nx.Graph()
        self._conflict_graph.add_nodes_from(range(self.n))
        for inter in interactions:
            i = self._name_to_idx.get(inter.get('drug_a_name', ''))
            j = self._name_to_idx.get(inter.get('drug_b_name', ''))
            if i is None or j is None or i == j:
                continue
            severity = inter.get('severity', 'minor').lower()
            w = SEVERITY_WEIGHT.get(severity, 1)
            self.W[i, j] = max(self.W[i, j], w)
            self.W[j, i] = max(self.W[j, i], w)
            self._nx_graph.add_edge(i, j, weight=w)
            if w >= 3:
                self._conflict_graph.add_edge(i, j, weight=w)

    def build_adjacency_matrix(self) -> np.ndarray:
        return self.W.copy()

    def compute_laplacian_spectrum(self) -> tuple[np.ndarray, np.ndarray]:
        D = np.diag(self.W.sum(axis=1))
        L = D - self.W
        eigenvalues, eigenvectors = np.linalg.eigh(L)
        return (eigenvalues, eigenvectors)

    def fiedler_value_and_vector(self) -> tuple[float, np.ndarray]:
        if self.n < 2:
            return (0.0, np.zeros(max(self.n, 1)))
        eigenvalues, eigenvectors = self.compute_laplacian_spectrum()
        return (float(eigenvalues[1]), eigenvectors[:, 1])

    def spectral_radius(self) -> tuple[float, np.ndarray]:
        if self.n == 0:
            return (0.0, np.array([]))
        eigenvalues, eigenvectors = np.linalg.eigh(self.W)
        max_idx = np.argmax(eigenvalues)
        perron = np.abs(eigenvectors[:, max_idx])
        norm = np.linalg.norm(perron)
        if norm > 0:
            perron = perron / norm
        return (float(eigenvalues[max_idx]), perron)

    def chromatic_number(self) -> int:
        if self._conflict_graph.number_of_edges() == 0:
            return 1
        coloring = nx.coloring.greedy_color(self._conflict_graph, strategy='largest_first')
        return max(coloring.values()) + 1 if coloring else 1

    def maximum_independent_set(self) -> tuple[int, list[str]]:
        complement = nx.complement(self._conflict_graph)
        clique, _ = nx.max_weight_clique(complement, weight=None)
        names = [self.drug_names[i] for i in sorted(clique)]
        return (len(clique), names)

    def bridge_drug(self) -> str | None:
        if self.n < 3:
            return None
        _, fv = self.fiedler_value_and_vector()
        bridge_idx = int(np.argmin(np.abs(fv)))
        return self.drug_names[bridge_idx]

    def independence_polynomial(self) -> list[int]:
        coeffs = [0] * (self.n + 1)
        coeffs[0] = 1
        for k in range(1, self.n + 1):
            count = 0
            for subset in combinations(range(self.n), k):
                is_independent = True
                for a, b in combinations(subset, 2):
                    if self._conflict_graph.has_edge(a, b):
                        is_independent = False
                        break
                if is_independent:
                    count += 1
            coeffs[k] = count
            if count == 0:
                break
        return coeffs

    def compute_all(self) -> GraphMetrics:
        eigenvalues, _ = self.compute_laplacian_spectrum() if self.n >= 2 else (np.array([0.0, 0.0]), None)
        fiedler_val, fiedler_vec = self.fiedler_value_and_vector()
        spec_radius, perron_vec = self.spectral_radius()
        chi = self.chromatic_number()
        alpha, safe_subset = self.maximum_independent_set()
        bridge = self.bridge_drug()
        indep_poly = self.independence_polynomial()
        return GraphMetrics(drug_names=self.drug_names, adjacency_matrix=self.W.tolist(), laplacian_eigenvalues=eigenvalues.tolist() if self.n >= 2 else [0.0], fiedler_value=fiedler_val, fiedler_vector=fiedler_vec.tolist(), spectral_radius=spec_radius, perron_vector=perron_vec.tolist(), chromatic_number=chi, independence_number=alpha, max_safe_subset=safe_subset, bridge_drug=bridge, independence_polynomial_coefficients=indep_poly)
