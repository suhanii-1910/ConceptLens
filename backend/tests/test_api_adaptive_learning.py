"""Phase 7 HTTP lifecycle, isolation, and transactional failures."""
import uuid
import pytest
from sqlalchemy import select, func, update
from app.models import Concept, PrerequisiteEdge, LearnerConceptMastery, MasteryObservation, AssessmentAttempt
from app.models.adaptive_learning import LearningSession, LearningIntervention, TransferCheck
from app.models.reasoning_diagnosis import ReasoningDiagnosis
from app.models.evidence_unit import evidence_concept_link
from app.services import adaptive_learning as service
from app.services.llm_provider import LLMProviderError
from tests.test_adaptive_learning import confirmed, teaching_provider
pytestmark = pytest.mark.asyncio

async def setup(client, db, monkeypatch):
    data = await confirmed(db, monkeypatch)
    provider = teaching_provider(monkeypatch)
    course, concept, evidence, question, attempt, diagnosis = data
    base = f'/courses/{course.id}/learners/{attempt.learner_id}/learning-sessions'
    response = await client.post(base, json={'diagnosis_id':str(diagnosis.id)})
    assert response.status_code == 200, response.text
    return data, provider, base, response.json()

async def feedback(client, base, session, value='still_confused'):
    return await client.post(f'{base}/{session["id"]}/feedback', json={
        'intervention_id':session['current_intervention']['id'], 'feedback':value})

async def add_prerequisite(db, data):
    course, target, evidence, *_ = data
    concept = Concept(id=uuid.uuid4(), course_id=course.id, name='Remaining execution')
    edge = PrerequisiteEdge(id=uuid.uuid4(), course_id=course.id, prerequisite_concept=concept,
        target_concept_id=target.id, relation_type='prerequisite', source_backed=True)
    db.add_all([concept,edge]); await db.flush()
    await db.execute(evidence_concept_link.insert().values(evidence_unit_id=evidence[0].id, concept_id=concept.id))
    await db.commit()
    return concept, edge

async def test_happy_transfer_trace_and_repeat(client, db_session, monkeypatch):
    data, provider, base, session = await setup(client, db_session, monkeypatch)
    assert session['current_action'] == 'source_explanation'
    assert session['current_intervention']['citations'][0]['evidence_unit_id'] == str(data[2][-1].id)
    response = await feedback(client, base, session, 'understood')
    assert response.status_code == 200, response.text
    session = response.json(); assert session['current_action'] == 'transfer_check'
    public = session['current_intervention']['question']
    assert 'correct_option_index' not in public and 'explanation' not in public
    calls = len(provider.calls)
    endpoint = f'{base}/{session["id"]}/transfer-check/attempts'
    response = await client.post(endpoint, json={'selected_option_index':0})
    assert response.status_code == 200, response.text
    first = response.json()
    assert first['session']['status'] == 'complete'
    assert first['attempt']['mastery_update_status'] == 'updated'
    response = await client.post(endpoint, json={'selected_option_index':1})
    assert response.status_code == 200, response.text
    assert response.json()['attempt']['mastery_update_status'] == 'skipped_repeated_question'
    trace = await client.get(f'{base}/{session["id"]}/trace')
    assert trace.status_code == 200, trace.text
    trace = trace.json(); assert all(trace['proof'].values())
    assert trace['transfer_result']['resolved_attempt_id'] == first['attempt']['attempt_id']
    assert trace['transfer_result']['status'] == 'passed'
    assert len(trace['learner_updates']) == 1 and len(provider.calls) == calls
    assert trace['observed']['assessment_attempt_id'] == str(data[4].id)
    bypass = await client.post(f'/courses/{data[0].id}/assessments/questions/{public["id"]}/attempts',
        json={'learner_id':str(uuid.uuid4()),'selected_option_index':0})
    assert bypass.status_code == 409

