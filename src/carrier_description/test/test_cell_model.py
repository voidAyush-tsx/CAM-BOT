"""Static positive and negative tests for the visual cell Xacro contract."""

from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


URDF_DIR = Path(__file__).parents[1] / "urdf"
XACRO = "{http://www.ros.org/wiki/xacro}"


class TestCellModel(unittest.TestCase):
    def test_positive_cell_has_five_stations_and_movable_workpiece(self):
        root = ET.parse(URDF_DIR / "machine_tending_cell.xacro").getroot()
        links = {element.attrib["name"] for element in root.findall(".//link")}
        self.assertTrue({
            "station_s1_raw",
            "station_s2_staging",
            "station_s3_machine",
            "station_s4_output",
            "station_s5_finished",
            "workpiece",
        }.issubset(links))
        joints = {
            element.attrib["name"]: element.attrib["type"]
            for element in root.findall(".//joint")
        }
        self.assertEqual(joints["workpiece_x_joint"], "prismatic")
        self.assertEqual(joints["workpiece_y_joint"], "prismatic")
        self.assertEqual(joints["workpiece_z_joint"], "prismatic")

    def test_positive_ur5_wrapper_preserves_tool0_attachment_contract(self):
        text = (URDF_DIR / "ur5_with_test_tool.xacro").read_text(encoding="utf-8")
        self.assertIn('<xacro:ur_robot', text)
        self.assertNotIn('force_abs_paths=', text)
        self.assertIn('parent_link="tool0"', text)
        self.assertIn('parent_link="carrier_flange_interface"', text)

    def test_negative_malformed_xml_is_rejected(self):
        with self.assertRaises(ET.ParseError):
            ET.fromstring('<robot><link name="broken"></robot>')


if __name__ == "__main__":
    unittest.main()
