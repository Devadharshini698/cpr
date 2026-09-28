"""
PDF Report Generator for CPR Debriefing System.
Accepts ScoreReport + DebriefReport + FindingRecords.
Produces a formatted clinical debriefing PDF.

Sections:
  1. Cover page
  2. Scenario summary
  3. Domain scores with confidence indicators
  4. Protocol deviations
  5. Communication analysis
  6. Reflective prompts
  7. Recommendations
"""

import logging
import html
import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, KeepTogether
)

logger = logging.getLogger(__name__)

# ── Colour palette ──────────────────────────────────────────────
PRIMARY     = HexColor("#1F3A5F")   # deep navy
ACCENT      = HexColor("#0F6E56")   # clinical teal
MUTED       = HexColor("#5F5E5A")   # gray
LIGHT_BG    = HexColor("#F4F2EC")   # warm off-white
RULE        = HexColor("#D3D1C7")   # rule line

SEVERITY_COLORS = {
    "critical": HexColor("#A32D2D"),
    "high":     HexColor("#BA7517"),
    "moderate": HexColor("#185FA5"),
    "low":      HexColor("#3B6D11"),
}

CONFIDENCE_COLORS = {
    "high":   HexColor("#3B6D11"),
    "medium": HexColor("#BA7517"),
    "low":    HexColor("#A32D2D"),
}

GRADE_COLORS = {
    "Excellent":    HexColor("#3B6D11"),
    "Good":         HexColor("#185FA5"),
    "Needs Work":   HexColor("#BA7517"),
    "Critical":     HexColor("#A32D2D"),
    "A":            HexColor("#3B6D11"),
    "B":            HexColor("#185FA5"),
    "C":            HexColor("#BA7517"),
    "D":            HexColor("#BA7517"),
    "F":            HexColor("#A32D2D"),
}


# ── Style factory ───────────────────────────────────────────────
def _build_styles():
    base = getSampleStyleSheet()

    styles = {}

    styles["title"] = ParagraphStyle(
        "TitleS", parent=base["Title"],
        fontName="Helvetica-Bold", fontSize=22,
        textColor=white, spaceAfter=4,
        leading=26, alignment=TA_LEFT,
    )
    styles["subtitle"] = ParagraphStyle(
        "SubtitleS", parent=base["Normal"],
        fontName="Helvetica", fontSize=11,
        textColor=HexColor("#C8D8E8"),
        spaceAfter=0, leading=14, alignment=TA_LEFT,
    )
    styles["h1"] = ParagraphStyle(
        "H1S", parent=base["Heading1"],
        fontName="Helvetica-Bold", fontSize=14,
        textColor=PRIMARY, spaceBefore=16,
        spaceAfter=8, leading=17,
    )
    styles["h2"] = ParagraphStyle(
        "H2S", parent=base["Heading2"],
        fontName="Helvetica-Bold", fontSize=11.5,
        textColor=ACCENT, spaceBefore=10,
        spaceAfter=5, leading=14,
    )
    styles["body"] = ParagraphStyle(
        "BodyS", parent=base["Normal"],
        fontName="Helvetica", fontSize=10.5,
        textColor=black, leading=15.5,
        spaceAfter=8, alignment=TA_JUSTIFY,
    )
    styles["body_left"] = ParagraphStyle(
        "BodyLS", parent=base["Normal"],
        fontName="Helvetica", fontSize=10.5,
        textColor=black, leading=15.5,
        spaceAfter=6, alignment=TA_LEFT,
    )
    styles["small"] = ParagraphStyle(
        "SmallS", parent=base["Normal"],
        fontName="Helvetica", fontSize=9,
        textColor=MUTED, leading=12,
        spaceAfter=4, alignment=TA_LEFT,
    )
    styles["citation"] = ParagraphStyle(
        "CitationS", parent=base["Normal"],
        fontName="Helvetica-Oblique", fontSize=9,
        textColor=MUTED, leading=12,
        spaceAfter=4, alignment=TA_LEFT,
        leftIndent=10,
    )
    styles["callout"] = ParagraphStyle(
        "CalloutS", parent=base["Normal"],
        fontName="Helvetica-Oblique", fontSize=10.5,
        textColor=MUTED, leading=14.5,
        leftIndent=14, rightIndent=14,
        spaceBefore=6, spaceAfter=10,
        alignment=TA_LEFT,
    )
    styles["footer"] = ParagraphStyle(
        "FooterS", parent=base["Normal"],
        fontName="Helvetica", fontSize=8,
        textColor=MUTED, alignment=TA_CENTER,
    )
    return styles