@pytest.mark.parametrize('choice', ['sixty_second_recap','practice_prerequisite','continue_anyway'])
async def test_full_prerequisite_path(client, db_session, monkeypatch, choice):
    data, provider, base, session = await setup(client, db_session, monkeypatch)
    concept, edge = await add_prerequisite(db_session, data)
    for action in ['visual_explanation','prerequisite_probe']:
        response = await feedback(client, base, session)
        assert response.status_code == 200, response.text
        session = response.json(); assert session['current_action'] == action
    item = session['current_intervention']
    assert item['target_concept_id'] == str(data[1].id)
    assert item['prerequisite_concept_id'] == str(concept.id) and item['prerequisite_edge_id'] == str(edge.id)
    endpoint = f'{base}/{session["id"]}'
    response = await client.post(f'{endpoint}/interventions/{item["id"]}/attempts', json={'selected_option_index':1})
    assert response.status_code == 200, response.text
    session = response.json()['session']
    assert response.json()['attempt']['mastery_update_status'] is None
    assert session['prerequisite_choices'] == service.CHOICES
    response = await client.post(f'{endpoint}/prerequisite-choice',json={'intervention_id':item['id'],'choice':choice})
    assert response.status_code == 200, response.text
    session = response.json()
    if choice == 'sixty_second_recap':
        assert session['current_action'] == 'prerequisite_recap'
        session = (await feedback(client,base,session,'understood')).json()
    elif choice == 'practice_prerequisite':
        assert session['current_action'] == 'prerequisite_practice'
        response = await client.post(f'{endpoint}/interventions/{session["current_intervention"]["id"]}/attempts',json={'selected_option_index':0})
        assert response.status_code == 200, response.text
        session = response.json()['session']
    assert session['current_action'] == 'worked_example'
    assert await db_session.scalar(select(func.count()).select_from(MasteryObservation)) == 0
    await db_session.rollback()
    session = (await feedback(client,base,session,'understood')).json()
    assert session['current_action'] == 'transfer_check'
    response = await client.post(f'{endpoint}/transfer-check/attempts',json={'selected_option_index':1})
    assert response.status_code == 200, response.text
    assert response.json()['session']['current_action'] == 'reconsider_diagnosis'
    trace = (await client.get(f'{endpoint}/trace')).json()
    assert [i['learner_choice'] for i in trace['teaching_actions'] if i['strategy']=='prerequisite_probe'] == [choice]
    strategies = [i['strategy'] for i in trace['teaching_actions']]
    assert len(set(strategies)) == len(strategies)

async def test_no_prerequisite_and_early_transfer_failure(client, db_session, monkeypatch):
    _, _, base, session = await setup(client, db_session, monkeypatch)
    session = (await feedback(client,base,session,'understood')).json()
    endpoint=f'{base}/{session["id"]}'
    response = await client.post(f'{endpoint}/transfer-check/attempts',json={'selected_option_index':1})
    assert response.status_code==200,response.text
    session=response.json()['session']; assert session['current_action']=='visual_explanation'
    session=(await feedback(client,base,session)).json(); assert session['current_action']=='worked_example'
    session=(await feedback(client,base,session,'understood')).json(); assert session['current_action']=='reconsider_diagnosis'
    assert await db_session.scalar(select(func.count()).select_from(TransferCheck))==1

@pytest.mark.parametrize('status,action',[('hypothesis','diagnostic_probe'),('rejected','general_practice'),('inconclusive','reconsider_diagnosis'),('no_clear_break','general_practice'),('insufficient_reasoning','collect_more_reasoning'),('insufficient_evidence','collect_more_reasoning')])
async def test_nonconfirmed_safe_policy(client,db_session,monkeypatch,status,action):
    data=await confirmed(db_session,monkeypatch); provider=teaching_provider(monkeypatch)
    await db_session.execute(update(ReasoningDiagnosis).where(ReasoningDiagnosis.id==data[5].id).values(status=status)); await db_session.commit()
    base=f'/courses/{data[0].id}/learners/{data[4].learner_id}/learning-sessions'
    response=await client.post(base,json={'diagnosis_id':str(data[5].id)})
    assert response.status_code==200,response.text
    assert response.json()['current_action']==action and response.json()['status']=='diagnosis_not_confirmed'
    assert response.json()['current_intervention'] is None and provider.calls==[]
    trace=(await client.get(f'{base}/{response.json()["id"]}/trace')).json()
    for flag in ['teaching_content_verified','transfer_check_verified','learner_update_based_on_verified_evidence']: assert trace['proof'][flag] is False

