import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
import socket_manager as sm
from physiology import normalize_monitor_state
from models import DEFAULT_MONITOR_STATE
from curriculum import catalogue, validate_selection
from debriefing.scenarios.trauma_multisystem import configure_multisystem_trauma, FOCUSES
from debriefing.scenarios.trauma_haemorrhage import WARD_CONTEXT

def source(ward='ER',level='beginner'):
    return dict(patient={},location=ward,location_label=ward,level=level,discipline_labels=['Nurse'])

@pytest.mark.parametrize('ward',WARD_CONTEXT)
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
@pytest.mark.parametrize('focus',FOCUSES)
def test_cases(ward,level,focus):
    original=source(ward,level)
    case=configure_multisystem_trauma(original,focus)
    assert original['patient']=={}
    assert case['monitor_schema']=='trauma-multisystem-1'
    assert case['initial_state']['NBP_sys'] is None and not case['initial_state']['show_ibp']
    assert len(case['conditions'])==5-FOCUSES.index(focus)
    assert case['conditions'][0]['id']=='multisystem_'+focus
    assert bool(case['hints'])==(level=='beginner')
    for stage in case['conditions']:
        assert normalize_monitor_state(stage['state'])==stage['state']
        assert stage['state']['pulse_rate']>0
        assert 'student_display' not in stage['state']
    for key,value in case['conditions'][0]['state'].items(): assert case['initial_state'][key]==value
    if focus=='circulatory': assert case['initial_state']['SpO2']==95 and case['initial_state']['ABP_sys']==75
    if focus=='neurological': assert case['initial_state']['SpO2']==96 and 'GCS 9' in case['conditions'][0]['description']
    assert 'GCS 9' in case['conditions'][-1]['description']

def test_monitor_sync(monkeypatch):
    case=configure_multisystem_trauma(source())
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=SimpleNamespace(heart_rate=80,spo2=98,sys_bp=120,dia_bp=80,pap_sys=20,pap_dia=10,etco2=35,resp_rate=12))
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    state={**DEFAULT_MONITOR_STATE,**case['initial_state'],'student_display':dict.fromkeys(sm.STUDENT_DISPLAY_KEYS,False)}
    for stage in case['conditions']:
        state.update(stage['state'])
        asyncio.run(sm._sync_waveform_engine(state,'MULTISYSTEM_TEST'))
        command=engine.apply_command.call_args.args[0]
        assert command.heart_rate==state['HR'] and command.pulse_present
        assert command.spo2==state['SpO2'] and command.resp_rate==state['avRR']
        assert command.sys_bp==state['ABP_sys'] and command.dia_bp==state['ABP_dia']
        assert command.etco2==state['etCO2']
        assert not any(state['student_display'].values())

def test_catalogue_and_validation():
    assert 'Multisystem trauma' in catalogue()['TLS']['launchable_topics']
    assert validate_selection('TLS','Multisystem trauma')['programme']=='TLS'
    with pytest.raises(ValueError): configure_multisystem_trauma({},'unknown')
