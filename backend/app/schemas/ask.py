import enum
import json
import uuid
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.evidence_unit import Modality
from app.schemas.retrieval import Citation, EvidenceBoundaryDecisionSchema


class AskMode(str, enum.Enum):
    just_answer = "just_answer"
    explain = "explain"
    guide = "guide"


class AskStatus(str, enum.Enum):
    answered = "answered"
    declined = "declined"


class GroundedAnswerBlock(BaseModel):
    text: str
    citations: List[Citation]

    model_config = ConfigDict(from_attributes=True)

    @field_validator("text")
    @classmethod
    def not_blank_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Answer block text cannot be blank.")
        return s

    @field_validator("citations")
    @classmethod
    def at_least_one_citation(cls, v: List[Citation]) -> List[Citation]:
        if not v:
            raise ValueError("Every answer block must contain at least one citation.")
        return v


class AskRequest(BaseModel):
    question: str = Field(..., max_length=4000)
    mode: AskMode = AskMode.explain
    top_k: int = Field(8, ge=1, le=20)
    modalities: Optional[List[Modality]] = None
    source_version_ids: Optional[List[uuid.UUID]] = None

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Question cannot be blank or whitespace-only.")
        if len(s) > 4000:
            raise ValueError("Question cannot exceed 4000 characters.")
        return s


class AskResponse(BaseModel):
    status: AskStatus
    mode: AskMode
    answer: Optional[str] = None
    blocks: List[GroundedAnswerBlock] = Field(default_factory=list)
    next_question: Optional[str] = None
    decline_message: Optional[str] = None
    evidence_boundary: EvidenceBoundaryDecisionSchema
    used_evidence_unit_ids: List[uuid.UUID] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_status_contract(self) -> "AskResponse":
        if self.status == AskStatus.answered:
            if not self.answer or not self.answer.strip():
                raise ValueError("Answered response must have a non-empty answer.")
            if not self.blocks:
                raise ValueError("Answered response must have at least one block.")
            if self.decline_message is not None:
                raise ValueError("Answered response must not have a decline message.")
        elif self.status == AskStatus.declined:
            if self.answer is not None:
                raise ValueError("Declined response must have answer=None.")
            if self.blocks:
                raise ValueError("Declined response must have empty blocks.")
            if self.next_question is not None:
                raise ValueError("Declined response must have next_question=None.")
            if not self.decline_message:
                raise ValueError("Declined response must have a decline message.")
            if self.used_evidence_unit_ids:
                raise ValueError("Declined response must have empty used_evidence_unit_ids.")
        return self


# ---------------------------------------------------------------------------
# Strict LLM Draft Schemas
# ---------------------------------------------------------------------------

class LLMAnswerBlockDraft(BaseModel):
    text: str
    evidence_unit_ids: List[uuid.UUID]

    @field_validator("text")
    @classmethod
    def validate_block_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Block text cannot be empty.")
        return s

    @field_validator("evidence_unit_ids")
    @classmethod
    def validate_and_dedup_ids(cls, v: List[uuid.UUID]) -> List[uuid.UUID]:
        if not v:
            raise ValueError("Block must contain at least one evidence_unit_id.")
        seen: set[uuid.UUID] = set()
        deduped: List[uuid.UUID] = []
        for uid in v:
            if uid not in seen:
                seen.add(uid)
                deduped.append(uid)
        return deduped


class LLMAnswerDraft(BaseModel):
    blocks: List[LLMAnswerBlockDraft] = Field(..., min_length=1, max_length=8)
    next_question: Optional[str] = None

    def validate_for_mode(self, mode: AskMode) -> None:
        if mode == AskMode.guide:
            if self.next_question is None or not self.next_question.strip():
                raise ValueError("next_question is required for guide mode.")
            self.next_question = self.next_question.strip()
        elif mode in (AskMode.just_answer, AskMode.explain):
            if self.next_question is not None:
                raise ValueError(f"next_question must not be present for {mode.value} mode.")
