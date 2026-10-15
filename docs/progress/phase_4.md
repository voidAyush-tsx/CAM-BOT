# CAM-BOT --- Carrier-Assisted Bimanual Manipulation for Machine Tending

> **Archival provenance note (2026-10-15):** The text below is preserved as a
> historical progress narrative. Its Gazebo Classic world, bimanual controller
> and complete actuated execution claims have no matching world/controller
> source or retained runtime evidence in this checkout, so they are **unverified
> here**. Current supported acceptance is the ROS 2 Humble *visual* workcell,
> coordinator and five measured visual trials. See [status](../STATUS.md),
> [architecture](../ARCHITECTURE.md) and [raw capture](../../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/manifest.json).
> This note does not erase or adjudicate the historical author's observations.

> **Project:** Carrier-assisted Adaptive Manipulation with Bimanual
> Operational Technology (CAM-BOT)\
> **Current milestone:** Phase 4 --- Integrated visual simulation
> baseline\
> **ROS 2:** Humble\
> **OS:** Ubuntu 22.04\
> **Simulation:** Gazebo Classic 11.10.2\
> **Primary carrier:** Universal Robots UR5\
> **Workspace:** `~/tops_ws`

------------------------------------------------------------------------

# 1. Project Overview

CAM-BOT is a ROS 2 simulation/prototype feasibility project for a
**carrier-assisted bimanual manipulation system**.

The system combines:

1.  A **UR5 carrier arm** for global positioning.
2.  A custom **carrier flange/interface** mounted after the UR5 `tool0`.
3.  A custom **4-DOF bimanual mechanism** mounted on the carrier flange.
4.  A five-station machine-shop environment.
5.  Predefined joint trajectories and taught poses for a machine-tending
    demonstration.

The intended system architecture is:

``` text
                         CAM-BOT
                            │
                    Machine-Tending Cell
                            │
             ┌──────────────┴──────────────┐
             │                             │
       GLOBAL POSITIONING             LOCAL MANIPULATION
             │                             │
          UR5 Carrier                 Bimanual Module
             │                             │
             └────────── Carrier Flange ──┘
                            │
                    Five-Station Workspace
```

The project is intended as a **simulation/prototype feasibility
demonstration**, not as an industrial deployment or production-ready
manipulation system.

------------------------------------------------------------------------

# 2. Final Technical Objective

The final system demonstrates:

> A UR5 carrier positions a custom bimanual manipulator around a
> simulated machine-tending workspace, where predefined coordinated
> motions perform a sequential workpiece-handling workflow across five
> stations.

The demonstration communicates three main concepts:

### 2.1 Carrier-assisted manipulation

The UR5 provides the global positioning capability.

### 2.2 Local bimanual manipulation

The custom mechanism provides four additional controlled joints for
local manipulation around the task area.

### 2.3 Machine-tending workflow

The complete system operates inside a structured industrial-style
five-station environment rather than as an isolated robot animation.

------------------------------------------------------------------------

# 3. Current Project Status

## 3.1 Completed

-   UR5 carrier simulation.
-   Official UR5 `flange` and `tool0` chain.
-   Custom carrier flange.
-   Carrier flange interface frame.
-   Custom dual-arm base.
-   Left and right bimanual arms.
-   Four custom bimanual joints.
-   Xacro generation.
-   URDF validation with `check_urdf`.
-   Gazebo Classic simulation.
-   ROS 2 control integration.
-   UR5 joint trajectory controller.
-   Bimanual joint trajectory controller.
-   Joint state broadcaster.
-   Taught-pose system.
-   Machine-shop station layout.
-   Factory-style world.
-   Complete CAM-BOT demonstration cycle.
-   S3 release/retract/re-grasp sequence.
-   Gazebo material/color rendering.
-   Integrated carrier + flange + bimanual visual appearance.

## 3.2 Phase 4 status

**Phase 4 is functionally complete.**

The final visual verification showed:

-   Gray carrier flange.
-   Dark bimanual base.
-   Blue upper arms.
-   Orange forearms.
-   Factory environment.
-   Five-station workspace.
-   Working robot motion.
-   Integrated carrier/bimanual assembly.

The remaining polish item is only to preserve a final preferred camera
view if a specific presentation view is desired.

------------------------------------------------------------------------

# 4. Software and Environment

## 4.1 Operating system

``` text
Ubuntu 22.04
```

## 4.2 ROS 2

``` text
ROS 2 Humble
```

Check:

``` bash
echo $ROS_DISTRO
```

Expected:

``` text
humble
```

## 4.3 Workspace

``` text
~/tops_ws
```

Typical setup:

``` bash
source /opt/ros/humble/setup.bash
source ~/tops_ws/install/setup.bash
```

## 4.4 Gazebo

``` text
Gazebo Classic 11.10.2
```

Check:

``` bash
gazebo --version
```

------------------------------------------------------------------------

# 5. Workspace Structure

The important CAM-BOT packages are:

``` text
~/tops_ws/src/
│
├── carrier_description/
│   ├── carrier_description/
│   ├── launch/
│   ├── rviz/
│   └── urdf/
│
├── carrier_control/
│   └── carrier_control/
│
├── cambot_environment/
│   ├── launch/
│   └── worlds/
│
├── Universal_Robots_ROS2_Description/
│
└── Universal_Robots_ROS2_Gazebo_Simulation/
```

------------------------------------------------------------------------

# 6. Carrier Description Package

Package:

``` text
carrier_description
```

Important files:

``` text
src/carrier_description/
│
├── launch/
│   ├── dual_arm_demo.launch.py
│   ├── view_carrier.launch.py
│   └── view_dual_arm.launch.py
│
├── rviz/
│   └── dual_arm.rviz
│
└── urdf/
    ├── carrier_flange.xacro
    ├── dual_arm_platform.xacro
    ├── test_tool.xacro
    └── ur5_with_test_tool.xacro
```

The main integrated robot description is:

``` text
ur5_with_test_tool.xacro
```

Despite the historical filename, the active integrated assembly does not
rely on the old standalone test-tool geometry. The important custom
chain is the carrier flange and bimanual assembly.

------------------------------------------------------------------------

# 7. Robot Structure

The final robot chain is:

``` text
world
 └── base_link
      └── base_link_inertia
           └── shoulder_link
                └── upper_arm_link
                     └── forearm_link
                          └── wrist_1_link
                               └── wrist_2_link
                                    └── wrist_3_link
                                         └── flange
                                              └── tool0
                                                   └── carrier_flange
                                                        └── carrier_flange_interface
                                                             └── dual_arm_base_link
                                                                  ├── left_upper_arm
                                                                  │    └── left_forearm
                                                                  │
                                                                  └── right_upper_arm
                                                                       └── right_forearm
```

This chain has been generated and validated with `check_urdf`.

------------------------------------------------------------------------

# 8. UR5 Carrier

The carrier is a Universal Robots UR5.

The six carrier joints are:

``` text
shoulder_pan_joint
shoulder_lift_joint
elbow_joint
wrist_1_joint
wrist_2_joint
wrist_3_joint
```

The UR5 provides the global positioning motion for the CAM-BOT system.

------------------------------------------------------------------------

# 9. Carrier Flange

The custom carrier flange is mounted after `tool0`.

The interface is:

``` text
tool0
  ↓
carrier_flange
  ↓
carrier_flange_interface
  ↓
dual_arm_base_link
```

Current flange dimensions:

``` text
Length:    0.32 m
Width:     0.26 m
Thickness: 0.045 m
Mass:      1.0 kg
```

The flange is a rigid fixed interface and does not introduce an
additional actuated joint.

------------------------------------------------------------------------

# 10. Bimanual Module

The bimanual module consists of a central platform and two compact arms.

## 10.1 Base

Current base size:

``` text
0.40 × 0.28 × 0.06 m
```

The base is mounted directly to:

``` text
carrier_flange_interface
```

## 10.2 Shoulder housings

Two visual shoulder housings were added to improve the physical
appearance of the interface.

Approximate geometry:

``` text
Radius: 0.045 m
Length: 0.06 m
```

They are visual geometry and do not add extra joints.

## 10.3 Upper arms

Each upper arm:

``` text
Length: 0.15 m
Radius: 0.025 m
```

## 10.4 Forearms

Each forearm:

``` text
Length: 0.12 m
Radius: 0.020 m
```

------------------------------------------------------------------------

# 11. Bimanual Joints

The custom mechanism contains four controlled joints:

``` text
left_shoulder_joint
left_elbow_joint
right_shoulder_joint
right_elbow_joint
```

The complete system therefore has:

``` text
6 UR5 joints
+
4 bimanual joints
=
10 controlled joints
```

------------------------------------------------------------------------

# 12. Visual Materials

The intended visual appearance is:

  Component           Appearance
  ------------------- -------------------------------
  UR5                 UR5/default visual appearance
  Carrier flange      Gray
  Bimanual base       Dark gray
  Shoulder housings   Dark gray
  Left upper arm      Blue
  Right upper arm     Blue
  Left forearm        Orange
  Right forearm       Orange

