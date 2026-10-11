# ConceptLens

**Learn anything. Debug your understanding.**

Most AI tutors optimize the answer. **ConceptLens optimizes the next learning action.**

A fluent explanation can leave the learner's original mistake intact. ConceptLens connects course evidence, the learner's answer and reasoning, a tentative diagnosis, targeted teaching, and a fresh Transfer Check. It shows the source and the evidence behind its decisions.

**Status:** Phase 10 functionality is implemented; Phase 11 adds final acceptance, reproducible demo tooling, documentation and submission assets. This is a local hackathon prototype, with exactly five principal views. [Release verification](docs/phase11/verification.json) records actual tests. **Real provider acceptance and real framework grounding scores remain PENDING CONFIGURATION.**

[Run the demo](docs/phase11/demo-guide.md) · [Submission draft and video plan](docs/phase11/submission.md) · [Evaluation methodology](evaluation/README.md)

## The learner journey

| View | What the learner does |
| --- | --- |
| Workspace | Organize PDF, PPTX and MP4 sources; process and index their evidence. |
| Ask | Ask a grounded question, inspect its citation, open the exact source location. |
| Learn | Answer a verified question, explain reasoning, test a diagnosis hypothesis, and follow the next learning action. |
| Practice | Try multiple-choice, short-answer or numerical questions, or start a short diagnostic. |
| Dashboard | Inspect observed mastery, untested concepts, source-linked prerequisites and the assessment report. |

**Judge journey:** source → grounded Ask → exact citation → verified assessment → learner reasoning → possible first break → diagnostic probe → source-backed teaching → different strategy if still confused → prerequisite repair when justified → fresh Transfer Check → eligible mastery update → Learning Trace → Dashboard.

### Evidence before explanation

PDF text, tables and embedded images preserve page provenance. PPTX extraction preserves slide locations. Video uses timestamped transcription and actual decoded frames. Hybrid retrieval combines local embeddings with PostgreSQL lexical search; citation validation checks ownership, readiness and stored locators. Unsupported questions are declined rather than answered from invented course evidence.

The source viewer opens the exact PDF page, a PPTX content preview, or a video timestamp. PPTX preview is an approximation, with the original file available. Images and video frames can be interpreted by a configured vision model; a separate verification call inspects the same actual image bytes before the description is accepted. Extraction alone is never presented as semantic understanding. After acceptance, explicitly re-index in Workspace.

### Assessment, reasoning and the next action

Generated questions must pass a separate verifier call. Private answer keys and grading contracts stay on the server until submission. MCQ grading is deterministic; numerical grading uses exact arithmetic and validated units/tolerance; short-answer grading uses a source-constrained semantic evaluator and can return **cannot grade**. Provider failure cannot become a correct answer.

The Reasoning Debugger uses the original attempt, learner-authored reasoning and course evidence to propose a **possible** first reasoning break. A diagnostic probe can confirm, reject or leave that hypothesis unresolved. A wrong answer alone does not permanently label a learner.

The adaptive policy chooses among source explanation, visual explanation, prerequisite checks/recaps, worked examples, practice and a fresh Transfer Check. Strategies are bounded and do not repeat within a session. Prerequisite repair requires a stored relationship and evidence. Safe concept-level learning can continue after an unconfirmed diagnosis without pretending the hypothesis is true.

Bayesian Knowledge Tracing (BKT) estimates mastery from eligible verified attempts. **Reading an explanation does not increase mastery.** Repeated exposure, probes and ungradable responses do not manufacture new mastery evidence. Untested concepts remain **Untested**, not weak. The persistent short diagnostic samples course concepts, while the report separates first gradable attempts, repeats and ungradable responses. Small samples and uncalibrated BKT defaults limit interpretation.

“**Why did ConceptLens do this?**” opens the Learning Trace: original evidence, diagnosis status, strategy decisions, prerequisites, transfer outcome and actual mastery changes. Missing proof stays visibly unverified.

### CPU Scheduling showcase

The generic deterministic scheduler supports FCFS, SJF, SRTF, non-preemptive and preemptive priority, and Round Robin. It computes execution segments, dispatch decisions, completion, turnaround, waiting and response time before grading scheduling questions.

Under SRTF, compare **remaining time**, not original burst:

| Processes (arrival, burst) | Generic solver result |
| --- | --- |
| P1 (0, 8), P2 (5, 4) | At t=5, P1 has 3 remaining; it continues. P1 0–8, P2 8–12. |
| P1 (0, 9), P2 (4, 3) | At t=4, P1 has 5 remaining; P2 preempts. P1 0–4, P2 4–7, P1 7–12. |

