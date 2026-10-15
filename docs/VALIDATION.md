# Validation procedure

**Current entry point (2026-10-15):** Follow the [clean-checkout and independent
repeat guide](ayush/README.md), then the [experiment methods](../experiments/machine_tending/README.md).
The [cross-validation record](evidence/AY-13/cross_validation/README.md)
includes actual G0–G10 results and scenario evidence. Use
`--base-paths src` for both Colcon build and test: archived AY-10 source
snapshots otherwise appear as duplicate packages.
The commands below include historical component probes. References to
uncommitted AY-04/AY-06–09 capture outputs describe how those scripts write
evidence, not files presently retained in this checkout. The AY-10 raw
capture is the retained live visual evidence. Controller execution remains
unverified.

## AY-10…AY-12 visual experiment acceptance

The user selected visual ROS trials as the qualifying scope. Five observed
attempts, reset/readiness evidence, raw ROS events/bag and derived metrics/plots
are retained under `experiments/machine_tending/runs/ay10-visual-20261015-03/`.
See [methods, evidence and exact commands](../experiments/machine_tending/README.md).
Controller gates below remain requirements for a future controller experiment.

```bash
python3 -m unittest discover -s experiments/machine_tending/tests -v
python3 experiments/machine_tending/scripts/analyze_trials.py \
  experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv \
  --output experiments/machine_tending/runs/ay10-visual-20261015-03/raw_analysis \
  --qualify
```

Run analysis with Matplotlib available (the Humble container has 3.5.1).
Qualification checks raw checksums, source/config identity, five unique finals,
terminal outcomes, state and adapter event order, observed resets, both
coordination cases, and completed goals against observed joint publications.
The original 48-test regression suite also passed after the coordinator's
logging additions. These results establish visual runtime evidence only.

## Offline checks

These checks are valid without ROS and establish only **STATIC VALID** evidence:

```bash
PYTHONPATH=src/carrier_control python3 -m unittest \
  src/carrier_control/test/test_workflow.py \
  src/carrier_control/test/test_metrics.py \
  src/carrier_control/test/test_action_safety.py -v
python3 -m unittest \
  src/carrier_description/test/test_cell_model.py \
  src/carrier_description/test/test_launch_contract.py -v
python3 -m compileall -q \
  src/carrier_control/carrier_control src/carrier_description/launch
python3 tools/verify_ay.py --output artifacts/verification/ay_verification.json
```

The generated JSON contains legacy offline component checks created before the
PDF-defined AY mapping was supplied. It is useful static evidence but is not
AY-01…AY-13 acceptance evidence. The current runtime gate is recorded in
`artifacts/verification/first_execution_gate.json`.

## ROS 2 Humble static checks

Run in a sourced Humble workspace. These commands were unavailable in an
earlier offline implementation shell, but the later Distrobox/Humble build,
Xacro and runtime captures succeeded; see the AY-10 logs and raw evidence:

```bash
timeout 120s colcon build --base-paths src --symlink-install --packages-select carrier_description carrier_control
export COLCON_TRACE=
set +u
source install/setup.bash
set -u
xacro $(ros2 pkg prefix carrier_description)/share/carrier_description/urdf/ur5_with_test_tool.xacro > /tmp/cambot.urdf
check_urdf /tmp/cambot.urdf
timeout 20s ros2 launch carrier_description dual_arm_demo.launch.py \
  visual_time_scale:=0.05
```

The last command is a visual simulation check, not Gazebo actuation.

For the five-station cell, run
`PYTHONPATH=src/carrier_control python3 -m unittest
src/carrier_control/test/test_workcell_contract.py -v` for positive and
failure-path config/transform tests. In Humble, run
`bash tools/capture_ay04_humble.sh` to expand/check the configured URDF,
inspect station TF frames and workpiece state, and capture an RViz screenshot.
The supplied cell geometry is temporary simulation-only. A later genuine
[RViz screenshot](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/rviz_runtime.png)
and [TF-containing rosbag](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/visual_rosbag/metadata.yaml)
are retained from the Humble visual run.

## Controller-mode gate and five-trial run

Before changing `controller_validated` to `true`, teach each named target against
the actual cell, add the missing S5 target, and review the mapping. Supply a
single selected ROS launch file that starts the UR5 trajectory controller and
its joint-state broadcaster, without a second robot-state publisher or a
publisher of fabricated UR5 positions. The gated entry point includes that
file and waits for both the action server and a complete UR5 `/joint_states`
sample before proceeding:

