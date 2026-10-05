"""Phase 6 event-scoped reasoning diagnosis and diagnostic probes."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A redundant unique key enables a composite FK without altering old rows.
    op.create_unique_constraint("uq_assessment_attempt_diagnosis_scope", "assessment_attempts",
                                ["id", "question_id", "course_id", "learner_id"])
    op.create_table(
        "reasoning_diagnoses",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("course_id", sa.UUID(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("reasoning_text", sa.Text()),
        sa.Column("reasoning_steps", JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("observed_reasoning", sa.Text()),
        sa.Column("first_break_step_index", sa.Integer()),
        sa.Column("first_break_excerpt", sa.Text()),
        sa.Column("hypothesis_text", sa.Text()),
        sa.Column("target_concept_id", sa.UUID(), sa.ForeignKey("concepts.id", ondelete="RESTRICT")),
        sa.Column("evidence_unit_ids", JSONB(), nullable=False),
        sa.Column("citation_snapshots", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["attempt_id", "question_id", "course_id", "learner_id"],
            ["assessment_attempts.id", "assessment_attempts.question_id", "assessment_attempts.course_id", "assessment_attempts.learner_id"],
            name="fk_diagnosis_attempt_scope", ondelete="RESTRICT"),
        sa.UniqueConstraint("id", "course_id", "learner_id", name="uq_diagnosis_scope"),
        sa.CheckConstraint("status IN ('hypothesis','no_clear_break','insufficient_reasoning','insufficient_evidence','confirmed','rejected','inconclusive')", name="ck_diagnosis_status"),
        sa.CheckConstraint("first_break_step_index IS NULL OR first_break_step_index >= 0", name="ck_diagnosis_step"),
    )
    op.create_index("ix_diagnosis_learner_course", "reasoning_diagnoses", ["learner_id", "course_id"])
    op.create_table(
        "diagnostic_probes",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("diagnosis_id", sa.UUID(), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", JSONB(), nullable=False),
        sa.Column("correct_option_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence_unit_ids", JSONB(), nullable=False),
        sa.Column("citation_snapshots", JSONB(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["diagnosis_id", "course_id", "learner_id"],
            ["reasoning_diagnoses.id", "reasoning_diagnoses.course_id", "reasoning_diagnoses.learner_id"], name="fk_probe_diagnosis_scope", ondelete="CASCADE"),
        sa.UniqueConstraint("diagnosis_id", name="uq_probe_diagnosis"),
        sa.UniqueConstraint("id", "diagnosis_id", "course_id", "learner_id", name="uq_probe_scope"),
        sa.CheckConstraint("correct_option_index >= 0 AND correct_option_index <= 3", name="ck_probe_option"),
    )
    op.create_table(
        "diagnostic_probe_attempts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("probe_id", sa.UUID(), nullable=False),
        sa.Column("diagnosis_id", sa.UUID(), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("selected_option_index", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean()),
        sa.Column("applied_outcome", sa.String(16)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["probe_id", "diagnosis_id", "course_id", "learner_id"],
            ["diagnostic_probes.id", "diagnostic_probes.diagnosis_id", "diagnostic_probes.course_id", "diagnostic_probes.learner_id"], name="fk_probe_attempt_scope", ondelete="CASCADE"),
        sa.CheckConstraint("selected_option_index >= 0 AND selected_option_index <= 3", name="ck_probe_attempt_option"),
        sa.CheckConstraint("applied_outcome IS NULL OR applied_outcome IN ('confirmed','rejected','inconclusive')", name="ck_probe_attempt_outcome"),
    )
    op.create_index("uq_probe_first_resolution", "diagnostic_probe_attempts", ["diagnosis_id"],
                    unique=True, postgresql_where=sa.text("applied_outcome IS NOT NULL"))


def downgrade() -> None:
    op.drop_table("diagnostic_probe_attempts")
    op.drop_table("diagnostic_probes")
    op.drop_table("reasoning_diagnoses")
    op.drop_constraint("uq_assessment_attempt_diagnosis_scope", "assessment_attempts", type_="unique")
