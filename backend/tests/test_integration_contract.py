from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError
from debrief_adapter import DebriefAdapter
from debriefing.contracts import Session
from debriefing.engine import DebriefEngine
from debriefing.acls_engine import ScenarioClassifier
from debriefing.rhythms import RHYTHMS, rhythm_event, normalize_engine_events
from debriefing.schemas.event_schema import Severity, EventType
from audio_debrief_jobs import _log_entries
from synthetic_transcript import generate_synthetic_segments
from ecg_state import ECGState, RhythmType
from simman_engine.waveform_generator import WaveformGenerator
from simman_engine.state_machine import get_session_engine
from debriefing.scenarios.generator import ScenarioGenerator


def test_vf_scenario_starts_in_nonperfusing_vf_arrest():
    condition = ScenarioGenerator()._derive_conditions("VF")[0]
    state = condition["state"]
    assert condition["name"] == "VF Arrest"
    assert state["rhythm"] == "Ventricular Fibrillation"
    assert all(state[field] == 0.0 for field in ("HR", "pulse_rate", "ABP_sys", "ABP_dia", "MAP", "SpO2", "avRR", "etCO2", "PAP_sys", "PAP_dia"))


def test_generator_does_not_always_choose_the_first_vf_template():
    generator = ScenarioGenerator()
    rhythms = {
        generator.generate("beginner", "ER", ["doctor"], "ER", seed=seed)["rhythm_type"]
        for seed in range(12)
    }
    # Beginner ER has VF, PEA and asystole templates.  Generation must choose
    # a candidate rather than deterministically returning T001 (VF).
    assert {"VF", "PEA", "asystole"}.issubset(rhythms)


@pytest.mark.parametrize("requested,expected_name,expected_rhythm", [
    ("PEA", "PEA Arrest", "Sinus Rhythm"),
    ("asystole", "Asystole Arrest", "Asystole"),
    ("VF", "VF Arrest", "Ventricular Fibrillation"),
])
def test_explicit_rhythm_request_controls_opening_physiology(requested, expected_name, expected_rhythm):
    spec = ScenarioGenerator().generate(
        "beginner", "ER", ["doctor"], "ER", rhythm_hint=requested
    )
    assert spec["rhythm_type"] == requested
    assert spec["conditions"][0]["name"] == expected_name
    assert spec["initial_state"]["rhythm"] == expected_rhythm


def test_custom_scenario_parser_does_not_find_er_inside_create():
    from debriefing.scenarios.instructor_listener import InstructorListener
    parsed = InstructorListener().parse_text("Create an advanced ICU PEA scenario for doctors and nurses.")
    assert parsed["location"] == "ICU"
    assert parsed["rhythm_hint"] == "PEA"


def test_structured_launch_rhythm_is_available_to_debrief_classification():
    canonical = DebriefAdapter().convert({"session_code": "PEA-LAUNCH", "current_scenario_json": '{"title":"PEA test","rhythm_type":"PEA"}'}, [
        {"event_id": "launch", "timestamp_ms": 0, "event": "Scenario launched", "event_type": "rhythm_change",
         "source": "simman", "payload": {"rhythm": "Sinus Rhythm", "pulse_present": False, "emd_pea": True}},
    ])
    result = DebriefEngine(enable_narrative=False).generate(canonical)
    assert result["classification"]["sub_type"] == "PEA"


def test_pulseless_vf_keeps_a_chaotic_ecg_but_no_mechanical_traces():
    state = ECGState(rhythm=RhythmType.VF, heart_rate=0.0)
    generator = WaveformGenerator()
    ecg = generator.generate(state, 512)
    assert np.std(ecg) > 0.08, "VF must not be rendered as a flatline"
    assert not generator.generate_pleth(state, 512).any()
    assert not generator.generate_abp(state, 512).any()
    assert not generator.generate_pap(state, 512).any()
    assert not generator.generate_etco2(state, 512).any()


def test_waveform_engines_are_isolated_by_session_code():
    vf_engine = get_session_engine("VF-SESSION")
    other_engine = get_session_engine("OTHER-SESSION")
    assert vf_engine is not other_engine
    vf_engine.state.rhythm = RhythmType.VF
    vf_engine.state.heart_rate = 0.0
    assert other_engine.state.rhythm != RhythmType.VF


