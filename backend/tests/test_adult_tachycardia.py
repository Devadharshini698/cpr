import pytest
from debriefing.scenarios.adult_tachycardia import CONTEXTS, configure_tachycardia_case

@pytest.mark.parametrize('ward', CONTEXTS)
@pytest.mark.parametrize('severity', ['stable','unstable'])
@pytest.mark.parametrize('level', ['beginner','intermediate','advanced'])
def test_tachy_cases(ward,severity,level):
    original={'location':ward,'location_label':ward,'level':level,'patient':{},'discipline_labels':['Nurse'],'resources':{'defibrillator':False}}
    case=configure_tachycardia_case(original,severity)
    assert original['patient']=={}
    assert case['initial_state']['pulse_rate']>100
    assert (case['initial_state']['ABP_sys']<90)==(severity=='unstable')
    assert case['patient']['history']==CONTEXTS[ward][1]
    assert 'Nurse' in case['patient']['presentation']
    assert case['resources']==original['resources']
    assert bool(case['hints'])==(level=='beginner')
    assert case['conditions'][-1]['state']['pulse_rate']==90
    assert all('student_display' not in c['state'] for c in case['conditions'])
    if CONTEXTS[ward][2]=='SINUS_TACHY':
        assert 'do not cardiovert' in case['teaching_notes']['clinical_focus']

def test_invalid_severity():
    with pytest.raises(ValueError): configure_tachycardia_case({},'arrest')
