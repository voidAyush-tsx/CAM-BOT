#!/usr/bin/env bash
set -eo pipefail
cd /workspace/CAM-BOT
source /opt/ros/humble/setup.bash
export COLCON_TRACE= PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg MPLCONFIGDIR=/tmp/cambot-mpl
git config --global --add safe.directory /workspace/CAM-BOT
{
  git rev-parse HEAD
  git status --short --branch
  cat /etc/os-release
  python3 --version
  dpkg-query -W ros-humble-ros-base ros-humble-rviz2 ros-humble-rclpy ros-humble-ur-description python3-matplotlib python3-pytest
} > /evidence/environment.txt
[[ -z "$(git status --porcelain)" ]]
rosdep check --from-paths src --ignore-src > /evidence/rosdep-check.log 2>&1
colcon build --base-paths src --symlink-install --packages-select carrier_description carrier_control --executor sequential > /evidence/colcon-build.log 2>&1
source install/setup.bash
colcon test --base-paths src --packages-select carrier_description carrier_control --executor sequential --return-code-on-test-failure > /evidence/colcon-test.log 2>&1
colcon test-result --verbose > /evidence/colcon-test-result.log 2>&1
python3 tools/check_ay13_docs.py --installed > /evidence/installed-doc-check.log 2>&1
python3 -m unittest discover -s experiments/machine_tending/tests -v > /evidence/analysis-tests.log 2>&1
python3 -m unittest tools/test_check_ay13_docs.py tools/test_generate_build_report.py tools/test_verify_ay.py tools/test_ay05_ros_probe.py tools/test_ros_shutdown.py -v > /evidence/tool-tests.log 2>&1
python3 tools/verify_ay.py --output /evidence/legacy-verification.json > /evidence/legacy-verification.log 2>&1
xacro src/carrier_description/urdf/ur5_with_test_tool.xacro > /evidence/cambot.urdf
check_urdf /evidence/cambot.urdf > /evidence/check-urdf.log 2>&1
python3 experiments/machine_tending/scripts/analyze_trials.py experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv --output /evidence/regenerated-analysis --qualify > /evidence/analysis-regeneration.log 2>&1
python3 tools/generate_build_report.py --output /evidence/historical-report.json > /evidence/historical-report.log 2>&1
python3 - <<'PY' > /evidence/analysis-comparison.log
from pathlib import Path
old=Path('experiments/machine_tending/runs/ay10-visual-20261015-03/raw_analysis')
new=Path('/evidence/regenerated-analysis')
for path in sorted(old.iterdir()):
    if path.is_file():
        assert path.read_bytes() == (new/path.name).read_bytes(), path
        print(path.name, 'MATCH')
PY
python3 - <<'PY' > /evidence/syntax.log
import ast, subprocess
from pathlib import Path
paths=subprocess.check_output(['git','ls-files','src','tools','experiments/machine_tending/scripts','experiments/machine_tending/tests'],text=True).splitlines()
python_paths=[p for p in paths if p.endswith('.py')]
shell_paths=[p for p in paths if p.endswith('.sh')]
for p in python_paths: ast.parse(Path(p).read_text(), filename=p)
for p in shell_paths: subprocess.run(['bash','-n',p],check=True)
print('PASS:',len(python_paths),'Python files,',len(shell_paths),'shell files')
PY
for scenario in success unreachable load_failure cancelled; do
  bash tools/capture_ay0608_humble.sh "/evidence/$scenario" "$scenario" > "/evidence/$scenario-runner.log" 2>&1
done
set +e
timeout 15s ros2 launch carrier_description machine_tending_controller.launch.py > /evidence/controller-gate.log 2>&1
code=$?
set -e
[[ "$code" -ne 0 && "$code" -ne 124 ]]
python3 - <<'PY'
from pathlib import Path
text=Path('/evidence/controller-gate.log').read_text()
assert 'not controller-validated' in text
print('CONTROLLER_PREFLIGHT_REJECTION_PASS: no controller actuation tested')
PY
git status --short --branch > /evidence/final-git-status.txt
[[ -z "$(git status --porcelain)" ]]
printf 'AY13_AGENT_TECHNICAL_REPLAY_PASS\n'
