#!/usr/bin/env python3
"""Humble-only observer for visual FSM integration checks.

This deliberately observes state/events, not physics or grasp execution.
"""

import argparse
import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger


ALL_STATES = [
    "HOME", "PICK_RAW", "STAGE", "LOAD_MACHINE", "MACHINE_DWELL",
    "UNLOAD_MACHINE", "PLACE_FINISHED", "HOME",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect", choices=("success", "load_failure", "cancelled"),
                        required=True)
    parser.add_argument("--timeout-s", type=float, default=90.0)
    args = parser.parse_args()
    rclpy.init()
    node = Node("ay05_fsm_probe")
    task_events = []
    workpiece_events = []
    cancellation_sent = False

    def collect(target, topic):
        def callback(message):
            payload = json.loads(message.data)
            target.append(payload)
            print(json.dumps({"topic": topic, "payload": payload}), flush=True)
        return callback

    node.create_subscription(String, "/cambot/task_state",
                             collect(task_events, "task_state"), 100)
    node.create_subscription(String, "/cambot/workpiece_state",
                             collect(workpiece_events, "workpiece_state"), 100)
    start_client = node.create_client(Trigger, "/machine_tending_coordinator/start")
    cancel_client = node.create_client(Trigger, "/machine_tending_coordinator/cancel")
    deadline = time.monotonic() + args.timeout_s
    try:
        while not start_client.wait_for_service(timeout_sec=0.25):
            if time.monotonic() >= deadline:
                raise RuntimeError("start service not ready")
        start_future = start_client.call_async(Trigger.Request())
        while not start_future.done() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
        if not start_future.done() or not start_future.result().success:
            raise RuntimeError("start service rejected or timed out")
        terminal = None
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            entered = [event["state"] for event in task_events
                       if event.get("event") == "ENTERED"]
            if args.expect == "cancelled" and not cancellation_sent and "PICK_RAW" in entered:
                if not cancel_client.wait_for_service(timeout_sec=0.5):
                    raise RuntimeError("cancel service not ready")
                cancel_client.call_async(Trigger.Request())
                cancellation_sent = True
            terminals = [event for event in task_events
                         if event.get("event") in ("SUCCESS", "FAILURE")]
            if terminals:
                terminal = terminals[-1]
                break
        if terminal is None:
            raise RuntimeError("FSM terminal event not observed")
        for _ in range(20):
            rclpy.spin_once(node, timeout_sec=0.1)
        entered = [event["state"] for event in task_events
                   if event.get("event") == "ENTERED"]
        phases = [event.get("process_phase") for event in workpiece_events]
        if "RAW" not in phases:
            raise RuntimeError("initial raw workpiece state not observed")
        trial_ids = {event.get("trial_id") for event in task_events
                     if event.get("event") != "RESET"}
        if len(trial_ids) != 1 or None in trial_ids:
            raise RuntimeError(f"trial IDs inconsistent: {trial_ids}")
        if not all(event.get("timestamp_utc") for event in task_events):
            raise RuntimeError("task timestamp missing")
        if args.expect == "success":
            if entered != ALL_STATES or terminal["event"] != "SUCCESS":
                raise RuntimeError(f"success sequence mismatch: {entered}, {terminal}")
            if terminal["workpiece_state"] != "FINISHED_AT_S5":
                raise RuntimeError("finished workpiece state not observed")
            if "FINISHED" not in phases:
                raise RuntimeError("finished workpiece topic update not observed")
        elif args.expect == "load_failure":
            if (entered != ALL_STATES[:4] or terminal["event"] != "FAILURE" or
                    terminal.get("cause") != "INJECTED_VISUAL_TEST_FAILURE" or
                    terminal.get("failure_step") != "S3_LOAD" or
                    terminal["workpiece_state"] != "HELD_RAW_AT_S2"):
                raise RuntimeError(f"injected failure did not stop at load: {entered}, {terminal}")
            if "FINISHED" in phases:
                raise RuntimeError("workpiece advanced after injected load failure")
        else:
            if not cancellation_sent or terminal["event"] != "FAILURE" or not \
                    terminal.get("cause", "").startswith("CANCEL"):
                raise RuntimeError(f"early cancellation failed: {terminal}")
            if "STAGE" in entered:
                raise RuntimeError("FSM advanced to STAGE after cancellation")
        print(json.dumps({"probe_result": "PASS", "expect": args.expect,
                          "states_entered": entered, "terminal": terminal,
                          "workpiece_samples": len(workpiece_events)}), flush=True)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
