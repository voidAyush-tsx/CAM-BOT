# AY-13 independent clean-checkout acceptance

Accepted 2026-11-12 (Asia/Calcutta) for **visual ROS 2 Humble reproducibility**.
Reviewer: **Ayush Ranjan**. The reviewer supplied the runtime archive, reported
PASS and no visual problems, and explicitly clarified their role as
“independently review someone else’s implementation”. Independence is recorded
on the basis of that declaration. Codex inspected the evidence and recorded
the acknowledgement; it did not perform or witness the human desktop review.

## Provenance and retained evidence

- Tested branch: `feat/ay13-reproducible-rviz`.
- Tested source: `6df990b9fd990328f0222f8249d59438ee31dc83`.
- Separate checkout: `/home/ayush/cambot-review.cL0yGL/repo`.
- Host: CachyOS, Docker 29.9.2, Wayland/XWayland `DISPLAY=:1`.
- Container: Ubuntu 22.04.5, ROS 2 Humble, Python 3.10.12, Matplotlib 3.5.1.
- Image ID: `sha256:e8020c7bfd5c805bb67c5bb24c8650dcbeacff4893e80ab8599110877180e4c6`.
- RViz 11.2.29 source: `4e2b27b7561da7eb03fbc7e92a74d4b3f1e0b054`, with the
  tracked timer-stop patch. Build and replay logs select the patched library.
- Runtime captures: 2026-11-11 UTC. Manual trial ran 18:23:57–18:24:20 UTC
  (23:53:57–23:54:20 Asia/Calcutta); acknowledgement recorded 2026-11-12.

The [original archive](independent_review_20261112/cambot-ay13-review.Lm71RR.tar.gz)
and [original checksum file](independent_review_20261112/cambot-ay13-review.Lm71RR.tar.gz.sha256)
are retained byte-for-byte. Archive SHA-256:
`b7f67d669cf1265e8cf2b16c41b40c838b6e8a3dec64dac9ee2c24e1ef4b4d57`.
The [manifest](independent_review_20261112/manifest.json) inventories 146 enclosed
files; it was generated during inspection, not at capture time. The original
checksum file includes the reviewer's absolute path. To verify and inspect
without modifying repository evidence:

```bash
python3 - <<'PY'
import hashlib, json, pathlib, tarfile, tempfile
base = pathlib.Path('docs/evidence/AY-13/independent_review_20261112')
manifest = json.loads((base / 'manifest.json').read_text())
archive = base / manifest['archive']
assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['archive_sha256']
assert (base / (archive.name + '.sha256')).read_text().split()[0] == manifest['archive_sha256']
output = pathlib.Path(tempfile.mkdtemp(prefix='cambot-human-review-'))
with tarfile.open(archive) as bundle:
    members = bundle.getmembers()
    assert all(m.isfile() or m.isdir() for m in members)
    assert {m.name for m in members if m.isfile()} == set(manifest['files'])
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        if member.isfile():
            data = bundle.extractfile(member).read()
            expected = manifest['files'][member.name]
            assert len(data) == expected['bytes']
            assert hashlib.sha256(data).hexdigest() == expected['sha256']
            destination = output / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
print(output)
PY
```

Fresh checks of this documentation/evidence change, including the local ROS
dependency limitation, are recorded in
[recording validation](independent_review_20261112/recording_validation.md).

## Acceptance gates

Paths below are inside that archive. `replay` abbreviates
`evidence/replay-attempt.Q83wDN/replay`; `manual` abbreviates
`evidence/manual.X5XWOl`. The commands executed by the technical runner are
retained in `tools/cloud/validate_humble.sh` at the tested commit.

| Gate | Observed result and evidence |
|---|---|
| Separate checkout, dependencies and provenance | PASS: `evidence/checkout-sha.txt`, `evidence/image-id.txt`, `evidence/docker-build.log`, `replay/environment.txt`, `replay/lfs-fsck.log`, `replay/rosdep-check.log`. Clean Git status recorded before and after replay. |
| Scoped build and tests | PASS: two packages built; `replay/colcon-test-result.log` records 70 results, 0 errors, 0 failures, 2 skips. The skips are the existing copyright checks. |
| Model and installed assets | PASS: `replay/cambot.urdf`, `replay/check-urdf.log`, `replay/installed-doc-check.log`. |
| Visual graph | PASS: one coordinator joint-state publisher in each scenario and `manual/joint-state-publishers.txt`; initial and residual node files empty. |
| Manual one-shot cycle | PASS: `manual/start-service.txt`, topic logs, `manual/trials.csv` and 106 sequential events in `manual/trials.events.jsonl`. Five repositions, `FINISHED_AT_S5`, completed HOME motion and `HOME_END`, final SUCCESS. |
| Reproduction, checks and analysis | PASS: 38 tool tests, 14 analysis tests, 26 legacy offline component checks, 64 Python/10 shell syntax checks. `replay/analysis-comparison.log` records three numerical comparisons and seven byte matches in a new output directory. |
| Identified human review | PASS: [reviewer acknowledgement](independent_review_20261112/reviewer_acknowledgement.json), including the subsequent explicit declaration of independent review. |

The technical replay additionally passes normal completion, unreachable-target
classification (`RECHECK_STILL_UNREACHABLE`), injected load failure, cancellation,
idle shutdown and five active interruptions. All ten automated launches and the
manual launch have three clean child exits and empty residual-node records.
Four enclosed rosbag SQLite databases passed read-only integrity checks during
inspection. The expected controller rejection, “station S1_RAW target is not
controller-validated”, is a passing fail-closed check, not a visual failure.

The reviewer used `docker buildx build --load --progress=plain` with the CA
secret, ran `validate_humble.sh /evidence/replay` under Xvfb, and then launched
`dual_arm_demo.launch.py auto_start:=false enable_coordination:=true
trial_count:=1 visual_time_scale:=1.0 results_file:=/evidence/trials.csv` on
their desktop. They called `/machine_tending_coordinator/start`, captured the
three state/decision topics and graph, then checked shutdown and residual nodes.
The GUI container used the host UID/GID, scoped X access, `QT_QPA_PLATFORM=xcb`,
`LIBGL_ALWAYS_SOFTWARE=1`, domain 99 and localhost-only ROS discovery.

## Reviewer acknowledgement and limits

Verbatim statements supplied in the chat:

> Reviewer name: Ayush Ranjan  
> Involvement in implementing CAM-BOT: good  
> What you personally observed in RViz: it was working fine  
> Any visual problems: no  
> Conclusion: PASS

On clarification of implementation involvement:

> independently review someone else’s implementation

The brief personal observation is retained as given; the detailed FSM, workpiece,
HOME and graph claims above come from logs, not invented reviewer quotations.
There is no screenshot in this upload. The shell's missing host Jazzy setup
warning did not affect the Humble container. Earlier Buildx/package-mirror/APT
and deleted-temporary-checkout problems preceded this successful persistent
checkout run; this archive retains the successful build and replay, not a
complete history of those earlier attempts.

**Conclusion: AY-13 acceptance PASS, visual scope only.** The new acceptance
commit changes documentation/evidence only; runtime provenance remains the
tested `6df990b` source. Historical agent-only records and their open-gate notes
remain unchanged as dated records. No controller, grasp, collision or physical
operation is verified. All corresponding verification flags remain false.
The new manual timing is not pooled into the sealed AY-10 experiment.
