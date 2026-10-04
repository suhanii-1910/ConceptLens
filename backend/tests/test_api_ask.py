"""Phase 3 API integration tests: POST /courses/{course_id}/ask."""

import json
import os
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.evidence_unit import EvidenceUnit, ExtractionStatus, Modality
from app.models.source_version import ProcessingStatus, SourceType, SourceVersion
from app.schemas.ask import AskMode, AskStatus
from app.services.indexing import index_evidence_units
from app.services.llm_provider import (
    LLMConfigurationError,
    LLMProviderError,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _setup_test_env():
    os.environ["TESTING"] = "1"
    os.environ["USE_FAKE_EMBEDDING"] = "1"


class RecordingFakeLLMProvider:
    """Deterministic fake provider for test code only."""

    def __init__(self, response_text: str = "", error: Exception | None = None):
        self.response_text = response_text
        self.error = error
        self.call_count = 0
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None

    async def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.call_count += 1
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        if self.error is not None:
            raise self.error
        return self.response_text


async def _seed_course(db: AsyncSession, name: str = "Operating Systems") -> uuid.UUID:
    c_id = uuid.uuid4()
    db.add(Course(id=c_id, name=name))
    await db.commit()
    return c_id


async def _seed_source_version(
    db: AsyncSession,
    course_id: uuid.UUID,
    *,
    filename: str = "os_notes.pdf",
    source_type: SourceType = SourceType.pdf,
    storage_path: str = "/private/storage/secret/source.pdf",
    processing_status: ProcessingStatus = ProcessingStatus.ready,
) -> uuid.UUID:
    sv_id = uuid.uuid4()
    mime = "application/pdf"
    if source_type == SourceType.pptx:
        mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif source_type == SourceType.video:
        mime = "video/mp4"
    db.add(
        SourceVersion(
            id=sv_id,
            course_id=course_id,
            original_filename=filename,
            file_hash=str(uuid.uuid4()),
            mime_type=mime,
            source_type=source_type,
            storage_path=storage_path,
            processing_status=processing_status,
        )
    )
    await db.commit()
    return sv_id


async def _seed_evidence_unit(
    db: AsyncSession,
    course_id: uuid.UUID,
    sv_id: uuid.UUID,
    *,
    text: str,
    location_metadata: dict,
    modality: Modality = Modality.text,
    extracted_description: str | None = None,
) -> uuid.UUID:
    eu_id = uuid.uuid4()
    db.add(
        EvidenceUnit(
            id=eu_id,
            course_id=course_id,
            source_version_id=sv_id,
            modality=modality,
            original_text=text,
            extracted_description=extracted_description,
            extraction_status=ExtractionStatus.extracted,
            location_metadata=location_metadata,
            embedding=[0.1] * 384,
        )
    )
    await db.commit()
    return eu_id


# ---------------------------------------------------------------------------
# 1. SUPPORTED — JUST ANSWER
# ---------------------------------------------------------------------------
async def test_api_ask_supported_just_answer(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)
    sv_id = await _seed_source_version(db_session, c_id)
    eu_id = await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="Round Robin CPU scheduling assigns each ready process a fixed time quantum.",
        location_metadata={"page_index": 0, "page_number": 1, "printed_page_label": "1"},
    )
    await index_evidence_units(db_session, c_id)

    model_json = json.dumps({
        "blocks": [
            {
                "text": "Round Robin CPU scheduling allocates a fixed time quantum to each ready process.",
                "evidence_unit_ids": [str(eu_id)],
            }
        ],
        "next_question": None,
    })
    fake_provider = RecordingFakeLLMProvider(response_text=model_json)
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "What does Round Robin scheduling assign?", "mode": "just_answer"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "answered"
    assert data["mode"] == "just_answer"
    assert data["answer"] is not None
    assert len(data["answer"].strip()) > 0
    assert len(data["blocks"]) > 0
    for block in data["blocks"]:
        assert len(block["citations"]) >= 1
    assert data["next_question"] is None
    assert data["decline_message"] is None
    assert data["used_evidence_unit_ids"] == [str(eu_id)]
    assert fake_provider.call_count == 1


