"""Shared deterministic grading; caller owns scope checks and transaction."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.assessment import AssessmentAttempt, AssessmentQuestion
from app.schemas.assessment import AssessmentAttemptResponse
from app.schemas.retrieval import Citation
from app.services.mastery_update import process_mastery_update


async def grade_attempt(db: AsyncSession, question: AssessmentQuestion, learner_id: uuid.UUID,
                        selected_option_index: int, *, update_mastery: bool = True) -> tuple[AssessmentAttempt, AssessmentAttemptResponse]:
    course_id = question.course_id
    # Validate stored response data before accepting an attempt.
    parsed_citations = [Citation.model_validate(c) for c in question.citation_snapshots]
    correct_text = question.options[question.correct_option_index]
    attempt = AssessmentAttempt(
        id=uuid.uuid4(),
        question_id=question.id,
        course_id=course_id,
        learner_id=learner_id,
        selected_option_index=selected_option_index,
        is_correct=selected_option_index == question.correct_option_index,
    )
    db.add(attempt)
    await db.flush()

    status_enum, update_public = None, None
    if update_mastery:
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
        explanation=question.explanation,
        citations=parsed_citations,
        created_at=attempt.created_at,
        mastery_update_status=status_enum,
        mastery_update=update_public,
    )
    return attempt, response
