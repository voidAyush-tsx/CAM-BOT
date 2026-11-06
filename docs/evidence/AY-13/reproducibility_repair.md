# AY-13 documentation repair validation

Date: 2026-11-05 (Asia/Kolkata). Base: `eeca5d3492369f671a19e341c53af39d16789fe2`.
Branch: `repair/ay13-reproducibility-docs`.
Environment: Debian 13, Python 3.12.14, pytest 9.2.0, Matplotlib 3.11.2.
This is an agent-run offline repair check, not an independent human replay.
AY-13 remains **IN PROGRESS**. No fresh ROS runtime pass is claimed.

## Changes

- Restored the project README from the pre-handoff version, retaining project
  identity, architecture and visual-only results. Removed handoff-only claims
  and the nonexistent setup-script reference.
- Updated clone/review guidance for `main`, an exact review ref and local
  `work`; scoped builds/tests to `src`; required coordinated visual launch.
- Allocated new output directories for demonstrations, capture and analysis.
  Classified fixed-output legacy capture scripts as historical references.
- Distinguished later AY-06–08 runtime probes from missing original evidence;
  kept the original AY-09 one-trial runtime directory explicitly absent.
- Added exact-path LFS exceptions for 12 ordinary Git blobs. See the
  [LFS diagnosis](../../GIT_LFS.md) for reproduction and storage boundaries.

## Executed checks

Commands ran from the repository root with `/workspace/cambot-venv/bin/python`
and `PYTHONDONTWRITEBYTECODE=1`. Rendering used `MPLBACKEND=Agg` and
`MPLCONFIGDIR=/tmp/cambot-mpl`. Temporary output was written outside the repo.

| Check | Result |
|---|---|
| `python tools/check_ay13_docs.py` | PASS: all 13 status/ledger records, links, evidence paths and source contracts. |
| `python -m unittest tools/test_check_ay13_docs.py tools/test_generate_build_report.py -v` after final ledger edits | 7 passed. |
| Existing offline pytest selection below | 74 passed, zero failures or skips within the selection; six ROS ament lint modules excluded. Includes 14 analysis tests and documentation/report fixtures. |
| `python tools/validate_ay09_dataset.py experiments/machine_tending/runs/ay10-visual-20261015-03/raw/trials.csv` with `PYTHONPATH=src/carrier_control` | PASS: five trials, 530 events. |
| Analyzer CLI with that raw CSV, `--qualify`, and a new `/tmp` output | VISUAL_SIMULATION_PASS: five archived trials; raw checksums/source/reset observations verified. No new trials collected. |
| Generated `trials.csv`, `summary.csv`, `metrics.json` comparison | All three byte-match published contents; pointer-backed tables compared against their LFS SHA-256 identities. Numerical results unchanged. |
| Generated plots and `artifacts.json` comparison | Three PNGs and rendering byte counts differ with Matplotlib 3.11.2 versus recorded 3.5.1. Published files preserved. |
| Python AST parsing / Bash syntax | PASS: 53 live Python files, eight capture scripts, 23 Bash documentation blocks. |
| Additional local-link checks | PASS across all eight repaired/new Markdown documents. |
| Source inventory | All 56 retained source hashes match. |
| Protected-content comparison to pre-edit snapshot | All 387 existing source/evidence/artifact/archive/media files remain byte-identical. |
| Git/LFS | Reproduced 12 false modifications with a temporary index; after exceptions all 12 filtered hashes match original blobs and all ten genuine LFS paths retain their filter. |
| `git diff --check` | PASS. |
| `python tools/verify_ay.py --output /tmp/cambot-ay13-validation/static-verification.json` | 25/26 legacy static checks pass; exit 1 for the stale package-install assertion described below. |

The offline pytest selection was executed by the existing cloud helper using:

```bash
PYTHONPATH=src/carrier_control python -m pytest \
  src/carrier_control/test src/carrier_description/test \
  tools/test_check_ay13_docs.py tools/test_generate_build_report.py \
  experiments/machine_tending/tests \
  --ignore=src/carrier_control/test/test_copyright.py \
  --ignore=src/carrier_control/test/test_flake8.py \
  --ignore=src/carrier_control/test/test_pep257.py \
  --ignore=src/carrier_description/test/test_copyright.py \
  --ignore=src/carrier_description/test/test_flake8.py \
  --ignore=src/carrier_description/test/test_pep257.py -q -p no:cacheprovider
```

The superseded `verify_ay.py` package check demands the literal text
`glob('config/*')` in `carrier_control/setup.py`. The setup instead uses the
existing `asset_files('config')` helper. Both files are unchanged from the
base commit; the current package integration tests pass. Its message
`config not installed` is a stale static assertion, not a demonstrated
installation failure. No ROS installation check was possible. This legacy
checker issue is left for a separate tooling change.

## Required independent verification

Ubuntu 22.04 / ROS Humble is still required for rosdep, scoped Colcon build
and tests (including excluded ament checks), installed assets, Xacro/URDF,
RViz and a new live coordinated visual cycle. This cloud machine has no
Humble installation; its active policy still blocks `packages.ros.org`.

An identified second person must use a clean checkout of the exact review
commit with LFS data, observe one authoritative joint-state publisher,
the full FSM and `FINISHED_AT_S5`, both coordination branches and TF rechecks,
record commands/results/deviations, and sign off as described in the
[review guide](../../ayush/README.md). Controller actuation, bimanual/grasp
feedback and physical CNC operation remain unverified.
