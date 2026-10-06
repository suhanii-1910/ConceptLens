"""Opt-in acceptance on freshly migrated disposable DATABASES, never app data.

CONCEPTLENS_TEST_POSTGRES=1 enables runtime tests. Set
CONCEPTLENS_TEST_MIGRATION_LIFECYCLE=1 separately for the migration lifecycle.
CONCEPTLENS_TEST_POSTGRES_URL supplies server credentials; its database is never
connected to. Administration uses postgres; every test creates/drops its own DB.
"""

import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
import uuid

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy import insert, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.models import AssessmentAttempt, Concept, Course, LearnerConceptMastery, MasteryObservation
from app.models.reasoning_diagnosis import ReasoningDiagnosis, DiagnosticProbe, DiagnosticProbeAttempt
from app.api.endpoints.reasoning_diagnosis import create_reasoning_diagnosis, submit_probe_attempt
from app.schemas.reasoning_diagnosis import DiagnosisCreate, ProbeAttemptCreate
from app.services.mastery_update import process_mastery_update
from tests.test_reasoning_diagnosis import seed, payloads, provider_for, STEPS

BACKEND = Path(__file__).resolve().parents[1]
PHASE6 = {'reasoning_diagnoses', 'diagnostic_probes', 'diagnostic_probe_attempts'}
runtime = pytest.mark.skipif(os.getenv('CONCEPTLENS_TEST_POSTGRES') != '1', reason='Opt-in real PostgreSQL Phase 6')
pytestmark = pytest.mark.asyncio


