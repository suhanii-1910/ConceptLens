import { useState } from "react";
import {
  ArrowRight,
  CornerDownRight,
  FileCheck2,
  MessageCircleQuestion,
  Quote,
} from "lucide-react";
import { api } from "../api/client";
import type { AskMode, AskResponse } from "../api/types";
import { useLearning } from "../state";
import { useTask } from "../hooks";
import {
  Button,
  Citations,
  ErrorNotice,
  EvidenceBoundary,
  Loading,
  NoCourse,
  PageHeading,
} from "../components/ui";

export const askModes: { value: AskMode; label: string; hint: string }[] = [
  { value: "just_answer", label: "Just Answer", hint: "Get to the point." },
  {
    value: "explain",
    label: "Explain It",
    hint: "Build the idea step by step.",
  },
  {
    value: "guide",
    label: "Guide Me With Questions",
    hint: "Work toward the answer yourself.",
  },
];
export function Ask() {
  const { course } = useLearning();
  const [mode, setMode] = useState<AskMode>("explain");
  const [question, setQuestion] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [response, setResponse] = useState<AskResponse>();
  const task = useTask();
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!course || !question.trim()) return;
    setSubmitted(question.trim());
    setResponse(undefined);
    const result = await task.run((signal) =>
      api.ask(course.id, question.trim(), mode, signal),
    );
    if (result) setResponse(result);
  };
  return (
    <>
      <PageHeading
        eyebrow="Ask / Grounded in your course"
        title="An answer you can trace."
        description="Your questions. Your material. A clear line between what’s supported and what isn’t."
      />
      {!course ? (
        <NoCourse />
      ) : (
        <div className="ask-layout">
          <div className="ask-main">
            <section className="card ask-composer">
              <form onSubmit={submit}>
                <div
                  className="mode-selector"
                  role="group"
                  aria-label="Answer mode"
                >
                  {askModes.map((item) => (
                    <button
                      key={item.value}
                      type="button"
                      aria-pressed={mode === item.value}
                      className={mode === item.value ? "active" : ""}
                      onClick={() => setMode(item.value)}
                      disabled={task.busy}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <label htmlFor="ask-question">
                  What would you like to understand?
                </label>
                <textarea
                  id="ask-question"
                  rows={4}
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  required
                  maxLength={4000}
                  placeholder="Ask about an idea in your course material…"
                  disabled={task.busy}
                />
                <div className="form-footer">
                  <small>
                    {askModes.find((item) => item.value === mode)?.hint}
                  </small>
                  <Button
                    type="submit"
                    busy={task.busy}
                    disabled={!question.trim()}
                  >
                    Ask ConceptLens <ArrowRight size={17} />
                  </Button>
                </div>
              </form>
            </section>
            <ErrorNotice error={task.error} />
            {task.busy && (
              <Loading label="Finding relevant evidence in your material…" />
            )}
            {response?.status === "declined" && (
              <EvidenceBoundary message={response.decline_message} />
            )}
            {response?.status === "answered" && (
              <section className="card answer-card">
                <div className="answer-heading">
                  <span className="eyebrow">Your question</span>
                  <h2>{submitted}</h2>
                </div>
                <div className="answer-label">
                  <Quote size={19} />
                  <span>From your course material</span>
                </div>
                {response.blocks.map((block, index) => (
                  <article className="answer-block" key={index}>
                    <p className="prose">{block.text}</p>
                    <Citations citations={block.citations} compact />
                  </article>
                ))}
                {response.next_question && (
                  <div className="next-question">
                    <CornerDownRight size={20} />
                    <div>
                      <p className="eyebrow">Think it through</p>
                      <p>{response.next_question}</p>
                      <Button
                        className="secondary small"
                        onClick={() => {
                          setQuestion(response.next_question!);
                          document.getElementById("ask-question")?.focus();
                        }}
                      >
                        Explore this question
                      </Button>
                    </div>
                  </div>
                )}
              </section>
            )}
            {!response && !task.busy && !task.error && (
              <div className="ask-empty">
                <div className="orbital-mark" aria-hidden="true">
                  <span />
                  <span />
                  <FileCheck2 size={26} />
                </div>
                <h2>Clarity, with the source attached.</h2>
                <p>
                  Every answer block carries its own evidence.
                  <br />
                  If your material can’t support it, we’ll say so.
                </p>
              </div>
            )}
          </div>
          <aside className="card ask-context">
            <p className="eyebrow">Evidence first</p>
            <h2>Know where the answer comes from.</h2>
            <p>
              Source cards sit beside the ideas they support. Expand one to
              inspect its recorded page, slide, or video location.
            </p>
            <div className="rule" />
            <MessageCircleQuestion size={25} />
            <h3>Choose how you learn.</h3>
            <p>
              Get a direct answer, unpack the explanation, or reason your way
              there with questions.
            </p>
            <p className="quiet-note">
              Each question is independent. This is a grounded workspace, not a
              stored chat history.
            </p>
          </aside>
        </div>
      )}
    </>
  );
}
