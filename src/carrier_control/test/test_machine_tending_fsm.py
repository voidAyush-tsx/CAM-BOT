"""AY-05 offline FSM unit and adapter-integration tests."""

import json
from pathlib import Path
import unittest

from carrier_control.machine_tending_fsm import (
    FSMError, MAX_RETRIES, MachineTendingFSM, STATE_STEPS, StepOutcome,
)


CONFIG = Path(__file__).resolve().parents[1] / "config/machine_tending.json"
COORDINATOR = (
    Path(__file__).resolve().parents[1] /
    "carrier_control/machine_tending_coordinator.py"
)


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


class TestMachineTendingFSM(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.clock = FakeClock()
        self.events = []
        self.fsm = MachineTendingFSM(self.plan, self.events.append, self.clock)

    def test_positive_one_shot_order_and_terminal_success(self):
        executed = []

        def adapter(step, deadline, cancelled):
            executed.append(step["name"])
            self.assertGreater(deadline, self.clock())
            self.assertFalse(cancelled())
            self.clock.value += 0.1
            return StepOutcome(True)

        self.fsm.start("trial-001")
        outcome = self.fsm.run(adapter)
        self.assertTrue(outcome.success)
        self.assertEqual(outcome.terminal, "SUCCESS")
        self.assertEqual(outcome.workpiece_state, "FINISHED_AT_S5")
        self.assertEqual(executed, [name for _, names in STATE_STEPS for name in names])
        self.assertEqual(
            [event["state"] for event in self.events if event["event"] == "ENTERED"],
            [name for name, _ in STATE_STEPS],
        )
        self.assertTrue(all(event["trial_id"] == "trial-001" for event in self.events))
        self.assertTrue(all(event["timestamp_utc"] for event in self.events))
        with self.assertRaisesRegex(FSMError, "reset first"):
            self.fsm.start("trial-002")

    def test_positive_reset_then_new_start(self):
        self.fsm.start("trial-001")
        self.fsm.run(lambda step, deadline, cancelled: StepOutcome(True))
        self.fsm.reset()
        self.assertEqual(self.fsm.status, "IDLE")
        self.assertEqual(self.fsm.workpiece_state, "RAW_AT_S1")
        self.fsm.start("trial-002")
        self.assertEqual(self.fsm.trial_id, "trial-002")

    def test_negative_failed_load_stops_before_dwell_unload_or_place(self):
        executed = []

        def adapter(step, deadline, cancelled):
            executed.append(step["name"])
            if step["name"] == "S3_LOAD":
                return StepOutcome(False, "INJECTED_ACTION_FAILURE")
            return StepOutcome(True)

        self.fsm.start("failure-at-load")
        result = self.fsm.run(adapter)
        self.assertEqual(result.terminal, "FAILURE")
        self.assertEqual(result.failure_state, "LOAD_MACHINE")
        self.assertEqual(result.failure_step, "S3_LOAD")
        self.assertEqual(result.cause, "INJECTED_ACTION_FAILURE")
        self.assertEqual(result.workpiece_state, "HELD_RAW_AT_S2")
        self.assertNotIn("S3_RELEASE", executed)
        self.assertNotIn("MACHINE_DWELL", executed)
        self.assertNotIn("S4_UNLOAD", executed)
        self.assertNotIn("S5_PLACE", executed)
        self.assertEqual(executed.count("S3_LOAD"), 1)
        self.assertEqual(MAX_RETRIES, 0)

    def test_negative_timeout_prevents_workpiece_advance(self):
        def adapter(step, deadline, cancelled):
            if step["name"] == "S1_GRASP":
                self.clock.value = deadline + 0.01
            return StepOutcome(True)

        self.fsm.start("timeout")
        result = self.fsm.run(adapter)
        self.assertEqual((result.failure_state, result.failure_step, result.cause),
                         ("PICK_RAW", "S1_GRASP", "STATE_TIMEOUT"))
        self.assertEqual(result.workpiece_state, "RAW_AT_S1")

    def test_negative_early_cancellation_and_invalid_lifecycle(self):
        with self.assertRaisesRegex(FSMError, "requires start"):
            self.fsm.run(lambda step, deadline, cancelled: StepOutcome(True))
        self.fsm.start("cancelled")
        with self.assertRaisesRegex(FSMError, "cancel first"):
            self.fsm.reset()
        executed = []

        def adapter(step, deadline, cancelled):
            executed.append(step["name"])
            self.fsm.cancel()
            return StepOutcome(True)

        result = self.fsm.run(adapter)
        self.assertEqual((result.terminal, result.cause), ("FAILURE", "CANCELLED"))
        self.assertEqual(result.workpiece_state, "RAW_AT_S1")
        self.assertEqual(executed, ["HOME_START"])

    def test_negative_cancel_before_first_action_and_invalid_retry_policy(self):
        self.fsm.start("cancel-before-action")
        self.fsm.cancel()
        executed = []
        result = self.fsm.run(lambda step, deadline, cancelled: executed.append(step))
        self.assertEqual((result.terminal, result.cause), ("FAILURE", "CANCELLED"))
        self.assertEqual(executed, [])
        broken = json.loads(CONFIG.read_text(encoding="utf-8"))
        broken["fsm"]["retry_count"] = 1
        with self.assertRaisesRegex(FSMError, "automatic retries are disabled"):
            MachineTendingFSM(broken)

    def test_positive_ros_adapter_contract_is_feedback_gated_and_interruptible(self):
        source = COORDINATOR.read_text(encoding="utf-8")
        for service in ('"~/start"', '"~/reset"', '"~/cancel"'):
            self.assertIn(service, source)
        self.assertIn("def _execute_fsm_step", source)
        self.assertIn("def _wait_machine_dwell", source)
        self.assertIn("success result had no actual-position feedback", source)
        self.assertNotIn("time.sleep(", source)


if __name__ == "__main__":
    unittest.main()
