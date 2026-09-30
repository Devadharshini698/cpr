import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import numpy as np
import pytest
from curriculum import catalogue,validate_selection
from debriefing.scenarios.neonatal_transition import configure_neonatal_transition,PROFILES,SETTINGS,TOPIC
from debriefing.scenarios.teaching_design import apply_teaching_design
from physiology import normalize_monitor_state
from pacer import update_pacer
from ecg_state import ECGState
from simman_engine.waveform_generator import WaveformGenerator
import socket_manager as sm

def source(level='beginner',roles=None):
    return dict(patient={'age':65},location='ER',location_label='ER',level=level,
        discipline=roles or ['doctor','nurse'],discipline_labels=['Selected team'],curriculum={'programme':'NALS','subtopic':TOPIC})

@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('setting',SETTINGS)
@pytest.mark.parametrize('course',['vigorous','poor_transition'])
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
@pytest.mark.parametrize('roles',[['doctor'],['nurse'],['doctor','nurse'],['allied','physiotherapist']])
def test_cases(profile,setting,course,level,roles):
    original=source(level,roles)
    case=apply_teaching_design(configure_neonatal_transition(original,profile,course,setting))
    assert original['patient']['age']==65
    assert case['patient']['age']==0 and case['patient']['weight_kg']==PROFILES[profile][1]
    assert case['monitor_schema']=='neonatal-transition-1'
    assert bool(case['hints'])==(level=='beginner')
    assert len(case['teaching_plan']['team_tasks'])==len(roles)
    assert case['initial_state']['NBP_sys'] is None and not case['initial_state']['show_ibp']
    for stage in case['conditions']:
        state=stage['state']
        assert normalize_monitor_state(state)==state
        assert state['patient_profile']=='neonate' and state['pulse_rate']>0
        assert 'student_display' not in state
        assert state['etCO2']==0
        alarms=sm.compute_alarms(state)
        if stage['id']=='neonatal_poor_transition':
            assert {'APNEA','HR LOW','DESAT','Tperi LOW'}<=set(alarms)
        else: assert not alarms
    with pytest.raises(ValueError,match='adult'):
        update_pacer(case['initial_state'],{'enabled':True,'pads_connected':True},'instructor')

def test_only_first_neonatal_module_enabled():
    assert {TOPIC,'Ventilation support','Advanced neonatal resuscitation','Post-resuscitation stabilisation','Neonatal combined case — configurable progression'}==set(catalogue()['NALS']['launchable_topics'])
    assert validate_selection('NALS',TOPIC)['programme']=='NALS'
    with pytest.raises(ValueError): validate_selection('NALS','Unknown neonatal topic')

@pytest.mark.parametrize('args',[('child','vigorous','delivery_room'),('term','arrest','theatre'),('term','vigorous','unknown')])
def test_bad_options(args):
    with pytest.raises(ValueError): configure_neonatal_transition(source(),*args)

def test_neonatal_waveform_sync_and_stage_age(monkeypatch):
    case=configure_neonatal_transition(source())
    engine=SimpleNamespace(start=AsyncMock(),apply_command=AsyncMock(),state=ECGState())
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    for condition in case['conditions']:
        state=condition['state']
        asyncio.run(sm._sync_waveform_engine(state,'NEONATAL_QA'))
        command=engine.apply_command.call_args.args[0]
        assert command.heart_rate==state['HR'] and command.resp_rate==state['avRR']
        assert command.spo2==state['SpO2'] and command.pulse_present
        telemetry=ECGState(**command.model_dump(exclude_none=True))
        generator=WaveformGenerator()
        assert np.ptp(generator.generate(telemetry,1024))>.1
        assert np.ptp(generator.generate_pleth(telemetry,1024))>.1
        assert np.isfinite(generator.generate_etco2(telemetry,1024)).all()
