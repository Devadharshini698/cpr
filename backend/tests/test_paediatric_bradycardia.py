import pytest
from debriefing.scenarios.paediatric_bradycardia import configure_paediatric_bradycardia
from debriefing.scenarios.paediatric_respiratory import WARD_HISTORY
from socket_manager import compute_alarms

@pytest.mark.parametrize('ward',WARD_HISTORY)
@pytest.mark.parametrize('profile',['infant','child'])
@pytest.mark.parametrize('severity',['maintained','compromise'])
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
def test_brady(ward,profile,severity,level):
    spec={'patient':{},'location':ward,'location_label':ward,'level':level,'discipline_labels':['Nurse']}
    case=configure_paediatric_bradycardia(spec,profile,severity)
    assert case['monitor_schema']=='paediatric-bradycardia-1'
    assert case['initial_state']['patient_profile']==profile
    assert 'HR LOW' in compute_alarms(case['initial_state'])
    assert bool(case['hints'])==(level=='beginner')
    assert all(c['state']['pulse_rate']>0 for c in case['conditions'])
    persistent=case['conditions'][2]['state']
    assert persistent['HR']<60 and persistent['SpO2']==96 and persistent['ABP_sys']<75
    assert not compute_alarms({**case['initial_state'],**case['conditions'][-1]['state']})
    assert not spec['patient']

def test_invalid():
    with pytest.raises(ValueError): configure_paediatric_bradycardia({},severity='arrest')
