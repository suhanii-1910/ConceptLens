"""Phase 1A final acceptance audit tests.

These tests verify acceptance criteria not clearly evidenced in the
original completion report:

1. Unicode text preservation
2. Image-only / scanned-style PDF behavior
3. Original source file immutability (SHA-256 before/after)
4. Derived image path separation from uploads
5. Text bounding-box evidence in location_metadata
6. Page numbering consistency (page_index / page_number)
7. Existing regression suite is not weakened (run via test_pdf_ingestion.py)

All PDFs are generated programmatically — no binary fixtures needed.
"""

import hashlib
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.evidence_unit import EvidenceUnit, ExtractionStatus, Modality
from app.models.source_version import ProcessingStatus, SourceType, SourceVersion
from app.services.pdf_ingestion import process_pdf
from tests.fixtures.pdf_factory import (
    make_image_only_pdf,
    make_image_pdf,
    make_multipage_pdf,
    make_text_pdf,
    make_unicode_pdf,
)


# ---- helpers ----


async def _create_course(db: AsyncSession, name: str = "Audit Course") -> Course:
    course = Course(name=name)
    db.add(course)
    await db.flush()
    await db.refresh(course)
    return course


async def _create_source_version(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    pdf_bytes: bytes,
    tmp_path: Path,
    filename: str = "audit.pdf",
    source_type: SourceType = SourceType.pdf,
) -> SourceVersion:
    pdf_path = tmp_path / filename
    pdf_path.write_bytes(pdf_bytes)

    sv = SourceVersion(
        course_id=course_id,
        original_filename=filename,
        file_hash="sha256_audit_" + uuid.uuid4().hex[:16],
        mime_type="application/pdf",
        source_type=source_type,
        storage_path=str(pdf_path),
        processing_status=ProcessingStatus.uploaded,
    )
    db.add(sv)
    await db.flush()
    await db.refresh(sv)
    return sv


async def _get_evidence_units(
    db: AsyncSession, source_version_id: uuid.UUID
) -> list[EvidenceUnit]:
    result = await db.execute(
        select(EvidenceUnit).where(EvidenceUnit.source_version_id == source_version_id)
    )
    return list(result.scalars().all())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ========================================================================
# 1. Unicode preservation
# ========================================================================


class TestUnicodePreservation:
    """Verify that Unicode text in PDFs is preserved through extraction."""

    @pytest.mark.asyncio
    async def test_unicode_text_preserved(self, db_session: AsyncSession, tmp_path: Path):
        """Accented Latin characters survive PDF extraction intact.

        The built-in PDF font (Helvetica) only encodes Latin-1 / Latin-2
        characters.  Greek, CJK, and em-dash are dropped at PDF creation
        time.  This test verifies the extraction pipeline preserves
        characters that the PDF actually contains.
        """
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_unicode_pdf(), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)
        assert result.processing_status == "ready"
        assert result.text_evidence_count >= 1

        units = await _get_evidence_units(db_session, sv.id)
        text_units = [u for u in units if u.modality == Modality.text]
        assert len(text_units) >= 1

        combined_text = " ".join(u.original_text for u in text_units if u.original_text)

        # Verify accented characters survived extraction
        assert "Café" in combined_text, "Accented 'Café' not preserved"
        assert "résumé" in combined_text, "Accented 'résumé' not preserved"
        assert "naïve" in combined_text, "Diaeresis in 'naïve' not preserved"
        assert "über" in combined_text, "Umlaut in 'über' not preserved"
        assert "Zürich" in combined_text, "Umlaut in 'Zürich' not preserved"
        assert "año" in combined_text, "Tilde in 'año' not preserved"
        assert "señor" in combined_text, "Tilde in 'señor' not preserved"


# ========================================================================
# 2. Image-only / scanned-style PDF behavior
# ========================================================================


