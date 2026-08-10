import numpy as np
import pytest
from services.graph_analysis import InteractionGraphAnalyzer, SEVERITY_WEIGHT
from services.bipartite_analysis import CYP450BipartiteAnalyzer
from services.flow_analysis import MetabolicFlowAnalyzer
from services.combinatorial_analysis import PolypharmacyCombinatorics

class TestInteractionGraphAnalyzer:

    def _make_complete_graph(self, n: int=4) -> InteractionGraphAnalyzer:
        names = [f'drug_{i}' for i in range(n)]
        interactions = []
        for i in range(n):
            for j in range(i + 1, n):
                interactions.append({'drug_a_name': names[i], 'drug_b_name': names[j], 'severity': 'critical'})
        return InteractionGraphAnalyzer(names, interactions)

    def _make_empty_graph(self, n: int=4) -> InteractionGraphAnalyzer:
        names = [f'drug_{i}' for i in range(n)]
        return InteractionGraphAnalyzer(names, [])

    def _make_path_graph(self) -> InteractionGraphAnalyzer:
        names = ['drug_0', 'drug_1', 'drug_2', 'drug_3']
        interactions = [{'drug_a_name': 'drug_0', 'drug_b_name': 'drug_1', 'severity': 'major'}, {'drug_a_name': 'drug_1', 'drug_b_name': 'drug_2', 'severity': 'major'}, {'drug_a_name': 'drug_2', 'drug_b_name': 'drug_3', 'severity': 'major'}]
        return InteractionGraphAnalyzer(names, interactions)

    def test_complete_graph_chromatic_number(self):
        analyzer = self._make_complete_graph(4)
        assert analyzer.chromatic_number() == 4

    def test_empty_graph_independence(self):
        analyzer = self._make_empty_graph(5)
        alpha, safe = analyzer.maximum_independent_set()
        assert alpha == 5
        assert len(safe) == 5

    def test_empty_graph_chromatic_number_is_one(self):
        analyzer = self._make_empty_graph(4)
        assert analyzer.chromatic_number() == 1

    def test_adjacency_matrix_symmetric(self):
        analyzer = self._make_path_graph()
        W = analyzer.build_adjacency_matrix()
        assert np.allclose(W, W.T)

    def test_laplacian_first_eigenvalue_zero(self):
        analyzer = self._make_path_graph()
        eigenvalues, _ = analyzer.compute_laplacian_spectrum()
        assert eigenvalues[0] == pytest.approx(0.0, abs=1e-10)

    def test_fiedler_value_positive_for_connected_graph(self):
        analyzer = self._make_path_graph()
        fv, _ = analyzer.fiedler_value_and_vector()
        assert fv > 0.0

    def test_fiedler_vector_partition(self):
        names = ['cluster_a_0', 'cluster_a_1', 'cluster_b_0', 'cluster_b_1']
        interactions = [{'drug_a_name': 'cluster_a_0', 'drug_b_name': 'cluster_a_1', 'severity': 'major'}, {'drug_a_name': 'cluster_b_0', 'drug_b_name': 'cluster_b_1', 'severity': 'major'}]
        analyzer = InteractionGraphAnalyzer(names, interactions)
        fv, fiedler_vec = analyzer.fiedler_value_and_vector()
        assert fv == pytest.approx(0.0, abs=1e-08), 'Disconnected graph should have λ₂ ≈ 0'

    def test_spectral_radius_complete_graph(self):
        n = 4
        analyzer = self._make_complete_graph(n)
        rho, perron = analyzer.spectral_radius()
        expected = SEVERITY_WEIGHT['critical'] * (n - 1)
        assert rho == pytest.approx(expected, rel=0.01)

    def test_spectral_radius_empty_graph(self):
        analyzer = self._make_empty_graph(3)
        rho, _ = analyzer.spectral_radius()
        assert rho == pytest.approx(0.0, abs=1e-10)

    def test_bridge_drug_identified(self):
        analyzer = self._make_path_graph()
        bridge = analyzer.bridge_drug()
        assert bridge in analyzer.drug_names

    def test_independence_polynomial_empty_graph(self):
        n = 4
        analyzer = self._make_empty_graph(n)
        poly = analyzer.independence_polynomial()
        from math import comb
        for k in range(n + 1):
            assert poly[k] == comb(n, k), f'i_{k} should be C({n},{k}) = {comb(n, k)}'

    def test_independence_polynomial_complete_conflict_graph(self):
        analyzer = self._make_complete_graph(4)
        poly = analyzer.independence_polynomial()
        assert poly[0] == 1
        assert poly[1] == 4
        assert poly[2] == 0

    def test_compute_all_returns_all_fields(self):
        analyzer = self._make_path_graph()
        metrics = analyzer.compute_all()
        assert len(metrics.drug_names) == 4
        assert len(metrics.adjacency_matrix) == 4
        assert len(metrics.fiedler_vector) == 4
        assert metrics.chromatic_number >= 1
        assert metrics.independence_number >= 1
        assert metrics.bridge_drug is not None

