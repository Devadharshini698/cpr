import asyncio
import numpy as np
import pytest
from unittest.mock import AsyncMock
from physiology import apply_perfusion_intent
from ecg_state import ECGState
from simman_engine.waveform_generator import WaveformGenerator
from local_request_speech import suggest_channel
import socket_manager as sm

def test_organised_ecg_alone_does_not_establish_rosc():
    state=apply_perfusion_intent({'rhythm':'NSR','HR':75,'pulse_rate':0,'SpO2':95,'ABP_sys':0,'ABP_dia':0}, {'HR':75})
    assert state['pulse_rate']==0 and state['SpO2']==0

def test_explicit_rosc_restores_pleth_with_reviewed_values():
    state=apply_perfusion_intent({'rhythm':'NSR','HR':75,'pulse_rate':0,'emd_pea':True,
        'SpO2':95,'ABP_sys':90,'ABP_dia':60}, {'pulse_present':True})
    assert state['pulse_rate']==75 and state['emd_pea'] is False
    generator=WaveformGenerator()
    telemetry=ECGState(rhythm='NSR',heart_rate=state['HR'],pulse_present=state['pulse_rate']>0,spo2=state['SpO2'],sys_bp=state['ABP_sys'],dia_bp=state['ABP_dia'])
    generator.generate(telemetry,1000)
    assert np.ptp(generator.generate_pleth(telemetry,1000))>0.1

@pytest.mark.parametrize('rhythm',['VF','ASYSTOLE','PEA'])
def test_pulse_cannot_be_asserted_for_arrest_rhythm(rhythm):
    with pytest.raises(ValueError): apply_perfusion_intent({'rhythm':rhythm,'HR':75}, {'pulse_present':True})

@pytest.mark.parametrize('text,channel',[('Please show ECG','ecg'),('Check blood pressure','nibp'),('ECG and blood pressure',None),('give adrenaline',None)])
def test_speech_only_suggests_unambiguous_monitoring(text,channel):
    assert suggest_channel(text)==channel

def test_student_cannot_approve_their_request(monkeypatch):
    monkeypatch.setattr(sm.sio,'get_session',AsyncMock(return_value={'role':'student','session_code':'TEST01'}))
    pool=AsyncMock();monkeypatch.setattr(sm,'get_db_pool',pool)
    result=asyncio.run(sm.resolve_monitor_request('student',{'id':'x','decision':'reveal'}))
    assert result['status']=='error'
    pool.assert_not_called()


@pytest.mark.parametrize('field,value', [('SpO2',97),('ABP_sys',110),('ABP_dia',70),('PAP_sys',24),('PAP_dia',12),('CO',5)])
def test_positive_measurement_on_stale_pulseless_state_explains_rosc(field,value):
    with pytest.raises(ValueError, match='still set to pulseless'):
        apply_perfusion_intent({'rhythm':'NSR','HR':75,'pulse_rate':0,field:value},{field:value})


@pytest.mark.parametrize('field,value', [('SpO2',97),('ABP_sys',110),('ABP_dia',70),('PAP_sys',24),('PAP_dia',12),('CO',5),('Tperi',36.5),('Tblood',37.2)])
def test_separate_edits_after_confirmed_rosc_remain_editable(field,value):
    state=apply_perfusion_intent({'rhythm':'NSR','HR':75,'pulse_rate':0,'emd_pea':True,'ABP_sys':90,'ABP_dia':60,'SpO2':95}, {'pulse_present':True})
    state.update({'ABP_sys':110,'ABP_dia':70,'PAP_sys':24,'PAP_dia':12,field:value})
    result=apply_perfusion_intent(state,{field:value})
    assert result[field]==value and result['pulse_rate']==75


def test_co2_edit_explains_zero_ventilation_rate():
    with pytest.raises(ValueError,match='ventilation rate'):
        apply_perfusion_intent({'rhythm':'NSR','HR':75,'pulse_rate':75,'avRR':0,'etCO2':35},{'etCO2':35})
    result=apply_perfusion_intent({'rhythm':'NSR','HR':75,'pulse_rate':75,'avRR':16,'etCO2':35},{'etCO2':35,'avRR':16})
    assert result['etCO2']==35
