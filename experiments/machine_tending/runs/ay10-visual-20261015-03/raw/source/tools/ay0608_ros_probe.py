#!/usr/bin/env python3
"""Humble visual-only AY-06/08 observer; never labels animation actuation."""

import json
import time

import rclpy
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformListener


EXPECTED = ["HOME", "PICK_RAW", "STAGE", "LOAD_MACHINE", "MACHINE_DWELL",
            "UNLOAD_MACHINE", "PLACE_FINISHED", "HOME"]
UR5 = ("shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
       "wrist_1_joint", "wrist_2_joint", "wrist_3_joint")


def main():
    rclpy.init()
    node = Node("ay0608_visual_probe")
    tf_buffer = Buffer()
    listener = TransformListener(tf_buffer, node, spin_thread=False)
    task, decision, workpiece, carrier_samples = [], [], [], []

    def collect(target, topic):
        def callback(message):
            data = json.loads(message.data)
            target.append(data)
            print(json.dumps({"topic": topic, "data": data}), flush=True)
        return callback

    node.create_subscription(String, "/cambot/task_state",
                             collect(task, "task_state"), 100)
    node.create_subscription(String, "/cambot/coordination_decision",
                             collect(decision, "coordination_decision"), 100)
    node.create_subscription(String, "/cambot/workpiece_state",
                             collect(workpiece, "workpiece_state"), 100)

    def joint_callback(message):
        positions = dict(zip(message.name, message.position))
        if all(name in positions for name in UR5):
            carrier_samples.append(tuple(positions[name] for name in UR5))

    node.create_subscription(JointState, "/joint_states", joint_callback, 100)
    start = node.create_client(Trigger, "/machine_tending_coordinator/start")
    deadline = time.monotonic() + 100
    try:
        while not start.wait_for_service(timeout_sec=0.25):
            if time.monotonic() >= deadline:
                raise RuntimeError("start service unavailable")
        if node.count_publishers("/joint_states") != 1:
            raise RuntimeError("visual mode requires one joint-state publisher")
        future = start.call_async(Trigger.Request())
        while not future.done() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
        if not future.done() or not future.result().success:
            raise RuntimeError("start rejected")
        while time.monotonic() < deadline and not any(
                event.get("event") in ("SUCCESS", "FAILURE") for event in task):
            rclpy.spin_once(node, timeout_sec=0.1)
        entered = [event.get("state") for event in task
                   if event.get("event") == "ENTERED"]
        terminal = [event for event in task
                    if event.get("event") in ("SUCCESS", "FAILURE")]
        if not terminal or terminal[-1]["event"] != "SUCCESS":
            raise RuntimeError(f"visual FSM failed: {terminal[-1:]}")
        if entered != EXPECTED:
            raise RuntimeError(f"state order mismatch: {entered}")
        choices = {event.get("decision") for event in decision}
        if not {"LOCAL_MANIPULATION", "CARRIER_REPOSITION"} <= choices:
            raise RuntimeError(f"both policy branches not observed: {choices}")
        rechecked = [event for event in decision
                     if event.get("outcome") == "RECHECKED_AFTER_CARRIER"]
        if not rechecked or not all(
                event.get("decision") == "LOCAL_MANIPULATION" for event in rechecked):
            raise RuntimeError("post-move TF/reachability recheck did not pass")
        if not any(event.get("process_phase") == "FINISHED" for event in workpiece):
            raise RuntimeError("finished workpiece update missing")
        if len(set(carrier_samples)) < 2:
            raise RuntimeError("visual UR5 joint-state animation did not change")
        try:
            transform = tf_buffer.lookup_transform("world", "dual_arm_base_link", Time())
        except Exception as exc:
            raise RuntimeError(f"live world-to-BM TF missing: {exc}") from exc
        if not all(event.get("mode") == "visual_simulation" for event in decision):
            raise RuntimeError("unexpected controller-mode decision")
        print(json.dumps({
            "probe_result": "VISUAL_SIMULATION_PASS",
            "states": entered, "decisions": sorted(choices),
            "rechecks": len(rechecked),
            "visual_carrier_joint_samples": len(carrier_samples),
            "latest_tf_stamp": str(transform.header.stamp),
            "actuation_verified": False, "grasp_verified": False,
        }), flush=True)
    finally:
        del listener
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
