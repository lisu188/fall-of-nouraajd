# Historical recovery status

The BFG-damaged history has been recovered, and on 2026-11-26 `main` was rewritten
into one linear history that starts with the recovered snapshots. This page records
the outcome. The tooling under `scripts/history_*.py` and `scripts/recover_history.py`
and the data under `recovery/` are kept as an archive of how the recovery was done.

## Objective and acceptance

Recover every BFG-damaged historical project tree, including reconstructed files
when exact originals cannot be found. Each distinct repaired tree must compile and
start its real game on Linux under Xvfb, with a loaded map/player, a rendered frame,
and clean shutdown. Exact originals and reconstructions are recorded separately.
Compiled binaries, installers, and IDE state are inventoried rather than recreated.

The read-only audit (`recovery/catalog.json`, frozen to `recovery/original-refs.json`)
found 367 affected commits and 365 distinct trees: 1,958 removed blob hashes across
747 paths, 72 locally surviving originals (82 with exact upstream matches), 636
generated/IDE versions, and 1,250 required versions that need reconstruction.
BFG removed the largest blobs, so the damage concentrates on the big core sources
(`creature.cpp`, `map.cpp`, `gamescene.cpp`, `interaction.cpp`, `stats.cpp`), the
vendored jsoncpp/zlib/tmxparser/Boost.Python sources, images, and often `Game.pro`.

## Outcome

- **Verification.** Draft PR #1697 reports pinned builds and startups for all 367
  cataloged damaged revisions (365 distinct trees), with the complete replay mapping
  `recovery/mappings/2026-11-23-complete-367-replay.json`. That PR was closed unmerged
  when its branch was deleted; GitHub keeps it as `refs/pull/1697/head`. The `recovery/`
  data in `main` is the earlier 93-snapshot checkpoint from PR #1660.
- **Linear history.** `main` now has 2,532 single-parent commits, one per former
  first-parent commit:
  - The first 362 commits (2013–2015) use the recovered trees without the per-commit
    recovery notes (README section, startup screenshot, verification and preparation
    files). Each stripped tree reproduces its recorded `restoredFilesFingerprint`.
  - Later trees are unchanged. Former merges became ordinary commits holding the merge
    result, so the 1,257 commits that existed only on side branches are folded into
    them, including 3 damaged side commits and the duplicate recovered copies that
    #1659 and #1698 had merged in.
  - Authors, committers and dates are unchanged. Every message was regenerated from the
    old message and the commit's diff.
  - The tip tree is identical to the pre-rewrite tip `268d11a6`.
- **Branches and tags.** Every other branch was deleted. Tags `v0.0.1`, `0.0.1` and
  `v0.0.2` point to the corresponding rewritten commits.
- **Commit IDs.** Every commit ID changed. `linear-history-map-2026-11-26.json` maps
  each former first-parent commit, and each recovered commit used from the complete
  replay, to its linear commit. IDs quoted in older PRs and issues, and in files under
  `recovery/`, refer to the pre-rewrite history.

Some removed files could only be reconstructed. Their exact original bytes remain
unavailable, and each reconstruction's provenance is in the override records.
Compilation and startup evidence do not establish historical gameplay parity.

## How reconstruction works

- **Content-keyed reconstructions.** An override entry with `originalBlob` applies
  wherever BFG removed that exact original blob, regardless of tree or path, so one
  reconstruction serves every tree that contained that file version. Precedence:
  exact original > commit-scoped entry > `originalBlob` entry > tree/global proposal.
  `replaceExisting` on an `originalBlob` entry repairs every surviving copy of that
  exact file (none are currently used).
- Reconstructions are written per version, walking the history in catalog order:
  start from the previous version's reconstruction and adapt it to the same-commit
  changes in surviving headers and callers (for example the developer's own edits to
  `player.cpp` or `item.cpp`). Provenance for each payload says what it was derived
  from. Payloads live in `recovery/payloads/reconstructions/<xx>/<blob>-<name>`.
- **Missing qmake projects** are regenerated from the tree's surviving
  `object_script.Game.Debug` (the exact compiled object list) with project settings
  from the nearest intact original `Game.pro`.
- `recovery/.gitattributes` keeps payload bytes exact; the repository-wide
  `* text eol=lf` rule had silently converted 13 CRLF/mixed-EOL upstream payloads.

## Toolchain

`recovery/toolchains/Dockerfile` builds the pinned image. Both Boost.Python and the
image's final checks now succeed: Boost 1.58 needed the upstream Python 3.3
`_Py_fopen` fix, and verbose build output is logged to files so BuildKit's 2 MiB step
log cap cannot hide failures. Where python.org/boost.io are unreachable, stage sources
with `stage_sources.py --lock sources-git.json` (CPython from the pinned release-tag
commits, Boost from the identical archive) and pass `--build-context source-cache=...`;
`http_archive_proxy.py` lets Xenial apt reach the archive through an HTTPS-only proxy.
See `recovery/toolchains/README.md`.

This host has no Docker. A sealed local Xenial filesystem was built with the same
pinned recipe and verified signed package/source inputs, then tested through
read-only `bwrap` mounts and an isolated network/display. Its content identity is
`sha256:d3f59ec1d12297ee8091fbea687aa619275fc92b3fd426560e0a1fa40715afc8`.
It contains GCC 5.4, Qt 5.5.1, CPython 2.7/3.3/3.4 and their Boost.Python libraries.
Compact provenance is in `recovery/toolchains/evidence/local-2026-11-15/`.
This local image identity is separate from any future CI-built image.

## Working with the pre-rewrite history

The recovery tooling reads the original damaged commits, which are no longer in `main`.
GitHub still serves them through pull-request refs:

```sh
git fetch origin refs/pull/1697/head:refs/recovery/complete-367  # final tooling, evidence and old history
git fetch origin refs/pull/1698/head:refs/recovery/old-main      # old main with the recovered old master
```

Run `scripts/history_workbench.py` and `scripts/recover_history.py` from a checkout of
`refs/recovery/complete-367`; the `docs/recovery/STATUS.md` in that revision describes
the workbench commands. Translate pre-rewrite commit IDs with
`linear-history-map-2026-11-26.json`.

The ancestry records `verified-ancestry-2026-11-15.json` (#1659) and
`verified-ancestry-2026-11-24-master-original.json` (#1698) described merge parents
that the rewrite removed. They were deleted from `main` and remain in the pre-rewrite
history.