def _hr():
    return HRFlowable(
        width="100%", thickness=0.5,
        color=RULE, spaceBefore=4, spaceAfter=10,
    )


def _table(data, col_widths, header=True, row_colors=None):
    cmds = [
        ("FONTNAME",     (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9.5),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 7),
        ("LINEBELOW",    (0, 0), (-1, -1), 0.25, RULE),
        ("LEADING",      (0, 0), (-1, -1), 13),
    ]
    if header:
        cmds += [
            ("BACKGROUND",    (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
            ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ]
    if row_colors:
        for row_idx, color in row_colors.items():
            cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), color))
    return Table(
        data, colWidths=col_widths, style=TableStyle(cmds),
        repeatRows=1 if header else 0,
    )


# ── Page decorations ────────────────────────────────────────────
def _page_decorations(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        2 * cm, 1.2 * cm,
        "CPR Debriefing System  |  Simulation Lab Report"
    )
    canvas.drawRightString(
        A4[0] - 2 * cm, 1.2 * cm,
        f"Page {doc.page}"
    )
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.3)
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.restoreState()


def _cover_page_decorations(canvas, doc):
    """Full-bleed navy cover on page 1 only."""
    if doc.page == 1:
        canvas.saveState()
        canvas.setFillColor(PRIMARY)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        # Accent stripe
        canvas.setFillColor(ACCENT)
        canvas.rect(0, A4[1] * 0.42, A4[0], 4, fill=1, stroke=0)
        canvas.restoreState()
    else:
        _page_decorations(canvas, doc)


# ── Section builders ────────────────────────────────────────────

def _build_cover(styles, metadata: dict) -> list:
    s = []
    s.append(Spacer(1, 3.5 * cm))
    s.append(Paragraph(
        "CPR Debriefing Report", styles["title"]
    ))
    s.append(Spacer(1, 0.3 * cm))
    s.append(Paragraph(
        f"Simulation Lab  ·  {metadata.get('date', '')}",
        styles["subtitle"]
    ))
    s.append(Spacer(1, 0.15 * cm))
    s.append(Paragraph(
        f"Session {metadata.get('session_id', '')}  "
        f"·  {metadata.get('scenario_name', '')}",
        styles["subtitle"]
    ))
    s.append(Spacer(1, 0.15 * cm))
    s.append(Paragraph(
        f"Team Leader: {metadata.get('team_leader_name', 'Unknown')}",
        styles["subtitle"]
    ))
    s.append(Spacer(1, 0.15 * cm))
    s.append(Paragraph(
        f"Guideline: {metadata.get('guideline_version', 'AHA 2020')}",
        styles["subtitle"]
    ))
    s.append(PageBreak())
    return s


def _build_scenario_summary(
    styles, metadata: dict, score_report, findings: list | None = None
) -> list:
    s = []
    s.append(Paragraph("Recording summary" if metadata.get("audio_only") else "Scenario summary", styles["h1"]))
    s.append(_hr())

    # Metadata table
    duration_s = metadata.get("duration_ms", 0) // 1000
    duration_str = f"{duration_s // 60}m {duration_s % 60:02d}s"
    meta_data = [
        ["Session ID",    metadata.get("session_id", "—")],
        ["Date",          metadata.get("date", "—")],
        ["Scenario",      metadata.get("scenario_name", "—")],
        ["Scenario type", metadata.get("scenario_type", "—")],
        ["Team leader",   metadata.get("team_leader_name", "—")],
        ["Team size",     str(metadata.get("team_size", "—"))],
        ["Duration",      duration_str],
        ["Guideline",     metadata.get("guideline_version", "AHA 2020")],
    ]
    if metadata.get("audio_only"):
        meta_data = [
            ["Session ID", metadata.get("session_id", "—")],
            ["Recording", metadata.get("scenario_name", "Audio-only debrief")],
            ["Mode", "Audio only - no patient simulation"],
            ["Duration", duration_str],
        ]
    s.append(_table(
        meta_data,
        col_widths=[5 * cm, 11.5 * cm],
        header=False,
    ))
    s.append(Spacer(1, 12))
    if metadata.get("audio_only"):
        s.append(Paragraph(
            "Clinical score: not assessed. This recording contains no verified simulator actions or patient telemetry.",
            styles["callout"],
        ))
        return s

    # Score summary strip — handle both object and dict
    def _attr(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    grade       = _attr(score_report, "overall_grade", _attr(score_report, "grade", "—"))
    grade_color = GRADE_COLORS.get(grade, MUTED)
    overall     = _attr(score_report, "overall_score", 0) or 0
    score_display = "Not assessed" if grade == "N/A" else f"{overall:.1f} / 100"
    # ScoreReport intentionally contains scoring aggregates, while ACLS rule
    # findings are carried separately to the renderer.  Build this strip from
    # that authoritative list so the headline cannot contradict the protocol
    # deviations section.
    finding_list = list(findings or [])
    n_findings = len(finding_list)
    by_sev = {"critical": 0, "high": 0, "moderate": 0}
    for finding in finding_list:
        severity = _get_value(finding, "severity", "info")
        severity = getattr(severity, "value", severity)
        key = str(severity).lower().replace("severity.", "")
        if key in by_sev:
            by_sev[key] += 1

    strip = [
        ["Overall score", "Grade", "Findings", "Critical", "High", "Moderate"],
        [
            score_display,
            grade,
            str(n_findings),
            str(by_sev.get("critical", by_sev.get("CRITICAL", 0))),
            str(by_sev.get("high", by_sev.get("HIGH", 0))),
            str(by_sev.get("moderate", by_sev.get("MODERATE", 0))),
        ],
    ]
    strip_style = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9.5),
        ("BACKGROUND",    (0, 1), (-1, 1), LIGHT_BG),
        ("FONTNAME",      (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 1), (-1, 1), 13),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR",     (1, 1), (1, 1), grade_color),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.25, RULE),
    ])
    w = (A4[0] - 4 * cm) / 6
    t = Table(strip, colWidths=[w] * 6, style=strip_style)
    s.append(t)
    return s


