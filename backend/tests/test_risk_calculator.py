from types import SimpleNamespace
from services.risk_calculator import anticholinergic_burden, cns_depression_risk, qtc_risk_score, serotonin_risk_score, top_interaction

def _med(**kwargs):
    return SimpleNamespace(**kwargs)

def test_serotonin_ssri_maoi_critical():
    meds = [_med(drug_class='SSRI', generic_name='sertraline', serotonergic_potency=1), _med(drug_class='MAOI', generic_name='phenelzine', serotonergic_potency=1)]
    assert serotonin_risk_score(meds) == 'Critical'

def test_serotonin_ssri_only_low():
    meds = [_med(drug_class='SSRI', generic_name='sertraline', serotonergic_potency=2)]
    assert serotonin_risk_score(meds) == 'Low'

def test_serotonin_ssri_snri_high():
    meds = [_med(drug_class='SSRI', generic_name='sertraline', serotonergic_potency=1), _med(drug_class='SNRI', generic_name='venlafaxine', serotonergic_potency=1)]
    assert serotonin_risk_score(meds) == 'High'

def test_serotonin_moderate():
    meds = [_med(drug_class='SSRI', generic_name='sertraline', serotonergic_potency=2), _med(drug_class='OTHER', generic_name='trazodone', serotonergic_potency=1)]
    assert serotonin_risk_score(meds) == 'Moderate'

def test_serotonin_none():
    meds = [_med(drug_class='OTHER', generic_name='gabapentin', serotonergic_potency=0), _med(drug_class='OTHER', generic_name='topiramate', serotonergic_potency=0)]
    assert serotonin_risk_score(meds) == 'None'

def test_qtc_two_high_tier_critical():
    meds = [_med(generic_name='ziprasidone', qtc_prolongation_risk=True), _med(generic_name='methadone', qtc_prolongation_risk=True)]
    assert qtc_risk_score(meds) == 'Critical'

def test_qtc_two_moderate_tier():
    meds = [_med(generic_name='haloperidol', qtc_prolongation_risk=True), _med(generic_name='citalopram', qtc_prolongation_risk=True)]
    assert qtc_risk_score(meds) == 'Moderate'

def test_qtc_single_low():
    meds = [_med(generic_name='haloperidol', qtc_prolongation_risk=True), _med(generic_name='sertraline', qtc_prolongation_risk=False)]
    assert qtc_risk_score(meds) == 'Low'

def test_qtc_none():
    meds = [_med(generic_name='sertraline', qtc_prolongation_risk=False), _med(generic_name='bupropion', qtc_prolongation_risk=False)]
    assert qtc_risk_score(meds) == 'None'

def test_anticholinergic_sum():
    meds = [_med(anticholinergic_potency=2), _med(anticholinergic_potency=3)]
    assert anticholinergic_burden(meds) == 5

def test_cns_depression_high():
    meds = [_med(cns_depression_risk=3), _med(cns_depression_risk=3)]
    assert cns_depression_risk(meds) == 'High'

def test_cns_depression_moderate():
    meds = [_med(cns_depression_risk=2), _med(cns_depression_risk=2)]
    assert cns_depression_risk(meds) == 'Moderate'

def test_cns_depression_low():
    meds = [_med(cns_depression_risk=1), _med(cns_depression_risk=1)]
    assert cns_depression_risk(meds) == 'Low'

def test_top_interaction_critical():
    interactions = [{'severity': 'major', 'id': 1}, {'severity': 'critical', 'id': 2}, {'severity': 'minor', 'id': 3}]
    top = top_interaction(interactions)
    assert top is not None
    assert top['severity'] == 'critical'
    assert top['id'] == 2

def test_top_interaction_empty():
    assert top_interaction([]) is None
