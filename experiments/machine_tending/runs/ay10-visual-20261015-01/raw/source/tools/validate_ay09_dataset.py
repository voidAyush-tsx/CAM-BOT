#!/usr/bin/env python3
"""Validate one AY-09 CSV/JSONL dataset without ROS dependencies."""

import argparse
import csv
import json
from pathlib import Path

from carrier_control.metrics import (
    ExperimentLogger, validate_event, validate_trial_record,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("summary_csv", type=Path)
    args = parser.parse_args()
    event_path = args.summary_csv.with_suffix(".events.jsonl")
    with args.summary_csv.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise RuntimeError("dataset has no summary rows")
    ids = [row["trial_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate trial IDs in summary")
    for raw in rows:
        record = dict(raw)
        record["cycle_time_s"] = float(record["cycle_time_s"])
        record["carrier_repositions"] = int(record["carrier_repositions"])
        for field in ("success", "runtime_verified", "end_to_end_verified"):
            record[field] = record[field].lower() == "true"
        for field in ("failure_state", "failure_reason"):
            record[field] = record[field] or None
        validate_trial_record(record)
    by_trial = {}
    with event_path.open(encoding="utf-8") as stream:
        for line in stream:
            event = json.loads(line)
            validate_event(event)
            by_trial.setdefault(event["trial_id"], []).append(event)
    if set(ids) - set(by_trial):
        raise RuntimeError("summary trial missing event stream")
    for trial_id, events in by_trial.items():
        sequences = [event["sequence"] for event in events]
        elapsed = [event["monotonic_elapsed_s"] for event in events]
        if sequences != list(range(len(events))) or elapsed != sorted(elapsed):
            raise RuntimeError(f"events out of order for {trial_id}")
        if events[-1]["action"] != "FINALIZE":
            raise RuntimeError(f"trial {trial_id} remains incomplete")
    # Reuse the logger's dangling-start detector against the same paths.
    probe = ExperimentLogger(args.summary_csv, "validation", "UNKNOWN",
                             "validation-only", {})
    if probe.incomplete_trial_ids():
        raise RuntimeError(f"incomplete trials: {probe.incomplete_trial_ids()}")
    print(json.dumps({"validation": "PASS", "trials": len(rows),
                      "events": sum(map(len, by_trial.values()))}))


if __name__ == "__main__":
    main()
