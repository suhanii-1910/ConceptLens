# ConceptLens

**Learn anything. Debug your understanding.**

ConceptLens is a multimodal adaptive-learning platform. It builds a model of the learning material, a model of the learner, and a policy for choosing the next learning action.

---

## Current implementation status

**Phase 0A — backend foundation only.**

This phase implements:

- FastAPI backend skeleton
- PostgreSQL + pgvector database configuration
- Database models (Course, SourceVersion, EvidenceUnit, Concept, PrerequisiteEdge)
- Alembic migrations
- Course CRUD API
- Raw source file upload and storage (PDF, PPTX, PPT, MP4)
- Automated tests (19 passing)

### NOT implemented

The following are **not** implemented and will come in future phases:

- AI / LLM calls
- RAG (retrieval-augmented generation)
- Multimodal parsing (PDF extraction, PPTX extraction, video transcription)
- Embeddings / pgvector similarity search
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
│   │   ├── services/       # Business logic (course service, file storage)
│   │   └── main.py         # FastAPI app entry point
│   ├── tests/              # Pytest test suite
│   ├── alembic/            # Database migrations
│   ├── alembic.ini         # Alembic configuration
│   └── pyproject.toml      # Python project & dependencies
├── frontend/               # (future) React/TypeScript frontend
├── worker/                 # (future) Ingestion/background worker
├── evaluation/             # (future) Evaluation runner
├── storage/
│   └── uploads/            # Uploaded source files
├── demo-course/            # (future) Demo course data
├── docs/                   # (future) Documentation
├── docker-compose.yml      # PostgreSQL + pgvector
├── .env.example            # Environment variable template
└── CLAUDE.md               # Engineering constitution
```

---

## API endpoints

| Method | Path                              | Description               |
|--------|-----------------------------------|---------------------------|
| GET    | `/health`                         | Health check              |
| POST   | `/courses`                        | Create a course           |
| GET    | `/courses`                        | List all courses          |
| GET    | `/courses/{course_id}`            | Get a single course       |
| POST   | `/courses/{course_id}/sources`    | Upload a source file      |
| GET    | `/courses/{course_id}/sources`    | List sources for a course |

---

## Known limitations

- **No Docker in CI/dev environment**: Migrations require a running PostgreSQL instance started via `docker compose up -d`. Tests use in-memory SQLite and do not require PostgreSQL.
- **No file parsing**: Uploaded files are stored but not parsed, indexed, or processed.
- **No authentication**: All endpoints are open.
- **Duplicate detection is per-course**: The same file uploaded to different courses creates separate records.
- **No file-size limits enforced at the application level**: Large uploads are accepted (rely on reverse proxy limits in production).
