# Phase 10 implementation and acceptance notes

All work is uncommitted on `feature/requirement-closure`, based on `c054808b43bfa3c29030bbec3433bde83da0bd61`. No normal development database was connected to or migrated. Migrations 0001–0006 and the Phase 9 scientific baseline are unchanged.

## Source and visual evidence

`GET /courses/{course}/sources/{source}/location` accepts an exact typed page, slide, or time locator. `/preview` renders the actual PDF page or PPTX slide content; `/file` returns only the server-resolved course-owned original and supports HTTP byte ranges. Unknown query fields, traversal, escaping symlinks, missing files, foreign sources, wrong locator kinds, invalid bounds and nonfinite timestamps fail closed. UUIDs never become caller-supplied filesystem paths. MIME types are fixed by supported source type; filenames are sanitized; responses are private/no-store with nosniff and a restrictive CSP.

The reusable native-dialog SourceViewer is used by every citation surface. It shows the filename and exact page/slide/time; video seeks on metadata load and retains ordinary playback controls. Original files remain accessible. PDF highlighting is not implemented. PPTX is an actual-content layout fallback using python-pptx/PyMuPDF: original text, pictures, tables and basic shapes at slide coordinates. LibreOffice is unavailable. Group transforms, charts, theme styling, font fidelity and Office effects can be omitted or simplified, with an explicit notice and original-file download.

EvidenceUnit provides stable visual identity and course/source/locator ownership. `/sources/{source}/evidence` lists source evidence; `/evidence/{id}` exposes sanitized details; `/asset` serves only a contained, decoded source-owned image. PDF/PPTX tables retain cell rows as well as existing searchable text. Existing video keyframes retain timestamp provenance.

`POST /evidence/{id}/interpret` passes the actual extracted image to a vision provider, then makes an independent image-backed verification call. Only accepted descriptions populate searchable evidence; rejection is recorded and contributes no semantic description. Interpretation invalidates stale embeddings. The UI explicitly instructs re-indexing after acceptance. Configure `CONCEPTLENS_VISION_MODEL` plus the existing LLM URL/key to enable this path. Without configuration, extracted assets remain inspectable and interpretation returns 503; no understanding is claimed.

The frozen raster-only Aster PDF figure was exercised through real extraction, fixture image interpretation/verification, indexing, retrieval and grounded Ask, retaining image modality and page 4. **TEST FIXTURE — NOT A SUBMISSION RESULT.** It proves integration, not real multimodal model quality. Frozen grounding scores remain pending.

## Typed assessment and deterministic scheduling

The shared AssessmentQuestion/Attempt pipeline now accepts MCQ, short_answer and numerical. Private grading contracts are excluded from public questions. Generator and independent verifier remain separate calls. Server-owned evidence allowlists and citations remain in force. Exact repeated stems are rejected; a narrow course-row lock serializes generation freshness checks/inserts after provider calls. A real PostgreSQL race test verifies only one duplicate candidate persists.

MCQ retains four-option deterministic grading. Short answers use verified reference facts plus current grounded evidence and a structured semantic evaluator, accepting semantic equivalents rather than string equality. Verdicts are correct, incorrect or cannot_grade. Unavailable/malformed/unsupported-credit responses cannot update BKT. Numerical responses use bounded exact Fraction parsing, validated units, and a verified explicit tolerance (nonzero tolerance requires justification). No implicit unit conversion occurs. Scheduling quantities use exact comparison and server-computed answers.

The pure single-CPU scheduler supports FCFS, SJF, SRTF, non-preemptive priority, preemptive priority and Round Robin. Inputs are bounded integer ticks, unique process IDs, nonnegative arrivals/priorities, positive bursts and a positive RR quantum. Lower priority values run first. Ties resolve by criterion, arrival and input order; RR boundary arrivals enter before the preempted process is requeued. Outputs contain idle/execution segments, dispatch decisions, start/completion/turnaround/waiting/response, averages and assumptions. There is no context-switch overhead or multi-CPU model. Classic and reversed SRTF cases are generic solver cases, not special branches.

For scheduling generation, the server solver builds the authoritative private result/proof before independent wording/source verification. Candidate numeric disagreements are rejected. Proof appears only after submission. The learner sees only scenario inputs and answer format beforehand.

Attempts preserve submitted data and grading results. ORM guards and PostgreSQL triggers prohibit mutation/deletion except the first mastery-status resolution and legitimate whole-course deletion. The delete trigger checks at transaction completion so ORM child-first deletion works; isolated SQL deletion is rejected at commit. Repeated exposure retains existing BKT rules. An earlier ungradable exposure can therefore cause a later response to that same item to skip BKT; a fresh verified question is the next opportunity for a mastery update.

## Diagnostic, reports and adaptive learning

The diagnostic stores a unique learner/course selection in DiagnosticSession. It selects up to five fresh, single-concept, provenance-valid verified questions, balancing distinct concepts. Generated diagnostic questions carry the server-selected course concept to both generator and independent verifier; foreign concept IDs are rejected before provider calls. If fewer than three are available, the existing generator may fill gaps (at most five candidate-generation calls). One or two questions are permitted when evidence is limited. Provider failure retains an available verified sample; without one it returns a safe unavailable/insufficient-evidence state. Selection is serialized and stable; completion is derived from real gradable attempts and resumes after reload. Untouched concepts remain UNTESTED. The existing BKT virtual prior is never rendered as observed ability.

