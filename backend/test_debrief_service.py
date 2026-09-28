"""
Local test script for backend/debrief_service.py
"""

import json
import logging
from pathlib import Path
from debrief_service import generate_debrief

logging.basicConfig(level=logging.INFO)

def main():
    transcript_path = Path(__file__).parent / "debriefing" / "dummy" / "ses_scn_001.json"
    print(f"Loading transcript from: {transcript_path}")
    with open(transcript_path, "r", encoding="utf-8") as f:
        session_data = json.load(f)

    print("Calling generate_debrief(session_data)...")
    result = generate_debrief(session_data)

    print("\n" + "="*50)
    print("DEBRIEF SERVICE TEST RESULT:")
    print("="*50)
    print(f"Overall Score   : {result['overall_score']}")
    print(f"Grade           : {result['grade']}")
    print(f"Findings Count  : {len(result['findings'])}")
    print(f"Domain Scores   : {len(result['domain_scores'])} domains scored")
    print(f"Timeline Events : {len(result['timeline']['events'])} events")
    print(f"PDF Path        : {result['pdf_path']}")
    print(f"PDF Exists      : {Path(result['pdf_path']).exists()}")
    print("="*50)

    assert result["overall_score"] is not None
    assert result["grade"] is not None
    assert isinstance(result["findings"], list)
    assert isinstance(result["timeline"], dict)
    assert isinstance(result["domain_scores"], list)
    assert isinstance(result["narrative_report"], dict)
    assert Path(result["pdf_path"]).exists()
    print("TEST PASSED SUCCESSFULLY!")

    # Test Case 1: Session with ONLY arrest_recognized (No actions performed)
    arrest_only_session = {
        "session_id": "SES-TEST-ARREST-ONLY",
        "scenario_name": "Adult ACLS - VF Cardiac Arrest",
        "scenario_type": "VF",
        "team_leader_name": "Test Team Leader",
        "team_size": 4,
        "duration_ms": 120000,
        "date": "2026-08-10",
        "segments": [
            {
                "segment_id": "seg_001",
                "speaker": "Team Leader",
                "role": "team_leader",
                "text": "Patient collapsed, no pulse, cardiac arrest recognized.",
                "start_ms": 0,
                "end_ms": 2500,
            }
        ],
    }

    print("\nCalling generate_debrief(arrest_only_session)...")
    res_failed = generate_debrief(arrest_only_session)
    print(f"Arrest Only Session Score: {res_failed['overall_score']}, Grade: {res_failed['grade']}")
    assert res_failed["overall_score"] < 40.0, f"Expected < 40.0 for arrest-only session, got {res_failed['overall_score']}"
    assert res_failed["grade"] == "F", f"Expected Grade F, got {res_failed['grade']}"
    print("[PASS] Arrest-only session correctly evaluated to Score < 40 and Grade F!")

if __name__ == "__main__":
    main()
