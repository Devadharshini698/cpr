import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
import socket_manager as sm
from physiology import normalize_monitor_state
from models import DEFAULT_MONITOR_STATE
from curriculum import catalogue, validate_selection, assessment_items
from debriefing.scenarios.trauma_haemorrhage import configure_trauma_haemorrhage, MECHANISMS, WARD_CONTEXT

def source(ward='ER',level='beginner'):
    return dict(patient={},location=ward,location_label=ward,level=level,discipline_labels=['Nurse'])

@pytest.mark.parametrize('ward',WARD_CONTEXT)
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
@pytest.mark.parametrize('mechanism',MECHANISMS)
@pytest.mark.parametrize('severity',['compensated','hypotensive'])
def test_trauma(ward,level,mechanism,severity):
    original=source(ward,level)
    case=configure_trauma_haemorrhage(original,mechanism,severity)
    assert original['patient']=={}
    assert case['patient']['age']==35 and case['patient']['weight_kg']==70
    assert case['initial_state']['NBP_sys'] is None and not case['initial_state']['show_ibp']
    assert case['initial_state']['ABP_sys']==(110 if severity=='compensated' else 80)
    assert bool(case['hints'])==(level=='beginner')
    assert len(case['conditions'])==4
    for stage in case['conditions']:
        assert normalize_monitor_state(stage['state'])==stage['state']
        assert stage['state']['pulse_rate']>0 and not stage['state']['emd_pea']
        assert stage['state']['rhythm'] in ('NSR','SINUS_TACHY')
        assert 'student_display' not in stage['state']

def test_monitor_transitions(monkeypatch):
    case=configure_trauma_haemorrhage(source())
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=SimpleNamespace(heart_rate=80,spo2=98,sys_bp=120,dia_bp=80,pap_sys=20,pap_dia=10,etco2=35,resp_rate=12))
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    state={**DEFAULT_MONITOR_STATE,**case['initial_state'],'student_display':dict.fromkeys(sm.STUDENT_DISPLAY_KEYS,False)}
    for stage in case['conditions']:
        state.update(stage['state'])
        asyncio.run(sm._sync_waveform_engine(state,'TRAUMA_TEST'))
        command=engine.apply_command.call_args.args[0]
        assert command.heart_rate==state['HR'] and command.pulse_present
        assert command.spo2==state['SpO2'] and command.resp_rate==state['avRR']
        assert command.sys_bp==state['ABP_sys'] and command.dia_bp==state['ABP_dia']
        assert command.etco2==state['etCO2']
        assert not any(state['student_display'].values())

def test_catalogue_and_assessment():
    assert 'Major haemorrhage' in catalogue()['TLS']['launchable_topics']
    assert validate_selection('TLS','Major haemorrhage')['programme']=='TLS'
    assert next(iter(assessment_items('TLS')['primary']))=='haemorrhage'
    with pytest.raises(ValueError): validate_selection('TLS','Unknown trauma topic')

@pytest.mark.parametrize('mechanism,severity',[('bad','compensated'),('external','bad')])
def test_invalid(mechanism,severity):
    with pytest.raises(ValueError): configure_trauma_haemorrhage({},mechanism,severity)
