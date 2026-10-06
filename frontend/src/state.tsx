import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import type { Course } from "./api/types";

export const isUUID = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
export function readStorage(key: string) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
export function saveStorage(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* The current tab still works when browser storage is unavailable. */
  }
}
export function learnerUUID() {
  const saved = readStorage("conceptlens:learner");
  if (isUUID(saved)) return saved;
  const created = crypto.randomUUID();
  saveStorage("conceptlens:learner", created);
  return created;
}
export interface JourneyRefs {
  question_id?: string;
  attempt_id?: string;
  diagnosis_id?: string;
  session_id?: string;
}
function readJourney(key: string): JourneyRefs {
  try {
    const value: unknown = JSON.parse(readStorage(key) || "{}");
    if (typeof value !== "object" || value === null) return {};
    return Object.fromEntries(
      Object.entries(value).filter(
        ([key, id]) =>
          ["question_id", "attempt_id", "diagnosis_id", "session_id"].includes(
            key,
          ) && isUUID(id),
      ),
    );
  } catch {
    return {};
  }
}
interface Context {
  course?: Course;
  learner: string;
  refs: JourneyRefs;
  remember: (refs: JourneyRefs) => void;
  coursesChanged: (course: Course) => void;
}
const LearningContext = createContext<Context | null>(null);
export function LearningProvider({
  course,
  learner,
  coursesChanged,
  children,
}: {
  course?: Course;
  learner: string;
  coursesChanged: (course: Course) => void;
  children: ReactNode;
}) {
  const key = `conceptlens:journey:${learner}:${course?.id ?? "none"}`;
  const [refs, setRefs] = useState(() => readJourney(key));
  const remember = useCallback(
    (next: JourneyRefs) => {
      setRefs(next);
      saveStorage(key, JSON.stringify(next));
    },
    [key],
  );
  return (
    <LearningContext.Provider
      value={{ course, learner, refs, remember, coursesChanged }}
    >
      {children}
    </LearningContext.Provider>
  );
}
export function useLearning() {
  const context = useContext(LearningContext);
  if (!context) throw new Error("Learning context is required");
  return context;
}
