import { useState } from "react";
import { ArrowRight, ScanLine, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Attempt, Question } from "../api/types";
import { useTask } from "../hooks";
import { useLearning } from "../state";
import { QuestionGenerator } from "../components/QuestionGenerator";
import {
  AttemptResult,
  Button,
  Citations,
  ErrorNotice,
  NoCourse,
  PageHeading,
  QuestionForm,
} from "../components/ui";

export function Practice() {
  const { course, learner, remember } = useLearning();
  const [question, setQuestion] = useState<Question>();
  const [attempt, setAttempt] = useState<Attempt>();
  const task = useTask();
  const navigate = useNavigate();
  const submit = async (selected: number) => {
    if (!course || !question) return;
    const result = await task.run((signal) =>
      api.attempt(course.id, learner, question.id, selected, signal),
    );
    if (result) setAttempt(result);
  };
  const learn = () => {
    if (!question || !attempt) return;
    remember({ question_id: question.id, attempt_id: attempt.attempt_id });
    navigate("/learn");
  };
  return (
    <>
      <PageHeading
        eyebrow="Practice / Put ideas to work"
        title="A little practice. Clearer understanding."
        description="Source-grounded questions, verified feedback, and an honest record of what you’ve demonstrated."
      />
      {!course ? (
        <NoCourse />
      ) : (
        <div className="practice-layout">
          <div>
            {!question ? (
              <QuestionGenerator
                onQuestion={(value) => {
                  setQuestion(value);
                  setAttempt(undefined);
                }}
              />
            ) : (
              <section className="card">
                <div className="section-heading">
                  <ShieldCheck size={23} />
                  <div>
                    <p className="eyebrow">Verified practice</p>
                    <h2>One problem. Think it through.</h2>
                  </div>
                </div>
                {!attempt ? (
                  <>
                    <QuestionForm
                      question={question}
                      onSubmit={(selected) => void submit(selected)}
                      busy={task.busy}
                    />
                    <Citations citations={question.citations} />
                  </>
                ) : (
                  <>
                    <p className="problem-recap">{question.question_text}</p>
                    <AttemptResult attempt={attempt} />
                    <div className="button-row">
                      <Button onClick={learn}>
                        <ScanLine size={17} /> Debug my reasoning
                      </Button>
                      <Button
                        className="secondary"
                        onClick={() => {
                          setQuestion(undefined);
                          setAttempt(undefined);
                          task.clearError();
                        }}
                      >
                        Try a new problem <ArrowRight size={16} />
                      </Button>
                    </div>
                  </>
                )}
                <ErrorNotice error={task.error} />
              </section>
            )}
          </div>
          <aside className="card">
            <p className="eyebrow">Practice with a purpose</p>
            <h2>A result is a starting point.</h2>
            <p>
              After answering, take your actual response into Learn to inspect
              the reasoning behind it.
            </p>
            <div className="rule" />
            <h3>Practice & Transfer Check</h3>
            <p>
              Practice explores an idea from your material. A Transfer Check
              follows adaptive teaching to see whether understanding carries
              into a fresh problem.
            </p>
            <p className="quiet-note">
              Multiple-choice questions are available. Short-answer and
              numerical grading are not yet supported.
            </p>
          </aside>
        </div>
      )}
    </>
  );
}
