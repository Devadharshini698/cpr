import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from debriefing.scenarios.neonatal_post_resuscitation import configure_neonatal_post_resuscitation,FOCI,TOPIC
from debriefing.scenarios.neonatal_transition import PROFILES,SETTINGS
from curriculum import validate_selection,assessment_items,public_assessment
from physiology import normalize_monitor_state
from ecg_state import ECGState
import socket_manager as sm

def source(level='beginner'):
    return dict(patient={},location='ER',location_label='ER',level=level,discipline_labels=['Nurse','Doctor'])

@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('setting',SETTINGS)
@pytest.mark.parametrize('focus',FOCI)
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
def test_variants(profile,setting,focus,level):
    original=source(level)
    case=configure_neonatal_post_resuscitation(original,profile,setting,focus)
    assert original['patient']=={}
    assert case['monitor_schema']=='neonatal-post-resuscitation-1'
    assert case['conditions'][0]['id']=='neo_post_'+focus
    assert bool(case['hints'])==(level=='beginner')
    assert not case['initial_state']['show_ibp'] and case['initial_state']['NBP_sys'] is None
    for stage in case['conditions']:
        state=stage['state']
        assert normalize_monitor_state(state)==state
        assert state['HR']==state['pulse_rate'] and state['pulse_rate']>0
        assert state['etCO2']==0 and 'student_display' not in state and 'glucose' not in state
        alarms=sm.compute_alarms(state)
        if stage['id']=='neo_post_temperature': assert 'Tperi LOW' in alarms
        if stage['id']=='neo_post_deterioration': assert {'HR LOW','DESAT','avRR LOW'}<=set(alarms)
        if stage['id'] in ('neo_post_response','neo_post_handover'): assert not alarms

def test_sync(monkeypatch):
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=ECGState())
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    for stage in configure_neonatal_post_resuscitation(source())['conditions']:
        state=stage['state']
        asyncio.run(sm._sync_waveform_engine(state,'POST_QA'))
        update=engine.apply_command.call_args.args[0]
        assert update.heart_rate==state['HR'] and update.resp_rate==state['avRR']
        assert update.pulse_present and update.spo2==state['SpO2']

def test_gate_assessment_and_validation():
    assert validate_selection('NALS',TOPIC)['programme']=='NALS'
    assert {'glucose','neurology','perfusion'}<=set(assessment_items('NALS')['focused_assessment'])
    row=dict(id=1,phase='focused_assessment',item='glucose',created_at='now',kind='observation',revealed=False,finding='Faculty laboratory result')
    assert public_assessment(row)['finding'] is None
    with pytest.raises(ValueError): configure_neonatal_post_resuscitation(source(),focus='unknown')
