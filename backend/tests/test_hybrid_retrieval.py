import pytest
import uuid
import math
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.evidence_unit import EvidenceUnit, ExtractionStatus, Modality
from app.services.embedding_provider import FakeEmbeddingProvider, EmbeddingProvider, EmbeddingValidationError
from app.services.indexing import index_evidence_units
from app.services.retriever import get_retrieval_backend, FakeRetrievalBackend, PostgresRetrievalBackend
from app.models.course import Course
from app.models.source_version import SourceVersion, SourceType, ProcessingStatus
from app.services.searchable_text import get_searchable_text_hash, build_canonical_searchable_text

pytestmark = pytest.mark.asyncio

# ============================================================
# SEARCHABLE TEXT TESTS
# ============================================================

async def test_searchable_text_combinations(db_session: AsyncSession):
    course_id = uuid.uuid4()
    db_session.add(Course(id=course_id, name="Text Test"))

    source = SourceVersion(
        id=uuid.uuid4(), course_id=course_id, original_filename="a", file_hash="a",
        mime_type="a", source_type=SourceType.pdf, storage_path="a", processing_status=ProcessingStatus.ready
    )
    db_session.add(source)

    # Unit 1: original_text only
    u1 = EvidenceUnit(id=uuid.uuid4(), course_id=course_id, source_version_id=source.id, modality=Modality.text, original_text="Original text.", extraction_status=ExtractionStatus.extracted)
    # Unit 2: extracted_description only
    u2 = EvidenceUnit(id=uuid.uuid4(), course_id=course_id, source_version_id=source.id, modality=Modality.image, extracted_description="Image desc.", extraction_status=ExtractionStatus.extracted)
    # Unit 3: topic/subtopic
    u3 = EvidenceUnit(id=uuid.uuid4(), course_id=course_id, source_version_id=source.id, modality=Modality.text, original_text="Text.", topic="Topic", subtopic="Sub", extraction_status=ExtractionStatus.extracted)
    # Unit 4: duplicate fields, whitespace
    u4 = EvidenceUnit(id=uuid.uuid4(), course_id=course_id, source_version_id=source.id, modality=Modality.text, original_text="  Dup   \n", topic="Dup", extracted_description="Unique", extraction_status=ExtractionStatus.extracted)
    # Unit 5: all null
    u5 = EvidenceUnit(id=uuid.uuid4(), course_id=course_id, source_version_id=source.id, modality=Modality.image, extraction_status=ExtractionStatus.extracted)
    # Unit 6: table markdown
    u6 = EvidenceUnit(id=uuid.uuid4(), course_id=course_id, source_version_id=source.id, modality=Modality.table, original_text="| A | B |\n|---|---|", extraction_status=ExtractionStatus.extracted)
    # Unit 7: video transcript
    u7 = EvidenceUnit(id=uuid.uuid4(), course_id=course_id, source_version_id=source.id, modality=Modality.video, original_text="Video transcript.", extraction_status=ExtractionStatus.extracted)

    db_session.add_all([u1, u2, u3, u4, u5, u6, u7])
    await db_session.commit()

    import os
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"

    await index_evidence_units(db_session, course_id)

    await db_session.refresh(u1)
    await db_session.refresh(u2)
    await db_session.refresh(u3)
    await db_session.refresh(u4)
    await db_session.refresh(u5)
    await db_session.refresh(u6)
    await db_session.refresh(u7)

    # We do a determinisitic content hash generation on these texts inside indexer, we can reverse verify
    import hashlib
    def get_hash(s): return get_searchable_text_hash(build_canonical_searchable_text(original_text=s, extracted_description=None, topic=None, subtopic=None))

    assert u1.embedding_content_hash == get_searchable_text_hash("Original text.")
    assert u2.embedding_content_hash == get_searchable_text_hash("Image desc.")
    assert u3.embedding_content_hash == get_searchable_text_hash("Text.\n\nTopic\n\nSub")
    assert u4.embedding_content_hash == get_searchable_text_hash("Dup\n\nUnique")
    assert u5.embedding_content_hash is None # Blank image skipped
    assert u6.embedding_content_hash == get_searchable_text_hash("| A | B | |---|---|")
    assert u7.embedding_content_hash == get_searchable_text_hash("Video transcript.")

# ============================================================
# EMBEDDING VALIDATION TESTS
# ============================================================

async def test_fake_embedding_provider_deterministic():
    provider = FakeEmbeddingProvider(dimensions=384)
    v1 = provider.embed_text("apple")
    v2 = provider.embed_text("apple")
    v3 = provider.embed_text("banana")

    assert v1 == v2
    assert v1 != v3
    assert len(v1) == 384
    
    # Check no NaN/infinity
    assert all(not math.isnan(x) for x in v1)
    assert all(not math.isinf(x) for x in v1)