class TestImageOnlyPdf:
    """Verify correct handling of PDFs with embedded images but no text."""

    @pytest.mark.asyncio
    async def test_image_only_pdf_succeeds(self, db_session: AsyncSession, tmp_path: Path):
        """An image-only PDF processes successfully and transitions to ready."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_image_only_pdf(), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)
        assert result.processing_status == "ready"
        await db_session.refresh(sv)
        assert sv.processing_status == ProcessingStatus.ready

    @pytest.mark.asyncio
    async def test_image_only_no_text_fabricated(self, db_session: AsyncSession, tmp_path: Path):
        """No text EvidenceUnit is fabricated for an image-only PDF."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_image_only_pdf(), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)
        assert result.text_evidence_count == 0

        units = await _get_evidence_units(db_session, sv.id)
        text_units = [u for u in units if u.modality == Modality.text]
        assert len(text_units) == 0, "Text EvidenceUnits were fabricated for image-only PDF"

    @pytest.mark.asyncio
    async def test_image_only_image_evidence_created(self, db_session: AsyncSession, tmp_path: Path):
        """Image evidence is created for the embedded image in an image-only PDF."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_image_only_pdf(), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)
        assert result.image_evidence_count >= 1

        units = await _get_evidence_units(db_session, sv.id)
        image_units = [u for u in units if u.modality == Modality.image]
        assert len(image_units) >= 1


# ========================================================================
# 3. Original source file immutability
# ========================================================================


class TestSourceImmutability:
    """Verify that the ingestion pipeline never modifies the original source file."""

    @pytest.mark.asyncio
    async def test_original_pdf_hash_unchanged(self, db_session: AsyncSession, tmp_path: Path):
        """SHA-256 of the original PDF is identical before and after processing."""
        pdf_bytes = make_text_pdf()
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=pdf_bytes, tmp_path=tmp_path,
        )

        pdf_path = Path(sv.storage_path)
        hash_before = _sha256(pdf_path)

        await process_pdf(db_session, source_version=sv)

        hash_after = _sha256(pdf_path)
        assert hash_before == hash_after, (
            f"Original PDF was modified during processing: "
            f"before={hash_before}, after={hash_after}"
        )

    @pytest.mark.asyncio
    async def test_image_pdf_hash_unchanged(self, db_session: AsyncSession, tmp_path: Path):
        """SHA-256 of a PDF containing images is unchanged after processing (with image extraction)."""
        pdf_bytes = make_image_pdf()
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=pdf_bytes, tmp_path=tmp_path,
        )

        pdf_path = Path(sv.storage_path)
        hash_before = _sha256(pdf_path)

        result = await process_pdf(db_session, source_version=sv)
        assert result.image_evidence_count >= 1  # Ensure images were actually extracted

        hash_after = _sha256(pdf_path)
        assert hash_before == hash_after, "Original PDF with images was modified during processing"


# ========================================================================
# 4. Derived image path separation
# ========================================================================


class TestDerivedImageSeparation:
    """Verify derived files are stored outside uploads and don't overwrite originals."""

    @pytest.mark.asyncio
    async def test_derived_path_outside_uploads(self, db_session: AsyncSession, tmp_path: Path):
        """Derived image files are stored outside the upload directory."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_image_pdf(), tmp_path=tmp_path,
        )

        from app.core.config import settings
        upload_dir = Path(settings.upload_dir).resolve()

        result = await process_pdf(db_session, source_version=sv)
        assert result.image_evidence_count >= 1

        units = await _get_evidence_units(db_session, sv.id)
        image_units = [u for u in units if u.modality == Modality.image]

        for iu in image_units:
            derived_path = Path(iu.location_metadata["derived_path"]).resolve()
            # Derived path must NOT be under the upload directory
            assert not str(derived_path).startswith(str(upload_dir)), (
                f"Derived file {derived_path} is inside upload dir {upload_dir}"
            )

    @pytest.mark.asyncio
    async def test_derived_path_under_derived_dir(self, db_session: AsyncSession, tmp_path: Path):
        """Derived image files are under the intended derived-artifact location."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_image_pdf(), tmp_path=tmp_path,
        )

        from app.services.derived_storage import derived_dir_for
        expected_derived_dir = derived_dir_for(sv.id)

        result = await process_pdf(db_session, source_version=sv)
        assert result.image_evidence_count >= 1

        units = await _get_evidence_units(db_session, sv.id)
        image_units = [u for u in units if u.modality == Modality.image]

        for iu in image_units:
            derived_path = Path(iu.location_metadata["derived_path"]).resolve()
            assert str(derived_path).startswith(str(expected_derived_dir)), (
                f"Derived file {derived_path} is not under {expected_derived_dir}"
            )

    @pytest.mark.asyncio
    async def test_derived_does_not_overwrite_source(self, db_session: AsyncSession, tmp_path: Path):
        """No derived file has the same path as the original source PDF."""
        pdf_bytes = make_image_pdf()
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=pdf_bytes, tmp_path=tmp_path,
        )

        original_path = Path(sv.storage_path).resolve()

        result = await process_pdf(db_session, source_version=sv)
        assert result.image_evidence_count >= 1

        units = await _get_evidence_units(db_session, sv.id)
        image_units = [u for u in units if u.modality == Modality.image]

        for iu in image_units:
            derived_path = Path(iu.location_metadata["derived_path"]).resolve()
            assert derived_path != original_path, "Derived file overwrites the source PDF"

    @pytest.mark.asyncio
    async def test_derived_files_exist_on_disk(self, db_session: AsyncSession, tmp_path: Path):
        """Derived image files actually exist on disk after extraction."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_image_pdf(), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)
        assert result.image_evidence_count >= 1

        units = await _get_evidence_units(db_session, sv.id)
        image_units = [u for u in units if u.modality == Modality.image]

        for iu in image_units:
            derived_path = Path(iu.location_metadata["derived_path"])
            assert derived_path.exists(), f"Derived file does not exist: {derived_path}"
            assert derived_path.stat().st_size > 0, f"Derived file is empty: {derived_path}"


# ========================================================================
# 5. Text bounding-box evidence
# ========================================================================


class TestBoundingBox:
    """Verify bounding-box data in text EvidenceUnit location_metadata."""

    @pytest.mark.asyncio
    async def test_text_bbox_present(self, db_session: AsyncSession, tmp_path: Path):
        """At least one text EvidenceUnit has a non-null bounding_box."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_text_pdf(), tmp_path=tmp_path,
        )

        await process_pdf(db_session, source_version=sv)
        units = await _get_evidence_units(db_session, sv.id)
        text_units = [u for u in units if u.modality == Modality.text]
        assert len(text_units) >= 1

        units_with_bbox = [
            u for u in text_units
            if u.location_metadata and u.location_metadata.get("bounding_box") is not None
        ]
        assert len(units_with_bbox) >= 1, "No text EvidenceUnit has a bounding_box"

    @pytest.mark.asyncio
    async def test_text_bbox_four_coordinates(self, db_session: AsyncSession, tmp_path: Path):
        """Bounding box has exactly four numeric coordinates [x0, y0, x1, y1]."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_text_pdf(), tmp_path=tmp_path,
        )

        await process_pdf(db_session, source_version=sv)
        units = await _get_evidence_units(db_session, sv.id)
        text_units = [
            u for u in units
            if u.modality == Modality.text
            and u.location_metadata
            and u.location_metadata.get("bounding_box") is not None
        ]
        assert len(text_units) >= 1

        for u in text_units:
            bbox = u.location_metadata["bounding_box"]
            assert isinstance(bbox, list), f"bounding_box is not a list: {type(bbox)}"
            assert len(bbox) == 4, f"bounding_box has {len(bbox)} elements, expected 4"
            for coord in bbox:
                assert isinstance(coord, (int, float)), (
                    f"bounding_box coordinate is not numeric: {coord!r}"
                )

    @pytest.mark.asyncio
    async def test_text_bbox_from_parser(self, db_session: AsyncSession, tmp_path: Path):
        """Bounding box coordinates are plausible page coordinates, not fabricated zeros."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_text_pdf(), tmp_path=tmp_path,
        )

        await process_pdf(db_session, source_version=sv)
        units = await _get_evidence_units(db_session, sv.id)
        text_units = [
            u for u in units
            if u.modality == Modality.text
            and u.location_metadata
            and u.location_metadata.get("bounding_box") is not None
        ]
        assert len(text_units) >= 1

        bbox = text_units[0].location_metadata["bounding_box"]
        x0, y0, x1, y1 = bbox
        # make_text_pdf inserts at (72, 72) — bbox should have non-zero area
        assert x1 > x0, f"x1 ({x1}) must be > x0 ({x0})"
        assert y1 > y0, f"y1 ({y1}) must be > y0 ({y0})"
        # Coordinates should be within typical PDF page bounds (letter/A4)
        assert x0 >= 0, f"x0 ({x0}) is negative"
        assert y0 >= 0, f"y0 ({y0}) is negative"
        assert x1 <= 700, f"x1 ({x1}) exceeds page width"
        assert y1 <= 900, f"y1 ({y1}) exceeds page height"


