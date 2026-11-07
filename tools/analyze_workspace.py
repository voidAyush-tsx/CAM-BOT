#!/usr/bin/env python3
"""Sample URDF kinematics and compare assumed placements; no collision/IK claim."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/carrier_control"))
from carrier_control.workflow import load_plan  # noqa: E402
from carrier_control.workcell_model import target_world_xyz  # noqa: E402


def rotation(axis, angles):
    axis = np.asarray(axis, dtype=float)
    if axis.shape != (3,) or not np.isfinite(axis).all() or np.linalg.norm(axis) == 0:
        raise ValueError("joint axis must be a finite nonzero vector")
    x, y, z = axis / np.linalg.norm(axis)
    skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    angle = np.asarray(angles)[..., None, None]
    return np.eye(3) + np.sin(angle) * skew + (1 - np.cos(angle)) * (skew @ skew)


def pose(xyz, rpy):
    xyz, rpy = np.asarray(xyz, dtype=float), np.asarray(rpy, dtype=float)
    if xyz.shape != (3,) or rpy.shape != (3,) or not np.isfinite([xyz, rpy]).all():
        raise ValueError("pose requires finite xyz/rpy triples")
    matrix = np.eye(4)
    matrix[:3, :3] = (rotation([0, 0, 1], rpy[2]) @
                      rotation([0, 1, 0], rpy[1]) @ rotation([1, 0, 0], rpy[0]))
    matrix[:3, 3] = xyz
    return matrix


class Chain:
    """Read fixed/revolute joints from expanded URDF, retaining declared limits."""

    def __init__(self, xml, root="world", tip="dual_arm_base_link"):
        joints = list(ET.fromstring(xml).findall("joint"))
        by_child = {j.find("child").get("link"): j for j in joints}
        if len(by_child) != len(joints):
            raise ValueError("duplicate child link")
        chain, seen = [], set()
        while tip != root:
            if tip in seen or tip not in by_child:
                raise ValueError("missing or cyclic root-to-tip chain")
            seen.add(tip)
            joint = by_child[tip]
            chain.append(joint)
            tip = joint.find("parent").get("link")
        self.joints, self.names, limits = [], [], []
        for joint in reversed(chain):
            kind = joint.get("type")
            if kind not in ("fixed", "revolute") or joint.find("mimic") is not None:
                raise ValueError("analysis supports only fixed and bounded revolute joints")
            origin = joint.find("origin")
            attrs = {} if origin is None else origin.attrib
            transform = pose([float(x) for x in attrs.get("xyz", "0 0 0").split()],
                             [float(x) for x in attrs.get("rpy", "0 0 0").split()])
            axis = None
            if kind == "revolute":
                axis_node = joint.find("axis")
                axis = [float(x) for x in (
                    "1 0 0" if axis_node is None else axis_node.get("xyz")).split()]
                rotation(axis, 0)  # validate even before evaluating a sample
                limit = joint.find("limit")
                if limit is None or not {"lower", "upper"}.issubset(limit.attrib):
                    raise ValueError("every sampled joint needs explicit limits")
                bounds = [float(limit.get(key)) for key in ("lower", "upper")]
                if not np.isfinite(bounds).all() or bounds[0] >= bounds[1]:
                    raise ValueError("invalid joint limits")
                self.names.append(joint.get("name"))
                limits.append(bounds)
            self.joints.append((transform, axis))
        self.limits = np.asarray(limits)

    def forward(self, configurations):
        q = np.atleast_2d(np.asarray(configurations, dtype=float))
        if q.shape[1] != len(self.names) or not np.isfinite(q).all():
            raise ValueError("configuration shape or values invalid")
        if np.any(q < self.limits[:, 0]) or np.any(q > self.limits[:, 1]):
            raise ValueError("joint limit exceeded")
        result = np.broadcast_to(np.eye(4), (len(q), 4, 4)).copy()
        index = 0
        for origin, axis in self.joints:
            result = result @ origin
            if axis is not None:
                motion = np.broadcast_to(np.eye(4), result.shape).copy()
                motion[:, :3, :3] = rotation(axis, q[:, index])
                result = result @ motion
                index += 1
        return result


def proxy_margins(target, transforms, workspace):
    """Signed clearance to both proxy boxes/spheres, not a robot workspace margin."""
    local = np.einsum("nji,nj->ni", transforms[:, :3, :3],
                      np.asarray(target) - transforms[:, :3, 3])
    margins = []
    for arm in ("left", "right"):
        config = workspace[arm]
        bounds = np.asarray(config["bounds_xyz_m"])
        margins += [np.min(local - bounds[:, 0], axis=1),
                    np.min(bounds[:, 1] - local, axis=1),
                    config["max_radius_m"] - np.linalg.norm(
                        local - config["center_xyz_m"], axis=1)]
    return np.min(margins, axis=0)


def analyze(urdf, config, placements, output, samples=20000, seed=13):
    if output.exists():
        raise FileExistsError(f"choose a new output directory: {output}")
    if samples < 1:
        raise ValueError("samples must be positive")
    plan = load_plan(config)
    chain = Chain(urdf.read_text())
    if chain.names != plan["carrier"]["joint_names"]:
        raise ValueError("URDF/config carrier joint order mismatch")
    candidates = json.loads(placements.read_text())
    if not candidates or len({c["name"] for c in candidates}) != len(candidates):
        raise ValueError("placements must have unique names")
    candidate_poses = [pose(c["xyz_m"], c["rpy_rad"]) for c in candidates]
    rng = np.random.default_rng(seed)
    random_q = rng.uniform(chain.limits[:, 0], chain.limits[:, 1], (samples, len(chain.names)))
    named = list(plan["stations"])
    known_q = np.array([plan["stations"][name]["visual_carrier_joints"] for name in named])
    q = np.concatenate([random_q, known_q])
    transforms = chain.forward(q)
    targets = {name: target_world_xyz(plan["workcell"], name)
               for station in plan["workcell"]["stations"].values()
               for name in station["targets"]}
    output.mkdir(parents=True, exist_ok=False)
    configured = []
    for name, station in plan["stations"].items():
        for mode in ("visual_carrier_joints", "carrier_joints"):
            values = station[mode]
            entry = {"station": name, "configuration": mode, "joints": values,
                     "controller_validated": station["controller_validated"]}
            if values is not None:
                transform = chain.forward(values)
                entry["base_xyz_m"] = transform[0, :3, 3].tolist()
                cell = station.get("workcell_station_id")
                entry["target_proxy_clearance_m"] = {
                    target: float(proxy_margins(targets[target], transform, plan["workspace"])[0])
                    for target in plan["workcell"]["stations"][cell]["targets"]} if cell else {}
            configured.append(entry)
    (output / "configured_targets.json").write_text(json.dumps(configured, indent=2) + "\n")
    np.savetxt(output / "point_cloud.csv", np.column_stack([q, transforms[:, :3, 3]]),
               delimiter=",", header=",".join(chain.names + ["x_m", "y_m", "z_m"]), comments="")
    rows, journeys = [], []
    for candidate, placement in zip(candidates, candidate_poses):
        placed = placement @ transforms
        masks = {}
        for target, xyz in targets.items():
            margins = proxy_margins(xyz, placed, plan["workspace"])
            masks[target] = margins >= 0
            rows.append({"placement": candidate["name"], "target": target,
                         "proxy_matching_samples": int(np.count_nonzero(masks[target])),
                         "random_matches": int(np.count_nonzero(masks[target][:samples])),
                         "best_proxy_clearance_m": float(margins.max()),
                         "nearest_sampled_base_distance_m": float(np.linalg.norm(
                             placed[:, :3, 3] - xyz, axis=1).min()),
                         "workspace_boundary_margin_m": None})
        current, travel, selected = known_q[named.index("HOME")], 0.0, []
        for step in plan["workflow"]:
            if not step.get("target") or not step.get("station"):
                continue
            indices = np.flatnonzero(masks[step["target"]])
            if not len(indices):
                travel = None
                break
            costs = np.abs(q[indices] - current).sum(axis=1)
            index = int(indices[int(costs.argmin())])
            travel += float(costs.min())
            current = q[index]
            selected.append({"step": step["name"], "sample_index": index})
        if travel is not None:
            travel += float(np.abs(current - known_q[named.index("HOME")]).sum())
        journeys.append({"placement": candidate["name"],
                         "targets_with_proxy_samples": sum(bool(mask.any()) for mask in masks.values()),
                         "greedy_endpoint_joint_travel_rad": travel,
                         "selected_samples": selected})
    with (output / "station_coverage.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "scope": "preliminary model kinematics and both-arm geometric proxy only",
        "geometry_status": plan["workcell"]["geometry_status"],
        "collision_checked": False, "ik_validated": False,
        "orientation_constraints_evaluated": False,
        "actuation_verified": False, "grasp_verified": False,
        "physical_placement_recommendation": None,
        "seed": seed, "random_samples": samples, "known_visual_samples": named,
        "joint_names": chain.names, "joint_limits_rad": chain.limits.tolist(),
        "sampled_base_aabb_m": [transforms[:, :3, 3].min(axis=0).tolist(),
                                transforms[:, :3, 3].max(axis=0).tolist()],
        "placements": candidates, "targets_world_m": targets, "comparisons": journeys,
        "input_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in (urdf, config, placements)},
        "source_commit": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "numpy_version": np.__version__,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")
    points = transforms[::max(1, len(transforms) // 5000), :3, 3]
    ax.scatter(*points.T, s=1, alpha=0.12, label="Sampled bimanual-base origins")
    for name, xyz in targets.items():
        ax.scatter(*xyz, s=25)
        ax.text(*xyz, name, fontsize=7)
    ax.set(xlabel="World X (m)", ylabel="World Y (m)", zlabel="World Z (m)",
           title="Assumed layout: kinematic samples, collision unchecked")
    ax.legend(loc="upper left")
    ax.set_box_aspect(np.ptp(points, axis=0))
    fig.tight_layout()
    fig.savefig(output / "workspace.png", dpi=150)
    plt.close(fig)
    print(json.dumps(journeys, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "src/carrier_control/config/machine_tending.json")
    parser.add_argument("--placements", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()
    analyze(args.urdf, args.config, args.placements, args.output, args.samples, args.seed)
