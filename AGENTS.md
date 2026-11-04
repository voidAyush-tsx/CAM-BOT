# CAM-BOT — Codex Agent Instructions

Read `docs/CODEX_CONTEXT.md` and `docs/CODEX_FIRST_TASK.md` before editing. This file is intended for the **root of the actual CAM-BOT checkout**. If you received this in a handoff bundle, copy it to the repository root and copy the other handoff docs into the corresponding `docs/` paths.

## Project identity
CAM-BOT (Carrier-assisted Adaptive Manipulation with Bimanual Operational Technology) is a ROS 2 Humble **visual simulation** of a UR5 carrier transporting a flange-mounted four-joint bimanual placeholder through a five-station CNC machine-tending task. The integration is *not* verified controller actuation or grasp physics.

## Source of truth and precedence
1. Actual checked-out source code, tests, experiments, and observed runtime behavior.
2. `docs/STATUS.md` (the **only authoritative** AY/phase status matrix), `docs/ayush/ledger.json`, `docs/ayush/README.md`.
3. `docs/ARCHITECTURE.md`, `docs/INTERFACES.md`, `docs/VALIDATION.md`, `docs/DECISIONS.md`, experiment `README.md`.
4. This Codex handoff is orientation material. If it conflicts with live repository, inspect and report the discrepancy; do not silently replace the source of truth.

## Environment and commands
- Target: Ubuntu 22.04 / ROS 2 Humble, on CachyOS host via `cambot-humble` Distrobox when appropriate.
- Build/test **only under `src/`**: archived experiment captures contain duplicate ROS package names.
- `source /opt/ros/humble/setup.bash`; `rosdep install --from-paths src --ignore-src -r -y`;
  `colcon build --base-paths src --symlink-install --packages-select carrier_description carrier_control`;
  `colcon test --base-paths src --packages-select carrier_description carrier_control`.
- To source workspace under Bash `set -u`: `export COLCON_TRACE=; set +u; source install/setup.bash; set -u`.
- Wayland/niri RViz workaround: `QT_QPA_PLATFORM=xcb`, `LIBGL_ALWAYS_SOFTWARE=1`.
- Demo: `ros2 launch carrier_description dual_arm_demo.launch.py auto_start:=true enable_coordination:=true trial_count:=1 visual_time_scale:=1.0`.
- This launch is a visual joint-state simulator, not a Gazebo/controller demonstration.

## Nonnegotiable engineering rules
- Inspect before editing. Preserve pre-existing work, tests and historical provenance; use feature branches and reviewable changes.
- **Do not modify the official UR5 chain above `tool0`.** CAM-BOT attaches `tool0 → carrier_flange → carrier_flange_interface → dual_arm_base_link`.
- The placeholder has `left_shoulder_joint`, `left_elbow_joint`, `right_shoulder_joint`, `right_elbow_joint` (shoulder Z, elbow X), with no validated coordinated grasp.
- `src/carrier_control/config/machine_tending.json` is the installed configuration authority; geometry and `visual_carrier_joints` are visual assumptions. `carrier_joints` for S1–S4 are unvalidated, and S5's controller target is null.
- Never label visual joint publications as controller success. Never set `runtime_verified`, `end_to_end_verified`, `actuation_verified`, or `grasp_verified` true without appropriate evidence.
- Don't claim IK, collision checking, optimized trajectory, CNC physics, hardware performance, or quantitative improvement over a comparative baseline without implementation and evidence.
- Preserve sealed raw experiments: do not overwrite archives, checksums, manifests or derived published results. Regenerate into a new directory.
- Distinguish source, unit-test, live visual, controller-actuated and physical verification; report failures/skips precisely.
- Do not run duplicate `/joint_states` publishers. Visual mode's authoritative publisher is `machine_tending_coordinator`. Diagnose ROS graph before changing motion code.
- Prefer small deterministic changes, regression tests, runtime probes, documented outputs, and evidence-linked status updates. Never fabricate test execution.
- Ask before pushing/merging into shared `main` if authorization is not already explicit; do not force-push or destroy branches.
- Use `docs/STATUS.md` for task statuses and ledger for per-task evidence; avoid contradictory duplicated status matrices.

## First task
Check current branch/commit and compare to the 2026-10-15 handoff evidence. Inspect AY-13 independent-review acceptance criteria, then execute/document a **clean-checkout quick-start repeat** only if able to actually run it. If the environment cannot run ROS, provide static findings and a reproducible command plan; leave AY-13 IN PROGRESS. See `docs/CODEX_FIRST_TASK.md`.

## Response contract for engineering tasks
Report: (1) exact files inspected/changed; (2) observed facts vs assumptions; (3) tests run, command and pass/fail/skip; (4) evidence paths; (5) scope limitations; (6) next smallest safe step. When providing commands for a user to run, group them into one copy-pasteable block and clearly mark destructive steps.
