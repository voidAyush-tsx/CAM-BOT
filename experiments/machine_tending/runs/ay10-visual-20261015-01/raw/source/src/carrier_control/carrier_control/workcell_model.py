"""Canonical, ROS-independent workcell geometry and target transforms.

All positions are metres and all RPY angles are radians in the ``world``
frame. Geometry is explicitly a temporary visual-simulation assumption.
"""

import math
from pathlib import Path
import subprocess


STATION_IDS = (
    "RAW_INPUT", "STAGING_INSPECTION", "CNC_MACHINE",
    "OUTPUT_UNLOADING", "FINISHED_PART",
)
STATION_SLOT = dict(zip(STATION_IDS, ("s1", "s2", "s3", "s4", "s5")))


class WorkcellError(ValueError):
    """Invalid visual workcell configuration."""


def _triple(value, field, positive=False):
    if (not isinstance(value, list) or len(value) != 3 or
            any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                not math.isfinite(v) or (positive and v <= 0) for v in value)):
        qualifier = "positive " if positive else ""
        raise WorkcellError(f"{field} must contain three finite {qualifier}numbers")


def validate_workcell(workcell):
    if not isinstance(workcell, dict):
        raise WorkcellError("workcell must be an object")
    if workcell.get("world_frame") != "world" or workcell.get("base_frame") != "base_link":
        raise WorkcellError("workcell requires world and base_link frames")
    if workcell.get("units") != {"position": "m", "orientation": "rad"}:
        raise WorkcellError("workcell units must be m/rad")
    if workcell.get("geometry_status") != "temporary_visual_simulation_assumption_not_measured":
        raise WorkcellError("unmeasured geometry must remain labelled as a simulation assumption")
    stations = workcell.get("stations")
    if not isinstance(stations, dict) or tuple(stations) != STATION_IDS:
        raise WorkcellError("workcell must have exactly five ordered station identifiers")
    frames = set()
    targets = set()
    for station_id, station in stations.items():
        if not isinstance(station, dict):
            raise WorkcellError(f"{station_id} must be an object")
        frame = station.get("frame")
        if not isinstance(frame, str) or not frame.startswith("station_") or frame in frames:
            raise WorkcellError(f"{station_id} has a missing or duplicate station frame")
        frames.add(frame)
        _triple(station.get("pose_xyz_m"), f"{station_id}.pose_xyz_m")
        _triple(station.get("pose_rpy_rad"), f"{station_id}.pose_rpy_rad")
        _triple(station.get("size_xyz_m"), f"{station_id}.size_xyz_m", positive=True)
        station_targets = station.get("targets")
        if not isinstance(station_targets, dict) or not station_targets:
            raise WorkcellError(f"{station_id} needs at least one target")
        for target, offset in station_targets.items():
            if not isinstance(target, str) or not target or target in targets:
                raise WorkcellError(f"duplicate or empty interaction target {target}")
            targets.add(target)
            _triple(offset, f"{station_id}.{target}")


def station_for_target(workcell, target):
    for station_id, station in workcell["stations"].items():
        if target in station["targets"]:
            return station_id
    raise WorkcellError(f"unknown interaction target {target}")


def target_world_xyz(workcell, target):
    """Transform a station-local XYZ target into world using its RPY pose."""
    station = workcell["stations"][station_for_target(workcell, target)]
    x, y, z = station["targets"][target]
    roll, pitch, yaw = station["pose_rpy_rad"]
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rotated = (
        cy * cp * x + (cy * sp * sr - sy * cr) * y + (cy * sp * cr + sy * sr) * z,
        sy * cp * x + (sy * sp * sr + cy * cr) * y + (sy * sp * cr - cy * sr) * z,
        -sp * x + cp * sr * y + cp * cr * z,
    )
    return [origin + offset for origin, offset in zip(station["pose_xyz_m"], rotated)]


def xacro_station_arguments(workcell):
    """Return command-line Xacro substitutions from the same runtime config."""
    validate_workcell(workcell)
    arguments = []
    for station_id, slot in STATION_SLOT.items():
        station = workcell["stations"][station_id]
        for name, values in (
            ("xyz", station["pose_xyz_m"]),
            ("rpy", station["pose_rpy_rad"]),
            ("size", station["size_xyz_m"]),
        ):
            arguments.append(f"station_{slot}_{name}:=" + " ".join(
                format(value, ".12g") for value in values
            ))
    return arguments


def render_workcell_xacro(xacro_file, workcell):
    """Expand the installed robot wrapper with validated workcell geometry."""
    arguments = [
        "xacro", str(Path(xacro_file)), "include_workcell:=true",
        *xacro_station_arguments(workcell),
    ]
    try:
        result = subprocess.run(
            arguments, check=True, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise WorkcellError(f"workcell Xacro expansion failed: {exc}") from exc
    if not result.stdout.lstrip().startswith(("<?xml", "<robot")):
        raise WorkcellError("workcell Xacro returned no URDF")
    return result.stdout
