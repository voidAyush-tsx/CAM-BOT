# AY-09 schema evidence

Authoritative machine-readable schemas:

- `experiments/machine_tending/schema/trial.schema.json`
- `experiments/machine_tending/schema/event.schema.json`
- `experiments/machine_tending/templates/trials.csv`

Summary schema 2.0 contains `experiment_id`, UUID-bearing `trial_id`, resolved
`git_commit` (or explicit `UNKNOWN` outside a Git checkout), parameter config
path and SHA-256, UTC start/end, time-source declaration, monotonic duration,
terminal status/success/failure context, coordinator reposition count, mode,
final workpiece state, verification flags, and notes.

Event schema 2.0 contains UTC and monotonic elapsed time plus FSM state,
target, reachability, decision, action/result, and structured details. Sequence
starts at zero per trial. The logger writes events from `_fsm_event` and
`_emit_decision`; it does not parse stdout.

`START` is durably written with `INCOMPLETE_PENDING` before the FSM starts.
Normal success/failure writes `FINALIZE` followed by one CSV summary. Caught
interruptions are finalized as `INCOMPLETE`; an abrupt kill still leaves the
pending start detectable with `incomplete_trial_ids()`.

No genuine runtime sample is present because this host has `ROS_DISTRO=unset`.
`tools/capture_ay09_humble.sh` creates the visual-runtime sample and validates
it when run in the required Humble environment. Do not relabel offline test
fixtures as measured data.
