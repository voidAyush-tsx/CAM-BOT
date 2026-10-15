# AY-04 temporary visual workcell mapping

Canonical runtime configuration:
`src/carrier_control/config/machine_tending.json:5-59` (`workcell`). All
positions and dimensions are **metres**, RPY values **radians**, and station
poses are relative to `world`. The geometry is an explicit
`temporary_visual_simulation_assumption_not_measured`, not Tanmay's final
layout, manufacturing CAD, or a reachability study. The existing workcell
Xacro is reused, not replaced. Its direct-Xacro fallback values are tested
against the config, while both launch files override them from the installed
config at runtime.

| Station ID | TF frame | Origin XYZ (m, assumption) | Interaction targets | Workflow alias |
|---|---|---|---|---|
| RAW_INPUT | station_s1_raw | 0.75, 0.85, 0 | RAW_PICK | S1_RAW |
| STAGING_INSPECTION | station_s2_staging | 0.15, 1.05, 0 | STAGE_INSPECT | S2_STAGING |
| CNC_MACHINE | station_s3_machine | -0.65, 0.75, 0 | MACHINE_LOAD, MACHINE_UNLOAD | S3_MACHINE |
| OUTPUT_UNLOADING | station_s4_output | -0.75, -0.45, 0 | OUTPUT_UNLOAD | S4_OUTPUT |
| FINISHED_PART | station_s5_finished | 0.35, -0.95, 0 | FINISHED_PLACE | S5_FINISHED |

`MACHINE_LOAD` and `MACHINE_UNLOAD` are two interactions at the **same**
`CNC_MACHINE` physical station. `HOME` is a carrier configuration, **not** a
sixth physical station. `STAGE_INSPECT` does not claim a gripper release;
the current logical sequence transports a simulated held workpiece through
staging. `OUTPUT_UNLOAD` is the output station target after machine unload.

The single visual workpiece begins at world XYZ `(0.75, 0.85, 0.76)` and its
logical process phase follows `RAW → STAGED → IN_MACHINE → PROCESSED → FINISHED`.
Detailed `HELD_*` states remain for traceability. `simulated_attachment=true`
means a logical/visual hold only. There is no physical grasp or CNC
material-removal simulation. The task-state topic includes its named target,
target frame, and transformed visual world XYZ; config changes to station
pose update those values and Xacro frame placement without source edits.

Unknown geometry input still requested: Tanmay's final station poses,
coordinate convention, and dimensions. No measured values have been assumed.
The supplied dual-arm CAD ZIP was inspected separately; it does not establish
those five station placements. See `tanmay_zip_audit.md`.
