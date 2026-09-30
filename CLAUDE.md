# ConceptLens Engineering Constitution

## Product

ConceptLens is a multimodal adaptive-learning system.

Tagline:
Learn anything. Debug your understanding.

Core principle:
Most AI tutors optimize the answer.
ConceptLens optimizes the next learning action.

ConceptLens builds:
1. a model of the learning material,
2. a model of the learner,
3. a policy for choosing the next learning action.

The system may answer, explain, ask a diagnostic question,
repair a prerequisite, provide practice, change teaching strategy,
or issue a Transfer Check.

---

## Non-negotiable reliability rules

Never fabricate:
- citations
- source locations
- PDF page numbers
- PPTX slide numbers
- video timestamps
- mastery values
- evaluation scores
- verification results

Every source-backed generated claim must reference stored evidence.

Every learner-state update must be traceable to an actual learner
attempt, assessment, diagnostic check, or verified interaction.

Reading an explanation alone does NOT increase mastery.

An unverified generated assessment question must NEVER modify
learner state.

Attempts are immutable evidence.

Question answer keys must remain server-side until grading.

Unsupported source questions must be declined or explicitly
separated from outside knowledge.

Misconceptions are hypotheses, not facts.
A single wrong answer must not permanently label the learner.

---

## Architecture

Frontend:
- React
- TypeScript

Backend:
- Python
- FastAPI

Persistence:
- PostgreSQL
- pgvector

Other:
- one ingestion/background worker
- original source file storage
- evaluation runner

Major modules:
- ingestion
- evidence/provenance
- retrieval
- grounding
- assessment
- learner model
- reasoning diagnosis
- teaching policy
- evaluation

---

## Engineering rules

Prefer a modular monolith.

Do NOT introduce:
- unnecessary microservices
- Kubernetes
- multiple databases
- free-form multi-agent orchestration
- unrelated features
- premature abstractions

Use type hints.

Keep API routes, schemas, database models,
business services, and provider adapters separated.

All external-model providers must sit behind interfaces/adapters.

Do not silently change established architecture.

---

## Development workflow

For every assigned task:

1. Inspect the existing repository.
2. State the implementation plan briefly.
3. Modify only the requested scope.
4. Preserve working behavior.
5. Add or update tests.
6. Run relevant tests.
7. Report exact test results.
8. Report files created/changed.
9. Report limitations or unresolved issues.
10. STOP.

Never automatically continue into the next project phase.

Do not claim a feature works unless it was actually implemented
and tested.