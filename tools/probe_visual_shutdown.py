#!/usr/bin/env python3
"""Exercise idle/active SIGINT shutdown; retain logs in a fresh directory."""

import argparse
import csv
import json
import os
from pathlib import Path
import signal
import subprocess
import time

try:
    from .check_ros_shutdown import check_shutdown
except ImportError:
    from check_ros_shutdown import check_shutdown


def validate_trials(rows, scenario):
    """Reject a success record after interruption or any trial during idle."""
    if scenario == "idle":
        if rows:
            raise ValueError("idle launch unexpectedly recorded a trial")
    elif scenario == "active":
        if len(rows) != 1 or any(rows[0].get(key) != value for key, value in {
                "status": "INCOMPLETE", "success": "False",
                "workpiece_final_state": "RAW_AT_S1"}.items()):
            raise ValueError(f"expected one interrupted raw-workpiece trial: {rows}")
    else:
        raise ValueError(f"unknown scenario: {scenario}")


def node_list(output):
    result = subprocess.run(
        ["ros2", "node", "list", "--no-daemon"], check=True,
        capture_output=True, text=True, timeout=15)
    output.write_text(result.stdout)
    if result.stdout.strip():
        raise RuntimeError(f"ROS domain is occupied; see {output}")


def run(output, scenario):
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    from std_srvs.srv import Trigger

    output.mkdir(parents=True, exist_ok=False)
    node_list(output / "preexisting_nodes.txt")
    rclpy.init()
    node = Node("ay13_shutdown_observer")
    events = []
    node.create_subscription(
        String, "/cambot/task_state",
        lambda message: events.append(json.loads(message.data)), 100)
    client = node.create_client(Trigger, "/machine_tending_coordinator/start")
    process = None
    try:
        with (output / "launch.log").open("w") as log:
            process = subprocess.Popen([
                "ros2", "launch", "carrier_description", "dual_arm_demo.launch.py",
                "auto_start:=false", "enable_coordination:=true",
                "results_file:=" + str(output / "trials.csv")],
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + 40

            def wait_until(predicate, description):
                while not predicate():
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError(f"launch stopped or timed out waiting for {description}")
                    rclpy.spin_once(node, timeout_sec=0.05)

            expected = {"robot_state_publisher", "machine_tending_coordinator", "rviz2"}
            wait_until(lambda: expected.issubset(set(node.get_node_names())) and
                       client.service_is_ready() and
                       "OpenGl version" in (output / "launch.log").read_text(),
                       "three nodes, start service and rendered RViz")
            publishers = node.get_publishers_info_by_topic("/joint_states")
            names = [publisher.node_name for publisher in publishers]
            if names != ["machine_tending_coordinator"]:
                raise RuntimeError(f"unexpected joint-state publishers: {names}")
            (output / "graph.json").write_text(json.dumps({
                "nodes": sorted(node.get_node_names()),
                "joint_state_publishers": names}, indent=2) + "\n")
            if scenario == "active":
                future = client.call_async(Trigger.Request())
                wait_until(future.done, "start acknowledgement")
                if not future.result().success:
                    raise RuntimeError("start request rejected")
                wait_until(lambda: any(event.get("state") == "PICK_RAW" and
                                       event.get("event") == "ENTERED" for event in events),
                           "PICK_RAW")
            else:
                until = time.monotonic() + 3
                wait_until(lambda: time.monotonic() >= until, "idle rendering")
            process.send_signal(signal.SIGINT)  # launch forwards once to its children
            if process.wait(timeout=15) != 0:
                raise RuntimeError("launch returned a nonzero exit code")
        check_shutdown((output / "launch.log").read_text())
        trials = output / "trials.csv"
        with trials.open() if trials.exists() else open(os.devnull) as stream:
            rows = list(csv.DictReader(stream))
        validate_trials(rows, scenario)
    finally:
        # Only clean up the process group created by this probe; escalation fails
        # the test above and never counts as graceful shutdown.
        try:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        finally:
            node.destroy_node()
            rclpy.shutdown()
    node_list(output / "residual_nodes.txt")
    (output / "task_events.json").write_text(json.dumps(events, indent=2) + "\n")
    (output / "result.json").write_text(json.dumps({
        "result": "PASS", "scenario": scenario, "trials": rows,
        "actuation_verified": False, "grasp_verified": False}, indent=2) + "\n")
    print(f"VISUAL_SHUTDOWN_PASS: {scenario}, clean exits and no residual nodes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scenario", choices=("idle", "active"), required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.scenario)
