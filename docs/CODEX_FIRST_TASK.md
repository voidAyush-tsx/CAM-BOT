# Codex First Session — Audit & AY-13 Independent Replay

## Opening request to Codex

You have taken over the CAM-BOT repository. Read `AGENTS.md`, `docs/CODEX_CONTEXT.md`, `docs/STATUS.md`, `docs/ayush/README.md`, `docs/ayush/ledger.json`, `docs/ARCHITECTURE.md`, `docs/INTERFACES.md`, `docs/VALIDATION.md`, and `experiments/machine_tending/README.md`. Begin with a **read-only** repository audit. Check current branch, HEAD, tree cleanliness, installed toolchain and discrepancies from the 2026-10-15 evidence. Do **not** rewrite AY-01–12 or claim controller verification. Propose the smallest way to obtain an independent second-person AY-13 quick-start repeat. Perform checks only if environment supports them, record exact outputs. Distinguish a reproducible plan from observed evidence. Preserve sealed experiment data. Finish with findings, commands, blockers and a small suggested PR plan.

## Session 1 read-only inventory

```bash
git status --short --branch
git rev-parse HEAD
git remote -v
find src -maxdepth 3 -type f | sort | head -100
sed -n '1,180p' docs/STATUS.md
sed -n '1,240p' docs/ayush/README.md
sed -n '1,180p' experiments/machine_tending/README.md
```

## AY-13 acceptance gates

1. A genuinely separate **clean checkout**, correct branch, Git LFS, Ubuntu 22.04 / ROS Humble and dependencies.
2. `colcon build --base-paths src ...` and `colcon test --base-paths src ...` pass with recorded versions and outputs.
3. Expanded Xacro and `check_urdf` succeed; installed package assets/executables exist.
4. Visual launch starts and ROS node/topic graph is inspected; verify **one** `/joint_states` publisher.
5. Manually trigger a one-shot cycle; observe FSM, workpiece reaching `FINISHED_AT_S5`, and coordination decisions; capture evidence without claiming physical actuation.
6. Run checker and analyzer into new output directory; record any differences and failed/skipped gates.
7. A second person is clearly identified as reviewer and signs off with reproducible evidence. Merely having Codex reread documentation is **not** an independent human repeat.
8. Only after independently observed acceptance evidence, update ledger/status with provenance and tests. Otherwise leave AY-13 in progress.

## Suggested reviewer record (create only after actual replay)

```markdown
# AY-13 Independent Clean Checkout Review
Reviewer ID:
Date / timezone:
Repository URL / branch / HEAD:
Clean checkout path:
Host / container / ROS version:
Git LFS / dependencies:
Commands executed:
Observed results (logs/evidence paths):
One /joint_states publisher verified? (method + output):
FSM + FINISHED_AT_S5 observed? (method + output):
Metrics regenerated in new directory? (path/results):
Deviations / skipped gates / failures:
Conclusion: PASS / FAIL / BLOCKED
Reviewer acknowledgement:
```

## What to do next if no ROS runtime or independent reviewer exists

Give the user one consolidated Ubuntu/Distrobox command block and a checklist; do not represent it as a completed verification. You may still validate documentation links or write tests locally if dependencies are available, noting exact limits.
