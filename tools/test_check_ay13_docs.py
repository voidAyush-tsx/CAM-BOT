"""Focused negative fixtures for AY-13 documentation checks."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "check_ay13_docs", Path(__file__).with_name("check_ay13_docs.py")
)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class DocCheckTests(unittest.TestCase):
    def test_broken_local_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("[missing](absent.md)\n", encoding="utf-8")
            self.assertIn(
                "broken link",
                " ".join(CHECK.local_link_errors(root, ["README.md"])),
            )

    def test_valid_local_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("[exists](doc.md)\n", encoding="utf-8")
            (root / "doc.md").write_text("ok\n", encoding="utf-8")
            self.assertEqual([], CHECK.local_link_errors(root, ["README.md"]))

    def test_missing_and_duplicate_ay_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/ayush").mkdir(parents=True)
            (root / "docs/evidence/AY-10").mkdir(parents=True)
            (root / "docs/evidence/AY-10/acceptance.json").write_text(
                json.dumps({"AY-10": {"trials": 5},
                            "runtime_verified": False,
                            "end_to_end_verified": False}), encoding="utf-8"
            )
            rows = []
            for number in range(1, 14):
                ident = f"AY-{number:02d}"
                rows.append({
                    "id": ident, "requirement": "r", "prior_state": "p",
                    "approach_options": "a", "files_changes": ["docs/STATUS.md"],
                    "tests": [{"command": "true", "environment": "fixture", "result": "PASS"}],
                    "evidence": ["docs/STATUS.md"], "limitations": "l", "next": "n",
                })
            (root / "docs/ayush/ledger.json").write_text(
                json.dumps({"records": rows}), encoding="utf-8"
            )
            status = root / "docs/STATUS.md"
            status.write_text(
                "\n".join(f"| AY-{n:02d} | {'IN PROGRESS' if n == 13 else 'COMPLETE'} | proof |"
                          for n in range(1, 14)),
                encoding="utf-8",
            )
            self.assertEqual([], CHECK.ledger_errors(root))
            status.write_text(status.read_text(encoding="utf-8") +
                              "\n| AY-01 | COMPLETE | duplicate |", encoding="utf-8")
            self.assertIn("exactly once", " ".join(CHECK.ledger_errors(root)))
            status.write_text("| AY-01 | COMPLETE | proof |\n", encoding="utf-8")
            self.assertIn("exactly once", " ".join(CHECK.ledger_errors(root)))
            rows[0]["evidence"] = []
            (root / "docs/ayush/ledger.json").write_text(
                json.dumps({"records": rows}), encoding="utf-8"
            )
            self.assertIn("missing evidence", " ".join(CHECK.ledger_errors(root)))

    def test_phantom_launch_and_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            setup = root / "src/carrier_control/setup.py"
            setup.parent.mkdir(parents=True)
            setup.write_text("console_scripts = ['real = carrier_control.node:main']\n",
                             encoding="utf-8")
            (root / "src/carrier_description").mkdir(parents=True)
            for package in ("carrier_control", "carrier_description"):
                (root / "src" / package / "package.xml").write_text("<package/>",
                                                                      encoding="utf-8")
            (root / "README.md").write_text(
                "ros2 run carrier_control phantom\n"
                "ros2 launch carrier_description phantom.launch.py\n",
                encoding="utf-8",
            )
            errors, _, _ = CHECK.source_contract_errors(root, ["README.md"])
            self.assertIn("phantom", " ".join(errors))

    def test_source_inventory_detects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src/carrier_control/node.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "src"], check=True)
            import hashlib
            inventory = root / "docs/evidence/AY-13/cross_validation/source_inventory.json"
            inventory.parent.mkdir(parents=True)
            inventory.write_text(json.dumps({"files": [{
                "path": "src/carrier_control/node.py",
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }]}), encoding="utf-8")
            self.assertEqual([], CHECK.inventory_errors(root))
            source.write_text("value = 2\n", encoding="utf-8")
            self.assertIn("hash mismatch", " ".join(CHECK.inventory_errors(root)))


if __name__ == "__main__":
    unittest.main()
