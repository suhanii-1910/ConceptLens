# ConceptLens

**Learn anything. Debug your understanding.**

ConceptLens is a multimodal adaptive-learning platform. It builds a model of the learning material, a model of the learner, and a policy for choosing the next learning action.

---

## Current implementation status

**Phase 6 — Reasoning Debugger and Diagnostic Probes implemented.**

### Phase 0A — Backend foundation

- FastAPI backend skeleton
- PostgreSQL + pgvector database configuration
- Database models (Course, SourceVersion, EvidenceUnit, Concept, PrerequisiteEdge)
- Alembic migrations
- Course CRUD API
- Raw source file upload and storage (PDF, PPTX, PPT, MP4)

### Phase 1A — PDF ingestion

- **Text extraction**: Page-by-page, block-by-block via PyMuPDF with minimum-content threshold (≥20 non-whitespace characters)
- **Table extraction**: pdfplumber `find_tables()` per page, serialised as Markdown pipe-delimited format
- **Image extraction**: Embedded raster images via PyMuPDF, filtered for minimum dimensions (50×50 px), saved to derived storage
- **Provenance**: Every EvidenceUnit carries `location_metadata` with page_index (0-based), page_number (1-based), printed_page_label, bounding_box, block_index, element_type
- **Processing status**: Transitions `uploaded → processing → ready` (or `→ failed` on error)
- **Idempotency**: Already-processed sources return existing results without creating duplicates; failed sources can be retried
- **Derived storage**: Extracted images stored under `storage/derived/<source_version_id>/`, separate from originals
- **API endpoint**: `POST /courses/{course_id}/sources/{source_version_id}/process` (201 on fresh processing, 200 if already processed)
- **Scanned PDFs**: Process successfully with zero text evidence (no OCR, no fabrication)
- **Automated regression suite**: 72 passing tests across backend ingestion and API behavior

### Phase 1B — PPTX ingestion

- **Text extraction**: Normal text extraction preserving slide structure
- **Table extraction**: Native tables correctly rendered as deterministic Markdown pipe-delimited tables
- **Image extraction**: Embedded raster image extraction to derived storage
- **Provenance**: Slide index, slide number, shape index, exact bounding box
- **Resilience**: Idempotent processing and failure/partial evidence safety

### Phase 1C — Video ingestion

- **Media inspection**: FFprobe detects source duration and available audio/video streams
- **Local transcription**: Timestamped speech transcription through a provider interface, with MLX Whisper (`mlx-community/whisper-base-mlx`) as the default Apple Silicon provider
- **Grounded transcript provenance**: Transcript EvidenceUnits preserve real provider timestamps and source duration
- **Terminal timestamp hardening**: Small ASR end-boundary overshoots are bounded to the real source duration while preserving the provider's original timestamp and adjustment metadata
- **Decoded-frame provenance**: Representative visual evidence is selected only from actual FFprobe-decoded frames — citation timestamps are never mathematically fabricated
- **Frame extraction**: Selected frames are extracted by decoded frame index with source frame index, real timestamp, width, height, keyframe flag, selection method, and source duration recorded in provenance
- **Source immutability**: Original video SHA-256 is verified before and after processing
- **Derived storage**: Extracted frames are stored separately under `storage/derived/<source_version_id>/`
- **Stream resilience**: Video-only and audio-only media are handled with explicit warnings; media with no usable streams fails
- **Idempotency**: Reprocessing an already-ready source creates no duplicate EvidenceUnits or derived frames
- **Failure cleanup**: Partially created derived frame artifacts are removed when processing fails
- **No visual semantic interpretation yet**: Frames are preserved as grounded visual evidence but are not captioned or interpreted by an AI model in Phase 1C


### Phase 2A — Hybrid evidence retrieval

- **Explicit evidence indexing**: Course-scoped indexing prepares existing extracted EvidenceUnits for retrieval without creating new evidence
- **Local semantic embeddings**: `sentence-transformers/all-MiniLM-L6-v2` generates normalized 384-dimensional embeddings
- **Embedding change detection**: SHA-256 content hashes and model identifiers prevent unnecessary re-embedding of unchanged evidence
- **Dense retrieval**: PostgreSQL `pgvector` cosine-distance search over indexed EvidenceUnits
- **Lexical retrieval**: PostgreSQL full-text search using `to_tsvector`, `websearch_to_tsquery`, and ranked lexical candidates
- **Hybrid ranking**: Reciprocal Rank Fusion (RRF) combines dense and lexical rankings without mixing incomparable raw score scales
- **Course isolation**: Dense and lexical retrieval are both restricted to the requested course
- **Evidence safety**: Retrieval includes only extracted EvidenceUnits from ready SourceVersions
- **Optional filters**: Retrieval supports modality and source-version filtering
- **Grounded results**: Retrieval returns stored EvidenceUnit provenance and source metadata without fabricating page, slide, timestamp, or bounding-box information
- **Image limitation**: Raw image EvidenceUnits without real semantic descriptions remain unembedded and are not semantically searchable
- **API endpoints**:
  - `POST /courses/{course_id}/retrieval/index`
  - `POST /courses/{course_id}/retrieval/search`

