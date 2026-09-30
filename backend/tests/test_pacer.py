import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock
import numpy as np
import pytest
from pacer import update_pacer,stop_pacer
from ecg_state import ECGState
from simman_engine.waveform_generator import WaveformGenerator
import socket_manager as sm

def baseline():
    return dict(rhythm='SINUS_BRADY',HR=40,pulse_rate=40,emd_pea=False,ABP_sys=90,ABP_dia=55,
        MAP=67,SpO2=94,avRR=16,etCO2=36,PAP_sys=0,PAP_dia=0,CO=3)

def running():
    return update_pacer(baseline(),dict(visible=True,student_enabled=True,pads_connected=True,enabled=True,rate=70,output=60),'instructor')

def test_permission_and_capture_separation():
    with pytest.raises(ValueError): update_pacer(baseline(),{'enabled':True},'student')
    state=running()
    with pytest.raises(ValueError): update_pacer(state,{'electrical_capture':True},'student')
    assert state['HR']==40 and state['pulse_rate']==40
    electrical=update_pacer(state,{'electrical_capture':True},'instructor')
    assert electrical['HR']==70 and electrical['pulse_rate']==0 and electrical['ABP_sys']==0
    both=update_pacer(electrical,{'mechanical_capture':True},'instructor')
    assert both['pulse_rate']==70 and both['ABP_sys']==90 and both['SpO2']==94
    stopped=update_pacer(both,{'enabled':False},'student')
    for k,v in baseline().items(): assert stopped[k]==v
    assert not stopped['pacer']['electrical_capture']

def test_changes_revoke_capture_without_inventing_threshold():
    state=update_pacer(running(),{'electrical_capture':True,'mechanical_capture':True},'instructor')
    for field,value in [('rate',80),('output',100)]:
        changed=update_pacer(state,{field:value},'student')
        assert changed['HR']==40 and not changed['pacer']['electrical_capture']
    assert stop_pacer(state)['HR']==40
    assert not stop_pacer(state)['pacer']['enabled']
    revoked=update_pacer(state,{'visible':False},'instructor')
    assert not revoked['pacer']['student_enabled'] and not revoked['pacer']['enabled']

@pytest.mark.parametrize('changes',[{'rate':float('nan')},{'rate':29},{'rate':181},{'output':201},{'output':-1},{'rate':True},{'enabled':'yes'},{'unknown':1},{'mechanical_capture':True}])
def test_invalid(changes):
    with pytest.raises(ValueError): update_pacer(running(),changes,'instructor')

@pytest.mark.parametrize('change',[{'pulse_rate':0},{'rhythm':'VF'},{'rhythm':'VT'},{'patient_profile':'child'},{'patient_profile':'infant'}])
def test_unsupported_patient(change):
    with pytest.raises(ValueError): update_pacer({**baseline(),**change},dict(visible=True,pads_connected=True,enabled=True),'instructor')

def test_no_mutation():
    state=running();before=deepcopy(state)
    update_pacer(state,{'electrical_capture':True},'instructor')
    assert state==before

def test_instructor_can_pace_before_student_disclosure():
    state=update_pacer(baseline(),dict(pads_connected=True,output=50,enabled=True),'instructor')
    assert state['pacer']['enabled'] and not state['pacer']['visible']
    with pytest.raises(ValueError):
        update_pacer(state,{'output':60},'student')
    captured=update_pacer(state,{'electrical_capture':True},'instructor')
    assert captured['HR']==70 and captured['pacer']['electrical_capture']
    assert not captured['pacer']['visible']

def test_hidden_pacer_sync_produces_streamed_spikes_and_capture(monkeypatch):
    from simman_engine.state_machine import SimulationEngine, SAMPLES_PER_PKT
    from simman_engine.lead_generator import generate_all_leads
    engine=SimulationEngine()
    monkeypatch.setattr(sm,'get_session_engine',lambda code:engine)
    monkeypatch.setattr(engine,'start',AsyncMock())
    state=update_pacer(baseline(),dict(pads_connected=True,output=50,enabled=True),'instructor')
    async def verify():
        for capture in (False,True):
            current=update_pacer(state,{'electrical_capture':capture},'instructor')
            await sm._sync_waveform_engine(current,'TEST')
            assert engine.state.pacer_active
            assert engine.state.pacer_capture==capture
            blocks=[]
            for _ in range(200):
                signal=engine._generator.generate(engine.state,SAMPLES_PER_PKT)
                blocks.append(generate_all_leads(signal,engine.state,512)['II'])
            signal=np.concatenate(blocks)
            from scipy.signal import find_peaks
            peaks,_=find_peaks(signal,height=2,distance=256)
            assert len(peaks)>=10
            assert np.median(np.diff(peaks))/512==pytest.approx(60/70,abs=.01)
            if capture:
                # A broad captured complex follows each narrow stimulus.
                assert all(np.max(signal[p+20:p+65])>.8 for p in peaks if p+65<len(signal))
    asyncio.run(verify())

