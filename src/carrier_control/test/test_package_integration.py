"""Offline packaging and taught-waypoint contract checks for AY-02."""

import contextlib
import io
import os
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
CONTROL = ROOT / "src/carrier_control"
DESCRIPTION = ROOT / "src/carrier_description"
sys.path.insert(0, str(CONTROL))
from carrier_control.waypoints import load_waypoints, parse_waypoints  # noqa: E402


def capture_setup(package):
    captured = {}
    old_cwd = Path.cwd()
    try:
        os.chdir(package)
        with patch("setuptools.setup", side_effect=lambda **kwargs: captured.update(kwargs)):
            with contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(package / "setup.py"))
    finally:
        os.chdir(old_cwd)
    return captured


def validate_assets(package, setup_data, required):
    installed = {
        f"{destination}/{Path(source).name}": source
        for destination, sources in setup_data["data_files"]
        for source in sources
    }
    for source in installed.values():
        if not (package / source).is_file():
            raise ValueError(f"missing package source: {source}")
    absent = sorted(set(required) - installed.keys())
    if absent:
        raise ValueError(f"missing installed assets: {absent}")
    return installed


class TestPackageIntegration(unittest.TestCase):
    def test_positive_required_assets_entries_and_waypoints(self):
        description = capture_setup(DESCRIPTION)
        control = capture_setup(CONTROL)
        validate_assets(DESCRIPTION, description, {
            "share/carrier_description/rviz/dual_arm.rviz",
            "share/carrier_description/launch/dual_arm_demo.launch.py",
            "share/carrier_description/launch/machine_tending_controller.launch.py",
            "share/carrier_description/urdf/ur5_with_test_tool.xacro",
            "share/carrier_description/urdf/carrier_flange.xacro",
            "share/carrier_description/urdf/dual_arm.xacro",
        })
        validate_assets(CONTROL, control, {
            "share/carrier_control/config/waypoints.yaml",
            "share/carrier_control/config/machine_tending.json",
        })
        scripts = control["entry_points"]["console_scripts"]
        self.assertTrue(any(s.startswith("machine_shop_joint_cycle = ") for s in scripts))
        self.assertTrue(any(s.startswith("machine_tending_coordinator = ") for s in scripts))
        self.assertEqual((ROOT / "config/waypoints.yaml").read_bytes(),
                         (CONTROL / "config/waypoints.yaml").read_bytes())
        waypoints = load_waypoints(CONTROL / "config/waypoints.yaml")
        self.assertEqual(len(waypoints["P4"]), 6)
        self.assertEqual(waypoints["dwell_time"], 3.0)
        for package in (DESCRIPTION, CONTROL):
            root = ET.parse(package / "package.xml").getroot()
            dependencies = [node.text for node in root if node.tag.endswith("depend")]
            self.assertEqual(len(dependencies), len(set(dependencies)))

    def test_negative_missing_asset_and_invalid_waypoints_fail(self):
        with self.assertRaisesRegex(ValueError, "missing installed assets"):
            validate_assets(CONTROL, {"data_files": []},
                            {"share/carrier_control/config/waypoints.yaml"})
        valid = (CONTROL / "config/waypoints.yaml").read_text()
        with self.assertRaisesRegex(ValueError, "six finite joints"):
            parse_waypoints(valid.replace("[0.0, -1.5707, 0.0, 0.0, 0.0, 0.0]", "[0.0]"))
        with self.assertRaisesRegex(ValueError, "missing waypoint fields"):
            parse_waypoints(valid.replace("dwell_time: 3.0", ""))


if __name__ == "__main__":
    unittest.main()
