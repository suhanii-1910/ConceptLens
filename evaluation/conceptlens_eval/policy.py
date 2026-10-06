"""Use actual Phase 6/7 decisions, replacing only persistence/content boundaries.

The in-memory content is a reviewed fixture, NOT evidence of live diagnosis or
content-verifier quality. No latent learner state is accepted by this adapter.
Global patches are confined to a sequential offline context, never an app server.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
from types import SimpleNamespace as N
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from app.services import adaptive_learning as production, reasoning_diagnosis as diagnosis_service
from app.services import assessment_grading
from app.services.learner_mastery import compute_bkt_step
from app.models.adaptive_learning import LearningSession, LearningIntervention, TransferCheck
from app.models.assessment import AssessmentQuestion
from app.models.concept import Concept
from app.models.prerequisite_edge import PrerequisiteEdge
from app.schemas import adaptive_learning as schema
from app.schemas.reasoning_diagnosis import ProbeAttemptCreate
from app.schemas.learner_mastery import MasteryUpdateStatus

POLICIES = ("FIXED", "SIMPLE ADAPTIVE", "CONCEPTLENS")
DEFINITIONS = {
    "FIXED": "source_explanation -> worked_example -> transfer_check, irrespective of observations",
    "SIMPLE ADAPTIVE": "wrong entry answer -> worked_example -> general_practice; otherwise source_explanation; then transfer_check; failed transfer repeats worked example and practice",
    "CONCEPTLENS": "Production create_session, submit_probe, select_prerequisite, feedback, advance, prerequisite_choice and submit_attempt with frozen content and memory persistence"}


def uid(name):
    return uuid5(NAMESPACE_URL, "conceptlens-eval/" + name)


def baseline_action(policy: str, step: int, history: list[dict], initial_correct: bool) -> str | None:
    if policy == "FIXED":
        return ("source_explanation", "worked_example", "transfer_check")[step] if step < 3 else None
    if policy != "SIMPLE ADAPTIVE":
        raise ValueError("unknown baseline")
    if not history:
        return "source_explanation" if initial_correct else "worked_example"
    last = history[-1]
    if last["action"] == "transfer_check":
        return None if last["correct"] else "worked_example"
    if last["action"] == "worked_example":
        return "general_practice"
    return "transfer_check"


class MemoryPolicy:
    """A minimal SQLAlchemy-shaped persistence port; never creates an engine."""
    def __init__(self, bank: list[dict], bkt: dict, counts: dict, session_index: int, edges: list[list[str]]):
        self.bank = [item for item in bank if item["role"] == "training"]
        self.bkt, self.counts, self.session_index = bkt, counts, session_index
        self.course, self.learner = uid("course"), uid("learner")
        self.concepts = {k: Concept(id=uid(k), course_id=self.course, name=k) for k in ("target", "prerequisite")}
        self.edges = [PrerequisiteEdge(id=uid("edge/"+a+"/"+b), course_id=self.course,
            prerequisite_concept_id=uid(a), target_concept_id=uid(b), relation_type="requires", source_backed=True) for a,b in edges]
        self.history, self.questions, self.probe_attempts = [], {}, []
        self.session = self.check = None
        self.citation = dict(evidence_unit_id=str(uid("evidence")), course_id=str(self.course), source_version_id=str(uid("source")),
            source_filename="aster-memory.pdf", source_type="pdf", modality="text", locator={"page_number":2},
            location_metadata={"page_number":2}, locator_label="Page 2")
        self.diagnosis = N(id=uid("diagnosis"), course_id=self.course, learner_id=self.learner,
            target_concept_id=uid("target"), status="hypothesis", attempt_id=uid("entry-attempt"), question_id=uid("entry-question"),
            hypothesis_text="Possible conflation of translation miss and residency fault", first_break_excerpt="Every TLB miss is a page fault",
            evidence_unit_ids=[str(uid("evidence"))], citation_snapshots=[self.citation])
        self.original = self.question("target", 0, "entry-question")
        self.probe = self.question("target", 1, "diagnostic-probe")
        self.probe.verified = True
        self.probe.diagnosis_id = self.diagnosis.id
        self.calls = []

    def question(self, concept, offset, name):
        items = [i for i in self.bank if i["role"] == "training" and i["concept"] == concept]
        item = items[(self.session_index * 2 + offset) % len(items)]
        q = AssessmentQuestion(id=uid(name), course_id=self.course, question_type="multiple_choice", difficulty="medium",
            question_text=item["question"], options=item["options"], correct_option_index=item["correct_option_index"],
            explanation=item["explanation"], concepts=[self.concepts[concept]], verification_status="verified",
            evidence_unit_ids=[str(uid("evidence"))], citation_snapshots=[self.citation])
        q.fixture_item = item
        self.questions[q.id] = q
        return q

    async def scalar(self, statement):
        name = statement.column_descriptions[0]["entity"].__name__
        if name == "LearningSession": return self.session
        if name == "TransferCheck": return self.check
        if name == "DiagnosticProbe": return self.probe
        if name == "DiagnosticProbeAttempt": return self.probe_attempts[0] if self.probe_attempts else None
        if name == "AssessmentQuestion":
            params = statement.compile().params
            return self.questions[params["id_1"]]
        raise AssertionError("unexpected production query: " + name)

    async def execute(self, statement):
        if statement.column_descriptions[0]["entity"] is not PrerequisiteEdge:
            raise AssertionError("unexpected prerequisite query")
        rows = []
        for edge in self.edges:
            concept = next(c for c in self.concepts.values() if c.id == edge.prerequisite_concept_id)
            observed = N(observation_count=self.counts[concept.name], mastery_probability=self.bkt[concept.name])
            rows.append((edge, concept, observed))
        return N(all=lambda: rows)

    async def get(self, cls, key):
        if cls is PrerequisiteEdge: return next(e for e in self.edges if e.id == key)
        if cls is Concept: return next(c for c in self.concepts.values() if c.id == key)
        return self.questions.get(key)

    def add(self, obj):
        obj.created_at = datetime(2026, 10, 6, tzinfo=timezone.utc)
        if isinstance(obj, LearningSession):
            obj.updated_at = obj.created_at
            self.session = obj
        if type(obj).__name__ == "DiagnosticProbeAttempt": self.probe_attempts.append(obj)

    async def flush(self): pass

    async def history_port(self, db, session): return self.history
    async def diagnosis_port(self, *args, **kwargs): return self.diagnosis
    async def eligible_port(self, *args, **kwargs): return None, self.original
    async def evidence_port(self, *args, **kwargs): return {uid("evidence"): self.citation}, []

    async def mastery_port(self, *, db, attempt, course_id, concepts):
        for concept in concepts:
            self.bkt[concept.name] = compute_bkt_step(self.bkt[concept.name], attempt.is_correct).updated_mastery
            self.counts[concept.name] += 1
        return MasteryUpdateStatus.updated, None

    async def public_port(self, db, session):
        return schema.SessionPublic(**{k:getattr(session,k) for k in ("id","course_id","learner_id","diagnosis_id","target_concept_id","status","current_action","reason","created_at","updated_at")}, current_intervention=None, prerequisite_choices=[])

    async def content_port(self, db, session, strategy, reason, prerequisite=None):
        if strategy in {i.strategy for i in self.history}:
            raise AssertionError("production requested repeated strategy")
        edge, concept = (prerequisite[0], prerequisite[1]) if prerequisite else (None, self.concepts["target"])
        question = None
        if strategy in production.GRADED:
            previous = {q.question_text for q in self.questions.values()}
            for offset in range(len(self.history)+2, len(self.history)+2+len(self.bank)):
                question = self.question(concept.name, offset, "question/"+strategy)
                if question.question_text not in previous:
                    break
            else:
                raise ValueError("frozen content exhausted; never bypass production question freshness")
        item = LearningIntervention(id=uid("intervention/"+strategy), session_id=session.id, course_id=self.course,
            learner_id=self.learner, target_concept_id=uid("target"), sequence_index=len(self.history)+1,
            strategy=strategy, prerequisite_concept_id=concept.id if edge else None, prerequisite_edge_id=edge.id if edge else None,
            assessment_question_id=question.id if question else None, verified=True, completed=False)
        self.history.append(item)
        if strategy == "transfer_check":
            self.check = N(status="pending", resolved_attempt_id=None)
        session.current_action, session.reason = strategy, reason

    def __enter__(self):
        self.stack = ExitStack()
        for module, name, fn in [(production,"interventions",self.history_port), (production,"add_intervention",self.content_port),
            (production,"trusted_evidence",self.evidence_port), (production,"public_session",self.public_port),
            (diagnosis_service,"get_diagnosis",self.diagnosis_port), (diagnosis_service,"eligible_attempt",self.eligible_port),
            (assessment_grading,"process_mastery_update",self.mastery_port)]:
            self.stack.enter_context(patch.object(module,name,fn))
        return self

    def __exit__(self, *args): return self.stack.__exit__(*args)

    async def start(self, reasoning_marker: bool):
        self.diagnosis.status = "hypothesis" if reasoning_marker else "no_clear_break"
        self.calls.append("create_session")
        await production.create_session(self, self.course, self.learner, schema.SessionCreate(diagnosis_id=self.diagnosis.id))

    def current_item(self):
        if self.session.current_action == "diagnostic_probe": return self.probe.fixture_item
        if self.history and self.history[-1].assessment_question_id:
            return self.questions[self.history[-1].assessment_question_id].fixture_item
        return None

    async def respond(self, correct: bool, understood: bool):
        action = self.session.current_action
        if action == "diagnostic_probe":
            self.calls.append("submit_probe")
            key = self.probe.correct_option_index
            await diagnosis_service.submit_probe(self, self.course, self.learner, self.diagnosis.id,
                ProbeAttemptCreate(selected_option_index=key if correct else (key+1)%4))
            await production.create_session(self, self.course, self.learner, schema.SessionCreate(diagnosis_id=self.diagnosis.id))
        elif action == "prerequisite_choice":
            self.calls.append("prerequisite_choice")
            # Fixed learner preference, observable and available to every policy.
            await production.prerequisite_choice(self,self.session,schema.PrerequisiteChoice(intervention_id=self.history[-1].id,choice="sixty_second_recap"))
        elif action in production.GRADED:
            self.calls.append("submit_attempt")
            item = self.history[-1]
            key = self.questions[item.assessment_question_id].correct_option_index
            await production.submit_attempt(self,self.session,schema.LearningAttemptCreate(selected_option_index=key if correct else (key+1)%4),
                intervention_id=item.id,transfer=action=="transfer_check")
        elif action in {"source_explanation","visual_explanation","worked_example","prerequisite_recap"}:
            self.calls.append("feedback")
            await production.feedback(self,self.session,schema.FeedbackCreate(intervention_id=self.history[-1].id,
                feedback="understood" if understood else "still_confused"))
        else:
            raise ValueError("action requires external reassessment/general practice, not targeted repair")
