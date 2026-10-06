import { ArrowRight, Plus, ScanLine, Trash2 } from "lucide-react";
import type { Diagnosis } from "../api/types";
import { Button, Citations, diagnosisLabels } from "./ui";

export function ReasoningEditor({
  text,
  steps,
  onText,
  onSteps,
  disabled,
}: {
  text: string;
  steps: string[];
  onText: (text: string) => void;
  onSteps: (steps: string[]) => void;
  disabled: boolean;
}) {
  const count = [...text, ...steps.join("")].length;
  return (
    <fieldset className="reasoning-editor" disabled={disabled}>
      <legend>Your reasoning, in your words</legend>
      <p className="muted">
        Show the path you took—not just the answer. Add steps, a short
        explanation, or both.
      </p>
      <label htmlFor="reasoning-text">
        Explain your thinking{" "}
        <span className="muted">(optional when adding steps)</span>
      </label>
      <textarea
        id="reasoning-text"
        value={text}
        onChange={(event) =>
          onText([...event.target.value].slice(0, 8000).join(""))
        }
        rows={3}
        placeholder="I started by comparing…"
      />
      <div className="editor-steps">
        {steps.map((step, index) => (
          <div className="editor-step" key={index}>
            <span className="step-number">{index + 1}</span>
            <label className="sr-only" htmlFor={`reasoning-${index}`}>
              Reasoning step {index + 1}
            </label>
            <textarea
              id={`reasoning-${index}`}
              value={step}
              onChange={(event) =>
                onSteps(
                  steps.map((value, i) =>
                    i === index
                      ? [...event.target.value].slice(0, 1000).join("")
                      : value,
                  ),
                )
              }
              rows={2}
              placeholder="Describe this step…"
            />
            <button
              type="button"
              className="icon-button"
              aria-label={`Remove step ${index + 1}`}
              onClick={() => onSteps(steps.filter((_, i) => i !== index))}
            >
              <Trash2 size={17} />
            </button>
          </div>
        ))}
      </div>
      <div className="form-footer">
        <Button
          type="button"
          className="secondary small"
          onClick={() => onSteps([...steps, ""])}
          disabled={steps.length >= 20}
        >
          <Plus size={16} /> Add a step
        </Button>
        <small className={count > 12000 ? "text-error" : "muted"}>
          {count.toLocaleString()} / 12,000 characters
        </small>
      </div>
    </fieldset>
  );
}
function Excerpt({ text, excerpt }: { text: string; excerpt: string | null }) {
  const start = excerpt ? text.indexOf(excerpt) : -1;
  if (!excerpt || start < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, start)}
      <mark>{excerpt}</mark>
      {text.slice(start + excerpt.length)}
    </>
  );
}
export function ReasoningDebugger({ diagnosis }: { diagnosis: Diagnosis }) {
  const fault = !!diagnosis.hypothesis_text;
  return (
    <section className="card reasoning-debugger">
      <div className="section-heading">
        <div className="icon-tile">
          <ScanLine size={20} />
        </div>
        <div>
          <p className="eyebrow">Reasoning Debugger</p>
          <h2>Follow the thought. Find the turning point.</h2>
        </div>
      </div>
      {diagnosis.reasoning_steps.length > 0 && (
        <ol className="reasoning-sequence">
          {diagnosis.reasoning_steps.map((step, index) => {
            const isBreak =
              index === diagnosis.first_break_step_index &&
              !!diagnosis.first_break_excerpt &&
              step.includes(diagnosis.first_break_excerpt);
            return (
              <li className={isBreak ? "possible-break" : ""} key={index}>
                <span className="step-number">{index + 1}</span>
                <div>
                  <p className="prose">
                    <Excerpt
                      text={step}
                      excerpt={isBreak ? diagnosis.first_break_excerpt : null}
                    />
                  </p>
                  {isBreak && (
                    <small>
                      <ArrowRight size={13} /> Possible first break
                    </small>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {diagnosis.reasoning_text && (
        <blockquote className="prose">
          <Excerpt
            text={diagnosis.reasoning_text}
            excerpt={
              diagnosis.first_break_step_index === null
                ? diagnosis.first_break_excerpt
                : null
            }
          />
        </blockquote>
      )}
      <div className="diagnosis-columns">
        <div>
          <p className="eyebrow">Observed</p>
          <p>
            {diagnosis.observed_reasoning ||
              "No supported observation was recorded."}
          </p>
        </div>
        <div className={fault ? "hypothesis" : "no-fault"}>
          <p className="eyebrow">
            {fault ? "Possible hypothesis" : "What the evidence says"}
          </p>
          <p>
            {diagnosis.hypothesis_text || diagnosisLabels[diagnosis.status]}
          </p>
          <small>
            {fault
              ? "A possibility about this reasoning event, not a label about you."
              : "You can add more detail or try another problem. A misconception is never assumed."}
          </small>
        </div>
      </div>
      <Citations citations={diagnosis.citations} compact />
    </section>
  );
}
