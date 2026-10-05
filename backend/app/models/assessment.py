"""Assessment models for Phase 4 Grounded Assessment System."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.learner_mastery import assessment_question_concept_link
from app.schemas.assessment import (
    AssessmentDifficulty,
    AssessmentQuestionType,
    AssessmentQuestionVerificationStatus,
)
from app.schemas.learner_mastery import MasteryUpdateStatus


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_type: Mapped[AssessmentQuestionType] = mapped_column(
        Enum(AssessmentQuestionType, name="assessment_question_type_enum"),
        default=AssessmentQuestionType.multiple_choice,
        nullable=False,
    )
    difficulty: Mapped[AssessmentDifficulty] = mapped_column(
        Enum(AssessmentDifficulty, name="assessment_difficulty_enum"),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSONB, nullable=False)
    correct_option_index: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_unit_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    citation_snapshots: Mapped[list] = mapped_column(JSONB, nullable=False)
    verification_status: Mapped[AssessmentQuestionVerificationStatus] = mapped_column(
        Enum(
            AssessmentQuestionVerificationStatus,
            name="assessment_question_verification_status_enum",
        ),
        default=AssessmentQuestionVerificationStatus.verified,
        nullable=False,
    )
    generation_focus: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "correct_option_index >= 0 AND correct_option_index <= 3",
            name="ck_assessment_questions_correct_option_index",
        ),
        sa.Index("ix_assessment_questions_course_id_created_at", "course_id", "created_at"),
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="assessment_questions")  # noqa: F821
    concepts: Mapped[list["Concept"]] = relationship(  # noqa: F821
        secondary=assessment_question_concept_link,
        back_populates="assessment_questions",
    )
    attempts: Mapped[list["AssessmentAttempt"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    selected_option_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    mastery_update_status: Mapped[MasteryUpdateStatus | None] = mapped_column(
        Enum(MasteryUpdateStatus, name="mastery_update_status_enum"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        sa.UniqueConstraint("id", "question_id", "course_id", "learner_id", name="uq_assessment_attempt_diagnosis_scope"),
        CheckConstraint(
            "selected_option_index >= 0 AND selected_option_index <= 3",
            name="ck_assessment_attempts_selected_option_index",
        ),
        sa.Index("ix_assessment_attempts_question_id_created_at", "question_id", "created_at"),
        sa.Index("ix_assessment_attempts_learner_id_created_at", "learner_id", "created_at"),
        sa.Index("ix_assessment_attempts_course_id_created_at", "course_id", "created_at"),
    )

    # Relationships
    question: Mapped["AssessmentQuestion"] = relationship(back_populates="attempts")
    course: Mapped["Course"] = relationship(back_populates="assessment_attempts")  # noqa: F821
