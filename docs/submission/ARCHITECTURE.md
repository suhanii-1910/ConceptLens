# ConceptLens architecture

**Source-reviewed draft · commit `9fe1751` · 14 October 2026.** These diagrams describe the accessible implementation. They do not certify a successful real-provider journey or the unavailable Concept Observatory frontend. See [verification](VERIFICATION.md) and [repository provenance](INDEX.md).

## 1. Application structure

```mermaid
flowchart TD
    Browser[React + TypeScript + Vite]
    Browser --> W[Workspace]
    Browser --> A[Ask]
    Browser --> L[Learn]
    Browser --> P[Practice]
    Browser --> D[Dashboard]
    W & A & L & P & D --> Client[Typed API client]
    Client -->|Development /api proxy| API[FastAPI routers + Pydantic schemas]
    API --> Ingest[Ingestion / previews / indexing]
    API --> Retrieve[Hybrid retrieval / citation validation]
    API --> LearnServices[Assessment / diagnosis / adaptive learning]
    API --> Reports[Mastery / learner report / trace]
    Ingest --> Files[Course-owned originals + derived artifacts]
    Ingest --> Embeddings[Local sentence-transformers]
    Ingest & Retrieve & LearnServices & Reports <--> DB[(PostgreSQL 16 + pgvector)]
    Retrieve & LearnServices --> Providers[Text provider adapter]
    Ingest --> Vision[Visual provider adapter]
    Providers & Vision --> Remote[Configured external model API]
```

The backend is a modular monolith, not a microservice or distributed-agent deployment. FastAPI mounts course/source, retrieval, Ask, assessment, mastery, diagnosis, adaptive-learning, preview, visual-evidence and report routers. SQLAlchemy models and Alembic migrations define persistence; migration head is `0007`.

The frontend uses React Router for exactly five principal routes. Workspace manages sources; Ask presents grounded answers; Learn hosts reasoning and adaptive sessions; Practice exposes assessments and diagnostics; Dashboard presents concept/mastery/report data. Shared components render source previews, reasoning, teaching and Learning Trace.

The browser stores a learner UUID and journey references scoped to learner/course. This identifier is not authentication. Course ownership checks provide internal data-scope boundaries, not an authenticated multi-user security model. The development proxy removes `/api`; the API routes themselves do not use that prefix.

**Source:** [frontend routes](../../frontend/src/App.tsx), [API client](../../frontend/src/api/client.ts), [state](../../frontend/src/state.tsx), [Vite config](../../frontend/vite.config.ts), [API entry](../../backend/app/main.py), [models](../../backend/app/models), [migrations](../../backend/alembic/versions).

## 2. Multimodal ingestion and document processing

```mermaid
flowchart TD
    Upload[Workspace upload: PDF / PPTX / MP4] --> Source[Course-owned SourceVersion + original file]
    Source --> Process[Explicit Process request]
    Process --> PDF[PDF: text / tables / embedded images]
    Process --> PPTX[PPTX: text / tables / pictures]
    Process --> MP4[MP4: FFmpeg audio and decoded frames]
    MP4 --> ASR[Local MLX Whisper timestamped transcription]
    PDF & PPTX & MP4 & ASR --> Evidence[EvidenceUnit + modality + typed locator]
    Evidence --> Text[Original text and table content]
    Evidence --> Image[Extracted image or video-frame bytes]
    Image --> Inspect[Optional model interpretation]
    Inspect --> Verify[Separate verification using the same actual image]
    Verify --> Accepted{Accepted?}
    Accepted -->|Yes| Description[Store description; invalidate stale embedding]
    Accepted -->|No or provider failure| NoClaim[No accepted semantic description]
    Text & Description --> Index[Explicit course indexing]
    Index --> Canonical[Canonical searchable text + content hash]
    Canonical --> Embed[Local 384-dimensional text embedding]
    Embed --> DB[(pgvector + lexical searchable evidence)]
    Evidence --> Preview[Page / approximate slide / video timestamp preview]
```

Processing dispatches by source type. PDF uses PyMuPDF/pdfplumber; PPTX uses python-pptx; video uses FFmpeg/FFprobe and the configured local transcription adapter. Originals and derived images are file-backed; evidence metadata, descriptions and vectors reside in the database. There is no general scanned-PDF OCR path and no standalone image/audio upload route claimed here.

Locators preserve page, slide or time provenance. Image extraction does not establish semantic understanding. Only accepted descriptions contribute semantic text; changing a description invalidates its old embedding. Workspace must explicitly re-index afterward. The text embedding provider defaults to `sentence-transformers/all-MiniLM-L6-v2` and validates 384-dimensional outputs; it does not embed raw images or video directly.

