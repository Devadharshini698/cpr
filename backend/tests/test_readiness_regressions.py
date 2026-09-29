import asyncio
import json
from pathlib import Path
import numpy as np
import pytest
from fastapi import HTTPException
from ecg_state import ECGState, RhythmType
from simman_engine.waveform_generator import WaveformGenerator
from physiology import normalize_monitor_state
from debrief_jobs import JobStore
import prebrief


@pytest.mark.parametrize('rhythm', list(RhythmType))
def test_all_waveform_channels_finite(rhythm):
    state = ECGState(rhythm=rhythm)
    generator = WaveformGenerator()
    for method in (generator.generate, generator.generate_pleth, generator.generate_abp,
                   generator.generate_pap, generator.generate_etco2):
        samples = method(state, 2048)
        assert samples.shape == (2048,)
        assert np.isfinite(samples).all()


def test_vt_with_pulse_has_pressure_and_pulseless_vt_does_not():
    for pulse in (True, False):
        state = ECGState(rhythm=RhythmType.VT, heart_rate=160, pulse_present=pulse)
        generator = WaveformGenerator()
        generator.generate(state, 2048)
        pressure = generator.generate_abp(state, 2048)
        assert bool(np.any(pressure)) == pulse


def test_arrest_does_not_inherit_normal_cardiac_output():
    state = normalize_monitor_state({'rhythm':'VF','HR':80,'pulse_rate':80,'CO':5,
                                     'ABP_sys':120,'ABP_dia':80,'avRR':0,'etCO2':35})
    assert state['CO'] == state['ABP_sys'] == state['pulse_rate'] == state['HR'] == state['etCO2'] == 0


def test_invalid_bp_is_rejected():
    with pytest.raises(ValueError):
        normalize_monitor_state({'HR':80,'ABP_sys':60,'ABP_dia':90})


def test_prebrief_ownership_consent_and_no_clinical_events(tmp_path, monkeypatch):
    monkeypatch.setattr(prebrief, 'ROOT', tmp_path)
    record = 'a' * 32
    (tmp_path / (record+'.json')).write_text(json.dumps({'owner_id':1,'name':'Training Alias','role':'Leader','recording_id':record}))
    with pytest.raises(HTTPException):
        prebrief.validate_prebrief({'recording_ids':[record]}, {'id':1})
    with pytest.raises(HTTPException):
        prebrief.validate_prebrief({'consent_confirmed':True,'recording_ids':[record]}, {'id':2})
    result = prebrief.validate_prebrief({'consent_confirmed':True,'recording_ids':[record]}, {'id':1})
    assert result['members'][0]['name'] == 'Training Alias'
    assert 'event_log' not in result
    assert 'owner_id' not in result['members'][0]


class Context:
    def __init__(self, value): self.value = value
    async def __aenter__(self): return self.value
    async def __aexit__(self, *args): pass


class Connection:
    def __init__(self, fail=False, owned=True):
        self.fail, self.owned = fail, owned
        self.rowcount = 1
        self.events = []
    def cursor(self): return Context(self)
    async def begin(self): self.events.append('begin')
    async def commit(self): self.events.append('commit')
    async def rollback(self): self.events.append('rollback')
    async def fetchone(self): return (7,)
    async def execute(self, sql, args):
        if 'UPDATE debrief_jobs' in sql: self.rowcount = int(self.owned)
        if 'INSERT INTO debrief_reports' in sql:
            self.events.append('save')
            if self.fail: raise RuntimeError('simulated DB failure')


@pytest.mark.parametrize('fail,owned', [(False,True),(True,True),(False,False)])
def test_report_completion_transaction(fail, owned):
    conn = Connection(fail, owned)
    pool = type('Pool', (), {'acquire': lambda self: Context(conn)})()
    operation = JobStore(pool).complete({'job_id':'job','lease_token':'lease','session_code':'TEST01'}, {})
    if fail:
        with pytest.raises(RuntimeError): asyncio.run(operation)
        assert conn.events == ['begin','save','rollback']
    else:
        assert asyncio.run(operation) == owned
        assert conn.events == (['begin','save','commit'] if owned else ['begin','rollback'])


def test_diarization_workers_do_not_receive_token_argument():
    source = (Path(__file__).parents[1]/'debriefing/ingestion/diarization.py').read_text(encoding='utf-8')
    assert 'cmd = [_sys.executable, str(worker), audio_for_pyannote]' in source
    assert 'audio_for_pyannote, hf_token]' not in source


def test_audio_model_loading_and_inference_run_off_event_loop(tmp_path, monkeypatch):
    import sys
    import threading
    import types
    import audio_debrief_jobs
    main_thread = threading.get_ident()
    calls = []
    class Pipeline:
        def __init__(self):
            assert threading.get_ident() != main_thread
            calls.append('load')
        def process(self, *args, **kwargs):
            assert threading.get_ident() != main_thread
            calls.append('process')
            return []
    monkeypatch.setitem(sys.modules, 'debriefing.ingestion.audio_pipeline',
                        types.SimpleNamespace(AudioPipeline=Pipeline, WHISPER_AVAILABLE=True))
    audio = tmp_path / 'test.wav'
    audio.write_bytes(b'test')
    class Store:
        async def claim(self): return {'audio_path':str(audio),'session_code':'TEST01'}
        async def renew(self, job): return False
        async def fail(self, job, error): raise AssertionError(type(error).__name__)
    assert asyncio.run(audio_debrief_jobs.run_one(Store()))
    assert calls == ['load', 'process']
