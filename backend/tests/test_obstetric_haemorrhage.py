import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from debriefing.scenarios.obstetric_haemorrhage import configure_obstetric_haemorrhage,CAUSES,SETTINGS,SEVERITIES,TOPIC
from curriculum import catalogue,validate_selection,assessment_items
from physiology import normalize_monitor_state
from ecg_state import ECGState
import socket_manager as sm

def source(level='beginner'):
    return dict(patient={},location='ER',location_label='ER',level=level,discipline_labels=['Doctor','Nurse'])

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('setting',SETTINGS)
@pytest.mark.parametrize('severity',SEVERITIES)
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
def test_cases(cause,setting,severity,level):
    original=source(level)
    case=configure_obstetric_haemorrhage(original,cause,severity,setting)
    assert original['patient']=={}
    assert case['monitor_schema']=='obstetric-haemorrhage-1'
    assert case['conditions'][0]['id']=='pph_'+severity
    assert bool(case['hints'])==(level=='beginner')
    assert case['patient']['postpartum_minutes']==30 and case['patient']['sex']=='female'
    assert case['initial_state']['NBP_sys'] is None and not case['initial_state']['show_ibp']
    assert not case['initial_state']['show_etco2']
    for stage in case['conditions']:
        state=stage['state']
        assert normalize_monitor_state(state)==state
        assert state['pulse_rate']==state['HR'] and state['pulse_rate']>0
        assert state['SpO2']==97 and state['etCO2']==0
        assert state['rhythm']==('SINUS_TACHY' if state['HR']>100 else 'NSR')
        assert 'student_display' not in state
        if stage['id']=='pph_critical': assert {'HR HIGH','ABP_sys LOW'}<=set(sm.compute_alarms(state))

def test_sync(monkeypatch):
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=ECGState())
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    for stage in configure_obstetric_haemorrhage(source())['conditions']:
        state=stage['state'];asyncio.run(sm._sync_waveform_engine(state,'PPH_QA'))
        update=engine.apply_command.call_args.args[0]
        assert update.heart_rate==state['HR'] and update.sys_bp==state['ABP_sys']
        assert update.pulse_present and update.resp_rate==state['avRR']

def test_validation_and_assessment():
    assert catalogue()['ALSO']['launchable_topics']==[TOPIC,'Hypertensive emergencies','Maternal collapse','Other obstetric emergencies']
    assert validate_selection('ALSO',TOPIC)['programme']=='ALSO'
    assert 'bleeding' in assessment_items('ALSO')['primary']
    with pytest.raises(ValueError): validate_selection('ALSO','Unknown topic')
    for args in [('unknown','maintained','delivery_suite'),('tone','unknown','delivery_suite'),('tone','maintained','unknown')]:
        with pytest.raises(ValueError): configure_obstetric_haemorrhage(source(),*args)
