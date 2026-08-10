from __future__ import annotations
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any
from sqlalchemy import or_
from sqlalchemy.orm import Session
from models import CYP450Profile, Interaction, Medication

@dataclass
class ResolvedInteraction:
    drug_a_id: int
    drug_b_id: int
    drug_a_name: str
    drug_b_name: str
    severity: str
    mechanism_type: str
    mechanism_detail: str
    clinical_effect: str
    recommendation: str
    evidence_level: str | None = None
    references: list[str] | None = None
    source: str = 'database'
SEVERITY_ORDER = ['critical', 'major', 'moderate', 'minor']

def _severity_rank(sev: str) -> int:
    try:
        return SEVERITY_ORDER.index(sev.lower())
    except ValueError:
        return len(SEVERITY_ORDER)
_CLASS_TAG_MAP: dict[str, set[str]] = {'SSRI': {'SSRI'}, 'SNRI': {'SNRI'}, 'MAOI': {'MAOI'}, 'TCA': {'TCA'}, 'Atypical Antipsychotic': {'ANTIPSYCHOTIC'}, 'Typical Antipsychotic': {'ANTIPSYCHOTIC'}, 'Benzodiazepine': {'BENZO'}, 'Opioid': {'OPIOID'}, 'Mood Stabilizer': {'MOOD_STABILIZER'}, 'ACE Inhibitor': {'ACE_I'}, 'NSAID': {'NSAID'}, 'Diuretic': {'DIURETIC'}, 'Anticonvulsant': {'ANTICONVULSANT'}, 'Anticholinergic': {'ANTICHOLINERGIC'}}
_NAME_TAG_MAP: dict[str, set[str]] = {'tramadol': {'TRAMADOL', 'OPIOID', 'SEROTONERGIC'}, 'meperidine': {'MEPERIDINE', 'OPIOID', 'SEROTONERGIC'}, 'lithium': {'LITHIUM', 'MOOD_STABILIZER'}, 'linezolid': {'LINEZOLID', 'SEROTONERGIC'}, 'sumatriptan': {'TRIPTAN'}, 'rizatriptan': {'TRIPTAN'}, 'zolmitriptan': {'TRIPTAN'}, 'naratriptan': {'TRIPTAN'}, 'almotriptan': {'TRIPTAN'}, 'eletriptan': {'TRIPTAN'}, 'frovatriptan': {'TRIPTAN'}}

def _tags_for(med: Medication) -> set[str]:
    tags: set[str] = set()
    dc = (med.drug_class or '').strip()
    if dc in _CLASS_TAG_MAP:
        tags |= _CLASS_TAG_MAP[dc]
    gn = (med.generic_name or '').strip().lower()
    if gn in _NAME_TAG_MAP:
        tags |= _NAME_TAG_MAP[gn]
    if dc in ('SSRI', 'SNRI', 'MAOI', 'TCA'):
        tags.add('SEROTONERGIC')
    if med.anticholinergic_potency and med.anticholinergic_potency >= 2:
        tags.add('HIGH_ACH')
    if med.cns_depression_risk and med.cns_depression_risk >= 1:
        tags.add('CNS_DEPRESSANT')
    return tags