def test_role_assignment_does_not_invent_roles_from_speaking_duration():
    from debriefing.ingestion.role_assigner import RoleAssigner
    assigned = RoleAssigner().assign([
        {"speaker_label": "SPEAKER_00", "timestamp_ms": 0, "end_ms": 3000, "text": "Okay."},
        {"speaker_label": "SPEAKER_01", "timestamp_ms": 3000, "end_ms": 5000, "text": "Thank you."},
    ])
    assert assigned == {"SPEAKER_00": "unknown", "SPEAKER_01": "unknown"}

def event(kind, time, **payload):
    return {"event_id": f"{kind}_{time}", "event_type": kind, "timestamp_ms": time, "payload": payload}

def test_adapter_preserves_real_time_role_and_source():
    result = DebriefAdapter().convert({"session_code": "TEST", "started_at": "2026-01-01T10:00:00+05:30"}, [
        {"timestamp": "2026-01-01T04:30:12Z", "event": "Start CPR", "role": "team_leader", "speaker": "S1", "source": "ceiling_audio"}])
    segment = result["segments"][0]
    assert segment["timestamp_ms"] == 12000
    assert segment["actor_role"] == "team_leader"
    assert segment["speaker_label"] == "S1"
    assert segment["source"] == "ceiling_audio"


def test_adapter_aligns_small_negative_clock_skew_to_session_start():
    result = DebriefAdapter().convert(
        {"session_code": "SKEW", "started_at": "2026-01-01T10:00:00+00:00"},
        [{"timestamp": "2026-01-01T09:59:59.700+00:00", "event": "Room audio started"}],
    )
    assert result["segments"][0]["timestamp_ms"] == 0
    assert result["segments"][0]["timestamp_inferred"] is False
    assert any("aligned to 0 ms" in warning for warning in result["warnings"])

def test_adapter_does_not_invent_rosc_or_cpr():
    result = DebriefAdapter().convert({"session_code": "TEST"}, [
        {"timestamp_ms": 0, "event": "Rhythm -> Sinus Bradycardia, HR -> 40"}])
    assert result["segments"] == []
    assert result["events"][0]["payload"]["rhythm"] == "SINUS_BRADY"
    assert ScenarioClassifier.classify(result["events"]) == ("unknown", None)

@pytest.mark.parametrize("initial,subtype", [("bradycardia_recognized", "brady_to_arrest"), ("tachyarrhythmia_recognized", "tachy_to_arrest")])
def test_transition_routes_correct_initial_processor(initial, subtype):
    assert ScenarioClassifier.classify([event("vf_detected", 60000), event(initial, 0)]) == ("megacode", subtype)

def test_arrest_then_brady_is_not_pre_arrest_megacode():
    assert ScenarioClassifier.classify([event("vf_detected", 0), event("bradycardia_recognized", 60000)])[0] == "cardiac_arrest"

@pytest.mark.parametrize("rhythm", sorted(RHYTHMS))
def test_all_simulator_rhythms_have_conservative_mapping(rhythm):
    assert rhythm_event({"rhythm": rhythm}) == {"VF": "vf_detected", "PEA": "pea_detected", "ASYSTOLE": "asystole_detected"}.get(rhythm)

def test_vt_requires_explicit_pulse_and_vf_value_is_supported():
    assert ScenarioClassifier.classify([event("rhythm_change", 0, rhythm="VF")]) == ("cardiac_arrest", "VF")
    assert ScenarioClassifier.classify([event("rhythm_change", 0, rhythm="VT")])[0] == "unknown"
    assert ScenarioClassifier.classify([event("rhythm_change", 0, rhythm="VT", pulse_present=False)]) == ("cardiac_arrest", "pVT")
    assert ScenarioClassifier.classify([event("rhythm_change", 0, rhythm="VT", pulse_present=True)])[0] == "tachyarrhythmia_with_pulse"

def test_drug_payload_survives_dispatch():
    result = normalize_engine_events([event("drug_administered", 12000, drug_name="epinephrine", dose_mg=1, route="IV")])[0]
    assert (result["event_type"], result["timestamp_sec"], result["dose_mg"]) == ("epinephrine_given", 12, 1)

@pytest.mark.parametrize("bad", [{}, {"event_type":"vf_detected"}, {"event_type":"vf_detected", "timestamp_sec":float("nan")}])
def test_malformed_events_fail_clearly(bad):
    with pytest.raises(ValueError): ScenarioClassifier.classify([bad])

