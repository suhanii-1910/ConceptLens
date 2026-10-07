"""PDF ingestion service — extracts evidence from uploaded PDF source files.

Architecture:
    1. Validates the SourceVersion is a PDF in ``uploaded`` or ``failed`` status
    2. Transitions status to ``processing``
    3. Opens the PDF with PyMuPDF for text/image extraction
    4. Opens the PDF with pdfplumber for table extraction
    5. Creates EvidenceUnit records with exact page-level provenance
    6. Stores extracted images under ``storage/derived/<source_version_id>/``
    7. Transitions status to ``ready`` (or ``failed`` on error)

Idempotency:
    - If the SourceVersion is already ``ready``, processing is skipped and
      the existing evidence is reported.
    - If the SourceVersion is ``failed``, it may be retried.
    - Re-processing does NOT create duplicate EvidenceUnits because
      ``ready`` sources are short-circuited.

Text extraction:
    - Page-by-page, block-by-block via PyMuPDF ``get_text("dict")``
    - Each text block with ≥ 20 non-whitespace characters becomes an
      EvidenceUnit with ``modality=text``
    - Minimum-content threshold avoids storing tiny fragments like page
      numbers or single words

Table extraction:
    - pdfplumber ``extract_tables()`` per page
    - Each table is serialised as Markdown (pipe-delimited)
    - Each table becomes an EvidenceUnit with ``modality=table``

Image extraction:
    - PyMuPDF ``get_images()`` per page, filtered for meaningful size
    - Image bytes are saved to ``storage/derived/<source_version_id>/``
    - Each image becomes an EvidenceUnit with ``modality=image``
    - Minimum dimension threshold (50×50 px) to skip decorative dots/lines
    - derived_path stored in location_metadata

Scanned PDFs:
    - Produce zero text EvidenceUnits (no OCR / no fabrication)
    - Extractable embedded images are still preserved
    - Processing succeeds with zero text evidence

Provenance (location_metadata):
    {
        "page_index": 0,          # zero-based
        "page_number": 1,         # one-based
        "printed_page_label": str | None,
        "bounding_box": [x0, y0, x1, y1] | None,
        "block_index": int | None,
        "element_type": "text" | "table" | "image"
    }
"""

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
import pymupdf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence_unit import EvidenceUnit, ExtractionStatus, Modality
from app.models.source_version import ProcessingStatus, SourceType, SourceVersion
from app.services.derived_storage import derived_dir_for, safe_derived_filename

logger = logging.getLogger(__name__)

# ---- configuration constants ----

# Text blocks with fewer non-whitespace characters than this are skipped.
MIN_TEXT_CHARS = 20

# Images smaller than this (either dimension in pixels) are skipped
# to avoid decorative dots, lines, and spacer images.
MIN_IMAGE_DIMENSION = 50


# ---- result dataclass ----


@dataclass
class ProcessingResult:
    """Structured result returned after processing."""

    source_version_id: uuid.UUID
    processing_status: str
    page_count: int | None = 0
    slide_count: int | None = None
    duration_seconds: float | None = None
    text_evidence_count: int = 0
    table_evidence_count: int = 0
    image_evidence_count: int = 0
    video_evidence_count: int = 0
    warnings: list[str] = field(default_factory=list)
    already_processed: bool = False


# ---- exceptions ----


class PDFProcessingError(Exception):
    """Raised when PDF processing fails unrecoverably."""


class NotAPDFError(Exception):
    """Raised when processing is requested for a non-PDF source."""


class AlreadyProcessedError(Exception):
    """Raised when a source is already in ``ready`` status."""

    def __init__(self, result: ProcessingResult) -> None:
        self.result = result
        super().__init__("SourceVersion is already processed")


# ---- public API ----


