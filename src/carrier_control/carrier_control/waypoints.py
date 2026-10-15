"""
Load the intentionally small, fixed-schema machine-shop waypoint file.

This accepts only the flat YAML subset used by config/waypoints.yaml.  It does
not silently accept new keys or malformed trajectories.  No ROS installation
is needed to test the schema.
"""

import ast
import math
from pathlib import Path


TARGETS = ("home", "P1", "P2", "P3", "P4")
UR5_JOINT_NAMES = (
    "shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
    "wrist_1_joint", "wrist_2_joint", "wrist_3_joint",
)


def parse_waypoints(text):
    values = {}
    current = None
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  joints: ") and current in TARGETS:
            if current in values:
                raise ValueError(f"duplicate joints for {current} at line {line_number}")
            try:
                joints = ast.literal_eval(line.split(":", 1)[1].strip())
            except (SyntaxError, ValueError) as exc:
                raise ValueError(f"invalid joints at line {line_number}") from exc
            if (not isinstance(joints, list) or len(joints) != 6 or
                    any(isinstance(j, bool) or not isinstance(j, (int, float)) or
                        not math.isfinite(j) for j in joints)):
                raise ValueError(f"expected six finite joints at line {line_number}")
            values[current] = [float(j) for j in joints]
            current = None
        elif line.startswith("dwell_time: "):
            if "dwell_time" in values:
                raise ValueError("duplicate dwell_time")
            try:
                dwell = float(line.split(":", 1)[1].strip())
            except ValueError as exc:
                raise ValueError("invalid dwell_time") from exc
            if not math.isfinite(dwell) or dwell < 0:
                raise ValueError("dwell_time must be nonnegative and finite")
            values["dwell_time"] = dwell
            current = None
        elif line in [f"{name}:" for name in TARGETS]:
            if current is not None:
                raise ValueError(f"missing joints for {current}")
            current = line[:-1]
        else:
            raise ValueError(f"unexpected waypoint syntax at line {line_number}")
    missing = set(TARGETS + ("dwell_time",)) - values.keys()
    if missing:
        raise ValueError(f"missing waypoint fields: {', '.join(sorted(missing))}")
    return values


def load_waypoints(path):
    return parse_waypoints(Path(path).read_text(encoding="utf-8"))
