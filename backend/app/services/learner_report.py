"""Read-only summaries of attempt evidence, never inferred weakness for unseen concepts."""
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.assessment import AssessmentAttempt, AssessmentQuestion
from app.models.concept import Concept
from app.models.prerequisite_edge import PrerequisiteEdge
from app.models.reasoning_diagnosis import ReasoningDiagnosis
from app.services.adaptive_learning import trusted_evidence


async def concept_graph(db, course_id):
    concepts = list((await db.scalars(select(Concept).options(selectinload(Concept.evidence_units))
        .where(Concept.course_id == course_id).order_by(Concept.name, Concept.id))).all())
    ids = {c.id for c in concepts}
    nodes = []
    for c in concepts:
        citations, _ = await trusted_evidence(db, course_id, [e.id for e in c.evidence_units
            if e.course_id == course_id][:10])
        nodes.append(dict(id=c.id, name=c.name, description=c.description, citations=list(citations.values())))
    edges = (await db.scalars(select(PrerequisiteEdge).where(PrerequisiteEdge.course_id == course_id))).all()
    return dict(concepts=nodes, prerequisites=[dict(id=e.id, prerequisite_concept_id=e.prerequisite_concept_id,
        target_concept_id=e.target_concept_id, relation_type=e.relation_type, source_backed=e.source_backed,
        confidence=e.confidence) for e in edges if e.prerequisite_concept_id in ids and e.target_concept_id in ids])


async def assessment_report(db, course_id, learner_id):
    rows = (await db.execute(select(AssessmentAttempt, AssessmentQuestion).join(AssessmentQuestion,
        AssessmentQuestion.id == AssessmentAttempt.question_id).options(selectinload(AssessmentQuestion.concepts))
        .where(AssessmentAttempt.course_id == course_id, AssessmentAttempt.learner_id == learner_id,
            AssessmentQuestion.course_id == course_id, AssessmentQuestion.verification_status == 'verified')
        .order_by(AssessmentAttempt.created_at, AssessmentAttempt.id))).all()
    counted, excluded, by_type, by_concept, citations, selected_ids = set(), 0, {}, {}, {}, []
    correct = 0
    for attempt, question in rows:
        if attempt.is_correct is None:
            continue
        if question.id in counted:
            excluded += 1
            continue
        counted.add(question.id)
        selected_ids.append(attempt.id)
        correct += int(attempt.is_correct)
        groups = [by_type.setdefault(question.question_type, dict(attempt_count=0, correct_count=0))]
        for concept in question.concepts:
            if concept.course_id == course_id:
                groups.append(by_concept.setdefault(str(concept.id), dict(concept_id=concept.id,
                    name=concept.name, attempt_count=0, correct_count=0)))
        for group in groups:
            group['attempt_count'] += 1
            group['correct_count'] += int(attempt.is_correct)
        valid, _ = await trusted_evidence(db, course_id, question.evidence_unit_ids)
        if list(valid.values()) == question.citation_snapshots:
            citations.update(valid)
    for group in by_concept.values():
        group['status'] = 'observed_strong' if group['correct_count'] == group['attempt_count'] else 'observed_weak' if group['correct_count'] == 0 else 'observed_uncertain'
    diagnoses = (await db.scalars(select(ReasoningDiagnosis).where(ReasoningDiagnosis.course_id == course_id,
        ReasoningDiagnosis.learner_id == learner_id).order_by(ReasoningDiagnosis.created_at))).all()
    graph = await concept_graph(db, course_id)
    weak = {key for key, value in by_concept.items() if value['status'] == 'observed_weak'}
    return dict(attempt_count=len(rows), scored_question_count=len(counted), correct_count=correct,
        score=correct/len(counted) if counted else None,
        cannot_grade_count=sum(a.is_correct is None for a, _ in rows), repeated_attempts_excluded=excluded,
        scoring_policy='First gradable attempt per verified question; repeats excluded. Small samples are provisional.',
        counted_attempt_ids=selected_ids, by_type=by_type, concepts=list(by_concept.values()),
        untested=[c for c in graph['concepts'] if str(c['id']) not in by_concept],
        misconceptions=[dict(id=d.id, status=d.status, hypothesis=d.hypothesis_text,
            observed=d.observed_reasoning, attempt_id=d.attempt_id, target_concept_id=d.target_concept_id)
            for d in diagnoses],
        prerequisite_concerns=[dict(**e, reason='Prerequisite has an incorrect observed assessment response; this is not a confirmed causal diagnosis.')
            for e in graph['prerequisites'] if str(e['prerequisite_concept_id']) in weak],
        next_action='Review the cited concepts, then try a fresh verified question.' if weak else
            'Sample untested concepts with the short diagnostic.' if len(graph['concepts']) > len(by_concept) else
            'Try fresh transfer questions to gather more evidence.', citations=list(citations.values()))
