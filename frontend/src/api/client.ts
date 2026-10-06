import type {
  AskMode,
  AskResponse,
  Attempt,
  Choice,
  Course,
  CourseMastery,
  Diagnosis,
  Difficulty,
  Feedback,
  Generation,
  IndexingResult,
  LearningAttempt,
  LearningSession,
  LearningTrace,
  ProbeAttempt,
  ProcessingResult,
  Question,
  Source,
} from "./types";

export const errorMessages: Record<number, string> = {
  0: "We couldn’t reach ConceptLens. Check your connection and try again.",
  404: "This item is no longer available in the selected course. Refresh or choose another item.",
  409: "This learning session changed. Refreshing the latest step keeps your progress in sync.",
  415: "This file type isn’t supported. Choose a PDF, PPTX, or MP4 file.",
  422: "There isn’t enough verified evidence to support this action, or the input needs attention. Review your input and course material before retrying.",
  502: "The generated response couldn’t be verified. Nothing unverified will be shown. Please try again.",
  503: "The learning provider is temporarily unavailable. Your saved work is still here. Try again shortly.",
};
export class ApiError extends Error {
  constructor(
    public status: number,
    public validation: string[] = [],
    public detail: string | null = null,
  ) {
    super(
      errorMessages[status] ??
        "Something went wrong while loading your work. Please try again.",
    );
    this.name = "ApiError";
  }
}
export const isCancelled = (error: unknown) =>
  typeof error === "object" &&
  error !== null &&
  "name" in error &&
  error.name === "AbortError";
const base = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
function safePublicMessage(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= 300 &&
    !/[\r\n]|traceback|exception|stack trace|sqlalchemy|asyncpg|api[_ -]?key|password|secret|token|https?:|file:|(?:\/|\\)[a-z0-9_.-]+(?:\/|\\)|SELECT\s|INSERT\s|UPDATE\s/i.test(
      value,
    )
  );
}

export async function request<T>(
  path: string,
  options: {
    method?: "GET" | "POST";
    body?: unknown;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  const multipart = options.body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      method: options.method ?? "GET",
      signal: options.signal,
      headers:
        options.body !== undefined && !multipart
          ? { "Content-Type": "application/json" }
          : undefined,
      body:
        options.body === undefined
          ? undefined
          : multipart
            ? (options.body as FormData)
            : JSON.stringify(options.body),
    });
  } catch (error) {
    if (isCancelled(error)) throw error;
    throw new ApiError(0);
  }
  let data: unknown;
  try {
    data = await response.json();
  } catch (error) {
    if (isCancelled(error)) throw error;
    throw new ApiError(response.ok ? 502 : response.status);
  }
  if (!response.ok) {
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? data.detail
        : null;
    const validation =
      response.status === 422 && Array.isArray(detail)
        ? detail.flatMap((item: unknown) =>
            typeof item === "object" &&
            item !== null &&
            "msg" in item &&
            safePublicMessage(item.msg)
              ? [item.msg]
              : [],
          )
        : [];
    // Only expose bounded public error details. Server failures and diagnostic
    // traces/queries/paths/credentials stay out of the learner-facing surface.
    const safeDetail =
      safePublicMessage(detail) &&
      [400, 404, 409, 415, 422, 502, 503].includes(response.status)
        ? detail
        : null;
    throw new ApiError(response.status, validation, safeDetail);
  }
  return data as T;
}
const c = (course: string) => `/courses/${encodeURIComponent(course)}`;
const l = (course: string, learner: string) =>
  `${c(course)}/learners/${encodeURIComponent(learner)}`;
const sessions = (course: string, learner: string) =>
  `${l(course, learner)}/learning-sessions`;
const diagnoses = (course: string, learner: string) =>
  `${l(course, learner)}/reasoning-diagnoses`;
const post = <T>(path: string, body?: unknown, signal?: AbortSignal) =>
  request<T>(path, { method: "POST", body, signal });
