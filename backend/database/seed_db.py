from database.connection import Base, SessionLocal, engine
from database.seed_data import CYP_ROWS, INTERACTION_ROWS, MEDICATION_ROWS
from models import CYP450Profile, Interaction, Medication
_MEDICATION_FIELDS = ('generic_name', 'brand_names', 'drug_class', 'sub_class', 'bioavailability', 'volume_of_distribution_l', 'clearance_l_per_h', 'half_life_hours', 'absorption_rate_constant', 'tmax_hours', 'protein_binding_pct', 'cl_cv_pct', 'vd_cv_pct', 'therapeutic_min_ng_ml', 'therapeutic_max_ng_ml', 'toxic_threshold_ng_ml', 'has_active_metabolite', 'metabolite_name', 'metabolite_half_life_hours', 'metabolite_formation_fraction', 'qtc_prolongation_risk', 'anticholinergic_potency', 'serotonergic_potency', 'cns_depression_risk', 'beers_criteria_flag', 'fda_pregnancy_category', 'common_dose_range', 'typical_start_dose_mg', 'max_dose_mg', 'dosing_frequency', 'notes')

def create_tables() -> None:
    Base.metadata.create_all(bind=engine)

def seed_if_empty() -> None:
    db = SessionLocal()
    try:
        if db.query(Medication).count() == 0:
            _seed_medications(db)
            _seed_cyp(db)
            _seed_interactions(db)
            db.commit()
    finally:
        db.close()

def _seed_medications(db) -> None:
    for row in MEDICATION_ROWS:
        med = Medication(**dict(zip(_MEDICATION_FIELDS, row)))
        db.add(med)
    db.flush()

def _seed_cyp(db) -> None:
    name_to_id: dict[str, int] = {m.generic_name: m.id for m in db.query(Medication).all()}
    for name, enzyme, role, potency, frac, ki, vmax, km in CYP_ROWS:
        profile = CYP450Profile(medication_id=name_to_id[name], enzyme=enzyme, role=role, potency=potency, fraction_metabolized=frac, ki_nm=ki, vmax_nmol_per_h=vmax, km_nm=km)
        db.add(profile)
    db.flush()

def _seed_interactions(db) -> None:
    name_to_id: dict[str, int] = {m.generic_name: m.id for m in db.query(Medication).all()}
    seen: set[tuple[int, int]] = set()
    for a, b, sev, mech_type, mech_detail, clin, rec, evid in INTERACTION_ROWS:
        id_a, id_b = (name_to_id[a], name_to_id[b])
        key = (min(id_a, id_b), max(id_a, id_b))
        if key in seen:
            continue
        seen.add(key)
        interaction = Interaction(drug_a_id=id_a, drug_b_id=id_b, severity=sev, mechanism_type=mech_type, mechanism_detail=mech_detail, clinical_effect=clin, recommendation=rec, evidence_level=evid)
        db.add(interaction)
    db.flush()
