# Machine-tending experiments: AY-09 through AY-12

AY-10 is complete **for visual ROS 2 Humble simulation**, as explicitly selected
for these experiments. AY-11/12 results measure the live visual FSM and joint
publication workflow. All `runtime_verified`, `end_to_end_verified`,
`actuation_verified`, and `grasp_verified` flags remain false. These timings and
counts are not physical robot or CNC performance measurements.

## Recorded experiments

| Capture | Actual attempted trials | Outcomes | Disposition |
|---|---:|---|---|
| [01](runs/ay10-visual-20261015-01/) | 1 | 1 success | Retained preliminary capture; reset-readiness gate blocked the next start |
| [02](runs/ay10-visual-20261015-02/) | 0 | No trial started | Preflight found residual nodes from 01 |
| [03](runs/ay10-visual-20261015-03/) | 5 | 5 successes | Qualifying fixed-configuration AY-10 dataset |

All **six actual attempted trials** are retained; none failed. The two capture
infrastructure failures are recorded separately because no second/first trial
was started in those cases. Capture 01 and 03 have different runner source
snapshots and are reported separately, without pooled timing statistics.
Neither old carrier-only cycles nor mass-sensitivity experiments are included.

The main dataset has 5 unique final rows, 530 structured node events, one FSM
terminal and one administrative `FINALIZE` per trial. Before each start, the
observer verified HOME carrier/custom joints, the raw workpiece at S1, fresh
world-to-BM TF, all five fixed station transforms, and one `/joint_states`
publisher. The batch also verified the final reset. Each successful trial
executed all 12 steps and 8 state visits, ending with `FINISHED_AT_S5` and HOME.

Each trial exercised five reposition-and-TF-recheck cases and four already
reachable/no-reposition steps (`S1_GRASP`, `S3_RELEASE`, `S3_REGRASP`,
`S5_RELEASE`). These are coordination-specific cases within the full workflow,
not a separate optimized baseline.

## Results and counting rules

[Main metrics](runs/ay10-visual-20261015-03/raw_analysis/metrics.json),
[per-trial table](runs/ay10-visual-20261015-03/raw_analysis/trials.csv), and
[summary table](runs/ay10-visual-20261015-03/raw_analysis/summary.csv) are generated
from immutable raw CSV and JSONL files.

| Main capture metric | Observed value |
|---|---:|
| Successful / all attempted | 5 / 5 (100%) |
| Mean successful cycle duration | 19.579117 s |
| Median | 19.585576 s |
| Minimum / maximum | 19.551515 / 19.592351 s |
| Sample standard deviation (`n-1`) | 0.016634 s |
| Missing / censored durations | 0 / 0 |
| Repositions requested / accepted / completed | 25 / 25 / 25 |

The cycle starts at node event `S1_APPROACH: STEP_STARTED` (first PICK_RAW
action) and ends at `HOME_END: STEP_COMPLETED`. Durations use recorded
`time.monotonic()` offsets; UTC and ROS timestamps correlate evidence. Startup,
readiness, resetting, and `HOME_START` are excluded. The original AY-09
`cycle_time_s` includes `HOME_START`; it remains intact in raw data and appears
as `logger_elapsed_s` in the derived table.

For failed trials, elapsed time ends at the failure terminal; it is marked
censored because the intended complete cycle was not observed. A trial failing
before PICK_RAW has a missing duration. All attempts remain in the success-rate
denominator. Successful-duration summaries exclude failed/incomplete trials
and report their counts and failure causes alongside the summary. Standard
deviation is undefined (JSON null / empty CSV cell) with fewer than two successes.

A reposition is one distinct `CARRIER_MOTION` ID with maximum absolute commanded
joint change greater than `1e-6 rad`, targeting a station other than HOME.
Requests, visual-adapter acceptances, and completed exact-goal joint publications
are counted separately. HOME return is included only in the separate total move
count (six nontrivial visual moves per successful trial); zero-motion HOME_START
is excluded. Qualification additionally finds each completed goal in the
independently observed `/joint_states` stream. The legacy summary reposition
counter is retained but is not used for AY-11 counts. Controller action requests,
acceptances, and results are **not present** in this visual dataset.

Scenario groups include configuration hash, source commit plus source snapshot,
environment hash, experiment ID, mode, coordination, time scale, and injected
fault parameters. Different groups get separate summaries. Results are
descriptive; there is no controlled comparison or optimization claim.

## Evidence and source identity

The main capture ran on 2026-10-15, approximately **16:09–16:11 Asia/Kolkata**,
in `cambot-humble`, Ubuntu 22.04, ROS Humble, with `visual_time_scale=1.0`,
coordination enabled, Qt xcb, and software rendering. Source provenance is:

