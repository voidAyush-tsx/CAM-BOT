#!/usr/bin/env bash
# Bounded visual-only live TF/decision capture; controller motion is not proven.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
evidence_dir="${1:-$repo_root/docs/evidence/AY-06-08/runtime}"
[[ ! -e "$evidence_dir" ]] || {
  printf 'Output already exists; choose a new evidence directory: %s\n' "$evidence_dir" >&2
  exit 2
}
[[ "${ROS_DISTRO:-}" == humble ]] || {
  printf 'ROS_DISTRO must be humble; observed %s\n' "${ROS_DISTRO:-unset}" >&2; exit 2;
}
for command_name in ros2 timeout setsid; do
  command -v "$command_name" >/dev/null || {
    printf 'Missing %s\n' "$command_name" >&2; exit 2;
  }
done
[[ -f "$repo_root/install/setup.bash" ]] || {
  printf 'Build the workspace first\n' >&2; exit 2;
}
set +u
source "$repo_root/install/setup.bash"
set -u
mkdir -p "$evidence_dir"
ros2 node list --no-daemon > "$evidence_dir/preexisting_nodes.txt"
[[ ! -s "$evidence_dir/preexisting_nodes.txt" ]] || {
  printf 'ROS domain is occupied; choose a clean ROS_DOMAIN_ID\n' >&2
  exit 2
}
setsid ros2 bag record -o "$evidence_dir/visual_rosbag" \
  /joint_states /tf /tf_static /cambot/task_state \
  /cambot/workpiece_state /cambot/coordination_decision \
  > "$evidence_dir/bag_record.log" 2>&1 &
bag_pid=$!
setsid ros2 launch carrier_description dual_arm_demo.launch.py \
  auto_start:=false enable_coordination:=true \
  trial_count:=1 visual_time_scale:=1.0 \
  > "$evidence_dir/launch.log" 2>&1 &
launch_pid=$!
cleanup() {
  kill -INT -- "-$launch_pid" "-$bag_pid" 2>/dev/null || true
  for _ in {1..10}; do
    if ! kill -0 -- "-$launch_pid" 2>/dev/null && \
       ! kill -0 -- "-$bag_pid" 2>/dev/null; then break; fi
    sleep 1
  done
  kill -TERM -- "-$launch_pid" "-$bag_pid" 2>/dev/null || true
  wait "$launch_pid" 2>/dev/null || true
  wait "$bag_pid" 2>/dev/null || true
}
trap cleanup EXIT
timeout 110s python3 "$repo_root/tools/ay0608_ros_probe.py" \
  > "$evidence_dir/probe.jsonl" 2>&1
timeout 10s ros2 topic info /joint_states --verbose \
  > "$evidence_dir/joint_state_publishers.txt"
cleanup
trap - EXIT
timeout 10s ros2 bag info "$evidence_dir/visual_rosbag" \
  > "$evidence_dir/bag_info.txt"
ros2 node list --no-daemon > "$evidence_dir/residual_nodes.txt"
[[ ! -s "$evidence_dir/residual_nodes.txt" ]] || {
  printf 'ROS nodes remained after capture shutdown\n' >&2
  exit 1
}
printf 'Visual-only probe complete; inspect logs before claiming a pass.\n'
