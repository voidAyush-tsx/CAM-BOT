"""AY-09 experiment logger positive, failure, and interruption tests."""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from carrier_control.metrics import (
    EVENT_FIELDS, SUMMARY_FIELDS, ExperimentLogger, TrialRecordError,
)


class FakeTime:
    def __init__(self):
        self.steady = 10.0
        self.wall_index = 0

    def monotonic(self):
        return self.steady

    def wall(self):
        self.wall_index += 1
        return f"2026-10-15T00:00:{self.wall_index:02d}+00:00"


class TestExperimentLogger(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "trials.csv"
        self.clock = FakeTime()
        self.logger = ExperimentLogger(
            self.path, "ay09-offline-test", "a" * 40,
            "config/machine_tending.json", {"gain": 1.0},
            wall_clock=self.clock.wall, steady_clock=self.clock.monotonic,
        )

    def finalize(self, success=True, **overrides):
        values = {
            "success": success,
            "failure_state": None if success else "LOAD_MACHINE",
            "failure_reason": None if success else "GOAL_REJECTED",
            "carrier_repositions": 2,
            "workpiece_final_state": (
                "FINISHED_AT_S5" if success else "HELD_RAW_AT_S2"
            ),
            "runtime_verified": False, "end_to_end_verified": False,
            "notes": "offline fixture; not measured",
        }
        values.update(overrides)
        return self.logger.finalize(**values)

    def test_positive_success_and_failure_samples_are_unique_and_parseable(self):
        first = self.logger.begin_trial("visual_simulation")
        self.logger.log_event(state="PICK_RAW", target="RAW_PICK",
                              reachability="REACHABLE",
                              decision="LOCAL_MANIPULATION",
                              action="S1_GRASP", result="COMPLETED")
        self.clock.steady += 1.25
        success = self.finalize()
        second = self.logger.begin_trial("visual_simulation")
        self.clock.steady += 0.5
        failure = self.finalize(success=False)
        self.assertNotEqual(first, second)
        self.assertGreaterEqual(success["cycle_time_s"], 0)
        self.assertEqual((failure["failure_state"], failure["failure_reason"]),
                         ("LOAD_MACHINE", "GOAL_REJECTED"))
        with self.path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row["trial_id"] for row in rows}), 2)
        with self.logger.event_path.open(encoding="utf-8") as stream:
            events = [json.loads(line) for line in stream]
        for trial_id in (first, second):
            selected = [event for event in events if event["trial_id"] == trial_id]
            self.assertEqual([event["sequence"] for event in selected],
                             list(range(len(selected))))
            elapsed = [event["monotonic_elapsed_s"] for event in selected]
            self.assertEqual(elapsed, sorted(elapsed))

    def test_negative_duplicate_final_record_is_not_written(self):
        trial_id = self.logger.begin_trial("visual_simulation", "fixed-id")
        self.finalize()
        with self.assertRaisesRegex(TrialRecordError, "no active trial"):
            self.finalize()
        with self.assertRaisesRegex(TrialRecordError, "duplicate trial_id"):
            self.logger.begin_trial("visual_simulation", trial_id)
        with self.path.open(newline="", encoding="utf-8") as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 1)

    def test_negative_failure_requires_context(self):
        self.logger.begin_trial("visual_simulation")
        with self.assertRaisesRegex(TrialRecordError, "failure context"):
            self.finalize(success=False, failure_state=None, failure_reason=None)

    def test_positive_interruption_is_preserved_and_marked_incomplete(self):
        trial_id = self.logger.begin_trial("visual_simulation", "interrupted-id")
        self.logger.log_event(state="LOAD_MACHINE", target="MACHINE_LOAD",
                              action="S3_LOAD", result="STARTED")
        self.assertEqual(self.logger.incomplete_trial_ids(), {trial_id})
        self.clock.steady += 0.2
        record = self.logger.finalize_incomplete(
            "KeyboardInterrupt", state="LOAD_MACHINE",
            workpiece_state="HELD_RAW_AT_S2",
        )
        self.assertEqual(record["status"], "INCOMPLETE")
        self.assertFalse(record["success"])
        self.assertEqual(record["failure_reason"], "KeyboardInterrupt")
        self.assertEqual(self.logger.incomplete_trial_ids(), set())

    def test_negative_invalid_duration_and_visual_claim_rejected(self):
        self.logger.begin_trial("visual_simulation")
        self.clock.steady = 9.0
        # Clock rollback is clamped for duration/event ordering.
        record = self.finalize()
        self.assertEqual(record["cycle_time_s"], 0.0)
        second = ExperimentLogger(
            Path(self.temporary.name) / "claims.csv", "claims", "b" * 40,
            "config.json", {}, wall_clock=self.clock.wall,
            steady_clock=self.clock.monotonic,
        )
        second.begin_trial("visual_simulation")
        with self.assertRaisesRegex(TrialRecordError, "visual simulation"):
            second.finalize(
                success=True, failure_state=None, failure_reason=None,
                carrier_repositions=0, workpiece_final_state="FINISHED_AT_S5",
                runtime_verified=True, end_to_end_verified=False, notes="invalid",
            )

    def test_positive_schema_assets_and_coordinator_signal_hooks(self):
        root = Path(__file__).resolve().parents[3]
        schema_root = root / "experiments/machine_tending/schema"
        trial_schema = json.loads((schema_root / "trial.schema.json").read_text())
        event_schema = json.loads((schema_root / "event.schema.json").read_text())
        self.assertEqual(tuple(trial_schema["required"]), SUMMARY_FIELDS)
        self.assertEqual(tuple(event_schema["required"]), EVENT_FIELDS)
        template = (root / "experiments/machine_tending/templates/trials.csv")
        with template.open(newline="", encoding="utf-8") as stream:
            self.assertEqual(tuple(next(csv.reader(stream))), SUMMARY_FIELDS)
        coordinator = (root / "src/carrier_control/carrier_control/"
                       "machine_tending_coordinator.py").read_text()
        self.assertIn("self.experiment_logger.begin_trial", coordinator)
        self.assertIn("self.experiment_logger.log_event", coordinator)
        self.assertIn("self.experiment_logger.finalize(", coordinator)
        self.assertIn("self.experiment_logger.finalize_incomplete(", coordinator)


if __name__ == "__main__":
    unittest.main()
