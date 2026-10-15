# CAMBOT — Roadmap

The six phases from carrier baseline to carrier placement recommendation.
Current progress lives in [`STATUS.md`](STATUS.md), not here.

**Planning provenance:** The phase headings and check marks below reflect the
original roadmap, not current evidence levels. In particular, the Phase 1/4
Gazebo and controller milestones are historical reports without retained
controller proof in this checkout. The status matrix classifies present code,
visual runtime, measured visual cycles and unverified actuation.

**Scope boundary:** this roadmap stops at the CA → CF → BM placeholder stage.
Detailed bimanual arm design comes afterwards.

---

## Phase 1 — UR5 Carrier Baseline ✅

Establish a functional simulated Carrier Arm.

- UR5 in Gazebo with MoveIt 2, RViz, `ros2_control`
- Joint trajectory execution to commanded configurations
- Machine-shop waypoints HOME, P1–P4 in `waypoints.yaml`
- Automated cycle `HOME → P1 → HOME → P2 → HOME → P3 → HOME → P4 → HOME`

**Output:** functional machine-shop carrier baseline.

---

## Phase 2 — Mass Sensitivity ✅

Characterize how link mass perturbation affects recorded trajectory statistics.

- EXP01 upper arm +10%, EXP02 forearm +10%, EXP03 shoulder +10%
- Position range, max velocity, max acceleration per joint

**Output:** three-case mass sensitivity dataset with stated limitations.

---

## Phase 3 — Carrier Workspace Characterization ⏸

Sample valid joint configurations, push them through forward kinematics, and
build a reachable workspace.

```text
q1..q6  →  Forward Kinematics  →  (x, y, z)
```

Requirements: respect joint limits; reject self-collision configurations where
practical; produce a 3D reachable point cloud; overlay P1–P4.

Deliverable table:

| Station | Reachable? | Margin to boundary | Notes |
|---|---|---|---|
| P1 | ✓/✗ | | |
| P2 | ✓/✗ | | |
| P3 | ✓/✗ | | |
| P4 | ✓/✗ | | |

**Output:** quantitative station-coverage analysis.

---

## Phase 4 — Carrier Flange / Interface 🔧

A simple **parameterized** flange attached to the UR5 wrist, plus a dedicated
`carrier_flange` TF frame.

Parameters: `flange_length`, `flange_width`, `flange_thickness`,
`mount_spacing`, `mount_height`, `tilt_angle`.

Target TF architecture:

```text
world → Carrier Arm (CA) → carrier_flange (CF) → Bimanual Module (BM)
```

The goal is a clean interface contract, not final mechanical complexity.

**Output:** `carrier_flange.xacro`, correct transform, documented TF architecture.

---

## Phase 5 — Baseline Logging & Metrics ⏸

Make every claim about the carrier measurable. Instrument the cycle to record:

```text
trial, from, to, planning_time, execution_time, result
1, HOME, P1, 0.82, 3.41, SUCCESS
1, P1, HOME, 0.74, 3.25, SUCCESS
```

Run **10–20 complete cycles**, then compute:

- mean, standard deviation, min, max cycle time
- success rate
- station-wise motion time
- planning vs execution failure counts

```text
Success Rate = (N_successful / N_trials) × 100
T_cycle      = T_motion + T_dwell
Joint Motion = Σ |q_i,final − q_i,initial|
```

**Output:** `results/baseline_trials.csv` and a quantitative baseline description.

> This phase was originally planned as Phase 2 and got deferred. It is the
> difference between "the carrier works" as an anecdote and as a measurement.

---

## Phase 6 — Carrier Placement Analysis ⏸

> Where should the Carrier Arm position itself so the future Bimanual Module can
> service the machine-shop stations effectively?

Evaluate candidate positions on station reachability, distance to stations,
orientation feasibility, workspace overlap, and carrier travel distance.

| Carrier position | P1 | P2 | P3 | P4 | Total movement |
|---|---|---|---|---|---|
| A | ✓ | ✓ | ✓ | ✓ | |
| B | ✓ | ✓ | ✓ | ✓ | |
| C | ✓ | ✓ | ✓ | ✓ | |
| D | ✓ | ✓ | ✓ | ✓ | |

**Output:** preliminary carrier-placement recommendation.

---

## Then: mechanical & system design

Only after the above does the actual bimanual mechanism get designed.

## The progression in one line

> Functional carrier → measurable carrier → spatially characterized carrier →
> defined interface → future manipulation system.
