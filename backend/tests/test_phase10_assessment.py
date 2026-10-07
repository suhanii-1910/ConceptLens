"""Typed grading, no answer leakage, auditable attempts, diagnostic and report evidence."""
import json
import uuid
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func
from app.models import AssessmentQuestion, AssessmentAttempt, Concept, MasteryObservation
from app.schemas.assessment import AssessmentAttemptCreate, TypedQuestionDraft
from app.schemas.assessment_contracts import GradingContract, number
from app.services.typed_assessment import prepare_contract, grade_response
from app.services.assessment_grading import grade_attempt
from tests.test_reasoning_diagnosis import seed
from tests.test_api_assessment import SequentialFakeLLMProvider

async def typed(db,kind='numerical'):
    c,concept,e,q,a=await seed(db)
    question=AssessmentQuestion(id=uuid.uuid4(),course_id=c.id,concepts=[concept],question_type=kind,difficulty='medium',
        question_text='What is the completion time?' if kind=='numerical' else 'Explain remaining execution time.',options=[],
        correct_option_index=None,grading_contract=dict(reference_answer='8 ticks',required_facts=['Remaining execution excludes completed work'],expected_value='8' if kind=='numerical' else None,unit='ticks' if kind=='numerical' else None),
        explanation='P1 continues and completes at 8.',evidence_unit_ids=q.evidence_unit_ids,citation_snapshots=q.citation_snapshots,verification_status='verified')
    db.add(question);await db.commit()
    return c,concept,question,a.learner_id

@pytest.mark.asyncio
@pytest.mark.parametrize('answer,unit,correct',[('8','ticks',True),('8.0','ticks',True),('16/2','TICKS',True),('9','ticks',False),('8','seconds',False)])
async def test_numeric_grade_api_and_leakage(db_session,client,answer,unit,correct):
    c,concept,q,learner=await typed(db_session)
    public=(await client.get(f'/courses/{c.id}/assessments/questions/{q.id}')).json()
    assert not {'grading_contract','expected_value','reference_answer','correct_option_index','explanation'} & public.keys()
    result=await client.post(f'/courses/{c.id}/assessments/questions/{q.id}/attempts',json={'learner_id':str(learner),'answer_value':answer,'answer_unit':unit})
    assert result.status_code==200,result.text
    assert result.json()['is_correct'] is correct and result.json()['mastery_update_status']=='updated'
    repeat=await client.post(f'/courses/{c.id}/assessments/questions/{q.id}/attempts',json={'learner_id':str(learner),'answer_value':'8','answer_unit':'ticks'})
    assert repeat.json()['mastery_update_status']=='skipped_repeated_question'

@pytest.mark.parametrize('value',['nan','inf','1/0','1e100000','a',''])
def test_invalid_number(value):
    with pytest.raises(ValueError):number(value)

@pytest.mark.parametrize('contract',[{'tolerance':'-1'},{'tolerance':'0.1'},{'integer_only':True,'tolerance':'1','tolerance_reason':'rounding'}])
def test_tolerance_must_be_justified(contract):
    with pytest.raises(ValidationError):GradingContract(reference_answer='x',**contract)

@pytest.mark.asyncio
async def test_short_semantic_and_unavailable(db_session,monkeypatch):
    c,concept,q,learner=await typed(db_session,'short_answer')
    from app.services.llm_provider import LLMConfigurationError
    def unavailable():raise LLMConfigurationError('unavailable')
    monkeypatch.setattr('app.services.typed_assessment.get_llm_provider',unavailable)
    _,result=await grade_attempt(db_session,q,learner,None,response=AssessmentAttemptCreate(learner_id=learner,answer_text='Total time less execution already done.'))
    assert result.is_correct is None and result.mastery_update_status is None
    assert await db_session.scalar(select(func.count()).select_from(MasteryObservation))==0
    provider=SequentialFakeLLMProvider([json.dumps(dict(verdict='correct',explanation='Equivalent source-supported meaning.',missing_facts=[],source_supported=True))])
    _,result=await grade_attempt(db_session,q,learner,None,response=AssessmentAttemptCreate(learner_id=learner,answer_text='Subtract completed work from total.'),provider=provider)
    # Existing repeated exposure policy deliberately also excludes earlier ungradable exposure.
    assert result.is_correct and result.mastery_update_status=='skipped_repeated_question'
    assert 'source evidence' in provider.prompts[0]['system']

@pytest.mark.asyncio
async def test_unsupported_short_credit_rejected(db_session):
    c,_,q,l=await typed(db_session,'short_answer')
    provider=SequentialFakeLLMProvider([json.dumps(dict(verdict='correct',explanation='Unsupported claim',missing_facts=[],source_supported=False))])
    r=await grade_response(q,AssessmentAttemptCreate(learner_id=l,answer_text='Invented assertion'),provider=provider,evidence_context=[{'content':'Actual source'}])
    assert r['verdict']=='cannot_grade'

