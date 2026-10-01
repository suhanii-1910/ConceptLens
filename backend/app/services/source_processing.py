import uuid
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_version import SourceVersion
from app.services.pdf_ingestion import process_pdf


class VideoNotSupportedError(Exception):
    pass


async def process_source(db: AsyncSession, source_version: SourceVersion):
    """Dispatch processing based on source type."""
    from app.models.source_version import SourceType

    if source_version.source_type == SourceType.pdf:
        return await process_pdf(db, source_version=source_version)
    elif source_version.source_type == SourceType.pptx:
        from app.services.pptx_ingestion import process_pptx

        return await process_pptx(db, source_version=source_version)
    elif source_version.source_type == SourceType.video:
        raise VideoNotSupportedError("Video processing is not yet implemented.")
    else:
        raise ValueError(f"Unknown source type: {source_version.source_type}")
