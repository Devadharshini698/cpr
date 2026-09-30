import pytest
from curriculum import catalogue, validate_selection
from physiology import normalize_monitor_state
from debriefing.scenarios.paediatric_post_resuscitation import configure_post_resuscitation, FOCUSES
from debriefing.scenarios.paediatric_respiratory import WARD_HISTORY

@pytest.mark.parametrize('ward', WARD_HISTORY)
@pytest.mark.parametrize('profile', ['infant', 'child'])
@pytest.mark.parametrize('focus', FOCUSES)
@pytest.mark.parametrize('level', ['beginner', 'intermediate', 'advanced'])
def test_post_resuscitation(ward, profile, focus, level):
    source = dict(patient={}, location=ward, location_label=ward, level=level, discipline_labels=['Nurse'])
    case = configure_post_resuscitation(source, profile, focus)
    state = case['initial_state']
    assert case['monitor_schema']=='paediatric-post-resuscitation-1'
    assert state['patient_profile']==profile and state['NBP_sys'] is None
    assert state['nibp_state']=='IDLE' and not state['show_ibp']
    assert len(case['conditions'])==5
    assert bool(case['hints'])==(level=='beginner')
    for stage in case['conditions']:
        assert normalize_monitor_state(stage['state'])==stage['state']
        assert stage['state']['pulse_rate']==stage['state']['HR']>0
        assert not stage['state']['emd_pea']
        assert 'student_display' not in stage['state']
        assert 'alarm_thresholds' not in stage['state']
    for key,value in case['conditions'][0]['state'].items():
        assert state[key]==value
    if focus=='oxygenation': assert state['SpO2']==88
    if focus=='ventilation': assert state['etCO2']==58 and state['avRR']==10
    if focus=='perfusion': assert state['ABP_sys']<75
    assert not source['patient']

def test_topic_enabled():
    assert 'Post-resuscitation care' in catalogue()['PALS']['launchable_topics']
    assert validate_selection('PALS','Post-resuscitation care')['programme']=='PALS'

@pytest.mark.parametrize('profile,focus', [('adult','assessment'),('child','unknown')])
def test_invalid_selection(profile,focus):
    with pytest.raises(ValueError): configure_post_resuscitation({},profile,focus)
