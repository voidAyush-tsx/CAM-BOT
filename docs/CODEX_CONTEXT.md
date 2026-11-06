# CAM-BOT — Comprehensive Codex Context and Continuation Guide

**Prepared:** 2026-11-04. **Repository:** https://github.com/voidAyush-tsx/CAM-BOT (default branch: `main`).

> **Provenance:** This handoff combines past engineering conversation notes with a GitHub review of repository files such as `README.md`, `docs/STATUS.md`, `docs/ayush/README.md`, `docs/ARCHITECTURE.md`, `docs/VALIDATION.md`, `experiments/machine_tending/README.md`, `src/carrier_description/launch/dual_arm_demo.launch.py`, `src/carrier_control/carrier_control/machine_tending_coordinator.py`, and `src/carrier_control/config/machine_tending.json`. These were read from the repository at handoff time. This guide originated in a handoff bundle; it is now stored in the actual repository. No local ROS test was run during its generation. The October 15 feature work was merged, reverted and restored before the November 4 handoff commit. `main` is the repository default branch; `work` is a local Codex task branch. Verify the exact checkout/review commit; the actual source is definitive.

## 1. Goal, user intent, and completion boundary

CAM-BOT = **Carrier-assisted Adaptive Manipulation with Bimanual Operational Technology**. Learning/prototype project also described as **Adaptive Dual-Arm Robotics for Efficient CNC Automation**. Objective: a large **UR5 carrier** positions a flange-mounted small dual-arm module at useful workcell locations; the local arms then execute a simulated tending sequence. Coordination decides whether target is locally reachable or whether carrier repositioning is required. Target demonstrator: five-station visual CNC tending, repeatability, logging, analysis, evidence.

**This is not** an industrial automation stack, force-controlled gripper, collision-aware MoveIt plan, real CNC process, or mechanically validated deployment. The core deliverable is an evidence-backed ROS 2 visual simulation. Extensions (better IK/planning, controller-backed simulation, physical grasping, real-world hardware) may be considered only after the existing demonstration and documentation are stable.

## 2. Team responsibilities (historical documentation)

- **Ayush:** software/digital systems, integration, carrier-vs-dual-arm coordination, reachability, machine-tending FSM, GitHub, tests, logging, experiments, plots, documentation, presentation. AY-01 through AY-13 are his core tracked IDs.
- **Shanmukha:** manipulator kinematics/control, ROS robotics architecture/integration.
- **Tanmay:** mechanical/carrier/CAD and workcell structure.

Do not assume other team members' source is missing or redesign their work without evidence. Team ownership may evolve; honor actual repository contribution standards and user direction.

## 3. Current documented status — critical chronology

Past project notes originally described the carrier baseline as stable but Phase 4, coordination and experiments incomplete. **These notes are historical**, not the current state. Subsequent implementation, runtime debug and October 15 captures advanced the project substantially.

As recorded by **`docs/STATUS.md`, updated 2026-10-15**:

| Task | Repository disposition | Scope |
|---|---|---|
| AY-01 | COMPLETE | Phase 4 source integration |
| AY-02 | COMPLETE | Package/build/install and repository integration |
| AY-03 | COMPLETE | Visual single-command launch; gated controller entry point |
| AY-04 | COMPLETE | Five-station visual workcell |
| AY-05 | COMPLETE | One-shot visual tending FSM |
| AY-06 | COMPLETE | Visual coordination / reposition decisions |
| AY-07 | COMPLETE | Both-arm geometric workspace proxy |
| AY-08 | COMPLETE | Integrated visual cycle |
| AY-09 | COMPLETE | Structured logging |
| AY-10 | COMPLETE | Five qualifying visual attempts |
| AY-11 | COMPLETE | Event-derived visual metrics |
| AY-12 | COMPLETE | Reproducible plots/tables |
| AY-13 | IN PROGRESS | Documentation and cross-validation; blocked on independent second-person clean-checkout quick-start repeat |

**Do not re-implement AY-01–12 automatically.** Audit first; fix only demonstrated defects. The 2026-10-15 status, ledger and actual checkout trump older conversation summaries, including older claims that AY-10–13 remained undone.

## 4. Architecture, robot and workcell

```text
world
├── base_link → UR5 official chain → wrist_3_link → flange → tool0
│    → carrier_flange → carrier_flange_interface → dual_arm_base_link
│      ├── left_upper_arm → left_forearm
│      └── right_upper_arm → right_forearm
├── station_s1_raw
├── station_s2_staging
├── station_s3_machine
├── station_s4_output
├── station_s5_finished
└── workpiece (visual world-referenced prismatic xyz joints)
```

