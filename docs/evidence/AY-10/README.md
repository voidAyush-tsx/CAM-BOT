# AY-10…AY-12 validation evidence

The complete measured artifacts are in
[`experiments/machine_tending/`](../../../experiments/machine_tending/README.md).
The main five-trial capture is `runs/ay10-visual-20261015-03/` under that directory.

- `build.log`: actual clean ROS Humble build output (both packages passed).
- `final_tests.log`: original 48 regression tests and the analysis test suite.
- `analysis_tests.log`: independent fixture/validation/regeneration test output.
- `acceptance.json`: machine-readable qualification and retained-capture inventory.
- `regeneration.log`: actual command output for regeneration/qualification.

The old `build`, `install`, and `log` directories had stale absolute paths to
`CAM-BOT-latest`. They were preserved under `.colcon/ay10-before-rebuild/` before
a fresh standard build. No source calibration or controller validation flags
were altered. All evidence remains scoped to visual ROS simulation.
