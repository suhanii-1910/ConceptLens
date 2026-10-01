"""Comprehensive tests for PDF ingestion service and API endpoint.

Test categories:
    1. Service-level tests (process_pdf, extraction helpers)
    2. API endpoint tests (POST /courses/{id}/sources/{id}/process)
    3. Edge cases & error handling

All PDFs are generated programmatically — no binary fixtures needed.
"""

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.evidence_unit import EvidenceUnit, ExtractionStatus, Modality
from app.models.source_version import ProcessingStatus, SourceType, SourceVersion
from app.services.pdf_ingestion import (
    AlreadyProcessedError,
    NotAPDFError,
    PDFProcessingError,
    ProcessingResult,
    _table_to_markdown,
    process_pdf,
)
from tests.fixtures.pdf_factory import (
    make_empty_pdf,
    make_image_pdf,
    make_mixed_content_pdf,
    make_multiblock_pdf,
    make_multipage_pdf,
    make_short_text_pdf,
    make_table_pdf,
    make_text_pdf,
    make_tiny_image_pdf,
)


# ---- helpers ----


async def _create_course(db: AsyncSession, name: str = "Test Course") -> Course:
    """Insert a minimal Course and return it."""
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
    filename: str = "test.pdf",
    source_type: SourceType = SourceType.pdf,
    processing_status: ProcessingStatus = ProcessingStatus.uploaded,
) -> SourceVersion:
    """Write pdf_bytes to disk and insert a matching SourceVersion row."""
    pdf_path = tmp_path / filename
    pdf_path.write_bytes(pdf_bytes)

    sv = SourceVersion(
        course_id=course_id,
        original_filename=filename,
        file_hash="sha256_test_" + uuid.uuid4().hex[:16],
        mime_type="application/pdf",
        source_type=source_type,
        storage_path=str(pdf_path),
        processing_status=processing_status,
    )
    db.add(sv)
    await db.flush()
    await db.refresh(sv)
    return sv


async def _get_evidence_units(
    db: AsyncSession, source_version_id: uuid.UUID
) -> list[EvidenceUnit]:
    """Fetch all EvidenceUnits for a source version."""
    result = await db.execute(
        select(EvidenceUnit).where(EvidenceUnit.source_version_id == source_version_id)
    )
    return list(result.scalars().all())


# ========================================================================
# 1. Service-level tests
# ========================================================================


