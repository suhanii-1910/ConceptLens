# ConceptLens

**Learn anything. Debug your understanding.**

ConceptLens is a multimodal adaptive-learning platform. It builds a model of the learning material, a model of the learner, and a policy for choosing the next learning action.

---

## Current implementation status

**Phase 1C — PDF, PPTX, and video ingestion complete.**

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

### Current limitations

- No legacy .ppt support
- No SmartArt, chart, or vector-diagram interpretation
- No WordArt semantics, OLE, or macro interpretation
- **No OCR** — scanned PDFs produce zero text evidence
- **No LLM/AI calls** — `topic`, `subtopic`, and `extracted_description` are left NULL
- **No embeddings or vector search**
- **No authentication** — all endpoints are open
- **No frontend**

### NOT implemented (future phases)

- OCR for scanned documents
- AI descriptions / captions for images
- AI / LLM calls (topic classification, description generation)
- Embeddings / pgvector similarity search
- RAG (retrieval-augmented generation)
- Tutoring / chatbot
- Assessment generation
- Learner modelling / mastery tracking
- Reasoning diagnosis
- Teaching policy
- Evaluation
- Authentication / authorization
- Frontend

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
│   │   ├── services/       # Business logic, storage, PDF/PPTX/video ingestion
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

---

## Known limitations

- **No Docker in CI/dev environment**: Migrations require a running PostgreSQL instance started via `docker compose up -d`. Tests use in-memory SQLite and do not require PostgreSQL.
- **Supported processing formats**: PDF, PPTX, and MP4 video. Legacy `.ppt` is not supported.
- **No OCR**: Scanned PDFs produce zero text evidence — no text is fabricated.
- **Video visual semantics**: Video frames are grounded to real decoded-frame timestamps, but Phase 1C does not yet perform OCR, captioning, diagram interpretation, or other visual semantic analysis.
- **No authentication**: All endpoints are open.
- **Duplicate detection is per-course**: The same file uploaded to different courses creates separate records.
- **No file-size limits enforced at the application level**: Large uploads are accepted (rely on reverse proxy limits in production).
