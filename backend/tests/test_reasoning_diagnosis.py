"""Phase 6 strict input/provider contracts and shared, source-backed fixtures."""

import json
import uuid

import pytest
from pydantic import ValidationError

from app.models import AssessmentAttempt, AssessmentQuestion, Concept, Course, EvidenceUnit, SourceVersion
from app.schemas.reasoning_diagnosis import DiagnosisCreate, DiagnosisDraft, DiagnosisVerification, ProbeAttemptCreate
from app.services.citation_grounding import validate_and_build_citation
from app.services.llm_provider import InvalidLLMResponseError
from app.services.reasoning_diagnosis import parse_response
from tests.test_api_assessment import SequentialFakeLLMProvider

STEPS = ["P1 has run for 5 units.", "P1 has 3 units remaining.", "P2 has burst 4.", "4 is less than the original 8, so P2 preempts."]


async def seed(db):
    course = Course(id=uuid.uuid4(), name="Scheduling")
    concept = Concept(id=uuid.uuid4(), course=course, name="Shortest remaining time")
    source = SourceVersion(id=uuid.uuid4(), course=course, course_id=course.id, original_filename="scheduling.pdf",
        file_hash="a"*64, mime_type="application/pdf", source_type="pdf",
        storage_path="/private/never-expose.pdf", processing_status="ready")
    evidence = [EvidenceUnit(id=uuid.uuid4(), course=course, course_id=course.id, source_version=source, source_version_id=source.id,
        modality="text", extraction_status="extracted",
        original_text="Shortest remaining time compares remaining execution times, not original burst times. A new process preempts only if its remaining time is shorter.",
        location_metadata={"page_index":i, "page_number":i+1}) for i in range(2)]
    snapshots = [validate_and_build_citation(e, source, course.id).citation.model_dump(mode="json") for e in evidence]
    question = AssessmentQuestion(id=uuid.uuid4(), course=course, concepts=[concept],
        question_type="multiple_choice", difficulty="medium", question_text="P1 burst 8 has run 5 units. P2 burst 4 arrives. Which runs under SRTF?",
        options=["P1", "P2", "Both", "Neither"], correct_option_index=0,
        explanation="P1 has 3 remaining, fewer than P2's 4.",
        evidence_unit_ids=[str(e.id) for e in evidence], citation_snapshots=snapshots, verification_status="verified")
    attempt = AssessmentAttempt(id=uuid.uuid4(), course=course, question=question,
        learner_id=uuid.uuid4(), selected_option_index=1, is_correct=False)
    db.add_all([course, source, *evidence, question, attempt])
    await db.commit()
    return course, concept, evidence, question, attempt


def payloads(concept, evidence):
    draft = dict(outcome="hypothesis", observed_reasoning="The learner computed 3 remaining, then compared 4 with the original 8.",
        first_break_step_index=3, first_break_excerpt=STEPS[3],
        hypothesis_text="The learner may be comparing original burst time instead of remaining time.",
        target_concept_id=str(concept.id), evidence_unit_ids=[str(evidence[0].id)],
        probe=dict(question_text="A has burst 10 and has run 7 units; B with burst 5 arrives. Which process runs under SRTF?",
            options=["A, with 3 remaining", "B, because 5 is less than 10", "Both", "Neither"],
            correct_option_index=0, explanation="Compare A's remaining 3 with B's 5; A continues.",
            evidence_unit_ids=[str(evidence[0].id)]))
    verdict = dict(verdict="verified", first_break_supported=True, hypothesis_supported=True,
        target_allowed=True, probe_isolates_hypothesis=True, probe_answer_supported=True,
        probe_is_fresh=True, public_content_safe=True, evidence_unit_ids=[str(evidence[1].id)],
        probe_evidence_unit_ids=[str(evidence[1].id)])
    return draft, verdict


def provider_for(monkeypatch, draft, verdict):
    provider = SequentialFakeLLMProvider([json.dumps(draft), json.dumps(verdict)])
    monkeypatch.setattr("app.services.reasoning_diagnosis.get_llm_provider", lambda: provider)
    return provider


@pytest.mark.parametrize("body", [
    {}, {"reasoning_text":"  "}, {"reasoning_steps":[" "]},
    {"reasoning_text":"x"*8001}, {"reasoning_steps":["x"]*21},
    {"reasoning_steps":["x"*1001]}, {"reasoning_text":"x"*8000,"reasoning_steps":["y"*1000]*5},
    {"reasoning_text":"test", "target_concept_id":str(uuid.uuid4())},
])
def test_input_bounds(body):
    with pytest.raises(ValidationError):
        DiagnosisCreate(attempt_id=uuid.uuid4(), **body)


@pytest.mark.parametrize("body", [{"reasoning_text":"My explanation"}, {"reasoning_steps":STEPS}, {"reasoning_text":"  ", "reasoning_steps":STEPS}])
def test_input_accepts_either_form_and_preserves_original(body):
    result = DiagnosisCreate(attempt_id=uuid.uuid4(), **body)
    for key,value in body.items():
        assert getattr(result,key) == value


@pytest.mark.parametrize("value", [-1,4,True,1.0,"1"])
def test_probe_index_strict(value):
    with pytest.raises(ValidationError):
        ProbeAttemptCreate(selected_option_index=value)


@pytest.mark.parametrize("raw", ["", "not JSON", "{}", "[]", "```json\n{}\n```", "x"*32001])
def test_invalid_response_convention(raw):
    with pytest.raises(InvalidLLMResponseError):
        parse_response(raw, DiagnosisDraft)


@pytest.mark.parametrize("schema,body", [
    (DiagnosisDraft, {"outcome":"confirmed","observed_reasoning":"wrong"}),
    (DiagnosisDraft, {"outcome":"hypothesis","observed_reasoning":"wrong"}),
    (DiagnosisDraft, {"outcome":"no_clear_break","observed_reasoning":"Observed", "page_number":42}),
    (DiagnosisDraft, {"outcome":"no_clear_break","observed_reasoning":"Observed", "target_concept_id":"not-a-uuid"}),
    (DiagnosisVerification, {"verdict":"verified"}),
])
def test_provider_schema_forbids_unsafe_shapes(schema, body):
    with pytest.raises(InvalidLLMResponseError):
        parse_response(json.dumps(body), schema)
