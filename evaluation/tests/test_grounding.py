import copy
import json
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from conceptlens_eval.common import ROOT, PENDING, REAL, FIXTURE
from conceptlens_eval.dataset import Manifest, Locator, resolve_source, load_manifest
from conceptlens_eval.metrics import locator_matches, case_metrics, aggregate, failures
from conceptlens_eval.grounding import run, ask_case, normalize_locator
from conceptlens_eval.framework import score, METRICS


def test_manifest(manifest):
    assert len(manifest.cases)==18
    assert {s:sum(c.split==s for c in manifest.cases) for s in ['development','test']}=={'development':6,'test':12}
    assert len({c.case_type for c in manifest.cases})==6
    assert {e.locator.kind for c in manifest.cases for e in c.expected}=={'page','slide','time'}

@pytest.mark.parametrize('mutation',[
    lambda d:d['cases'].append(d['cases'][0]),
    lambda d:d['sources'].append(d['sources'][0]),
    lambda d:d['cases'][0].update(expected=[]),
    lambda d:d['cases'][0].update(modality='audio'),
    lambda d:d['cases'][0].update(modality='figure'),
    lambda d:d['cases'][0].update(supported=False),
    lambda d:d['cases'][0]['expected'][0].update(source_id='missing'),
    lambda d:d['cases'][0]['expected'][0].update(locator={'kind':'slide','number':1}),
    lambda d:d['sources'][0].update(path='../aster-memory.pdf'),
    lambda d:d['sources'][0].update(filename='aster-operations.pptx'),
    lambda d:d['cases'][0].update(split='train'),
    lambda d:d['cases'][0].update(unexpected='field'),
])
def test_invalid_manifest(manifest,mutation):
    data=manifest.model_dump(); mutation(data)
    with pytest.raises(ValidationError): Manifest.model_validate(data)

@pytest.mark.parametrize('value',[{'kind':'page'}, {'kind':'page','number':0}, {'kind':'page','number':True},
    {'kind':'slide','number':-1},{'kind':'time','start':-1.,'end':2.},{'kind':'time','start':3.,'end':2.},
    {'kind':'time','start':0.},{'kind':'time','start':0.,'end':float('inf')},{'kind':'time','start':0.,'end':float('nan')},
    {'kind':'page','number':1,'start':0.},{'kind':'time','start':0.,'end':1.,'number':1}])
def test_bad_locators(value):
    with pytest.raises(ValidationError): Locator.model_validate(value)


def test_asset_hash_and_escape(manifest,tmp_path):
    data=manifest.model_dump()
    path=tmp_path/'manifest.json'; path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='missing'):load_manifest(path)


def test_source_resolution(manifest):
    s=manifest.sources[0]; r={'filename':s.filename,'sha256':s.sha256,'id':'runtime-only'}
    assert resolve_source(s,[r])==r
    for rows in [[],[r,r],[{**r,'sha256':'0'*64}]]:
        with pytest.raises(ValueError):resolve_source(s,rows)

@pytest.mark.parametrize('kind',['page','slide'])
def test_page_slide(kind):
    assert locator_matches({'kind':kind,'number':2},{'kind':kind,'number':2})
    assert not locator_matches({'kind':kind,'number':2},{'kind':kind,'number':3})
    assert not locator_matches({'kind':kind,'number':2},{})
    assert not locator_matches({'kind':kind,'number':2},{'kind':'time','start':2.,'end':2.})

@pytest.mark.parametrize('actual,expected_result',[(dict(start=5.,end=10.),True),(dict(start=5.,end=9.9),False),
    (dict(start=0.,end=20.),True),(dict(start=10.,end=15.),False),(dict(start=6.,end=7.),False)])
def test_video_overlap(actual,expected_result):
    assert locator_matches(dict(kind='time',start=0.,end=10.),dict(kind='time',**actual)) is expected_result


def test_video_point():
    assert locator_matches(dict(kind='time',start=5.,end=5.),dict(kind='time',start=4.,end=5.))
    assert not locator_matches(dict(kind='time',start=5.,end=5.),dict(kind='time',start=5.1,end=6.))


def result(case,status='answered',expected=None):
    evidence=expected if expected is not None else [e.model_dump() for e in case.expected]
    return dict(case_id=case.case_id,status=status,retrieved=evidence,citations=evidence if status=='answered' else [],answer='example',framework={'scores':{}})


def test_custom_metrics(manifest):
    case=manifest.cases[0]; r=result(case)
    m=case_metrics(case,r)
    assert m['citation_source_accuracy']==m['citation_locator_accuracy']==m['retrieval_source_recall']==m['evidence_coverage']==1
    wrong=copy.deepcopy(r); wrong['citations'][0]['locator']['number']=99
    m=case_metrics(case,wrong)
    assert m['citation_source_accuracy']==1 and m['citation_locator_accuracy']==0
    wrong['citations'][0]['source_id']='wrong'; assert case_metrics(case,wrong)['citation_source_accuracy']==0
    empty=result(case,expected=[]); m=case_metrics(case,empty)
    assert m['citation_source_accuracy'] is None and m['missing_citation'] and m['evidence_coverage']==0
    assert {'citation','retrieval_source_recall','evidence_coverage'} <= {f['failed_metric'] for f in failures(case,empty)}


def test_cross_source_coverage(manifest):
    c=next(c for c in manifest.cases if c.case_type=='cross_source')
    m=case_metrics(c,result(c,expected=[c.expected[0].model_dump()]))
    assert m['retrieval_source_recall']==1 and m['evidence_coverage']==0.5