export const api = {
  courses: (signal?: AbortSignal) => request<Course[]>("/courses", { signal }),
  createCourse: (name: string, description: string, signal?: AbortSignal) =>
    post<Course>(
      "/courses",
      { name, description: description || null },
      signal,
    ),
  sources: (course: string, signal?: AbortSignal) =>
    request<Source[]>(`${c(course)}/sources`, { signal }),
  upload: (course: string, file: File, signal?: AbortSignal) => {
    const body = new FormData();
    body.append("file", file);
    return post<Source>(`${c(course)}/sources`, body, signal);
  },
  process: (course: string, source: string, signal?: AbortSignal) =>
    post<ProcessingResult>(
      `${c(course)}/sources/${source}/process`,
      undefined,
      signal,
    ),
  index: (course: string, signal?: AbortSignal) =>
    post<IndexingResult>(`${c(course)}/retrieval/index`, undefined, signal),
  ask: (
    course: string,
    question: string,
    mode: AskMode,
    signal?: AbortSignal,
  ) => post<AskResponse>(`${c(course)}/ask`, { question, mode }, signal),
  generate: (
    course: string,
    focus: string,
    difficulty: Difficulty,
    signal?: AbortSignal,
  ) =>
    post<Generation>(
      `${c(course)}/assessments/generate`,
      { focus, difficulty, count: 1 },
      signal,
    ),
  question: (course: string, id: string, signal?: AbortSignal) =>
    request<Question>(`${c(course)}/assessments/questions/${id}`, { signal }),
  attempt: (
    course: string,
    learner: string,
    question: string,
    selected: number,
    signal?: AbortSignal,
  ) =>
    post<Attempt>(
      `${c(course)}/assessments/questions/${question}/attempts`,
      { learner_id: learner, selected_option_index: selected },
      signal,
    ),
  mastery: (course: string, learner: string, signal?: AbortSignal) =>
    request<CourseMastery>(`${l(course, learner)}/mastery`, { signal }),
  diagnose: (
    course: string,
    learner: string,
    attempt: string,
    text: string,
    steps: string[],
    signal?: AbortSignal,
  ) =>
    post<Diagnosis>(
      diagnoses(course, learner),
      {
        attempt_id: attempt,
        reasoning_text: text || null,
        reasoning_steps: steps,
      },
      signal,
    ),
  diagnosis: (
    course: string,
    learner: string,
    id: string,
    signal?: AbortSignal,
  ) => request<Diagnosis>(`${diagnoses(course, learner)}/${id}`, { signal }),
  probe: (
    course: string,
    learner: string,
    diagnosis: string,
    selected: number,
    signal?: AbortSignal,
  ) =>
    post<ProbeAttempt>(
      `${diagnoses(course, learner)}/${diagnosis}/probe-attempts`,
      { selected_option_index: selected },
      signal,
    ),
  startSession: (
    course: string,
    learner: string,
    diagnosis: string,
    signal?: AbortSignal,
  ) =>
    post<LearningSession>(
      sessions(course, learner),
      { diagnosis_id: diagnosis },
      signal,
    ),
  session: (
    course: string,
    learner: string,
    id: string,
    signal?: AbortSignal,
  ) =>
    request<LearningSession>(`${sessions(course, learner)}/${id}`, { signal }),
  feedback: (
    course: string,
    learner: string,
    id: string,
    intervention: string,
    feedback: Feedback,
    signal?: AbortSignal,
  ) =>
    post<LearningSession>(
      `${sessions(course, learner)}/${id}/feedback`,
      { intervention_id: intervention, feedback },
      signal,
    ),
  choice: (
    course: string,
    learner: string,
    id: string,
    intervention: string,
    choice: Choice,
    signal?: AbortSignal,
  ) =>
    post<LearningSession>(
      `${sessions(course, learner)}/${id}/prerequisite-choice`,
      { intervention_id: intervention, choice },
      signal,
    ),
  learningAttempt: (
    course: string,
    learner: string,
    id: string,
    intervention: string,
    selected: number,
    transfer: boolean,
    signal?: AbortSignal,
  ) =>
    post<LearningAttempt>(
      `${sessions(course, learner)}/${id}/${transfer ? "transfer-check/attempts" : `interventions/${intervention}/attempts`}`,
      { selected_option_index: selected },
      signal,
    ),
  trace: (course: string, learner: string, id: string, signal?: AbortSignal) =>
    request<LearningTrace>(`${sessions(course, learner)}/${id}/trace`, {
      signal,
    }),
};
