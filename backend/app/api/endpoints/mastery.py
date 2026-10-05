"""Read-only mastery estimates; unseen concepts are represented without inserts."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.concept import Concept
from app.models.course import Course
from app.models.learner_mastery import LearnerConceptMastery
from app.schemas.learner_mastery import (
    LearnerConceptMasteryPublic,
    LearnerCourseMasteryResponse,
)
from app.services.learner_mastery import BKT_INITIAL_MASTERY, get_mastery_band

router = APIRouter(
    prefix="/courses/{course_id}/learners/{learner_id}/mastery", tags=["mastery"]
)


async def _read_mastery(
    db: AsyncSession,
    course_id: uuid.UUID,
    learner_id: uuid.UUID,
    concept_id: uuid.UUID | None = None,
) -> list[LearnerConceptMasteryPublic]:
    if await db.scalar(select(Course.id).where(Course.id == course_id)) is None:
        raise HTTPException(status_code=404, detail="Course not found")

    stmt = (
        select(Concept, LearnerConceptMastery)
        .outerjoin(
            LearnerConceptMastery,
            and_(
                LearnerConceptMastery.concept_id == Concept.id,
                LearnerConceptMastery.course_id == course_id,
                LearnerConceptMastery.learner_id == learner_id,
            ),
        )
        .where(Concept.course_id == course_id)
        .order_by(Concept.name, Concept.id)
    )
    if concept_id is not None:
        stmt = stmt.where(Concept.id == concept_id)
    rows = (await db.execute(stmt)).all()
    if concept_id is not None and not rows:
        raise HTTPException(status_code=404, detail="Concept not found")

    results = []
    for concept, mastery in rows:
        probability = mastery.mastery_probability if mastery else BKT_INITIAL_MASTERY
        count = mastery.observation_count if mastery else 0
        results.append(LearnerConceptMasteryPublic(
            concept_id=concept.id,
            concept_name=concept.name,
            course_id=course_id,
            learner_id=learner_id,
            mastery_probability=probability,
            observation_count=count,
            correct_count=mastery.correct_count if mastery else 0,
            mastery_band=get_mastery_band(count, probability),
            last_attempt_id=mastery.last_attempt_id if mastery else None,
            created_at=mastery.created_at if mastery else None,
            updated_at=mastery.updated_at if mastery else None,
        ))
    return results


@router.get("", response_model=LearnerCourseMasteryResponse)
async def get_course_mastery(
    course_id: uuid.UUID,
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> LearnerCourseMasteryResponse:
    return LearnerCourseMasteryResponse(
        course_id=course_id,
        learner_id=learner_id,
        concepts=await _read_mastery(db, course_id, learner_id),
    )


@router.get("/{concept_id}", response_model=LearnerConceptMasteryPublic)
async def get_concept_mastery(
    course_id: uuid.UUID,
    learner_id: uuid.UUID,
    concept_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> LearnerConceptMasteryPublic:
    return (await _read_mastery(db, course_id, learner_id, concept_id))[0]
