"""Question mappings are snapshots of verifier-approved, same-course evidence."""

import json
import uuid

import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import selectinload

from app.models.assessment import AssessmentQuestion
from app.models.concept import Concept
from app.models.evidence_unit import EvidenceUnit, evidence_concept_link
from app.models.source_version import SourceVersion
from app.services.citation_grounding import validate_and_build_citation
from tests.test_api_assessment import (
    _create_course, _seed_course_with_indexed_evidence, SequentialFakeLLMProvider,
)

pytestmark = pytest.mark.asyncio


async def generate(client, monkeypatch, course, generator_ids, verifier_ids):
    generator = {"questions": [{
        "question_text": "What does Round Robin allocate?",
        "options": ["Time quantum", "Mutex", "Semaphore", "Disk block"],
        "correct_option_index": 0,
        "explanation": "Round Robin allocates a fixed time quantum.",
        "evidence_unit_ids": [str(eid) for eid in generator_ids],
    }]}
    verifier = {"verifications": [{
        "question_index": 0, "verdict": "verified",
        "evidence_unit_ids": [str(eid) for eid in verifier_ids],
    }]}
    provider = SequentialFakeLLMProvider([json.dumps(generator), json.dumps(verifier)])
    monkeypatch.setattr("app.services.assessment_generation.get_llm_provider", lambda: provider)
    response = await client.post(
        f"/courses/{course.id}/assessments/generate",
        json={"focus": "Round Robin", "count": 1},
    )
    assert response.status_code == 200, response.text
    assert provider.call_count == 2
    public = response.json()["questions"][0]
    assert "correct_option_index" not in public and "explanation" not in public
    return public, provider


async def test_published_mapping_cannot_be_reassigned(client, db_session, monkeypatch):
    course, eu = await _seed_course_with_indexed_evidence(db_session)
    concept = Concept(id=uuid.uuid4(), course_id=course.id, name="Original skill")
    db_session.add(concept)
    await db_session.flush()
    await db_session.execute(insert(evidence_concept_link).values(evidence_unit_id=eu.id, concept_id=concept.id))
    await db_session.commit()
    public, _ = await generate(client, monkeypatch, course, [eu.id], [eu.id])
    q = await db_session.scalar(select(AssessmentQuestion).options(selectinload(AssessmentQuestion.concepts)).where(AssessmentQuestion.id == uuid.UUID(public["id"])))
    q.concepts.clear()
    with pytest.raises(ValueError, match="frozen"):
        await db_session.commit()
    await db_session.rollback()


async def second_evidence(db, eu):
    extra = EvidenceUnit(
        id=uuid.uuid4(), course_id=eu.course_id, source_version_id=eu.source_version_id,
        modality=eu.modality, extraction_status=eu.extraction_status,
        original_text="Round Robin allocates a fixed time quantum to each process.",
        location_metadata={"page_index": 1, "page_number": 2}, embedding=[.05] * 384,
    )
    db.add(extra)
    await db.commit()
    return extra


@pytest.mark.parametrize("n", [0, 1, 2])
async def test_mapping_cardinality_and_deduplication(client, db_session, monkeypatch, n):
    course, eu = await _seed_course_with_indexed_evidence(db_session)
    extra = await second_evidence(db_session, eu)
    concepts = [Concept(id=uuid.uuid4(), course_id=course.id, name=f"Skill {i}") for i in range(n)]
    db_session.add_all(concepts)
    await db_session.flush()
    if concepts:
        # Each concept occurs on two approved evidence units; map it only once.
        await db_session.execute(insert(evidence_concept_link), [
            {"evidence_unit_id": e.id, "concept_id": c.id} for e in [eu, extra] for c in concepts
        ])
    await db_session.commit()
    public, _ = await generate(client, monkeypatch, course, [eu.id], [eu.id, extra.id])
    q = await db_session.scalar(select(AssessmentQuestion).options(selectinload(AssessmentQuestion.concepts)).where(AssessmentQuestion.id == uuid.UUID(public["id"])))
    assert {c.id for c in q.concepts} == {c.id for c in concepts}
    assert len(q.concepts) == n
    assert q.evidence_unit_ids == [str(eu.id), str(extra.id)]


async def test_verifier_mapping_course_filter_frozen_and_exact_citations(client, db_session, monkeypatch):
    course, generator_eu = await _seed_course_with_indexed_evidence(db_session)
    verifier_eu = await second_evidence(db_session, generator_eu)
    other = await _create_course(db_session, "Foreign course")
    generator_concept = Concept(id=uuid.uuid4(), course_id=course.id, name="Generator-only skill")
    approved_concept = Concept(id=uuid.uuid4(), course_id=course.id, name="Verified skill")
    foreign = Concept(id=uuid.uuid4(), course_id=other.id, name="Foreign skill")
    db_session.add_all([generator_concept, approved_concept, foreign])
    await db_session.flush()
    await db_session.execute(insert(evidence_concept_link), [
        {"evidence_unit_id": generator_eu.id, "concept_id": generator_concept.id},
        {"evidence_unit_id": verifier_eu.id, "concept_id": approved_concept.id},
        {"evidence_unit_id": verifier_eu.id, "concept_id": foreign.id},
    ])
    await db_session.commit()
    public, provider = await generate(client, monkeypatch, course, [generator_eu.id], [verifier_eu.id])
    qid = uuid.UUID(public["id"])
    q = await db_session.scalar(select(AssessmentQuestion).options(selectinload(AssessmentQuestion.concepts)).where(AssessmentQuestion.id == qid))
    assert [c.id for c in q.concepts] == [approved_concept.id]
    sv = await db_session.get(SourceVersion, verifier_eu.source_version_id)
    expected = validate_and_build_citation(verifier_eu, sv, course.id).citation.model_dump(mode="json")
    assert q.citation_snapshots == public["citations"] == [expected]

    # Change the live evidence annotations. The published question stays frozen.
    await db_session.execute(delete(evidence_concept_link).where(evidence_concept_link.c.evidence_unit_id == verifier_eu.id))
    await db_session.execute(insert(evidence_concept_link).values(evidence_unit_id=verifier_eu.id, concept_id=generator_concept.id))
    await db_session.commit()
    fetched = (await client.get(f"/courses/{course.id}/assessments/questions/{qid}")).json()
    assert "correct_option_index" not in fetched and "explanation" not in fetched
    assert fetched["citations"] == [expected]
    attempt = await client.post(
        f"/courses/{course.id}/assessments/questions/{qid}/attempts",
        json={"learner_id": str(uuid.uuid4()), "selected_option_index": 0},
    )
    assert attempt.status_code == 200
    assert attempt.json()["mastery_update"]["concept_id"] == str(approved_concept.id)
    assert attempt.json()["citations"] == [expected]
    assert provider.call_count == 2
