# Live ConceptLens walkthrough — 14 October 2026

## Verification scope

An operator demonstrated the integrated ConceptLens application locally using direct OpenAI requests and a processed MIT algorithms lecture. The learner responses were deliberately simulated for the demonstration.

This record supplements, rather than replaces, the historical integration verification report.

## Observed results

| Stage | Observed result |
| --- | --- |
| Source inspection | Original lecture video and timestamped transcript displayed |
| Grounded Ask | Quadratic complexity explained with a video citation at 00:27–00:32 |
| Assessment | A source-linked, verified question was generated |
| Initial answer | Deliberately incorrect response: 3 instead of 9 |
| Reasoning analysis | Completed; no clear reasoning break found |
| Teaching | Source-backed, step-by-step concept explanation displayed |
| Transfer Check | Fresh 225-operation problem; answer 15 graded correct |
| Mastery | Estimated 13% after one observation and 46% after two |
| Dashboard | Two verified observations reflected in the learner record |

The first reasoning-diagnosis request failed because the direct OpenAI adapter did not include the required JSON instruction in its request input. The corrected adapter passed four targeted regression tests and the subsequent walkthrough succeeded. Fix commit: `d0da5f9`.

## Evidence

The actual application screenshots are stored in `../assets/screenshots/`.

The CPU Scheduling prerequisite graph is a separate curated-course example, not part of the MIT lecture assessment sequence.

## Boundaries and limitations

- No specific misconception was verified in this walkthrough.
- A diagnostic probe and confirmed-misconception repair were not demonstrated.
- The alternative "Still confused" teaching path was not tested here.
- The mastery percentages are provisional model estimates, not measured learning gains.
- Broader provider reliability, real vision-quality evaluation and real grounding framework scores remain pending.
- This was an operator-run demonstration, not a real-student study.
- The older compatible-gateway completion issue remains separate from the successful direct OpenAI path.

See [historical integration verification](INTEGRATION_VERIFICATION.md) for the automated testing scope. The final demo video is handled separately.
