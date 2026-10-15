# Phase 1 — UR5 Carrier Baseline

> **Archival provenance note (2026-10-15):** This is a historical Phase 1
> report. It records earlier Gazebo/MoveIt/controller observations but the
> selected controller bring-up and action-result evidence are not retained in
> this checkout. See [current evidence levels](../STATUS.md). Present AY-10
> measurements are visual ROS cycles, not a replay of this controller baseline.

**Status:** ✅ Complete
**Goal:** establish a simulated UR5 Carrier Arm that executes a repeatable
machine-shop cycle, packaged so a third party can reproduce it.

---

## 1. Environment

| Component | Version / package |
|---|---|
| OS | Ubuntu 22.04 |
| ROS | ROS 2 Humble |
| Simulator | Gazebo |
| Planning | MoveIt 2 |
| Control | `ros2_control` |
| Robot | Universal Robots UR5 |

Upstream UR packages used: `ur_description`, `ur_bringup`, `ur_calibration`,
`ur_controllers`, `ur_moveit_config`, `ur_robot_driver`, `ur_simulation_gazebo`.

---

## 2. Robot description

The UR5 is instantiated from the official macro rather than a vendored copy:

```xml
<xacro:include filename="$(find ur_description)/urdf/ur_macro.xacro"/>
<xacro:ur_robot ... ur_type="ur5"/>
```

The official chain terminates as:

```text
wrist_3_link → flange → tool0
```

All custom geometry attaches **after `tool0`**, which keeps the upstream UR5
description untouched and upgradeable.

### Files

```text
src/carrier_description/urdf/
├── test_tool.xacro
└── ur5_with_test_tool.xacro
```

### Problems encountered

**Xacro macro instantiation.** First conversion failed with:

```text
Not enough blocks
when instantiating macro: ur_robot
```

The `ur_robot` macro's parameter list was inspected directly and the call
corrected.

**Missing `world` link.** `check_urdf` then reported:

```text
Failed to build tree: parent link [world] of joint [base_joint] not found.
```

A joint referenced `parent link="world"` without the URDF ever declaring
`<link name="world"/>`. This was a tree-declaration issue, not a fault in the
custom tool.

After both fixes the generated URDF parsed cleanly and contained the expected
`test_tool_base` / `test_tool_tip` links.

---

## 3. MoveIt and control verification

**Planning group** — `ur_manipulator`, chain `base_link → tool0`.

Named configurations present in the semantic description: `HOME`, `UP`,
`TEST_CONFIGURATION`.

**Verified action interfaces:**

```text
/move_action
/execute_trajectory
/joint_trajectory_controller/follow_joint_trajectory
/scaled_joint_trajectory_controller/follow_joint_trajectory
```

with `/rviz2_moveit` as client and `/move_group` as server — confirming the
`RViz → move_group → controller` path.

**Active controllers:** `joint_trajectory_controller`, `joint_state_broadcaster`.

**Joint states** publishing for all six joints: `shoulder_pan`, `shoulder_lift`,
`elbow`, `wrist_1`, `wrist_2`, `wrist_3`.

**TF spot-check**, `base_link → tool0`:

```text
Translation:  X = 0.001   Y = 0.191   Z = 1.001   [m]
RPY:         -1.571       0.002       0.000       [rad]
```

---

## 4. The waypoint problem — and the fix

This is the central technical result of Phase 1.

### What was tried first

Machine-shop stations were specified as **Cartesian targets**. A point at
`(0.001, 0.241, 1.001)` planned and executed fine. But P2 failed outright, and
after dropping the working height to `Z ≈ Z_max/2 = 0.500 m` and retrying with

```text
P1: (0.200, 0.241, 0.500)
P2: (0.200, 0.391, 0.500)
P3: (0.201, 0.391, 0.500)
```

P1 and P2 succeeded while P3 still failed with MoveIt error `-4`.

### Diagnosis

Hand-chosen Cartesian coordinates give no guarantee of a reachable,
well-conditioned, collision-free IK solution. Points that look adjacent in
Cartesian space can sit on opposite sides of a singularity or outside the
dexterous workspace. Nudging coordinates until planning happens to succeed is
not a method.

### The redesign

Stations are now taught **in joint space**:

1. Drag the UR5 to a visually valid pose with MoveIt's RViz interactive marker.
2. Read the resulting six-joint configuration from `/joint_states`.
3. Store it as the station definition.