- Base Git commit: `6e77292e4fceca0636a4cd86a037bf9e7d64f93a`.
- Configuration SHA-256: `4a30a60ff007ec96a0be3d97aee8319e4bc8db24a8f4ffe1cd01c68968359076`.
- Capture 03 source-tree SHA-256: `fa421a5426f597b6dc65ec47781e4e8d6c7886796d30774998aa8f7f0933fe08`.

The source was modified relative to that base commit during execution. The
commit alone does not identify the executed version. `raw/source.patch`, the
complete selected `raw/source/` snapshot (including new scripts), and its
per-file hashes identify the exact capture version. `manifest.json` records
package versions, runtime parameters, environment and invocation. Later analysis
revisions have their own script SHA-256 in `metrics.json`; raw capture snapshots
are never silently updated when analysis changes.

Raw evidence includes `trials.csv`, `trials.events.jsonl`, `attempts.jsonl`,
`topics.jsonl`, launch/probe logs, publisher inspection, a rosbag with 5,643
messages, and a [real RViz screenshot](runs/ay10-visual-20261015-03/raw/rviz_runtime.png).
`checksums.json` seals every raw file. Regeneration checks these hashes when
`--qualify` is used. The screenshot was taken on the host using
`niri msg action screenshot-window --id RVIZ_WINDOW_ID --path ABSOLUTE_PATH`;
its timestamp and window title are retained beside it.

Capture 01 exposed two runner defects: consecutive redundant resets could
produce no new TF because robot_state_publisher throttled the second sample;
parent-only cleanup could leave children running. Capture 03 uses one verified
reset between attempts and process-group cleanup. Its launch log contains an
`ExternalShutdownException` from the coordinator during intentional shutdown,
after five durable successful finals and the final reset. No CAM-BOT node was
left running. This teardown traceback is retained rather than removed from logs.

## Reproduce capture

Use a fresh output directory; the script refuses to overwrite captures or use
an occupied ROS domain. Starting a batch does not stop at a failed trial: the
observer records the outcome, verifies reset, then attempts the next trial.
If readiness, reset, or terminal evidence cannot be established, it stops and
retains a blocked partial capture. A hard crash leaving a dangling attempt is
rejected by analysis; it cannot disappear from the denominator.

```bash
distrobox enter cambot-humble -- bash
cd ~/TOPS/CAM-BOT
source /opt/ros/humble/setup.bash
export COLCON_TRACE=
colcon build --symlink-install --packages-select carrier_description carrier_control
export ROS_DOMAIN_ID=86
bash tools/capture_ay10_humble.sh \
  experiments/machine_tending/runs/NEW_CAPTURE/raw 5
```

The script safely sources the workspace under `set +u` / `set -u`, sets the
required Qt/software-rendering environment, launches the existing visual
system, and records a bag. It expects the existing Humble runtime dependencies.
Matplotlib 3.5.1 was already installed in the container; it is an analysis-only
dependency declared in `analysis-requirements.txt`. Pandas is not required.
A screenshot is a separate host capture while RViz is running.

To recreate the exact recorded capture version, check out the base commit into
a separate workspace and overlay `raw/source/` before building. Use a fresh
output directory and the same manifest parameters. Reproduction is expected
to yield new IDs, timestamps and measured durations, not identical observations.

## Regenerate AY-11/12

```bash
python3 experiments/machine_tending/scripts/analyze_trials.py \
  experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv \
  --output experiments/machine_tending/runs/ay10-visual-20261015-03/raw_analysis \
  --qualify
```

Run with the container's Python/Matplotlib. Outputs are `trials.csv`,
`summary.csv`, `metrics.json`, `artifacts.json`, `cycle_time_by_trial.png`,
`trial_outcomes.png`, and `carrier_repositions_by_trial.png`. Plots use seconds
or move counts, display sample count, and preserve failed/missing/censored
observations. An empty header-only CSV plus empty JSONL explicitly yields no
measured statistics and labeled empty plots; it cannot qualify for AY-10.
Output directories inside raw input directories are rejected.

To regenerate the preliminary single-trial analysis, use capture `01` and omit
`--qualify`. It cannot satisfy the five-trial acceptance requirement.

## Tests

```bash
python3 -m unittest discover -s experiments/machine_tending/tests -v
```

The synthetic fixture is explicitly marked as nonexperimental. Its successful
times are 10 and 14 seconds, failure duration 6 seconds: 2/3 success, successful
mean/median 12 seconds, sample variance 8, and requested/accepted/completed
reposition totals 6/6/5. Tests also cover malformed records, duplicate IDs and
terminals, missing adapters, dangling attempts, inconsistent times, scenario
separation, nontrivial thresholds, HOME exclusion, raw checksum tampering,
empty input, repeated regeneration, table/chart sample counts, and nonzero PNGs.
The existing 48-test baseline is also required after coordinator changes.

AY-09 schema version 2.0 is preserved. New context/motion/adapter information
uses the schema's existing `details` objects; no old raw row is rewritten.
