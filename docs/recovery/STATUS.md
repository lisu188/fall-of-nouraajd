# Historical recovery status

Work in progress on recovering the BFG-damaged history. Recovery tooling and the
93-snapshot checkpoint were merged through PR #1660. PR #1659 connected the
65 published recovered commits to main ancestry. The current continuation builds on the #204 checkpoint in draft PR #1677.

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

The pinned local toolchain currently accepts **324 commits / 322 trees** against the
restored inputs: **313 game commits and 11 authored editor commits**. Each accepted
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

The November 23 local bundle extends the verified ancestry through #179 and includes
the independently rooted #367. Its 180 commits preserve all 109 published IDs.
An independent bare clone with no alternates passed strict fsck across 3,551 reachable
objects. The check compared parent order, identities, file modes and bytes, README
evidence and startup frames. The 21,116,789-byte bundle has SHA-256
`4f6c5c6091bf059005e9b243d2229bce966830362269437f16b0637f5994196f`.
The mapping and verification are in `recovery/mappings/2026-11-23-prefix*.json`.
The 71 additional IDs are local to the verified bundle.

The follow-up local bundle extends the verified ancestry through #203 and includes
#367. An independent bare clone passed strict fsck across 204 commits and 4,004
reachable objects, preserving all 180 IDs from the #179 bundle. The mapping and
verification are in `recovery/mappings/2026-11-23-through-203-prefix*.json`.
Its SHA-256 is `41e24771115b9f7538d146654bde9acdd8e63f245a8005e68c7a4b6da48ed524`.

The #223 bundle extends local replay to #1–#223 and #367. The independent clone
passed strict fsck across 224 commits and 4,273 reachable objects and preserved
all 204 IDs in the #203 bundle. The mapping and verification are in
`recovery/mappings/2026-11-23-through-223-prefix*.json`.

The current local bundle covers #1–#272 and #367, preserving all 224 commit IDs
from the #223 bundle. The independent clone passed strict fsck across 273 commits
and 5,406 objects. Its SHA-256 is
`42dfa7a45388e2886933b5924287fecb132326ed9e55946f0d5a7d72e1f6b2f6`. The review records are in
`recovery/mappings/2026-11-23-through-272-prefix*.json`.

The #273 bundle extends the verified ancestry by one revision while preserving
the 273 previously bundled IDs. Its independent clone passed strict fsck across
274 commits. Revision #273 uses the preceding compatible map body and a pinned
build-copy repair for panel iteration and Python shutdown.

