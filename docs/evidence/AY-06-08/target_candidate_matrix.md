# AY-07/06 target/candidate matrix — synthetic transform tests

Source: `machine_tending.json` temporary station geometry; current entries are
**simulation assumptions**, not measured poses. `test_reachability.py` and
`test_coordination.py` use these examples. The workspace is an inclusive box
and 0.40 m radius per arm, with shoulder-center assumptions at x=-0.22 m and
x=+0.22 m. Both arms must pass. This is a geometric proxy, not IK, collision
clearance, or a closed-chain grasp test.

| Target | World XYZ (m) | Synthetic world→BM origin (m), identity rotation | Local XYZ (m) | Result / policy |
|---|---|---|---|---|
| RAW_PICK | (0.75, 0.85, 0.76) | (0.75, 0.60, 0.71) | (0, 0.25, 0.05) | Both pass → LOCAL_MANIPULATION; zero carrier requests |
| STAGE_INSPECT before | (0.15, 1.05, 0.76) | (0.75, 0.60, 0.71) | (-0.60, 0.45, 0.05) | Both fail → one CARRIER_REPOSITION request |
| STAGE_INSPECT after synthetic move | (0.15, 1.05, 0.76) | (0.15, 0.80, 0.71) | (0, 0.25, 0.05) | Both pass → LOCAL_MANIPULATION after recheck |
| STAGE_INSPECT after failed candidate | (0.15, 1.05, 0.76) | (0.75, 0.60, 0.71) | (-0.60, 0.45, 0.05) | UNREACHABLE, `RECHECK_STILL_UNREACHABLE`; no second request |
| Boundary (local) | (0.02, 0.25, 0.05) | (0, 0, 0) | (0.02, 0.25, 0.05) | Both pass; inclusive x boundary |
| Just outside | (0.020001, 0.25, 0.05) | (0, 0, 0) | (0.020001, 0.25, 0.05) | Both-arm requirement fails |
| Missing/NaN TF | any | invalid | unknown | UNKNOWN → ERROR; never accepted |

The offline full-cycle test uses a synthetic TF update to reach each later
station, then confirms eight state visits and `FINISHED_AT_S5`. It does not
show that the historical UR5 joint targets reach these poses. In live ROS,
the coordinator must independently observe `world -> dual_arm_base_link` TF
change after a successful carrier action result and actual-position feedback.
