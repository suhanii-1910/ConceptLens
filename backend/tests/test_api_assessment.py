"""API endpoint integration tests for Phase 4 Grounded Assessment System."""

import json
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    AssessmentAttempt,
    AssessmentQuestion,
)
from app.models.course import Course
from app.models.evidence_unit import EvidenceUnit, ExtractionStatus, Modality
from app.models.source_version import ProcessingStatus, SourceType, SourceVersion
from app.schemas.assessment import (
    AssessmentDifficulty,
    AssessmentGenerationStatus,
    AssessmentQuestionType,
    AssessmentQuestionVerificationStatus,
)
from app.schemas.retrieval import Citation
from app.services.indexing import index_evidence_units
from app.services.llm_provider import (
    LLMConfigurationError,
    LLMProvider,
    LLMProviderError,
)

pytestmark = pytest.mark.asyncio


class SequentialFakeLLMProvider(LLMProvider):
    """Test LLM provider that returns sequential scripted responses."""

    def __init__(self, responses=None, error: Exception = None):
        self.responses = list(responses or [])
        self.error = error
        self.call_count = 0
        self.prompts = []

    async def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.call_count += 1
        self.prompts.append({"system": system_prompt, "user": user_prompt})
        if self.error:
            raise self.error
        if not self.responses:
            raise RuntimeError("SequentialFakeLLMProvider ran out of mock responses.")
        return self.responses.pop(0)


async def _create_course(db: AsyncSession, name: str = "Test Course") -> Course:
    course = Course(id=uuid.uuid4(), name=name)
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


async def _seed_course_with_indexed_evidence(
    db: AsyncSession,
    text: str = "Round Robin CPU scheduling allocates a fixed time quantum to each ready process.",
) -> tuple[Course, EvidenceUnit]:
    course = await _create_course(db, "Operating Systems")
    sv = SourceVersion(
        id=uuid.uuid4(),
        course_id=course.id,
        original_filename="os_notes.pdf",
        file_hash="hash_os_1",
        mime_type="application/pdf",
        source_type=SourceType.pdf,
        storage_path="/private/os_notes.pdf",
        processing_status=ProcessingStatus.ready,
    )
    db.add(sv)

    eu = EvidenceUnit(
        id=uuid.uuid4(),
        course_id=course.id,
        source_version_id=sv.id,
        modality=Modality.text,
        original_text=text,
        extraction_status=ExtractionStatus.extracted,
        location_metadata={"page_index": 0, "page_number": 1},
        embedding=[0.05] * 384,
    )
    db.add(eu)
    await db.commit()
    await index_evidence_units(db, course.id)
    return course, eu


