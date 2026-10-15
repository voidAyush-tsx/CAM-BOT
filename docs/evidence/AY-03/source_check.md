# AY-03 source contract

`src/carrier_description/launch/dual_arm_demo.launch.py:10-58` is the preserved
single-command visual-only entry point. It fixes `mode` to
`visual_simulation`, starts the expanded UR5/workcell description, robot state
publisher, coordinator, and RViz, and exposes config/results/trial parameters.
It starts no controller and no competing `dual_arm_cycle`.

`src/carrier_description/launch/machine_tending_controller.launch.py:1-85`
is a separate gated controller integration entry point. It assembles a
supplied external controller bring-up file, workcell description, TF publisher,
coordinator (which publishes logical workpiece/task state and CSV records),
and RViz. Coordinator exit triggers launch shutdown. `launch_preflight.py`
rejects unvalidated/missing stations and missing controller bring-up before
any actions are returned. The supplied config fails at S1–S4 validation and
lacks an S5 target; no controller launch file is in this repository. The
external bring-up contract requires a carrier trajectory action server and
an authoritative UR5 joint-state broadcaster, with no duplicate UR5 writer.

`machine_tending_coordinator.py` in controller mode waits for the action
server and a complete, finite six-joint UR5 `/joint_states` sample before a
trial. It publishes only custom arm/workpiece joints in that mode. Action
success still requires actual-position feedback; runtime and end-to-end
verification flags remain false. Placeholder arm positions and workpiece
transitions are not evidence of a physical grasp or placement.

Offline commands actually run:

```bash
PYTHONPATH=src/carrier_control python3 -m unittest src/carrier_control/test/test_launch_preflight.py src/carrier_control/test/test_package_integration.py src/carrier_control/test/test_action_safety.py src/carrier_control/test/test_workflow.py src/carrier_control/test/test_metrics.py src/carrier_description/test/test_launch_contract.py src/carrier_description/test/test_cell_model.py -v
python3 -m py_compile src/carrier_control/carrier_control/launch_preflight.py src/carrier_control/carrier_control/machine_tending_coordinator.py src/carrier_description/launch/dual_arm_demo.launch.py src/carrier_description/launch/machine_tending_controller.launch.py
bash -n tools/capture_ay03_humble.sh
git diff --check
```

Results: 22/22 unittest checks passed, including positive launch/preflight
contracts and negative unvalidated-plan, missing-stack, and duplicate-writer
cases; syntax and whitespace checks exited 0. These are STATIC VALID checks,
not ROS launch or controller execution.