## 12.1 Gazebo material issue and resolution

The original URDF/Xacro contained valid color declarations, but Gazebo
Classic's URDF-to-SDF conversion did not preserve those custom visual
materials correctly.

The diagnosis was confirmed by converting the expanded URDF using:

``` bash
gz sdf -p /tmp/cambot_colors.urdf
```

The converted SDF retained the geometry but dropped the expected
material information, causing Gazebo to render the affected components
white.

The solution was to use appropriate Gazebo material definitions in the
correct Gazebo extension structure.

After the correction and rebuild, the final Gazebo simulation visibly
renders:

``` text
Gray flange
Dark base
Blue upper arms
Orange forearms
```

This visual issue is now considered resolved.

------------------------------------------------------------------------

# 13. URDF Validation

The primary validation command is:

``` bash
xacro src/carrier_description/urdf/ur5_with_test_tool.xacro \
  > /tmp/cambot.urdf
```

Then:

``` bash
check_urdf /tmp/cambot.urdf
```

A successful validation should report:

``` text
Successfully Parsed XML
```

and show the complete chain through:

``` text
carrier_flange
carrier_flange_interface
dual_arm_base_link
left_upper_arm
left_forearm
right_upper_arm
right_forearm
```

------------------------------------------------------------------------

# 14. Build Procedure

From the workspace:

``` bash
cd ~/tops_ws

source /opt/ros/humble/setup.bash

colcon build --symlink-install \
  --packages-select carrier_description
```

Then:

``` bash
source ~/tops_ws/install/setup.bash
```

For a complete workspace rebuild:

``` bash
cd ~/tops_ws

source /opt/ros/humble/setup.bash

colcon build --symlink-install

source ~/tops_ws/install/setup.bash
```

------------------------------------------------------------------------

# 15. CAM-BOT Environment

Package:

``` text
cambot_environment
```

World:

``` text
src/cambot_environment/worlds/cambot_machine_shop.world
```

The environment is a custom factory-style machine-shop world rather than
a default Gazebo world.

------------------------------------------------------------------------

# 16. Five-Station Workspace

The five stations are:

``` text
S1 — Raw
S2 — Staging
S3 — CNC
S4 — Output
S5 — Finished
```

Approximate station positions:

``` text
S1 = (-0.65, -0.55)
S2 = ( 0.00, -0.65)
S3 = ( 0.65,  0.00)
S4 = ( 0.00,  0.65)
S5 = (-0.65,  0.55)
```

The environment includes:

-   machine-shop floor
-   factory walls
-   ceiling
-   structural columns
-   lighting
-   five work stations
-   CNC station representation
-   workpiece
-   industrial-style layout

------------------------------------------------------------------------

# 17. World Design

The factory environment was intentionally kept simple.

The project focus is:

``` text
Carrier-assisted manipulation
```

rather than:

``` text
Detailed CNC simulation
```

Therefore, the CNC station is a visual/simple task representation.

The environment provides enough structure to demonstrate:

``` text
robot positioning
+
local manipulation
+
machine tending
```

without adding unnecessary simulation complexity.

------------------------------------------------------------------------

# 18. Controllers

The final simulation uses:

``` text
joint_state_broadcaster
joint_trajectory_controller
bimanual_joint_trajectory_controller
```

Check them with:

``` bash
ros2 control list_controllers
```

The expected state is:

``` text
joint_state_broadcaster              active
joint_trajectory_controller          active
bimanual_joint_trajectory_controller active
```

------------------------------------------------------------------------

# 19. Controller Interfaces

UR5 trajectory action:

``` text
/joint_trajectory_controller/follow_joint_trajectory
```

Bimanual trajectory action:

``` text
/bimanual_joint_trajectory_controller/follow_joint_trajectory
```

The working CAM-BOT demonstration also publishes trajectories directly
to:

``` text
/joint_trajectory_controller/joint_trajectory
/bimanual_joint_trajectory_controller/joint_trajectory
```

------------------------------------------------------------------------

# 20. Taught Pose System

The project includes a pose teaching interface:

``` text
carrier_control/pose_teaching_gui.py
```

The taught poses are saved to:

``` text
src/carrier_control/config/taught_poses.yaml
```

The pose set includes:

``` text
home

s1_app
s1_grasp
s1_lift

s2_grasp

s3_app
s3_place
s3_rel
s3_retract

s4_grasp
s5_grasp
```

