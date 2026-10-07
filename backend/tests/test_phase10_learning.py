import pytest
from sqlalchemy import select,func
from app.models import MasteryObservation
from app.api.endpoints.reasoning_diagnosis import create_reasoning_diagnosis
from app.schemas.reasoning_diagnosis import DiagnosisCreate
from tests.test_reasoning_diagnosis import seed,provider_for,STEPS
from tests.test_adaptive_learning import teaching_provider

@pytest.mark.asyncio
async def test_real_uncertain_event_continues_and_trace_does_not_confirm(db_session,client,monkeypatch):
    c,concept,e,q,a=await seed(db_session)
    draft=dict(outcome='no_clear_break',observed_reasoning='The learner selected P2 but the explanation is inconclusive.')
    verdict=dict(verdict='verified',first_break_supported=False,hypothesis_supported=False,target_allowed=False,
        probe_isolates_hypothesis=False,probe_answer_supported=False,probe_is_fresh=False,public_content_safe=True,
        evidence_unit_ids=[],probe_evidence_unit_ids=[])
    provider_for(monkeypatch,draft,verdict)
    diagnosis=await create_reasoning_diagnosis(c.id,a.learner_id,DiagnosisCreate(attempt_id=a.id,reasoning_steps=STEPS),db_session)
    assert diagnosis.status=='no_clear_break' and diagnosis.target_concept_id is None
    provider=teaching_provider(monkeypatch)
    base=f'/courses/{c.id}/learners/{a.learner_id}/learning-sessions'
    result=await client.post(base,json={'diagnosis_id':str(diagnosis.id)})
    assert result.status_code==200,result.text
    session=result.json();assert session['target_concept_id']==str(concept.id)
    assert 'no_clear_break' in session['reason']
    assert 'no confirmed misconception' in provider.calls[0][1]
    endpoint=base+'/'+session['id']
    # Source explanation -> alternative visual -> worked example -> fresh transfer.
    for expected in ['visual_explanation','worked_example','transfer_check']:
        result=await client.post(endpoint+'/feedback',json={'intervention_id':session['current_intervention']['id'],'feedback':'still_confused'})
        assert result.status_code==200,result.text
        session=result.json();assert session['current_action']==expected
    assert await db_session.scalar(select(func.count()).select_from(MasteryObservation))==0
    result=await client.post(endpoint+'/transfer-check/attempts',json={'selected_option_index':0})
    assert result.status_code==200,result.text
    assert result.json()['session']['status']=='complete'
    trace=(await client.get(endpoint+'/trace')).json()
    assert trace['interpretation']=='no_clear_break' and trace['hypothesis'] is None
    assert trace['proof']['diagnostic_question_verified'] is False
    assert trace['proof']['teaching_content_verified'] is True
    assert trace['proof']['learner_update_based_on_verified_evidence'] is True
    assert len(trace['learner_updates'])==1
    assert len({i['strategy'] for i in trace['teaching_actions']})==4
    assert (await client.post(endpoint+'/feedback',json={'intervention_id':session['current_intervention']['id'],'feedback':'understood'})).status_code==409