```bash
timeout 10s ros2 action info \
  /joint_trajectory_controller/follow_joint_trajectory
timeout 10s ros2 topic hz /joint_states
```

Run five trials only after both commands show the expected controller and stream:

```bash
timeout 300s ros2 launch carrier_description machine_tending_controller.launch.py \
  controller_bringup_file:=/absolute/path/to/selected_controller.launch.py \
  config_file:=/absolute/path/to/validated_machine_tending.json trial_count:=5
```

Inspect the CSV and state topics. Carrier movement may be marked **RUNTIME
VERIFIED** only when every carrier action has a successful result and actual
position feedback. The overall cycle remains below **END-TO-END VERIFIED** while
the bimanual module has no selected controller/feedback interface.

The current repository cannot pass this run: there is no selected controller
bring-up file, S1–S4 are unvalidated mappings, and S5 lacks a taught carrier
target. Use `bash tools/capture_ay03_humble.sh` in a sourced Ubuntu 22.04/Humble
GUI session for three visual launch/stop checks and the default fail-closed
controller check. Do not label those visual trials as controlled motion.

## AY-05 FSM checks

The offline FSM tests cover ordered transitions, one-shot success, reset,
invalid lifecycle, state timeout, zero retry, cancellation, and a failed
`LOAD_MACHINE` step with no later state or workpiece advance:

```bash
PYTHONPATH=src/carrier_control python3 -m unittest \
  src/carrier_control/test/test_machine_tending_fsm.py -v
```

In a sourced Ubuntu 22.04/Humble GUI workspace, run
`bash tools/capture_ay05_humble.sh`. It launches the **visual-only** coordinator
in manual-start mode for three cases: successful one-shot, injected `S3_LOAD`
failure, and early cancel. Its observer records trial IDs, timestamps, state
order, terminal event, and workpiece topic updates. It does not simulate a
trajectory controller or prove physical picking/placing. Controller-mode FSM
integration remains blocked by AY-03's missing controller stack and validated
station targets.

Failure tests include an unavailable action server, rejected goal, result
timeout, missing feedback, discontinuous workpiece state, and invalid or
unvalidated station configuration. In each case the coordinator must publish or
log failure, stop the cycle, and must not advance the workpiece state for the
failed step.

## AY-06–08 coordination/reachability checks

```bash
PYTHONPATH=src/carrier_control python3 -m unittest \
  src/carrier_control/test/test_reachability.py \
  src/carrier_control/test/test_coordination.py -v
```

These are offline geometric-proxy and synthetic-TF tests, not robot
execution. In a sourced Ubuntu 22.04/Humble GUI workspace, run
`bash tools/capture_ay0608_humble.sh /absolute/new/evidence-directory`
for a fail-closed **visual-simulation**
probe that checks live TF, both decision branches, joint-state animation,
FSM state visits, and workpiece updates. A successful visual probe still does
not verify UR5 actuation or grasp. A real carrier/BM end-to-end test requires
the missing selected controller stack, validated station targets, and BM
action/feedback interface; record actual action results and TF/joint-state
changes before claiming runtime/end-to-end verification.

## AY-09 experiment logger checks

```bash
PYTHONPATH=src/carrier_control python3 -m unittest \
  src/carrier_control/test/test_metrics.py -v
python3 -m json.tool experiments/machine_tending/schema/trial.schema.json >/dev/null
python3 -m json.tool experiments/machine_tending/schema/event.schema.json >/dev/null
```

The tests create temporary successful, failed, interrupted, duplicate, and
invalid-claim datasets. They verify unique IDs, one final row, nonnegative
steady-clock durations, complete failure context, chronological event
sequences, schema/template parity, and direct coordinator logger hooks.

In a sourced Ubuntu 22.04/Humble GUI workspace,
`bash tools/capture_ay09_humble.sh` can create a **visual runtime** CSV
and JSONL pair under `docs/evidence/AY-09/runtime/`; that directory is not
present in this checkout. The retained [AY-10 CSV](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv)
and [event JSONL](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.events.jsonl)
show the live logger integrated with five visual cycles. They are not carrier
actuation, grasp, Gazebo physics, or end-to-end controller evidence.

