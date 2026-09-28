"""Audio-only debrief must preserve dialogue without inventing clinical scoring."""
from pathlib import Path

from debriefing.engine import DebriefEngine, report_fingerprint
from debriefing.synthesis.narrative_service import _spoken_clinical_topics


def test_speech_discussion_uses_distinct_utterances_not_roster_keywords():
    segments = [
        {"segment_id": "roster", "timestamp_ms": 0, "role_evidence": "roster_declaration",
         "text": "The compressor, airway member, and defibrillator operator are here; medication recorder is ready."},
        {"segment_id": "cpr", "timestamp_ms": 20000, "text": "Continue CPR while the monitor is attached."},
        {"segment_id": "rhythm", "timestamp_ms": 40000, "text": "Check the rhythm and pulse."},
        {"segment_id": "shock", "timestamp_ms": 60000, "text": "Prepare for defibrillation; everyone clear?"},
    ]
    topics = _spoken_clinical_topics(segments)
    assert "Medication / access" not in {topic["topic"] for topic in topics}
    assert next(topic for topic in topics if topic["topic"] == "Compressions / CPR")["timestamp_ms"] == 20000
    assert next(topic for topic in topics if topic["topic"] == "Defibrillation")["timestamp_ms"] == 60000


def test_audio_only_report_contains_transcript_and_no_clinical_score(tmp_path):
    dialogue = [
        ("team_leader", "I am Arun, the team leader. Please state your roles."),
        ("compressor", "I am Priya, assigned to chest compressions."),
        ("airway_manager", "I am Rahul, responsible for airway and breathing."),
        ("defibrillator", "I am Divya, responsible for the ECG and defibrillator."),
        ("team_leader", "Please repeat back any instructions so we know they were heard."),
        ("compressor", "Understood. I will repeat back compression instructions."),
        ("airway_manager", "I will announce any airway assessment findings."),
        ("defibrillator", "I will announce the monitor rhythm when asked."),
    ]
    segments = [
        {"segment_id": f"speech_{i}", "timestamp_ms": i * 12000,
         "end_ms": i * 12000 + 5000, "text": text, "speaker_label": f"SPEAKER_{i % 4:02d}",
         "actor_role": role, "role_evidence": "spoken_introduction" if i < 4 else "acoustic_match",
         "source": "ceiling_audio", "confidence": 0.85}
        for i, (role, text) in enumerate(dialogue * 4)
    ]
    result = DebriefEngine(output_dir=tmp_path, enable_narrative=False).generate({
        "session_id": "AUDIOONLYTEST", "scenario_name": "Audio-only team debrief",
        "scenario_type": "unknown", "duration_ms": 32 * 12000,
        "segments": segments, "events": [],
        "warnings": ["Synthetic test transcript; not a microphone recording."],
    })
    assert result["overall_score"] is None
    assert result["score_status"] == "not_assessed"
    assert len(result["timeline"]["transcript_segments"]) == 32
    assert "32 speech segments" in result["narrative_report"]["sections"]["communication_analysis"]
    assert "4 acoustic speaker labels" in result["narrative_report"]["sections"]["communication_analysis"]
    topics = result["narrative_report"]["generation_metadata"]["speech_topics"]
    assert {topic["topic"] for topic in topics} >= {"Compressions / CPR", "Airway / breathing", "Rhythm / pulse"}
    assert all(topic["status"] == "unverified_speech" for topic in topics)
    assert result["classification"]["status"] == "insufficient_data"
    assert (tmp_path / next(iter(p.name for p in tmp_path.glob("*.pdf")))).stat().st_size > 1000


def test_audio_only_surfaces_speech_topics_without_creating_clinical_findings(tmp_path):
    result = DebriefEngine(output_dir=tmp_path, enable_narrative=False).generate({
        "session_id": "AUDIOONLYTOPICS", "scenario_name": "Audio-only team debrief",
        "scenario_type": "unknown", "duration_ms": 60000,
        "segments": [{
            "segment_id": "speech_1", "timestamp_ms": 10000, "end_ms": 14000,
            "text": "Start CPR now, charge the defibrillator, and give epinephrine.",
            "speaker_label": "SPEAKER_00", "actor_role": "unknown",
            "source": "ceiling_audio", "confidence": 0.42,
        }], "events": [], "warnings": [],
    })
    assert result["overall_score"] is None
    assert result["findings"] == []
    assert result["timeline"]["total_events"] >= 2
    assert "unverified speech-derived discussion topics" in " ".join(result["warnings"])
    assert result["narrative_report"]["generation_metadata"]["speech_topics"]


def test_report_fingerprint_tracks_report_producing_modules():
    assert len(report_fingerprint()) == 64


def test_simulation_report_retains_launch_configuration_for_pdf(tmp_path):
    configuration = {
        "generation_mode": "instructor_authored", "scenario_id": "SCN-TEST",
        "rhythm_type": "PEA", "level": "advanced", "location_label": "Intensive Care Unit",
        "patient": {"age": 62, "sex": "Female", "weight_kg": 70, "presentation": "Collapse", "history": "PE risk"},
        "conditions": [{"name": "PEA Arrest"}], "checklist": [{"action": "Start CPR"}],
        "instructor_request": "Create an ICU PEA scenario.",
    }
    result = DebriefEngine(output_dir=tmp_path, enable_narrative=False).generate({
        "session_id": "CONFIGPDF", "scenario_name": "Custom PEA", "scenario_type": "PEA",
        "scenario_configuration": configuration, "duration_ms": 1000,
        "events": [{"event_id": "pea", "event_type": "rhythm_change", "timestamp_ms": 0,
                    "source": "simman", "payload": {"rhythm": "Sinus Rhythm", "pulse_present": False}}],
    })
    assert result["timeline"]["scenario_configuration"] == configuration
    assert Path(result["pdf_path"]).is_file()
