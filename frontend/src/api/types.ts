/** Public contracts from backend/app/schemas; no provider draft or answer-key types on public questions. */
export interface Course {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}
export interface Source {
  id: string;
  course_id: string;
  original_filename: string;
  source_type: "pdf" | "pptx" | "video";
  processing_status: "uploaded" | "processing" | "ready" | "failed";
  created_at: string;
}
export interface ProcessingResult {
  source_version_id: string;
  processing_status: string;
  page_count: number | null;
  slide_count: number | null;
  duration_seconds: number | null;
  text_evidence_count: number;
  table_evidence_count: number;
  image_evidence_count: number;
  video_evidence_count: number;
  warnings: string[];
  already_processed: boolean;
}
export interface IndexingResult {
  total_evidence: number;
  searchable_evidence: number;
  embedded_count: number;
  skipped_unchanged_count: number;
  skipped_no_text_count: number;
}
export interface Citation {
  evidence_unit_id: string;
  course_id: string;
  source_version_id: string;
  source_filename: string;
  source_type: "pdf" | "pptx" | "video";
  modality: string;
  locator: Record<string, unknown>;
  location_metadata: Record<string, unknown>;
  locator_label: string;
}
export interface EvidenceBoundary {
  status: "supported" | "insufficient_evidence" | "unsupported";
  reason:
    | "grounded_relevant_evidence"
    | "no_candidates"
    | "no_relevant_evidence"
    | "relevant_evidence_not_grounded";
  should_decline: boolean;
  message: string | null;
  candidate_count: number;
  relevant_candidate_count: number;
  usable_candidate_count: number;
  usable_evidence_unit_ids: string[];
}
export type AskMode = "just_answer" | "explain" | "guide";
export interface AskResponse {
  status: "answered" | "declined";
  mode: AskMode;
  answer: string | null;
  blocks: { text: string; citations: Citation[] }[];
  next_question: string | null;
  decline_message: string | null;
  evidence_boundary: EvidenceBoundary;
  used_evidence_unit_ids: string[];
}
export type Difficulty = "easy" | "medium" | "hard";
export interface Question {
  id: string;
  course_id: string;
  question_type: "multiple_choice" | "short_answer" | "numerical";
  answer_unit?: string | null;
  numeric_format?: string | null;
  scenario?: Record<string, unknown> | null;
  difficulty: Difficulty;
  question_text: string;
  options: string[];
  citations: Citation[];
  created_at: string;
}
export interface Generation {
  status: "generated" | "declined" | "no_verified_questions";
  questions: Question[];
  requested_count: number;
  generated_count: number;
  rejected_count: number;
  decline_message: string | null;
  evidence_boundary: EvidenceBoundary;
}
export type MasteryStatus =
  | "updated"
  | "skipped_unmapped"
  | "skipped_ambiguous"
  | "skipped_repeated_question";
export type MasteryBand =
  "unseen" | "needs_work" | "developing" | "strong" | "mastered";
export interface MasteryUpdate {
  concept_id: string;
  concept_name: string;
  prior_mastery: number;
  posterior_mastery: number;
  updated_mastery: number;
  mastery_band: MasteryBand;
  observation_count: number;
  correct_count: number;
  model_version: string;
}
export interface Attempt {
  attempt_id: string;
  question_id: string;
  course_id: string;
  learner_id: string;
  selected_option_index: number | null;
  is_correct: boolean | null;
  correct_option_index: number | null;
  correct_option_text: string | null;
  question_type?: Question["question_type"];
  submitted_answer?: string | null;
  grading?: { verdict: string; explanation: string; method: string; solution_proof?: SchedulingProof } | null;
  explanation: string;
  citations: Citation[];
  created_at: string;
  mastery_update_status: MasteryStatus | null;
  mastery_update: MasteryUpdate | null;
}
export interface Mastery {
  concept_id: string;
  concept_name: string;
  course_id: string;
  learner_id: string;
  model_version: string;
  mastery_probability: number;
  observation_count: number;
  correct_count: number;
  mastery_band: MasteryBand;
  last_attempt_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}
export interface CourseMastery {
  course_id: string;
  learner_id: string;
  model_version: string;
  concepts: Mastery[];
}
export type Resolution = "confirmed" | "rejected" | "inconclusive";
export type DiagnosisStatus =
  | "hypothesis"
  | "no_clear_break"
  | "insufficient_reasoning"
  | "insufficient_evidence"
  | Resolution;
export interface Prerequisite {
  edge_id: string;
  prerequisite_concept_id: string;
  target_concept_id: string;
  name: string;
  relation_type: string;
}
export interface Probe {
  id: string;
  question_type: "multiple_choice";
  question_text: string;
  options: string[];
  citations: Citation[];
}
export interface Diagnosis {
  id: string;
  course_id: string;
  learner_id: string;
  attempt_id: string;
  question_id: string;
  reasoning_text: string | null;
  reasoning_steps: string[];
  status: DiagnosisStatus;
  observed_reasoning: string | null;
  first_break_step_index: number | null;
  first_break_excerpt: string | null;
  hypothesis_text: string | null;
  target_concept_id: string | null;
  prerequisites: Prerequisite[];
  citations: Citation[];
  probe: Probe | null;
  cold_start: boolean;
  created_at: string;
  updated_at: string;
}
export interface ProbeAttempt {
  attempt_id: string;
  probe_id: string;
  diagnosis_id: string;
  selected_option_index: number;
  is_correct: boolean | null;
  correct_option_index: number | null;
  explanation: string | null;
  citations: Citation[];
  diagnostic_outcome: Resolution;
  resolution_applied: boolean;
  created_at: string;
}
export type Strategy =
  | "source_explanation"
  | "visual_explanation"
  | "prerequisite_probe"
  | "prerequisite_recap"
  | "prerequisite_practice"
  | "worked_example"
  | "transfer_check";
