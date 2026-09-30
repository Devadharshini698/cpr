import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from debriefing.scenarios.neonatal_transition import PROFILES,SETTINGS
from debriefing.scenarios.neonatal_ventilation import configure_neonatal_ventilation,PROBLEMS,TOPIC
from physiology import normalize_monitor_state
from curriculum import validate_selection
from ecg_state import ECGState
import socket_manager as sm

def source(level='beginner'):
    return dict(patient={},location='ER',location_label='ER',level=level,discipline_labels=['Doctor','Nurse'])

@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('setting',SETTINGS)
@pytest.mark.parametrize('course',['apnoea','ineffective'])
@pytest.mark.parametrize('problem',PROBLEMS)
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
def test_variants(profile,setting,course,problem,level):
    original=source(level)
    case=configure_neonatal_ventilation(original,profile,course,setting,problem)
    assert original['patient']=={}
    assert case['monitor_schema']=='neonatal-ventilation-1'
    assert case['conditions'][0]['id']=='neo_vent_'+course
    assert bool(case['hints'])==(level=='beginner')
    assert not case['initial_state']['show_etco2'] and not case['initial_state']['show_ibp']
    for stage in case['conditions']:
        state=stage['state']
        assert normalize_monitor_state(state)==state
        assert state['pulse_rate']==state['HR'] and state['pulse_rate']>0
        assert state['etCO2']==0 and 'student_display' not in state
        alarms=sm.compute_alarms(state)
        if stage['id'] in ('neo_vent_apnoea','neo_vent_ineffective'):
            assert 'APNEA' in alarms and 'HR LOW' in alarms
        if stage['id']=='neo_vent_escalation': assert state['HR']<60 and state['avRR']==40
        if stage['id'] in ('neo_vent_effective','neo_vent_spontaneous'): assert not alarms

def test_monitor_sync(monkeypatch):
    case=configure_neonatal_ventilation(source())
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=ECGState())
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    for stage in case['conditions']:
        state=stage['state']
        asyncio.run(sm._sync_waveform_engine(state,'VENT_QA'))
        command=engine.apply_command.call_args.args[0]
        assert command.heart_rate==state['HR'] and command.resp_rate==state['avRR']
        assert command.pulse_present and command.spo2==state['SpO2'] and command.etco2==0

def test_gate_and_invalid_options():
    assert validate_selection('NALS',TOPIC)['subtopic']==TOPIC
    for course,problem in [('unknown','mask_leak'),('apnoea','unknown')]:
        with pytest.raises(ValueError): configure_neonatal_ventilation(source(),course=course,problem=problem)
