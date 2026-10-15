# Preliminary capture 01 — one actual successful trial

This capture made one actual attempt, which completed all FSM states and ended
with the workpiece at S5. It then stopped before starting the second trial:
a redundant immediate reset produced no fresh TF sample at the observer's
readiness gate. The attempted trial is preserved in the denominator (1/1
success for this capture); the readiness failure is a capture infrastructure
failure, not a second attempted FSM trial.

The original raw data, screenshot, source snapshot, logs, rosbag and checksums
are retained in `raw/`. Its derived results are in `raw_analysis/`. This capture
cannot qualify AY-10 by itself. Its successful cycle duration is 19.548801497 s
under the PICK_RAW-through-final-HOME definition. Do not pool it with capture
03: the runner/source snapshots differ.

Parent-only cleanup also left ROS child processes after this capture; capture
02's preflight detected them. The runner was repaired before capture 03 by
using one reset between attempts and stopping process groups.
