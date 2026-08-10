from __future__ import annotations
from typing import Any
from sqlalchemy.orm import Session
from models import CYP450Profile, Medication
from services.constants import TRACKED_ENZYMES as ENZYMES

def _phenotype_note(enzyme: str, phenotype: str) -> str | None:
    if phenotype == 'normal':
        return None
    labels = {'poor': 'Poor metaboliser — significantly reduced enzyme activity', 'intermediate': 'Intermediate metaboliser — moderately reduced activity', 'rapid': 'Rapid metaboliser — increased enzyme activity', 'ultrarapid': 'Ultra-rapid metaboliser — markedly increased activity', 'ultra-rapid': 'Ultra-rapid metaboliser — markedly increased activity'}
    desc = labels.get(phenotype.lower(), f'Non-standard phenotype: {phenotype}')
    return f'{enzyme} {desc}'

def analyze_cyp450(db: Session, medication_ids: list[int], cyp2d6_phenotype: str='normal', cyp2c19_phenotype: str='normal') -> dict[str, Any]:
    meds: list[Medication] = db.query(Medication).filter(Medication.id.in_(medication_ids)).all()
    med_map: dict[int, Medication] = {m.id: m for m in meds}
    profiles: list[CYP450Profile] = db.query(CYP450Profile).filter(CYP450Profile.medication_id.in_(medication_ids)).all()
    enzymes_data: dict[str, dict[str, list[dict[str, Any]]]] = {enz: {'substrates': [], 'inhibitors': [], 'inducers': []} for enz in ENZYMES}
    for p in profiles:
        enz = p.enzyme
        if enz not in enzymes_data:
            enzymes_data[enz] = {'substrates': [], 'inhibitors': [], 'inducers': []}
        med = med_map.get(p.medication_id)
        entry = {'medication_id': p.medication_id, 'generic_name': med.generic_name if med else f'med#{p.medication_id}', 'potency': p.potency, 'fraction_metabolized': float(p.fraction_metabolized) if p.fraction_metabolized is not None else None}
        role = (p.role or '').lower()
        if role == 'substrate':
            enzymes_data[enz]['substrates'].append(entry)
        elif role == 'inhibitor':
            enzymes_data[enz]['inhibitors'].append(entry)
        elif role == 'inducer':
            enzymes_data[enz]['inducers'].append(entry)
    conflicts: list[dict[str, Any]] = []
    for enz, buckets in enzymes_data.items():
        inhibitors = buckets['inhibitors']
        inducers = buckets['inducers']
        substrates = buckets['substrates']
        for inh in inhibitors:
            for sub in substrates:
                if inh['medication_id'] == sub['medication_id']:
                    continue
                potency = (inh['potency'] or 'moderate').lower()
                sev = 'major' if potency == 'strong' else 'moderate'
                if enz == 'CYP2D6' and cyp2d6_phenotype == 'poor' and (potency == 'strong'):
                    sev = 'critical'
                if enz == 'CYP2C19' and cyp2c19_phenotype == 'poor' and (potency == 'strong'):
                    sev = 'critical'
                conflicts.append({'enzyme': enz, 'type': 'inhibition', 'detail': f"{inh['generic_name']} ({potency} inhibitor) inhibits {enz} metabolism of {sub['generic_name']}", 'severity': sev})
        for ind in inducers:
            for sub in substrates:
                if ind['medication_id'] == sub['medication_id']:
                    continue
                conflicts.append({'enzyme': enz, 'type': 'induction', 'detail': f"{ind['generic_name']} induces {enz}, increasing clearance of {sub['generic_name']}", 'severity': 'moderate'})
        if len(substrates) >= 2:
            names = [s['generic_name'] for s in substrates]
            conflicts.append({'enzyme': enz, 'type': 'competition', 'detail': f"Substrate competition on {enz}: {', '.join(names)} — may alter metabolism unpredictably", 'severity': 'minor'})
    severity_order = {'critical': 0, 'major': 1, 'moderate': 2, 'minor': 3}
    conflicts.sort(key=lambda c: severity_order.get(c['severity'], 4))
    phenotypes: dict[str, Any] = {'cyp2d6': {'phenotype': cyp2d6_phenotype, 'note': _phenotype_note('CYP2D6', cyp2d6_phenotype)}, 'cyp2c19': {'phenotype': cyp2c19_phenotype, 'note': _phenotype_note('CYP2C19', cyp2c19_phenotype)}}
    return {'enzymes': enzymes_data, 'conflicts': conflicts, 'phenotypes': phenotypes}
