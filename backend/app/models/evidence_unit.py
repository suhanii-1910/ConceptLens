"""EvidenceUnit model — one atomic piece of evidence extracted from a source."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Modality(str, enum.Enum):
    text = "text"
    image = "image"
    slide = "slide"
    video = "video"
    table = "table"


class ExtractionStatus(str, enum.Enum):
    pending = "pending"
    extracted = "extracted"
    failed = "failed"


# Association table for EvidenceUnit <-> Concept many-to-many
from sqlalchemy import Column, Table

evidence_concept_link = Table(
    "evidence_concept_link",
    Base.metadata,
    Column(
        "evidence_unit_id",
        UUID(as_uuid=True),
        ForeignKey("evidence_units.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "concept_id",
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class EvidenceUnit(Base):
    __tablename__ = "evidence_units"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    source_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    modality: Mapped[Modality] = mapped_column(
        Enum(Modality, name="modality_enum"), nullable=False
    )
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subtopic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus, name="extraction_status_enum"),
        default=ExtractionStatus.pending,
        nullable=False,
    )
    location_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="evidence_units")  # noqa: F821
    source_version: Mapped["SourceVersion"] = relationship(  # noqa: F821
        back_populates="evidence_units"
    )
    concepts: Mapped[list["Concept"]] = relationship(  # noqa: F821
        secondary=evidence_concept_link, back_populates="evidence_units"
    )
