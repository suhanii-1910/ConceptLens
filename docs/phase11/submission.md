# ConceptLens — submission draft

**Learn anything. Debug your understanding.**

Draft for human review before submission. No deployment or video URL is claimed. The project is a local prototype; real external provider acceptance and framework grounding measurements remain **PENDING CONFIGURATION**. See [release verification](verification.json) and the [demo guide](demo-guide.md).

## One-line pitch

ConceptLens turns course material and learner reasoning into a grounded next learning action, then checks whether understanding transfers.

## Short description

Most AI tutors optimize the answer. ConceptLens optimizes the next learning action. Upload course material, answer a verified question, explain your thinking, test a possible reasoning break, and follow targeted teaching or prerequisite repair. A fresh Transfer Check and an inspectable Learning Trace connect the learning decision to evidence.

## Inspiration and problem

An explanation can sound clear while a learner still applies the wrong rule. Correct answers can also come from guessing or memorizing a pattern. We wanted the system to ask a more useful question: what evidence would distinguish understanding from a plausible answer, and what should the learner do next?

CPU Scheduling makes this concrete. Under SRTF, a learner may compare an arriving process's burst with the running process's original burst, forgetting the work already completed. A longer explanation is not necessarily the right intervention. The learner may need a diagnostic question about remaining time, a prerequisite recap, or a different example whose answer reverses.

## What it does: the solution

ConceptLens builds a model of course material, a model of learner evidence, and a policy for the next learning action. Its five views are Workspace, Ask, Learn, Practice and Dashboard.

Sources become evidence with exact provenance. Grounded Ask provides citations that open actual PDF pages, PPTX slide previews or video timestamps. Verified assessments gather answers. Learner-authored reasoning helps the Reasoning Debugger propose a possible first break; a diagnostic probe can confirm or reject that hypothesis. The adaptive loop can explain, change strategy, inspect a prerequisite, offer practice, or issue a fresh Transfer Check. The Learning Trace shows what was supported, what happened and what remains uncertain.

The key innovation is the connection between these steps: a decision about the next action is tied to source evidence and learner evidence, and its outcome is tested rather than assumed. A diagnosis is an event-specific hypothesis, not a permanent label.

## How it works

1. **Material model:** extract PDF text/tables/images, PPTX content and timestamped video transcript/frames. Store source-owned evidence and curated concepts/prerequisites.
2. **Grounding:** combine local semantic embeddings with lexical retrieval in PostgreSQL/pgvector. Validate citation locations and decline unsupported source questions.
3. **Assessment:** independently verify generated MCQ, short-answer and numerical questions. Keep answer contracts private until grading; preserve attempts as immutable evidence.
4. **Reasoning diagnosis:** use an actual attempt and learner explanation to propose and test a tentative misconception. Rejected or unclear diagnoses can lead to safe concept-level learning without inventing certainty.
5. **Personalization:** select a bounded sequence of teaching strategies and prerequisite actions from observed state. Reading an explanation does not change mastery.
6. **Transfer and proof:** grade a fresh verified check through the normal evidence path, update eligible BKT observations, and expose the decision trail and provisional learner report.

The deterministic scheduling engine covers FCFS, SJF, SRTF, both priority variants and Round Robin. It computes scheduling proof before numerical grading. In the showcase, P1(0,8)/P2(5,4) keeps P1 running, while P1(0,9)/P2(4,3) preempts it. These are inputs to a generic solver, not special cases in production logic. A live generated transfer is provider-dependent and may use different numbers.

## How we built it

A modular monolith connects a React/TypeScript/Vite frontend to FastAPI, SQLAlchemy and PostgreSQL 16 with pgvector. PyMuPDF, pdfplumber and python-pptx preserve document evidence; FFmpeg/FFprobe and local transcription support video. Local sentence-transformers supplies retrieval embeddings. External text and vision generation use provider adapters.

Source originals and derived artifacts are separate. Course isolation and provenance validation guard evidence reuse. Strict schemas, private grading contracts, immutable attempts, transaction boundaries and fresh transfer checks protect the learner evidence trail. Tests distinguish deterministic mechanisms, fixture behavior, simulated outcomes and actual provider execution.

Visual semantics use actual image bytes in both generation and a separate verification call. The two calls currently share the configured vision model; this is not a claim of independent model populations. Unsupported or unreadable content is not accepted by design. Real vision quality remains pending measurement.

## Evaluation and measured outcomes

**SIMULATED PERSONALIZATION RESULT** — 120 learner identities, four sessions each, 480 sessions per policy, frozen profiles/seeds/items and shared response assumptions. These are simulated outcomes, not real student gains or a statistical-significance claim.

| Metric | Fixed | Simple Adaptive | ConceptLens |
| --- | ---: | ---: | ---: |
| Held-out transfer | 57.92% | 60.00% | 59.38% |
| Actions per successful transfer | 5.18 | 6.87 | 7.12 |
| Exact question repetition | 33.33% | 33.82% | 17.29% |
| Session completion | 58.13% | 86.25% | 58.96% |
| Simulated latent mastery gain | +0.1958 | +0.2260 | +0.2123 |

ConceptLens repeats fewer exact questions and slightly exceeds Fixed transfer, while remaining slightly below Simple Adaptive transfer and spending more actions per successful transfer. Completion and other metrics expose further trade-offs. We do not claim an overall winner. Template repetition remains high even when exact repeats fall.

