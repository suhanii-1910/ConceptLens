"""A short, resumable sample using the existing verified assessment path."""
import uuid
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.assessment import AssessmentQuestion, AssessmentAttempt
from app.models.concept import Concept
from app.models.course import Course
from app.models.diagnostic_session import DiagnosticSession
from app.models.adaptive_learning import LearningIntervention
from app.schemas.assessment import AssessmentGenerationRequest, AssessmentQuestionPublic
from app.services.assessment_generation import generate_assessments
from app.services.typed_assessment import public_format
from app.services.adaptive_learning import trusted_evidence
from app.services.llm_provider import LLMConfigurationError, LLMProviderError

async def get_diagnostic(db, course_id, learner_id):
    return await db.scalar(select(DiagnosticSession).where(DiagnosticSession.course_id == course_id,
        DiagnosticSession.learner_id == learner_id))

async def start_diagnostic(db, course_id, learner_id):
    # Serialize selection so repeated clicks cannot create different diagnostic sets.
    if not await db.scalar(select(Course).where(Course.id == course_id).with_for_update()):
        raise HTTPException(404, 'Course not found')
    existing = await get_diagnostic(db, course_id, learner_id)
    if existing:
        return existing
    seen = select(AssessmentAttempt.question_id).where(AssessmentAttempt.course_id == course_id,
        AssessmentAttempt.learner_id == learner_id)
    scoped = select(LearningIntervention.assessment_question_id).where(LearningIntervention.assessment_question_id.is_not(None))
    bank = list((await db.scalars(select(AssessmentQuestion).options(selectinload(AssessmentQuestion.concepts)).where(
        AssessmentQuestion.course_id == course_id, AssessmentQuestion.verification_status == 'verified',
        AssessmentQuestion.id.not_in(seen), AssessmentQuestion.id.not_in(scoped))
        .order_by(AssessmentQuestion.created_at, AssessmentQuestion.id))).all())
    selected, covered = [], set()
    for q in bank:
        concepts = {c.id for c in q.concepts if c.course_id == course_id}
        if len(concepts) != 1 or concepts <= covered:
            continue
        valid, _ = await trusted_evidence(db, course_id, q.evidence_unit_ids)
        if not valid or list(valid.values()) != q.citation_snapshots:
            continue
        selected.append(str(q.id)); covered.update(concepts)
        if len(selected) == 5:
            break
    if len(selected) < 3:
        concepts = (await db.scalars(select(Concept).where(Concept.course_id == course_id)
            .order_by(Concept.name, Concept.id))).all()
        # Bound provider work even when a large graph lacks usable source evidence.
        for c in [c for c in concepts if c.id not in covered][:5]:
            try:
                result = await generate_assessments(db=db, course_id=course_id,
                    request=AssessmentGenerationRequest(focus=c.name, concept_id=c.id, count=1), commit=False)
            except (LLMConfigurationError, LLMProviderError):
                if selected:
                    break
                raise
            if result.questions:
                selected.append(str(result.questions[0].id)); covered.add(c.id)
            if len(selected) >= 3:
                break
    if not selected:
        raise HTTPException(422, 'Insufficient verified concept evidence for a diagnostic. Add and index source material first.')
    session = DiagnosticSession(id=uuid.uuid4(), course_id=course_id, learner_id=learner_id, question_ids=selected)
    db.add(session)
    await db.flush()
    return session

async def public_diagnostic(db, session):
    if session is None:
        return dict(status='not_started', questions=[], completed_question_ids=[], question_count=0)
    ids = [uuid.UUID(q) for q in session.question_ids]
    questions = {q.id:q for q in (await db.scalars(select(AssessmentQuestion).where(
        AssessmentQuestion.course_id == session.course_id, AssessmentQuestion.id.in_(ids),
        AssessmentQuestion.verification_status == 'verified'))).all()}
    completed = list((await db.scalars(select(AssessmentAttempt.question_id).where(
        AssessmentAttempt.course_id == session.course_id, AssessmentAttempt.learner_id == session.learner_id,
        AssessmentAttempt.question_id.in_(ids), AssessmentAttempt.is_correct.is_not(None)).distinct())).all())
    return dict(id=session.id, status='complete' if set(ids) <= set(completed) else 'in_progress',
        question_count=len(ids), completed_question_ids=completed,
        questions=[AssessmentQuestionPublic(id=q.id, course_id=q.course_id, question_type=q.question_type,
            difficulty=q.difficulty, question_text=q.question_text, options=q.options,
            citations=q.citation_snapshots, created_at=q.created_at, **public_format(q)) for qid in ids if (q:=questions.get(qid))],
        message='This is a small sample, not a complete measure of ability. Unsampled concepts remain UNTESTED.')
