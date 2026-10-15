# AY-13 reproducibility and review guide

The [status matrix](../STATUS.md) owns dispositions; [ledger.json](ledger.json)
records the requirement, prior state, options, exact changed paths, test
command/environment/result, evidence, limitation, and next step for every AY-ID.
The [experiment methods](../../experiments/machine_tending/README.md) own the
AY-10–12 counting rules and results. This avoids maintaining another status table.

## Documentation change and blocker record

On 2026-10-15 the status page's missing Phase 4 link was corrected to the
archived Phase 4 document; stale present-tense controller/Gazebo claims were
classified as historical; the obsolete clone/workspace instructions were
replaced; and a false assertion that waypoints were still hardcoded was
corrected against source. [D-08 and D-09](../DECISIONS.md) record the evidence
policy and visual-trial scope. The [Humble contract log](../evidence/AY-13/humble_contract.log)
shows installed packages, executables and URDF, while the
[checker fixtures](../evidence/AY-13/doc_checker_tests.log) cover negative
path/status/launch cases. The only AY-13 acceptance blocker is an independent
second-person quick-start repeat; no reviewer observation is fabricated.

## Evidence boundary

Available source/installed code, observed visual ROS execution, actuated
simulated execution, and measured complete cycles are distinct claims. Five
complete cycles were measured in a **visual ROS simulation**, with five
successful attempts and no failed attempts in the qualifying fixed scenario.
Their timing is first PICK_RAW action through final HOME. Requested, accepted
and completed carrier *visual* motions are separately counted. The sealed
[main manifest](../../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/manifest.json),
[raw checksums](../../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/checksums.json),
[bag](../../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/visual_rosbag/metadata.yaml),
[screenshot](../../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/rviz_runtime.png)
and [analysis](../../experiments/machine_tending/runs/ay10-visual-20261015-03/raw_analysis/metrics.json)
support that claim.

No selected UR controller bring-up, validated S1–S5 controller targets,
bimanual/gripper feedback, IK/collision study, surveyed workcell or real CNC
evidence exists in this checkout. Runtime/end-to-end/actuation/grasp
verification flags in the visual data are false. The historical
[Phase 4 narrative](../progress/phase_4.md) is preserved as an archival report,
not present Gazebo evidence. Earlier AY-06–08 and AY-09 one-trial capture
directories were not committed; their offline evidence and later AY-10 live
integration evidence are identified separately in the ledger.

## Clean-checkout quick start

Use a fresh Ubuntu 22.04 ROS 2 Humble environment, or the project's
`cambot-humble` Distrobox on CachyOS. ROS Humble, `colcon`, `rosdep`,
`xacro`, `check_urdf`, `rviz2`, `git-lfs` (for complete media/CSV checkout)
and the package dependencies must be installed. A clean clone has no local
`install/` until built. Use the current feature branch while AY-13 is under
review; use `main` once these docs are merged.

```bash
git lfs install
git clone --branch feature/ay10-ay12-visual-experiments https://github.com/voidAyush-tsx/CAM-BOT.git
cd CAM-BOT
# On CachyOS: enter the Ubuntu container, then return to this checkout.
distrobox enter cambot-humble -- bash
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
```

The `set +u` bracket is required if the caller enabled Bash `nounset`.
The `--base-paths src` restriction is required because the immutable AY-10
raw archives contain source snapshots with duplicate ROS package names;
Colcon's default repository-wide discovery would reject them.
On Wayland/niri, use `export QT_QPA_PLATFORM=xcb` and
`export LIBGL_ALWAYS_SOFTWARE=1` for RViz.

```bash
xacro src/carrier_description/urdf/ur5_with_test_tool.xacro > /tmp/cambot.urdf
check_urdf /tmp/cambot.urdf
ros2 pkg executables carrier_control
python3 tools/check_ay13_docs.py --installed
ros2 launch carrier_description dual_arm_demo.launch.py auto_start:=false trial_count:=1 visual_time_scale:=1.0
```

In another sourced terminal, trigger one visual trial:

```bash
ros2 service call /machine_tending_coordinator/start std_srvs/srv/Trigger "{}"
ros2 topic echo /cambot/task_state
ros2 topic echo /cambot/workpiece_state
```

Use separate terminals for the topic echoes. Observe HOME → PICK_RAW → STAGE
→ LOAD_MACHINE → MACHINE_DWELL → UNLOAD_MACHINE → PLACE_FINISHED → HOME and
`FINISHED_AT_S5`. Check `ros2 topic info /joint_states --verbose`: visual
mode must show one publisher, `machine_tending_coordinator`. Do not launch
a second coordinator or state publisher into the same ROS domain.

Recompute the archived metrics and plots into a **new** output directory,
leaving the sealed raw and published derived data intact:

```bash
python3 -m unittest discover -s experiments/machine_tending/tests -v
python3 experiments/machine_tending/scripts/analyze_trials.py \
  experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv \
  --output /tmp/cambot-ay13-regenerated --qualify
```

The [experiment README](../../experiments/machine_tending/README.md) explains
the source commit plus patch/snapshot identity, environment/config hashes,
reset gates, preliminary captures and nonpooling rule. Capture 03 records base
commit `6e77292e4fceca0636a4cd86a037bf9e7d64f93a` plus
`raw/source.patch` and per-file hashes; that commit by itself is not the
executed source version.

The [cross-validation record](../evidence/AY-13/cross_validation/README.md)
retains the failing unscoped build, passing scoped build and Colcon tests,
48-test regression, model/installed-asset checks, live visual probe and exact
analysis regeneration comparison. The [machine-readable report](../../artifacts/verification/cambot_build_report.json)
is generated by `python3 tools/generate_build_report.py` from those committed
records. The build and script repairs did not add a controller stack;
controller smoke cases remain unverified.

## Independent quick-start repeat

AY-13 remains **IN PROGRESS** until a second person executes the clean
checkout/build/Xacro/visual launch/start/one publisher steps above and records:
their name or reviewer ID, date, checkout commit, Humble/container details,
command outputs or logs, and any deviations. Place that record under
`docs/evidence/AY-13/`, link it from the ledger and status, then change AY-13
to COMPLETE. No independent replay is claimed by this guide.

For any later documentation or source edit, run the document checker and the
relevant regression commands before committing docs with that change. Keep
historical reports intact; add dated provenance corrections when evidence
changes.
