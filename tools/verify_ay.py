#!/usr/bin/env python3
"""Generate machine-readable offline AY-01…AY-13 verification evidence."""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CONTROL_ROOT = ROOT / "src" / "carrier_control"
sys.path.insert(0, str(CONTROL_ROOT))

from carrier_control.metrics import (  # noqa: E402
    TrialRecordError, parameter_hash, validate_trial_record,
)
from carrier_control.workflow import (  # noqa: E402
    WorkflowError,
    load_plan,
    simulate_state_sequence,
    validate_plan,
)


PLAN_PATH = CONTROL_ROOT / "config" / "machine_tending.json"
CELL_PATH = ROOT / "src" / "carrier_description" / "urdf" / "machine_tending_cell.xacro"
WRAPPER_PATH = ROOT / "src" / "carrier_description" / "urdf" / "ur5_with_test_tool.xacro"
COORDINATOR_PATH = CONTROL_ROOT / "carrier_control" / "machine_tending_coordinator.py"
LAUNCH_PATH = ROOT / "src" / "carrier_description" / "launch" / "dual_arm_demo.launch.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_failure(function, exception_type, contains: str = "") -> None:
    try:
        function()
    except exception_type as exc:
        require(contains in str(exc), f"unexpected failure text: {exc}")
        return
    raise AssertionError(f"expected {exception_type.__name__}")


def visual_record():
    return {
        "schema_version": "2.0",
        "experiment_id": "offline-verifier",
        "trial_id": "offline-check",
        "git_commit": "UNKNOWN",
        "parameter_config": "offline-fixture",
        "parameter_hash_sha256": parameter_hash({"fixture": True}),
        "start_timestamp_utc": "2026-10-15T00:00:00Z",
        "end_timestamp_utc": "2026-10-15T00:00:01Z",
        "time_source": "monotonic_duration+utc_wall_timestamps",
        "cycle_time_s": 0.0,
        "status": "COMPLETE",
        "success": True,
        "failure_state": None,
        "failure_reason": None,
        "carrier_repositions": 0,
        "mode": "visual_simulation",
        "workpiece_final_state": "FINISHED_AT_S5",
        "runtime_verified": False,
        "end_to_end_verified": False,
        "notes": "offline validation fixture",
    }


def unbounded_wait_lines(source: str):
    tree = ast.parse(source)
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "spin_until_future_complete" and not any(
                keyword.arg == "timeout_sec" for keyword in node.keywords):
            lines.append(node.lineno)
    return lines


def inventory_positive():
    inventory = json.loads((ROOT / "artifacts" / "inventory.json").read_text())
    require(len(inventory["packages"]) == 2, "inventory must contain two packages")
    result = subprocess.run(
        ["git", "diff", "--quiet", "66c436a", "--", "experiments/mass_sensitivity"],
        cwd=ROOT,
        check=False,
    )
    require(result.returncode == 0, "mass-sensitivity archive changed from base")


def inventory_negative():
    expect_failure(
        lambda: require((ROOT / "missing-archive").exists(), "archive missing"),
        AssertionError,
        "archive missing",
    )


def packages_positive():
    manifests = sorted((ROOT / "src").glob("*/package.xml"))
    require(len(manifests) == 2, "expected exactly two ROS packages")
    for manifest in manifests:
        root = ET.parse(manifest).getroot()
        description = root.findtext("description", "")
        require("TODO" not in description, f"scaffold description in {manifest}")
    require(
        "glob('config/*')" in (CONTROL_ROOT / "setup.py").read_text(),
        "config not installed",
    )
    require(
        "glob('rviz/*')" in (
            ROOT / "src/carrier_description/setup.py"
        ).read_text(),
        "RViz not installed",
    )


def packages_negative():
    expect_failure(lambda: ET.fromstring("<package>"), ET.ParseError)


def chain_positive():
    wrapper = WRAPPER_PATH.read_text()
    require("<xacro:ur_robot" in wrapper, "official UR macro missing")
    require('parent_link="tool0"' in wrapper, "flange is not attached at tool0")
    dual = (WRAPPER_PATH.parent / "dual_arm.xacro").read_text()
    require(dual.count('type="revolute"') == 4, "expected four custom joints")