No-clear-break, rejected and inconclusive diagnoses can now enter concept-level teaching when the underlying verified assessment has one unambiguous course concept. The diagnosis is not promoted or rewritten. Hypotheses still require a real diagnostic probe; insufficient reasoning/evidence still requests more evidence. Confirmed repair retains its strict original context checks. Existing strategies, source verification, real prerequisite graph, learner choices, a fresh Transfer Check and ordinary attempt/BKT machinery are reused. Prior diagnostic questions remain in freshness context even after rejection. Strategies cannot repeat within a session; the one-transfer policy and reassessment terminal bound the loop. Ambiguous/missing concept mappings fail safely. Historical sessions whose immutable target was absent may require a fresh reasoning event.

Trace shows observations, unchanged interpretation, probe results, teaching, actual verification and BKT observations. Concept-level continuation is explained explicitly. Missing probes never receive a verified-probe flag. Citation proof evaluates evidence actually present, so a missing optional probe does not invalidate independently grounded teaching.

The read-only assessment report is course/learner cumulative, counts the first gradable response per verified question, excludes repeats from scoring, and separately counts ungradable responses. It shows type/concept performance, small-sample caveats, observed weak/strong/uncertain areas, UNTESTED concepts, event-scoped hypotheses with actual status, evidence-backed prerequisite concerns and next action. These performance counts are distinct from eligible BKT observations. Citations are rebuilt against current stored provenance. The course concept panel shows existing source links and actual prerequisite relationships, explicitly distinguishing recorded edges without verified source backing from source-backed edges.

Exactly five principal views remain: Workspace, Ask, Learn, Practice and Dashboard. New capabilities use panels/dialogs. Scope-keyed state, cancellation, duplicate-submit guards and existing 409 reconciliation remain.

## Migration and evaluation compatibility

0007 adds typed grading/response data, nullable type-specific answer fields, question/response constraints, immutable-attempt triggers and diagnostic sessions. The enum is rebuilt transactionally. Historical MCQ records survive 0006→0007→0006→0007. A downgrade refuses to discard typed assessments: export and explicitly remove Phase-10-only data before a lossy downgrade can be attempted. Lifecycle tests remove only their disposable typed fixture course before exercising the successful downgrade.

The only evaluation runtime change is `database.py` migrating newly created evaluation databases to 0007 so the current ORM can read them. This changes no benchmark meaning. `policy.py`, simulation transitions, configuration, both item manifests, baselines, metrics and bootstrap code are byte-for-byte unchanged. Evaluation tests update only schema expectations and assertions for the real production continuation behavior. Adapter parity exercises the same production state transitions and verifies no diagnosis/BKT promotion during teaching.

Historical migration tests now stage current-ORM fixture work at head and return to exact historical revisions for preservation/schema assertions. The unchanged original lifecycle tests were also replayed from a temporary frozen-base checkout. No old migration was edited. All disposable databases were dropped and namespace absence was independently checked.

## Same-benchmark result

**SIMULATED PERSONALIZATION RESULT — not real student learning evidence.** 120 independent simulated learners, 480 sessions per policy, unchanged seeds/profiles/held-out bank, gains/noise and 1,000 bootstrap replicates. The pre artifact is byte-identical to Phase 9. Two final post runs have identical deterministic payloads; timestamps remain outside that contract. Fixed and Simple Adaptive individual trajectories and statistics are unchanged.

| Metric | Fixed (unchanged) | Simple Adaptive (unchanged) | ConceptLens pre | ConceptLens post |
|---|---:|---:|---:|---:|
| Held-out transfer | 57.9167% | 60.0000% | 54.3750% | 59.3750% |
| Actions / successful transfer | 5.179856 | 6.871528 | 2.574713 | 7.119298 |
| Exact question repetition | 33.3333% | 33.8235% | 29.9608% | 17.2900% |
| Template repetition | 75.0000% | 83.4559% | 75.0000% | 74.7967% |
| Simulated latent mastery gain | +0.195794 | +0.225984 | +0.086311 | +0.212329 |
| Internal completion | 58.1250% | 86.2500% | 3.5417% | 58.9583% |
| BKT absolute tracking error | 0.243930 | 0.260943 | 0.260224 | 0.253990 |
| Strategy changes / session | 2.000000 | 3.122917 | 0.400000 | 3.227083 |
| Simulated prerequisite gain | 0 | 0 | +0.003529 | +0.034067 |

Pre diagnoses: 425 no_clear_break, 20 rejected, 35 confirmed. Post: 432 no_clear_break, 21 rejected, 27 confirmed. Completion improves while diagnoses remain largely unconfirmed, as intended; no forced confirmation was introduced. Transfer improves by 5 percentage points and completion by 55.4167 points, while actions/success worsen by 4.544586. ConceptLens transfer is numerically above Fixed and below Simple Adaptive. No statistical-significance claim is made. Bootstrap CIs remain in the raw artifacts.

## Verification and limits

See `verification.json` for exact commands/counts, frozen hashes and cleanup evidence. Backend: 555 ordinary tests; focused Phase 10: 84; PostgreSQL: Phase 5 seven, Phase 6 four, Phase 7 seven, Phase 10 three, plus two historical migration lifecycles. Evaluation: 80, including actual RAGAS 0.4.3 positive/negative provider fixtures and disposable lifecycle tests. Frontend: 52 unit tests, typecheck/lint/build; Playwright: eight fixture journeys across desktop/mobile. Two live-backend browser cases are intentionally opt-in and were not run.

Generator, independent verifier, vision and evaluator providers are unconfigured. Real model acceptance and real grounding scores are pending. Fixture results are never substituted for provider quality. Remaining limitations are provider validation, simplified PPTX rendering, no PDF region highlighting, small-sample/un-calibrated BKT estimates, and the simulator's existing assumptions. Optional Hindi/Hinglish work and Phase 11 submission assets were not added.