Previews resolve files through course/source ownership and contained storage paths. PDF pages render from the original. PPTX previews reconstruct supported content at slide coordinates and can omit complex Office features. Video opens at the referenced timestamp. Original-file access remains available.

**Source:** [source routes](../../backend/app/api/sources.py), [dispatch](../../backend/app/services/source_processing.py), [PDF](../../backend/app/services/pdf_ingestion.py), [PPTX](../../backend/app/services/pptx_ingestion.py), [video](../../backend/app/services/video_ingestion.py), [transcription](../../backend/app/services/transcription.py), [visual interpretation](../../backend/app/services/visual_evidence.py), [indexing](../../backend/app/services/indexing.py), [embeddings](../../backend/app/services/embedding_provider.py), [previews](../../backend/app/services/source_preview.py).

## 3. Retrieval and source-grounded answering

```mermaid
flowchart TD
    Q[Question + course + optional source/modality filters] --> Dense[Embed query; vector similarity candidates]
    Q --> Lexical[PostgreSQL lexical candidates]
    Dense & Lexical --> RRF[Reciprocal rank fusion]
    RRF --> Ground[Validate evidence ownership / readiness / locator]
    Ground --> Boundary{Usable relevant evidence?}
    Boundary -->|No| Decline[Deterministic declined response; no model call]
    Boundary -->|Yes| Context[Bounded supported context + evidence ID allowlist]
    Context --> Model[Configured Ask provider]
    Model --> Parse[Parse structured response]
    Parse --> Check[Validate returned evidence IDs against allowlist]
    Check --> Citations[Server builds citations from stored provenance]
    Citations --> Answer[Answer blocks + inspectable citations]
    Answer --> Viewer[Open exact source location]
    Model -->|Timeout or provider error| Error[Unavailable/error response]
    Parse -->|Invalid content| Error
    Check -->|Unallowed evidence reference| Error
```

Hybrid retrieval merges vector and lexical rankings. The evidence boundary rejects insufficient support before creating a provider. Answer generation receives a bounded context; the model returns evidence IDs, not authoritative filenames or locators. The server validates those IDs and supplies the citation objects.

These structural/provenance safeguards do not mathematically prove that every generated sentence is entailed. Ask does not have the same separate content-verifier stage as assessment generation. Real answer quality and grounding metrics remain pending.

**Source:** [retriever](../../backend/app/services/retriever.py), [citation checks](../../backend/app/services/citation_grounding.py), [evidence boundary](../../backend/app/services/evidence_boundary.py), [Ask orchestration](../../backend/app/services/grounded_ask.py), [SourceViewer](../../frontend/src/components/SourceViewer.tsx).

## 4. Reasoning diagnosis and adaptive learning

```mermaid
flowchart TD
    Attempt[Verified assessment + recorded learner attempt] --> Reasoning[Learner-authored reasoning + frozen course evidence]
    Reasoning --> Diagnosis[Generate and separately verify diagnosis candidate]
    Diagnosis --> Status{Supported outcome}
    Status -->|Hypothesis| Probe[Verified diagnostic probe]
    Probe --> Resolution[Confirmed / rejected / inconclusive]
    Status -->|No clear break| Concept[Eligible single-concept teaching]
    Resolution -->|Confirmed with valid context| Repair[Targeted repair context]
    Resolution -->|Rejected or inconclusive; eligible concept| Concept
    Status -->|Insufficient reasoning or evidence| More[Request more evidence; no forced diagnosis]
    Repair & Concept --> Policy[Deterministic adaptive policy]
    Policy --> Strategy[Select unused strategy within bounded session]
    Strategy --> Content[Generate and verify source-backed teaching or question]
    Content --> Feedback[Learner feedback or graded response]
    Feedback --> Policy
    Policy --> Prereq[Optional stored prerequisite + supporting evidence]
    Prereq --> Content
    Policy --> Transfer[Fresh verified Transfer Check]
    Transfer --> Outcome[Actual attempt / terminal session outcome]
    Outcome --> Trace[Learning Trace: observations, decisions and verification]
```

The system diagnoses reasoning the learner supplies; it does not inspect private model reasoning or infer an enduring learner trait from one wrong answer. Diagnostic probe responses resolve the event-specific hypothesis. Probes do not create mastery gains. Concept-level teaching after an unresolved/rejected diagnosis does not rewrite that diagnosis as confirmed.

