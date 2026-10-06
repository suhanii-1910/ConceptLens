# ConceptLens Phase 9 evaluation

## What was evaluated?

The actual ingestion/retrieval/Ask pipeline is executable against a disposable PostgreSQL database. RAGAS 0.4.3 supplies four framework metrics; deterministic source/location/refusal metrics are separate.

Grounding: **PENDING REAL PROVIDER RUN**. Dataset `aster-memory-1.0.0`, split `test`, 12 cases.

**REAL FRAMEWORK RESULTS: PENDING PROVIDER CONFIGURATION**
No pending value is a zero, a success, or a test-fixture score.

| Framework metric | Mean | Scored N |
| --- | --- | --- |
| answer_relevancy | PENDING / undefined | 0 |
| context_precision | PENDING / undefined | 0 |
| context_recall | PENDING / undefined | 0 |
| faithfulness | PENDING / undefined | 0 |

| Custom metric | Value |
| --- | --- |
| answers_missing_citations | 0.0000 |
| cases_scored | 0.0000 |
| cases_total | 12.0000 |
| citation_count | 0.0000 |
| citation_locator_accuracy | PENDING / undefined |
| citation_source_accuracy | PENDING / undefined |
| evidence_coverage | PENDING / undefined |
| refusal_accuracy | PENDING / undefined |
| refusal_f1 | PENDING / undefined |
| refusal_precision | PENDING / undefined |
| refusal_recall | PENDING / undefined |
| retrieval_source_recall | PENDING / undefined |

Refusal confusion matrix: `{"FN": 0, "FP": 0, "TN": 0, "TP": 0}`.

## Grounding by modality

| Modality | Cases | Scored | Locator accuracy | Evidence coverage |
| --- | --- | --- | --- | --- |
| figure | 2 | 0 | PENDING / undefined | PENDING / undefined |
| mixed | 2 | 0 | PENDING / undefined | PENDING / undefined |
| none | 2 | 0 | PENDING / undefined | PENDING / undefined |
| table | 2 | 0 | PENDING / undefined | PENDING / undefined |
| text | 2 | 0 | PENDING / undefined | PENDING / undefined |
| video | 2 | 0 | PENDING / undefined | PENDING / undefined |

| Modality | Faithfulness (N) | Relevancy (N) | Context precision (N) | Context recall (N) |
| --- | --- | --- | --- | --- |
| figure | PENDING / undefined (0) | PENDING / undefined (0) | PENDING / undefined (0) | PENDING / undefined (0) |
| mixed | PENDING / undefined (0) | PENDING / undefined (0) | PENDING / undefined (0) | PENDING / undefined (0) |
| none | PENDING / undefined (0) | PENDING / undefined (0) | PENDING / undefined (0) | PENDING / undefined (0) |
| table | PENDING / undefined (0) | PENDING / undefined (0) | PENDING / undefined (0) | PENDING / undefined (0) |
| text | PENDING / undefined (0) | PENDING / undefined (0) | PENDING / undefined (0) | PENDING / undefined (0) |
| video | PENDING / undefined (0) | PENDING / undefined (0) | PENDING / undefined (0) | PENDING / undefined (0) |

## Inspectable grounding failures

No observed grounding failures or successes are claimed for pending cases. `grounding-cases.csv` preserves every pending case; `failures.csv` includes execution/pending reasons and complete source/answer/citation fields.

No completed pipeline results are available to analyze.

## Policy comparison — SIMULATION

**SIMULATED PERSONALIZATION RESULT**

Five explicit profiles, identical starting states and counter-based random seeds, common item pool, four sessions and equal maximum action horizons. The held-out transfer check is never used in teaching. Production Phase 6/7 decisions run with frozen content and memory persistence; this does not test live LLM diagnosis or content verification.

| Policy | Transfer success | 95% CI | Learners | Sessions | Actions/success | Exact repetition | Latent gain | Internal completion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FIXED | 0.5792 | [0.5395833333333333, 0.6208333333333333] | 120 | 480 | 5.1799 | 0.3333 | 0.1958 | 0.5813 |
| SIMPLE ADAPTIVE | 0.6000 | [0.55625, 0.64375] | 120 | 480 | 6.8715 | 0.3382 | 0.2260 | 0.8625 |
| CONCEPTLENS | 0.5437 | [0.5020833333333333, 0.5875] | 120 | 480 | 2.5747 | 0.2996 | 0.0863 | 0.0354 |

Latent gain is final minus initial simulated target mastery across all sessions. Internal completion means a policy's own verification passed; held-out transfer is the primary common outcome. Full metric N, learner SD, confidence intervals and profile breakdowns are in JSON/CSV.

The results do not establish that ConceptLens outperforms the baselines. The production safe path can end after general practice when diagnosis is unconfirmed. No test of statistical significance or real educational gain is claimed.

95% percentile bootstrap intervals resample whole learners within each fixed profile; sessions are not treated as independent participants. Policies use matched learner identities and random counters. The SD for efficiency describes defined per-learner ratios; the overall estimate is a ratio of totals.

## Limitations and Phase 10

- Synthetic transition assumptions; not measured student learning.
- Frozen content and noisy reasoning fixtures do not evaluate live generator/verifier/diagnosis quality.
- Equal maximum horizon; policies may stop early. Held-out checks are common and never taught.
- Template repetition groups manually declared equivalent structures; no semantic embedding threshold.
- Confidence intervals condition on this simulator and five fixed profiles; no significance test.
- Small original authored corpus; reference locations measure location coverage, not entailment of every fact.
- Page-level retrieval can find a figure caption without understanding its raster diagram. Framework judgments and case inspection are still necessary.
- Exact source opening, real visual evidence, short-answer/numerical grading, CPU verifier, cold start and post-assessment reporting remain Phase 10.

See `phase10-handoff.json` for five ranked weaknesses, evidence and reserved work.

## Reproduction

See `evaluation/README.md` for exact commands, provider configuration, metric definitions and database safeguards. JSON envelopes record commit, evaluation code hashes, configuration, dataset version and timestamps. Timestamp metadata is excluded from deterministic payload comparisons.