def test_schema_rejects_negative_times_duplicates_and_path_traversal():
    for data in [
        {"session_id":"../escape"},
        {"session_id":"T", "events":[event("vf_detected", -1)]},
        {"session_id":"T", "events":[event("vf_detected", 0)]*2},
        {"session_id":"T", "duration_ms":10, "events":[event("vf_detected", 100)]},
    ]:
        with pytest.raises(ValidationError): Session.model_validate(data)

def test_scoring_uses_one_enum_identity():
    from debriefing.analysis.scoring.domain_scorers import drug_admin
    assert drug_admin.Severity is Severity
    assert drug_admin.EventType is EventType

def test_real_engine_generates_pdf_and_reproducible_metadata(tmp_path):
    data = {"session_id":"TEST", "duration_ms":180000, "events":[
        event("rhythm_change", 0, rhythm="VF"), event("cpr_initiated", 45000),
        event("shock_delivered", 70000, energy_joules=200), event("drug_administered", 90000, drug_name="epinephrine", dose_mg=1, route="IV")]}
    engine = DebriefEngine(output_dir=tmp_path, enable_narrative=False)
    result = engine.generate(data)
    assert result["classification"]["sub_type"] == "VF"
    assert [e["timestamp_ms"] for e in result["timeline"]["events"]] == [0,45000,70000,90000]
    assert Path(result["pdf_path"]).read_bytes().startswith(b"%PDF")
    assert result["narrative_status"] == "deterministic"
    assert result["normalized_input"]["events"][3]["payload"]["dose_mg"] == 1
    again = engine.generate(data)
    assert again["input_hash"] == result["input_hash"]
    assert again["pdf_path"] == result["pdf_path"]

def test_unknown_is_ungraded_and_missing_time_never_creates_timing_findings(tmp_path):
    engine = DebriefEngine(output_dir=tmp_path, enable_narrative=False)
    result = engine.generate({"session_id":"EMPTY"})
    assert result["overall_score"] is None and result["grade"] == "N/A"
    result = engine.generate(DebriefAdapter().convert({"session_id":"MISSING"}, [{"event":"Start CPR"}]))
    assert result["findings"] == []
    assert result["overall_score"] is None

def test_event_log_json_column_passthrough(tmp_path):
    """Regression: _enqueue_debrief now passes session.get('event_log') to convert().
    Simulate that: build a session dict whose event_log matches what MySQL returns
    (a Python list — aiomysql auto-deserialises JSON columns), pass it as the second
    arg, and assert the events survive into the engine output.
    """
    session_dict = {
        "session_code": "EVT_TEST",
        "started_at": "2026-01-01T10:00:00+00:00",
        "ended_at":   "2026-01-01T10:03:00+00:00",
        # MySQL JSON column is already deserialised to a list by aiomysql
        "event_log": [
            {"timestamp_ms": 0,     "event_type": "rhythm_change",  "payload": {"rhythm": "VF"}},
            {"timestamp_ms": 30000, "event_type": "cpr_initiated",  "payload": {}},
            {"timestamp_ms": 65000, "event_type": "shock_delivered", "payload": {"energy_joules": 200}},
            {"timestamp_ms": 90000, "event_type": "drug_administered",
             "payload": {"drug_name": "epinephrine", "dose_mg": 1, "route": "IV"}},
        ],
    }
    converted = DebriefAdapter().convert(session_dict, event_log=session_dict.get("event_log"))
    assert len(converted["events"]) == 4, "All 4 events must survive the adapter"
    engine = DebriefEngine(output_dir=tmp_path, enable_narrative=False)
    result = engine.generate(converted)
    assert result["classification"]["sub_type"] == "VF", "VF must be classified"
    assert result["overall_score"] is not None, "Clocked VF session must produce a score"
    assert result["score_status"] == "provisional", "Score status must be provisional for clocked sessions"


def test_audio_transcript_entries_become_segments_not_inferred_clinical_events():
    job = {"job_id": "audio1", "audio_source": "ceiling", "audio_offset_ms": 5000}
    entries = _log_entries(job, [{
        "timestamp_ms": 12000, "end_ms": 13500, "text": "Start compressions now",
        "speaker_label": "SPEAKER_00", "role": "team_leader", "confidence": 0.87,
    }])
    converted = DebriefAdapter().convert({"session_code": "AUDIO", "event_log": entries})
    assert converted["events"] == []
    assert converted["segments"][0]["source"] == "ceiling_audio"
    assert converted["segments"][0]["actor_role"] == "team_leader"
    assert converted["segments"][0]["timestamp_ms"] == 17000