class MaliciousProvider(EmbeddingProvider):
    def __init__(self, defect: str):
        self.defect = defect
    def _embed_text(self, text: str) -> List[float]:
        if self.defect == "dim": return [0.1] * 383
        if self.defect == "nan": return [float('nan')] * 384
        if self.defect == "inf": return [float('inf')] * 384
        if self.defect == "valid": return [0.1] * 384
        return []
    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        if self.defect == "count_short": return [[0.1]*384] # Only 1 result for multiple texts
        if self.defect == "count_long": return [[0.1]*384] * (len(texts) + 1)
        return [self._embed_text(t) for t in texts]
    @property
    def model_name(self) -> str: return "malicious"
    @property
    def dimensions(self) -> int: return 384

def test_embedding_validation():
    # Valid vector accepted
    p_valid = MaliciousProvider("valid")
    assert len(p_valid.embed_text("test")) == 384

    # Wrong dimension rejected
    p_dim = MaliciousProvider("dim")
    with pytest.raises(EmbeddingValidationError, match="Expected dimension"):
        p_dim.embed_text("test")

    # NaN rejected
    p_nan = MaliciousProvider("nan")
    with pytest.raises(EmbeddingValidationError, match="NaN"):
        p_nan.embed_text("test")

    # Infinity rejected
    p_inf = MaliciousProvider("inf")
    with pytest.raises(EmbeddingValidationError, match="infinity"):
        p_inf.embed_text("test")

    # Too few batch results rejected
    p_short = MaliciousProvider("count_short")
    with pytest.raises(EmbeddingValidationError, match="Expected 2 embeddings"):
        p_short.embed_texts(["a", "b"])

    # Too many batch results rejected
    p_long = MaliciousProvider("count_long")
    with pytest.raises(EmbeddingValidationError, match="Expected 2 embeddings"):
        p_long.embed_texts(["a", "b"])


# ============================================================
# INDEXING TESTS
# ============================================================

async def test_indexing_behavior(db_session: AsyncSession):
    from app.core.config import settings
    settings.embedding_batch_size = 2 # test batching

    course_id = uuid.uuid4()
    db_session.add(Course(id=course_id, name="Index Test"))

    source = SourceVersion(id=uuid.uuid4(), course_id=course_id, processing_status=ProcessingStatus.ready, original_filename="a", file_hash="a", mime_type="a", source_type=SourceType.pdf, storage_path="a")
    db_session.add(source)

    u1 = EvidenceUnit(id=uuid.uuid4(), course_id=course_id, source_version_id=source.id, modality=Modality.text, original_text="Searchable 1", extraction_status=ExtractionStatus.extracted)
    u2 = EvidenceUnit(id=uuid.uuid4(), course_id=course_id, source_version_id=source.id, modality=Modality.image, extraction_status=ExtractionStatus.extracted, embedding=[0.0]*384, embedding_model="old")
    u3 = EvidenceUnit(id=uuid.uuid4(), course_id=course_id, source_version_id=source.id, modality=Modality.text, original_text="Searchable 3", extraction_status=ExtractionStatus.extracted)
    u4 = EvidenceUnit(id=uuid.uuid4(), course_id=course_id, source_version_id=source.id, modality=Modality.text, original_text="Searchable 4", extraction_status=ExtractionStatus.extracted)
    db_session.add_all([u1, u2, u3, u4])
    await db_session.commit()

    import os
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"

    # First indexing run
    res = await index_evidence_units(db_session, course_id)
    assert res["total_evidence"] == 4
    assert res["searchable_evidence"] == 3
    assert res["embedded_count"] == 3
    assert res["skipped_no_text_count"] == 1
    assert res["skipped_unchanged_count"] == 0

    await db_session.refresh(u2)
    assert u2.embedding is None # Stale metadata cleared

    # Second indexing run (unchanged)
    res2 = await index_evidence_units(db_session, course_id)
    assert res2["embedded_count"] == 0
    assert res2["skipped_unchanged_count"] == 3
    assert res2["skipped_no_text_count"] == 1
    assert res2["total_evidence"] == 4

    # Changed searchable content
    u1.original_text = "Searchable changed"
    await db_session.commit()
    res3 = await index_evidence_units(db_session, course_id)
    assert res3["embedded_count"] == 1
    assert res3["skipped_unchanged_count"] == 2

    # Changed model
    await db_session.refresh(u1)
    u1.embedding_model = "old-model"
    await db_session.commit()
    res4 = await index_evidence_units(db_session, course_id)
    assert res4["embedded_count"] == 1

# ============================================================
# RRF TESTS
# ============================================================

