"""Shared deterministic grading; caller owns scope checks and transaction."""
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.assessment import AssessmentAttempt, AssessmentQuestion
from app.schemas.assessment import AssessmentAttemptResponse
from app.schemas.retrieval import Citation
from app.services.mastery_update import process_mastery_update


async def grade_attempt(db: AsyncSession, question: AssessmentQuestion, learner_id: uuid.UUID,
                        selected_option_index: int | None, *, update_mastery: bool = True, response=None, provider=None) -> tuple[AssessmentAttempt, AssessmentAttemptResponse]:
    course_id = question.course_id
    # Validate stored response data before accepting an attempt.
    parsed_citations = [Citation.model_validate(c) for c in question.citation_snapshots]
    from fastapi import HTTPException
    from app.services.typed_assessment import grade_response
    grading = None
    is_mcq = question.question_type == 'multiple_choice'
    if is_mcq:
        if selected_option_index is None or (response and (response.answer_text is not None or response.answer_value is not None)):
            raise HTTPException(422, 'A multiple-choice selection is required')
        correct_text = question.options[question.correct_option_index]
        correct = selected_option_index == question.correct_option_index
    else:
        if response is None or selected_option_index is not None:
            raise HTTPException(422, 'Submit the answer form matching this question type')
        from app.services.adaptive_learning import trusted_evidence
        citations, evidence = await trusted_evidence(db, course_id, question.evidence_unit_ids)
        safe = citations and list(citations.values()) == question.citation_snapshots
        grading = await grade_response(question,response,provider=provider,evidence_context=evidence if safe else None) if safe else dict(verdict='cannot_grade',explanation='Source provenance is no longer valid.',method='unavailable')
        correct = None if grading['verdict']=='cannot_grade' else grading['verdict']=='correct'
        correct_text = question.grading_contract['reference_answer'] if correct is not None else None
    attempt = AssessmentAttempt(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        question_id=question.id,
        course_id=course_id,
        learner_id=learner_id,
        selected_option_index=selected_option_index,
        is_correct=correct,
        response_data=response.model_dump(mode='json',exclude={'learner_id','selected_option_index'},exclude_none=True) if not is_mcq else None,
        grading_result=grading,
    )
    db.add(attempt)
    await db.flush()

    status_enum, update_public = None, None
    if update_mastery and correct is not None:
        status_enum, update_public = await process_mastery_update(
            db=db, attempt=attempt, course_id=course_id, concepts=question.concepts,
        )
    attempt.mastery_update_status = status_enum
    response = AssessmentAttemptResponse(
        attempt_id=attempt.id,
        question_id=question.id,
        course_id=course_id,
        learner_id=attempt.learner_id,
        selected_option_index=attempt.selected_option_index,
        is_correct=attempt.is_correct,
        correct_option_index=question.correct_option_index,
        correct_option_text=correct_text,
        explanation=grading['explanation'] if grading else question.explanation,
        question_type=question.question_type,
        submitted_answer=(response.answer_text or response.answer_value) if response and not is_mcq else None,
        grading=grading,
        citations=parsed_citations,
        created_at=attempt.created_at,
        mastery_update_status=status_enum,
        mastery_update=update_public,
    )
    return attempt, response
