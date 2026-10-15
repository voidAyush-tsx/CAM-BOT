#!/usr/bin/env bash
# Capture a genuine visual ROS trial; this does not prove carrier/BM actuation.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
evidence_dir="$repo_root/docs/evidence/AY-09/runtime"
[[ "${ROS_DISTRO:-}" == humble ]] || {
  printf 'ROS_DISTRO must be humble; observed %s\n' "${ROS_DISTRO:-unset}" >&2; exit 2;
}
for command_name in ros2 timeout; do
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
summary="$evidence_dir/trials.csv"
ros2 launch carrier_description dual_arm_demo.launch.py \
  auto_start:=false trial_count:=1 experiment_id:=ay09-visual-runtime \
  results_file:="$summary" > "$evidence_dir/launch.log" 2>&1 &
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
  --expect success --timeout-s 90 > "$evidence_dir/probe.log" 2>&1
cleanup
trap - EXIT
PYTHONPATH="$repo_root/src/carrier_control" python3 \
  "$repo_root/tools/validate_ay09_dataset.py" "$summary" \
  > "$evidence_dir/dataset_validation.json"
printf 'AY-09 visual-runtime sample captured; no actuation claim.\n'
