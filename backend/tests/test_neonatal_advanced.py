import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from debriefing.scenarios.neonatal_advanced import configure_neonatal_advanced,CONTEXTS,TOPIC
from debriefing.scenarios.neonatal_transition import PROFILES,SETTINGS
from physiology import normalize_monitor_state
from curriculum import validate_selection
from ecg_state import ECGState
import socket_manager as sm

def source(level='beginner'):
    return dict(patient={},location='ER',location_label='ER',level=level,discipline_labels=['Nurse','Doctor'])

@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('setting',SETTINGS)
@pytest.mark.parametrize('context',CONTEXTS)
@pytest.mark.parametrize('entry',['escalation','ongoing_resuscitation'])
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
def test_variants(profile,setting,context,entry,level):
    original=source(level)
    case=configure_neonatal_advanced(original,profile,setting,context,entry)
    assert original['patient']=={}
    assert case['monitor_schema']=='neonatal-advanced-1' and case['clinical_severity']=='critical'
    assert bool(case['hints'])==(level=='beginner')
    assert not case['initial_state']['show_ibp'] and not case['initial_state']['show_etco2']
    assert case['initial_state']['HR']<60
    for stage in case['conditions']:
        state=stage['state']
        assert normalize_monitor_state(state)==state
        assert state['HR']==state['pulse_rate'] and state['pulse_rate']>0
        assert state['etCO2']==0 and 'student_display' not in state
        if stage['id'] in ('neo_adv_ongoing','neo_adv_refractory'):
            assert state['avRR']==30 and state['HR']<60
        if stage['id']=='neo_adv_hr_response': assert 60<state['HR']<100
        if stage['id']=='neo_adv_stabilisation': assert not sm.compute_alarms(state)

def test_sync(monkeypatch):
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=ECGState())
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    for stage in configure_neonatal_advanced(source())['conditions']:
        state=stage['state']
        asyncio.run(sm._sync_waveform_engine(state,'ADV_QA'))
        update=engine.apply_command.call_args.args[0]
        assert update.heart_rate==state['HR'] and update.resp_rate==state['avRR']
        assert update.pulse_present and update.sys_bp==state['ABP_sys']

def test_validation():
    assert validate_selection('NALS',TOPIC)['programme']=='NALS'
    with pytest.raises(ValueError): configure_neonatal_advanced(source(),context='unknown')
    with pytest.raises(ValueError): configure_neonatal_advanced(source(),entry='unknown')
