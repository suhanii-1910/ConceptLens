"""Phase 6 endpoint trust boundaries, immutable audit trail and atomic writes."""

import json
import uuid

import pytest
from sqlalchemy import event, func, select, update

from app.models import Course, Concept, PrerequisiteEdge, AssessmentAttempt, AssessmentQuestion, LearnerConceptMastery, MasteryObservation
from app.models.reasoning_diagnosis import ReasoningDiagnosis, DiagnosticProbe, DiagnosticProbeAttempt
from app.services.llm_provider import LLMConfigurationError, LLMProviderError, InvalidLLMResponseError
from tests.test_api_assessment import SequentialFakeLLMProvider
from tests.test_reasoning_diagnosis import seed, payloads, provider_for, STEPS

pytestmark = pytest.mark.asyncio


def base(course, attempt):
    return f"/courses/{course.id}/learners/{attempt.learner_id}/reasoning-diagnoses"


async def create(client, course, attempt, **extra):
    return await client.post(base(course,attempt), json={"attempt_id":str(attempt.id), "reasoning_steps":STEPS, **extra})


async def counts(db):
    return [await db.scalar(select(func.count()).select_from(m)) for m in [ReasoningDiagnosis, DiagnosticProbe, DiagnosticProbeAttempt, LearnerConceptMastery, MasteryObservation]]


async def prepared(client, db, monkeypatch):
    course, concept, evidence, question, attempt = await seed(db)
    draft, verdict = payloads(concept, evidence)
    provider = provider_for(monkeypatch, draft, verdict)
    response = await create(client, course, attempt)
    assert response.status_code == 200, response.text
    return course, concept, evidence, question, attempt, response.json(), provider


async def test_verified_hypothesis_exact_verifier_citations_hidden_keys_and_no_mastery(client, db_session, monkeypatch):
    course, concept, evidence, question, attempt, data, provider = await prepared(client,db_session,monkeypatch)
    assert data['status'] == 'hypothesis'
    assert data['hypothesis_text'].startswith('The learner may be')
    assert data['reasoning_steps'] == STEPS and data['first_break_step_index'] == 3
    assert data['first_break_excerpt'] == STEPS[3]
    assert data['target_concept_id'] == str(concept.id)
    assert data['citations'] == data['probe']['citations'] == [question.citation_snapshots[1]]
    assert data['cold_start'] is True and data['prerequisites'] == []
    fetched = await client.get(base(course,attempt)+'/'+data['id'])
    assert fetched.json() == data
    for content in [data, fetched.json()]:
        assert 'correct_option_index' not in json.dumps(content)
        assert 'explanation' not in content['probe']
        assert '/private/' not in json.dumps(content)
    assert provider.call_count == 2
    assert await counts(db_session) == [1,1,0,0,0]
    await db_session.refresh(question)
    await db_session.refresh(attempt)
    assert attempt.mastery_update_status is None and attempt.selected_option_index == 1
    assert len(question.citation_snapshots) == 2


@pytest.mark.parametrize('selected,expected', [(0,'rejected'),(1,'confirmed')])
async def test_first_probe_grading_repeat_cannot_flip(client,db_session,monkeypatch,selected,expected):
    course, _, _, q, attempt, data, provider = await prepared(client,db_session,monkeypatch)
    url=base(course,attempt)+'/'+data['id']+'/probe-attempts'
    first=(await client.post(url,json={'selected_option_index':selected})).json()
    assert first['is_correct'] == (selected==0)
    assert first['correct_option_index']==0 and first['explanation']
    assert first['citations']==[q.citation_snapshots[1]]
    assert first['diagnostic_outcome']==expected and first['resolution_applied']
    repeat=(await client.post(url,json={'selected_option_index':1-selected})).json()
    assert repeat['diagnostic_outcome']==expected and not repeat['resolution_applied']
    assert repeat['attempt_id']!=first['attempt_id']
    assert (await client.get(base(course,attempt)+'/'+data['id'])).json()['status']==expected
    assert await counts(db_session)==[1,1,2,0,0]
    assert provider.call_count==2


