# AY-01 Phase-4 reproduction evidence

Disposition: **REPAIR / VERIFY**. Phase-4 reconstruction source is present in
Git history at `66c436a`; see `manifest.json`. The current checkout has an
isolated `view_dual_arm.launch.py` entry point. The five-station model can be
disabled in its Xacro invocation so this viewer tests the Phase-4 baseline.

## Static source result

Run:

```bash
python3 tools/phase4_contract.py
python3 -m unittest src/carrier_description/test/test_phase4_contract.py -v
```

The source contract checks local link/joint uniqueness, the fixed chain from
`tool0` to `dual_arm_base_link`, four joint names and limits, joint sample order,
and every generic stage target. Negative tests introduce a duplicate link,
broken attachment, limit violation, and duplicate expanded URDF name.

These checks do not expand the upstream `ur_description` macro, observe ROS
topics, or inspect an RViz image.

## Humble reproduction

Use a clean Ubuntu 22.04 / ROS 2 Humble workspace, in Bash with
`/opt/ros/humble/setup.bash` sourced. Run from this checkout:

```bash
bash tools/capture_ay01_humble.sh
```

The capture script records environment, dependencies, build, package prefixes,
Xacro output, `check_urdf`, expanded URDF uniqueness/chain, isolated viewer
launch, a `/joint_states` sample, one-publisher authority, a TF frame diagram,
and final Git status under `runtime/`. It uses bounded ROS waits and shuts down
the viewer. Inspect `runtime/frames.pdf` and capture an RViz screenshot as
`runtime/rviz-phase4.png`; record the displayed UR5, flange, both arms, and
fixed frame `base_link`. Add a short visual observation to `runtime/notes.md`.

Only then can AY-01 be marked complete for the visual baseline. The generic
`GRASP` stage is an arm pose label: it provides no physics-simulated grasp or
workpiece attachment. For controller/Gazebo execution beyond this viewer, obtain
Shanmukha's separate implementation and test it as a separate integration step.

Current runtime evidence is **BLOCKED** on the local CachyOS host; the Humble
tools are absent. See `artifacts/verification/first_execution_gate.json`.
