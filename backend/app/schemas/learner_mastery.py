"""Pydantic schemas and contracts for Phase 5 Learner Concept Mastery."""

from datetime import datetime
import enum
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.services.learner_mastery import BKT_MODEL_VERSION


class MasteryUpdateStatus(str, enum.Enum):
    """Additive status indicating how an attempt affected learner mastery."""

    updated = "updated"
    skipped_unmapped = "skipped_unmapped"
    skipped_ambiguous = "skipped_ambiguous"
    skipped_repeated_question = "skipped_repeated_question"


class MasteryBand(str, enum.Enum):
    """Presentation-only mastery bands."""

    unseen = "unseen"
    needs_work = "needs_work"
    developing = "developing"
    strong = "strong"
    mastered = "mastered"


class LearnerMasteryUpdatePublic(BaseModel):
    """Public summary of a single concept mastery update following an eligible attempt."""

    concept_id: uuid.UUID
    concept_name: str
    prior_mastery: float
    posterior_mastery: float
    updated_mastery: float
    mastery_band: MasteryBand
    observation_count: int
    correct_count: int
    model_version: str

    model_config = ConfigDict(from_attributes=True)


class LearnerConceptMasteryPublic(BaseModel):
    """Public read model for learner concept mastery."""

    concept_id: uuid.UUID
    concept_name: str
    course_id: uuid.UUID
    learner_id: uuid.UUID
    model_version: str = BKT_MODEL_VERSION
    mastery_probability: float
    observation_count: int
    correct_count: int
    mastery_band: MasteryBand
    last_attempt_id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LearnerCourseMasteryResponse(BaseModel):
    """Course-wide list of concept masteries for a learner."""

    course_id: uuid.UUID
    learner_id: uuid.UUID
    model_version: str = BKT_MODEL_VERSION
    concepts: List[LearnerConceptMasteryPublic] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
