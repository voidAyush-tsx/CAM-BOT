# AY-01…AY-09 runtime finalization — 2026-10-15

This record summarizes the final visual-runtime bring-up completed after the implementation commits through AY-09.

## Final result

The ROS 2 Humble visual system builds and launches the UR5 carrier, CAM-BOT flange/interface, dual-arm placeholder, five-station workcell and movable workpiece. The coordinated machine-tending probe completes the full one-shot workflow and returns HOME with the workpiece at `FINISHED_AT_S5`.

The successful coordinated probe observed both policy branches (`CARRIER_REPOSITION` and `LOCAL_MANIPULATION`) and five successful post-reposition reachability rechecks. The experiment logger subsequently produced a schema-valid visual-runtime sample (`validation: PASS`, 1 trial, 44 events).

## Runtime fixes finalized in this repository

1. ROS 2 Humble UR-description compatibility in `ur5_with_test_tool.xacro`.
2. ROS message list/`array.array` compatibility in visual joint-state publication.
3. Visual-only S1…S5 carrier-pose calibration; controller poses/validation remain unclaimed.
4. Exact final carrier-pose republish plus TF settling/recheck synchronization.
5. Capture-script compatibility with ROS setup files when Bash `set -u` is enabled.
6. Traceability updated through AY-09.

## Verification boundary

This is a **visual ROS simulation demonstration**. The successful probe explicitly reports `actuation_verified: false` and `grasp_verified: false`; the AY-09 summary likewise keeps `runtime_verified` and `end_to_end_verified` false. No claim is made here for physical robot actuation, collision-aware planning, IK validation, controller-backed bimanual actuation, or verified grasp feedback.

## Next work

AY-10 is the next task: collect at least five qualifying trials under the agreed experimental conditions. AY-11 and AY-12 should consume that dataset for metrics and plots/tables; AY-13 should then finalize the technical record.