No production branch special-cases these examples. The [authored demo source](demo-course/cpu-scheduling.md) teaches the general rule without embedding either example. Generated questions and diagnosis outcomes remain provider-dependent; a particular live question or transfer variant is not guaranteed.

## Evaluation: evidence and trade-offs

Two separate tracks measure grounding and simulated personalization. Grounding uses a frozen authored PDF/PPTX/video benchmark, deterministic citation/refusal checks and RAGAS 0.4.3. **Real framework results are pending, not zero.** Positive/negative framework fixtures test the metric implementation; they are not product quality measurements.

**SIMULATED PERSONALIZATION RESULT** — the historical [Phase 10 post-change run](evaluation/reports/post-phase10-simulation.json), 120 learner identities, 480 sessions per policy:

| Metric | Fixed | Simple Adaptive | ConceptLens |
| --- | ---: | ---: | ---: |
| Held-out transfer success | 57.92% | 60.00% | 59.38% |
| Interventions per successful transfer (lower is cheaper) | 5.18 | 6.87 | 7.12 |
| Exact question repetition | 33.33% | 33.82% | 17.29% |
| Session completion | 58.13% | 86.25% | 58.96% |
| Simulated latent mastery gain | +0.1958 | +0.2260 | +0.2123 |
| BKT absolute tracking error | 0.2439 | 0.2609 | 0.2540 |

ConceptLens slightly exceeds Fixed transfer and remains slightly below Simple Adaptive. It repeats fewer exact questions, but uses more interventions per successful transfer. This is **not a real student study**, a claim of statistical significance, or evidence of universal superiority. Latent learning gains depend on published simulator assumptions. Template repetition remains high; the raw artifact and [methodology](evaluation/README.md) expose the full metrics and uncertainty.

Phase 9 results and Phase 10 pre/post artifacts are historical records. Phase 11 preserves the frozen benchmark inputs, policy adapter and result artifacts. [Phase 10 implementation notes](docs/phase10/implementation.md) describe that earlier acceptance state.

## Architecture and stack

```text
React / TypeScript / Vite — five views
                 |
              FastAPI
                 |
       +---------+------------------+
       |                            |
 PDF / PPTX / video ingestion    Learning services
       |                      assessment / diagnosis
 Evidence + provenance         adaptive policy / BKT
       |                            |
 Hybrid retrieval → grounding → Ask / teaching / trace
                 |
        PostgreSQL 16 + pgvector

External text/vision models sit behind provider adapters.
Course-owned originals and derived artifacts are stored separately.
```

One modular monolith: SQLAlchemy, Alembic, PyMuPDF, pdfplumber, python-pptx, FFmpeg/FFprobe, local sentence-transformers and optional Apple Silicon MLX Whisper transcription. Processing is explicitly requested through the API; there is no separately deployed ingestion worker to start.

## Local setup

Prerequisites: Python 3.12+, Node 22.12+ (Node 24 used for acceptance), PostgreSQL 16 with pgvector (Docker Compose supplied). Video requires FFmpeg/FFprobe; the default transcription provider requires Apple Silicon macOS. Local embedding/ASR models need an initial download or an existing cache.

From the repository root:

```sh
cp .env.example .env
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e './backend[dev]'
docker compose up -d
cd frontend
npm ci
cd ..
```

The root `.env` is loaded regardless of working directory. Storage paths are relative to the backend process's working directory; the template assumes backend startup from `backend/`. PostgreSQL is bound to localhost port **55432**. Compose credentials are local development defaults, not production secrets.

For a **new, intended local application database only**, initialize its schema:

```sh
cd backend
.venv/bin/alembic upgrade head
.venv/bin/alembic current
```

Current head is **0007**. Existing databases already at 0007 need no migration. Do not run reset/downgrade commands to prepare a demo. Automated acceptance uses disposable databases exclusively; Phase 11 did not connect to or migrate the normal development database.

Start the backend in one terminal:

```sh
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Start the frontend in another:

```sh
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`; API documentation is at `http://127.0.0.1:8000/docs`. Vite proxies `/api` to the backend. `CONCEPTLENS_API_PROXY_TARGET` overrides the development proxy target for disposable acceptance; `VITE_API_BASE_URL` is the optional public frontend API prefix. Never place credentials in a `VITE_` variable.

### Model configuration

Set these backend variables in the untracked root `.env`, or export them from your local secret manager. No provider or exact model has been verified in this release.

