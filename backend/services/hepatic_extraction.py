from __future__ import annotations
from dataclasses import dataclass, field
DEFAULT_Q_HEPATIC_L_PER_H: float = 81.0
DEFAULT_Q_PORTAL_FRACTION: float = 0.75

@dataclass
class EnzymePathway:
    enzyme: str
    vmax_mg_per_h: float
    km_mg_per_l: float

@dataclass
class InhibitorTerm:
    enzyme: str
    unbound_concentration_mg_per_l: float
    ki_mg_per_l: float

@dataclass
class HepaticExtractionResult:
    cl_intrinsic_l_per_h: float
    cl_intrinsic_inhibited_l_per_h: float
    cl_hepatic_l_per_h: float
    cl_hepatic_inhibited_l_per_h: float
    extraction_ratio: float
    extraction_ratio_inhibited: float
    first_pass_fraction: float
    first_pass_fraction_inhibited: float
    bioavailability_hepatic: float
    bioavailability_hepatic_inhibited: float
    pathway_contributions: dict[str, float]
    q_hepatic_l_per_h: float
    f_unbound: float
    classification: str

def classify_extraction(e_h: float) -> str:
    if e_h < 0.3:
        return 'low'
    if e_h < 0.7:
        return 'intermediate'
    return 'high'

def compute_hepatic_clearance(pathways: list[EnzymePathway], f_unbound: float, q_hepatic_l_per_h: float=DEFAULT_Q_HEPATIC_L_PER_H, inhibitors: list[InhibitorTerm] | None=None) -> HepaticExtractionResult:
    if f_unbound <= 0.0 or f_unbound > 1.0:
        raise ValueError('f_unbound must be in (0, 1]')
    if q_hepatic_l_per_h <= 0.0:
        raise ValueError('q_hepatic_l_per_h must be positive')
    if not pathways:
        raise ValueError('At least one EnzymePathway is required')
    inhibitors = inhibitors or []
    inhib_by_enzyme: dict[str, list[InhibitorTerm]] = {}
    for inh in inhibitors:
        inhib_by_enzyme.setdefault(inh.enzyme, []).append(inh)
    cl_int = 0.0
    cl_int_inhibited = 0.0
    pathway_contrib: dict[str, float] = {}
    for p in pathways:
        if p.km_mg_per_l <= 0.0 or p.vmax_mg_per_h <= 0.0:
            continue
        per_pathway = p.vmax_mg_per_h / p.km_mg_per_l
        cl_int += per_pathway
        inhib_sum = 0.0
        for inh in inhib_by_enzyme.get(p.enzyme, []):
            if inh.ki_mg_per_l > 0.0 and inh.unbound_concentration_mg_per_l > 0.0:
                inhib_sum += inh.unbound_concentration_mg_per_l / inh.ki_mg_per_l
        cl_int_inhibited += per_pathway / (1.0 + inhib_sum)
        pathway_contrib[p.enzyme] = per_pathway
    if cl_int > 0.0:
        pathway_contrib = {k: 100.0 * v / cl_int for k, v in pathway_contrib.items()}

    def well_stirred(cli: float) -> float:
        denom = q_hepatic_l_per_h + f_unbound * cli
        if denom <= 0.0:
            return 0.0
        return q_hepatic_l_per_h * f_unbound * cli / denom
    cl_h = well_stirred(cl_int)
    cl_h_inh = well_stirred(cl_int_inhibited)
    e_h = cl_h / q_hepatic_l_per_h
    e_h_inh = cl_h_inh / q_hepatic_l_per_h
    return HepaticExtractionResult(cl_intrinsic_l_per_h=cl_int, cl_intrinsic_inhibited_l_per_h=cl_int_inhibited, cl_hepatic_l_per_h=cl_h, cl_hepatic_inhibited_l_per_h=cl_h_inh, extraction_ratio=e_h, extraction_ratio_inhibited=e_h_inh, first_pass_fraction=1.0 - e_h, first_pass_fraction_inhibited=1.0 - e_h_inh, bioavailability_hepatic=1.0 - e_h, bioavailability_hepatic_inhibited=1.0 - e_h_inh, pathway_contributions=pathway_contrib, q_hepatic_l_per_h=q_hepatic_l_per_h, f_unbound=f_unbound, classification=classify_extraction(e_h))

@dataclass
class RegimenHepaticResult:
    per_drug: dict[str, HepaticExtractionResult] = field(default_factory=dict)

def compute_regimen_hepatic_extraction(drug_pathways: dict[str, list[EnzymePathway]], f_unbound: dict[str, float], inhibitor_plasma_mg_per_l: dict[str, float] | None=None, drug_inhibitor_targets: dict[str, list[tuple[str, float]]] | None=None, q_hepatic_l_per_h: float=DEFAULT_Q_HEPATIC_L_PER_H) -> RegimenHepaticResult:
    inhibitor_plasma_mg_per_l = inhibitor_plasma_mg_per_l or {}
    drug_inhibitor_targets = drug_inhibitor_targets or {}
    results: dict[str, HepaticExtractionResult] = {}
    for drug, pathways in drug_pathways.items():
        fu = f_unbound.get(drug, 0.2)
        targets: list[InhibitorTerm] = []
        for other, profile in drug_inhibitor_targets.items():
            if other == drug:
                continue
            c_other = inhibitor_plasma_mg_per_l.get(other, 0.0)
            if c_other <= 0.0:
                continue
            fu_other = f_unbound.get(other, 1.0)
            for enzyme, ki in profile:
                targets.append(InhibitorTerm(enzyme=enzyme, unbound_concentration_mg_per_l=fu_other * c_other, ki_mg_per_l=ki))
        results[drug] = compute_hepatic_clearance(pathways, fu, q_hepatic_l_per_h, targets)
    return RegimenHepaticResult(per_drug=results)
