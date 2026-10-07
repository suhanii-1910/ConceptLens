import { SourceViewer } from "./SourceViewer";
import { SchedulingResult } from "./TypedAssessment";
import {
  ArrowRight,
  BookOpen,
  Check,
  Circle,
  FileText,
  LoaderCircle,
  ShieldCheck,
  TriangleAlert,
  Video,
} from "lucide-react";
import { useId, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import type {
  Attempt,
  Citation,
  DiagnosisStatus,
  MasteryStatus,
  Question,
} from "../api/types";

export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="lede">{description}</p>
      </div>
      {action}
    </header>
  );
}
export function Button({
  busy = false,
  children,
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  return (
    <button
      {...props}
      className={`button ${className}`}
      disabled={props.disabled || busy}
      aria-busy={busy}
    >
      {busy && <LoaderCircle className="spin" size={17} aria-hidden="true" />}
      {children}
    </button>
  );
}
export function ErrorNotice({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  if (!error) return null;
  return (
    <div className="notice error" role="alert">
      <TriangleAlert size={20} aria-hidden="true" />
      <div>
        <strong>
          {error instanceof ApiError
            ? error.message
            : "We couldn’t finish this action. Please try again."}
        </strong>
        {error instanceof ApiError && error.detail && <p>{error.detail}</p>}
        {error instanceof ApiError && error.validation.length > 0 && (
          <ul>
            {error.validation.map((message, index) => (
              <li key={index}>{message}</li>
            ))}
          </ul>
        )}
        {retry && (
          <Button className="small secondary" onClick={retry}>
            Try again
          </Button>
        )}
      </div>
    </div>
  );
}
export function Loading({
  label = "Loading your workspace…",
}: {
  label?: string;
}) {
  return (
    <div className="loading" role="status">
      <span>
        <LoaderCircle className="spin" size={18} aria-hidden="true" />
        {label}
      </span>
      <div className="skeleton" />
      <div className="skeleton short" />
      <div className="skeleton" />
    </div>
  );
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <BookOpen size={24} />
      </div>
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function NoCourse() {
  return (
    <Empty
      title="Give your learning a home."
      action={
        <Link className="button" to="/workspace">
          Create a course <ArrowRight size={16} />
        </Link>
      }
    >
      Add a course and your material in Workspace. Everything you learn will
      stay connected to it.
    </Empty>
  );
}
export function EvidenceBoundary({ message }: { message?: string | null }) {
  return (
    <div className="evidence-boundary" role="status">
      <ShieldCheck size={30} />
      <p className="eyebrow">An honest boundary</p>
      <h2>Your material doesn’t support an answer yet.</h2>
      <p>
        {message ||
          "ConceptLens couldn’t verify this from your course material."}
      </p>
      <Link to="/workspace" className="text-link">
        Review your sources <ArrowRight size={15} />
      </Link>
    </div>
  );
}
export function Citations({
  citations,
  compact = false,
}: {
  citations: Citation[];
  compact?: boolean;
}) {
  const [opened, setOpened] = useState<Citation>();
  const unique = [
    ...new Map(
      citations.map((citation) => [citation.evidence_unit_id, citation]),
    ).values(),
  ];
  if (!unique.length) return null;
  return (
    <div
      className={`citations ${compact ? "compact" : ""}`}
      aria-label="Source evidence"
    >
      {opened && <SourceViewer citation={opened} onClose={() => setOpened(undefined)} />}
      {unique.map((citation) => (
        <details className="citation" key={citation.evidence_unit_id}>
          <summary>
            {citation.source_type === "video" ? (
              <Video size={17} aria-hidden="true" />
            ) : (
              <FileText size={17} aria-hidden="true" />
            )}
            <span>
              <strong>{citation.source_filename}</strong>
              <small>{citation.locator_label}</small>
            </span>
            <span className="citation-expand" aria-hidden="true">
              +
            </span>
          </summary>
          <div className="citation-detail">
            <span className="eyebrow">Stored source location</span>
            <p>{citation.locator_label}</p>
            <Button onClick={() => setOpened(citation)}>Open exact source</Button>
          </div>
        </details>
      ))}
    </div>
  );
}
export function Choices({
  question,
  selected,
  onChange,
  disabled = false,
}: {
  question: Pick<Question, "question_text" | "options">;
  selected: number | null;
  onChange: (index: number) => void;
  disabled?: boolean;
}) {
  const name = useId();
  return (
    <fieldset className="question" disabled={disabled}>
      <legend>{question.question_text}</legend>
      <div className="options">
        {question.options.map((option, index) => (
          <label
            className={`option ${selected === index ? "selected" : ""}`}
            key={index}
          >
            <input
              type="radio"
              name={name}
              checked={selected === index}
              onChange={() => onChange(index)}
            />
            <span className="option-letter">
              {String.fromCharCode(65 + index)}
            </span>
            <span>{option}</span>
            <Circle className="option-circle" size={16} aria-hidden="true" />
          </label>
        ))}
      </div>
    </fieldset>
  );
}
export function QuestionForm({
  question,
  onSubmit,
  busy,
  label = "Check my answer",
}: {
  question: Pick<Question, "question_text" | "options">;
  onSubmit: (selected: number) => void;
  busy: boolean;
  label?: string;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (selected !== null && !busy) onSubmit(selected);
      }}
    >
      <Choices
        question={question}
        selected={selected}
        onChange={setSelected}
        disabled={busy}
      />
      <div className="form-footer">
        <span className="muted">
          Choose one answer. Feedback follows submission.
        </span>
        <Button type="submit" busy={busy} disabled={selected === null}>
          {label} <ArrowRight size={16} />
        </Button>
      </div>
    </form>
  );
}
export const masteryMessages: Record<MasteryStatus, string> = {
  updated: "Mastery updated from this verified response.",
  skipped_repeated_question:
    "Repeat response recorded. Mastery stays unchanged.",
  skipped_unmapped:
    "Response recorded. No concept mapping is available for a mastery update.",
  skipped_ambiguous:
    "Response recorded. Multiple concepts make a single mastery update ambiguous.",
};
export function AttemptResult({ attempt }: { attempt: Attempt }) {
  return (
    <section
      className={`attempt-result ${attempt.is_correct ? "success" : "review"}`}
      aria-label="Verified response"
    >
      <div className="result-title">
        {attempt.is_correct ? <Check size={21} /> : <TriangleAlert size={21} />}
        <h3>
          {attempt.is_correct === null ? "Unable to grade this response." : attempt.is_correct ? "That’s right." : "A useful point to revisit."}
        </h3>
      </div>
      <p>{attempt.is_correct === null ? "No mastery update was made." : attempt.is_correct ? "Correct response." : "Incorrect response."}</p>
      <p>
        Your response:{" "}
        <strong>
          {attempt.selected_option_index === null ? attempt.submitted_answer : String.fromCharCode(65 + attempt.selected_option_index)}
        </strong>{" "}
        · Verified answer: <strong>{attempt.correct_option_text}</strong>
      </p>
      <p className="prose">{attempt.explanation}</p>
      {attempt.grading?.solution_proof && <SchedulingResult proof={attempt.grading.solution_proof} />}
      <Citations citations={attempt.citations} compact />
      {attempt.mastery_update_status && (
        <p className="mastery-note">
          <ShieldCheck size={16} />
          {masteryMessages[attempt.mastery_update_status]}
        </p>
      )}
      {attempt.mastery_update && (
        <p className="muted">
          {attempt.mastery_update.concept_name} ·{" "}
          {Math.round(attempt.mastery_update.updated_mastery * 100)}% estimated
          mastery · {attempt.mastery_update.observation_count} observations
        </p>
      )}
    </section>
  );
}
export const diagnosisLabels: Record<DiagnosisStatus, string> = {
  hypothesis: "A possibility to test",
  confirmed: "Supported by this probe",
  rejected: "Not supported by this probe",
  inconclusive: "The evidence is inconclusive",
  no_clear_break: "No clear reasoning break found",
  insufficient_reasoning: "A little more reasoning would help",
  insufficient_evidence: "More source evidence is needed",
};
