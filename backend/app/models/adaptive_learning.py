"""Auditable adaptive sessions with one use of each strategy and one Transfer Check."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.db.base import Base


class LearningSession(Base):
    __tablename__ = 'learning_sessions'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey('courses.id', ondelete='CASCADE'))
    learner_id: Mapped[uuid.UUID]
    diagnosis_id: Mapped[uuid.UUID]
    target_concept_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey('concepts.id', ondelete='RESTRICT'))
    status: Mapped[str] = mapped_column(sa.String(32))
    current_action: Mapped[str] = mapped_column(sa.String(32))
    reason: Mapped[str] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    __table_args__ = (
        sa.ForeignKeyConstraint(['diagnosis_id','course_id','learner_id'], ['reasoning_diagnoses.id','reasoning_diagnoses.course_id','reasoning_diagnoses.learner_id'], name='fk_learning_diagnosis_scope', ondelete='RESTRICT'),
        sa.UniqueConstraint('diagnosis_id', name='uq_learning_diagnosis'),
        sa.UniqueConstraint('id','course_id','learner_id','target_concept_id', name='uq_learning_session_scope'),
        sa.ForeignKeyConstraint(['target_concept_id','course_id'], ['concepts.id','concepts.course_id'], name='fk_learning_target_scope', ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('active','complete','diagnosis_not_confirmed','needs_reassessment')", name='ck_learning_session_status'),
    )
    course: Mapped['Course'] = relationship(back_populates='learning_sessions', foreign_keys=[course_id])
    diagnosis: Mapped['ReasoningDiagnosis'] = relationship(overlaps='course,learning_sessions')
    target_concept: Mapped['Concept'] = relationship(foreign_keys=[target_concept_id])
    interventions: Mapped[list['LearningIntervention']] = relationship(back_populates='session', cascade='all, delete-orphan')
    transfer_check: Mapped['TransferCheck | None'] = relationship(back_populates='session', cascade='all, delete-orphan', uselist=False)


class LearningIntervention(Base):
    __tablename__ = 'learning_interventions'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID]
    course_id: Mapped[uuid.UUID]
    learner_id: Mapped[uuid.UUID]
    sequence_index: Mapped[int]
    strategy: Mapped[str] = mapped_column(sa.String(32))
    target_concept_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey('concepts.id', ondelete='RESTRICT'))
    prerequisite_concept_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey('concepts.id', ondelete='RESTRICT'))
    prerequisite_edge_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey('prerequisite_edges.id', ondelete='RESTRICT'))
    payload: Mapped[dict | None] = mapped_column(JSONB)
    assessment_question_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey('assessment_questions.id', ondelete='RESTRICT'))
    evidence_unit_ids: Mapped[list] = mapped_column(JSONB)
    citation_snapshots: Mapped[list] = mapped_column(JSONB)
    verified: Mapped[bool]
    feedback: Mapped[str | None] = mapped_column(sa.String(32))
    learner_choice: Mapped[str | None] = mapped_column(sa.String(32))
    completed: Mapped[bool] = mapped_column(default=False, server_default=sa.false())
    response_attempt_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey('assessment_attempts.id', ondelete='RESTRICT'))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    __table_args__ = (
        sa.ForeignKeyConstraint(['session_id','course_id','learner_id','target_concept_id'], ['learning_sessions.id','learning_sessions.course_id','learning_sessions.learner_id','learning_sessions.target_concept_id'], name='fk_intervention_session_scope', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assessment_question_id','course_id'], ['assessment_questions.id','assessment_questions.course_id'], name='fk_intervention_question_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['prerequisite_concept_id','course_id'], ['concepts.id','concepts.course_id'], name='fk_intervention_prerequisite_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['prerequisite_edge_id','course_id','prerequisite_concept_id','target_concept_id'], ['prerequisite_edges.id','prerequisite_edges.course_id','prerequisite_edges.prerequisite_concept_id','prerequisite_edges.target_concept_id'], name='fk_intervention_edge_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['response_attempt_id','assessment_question_id','course_id','learner_id'], ['assessment_attempts.id','assessment_attempts.question_id','assessment_attempts.course_id','assessment_attempts.learner_id'], name='fk_intervention_response_scope', ondelete='RESTRICT'),
        sa.CheckConstraint('(prerequisite_concept_id IS NULL) = (prerequisite_edge_id IS NULL)', name='ck_intervention_prerequisite'),
        sa.UniqueConstraint('session_id','sequence_index', name='uq_intervention_sequence'),
        sa.UniqueConstraint('session_id','strategy', name='uq_intervention_strategy'),
        sa.UniqueConstraint('assessment_question_id', name='uq_intervention_question'),
        sa.CheckConstraint('sequence_index >= 1', name='ck_intervention_sequence'),
        sa.CheckConstraint("strategy IN ('source_explanation','visual_explanation','prerequisite_probe','prerequisite_recap','prerequisite_practice','worked_example','transfer_check')", name='ck_intervention_strategy'),
        sa.CheckConstraint("feedback IS NULL OR feedback IN ('understood','still_confused')", name='ck_intervention_feedback'),
        sa.CheckConstraint("learner_choice IS NULL OR learner_choice IN ('sixty_second_recap','practice_prerequisite','continue_anyway')", name='ck_intervention_choice'),
    )
    session: Mapped[LearningSession] = relationship(back_populates='interventions')
    target_concept: Mapped['Concept'] = relationship(foreign_keys=[target_concept_id], overlaps='interventions,session')
    prerequisite_concept: Mapped['Concept | None'] = relationship(foreign_keys=[prerequisite_concept_id])
    prerequisite_edge: Mapped['PrerequisiteEdge | None'] = relationship(foreign_keys=[prerequisite_edge_id])
    question: Mapped['AssessmentQuestion | None'] = relationship(foreign_keys=[assessment_question_id])
    response_attempt: Mapped['AssessmentAttempt | None'] = relationship(foreign_keys=[response_attempt_id])


class TransferCheck(Base):
    __tablename__ = 'transfer_checks'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID]
    course_id: Mapped[uuid.UUID]
    learner_id: Mapped[uuid.UUID]
    assessment_question_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey('assessment_questions.id', ondelete='RESTRICT'))
    target_concept_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey('concepts.id', ondelete='RESTRICT'))
    status: Mapped[str] = mapped_column(sa.String(16), default='pending')
    resolved_attempt_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey('assessment_attempts.id', ondelete='RESTRICT'))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    __table_args__ = (
        sa.ForeignKeyConstraint(['session_id','course_id','learner_id','target_concept_id'], ['learning_sessions.id','learning_sessions.course_id','learning_sessions.learner_id','learning_sessions.target_concept_id'], name='fk_transfer_session_scope', ondelete='CASCADE'),
        sa.UniqueConstraint('session_id', name='uq_transfer_session'),
        sa.ForeignKeyConstraint(['assessment_question_id','course_id'], ['assessment_questions.id','assessment_questions.course_id'], name='fk_transfer_question_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['resolved_attempt_id','assessment_question_id','course_id','learner_id'], ['assessment_attempts.id','assessment_attempts.question_id','assessment_attempts.course_id','assessment_attempts.learner_id'], name='fk_transfer_attempt_scope', ondelete='RESTRICT'),
        sa.UniqueConstraint('assessment_question_id', name='uq_transfer_question'),
        sa.CheckConstraint("status IN ('pending','passed','failed')", name='ck_transfer_status'),
        sa.CheckConstraint("(status = 'pending' AND resolved_attempt_id IS NULL) OR (status != 'pending' AND resolved_attempt_id IS NOT NULL)", name='ck_transfer_resolution'),
    )
    session: Mapped[LearningSession] = relationship(back_populates='transfer_check')
    question: Mapped['AssessmentQuestion'] = relationship(foreign_keys=[assessment_question_id])
    target_concept: Mapped['Concept'] = relationship(foreign_keys=[target_concept_id], overlaps='session,transfer_check')
    resolved_attempt: Mapped['AssessmentAttempt | None'] = relationship(foreign_keys=[resolved_attempt_id])


@sa.event.listens_for(Session, 'before_flush')
def protect_learning_history(session, flush_context, instances):
    from app.models.course import Course
    from app.models.assessment import AssessmentQuestion

    deleted_courses = {obj.id for obj in session.deleted if isinstance(obj, Course)}
    for obj in session.dirty:
        state = sa.inspect(obj)
        changed = {c.key for c in state.mapper.column_attrs if state.attrs[c.key].history.has_changes()}
        if isinstance(obj, LearningIntervention):
            if changed - {'feedback','learner_choice','completed','response_attempt_id'}:
                raise ValueError('Learning content is immutable.')
            for field in changed:
                old = state.attrs[field].history.deleted
                if old and old[0] not in (None, False):
                    raise ValueError('Learner responses resolve only once.')
        if isinstance(obj, TransferCheck):
            if changed - {'status','resolved_attempt_id'}:
                raise ValueError('Transfer Check content is immutable.')
            previous = state.attrs.status.history.deleted
            if changed and (previous[0] if previous else obj.status) != 'pending':
                raise ValueError('Transfer Check resolves only once.')
        if isinstance(obj, LearningSession) and changed - {'status','current_action','reason','updated_at'}:
            raise ValueError('Learning session identity is immutable.')
        if isinstance(obj, AssessmentQuestion) and changed:
            linked = session.connection().scalar(sa.select(LearningIntervention.id).where(LearningIntervention.assessment_question_id == obj.id).limit(1))
            if linked is not None:
                raise ValueError('Learning assessment questions are immutable.')
    for obj in session.deleted:
        if isinstance(obj, (LearningSession,LearningIntervention,TransferCheck)) and obj.course_id not in deleted_courses:
            raise ValueError('Learning history is immutable outside whole-course deletion.')
