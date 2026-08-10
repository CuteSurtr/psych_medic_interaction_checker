from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Text, cast, func, or_
from sqlalchemy.orm import Session
from database.connection import get_db
from models import CYP450Profile, Medication
router = APIRouter(prefix='/api/medications', tags=['medications'])

@router.get('/search')
def search_medications(q: str=Query('', min_length=0), db: Session=Depends(get_db)) -> list[dict[str, Any]]:
    q = (q or '').strip()
    if not q:
        return []
    like = f'%{q.lower()}%'
    # Cast rather than array_to_string, which is PostgreSQL-only. The text form
    # is `{Prozac,Sarafem}` on PostgreSQL and `["Prozac", "Sarafem"]` on SQLite;
    # a substring match finds the brand either way.
    brand_match = func.coalesce(cast(Medication.brand_names, Text), '').ilike(like)
    rows = db.query(Medication).filter(or_(Medication.generic_name.ilike(like), brand_match)).order_by(Medication.generic_name).limit(25).all()
    return [{'id': m.id, 'generic_name': m.generic_name, 'brand_names': m.brand_names or [], 'drug_class': m.drug_class, 'sub_class': m.sub_class} for m in rows]

@router.get('/classes')
def list_classes(db: Session=Depends(get_db)) -> list[str]:
    rows = db.query(Medication.drug_class).distinct().order_by(Medication.drug_class).all()
    return [r[0] for r in rows if r[0]]

def _med_to_dict(m: Medication, cyp: list[CYP450Profile]) -> dict[str, Any]:
    return {'id': m.id, 'generic_name': m.generic_name, 'brand_names': m.brand_names or [], 'drug_class': m.drug_class, 'sub_class': m.sub_class, 'bioavailability': float(m.bioavailability) if m.bioavailability else None, 'volume_of_distribution_l': float(m.volume_of_distribution_l) if m.volume_of_distribution_l else None, 'clearance_l_per_h': float(m.clearance_l_per_h) if m.clearance_l_per_h else None, 'half_life_hours': float(m.half_life_hours) if m.half_life_hours is not None else None, 'absorption_rate_constant': float(m.absorption_rate_constant) if m.absorption_rate_constant else None, 'tmax_hours': float(m.tmax_hours) if m.tmax_hours else None, 'protein_binding_pct': float(m.protein_binding_pct) if m.protein_binding_pct else None, 'therapeutic_min_ng_ml': float(m.therapeutic_min_ng_ml) if m.therapeutic_min_ng_ml else None, 'therapeutic_max_ng_ml': float(m.therapeutic_max_ng_ml) if m.therapeutic_max_ng_ml else None, 'toxic_threshold_ng_ml': float(m.toxic_threshold_ng_ml) if m.toxic_threshold_ng_ml else None, 'has_active_metabolite': m.has_active_metabolite, 'metabolite_name': m.metabolite_name, 'metabolite_half_life_hours': float(m.metabolite_half_life_hours) if m.metabolite_half_life_hours else None, 'qtc_prolongation_risk': m.qtc_prolongation_risk, 'anticholinergic_potency': m.anticholinergic_potency, 'serotonergic_potency': m.serotonergic_potency, 'cns_depression_risk': m.cns_depression_risk, 'beers_criteria_flag': m.beers_criteria_flag, 'fda_pregnancy_category': m.fda_pregnancy_category, 'common_dose_range': m.common_dose_range, 'typical_start_dose_mg': float(m.typical_start_dose_mg) if m.typical_start_dose_mg else None, 'max_dose_mg': float(m.max_dose_mg) if m.max_dose_mg else None, 'dosing_frequency': m.dosing_frequency, 'notes': m.notes, 'cyp450': [{'enzyme': c.enzyme, 'relationship': c.role, 'potency': c.potency, 'fraction_metabolized': float(c.fraction_metabolized) if c.fraction_metabolized else None, 'ki_nm': float(c.ki_nm) if c.ki_nm else None} for c in cyp]}

@router.get('/{med_id}')
def get_medication(med_id: int, db: Session=Depends(get_db)) -> dict[str, Any]:
    m = db.query(Medication).filter(Medication.id == med_id).first()
    if not m:
        raise HTTPException(status_code=404, detail='Medication not found')
    cyp = db.query(CYP450Profile).filter(CYP450Profile.medication_id == m.id).all()
    return _med_to_dict(m, cyp)

@router.get('/{med_id}/pk-parameters')
def get_pk_parameters(med_id: int, db: Session=Depends(get_db)) -> dict[str, Any]:
    m = db.query(Medication).filter(Medication.id == med_id).first()
    if not m:
        raise HTTPException(status_code=404, detail='Medication not found')
    return {'id': m.id, 'generic_name': m.generic_name, 'bioavailability': float(m.bioavailability) if m.bioavailability else None, 'volume_of_distribution_l': float(m.volume_of_distribution_l) if m.volume_of_distribution_l else None, 'clearance_l_per_h': float(m.clearance_l_per_h) if m.clearance_l_per_h else None, 'half_life_hours': float(m.half_life_hours) if m.half_life_hours is not None else None, 'absorption_rate_constant': float(m.absorption_rate_constant) if m.absorption_rate_constant else None, 'therapeutic_min_ng_ml': float(m.therapeutic_min_ng_ml) if m.therapeutic_min_ng_ml else None, 'therapeutic_max_ng_ml': float(m.therapeutic_max_ng_ml) if m.therapeutic_max_ng_ml else None, 'toxic_threshold_ng_ml': float(m.toxic_threshold_ng_ml) if m.toxic_threshold_ng_ml else None, 'has_active_metabolite': m.has_active_metabolite, 'metabolite_name': m.metabolite_name, 'metabolite_half_life_hours': float(m.metabolite_half_life_hours) if m.metabolite_half_life_hours else None, 'metabolite_formation_fraction': float(m.metabolite_formation_fraction) if m.metabolite_formation_fraction else None}
