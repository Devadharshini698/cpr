"""Database-free engine boundary used by IMSR and offline regression tests."""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import importlib
import json
import os
from pathlib import Path

from debriefing import __version__
from debriefing.contracts import Session, Report, RULE_SET
from debriefing.acls_engine import ACLSEngine, ScenarioClassifier
from debriefing.analysis.event_extractor import EventExtractor
from debriefing.analysis.scoring.scoring_engine import ScoringEngine
from debriefing.rhythms import normalize_engine_events
from debriefing.schemas.event_schema import (
    UnifiedTimeline, UnifiedEvent, EventType, ActorRole, SourceSystem,
    DrugPayload, ShockPayload, CPRQualityPayload, Evidence, FindingRecord,
    Severity, TranscriptSegment, DataCompletenessFlag,
)

def _hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def rule_fingerprint():
    root = Path(__file__).parent
    paths = sorted((root / "acls_engine").rglob("*.json")) + sorted((root / "acls_engine" / "algorithms").glob("*.py"))
    return _hash({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})


def report_fingerprint():
    """Version report artifacts when report-generation code changes.

    A debrief job is otherwise intentionally idempotent for identical session
    evidence.  Include the report-producing modules so a corrected PDF or
    audio-only narrative can replace an older completed artifact without
    pretending that the underlying session data changed.
    """
    root = Path(__file__).parent
    paths = [
        Path(__file__),
        root / "synthesis" / "pdf_generator.py",
        root / "synthesis" / "narrative_service.py",
    ]
    return _hash({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})

def _actor(role):
    try: return ActorRole(role)
    except ValueError: return ActorRole.UNKNOWN


def _deduplicate_segments(segments):
    """Collapse identical ingestion retries before any analysis or reporting.

    A repeated MediaRecorder retry must not become repeated communication evidence
    or influence any downstream model.  The acoustic label is retained in the key,
    so two people saying the same thing are still distinct observations.
    """
    seen, unique = set(), []
    for segment in sorted(segments, key=lambda item: (item.timestamp_ms, item.end_ms, item.segment_id)):
        key = (
            segment.source, segment.timestamp_ms, segment.end_ms,
            segment.speaker_label, segment.actor_role,
            " ".join(segment.text.lower().split()),
        )
        if key not in seen:
            seen.add(key)
            unique.append(segment)
    return unique

def _structured_event(item):
    try: event_type = EventType(item.event_type)
    except ValueError: event_type = EventType.SCENARIO_MARKER
    source = SourceSystem(item.source)
    event = UnifiedEvent(event_id=item.event_id, timestamp_ms=item.timestamp_ms,
        event_type=event_type, source_systems=[source], actor_role=_actor(item.actor_role),
        value=item.payload, confidence=item.confidence,
        has_confirmed_timestamp=not item.timestamp_inferred,
        data_completeness=DataCompletenessFlag.UNCERTAIN if item.timestamp_inferred else DataCompletenessFlag.FULL,
        evidence=[Evidence(source=source, ref=item.event_id, text=item.evidence,
            timestamp_ms=item.timestamp_ms, confidence=item.confidence)])
    if item.event_type in {"drug_ordered", "drug_administered"}:
        event.drug_payload = DrugPayload(**{k: v for k, v in item.payload.items() if k in DrugPayload.__dataclass_fields__})
    if item.event_type == "shock_delivered":
        event.shock_payload = ShockPayload(**{k: v for k, v in item.payload.items() if k in ShockPayload.__dataclass_fields__})
    if item.event_type == "cpr_quality_measured":
        event.cpr_payload = CPRQualityPayload(**{k: v for k, v in item.payload.items() if k in CPRQualityPayload.__dataclass_fields__})
    return event

