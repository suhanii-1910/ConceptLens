"""Reasoning diagnosis endpoints. Every new diagnostic unit commits atomically."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.reasoning_diagnosis import DiagnosisCreate, DiagnosisPublic, ProbeAttemptCreate, ProbeAttemptPublic
from app.services import reasoning_diagnosis as service
from app.services.llm_provider import (
    InvalidLLMResponseError, UnsafeCitationReferenceError, LLMConfigurationError, LLMProviderError,
)

router = APIRouter(prefix="/courses/{course_id}/learners/{learner_id}/reasoning-diagnoses", tags=["reasoning-diagnoses"])


@router.post("", response_model=DiagnosisPublic)
async def create_reasoning_diagnosis(course_id: uuid.UUID, learner_id: uuid.UUID,
        request: DiagnosisCreate, db: AsyncSession = Depends(get_db)):
    try:
        async with db.begin():
            diagnosis = await service.create_diagnosis(db, course_id, learner_id, request)
            response = await service.public_diagnosis(db, diagnosis)
        return response
    except LLMConfigurationError:
        raise HTTPException(503, "Reasoning diagnosis is not configured.") from None
    except LLMProviderError:
        raise HTTPException(503, "Reasoning diagnosis provider is unavailable.") from None
    except (InvalidLLMResponseError, UnsafeCitationReferenceError):
        raise HTTPException(502, "Invalid response from reasoning diagnosis.") from None


@router.get("/{diagnosis_id}", response_model=DiagnosisPublic)
async def read_reasoning_diagnosis(course_id: uuid.UUID, learner_id: uuid.UUID,
        diagnosis_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    diagnosis = await service.get_diagnosis(db, course_id, learner_id, diagnosis_id)
    return await service.public_diagnosis(db, diagnosis)


@router.post("/{diagnosis_id}/probe-attempts", response_model=ProbeAttemptPublic)
async def submit_probe_attempt(course_id: uuid.UUID, learner_id: uuid.UUID,
        diagnosis_id: uuid.UUID, request: ProbeAttemptCreate, db: AsyncSession = Depends(get_db)):
    async with db.begin():
        response = await service.submit_probe(db, course_id, learner_id, diagnosis_id, request)
    return response
