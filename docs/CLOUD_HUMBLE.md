# ROS Humble in the managed cloud environment

The host is Debian; run ROS work in the Ubuntu 22.04 / Humble image below.
Docker needs its managed socket. Builds use the session proxy and a read-only
CA secret, with TLS and package signatures verified. Allow `github.com`,
`packages.ros.org` and the package-manager destinations.

## Build and dependency provenance

Run from the repository root; the build context must be `.`:

```bash
docker build -f tools/cloud/Dockerfile.humble \
  --secret id=ca,src=/etc/ssl/certs/ca-certificates.crt \
  -t cambot-humble:ay13-reproducible .
```

The base image digest and RViz source revision are pinned. The Dockerfile
fetches `ros2/rviz` commit `4e2b27b7561da7eb03fbc7e92a74d4b3f1e0b054`
(Humble 11.2.29), applies the tracked
[timer-stop patch](../tools/cloud/rviz-stop-render-on-close.patch), and builds
only `rviz_common` into `/opt/cambot/rviz`. The patch stops rendering before
window closure after ROS shutdown. It leaves the apt installation intact.
The build rejects a different installed RViz common/2/default-plugins version
so an ABI change requires review. Other apt dependencies can advance; this is
a pinned source repair, not a claim of byte-identical images across dates.

The final image contains the upstream license, patch, source revision,
package versions and library SHA-256 under
`/opt/cambot/rviz/share/cambot-patches/`. The image entrypoint sources the overlay;
**`docker exec` bypasses image entrypoints**, so invoke `/cambot_entrypoint.sh`
explicitly as below. The validator checks both the ROS package prefix and
actual dynamic-library resolution. No `LD_PRELOAD` shim is used.

The [earlier diagnostics](evidence/AY-13/runtime_repair_20261107/README.md)
include the RViz shutdown crash and five successful locally patched interrupted
runs. `GALLIUM_DRIVER=softpipe` failed an earlier interruption test; it is not
an accepted workaround. The old replay records retain their original image
IDs and failures. Use a fresh output directory for each new attempt.

## Clean-checkout technical replay

Use the exact published review branch/commit until it is merged into `main`.
A separate clone is required for acceptance; the commands below create one,
fetch LFS objects, and preserve the original checkout and sealed captures.
Choose an unused container name. Record the printed commit and image ID.

```bash
review_ref=feat/ay13-reproducible-rviz
replay_checkout="$(mktemp -d /tmp/cambot-clean.XXXXXX)"
replay_output="$(mktemp -d /tmp/cambot-evidence.XXXXXX)"
git clone --branch "$review_ref" https://github.com/voidAyush-tsx/CAM-BOT.git "$replay_checkout"
cd "$replay_checkout"
git lfs install --local
git lfs pull
git rev-parse HEAD
git status --short
docker build -f tools/cloud/Dockerfile.humble \
  --secret id=ca,src=/etc/ssl/certs/ca-certificates.crt \
  -t cambot-humble:ay13-reproducible .
docker image inspect cambot-humble:ay13-reproducible --format '{{.Id}}' \
  > "$replay_output/image-id.txt"
docker run -d --name cambot-ay13-reproduce \
  --mount "type=bind,src=$replay_checkout,dst=/workspace/CAM-BOT" \
  --mount "type=bind,src=$replay_output,dst=/evidence" \
  -e ROS_DOMAIN_ID=99 -e ROS_LOCALHOST_ONLY=1 \
  cambot-humble:ay13-reproducible sleep infinity
docker exec cambot-ay13-reproduce /cambot_entrypoint.sh \
  xvfb-run -a -s '-screen 0 1280x800x24' bash -ec '
    git config --global --add safe.directory /workspace/CAM-BOT
    bash tools/cloud/validate_humble.sh /evidence/replay
  ' > "$replay_output/runner.log" 2>&1
cat "$replay_output/runner.log"
docker stop cambot-ay13-reproduce
printf 'Retained evidence: %s\n' "$replay_output"
```

The [validator](../tools/cloud/validate_humble.sh) refuses an existing output
path or dirty checkout. It records dependencies, Git/LFS, scoped Colcon tests,
installed documentation/source-inventory checks, tool and analysis tests,
expanded URDF, and historical analysis regenerated into a new directory.
Numerical outputs must match. PNG bytes and plot byte counts can differ across
Matplotlib versions; every byte comparison is recorded separately.

Runtime cases cover normal completion, unreachable targets, an injected
S3 load failure, cancellation, idle shutdown and five interruptions during
PICK_RAW. Each case checks clean child exits and an empty residual graph;
probes inspect the single authoritative `/joint_states` publisher. Interrupted
trials must be sealed as `INCOMPLETE`, never success. The controller entrypoint
must still reject the unvalidated default configuration.

A technical replay is agent-run when executed by Codex. It does not satisfy
the [independent human reproduction requirement](CODEX_FIRST_TASK.md).
AY-13 remains in progress until that evidence exists. Controller actuation,
grasp feedback and physical operation are outside this visual replay.

For ordinary development, mount the existing checkout instead; do not call
that a clean-checkout acceptance run. Stop only containers started for your
run. Evidence remains on the host. Live processes do not survive environment
snapshots; start the workflow again in a later task.
