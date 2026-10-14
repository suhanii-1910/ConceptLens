# ConceptLens

**Learn anything. Debug your understanding.**

> Submission update · 14 October 2026. The integrated application successfully demonstrated a source-grounded, adaptive-learning journey using direct OpenAI. The historical compatible-gateway timeout remains a separate limitation. This is a local prototype, not a production deployment or a real-student learning study.

## Inspiration: an answer is not proof of understanding

A student can read a correct explanation and still carry the same misconception into the next problem. Conventional AI answers often end at fluency: they explain a topic, summarize a document or return a plausible solution. They rarely establish which step in the student's own reasoning needs attention, or whether the student can apply the rule in a new situation.

We built ConceptLens around a different question: **what should the learner do next, and what evidence justifies that choice?**

## What we built

ConceptLens is a local adaptive-learning prototype that connects course materials, source-grounded answers, assessed responses, learner-authored reasoning and guided learning. Its five modules form one learning journey:

| Module | Purpose |
| --- | --- |
| **Workspace** | Create a course; upload, process and index PDF, PPTX and MP4 study materials; inspect extracted evidence and its source location. |
| **Ask** | Ask a question against course evidence and open the page, slide or video timestamp behind a citation. |
| **Learn** | Explain an assessed answer, investigate a possible reasoning break, and follow source-backed teaching with a fresh Transfer Check. |
| **Practice** | Work with verified multiple-choice, short-answer and numerical questions, or a short course diagnostic. |
| **Dashboard** | Inspect observed mastery, assessment history summaries, concept evidence and recorded prerequisite relationships. Untested concepts remain explicitly untested. |

## How it works

First, ConceptLens preserves where information came from. Documents become evidence units with course ownership and page, slide or timestamp provenance. Local text embeddings and PostgreSQL lexical search are combined for retrieval. Before generation, the backend checks whether retrieved evidence is usable and relevant; insufficient evidence produces a refusal. Returned evidence identifiers are checked against the allowed context and converted into server-built citations.

Next, the learning pipeline separates answers from understanding. Generated assessment candidates must pass a separate verification call before being offered. Answer keys stay on the server until submission. Multiple-choice and numerical answers use deterministic grading; short answers use a source-constrained evaluator that can return **cannot grade**.

The Reasoning Debugger combines an actual attempt, the learner's written explanation and course evidence. A possible first reasoning break is a hypothesis, not a permanent label. A diagnostic probe can confirm it, reject it or leave it unresolved. Where a verified attempt has an unambiguous concept, the system can also offer concept-level teaching without declaring the hypothesis true.

A deterministic adaptive policy selects teaching strategies and uses learner feedback to advance. It can offer source explanations, structured visual explanations, worked examples and evidence-backed prerequisite support. A fresh Transfer Check tests the same rule in a different problem. Eligible graded attempts update Bayesian Knowledge Tracing estimates; merely reading an explanation does not increase mastery. The Learning Trace exposes the evidence behind the session's decisions.

The core journey has automated coverage and was exercised in one live, operator-run demonstration using direct OpenAI. The diagnosis completed but did not identify a verified misconception; the system continued with evidence-grounded concept teaching instead. Broader reliability and student outcomes remain unverified.

## Multimodal capabilities

The implemented ingestion pipeline handles PDF text, tables and embedded images; PPTX text, tables and pictures; and MP4 audio transcription with representative decoded frames. Evidence retains its original location. Video transcription uses local MLX Whisper on supported Apple Silicon macOS; frames are extracted with FFmpeg. This is not an end-to-end raw-video reasoning model.

Extracted images can be sent to a configured vision provider and then checked with a separate image-backed verification call. Accepted descriptions become searchable after explicit re-indexing. Extraction alone is not visual understanding: live vision interpretation and its quality remain pending verification. General scanned-document OCR, handwritten learner reasoning and standalone audio/image upload are not implemented submission claims.

## Built with

React, TypeScript, Vite, React Router and Lucide form the browser application. FastAPI, Pydantic, SQLAlchemy and Alembic provide the API and persistence layer. PostgreSQL 16 with pgvector stores learning records and searchable evidence; sentence-transformers supplies local embeddings. PyMuPDF, pdfplumber, python-pptx and FFmpeg support source processing.

The inspected backend supports an OpenAI-compatible completion gateway and a newer direct Responses API adapter. Configuration determines which path is used. The direct OpenAI route subsequently completed real model requests and the demonstrated learning journey. This does not establish successful completion through the older compatible gateway. The final submission must identify the route actually used in its recording.

## What makes ConceptLens distinctive

Retrieval is the starting point of the learning loop. ConceptLens carries evidence through assessment, reasoning diagnosis, strategy selection and understanding verification. It distinguishes a wrong answer from a supported diagnosis, a teaching interaction from a mastery observation, and an untested topic from a weakness.

The CPU Scheduling showcase illustrates the difference. Under shortest remaining time first, the learner must compare remaining execution time rather than original burst time. The backend includes a generic deterministic scheduling solver that checks supported numerical questions and exposes its proof after grading. The intended transfer task changes the situation so the correct scheduling decision may reverse; it is meant to test the rule rather than memorization. The CPU Scheduling transfer scenario remains a distinct showcase; the successfully demonstrated live Transfer Check instead used quadratic time complexity from an uploaded MIT lecture.

