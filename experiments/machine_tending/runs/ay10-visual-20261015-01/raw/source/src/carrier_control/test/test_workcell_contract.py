"""Offline AY-04 station, target, transform, and failure contracts."""

import copy
import json
import math
from pathlib import Path
import shlex
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from carrier_control.workcell_model import (
    STATION_IDS, WorkcellError, station_for_target, target_world_xyz,
    validate_workcell, xacro_station_arguments, render_workcell_xacro,
)
from carrier_control.workflow import PROCESS_PHASES, WorkflowError, validate_plan


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "src/carrier_control/config/machine_tending.json"
WRAPPER = ROOT / "src/carrier_description/urdf/ur5_with_test_tool.xacro"
XACRO = "{http://www.ros.org/wiki/xacro}"


class TestWorkcellContract(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.workcell = self.plan["workcell"]

    def test_positive_five_frames_targets_and_initial_workpiece(self):
        validate_plan(self.plan)
        self.assertEqual(tuple(self.workcell["stations"]), STATION_IDS)
        frames = [station["frame"] for station in self.workcell["stations"].values()]
        self.assertEqual(len(set(frames)), 5)
        self.assertEqual(target_world_xyz(self.workcell, "RAW_PICK"), [0.75, 0.85, 0.76])
        for step in self.plan["workflow"]:
            if step.get("target"):
                station_id = station_for_target(self.workcell, step["target"])
                if step["station"] is not None:
                    self.assertEqual(
                        self.plan["stations"][step["station"]]["workcell_station_id"],
                        station_id,
                    )
        phases = [PROCESS_PHASES[step["to_state"]] for step in self.plan["workflow"]]
        self.assertEqual(list(dict.fromkeys(phases)),
                         ["RAW", "STAGED", "IN_MACHINE", "PROCESSED", "FINISHED"])

    def test_positive_config_pose_changes_target_and_xacro_without_source_edit(self):
        baseline = target_world_xyz(self.workcell, "RAW_PICK")
        shifted = copy.deepcopy(self.workcell)
        shifted["stations"]["RAW_INPUT"]["pose_xyz_m"][0] += 0.2
        shifted["stations"]["RAW_INPUT"]["pose_rpy_rad"][2] = math.pi / 2
        shifted["stations"]["RAW_INPUT"]["targets"]["RAW_PICK"][0] = 0.1
        changed = target_world_xyz(shifted, "RAW_PICK")
        self.assertAlmostEqual(changed[0], baseline[0] + 0.2)
        self.assertAlmostEqual(changed[1], baseline[1] + 0.1)
        arguments = xacro_station_arguments(shifted)
        self.assertIn("station_s1_xyz:=0.95 0.85 0", arguments)
        self.assertTrue(any(argument.startswith("station_s1_rpy:=") for argument in arguments))
        self.assertEqual(len(shlex.split(" ".join(shlex.quote(a) for a in arguments))), 15)

    def test_positive_xacro_frame_names_and_fallback_match_config(self):
        wrapper = ET.parse(WRAPPER).getroot()
        arg_defaults = {
            element.attrib["name"]: element.attrib.get("default")
            for element in wrapper.findall(f"{XACRO}arg")
        }
        for station_id, slot in zip(STATION_IDS, ("s1", "s2", "s3", "s4", "s5")):
            station = self.workcell["stations"][station_id]
            for suffix, field in (("xyz", "pose_xyz_m"), ("rpy", "pose_rpy_rad"),
                                  ("size", "size_xyz_m")):
                self.assertEqual(
                    [float(v) for v in arg_defaults[f"station_{slot}_{suffix}"].split()],
                    station[field],
                )
        cell = ET.parse(ROOT / "src/carrier_description/urdf/machine_tending_cell.xacro").getroot()
        link_names = {element.attrib["name"] for element in cell.findall(".//link")}
        frames = {station["frame"] for station in self.workcell["stations"].values()}
        self.assertTrue(frames.issubset(link_names))

    def test_negative_missing_duplicate_or_nonfinite_station_rejected(self):
        broken = copy.deepcopy(self.workcell)
        del broken["stations"]["FINISHED_PART"]
        with self.assertRaisesRegex(WorkcellError, "exactly five"):
            validate_workcell(broken)
        broken = copy.deepcopy(self.workcell)
        broken["stations"]["FINISHED_PART"]["frame"] = broken["stations"]["RAW_INPUT"]["frame"]
        with self.assertRaisesRegex(WorkcellError, "duplicate station frame"):
            validate_workcell(broken)
        broken = copy.deepcopy(self.workcell)
        broken["stations"]["RAW_INPUT"]["pose_xyz_m"][0] = math.nan
        with self.assertRaisesRegex(WorkcellError, "finite"):
            validate_workcell(broken)
        broken_plan = copy.deepcopy(self.plan)
        broken_plan["workflow"][1]["target"] = "UNKNOWN_PICK"
        with self.assertRaisesRegex(WorkflowError, "unknown interaction target"):
            validate_plan(broken_plan)

    def test_positive_and_negative_xacro_render_is_bounded_and_parameterized(self):
        class Result:
            stdout = "<?xml version='1.0'?><robot name='test'/>"

        with patch("carrier_control.workcell_model.subprocess.run", return_value=Result()) as run:
            self.assertIn("<robot", render_workcell_xacro(WRAPPER, self.workcell))
            command = run.call_args.args[0]
            self.assertIn("station_s1_xyz:=0.75 0.85 0", command)
            self.assertEqual(run.call_args.kwargs["timeout"], 30)
        with patch("carrier_control.workcell_model.subprocess.run",
                   side_effect=OSError("missing xacro")):
            with self.assertRaisesRegex(WorkcellError, "Xacro expansion failed"):
                render_workcell_xacro(WRAPPER, self.workcell)


if __name__ == "__main__":
    unittest.main()
