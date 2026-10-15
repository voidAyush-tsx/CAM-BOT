"""Offline launch contract tests that do not pretend ROS is available."""

import ast
from pathlib import Path
import unittest


LAUNCH = Path(__file__).parents[1] / "launch" / "dual_arm_demo.launch.py"
CONTROLLER_LAUNCH = Path(__file__).parents[1] / "launch" / "machine_tending_controller.launch.py"


class TestLaunchContract(unittest.TestCase):
    def test_positive_launch_is_python_and_starts_required_visual_nodes(self):
        text = LAUNCH.read_text(encoding="utf-8")
        ast.parse(text)
        self.assertIn('package="robot_state_publisher"', text)
        self.assertIn('executable="machine_tending_coordinator"', text)
        self.assertIn('package="rviz2"', text)
        self.assertIn('"mode": "visual_simulation"', text)
        self.assertIn('"config_file": config_file', text)
        self.assertIn('"results_file": results_file', text)

    def test_negative_launch_does_not_start_competing_joint_publishers(self):
        text = LAUNCH.read_text(encoding="utf-8")
        self.assertNotIn('executable="dual_arm_cycle"', text)
        self.assertNotIn('package="joint_state_publisher"', text)
        self.assertNotIn('package="joint_state_publisher_gui"', text)
        self.assertNotIn('DeclareLaunchArgument("mode"', text)

    def test_positive_controller_entry_point_gates_inputs_and_shutdown(self):
        text = CONTROLLER_LAUNCH.read_text(encoding="utf-8")
        ast.parse(text)
        self.assertIn("validate_controller_launch(config_file, controller_file)", text)
        self.assertIn("IncludeLaunchDescription", text)
        self.assertIn('"mode": "controller"', text)
        self.assertIn("OnProcessExit", text)
        self.assertIn("Shutdown", text)
        self.assertIn('package="robot_state_publisher"', text)
        self.assertIn('package="rviz2"', text)

    def test_negative_controller_launch_has_no_competing_carrier_writer(self):
        text = CONTROLLER_LAUNCH.read_text(encoding="utf-8")
        self.assertNotIn('executable="dual_arm_cycle"', text)
        self.assertNotIn('package="joint_state_publisher"', text)
        self.assertNotIn('package="joint_state_publisher_gui"', text)


if __name__ == "__main__":
    unittest.main()