## Challenges and lessons

**Preserving provenance across formats.** A citation is useful only if a learner can inspect its source. PDF page previews, approximate PPTX rendering and timestamped video playback each require different handling. Office rendering remains limited, and the original file stays available.

**Avoiding circular verification.** A generator's assertion is insufficient evidence of correctness. Separate verification calls, server-owned citation metadata, hidden grading contracts and deterministic arithmetic strengthen the pipeline, but model verification is not a guarantee of truth.

**Handling uncertainty honestly.** Provider failures must remain failures; they cannot become correct answers, confirmed diagnoses or artificial mastery gains. Earlier gateway completion tests reportedly timed out even when network and gateway health checks were reachable. A reachable endpoint does not prove that a model workflow works.

**Keeping progress interpretable.** Repeated questions, unsupported concept mappings and ungradable responses must not inflate learning evidence. The resulting mastery estimates remain provisional, especially with few attempts and uncalibrated parameters.

## Verified accomplishments

### Live adaptive-learning walkthrough — 14 October 2026

Supporting evidence: [Live walkthrough record](LIVE_WALKTHROUGH_2026-10-14.md) and [application screenshots](../assets/screenshots/).

Using a real uploaded MIT algorithms lecture, the team demonstrated the following sequence in the running application:

1. **Source-grounded Ask:** The application answered a question about quadratic complexity and cited the lecture at 00:27–00:32.
2. **Verified assessment:** A generated question tested how work proportional to n² changes when input size triples. A deliberately incorrect learner response of 3 was recorded; the verified answer was 9.
3. **Reasoning analysis:** The learner's written explanation was processed. The result was **no clear reasoning break found**, so no specific misconception was claimed.
4. **Adaptive teaching:** ConceptLens selected a source-grounded, step-by-step explanation instead of asserting an unsupported diagnosis.
5. **Fresh Transfer Check:** A new problem asked for the maximum number of input points under a 225-operation limit. The answer, 15, passed verification.
6. **Mastery evidence:** The application reported provisional Bayesian Knowledge Tracing estimates of 13% after one observation and 46% after two verified observations.

This was an operator-run demonstration with a simulated learner, not evidence from a real-student study. The observed mastery change is a model estimate, not a measured educational improvement. This single demonstration does not establish a confirmed misconception-detection case or broad educational effectiveness.

The direct OpenAI adapter required a correction to the JSON request format; the fix was separately tested and committed as `d0da5f9`.

The integrated checkout passed **590 ordinary backend tests**, plus all **23 PostgreSQL/migration tests** in separate disposable databases, **55 frontend unit tests** and **20 desktop/mobile browser tests**. Frontend typecheck, lint and production build passed. Four browser cases exercised the real isolated backend for all-five-route page/data checks; the remaining cases validate UI behavior with fixtures or interface assertions. These are software checks, not measurements of teaching quality.

A fresh disposable API run verified real PDF processing, eight cached-model embeddings from nine evidence units, supported retrieval, an exact-page preview, three explicitly curated concepts and one prerequisite. It created no learner attempts. Ask, assessment generation and visual interpretation correctly returned 503 with providers deliberately unconfigured for that test process. This does not establish that the existing gateway can complete a model request. Disposable database cleanup was verified.

The follow-up publication audit and clean-install checks also passed: fresh npm/pip installs, frontend build, dependency consistency and a disposable backend smoke. The three publishable evaluation binaries were reviewed without confirmed sensitive content. Installation was checked on Apple Silicon macOS using existing PostgreSQL and cached model weights, not a new Docker/model download or cross-platform matrix. These results do not clear the unresolved OmniRoute completion blocker.

See [integration verification details](INTEGRATION_VERIFICATION.md) for dates, scope and pending gates, and the [README AI coding-assistant disclosure](../../README.md#ai-coding-assistant-disclosure) for OpenAI Codex assistance and its scope. The later direct OpenAI walkthrough demonstrated one successful learning workflow. No real-student learning improvements, production-scale performance or broad model reliability are claimed.

## Limitations and next steps

The direct OpenAI path now supports the recorded learning walkthrough following a JSON request-format fix. The historical compatible-gateway completion issue remains unresolved, and final video recording is still pending. Real grounding evaluation and vision quality remain pending. Existing personalization simulations are engineering experiments, not student studies or evidence of superiority.

Concept/evidence mappings and prerequisites currently require curation. PPTX previews approximate some layouts, scanned-PDF OCR is absent, and the prototype has no authentication or production deployment. Future development should improve source authoring and format coverage, calibrate mastery with appropriate evidence, and evaluate educational outcomes with real learners before making impact claims.

**Repository:** https://github.com/suhanii-1910/ConceptLens — confirmed public on 14 October 2026.

**Demo:** `YOUTUBE_URL_PENDING`

**Team:** Priyanshu Pandey (`@GODLIKEyp`) and Suhani Garg (`@suhanigarg5670`). Both are registered project teammates.

Before pasting into Devpost, replace placeholders and replace the relative verification link with the final public repository link to `docs/submission/INTEGRATION_VERIFICATION.md`.
