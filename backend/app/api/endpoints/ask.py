import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.course import Course
from app.schemas.ask import AskRequest, AskResponse
from app.services.grounded_ask import execute_grounded_ask
from app.services.llm_provider import (
    InvalidLLMResponseError,
    LLMConfigurationError,
    LLMProviderError,
    UnsafeCitationReferenceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/courses/{course_id}", tags=["ask"])


async def _verify_course(db: AsyncSession, course_id: uuid.UUID) -> Course:
    course = await db.scalar(select(Course).where(Course.id == course_id))
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )
    return course


@router.post("/ask", response_model=AskResponse)
async def ask_course_question(
    course_id: uuid.UUID,
    request: AskRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Answer a learner question grounded strictly in course materials."""
    await _verify_course(db, course_id)

    try:
        response = await execute_grounded_ask(
            db=db,
            course_id=course_id,
            request=request,
        )
        return response
    except HTTPException:
        raise
    except LLMConfigurationError:
        logger.warning("LLM provider not configured for course %s", course_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer generation is not configured.",
        )
    except LLMProviderError:
        logger.exception("LLM provider error during answer generation")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer generation provider is unavailable.",
        )
    except (InvalidLLMResponseError, UnsafeCitationReferenceError):
        logger.exception("Invalid or unsafe LLM response generated")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from answer generation.",
        )
    except Exception:
        logger.exception("Unexpected error in ask endpoint")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during answer generation.",
        )
