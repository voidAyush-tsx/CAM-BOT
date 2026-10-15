# CAM-BOT status and evidence levels

Updated 2026-10-15. This is the only project status matrix. Each AY record,
including prior state, options, exact files, commands, results, limitations and
next action, is in the [versioned evidence ledger](ayush/ledger.json).

| Level | Meaning | Present evidence |
|---|---|---|
| Available code | Source, installed assets, offline contracts | Two installed Humble packages; Xacro/URDF; 48 regression tests ([log](evidence/AY-10/final_tests.log)) |
| Visual-only run | Live ROS/TF/RViz and visual adapter transitions | [AY-10 raw manifest](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/manifest.json), [probe](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/probe.log), [screenshot](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/rviz_runtime.png) |
| Actuated simulated run | Controller results and simulated feedback | **Unverified** here. Historical [Phase 1](progress/phase1-carrier-baseline.md) and [Phase 4](progress/phase_4.md) reports do not establish current controller operation. |
| Measured complete cycle | Declared timing boundary, complete attempted FSM, raw events | **Five visual cycles only**; [methods/results](../experiments/machine_tending/README.md) |

Workcell dimensions and visual carrier poses are temporary assumptions. The
reachability check is a geometric proxy, not IK or collision checking.
Controller targets S1–S4 are unvalidated and S5 has no taught target.

## AY task matrix

| ID | Status | Accepted scope and evidence |
|---|---|---|
| AY-01 | COMPLETE | Source integration; [inventory](evidence/AY-01/manifest.json), [runtime record](progress/AY01_AY09_RUNTIME_FINALIZATION.md) |
| AY-02 | COMPLETE | Packages/build/install; [clean build](evidence/AY-02/clean_build.log), [assets](evidence/AY-02/installed_assets.txt) |
| AY-03 | COMPLETE | Visual launch and gated controller entry; [launch](evidence/AY-03/launch_process.log), [graph](evidence/AY-03/ros_graph.txt) |
| AY-04 | COMPLETE | Five visual stations; [mapping](evidence/AY-04/station_mapping.md), [TF](evidence/AY-04/tf_station_inspection.txt) |
| AY-05 | COMPLETE | One-shot visual FSM; [tests](evidence/AY-05/test_outputs.log), [live events](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.events.jsonl) |
| AY-06 | COMPLETE | Visual coordination; [component verification](evidence/AY-06-08/verification.log), [probe](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/probe.log) |
| AY-07 | COMPLETE | Both-arm geometric proxy; [candidate matrix](evidence/AY-06-08/target_candidate_matrix.md), [probe](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/probe.log) |
| AY-08 | COMPLETE | Integrated visual cycle; [live manifest](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/manifest.json) |
| AY-09 | COMPLETE | Structured visual logger; [schema](evidence/AY-09/schema.md), [live CSV](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv) |
| AY-10 | COMPLETE | Five actual visual attempts; [acceptance](evidence/AY-10/acceptance.json), [raw manifest](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw/manifest.json) |
| AY-11 | COMPLETE | Event-derived visual metrics; [metrics](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw_analysis/metrics.json), [tests](evidence/AY-10/analysis_tests.log) |
| AY-12 | COMPLETE | Reproducible visual tables/plots; [artifacts](../experiments/machine_tending/runs/ay10-visual-20261015-03/raw_analysis/artifacts.json), [regeneration](evidence/AY-10/regeneration.log) |
| AY-13 | IN PROGRESS | Documentation and [G0–G10 cross-validation](evidence/AY-13/cross_validation/README.md) recorded in a [machine report](../artifacts/verification/cambot_build_report.json); controller gates and independent second-person repeat remain open. [Guide](ayush/README.md) |

AY-01…09 completion refers to visual ROS scope. Original AY-06–08 and AY-09
runtime capture directories are absent here; the later AY-10 raw dataset
independently shows their integrated paths and logger. It does not change the
older offline logs into runtime proof. The [Phase 4 narrative](progress/phase_4.md)
is retained with an archival caveat because its Gazebo/controller claims lack
supporting files in this checkout.

Historical Phase 1 UR5 and Phase 2 mass experiments have their original
[progress](progress/phase1-carrier-baseline.md) and
[experiment](progress/phase2-mass-sensitivity.md) reports. Phase 3 carrier
workspace characterization and Phase 6 placement analysis remain planned.
Phase 4/5 have visual integration and five measured visual cycles; selected
controllers, validated targets, grasp feedback, and actuated simulation remain
open. The installed carrier-control waypoint YAML is read by the legacy joint
cycle; root config is a mirror. See [decisions](DECISIONS.md) and
[clean-checkout steps](ayush/README.md).
