import { useState } from "react";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { api } from "../api/client";
import type { Difficulty, Generation, Question } from "../api/types";
import { useTask } from "../hooks";
import { useLearning } from "../state";
import { Button, ErrorNotice, EvidenceBoundary, Loading } from "./ui";

export function QuestionGenerator({
  onQuestion,
  purpose = "practice",
}: {
  onQuestion: (question: Question) => void;
  purpose?: "practice" | "reasoning";
}) {
  const { course } = useLearning();
  const [questionType, setQuestionType] = useState<Question["question_type"]>("multiple_choice");
  const [focus, setFocus] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [generation, setGeneration] = useState<Generation>();
  const task = useTask();
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!course || !focus.trim()) return;
    setGeneration(undefined);
    const result = await task.run((signal) =>
      api.generate(course.id, focus.trim(), difficulty, signal, questionType),
    );
    if (result) {
      setGeneration(result);
      if (result.status === "generated" && result.questions[0])
        onQuestion(result.questions[0]);
    }
  };
  return (
    <section className="card generator">
      <p className="eyebrow">Start with your material</p>
      <h2>
        {purpose === "reasoning"
          ? "A real problem. Your line of thought."
          : "Give your understanding a little exercise."}
      </h2>
      <p className="muted">
        Choose a focus from your course. ConceptLens will create and
        independently verify one fresh problem.
      </p>
      <form onSubmit={submit}>
        {purpose === "practice" && <label>Question type<select value={questionType} disabled={task.busy} onChange={event => setQuestionType(event.target.value as Question["question_type"])}><option value="multiple_choice">Multiple choice</option><option value="short_answer">Short answer</option><option value="numerical">Numerical</option></select></label>}
        <label htmlFor="question-focus">What would you like to work on?</label>
        <input
          id="question-focus"
          value={focus}
          onChange={(event) => setFocus(event.target.value)}
          maxLength={2000}
          placeholder="A topic or idea from your material"
          required
          disabled={task.busy}
        />
        <div className="form-footer">
          <div className="field-inline">
            <label htmlFor="difficulty">Difficulty</label>
            <select
              id="difficulty"
              value={difficulty}
              onChange={(event) =>
                setDifficulty(event.target.value as Difficulty)
              }
              disabled={task.busy}
            >
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </div>
          <Button type="submit" busy={task.busy} disabled={!focus.trim()}>
            Find me a problem <ArrowRight size={16} />
          </Button>
        </div>
      </form>
      <ErrorNotice error={task.error} />
      {task.busy && (
        <Loading label="Finding source evidence and verifying a fresh question…" />
      )}
      {generation && generation.status !== "generated" && (
        <EvidenceBoundary
          message={
            generation.decline_message ||
            "No question passed independent verification. Try a different focus or review your course sources."
          }
        />
      )}
      <p className="quiet-note">
        <ShieldCheck size={16} /> Only verified questions reach your workspace.
      </p>
    </section>
  );
}