### Phase 2B — Citation + Grounding Validation

- **Deterministic provenance validation**: Every retrieval result is validated against stored evidence before any citation is issued — no citations are fabricated
- **PDF page grounding**: Page index, page number, and optional printed page label are validated for internal consistency; bounding boxes are checked for geometric validity
- **PPTX slide grounding**: Slide index, slide number, and optional shape index are validated; bounding boxes are checked
- **Video transcript timestamp grounding**: Start/end seconds are validated for ordering, finiteness, and bounds against recorded source duration
- **Decoded video-frame grounding**: Frame timestamps and source frame indices are validated; timestamps are never mathematically derived — only real decoded-frame provenance is accepted
- **Structured citation objects**: Valid results carry a `Citation` with `locator`, `locator_label`, `location_metadata`, source identity, and modality
- **Invalid provenance rejection**: Any inconsistency (wrong course, source mismatch, bad locator, unready source) produces `grounding_status=invalid` with structured `grounding_errors`; the HTTP response is still 200
- **Course/source/status consistency checks**: Evidence unit course, source version course, and expected course are compared directly; source version must be `ready` and evidence unit must be `extracted`
- **Safe public provenance metadata**: Citation and retrieval result `location_metadata` are filtered through a per-source-type allowlist — only known safe keys are exposed
- **Local derived/storage paths excluded**: Fields such as `derived_path` carrying filesystem paths are excluded from all public surfaces by the allowlist; raw DB metadata is never mutated
- **`only_grounded` downstream boundary**: A utility filter exposes only fully-validated results to downstream consumers, enforcing the grounding boundary

### Phase 2C — Unsupported / Insufficient-Evidence Boundary

- **Deterministic evidence support classification**: Every search response includes an `evidence_boundary` decision object with one of three stable statuses: `supported`, `insufficient_evidence`, or `unsupported`
- **Distinct relevance and grounding requirements**: Relevance qualification (is this evidence semantically or lexically related?) and grounding validation (is this evidence citable?) are evaluated separately — a result can be relevant but ungradeable, or graded but irrelevant
- **Dense relevance signal**: An evidence unit is relevance-qualified by dense retrieval when its cosine distance is finite, non-negative, and at or below the 0.55 threshold (conservatively calibrated for the `all-MiniLM-L6-v2` embedding space, range approximately [0, 2])
- **Lexical relevance signal**: An evidence unit is also relevance-qualified when its PostgreSQL `ts_rank` score is a positive finite number (any FTS match)
- **RRF rank and fused score are NOT support signals**: `dense_rank`, `lexical_rank`, and `fused_score` are relative ranking signals; they are never treated as calibrated evidence quality probabilities; rank #1 alone cannot make evidence supported
- **Grounded citation required**: A relevance-qualified evidence unit is usable only when Phase 2B grounding is `valid` AND a `Citation` object is present — both conditions must hold
- **Three decision states**:
  - `supported`: at least one retrieved result is relevance-qualified, grounding valid, and has a citation — future answer generation may use only those usable results
  - `insufficient_evidence`: at least one result is relevance-qualified but no relevance-qualified result is safely grounded — related material was found but source-backed answers cannot be issued
  - `unsupported`: no results at all, or no result met the relevance threshold — the current uploaded course materials do not provide sufficiently relevant support for the query
