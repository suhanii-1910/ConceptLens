"""Pydantic schemas and contracts for Phase 4 Grounded Assessment System."""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.evidence_unit import Modality
from app.schemas.retrieval import Citation, EvidenceBoundaryDecisionSchema
from app.schemas.learner_mastery import MasteryUpdateStatus, LearnerMasteryUpdatePublic


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AssessmentQuestionType(str, enum.Enum):
    multiple_choice = "multiple_choice"


class AssessmentDifficulty(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class AssessmentQuestionVerificationStatus(str, enum.Enum):
    verified = "verified"
    rejected = "rejected"
    unverified = "unverified"


class QuestionVerificationVerdict(str, enum.Enum):
    verified = "verified"
    rejected = "rejected"


class AssessmentGenerationStatus(str, enum.Enum):
    generated = "generated"
    declined = "declined"
    no_verified_questions = "no_verified_questions"


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class AssessmentGenerationRequest(BaseModel):
    focus: str = Field(..., max_length=2000)
    count: int = Field(3, ge=1, le=5)
    difficulty: AssessmentDifficulty = AssessmentDifficulty.medium
    top_k: int = Field(12, ge=1, le=20)
    modalities: Optional[List[Modality]] = None
    source_version_ids: Optional[List[uuid.UUID]] = None

    @field_validator("focus")
    @classmethod
    def validate_focus(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Focus cannot be blank or whitespace-only.")
        if len(s) > 2000:
            raise ValueError("Focus cannot exceed 2000 characters.")
        return s

    @field_validator("count", mode="before")
    @classmethod
    def validate_count(cls, v: Any) -> int:
        if isinstance(v, bool):
            raise ValueError("Count must be an integer, not a boolean.")
        if not isinstance(v, int):
            raise ValueError("Count must be an integer.")
        if v < 1 or v > 5:
            raise ValueError("Count must be between 1 and 5.")
        return v

    @field_validator("top_k", mode="before")
    @classmethod
    def validate_top_k(cls, v: Any) -> int:
        if isinstance(v, bool):
            raise ValueError("top_k must be an integer, not a boolean.")
        if not isinstance(v, int):
            raise ValueError("top_k must be an integer.")
        if v < 1 or v > 20:
            raise ValueError("top_k must be between 1 and 20.")
        return v


class AssessmentAttemptCreate(BaseModel):
    learner_id: uuid.UUID
    selected_option_index: int = Field(..., ge=0, le=3)

    @field_validator("selected_option_index", mode="before")
    @classmethod
    def validate_selected_option_index(cls, v: Any) -> int:
        if isinstance(v, bool):
            raise ValueError("selected_option_index must be an integer, not a boolean.")
        if not isinstance(v, int):
            raise ValueError("selected_option_index must be an integer.")
        if v < 0 or v > 3:
            raise ValueError("selected_option_index must be between 0 and 3.")
        return v


# ---------------------------------------------------------------------------
# Public Response Schemas (Never reveal answer keys / explanations prematurely)
# ---------------------------------------------------------------------------

class AssessmentQuestionPublic(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    question_type: AssessmentQuestionType = AssessmentQuestionType.multiple_choice
    difficulty: AssessmentDifficulty
    question_text: str
    options: List[str]
    citations: List[Citation] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssessmentGenerationResponse(BaseModel):
    status: AssessmentGenerationStatus
    questions: List[AssessmentQuestionPublic] = Field(default_factory=list)
    requested_count: int
    generated_count: int
    rejected_count: int
    decline_message: Optional[str] = None
    evidence_boundary: EvidenceBoundaryDecisionSchema

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_status_contract(self) -> "AssessmentGenerationResponse":
        if self.status == AssessmentGenerationStatus.generated:
            if not self.questions:
                raise ValueError("Generated status must contain at least one question.")
            if self.decline_message is not None:
                raise ValueError("Generated status must not have a decline message.")
        elif self.status == AssessmentGenerationStatus.declined:
            if self.questions:
                raise ValueError("Declined status must have empty questions.")
            if not self.decline_message:
                raise ValueError("Declined status must include a decline message.")
        elif self.status == AssessmentGenerationStatus.no_verified_questions:
            if self.questions:
                raise ValueError("no_verified_questions status must have empty questions.")
        return self


class AssessmentAttemptResponse(BaseModel):
    attempt_id: uuid.UUID
    question_id: uuid.UUID
    course_id: uuid.UUID
    learner_id: uuid.UUID
    selected_option_index: int
    is_correct: bool
    correct_option_index: int
    correct_option_text: str
    explanation: str
    citations: List[Citation]
    created_at: datetime
    mastery_update_status: Optional[MasteryUpdateStatus] = None
    mastery_update: Optional[LearnerMasteryUpdatePublic] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Strict LLM Draft & Verifier Schemas
# ---------------------------------------------------------------------------

class DraftQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_text: str
    options: List[str]
    correct_option_index: int
    explanation: str
    evidence_unit_ids: List[uuid.UUID]

    @field_validator("question_text")
    @classmethod
    def validate_question_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("question_text cannot be blank.")
        if len(s) > 2000:
            raise ValueError("question_text cannot exceed 2000 characters.")
        return s

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: List[str]) -> List[str]:
        if len(v) != 4:
            raise ValueError("options must contain exactly 4 choices.")
        cleaned: List[str] = []
        normalized_seen: set[str] = set()
        for opt in v:
            if not isinstance(opt, str):
                raise ValueError("Each option must be a string.")
            s = opt.strip()
            if not s:
                raise ValueError("Option text cannot be blank.")
            norm = s.lower()
            if norm in normalized_seen:
                raise ValueError(f"Duplicate option detected: '{s}'")
            normalized_seen.add(norm)
            cleaned.append(s)
        return cleaned

    @field_validator("correct_option_index", mode="before")
    @classmethod
    def validate_correct_index(cls, v: Any) -> int:
        if isinstance(v, bool):
            raise ValueError("correct_option_index must be an integer, not a boolean.")
        if not isinstance(v, int):
            raise ValueError("correct_option_index must be an integer.")
        if v < 0 or v > 3:
            raise ValueError("correct_option_index must be between 0 and 3.")
        return v

    @field_validator("explanation")
    @classmethod
    def validate_explanation(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("explanation cannot be blank.")
        return s

    @field_validator("evidence_unit_ids")
    @classmethod
    def validate_evidence_ids(cls, v: List[uuid.UUID]) -> List[uuid.UUID]:
        if not v:
            raise ValueError("evidence_unit_ids must contain at least one ID.")
        seen: set[uuid.UUID] = set()
        deduped: List[uuid.UUID] = []
        for uid in v:
            if uid not in seen:
                seen.add(uid)
                deduped.append(uid)
        return deduped


class GeneratorDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: List[DraftQuestion]


class VerifierItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_index: int
    verdict: QuestionVerificationVerdict
    evidence_unit_ids: List[uuid.UUID] = Field(default_factory=list)

    @field_validator("question_index", mode="before")
    @classmethod
    def validate_question_index(cls, v: Any) -> int:
        if isinstance(v, bool):
            raise ValueError("question_index must be an integer, not a boolean.")
        if not isinstance(v, int):
            raise ValueError("question_index must be an integer.")
        if v < 0:
            raise ValueError("question_index cannot be negative.")
        return v

    @field_validator("evidence_unit_ids")
    @classmethod
    def validate_verifier_evidence_ids(cls, v: List[uuid.UUID]) -> List[uuid.UUID]:
        seen: set[uuid.UUID] = set()
        deduped: List[uuid.UUID] = []
        for uid in v:
            if uid not in seen:
                seen.add(uid)
                deduped.append(uid)
        return deduped


class VerifierResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verifications: List[VerifierItem]