def _serotonin_class_rules(a: Medication, b: Medication, ta: set[str], tb: set[str]) -> list[ResolvedInteraction]:
    results: list[ResolvedInteraction] = []

    def _add(sev: str, detail: str, effect: str, rec: str) -> None:
        results.append(ResolvedInteraction(drug_a_id=a.id, drug_b_id=b.id, drug_a_name=a.generic_name, drug_b_name=b.generic_name, severity=sev, mechanism_type='pharmacodynamic', mechanism_detail=detail, clinical_effect=effect, recommendation=rec, source='class_rule'))
    if {'SSRI'} & ta and {'MAOI'} & tb or ({'MAOI'} & ta and {'SSRI'} & tb):
        _add('critical', 'Combined serotonergic activity via SSRI + MAOI', 'Life-threatening serotonin syndrome', 'Absolutely contraindicated. Allow ≥14-day washout between agents.')
    if {'SNRI'} & ta and {'MAOI'} & tb or ({'MAOI'} & ta and {'SNRI'} & tb):
        _add('critical', 'Combined serotonergic activity via SNRI + MAOI', 'Life-threatening serotonin syndrome', 'Absolutely contraindicated. Allow ≥14-day washout between agents.')
    if {'MAOI'} & ta and {'MEPERIDINE'} & tb or ({'MEPERIDINE'} & ta and {'MAOI'} & tb):
        _add('critical', 'MAOI inhibition of meperidine metabolism + serotonergic synergy', 'Serotonin syndrome, hyperpyrexia, cardiovascular collapse', 'Absolutely contraindicated; use alternative opioid (morphine preferred).')
    if {'LINEZOLID'} & ta and {'SEROTONERGIC'} & tb or ({'SEROTONERGIC'} & ta and {'LINEZOLID'} & tb):
        _add('critical', 'Linezolid (reversible MAOI) + serotonergic agent', 'Serotonin syndrome risk', 'Avoid combination; if necessary, monitor closely for serotonin syndrome signs.')
    if {'SSRI'} & ta and {'SNRI'} & tb or ({'SNRI'} & ta and {'SSRI'} & tb):
        _add('major', 'Dual serotonin reuptake inhibition (SSRI + SNRI)', 'Increased serotonin syndrome risk', 'Avoid concurrent use; taper one agent before starting the other.')
    if {'SSRI'} & ta and {'TRAMADOL'} & tb or ({'TRAMADOL'} & ta and {'SSRI'} & tb):
        _add('major', 'SSRI serotonin reuptake inhibition + tramadol serotonergic activity', 'Elevated serotonin syndrome risk and lowered seizure threshold', 'Use alternative analgesic; if necessary, use lowest tramadol dose and monitor.')
    if {'SSRI'} & ta and {'TRIPTAN'} & tb or ({'TRIPTAN'} & ta and {'SSRI'} & tb):
        _add('moderate', 'SSRI + triptan 5-HT1 agonist serotonergic overlap', 'Potential serotonin syndrome (rare but documented)', 'Monitor for serotonin syndrome symptoms; generally manageable with clinical vigilance.')
    if {'SSRI'} & ta and {'LITHIUM'} & tb or ({'LITHIUM'} & ta and {'SSRI'} & tb):
        _add('moderate', 'SSRI-augmented serotonergic tone + lithium serotonin facilitation', 'Increased serotonin effects, possible serotonin syndrome or lithium toxicity', 'Monitor lithium levels and watch for serotonin syndrome symptoms.')
    return results

def _benzo_opioid_rule(a: Medication, b: Medication, ta: set[str], tb: set[str]) -> ResolvedInteraction | None:
    if {'BENZO'} & ta and {'OPIOID'} & tb or ({'OPIOID'} & ta and {'BENZO'} & tb):
        return ResolvedInteraction(drug_a_id=a.id, drug_b_id=b.id, drug_a_name=a.generic_name, drug_b_name=b.generic_name, severity='critical', mechanism_type='pharmacodynamic', mechanism_detail='Additive CNS and respiratory depression (benzodiazepine + opioid)', clinical_effect='Profound sedation, respiratory depression, coma, death', recommendation='FDA Black Box Warning: avoid concurrent use unless no alternatives. Use lowest effective doses and shortest duration.', source='class_rule')
    return None

def _lithium_rules(a: Medication, b: Medication, ta: set[str], tb: set[str]) -> list[ResolvedInteraction]:
    results: list[ResolvedInteraction] = []
    pairs = [({'LITHIUM'}, {'ACE_I'}, 'ACE inhibitor reduces renal lithium clearance', 'Lithium toxicity risk (tremor, confusion, renal impairment)', 'Monitor lithium levels closely; consider 25-50 % dose reduction.'), ({'LITHIUM'}, {'NSAID'}, 'NSAIDs reduce renal prostaglandins → decreased lithium clearance', 'Elevated lithium levels and toxicity risk', 'Avoid chronic NSAID use; if needed, monitor lithium levels frequently.'), ({'LITHIUM'}, {'DIURETIC'}, 'Diuretic-induced sodium/volume depletion increases lithium reabsorption', 'Lithium toxicity risk', 'Monitor lithium levels; maintain adequate hydration and sodium intake.')]
    for tag_x, tag_y, detail, effect, rec in pairs:
        if tag_x & ta and tag_y & tb or (tag_y & ta and tag_x & tb):
            results.append(ResolvedInteraction(drug_a_id=a.id, drug_b_id=b.id, drug_a_name=a.generic_name, drug_b_name=b.generic_name, severity='major', mechanism_type='pharmacokinetic', mechanism_detail=detail, clinical_effect=effect, recommendation=rec, source='lithium'))
    return results

