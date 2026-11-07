# AY-13: consolidate reproducibility repairs, runtime fixes, and validation evidence

This draft collects all post-PR-#3 CAM-BOT work into one review branch, including
the earlier Humble replay and the subsequent runtime-repair sessions. The README,
quick-start, and Git LFS repairs from PR #3 are already on `main`; their history
is preserved rather than reapplied.

The coordinator now distinguishes a genuinely unreachable final target from
missing TF by checking fresh, stable transform timestamps. Shutdown requests
cancel bounded work, preserve interrupted-trial records, and close the ROS
context after cleanup. Capture scripts restore background-job signal handling,
reject child crashes or forced termination, and test success, unreachable-target,
injected-failure, and acknowledged-cancellation scenarios.

The branch also repairs package-asset verification, keeps current source hashes
separate from sealed historical evidence, prevents historical report overwrites,
and provides a Humble Dockerfile with Git LFS. All session code, raw captures,
passing checks, and unsuccessful diagnostics are retained with provenance and
checksums. A one-line upstream RViz timer-stop patch is included as a review
candidate; it has not yet been integrated into the reproducible Docker image.

Validation:

- Latest Humble package suite: **70 results, 0 errors, 0 failures, 2 existing skips**.
- **26 tool tests** and **14 experiment-analysis tests** passed.
- Scoped build, installed assets, Xacro/URDF, source inventory and syntax checks passed.
- All **7 archived analysis outputs** reproduced byte-for-byte with Matplotlib 3.5.1.
- All **404 pre-existing protected files** matched their baseline hashes.
- Three intermediate-source full visual cycles and unreachable/load-failure/cancellation
  probes passed. Five latest interrupted runs passed with locally rebuilt, patched RViz.

This remains a **draft**: integrate the pinned RViz dependency patch and repeat
the complete final visual/shutdown suite. Stock RViz still has a reproduced exit
crash, and switching to softpipe alone did not resolve it. AY-13 remains
**IN PROGRESS** pending those gates and the originally required independent
second-person review. Controller-backed simulation, grasp feedback, physical
operation, and comparative performance improvements remain unverified.

Review entry points:

- `docs/evidence/AY-13/runtime_repair_20261107/README.md`
- `docs/evidence/AY-13/agent_replay_20261106/README.md`
- `docs/STATUS.md` and `docs/ayush/ledger.json`
- `tools/cloud/rviz-stop-render-on-close.patch`

No merge into `main`, history rewrite, sealed-data overwrite, or numerical
experimental-result change is part of this PR.
