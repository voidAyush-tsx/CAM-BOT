"""Check generated report completeness and evidence guards."""

from pathlib import Path
import unittest
from unittest.mock import patch

from tools import generate_build_report as report_module


class BuildReportTests(unittest.TestCase):
    def test_report_has_all_gates_tasks_and_real_paths(self):
        report = report_module.build_report()
        self.assertEqual(13, len(report["ids"]))
        self.assertEqual(11, len(report["gates"]))
        self.assertEqual(5, report["trials"]["qualifying_raw_attempted"])
        self.assertEqual("NOT RUN",
                         report["end_to_end_scenarios"]["S4_controller_rejection"]["status"])
        self.assertEqual("NOT VERIFIED", report["ids"][-1]["outcome"])
        for task in report["ids"]:
            for name in task["changed_files"] + task["evidence"]:
                self.assertTrue((report_module.ROOT / name).exists(), name)
        for name in report["results"]["plots"]:
            self.assertGreater((report_module.ROOT / name).stat().st_size, 0)

    def test_changed_raw_qualification_cannot_generate_report(self):
        original = report_module.read_json

        def changed(path):
            data = original(path)
            if path == "docs/evidence/AY-10/acceptance.json":
                data["AY-10"]["trials"] = 4
            return data

        with patch.object(report_module, "read_json", side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, "five-trial"):
                report_module.build_report()


if __name__ == "__main__":
    unittest.main()