def _text(value, fallback="-"):
    """Safe compact display for scenario configuration values."""
    if value is None or value == "":
        return fallback
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) or fallback
    return str(value)


def _build_simulation_configuration(styles, configuration: dict, audio_only: bool = False) -> list:
    """Render the immutable launch specification separately from performance evidence."""
    if audio_only or not isinstance(configuration, dict) or not configuration:
        return []
    patient = configuration.get("patient") if isinstance(configuration.get("patient"), dict) else {}
    resources = configuration.get("resources") if isinstance(configuration.get("resources"), dict) else {}
    conditions = configuration.get("conditions") if isinstance(configuration.get("conditions"), list) else []
    checklist = configuration.get("checklist") if isinstance(configuration.get("checklist"), list) else []
    request = configuration.get("instructor_request") or configuration.get("generation_request")
    mode = _text(configuration.get("generation_mode", "guided_generator")).replace("_", " ").title()
    rows = [
        ["Generation mode", mode],
        ["Scenario ID", _text(configuration.get("scenario_id"))],
        ["Rhythm at launch", _text(configuration.get("rhythm_type"))],
        ["Difficulty", _text(configuration.get("level"))],
        ["Location", _text(configuration.get("location_label") or configuration.get("location"))],
        ["Speciality", _text(configuration.get("speciality_label") or configuration.get("speciality"))],
        ["Team design", _text(configuration.get("team_roles") or configuration.get("discipline_labels"))],
        ["Patient design", f"{_text(patient.get('age'))}-year-old {_text(patient.get('sex'))}; {_text(patient.get('weight_kg'))} kg"],
        ["Presentation", _text(patient.get("presentation"))],
        ["History", _text(patient.get("history"))],
        ["Resources", ", ".join(name.replace("_", " ") for name, enabled in resources.items() if enabled is True) or "Not specified"],
        ["Complications", _text(configuration.get("complications"), "None selected")],
        ["Scripted states", _text([c.get("name", "Unnamed state") for c in conditions if isinstance(c, dict)], "Not specified")],
        ["Checklist items", str(len(checklist))],
    ]
    if request:
        rows.append(["Instructor request", _text(request)])
    story = [Paragraph("Simulation configuration", styles["h1"]), _hr()]
    story.append(Paragraph(
        "This is the launch configuration, not evidence of actions performed by the team.",
        styles["small"],
    ))
    story.append(_table(rows, col_widths=[4.4 * cm, 12.1 * cm], header=False))
    return story


def _get_value(value, key, default=None):
    """Read a score/finding attribute from either a dataclass or a mapping."""
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


def _narrative_content(debrief_report, field: str) -> str:
    section = _get_value(debrief_report, field) if debrief_report else None
    if hasattr(section, "content"):
        return section.content or ""
    return section if isinstance(section, str) else ""