async def process_pdf(
    db: AsyncSession,
    *,
    source_version: SourceVersion,
) -> ProcessingResult:
    """Process a PDF SourceVersion: extract text, tables, and images.

    Raises:
        NotAPDFError: if source_type is not PDF
        AlreadyProcessedError: if already in ``ready`` status (carries result)

    Returns:
        ProcessingResult with counts and final status.
    """
    sv_id = source_version.id

    # ---- guard: non-PDF ----
    if source_version.source_type != SourceType.pdf:
        raise NotAPDFError(
            f"SourceVersion {sv_id} is {source_version.source_type.value}, not PDF"
        )

    # ---- guard: already processed ----
    if source_version.processing_status == ProcessingStatus.ready:
        existing_count = await _count_existing_evidence(db, sv_id)
        result = ProcessingResult(
            source_version_id=sv_id,
            processing_status="ready",
            already_processed=True,
            **existing_count,
        )
        raise AlreadyProcessedError(result)

    # ---- transition: uploaded/failed → processing ----
    source_version.processing_status = ProcessingStatus.processing
    await db.commit()
    await db.refresh(source_version)

    logger.info(
        "PDF processing started: source_version_id=%s, file=%s",
        sv_id,
        source_version.original_filename,
    )

    try:
        result = await _extract_pdf(db, source_version=source_version)
    except Exception as exc:
        # ---- transition: processing → failed ----
        logger.error("PDF processing failed: source_version_id=%s, error=%s", sv_id, exc)
        source_version.processing_status = ProcessingStatus.failed
        await db.commit()
        raise PDFProcessingError(str(exc)) from exc

    # ---- transition: processing → ready ----
    source_version.processing_status = ProcessingStatus.ready
    await db.commit()

    logger.info(
        "PDF processing completed: source_version_id=%s, pages=%d, "
        "text=%d, tables=%d, images=%d",
        sv_id,
        result.page_count,
        result.text_evidence_count,
        result.table_evidence_count,
        result.image_evidence_count,
    )

    return result


# ---- internal extraction logic ----


async def _extract_pdf(
    db: AsyncSession,
    *,
    source_version: SourceVersion,
) -> ProcessingResult:
    """Run all extraction passes on the PDF and persist EvidenceUnits."""
    sv_id = source_version.id
    course_id = source_version.course_id
    pdf_path = Path(source_version.storage_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    result = ProcessingResult(
        source_version_id=sv_id,
        processing_status="ready",
    )

    evidence_units: list[EvidenceUnit] = []

    # ---- PyMuPDF pass: text + images ----
    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception as exc:
        raise PDFProcessingError(f"Cannot open PDF: {exc}") from exc

    try:
        result.page_count = len(doc)

        for page_index in range(len(doc)):
            page = doc[page_index]
            page_number = page_index + 1
            page_label = _get_page_label(doc, page_index)

            # ---- text blocks ----
            text_units = _extract_text_blocks(
                page=page,
                page_index=page_index,
                page_number=page_number,
                page_label=page_label,
                course_id=course_id,
                source_version_id=sv_id,
            )
            evidence_units.extend(text_units)
            result.text_evidence_count += len(text_units)

            # ---- images ----
            image_units = _extract_images(
                doc=doc,
                page=page,
                page_index=page_index,
                page_number=page_number,
                page_label=page_label,
                course_id=course_id,
                source_version_id=sv_id,
            )
            evidence_units.extend(image_units)
            result.image_evidence_count += len(image_units)
    finally:
        doc.close()

    # ---- pdfplumber pass: tables ----
    try:
        with pdfplumber.open(str(pdf_path)) as plumber_pdf:
            for page_index, plumber_page in enumerate(plumber_pdf.pages):
                page_number = page_index + 1
                # Re-derive label from PyMuPDF data already extracted
                page_label = None  # pdfplumber doesn't expose labels reliably
                # Re-open PyMuPDF briefly just for label if needed
                try:
                    tmp_doc = pymupdf.open(str(pdf_path))
                    page_label = _get_page_label(tmp_doc, page_index)
                    tmp_doc.close()
                except Exception:
                    pass

                table_units = _extract_tables(
                    plumber_page=plumber_page,
                    page_index=page_index,
                    page_number=page_number,
                    page_label=page_label,
                    course_id=course_id,
                    source_version_id=sv_id,
                )
                evidence_units.extend(table_units)
                result.table_evidence_count += len(table_units)
    except Exception as exc:
        # Table extraction is best-effort; don't fail the whole PDF
        warning = f"Table extraction failed: {exc}"
        result.warnings.append(warning)
        logger.warning("Table extraction failed for source_version_id=%s: %s", sv_id, exc)

    # ---- persist all evidence units ----
    if evidence_units:
        db.add_all(evidence_units)
        await db.flush()

    return result


def _get_page_label(doc: pymupdf.Document, page_index: int) -> str | None:
    """Get the printed page label from the PDF, if the PDF exposes one.

    Returns None if the label is just the stringified page number (i.e. no
    custom labeling scheme) or if labels are unavailable.
    """
    try:
        labels = doc.get_page_labels()
        if labels and page_index < len(labels):
            label = labels[page_index]
            # Only store if the label differs from the default "page_number"
            if label and label != str(page_index + 1):
                return label
    except Exception:
        pass
    return None


def _extract_text_blocks(
    *,
    page: pymupdf.Page,
    page_index: int,
    page_number: int,
    page_label: str | None,
    course_id: uuid.UUID,
    source_version_id: uuid.UUID,
) -> list[EvidenceUnit]:
    """Extract text blocks from a single PDF page."""
    units: list[EvidenceUnit] = []

    try:
        blocks = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)["blocks"]
    except Exception:
        return units

    for block_index, block in enumerate(blocks):
        # Skip image blocks (type 1); we handle images separately
        if block.get("type") != 0:
            continue

        # Assemble text from spans within lines
        text_parts: list[str] = []
        for line in block.get("lines", []):
            line_text = "".join(span.get("text", "") for span in line.get("spans", []))
            text_parts.append(line_text)

        text = "\n".join(text_parts).strip()

        # Skip blocks that are too short to be useful
        non_ws = sum(1 for c in text if not c.isspace())
        if non_ws < MIN_TEXT_CHARS:
            continue

        bbox = block.get("bbox")
        location_metadata = {
            "page_index": page_index,
            "page_number": page_number,
            "printed_page_label": page_label,
            "bounding_box": list(bbox) if bbox else None,
            "block_index": block_index,
            "element_type": "text",
        }

        eu = EvidenceUnit(
            course_id=course_id,
            source_version_id=source_version_id,
            modality=Modality.text,
            original_text=text,
            extracted_description=None,
            topic=None,
            subtopic=None,
            extraction_status=ExtractionStatus.extracted,
            location_metadata=location_metadata,
        )
        units.append(eu)

    return units