class DebriefEngine:
    def __init__(self, output_dir=None, enable_narrative=None):
        self.output_dir = Path(output_dir or os.getenv("DEBRIEF_REPORT_DIR") or Path(__file__).parent / "output" / "reports")
        self.enable_narrative = (os.getenv("ENABLE_OLLAMA_DEBRIEF", "false").lower() == "true") if enable_narrative is None else enable_narrative

    def generate(self, data):
        session = data if isinstance(data, Session) else Session.model_validate(data)
        unique_segments = _deduplicate_segments(session.segments)
        if len(unique_segments) != len(session.segments):
            session = session.model_copy(update={
                "segments": unique_segments,
                "warnings": list(session.warnings) + [
                    f"Removed {len(session.segments) - len(unique_segments)} duplicate transcript segment(s) before analysis."
                ],
            })
        canonical_input = session.model_dump(mode="json")
        input_hash = _hash(canonical_input)
        warnings = list(session.warnings)
        programme=session.scenario_configuration.get('curriculum',{}).get('programme','ACLS')
        unsupported_curriculum=programme != 'ACLS'
        if unsupported_curriculum:
            warnings.append(f'{programme}: adult ACLS findings and clinical grading are disabled; programme-specific validation is pending.')
        raw_segments = [s.model_dump(mode="json") for s in session.segments]
        events = [_structured_event(e) for e in session.events]
        # An audio-only run has no independent patient-monitor or observer
        # evidence.  It may still be useful to surface *spoken* clinical
        # topics for debrief discussion, but those are deliberately kept out
        # of ACLS scoring and rule findings below.
        audio_only = (
            session.scenario_type == "unknown"
            and "audio-only" in session.scenario_name.lower()
        )
        # Speech recognition is fallible.  Simulator/observer events are the
        # clinical source of truth; transcripts inform communication only.
        # Transcript-to-clinical-event inference remains an explicit, opt-in
        # research mode and is never enabled by a normal deployment.
        allow_transcript_inference = os.getenv("ALLOW_TRANSCRIPT_CLINICAL_INFERENCE", "false").lower() == "true"
        speech_topic_inference = audio_only and bool(raw_segments)
        extracted = EventExtractor().extract([s for s in raw_segments if s["source"] != "synthetic_audio"]) if (allow_transcript_inference or speech_topic_inference) else []
        if speech_topic_inference:
            for event in extracted:
                event.data_completeness = DataCompletenessFlag.UNCERTAIN
            warnings.append(
                "Audio-only report includes unverified speech-derived discussion topics. They are not confirmed clinical actions and are excluded from clinical scoring."
            )
        if raw_segments and not allow_transcript_inference:
            warnings.append("Transcript retained for communication analysis only; it was not used to infer clinical actions or scores.")
        for index, event in enumerate(extracted): event.event_id = f"extracted_{index}"
        events.extend(extracted)
        events.sort(key=lambda e: e.timestamp_ms)
        timeline = UnifiedTimeline(session_id=session.session_id, scenario_name=session.scenario_name,
            team_leader_id=session.team_leader_name, session_date=session.date, events=events)
        timeline.duration_ms = session.duration_ms
        timeline.team_size = session.team_size
        timeline.guideline_version = RULE_SET
        timeline.scenario_type = session.scenario_type
        timeline.scenario_configuration = session.scenario_configuration
        timeline.audio_only = audio_only
        timeline.raw_segments = raw_segments
        engine_events = [dict(e.model_dump(), timestamp_sec=e.timestamp_ms/1000) for e in session.events]
        for e in extracted:
            payload = dict(e.value or {})
            if e.drug_payload: payload.update(e.drug_payload.to_dict())
            engine_events.append({"event_id": e.event_id, "event_type": e.event_type.value,
                "timestamp_ms": e.timestamp_ms, "payload": payload})
        engine_events = normalize_engine_events(engine_events)
        classification = ScenarioClassifier.classify_detailed(engine_events)
        warnings.extend(classification.warnings)
        # Missing clock data must never be used to claim response-time deviations.
        reliable_clock = all(e.has_confirmed_timestamp for e in events)
        if not reliable_clock:
            warnings.append("Timing evaluation withheld because one or more event timestamps are unknown.")
        scorer = ScoringEngine()
        rule_domains = {}
        for domain in scorer.scorers:
            module = importlib.import_module(type(domain).__module__)
            for key in getattr(module, "_FINDING_TO_SUBSIGNAL", {}): rule_domains[key] = domain.domain_key
        raw_findings = ACLSEngine().evaluate({"session_id": session.session_id, "events": engine_events}) if (reliable_clock and classification.algorithm != "unknown" and not audio_only and not unsupported_curriculum) else []
        unmapped = set()
        for index, finding in enumerate(raw_findings):
            rule = finding.get("rule_id", "")
            domain = rule_domains.get(rule, "protocol_compliance")
            if domain == "protocol_compliance": unmapped.add(rule)
            severity = {"MEDIUM": "MODERATE", "ADVISORY": "INFO"}.get(finding.get("severity"), finding.get("severity", "INFO"))
            timestamp = round((finding.get("timestamp_sec") or 0)*1000)
            trigger_types = {finding.get("from_event"), finding.get("to_event")}
            ids = {e.get("event_id") for e in engine_events if e["event_type"] in trigger_types and e["timestamp_sec"] <= timestamp/1000}
            supporting = [e for e in events if e.event_id in ids]
            timeline.findings.append(FindingRecord(finding_id=f"finding_{index:04d}", template_id=rule,
                title=rule, domain=domain, severity=Severity[severity], description=finding.get("deviation_message", ""),
                guideline_citation=finding.get("guideline", ""), recommendation=finding.get("recommendation", ""),
                timestamp_ms=timestamp, penalty_weight=finding.get("penalty_weight", 0),
                triggering_event_ids=sorted(ids), evidence=[ev for e in supporting for ev in e.evidence]))
        if unmapped: warnings.append("Findings displayed but not covered by the existing scoring rubric: " + ", ".join(sorted(unmapped)))
        if classification.sub_type in {"VF", "pVT", "PEA", "asystole"}: timeline.scenario_type = classification.sub_type
        transcripts = {"lapel": [], "ceiling": []}
        for s in session.segments:
            key = {"lapel_audio": "lapel", "ceiling_audio": "ceiling", "synthetic_audio": "ceiling"}.get(s.source)
            if key:
                transcripts[key].append(TranscriptSegment(segment_id=s.segment_id, text=s.text,
                    start_ms=s.timestamp_ms, end_ms=s.end_ms, source=key, speaker_role=_actor(s.actor_role), confidence=s.confidence))
        score = scorer.score(timeline, lapel_transcript=transcripts["lapel"], ceiling_transcript=transcripts["ceiling"])
        score.protocol_version = RULE_SET
        assessed = not audio_only and not unsupported_curriculum and classification.algorithm == "cardiac_arrest" and reliable_clock
        if not assessed:
            warnings.append("Overall grade withheld: the current domain rubric supports cardiac-arrest sessions with known timing only.")
            score.overall_score, score.grade, score.domain_scores = 0.0, "N/A", []
        if score.has_low_data_domains:
            warnings.append("One or more domains have limited evidence; scores and uncertainty ranges are provisional.")
        warnings.append("Rule bundle preserves the repository's existing thresholds; clinical validation is pending.")
        from debriefing.analysis.nlp_engine import NLPEngine
        communication = NLPEngine().process(session_id=session.session_id, segments=raw_segments) if self.enable_narrative else {"status": "disabled", "nlp_analysis": {}}
        from debriefing.synthesis.narrative_service import NarrativeService
        narrative, narrative_status = NarrativeService(enable_llm=self.enable_narrative).generate(timeline)
        if narrative_status.startswith("deterministic_provider_"):
            warnings.append("Optional LLM narrative was unavailable; the report uses a deterministic evidence-based narrative.")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        fingerprint = rule_fingerprint()
        artifact_key = _hash([__version__, fingerprint, report_fingerprint(), input_hash])[:20]
        pdf = self.output_dir / f"{session.session_id}_{artifact_key}_debrief.pdf"
        score.data_completeness_warnings = warnings
        from debriefing.synthesis.pdf_generator import generate_pdf
        generate_pdf(score_report=score, findings=timeline.findings, timeline=timeline,
            output_path=pdf, debrief_report=narrative)
        domains = [{**asdict(d), "score": d.final_score, "completeness_flag": d.completeness_flag.value} for d in score.domain_scores]
        result = Report(session_id=session.session_id, scenario_name=session.scenario_name,
            engine_version=__version__, rule_set=RULE_SET, rule_set_hash=fingerprint, input_hash=input_hash,
            classification=classification, overall_score=score.overall_score if assessed else None, grade=score.grade,
            warnings=list(dict.fromkeys(warnings)), findings=[f.to_dict() for f in timeline.findings],
            domain_scores=domains, timeline={
                "session_id": session.session_id,
                "scenario_configuration": session.scenario_configuration,
                "total_events": len(events),
                "events": [e.to_dict() for e in events],
                "transcript_segments": raw_segments,
                "synchronized_items": sorted(
                    ([{"kind": "clinical_event", **e.to_dict()} for e in events] +
                     [{"kind": "conversation", **s} for s in raw_segments]),
                    key=lambda item: (item.get("timestamp_ms", 0), item.get("kind", "")),
                ),
            },
            narrative_report=narrative.to_dict() if narrative and hasattr(narrative, "to_dict") else {},
            narrative_status=narrative_status, communication_status=communication["status"], communication_analysis=communication.get("nlp_analysis", {}), pdf_path=str(pdf.resolve()),
            normalized_input=canonical_input, score_status="provisional" if assessed else "not_assessed")
        return result.model_dump(mode="json")
