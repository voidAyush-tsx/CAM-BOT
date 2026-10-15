#!/usr/bin/env python3
"""Print a reproducible offline FSM transition trace; no ROS action is used."""

import json
from pathlib import Path

from carrier_control.machine_tending_fsm import MachineTendingFSM, StepOutcome


PLAN = json.loads((Path(__file__).resolve().parents[1] /
                   "src/carrier_control/config/machine_tending.json").read_text())


def run_case(label, fail_at=None):
    print(f"SCENARIO {label}")

    def notify(event):
        if event["event"] in ("ENTERED", "SUCCESS", "FAILURE"):
            parts = [event["event"], event["state"], event["workpiece_state"]]
            if event.get("cause"):
                parts.append(event["cause"])
            print(" ".join(parts))

    def adapter(step, deadline, cancelled):
        if step["name"] == fail_at:
            return StepOutcome(False, "INJECTED_ACTION_FAILURE")
        return StepOutcome(True)

    fsm = MachineTendingFSM(PLAN, notify=notify)
    fsm.start(label)
    print(fsm.run(adapter))


if __name__ == "__main__":
    run_case("success")
    run_case("load_failure", "S3_LOAD")