# ---------------------------------------------------------------------------
# 2. SUPPORTED — EXPLAIN
# ---------------------------------------------------------------------------
async def test_api_ask_supported_explain(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)
    sv_id = await _seed_source_version(db_session, c_id)
    eu_id = await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="Virtual memory uses paging to map virtual addresses to physical page frames.",
        location_metadata={"page_index": 1, "page_number": 2},
    )
    await index_evidence_units(db_session, c_id)

    model_json = json.dumps({
        "blocks": [
            {
                "text": "Virtual memory provides an abstraction using paging.",
                "evidence_unit_ids": [str(eu_id)],
            },
            {
                "text": "Virtual addresses are mapped to physical frames.",
                "evidence_unit_ids": [str(eu_id)],
            },
        ],
        "next_question": None,
    })
    fake_provider = RecordingFakeLLMProvider(response_text=model_json)
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "Explain virtual memory paging", "mode": "explain"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "answered"
    assert data["mode"] == "explain"
    assert len(data["blocks"]) == 2
    assert all(len(b["citations"]) >= 1 for b in data["blocks"])
    assert data["next_question"] is None
    assert fake_provider.call_count == 1


# ---------------------------------------------------------------------------
# 3. SUPPORTED — GUIDE
# ---------------------------------------------------------------------------
async def test_api_ask_supported_guide(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)
    sv_id = await _seed_source_version(db_session, c_id)
    eu_id = await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="A mutex provides mutual exclusion by allowing only one thread to lock it at a time.",
        location_metadata={"page_index": 2, "page_number": 3},
    )
    await index_evidence_units(db_session, c_id)

    model_json = json.dumps({
        "blocks": [
            {
                "text": "Notice how shared data access is restricted to prevent race conditions.",
                "evidence_unit_ids": [str(eu_id)],
            }
        ],
        "next_question": "What happens when a second thread attempts to acquire the lock?",
    })
    fake_provider = RecordingFakeLLMProvider(response_text=model_json)
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "How does mutual exclusion work?", "mode": "guide"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "answered"
    assert data["mode"] == "guide"
    assert len(data["blocks"]) >= 1
    assert data["next_question"] == "What happens when a second thread attempts to acquire the lock?"
    assert fake_provider.call_count == 1


# ---------------------------------------------------------------------------
# 4. UNSUPPORTED DECLINE
# ---------------------------------------------------------------------------
async def test_api_ask_unsupported_decline(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session, name="Empty Course")
    fake_provider = RecordingFakeLLMProvider(error=RuntimeError("Provider must never be called!"))
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "What is photosynthesis?", "mode": "explain"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "declined"
    assert data["answer"] is None
    assert data["blocks"] == []
    assert data["next_question"] is None
    assert data["used_evidence_unit_ids"] == []
    assert data["decline_message"] is not None
    assert "couldn't find enough relevant support" in data["decline_message"]
    assert data["evidence_boundary"]["status"] == "unsupported"
    assert fake_provider.call_count == 0


# ---------------------------------------------------------------------------
# 5. INSUFFICIENT_EVIDENCE DECLINE
# ---------------------------------------------------------------------------
async def test_api_ask_insufficient_evidence_decline(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)
    sv_id = await _seed_source_version(db_session, c_id)
    # Strongly relevant text but invalid citation provenance (empty location_metadata for PDF)
    await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="Deadlock prevention invalidates one of the four Coffman conditions.",
        location_metadata={},
    )
    await index_evidence_units(db_session, c_id)

    fake_provider = RecordingFakeLLMProvider(error=RuntimeError("Provider must never be called!"))
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "How is deadlock prevented?", "mode": "explain"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "declined"
    assert data["answer"] is None
    assert data["blocks"] == []
    assert data["evidence_boundary"]["status"] == "insufficient_evidence"
    assert data["evidence_boundary"]["relevant_candidate_count"] >= 1
    assert data["evidence_boundary"]["usable_candidate_count"] == 0
    assert "found related material, but not enough grounded evidence" in data["decline_message"]
    assert fake_provider.call_count == 0


