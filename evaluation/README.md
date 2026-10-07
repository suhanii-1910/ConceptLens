# ConceptLens Phase 9 evaluation

> Phase 10 compatibility note: current disposable evaluation databases migrate to **0007** for the updated ORM. The Phase 9 benchmark inputs and simulation policy adapter remain frozen. See [Phase 10 acceptance notes](../docs/phase10/implementation.md) and the separate pre/post simulation artifacts; historical Phase 9 results below remain unchanged.

Phase 9 measures grounding and compares three tutoring policies under an explicit simulator. It adds no product features, changes no backend/frontend dependencies or behavior, and uses no migrations beyond **0006**.

Start with [the judge report](reports/judge/report.md), [run verification](reports/verification.json), and [Phase 10 handoff](reports/judge/phase10-handoff.json).

**REAL FRAMEWORK RESULTS: PENDING PROVIDER CONFIGURATION.** No generator/evaluator provider was configured for this implementation. The checked-in grounding report contains 12 pending test cases and **no grounding scores**. Null values are not zeros. The simulation is executable and its results are **SIMULATED PERSONALIZATION RESULT**, not real student learning gains. RAGAS fixture scores appear only in tests, never in the judge report.

## Run from the repository root

The core evaluator uses the existing backend environment (Python 3.14.2 was tested), its Pydantic/SQLAlchemy dependencies, and the standard library. It is deliberately not an application dependency.

```sh
export PYTHONPATH="$PWD/evaluation:$PWD/backend"
backend/.venv/bin/python -m conceptlens_eval validate-dataset
backend/.venv/bin/python -m conceptlens_eval grounding
backend/.venv/bin/python -m conceptlens_eval simulate
backend/.venv/bin/python -m conceptlens_eval report
backend/.venv/bin/pytest -q evaluation/tests
```

`grounding` safely emits a pending report without creating a database if the generator is unavailable. `simulate` requires no network or database. Defaults write to `evaluation/reports/`; every command that writes results accepts `--out`. `validate-dataset` and `grounding` accept `--manifest`; grounding also accepts `--split development|test`. `simulate` accepts `--config` and `--bank`. `report` accepts explicit `--grounding` and `--simulation` JSON paths.

### Isolated framework environment