def _build_executive_summary(styles, score_report, findings: list, warnings: list) -> list:
    """A short, evidence-first briefing for the first report page."""
    grade = _get_value(score_report, "overall_grade", _get_value(score_report, "grade", "—"))
    overall = _get_value(score_report, "overall_score", 0) or 0
    total = _get_value(score_report, "total_findings", len(findings)) or len(findings)
    assessed = grade != "N/A"

    s = [Paragraph("Clinical debrief at a glance", styles["h1"]), _hr()]
    if assessed:
        text = (
            f"<b>{overall:.0f}/100 · {html.escape(str(grade))}</b> — "
            f"{total} protocol finding{'s' if total != 1 else ''} identified. "
            "Use the priorities below to guide the facilitated debrief."
        )
    else:
        text = (
            "<b>Assessment not available.</b> This session does not contain the "
            "validated cardiac-arrest event evidence required for an overall score. "
            "The report preserves the available conversation evidence without assigning a clinical grade."
        )
    s.append(Paragraph(text, styles["body_left"]))

    severity_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3, "info": 4}
    ranked = sorted(findings, key=lambda f: severity_order.get(str(_get_value(f, "severity", "info")).lower().replace("severity.", ""), 4))[:3]
    if ranked:
        s.append(Paragraph("Priority evidence", styles["h2"]))
        for finding in ranked:
            severity = str(_get_value(finding, "severity", "info")).replace("Severity.", "").upper()
            title = html.escape(str(_get_value(finding, "title", _get_value(finding, "rule_id", "Finding"))))
            description = html.escape(str(_get_value(finding, "description", _get_value(finding, "deviation_message", ""))))
            s.append(Paragraph(f"<b>{severity}</b> · {title}<br/>{description}", styles["body_left"]))

    meaningful_warnings = list(dict.fromkeys(warnings or []))[:2]
    if meaningful_warnings:
        s.append(Paragraph("Data confidence", styles["h2"]))
        for warning in meaningful_warnings:
            s.append(Paragraph(html.escape(str(warning)), styles["callout"]))
    return s


def _deduplicate_transcript_segments(transcript_segments) -> list:
    """Remove retries/duplicate uploads while retaining chronological dialogue."""
    unique, seen = [], set()
    for segment in sorted(transcript_segments or [], key=lambda item: int(item.get("timestamp_ms", 0) or 0)):
        text = str(segment.get("text", "")).strip()
        # Event labels such as ``shock_delivered`` are not spoken dialogue.
        if not text or (" " not in text and re.fullmatch(r"[a-z_]+", text.lower())):
            continue
        role = str(segment.get("actor_role", "unknown")).strip().lower()
        key = (int(segment.get("timestamp_ms", 0) or 0), role, re.sub(r"\s+", " ", text).lower())
        if key in seen:
            continue
        seen.add(key)
        clean = dict(segment)
        clean["text"] = text
        unique.append(clean)
    return unique


def _build_audio_only_review(styles, transcript_segments) -> list:
    """Describe observed speech without implying a simulator or verified actions."""
    count = len(transcript_segments)
    spoken = [segment for segment in transcript_segments if segment.get("source") != "synthetic_audio"]
    labels = sorted({str(segment.get("actor_role") or "unknown").replace("_", " ").title()
                     for segment in spoken})
    uncertain = sum(float(segment.get("confidence", 0) or 0) < 0.7 for segment in spoken)
    duration_ms = max((int(segment.get("end_ms", segment.get("timestamp_ms", 0)) or 0)
                       for segment in transcript_segments), default=0)
    s = [Paragraph("Audio evidence review", styles["h1"]), _hr()]
    s.append(Paragraph(
        "This is an audio-only debrief. No simulator vitals, rhythm, CPR-quality, shock, "
        "or medication telemetry was supplied. Spoken claims are not confirmation that "
        "a clinical action occurred; no clinical performance score is assigned.", styles["callout"]
    ))
    s.append(Paragraph("Recording and transcript coverage", styles["h2"]))
    s.append(Paragraph(
        f"{len(spoken)} observed speech segment(s); {count - len(spoken)} synthetic segment(s). "
        f"Last transcript timestamp: {duration_ms // 60000:02d}:{(duration_ms // 1000) % 60:02d}. "
        f"Role labels in transcript: {html.escape(', '.join(labels) if labels else 'none')}. "
        f"Low-confidence observed segments (&lt;0.70): {uncertain}.", styles["body_left"]
    ))
    s.append(Paragraph("How to review this evidence", styles["h2"]))
    for item in (
        "Compare introductions with speaker labels; verify any role before attributing later statements.",
        "Replay low-confidence or clinically important phrases against the original recording.",
        "Discuss whether orders were acknowledged and repeated back; a transcript alone cannot prove execution.",
        "Add independent observations or simulator logs before judging treatment timing or technical performance.",
    ):
        s.append(Paragraph("- " + html.escape(item), styles["body_left"]))
    return s


