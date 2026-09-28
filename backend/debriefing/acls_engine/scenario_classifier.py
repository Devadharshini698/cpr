"""
scenario_classifier.py — ACLS Scenario Classifier

Reads the full event stream for a session and returns:
  (algorithm_type, sub_type)

algorithm_type : 'cardiac_arrest' | 'tachyarrhythmia_with_pulse'
               | 'bradycardia_with_pulse' | 'unknown'
sub_type       : 'VF' | 'pVT' | 'PEA' | 'asystole' | None
"""

from typing import Optional, Tuple
from debriefing.contracts import Classification
from debriefing.rhythms import normalize_engine_events


class ScenarioClassifier:
    """
    One-pass classifier over the event stream.
    Determines which AHA 2025 algorithm the session belongs to.
    """

    # Events that unambiguously signal cardiac arrest
    ARREST_SIGNALS = {
        "arrest_recognized",
        "cpr_initiated",
        "vf_detected",
        "pvt_detected",
        "pea_detected",
        "asystole_detected",
    }

    # Rhythm-detection events → cardiac arrest sub-type
    RHYTHM_TO_SUBTYPE = {
        "vf_detected":       "VF",
        "pvt_detected":      "pVT",
        "pea_detected":      "PEA",
        "asystole_detected": "asystole",
    }

    @classmethod
    def classify(cls, events: list) -> Tuple[str, Optional[str]]:
        """
        Classify the scenario from a sorted list of event dicts.

        Priority order:
          1. Megacode (multi-phase)       (bradycardia_recognized AND any arrest signal)
          2. Tachyarrhythmia with pulse  (tachyarrhythmia_recognized, no arrest)
          3. Bradycardia with pulse       (bradycardia_recognized only, no arrest)
          4. Cardiac arrest               (any ARREST_SIGNAL present)
          5. Unknown

        Returns:
            (algorithm_type, sub_type)
        """
        result = cls.classify_detailed(events)
        return result.algorithm, result.sub_type

    @classmethod
    def classify_detailed(cls, events):
        events = normalize_engine_events(events)
        arrest = [e for e in events if e["event_type"] in cls.ARREST_SIGNALS]
        pulse = [e for e in events if e["event_type"] in {"bradycardia_recognized", "tachyarrhythmia_recognized"}]
        algorithm, subtype = "unknown", None
        warnings = []
        status = "classified"
        if arrest:
            preceding = [e for e in pulse if e["timestamp_sec"] < arrest[0]["timestamp_sec"]]
            if preceding:
                algorithm = "megacode"
                subtype = "brady_to_arrest" if preceding[0]["event_type"] == "bradycardia_recognized" else "tachy_to_arrest"
            else:
                algorithm = "cardiac_arrest"
                subtype = next((cls.RHYTHM_TO_SUBTYPE[e["event_type"]] for e in arrest if e["event_type"] in cls.RHYTHM_TO_SUBTYPE), "unknown")
                if pulse:
                    warnings.append("With-pulse events occur during/after arrest; review transition evidence.")
        elif pulse:
            types = {e["event_type"] for e in pulse}
            if len(types) == 1:
                algorithm = "bradycardia_with_pulse" if "bradycardia_recognized" in types else "tachyarrhythmia_with_pulse"
            else:
                status = "ambiguous"
                warnings.append("Both bradycardia and tachyarrhythmia with pulse are present; manual review required.")
        if algorithm == "unknown":
            status = "ambiguous" if status == "ambiguous" else "insufficient_data"
            warnings.append("No supported ACLS pathway established; automatic grading is unavailable.")
        return Classification(algorithm=algorithm, sub_type=subtype, status=status,
            evidence_event_ids=[str(e.get("event_id", "")) for e in events if e in arrest or e in pulse], warnings=warnings)
