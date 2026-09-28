"""One safe narrative boundary for final IMSR debrief reports.

The rule engine owns clinical facts.  This module only turns those facts into
readable coaching text.  A local LLM may improve wording, but a deterministic,
traceable fallback is always available and is never replaced by an error message.
"""
from __future__ import annotations

import re

from debriefing.schemas.event_schema import Severity
from debriefing.synthesis.claude_api import DebriefReport, ReportSection


def _value(item, name, default=""):
    value = item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)
    return default if value is None else value


def _severity(value) -> str:
    return str(value.value if hasattr(value, "value") else value).lower().replace("severity.", "")


_SPOKEN_TOPICS = (
    ("Initial assessment", r"\b(unresponsive|not responding|collapse[ds]?|assess(?:ment)?)\b",
     "What was observed directly, and what remains only a spoken description?"),
    ("Compressions / CPR", r"\b(cpr|compressions?|compress(?:ing)?)\b",
     "Were compressions actually performed, and what independent record could confirm timing and quality?"),
    ("Airway / breathing", r"\b(airway|breath(?:ing)?|ventilat(?:e|ion|ions)|oxygen)\b",
     "What airway or ventilation steps were actually performed, as distinct from discussed?"),
    ("Rhythm / pulse", r"\b(rhythm|ecg|pulse|shockable)\b",
     "Which rhythm or pulse assessment was confirmed by a monitor or observer?"),
    ("Defibrillation", r"\b(defibrillat\w*|shock(?:ed|ing)?|charging|clear)\b",
     "Was a shock delivered, or was the team only preparing or discussing one?"),
    ("Medication / access", r"\b(epinephrine|adrenaline|amiodarone|lidocaine|iv access|io access|administer\w*)\b",
     "Which medication or access step, if any, has an independent administration record?"),
    ("Return of circulation", r"\b(rosc|return of spontaneous circulation)\b",
     "Was return of circulation confirmed by observed patient data?"),
)

_TOPIC_PREFERENCE = {
    "Compressions / CPR": r"\bcompression\w*\b",
    "Rhythm / pulse": r"\b(rhythm|pulse)\b",
    "Defibrillation": r"\b(deliver\w*|charging|charged|shock)\b",
}


def _spoken_clinical_topics(segments):
    """Select transcript excerpts for discussion, never inferred clinical events."""
    topics = []
    used = set()
    for label, pattern, question in _SPOKEN_TOPICS:
        candidates = []
        for segment in segments:
            raw = str(_value(segment, "text", ""))
            keyword = re.search(pattern, raw, re.IGNORECASE)
            if keyword:
                candidates.append((segment, keyword))
        candidates.sort(key=lambda pair: (
            _value(pair[0], "role_evidence", "") == "roster_declaration",
            not bool(re.search(_TOPIC_PREFERENCE.get(label, pattern),
                               str(_value(pair[0], "text", "")), re.IGNORECASE)),
            len(str(_value(pair[0], "text", ""))) > 130,
            int(_value(pair[0], "timestamp_ms", 0) or 0),
        ))
        selected = next(((segment, keyword) for segment, keyword in candidates
                         if str(_value(segment, "segment_id", id(segment))) not in used), None)
        if selected is None:
            continue
        match, keyword = selected
        used.add(str(_value(match, "segment_id", id(match))))
        raw = str(_value(match, "text", "")).strip()
        start = max(0, keyword.start() - 38) if len(raw) > 140 else 0
        excerpt = ("..." if start else "") + raw[start:start + 125]
        if start + 125 < len(raw):
            excerpt += "..."
        timestamp_ms = max(0, int(_value(match, "timestamp_ms", 0) or 0))
        topics.append({
            "topic": label,
            "timestamp_ms": timestamp_ms,
            "excerpt": excerpt,
            "question": question,
            "confidence": float(_value(match, "confidence", 0) or 0),
            "status": "unverified_speech",
        })
    return sorted(topics, key=lambda topic: topic["timestamp_ms"])


