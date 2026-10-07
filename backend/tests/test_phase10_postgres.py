"""Explicit disposable PostgreSQL lifecycle for 0007; never connects to the app DB."""
import os
import uuid
import pytest
from sqlalchemy import text,update,select,delete
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.models import AssessmentAttempt,Course
from app.schemas.assessment import AssessmentAttemptCreate
from app.services.assessment_grading import grade_attempt
from tests.test_phase10_assessment import typed
from tests.test_reasoning_diagnosis_postgres import disposable_database,migrate

pytestmark=[pytest.mark.asyncio,pytest.mark.skipif(os.getenv('CONCEPTLENS_TEST_POSTGRES')!='1',reason='Explicit disposable PostgreSQL acceptance')]

async def test_phase10_lifecycle_and_typed_attempt_contracts():
    async with disposable_database('0006') as (engine,name):
        cid,qid,aid,lid=[uuid.uuid4() for _ in range(4)]
        async with engine.begin() as conn:
            await conn.execute(text("INSERT INTO courses(id,name) VALUES (:id,'Historical course')"),{'id':cid})
            await conn.execute(text("INSERT INTO assessment_questions(id,course_id,question_type,difficulty,question_text,options,correct_option_index,explanation,evidence_unit_ids,citation_snapshots,verification_status) VALUES (:id,:c,'multiple_choice','medium','Historical question','[\"A\",\"B\",\"C\",\"D\"]',0,'Historical explanation','[]','[]','verified')"),{'id':qid,'c':cid})
            await conn.execute(text('INSERT INTO assessment_attempts(id,course_id,question_id,learner_id,selected_option_index,is_correct) VALUES (:id,:c,:q,:l,0,true)'),{'id':aid,'c':cid,'q':qid,'l':lid})
        async def historical():
            async with engine.connect() as conn:
                return (await conn.execute(text('SELECT question_id,learner_id,selected_option_index,is_correct,created_at FROM assessment_attempts WHERE id=:id'),{'id':aid})).one()
        before=await historical()
        await migrate(engine,name,'upgrade','0007');assert await historical()==before
        factory=async_sessionmaker(engine,expire_on_commit=False)
        async with factory() as db:
            c,_,q,l=await typed(db)
            typed_course_id=c.id
            attempt,result=await grade_attempt(db,q,l,None,response=AssessmentAttemptCreate(learner_id=l,answer_value='8',answer_unit='ticks'))
            attempt_id=attempt.id
            await db.commit();assert result.is_correct and result.mastery_update_status=='updated'
            with pytest.raises(DBAPIError,match='immutable'):
                await db.execute(update(AssessmentAttempt).where(AssessmentAttempt.id==attempt.id).values(is_correct=False))
            await db.rollback()
            with pytest.raises(DBAPIError,match='immutable'):
                await db.execute(delete(AssessmentAttempt).where(AssessmentAttempt.id==aid))
                await db.commit()  # deferred guard must reject isolated deletion
            await db.rollback()
            assert await db.get(AssessmentAttempt,aid) is not None
        # Lossy downgrade must refuse while typed records exist.
        with pytest.raises(AssertionError,match='Downgrade requires'):
            await migrate(engine,name,'downgrade','0006')
        async with factory() as db:
            await db.delete(await db.get(Course,typed_course_id));await db.commit()
        await migrate(engine,name,'downgrade','0006');assert await historical()==before
        await migrate(engine,name,'upgrade','0007');assert await historical()==before
        async with engine.connect() as conn:
            assert await conn.scalar(text('SELECT version_num FROM alembic_version'))=='0007'
            assert await conn.scalar(text('SELECT count(*) FROM diagnostic_sessions'))==0

async def test_fresh_database_head():
    async with disposable_database('head') as (engine,name):
        async with engine.connect() as conn:
            assert await conn.scalar(text('SELECT version_num FROM alembic_version'))=='0007'
            assert await conn.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_name='assessment_questions' AND column_name='grading_contract'"))==1

async def test_concurrent_generation_keeps_exact_question_freshness():
    import asyncio,json
    from tests.test_api_assessment import _seed_course_with_indexed_evidence, SequentialFakeLLMProvider
    from app.services.assessment_generation import generate_assessments
    from app.schemas.assessment import AssessmentGenerationRequest
    async with disposable_database('head') as (engine,name):
        factory=async_sessionmaker(engine,expire_on_commit=False)
        async with factory() as db:
            c,e=await _seed_course_with_indexed_evidence(db)
        draft=dict(questions=[dict(question_text='Which scheduler uses a fixed quantum?',options=['Round Robin','FCFS','SJF','Priority'],correct_option_index=0,explanation='Round Robin rotates using a fixed quantum.',evidence_unit_ids=[str(e.id)])])
        verdict=dict(verifications=[dict(question_index=0,verdict='verified',evidence_unit_ids=[str(e.id)])])
        barrier=asyncio.Barrier(2)
        class Provider(SequentialFakeLLMProvider):
            async def generate(self,**kwargs):
                raw=await super().generate(**kwargs)
                if self.call_count==2:await barrier.wait()
                return raw
        async def generate():
            async with factory() as db:
                return await generate_assessments(db,c.id,AssessmentGenerationRequest(focus='Round Robin CPU scheduling time quantum',count=1),Provider([json.dumps(draft),json.dumps(verdict)]))
        results=await asyncio.wait_for(asyncio.gather(generate(),generate()),20)
        assert sorted(r.generated_count for r in results)==[0,1]