Because the configuration came from the simulation itself, it is reachable by
construction. Planning failures disappeared.

> **The narrative worth reporting:** arbitrary Cartesian waypoints proved
> unreliable; the failure was diagnosed as ill-posed IK targets rather than a
> planner defect; the design changed to interactive joint-space teaching; the
> cycle then executed reliably. Problem → diagnosis → design change → result.

---

## 5. Taught configurations

Recorded from `/joint_states`, in the order
`[shoulder_pan, shoulder_lift, elbow, wrist_1, wrist_2, wrist_3]` (rad).
Authoritative copy lives in [`config/waypoints.yaml`](../../config/waypoints.yaml).

| Station | Joint configuration |
|---|---|
| HOME | `[ 0.000000, -1.570700,  0.000000,  0.000000,  0.000000,  0.000000]` |
| P1 | `[ 3.593065, -2.205479, -1.067588,  0.131337,  1.242010, -4.712387]` |
| P2 | `[-2.973180, -1.069788,  0.405185, -2.478748, -1.710968, -0.000344]` |
| P3 | `[-0.491184, -1.243253,  1.013834, -2.910754, -1.513936, -0.000694]` |
| P4 | `[-1.912422, -1.170719,  1.563141, -3.534719, -1.728039, -0.001561]` |

*(The original `Task1_Progress.md` was truncated after HOME and lost P1–P4.
Values above are recovered from `task1_chat .md` §15–18 and cross-checked
against `waypoints.yaml`.)*

---

## 6. Automated cycle

`src/carrier_control/carrier_control/machine_shop_joint_cycle.py`

```text
HOME → P1 → HOME → P2 → HOME → P3 → HOME → P4 → HOME
```

The carrier stops at every waypoint and holds each station for **3 s**
(reduced from an initial 10 s). Motion speed was raised moderately from the
first implementation — the target was safe, repeatable execution rather than
minimum cycle time.

Returning to HOME between stations keeps each transit independent and makes
per-station timing separable, which Phase 5 will need.

---

## 7. Trajectory recording and plotting

`plot_machine_shop_path.py` subscribes to `/joint_states`, records a full cycle,
computes the end-effector path via forward kinematics, and renders a 3D plot.

**Recording works** — a representative run collected 6494 samples.

**Plotting was obstructed** by a Python environment conflict, resolved as follows:

| Problem | Cause | Fix |
|---|---|---|
| `Unable to import Axes3D`, `Unknown projection '3d'` | Two matplotlib installs: 3.10.9 in `~/.local`, 3.5.1 from apt | Removed the user-local install |
| `A module compiled using NumPy 1.x cannot be run in NumPy 2.2.6`, `_ARRAY_API not found` | apt matplotlib built against NumPy 1.x, system had NumPy 2.2.6 | Isolated venv `plot_env` with NumPy 1.26.4 + matplotlib 3.10.9 |

Verified inside `plot_env`: `3D Matplotlib OK`, `ROS Python OK`.

⚠️ End-to-end plot generation was never confirmed. This remains open.

---

## 8. Packaging notes

- A hardcoded `/home/shanmukha/tops_ws/machine_shop_3d_path.png` output path was
  found via `grep -Rni "/home/shanmukha"` and **has since been fixed** — the
  script now writes a relative filename. Verified: no absolute home paths remain
  in any `.py`, `.yaml`, or `.xacro` in the repository.
- `__pycache__/` directories were identified as unwanted. A `.gitignore` was
  specified but never created — see [`STATUS.md`](../STATUS.md) debt item 5.
- Git identity (`user.name` / `user.email`) is required to *commit*; GitHub
  credentials are required to *push*. These are separate, and an unconfigured
  identity blocked the first commit.

---

## 9. Outcome

A UR5 carrier manipulator was integrated into a ROS 2 Humble simulation using
Gazebo, MoveIt 2, and `ros2_control`. Custom geometry was attached at `tool0`
without modifying the upstream UR description. Cartesian waypoint specification
proved unreliable and was replaced by interactive joint-space teaching, with
configurations captured from `/joint_states`. Four taught stations were composed
into an automated joint-space cycle with HOME returns and fixed station dwell,
which executes reliably through the joint trajectory controller.

**Next:** [Phase 2 — Mass sensitivity](phase2-mass-sensitivity.md)
