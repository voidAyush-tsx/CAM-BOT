"""Offline positive and failure tests for the machine-tending plan."""

import copy
import json
from pathlib import Path
import unittest

from carrier_control.workflow import (
    REQUIRED_STATIONS,
    WorkflowError,
    load_plan,
    simulate_state_sequence,
    stations_used_by,
    validate_plan,
)


CONFIG = Path(__file__).parents[1] / "config" / "machine_tending.json"


class TestWorkflow(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_positive_plan_has_five_named_stations_and_complete_sequence(self):
        plan = load_plan(CONFIG)
        self.assertEqual(tuple(plan["stations"]), REQUIRED_STATIONS)
        self.assertEqual(stations_used_by(plan["workflow"])[-1], "HOME")
        self.assertEqual(plan["workflow"][-2]["to_state"], "FINISHED_AT_S5")

    def test_negative_rejects_discontinuous_workpiece_state(self):
        broken = copy.deepcopy(self.plan)
        broken["workflow"][4]["from_state"] = "LOST_WORKPIECE"
        with self.assertRaisesRegex(WorkflowError, "state discontinuity"):
            validate_plan(broken)

    def test_negative_controller_mode_rejects_unvalidated_targets(self):
        with self.assertRaisesRegex(WorkflowError, "not controller-validated"):
            validate_plan(self.plan, require_controller_ready=True)

    def test_negative_rejects_out_of_limit_bimanual_pose(self):
        broken = copy.deepcopy(self.plan)
        broken["bimanual_poses"]["GRASP"][1] = -2.0
        with self.assertRaisesRegex(WorkflowError, "exceeds placeholder joint limits"):
            validate_plan(broken)

    def test_positive_state_sequence_reaches_finished(self):
        self.assertEqual(
            simulate_state_sequence(self.plan),
            (True, "FINISHED_AT_S5", None),
        )

    def test_negative_failed_dependency_does_not_advance_workpiece(self):
        self.assertEqual(
            simulate_state_sequence(self.plan, failed_step="S3_LOAD"),
            (False, "HELD_RAW_AT_S2", "S3_LOAD"),
        )


if __name__ == "__main__":
    unittest.main()
