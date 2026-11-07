#!/usr/bin/env bash
set -e
# Keep the patched RViz overlay ahead of the apt underlay. For docker exec,
# invoke this entrypoint explicitly (Docker only applies ENTRYPOINT to run).
source /opt/ros/humble/setup.bash
source /opt/cambot/rviz/setup.bash
exec "$@"
