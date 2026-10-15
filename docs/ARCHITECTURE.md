# CAMBOT — Architecture

**Evidence scope (2026-10-15):** This is the implemented visual ROS 2 Humble
topology. The [status matrix](STATUS.md) separates available source, observed
visual runs, unverified actuated simulation, and measured visual cycles.
Station geometry is an assumption; the four-joint module is a visual
placeholder, not a validated gripper.

## Hierarchy

```text
                        CAMBOT
                           │
             ┌─────────────┴─────────────┐
             │                           │
    Global positioning           Local manipulation
             │                           │
      Carrier Arm (CA)           ┌───────┴───────┐
             │                   │               │
        UR5, 6 DOF          Left arm        Right arm
             │              (2 DOF)          (2 DOF)
             └──────────┬────────┴───────┬───────┘
                        │                │
              Hierarchical task & motion coordination
                        │
                 CNC machine tending
```

The carrier moves the *system*; the arms move the *workpiece*. Separating them
is the entire premise of the project.

## Kinematic chain

```text
world
└── base_link
    └── base_link_inertia
        └── shoulder_link
            └── upper_arm_link
                └── forearm_link
                    └── wrist_1_link
                        └── wrist_2_link
                            └── wrist_3_link
                                └── flange              ← upstream UR5 ends here
                                    └── tool0
                                        └── carrier_flange           (CF)
                                            └── carrier_flange_interface
                                                └── dual_arm_base_link  (BM)
                                                    ├── left_upper_arm
                                                    │   └── left_forearm
                                                    └── right_upper_arm
                                                        └── right_forearm
```

Everything at or above `tool0` comes from `ur_description` and is not modified.
Everything below is CAMBOT's.

## Interface contract: CF

The carrier flange is the project's key abstraction — the seam between work that
is done (carrier) and work that is deferred (bimanual module).

| Property | Value |
|---|---|
| Parent link | `tool0` |
| Attachment joint | `tool0_to_carrier_flange` (fixed) |
| Child link | `carrier_flange` |
| Mount frame | `carrier_flange_interface` |
| Parameters | `flange_length`, `flange_width`, `flange_thickness`, `mount_spacing`, `mount_height`, `tilt_angle` |

Any future bimanual module attaches at `carrier_flange_interface` and needs to
know nothing else about the carrier.

## Joints

**Carrier (UR5), 6 DOF** — `shoulder_pan`, `shoulder_lift`, `elbow`,
`wrist_1`, `wrist_2`, `wrist_3`. The current visual launch publishes
assumed carrier joint values from the coordinator. A separate controller
entry point exists but fails closed with the supplied unvalidated targets.
Historical MoveIt 2/controller descriptions have no selected live controller
bring-up in this checkout.

**Bimanual placeholder, 4 DOF**

| Joint | Axis |
|---|---|
| `left_shoulder_joint` | Z |
| `left_elbow_joint` | X |
| `right_shoulder_joint` | Z |
| `right_elbow_joint` | X |

Driven by direct `/joint_states` publication. This is predefined visual motion,
not force-controlled grasping.

**Visual workpiece, 3 DOF** — three world-referenced prismatic joints provide an
observable kinematic position. Logical ownership/state is published separately;
there is no Gazebo attachment or grasp physics.

## Runtime topology

```text
carrier_description/urdf/*.xacro
            │ xacro
            ▼
     robot_description
            │
            ▼
  robot_state_publisher ──► /tf, /tf_static ──► RViz
            ▲
            │
      /joint_states
            ▲
     machine_tending_coordinator
     (assumed UR5 + 4 custom + 3 workpiece joints)
     + task/workpiece/coordination state
```

This is **visual mode**, with exactly one authoritative `/joint_states`
publisher observed in the AY-10 capture. Controller mode would instead require
a selected controller and joint-state broadcaster; in that mode the coordinator
must not publish UR5 joints. It is not demonstrated here.

## Historical planning interface

The following comes from the Phase 1 record and must not be read as current
controller acceptance evidence.

| Property | Value |
|---|---|
| Planning group | `ur_manipulator` |
| Chain | `base_link → tool0` |
| Action server | `/move_group` |
| Execution | `/joint_trajectory_controller/follow_joint_trajectory` |
| Named states | `HOME`, `UP`, `TEST_CONFIGURATION` |

## Packages

| Package | Type | Contents |
|---|---|---|
| `carrier_description` | `ament_python` | URDF/Xacro, meshes, launch, RViz configs |
| `carrier_control` | `ament_python` | trajectory and cycle nodes |

**`carrier_control` executables:**

```text
machine_shop_trajectory     Cartesian trajectory (superseded — see DECISIONS D-01)
machine_shop_joint_cycle    legacy joint-space machine-shop cycle
plot_machine_shop_path      records /joint_states, renders 3D path
dual_arm_cycle              legacy generic bimanual visual cycle
machine_tending_coordinator named, bounded machine-tending visual/coordinator cycle
```

Runtime contracts and proof gates are specified in [`INTERFACES.md`](INTERFACES.md).