def _extract_tables(
    *,
    plumber_page: pdfplumber.page.Page,
    page_index: int,
    page_number: int,
    page_label: str | None,
    course_id: uuid.UUID,
    source_version_id: uuid.UUID,
) -> list[EvidenceUnit]:
    """Extract tables from a single PDF page using pdfplumber.

    Tables are serialised as Markdown (pipe-delimited) for deterministic
    textual representation.
    """
    units: list[EvidenceUnit] = []

    try:
        tables = plumber_page.find_tables()
    except Exception:
        return units

    for table_index, table_obj in enumerate(tables):
        try:
            rows = table_obj.extract()
        except Exception:
            continue

        if not rows:
            continue

        # Convert to Markdown table
        md_text = _table_to_markdown(rows)
        if not md_text.strip():
            continue

        # pdfplumber exposes table bounding box
        bbox = table_obj.bbox if hasattr(table_obj, "bbox") else None

        location_metadata = {
            "page_index": page_index,
            "page_number": page_number,
            "printed_page_label": page_label,
            "table_rows": [[cell or "" for cell in row] for row in rows],
            "bounding_box": list(bbox) if bbox else None,
            "block_index": table_index,
            "element_type": "table",
        }

        eu = EvidenceUnit(
            course_id=course_id,
            source_version_id=source_version_id,
            modality=Modality.table,
            original_text=md_text,
            extracted_description=None,
            topic=None,
            subtopic=None,
            extraction_status=ExtractionStatus.extracted,
            location_metadata=location_metadata,
        )
        units.append(eu)

    return units