Each pose contains:

``` text
carrier:
  six UR5 joint values

bimanual:
  four bimanual joint values
```

This provides a practical way to teach and reproduce the machine-shop
motions.

------------------------------------------------------------------------

# 21. Current Taught Pose Data

The current saved pose set is:

``` yaml
s1_app:
  carrier: [-2.525, -1.293, 1.383, 0.361, 1.714, 0.18]
  bimanual: [-0.0, 0.0, 0.0, 0.0]

s1_grasp:
  carrier: [-2.525, -1.293, 1.383, 0.361, 1.714, 0.18]
  bimanual: [-2.194, -0.734, 2.33, -0.634]

s1_lift:
  carrier: [-2.525, -1.293, 0.932, 0.361, 1.714, 0.18]
  bimanual: [-2.194, -0.734, 2.33, -0.634]

s3_app:
  carrier: [-0.18, -1.683, 1.503, 0.361, 1.714, 0.12]
  bimanual: [-2.194, -0.734, 2.33, -0.634]

s3_place:
  carrier: [-0.18, -1.683, 1.744, 0.361, 1.714, 0.12]
  bimanual: [-2.194, -0.734, 2.33, -0.634]

s3_rel:
  carrier: [-0.18, -1.683, 1.744, 0.361, 1.714, 0.12]
  bimanual: [-0.0, -0.373, -0.0, -0.435]

s3_retract:
  carrier: [-0.18, -2.435, 2.014, 0.361, 1.714, 0.12]
  bimanual: [-0.0, -0.037, -0.0, -0.075]

s2_grasp:
  carrier: [-1.683, -1.293, 1.383, 0.361, 1.714, 0.09]
  bimanual: [-2.194, -0.734, 2.33, -0.634]

s4_grasp:
  carrier: [1.533, -1.473, 1.623, 0.361, 1.714, 0.09]
  bimanual: [-2.194, -0.734, 2.33, -0.634]

s5_grasp:
  carrier: [2.495, -1.473, 1.623, 0.361, 1.714, 0.301]
  bimanual: [-2.194, -0.734, 2.33, -0.634]

home:
  carrier: [-1.383, -1.533, -0.09, 1.503, 1.653, -0.12]
  bimanual: [-0.0, 0.0, 0.0, 0.0]
```

------------------------------------------------------------------------

# 22. CAM-BOT Demonstration Cycle

The primary working demonstration executable is:

``` text
cambot_demo_cycle
```

Run it with:

``` bash
source /opt/ros/humble/setup.bash
source ~/tops_ws/install/setup.bash

ros2 run carrier_control cambot_demo_cycle
```

The demonstrated workflow includes:

``` text
HOME
  ↓
S1 approach
  ↓
S1 grasp
  ↓
S1 lift
  ↓
S2
  ↓
S3 approach
  ↓
S3 place
  ↓
S3 work/processing position
  ↓
S3 release
  ↓
S3 retract
  ↓
S3 re-grasp
  ↓
S4
  ↓
S5
```

The S3 section was deliberately changed so that, after releasing the
workpiece, the carrier retracts and returns to re-grasp the processed
workpiece.

------------------------------------------------------------------------

# 23. Motion Strategy

The project initially experimented with manually interpolated
intermediate points.

That approach produced undesirable motion quality.

The current approach uses:

``` text
direct taught-pose → taught-pose trajectories
```

with appropriately longer move times.

This gives a simpler and visually smoother machine-tending sequence.

The project does not currently depend on manually inserted:

``` text
25%
50%
75%
```

trajectory points.

------------------------------------------------------------------------

# 24. Main Gazebo Launch

The final simulation launch is:

``` bash
source /opt/ros/humble/setup.bash
source ~/tops_ws/install/setup.bash

ros2 launch cambot_environment cambot_gazebo.launch.py
```

This starts:

``` text
Gazebo
    ↓
CAM-BOT machine-shop world
    ↓
robot_state_publisher
    ↓
robot_description
    ↓
CAM-BOT spawned in Gazebo
    ↓
joint_state_broadcaster
    ↓
joint_trajectory_controller
    ↓
bimanual_joint_trajectory_controller
```

------------------------------------------------------------------------

# 25. Complete Demonstration Procedure

## Terminal 1 --- Start simulation

``` bash
source /opt/ros/humble/setup.bash
source ~/tops_ws/install/setup.bash

ros2 launch cambot_environment cambot_gazebo.launch.py
```

Wait for Gazebo to finish loading.

## Terminal 2 --- Verify controllers

