import asyncio
import copy
import inspect
from dataclasses import asdict, fields
from unittest.mock import patch
import pytest
from pydantic import ValidationError
from conceptlens_eval.simulation import Hidden, Observation, transition, answer, observe, learner, run, totals, repetition, Config, uniform
from conceptlens_eval.policy import MemoryPolicy, baseline_action, POLICIES, production, uid


def test_fixed_ignores_observations():
    for correct in [True,False]:
        assert [baseline_action('FIXED',i,[{'action':'anything'}],correct) for i in range(4)]==['source_explanation','worked_example','transfer_check',None]


def test_simple_only_wrong_answer():
    assert baseline_action('SIMPLE ADAPTIVE',0,[],False)=='worked_example'
    assert baseline_action('SIMPLE ADAPTIVE',0,[],True)=='source_explanation'
    assert baseline_action('SIMPLE ADAPTIVE',2,[{'action':'transfer_check','correct':False}],True)=='worked_example'
    assert baseline_action('SIMPLE ADAPTIVE',2,[{'action':'transfer_check','correct':True}],False) is None


def test_no_hidden_policy_api():
    assert {f.name for f in fields(Observation)}=={'correct','reasoning_marker'}
    assert list(inspect.signature(transition).parameters)==['state','action','config','key']
    assert 'Hidden' not in inspect.getsource(MemoryPolicy)
    assert list(inspect.signature(MemoryPolicy.start).parameters)==['self','reasoning_marker']
    assert 'hidden' not in inspect.signature(baseline_action).parameters


def test_shared_transition_and_bkt_separation(config):
    state=Hidden(.2,.3,.4,True,.1)
    key=(7,'profile',0,0,0)
    assert transition(state,'worked_example',config,key)==transition(state,'worked_example',config,key)
    assert transition(state,'transfer_check',config,key)==state
    updated=transition(state,'source_explanation',config,key)
    assert updated.target>state.target and updated.prerequisite==state.prerequisite
    assert uniform(key,'answer')==uniform(key,'answer')
    assert uniform(key,'answer')!=uniform((*key,1),'answer')


@pytest.mark.asyncio
async def test_same_seed_multisession_fairness(config,bank):
    profile=config.profiles[0]
    first=await learner('CONCEPTLENS',profile,7,0,config,bank)
    assert first==await learner('CONCEPTLENS',profile,7,0,config,bank)
    assert first!=await learner('CONCEPTLENS',profile,19,0,config,bank)
    all_rows=[await learner(p,profile,7,0,config,bank) for p in POLICIES]
    assert all(r['initial_latent']==first['initial_latent'] for r in all_rows)
    assert len(first['sessions'])==2
    for row in all_rows:
        assert row['sessions'][1]['initial_latent']==row['sessions'][0]['final_latent']
        assert [s['heldout_item_id'] for s in row['sessions']]==[s['heldout_item_id'] for s in first['sessions']]
        assert row['sessions'][0]['observation']==first['sessions'][0]['observation']
        heldout={s['heldout_item_id'] for s in row['sessions']}
        assert not heldout & {h['item_id'] for s in row['sessions'] for h in s['trajectory']}
        assert all(s['interventions']<=config.horizon for s in row['sessions'])


@pytest.mark.asyncio
async def test_production_repair_exhaustion_and_freshness(bank):
    bkt={'target':.2,'prerequisite':.2}; counts={'target':0,'prerequisite':0}
    original_feedback=production.feedback; original_advance=production.advance; original_submit=production.submit_attempt
    with MemoryPolicy(bank['items'],bkt,counts,0,bank['prerequisite_edges']) as p:
        assert all(item['role']=='training' for item in p.bank)
        assert production.feedback is original_feedback and production.advance is original_advance and production.submit_attempt is original_submit
        await p.start(True)
        assert p.session.current_action=='diagnostic_probe'
        await p.respond(False,False)
        assert p.diagnosis.status=='confirmed' and p.session.current_action=='source_explanation'
        await p.respond(False,False); assert p.session.current_action=='visual_explanation'
        await p.respond(False,False); assert p.session.current_action=='prerequisite_probe'
        before=dict(bkt)
        await p.respond(False,False); assert p.session.current_action=='prerequisite_choice'
        assert bkt==before  # actual production probe does not update mastery
        await p.respond(False,False); assert p.session.current_action=='prerequisite_recap'
        await p.respond(False,False); assert p.session.current_action=='worked_example'
        await p.respond(False,False); assert p.session.current_action=='transfer_check'
        await p.respond(False,False)
        assert p.session.status=='needs_reassessment' and p.session.current_action=='reconsider_diagnosis'
        assert bkt['target'] != before['target'] and counts['target']==1
        texts=[q.question_text for q in p.questions.values()]
        assert len(texts)==len(set(texts))