# ---------------------------------------------------------------------------
# 6. NONEXISTENT COURSE
# ---------------------------------------------------------------------------
async def test_api_ask_nonexistent_course(client: AsyncClient):
    bad_id = uuid.uuid4()
    resp = await client.post(
        f"/courses/{bad_id}/ask",
        json={"question": "What is CPU scheduling?", "mode": "just_answer"},
    )
    assert resp.status_code == 404
    assert resp.status_code != 500


# ---------------------------------------------------------------------------
# 7. BLANK QUESTION
# ---------------------------------------------------------------------------
async def test_api_ask_blank_question(client: AsyncClient, db_session: AsyncSession):
    c_id = await _seed_course(db_session)
    resp1 = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "   ", "mode": "explain"},
    )
    assert resp1.status_code == 422

    resp2 = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "", "mode": "explain"},
    )
    assert resp2.status_code == 422


# ---------------------------------------------------------------------------
# 8. INVALID ASK MODE
# ---------------------------------------------------------------------------
async def test_api_ask_invalid_ask_mode(client: AsyncClient, db_session: AsyncSession):
    c_id = await _seed_course(db_session)
    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "What is CPU scheduling?", "mode": "chat_mode"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 9. top_k = 0
# ---------------------------------------------------------------------------
async def test_api_ask_top_k_zero(client: AsyncClient, db_session: AsyncSession):
    c_id = await _seed_course(db_session)
    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "What is CPU scheduling?", "top_k": 0},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 10. top_k > 20
# ---------------------------------------------------------------------------
async def test_api_ask_top_k_greater_than_20(client: AsyncClient, db_session: AsyncSession):
    c_id = await _seed_course(db_session)
    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "What is CPU scheduling?", "top_k": 21},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 11. MALFORMED PROVIDER JSON
# ---------------------------------------------------------------------------
async def test_api_ask_malformed_provider_json(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)
    sv_id = await _seed_source_version(db_session, c_id)
    await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="Round Robin CPU scheduling allocates time quantum.",
        location_metadata={"page_index": 0, "page_number": 1},
    )
    await index_evidence_units(db_session, c_id)

    fake_provider = RecordingFakeLLMProvider(response_text="{invalid json content not parseable")
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "What is Round Robin?", "mode": "explain"},
    )
    assert resp.status_code == 502
    data = resp.json()
    assert data["detail"] == "Invalid response from answer generation."
    assert "invalid json content not parseable" not in resp.text
    assert "answer" not in data


# ---------------------------------------------------------------------------
# 12. HALLUCINATED EVIDENCE ID
# ---------------------------------------------------------------------------
async def test_api_ask_hallucinated_evidence_id(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)
    sv_id = await _seed_source_version(db_session, c_id)
    await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="Virtual memory uses paging.",
        location_metadata={"page_index": 0, "page_number": 1},
    )
    await index_evidence_units(db_session, c_id)

    hallucinated_id = uuid.uuid4()
    model_json = json.dumps({
        "blocks": [
            {
                "text": "Virtual memory maps addresses to frames.",
                "evidence_unit_ids": [str(hallucinated_id)],
            }
        ],
        "next_question": None,
    })
    fake_provider = RecordingFakeLLMProvider(response_text=model_json)
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "What is virtual memory?", "mode": "explain"},
    )
    assert resp.status_code == 502
    data = resp.json()
    assert data["detail"] == "Invalid response from answer generation."
    assert "answer" not in data


