from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
import wave


@dataclass
class Turn:
    start: float
    end: float


def test_community_worker_prefers_exclusive_speaker_turns():
    from debriefing.ingestion.diarize_worker_community import _turns_from_output

    output = SimpleNamespace(
        speaker_diarization=[(Turn(0, 2), "original")],
        exclusive_speaker_diarization=[
            (Turn(2.5, 3.0), "SPEAKER_01"),
            (Turn(0.1, 2.4), "SPEAKER_00"),
        ],
    )
    assert _turns_from_output(output) == [
        {"speaker": "SPEAKER_00", "start_ms": 100, "end_ms": 2400},
        {"speaker": "SPEAKER_01", "start_ms": 2500, "end_ms": 3000},
    ]


def test_community_worker_loads_preprocessed_pcm_without_torchcodec(tmp_path):
    from debriefing.ingestion.diarize_worker_community import _load_preprocessed_wav

    audio = tmp_path / "sample.wav"
    with wave.open(str(audio), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"\x00\x00\xff\x7f\x00\x80")

    loaded = _load_preprocessed_wav(str(audio))
    assert loaded["sample_rate"] == 16000
    assert loaded["waveform"].shape == (1, 3)
    assert loaded["waveform"][0, 0].item() == 0
    assert loaded["waveform"][0, 1].item() > 0.99
    assert loaded["waveform"][0, 2].item() == -1


def test_turbo_uses_supported_faster_whisper_repository(tmp_path, monkeypatch):
    from debriefing.ingestion import whisper_pipeline

    model_dir = tmp_path / "mobiuslabsgmbh--faster-whisper-large-v3-turbo"
    model_dir.mkdir()
    for name in ("config.json", "model.bin", "tokenizer.json", "vocabulary.json"):
        (model_dir / name).write_bytes(b"test")
    assert whisper_pipeline._local_whisper_model_path("large-v3-turbo", tmp_path) == str(model_dir)


def test_turbo_translation_uses_medium_model(monkeypatch):
    from debriefing.ingestion import whisper_pipeline
    import faster_whisper

    loaded = []
    monkeypatch.setattr(whisper_pipeline, "_local_whisper_model_path", lambda name, cache: name)
    monkeypatch.setattr(faster_whisper, "WhisperModel", lambda path, **kwargs: loaded.append((path, kwargs)) or object())
    pipeline = object.__new__(whisper_pipeline.WhisperPipeline)
    pipeline.model_size = "large-v3-turbo"
    pipeline.model = object()
    pipeline._translation_model = None
    assert pipeline._model_for_task("translate") is pipeline._translation_model
    assert pipeline.active_model_size == "medium"
    assert loaded == [("medium", {"device": "cpu", "compute_type": "int8"})]
    assert pipeline._model_for_task("transcribe") is pipeline.model
    assert pipeline.active_model_size == "large-v3-turbo"


def test_community_worker_uses_separate_python_and_no_token_argument(tmp_path, monkeypatch):
    from debriefing.ingestion import diarization

    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"test")
    community_python = tmp_path / "community-python.exe"
    community_python.write_bytes(b"test")
    monkeypatch.setenv("DIARIZATION_MODEL", "community-1")
    monkeypatch.setenv("DIARIZATION_BACKEND", "pyannote")
    monkeypatch.setenv("DEBRIEF_COMMUNITY_PYTHON", str(community_python))
    monkeypatch.setenv("HF_TOKEN", "private-test-token")
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return SimpleNamespace(returncode=0, stdout='[{"speaker":"SPEAKER_00","start_ms":0,"end_ms":1000}]')

    monkeypatch.setattr("subprocess.run", fake_run)
    class FakeRoleAssigner:
        def assign(self, aligned, **kwargs):
            return {"SPEAKER_00": "team_leader"}

        def apply_role_map(self, aligned, role_map):
            return [{**segment, "role": "team_leader"} for segment in aligned]

    monkeypatch.setattr(diarization, "RoleAssigner", FakeRoleAssigner)
    segments = diarization._mode_b_pyannote(
        [{"timestamp_ms": 0, "end_ms": 1000, "text": "I am the team leader."}],
        str(audio), None, 1,
    )
    assert seen["command"][0] == str(community_python)
    assert seen["command"][1].endswith("diarize_worker_community.py")
    assert "private-test-token" not in seen["command"]
    assert segments[0]["speaker_label"] == "SPEAKER_00"