``` bash
source /opt/ros/humble/setup.bash
source ~/tops_ws/install/setup.bash

ros2 control list_controllers
```

Confirm:

``` text
joint_state_broadcaster              active
joint_trajectory_controller          active
bimanual_joint_trajectory_controller active
```

## Terminal 3 --- Run demonstration

``` bash
source /opt/ros/humble/setup.bash
source ~/tops_ws/install/setup.bash

ros2 run carrier_control cambot_demo_cycle
```

------------------------------------------------------------------------

# 26. TF Verification

The important TF chain is:

``` text
world
 ↓
UR5 base
 ↓
UR5 wrist
 ↓
tool0
 ↓
carrier_flange
 ↓
carrier_flange_interface
 ↓
dual_arm_base_link
 ↓
left/right bimanual arms
```

Useful verification:

``` bash
ros2 run tf2_ros tf2_echo tool0 carrier_flange
```

and:

``` bash
ros2 run tf2_ros tf2_echo carrier_flange_interface dual_arm_base_link
```

For a complete frame graph:

``` bash
ros2 run tf2_tools view_frames
```

------------------------------------------------------------------------

# 27. Joint-State Verification

Check:

``` bash
ros2 topic echo /joint_states --once
```

The final system contains ten controlled joints:

``` text
UR5:
  shoulder_pan_joint
  shoulder_lift_joint
  elbow_joint
  wrist_1_joint
  wrist_2_joint
  wrist_3_joint

Bimanual:
  left_shoulder_joint
  left_elbow_joint
  right_shoulder_joint
  right_elbow_joint
```

------------------------------------------------------------------------

# 28. Direct Bimanual Controller Test

A direct bimanual test that was verified successfully is:

``` bash
ros2 action send_goal \
/bimanual_joint_trajectory_controller/follow_joint_trajectory \
control_msgs/action/FollowJointTrajectory \
"{trajectory: {joint_names: ['left_shoulder_joint', 'left_elbow_joint', 'right_shoulder_joint', 'right_elbow_joint'], points: [{positions: [0.0, -0.8, 0.0, 0.8], time_from_start: {sec: 3}}, {positions: [0.0, 0.0, 0.0, 0.0], time_from_start: {sec: 6}}]}}"
```

This was used to verify that the four custom bimanual joints can
actually move through the ROS 2 controller.

------------------------------------------------------------------------

# 29. Phase History

## Phase 1 --- UR5 Carrier Baseline

Completed:

-   UR5 simulation.
-   MoveIt investigation/baseline.
-   RViz control.
-   Joint trajectory execution.
-   Machine-shop carrier waypoints.
-   Baseline measurements.

The baseline UR5 machine-shop cycle was verified independently.

------------------------------------------------------------------------

# 30. Phase 2 --- Mass Sensitivity

The project also established baseline data and mass-sensitivity
experiments.

Relevant experiment area:

``` text
Task2/
experiments/
mass_sensitivity/
```

Example data included:

``` text
baseline_2.330kg.csv
exp02_forearm_2.563kg.csv
```

Earlier baseline data also included:

``` text
results/ur5_baseline/ur5_baseline.csv
```

These experiments belong to the quantitative/experimental part of the
project and can be incorporated into the final results section.

------------------------------------------------------------------------

# 31. Phase 3 --- Carrier/Bimanual Integration Preparation

The carrier/bimanual integration established:

``` text
UR5
 ↓
tool0
 ↓
carrier flange
 ↓
interface
 ↓
dual-arm platform
```

The custom bimanual mechanism was then connected to the UR5 carrier.

------------------------------------------------------------------------

# 32. Phase 4 --- Integrated Visual Simulation

Phase 4 was defined as the stage for establishing the complete visual
integrated system.

### Phase 4 target

``` text
PHASE 4
│
├── Step 1  Verify current visual baseline       ✅
├── Step 2  Perfect UR5 + flange appearance     ✅
├── Step 3  Perfect bimanual visual geometry    ✅
├── Step 4  Verify TF/frame structure visually  ✅
├── Step 5  Verify all 10 joints visually       ✅
├── Step 6  Verify factory/world composition    ✅
├── Step 7  Set final Gazebo camera              🟡
├── Step 8  Run complete visual cycle            ✅
└── Step 9  Freeze Phase 4 visual baseline       🔜
```

The integrated visual simulation has now been established.

------------------------------------------------------------------------

# 33. Phase 4 Visual Result

The final visual simulation shows:

