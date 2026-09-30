import pytest
import numpy as np
from ecg_state import ECGState
from simman_engine.waveform_generator import WaveformGenerator
from debriefing.scenarios.paediatric_tachyarrhythmia import configure_paediatric_tachyarrhythmia, PATTERNS
from debriefing.scenarios.paediatric_respiratory import WARD_HISTORY
from socket_manager import compute_alarms

@pytest.mark.parametrize('ward',WARD_HISTORY)
@pytest.mark.parametrize('profile',['infant','child'])
@pytest.mark.parametrize('severity',['maintained','compromise'])
@pytest.mark.parametrize('pattern',PATTERNS)
def test_cases(ward,profile,severity,pattern):
    source={'patient':{},'location':ward,'location_label':ward,'level':'beginner','discipline_labels':['Nurse']}
    case=configure_paediatric_tachyarrhythmia(source,profile,severity,pattern)
    state=case['initial_state']
    assert state['patient_profile']==profile and state['pulse_rate']==state['HR']>0
    assert (state['ABP_sys']<75)==(severity=='compromise')
    assert case['monitor_schema']=='paediatric-tachyarrhythmia-1'
    assert not source['patient']
    assert not compute_alarms({**state,**case['conditions'][-1]['state']})
    assert all('student_display' not in s['state'] for s in case['conditions'])

@pytest.mark.parametrize('pattern',PATTERNS)
def test_high_rate_waveforms(pattern):
    case=configure_paediatric_tachyarrhythmia({'patient':{},'location':'ER','location_label':'ER','level':'advanced','discipline_labels':['Doctor']},'infant','compromise',pattern)
    s=case['initial_state']; telemetry=ECGState(rhythm=s['rhythm'],heart_rate=s['HR'],pulse_present=True,spo2=s['SpO2'])
    gen=WaveformGenerator()
    for values in (gen.generate(telemetry,2000),gen.generate_pleth(telemetry,2000)):
        assert np.isfinite(values).all() and np.ptp(values)>0.1

def test_invalid():
    with pytest.raises(ValueError): configure_paediatric_tachyarrhythmia({},pattern='unknown')