@pytest.mark.parametrize('variant', ['missing','learner','course','question_course','unverified'])
async def test_eligibility(client,db_session,monkeypatch,variant):
    course, concept, evidence, question, attempt=await seed(db_session)
    provider=provider_for(monkeypatch,*payloads(concept,evidence))
    aid=attempt.id
    url=base(course,attempt)
    if variant=='missing': aid=uuid.uuid4()
    if variant=='learner': url=url.replace(str(attempt.learner_id),str(uuid.uuid4()))
    if variant=='course': url=url.replace(str(course.id),str(uuid.uuid4()))
    if variant=='unverified': question.verification_status='rejected'
    if variant=='question_course':
        other=Course(id=uuid.uuid4(),name='Other')
        db_session.add(other)
        question.course_id=other.id
    await db_session.commit()
    r=await client.post(url,json={'attempt_id':str(aid),'reasoning_steps':STEPS})
    assert r.status_code==404
    assert provider.call_count==0 and await counts(db_session)==[0,0,0,0,0]


@pytest.mark.parametrize('body', [{}, {'reasoning_text':' '}, {'reasoning_steps':[' ']}, {'reasoning_steps':['x']*21}, {'reasoning_text':'x'*8001}, {'reasoning_text':'valid input', 'citation':{}}])
async def test_api_input_validation(client,body):
    r=await client.post(f'/courses/{uuid.uuid4()}/learners/{uuid.uuid4()}/reasoning-diagnoses',json={'attempt_id':str(uuid.uuid4()),**body})
    assert r.status_code==422


@pytest.mark.parametrize('mutation', ['index','excerpt','concept','evidence','probe_evidence','verifier_evidence','verifier_probe_evidence','citation','prerequisite','repeat','bad_uuid','boolean_index'])
async def test_tampered_model_output_fails_closed(client,db_session,monkeypatch,mutation):
    course, concept, evidence, question, attempt=await seed(db_session)
    draft,verdict=payloads(concept,evidence)
    if mutation=='index': draft['first_break_step_index']=4
    if mutation=='boolean_index': draft['first_break_step_index']=True
    if mutation=='excerpt': draft['first_break_excerpt']='Never said this'
    if mutation=='concept': draft['target_concept_id']=str(uuid.uuid4())
    if mutation=='bad_uuid': draft['target_concept_id']='not-a-uuid'
    if mutation=='evidence': draft['evidence_unit_ids']=[str(uuid.uuid4())]
    if mutation=='probe_evidence': draft['probe']['evidence_unit_ids']=[str(uuid.uuid4())]
    if mutation=='verifier_evidence': verdict['evidence_unit_ids']=[str(uuid.uuid4())]
    if mutation=='verifier_probe_evidence': verdict['probe_evidence_unit_ids']=[str(uuid.uuid4())]
    if mutation=='citation': draft['probe']['page_number']=99
    if mutation=='prerequisite': draft['prerequisite_ids']=[str(uuid.uuid4())]
    if mutation=='repeat': draft['probe']['question_text']=question.question_text
    provider_for(monkeypatch,draft,verdict)
    r=await create(client,course,attempt)
    assert r.status_code==502,r.text
    assert await counts(db_session)==[0,0,0,0,0]


@pytest.mark.parametrize('field', ['verdict','first_break_supported','hypothesis_supported','target_allowed','probe_isolates_hypothesis','probe_answer_supported','probe_is_fresh','public_content_safe'])
async def test_verifier_rejection_never_persists_hypothesis(client,db_session,monkeypatch,field):
    course,concept,evidence,_,attempt=await seed(db_session)
    draft,verdict=payloads(concept,evidence)
    verdict[field]='rejected' if field=='verdict' else False
    provider_for(monkeypatch,draft,verdict)
    r=await create(client,course,attempt)
    assert r.status_code==200,r.text
    data=r.json()
    assert data['status']=='no_clear_break'
    assert data['probe'] is data['hypothesis_text'] is data['first_break_excerpt'] is None
    assert await counts(db_session)==[1,0,0,0,0]


