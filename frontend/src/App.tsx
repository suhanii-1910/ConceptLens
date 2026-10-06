import {
  Component,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  BarChart3,
  BookOpen,
  ChevronDown,
  Compass,
  FlaskConical,
  FolderOpen,
  MessageSquareText,
  RotateCcw,
  ScanLine,
} from "lucide-react";
import {
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { api } from "./api/client";
import type { Course } from "./api/types";
import { useQuery } from "./hooks";
import {
  LearningProvider,
  learnerUUID,
  readStorage,
  saveStorage,
} from "./state";
import { Button, ErrorNotice, Loading } from "./components/ui";
import { Workspace } from "./views/Workspace";
import { Ask } from "./views/Ask";
import { Learn } from "./views/Learn";
import { Practice } from "./views/Practice";
import { Dashboard } from "./views/Dashboard";

export const destinations = [
  { path: "/workspace", label: "Workspace", icon: FolderOpen },
  { path: "/ask", label: "Ask", icon: MessageSquareText },
  { path: "/learn", label: "Learn", icon: ScanLine },
  { path: "/practice", label: "Practice", icon: FlaskConical },
  { path: "/dashboard", label: "Dashboard", icon: BarChart3 },
];
export default function App() {
  const courses = useQuery(
    useCallback((signal: AbortSignal) => api.courses(signal), []),
  );
  const [courseId, setCourseId] = useState(
    () => readStorage("conceptlens:course") || "",
  );
  const [learner, setLearner] = useState(learnerUUID);
  const [resetOpen, setResetOpen] = useState(false);
  const location = useLocation();
  const course =
    courses.data?.find((item) => item.id === courseId) ?? courses.data?.[0];
  const mode =
    destinations.find((item) => item.path === location.pathname)?.label ??
    "Workspace";
  useEffect(() => {
    if (course) saveStorage("conceptlens:course", course.id);
  }, [course]);
  useEffect(() => {
    document.title = `${mode} · ConceptLens`;
    document.getElementById("main-content")?.focus();
    window.scrollTo(0, 0);
  }, [location.pathname, mode]);
  const reloadCourses = courses.reload;
  const coursesChanged = useCallback(
    (next: Course) => {
      setCourseId(next.id);
      reloadCourses();
    },
    [reloadCourses],
  );
  const reset = () => {
    const id = crypto.randomUUID();
    saveStorage("conceptlens:learner", id);
    setLearner(id);
    setResetOpen(false);
  };
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <NavLink
          to="/workspace"
          className="brand"
          aria-label="ConceptLens workspace"
        >
          <img src="/lens.svg" alt="" width="36" height="36" />
          <span>
            Concept<span className="brand-light">Lens</span>
          </span>
        </NavLink>
        <p className="brand-tagline">
          Learn anything.
          <br />
          Debug your understanding.
        </p>
        <p className="nav-label">Your learning space</p>
        <nav aria-label="Principal navigation">
          {destinations.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
            >
              <Icon size={19} />
              <span>{label}</span>
              {label === "Learn" && (
                <span className="nav-dot" aria-hidden="true" />
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-principle">
            <Compass size={21} />
            <p>
              Not just the answer.
              <br />
              <strong>The next learning action.</strong>
            </p>
          </div>
          <details className="learner-settings">
            <summary>
              <span className="learner-avatar">L</span>
              <span>
                Your learning profile<small>Local learner · no sign-in</small>
              </span>
              <ChevronDown size={14} />
            </summary>
            <p>
              A stable browser identifier connects your learning evidence. This
              is not an authenticated account.
            </p>
            <Button
              className="secondary small"
              onClick={() => setResetOpen(true)}
            >
              <RotateCcw size={14} /> Reset demo learner
            </Button>
          </details>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <BookOpen size={16} />
            <span>Your workspace</span>
            <span className="slash">/</span>
            <strong>{mode}</strong>
          </div>
          <div className="course-selector">
            <label htmlFor="active-course">Active course</label>
            <select
              id="active-course"
              value={course?.id ?? ""}
              onChange={(event) => setCourseId(event.target.value)}
              disabled={courses.loading || !courses.data?.length}
            >
              {!courses.data?.length && (
                <option value="">
                  {courses.loading ? "Loading courses…" : "No course selected"}
                </option>
              )}
              {courses.data?.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
        </header>
        <main id="main-content" tabIndex={-1}>
          {courses.loading ? (
            <Loading label="Opening your learning workspace…" />
          ) : courses.error ? (
            <ErrorNotice error={courses.error} retry={courses.reload} />
          ) : (
            <LearningProvider
              key={`${course?.id ?? "none"}:${learner}`}
              course={course}
              learner={learner}
              coursesChanged={coursesChanged}
            >
              <Routes>
                <Route path="/workspace" element={<Workspace />} />
                <Route path="/ask" element={<Ask />} />
                <Route path="/learn" element={<Learn />} />
                <Route path="/practice" element={<Practice />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route
                  path="*"
                  element={<Navigate to="/workspace" replace />}
                />
              </Routes>
            </LearningProvider>
          )}
        </main>
        <footer className="app-footer">
          <span>ConceptLens</span>
          <span>Grounded in your material. Guided by evidence.</span>
        </footer>
      </div>
      {resetOpen && (
        <ResetDialog onClose={() => setResetOpen(false)} onReset={reset} />
      )}
    </div>
  );
}
function ResetDialog({
  onClose,
  onReset,
}: {
  onClose: () => void;
  onReset: () => void;
}) {
  const dialog = useCallback((element: HTMLDialogElement | null) => {
    element?.showModal();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="reset-dialog"
      onCancel={onClose}
      aria-labelledby="reset-title"
    >
      <h2 id="reset-title">Start with a new learner?</h2>
      <p>
        This browser will use a new learner identifier. Existing backend
        evidence is preserved, but will no longer appear for the new learner.
      </p>
      <div className="button-row">
        <Button className="secondary" onClick={onClose} autoFocus>
          Keep this learner
        </Button>
        <Button onClick={onReset}>Reset learner</Button>
      </div>
    </dialog>
  );
}
export class AppBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className="fatal">
        <h1>Your workspace needs a refresh.</h1>
        <p>
          We couldn’t display this view safely. Your saved backend records are
          unchanged.
        </p>
        <Button onClick={() => window.location.reload()}>
          Reload workspace
        </Button>
      </main>
    ) : (
      this.props.children
    );
  }
}
