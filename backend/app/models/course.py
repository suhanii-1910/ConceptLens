"""Course model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    source_versions: Mapped[list["SourceVersion"]] = relationship(  # noqa: F821
        back_populates="course", cascade="all, delete-orphan"
    )
    evidence_units: Mapped[list["EvidenceUnit"]] = relationship(  # noqa: F821
        back_populates="course", cascade="all, delete-orphan"
    )
    concepts: Mapped[list["Concept"]] = relationship(  # noqa: F821
        back_populates="course", cascade="all, delete-orphan"
    )
    prerequisite_edges: Mapped[list["PrerequisiteEdge"]] = relationship(  # noqa: F821
        back_populates="course", cascade="all, delete-orphan"
    )
    assessment_questions: Mapped[list["AssessmentQuestion"]] = relationship(  # noqa: F821
        back_populates="course", cascade="all, delete-orphan"
    )
    assessment_attempts: Mapped[list["AssessmentAttempt"]] = relationship(  # noqa: F821
        back_populates="course", cascade="all, delete-orphan"
    )
    learner_concept_masteries: Mapped[list["LearnerConceptMastery"]] = relationship(  # noqa: F821
        back_populates="course", cascade="all, delete-orphan"
    )
    reasoning_diagnoses: Mapped[list["ReasoningDiagnosis"]] = relationship(  # noqa: F821
        back_populates="course", cascade="all, delete-orphan",
        foreign_keys="ReasoningDiagnosis.course_id",
    )
    learning_sessions: Mapped[list["LearningSession"]] = relationship(  # noqa: F821
        back_populates="course", cascade="all, delete-orphan", foreign_keys="LearningSession.course_id",
    )
