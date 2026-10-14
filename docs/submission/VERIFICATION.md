# ConceptLens verification record

**Documentation review: 14 October 2026 (Asia/Kolkata).** Inspected HEAD: `9fe1751b6f7242308739b47135ce0ff2204d98e3`, branch `feature/direct-openai-router`. This is not a verification record for Suhani's unavailable `feature/uiux-observatory-fieldnotes` worktree.

## Evidence categories

- **Verified this review:** commands executed against the accessible checkout and their observed outcomes.
- **Historical recorded pass:** results read from checked-in records; not rerun or promoted to current integrated-build acceptance.
- **Implemented / fixture-tested:** code and automated contracts exist; real model behavior is not established.
- **User-reported:** supplied in the task, without an accessible raw record.
- **Pending / blocked:** missing evidence, unexecuted checks or an execution prerequisite that prevented completion.

## Repository and review scope

The remote matches the requested GitHub URL. Git status began clean; one worktree was listed. Local refs do not include the Observatory branch. Recent commits add direct-provider routing, concise Ask routing, test-provider isolation and transcription timestamp handling. These postdate the Phase 11 report. The inspected frontend still has the earlier five-view sidebar; no Observatory identity was established.

Read-only `git ls-remote --heads origin feature/uiux-observatory-fieldnotes feature/direct-openai-router main` failed because the shell could not resolve `github.com`. An unauthenticated web request to the [repository URL](https://github.com/suhanii-1910/ConceptLens) returned 404. Current remote state/public accessibility remain pending, not confirmed private or absent.

Reviewed evidence includes the existing root/frontend READMEs, manifests, safe environment templates, API and service source, frontend routes/components, backend and browser tests, [Phase 10 implementation](../phase10/implementation.md), [Phase 10 verification](../phase10/verification.json), [Phase 11 demo guide](../phase11/demo-guide.md), [Phase 11 verification](../phase11/verification.json) and [evaluation methodology](../../evaluation/README.md). The private `.env` contents were not read for documentation.

## Current command results

Existing installed environments were used: Node 24.13.0 and backend Python 3.12.14. Dependency installation was not rerun. System `python3` reported 3.9.6, so the reviewed setup explicitly calls for Python 3.12+.

| Check | Observed result | Scope |
| --- | --- | --- |
| Backend `pytest -q backend/tests` with settings below | **590 passed, 23 skipped, 50 warnings in 21.33s**; exit 0 | Ordinary unit/API suite, including injected transport/routing checks; SQLite and test embedding/retrieval paths |
| Frontend `npm test` | **4 test files passed; 52 tests passed**; exit 0 | Vitest/jsdom, fixture scenarios |
| Frontend `npm run typecheck` | Passed, exit 0 | TypeScript validation |
| Frontend `npm run lint` | Passed, exit 0 | ESLint |
| Frontend `npm run build` | Passed, exit 0; Vite reported **2.14s** | Production bundle generation, not deployment or a performance benchmark |
| `CI=1 npm run test:e2e`, restricted environment | Blocked at server startup: `listen EPERM` on `127.0.0.1:5173` | No browser cases executed |
| Same browser command with localhost permission | Blocked: `http://127.0.0.1:5173 is already used` | No browser cases executed; existing server left untouched |

The 23 backend skips include opt-in database/migration coverage. The suite's pass does not establish fresh PostgreSQL persistence or live-provider acceptance. Warnings remain, including an asyncio mark on a synchronous test and dependency deprecations.

Exact current backend invocation, from the repository root (output redirected locally during review):

```sh
CONCEPTLENS_PROVIDER_MODE=compatible \
CONCEPTLENS_LLM_BASE_URL='' CONCEPTLENS_LLM_API_KEY='' CONCEPTLENS_LLM_MODEL='' \
CONCEPTLENS_VISION_MODEL='' CONCEPTLENS_OPENAI_API_KEY='' OPENAI_API_KEY='' \
CONCEPTLENS_DATABASE_URL='sqlite+aiosqlite:///' \
backend/.venv/bin/pytest -q backend/tests
```

Frontend checks ran in `frontend/`: `npm test && npm run typecheck && npm run lint && npm run build`. No new tests, functional code changes, migrations, provider calls, database resets or deployment were required for this documentation review.

Documentation validation checked all seven Markdown files and 82 local links/anchors, balanced code fences, trailing whitespace and common credential patterns. No findings remained. Mermaid diagrams were source-reviewed, not rendered by an automated diagram validator. The root README was byte-compared with HEAD, and no tracked application files changed. Only the new submission-document directory was added; no commit, push or merge was performed.

## Historical recorded results — not current reruns

The [Phase 11 JSON](../phase11/verification.json) records timestamp `2026-10-07T16:48:05.762414+00:00`, base `37ef33dace275cc3e92d8e1296b9c8a42972ba96`, branch `feature/final-polish`, and then-uncommitted implementation. Its own provenance is preserved; the record timestamp is not the current review date or a certificate for later commits.

| Historical check | Exact recorded result | Interpretation |
| --- | --- | --- |
| Backend suite | `560 passed, 23 skipped, 5091 warnings` | Earlier ordinary suite |
| Focused demo/scheduler tests | `40 passed, 366 warnings` | Earlier focused acceptance |
| Evaluation suite | `80 passed, 141 warnings` | Includes locked-framework positive/negative fixtures; not real model scores |
| Frontend unit tests | `52 passed (52)` | Earlier frontend fixtures |
| Typecheck / lint | `passed; exit 0` each | Earlier source checks |
| Frontend build | `built in 1.13s` | Historical build time, not a benchmark |
| Fixture Playwright | `8 passed (9.4s)`; 2 opt-in cases skipped | Desktop/mobile mocked API journeys |
| Separately executed live-backend browser smoke | `2 passed (4.3s)` | Real local backend and ingestion; providers unconfigured |

The live-backend record explicitly labels itself **DISPOSABLE DEMO ACCEPTANCE — NOT MODEL QUALITY**. It records:

- Disposable database migration to `0007`, course creation and actual PDF upload/processing.
- **9 evidence units; 8 searchable; 8 embedded; 1 skipped for no text.** Embeddings used the real cached local sentence-transformers adapter, with fake flags removed.
- Supported retrieval and a passing exact-page preview.
- **3 curated concepts, 1 source-backed prerequisite, 3 untested concepts and 0 learner attempts.** This demonstrates authored concept metadata, not automatic concept discovery or student mastery.
- A visual asset extracted but **not interpreted**.
- Ask, assessment and visual interpretation returning **503** with providers unconfigured.
- Disposable cleanup and database absence verification.

The live browser test definition in [acceptance.spec.ts](../../frontend/e2e/acceptance.spec.ts) checks the proxy and all five views. Together with the helper report, this supports historical course loading, React/FastAPI connectivity, source inspection and concept relationships. It does not prove the latest Observatory integration or an AI-generated answer.

Phase 10 also records earlier persistence/fixture coverage. Those artifacts are historical and were not rewritten or summed with current results. Do not combine overlapping suites into a unique-test total.

## Workflow status matrix

| Capability | Source/test evidence | Live or final-build status |
| --- | --- | --- |
| Frontend build/lint/typecheck | Passed this review | Observatory build remains unverified |
| Unit/API behavior | Current backend/frontend suites passed | Provider I/O is injected or disabled |
| Browser journeys | Historical 8 fixture + 2 real-backend cases | Current rerun blocked by occupied port |
| Course creation/loading | Course/API tests; historical helper/browser record | Passed historically; final frontend pending |
| PDF ingestion and local embeddings | Historical real-adapter run with counts above | Passed historically; not rerun now |
| Source previews / concept relationships | Historical exact-page preview and curated prerequisite | Passed historically; no automatic graph-discovery claim |
| React/FastAPI connectivity | Historical proxy/all-five-views smoke | Passed historically; final integration pending |
| PPTX/video extraction | Source and automated coverage exist | No new live transcription/multimodal acceptance collected here |
| Model-generated Ask answer | Source and fixture/routing tests | **Pending**; no newer reliable completion evidence found |
| Generated assessments and separate verifier | Source and fixture tests | **Pending** real candidate plus accepted verification |
| Adaptive reasoning diagnosis and probe | Source and fixtures | **Pending** real attempt/reasoning/probe journey |
| Adaptive teaching / strategy change | Deterministic policy and fixtures | **Pending** real verified content and transitions |
| Live grading | Deterministic MCQ/numerical and fixture semantic coverage | **Pending** real generated-item grading; semantic evaluator unverified live |
| Transfer Checks | Freshness and transition fixtures | **Pending** actual verified fresh item, response and outcome |
| Mastery updates | BKT/eligibility tests; historical persistence suites | **Pending** observation tied to a real current provider journey |
| Visual interpretation / verification | Actual-image adapter and fixture coverage | **Pending** accepted live result; extraction is insufficient |
| Real grounding scores / learning gains | Evaluation infrastructure and simulations | **Pending** real grounding; no real-student outcome claim |

## Gateway failure and evidence needed to change status

The user reports previous completion requests timing out despite reachable Tailscale and OmniRoute health endpoints. The underlying runtime report was not present in the inspected repository. Treat this as **user-reported blocked completion**, not a fresh timed test or a pass. Private network details are intentionally excluded.

The newer direct-provider code does not itself supersede that failure. Its unit tests check transport, parsing, tiers and error handling using injected responses. A successful health request, configured key, green unit suite or generated-looking fixture cannot establish a working model completion.

For the final integrated commit, retain a sanitized record with: date/timezone; full commit and dirty status; provider mode and nonsecret model identity; environment versions; actual commands; source provenance; each requested operation's response/status; and course/question/attempt/session references where safe. For mastery, show the eligible attempt and actual persisted observation. For transfer, show a fresh verified question and its outcome. For vision, show the actual image and accepted verification, then re-indexing. Record each downstream gate separately; do not infer a pass from an upstream success.

Do not publish authorization headers, `.env`, request dumps containing secrets, private gateway addresses or management tokens. Do not label fixture data as runtime evidence.

## Reproducibility gaps and release review

- Obtain Suhani's exact Observatory source and its integration diff; rerun build/lint/unit/browser checks there.
- Rehearse setup from the final public ref, including dependency installation, migration on an intended local database, cached/downloaded models and authorized provider access. This review checked commands against source but did not perform a clean install.
- Fix documentation against the final routing mode. The old demo helper clears only compatible settings; explicitly force compatible mode for an unconfigured rehearsal. See the [README caveat](README_REVIEW_DRAFT.md#try-the-application).
- Obtain real screenshots, full team names/accounts, public repository confirmation, final links and official deadline.
- Preserve failures and pending outcomes alongside passes. Submission readiness is not established by this draft alone.
