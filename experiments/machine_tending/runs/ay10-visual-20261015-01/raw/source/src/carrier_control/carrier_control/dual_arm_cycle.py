#!/usr/bin/env python3
"""Phase-4 synchronized placeholder bimanual motion cycle."""
import time
from typing import Dict, List, Tuple

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class DualArmCycle(Node):
    JOINTS = [
        "shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
        "wrist_1_joint", "wrist_2_joint", "wrist_3_joint",
        "left_shoulder_joint", "left_elbow_joint",
        "right_shoulder_joint", "right_elbow_joint",
    ]
    CUSTOM = JOINTS[6:]

    # The custom-joint values below are the documented Phase-4 placeholder
    # motion values. They are not a physical grasp solution.
    STAGES: List[Tuple[str, Dict[str, float], float]] = [
        ("HOME",     dict(ls=0.0,  le=0.0,  rs=0.0,  re=0.0), 1.5),
        ("APPROACH", dict(ls=-0.45, le=0.0,  rs=0.45, re=0.0), 2.0),
        ("GRASP",    dict(ls=-0.45, le=-1.20, rs=0.45, re=1.20), 1.5),
        ("HOLD",     dict(ls=-0.45, le=-1.20, rs=0.45, re=1.20), 0.8),
        ("TRANSPORT",dict(ls=-0.80, le=-1.20, rs=0.80, re=1.20), 2.0),
        ("PLACE",    dict(ls=-1.00, le=-1.20, rs=1.00, re=1.20), 2.0),
        ("RELEASE",  dict(ls=-1.00, le=0.0,  rs=1.00, re=0.0), 1.2),
        ("HOME",     dict(ls=0.0,  le=0.0,  rs=0.0,  re=0.0), 2.0),
    ]

    def __init__(self) -> None:
        super().__init__("dual_arm_cycle")
        self.pub = self.create_publisher(JointState, "/joint_states", 10)
        self.timer = self.create_timer(0.02, self._tick)  # ~50 Hz
        self.index = 0
        self.phase_elapsed = 0.0
        self.current = {k: 0.0 for k in ("ls", "le", "rs", "re")}
        self.start = dict(self.current)
        self.target = dict(self.current)
        self.stage_name = "HOME"
        self._set_stage(0)
        self.get_logger().info("Phase-4 synchronized dual-arm cycle started")

    def _set_stage(self, index: int) -> None:
        self.index = index
        self.stage_name, target, duration = self.STAGES[index]
        self.start = dict(self.current)
        self.target = dict(target)
        self.duration = duration
        self.phase_elapsed = 0.0
        self.get_logger().info(f"Stage: {self.stage_name}")

    @staticmethod
    def _ease(alpha: float) -> float:
        return 3.0 * alpha * alpha - 2.0 * alpha * alpha * alpha

    def _tick(self) -> None:
        dt = 0.02
        self.phase_elapsed += dt
        alpha = min(1.0, self.phase_elapsed / self.duration)
        s = self._ease(alpha)
        for key in self.current:
            self.current[key] = self.start[key] + (self.target[key] - self.start[key]) * s

        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = self.JOINTS
        msg.position = [0.0] * 6 + [
            self.current["ls"], self.current["le"],
            self.current["rs"], self.current["re"],
        ]
        self.pub.publish(msg)

        if alpha >= 1.0 and self.stage_name != "HOLD":
            self._set_stage((self.index + 1) % len(self.STAGES))
        elif alpha >= 1.0 and self.stage_name == "HOLD":
            self._set_stage((self.index + 1) % len(self.STAGES))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DualArmCycle()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
