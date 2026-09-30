import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
import socket_manager as sm
from physiology import normalize_monitor_state
from models import DEFAULT_MONITOR_STATE
from curriculum import catalogue, validate_selection
from debriefing.scenarios.trauma_airway_chest import configure_trauma_airway_chest, INJURIES
from debriefing.scenarios.trauma_haemorrhage import WARD_CONTEXT

def source(ward='ER',level='beginner'):
    return dict(patient={},location=ward,location_label=ward,level=level,discipline_labels=['Nurse'])

@pytest.mark.parametrize('ward',WARD_CONTEXT)
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
@pytest.mark.parametrize('injury',INJURIES)
@pytest.mark.parametrize('severity',['initial','deteriorating'])
def test_cases(ward,level,injury,severity):
    original=source(ward,level)
    case=configure_trauma_airway_chest(original,injury,severity)
    assert original['patient']=={}
    assert case['monitor_schema']=='trauma-airway-chest-1'
    assert case['patient']['age']==35
    assert case['initial_state']['NBP_sys'] is None and not case['initial_state']['show_ibp']
    assert bool(case['hints'])==(level=='beginner')
    assert len(case['conditions'])==3
    initial,worse=sorted(case['conditions'][:2],key=lambda s:s['state']['SpO2'],reverse=True)
    assert worse['state']['ABP_sys']<initial['state']['ABP_sys']
    if injury=='airway': assert worse['state']['avRR']==10 and worse['state']['etCO2']==58
    if injury=='tension': assert initial['state']['ABP_sys']<90
    for stage in case['conditions']:
        assert normalize_monitor_state(stage['state'])==stage['state']
        assert stage['state']['pulse_rate']>0 and not stage['state']['emd_pea']
        assert stage['state']['rhythm'] in ('NSR','SINUS_TACHY')
        assert 'student_display' not in stage['state']
    for key,value in case['conditions'][0]['state'].items(): assert case['initial_state'][key]==value

@pytest.mark.parametrize('injury',INJURIES)
def test_monitor_sync(monkeypatch,injury):
    case=configure_trauma_airway_chest(source(),injury)
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=SimpleNamespace(heart_rate=80,spo2=98,sys_bp=120,dia_bp=80,pap_sys=20,pap_dia=10,etco2=35,resp_rate=12))
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    state={**DEFAULT_MONITOR_STATE,**case['initial_state'],'student_display':dict.fromkeys(sm.STUDENT_DISPLAY_KEYS,False)}
    for stage in case['conditions']:
        state.update(stage['state'])
        asyncio.run(sm._sync_waveform_engine(state,'TRAUMA_CHEST_TEST'))
        command=engine.apply_command.call_args.args[0]
        assert command.heart_rate==state['HR'] and command.pulse_present
        assert command.spo2==state['SpO2'] and command.resp_rate==state['avRR']
        assert command.sys_bp==state['ABP_sys'] and command.dia_bp==state['ABP_dia']
        assert command.etco2==state['etCO2']
        assert not any(state['student_display'].values())

def test_catalogue():
    assert 'Airway and chest injury' in catalogue()['TLS']['launchable_topics']
    assert validate_selection('TLS','Airway and chest injury')['programme']=='TLS'

@pytest.mark.parametrize('injury,severity',[('unknown','initial'),('airway','unknown')])
def test_invalid(injury,severity):
    with pytest.raises(ValueError): configure_trauma_airway_chest({},injury,severity)
