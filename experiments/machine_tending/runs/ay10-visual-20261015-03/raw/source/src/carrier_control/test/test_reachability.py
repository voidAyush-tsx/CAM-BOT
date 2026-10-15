"""AY-07 geometric-proxy positive and negative boundaries."""

import copy
import json
import math
from pathlib import Path
import unittest

from carrier_control.reachability import evaluate_reachability, validate_workspace


CONFIG = Path(__file__).resolve().parents[1] / "config/machine_tending.json"
IDENTITY = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))


class TestReachability(unittest.TestCase):
    def setUp(self):
        self.workspace = json.loads(CONFIG.read_text())["workspace"]

    def test_positive_center_and_inclusive_boundary(self):
        center = evaluate_reachability((0, 0.25, 0.05), IDENTITY, self.workspace)
        boundary = evaluate_reachability((0.02, 0.25, 0.05), IDENTITY,
                                         self.workspace)
        self.assertEqual(center.status, "REACHABLE")
        self.assertEqual(boundary.status, "REACHABLE")
        self.assertEqual(center.arms, {"left": True, "right": True})

    def test_negative_just_outside_and_both_arm_requirement(self):
        outside = evaluate_reachability((0.020001, 0.25, 0.05), IDENTITY,
                                        self.workspace)
        left = evaluate_reachability((-0.22, 0.25, 0.05), IDENTITY,
                                     self.workspace, "left")
        both = evaluate_reachability((-0.22, 0.25, 0.05), IDENTITY,
                                     self.workspace, "both")
        self.assertEqual(outside.status, "UNREACHABLE")
        self.assertEqual(left.status, "REACHABLE")
        self.assertEqual(both.status, "UNREACHABLE")

    def test_positive_rotated_and_translated_tf_changes_local_result(self):
        yaw90 = ((1.0, 2.0, 0.0),
                 (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5)))
        result = evaluate_reachability((0.75, 2.0, 0.05), yaw90,
                                       self.workspace, "left")
        self.assertEqual(result.status, "REACHABLE")
        self.assertAlmostEqual(result.local_xyz_m[0], 0.0, places=6)
        self.assertAlmostEqual(result.local_xyz_m[1], 0.25, places=6)
        self.assertEqual(evaluate_reachability((0.75, 2.0, 0.05), IDENTITY,
                                               self.workspace).status, "UNREACHABLE")

    def test_negative_missing_nan_tf_target_and_invalid_units(self):
        for target, tf, reason in (
            ((0, 0.25, 0.05), None, "MISSING_OR_INVALID_TF"),
            ((math.nan, 0.25, 0.05), IDENTITY, "INVALID_TARGET"),
            ((0, 0.25, 0.05), ((0, math.nan, 0), IDENTITY[1]),
             "MISSING_OR_INVALID_TF"),
            ((0, 0.25, 0.05), ((0, 0, 0), (0, 0, 0, 0)),
             "INVALID_TF_QUATERNION"),
        ):
            result = evaluate_reachability(target, tf, self.workspace)
            self.assertEqual((result.status, result.reason), ("UNKNOWN", reason))
        invalid = copy.deepcopy(self.workspace)
        invalid["units"] = "mm"
        with self.assertRaisesRegex(ValueError, "units must be m"):
            validate_workspace(invalid)


if __name__ == "__main__":
    unittest.main()
