# ConceptLens

### Learn anything. Debug your understanding.

ConceptLens connects course evidence to the next learning action: ask a grounded question, explain your reasoning, work through targeted teaching, and check understanding on a fresh problem.

**Review draft:** this proposed README describes commit `9fe1751` on `feature/direct-openai-router`. The existing [root README](../../README.md) is unchanged. Final Concept Observatory source, screenshots and real-provider acceptance are pending. [Evidence and test scope](VERIFICATION.md) · [Architecture](ARCHITECTURE.md) · [Demo script](DEMO_VIDEO_SCRIPT.md) · [Submission checklist](SUBMISSION_CHECKLIST.md).

**Video:** `YOUTUBE_URL_PENDING` — insert the actual Public or Unlisted YouTube link after upload.

## Concept Observatory screenshots

**Awaiting genuine captures from the final Observatory build.** No substitute UI, generated mockup or fixture image is presented as the final frontend. Add screenshots of Workspace with a source preview, Ask with citations, Learn with its trace, Practice feedback and Dashboard. Record the capture commit and real/fixture provenance in each caption. See the [handoff requirements](INDEX.md#information-and-assets-still-needed). No broken image links are included in this draft.

## Overview and features

| Module | Implemented purpose |
| --- | --- |
| Workspace | Course creation, PDF/PPTX/MP4 upload, explicit processing/indexing, extracted evidence and source previews |
| Ask | Hybrid evidence retrieval, supported-answer generation, citation inspection and insufficient-evidence refusal |
| Learn | Learner-authored reasoning, tentative diagnosis and probe, adaptive strategies, fresh Transfer Check and Learning Trace |
| Practice | Verified MCQ, short-answer and numerical assessments; short course diagnostic; deterministic scheduling proof where applicable |
| Dashboard | Assessment report, eligible BKT mastery observations, Untested concepts and recorded prerequisite relationships |

Generation-dependent features are implemented and fixture-tested; the available reports do not verify a successful live-provider learning loop. ConceptLens differs from a document chatbot by connecting the student's own reasoning to inspectable learning decisions and new assessment evidence. Reading explanations alone does not increase mastery.

## Technology and architecture

React 19, TypeScript, Vite 7, React Router and Lucide; FastAPI, Pydantic, SQLAlchemy and Alembic; PostgreSQL 16 with pgvector; sentence-transformers; PyMuPDF, pdfplumber, python-pptx, FFmpeg/FFprobe and Apple Silicon MLX Whisper. Exact frontend resolutions are in [package-lock.json](../../frontend/package-lock.json); backend dependency ranges are in [pyproject.toml](../../backend/pyproject.toml).

```mermaid
flowchart TD
    UI[React: Workspace / Ask / Learn / Practice / Dashboard] -->|Vite /api proxy| API[FastAPI]
    API --> Sources[Source processing and previews]
    Sources --> Files[Course originals and derived files]
    Sources --> DB[(PostgreSQL 16 + pgvector)]
    API --> Retrieval[Hybrid retrieval and citation checks]
    Retrieval <--> DB
    API --> Learning[Assessment / diagnosis / adaptive policy / BKT]
    Learning <--> DB
    Retrieval --> Models[Configured text provider]
    Learning --> Models
    Sources --> Vision[Optional image interpretation and verification]
```

The API is a modular monolith. Source processing is explicitly requested; there is no separate ingestion worker to start. Local embeddings index searchable text, including accepted image descriptions; these are not native image embeddings. [Detailed flows and source references](ARCHITECTURE.md).

```text
backend/app/          API, schemas, models and services
backend/alembic/      Database migrations 0001–0007
backend/tests/        Unit, API and opt-in PostgreSQL tests
frontend/src/         Five views, components, API client and state
frontend/e2e/         Playwright fixture and opt-in live tests
evaluation/          Frozen datasets, simulator and historical reports
demo-course/         Authored CPU Scheduling material and isolated demo helper
docs/phase10/         Historical implementation and verification
docs/phase11/         Historical demo guide and verification
docs/submission/      This submission package
storage/uploads/     Local source storage; not submission assets
```

## Prerequisites

- Python **3.12+**. This review used the existing Python 3.12.14 virtual environment; the system `python3` here was 3.9.6 and is unsuitable.
- Node **22.12+** and npm; this review used Node 24.13.0.
- Docker with Compose, or a separately configured PostgreSQL 16 database with the `vector` extension available.
- FFmpeg and FFprobe on `PATH` for MP4 processing. The built-in transcription provider needs Apple Silicon macOS and MLX Whisper. PDF/PPTX workflows do not require video transcription.
- Initial download access or cached local embedding/Whisper model weights. The default embedding path expects 384 dimensions.
- Authorized access to a compatible text provider; image-capable access for visual interpretation. Ingestion and inspection can be used without external generation.

## Install dependencies and configure the environment

From a new clone of the reviewed branch:

```sh
git clone --branch feature/direct-openai-router https://github.com/suhanii-1910/ConceptLens.git
cd ConceptLens
git rev-parse HEAD
```

Compare HEAD to the intended reviewed revision; the branch may advance. This clone command depends on repository access, which was not established in this review. Use the final integrated branch/ref when the team publishes it.

From the repository root:

```sh
# Preserve any existing local environment file.
test -e .env || cp .env.example .env
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e './backend[dev]'
cd frontend
npm ci
cd ..
```

Use an installed Python 3.12+ executable if it has another name. Do not replace an existing virtual environment without first checking it. Edit the untracked root `.env` locally; never publish its contents. The application resolves that file from the repository root regardless of the current directory.

```dotenv
# Repository-provided local development database defaults only.
CONCEPTLENS_DATABASE_URL=postgresql+asyncpg://conceptlens:conceptlens@127.0.0.1:55432/conceptlens
CONCEPTLENS_UPLOAD_DIR=../storage/uploads
CONCEPTLENS_DEBUG=false
CONCEPTLENS_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CONCEPTLENS_EMBEDDING_DIMENSIONS=384
CONCEPTLENS_EMBEDDING_BATCH_SIZE=32
```

Start the backend from `backend/` so the relative upload path resolves correctly. Database credentials above are the defaults in the checked-in Compose file, not production credentials. The 384-dimensional embedding provider/schema must remain compatible; simply changing a dimension setting does not migrate stored vectors.

### Model API and gateway configuration

Choose the mode authorized for your environment; this documentation does not change routing. The current [.env.example](../../.env.example) documents compatible mode but omits the newer direct-mode settings.

**Compatible gateway (default):** add these backend-only settings, substituting real authorized values. Leaving the three required fields empty yields an unavailable-provider state.

```dotenv
CONCEPTLENS_PROVIDER_MODE=compatible
CONCEPTLENS_LLM_BASE_URL=https://YOUR_AUTHORIZED_GATEWAY.example/v1
CONCEPTLENS_LLM_API_KEY=YOUR_BACKEND_ONLY_KEY
CONCEPTLENS_LLM_MODEL=YOUR_AUTHORIZED_TEXT_MODEL
CONCEPTLENS_LLM_TIMEOUT_SECONDS=45
CONCEPTLENS_VISION_MODEL=YOUR_AUTHORIZED_IMAGE_MODEL
```

The text adapter appends `/chat/completions`; supply the base URL, not that full route. The provider must support the adapter's structured JSON contract; image interpretation additionally needs an image-capable endpoint. Separate generator/verifier calls share the configured provider/model in this mode. Health checks, including an OmniRoute health response, do not establish successful completion.

**Direct mode implemented in this branch:**

```dotenv
CONCEPTLENS_PROVIDER_MODE=direct_openai
CONCEPTLENS_OPENAI_API_KEY=YOUR_BACKEND_ONLY_KEY
```

The adapter also supports an exported `OPENAI_API_KEY` fallback. It calls the Responses endpoint directly. Its checked-in tier strings are `gpt-6-luna` for light work, `gpt-6.1-sol` for standard work and `gpt-6-astra` for deep verification. These are **source-code configuration facts, not a statement of public model availability or account entitlement**. Confirm authorized access to the exact identifiers before using this path. Concise `just_answer` Ask uses light; other Ask modes and normal generation use standard; separate assessment, diagnosis, teaching and visual verification use deep where wired. The direct adapter's default timeout is 75 seconds; the compatible-mode timeout setting is not forwarded to it.

Keep keys in backend settings. `VITE_` variables are public build-time values. No private network address, tunnel credential or management token is needed in submission documentation. Do not enable `TESTING=1` or `USE_FAKE_EMBEDDING=1` for a real demo.

## Database and local servers

Start the supplied database from the repository root:

```sh
docker compose up -d db
```

Compose binds PostgreSQL to loopback port **55432**, avoiding the common local 5432 conflict. It uses a persistent volume. For a new intended local database, create the schema:

```sh
cd backend
.venv/bin/alembic upgrade head
.venv/bin/alembic current
```

The inspected migration head is **0007**. Alembic uses the root environment configuration. A separate PostgreSQL installation must permit the migration to create/use pgvector. Do not downgrade or reset a database to prepare a demo; preserve existing records and review pending migrations before applying them to an existing database.

Backend terminal, from the repository root:

```sh
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend terminal, from the repository root:

```sh
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`. API docs: `http://127.0.0.1:8000/docs`. `/health` reports the API process status only, not database or model readiness. Vite forwards `/api` to port 8000, removing the prefix. `CONCEPTLENS_API_PROXY_TARGET` overrides that development proxy target; optional `VITE_API_BASE_URL` overrides the browser API prefix. The production build does not provide Vite's development proxy.

## Try the application

1. In Workspace, create a course and upload supported material. Click **Process**, then **Index course material**. Uploading alone does not make evidence searchable.
2. Open **Inspect source evidence** and the exact page, slide or timestamp. If using a real configured vision provider, **Interpret and verify visual**, then explicitly re-index accepted descriptions.
3. In Ask, ask a question supported by that material and inspect the citations. A refusal is different from a provider error; neither is a generated answer.
4. With curated concept/evidence mappings and an authorized working provider, use Learn and Practice, submit actual responses and reasoning, then inspect Learning Trace and Dashboard. There is no general concept-authoring UI; manual upload alone does not create the demo's curated prerequisites.

For the authored CPU Scheduling course, the existing helper creates a disposable database, actual PDF, real embeddings and curated metadata. It creates no learner attempts or fake assessment history. To use it without external generation, from the repository root:

```sh
CONCEPTLENS_PROVIDER_MODE=compatible \
CONCEPTLENS_OPENAI_API_KEY='' OPENAI_API_KEY='' \
CONCEPTLENS_EVAL_ADMIN_URL='postgresql+asyncpg://conceptlens:conceptlens@127.0.0.1:55432/postgres' \
backend/.venv/bin/python demo-course/prepare.py --serve
```

Then start Vite with `CONCEPTLENS_API_PROXY_TARGET=http://127.0.0.1:8100 npm run dev` from `frontend/`. Stop Vite, then Ctrl-C the helper when finished; the helper removes its own temporary database and storage. Ports must be free.

**Current helper caveat:** it predates direct routing. It clears compatible-provider fields by default but does not override `provider_mode` or direct API credentials. The command above explicitly forces compatible mode. For a live compatible-provider rehearsal, securely export the three required compatible settings, retain `CONCEPTLENS_PROVIDER_MODE=compatible`, and add `--with-provider`. That flag currently requires compatible settings even if direct mode was selected. Do not invent dummy gateway fields to bypass it; use the normal local setup for direct-mode testing. Reconcile this caveat with the final integrated source before recording.

See the [4:40 script](DEMO_VIDEO_SCRIPT.md) and [historical detailed demo guide](../phase11/demo-guide.md). The historical guide's claims about provider isolation and a shared verifier model need the mode-specific qualifications above.

## Tests

From the repository root, run ordinary backend tests with external configuration cleared:

```sh
CONCEPTLENS_PROVIDER_MODE=compatible \
CONCEPTLENS_LLM_BASE_URL='' CONCEPTLENS_LLM_API_KEY='' CONCEPTLENS_LLM_MODEL='' \
CONCEPTLENS_VISION_MODEL='' CONCEPTLENS_OPENAI_API_KEY='' OPENAI_API_KEY='' \
CONCEPTLENS_DATABASE_URL='sqlite+aiosqlite:///' \
backend/.venv/bin/pytest -q backend/tests
```

These tests use SQLite and fake/injected model or embedding I/O; opt-in PostgreSQL suites are skipped by default. They are not real-provider acceptance.

```sh
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
# If a Playwright browser is not already installed:
npx playwright install chromium
CI=1 npm run test:e2e
```

Fixture Playwright journeys exercise UI states at desktop/mobile sizes. Live cases are opt-in. Keep port 5173 free for the test server; an existing server prevented the browser rerun in this review. Do not stop someone else's server or silently reuse an unknown backend.

For a disposable real-ingestion browser smoke, use the helper command above with `--browser-smoke` instead of `--serve`; it starts the necessary servers and tests. This requires PostgreSQL, cached/downloadable embeddings and a browser, and still does not certify real generation. For optional evaluation/database suites and their separate locked framework environment, follow [evaluation/README.md](../../evaluation/README.md). No benchmark rerun is required simply to try the app.

Current review: **590 backend passed / 23 skipped; 52 frontend passed; typecheck, lint and build passed.** Historical live smoke and fixture results are separately labeled in [VERIFICATION.md](VERIFICATION.md). Fresh dependency installation, migrations and a live provider journey were not rerun in this documentation task.

## Limitations and troubleshooting

| Symptom or limit | What to check |
| --- | --- |
| Course loading fails | Backend process, database connection and Vite proxy target; `/health` alone does not check the database. |
| Port is occupied | Use the intended server/port after identifying it. Do not kill an unrelated process. |
| Nothing is retrieved | Source processing status, explicit indexing, embedding model availability and supported source evidence. |
| Model unavailable or completion times out | Selected mode, authorized model access, endpoint contract and actual completion response. Network/gateway health is not proof of generation. |
| Images extracted but not searchable | Interpretation must be accepted, then explicitly re-indexed. Extraction is not verified semantic understanding. |
| MP4 transcription fails | FFmpeg/FFprobe, Apple Silicon MLX Whisper and model download/cache availability. Other platforms need an implemented alternative provider. |
| No concept/mastery change | Curated mappings, a fresh eligible verified question and a gradable attempt. Repeats, ambiguous mappings and ungradable responses may be excluded. |
| PPTX looks different | Preview approximates source content; complex charts, groups, themes and effects may be omitted. Open the original file. |

No general scanned-PDF OCR, PDF region highlighting, handwritten learner reasoning, durable chat history or authentication is implemented. Keep the unauthenticated prototype local. BKT defaults are uncalibrated and small-sample estimates provisional. Scheduling models one CPU with integer ticks and no context-switch overhead. Real AI acceptance, real vision quality and real grounding scores remain pending; simulations are not student outcome evidence.

## Contributors

| Real full name | Contribution | Devpost account |
| --- | --- | --- |
| `MEMBER_1_FULL_NAME` | `CONFIRMED_CONTRIBUTION` | `MEMBER_1_DEVPOST_URL` |
| `MEMBER_2_FULL_NAME_IF_APPLICABLE` | `CONFIRMED_CONTRIBUTION` | `MEMBER_2_DEVPOST_URL` |

Confirm the final roster of 1–4 members; add/remove rows accordingly. Do not infer full names from machine paths or Git handles. AI coding/review assistance was disclosed in the existing README; human review remains necessary before submission.
