#!/usr/bin/env bash
# Agent/reviewer technical replay. This does not create a human sign-off.
set -eo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
[[ $# == 1 && ! -e "$1" ]] || {
  printf 'Usage: bash tools/cloud/validate_humble.sh NEW_OUTPUT_DIRECTORY\n' >&2
  exit 2
}
evidence_dir="$(realpath -m "$1")"
[[ -z "$(git status --porcelain)" ]] || {
  printf 'A clean checkout is required\n' >&2; exit 2;
}
mkdir -p "$evidence_dir"
export CAMBOT_REPLAY_OUTPUT="$evidence_dir"
export COLCON_TRACE= PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg MPLCONFIGDIR=/tmp/cambot-mpl
export QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1
source /opt/ros/humble/setup.bash
source /opt/cambot/rviz/setup.bash
[[ -z "${LD_PRELOAD:-}" ]] || { printf 'Unexpected LD_PRELOAD\n' >&2; exit 2; }
[[ "$(ros2 pkg prefix rviz_common)" == /opt/cambot/rviz ]]
ldd /opt/ros/humble/lib/rviz2/rviz2 > "$evidence_dir/rviz-libraries.txt"
grep -F 'librviz_common.so => /opt/cambot/rviz/lib/librviz_common.so' "$evidence_dir/rviz-libraries.txt"
cp /opt/cambot/rviz/share/cambot-patches/provenance.txt "$evidence_dir/rviz-provenance.txt"
{
  git rev-parse HEAD
  git status --short --branch
  cat /etc/os-release
  python3 --version
  dpkg-query -W ros-humble-ros-base ros-humble-rviz2 ros-humble-rclpy ros-humble-ur-description python3-matplotlib python3-pytest
  printf 'ROS_DOMAIN_ID=%s\nROS_LOCALHOST_ONLY=%s\nGALLIUM_DRIVER=%s\n' \
    "${ROS_DOMAIN_ID:-0}" "${ROS_LOCALHOST_ONLY:-0}" "${GALLIUM_DRIVER:-default}"
} > "$evidence_dir/environment.txt"
git lfs fsck > "$evidence_dir/lfs-fsck.log" 2>&1
rosdep check --from-paths src --ignore-src > "$evidence_dir/rosdep-check.log" 2>&1
colcon build --base-paths src --symlink-install --packages-select carrier_description carrier_control --executor sequential > "$evidence_dir/colcon-build.log" 2>&1
source install/setup.bash
colcon test --base-paths src --packages-select carrier_description carrier_control --executor sequential --return-code-on-test-failure > "$evidence_dir/colcon-test.log" 2>&1
colcon test-result --verbose > "$evidence_dir/colcon-test-result.log" 2>&1
python3 tools/check_ay13_docs.py --installed > "$evidence_dir/installed-doc-check.log" 2>&1
python3 -m unittest discover -s experiments/machine_tending/tests -v > "$evidence_dir/analysis-tests.log" 2>&1
python3 -m unittest discover -s tools -p 'test_*.py' -v > "$evidence_dir/tool-tests.log" 2>&1
python3 tools/verify_ay.py --output "$evidence_dir/legacy-verification.json" > "$evidence_dir/legacy-verification.log" 2>&1
xacro src/carrier_description/urdf/ur5_with_test_tool.xacro > "$evidence_dir/cambot.urdf"
check_urdf "$evidence_dir/cambot.urdf" > "$evidence_dir/check-urdf.log" 2>&1
python3 experiments/machine_tending/scripts/analyze_trials.py experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv --output "$evidence_dir/regenerated-analysis" --qualify > "$evidence_dir/analysis-regeneration.log" 2>&1
python3 tools/generate_build_report.py --output "$evidence_dir/historical-report.json" > "$evidence_dir/historical-report.log" 2>&1
python3 - <<'PY' > "$evidence_dir/analysis-comparison.log"
import json
import os
from pathlib import Path
old = Path('experiments/machine_tending/runs/ay10-visual-20261015-03/raw_analysis')
new = Path(os.environ['CAMBOT_REPLAY_OUTPUT']) / 'regenerated-analysis'
for name in ('metrics.json', 'summary.csv', 'trials.csv'):
    assert (old / name).read_bytes() == (new / name).read_bytes(), name
    print(name, 'NUMERICAL_MATCH')
before = json.loads((old / 'artifacts.json').read_text())
after = json.loads((new / 'artifacts.json').read_text())
assert set(before) == set(after)
for name in before:
    assert before[name]['observations'] == after[name]['observations']
for path in sorted(old.iterdir()):
    if path.is_file():
        match = path.read_bytes() == (new / path.name).read_bytes()
        print(path.name, 'BYTE_MATCH' if match else 'RENDERING_BYTES_DIFFER')
# PNG/artifact byte counts can vary with Matplotlib; numerical equality above
# is mandatory. All byte differences remain visible in the evidence.
PY
python3 - <<'PY' > "$evidence_dir/syntax.log"
import ast
import subprocess
from pathlib import Path
paths = subprocess.check_output(['git', 'ls-files', 'src', 'tools',
    'experiments/machine_tending/scripts', 'experiments/machine_tending/tests'], text=True).splitlines()
python_paths = [p for p in paths if p.endswith('.py')]
shell_paths = [p for p in paths if p.endswith('.sh')]
for p in python_paths:
    ast.parse(Path(p).read_text(), filename=p)
for p in shell_paths:
    subprocess.run(['bash', '-n', p], check=True)
print('PASS:', len(python_paths), 'Python files,', len(shell_paths), 'shell files')
PY
printf 'Build, offline checks, model and historical analysis passed\n'
for scenario in success unreachable load_failure cancelled; do
  bash tools/capture_ay0608_humble.sh "$evidence_dir/$scenario" "$scenario" > "$evidence_dir/$scenario-runner.log" 2>&1
  printf 'Visual scenario passed: %s\n' "$scenario"
done
python3 tools/probe_visual_shutdown.py "$evidence_dir/idle" --scenario idle > "$evidence_dir/idle-runner.log" 2>&1
printf 'Idle shutdown passed\n'
for repeat in 1 2 3 4 5; do
  python3 tools/probe_visual_shutdown.py "$evidence_dir/interrupted-$repeat" --scenario active > "$evidence_dir/interrupted-$repeat-runner.log" 2>&1
  printf 'Interrupted shutdown passed: %s/5\n' "$repeat"
done
set +e
timeout 15s ros2 launch carrier_description machine_tending_controller.launch.py > "$evidence_dir/controller-gate.log" 2>&1
code=$?
set -e
[[ "$code" -ne 0 && "$code" -ne 124 ]]
grep -F 'not controller-validated' "$evidence_dir/controller-gate.log"
git status --short --branch > "$evidence_dir/final-git-status.txt"
[[ -z "$(git status --porcelain)" ]]
printf 'AY13_AGENT_TECHNICAL_REPLAY_PASS (independent human review still required)\n'
