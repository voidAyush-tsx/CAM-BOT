#!/usr/bin/env bash
# Run inside a clean Ubuntu 22.04 / ROS 2 Humble workspace checkout.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
evidence_dir="$repo_root/docs/evidence/AY-01/runtime"
cd "$repo_root"

if [[ "${ROS_DISTRO:-}" != "humble" ]]; then
  printf 'ROS_DISTRO must be humble; observed %s\n' "${ROS_DISTRO:-unset}" >&2
  exit 2
fi
for required_command in ros2 rosdep colcon xacro check_urdf timeout; do
  if ! command -v "$required_command" >/dev/null 2>&1; then
    printf 'Missing command: %s\n' "$required_command" >&2
    exit 2
  fi
done
mkdir -p "$evidence_dir"

{
  date --iso-8601=seconds
  pwd
  git status --short --branch
  git rev-parse HEAD
  sed -n '1,12p' /etc/os-release
  printf 'ROS_DISTRO=%s\n' "$ROS_DISTRO"
  printf 'SHELL=%s\n' "${SHELL:-unset}"
  command -v ros2 rosdep colcon xacro check_urdf
} > "$evidence_dir/environment.log"

timeout 20s ros2 pkg list > "$evidence_dir/packages-before-build.log"
timeout 300s rosdep install --from-paths src --ignore-src -r -y \
  > "$evidence_dir/rosdep.log" 2>&1
timeout 600s colcon build --symlink-install \
  --packages-select carrier_description carrier_control \
  > "$evidence_dir/colcon.log" 2>&1
source install/setup.bash
{
  timeout 10s ros2 pkg prefix carrier_description
  timeout 10s ros2 pkg prefix carrier_control
} > "$evidence_dir/package-prefixes.log"

timeout 30s xacro src/carrier_description/urdf/ur5_with_test_tool.xacro \
  include_workcell:=false > "$evidence_dir/phase4_generated.urdf"
timeout 30s check_urdf "$evidence_dir/phase4_generated.urdf" \
  > "$evidence_dir/check_urdf.log" 2>&1
python3 tools/phase4_contract.py --urdf "$evidence_dir/phase4_generated.urdf" \
  > "$evidence_dir/contract.json"

ros2 launch carrier_description view_dual_arm.launch.py \
  > "$evidence_dir/viewer.log" 2>&1 &
launch_pid=$!
cleanup() {
  if kill -0 "$launch_pid" 2>/dev/null; then
    kill -INT "$launch_pid" 2>/dev/null || true
    for _ in {1..10}; do
      if ! kill -0 "$launch_pid" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "$launch_pid" 2>/dev/null; then
      kill -TERM "$launch_pid" 2>/dev/null || true
    fi
  fi
  wait "$launch_pid" 2>/dev/null || true
}
trap cleanup EXIT

ready=false
for _ in {1..20}; do
  if timeout 3s ros2 topic info /joint_states -v \
      > "$evidence_dir/joint_state_authority.log" 2>&1; then
    if grep -q 'Publisher count: 1' \
        "$evidence_dir/joint_state_authority.log"; then
      ready=true
      break
    fi
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  printf 'Expected exactly one /joint_states publisher\n' >&2
  exit 1
fi

timeout 15s ros2 topic echo /joint_states --once \
  > "$evidence_dir/joint_states_once.log" 2>&1
(
  cd "$evidence_dir"
  timeout 20s ros2 run tf2_tools view_frames \
    > view_frames.log 2>&1
)

cleanup
trap - EXIT
git status --short --branch > "$evidence_dir/git-status-after.log"
printf 'AY-01 automated ROS checks completed. Capture RViz screenshot and inspect TF diagram.\n'
