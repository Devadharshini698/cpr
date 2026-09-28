"""Compatibility boundary for saved IMSR logs and canonical debrief contracts."""
import json
import re
from datetime import datetime, timezone

from debriefing.contracts import Session, Segment, Event, RULE_SET
from debriefing.rhythms import normalize_rhythm

ROLE_ALIASES = {"team leader": "team_leader", "consultant": "team_leader", "nurse": "medication_nurse", "iv_member": "medication_nurse", "resident": "unknown", "airway": "airway_manager", "defib_coach": "defibrillator"}

def parse_datetime(value):
    if isinstance(value, str):
        try: value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError: return None
    if not isinstance(value, datetime): return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def _json(value, default):
    if isinstance(value, str):
        try: return json.loads(value)
        except (ValueError, TypeError): return default
    return value if value is not None else default

def _time(item, start):
    if "timestamp_ms" in item: return item["timestamp_ms"], False
    if "start_ms" in item: return item["start_ms"], False
    if "timestamp_sec" in item: return round(item["timestamp_sec"] * 1000), False
    value = item.get("timestamp", item.get("time", item.get("created_at")))
    parsed = parse_datetime(value)
    if parsed and start:
        return round((parsed - start).total_seconds() * 1000), False
    # Historical numeric timestamps mean seconds relative to session start.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(value * 1000), False
    return 0, True

class DebriefAdapter:
    parse_datetime = staticmethod(parse_datetime)

    def __init__(self, service=None):
        from debrief_service import DebriefService
        self.service = service or DebriefService()

    def convert(self, session, event_log=None, monitor_state=None):
        if not isinstance(session, dict): raise ValueError("session must be an object")
        start = parse_datetime(session.get("started_at"))
        end = parse_datetime(session.get("ended_at"))
        raw = _json(event_log if event_log is not None else session.get("event_log"), [])
        if not isinstance(raw, list): raise ValueError("event_log must be a list")
        segments, events, warnings = [], [], []
        if any(isinstance(entry, dict) and entry.get("synthetic_transcript") for entry in raw):
            warnings.append("Synthetic transcript was used; communication and leadership results are demonstration-only, not observed performance.")
        for index, entry in enumerate(raw):
            item = entry if isinstance(entry, dict) else {"event": str(entry)}
            text = str(item.get("event", item.get("text", item.get("message", ""))))
            timestamp, inferred = _time(item, start)
            # Browser and server clocks can differ by a few milliseconds when a
            # session is created and its first telemetry event arrives. Preserve
            # the event at session start rather than rejecting the whole debrief.
            # This is a known clock skew, not missing timing data: marking it as
            # inferred would incorrectly suppress every clinical score for an
            # otherwise fully timestamped simulation.
            if timestamp < 0:
                warnings.append(f"Log entry {index} preceded session start by {-timestamp} ms; aligned to 0 ms.")
                timestamp = 0
            if inferred: warnings.append(f"Log entry {index} has no timestamp; timing is unknown.")
            role = str(item.get("actor_role", item.get("role", "unknown"))).lower()
            role = ROLE_ALIASES.get(role, role)
            speaker = str(item.get("speaker_label", item.get("speaker", "unknown")))
            # Recording lifecycle entries are system-generated evidence, not
            # speech segments, but they must still satisfy the same canonical
            # event-source contract as the transcript they describe.
            source = {
                "lapel": "lapel_audio",
                "ceiling": "ceiling_audio",
                "live_audio": "ceiling_audio",
            }.get(item.get("source"), item.get("source", "manual"))
            event_type = item.get("event_type")
            if event_type == "LOG_NOTE": event_type = None
            payload = item.get("payload", item.get("value", {})) or {}
            # Old rhythm log strings contain explicit telemetry, never a ROSC assertion.
            rhythm = re.search(r"(?:^|\b)rhythm\s*(?:->|:)\s*([^,]+)", text, re.I)
            if not event_type and rhythm:
                event_type, payload = "rhythm_change", {"rhythm": normalize_rhythm(rhythm.group(1).strip())}
            if event_type:
                events.append(Event(event_id=str(item.get("event_id", f"log_{index}")), event_type=event_type,
                    timestamp_ms=timestamp, actor_role=role, source=source, payload=payload,
                    confidence=item.get("confidence", 1.0), evidence=text, timestamp_inferred=inferred))
            elif text:
                end_ms = item.get("end_ms", timestamp)
                if end_ms < 0:
                    end_ms = 0
                segments.append(Segment(segment_id=str(item.get("segment_id", f"log_{index}")), timestamp_ms=timestamp,
                    end_ms=end_ms, text=text, speaker_label=speaker,
                    speaker_name=item.get("speaker_name") or None, actor_role=role,
                    role_evidence=str(item.get("role_evidence", "unknown")),
                    source=source, confidence=item.get("confidence", 0.8), timestamp_inferred=inferred))
        spec = _json(session.get("current_scenario_json"), {})
        if not isinstance(spec, dict): spec = {}
        requested = session.get("guideline_version")
        if requested and requested != RULE_SET:
            warnings.append(f"Session requested {requested}; evaluated using {RULE_SET}. Historical guideline is retained as metadata.")
        # Uploaded room/lapel audio can legitimately outlast the simulator's
        # recorded stop timestamp (for example, when staff finish a call-out
        # while the monitor is being stopped).  The canonical contract requires
        # every event and speech segment to fit inside the session duration, so
        # preserve both evidence streams by extending the combined timeline to
        # the final recorded item rather than discarding the transcript.
        recorded_duration = round((end-start).total_seconds()*1000) if start and end else 0
        evidence_end = max(
            [0]
            + [event.timestamp_ms for event in events]
            + [segment.end_ms for segment in segments]
        )
        duration = max(recorded_duration, evidence_end)
        if recorded_duration and evidence_end > recorded_duration:
            warnings.append(
                "Audio evidence extended beyond the simulator stop time; the synchronized session duration was extended to retain the complete transcript."
            )
        canonical = Session(session_id=str(session.get("session_code", session.get("session_id", session.get("id", "")))),
            scenario_name=spec.get("title") or session.get("scenario_name", "Clinical simulation"),
            scenario_type=spec.get("rhythm_type") or session.get("scenario_type", "unknown"),
            scenario_configuration=spec,
            team_leader_name=session.get("team_leader_name") or session.get("team_name") or "Unknown",
            team_size=session.get("team_size") or 1, duration_ms=duration,
            date=start.date().isoformat() if start else "", requested_guideline=requested,
            segments=segments, events=events, warnings=warnings)
        return canonical.model_dump(mode="json")

    def transform_event_log_to_segments(self, event_log, start_time):
        return self.convert({"session_id": "legacy", "started_at": start_time}, event_log)["segments"]

    def process_session_and_debrief(self, session, event_log=None, monitor_state=None):
        return self.service.generate_debrief(self.convert(session, event_log, monitor_state))

def convert_and_debrief(session, event_log=None, monitor_state=None):
    return DebriefAdapter().process_session_and_debrief(session, event_log, monitor_state)