def test_adapter_extends_session_for_audio_that_outlasts_simulator_stop():
    converted = DebriefAdapter().convert(
        {
            "session_code": "AUDIO-LONGER",
            "started_at": "2026-01-01T10:00:00+00:00",
            "ended_at": "2026-01-01T10:01:00+00:00",
        },
        [{
            "timestamp_ms": 59000,
            "end_ms": 75000,
            "event": "Continue compressions while the defibrillator charges.",
            "source": "ceiling_audio",
        }],
    )
    assert converted["duration_ms"] == 75000
    assert any("extended beyond the simulator stop time" in warning for warning in converted["warnings"])


def test_report_exposes_one_synchronized_clinical_and_conversation_timeline(tmp_path):
    data = {
        "session_id": "SYNC", "duration_ms": 30000,
        "events": [event("rhythm_change", 10000, rhythm="VF")],
        "segments": [{
            "segment_id": "speech_1", "timestamp_ms": 12000, "end_ms": 14000,
            "text": "VF confirmed", "speaker_label": "Leader",
            "actor_role": "team_leader", "source": "ceiling_audio", "confidence": 0.9,
        }],
    }
    result = DebriefEngine(output_dir=tmp_path, enable_narrative=False).generate(data)
    items = result["timeline"]["synchronized_items"]
    assert [item["timestamp_ms"] for item in items] == sorted(item["timestamp_ms"] for item in items)
    transcript = [item for item in items if item["kind"] == "conversation"]
    assert len(transcript) == 1
    assert transcript[0]["text"] == "VF confirmed"
    assert transcript[0]["source"] == "ceiling_audio"


def test_spoken_role_introduction_binds_diarized_voice_for_later_segments():
    from debriefing.ingestion.role_assigner import RoleAssigner
    assigner = RoleAssigner()
    segments = [
        {"speaker_label": "SPEAKER_02", "timestamp_ms": 0, "end_ms": 2000,
         "text": "I am Priya, the team leader."},
        {"speaker_label": "SPEAKER_02", "timestamp_ms": 3000, "end_ms": 5000,
         "text": "Charge to 200 joules and clear the patient."},
        {"speaker_label": "SPEAKER_01", "timestamp_ms": 5000, "end_ms": 7000,
         "text": "I am Arun, compressor."},
    ]
    attributed = assigner.apply_role_map(segments, assigner.assign(segments))
    assert attributed[0]["role"] == attributed[1]["role"] == "team_leader"
    assert attributed[1]["speaker"] == "Team Leader — Priya"
    assert attributed[2]["speaker"] == "Compressor — Arun"


def test_roster_declaration_parses_all_six_standard_roles():
    from debriefing.ingestion.role_assigner import extract_roster_entries
    roster = extract_roster_entries(
        "Preya, chest compression; Rahul, airway and breathing; Divya, deep fribrillator or ECG operator; "
        "Karthik, IV or medication; Meena, timekeeper or recorder; Priya, team leader."
    )
    assert [(item["name"], item["role"]) for item in roster] == [
        ("Preya", "compressor"), ("Rahul", "airway"), ("Divya", "defib_coach"),
        ("Karthik", "iv_member"), ("Meena", "recorder"), ("Priya", "team_leader"),
    ]


def test_roster_binds_turns_only_when_each_listed_voice_is_observed():
    from debriefing.ingestion.diarization import _bind_roster_turns
    segments = [{"timestamp_ms": 0, "end_ms": 6000,
                 "text": "Preya, chest compression; Rahul, airway and breathing; Divya, defibrillator; Karthik, IV; Meena, recorder."}]
    turns = [
        {"speaker": "SPEAKER_01", "start_ms": 0, "end_ms": 1200},
        {"speaker": "SPEAKER_02", "start_ms": 1200, "end_ms": 2400},
        {"speaker": "SPEAKER_03", "start_ms": 2400, "end_ms": 3600},
        {"speaker": "SPEAKER_04", "start_ms": 3600, "end_ms": 4800},
        {"speaker": "SPEAKER_05", "start_ms": 4800, "end_ms": 6000},
    ]
    bindings = _bind_roster_turns(segments, turns)
    assert bindings == {
        "SPEAKER_01": {"name": "Preya", "role": "compressor"},
        "SPEAKER_02": {"name": "Rahul", "role": "airway"},
        "SPEAKER_03": {"name": "Divya", "role": "defib_coach"},
        "SPEAKER_04": {"name": "Karthik", "role": "iv_member"},
        "SPEAKER_05": {"name": "Meena", "role": "recorder"},
    }
    assert segments[0]["is_roster_introduction"] is True


