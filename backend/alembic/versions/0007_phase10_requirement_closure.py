"""Typed grading contracts, auditable responses and resumable cold-start diagnostics."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='0007'
down_revision='0006'
branch_labels=None
depends_on=None


def upgrade():
    # Rebuild the enum in one transaction, avoiding ADD VALUE's commit requirement.
    op.execute('ALTER TABLE assessment_questions ALTER COLUMN question_type DROP DEFAULT')
    op.execute('ALTER TYPE assessment_question_type_enum RENAME TO assessment_question_type_old')
    op.execute("CREATE TYPE assessment_question_type_enum AS ENUM ('multiple_choice','short_answer','numerical')")
    op.execute('ALTER TABLE assessment_questions ALTER COLUMN question_type TYPE assessment_question_type_enum USING question_type::text::assessment_question_type_enum')
    op.execute("ALTER TABLE assessment_questions ALTER COLUMN question_type SET DEFAULT 'multiple_choice'")
    op.execute('DROP TYPE assessment_question_type_old')
    op.add_column('assessment_questions',sa.Column('grading_contract',postgresql.JSONB(),nullable=True))
    op.alter_column('assessment_questions','correct_option_index',nullable=True)
    op.add_column('assessment_attempts',sa.Column('response_data',postgresql.JSONB(),nullable=True))
    op.add_column('assessment_attempts',sa.Column('grading_result',postgresql.JSONB(),nullable=True))
    op.alter_column('assessment_attempts','selected_option_index',nullable=True)
    op.alter_column('assessment_attempts','is_correct',nullable=True)
    op.create_check_constraint('ck_question_type_contract','assessment_questions',"(question_type='multiple_choice' AND correct_option_index IS NOT NULL AND grading_contract IS NULL) OR (question_type!='multiple_choice' AND correct_option_index IS NULL AND grading_contract IS NOT NULL AND options='[]'::jsonb)")
    op.create_check_constraint('ck_attempt_response_contract','assessment_attempts',"(selected_option_index IS NOT NULL AND response_data IS NULL AND is_correct IS NOT NULL) OR (selected_option_index IS NULL AND response_data IS NOT NULL AND grading_result IS NOT NULL)")
    op.create_table('diagnostic_sessions',sa.Column('id',sa.UUID(),primary_key=True),
        sa.Column('course_id',sa.UUID(),sa.ForeignKey('courses.id',ondelete='CASCADE'),nullable=False),
        sa.Column('learner_id',sa.UUID(),nullable=False),sa.Column('question_ids',postgresql.JSONB(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint('course_id','learner_id',name='uq_diagnostic_learner_course'))
    op.execute("""CREATE FUNCTION protect_assessment_attempt() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        IF EXISTS(SELECT 1 FROM courses WHERE id=OLD.course_id) THEN RAISE EXCEPTION 'Assessment attempts are immutable'; END IF;
        RETURN OLD;
      END IF;
      IF (to_jsonb(NEW)-'mastery_update_status') IS DISTINCT FROM (to_jsonb(OLD)-'mastery_update_status')
         OR (OLD.mastery_update_status IS NOT NULL AND NEW.mastery_update_status IS DISTINCT FROM OLD.mastery_update_status)
      THEN RAISE EXCEPTION 'Assessment attempts are immutable'; END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql""")
    op.execute('CREATE TRIGGER assessment_attempt_immutable BEFORE UPDATE ON assessment_attempts FOR EACH ROW EXECUTE FUNCTION protect_assessment_attempt()')

    op.execute('CREATE CONSTRAINT TRIGGER assessment_attempt_delete_immutable AFTER DELETE ON assessment_attempts DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION protect_assessment_attempt()')

def downgrade():
    # Refuse lossy conversion of typed assessments. Export/remove Phase 10-only data explicitly first.
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM assessment_questions WHERE question_type!='multiple_choice')")):
        raise RuntimeError('Downgrade requires exporting/removing Phase 10 typed assessments; no data was discarded')
    op.execute('DROP TRIGGER assessment_attempt_delete_immutable ON assessment_attempts')
    op.execute('DROP TRIGGER assessment_attempt_immutable ON assessment_attempts')
    op.execute('DROP FUNCTION protect_assessment_attempt()')
    op.drop_table('diagnostic_sessions')
    op.drop_constraint('ck_attempt_response_contract','assessment_attempts',type_='check')
    op.drop_constraint('ck_question_type_contract','assessment_questions',type_='check')
    op.drop_column('assessment_attempts','grading_result');op.drop_column('assessment_attempts','response_data')
    op.alter_column('assessment_attempts','is_correct',nullable=False)
    op.alter_column('assessment_attempts','selected_option_index',nullable=False)
    op.drop_column('assessment_questions','grading_contract')
    op.alter_column('assessment_questions','correct_option_index',nullable=False)
    op.execute('ALTER TABLE assessment_questions ALTER COLUMN question_type DROP DEFAULT')
    op.execute('ALTER TYPE assessment_question_type_enum RENAME TO assessment_question_type_new')
    op.execute("CREATE TYPE assessment_question_type_enum AS ENUM ('multiple_choice')")
    op.execute('ALTER TABLE assessment_questions ALTER COLUMN question_type TYPE assessment_question_type_enum USING question_type::text::assessment_question_type_enum')
    op.execute("ALTER TABLE assessment_questions ALTER COLUMN question_type SET DEFAULT 'multiple_choice'")
    op.execute('DROP TYPE assessment_question_type_new')
