# Model study — 2026-11-07

Source `ed7390e`, based on merged PR #4 plus the reproducible-image follow-up.
Ubuntu 22.04/Humble image
`sha256:276b84e9359aa087e5c166f64eeed1d3d18b93d9fc159fe6c21506a56da0e0a2`;
agent-run with current model assumptions explicitly authorized by the user.
The [method and commands](../../README.md) explain the proof boundary.

The [report](study/report.json) records exact URDF/config/placement hashes,
joint limits, random seed 13, NumPy version and source commit. The
[point cloud](study/point_cloud.csv) contains 20,006 configurations and their
bimanual-base origins. [Coverage](study/station_coverage.csv),
[configured visual/controller targets](study/configured_targets.json), and
[plot](study/workspace.png) are retained without changing the AY-10 experiments.

| Assumed base placement | Interaction targets with a proxy-matching sample / 6 |
|---|---:|
| Current | 6 |
| East 0.2 m | 0 |
| West 0.2 m | 3 |
| North 0.2 m | 3 |
| South 0.2 m | 2 |

For the current placement, every match comes from an appended configured visual
pose; none came from the 20,000 uniform random samples. This bias prevents a
claim that the current placement is optimal. The other candidates' no-hit
targets also cannot be declared unreachable. The practical recommendation is
to retain the current visual baseline while adding targeted IK and collision
validation before selecting a physical placement.

All four legacy S1–S4 controller vectors fail the current both-arm proxy for
their station targets. Their best signed clearances are approximately
−0.423 m, −1.310 m, −1.472 m and −0.614 m respectively. These values quantify
mismatch to the assumed layout, not measured physical clearance. S5 still has
no controller vector. No validation flag or runtime configuration was changed.

The eight new regression tests cover analytic two-link FK, transform order,
limits, malformed chains, proxy agreement with the existing runtime evaluator,
and refusal to overwrite output. The full tool suite passed **38 tests** in
Humble ([log](tool-tests.log)). A separate [live TF probe](fk-crosscheck/result.json)
compared HOME, S1, S3 and S5 against `robot_state_publisher`; maximum matrix
error was `5.551115123125783e-16`, below the `1e-9` tolerance. One joint-state
publisher and an empty residual graph were verified. This checks kinematics,
not controller execution.

Phase 3/6 completion remains pending collision/orientation checks, workspace
boundary validation and stronger sampling/IK coverage. A physical-placement
recommendation is intentionally null in the report. These are preliminary
model results; no independent human review, actuation or grasp is claimed.
`manifest.json` hashes this retained run except itself.
