# ConceptLens demo guide

**Objective:** show how ConceptLens uses learner evidence to choose the next learning action and makes that decision inspectable. The CPU Scheduling story tests whether a learner compares remaining time rather than original burst.

**Acceptance status:** real local ingestion, indexing, source preview and live browser smoke are recorded in [verification.json](verification.json). Real text/vision provider acceptance is **PENDING CONFIGURATION**. This guide is a reproducible rehearsal procedure, not a claim that a live provider journey has already passed.

## Pre-demo checklist

- Install the [root README prerequisites](../../README.md#local-setup), backend dependencies, frontend dependencies and a Playwright browser.
- Start PostgreSQL with `docker compose up -d`. Do not reset, seed or migrate the normal `conceptlens` database for acceptance.
- Confirm the local embedding model is cached or downloadable. This helper uses the real sentence-transformers adapter, never fake embeddings. `HF_HUB_OFFLINE=1` can prevent downloads when the model is already cached.
- Ports 8100 (disposable API) and 5173 (Vite) must be free. The helper fails instead of stopping someone else's server. `--port` changes the API port; update the Vite target accordingly.
- For real generation, export `CONCEPTLENS_LLM_BASE_URL`, `CONCEPTLENS_LLM_API_KEY` and `CONCEPTLENS_LLM_MODEL` securely into the helper's process environment. Add `CONCEPTLENS_VISION_MODEL` for images. The adapter appends `/chat/completions` to the base URL. All credentials stay server-side.
- Independent generator/verifier calls currently share the configured model. A provider must support the required strict JSON responses; vision must accept image content. Do not assume provider compatibility from an endpoint URL alone.
- Use a fresh browser profile or “Reset demo learner” to avoid prior learner references. This changes the local learner UUID; it does not delete evidence.
- Before recording, rehearse once with real providers and inspect the actual citations, verification statuses, grading and trace. Record failures honestly. Do not repeatedly tune prompts against frozen evaluation test outcomes.

## Prepare an isolated course

From the repository root, export the explicit local administration connection. The following credentials are the repository's local Compose defaults:

```sh
export CONCEPTLENS_EVAL_ADMIN_URL='postgresql+asyncpg://conceptlens:conceptlens@127.0.0.1:55432/postgres'
backend/.venv/bin/python demo-course/prepare.py --serve --with-provider
```

For a provider-unconfigured demonstration, omit `--with-provider`. The helper explicitly disables external providers by default, including settings in the application's `.env`. With `--with-provider`, it requires the three text settings exported in the process environment; it never prints their values.

In a second terminal:

```sh
cd frontend
CONCEPTLENS_API_PROXY_TARGET=http://127.0.0.1:8100 npm run dev
```

Open `http://127.0.0.1:5173/workspace` and select **CPU Scheduling — disposable demo**. Keep the helper running throughout the rehearsal. On completion, stop Vite, then Ctrl-C the helper. It stops its backend and deletes its own temporary storage and database. Each invocation starts a new isolated course rather than accumulating duplicates in an existing database. Do not expect demo data to survive shutdown.

### What preparation actually does

[prepare.py](../../demo-course/prepare.py) reuses the evaluation disposable database harness, which accepts only a local `/postgres` admin connection. It generates a random `conceptlens_eval_<32 hex digits>` database, migrates that database to 0007 and starts a local backend with isolated uploads/derived storage. It never accepts an existing application database or arbitrary API target.

The helper generates a four-page PDF from [cpu-scheduling.md](../../demo-course/cpu-scheduling.md):

1. Arrival, burst, execution and remaining time.
2. The general SRTF rule, preemption, ties and prerequisite relationship.
3. Completion, turnaround, waiting and response metrics.
4. An embedded raster diagram of the general decision rule, suitable for actual image-backed interpretation.

It creates a course, uploads the actual PDF and calls the existing process and indexing APIs. The source has neither judge example. Because there is no concept-authoring API, the helper uses the existing ORM only for three curated concepts, their real extracted page evidence, and the explicitly taught Remaining time → SRTF prerequisite. It creates **no assessments, attempts, diagnoses, mastery observations or learning sessions**. Those must come from real product interactions.

The image is initially extracted but not interpreted or semantically indexed. In Workspace, use **Inspect source evidence**, open the page-4 image, then **Interpret and verify visual**. Acceptance requires a real image-backed candidate and a separate image-backed verifier. If accepted, close the viewer and click **Index course material** to include its description. Do not describe a 503 or rejected interpretation as verified vision.

To generate just the PDF for inspection, without database access, run from the root:

```sh
backend/.venv/bin/python - <<'PY'
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('demo', 'demo-course/prepare.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
demo.build_source(Path('/tmp/conceptlens-cpu-scheduling.pdf'))
PY
```

Uploading that PDF manually works through Workspace → Choose file → Process → Index course material. Manual upload alone does not curate concepts or prerequisites; use the isolated helper for the complete demo setup.

## Judge journey and suggested inputs

| Step | Action / suggested input | Evidence to show |
| --- | --- | --- |
| 1. Workspace | Open **Inspect source evidence**; select a text item on page 2. | Actual source page and general SRTF rule; separate original and derived content. |
| 2. Ask | “In SRTF, what should I compare when a new process arrives?” Click **Ask ConceptLens**. | Source-supported answer or honest refusal. Open citation details and **Open exact source**. |
| 3. Learn | Focus: “SRTF: P1 arrives at 0 with burst 8; P2 arrives at 5 with burst 4. Ask which process runs at time 5 and why.” Click **Find me a problem**. | A question only appears after verification. The requested scenario is a prompt, not a guaranteed provider result. |
| 4. Attempt | If that scenario is returned, select the distractor that P2 preempts; click **Record my answer**. | Actual incorrect attempt. If another question is returned, answer and reason about that question instead. |
| 5. Reasoning | “I chose P2 because its burst is 4 and P1's burst is 8, so 4 is shorter.” Click **Debug my reasoning**. | Possible first break should concern original burst versus remaining time if supported. Never paste this reasoning against an unrelated question. |
| 6. Probe | Answer the displayed diagnostic probe as the learner; click **Test the hypothesis**. | Hypothesis/confirmed/rejected/inconclusive are distinct. Do not force confirmation if the probe rejects it. |
| 7. Teach | Use the offered guided-learning action. Inspect cited source explanation. Click **Still confused** when demonstrating that learner state. | A different server-selected strategy, not the same explanation renamed. |
| 8. Prerequisite | If offered, answer **Check this prerequisite**, then choose **60-second recap** or continue. | The authored prerequisite link plus actual learner response. This branch is conditional; do not invent a gap to claim repair. |
| 9. Transfer | Continue through **I understand** and any required practice. Answer the fresh **Transfer Check** with **Verify my understanding**. | The question and verification evidence must be fresh; show actual pass/fail. No answer key before submission. |
| 10. Trace | Click **Why did ConceptLens do this?** | Original attempt, reasoning, hypothesis resolution, strategy changes, transfer and actual mastery update; unverified facts remain unverified. |
| 11. Dashboard | Show the assessment report, concept evidence and Untested concepts. | Observed evidence, not assumed weakness; one response is a small sample. |
| 12. Evaluation | Show the README comparison table and linked historical JSON. | All three policies, efficiency trade-off and the simulation disclaimer. Real RAGAS scores remain pending. |

The desired transfer changes the numbers to **P1(0,9), P2(4,3)**: now 5 remains for P1 and 3 for P2, so P2 preempts. The adaptive engine owns transfer generation; there is no “force these numbers” control. If a verified transfer uses different numbers, show its actual evidence and use the deterministic solver check below to illustrate the reversal separately. A later Practice question is ordinary practice, not the session's persisted Transfer Check.

For the server-owned scheduling proof UI, choose **Numerical** in Practice and request “SRTF completion time of P1 with arrivals/bursts P1 (0,8), P2 (5,4), in ticks.” If the verified question actually asks this, submit `8`. The proof appears after grading. A repeated normalized stem may be rejected for freshness; request a genuinely fresh problem instead of bypassing that rule. The Learn entry form defaults to MCQ; Practice supports typed answers and can pass a recorded attempt into reasoning.

A short-answer rehearsal should use Practice → Short answer: “Why does elapsed waiting time not reduce a process's remaining CPU time?” Check a supported answer and an incorrect answer with fresh verified questions. A malformed/unavailable semantic evaluation must produce **cannot grade**, not a mastery increase.

## Deterministic scheduler acceptance

Run the existing generic solver tests:

```sh
backend/.venv/bin/pytest -q backend/tests/test_phase10_scheduling.py
```

For reviewable output with both cases, from the repository root:

```sh
PYTHONPATH=backend backend/.venv/bin/python - <<'PY'
from app.schemas.scheduling import SchedulingInput
from app.services.scheduling import solve
for burst, arrival, newcomer in [(8, 5, 4), (9, 4, 3)]:
    result = solve(SchedulingInput(algorithm='srtf', processes=[
        dict(pid='P1', arrival=0, burst=burst),
        dict(pid='P2', arrival=arrival, burst=newcomer)]))
    print(result['segments'])
    print(result['decisions'])
PY
```

Expected A: P1 0–8, P2 8–12; at t=5, P1 continues with 3 remaining. Expected B: P1 0–4, P2 4–7, P1 7–12; at t=4, P2 preempts. No production special case or fake diagnosis is involved. Solver correctness alone does not establish diagnosis quality.

## Safe live smoke and provider acceptance

The following starts and cleans up the actual isolated backend and Vite/browser processes:

```sh
CONCEPTLENS_EVAL_ADMIN_URL='postgresql+asyncpg://conceptlens:conceptlens@127.0.0.1:55432/postgres' \
  backend/.venv/bin/python demo-course/prepare.py --browser-smoke
```

Without providers it checks real source ingestion, local embeddings, supported retrieval, page rendering, API 503 boundaries, and both desktop/mobile five-view smoke paths. This is not a real-provider learning acceptance test. `--with-provider` enables providers but does not by itself exercise or certify a complete generated learning loop; use the manual journey above and record each actual outcome.

For real provider acceptance later, retain a small local record of the actual provider/model identity (never credentials), course/learner/question/session IDs, result statuses and trace from the isolated run before teardown. Mark each of Ask, generator, verifier, short-answer grader, diagnosis, adaptive teaching, transfer, mastery and vision as passed/failed/pending based on observed results. Do not infer a downstream pass from an upstream success. Keep costs bounded to one rehearsal; refusal/rejection is a recorded result, not permission to bypass verification.

Real framework grounding is a separate measurement. Follow [evaluator configuration](../../evaluation/README.md#configure-and-execute-a-real-grounding-run), including its locked framework environment and evaluator embedding model, then write fresh outputs outside historical reports:

```sh
PYTHONPATH=evaluation:backend backend/.venv/bin/python -m conceptlens_eval grounding --split test --out /tmp/conceptlens-grounding-real.json
PYTHONPATH=evaluation:backend backend/.venv/bin/python -m conceptlens_eval report --grounding /tmp/conceptlens-grounding-real.json --simulation evaluation/reports/post-phase10-simulation.json --out /tmp/conceptlens-real-report
```

## Honest fallback and recovery

If providers are unavailable, show the real source, exact page viewer, indexed evidence and generic scheduler output. Explain that generated diagnosis/teaching/vision acceptance remains pending. The fixture browser journey can illustrate the intended UI only if explicitly labeled **API FIXTURE — NOT LIVE AI ACCEPTANCE** in the presentation; do not imply fixture screenshots are a recorded learner or real provider output.

The fixture journey is reproducible with `cd frontend && npm run test:e2e`. Its screenshots are in ignored `frontend/test-results/` folders and include desktop/mobile states. It is a test harness, not a production demo mode or seeded live course.

If indexing fails, check model availability and storage permissions; do not substitute mock embeddings. If generation fails, inspect configuration and evidence/refusal state without exposing provider secrets. If a session reaches a bounded stop, show its reason; do not replay old content as fresh transfer. If a terminal is forcibly killed, cleanup cannot be guaranteed: inspect the exact generated database name printed by that invocation and its owned processes. Never blanket-drop a prefix or kill unrelated servers.

## Screenshot checklist and talking points

Capture a source with its locator, Ask with its citation open, a tentative reasoning break and diagnostic probe, a changed strategy, a conditional prerequisite choice, fresh transfer feedback, expanded Learning Trace, and Dashboard with both observed and Untested concepts. Include a desktop view and one narrow/mobile view. A separate evaluation screenshot must retain all three baselines and the simulation label. Use the captions in [submission.md](submission.md); label fixture captures visibly if used.

Say: “The unit of personalization is the next action.” “A misconception starts as a hypothesis.” “A citation opens the source.” “Mastery changes when eligible evidence changes.” “The numbers reverse the scheduling decision, so transfer tests the rule rather than memorization.”

Do not claim real student learning gains, statistical superiority, production deployment, full Office rendering, general OCR, verified vision from extraction alone, or completed provider acceptance without its actual record.
