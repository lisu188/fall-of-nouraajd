# Historical recovery status

Work in progress on recovering the BFG-damaged history. The tooling branch is
`recovery/bfg-history` (draft PR #1653); follow-up increments are stacked on it.
Existing branches, tags, and `main` are preserved.

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

## Current state

The continuation imports **53 additional exact original source/image payloads**
(1,375,733 bytes): fifty from the preserved pre-BFG object archive and three
CRLF variants derived from verified originals. Their Git blob hashes
match the BFG pointers; SHA-256 pins and provenance are in
`recovery/upstream/software-heritage/catalog.json` and
`recovery/upstream/layout-variants/catalog.json`. Compiled binaries remain inventoried.

The pinned local toolchain has now revalidated the earlier checkpoint and accepted
**74 commits / 74 trees** against the current restored inputs (catalog #1–#73 and
#367). Each accepted tree compiled and started its real game under isolated Xvfb,
with map/player, rendered frame and clean shutdown. Matching hashes, compiler logs,
startup records and screenshots are retained in `recovery/evidence/<commit>/`.
`recovery/progress.json` is the authoritative current count; it rejects evidence
whose restored fingerprint or explicit toolchain image identity no longer matches.

**65 verified commits (#1–#64 plus #367) are published** under new refs:

- `recovery/bfg/2026-11-15/e1131adb2c47336c7dbe62dee0246216feb554eb`
- `recovery/bfg/2026-11-15/108bdcbeda04cefeba5e1895f91df023cea8487f`

`recovery/mappings/2026-11-15-prefix.json` records original-to-recovered identities.
A 14,437,423-byte portable bundle was independently cloned without alternates and
passed strict fsck, topology/identity checks and documentation/frame verification.
Its SHA-256 is `e5a86fa8f5d69a74fb2727ae8c49ba70a0eb18f1cb3bb9e2d590a6baac4d5ad6`;
compact verification and publication records accompany the mapping. Existing
branches/tags are unchanged. The continuation PR is draft #1658, stacked on the
explicitly approved PR #1655 branch; it has not been merged.

All 365 trees restore without unresolved inputs or BFG markers, preserving every
surviving original file and mode. **Source readiness is not native acceptance.**
Most later replacements remain unverified donor proposals. The chronological walk
has reached #79, where a surviving Windows include path requires a recorded Linux
build-copy translation. Reconstructions are derived from same-version headers,
callers and configuration; underdetermined formulas, map transitions and layouts
are labeled as inference. Compilation/startup do not prove historical gameplay parity.

Startup uses case-insensitive Windows file lookup only in the game process
(`recovery/smoke/windows_paths.cpp`), including the original `Robe.json`/`robe.json`
mismatch. Verification force-includes `<functional>` as recorded in `qt5.json`;
original MinGW headers supplied it transitively. Missing Windows zlib import
libraries are aliased to the installed library with the same API. No original
source or packaged binary is replaced for these compatibility steps.

Linux qmake selection follows the active application and declared subdirectory
dependencies. Reconstructed projects resolve the historical case-only project
rename; intact projects are unchanged. Combined creature/player headers and
Python 2.7 binding reconstructions now follow the surviving APIs. The reconstructed
binding compiles as a real native object at #260 and #266 and exports `init_game`;
those whole games still fail on other unverified donor sources and are not accepted.

Where surviving `preprocessor.py` generates property headers, verification runs
that exact generator under pinned Python 2.7.18 in the private build-source copy.
Inputs, outputs and hashes are recorded separately from the restored snapshot.
The real generators at #250 and #257 succeeded; this proves preparation only.

GitHub has no forks. Three sampled missing-blob API probes returned HTTP 404;
this does not prove all originals unavailable. Fetching exact catalog commit SHAs
recovered 44 missing original commits without replacing refs. The 1,432 unique
original tips are pinned under new local preservation refs. The clone still uses
read-only object alternates, which must be retained.

GitHub's build and Historical recovery jobs for the latest pushed checkpoint
remain pending. No GitHub compilation, full-suite or coverage success is claimed.

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

## Resume

```sh
git fetch origin && git switch <recovery branch> && git pull --ff-only
python3 recovery/toolchains/stage_sources.py --lock recovery/toolchains/sources-git.json /tmp/sources
docker build --build-context source-cache=/tmp/sources --build-arg RECOVERY_SOURCE_LOCK=sources-git.json \
    --tag nouraajd-recovery:qt5 recovery/toolchains        # see README for proxy-restricted hosts
export HISTORY_WORK_DIR=/path/to/scratch
python3 scripts/history_workbench.py auto 74 367 --verify  # stop at the first failure
python3 scripts/history_workbench.py prep N         # then reconstruct, build, keep, verify by hand
python3 scripts/history_workbench.py verify N
python3 scripts/history_workbench.py save && python3 scripts/history_workbench.py export
python3 scripts/history_workbench.py progress
```

On a Linux host without Docker, retrieve the `historical-qt5-toolchain` artifact from
a successful Historical recovery toolchain job. Verify/materialize its Docker-save
archive with `scripts/history_rootfs.py materialize image.tar.gz /absolute/rootfs
--image-id <Id-from-image.json>`, then set `HISTORY_TOOLCHAIN_ROOTFS` to that directory
and `HISTORY_WORK_DIR` to a separate writable scratch directory. The workbench uses
the image's own compiler, libraries and controller through isolated `bwrap` namespaces;
the source/Git stores are read-only. Run one previously verified commit first.

Catalog positions enumerate 367 commits, not 365 distinct trees. Keep compact
exported evidence before removing reproducible build scratch.

## Remaining work

- Continue the chronological reconstruction/build/startup walk through all 365 trees.
  Finish the #79 Windows include compatibility and version-specific map serialization.
- Replace later donor implementations that conflict with surviving APIs, including
  the whole-game blockers at #260/#266. Object compilation and generator preparation
  are supporting evidence only.
- Extend verified replay/publication beyond the 65-commit prefix and verify another
  independent portable bundle when ready. Preserve prior recovery publications.
- Obtain successful current-head GitHub build, full-suite and coverage evidence;
  the current queued jobs have supplied none yet. Keep the PR draft while acceptance
  is incomplete.