@pytest.mark.asyncio
async def test_attempt_immutable(db_session):
    c,concept,q,learner=await typed(db_session)
    a,_=await grade_attempt(db_session,q,learner,None,response=AssessmentAttemptCreate(learner_id=learner,answer_value='8',answer_unit='ticks'))
    await db_session.commit();a.is_correct=False
    with pytest.raises(ValueError,match='immutable'):await db_session.flush()
    await db_session.rollback()

@pytest.mark.asyncio
async def test_report_and_diagnostic_resume(db_session,client):
    c,concept,q,l=await typed(db_session)
    # Fresh learner; bank contains one mapped concept. Freeze that real sample.
    learner=uuid.uuid4();base=f'/courses/{c.id}/learners/{learner}'
    assert (await client.get(base+'/diagnostic')).json()['status']=='not_started'
    started=await client.post(base+'/diagnostic');assert started.status_code==200,started.text
    data=started.json();assert data['question_count']==1
    assert (await client.post(base+'/diagnostic')).json()['id']==data['id']
    item=data['questions'][0]
    answer={'selected_option_index':0} if item['question_type']=='multiple_choice' else {'answer_value':'8','answer_unit':'ticks'}
    result=await client.post(f'/courses/{c.id}/assessments/questions/{item["id"]}/attempts',json={'learner_id':str(learner),**answer});assert result.status_code==200
    assert (await client.get(base+'/diagnostic')).json()['status']=='complete'
    report=(await client.get(base+'/assessment-report')).json()
    assert report['correct_count']==report['scored_question_count']==1
    assert report['concepts'][0]['status']=='observed_strong'
    assert report['citations'] and report['cannot_grade_count']==0

@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['short_answer','numerical'])
async def test_typed_generation_independent_verifier(db_session,kind):
    from tests.test_api_assessment import _seed_course_with_indexed_evidence
    from app.schemas.assessment import AssessmentGenerationRequest
    from app.services.assessment_generation import generate_assessments
    c,e=await _seed_course_with_indexed_evidence(db_session,'CPU scheduling SRTF selects the process with shortest remaining execution time. For P1 burst 8 arrival 0 and P2 burst 4 arrival 5, P1 continues at 5 and completes at 8.')
    contract=dict(reference_answer='Remaining time excludes execution already done.',required_facts=['Exclude executed work'])
    if kind=='numerical':
        contract.update(reference_answer='8 ticks',expected_value='8',scheduling=dict(scenario=dict(algorithm='srtf',processes=[dict(pid='P1',arrival=0,burst=8),dict(pid='P2',arrival=5,burst=4)]),metric='completion',pid='P1'))
    draft=dict(question_type=kind,question_text='For the stated SRTF processes, when does P1 complete?' if kind=='numerical' else 'What does remaining execution mean in SRTF?',explanation='Compare remaining execution.',evidence_unit_ids=[str(e.id)],grading_contract=contract)
    provider=SequentialFakeLLMProvider([json.dumps(dict(questions=[draft])),json.dumps(dict(verifications=[dict(question_index=0,verdict='verified',evidence_unit_ids=[str(e.id)])]))])
    result=await generate_assessments(db_session,c.id,AssessmentGenerationRequest(focus='CPU scheduling SRTF remaining execution',count=1,question_type=kind),provider)
    assert result.generated_count==1 and provider.call_count==2
    public=result.questions[0].model_dump();assert 'grading_contract' not in public
    stored=await db_session.get(AssessmentQuestion,result.questions[0].id)
    if kind=='numerical':
        assert stored.grading_contract['solution_proof']['processes'][0]['completion']==8
        assert 'authoritative_grading_contracts' in provider.prompts[1]['user']
        assert public['answer_unit']=='ticks'
    else:assert stored.grading_contract['required_facts']==['Exclude executed work']

def test_solver_disagreement_rejected_before_verifier():
    from app.services.llm_provider import InvalidLLMResponseError
    draft=TypedQuestionDraft(question_type='numerical',question_text='When does P complete?',explanation='Source rules.',evidence_unit_ids=[uuid.uuid4()],grading_contract=dict(reference_answer='99',expected_value='99',scheduling=dict(scenario=dict(algorithm='fcfs',processes=[dict(pid='P',arrival=0,burst=8)]),metric='completion',pid='P')))
    with pytest.raises(InvalidLLMResponseError,match='disagrees'):prepare_contract(draft)

