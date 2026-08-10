from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from services.constants import TRACKED_ENZYMES

@dataclass
class EntropyMetrics:
    cdi: float
    entropy_bits: float
    max_entropy: float
    kl_divergence: float
    load_distribution: dict[str, float]
    dominant_enzyme: str
    dominant_enzyme_pct: float
    interpretation: str

class MetabolicEntropyAnalyzer:

    def compute(self, drug_data: list[dict], cyp_profiles: list[dict]) -> EntropyMetrics:
        loads = {e: 0.0 for e in TRACKED_ENZYMES}
        fm_lookup: dict[tuple[str, str], float] = {}
        for cp in cyp_profiles:
            if cp.get('role', '').lower() == 'substrate':
                key = (cp['drug_name'].lower(), cp['enzyme'])
                fm_lookup[key] = float(cp.get('fraction_metabolized', 0.0))
        for drug in drug_data:
            dname = drug['name'].lower()
            cl = drug.get('clearance_l_per_h', 1.0)
            for enz in TRACKED_ENZYMES:
                fm = fm_lookup.get((dname, enz), 0.0)
                loads[enz] += fm * cl
        load_arr = np.array([loads[e] for e in TRACKED_ENZYMES])
        total = load_arr.sum()
        if total <= 0:
            return EntropyMetrics(cdi=1.0, entropy_bits=0.0, max_entropy=np.log2(len(TRACKED_ENZYMES)), kl_divergence=0.0, load_distribution=loads, dominant_enzyme='none', dominant_enzyme_pct=0.0, interpretation='No hepatic metabolism detected.')
        p = load_arr / total
        p_pos = p[p > 0]
        H = float(-np.sum(p_pos * np.log2(p_pos)))
        H_max = float(np.log2(len(TRACKED_ENZYMES)))
        cdi = H / H_max if H_max > 0 else 1.0
        uniform = 1.0 / len(TRACKED_ENZYMES)
        kl = float(np.sum(p_pos * np.log2(p_pos / uniform)))
        dom_idx = int(np.argmax(load_arr))
        dom_enz = TRACKED_ENZYMES[dom_idx]
        dom_pct = float(load_arr[dom_idx] / total * 100)
        return EntropyMetrics(cdi=round(cdi, 4), entropy_bits=round(H, 4), max_entropy=round(H_max, 4), kl_divergence=round(kl, 4), load_distribution={e: round(v, 3) for e, v in loads.items()}, dominant_enzyme=dom_enz, dominant_enzyme_pct=round(dom_pct, 1), interpretation=self._interpret(cdi))

    @staticmethod
    def _interpret(cdi: float) -> str:
        if cdi >= 0.8:
            return 'Well-diversified metabolic profile. Low bottleneck risk.'
        elif cdi >= 0.5:
            return 'Moderately concentrated. Some metabolic pathway overlap.'
        elif cdi >= 0.3:
            return 'Concentrated metabolism. Consider drug substitution to diversify CYP pathways.'
        else:
            return 'Highly concentrated. Most drugs compete for the same enzyme. High DDI risk.'