export type Action =
  | Strategy
  | "prerequisite_choice"
  | "reconsider_diagnosis"
  | "complete"
  | "collect_more_reasoning"
  | "general_practice"
  | "diagnostic_probe";
export type Feedback = "understood" | "still_confused";
export type Choice =
  "sixty_second_recap" | "practice_prerequisite" | "continue_anyway";
export interface TeachingPayload {
  title: string;
  body: string;
  steps: string[];
  visual: {
    title: string;
    steps: { label: string; annotation: string }[];
  } | null;
}
export interface Intervention {
  id: string;
  sequence_index: number;
  strategy: Strategy;
  target_concept_id: string;
  prerequisite_concept_id: string | null;
  prerequisite_edge_id: string | null;
  payload: TeachingPayload | null;
  question: Question | null;
  citations: Citation[];
  verified: boolean;
  feedback: Feedback | null;
  learner_choice: Choice | null;
  completed: boolean;
  response_attempt_id: string | null;
  created_at: string;
}
export interface LearningSession {
  id: string;
  course_id: string;
  learner_id: string;
  diagnosis_id: string;
  target_concept_id: string | null;
  status:
    "active" | "complete" | "diagnosis_not_confirmed" | "needs_reassessment";
  current_action: Action;
  reason: string;
  current_intervention: Intervention | null;
  prerequisite_choices: Choice[];
  created_at: string;
  updated_at: string;
}
export interface LearningAttempt {
  session: LearningSession;
  attempt: Attempt;
}
export interface Proof {
  source_location_verified: boolean;
  diagnostic_question_verified: boolean;
  citation_valid: boolean;
  teaching_content_verified: boolean;
  transfer_check_verified: boolean;
  learner_update_based_on_verified_evidence: boolean;
}
export interface LearningTrace {
  session: LearningSession;
  observed: {
    diagnosis_id: string;
    assessment_attempt_id: string;
    question_id: string;
    reasoning_text: string | null;
    reasoning_steps: string[];
    observed_reasoning: string | null;
    first_break_step_index: number | null;
    first_break_excerpt: string | null;
  };
  hypothesis: string | null;
  diagnostic_evidence: {
    attempt_id: string;
    probe_id: string;
    selected_option_index: number;
    is_correct: boolean | null;
    applied_outcome: Resolution | null;
    created_at: string;
  }[];
  interpretation: DiagnosisStatus;
  teaching_actions: Intervention[];
  transfer_result: {
    transfer_check_id: string;
    question_id: string;
    status: "pending" | "passed" | "failed";
    resolved_attempt_id: string | null;
    is_correct: boolean | null;
    mastery_update_status: MasteryStatus | null;
  } | null;
  learner_updates: {
    observation_id: string;
    attempt_id: string;
    concept_id: string;
    observation_index: number;
    prior_mastery: number;
    updated_mastery: number;
    model_version: string;
    created_at: string;
  }[];
  proof: Proof;
}

export type AnswerInput = { selected_option_index: number } | { answer_text: string } | { answer_value: string; answer_unit?: string };
export interface SourceLocation { source_id: string; source_type: Source['source_type']; filename: string; file_url: string; preview_url: string | null; preview_note: string | null; locator: { kind: string; number?: number; start?: number; end?: number } }
export interface VisualEvidence { evidence_unit_id: string; citation: Citation; modality: string; evidence_type: string; asset_extracted: boolean; semantic_state: string; semantic_description: string | null; text: string | null; table_rows: string[][] | null; asset_url: string | null }
export interface Diagnostic { id?: string; status: 'not_started' | 'in_progress' | 'complete'; question_count: number; questions: Question[]; completed_question_ids: string[]; message?: string }
export interface ConceptEvidence { id: string; name: string; description: string | null; citations: Citation[] }
export interface ConceptGraph { concepts: ConceptEvidence[]; prerequisites: { id: string; prerequisite_concept_id: string; target_concept_id: string; relation_type: string; source_backed: boolean; confidence: number | null }[] }
export interface AssessmentReport { attempt_count: number; scored_question_count: number; correct_count: number; score: number | null; cannot_grade_count: number; repeated_attempts_excluded: number; scoring_policy: string; by_type: Record<string, {attempt_count: number; correct_count: number}>; concepts: { concept_id: string; name: string; status: string; attempt_count: number; correct_count: number }[]; untested: ConceptEvidence[]; misconceptions: { id: string; status: DiagnosisStatus; hypothesis: string | null; observed: string | null }[]; prerequisite_concerns: { id: string; reason: string }[]; next_action: string; citations: Citation[] }
export interface SchedulingProof { segments: {pid: string | null; start: number; end: number}[]; processes: {pid: string; start: number; completion: number; turnaround: number; waiting: number; response: number}[]; averages: Record<string, number>; assumptions: string[]; tie_breaking?: string; decisions: { time: number; pid: string; remaining_before?: number; ready?: string[]; algorithm?: string }[] }
