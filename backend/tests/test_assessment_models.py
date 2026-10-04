"""Unit tests for Assessment models, relationships, and constraints."""

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import AssessmentAttempt, AssessmentQuestion
from app.models.course import Course
from app.schemas.assessment import (
    AssessmentDifficulty,
    AssessmentQuestionType,
    AssessmentQuestionVerificationStatus,
)

pytestmark = pytest.mark.asyncio


async def _create_course(db: AsyncSession, name: str = "Test Course") -> Course:
    course = Course(id=uuid.uuid4(), name=name)
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


async def test_create_assessment_question_valid(db_session: AsyncSession):
    course = await _create_course(db_session)
    q_id = uuid.uuid4()
    q = AssessmentQuestion(
        id=q_id,
        course_id=course.id,
        question_type=AssessmentQuestionType.multiple_choice,
        difficulty=AssessmentDifficulty.medium,
        question_text="What is a process control block?",
        options=["Data structure", "CPU register", "Disk sector", "Network packet"],
        correct_option_index=0,
        explanation="PCB is a kernel data structure representing a process.",
        evidence_unit_ids=[str(uuid.uuid4())],
        citation_snapshots=[{"source_filename": "notes.pdf", "locator_label": "notes.pdf · p. 1"}],
        verification_status=AssessmentQuestionVerificationStatus.verified,
        generation_focus="Process management",
    )
    db_session.add(q)
    await db_session.commit()
    await db_session.refresh(q)

    assert q.id == q_id
    assert q.course_id == course.id
    assert q.difficulty == AssessmentDifficulty.medium
    assert q.correct_option_index == 0
    assert len(q.options) == 4
    assert q.verification_status == AssessmentQuestionVerificationStatus.verified
    assert q.created_at is not None


async def test_assessment_question_cascade_delete(db_session: AsyncSession):
    course = await _create_course(db_session)
    q = AssessmentQuestion(
        id=uuid.uuid4(),
        course_id=course.id,
        question_type=AssessmentQuestionType.multiple_choice,
        difficulty=AssessmentDifficulty.easy,
        question_text="Sample text",
        options=["A", "B", "C", "D"],
        correct_option_index=1,
        explanation="B is correct",
        evidence_unit_ids=[str(uuid.uuid4())],
        citation_snapshots=[],
        verification_status=AssessmentQuestionVerificationStatus.verified,
    )
    db_session.add(q)
    await db_session.commit()

    # Deleting course should cascade delete questions
    await db_session.delete(course)
    await db_session.commit()

    saved_q = await db_session.scalar(select(AssessmentQuestion).where(AssessmentQuestion.id == q.id))
    assert saved_q is None


async def test_create_assessment_attempt_valid(db_session: AsyncSession):
    course = await _create_course(db_session)
    q = AssessmentQuestion(
        id=uuid.uuid4(),
        course_id=course.id,
        question_type=AssessmentQuestionType.multiple_choice,
        difficulty=AssessmentDifficulty.hard,
        question_text="Sample hard question",
        options=["Option 0", "Option 1", "Option 2", "Option 3"],
        correct_option_index=2,
        explanation="Option 2 is correct",
        evidence_unit_ids=[str(uuid.uuid4())],
        citation_snapshots=[],
        verification_status=AssessmentQuestionVerificationStatus.verified,
    )
    db_session.add(q)
    await db_session.commit()

    learner_id = uuid.uuid4()
    attempt = AssessmentAttempt(
        id=uuid.uuid4(),
        question_id=q.id,
        course_id=course.id,
        learner_id=learner_id,
        selected_option_index=2,
        is_correct=True,
    )
    db_session.add(attempt)
    await db_session.commit()
    await db_session.refresh(attempt)

    assert attempt.is_correct is True
    assert attempt.selected_option_index == 2
    assert attempt.learner_id == learner_id
    assert attempt.created_at is not None


async def test_assessment_attempt_immutability_new_row_for_second_attempt(db_session: AsyncSession):
    course = await _create_course(db_session)
    q = AssessmentQuestion(
        id=uuid.uuid4(),
        course_id=course.id,
        question_type=AssessmentQuestionType.multiple_choice,
        difficulty=AssessmentDifficulty.medium,
        question_text="Question stem",
        options=["A", "B", "C", "D"],
        correct_option_index=0,
        explanation="A is correct",
        evidence_unit_ids=[str(uuid.uuid4())],
        citation_snapshots=[],
        verification_status=AssessmentQuestionVerificationStatus.verified,
    )
    db_session.add(q)
    await db_session.commit()

    learner_id = uuid.uuid4()
    att1 = AssessmentAttempt(
        id=uuid.uuid4(),
        question_id=q.id,
        course_id=course.id,
        learner_id=learner_id,
        selected_option_index=0,
        is_correct=True,
    )
    db_session.add(att1)
    await db_session.commit()
    await db_session.refresh(att1)

    # Second attempt with different answer
    att2 = AssessmentAttempt(
        id=uuid.uuid4(),
        question_id=q.id,
        course_id=course.id,
        learner_id=learner_id,
        selected_option_index=1,
        is_correct=False,
    )
    db_session.add(att2)
    await db_session.commit()
    await db_session.refresh(att2)

    assert att1.id != att2.id
    assert att1.selected_option_index == 0
    assert att1.is_correct is True
    assert att2.selected_option_index == 1
    assert att2.is_correct is False

    # Check both rows exist
    attempts = (await db_session.scalars(select(AssessmentAttempt).where(AssessmentAttempt.question_id == q.id))).all()
    assert len(attempts) == 2
