import { useCallback, useState } from 'react';
import { api } from '../api/client';
import type { Attempt, Diagnostic } from '../api/types';
import { useLearning } from '../state';
import { useQuery, useTask } from '../hooks';
import { AttemptResult, Button, Citations, ErrorNotice, Loading, diagnosisLabels } from './ui';
import { TypedAssessment } from './TypedAssessment';

export function DiagnosticPanel({onEvidence}: {onEvidence?: ()=>void}) {
  const {course,learner}=useLearning(); const task=useTask();
  const query=useQuery(useCallback((signal:AbortSignal)=>api.diagnostic(course!.id,learner,signal),[course,learner]));
  const [updated,setUpdated]=useState<Diagnostic>(); const [attempt,setAttempt]=useState<Attempt>();
  const state=updated ?? query.data;
  const next=state?.questions.find(q=>!state.completed_question_ids.includes(q.id));
  return <section className="card"><h2>Short diagnostic</h2><p>We need observed answers to understand where to help. Untested concepts are not weak concepts.</p>
    {query.loading && <Loading label="Restoring diagnostic progress…"/>}<ErrorNotice error={query.error} retry={query.reload}/>
    {state?.status==='not_started' && <Button busy={task.busy} onClick={async()=>{const result=await task.run(signal=>api.startDiagnostic(course!.id,learner,signal));if(result)setUpdated(result);}}>Start short diagnostic</Button>}
    {state && state.status!=='not_started' && <p>{state.completed_question_ids.length} / {state.question_count} verified questions completed. {state.message}</p>}
    {attempt && <AttemptResult attempt={attempt}/>}
    {next && <TypedAssessment key={next.id} question={next} busy={task.busy} onSubmit={async answer=>{const result=await task.run(async signal=>{const response=await api.attempt(course!.id,learner,next.id,answer,signal);const progress=await api.diagnostic(course!.id,learner,signal);return {response,progress};});if(result){setAttempt(result.response);setUpdated(result.progress);onEvidence?.();}}}/>}
    {state?.status==='complete' && <p role="status">Diagnostic complete. Your dashboard reflects actual responses; unsampled concepts remain UNTESTED.</p>}
    <ErrorNotice error={task.error}/>
  </section>;
}
export function ReportPanel() {
  const {course,learner}=useLearning();
  const query=useQuery(useCallback((signal:AbortSignal)=>api.report(course!.id,learner,signal),[course,learner]));
  const r=query.data;
  return <section className="assessment-report"><h2>Assessment evidence report</h2>{query.loading && <Loading label="Reading attempt evidence…"/>}<ErrorNotice error={query.error} retry={query.reload}/>
    {r && <><p>{r.score === null ? 'No gradable responses yet' : `${r.correct_count} / ${r.scored_question_count} correct (${Math.round(r.score*100)}%)`}</p><p>{r.attempt_count} attempts · {r.cannot_grade_count} ungradable · {r.repeated_attempts_excluded} repeats excluded</p><p className="quiet-note">{r.scoring_policy}</p>
      <ul>{Object.entries(r.by_type).map(([type,v])=><li key={type}>{type.replaceAll('_',' ')}: {v.correct_count}/{v.attempt_count}</li>)}</ul>
      <ul>{r.concepts.map(c=><li key={c.concept_id}><strong>{c.name}</strong>: {c.status.replaceAll('_',' ')} · {c.correct_count}/{c.attempt_count} correct</li>)}</ul>
      <p>UNTESTED: {r.untested.map(c=>c.name).join(', ') || 'None in the current concept graph'}</p>
      {r.misconceptions.map(d=><div key={d.id}><strong>{diagnosisLabels[d.status]}</strong><p>{d.observed}</p>{d.hypothesis && <p>Event hypothesis: {d.hypothesis}</p>}</div>)}
      {r.prerequisite_concerns.map(p=><p key={p.id}>{p.reason}</p>)}<p>{r.next_action}</p><Citations citations={r.citations}/></>}
  </section>;
}
export function ConceptEvidencePanel() {
  const {course}=useLearning(); const query=useQuery(useCallback((signal:AbortSignal)=>api.graph(course!.id,signal),[course])); const graph=query.data;
  return <section className="card"><h2>Concepts and prerequisites</h2><ErrorNotice error={query.error} retry={query.reload}/>{query.loading && <Loading/>}
    {graph?.concepts.map(c=><details key={c.id}><summary>{c.name}</summary><p>{c.description}</p><Citations citations={c.citations}/><ul>{graph.prerequisites.filter(e=>e.target_concept_id===c.id).map(e=><li key={e.id}>{graph.concepts.find(n=>n.id===e.prerequisite_concept_id)?.name} → {c.name} · {e.relation_type} · {e.source_backed?'Source-backed relationship':'Recorded relationship; source backing not verified'}</li>)}</ul></details>)}
    <p className="quiet-note">A prerequisite relationship alone does not establish learner weakness. Observation counts and assessment evidence are shown separately.</p>
  </section>;
}
