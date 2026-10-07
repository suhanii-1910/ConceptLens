// Test-only public API fixtures. Never imported by application code.
import type {
  Attempt,
  Citation,
  Course,
  CourseMastery,
  Diagnosis,
  EvidenceBoundary,
  Intervention,
  LearningSession,
  LearningTrace,
  Question,
  Source,
  Strategy,
} from "../api/types";

export const id = (n: number) =>
  `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
export const learner = id(90);
export const date = "2026-10-06T10:00:00Z";
export const course: Course = {
  id: id(1),
  name: "Operating Systems",
  description: "Scheduling and process management",
  created_at: date,
  updated_at: date,
};
export const otherCourse: Course = {
  ...course,
  id: id(2),
  name: "Computer Networks",
};
export const citation: Citation = {
  evidence_unit_id: id(10),
  course_id: course.id,
  source_version_id: id(11),
  source_filename: "CPU Scheduling.pdf",
  source_type: "pdf",
  modality: "text",
  locator: { page_number: 4 },
  location_metadata: { page_number: 4 },
  locator_label: "Page 4",
};
export const boundary: EvidenceBoundary = {
  status: "supported",
  reason: "grounded_relevant_evidence",
  should_decline: false,
  message: null,
  candidate_count: 1,
  relevant_candidate_count: 1,
  usable_candidate_count: 1,
  usable_evidence_unit_ids: [citation.evidence_unit_id],
};
export const question: Question = {
  id: id(20),
  course_id: course.id,
  question_type: "multiple_choice",
  difficulty: "medium",
  question_text:
    "A long process arrives first. Which process runs first under FCFS?",
  options: [
    "The first arrival",
    "The shortest process",
    "Both together",
    "The last arrival",
  ],
  citations: [citation],
  created_at: date,
};
export const attempt: Attempt = {
  attempt_id: id(21),
  question_id: question.id,
  course_id: course.id,
  learner_id: learner,
  selected_option_index: 1,
  is_correct: false,
  correct_option_index: 0,
  correct_option_text: question.options[0],
  explanation:
    "Verified assessment explanation: FCFS follows arrival order, not burst length.",
  citations: [citation],
  created_at: date,
  mastery_update_status: "skipped_unmapped",
  mastery_update: null,
};
export const diagnosis: Diagnosis = {
  id: id(30),
  course_id: course.id,
  learner_id: learner,
  attempt_id: attempt.attempt_id,
  question_id: question.id,
  reasoning_text: null,
  reasoning_steps: [
    "I list both arrival times.",
    "I choose the shortest process first.",
  ],
  status: "hypothesis",
  observed_reasoning:
    "The response uses burst length to choose the first process.",
  first_break_step_index: 1,
  first_break_excerpt: "shortest process",
  hypothesis_text:
    "FCFS may have been confused with shortest-job-first scheduling in this response.",
  target_concept_id: id(40),
  prerequisites: [
    {
      edge_id: id(42),
      prerequisite_concept_id: id(41),
      target_concept_id: id(40),
      name: "Arrival order",
      relation_type: "prerequisite_of",
    },
  ],
  citations: [citation],
  probe: {
    id: id(31),
    question_type: "multiple_choice",
    question_text: "Under FCFS, what determines the next process?",
    options: ["Arrival time", "Burst length", "Process name", "Memory size"],
    citations: [citation],
  },
  cold_start: true,
  created_at: date,
  updated_at: date,
};
export function intervention(strategy: Strategy, sequence = 1): Intervention {
  const graded = [
    "prerequisite_probe",
    "prerequisite_practice",
    "transfer_check",
  ].includes(strategy);
  return {
    id: id(50 + sequence),
    sequence_index: sequence,
    strategy,
    target_concept_id: id(40),
    prerequisite_concept_id: strategy.startsWith("prerequisite")
      ? id(41)
      : null,
    prerequisite_edge_id: strategy.startsWith("prerequisite") ? id(42) : null,
    payload: graded
      ? null
      : {
          title:
            strategy === "visual_explanation"
              ? "Follow the arrival queue."
              : "Arrival order is the key.",
          body: "FCFS serves processes in the order they arrive. A shorter burst does not move a process ahead in the queue.",
          steps:
            strategy === "worked_example"
              ? [
                  "P1 arrives at time 0 and starts running.",
                  "P2 arrives at time 2 and joins the queue.",
                  "P2 starts after P1 finishes.",
                ]
              : [],
          visual:
            strategy === "visual_explanation"
              ? {
                  title: "From arrival to execution",
                  steps: [
                    {
                      label: "P1 arrives · 0 ms",
                      annotation: "The first arrival begins execution.",
                    },
                    {
                      label: "P2 arrives · 2 ms",
                      annotation: "P2 waits, even though its burst is shorter.",
                    },
                    {
                      label: "P1 finishes · 8 ms",
                      annotation:
                        "P2 now begins. The queue preserves arrival order.",
                    },
                  ],
                }
              : null,
        },
    question: graded
      ? {
          ...question,
          id: id(60 + sequence),
          question_text:
            strategy === "transfer_check"
              ? "Transfer problem: P3 arrives before P4. Which starts first under FCFS?"
              : "Which process arrived first in the queue?",
        }
      : null,
    citations: [citation],
    verified: true,
    feedback: null,
    learner_choice: null,
    completed: false,
    response_attempt_id: null,
    created_at: date,
  };
}
export function session(
  strategy: Strategy = "source_explanation",
  sequence = 1,
): LearningSession {
  return {
    id: id(70),
    course_id: course.id,
    learner_id: learner,
    diagnosis_id: diagnosis.id,
    target_concept_id: id(40),
    status: "active",
    current_action: strategy,
    reason: "The recorded response supports this next teaching action.",
    current_intervention: intervention(strategy, sequence),
    prerequisite_choices: [],
    created_at: date,
    updated_at: date,
  };
}
export function mastery(observed = false): CourseMastery {
  return {
    course_id: course.id,
    learner_id: learner,
    model_version: "bkt-v1",
    concepts: [
      {
        concept_id: id(40),
        concept_name: "First-come, first-served scheduling",
        course_id: course.id,
        learner_id: learner,
        model_version: "bkt-v1",
        mastery_probability: observed ? 0.62 : 0.2,
        observation_count: observed ? 2 : 0,
        correct_count: observed ? 1 : 0,
        mastery_band: observed ? "developing" : "unseen",
        last_attempt_id: observed ? id(80) : null,
        created_at: observed ? date : null,
        updated_at: observed ? date : null,
      },
      {
        concept_id: id(41),
        concept_name: "Arrival order",
        course_id: course.id,
        learner_id: learner,
        model_version: "bkt-v1",
        mastery_probability: 0.2,
        observation_count: 0,
        correct_count: 0,
        mastery_band: "unseen",
        last_attempt_id: null,
        created_at: null,
        updated_at: null,
      },
    ],
  };
}
export function trace(current = session()): LearningTrace {
  return {
    session: current,
    observed: {
      diagnosis_id: diagnosis.id,
      assessment_attempt_id: attempt.attempt_id,
      question_id: question.id,
      reasoning_text: diagnosis.reasoning_text,
      reasoning_steps: diagnosis.reasoning_steps,
      observed_reasoning: diagnosis.observed_reasoning,
      first_break_step_index: diagnosis.first_break_step_index,
      first_break_excerpt: diagnosis.first_break_excerpt,
    },
    hypothesis: diagnosis.hypothesis_text,
    diagnostic_evidence: [
      {
        attempt_id: id(32),
        probe_id: id(31),
        selected_option_index: 1,
        is_correct: false,
        applied_outcome: "confirmed",
        created_at: date,
      },
    ],
    interpretation: "confirmed",
    teaching_actions: [
      intervention("source_explanation"),
      intervention("visual_explanation", 2),
    ],
    transfer_result:
      current.status === "complete"
        ? {
            transfer_check_id: id(80),
            question_id: id(66),
            status: "passed",
            resolved_attempt_id: id(81),
            is_correct: true,
            mastery_update_status: "updated",
          }
        : null,
    learner_updates: [],
    proof: {
      source_location_verified: true,
      diagnostic_question_verified: true,
      citation_valid: true,
      teaching_content_verified: true,
      transfer_check_verified: current.status === "complete",
      learner_update_based_on_verified_evidence: false,
    },
  };
}
export type TestReply = { status: number; body: unknown };
export function scenario() {
  let current = session();
  let diagnosed = { ...diagnosis };
  let sources: Source[] = [];
  let observed = false;
  let stale: string | null = null;
  const calls: {
    path: string;
    method: string;
    body: Record<string, unknown>;
  }[] = [];
  const ok = (body: unknown): TestReply => ({ status: 200, body });
  return {
    calls,
    setSession(value: LearningSession) {
      current = value;
      diagnosed = { ...diagnosis, status: "confirmed" };
    },
    setSources(value: Source[]) {
      sources = value;
    },
    conflict(path: string) {
      stale = path;
    },
    handle(
      path: string,
      method = "GET",
      body: Record<string, unknown> = {},
    ): TestReply {
      calls.push({ path, method, body });
      if (method === "POST" && stale && path.endsWith(stale)) {
        stale = null;
        current = session("visual_explanation", 2);
        return {
          status: 409,
          body: { detail: "Intervention is no longer current." },
        };
      }
      if (path === "/courses") return ok([course, otherCourse]);
      if (path.endsWith("/sources")) {
        if (method === "POST") {
          sources = [
            {
              id: id(12),
              course_id: course.id,
              original_filename: "CPU Scheduling.pdf",
              source_type: "pdf",
              processing_status: "uploaded",
              created_at: date,
            },
          ];
          return ok(sources[0]);
        }
        return ok(sources);
      }
      if (path.endsWith("/process")) {
        sources = sources.map((s) => ({ ...s, processing_status: "ready" }));
        return ok({
          source_version_id: id(11),
          processing_status: "ready",
          page_count: 8,
          slide_count: null,
          duration_seconds: null,
          text_evidence_count: 12,
          table_evidence_count: 0,
          image_evidence_count: 0,
          video_evidence_count: 0,
          warnings: [],
          already_processed: false,
        });
      }
      if (path.endsWith("/retrieval/index"))
        return ok({
          total_evidence: 12,
          searchable_evidence: 12,
          embedded_count: 12,
          skipped_unchanged_count: 0,
          skipped_no_text_count: 0,
        });
      if (path.endsWith("/ask"))
        return ok(
          body.question === "Unsupported topic"
            ? {
                status: "declined",
                mode: body.mode,
                answer: null,
                blocks: [],
                next_question: null,
                decline_message: "Your sources do not support this topic.",
                evidence_boundary: {
                  ...boundary,
                  status: "unsupported",
                  should_decline: true,
                },
                used_evidence_unit_ids: [],
              }
            : {
                status: "answered",
                mode: body.mode,
                answer: "Arrival order controls FCFS.",
                blocks: [
                  {
                    text: "FCFS runs each process in arrival order. A short process waits behind an earlier long process.",
                    citations: [citation],
                  },
                ],
                next_question:
                  body.mode === "guide"
                    ? "Which process entered the queue first?"
                    : null,
                decline_message: null,
                evidence_boundary: boundary,
                used_evidence_unit_ids: [id(10)],
              },
        );
      if (path.endsWith("/assessments/generate"))
        return ok({
          status: "generated",
          questions: [question],
          requested_count: 1,
          generated_count: 1,
          rejected_count: 0,
          decline_message: null,
          evidence_boundary: boundary,
        });
      if (
        path.includes("/assessments/questions/") &&
        path.endsWith("/attempts")
      )
        return ok({
          ...attempt,
          selected_option_index: body.selected_option_index,
        });
      if (path.endsWith(`/assessments/questions/${question.id}`))
        return ok(question);
      if (path.endsWith("/reasoning-diagnoses")) {
        diagnosed = {
          ...diagnosis,
          reasoning_text: body.reasoning_text as string,
          reasoning_steps: body.reasoning_steps as string[],
        };
        return ok(diagnosed);
      }
      if (path.endsWith("/probe-attempts")) {
        diagnosed = { ...diagnosed, status: "confirmed" };
        return ok({
          attempt_id: id(32),
          probe_id: id(31),
          diagnosis_id: diagnosis.id,
          selected_option_index: body.selected_option_index,
          is_correct: false,
          correct_option_index: 0,
          explanation:
            "Verified probe explanation: arrival time determines FCFS order.",
          citations: [citation],
          diagnostic_outcome: "confirmed",
          resolution_applied: true,
          created_at: date,
        });
      }
      if (path.endsWith(`/reasoning-diagnoses/${diagnosis.id}`))
        return ok(diagnosed);
      if (
        path.endsWith("/learning-sessions") ||
        path.endsWith(`/learning-sessions/${current.id}`)
      )
        return ok(current);
      if (path.endsWith("/feedback")) {
        current =
          current.current_action === "source_explanation"
            ? session("visual_explanation", 2)
            : current.current_action === "visual_explanation"
              ? session("prerequisite_probe", 3)
              : current.current_action === "prerequisite_recap"
                ? session("worked_example", 5)
                : session("transfer_check", 6);
        return ok(current);
      }
      if (path.endsWith("/prerequisite-choice")) {
        current =
          body.choice === "sixty_second_recap"
            ? session("prerequisite_recap", 4)
            : body.choice === "practice_prerequisite"
              ? session("prerequisite_practice", 4)
              : session("worked_example", 5);
        return ok(current);
      }
      if (path.includes("/learning-sessions/") && path.endsWith("/attempts")) {
        const transfer = path.includes("/transfer-check/");
        const response: Attempt = {
          ...attempt,
          attempt_id: id(80 + calls.length),
          question_id: current.current_intervention!.question!.id,
          selected_option_index: Number(body.selected_option_index),
          is_correct: transfer,
          explanation: transfer
            ? "Verified transfer explanation: arrival order still controls the new situation."
            : "Verified prerequisite explanation: identify the earlier arrival.",
          mastery_update_status: transfer ? "updated" : "skipped_unmapped",
          mastery_update: transfer
            ? {
                concept_id: id(40),
                concept_name: "First-come, first-served scheduling",
                prior_mastery: 0.2,
                posterior_mastery: 0.52,
                updated_mastery: 0.62,
                mastery_band: "developing",
                observation_count: 2,
                correct_count: 1,
                model_version: "bkt-v1",
              }
            : null,
        };
        current = transfer
          ? {
              ...current,
              current_action: "complete",
              status: "complete",
              current_intervention: null,
            }
          : current.current_action === "prerequisite_practice"
            ? session("worked_example", 5)
            : {
                ...current,
                current_action: "prerequisite_choice",
                prerequisite_choices: [
                  "sixty_second_recap",
                  "practice_prerequisite",
                  "continue_anyway",
                ],
              };
        if (transfer) observed = true;
        return ok({ session: current, attempt: response });
      }
      if (path.endsWith("/trace")) return ok(trace(current));
      if (path.endsWith("/mastery")) return ok(mastery(observed));
      return { status: 404, body: { detail: "Test route not found." } };
    },
  };
}