def _antipsychotic_anticholinergic(a: Medication, b: Medication, ta: set[str], tb: set[str]) -> ResolvedInteraction | None:
    if {'ANTIPSYCHOTIC'} & ta and {'HIGH_ACH'} & tb or ({'HIGH_ACH'} & ta and {'ANTIPSYCHOTIC'} & tb):
        return ResolvedInteraction(drug_a_id=a.id, drug_b_id=b.id, drug_a_name=a.generic_name, drug_b_name=b.generic_name, severity='moderate', mechanism_type='pharmacodynamic', mechanism_detail='Antipsychotic + high-anticholinergic drug additive ACh blockade', clinical_effect='Cognitive impairment, constipation, urinary retention, delirium (especially elderly)', recommendation='Minimise anticholinergic burden; consider alternatives with lower ACh load.', source='class_rule')
    return None

def _qtc_additive(a: Medication, b: Medication) -> ResolvedInteraction | None:
    if a.qtc_prolongation_risk and b.qtc_prolongation_risk:
        return ResolvedInteraction(drug_a_id=a.id, drug_b_id=b.id, drug_a_name=a.generic_name, drug_b_name=b.generic_name, severity='major', mechanism_type='pharmacodynamic', mechanism_detail='Additive QTc prolongation from two QTc-prolonging agents', clinical_effect='Increased risk of Torsades de Pointes and sudden cardiac death', recommendation='Obtain baseline and periodic ECGs; correct electrolytes; consider alternatives with lower QTc risk.', source='additive_qtc')
    return None

def _cns_multi_sedation(meds: list[Medication]) -> list[ResolvedInteraction]:
    results: list[ResolvedInteraction] = []
    sedating = [m for m in meds if (m.cns_depression_risk or 0) >= 2]
    for a, b in combinations(sedating, 2):
        results.append(ResolvedInteraction(drug_a_id=a.id, drug_b_id=b.id, drug_a_name=a.generic_name, drug_b_name=b.generic_name, severity='moderate', mechanism_type='pharmacodynamic', mechanism_detail=f'Additive CNS depression: {a.generic_name} (score {a.cns_depression_risk}) + {b.generic_name} (score {b.cns_depression_risk})', clinical_effect='Excessive sedation, psychomotor impairment, falls risk', recommendation='Use lowest effective doses; counsel patient about sedation and driving.', source='cns_sedation'))
    return results

def _cyp450_derived(db: Session, a: Medication, b: Medication, cyp2d6: str, cyp2c19: str) -> list[ResolvedInteraction]:
    profiles_a: list[CYP450Profile] = db.query(CYP450Profile).filter(CYP450Profile.medication_id == a.id).all()
    profiles_b: list[CYP450Profile] = db.query(CYP450Profile).filter(CYP450Profile.medication_id == b.id).all()
    results: list[ResolvedInteraction] = []
    for pa in profiles_a:
        for pb in profiles_b:
            if pa.enzyme != pb.enzyme:
                continue
            enzyme = pa.enzyme
            inhibitor, substrate = (None, None)
            if pa.role == 'inhibitor' and pb.role == 'substrate':
                inhibitor, substrate = (pa, pb)
                inh_med, sub_med = (a, b)
            elif pb.role == 'inhibitor' and pa.role == 'substrate':
                inhibitor, substrate = (pb, pa)
                inh_med, sub_med = (b, a)
            elif pa.role == 'inducer' and pb.role == 'substrate':
                results.append(ResolvedInteraction(drug_a_id=a.id, drug_b_id=b.id, drug_a_name=a.generic_name, drug_b_name=b.generic_name, severity='moderate', mechanism_type='pharmacokinetic', mechanism_detail=f'{a.generic_name} induces {enzyme}, increasing metabolism of {b.generic_name}', clinical_effect=f'Reduced {b.generic_name} plasma levels; possible therapeutic failure', recommendation=f'Monitor {b.generic_name} efficacy; dose increase may be needed.', source='cyp450'))
                continue
            elif pb.role == 'inducer' and pa.role == 'substrate':
                results.append(ResolvedInteraction(drug_a_id=a.id, drug_b_id=b.id, drug_a_name=a.generic_name, drug_b_name=b.generic_name, severity='moderate', mechanism_type='pharmacokinetic', mechanism_detail=f'{b.generic_name} induces {enzyme}, increasing metabolism of {a.generic_name}', clinical_effect=f'Reduced {a.generic_name} plasma levels; possible therapeutic failure', recommendation=f'Monitor {a.generic_name} efficacy; dose increase may be needed.', source='cyp450'))
                continue
            else:
                continue
            potency = (inhibitor.potency or 'moderate').lower()
            sev = 'major' if potency == 'strong' else 'moderate'
            if enzyme == 'CYP2D6' and cyp2d6 == 'poor' and (potency == 'strong'):
                sev = 'critical'
            if enzyme == 'CYP2C19' and cyp2c19 == 'poor' and (potency == 'strong'):
                sev = 'critical'
            fraction_note = ''
            if substrate.fraction_metabolized:
                fraction_note = f' ({float(substrate.fraction_metabolized) * 100:.0f}% metabolised via {enzyme})'
            results.append(ResolvedInteraction(drug_a_id=a.id, drug_b_id=b.id, drug_a_name=a.generic_name, drug_b_name=b.generic_name, severity=sev, mechanism_type='pharmacokinetic', mechanism_detail=f'{inh_med.generic_name} ({potency} {enzyme} inhibitor) inhibits metabolism of {sub_med.generic_name}{fraction_note}', clinical_effect=f'Elevated {sub_med.generic_name} plasma levels; increased risk of dose-dependent adverse effects', recommendation=f'Consider {sub_med.generic_name} dose reduction or alternative not metabolised via {enzyme}.', source='cyp450'))
    return results