UR5: 6 revolute joints (shoulder pan/lift, elbow, wrist_1/2/3). Dual-arm placeholder: four custom joints, shoulders rotating around Z and elbows around X. Flange and interface are fixed transforms attached **below `tool0`**, preserving upstream official UR description. The workpiece is a visual kinematic model with logical state; it is not attached through physical grasp constraints. Neither true bimanual IK nor force closure is established.

Five stations: S1 RAW_INPUT, S2 STAGING_INSPECTION, S3 CNC_MACHINE, S4 OUTPUT_UNLOADING, S5 FINISHED_PART. All pose/dimension data are **temporary visual simulation assumptions** in `src/carrier_control/config/machine_tending.json`, not surveyed CAD coordinates. Important config separation: `visual_carrier_joints` were calibrated for RViz; `carrier_joints` S1–S4 remain legacy, `controller_validated=false`; S5 controller pose is `null`.

## 5. ROS packages, launch and software interfaces

Repository topology (verify exact paths from checkout):

```text
CAM-BOT/
├── README.md
├── CONTRIBUTING.md
├── src/
│   ├── carrier_description/
│   │   ├── urdf/                  # UR5 wrapper, flange, dual-arm, workcell Xacros
│   │   ├── launch/                # dual_arm_demo.launch.py and gated controller launch
│   │   └── rviz/                  # RViz configs
│   └── carrier_control/
│       ├── carrier_control/       # coordinator, FSM, policy, reachability, metrics
│       ├── config/                # machine_tending.json and installed waypoints.yaml
│       └── test/
├── docs/
│   ├── STATUS.md                 # ONLY task status matrix
│   ├── ARCHITECTURE.md
│   ├── INTERFACES.md
│   ├── VALIDATION.md
│   ├── DECISIONS.md
│   ├── ayush/README.md
│   ├── ayush/ledger.json
│   └── evidence/
├── experiments/
│   └── machine_tending/
│       ├── README.md
│       ├── runs/ay10-visual-20261015-03/
│       ├── scripts/analyze_trials.py
│       └── tests/
├── artifacts/verification/cambot_build_report.json
└── tools/
```

The primary **visual** launch is `ros2 launch carrier_description dual_arm_demo.launch.py auto_start:=true enable_coordination:=true trial_count:=1 visual_time_scale:=1.0`. It expands Xacro via workcell model, launches `robot_state_publisher`, `machine_tending_coordinator`, and RViz. The coordinator publishes assumed `/joint_states`; `robot_state_publisher` produces `/tf` and `/tf_static`. In live visual tests **one `/joint_states` publisher** should exist, the coordinator. A legacy `dual_arm_cycle` is separate and must not be launched concurrently with the FSM. The controller entry point fails closed with current unvalidated station targets and absent selected bring-up.

`machine_tending_coordinator.py` uses ROS 2 `rclpy`, `CoordinationPolicy`, `MachineTendingFSM`, TF and geometric `evaluate_reachability`, `ExperimentLogger`, and a gated `FollowJointTrajectory` client in controller mode. Relevant interfaces observed in source/documentation:

- Service: `/machine_tending_coordinator/start` (`std_srvs/srv/Trigger`), plus reset and cancel under same node namespace.
- Topics: `/joint_states`, `/tf`, `/tf_static`, `/cambot/task_state`, `/cambot/workpiece_state`, `/cambot/coordinator_state`, `/cambot/coordination_decision`.
- Visual launch args: `auto_start`, `enable_coordination`, `trial_count`, `visual_time_scale`, `config_file`, `results_file`, `experiment_id`, `fault_injection_step`.
- Configuration: `src/carrier_control/config/machine_tending.json` authoritative installed source; root `config/waypoints.yaml` is a mirror, while installed `src/carrier_control/config/waypoints.yaml` serves legacy carrier motion.

## 6. Task sequence, workpiece states, and coordination policy

FSM states:

```text
HOME → PICK_RAW → STAGE → LOAD_MACHINE → MACHINE_DWELL
     → UNLOAD_MACHINE → PLACE_FINISHED → HOME
```

12 workflow steps: `HOME_START`, `S1_APPROACH`, `S1_GRASP`, `S2_STAGE`, `S3_LOAD`, `S3_RELEASE`, `MACHINE_DWELL`, `S3_REGRASP`, `S4_UNLOAD`, `S5_PLACE`, `S5_RELEASE`, `HOME_END`.

Visual workpiece progression:

```text
RAW_AT_S1 → HELD_RAW_AT_S1 → HELD_RAW_AT_S2 → HELD_RAW_AT_S3
→ RAW_IN_MACHINE → PROCESSED_IN_MACHINE → HELD_PROCESSED_AT_S3
→ HELD_PROCESSED_AT_S4 → HELD_PROCESSED_AT_S5 → FINISHED_AT_S5
```

