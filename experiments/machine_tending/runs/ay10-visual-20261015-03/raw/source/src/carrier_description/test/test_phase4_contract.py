"""Positive and failure cases for the retained Phase-4 interface."""

import copy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from phase4_contract import (  # noqa: E402
    CONTROL,
    DESCRIPTION,
    cycle_contract,
    expanded_urdf_contract,
    local_model_contract,
)


class TestPhase4Contract(unittest.TestCase):
    def setUp(self):
        self.flange = ET.parse(DESCRIPTION / "urdf/carrier_flange.xacro").getroot()
        self.dual = ET.parse(DESCRIPTION / "urdf/dual_arm.xacro").getroot()
        self.wrapper = ET.parse(
            DESCRIPTION / "urdf/ur5_with_test_tool.xacro"
        ).getroot()

    def test_positive_source_chain_order_and_limits(self):
        model = local_model_contract(self.flange, self.dual, self.wrapper)
        cycle = cycle_contract(
            (CONTROL / "carrier_control/dual_arm_cycle.py").read_text(),
            model["limits"],
        )
        self.assertEqual(cycle["joint_order"][6:], tuple(model["limits"]))
        self.assertEqual(cycle["stages"][0], "HOME")

    def test_negative_duplicate_link_rejected(self):
        broken = copy.deepcopy(self.dual)
        macro = next(broken.iter("{http://www.ros.org/wiki/xacro}macro"))
        ET.SubElement(macro, "link", {"name": "carrier_flange"})
        with self.assertRaisesRegex(ValueError, "duplicate local link"):
            local_model_contract(self.flange, broken, self.wrapper)

    def test_negative_broken_chain_rejected(self):
        broken = copy.deepcopy(self.wrapper)
        call = next(broken.iter("{http://www.ros.org/wiki/xacro}carrier_flange"))
        call.set("parent_link", "wrong_frame")
        with self.assertRaisesRegex(ValueError, "attach to tool0"):
            local_model_contract(self.flange, self.dual, broken)

    def test_negative_limit_violation_rejected(self):
        model = local_model_contract(self.flange, self.dual, self.wrapper)
        source = (CONTROL / "carrier_control/dual_arm_cycle.py").read_text()
        broken = source.replace("le=-1.20", "le=-2.00", 1)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            cycle_contract(broken, model["limits"])

    def test_negative_expanded_duplicate_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.urdf"
            path.write_text(
                '<robot name="broken"><link name="tool0"/>'
                '<link name="tool0"/></robot>', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "duplicate expanded link"):
                expanded_urdf_contract(path)

    def test_positive_isolated_viewer_has_one_joint_publisher(self):
        launch = (DESCRIPTION / "launch/view_dual_arm.launch.py").read_text()
        self.assertIn('include_workcell:=false', launch)
        self.assertIn('executable="dual_arm_cycle"', launch)
        self.assertNotIn('package="joint_state_publisher"', launch)
        self.assertNotIn('package="joint_state_publisher_gui"', launch)
        rviz = (DESCRIPTION / "rviz/dual_arm.rviz").read_text()
        self.assertIn('Fixed Frame: base_link', rviz)
        self.assertIn('Durability Policy: Transient Local', rviz)


if __name__ == "__main__":
    unittest.main()