The #274 bundle preserves all 274 IDs from the #273 bundle. Its independent
clone passed strict fsck across 275 recovered commits. Revision #274 uses the
surviving text-panel and const handler APIs and releases the Python handles
before finalization in the private Linux build copy.

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
Revisions #180–#182 now pass pinned native builds and game startup. The original
build failures are recorded in
`recovery/diagnostics/native-180-182-original-build-defects-2026-11-17.json`.
The private build copy supplies forwarding headers for #180–#181 and the three
jsoncpp companions restored at #183. The reconstructed qmake projects list the
relocated compilation units. The #181 map reconstruction folds in the preceding
Coords and PlayerAnimation bodies, and the #180–#181 building reconstruction
uses the coordinate and enabled-state JSON object from the #182 reconstruction.
That change fixes the reproduced shutdown assertion. #183 passed separately
with its committed layouts and restored companions.
The same continuation then accepted #186-#193 through the developer's serialization
refactor (#186: name-keyed `loadFromJson`, static factories, no saving), property
system (#187: per-kind configs merged into `config/object.json`, TMX properties applied
through `QObject::setProperty`) and `QT_NO_KEYWORDS` switch (#190). Inferred members are
named in each reconstruction's provenance (for example `Creature::getCreature`,
`MapObject::getMapObject`, `MapObject::loadFromProps`, `Map::getObjectByName`,
`Map::removeTile`).
It also accepted #205-#223 (scripted caves and teleporters, QString factories, the
inventory API of #215 and the move of scripts/configs to disk at #219). Revision #204 uses a pinned build-copy repair that dispatches console input
through Qt’s event loop instead of the blocking global-pool task. Native startup
and clean shutdown passed with both EOF and an open idle stdin pipe. A separate
probe confirmed command execution. The original entrypoint remains in the tree.
The reconstructed `main.cpp` from #205 to #246 omits the console reader, which
is absent again from the next surviving `main.cpp` at #247.
Revisions #224 and #225 now pass with a pinned Linux build-copy repair.
The #224 scene and tile call sites use the active scene instance, and #225
borrows the no-op RoadTile definition from #226. The surviving project headers
and adjacent implementations inform the missing map, view, and binding sources.
Both real game views are embedded in the main window. Synchronous map
initialization took approximately nine minutes in the pinned runs.
Carry-forward now seeds a missing file from the nearest earlier version even when that
version is a surviving original, and inferred projects leave out Qt resource manifests
whose listed files are absent.
The verifier now treats a cached success whose artifacts moved as a cache miss, and
the startup observer gained three narrowly scoped behaviours, re-checked against
accepted #193, #223, #258 and #340: it reads the player from the scene instance when the
scene declares a non-static `getPlayer()` and the map has none (#226+); it does not
force a still-hidden game view visible while background tasks run (a view hidden after
5 s with an idle pool is shown as before); and it reports success only once the global
thread pool is idle, so it never exits underneath genuine background loading. The
workbench startup watchdog is configurable with `HISTORY_VERIFY_TIMEOUT` (default 60 s),
and inferred projects list Qt Designer forms in `FORMS`.
#226-#236 are accepted with a documented long startup window. From #226 the surviving
`LoadGameTask` fills every map cell through the genuine `CoordsHasher`, which always
returns 0 (unchanged up to #366), so loading the restored 200x200 map is quadratic; it was
confirmed to finish (about 279 s for the loading task in the verifier environment) and
these trees verify with `HISTORY_VERIFY_TIMEOUT=1200` (recorded smoke durations of about
700 s). The observer applies its loading deadline as soon as background work is seen,
even while the game keeps its view hidden. Reconstructions follow the developer's switch
to Python 2.7 (#229, `Py_InitModule`) and Boost.Python (#231: the ScriptEngine calls
`init_Game`, so a `_Game` module exposing `Building`, the class the same-commit
`Objects.py` imports, is reconstructed), the `ListItem`-into-`MapObject` merge (#231)
and the per-map `LootProvider` (#233). Inferred projects switch borrowed Python 3
libraries to 2.7 for the Python 2 module API and link Boost.Python when a tree includes
it. See `recovery/diagnostics/native-226-background-loading-2026-11-18.json`.
#237-#246 follow the developer's move of interactions into Python: actions leave the C++
table as the same-commit `interaction.h` stops declaring them and run from the map's
ScriptEngine; `_Game` (renamed `_game` at #241) also exposes `Damage`, `Interaction` and
`Coords` because the same-commit scripts import them and, from #239, the ScriptEngine's
`PY_UNSAFE` makes import failures fatal; `MapObject` expands the #241 `PROPERTY_ACCESSOR`
macro; at #245 interactions become Python classes (`performAction`/`configureEffect`),
the factory attaches the map before loading (as the genuine `Player(Map*, name)` does),
and the surviving `LoadGameTask` stops filling the whole map, so startups are fast again.
#246 adds the main window; after the developer's case-only `Game.pro` -> `game.pro`
rename the active `game.pro` carries `GAME_RECOVERY_APPLICATION = true`. Saving the
stale uppercase `Game.pro` reconstruction (active only for #241-#245) changed the inputs
of #256-#259, which were re-verified under the current inputs.

At #247 the surviving reflection table registers the renamed classes, and the
scripts import `CBuilding` from the native module. The reconstructed game panel
uses the layouts of the earlier character and fight views. Refreshing their lists
when shown is inferred. The active lowercase qmake project builds the new panel.
The verification record includes the loaded map and player, rendered frame and
clean exit.

Revisions #248–#253 build and start with reconstructed sources following the class
and panel renames, the genuine property generator where present, and the joined
player views and item hierarchy. At #254–#255 the surviving Qt JSON callers still
request flat configuration paths. The verifier merges the ten restored object tables,
copies the existing tiles table, and supplies 15 empty timing arrays so the original
animation provider selects its 250 ms default. These files are generated in the
isolated runtime copy. At #255 the reconstructed map dispatches Python building
classes through the map's script engine and weapon types through the item factory.
That dispatch is inferred. The retained startup log shows Cave and Teleporter loaded.

Revision #176 now builds after the documented trivial conflict resolution and one
build-copy addition. Its project lists `pathfinder/pathfindercache.cpp`, introduced as
the sole change in its immediate child #177. The verifier pins the donor, the project
and header inputs, exports the exact donor source with the evidence, and leaves the
restored #176 tree intact. #177 also passed a separate control build and startup.

Revisions #269–#272 now pass with reconstructed Python 3.3 bindings. The
verifier builds the declared Python dependency and uses the authored resource
directory for each layout. A pinned build-copy repair releases the owned
Boost.Python handles before interpreter finalization.

Revision #352 uses a reconstructed qmake project with the Python 3.4 link ABI.
Returning the class from the trigger decorator lets the existing map factory
resolve the named constructor. Revision #366 preserves the authored map source
and disambiguates the graphics position call in the private build copy. Its
GameScene reconstruction is scoped to that commit.

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
both games subsequently passed the native startup verifier as recorded in the ledger.

Where surviving `preprocessor.py` generates property headers, verification runs
that exact generator under pinned Python 2.7.18 in the private build-source copy.
Inputs, outputs and hashes are recorded separately from the restored snapshot.
The accepted startups at #250 and #257 also carry the generator evidence.

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

The acceptance totals above come from the local pinned toolchain. GitHub workflow
results are tracked separately on the continuation pull request.

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
python3 scripts/history_workbench.py auto 295 330 --verify  # next long gap; stops at first failure
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

Revisions #275–#281 passed the pinned build and startup verifier. The
reconstructions cover sparse map and saved creature state, the map-script
namespace, panel refresh, the effect base class, and movement callbacks. The
sparse map input does not establish the original placement of the named
`event1` trigger. The replay through #281 and #367 contains 282 commits and
preserves all 280 IDs in the replay through #279.

Revision #282 passed the pinned Qt build and startup verifier. The rebuilt
image manifest uses the surviving arrow PNGs and omits the missing loading
image. The original image inventory remains uncertain. The verifier builds
the two static libraries with the matching GCC archive plugin and starts the
game from the authored resources directory. The new replay through #282 and
#367 contains 283 commits and preserves every ID from the #281 bundle.

Revision #283 passed the same pinned verifier and a second isolated run with
no loose script files. The reconstructed `_core.ScriptLoader` resolved the
authored Python package from Qt resources and delegated standard-library imports
to the registered Python finders. Its original implementation remains unknown.
The replay through #283 and #367 contains 284 commits and preserves all IDs
from the #282 bundle.

Revisions #284–#287 passed the pinned Python 3.4 build and startup verifier.
The #284 startup script produced all 1,000 requested random draws within its
authored bounds. The panel, player view, and resource-backed script loader
reconstructions follow their surviving interfaces through the #285 resource
merge and the #286 root-project move. The original random engine and precise
removed implementation changes remain unknown. The replay through #287 and
#367 contains 288 commits and preserves all IDs from the #283 bundle.

Revisions #288 and #289 passed the pinned build and startup verifier. The
reconstructions load the map directory and its companion script, use the
per-map Python event dictionary, and adapt panel refresh and native effect
callbacks to the surviving declarations. Startup verifies map and player
readiness and equipment loading. Event placement and effect behavior during
combat remain unverified. The replay through #289 and #367 contains 290
commits and preserves every ID from the #287 bundle.

Revisions #290–#292 passed the pinned build and startup verifier with the
authored Python effect subclasses. The reconstruction exposes the effect
callback, uses the surviving object and map accessors, and implements the
stat bonus methods called by the authored code. Effect behavior during combat
remains unverified. The replay through #292 and #367 contains 293 commits
and preserves the previous replay IDs.

Revisions #293 and #294 passed the pinned build and startup verifier. #293
loads the authored event classes into the namespace used by the surviving
class-switching code. #294 exposes the native resource loader through the
Python 3.4 import protocol. Startup verifies game readiness, while in-play
event activation remains unverified. The replay through #294 and #367
contains 295 commits and preserves all IDs from the #292 bundle.

## Remaining work

- #295 is the first gap in the replay ancestry. Its project manifests reference loader sources and map files absent from the surviving tree. #295–#330 await native acceptance.
- #353–#359 still need native validation. At #353, moving imports below the
  decorators exposed the next failure, a missing ChaosSword definition.
- The ledger lists 43 catalog commits awaiting native acceptance. Track GitHub
  build, suite, and coverage on the continuation PR.