class NarrativeService:
    """Generate a debrief narrative without letting a language model alter facts."""

    def __init__(self, enable_llm: bool = False):
        self.enable_llm = enable_llm

    def generate(self, timeline):
        fallback = self._deterministic_report(timeline)
        if not (getattr(timeline, "events", None) or []) and getattr(timeline, "raw_segments", None):
            return fallback, "deterministic_audio_only"
        if not self.enable_llm:
            return fallback, "deterministic"

        try:
            # Ollama is the single supported optional provider in final IMSR.
            from debriefing.synthesis.ollama_api import ReportGenerator
            provider = ReportGenerator()
            if not provider.is_available():
                return fallback, "deterministic_provider_unavailable"
            candidate = provider.generate_report(timeline)
            if self._is_safe(candidate):
                return self._merge(candidate, fallback), "completed"
        except Exception:
            # A narrative failure must never turn into clinical or PDF failure.
            pass
        return fallback, "deterministic_provider_failed"

    def _deterministic_report(self, timeline) -> DebriefReport:
        findings = list(getattr(timeline, "findings", []) or [])
        report = DebriefReport(
            session_id=timeline.session_id,
            scenario_name=getattr(timeline, "scenario_name", "Clinical simulation"),
            team_leader_id=getattr(timeline, "team_leader_id", "Unknown"),
            session_date=getattr(timeline, "session_date", ""),
        )
        if not findings:
            segments = [s for s in (getattr(timeline, "raw_segments", []) or [])
                        if _value(s, "source", "") != "synthetic_audio" and str(_value(s, "text", "")).strip()]
            if segments:
                speakers = {str(_value(s, "speaker_label", "")).strip() for s in segments
                            if str(_value(s, "speaker_label", "")).strip()}
                uncertain = [s for s in segments if float(_value(s, "confidence", 0) or 0) < 0.7]
                ambiguous = sum("+" in str(_value(s, "actor_role", "")) or
                                str(_value(s, "actor_role", "unknown")) == "unknown" for s in segments)
                replay = sorted(uncertain, key=lambda s: int(_value(s, "timestamp_ms", 0) or 0))[:3]
                stamps = [f"{(int(_value(s, 'timestamp_ms', 0) or 0) // 1000) // 60:02d}:"
                          f"{(int(_value(s, 'timestamp_ms', 0) or 0) // 1000) % 60:02d}" for s in replay]
                report.communication_analysis = ReportSection(
                    "Transcript evidence review",
                    f"The recording yielded {len(segments)} speech segments and {len(speakers)} acoustic speaker labels. "
                    f"{len(uncertain)} segments have low transcription confidence; {ambiguous} have an unknown or ambiguous role. "
                    + (f"Replay priority timestamps: {', '.join(stamps)}. " if stamps else "")
                    + "These are quality indicators, not a judgment of team performance. Confirm wording and speaker roles against the audio before interpreting communication or claimed actions."
                )
            report.generation_metadata = {"backend": "deterministic", "evidence_based": True,
                                          "transcript_segments": len(segments),
                                          "speech_topics": _spoken_clinical_topics(segments)}
            return report

        ordered = sorted(findings, key=lambda f: {
            "critical": 0, "high": 1, "moderate": 2, "low": 3, "info": 4,
        }.get(_severity(_value(f, "severity", "info")), 4))
        recommendations, prompts, strengths = [], [], []
        for finding in ordered:
            severity = _severity(_value(finding, "severity", "info")).upper()
            title = str(_value(finding, "title", _value(finding, "rule_id", "Finding")))
            finding_id = str(_value(finding, "finding_id", ""))
            stamp = int(_value(finding, "timestamp_ms", 0) or 0) // 1000
            tag = f" [Evidence: {finding_id}]" if finding_id else ""
            recommendation = str(_value(finding, "recommendation", "")).strip()
            prompt = str(_value(finding, "reflective_prompt", "")).strip()
            if recommendation:
                recommendations.append(f"{severity} · {title} at {stamp // 60}:{stamp % 60:02d}: {recommendation}{tag}")
            if prompt:
                prompts.append(f"{prompt}{tag}")
            if _severity(_value(finding, "severity", "")) == "info":
                strengths.append(f"{title} at {stamp // 60}:{stamp % 60:02d}.{tag}")

        if recommendations:
            report.recommendations = ReportSection("Recommendations", "<br/><br/>".join(recommendations[:5]))
        if prompts:
            report.reflective_prompts = ReportSection("Reflective prompts", "<br/><br/>".join(prompts[:5]))
        if strengths:
            report.strengths = ReportSection("Strengths", "<br/><br/>".join(strengths[:4]))
        elif getattr(timeline, "events", None):
            documented = []
            for event in sorted(timeline.events, key=lambda item: item.timestamp_ms):
                name = str(getattr(event.event_type, "value", event.event_type)).replace("_", " ")
                if name in {"cpr initiated", "cpr resumed", "shock delivered", "drug administered", "airway secured", "rosc achieved", "hs ts discussed"}:
                    seconds = event.timestamp_ms // 1000
                    documented.append(f"Documented action: {name} at {seconds // 60}:{seconds % 60:02d}.")
            if documented:
                report.strengths = ReportSection(
                    "Documented actions", "<br/><br/>".join(dict.fromkeys(documented[:4]))
                )
        report.generation_metadata = {
            "backend": "deterministic", "evidence_based": True,
            "total_findings": len(findings),
        }
        return report

    @staticmethod
    def _is_safe(report) -> bool:
        """Reject unavailable, uncited, or verification-warning prose."""
        if report is None:
            return False
        contents = [getattr(section, "content", "") for section in report.all_sections()]
        unsafe_markers = ("[ollama unavailable:", "[verification warning")
        return all(not any(marker in str(content).lower() for marker in unsafe_markers) for content in contents)

    @staticmethod
    def _merge(candidate, fallback):
        """Use model wording only where it supplied content; retain factual fallback elsewhere."""
        for field in ("strengths", "communication_analysis", "reflective_prompts", "recommendations"):
            if not getattr(candidate, field, None) and getattr(fallback, field, None):
                setattr(candidate, field, getattr(fallback, field))
        candidate.generation_metadata = {
            **getattr(candidate, "generation_metadata", {}),
            "fallback_available": True,
            "evidence_based": True,
        }
        return candidate
