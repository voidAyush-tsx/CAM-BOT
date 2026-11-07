# AY-13 reproducible-image technical replay — 2026-11-07

Agent-run technical validation passed. This record does **not** supply the
independent second-person reproduction required to close AY-13.

## Provenance and change

The user merged PR #4 into `main` at
`f1279828b875865ada5811189c8df593b9690e39`; the merge tree matches the consolidated
repair commit `51c3d9f`. This follow-up was built on that merge, published as
`feat/ay13-reproducible-rviz`, then cloned afresh from GitHub into
`/tmp/cambot-ay13-reproducible-clean`. The tested source is
`540998c02b568350bc84737fd462208c7f251d09`, with a clean tree before and after.
Subsequent evidence/status commits do not change the tested ROS implementation.

The [Dockerfile](../../../../tools/cloud/Dockerfile.humble) builds the one-line
RViz render-timer shutdown patch from pinned upstream revision
`4e2b27b7561da7eb03fbc7e92a74d4b3f1e0b054` (11.2.29). The final image ID is
`sha256:276b84e9359aa087e5c166f64eeed1d3d18b93d9fc159fe6c21506a56da0e0a2`.
It selects the compiled library through a ROS overlay, without a preload shim
or softpipe override. [Build output](docker-build.log),
[library resolution](replay/rviz-libraries.txt),
[patch/library hashes and package versions](replay/rviz-provenance.txt), and
[environment](replay/environment.txt) are retained. Apt dependency versions
are recorded; byte-identical future images are not claimed.

Ubuntu 22.04.5 / ROS Humble ran in Docker with Xvfb and software rendering,
Python 3.10.12, Matplotlib 3.5.1, ROS domain 99, and localhost-only DDS.
The Debian host itself does not provide ROS. A host-side broad tool-test
attempt failed to import `rclpy`; the complete suite below passed inside Humble.

## Commands and observed results

Follow the exact [clean-clone workflow](../../../CLOUD_HUMBLE.md). The primary
command, inside the new container and Xvfb, was:

```bash
bash tools/cloud/validate_humble.sh /evidence/replay
```

The [runner output](runner.log) ended with `AY13_AGENT_TECHNICAL_REPLAY_PASS`.

| Check | Result / evidence |
|---|---|
| Git LFS, dependencies, scoped Colcon build | PASS; [LFS](replay/lfs-fsck.log), [rosdep](replay/rosdep-check.log), [build](replay/colcon-build.log) |
| Package tests | 70 results, 0 errors, 0 failures, 2 pre-existing copyright skips; [log](replay/colcon-test-result.log) |
| Documentation/source inventory and installed contracts | PASS; [log](replay/installed-doc-check.log) |
| Tool regression tests | 30 passed; [log](replay/tool-tests.log) |
| Experiment analysis tests | 14 passed; [log](replay/analysis-tests.log) |
| Legacy static checks | 26/26; [JSON](replay/legacy-verification.json); its historical runtime disclaimer is fixed text, not the environment record for this replay |
| Xacro / URDF | PASS; [expanded model](replay/cambot.urdf), [check](replay/check-urdf.log) |
| Python / shell syntax | 61 Python and 10 shell files passed; [log](replay/syntax.log) |
| Historical report / analysis regenerated in new paths | PASS; [comparison](replay/analysis-comparison.log); all seven analysis files byte-match, including PNGs |
| Normal coordinated cycle | PASS: five reposition rechecks, `FINISHED_AT_S5`; [probe](replay/success/probe.jsonl) |
| Impossible target | PASS: one reposition then `RECHECK_STILL_UNREACHABLE`; [probe](replay/unreachable/probe.jsonl) |
| Injected S3 load failure | PASS; [probe](replay/load_failure/probe.jsonl) |
| Acknowledged cancellation | PASS; [probe](replay/cancelled/probe.jsonl) |
| Idle shutdown | PASS: no trial created; [result](replay/idle/result.json) |
| Interrupted shutdown | 5/5 PASS during PICK_RAW; [first result](replay/interrupted-1/result.json), [fifth result](replay/interrupted-5/result.json); each trial is `INCOMPLETE`, false success, `RAW_AT_S1` |
| Controller preflight | Expected rejection of unvalidated S1 target; [log](replay/controller-gate.log) |
| Preservation | All 721 baseline source/evidence/experiment/media/config/report files unchanged; [hashes](preserved-artifacts.json) |

All ten launch cases passed the strict clean-exit checker for coordinator,
robot-state publisher and RViz. Each recorded one authoritative joint-state
publisher and an empty residual node graph. The active/idle observers are
separate nodes, not joint-state publishers. No runtime test changed station
configuration: the impossible-target fixture lives only in its new capture.

Matplotlib differences may change PNG bytes even when numerical results match.
The validator requires numerical/table equality and records image-byte
comparisons separately. This replay happened to match every published output.
The historical AY-10 dataset and every earlier failure/diagnostic are preserved.
`manifest.json` hashes every file in this new evidence directory except itself.

## Remaining acceptance boundary

The demonstrated fixes cover the current visual simulation and software-rendered
cloud image. They do not establish universal graphics-driver correctness,
controller actuation, grasp/release feedback, collision-free paths, surveyed
geometry or physical operation. No `src/` implementation changed in this branch.

AY-13 remains **IN PROGRESS** until an identified independent human actually
repeats the clean-checkout procedure and records the required observations and
acknowledgement. The agent replay must not be relabeled as that review. Review
and merge this follow-up separately from the already merged PR #4.