- **"Unsupported" is not real-world falsity**: The absence of support in uploaded course materials does not mean the claim is false in the world; decline messages say exactly that
- **Stable, safe decline messages**: Human-readable decline messages are deterministic string constants (not generated text); `supported` carries no message
- **`only_supported_evidence` downstream gate**: A pure helper function returns only usable evidence units for future answer generation; it preserves retrieval order, all ranking scores, all citation data, and all provenance without rescoring or mutation
- **Future answer generation must use only supported evidence**: The boundary decision is the enforceable gate between retrieval and any future RAG or Ask phase; downstream consumers must check `should_decline` before generating a source-backed answer
- **No database mutation**: Phase 2C performs no DB writes, no extra DB reads, and does not alter any stored provenance
- **No LLM required**: The boundary classification is entirely deterministic — no language model is called at any point in the boundary decision
- **`evidence_boundary` field is additive**: The search API still returns all retrieved results in `results` for inspection; the boundary object is added alongside, not in place of, existing results

### Phase 3 — Grounded Ask Experience

- **Stateless grounded question answering**: `POST /courses/{course_id}/ask` accepts a learner question and an ask mode, answering strictly from grounded course evidence without maintaining server-side conversational state.
- **Three ask modes**:
  - `just_answer`: Direct, concise answer grounded in course material.
  - `explain`: Structured step-by-step conceptual explanation with grounded answer blocks.
  - `guide`: Socratic guiding hints and scaffolding, concluding with a targeted follow-up question (`next_question`).
- **End-to-end grounded pipeline**:
  `retrieval → grounding → evidence boundary → supported-only evidence → provider → evidence-ID validation → server citation mapping`
- **Pre-generation deterministic boundary gate**:
  Retrieval and Phase 2C evidence boundary qualification run before any provider call. If the evidence boundary evaluates to `unsupported` or `insufficient_evidence`, the endpoint immediately returns HTTP 200 with status `declined` and a deterministic decline message. The external LLM provider is **never called**, preventing hallucination and unnecessary provider spend.
- **Model sees only supported evidence**:
  Only evidence units that pass both Phase 2A relevance qualification and Phase 2B grounding validation are supplied to the model. Ungrounded or irrelevant material is excluded.
- **Model never authors Citation objects**:
  The language model returns only draft answer blocks referencing `evidence_unit_ids`. The model never generates citations, locator labels, page/slide numbers, or file paths.
- **Server-driven citation mapping**:
  The server validates referenced `evidence_unit_ids` against the verified supported evidence set and maps them directly to immutable, exact Phase 2B `Citation` objects.
- **Fail-closed on hallucinated evidence IDs**:
  If the model cites unknown, unprovided, or hallucinated `evidence_unit_ids`, or returns malformed output, the system fails closed with HTTP 502 Bad Gateway without returning partial or ungrounded answers.
- **Answer construction**:
  The final top-level `answer` is constructed server-side by joining validated block texts; the provider returns block drafts only.
- **Untrusted data & prompt injection defense**:
  All source evidence content is strictly demarcated as untrusted data in prompts. Prompt injection instructions appearing inside course evidence are systematically ignored. Learner requests to bypass grounding or answer from outside knowledge are declined.
- **Private path and prompt safety**:
  Responses expose zero private filesystem paths (`storage_path`, `derived_path`), system prompts, internal prompts, or provider credentials.
- **OpenAI-compatible provider adapter**:
  Configurable LLM provider integration via standard HTTP client (`httpx`) targeting any OpenAI-compatible API endpoint with zero temperature and structured JSON response handling.
- **Server-only provider credentials**:
  API keys and endpoint configurations remain strictly server-side and are never exposed across API boundaries or logged.
- **Exact citation provenance preserved**:
  Downstream citations preserve exact source provenance from Phase 1 and Phase 2 (PDF page numbers, PPTX slide numbers, transcript start/end timestamps, decoded video frame timestamps, and public locator labels).

### Phase 4 — Grounded Assessment System

- **MCQ assessment v1**: Generates 4-option single-select multiple choice questions anchored strictly to verified course evidence.
- **API Endpoints**:
  - `POST /courses/{course_id}/assessments/generate`: Request generation of questions for a topic focus and requested difficulty (`easy`, `medium`, `hard`).
  - `GET /courses/{course_id}/assessments/questions/{question_id}`: Fetch public representation of a verified question.
  - `POST /courses/{course_id}/assessments/questions/{question_id}/attempts`: Submit learner attempt and receive deterministic grading.
- **Pipeline flow**:
  - `hybrid retrieval → Phase 2B grounding → Phase 2C evidence boundary`.
  - Only supported evidence reaches generator and verifier.
  - Unsupported or insufficient evidence calls provider 0 times (early decline with HTTP 200).
- **Dual-model generation & independent verification**:
  - Generator and verifier are separate, decoupled provider calls.
  - Only independently verified questions are persisted transactionally to the database.
  - Server validates all generator and verifier claimed evidence unit IDs against the supported allowlist (tampered or unallowed IDs fail closed).