# ---------------------------------------------------------------------------
# 13. PROVIDER UNAVAILABLE
# ---------------------------------------------------------------------------
async def test_api_ask_provider_unavailable(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)
    sv_id = await _seed_source_version(db_session, c_id)
    await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="Round Robin CPU scheduling assigns a time quantum.",
        location_metadata={"page_index": 0, "page_number": 1},
    )
    await index_evidence_units(db_session, c_id)

    sensitive_error = "SECRET_UPSTREAM_NETWORK_TIMEOUT_KEY_12345"
    fake_provider = RecordingFakeLLMProvider(error=LLMProviderError(sensitive_error))
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "What is Round Robin?", "mode": "explain"},
    )
    assert resp.status_code == 503
    data = resp.json()
    assert data["detail"] == "Answer generation provider is unavailable."
    assert sensitive_error not in resp.text


# ---------------------------------------------------------------------------
# 14. MISSING PROVIDER CONFIG — SUPPORTED
# ---------------------------------------------------------------------------
async def test_api_ask_missing_provider_config_supported(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)
    sv_id = await _seed_source_version(db_session, c_id)
    await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="Round Robin CPU scheduling assigns a time quantum.",
        location_metadata={"page_index": 0, "page_number": 1},
    )
    await index_evidence_units(db_session, c_id)

    def _raise_missing_config():
        raise LLMConfigurationError("Answer generation is not configured.")

    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", _raise_missing_config)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "What is Round Robin?", "mode": "explain"},
    )
    assert resp.status_code == 503
    data = resp.json()
    assert data["detail"] == "Answer generation is not configured."


# ---------------------------------------------------------------------------
# 15. MISSING PROVIDER CONFIG — DECLINED
# ---------------------------------------------------------------------------
async def test_api_ask_missing_provider_config_declined(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session, name="Empty Course")

    def _fail_if_called():
        raise LLMConfigurationError("Should never be called on decline!")

    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", _fail_if_called)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "What is photosynthesis?", "mode": "explain"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "declined"
    assert data["answer"] is None


# ---------------------------------------------------------------------------
# 16. EXACT CITATION MAPPING
# ---------------------------------------------------------------------------
async def test_api_ask_exact_citation_mapping_pdf(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)
    sv_id = await _seed_source_version(db_session, c_id, filename="lecture1.pdf", source_type=SourceType.pdf)
    eu_id = await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="CPU scheduling algorithms include FCFS and Round Robin.",
        location_metadata={"page_index": 4, "page_number": 5, "printed_page_label": "5"},
    )
    await index_evidence_units(db_session, c_id)

    model_json = json.dumps({
        "blocks": [
            {
                "text": "FCFS and Round Robin are standard CPU scheduling algorithms.",
                "evidence_unit_ids": [str(eu_id)],
            }
        ],
        "next_question": None,
    })
    fake_provider = RecordingFakeLLMProvider(response_text=model_json)
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "CPU scheduling algorithms", "mode": "just_answer"},
    )
    assert resp.status_code == 200
    cit = resp.json()["blocks"][0]["citations"][0]
    assert cit["evidence_unit_id"] == str(eu_id)
    assert cit["source_filename"] == "lecture1.pdf"
    assert cit["locator"]["page_index"] == 4
    assert cit["locator"]["page_number"] == 5
    assert cit["locator_label"] == "lecture1.pdf · p. 5"
    assert cit["location_metadata"]["page_index"] == 4
    assert cit["location_metadata"]["page_number"] == 5