``` text
                   BLUE       BLUE
                    │           │
                  ORANGE      ORANGE
                    │           │
                ┌─────────────────┐
                │  DARK GRAY BASE │
                └─────────────────┘
                ═══════════════════
                    GRAY FLANGE
                ═══════════════════
                       UR5
```

The complete assembly is positioned inside the factory environment.

The factory contains the five-station machine-tending layout.

------------------------------------------------------------------------

# 34. Workpiece Status

The current workpiece is primarily a **visual/kinematic
representation**.

The current grasp/release sequence represents the task logically and
visually.

The workpiece does not yet require a fully physical attachment
mechanism.

Physical attachment/transport can be addressed in Phase 5 if needed.

------------------------------------------------------------------------

# 35. Important Current Limitation

The current simulation demonstrates:

``` text
robot motion
+
carrier positioning
+
bimanual coordinated motion
+
station workflow
```

It does not yet represent:

``` text
force-controlled grasping
full physical grasp dynamics
real CNC machining physics
full bimanual inverse kinematics
industrial collision certification
real hardware execution
```

These are outside the core simulation feasibility scope.

------------------------------------------------------------------------

# 36. MoveIt 2 Scope

MoveIt 2 is **not mandatory for project completion**.

The project already has a working trajectory-control solution.

The recommended MoveIt strategy is:

### Step 1 --- Inspect

Determine:

-   existing UR5 MoveIt configuration
-   planning groups
-   end-effector definition
-   SRDF
-   controllers
-   whether the custom flange is included

### Step 2 --- Minimal integration

Attempt:

``` text
UR5
 ↓
carrier flange
 ↓
dual-arm base
```

### Step 3 --- Decision gate

If integration is straightforward:

-   update required links/joints
-   update planning groups
-   update controllers if required
-   test one simple planned motion

If integration becomes complex:

-   keep the working trajectory-controller system
-   document MoveIt as investigated/future work

The project must not be blocked by MoveIt integration.

------------------------------------------------------------------------

# 37. Phase 5 --- Remaining Work

After Phase 4 is frozen, Phase 5 should contain the remaining
engineering and experimental work.

## 37.1 Workpiece transport

Potential next step:

``` text
S1
 ↓
grasp
 ↓
attach
 ↓
transport
 ↓
S3
 ↓
release
```

The current representation is primarily visual/kinematic.

------------------------------------------------------------------------

## 37.2 Complete physical/kinematic workflow

Establish the complete sequence:

``` text
S1 Raw
 ↓
S2 Staging
 ↓
S3 CNC
 ↓
processing
 ↓
S4 Output
 ↓
S5 Finished
```

------------------------------------------------------------------------

## 37.3 CNC/workstation state

The CNC station can remain simplified.

A possible logical state machine is:

``` text
READY
  ↓
PART_LOADED
  ↓
PROCESSING
  ↓
PROCESS_COMPLETE
  ↓
PART_READY_FOR_PICKUP
```

------------------------------------------------------------------------

## 37.4 Motion refinement

Measure and refine:

-   motion duration
-   velocity
-   acceleration
-   repeatability
-   collision margins
-   cycle consistency

------------------------------------------------------------------------

## 37.5 Quantitative metrics

Potential metrics:

  Metric                       Status
  ---------------------------- ------------
  Cycle time                   To measure
  Station-to-station time      To measure
  Repeatability                To measure
  Successful cycles            To measure
  Failure count                To measure
  Joint motion                 Available
  Payload/workpiece behavior   Phase 5
  Overall success rate         To measure

Do not report numerical results until they have actually been measured.

------------------------------------------------------------------------

# 38. Recommended Phase 5 Demonstration

The final Phase 5 demonstration should aim for:

``` text
                    CAM-BOT
                       │
                       ▼
                    HOME
                       │
                       ▼
                  S1 — RAW
                       │
                    GRASP
                       │
                       ▼
                 S2 — STAGING
                       │
                       ▼
                   S3 — CNC
                       │
                  LOAD PART
                       │
                       ▼
                   PROCESS
                       │
                       ▼
                PICK PROCESSED
                       │
                       ▼
                  S4 — OUTPUT
                       │
                       ▼
                 S5 — FINISHED
```

The exact implementation can remain trajectory-based if physical
grasping is not required.

------------------------------------------------------------------------

# 39. Project Definition of Done

The core CAM-BOT project is considered complete when:

``` text
Reliable simulation launch
        +
UR5 carrier
        +
custom carrier flange
        +
custom bimanual module
        +
five-station environment
        +
complete machine-tending sequence
        +
repeatable demonstration
        +
basic quantitative metrics
        +
technical documentation
```

