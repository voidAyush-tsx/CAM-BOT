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
git lfs install --local
git lfs pull
docker run -d --name cambot-dev \
  --mount type=bind,src=/workspace/CAM-BOT,dst=/workspace/CAM-BOT \
  --mount "type=bind,src=$replay_output,dst=/evidence" \
  -e ROS_DOMAIN_ID=96 -e ROS_LOCALHOST_ONLY=1 \
  -e GALLIUM_DRIVER=softpipe cambot-humble:cloud sleep infinity
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
  export QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=softpipe
  for scenario in success unreachable load_failure cancelled; do
    bash tools/capture_ay0608_humble.sh "/evidence/$scenario" "$scenario"
  done
'
```

Use an unused container name or inspect an existing one before reuse. The image
includes Git LFS because container-side Git also applies checkout-local filters.
The capture runner now requires clean exits for all three launch children and
an empty residual graph; crashes or forced termination fail the capture.
Each scenario requires a new output directory. The unreachable fixture changes
only a copied configuration's two workspace radii to 1 mm.

Headless Xvfb with Mesa's default LLVM renderer reproduced an intermittent
RViz crash, including after single-interrupt shutdown was repaired. The debugger
stack entered LLVM compilation through `swrast_dri.so` during an RViz redraw.
`GALLIUM_DRIVER=softpipe` selects Mesa's alternative software renderer and is the
cloud image default. This is an environment workaround, not a fix to Mesa or
proof that every desktop renderer shuts down correctly. Keep all error checks
enabled. The recorded five-trial experiment remains separate.

Stop only the container started for this run with `docker stop cambot-dev`.
The mounted output directory remains on the host. Live processes do not
survive environment snapshots; restart the container workflow in new tasks.