class TestCYP450BipartiteAnalyzer:

    def _make_analyzer(self) -> CYP450BipartiteAnalyzer:
        drugs = ['fluoxetine', 'aripiprazole']
        profiles = [{'drug_name': 'fluoxetine', 'enzyme': 'CYP2D6', 'role': 'inhibitor', 'potency': 'strong', 'fraction_metabolized': 0.0}, {'drug_name': 'aripiprazole', 'enzyme': 'CYP2D6', 'role': 'substrate', 'potency': 'moderate', 'fraction_metabolized': 0.35}, {'drug_name': 'aripiprazole', 'enzyme': 'CYP3A4', 'role': 'substrate', 'potency': 'moderate', 'fraction_metabolized': 0.65}]
        return CYP450BipartiteAnalyzer(drugs, profiles)

    def test_bipartite_conflict_count(self):
        analyzer = self._make_analyzer()
        conflicts = analyzer.count_conflicts_per_enzyme()
        assert conflicts['CYP2D6'] == 1
        assert conflicts.get('CYP3A4', 0) == 0

    def test_bipartite_two_substrates_one_inhibitor(self):
        drugs = ['fluoxetine', 'aripiprazole', 'risperidone']
        profiles = [{'drug_name': 'fluoxetine', 'enzyme': 'CYP2D6', 'role': 'inhibitor', 'potency': 'strong'}, {'drug_name': 'aripiprazole', 'enzyme': 'CYP2D6', 'role': 'substrate', 'fraction_metabolized': 0.35}, {'drug_name': 'risperidone', 'enzyme': 'CYP2D6', 'role': 'substrate', 'fraction_metabolized': 0.6}]
        analyzer = CYP450BipartiteAnalyzer(drugs, profiles)
        conflicts = analyzer.count_conflicts_per_enzyme()
        assert conflicts['CYP2D6'] == 2

    def test_biadjacency_matrix_shape(self):
        analyzer = self._make_analyzer()
        M = analyzer.build_biadjacency_matrix()
        assert M.shape == (2, 2)

    def test_svd_singular_values_nonnegative(self):
        analyzer = self._make_analyzer()
        _, sigma, _ = analyzer.compute_svd()
        assert all((s >= 0 for s in sigma))

    def test_konig_minimum_cover(self):
        analyzer = self._make_analyzer()
        cover, resolved = analyzer.minimum_vertex_cover()
        assert 'fluoxetine' in cover or 'aripiprazole' in cover
        assert resolved >= 1

    def test_no_conflicts_empty_cover(self):
        drugs = ['aripiprazole', 'quetiapine']
        profiles = [{'drug_name': 'aripiprazole', 'enzyme': 'CYP2D6', 'role': 'substrate', 'fraction_metabolized': 0.35}, {'drug_name': 'quetiapine', 'enzyme': 'CYP3A4', 'role': 'substrate', 'fraction_metabolized': 0.7}]
        analyzer = CYP450BipartiteAnalyzer(drugs, profiles)
        cover, resolved = analyzer.minimum_vertex_cover()
        assert cover == []
        assert resolved == 0

