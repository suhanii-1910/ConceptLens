"""Course API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.course import CourseCreate, CourseRead
from app.services import course_service

router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
async def create_course(
    body: CourseCreate,
    db: AsyncSession = Depends(get_db),
) -> CourseRead:
    course = await course_service.create_course(db, name=body.name, description=body.description)
    return CourseRead.model_validate(course)


@router.get("", response_model=list[CourseRead])
async def list_courses(
    db: AsyncSession = Depends(get_db),
) -> list[CourseRead]:
    courses = await course_service.list_courses(db)
    return [CourseRead.model_validate(c) for c in courses]


@router.get("/{course_id}", response_model=CourseRead)
async def get_course(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CourseRead:
    course = await course_service.get_course(db, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )
    return CourseRead.model_validate(course)
