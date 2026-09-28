"""Generate a fully synthetic, labelled VF arrest debrief for UI/PDF testing.

No microphone file is read.  Both the dialogue and event annotations are test
fixtures and are deliberately marked synthetic in the resulting report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from debriefing.engine import DebriefEngine


SESSION_ID = "SYNTH_VF_TEST_01"


def segment(index, seconds, role, text):
    return {
        "segment_id": f"synthetic_speech_{index:02d}",
        "timestamp_ms": seconds * 1000,
        "end_ms": seconds * 1000 + 2800,
        "text": text,
        "speaker_label": role.upper(),
        "actor_role": role,
        "role_evidence": "synthetic_test_fixture",
        "source": "synthetic_audio",
        "confidence": 1.0,
    }


def event(index, seconds, kind, role, evidence, payload=None):
    return {
        "event_id": f"synthetic_event_{index:02d}",
        "event_type": kind,
        "timestamp_ms": seconds * 1000,
        "actor_role": role,
        "source": "manual",
        "payload": payload or {},
        "confidence": 1.0,
        "evidence": f"Synthetic transcript annotation: {evidence}",
    }


def build_input():
    dialogue = [
        (0, "team_leader", "I am Arun, team leader. Priya compressions; Rahul airway; Divya defibrillator; Karthik medications; Meena recorder."),
        (10, "team_leader", "Patient is unresponsive. Priya, assess response."),
        (15, "compressor", "No response."),
        (18, "team_leader", "Rahul, check breathing and carotid pulse for no more than ten seconds."),
        (25, "airway_manager", "No normal breathing and no carotid pulse."),
        (28, "team_leader", "Cardiac arrest confirmed. Start CPR now."),
        (32, "compressor", "Starting high-quality compressions."),
        (36, "team_leader", "Rahul provide bag-mask ventilation with oxygen. Divya attach pads and monitor."),
        (44, "defibrillator", "Pads attached. Rhythm is ventricular fibrillation; shock is advised."),
        (49, "team_leader", "Charge to 200 joules. Everyone clear."),
        (55, "defibrillator", "All clear. Shock delivered."),
        (57, "team_leader", "Resume CPR immediately."),
        (61, "medication_nurse", "IV access established."),
        (75, "team_leader", "At the two-minute check: pause briefly for rhythm and pulse."),
        (80, "defibrillator", "Ventricular fibrillation persists. No pulse."),
        (84, "team_leader", "Charge. Everyone clear."),
        (89, "defibrillator", "All clear. Second shock delivered."),
        (91, "team_leader", "Resume CPR. Karthik, give epinephrine one milligram IV."),
        (96, "medication_nurse", "Epinephrine one milligram IV administered and time recorded."),
        (110, "team_leader", "Continue CPR and ventilation. Prepare for the next rhythm check."),
        (135, "team_leader", "Pause briefly. Check rhythm and pulse."),
        (140, "defibrillator", "Ventricular fibrillation persists. No pulse."),
        (144, "team_leader", "Charge. Everyone clear."),
        (149, "defibrillator", "All clear. Third shock delivered."),
        (151, "team_leader", "Resume CPR. Give amiodarone 300 milligrams IV bolus."),
        (157, "medication_nurse", "Amiodarone 300 milligrams IV administered."),
        (175, "team_leader", "Prepare for rhythm and pulse check."),
        (180, "defibrillator", "Organized rhythm on the monitor."),
        (184, "team_leader", "Check pulse."),
        (187, "airway_manager", "Carotid pulse present. We have return of spontaneous circulation."),
        (192, "team_leader", "Stop CPR. Begin post-cardiac-arrest care and continue monitoring."),
    ]
    segments = [segment(i, *row) for i, row in enumerate(dialogue)]
    annotations = [
        (0, 10, "arrest_recognized", "team_leader", dialogue[1][2], {}),
        (1, 28, "cpr_initiated", "team_leader", dialogue[5][2], {}),
        (2, 44, "rhythm_change", "defibrillator", dialogue[8][2], {"rhythm": "VF", "pulse_present": False}),
        (3, 55, "shock_delivered", "defibrillator", dialogue[10][2], {"energy_joules": 200}),
        (4, 57, "cpr_resumed", "team_leader", dialogue[11][2], {}),
        (5, 61, "vascular_access", "medication_nurse", dialogue[12][2], {"route": "IV"}),
        (6, 80, "rhythm_change", "defibrillator", dialogue[14][2], {"rhythm": "VF", "pulse_present": False}),
        (7, 89, "shock_delivered", "defibrillator", dialogue[16][2], {"energy_joules": 200}),
        (8, 91, "cpr_resumed", "team_leader", dialogue[17][2], {}),
        (9, 96, "drug_administered", "medication_nurse", dialogue[18][2], {"drug_name": "epinephrine", "dose_mg": 1, "route": "IV"}),
        (10, 140, "rhythm_change", "defibrillator", dialogue[21][2], {"rhythm": "VF", "pulse_present": False}),
        (11, 149, "shock_delivered", "defibrillator", dialogue[23][2], {"energy_joules": 200}),
        (12, 151, "cpr_resumed", "team_leader", dialogue[24][2], {}),
        (13, 157, "drug_administered", "medication_nurse", dialogue[25][2], {"drug_name": "amiodarone", "dose_mg": 300, "route": "IV"}),
        (14, 180, "rhythm_change", "defibrillator", dialogue[27][2], {"rhythm": "NSR", "pulse_present": True}),
        (15, 187, "rosc_achieved", "airway_manager", dialogue[29][2], {}),
    ]
    return {
        "session_id": SESSION_ID,
        "scenario_name": "Synthetic VF Cardiac Arrest - Test Fixture",
        "scenario_type": "VF",
        "team_leader_name": "Arun",
        "team_size": 6,
        "duration_ms": 200000,
        "segments": segments,
        "events": [event(*row) for row in annotations],
        "warnings": [
            "SYNTHETIC TEST FIXTURE: transcript and event annotations were generated internally; they are not observed patient or team data.",
            "This report is for workflow, interface, and scoring demonstration only. It must not be used for learner assessment or clinical quality review.",
        ],
    }


def main():
    destination = ROOT / "output" / "synthetic_vf_test"
    result = DebriefEngine(output_dir=destination, enable_narrative=False).generate(build_input())
    (destination / "synthetic_vf_input.json").write_text(
        json.dumps(build_input(), indent=2), encoding="utf-8"
    )
    (destination / "synthetic_vf_report.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps({"session_id": SESSION_ID, "pdf_path": result["pdf_path"],
                      "score": result["overall_score"], "grade": result["grade"],
                      "findings": len(result["findings"]), "segments": len(result["timeline"]["transcript_segments"])}))


if __name__ == "__main__":
    main()
