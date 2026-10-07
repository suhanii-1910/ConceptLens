"""Diagnostic, report, and concept evidence surfaces within the five main views."""
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.endpoints.assessment import _verify_course
from app.api.endpoints.adaptive_learning import transition
from app.services.cold_start import get_diagnostic, start_diagnostic, public_diagnostic
from app.services.learner_report import assessment_report, concept_graph
router = APIRouter(prefix='/courses/{course_id}', tags=['learner-evidence'])

@router.get('/concept-evidence')
async def graph(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _verify_course(db, course_id)
    return await concept_graph(db, course_id)

@router.get('/learners/{learner_id}/assessment-report')
async def report(course_id: uuid.UUID, learner_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _verify_course(db, course_id)
    return await assessment_report(db, course_id, learner_id)

@router.get('/learners/{learner_id}/diagnostic')
async def read_diagnostic(course_id: uuid.UUID, learner_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _verify_course(db, course_id)
    return await public_diagnostic(db, await get_diagnostic(db, course_id, learner_id))

@router.post('/learners/{learner_id}/diagnostic')
async def create_diagnostic(course_id: uuid.UUID, learner_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    async with transition(db):
        result = await public_diagnostic(db, await start_diagnostic(db, course_id, learner_id))
    return result
