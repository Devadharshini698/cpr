"""Simulator vocabulary and pulse-aware mapping to ACLS events."""
import math
import re

RHYTHMS = frozenset("NSR SINUS_BRADY SINUS_TACHY AFIB AFLUTTER JUNCTIONAL AVB1 AVB2_I AVB2_II AVB3 PAC PVC SVT VT VF TORSADES ASYSTOLE PEA LBBB RBBB ANT_STEMI INF_STEMI LAT_STEMI".split())
ALIASES = {
    "SINUS_RHYTHM": "NSR", "NORMAL_SINUS_RHYTHM": "NSR", "SINUS": "NSR",
    "SINUS_BRADYCARDIA": "SINUS_BRADY", "BRADYCARDIA": "SINUS_BRADY",
    "SINUS_TACHYCARDIA": "SINUS_TACHY", "TACHYCARDIA": "SINUS_TACHY",
    "VENTRICULAR_FIBRILLATION": "VF", "VENTRICULAR_TACHYCARDIA": "VT",
    "PULSELESS_VT": "PVT", "PULSELESS_VENTRICULAR_TACHYCARDIA": "PVT",
    "PULSELESS_ELECTRICAL_ACTIVITY": "PEA", "SUPRAVENTRICULAR_TACHYCARDIA": "SVT",
    "ATRIAL_FIBRILLATION": "AFIB", "ATRIAL_FLUTTER": "AFLUTTER", "TORSADES_DE_POINTES": "TORSADES",
}

def normalize_rhythm(value):
    value = getattr(value, "value", value)
    key = re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip("_")
    return ALIASES.get(key, key)

def rhythm_event(payload):
    """Require pulse evidence; normal sinus rhythm alone does not establish ROSC."""
    rhythm = normalize_rhythm(payload.get("rhythm"))
    pulse = payload.get("pulse_present")
    if rhythm == "VF": return "vf_detected"
    if rhythm == "ASYSTOLE": return "asystole_detected"
    if rhythm == "PEA": return "pea_detected"
    if rhythm == "PVT" or (rhythm in {"VT", "TORSADES"} and pulse is False): return "pvt_detected"
    if pulse is False and rhythm in RHYTHMS: return "pea_detected"
    if pulse is not True: return None
    if rhythm in {"SINUS_BRADY", "AVB2_II", "AVB3"}: return "bradycardia_recognized"
    if rhythm in {"VT", "TORSADES", "SVT"}: return "tachyarrhythmia_recognized"
    return None

def normalize_engine_events(events):
    normalized = []
    for index, original in enumerate(events):
        if not isinstance(original, dict) or not original.get("event_type"):
            raise ValueError(f"event {index} requires event_type")
        event = dict(original)
        if "timestamp_sec" not in event:
            if "timestamp_ms" not in event: raise ValueError(f"event {index} requires a timestamp")
            event["timestamp_sec"] = event["timestamp_ms"] / 1000
        time = event["timestamp_sec"]
        if isinstance(time, bool) or not isinstance(time, (float, int)) or not math.isfinite(time) or time < 0:
            raise ValueError(f"event {index} has an invalid timestamp")
        event = {**(event.get("payload") or event.get("value") or {}), **event}
        if event["event_type"] == "rhythm_change":
            event["event_type"] = rhythm_event(event) or "rhythm_change"
        elif event["event_type"] == "drug_administered":
            drug = str(event.get("drug_name", "")).lower()
            drug = {"adrenaline": "epinephrine", "epi": "epinephrine"}.get(drug, drug)
            if drug in {"epinephrine", "amiodarone", "lidocaine", "atropine", "adenosine"}: event["event_type"] = drug + "_given"
        event["event_type"] = {"airway_secured": "advanced_airway_placed", "hs_ts_discussed": "reversible_causes_discussed"}.get(event["event_type"], event["event_type"])
        normalized.append(event)
    return sorted(normalized, key=lambda e: e["timestamp_sec"])
