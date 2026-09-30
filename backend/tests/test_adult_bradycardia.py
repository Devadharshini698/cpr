import pytest
from debriefing.scenarios.adult_bradycardia import CONTEXTS, configure_bradycardia_case
from physiology import normalize_monitor_state, apply_perfusion_intent

@pytest.mark.parametrize('ward', CONTEXTS)
@pytest.mark.parametrize('severity', ['stable','unstable'])
@pytest.mark.parametrize('level', ['beginner','intermediate','advanced'])
def test_bradycardia_case(ward,severity,level):
    spec={'location':ward,'location_label':ward,'level':level,'patient':{},'discipline_labels':['Nurse'],'resources':{'defibrillator':False}}
    case=configure_bradycardia_case(spec,severity)
    assert spec['patient']=={}
    assert 0 < case['initial_state']['pulse_rate'] < 50
    assert (case['initial_state']['ABP_sys']<90)==(severity=='unstable')
    assert case['patient']['history']==CONTEXTS[ward][1]
    assert 'Nurse' in case['patient']['presentation']
    assert case['resources']==spec['resources']
    assert bool(case['hints'])==(level=='beginner')
    for stage in case['conditions']:
        assert normalize_monitor_state(stage['state'])==stage['state']
        assert 'student_display' not in stage['state']
    arrest=dict(case['initial_state'], pulse_rate=0, ABP_sys=0, ABP_dia=0, SpO2=0, CO=0)
    assert apply_perfusion_intent(arrest, {'rhythm':arrest['rhythm']})['pulse_rate']==0
    assert case['conditions'][-1]['state']['HR']==75

def test_invalid_course():
    with pytest.raises(ValueError): configure_bradycardia_case({},'arrest')
