# ROS Humble in the managed cloud environment

The host is Debian; use the tested Ubuntu 22.04 / Humble image for ROS work.
Docker requires access to its managed socket. Networked builds use the session
proxy and a read-only CA secret, with TLS and package signatures verified.
`packages.ros.org` and the package-manager destinations must be allowed.

From `/workspace/CAM-BOT`:

```bash
docker build -f tools/cloud/Dockerfile.humble \
  --secret id=ca,src=/etc/ssl/certs/ca-certificates.crt \
  -t cambot-humble:cloud tools/cloud
```

The base image digest is pinned; apt dependencies may advance. Record installed
versions for each run. The [agent replay](evidence/AY-13/agent_replay_20261106/README.md)
records the tested image ID and versions; it also records failed diagnostics.

For normal development, mount the existing checkout and use a new output
directory. Cloud tasks are isolated; do not create a worktree unless requested.
These commands create only the named container and local build outputs:

```bash
replay_output="$(mktemp -d /tmp/cambot-humble.XXXXXX)"
docker run -d --name cambot-dev \
  --mount type=bind,src=/workspace/CAM-BOT,dst=/workspace/CAM-BOT \
  --mount "type=bind,src=$replay_output,dst=/evidence" \
  -e ROS_DOMAIN_ID=96 -e ROS_LOCALHOST_ONLY=1 cambot-humble:cloud sleep infinity
docker exec cambot-dev bash -c '
  set -e
  git config --global --add safe.directory /workspace/CAM-BOT
  source /opt/ros/humble/setup.bash
  colcon build --base-paths src --symlink-install --packages-select carrier_description carrier_control --executor sequential
  source install/setup.bash
  colcon test --base-paths src --packages-select carrier_description carrier_control --return-code-on-test-failure
  colcon test-result --verbose
  python3 tools/check_ay13_docs.py --installed
'
docker exec cambot-dev xvfb-run -a -s '-screen 0 1280x800x24' bash -c '
  set -e
  source /opt/ros/humble/setup.bash
  export QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1
  bash tools/capture_ay0608_humble.sh /evidence/visual
'
```

Use an unused container name or inspect an existing one before reuse. A passing
probe establishes the functional visual cycle; inspect `launch.log` and
`residual_nodes.txt` separately because the runner does not reject every child
exit error. Known shutdown and impossible-target diagnostics are documented in
the replay record. The recorded five-trial experiment remains separate.

Stop only the container started for this run with `docker stop cambot-dev`.
The mounted output directory remains on the host. Live processes do not
survive environment snapshots; restart the container workflow in new tasks.
