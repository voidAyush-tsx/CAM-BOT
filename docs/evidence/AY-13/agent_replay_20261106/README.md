# Agent-run Humble reproduction — 2026-11-06

Codex executed a fresh clone of merged `main` at
`63db6539fb4a3cab311fb2f7ae09ec100ad304f8` in Ubuntu 22.04 / ROS 2 Humble.
The user requested continued technical execution because another team member
was unavailable. This record is **not an independent human sign-off**.
AY-13 remains IN PROGRESS; the replay also exposed open runtime diagnostics.

The source checkout was `/tmp/cambot-ay13-replay-20261106`, mounted inside
Docker at `/workspace/CAM-BOT`. Git LFS was hydrated and the checkout was clean
before building. The image used the pinned base in
[Dockerfile.humble](../../../../tools/cloud/Dockerfile.humble), with package
versions in [environment.txt](environment.txt). Xvfb and software rendering
provided RViz's display. ROS domain 96 was local to the container.

## Results

| Check | Observed result | Evidence |
|---|---|---|
| rosdep | PASS: all system dependencies satisfied | [log](rosdep-check.log) |
| Scoped Colcon build | PASS: two packages | [log](colcon-build.log) |
| Scoped Colcon tests | 59 results, 0 errors/failures, 2 skips (existing copyright-header skips) | [summary](colcon-test-result.log), [execution](colcon-test.log) |
| Installed documentation/assets | PASS | [log](installed-doc-check.log) |
| Xacro/URDF | PASS: expanded model parsed successfully | [log](check-urdf.log) |
| Analysis tests | 14 passed | [log](analysis-tests.log) |
| Documentation/report fixtures | 7 passed | [log](doc-report-tests.log) |
| Archived five-trial qualification | PASS; no new batch statistics substituted | [log](analysis-regeneration.log) |
| Published analysis reproduction | All seven outputs byte-match with Matplotlib 3.5.1 | [comparison](analysis-comparison.json) |
| New coordinated visual cycle | PASS: full FSM, SUCCESS, FINISHED_AT_S5, both decisions, 5 TF rechecks | [probe](visual-success/probe.jsonl) |
| Joint-state authority | Exactly 1 publisher | [inspection](visual-success/joint_state_publishers.txt) |
| Injected S3_LOAD failure | PASS: stops at LOAD_MACHINE, workpiece remains HELD_RAW_AT_S2 | [probe](load_failure/probe.jsonl) |
| Early coordinated cancellation | PASS after observer repair: service acknowledged, stops in PICK_RAW, workpiece remains RAW_AT_S1 | [probe](cancelled-confirmed/probe.jsonl) |
| Controller entry | Expected rejection: S1_RAW target not controller-validated; not controller execution | [log](controller-gate.log) |
| Impossible proxy target | Safety stop observed after one reposition; expected UNREACHABLE recheck classification **FAILS** | [probe](unreachable/probe.jsonl) |
| Shutdown | No residual ROS nodes; graceful shutdown **not established** | [node list](visual-success/residual_nodes.txt), [launch](visual-success/launch.log) |
| New tooling regressions | 11 passed in Humble | [log](tool-regressions.log) |
| Legacy static verifier after repair | 26/26 passed | [JSON](static-verification-humble.json) |

## Repairs and failed diagnostics

The package verifier previously required the literal `glob('config/*')` text.
It now checks evaluated setup metadata and file existence. Five tests cover
helper-based setup, missing declarations/files and working-directory recovery.

The old cancellation observer accepted only reasons beginning with `CANCEL`.
Coordinated visual mode returned `CARRIER_VISUAL_UPDATE_CANCELLED_OR_TIMEOUT`
after an actual cancellation, causing the [original observer failure](cancelled-retry/probe.jsonl).
The repaired observer requires a successful cancellation-service reply, a
failure terminal, the exact HOME/PICK_RAW state sequence and unchanged raw
workpiece state; six tests reject unacknowledged timeouts, unrelated failures
and unwanted progress. Application FSM/coordinator code was not changed.
An earlier [runner attempt](cancelled/launch.log) passed an invalid empty launch
argument and started no trial; the helper was corrected before the retry.

The impossible-target configuration changes only the copied arm proxy radii
to 0.001 m. [Configuration](unreachable-config.json) and the strict observer
are retained. The coordinator's first post-motion TF was already the final
pose, but `_settled_base_transform(previous=first_after)` requires another
changed pose. It therefore reported `FINAL_TF_NOT_OBSERVED`, despite an
observed changed world-to-base transform, before emitting the expected
`RECHECK_STILL_UNREACHABLE` decision. The trial stopped within its bound at
RAW_AT_S1 after one reposition; the stricter classification assertion failed.
This requires a focused fresh-TF/settling regression repair, not looser proxy
bounds or a passing replacement assertion.

Normal capture teardown produced `ExternalShutdownException` from the
coordinator and an RViz allocator/segmentation exit error. A standalone RViz
process exited 0 on SIGINT ([log](rviz-standalone.log)). A later
[parent-signal diagnostic](visual-parent-signal/launch.log) left no nodes but
retained a timed process-group TERM fallback; it does not prove graceful
shutdown. The original failure logs remain intact. Shutdown handling and the
TF classification defect remain open; no controller/grasp verification follows.

## Reproduction and provenance

The [runner directory](runner/) contains the final helper snapshots used for
build/test/model/analysis, fault/cancel tests, the impossible target and the
signal diagnostic. Helpers use the container paths `/workspace/CAM-BOT`,
`/cloud` and `/evidence`; use new output directories for subsequent runs.
The normal success capture used the unmodified repository command
`bash tools/capture_ay0608_humble.sh /evidence/visual-success` under `xvfb-run`.
The cancellation rerun used the repaired observer from tool commit
`8ebe7de`; the application checkout remained at `63db653` throughout.

[manifest.json](manifest.json) records the application/tool commits, image ID
and SHA-256 identities of retained outputs and helpers. Bag/CSV files use Git
LFS. The seven regenerated analysis outputs were compared, then left outside
the repository rather than duplicating the published artifacts. Original
October captures, checksums, source inventory and numerical results are intact.

All results establish visual ROS behavior or static checks. Actuated
simulation, bimanual/grasp feedback and physical CNC operation remain
unverified. The independent second-person criterion is unfulfilled.
