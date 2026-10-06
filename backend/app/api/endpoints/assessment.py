"""Phase 4 & 5 Grounded Assessment API endpoints."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.assessment import (
    AssessmentQuestion,
)
from app.models.course import Course
from app.schemas.assessment import (
    AssessmentAttemptCreate,
    AssessmentAttemptResponse,
    AssessmentGenerationRequest,
    AssessmentGenerationResponse,
    AssessmentQuestionPublic,
    AssessmentQuestionVerificationStatus,
)
from app.schemas.retrieval import Citation
from app.services.assessment_generation import generate_assessments
from app.services.assessment_grading import grade_attempt
from app.services.llm_provider import (
    InvalidLLMResponseError,
    LLMConfigurationError,
    LLMProviderError,
    UnsafeCitationReferenceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/courses/{course_id}/assessments", tags=["assessments"])


async def _verify_course(db: AsyncSession, course_id: uuid.UUID) -> Course:
    course = await db.scalar(select(Course).where(Course.id == course_id))
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )
    return course


@router.post("/generate", response_model=AssessmentGenerationResponse)
async def generate_course_assessments(
    course_id: uuid.UUID,
    request: AssessmentGenerationRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Generate independently verified multiple-choice questions grounded in course materials."""
    await _verify_course(db, course_id)

    try:
        response = await generate_assessments(
            db=db,
            course_id=course_id,
            request=request,
        )
        return response
    except HTTPException:
        raise
    except LLMConfigurationError:
        logger.warning("LLM provider not configured for course %s assessment generation", course_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Assessment generation is not configured.",
        )
    except LLMProviderError:
        logger.exception("LLM provider error during assessment generation")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Assessment generation provider is unavailable.",
        )
    except (InvalidLLMResponseError, UnsafeCitationReferenceError):
        logger.exception("Invalid or unsafe LLM response generated during assessment")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from assessment generation.",
        )
    except Exception:
        logger.exception("Unexpected error in assessment generation endpoint")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during assessment generation.",
        )


@router.get("/questions/{question_id}", response_model=AssessmentQuestionPublic)
async def get_assessment_question(
    course_id: uuid.UUID,
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Fetch a public assessment question. Answer key and explanation are strictly hidden."""
    await _verify_course(db, course_id)

    stmt = select(AssessmentQuestion).where(
        AssessmentQuestion.id == question_id,
        AssessmentQuestion.course_id == course_id,
        AssessmentQuestion.verification_status == AssessmentQuestionVerificationStatus.verified,
    )
    question = await db.scalar(stmt)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found",
        )

    parsed_citations = [
        Citation.model_validate(c) for c in question.citation_snapshots
    ]

    return AssessmentQuestionPublic(
        id=question.id,
        course_id=question.course_id,
        question_type=question.question_type,
        difficulty=question.difficulty,
        question_text=question.question_text,
        options=question.options,
        citations=parsed_citations,
        created_at=question.created_at,
    )


@router.post("/questions/{question_id}/attempts", response_model=AssessmentAttemptResponse)
async def submit_assessment_attempt(
    course_id: uuid.UUID,
    question_id: uuid.UUID,
    attempt_in: AssessmentAttemptCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Submit a learner attempt on a verified assessment question.

    - Graded deterministically without LLM calls.
    - Persisted as an immutable append-only record.
    - Updates BKT Learner Mastery (Phase 5).
    - Answer key, explanation, and citations revealed only AFTER submission.
    """
    # Own the transaction before the first read (SQLAlchemy otherwise autobegins).
    async with db.begin():
        await _verify_course(db, course_id)
        stmt = select(AssessmentQuestion).options(
            selectinload(AssessmentQuestion.concepts)
        ).where(
            AssessmentQuestion.id == question_id,
            AssessmentQuestion.course_id == course_id,
            AssessmentQuestion.verification_status == AssessmentQuestionVerificationStatus.verified,
        )
        question = await db.scalar(stmt)
        if not question:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")

        from app.models.adaptive_learning import LearningIntervention
        if await db.scalar(select(LearningIntervention.id).where(
            LearningIntervention.assessment_question_id == question.id)):
            raise HTTPException(409, "Use the scoped learning-session submission route")
        _, response = await grade_attempt(db, question, attempt_in.learner_id, attempt_in.selected_option_index)
    # Exiting the transaction commits all three records or rolls them all back.
    return response
