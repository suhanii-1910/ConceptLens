"""Concept model — a named concept within a course."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.evidence_unit import evidence_concept_link
from app.models.learner_mastery import assessment_question_concept_link


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("id", "course_id", name="uq_concept_learning_scope"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="concepts")  # noqa: F821
    evidence_units: Mapped[list["EvidenceUnit"]] = relationship(  # noqa: F821
        secondary=evidence_concept_link, back_populates="concepts"
    )
    assessment_questions: Mapped[list["AssessmentQuestion"]] = relationship(  # noqa: F821
        secondary=assessment_question_concept_link,
        back_populates="concepts",
        passive_deletes=True,
    )
