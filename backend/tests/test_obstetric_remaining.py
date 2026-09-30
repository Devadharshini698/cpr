import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
import numpy as np
from simman_engine.waveform_generator import WaveformGenerator
from physiology import normalize_monitor_state
from curriculum import validate_selection
from ecg_state import ECGState
import socket_manager as sm
from debriefing.scenarios.obstetric_remaining import configure_maternal_collapse,configure_other_obstetric,SETTINGS,COLLAPSE_CAUSES,EMERGENCIES

def source(level='beginner'):
    return dict(level=level,discipline_labels=['Doctor','Nurse'],patient={})

def assert_case(case):
    assert case['initial_state']['NBP_sys'] is None
    assert case['initial_state']['configured_channels']['pap'] is False
    ids=[c['id'] for c in case['conditions']]
    assert len(ids)==len(set(ids))
    for condition in case['conditions']:
        state=condition['state']
        assert normalize_monitor_state(state)==state
        assert 'student_display' not in state and 'waveform_channels' not in state
        if state['pulse_rate']==0:
            assert state['SpO2']==state['ABP_sys']==state['ABP_dia']==0
        else:
            assert state['rhythm']==('SINUS_TACHY' if state['HR']>100 else 'NSR')

@pytest.mark.parametrize('context',['antenatal','postpartum'])
@pytest.mark.parametrize('entry',['deteriorating','arrest'])
@pytest.mark.parametrize('cause',COLLAPSE_CAUSES)
@pytest.mark.parametrize('setting',SETTINGS)
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
def test_collapse(context,entry,cause,setting,level):
    original=source(level)
    case=configure_maternal_collapse(original,context,entry,cause,setting)
    assert original['patient']=={}
    assert_case(case)
    assert case['initial_state']['pulse_rate']>0 if entry=='deteriorating' else case['initial_state']['pulse_rate']==0
    assert case['patient']['postpartum_hours']==(24 if context=='postpartum' else None)
    assert bool(case['hints'])==(level=='beginner')
    assert ('aim to complete by 5 minutes' in str(case['checklist']))==(context=='antenatal')
    rosc=next(c['state'] for c in case['conditions'] if c['id']=='mc_rosc')
    assert rosc['pulse_rate']>0 and rosc['emd_pea'] is False

@pytest.mark.parametrize('kind',EMERGENCIES)
@pytest.mark.parametrize('context',['antenatal','postpartum'])
@pytest.mark.parametrize('setting',SETTINGS)
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
def test_other(kind,context,setting,level):
    case=configure_other_obstetric(source(level),kind,setting,context)
    assert_case(case)
    assert all(c['state']['pulse_rate']>0 for c in case['conditions'])
    if kind!='sepsis':
        assert case['patient']['gestational_age_weeks']==39
        assert case['patient']['postpartum_hours'] is None
        assert case['obstetric_emergency_context']=='intrapartum'

def test_sync(monkeypatch):
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=ECGState())
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    cases=[configure_maternal_collapse(source())]+[configure_other_obstetric(source(),kind) for kind in EMERGENCIES]
    for case in cases:
        for condition in case['conditions']:
            state=condition['state'];asyncio.run(sm._sync_waveform_engine(state,'OB_QA'))
            command=engine.apply_command.call_args.args[0]
            assert command.heart_rate==state['HR'] and command.sys_bp==state['ABP_sys']
            assert command.pulse_present==(state['pulse_rate']>0)
            assert command.rhythm.value==state['rhythm']
            telemetry=ECGState(**command.model_dump(exclude_none=True))
            assert np.isfinite(WaveformGenerator().generate(telemetry,256)).all()

@pytest.mark.parametrize('kwargs',[{'entry':'bad'},{'cause':'bad'},{'context':'bad'},{'setting':'bad'}])
def test_invalid_collapse(kwargs):
    with pytest.raises(ValueError): configure_maternal_collapse(source(),**kwargs)

@pytest.mark.parametrize('kwargs',[{'kind':'bad'},{'context':'bad'},{'setting':'bad'}])
def test_invalid_other(kwargs):
    with pytest.raises(ValueError): configure_other_obstetric(source(),**kwargs)

def test_catalogue():
    for topic in ('Maternal collapse','Other obstetric emergencies'):
        assert validate_selection('ALSO',topic)['programme']=='ALSO'
