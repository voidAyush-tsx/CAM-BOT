#!/usr/bin/env bash
# Reproduce AY-02 from a fresh local clone in Ubuntu 22.04 / ROS Humble.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
evidence_dir="$repo_root/docs/evidence/AY-02/runtime"
if [[ "${ROS_DISTRO:-}" != humble ]]; then
  printf 'ROS_DISTRO must be humble; observed %s\n' "${ROS_DISTRO:-unset}" >&2
  exit 2
fi
for command_name in git ros2 rosdep colcon timeout; do
  command -v "$command_name" >/dev/null || { printf 'Missing %s\n' "$command_name" >&2; exit 2; }
done
mkdir -p "$evidence_dir"
scratch="$(mktemp -d /tmp/cambot-ay02.XXXXXXXX)"
printf '%s\n' "$scratch" > "$evidence_dir/scratch-path.txt"
mkdir -p "$scratch/ws/src"
GIT_LFS_SKIP_SMUDGE=1 timeout 120s git clone --local --no-hardlinks "$repo_root" "$scratch/ws/src/CAM-BOT" \
  > "$evidence_dir/clone.log" 2>&1
cd "$scratch/ws/src/CAM-BOT"
{
  date --iso-8601=seconds
  pwd
  git rev-parse HEAD
  git status --short --branch
  sed -n '1,12p' /etc/os-release
  printf 'ROS_DISTRO=%s\n' "$ROS_DISTRO"
  command -v ros2 rosdep colcon
} > "$evidence_dir/environment.log"
if command -v git-lfs >/dev/null; then
  timeout 120s git lfs pull > "$evidence_dir/lfs.log" 2>&1
  timeout 60s git lfs fsck >> "$evidence_dir/lfs.log" 2>&1
else
  printf 'git-lfs unavailable; LFS materialization not verified\n' > "$evidence_dir/lfs.log"
fi

cd "$scratch/ws"
timeout 900s rosdep install --from-paths src/CAM-BOT/src --ignore-src -r -y \
  > "$evidence_dir/rosdep.log" 2>&1
timeout 900s colcon build --symlink-install --base-paths src/CAM-BOT/src \
  --packages-select carrier_description carrier_control \
  > "$evidence_dir/clean_build.log" 2>&1
source install/setup.bash
description_prefix="$(timeout 10s ros2 pkg prefix carrier_description)"
control_prefix="$(timeout 10s ros2 pkg prefix carrier_control)"
{
  printf 'carrier_description=%s\ncarrier_control=%s\n' "$description_prefix" "$control_prefix"
  timeout 10s ros2 pkg executables carrier_control
  find "$description_prefix/share/carrier_description" -type f | sort
  find "$control_prefix/share/carrier_control" -type f | sort
} > "$evidence_dir/installed_assets.txt"
for asset in \
  "$description_prefix/share/carrier_description/rviz/dual_arm.rviz" \
  "$description_prefix/share/carrier_description/launch/dual_arm_demo.launch.py" \
  "$description_prefix/share/carrier_description/urdf/ur5_with_test_tool.xacro" \
  "$control_prefix/share/carrier_control/config/waypoints.yaml"; do
  test -f "$asset" || { printf 'Missing installed asset: %s\n' "$asset" >&2; exit 1; }
done

ros2 launch carrier_description dual_arm_demo.launch.py trial_count:=1 \
  > "$evidence_dir/launch.log" 2>&1 &
launch_pid=$!
cleanup() {
  if kill -0 "$launch_pid" 2>/dev/null; then
    kill -INT "$launch_pid" 2>/dev/null || true
    for _ in {1..10}; do
      kill -0 "$launch_pid" 2>/dev/null || break
      sleep 1
    done
    kill -TERM "$launch_pid" 2>/dev/null || true
  fi
  wait "$launch_pid" 2>/dev/null || true
}
trap cleanup EXIT
ready=false
for _ in {1..20}; do
  if timeout 3s ros2 topic info /joint_states -v > "$evidence_dir/joint_state_authority.log" 2>&1 &&
    grep -q 'Publisher count: 1' "$evidence_dir/joint_state_authority.log"; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]] || { printf 'Expected one /joint_states publisher\n' >&2; exit 1; }
timeout 15s ros2 topic echo /joint_states --once > "$evidence_dir/joint_states_once.log" 2>&1
cleanup
trap - EXIT
git -C "$scratch/ws/src/CAM-BOT" status --short --branch > "$evidence_dir/clone-status-after.log"
printf 'AY-02 automated checks passed. Inspect RViz and launch.log for asset errors.\n'
