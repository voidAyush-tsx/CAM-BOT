# AY-02 dependency and packaging audit

At audit start, HEAD was `8a4b3814ce43ff55468909c0c27985d2c853f4d7`
on `feat/ay01-ay13-implementation`. The worktree was clean. The host is
CachyOS/Arch with `ROS_DISTRO` unset, so ROS package resolution and `rosdep`
could not run here. See `clean_build.log` for exact checks and outcomes.

- `src/carrier_description/setup.py:25-50` installs URDF, launch, and RViz
  files; `src/carrier_control/setup.py:19-36` installs config and five console
  scripts. Both now filter out directories such as `__pycache__` from globs.
- `src/carrier_control/carrier_control/machine_shop_joint_cycle.py:35-37`
  resolves the installed `carrier_control` share path and loads validated
  waypoints. The package-local YAML is byte-identical to the unchanged root
  `config/waypoints.yaml`; the offline test rejects drift. This removes the
  hardcoded-controller-vs-YAML source split. Earlier hardcoded controller
  literals had extra decimal places; numerical differences are below 1e-6 rad
  and must be reviewed before any hardware/controller run. No controller
  actuation is claimed by this audit.
- `src/carrier_description/package.xml` and `src/carrier_control/package.xml`
  parse and have no repeated dependency declarations. Description declares
  `launch`, `launch_ros`, `xacro`, `robot_state_publisher`, `rviz2`,
  `carrier_control`, `ur_description`, and legacy joint-state viewer options;
  control declares message/action and ament-index runtime dependencies.
  Description metadata was corrected from the obsolete “bin manipulator”
  wording. Maintainer fields are inherited and unverified, not replaced with
  guessed identities.
- `.gitignore` was not modified. `.gitattributes` marks experiment CSV and
  media types for Git LFS. `git check-attr filter --
  experiments/mass_sensitivity/exp01-upper-arm-10pct/data/baseline_8.393kg.csv`
  returned `lfs`; `git-lfs` is unavailable here, so clean-clone LFS object
  materialization is **not verified**. The Humble capture script checks it
  when available. No archived data or media was edited.
- No remote push or merge was attempted.

The applicable positive and negative tests are in
`src/carrier_control/test/test_package_integration.py`. The negative cases
remove an expected installed asset and corrupt the waypoint schema; both must
raise `ValueError`. `ros2 pkg prefix`, `ros2 pkg executables`, installed share
paths, clean `colcon build`, and GUI launch remain **BLOCKED** pending Ubuntu
22.04 / ROS Humble execution via `tools/capture_ay02_humble.sh`.
