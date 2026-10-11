"""Phase 7 trust boundaries and shared source-backed fixtures."""
import json
import uuid
import pytest
from pydantic import ValidationError
from app.api.endpoints.reasoning_diagnosis import create_reasoning_diagnosis, submit_probe_attempt
from app.schemas.reasoning_diagnosis import DiagnosisCreate, ProbeAttemptCreate
from app.schemas import adaptive_learning as schema
from tests.test_reasoning_diagnosis import seed, payloads, provider_for, STEPS

async def confirmed(db, monkeypatch):
    course, concept, evidence, question, attempt = await seed(db)
    provider_for(monkeypatch, *payloads(concept, evidence))
    diagnosis = await create_reasoning_diagnosis(course.id, attempt.learner_id,
        DiagnosisCreate(attempt_id=attempt.id, reasoning_steps=STEPS), db)
    await submit_probe_attempt(course.id, attempt.learner_id, diagnosis.id, ProbeAttemptCreate(selected_option_index=1), db)
    return course, concept, evidence, question, attempt, diagnosis

class TeachingProvider:
    def __init__(self):
        self.calls = []
        self.change_draft = lambda d: d
        self.change_verdict = lambda v: v
        self.error = None
    async def generate(self, *, system_prompt, user_prompt):
        if self.error: raise self.error
        self.calls.append((system_prompt, user_prompt))
        context = json.loads(user_prompt.split('\n')[0])
        strategy = context['requested_strategy']
        ids = [e['evidence_unit_id'] for e in context['evidence']]
        if 'CANDIDATE:' in user_prompt:
            verdict = dict(verdict='verified', strategy_matches=True, addresses_gap=True,
                source_supported=True, materially_different=True, answer_supported=True,
                no_answer_leak=True, no_permanent_label=True, same_target_rule=True,
                fresh_structure=True, evidence_unit_ids=[ids[-1]])
            return json.dumps(self.change_verdict(verdict))
        draft = dict(strategy=strategy, evidence_unit_ids=[ids[0]])
        if strategy in {'transfer_check', 'prerequisite_probe', 'prerequisite_practice'}:
            items = {
                'prerequisite_probe': ('A job needs 8 execution units in total and has run for 3. How much remains?',
                    ['5 units', '8 units', '3 units', '11 units'], 'Remaining execution is 8 minus 3, or 5.'),
                'prerequisite_practice': ('Two jobs originally need 9 and 12 units. Each has executed 4 units. Which pair gives their remaining execution times?',
                    ['5 and 8', '9 and 12', '4 and 4', '13 and 16'], 'Subtract executed time from each original duration: 9-4=5 and 12-4=8.'),
                'transfer_check': ('At a scheduling decision, A has completed 7 of 12 units, B has 4 units left, and newly arrived C needs 3 units. Which process runs under SRTF?',
                    ['C', 'B', 'A', 'All three equally'], 'A has 5 remaining, B has 4, and C has 3. The shortest remaining job C runs.'),
            }
            stem, options, explanation = items[strategy]
            draft['question'] = dict(question_text=stem, options=options, correct_option_index=0,
                explanation=explanation, evidence_unit_ids=[ids[0]])
        else:
            draft['payload'] = dict(title=strategy, body='Compare remaining execution times.', steps=['Subtract elapsed execution from original burst.'])
            if strategy == 'visual_explanation':
                draft['payload']['visual'] = dict(title='Remaining-time timeline', steps=[dict(label='X', annotation='9 total minus 6 executed leaves 3.')])
        return json.dumps(self.change_draft(draft))

def teaching_provider(monkeypatch):
    provider = TeachingProvider()
    monkeypatch.setattr('app.services.adaptive_learning.get_llm_provider', lambda: provider)
    return provider

@pytest.mark.parametrize('field,value', [('strategy','arbitrary'), ('target_concept_id',str(uuid.uuid4())), ('citations',[]), ('page_number',99)])
def test_server_owned_draft(field, value):
    draft = dict(strategy='source_explanation', payload=dict(title='t',body='b'), evidence_unit_ids=[uuid.uuid4()])
    draft[field] = value
    with pytest.raises(ValidationError): schema.TeachingDraft.model_validate(draft)

@pytest.mark.parametrize('body', ['<script>alert(1)</script>', '<svg/onload=x>', 'javascript:alert(1)', 'data:text/html,x', 'x'*2001])
def test_visual_and_text_are_bounded_non_executable(body):
    with pytest.raises(ValidationError):
        schema.TeachingDraft(strategy='source_explanation', payload=dict(title='t',body=body), evidence_unit_ids=[uuid.uuid4()])

@pytest.mark.parametrize('index', [True, -1, 4, '1', 1.0])
def test_attempt_strict(index):
    with pytest.raises(ValidationError): schema.LearningAttemptCreate(selected_option_index=index)

def test_trace_has_explicit_structures_and_state_literals():
    spec = schema.LearningTrace.model_json_schema()
    for name in ['ObservedReasoning','DiagnosticEvidence','TransferResult','LearnerUpdateEvidence']:
        assert spec['$defs'][name]['additionalProperties'] is False
    for field in ['status','current_action']:
        assert 'enum' in spec['$defs']['SessionPublic']['properties'][field]

@pytest.mark.parametrize('count',[0,3,5])
def test_mcq_requires_exactly_four_choices(count):
    with pytest.raises(ValidationError):
        schema.TeachingDraft(strategy='transfer_check',evidence_unit_ids=[uuid.uuid4()],
            question=dict(question_text='Which?',options=[str(i) for i in range(count)],correct_option_index=0,
                          explanation='Explanation',evidence_unit_ids=[uuid.uuid4()]))

@pytest.mark.parametrize('field',['strategy_matches','addresses_gap','source_supported','materially_different',
    'answer_supported','no_answer_leak','no_permanent_label','same_target_rule','fresh_structure'])
def test_verifier_flags_strict(field):
    verdict=dict(verdict='verified',evidence_unit_ids=[uuid.uuid4()],**{name:True for name in
        ['strategy_matches','addresses_gap','source_supported','materially_different','answer_supported',
         'no_answer_leak','no_permanent_label','same_target_rule','fresh_structure']})
    verdict[field]='true'
    with pytest.raises(ValidationError): schema.TeachingVerification.model_validate(verdict)


def test_rejected_teaching_verifier_may_omit_evidence():
    verdict = dict(
        verdict="rejected",
        strategy_matches=True,
        addresses_gap=True,
        source_supported=True,
        materially_different=True,
        answer_supported=True,
        no_answer_leak=True,
        no_permanent_label=True,
        same_target_rule=True,
        fresh_structure=False,
    )
    parsed = schema.TeachingVerification.model_validate(verdict)
    assert parsed.verdict == "rejected"
    assert parsed.evidence_unit_ids == []


def test_verified_teaching_verifier_requires_evidence():
    verdict = dict(
        verdict="verified",
        strategy_matches=True,
        addresses_gap=True,
        source_supported=True,
        materially_different=True,
        answer_supported=True,
        no_answer_leak=True,
        no_permanent_label=True,
        same_target_rule=True,
        fresh_structure=True,
    )
    with pytest.raises(ValidationError):
        schema.TeachingVerification.model_validate(verdict)
