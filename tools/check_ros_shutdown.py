#!/usr/bin/env python3
"""Require all visual launch children to finish cleanly, with no crash markers."""

from pathlib import Path
import re
import sys


def check_shutdown(log):
    for marker in ("Traceback", "process has died", "failed to terminate",
                   "escalating", "double free", "corrupted", "Segmentation fault"):
        if marker in log:
            raise ValueError(f"shutdown error: {marker}")
    for name in ("robot_state_publisher", "machine_tending_coordinator", "rviz2"):
        if not re.search(r"\[" + re.escape(name) + r"-\d+\]: process has finished cleanly", log):
            raise ValueError(f"no clean exit recorded for {name}")


if __name__ == "__main__":
    check_shutdown(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print("VISUAL_LAUNCH_SHUTDOWN_PASS: all three children exited cleanly")