@pytest.mark.parametrize('failure', ['concept','strategy','evidence','verifier_evidence','verdict','freshness','answer','markup','duplicate','provider'])
async def test_generation_fails_closed_and_rolls_back_feedback(client,db_session,monkeypatch,failure):
    data,provider,base,session=await setup(client,db_session,monkeypatch)
    if failure=='concept': provider.change_draft=lambda d:{**d,'target_concept_id':str(uuid.uuid4())}
    if failure=='strategy': provider.change_draft=lambda d:{**d,'strategy':'worked_example'}
    if failure=='evidence': provider.change_draft=lambda d:{**d,'evidence_unit_ids':[str(uuid.uuid4())]}
    if failure=='verifier_evidence': provider.change_verdict=lambda v:{**v,'evidence_unit_ids':[str(uuid.uuid4())]}
    if failure=='verdict': provider.change_verdict=lambda v:{**v,'verdict':'rejected'}
    if failure=='freshness': provider.change_verdict=lambda v:{**v,'fresh_structure':False}
    if failure=='answer': provider.change_verdict=lambda v:{**v,'answer_supported':False}
    if failure=='markup': provider.change_draft=lambda d:{**d,'question':{**d['question'],'question_text':'<script>x</script>'}}
    if failure=='duplicate': provider.change_draft=lambda d:{**d,'question':{**d['question'],'question_text':data[3].question_text}}
    if failure=='provider': provider.error=LLMProviderError('Unavailable')
    response=await feedback(client,base,session,'understood'); assert response.status_code in {422,502,503},response.text
    current=(await client.get(f'{base}/{session["id"]}')).json()
    assert current['current_action']=='source_explanation' and current['current_intervention']['feedback'] is None
    assert await db_session.scalar(select(func.count()).select_from(LearningIntervention))==1
    assert await db_session.scalar(select(func.count()).select_from(TransferCheck))==0

async def test_scope_stale_feedback_and_read_only_selection(client,db_session,monkeypatch):
    data,_,base,session=await setup(client,db_session,monkeypatch)
    for foreign in [f'/courses/{uuid.uuid4()}/learners/{data[4].learner_id}/learning-sessions',f'/courses/{data[0].id}/learners/{uuid.uuid4()}/learning-sessions']:
        assert (await client.get(f'{foreign}/{session["id"]}')).status_code==404
        assert (await client.post(foreign,json={'diagnosis_id':str(data[5].id)})).status_code==404
    old=session; session=(await feedback(client,base,session)).json()
    assert (await feedback(client,base,old)).status_code==409
    await add_prerequisite(db_session,data)
    saved=await db_session.get(LearningSession,uuid.UUID(session['id']))
    selected=await service.select_prerequisite(db_session,saved); assert 'untested' in selected[2]
    assert await db_session.scalar(select(func.count()).select_from(LearnerConceptMastery))==0

async def test_resolved_attempt_orm_immutable(client,db_session,monkeypatch):
    _,_,base,session=await setup(client,db_session,monkeypatch)
    session=(await feedback(client,base,session,'understood')).json()
    endpoint=f'{base}/{session["id"]}/transfer-check/attempts'
    first=(await client.post(endpoint,json={'selected_option_index':0})).json()
    repeat=(await client.post(endpoint,json={'selected_option_index':1})).json()
    check=await db_session.scalar(select(TransferCheck)); assert str(check.resolved_attempt_id)==first['attempt']['attempt_id']
    check.resolved_attempt_id=uuid.UUID(repeat['attempt']['attempt_id'])
    with pytest.raises(ValueError,match='resolves only once'): await db_session.flush()
    await db_session.rollback()

