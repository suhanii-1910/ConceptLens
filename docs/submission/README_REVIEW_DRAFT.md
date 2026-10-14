# README review reconciliation

The proposed README from documentation commit `ac36dd4` has been reconciled into the [root README](../../README.md), which is now the canonical setup and product document. The original proposal remains available in Git history at that commit.

Applied corrections:

- Integrated Observatory identity, automated tests and the subsequent successful direct OpenAI walkthrough. Historical gateway limitations remain separate.
- Default frontend/backend ports 5174/8001, with a separate local integration frontend on 5175.
- Compatible and direct provider modes described as implemented configurations, not model-access guarantees. Existing gateway settings and credentials were not changed.
- Explicit provider isolation for the older disposable demo helper.
- Safe environment setup, migration cautions and corrected links at the repository root.
- Historical simulation/evaluation disclosure retained from the previous root README.
- Real screenshots have been added locally; team details, final video and deadline information still require completion.

See [current integration verification](INTEGRATION_VERIFICATION.md) for exact commands and scope. The publication audit and fresh dependency installation/build/runtime checks passed; see the [follow-up results](INTEGRATION_VERIFICATION.md#publication-and-clean-install-follow-up) for platform/cache scope and personal-metadata disclosures. A successful live OmniRoute AI journey remains unverified. The [README AI coding-assistant disclosure](../../README.md#ai-coding-assistant-disclosure) identifies OpenAI Codex and the evidenced assisted work.

## Model API and gateway configuration

Use the [canonical model configuration](../../README.md#model-api-and-gateway-configuration).

## Try the application

Use the [canonical application instructions](../../README.md#try-the-application), including the disposable helper caveat.
