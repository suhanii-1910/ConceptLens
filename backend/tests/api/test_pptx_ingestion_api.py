import os
import uuid
import collections
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from pptx import Presentation
from pptx.util import Inches

from app.models.evidence_unit import EvidenceUnit
from app.models.source_version import SourceVersion


@pytest.fixture
def tmp_pptx(tmp_path) -> Path:
    """Fixture that generates a programmatic PPTX for testing."""
    prs = Presentation()

    # Slide 1: Normal text
    blank_slide_layout = prs.slide_layouts[6]
    slide1 = prs.slides.add_slide(blank_slide_layout)
    txBox1 = slide1.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1))
    tf1 = txBox1.text_frame
    tf1.text = "  \n  Slide 1 Text  \n  "

    # Add empty text shape (should be skipped)
    txBox_empty = slide1.shapes.add_textbox(Inches(1), Inches(2), Inches(2), Inches(1))
    tf_empty = txBox_empty.text_frame
    tf_empty.text = "   \n  "

    # Slide 2: Unicode text
    slide2 = prs.slides.add_slide(blank_slide_layout)
    txBox2 = slide2.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1))
    tf2 = txBox2.text_frame
    tf2.text = "Unicode 🌟 ñ 測試"

    pptx_file = tmp_path / "test.pptx"
    prs.save(str(pptx_file))
    return pptx_file


@pytest.fixture
def corrupt_pptx(tmp_path) -> Path:
    """Fixture that generates a corrupt PPTX for testing."""
    pptx_file = tmp_path / "corrupt.pptx"
    pptx_file.write_bytes(b"PK\x03\x04 not a real pptx file content")
    return pptx_file


@pytest.mark.asyncio
async def test_process_pptx_dispatcher(client: AsyncClient, tmp_pptx: Path, db_session: AsyncSession):
    # 1. Create course
    resp = await client.post("/courses", json={"name": "Process PPTX Dispatcher"})
    assert resp.status_code == 201
    course_id = resp.json()["id"]

    # 2. Upload PPTX
    with open(tmp_pptx, "rb") as f:
        pptx_bytes = f.read()

    resp = await client.post(
        f"/courses/{course_id}/sources",
        files={"file": ("test.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )
    assert resp.status_code == 201
    source_version_id = resp.json()["id"]

    # 3. Trigger processing
    resp = await client.post(f"/courses/{course_id}/sources/{source_version_id}/process")
    assert resp.status_code == 201
    data = resp.json()
    assert data["processing_status"] == "ready"
    assert data["slide_count"] == 2
    assert data["page_count"] is None
    assert data["text_evidence_count"] == 2  # Slide 1 Text, Unicode text
    assert data["table_evidence_count"] == 0
    assert data["image_evidence_count"] == 0

    # 4. Verify evidence in DB
    # We can fetch evidence units via the db session
    from sqlalchemy import select

    result = await db_session.execute(
        select(EvidenceUnit)
        .where(EvidenceUnit.source_version_id == uuid.UUID(source_version_id))
    )
    evidence_units = result.scalars().all()
    # Sort in Python by slide_index since UUIDs have random ordering
    evidence_units.sort(key=lambda x: x.location_metadata["slide_index"])

    assert len(evidence_units) == 2


    # Verify first slide text
    eu1 = evidence_units[0]
    assert eu1.original_text == "  \n  Slide 1 Text  \n  "
    assert eu1.location_metadata["slide_index"] == 0
    assert eu1.location_metadata["slide_number"] == 1
    assert "bounding_box" in eu1.location_metadata
    assert eu1.location_metadata["coordinate_unit"] == "emu"
    assert eu1.location_metadata["element_type"] == "text"
    w = eu1.location_metadata["slide_width"]
    h = eu1.location_metadata["slide_height"]
    assert w > 0 and h > 0


    # Verify second slide text (unicode)
    eu2 = evidence_units[1]
    assert eu2.original_text == "Unicode 🌟 ñ 測試"
    assert eu2.location_metadata["slide_index"] == 1
    assert eu2.location_metadata["slide_number"] == 2

    # 5. Trigger processing again (already ready)
    resp = await client.post(f"/courses/{course_id}/sources/{source_version_id}/process")
    assert resp.status_code == 200  # Returns 200 Not modified/Already Processed
    data2 = resp.json()
    assert data2["already_processed"] is True
    assert data2["processing_status"] == "ready"
    assert data2["slide_count"] == 2
    assert data2["page_count"] is None

    # 6. Verify evidence count hasn't changed (Idempotency)
    result = await db_session.execute(
        select(EvidenceUnit)
        .where(EvidenceUnit.source_version_id == uuid.UUID(source_version_id))
    )
    evidence_units_post_duplicate = result.scalars().all()
    assert len(evidence_units_post_duplicate) == 2


@pytest.mark.asyncio
async def test_process_corrupt_pptx(client: AsyncClient, corrupt_pptx: Path):
    resp = await client.post("/courses", json={"name": "Corrupt PPTX"})
    assert resp.status_code == 201
    course_id = resp.json()["id"]

    with open(corrupt_pptx, "rb") as f:
        pptx_bytes = f.read()

    resp = await client.post(
        f"/courses/{course_id}/sources",
        files={"file": ("corrupt.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )
    assert resp.status_code == 201
    source_version_id = resp.json()["id"]

    # Trigger processing
    resp = await client.post(f"/courses/{course_id}/sources/{source_version_id}/process")
    assert resp.status_code == 422
    assert "PPTX processing failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_process_video_not_supported(client: AsyncClient):
    resp = await client.post("/courses", json={"name": "Video Processing"})
    assert resp.status_code == 201
    course_id = resp.json()["id"]

    mp4_bytes = b"\x00\x00\x00\x18ftypmp42"
    resp = await client.post(
        f"/courses/{course_id}/sources",
        files={"file": ("vid.mp4", mp4_bytes, "video/mp4")},
    )
    assert resp.status_code == 201
    source_version_id = resp.json()["id"]

    # Trigger processing
    resp = await client.post(f"/courses/{course_id}/sources/{source_version_id}/process")
    assert resp.status_code == 400
    assert "Video processing is not yet implemented" in resp.json()["detail"]
