"""
Dependency-light, one-shot machine-tending application state machine.

The FSM owns logical state. Adapters own ROS actions and visual-only updates.
No step, workpiece transition, or subsequent state commits after failure.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import time
from typing import Callable, Mapping


STATE_STEPS = (
    ("HOME", ("HOME_START",)),
    ("PICK_RAW", ("S1_APPROACH", "S1_GRASP")),
    ("STAGE", ("S2_STAGE",)),
    ("LOAD_MACHINE", ("S3_LOAD", "S3_RELEASE")),
    ("MACHINE_DWELL", ("MACHINE_DWELL",)),
    ("UNLOAD_MACHINE", ("S3_REGRASP", "S4_UNLOAD")),
    ("PLACE_FINISHED", ("S5_PLACE", "S5_RELEASE")),
    ("HOME", ("HOME_END",)),
)
STATE_NAMES = ("HOME", "PICK_RAW", "STAGE", "LOAD_MACHINE",
               "MACHINE_DWELL", "UNLOAD_MACHINE", "PLACE_FINISHED")
MAX_RETRIES = 0


class FSMError(ValueError):
    """Invalid lifecycle operation or FSM configuration."""


@dataclass(frozen=True)
class StepOutcome:
    success: bool
    cause: str | None = None


@dataclass(frozen=True)
class CycleOutcome:
    success: bool
    terminal: str
    failure_state: str | None
    failure_step: str | None
    cause: str | None
    workpiece_state: str


class MachineTendingFSM:
    """One trial at a time; reset is required before a second start."""

    def __init__(self, plan: Mapping, notify: Callable | None = None,
                 clock: Callable = time.monotonic, timeout_scale: float = 1.0):
        fsm_config = plan.get("fsm")
        if not isinstance(fsm_config, dict):
            raise FSMError("fsm must be an object")
        if fsm_config.get("retry_count") != MAX_RETRIES:
            raise FSMError("fsm.retry_count must be 0; automatic retries are disabled")
        configured = fsm_config.get("state_timeout_s")
        if (not isinstance(configured, dict) or
                set(configured) != set(STATE_NAMES)):
            raise FSMError("fsm.state_timeout_s must cover the seven unique states")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
               not math.isfinite(value) or not 0 < value <= 600
               for value in configured.values()):
            raise FSMError("FSM state timeouts must be finite in (0, 600] seconds")
        if not isinstance(timeout_scale, (int, float)) or not 0 < timeout_scale <= 10:
            raise FSMError("timeout_scale must be in (0, 10]")
        workflow = plan.get("workflow", [])
        grouped = tuple(name for _, names in STATE_STEPS for name in names)
        if tuple(step.get("name") for step in workflow) != grouped:
            raise FSMError("workflow step order does not match the FSM state groups")
        self.steps = {step["name"]: step for step in workflow}
        self.timeouts = configured
        self.notify = notify or (lambda event: None)
        self.clock = clock
        self.timeout_scale = timeout_scale
        self.status = "IDLE"
        self.trial_id = None
        self.workpiece_state = "RAW_AT_S1"
        self.cancel_requested = False
        self.current_state = None

    def _emit(self, event, **extra):
        self.notify({
            "event": event,
            "state": self.current_state,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "trial_id": self.trial_id,
            "workpiece_state": self.workpiece_state,
            **extra,
        })

    def start(self, trial_id):
        if self.status != "IDLE":
            raise FSMError(f"cannot start from {self.status}; reset first")
        if not isinstance(trial_id, str) or not trial_id:
            raise FSMError("start requires a nonempty trial ID")
        self.trial_id = trial_id
        self.status = "RUNNING"
        self.current_state = None
        self.cancel_requested = False
        self.workpiece_state = "RAW_AT_S1"
        self._emit("STARTED")

    def reset(self):
        if self.status == "RUNNING":
            raise FSMError("cannot reset while running; cancel first")
        self.status = "IDLE"
        self.trial_id = None
        self.current_state = None
        self.cancel_requested = False
        self.workpiece_state = "RAW_AT_S1"
        self._emit("RESET")

    def cancel(self):
        if self.status != "RUNNING":
            raise FSMError("cancel requires a running cycle")
        self.cancel_requested = True

    def _fail(self, cause, step=None):
        self.status = "FAILURE"
        self._emit("FAILURE", cause=cause, failure_step=step)
        return CycleOutcome(False, "FAILURE", self.current_state, step,
                            cause, self.workpiece_state)

    def run(self, execute_step):
        """Run once; execute_step(step, deadline, is_cancelled) returns StepOutcome."""
        if self.status != "RUNNING":
            raise FSMError("run requires start")
        for state_index, (state_name, names) in enumerate(STATE_STEPS):
            self.current_state = state_name
            deadline = self.clock() + self.timeouts[state_name] * self.timeout_scale
            self._emit("ENTERED", phase_index=state_index)
            for name in names:
                step = self.steps[name]
                if self.cancel_requested:
                    return self._fail("CANCELLED", name)
                if self.workpiece_state != step["from_state"]:
                    return self._fail("PRECONDITION_FAILED", name)
                if self.clock() >= deadline:
                    return self._fail("STATE_TIMEOUT", name)
                self._emit("STEP_STARTED", step=name)
                try:
                    outcome = execute_step(step, deadline, lambda: self.cancel_requested)
                except Exception as exc:
                    return self._fail(f"ADAPTER_EXCEPTION:{type(exc).__name__}", name)
                if not isinstance(outcome, StepOutcome):
                    return self._fail("INVALID_ADAPTER_RESULT", name)
                if self.cancel_requested:
                    cause = outcome.cause if not outcome.success and outcome.cause else "CANCELLED"
                    return self._fail(cause, name)
                if self.clock() >= deadline:
                    return self._fail("STATE_TIMEOUT", name)
                if not outcome.success:
                    return self._fail(outcome.cause or "ACTION_FAILED", name)
                self.workpiece_state = step["to_state"]
                self._emit("STEP_COMPLETED", step=name)
            self._emit("COMPLETED", phase_index=state_index)
        if self.workpiece_state != "FINISHED_AT_S5":
            return self._fail("FINAL_WORKPIECE_STATE_INVALID")
        self.status = "SUCCESS"
        self._emit("SUCCESS")
        return CycleOutcome(True, "SUCCESS", None, None, None,
                            self.workpiece_state)