async def migrate(engine, database, command, revision=None):
    async with engine.connect() as conn:
        actual = await conn.scalar(text('SELECT current_database()'))
        assert actual == database and actual.startswith('conceptlens_phase6_check_')
        print(f'Confirmed disposable target before alembic {command}: {actual}', flush=True)
    await engine.dispose()
    env = dict(os.environ, CONCEPTLENS_DATABASE_URL=engine.url.render_as_string(hide_password=False), PYTHONDONTWRITEBYTECODE='1')
    proc = await asyncio.create_subprocess_exec(sys.executable, '-m', 'alembic', command,
        *([revision] if revision else []), cwd=BACKEND, env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    output, _ = await proc.communicate()
    print(output.decode(), flush=True)
    assert proc.returncode == 0, output.decode()
    return output.decode()


@asynccontextmanager
async def disposable_database(revision='head'):
    original = make_url(os.getenv('CONCEPTLENS_TEST_POSTGRES_URL') or Settings.model_fields['database_url'].default)
    name = 'conceptlens_phase6_check_' + uuid.uuid4().hex[:16]
    assert name != original.database and name != 'conceptlens'
    admin_url = original.set(drivername='postgresql', database='postgres')
    admin = await asyncpg.connect(admin_url.render_as_string(hide_password=False))
    engine = create_async_engine(original.set(database=name), isolation_level='READ COMMITTED')
    created = False
    try:
        assert await admin.fetchval('SELECT current_database()') == 'postgres'
        print(f'CREATE disposable database: {name}; normal database is not connected to.', flush=True)
        await admin.execute(f'CREATE DATABASE "{name}" TEMPLATE template0')
        created = True
        await migrate(engine, name, 'upgrade', revision)
        yield engine, name
    finally:
        await engine.dispose()
        if created:
            assert await admin.fetchval('SELECT current_database()') == 'postgres'
            assert name.startswith('conceptlens_phase6_check_') and name != original.database
            print(f'DROP confirmed disposable database: {name}', flush=True)
            await admin.execute(f'DROP DATABASE "{name}"')
            assert not await admin.fetchval('SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=$1)', name)
        await admin.close()


@pytest_asyncio.fixture
async def migrated():
    async with disposable_database() as (engine, name):
        yield engine


async def diagnostic_event(factory, monkeypatch, *, mastery=False):
    async with factory() as db:
        course, concept, evidence, question, attempt = await seed(db)
        if mastery:
            async with db.begin():
                status, _ = await process_mastery_update(db, attempt, course.id, [concept])
                attempt.mastery_update_status = status
    provider_for(monkeypatch, *payloads(concept, evidence))
    async with factory() as db:
        diagnosis = await create_reasoning_diagnosis(course.id, attempt.learner_id,
            DiagnosisCreate(attempt_id=attempt.id, reasoning_steps=STEPS), db)
    return course, attempt, diagnosis


@runtime
@pytest.mark.parametrize('already_resolved', [False, True])
async def test_concurrent_probe_resolution(migrated, monkeypatch, already_resolved):
    factory = async_sessionmaker(migrated, expire_on_commit=False)
    course, attempt, diagnosis = await diagnostic_event(factory, monkeypatch)
    if already_resolved:
        async with factory() as db:
            await submit_probe_attempt(course.id, attempt.learner_id, diagnosis.id, ProbeAttemptCreate(selected_option_index=0), db)
    # Synchronize immediately before SELECT FOR UPDATE, never after acquiring it.
    barrier = asyncio.Barrier(2)
    class RacingSession(AsyncSession):
        async def scalar(self, statement, *args, **kwargs):
            if getattr(statement, '_for_update_arg', None) is not None and not self.info.get('synchronized'):
                self.info['synchronized'] = True
                await barrier.wait()
            return await super().scalar(statement, *args, **kwargs)
    racing = async_sessionmaker(migrated, class_=RacingSession, expire_on_commit=False)
    async def submit(selected):
        async with racing() as db:
            return await submit_probe_attempt(course.id, attempt.learner_id, diagnosis.id, ProbeAttemptCreate(selected_option_index=selected), db)
    results = await asyncio.wait_for(asyncio.gather(submit(0), submit(1)), timeout=20)
    assert sum(r.resolution_applied for r in results) == (0 if already_resolved else 1)
    assert len({r.diagnostic_outcome for r in results}) == 1
    async with factory() as db:
        attempts = (await db.scalars(select(DiagnosticProbeAttempt))).all()
        assert len(attempts) == 2 + int(already_resolved)
        first = [a for a in attempts if a.applied_outcome]
        assert len(first) == 1
        saved = await db.get(ReasoningDiagnosis, diagnosis.id)
        assert saved.status == first[0].applied_outcome == results[0].diagnostic_outcome
        assert saved.status == ('rejected' if first[0].is_correct else 'confirmed')


@runtime
async def test_unique_resolution_and_scope_fks(migrated, monkeypatch):
    factory = async_sessionmaker(migrated, expire_on_commit=False)
    course, attempt, diagnosis = await diagnostic_event(factory, monkeypatch)
    async with factory() as db:
        result = await submit_probe_attempt(course.id, attempt.learner_id, diagnosis.id, ProbeAttemptCreate(selected_option_index=0), db)
    async with factory() as db:
        values = dict(id=uuid.uuid4(), probe_id=result.probe_id, diagnosis_id=diagnosis.id,
            course_id=course.id, learner_id=attempt.learner_id, selected_option_index=1, is_correct=False, applied_outcome='confirmed')
        with pytest.raises(IntegrityError, match='uq_probe_first_resolution'):
            await db.execute(insert(DiagnosticProbeAttempt).values(**values))
        await db.rollback()
        for field in ['course_id', 'learner_id', 'diagnosis_id', 'probe_id']:
            with pytest.raises(IntegrityError, match='fk_probe_attempt_scope'):
                await db.execute(insert(DiagnosticProbeAttempt).values(**{**values, 'id':uuid.uuid4(), 'applied_outcome':None, field:uuid.uuid4()}))
            await db.rollback()
        # A real, foreign course cannot be paired with the original attempt.
        other = Course(id=uuid.uuid4(), name='Foreign')
        db.add(other)
        await db.commit()
        with pytest.raises(IntegrityError, match='fk_diagnosis_attempt_scope'):
            await db.execute(insert(ReasoningDiagnosis).values(id=uuid.uuid4(), course_id=other.id,
                learner_id=attempt.learner_id, question_id=diagnosis.question_id, attempt_id=attempt.id,
                reasoning_text='Legacy input', reasoning_steps=[], status='insufficient_reasoning',
                evidence_unit_ids=[], citation_snapshots=[]))
        await db.rollback()


@runtime
async def test_migrated_course_cascade(migrated, monkeypatch):
    factory = async_sessionmaker(migrated, expire_on_commit=False)
    course, attempt, diagnosis = await diagnostic_event(factory, monkeypatch, mastery=True)
    async with factory() as db:
        await submit_probe_attempt(course.id, attempt.learner_id, diagnosis.id, ProbeAttemptCreate(selected_option_index=1), db)
    async with factory() as db:
        await db.delete(await db.get(Course, course.id))
        await db.commit()
    async with factory() as db:
        for model in [ReasoningDiagnosis, DiagnosticProbe, DiagnosticProbeAttempt, AssessmentAttempt, LearnerConceptMastery, MasteryObservation, Concept]:
            assert (await db.scalars(select(model))).all() == []


@pytest.mark.skipif(os.getenv('CONCEPTLENS_TEST_MIGRATION_LIFECYCLE') != '1', reason='Opt-in migration lifecycle')
async def test_migration_lifecycle(monkeypatch):
    async with disposable_database('0004') as (engine, name):
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.connect() as conn:
            phase5_tables = set((await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))).scalars()) - {'alembic_version'}
            assert not phase5_tables & PHASE6
        async with factory() as db:
            course, concept, evidence, question, attempt = await seed(db)
            async with db.begin():
                status, _ = await process_mastery_update(db, attempt, course.id, [concept])
                attempt.mastery_update_status = status
        async def snapshot():
            async with engine.connect() as conn:
                return {table: sorted([r[0] for r in (await conn.execute(text(f'SELECT to_jsonb(t)::text FROM "{table}" t'))).all()]) for table in sorted(phase5_tables)}
        before = await snapshot()
        print('Phase 5 seed IDs:', course.id, concept.id, question.id, attempt.id, flush=True)
        print('Phase 5 counts:', {t:len(v) for t,v in before.items()}, flush=True)
        await migrate(engine, name, 'upgrade', '0005')
        assert await snapshot() == before
        async with engine.connect() as conn:
            tables = set((await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))).scalars())
            assert PHASE6 <= tables
            constraints = set((await conn.execute(text("SELECT conname FROM pg_constraint"))).scalars())
            assert {'fk_diagnosis_attempt_scope','fk_probe_diagnosis_scope','fk_probe_attempt_scope','ck_probe_option','ck_probe_attempt_option','uq_probe_diagnosis','ck_diagnosis_status'} <= constraints
            index = await conn.scalar(text("SELECT indexdef FROM pg_indexes WHERE indexname='uq_probe_first_resolution'"))
            assert 'UNIQUE' in index and 'WHERE (applied_outcome IS NOT NULL)' in index
        provider_for(monkeypatch, *payloads(concept, evidence))
        async with factory() as db:
            diag = await create_reasoning_diagnosis(course.id, attempt.learner_id, DiagnosisCreate(attempt_id=attempt.id, reasoning_steps=STEPS), db)
        async with factory() as db:
            await submit_probe_attempt(course.id, attempt.learner_id, diag.id, ProbeAttemptCreate(selected_option_index=1), db)
        other, other_attempt, other_diag = await diagnostic_event(factory, monkeypatch, mastery=True)
        async with factory() as db:
            await submit_probe_attempt(other.id, other_attempt.learner_id, other_diag.id, ProbeAttemptCreate(selected_option_index=0), db)
        async with factory() as db:
            course_to_delete = await db.get(Course, other.id)
            # This historical lifecycle intentionally stops at 0005, before the
            # Phase 7 relationship/table exists; its collection is known empty.
            set_committed_value(course_to_delete, 'learning_sessions', [])
            await db.delete(course_to_delete)
            await db.commit()
        assert await snapshot() == before
        assert '0005' in await migrate(engine, name, 'current')
        assert '0006 (head)' in await migrate(engine, name, 'heads')
        await migrate(engine, name, 'downgrade', '0004')
        assert await snapshot() == before
        async with engine.connect() as conn:
            assert await conn.scalar(text('SELECT version_num FROM alembic_version')) == '0004'
            tables = set((await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))).scalars())
            assert not tables & PHASE6
            assert tables - {'alembic_version'} == phase5_tables
            assert await conn.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname='uq_assessment_attempt_diagnosis_scope'")) == 0
        await migrate(engine, name, 'upgrade', '0005')
        assert await snapshot() == before
        assert '0005' in await migrate(engine, name, 'current')
        async with engine.connect() as conn:
            for table in PHASE6:
                assert await conn.scalar(text(f'SELECT count(*) FROM "{table}"')) == 0
        print('PASS: Phase 5 preserved through upgrade, course cascade, downgrade and re-upgrade; no backfill.', flush=True)
