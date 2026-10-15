#!/usr/bin/env bash
# Three isolated visual launch/stop trials and one controller fail-closed check.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
evidence_dir="$repo_root/docs/evidence/AY-03/runtime"
if [[ "${ROS_DISTRO:-}" != humble ]]; then
  printf 'ROS_DISTRO must be humble; observed %s\n' "${ROS_DISTRO:-unset}" >&2
  exit 2
fi
for command_name in ros2 timeout; do
  command -v "$command_name" >/dev/null || { printf 'Missing %s\n' "$command_name" >&2; exit 2; }
done
[[ -f "$repo_root/install/setup.bash" ]] || {
  printf 'Build and source the repository workspace first\n' >&2; exit 2;
}
source "$repo_root/install/setup.bash"
mkdir -p "$evidence_dir"
{
  date --iso-8601=seconds
  git -C "$repo_root" rev-parse HEAD
  sed -n '1,12p' /etc/os-release
  printf 'ROS_DISTRO=%s ROS_DOMAIN_ID=%s\n' "$ROS_DISTRO" "${ROS_DOMAIN_ID:-unset}"
  timeout 10s ros2 pkg prefix carrier_description
  timeout 10s ros2 pkg prefix carrier_control
} > "$evidence_dir/environment.log"

for trial in 1 2 3; do
  trial_dir="$evidence_dir/visual-$trial"
  mkdir -p "$trial_dir"
  ros2 launch carrier_description dual_arm_demo.launch.py \
    visual_time_scale:=1.0 trial_count:=1 > "$trial_dir/launch.log" 2>&1 &
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
    if timeout 3s ros2 topic info /joint_states -v > "$trial_dir/joint_source.log" 2>&1 &&
      grep -q 'Publisher count: 1' "$trial_dir/joint_source.log"; then
      ready=true
      break
    fi
    sleep 1
  done
  [[ "$ready" == true ]] || { printf 'visual trial %s has no unique joint publisher\n' "$trial" >&2; exit 1; }
  timeout 10s ros2 node list > "$trial_dir/nodes.txt"
  timeout 10s ros2 topic list > "$trial_dir/topics.txt"
  timeout 10s ros2 action list > "$trial_dir/actions.txt"
  timeout 15s ros2 topic echo /joint_states --once > "$trial_dir/joint_sample.txt"
  timeout 15s ros2 topic echo /tf --once > "$trial_dir/tf_sample.txt"
  timeout 15s ros2 topic echo /tf_static --once --qos-durability transient_local \
    > "$trial_dir/tf_static_sample.txt"
  timeout 15s ros2 topic echo /cambot/workpiece_state --once > "$trial_dir/workpiece_state.txt"
  cleanup
  trap - EXIT
  stopped=false
  for _ in {1..10}; do
    timeout 3s ros2 node list > "$trial_dir/nodes_after_stop.txt" || true
    if ! grep -Eq '^/(machine_tending_coordinator|robot_state_publisher|rviz2)$' \
        "$trial_dir/nodes_after_stop.txt"; then
      stopped=true
      break
    fi
    sleep 1
  done
  [[ "$stopped" == true ]] || { printf 'visual trial %s left ROS nodes running\n' "$trial" >&2; exit 1; }
  printf 'SIGINT sent; launch exited and its named nodes disappeared\n' > "$trial_dir/stop_result.txt"
done

# The supplied config is intentionally unvalidated. This launch must fail
# before starting nodes, even if somebody supplies a controller path later.
set +e
timeout 15s ros2 launch carrier_description machine_tending_controller.launch.py \
  > "$evidence_dir/controller-default-rejection.log" 2>&1
controller_exit=$?
set -e
printf 'controller_default_exit=%s\n' "$controller_exit" \
  > "$evidence_dir/controller-default-result.txt"
[[ "$controller_exit" != 0 && "$controller_exit" != 124 ]] || {
  printf 'Controller default launch did not fail promptly\n' >&2; exit 1;
}
printf 'AY-03 visual trials captured; inspect images/graph and confirm child cleanup.\n'
