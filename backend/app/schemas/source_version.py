"""Pydantic schemas for SourceVersion endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.source_version import ProcessingStatus, SourceType


class SourceVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    original_filename: str
    file_hash: str
    mime_type: str
    source_type: SourceType
    storage_path: str
    processing_status: ProcessingStatus
    created_at: datetime


class ProcessingResultRead(BaseModel):
    """Response schema for PDF processing results."""

    source_version_id: uuid.UUID
    processing_status: str
    page_count: int
    text_evidence_count: int
    table_evidence_count: int
    image_evidence_count: int
    warnings: list[str] = []
    already_processed: bool = False
