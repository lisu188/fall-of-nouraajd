# Navigation profiling

This opt-in driver links an already built Windows MSVC Release engine. It does not rebuild the engine or create a GUI.
Use the same Release configuration, headers, object files and dependencies on both sides of a comparison. Do not link
old objects against new headers after a class layout changes. Timings use two warmups and seven samples; their medians
are diagnostic data, never millisecond CI gates.

## Fixed native workloads

The executable runs three callback-API graphs (open 96-by-96, weighted 128-by-128 and unreachable 96-by-96) and 20,000
overlay queries on a retained 4,096-step player route. Each query must preserve reachability, and every overlay coordinate
must match. Graph output includes callback and expansion counts as well as timings. The final baseline revision is
`762157313795cbdc5a1ec3d63848e03565c5d57c`, using Windows x64 MSVC Release and Python 3.12. Its complete output is in
[baseline-results.txt](baseline-results.txt).

Configure from the repository root, substituting the local vcpkg and Python paths:

```powershell
cmake -S scripts/navigation_profile -B cmake-build-release/navigation-profile-after `
  -G "Visual Studio 17 2022" -A x64 `
  -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake `
  -DVCPKG_MANIFEST_INSTALL=OFF `
  -DVCPKG_INSTALLED_DIR=C:/Users/andrz/git/fall-of-nouraajd/vcpkg_installed `
  -DPython3_EXECUTABLE=C:/Users/andrz/git/fall-of-nouraajd/vcpkg_installed/x64-windows/tools/python3/python.exe `
  -DGAME_SOURCE_DIR="$pwd" -DGAME_BUILD_DIR="$pwd/cmake-build-release"
cmake --build cmake-build-release/navigation-profile-after --config Release --target navigation_profile --parallel 2
$env:PYTHONHOME='C:/Users/andrz/git/fall-of-nouraajd/vcpkg_installed/x64-windows/tools/python3'
$env:PATH='C:/Users/andrz/git/fall-of-nouraajd/vcpkg_installed/x64-windows/bin;'+$env:PATH
cmake-build-release/navigation-profile-after/Release/navigation_profile.exe `
  "$pwd/res" "$pwd/cmake-build-release/navigation-profile-after/data"
