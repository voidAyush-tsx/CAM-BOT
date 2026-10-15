#!/usr/bin/env python3
"""Generate the machine-readable CAM-BOT cross-validation report."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = "docs/evidence/AY-13/cross_validation"
CAPTURE = "experiments/machine_tending/runs/ay10-visual-20261015-03"


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def need(path):
    if not (ROOT / path).exists():
        raise RuntimeError(f"missing evidence: {path}")
    return path


def build_report():
    head = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
    ).strip()
    ledger = read_json("docs/ayush/ledger.json")
    acceptance = read_json("docs/evidence/AY-10/acceptance.json")
    metrics = read_json(f"{CAPTURE}/raw_analysis/metrics.json")
    manifest = read_json(f"{CAPTURE}/raw/manifest.json")
    inventory = read_json(f"{EVIDENCE}/source_inventory.json")
    status_text = (ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
    statuses = dict(re.findall(
        r"^\| (AY-\d{2}) \| (COMPLETE|IN PROGRESS|BLOCKED) \|",
        status_text, re.MULTILINE,
    ))
    if len(statuses) != 13 or len(ledger["records"]) != 13:
        raise RuntimeError("report requires 13 AY records and statuses")
    if inventory["count"] != len(inventory["files"]):
        raise RuntimeError("source inventory count changed")
    if subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--", "src"],
        check=False,
    ).returncode != 0:
        raise RuntimeError("src differs from report commit")
    tracked = set(subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "src"], text=True
    ).splitlines())
    mapped = {item["path"]: item["sha256"] for item in inventory["files"]}
    if set(mapped) != tracked:
        raise RuntimeError("source inventory does not cover committed source")
    for path, digest in mapped.items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"source inventory hash mismatch: {path}")

    retest = (ROOT / EVIDENCE / "colcon_retest.log").read_text(encoding="utf-8")
    regression = (ROOT / EVIDENCE / "regression_48.log").read_text(encoding="utf-8")
    comparison = (ROOT / EVIDENCE / "analysis_comparison.log").read_text(encoding="utf-8")
    if "59 tests, 0 errors, 0 failures, 2 skipped" not in retest:
        raise RuntimeError("Colcon test result is not passing")
    if "Ran 35 tests" not in regression or "Ran 13 tests" not in regression:
        raise RuntimeError("48-test regression result absent")
    if len(comparison.splitlines()) != 6 or any(
        not line.endswith(" MATCH") for line in comparison.splitlines()
    ):
        raise RuntimeError("derived artifacts do not byte-match")
    probe_path = need(f"{EVIDENCE}/live_recheck/probe.jsonl")
    probe = json.loads((ROOT / probe_path).read_text(encoding="utf-8").splitlines()[-1])
    if (probe.get("probe_result") != "VISUAL_SIMULATION_PASS" or
            probe.get("rechecks") != 5 or
            sorted(probe.get("decisions", [])) !=
            ["CARRIER_REPOSITION", "LOCAL_MANIPULATION"] or
            probe.get("actuation_verified") is not False or
            probe.get("grasp_verified") is not False):
        raise RuntimeError("live probe lacks required visual evidence")
    for name in ("preexisting_nodes.txt", "residual_nodes.txt"):
        if (ROOT / EVIDENCE / "live_recheck" / name).read_text(encoding="utf-8"):
            raise RuntimeError(f"live ROS graph was not clean: {name}")
    main = metrics["scenarios"][0]
    if (acceptance["AY-10"]["trials"] != 5 or main["attempts"] != 5 or
            main["successful_attempts"] != 5 or metrics["attempts"] != 5 or
            acceptance["runtime_verified"] is not False or
            acceptance["end_to_end_verified"] is not False):
        raise RuntimeError("five-trial visual qualification changed")

    disposition = {
        "AY-01": "REPAIR", "AY-02": "REPAIR", "AY-03": "BUILD",
        "AY-04": "BUILD", "AY-05": "BUILD", "AY-06": "BUILD",
        "AY-07": "BUILD", "AY-08": "BUILD", "AY-09": "BUILD",
        "AY-10": "BUILD", "AY-11": "BUILD", "AY-12": "BUILD",
        "AY-13": "REPAIR",
    }
    tasks = []
    for row in ledger["records"]:
        ident = row["id"]
        for path in row["files_changes"] + row["evidence"]:
            need(path)
        tasks.append({
            "id": ident,
            "disposition": disposition[ident],
            "outcome": "NOT VERIFIED" if ident == "AY-13" else "VERIFIED",
            "verified_scope": "documentation checks; independent replay pending"
            if ident == "AY-13" else "visual ROS/source/offline scope stated in ledger",
            "authoritative_status": statuses[ident],
            "source_commit_or_change": row["source_commit_or_change"],
            "changed_files": row["files_changes"],
            "tests": row["tests"],
            "evidence": row["evidence"],
            "caveat": row["limitations"],
        })

    gates = {
        "G0": {"status": "PASS", "evidence": [f"{EVIDENCE}/source_inventory.json",
                                              "docs/ayush/ledger.json"]},
        "G1": {"status": "PASS_AFTER_REPAIR", "evidence": [f"{EVIDENCE}/rosdep_check.log",
                          f"{EVIDENCE}/colcon_build.log",
                          f"{EVIDENCE}/colcon_build_scoped.log",
                          f"{EVIDENCE}/colcon_test.log",
                          f"{EVIDENCE}/colcon_retest.log"]},
        "G2": {"status": "PASS_VISUAL_MODEL", "evidence": [f"{EVIDENCE}/model_assets.log",
                          probe_path]},
        "G3": {"status": "PASS_VISUAL_ONLY", "evidence": [probe_path,
                          f"{EVIDENCE}/live_recheck/residual_nodes.txt"]},
        "G4": {"status": "PASS_VISUAL_ASSUMPTIONS", "evidence": [
            f"{EVIDENCE}/model_assets.log",
            f"{EVIDENCE}/live_recheck/visual_rosbag/metadata.yaml"]},
        "G5": {"status": "PASS_VISUAL_AND_OFFLINE", "evidence": [
            f"{EVIDENCE}/regression_48.log", probe_path]},
        "G6": {"status": "PASS_VISUAL_ONLY", "evidence": [
            probe_path, "src/carrier_control/test/test_coordination.py"]},
        "G7": {"status": "PASS_VISUAL_ONLY", "evidence": [
            probe_path, f"{EVIDENCE}/live_recheck/visual_rosbag/metadata.yaml"]},
        "G8": {"status": "PASS_VISUAL_ONLY", "evidence": [
            "docs/evidence/AY-10/acceptance.json", f"{CAPTURE}/raw/manifest.json"]},
        "G9": {"status": "PASS", "evidence": [
            f"{EVIDENCE}/analysis_regeneration.log",
            f"{EVIDENCE}/analysis_comparison.log"]},
        "G10": {"status": "AUTOMATED_PASS_PEER_PENDING", "evidence": [
            "docs/evidence/AY-13/source_contract.log",
            "docs/evidence/AY-13/doc_checker_tests.log",
            "docs/ayush/README.md"]},
    }
    for gate in gates.values():
        for path in gate["evidence"]:
            need(path)

    return {
        "title": "CAM-BOT BUILD REPORT",
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "commit": head,
        "commit_role": "validated ROS source and cross-validation repair commit",
        "environment": {
            "host": "CachyOS x86_64",
            "container": "Ubuntu 22.04.5 LTS via cambot-humble Distrobox",
            "ros": "ROS 2 Humble",
            "rviz": "11.2.28 (archived AY-10 manifest)",
            "gazebo": "not launched or verified in this validation",
            "capture_environment": manifest["environment"],
        },
        "source_inventory": {"path": f"{EVIDENCE}/source_inventory.json",
                             "tracked_src_files": inventory["count"]},
        "verification_boundary": {
            "available_code": True,
            "visual_ros_run_observed": True,
            "measured_complete_visual_cycle": True,
            "actuated_simulated_run_verified": False,
            "physical_or_cnc_run_verified": False,
            "grasp_verified": False,
            "collision_or_ik_verified": False,
        },
        "joint_state_authority": {
            "visual_mode": "one observed /joint_states publisher: machine_tending_coordinator",
            "controller_mode_source_contract": "coordinator publishes only four BM and three workpiece joints; external controller must own UR5 feedback",
            "controller_mode_live_publisher_audit": "NOT RUN",
            "evidence": [f"{EVIDENCE}/live_recheck/joint_state_publishers.txt",
                         "src/carrier_control/carrier_control/machine_tending_coordinator.py"],
        },
        "ids": tasks,
        "gates": gates,
        "end_to_end_scenarios": {
            "S1_local": {"status": "PASS", "scope": "visual/offline",
                         "evidence": [probe_path, "src/carrier_control/test/test_coordination.py"]},
            "S2_global": {"status": "NOT RUN", "scope": "requested UR5 action result unavailable; visual reposition/recheck passed",
                          "evidence": [probe_path]},
            "S3_impossible": {"status": "NOT RUN", "scope": "live impossible-target case not run; bounded offline failure test passed",
                              "evidence": ["src/carrier_control/test/test_coordination.py",
                                           f"{EVIDENCE}/regression_48.log"]},
            "S4_controller_rejection": {"status": "NOT RUN", "scope": "no selected controller; offline rejection/timeout contracts passed",
                                        "evidence": ["src/carrier_control/test/test_action_safety.py",
                                                     f"{EVIDENCE}/regression_48.log"]},
            "S5_clean_repeatability": {"status": "PASS", "scope": "archived five-attempt visual capture; current source one-cycle recheck",
                                       "evidence": ["docs/evidence/AY-10/acceptance.json",
                                                    f"{CAPTURE}/raw/attempts.jsonl",
                                                    f"{EVIDENCE}/live_recheck/residual_nodes.txt"]},
        },
        "trials": {
            "qualifying_raw_attempted": 5,
            "qualifying_succeeded": 5,
            "qualifying_failed": 0,
            "all_retained_attempted_separate_captures": 6,
            "all_retained_succeeded_separate_captures": 6,
            "scenario_pooling": "none",
        },
        "metric_definitions": {
            "cycle_time": metrics["cycle_boundary"],
            "clock": "node monotonic timestamps; UTC and ROS stamps retained for correlation",
            "carrier_reposition": metrics["motion_count_rule"],
            "success_rate": "100 * successful_attempts / all_attempts; failures remain in denominator",
        },
        "results": {
            "raw_dataset": f"{CAPTURE}/raw/trials.csv",
            "raw_events": f"{CAPTURE}/raw/trials.events.jsonl",
            "raw_manifest": f"{CAPTURE}/raw/manifest.json",
            "metrics": f"{CAPTURE}/raw_analysis/metrics.json",
            "trials_table": f"{CAPTURE}/raw_analysis/trials.csv",
            "summary_table": f"{CAPTURE}/raw_analysis/summary.csv",
            "plots": [f"{CAPTURE}/raw_analysis/{name}.png" for name in
                      ("cycle_time_by_trial", "trial_outcomes",
                       "carrier_repositions_by_trial")],
            "mean_successful_cycle_time_s": main["successful_cycle_time"]["mean_s"],
            "completed_visual_carrier_repositions": main["carrier_repositions_completed"],
        },
        "open_blockers": [
            "No selected UR5 controller bring-up/action results in this checkout.",
            "S1–S4 controller targets unvalidated; S5 lacks a taught carrier target.",
            "No bimanual/gripper controller feedback or grasp verification.",
            "Independent second-person clean-checkout repeat for AY-13 pending.",
        ],
        "scope_extensions_excluded": [f"AY-{n:02d}" for n in range(14, 21)],
    }


def main():
    report = build_report()
    output = ROOT / "artifacts/verification/cambot_build_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{output.relative_to(ROOT)}: {len(report['ids'])} AY IDs, "
          f"{len(report['gates'])} gates, {report['trials']['qualifying_raw_attempted']} visual attempts")


if __name__ == "__main__":
    main()
