"""Real PostgreSQL acceptance, restricted to freshly created disposable databases."""
import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select, text, insert, update, func, inspect, ForeignKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.endpoints import adaptive_learning as api
from app.schemas import adaptive_learning as schema
from app.models import Course, Concept, AssessmentAttempt, AssessmentQuestion, MasteryObservation, LearnerConceptMastery, PrerequisiteEdge
from app.models.adaptive_learning import LearningSession, LearningIntervention, TransferCheck
from app.models.reasoning_diagnosis import ReasoningDiagnosis
from app.services.mastery_update import process_mastery_update
from tests.test_adaptive_learning import confirmed, teaching_provider
from tests.test_api_adaptive_learning import add_prerequisite
from tests.test_reasoning_diagnosis_postgres import disposable_database, migrate

runtime = pytest.mark.skipif(os.getenv('CONCEPTLENS_TEST_POSTGRES') != '1', reason='Opt-in real PostgreSQL Phase 7')
pytestmark = pytest.mark.asyncio
PHASE7 = {'learning_sessions','learning_interventions','transfer_checks'}

@pytest_asyncio.fixture
async def migrated():
    async with disposable_database('head') as (engine, name):
        yield engine

async def start(factory, monkeypatch, *, transfer=False):
    async with factory() as db:
        data = await confirmed(db, monkeypatch)
    provider = teaching_provider(monkeypatch)
    course, concept, evidence, question, attempt, diagnosis = data
    async with factory() as db:
        session = await api.create_learning_session(course.id, attempt.learner_id, schema.SessionCreate(diagnosis_id=diagnosis.id), db)
    if transfer:
        async with factory() as db:
            session = await api.submit_feedback(course.id, attempt.learner_id, session.id,
                schema.FeedbackCreate(intervention_id=session.current_intervention.id,feedback='understood'),db)
    return data, provider, session

def racing_factory(engine):
    barrier = asyncio.Barrier(2)
    class RacingSession(AsyncSession):
        async def scalar(self, statement, *args, **kwargs):
            if getattr(statement, '_for_update_arg', None) is not None and not self.info.get('synchronized'):
                self.info['synchronized'] = True
                await barrier.wait()
            return await super().scalar(statement,*args,**kwargs)
    return async_sessionmaker(engine,class_=RacingSession,expire_on_commit=False)

@runtime
@pytest.mark.parametrize('conflicting', [False, True])
async def test_concurrent_feedback_single_path(migrated,monkeypatch,conflicting):
    factory=async_sessionmaker(migrated,expire_on_commit=False)
    data,provider,session=await start(factory,monkeypatch)
    race=racing_factory(migrated)
    async def submit(value):
        async with race() as db:
            try:
                return await api.submit_feedback(data[0].id,data[4].learner_id,session.id,
                    schema.FeedbackCreate(intervention_id=session.current_intervention.id,feedback=value),db)
            except HTTPException as exc: return exc.status_code
    results=await asyncio.wait_for(asyncio.gather(submit('understood'),submit('still_confused' if conflicting else 'understood')),20)
    assert sum(r==409 for r in results)==1
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(LearningIntervention))==2
        count=await db.scalar(select(func.count()).select_from(TransferCheck))
        assert count<=1
        if not conflicting: assert count==1

@runtime
async def test_concurrent_creation_idempotent(migrated,monkeypatch):
    factory=async_sessionmaker(migrated,expire_on_commit=False)
    async with factory() as db: data=await confirmed(db,monkeypatch)
    provider=teaching_provider(monkeypatch)
    race=racing_factory(migrated)
    async def create():
        async with race() as db:
            return await api.create_learning_session(data[0].id,data[4].learner_id,schema.SessionCreate(diagnosis_id=data[5].id),db)
    results=await asyncio.wait_for(asyncio.gather(create(),create()),20)
    assert results[0].id==results[1].id and len(provider.calls)==2