```

Add `-DNAVIGATION_PROFILE_CURRENT_ONLY=ON` to the after configuration to include two extra map-service workloads.
They have no old-service equivalent and must not be included in a before/after speedup ratio:

- A seed-241 dungeon uses the existing `rdg::create_dungeon` implementation, the game's 555-by-555 dimensions and bent
  corridors. Native tiles reproduce the generated passability. A separate breadth-first traversal chooses a reachable
  farthest goal and verifies every measured route's exact cost. Generation and tile setup are outside the timed region.
- A service-level pursuit workload advances 128 start positions through 16 turns while their target alternates between
  adjacent cells. Each of its 2,048 requests must return a legal complete step or explicitly defer work. It reports
  expansions, fields, repairs, cache hits, deferred requests and peak budget usage. This isolates shared routing and does
  not instantiate game creatures or time their AI, combat or `CMap::move`. Each sample includes fresh map, target and
  service setup; its turn values are routing-work identifiers, not committed world turns.

The recorded baseline used the same commands with directory `navigation-profile-baseline`, plus
`-DGAME_HEADER_DIR=<repo>/cmake-build-release/navigation-profile-baseline/headers/src` and
`-DCMAKE_SUPPRESS_REGENERATION=ON`. Those headers were archived from the baseline commit before any engine source edit,
and the harness linked its untouched matching object files. On this host MSBuild required a child environment with
case-normalized keys (`{key.upper(): value for key, value in os.environ.items()}`) to avoid duplicate `PATH`/`Path` keys.

| Workload | Baseline median | Expanded | Passability calls | Edge-cost calls | Heuristic calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| Open 96-by-96 | 4.859900 ms | 9,215 | 9,598 | 36,478 | 9,216 |
| Weighted 128-by-128 | 2.404300 ms | 4,656 | 5,169 | 18,332 | 4,877 |
| Unreachable 96-by-96 | 2.082000 ms | 4,608 | 4,897 | 18,144 | 4,608 |
| Player overlay, 20,000 queries | 141.393700 ms | — | — | — | — |

The 2026-10-01 after run used the same configuration command with
`-DNAVIGATION_PROFILE_CURRENT_ONLY=ON`. Its complete output is in [after-results.txt](after-results.txt), with compiled
source hashes in [after-source-sha256.txt](after-source-sha256.txt). All fixed reachability and overlay assertions passed.
The median comparisons below are supplemental Windows Release measurements, not test thresholds:

| Paired workload | Before | After | After / before | After expansions |
| --- | ---: | ---: | ---: | ---: |
| Open 96-by-96 | 4.859900 ms | 3.864500 ms | 0.7952 | 9,026 |
| Weighted 128-by-128 | 2.404300 ms | 1.843500 ms | 0.7668 | 4,492 |
| Unreachable 96-by-96 | 2.082000 ms | 1.854100 ms | 0.8905 | 4,608 |
| Player overlay, 20,000 queries | 141.393700 ms | 8.910600 ms | 0.0630 | — |

The current-only seeded dungeon's route cost and length were 2,306, exactly matching the independent BFS. Its median
was 47.636200 ms, with 83,082 expansions per search and a 20,907,472-byte peak navigation budget. The current-only moving
target service sample returned 2,040 moving steps and eight deferred requests across 2,048 calls. Its median was
2,363.516900 ms including fresh setup; counters were 386,132 expansions, one field, 15 repairs, 2,047 hits and a
1,891,952-byte peak budget. No before-service speedup is claimed for either workload.

The retained source hashes and results are from the final rebuilt objects, including the direct-NPC-controller
compatibility fix and snapshot chunk-lock ordering fix. The harness was relinked and every after workload rerun after
those fixes; earlier development measurements were replaced, not relabelled as final-binary results.

An initial harness used `CGameLoader::loadGame` inside the native embed and exited with `0xC0000409` before its overlay
case. The retained final harness instead constructs an explicit native map/player fixture; all four recorded baseline
workloads completed with exit 0. The failing preliminary run is not counted as validation.

## Real authored-map workloads

`authored.py` imports the current build, loads real authored resources and plans routes without moving the player. It
asserts unchanged position, turn, HP, mana and inventory size. It requires the ordinary `_game` build but creates no GUI.
The default cases are `short` and `center`; repeatable `--case` options select specific workloads. `far` is explicitly
opt-in because it can explore a large part of an authored map. Run an external process timeout for that diagnostic.

```powershell
$env:GAME_BUILD_DIR='cmake-build-release'
$env:GAME_BUILD_CONFIG='Release'
& "$env:PYTHONHOME/python.exe" scripts/navigation_profile/authored.py `
  --map nouraajd --case short --case center --case far
& "$env:PYTHONHOME/python.exe" scripts/navigation_profile/authored.py `
  --map ninemarches --case short --case center
