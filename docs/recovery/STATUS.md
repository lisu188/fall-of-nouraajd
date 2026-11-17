# Historical recovery status

Work in progress on recovering the BFG-damaged history. Recovery tooling and the
93-snapshot checkpoint were merged through PR #1660. PR #1659 connected the
65 published recovered commits to main ancestry. The resumed checkpoint is on
`codex/resume-bfg-recovery-20261116`. Existing branches and tags are preserved.

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

The continuation imports **55 additional exact original source/image payloads**
(1,387,269 bytes): fifty-two from the preserved pre-BFG object archive and three
CRLF variants derived from verified originals. Their Git blob hashes
match the BFG pointers; SHA-256 pins and provenance are in
`recovery/upstream/software-heritage/catalog.json` and
`recovery/upstream/layout-variants/catalog.json`. Compiled binaries remain inventoried.

The pinned local toolchain currently accepts **232 commits / 231 trees** against the
restored inputs: **221 game startups and 11 authored editor startups**. Each accepted
tree compiled, entered its real Qt event loop, rendered a frame and shut down cleanly
under isolated Xvfb. Game startups also require a loaded map and healthy player;
editor startups follow the surviving original editor entrypoint. Matching hashes,
compiler logs, startup records and screenshots are retained in
`recovery/evidence/<commit>/`. `recovery/progress.json` is authoritative and rejects
evidence with a different restored fingerprint or toolchain image identity.

Revision #98 has an original resource-manifest omission: genuine configuration
requests 21 interaction images that are already present in the same tree but absent
from its unchanged manifest. A hash-pinned supplemental qrc is generated only in an
isolated build copy. Its evidence and README explicitly identify this compatibility
boundary; it must not be reported as unmodified authored startup. Compilation and
startup evidence do not establish historical gameplay parity.

Revision #151 needs a hash-pinned build-only `std::hash<Coords>` specialization
that delegates to its genuine `CoordsHasher`; #152 supplies the authored fix.
Revision #340 needs the genuine parent reflection registration macro because its
unchanged macro calls a nonexistent constructor. Both compatibility paths retain
original bytes and export their exact generated headers and replay checks.
The reconstructed #114 project force-includes its genuine CharView header for a
missing declaration; #115 retains that redundant include and its newer original header.

**109 verified commits (#1–#108 plus #367) are published** under new refs:

- `recovery/bfg/2026-11-16/998e1e09c2ab203e7b5ad4a3a5b92fb39096cfa0`
- `recovery/bfg/2026-11-16/108bdcbeda04cefeba5e1895f91df023cea8487f`

`recovery/mappings/2026-11-16-prefix.json` records original-to-recovered identities.
All 65 previously published recovered commit IDs are unchanged. The 17,964,845-byte
portable bundle passed an independent clone without alternates and strict fsck of
2,113 reachable objects, plus parent-order, identity, original-file/mode and
README/frame checks. Its SHA-256 is
`bb630b209f4cce4ffd875a9c644c50fafc8a7271552a96e70bf97508e9758401`.
Compact verification accompanies the mapping; the earlier refs/bundle remain intact.

The first 65 recovered commits are already ancestors of main through merge commit
`c3f6bb647cc276a7ea245cc38cca333ec83abcfe`. The 93-snapshot checkpoint was merged as
`9acf3570ced5f0dcd8a9192184e169172d52ac28`. The additional 44 commits are published;
connecting their ancestry to main requires retaining the recovery branch's merge
parent. Squash or rebase merging would discard that connection. The owner waived
queued CI only for PRs #1659 and #1660; that waiver does not apply to this checkpoint.

The 2026-11-17 continuation accepted #177-#179, #183-#185, #194, #198-#199 and #200-#203
(an earlier commit message listed #194-#197 instead of #178, #194, #198 and #199; #195-#197
were already accepted). Rebuilt qmake projects for trees without an object listing now
follow `#include` chains into vendored directories, borrow settings from the
best-matching nearby reconstructed project (dropping `QT_NO_KEYWORDS` and Python
libraries when the earlier tree does not need them), and carry reconstructions across
file moves without ever replacing exact originals. The verifier treats a cached
success whose artifacts have moved as a cache miss instead of a startup failure.
Revisions #180-#182 are mid-refactor commits that cannot compile from their committed
contents (deleted per-class headers still included, missing jsoncpp `.inl` companions);
see `recovery/diagnostics/native-180-182-original-build-defects-2026-11-17.json`.
Their reconstructions are kept for carrying; no compatibility step exists for them yet.

All 365 trees restore without unresolved inputs or BFG markers, preserving every
surviving original file and mode. **Source readiness is not native acceptance.**
Most later replacements remain unverified donor proposals. The chronological walk
uses recorded Linux build-copy translations of surviving Windows include paths
and an empty save-directory prerequisite where required. Reconstructions are derived from same-version headers,
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

A real two-process save/reload regression exposed equipment bonuses being saved
as base stats in the missing Creature implementation (#71–#79). The corrected
reconstruction passes complete map/creature state comparison; it fails before the
fix. Both versions start and exit cleanly. The portable regression and compact
before/after proof are in `recovery/regressions/save-roundtrip/`.

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
python3 scripts/history_workbench.py auto 108 367 --verify  # stop at the first failure
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
  The next blocker is #186, the serialization refactor (`loadFromJson(std::string)`,
  default-only constructors); `recovery/progress.json` records the exact accepted set.
- Decide whether #180-#182 get a reviewed build-copy compatibility step, and finish the
  partial #176 conflict-adapter wiring.
- Replace later donor implementations that conflict with surviving APIs, including
  the remaining whole-game blockers around #257/#266. Object compilation and generator preparation
  are supporting evidence only.
- Extend verified replay/publication beyond the 109-commit publication and verify another
  independent portable bundle when ready. Preserve prior recovery publications.
- Obtain successful current-head GitHub build, full-suite and coverage evidence;
  the current queued jobs have supplied none yet. Keep the PR draft while acceptance
  is incomplete.
