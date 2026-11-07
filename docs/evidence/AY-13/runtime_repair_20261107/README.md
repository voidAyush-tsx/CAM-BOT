# AY-13 consolidated runtime repair progress — 2026-11-07

This is an **agent-run engineering record**, not independent human review.
AY-13 remains IN PROGRESS. This snapshot collects work across the earlier
validation branch and subsequent runtime-repair sessions for a single draft PR.
Machine logs retain their original UTC timestamps, including November 6.

## Source and environment

- GitHub: `voidAyush-tsx/CAM-BOT`, branch `fix/ay13-runtime-finalization`.
- Earlier validation commits: `8ebe7de`, `e58b802`; these are ancestors of this branch.
- Fresh GitHub clone: `/tmp/cambot-ay13-final-clean`, initially `fb3a5af`, then
  fast-forwarded to the recorded test revisions. Source stayed clean during runs.
- Initial full-suite checkout: `4bc0b2c8a2bb7274e618510be6f07726bd962a2e`.
- Latest coordinator source: `c375343`; latest package/tool/analysis tests and
  five native patched-RViz interruption checks: `9a192eca37f1c46c972e6fc248a09c4494e17941`.
- Ubuntu 22.04, ROS Humble, Python 3.10.12, Matplotlib 3.5.1, Xvfb; exact packages
  in [environment.txt](environment.txt). This checkout now needs Git LFS inside
  the container as well as on the host; the missing-package preflight is retained.
- Runtime image: `sha256:054827b1e2d9e711165f41e41e35d57153eab94a0f1ab94e9699f79d124fa15d`,
  with Git LFS and diagnostic tools installed afterward. The Dockerfile rebuild
  in [docker-build.log](docker-build.log) produced
  `sha256:4eec5fe2e4725fbd08e0af85d192acc980b1f60ea8b1e9dd7c641a23917499af`.
  That intermediate image selected softpipe; its renderer setting was withdrawn
  after another crash. Do not treat that image as the final validated solution.

## Implemented repairs

1. TF freshness uses timestamps rather than demanding more geometric movement
   after the final pose. Four distinct, stable post-motion samples are required;
   stale/cached samples and unsettled timeouts are rejected. The visual adapter
   republishes the final pose while waiting. An observed unreachable final pose
   now returns `RECHECK_STILL_UNREACHABLE` after exactly one reposition.
2. The coordinator owns SIGINT/SIGTERM handling, requests bounded cancellation,
   seals an interrupted trial as INCOMPLETE, then destroys the node and shuts
   down its context. This avoids invalid-publisher and native subscription-take
   races. Queued starts do not run after shutdown is requested.
3. Capture sessions restore SIGINT inherited as ignored from Bash background
   execution. Only the launch parent is interrupted; launch forwards the signal.
   Child crashes, forced termination, missing clean exits, or residual nodes fail
   the capture. Failure/cancellation/unreachable scenarios have reproducible probes.
4. The maintained source inventory is separate from the sealed historical map.
   Historical reports validate their original source revision; their writer now
   requires a new output path and refuses overwrites. Package-asset and observer
   repairs from the earlier validation branch are included.

Carrier kinematics, station targets, coordination policy, reachability geometry,
and FSM implementation were not redesigned. Historical experiment results and
all 404 protected files match their baseline hashes; see
[sealed-preservation.json](sealed-preservation.json).

## Verification results

| Check | Result and evidence |
|---|---|
| Dependencies and scoped build | PASS: [rosdep](rosdep-check.log), [two packages](colcon-build.log) |
| Latest package tests | **70 results, 0 errors, 0 failures, 2 existing copyright skips**: [summary](final-colcon-test-result.log) |
| Latest tools/document/report/observer tests | **26 passed**: [log](final-tool-tests.log) |
| Latest experiment analysis tests | **14 passed**: [log](final-analysis-tests.log) |
| Installed assets and source inventory | PASS: [installed check](installed-doc-check.log); maintained inventory refreshed for latest source |
| Syntax and model | 59 Python files and 8 shell files passed; [syntax](syntax.log), [URDF](check-urdf.log) |
| Legacy verifier | 26/26: [report](legacy-verification.json) |
| Archived analysis reproduction | All **7 outputs byte-match** with Matplotlib 3.5.1: [comparison](analysis-comparison.log); outputs are in a new directory |
| Coordinated full visual cycles | Three consecutive softpipe runs passed, five TF rechecks each, one publisher, all children clean: [first probe](softpipe/success-1/probe.jsonl), [second](softpipe/success-2/probe.jsonl), [third](softpipe/success-3/probe.jsonl) |
| Impossible target | PASS: exactly one reposition, `RECHECK_STILL_UNREACHABLE`, RAW_AT_S1: [probe](softpipe/unreachable/probe.jsonl) |
| Injected load failure / acknowledged cancellation | PASS: [load failure](softpipe/load_failure/probe.jsonl), [cancellation](softpipe/cancelled/probe.jsonl) |
| Latest interrupted-trial checks with locally patched RViz | Five passes, clean exits, durable INCOMPLETE records: [runner log](patched-native-interrupted.log), per-run `patched-native-interrupted-1` through `-5` |

The visual cycles/failure checks above preceded the final signal-only correction.
The latest correction has the full package regression and five interruption
checks. A complete visual-suite repeat with the final packaged RViz patch remains
required. No new controller actuation, grasp, hardware, or independent-person
verification is claimed. Prior controller-preflight rejection evidence remains
in the earlier agent replay; the initial full-suite runner stopped at RViz
shutdown before its controller-preflight step.

## RViz candidate and retained failures

The original LLVM renderer failed during shutdown after a successful cycle:
[failed capture](success-runner.log), [GDB trace](rviz-gdb-2/launch.log).
Softpipe passed six scenarios but failed an early interruption:
[log](softpipe/interrupted/launch.log). Valgrind found invalid writes during
rendering, including a write beyond a zero-sized allocation:
[memory log](rviz-valgrind/memory.log). A renderer switch alone is insufficient.

The candidate [patch](../../../../tools/cloud/rviz-stop-render-on-close.patch)
stops `VisualizationManager`'s update timer before closing the RViz window.
It applies to upstream `ros2/rviz` tag `11.2.29`, commit
`4e2b27b7561da7eb03fbc7e92a74d4b3f1e0b054`. A diagnostic interposition test was
followed by a real source build of `rviz_common` and five passing interrupted
runs with the original LLVM renderer. See [build](rviz-common-build.log),
[loaded libraries](patched-rviz-libraries.txt), and the per-run result files.
The rebuilt library was sourced from `/cloud/rviz-patched/install/local_setup.bash`.

**The patch is collected for review, not applied by the repository Dockerfile.**
Next: integrate the pinned dependency patch reproducibly, rebuild the image,
repeat all visual scenarios and interrupted/idle shutdown checks without the
diagnostic preload helper, then obtain the originally required independent
second-person clean-checkout review. AY-13 stays IN PROGRESS until its acceptance
requirements are genuinely fulfilled.

`development/` and the other diagnostic folders retain unsuccessful intermediate
attempts as well as successes. They are not pooled with the sealed AY-10 data.
`runner/` preserves the session's actual helper code, including diagnostic code;
its absolute paths describe this environment and are not an automatic setup
interface. The production capture command remains
`bash tools/capture_ay0608_humble.sh NEW_OUTPUT [success|unreachable|load_failure|cancelled]`.
The manifest records the collected files' SHA-256 hashes.