def _build_speech_clinical_discussion(styles, debrief_report) -> list:
    """Discussion cues from words alone, with no inferred patient actions."""
    metadata = getattr(debrief_report, "generation_metadata", {}) or {}
    topics = metadata.get("speech_topics", [])
    if not topics:
        return []
    s = [Paragraph("Speech-based clinical discussion - unverified", styles["h1"]), _hr()]
    s.append(Paragraph(
        "The following topics were selected from the automatic transcript, not from patient telemetry. "
        "Quotations may contain recognition errors. They are prompts for instructor review, "
        "not verified care, guideline-compliance findings, or a clinical score.", styles["callout"]
    ))
    for topic in topics:
        seconds = int(topic.get("timestamp_ms", 0)) // 1000
        clock = f"{seconds // 60:02d}:{seconds % 60:02d}"
        label = html.escape(str(topic.get("topic", "Topic")))
        excerpt = html.escape(str(topic.get("excerpt", "")))
        question = html.escape(str(topic.get("question", "")))
        s.append(Paragraph(f"{clock} - {label}", styles["h2"]))
        s.append(Paragraph(f"Transcript excerpt (unverified): '{excerpt}'", styles["body_left"]))
        s.append(Paragraph(f"Discussion question: {question}", styles["body_left"]))
        s.append(Spacer(1, 5))
    return s


def _build_domain_scores(styles, score_report) -> list:
    s = []
    s.append(Paragraph("Domain scores", styles["h1"]))
    s.append(_hr())
    s.append(Paragraph(
        "Scores use the versioned rule bundle listed in this report and the recorded "
        "session evidence. Confidence "
        "indicators reflect data completeness — scores marked medium "
        "or low confidence should not be over-interpreted.",
        styles["body"],
    ))

    domain_scores_raw = getattr(score_report, "domain_scores", []) if not isinstance(score_report, dict) else score_report.get("domain_scores", [])
    if not domain_scores_raw:
        s.append(Paragraph("No domain scores available.", styles["body_left"]))
        return s

    if isinstance(domain_scores_raw, dict):
        items = list(domain_scores_raw.items())
    elif isinstance(domain_scores_raw, list):
        items = []
        for ds in domain_scores_raw:
            if isinstance(ds, dict):
                d_key = ds.get("domain_label", ds.get("domain_key", ds.get("domain", "Domain")))
            else:
                d_key = getattr(ds, "domain_label", getattr(ds, "domain_key", getattr(ds, "domain", "Domain")))
            items.append((d_key, ds))
    else:
        items = []

    rows = [["Domain", "Score", "Confidence", "Key finding"]]
    row_colors = {}
    for i, (domain, ds) in enumerate(items, start=1):
        if isinstance(ds, dict):
            score_val = ds.get("final_score", ds.get("score", 0))
            ci_lower  = ds.get("ci_lower", score_val)
            ci_upper  = ds.get("ci_upper", score_val)
            conf      = ds.get("completeness_flag", ds.get("confidence", "medium"))
            conf_str  = conf.value if hasattr(conf, "value") else str(conf)
            conf_label = conf_str.title() + " confidence"
            key = ds.get("key_finding", "") or ds.get("completeness_note", "") or "Evidence recorded; see sub-signal details."
            is_wide = ds.get("is_wide_ci", False)
        else:
            score_val = getattr(ds, "final_score", getattr(ds, "score", 0))
            ci_lower  = getattr(ds, "ci_lower", score_val)
            ci_upper  = getattr(ds, "ci_upper", score_val)
            conf      = getattr(ds, "completeness_flag", getattr(ds, "confidence", "medium"))
            conf_str  = conf.value if hasattr(conf, "value") else str(conf)
            conf_label = conf_str.title() + " confidence"
            key = getattr(ds, "key_finding", "") or getattr(ds, "completeness_note", "") or "Evidence recorded; see sub-signal details."
            is_wide = getattr(ds, "is_wide_ci", False)

        score_str = (
            f"{score_val:.0f}/100\n"
            f"CI: {ci_lower:.0f}–{ci_upper:.0f}"
        )
        if is_wide:
            score_str += " ⚠"

        rows.append([
            Paragraph(html.escape(str(domain).replace("_", " ").title()), styles["small"]),
            Paragraph(html.escape(score_str).replace("\n", "<br/>"), styles["small"]),
            Paragraph(html.escape(conf_label), styles["small"]),
            Paragraph(html.escape(str(key)), styles["small"]),
        ])

        if str(conf_str).lower() in ["low", "uncertain", "low_data"]:
            row_colors[i] = HexColor("#FFF4F4")

    s.append(_table(
        rows,
        col_widths=[4.5 * cm, 3.5 * cm, 4 * cm, 4.5 * cm],
        row_colors=row_colors,
    ))

    warnings = getattr(score_report, "data_completeness_warnings", []) if not isinstance(score_report, dict) else score_report.get("data_completeness_warnings", [])
    if warnings:
        s.append(Spacer(1, 6))
        for w in warnings:
            s.append(Paragraph(f"⚠  {w}", styles["small"]))

    return s