@pytest.mark.asyncio
async def test_mixed_report_first_gradable_counts_and_untested(db_session,client,monkeypatch):
    from app.services.llm_provider import LLMConfigurationError
    c,concept,numeric,learner=await typed(db_session)
    untested=Concept(id=uuid.uuid4(),course_id=c.id,name='Untested prerequisite')
    short=AssessmentQuestion(id=uuid.uuid4(),course_id=c.id,concepts=[concept],question_type='short_answer',difficulty='medium',question_text='Explain the selection criterion.',options=[],correct_option_index=None,
        grading_contract=dict(reference_answer='Compare remaining time.',required_facts=['Remaining time']),explanation='Use remaining execution time.',evidence_unit_ids=numeric.evidence_unit_ids,citation_snapshots=numeric.citation_snapshots,verification_status='verified')
    db_session.add_all([untested,short]);await db_session.commit()
    await grade_attempt(db_session,numeric,learner,None,response=AssessmentAttemptCreate(learner_id=learner,answer_value='8',answer_unit='ticks'))
    await grade_attempt(db_session,numeric,learner,None,response=AssessmentAttemptCreate(learner_id=learner,answer_value='9',answer_unit='ticks'))
    def unavailable():raise LLMConfigurationError('unavailable')
    monkeypatch.setattr('app.services.typed_assessment.get_llm_provider',unavailable)
    await grade_attempt(db_session,short,learner,None,response=AssessmentAttemptCreate(learner_id=learner,answer_text='Remaining time.'))
    provider=SequentialFakeLLMProvider([json.dumps(dict(verdict='correct',explanation='Source-supported meaning.',missing_facts=[],source_supported=True))])
    await grade_attempt(db_session,short,learner,None,response=AssessmentAttemptCreate(learner_id=learner,answer_text='Compare the work still left.'),provider=provider)
    await db_session.commit()
    result=await client.get(f'/courses/{c.id}/learners/{learner}/assessment-report');assert result.status_code==200,result.text
    r=result.json();assert (r['attempt_count'],r['scored_question_count'],r['correct_count'],r['cannot_grade_count'],r['repeated_attempts_excluded'])==(5,3,2,1,1)
    assert set(r['by_type'])=={'multiple_choice','short_answer','numerical'}
    assert r['concepts'][0]['status']=='observed_uncertain'
    assert [u['id'] for u in r['untested']]==[str(untested.id)]
    assert not r['prerequisite_concerns'] and len(r['citations'])==2

@pytest.mark.asyncio
async def test_report_confirmed_event_is_distinct(db_session,client,monkeypatch):
    from tests.test_adaptive_learning import confirmed
    c,concept,e,q,a,d=await confirmed(db_session,monkeypatch)
    result=(await client.get(f'/courses/{c.id}/learners/{a.learner_id}/assessment-report')).json()
    assert result['misconceptions'][0]['status']=='confirmed'
    assert result['misconceptions'][0]['hypothesis']==d.hypothesis_text
    assert result['concepts'][0]['status']=='observed_weak'

@pytest.mark.asyncio
async def test_cold_start_generation_participates_in_transaction(db_session,client,monkeypatch):
    from tests.test_api_assessment import _seed_course_with_indexed_evidence
    from app.models.evidence_unit import evidence_concept_link
    from sqlalchemy import insert
    c,e=await _seed_course_with_indexed_evidence(db_session)
    concept=Concept(id=uuid.uuid4(),course_id=c.id,name='Round Robin CPU scheduling')
    db_session.add(concept);await db_session.flush()
    await db_session.execute(insert(evidence_concept_link).values(evidence_unit_id=e.id,concept_id=concept.id));await db_session.commit()
    draft=dict(questions=[dict(question_text='Which rule defines Round Robin?',options=['Fixed quantum','Shortest original job','No preemption','Largest priority'],correct_option_index=0,explanation='A fixed quantum rotates execution.',evidence_unit_ids=[str(e.id)])])
    verdict=dict(verifications=[dict(question_index=0,verdict='verified',evidence_unit_ids=[str(e.id)])])
    provider=SequentialFakeLLMProvider([json.dumps(draft),json.dumps(verdict)])
    monkeypatch.setattr('app.services.assessment_generation.get_llm_provider',lambda:provider)
    base=f'/courses/{c.id}/learners/{uuid.uuid4()}/diagnostic'
    result=await client.post(base);assert result.status_code==200,result.text
    assert result.json()['question_count']==1 and provider.call_count==2
    assert all(str(concept.id) in prompt['user'] for prompt in provider.prompts)
    assert 'tests this single server-selected concept' in provider.prompts[1]['user']
    assert (await client.get(base)).json()['questions']==result.json()['questions']


@pytest.mark.asyncio
async def test_requested_concept_cannot_cross_course(db_session,client,monkeypatch):
    from tests.test_api_assessment import _seed_course_with_indexed_evidence
    c,e=await _seed_course_with_indexed_evidence(db_session)
    provider=SequentialFakeLLMProvider([])
    monkeypatch.setattr('app.services.assessment_generation.get_llm_provider',lambda:provider)
    result=await client.post(f'/courses/{c.id}/assessments/generate',json={'focus':'Round Robin','concept_id':str(uuid.uuid4()),'count':1})
    assert result.status_code==422 and provider.call_count==0
