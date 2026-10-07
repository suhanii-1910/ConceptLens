// TEST FIXTURE — NOT A SUBMISSION RESULT. UI contract testing only.
import { scenario, course, learner, question, citation, attempt, date, id } from './scenario';
import type { AssessmentReport, Citation, Diagnostic, Question, SchedulingProof } from '../api/types';
export const schedulingProof: SchedulingProof = {segments:[{pid:'P1',start:0,end:8},{pid:'P2',start:8,end:12}],processes:[{pid:'P1',start:0,completion:8,turnaround:8,waiting:0,response:0},{pid:'P2',start:8,completion:12,turnaround:7,waiting:3,response:3}],averages:{completion:10,turnaround:7.5,waiting:1.5,response:1.5},decisions:[],assumptions:['One CPU','Integer ticks','No context-switch overhead']};
export const visualCitation: Citation={...citation,modality:'image'};
export const pptCitation: Citation={...citation,evidence_unit_id:id(14),source_type:'pptx',source_version_id:id(12),source_filename:'Scheduling slides.pptx',locator:{slide_number:2},locator_label:'Slide 2'};
export const videoCitation: Citation={...citation,evidence_unit_id:id(15),source_type:'video',source_version_id:id(13),source_filename:'Scheduling lecture.mp4',locator:{start_seconds:3,end_seconds:8},locator_label:'00:03–00:08'};
export const numerical: Question={...question,id:id(101),question_type:'numerical',question_text:'Under SRTF, P1 arrives at 0 with burst 8; P2 arrives at 5 with burst 4. When does P1 complete?',options:[],answer_unit:'ticks',numeric_format:'integer',scenario:{algorithm:'srtf',processes:[{pid:'P1',arrival:0,burst:8},{pid:'P2',arrival:5,burst:4}]}};
export const shortAnswer: Question={...question,id:id(102),question_type:'short_answer',question_text:'Explain why SRTF compares remaining time.',options:[]};
export function phase10Scenario() {
  const base=scenario(); const completed=new Set<string>(); let started=false; let generated=question; const types=new Set<string>();
  const questions=[0,1,2].map((i)=>({...question,id:id(110+i),question_text:`Diagnostic ${i+1}: ${question.question_text}`}));
  const diagnostic=():Diagnostic=>({id:id(120),status:!started?'not_started':completed.size===3?'complete':'in_progress',question_count:started?3:0,questions:started?questions:[],completed_question_ids:[...completed],message:'Untested concepts remain UNTESTED.'});
  return { ...base, handle(path:string,method='GET',body:Record<string,unknown>={}) {
    const plain=path.split('?')[0];
    if(plain.endsWith('/diagnostic')){if(method==='POST')started=true;return {status:200,body:diagnostic()};}
    if(plain.endsWith('/concept-evidence'))return {status:200,body:{concepts:[{id:id(31),name:'Remaining time',description:'A curated course concept.',citations:[citation]}],prerequisites:[]}};
    if(plain.endsWith('/assessment-report')) {
      const report: AssessmentReport={attempt_count:completed.size+types.size,scored_question_count:completed.size+types.size,correct_count:completed.size+(types.has('short_answer')?1:0),score:types.size?0.5:null,cannot_grade_count:0,repeated_attempts_excluded:0,scoring_policy:'First gradable attempt per question. Small samples are provisional.',by_type:Object.fromEntries([...types].map(t=>[t,{attempt_count:1,correct_count:t==='short_answer'?1:0}])),concepts:types.size?[{concept_id:id(31),name:'Remaining time',status:'observed_uncertain',attempt_count:types.size,correct_count:1}]:[],untested:[{id:id(32),name:'Priority scheduling',description:null,citations:[]}],misconceptions:[],prerequisite_concerns:[],next_action:'Review cited source evidence and try a fresh question.',citations:types.size?[citation]:[]};
      return {status:200,body:report};
    }
    if(plain.endsWith('/sources') && method==='GET')return {status:200,body:[citation,pptCitation,videoCitation].map(c=>({id:c.source_version_id,course_id:course.id,source_type:c.source_type,original_filename:c.source_filename,processing_status:'ready',created_at:date}))};
    if(plain.endsWith('/location')) {
      const params=new URLSearchParams(path.split('?')[1]);const kind=params.get('kind') ?? 'page';const source=kind==='slide'?pptCitation:kind==='time'?videoCitation:citation;
      const prefix=`/courses/${course.id}/sources/${source.source_version_id}`;
      return {status:200,body:{source_id:source.source_version_id,source_type:source.source_type,filename:source.source_filename,locator:{kind,number:Number(params.get('number')),start:Number(params.get('start')),end:Number(params.get('end'))},file_url:prefix+'/file',preview_url:kind==='time'?null:prefix+'/preview',preview_note:kind==='slide'?'Original slide content preview; complex Office effects may differ.':null}};
    }
    const visual={evidence_unit_id:citation.evidence_unit_id,citation:visualCitation,modality:'image',evidence_type:'figure',asset_extracted:true,semantic_state:'verified',semantic_description:'Fixture: the timeline shows P1 continuing at t=5.',text:null,table_rows:[['Process','Burst'],['P1','8'],['P2','4']],asset_url:`/courses/${course.id}/evidence/${citation.evidence_unit_id}/asset`};
    if(plain.endsWith('/evidence'))return {status:200,body:[{...visual,citation:plain.includes(id(12))?pptCitation:plain.includes(id(13))?videoCitation:visualCitation}]};
    if(plain.includes('/evidence/'))return {status:200,body:visual};
    if(plain.endsWith('/assessments/generate')) {generated=body.question_type==='short_answer'?shortAnswer:body.question_type==='numerical'?numerical:question;return {status:200,body:{status:'generated',questions:[generated],requested_count:1,generated_count:1,rejected_count:0,decline_message:null}};}
    if(plain.includes('/assessments/questions/') && plain.endsWith('/attempts')) {
      const qid=plain.split('/').at(-2)!;
      if(questions.some(q=>q.id===qid)){completed.add(qid);return {status:200,body:{...attempt,question_id:qid,is_correct:true}};}
      types.add(generated.question_type);
      if(generated.question_type!=='multiple_choice')return {status:200,body:{...attempt,question_id:generated.id,question_type:generated.question_type,selected_option_index:null,correct_option_index:null,submitted_answer:body.answer_text ?? body.answer_value,is_correct:generated.question_type==='short_answer',correct_option_text:generated.question_type==='numerical'?'8 ticks':'Compare remaining execution.',grading:{verdict:generated.question_type==='numerical'?'incorrect':'correct',method:generated.question_type==='numerical'?'deterministic_scheduler':'grounded_semantic_evaluator',solution_proof:generated.question_type==='numerical'?schedulingProof:undefined}}};
    }
    if(plain.endsWith(`/assessments/questions/${numerical.id}`))return {status:200,body:numerical};
    const reply=base.handle(plain,method,body);
    if(plain.endsWith('/ask') && (reply.body as {status:string}).status==='answered')return {status:200,body:{...(reply.body as object),blocks:[{text:'The source compares remaining execution time.',citations:[visualCitation,pptCitation,videoCitation]}]}};
    return reply;
  }};
}
export {course,learner};