def _build_protocol_deviations(
    styles, findings: list
) -> list:
    s = []
    s.append(Paragraph("Protocol deviations", styles["h1"]))
    s.append(_hr())

    if not findings:
        s.append(Paragraph(
            "No protocol deviations detected.", styles["body_left"]
        ))
        return s

    def _get_sev(f):
        if isinstance(f, dict):
            return str(f.get("severity", "info")).lower()
        sev = getattr(f, "severity", "info")
        return str(sev.value if hasattr(sev, "value") else sev).lower()

    sev_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3, "info": 4}
    sorted_findings = sorted(
        findings,
        key=lambda f: sev_order.get(_get_sev(f), 4)
    )

    for finding in sorted_findings:
        sev = _get_sev(finding)
        sev_color = SEVERITY_COLORS.get(sev, MUTED)
        if isinstance(finding, dict):
            ts_ms = int(finding.get("timestamp_sec", 0) * 1000) if finding.get("timestamp_sec") else finding.get("timestamp_ms", 0)
            f_title = finding.get("rule_id", finding.get("title", "—"))
            f_desc = finding.get("deviation_message", finding.get("description", ""))
        else:
            ts_ms = getattr(finding, "timestamp_ms", 0)
            f_title = getattr(finding, "title", "—")
            f_desc = getattr(finding, "description", "")

        ts_s = ts_ms // 1000
        ts_str = f"{ts_s // 60}:{ts_s % 60:02d}"

        block = []

        # Finding header row
        header = _table(
            [[
                Paragraph(
                    f"<b>{sev.upper()}</b>",
                    ParagraphStyle(
                        "SevP", fontName="Helvetica-Bold",
                        fontSize=9, textColor=white,
                    )
                ),
                Paragraph(
                    f"<b>{f_title}</b>",
                    ParagraphStyle(
                        "TitleP", fontName="Helvetica-Bold",
                        fontSize=10.5, textColor=PRIMARY,
                    )
                ),
                Paragraph(
                    f"@ {ts_str}",
                    ParagraphStyle(
                        "TimeP", fontName="Helvetica",
                        fontSize=9, textColor=MUTED,
                        alignment=TA_RIGHT,
                    )
                ),
            ]],
            col_widths=[2 * cm, 11 * cm, 3.5 * cm],
            header=False,
        )
        header.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, 0), sev_color),
            ("BACKGROUND",    (1, 0), (-1, 0), LIGHT_BG),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ]))
        block.append(header)

        # Description
        block.append(Paragraph(
            f_desc,
            styles["body_left"]
        ))

        # Guideline citation
        f_citation = finding.get("guideline", finding.get("guideline_citation", "")) if isinstance(finding, dict) else getattr(finding, "guideline_citation", "")
        if f_citation:
            block.append(Paragraph(
                f"Guideline reference: {f_citation}",
                styles["citation"]
            ))

        # Finding ID for traceability
        fid = finding.get("finding_id", "") if isinstance(finding, dict) else getattr(finding, "finding_id", "")
        if fid:
            block.append(Paragraph(
                f"Finding ID: {fid}",
                styles["small"]
            ))

        block.append(Spacer(1, 8))
        s.append(KeepTogether(block))

    return s


