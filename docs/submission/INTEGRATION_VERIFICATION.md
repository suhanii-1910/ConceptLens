# Integrated application verification

**14 October 2026 · Asia/Kolkata · local review, not public release approval.**

Application merge: `16d208cfecf4472f172bc9d496f5fdc89c75d74d` on `feature/final-integration`. Parents: backend/documentation `ac36dd46c0dc6ed31853dcafc14f25cfe7002040` and frontend `6b1a441041c2ca2782c2fe834bb67a5c96c43ab5`; shared baseline `9fe1751b6f7242308739b47135ce0ff2204d98e3`. Remote tips were checked, refs fetched, and an unused integration worktree/branch created before the conflict-free merge. Shared backend commits were not cherry-picked.

Subsequent changes are documentation reconciliation and local-artifact ignore rules. Frontend source/configuration is identical to `6b1a441`; backend application code and migrations are identical to `ac36dd4`. No provider credentials, permanent model defaults, routing, original checkout files or application databases were changed. Nothing on the integration branch has been pushed, merged into main or deployed.

## Actual results

| Check | Result | What it establishes |
| --- | --- | --- |
| Frontend typecheck | Passed | TypeScript contracts compile |
| Frontend ESLint | Passed | Configured lint checks |
| Frontend unit tests | 55 passed / 5 files | jsdom and fixture behavior |
| Production build | Passed; Vite 7.3.7 | Bundle builds; not a deployment |
| Desktop/mobile Playwright | 20 passed in 24.0s | Existing UI suite plus Observatory checks |
| Real-backend browser subset | 4 of those 20 passed | Proxy health HTTP 200, course loading and all five routes against the existing isolated API; no API interception in these cases |
| Ordinary backend suite | 590 passed, 23 skipped, 5361 warnings in 13.47s | SQLite unit/API tests with injected/disabled external providers |
| Opt-in PostgreSQL/migration suite | All 23 passed, 213 warnings in 29.81s | Disposable database/schema persistence, concurrency and migration lifecycle tests; covers the 23 ordinary-suite skips |
| Fresh real-ingestion smoke | Passed | Integrated backend started separately on 8101; actual authored PDF, real cached embeddings, retrieval and source inspection |
| Disposable cleanup | Verified | Created test database dropped and absence checked; temporary API stopped |

Backend warnings include dependency/Python deprecations and synchronous tests marked asyncio; they are not hidden or counted as failures. Tests reused installed dependencies: Node 26.9.0 and Python 3.14.2. A separate copy of frontend dependencies was used; the existing Python environment was reused read-only with bytecode writes disabled and integrated source first on `PYTHONPATH`. This is not a clean dependency installation rehearsal.

Browser tests used an ignored config on port 5175 rather than the occupied default 5174. Two temporary harness startup mistakes (npm initially launched from the repository root; then an ESM config interpreted as CommonJS) were corrected locally before the successful suite. Neither required application changes. Sixteen browser cases check fixture/interface behavior; four check real page/data availability. Generated screenshots remain local, uncommitted review artifacts. They are not evidence of live AI generation.

### Fresh ingestion details

The existing `demo-course/prepare.py --port 8101` helper created a fresh disposable database, migrated it to 0007, started the integrated API, created a course, uploaded/processed a real PDF, and indexed it using cached sentence-transformer weights with `HF_HUB_OFFLINE=1`.

- Nine evidence units; eight searchable/embedded; one skipped for no searchable text.
- Supported retrieval and exact page preview passed.
- Three explicitly curated concepts and one source-backed prerequisite; three Untested concepts and zero learner attempts.
- Raster asset extracted, not semantically interpreted.
- Ask, assessment generation and visual interpretation returned HTTP 503 with providers deliberately unconfigured for this disposable process.
- Cleanup verified database absence. The original application database and existing isolated UI database were not migration/reset targets.

No successful external completion was inferred from these 503 checks.

## AI limitations

The earlier local runtime evidence from 14 October records restored gateway/Tailscale health but no completion for the exact previously working alias within bounded 25- and 45-second requests. Earlier configured-route/Astra requests also timed out. Available forwarding logs did not establish the precise internal failure boundary. That evidence remains unresolved; it was not rerun or promoted to a new failure measurement here.

This integration pass made **no new external model completion requests** and did not switch models. Real generated Ask answers/citations, Learn/Practice generation and verification, semantic grading, diagnosis/probes, adaptive teaching, Transfer Checks and corresponding mastery/Dashboard changes remain unverified. Live vision interpretation, new MP4 transcription and real grounding scores also remain unverified. Fixture grading, policy and mastery tests are separate evidence.

## Run the reviewed application

The integrated frontend is running at **http://127.0.0.1:5175** and uses the existing isolated FastAPI service at **http://127.0.0.1:8001** (API docs: **http://127.0.0.1:8001/docs**). The earlier frontend remains on 5174. Existing services were not stopped or restarted. The running backend has the same application source as the merged backend; the fresh disposable smoke additionally tested backend startup from the integration worktree itself.

On this Mac, if the integrated frontend is stopped, run:

```sh
cd /Users/suhanigarg670/Projects/ConceptLens-integration/frontend
CONCEPTLENS_API_PROXY_TARGET=http://127.0.0.1:8001 npm run dev -- --port 5175
```

