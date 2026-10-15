# CAM-BOT

**Carrier-assisted Adaptive Manipulation with Bimanual Operational Technology**

A ROS 2 Humble prototype for carrier-assisted CNC machine tending. A UR5
carrier positions a flange-mounted, four-joint dual-arm placeholder; an
application FSM coordinates visual carrier motion, local motion, workpiece
state and trial logging.

![scope](https://img.shields.io/badge/scope-visual%20ROS%20simulation-blue)
![ros](https://img.shields.io/badge/ROS%202-Humble-blue)
![license](https://img.shields.io/badge/license-Apache--2.0-green)

---

## The problem

The project asks whether a carrier can handle transit between workcell
stations while a smaller mounted module handles local manipulation. The
current experiment measures a visual ROS workflow; it does not establish a
time, energy or throughput advantage over a controlled baseline.

## The approach

CAM-BOT separates global and local motion in a task-level hierarchy:

```text
                        CAM-BOT
                           │
             ┌─────────────┴─────────────┐
             │                           │
    Global positioning           Local manipulation
             │                           │
      Carrier Arm (CA)           ┌───────┴───────┐
             │                   │               │
             │               Left arm        Right arm
             │                   │               │
             └──────────┬────────┴───────┬───────┘
                        │                │
              Hierarchical task & motion coordination
                        │
                 CNC machine tending
```

**Terminology used throughout this repository:**

| Term | Meaning |
|---|---|
| **CA** — Carrier Arm | The UR5 that positions the manipulation system |
| **CF** — Carrier Flange | The coupling between the UR5 wrist and the bimanual module |
| **BM** — Bimanual Module | The two-arm manipulation system mounted on the flange |

The mounted arms are a **kinematic placeholder**, not a validated grasping
mechanism. The carrier flange attaches after UR5 `tool0`; five configurable
stations and a movable visual workpiece are included in the expanded robot
model. See [architecture](docs/ARCHITECTURE.md) and
[design decisions](docs/DECISIONS.md).

---

## Current status

**AY-01–AY-12 are complete for their stated visual ROS 2 Humble scope. AY-13
remains in progress pending an independent quick-start repeat.** The
[status matrix](docs/STATUS.md) is the authoritative task/phase record;
the [AY evidence ledger](docs/ayush/ledger.json) maps each requirement to
files, tests, evidence and limits.

The five-trial fixed scenario recorded **5/5 successful visual attempts**,
with a mean complete-cycle time of **19.579117 s** and **25 completed visual
carrier repositions** across those attempts. The [raw capture and analysis](experiments/machine_tending/README.md)
retain all attempts, including preliminary captures kept separate. These
numbers describe the visual FSM and joint-publication workflow. No UR5
controller execution, physical grasp, collision-aware planning or real CNC
operation has been verified. The [G0–G10 build report](artifacts/verification/cambot_build_report.json)
labels each observed gate and each controller scenario that could not run.

---

## Repository layout

```text
CAM-BOT/
├── README.md                     ← you are here
├── LICENSE                       Apache-2.0
├── CONTRIBUTING.md               contribution conventions
├── .gitignore
├── .gitattributes                Git LFS rules for CSV, bags and video
│
├── src/
│   ├── carrier_description/      Xacro model, launch files, RViz config
│   └── carrier_control/          FSM, coordinator, reachability, logger
│
├── config/
│   └── waypoints.yaml            mirror of installed carrier-control waypoints
│
├── docs/
│   ├── STATUS.md                 ← single source of truth for progress
│   ├── ROADMAP.md                original six-phase plan
│   ├── ARCHITECTURE.md           robot chain and runtime topology
│   ├── DECISIONS.md              design and evidence decisions
│   ├── ayush/                    AY-01–AY-13 ledger and repeat guide
│   ├── evidence/                captured checks and runtime logs
│   ├── progress/
│   │   ├── phase1-carrier-baseline.md
│   │   ├── phase2-mass-sensitivity.md
│   │   └── phase_4.md            historical narrative with caveat
│   └── reference/               project briefs and supplied material
│
├── experiments/
│   ├── machine_tending/          sealed visual trial data, analysis, plots
│   └── mass_sensitivity/         archived EXP01–03 data and plots
│
├── artifacts/verification/       machine-readable build report
├── tools/                        capture, validation and report commands
└── media/                        screencasts (Git LFS)
```

---

## Quick start

**Visual quick-start requirements:** Ubuntu 22.04, ROS 2 Humble, `colcon`,
`rosdep`, `git-lfs`, RViz and the Universal Robots description package.
On CachyOS, run the ROS commands inside the `cambot-humble` Ubuntu
Distrobox. The [clean-checkout guide](docs/ayush/README.md) lists package,
display and independent-review details.

```bash
# 1. Clone the current work branch (use main after merge)
git lfs install
git clone --branch feature/ay10-ay12-visual-experiments https://github.com/voidAyush-tsx/CAM-BOT.git
cd CAM-BOT
git lfs pull
```

On CachyOS, enter `cambot-humble` and return to this checkout before the
next commands:

```bash
distrobox enter cambot-humble -- bash
cd /path/to/CAM-BOT
```

```bash
# 2. Install dependencies in Ubuntu/ROS 2 Humble
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y

# 3. Build only the live packages; archived trial snapshots duplicate names
colcon build --base-paths src --symlink-install --packages-select carrier_description carrier_control
export COLCON_TRACE=
set +u
source install/setup.bash
set -u
```

On a Wayland/niri desktop, set `QT_QPA_PLATFORM=xcb` and
`LIBGL_ALWAYS_SOFTWARE=1` before launching RViz.

**Run one integrated visual cycle:**

```bash
ros2 launch carrier_description dual_arm_demo.launch.py \
  auto_start:=true enable_coordination:=true trial_count:=1 visual_time_scale:=1.0
```

The launch starts `robot_state_publisher`, one authoritative visual
`/joint_states` publisher (`machine_tending_coordinator`), workpiece/task
topics, the trial logger and RViz. It runs the visual cycle automatically;
stop RViz/launch with Ctrl-C after observing the terminal result. The task
states are:

```text
HOME → PICK_RAW → STAGE → LOAD_MACHINE → MACHINE_DWELL
     → UNLOAD_MACHINE → PLACE_FINISHED → HOME
```

The five stations are S1 raw, S2 staging, S3 machine, S4 output and S5
finished; a successful visual cycle leaves the workpiece at
`FINISHED_AT_S5`. For manual start, launch with `auto_start:=false` and
call `ros2 service call /machine_tending_coordinator/start std_srvs/srv/Trigger "{}"`
from another sourced terminal. See [interfaces](docs/INTERFACES.md) for reset
and cancellation.

`dual_arm_cycle` is a separate Phase 4 viewer and is not launched with this
FSM. The visual system publishes assumed joint positions; it does not command
an actuator, run Gazebo physics or verify a grasp.

The separate `machine_tending_controller.launch.py` entry point requires a
selected controller bring-up file and validated named station targets. The
supplied plan fails that gate: S1–S4 are not controller validated and S5 has
no taught carrier target. Controller execution is therefore unverified.

The installed [machine-tending configuration](src/carrier_control/config/machine_tending.json)
is the single station/workspace source. Its poses and dimensions are
**visual simulation assumptions in metres/radians**, not surveyed cell
geometry. Both launch modes render station frames and visual targets from it.

---

## Waypoints

The legacy machine-shop joint cycle reads taught UR5 configurations from the
installed [waypoint file](src/carrier_control/config/waypoints.yaml). The root
[waypoint mirror](config/waypoints.yaml) supports older documentation.

| Station | Purpose |
|---|---|
| HOME | Standby configuration |
| P1–P4 | Historical machine-shop waypoints; not validated for S1–S5 |

The Phase 1 record describes teaching P1–P4 in MoveIt's RViz interface; see
[historical baseline](docs/progress/phase1-carrier-baseline.md). The five
newer machine-tending stations have separate `visual_carrier_joints` in
[machine_tending.json](src/carrier_control/config/machine_tending.json).
These were calibrated for the RViz workcell, while their
`controller_validated` flags remain false. The S5 controller target is
unset.

The coordinator checks both placeholder arms against a configured geometric
workspace proxy using live TF. It can select `LOCAL_MANIPULATION` or a
visual `CARRIER_REPOSITION`, then recheck the target after the final carrier
TF is observed. This is neither IK nor collision checking. See
[interfaces](docs/INTERFACES.md) and [validation](docs/VALIDATION.md).

---

## Experiments

The [AY-10 visual experiment](experiments/machine_tending/README.md) contains
five reset-verified attempts in one fixed scenario, all successful. Its
[raw trial CSV](experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv),
[event JSONL](experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.events.jsonl),
[rosbag](experiments/machine_tending/runs/ay10-visual-20261015-03/raw/visual_rosbag/metadata.yaml)
and [RViz screenshot](experiments/machine_tending/runs/ay10-visual-20261015-03/raw/rviz_runtime.png)
are retained with configuration/source hashes. Preliminary captures are
preserved separately and are not pooled into the five-trial summary.

AY-11 measures from the first `PICK_RAW` action through completion of final
`HOME` using node monotonic timestamps. AY-12 derives the
[per-trial table](experiments/machine_tending/runs/ay10-visual-20261015-03/raw_analysis/trials.csv),
[summary](experiments/machine_tending/runs/ay10-visual-20261015-03/raw_analysis/summary.csv),
[cycle-time plot](experiments/machine_tending/runs/ay10-visual-20261015-03/raw_analysis/cycle_time_by_trial.png),
[outcome plot](experiments/machine_tending/runs/ay10-visual-20261015-03/raw_analysis/trial_outcomes.png)
and [reposition plot](experiments/machine_tending/runs/ay10-visual-20261015-03/raw_analysis/carrier_repositions_by_trial.png)
from that sealed data. Recreate them in a new directory with:

```bash
python3 experiments/machine_tending/scripts/analyze_trials.py \
  experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv \
  --output /tmp/cambot-analysis --qualify
```

The [cross-validation record](docs/evidence/AY-13/cross_validation/README.md)
reports a passing scoped Humble build, 48 regression tests, 59 package tests
(two skips), 14 analysis tests and a clean-shutdown live visual probe.
Descriptions of carrier moves here count **visual joint publications**, not
controller action results. All runtime/end-to-end/actuation/grasp verification
flags remain false for the measured visual dataset. Comparisons with a
controlled baseline have not been run.

The separate mass-sensitivity archive contains three 10% UR5 link-mass
perturbations and recorded joint-trajectory statistics:

| ID | Link | Baseline | Perturbed |
|---|---|---|---|
| EXP01 | Upper arm | 8.3930 kg | 9.2323 kg |
| EXP02 | Forearm | 2.3300 kg | 2.5630 kg |
| EXP03 | Shoulder | 3.7000 kg | 4.0700 kg |

Read its [methods and limitations](experiments/mass_sensitivity/README.md)
before interpreting the derived acceleration values.

---

## Team

**CAM-BOT — TOPS Programme 2026**

| Member | Workstream |
|---|---|
| Shannu | Manipulator kinematics & control |
| Tanmay | Mechanical & carrier design |
| Ayush | Software, simulation & digital systems |

See [`docs/TASK_ALLOCATION.md`](docs/TASK_ALLOCATION.md).

---

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
