# Git LFS and legacy Git blobs

The repository uses Git LFS for selected CSV, rosbag and media assets. Run
`git lfs install --local` and `git lfs pull` inside a new checkout before
validating data. A file containing an LFS pointer is not the experiment data.

## AY-13 diagnosis (2026-11-05)

At base commit `eeca5d3492369f671a19e341c53af39d16789fe2`, the broad extension
rules in `.gitattributes` selected 22 paths. Ten were committed LFS pointers;
the other 12 were ordinary Git blobs: three Task2 assets, the trial CSV
template, six mass-sensitivity CSVs and two media files. All 12 working files
were byte-identical to their committed blobs.

With the LFS clean/process filters installed, Git compares a generated LFS
pointer against each ordinary committed blob and reports a modification.
A populated index can initially show a clean status because its cached stat
information avoids re-running the filter. A temporary index populated with
`git read-tree HEAD`, followed by `git update-index --refresh`, reproduced
exactly 12 modified paths without changing the checkout or real index.

## Correction

The root attributes now exempt exactly those 12 existing paths from the LFS
filter. Their diff and merge attributes return to Git's defaults, while
`-text` continues to preserve their exact bytes. The ten genuine LFS pointers
and the broad rules for new assets retain LFS handling. Paths are enumerated
in `.gitattributes`; moving one requires reviewing its attributes.

This correction changes attribute interpretation only. It does not migrate
data, replace archived blobs, update checksums, or rewrite history. Do not run
`git add --renormalize .` or an LFS history migration to hide this discrepancy.
Any future storage migration needs a separate reviewed change with archive
integrity checks.

Verification compares each exempt path's working bytes with its original Git
blob, and its filtered `git hash-object --path=PATH PATH` with `HEAD:PATH`.
A refreshed temporary index then reports no data-file changes. Published raw
checksums remain authoritative for hydrated experiment contents.
