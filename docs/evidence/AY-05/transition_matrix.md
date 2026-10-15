# AY-05 FSM contract (offline-verified; ROS runtime pending)

The FSM runs one cycle per start. Each state requires the listed workpiece
precondition and successful completion of every named step before transition.
Step success is supplied by the selected adapter. In controller mode, a carrier
step requires an accepted trajectory goal, successful action result, and actual
position feedback; placeholder arm/workpiece movement remains visual only.
Automatic retries are disabled (`retry_count: 0`). Any action rejection,
missing feedback, timeout, cancellation, invalid precondition, or adapter
exception terminates in `FAILURE` without committing the failed step's
workpiece transition. Only `MACHINE_DWELL` uses an explicit timer.

```text
START -> HOME -> PICK_RAW -> STAGE -> LOAD_MACHINE -> MACHINE_DWELL
          -> UNLOAD_MACHINE -> PLACE_FINISHED -> HOME -> SUCCESS
             \------ any failed precondition/action/timeout/cancel ------> FAILURE
RESET: SUCCESS or FAILURE -> IDLE (workpiece RAW_AT_S1)
```

| State | Precondition | Action / completion event | Timeout (s) | Next on success |
|---|---|---|---:|---|
| HOME (initial) | `RAW_AT_S1` | `HOME_START`; step completed | 30 | PICK_RAW |
| PICK_RAW | `RAW_AT_S1` | `S1_APPROACH`, `S1_GRASP`; both completed | 30 | STAGE |
| STAGE | `HELD_RAW_AT_S1` | `S2_STAGE`; step completed | 20 | LOAD_MACHINE |
| LOAD_MACHINE | `HELD_RAW_AT_S2` | `S3_LOAD`, `S3_RELEASE`; both completed | 30 | MACHINE_DWELL |
| MACHINE_DWELL | `RAW_IN_MACHINE` | parameterized dwell timer elapsed; step completed | 10 | UNLOAD_MACHINE |
| UNLOAD_MACHINE | `PROCESSED_IN_MACHINE` | `S3_REGRASP`, `S4_UNLOAD`; both completed | 30 | PLACE_FINISHED |
| PLACE_FINISHED | `HELD_PROCESSED_AT_S4` | `S5_PLACE`, `S5_RELEASE`; both completed | 30 | HOME |
| HOME (final) | `FINISHED_AT_S5` | `HOME_END`; step completed | 30 | SUCCESS |

Timeouts are configurable in
`src/carrier_control/config/machine_tending.json`. The FSM emits timestamped,
trial-ID-tagged `STARTED`, `ENTERED`, `STEP_STARTED`, `STEP_COMPLETED`,
`COMPLETED`, and terminal `SUCCESS`/`FAILURE` events on
`/cambot/task_state`. `~/start`, `~/reset`, and `~/cancel` are Trigger services;
`~/start` queues one cycle when `auto_start:=false`. The visual-only test hook
`fault_injection_step` is rejected in controller mode.

Visual arm poses, simulated workpiece attachment, and assumed station positions
are not validated grasp, CNC processing, or carrier actuation.
