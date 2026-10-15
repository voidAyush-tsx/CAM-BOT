#!/usr/bin/env bash
# Capture AY-04 only in a built, sourced Ubuntu 22.04 / Humble GUI workspace.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
evidence_dir="$repo_root/docs/evidence/AY-04/runtime"
[[ "${ROS_DISTRO:-}" == humble ]] || {
  printf 'ROS_DISTRO must be humble; observed %s\n' "${ROS_DISTRO:-unset}" >&2; exit 2;
}
for command_name in ros2 xacro check_urdf timeout; do
  command -v "$command_name" >/dev/null || { printf 'Missing %s\n' "$command_name" >&2; exit 2; }
done
[[ -f "$repo_root/install/setup.bash" ]] || {
  printf 'Build the workspace first\n' >&2; exit 2;
}
source "$repo_root/install/setup.bash"
mkdir -p "$evidence_dir"
control_prefix="$(timeout 10s ros2 pkg prefix carrier_control)"
description_prefix="$(timeout 10s ros2 pkg prefix carrier_description)"
config_file="$control_prefix/share/carrier_control/config/machine_tending.json"
wrapper="$description_prefix/share/carrier_description/urdf/ur5_with_test_tool.xacro"
mapfile -d '' station_args < <(python3 -c '
import json, sys
from carrier_control.workcell_model import xacro_station_arguments
workcell = json.load(open(sys.argv[1], encoding="utf-8"))["workcell"]
for argument in xacro_station_arguments(workcell):
    sys.stdout.buffer.write(argument.encode() + b"\0")
' "$config_file")
[[ "${#station_args[@]}" == 15 ]] || { printf 'Expected 15 station Xacro arguments\n' >&2; exit 1; }
{
  date --iso-8601=seconds
  git -C "$repo_root" rev-parse HEAD
  sed -n '1,12p' /etc/os-release
  printf 'ROS_DISTRO=%s\nconfig=%s\nwrapper=%s\n' "$ROS_DISTRO" "$config_file" "$wrapper"
  printf '%s\n' "${station_args[@]}"
} > "$evidence_dir/environment-and-arguments.log"
timeout 30s xacro "$wrapper" include_workcell:=true "${station_args[@]}" \
  > "$evidence_dir/configured.urdf"
timeout 30s check_urdf "$evidence_dir/configured.urdf" \
  > "$evidence_dir/check_urdf.log" 2>&1

ros2 launch carrier_description dual_arm_demo.launch.py \
  config_file:="$config_file" visual_time_scale:=1.0 \
  > "$evidence_dir/launch.log" 2>&1 &
launch_pid=$!
cleanup() {
  kill -INT "$launch_pid" 2>/dev/null || true
  for _ in {1..10}; do
    kill -0 "$launch_pid" 2>/dev/null || break
    sleep 1
  done
  kill -TERM "$launch_pid" 2>/dev/null || true
  wait "$launch_pid" 2>/dev/null || true
}
trap cleanup EXIT
ready=false
for _ in {1..20}; do
  if timeout 3s ros2 topic info /joint_states -v > "$evidence_dir/joint_source.log" 2>&1 &&
    grep -q 'Publisher count: 1' "$evidence_dir/joint_source.log"; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]] || { printf 'Visual joint source did not become ready\n' >&2; exit 1; }
timeout 15s ros2 topic echo /tf_static --once --qos-durability transient_local \
  > "$evidence_dir/tf_static.log"
for frame in station_s1_raw station_s2_staging station_s3_machine station_s4_output station_s5_finished; do
  grep -q "$frame" "$evidence_dir/tf_static.log" || {
    printf 'Missing station TF frame: %s\n' "$frame" >&2; exit 1;
  }
done
(
  cd "$evidence_dir"
  timeout 20s ros2 run tf2_tools view_frames > view_frames.log 2>&1
)
timeout 15s ros2 topic echo /cambot/workpiece_state --once \
  > "$evidence_dir/workpiece_state.log"
timeout 15s ros2 topic echo /cambot/task_state --once \
  > "$evidence_dir/task_target.log"
cleanup
trap - EXIT

scratch="$(mktemp -d /tmp/cambot-ay04.XXXXXXXX)"
set +e
timeout 15s ros2 launch carrier_description dual_arm_demo.launch.py \
  config_file:="$scratch/missing.json" > "$evidence_dir/missing-config.log" 2>&1
missing_exit=$?
set -e
printf 'missing_config_exit=%s\n' "$missing_exit" > "$evidence_dir/missing-config-result.txt"
[[ "$missing_exit" != 0 && "$missing_exit" != 124 ]] || {
  printf 'Missing configuration did not fail promptly\n' >&2; exit 1;
}
printf 'Inspect RViz and save screenshot to runtime/rviz-cell.png.\n'