async def test_api_ask_exact_citation_mapping_pptx_transcript_frame(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)

    # PPTX
    sv_pptx = await _seed_source_version(db_session, c_id, filename="slides.pptx", source_type=SourceType.pptx)
    eu_pptx = await _seed_evidence_unit(
        db_session,
        c_id,
        sv_pptx,
        text="A semaphore has wait and signal operations.",
        location_metadata={"slide_index": 2, "slide_number": 3, "shape_index": 1},
    )

    # Video transcript
    sv_video = await _seed_source_version(db_session, c_id, filename="lecture.mp4", source_type=SourceType.video)
    eu_transcript = await _seed_evidence_unit(
        db_session,
        c_id,
        sv_video,
        text="Semaphores can be counting or binary semaphores.",
        location_metadata={
            "element_type": "transcript_segment",
            "start_seconds": 15.0,
            "end_seconds": 30.0,
            "source_duration_seconds": 100.0,
            "timestamp_source": "whisper",
        },
        modality=Modality.video,
    )

    # Video frame
    eu_frame = await _seed_evidence_unit(
        db_session,
        c_id,
        sv_video,
        text="Diagram illustrating semaphore queue mechanism.",
        extracted_description="Diagram illustrating semaphore queue mechanism.",
        location_metadata={
            "element_type": "video_frame",
            "timestamp_seconds": 45.0,
            "source_frame_index": 120,
        },
        modality=Modality.image,
    )
    await index_evidence_units(db_session, c_id)

    model_json = json.dumps({
        "blocks": [
            {
                "text": "Semaphores provide wait and signal operations.",
                "evidence_unit_ids": [str(eu_pptx)],
            },
            {
                "text": "They can be binary or counting.",
                "evidence_unit_ids": [str(eu_transcript)],
            },
            {
                "text": "The diagram displays the queue mechanism.",
                "evidence_unit_ids": [str(eu_frame)],
            },
        ],
        "next_question": None,
    })
    fake_provider = RecordingFakeLLMProvider(response_text=model_json)
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "Semaphore operations", "mode": "explain"},
    )
    assert resp.status_code == 200
    blocks = resp.json()["blocks"]

    # PPTX
    cit_pptx = blocks[0]["citations"][0]
    assert cit_pptx["evidence_unit_id"] == str(eu_pptx)
    assert cit_pptx["locator"]["slide_index"] == 2
    assert cit_pptx["locator"]["slide_number"] == 3
    assert cit_pptx["locator_label"] == "slides.pptx · slide 3"

    # Transcript
    cit_tr = blocks[1]["citations"][0]
    assert cit_tr["evidence_unit_id"] == str(eu_transcript)
    assert cit_tr["locator"]["start_seconds"] == 15.0
    assert cit_tr["locator"]["end_seconds"] == 30.0
    assert cit_tr["locator_label"] == "lecture.mp4 · 00:15–00:30"

    # Frame
    cit_fr = blocks[2]["citations"][0]
    assert cit_fr["evidence_unit_id"] == str(eu_frame)
    assert cit_fr["locator"]["timestamp_seconds"] == 45.0
    assert cit_fr["locator"]["source_frame_index"] == 120
    assert cit_fr["locator_label"] == "lecture.mp4 · 00:45"


# ---------------------------------------------------------------------------
# 17. PRIVATE PATH SAFETY
# ---------------------------------------------------------------------------
async def test_api_ask_private_path_safety(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)
    secret_storage = "/private/storage/secret/user_data/notes.pdf"
    sv_id = await _seed_source_version(
        db_session,
        c_id,
        storage_path=secret_storage,
    )
    secret_derived = "/private/storage/secret/derived/image_12345.png"
    eu_id = await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="A thread is the basic unit of CPU utilization.",
        location_metadata={
            "page_index": 0,
            "page_number": 1,
            "derived_path": secret_derived,
            "storage_path": secret_storage,
        },
    )
    await index_evidence_units(db_session, c_id)

    model_json = json.dumps({
        "blocks": [
            {
                "text": "A thread is the basic unit of CPU utilization.",
                "evidence_unit_ids": [str(eu_id)],
            }
        ],
        "next_question": None,
    })
    fake_provider = RecordingFakeLLMProvider(response_text=model_json)
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "What is a thread?", "mode": "just_answer"},
    )
    assert resp.status_code == 200
    resp_text = resp.text

    assert "derived_path" not in resp_text
    assert "storage_path" not in resp_text
    assert "/private/storage" not in resp_text
    assert secret_storage not in resp_text
    assert secret_derived not in resp_text


