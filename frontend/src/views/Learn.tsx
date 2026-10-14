import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  Fingerprint,
  Focus,
  GitBranch,
  ScanLine,
} from "lucide-react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type {
  Attempt,
  Choice,
  Diagnosis,
  Feedback,
  LearningAttempt,
  LearningSession,
  ProbeAttempt,
  Question,
} from "../api/types";
import { useQuery, useTask } from "../hooks";
import { useLearning, type JourneyRefs } from "../state";
import { ConceptEvidencePanel } from "../components/ConceptExplorer";
import { QuestionGenerator } from "../components/QuestionGenerator";
import { ReasoningDebugger, ReasoningEditor } from "../components/Reasoning";
import { Teaching, actionLabels } from "../components/Teaching";
import { TracePanel } from "../components/TracePanel";
import {
  AttemptResult,
  Button,
  Citations,
  diagnosisLabels,
  ErrorNotice,
  Loading,
  NoCourse,
  PageHeading,
  QuestionForm,
} from "../components/ui";

export function Learn() {
  const { course } = useLearning();
  return (
    <>
      <PageHeading
        eyebrow="Learn / The reasoning workspace"
        title="Make the connections. Find your clarity."
        description="Follow your reasoning, test a possible gap, and find a learning approach that helps."
      />
      {course ? <LearningJourney /> : <NoCourse />}
    </>
  );
}
interface Restored {
  refs: JourneyRefs;
  question?: Question;
  diagnosis?: Diagnosis;
  session?: LearningSession;
  notice: string;
}
export function validReasoning(text: string, steps: string[]) {
  return (
    [...text].length <= 8000 &&
    steps.length <= 20 &&
    steps.every((step) => !!step.trim() && [...step].length <= 1000) &&
    [...text, ...steps.join("")].length <= 12000 &&
    (!!text.trim() || steps.length > 0)
  );
}
function LearningJourney() {
  const { course, learner, refs, remember } = useLearning();
  const initialRefs = useRef(refs);
  const restore = useQuery(
    useCallback(
      async (signal: AbortSignal): Promise<Restored> => {
        let saved = { ...initialRefs.current };
        let question: Question | undefined,
          diagnosis: Diagnosis | undefined,
          session: LearningSession | undefined;
        let notice = "";
        const gone = (error: unknown) =>
          error instanceof ApiError && error.status === 404;
        if (saved.question_id) {
          try {
            question = await api.question(
              course!.id,
              saved.question_id,
              signal,
            );
          } catch (error) {
            if (!gone(error)) throw error;
            saved = {};
            notice =
              "The saved problem is no longer available. Start with a fresh one.";
          }
        }
        if (saved.diagnosis_id) {
          try {
            diagnosis = await api.diagnosis(
              course!.id,
              learner,
              saved.diagnosis_id,
              signal,
            );
            if (question?.id !== diagnosis.question_id)
              question = await api.question(
                course!.id,
                diagnosis.question_id,
                signal,
              );
            saved = {
              ...saved,
              question_id: diagnosis.question_id,
              attempt_id: diagnosis.attempt_id,
            };
          } catch (error) {
            if (!gone(error)) throw error;
            diagnosis = undefined;
            saved = {
              question_id: saved.question_id,
              attempt_id: saved.attempt_id,
            };
            notice =
              "The saved diagnosis is no longer available. You can explain your reasoning again.";
          }
        }
        if (saved.session_id && diagnosis) {
          try {
            session = await api.session(
              course!.id,
              learner,
              saved.session_id,
              signal,
            );
            if (session.diagnosis_id !== diagnosis.id) throw new ApiError(404);
          } catch (error) {
            if (!gone(error)) throw error;
            session = undefined;
            saved = {
              question_id: saved.question_id,
              attempt_id: saved.attempt_id,
              diagnosis_id: saved.diagnosis_id,
            };
            notice =
              "The saved learning session is no longer available. Your reasoning record is still here.";
          }
        } else if (saved.session_id) {
          saved = {
            question_id: saved.question_id,
            attempt_id: saved.attempt_id,
          };
        }
        return { refs: saved, question, diagnosis, session, notice };
      },
      [course, learner],
    ),
  );
  const [showInitialMap] = useState(() => typeof window.matchMedia !== "function" || !window.matchMedia("(max-width: 760px)").matches);
  const [question, setQuestion] = useState<Question>();
  const [attemptId, setAttemptId] = useState<string>();
  const [diagnosis, setDiagnosis] = useState<Diagnosis>();
  const [session, setSession] = useState<LearningSession>();
  const [text, setText] = useState("");
  const [steps, setSteps] = useState<string[]>([]);
  const [probeResult, setProbeResult] = useState<ProbeAttempt>();
  const [results, setResults] = useState<Attempt[]>([]);
  const [notice, setNotice] = useState("");
  const [traceOpen, setTraceOpen] = useState(false);
  const task = useTask();
  useEffect(() => {
    if (!restore.data) return;
    const saved = restore.data;
    setQuestion(saved.question);
    setAttemptId(saved.refs.attempt_id);
    setDiagnosis(saved.diagnosis);
    setSession(saved.session);
    setNotice(saved.notice);
    remember(saved.refs);
  }, [restore.data, remember]);
  const selectQuestion = (next: Question) => {
    setQuestion(next);
    setAttemptId(undefined);
    setDiagnosis(undefined);
    setSession(undefined);
    setResults([]);
    setProbeResult(undefined);
    setText("");
    setSteps([]);
    setTraceOpen(false);
    setNotice("");
    remember({ question_id: next.id });
  };
  const restart = () => {
    setQuestion(undefined);
    setAttemptId(undefined);
    setDiagnosis(undefined);
    setSession(undefined);
    setResults([]);
    setProbeResult(undefined);
    setText("");
    setSteps([]);
    setTraceOpen(false);
    setNotice("");
    task.clearError();
    remember({});
  };
  const answer = async (selected: number) => {
    if (!question) return;
    const result = await task.run((signal) =>
      api.attempt(course!.id, learner, question.id, selected, signal),
    );
    if (result) {
      setAttemptId(result.attempt_id);
      setResults([result]);
      remember({ question_id: question.id, attempt_id: result.attempt_id });
    }
  };
  const debug = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!attemptId || !question || !validReasoning(text, steps)) return;
    const result = await task.run(async (signal) => {
      try {
        return await api.diagnose(
          course!.id,
          learner,
          attemptId,
          text,
          steps,
          signal,
        );
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          setAttemptId(undefined);
          remember({ question_id: question.id });
          setNotice(
            "The saved response is no longer available. Answer this problem again to continue.",
          );
        }
        throw error;
      }
    });
    if (result) {
      setDiagnosis(result);
      remember({
        question_id: question.id,
        attempt_id: attemptId,
        diagnosis_id: result.id,
      });
    }
  };
  const submitProbe = async (selected: number) => {
    if (!diagnosis) return;
    const result = await task.run((signal) =>
      api.probe(course!.id, learner, diagnosis.id, selected, signal),
    );
    if (result) {
      setProbeResult(result);
      const refreshed = await task.run((signal) =>
        api.diagnosis(course!.id, learner, diagnosis.id, signal),
      );
      if (refreshed) setDiagnosis(refreshed);
    }
  };
  const acceptSession = (next: LearningSession) => {
    setSession(next);
    setTraceOpen(false);
    remember({
      question_id: question?.id,
      attempt_id: attemptId,
      diagnosis_id: next.diagnosis_id,
      session_id: next.id,
    });
  };
  const start = async () => {
    if (!diagnosis) return;
    const result = await task.run((signal) =>
      api.startSession(course!.id, learner, diagnosis.id, signal),
    );
    if (result) acceptSession(result);
  };
  const sessionAction = async (
    operation: (
      signal: AbortSignal,
    ) => Promise<LearningSession | LearningAttempt>,
  ) => {
    if (!session) return;
    setNotice("");
    const result = await task.run(async (signal) => {
      try {
        return await operation(signal);
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          const fresh = await api.session(
            course!.id,
            learner,
            session.id,
            signal,
          );
          setNotice(
            "This learning step changed. You’re now seeing the latest saved step.",
          );
          return fresh;
        }
        throw error;
      }
    });
    if (result) {
      if ("session" in result) {
        setResults((previous) => [...previous, result.attempt]);
        acceptSession(result.session);
      } else acceptSession(result);
    }
  };
  const sendFeedback = (feedback: Feedback) => {
    if (session?.current_intervention)
      void sessionAction((signal) =>
        api.feedback(
          course!.id,
          learner,
          session.id,
          session.current_intervention!.id,
          feedback,
          signal,
        ),
      );
  };
  const sendChoice = (choice: Choice) => {
    if (session?.current_intervention)
      void sessionAction((signal) =>
        api.choice(
          course!.id,
          learner,
          session.id,
          session.current_intervention!.id,
          choice,
          signal,
        ),
      );
  };
  const sendAttempt = (selected: number) => {
    if (session?.current_intervention)
      void sessionAction((signal) =>
        api.learningAttempt(
          course!.id,
          learner,
          session.id,
          session.current_intervention!.id,
          selected,
          session.current_action === "transfer_check",
          signal,
        ),
      );
  };
  const revise = () => {
    setDiagnosis(undefined);
    setSession(undefined);
    setProbeResult(undefined);
    setTraceOpen(false);
    remember({ question_id: question?.id, attempt_id: attemptId });
  };
  if (restore.loading)
    return <Loading label="Restoring your learning workspace…" />;
  if (restore.error)
    return <ErrorNotice error={restore.error} retry={restore.reload} />;
  const stages = [
    { label: "Reasoning", active: !!attemptId },
    { label: "Debug", active: !!diagnosis },
    { label: "Repair", active: !!session },
    {
      label: "Transfer",
      active:
        session?.current_action === "transfer_check" ||
        session?.status === "complete",
    },
  ];
  return (
    <>
      <ol className="journey-rail" aria-label="Learning journey">
        {stages.map((stage, index) => (
          <li className={stage.active ? "reached" : ""} key={stage.label}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            {stage.label}
            <small>{stage.active ? "Reached" : "Ahead"}</small>
          </li>
        ))}
      </ol>
      <details className="learn-atlas" open={!question && showInitialMap}>
        <summary>Explore concepts and source connections</summary>
        <ConceptEvidencePanel />
      </details>
      <div className="learn-layout">
        <div className="learn-main">
          {notice && (
            <p className="notice" role="status">
              {notice}
            </p>
          )}
          <ErrorNotice error={task.error} />
          {!question && (
            <QuestionGenerator
              purpose="reasoning"
              onQuestion={selectQuestion}
            />
          )}
          {question && !diagnosis && (
            <section className="card">
              <div className="section-heading">
                <Focus size={23} />
                <div>
                  <p className="eyebrow">Your starting problem</p>
                  <h2>
                    {attemptId
                      ? "Now show us how you got there."
                      : "First, work through the problem."}
                  </h2>
                </div>
              </div>
              {!attemptId ? (
                <>
                  <QuestionForm
                    key={question.id}
                    question={question}
                    busy={task.busy}
                    onSubmit={(selected) => void answer(selected)}
                    label="Record my answer"
                  />
                  <Citations citations={question.citations} compact />
                </>
              ) : (
                <>
                  <p className="prose problem-recap">
                    {question.question_text}
                  </p>
                  {results[0] && <AttemptResult attempt={results[0]} />}
                  <form onSubmit={debug}>
                    <ReasoningEditor
                      text={text}
                      steps={steps}
                      onText={setText}
                      onSteps={setSteps}
                      disabled={task.busy}
                    />
                    <div className="form-footer">
                      <small className="muted">
                        Typed reasoning only. No image interpretation.
                      </small>
                      <Button
                        type="submit"
                        busy={task.busy}
                        disabled={!validReasoning(text, steps)}
                      >
                        <ScanLine size={17} /> Debug my reasoning
                      </Button>
                    </div>
                  </form>
                  {task.busy && (
                    <Loading label="Inspecting your reasoning against source evidence…" />
                  )}
                </>
              )}
            </section>
          )}
          {diagnosis && (
            <>
              <ReasoningDebugger diagnosis={diagnosis} />
              {results.length > 0 && (
                <section
                  className="response-history"
                  aria-label="Assessment feedback"
                >
                  {results.length > 1 && (
                    <details>
                      <summary>
                        Earlier verified assessment responses (
                        {results.length - 1})
                      </summary>
                      {results.slice(0, -1).map((result) => (
                        <AttemptResult
                          key={result.attempt_id}
                          attempt={result}
                        />
                      ))}
                    </details>
                  )}
                  <p className="eyebrow">Latest verified assessment response</p>
                  <AttemptResult attempt={results[results.length - 1]} />
                </section>
              )}
              {diagnosis.probe && (
                <section className="card diagnostic-probe">
                  <p className="eyebrow">Diagnostic Probe</p>
                  <h2>A small question to test that possibility.</h2>
                  {diagnosis.status === "hypothesis" && !probeResult ? (
                    <>
                      <QuestionForm
                        question={diagnosis.probe}
                        busy={task.busy}
                        onSubmit={(selected) => void submitProbe(selected)}
                        label="Test the hypothesis"
                      />
                      <Citations
                        citations={diagnosis.probe.citations}
                        compact
                      />
                    </>
                  ) : (
                    <p className="diagnostic-outcome">
                      <Check size={18} />
                      {
                        diagnosisLabels[
                          probeResult?.diagnostic_outcome ?? diagnosis.status
                        ]
                      }
                    </p>
                  )}
                  {probeResult && diagnosis.status === "hypothesis" && (
                    <Button
                      className="secondary small"
                      busy={task.busy}
                      onClick={() => {
                        void task
                          .run((signal) =>
                            api.diagnosis(
                              course!.id,
                              learner,
                              diagnosis.id,
                              signal,
                            ),
                          )
                          .then((value) => {
                            if (value) setDiagnosis(value);
                          });
                      }}
                    >
                      Refresh diagnostic outcome
                    </Button>
                  )}
                  {probeResult && (
                    <div className="probe-result">
                      <p>
                        Your response:{" "}
                        <strong>
                          {
                            diagnosis.probe.options[
                              probeResult.selected_option_index
                            ]
                          }
                        </strong>
                      </p>
                      <p>
                        {probeResult.is_correct === null
                          ? "This response could not be safely graded."
                          : probeResult.is_correct
                            ? "Correct response."
                            : "Incorrect response."}
                      </p>
                      {probeResult.correct_option_index !== null && (
                        <p>
                          Verified answer:{" "}
                          <strong>
                            {
                              diagnosis.probe.options[
                                probeResult.correct_option_index
                              ]
                            }
                          </strong>
                        </p>
                      )}
                      {probeResult.explanation && (
                        <p className="prose">{probeResult.explanation}</p>
                      )}
                      <Citations citations={probeResult.citations} compact />
                    </div>
                  )}
                  <p className="quiet-note">
                    This is evidence about one reasoning event, not a permanent
                    diagnosis.
                  </p>
                </section>
              )}
              {!session && diagnosis.status !== "hypothesis" && (
                <section className="card next-learning">
                  <p className="eyebrow">
                    A next step that follows the evidence
                  </p>
                  <h2>
                    {diagnosis.status === "confirmed"
                      ? "Let’s work on this together."
                      : diagnosisLabels[diagnosis.status]}
                  </h2>
                  <p>
                    {diagnosis.status === "confirmed"
                      ? "The probe supports this possibility. ConceptLens can now choose a source-grounded repair approach."
                      : "The diagnosis is uncertain. Continue with concept-level teaching and fresh verification, or add more reasoning."}
                  </p>
                  <div className="button-row">
                    {diagnosis.status !== "confirmed" && (
                      <Button className="secondary" onClick={revise}>
                        Revisit my reasoning
                      </Button>
                    )}
                    <Button onClick={() => void start()} busy={task.busy}>
                      {diagnosis.status === "confirmed"
                        ? "Start guided repair"
                        : "See recommended next step"}
                      <ArrowRight size={16} />
                    </Button>
                  </div>
                </section>
              )}
              {session && (
                <Teaching
                  session={session}
                  diagnosis={diagnosis}
                  busy={task.busy}
                  onFeedback={sendFeedback}
                  onChoice={sendChoice}
                  onAttempt={sendAttempt}
                  onRestart={restart}
                  onRevise={revise}
                />
              )}
            </>
          )}
          {session && (
            <div className="trace-trigger">
              <button
                className="trace-button"
                aria-expanded={traceOpen}
                aria-controls="learning-trace"
                onClick={() => setTraceOpen((value) => !value)}
              >
                <Fingerprint size={21} />
                <span>
                  Why did ConceptLens do this?
                  <small>Inspect the evidence behind every step.</small>
                </span>
                <span aria-hidden="true">{traceOpen ? "−" : "+"}</span>
              </button>
              {traceOpen && (
                <div id="learning-trace">
                  <TracePanel
                    key={`${session.id}:${session.updated_at}`}
                    sessionId={session.id}
                    onClose={() => setTraceOpen(false)}
                  />
                </div>
              )}
            </div>
          )}
        </div>
        <aside className="learn-context">
          <section className="card">
            <p className="eyebrow">The idea behind Learn</p>
            <h2>A better next step, not just another answer.</h2>
            <div className="learning-lens" aria-hidden="true">
              <span />
              <ScanLine size={34} />
            </div>
            <p>
              We look at your reasoning, test a possible gap, and adapt the
              teaching to what the evidence shows.
            </p>
            <div className="rule" />
            <p className="eyebrow">Current focus</p>
            <p>
              {session
                ? actionLabels[session.current_action]
                : diagnosis
                  ? diagnosisLabels[diagnosis.status]
                  : attemptId
                    ? "Explain your reasoning"
                    : "Start with a verified problem"}
            </p>
            {diagnosis?.prerequisites.length ? (
              <div className="real-prerequisites">
                <GitBranch size={18} />
                <strong>Connected foundations</strong>
                {diagnosis.prerequisites.map((item) => (
                  <p key={item.edge_id}>{item.name}</p>
                ))}
              </div>
            ) : null}
            <p className="quiet-note">
              Understanding is checked with a fresh Transfer Check. Feedback
              alone never increases mastery.
            </p>
          </section>
          {question && (
            <Button
              className="secondary full"
              disabled={task.busy}
              onClick={restart}
            >
              Start a new problem
            </Button>
          )}
          <Link className="context-link" to="/dashboard">
            See your learning evidence <ArrowRight size={15} />
          </Link>
        </aside>
      </div>
    </>
  );
}
