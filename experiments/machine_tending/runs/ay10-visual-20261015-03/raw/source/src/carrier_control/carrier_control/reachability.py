"""Geometric proxy workspace in dual_arm_base_link; not IK or collision proof."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ReachabilityResult:
    status: str  # REACHABLE, UNREACHABLE, UNKNOWN
    reason: str
    local_xyz_m: tuple[float, float, float] | None
    arms: dict[str, bool]


def validate_workspace(config):
    if not isinstance(config, dict) or config.get("units") != "m":
        raise ValueError("workspace units must be m")
    if config.get("frame") != "dual_arm_base_link":
        raise ValueError("workspace frame must be dual_arm_base_link")
    if config.get("max_reposition_attempts") != 1:
        raise ValueError("prototype permits exactly one reposition attempt")
    for arm in ("left", "right"):
        limits = config.get(arm)
        if not isinstance(limits, dict):
            raise ValueError(f"missing {arm} workspace")
        center = limits.get("center_xyz_m")
        bounds = limits.get("bounds_xyz_m")
        radius = limits.get("max_radius_m")
        if (not _finite_vector(center, 3) or not isinstance(bounds, list) or
                len(bounds) != 3 or any(not _finite_vector(axis, 2) or
                                        axis[0] > axis[1] for axis in bounds) or
                isinstance(radius, bool) or not isinstance(radius, (int, float)) or
                not math.isfinite(radius) or radius <= 0):
            raise ValueError(f"invalid {arm} geometric workspace")


def _finite_vector(value, count):
    return (isinstance(value, (tuple, list)) and len(value) == count and
            all(not isinstance(v, bool) and isinstance(v, (int, float)) and
                math.isfinite(v) for v in value))


def _rotate(q, vector):
    x, y, z, w = q
    vx, vy, vz = vector
    # Unit-quaternion rotation, expanded without an external math dependency.
    tx, ty, tz = (2 * (y * vz - z * vy),
                  2 * (z * vx - x * vz),
                  2 * (x * vy - y * vx))
    return (vx + w * tx + y * tz - z * ty,
            vy + w * ty + z * tx - x * tz,
            vz + w * tz + x * ty - y * tx)


def evaluate_reachability(target_world_xyz_m, world_from_base, workspace,
                          required_arms="both"):
    """Transform world XYZ by current TF (xyz, xyzw) and test inclusive proxy bounds.

    Unknown or malformed TF is UNKNOWN, never reachable. A single-arm pass
    cannot satisfy a both-arm requirement.
    """
    validate_workspace(workspace)
    if required_arms not in ("left", "right", "both"):
        raise ValueError("required_arms must be left, right or both")
    if not _finite_vector(target_world_xyz_m, 3):
        return ReachabilityResult("UNKNOWN", "INVALID_TARGET", None, {})
    if (not isinstance(world_from_base, (tuple, list)) or
            len(world_from_base) != 2 or
            not _finite_vector(world_from_base[0], 3) or
            not _finite_vector(world_from_base[1], 4)):
        return ReachabilityResult("UNKNOWN", "MISSING_OR_INVALID_TF", None, {})
    origin, quat = world_from_base
    norm = math.sqrt(sum(value * value for value in quat))
    if not 0.999 <= norm <= 1.001:
        return ReachabilityResult("UNKNOWN", "INVALID_TF_QUATERNION", None, {})
    inverse = (-quat[0] / norm, -quat[1] / norm,
               -quat[2] / norm, quat[3] / norm)
    local = _rotate(inverse, tuple(a - b for a, b in
                                   zip(target_world_xyz_m, origin)))
    arms = {}
    for arm in ("left", "right"):
        limits = workspace[arm]
        center = limits["center_xyz_m"]
        inside_box = all(low <= value <= high for value, (low, high) in
                         zip(local, limits["bounds_xyz_m"]))
        inside_radius = sum((a - b) ** 2 for a, b in zip(local, center)) <= (
            limits["max_radius_m"] ** 2 + 1e-12)
        arms[arm] = inside_box and inside_radius
    selected = (arms["left"] and arms["right"] if required_arms == "both"
                else arms[required_arms])
    return ReachabilityResult("REACHABLE" if selected else "UNREACHABLE",
                              "GEOMETRIC_PROXY_PASS" if selected else
                              "OUTSIDE_GEOMETRIC_PROXY", local, arms)
