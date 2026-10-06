"""Phase 7 adaptive learning; no historical backfill."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint('uq_concept_learning_scope', 'concepts', ['id', 'course_id'])
    op.create_unique_constraint('uq_question_learning_scope', 'assessment_questions', ['id', 'course_id'])
    op.create_unique_constraint('uq_edge_learning_scope', 'prerequisite_edges', ['id', 'course_id', 'prerequisite_concept_id', 'target_concept_id'])

    op.create_table('learning_sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('course_id', sa.UUID(), nullable=False),
    sa.Column('learner_id', sa.Uuid(), nullable=False),
    sa.Column('diagnosis_id', sa.Uuid(), nullable=False),
    sa.Column('target_concept_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('current_action', sa.String(length=32), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('active','complete','diagnosis_not_confirmed','needs_reassessment')", name='ck_learning_session_status'),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['diagnosis_id', 'course_id', 'learner_id'], ['reasoning_diagnoses.id', 'reasoning_diagnoses.course_id', 'reasoning_diagnoses.learner_id'], name='fk_learning_diagnosis_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['target_concept_id', 'course_id'], ['concepts.id', 'concepts.course_id'], name='fk_learning_target_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['target_concept_id'], ['concepts.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('diagnosis_id', name='uq_learning_diagnosis'),
    sa.UniqueConstraint('id', 'course_id', 'learner_id', 'target_concept_id', name='uq_learning_session_scope')
    )

    op.create_table('learning_interventions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('course_id', sa.Uuid(), nullable=False),
    sa.Column('learner_id', sa.Uuid(), nullable=False),
    sa.Column('sequence_index', sa.Integer(), nullable=False),
    sa.Column('strategy', sa.String(length=32), nullable=False),
    sa.Column('target_concept_id', sa.UUID(), nullable=False),
    sa.Column('prerequisite_concept_id', sa.UUID(), nullable=True),
    sa.Column('prerequisite_edge_id', sa.UUID(), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('assessment_question_id', sa.UUID(), nullable=True),
    sa.Column('evidence_unit_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('citation_snapshots', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('verified', sa.Boolean(), nullable=False),
    sa.Column('feedback', sa.String(length=32), nullable=True),
    sa.Column('learner_choice', sa.String(length=32), nullable=True),
    sa.Column('completed', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('response_attempt_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("feedback IS NULL OR feedback IN ('understood','still_confused')", name='ck_intervention_feedback'),
    sa.CheckConstraint("learner_choice IS NULL OR learner_choice IN ('sixty_second_recap','practice_prerequisite','continue_anyway')", name='ck_intervention_choice'),
    sa.CheckConstraint("strategy IN ('source_explanation','visual_explanation','prerequisite_probe','prerequisite_recap','prerequisite_practice','worked_example','transfer_check')", name='ck_intervention_strategy'),
    sa.CheckConstraint('(prerequisite_concept_id IS NULL) = (prerequisite_edge_id IS NULL)', name='ck_intervention_prerequisite'),
    sa.CheckConstraint('sequence_index >= 1', name='ck_intervention_sequence'),
    sa.ForeignKeyConstraint(['assessment_question_id', 'course_id'], ['assessment_questions.id', 'assessment_questions.course_id'], name='fk_intervention_question_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['assessment_question_id'], ['assessment_questions.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['prerequisite_concept_id', 'course_id'], ['concepts.id', 'concepts.course_id'], name='fk_intervention_prerequisite_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['prerequisite_concept_id'], ['concepts.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['prerequisite_edge_id', 'course_id', 'prerequisite_concept_id', 'target_concept_id'], ['prerequisite_edges.id', 'prerequisite_edges.course_id', 'prerequisite_edges.prerequisite_concept_id', 'prerequisite_edges.target_concept_id'], name='fk_intervention_edge_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['prerequisite_edge_id'], ['prerequisite_edges.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['response_attempt_id', 'assessment_question_id', 'course_id', 'learner_id'], ['assessment_attempts.id', 'assessment_attempts.question_id', 'assessment_attempts.course_id', 'assessment_attempts.learner_id'], name='fk_intervention_response_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['response_attempt_id'], ['assessment_attempts.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['session_id', 'course_id', 'learner_id', 'target_concept_id'], ['learning_sessions.id', 'learning_sessions.course_id', 'learning_sessions.learner_id', 'learning_sessions.target_concept_id'], name='fk_intervention_session_scope', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_concept_id'], ['concepts.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('assessment_question_id', name='uq_intervention_question'),
    sa.UniqueConstraint('session_id', 'sequence_index', name='uq_intervention_sequence'),
    sa.UniqueConstraint('session_id', 'strategy', name='uq_intervention_strategy')
    )

    op.create_table('transfer_checks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('course_id', sa.Uuid(), nullable=False),
    sa.Column('learner_id', sa.Uuid(), nullable=False),
    sa.Column('assessment_question_id', sa.UUID(), nullable=False),
    sa.Column('target_concept_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('resolved_attempt_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(status = 'pending' AND resolved_attempt_id IS NULL) OR (status != 'pending' AND resolved_attempt_id IS NOT NULL)", name='ck_transfer_resolution'),
    sa.CheckConstraint("status IN ('pending','passed','failed')", name='ck_transfer_status'),
    sa.ForeignKeyConstraint(['assessment_question_id', 'course_id'], ['assessment_questions.id', 'assessment_questions.course_id'], name='fk_transfer_question_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['assessment_question_id'], ['assessment_questions.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['resolved_attempt_id', 'assessment_question_id', 'course_id', 'learner_id'], ['assessment_attempts.id', 'assessment_attempts.question_id', 'assessment_attempts.course_id', 'assessment_attempts.learner_id'], name='fk_transfer_attempt_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['resolved_attempt_id'], ['assessment_attempts.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['session_id', 'course_id', 'learner_id', 'target_concept_id'], ['learning_sessions.id', 'learning_sessions.course_id', 'learning_sessions.learner_id', 'learning_sessions.target_concept_id'], name='fk_transfer_session_scope', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_concept_id'], ['concepts.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('assessment_question_id', name='uq_transfer_question'),
    sa.UniqueConstraint('session_id', name='uq_transfer_session')
    )

    op.execute("""CREATE FUNCTION protect_transfer_resolution() RETURNS trigger AS $$
    BEGIN
        IF OLD.status <> 'pending' AND
           (NEW.status IS DISTINCT FROM OLD.status OR
            NEW.resolved_attempt_id IS DISTINCT FROM OLD.resolved_attempt_id) THEN
            RAISE EXCEPTION 'Transfer Check resolution is immutable';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql""")
    op.execute("""CREATE TRIGGER transfer_resolution_immutable BEFORE UPDATE ON transfer_checks
        FOR EACH ROW EXECUTE FUNCTION protect_transfer_resolution()""")


def downgrade() -> None:
    op.drop_table('transfer_checks')
    op.execute('DROP FUNCTION protect_transfer_resolution()')
    op.drop_table('learning_interventions')
    op.drop_table('learning_sessions')
    op.drop_constraint('uq_edge_learning_scope', 'prerequisite_edges', type_='unique')
    op.drop_constraint('uq_question_learning_scope', 'assessment_questions', type_='unique')
    op.drop_constraint('uq_concept_learning_scope', 'concepts', type_='unique')