The model generates content for a server-selected strategy. It does not control the adaptive policy. Strategies include source explanation, structured visual teaching, worked examples, prerequisite checks/recaps/practice and transfer. Visual teaching is structured steps/timelines/annotations, not image generation. Prerequisite interventions require a real recorded edge and usable evidence. The session prevents strategy repetition and bounds the learning loop; freshness checks and separate verifier prompts guard transfer candidates, but are not proof of pedagogical effectiveness.

**Source:** [diagnosis](../../backend/app/services/reasoning_diagnosis.py), [adaptive policy](../../backend/app/services/adaptive_learning.py), [adaptive schemas](../../backend/app/schemas/adaptive_learning.py), [reasoning component](../../frontend/src/components/Reasoning.tsx), [teaching component](../../frontend/src/components/Teaching.tsx), [trace panel](../../frontend/src/components/TracePanel.tsx).

## 5. Practice, verification and Dashboard updates

```mermaid
flowchart TD
    Request[Practice / Learn / diagnostic request] --> Generate[Source-constrained assessment candidate]
    Generate --> Contract[Validate private grading contract; solve scheduling if applicable]
    Contract --> Verify[Separate assessment verification]
    Verify --> Gate{Verified and fresh?}
    Gate -->|No| Reject[No public question; record safe rejection/error]
    Gate -->|Yes| Question[Public question; private key withheld]
    Question --> Submit[Actual learner response]
    Submit --> MCQ[MCQ: deterministic option comparison]
    Submit --> Numeric[Numerical: exact arithmetic / units / tolerance]
    Submit --> Short[Short answer: source-constrained semantic evaluator]
    MCQ & Numeric & Short --> Attempt[Persist attempt and grading result]
    Attempt --> Eligible{Gradable + mapped to one concept + fresh exposure?}
    Eligible -->|Yes| BKT[Transactional BKT observation and mastery update]
    Eligible -->|No| Skip[No new mastery observation]
    BKT & Skip --> Report[Read-only learner report / observed mastery / Untested concepts]
    Report --> Dashboard[Dashboard]
    Attempt --> Trace[Session trace where applicable]
```

Assessment verification precedes presentation; private answer keys and grading contracts are withheld until submission. MCQ grading compares the selected option. Numerical grading uses exact values with explicit units/tolerance; supported scheduling contracts use the generic solver. Short-answer evaluation may return `cannot_grade`; unsupported or unavailable grading must not award credit or update mastery.

Mastery updates require one unambiguous course concept and no prior exposure to the question. Repeated questions, unmapped/ambiguous questions and ungradable attempts do not manufacture observations. A prior ungradable exposure can also prevent a later response to that same question from contributing new mastery evidence. Teaching itself never calls an observation a correct answer.

BKT updates are persisted with before/after values. The Dashboard report separately summarizes first gradable responses and repeated/ungradable responses; report scores and BKT observations have different eligibility rules. Untested concepts remain untested. The short diagnostic selects a small fresh sample from course concepts and may generate additional verified questions when needed; it is not a validated psychometric instrument.

**Source:** [assessment generation](../../backend/app/services/assessment_generation.py), [grading](../../backend/app/services/assessment_grading.py), [typed assessments](../../backend/app/services/typed_assessment.py), [scheduling](../../backend/app/services/scheduling.py), [mastery updates](../../backend/app/services/mastery_update.py), [BKT](../../backend/app/services/learner_mastery.py), [diagnostic selection](../../backend/app/services/cold_start.py), [report](../../backend/app/services/learner_report.py), [Dashboard](../../frontend/src/views/Dashboard.tsx).

## Model integration and deployment boundary

| Inspected mode | Transport and routing | What remains unverified |
| --- | --- | --- |
| `compatible` (default) | Configured base URL plus `/chat/completions`; text model and optional vision model. Separate verification calls use the same configured provider/model. | Actual gateway completion, schema support and model quality |
| `direct_openai` | Direct Responses adapter; light/standard/deep routing in source. Concise Ask uses light; normal generation uses standard; wired verification uses deep. | Authorized access to the exact source identifiers and successful live generation/verification |

Tier names and settings are documented in the [README draft](README_REVIEW_DRAFT.md#model-api-and-gateway-configuration). They are implementation facts, not claims about public model availability. No private endpoint details or credentials are required to understand the architecture. The older demo helper requires explicit mode isolation; see its caveat in the README draft.

The inspected application has no authentication, external queue, production hosting configuration or successful deployment claim. Local browser/API/database communication and fixture-tested provider adapters must be distinguished from a working external completion and a verified full learning loop.

**Source:** [configuration](../../backend/app/core/config.py), [compatible provider and routing](../../backend/app/services/llm_provider.py), [direct adapter](../../backend/app/services/direct_openai.py), [demo helper](../../demo-course/prepare.py).