async def _seed_verified_question(
    db: AsyncSession,
    course_id: uuid.UUID,
    *,
    correct_option_index: int = 2,
    verification_status: AssessmentQuestionVerificationStatus = AssessmentQuestionVerificationStatus.verified,
) -> AssessmentQuestion:
    eu_id = uuid.uuid4()
    sv_id = uuid.uuid4()
    citation = Citation(
        evidence_unit_id=eu_id,
        course_id=course_id,
        source_version_id=sv_id,
        source_filename="os_notes.pdf",
        source_type=SourceType.pdf,
        modality=Modality.text,
        locator={"page_index": 0, "page_number": 1},
        location_metadata={"page_index": 0, "page_number": 1},
        locator_label="os_notes.pdf · p. 1",
    )
    q = AssessmentQuestion(
        id=uuid.uuid4(),
        course_id=course_id,
        question_type=AssessmentQuestionType.multiple_choice,
        difficulty=AssessmentDifficulty.medium,
        question_text="Which CPU scheduling algorithm uses time quanta?",
        options=["First-Come First-Served", "Shortest Job First", "Round Robin", "Priority Scheduling"],
        correct_option_index=correct_option_index,
        explanation="Round Robin uses preemption based on a static time quantum.",
        evidence_unit_ids=[str(eu_id)],
        citation_snapshots=[citation.model_dump(mode="json")],
        verification_status=verification_status,
        generation_focus="CPU Scheduling",
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return q


# ===========================================================================
# 1. POST /courses/{course_id}/assessments/generate
# ===========================================================================

async def test_api_generate_course_not_found(client: AsyncClient):
    random_id = uuid.uuid4()
    resp = await client.post(
        f"/courses/{random_id}/assessments/generate",
        json={"focus": "CPU scheduling", "count": 2},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


async def test_api_generate_request_validation(client: AsyncClient, db_session: AsyncSession):
    course = await _create_course(db_session)

    # Empty focus
    resp = await client.post(
        f"/courses/{course.id}/assessments/generate",
        json={"focus": "   ", "count": 2},
    )
    assert resp.status_code == 422

    # Count out of bounds (< 1)
    resp = await client.post(
        f"/courses/{course.id}/assessments/generate",
        json={"focus": "Valid focus", "count": 0},
    )
    assert resp.status_code == 422

    # Count out of bounds (> 5)
    resp = await client.post(
        f"/courses/{course.id}/assessments/generate",
        json={"focus": "Valid focus", "count": 6},
    )
    assert resp.status_code == 422

    # Count boolean
    resp = await client.post(
        f"/courses/{course.id}/assessments/generate",
        json={"focus": "Valid focus", "count": True},
    )
    assert resp.status_code == 422

    # top_k out of bounds
    resp = await client.post(
        f"/courses/{course.id}/assessments/generate",
        json={"focus": "Valid focus", "count": 2, "top_k": 25},
    )
    assert resp.status_code == 422


async def test_api_generate_declined_unsupported_evidence_zero_provider_calls(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    course = await _create_course(db_session, "Empty Course")
    provider = SequentialFakeLLMProvider(error=RuntimeError("Provider should NOT be called!"))
    monkeypatch.setattr("app.services.assessment_generation.get_llm_provider", lambda: provider)

    resp = await client.post(
        f"/courses/{course.id}/assessments/generate",
        json={"focus": "Quantum computing", "count": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == AssessmentGenerationStatus.declined.value
    assert data["questions"] == []
    assert data["decline_message"] is not None
    assert provider.call_count == 0


async def test_api_generate_success_hides_answer_key_and_explanation(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    course, eu = await _seed_course_with_indexed_evidence(db_session)

    gen_payload = json.dumps({
        "questions": [
            {
                "question_text": "What does Round Robin allocate to each process?",
                "options": ["Fixed time quantum", "Priority token", "Thread lock", "Semaphore"],
                "correct_option_index": 0,
                "explanation": "Round robin allocates a fixed time quantum.",
                "evidence_unit_ids": [str(eu.id)],
            }
        ]
    })
    ver_payload = json.dumps({
        "verifications": [
            {
                "question_index": 0,
                "verdict": "verified",
                "evidence_unit_ids": [str(eu.id)],
            }
        ]
    })

    provider = SequentialFakeLLMProvider([gen_payload, ver_payload])
    monkeypatch.setattr("app.services.assessment_generation.get_llm_provider", lambda: provider)

    resp = await client.post(
        f"/courses/{course.id}/assessments/generate",
        json={"focus": "Round Robin CPU scheduling", "count": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == AssessmentGenerationStatus.generated.value
    assert len(data["questions"]) == 1
    assert provider.call_count == 2  # 1 generator + 1 verifier call

    q = data["questions"][0]
    # Invariant: public representation hides answer key and explanation
    assert "correct_option_index" not in q
    assert "explanation" not in q
    assert q["question_text"] == "What does Round Robin allocate to each process?"
    assert len(q["options"]) == 4
    assert len(q["citations"]) == 1
    # Check citation snapshot does not leak storage_path
    cit = q["citations"][0]
    assert "storage_path" not in cit
    assert "derived_path" not in cit
    assert cit["source_filename"] == "os_notes.pdf"


async def test_api_generate_no_verified_questions(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    course, eu = await _seed_course_with_indexed_evidence(db_session)

    gen_payload = json.dumps({
        "questions": [
            {
                "question_text": "Hallucinated claim?",
                "options": ["A", "B", "C", "D"],
                "correct_option_index": 0,
                "explanation": "No basis.",
                "evidence_unit_ids": [str(eu.id)],
            }
        ]
    })
    ver_payload = json.dumps({
        "verifications": [
            {
                "question_index": 0,
                "verdict": "rejected",
                "evidence_unit_ids": [],
            }
        ]
    })

    provider = SequentialFakeLLMProvider([gen_payload, ver_payload])
    monkeypatch.setattr("app.services.assessment_generation.get_llm_provider", lambda: provider)

    resp = await client.post(
        f"/courses/{course.id}/assessments/generate",
        json={"focus": "Round Robin CPU scheduling", "count": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == AssessmentGenerationStatus.no_verified_questions.value
    assert data["questions"] == []
    assert data["generated_count"] == 0
    assert data["rejected_count"] == 1


async def test_api_generate_provider_configuration_error(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    course, eu = await _seed_course_with_indexed_evidence(db_session)
    provider = SequentialFakeLLMProvider(error=LLMConfigurationError("API key not set"))
    monkeypatch.setattr("app.services.assessment_generation.get_llm_provider", lambda: provider)

    resp = await client.post(
        f"/courses/{course.id}/assessments/generate",
        json={"focus": "Round Robin CPU scheduling", "count": 1},
    )
    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"].lower()


async def test_api_generate_provider_runtime_error(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    course, eu = await _seed_course_with_indexed_evidence(db_session)
    provider = SequentialFakeLLMProvider(error=LLMProviderError("Provider 500 error"))
    monkeypatch.setattr("app.services.assessment_generation.get_llm_provider", lambda: provider)

    resp = await client.post(
        f"/courses/{course.id}/assessments/generate",
        json={"focus": "Round Robin CPU scheduling", "count": 1},
    )
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


async def test_api_generate_invalid_llm_response_error(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    course, eu = await _seed_course_with_indexed_evidence(db_session)
    provider = SequentialFakeLLMProvider(["Invalid JSON from generator"])
    monkeypatch.setattr("app.services.assessment_generation.get_llm_provider", lambda: provider)

    resp = await client.post(
        f"/courses/{course.id}/assessments/generate",
        json={"focus": "Round Robin CPU scheduling", "count": 1},
    )
    assert resp.status_code == 502
    assert "invalid response" in resp.json()["detail"].lower()


# ===========================================================================
# 2. GET /courses/{course_id}/assessments/questions/{question_id}
# ===========================================================================

async def test_api_get_question_success_hides_answer_and_explanation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    course = await _create_course(db_session)
    q = await _seed_verified_question(db_session, course.id, correct_option_index=2)

    resp = await client.get(f"/courses/{course.id}/assessments/questions/{q.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["id"] == str(q.id)
    assert data["course_id"] == str(course.id)
    assert data["question_text"] == q.question_text
    assert data["options"] == q.options
    assert len(data["citations"]) == 1

    # Invariant: answer key and explanation must NEVER be in public get question response
    assert "correct_option_index" not in data
    assert "explanation" not in data


async def test_api_get_question_not_found(client: AsyncClient, db_session: AsyncSession):
    course = await _create_course(db_session)
    random_q_id = uuid.uuid4()

    resp = await client.get(f"/courses/{course.id}/assessments/questions/{random_q_id}")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


async def test_api_get_question_from_different_course_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
):
    course1 = await _create_course(db_session, "Course 1")
    course2 = await _create_course(db_session, "Course 2")
    q = await _seed_verified_question(db_session, course1.id)

    # Request question with course2 id
    resp = await client.get(f"/courses/{course2.id}/assessments/questions/{q.id}")
    assert resp.status_code == 404


async def test_api_get_unverified_question_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
):
    course = await _create_course(db_session)
    q_rejected = await _seed_verified_question(
        db_session,
        course.id,
        verification_status=AssessmentQuestionVerificationStatus.rejected,
    )

    resp = await client.get(f"/courses/{course.id}/assessments/questions/{q_rejected.id}")
    assert resp.status_code == 404


# ===========================================================================
# 3. POST /courses/{course_id}/assessments/questions/{question_id}/attempts
# ===========================================================================

async def test_api_submit_attempt_correct(client: AsyncClient, db_session: AsyncSession):
    course = await _create_course(db_session)
    q = await _seed_verified_question(db_session, course.id, correct_option_index=2)
    learner_id = uuid.uuid4()

    resp = await client.post(
        f"/courses/{course.id}/assessments/questions/{q.id}/attempts",
        json={"learner_id": str(learner_id), "selected_option_index": 2},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["question_id"] == str(q.id)
    assert data["course_id"] == str(course.id)
    assert data["learner_id"] == str(learner_id)
    assert data["selected_option_index"] == 2
    assert data["is_correct"] is True
    assert data["correct_option_index"] == 2
    assert data["correct_option_text"] == "Round Robin"
    assert data["explanation"] == q.explanation
    assert len(data["citations"]) == 1


async def test_api_submit_attempt_incorrect(client: AsyncClient, db_session: AsyncSession):
    course = await _create_course(db_session)
    q = await _seed_verified_question(db_session, course.id, correct_option_index=2)
    learner_id = uuid.uuid4()

    resp = await client.post(
        f"/courses/{course.id}/assessments/questions/{q.id}/attempts",
        json={"learner_id": str(learner_id), "selected_option_index": 0},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["selected_option_index"] == 0
    assert data["is_correct"] is False
    assert data["correct_option_index"] == 2
    assert data["correct_option_text"] == "Round Robin"
    assert data["explanation"] == q.explanation


async def test_api_submit_attempt_immutability_appends_new_row(
    client: AsyncClient,
    db_session: AsyncSession,
):
    course = await _create_course(db_session)
    q = await _seed_verified_question(db_session, course.id, correct_option_index=2)
    learner_id = uuid.uuid4()

    # Attempt 1: incorrect
    resp1 = await client.post(
        f"/courses/{course.id}/assessments/questions/{q.id}/attempts",
        json={"learner_id": str(learner_id), "selected_option_index": 0},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()

    # Attempt 2: correct
    resp2 = await client.post(
        f"/courses/{course.id}/assessments/questions/{q.id}/attempts",
        json={"learner_id": str(learner_id), "selected_option_index": 2},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data1["attempt_id"] != data2["attempt_id"]

    # Verify database contains both distinct immutable records
    stmt = select(AssessmentAttempt).where(AssessmentAttempt.question_id == q.id)
    attempts = (await db_session.scalars(stmt)).all()
    assert len(attempts) == 2

    # Verify attempt 1 was not mutated by attempt 2
    db_att1 = next(a for a in attempts if str(a.id) == data1["attempt_id"])
    assert db_att1.selected_option_index == 0
    assert db_att1.is_correct is False

    db_att2 = next(a for a in attempts if str(a.id) == data2["attempt_id"])
    assert db_att2.selected_option_index == 2
    assert db_att2.is_correct is True


async def test_api_submit_attempt_validation_option_index(
    client: AsyncClient,
    db_session: AsyncSession,
):
    course = await _create_course(db_session)
    q = await _seed_verified_question(db_session, course.id)
    learner_id = uuid.uuid4()

    # Negative option index
    resp = await client.post(
        f"/courses/{course.id}/assessments/questions/{q.id}/attempts",
        json={"learner_id": str(learner_id), "selected_option_index": -1},
    )
    assert resp.status_code == 422

    # Out of bounds (> 3)
    resp = await client.post(
        f"/courses/{course.id}/assessments/questions/{q.id}/attempts",
        json={"learner_id": str(learner_id), "selected_option_index": 4},
    )
    assert resp.status_code == 422

    # Boolean value
    resp = await client.post(
        f"/courses/{course.id}/assessments/questions/{q.id}/attempts",
        json={"learner_id": str(learner_id), "selected_option_index": True},
    )
    assert resp.status_code == 422


async def test_api_submit_attempt_not_found_handling(
    client: AsyncClient,
    db_session: AsyncSession,
):
    course = await _create_course(db_session)
    q = await _seed_verified_question(db_session, course.id)
    other_course = await _create_course(db_session, "Other Course")
    learner_id = uuid.uuid4()

    # Missing question
    resp = await client.post(
        f"/courses/{course.id}/assessments/questions/{uuid.uuid4()}/attempts",
        json={"learner_id": str(learner_id), "selected_option_index": 0},
    )
    assert resp.status_code == 404

    # Missing course
    resp = await client.post(
        f"/courses/{uuid.uuid4()}/assessments/questions/{q.id}/attempts",
        json={"learner_id": str(learner_id), "selected_option_index": 0},
    )
    assert resp.status_code == 404

    # Question belongs to course, but requested through other_course
    resp = await client.post(
        f"/courses/{other_course.id}/assessments/questions/{q.id}/attempts",
        json={"learner_id": str(learner_id), "selected_option_index": 0},
    )
    assert resp.status_code == 404