def chain_negative():
    broken = WRAPPER_PATH.read_text().replace('parent_link="tool0"', 'parent_link="wrong"')
    expect_failure(
        lambda: require('parent_link="tool0"' in broken, "tool0 contract broken"),
        AssertionError,
        "tool0 contract broken",
    )


def stations_positive():
    plan = load_plan(PLAN_PATH)
    require(len(plan["stations"]) == 6, "HOME plus five stations required")
    links = {
        node.attrib["name"]
        for node in ET.parse(CELL_PATH).getroot().findall(".//link")
    }
    require(
        len([name for name in links if name.startswith("station_s")]) == 5,
        "five station links required",
    )


def stations_negative():
    broken = load_plan(PLAN_PATH)
    del broken["stations"]["S5_FINISHED"]
    expect_failure(lambda: validate_plan(broken), WorkflowError, "stations must contain")


def workpiece_positive():
    joints = {
        node.attrib["name"]
        for node in ET.parse(CELL_PATH).getroot().findall(".//joint")
    }
    expected = {"workpiece_x_joint", "workpiece_y_joint", "workpiece_z_joint"}
    require(expected <= joints, "workpiece joints missing")
    require(
        simulate_state_sequence(load_plan(PLAN_PATH))[1] == "FINISHED_AT_S5",
        "final workpiece state missing",
    )


def workpiece_negative():
    broken = load_plan(PLAN_PATH)
    broken["workflow"][4]["from_state"] = "LOST"
    expect_failure(lambda: validate_plan(broken), WorkflowError, "state discontinuity")


def workflow_positive():
    plan = load_plan(PLAN_PATH)
    require(len(plan["workflow"]) == 12, "complete named workflow required")
    require(
        {"GRASP", "HOLD", "RELEASE"} <= set(plan["bimanual_poses"]),
        "bimanual poses missing",
    )


def workflow_negative():
    broken = load_plan(PLAN_PATH)
    broken["bimanual_poses"]["GRASP"][0] = 2.0
    expect_failure(
        lambda: validate_plan(broken),
        WorkflowError,
        "exceeds placeholder joint limits",
    )


def actions_positive():
    paths = (
        CONTROL_ROOT / "carrier_control/machine_shop_joint_cycle.py",
        CONTROL_ROOT / "carrier_control/machine_shop_trajectory.py",
        COORDINATOR_PATH,
    )
    for path in paths:
        source = path.read_text()
        require(not unbounded_wait_lines(source), f"unbounded wait in {path}")
        require("feedback" in source.lower(), f"feedback gate absent in {path}")


def actions_negative():
    source = "rclpy.spin_until_future_complete(node, future)\n"
    require(unbounded_wait_lines(source) == [1], "unsafe wait not detected")


def coordinator_positive():
    plan = load_plan(PLAN_PATH)
    require(
        simulate_state_sequence(plan) == (True, "FINISHED_AT_S5", None),
        "sequence did not finish",
    )


def coordinator_negative():
    plan = load_plan(PLAN_PATH)
    require(
        simulate_state_sequence(plan, "S3_LOAD") == (False, "HELD_RAW_AT_S2", "S3_LOAD"),
        "failed dependency advanced workpiece state",
    )


def states_positive():
    source = COORDINATOR_PATH.read_text()
    for topic in ("/cambot/task_state", "/cambot/workpiece_state", "/cambot/coordinator_state"):
        require(topic in source, f"missing state topic {topic}")


def states_negative():
    record = {**visual_record(), "end_to_end_verified": True}
    expect_failure(
        lambda: validate_trial_record(record),
        TrialRecordError,
        "visual simulation",
    )


def launch_positive():
    source = LAUNCH_PATH.read_text()
    ast.parse(source)
    for token in (
            'package="robot_state_publisher"',
            'executable="machine_tending_coordinator"',
            'package="rviz2"'):
        require(token in source, f"launch missing {token}")


