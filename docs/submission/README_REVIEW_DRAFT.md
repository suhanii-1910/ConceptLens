# README review reconciliation

The proposed README from documentation commit `ac36dd4` has been reconciled into the [root README](../../README.md), which is now the canonical setup and product document. The original proposal remains available in Git history at that commit.

Applied corrections:

- Integrated Observatory identity and current test evidence; live AI acceptance remains blocked.
- Default frontend/backend ports 5174/8001, with a separate local integration frontend on 5175.
- Compatible and direct provider modes described as implemented configurations, not model-access guarantees. Existing gateway settings and credentials were not changed.
- Explicit provider isolation for the older disposable demo helper.
- Safe environment setup, migration cautions and corrected links at the repository root.
- Historical simulation/evaluation disclosure retained from the previous root README.
- Team, video, deadline and curated screenshot placeholders remain incomplete.

See [current integration verification](INTEGRATION_VERIFICATION.md) for exact commands and scope. Clean-clone dependency installation and a successful live AI journey are still unverified.

## Model API and gateway configuration

Use the [canonical model configuration](../../README.md#model-api-and-gateway-configuration).

## Try the application

Use the [canonical application instructions](../../README.md#try-the-application), including the disposable helper caveat.
