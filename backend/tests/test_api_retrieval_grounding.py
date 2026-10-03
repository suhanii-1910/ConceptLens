import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, select, null
from datetime import datetime
import json
import copy

from app.models.course import Course
from app.models.source_version import SourceVersion, SourceType, ProcessingStatus
from app.models.evidence_unit import EvidenceUnit, Modality, ExtractionStatus
from app.services.embedding_provider import FakeEmbeddingProvider

@pytest.fixture
def base_ids():
    return {
        "course": uuid.uuid4(),
        "sv": uuid.uuid4(),
        "eu": uuid.uuid4()
    }

@pytest.mark.asyncio
async def test_api_retrieval_grounding_valid(client: AsyncClient, db_session: AsyncSession, base_ids):
    # Setup test data
    import os
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"
    c_id = base_ids["course"]
    sv_id = base_ids["sv"]
    eu_id = base_ids["eu"]
    
    course = Course(id=c_id, name="Test", description="Test")
    db_session.add(course)
    
    sv = SourceVersion(
        id=sv_id,
        course_id=c_id,
        original_filename="test.pdf",
        file_hash="x",
        mime_type="application/pdf",
        source_type=SourceType.pdf,
        storage_path="x",
        processing_status=ProcessingStatus.ready
    )
    db_session.add(sv)
    
    eu = EvidenceUnit(
        id=eu_id,
        course_id=c_id,
        source_version_id=sv_id,
        modality=Modality.text,
        original_text="test content",
        extraction_status=ExtractionStatus.extracted,
        # Ensure correct exact location matching
        location_metadata={"page_index": 0, "page_number": 1},
        embedding=[0.1]*384
    )
    db_session.add(eu)
    await db_session.commit()
    
    # Must index before search (mock behavior)
    # The hybrid_search normally expects full schema setup but we can insert vectors
    
    # Send retrieval req
    res = await client.post(
        f"/courses/{str(c_id)}/retrieval/search",
        json={"query": "test content", "top_k": 5}
    )
    assert res.status_code == 200
    
    data = res.json()
    assert "results" in data
    assert len(data["results"]) == 1
    
    res0 = data["results"][0]
    
    assert res0["grounding_status"] == "valid"
    assert res0["citation"] is not None
    assert res0["citation"]["locator"]["page_index"] == 0
    assert res0["citation"]["locator"]["page_number"] == 1
    assert res0["citation"]["locator_label"] == "test.pdf · p. 1"
    assert res0["grounding_errors"] == []

@pytest.mark.asyncio
async def test_api_retrieval_grounding_invalid(client: AsyncClient, db_session: AsyncSession, base_ids):
    import os
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"
    c_id = uuid.uuid4()
    sv_id = uuid.uuid4()
    eu_id = uuid.uuid4()
    
    course = Course(id=c_id, name="Test", description="Test")
    db_session.add(course)
    sv = SourceVersion(
        id=sv_id, course_id=c_id, original_filename="test.pdf", file_hash="x",
        mime_type="application/pdf", source_type=SourceType.pdf, storage_path="x",
        processing_status=ProcessingStatus.ready
    )
    db_session.add(sv)
    
    # MISSING location metadata
    eu = EvidenceUnit(
        id=eu_id, course_id=c_id, source_version_id=sv_id, modality=Modality.text,
        original_text="test missing metadata", extraction_status=ExtractionStatus.extracted,
        location_metadata=None, embedding=[0.1]*384
    )
    db_session.add(eu)
    await db_session.commit()
    
    res = await client.post(
        f"/courses/{str(c_id)}/retrieval/search",
        json={"query": "test metadata", "top_k": 5}
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) == 1
    res0 = data["results"][0]
    
    assert res0["grounding_status"] == "invalid"
    assert res0["citation"] is None
    assert "missing_location_metadata" in res0["grounding_errors"]
