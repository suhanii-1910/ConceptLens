import logging
import uuid
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence_unit import EvidenceUnit, ExtractionStatus, Modality
from app.models.source_version import ProcessingStatus, SourceType, SourceVersion
from app.services.pdf_ingestion import (
    AlreadyProcessedError,
    ProcessingResult,
    _count_existing_evidence,
)

logger = logging.getLogger(__name__)


class PPTXProcessingError(Exception):
    """Raised when PPTX processing fails unrecoverably."""


class NotAPPTXError(Exception):
    """Raised when processing is requested for a non-PPTX source."""


async def process_pptx(
    db: AsyncSession,
    *,
    source_version: SourceVersion,
) -> ProcessingResult:
    """Process a PPTX SourceVersion: extract text shapes.

    Raises:
        NotAPPTXError: if source_type is not PPTX
        AlreadyProcessedError: if already in ``ready`` status (carries result)

    Returns:
        ProcessingResult with counts and final status.
    """
    sv_id = source_version.id

    # guard: non-PPTX
    if source_version.source_type != SourceType.pptx:
        raise NotAPPTXError(
            f"SourceVersion {sv_id} is {source_version.source_type.value}, not PPTX"
        )

    # guard: already processed
    if source_version.processing_status == ProcessingStatus.ready:
        existing_count = await _count_existing_evidence(db, sv_id)

        slide_count = None
        pptx_path = Path(source_version.storage_path)
        if pptx_path.exists():
            try:
                prs = Presentation(str(pptx_path))
                slide_count = len(prs.slides)
            except Exception:
                pass

        result = ProcessingResult(
            source_version_id=sv_id,
            processing_status="ready",
            already_processed=True,
            page_count=None,
            slide_count=slide_count,
            **existing_count,
        )
        raise AlreadyProcessedError(result)

    # transition: uploaded/failed → processing
    source_version.processing_status = ProcessingStatus.processing
    await db.commit()
    await db.refresh(source_version)

    logger.info(
        "PPTX processing started: source_version_id=%s, file=%s",
        sv_id,
        source_version.original_filename,
    )

    try:
        result = await _extract_pptx(db, source_version=source_version)
    except Exception as exc:
        # transition: processing → failed
        logger.error("PPTX processing failed: source_version_id=%s, error=%s", sv_id, exc)
        source_version.processing_status = ProcessingStatus.failed
        await db.commit()
        raise PPTXProcessingError(str(exc)) from exc

    # transition: processing → ready
    source_version.processing_status = ProcessingStatus.ready
    await db.commit()

    logger.info(
        "PPTX processing completed: source_version_id=%s, slides=%d, "
        "text=%d, tables=%d, images=%d",
        sv_id,
        result.slide_count or 0,
        result.text_evidence_count,
        result.table_evidence_count,
        result.image_evidence_count,
    )

    return result


async def _extract_pptx(
    db: AsyncSession,
    *,
    source_version: SourceVersion,
) -> ProcessingResult:
    """Run extraction passes on the PPTX and persist EvidenceUnits."""
    sv_id = source_version.id
    course_id = source_version.course_id
    pptx_path = Path(source_version.storage_path)

    if not pptx_path.exists():
        raise FileNotFoundError(f"PPTX file not found: {pptx_path}")

    result = ProcessingResult(
        source_version_id=sv_id,
        processing_status="ready",
    )

    evidence_units: list[EvidenceUnit] = []

    try:
        prs = Presentation(str(pptx_path))
    except Exception as exc:
        raise PPTXProcessingError(f"Cannot open PPTX: {exc}") from exc

    slide_width = prs.slide_width
    slide_height = prs.slide_height
    result.slide_count = len(prs.slides)
    result.page_count = None

    for slide_index, slide in enumerate(prs.slides):
        slide_number = slide_index + 1

        for shape_index, shape in enumerate(slide.shapes):
            if not shape.has_text_frame:
                continue

            raw_text = shape.text
            if not raw_text.strip():
                continue

            left = shape.left
            top = shape.top
            width = shape.width
            height = shape.height

            # Avoid missing coordinates crashing extraction
            bbox = None
            if left is not None and top is not None and width is not None and height is not None:
                bbox = [left, top, left + width, top + height]

            location_metadata = {
                "slide_index": slide_index,
                "slide_number": slide_number,
                "shape_id": shape.shape_id if hasattr(shape, "shape_id") else None,
                "shape_name": shape.name if hasattr(shape, "name") else None,
                "shape_index": shape_index,
                "bounding_box": bbox,
                "coordinate_unit": "emu",
                "slide_width": slide_width,
                "slide_height": slide_height,
                "element_type": "text",
            }

            eu = EvidenceUnit(
                course_id=course_id,
                source_version_id=sv_id,
                modality=Modality.text,
                original_text=raw_text,
                extracted_description=None,
                topic=None,
                subtopic=None,
                extraction_status=ExtractionStatus.extracted,
                location_metadata=location_metadata,
            )
            evidence_units.append(eu)
            result.text_evidence_count += 1

    # For phase 1B-A task, table_evidence_count = 0 and image_evidence_count = 0
    result.table_evidence_count = 0
    result.image_evidence_count = 0

    if evidence_units:
        db.add_all(evidence_units)
        await db.flush()

    return result
