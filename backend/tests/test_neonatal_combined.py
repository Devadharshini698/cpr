import pytest
from debriefing.scenarios.neonatal_combined import configure_neonatal_combined,DEFAULT_SEQUENCE,TOPIC
from debriefing.scenarios.neonatal_transition import PROFILES,SETTINGS
from debriefing.scenarios.neonatal_advanced import CONTEXTS
from debriefing.scenarios.neonatal_ventilation import PROBLEMS
from physiology import normalize_monitor_state
from curriculum import validate_selection

def source(level='beginner'):
    return dict(patient={},location='ER',location_label='ER',level=level,discipline_labels=['Doctor','Nurse'])

@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('setting',SETTINGS)
@pytest.mark.parametrize('context',CONTEXTS)
@pytest.mark.parametrize('problem',PROBLEMS)
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
def test_combined(profile,setting,context,problem,level):
    original=source(level)
    case=configure_neonatal_combined(original,profile,setting,problem=problem,context=context)
    assert original['patient']=={}
    assert case['monitor_schema']=='neonatal-combined-1' and case['neonatal_sequence']==DEFAULT_SEQUENCE
    assert len({s['id'] for s in case['conditions']})==len(DEFAULT_SEQUENCE)
    assert bool(case['hints'])==(level=='beginner')
    assert len({i['action'] for i in case['checklist']})==len(case['checklist'])
    ages=[]
    for stage in case['conditions']:
        state=stage['state'];ages.append(state['neonatal_age_minutes'])
        assert normalize_monitor_state(state)==state
        assert state['patient_profile']=='neonate' and 'student_display' not in state
        assert state['patient_weight_kg']==case['patient']['weight_kg']
    assert ages==sorted(ages)

@pytest.mark.parametrize('sequence',[[],['neo_vent_apnoea'],['invalid','invalid'],[{},'neo_vent_apnoea'],['neo_post_assessment','neo_post_handover'],['neo_vent_effective','neo_post_handover'],['neo_adv_hr_response','neo_vent_apnoea'],['neo_vent_effective','neo_adv_refractory','neo_post_assessment']])
def test_invalid_sequence(sequence):
    with pytest.raises(ValueError): configure_neonatal_combined(source(),sequence=sequence)

def test_shorter_case_and_topic():
    assert validate_selection('NALS',TOPIC)['programme']=='NALS'
    sequence=['neo_vent_apnoea','neo_vent_effective','neo_post_assessment','neo_post_handover']
    case=configure_neonatal_combined(source(),sequence=sequence)
    assert case['neonatal_sequence']==sequence
    assert not any('3:1' in i['action'] for i in case['checklist'])
