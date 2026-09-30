"""Course service — business logic for courses."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course


async def create_course(db: AsyncSession, *, name: str, description: str | None = None) -> Course:
    """Create and persist a new course."""
    course = Course(name=name, description=description)
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


async def list_courses(db: AsyncSession) -> list[Course]:
    """Return all courses ordered by creation time (newest first)."""
    result = await db.execute(select(Course).order_by(Course.created_at.desc()))
    return list(result.scalars().all())


async def get_course(db: AsyncSession, course_id: uuid.UUID) -> Course | None:
    """Return a single course by id, or None."""
    return await db.get(Course, course_id)
