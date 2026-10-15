"""Pure-Python machine-tending plan loading and validation."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable

from carrier_control.machine_tending_fsm import FSMError, MachineTendingFSM
from carrier_control.reachability import validate_workspace
from carrier_control.waypoints import UR5_JOINT_NAMES
from carrier_control.workcell_model import (
    STATION_IDS, WorkcellError, station_for_target, validate_workcell,
)


REQUIRED_STATIONS = (
    "HOME",
    "S1_RAW",
    "S2_STAGING",
    "S3_MACHINE",
    "S4_OUTPUT",
    "S5_FINISHED",
)
REQUIRED_STEPS = (
    "HOME_START",
    "S1_APPROACH",
    "S1_GRASP",
    "S2_STAGE",
    "S3_LOAD",
    "S3_RELEASE",
    "MACHINE_DWELL",
    "S3_REGRASP",
    "S4_UNLOAD",
    "S5_PLACE",
    "S5_RELEASE",
    "HOME_END",
)
PROCESS_PHASES = {
    "RAW_AT_S1": "RAW",
    "HELD_RAW_AT_S1": "RAW",
    "HELD_RAW_AT_S2": "STAGED",
    "HELD_RAW_AT_S3": "STAGED",
    "RAW_IN_MACHINE": "IN_MACHINE",
    "PROCESSED_IN_MACHINE": "PROCESSED",
    "HELD_PROCESSED_AT_S3": "PROCESSED",
    "HELD_PROCESSED_AT_S4": "PROCESSED",
    "HELD_PROCESSED_AT_S5": "PROCESSED",
    "FINISHED_AT_S5": "FINISHED",
}


class WorkflowError(ValueError):
    """Raised when a machine-tending plan violates its safety contract."""


def _numbers(values: Any, count: int, field: str) -> None:
    if not isinstance(values, list) or len(values) != count:
        raise WorkflowError(f"{field} must contain {count} values")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
           not math.isfinite(value)
           for value in values):
        raise WorkflowError(f"{field} must contain only finite numbers")


def load_plan(path: Path | str, require_controller_ready: bool = False) -> Dict[str, Any]:
    """Load and validate a plan without requiring ROS or PyYAML."""
    plan_path = Path(path)
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot load plan {plan_path}: {exc}") from exc
    validate_plan(plan, require_controller_ready=require_controller_ready)
    return plan


def validate_plan(plan: Any, require_controller_ready: bool = False) -> None:
    """Validate structure, state continuity, limits, and controller readiness."""
    if not isinstance(plan, dict) or plan.get("schema_version") != "1.0":
        raise WorkflowError("schema_version must be '1.0'")

    workcell = plan.get("workcell")
    try:
        validate_workcell(workcell)
    except WorkcellError as exc:
        raise WorkflowError(str(exc)) from exc
    workspace = plan.get("workspace")
    try:
        validate_workspace(workspace)
    except ValueError as exc:
        raise WorkflowError(str(exc)) from exc
    if workspace.get("status") != "geometric_proxy_assumption_not_ik_or_collision_checked":
        raise WorkflowError("workspace must retain its geometric-proxy warning")
    if workspace.get("required_arms") not in ("left", "right", "both"):
        raise WorkflowError("workspace.required_arms must be left, right or both")
    timeout = workspace.get("tf_timeout_s")
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or
            not math.isfinite(timeout) or not 0 < timeout <= 10):
        raise WorkflowError("workspace.tf_timeout_s must be in (0, 10]")

    carrier = plan.get("carrier")
    if not isinstance(carrier, dict):
        raise WorkflowError("carrier must be an object")
    joint_names = carrier.get("joint_names")
    if not isinstance(joint_names, list) or len(joint_names) != 6 or not all(
            isinstance(name, str) and name for name in joint_names):
        raise WorkflowError("carrier.joint_names must contain six names")
    if tuple(joint_names) != UR5_JOINT_NAMES:
        raise WorkflowError("carrier.joint_names must match the UR5 driver joint order")
    for field in (
        "server_timeout_s",
        "goal_response_timeout_s",
        "result_margin_s",
        "feedback_timeout_s",
    ):
        value = carrier.get(field)
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                not math.isfinite(value) or not 0 < value <= 120):
            raise WorkflowError(f"carrier.{field} must be in (0, 120]")

    stations = plan.get("stations")
    if not isinstance(stations, dict) or tuple(stations) != REQUIRED_STATIONS:
        raise WorkflowError("stations must contain HOME and S1_RAW through S5_FINISHED in order")
    for index, (name, station) in enumerate(stations.items()):
        if not isinstance(station, dict):
            raise WorkflowError(f"station {name} must be an object")
        expected_id = None if index == 0 else STATION_IDS[index - 1]
        if station.get("workcell_station_id") != expected_id:
            raise WorkflowError(f"station {name} must map to {expected_id}")
        _numbers(
            station.get("visual_carrier_joints"),
            6,
            f"stations.{name}.visual_carrier_joints",
        )
        joints = station.get("carrier_joints")
        if joints is not None:
            _numbers(joints, 6, f"stations.{name}.carrier_joints")
        if require_controller_ready and name != "HOME":
            if joints is None:
                raise WorkflowError(f"station {name} has no taught carrier target")
            if station.get("controller_validated") is not True:
                raise WorkflowError(f"station {name} target is not controller-validated")

    poses = plan.get("bimanual_poses")
    if not isinstance(poses, dict) or not poses:
        raise WorkflowError("bimanual_poses must be a non-empty object")
    for name, pose in poses.items():
        _numbers(pose, 4, f"bimanual_poses.{name}")
        if any(not -1.57 <= value <= 1.57 for value in pose):
            raise WorkflowError(f"bimanual pose {name} exceeds placeholder joint limits")

    workflow = plan.get("workflow")
    if not isinstance(workflow, list) or tuple(
            step.get("name")
            for step in workflow
            if isinstance(step, dict)
    ) != REQUIRED_STEPS:
        raise WorkflowError(
            "workflow names/order do not match the required machine-tending sequence"
        )
    previous_to = None
    for index, step in enumerate(workflow):
        if not isinstance(step, dict):
            raise WorkflowError(f"workflow[{index}] must be an object")
        station = step.get("station")
        if station is not None and station not in stations:
            raise WorkflowError(f"workflow[{index}] references unknown station {station}")
        target = step.get("target")
        if station not in (None, "HOME") and target is None:
            raise WorkflowError(f"workflow[{index}] requires an interaction target")
        if target is not None:
            try:
                target_station = station_for_target(workcell, target)
            except WorkcellError as exc:
                raise WorkflowError(f"workflow[{index}] {exc}") from exc
            if station is not None and stations[station]["workcell_station_id"] != target_station:
                raise WorkflowError(f"workflow[{index}] target {target} is at a different station")
        if step.get("bimanual_pose") not in poses:
            raise WorkflowError(f"workflow[{index}] references unknown bimanual pose")
        duration = step.get("duration_s")
        if (
                isinstance(duration, bool)
                or not isinstance(duration, (int, float))
                or not math.isfinite(duration)
                or not 0 < duration <= 120):
            raise WorkflowError(f"workflow[{index}].duration_s must be in (0, 120]")
        from_state = step.get("from_state")
        to_state = step.get("to_state")
        if not isinstance(from_state, str) or not isinstance(to_state, str):
            raise WorkflowError(f"workflow[{index}] requires string workpiece states")
        if previous_to is not None and from_state != previous_to:
            raise WorkflowError(
                f"workflow[{index}] state discontinuity: expected {previous_to}, got {from_state}"
            )
        if from_state not in PROCESS_PHASES or to_state not in PROCESS_PHASES:
            raise WorkflowError(f"workflow[{index}] has an unknown workpiece process state")
        previous_to = to_state
    try:
        MachineTendingFSM(plan)
    except FSMError as exc:
        raise WorkflowError(str(exc)) from exc


def stations_used_by(workflow: Iterable[Dict[str, Any]]) -> tuple[str, ...]:
    """Return carrier station names in execution order."""
    return tuple(step["station"] for step in workflow if step.get("station") is not None)


def simulate_state_sequence(
        plan: Dict[str, Any], failed_step: str | None = None
) -> tuple[bool, str, str | None]:
    """Exercise state gating offline; a failed dependency never advances state."""
    validate_plan(plan)
    state = plan["workflow"][0]["from_state"]
    for step in plan["workflow"]:
        if step["from_state"] != state:
            raise WorkflowError(
                f"step {step['name']} expected {step['from_state']}, got {state}"
            )
        if step["name"] == failed_step:
            return False, state, step["name"]
        state = step["to_state"]
    return state == "FINISHED_AT_S5", state, None
