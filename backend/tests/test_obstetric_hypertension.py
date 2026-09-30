import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from debriefing.scenarios.obstetric_hypertension import configure_obstetric_hypertension,CONTEXTS,SETTINGS,ENTRIES,TOPIC
from physiology import normalize_monitor_state
from curriculum import validate_selection
from ecg_state import ECGState
import socket_manager as sm

def source(level='beginner'):
    return dict(patient={},location='ER',location_label='ER',level=level,discipline_labels=['Nurse','Doctor'])

@pytest.mark.parametrize('context',CONTEXTS)
@pytest.mark.parametrize('setting',SETTINGS)
@pytest.mark.parametrize('entry',ENTRIES)
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
def test_cases(context,setting,entry,level):
    original=source(level)
    case=configure_obstetric_hypertension(original,context,entry,setting)
    assert original['patient']=={}
    assert case['conditions'][0]['id']=='obht_'+entry
    assert case['monitor_schema']=='obstetric-hypertension-1'
    assert bool(case['hints'])==(level=='beginner')
    assert case['patient']['postpartum_hours']==(24 if context=='postpartum' else None)
    assert case['initial_state']['NBP_sys'] is None
    for stage in case['conditions']:
        state=stage['state']
        assert normalize_monitor_state(state)==state and state['pulse_rate']>0
        assert state['etCO2']==0 and 'student_display' not in state
        if stage['id'] not in ('obht_response','obht_handover'):
            assert {'ABP_sys HIGH','ABP_dia HIGH'}<=set(sm.compute_alarms(state))
        else: assert not sm.compute_alarms(state)

def test_sync(monkeypatch):
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=ECGState())
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    for stage in configure_obstetric_hypertension(source())['conditions']:
        state=stage['state'];asyncio.run(sm._sync_waveform_engine(state,'HT_QA'))
        command=engine.apply_command.call_args.args[0]
        assert command.heart_rate==state['HR'] and command.sys_bp==state['ABP_sys']
        assert command.dia_bp==state['ABP_dia'] and command.pulse_present

def test_validation():
    assert validate_selection('ALSO',TOPIC)['programme']=='ALSO'
    for kwargs in ({'context':'unknown'},{'entry':'unknown'},{'setting':'unknown'}):
        with pytest.raises(ValueError): configure_obstetric_hypertension(source(),**kwargs)
