"""Scoped adaptive learning routes with atomic transitions."""
import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas import adaptive_learning as schema
from app.services import adaptive_learning as service
from app.services.llm_provider import InvalidLLMResponseError, UnsafeCitationReferenceError, LLMConfigurationError, LLMProviderError

router = APIRouter(prefix='/courses/{course_id}/learners/{learner_id}/learning-sessions', tags=['learning-sessions'])


@asynccontextmanager
async def transition(db):
    try:
        async with db.begin():
            yield
    except (LLMConfigurationError, LLMProviderError):
        raise HTTPException(503, 'Teaching provider is unavailable.') from None
    except (InvalidLLMResponseError, UnsafeCitationReferenceError):
        raise HTTPException(502, 'Invalid response from teaching generation.') from None


@router.post('', response_model=schema.SessionPublic)
async def create_learning_session(course_id: uuid.UUID, learner_id: uuid.UUID,
        request: schema.SessionCreate, db: AsyncSession = Depends(get_db)):
    async with transition(db):
        session = await service.create_session(db, course_id, learner_id, request)
        result = await service.public_session(db, session)
    return result


@router.get('/{session_id}', response_model=schema.SessionPublic)
async def read_learning_session(course_id: uuid.UUID, learner_id: uuid.UUID,
        session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await service.get_session(db, course_id, learner_id, session_id)
    return await service.public_session(db, session)


@router.post('/{session_id}/feedback', response_model=schema.SessionPublic)
async def submit_feedback(course_id: uuid.UUID, learner_id: uuid.UUID, session_id: uuid.UUID,
        request: schema.FeedbackCreate, db: AsyncSession = Depends(get_db)):
    async with transition(db):
        session = await service.get_session(db, course_id, learner_id, session_id, lock=True)
        await service.feedback(db, session, request)
        result = await service.public_session(db, session)
    return result


@router.post('/{session_id}/prerequisite-choice', response_model=schema.SessionPublic)
async def choose_prerequisite(course_id: uuid.UUID, learner_id: uuid.UUID, session_id: uuid.UUID,
        request: schema.PrerequisiteChoice, db: AsyncSession = Depends(get_db)):
    async with transition(db):
        session = await service.get_session(db, course_id, learner_id, session_id, lock=True)
        await service.prerequisite_choice(db, session, request)
        result = await service.public_session(db, session)
    return result


@router.post('/{session_id}/interventions/{intervention_id}/attempts', response_model=schema.LearningAttemptPublic)
async def submit_prerequisite_attempt(course_id: uuid.UUID, learner_id: uuid.UUID, session_id: uuid.UUID,
        intervention_id: uuid.UUID, request: schema.LearningAttemptCreate, db: AsyncSession = Depends(get_db)):
    async with transition(db):
        session = await service.get_session(db, course_id, learner_id, session_id, lock=True)
        result = await service.submit_attempt(db, session, request, intervention_id=intervention_id)
    return result


@router.post('/{session_id}/transfer-check/attempts', response_model=schema.LearningAttemptPublic)
async def submit_transfer_attempt(course_id: uuid.UUID, learner_id: uuid.UUID, session_id: uuid.UUID,
        request: schema.LearningAttemptCreate, db: AsyncSession = Depends(get_db)):
    async with transition(db):
        session = await service.get_session(db, course_id, learner_id, session_id, lock=True)
        result = await service.submit_attempt(db, session, request, transfer=True)
    return result


@router.get('/{session_id}/trace', response_model=schema.LearningTrace)
async def read_trace(course_id: uuid.UUID, learner_id: uuid.UUID, session_id: uuid.UUID,
        db: AsyncSession = Depends(get_db)):
    session = await service.get_session(db, course_id, learner_id, session_id)
    return await service.learning_trace(db, session)
