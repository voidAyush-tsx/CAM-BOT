#!/usr/bin/env bash
set -eo pipefail
cd /workspace/CAM-BOT
source /opt/ros/humble/setup.bash
source install/setup.bash
export QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1 PYTHONDONTWRITEBYTECODE=1
scenarios=(unreachable)
if [ "$#" -gt 0 ]; then scenarios=("$@"); fi
for scenario in "${scenarios[@]}"; do
  output="/evidence/$scenario${CAMBOT_RUN_SUFFIX:-}"
  test ! -e "$output"
  mkdir -p "$output"
  ros2 node list --no-daemon > "$output/preexisting_nodes.txt"
  test ! -s "$output/preexisting_nodes.txt"
  fault_args=()
  if [ "$scenario" = load_failure ]; then fault_args=(fault_injection_step:=S3_LOAD); fi
  setsid ros2 launch carrier_description dual_arm_demo.launch.py auto_start:=false enable_coordination:=true trial_count:=1 visual_time_scale:=1.0 config_file:=/evidence/unreachable-config.json results_file:="$output/trials.csv" > "$output/launch.log" 2>&1 &
  launch_pid=$!
  cleanup() {
    kill -INT "$launch_pid" 2>/dev/null || true
    for attempt in {1..10}; do
      kill -0 -- "-$launch_pid" 2>/dev/null || break
      sleep 1
    done
    kill -TERM -- "-$launch_pid" 2>/dev/null || true
    wait "$launch_pid" 2>/dev/null || true
  }
  trap cleanup EXIT
  timeout 75s python3 /cloud/observe-unreachable.py > "$output/probe.jsonl" 2>&1
  cleanup
  trap - EXIT
  ros2 node list --no-daemon > "$output/residual_nodes.txt"
  test ! -s "$output/residual_nodes.txt"
done
printf 'UNREACHABLE_SCENARIO_PASS\n'
