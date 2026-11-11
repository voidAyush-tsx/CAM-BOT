# Validation of the acceptance documentation change

Recorded 2026-11-12 (Asia/Calcutta), in a separate Codex checkout based on
`6df990b9fd990328f0222f8249d59438ee31dc83`. This file describes fresh offline
checks while recording the user's evidence; it is not another ROS runtime run.

| Check | Result |
|---|---|
| `python3 tools/check_ay13_docs.py` | PASS: 13 statuses/ledger records, evidence paths, links and ROS source contracts, including maintained source inventory. |
| `python3 -m unittest discover -s experiments/machine_tending/tests -v` | PASS: 14 tests. |
| `python3 -m unittest discover -s tools -p 'test_*.py' -v` | 31 tests passed; one module import error (`test_ay05_ros_probe`, missing `rclpy`). Its seven ROS-dependent tests could not run in this shell. The uploaded Humble replay separately records all 38 tool tests passing. |
| AST parsing of tracked Python and `bash -n` for tracked shell files under source/tools/analysis paths | PASS: 64 Python, 10 shell files. |
| `git lfs pull`; `git lfs fsck` | PASS. Initial analysis CSV comparisons encountered LFS pointers in this clone; fetching the objects resolved that setup issue. |
| Uploaded archive SHA-256 and member manifest | PASS: original checksum and all 146 member sizes/hashes match. |
| `check_ros_shutdown.check_shutdown` against all enclosed launch logs | PASS: 11 launches, three clean child exits each. All 22 initial/residual-node files empty. |
| Uploaded regenerated analysis versus repository's published analysis | PASS: seven file-by-file byte comparisons after LFS retrieval. |
| Links in new acceptance record and context update | PASS using `local_link_errors`. |
| `git diff --check` | PASS. |
| Diff of `src`, `tools`, `experiments`, `artifacts` against tested base | Empty; implementation and sealed experimental artifacts unchanged. |

The 70 Colcon results and live ROS scenarios in the acceptance record are from
the reviewer's uploaded Humble run. They were not rerun in this recording shell.