# ---------------------------------------------------------------------------
# 18. RESPONSE INTERNAL-SAFETY
# ---------------------------------------------------------------------------
async def test_api_ask_response_internal_safety(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)
    sv_id = await _seed_source_version(db_session, c_id)
    eu_id = await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="Context switching saves the state of the active process.",
        location_metadata={"page_index": 0, "page_number": 1},
    )
    await index_evidence_units(db_session, c_id)

    model_json = json.dumps({
        "blocks": [
            {
                "text": "Context switching saves and restores process state.",
                "evidence_unit_ids": [str(eu_id)],
            }
        ],
        "next_question": None,
    })
    fake_provider = RecordingFakeLLMProvider(response_text=model_json)
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "What is context switching?", "mode": "just_answer"},
    )
    assert resp.status_code == 200
    data = resp.json()
    resp_text = resp.text

    assert "system_prompt" not in data
    assert "user_prompt" not in data
    assert "raw_provider_response" not in data
    assert "traceback" not in resp_text.lower()
    assert "api_key" not in resp_text.lower()
    assert "authorization" not in resp_text.lower()


# ---------------------------------------------------------------------------
# 19. CROSS-COURSE SAFETY
# ---------------------------------------------------------------------------
async def test_api_ask_cross_course_safety(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    course_a = await _seed_course(db_session, name="Course A")
    course_b = await _seed_course(db_session, name="Course B")

    # Seed evidence in Course B only
    sv_b = await _seed_source_version(db_session, course_b, filename="course_b.pdf")
    eu_b = await _seed_evidence_unit(
        db_session,
        course_b,
        sv_b,
        text="B-Trees are balanced search trees optimized for disk storage systems.",
        location_metadata={"page_index": 0, "page_number": 1},
    )
    await index_evidence_units(db_session, course_b)

    fake_provider = RecordingFakeLLMProvider(error=RuntimeError("Provider must not be called!"))
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    # Ask in Course A where no B-Tree evidence exists
    resp = await client.post(
        f"/courses/{course_a}/ask",
        json={"question": "How do B-Trees work?", "mode": "explain"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "declined"
    assert data["answer"] is None
    assert str(eu_b) not in resp.text
    assert fake_provider.call_count == 0


# ---------------------------------------------------------------------------
# 20. ANSWER CONSTRUCTION
# ---------------------------------------------------------------------------
async def test_api_ask_answer_construction(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    c_id = await _seed_course(db_session)
    sv_id = await _seed_source_version(db_session, c_id)
    eu1 = await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="Concurrency allows interleaved execution of tasks.",
        location_metadata={"page_index": 0, "page_number": 1},
    )
    eu2 = await _seed_evidence_unit(
        db_session,
        c_id,
        sv_id,
        text="Parallelism executes tasks simultaneously on multiple processors.",
        location_metadata={"page_index": 1, "page_number": 2},
    )
    await index_evidence_units(db_session, c_id)

    block1_text = "Concurrency provides interleaved execution of tasks on one or more cores."
    block2_text = "Parallelism involves true simultaneous execution on multiple cores."

    # Fake provider returns only block drafts — NO top-level answer field
    model_json = json.dumps({
        "blocks": [
            {"text": block1_text, "evidence_unit_ids": [str(eu1)]},
            {"text": block2_text, "evidence_unit_ids": [str(eu2)]},
        ],
        "next_question": None,
    })
    fake_provider = RecordingFakeLLMProvider(response_text=model_json)
    monkeypatch.setattr("app.services.grounded_ask.get_llm_provider", lambda: fake_provider)

    resp = await client.post(
        f"/courses/{c_id}/ask",
        json={"question": "Compare concurrency and parallelism", "mode": "explain"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify top-level answer is constructed by joining validated block texts with double newlines
    expected_answer = f"{block1_text}\n\n{block2_text}"
    assert data["answer"] == expected_answer
    assert [b["text"] for b in data["blocks"]] == [block1_text, block2_text]
