"""Cancellation observer regression checks; run in a sourced Humble shell."""

import copy
import unittest

from tools.ay05_ros_probe import validate_cancellation, validate_unreachable


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


class UnreachableProbeTests(unittest.TestCase):
    def test_exact_failure_and_recheck_are_required(self):
        terminal = {"event": "FAILURE", "cause": "RECHECK_STILL_UNREACHABLE",
                    "failure_step": "S1_APPROACH", "workpiece_state": "RAW_AT_S1"}
        decisions = [{"decision": "CARRIER_REPOSITION", "outcome": "PENDING"},
                     {"decision": "UNREACHABLE", "reason": "RECHECK_STILL_UNREACHABLE",
                      "outcome": "RECHECKED_AFTER_CARRIER"}]
        validate_unreachable(["HOME", "PICK_RAW"], terminal, decisions)
        for field, value in (("cause", "FINAL_TF_NOT_OBSERVED"), ("event", "SUCCESS"),
                             ("workpiece_state", "HELD_RAW_AT_S1")):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                validate_unreachable(["HOME", "PICK_RAW"], {**terminal, field: value}, decisions)
        for altered in ([], decisions[:1], decisions + [decisions[0]]):
            with self.assertRaises(RuntimeError):
                validate_unreachable(["HOME", "PICK_RAW"], terminal, copy.deepcopy(altered))
        with self.assertRaises(RuntimeError):
            validate_unreachable(["HOME", "PICK_RAW", "STAGE"], terminal, decisions)


if __name__ == "__main__":
    unittest.main()
