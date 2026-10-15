#!/usr/bin/env python3
"""Check maintained AY documentation against tracked paths and ROS packages."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = [
    "README.md",
    "docs/STATUS.md",
    "docs/ARCHITECTURE.md",
    "docs/DECISIONS.md",
    "docs/AY_TRACEABILITY.md",
    "docs/VALIDATION.md",
    "docs/ROADMAP.md",
    "docs/ayush/README.md",
    "docs/progress/phase_4.md",
    "docs/progress/phase3-carrier-flange.md",
    "docs/progress/phase1-carrier-baseline.md",
    "docs/evidence/AY-13/README.md",
    "docs/evidence/AY-13/cross_validation/README.md",
]
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
LAUNCH = re.compile(r"ros2\s+launch\s+carrier_description\s+([\w.-]+\.launch\.py)")
RUN = re.compile(r"ros2\s+run\s+carrier_control\s+([\w-]+)")
AY_ROW = re.compile(r"^\| (AY-\d{2}) \| (COMPLETE|IN PROGRESS|BLOCKED) \|", re.MULTILINE)


def local_link_errors(root=ROOT, documents=DOCUMENTS):
    errors = []
    for name in documents:
        source = root / name
        if not source.is_file():
            errors.append(f"missing document: {name}")
            continue
        for raw in LINK.findall(source.read_text(encoding="utf-8")):
            target = raw.split(" ", 1)[0].strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith(("#", "mailto:")):
                continue
            path = unquote(parsed.path)
            resolved = (source.parent / path).resolve()
            if not resolved.exists():
                errors.append(f"{name}: broken link {raw}")
    return errors


def ledger_errors(root=ROOT):
    errors = []
    ledger_path = root / "docs/ayush/ledger.json"
    status_path = root / "docs/STATUS.md"
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"invalid ledger: {exc}"]
    records = ledger.get("records", [])
    expected = {f"AY-{number:02d}" for number in range(1, 14)}
    ids = [row.get("id") for row in records]
    if len(ids) != 13 or set(ids) != expected:
        errors.append("ledger must contain each AY-01…AY-13 exactly once")
    statuses = AY_ROW.findall(status_path.read_text(encoding="utf-8"))
    status_ids = [item[0] for item in statuses]
    if len(status_ids) != 13 or set(status_ids) != expected:
        errors.append("status matrix must contain each AY-01…AY-13 exactly once")
    for row in records:
        ident = row.get("id", "<missing>")
        for key in ("requirement", "prior_state", "approach_options",
                    "files_changes", "tests", "evidence", "limitations", "next"):
            if not row.get(key):
                errors.append(f"{ident}: missing {key}")
        for key in ("files_changes", "evidence"):
            for path in row.get(key, []):
                if not (root / path).exists():
                    errors.append(f"{ident}: missing {key} path {path}")
        for test in row.get("tests", []):
            if not all(test.get(k) for k in ("command", "environment", "result")):
                errors.append(f"{ident}: incomplete test record")
    statuses_by_id = dict(statuses)
    records_by_id = {row.get("id"): row for row in records}
    for ident, disposition in statuses:
        if disposition == "COMPLETE" and not records_by_id.get(ident, {}).get("evidence"):
            errors.append(f"{ident}: completed without evidence")
    if statuses_by_id.get("AY-13") == "COMPLETE":
        peer = root / "docs/evidence/AY-13/independent_repeat.md"
        if not peer.is_file():
            errors.append("AY-13 marked complete without independent repeat")
    acceptance = root / "docs/evidence/AY-10/acceptance.json"
    data = json.loads(acceptance.read_text(encoding="utf-8"))
    if data["AY-10"]["trials"] < 5 or any(data.get(flag) for flag in
                                           ("runtime_verified", "end_to_end_verified")):
        errors.append("AY-10 qualification or evidence boundary changed")
    return errors


def source_contract_errors(root=ROOT, documents=DOCUMENTS):
    errors = []
    setup = ast.parse((root / "src/carrier_control/setup.py").read_text(encoding="utf-8"))
    executables = set()
    for node in ast.walk(setup):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if " = carrier_control." in node.value:
                executables.add(node.value.split(" = ", 1)[0])
    if not executables:
        errors.append("no console_scripts found in carrier_control setup.py")
    documented = set()
    launches = set()
    for name in documents:
        if name.startswith("docs/progress/"):
            continue  # Archival commands are historical, not today's contract.
        content = (root / name).read_text(encoding="utf-8")
        documented.update(RUN.findall(content))
        launches.update(LAUNCH.findall(content))
    for name in documented - executables:
        errors.append(f"documented ros2 run executable absent from setup.py: {name}")
    for name in launches:
        if not (root / "src/carrier_description/launch" / name).is_file():
            errors.append(f"documented launch file absent from source: {name}")
    for name in ("carrier_description", "carrier_control"):
        if not (root / "src" / name / "package.xml").is_file():
            errors.append(f"missing ROS package: {name}")
    return errors, executables, launches


def installed_errors(executables, launches):
    errors = []
    try:
        output = subprocess.check_output(
            ["ros2", "pkg", "executables", "carrier_control"], text=True
        )
        installed = {line.split()[1] for line in output.splitlines()
                     if len(line.split()) == 2 and line.split()[0] == "carrier_control"}
        for name in executables - installed:
            errors.append(f"console_script absent from installed package: {name}")
        prefix = subprocess.check_output(
            ["ros2", "pkg", "prefix", "carrier_description"], text=True
        ).strip()
        for name in launches:
            path = Path(prefix) / "share/carrier_description/launch" / name
            if not path.is_file():
                errors.append(f"launch absent from installed package: {name}")
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f"installed ROS inspection failed: {exc}")
    return errors


def inventory_errors(root=ROOT):
    """Check the G0 source map against all tracked source paths and bytes."""
    path = root / "docs/evidence/AY-13/cross_validation/source_inventory.json"
    if not path.is_file():
        return ["missing G0 source inventory"]
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("files", [])
    mapped = {item["path"]: item for item in rows}
    tracked = set(subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "src"], text=True
    ).splitlines())
    errors = []
    if set(mapped) != tracked or len(rows) != len(mapped):
        errors.append("G0 source inventory does not map each tracked src file once")
    for name, item in mapped.items():
        file_path = root / name
        if not file_path.is_file():
            errors.append(f"G0 source inventory missing path: {name}")
        elif hashlib.sha256(file_path.read_bytes()).hexdigest() != item.get("sha256"):
            errors.append(f"G0 source inventory hash mismatch: {name}")
    return errors


def check(root=ROOT, installed=False):
    errors = local_link_errors(root) + ledger_errors(root) + inventory_errors(root)
    contract_errors, executables, launches = source_contract_errors(root)
    errors.extend(contract_errors)
    if installed:
        errors.extend(installed_errors(executables, launches))
    for name, phrase in (
        ("docs/progress/phase_4.md", "Archival provenance note"),
        ("docs/progress/phase3-carrier-flange.md", "Archival provenance note"),
        ("docs/STATUS.md", "Actuated simulated run"),
        ("docs/STATUS.md", "geometric proxy"),
        ("docs/STATUS.md", "temporary assumptions"),
        ("docs/ayush/README.md", "Independent quick-start repeat"),
    ):
        if phrase not in (root / name).read_text(encoding="utf-8"):
            errors.append(f"{name}: missing evidence-scope marker")
    for name in ("README.md", "docs/AY_TRACEABILITY.md"):
        if AY_ROW.search((root / name).read_text(encoding="utf-8")):
            errors.append(f"{name}: duplicates authoritative AY status table")
    for name in ("README.md", "docs/ayush/README.md", "docs/VALIDATION.md"):
        if "colcon build --base-paths src" not in (root / name).read_text(encoding="utf-8"):
            errors.append(f"{name}: build must exclude archived source snapshots")
    config = json.loads(
        (root / "src/carrier_control/config/machine_tending.json").read_text(encoding="utf-8")
    )
    for station in ("S1_RAW", "S2_STAGING", "S3_MACHINE", "S4_OUTPUT", "S5_FINISHED"):
        if config["stations"][station].get("controller_validated") is not False:
            errors.append(f"{station}: controller validation claim changed")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true",
                        help="also compare source against sourced ROS install")
    args = parser.parse_args()
    errors = check(installed=args.installed)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("AY-13 DOC CHECK PASS: 13 statuses/ledger records, evidence paths, "
          "links and ROS source contracts" + (" and installed assets" if args.installed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
