#!/usr/bin/env bash
# Bounded visual-only live TF/decision capture; controller motion is not proven.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
evidence_dir="${1:-$repo_root/docs/evidence/AY-06-08/runtime}"
scenario="${2:-success}"
case "$scenario" in success|load_failure|cancelled|unreachable) ;; *)
  printf 'Unknown visual scenario: %s\n' "$scenario" >&2; exit 2 ;;
esac
[[ ! -e "$evidence_dir" ]] || {
  printf 'Output already exists; choose a new evidence directory: %s\n' "$evidence_dir" >&2
  exit 2
}
[[ "${ROS_DISTRO:-}" == humble ]] || {
  printf 'ROS_DISTRO must be humble; observed %s\n' "${ROS_DISTRO:-unset}" >&2; exit 2;
}
for command_name in ros2 timeout python3; do
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
launch_options=()
probe=(python3 "$repo_root/tools/ay0608_ros_probe.py")
if [[ "$scenario" != success ]]; then
  probe=(python3 "$repo_root/tools/ay05_ros_probe.py" --expect "$scenario")
fi
if [[ "$scenario" == load_failure ]]; then
  launch_options=(fault_injection_step:=S3_LOAD)
elif [[ "$scenario" == unreachable ]]; then
  # Change only a new fixture. Never edit the installed station configuration.
  python3 - "$repo_root/src/carrier_control/config/machine_tending.json" \
    "$evidence_dir/unreachable-config.json" <<'PY'
import json
from pathlib import Path
import sys
plan = json.loads(Path(sys.argv[1]).read_text())
for arm in ("left", "right"):
    plan["workspace"][arm]["max_radius_m"] = 0.001
Path(sys.argv[2]).write_text(json.dumps(plan, indent=2) + "\n")
PY
  launch_options=(config_file:="$evidence_dir/unreachable-config.json")
fi
ros2 node list --no-daemon > "$evidence_dir/preexisting_nodes.txt"
[[ ! -s "$evidence_dir/preexisting_nodes.txt" ]] || {
  printf 'ROS domain is occupied; choose a clean ROS_DOMAIN_ID\n' >&2
  exit 2
}
python3 "$repo_root/tools/start_ros_session.py" ros2 bag record -o "$evidence_dir/visual_rosbag" \
  /joint_states /tf /tf_static /cambot/task_state \
  /cambot/workpiece_state /cambot/coordination_decision \
  > "$evidence_dir/bag_record.log" 2>&1 &
bag_pid=$!
python3 "$repo_root/tools/start_ros_session.py" ros2 launch carrier_description dual_arm_demo.launch.py \
  auto_start:=false enable_coordination:=true \
  trial_count:=1 visual_time_scale:=1.0 results_file:="$evidence_dir/trials.csv" \
  "${launch_options[@]}" \
  > "$evidence_dir/launch.log" 2>&1 &
launch_pid=$!
cleanup() {
  # Launch relays SIGINT to children. Signalling its whole group sends it twice.
  kill -INT "$launch_pid" "$bag_pid" 2>/dev/null || true
  for _ in {1..10}; do
    if ! kill -0 -- "-$launch_pid" 2>/dev/null && \
       ! kill -0 -- "-$bag_pid" 2>/dev/null; then break; fi
    sleep 1
  done
  cleanup_result=0
  if kill -0 -- "-$launch_pid" 2>/dev/null || \
     kill -0 -- "-$bag_pid" 2>/dev/null; then
    printf 'Graceful shutdown timed out; terminating owned process groups\n' >&2
    cleanup_result=1
    kill -TERM -- "-$launch_pid" "-$bag_pid" 2>/dev/null || true
    sleep 1
    kill -KILL -- "-$launch_pid" "-$bag_pid" 2>/dev/null || true
  fi
  wait "$launch_pid" 2>/dev/null || cleanup_result=1
  wait "$bag_pid" 2>/dev/null || cleanup_result=1
  return "$cleanup_result"
}
trap cleanup EXIT
timeout 110s "${probe[@]}" \
  > "$evidence_dir/probe.jsonl" 2>&1
timeout 10s ros2 topic info /joint_states --verbose \
  > "$evidence_dir/joint_state_publishers.txt"
cleanup_result=0
cleanup || cleanup_result=$?
trap - EXIT
[[ "$cleanup_result" == 0 ]] || exit "$cleanup_result"
python3 "$repo_root/tools/check_ros_shutdown.py" "$evidence_dir/launch.log"
timeout 10s ros2 bag info "$evidence_dir/visual_rosbag" \
  > "$evidence_dir/bag_info.txt"
ros2 node list --no-daemon > "$evidence_dir/residual_nodes.txt"
[[ ! -s "$evidence_dir/residual_nodes.txt" ]] || {
  printf 'ROS nodes remained after capture shutdown\n' >&2
  exit 1
}
printf 'Visual-only probe complete; inspect logs before claiming a pass.\n'