class TestProcessPdfService:
    """Tests for the process_pdf service function."""

    @pytest.mark.asyncio
    async def test_text_extraction_basic(self, db_session: AsyncSession, tmp_path: Path):
        """Text blocks are extracted and stored as EvidenceUnits."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_text_pdf(), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)

        assert result.processing_status == "ready"
        assert result.page_count >= 1
        assert result.text_evidence_count >= 1

        units = await _get_evidence_units(db_session, sv.id)
        text_units = [u for u in units if u.modality == Modality.text]
        assert len(text_units) >= 1
        assert all(u.original_text for u in text_units)
        assert all(u.extraction_status == ExtractionStatus.extracted for u in text_units)

    @pytest.mark.asyncio
    async def test_multiblock_text(self, db_session: AsyncSession, tmp_path: Path):
        """Multiple distinct text blocks yield multiple EvidenceUnits."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_multiblock_pdf(), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)
        assert result.text_evidence_count >= 2

    @pytest.mark.asyncio
    async def test_short_text_skipped(self, db_session: AsyncSession, tmp_path: Path):
        """Text below MIN_TEXT_CHARS threshold is not extracted."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_short_text_pdf(), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)
        assert result.text_evidence_count == 0

    @pytest.mark.asyncio
    async def test_empty_pdf(self, db_session: AsyncSession, tmp_path: Path):
        """An empty PDF processes successfully with zero evidence."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_empty_pdf(), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)
        assert result.processing_status == "ready"
        assert result.text_evidence_count == 0
        assert result.table_evidence_count == 0
        assert result.image_evidence_count == 0
        assert result.page_count == 1

    @pytest.mark.asyncio
    async def test_image_extraction(self, db_session: AsyncSession, tmp_path: Path):
        """Embedded images above the dimension threshold are extracted."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_image_pdf(), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)
        assert result.image_evidence_count >= 1

        units = await _get_evidence_units(db_session, sv.id)
        image_units = [u for u in units if u.modality == Modality.image]
        assert len(image_units) >= 1
        for iu in image_units:
            assert iu.location_metadata is not None
            assert iu.location_metadata["element_type"] == "image"
            assert "derived_path" in iu.location_metadata

    @pytest.mark.asyncio
    async def test_tiny_image_skipped(self, db_session: AsyncSession, tmp_path: Path):
        """Images below MIN_IMAGE_DIMENSION are not extracted."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_tiny_image_pdf(), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)
        assert result.image_evidence_count == 0

    @pytest.mark.asyncio
    async def test_multipage_pdf(self, db_session: AsyncSession, tmp_path: Path):
        """Multi-page PDFs report the correct page count."""
        num_pages = 5
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id,
            pdf_bytes=make_multipage_pdf(num_pages), tmp_path=tmp_path,
        )

        result = await process_pdf(db_session, source_version=sv)
        assert result.page_count == num_pages
        # Each page has enough text → at least one unit per page
        assert result.text_evidence_count >= 1

    @pytest.mark.asyncio
    async def test_location_metadata_structure(self, db_session: AsyncSession, tmp_path: Path):
        """EvidenceUnit.location_metadata has required provenance keys."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_text_pdf(), tmp_path=tmp_path,
        )

        await process_pdf(db_session, source_version=sv)
        units = await _get_evidence_units(db_session, sv.id)
        text_units = [u for u in units if u.modality == Modality.text]
        assert len(text_units) >= 1

        meta = text_units[0].location_metadata
        assert meta is not None
        assert "page_index" in meta
        assert "page_number" in meta
        assert meta["page_number"] == meta["page_index"] + 1
        assert "element_type" in meta
        assert meta["element_type"] == "text"

    @pytest.mark.asyncio
    async def test_status_transition_to_ready(self, db_session: AsyncSession, tmp_path: Path):
        """Successful processing transitions status to 'ready'."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_text_pdf(), tmp_path=tmp_path,
        )

        assert sv.processing_status == ProcessingStatus.uploaded
        await process_pdf(db_session, source_version=sv)
        await db_session.refresh(sv)
        assert sv.processing_status == ProcessingStatus.ready

    @pytest.mark.asyncio
    async def test_status_transition_to_failed(self, db_session: AsyncSession, tmp_path: Path):
        """Processing a missing file transitions status to 'failed'."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_text_pdf(), tmp_path=tmp_path,
        )
        # Delete the file so extraction fails
        Path(sv.storage_path).unlink()

        with pytest.raises(PDFProcessingError):
            await process_pdf(db_session, source_version=sv)

        await db_session.refresh(sv)
        assert sv.processing_status == ProcessingStatus.failed

    @pytest.mark.asyncio
    async def test_idempotency_already_ready(self, db_session: AsyncSession, tmp_path: Path):
        """Processing an already-ready source raises AlreadyProcessedError."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_text_pdf(), tmp_path=tmp_path,
        )

        # Process once
        await process_pdf(db_session, source_version=sv)
        await db_session.refresh(sv)
        assert sv.processing_status == ProcessingStatus.ready

        # Process again — should raise
        with pytest.raises(AlreadyProcessedError) as exc_info:
            await process_pdf(db_session, source_version=sv)

        assert exc_info.value.result.already_processed is True

    @pytest.mark.asyncio
    async def test_retry_after_failure(self, db_session: AsyncSession, tmp_path: Path):
        """A failed source can be retried and succeed."""
        course = await _create_course(db_session)
        pdf_bytes = make_text_pdf()
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=pdf_bytes, tmp_path=tmp_path,
        )

        # Delete file → failure
        pdf_path = Path(sv.storage_path)
        pdf_path.unlink()
        with pytest.raises(PDFProcessingError):
            await process_pdf(db_session, source_version=sv)

        await db_session.refresh(sv)
        assert sv.processing_status == ProcessingStatus.failed

        # Restore file → retry should succeed
        pdf_path.write_bytes(pdf_bytes)
        result = await process_pdf(db_session, source_version=sv)
        assert result.processing_status == "ready"
        await db_session.refresh(sv)
        assert sv.processing_status == ProcessingStatus.ready

    @pytest.mark.asyncio
    async def test_non_pdf_rejected(self, db_session: AsyncSession, tmp_path: Path):
        """Processing a non-PDF source raises NotAPDFError."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=b"dummy",
            tmp_path=tmp_path, source_type=SourceType.pptx,
        )

        with pytest.raises(NotAPDFError):
            await process_pdf(db_session, source_version=sv)

    @pytest.mark.asyncio
    async def test_topic_subtopic_null(self, db_session: AsyncSession, tmp_path: Path):
        """Phase 1A must NOT populate topic/subtopic."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_text_pdf(), tmp_path=tmp_path,
        )

        await process_pdf(db_session, source_version=sv)
        units = await _get_evidence_units(db_session, sv.id)
        for u in units:
            assert u.topic is None
            assert u.subtopic is None

    @pytest.mark.asyncio
    async def test_extracted_description_null(self, db_session: AsyncSession, tmp_path: Path):
        """Phase 1A must NOT populate extracted_description (no LLM calls)."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_image_pdf(), tmp_path=tmp_path,
        )

        await process_pdf(db_session, source_version=sv)
        units = await _get_evidence_units(db_session, sv.id)
        for u in units:
            assert u.extracted_description is None

    @pytest.mark.asyncio
    async def test_course_id_propagation(self, db_session: AsyncSession, tmp_path: Path):
        """All EvidenceUnits inherit the correct course_id."""
        course = await _create_course(db_session)
        sv = await _create_source_version(
            db_session, course_id=course.id, pdf_bytes=make_text_pdf(), tmp_path=tmp_path,
        )

        await process_pdf(db_session, source_version=sv)
        units = await _get_evidence_units(db_session, sv.id)
        assert all(u.course_id == course.id for u in units)


# ========================================================================
# 2. Table helpers
# ========================================================================


class TestTableToMarkdown:
    """Tests for the _table_to_markdown helper."""

    def test_basic_table(self):
        rows = [["A", "B"], ["1", "2"]]
        md = _table_to_markdown(rows)
        lines = md.strip().split("\n")
        assert len(lines) == 3  # header + separator + 1 body row
        assert "| A | B |" in lines[0]
        assert "---" in lines[1]
        assert "| 1 | 2 |" in lines[2]

    def test_empty_input(self):
        assert _table_to_markdown([]) == ""

    def test_none_cells(self):
        rows = [["X", None], [None, "Y"]]
        md = _table_to_markdown(rows)
        assert "X" in md
        assert "Y" in md

    def test_pipe_in_cell(self):
        """Pipe characters inside cell values are escaped."""
        rows = [["Header"], ["a|b"]]
        md = _table_to_markdown(rows)
        assert "a\\|b" in md


# ========================================================================
# 3. API endpoint tests
# ========================================================================


class TestProcessEndpoint:
    """Tests for POST /courses/{course_id}/sources/{source_version_id}/process."""

    @pytest.mark.asyncio
    async def test_process_endpoint_success(self, client: AsyncClient, tmp_path: Path):
        """Happy path: upload then process returns 201 with result."""
        # Create course
        resp = await client.post("/courses", json={"name": "PDF Course"})
        assert resp.status_code == 201
        course_id = resp.json()["id"]

        # Upload a PDF
        pdf_bytes = make_text_pdf()
        resp = await client.post(
            f"/courses/{course_id}/sources",
            files={"file": ("lecture.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 201
        sv_id = resp.json()["id"]

        # Process
        resp = await client.post(f"/courses/{course_id}/sources/{sv_id}/process")
        assert resp.status_code == 201

        data = resp.json()
        assert data["source_version_id"] == sv_id
        assert data["processing_status"] == "ready"
        assert data["page_count"] >= 1
        assert data["already_processed"] is False

    @pytest.mark.asyncio
    async def test_process_endpoint_idempotent(self, client: AsyncClient, tmp_path: Path):
        """Second process call returns 200 with already_processed=True."""
        resp = await client.post("/courses", json={"name": "Idem Course"})
        course_id = resp.json()["id"]

        pdf_bytes = make_text_pdf()
        resp = await client.post(
            f"/courses/{course_id}/sources",
            files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
        )
        sv_id = resp.json()["id"]

        # First process
        resp = await client.post(f"/courses/{course_id}/sources/{sv_id}/process")
        assert resp.status_code == 201

        # Second process
        resp = await client.post(f"/courses/{course_id}/sources/{sv_id}/process")
        assert resp.status_code == 200
        assert resp.json()["already_processed"] is True

    @pytest.mark.asyncio
    async def test_process_endpoint_course_not_found(self, client: AsyncClient):
        """Returns 404 for non-existent course."""
        fake_course = str(uuid.uuid4())
        fake_sv = str(uuid.uuid4())
        resp = await client.post(f"/courses/{fake_course}/sources/{fake_sv}/process")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_process_endpoint_source_not_found(self, client: AsyncClient):
        """Returns 404 if source doesn't belong to course."""
        resp = await client.post("/courses", json={"name": "Lost Source"})
        course_id = resp.json()["id"]

        fake_sv = str(uuid.uuid4())
        resp = await client.post(f"/courses/{course_id}/sources/{fake_sv}/process")
        assert resp.status_code == 404


# ========================================================================
# 4. Result dataclass
# ========================================================================


class TestProcessingResult:
    """Tests for the ProcessingResult dataclass."""

    def test_defaults(self):
        r = ProcessingResult(source_version_id=uuid.uuid4(), processing_status="ready")
        assert r.page_count == 0
        assert r.text_evidence_count == 0
        assert r.table_evidence_count == 0
        assert r.image_evidence_count == 0
        assert r.warnings == []
        assert r.already_processed is False

    def test_custom_values(self):
        sid = uuid.uuid4()
        r = ProcessingResult(
            source_version_id=sid,
            processing_status="ready",
            page_count=10,
            text_evidence_count=50,
            warnings=["table extraction failed"],
        )
        assert r.source_version_id == sid
        assert r.page_count == 10
        assert r.text_evidence_count == 50
        assert len(r.warnings) == 1
