# CAM-BOT to Codex: handoff package

Git repository: **https://github.com/voidAyush-tsx/CAM-BOT**

This package contains only Codex instructions and context, **not the actual git repository source files**. To work on the code, Codex must open/clone the repository. It was assembled from the repository's October 15 documentation and project engineering history, without executing a new ROS validation.

## Contents

- `AGENTS.md` — permanent Codex instructions; place in the **actual repository root**.
- `docs/CODEX_CONTEXT.md` — architecture, implementation history, evidence, debugging, experiment results, remaining work.
- `docs/CODEX_FIRST_TASK.md` — copy-paste onboarding request and AY-13 independent review gates.
- `scripts/setup_handoff.sh` — convenience script for copying these files into an existing checkout (no changes to other files).

## Workflow

1. Clone `https://github.com/voidAyush-tsx/CAM-BOT.git` in Codex's workspace, selecting the correct branch after checking remote branch history. Do not assume `main` already contains everything from the October 15 feature branch.
2. Copy `AGENTS.md` into the repo root and context guides into `docs/`. Avoid overwriting existing handoff files without reviewing differences.
3. Start Codex with the request from `docs/CODEX_FIRST_TASK.md`.
4. Require real test evidence before changing repository statuses or merging.

You can add handoff docs to a feature branch and open a PR; the bundled files have **not** been pushed to GitHub.
