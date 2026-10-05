"""Bounded learner input, strict provider contracts, and answer-safe public views."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.assessment import DraftQuestion
from app.schemas.retrieval import Citation

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Step = Annotated[str, StringConstraints(min_length=1, max_length=1000)]
Outcome = Literal["hypothesis", "no_clear_break", "insufficient_reasoning", "insufficient_evidence"]
Resolution = Literal["confirmed", "rejected", "inconclusive"]
Status = Literal["hypothesis", "no_clear_break", "insufficient_reasoning", "insufficient_evidence", "confirmed", "rejected", "inconclusive"]
EvidenceIDs = Annotated[list[uuid.UUID], Field(max_length=10)]


class DiagnosisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attempt_id: uuid.UUID
    reasoning_text: str | None = Field(None, max_length=8000)
    reasoning_steps: list[Step] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def require_reasoning(self):
        if any(not step.strip() for step in self.reasoning_steps):
            raise ValueError("Reasoning steps cannot be blank.")
        if not (self.reasoning_text or "").strip() and not self.reasoning_steps:
            raise ValueError("Supply reasoning_text or reasoning_steps.")
        if len(self.reasoning_text or "") + sum(map(len, self.reasoning_steps)) > 12000:
            raise ValueError("Combined reasoning cannot exceed 12000 characters.")
        return self


class ProbeDraft(DraftQuestion):
    question_text: Text
    options: list[Text] = Field(min_length=4, max_length=4)
    explanation: Text
    evidence_unit_ids: EvidenceIDs = Field(min_length=1)


class DiagnosisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Outcome
    observed_reasoning: Text
    first_break_step_index: int | None = Field(None, strict=True, ge=0)
    first_break_excerpt: Text | None = None
    hypothesis_text: Text | None = None
    target_concept_id: uuid.UUID | None = None
    evidence_unit_ids: EvidenceIDs = Field(default_factory=list)
    probe: ProbeDraft | None = None

    @model_validator(mode="after")
    def consistent_outcome(self):
        details = [self.first_break_excerpt, self.hypothesis_text, self.target_concept_id, self.probe]
        if self.outcome == "hypothesis":
            if not all(details) or not self.evidence_unit_ids:
                raise ValueError("A hypothesis requires a supported break, concept and probe.")
        elif any(x is not None for x in details) or self.first_break_step_index is not None or self.evidence_unit_ids:
            raise ValueError("No-fault outcomes cannot contain a hypothesis or probe.")
        return self


class DiagnosisVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["verified", "rejected"]
    first_break_supported: bool = Field(strict=True)
    hypothesis_supported: bool = Field(strict=True)
    target_allowed: bool = Field(strict=True)
    probe_isolates_hypothesis: bool = Field(strict=True)
    probe_answer_supported: bool = Field(strict=True)
    probe_is_fresh: bool = Field(strict=True)
    public_content_safe: bool = Field(strict=True)
    evidence_unit_ids: EvidenceIDs
    probe_evidence_unit_ids: EvidenceIDs


class PrerequisitePublic(BaseModel):
    edge_id: uuid.UUID
    prerequisite_concept_id: uuid.UUID
    target_concept_id: uuid.UUID
    name: str
    relation_type: str


class ProbePublic(BaseModel):
    id: uuid.UUID
    question_type: Literal["multiple_choice"] = "multiple_choice"
    question_text: str
    options: list[str]
    citations: list[Citation]


class DiagnosisPublic(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    learner_id: uuid.UUID
    attempt_id: uuid.UUID
    question_id: uuid.UUID
    reasoning_text: str | None
    reasoning_steps: list[str]
    status: Status
    observed_reasoning: str | None
    first_break_step_index: int | None
    first_break_excerpt: str | None
    hypothesis_text: str | None
    target_concept_id: uuid.UUID | None
    prerequisites: list[PrerequisitePublic]
    citations: list[Citation]
    probe: ProbePublic | None
    cold_start: bool
    created_at: datetime
    updated_at: datetime


class ProbeAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_option_index: int = Field(strict=True, ge=0, le=3)


class ProbeAttemptPublic(BaseModel):
    attempt_id: uuid.UUID
    probe_id: uuid.UUID
    diagnosis_id: uuid.UUID
    selected_option_index: int
    is_correct: bool | None
    correct_option_index: int | None
    explanation: str | None
    citations: list[Citation]
    diagnostic_outcome: Resolution
    resolution_applied: bool
    created_at: datetime
