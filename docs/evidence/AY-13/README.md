# AY-13 documentation verification

Run date: 2026-10-15. Checkout branch:
`feature/ay10-ay12-visual-experiments`; pre-documentation HEAD:
`7409988`. These logs were produced with the documentation/tool changes in
the working tree, then committed together. The final commit identifies the
reviewable version.

- [source contract](source_contract.log): local links, 13 AY rows/ledger
  records, evidence paths, source launch/executable names and scope markers.
- [checker fixture tests](doc_checker_tests.log): missing link, valid link,
  duplicate/missing status and phantom launch/executable cases.
- [Humble contract](humble_contract.log): sourced Distrobox ROS package
  installation, Xacro/URDF parse, and installed executable list.

The checks do not constitute the requested **second-person** clean-checkout
repeat. [Reviewer instructions](../../ayush/README.md) specify that remaining
acceptance step. The earlier [48-test baseline](../AY-10/final_tests.log) is
retained; no CAM-BOT ROS behavior source was changed in AY-13.

The later [cross-validation run](cross_validation/README.md) found that
repository-wide Colcon discovery sees archived AY-10 source copies as duplicate
packages. The reproducible build now uses `--base-paths src`. It also
identified preexisting lint failures and an AY-06–08 capture shutdown leak;
both repairs and their before/after logs are retained there.
