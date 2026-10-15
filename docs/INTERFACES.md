# CAM-BOT runtime interfaces

These interfaces support a bounded simulation/prototype workflow. They do not
define force control, a production gripper, or a physical CNC interface.

## Carrier action

| Property | Contract |
|---|---|
| Action type | `control_msgs/action/FollowJointTrajectory` |
| Default name | `/joint_trajectory_controller/follow_joint_trajectory` |
| Commanded joints | six UR5 joints in `machine_tending.json` order |
| Success gate | accepted goal + successful result + actual-position action feedback |
| Time bounds | server 10 s; response 5 s; result = requested duration + 5 s; cancellation 2 s |
| Retry policy | zero automatic retries |

Controller mode is rejected before connecting when any named target is missing
or is not marked `controller_validated`. It also requires a complete UR5
`/joint_states` sample in addition to the action server before proceeding.
Current S1–S4 mappings are legacy P1–P4
assumptions, and S5 has no taught target, so controller mode is intentionally
blocked until targets are taught against the displayed cell geometry.

## State topics

All state payloads are compact JSON strings in `std_msgs/msg/String`.

| Topic | Publisher | Meaning |
|---|---|---|
| `/cambot/coordinator_state` | coordinator | `READY`, `RUNNING`, `SUCCESS`, or `FAILURE`, with mode/trial and failure cause |
| `/cambot/task_state` | coordinator | timestamped FSM `STARTED`/`ENTERED`/`STEP_STARTED`/`STEP_COMPLETED`/`COMPLETED`/terminal events, with trial ID; `CARRIER_NOT_COMMANDED` in visual mode |
| `/cambot/workpiece_state` | coordinator | logical workpiece state and visual world position |
| `/joint_states` | controller/broadcaster plus coordinator | carrier feedback plus partial placeholder/workpiece joint updates |

The coordinator publishes UR5 joint values only in `visual_simulation` mode.
Those values animate RViz and are not commands, controller results, or Gazebo
actuation. In `controller` mode it publishes only the four placeholder arm and
three visual workpiece joints, leaving UR5 joint feedback to the controller.
The controller bring-up file must include one authoritative broadcaster for
those six UR5 joints; the coordinator's second publisher owns disjoint joint
names. The launch never starts `dual_arm_cycle` alongside a UR5 controller.

## Machine-tending FSM commands

The one-shot application sequence is `HOME → PICK_RAW → STAGE → LOAD_MACHINE →
MACHINE_DWELL → UNLOAD_MACHINE → PLACE_FINISHED → HOME`. The second `HOME` is
the return phase, not a new physical station. Each state has an explicit
timeout in `machine_tending.json` and zero automatic retries. Logical
workpiece state advances only after its underlying step returns success.
Carrier steps require action acceptance, result success, and actual-position
feedback; visual placeholder movement is never treated as actuator feedback.

`auto_start:=true` (default) runs one trial from the launch command and exits.
For an interactive FSM session, launch with `auto_start:=false` and use
`std_srvs/srv/Trigger` services
`/machine_tending_coordinator/start`, `/machine_tending_coordinator/reset`,
and `/machine_tending_coordinator/cancel`. Start is accepted only in `IDLE`;
reset is required after `SUCCESS` or `FAILURE`. Reset while running is
rejected—cancel first. Cancellation stops logical progress and requests a
bounded controller goal cancellation if one is active; an unconfirmed action
cancel is reported as such, never as successful execution.

`fault_injection_step` is a visual-simulation-only test parameter. It fails
the named step before motion, and is rejected in controller mode. It is not a
production fault-recovery or retry mechanism.

## Visual workcell and targets

`carrier_control/config/machine_tending.json` is the runtime source for five
station IDs, unique TF frames, metres/radians poses, box dimensions and named
station-local interaction targets. Both launch files expand the workcell Xacro
from this installed config with a bounded 30-second Xacro call. Direct manual
Xacro expansion uses checked fallback geometry in the wrapper; launch does not
use those fallback coordinates. The `world` frame is parent of the station
frames and UR5 base. The coordinator transforms target offsets into world
coordinates and includes the resulting *visual* XYZ in task-state messages.
The coordinator now applies a bounded geometric-proxy reachability test to
the current `world -> dual_arm_base_link` TF. This is **not** IK, collision,
grasp, or material-removal validation.