def _table_to_markdown(rows: list[list[str | None]]) -> str:
    """Convert a list of rows (from pdfplumber) into a Markdown table.

    Representation choice: Markdown pipe-delimited tables.
    The first row is treated as the header.
    """
    if not rows:
        return ""

    def _cell(val: str | None) -> str:
        if val is None:
            return ""
        # Replace pipe characters and newlines inside cells
        return str(val).replace("|", "\\|").replace("\n", " ").strip()

    lines: list[str] = []
    # Header
    header = [_cell(c) for c in rows[0]]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    # Body
    for row in rows[1:]:
        cells = [_cell(c) for c in row]
        # Pad if row has fewer columns than header
        while len(cells) < len(header):
            cells.append("")
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def _extract_images(
    *,
    doc: pymupdf.Document,
    page: pymupdf.Page,
    page_index: int,
    page_number: int,
    page_label: str | None,
    course_id: uuid.UUID,
    source_version_id: uuid.UUID,
) -> list[EvidenceUnit]:
    """Extract embedded raster images from a single PDF page."""
    units: list[EvidenceUnit] = []
    derived_dir = derived_dir_for(source_version_id)

    try:
        image_list = page.get_images(full=True)
    except Exception:
        return units

    seen_xrefs: set[int] = set()

    for img_index, img_info in enumerate(image_list):
        xref = img_info[0]

        # Skip duplicates (same image referenced multiple times on one page)
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)

        try:
            base_image = doc.extract_image(xref)
        except Exception:
            continue

        if not base_image or not base_image.get("image"):
            continue

        width = base_image.get("width", 0)
        height = base_image.get("height", 0)

        # Skip tiny images (decorative dots, spacers, etc.)
        if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
            continue

        ext = base_image.get("ext", "png")
        image_bytes = base_image["image"]

        # Save to derived storage
        filename = safe_derived_filename(
            prefix="img", page_index=page_index, img_index=img_index, ext=ext,
        )
        image_path = derived_dir / filename
        image_path.write_bytes(image_bytes)

        # Try to find bounding box from image placement on page
        bbox = _find_image_bbox(page, xref)

        location_metadata = {
            "page_index": page_index,
            "page_number": page_number,
            "printed_page_label": page_label,
            "bounding_box": list(bbox) if bbox else None,
            "block_index": img_index,
            "element_type": "image",
            "derived_path": str(image_path),
            "image_width": width,
            "image_height": height,
        }

        eu = EvidenceUnit(
            course_id=course_id,
            source_version_id=source_version_id,
            modality=Modality.image,
            original_text=None,
            extracted_description=None,
            topic=None,
            subtopic=None,
            extraction_status=ExtractionStatus.extracted,
            location_metadata=location_metadata,
        )
        units.append(eu)

    return units


def _find_image_bbox(
    page: pymupdf.Page, xref: int
) -> tuple[float, float, float, float] | None:
    """Try to find the bounding box of an image on the page by its xref.

    Returns (x0, y0, x1, y1) in the page's coordinate system, or None.
    """
    try:
        for img_block in page.get_text("dict")["blocks"]:
            if img_block.get("type") == 1:  # image block
                # PyMuPDF image blocks carry the bbox directly
                bbox = img_block.get("bbox")
                if bbox:
                    return tuple(bbox)  # type: ignore[return-value]
    except Exception:
        pass
    return None


# ---- helpers ----


async def _count_existing_evidence(
    db: AsyncSession, source_version_id: uuid.UUID
) -> dict[str, int]:
    """Count existing EvidenceUnits by modality for a source version."""
    result = await db.execute(
        select(EvidenceUnit).where(EvidenceUnit.source_version_id == source_version_id)
    )
    units = list(result.scalars().all())

    counts = {
        "text_evidence_count": 0,
        "table_evidence_count": 0,
        "image_evidence_count": 0,
        "video_evidence_count": 0,
    }
    for u in units:
        if u.modality == Modality.text:
            counts["text_evidence_count"] += 1
        elif u.modality == Modality.table:
            counts["table_evidence_count"] += 1
        elif u.modality == Modality.image:
            counts["image_evidence_count"] += 1
        elif u.modality == Modality.video:
            counts["video_evidence_count"] += 1

    return counts