@pytest.mark.parametrize('outcome',['no_clear_break','insufficient_reasoning','insufficient_evidence'])
async def test_no_fault_outcomes(client,db_session,monkeypatch,outcome):
    course,concept,evidence,_,attempt=await seed(db_session)
    _,verdict=payloads(concept,evidence)
    verdict.update(evidence_unit_ids=[],probe_evidence_unit_ids=[])
    provider_for(monkeypatch,{'outcome':outcome,'observed_reasoning':'No supported interpretation is available.'},verdict)
    r=await create(client,course,attempt)
    assert r.json()['status']==outcome and r.json()['probe'] is None
    assert (await client.post(base(course,attempt)+'/'+r.json()['id']+'/probe-attempts',json={'selected_option_index':0})).status_code==422


async def test_too_short_reasoning_no_provider(client,db_session,monkeypatch):
    course,concept,evidence,_,attempt=await seed(db_session)
    provider=provider_for(monkeypatch,*payloads(concept,evidence))
    r=await create(client,course,attempt,reasoning_steps=[],reasoning_text="I guess")
    assert r.json()['status']=='insufficient_reasoning' and provider.call_count==0


async def test_text_only_first_break(client,db_session,monkeypatch):
    course,concept,evidence,_,attempt=await seed(db_session)
    draft,verdict=payloads(concept,evidence)
    draft['first_break_step_index']=None
    provider_for(monkeypatch,draft,verdict)
    r=await create(client,course,attempt,reasoning_steps=[],reasoning_text=STEPS[3])
    assert r.status_code==200 and r.json()['first_break_step_index'] is None


@pytest.mark.parametrize('variant',['missing_evidence','foreign_evidence','foreign_concept','no_mapping'])
async def test_frozen_context_isolation(client,db_session,monkeypatch,variant):
    from app.models.learner_mastery import assessment_question_concept_link
    course,concept,evidence,q,attempt=await seed(db_session)
    foreign,foreign_concept,foreign_evidence,_,_=await seed(db_session)
    if variant=='missing_evidence': q.evidence_unit_ids=[str(uuid.uuid4())]
    if variant=='foreign_evidence':
        q.evidence_unit_ids=[str(foreign_evidence[0].id)]
        q.citation_snapshots=[validate_citation for validate_citation in (await db_session.scalar(select(AssessmentQuestion).where(AssessmentQuestion.course_id==foreign.id))).citation_snapshots[:1]]
    if variant in {'foreign_concept','no_mapping'}:
        await db_session.execute(assessment_question_concept_link.delete().where(assessment_question_concept_link.c.question_id==q.id))
        if variant=='foreign_concept':
            await db_session.execute(assessment_question_concept_link.insert().values(question_id=q.id,concept_id=foreign_concept.id))
    await db_session.commit()
    provider=provider_for(monkeypatch,*payloads(concept,evidence))
    r=await create(client,course,attempt)
    assert r.json()['status']=='insufficient_evidence' and provider.call_count==0


async def test_existing_prerequisites_only(client,db_session,monkeypatch):
    course,concept,evidence,_,attempt=await seed(db_session)
    prior=Concept(id=uuid.uuid4(),course_id=course.id,name='Subtraction')
    foreign=Course(id=uuid.uuid4(),name='Foreign')
    foreign_concept=Concept(id=uuid.uuid4(),course=foreign,name='Foreign')
    db_session.add_all([prior,foreign,foreign_concept])
    await db_session.flush()
    edge=PrerequisiteEdge(id=uuid.uuid4(),course_id=course.id,prerequisite_concept_id=prior.id,target_concept_id=concept.id,relation_type='requires')
    bad=PrerequisiteEdge(id=uuid.uuid4(),course_id=course.id,prerequisite_concept_id=foreign_concept.id,target_concept_id=concept.id,relation_type='requires')
    db_session.add_all([edge,bad])
    await db_session.commit()
    provider_for(monkeypatch,*payloads(concept,evidence))
    r=await create(client,course,attempt)
    assert [p['edge_id'] for p in r.json()['prerequisites']]==[str(edge.id)]