def test_refusal_confusion(manifest):
    supported=[c for c in manifest.cases if c.supported][:2]
    unsupported=[c for c in manifest.cases if not c.supported][:2]
    cases=[*supported,*unsupported]
    rows=[result(c,status) for c,status in zip(cases,['answered','declined','declined','answered'])]
    m=aggregate(cases,rows)
    assert m['confusion']==dict(TP=1,TN=1,FP=1,FN=1)
    assert all(m[k]==0.5 for k in ['refusal_accuracy','refusal_precision','refusal_recall','refusal_f1'])
    rows=[result(c,'error') for c in cases]
    assert aggregate(cases,rows)['cases_scored']==0
    assert aggregate(cases,rows)['refusal_accuracy'] is None


def test_normalize_no_invented_location():
    assert normalize_locator('pdf',{'page_number':2})==dict(kind='page',number=2)
    assert normalize_locator('pptx',{'slide_number':3})==dict(kind='slide',number=3)
    assert normalize_locator('video',{'timestamp_seconds':5})==dict(kind='time',start=5.,end=5.)
    assert normalize_locator('pdf',{'page_index':0})=={}


def test_framework_absence_no_scores():
    r=score({},environment={})
    assert r['label']==PENDING and r['status']=='pending'
    assert set(r['scores'])==set(METRICS) and all(v is None for v in r['scores'].values())

@pytest.mark.parametrize('verdict',[0,1])
def test_actual_ragas_fixture(verdict):
    sample=dict(user_input='What is a page?',response='A page is a block.',reference='A page is a block.',retrieved_contexts=['A page is a block.'])
    r=score(sample,fixture=True,fixture_verdict=verdict,environment={})
    assert r['label']==FIXTURE and r['version']=='0.4.3' and r['status']=='scored',r
    assert set(r['scores'])==set(METRICS)
    for key,value in r['scores'].items():
        assert value==pytest.approx(verdict,abs=1e-8)
        assert r['raw'][key]['implementation'].startswith('ragas.metrics.collections.')
        assert r['raw'][key]['judgments']

@pytest.mark.asyncio
async def test_pending_grounding_never_opens_db(manifest):
    from app.core.config import settings
    with patch.object(settings,'llm_model',None),patch('conceptlens_eval.grounding.disposable_database',side_effect=AssertionError('DB accessed')):
        r=await run(manifest,ROOT/'evaluation/datasets/grounding.json','test',None)
    assert r['label']==PENDING and not r['real_pipeline_run']
    assert len(r['cases'])==12 and all(m['mean'] is None and m['n']==0 for m in r['framework_metrics'].values())
    assert r['custom_metrics']['cases_scored']==0
    assert set(r['by_modality'])=={'text','table','video','mixed','none','figure'}

@pytest.mark.asyncio
async def test_configured_grounding_requires_explicit_admin(manifest):
    from app.core.config import settings
    with patch.object(settings,'llm_model','fixture'),patch.object(settings,'llm_api_key','fixture'),patch.object(settings,'llm_base_url','http://fixture'):
        with pytest.raises(ValueError,match='no app DB fallback'):
            await run(manifest,ROOT/'evaluation/datasets/grounding.json','test',None)

@pytest.mark.asyncio
async def test_capture_actual_ask_pipeline(manifest):
    """Actual boundary/Ask parsing/citation validation; only retrieval and provider are fixture I/O."""
    from app.services import grounded_ask
    from app.schemas.retrieval import RetrievalResultItem,Citation
    case=manifest.cases[0]; course,source,eid=uuid4(),uuid4(),uuid4()
    citation=Citation(evidence_unit_id=eid,course_id=course,source_version_id=source,source_filename='aster-memory.pdf',source_type='pdf',modality='text',locator={'page_number':1},location_metadata={'page_number':1},locator_label='Page 1')
    item=RetrievalResultItem(evidence_unit_id=eid,course_id=course,source_version_id=source,source_filename='aster-memory.pdf',modality='text',original_text='A virtual page is a block of virtual addresses.',dense_distance=0.1,dense_rank=1,lexical_rank=1,lexical_score=1.,grounding_status='valid',citation=citation)
    provider=N(generate=AsyncMock(return_value=json.dumps({'blocks':[{'text':'A virtual page is a block of virtual addresses.','evidence_unit_ids':[str(eid)]}],'next_question':None})))
    mapping={str(source):{'source_id':'memory','sha256':manifest.sources[0].sha256,'kind':'pdf'}}
    with patch.object(grounded_ask,'hybrid_search',AsyncMock(return_value=[item])),patch.object(grounded_ask,'ground_retrieval_results',AsyncMock(return_value=[item])),patch.object(grounded_ask,'get_llm_provider',return_value=provider),patch('conceptlens_eval.grounding.framework.score',return_value={'label':FIXTURE,'scores':{},'raw':{}}):
        row=await ask_case(None,course,case,mapping)
    assert row['status']=='answered',row
    assert row['retrieved'][0]['source_id']=='memory' and row['citations'][0]['locator']==dict(kind='page',number=1)
    assert row['answer_contexts']==[item.original_text]
    provider.generate.assert_awaited_once()


def test_framework_roundoff_is_not_a_failure(manifest):
    c=manifest.cases[0]; r=result(c)
    r['framework']={'scores':{'context_precision':.9999999999},'raw':{}}
    assert failures(c,r)==[]
    r['framework']['raw']={'faithfulness':{'status':'error'}}
    assert any(f['reason']=='framework metric unavailable: error' for f in failures(c,r))


def test_raster_figure_and_authored_table():
    import pymupdf
    with pymupdf.open(ROOT/'evaluation/datasets/sources/aster-memory.pdf') as document:
        assert 'Cedar' in document[2].get_text() and '150' in document[2].get_text()
        assert document[3].get_images()
        assert 'Violet queue' not in document[3].get_text() and 'Amber gate' not in document[3].get_text()
