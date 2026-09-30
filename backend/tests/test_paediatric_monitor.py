import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
import socket_manager as sm
import numpy as np
from ecg_state import ECGState
from simman_engine.waveform_generator import WaveformGenerator
from debriefing.scenarios.paediatric_respiratory import configure_respiratory_case
from models import DEFAULT_MONITOR_STATE

@pytest.mark.parametrize('profile',['infant','child'])
@pytest.mark.parametrize('severity',['distress','failure'])
def test_stage_to_waveform_sync(monkeypatch,profile,severity):
    case=configure_respiratory_case({'patient':{},'location':'ER','location_label':'ER','level':'beginner','discipline_labels':['Nurse']},profile,severity)
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=SimpleNamespace(heart_rate=80,spo2=98,sys_bp=120,dia_bp=80,pap_sys=20,pap_dia=10,etco2=35,resp_rate=12))
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    state={**DEFAULT_MONITOR_STATE,**case['initial_state'],'student_display':dict.fromkeys(sm.STUDENT_DISPLAY_KEYS,False)}
    thresholds=state['alarm_thresholds'].copy()
    assert state['NBP_sys'] is None and state['show_ibp'] is False
    for stage in case['conditions']:
        state.update(stage['state'])
        asyncio.run(sm._sync_waveform_engine(state,'PEDIATRIC_TEST'))
        command=engine.apply_command.call_args.args[0]
        assert command.heart_rate==state['HR']
        assert command.resp_rate==state['avRR']
        assert command.etco2==state['etCO2']
        assert command.spo2==state['SpO2']
        assert command.sys_bp==state['ABP_sys']
        assert command.pulse_present
        telemetry=ECGState(rhythm=command.rhythm,heart_rate=command.heart_rate,
            pulse_present=command.pulse_present,spo2=command.spo2,
            sys_bp=command.sys_bp,dia_bp=command.dia_bp,
            resp_rate=command.resp_rate,etco2=command.etco2)
        generator=WaveformGenerator()
        for output in (generator.generate(telemetry,5000),generator.generate_pleth(telemetry,5000),generator.generate_etco2(telemetry,5000)):
            assert np.isfinite(output).all() and np.ptp(output)>0.1
        assert state['alarm_thresholds']==thresholds
        assert not any(state['student_display'].values())
        alarms=sm.compute_alarms(state)
        if stage['id']=='respiratory_failure':
            assert {'avRR LOW','SpO2 LOW','etCO2 HIGH','DESAT'} <= set(alarms)
        if stage['id']=='response_to_support':
            assert not alarms
