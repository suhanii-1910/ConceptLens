"""Tests for source upload and file-storage behavior."""

import hashlib
import io
import os
import uuid

import pytest
from httpx import AsyncClient


def _make_upload(content: bytes, filename: str, content_type: str) -> dict:
    """Build the ``files`` dict for httpx multipart upload."""
    return {"file": (filename, io.BytesIO(content), content_type)}


# ---- valid uploads ----


@pytest.mark.asyncio
async def test_upload_pdf(client: AsyncClient):
    resp = await client.post("/courses", json={"name": "PDF Course"})
    course_id = resp.json()["id"]

    pdf_bytes = b"%PDF-1.4 fake content"
    resp = await client.post(
        f"/courses/{course_id}/sources",
        files=_make_upload(pdf_bytes, "lecture.pdf", "application/pdf"),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_type"] == "pdf"
    assert data["original_filename"] == "lecture.pdf"
    assert data["processing_status"] == "uploaded"
    assert data["mime_type"] == "application/pdf"


@pytest.mark.asyncio
async def test_upload_pptx(client: AsyncClient):
    resp = await client.post("/courses", json={"name": "PPTX Course"})
    course_id = resp.json()["id"]

    pptx_bytes = b"PK\x03\x04 fake pptx"
    resp = await client.post(
        f"/courses/{course_id}/sources",
        files=_make_upload(
            pptx_bytes,
            "slides.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
    )
    assert resp.status_code == 201
    assert resp.json()["source_type"] == "pptx"


@pytest.mark.asyncio
async def test_upload_legacy_ppt_rejected(client: AsyncClient):
    resp = await client.post("/courses", json={"name": "Reject PPT Course"})
    course_id = resp.json()["id"]

    ppt_bytes = b"fake legacy ppt"
    resp = await client.post(
        f"/courses/{course_id}/sources",
        files=_make_upload(
            ppt_bytes,
            "slides.ppt",
            "application/vnd.ms-powerpoint",
        ),
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_mp4(client: AsyncClient):
    resp = await client.post("/courses", json={"name": "Video Course"})
    course_id = resp.json()["id"]

    mp4_bytes = b"\x00\x00\x00\x18ftypmp42"
    resp = await client.post(
        f"/courses/{course_id}/sources",
        files=_make_upload(mp4_bytes, "lecture.mp4", "video/mp4"),
    )
    assert resp.status_code == 201
    assert resp.json()["source_type"] == "video"


# ---- SHA-256 correctness ----


@pytest.mark.asyncio
async def test_sha256_correctness(client: AsyncClient):
    resp = await client.post("/courses", json={"name": "Hash Course"})
    course_id = resp.json()["id"]

    content = b"deterministic content for hashing"
    expected_hash = hashlib.sha256(content).hexdigest()

    resp = await client.post(
        f"/courses/{course_id}/sources",
        files=_make_upload(content, "doc.pdf", "application/pdf"),
    )
    assert resp.status_code == 201
    assert resp.json()["file_hash"] == expected_hash


# ---- unsupported file rejection ----


@pytest.mark.asyncio
async def test_reject_unsupported_file(client: AsyncClient):
    resp = await client.post("/courses", json={"name": "Reject Course"})
    course_id = resp.json()["id"]

    resp = await client.post(
        f"/courses/{course_id}/sources",
        files=_make_upload(b"hello world", "notes.txt", "text/plain"),
    )
    assert resp.status_code == 415


# ---- invalid course upload ----


@pytest.mark.asyncio
async def test_upload_to_nonexistent_course(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.post(
        f"/courses/{fake_id}/sources",
        files=_make_upload(b"%PDF-1.4", "doc.pdf", "application/pdf"),
    )
    assert resp.status_code == 404


# ---- safe file storage ----


@pytest.mark.asyncio
async def test_safe_storage_no_path_traversal(client: AsyncClient, tmp_path):
    resp = await client.post("/courses", json={"name": "Safe Course"})
    course_id = resp.json()["id"]

    # Upload a file with a malicious filename
    resp = await client.post(
        f"/courses/{course_id}/sources",
        files=_make_upload(b"%PDF-1.4", "../../../etc/passwd.pdf", "application/pdf"),
    )
    assert resp.status_code == 201
    data = resp.json()
    # The storage path must not contain ".."
    assert ".." not in data["storage_path"]
    # Original filename is preserved as-is for display
    assert data["original_filename"] == "../../../etc/passwd.pdf"


# ---- duplicate upload handling ----


@pytest.mark.asyncio
async def test_duplicate_upload_returns_existing(client: AsyncClient):
    resp = await client.post("/courses", json={"name": "Dedup Course"})
    course_id = resp.json()["id"]

    content = b"%PDF-1.4 same content"
    upload_args = _make_upload(content, "doc.pdf", "application/pdf")

    resp1 = await client.post(f"/courses/{course_id}/sources", files=upload_args)
    assert resp1.status_code == 201
    id1 = resp1.json()["id"]

    # Upload again — same content
    upload_args2 = _make_upload(content, "doc.pdf", "application/pdf")
    resp2 = await client.post(f"/courses/{course_id}/sources", files=upload_args2)
    assert resp2.status_code == 200  # not 201
    assert resp2.json()["id"] == id1


# ---- list sources ----


@pytest.mark.asyncio
async def test_list_sources(client: AsyncClient):
    resp = await client.post("/courses", json={"name": "List Course"})
    course_id = resp.json()["id"]

    # Empty initially
    resp = await client.get(f"/courses/{course_id}/sources")
    assert resp.status_code == 200
    assert resp.json() == []

    # Upload one file
    await client.post(
        f"/courses/{course_id}/sources",
        files=_make_upload(b"%PDF-1.4", "a.pdf", "application/pdf"),
    )
    resp = await client.get(f"/courses/{course_id}/sources")
    assert len(resp.json()) == 1
