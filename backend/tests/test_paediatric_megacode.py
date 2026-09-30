import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
import socket_manager as sm
from models import DEFAULT_MONITOR_STATE
from physiology import normalize_monitor_state
from curriculum import catalogue, validate_selection
from debriefing.scenarios.paediatric_megacode import configure_paediatric_megacode, validate_sequence, DEFAULT_SEQUENCE, STAGES, TOPIC
from debriefing.scenarios.paediatric_respiratory import WARD_HISTORY
from debriefing.scenarios.paediatric_shock import CAUSES

def source(ward='ER',level='beginner'):
    return dict(patient={},location=ward,location_label=ward,level=level,discipline_labels=['Nurse'])

@pytest.mark.parametrize('ward',WARD_HISTORY)
@pytest.mark.parametrize('profile',['infant','child'])
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
@pytest.mark.parametrize('cause',CAUSES)
def test_combined_case(ward,profile,level,cause):
    original=source(ward,level)
    case=configure_paediatric_megacode(original,profile,shock_cause=cause)
    assert not original['patient']
    assert case['monitor_schema']=='paediatric-megacode-1'
    assert len(case['conditions'])==len(DEFAULT_SEQUENCE)
    assert len({s['id'] for s in case['conditions']})==len(DEFAULT_SEQUENCE)
    assert case['initial_state']['patient_profile']==profile
    assert case['initial_state']['NBP_sys'] is None
    assert bool(case['hints'])==(level=='beginner')
    assert len({i['action'] for i in case['checklist']})==len(case['checklist'])
    for key,stage in zip(DEFAULT_SEQUENCE,case['conditions']):
        state=stage['state']
        assert normalize_monitor_state(state)==state
        assert (state['pulse_rate']==0)==key.startswith('arrest_')
        assert 'student_display' not in state and 'alarm_thresholds' not in state
    assert case['conditions'][1]['state']['rhythm']=='SINUS_TACHY'

@pytest.mark.parametrize('sequence',[None,[],['arrest_pea'],['rosc','stabilisation'],['arrest_vf','sinus_tachy'],['post_perfusion','stabilisation'],['bad','stabilisation'],['sinus_tachy']*17,['arrest_pea','rosc','arrest_vf','stabilisation'],[{},'stabilisation']])
def test_invalid_sequence(sequence):
    with pytest.raises(ValueError): validate_sequence(sequence)

@pytest.mark.parametrize('key',STAGES)
def test_every_preset(key):
    seq=['arrest_pea','rosc',key] if key.startswith('post_') else ['arrest_pea','rosc'] if key=='rosc' else [key,'arrest_pea']
    case=configure_paediatric_megacode(source(),sequence=seq)
    assert len(case['conditions'])==len(seq)

@pytest.mark.parametrize('profile',['infant','child'])
def test_monitor_sync_and_rearrest(monkeypatch,profile):
    sequence=['svt','vt_pulse','arrest_vf','arrest_pvt','rosc','post_ventilation','arrest_pea','rosc','stabilisation']
    case=configure_paediatric_megacode(source(),profile,sequence)
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=SimpleNamespace(heart_rate=80,spo2=98,sys_bp=120,dia_bp=80,pap_sys=20,pap_dia=10,etco2=35,resp_rate=12))
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    state={**DEFAULT_MONITOR_STATE,**case['initial_state'],'student_display':dict.fromkeys(sm.STUDENT_DISPLAY_KEYS,False)}
    thresholds=state['alarm_thresholds'].copy()
    for key,stage in zip(sequence,case['conditions']):
        state.update(stage['state'])
        asyncio.run(sm._sync_waveform_engine(state,'PAEDIATRIC_MEGACODE_TEST'))
        command=engine.apply_command.call_args.args[0]
        assert command.heart_rate==state['HR'] and command.spo2==state['SpO2']
        assert command.resp_rate==state['avRR'] and command.etco2==state['etCO2']
        assert command.sys_bp==state['ABP_sys'] and command.dia_bp==state['ABP_dia']
        assert bool(command.pulse_present)==(not key.startswith('arrest_'))
        assert state['alarm_thresholds']==thresholds
        assert not any(state['student_display'].values())

def test_catalogue():
    assert TOPIC in catalogue()['PALS']['launchable_topics']
    assert validate_selection('PALS',TOPIC)['programme']=='PALS'