The workpiece topic adds `process_phase` (`RAW`, `STAGED`, `IN_MACHINE`,
`PROCESSED`, `FINISHED`) and `simulated_attachment`. A `true` attachment is a
declared visual/logical state, not a gripper result. The moving workpiece is a
single three-prismatic-joint visual object; it is not Gazebo physics.

## Parameters

| Parameter | Default | Constraint |
|---|---:|---|
| `mode` | `visual_simulation` | `visual_simulation` or `controller` |
| `config_file` | installed `machine_tending.json` | valid schema and continuous state sequence |
| `results_file` | `~/.ros/cambot/machine_tending_trials.csv` | append-only CSV |
| `experiment_id` | `cambot-machine-tending` | nonempty experiment grouping identifier |
| `trial_count` | 1 | 1–25 |
| `visual_time_scale` | 1.0 | 0.01–10.0 |
| `enable_coordination` | false in visual demo; true in controller launch | Boolean; false preserves scripted visual replay |

## AY-09 experiment records

`results_file` names the append-only CSV summary. A sibling file with suffix
`.events.jsonl` receives events directly from FSM and coordinator callbacks;
the logger does not scrape console output. Schema 2.0 records experiment/trial
IDs, source commit, config path and canonical JSON SHA-256, UTC start/end,
steady-clock duration, terminal/failure context, coordinator reposition count,
mode, workpiece state, and verification flags. Events record sequence,
monotonic elapsed time, state, target, reachability, decision, action/result,
and structured details.

Every row/line is flushed and `fsync`ed. A `START/INCOMPLETE_PENDING` event is
written before the FSM starts. Exceptions and interrupts attempt a final
`INCOMPLETE` summary, and duplicate trial/final IDs are rejected. Cycle time is
`time.monotonic()` elapsed duration; UTC is only for cross-stream correlation.
ROS simulation time is not used by this logger and would need a separately
named field if introduced later.

## AY-06/07 coordination contract

`workspace` in installed `machine_tending.json` defines two arm-specific,
inclusive axis-aligned boxes and conservative radius checks (metres) in
`dual_arm_base_link`. Each target is resolved from the canonical workcell
config into `world`, then transformed using live TF. `required_arms: both`
requires both arm proxies to pass; an unknown/missing/invalid TF is `UNKNOWN`,
not reachable. The arm geometry and station poses are simulation assumptions.

The pure policy takes target XYZ, workpiece state, current base transform,
reachability result, step ID, and a candidate station. It returns
`LOCAL_MANIPULATION`, `CARRIER_REPOSITION`, `UNREACHABLE`, or `ERROR` with a
reason and attempt count. It issues at most one reposition request per trial
step. After carrier action feedback and a changed TF (or visual-only joint
animation and changed TF), it reevaluates reachability before any local step.
`/cambot/coordination_decision` emits timestamped JSON with trial/step,
target/world/local poses, arm results, decision, reason, attempts, and outcome.
No target or TF assumption is treated as a measured fact.

The local arm adapter is a visual placeholder. Controller mode fails with
`BM_ACTUATION_UNAVAILABLE` before any non-HOME step, rather than advancing a
workpiece on an unverified BM actuation. Full controller-backed AY-08 requires
an authoritative BM action/feedback interface as well as validated carrier
station targets and actual ROS TF/controller evidence.

The existing `dual_arm_demo.launch.py` defaults to
`enable_coordination:=false` to preserve its scripted visual-only entry point.
Set `enable_coordination:=true` for the TF/reachability-gated visual prototype;
the controller launch always enables it. Scripted replay is not adaptive
coordination evidence.

## Inputs still required for controller validation

- actual five station poses relative to the UR5 base;
- a taught and collision-checked six-joint target for every station, including S5;
- the selected controller name and confirmation that its action feedback contains actual positions;
- the selected bimanual/gripper controller interface if end-to-end verification is desired; and
- Tanmay's final flange/module dimensions if the reconstruction values are to be replaced.