@runtime
async def test_concurrent_transfer_one_mastery_update(migrated,monkeypatch):
    factory=async_sessionmaker(migrated,expire_on_commit=False)
    data,_,session=await start(factory,monkeypatch,transfer=True)
    race=racing_factory(migrated)
    async def submit(index):
        async with race() as db:
            return await api.submit_transfer_attempt(data[0].id,data[4].learner_id,session.id,schema.LearningAttemptCreate(selected_option_index=index),db)
    results=await asyncio.wait_for(asyncio.gather(submit(0),submit(1)),20)
    assert sorted(r.attempt.mastery_update_status.value for r in results)==['skipped_repeated_question','updated']
    async with factory() as db:
        check=await db.scalar(select(TransferCheck))
        first=next(r for r in results if r.attempt.mastery_update_status=='updated')
        assert check.resolved_attempt_id==first.attempt.attempt_id
        assert check.status==('passed' if first.attempt.is_correct else 'failed')
        assert await db.scalar(select(func.count()).select_from(MasteryObservation))==1
        assert (await db.scalar(select(LearnerConceptMastery))).observation_count==1
        # Even SQL bypassing the ORM cannot replace the historical resolving attempt.
        other=next(r for r in results if r.attempt.attempt_id!=check.resolved_attempt_id)
        with pytest.raises(DBAPIError,match='resolution is immutable'):
            await db.execute(update(TransferCheck).where(TransferCheck.id==check.id).values(resolved_attempt_id=other.attempt.attempt_id))
        await db.rollback()
        with pytest.raises(DBAPIError,match='resolution is immutable'):
            await db.execute(update(TransferCheck).values(status='pending',resolved_attempt_id=None))
        await db.rollback()

@runtime
async def test_database_scope_and_unique_constraints(migrated,monkeypatch):
    factory=async_sessionmaker(migrated,expire_on_commit=False)
    data,_,session=await start(factory,monkeypatch,transfer=True)
    async with factory() as db: foreign=await confirmed(db,monkeypatch)
    async with factory() as db:
        prerequisite,edge=await add_prerequisite(db,data)
        other_prerequisite,other_edge=await add_prerequisite(db,foreign)
    async with factory() as db:
        check=await db.scalar(select(TransferCheck))
        check_id=check.id
        # Real existing UUIDs from another course are still rejected.
        mutations=[(LearningSession,session.id,dict(target_concept_id=foreign[1].id),'fk_.*scope'),
            (TransferCheck,check_id,dict(assessment_question_id=foreign[3].id),'fk_transfer_question_scope'),
            (TransferCheck,check_id,dict(status='failed',resolved_attempt_id=data[4].id),'fk_transfer_attempt_scope')]
        for model,row_id,values,constraint in mutations:
            with pytest.raises(IntegrityError,match=constraint):
                await db.execute(update(model).where(model.id==row_id).values(**values))
            await db.rollback()
        # A real attempt on the correct question by another learner is rejected.
        wrong=AssessmentAttempt(id=uuid.uuid4(),course_id=data[0].id,question_id=session.current_intervention.question.id,
            learner_id=uuid.uuid4(),selected_option_index=0,is_correct=True)
        db.add(wrong); await db.commit()
        with pytest.raises(IntegrityError,match='fk_transfer_attempt_scope'):
            await db.execute(update(TransferCheck).where(TransferCheck.id==check_id).values(status='passed',resolved_attempt_id=wrong.id))
        await db.rollback()
        base=dict(id=uuid.uuid4(),session_id=session.id,course_id=data[0].id,learner_id=data[4].learner_id,
            sequence_index=3,strategy='prerequisite_probe',target_concept_id=data[1].id,
            prerequisite_concept_id=prerequisite.id,prerequisite_edge_id=edge.id,evidence_unit_ids=[],citation_snapshots=[],verified=True,completed=False)
        for values in [dict(prerequisite_concept_id=other_prerequisite.id),dict(prerequisite_edge_id=other_edge.id),dict(assessment_question_id=foreign[3].id),dict(target_concept_id=foreign[1].id)]:
            with pytest.raises(IntegrityError): await db.execute(insert(LearningIntervention).values(**{**base,**values}))
            await db.rollback()
        with pytest.raises(IntegrityError,match='uq_intervention_strategy'):
            await db.execute(insert(LearningIntervention).values(**{**base,'strategy':'source_explanation'}))
        await db.rollback()
        with pytest.raises(IntegrityError,match='uq_transfer_session'):
            await db.execute(insert(TransferCheck).values(id=uuid.uuid4(),session_id=session.id,course_id=data[0].id,
                learner_id=data[4].learner_id,target_concept_id=data[1].id,assessment_question_id=data[3].id,status='pending'))
        await db.rollback()

