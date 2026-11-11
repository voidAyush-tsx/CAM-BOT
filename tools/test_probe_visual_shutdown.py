"""Negative fixtures for durable interrupted-trial acceptance."""

import unittest

from tools.probe_visual_shutdown import validate_trials


class ShutdownTrialTests(unittest.TestCase):
    def test_idle_has_no_trials(self):
        validate_trials([], "idle")

    def test_idle_rejects_any_trial(self):
        with self.assertRaises(ValueError):
            validate_trials([{"status": "INCOMPLETE"}], "idle")

    def test_active_accepts_one_incomplete_raw_trial(self):
        validate_trials([{"status": "INCOMPLETE", "success": "False",
                          "workpiece_final_state": "RAW_AT_S1"}], "active")

    def test_active_rejects_success_missing_fields_and_wrong_workpiece(self):
        good = {"status": "INCOMPLETE", "success": "False",
                "workpiece_final_state": "RAW_AT_S1"}
        for rows in ([], [good, good], [{}], [dict(good, status="SUCCESS")],
                     [dict(good, success="True")],
                     [dict(good, workpiece_final_state="FINISHED_AT_S5")]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_trials(rows, "active")


if __name__ == "__main__":
    unittest.main()