async def test_mastery_failure_rolls_back_transfer(client,db_session,monkeypatch):
    _,_,base,session=await setup(client,db_session,monkeypatch)
    session=(await feedback(client,base,session,'understood')).json()
    def fail(*args,**kwargs): raise ValueError('BKT failure')
    monkeypatch.setattr('app.services.mastery_update.compute_bkt_step',fail)
    with pytest.raises(ValueError,match='BKT failure'):
        await client.post(f'{base}/{session["id"]}/transfer-check/attempts',json={'selected_option_index':0})
    assert await db_session.scalar(select(func.count()).select_from(AssessmentAttempt))==1
    assert await db_session.scalar(select(func.count()).select_from(MasteryObservation))==0
    assert (await db_session.scalar(select(TransferCheck))).status=='pending'

@pytest.mark.parametrize('selected',[0,1])
async def test_unresolved_session_refreshes_after_resolution(client,db_session,monkeypatch,selected):
    from app.api.endpoints.reasoning_diagnosis import create_reasoning_diagnosis, submit_probe_attempt
    from app.schemas.reasoning_diagnosis import DiagnosisCreate, ProbeAttemptCreate
    from tests.test_reasoning_diagnosis import seed,payloads,provider_for,STEPS
    data=await seed(db_session)
    provider_for(monkeypatch,*payloads(data[1],data[2]))
    diagnosis=await create_reasoning_diagnosis(data[0].id,data[4].learner_id,DiagnosisCreate(attempt_id=data[4].id,reasoning_steps=STEPS),db_session)
    base=f'/courses/{data[0].id}/learners/{data[4].learner_id}/learning-sessions'
    first=(await client.post(base,json={'diagnosis_id':str(diagnosis.id)})).json()
    assert first['status']=='diagnosis_not_confirmed'
    await submit_probe_attempt(data[0].id,data[4].learner_id,diagnosis.id,ProbeAttemptCreate(selected_option_index=selected),db_session)
    provider=teaching_provider(monkeypatch)
    response=await client.post(base,json={'diagnosis_id':str(diagnosis.id)})
    assert response.status_code==200,response.text
    assert response.json()['id']==first['id']
    assert response.json()['current_action']==('source_explanation' if selected else 'general_practice')
    assert len(provider.calls)==(2 if selected else 0)
    again=await client.post(base,json={'diagnosis_id':str(diagnosis.id)})
    assert again.json()==response.json() and len(provider.calls)==(2 if selected else 0)

async def test_prerequisite_correct_does_not_invent_gap(client,db_session,monkeypatch):
    data,_,base,session=await setup(client,db_session,monkeypatch)
    await add_prerequisite(db_session,data)
    session=(await feedback(client,base,session)).json()
    session=(await feedback(client,base,session)).json()
    response=await client.post(f'{base}/{session["id"]}/interventions/{session["current_intervention"]["id"]}/attempts',json={'selected_option_index':0})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['session']['current_action']=='worked_example' and result['session']['prerequisite_choices']==[]
    assert result['attempt']['is_correct'] and result['attempt']['mastery_update_status'] is None
    assert await db_session.scalar(select(func.count()).select_from(LearnerConceptMastery))==0

async def test_prerequisite_lowest_observed_and_stable_tie(db_session,monkeypatch):
    data=await confirmed(db_session,monkeypatch)
    concepts=[]
    for _ in range(3): concepts.append((await add_prerequisite(db_session,data))[0])
    for concept in concepts[:2]:
        db_session.add(LearnerConceptMastery(id=uuid.uuid4(),course_id=data[0].id,learner_id=data[4].learner_id,
            concept_id=concept.id,mastery_probability=.4,observation_count=1,correct_count=0))
    await db_session.commit()
    session=LearningSession(course_id=data[0].id,learner_id=data[4].learner_id,target_concept_id=data[1].id)
    selected=await service.select_prerequisite(db_session,session)
    assert selected[1].id==min(c.id for c in concepts[:2])
    await db_session.execute(update(LearnerConceptMastery).where(LearnerConceptMastery.concept_id==concepts[1].id).values(mastery_probability=.1))
    await db_session.commit()
    assert (await service.select_prerequisite(db_session,session))[1].id==concepts[1].id
    assert await db_session.scalar(select(func.count()).select_from(LearnerConceptMastery))==2
    assert await db_session.scalar(select(func.count()).select_from(MasteryObservation))==0

