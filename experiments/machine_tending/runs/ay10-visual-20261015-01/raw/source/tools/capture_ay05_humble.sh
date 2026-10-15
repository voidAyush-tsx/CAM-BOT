#!/usr/bin/env bash
# Bounded visual-only ROS FSM integration checks; no carrier actuation claim.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
evidence_dir="$repo_root/docs/evidence/AY-05/runtime"
[[ "${ROS_DISTRO:-}" == humble ]] || {
  printf 'ROS_DISTRO must be humble; observed %s\n' "${ROS_DISTRO:-unset}" >&2; exit 2;
}
for command_name in ros2 timeout; do
  command -v "$command_name" >/dev/null || { printf 'Missing %s\n' "$command_name" >&2; exit 2; }
done
[[ -f "$repo_root/install/setup.bash" ]] || {
  printf 'Build the workspace first\n' >&2; exit 2;
}
source "$repo_root/install/setup.bash"
mkdir -p "$evidence_dir"
{
  date --iso-8601=seconds
  git -C "$repo_root" rev-parse HEAD
  sed -n '1,12p' /etc/os-release
  printf 'ROS_DISTRO=%s ROS_DOMAIN_ID=%s\n' "$ROS_DISTRO" "${ROS_DOMAIN_ID:-unset}"
} > "$evidence_dir/environment.log"

for scenario in success load_failure cancelled; do
  scenario_dir="$evidence_dir/$scenario"
  mkdir -p "$scenario_dir"
  fault_step=""
  if [[ "$scenario" == load_failure ]]; then
    fault_step="S3_LOAD"
  fi
  ros2 launch carrier_description dual_arm_demo.launch.py \
    auto_start:=false trial_count:=1 visual_time_scale:=1.0 \
    fault_injection_step:="$fault_step" \
    > "$scenario_dir/launch.log" 2>&1 &
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
  timeout 110s python3 "$repo_root/tools/ay05_ros_probe.py" \
    --expect "$scenario" --timeout-s 90 \
    > "$scenario_dir/transition-events.jsonl" 2>&1
  cleanup
  trap - EXIT
  timeout 10s ros2 node list > "$scenario_dir/nodes-after-stop.txt" || true
done
printf 'AY-05 visual FSM scenarios captured; no actuator verification claimed.\n'