@pytest.mark.parametrize('error,code',[(LLMConfigurationError('secret'),503),(LLMProviderError('secret'),503),(InvalidLLMResponseError('secret'),502)])
async def test_provider_failures(client,db_session,monkeypatch,error,code):
    course,_,_,_,attempt=await seed(db_session)
    monkeypatch.setattr('app.services.reasoning_diagnosis.get_llm_provider',lambda:SequentialFakeLLMProvider(error=error))
    r=await create(client,course,attempt)
    assert r.status_code==code and 'secret' not in r.text
    assert await counts(db_session)==[0,0,0,0,0]


async def test_malformed_second_response_rolls_back(client,db_session,monkeypatch):
    course,concept,evidence,_,attempt=await seed(db_session)
    draft,_=payloads(concept,evidence)
    monkeypatch.setattr('app.services.reasoning_diagnosis.get_llm_provider',lambda:SequentialFakeLLMProvider([json.dumps(draft),'not json']))
    assert (await create(client,course,attempt)).status_code==502
    assert await counts(db_session)==[0,0,0,0,0]


async def test_context_bounded(client,db_session,monkeypatch):
    course,concept,evidence,_,attempt=await seed(db_session)
    for eu in evidence: eu.original_text='s'*100000
    await db_session.commit()
    provider=provider_for(monkeypatch,*payloads(concept,evidence))
    assert (await create(client,course,attempt)).status_code==200
    for prompt in provider.prompts:
        assert len(prompt['user'])<=64000
        assert '/private/' not in prompt['user']
        assert 'UNTRUSTED DATA' in prompt['system']


@pytest.mark.parametrize('model',[ReasoningDiagnosis,DiagnosticProbe])
async def test_create_atomicity(client,db_session,monkeypatch,model):
    course,concept,evidence,_,attempt=await seed(db_session)
    provider_for(monkeypatch,*payloads(concept,evidence))
    def fail(*args): raise RuntimeError('injected persistence failure')
    event.listen(model,'before_insert',fail)
    try:
        with pytest.raises(RuntimeError,match='injected'):
            await create(client,course,attempt)
    finally: event.remove(model,'before_insert',fail)
    assert await counts(db_session)==[0,0,0,0,0]


async def test_resolution_atomicity(client,db_session,monkeypatch):
    course,_,_,_,attempt,data,_=await prepared(client,db_session,monkeypatch)
    def fail(*args): raise RuntimeError('injected resolution failure')
    event.listen(DiagnosticProbeAttempt,'before_insert',fail)
    try:
        with pytest.raises(RuntimeError,match='injected'):
            await client.post(base(course,attempt)+'/'+data['id']+'/probe-attempts',json={'selected_option_index':0})
    finally: event.remove(DiagnosticProbeAttempt,'before_insert',fail)
    assert (await client.get(base(course,attempt)+'/'+data['id'])).json()['status']=='hypothesis'
    assert await counts(db_session)==[1,1,0,0,0]


@pytest.mark.parametrize('model,field,value',[(ReasoningDiagnosis,'hypothesis_text','rewritten'),(DiagnosticProbe,'explanation','rewritten'),(DiagnosticProbeAttempt,'selected_option_index',3)])
async def test_immutable_history(client,db_session,monkeypatch,model,field,value):
    course,_,_,_,attempt,data,_=await prepared(client,db_session,monkeypatch)
    await client.post(base(course,attempt)+'/'+data['id']+'/probe-attempts',json={'selected_option_index':0})
    obj=await db_session.scalar(select(model))
    setattr(obj,field,value)
    with pytest.raises(ValueError,match='immutable'): await db_session.commit()
    await db_session.rollback()
    obj=await db_session.scalar(select(model))
    await db_session.delete(obj)
    with pytest.raises(ValueError,match='immutable'): await db_session.commit()
    await db_session.rollback()


