"""Ensure every ROS action wait is bounded and feedback-gated."""

import ast
from pathlib import Path
import unittest


PACKAGE = Path(__file__).parents[1] / "carrier_control"
ACTION_SOURCES = (
    PACKAGE / "machine_shop_joint_cycle.py",
    PACKAGE / "machine_shop_trajectory.py",
    PACKAGE / "machine_tending_coordinator.py",
)


def unbounded_wait_lines(source: str):
    tree = ast.parse(source)
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not isinstance(function, ast.Attribute):
            continue
        if function.attr != "spin_until_future_complete":
            continue
        if not any(keyword.arg == "timeout_sec" for keyword in node.keywords):
            lines.append(node.lineno)
    return lines


class TestActionSafety(unittest.TestCase):
    def test_positive_all_action_waits_have_explicit_timeouts_and_feedback_gates(self):
        for path in ACTION_SOURCES:
            source = path.read_text(encoding="utf-8")
            self.assertEqual(unbounded_wait_lines(source), [], path)
            self.assertIn("feedback", source.lower(), path)
        coordinator = ACTION_SOURCES[-1].read_text(encoding="utf-8")
        self.assertIn("cancel_goal_async", coordinator)
        self.assertIn("success result had no actual-position feedback", coordinator)

    def test_negative_scanner_detects_an_unbounded_action_wait(self):
        unsafe = "rclpy.spin_until_future_complete(node, future)\n"
        self.assertEqual(unbounded_wait_lines(unsafe), [1])


if __name__ == "__main__":
    unittest.main()