[RAGAS 0.4.3](https://pypi.org/project/ragas/0.4.3/) is the preferred recognized grounding framework and its four modern metric classes run under Python 3.14 in a **separate environment**. No changes to `backend/pyproject.toml` or the backend environment were required.

```sh
uv venv --python backend/.venv/bin/python evaluation/.venv-framework
uv pip sync --python evaluation/.venv-framework/bin/python evaluation/requirements-framework.lock
```

The lock pins the complete resolved environment, including `ragas==0.4.3` and `langchain-community==0.4.1`. Community 0.4.2 removes `chat_models.vertexai`, which RAGAS 0.4.3 imports, so installing only `ragas==0.4.3` is insufficient. The lock was resolved on macOS ARM/Python 3.14; other platforms may need compatible wheels or build tools (notably scikit-network). Do not solve compatibility issues by changing production dependencies.

`framework.py` sends a JSON sample to `framework_worker.py` under that interpreter. The worker uses actual `ragas.metrics.collections` implementations:

| Report name | RAGAS class | Inputs |
| --- | --- | --- |
| faithfulness | `Faithfulness` | query, answer, answer contexts |
| answer_relevancy | `AnswerRelevancy` | query, answer; evaluator embeddings |
| context_precision | `ContextPrecisionWithReference` | query, reference answer, answer contexts |
| context_recall | `ContextRecall` | query, reference answer, answer contexts |

The framework supplies the scoring algorithms. Per-metric implementation name, value and raw structured evaluator judgments are retained. Metrics that error or return nonfinite values are null with explicit status. Each aggregate has its own scored N. Unsupported/refused/error cases are not assigned fabricated framework values: these metrics are conditional on supported, answered, evaluable cases; refusal metrics and execution counts expose the excluded cases.

Fixture tests supply deterministic structured judgments through an actual `InstructorBaseRagasLLM` and `BaseRagasEmbedding`. They execute the genuine metric classes for both all-positive and all-negative judgments. Their outputs are labeled **TEST FIXTURE — NOT A SUBMISSION RESULT**. The real grounding CLI has no fixture switch. RAGAS telemetry is disabled.

### Configure and execute a real grounding run

Configure the existing generator using the existing `CONCEPTLENS_LLM_BASE_URL`, `CONCEPTLENS_LLM_API_KEY`, and `CONCEPTLENS_LLM_MODEL` settings. These can use the project's normal untracked `.env` or process environment.

Export these evaluator variables in the process environment (do not add unknown evaluation settings to the production `.env` schema):

| Variable | Requirement |
| --- | --- |
| `CONCEPTLENS_EVAL_BASE_URL` | OpenAI-compatible evaluator endpoint; falls back to generator base URL |
| `CONCEPTLENS_EVAL_API_KEY` | Evaluator key; falls back to generator key |
| `CONCEPTLENS_EVAL_MODEL` | Evaluator model supporting Instructor structured output; falls back to generator model |
| `CONCEPTLENS_EVAL_EMBEDDING_MODEL` | Required explicit evaluator embedding model supported by that endpoint; no silent default |
| `CONCEPTLENS_EVAL_ADMIN_URL` | Explicit **local** PostgreSQL administration connection whose database is `postgres` |

Credentials are never written to artifacts or command arguments by the harness. Provider exception text is redacted. Model names and configuration availability are recorded. The evaluator may be a separate model from the generator; both use configured endpoints. Real model responses need not be bitwise deterministic.

With those variables configured, the **one command** to execute the real frozen test benchmark is:

```sh
PYTHONPATH=evaluation:backend backend/.venv/bin/python -m conceptlens_eval grounding --split test --out evaluation/reports/grounding.json
```

Then regenerate the report:

```sh
PYTHONPATH=evaluation:backend backend/.venv/bin/python -m conceptlens_eval report
```

Actual ingestion runs on the original PDF/PPTX/MP4 assets, then the production embedding/indexing service, hybrid retrieval, citation grounding, evidence boundary and `execute_grounded_ask` run. This needs the normal local embedding/ASR model availability and FFmpeg, in addition to the generator. On this Mac, video ingestion uses the existing MLX Whisper provider. No authored transcript is substituted for ASR. `video-script.json` documents the original narration and measured clip spans, and is never supplied to retrieval or generation.

The runner captures the same grounded retrieval objects consumed by each Ask call; it does not run a second independent retrieval. It records original text/descriptions, retrieval ranks/distances, stable source/hash, runtime evidence IDs, locators, boundary, answer/refusal, returned citations, latency and framework raw data. Framework context is the same relevance-qualified, bounded context used by Ask. References go only to evaluator metrics, never to the answer generator. Ask creates no assessment/mastery history; the runner verifies those tables remain empty.

## Disposable database boundary

Simulation uses Python memory and files only. Grounding accepts **no existing evaluation or normal development database URL**. The administration URL must explicitly name `/postgres` on localhost, 127.0.0.1 or ::1, with no query options. It is never derived from `settings.database_url`.

The context manager creates a random `conceptlens_eval_<32 hex digits>` database, passes only that URL to Alembic, upgrades specifically to `0006`, seeds/evaluates, disposes connections, and drops it in `finally`. The drop guard accepts only the exact generated namespace; database absence is checked afterward. Extraction artifacts live in a temporary directory. The normal development database is never connected to, reset, or seeded. No migration 0007 exists.

After exporting the administration URL, verify both successful and failed-work cleanup:

```sh
PYTHONPATH=evaluation:backend backend/.venv/bin/python -m conceptlens_eval db-check
CONCEPTLENS_EVAL_ADMIN_URL="$CONCEPTLENS_EVAL_ADMIN_URL" PYTHONPATH=evaluation:backend backend/.venv/bin/pytest -q evaluation/tests
```

The checked-in `database-check.json` records both successful lifecycle runs. A separate end-to-end test also runs actual PDF/PPTX/MP4 extraction (including FFmpeg), indexing SQL, hybrid retrieval and Ask with deterministic test-only transcription/embedding/generator I/O; it verifies that assessment and mastery tables remain empty. That fixture does not produce benchmark scores. These are **test fixtures**, not benchmark performance. A process kill or host failure can bypass Python `finally`; inspect the uniquely named database in that exceptional situation. The tool does not scan/drop unrelated databases.

## Frozen grounding dataset

`datasets/grounding.json`, version **aster-memory-1.0.0**, contains **18 original authored cases**: six development and twelve test. Each of text, table/numerical, video, cross-source, unsupported and figure/diagram has one development and two test cases. The three source files are a four-page PDF, two-slide PPTX and 58.4-second narrated MP4. This avoids the heavily used CPU scheduling demo, but remains a small diagnostic benchmark, not a representative educational study.

The manifest contains stable case/source IDs, source filename, contained relative path, SHA-256, source type, split, modality, support label, exact typed locators, topic, reference answer, required facts and notes. Permanent references contain no database UUIDs. Filename plus content hash must resolve to exactly one runtime source. Validation rejects duplicates/ambiguous filenames, escaping or changed assets, unknown references, invalid modalities, nonpositive pages/slides, malformed/nonfinite intervals, missing expected support, inconsistent types, and unsupported cases with fabricated expected citations.

Example source location:

```json
{"source_id":"memory","locator":{"kind":"page","number":2}}
```

A video locator uses `{"kind":"time","start":19.8,"end":40.0}`; equal start/end represents a point. All pages/slides are one-based. Null/default fields are accepted by the schema but cannot contradict the locator type.

The binary assets and their hashes are authoritative. `datasets/build_corpus.py` is an **authoring tool**, not a benchmark step; rerunning it may change PDF/PPTX timestamps, compression or system speech output. Changing any asset/reference requires an intentional dataset version/hash update. The test split was authored and frozen without provider-backed test-outcome tuning. Use development cases for subsequent tuning, and version/report any changes before evaluating the test split.

Page 4 stores diagram labels only inside a raster image. The manifest knows its location and correct labels; retrieval receives only the original file. Phase 9 does not add OCR, visual reasoning or Phase 10 repairs. A retrieved caption can earn page-level location credit without demonstrating diagram understanding. Real figure performance is **pending**, not assumed to be zero or successful.

## Deterministic grounding metrics

These are transparent ConceptLens-specific checks, **not RAGAS metrics**. Their per-case values are retained alongside framework values.

- **Citation source accuracy:** expected-source hits / returned citation occurrences (micro average). An unexpected source gets zero credit even if its locator number matches. Repeated citations across answer blocks count as returned occurrences.
- **Citation locator accuracy:** expected-source **and** expected-location hits / returned citation occurrences. PDF pages and PPTX slides require exact numbers. Missing/malformed locations fail. For a video point, the cited interval must contain it inclusively. For an interval, overlap divided by expected duration must be at least **0.5**. The threshold is frozen, not fitted to results. Coarse clip references can penalize otherwise useful short ASR chunks; inspect this limitation when interpreting video failures.
- **Missing citations:** counted separately for supported answered cases. No citations gives undefined precision, never perfect citation accuracy.
- **Refusal:** positive class = decline, ground truth = unsupported. TP: unsupported declined; TN: supported answered; FP: supported declined; FN: unsupported answered. Precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = 2TP/(2TP+FP+FN), accuracy = (TP+TN)/N.
- **Retrieval source recall:** on each supported case, 1 iff at least one expected **source/location** pair appears in retrieved evidence. Average over supported scored cases. Despite the short metric name, filename-only retrieval is insufficient.
- **Evidence coverage:** matched expected source/location pairs / total expected pairs, macro-averaged across supported scored cases. This is **location coverage**, not an automatic assertion that every reference fact was entailed. RAGAS evaluates semantic support separately.
- Pending/errors are excluded from metric denominators and counted by total versus scored coverage. Empty denominators are null. Unsupported cases have undefined retrieval coverage.

Reports break down custom metrics by modality and case type. `failures.csv` stores case ID/question, expected and retrieved support, answer/refusal, citations, failed metric and deterministic reason. A framework score below 1 (with 1e-8 numerical tolerance) is a review signal, not an LLM-written explanation. Raw judgments remain available. Pending rows expose missing execution and are not counted as observed grounding failures.

## Simulator assumptions and fairness

`configuration/simulation.json` freezes all assumptions before the reported comparison. `datasets/items.json` freezes 20 original, source-reviewed deterministic MCQ fixtures: 8 target training items, 8 prerequisite training items and 4 held-out transfer items. They are **not claimed to have passed a live production LLM verifier**. The simulator does not make hundreds of provider calls.

Five profiles have explicit target/prerequisite latent mastery, procedural ability, misconception and response noise:

| Profile | Target | Prerequisite | Procedural | Misconception | Noise |
| --- | --- | --- | --- | --- | --- |
| Novice with prerequisite gaps | .15 | .15 | .20 | false | .08 |
| Misconception | .40 | .65 | .50 | true | .08 |
| Procedural but conceptually weak | .25 | .65 | .85 | false | .08 |
| Strong | .85 | .90 | .90 | false | .04 |
| Noisy/inconsistent | .60 | .60 | .65 | false | .35 |

There are no demographic attributes. Default seeds are **7, 19, 31, 43, 59, 71, 83, 97**, three learners per profile/seed: **120 independent learner identities**, each replayed under three policies across four sessions (**480 sessions/policy, 1,440 total**). Each session has an equal **maximum eight-action** budget, plus one common entry assessment and one common held-out check. Early stopping is permitted and visible; unused budget is not filled with invented interventions.

Response probability is `(1-noise) * max(0, .25 + .67 * ability - misconception_penalty) + noise*.25`. Ability is concept mastery, or the mean of concept mastery and procedural ability for procedural items. The misconception penalty is .20 only on target items while misconception is present. There is no policy-name parameter. Items share the same response model; no policy gets an easier held-out item.

Learning is `m' = m + (1-m)*gain`. Source/visual explanations and prerequisite recaps have gain .07, worked examples .09, ordinary/prerequisite practice .05; probes and verification have zero gain. Target learning is multiplied by `.35 + .65*prerequisite_mastery`. Any target teaching action with positive gain has a .18 chance to remove the misconception. These are published **model assumptions**, not empirical estimates of pedagogy. Visual explanation means the existing structured teaching strategy, not true source-image understanding.

A noisy reasoning marker is emitted on an incorrect entry response with sensitivity .75 for a misconception and false-positive probability .12 otherwise. This produces an observable, event-specific hypothesis fixture. It does not pass latent misconception state to ConceptLens. Reported understanding is also noisy: probability `(1-noise)*target_mastery + noise*.5`. All policies can observe the same entry correctness/reasoning and response feedback; baselines deliberately use less information.

Counter-based SHA-256 random draws use `(seed, profile, replica, session, step, event)`, never policy name. Initial states, seeds, item pool, held-out items and horizon are matched. A policy's different action cannot shift a sequential RNG stream to obtain a more favorable future transfer draw. Latent state persists between sessions; held-out answers never train the learner or update BKT.

### Exactly three policies

- **FIXED:** source explanation → worked example → internal transfer check. The sequence ignores observed learner state and stops after its verification.
- **SIMPLE ADAPTIVE:** wrong entry answer → worked example → ordinary practice; correct entry → source explanation. Then internal transfer; a failure repeats worked example/practice within the same maximum horizon. No diagnosis or prerequisite repair.
- **CONCEPTLENS:** calls the existing `create_session`, `submit_probe`, `select_prerequisite`, `feedback`, `advance`, `prerequisite_choice` and `submit_attempt`. The server-owned strategy order, prerequisite branching, one-transfer behavior, safe actions and exhaustion are unchanged. A real `PrerequisiteEdge` object represents residency understanding → distinguishing TLB misses/page faults; selection uses only observed BKT/counts. A fixed learner preference chooses the sixty-second recap when offered.

`policy.py` replaces persistence, trusted fixture evidence, content generation and response serialization in a scoped in-memory adapter. It does **not** replace policy functions or grading correctness. Diagnostic resolution and assessment grading run production functions; BKT calls production `compute_bkt_step`. The tests assert the actual functions remain installed and exercise confirmation/rejection, feedback, prerequisite selection/choice, no-prerequisite fallback, success, failure and exhaustion.

The initial hypothesis/no-clear-break label comes from the published noisy reasoning fixture, not a live LLM diagnosis. Source/assessment verification is assumed for the reviewed fixture bank, not measured. For a production `general_practice` safe action, the shared harness supplies one ordinary bank item and ends that session; it does not invent a targeted repair loop. Reconsider/collect-more-reasoning stops the session. This cold-start boundary matters: most profiles need not produce a confirmed misconception. No result is tuned to make ConceptLens win.

The fixture port enforces exact question freshness within a ConceptLens repair session. All policies access the same bank; repeats across sessions remain possible and are measured. Held-out IDs/text are never passed into intervention content. Held-out contexts still test the same rules, so template repetition can be high even without exact duplicates.

**BKT is not latent truth.** Entry/ordinary graded assessments and internal transfer update the observed BKT estimate. Production diagnostic/prerequisite probes do not. Reading an explanation does not update BKT. Latent simulated learning is a separate hidden transition used to assess the learner model, not a production mastery write.

## Personalization metrics and statistics

- **Held-out transfer success (primary):** successful common held-out checks / sessions. The same four held-out items and random counters are used by all policies; no policy sees them during teaching.
- **Interventions per successful transfer:** all tutoring actions across sessions / successful held-out checks. Includes explanations, diagnostic questions and choice interactions; excludes the common entry/final test. Includes costs of failed sessions. Zero successes yields null, not zero. Fewer actions can reflect early stopping, so read alongside transfer success and completion.
- **Question repetition:** repeated ID **or** normalized exact text / all presented questions per learner, pooled across entry, teaching and held-out questions across sessions. Normalization casefolds and collapses whitespace. Also report repeated manually assigned template IDs / questions. Held-out variants with the same structural rule share a template; changing numbers/context is not automatically counted as novel. No semantic similarity detector is claimed.
- **Simulated latent mastery gain:** mean final minus initial target mastery per learner over all sessions. Also report prerequisite gain. Neither is measured human learning.
- **Session completion:** proportion with a passed policy-internal verification (actual completed Phase 7 status for ConceptLens). This is distinct from the common primary held-out outcome.
- **BKT error:** mean absolute difference between target BKT estimate and latent target mastery at session end, before held-out feedback. It is simulated tracking error, not real calibration validation.
- **Strategy changes:** number of adjacent differing action types per session. Raw trajectories retain all actions and outcomes.

Each policy reports point estimate, learner/session N, SD across per-learner metric values, and a 95% percentile bootstrap interval from **1,000** resamples using seed **20261006**. Resampling is stratified by the five fixed profiles and clustered at learner identity, preserving each learner's sessions. The same sampling stream is used across policies. Ratios are recomputed from totals in every resample. Undefined efficiency replicates are omitted with `bootstrap_defined` and `sd_n_defined` recorded. SD for a ratio describes defined per-learner ratios, not its pooled point estimate.

This is not a hypothesis test and makes no statistical-significance claim. Profiles and transition parameters are assumed, not sampled from a population. Confidence intervals describe simulation variability under these assumptions. Diagnosis accuracy is deliberately not presented: the initial classifier is synthetic; reporting its configured error rate as measured production quality would be misleading. Prerequisite gain is reported without inventing a clinically meaningful repair-success threshold. There is no simulated wall-clock learning-time claim.

To increase size without changing items, copy the configuration and increase `learners_per_profile_seed` or add unique seeds. Larger session counts require additional versioned, disjoint held-out items; the loader rejects silent held-out reuse. Do not tune the gains after seeing comparisons and call that independent evaluation.

## Reproducibility and artifacts

JSON envelopes record evaluation version, base commit, Python/framework versions, dependency-lock hash, all production service hashes, evaluation code hashes, dataset version/hash and full run configuration. Simulation payloads contain profiles/seeds/counts/policy definitions, summaries and raw multi-session trajectories. Timestamps are outside the payload.

The checked-in default simulation was run twice. Canonical payloads and all non-timestamp metadata matched exactly; `reports/reproducibility.json` records the SHA-256 and both timestamps. To repeat:

```sh
PYTHONPATH=evaluation:backend backend/.venv/bin/python -m conceptlens_eval simulate --out /tmp/conceptlens-repeat.json
PYTHONPATH=evaluation:backend backend/.venv/bin/python - <<'PY'
import json
from pathlib import Path
saved = json.loads(Path('evaluation/reports/simulation.json').read_text())
repeat = json.loads(Path('/tmp/conceptlens-repeat.json').read_text())
assert saved['payload'] == repeat['payload']
print('identical simulation payload')
PY
```

Results include JSON, per-case and per-session CSV, Markdown and six standalone SVG charts. Pending grounding charts deliberately contain no bars. There are no fake zero/100% values. The report generator rejects fixture results unless its output directory is explicitly named as a fixture report, and labels every report/CSV/chart with result provenance.

| Artifact | Contents |
| --- | --- |
| `reports/grounding.json` | Pending or actual per-case grounding, framework/custom metrics and failures |
| `reports/simulation.json` | Reproducible full simulation trajectories and statistics |
| `reports/reproducibility.json` | Two-run equality evidence |
| `reports/database-check.json` | Disposable success/failure lifecycle fixtures |
| `reports/verification.json` | Test/regression/gate results, limitations |
| `reports/judge/report.md` | Judge-facing account of outcomes and limitations |
| `reports/judge/*.csv` | Grounding cases/failures; simulation summaries/sessions |
| `reports/judge/*.svg` | Framework summary, modality coverage, failure categories, transfer, efficiency, repetition |
| `reports/judge/phase10-handoff.json` | Five prioritized weaknesses and Phase 10 scope |

The implementation leaves all files uncommitted. Grounding/provider/visual quality remains a pending measurement; exact source opening, true visual evidence, short-answer/numerical assessment, CPU scheduling verification, stronger cold start, post-assessment reports and remaining Track-D closure remain Phase 10.