# ========================================================================
# 6. Page numbering
# ========================================================================


class TestPageNumbering:
    """Verify that page_index (0-based) and page_number (1-based) are correct."""

    @pytest.mark.asyncio
    async def test_page_numbering_multipage(self, db_session: AsyncSession, tmp_path: Path):
        """On a multi-page PDF, page 1 has index=0/number=1, page 2 has index=1/number=2."""
        num_pages = 3
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id,
            pdf_bytes=make_multipage_pdf(num_pages), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)
        assert result.page_count == num_pages

        units = await _get_evidence_units(db_session, sv.id)
        text_units = [u for u in units if u.modality == Modality.text]
        assert len(text_units) >= num_pages  # at least one per page

        # Collect all (page_index, page_number) pairs seen across evidence
        page_pairs = set()
        for u in text_units:
            meta = u.location_metadata
            page_pairs.add((meta["page_index"], meta["page_number"]))

        # Verify page 1: index=0, number=1
        assert (0, 1) in page_pairs, "Page 1 should have page_index=0, page_number=1"
        # Verify page 2: index=1, number=2
        assert (1, 2) in page_pairs, "Page 2 should have page_index=1, page_number=2"
        # Verify page 3: index=2, number=3
        assert (2, 3) in page_pairs, "Page 3 should have page_index=2, page_number=3"

        # Verify the invariant across all evidence
        for u in text_units:
            meta = u.location_metadata
            assert meta["page_number"] == meta["page_index"] + 1, (
                f"page_number ({meta['page_number']}) != page_index ({meta['page_index']}) + 1"
            )