Coordination concept: compute target in `dual_arm_base_link` from live TF, evaluate against configured **both-arm bounding regions and radius proxy**; if locally reachable use `LOCAL_MANIPULATION`; else publish `CARRIER_REPOSITION`, move *visual carrier joint states* to configured calibrated station pose, await final TF and recheck. Limit reposition attempts (`max_reposition_attempts=1` currently). No inverse kinematics or collision checking is performed. Coordination should **fail closed** if target cannot be validated.

## 7. Historical debugging and exact root causes (AY-01 to AY-09)

These events occurred during CachyOS + ROS Humble Distrobox validation; treat them as historical diagnostics, **not** a claim that the current checkout still contains each defect.

| Symptom | Root cause | Resolution / rationale |
|---|---|---|
| `Invalid parameter "force_abs_paths"` in `ur_robot` Xacro macro | Wrapper used newer UR description API incompatible with Humble | Removed unsupported macro argument, then `xacro` and `check_urdf` passed |
| RViz: Qt platform plugin `wayland` unavailable | niri/Wayland host vs container Qt plugins | `QT_QPA_PLATFORM=xcb`; `LIBGL_ALWAYS_SOFTWARE=1` for software rendering |
| `TypeError: can only concatenate list (not "array.array") to list` | `JointState.position` field is an `array.array` in ROS Python | Convert to `list(message.position)` before concatenation |
| Duplicate/stale `/joint_states` publisher behavior | Residual processes or concurrent state publishers | Inspect `ros2 topic info /joint_states --verbose`; terminate only known stale processes; enforce one authoritative visual publisher |
| `UNREACHABLE` after reposition | Historical P1–P4 carrier pose mapping did not align with new S1–S5 simulated geometry | Calibrated visual UR5 station joints from expanded URDF; kept controller `carrier_joints` and validation flags unchanged |
| S3 miss around 0.35 mm near proxy X boundary | Reachability recheck observed an intermediate/stale TF before final carrier pose | Two-stage fresh TF synchronization / final-pose observation |
| `FINAL_TF_NOT_OBSERVED` | Exact final visual joint value was published only once and TF consumer sometimes missed it | Snap to exact final visual UR5 goal and republish final joint sample multiple times |
| Bash capture script `unbound variable` for `COLCON_TRACE` / `AMENT_TRACE_SETUP_FILES` | `set -euo pipefail` and ROS/Colcon setup scripts | Temporarily disable nounset while sourcing, set `COLCON_TRACE` as needed |

The original AY-06–08 capture is not retained, but later records exist in `docs/evidence/AY-06-08/runtime/`; that visual probe left child nodes. The subsequent `docs/evidence/AY-13/cross_validation/live_recheck/` records the repaired cleanup. These later runs do not recover the missing original capture. AY-09's original one-trial runtime directory remains absent; the later AY-10 dataset supplies integrated logger evidence. Keep each run's provenance distinct.

## 8. Measured experiment (AY-10–12)

Authoritative record: `experiments/machine_tending/README.md` and `runs/ay10-visual-20261015-03/`. Main fixed visual scenario on 2026-10-15 in Ubuntu 22.04 / ROS Humble `cambot-humble` on CachyOS:

- Five qualifying attempted cycles, **5 successes**, zero attempted failures in qualifying capture.
- Mean successful cycle time **19.579117 seconds**; median **19.585576**; min/max **19.551515 / 19.592351**, sample SD **0.016634**.
- Requested / accepted / completed **visual** carrier repositions **25 / 25 / 25** (5 per trial); visual HOME return counted separately.
- 530 structured node events across five trials; 12 workflow steps and 8 FSM state visits per success.
- Preliminary capture 01 had 1 success; capture 02 attempted 0 trials due to residual nodes; these are kept separate from qualifying capture 03. All actual attempted trials across preliminary + main = 6, all successful; only 5 belong to fixed main capture.
- Timing boundary: first `S1_APPROACH: STEP_STARTED` (first PICK_RAW) through `HOME_END: STEP_COMPLETED`, measured by node monotonic clock. Initial HOME/startup/reset excluded.
- Reported metrics describe observed visual-state publications, **not** action-server results, grasp correctness, physical throughput, energy savings, or improvements over a baseline.
- Source provenance is base commit **`6e77292e4fceca0636a4cd86a037bf9e7d64f93a` PLUS archived patch/snapshot**, not that commit alone. Keep raw artifacts immutable.

The repo includes raw `trials.csv`, `trials.events.jsonl`, `attempts.jsonl`, `topics.jsonl`, rosbag metadata, logs, checksums, RViz screenshot, derived tables/plots, hashes, acceptance and validation evidence. Scripts: `experiments/machine_tending/scripts/analyze_trials.py` and tests under `experiments/machine_tending/tests/`.