def test_prebrief_embedding_matches_only_distinct_voice(monkeypatch):
    import numpy as np
    from debriefing.ingestion import diarize_worker_community as worker

    output = SimpleNamespace(
        speaker_diarization=SimpleNamespace(labels=lambda: ['SPEAKER_00', 'SPEAKER_01']),
        speaker_embeddings=np.array([[1., 0., 0.], [0., 1., 0.]], dtype='float32'),
    )
    clips = [
        {'name': 'Arun', 'role': 'Team Leader', 'path': 'arun'},
        {'name': 'Priya', 'role': 'Chest Compression', 'path': 'priya'},
    ]
    monkeypatch.setattr(worker, '_enrollment_embedding',
                        lambda pipeline, path: np.array([0.98, 0.20, 0.]) if path == 'arun'
                        else np.array([0.1, 0.99, 0.]))
    matches = worker._match_enrollments(output, clips, object())
    assert matches['SPEAKER_00']['name'] == 'Arun'
    assert matches['SPEAKER_01']['name'] == 'Priya'


def test_prebrief_embedding_rejects_ambiguous_match(monkeypatch):
    import numpy as np
    from debriefing.ingestion import diarize_worker_community as worker

    output = SimpleNamespace(
        speaker_diarization=SimpleNamespace(labels=lambda: ['SPEAKER_00', 'SPEAKER_01']),
        speaker_embeddings=np.array([[1., 0.], [0.99, 0.1]], dtype='float32'),
    )
    monkeypatch.setattr(worker, '_enrollment_embedding', lambda pipeline, path: np.array([1., 0.]))
    assert worker._match_enrollments(output, [{'name': 'Arun', 'role': 'Leader', 'path': 'arun'}], object()) == {}


def test_verified_prebrief_identity_overrides_noisy_introduction():
    from debriefing.ingestion.role_assigner import RoleAssigner

    assigner = RoleAssigner()
    segments = [{'speaker_label': 'SPEAKER_00', 'timestamp_ms': 0, 'end_ms': 1200,
                 'text': 'I am Rahul, airway manager.'}]
    roles = assigner.assign(segments, verified_bindings={
        'SPEAKER_00': {'name': 'Priya', 'role': 'compressor',
                       'evidence': 'prebrief_voice_match', 'score': 0.84},
    })
    attributed = assigner.apply_role_map(segments, roles)
    assert attributed[0]['speaker_name'] == 'Priya'
    assert attributed[0]['role'] == 'compressor'
    assert attributed[0]['role_evidence'] == 'prebrief_voice_match'
    assert attributed[0]['speaker_match_score'] == 0.84


def test_community_match_reaches_transcript_role(tmp_path, monkeypatch):
    from debriefing.ingestion import diarization

    audio = tmp_path / 'sample.wav'
    audio.write_bytes(b'test')
    interpreter = tmp_path / 'python.exe'
    interpreter.write_bytes(b'test')
    monkeypatch.setenv('DIARIZATION_MODEL', 'community-1')
    monkeypatch.setenv('DIARIZATION_BACKEND', 'pyannote')
    monkeypatch.setenv('DEBRIEF_COMMUNITY_PYTHON', str(interpreter))
    monkeypatch.setattr('subprocess.run', lambda command, **kwargs: SimpleNamespace(
        returncode=0, stdout='{"turns":[{"speaker":"SPEAKER_00","start_ms":0,"end_ms":1200}],'
        '"enrollment_matches":{"SPEAKER_00":{"name":"Priya","role":"Chest Compression","score":0.84}}}',
    ))
    segments = diarization._mode_b_pyannote(
        [{'timestamp_ms': 0, 'end_ms': 1200, 'text': 'I am Rahul, airway manager.'}],
        str(audio), None, 1,
        enrollment_clips=[{'name': 'Priya', 'role': 'Chest Compression', 'path': str(audio)}],
    )
    assert segments[0]['speaker_name'] == 'Priya'
    assert segments[0]['role'] == 'compressor'
    assert segments[0]['role_evidence'] == 'prebrief_voice_match'