Do not start a duplicate while 5175 is occupied. If the existing isolated backend has stopped, its already prepared local launcher is:

```sh
cd /Users/suhanigarg670/Projects/ConceptLens-uiux
./backend/run-uiux.sh
```

That launcher and its private environment are local runtime tools, not part of the published UI commit. Do not copy secrets into frontend settings or point tests at the original application database. For a new clone, use the [canonical setup](../../README.md#install-dependencies-and-configure-the-environment); the local integration ref must first be approved and published.

## Commands and test isolation

Frontend checks ran in `frontend/`: `npm run typecheck && npm run lint && npm test && npm run build`.

Browser command, from `frontend/`, using the local ignored config:

```sh
CONCEPTLENS_LIVE_SMOKE=1 CONCEPTLENS_EXPECT_UNCONFIGURED=0 \
  npm run test:e2e -- --config ../.runtime/playwright.config.ts
```

The ignored config imports the committed Playwright config, changes only the test-server URL/port to 5175, sets the integrated frontend working directory, and writes results beneath `.runtime/`. The existing known integration frontend was reused. The 503 generation check was not enabled against the running configured gateway.

Ordinary backend command, from the integration root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/backend" \
CONCEPTLENS_PROVIDER_MODE=compatible CONCEPTLENS_LLM_BASE_URL='' \
CONCEPTLENS_LLM_API_KEY='' CONCEPTLENS_LLM_MODEL='' CONCEPTLENS_VISION_MODEL='' \
CONCEPTLENS_OPENAI_API_KEY='' OPENAI_API_KEY='' \
CONCEPTLENS_DATABASE_URL='sqlite+aiosqlite:///' CONCEPTLENS_DEBUG=false \
backend/.venv/bin/python -B -m pytest -q backend/tests -o cache_dir=.runtime/pytest-cache
```

For PostgreSQL tests, the existing safe `conceptlens_eval.database.disposable_database` harness created and migrated an outer disposable database, then a local wrapper enabled `CONCEPTLENS_TEST_POSTGRES=1` and `CONCEPTLENS_TEST_MIGRATION_LIFECYCLE=1`, setting `CONCEPTLENS_TEST_POSTGRES_URL` to that disposable URL. It ran `test_mastery_postgres.py`, `test_reasoning_diagnosis_postgres.py`, `test_adaptive_learning_postgres.py` and `test_phase10_postgres.py`. The latter suites create their own disposable databases. Do not enable these flags against a normal application database: the mastery suite creates schemas in its supplied database.

Fresh ingestion command (repository-provided local development admin credentials only):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/backend:$PWD/evaluation" \
CONCEPTLENS_PROVIDER_MODE=compatible CONCEPTLENS_LLM_BASE_URL='' \
CONCEPTLENS_LLM_API_KEY='' CONCEPTLENS_LLM_MODEL='' CONCEPTLENS_VISION_MODEL='' \
CONCEPTLENS_OPENAI_API_KEY='' OPENAI_API_KEY='' CONCEPTLENS_DEBUG=false \
HF_HUB_OFFLINE=1 \
CONCEPTLENS_EVAL_ADMIN_URL='postgresql+asyncpg://conceptlens:conceptlens@127.0.0.1:55432/postgres' \
backend/.venv/bin/python -B demo-course/prepare.py --port 8101
```

## Repository and secret review

A sanitized scan examined **449 distinct text blobs across all locally reachable refs after fetch**, including branch history and local checkpoint/stash refs, for known local provider-key values and common provider-token/private-key/bearer patterns. No known local provider key was found. One token-shaped match was reviewed as a synthetic credential-redaction test fixture in a local checkpoint blob, not an integrated tracked file. No sensitive environment/database/key filenames were found in that history scan.

The scan skipped text inspection of **58 binary blobs** and no oversized blobs. It does not certify screenshots, embedded binary metadata, unrecognized secret formats, remote-only/unreachable objects, licenses or repository visibility. Existing localhost database defaults and documentation placeholders are not production provider secrets. A separate scan of 250 tracked/current text files (including this new report) and all reachable commit messages found no secret-pattern or known-key matches. Documentation validation passed for 99 local links/anchors across 10 Markdown files, balanced fences and Git whitespace checks.

Private `.env`, backups, runtime data, diagnostic tools and generated screenshots are excluded. The ignored dependency symlink and generated review folder remain local. The original checkout's untracked environment backup remains untouched and must never be blanket-staged.

**Public visibility is not yet recommended as an automatic next action.** Complete human publication review of binary assets and remaining submission placeholders, then obtain explicit approval for visibility changes. No credential rotation, history rewriting or visibility change was performed.

## Remaining delivery gates

- Approve the local integration/documentation diff, then push only `feature/final-integration` and open a PR into `main`.
- Resolve the real completion blocker or retain explicit limitations throughout Devpost and the video. Do not call fixture-generated results live AI success.
- Curate real screenshots; record the actual application with honest narration; upload the approved video and test the link.
- Fill confirmed team names/accounts, Devpost URL, YouTube URL and official deadline/timezone. Organizer requirements still need an authoritative event link.
- Review public access/visibility separately. No PR, main merge, deployment or publication was performed by this integration task.
