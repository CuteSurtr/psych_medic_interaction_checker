from __future__ import annotations
import networkx as nx
from dataclasses import dataclass

@dataclass
class FlowMetrics:
    max_flow_value: float
    bottleneck_enzyme: str | None
    bottleneck_utilization_pct: float
    enzyme_utilizations: dict[str, float]
    min_cut_edges: list[dict]

class MetabolicFlowAnalyzer:

    def __init__(self, drug_names: list[str], enzyme_substrate_data: list[dict]):
        self.drug_names = drug_names
        self.G = nx.DiGraph()
        self.enzyme_capacities: dict[str, float] = {}
        self._enzyme_set: set[str] = set()
        self.G.add_node('SOURCE')
        self.G.add_node('SINK')
        for dname in drug_names:
            self.G.add_node(f'drug:{dname}')
            self.G.add_edge('SOURCE', f'drug:{dname}', capacity=1000000.0)
        for entry in enzyme_substrate_data:
            dname = entry.get('drug_name', '')
            ename = entry.get('enzyme', '')
            vmax = entry.get('vmax', 0.0)
            if dname not in drug_names or vmax <= 0:
                continue
            self._enzyme_set.add(ename)
            self.G.add_node(f'enzyme:{ename}')
            edge_cap = float(vmax)
            drug_node = f'drug:{dname}'
            enz_node = f'enzyme:{ename}'
            if self.G.has_edge(drug_node, enz_node):
                self.G[drug_node][enz_node]['capacity'] += edge_cap
            else:
                self.G.add_edge(drug_node, enz_node, capacity=edge_cap)
            self.enzyme_capacities[ename] = self.enzyme_capacities.get(ename, 0.0) + edge_cap
        for ename, cap in self.enzyme_capacities.items():
            self.G.add_edge(f'enzyme:{ename}', 'SINK', capacity=cap)

    def compute_max_flow(self) -> tuple[float, dict]:
        if len(self._enzyme_set) == 0:
            return (0.0, {})
        flow_value, flow_dict = nx.maximum_flow(self.G, 'SOURCE', 'SINK')
        return (float(flow_value), flow_dict)

    def find_bottleneck(self) -> tuple[str | None, float]:
        if not self._enzyme_set:
            return (None, 0.0)
        _, flow_dict = self.compute_max_flow()
        max_util = 0.0
        bottleneck = None
        for ename in self._enzyme_set:
            enz_node = f'enzyme:{ename}'
            flow_to_sink = flow_dict.get(enz_node, {}).get('SINK', 0.0)
            capacity = self.enzyme_capacities.get(ename, 1.0)
            util = flow_to_sink / capacity if capacity > 0 else 0.0
            if util > max_util:
                max_util = util
                bottleneck = ename
        return (bottleneck, max_util * 100.0)

    def enzyme_utilizations(self) -> dict[str, float]:
        if not self._enzyme_set:
            return {}
        _, flow_dict = self.compute_max_flow()
        utils: dict[str, float] = {}
        for ename in self._enzyme_set:
            enz_node = f'enzyme:{ename}'
            flow_to_sink = flow_dict.get(enz_node, {}).get('SINK', 0.0)
            capacity = self.enzyme_capacities.get(ename, 1.0)
            utils[ename] = flow_to_sink / capacity * 100.0 if capacity > 0 else 0.0
        return utils

    def compute_min_cut(self) -> list[dict]:
        if not self._enzyme_set:
            return []
        _, partition = nx.minimum_cut(self.G, 'SOURCE', 'SINK')
        reachable, non_reachable = partition
        cut_edges: list[dict] = []
        for u in reachable:
            for v in non_reachable:
                if self.G.has_edge(u, v):
                    cut_edges.append({'from': u.replace('drug:', '').replace('enzyme:', ''), 'to': v.replace('drug:', '').replace('enzyme:', ''), 'capacity': self.G[u][v].get('capacity', 0.0)})
        return cut_edges

    def compute_all(self) -> FlowMetrics:
        max_flow, _ = self.compute_max_flow()
        bottleneck, util_pct = self.find_bottleneck()
        utils = self.enzyme_utilizations()
        cut_edges = self.compute_min_cut()
        return FlowMetrics(max_flow_value=max_flow, bottleneck_enzyme=bottleneck, bottleneck_utilization_pct=util_pct, enzyme_utilizations=utils, min_cut_edges=cut_edges)