def test_synthetic_transcript_is_labelled_and_never_claimed_as_observed_audio():
    segments = generate_synthetic_segments("DEMO")
    converted = DebriefAdapter().convert({"session_code": "DEMO", "event_log": segments})
    assert len(converted["segments"]) == 8
    assert all(segment["source"] == "synthetic_audio" for segment in converted["segments"])
    assert any("demonstration-only" in warning for warning in converted["warnings"])


def test_synthetic_transcript_does_not_create_clinical_events(tmp_path):
    data = DebriefAdapter().convert({"session_code": "SYNTH", "duration_ms": 120000}, generate_synthetic_segments("SYNTH"))
    result = DebriefEngine(output_dir=tmp_path, enable_narrative=False).generate(data)
    assert result["timeline"]["total_events"] == 0


def test_transcript_cannot_create_clinical_actions_or_scores_by_default(tmp_path, monkeypatch):
    """An STT phrase is communication evidence, never simulator telemetry."""
    monkeypatch.delenv("ALLOW_TRANSCRIPT_CLINICAL_INFERENCE", raising=False)
    result = DebriefEngine(output_dir=tmp_path, enable_narrative=False).generate({
        "session_id": "SPEECH_ONLY", "duration_ms": 30000,
        "events": [event("rhythm_change", 0, rhythm="VF")],
        "segments": [{
            "segment_id": "speech", "timestamp_ms": 5000, "end_ms": 6000,
            "text": "Start CPR and give epinephrine one milligram.",
            "speaker_label": "SPEAKER_00", "actor_role": "team_leader",
            "source": "ceiling_audio", "confidence": 0.92,
        }],
    })
    assert [item["event_type"] for item in result["timeline"]["events"]] == ["rhythm_change"]
    assert any("communication analysis only" in warning for warning in result["warnings"])


def test_engine_removes_duplicate_transcript_retries(tmp_path):
    segment = {
        "segment_id": "retry_a", "timestamp_ms": 5000, "end_ms": 6000,
        "text": "Defibrillator charged. Everybody clear.", "speaker_label": "SPEAKER_01",
        "actor_role": "defibrillator", "source": "ceiling_audio", "confidence": 0.9,
    }
    repeated = {**segment, "segment_id": "retry_b"}
    result = DebriefEngine(output_dir=tmp_path, enable_narrative=False).generate({
        "session_id": "DEDUP", "duration_ms": 10000, "segments": [segment, repeated],
    })
    assert len(result["timeline"]["transcript_segments"]) == 1
    assert any("duplicate transcript" in warning for warning in result["warnings"])


def test_llm_verifier_requires_a_real_canonical_finding_id():
    from debriefing.synthesis.claude_api import FindingVerifier
    verifier = FindingVerifier({"finding_0000"})
    assert verifier.verify("Observed delay [finding_id:finding_0000]", "recommendations") == (True, [])
    assert verifier.verify("Observed delay [finding_id:fnd_0000]", "recommendations")[0] is False
    assert verifier.verify("Observed delay", "recommendations")[0] is False


@pytest.mark.parametrize("rhythm", [RhythmType.VT, RhythmType.VF, RhythmType.PEA, RhythmType.ASYSTOLE])
def test_no_output_rhythms_flatten_every_non_ecg_waveform(rhythm):
    """Only the ECG stays active for configured no-output/pulseless rhythms."""
    generator = WaveformGenerator(fs=512)
    state = ECGState(
        rhythm=rhythm,
        heart_rate=160,
        resp_rate=20,
        etco2=35,
        sys_bp=110,
        dia_bp=70,
        pap_sys=25,
        pap_dia=10,
    )
    generator.generate(state, 128)  # establish phase data for mechanical traces
    for waveform in (
        generator.generate_pleth,
        generator.generate_abp,
        generator.generate_pap,
        generator.generate_etco2,
    ):
        np.testing.assert_array_equal(waveform(state, 128), np.zeros(128, dtype=np.float32))