## 9. Development and verification (use checked-out README for freshest instructions)

Host: CachyOS Linux; container: Ubuntu 22.04/ROS 2 Humble Distrobox named `cambot-humble`. Linux graphical host used niri/Wayland; XWayland and software rendering for RViz. For independent repeat, **start from a separate clean checkout**, install Git LFS files and ROS dependencies, then run `rosdep`, scoped Colcon build/test, Xacro/URDF checks, visual launch and one-cycle observation. Script below is a non-destructive starter except for build outputs.

```bash
# On host, after checkout: distrobox enter cambot-humble -- bash
cd /path/to/CAM-BOT
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --base-paths src --symlink-install --packages-select carrier_description carrier_control
export COLCON_TRACE=
set +u
source install/setup.bash
set -u
colcon test --base-paths src --packages-select carrier_description carrier_control
colcon test-result --verbose
xacro src/carrier_description/urdf/ur5_with_test_tool.xacro > /tmp/cambot.urdf
check_urdf /tmp/cambot.urdf
python3 tools/check_ay13_docs.py --installed
python3 -m unittest discover -s experiments/machine_tending/tests -v
ros2 launch carrier_description dual_arm_demo.launch.py auto_start:=false enable_coordination:=true trial_count:=1 visual_time_scale:=1.0
```

Open another ROS-sourced shell to invoke `ros2 service call /machine_tending_coordinator/start std_srvs/srv/Trigger "{}"` and inspect `/joint_states` publisher count, `/cambot/task_state`, `/cambot/workpiece_state`, `/cambot/coordination_decision`. RViz should show five stations and workpiece, with `FINISHED_AT_S5` and `SUCCESS` at end. Use clean ROS domain / no residual nodes. **Running these in Codex's agent environment may be impossible without ROS/GUI; never claim tests passed unless actually executed.**

For archived plot regeneration, never overwrite sealed output:

```bash
analysis_output="$(mktemp -d /tmp/cambot-ay13-analysis.XXXXXX)"
python3 experiments/machine_tending/scripts/analyze_trials.py \
  experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv \
  --output "$analysis_output" --qualify
```

Inspect `docs/evidence/AY-13/cross_validation/README.md` and `artifacts/verification/cambot_build_report.json` before claiming all gates. Report skips and controller failures accurately. Historical reference: 48 offline regression tests (35 control + 13 description); later AY-13 documentation reports scoped Colcon test outcomes plus separate analysis tests. Do not confuse archived logs with tests rerun today.

## 10. Critical constraints / what not to change

1. Current visual-only acceptance evidence must **not** be silently promoted to verified control or hardware.
2. `tool0` attachment boundary; preserve upstream UR5 packages.
3. Single authoritative `/joint_states` publisher in visual mode.
4. Config assumptions clearly labeled; keep visual and controller joint targets separate.
5. Fail-closed controller readiness and feedback checks.
6. Don't alter immutable experiment datasets/hashes or fabricate performance numbers.
7. Don't install/recreate complex bimanual MoveIt stack without explicit scope change.
8. Build under `src` due to archived source snapshots.
9. Keep `docs/STATUS.md` status authority; changes should update per-task evidence ledger.
10. Feature branches / reversible edits / no uncontrolled force pushes to main.

## 11. Remaining work / opportunities

**First:** AY-13 independent second-person clean-checkout repeat, with review ID, date, commit, machine/container/ROS versions, commands, actual logs and deviations under `docs/evidence/AY-13/`. Once evidence passes, update `docs/ayush/ledger.json` and `docs/STATUS.md`, rerun doc checker, commit reviewed change. If no independent reviewer available, leave IN PROGRESS and provide their exact execution guide.

**After AY-13 / optional backlog:** controller-selected bring-up and tested station targets (S1–S5), actuated simulation and controller feedback, physically meaningful grasp/attachment or bimanual planning, assessed collision/IK reachability, calibrated workcell geometry/CAD, controlled comparative performance study. These are *not* current core completion claims. Historical Phase 3 workspace characterization and Phase 6 carrier placement analysis remain planned; inspect new progress before picking them up.

## 12. How Codex should collaborate

For each task: inventory relevant paths → read code/contract/tests/evidence → state exact change and verification level → implement smallest safe patch → run offline tests → run ROS tests if available → store logs/evidence under appropriate path → update ledger/status only with observed proof → present command-by-command summary, failure causes and next safe step. When asking user to run commands, provide one consolidated runnable block. Prefer concise technical communications without unverifiable completion statements.

**Suggested immediate deliverable:** Independent AY-13 replay checklist and a PR containing only independently substantiated evidence or documented blockers, not a rewrite of the visual core.