@runtime
async def test_whole_course_cascade(migrated,monkeypatch):
    factory=async_sessionmaker(migrated,expire_on_commit=False)
    data,_,session=await start(factory,monkeypatch)
    async with factory() as db:
        await add_prerequisite(db,data)
    for _ in range(2):
        async with factory() as db:
            session=await api.submit_feedback(data[0].id,data[4].learner_id,session.id,
                schema.FeedbackCreate(intervention_id=session.current_intervention.id,feedback='still_confused'),db)
    probe_id=session.current_intervention.id
    async with factory() as db:
        result=await api.submit_prerequisite_attempt(data[0].id,data[4].learner_id,session.id,probe_id,
            schema.LearningAttemptCreate(selected_option_index=1),db)
    async with factory() as db:
        session=await api.choose_prerequisite(data[0].id,data[4].learner_id,session.id,
            schema.PrerequisiteChoice(intervention_id=probe_id,choice='practice_prerequisite'),db)
    async with factory() as db:
        result=await api.submit_prerequisite_attempt(data[0].id,data[4].learner_id,session.id,session.current_intervention.id,
            schema.LearningAttemptCreate(selected_option_index=0),db)
        session=result.session
    async with factory() as db:
        session=await api.submit_feedback(data[0].id,data[4].learner_id,session.id,
            schema.FeedbackCreate(intervention_id=session.current_intervention.id,feedback='understood'),db)
    async with factory() as db:
        await api.submit_transfer_attempt(data[0].id,data[4].learner_id,session.id,schema.LearningAttemptCreate(selected_option_index=0),db)
    async with factory() as db:
        await db.delete(await db.get(Course,data[0].id)); await db.commit()
    async with factory() as db:
        for model in [LearningSession,LearningIntervention,TransferCheck,AssessmentAttempt,AssessmentQuestion,
                      ReasoningDiagnosis,MasteryObservation,LearnerConceptMastery,Concept]:
            assert await db.scalar(select(func.count()).select_from(model))==0

@runtime
async def test_failed_transition_rolls_back_postgres(migrated,monkeypatch):
    factory=async_sessionmaker(migrated,expire_on_commit=False)
    data,provider,session=await start(factory,monkeypatch,transfer=True)
    provider.change_verdict=lambda v:{**v,'verdict':'rejected'}
    async with factory() as db:
        with pytest.raises(HTTPException,match='rejected'):
            await api.submit_transfer_attempt(data[0].id,data[4].learner_id,session.id,schema.LearningAttemptCreate(selected_option_index=1),db)
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(AssessmentAttempt))==1
        assert await db.scalar(select(func.count()).select_from(MasteryObservation))==0
        assert await db.scalar(select(func.count()).select_from(LearnerConceptMastery))==0
        assert (await db.scalar(select(TransferCheck))).status=='pending'
        assert (await db.get(LearningSession,session.id)).current_action=='transfer_check'