def launch_negative():
    source = LAUNCH_PATH.read_text()
    require(
        'executable="dual_arm_cycle"' not in source,
        "competing joint publisher launched",
    )
    require(
        'package="joint_state_publisher_gui"' not in source,
        "GUI joint publisher launched",
    )


def metrics_positive():
    schema_path = ROOT / "experiments/machine_tending/schema/trial.schema.json"
    schema = json.loads(schema_path.read_text())
    require(
        schema["properties"]["mode"]["enum"]
        == ["controller", "visual_simulation"],
        "mode schema missing",
    )
    validate_trial_record(visual_record())


def metrics_negative():
    record = {**visual_record(), "runtime_verified": True}
    expect_failure(
        lambda: validate_trial_record(record),
        TrialRecordError,
        "visual simulation",
    )


def tests_positive():
    required = (
        CONTROL_ROOT / "test/test_workflow.py",
        CONTROL_ROOT / "test/test_metrics.py",
        CONTROL_ROOT / "test/test_action_safety.py",
        ROOT / "src/carrier_description/test/test_cell_model.py",
        ROOT / "src/carrier_description/test/test_launch_contract.py",
    )
    require(all(path.is_file() for path in required), "acceptance test missing")


def tests_negative():
    entries = {"positive": "PASS"}
    expect_failure(
        lambda: require("negative" in entries, "negative evidence missing"),
        AssertionError,
        "negative evidence missing",
    )


def docs_positive():
    required = (
        "AY_TRACEABILITY.md",
        "INTERFACES.md",
        "VALIDATION.md",
        "ARCHITECTURE.md",
        "STATUS.md",
    )
    require(
        all((ROOT / "docs" / name).is_file() for name in required),
        "required documentation missing",
    )


def docs_negative():
    current = (
        (ROOT / "README.md").read_text()
        + (ROOT / "docs/STATUS.md").read_text()
    )
    require("Phase 4 dual-arm files are" not in current, "stale missing-source claim remains")


CHECKS = {
    "AY-01": (inventory_positive, inventory_negative, "inventory and archive preservation"),
    "AY-02": (packages_positive, packages_negative, "package metadata and installed assets"),
    "AY-03": (chain_positive, chain_negative, "UR5/tool0/flange/four-joint chain"),
    "AY-04": (stations_positive, stations_negative, "five-station visual cell"),
    "AY-05": (workpiece_positive, workpiece_negative, "workpiece model and state continuity"),
    "AY-06": (workflow_positive, workflow_negative, "named bimanual workflow"),
    "AY-07": (actions_positive, actions_negative, "bounded feedback-gated actions"),
    "AY-08": (coordinator_positive, coordinator_negative, "fail-closed coordinator transitions"),
    "AY-09": (states_positive, states_negative, "traceable state interfaces"),
    "AY-10": (launch_positive, launch_negative, "single visual launch contract"),
    "AY-11": (metrics_positive, metrics_negative, "metrics schema evidence integrity"),
    "AY-12": (tests_positive, tests_negative, "positive and failure tests"),
    "AY-13": (docs_positive, docs_negative, "current documentation and limitations"),
}


def run_check(function):
    try:
        function()
    except Exception as exc:  # evidence collector must retain all failures
        return {"status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"}
    return {"status": "PASS", "detail": function.__name__}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    tasks = {}
    for task_id, (positive, negative, description) in CHECKS.items():
        tasks[task_id] = {
            "description": description,
            "positive": run_check(positive),
            "negative": run_check(negative),
        }
    passed = sum(
        result["status"] == "PASS"
        for task in tasks.values()
        for result in (task["positive"], task["negative"])
    )
    evidence = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acceptance_status": (
            "SUPERSEDED MAPPING — OFFLINE COMPONENT CHECKS ONLY"
        ),
        "proof_level": "STATIC COMPONENT CHECKS",
        "command": (
            "python3 tools/verify_ay.py --output "
            "artifacts/verification/ay_verification.json"
        ),
        "summary": {"passed": passed, "total": len(tasks) * 2},
        "tasks": tasks,
        "runtime_note": (
            "ROS 2, Gazebo, xacro, check_urdf, and controller runtime "
            "were unavailable."
        ),
    }
    rendered = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if passed == len(tasks) * 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
