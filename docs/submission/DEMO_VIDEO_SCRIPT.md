# ConceptLens demo video script

**Target: 4 minutes 40 seconds · English narration · actual running application.** The supplied requirement is 3–10 minutes on YouTube, Public or Unlisted. The team will record and upload. This document is a script, not a recorded demonstration.

**Current gate:** the final Observatory frontend is integrated and its browser checks pass. Successful live-provider evidence is still unavailable. Use the failure alternative for any AI operation that has not actually succeeded; do not infer success from the passing fixture suite. See [current verification and run commands](INTEGRATION_VERIFICATION.md).

## Recording preparation

- Use the [README setup](README_REVIEW_DRAFT.md) and final intended commit. Confirm course loading, source processing/indexing and previews. Rehearse the chosen provider mode through an actual completion, not just a health endpoint.
- Prefer the authored CPU Scheduling course and its general SRTF rule. The disposable helper supplies real PDF evidence and explicitly curated concepts/prerequisites, not learner history. Observe its routing caveat: provider-unconfigured runs must explicitly force `CONCEPTLENS_PROVIDER_MODE=compatible`; `--with-provider` expects securely exported compatible settings.
- Use an actual app window at a readable desktop resolution. Enable a fresh local learner if needed using **Reset demo learner**; this changes the browser UUID, not backend history. Keep notifications and private terminals out of frame.
- Prepare a source to upload, an existing processed source for inspection, and the final architecture diagram. Clearly announce when moving between courses or previously processed sources.
- For each success segment below, first establish that the displayed result actually exists. Generation can return a different question or decline; adapt the answer/reasoning to the real question. Never paste the sample reasoning against an unrelated item.
- Record a voice track at a measured pace, leaving time for clicks and reading. The timestamps are editing targets, not claims about response latency. Trim waiting only with an on-screen “wait shortened” caption. Keep the exported duration between 3 and 10 minutes; use 4:40 as the rehearsal target.

## Timed narration and screen direction

### 0:00–0:20 — Concept Observatory opening

**Display/actions:** Open `/?intro=1` on the actual integrated frontend to show the Observatory introduction. Use **Skip intro** to enter Workspace, then point to its five learning modules and selected course. Capture the real rendered motion or use **Pause motion**; do not substitute a generated mockup.

**Exact narration:**

> “This is ConceptLens: learn anything, debug your understanding. We connect the material a student is studying to the next learning action. The application has five connected spaces: Workspace, Ask, Learn, Practice and Dashboard.”

**Transition:** Direct cut to source inventory at the same browser scale.

### 0:20–0:45 — The problem and the approach

**Display/actions:** Show the general CPU Scheduling source and the rule about remaining time. Point to the rule without adding a fabricated citation or highlight inside the product.

**Exact narration:**

> “A clear AI answer can still leave the original misconception untouched. A student may repeat an explanation without being able to solve a different problem. ConceptLens is designed to connect source evidence, the student's answer and reasoning, targeted teaching, and a fresh check of understanding. The decision to teach something should be inspectable.”

**Transition:** Return to Workspace with a normal in-app click.

### 0:45–1:30 — Upload, process and inspect study material

**Display/actions:** Click **New course**, enter a public-safe course name, click **Create course**, and use the file picker to upload a real PDF. Click **Process**, wait for the result, then **Index course material**. Open **Inspect source evidence** and an exact page preview. For the later learning sequence, explicitly select the prepared CPU Scheduling course with curated concepts. If processing takes longer, shorten the wait with a caption or use the fallback below. Optionally show real PPTX/MP4 entries only if they exist.

**Exact narration:**

> “I start with a real course document. Uploading saves the source; processing extracts evidence, and indexing makes its text searchable. Each evidence item keeps its page, slide or timestamp so we can inspect where it came from. Here is the actual PDF page. The implementation also supports presentations and video transcription with extracted frames. An extracted image is not automatically an understood image: visual interpretation needs a configured model, a separate verification call, and re-indexing. For the learning sequence, I am switching to our prepared scheduling course, whose concept links were explicitly curated.”

**Transition:** Close the source dialog and click **Ask**. Keep source/course continuity visible.

### 1:30–2:00 — Ask and inspect the evidence

**Display/actions:** Type “In SRTF, what should I compare when a new process arrives?” Click **Ask ConceptLens**. If it returns a supported answer, expand its citation and click **Open exact source**. Show the actual page. Do not claim a response from a spinner, error or fixture.

