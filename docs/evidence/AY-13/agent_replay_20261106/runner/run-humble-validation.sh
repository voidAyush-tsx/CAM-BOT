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
  dpkg-query -W ros-humble-ros-base ros-humble-rviz2 ros-humble-ur-description python3-matplotlib python3-pytest
} > /evidence/environment.txt
colcon build --base-paths src --symlink-install --packages-select carrier_description carrier_control --executor sequential > /evidence/colcon-build.log 2>&1
source install/setup.bash
colcon test --base-paths src --packages-select carrier_description carrier_control --executor sequential --return-code-on-test-failure > /evidence/colcon-test.log 2>&1
colcon test-result --verbose > /evidence/colcon-test-result.log 2>&1
python3 tools/check_ay13_docs.py --installed > /evidence/installed-doc-check.log 2>&1
python3 -m unittest discover -s experiments/machine_tending/tests -v > /evidence/analysis-tests.log 2>&1
python3 -m unittest tools/test_check_ay13_docs.py tools/test_generate_build_report.py -v > /evidence/doc-report-tests.log 2>&1
xacro src/carrier_description/urdf/ur5_with_test_tool.xacro > /evidence/cambot.urdf
check_urdf /evidence/cambot.urdf > /evidence/check-urdf.log 2>&1
python3 experiments/machine_tending/scripts/analyze_trials.py experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv --output /evidence/regenerated-analysis --qualify > /evidence/analysis-regeneration.log 2>&1
printf 'BUILD_TEST_MODEL_ANALYSIS_PASS\n'
