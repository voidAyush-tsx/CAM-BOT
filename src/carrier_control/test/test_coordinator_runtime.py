"""ROS adapter regressions with deterministic TF and executor doubles."""

import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("rclpy", reason="coordinator adapter tests require ROS Humble")
from geometry_msgs.msg import TransformStamped  # noqa: E402
from carrier_control import machine_tending_coordinator as coordinator  # noqa: E402
from carrier_control.coordination_policy import CoordinationPolicy  # noqa: E402


def sample(stamp, x=1.0):
    message = TransformStamped()
    message.header.stamp.nanosec = stamp
    message.transform.translation.x = x
    message.transform.rotation.w = 1.0
    return message


class SettledTransformTests(unittest.TestCase):
    def run_samples(self, samples, cancelled=lambda: False):
        clock = [0.0]
        remaining = iter(samples)
        last = [samples[-1]]

        def lookup(*args):
            last[0] = next(remaining, last[0])
            return last[0]

        def spin(*args, **kwargs):
            clock[0] += 0.05

        node = SimpleNamespace(
            mode="visual_simulation", _publish_visual_joints=Mock(),
            plan={"workspace": {"tf_timeout_s": 0.5}},
            tf_buffer=SimpleNamespace(can_transform=lambda *args: True,
                                      lookup_transform=lookup),
        )
        with patch.object(coordinator.time, "monotonic", lambda: clock[0]), \
                patch.object(coordinator.rclpy, "spin_once", spin):
            return coordinator.MachineTendingCoordinator._settled_base_transform(
                node, 1.0, cancelled, not_before_ns=100
            )

    def test_final_pose_can_already_be_present_without_further_movement(self):
        self.assertEqual(
            ((1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
            self.run_samples([sample(n) for n in range(100, 104)]),
        )

    def test_old_samples_are_not_motion_completion(self):
        self.assertIsNone(self.run_samples([sample(n) for n in range(1, 20)]))

    def test_repeated_cached_sample_is_not_four_observations(self):
        self.assertIsNone(self.run_samples([sample(100)]))

    def test_moving_pose_does_not_escape_on_timeout(self):
        self.assertIsNone(self.run_samples([sample(100 + n, float(n))
                                           for n in range(20)]))

    def test_only_final_stable_samples_count(self):
        result = self.run_samples([sample(100, 0.0), sample(101, 0.5)] +
                                  [sample(n, 2.0) for n in range(102, 106)])
        self.assertEqual(2.0, result[0][0])

    def test_cancellation_does_not_return_partial_observation(self):
        calls = iter([False, False, True])
        self.assertIsNone(self.run_samples(
            [sample(100), sample(101)], lambda: next(calls, True)
        ))


class RecheckTests(unittest.TestCase):
    def run_recheck(self, final_transform):
        plan = json.loads((Path(__file__).resolve().parents[1] /
                           "config/machine_tending.json").read_text())
        before = ((10.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
        decisions = []
        node = SimpleNamespace(
            plan=plan, policy=CoordinationPolicy(), mode="visual_simulation",
            fsm=SimpleNamespace(trial_id="test", workpiece_state="RAW_AT_S1"),
            _current_base_transform=lambda *args: before,
            _settled_base_transform=lambda *args: final_transform,
            _move_carrier=Mock(return_value=True),
            _animate_carrier_visual=Mock(return_value=True),
            _emit_decision=lambda *args: decisions.append(args),
            get_clock=lambda: SimpleNamespace(now=lambda: SimpleNamespace(nanoseconds=100)),
            carrier_reposition_count=0,
        )
        outcome = coordinator.MachineTendingCoordinator._coordinate_target(
            node, {"name": "S1_APPROACH", "station": "S1_RAW",
                   "target": "RAW_PICK", "duration_s": 1.0}, 10.0, lambda: False
        )
        self.assertEqual(1, node.carrier_reposition_count)
        node._move_carrier.assert_called_once()
        return outcome, decisions

    def test_observed_unreachable_final_pose_is_classified_by_policy(self):
        outcome, decisions = self.run_recheck(
            ((11.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
        )
        self.assertFalse(outcome.success)
        self.assertEqual("RECHECK_STILL_UNREACHABLE", outcome.cause)
        self.assertEqual("UNREACHABLE", decisions[-1][4].decision)

    def test_absent_final_tf_remains_a_distinct_failure(self):
        outcome, decisions = self.run_recheck(None)
        self.assertFalse(outcome.success)
        self.assertEqual("FINAL_TF_NOT_OBSERVED", outcome.cause)
        self.assertEqual("FINAL_TF_NOT_OBSERVED", decisions[-1][-1])


class ShutdownTests(unittest.TestCase):
    def test_normal_shutdown_exceptions_destroy_node_without_traceback(self):
        for exception in (KeyboardInterrupt, coordinator.ExternalShutdownException):
            with self.subTest(exception=exception):
                node = Mock(auto_start=False)
                with patch.object(coordinator, "MachineTendingCoordinator", return_value=node), \
                        patch.object(coordinator.rclpy, "init"), \
                        patch.object(coordinator.rclpy, "ok", return_value=True), \
                        patch.object(coordinator.rclpy, "spin_once", side_effect=exception), \
                        patch.object(coordinator.rclpy, "shutdown") as shutdown:
                    coordinator.main()
                node.destroy_node.assert_called_once()
                shutdown.assert_called_once()

    def test_unexpected_executor_errors_still_fail(self):
        node = Mock(auto_start=False)
        with patch.object(coordinator, "MachineTendingCoordinator", return_value=node), \
                patch.object(coordinator.rclpy, "init"), \
                patch.object(coordinator.rclpy, "ok", return_value=True), \
                patch.object(coordinator.rclpy, "spin_once", side_effect=RuntimeError("fault")), \
                patch.object(coordinator.rclpy, "shutdown"):
            with self.assertRaisesRegex(RuntimeError, "fault"):
                coordinator.main()
        node.destroy_node.assert_called_once()