MoveIt 2 is an enhancement rather than a mandatory completion criterion.

------------------------------------------------------------------------

# 40. Final Results Table

  Parameter                       Current Result
  ------------------------------- ------------------------------
  Project                         CAM-BOT
  Carrier robot                   UR5
  Carrier interface               Custom carrier flange
  Bimanual mechanism              Custom 4-DOF module
  Carrier joints                  6
  Bimanual joints                 4
  Total controlled joints         10
  ROS 2                           Humble
  OS                              Ubuntu 22.04
  Simulator                       Gazebo Classic 11.10.2
  Visualization                   Gazebo + RViz
  Environment                     Five-station machine shop
  Motion control                  ROS 2 trajectory controllers
  Taught poses                    Implemented
  Complete demonstration cycle    Working
  S3 release/re-grasp             Implemented
  Gazebo custom colors            Working
  Physical workpiece attachment   Phase 5
  Quantitative final metrics      Phase 5
  MoveIt 2                        Optional investigation
  Industrial deployment           Not claimed

------------------------------------------------------------------------

# 41. Troubleshooting

## 41.1 Package not found

If a package exists under:

``` text
~/tops_ws/src
```

but:

``` bash
ros2 pkg prefix <package>
```

returns package not found, build and source the workspace:

``` bash
cd ~/tops_ws

colcon build --symlink-install \
  --packages-up-to <package>

source ~/tops_ws/install/setup.bash
```

------------------------------------------------------------------------

## 41.2 Controller unavailable

Check:

``` bash
ros2 control list_controllers
```

Expected:

``` text
joint_state_broadcaster
joint_trajectory_controller
bimanual_joint_trajectory_controller
```

If the controller is missing, check that the simulation was launched
from the CAM-BOT environment launch.

------------------------------------------------------------------------

## 41.3 Robot description validation

Generate:

``` bash
xacro src/carrier_description/urdf/ur5_with_test_tool.xacro \
  > /tmp/cambot.urdf
```

Then:

``` bash
check_urdf /tmp/cambot.urdf
```

------------------------------------------------------------------------

## 41.4 Gazebo robot appears white

Do not immediately change the Xacro colors.

First inspect the expanded URDF:

``` bash
grep -n -A8 -B2 \
"CarrierFlangeGrey\|DualArmUpperMaterial\|DualArmForearmMaterial" \
/tmp/cambot.urdf
```

Then inspect Gazebo conversion:

``` bash
gz sdf -p /tmp/cambot.urdf > /tmp/cambot.sdf
```

The final project already resolved this issue by correcting the Gazebo
material handling.

------------------------------------------------------------------------

# 42. Recommended Final Launch Checklist

Before a presentation or recorded demonstration:

``` bash
cd ~/tops_ws

source /opt/ros/humble/setup.bash
source ~/tops_ws/install/setup.bash

ros2 launch cambot_environment cambot_gazebo.launch.py
```

Then verify:

``` bash
ros2 control list_controllers
```

Then:

``` bash
ros2 run carrier_control cambot_demo_cycle
```

Check visually:

``` text
[ ] UR5 visible
[ ] Carrier flange visible
[ ] Flange gray
[ ] Bimanual base dark
[ ] Upper arms blue
[ ] Forearms orange
[ ] Five stations visible
[ ] CNC visible
[ ] Workpiece visible
[ ] Robot remains inside workspace
[ ] Complete motion sequence executes
```

------------------------------------------------------------------------

# 43. Final Architecture

``` text
                              CAM-BOT
                                 │
                         ROS 2 Humble
                                 │
             ┌───────────────────┴───────────────────┐
             │                                       │
      carrier_description                       carrier_control
             │                                       │
           Xacro                              taught poses / cycle
             │                                       │
             ▼                                       ▼
    robot_description                    trajectory controllers
             │                                       │
             └──────────────────┬────────────────────┘
                                │
                     robot_state_publisher
                                │
                                ▼
                              TF tree
                                │
             ┌──────────────────┴──────────────────┐
             │                                     │
          Gazebo                                  RViz
             │
       CAM-BOT World
             │
     ┌───────┴────────┐
     │                │
  UR5 Carrier    Bimanual Module
     │                │
     └──────┬─────────┘
            │
      Carrier Flange
            │
      Five-Station Cell
            │
     Machine-Tending
       Demonstration
```

------------------------------------------------------------------------

# 44. Final Project Claim

The appropriate project-level claim is:

