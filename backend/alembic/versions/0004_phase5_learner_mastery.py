"""Phase 5 Learner Concept Mastery migration."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Freeze migration semantics independently of future BKT model versions.
BKT_MAX_MASTERY = 1.0 - 1e-12

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enums
    mastery_update_status_enum = postgresql.ENUM(
        "updated",
        "skipped_unmapped",
        "skipped_ambiguous",
        "skipped_repeated_question",
        name="mastery_update_status_enum",
        create_type=False,
    )
    mastery_update_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Add nullable mastery_update_status column to assessment_attempts
    op.add_column(
        "assessment_attempts",
        sa.Column(
            "mastery_update_status",
            mastery_update_status_enum,
            nullable=True,
        ),
    )

    # 3. Table: assessment_question_concept_link
    op.create_table(
        "assessment_question_concept_link",
        sa.Column(
            "question_id",
            sa.UUID(),
            sa.ForeignKey("assessment_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "concept_id",
            sa.UUID(),
            sa.ForeignKey("concepts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("question_id", "concept_id"),
    )

    # 4. Table: learner_concept_mastery
    op.create_table(
        "learner_concept_mastery",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "concept_id",
            sa.UUID(),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mastery_probability", sa.Float(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_attempt_id",
            sa.UUID(),
            sa.ForeignKey("assessment_attempts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "learner_id", "course_id", "concept_id", name="uq_learner_course_concept"
        ),
        sa.CheckConstraint(
            f"mastery_probability >= 0.0 AND mastery_probability <= {BKT_MAX_MASTERY}",
            name="ck_learner_concept_mastery_probability",
        ),
        sa.CheckConstraint(
            "observation_count >= 0",
            name="ck_learner_concept_mastery_obs_count",
        ),
        sa.CheckConstraint(
            "correct_count >= 0",
            name="ck_learner_concept_mastery_correct_count",
        ),
        sa.CheckConstraint(
            "correct_count <= observation_count",
            name="ck_learner_concept_mastery_correct_le_obs",
        ),
    )
    op.create_index(
        "ix_learner_concept_mastery_learner_course",
        "learner_concept_mastery",
        ["learner_id", "course_id"],
    )
    op.create_index(
        "ix_learner_concept_mastery_course_concept",
        "learner_concept_mastery",
        ["course_id", "concept_id"],
    )

    # 5. Table: mastery_observations
    op.create_table(
        "mastery_observations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "learner_mastery_id",
            sa.UUID(),
            sa.ForeignKey("learner_concept_mastery.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "concept_id",
            sa.UUID(),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "attempt_id",
            sa.UUID(),
            sa.ForeignKey("assessment_attempts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            sa.UUID(),
            sa.ForeignKey("assessment_questions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("observation_index", sa.Integer(), nullable=False),
        sa.Column("prior_mastery", sa.Float(), nullable=False),
        sa.Column("posterior_mastery", sa.Float(), nullable=False),
        sa.Column("updated_mastery", sa.Float(), nullable=False),
        sa.Column("learn_probability", sa.Float(), nullable=False),
        sa.Column("guess_probability", sa.Float(), nullable=False),
        sa.Column("slip_probability", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "attempt_id", name="uq_mastery_observations_attempt_id"
        ),
        sa.UniqueConstraint(
            "learner_mastery_id",
            "observation_index",
            name="uq_mastery_obs_learner_mastery_index",
        ),
        sa.CheckConstraint(
            "observation_index >= 1",
            name="ck_mastery_obs_observation_index",
        ),
        sa.CheckConstraint(
            "prior_mastery >= 0.0 AND prior_mastery <= 1.0",
            name="ck_mastery_obs_prior_mastery",
        ),
        sa.CheckConstraint(
            "posterior_mastery >= 0.0 AND posterior_mastery <= 1.0",
            name="ck_mastery_obs_posterior_mastery",
        ),
        sa.CheckConstraint(
            "updated_mastery >= 0.0 AND updated_mastery <= 1.0",
            name="ck_mastery_obs_updated_mastery",
        ),
        sa.CheckConstraint(
            "learn_probability >= 0.0 AND learn_probability <= 1.0",
            name="ck_mastery_obs_learn_probability",
        ),
        sa.CheckConstraint(
            "guess_probability >= 0.0 AND guess_probability <= 1.0",
            name="ck_mastery_obs_guess_probability",
        ),
        sa.CheckConstraint(
            "slip_probability >= 0.0 AND slip_probability <= 1.0",
            name="ck_mastery_obs_slip_probability",
        ),
    )


def downgrade() -> None:
    op.drop_table("mastery_observations")

    op.drop_index("ix_learner_concept_mastery_course_concept", table_name="learner_concept_mastery")
    op.drop_index("ix_learner_concept_mastery_learner_course", table_name="learner_concept_mastery")
    op.drop_table("learner_concept_mastery")

    op.drop_table("assessment_question_concept_link")

    op.drop_column("assessment_attempts", "mastery_update_status")

    op.execute("DROP TYPE IF EXISTS mastery_update_status_enum")