- **Exact Phase 2B citation snapshots**:
  - Stored questions record immutable, exact Phase 2B `Citation` snapshots, preserving full source provenance while guaranteeing public safety (no internal `storage_path` or `derived_path` leaks).
- **Public question answer-key safety**:
  - Public generated/fetched questions hide answer key (`correct_option_index`, `correct_option_text`).
  - Public generated/fetched questions hide `explanation`.
- **Deterministic grading**:
  - Deterministic grading after learner submission via direct index comparison on server.
  - Grading uses NO LLM (0 provider calls).
- **Attempt immutability**:
  - Attempts are immutable append-only rows (`AssessmentAttempt`).
  - Second submission creates a new attempt; previous attempt rows remain unchanged.
- **Post-submission reveal**:
  - Attempt response reveals answer, explanation, and citations only after submission.
- **Difficulty and focus**:
  - Requested difficulty `easy` / `medium` / `hard`.
- **Learner identity & state**:
  - `learner_id` is an opaque client-provided UUID, not authenticated identity.
  - Phase 4 alone performs no mastery updates; Phase 5 adds the policy below.

### Phase 5 — Persistent Learner Mastery

- **Trusted mapping prerequisite:** course Concepts and `evidence_concept_link` annotations must already be curated. Ingestion does not infer concepts. New verified questions freeze their deduplicated same-course mapping from verifier-approved evidence only; existing questions remain unmapped.
- **Deterministic BKT v1:** initial mastery `0.20`, learn `0.10`, guess `0.20`, slip `0.10`, model version `bkt-v1`. These defaults are **uncalibrated estimates**. Stored mastery is capped at `1 - 1e-12` to avoid absorbing certainty; mastery bands are presentation labels, not diagnoses.
- **Singleton and first-exposure policy:** exactly one mapped concept and no previous learner/question attempt produces `updated`. Otherwise the attempt persists with `skipped_unmapped`, `skipped_ambiguous`, or `skipped_repeated_question`. Historical Phase 4 attempts count as prior exposure.
- **Atomic persistence:** attempt, mastery counters/probability, and immutable ordered observations commit together. PostgreSQL insert-on-conflict plus a row lock serializes mastery updates; exposure is rechecked under that lock. Repeats never increment observations or change `last_attempt_id`.
- **Read-only API:** `GET /courses/{course_id}/learners/{learner_id}/mastery` lists every course concept by name then UUID; appending `/{concept_id}` reads one. Unseen concepts return virtual `0.20` mastery, zero counts, `unseen`, and null timestamps/last attempt. Reads create no state.
- **Isolation and boundaries:** grading and mastery call no LLM/provider. Course and learner UUID scope every estimate; an opaque learner UUID provides no authentication. Question answers remain hidden until submission.
- **Verification:** Phase 5 unit/API tests cover mapping, BKT, reads, and rollback. Run `CONCEPTLENS_TEST_POSTGRES=1 .venv/bin/python -m pytest tests/test_mastery_postgres.py` from `backend` for real PostgreSQL concurrency acceptance. It uses disposable schemas on the local development database (or `CONCEPTLENS_TEST_POSTGRES_URL`), without rerunning migrations or changing application rows.

### Phase 6 — Reasoning Debugger

