"""SQLAlchemy models for Phase 5 Learner Concept Mastery and Mastery Observations."""

from datetime import datetime
from typing import Optional
import uuid

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.db.base import Base
from app.services.learner_mastery import BKT_MAX_MASTERY

# ---------------------------------------------------------------------------
# Association Table: assessment_question_concept_link
# ---------------------------------------------------------------------------
# Preserves frozen question -> concept mapping at verification time.
# FK deletion policy:
# - question_id CASCADE: deleting a question (or whole course) drops the link.
# - concept_id RESTRICT: prevents deleting an individual Concept when that deletion
#   would silently shrink/alter a published question's frozen mapping.
# ---------------------------------------------------------------------------
assessment_question_concept_link = Table(
    "assessment_question_concept_link",
    Base.metadata,
    Column(
        "question_id",
        UUID(as_uuid=True),
        ForeignKey("assessment_questions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "concept_id",
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)


class LearnerConceptMastery(Base):
    """Current mastery probability and exposure counters for a learner on a concept."""

    __tablename__ = "learner_concept_mastery"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    mastery_probability: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    observation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    correct_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_attempt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "learner_id", "course_id", "concept_id", name="uq_learner_course_concept"
        ),
        CheckConstraint(
            f"mastery_probability >= 0.0 AND mastery_probability <= {BKT_MAX_MASTERY}",
            name="ck_learner_concept_mastery_probability",
        ),
        CheckConstraint(
            "observation_count >= 0",
            name="ck_learner_concept_mastery_obs_count",
        ),
        CheckConstraint(
            "correct_count >= 0",
            name="ck_learner_concept_mastery_correct_count",
        ),
        CheckConstraint(
            "correct_count <= observation_count",
            name="ck_learner_concept_mastery_correct_le_obs",
        ),
        Index(
            "ix_learner_concept_mastery_learner_course",
            "learner_id",
            "course_id",
        ),
        Index(
            "ix_learner_concept_mastery_course_concept",
            "course_id",
            "concept_id",
        ),
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="learner_concept_masteries")  # noqa: F821
    concept: Mapped["Concept"] = relationship()  # noqa: F821
    observations: Mapped[list["MasteryObservation"]] = relationship(
        back_populates="learner_mastery", cascade="all, delete-orphan"
    )


class MasteryObservation(Base):
    """Immutable audit record of a single deterministic BKT mastery transition."""

    __tablename__ = "mastery_observations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learner_mastery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learner_concept_mastery.id", ondelete="CASCADE"),
        nullable=False,
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_questions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    observation_index: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    prior_mastery: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    posterior_mastery: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    updated_mastery: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    learn_probability: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    guess_probability: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    slip_probability: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    model_version: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_mastery_observations_attempt_id"),
        UniqueConstraint(
            "learner_mastery_id",
            "observation_index",
            name="uq_mastery_obs_learner_mastery_index",
        ),
        CheckConstraint(
            "observation_index >= 1",
            name="ck_mastery_obs_observation_index",
        ),
        CheckConstraint(
            "prior_mastery >= 0.0 AND prior_mastery <= 1.0",
            name="ck_mastery_obs_prior_mastery",
        ),
        CheckConstraint(
            "posterior_mastery >= 0.0 AND posterior_mastery <= 1.0",
            name="ck_mastery_obs_posterior_mastery",
        ),
        CheckConstraint(
            "updated_mastery >= 0.0 AND updated_mastery <= 1.0",
            name="ck_mastery_obs_updated_mastery",
        ),
        CheckConstraint(
            "learn_probability >= 0.0 AND learn_probability <= 1.0",
            name="ck_mastery_obs_learn_probability",
        ),
        CheckConstraint(
            "guess_probability >= 0.0 AND guess_probability <= 1.0",
            name="ck_mastery_obs_guess_probability",
        ),
        CheckConstraint(
            "slip_probability >= 0.0 AND slip_probability <= 1.0",
            name="ck_mastery_obs_slip_probability",
        ),
    )

    # Relationships
    learner_mastery: Mapped["LearnerConceptMastery"] = relationship(
        back_populates="observations"
    )
    # Tell the ORM to delete course-owned observations before their restricted
    # question/attempt parents during a whole-course cascade.
    attempt: Mapped["AssessmentAttempt"] = relationship()  # noqa: F821
    question: Mapped["AssessmentQuestion"] = relationship()  # noqa: F821


@sa.event.listens_for(MasteryObservation, "before_update")
def _reject_observation_update(mapper, connection, target) -> None:
    """Application ORM writes may append observations, never rewrite history."""
    raise ValueError("Mastery observations are immutable.")


@sa.event.listens_for(Session, "before_flush")
def _protect_mastery_history(session, flush_context, instances) -> None:
    # Imports stay local because these models also reference this association.
    from app.models.assessment import AssessmentQuestion
    from app.models.concept import Concept
    from app.models.course import Course

    deleted_courses = {obj.id for obj in session.deleted if isinstance(obj, Course)}
    for obj in session.dirty:
        if isinstance(obj, AssessmentQuestion) and obj not in session.deleted:
            if sa.inspect(obj).attrs.concepts.history.has_changes():
                raise ValueError("Published question concept mappings are frozen.")
    for obj in session.deleted:
        if isinstance(obj, MasteryObservation) and obj.course_id not in deleted_courses:
            raise ValueError("Mastery observations are immutable outside whole-course deletion.")
        if isinstance(obj, Concept) and obj.course_id not in deleted_courses:
            # A loaded many-to-many collection otherwise makes the ORM remove
            # link rows *before* deleting the Concept, bypassing its RESTRICT FK.
            linked = session.connection().scalar(sa.select(
                assessment_question_concept_link.c.question_id
            ).where(assessment_question_concept_link.c.concept_id == obj.id).limit(1))
            if linked is not None:
                raise ValueError("Cannot delete a concept in a frozen question mapping.")