def _build_communication_analysis(
    styles, debrief_report, score_report, transcript_segments=None, include_full_transcript=False
) -> list:
    s = []
    s.append(Paragraph("Communication analysis", styles["h1"]))
    s.append(_hr())

    comm_text = _narrative_content(debrief_report, "communication_analysis")

    if comm_text:
        s.append(Paragraph(comm_text, styles["body"]))
    elif not transcript_segments:
        s.append(Paragraph(
            "Detailed communication analysis requires audio transcription. "
            "Ensure lapel and ceiling mic audio files are provided for "
            "full closed-loop communication metrics.",
            styles["callout"]
        ))

    if transcript_segments:
        display_segments = transcript_segments if include_full_transcript else transcript_segments[:6]
        heading = "Transcript appendix" if include_full_transcript else "Selected communication evidence"
        s.append(Paragraph(heading, styles["h2"]))
        s.append(Paragraph(
            "Role labels are based on spoken introductions and diarization when available. "
            + ("This appendix contains the de-duplicated transcript." if include_full_transcript
               else "The complete de-duplicated transcript is included in the appendix."),
            styles["small"],
        ))
        rows = [["Time", "Role / speaker", "Transcript"]]
        for segment in display_segments:
            timestamp = int(segment.get("timestamp_ms", 0)) // 1000
            clock = f"{timestamp // 60:02d}:{timestamp % 60:02d}"
            raw_role = str(segment.get("actor_role", "unknown"))
            role = (
                "Team roster declaration"
                if segment.get("role_evidence") == "roster_declaration"
                else ("Ambiguous: " + " or ".join(raw_role.split("+"))).replace("_", " ").title()
                if "+" in raw_role
                else raw_role.replace("_", " ").title()
            )
            name = segment.get("speaker_name")
            speaker = f"{role} - {name}" if name else role
            rows.append([
                Paragraph(html.escape(clock), styles["small"]),
                Paragraph(html.escape(speaker), styles["small"]),
                Paragraph(html.escape(str(segment.get("text", ""))), styles["small"]),
            ])
        s.append(_table(rows, col_widths=[1.5 * cm, 4.1 * cm, 10.9 * cm]))

    return s


def _build_reflective_prompts(
    styles, findings: list, debrief_report
) -> list:
    s = []
    s.append(Paragraph("Reflective prompts", styles["h1"]))
    s.append(_hr())
    s.append(Paragraph(
        "The following questions are mapped to specific findings "
        "detected during this session. Use them to guide the "
        "debriefing conversation with the team leader.",
        styles["body"],
    ))

    prompts_text = _narrative_content(debrief_report, "reflective_prompts")

    if prompts_text:
        s.append(Paragraph(prompts_text, styles["body"]))
    else:
        sev_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
        sorted_findings = sorted(
            findings,
            key=lambda f: sev_order.get(
                f.severity.value
                if hasattr(f.severity, "value") else f.severity, 4
            )
        )[:6]
        for i, finding in enumerate(sorted_findings, 1):
            prompt = getattr(finding, "reflective_prompt", "")
            if prompt:
                s.append(Paragraph(
                    f"<b>{i}.</b> {prompt}",
                    styles["body_left"]
                ))
                s.append(Spacer(1, 4))

    return s


def _build_recommendations(
    styles, findings: list, debrief_report
) -> list:
    s = []
    s.append(Paragraph("Recommendations", styles["h1"]))
    s.append(_hr())
    s.append(Paragraph(
        "Ranked by clinical impact. Address critical and high-severity "
        "findings before moderate ones in the next training session.",
        styles["body"],
    ))

    rec_text = _narrative_content(debrief_report, "recommendations")

    if rec_text:
        s.append(Paragraph(rec_text, styles["body"]))
    else:
        seen = set()
        rank = 1
        sev_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
        sorted_findings = sorted(
            findings,
            key=lambda f: sev_order.get(
                f.severity.value
                if hasattr(f.severity, "value") else f.severity, 4
            )
        )
        for finding in sorted_findings:
            rec = getattr(finding, "recommendation", "")
            if rec and rec not in seen:
                seen.add(rec)
                s.append(Paragraph(
                    f"<b>{rank}.</b> {rec}",
                    styles["body_left"]
                ))
                rank += 1
                if rank > 8:
                    break

    return s


def _build_strengths(styles, debrief_report) -> list:
    s = []
    strengths_text = _narrative_content(debrief_report, "strengths")

    if strengths_text:
        s.append(Paragraph("Strengths", styles["h1"]))
        s.append(_hr())
        s.append(Paragraph(strengths_text, styles["body"]))

    return s


# ── Main entry point ────────────────────────────────────────────