@pytest.mark.skipif(os.getenv('CONCEPTLENS_TEST_MIGRATION_LIFECYCLE')!='1',reason='Opt-in Phase 7 migration lifecycle')
async def test_phase7_migration_lifecycle(monkeypatch):
    async with disposable_database('0005') as (engine,name):
        factory=async_sessionmaker(engine,expire_on_commit=False)
        # Only fixture setup/runtime use the current ORM schema; snapshots exercise exact historical revisions.
        await migrate(engine,name,'upgrade','head')
        async with factory() as db:
            original=await confirmed(db,monkeypatch)
            await add_prerequisite(db,original)
            async with db.begin():
                status,_=await process_mastery_update(db,original[4],original[0].id,[original[1]])
                original[4].mastery_update_status=status
        await migrate(engine,name,'downgrade','0005')
        async with engine.connect() as conn:
            old_tables=set((await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))).scalars())-{'alembic_version'}
            assert not PHASE7 & old_tables
        async def snapshot():
            async with engine.connect() as conn:
                return {t:sorted((await conn.execute(text(f'SELECT to_jsonb(t)::text FROM "{t}" t'))).scalars()) for t in sorted(old_tables)}
        before=await snapshot()
        print('Original Phase 0–6 counts:',{t:len(rows) for t,rows in before.items()},flush=True)
        await migrate(engine,name,'upgrade','0006')
        assert await snapshot()==before
        async with engine.connect() as conn:
            def check_schema(connection):
                inspector=inspect(connection)
                for model in [LearningSession,LearningIntervention,TransferCheck]:
                    table=model.__table__
                    assert {(c['name'],c['nullable']) for c in inspector.get_columns(table.name)} == {(c.name,c.nullable) for c in table.columns}
                    actual={(tuple(c['constrained_columns']),c['referred_table'],tuple(c['referred_columns']),c['options'].get('ondelete')) for c in inspector.get_foreign_keys(table.name)}
                    expected={(tuple(c.column_keys),c.referred_table.name,tuple(e.column.name for e in c.elements),c.ondelete) for c in table.constraints if isinstance(c,ForeignKeyConstraint)}
                    assert actual==expected
                    assert {tuple(c['column_names']) for c in inspector.get_unique_constraints(table.name)} == {tuple(c.columns.keys()) for c in table.constraints if isinstance(c,UniqueConstraint)}
                    assert {c['name'] for c in inspector.get_check_constraints(table.name)} == {c.name for c in table.constraints if isinstance(c,CheckConstraint)}
            await conn.run_sync(check_schema)
            for table in PHASE7: assert await conn.scalar(text(f'SELECT count(*) FROM "{table}"'))==0
        await migrate(engine,name,'upgrade','head')
        # Keep original rows untouched, add a separate fully populated Phase 7 course.
        data,_,session=await start(factory,monkeypatch,transfer=True)
        async with factory() as db:
            await api.submit_transfer_attempt(data[0].id,data[4].learner_id,session.id,schema.LearningAttemptCreate(selected_option_index=0),db)
        # Independently exercise a complete separate-course cascade.
        separate,_,second=await start(factory,monkeypatch,transfer=True)
        async with factory() as db:
            await api.submit_transfer_attempt(separate[0].id,separate[4].learner_id,second.id,schema.LearningAttemptCreate(selected_option_index=0),db)
        async with factory() as db:
            await db.delete(await db.get(Course,separate[0].id)); await db.commit()
        await migrate(engine,name,'downgrade','0006')
        after=await snapshot()
        for table,rows in before.items(): assert set(rows)<=set(after[table]),table
        assert '0006' in await migrate(engine,name,'current')
        await migrate(engine,name,'downgrade','0005')
        assert await snapshot()==after
        async with engine.connect() as conn:
            tables=set((await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))).scalars())-{'alembic_version'}
            assert tables==old_tables and not tables & PHASE7
            assert await conn.scalar(text("SELECT count(*) FROM pg_proc WHERE proname='protect_transfer_resolution'"))==0
            assert await conn.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname IN ('uq_concept_learning_scope','uq_question_learning_scope','uq_edge_learning_scope')"))==0
        await migrate(engine,name,'upgrade','0006')
        assert await snapshot()==after
        async with engine.connect() as conn:
            for table in PHASE7: assert await conn.scalar(text(f'SELECT count(*) FROM "{table}"'))==0
        print('PASS Phase 6 preserved; downgrade removes only Phase 7; re-upgrade has no backfill.',flush=True)
