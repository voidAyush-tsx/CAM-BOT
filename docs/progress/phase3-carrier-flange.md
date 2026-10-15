# Phase 3 — Carrier Flange & Bimanual Placeholder

> **Archival provenance note (2026-10-15):** The development-machine warning
> below described the state when this report was written. Flange and dual-arm
> Xacro plus launch source were later committed (see [AY-01 inventory](../evidence/AY-01/manifest.json)
> and [current status](../STATUS.md)). Preserve the original wording as a
> historical snapshot, not today's repository state.

**Status:** 🔧 In progress
**Goal:** define a clean, parameterized mechanical and TF interface between the
UR5 wrist and a future bimanual module — without designing the bimanual module.

> ⚠️ **Everything described here exists on a development machine and is not in
> this repository.** No flange Xacro, dual-arm Xacro, launch file, RViz config,
> or `dual_arm_cycle.py` has been committed. Treat this document as a record of
> work to be recovered and committed, not as a description of the repository's
> contents. See [`AUDIT.md`](../../AUDIT.md) §2.1.

---

## 1. Attachment point

The official UR5 chain ends:

```text
wrist_3_link → flange → tool0
```

All custom geometry attaches **after `tool0`**, leaving `ur_description`
untouched. Verified against the installed `ur_macro.xacro`.

---

## 2. Kinematic chain

Full tree as validated by `check_urdf`:

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
                                └── flange
                                    └── tool0
                                        └── carrier_flange
                                            └── carrier_flange_interface
                                                └── dual_arm_base_link
                                                    ├── left_upper_arm
                                                    │   └── left_forearm
                                                    └── right_upper_arm
                                                        └── right_forearm
```

Key fixed joints: `tool0_to_carrier_flange`, `carrier_flange_to_interface`.

Target TF architecture:

```text
world → Carrier Arm (CA) → carrier_flange (CF) → Bimanual Module (BM)
```

Validation command:

```bash
xacro src/carrier_description/urdf/ur5_with_test_tool.xacro > /tmp/ur5_phase4.urdf
check_urdf /tmp/ur5_phase4.urdf
# robot name is: ur5_with_test_tool
# ---------- Successfully Parsed XML ---------------
```

---

## 3. From test tool to flange

The dummy tool from Phase 1 (`tool0 → test_tool_base → test_tool_tip`) served
only to prove custom geometry could attach. It was reparented:

```xml
<!-- was -->  <xacro:test_tool parent_link="tool0"/>
<!-- now -->  <xacro:test_tool parent_link="carrier_flange"/>
```

and then superseded entirely by the dual-arm mechanism. The test tool is no
longer part of the working kinematic tree.

One URDF error was hit and fixed along the way:

```text
Error: Box shape has no size attribute
Could not parse visual element for Link [carrier_flange]
```

---

## 4. Bimanual placeholder

Deliberately minimal. Each arm is shoulder → upper arm → elbow → forearm, giving
**four controllable joints**:

| Joint | Axis |
|---|---|
| `left_shoulder_joint` | Z |
| `left_elbow_joint` | X |
| `right_shoulder_joint` | Z |
| `right_elbow_joint` | X |

```text
        Future BM
      ○           ○
      │           │
      └─────┬─────┘
            │
   ┌────────────────┐
   │ Carrier Flange │
   └───────┬────────┘
           │
          UR5
```

The base plate started at `1.0 × 0.5 × 0.1 m`; scaling to more realistic
dimensions was discussed but not concluded — **open item**.

The placeholder exists only to validate mounting geometry, spatial arrangement,
carrier reach, workspace interaction, collision envelope, and visualization. It
is not a design.

---

## 5. Motion controller

`carrier_control/carrier_control/dual_arm_cycle.py` publishes `sensor_msgs/JointState`
on `/joint_states` for the four custom joints, registered in `setup.py` as:

```python
'dual_arm_cycle = carrier_control.dual_arm_cycle:main',
```

**Smoothing** — cubic ease, published at ~50 Hz (`time.sleep(0.02)`):

```python
s = 3.0 * alpha**2 - 2.0 * alpha**3
```

**Sequence:**

```text
HOME → APPROACH → GRASP → HOLD → TRANSPORT → PLACE → RELEASE → HOME
```

| Stage | Left shoulder | Left elbow | Right shoulder | Right elbow |
|---|---:|---:|---:|---:|
| HOME | 0 | 0 | 0 | 0 |
| Approach | −0.45 | 0 | +0.45 | 0 |
| Grasp | −0.45 | −1.20 | +0.45 | +1.20 |
| Transport | further | −1.20 | further | +1.20 |
| Place | further | −1.20 | further | +1.20 |
| Release | — | 0 | — | 0 |
| HOME | 0 | 0 | 0 | 0 |

⚠️ This is four independent joint interpolations that *look* like a pick-and-place.
The arms do not maintain a fixed relative pose, so they are not physically
holding a common object. Making the motion a genuine closed-chain bimanual
constraint is the substantive next step after the launch fix.

---

## 6. Visualization

Launch files created (uncommitted): `view_dual_arm.launch.py`,
`dual_arm_demo.launch.py`, `view_carrier.launch.py`.
RViz config intended at `carrier_description/rviz/dual_arm.rviz`.

`joint_state_publisher_gui` allows interactive control of the four custom
joints, and the model renders correctly.

---

## 7. The current blocker

`dual_arm_demo.launch.py` builds the description with:

```python
robot_description = ParameterValue(Command(['xacro ', xacro_file]), value_type=str)
```

and launches `robot_state_publisher`, `rviz2`, and `dual_arm_cycle`. The
description *is* present in the launch file, yet the RViz / robot-description
side does not come up reliably when the cycle launch is used.

Likely cause: both `dual_arm_cycle` and `joint_state_publisher_gui` publish to
`/joint_states`, so if the GUI is still running the two fight over the topic.
Verify only one publisher is active, then check node startup ordering.

**Do not modify `dual_arm_cycle.py` to chase this — the motion code works.**
The fault is in launch integration.

---

## 8. Definition of done for Phase 4

- [ ] **Commit everything described above** ← blocking
- [ ] One command brings up description → RSP → joint states → cycle → RViz
- [ ] `carrier_flange.xacro` genuinely parameterized (`flange_length`,
      `flange_width`, `flange_thickness`, `mount_spacing`, `mount_height`,
      `tilt_angle`)
- [ ] Flange base plate scaled to realistic dimensions
- [ ] `docs/reference/carrier_flange.md` documenting the interface contract
- [ ] TF verification evidence (`tf2_echo tool0 dual_arm_base_link`) captured
- [ ] Arms move as a coordinated pair rather than four independent joints

**Next:** Phase 3 (workspace characterization) and Phase 5 (baseline logging)
are both still outstanding — see [`ROADMAP.md`](../ROADMAP.md).
