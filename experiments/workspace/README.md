# Preliminary carrier workspace and placement study

This study uses the current **assumed visual workcell**, as requested by the
project owner. Its kinematic samples and geometric-proxy checks do not validate
station controller targets, physical reachability or collision-free motion.
The [project status](../../docs/STATUS.md) owns phase completion states.

## Reproduce into a new directory

Use the [Humble image](../../docs/CLOUD_HUMBLE.md), build the two ROS packages
with `colcon build --base-paths src`, and source the resulting workspace.
The analysis needs NumPy and Matplotlib, both included in that image.

```bash
study_output="$(mktemp -d /tmp/cambot-workspace.XXXXXX)"
xacro src/carrier_description/urdf/ur5_with_test_tool.xacro > "$study_output/model.urdf"
python3 tools/analyze_workspace.py \
  --urdf "$study_output/model.urdf" \
  --placements experiments/workspace/placements.json \
  --output "$study_output/study" --samples 20000 --seed 13
python3 -m unittest tools/test_analyze_workspace.py -v
# Requires a clean ROS domain; the probe starts only its own publisher and RSP.
ROS_DOMAIN_ID=100 ROS_LOCALHOST_ONLY=1 python3 tools/probe_workspace_fk.py \
  --urdf "$study_output/model.urdf" --output "$study_output/fk-crosscheck"
```

The commands do not change the robot model, coordinator, configuration or
controller gates. Both analysis and live TF probe refuse existing output paths.
The [retained run](runs/model-study-20261107/README.md) records the tested source,
commands, numerical outputs, tests and input hashes.

## Method and interpretation

The tool reads the expanded URDF chain from `world` to `dual_arm_base_link`,
including fixed flange transforms, revolute axes and hard joint limits. It
samples 20,000 configurations uniformly within those limits, then appends the
six configured visual poses (HOME and S1–S5). All five candidate base placements
use the same configuration sample. Random and appended-pose hit counts are
reported separately so the known visual poses cannot be mistaken for an
independent random coverage result.

The point cloud contains **bimanual-base origins**, not gripper tips or achieved
grasp poses. Target positions come from the existing station transforms and
interaction offsets. Each sampled base transform maps those targets into the
existing both-arm box/sphere proxy. A positive `best_proxy_clearance_m` measures
distance to that assumed proxy's limiting boundary; it is **not** distance to
a proven robot workspace boundary. `workspace_boundary_margin_m` stays null.
Configurations below the floor or in self-collision are not filtered yet.

The five candidates are the current base and ±0.2 m translations along world
X/Y, with unchanged orientation and height. These offsets are analysis
assumptions, not surveyed candidate mounting locations. The report includes
coverage of six interaction targets across five stations. MACHINE_LOAD and
MACHINE_UNLOAD share a point but remain distinct task targets.

For candidates with all targets represented, a greedy sequence selects sampled
proxy-matching endpoints nearest to the previous joint vector, beginning and
ending at HOME. Its sum of absolute joint changes is in radians, without angle
wrapping, trajectory optimization, timing, collision clearance or executable
path verification. It does not establish machine throughput or placement
optimality. The four legacy P1–P4 controller vectors are also evaluated and
retained separately; S5's missing controller vector remains null.

No-hit results mean **no matching sample found**, not unreachable. The narrow
both-arm overlap and large six-dimensional search space make uniform sampling
sparse. Any placement decision needs targeted IK, self/environment collision
checks, orientation requirements, validated geometry and an uncertainty study.
