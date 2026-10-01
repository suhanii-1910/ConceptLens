"""File-storage service — handles source file uploads.

Behavior on duplicate uploads:
    If a file with the same SHA-256 hash is uploaded to the same course, the
    existing SourceVersion is returned and no new copy is stored.  This keeps
    storage deterministic and avoids wasted space.  The HTTP response uses
    status 200 (not 201) so the caller can distinguish a new upload from a
    dedup hit.
"""

import hashlib
import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.source_version import ProcessingStatus, SourceType, SourceVersion

# Allowed MIME types → SourceType mapping
ALLOWED_MIME_TYPES: dict[str, SourceType] = {
    "application/pdf": SourceType.pdf,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": SourceType.pptx,
    "video/mp4": SourceType.video,
}


class UnsupportedFileTypeError(Exception):
    """Raised when the uploaded file's MIME type is not supported."""

    def __init__(self, mime_type: str) -> None:
        self.mime_type = mime_type
        super().__init__(f"Unsupported file type: {mime_type}")


async def store_source(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    upload: UploadFile,
) -> tuple[SourceVersion, bool]:
    """Store an uploaded source file and create a SourceVersion record.

    Returns (source_version, is_new).  ``is_new`` is False when an identical
    file (same SHA-256) already existed in this course.
    """
    content_type = upload.content_type or ""
    source_type = ALLOWED_MIME_TYPES.get(content_type)
    if source_type is None:
        raise UnsupportedFileTypeError(content_type)

    # Read file bytes and compute SHA-256
    file_bytes = await upload.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Check for duplicate in the same course
    existing = await db.execute(
        select(SourceVersion).where(
            SourceVersion.course_id == course_id,
            SourceVersion.file_hash == file_hash,
        )
    )
    existing_sv = existing.scalar_one_or_none()
    if existing_sv is not None:
        return existing_sv, False

    # Build safe storage path:  <upload_dir>/<course_id>/<uuid>_<sanitised_name>
    original_filename = upload.filename or "unnamed"
    safe_name = _safe_filename(original_filename)
    relative_dir = str(course_id)
    storage_dir = Path(settings.upload_dir) / relative_dir
    storage_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    storage_path = storage_dir / unique_name

    storage_path.write_bytes(file_bytes)

    sv = SourceVersion(
        course_id=course_id,
        original_filename=original_filename,
        file_hash=file_hash,
        mime_type=content_type,
        source_type=source_type,
        storage_path=str(storage_path),
        processing_status=ProcessingStatus.uploaded,
    )
    db.add(sv)
    await db.commit()
    await db.refresh(sv)
    return sv, True


async def list_sources(db: AsyncSession, course_id: uuid.UUID) -> list[SourceVersion]:
    """List all source versions for a course."""
    result = await db.execute(
        select(SourceVersion)
        .where(SourceVersion.course_id == course_id)
        .order_by(SourceVersion.created_at.desc())
    )
    return list(result.scalars().all())


def _safe_filename(filename: str) -> str:
    """Strip path components and dangerous characters from a user-supplied filename."""
    # Take only the basename to prevent path traversal
    name = os.path.basename(filename)
    # Replace anything that isn't alphanumeric, dot, hyphen, or underscore
    safe = "".join(c if (c.isalnum() or c in ".-_") else "_" for c in name)
    return safe or "unnamed"