```

The original baseline invocation had all three cases enabled for Nouraajd, Nine Marches and Castle Homecoming. Five
cases completed and are preserved in [baseline-authored-partial.jsonl](baseline-authored-partial.jsonl). Nouraajd's
200-by-121 floor returned medians 0.0320, 2.5762 and 51.8504 ms. Nine Marches' 1,000-by-1,000 floor returned 0.0168 and
1.2028 ms for the first two cases. Its far-corner query did not finish before the profiling process was explicitly
stopped to release the DLL for the next build. It has no completed timing or correctness result, and Castle Homecoming
was never reached in that run. Compare only the five completed identical cases; do not interpret this partial file as
a completed full-map benchmark.

The two exact commands above completed against the current Release DLL, producing
[after-authored.jsonl](after-authored.jsonl). All five comparisons programmatically matched `map`, `dimensions`,
`origin`, `goal` and `route_pending` exactly, and every planning call preserved the player's position, turn, HP, mana and
inventory size. These final samples use the same rebuilt source as the native after profile.

| Authored workload | Before median | After median |
| --- | ---: | ---: |
| Nouraajd short, `(110,111)` → `(110,99)` | 0.0320 ms | 0.0148 ms |
| Nouraajd center, `(110,111)` → `(100,60)` | 2.5762 ms | 0.4219 ms |
| Nouraajd far, `(110,111)` → `(12,12)` | 51.8504 ms | 8.7550 ms |
| Nine Marches short, `(500,662)` → `(500,650)` | 0.0168 ms | 0.0176 ms |
| Nine Marches center, `(500,662)` → `(500,500)` | 1.2028 ms | 0.2199 ms |

The Nine Marches short case was slightly slower. The shortest cases are close to timer and call overhead; interpret their
small absolute differences cautiously. These
figures measure route planning on fixed destinations, not total frame time or full-game responsiveness.

## Live routing checks

The Windows Release `_game` checks use `GAME_BUILD_DIR=cmake-build-release`, `GAME_BUILD_CONFIG=Release` and the existing
stdio MCP subprocess harness. Neither the routes nor the callback child creates a GUI. Exact executed commands were:

```powershell
python -m unittest -v tests.test_navigation_mcp
python -m unittest -v tests.test_navigation_mcp.NavigationCallbackTest
```

After the final NPC and chunk-lock fixes and rebuild, the complete first command passed all three tests in 1.663 seconds
(`cmake-build-release/navigation-delivery-python.log`). Both MCP walkthroughs move the real player through the authored
stairs and goal triggers, and verify blocked-route abandonment and explicit retargeting. The callback guard verifies
worker and owner-thread Python factory callbacks, one committed map turn and legal actor movement with the player
stationary. Its separate focused invocation also passed in 0.183 seconds before the unrelated NPC fix.

The final native performance selection passed five of five tests in 4.68 seconds, and the legacy controller suite passed
one of one in 0.08 seconds. Their logs are `cmake-build-release/navigation-delivery-performance.log` and
`cmake-build-release/navigation-delivery-controller.log`. These are final-source correctness and deterministic-budget
results, separate from the repeated timing measurements above.

The deterministic chunk-lock regression failed two assertions against the old method (CTest exit 8; test duration
2.67 seconds, `cmake-build-release/navigation-chunk-before-test.log`) and passed after rebuilding the fixed method.
An intervening build retained the restored source file's old timestamp and therefore reused the old object; its failure
is preserved in `cmake-build-release/navigation-chunk-stale-build-test.log`, not counted as a passing fixed build.

## Deterministic validation and Linux profiling

Use the repository's `performance_guard_tests` target and CTest `performance` label for regression gates. The new
navigation tests also expose searches, expansions, flow reuse, budget peaks and indexed overlay probe counts. The
profiling driver itself is intentionally outside those gates.

The supplemental Linux driver builds only the real callback search translation units with existing GCC, Python,
pybind11, SDL and Valgrind tools. It stages matching baseline/current sources on the Linux filesystem, records source
hashes, and retains the workspace and reports. It creates no game or window and installs no dependencies:

```sh
bash scripts/navigation_profile/run-callgrind.sh 762157313795cbdc5a1ec3d63848e03565c5d57c
```

The [captured Callgrind and Memcheck results](callgrind-results.txt) used GCC 13.3, `-O2 -g` and Valgrind 3.22 in WSL.
The fixed open-128, weighted-128 and sealed-64 callback workloads all preserved reachability. Instruction references fell
from 79,755,620 to 73,197,340 (8.22%); allocator self-instruction counts fell from 9,682,525 to 3,260,684 for `_int_malloc`
and from 6,571,644 to 3,021,124 for `_int_free`. Afterward, the largest individual source attribution was the indexed
heap's sink operation. Memcheck reported zero errors, zero bytes retained at exit, and 46,686 allocations matched by
46,686 frees. The exact executed commands and source hashes are retained in the result file. The packaged wrapper also
completed end to end with exit 0 on the final hop-count and cancellation source snapshot.

This evidence supports reduced allocator overhead in the generic callback solver. It does not measure the map-aware
snapshot heuristic, shared pursuit, preview, overlay or whole game, and supplies no elapsed-time speedup claim. The
normal Windows engine build cannot run under Valgrind; the isolated GCC executable is a separate explicitly identified
measurement. Do not install dependencies or silently substitute a different revision.

## Current-only live engine profile

[`live.py`](live.py) drives the real Warrior through the authored `multilevel` stairs and both goals without creating a
GUI. On the final Linux source, all 36 planning calls preserved position, turn and resources; 19 actual turns reached
the four authored destinations and set their existing progress flags. The normal and Callgrind runs exited successfully.
The instrumented planning, movement, event-loop and assertion interval recorded 32,590,849 instruction references;
startup and shutdown were excluded. This has no historical live-engine baseline and supplies no speedup ratio.

Full-process Memcheck **failed with exit 97**: 377,240 definitely lost bytes and 1,428 error contexts. The same script's
`--import-only` control also failed with exit 97 before constructing a game: 364,950 definitely lost bytes and 1,463
contexts. Both reports had zero suppressions and no invalid-access/uninitialized-value diagnostic or stack frame named
`CNavigation` or `CPathFinder`. Their leak stacks include Python imports and pybind registration. This control shows
leakage before gameplay, but does not establish its historical origin or explain every live/control difference; the live
process must not be described as memory-clean.

[`live-results.txt`](live-results.txt) retains the exact build/runtime commands, selected source hashes, observed route,
raw-report locations and limitations. [`live-client.cpp`](live-client.cpp) supplies the optional Callgrind start/stop
markers. These diagnostics use existing Linux tools, add no production dependency, and remain separate from the clean
callback-only Memcheck result above.