def test_waveform_spikes_and_capture():
    np.random.seed(7)
    normal=WaveformGenerator().generate(ECGState(rhythm='SINUS_BRADY',heart_rate=40),5120)
    np.random.seed(7)
    spikes=WaveformGenerator().generate(ECGState(rhythm='SINUS_BRADY',heart_rate=40,pacer_active=True,pacer_rate=70),5120)
    assert np.max(spikes-normal)>2
    generator=WaveformGenerator()
    captured=ECGState(heart_rate=70,pacer_active=True,pacer_rate=70,pacer_capture=True,pulse_present=False)
    assert generator._rr(captured)==60/70
    ecg=generator.generate(captured,5120)
    assert np.isfinite(ecg).all() and np.max(ecg)>2
    assert np.max(np.abs(generator.generate_pleth(captured,5120)))==0
    captured.pulse_present=True
    generator.generate(captured,5120)
    assert np.ptp(generator.generate_pleth(captured,5120))>0.1

@pytest.mark.parametrize('rate',[50,70,120,180])
def test_paced_morphology_uses_fixed_activation_timing(rate):
    rr=60/rate
    t=np.arange(0,min(.45,rr),.001)
    phases=(.41-.060/rr+t/rr)%1
    signal=WaveformGenerator._paced_complex(phases,rate)
    assert signal[0]>2.3
    assert abs(signal[8])<.01  # QRS begins just after the stimulus
    assert signal[18]<-.1
    assert signal[60]>1.05  # R timing does not drift with rate
    assert signal[140]<-.3
    assert abs(signal[168])<.01  # 160 ms wide ventricular complex
    assert np.min(signal[200:])<-.4  # discordant broad T wave

def test_socket_denies_unjoined_client(monkeypatch):
    monkeypatch.setattr(sm.sio,'get_session',AsyncMock(return_value={}))
    assert asyncio.run(sm.pacer_update('unknown',{'enabled':True}))['status']=='error'

def test_pacer_events_are_debrief_compatible():
    from debriefing.contracts import Event
    event=Event(event_id='pacer_test',event_type='PACER_ACTIVITY',timestamp_ms=0,
        actor_role='student',source='simman',payload={'changes':{'output':60}})
    assert event.event_type=='PACER_ACTIVITY'

def test_mode_permission_validation_and_capture_reset():
    state=update_pacer(running(),{'electrical_capture':True,'mechanical_capture':True},'instructor')
    demand=update_pacer(state,{'mode':'demand'},'student')
    assert demand['pacer']['mode']=='demand'
    assert not demand['pacer']['electrical_capture'] and demand['HR']==40
    with pytest.raises(ValueError): update_pacer(state,{'mode':'invalid'},'instructor')
    hidden=update_pacer(baseline(),{'mode':'demand'},'instructor')
    with pytest.raises(ValueError): update_pacer(hidden,{'mode':'fixed'},'student')

def test_demand_sensing_resets_escape_timer_across_packets():
    generator=WaveformGenerator()
    def block(n, qrs=False, beat=0):
        generator._last_phases=np.full(n,.41 if qrs else .7)
        generator._last_beat_indices=np.full(n,beat)
        return generator._demand_stimuli(np.full(n,1.0 if qrs else 0),60)
    assert not block(400).any()
    assert not block(1,True,1).any()  # sensed QRS resets timer
    assert not block(400).any()
    assert block(120).max()==2.4
    # Repeated intrinsic QRS faster than escape interval inhibits output.
    for beat in range(2,8):
        assert not block(1,True,beat).any()
        assert not block(300).any()

@pytest.mark.parametrize('mode,expected',[('fixed',True),('demand',False)])
def test_live_generator_demand_vs_fixed_with_faster_intrinsic(mode,expected):
    np.random.seed(7)
    generator=WaveformGenerator()
    state=ECGState(heart_rate=90,pacer_active=True,pacer_rate=60,pacer_mode=mode,hrv_std=0)
    blocks=[generator.generate(state,26) for _ in range(200)]
    assert bool(np.max(np.concatenate(blocks))>2)==expected

def test_demand_delivers_when_intrinsic_slow_and_can_capture():
    generator=WaveformGenerator()
    state=ECGState(rhythm='SINUS_BRADY',heart_rate=40,pacer_active=True,pacer_rate=70,pacer_mode='demand',hrv_std=0)
    assert max(np.max(generator.generate(state,26)) for _ in range(200))>2
    state.pacer_capture=True
    assert generator._rr(state)==60/70
    assert max(np.max(generator.generate(state,26)) for _ in range(200))>2