@pytest.mark.parametrize('unsafe', ['unverified_probe', 'revoked_question', 'missing_hypothesis', 'malformed_probe', 'foreign_citation'])
async def test_unsafe_stored_probe_inconclusive(client,db_session,monkeypatch,unsafe):
    course,_,_,_,attempt,data,_=await prepared(client,db_session,monkeypatch)
    if unsafe=='unverified_probe':
        await db_session.execute(update(DiagnosticProbe).values(verified=False))
    if unsafe=='revoked_question':
        await db_session.execute(update(AssessmentQuestion).values(verification_status='rejected'))
    if unsafe=='missing_hypothesis':
        await db_session.execute(update(ReasoningDiagnosis).values(hypothesis_text=None))
    if unsafe=='malformed_probe':
        await db_session.execute(update(DiagnosticProbe).values(options=['Only one']))
    if unsafe=='foreign_citation':
        snapshots=data['probe']['citations']
        snapshots[0]['course_id']=str(uuid.uuid4())
        await db_session.execute(update(DiagnosticProbe).values(citation_snapshots=snapshots))
    await db_session.commit()
    r=await client.post(base(course,attempt)+'/'+data['id']+'/probe-attempts',json={'selected_option_index':0})
    assert r.json()['diagnostic_outcome']=='inconclusive'
    assert r.json()['is_correct'] is r.json()['correct_option_index'] is r.json()['explanation'] is None


@pytest.mark.parametrize('kind', ['same_course_unmapped', 'foreign_concept', 'foreign_evidence'])
async def test_real_unallowed_model_ids(client,db_session,monkeypatch,kind):
    course,concept,evidence,_,attempt=await seed(db_session)
    other,foreign_concept,foreign_evidence,_,_=await seed(db_session)
    unmapped=Concept(id=uuid.uuid4(),course_id=course.id,name='Unmapped')
    db_session.add(unmapped)
    await db_session.commit()
    draft,verdict=payloads(concept,evidence)
    if kind=='same_course_unmapped': draft['target_concept_id']=str(unmapped.id)
    if kind=='foreign_concept': draft['target_concept_id']=str(foreign_concept.id)
    if kind=='foreign_evidence': verdict['evidence_unit_ids']=[str(foreign_evidence[0].id)]
    provider_for(monkeypatch,draft,verdict)
    assert (await create(client,course,attempt)).status_code==502
    assert await counts(db_session)==[0,0,0,0,0]


async def test_foreign_reads_and_submissions(client,db_session,monkeypatch):
    course,_,_,_,attempt,data,_=await prepared(client,db_session,monkeypatch)
    for url in [base(course,attempt).replace(str(course.id),str(uuid.uuid4())),base(course,attempt).replace(str(attempt.learner_id),str(uuid.uuid4()))]:
        assert (await client.get(url+'/'+data['id'])).status_code==404
        assert (await client.post(url+'/'+data['id']+'/probe-attempts',json={'selected_option_index':0})).status_code==404


async def test_existing_mastery_unchanged_and_warm_start(client,db_session,monkeypatch):
    course,concept,evidence,q,attempt=await seed(db_session)
    # Standard attempts keep the Phase 5 behavior; Phase 6 must preserve it.
    learner=uuid.uuid4()
    r=await client.post(f'/courses/{course.id}/assessments/questions/{q.id}/attempts',json={'learner_id':str(learner),'selected_option_index':0})
    a=await db_session.get(AssessmentAttempt,uuid.UUID(r.json()['attempt_id']))
    mastery=await db_session.scalar(select(LearnerConceptMastery))
    before=(mastery.mastery_probability,mastery.observation_count,mastery.correct_count,mastery.last_attempt_id)
    await db_session.commit()
    provider_for(monkeypatch,*payloads(concept,evidence))
    data=(await create(client,course,a)).json()
    assert data['cold_start'] is False
    await client.post(base(course,a)+'/'+data['id']+'/probe-attempts',json={'selected_option_index':1})
    await db_session.refresh(mastery)
    assert before==(mastery.mastery_probability,mastery.observation_count,mastery.correct_count,mastery.last_attempt_id)
    assert (await counts(db_session))[-2:]==[1,1]


async def test_whole_course_deletion(client,db_session,monkeypatch):
    course,_,_,_,attempt,data,_=await prepared(client,db_session,monkeypatch)
    await client.post(base(course,attempt)+'/'+data['id']+'/probe-attempts',json={'selected_option_index':1})
    await db_session.delete(course)
    await db_session.commit()
    assert await counts(db_session)==[0,0,0,0,0]