def test_rrf_logic():
    from app.services.retriever import reciprocal_rank_fusion
    class DummyItem:
        def __init__(self, uid):
            self.id = uid

    v_res = [{"item": DummyItem("A"), "distance": 0.1}, {"item": DummyItem("B"), "distance": 0.5}]
    k_res = [{"item": DummyItem("B"), "score": 0.5}, {"item": DummyItem("C"), "score": 0.1}]

    fused = reciprocal_rank_fusion(v_res, k_res)
    assert len(fused) == 3

    # B appears in both: vector rank 2, keyword rank 1 -> 1/(60+2) + 1/(60+1)
    # A vector rank 1 -> 1/61
    # C keyword rank 2 -> 1/62

    # Check that sorting works correctly
    assert fused[0]["item"].id == "B"
    assert "fused_score" in fused[0]
    assert fused[0]["dense_rank"] == 2
    assert fused[0]["lexical_rank"] == 1
    assert fused[0]["dense_distance"] == 0.5
    assert fused[0]["lexical_score"] == 0.5

    assert fused[1]["item"].id == "A"
    assert fused[1]["dense_rank"] == 1
    assert fused[1]["lexical_rank"] is None

    assert fused[2]["item"].id == "C"
    assert fused[2]["dense_rank"] is None
    assert fused[2]["lexical_rank"] == 2

    # Weights checking
    fused_weighted = reciprocal_rank_fusion(v_res, k_res, dense_weight=2.0, lexical_weight=0.0)
    assert fused_weighted[0]["item"].id == "A" # A (1/61 * 2) wins heavily


# ============================================================
# QUERY BOUNDARY TESTS
# ============================================================
def test_retrieval_query_boundary():
    backend = get_retrieval_backend(force_fake=True)
    assert isinstance(backend, FakeRetrievalBackend)
    # The actual integration is tested in the API test below

# ============================================================
# API AND RETRIEVAL CONTRACT TESTS
# ============================================================

async def test_search_api_and_contract(client: AsyncClient, db_session: AsyncSession):
    import os
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"

    course_id = uuid.uuid4()
    db_session.add(Course(id=course_id, name="API Test"))

    source = SourceVersion(
        id=uuid.uuid4(), course_id=course_id, original_filename="test.txt", file_hash="c",
        mime_type="text/plain", source_type=SourceType.pdf, storage_path="c", processing_status=ProcessingStatus.ready
    )
    db_session.add(source)

    unit = EvidenceUnit(
        id=uuid.uuid4(), course_id=course_id, source_version_id=source.id, modality=Modality.text,
        original_text="Endpoint testing relies on strong coverage.", extraction_status=ExtractionStatus.extracted,
        location_metadata={"page": 1}
    )
    db_session.add(unit)
    await db_session.commit()
    await index_evidence_units(db_session, course_id)

    # 1. Nonexistent course indexing -> 404
    resp = await client.post(f"/courses/{uuid.uuid4()}/retrieval/index")
    assert resp.status_code == 404

    # 2. Nonexistent course search -> 404
    resp = await client.post(f"/courses/{uuid.uuid4()}/retrieval/search", json={"query": "test"})
    assert resp.status_code == 404

    # 3. Blank query rejected
    resp = await client.post(f"/courses/{course_id}/retrieval/search", json={"query": "   \n"})
    assert resp.status_code == 422 # Pydantic validation

    # 4. top_k=0 rejected
    resp = await client.post(f"/courses/{course_id}/retrieval/search", json={"query": "test", "top_k": 0})
    assert resp.status_code == 422

    # 5. top_k=51 rejected
    resp = await client.post(f"/courses/{course_id}/retrieval/search", json={"query": "test", "top_k": 51})
    assert resp.status_code == 422

    # 6. successful indexing response
    resp = await client.post(f"/courses/{course_id}/retrieval/index")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_evidence" in data

    # 7. successful search response
    resp = await client.post(f"/courses/{course_id}/retrieval/search", json={"query": "Endpoint testing", "top_k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1
    res0 = data["results"][0]

    # Flattened schema
    assert res0["original_text"] == "Endpoint testing relies on strong coverage."
    assert res0["source_filename"] == "test.txt"
    assert res0["evidence_unit_id"] == str(unit.id)
    assert res0["course_id"] == str(course_id)
    assert res0["source_version_id"] == str(source.id)

    assert "fused_score" in res0
    assert "dense_rank" in res0
    assert "lexical_rank" in res0

    # Location metadata preserved exactly
    assert res0["location_metadata"] == {"page": 1}

    # 8. Modality filter
    resp = await client.post(f"/courses/{course_id}/retrieval/search", json={"query": "testing", "modalities": ["image"]})
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 0
