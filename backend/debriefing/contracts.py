"""Validated wire contracts. All times are milliseconds from session start."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

RULE_SET = "imsr-acls-2025-bundle-v1"

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

class Segment(Contract):
    segment_id: str
    timestamp_ms: int = Field(ge=0, strict=True)
    end_ms: int = Field(ge=0, strict=True)
    text: str
    speaker_label: str = "unknown"
    # The acoustic diarization label is retained for traceability, while this
    # optional spoken name is what is shown in the debrief report.
    speaker_name: str | None = None
    actor_role: str = "unknown"
    role_evidence: str = "unknown"
    source: Literal["manual", "simman", "lapel_audio", "ceiling_audio", "synthetic_audio"] = "manual"
    confidence: float = Field(default=1.0, ge=0, le=1)
    timestamp_inferred: bool = False

    @model_validator(mode="after")
    def ordered_times(self):
        if self.end_ms < self.timestamp_ms:
            raise ValueError("end_ms must be at or after timestamp_ms")
        return self

class Event(Contract):
    event_id: str
    event_type: str = Field(min_length=1)
    timestamp_ms: int = Field(ge=0, strict=True)
    actor_role: str = "unknown"
    source: Literal["manual", "simman", "lapel_audio", "ceiling_audio"] = "simman"
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence: str = ""
    timestamp_inferred: bool = False

class Session(Contract):
    schema_version: Literal["1.0"] = "1.0"
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    scenario_name: str = "Clinical simulation"
    scenario_type: str = "unknown"
    scenario_configuration: dict[str, Any] = Field(default_factory=dict)
    team_leader_name: str = "Unknown"
    team_size: int = Field(default=1, ge=1, le=100)
    duration_ms: int = Field(default=0, ge=0, strict=True)
    date: str = ""
    guideline_version: Literal["imsr-acls-2025-bundle-v1"] = RULE_SET
    requested_guideline: str | None = None
    segments: list[Segment] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def session_bounds(self):
        ids = [e.event_id for e in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate event_id in session")
        end = max([0] + [e.timestamp_ms for e in self.events] + [s.end_ms for s in self.segments])
        if self.duration_ms and end > self.duration_ms:
            raise ValueError("event or segment extends beyond session duration")
        if not self.duration_ms:
            self.duration_ms = end
        return self

class Classification(Contract):
    algorithm: str
    sub_type: str | None = None
    status: Literal["classified", "insufficient_data", "ambiguous"]
    evidence_event_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float | None = None  # No calibrated probability exists for these rules.

class Report(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    schema_version: Literal["1.0"] = "1.0"
    session_id: str
    engine_version: str
    rule_set: str
    rule_set_hash: str
    input_hash: str
    classification: Classification
    overall_score: float | None
    grade: str
    warnings: list[str]