> **CAM-BOT demonstrates the feasibility of a carrier-assisted bimanual
> manipulation architecture for simulated machine-tending tasks.**

The system demonstrates:

-   global positioning using a UR5 carrier
-   a custom carrier/flange interface
-   local bimanual manipulation
-   coordinated trajectory control
-   a structured five-station machine-shop environment
-   a complete simulated machine-tending sequence

The project should be presented as a **simulation/prototype feasibility
demonstration**, not as an industrial-ready manipulation system.

------------------------------------------------------------------------

# 45. Current Milestone

## PHASE 4 --- COMPLETE

``` text
UR5 Carrier                         ✅
Carrier Flange                      ✅
Flange Interface                    ✅
Bimanual Platform                   ✅
4-DOF Bimanual Motion               ✅
10-Joint System                     ✅
ROS 2 Controllers                   ✅
Taught Poses                        ✅
Five-Station Environment            ✅
Gazebo Visual Materials             ✅
Complete Demonstration Cycle        ✅
S3 Release → Retract → Re-grasp     ✅
TF Chain                            ✅
Factory Composition                 ✅
```

### Phase 5 starts with:

``` text
Workpiece transport/attachment
        ↓
Complete workflow refinement
        ↓
Metrics and experiments
        ↓
Optional MoveIt investigation
        ↓
Final screenshots/video
        ↓
Final technical documentation
```

------------------------------------------------------------------------

# 46. Quick Reference

### Build

``` bash
cd ~/tops_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source ~/tops_ws/install/setup.bash
```

### Launch simulation

``` bash
ros2 launch cambot_environment cambot_gazebo.launch.py
```

### Check controllers

``` bash
ros2 control list_controllers
```

### Run CAM-BOT cycle

``` bash
ros2 run carrier_control cambot_demo_cycle
```

### Validate Xacro

``` bash
xacro src/carrier_description/urdf/ur5_with_test_tool.xacro \
  > /tmp/cambot.urdf

check_urdf /tmp/cambot.urdf
```

### Check TF

``` bash
ros2 run tf2_tools view_frames
```

### Check joint states

``` bash
ros2 topic echo /joint_states --once
```

------------------------------------------------------------------------

# 47. Project Completion Perspective

The most important achievement is that the project has moved from
isolated UR5 simulation work to an integrated CAM-BOT demonstration:

``` text
                 BEFORE
                   │
                   ▼
             UR5 simulation
                   │
                   ▼
             custom flange
                   │
                   ▼
             custom bimanual
                   │
                   ▼
          separate motion tests
                   │
                   ▼
                 NOW
                   │
                   ▼
          INTEGRATED CAM-BOT
                   │
          ┌────────┴────────┐
          │                 │
       carrier          bimanual
          │                 │
          └────────┬────────┘
                   │
             machine shop
                   │
             five stations
                   │
          complete demonstration
```

**Phase 4 establishes the integrated visual and functional baseline.
Phase 5 should focus on turning that baseline into a measured,
documented machine-tending demonstration without unnecessarily expanding
the scope.**



````markdown
# CAM-BOT — Quick Commands

## 1. Setup & Build

```bash
cd ~/tops_ws

source /opt/ros/humble/setup.bash

colcon build --symlink-install

source ~/tops_ws/install/setup.bash
````

## 2. Validate URDF

```bash
xacro src/carrier_description/urdf/ur5_with_test_tool.xacro \
> /tmp/cambot.urdf

check_urdf /tmp/cambot.urdf
```

## 3. Launch Gazebo

### Terminal 1

```bash
source /opt/ros/humble/setup.bash
source ~/tops_ws/install/setup.bash

ros2 launch cambot_environment cambot_gazebo.launch.py
```

## 4. Check Controllers

### Terminal 2

```bash
source /opt/ros/humble/setup.bash
source ~/tops_ws/install/setup.bash

ros2 control list_controllers
```

## 5. Run CAM-BOT Cycle

### Terminal 3

```bash
source /opt/ros/humble/setup.bash
source ~/tops_ws/install/setup.bash

ros2 run carrier_control cambot_demo_cycle
```

## 6. Optional Checks

### Joint states

```bash
ros2 topic echo /joint_states --once
```

### TF

```bash
ros2 run tf2_tools view_frames
```

### Check flange TF

```bash
ros2 run tf2_ros tf2_echo tool0 carrier_flange
```

### Check bimanual TF

```bash
ros2 run tf2_ros tf2_echo \
carrier_flange_interface dual_arm_base_link
```

```
```
