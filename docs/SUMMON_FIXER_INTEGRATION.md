# Summon Fixer in ConceptLens (opt-in development integration)

This integration is experimental. It is **disabled by default** and is not included
in ConceptLens production builds. It integrates only the React/Vite frontend,
not the FastAPI backend, PostgreSQL, or external services.

## Prerequisites

- Node 24+ for Summon Fixer; its npm workspace is independent of ConceptLens.
- A local checkout of `GODLIKEyp/Summon-Fixer-` at a verified, built revision.
- A working Codex CLI login and remaining usage for real proposals.
- A **disposable ConceptLens checkout**, not your primary learning-data workspace.
  Keep real credentials and real course/learner data out of this test checkout.

## Start

Use two terminals. Do not run this against production and do not expose the dev
server or its loopback bearer token over a public interface.

### Terminal 1 — build Summon Fixer

```sh
cd ~/Projects/Summon-Fixer-
git status --short --branch
npm ci
npm run build
```

### Terminal 2 — start ConceptLens using Summon's engine

In a separate **disposable ConceptLens checkout** containing this integration:

```sh
cd /path/to/disposable/ConceptLens/frontend
npm ci
npm run build
CONCEPTLENS_SUMMON=1 \
SUMMON_FIXER_ROOT="$HOME/Projects/Summon-Fixer-" \
CODEX_BIN_PATH="$(command -v codex)" \
node "$HOME/Projects/Summon-Fixer-/packages/cli/dist/bin.js" dev \
  --port 7890 --proposal-timeout-ms 120000 --command "npm run dev"
```

Open `http://127.0.0.1:5174`. If the port is taken, stop that process or
override Vite's port in a separate, deliberate step (do not accidentally take
over another live application). Backend/API proxy continues to use
`CONCEPTLENS_API_PROXY_TARGET` (default `127.0.0.1:8001`).

To test with **no model calls**, append `--fake` to the Summon CLI arguments.
Fake proposals are test fixtures, **not** real AI edits.

The Summon process launches ConceptLens's `npm run dev`, providing
`SUMMON_ENGINE_URL`, `SUMMON_ENGINE_TOKEN`, and
`SUMMON_WORKSPACE_ROOT` to the dev server only. Do not copy these to
`VITE_*` variables or the browser.

## Scope, compatibility and safety

- The Vite plugin annotates intrinsic JSX tags with verified source IDs/revisions.
  Select DOM elements on Workspace / Ask / Learn / Practice / Dashboard and check
  mapping before submitting a proposal.
- The overlay and session-protected bridge exist **only in Vite dev mode**.
  Production `npm run build` should contain no Summon client script or token.
- The plugin and ConceptLens use **different installed Vite major versions**
  (Summon Vite 8; ConceptLens Vite 7). This experimental cross-project wiring
  has **not** been verified by a live browser smoke test, so resolve any
  dependency or plugin typing differences before claiming acceptance.
- Approved application is currently disabled by Summon's
  `SAFE_WRITE_UNAVAILABLE` safety gate. Even when Codex generates a
  plausible patch, **approval does not edit ConceptLens source files**.
  Manual review/rejection and read-only planning are the currently supported
  integration targets; do not bypass the gate.
- Keep Auto Apply disabled. Do not use live learner data or commit secrets.
  Backend files, database migrations and multi-file edits are outside the MVP.
- To disable the integration, run ConceptLens normally without
  `CONCEPTLENS_SUMMON=1`. Do not remove the normal React plugin or API proxy.

## Verification checklist

1. `cd frontend && npm run typecheck && npm test && npm run build`
   with Summon disabled.
2. Test `CONCEPTLENS_SUMMON=1` with `--fake` in the disposable checkout.
3. Verify overlay, source mapping and one simulated Plan Only response.
4. Verify the actual approval review and reject, with no files modified.
5. Inspect production `dist` for injected overlay markers; confirm absence.
6. Attempt one real Codex proposal only with explicit consent for model usage,
   inspect the proposed source and **reject** it.
7. If any compatibility or validation check fails, switch the integration off
   and retain ConceptLens's normal dev mode.

No live test has yet established compatibility or successful source application
in ConceptLens.