@pytest.mark.asyncio
@pytest.mark.parametrize('marker,probe_correct,expected',[(False,False,'source_explanation'),(True,True,'source_explanation'),(True,False,'source_explanation')])
async def test_production_diagnosis_safe_path(bank,marker,probe_correct,expected):
    with MemoryPolicy(bank['items'],{'target':.2,'prerequisite':.2},{'target':0,'prerequisite':0},0,bank['prerequisite_edges']) as p:
        await p.start(marker)
        if marker: await p.respond(probe_correct,False)
        assert p.session.current_action==expected
        assert p.diagnosis.status == ('no_clear_break' if not marker else 'rejected' if probe_correct else 'confirmed')
        assert p.counts == {'target':0,'prerequisite':0}
        await p.respond(False,True)
        assert p.session.current_action=='transfer_check'
        await p.respond(True,True)
        assert p.session.status=='complete' and p.counts['target']==1

@pytest.mark.asyncio
async def test_production_transfer_pass_and_no_prerequisite(bank):
    with MemoryPolicy(bank['items'],{'target':.2,'prerequisite':.2},{'target':0,'prerequisite':0},0,[]) as p:
        await p.start(True); await p.respond(False,False)
        await p.respond(False,False); await p.respond(False,False)
        assert p.session.current_action=='worked_example'  # real select_prerequisite fallback
        await p.respond(False,False); await p.respond(True,True)
        assert p.session.status=='complete' and p.check.status=='passed'


def test_repetition_id_text_templates():
    items=[dict(item_id='a',question='What now?',template_id='rule'),dict(item_id='b',question=' WHAT   NOW? ',template_id='rule'),dict(item_id='c',question='Another context?',template_id='rule')]
    assert repetition(items)==dict(questions=3,exact_repeats=1,template_repeats=2)


def row(successes,interventions):
    return {'sessions':[dict(transfer_success=s,interventions=i,completion=s,bkt_absolute_error=.1,strategy_changes=2) for s,i in zip(successes,interventions)],
        'initial_latent':dict(target=.2,prerequisite=.3),'final_latent':dict(target=.5,prerequisite=.4),'repetition':dict(questions=10,exact_repeats=2,template_repeats=5)}


def test_metric_math():
    m=totals([row([True,False],[2,4]),row([False,True],[3,3])])
    assert m['transfer_success']==m['session_completion']==.5
    assert m['interventions_per_success']==6
    assert m['question_repetition']==.2 and m['template_repetition']==.5
    assert m['latent_mastery_gain']==pytest.approx(.3)
    assert m['bkt_absolute_error']==.1
    assert totals([row([False],[3])])['interventions_per_success'] is None


@pytest.mark.asyncio
async def test_full_small_run_deterministic(config,bank):
    a=await run(config,bank); b=await run(config,bank)
    assert a==b and a['label']=='SIMULATED PERSONALIZATION RESULT'
    assert set(a['statistics'])==set(POLICIES)
    assert a['counts']['sessions_per_policy']==20
    for p in POLICIES:
        m=a['statistics'][p]['transfer_success']
        assert m['n_learners']==10 and m['n_sessions']==20
        assert 0 <= m['ci95'][0] <= m['mean'] <= m['ci95'][1] <= 1

@pytest.mark.parametrize('change',[dict(seeds=[7,7]),dict(horizon=0),dict(sessions=0),dict(guess=.9,slip=.9)])
def test_bad_config(config,change):
    with pytest.raises(ValidationError):Config.model_validate({**config.model_dump(),**change})


def test_bank_rejects_heldout_leakage(bank,tmp_path):
    import json
    from conceptlens_eval.simulation import load_bank
    bank['items'][-1]['question']='  '+bank['items'][0]['question'].upper()+'  '
    path=tmp_path/'bank.json';path.write_text(json.dumps(bank))
    with pytest.raises(ValueError,match='duplicate bank question'):load_bank(path,2)


def test_bank_requires_distinct_session_transfer_items(bank,tmp_path):
    import json
    from conceptlens_eval.simulation import load_bank
    path=tmp_path/'bank.json';path.write_text(json.dumps(bank))
    with pytest.raises(ValueError,match='distinct held-out'):load_bank(path,5)