- **Event-scoped hypotheses:** a diagnosis belongs to an existing learner assessment attempt and its still-verified, same-course question. A wrong answer alone never diagnoses a misconception. The observation and tentative hypothesis remain separate, inspectable fields; neither becomes a permanent learner label.
- **Typed reasoning:** accepts `reasoning_text` (up to 8,000 characters), `reasoning_steps` (up to 20 nonblank steps of 1,000 characters), or both, with a combined 12,000-character limit. Original input is preserved. First-break excerpts must occur verbatim in that input; structured-step indices are zero-based and validated against the submitted steps.
- **Fail closed:** `no_clear_break`, `insufficient_reasoning`, and `insufficient_evidence` produce no hypothesis or probe. Very short explanations (under 12 trimmed characters) decline without a provider call. Unmapped questions and missing/unusable frozen evidence also decline. Unsupported or tampered model IDs and malformed responses return 502; provider configuration/network failures return 503.
- **Independent verification:** generation proposes one diagnosis/probe pair; a separate verifier checks the earliest break, tentative interpretation, allowed concept, supporting rule, fresh probe, unique correct answer, and absence of answer leakage. Only approved content persists; verifier-selected evidence replaces generator-selected evidence. Rejected candidates become `no_clear_break` without storing their proposed interpretation.
- **Server-owned citations:** context starts from the question's verifier-approved evidence IDs, exact frozen citation snapshots, and frozen concept mapping. Existing evidence/source rows are checked for course and provenance consistency. Context is bounded to 10 evidence items, 6,000 characters per item, 24,000 evidence characters, and 64,000 characters per user prompt. This implementation conservatively uses frozen evidence only; it does not retrieve additional evidence when that context is insufficient. Models cannot supply citation objects or source locators.
- **Existing prerequisite graph only:** public context lists up to 20 actual incoming same-course prerequisite edges for the verified target, in stable UUID order. Missing graph data yields an empty list. No graph or prerequisite lesson is generated.
- **Diagnostic probe:** one independently verified four-option MCQ tests the suspected reasoning distinction using fresh context. Public creation/GET responses hide its answer key and explanation. Submission grades deterministically, reveals the verified answer/explanation and exact citations, and requires no provider call.
- **Resolution means evidence, not certainty:** the first valid correct response rejects the hypothesis; an incorrect response confirms it **by this diagnostic probe**. These are not psychological certainties. Unsafe stored probe data resolves `inconclusive` and reveals no unsafe answer. Repeated attempts append audit rows but cannot flip the outcome. PostgreSQL `SELECT FOR UPDATE` serializes submissions; a partial unique index permits only one applied resolution per diagnosis.
- **Mastery remains separate:** diagnosis and probe processing never modify BKT state or observations. The read-only `cold_start` field is true when the learner has no positive mastery observation count in the course. Cold start remains untested; no new mastery estimate is created.
- **Atomic, auditable persistence:** diagnosis/probe creation and first resolution each commit as one transaction. Composite foreign keys enforce attempt/diagnosis/probe scope; original assessments and mappings remain untouched. ORM writes protect diagnosis content, probes, and append-only attempts. Whole-course ORM deletion cleans up the aggregate. Direct administrative SQL is outside the ORM immutability boundary.
- **Routes:** `POST /courses/{course_id}/learners/{learner_id}/reasoning-diagnoses` accepts `attempt_id` and reasoning; `GET .../{diagnosis_id}` returns the public event; `POST .../{diagnosis_id}/probe-attempts` accepts only `selected_option_index`.
- **Migration:** `0005` adds three Phase 6 tables and a composite unique key on assessment attempts, with no historical diagnosis backfill. Prior migrations remain unchanged. The normal development database is not migrated by acceptance tests.
- **Acceptance commands** (from `backend`):
  - `.venv/bin/pytest tests/test_reasoning_diagnosis.py tests/test_api_reasoning_diagnosis.py`
  - `CONCEPTLENS_TEST_POSTGRES=1 .venv/bin/pytest tests/test_reasoning_diagnosis_postgres.py -k 'not migration_lifecycle'`
  - `CONCEPTLENS_TEST_MIGRATION_LIFECYCLE=1 .venv/bin/pytest tests/test_reasoning_diagnosis_postgres.py -k migration_lifecycle -s`
  - PostgreSQL acceptance creates unique disposable databases on the configured test server (optional `CONCEPTLENS_TEST_POSTGRES_URL`), runs actual Alembic migrations, and drops only those databases. The role needs database-creation permission. The lifecycle check preserves representative Phase 5 rows through `0004 → 0005 → 0004 → 0005`.

### Explicitly NOT yet implemented

- adaptive difficulty selection from mastery
- adaptive teaching policy
- prerequisite repair lessons
- Transfer Check
- Learning Trace UI
- persistent chat history
- frontend
- image/handwritten/screenshot learner-reasoning interpretation (a later multimodal/UI requirement)
- authentication

### Current limitations

- No legacy .ppt support
- No SmartArt, chart, or vector-diagram interpretation
- No WordArt semantics, OLE, or macro interpretation
- **No OCR** — scanned PDFs produce zero text evidence
- **No authentication** — all endpoints are open
- **No frontend**
- **Stateless Ask** — no conversational follow-up memory; learner state includes concept mastery estimates and event-scoped diagnosis evidence

### NOT implemented (future phases)

- OCR for scanned documents
- AI descriptions / captions for images
- persistent conversations
- adaptive difficulty selection from mastery
- adaptive teaching policy
- prerequisite repair lessons
- image/handwritten learner-reasoning interpretation
- Transfer Check
- Learning Trace UI
- Authentication / authorization
- frontend

