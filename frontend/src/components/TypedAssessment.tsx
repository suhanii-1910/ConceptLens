import { useState } from 'react';
import type { AnswerInput, Question, SchedulingProof } from '../api/types';
import { Button, QuestionForm } from './ui';
export function TypedAssessment({question, onSubmit, busy}: {question: Question; onSubmit: (answer: AnswerInput)=>void; busy: boolean}) {
  const [answer,setAnswer]=useState('');
  const [unit,setUnit]=useState(question.answer_unit ?? '');
  if(question.question_type === 'multiple_choice') return <QuestionForm question={question} busy={busy} onSubmit={selected=>onSubmit({selected_option_index:selected})}/>;
  return <form onSubmit={event=>{event.preventDefault(); if(!busy && answer.trim()) onSubmit(question.question_type==='short_answer'?{answer_text:answer}:{answer_value:answer,answer_unit:unit});}}>
    <h3>{question.question_text}</h3>
    {question.scenario && <details><summary>Scheduling inputs and assumptions</summary><pre>{JSON.stringify(question.scenario,null,2)}</pre></details>}
    <label>Your answer{question.question_type==='short_answer'?<textarea value={answer} onChange={e=>setAnswer(e.target.value)} maxLength={8000} required disabled={busy}/>:<input value={answer} onChange={e=>setAnswer(e.target.value)} maxLength={80} required disabled={busy} placeholder="Integer, decimal, or fraction"/>}</label>
    {question.question_type==='numerical' && question.answer_unit && <label>Units<input value={unit} onChange={e=>setUnit(e.target.value)} maxLength={32} required disabled={busy}/></label>}
    <p className="quiet-note">{question.numeric_format} Feedback follows submission.</p><Button type="submit" busy={busy} disabled={!answer.trim()}>Check my answer</Button>
  </form>;
}
export function SchedulingResult({proof}: {proof: SchedulingProof}) {
  return <details className="scheduling-proof"><summary>Deterministic scheduling proof</summary>
    <p>Execution order (start → end)</p><ol>{proof.segments.map((s,i)=><li key={i}>{s.pid ?? 'Idle'}: {s.start} → {s.end}</li>)}</ol>
    <div className="table-scroll"><table><thead><tr><th>Process</th><th>Start</th><th>Completion</th><th>Turnaround</th><th>Waiting</th><th>Response</th></tr></thead><tbody>{proof.processes.map(p=><tr key={p.pid}><th>{p.pid}</th><td>{p.start}</td><td>{p.completion}</td><td>{p.turnaround}</td><td>{p.waiting}</td><td>{p.response}</td></tr>)}</tbody></table></div>
    <p>{proof.tie_breaking}</p>
    {proof.decisions.length > 0 && <details><summary>Dispatch decisions</summary><ol>{proof.decisions.map((d,i)=><li key={i}>At {d.time}: {d.pid}, {d.remaining_before} remaining · waiting: {d.ready?.join(', ') || 'none'} · {d.algorithm}</li>)}</ol></details>}
    <p>Averages: {Object.entries(proof.averages).map(([k,v])=>`${k}: ${v}`).join(' · ')}</p><ul>{proof.assumptions.map(a=><li key={a}>{a}</li>)}</ul>
  </details>;
}
