from __future__ import annotations
from typing import Any

def _severity_rank(sev: str) -> int:
    order = ['critical', 'major', 'moderate', 'minor']
    try:
        return order.index(sev.lower())
    except ValueError:
        return len(order)

def top_interaction(interactions: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not interactions:
        return None
    return min(interactions, key=lambda i: _severity_rank(i.get('severity', 'minor')))

def serotonin_risk_score(meds: list[Any]) -> str:
    reuptake_inhibitors: list[str] = []
    mao_inhibitors: list[str] = []
    releasers: list[str] = []
    receptor_agonists: list[str] = []
    for m in meds:
        dc = (getattr(m, 'drug_class', '') or '').upper()
        gn = (getattr(m, 'generic_name', '') or '').lower()
        if dc in ('SSRI', 'SNRI'):
            reuptake_inhibitors.append(gn)
        elif dc == 'TCA':
            reuptake_inhibitors.append(gn)
        elif dc == 'MAOI':
            mao_inhibitors.append(gn)
        if gn == 'tramadol':
            reuptake_inhibitors.append(gn)
        if gn == 'linezolid':
            mao_inhibitors.append(gn)
        if gn in ('buspirone',):
            receptor_agonists.append(gn)
        if gn in ('lisdexamfetamine', 'amphetamine', 'methamphetamine'):
            releasers.append(gn)
    if mao_inhibitors and (reuptake_inhibitors or releasers):
        return 'Critical'
    mechanism_count = sum((1 for bucket in [reuptake_inhibitors, mao_inhibitors, releasers, receptor_agonists] if bucket))
    if len(reuptake_inhibitors) >= 2:
        return 'High'
    if mechanism_count >= 2:
        return 'High'
    total_potency = sum((getattr(m, 'serotonergic_potency', 0) or 0 for m in meds))
    if total_potency >= 3 and len(meds) >= 2:
        return 'Moderate'
    if mechanism_count >= 1:
        return 'Low'
    return 'None'
QTC_TIERS: dict[str, str] = {'thioridazine': 'high', 'ziprasidone': 'high', 'methadone': 'high', 'droperidol': 'high', 'haloperidol': 'moderate', 'chlorpromazine': 'moderate', 'citalopram': 'moderate', 'escitalopram': 'moderate', 'amitriptyline': 'moderate', 'nortriptyline': 'moderate', 'imipramine': 'moderate', 'clomipramine': 'moderate', 'quetiapine': 'low', 'risperidone': 'low', 'olanzapine': 'low', 'fluoxetine': 'low', 'sertraline': 'low', 'mirtazapine': 'low'}

def qtc_risk_score(meds: list[Any]) -> str:
    high_agents: list[str] = []
    moderate_agents: list[str] = []
    low_agents: list[str] = []
    for m in meds:
        gn = (getattr(m, 'generic_name', '') or '').lower()
        tier = QTC_TIERS.get(gn)
        if tier == 'high':
            high_agents.append(gn)
        elif tier == 'moderate':
            moderate_agents.append(gn)
        elif tier == 'low':
            low_agents.append(gn)
        elif getattr(m, 'qtc_prolongation_risk', False):
            moderate_agents.append(gn)
    if len(high_agents) >= 2:
        return 'Critical'
    if high_agents and moderate_agents:
        return 'High'
    if len(moderate_agents) >= 2:
        return 'Moderate'
    if high_agents or moderate_agents:
        return 'Low'
    if len(low_agents) >= 3:
        return 'Low'
    return 'None'

def anticholinergic_burden(meds: list[Any]) -> int:
    return sum((getattr(m, 'anticholinergic_potency', 0) or 0 for m in meds))

def cns_depression_risk(meds: list[Any]) -> str:
    total = sum((getattr(m, 'cns_depression_risk', 0) or 0 for m in meds))
    if total >= 6:
        return 'High'
    if total >= 3:
        return 'Moderate'
    return 'Low'

def _contextual_notes(meds: list[Any], age: int | None, smoking: bool, egfr: float | None, hepatic: str, pregnancy: bool) -> list[str]:
    notes: list[str] = []
    if age is not None and age > 65:
        beers_flagged = [m.generic_name for m in meds if getattr(m, 'beers_criteria_flag', False)]
        if beers_flagged:
            notes.append(f"Patient >65 y/o: Beers Criteria flagged medications — {', '.join(beers_flagged)}. Review appropriateness.")
        else:
            notes.append('Patient >65 y/o: review all sedating/anticholinergic agents per Beers Criteria.')
    if smoking:
        cyp1a2_substrates = [m.generic_name for m in meds if hasattr(m, 'cyp450_profiles') and any((getattr(p, 'role', '') == 'substrate' and getattr(p, 'enzyme', '') == 'CYP1A2' for p in m.cyp450_profiles or []))]
        if cyp1a2_substrates:
            notes.append(f"Smoking induces CYP1A2: may reduce levels of {', '.join(cyp1a2_substrates)}. Monitor efficacy or increase dose.")
    if egfr is not None and egfr < 60:
        lithium_present = any(((getattr(m, 'generic_name', '') or '').lower() == 'lithium' for m in meds))
        if lithium_present:
            notes.append(f'eGFR {egfr:.0f} mL/min: impaired lithium clearance — reduce dose and monitor levels more frequently.')
        else:
            notes.append(f'eGFR {egfr:.0f} mL/min: consider renal dose adjustments for renally-cleared medications.')
    if hepatic and hepatic.lower() not in ('none', ''):
        notes.append(f'Hepatic impairment ({hepatic}): reduce doses of hepatically metabolised medications; monitor LFTs.')
    if pregnancy:
        categories = {m.generic_name: getattr(m, 'fda_pregnancy_category', 'N/A') or 'N/A' for m in meds}
        risky = [f'{name} (Cat {cat})' for name, cat in categories.items() if cat.upper() in ('D', 'X')]
        if risky:
            notes.append(f"Pregnancy: high-risk categories — {', '.join(risky)}. Re-evaluate necessity and consider safer alternatives.")
        else:
            notes.append('Pregnancy: review all medications for teratogenic risk; consult current FDA/TGA guidance.')
    return notes

def compute_risk_summary(db: Any, medication_ids: list[int], age: int | None=None, smoking: bool=False, egfr: float | None=None, hepatic: str='none', pregnancy: bool=False, cyp2d6: str='normal', cyp2c19: str='normal') -> dict[str, Any]:
    from models import Medication
    from services.interaction_engine import resolve_regimen_interactions
    interactions = resolve_regimen_interactions(db, medication_ids, cyp2d6_phenotype=cyp2d6, cyp2c19_phenotype=cyp2c19)
    meds: list[Medication] = db.query(Medication).filter(Medication.id.in_(medication_ids)).all()
    counts: dict[str, int] = {'critical': 0, 'major': 0, 'moderate': 0, 'minor': 0}
    for ix in interactions:
        sev = ix.get('severity', 'minor').lower()
        if sev in counts:
            counts[sev] += 1
    top = top_interaction(interactions)
    return {'interactions': interactions, 'counts_by_severity': counts, 'top_risk': top, 'serotonin_risk': serotonin_risk_score(meds), 'qtc_risk': qtc_risk_score(meds), 'anticholinergic_burden': anticholinergic_burden(meds), 'cns_depression_risk': cns_depression_risk(meds), 'contextual_notes': _contextual_notes(meds, age, smoking, egfr, hepatic, pregnancy)}
