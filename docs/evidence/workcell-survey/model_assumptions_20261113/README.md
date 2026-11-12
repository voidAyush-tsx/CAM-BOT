# Model-assumption survey intake review

Reviewed 2026-11-13 (Asia/Calcutta). **PASS as an assumption baseline only.**
Task 6's measured-geometry and controller-target requirements remain pending;
AY-13's accepted visual reproducibility scope is unchanged.

Ayush Ranjan supplied this packet after cloning merged `main` at
`138e1059189c2c5e79b82ed4daf2a9fb4f62d08d` (PR #6). Its provenance timestamp is
`2026-11-13T01:14:19.564074+05:30`. The packet was prepared at
`/home/ayush/cambot-survey-work.vxICIz/packet`.

## Original files and integrity

- [Original archive](cambot-survey-packet.oI05hp.tar.gz), retained unchanged.
- [Original checksum](cambot-survey-packet.oI05hp.tar.gz.sha256), retaining the
  submitter's absolute filename.
- [Member inventory](manifest.json), generated during inspection.
- [Review results](review.json), including all 31 consistency checks and
  derived assumed world positions.

Archive SHA-256:
`fca3128b5ab1799d3d150fd8057da6d3dfebb7b47aad72349a27730456c3126e`.
The five enclosed files are:

| File | Meaning |
|---|---|
| `repository-commit.txt` | Source checkout identity. |
| `evidence/model-config.json` | Exact configuration snapshot from that commit. |
| `survey.assumed.json` | Populated model station geometry and interaction offsets, labelled ASSUMED. |
| `survey.json` | Original blank measurement template; not a second completed survey. |
| `station_targets.json` | Original blank target template; no taught configurations. |

The configuration snapshot SHA-256 is
`a973226b7e02b7da1cdb96954990e61abe12a07867bfad678bbd07b3f3c8a64e`.
It matches both the provenance reference and the Git blob bytes at the recorded
commit. The blank files also match their committed templates byte-for-byte.

## Findings

Five station poses/dimensions and six station-local interaction positions
match the source configuration. Parent/child frame identifiers, metre/radian
units, positive dimensions, finite pose values and provenance references are
consistent. All recorded station rotations are zero. Applying the repository's
`target_world_xyz` transformation gives these **assumed**, not measured, points:

| Interaction | World XYZ (metres) |
|---|---|
| RAW_PICK | 0.75, 0.85, 0.76 |
| STAGE_INSPECT | 0.15, 1.05, 0.76 |
| MACHINE_LOAD | -0.65, 0.75, 0.95 |
| MACHINE_UNLOAD | -0.65, 0.75, 0.95 |
| OUTPUT_UNLOAD | -0.75, -0.45, 0.76 |
| FINISHED_PLACE | 0.35, -0.95, 0.76 |

LOAD and UNLOAD remain separate operations despite sharing an assumed position.
These points do not establish UR5 TCP targets, tool orientation, reachable
gripper poses or collision clearance.

HOME and S1–S5 candidate records retain null joint vectors and NOT_RUN
validation gates, with the correct six-joint ordering. The existing runtime
loader rejects all three intake JSON files as executable controller plans.
The archive checksum and source comparisons are offline inspection results;
no fresh ROS, controller or physical test was performed for this intake.

Fresh repository validation: `python3 tools/check_ay13_docs.py` passed;
`python3 -m unittest src/carrier_control/test/test_launch_preflight.py -v`
passed both existing tests. The original archive and all five member hashes,
new documentation links, null physical inputs and `git diff --check` passed.
No working source, runtime configuration or previously retained evidence changed.

## Remaining inputs and next action

| Missing input | Required evidence |
|---|---|
| Actual robot and calibration | Model/asset identification and calibration reference. |
| World frame and base placement | Origin/axes definition and measured world-to-base transform. |
| Station survey | Measured poses/dimensions, method and uncertainty. |
| Mounted assembly | Dimensioned CAD or measurements, mounting transforms and actual tool frames. |
| Interaction requirements | Tool orientation and approach/retreat paths for all six operations. |
| Carrier/controller targets | Taught HOME/S1–S5 configurations, path/collision/clearance checks and controller feedback. |

The [survey guide](../../../WORKCELL_SURVEY.md) describes how to collect these
inputs separately. For a CAD-only continuation, the next useful input is a
dimensioned assembly drawing/model with a revision and named tool frames;
it must remain CAD_ONLY until measured. If only the existing placeholder is
available, retain this packet as ASSUMED and leave physical validation open.

The [existing preliminary workspace study](../../../../experiments/workspace/README.md)
already analyzes this configuration. Copying its values into a survey packet
adds traceability, not new geometry or controller evidence. Do not repeat the
same analysis merely to turn these missing gates into apparent progress.
