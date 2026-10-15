"""Offline positive and failure checks for the AY-03 controller launch gate."""

import json
from pathlib import Path
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from carrier_control.launch_preflight import validate_controller_launch  # noqa: E402
from carrier_control.workflow import WorkflowError  # noqa: E402


class TestLaunchPreflight(unittest.TestCase):
    def test_negative_supplied_plan_and_absent_stack_fail_closed(self):
        config = PACKAGE / "config/machine_tending.json"
        with self.assertRaisesRegex(WorkflowError, "not controller-validated"):
            validate_controller_launch(config, "/tmp/missing.launch.py")
        with self.assertRaisesRegex(WorkflowError, "cannot load plan"):
            validate_controller_launch("/tmp/missing-plan.json", "/tmp/missing.launch.py")

    def test_positive_validated_fixture_requires_existing_selected_bringup(self):
        plan = json.loads((PACKAGE / "config/machine_tending.json").read_text())
        for station in plan["stations"].values():
            station["controller_validated"] = True
            if station["carrier_joints"] is None:
                station["carrier_joints"] = [0.0] * 6
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "validated-test-fixture.json"
            config.write_text(json.dumps(plan))
            bringup = Path(directory) / "selected_controller.launch.py"
            bringup.write_text("# test fixture only\n")
            checked, selected = validate_controller_launch(config, str(bringup))
            self.assertEqual(checked["stations"]["S5_FINISHED"]["carrier_joints"], [0.0] * 6)
            self.assertEqual(selected, bringup)
            with self.assertRaisesRegex(WorkflowError, "controller_bringup_file"):
                validate_controller_launch(config, str(Path(directory) / "missing.launch.py"))


if __name__ == "__main__":
    unittest.main()