Grounding evaluation uses an authored frozen multimodal benchmark, citation/refusal checks and actual RAGAS 0.4.3 metric implementations. Real provider-backed scores are **pending configuration**, represented as null with status, never zero or fabricated success. Positive/negative metric fixtures verify the harness, not model quality.

The [historical Phase 10 raw result](../../evaluation/reports/post-phase10-simulation.json) and [evaluation methodology](../../evaluation/README.md) expose the assumptions, full metrics and uncertainty. Phase 11 did not alter the frozen inputs or historical results to improve the presentation.

## Challenges and accomplishments

The difficult parts were maintaining a trustworthy chain across source retrieval, generated assessments, diagnostic uncertainty and learner updates; keeping original evidence separate from interpretation; and testing changes without touching the normal development database. The product handles those boundaries explicitly instead of treating every model response as learning evidence.

The implementation brings exact source opening, typed assessment, deterministic scheduling proof, diagnostic hypotheses, strategy changes, conditional prerequisite repair and fresh transfer into five coherent views. Phase 11 adds a reproducible isolated CPU Scheduling course, genuine local browser acceptance and clear run/submission documentation. Exact observed test counts and pending provider checks are in [verification.json](verification.json); fixture success is not described as a completed real-model journey.

## What we learned

Transfer is more revealing than repeating the same question. A diagnosis needs a way to be rejected. Unknown mastery is not evidence of weakness. Simulated policy comparisons can expose costs and failure modes, but their assumptions do not justify claims about students. Reliability includes showing when the system cannot answer or grade.

## Limitations and what's next

Real text/vision provider acceptance and real framework scores are the immediate remaining measurements. A bounded rehearsal must verify the actual generation → diagnosis → teaching → transfer chain; model latency, refusals and strict-schema compatibility remain empirical questions.

The prototype also has approximate PPTX previews, no general scanned-PDF OCR or PDF highlighting, manually curated concept relationships, uncalibrated BKT defaults, and a single-CPU integer-tick scheduler without switching costs. It has no authentication or production deployment. The simulation is not a real-user study. Future work should prioritize provider evaluation, BKT calibration and a carefully designed learner study before claims of learning effectiveness. These are future directions, not features shipped in this release.

## AI-use disclosure

**Product AI:** ConceptLens supports configurable external text and vision models, local sentence-transformers embeddings and local transcription. Generator/verifier calls have separate roles but can share a configured model. No specific external provider/model use or quality result is asserted without a recorded run; real provider acceptance remains pending.

**Development assistance:** AI coding and review assistance, including Codex, contributed to implementation and documentation. Automated checks and verification artifacts support the technical claims. The project team remains responsible for reviewing the code and submission. No private conversations, API keys or confidential provider responses are part of these assets.

## Demo video outline — approximately 6 minutes 30 seconds

| Time | Screen / action | Narration emphasis |
| --- | --- | --- |
| 0:00–0:30 | Title, SRTF learner mistake | “A clear answer can leave the wrong rule intact.” State the next-action thesis. |
| 0:30–1:15 | Workspace → Ask → exact PDF page | Sources are inspectable evidence. Avoid spending time on setup terminals. |
| 1:15–2:20 | Verified question → wrong answer → learner reasoning → probe | Contrast original burst with remaining time. Keep “possible” visible until the probe resolves. |
| 2:20–3:25 | Source teaching → Still confused → another strategy | Adaptation changes the action. Show prerequisite repair only if actually justified and offered. |
| 3:25–4:25 | Fresh Transfer Check and grading | Show the actual new problem and result. If numbers differ, explain its actual rule; separately show the generic solver reversal. |
| 4:25–5:15 | Expanded Learning Trace → Dashboard | Link learner evidence to action and actual mastery updates; retain Untested and uncertainty labels. |
| 5:15–6:00 | Evaluation comparison | Show all three baselines, repetition and cost trade-offs. Say “simulation,” and state grounding is pending if still unmeasured. |
| 6:00–6:30 | Return to product / disclosure | “Learn anything. Debug your understanding.” State prototype limits and AI use. |

This is a plan, not a completed recording. Before filming, run the [pre-demo checklist](demo-guide.md). If providers remain unavailable, identify the live local mechanisms and label any fixture UI segment **API FIXTURE — NOT LIVE AI ACCEPTANCE** visibly. Do not splice fixtures into an apparently continuous real-provider learning journey.

## Screenshot captions

| Capture | Caption |
| --- | --- |
| Source viewer | “An answer's citation opens the actual source page.” |
| Reasoning Debugger | “A possible first reasoning break, tested by a diagnostic probe.” |
| Changed teaching strategy | “When the learner is still confused, the next action changes.” |
| Prerequisite branch | “Repair offered from a stored prerequisite relationship and learner evidence.” |
| Transfer feedback | “A fresh verified problem tests whether the rule transfers.” |
| Learning Trace | “Inspect why the action was chosen and what was actually verified.” |
| Dashboard | “Observed mastery and untested concepts remain distinct.” |
| Evaluation | “Simulated policy comparison: lower exact repetition with visible efficiency trade-offs.” |

Only use a caption if the image actually shows that state. Prefix any fixture screenshot caption with **API fixture illustration**. Exclude credentials, local personal paths and developer consoles with sensitive content.

## Judging talking points

- A coherent loop connects material, reasoning, next action and transfer.
- Citations and trace make the evidence inspectable rather than decorative.
- A misconception can be rejected; missing evidence stays missing.
- The deterministic scheduling reversal demonstrates general rules without hardcoded demo logic.
- Baselines and pending statuses show trade-offs honestly; the submission does not claim a real-user learning study.
