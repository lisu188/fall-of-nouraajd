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

**21 original commits (21 trees) pass real build and headless startup** on the pinned
historical toolchain (GCC 5.4, Qt 5.5.1, Ubuntu 16.04): the first twenty trees of the
December 2013 line (`b9ae428b` … `a264a952`, catalog order #1–#20) and the 2026
reconstruction commit `108bdcbe`. Evidence for each is in `recovery/evidence/<commit>/`
and summarized in `recovery/progress.json`. These runs use only **unmodified surviving
original files**: the earlier root-era "compatibility repairs" that edited original
headers were removed, and the reconstructions were rewritten against the original APIs.
The earlier diagnostic evidence (GCC 15/Qt 5.15) for three commits is superseded.

Startup runs with Windows-style case-insensitive file lookup (`recovery/smoke/windows_paths.cpp`,
preloaded only into the game process): the game was developed on Windows and, from #20 on,
opens `config/items/Robe.json` while the file is `robe.json`. Exact paths behave as before.
The next tree needing manual work is reported by `history_workbench.py auto 21 …`.

All 365 trees restore with no unresolved inputs and no BFG markers. Most of the later
inputs are still the unverified donor proposals from the first checkpoint.

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

## Resume

```sh
git fetch origin && git switch <recovery branch> && git pull --ff-only
python3 recovery/toolchains/stage_sources.py --lock recovery/toolchains/sources-git.json /tmp/sources
docker build --build-context source-cache=/tmp/sources --build-arg RECOVERY_SOURCE_LOCK=sources-git.json \
    --tag nouraajd-recovery:qt5 recovery/toolchains        # see README for proxy-restricted hosts
export HISTORY_WORK_DIR=/path/to/scratch
python3 scripts/history_workbench.py auto 21 120    # carry forward until the first failing tree
python3 scripts/history_workbench.py prep N         # then reconstruct, build, keep, verify by hand
python3 scripts/history_workbench.py verify N
python3 scripts/history_workbench.py save && python3 scripts/history_workbench.py export
python3 scripts/history_workbench.py progress
```

## Remaining work

- Continue the chronological walk from #21 (December 2013 → April 2015), verifying
  each tree; replace unverified donor proposals with content-keyed reconstructions.
- Python-era trees: 40 declare several Python ABIs, 48 have initialization APIs that
  conflict with the declared ABI, and 18 use Python without declaring it, so recipe
  selection needs explicit per-tree recipes. 14 trees contain both `Game.pro` and
  `game.pro` (a case-only rename on Windows).
- 83 prefixed-era trees still need smoke-adapter mappings (their `CPlayer` is declared
  in a reconstructed header), and one lacks `map.h`.
- Replay the verified prefix under `recovery/bfg/` refs with `recover_history.py replay
  --evidence-dir recovery/evidence`, verify a portable bundle, and get the Historical
  recovery workflow green on GitHub.