def generate_pdf(
    score_report,
    findings: list,
    timeline,
    output_path,
    debrief_report=None,
) -> Path:
    """
    Generate the full debriefing PDF.

    Args:
        score_report:   ScoreReport from scoring_engine
        findings:       List of FindingRecord from ACLS FSM
        timeline:       UnifiedTimeline (or any object with session fields)
        output_path:    Where to write the PDF (str or Path)
        debrief_report: Optional DebriefReport from claude_api

    Returns:
        Path to the generated PDF
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()

    # Build metadata dict from timeline
    metadata = {
        "session_id":        getattr(timeline, "session_id",        "—"),
        "date":              getattr(timeline, "session_date",
                             getattr(timeline, "date",               "—")),
        "scenario_name":     getattr(timeline, "scenario_name",      "—"),
        "scenario_type":     getattr(timeline, "scenario_type",      "—"),
        "scenario_configuration": getattr(timeline, "scenario_configuration", {}) or {},
        "team_leader_name":  getattr(timeline, "team_leader_name",
                             getattr(timeline, "team_leader_id",     "—")),
        "team_size":         getattr(timeline, "team_size",          "—"),
        "duration_ms":       getattr(timeline, "duration_ms",        0),
        "guideline_version": getattr(timeline, "guideline_version",  "Unversioned legacy rules"),
    }

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"CPR Debrief — {metadata['session_id']}",
        author="CPR Debriefing System",
    )

    transcript_segments = _deduplicate_transcript_segments(
        getattr(timeline, "raw_segments", None)
    )
    warnings = _get_value(score_report, "data_completeness_warnings", []) or []
    domain_scores = _get_value(score_report, "domain_scores", []) or []
    # Speech-topic extraction in an audio-only session intentionally creates
    # unverified timeline items.  They must not turn its communication report
    # into a patient-monitor/clinical report merely because they resemble an
    # ACLS event type.
    audio_only = bool(getattr(timeline, "audio_only", False)) or not any(
        str(getattr(getattr(event, "event_type", None), "value", getattr(event, "event_type", "")))
        not in {"scenario_marker", "AUDIO_STATUS"}
        for event in (getattr(timeline, "events", None) or [])
    )
    metadata["audio_only"] = audio_only
    if audio_only:
        metadata["scenario_type"] = "Audio only - no patient simulation"

    # The report starts with clinically useful information rather than a cover-only page.
    story = [Paragraph("Audio-only Team Debrief Report" if audio_only else "CPR Clinical Debrief Report", styles["h1"])]
    story += _build_scenario_summary(styles, metadata, score_report, findings)
    story += _build_simulation_configuration(styles, metadata["scenario_configuration"], audio_only=audio_only)
    story.append(Spacer(1, 10))
    story += _build_executive_summary(styles, score_report, findings, warnings)
    if audio_only and transcript_segments:
        story.append(Spacer(1, 14))
        story += _build_audio_only_review(styles, transcript_segments)
        story.append(Spacer(1, 10))
        story += _build_speech_clinical_discussion(styles, debrief_report)
    if domain_scores:
        story.append(PageBreak())
        story += _build_domain_scores(styles, score_report)
    if findings:
        story.append(PageBreak())
        story += _build_protocol_deviations(styles, findings)

    communication = _build_communication_analysis(
        styles, debrief_report, score_report, None if audio_only else transcript_segments,
    ) if transcript_segments or _narrative_content(debrief_report, "communication_analysis") else []
    strengths = _build_strengths(styles, debrief_report)
    if communication or strengths:
        story += communication
        story += strengths

    has_prompts = bool(_narrative_content(debrief_report, "reflective_prompts")) or any(
        _get_value(finding, "reflective_prompt", "") for finding in findings
    )
    has_recommendations = bool(_narrative_content(debrief_report, "recommendations")) or any(
        _get_value(finding, "recommendation", "") for finding in findings
    )
    if has_prompts:
        story.append(PageBreak())
        story += _build_reflective_prompts(styles, findings, debrief_report)
    if has_recommendations:
        story.append(PageBreak())
        story += _build_recommendations(styles, findings, debrief_report)
    # Short recordings are already fully visible as selected evidence. Longer
    # recordings retain a complete, de-duplicated appendix for auditability.
    if len(transcript_segments) > 6:
        story.append(PageBreak())
        story += _build_communication_analysis(
            styles, None, score_report, transcript_segments, include_full_transcript=True,
        )

    doc.build(
        story,
        onFirstPage=_page_decorations,
        onLaterPages=_page_decorations,
    )

    logger.info(f"PDF generated: {output_path}")
    return output_path
