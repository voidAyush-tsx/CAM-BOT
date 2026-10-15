#!/usr/bin/env bash
# Five fresh visual ROS attempts with observed resets; preserve all outcomes.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
raw_dir="${1:?Usage: capture_ay10_humble.sh NEW_RAW_DIRECTORY [COUNT]}"
count="${2:-5}"
[[ "$count" =~ ^[0-9]+$ ]] && (( count >= 5 && count <= 25 )) || { echo 'COUNT must be 5..25' >&2; exit 2; }
[[ "${ROS_DISTRO:-}" == humble ]] || { echo 'Source ROS Humble first' >&2; exit 2; }
[[ ! -e "$raw_dir" ]] || { echo 'Output must be a new directory; captures are never overwritten' >&2; exit 2; }
set +u
source "$repo_root/install/setup.bash"
set -u
mkdir -p "$raw_dir"
raw_dir="$(realpath "$raw_dir")"
export QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1
# A caller may select another unused ROS domain. Abort if it already has nodes.
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-86}"
ros2 node list --no-daemon > "$raw_dir/preexisting_nodes.txt"
[[ ! -s "$raw_dir/preexisting_nodes.txt" ]] || { echo 'ROS domain is occupied; choose an unused ROS_DOMAIN_ID' >&2; exit 2; }
cp "$repo_root/src/carrier_control/config/machine_tending.json" "$raw_dir/config.json"
python3 "$repo_root/tools/record_ay10_environment.py" "$raw_dir" "$count"
ros2 bag record -o "$raw_dir/visual_rosbag" /joint_states /tf /tf_static \
  /cambot/task_state /cambot/workpiece_state /cambot/coordination_decision /cambot/coordinator_state \
  > "$raw_dir/bag_record.log" 2>&1 &
bag_pid=$!
ros2 launch carrier_description dual_arm_demo.launch.py \
  auto_start:=false enable_coordination:=true trial_count:=1 visual_time_scale:=1.0 \
  config_file:="$raw_dir/config.json" results_file:="$raw_dir/trials.csv" \
  experiment_id:=ay10-visual-fixed-v1 > "$raw_dir/launch.log" 2>&1 &
launch_pid=$!
cleanup() {
  kill -INT "$launch_pid" "$bag_pid" 2>/dev/null || true
  for _ in {1..10}; do
    if ! kill -0 "$launch_pid" 2>/dev/null && ! kill -0 "$bag_pid" 2>/dev/null; then break; fi
    sleep 1
  done
  kill -TERM "$launch_pid" "$bag_pid" 2>/dev/null || true
  wait "$launch_pid" 2>/dev/null || true
  wait "$bag_pid" 2>/dev/null || true
}
trap cleanup EXIT
set +e
python3 "$repo_root/tools/ay10_ros_probe.py" --raw-dir "$raw_dir" --count "$count" \
  > "$raw_dir/probe.log" 2>&1
probe_status=$?
set -e
ros2 topic info /joint_states --verbose > "$raw_dir/joint_state_publishers.txt"
cleanup
trap - EXIT
ros2 bag info "$raw_dir/visual_rosbag" > "$raw_dir/bag_info.txt"
python3 "$repo_root/tools/record_ay10_environment.py" "$raw_dir" "$count" --seal
if (( probe_status != 0 )); then
  echo 'AY-10 capture BLOCKED; partial evidence retained' >&2
  exit "$probe_status"
fi
python3 "$repo_root/experiments/machine_tending/scripts/analyze_trials.py" \
  "$raw_dir/trials.csv" --output "${raw_dir}_analysis" --qualify
