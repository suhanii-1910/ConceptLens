"""Phase 4 Grounded Assessment Generation and Verification migration."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enums
    question_type_enum = postgresql.ENUM(
        "multiple_choice",
        name="assessment_question_type_enum",
        create_type=False,
    )
    difficulty_enum = postgresql.ENUM(
        "easy", "medium", "hard",
        name="assessment_difficulty_enum",
        create_type=False,
    )
    verification_status_enum = postgresql.ENUM(
        "verified", "rejected", "unverified",
        name="assessment_question_verification_status_enum",
        create_type=False,
    )

    question_type_enum.create(op.get_bind(), checkfirst=True)
    difficulty_enum.create(op.get_bind(), checkfirst=True)
    verification_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Table: assessment_questions
    op.create_table(
        "assessment_questions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_type",
            question_type_enum,
            nullable=False,
            server_default="multiple_choice",
        ),
        sa.Column("difficulty", difficulty_enum, nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("correct_option_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence_unit_ids", postgresql.JSONB(), nullable=False),
        sa.Column("citation_snapshots", postgresql.JSONB(), nullable=False),
        sa.Column(
            "verification_status",
            verification_status_enum,
            nullable=False,
            server_default="verified",
        ),
        sa.Column("generation_focus", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "correct_option_index >= 0 AND correct_option_index <= 3",
            name="ck_assessment_questions_correct_option_index",
        ),
    )
    op.create_index(
        "ix_assessment_questions_course_id_created_at",
        "assessment_questions",
        ["course_id", "created_at"],
    )

    # 3. Table: assessment_attempts
    op.create_table(
        "assessment_attempts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "question_id",
            sa.UUID(),
            sa.ForeignKey("assessment_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("selected_option_index", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "selected_option_index >= 0 AND selected_option_index <= 3",
            name="ck_assessment_attempts_selected_option_index",
        ),
    )
    op.create_index(
        "ix_assessment_attempts_question_id_created_at",
        "assessment_attempts",
        ["question_id", "created_at"],
    )
    op.create_index(
        "ix_assessment_attempts_learner_id_created_at",
        "assessment_attempts",
        ["learner_id", "created_at"],
    )
    op.create_index(
        "ix_assessment_attempts_course_id_created_at",
        "assessment_attempts",
        ["course_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_assessment_attempts_course_id_created_at", table_name="assessment_attempts")
    op.drop_index("ix_assessment_attempts_learner_id_created_at", table_name="assessment_attempts")
    op.drop_index("ix_assessment_attempts_question_id_created_at", table_name="assessment_attempts")
    op.drop_table("assessment_attempts")

    op.drop_index("ix_assessment_questions_course_id_created_at", table_name="assessment_questions")
    op.drop_table("assessment_questions")

    op.execute("DROP TYPE IF EXISTS assessment_question_verification_status_enum")
    op.execute("DROP TYPE IF EXISTS assessment_difficulty_enum")
    op.execute("DROP TYPE IF EXISTS assessment_question_type_enum")
