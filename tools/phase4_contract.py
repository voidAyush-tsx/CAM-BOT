#!/usr/bin/env python3
"""Check the retained Phase-4 source contract and an optional expanded URDF."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = ROOT / "src/carrier_description"
CONTROL = ROOT / "src/carrier_control"
XACRO = "{http://www.ros.org/wiki/xacro}"
CUSTOM = (
    "left_shoulder_joint",
    "left_elbow_joint",
    "right_shoulder_joint",
    "right_elbow_joint",
)
CARRIER = (
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
)
CHAIN = (
    ("tool0", "carrier_flange"),
    ("carrier_flange", "carrier_flange_interface"),
    ("carrier_flange_interface", "dual_arm_base_link"),
)


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(detail)


def local_model_contract(
    flange: ET.Element, dual: ET.Element, wrapper: ET.Element
) -> dict:
    """Check local macros and invocation without pretending to expand ur_description."""
    roots = (flange, dual, wrapper)
    links = [node.get("name") for root in roots for node in root.iter("link")]
    joints = [node.get("name") for root in roots for node in root.iter("joint")]
    require(len(links) == len(set(links)), "duplicate local link name")
    require(len(joints) == len(set(joints)), "duplicate local joint name")
    require(set(CUSTOM) <= set(joints), "missing custom joint")
    require(sum(1 for node in wrapper.iter(f"{XACRO}ur_robot")) == 1,
            "upstream UR5 macro must be invoked once")
    require(
        any(node.get("parent_link") == "tool0"
            for node in wrapper.iter(f"{XACRO}carrier_flange")),
        "flange invocation must attach to tool0",
    )
    require(
        any(node.get("parent_link") == "carrier_flange_interface"
            for node in wrapper.iter(f"{XACRO}dual_arm")),
        "dual-arm invocation must attach to carrier_flange_interface",
    )
    local_joints = {
        node.get("name"): node
        for root in (flange, dual)
        for node in root.iter("joint")
    }
    for parent, child in CHAIN:
        matching = [
            joint for joint in local_joints.values()
            if joint.find("parent") is not None
            and joint.find("child") is not None
            and joint.find("parent").get("link") in (parent, "${parent_link}")
            and joint.find("child").get("link") == child
        ]
        require(len(matching) == 1 and matching[0].get("type") == "fixed",
                f"missing fixed chain edge {parent} -> {child}")
    limits = {}
    for name in CUSTOM:
        joint = local_joints[name]
        require(joint.get("type") == "revolute", f"{name} must be revolute")
        limit = joint.find("limit")
        require(limit is not None, f"{name} has no limit")
        lower, upper = float(limit.get("lower")), float(limit.get("upper"))
        require(lower < upper, f"invalid limit for {name}")
        limits[name] = (lower, upper)
    return {"links": len(links), "joints": len(joints), "limits": limits}


def cycle_contract(source: str, limits: dict) -> dict:
    """Check joint sample order and every generic stage against URDF limits."""
    tree = ast.parse(source)
    node_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DualArmCycle"
    )
    assignments = {
        target.id: statement.value
        for statement in node_class.body
        if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name)
    }
    assignments.update({
        statement.target.id: statement.value
        for statement in node_class.body
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
    })
    names = tuple(ast.literal_eval(assignments["JOINTS"]))
    require(names == CARRIER + CUSTOM, "JointState joint order changed")
    stages = assignments["STAGES"]
    require(isinstance(stages, ast.List), "stages must be a list")
    stage_names = []
    keys = ("ls", "le", "rs", "re")
    for stage in stages.elts:
        require(isinstance(stage, ast.Tuple) and len(stage.elts) == 3,
                "stage must contain name, target and duration")
        name = ast.literal_eval(stage.elts[0])
        target = stage.elts[1]
        duration = float(ast.literal_eval(stage.elts[2]))
        require(duration > 0, f"invalid duration in {name}")
        require(isinstance(target, ast.Call)
                and isinstance(target.func, ast.Name)
                and target.func.id == "dict", f"invalid target in {name}")
        values = {item.arg: ast.literal_eval(item.value) for item in target.keywords}
        require(tuple(values) == keys, f"wrong custom joint order in {name}")
        for key, joint in zip(keys, CUSTOM):
            lower, upper = limits[joint]
            require(lower <= values[key] <= upper,
                    f"{name}.{joint} exceeds [{lower}, {upper}]")
        stage_names.append(name)
    require(stage_names[0] == stage_names[-1] == "HOME",
            "cycle must start and end at HOME")
    require("self.pub.publish(msg)" in source,
            "JointState publication missing")
    require("msg.position = [0.0] * 6" in source,
            "visual UR5 sample behavior changed")
    return {"joint_order": names, "stages": stage_names,
            "carrier_samples": "six constant zero positions; visual only"}


def expanded_urdf_contract(path: Path) -> dict:
    """Validate generated URDF names and the complete tool0-to-arm chain."""
    robot = ET.parse(path).getroot()
    require(robot.tag == "robot", "expanded document is not a URDF robot")
    links = [node.get("name") for node in robot.findall("link")]
    joints = [node.get("name") for node in robot.findall("joint")]
    require(len(links) == len(set(links)), "duplicate expanded link name")
    require(len(joints) == len(set(joints)), "duplicate expanded joint name")
    require("tool0" in links, "upstream tool0 missing")
    require(set(CUSTOM) <= set(joints), "custom joint missing from expanded URDF")
    edges = {}
    for joint in robot.findall("joint"):
        parent, child = joint.find("parent"), joint.find("child")
        require(parent is not None and child is not None,
                f"joint {joint.get('name')} lacks parent/child")
        edges[(parent.get("link"), child.get("link"))] = joint.get("name")
    require(all(edge in edges for edge in CHAIN), "expanded frame chain incomplete")
    return {"links": len(links), "joints": len(joints),
            "chain": [edges[edge] for edge in CHAIN]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--urdf", type=Path,
                        help="expanded URDF generated by xacro in Humble")
    args = parser.parse_args()
    flange = ET.parse(DESCRIPTION / "urdf/carrier_flange.xacro").getroot()
    dual = ET.parse(DESCRIPTION / "urdf/dual_arm.xacro").getroot()
    wrapper = ET.parse(DESCRIPTION / "urdf/ur5_with_test_tool.xacro").getroot()
    local = local_model_contract(flange, dual, wrapper)
    cycle = cycle_contract(
        (CONTROL / "carrier_control/dual_arm_cycle.py").read_text(),
        local["limits"],
    )
    result = {"source": "PASS", "model": local, "cycle": cycle}
    if args.urdf:
        result["expanded_urdf"] = expanded_urdf_contract(args.urdf)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