**Exact narration — only after actual success:**

> “I ask what to compare when a new process arrives. The answer should be grounded in this course's evidence. Here, I can inspect the citation and open its exact source location. The backend checks returned evidence references against the allowed context. When evidence is insufficient, it declines instead of inventing a course citation.”

**Provider need:** Live text completion. If unavailable, use the matching replacement narration below.

**Transition:** Close the viewer and click **Learn**; label any trimmed provider wait.

### 2:00–2:55 — Reasoning diagnosis and adaptive teaching

**Display/actions:** In Learn, request an SRTF problem with **Find me a problem**. Use the actual verified question. If it matches P1 arrival 0/burst 8 and P2 arrival 5/burst 4, select the original-burst distractor and click **Record my answer**. Enter “I chose P2 because its burst is 4 and P1's burst is 8, so 4 is shorter.” Click **Debug my reasoning**. Answer the displayed probe and click **Test the hypothesis**. Show the actual diagnosis status, offered teaching, source citation and, if reached, **Still confused** and a changed strategy. A prerequisite branch is conditional; do not force or invent it.

**Exact narration — only for the steps actually reached:**

> “In Learn, a question must pass verification before I answer it. I then explain my own reasoning. For this scheduling rule, the key distinction is original burst time versus remaining time. ConceptLens treats a possible reasoning break as a hypothesis, not a permanent label. A diagnostic probe can confirm it, reject it, or leave it unresolved. The backend chooses a teaching strategy and asks the model for source-backed content. Feedback can lead to a different strategy, and prerequisite support needs a recorded, evidence-backed relationship. An unresolved diagnosis is not silently changed into a confirmed one.”

**Provider need:** Question generation/verification, diagnosis/probe generation/verification and teaching generation/verification. If these cannot all fit, show a transparently labeled recording from the real rehearsal or use the unavailable version; do not imply instant completion.

**Transition:** Finish on the true session status, then click **Practice**.

### 2:55–3:30 — Practice and feedback

**Display/actions:** Choose **Numerical** or **Short answer** in Practice, generate a verified item and submit a response matching the displayed question. Reveal the actual feedback. Numerical scheduling proof appears only after grading when the question has a scheduling contract. For the requested P1(0,8)/P2(5,4) completion-time example, enter `8` only if that is the actual question and required unit is supplied. Do not claim the prompt guarantees the item.

**Exact narration — after actual generation and grading:**

> “Practice supports multiple-choice, short-answer and numerical questions. Answer keys remain on the server until submission. Multiple-choice and numerical grading are deterministic; supported scheduling questions use the backend's solver. Short answers use a source-constrained evaluator, which can say it cannot grade. That distinction matters: an unavailable evaluator must not become a correct answer or a mastery gain. This is the actual feedback for the response I submitted.”

**Provider need:** Generation and verification for all new items; live semantic evaluation for short answers. MCQ/numerical grading itself is deterministic.

**Transition:** Return to Learn's actual session for transfer, then navigate to Dashboard.

### 3:30–4:05 — Transfer, trace and Dashboard

**Display/actions:** If the session offers a fresh **Transfer Check**, submit it using **Verify my understanding**. Show its actual result, then open **Why did ConceptLens do this?**. Click Dashboard; show observed versus Untested concepts and any actual mastery observation. A Practice question is not a substitute for the session's persisted Transfer Check. If transfer was not reached, use the unavailable narration.

**Exact narration — only after an actual transfer attempt:**

> “The Transfer Check tests the same rule in a fresh problem. We show the real outcome, including failure. The Learning Trace connects the original attempt, diagnosis, strategy choices and verification. Dashboard separates observed evidence from untested concepts. Eligible graded attempts can update the mastery estimate; simply reading an explanation cannot. With few attempts and uncalibrated defaults, these estimates are provisional, not proof of improved learning.”

**Provider need:** Fresh transfer generation/verification. Mastery requires a real eligible graded attempt; show a skipped update honestly if that is the result.

**Transition:** Brief dissolve to the architecture diagram, labeled “Implementation architecture.”

### 4:05–4:40 — Architecture, evidence and conclusion

**Display/actions:** Show the overall diagram from [ARCHITECTURE.md](ARCHITECTURE.md), then return to the running Workspace. End with the final repository URL and project title. Do not expose provider settings or private terminals.

**Exact narration:**

