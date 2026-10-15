# G0–G10 cross-validation record

Run on 2026-10-15 from CachyOS x86_64 in the `cambot-humble` Ubuntu 22.04 /
ROS 2 Humble Distrobox. Source under test is the cross-validation repair
commit; the archived AY-10 five-trial capture identifies its **own earlier**
base commit plus source patch/snapshot. The [machine-readable build report](../../../../artifacts/verification/cambot_build_report.json)
is a snapshot of these checks, not the authoritative AY status matrix.

| Gate | Observed result | Evidence and boundary |
|---|---|---|
| G0 inventory | PASS | [56 tracked source files with hashes](source_inventory.json); [AY status/ledger](../../../STATUS.md) |
| G1 build | PASS after repair | [rosdep](rosdep_check.log), [initial duplicate discovery failure](colcon_build.log), [scoped build](colcon_build_scoped.log), [first test lint failures](colcon_test.log), [retest: 59 tests, 0 failures, 2 skipped](colcon_retest.log). Use `--base-paths src`. |
| G2 model | PASS for visual model | [Xacro, 10 manipulator + 3 workpiece nonfixed joints, installed assets](model_assets.log); live TF rechecks in probe. |
| G3 launch | PASS for visual capture/cleanup; controller BLOCKED | [new capture](live_recheck/probe.jsonl), [empty before/after node lists](live_recheck/residual_nodes.txt). First probe passed but left child nodes; process-group cleanup repaired it. |
| G4 workcell | PASS for configured visual cell | Five station frames and workpiece in [model](model_assets.log) and [live bag](live_recheck/visual_rosbag/metadata.yaml); geometry is assumed. |
| G5 FSM | PASS visual/offline | [48 regression tests](regression_48.log), complete live sequence and final S5 in [probe](live_recheck/probe.jsonl). |
| G6 coordination | PASS visual/offline; controller BLOCKED | Both decisions, five TF rechecks in [probe](live_recheck/probe.jsonl). Visual joint publication is not an UR5 action result. |
| G7 integration | PASS visual; actuated integration BLOCKED | Moving visual workpiece and TF in [bag](live_recheck/visual_rosbag/metadata.yaml); no controller/gripper execution. |
| G8 experiment | PASS for archived fixed visual scenario | [AY-10 acceptance](../../AY-10/acceptance.json): five actual qualifying attempts; six across all separate captures. No failures occurred. |
| G9 analysis | PASS | [14 analysis tests and qualified regeneration](analysis_regeneration.log); [all six published outputs byte-match](analysis_comparison.log). |
| G10 documentation | PASS automated; human repeat PENDING | [link/status/assets check](../source_contract.log), [negative fixtures](../doc_checker_tests.log), [repeat guide](../../../ayush/README.md). |

The unscoped build failure arose because archived raw evidence contains
`raw/source/src/carrier_control` and `raw/source/src/carrier_description`.
Those sealed snapshots were not modified. The first AY-06–08 visual probe
returned `VISUAL_SIMULATION_PASS` but left ROS child nodes after the script
stopped the launch parent. Its [raw output](../../AY-06-08/runtime/probe.jsonl)
and the later [clean recheck](live_recheck/probe.jsonl) are both retained.

**Scenario classification:** S1 local is PASS in offline tests and live visual
decisions. S2's visual reposition/recheck is PASS; the requested UR5 action
result is NOT RUN because the controller stack is unavailable. S3 finite
unreachable failure is PASS offline, NOT RUN as a live impossible-target
scenario. S4 controller rejection/timeout is PASS offline contract, NOT RUN
against a controller. S5 five reset-verified visual attempts is PASS in the
sealed AY-10 batch; the current repair commit was rechecked with one live
visual cycle. Neither source snapshot is mislabeled as actuated simulation.

**Open blockers:** no selected controller bring-up, unvalidated S1–S4
controller targets, missing S5 taught target, no bimanual/gripper controller
feedback, no independent second-person clean-checkout repeat. AY-14…AY-20
are outside this report.

## Reproduce the verification

```bash
source /opt/ros/humble/setup.bash
rosdep check --from-paths src --ignore-src
colcon build --base-paths src --symlink-install --packages-select carrier_description carrier_control
export COLCON_TRACE=
set +u
source install/setup.bash
set -u
colcon test --base-paths src --packages-select carrier_description carrier_control
colcon test-result --verbose
python3 tools/check_ay13_docs.py --installed
python3 -m unittest tools/test_check_ay13_docs.py -v
xacro src/carrier_description/urdf/ur5_with_test_tool.xacro >/tmp/cambot.urdf
check_urdf /tmp/cambot.urdf
python3 -m unittest discover -s experiments/machine_tending/tests -v
python3 experiments/machine_tending/scripts/analyze_trials.py \
  experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv \
  --output /tmp/cambot-crossvalidation-analysis --qualify
```

For a new isolated live visual check, choose an unused `ROS_DOMAIN_ID`, set
`QT_QPA_PLATFORM=xcb` and `LIBGL_ALWAYS_SOFTWARE=1`, then run
`bash tools/capture_ay0608_humble.sh /absolute/new/evidence-directory`.
The script refuses an existing output path and a nonempty ROS domain.
