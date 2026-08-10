from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database.connection import get_db
router = APIRouter(prefix='/api/analysis', tags=['analysis'])

def _load_regimen_data(db: Session, medication_ids: list[int]) -> dict:
    from models import CYP450Profile, Interaction, Medication
    meds = db.query(Medication).filter(Medication.id.in_(medication_ids)).all()
    med_map = {m.id: m for m in meds}
    drug_names = [med_map[mid].generic_name for mid in medication_ids if mid in med_map]
    name_set = set(drug_names)
    interactions_raw = db.query(Interaction).filter(Interaction.drug_a_id.in_(medication_ids), Interaction.drug_b_id.in_(medication_ids)).all()
    interactions = []
    for ix in interactions_raw:
        a_name = med_map.get(ix.drug_a_id, None)
        b_name = med_map.get(ix.drug_b_id, None)
        if a_name and b_name:
            interactions.append({'drug_a_name': a_name.generic_name, 'drug_b_name': b_name.generic_name, 'severity': ix.severity, 'mechanism_type': ix.mechanism_type})
    cyp_profiles_raw = db.query(CYP450Profile).filter(CYP450Profile.medication_id.in_(medication_ids)).all()
    cyp_profiles = []
    enzyme_substrate_data = []
    for cp in cyp_profiles_raw:
        med = med_map.get(cp.medication_id)
        if not med:
            continue
        cyp_profiles.append({'drug_name': med.generic_name, 'enzyme': cp.enzyme, 'role': cp.role, 'potency': cp.potency or 'moderate', 'fraction_metabolized': float(cp.fraction_metabolized or 0.5)})
        if cp.role == 'substrate' and cp.vmax_nmol_per_h:
            enzyme_substrate_data.append({'drug_name': med.generic_name, 'enzyme': cp.enzyme, 'vmax': float(cp.vmax_nmol_per_h), 'km': float(cp.km_nm or 1000), 'fraction_metabolized': float(cp.fraction_metabolized or 0.5)})
    return {'drug_names': drug_names, 'interactions': interactions, 'cyp_profiles': cyp_profiles, 'enzyme_substrate_data': enzyme_substrate_data}

@router.get('/graph-metrics')
def get_graph_metrics(medication_ids: str=Query(..., description='Comma-separated medication IDs'), db: Session=Depends(get_db)) -> dict[str, Any]:
    from services.graph_analysis import InteractionGraphAnalyzer
    ids = [int(x.strip()) for x in medication_ids.split(',') if x.strip()]
    if len(ids) < 2:
        raise HTTPException(400, 'At least 2 medication IDs required.')
    data = _load_regimen_data(db, ids)
    analyzer = InteractionGraphAnalyzer(data['drug_names'], data['interactions'])
    metrics = analyzer.compute_all()
    return {'drug_names': metrics.drug_names, 'adjacency_matrix': metrics.adjacency_matrix, 'laplacian_eigenvalues': metrics.laplacian_eigenvalues, 'fiedler_value': metrics.fiedler_value, 'fiedler_vector': metrics.fiedler_vector, 'spectral_radius': metrics.spectral_radius, 'perron_vector': metrics.perron_vector, 'chromatic_number': metrics.chromatic_number, 'independence_number': metrics.independence_number, 'max_safe_subset': metrics.max_safe_subset, 'bridge_drug': metrics.bridge_drug, 'independence_polynomial_coefficients': metrics.independence_polynomial_coefficients}

@router.get('/bipartite-metrics')
def get_bipartite_metrics(medication_ids: str=Query(..., description='Comma-separated medication IDs'), db: Session=Depends(get_db)) -> dict[str, Any]:
    from services.bipartite_analysis import CYP450BipartiteAnalyzer
    ids = [int(x.strip()) for x in medication_ids.split(',') if x.strip()]
    if len(ids) < 1:
        raise HTTPException(400, 'At least 1 medication ID required.')
    data = _load_regimen_data(db, ids)
    analyzer = CYP450BipartiteAnalyzer(data['drug_names'], data['cyp_profiles'])
    metrics = analyzer.compute_all()
    return {'drug_names': metrics.drug_names, 'enzyme_names': metrics.enzyme_names, 'biadjacency_matrix': metrics.biadjacency_matrix, 'singular_values': metrics.singular_values, 'drug_clusters': metrics.drug_clusters, 'enzyme_clusters': metrics.enzyme_clusters, 'conflicts_per_enzyme': metrics.conflicts_per_enzyme, 'total_conflicts': metrics.total_conflicts, 'minimum_cover': metrics.minimum_cover, 'cover_resolves_n_conflicts': metrics.cover_resolves_n_conflicts}

@router.get('/metabolic-flow')
def get_metabolic_flow(medication_ids: str=Query(..., description='Comma-separated medication IDs'), db: Session=Depends(get_db)) -> dict[str, Any]:
    from services.flow_analysis import MetabolicFlowAnalyzer
    ids = [int(x.strip()) for x in medication_ids.split(',') if x.strip()]
    if len(ids) < 1:
        raise HTTPException(400, 'At least 1 medication ID required.')
    data = _load_regimen_data(db, ids)
    analyzer = MetabolicFlowAnalyzer(data['drug_names'], data['enzyme_substrate_data'])
    metrics = analyzer.compute_all()
    return {'max_flow': metrics.max_flow_value, 'bottleneck_enzyme': metrics.bottleneck_enzyme, 'bottleneck_utilization_pct': metrics.bottleneck_utilization_pct, 'enzyme_utilizations': metrics.enzyme_utilizations, 'min_cut_edges': metrics.min_cut_edges}

@router.get('/combinatorics')
def get_combinatorics(medication_ids: str=Query(..., description='Comma-separated medication IDs'), db: Session=Depends(get_db)) -> dict[str, Any]:
    from services.combinatorial_analysis import PolypharmacyCombinatorics
    ids = [int(x.strip()) for x in medication_ids.split(',') if x.strip()]
    data = _load_regimen_data(db, ids)
    analyzer = PolypharmacyCombinatorics(data['drug_names'])
    metrics = analyzer.compute_all(formulary_size=50)
    return {'n_drugs': metrics.n_drugs, 'pairwise_checks': metrics.pairwise_checks, 'triple_checks': metrics.triple_checks, 'detected_three_drug_interactions': metrics.detected_three_drug_interactions, 'conflict_probability_pct': metrics.conflict_probability_pct}