> “The application combines React and TypeScript with FastAPI, PostgreSQL and pgvector. Local embeddings support retrieval, while configured providers supply generated content. Automated tests cover the software contracts, but fixture success is not live AI acceptance. Our remaining work includes validating the full provider journey, improving format coverage and evaluating outcomes with real learners. ConceptLens is built around evidence that a learner can inspect, and learning decisions that can be checked. Thank you for watching.”

If a new reliable record has verified the full journey before recording, replace “validating the full provider journey” with “expanding real-provider evaluation.” Keep other limitations unless supported by newer evidence.

## Complete fallback narration for provider failures

Use the **same timestamps** and the unchanged opening/problem/architecture sections. Show actual working ingestion/previews and the real unavailable states. Do not leave the audience expecting a completed learning loop. The passages below replace the indicated success segments and maintain time for navigation and reading.

| Segment | Actual display/actions | Exact replacement narration |
| --- | --- | --- |
| 0:45–1:30, if new ingestion is unavailable | Show the real failure, then explicitly select a previously processed real source and open its page/evidence. | “This new upload has not completed processing, so I am showing a real source processed earlier. Its evidence and original page are available here. Processing and indexing are separate steps; I am not presenting the earlier result as a new upload success. The repository contains historical real PDF ingestion and embedding evidence. We still need a fresh acceptance run on the final build. Extracted images and frames also remain distinct from accepted visual interpretation.” |
| 1:30–2:00 | Show the actual Ask error/refusal, then return to the source preview through Workspace. | “This provider request did not produce a verified working answer in this recording. Earlier gateway completion requests also reportedly timed out despite reachable health endpoints. I can still inspect the actual source evidence here. The generated answer remains unverified; this source preview is not a substitute for a successful completion.” |
| 2:00–2:55 | Navigate to Learn and show its real empty/error state. If unavailable, use the labeled architecture flow beside the app, without creating fake results. | “The reasoning and adaptive-learning pipeline is implemented and covered by automated fixtures, but I cannot demonstrate successful live diagnosis in this recording. Its intended sequence is an assessed response, the learner's own explanation, a tentative hypothesis, and a diagnostic probe. The policy can then select source-backed teaching or a fresh check. Those are implementation capabilities, not results achieved here. I am showing the actual unavailable state rather than a simulated learner history. The next acceptance step is to run the entire sequence with an authorized provider and retain the real diagnosis, teaching and transfer records.” |
| 2:55–3:30 | Open Practice, attempt generation once, and retain the actual unavailable state. If an existing real item is used, label it as previously generated. | “Practice exposes the supported assessment types, but this new question has not been generated and verified successfully. Deterministic grading and scheduling logic have automated coverage; that does not establish live question generation or semantic grading. A saved question would need to be identified as previously generated. We are not substituting a fixture or showing a fabricated grade.” |
| 3:30–4:05 | Open Dashboard and show Untested/empty data and recorded concept relationships. Do not create a fake mastery delta or transfer result. | “Because the generated learning journey is unavailable, this recording contains no completed Transfer Check or new mastery gain. Dashboard shows the evidence actually present, including untested concepts and curated source relationships. Untested does not mean weak. The implemented update rules require an eligible graded attempt. We will verify that link and the session trace in a real provider run before claiming end-to-end success.” |

## Editing and backup rules

1. **Preferred:** record a genuine successful rehearsal on the final integrated application. If shown later, label it “Recorded application session” with the capture date; do not narrate it as a new live request.
2. **If a request fails during recording:** show the actual error, then either use the failure version or cut to a clearly labeled previously recorded real session. State that the live request failed. Do not splice a historical response into the failed request as though it completed.
3. **If no successful real session exists:** use the fallback script. Spend the remaining screen time on real source evidence, application states and the labeled implementation diagram. No fixture demonstration is needed to satisfy this script.
4. **If fixtures are included for explanation:** keep “API FIXTURE — NOT LIVE AI” visible throughout and explain that these are test states. They cannot satisfy a claim that the generated learning workflow works.
5. The final video must still show the actual running application and accurately represent how much works. A limitation disclosed in narration is better than an unsupported success claim, but it does not remove the team's need to review the final submission quality.

## Export and upload

Review captions, pointer visibility, legibility and audio; verify total duration is **3–10 minutes** with English narration or subtitles. Upload to YouTube as **Public or Unlisted**, never Private. Test the link while signed out. Insert the final URL into the README draft, Devpost description and submission checklist. The actual upload is the team's task.