class TestMetabolicFlowAnalyzer:

    def _make_analyzer(self) -> MetabolicFlowAnalyzer:
        drugs = ['drug_a', 'drug_b', 'drug_c', 'drug_d']
        data = [{'drug_name': 'drug_a', 'enzyme': 'CYP2D6', 'vmax': 100.0}, {'drug_name': 'drug_b', 'enzyme': 'CYP2D6', 'vmax': 100.0}, {'drug_name': 'drug_c', 'enzyme': 'CYP2D6', 'vmax': 100.0}, {'drug_name': 'drug_d', 'enzyme': 'CYP3A4', 'vmax': 200.0}]
        return MetabolicFlowAnalyzer(drugs, data)

    def test_max_flow_positive(self):
        analyzer = self._make_analyzer()
        flow, _ = analyzer.compute_max_flow()
        assert flow > 0.0

    def test_max_flow_bottleneck(self):
        analyzer = self._make_analyzer()
        bottleneck, util = analyzer.find_bottleneck()
        assert bottleneck in ('CYP2D6', 'CYP3A4')
        assert util > 0.0

    def test_enzyme_utilizations(self):
        analyzer = self._make_analyzer()
        utils = analyzer.enzyme_utilizations()
        assert 'CYP2D6' in utils
        assert 'CYP3A4' in utils
        for pct in utils.values():
            assert 0.0 <= pct <= 100.01

    def test_empty_network(self):
        analyzer = MetabolicFlowAnalyzer(['drug_a'], [])
        flow, _ = analyzer.compute_max_flow()
        assert flow == 0.0
        bottleneck, _ = analyzer.find_bottleneck()
        assert bottleneck is None

    def test_min_cut_returns_edges(self):
        analyzer = self._make_analyzer()
        edges = analyzer.compute_min_cut()
        assert len(edges) >= 1

class TestPolypharmacyCombinatorics:

    def test_interaction_pair_count(self):
        pc = PolypharmacyCombinatorics([f'drug_{i}' for i in range(8)])
        assert pc.interaction_pair_count() == 28

    def test_triple_count(self):
        pc = PolypharmacyCombinatorics([f'drug_{i}' for i in range(8)])
        assert pc.triple_interaction_count() == 56

    def test_three_drug_interaction_detected(self):
        drugs = ['lithium', 'ibuprofen', 'lisinopril', 'sertraline']
        pc = PolypharmacyCombinatorics(drugs)
        detected = pc.check_three_drug_interactions()
        assert len(detected) >= 1
        descriptions = [d['description'] for d in detected]
        assert any(('triple whammy' in desc.lower() for desc in descriptions))

    def test_three_drug_no_match(self):
        drugs = ['sertraline', 'lamotrigine', 'buspirone']
        pc = PolypharmacyCombinatorics(drugs)
        detected = pc.check_three_drug_interactions()
        assert len(detected) == 0

    def test_single_drug_no_pairs(self):
        pc = PolypharmacyCombinatorics(['solo_drug'])
        assert pc.interaction_pair_count() == 0

    def test_conflict_probability(self):
        pc = PolypharmacyCombinatorics(['a', 'b', 'c'])
        prob = pc.conflict_probability(formulary_size=50, n_substrates_per_enzyme={'CYP2D6': 10, 'CYP3A4': 15}, n_inhibitors_per_enzyme={'CYP2D6': 5, 'CYP3A4': 3})
        assert 0.0 <= prob <= 100.0

    def test_ramsey_six_drugs(self):
        import networkx as nx
        names = [f'drug_{i}' for i in range(6)]
        interactions = [{'drug_a_name': 'drug_0', 'drug_b_name': 'drug_1', 'severity': 'major'}, {'drug_a_name': 'drug_0', 'drug_b_name': 'drug_2', 'severity': 'major'}, {'drug_a_name': 'drug_1', 'drug_b_name': 'drug_3', 'severity': 'moderate'}, {'drug_a_name': 'drug_3', 'drug_b_name': 'drug_4', 'severity': 'major'}, {'drug_a_name': 'drug_4', 'drug_b_name': 'drug_5', 'severity': 'critical'}, {'drug_a_name': 'drug_2', 'drug_b_name': 'drug_5', 'severity': 'major'}]
        analyzer = InteractionGraphAnalyzer(names, interactions)
        g = analyzer._nx_graph
        complement = nx.complement(g)
        has_triangle_in_g = any(nx.triangles(g).values())
        has_triangle_in_complement = any(nx.triangles(complement).values())
        assert has_triangle_in_g or has_triangle_in_complement, 'Ramsey R(3,3)=6: any 2-coloring of K6 must contain a monochromatic K3'
