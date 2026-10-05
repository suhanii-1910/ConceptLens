"""Opt-in PostgreSQL acceptance using disposable schemas, never app data/migrations.

Run with CONCEPTLENS_TEST_POSTGRES=1. Optionally set
CONCEPTLENS_TEST_POSTGRES_URL for a PostgreSQL test server instead of the local
development default. The server must already have the Phase 4/5 enum types.
"""

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql.dml import Insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.endpoints.assessment import submit_assessment_attempt
from app.core.config import Settings
from app.db.base import Base
from app.models.assessment import AssessmentAttempt
from app.models.course import Course
from app.models.concept import Concept
from app.models.learner_mastery import LearnerConceptMastery, MasteryObservation
from app.models.learner_mastery import assessment_question_concept_link
from app.schemas.assessment import AssessmentAttemptCreate
from app.services.learner_mastery import compute_bkt_step
from tests.test_api_mastery import mapped_question, seed

pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(
    os.getenv("CONCEPTLENS_TEST_POSTGRES") != "1",
    reason="Opt-in real PostgreSQL acceptance (CONCEPTLENS_TEST_POSTGRES=1)",
)]


@pytest_asyncio.fixture
async def postgres_engine():
    url = os.getenv("CONCEPTLENS_TEST_POSTGRES_URL") or Settings.model_fields["database_url"].default
    engine = create_async_engine(url, isolation_level="READ COMMITTED")
    schema = "phase5_test_" + uuid.uuid4().hex
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        isolated = engine.execution_options(schema_translate_map={None: schema})
        async with isolated.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield isolated
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("repeat", [False, True])
async def test_concurrent_first_exposures(postgres_engine, existing, repeat):
    factory = async_sessionmaker(postgres_engine, expire_on_commit=False)
    learner = uuid.uuid4()
    async with factory() as db:
        course, concepts, q0 = await seed(db)
        q1 = await mapped_question(db, course, concepts)
        q2 = q1 if repeat else await mapped_question(db, course, concepts)
    if existing:
        async with factory() as db:
            await submit_assessment_attempt(course.id, q0.id, AssessmentAttemptCreate(
                learner_id=learner, selected_option_index=2,
            ), db)

    # Both requests must pass the initial exposure check before either can insert
    # or lock mastery. This deterministically exercises the old repeat race.
    barrier = asyncio.Barrier(2)
    class RacingSession(AsyncSession):
        async def execute(self, statement, *args, **kwargs):
            if isinstance(statement, Insert) and statement.table.name == "learner_concept_mastery":
                await barrier.wait()
            return await super().execute(statement, *args, **kwargs)

    racing = async_sessionmaker(postgres_engine, class_=RacingSession, expire_on_commit=False)
    async def attempt(question, selected):
        async with racing() as db:
            return await submit_assessment_attempt(course.id, question.id, AssessmentAttemptCreate(
                learner_id=learner, selected_option_index=selected,
            ), db)
    results = await asyncio.wait_for(asyncio.gather(attempt(q1, 2), attempt(q2, 0)), timeout=15)
    assert sorted(r.mastery_update_status.value for r in results) == (
        ["skipped_repeated_question", "updated"] if repeat else ["updated", "updated"]
    )
    async with factory() as db:
        mastery = (await db.scalars(select(LearnerConceptMastery))).one()
        observations = (await db.scalars(select(MasteryObservation).order_by(MasteryObservation.observation_index))).all()
        attempts = (await db.scalars(select(AssessmentAttempt))).all()
        expected = int(existing) + (1 if repeat else 2)
        assert len(attempts) == int(existing) + 2
        assert len(observations) == mastery.observation_count == expected
        assert [o.observation_index for o in observations] == list(range(1, expected + 1))
        assert mastery.correct_count == sum(o.is_correct for o in observations)
        p = .2
        for obs in observations:
            assert obs.prior_mastery == p
            p = compute_bkt_step(p, obs.is_correct).updated_mastery
            assert obs.updated_mastery == p
        assert mastery.mastery_probability == p
        assert mastery.last_attempt_id == observations[-1].attempt_id


async def test_course_cascade_with_observations(postgres_engine):
    factory = async_sessionmaker(postgres_engine, expire_on_commit=False)
    async with factory() as db:
        course, _, q = await seed(db)
    async with factory() as db:
        await submit_assessment_attempt(course.id, q.id, AssessmentAttemptCreate(
            learner_id=uuid.uuid4(), selected_option_index=2,
        ), db)
    async with factory() as db:
        await db.delete(await db.get(Course, course.id))
        await db.commit()
    async with factory() as db:
        for model in [AssessmentAttempt, LearnerConceptMastery, MasteryObservation, Concept]:
            assert (await db.scalars(select(model))).all() == []


@pytest.mark.parametrize("loaded", [False, True])
async def test_concept_deletion_cannot_shrink_mapping(postgres_engine, loaded):
    factory = async_sessionmaker(postgres_engine, expire_on_commit=False)
    async with factory() as db:
        _, concepts, q = await seed(db, 2)
    async with factory() as db:
        stmt = select(Concept).where(Concept.id == concepts[0].id)
        if loaded:
            stmt = stmt.options(selectinload(Concept.assessment_questions))
        concept = await db.scalar(stmt)
        with pytest.raises((IntegrityError, ValueError)):
            await db.delete(concept)
            await db.commit()
        await db.rollback()
        links = (await db.execute(select(assessment_question_concept_link).where(
            assessment_question_concept_link.c.question_id == q.id,
        ))).all()
        assert len(links) == 2
