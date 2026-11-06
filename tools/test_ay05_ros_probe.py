"""Cancellation observer regression checks; run in a sourced Humble shell."""

import unittest

from tools.ay05_ros_probe import validate_cancellation


class CancellationProbeTests(unittest.TestCase):
    def terminal(self, cause="CARRIER_VISUAL_UPDATE_CANCELLED_OR_TIMEOUT"):
        return {"event": "FAILURE", "cause": cause, "workpiece_state": "RAW_AT_S1"}

    def test_confirmed_coordinated_cancellation(self):
        validate_cancellation(["HOME", "PICK_RAW"], self.terminal(), True)

    def test_confirmed_scripted_cancellation(self):
        validate_cancellation(["HOME", "PICK_RAW"], self.terminal("CANCELLED"), True)

    def test_timeout_without_cancel_acknowledgement_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "early cancellation failed"):
            validate_cancellation(["HOME", "PICK_RAW"], self.terminal(), False)

    def test_unrelated_failure_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "early cancellation failed"):
            validate_cancellation(["HOME", "PICK_RAW"], self.terminal("TF_TIMEOUT"), True)

    def test_later_state_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "advanced"):
            validate_cancellation(["HOME", "PICK_RAW", "STAGE"], self.terminal(), True)

    def test_workpiece_advance_rejected(self):
        terminal = self.terminal()
        terminal["workpiece_state"] = "HELD_RAW_AT_S1"
        with self.assertRaisesRegex(RuntimeError, "advanced"):
            validate_cancellation(["HOME", "PICK_RAW"], terminal, True)


if __name__ == "__main__":
    unittest.main()