def _load_db_interactions(db: Session, medication_ids: list[int]) -> list[ResolvedInteraction]:
    rows = db.query(Interaction).filter(or_(Interaction.drug_a_id.in_(medication_ids) & Interaction.drug_b_id.in_(medication_ids), Interaction.drug_b_id.in_(medication_ids) & Interaction.drug_a_id.in_(medication_ids))).all()
    results: list[ResolvedInteraction] = []
    for row in rows:
        a_name = row.drug_a.generic_name if row.drug_a else f'med#{row.drug_a_id}'
        b_name = row.drug_b.generic_name if row.drug_b else f'med#{row.drug_b_id}'
        results.append(ResolvedInteraction(drug_a_id=row.drug_a_id, drug_b_id=row.drug_b_id, drug_a_name=a_name, drug_b_name=b_name, severity=row.severity, mechanism_type=row.mechanism_type, mechanism_detail=row.mechanism_detail, clinical_effect=row.clinical_effect, recommendation=row.recommendation, evidence_level=row.evidence_level, references=row.literature_references, source='database'))
    return results

def _pair_key(r: ResolvedInteraction) -> tuple[int, int]:
    return (min(r.drug_a_id, r.drug_b_id), max(r.drug_a_id, r.drug_b_id))

def _dedup_key(r: ResolvedInteraction) -> tuple:
    return (_pair_key(r), r.severity, r.mechanism_detail[:80])

def resolve_regimen_interactions(db: Session, medication_ids: list[int], cyp2d6_phenotype: str='normal', cyp2c19_phenotype: str='normal') -> list[dict[str, Any]]:
    if len(medication_ids) < 2:
        return []
    meds: list[Medication] = db.query(Medication).filter(Medication.id.in_(medication_ids)).all()
    med_by_id = {m.id: m for m in meds}
    all_interactions: list[ResolvedInteraction] = []
    all_interactions.extend(_load_db_interactions(db, medication_ids))
    tag_cache: dict[int, set[str]] = {m.id: _tags_for(m) for m in meds}
    for a, b in combinations(meds, 2):
        ta, tb = (tag_cache[a.id], tag_cache[b.id])
        all_interactions.extend(_serotonin_class_rules(a, b, ta, tb))
        benzo = _benzo_opioid_rule(a, b, ta, tb)
        if benzo:
            all_interactions.append(benzo)
        all_interactions.extend(_lithium_rules(a, b, ta, tb))
        ach = _antipsychotic_anticholinergic(a, b, ta, tb)
        if ach:
            all_interactions.append(ach)
        qtc = _qtc_additive(a, b)
        if qtc:
            all_interactions.append(qtc)
        all_interactions.extend(_cyp450_derived(db, a, b, cyp2d6_phenotype, cyp2c19_phenotype))
    all_interactions.extend(_cns_multi_sedation(meds))
    seen: set[tuple] = set()
    unique: list[ResolvedInteraction] = []
    for r in all_interactions:
        key = _dedup_key(r)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda r: _severity_rank(r.severity))
    return [{'drug_a_id': r.drug_a_id, 'drug_b_id': r.drug_b_id, 'drug_a_name': r.drug_a_name, 'drug_b_name': r.drug_b_name, 'severity': r.severity, 'mechanism_type': r.mechanism_type, 'mechanism_detail': r.mechanism_detail, 'clinical_effect': r.clinical_effect, 'recommendation': r.recommendation, 'evidence_level': r.evidence_level, 'references': r.references, 'source': r.source} for r in unique]
