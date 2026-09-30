import pytest
from debriefing.scenarios.paediatric_arrest import configure_paediatric_arrest, CONTEXTS
from debriefing.scenarios.paediatric_respiratory import WARD_HISTORY
from physiology import normalize_monitor_state

@pytest.mark.parametrize('ward',WARD_HISTORY)
@pytest.mark.parametrize('profile',['infant','child'])
@pytest.mark.parametrize('context',CONTEXTS)
@pytest.mark.parametrize('rhythm',[None,'PEA','ASYSTOLE','VF','PVT'])
def test_arrest(ward,profile,context,rhythm):
    source={'patient':{},'location':ward,'location_label':ward,'level':'advanced','discipline_labels':['Nurse']}
    case=configure_paediatric_arrest(source,profile,context,rhythm)
    state=case['initial_state']
    assert state['pulse_rate']==state['SpO2']==state['ABP_sys']==0
    assert state['patient_profile']==profile and state['NBP_sys'] is None
    rosc=case['conditions'][2]['state']
    assert rosc['pulse_rate']>0 and rosc['SpO2']>0 and not rosc['emd_pea']
    assert case['conditions'][3]['state']['pulse_rate']==0
    for stage in case['conditions']:
        assert normalize_monitor_state(stage['state'])==stage['state']
        assert 'student_display' not in stage['state']
    assert not source['patient']

def test_nonarrest_rhythm_rejected():
    with pytest.raises(ValueError): configure_paediatric_arrest({},initial_rhythm='NSR')