| Variable | Role |
| --- | --- |
| `CONCEPTLENS_LLM_BASE_URL` | OpenAI-compatible API base; adapter appends `/chat/completions`. |
| `CONCEPTLENS_LLM_API_KEY` | Backend-only provider credential. |
| `CONCEPTLENS_LLM_MODEL` | Text model for Ask, generation, verifier, semantic grading, diagnosis and teaching. |
| `CONCEPTLENS_LLM_TIMEOUT_SECONDS` | Per-call timeout, default 45 seconds. |
| `CONCEPTLENS_VISION_MODEL` | Image-capable model using the same base URL/key for visual interpretation and verification. |

Verification uses a separate call with its own verification prompt; it currently shares the configured model/endpoint. “Independent verification” does not mean statistically independent models. All three text settings are required for generated learning. Vision additionally requires its model setting. Missing configuration yields explicit unavailability, never fabricated output.

The demo helper deliberately requires exported process settings and `--with-provider`; it does not inherit model credentials from `.env`. Do not set `TESTING=1` or `USE_FAKE_EMBEDDING=1` for a real demo. [Full demo instructions](docs/phase11/demo-guide.md) cover source preparation, curated concepts, provider checks and recovery.

## Verification

From the repository root:

```sh
backend/.venv/bin/pytest -q backend/tests
CONCEPTLENS_EVAL_ADMIN_URL='postgresql+asyncpg://conceptlens:conceptlens@127.0.0.1:55432/postgres' \
  PYTHONPATH=evaluation:backend backend/.venv/bin/pytest -q evaluation/tests
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
npm run test:e2e
```

If needed, install the browser with `npx playwright install chromium`; alternatively select an installed Chrome using `PLAYWRIGHT_CHANNEL=chrome`. Evaluation framework tests require the separate locked environment described in [evaluation setup](evaluation/README.md).

Backend defaults skip opt-in PostgreSQL tests. Fixture Playwright checks desktop/mobile UI behavior using clearly isolated test data; they do not establish provider quality. To run the existing live smoke safely, with real ingestion, local embeddings and a disposable backend:

```sh
CONCEPTLENS_EVAL_ADMIN_URL='postgresql+asyncpg://conceptlens:conceptlens@127.0.0.1:55432/postgres' \
  backend/.venv/bin/python demo-course/prepare.py --browser-smoke
```

This creates and drops only a random `conceptlens_eval_<uuid>` database through the existing safe harness. It checks the honest provider-unconfigured state and cleans up its processes/storage. Ports 8100 and 5173 must be free. See [verification.json](docs/phase11/verification.json) for exact observed results and pending gates.

## Limits and evidence discipline

- Real model acceptance, end-to-end provider learning, vision quality and real RAGAS scores remain pending configuration. Fixture success is not provider acceptance.
- No general scanned-PDF OCR or PDF region highlighting. Raster source visuals can be interpreted when configured; complex PPTX charts, groups, themes and effects may be omitted or simplified.
- Scheduling assumes one CPU, integer ticks and no context-switch overhead. It is a bounded teaching model.
- Concept/evidence mappings and prerequisites require curation; the demo helper supplies transparent authored metadata, not learner history. There is no general concept-authoring UI.
- BKT defaults are uncalibrated; the report is provisional for small samples. Retrying an already exposed question may not create a new mastery observation, including after an earlier ungradable exposure.
- No authentication/authorization, durable chat history, image/handwritten learner reasoning or production cloud deployment. Keep the unauthenticated prototype local; it is not ready for public multi-user hosting.
- Source ownership, course isolation, citation grounding, private grading contracts, immutable attempts, transfer freshness and honest provider failure are enforced boundaries. Source documents are evidence, not runtime instructions.

## Repository map and AI disclosure

| Path | Purpose |
| --- | --- |
| `backend/app/` | API, schemas, models, ingestion and learning services |
| `backend/alembic/` | Historical migrations through 0007 |
| `frontend/` | Five-view React application and UI acceptance |
| `evaluation/` | Frozen datasets, framework runner, simulator and historical reports |
| `demo-course/` | Authored general rules and disposable demo preparation |
| `docs/phase11/` | Demo guide, submission/video draft and release verification |
| `docs/phase10/` | Historical Phase 10 acceptance records |

**Product AI:** ConceptLens uses configurable external text/vision providers and local embedding/transcription models. The provider identity and exact runtime text/vision model are operator choices; this release did not verify real external model use.

**Development assistance:** AI coding and review assistance, including Codex, was used during development. Automated tests and recorded verification support the implementation claims. Human review and responsibility remain with the project team. No private conversations or provider credentials are included in submission assets.
