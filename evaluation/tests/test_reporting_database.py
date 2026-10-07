import copy
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from conceptlens_eval.common import ROOT, envelope, SIMULATION, FIXTURE, PENDING
from conceptlens_eval.database import validate_admin,validate_disposable,check_lifecycle
from conceptlens_eval.grounding import run as grounding_run
from conceptlens_eval.simulation import run as simulate
from conceptlens_eval.reporting import build_report

@pytest.mark.parametrize('value',[
 'postgresql://localhost/conceptlens','postgresql://localhost/conceptlens_eval_abc',
 'sqlite:///postgres','postgresql://remote.example/postgres','postgresql://localhost/postgres?options=-csearch_path=public'])
def test_reject_normal_or_unsafe_admin(value):
    with pytest.raises(ValueError):validate_admin(value)

@pytest.mark.parametrize('name',['conceptlens','postgres','conceptlens_eval_bad','conceptlens_eval_'+'a'*32+';DROP DATABASE conceptlens'])
def test_drop_guard(name):
    with pytest.raises(ValueError):validate_disposable('postgresql://localhost/'+name)


def test_allow_only_exact_eval_namespace():
    assert validate_admin('postgresql://localhost/postgres').database=='postgres'
    assert validate_disposable('postgresql+asyncpg://localhost/conceptlens_eval_'+'a'*32)

@pytest.mark.asyncio
async def test_reporting_labels_and_machine_formats(config,bank,manifest,tmp_path):
    from app.core.config import settings
    with patch.object(settings,'llm_model',None):g=await grounding_run(manifest,ROOT/'evaluation/datasets/grounding.json','test',None)
    s=await simulate(config,bank)
    ge=envelope(g,{},manifest.version); se=envelope(s,config.model_dump(),bank['version'])
    result=build_report(ge,se,tmp_path/'judge')
    text=(tmp_path/'judge/report.md').read_text()
    assert PENDING in text and SIMULATION in text and 'PENDING PROVIDER CONFIGURATION' in text
    assert 'TEST FIXTURE' not in text
    assert json.loads((tmp_path/'judge/summary.json').read_text())['grounding_label']==PENDING
    assert len(list((tmp_path/'judge').glob('*.svg')))==6
    assert (tmp_path/'judge/simulation-sessions.csv').read_text().count(SIMULATION)==60
    assert all(b"\r\n" not in p.read_bytes() for p in (tmp_path/'judge').glob('*.csv'))
    assert 'width="0.00"' not in (tmp_path/'judge/grounding-summary.svg').read_text()
    assert len(json.loads((tmp_path/'judge/phase10-handoff.json').read_text())['priorities'])==5
    se['payload']['label']=FIXTURE
    with pytest.raises(ValueError,match='fixture'):build_report(ge,se,tmp_path/'misleading')
    build_report(ge,se,tmp_path/'fixture-report')
    assert (tmp_path/'fixture-report/report.md').read_text().startswith('# '+FIXTURE)


@pytest.mark.asyncio
async def test_simulation_never_opens_database(config,bank):
    with patch('asyncpg.connect',side_effect=AssertionError('DB access')),patch('sqlalchemy.ext.asyncio.create_async_engine',side_effect=AssertionError('engine')):
        await simulate(config,bank)


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv('CONCEPTLENS_EVAL_ADMIN_URL'),reason='explicit disposable PostgreSQL admin URL not configured')
@pytest.mark.parametrize('fail',[False,True])
async def test_real_disposable_lifecycle(fail):
    r=await check_lifecycle(os.environ['CONCEPTLENS_EVAL_ADMIN_URL'],fail_inside=fail)
    assert not r['normal_development_db_touched']
    assert any(e['action']=='migrated' and e['revision']=='0007' for e in r['events'])
    assert any(e['action']=='dropped' and e['absence_verified'] for e in r['events'])

@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv('CONCEPTLENS_EVAL_ADMIN_URL'),reason='explicit disposable PostgreSQL admin URL not configured')
async def test_full_source_seed_and_postgres_ask_fixture(manifest,tmp_path):
    """Real files/ingestion/index SQL/hybrid search/Ask, deterministic external-model I/O.
    This is TEST FIXTURE — NOT A SUBMISSION RESULT; no scores are persisted.
    """
    import re
    import uuid
    from types import SimpleNamespace as N
    from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
    from sqlalchemy import select,func
    from app.core.config import settings
    from app.services import indexing,retriever,grounded_ask,video_ingestion
    from app.services.embedding_provider import FakeEmbeddingProvider
    from app.models.assessment import AssessmentAttempt
    from app.models.learner_mastery import LearnerConceptMastery
    from conceptlens_eval.database import disposable_database
    from conceptlens_eval.grounding import seed,ask_case
    embedding=FakeEmbeddingProvider()
    script=json.loads((ROOT/'evaluation/datasets/video-script.json').read_text())
    class TranscriptionFixture:
        async def transcribe(self,path):
            return N(segments=[N(text=s['transcript'],start_seconds=s['start'],end_seconds=s['end'],language='en',timestamp_source='authored_test_fixture') for s in script],language='en')
    class GeneratorFixture:
        async def generate(self,*,system_prompt,user_prompt):
            eid=re.findall(r'evidence_unit_id: ([0-9a-f-]+)',user_prompt)[0]
            return json.dumps({'blocks':[{'text':'Deterministic pipeline fixture, not a benchmark answer.','evidence_unit_ids':[eid]}],'next_question':None})
    events=[]
    with patch.object(settings,'upload_dir',str(tmp_path/'uploads')),patch.object(indexing,'get_embedding_provider',return_value=embedding),patch.object(retriever,'get_embedding_provider',return_value=embedding),patch.object(video_ingestion,'MLXWhisperProvider',return_value=TranscriptionFixture()),patch.object(grounded_ask,'get_llm_provider',return_value=GeneratorFixture()),patch('conceptlens_eval.grounding.framework.score',return_value={'label':FIXTURE,'scores':{},'raw':{}}):
        async with disposable_database(os.environ['CONCEPTLENS_EVAL_ADMIN_URL'],events) as url:
            engine=create_async_engine(url)
            try:
                async with async_sessionmaker(engine,expire_on_commit=False)() as db:
                    mapping,ingested=await seed(db,manifest,ROOT/'evaluation/datasets/grounding.json')
                    assert len(mapping)==3 and all(r.get('status')=='ready' for r in ingested[:3])
                    assert ingested[-1]['indexing']['embedded_count']>0
                    course_id=uuid.uuid5(uuid.NAMESPACE_URL,'conceptlens-eval/grounding-course')
                    rows=[await ask_case(db,course_id,c,mapping) for c in manifest.cases if c.split=='development']
                    assert len(rows)==6 and all(r['status'] in {'answered','declined'} for r in rows),rows
                    assert any(r['status']=='answered' and r['retrieved'] and r['citations'] for r in rows)
                    assert any(r['source_id']=='demonstration' for row in rows for r in row['retrieved'])
                    assert await db.scalar(select(func.count()).select_from(AssessmentAttempt))==0
                    assert await db.scalar(select(func.count()).select_from(LearnerConceptMastery))==0
            finally:
                await engine.dispose()
    assert events[-1]['action']=='dropped' and events[-1]['absence_verified']
