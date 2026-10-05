"""Event-scoped diagnosis evidence. Diagnostic attempts never update mastery."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.db.base import Base


class ReasoningDiagnosis(Base):
    __tablename__ = "reasoning_diagnoses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("courses.id", ondelete="CASCADE"))
    learner_id: Mapped[uuid.UUID]
    attempt_id: Mapped[uuid.UUID]
    question_id: Mapped[uuid.UUID]
    reasoning_text: Mapped[str | None] = mapped_column(sa.Text)
    reasoning_steps: Mapped[list] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(sa.String(32))
    observed_reasoning: Mapped[str | None] = mapped_column(sa.Text)
    first_break_step_index: Mapped[int | None]
    first_break_excerpt: Mapped[str | None] = mapped_column(sa.Text)
    hypothesis_text: Mapped[str | None] = mapped_column(sa.Text)
    target_concept_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("concepts.id", ondelete="RESTRICT"))
    evidence_unit_ids: Mapped[list] = mapped_column(JSONB)
    citation_snapshots: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())

    __table_args__ = (
        sa.ForeignKeyConstraint(["attempt_id", "question_id", "course_id", "learner_id"],
            ["assessment_attempts.id", "assessment_attempts.question_id", "assessment_attempts.course_id", "assessment_attempts.learner_id"],
            name="fk_diagnosis_attempt_scope", ondelete="RESTRICT"),
        sa.UniqueConstraint("id", "course_id", "learner_id", name="uq_diagnosis_scope"),
        sa.CheckConstraint("status IN ('hypothesis','no_clear_break','insufficient_reasoning','insufficient_evidence','confirmed','rejected','inconclusive')", name="ck_diagnosis_status"),
        sa.CheckConstraint("first_break_step_index IS NULL OR first_break_step_index >= 0", name="ck_diagnosis_step"),
        sa.Index("ix_diagnosis_learner_course", "learner_id", "course_id"),
    )
    course: Mapped["Course"] = relationship(back_populates="reasoning_diagnoses", foreign_keys=[course_id])
    attempt: Mapped["AssessmentAttempt"] = relationship(foreign_keys="[ReasoningDiagnosis.attempt_id, ReasoningDiagnosis.question_id, ReasoningDiagnosis.course_id, ReasoningDiagnosis.learner_id]", overlaps="course,reasoning_diagnoses")
    target_concept: Mapped["Concept"] = relationship()
    probe: Mapped["DiagnosticProbe | None"] = relationship(back_populates="diagnosis", cascade="all, delete-orphan", uselist=False)


class DiagnosticProbe(Base):
    __tablename__ = "diagnostic_probes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    diagnosis_id: Mapped[uuid.UUID]
    course_id: Mapped[uuid.UUID]
    learner_id: Mapped[uuid.UUID]
    question_text: Mapped[str] = mapped_column(sa.Text)
    options: Mapped[list] = mapped_column(JSONB)
    correct_option_index: Mapped[int]
    explanation: Mapped[str] = mapped_column(sa.Text)
    evidence_unit_ids: Mapped[list] = mapped_column(JSONB)
    citation_snapshots: Mapped[list] = mapped_column(JSONB)
    verified: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    __table_args__ = (
        sa.ForeignKeyConstraint(["diagnosis_id", "course_id", "learner_id"],
            ["reasoning_diagnoses.id", "reasoning_diagnoses.course_id", "reasoning_diagnoses.learner_id"], name="fk_probe_diagnosis_scope", ondelete="CASCADE"),
        sa.UniqueConstraint("diagnosis_id", name="uq_probe_diagnosis"),
        sa.UniqueConstraint("id", "diagnosis_id", "course_id", "learner_id", name="uq_probe_scope"),
        sa.CheckConstraint("correct_option_index >= 0 AND correct_option_index <= 3", name="ck_probe_option"),
    )
    diagnosis: Mapped[ReasoningDiagnosis] = relationship(back_populates="probe")
    attempts: Mapped[list["DiagnosticProbeAttempt"]] = relationship(back_populates="probe", cascade="all, delete-orphan")


class DiagnosticProbeAttempt(Base):
    __tablename__ = "diagnostic_probe_attempts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    probe_id: Mapped[uuid.UUID]
    diagnosis_id: Mapped[uuid.UUID]
    course_id: Mapped[uuid.UUID]
    learner_id: Mapped[uuid.UUID]
    selected_option_index: Mapped[int]
    is_correct: Mapped[bool | None]
    applied_outcome: Mapped[str | None] = mapped_column(sa.String(16))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    __table_args__ = (
        sa.ForeignKeyConstraint(["probe_id", "diagnosis_id", "course_id", "learner_id"],
            ["diagnostic_probes.id", "diagnostic_probes.diagnosis_id", "diagnostic_probes.course_id", "diagnostic_probes.learner_id"], name="fk_probe_attempt_scope", ondelete="CASCADE"),
        sa.CheckConstraint("selected_option_index >= 0 AND selected_option_index <= 3", name="ck_probe_attempt_option"),
        sa.CheckConstraint("applied_outcome IS NULL OR applied_outcome IN ('confirmed','rejected','inconclusive')", name="ck_probe_attempt_outcome"),
        sa.Index("uq_probe_first_resolution", "diagnosis_id", unique=True,
            postgresql_where=sa.text("applied_outcome IS NOT NULL"), sqlite_where=sa.text("applied_outcome IS NOT NULL")),
    )
    probe: Mapped[DiagnosticProbe] = relationship(back_populates="attempts")


@sa.event.listens_for(Session, "before_flush")
def protect_diagnostic_history(session, flush_context, instances):
    from app.models.course import Course

    deleted_courses = {obj.id for obj in session.deleted if isinstance(obj, Course)}
    for obj in session.dirty:
        state = sa.inspect(obj)
        changed = {column.key for column in state.mapper.column_attrs if state.attrs[column.key].history.has_changes()}
        if isinstance(obj, (DiagnosticProbe, DiagnosticProbeAttempt)):
            if changed:
                raise ValueError("Diagnostic evidence is immutable.")
        if isinstance(obj, ReasoningDiagnosis):
            if changed - {"status", "updated_at"}:
                raise ValueError("Diagnosis input and interpretation are immutable.")
            if "status" in changed:
                history = state.attrs.status.history
                if list(history.deleted) != ["hypothesis"] or obj.status not in {"confirmed", "rejected", "inconclusive"}:
                    raise ValueError("A diagnosis can resolve only once.")
    for obj in session.deleted:
        if isinstance(obj, (ReasoningDiagnosis, DiagnosticProbe, DiagnosticProbeAttempt)) and obj.course_id not in deleted_courses:
            raise ValueError("Diagnostic evidence is immutable outside whole-course deletion.")
