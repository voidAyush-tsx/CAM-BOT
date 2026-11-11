#!/usr/bin/env python3
"""Cross-check offline FK against robot_state_publisher TF in an empty ROS domain."""

import argparse
import json
from pathlib import Path
import signal
import subprocess
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import JointState
from tf2_ros import Buffer, TransformException, TransformListener
import yaml

from analyze_workspace import Chain, ROOT


def check(urdf, output):
    output.mkdir(parents=True, exist_ok=False)
    existing = subprocess.check_output(["ros2", "node", "list", "--no-daemon"], text=True)
    if existing.strip():
        raise RuntimeError("choose an empty ROS domain")
    xml = urdf.read_text()
    chain = Chain(xml)
    plan = json.loads((ROOT / "src/carrier_control/config/machine_tending.json").read_text())
    parameters = output / "robot-description.yaml"
    parameters.write_text(yaml.safe_dump({"robot_state_publisher": {
        "ros__parameters": {"robot_description": xml}}}))
    rclpy.init()
    node = Node("workspace_fk_probe")
    publisher = node.create_publisher(JointState, "/joint_states", 10)
    buffer = Buffer()
    listener = TransformListener(buffer, node)
    records = []
    with (output / "publisher.log").open("w") as log:
        process = subprocess.Popen([
            "/opt/ros/humble/lib/robot_state_publisher/robot_state_publisher",
            "--ros-args", "--params-file", str(parameters)],
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            for name in ("HOME", "S1_RAW", "S3_MACHINE", "S5_FINISHED"):
                q = plan["stations"][name]["visual_carrier_joints"]
                expected = chain.forward(q)[0]
                earliest = node.get_clock().now().nanoseconds
                deadline = time.monotonic() + 10
                while True:
                    if time.monotonic() >= deadline or process.poll() is not None:
                        raise RuntimeError(f"fresh matching TF unavailable for {name}")
                    message = JointState()
                    message.header.stamp = node.get_clock().now().to_msg()
                    message.name, message.position = chain.names, q
                    publisher.publish(message)
                    rclpy.spin_once(node, timeout_sec=0.05)
                    try:
                        tf = buffer.lookup_transform("world", "dual_arm_base_link", Time())
                    except TransformException:
                        continue
                    if tf.header.stamp.sec * 10**9 + tf.header.stamp.nanosec < earliest:
                        continue
                    t, quat = tf.transform.translation, tf.transform.rotation
                    x, y, z, w = quat.x, quat.y, quat.z, quat.w
                    observed = np.eye(4)
                    observed[:3, 3] = [t.x, t.y, t.z]
                    observed[:3, :3] = [
                        [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                        [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                        [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
                    error = float(np.max(np.abs(expected - observed)))
                    if error > 1e-9:
                        raise RuntimeError(f"FK/TF mismatch for {name}: {error}")
                    records.append({"station": name, "max_matrix_error": error,
                                    "observed_xyz_m": observed[:3, 3].tolist()})
                    break
            if node.count_publishers("/joint_states") != 1:
                raise RuntimeError("duplicate joint-state publisher")
        finally:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise
            finally:
                listener.unregister()
                node.destroy_node()
                rclpy.shutdown()
    if process.returncode != 0:
        raise RuntimeError("robot-state publisher shutdown failed")
    residual = subprocess.check_output(["ros2", "node", "list", "--no-daemon"], text=True)
    (output / "residual_nodes.txt").write_text(residual)
    if residual.strip():
        raise RuntimeError("residual nodes after FK probe")
    (output / "result.json").write_text(json.dumps({
        "result": "PASS", "poses": records, "collision_checked": False,
        "actuation_verified": False}, indent=2) + "\n")
    print("FK_TF_CROSSCHECK_PASS: four poses, one publisher, empty residual graph")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    check(args.urdf, args.output.resolve())
