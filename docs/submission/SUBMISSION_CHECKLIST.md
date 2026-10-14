# ConceptLens submission checklist

**Integrated review · 14 October 2026; publication-safety and clean-install checks passed.** Visibility changes and merging into main still require approval. Official requirements below come from the user-supplied guideline summary. No separate official deadline or event URL was available. The additional review tasks are project-quality gates, not invented hackathon rules.

## Official submission requirements

- [ ] Devpost project description completed, reviewed against final source, and pasted into the project. [Full draft](DEVPOST_DESCRIPTION.md) exists; final reconciliation remains open.
- [ ] Public GitHub repository reviewed and accessible while signed out.
- [x] README covers prerequisites, dependencies, environment and setup; fresh dependency installation, frontend build and disposable backend startup/migration/ingestion passed on the reviewed revision. See [scope and results](INTEGRATION_VERIFICATION.md#publication-and-clean-install-follow-up). Real screenshots are now included locally under docs/assets/screenshots/; the demo video remains pending.
- [x] README discloses the AI coding assistant actually evidenced (OpenAI Codex) and specifies the assisted parts, as required by the team-supplied official rule.
- [x] Integrated source committed and pushed to the intended origin feature branch after approval; public visibility is a separate gate.
- [ ] Demo recorded showing the actual project working.
- [ ] Video duration is between **3 and 10 minutes**; the [script](DEMO_VIDEO_SCRIPT.md) targets 4:40.
- [ ] Video uploaded to **YouTube**.
- [ ] Video visibility is **Public or Unlisted**, not Private.
- [ ] Video has **English narration or subtitles**.
- [x] Team size confirmed: 2 members.
- [x] Both team members listed by their confirmed full names.
- [x] Both team members have Devpost accounts.
- [x] Both team members are registered on the Devpost project.
- [ ] All required repository, video, project and team-account links tested.
- [ ] Final submission completed before the **official deadline**.

**Deadline:** `OFFICIAL_DEADLINE_AND_TIMEZONE_PENDING`. Obtain it from the organizer; the supplied guideline summary does not state it. Do not infer it from the current date, commit dates or hackathon year.

## Team roster — complete before submission

| Member | Full name | Devpost username | Added? |
| --- | --- | --- | --- |
| 1 | Priyanshu Pandey | @GODLIKEyp | Yes |
| 2 | Suhani Garg | @suhanigarg5670 | Yes |

Remove unused rows. Priyanshu and Suhani are known first names from the task, not verified full-name/account records. Do not infer identities from local usernames or Git handles.

## Links and final source

| Item | Value / status |
| --- | --- |
| Intended repository | https://github.com/suhanii-1910/ConceptLens — public repository; final published branch accessibility still to verify |
| Final submission branch/ref | `feature/final-integration` on origin |
| Full final commit | `FINAL_COMMIT_SHA_PENDING` |
| Devpost project | `DEVPOST_PROJECT_URL_PENDING` |
| YouTube demonstration | `YOUTUBE_URL_PENDING` |
| Official guidelines/event URL | `OFFICIAL_GUIDELINES_URL_PENDING` |
| Official deadline and timezone | `OFFICIAL_DEADLINE_AND_TIMEZONE_PENDING` |

## Documentation package status

- [x] Complete Devpost narrative drafted.
- [x] README proposal reconciled into the root README; original proposal retained in Git history.
- [x] Architecture documentation includes five source-supported Mermaid flows.
- [x] Verification record separates current checks, historical evidence, fixtures and pending AI workflows.
- [x] Full timed English demo script includes exact narration, navigation and failure alternatives.
- [x] Documentation index and cross-machine handoff plan written.
- [x] Genuine Observatory screenshots added locally with captions and working relative image links; publication pending.
- [ ] All drafts reconciled with the final integrated source and cleared for publication.

## Final project review — team tasks, not additional event rules

- [x] Merge the committed Observatory contribution with backend/documentation in an isolated worktree; preserve unrelated local files. See [integration verification](INTEGRATION_VERIFICATION.md).
- [x] Confirmed direct OpenAI routing in the successful local walkthrough; JSON request fix d0da5f9 integrated. Historical compatible-mode demo helper documented separately.
- [x] Run integrated build, lint, unit, PostgreSQL/migration and browser checks; use port 5175 without stopping existing services.
- [x] Verify live route/course loading against the existing isolated API, plus fresh ingestion/indexing/previews/concept relationships in a disposable API run.
- [x] Documented live grounded Ask, verified assessment, uncertain diagnosis, adaptive teaching, fresh Transfer Check and provisional mastery estimates in LIVE_WALKTHROUGH_2026-10-14.md. No confirmed misconception or diagnostic probe claimed.
- [ ] Preserve the earlier gateway timeout status unless newer reliable completion evidence supersedes it. Health endpoints alone do not clear this gate.
- [ ] Verify real vision interpretation separately from image extraction if claiming vision success.
- [ ] Do not promote fixture or simulation results into live-model or real-student achievements.
- [x] Publication-safety review completed for tracked text/history and all three publishable binaries; no confirmed secrets or private documents found. Git author contact details and local username/path remain disclosed personal metadata for team acceptance.
- [x] Adopt README improvements and fix link prefixes; validate local documentation links.
- [ ] Fill team, YouTube, Devpost, final-source and deadline placeholders consistently.
- [ ] Obtain next approval before merging into main, changing repository visibility or deploying. The integration and documentation-only commit/push were authorized; deployment is not one of the supplied mandatory requirements.
