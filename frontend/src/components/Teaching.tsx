import {
  ArrowRight,
  Check,
  GitBranch,
  Layers,
  Lightbulb,
  RefreshCw,
  Route,
  ScanLine,
} from "lucide-react";
import { Link } from "react-router-dom";
import type {
  Action,
  Choice,
  Diagnosis,
  Feedback,
  LearningSession,
  TeachingPayload,
} from "../api/types";
import { Button, Citations, QuestionForm } from "./ui";

export const actionLabels: Record<Action, string> = {
  source_explanation: "Back to the source",
  visual_explanation: "Let’s look at this visually.",
  prerequisite_probe: "Check the foundation",
  prerequisite_recap: "Your 60-second recap",
  prerequisite_practice: "Practice the prerequisite",
  worked_example: "One example, step by step",
  transfer_check: "Transfer Check",
  prerequisite_choice: "Choose your next step",
  reconsider_diagnosis: "Let’s reconsider the diagnosis",
  complete: "Understanding, put to the test.",
  collect_more_reasoning: "Tell us a little more",
  general_practice: "Keep exploring with Practice",
  diagnostic_probe: "Test the hypothesis first",
};
export const choiceLabels: Record<Choice, string> = {
  sixty_second_recap: "60-second recap",
  practice_prerequisite: "Practice prerequisite",
  continue_anyway: "Continue anyway",
};
const choiceCopy: Record<Choice, string> = {
  sixty_second_recap: "A short, source-backed refresher.",
  practice_prerequisite: "Work through one small problem.",
  continue_anyway: "Return to the original concept.",
};
export function VisualExplanation({
  visual,
}: {
  visual: NonNullable<TeachingPayload["visual"]>;
}) {
  return (
    <figure className="visual-explanation">
      <figcaption>{visual.title}</figcaption>
      <ol>
        {visual.steps.map((step, index) => (
          <li key={index}>
            <div className="visual-node">
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{step.label}</strong>
            </div>
            <p>{step.annotation}</p>
          </li>
        ))}
      </ol>
    </figure>
  );
}
export function Teaching({
  session,
  diagnosis,
  busy,
  onFeedback,
  onChoice,
  onAttempt,
  onRestart,
  onRevise,
}: {
  session: LearningSession;
  diagnosis: Diagnosis;
  busy: boolean;
  onFeedback: (feedback: Feedback) => void;
  onChoice: (choice: Choice) => void;
  onAttempt: (selected: number) => void;
  onRestart: () => void;
  onRevise: () => void;
}) {
  const item = session.current_intervention;
  const terminal =
    session.current_action === "complete" ||
    session.current_action === "reconsider_diagnosis";
  const prerequisite = diagnosis.prerequisites.find(
    (value) =>
      value.prerequisite_concept_id === item?.prerequisite_concept_id &&
      value.edge_id === item?.prerequisite_edge_id,
  );
  if (terminal)
    return (
      <section
        className={`card terminal ${session.current_action === "complete" ? "completed" : ""}`}
      >
        <div className="terminal-icon">
          {session.current_action === "complete" ? (
            <Check size={28} />
          ) : (
            <RefreshCw size={28} />
          )}
        </div>
        <p className="eyebrow">
          {session.current_action === "complete"
            ? "Transfer verified"
            : "A more useful next question"}
        </p>
        <h2>{actionLabels[session.current_action]}</h2>
        <p>
          {session.current_action === "complete"
            ? "Your response to a fresh problem is now part of the evidence. See what it means for your learning."
            : "The evidence suggests we should reconsider the original diagnosis. Your earlier reasoning stays intact."}
        </p>
        <p className="policy-reason">{session.reason}</p>
        {session.current_action === "complete" ? (
          <Link className="button" to="/dashboard">
            See my learning evidence <ArrowRight size={16} />
          </Link>
        ) : (
          <Button onClick={onRestart}>
            Start a new reasoning event <ArrowRight size={16} />
          </Button>
        )}
      </section>
    );
  if (session.current_action === "prerequisite_choice")
    return (
      <section className="card prerequisite-choice">
        <GitBranch size={25} />
        <p className="eyebrow">You choose the route</p>
        <h2>A quick detour could help.</h2>
        <p>
          This response suggests revisiting{" "}
          {prerequisite?.name || "the selected prerequisite"}. It’s your choice
          how to continue.
        </p>
        <div className="choice-grid">
          {session.prerequisite_choices.map((choice) => (
            <button
              className="choice-card"
              key={choice}
              onClick={() => onChoice(choice)}
              disabled={busy}
            >
              <span>
                {choice === "sixty_second_recap" ? (
                  <Lightbulb size={22} />
                ) : choice === "practice_prerequisite" ? (
                  <Layers size={22} />
                ) : (
                  <ArrowRight size={22} />
                )}
              </span>
              <strong>{choiceLabels[choice]}</strong>
              <small>{choiceCopy[choice]}</small>
            </button>
          ))}
        </div>
        <p className="policy-reason">{session.reason}</p>
      </section>
    );
  if (!item || item.completed || session.status !== "active")
    return (
      <section className="card">
        <h2>{actionLabels[session.current_action]}</h2>
        <p>{session.reason}</p>
        {session.current_action === "collect_more_reasoning" && (
          <Button onClick={onRevise}>
            Add more reasoning <ArrowRight size={15} />
          </Button>
        )}
        <Link className="text-link" to="/practice">
          Go to Practice <ArrowRight size={15} />
        </Link>
      </section>
    );
  const transfer = session.current_action === "transfer_check";
  return (
    <section
      className={`card teaching strategy-${item.strategy}`}
      aria-label={actionLabels[session.current_action]}
    >
      <div className="section-heading">
        <div className="icon-tile">
          {transfer ? (
            <ScanLine size={22} />
          ) : item.prerequisite_concept_id ? (
            <GitBranch size={22} />
          ) : (
            <Route size={22} />
          )}
        </div>
        <div>
          <p className="eyebrow">
            {transfer
              ? "Understanding beyond memorization"
              : `Teaching approach ${item.sequence_index}`}
          </p>
          <h2>{actionLabels[session.current_action]}</h2>
        </div>
      </div>
      {diagnosis.status !== "confirmed" && <p className="notice">The diagnosis remains uncertain. This teaching uses observed concept performance; it does not assume a misconception.</p>}
      {transfer && (
        <p className="transfer-intro">
          Let’s see whether the idea transfers to a fresh problem.
        </p>
      )}
      {item.prerequisite_concept_id && (
        <p className="prerequisite-label">
          Checking a prerequisite may help here.
          {prerequisite && <strong> {prerequisite.name}</strong>}
        </p>
      )}
      {item.payload && (
        <>
          <h3>{item.payload.title}</h3>
          <p className="prose">{item.payload.body}</p>
          {item.payload.visual && (
            <VisualExplanation visual={item.payload.visual} />
          )}
          {item.payload.steps.length > 0 && (
            <ol className="worked-steps">
              {item.payload.steps.map((step, index) => (
                <li key={index}>
                  <span>{index + 1}</span>
                  <p className="prose">{step}</p>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
      <Citations citations={item.citations} />
      {item.question ? (
        <QuestionForm
          key={item.id}
          question={item.question}
          onSubmit={onAttempt}
          busy={busy}
          label={
            transfer ? "Verify my understanding" : "Check this prerequisite"
          }
        />
      ) : (
        <div className="feedback">
          <div>
            <strong>Is the idea becoming clearer?</strong>
            <small>
              Your feedback chooses the next step. It doesn’t change mastery.
            </small>
          </div>
          <div className="button-row">
            <Button
              className="secondary"
              busy={busy}
              onClick={() => onFeedback("still_confused")}
            >
              Still confused
            </Button>
            <Button busy={busy} onClick={() => onFeedback("understood")}>
              I understand <ArrowRight size={16} />
            </Button>
          </div>
        </div>
      )}
      <details className="policy-details">
        <summary>Why this approach?</summary>
        <p>{session.reason}</p>
      </details>
    </section>
  );
}
