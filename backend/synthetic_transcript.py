"""Explicitly synthetic dialogue for demos when no room recording is supplied."""
from __future__ import annotations


def generate_synthetic_segments(session_code: str) -> list[dict]:
    """Return a deterministic, role-attributed ACLS dialogue for demonstration only.

    These records are never presented as captured speech: callers persist the
    ``synthetic_transcript`` marker and the debrief adapter adds a warning.
    """
    turns = [
        (4_000, 7_000, "team_leader", "LEADER", "Team, we have ventricular fibrillation. Start high-quality CPR."),
        (8_000, 11_000, "compressor", "COMPRESSOR", "Starting compressions now."),
        (28_000, 32_000, "team_leader", "LEADER", "Continue CPR. Charge to 200 joules."),
        (34_000, 37_000, "defibrillator", "DEFIB", "Charging to 200 joules."),
        (62_000, 66_000, "team_leader", "LEADER", "Clear the patient. Deliver the shock."),
        (67_000, 70_000, "defibrillator", "DEFIB", "All clear. Shock delivered."),
        (82_000, 86_000, "team_leader", "LEADER", "Give epinephrine 1 milligram IV now."),
        (88_000, 92_000, "medication_nurse", "MEDICATION", "Epinephrine 1 milligram IV given."),
    ]
    return [{
        "segment_id": f"synthetic_{session_code}_{index:02d}",
        "timestamp_ms": start_ms,
        "end_ms": end_ms,
        "event": text,
        "speaker_label": speaker,
        "actor_role": role,
        "source": "synthetic_audio",
        "confidence": 1.0,
        "synthetic_transcript": True,
    } for index, (start_ms, end_ms, role, speaker, text) in enumerate(turns)]
