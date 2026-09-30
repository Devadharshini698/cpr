import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
import socket_manager as sm
from physiology import normalize_monitor_state
from models import DEFAULT_MONITOR_STATE
from curriculum import catalogue, validate_selection
from debriefing.scenarios.trauma_head_injury import configure_trauma_head_injury, COURSES
from debriefing.scenarios.trauma_haemorrhage import WARD_CONTEXT

def source(ward='ER',level='beginner'):
    return dict(patient={},location=ward,location_label=ward,level=level,discipline_labels=['Nurse'])

@pytest.mark.parametrize('ward',WARD_CONTEXT)
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
@pytest.mark.parametrize('course',COURSES)
def test_cases(ward,level,course):
    original=source(ward,level)
    case=configure_trauma_head_injury(original,course)
    assert original['patient']=={}
    assert case['monitor_schema']=='trauma-head-injury-1'
    assert case['initial_state']['NBP_sys'] is None and not case['initial_state']['show_ibp']
    assert len(case['conditions'])==4
    assert bool(case['hints'])==(level=='beginner')
    for stage in case['conditions']:
        assert normalize_monitor_state(stage['state'])==stage['state']
        assert stage['state']['pulse_rate']>0
        assert 'student_display' not in stage['state']
        assert 'GCS' in stage['description']
    for key,value in case['conditions'][0]['state'].items(): assert case['initial_state'][key]==value
    if course=='neurological_deterioration':
        assert case['initial_state']['SpO2']==96 and case['initial_state']['ABP_sys']==135
    if course=='secondary_insult':
        assert case['initial_state']['SpO2']==85 and case['initial_state']['ABP_sys']==85
    assert 'GCS 9' in case['conditions'][-1]['description']

@pytest.mark.parametrize('course',COURSES)
def test_monitor_sync(monkeypatch,course):
    case=configure_trauma_head_injury(source(),course)
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=SimpleNamespace(heart_rate=80,spo2=98,sys_bp=120,dia_bp=80,pap_sys=20,pap_dia=10,etco2=35,resp_rate=12))
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    state={**DEFAULT_MONITOR_STATE,**case['initial_state'],'student_display':dict.fromkeys(sm.STUDENT_DISPLAY_KEYS,False)}
    for stage in case['conditions']:
        state.update(stage['state'])
        asyncio.run(sm._sync_waveform_engine(state,'HEAD_INJURY_TEST'))
        command=engine.apply_command.call_args.args[0]
        assert command.heart_rate==state['HR'] and command.pulse_present
        assert command.spo2==state['SpO2'] and command.resp_rate==state['avRR']
        assert command.sys_bp==state['ABP_sys'] and command.dia_bp==state['ABP_dia']
        assert command.etco2==state['etCO2']
        assert not any(state['student_display'].values())

def test_catalogue():
    assert 'Head injury' in catalogue()['TLS']['launchable_topics']
    assert validate_selection('TLS','Head injury')['programme']=='TLS'
    with pytest.raises(ValueError): configure_trauma_head_injury({},'unknown')