---

## Prerequisites

- Python 3.12+
- Docker & Docker Compose (for PostgreSQL)
- FFmpeg / FFprobe (required for video ingestion)
- Apple Silicon macOS for the default local MLX Whisper transcription provider
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

---

## Environment setup

```bash
# 1. Clone and enter the repository
cd ConceptLens

# 2. Copy environment config
cp .env.example .env
# Edit .env if you need non-default database credentials

# 3. Create virtual environment and install dependencies
cd backend
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

---

## Database startup

```bash
# From the repository root
docker compose up -d

# Verify PostgreSQL is running
docker compose ps
```

This starts PostgreSQL 16 with the pgvector extension pre-installed.  The container's port 5432 is mapped to **host port 55432** (localhost only) to avoid conflicts with any existing local PostgreSQL installation.

Default connection: `postgresql+asyncpg://conceptlens:conceptlens@localhost:55432/conceptlens`

> **`.env` location:** The `.env` file lives at the **repository root** (`ConceptLens/.env`), not inside `backend/`.  The application resolves this path automatically regardless of your working directory.

---

## Migration commands

```bash
cd backend
source .venv/bin/activate

# Run all migrations (initialize a clean database)
alembic upgrade head

# Check current migration status
alembic current

# Downgrade one revision
alembic downgrade -1
```

---

## Backend startup

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is then available at `http://localhost:8000`.

API docs: `http://localhost:8000/docs` (Swagger UI)

---

## Test commands

Tests run against an in-memory SQLite database — no PostgreSQL required.

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

---

## Directory overview

```
ConceptLens/
├── backend/
│   ├── app/
│   │   ├── api/            # Route handlers (health, courses, sources)
│   │   ├── core/           # Configuration (settings from env vars)
│   │   ├── db/             # Database engine, session, base model
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Ingestion, embeddings, indexing, and hybrid retrieval
│   │   └── main.py         # FastAPI app entry point
│   ├── tests/              # Pytest test suite
│   │   └── fixtures/       # Programmatic PDF fixture factory
│   ├── alembic/            # Database migrations
│   ├── alembic.ini         # Alembic configuration
│   └── pyproject.toml      # Python project & dependencies
├── frontend/               # (future) React/TypeScript frontend
├── worker/                 # (future) Ingestion/background worker
├── evaluation/             # (future) Evaluation runner
├── storage/
│   ├── uploads/            # Uploaded source files
│   └── derived/            # Extracted artifacts (images, etc.)
├── demo-course/            # (future) Demo course data
├── docs/                   # (future) Documentation
├── docker-compose.yml      # PostgreSQL + pgvector
├── .env.example            # Environment variable template
└── CLAUDE.md               # Engineering constitution
```

---

## API endpoints

| Method | Path                                                          | Description               |
|--------|---------------------------------------------------------------|---------------------------|
| GET    | `/health`                                                     | Health check              |
| POST   | `/courses`                                                    | Create a course           |
| GET    | `/courses`                                                    | List all courses          |
| GET    | `/courses/{course_id}`                                        | Get a single course       |
| POST   | `/courses/{course_id}/sources`                                | Upload a source file      |
| GET    | `/courses/{course_id}/sources`                                | List sources for a course |
| POST   | `/courses/{course_id}/sources/{source_version_id}/process`    | Process a supported source |
| POST   | `/courses/{course_id}/retrieval/index`                       | Index searchable evidence |
| POST   | `/courses/{course_id}/retrieval/search`                      | Hybrid evidence search    |

---

## Known limitations

- **No Docker in CI/dev environment**: Migrations require a running PostgreSQL instance started via `docker compose up -d`. Tests use in-memory SQLite and do not require PostgreSQL.
- **Supported processing formats**: PDF, PPTX, and MP4 video. Legacy `.ppt` is not supported.
- **No OCR**: Scanned PDFs produce zero text evidence — no text is fabricated.
- **Video visual semantics**: Video frames are grounded to real decoded-frame timestamps, but Phase 1C does not yet perform OCR, captioning, diagram interpretation, or other visual semantic analysis.
- **Image semantic retrieval**: Raster image EvidenceUnits without a real `extracted_description` are intentionally not embedded or semantically searchable yet.
- **No authentication**: All endpoints are open.
- **Duplicate detection is per-course**: The same file uploaded to different courses creates separate records.
- **No file-size limits enforced at the application level**: Large uploads are accepted (rely on reverse proxy limits in production).