@pytest.mark.parametrize('target',['diagnostic','practice'])
async def test_transfer_duplicate_of_prior_question_rejected(client,db_session,monkeypatch,target):
    from app.models.reasoning_diagnosis import DiagnosticProbe
    data,provider,base,session=await setup(client,db_session,monkeypatch)
    if target=='diagnostic':
        probe=await db_session.scalar(select(DiagnosticProbe))
        stem=probe.question_text
        await db_session.rollback()
    else:
        await add_prerequisite(db_session,data)
        session=(await feedback(client,base,session)).json()
        session=(await feedback(client,base,session)).json()
        endpoint=f'{base}/{session["id"]}'
        item=session['current_intervention']
        session=(await client.post(f'{endpoint}/interventions/{item["id"]}/attempts',json={'selected_option_index':1})).json()['session']
        session=(await client.post(f'{endpoint}/prerequisite-choice',json={'intervention_id':item['id'],'choice':'practice_prerequisite'})).json()
        stem=session['current_intervention']['question']['question_text']
        session=(await client.post(f'{endpoint}/interventions/{session["current_intervention"]["id"]}/attempts',json={'selected_option_index':0})).json()['session']
    provider.change_draft=lambda d:{**d,'question':{**d['question'],'question_text':stem}}
    response=await feedback(client,base,session,'understood')
    assert response.status_code==502,response.text

@pytest.mark.parametrize('corruption',['concept','evidence','citation','question'])
async def test_invalid_confirmation_scope_fails_closed(client,db_session,monkeypatch,corruption):
    from app.models import AssessmentQuestion
    data=await confirmed(db_session,monkeypatch)
    provider=teaching_provider(monkeypatch)
    if corruption=='concept': values={'target_concept_id':uuid.uuid4()}
    elif corruption=='evidence': values={'evidence_unit_ids':[str(uuid.uuid4())]}
    elif corruption=='citation': values={'citation_snapshots':[]}
    else: values={'question_id':uuid.uuid4()}
    await db_session.execute(update(ReasoningDiagnosis).where(ReasoningDiagnosis.id==data[5].id).values(**values))
    await db_session.commit()
    response=await client.post(f'/courses/{data[0].id}/learners/{data[4].learner_id}/learning-sessions',json={'diagnosis_id':str(data[5].id)})
    assert response.status_code==422,response.text
    assert provider.calls==[]
    assert await db_session.scalar(select(func.count()).select_from(LearningSession))==0

async def test_foreign_evidence_and_proof_revocation(client,db_session,monkeypatch):
    from tests.test_reasoning_diagnosis import seed
    from app.models import SourceVersion
    data,provider,base,session=await setup(client,db_session,monkeypatch)
    foreign=await seed(db_session)
    provider.change_verdict=lambda v:{**v,'evidence_unit_ids':[str(foreign[2][0].id)]}
    assert (await feedback(client,base,session,'understood')).status_code==502
    await db_session.execute(update(SourceVersion).where(SourceVersion.course_id==data[0].id).values(processing_status='failed'))
    await db_session.commit()
    calls=len(provider.calls)
    response=await client.get(f'{base}/{session["id"]}/trace')
    assert response.status_code==200,response.text
    assert not any(response.json()['proof'].values())
    assert len(provider.calls)==calls

@pytest.mark.parametrize('fail_at',['intervention','transfer'])
async def test_persistence_failure_rolls_back_whole_action(client,db_session,monkeypatch,fail_at):
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    _,_,base,session=await setup(client,db_session,monkeypatch)
    def reject(db,context,instances):
        model=LearningIntervention if fail_at=='intervention' else TransferCheck
        if any(isinstance(row,model) for row in db.new): raise ValueError('Persistence failure')
    event.listen(Session,'before_flush',reject)
    try:
        with pytest.raises(ValueError,match='Persistence failure'):
            await feedback(client,base,session,'understood')
    finally: event.remove(Session,'before_flush',reject)
    current=(await client.get(f'{base}/{session["id"]}')).json()
    assert current['current_intervention']['feedback'] is None
    assert await db_session.scalar(select(func.count()).select_from(LearningIntervention))==1
    assert await db_session.scalar(select(func.count()).select_from(TransferCheck))==0
