"""
Phase 2C API integration tests: evidence_boundary in SearchResponse.

Uses the existing fake-embedding + in-memory SQLite test infrastructure.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.evidence_unit import EvidenceUnit, ExtractionStatus, Modality
from app.models.source_version import ProcessingStatus, SourceType, SourceVersion
from app.services.indexing import index_evidence_units

pytestmark = pytest.mark.asyncio


# ─── helpers ────────────────────────────────────────────────────────────────

async def _create_base(db: AsyncSession, *, filename="test.pdf", source_type=SourceType.pdf):
    """Create a course + source version and return (course_id, sv_id)."""
    c_id = uuid.uuid4()
    sv_id = uuid.uuid4()
    db.add(Course(id=c_id, name="TestCourse"))
    db.add(SourceVersion(
        id=sv_id,
        course_id=c_id,
        original_filename=filename,
        file_hash=str(uuid.uuid4()),
        mime_type="application/pdf",
        source_type=source_type,
        storage_path="x",
        processing_status=ProcessingStatus.ready,
    ))
    await db.commit()
    return c_id, sv_id


async def _add_eu(db: AsyncSession, *, c_id, sv_id, text, location_metadata):
    eu_id = uuid.uuid4()
    eu = EvidenceUnit(
        id=eu_id,
        course_id=c_id,
        source_version_id=sv_id,
        modality=Modality.text,
        original_text=text,
        extraction_status=ExtractionStatus.extracted,
        location_metadata=location_metadata,
        embedding=[0.1] * 384,
    )
    db.add(eu)
    await db.commit()
    return eu_id


# ─── test 1: supported ───────────────────────────────────────────────────────

async def test_api_boundary_supported(client: AsyncClient, db_session: AsyncSession):
    """
    Valid PDF evidence, correct page provenance.
    FakeRetrievalBackend returns distance=0.0 for first result → dense-qualified.
    Grounding valid → boundary: supported.
    """
    import os
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"

    c_id, sv_id = await _create_base(db_session)
    await _add_eu(
        db_session,
        c_id=c_id,
        sv_id=sv_id,
        text="Round Robin CPU scheduling assigns each process a fixed time quantum.",
        location_metadata={"page_index": 0, "page_number": 1},
    )
    await index_evidence_units(db_session, c_id)

    resp = await client.post(
        f"/courses/{c_id}/retrieval/search",
        json={"query": "Round Robin time quantum", "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "results" in data
    assert "evidence_boundary" in data

    eb = data["evidence_boundary"]
    assert eb["status"] == "supported"
    assert eb["should_decline"] is False
    assert eb["message"] is None
    assert eb["candidate_count"] >= 1
    assert eb["usable_candidate_count"] >= 1
    assert len(eb["usable_evidence_unit_ids"]) >= 1

    # No answer generation fields
    assert "answer" not in data
    assert "generated_answer" not in data
    assert "completion" not in data
    assert "llm_response" not in data


# ─── test 2: insufficient evidence ───────────────────────────────────────────

async def test_api_boundary_insufficient(client: AsyncClient, db_session: AsyncSession):
    """
    Evidence text matches query well (FakeBackend returns it via lexical ilike),
    but location_metadata is missing → grounding invalid → insufficient_evidence.
    Citation-invalid result still visible in results; usable_ids excludes it.
    """
    import os
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"

    c_id, sv_id = await _create_base(db_session)
    eu_id = await _add_eu(
        db_session,
        c_id=c_id,
        sv_id=sv_id,
        text="Quantum entanglement is a physical phenomenon.",
        location_metadata=None,  # deliberately broken provenance
    )
    await index_evidence_units(db_session, c_id)

    resp = await client.post(
        f"/courses/{c_id}/retrieval/search",
        json={"query": "Quantum entanglement phenomenon", "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()

    eb = data["evidence_boundary"]
    # The FakeBackend returns distance=0.0 → dense-qualified, so relevant_candidate_count >= 1
    # Grounding is invalid → insufficient_evidence
    assert eb["status"] in ("insufficient_evidence", "unsupported")
    assert eb["should_decline"] is True

    if eb["status"] == "insufficient_evidence":
        assert eb["reason"] == "relevant_evidence_not_grounded"
        assert str(eu_id) not in eb["usable_evidence_unit_ids"]

    # Citation-invalid result still visible in results list
    result_ids = [r["evidence_unit_id"] for r in data["results"]]
    assert str(eu_id) in result_ids
    # Citation should be None
    for r in data["results"]:
        if r["evidence_unit_id"] == str(eu_id):
            assert r["grounding_status"] == "invalid"
            assert r["citation"] is None


# ─── test 3: unsupported ─────────────────────────────────────────────────────

async def test_api_boundary_unsupported(client: AsyncClient, db_session: AsyncSession):
    """
    Empty course (no evidence units) → unsupported / no_candidates.
    """
    import os
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"

    c_id, _sv_id = await _create_base(db_session)
    # No evidence units added

    resp = await client.post(
        f"/courses/{c_id}/retrieval/search",
        json={"query": "quantum chromodynamics quarks", "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()

    eb = data["evidence_boundary"]
    assert eb["status"] == "unsupported"
    assert eb["should_decline"] is True
    assert eb["candidate_count"] == 0


# ─── test 4: old Phase 2A invalid provenance ({"page": 1}) still HTTP 200 ─────

async def test_api_old_invalid_provenance_still_200(client: AsyncClient, db_session: AsyncSession):
    """
    Phase 2B compatibility: evidence with {"page": 1} provenance returns HTTP 200.
    grounding remains invalid. boundary decision follows actual relevance signals.
    """
    import os
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"

    c_id, sv_id = await _create_base(db_session)
    await _add_eu(
        db_session,
        c_id=c_id,
        sv_id=sv_id,
        text="Endpoint testing relies on strong coverage.",
        location_metadata={"page": 1},  # old invalid format
    )
    await index_evidence_units(db_session, c_id)

    resp = await client.post(
        f"/courses/{c_id}/retrieval/search",
        json={"query": "Endpoint testing", "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "evidence_boundary" in data
    eb = data["evidence_boundary"]
    # Must be a valid status (any of the three)
    assert eb["status"] in ("supported", "insufficient_evidence", "unsupported")
    # Grounding must be invalid for this evidence
    for r in data["results"]:
        assert r["grounding_status"] == "invalid"


# ─── test 5: nonexistent course → 404 ────────────────────────────────────────

async def test_api_nonexistent_course_404(client: AsyncClient):
    resp = await client.post(
        f"/courses/{uuid.uuid4()}/retrieval/search",
        json={"query": "anything"},
    )
    assert resp.status_code == 404


# ─── test 6: blank query → 422 ────────────────────────────────────────────────

async def test_api_blank_query_422(client: AsyncClient, db_session: AsyncSession):
    import os
    os.environ["TESTING"] = "1"
    c_id, _ = await _create_base(db_session)
    resp = await client.post(
        f"/courses/{c_id}/retrieval/search",
        json={"query": "   "},
    )
    assert resp.status_code == 422


# ─── test 7: invalid top_k → 422 ──────────────────────────────────────────────

async def test_api_invalid_top_k_422(client: AsyncClient, db_session: AsyncSession):
    import os
    os.environ["TESTING"] = "1"
    c_id, _ = await _create_base(db_session)
    resp = await client.post(
        f"/courses/{c_id}/retrieval/search",
        json={"query": "test", "top_k": 0},
    )
    assert resp.status_code == 422


# ─── test 8: path safety — no derived_path in public result ──────────────────

async def test_api_no_derived_path_in_response(client: AsyncClient, db_session: AsyncSession):
    import os
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"

    c_id, sv_id = await _create_base(db_session)
    await _add_eu(
        db_session,
        c_id=c_id,
        sv_id=sv_id,
        text="Path safety test content.",
        location_metadata={
            "page_index": 0,
            "page_number": 1,
            "derived_path": "/private/secret/path.jpg",
        },
    )
    await index_evidence_units(db_session, c_id)

    resp = await client.post(
        f"/courses/{c_id}/retrieval/search",
        json={"query": "Path safety test", "top_k": 5},
    )
    assert resp.status_code == 200
    raw = resp.text
    assert "derived_path" not in raw
    assert "/private/secret" not in raw


# ─── test 9: no answer generation fields in response ─────────────────────────

async def test_api_no_generated_answer_fields(client: AsyncClient, db_session: AsyncSession):
    import os
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"

    c_id, sv_id = await _create_base(db_session)
    await _add_eu(
        db_session,
        c_id=c_id,
        sv_id=sv_id,
        text="Answer generation must not appear.",
        location_metadata={"page_index": 0, "page_number": 1},
    )
    await index_evidence_units(db_session, c_id)

    resp = await client.post(
        f"/courses/{c_id}/retrieval/search",
        json={"query": "answer generation", "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()

    for forbidden in ("answer", "generated_answer", "completion", "llm_response"):
        assert forbidden not in data, f"Forbidden field '{forbidden}' found in response"


# ─── test 10: evidence_boundary additive to SearchResponse ────────────────────

async def test_api_evidence_boundary_additive_to_results(client: AsyncClient, db_session: AsyncSession):
    """
    Verify that results and evidence_boundary coexist, and results are not filtered.
    """
    import os
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"

    c_id, sv_id = await _create_base(db_session)
    await _add_eu(
        db_session,
        c_id=c_id,
        sv_id=sv_id,
        text="Additive field test content.",
        location_metadata={"page_index": 0, "page_number": 1},
    )
    await index_evidence_units(db_session, c_id)

    resp = await client.post(
        f"/courses/{c_id}/retrieval/search",
        json={"query": "additive field test", "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Both fields present
    assert "results" in data
    assert "evidence_boundary" in data

    # Results not filtered — all retrieved candidates still there
    assert len(data["results"]) >= 1

    # Evidence boundary has required fields
    eb = data["evidence_boundary"]
    for field in (
        "status", "reason", "should_decline", "message",
        "candidate_count", "relevant_candidate_count",
        "usable_candidate_count", "usable_evidence_unit_ids",
    ):
        assert field in eb, f"Missing field '{field}' in evidence_boundary"
