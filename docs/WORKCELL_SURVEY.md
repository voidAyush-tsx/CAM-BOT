# Workcell survey and controller-target intake

This is the preparation for Task 6. It does not supply measured geometry,
taught targets or controller validation. Current task dispositions remain in
[STATUS.md](STATUS.md). AY-13 covers visual reproducibility and is independent
of this work.

## What already exists

At merged source `bc24ec61cdfde98a99e651042ca8e4b3d6e97521`,
[machine_tending.json](../src/carrier_control/config/machine_tending.json)
explicitly labels workcell dimensions as temporary visual assumptions. S1–S4
controller vectors are unvalidated and S5 has no controller vector. The
[flange model](../src/carrier_description/urdf/carrier_flange.xacro) labels its
dimensions as reconstruction values. None are substitutes for measurements.

The [preliminary model study](../experiments/workspace/README.md) already
provides 20,006 kinematic samples, five assumed placement comparisons and a
live FK/TF cross-check. It does not establish collision-free reachability,
surveyed geometry or physical station targets. Repeating that study alone
would not complete Task 6.

## Create a separate survey packet

Use a new directory outside the working demonstration configuration:

```bash
survey_dir="$(mktemp -d "$HOME/cambot-survey.XXXXXX")"
cp docs/templates/workcell-survey/survey.template.json "$survey_dir/survey.json"
cp docs/templates/workcell-survey/station_targets.template.json "$survey_dir/station_targets.json"
printf 'Survey packet: %s\n' "$survey_dir"
```

The [survey template](templates/workcell-survey/survey.template.json) contains
five station records and six interaction points using the existing identifiers.
The [candidate-target template](templates/workcell-survey/station_targets.template.json)
contains HOME and S1–S5. Unknown measurements and joint vectors are `null`;
validation states start at `NOT_RUN`. Do not replace unknowns with zero.
These files are intake documents, not launch configurations, and no runtime
loader consumes them. They deliberately omit `controller_validated` so filling
out a form cannot enable execution.

## Survey conventions and provenance

1. Identify the actual robot model, asset/serial and calibration file. Record
   a file reference and SHA-256. The existing UR5 visual model does not identify
   or calibrate a physical robot.
2. Define a right-handed `world` frame: its origin and positive axes. Measure
   `world → base_link` against that definition. Each transform maps child-frame
   coordinates into its parent: `p_parent = Rz(yaw) Ry(pitch) Rx(roll) p_child + t`.
   All translations/dimensions are metres; roll, pitch and yaw are radians.
3. Measure all five station poses and dimensions. Describe the station origin
   in the provenance method so offsets can be reproduced. Record transforms
   for the mounted assembly and the relevant actual tool frames. Preserve the
   official UR5 chain above `tool0`; do not infer flange/module dimensions from
   placeholder geometry.
4. Measure each interaction point in its named `reference_frame`. The template
   uses station-local frames; change the field explicitly if recording world
   coordinates. Required tool RPY is the tool orientation in that same frame.
   Approach and retreat directions are separate unit vectors in that frame,
   pointing in the direction of travel toward contact and away from contact,
   respectively. Distances are nonnegative metres. Record the actual tool frame
   name; an interaction point is not automatically a carrier TCP target.
5. Give every measurement a `provenance_id` matching a `provenance_records` ID.
   Create additional provenance records whenever person, date, instrument,
   source, method or uncertainty differs. Use `source_kind` values `measured`,
   `cad`, or `assumed`, with timezone-qualified timestamps. Record per-axis
   uncertainty and its basis (for example instrument bounds or a stated
   confidence level). A missing uncertainty stays null; zero requires support.
   Each `evidence_files` entry should record a path and SHA-256. Use relative
   paths within the survey packet so another person can inspect the sources.

For CAD-only work, set the packet status to `CAD_ONLY` and retain CAD revision
and units. For assumptions, use `ASSUMED`. Neither status means measured.
Use `MEASURED_PENDING_REVIEW` only after actual measurements are entered;
identify unresolved items in the review record. No physical measurement has
been supplied with these templates.

## Teach and validate candidate carrier targets

After assembly and frames are established, a qualified operator can teach
candidate carrier configurations through the robot's normal teaching procedure.
Record the survey ID/hash, calibration reference, assembly revision, controller
identity and teaching record. Fill `joint_positions_rad` with six finite angles
in this exact order, matching `joint_order` in the template:

```text
shoulder_pan_joint
shoulder_lift_joint
elbow_joint
wrist_1_joint
wrist_2_joint
wrist_3_joint
```

Record the required mounted-module pose and approach/retreat path references.
S3 serves both MACHINE_LOAD and MACHINE_UNLOAD; demonstrate suitability for
both or document the need for distinct poses. HOME also needs review for the
actual assembly and cell. Its legacy configuration flag is not physical proof.

For each validation gate, retain `NOT_RUN`, `PASS` or `FAIL` with supporting
evidence, reviewer/date and the criteria used:

| Gate | Evidence needed |
|---|---|
| Joint limits | Configuration checked against the calibrated robot/controller limits. |
| Target alignment | Actual mounted module/tool pose, orientation error and tolerance against the surveyed interaction requirement. |
| Approach/retreat | Full paths and transitions, with assumptions and clearances recorded; endpoints alone are insufficient. |
| Self-collision | Robot plus mounted assembly geometry and result over the path. |
| Environmental clearance | Station/obstacle model, minimum clearance, margin and measurement uncertainty. |
| Controller execution and feedback | Selected controller, command/actual joint feedback, timestamps, tracking tolerance, action result, and cancellation/failure observations. |

Set a candidate's status to `TAUGHT_PENDING_VALIDATION` when teaching is
recorded. Use `VALIDATED_PENDING_INTEGRATION` only after its gates pass with
evidence; keep failures and retests as distinct records. A template's status is
not an execution authorization. Do not run existing visual joint targets on
physical hardware or flip runtime validation flags to bypass these gates.

## Handoff and later integration

Return the two completed JSON files and their referenced measurement/CAD,
teaching and controller evidence. Basic JSON parsing can be checked with:

```bash
python3 -m json.tool "$survey_dir/survey.json" >/dev/null
python3 -m json.tool "$survey_dir/station_targets.json" >/dev/null
```

Parsing establishes syntax only. Integration still requires semantic review
of frames, units, uncertainty, calibration, all six joint values, all six
interaction points, complete validation evidence and assembly compatibility.
Preserve the survey packet unchanged once submitted; corrections use a new
revision and retain their provenance.

The current workcell parser intentionally accepts only the visual-assumption
contract. A separately reviewed implementation will be needed to support
measured configurations, selected controller bring-up and any new tool frames.
It must preserve the existing visual mode and fail-closed controller behavior.
Until those inputs and checks exist, Task 6 remains pending; the intake packet
does not complete it or alter AY-13's accepted visual scope.
