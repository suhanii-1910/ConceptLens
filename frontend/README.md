# ConceptLens frontend

React, TypeScript, Vite, React Router, Lucide icons, and plain CSS. Exactly five principal views: Workspace, Ask, Learn, Practice, Dashboard. The app calls the existing FastAPI routes; it contains no production mock learning data.

## Run locally

Use Node 22.12+ (Node 24 was used for acceptance). Start PostgreSQL and the backend using the repository README, then:

```sh
cd frontend
npm ci                 # npm install also works when updating dependencies
npm run dev
```

Frontend: `http://127.0.0.1:5173`. Backend: `http://127.0.0.1:8000`.

The default `VITE_API_BASE_URL=/api` uses Vite's development proxy: `/api/courses` becomes `http://127.0.0.1:8000/courses`. Export `CONCEPTLENS_API_PROXY_TARGET` when a disposable backend uses another port. This is a Vite server setting, not a browser credential. No backend CORS change is needed for this setup. Copy `.env.example` to `.env.local` only if overriding the public API prefix. Vite variables are public build-time settings; never put provider secrets there.

Configure the backend's existing `CONCEPTLENS_LLM_BASE_URL`, `CONCEPTLENS_LLM_MODEL`, and `CONCEPTLENS_LLM_API_KEY` settings for generated learning content. Missing provider configuration is shown as an unavailable-provider state. Upload, process, and index real material before asking questions or generating assessments. Mastery also requires curated backend concept/evidence mappings; the frontend does not create them.

## Checks

```sh
npm test
npm run typecheck
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

Playwright starts Vite and checks desktop (1440 px) and mobile (390 px) layouts. Its isolated API fixtures exercise the full judge journey, answer hiding, retained feedback, source citations, strategy changes, prerequisite choices, Transfer Check, trace proof, and failure states. Fixtures live only in test files and are not imported by the application. Screenshots and failure traces are written to ignored `test-results/` directories. These checks validate frontend behavior; they do not claim live provider verification.

For live acceptance, use the [disposable demo helper](../docs/phase11/demo-guide.md#safe-live-smoke-and-provider-acceptance) from the repository root. It starts an isolated backend and runs both live browser cases:

```sh
CONCEPTLENS_EVAL_ADMIN_URL='postgresql+asyncpg://conceptlens:conceptlens@127.0.0.1:55432/postgres' \
  backend/.venv/bin/python demo-course/prepare.py --browser-smoke
```

If Chrome is already installed, `PLAYWRIGHT_CHANNEL=chrome` can replace downloading Chromium. Internally, the helper opts in using `CONCEPTLENS_LIVE_SMOKE=1` and sets `CONCEPTLENS_EXPECT_UNCONFIGURED=1` for the missing-provider generation check. Do not aim acceptance at the normal development DB. Fixture results are not real-provider acceptance; external text/vision acceptance remains pending configuration.

## Runtime behavior and limits

- An opaque learner UUID is stored in this browser. It is not authentication. “Reset demo learner” creates a new UUID and leaves backend records intact.
- Journey references are scoped by both course and learner. Reload fetches saved public questions, diagnoses, and sessions. Only record IDs are persisted locally. The backend has no assessment-attempt retrieval endpoint, so immediate result details cannot be reconstructed after reload; the saved attempt ID still supports diagnosis.
- A normal assessment response precedes reasoning diagnosis. Typed reasoning accepts up to 8,000 characters, 20 nonblank steps of up to 1,000 characters each, and 12,000 characters combined. Character counting follows backend Unicode code-point semantics.
- Feedback, prerequisite choices, and learning attempts use server transitions. A stale-action 409 fetches the current session and tells the learner that the step changed. Returned grades remain visible as the session advances.
- Practice supports verified multiple-choice, short-answer and numerical questions, with deterministic scheduling proof after grading where applicable. Learn's entry generator defaults to MCQ; recorded typed attempts can enter reasoning from Practice. Image/handwriting learner-reasoning interpretation is not implemented.
- Source citations open actual PDF pages, approximate PPTX slide previews and video timestamps. Workspace exposes extracted visual evidence and optional independently verified image interpretation; re-index explicitly after acceptance. Dashboard includes course concept/prerequisite evidence, a persistent short diagnostic and a cumulative assessment report.
- Unseen concepts show **Untested** without displaying the BKT prior as measured performance. Trace proof indicators reflect actual backend booleans. The trace starts closed.
- Processing is initiated explicitly and uses actual backend status; refresh the source list to inspect work started elsewhere. No progress percentage is simulated.
- Generated content is rendered as React text and structured elements, never as arbitrary HTML. Native radio groups, labelled fields, visible keyboard focus, status announcements, and reduced-motion styles support accessibility.

## Production

`npm run build` produces `dist/`. Serve it with SPA fallback to `index.html` for the five routes, and reverse-proxy `/api` to FastAPI. The Vite proxy is development-only. An absolute `VITE_API_BASE_URL` needs appropriate CORS at that API origin. Provider credentials stay on the backend. Fonts use Google Fonts with local system fallbacks; the app remains usable if font loading is blocked.

Phase 11 preserves the five-view design and existing backend contracts. It adds a configurable development proxy target for isolated acceptance, without authentication, schema migrations or cloud deployment.
