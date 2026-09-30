"""phase0a_initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-09-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Enum types
    source_type_enum = postgresql.ENUM(
        "pdf", "pptx", "video", name="source_type_enum", create_type=False
    )
    processing_status_enum = postgresql.ENUM(
        "uploaded", "processing", "ready", "failed",
        name="processing_status_enum", create_type=False,
    )
    modality_enum = postgresql.ENUM(
        "text", "image", "slide", "video", "table",
        name="modality_enum", create_type=False,
    )
    extraction_status_enum = postgresql.ENUM(
        "pending", "extracted", "failed",
        name="extraction_status_enum", create_type=False,
    )

    source_type_enum.create(op.get_bind(), checkfirst=True)
    processing_status_enum.create(op.get_bind(), checkfirst=True)
    modality_enum.create(op.get_bind(), checkfirst=True)
    extraction_status_enum.create(op.get_bind(), checkfirst=True)

    # --- courses ---
    op.create_table(
        "courses",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
    )

    # --- source_versions ---
    op.create_table(
        "source_versions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False, index=True),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("source_type", source_type_enum, nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column(
            "processing_status",
            processing_status_enum,
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- concepts ---
    op.create_table(
        "concepts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- evidence_units ---
    op.create_table(
        "evidence_units",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.UUID(),
            sa.ForeignKey("source_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("modality", modality_enum, nullable=False),
        sa.Column("original_text", sa.Text(), nullable=True),
        sa.Column("extracted_description", sa.Text(), nullable=True),
        sa.Column("topic", sa.String(255), nullable=True),
        sa.Column("subtopic", sa.String(255), nullable=True),
        sa.Column("extraction_status", extraction_status_enum, nullable=False, server_default="pending"),
        sa.Column("location_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- evidence_concept_link (many-to-many) ---
    op.create_table(
        "evidence_concept_link",
        sa.Column(
            "evidence_unit_id",
            sa.UUID(),
            sa.ForeignKey("evidence_units.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "concept_id",
            sa.UUID(),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # --- prerequisite_edges ---
    op.create_table(
        "prerequisite_edges",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "prerequisite_concept_id",
            sa.UUID(),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_concept_id",
            sa.UUID(),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_backed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "prerequisite_concept_id != target_concept_id",
            name="ck_no_self_prerequisite",
        ),
    )


def downgrade() -> None:
    op.drop_table("prerequisite_edges")
    op.drop_table("evidence_concept_link")
    op.drop_table("evidence_units")
    op.drop_table("concepts")
    op.drop_table("source_versions")
    op.drop_table("courses")

    op.execute("DROP TYPE IF EXISTS extraction_status_enum")
    op.execute("DROP TYPE IF EXISTS modality_enum")
    op.execute("DROP TYPE IF EXISTS processing_status_enum")
    op.execute("DROP TYPE IF EXISTS source_type_enum")
    op.execute("DROP EXTENSION IF EXISTS vector")
