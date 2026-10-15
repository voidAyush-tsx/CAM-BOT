# CAMBOT — Design Decisions

Decisions and the reasoning behind them. Append; don't rewrite history.

---

## D-01 — Waypoints are joint configurations, not Cartesian poses

**Date:** Phase 1 · **Status:** Adopted

Hand-picked Cartesian targets produced repeated planning failures (MoveIt error
codes `99999` and `-4`) even for points that looked geometrically reasonable
and adjacent to points that worked.

Cartesian coordinates carry no guarantee of a reachable, well-conditioned,
collision-free IK solution. Stations are instead taught by positioning the UR5
with MoveIt's RViz interactive marker and recording `/joint_states`, making
every configuration reachable by construction.

**Trade-off:** joint configurations are tied to this base placement. If the
carrier base moves, they must be re-taught. Accepted for now; Phase 6 will
revisit when carrier placement becomes a variable.

---

## D-02 — Custom geometry attaches after `tool0`

**Date:** Phase 1 · **Status:** Adopted

`ur_description` is included via its official `ur_macro.xacro` rather than
vendored. All custom links attach below `tool0`, so upstream UR packages can be
updated without merge conflicts and the official
`wrist_3_link → flange → tool0` chain stays authoritative.

---

## D-03 — Stop mass experiments at EXP03

**Date:** Phase 2 · **Status:** Adopted

EXP01–03 cover distal, mid, and proximal links. A fourth perturbation would add
another point to a noisy dataset without answering a new question, and the
derived-acceleration metric is already at the edge of what unsynchronized
recordings support.

The binding constraint on the project is architectural (the CA → CF → BM
interface), not UR5 dynamics. Effort moves to Phase 4.

---

## D-04 — Defer the real bimanual design

**Date:** Phase 4 · **Status:** Adopted

The bimanual module is represented by a four-joint placeholder — two simple arms
of shoulder + elbow — not a designed mechanism.

Designing real arms before knowing the flange interface, the carrier's reachable
workspace, and the best carrier placement would mean designing against unknown
constraints and redoing it. The placeholder is enough to validate mounting
geometry, spatial arrangement, reach, collision envelope, and visualization.

**Consequence:** the current `dual_arm_cycle` moves four joints independently.
It resembles a pick-and-place but the arms do not hold a common object. That is
acceptable for a placeholder and must be stated whenever the demo is shown.

---

## D-05 — Interpret derived accelerations with caution

**Date:** Phase 2 · **Status:** Adopted

Baseline and experiment recordings differ in sample count and duration, and
acceleration is obtained by applying `numpy.gradient` twice. Double numerical
differentiation of unsynchronized data amplifies sampling noise heavily.

Results are reported as trajectory *statistics*, never as torque, motor current,
or physical acceleration capability. Percentage changes in the hundreds are
presented as artifacts unless independently corroborated.

---

## D-06 — `waypoints.yaml` becomes the single waypoint source

**Date:** Phase 4 · **Historical status:** ⚠️ Agreed, not implemented
· **Current status:** Implemented in `carrier_control` as audited below

The following rationale and action describe the state at the time:

Waypoints currently exist twice: in `config/waypoints.yaml` (which no node
reads) and hardcoded inside `machine_shop_joint_cycle.py`. Two sources will
drift.

**Action:** move `waypoints.yaml` inside `carrier_description`, install it via
`setup.py` `data_files`, and load it at node startup.

**2026-10-15 source audit:** The historical status/action above is superseded
in implementation by `src/carrier_control/config/waypoints.yaml`, installed
by `carrier_control/setup.py` and loaded by `machine_shop_joint_cycle.py`.
The root `config/waypoints.yaml` is a source mirror. No claim is made that the
historical plan's exact destination (`carrier_description`) was followed.

---

## D-07 — Separate visual assumptions from controller-validated targets

**Date:** 2026-10-15 · **Status:** Adopted

The five station poses are configurable visual assumptions. Legacy P1–P4 joint
values are retained as provenance but are not declared valid for the newly named
stations; S5 has no taught target. Controller mode therefore fails closed until
all targets are explicitly validated.

Visual mode may animate assumed carrier joints and workpiece joints, but its
records always set `runtime_verified=false` and `end_to_end_verified=false`.
This prevents an RViz sequence from being reported as Gazebo actuation or
verified grasping. AY-10/11 later measured **visual** FSM timing from live ROS
events; those records are measurements of the visual workflow only.

---

## D-08 — Preserve historical reports and classify current evidence

**Date:** 2026-10-15 · **Status:** Adopted

Keep the Phase 1, flange and Phase 4 progress documents as historical reports.
Add provenance notes where present repository evidence differs. The current
[status matrix](STATUS.md) distinguishes available source, live visual ROS,
actuated simulation, and measured complete visual cycles. A written historical
claim alone cannot promote current controller verification.

---

## D-09 — Scope five trials to one fixed visual scenario

**Date:** 2026-10-15 · **Status:** Adopted

The user qualified visual ROS trials. AY-10 capture 03 contains five actual
attempts under one configuration and a sealed raw manifest; preliminary
captures 01 and 02 remain separate. AY-11/12 derive descriptive metrics and
plots from that raw set. A visual carrier move counts as completed only when
its exact goal publication is observed; it is not a controller action result.
No optimization, grasp or physical-CNC claim follows from this dataset.

---

## D-10 — Scope Colcon discovery and own capture process groups

**Date:** 2026-10-15 · **Status:** Adopted

The immutable AY-10 evidence contains nested snapshots of both ROS packages.
Colcon's repository-wide package discovery therefore reports duplicate
package names. Build and test with `--base-paths src` so the tracked source
packages are the only candidates. The first AY-06–08 probe also left child
nodes after the launch parent stopped. The capture script now starts launch
and rosbag in process groups, signals the groups, and checks the ROS domain
for residual nodes before declaring a clean shutdown. These repairs do not
change the controller or visual reachability logic.
