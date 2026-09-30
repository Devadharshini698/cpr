import pytest
from debriefing.scenarios.paediatric_shock import configure_shock_case, CAUSES
from debriefing.scenarios.paediatric_respiratory import WARD_HISTORY
from physiology import normalize_monitor_state
from socket_manager import compute_alarms

@pytest.mark.parametrize('ward',WARD_HISTORY)
@pytest.mark.parametrize('profile',['infant','child'])
@pytest.mark.parametrize('severity',['compensated','hypotensive'])
@pytest.mark.parametrize('cause',CAUSES)
def test_shock(ward,profile,severity,cause):
    source={'patient':{},'location':ward,'location_label':ward,'level':'beginner','discipline_labels':['Nurse']}
    case=configure_shock_case(source,profile,severity,cause)
    assert not source['patient']
    assert case['monitor_schema']=='paediatric-shock-1'
    assert case['initial_state']['patient_profile']==profile
    assert case['initial_state']['NBP_sys'] is None
    assert case['initial_state']['pulse_rate']>0
    assert (case['initial_state']['ABP_sys']<75)==(severity=='hypotensive')
    for stage in case['conditions']:
        assert normalize_monitor_state(stage['state'])==stage['state']
        assert 'student_display' not in stage['state']
    assert not compute_alarms({**case['initial_state'],**case['conditions'][-1]['state']})

def test_bad_input():
    with pytest.raises(ValueError): configure_shock_case({},cause='unknown')
