import { useCallback } from "react";
import { Check, Circle, Fingerprint, X } from "lucide-react";
import { api } from "../api/client";
import type { LearningTrace, Proof } from "../api/types";
import { useQuery } from "../hooks";
import { useLearning } from "../state";
import { Button, Citations, diagnosisLabels, ErrorNotice, Loading } from "./ui";
import { actionLabels } from "./Teaching";

const proofLabels: Record<keyof Proof, string> = {
  source_location_verified: "Source location verified",
  diagnostic_question_verified: "Diagnostic question verified",
  citation_valid: "Citation valid",
  teaching_content_verified: "Teaching content verified",
  transfer_check_verified: "Transfer Check verified",
  learner_update_based_on_verified_evidence:
    "Learner update based on verified evidence",
};
export function TraceContent({ trace }: { trace: LearningTrace }) {
  return (
    <>
      <ol className="trace-timeline">
        <li>
          <h3>Observed</h3>
          <p>
            {trace.observed.observed_reasoning ||
              "No supported observation recorded."}
          </p>
          {trace.observed.first_break_excerpt && (
            <blockquote>{trace.observed.first_break_excerpt}</blockquote>
          )}
        </li>
        <li>
          <h3>Hypothesis</h3>
          <p>{trace.hypothesis || "No hypothesis was proposed."}</p>
        </li>
        <li>
          <h3>Diagnostic evidence</h3>
          {trace.diagnostic_evidence.length ? (
            trace.diagnostic_evidence.map((item) => (
              <p key={item.attempt_id}>
                Response {String.fromCharCode(65 + item.selected_option_index)}{" "}
                ·{" "}
                {item.is_correct === null
                  ? "Not graded"
                  : item.is_correct
                    ? "Correct"
                    : "Incorrect"}
                {item.applied_outcome && (
                  <> · {diagnosisLabels[item.applied_outcome]}</>
                )}
              </p>
            ))
          ) : (
            <p>No diagnostic responses recorded.</p>
          )}
        </li>
        <li>
          <h3>Interpretation</h3>
          <p>{diagnosisLabels[trace.interpretation]}</p>
        </li>
        <li>
          <h3>Teaching actions</h3>
          {trace.teaching_actions.length ? (
            trace.teaching_actions.map((item) => (
              <div className="trace-action" key={item.id}>
                <strong>
                  {item.sequence_index}. {actionLabels[item.strategy]}
                </strong>
                {item.feedback && (
                  <p>
                    Learner feedback:{" "}
                    {item.feedback === "understood"
                      ? "I understand"
                      : "Still confused"}
                  </p>
                )}
                {item.learner_choice && (
                  <p>
                    Learner choice:{" "}
                    {item.learner_choice === "sixty_second_recap"
                      ? "60-second recap"
                      : item.learner_choice === "practice_prerequisite"
                        ? "Practice prerequisite"
                        : "Continue anyway"}
                  </p>
                )}
                <Citations citations={item.citations} compact />
              </div>
            ))
          ) : (
            <p>No teaching action recorded.</p>
          )}
        </li>
        <li>
          <h3>Transfer verification</h3>
          <p>
            {trace.transfer_result
              ? trace.transfer_result.status === "pending"
                ? "Transfer Check awaits a response."
                : trace.transfer_result.status === "passed"
                  ? "The resolving Transfer Check response passed."
                  : "The resolving Transfer Check response did not pass."
              : "No Transfer Check recorded yet."}
          </p>
        </li>
        <li>
          <h3>Learner-state update</h3>
          {trace.learner_updates.length ? (
            trace.learner_updates.map((update) => (
              <p key={update.observation_id}>
                Observation {update.observation_index}:{" "}
                {Math.round(update.prior_mastery * 100)}% →{" "}
                {Math.round(update.updated_mastery * 100)}% estimated mastery.
              </p>
            ))
          ) : (
            <p>No verified mastery update recorded in this session.</p>
          )}
        </li>
      </ol>
      <section className="proof-panel">
        <p className="eyebrow">The proof, not a promise</p>
        <h3>What has been verified?</h3>
        <ul>
          {(Object.keys(proofLabels) as (keyof Proof)[]).map((key) => (
            <li
              className={trace.proof[key] === true ? "verified" : "unverified"}
              key={key}
            >
              {trace.proof[key] === true ? (
                <Check size={16} />
              ) : (
                <Circle size={16} />
              )}
              <span>
                {proofLabels[key]}
                <small>
                  {trace.proof[key] === true ? "Verified" : "Not verified"}
                </small>
              </span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
export function TracePanel({
  sessionId,
  onClose,
}: {
  sessionId: string;
  onClose: () => void;
}) {
  const { course, learner } = useLearning();
  const query = useQuery(
    useCallback(
      (signal: AbortSignal) =>
        api.trace(course!.id, learner, sessionId, signal),
      [course, learner, sessionId],
    ),
  );
  return (
    <section
      className="trace-panel card"
      aria-label="Learning Trace"
      tabIndex={-1}
    >
      <div className="section-heading">
        <Fingerprint size={25} />
        <div>
          <p className="eyebrow">Learning Trace</p>
          <h2>Nothing important is a black box.</h2>
        </div>
        <Button
          className="icon-button secondary"
          aria-label="Close Learning Trace"
          onClick={onClose}
        >
          <X size={18} />
        </Button>
      </div>
      <p className="muted">
        The recorded evidence behind this learning session. No generated
        retelling.
      </p>
      {query.loading && <Loading label="Retrieving your recorded evidence…" />}
      <ErrorNotice error={query.error} retry={query.reload} />
      {query.data && <TraceContent trace={query.data} />}
    </section>
  );
}
