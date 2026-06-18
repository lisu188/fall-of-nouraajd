# TODO Worklog

## Batch 1
- Location: `res/maps/nouraajd/script.py`, `res/maps/nouraajd/config.json`, `res/config/potions.json`, `test.py`
- Original TODO or summary: `TavernDialog1.sell_beer()` was a player-visible stub that only printed `sell_beer` even though the tavern dialog exposed a beer-purchase option.
- Status: fixed
- What was changed: Added a dedicated `tavernBeerMarket` in Nouraajd, introduced two beer consumables for that market, replaced the tavern stub with `showTrade(game.createObject("tavernBeerMarket"))`, and added a focused regression test that captures the opened market and verifies the stocked beer labels.
- Why the change is correct: The same map already uses the `createObject("<marketId>")` plus `showTrade(...)` pattern for `victorMarket`, and the dialog action was already wired in `dialog.json`. This completes the missing behavior without changing unrelated quest or map logic.
- Validation performed:
  - `cmake -S . -B cmake-build-release`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests`
  - `python3 test.py` -> `Ran 41 tests in 104.492s`, `OK`
  - `./scripts/run_coverage.sh` -> `Ran 41 tests in 321.592s`, `OK`, but repo-wide line coverage stayed at `75.07%`, below the required `80%`
- Blockers if unresolved: Coverage threshold is currently a repo-wide validation blocker for any batch that changes `test.py` or `src/core|src/handler|src/object`; the functional tavern fix itself passed build, unit, and Python test validation.

## Batch 2
- Location: `res/maps/nouraajd/dialog3.json`
- Original TODO or summary: Victor's reward dialog promised that his potions were available “whenever you ask,” but the implementation only opens a one-time trade screen right after the rescue.
- Status: fixed
- What was changed: Reworded the reward dialog to describe Victor offering the potions he has left immediately, matching the actual one-time `victorMarket` trade flow.
- Why the change is correct: The only verified market access in script is the single `showTrade(game.createObject("victorMarket"))` call during the reward trigger; there is no later Victor vendor hook.
- Validation performed:
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests`
  - `python3 test.py` -> `Ran 41 tests in 102.260s`, `OK`
- Blockers if unresolved: None so far.

## Batch 3
- Location: `CMakeLists.txt`
- Original TODO or summary: Packaging/install rules duplicated script entries, including installing `test.py` twice and repeating the same source file twice on the `play.py` and `mcp.py` lines.
- Status: fixed
- What was changed: Collapsed the script install rules into one single `install(FILES ...)` entry covering `res/game.py`, `play.py`, `mcp.py`, and `test.py`.
- Why the change is correct: The old rules were redundant and inconsistent; the new rule installs the same intended files exactly once without changing destinations.
- Validation performed:
  - `cmake -S . -B cmake-build-release`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests`
  - `python3 test.py` -> `Ran 41 tests in 97.681s`, `OK`
- Blockers if unresolved: None so far.

## Batch 4
- Location: `src/gui/object/CProxyTargetGraphicsObject.cpp`
- Original TODO or summary: `refreshObject()` silently ignored out-of-bounds coordinates even though the source already marked that path with `// TODO: log warning`.
- Status: fixed
- What was changed: Added a warning that logs the rejected proxy coordinates together with the current target size before returning.
- Why the change is correct: This preserves the existing behavior for invalid refreshes while making bad caller coordinates diagnosable at runtime.
- Validation performed:
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests`
  - `python3 test.py` -> `Ran 41 tests in 98.299s`, `OK`
- Blockers if unresolved: `clang-format -i src/gui/object/CProxyTargetGraphicsObject.cpp` could not be run because `clang-format` is not installed in this environment.

## Batch 5
- Location: `CMakeLists.txt`
- Original TODO or summary: The Windows packaging section still installed `play.bat` with the same source path repeated twice on one line.
- Status: fixed
- What was changed: Reduced the Windows `install(FILES ...)` rule to a single `play.bat` entry.
- Why the change is correct: It preserves the same destination artifact while removing the redundant duplicate source path.
- Validation performed:
  - `cmake -S . -B cmake-build-release`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests`
  - `python3 test.py` -> `Ran 41 tests in 101.447s`, `OK`
- Blockers if unresolved: None so far.

## Batch 6
- Location: `src/core/CJsonUtil.h`, `src/handler/CObjectHandler.cpp`, `test.py`
- Original TODO or summary: Remaining safe diagnostic and integrity fixes exist in the JSON parser, missing-config fallback, and dialog/trigger test coverage.
- Status: blocked
- What was changed: No source edits.
- Why the change is correct: These are still valid next candidates, but any change in `test.py`, `src/core`, or `src/handler` triggers the repository coverage gate.
- Validation performed:
  - reviewed `AGENTS.md`
  - ran `./scripts/run_coverage.sh` on the earlier tavern/test batch
  - confirmed current scoped coverage is `75.07%`, below the required `80%`
- Blockers if unresolved: Repo-wide coverage threshold blocks safe follow-up work in `test.py`, `src/core`, and `src/handler` until coverage is raised.

## Batch 7
- Location: `res/maps/nouraajd/script.py`, `res/maps/ritual/script.py`, `res/maps/siege/script.py`
- Original TODO or summary: Placeholder quest completion hooks and the siege property-export note remain in map scripts.
- Status: deferred
- What was changed: No source edits.
- Why the change is correct: The remaining quest `onComplete()` stubs would mostly duplicate existing trigger/dialog feedback, and the siege TODO points at engine/property export work rather than a bounded map-script fix.
- Validation performed:
  - inspected the Nouraajd and Ritual quest flows against their dialogs, triggers, and reward paths
  - verified the siege TODO is tied to property export behavior rather than a localized content defect
- Blockers if unresolved: Insufficient source evidence for a safe non-duplicative content change; siege item depends on broader engine behavior.

## Batch 8
- Location: `res/plugins/object.py`, `res/maps/nouraajd/script.py`
- Original TODO or summary: The generic `Market` building still had an empty `onEnter()` stub, while Nouraajd used a map-specific trigger to open the trade panel as a workaround.
- Status: fixed
- What was changed: Implemented generic market interaction in `Market.onEnter()` and removed the now-redundant Nouraajd-only `MarketTrigger`.
- Why the change is correct: The repo already stores the target market object on the building via the `market` property, and Nouraajd was already using that exact data to open trade. Moving the behavior into the generic building preserves existing gameplay while completing the placeholder.
- Validation performed:
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests`
  - static verification that `Market.onEnter()` now opens the configured market and that `MarketTrigger` is gone from Nouraajd
  - `python3 test.py` -> `Ran 41 tests in 106.832s`, `OK`
- Blockers if unresolved: None so far.

## Batch 9
- Location: `res/maps/siege/script.py`
- Original TODO or summary: Siege spawn points still prompted the player to seal the gate, or warned about needing a wand, even when the gate had never opened or had already been sealed.
- Status: fixed
- What was changed: Guarded `SpawnPoint.onEnter()` so it only prompts or warns when the gate is currently `enabled` and not `destroyed`, leaving dormant and already-sealed spawn points silent.
- Why the change is correct: `onCreate()` initializes every spawn point as `enabled = False` and `destroyed = False`, and the turn trigger is the only place that flips a gate open by setting `enabled = True` and swapping to the open-door animation. The old `onEnter()` path ignored both flags, so it advertised sealing on the wrong states. The new guard matches the actual open-gate lifecycle without changing spawn timing or seal behavior.
- Validation performed:
  - focused scripted repro before the fix: monkeypatched `CGuiHandler.showQuestion`, loaded `siege`, set `spawnPoint1` to `enabled = True` and `destroyed = True`, invoked `spawn.onEnter(...)`, and still captured `Do You want to seal the gate?`
  - focused scripted repro after the fix: unopened and destroyed spawn points stayed silent, while an opened gate still emitted the seal prompt and the missing-wand info path still emitted its warning
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `[100%] Built target _game`, `[100%] Built target for_unit_tests`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> emitted progress dots and wrote updated `test/*.json` artifacts through the map walkthrough tests, but never reached a final unittest summary; after remaining CPU-bound for several more minutes it was terminated manually, and the shell reported exit code `137`
  - static source verification of `res/maps/siege/config.json` and `res/maps/siege/map.json` to confirm `SpawnPoint` has no extra config gating and is wired directly from the siege map object layer
- Blockers if unresolved: Full Python-suite validation is currently blocked in this environment because `python3 test.py` did not finish on this run.

## Batch 10
- Location: `src/gui/panel/CListView.cpp`, `src/gui/panel/CGameInventoryPanel.cpp`, `src/gui/panel/CGameInventoryPanel.h`, `src/gui/panel/CGameFightPanel.cpp`, `src/gui/panel/CGameFightPanel.h`, `src/gui/panel/CGameTradePanel.cpp`, `src/gui/panel/CGameTradePanel.h`, `todo.txt`
- Original TODO or summary: `todo.txt` tracked combined right-click item-use and selection-reset work, but the current GUI only handled left-click in `CListView`, so right-clicks could not clear stale selections in the inventory, fight, or trade panels.
- Status: partially fixed
- What was changed: Let right-click `SDL_MOUSEBUTTONDOWN` events bubble past `CListView`, added panel-level right-click handlers that clear the relevant selection state in inventory, fight, and trade panels, and rewrote the `todo.txt` entry to leave only the still-unimplemented direct item-use-on-right-click behavior.
- Why the change is correct: The selected state in all three panels lives on the parent panel objects, not inside `CListView`. Returning `false` for right-clicks in `CListView` lets the parent panel receive the event, and each panel now clears exactly the selection state it owns before refreshing the views. This matches the verified missing behavior without changing left-click semantics or trade actions.
- Validation performed:
  - source verification of `todo.txt`, `TODO_WORKLOG.md`, `src/gui/panel/CListView.cpp`, `src/gui/panel/CGameInventoryPanel.cpp`, `src/gui/panel/CGameFightPanel.cpp`, and `src/gui/panel/CGameTradePanel.cpp`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `[100%] Built target _game`, `[100%] Built target for_unit_tests`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> emitted progress dots (`.....`, then later `.............`/`..............`) but did not reach a final unittest summary before multiple runs remained CPU-bound in this environment
- Blockers if unresolved: Direct right-click item use is still outstanding and remains in `todo.txt`; full Python-suite completion is still not reproducible in this environment because `python3 test.py` did not finish cleanly during this batch.

## Batch 11
- Location: `src/gui/CAnimation.h`, `src/gui/CAnimation.cpp`, `src/gui/object/CWidget.cpp`, `src/gui/panel/CListView.h`, `src/gui/panel/CListView.cpp`, `src/gui/panel/CGameInventoryPanel.h`, `src/gui/panel/CGameInventoryPanel.cpp`, `src/gui/panel/CGameFightPanel.h`, `src/gui/panel/CGameFightPanel.cpp`, `res/config/panels.json`, `todo.txt`
- Original TODO or summary: `todo.txt` still tracked `use items on right click`, but item use only happened on second left-click in the inventory and fight panels and the right-click path stopped at tooltip/list event handling instead of reaching `useItem(...)`.
- Status: fixed
- What was changed: Added an optional `rightClickCallback` property to `CListView`, wired dedicated right-click item handlers into the inventory and fight panel item lists through `res/config/panels.json`, let list item graphics reuse the list click path on both mouse buttons, kept empty-cell right-click bubbling for the existing selection-reset behavior, and made render-only `CWidget` overlays transparent to mouse events so grouped-item count labels no longer swallow clicks.
- Why the change is correct: The unresolved bug was not in `CCreature::useItem(...)`; it was in the GUI event chain. Right-clicks on list items never reached a panel method that could call `useItem(...)`, and item graphics/tooltips could consume the event before the parent list saw it. The new `rightClickCallback` path gives the two relevant panels an exact item-context handler, while the animation and widget changes keep tooltip behavior and grouped overlays from blocking the action.
- Validation performed:
  - source verification of `AGENTS.md`, `README.md`, `todo.txt`, `TODO_WORKLOG.md`, `test.py`, `res/game.py`, `CMakeLists.txt`, `scripts/run_coverage.sh`, `src/gui/CAnimation.h`, `src/gui/CAnimation.cpp`, `src/gui/object/CWidget.cpp`, `src/gui/panel/CListView.h`, `src/gui/panel/CListView.cpp`, `src/gui/panel/CGameInventoryPanel.h`, `src/gui/panel/CGameInventoryPanel.cpp`, `src/gui/panel/CGameFightPanel.h`, `src/gui/panel/CGameFightPanel.cpp`, and `res/config/panels.json`
  - GitHub `main` verification of the same backlog/baseline files plus the touched GUI files before editing
  - `git submodule update --init --recursive` -> restored missing `json`, `random-dungeon-generator`, and `vstd` submodules in the fresh worktree so validation could run
  - `clang-format -i src/gui/CAnimation.h src/gui/CAnimation.cpp src/gui/object/CWidget.cpp src/gui/panel/CListView.h src/gui/panel/CListView.cpp src/gui/panel/CGameInventoryPanel.h src/gui/panel/CGameInventoryPanel.cpp src/gui/panel/CGameFightPanel.h src/gui/panel/CGameFightPanel.cpp` -> failed with `/bin/bash: line 1: clang-format: command not found`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `[100%] Built target _game`, `[100%] Built target for_unit_tests`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> emitted progress output (`.....`, `....`, `.................`, `......`) and then remained CPU-bound without reaching a unittest summary; interrupted manually with `^C`
- Blockers if unresolved: Full `python3 test.py` completion is still not reproducible in this environment, so the item-use fix still needs manual in-game confirmation for the tooltip-plus-right-click interaction in inventory and fight panels.

## Batch 12
- Location: `src/gui/panel/CGameFightPanel.cpp`, `src/core/CController.cpp`, `src/handler/CFightHandler.cpp`, `todo.txt`
- Original TODO or summary: `todo.txt` tracked `cant quit game when in fight (hang in wait until)`, and the current fight UI blocked inside a nested event loop until the player selected an action.
- Status: fixed
- What was changed: Replaced the fight-panel interaction wait with a loop that exits when SDL posts `SDL_QUIT`, re-queued the quit event so the outer game loop still sees it, guarded `CPlayerFightController::control()` against null interaction selection, and made `CFightHandler::fight()` stop advancing turns once a quit event is pending. Removed the resolved `todo.txt` entry.
- Why the change is correct: The hang came from consuming `SDL_QUIT` inside the fight-panel selection wait and then continuing to wait for `finalSelected`. Returning early on quit prevents the infinite loop, reposting `SDL_QUIT` preserves the existing outer-loop shutdown path, and the controller/fight-handler guards prevent null action crashes or continued combat after the quit request.
- Validation performed:
  - source verification of `AGENTS.md`, `README.md`, `todo.txt`, `TODO_WORKLOG.md`, `test.py`, `res/game.py`, `CMakeLists.txt`, `scripts/run_coverage.sh`, `src/core/CFuture.cpp`, `src/core/CController.cpp`, `src/handler/CFightHandler.cpp`, `src/gui/panel/CGameFightPanel.cpp`, and `src/gui/panel/CGameFightPanel.h`
  - GitHub `main` verification of `todo.txt`, `TODO_WORKLOG.md`, `src/core/CFuture.cpp`, `src/core/CController.cpp`, `src/handler/CFightHandler.cpp`, and `src/gui/panel/CGameFightPanel.cpp` before editing
  - `clang-format -i src/gui/panel/CGameFightPanel.cpp src/core/CController.cpp src/handler/CFightHandler.cpp` -> failed with `/bin/bash: line 1: clang-format: command not found`
  - `cmake -G Ninja -B ./cmake-build-release -S . -DCMAKE_BUILD_TYPE=Release` -> configured successfully with only existing SDL2 CMake dev warnings
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `[21/21] Linking CXX shared module _game.cpython-312-x86_64-linux-gnu.so`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> `Ran 61 tests in 171.540s`, `OK`
  - `./scripts/run_coverage.sh` -> configured and built `cmake-build-coverage`, `ctest` passed, then the embedded `python3 test.py` phase emitted progress dots (`.....`, `......................`, `.....`) and remained CPU-bound for over 20 minutes without reaching a unittest summary or writing coverage reports; the run was terminated manually
- Blockers if unresolved: The functional quit fix passed the mandatory build, unit-test, and Python-suite validation, but the required coverage script is still blocked by the repo's long-running `python3 test.py` behavior under coverage instrumentation, so no fresh scoped percentage was produced for this batch.

## Batch 13
- Location: `todo.txt`, `src/core/CMap.cpp`, `src/core/CController.cpp`, `src/core/CPathFinder.cpp`, `src/object/CCreature.cpp`, `test.py`
- Original TODO or summary: `todo.txt` still tracked `implement move cost`, `implement move points`, and `implement dijkstra`.
- Status: fixed
- What was changed: Removed the three stale movement/pathfinding TODO entries from `todo.txt` after verifying that the functionality is already present in engine code and covered by existing automated tests. No runtime source changes were needed.
- Why the change is correct: `CMap::getMovementCost(...)` and `CTile::movementCost` already drive per-tile costs, `CCreature` already exposes and enforces move points through `getMovePointsMax()`, `spendMovePoints()`, and reset logic, and `CPathFinder::fillValues()` already performs weighted shortest-path expansion with a priority queue while `CController` passes `getMovementCost(...)` as the step-cost function. `test.py` already verifies weighted pathing and move-point budgeting in `test_weighted_player_path_respects_move_budget`, `test_move_potion_restores_points_and_is_not_consumed_when_full`, and `test_move_points_reset_and_scale_with_level`.
- Validation performed:
  - source verification of `AGENTS.md`, `README.md`, `todo.txt`, `TODO_WORKLOG.md`, `test.py`, `scripts/run_coverage.sh`, `res/game.py`, and `CMakeLists.txt`
  - local source verification of `src/core/CMap.cpp`, `src/core/CController.cpp`, `src/core/CPathFinder.cpp`, `src/core/CPathFinder.h`, and `src/object/CCreature.cpp`
  - GitHub `main` verification of `todo.txt`, `src/core/CMap.cpp`, `src/core/CController.cpp`, `src/core/CPathFinder.cpp`, and `test.py` before editing
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests`
  - `python3 test.py`
- Blockers if unresolved: None. This batch only cleans up stale backlog items; the verified movement/pathfinding behavior is already live and tested.

## Batch 14
- Location: `src/core/CJsonUtil.h`, `src/core/CProvider.cpp`, `src/handler/CObjectHandler.cpp`, `test.py`
- Original TODO or summary: Inline TODOs still left JSON parse failures silent (`return nullptr; // TODO: handle`) and missing object-config fallback undiscoverable (`// TODO: vstd::logger::debug("No config found for:", type);`).
- Status: fixed
- What was changed: Added contextual JSON parse warnings with source path and payload preview in `CJsonUtil::from_string(...)`, threaded source paths through configuration/resource loading so malformed files report which resource failed, restored a debug log when `CObjectHandler::_createObject(...)` falls back from a missing config to class-name construction, and added focused regression tests that capture native file-sink logs for both the class-name fallback and a malformed saved-game load. While validating this batch, stabilized the pre-existing `test_player_recovery_from_map_objects_preserves_state` fixture so it no longer depends on unrelated map activity during the full suite.
- Why the change is correct: Before this batch, both failure modes reproduced as completely silent no-op paths: creating `CCreature` by class name emitted no diagnostic, and loading an invalid save returned an empty `CMap` without any parse error context. The new logging keeps the existing fallback behavior intact while making malformed resources and missing configs diagnosable. The new tests verify the exact no-crash paths by asserting on the native logger output rather than implementation details.
- Validation performed:
  - source verification of `AGENTS.md`, `README.md`, `todo.txt`, `TODO_WORKLOG.md`, `test.py`, `scripts/run_coverage.sh`, `res/game.py`, and `CMakeLists.txt`
  - local and GitHub `main` verification of `src/core/CJsonUtil.h`, `src/core/CProvider.cpp`, `src/handler/CObjectHandler.cpp`, and `test.py` before editing
  - `black -l 120 test.py`
  - `clang-format -i src/core/CJsonUtil.h src/core/CProvider.cpp src/handler/CObjectHandler.cpp`
  - `python3 -m unittest test.GameTest.test_create_object_without_config_logs_fallback` -> `Ran 1 test`, `OK`
  - `python3 -m unittest test.GameTest.test_invalid_saved_game_logs_parse_failure` -> `Ran 1 test`, `OK`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `[100%] Built target _game`, `[100%] Built target for_unit_tests`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> `Ran 73 tests in 378.683s`, `OK`
  - `./scripts/run_coverage.sh` -> configured and built `cmake-build-coverage`, `ctest` passed, then the embedded instrumented `python3 test.py` phase emitted progress dots (`...........`, then `.............................`) and remained CPU-bound for over 24 minutes without reaching a unittest summary or coverage report; the run was terminated manually with `kill 88422 89103`
- Blockers if unresolved: The functional batch is validated by the mandatory build, C++ unit target, and full Python suite, but the required coverage script is still blocked by the instrumented `python3 test.py` phase not completing in this environment, so no fresh scoped coverage percentage was produced.

## Batch 15
- Location: `todo.txt`, `src/core/CMap.cpp`, `src/core/CLoader.cpp`, `res/maps/test/map.json`, `test.py`
- Original TODO or summary: `todo.txt` still tracked `add new toroidal map`.
- Status: fixed
- What was changed: Removed the stale toroidal-map TODO from `todo.txt`. No runtime source changes were needed.
- Why the change is correct: Toroidal-map support is already implemented in engine and test assets. `apply_tile_layer_metadata(...)` in `src/core/CLoader.cpp` already reads per-layer `wrapX` and `wrapY`; `CMap::normalizeCoords(...)`, `getAdjacentCoords(...)`, and `getShortestDelta(...)` in `src/core/CMap.cpp` already use those wrap flags; `res/maps/test/map.json` already defines a wrap-enabled authored map; and `test_toroidal_map_wraps_and_survives_save_load` in `test.py` already verifies wrap behavior across movement and save/load. Local source matched GitHub `main` before editing, so the backlog item was stale rather than merely locally implemented.
- Validation performed:
  - source verification of `AGENTS.md`, `README.md`, `todo.txt`, `TODO_WORKLOG.md`, `test.py`, `scripts/run_coverage.sh`, `res/game.py`, and `CMakeLists.txt`
  - local source verification of `src/core/CMap.cpp`, `src/core/CLoader.cpp`, `res/maps/test/map.json`, and `res/maps/test/script.py`
  - GitHub `main` verification of `todo.txt`, `src/core/CMap.cpp`, `src/core/CLoader.cpp`, `res/maps/test/map.json`, and `test.py` before editing
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `Built target _game`, `Built target for_unit_tests`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> `Ran 77 tests in 323.349s`, `OK` (rerun after rebasing onto the latest `origin/main`)
- Blockers if unresolved: None.

## Batch 16
- Location: `src/core/CMap.h`, `src/core/CMap.cpp`, `src/core/CLoader.cpp`, `res/maps/ritual/map.json`, `test.py`, `todo.txt`
- Original TODO or summary: `todo.txt` still tracked `customize out of bound tiles`.
- Status: fixed
- What was changed: Added per-layer `outOfBounds` tile metadata to `CMap` and `CMapLoader`, wired the `ritual` map to use `WaterTile` outside its bounds, added loader-assumption validation plus a save/load regression test for the override, and removed the resolved TODO entry from `todo.txt`.
- Why the change is correct: The real gap was that bounded coordinates outside `xBound`/`yBound` always materialized `MountainTile`, even though map layers already carried other tile metadata. The loader now accepts an explicit `outOfBounds` tile id and reapplies it when loading saved maps, so the configured fallback survives both fresh loads and saved-game reloads.
- Validation performed:
  - source verification of `AGENTS.md`, `README.md`, `todo.txt`, `TODO_WORKLOG.md`, `test.py`, `scripts/run_coverage.sh`, `res/game.py`, `CMakeLists.txt`, `src/core/CMap.h`, `src/core/CMap.cpp`, `src/core/CLoader.cpp`, `res/maps/ritual/config.json`, `res/maps/ritual/script.py`, `res/maps/ritual/map.json`, `res/maps/test/script.py`, and `res/maps/test/map.json`
  - GitHub `main` verification of `todo.txt`, `src/core/CMap.h`, `src/core/CMap.cpp`, `src/core/CLoader.cpp`, `test.py`, `res/maps/ritual/map.json`, `res/maps/test/map.json`, and `res/maps/test/script.py` before editing
  - `python3 -c 'import json, builtins, game; ...'` -> confirmed `game.jsonify(...)` exposes materialized map tiles under `properties.tiles[*].properties.typeId`, which the new regression uses to assert the actual fallback tile id
  - `black -l 120 test.py` -> `1 file left unchanged`
  - `clang-format -i src/core/CMap.h src/core/CMap.cpp src/core/CLoader.cpp` -> succeeded, but I restored `src/core/CLoader.cpp` to `HEAD` and reapplied only the minimal loader changes because whole-file formatting caused broad whitespace churn
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `[100%] Built target _game`, `[100%] Built target for_unit_tests`
  - `python3 -m unittest test.GameTest.test_out_of_bounds_tile_override_survives_save_load test.GameTest.test_toroidal_map_wraps_and_survives_save_load test.GameTest.test_map_json_tiled_compatibility` -> `Ran 3 tests in 0.436s`, `OK`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> `Ran 78 tests in 272.585s`, `OK`
  - `./scripts/run_coverage.sh` -> configured and built `cmake-build-coverage`, `ctest` passed, then the embedded instrumented `python3 test.py` printed `.........................................` and stopped producing output or reports; after an additional 4 minutes with no progress, I confirmed two coverage-run `python3 test.py` processes stuck at ~99% CPU (`280306`, `280331`), terminated them with `kill -9 280306 280331`, and the script exited with `./scripts/run_coverage.sh: line 27: 280331 Killed                  GAME_BUILD_DIR="${BUILD_DIR}" python3 test.py`
- Blockers if unresolved: Functional validation passed, but the required coverage step is still blocked by the instrumented `python3 test.py` phase hanging without generating `coverage/coverage.txt` or `coverage/coverage.html`, so no fresh scoped line percentage was produced for this batch.

## Batch 17
- Location: `src/gui/panel/CListView.cpp`, `todo.txt`
- Original TODO or summary: `todo.txt` still tracked `add stacks of object (wand etc) same as grouping but in the left corner`, and grouped item stacks were still rendering their count badge in the lower-right corner.
- Status: fixed
- What was changed: Changed `CListView::addCountBox(...)` to anchor grouped count badges with `LEFT`/`UP` instead of `RIGHT`/`DOWN`, then removed the resolved backlog entry from `todo.txt`.
- Why the change is correct: Grouped lists in inventory, fight, loot, and trade panels already share the same `CListView` count-badge path through `res/config/panels.json`, and `CLayout::getRect(...)` interprets `LEFT`/`UP` as top-left anchoring. The broken behavior was only the badge layout direction, so no panel callback or grouping logic changes were needed.
- Validation performed:
  - source verification of `AGENTS.md`, `README.md`, `todo.txt`, `TODO_WORKLOG.md`, `test.py`, `scripts/run_coverage.sh`, `res/game.py`, and `CMakeLists.txt`
  - local and GitHub `main` verification of `todo.txt`, `src/gui/panel/CListView.cpp`, `src/gui/CLayout.cpp`, and `res/config/panels.json` before editing
  - `clang-format -i --lines=253:264 src/gui/panel/CListView.cpp`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `[100%] Built target _game`, `[100%] Built target for_unit_tests`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> `Ran 77 tests in 338.493s`, `OK`
- Blockers if unresolved: None. This batch touched only `src/gui` plus backlog bookkeeping, so `./scripts/run_coverage.sh` was not required by the repository rules.

## Batch 18
- Location: `src/gui/object/CWidget.h`, `src/gui/object/CWidget.cpp`
- Original TODO or summary: `CWidget::mouseEvent(...)` still carried `// TODO: maybe require both up and down`, and clickable widgets invoked their callback on any left-button release while also swallowing unrelated mouse events.
- Status: fixed
- What was changed: Added per-widget press tracking in `CWidget`, limited click handling to left-button press/release sequences, and required the release to land back inside the widget before invoking the configured callback. The widget now still consumes the matching release after a captured press, but lets unrelated mouse events bubble to parent handlers.
- Why the change is correct: Before the fix, `CWidget::mouseEvent(...)` only checked for `SDL_MOUSEBUTTONUP` plus a non-empty `click`, so a modal button could fire even after the pointer was dragged off the widget, and any clickable widget returned `true` for unrelated mouse events. The new guard keeps the intended click path for real left-clicks while preventing false activations and accidental event swallowing.
- Validation performed:
  - source verification of `AGENTS.md`, `README.md`, `docs/testing.md`, `todo.txt`, `TODO_WORKLOG.md`, `src/gui/object/CWidget.h`, and `src/gui/object/CWidget.cpp`
  - GitHub `main` verification of `src/gui/object/CWidget.h`, `src/gui/object/CWidget.cpp`, and `TODO_WORKLOG.md` before editing
  - `git submodule update --init --recursive`
  - `clang-format -i src/gui/object/CWidget.h src/gui/object/CWidget.cpp`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `[100%] Built target _game`, `[100%] Built target for_unit_tests`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> tool polling duplicated long-running sandboxes in this environment, so the suite was rerun once in a single background shell writing to `/tmp/game-python-test.log`; the final log ended with `Ran 78 tests in 283.191s` and `OK`
- Blockers if unresolved: No known functional blocker remains, but this environment's long-command polling can clone `python3 test.py` runs, so future full-suite checks should avoid session polling and capture the output from a single process.

## Batch 19
- Location: `mcp.py`, `src/handler/CGuiHandler.h`, `src/handler/CGuiHandler.cpp`, `src/core/CModule.cpp`, `README.md`, `test.py`
- Original TODO or summary: Codex could inspect GUI state directly from Python with `game.jsonify(g.getGui())`, but the documented repo-root MCP stdio flow did not expose the pybind loader methods needed to build that session and failed to load game assets from repo root because it never changed into the build directory.
- Status: fixed
- What was changed: Made `EngineMcpServer.import_modules()` switch into the configured build directory before importing `game`/`_game`, taught MCP export discovery to include pybind-backed class methods such as `CGameLoader.loadGame`, `CGameLoader.loadGui`, and `CGameLoader.startGameWithPlayer`, and added a read-only `CGuiHandler.openPanel(...)` binding that opens a configured panel without blocking on `awaitClosing()`. Documented the now-supported GUI inspection path in `README.md` and added two regression tests that prove the pybind exports are visible over MCP and that `python3 mcp.py --stdio --repo-root . --build-dir cmake-build-release` can open `inventoryPanel` headlessly and dump a live GUI tree containing the expected `CListView` wiring.
- Why the change is correct: The missing capability was not GUI serialization itself; it was the MCP access path. Existing generic MCP tools (`engine_list`, `engine_call`, `engine_handle_call`) were already enough once they could actually reach the loader methods and a non-blocking panel opener. `flipPanel(...)` was the wrong API to expose because it waits for manual closure, so `openPanel(...)` keeps the change bounded and read-only while making the existing `jsonify(...)` surface usable for debugging and automation.
- Validation performed:
  - source verification of `AGENTS.md`, `README.md`, `docs/testing.md`, `CMakeLists.txt`, `test.py`, `mcp.py`, `src/core/CWrapper.h`, `src/core/CModule.cpp`, `src/core/CTypes.cpp`, `src/gui/CGui.h`, `src/gui/CGui.cpp`, `src/gui/object/CGameGraphicsObject.h`, `src/gui/object/CGameGraphicsObject.cpp`, `src/gui/object/CWidget.h`, `src/gui/object/CWidget.cpp`, `src/gui/CLayout.h`, `src/gui/CLayout.cpp`, `src/gui/CTooltip.h`, `src/gui/CTooltip.cpp`, `src/gui/panel/CGamePanel.h`, `src/gui/panel/CGamePanel.cpp`, `src/gui/panel/CListView.h`, `src/gui/panel/CListView.cpp`, `src/gui/panel/CGameInventoryPanel.h`, `src/gui/panel/CGameInventoryPanel.cpp`, `src/gui/panel/CGameFightPanel.h`, `src/gui/panel/CGameFightPanel.cpp`, `res/config/panels.json`, `tests/unit/test_coords.cpp`, `TODO_WORKLOG.md`, and `todo.txt`
  - `git fetch origin --prune`
  - GitHub `main` verification of `mcp.py`, `README.md`, `test.py`, `src/core/CModule.cpp`, `src/handler/CGuiHandler.h`, and `src/handler/CGuiHandler.cpp` before editing
  - `git submodule update --init --recursive`
  - `clang-format -i src/core/CModule.cpp src/handler/CGuiHandler.h src/handler/CGuiHandler.cpp`
  - `python3 -m py_compile mcp.py test.py` -> completed successfully
  - `python3 -m unittest test.McpServerTest.test_export_module_includes_pybind_class_methods` -> `Ran 1 test`, `OK`
  - `python3 -m unittest test.McpServerTest.test_stdio_handshake_and_tool_listing` -> `Ran 1 test`, `OK`
  - `python3 -m unittest test.McpServerTest.test_stdio_gui_inventory_dump_from_repo_root` -> `Ran 1 test`, `OK`
  - `python3 - <<'PY' ...` -> wrote `/tmp/game-gui-tree.json`, printed `CGameInventoryPanel`, and confirmed 5 top-level GUI children after `openPanel("inventoryPanel")`
  - `timeout 120s /home/andrz/.local/bin/black -l 120 mcp.py test.py` -> printed `All done!` and `2 files left unchanged`, but the wrapper still exited with code `124` after two trailing `Aborted!` lines during worker shutdown
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `[100%] Built target _game`, `[100%] Built target for_unit_tests`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> `/tmp/game-gui-python.log` ended with `Ran 80 tests in 98.953s` and `OK`
  - `./scripts/run_coverage.sh` -> configured and built `cmake-build-coverage`, `ctest` passed, then the instrumented `python3 test.py` phase emitted `..........................................` and remained CPU-bound until it was terminated with `kill -9`; the script ended with `./scripts/run_coverage.sh: line 27:   226 Killed                  GAME_BUILD_DIR="${BUILD_DIR}" python3 test.py`
- Blockers if unresolved: Functional validation passed, but the required coverage step is still blocked by the repo's instrumented `python3 test.py` phase hanging without producing a coverage report, so no fresh scoped percentage was produced for this batch.

## Batch 20
- Location: `README.md`, `docs/testing.md`, `TODO_WORKLOG.md`
- Original TODO or summary: PR `#189` documented the testing flow, but review feedback correctly noted that the fresh-checkout instructions still omitted `./configure.sh` and that the coverage trigger wording was too narrow because it only mentioned `test.py`.
- Status: fixed
- What was changed: Added `./configure.sh` to the fresh-checkout prep flow in `README.md` and `docs/testing.md`, broadened the coverage trigger wording to all test changes with concrete examples (`test.py` and `tests/unit/**`), and recorded the updated docs-sync batch after rebasing onto the newer `origin/main`.
- Why the change is correct: The repo workflow already requires configuration before a fresh checkout can build, and `AGENTS.md` requires coverage when changing tests in general rather than only `test.py`. The updated wording matches the executable repo workflow and the review findings without changing runtime behavior.
- Validation performed:
  - source verification of `AGENTS.md`, `README.md`, `docs/testing.md`, `TODO_WORKLOG.md`, and `.github/workflows/build.yml`
  - GitHub `main` verification of `README.md`, `docs/testing.md`, and `TODO_WORKLOG.md` before editing
  - review verification of PR `#189` comments on `docs/testing.md`
  - `git rebase origin/main` -> conflicted only in `TODO_WORKLOG.md`; resolved manually
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `[100%] Built target _game`, `[100%] Built target for_unit_tests`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> `/tmp/pr189-python.log` ended with `Ran 81 tests in 138.273s` and `OK`
- Blockers if unresolved: None. This batch only updates documentation and worklog bookkeeping, so `./scripts/run_coverage.sh` was not required by the repository rules.

## Batch 21
- Location: `src/gui/object/CMapGraphicsObject.cpp`, `test.py`, `TODO_WORKLOG.md`
- Original TODO or summary: Map movement could leave black rectangular holes and stale-looking map content because proxy cells reused the same cached tile/object animation instances while the player-centered viewport was shifting underneath them.
- Status: fixed
- What was changed: Stopped reusing shared cached map animation instances inside `CMapGraphicsObject::getProxiedObjects(...)` by building fresh per-proxy `CAnimation` objects for tiles and map objects while preserving the configured priority from the cached animation. Added a focused GUI regression in `test.py` that loads the `test` map with a GUI, moves the player east and back west, serializes `CMapGraphicsObject`, and asserts that no proxy cell is left without children after either move.
- Why the change is correct: The verified repro was not a texture or asset problem. On the `test` map, a one-tile move used to leave 22 serialized proxy cells with zero children even though each proxy should still contain at least its tile renderable. The root cause was map proxies sharing object-owned animation instances across multiple GUI cells and movement refreshes. Fresh per-proxy animations remove that ownership collision while still allowing wrapped maps to show the same world tile in more than one GUI slot.
- Validation performed:
  - source verification of `src/gui/object/CMapGraphicsObject.cpp`, `src/gui/object/CGameGraphicsObject.cpp`, `src/gui/object/CProxyGraphicsObject.cpp`, `src/gui/object/CProxyTargetGraphicsObject.cpp`, `src/gui/CAnimation.cpp`, `src/gui/CAnimation.h`, `src/gui/CLayout.cpp`, `src/core/CMap.cpp`, `src/object/CMapObject.cpp`, `test.py`, and `TODO_WORKLOG.md`
  - `git fetch origin --prune`
  - `git revert --no-edit 25177e82` -> removed the earlier incorrect asset-only fix from this branch before implementing the proxy-path fix
  - `python3 - <<'PY' ...` -> headless GUI repro on the `test` map showed `(858, 22, 0, 2)` proxy-child counts after a one-tile east move before the final fix and `(858, 0, 1, 2)` after the final fix
  - `clang-format -i src/gui/object/CMapGraphicsObject.cpp`
  - `black -l 120 test.py` -> `1 file left unchanged`
  - `python3 -m unittest test.GameTest.test_map_proxy_cells_remain_populated_after_player_move` -> `Ran 1 test`, `OK`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `ninja: no work to do.`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> `Ran 82 tests in 138.766s`, `OK`
  - `./scripts/run_coverage.sh` -> `Ran 82 tests in 622.127s`, `OK`, `lines: 83.12% (2944 out of 3542)`
- Blockers if unresolved: None. Manual visual confirmation in the original screenshot scene is still advisable, but the verified proxy-hole repro is now covered automatically.

## Batch 22
- Location: `test.py`, `src/core/CModule.cpp`, `src/gui/panel/CCreatureView.cpp`, `src/gui/panel/CCreatureView.h`, `src/gui/panel/CListView.cpp`, `todo.txt`
- Original TODO or summary: `todo.txt` still tracked missing regression coverage for quest-item selection guards in inventory/fight panels and inventory/equipped selection reset.
- Status: fixed
- What was changed: Added xvfb GUI regressions that assert quest-tagged `letterToBeren` items do not become selected in inventory or fight item lists, and that equipping an inventory sword clears inventory selection before selecting the equipped slot. Exposed `CGameFightPanel.setEnemy(...)` for nonblocking fight-panel fixtures. While wiring the fight-panel regression, fixed the creature-view effects collection signature to match `CListView` callback invocation and guarded `CListView` refresh-object connections against scripts that temporarily resolve to `None`.
- Why the change is correct: The guarded item-selection behavior already existed but had no active regression coverage. The new tests verify the rendered selection state through serialized `CSelectionBox` children instead of visual screenshots, so they exercise the actual GUI callback path without adding image baselines. The fight-panel fixture also covers a real initialization path that previously crashed when nested list refresh scripts were scheduled before every target object was available.
- Validation performed:
  - source verification of `todo.txt`, `TODO_WORKLOG.md`, `test.py`, `src/core/CModule.cpp`, `src/gui/panel/CGameInventoryPanel.cpp`, `src/gui/panel/CGameFightPanel.cpp`, `src/gui/panel/CCreatureView.cpp`, `src/gui/panel/CCreatureView.h`, `src/gui/panel/CListView.cpp`, and `res/config/panels.json`
  - `black -l 120 test.py` -> `1 file left unchanged`
  - `clang-format -i src/core/CModule.cpp src/gui/panel/CCreatureView.h src/gui/panel/CCreatureView.cpp src/gui/panel/CListView.cpp`
  - `env GAME_XVFB_GAMEPLAY_CHILD=1 SDL_VIDEODRIVER=x11 SDL_AUDIODRIVER=dummy SDL_RENDER_DRIVER=software LIBGL_ALWAYS_SOFTWARE=1 xvfb-run -a --server-args="-screen 0 1920x1080x24" python3 test.py XvfbGameplayProcessTest.test_inventory_equipped_selection_resets_inventory_selection XvfbGameplayProcessTest.test_inventory_quest_item_selection_is_ignored XvfbGameplayProcessTest.test_fight_quest_item_selection_is_ignored` -> `Ran 3 tests in 20.706s`, `OK` (run outside the sandbox because sandboxed `/tmp/.X11-unix` permissions made successful xvfb children exit nonzero)
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> `[100%] Built target _game`, `[100%] Built target for_unit_tests`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> `Ran 120 tests in 268.767s`, `OK (skipped=19)` (run outside the sandbox for xvfb child processes)
  - `./scripts/run_coverage.sh` -> configured and built `cmake-build-coverage`, `ctest` passed, embedded `python3 test.py` passed with `Ran 120 tests in 335.984s`, then report generation failed the configured total line gate: `lines: 81.9% (6737 out of 8222)`, below `90.0%`
  - `python3 scripts/coverage_report.py --root . --build-dir cmake-build-coverage --report-dir coverage --min-line 90 --jobs $(nproc)` -> also failed the total line gate: `lines: 82.04% (6766 out of 8247)`, below `90.00%`
- Blockers if unresolved: Functional validation passed, but the required coverage command still fails at report generation because the repository's total line coverage is below the configured 90% threshold.

## Batch 23
- Location: `CMakeLists.txt`, `src/core/CExport.h`, `src/core/CModule.cpp`, `src/core/CModuleEntry.cpp`, `src/core/CModuleInit.h`, `src/core/CTypes.cpp`, `src/plugin/NativePlugin.h`, `test.py`, `TODO_WORKLOG.md`
- Original TODO or summary: PR `#259` still targeted `dynamic-cpp-plugin-support` and needed to be replayed onto current `main` after PRs `#260` and `#261` merged, without weakening the 90% coverage gate or reintroducing old dynamic-plugin support changes already present on `main`.
- Status: fixed
- What was changed: Rebased `split-cpp-classes-dynamic-plugins` onto latest `origin/main` using `origin/dynamic-cpp-plugin-support` as the old-base boundary, preserving the newer coverage, Xvfb, and runtime-regression work from PRs `#260` and `#261`. Kept core/GUI static type registration intact while leaving gameplay-domain builders in manifest-loaded native plugins. Added explicit exported module-entry glue for Windows so `game_core`, `_game`, and native plugin DLLs link cleanly without relying on broad auto-export behavior. Expanded dynamic native-plugin regression coverage to prove manifest-loaded gameplay plugins register representative gameplay classes, create/clone/serialize/load representative objects, keep Python wrapper registration working across the split, exercise dynamic controller paths, load generated map content, and isolate console event coverage in a fresh child process. Disabled the native file logger before temporary log-directory cleanup so Windows CI can remove the test log file after logger-sink coverage.
- Why the change is correct: The refreshed branch now contains only the remaining PR `#259` gameplay native-plugin split on top of `main`. `res/plugins/manifest.json` still loads the native marker plugin followed by deterministic gameplay-domain native plugins, while `_game` retains pybind metadata for serializers, builders, custom setters, pointer/set/map serializers, and Python wrapper relations. The Windows export split keeps the build-tree and install-tree plugin layout usable by exporting only the module initializer and native registration entry points needed by `_game` and plugin targets.
- V_META TODO status: `todo.txt` is still non-empty, and the broad `//TODO: add mechanism to ensure registering every V_META in CTypes.cpp` entry was intentionally left unchanged. This PR narrows and tests the gameplay native-plugin registration surface, but it does not prove every `V_META(...)` class in the whole repo is registered automatically; remaining core/resource/internal types still need a dedicated audit/default-constructor decision.
- Validation performed:
  - source verification of `AGENTS.md`, `docs/testing.md`, `TODO_WORKLOG.md`, `todo.txt`, `CMakeLists.txt`, `src/core/CTypes.h`, `src/core/CTypes.cpp`, `src/plugin/NativePlugin.h`, `src/plugin/NativePlugin.cpp`, `res/plugins/manifest.json`, `test.py`, and `scripts/run_coverage.sh`
  - `git fetch origin --prune`
  - PR verification: PR `#260` and PR `#261` are merged into `main`; PR `#259` was open, non-draft, and still based on `dynamic-cpp-plugin-support` before the refresh
  - `git rebase --onto origin/main origin/dynamic-cpp-plugin-support split-cpp-classes-dynamic-plugins` -> conflicted only in `src/core/CTypes.cpp`; resolved by preserving latest `main` core/GUI static registrations and keeping gameplay-domain builders in native plugins
  - `git submodule update --init --recursive`
  - `python3 -m py_compile test.py`
  - `python3 -m black -l 120 test.py --check`
  - `clang-format -i src/core/CModule.cpp src/core/CModuleEntry.cpp src/core/CModuleInit.h src/core/CExport.h src/core/CTypes.cpp src/plugin/NativePlugin.h`
  - `git diff --check`
  - `cmake --build cmake-build-wsl-release --target _game for_unit_tests -j$(nproc)` -> completed successfully
  - `ctest --test-dir cmake-build-wsl-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `GAME_BUILD_DIR=cmake-build-wsl-release python3 -m unittest test.GameTest.test_cpp_plugin_manifest_registers_native_content test.GameTest.test_dynamic_plugin_manifest_registers_native_content test.GameTest.test_dynamic_plugin_direct_load_and_failures test.GameTest.test_dynamic_domain_plugins_register_gameplay_classes test.GameTest.test_dynamic_domain_plugins_serialize_clone_and_load_gameplay_content test.GameTest.test_python_registered_gameplay_wrappers_survive_native_plugin_split test.GameTest.test_dynamic_controller_plugins_drive_map_movement_modes test.GameTest.test_generated_tiled_map_exercises_loader_metadata_and_objects` -> `Ran 8 tests`, `OK`
  - `GAME_BUILD_DIR=cmake-build-wsl-release python3 test.py` -> `Ran 148 tests in 346.121s`, `OK (skipped=20)` before adding the isolated console child coverage test
  - `GAME_BUILD_DIR=cmake-build-wsl-release python3 -m unittest test.ConsoleEventIsolationTest.test_console_key_history_in_fresh_process` -> `Ran 1 test`, `OK`
  - `./scripts/run_coverage.sh` -> `ctest` passed, embedded `python3 test.py` passed with `Ran 150 tests in 957.424s`, `OK (skipped=21)`, and report generation passed with `lines: 90.2% (8352 out of 9262)`
  - Windows Release `cmake --build cmake-build-release --config Release --target _game for_unit_tests` -> completed successfully after allowing vcpkg/CMake to write under `C:\vcpkg`; produced `game_core.dll`, `_game.cp312-win_amd64.pyd`, `for_unit_tests.exe`, and all native plugin DLLs
  - Windows Release `ctest --test-dir cmake-build-release -C Release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - Windows Release bundled Python `python.exe -m unittest test.GameTest.test_cpp_plugin_manifest_registers_native_content test.GameTest.test_dynamic_plugin_manifest_registers_native_content test.GameTest.test_dynamic_plugin_direct_load_and_failures test.GameTest.test_dynamic_domain_plugins_register_gameplay_classes test.GameTest.test_dynamic_domain_plugins_serialize_clone_and_load_gameplay_content` with `GAME_BUILD_DIR=cmake-build-release` and `GAME_BUILD_CONFIG=Release` -> `Ran 5 tests`, `OK`
  - Windows bundled Python `python.exe -m py_compile test.py` -> completed successfully
  - Windows bundled Python `python.exe -m unittest test.GameTest.test_binding_validation_rejects_invalid_logger_and_dynamic_values` with `GAME_BUILD_DIR=cmake-build-release` and `GAME_BUILD_CONFIG=Release` -> `Ran 1 test`, `OK`
  - `GAME_BUILD_DIR=cmake-build-wsl-release python3 -m unittest test.GameTest.test_binding_validation_rejects_invalid_logger_and_dynamic_values` -> `Ran 1 test`, `OK`
  - `./scripts/run_coverage.sh` after the Windows logger cleanup -> `ctest` passed, embedded `python3 test.py` passed with `Ran 150 tests in 923.456s`, `OK (skipped=21)`, and report generation passed with `lines: 90.2% (8350 out of 9262)`
- Blockers if unresolved: None. Windows `python`/`py` shims were not available on the PowerShell PATH, so Windows Python checks used the Codex-bundled Python executable directly.

## Batch 24
- Location: `AGENTS.md`, `src/core/CTypes.cpp`, `src/core/CTypeRegistration.h`, `src/core/CCoreTypeRegistration.cpp`, `src/object/CObjectTypeRegistration.cpp`, `src/handler/CHandlerTypeRegistration.cpp`, `src/gui/CGuiTypeRegistration.cpp`, `src/gui/panel/CGuiPanelTypeRegistration.cpp`, `src/gui/object/CGuiWidgetTypeRegistration.cpp`, `src/gui/CAnimationTypeRegistration.cpp`, `test.py`, `todo.txt`
- Original TODO or summary: Runtime type registration for static engine, handler, GUI, panel, widget, and animation classes was concentrated in `CTypes.cpp`, and `todo.txt` still asked for a broad mechanism to ensure every `V_META` type is registered.
- Status: fixed
- What was changed: Added a small module registration declaration layer and moved the existing static registration groups into module-owned registration units. `CTypes.cpp` now keeps the registry storage and one static initializer that calls the module registration functions in sequence. The existing `CTypes::register_type<T>()`, custom serializer registration, builder registration, and metadata APIs remain unchanged. Added a regression test that creates representative registered classes through `CGameLoader.loadGame()` and verifies configured JSON type ids still instantiate through the initialized object handler. Updated the repository delivery workflow in `AGENTS.md` to require commit, push, PR creation, and enabling auto-merge without waiting for remote checks after auto-merge is set.
- Why the change is correct: The refactor preserves the same runtime registration mechanism and static initialization point while moving class ownership out of the monolithic registry body. The regression exercises the loader-to-handler path used by object creation and JSON loading, covering representative object, core, handler, GUI, panel, widget, and animation registrations. The broad `V_META` TODO was narrowed rather than removed because the new test is representative, not an exhaustive declaration audit. The `AGENTS.md` workflow now matches the requested delivery behavior while still preventing manual bypass of failed checks.
- Validation performed:
  - `clang-format -i src/core/CTypes.cpp src/core/CTypeRegistration.h src/core/CCoreTypeRegistration.cpp src/object/CObjectTypeRegistration.cpp src/handler/CHandlerTypeRegistration.cpp src/gui/CGuiTypeRegistration.cpp src/gui/CAnimationTypeRegistration.cpp src/gui/panel/CGuiPanelTypeRegistration.cpp src/gui/object/CGuiWidgetTypeRegistration.cpp`
  - `black -l 120 test.py` -> `1 file left unchanged`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> completed successfully
  - `python3 -m unittest test.GameTest.test_static_module_type_registration_initializes_runtime_factories` -> `Ran 1 test`, `OK`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> all shards and serial tests passed
  - `git diff --check` -> no whitespace errors
  - `./scripts/run_coverage.sh` -> C++ tests passed, embedded `python3 test.py` passed, and report generation passed with `lines: 91.3% (8805 out of 9644)`
- Blockers if unresolved: None.

## Batch 25
- Location: `src/core/CGameContext.h`, `src/core/CGameContext.cpp`, `src/core/CGame.h`,
  `src/core/CGame.cpp`, `src/core/CModule.cpp`, `test.py`, `todo.txt`
- Original TODO or summary: `CGame` still lazily constructed several runtime services directly, while `todo.txt`
  tracked broad singleton/context work without an explicit service-owner seam.
- Status: fixed
- What was changed: Added `CGameContext` as the first explicit per-game runtime service context. `CGame` now owns a
  `std::shared_ptr<CGameContext>` and keeps the existing `getObjectHandler()`, `getScriptHandler()`, and
  `getRngHandler()` APIs by delegating to context-owned stable service instances. Added `CGame::getContext()` and a
  minimal Python binding for `CGameContext` plus `CScriptHandler` so public regression coverage can exercise the new
  seam. `CGuiHandler`, `CSlotConfig`, active map, and active GUI intentionally remain owned by `CGame` for now because
  they are still tied to UI/session state or deserialized game configuration. Narrowed the context TODO to the
  remaining global/static providers and UI/session services.
- Why the change is correct: The loader still initializes object builders, JSON configs, and plugins through the same
  `CGame` public getters, so object creation, JSON loading, plugin loading, and serialization continue to receive the
  owning `CGame`. `CGameContext` stores only a `std::weak_ptr<CGame>` for services that need the game during lazy
  construction, avoiding a new strong `CGame -> CGameContext -> CGame` cycle while leaving the existing
  `CGameObject::getGame()` ownership model unchanged. The regression proves the context is non-null after
  `CGameLoader.loadGame()`, service instances are stable and shared with existing `CGame` getters, configured object
  creation remains per-game, and `startGameWithPlayer()` still creates map/player objects with the same owning game.
- Validation performed:
  - `git fetch origin main` -> updated `origin/main` from `99558a69` to `8e1060fe`
  - `git rebase --autostash origin/main` -> completed cleanly and reapplied the local changes
  - `clang-format -i src/core/CGameContext.h src/core/CGameContext.cpp src/core/CGame.h src/core/CGame.cpp src/core/CModule.cpp`
  - `black -l 120 test.py` -> `1 file left unchanged`
  - `python3 -m unittest test.GameTest.test_game_context_owns_runtime_services_and_preserves_creation` -> `Ran 1 test`, `OK`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)` -> completed successfully after CMake regenerated the build files
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests` -> `1/1 Test #1: for_unit_tests ... Passed`
  - `python3 test.py` -> all shards and serial tests passed on the rebased branch
  - `./scripts/run_coverage.sh` -> C++ tests passed, embedded `python3 test.py` passed, and report generation passed with `lines: 92.00% (9040 out of 9826)`
- Blockers if unresolved: None. A pre-rebase `python3 test.py` run wedged in a GUI shard and was terminated; the
  isolated shard, full suite rerun, and final post-rebase full suite all passed.

## Batch 26
- Location: `res/maps/multilevel/map.json`, `res/maps/multilevel/config.json`,
  `res/maps/multilevel/script.py`, `res/images/buildings/stairs_up.png`,
  `res/images/buildings/stairs_down.png`, `res/images/buildings/catacombs.png`, `CMakeLists.txt`,
  `src/core/CMap.cpp`, `tests/unit/test_coords.cpp`,
  `test.py`, `mcp.py`, `todo.txt`
- Original TODO or summary: Add a real authored multilevel map with deterministic level transitions, movement support,
  save/load coverage, and gameplay-facing walkthrough validation. The existing `todo.txt` item about multilevel
  pathfinding was too broad for the connector-based support implemented here.
- Status: fixed for authored connector-based multilevel gameplay; generalized multilevel pathfinding remains tracked.
- What was changed: Added the `multilevel` map with explicit z=0 and z=1 tile layers, z-specific object layers,
  entry coordinates, level-specific blockers, goal events, and `LevelStairs` transition objects. The stairs publish
  waypoint metadata for player pathfinding and use a one-event guard so landing on the paired stair does not bounce the
  player back immediately. Added the supplied `stairs_up.png` and `stairs_down.png` image assets under
  `res/images/buildings/`, then integrated the supplied `catacombs.png` as the level-1 goal landmark. Updated the
  authored animation ids and wired all new map/image resources through CMake.
  Tightened `CMap::canStep()` so missing sparse tiles honor configured default/out-of-bounds passability without
  materializing tiles or bumping navigation revisions. Narrowed MCP controller access to player handles while allowing
  MCP walkthroughs to drive the real player through `CPlayerController`.
- Why the map is truly multilevel: `map.json` contains separate authored tile and object layers with
  `properties.level` values for levels 0 and 1. Runtime tests assert level-specific tiles and objects load at the
  expected z values, blockers only affect their own z level, and the player can move from level 0 to level 1 and back
  through authored stair objects.
- Movement/transition design: Normal same-level movement still uses the existing controller/pathfinder and cardinal
  adjacency. Cross-level movement is connector-based: `stairsUp` and `stairsDown` are stepable map objects that expose
  `waypoint`, `x`, `y`, and `z` for the opposite landing and move the player on `onEnter` after validating
  `canStep(target)`. This supports the authored route without treating every matching x/y on another floor as adjacent.
- Tests added: Native unit tests cover z-specific tile/object/cache separation, explicit waypoint cross-level
  pathfinding, and non-mutating default-tile `canStep()` checks. Python integration tests cover authored z-layer
  loading, controller-driven up/down stair movement, save/load after moving to z=1, z-scoped stale collision cache
  behavior, and the `multilevel` walkthrough. MCP tests cover the same gameplay route over stdio and verify all playable
  maps have MCP walkthroughs. A security-scope regression keeps non-player creature controller access denied over MCP.
- Validation performed:
  - `python3 -m json.tool res/maps/multilevel/map.json`
  - `python3 -m json.tool res/maps/multilevel/config.json`
  - `python3 -m py_compile test.py mcp.py res/maps/multilevel/script.py`
  - `file res/images/buildings/stairs_up.png res/images/buildings/stairs_down.png res/images/buildings/catacombs.png`
  - `python3 - <<'PY' ... PIL Image.open(...) ... PY` -> all supplied PNGs load as 1024x1024 RGBA
  - `black -l 120 test.py mcp.py res/maps/multilevel/script.py`
  - `clang-format -i src/core/CMap.cpp tests/unit/test_coords.cpp`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests`
  - `python3 test.py GameTest.test_map_json_tiled_compatibility GameTest.test_map_walkthrough_test
    McpServerTest.test_stdio_map_walkthrough_test
    McpServerTest.test_engine_handle_call_scopes_controller_access_to_players
    GameTest.test_multilevel_map_loads_authored_z_layers
    GameTest.test_multilevel_map_player_uses_stairs_both_directions
    GameTest.test_multilevel_map_z_state_persists_after_save_load
    GameTest.test_multilevel_map_stale_collision_cache_is_z_scoped GameTest.test_map_walkthrough_multilevel
    McpServerTest.test_stdio_map_walkthrough_multilevel McpServerTest.test_stdio_map_walkthroughs_cover_all_maps`
    -> `Ran 11 tests`, `OK`
  - `git diff --check` -> no whitespace errors
  - `python3 test.py` -> all shards and serial tests passed, including MCP map walkthroughs and Xvfb gameplay shards
  - `./scripts/run_coverage.sh` -> C++ tests passed, embedded `python3 test.py` passed, and report generation passed
    with `lines: 90.34% (9455 out of 10466)`
  - `python3 mcp.py --stdio --repo-root . --build-dir cmake-build-release` -> modules imported, 10 callables
    exported, stdio server started, then exited cleanly when stdin closed
- Blockers if unresolved: The first user-provided path `/mnt/c/Users/andrz/OneDrive/Pulpit/stairs.png` was not visible
  in this runtime. The later `/mnt/c/Users/andrz/Downloads/stairs_up_and_down.zip` was visible and was extracted into
  versioned source assets. The later `catacombs.png` asset was available from
  `/mnt/c/Users/andrz/OneDrive/Pulpit/catacombs.png` and was integrated as the level-1 landmark.

## Batch 27
- Location: `src/core/CSceneManager.h`, `src/core/CSceneManager.cpp`, `src/core/CGame.h`,
  `src/core/CGame.cpp`, `src/core/CLoader.cpp`, `src/core/CModule.cpp`, `mcp.py`,
  `tests/unit/test_map.cpp`, `test.py`, `CMakeLists.txt`, `TODO_WORKLOG.md`
- Original TODO or summary: Map switching was implemented directly in `CGameLoader::changeMap(...)`, making it hard to
  reason about queued transition state, duplicate requests, and future multilevel-map/session policy. The task asked for
  a `CSceneManager`/`CWorldSession` boundary while preserving the existing queued Nouraajd -> ritual behavior and adding
  unit, integration, save/load, and MCP-style coverage.
- Status: fixed
- What was changed: Added `CSceneManager` as a per-game transition manager owned by `CGame`. `CGame::changeMap(...)`
  and `CGameLoader::changeMap(...)` remain public compatibility wrappers, but `CGameLoader::changeMap(...)` now delegates
  to `CSceneManager::requestMapChange(...)`. The manager stores explicit `Idle`, `TransitionPending`, and `Transitioning`
  state, queues work through the same event-loop path, waits for the current map to stop moving, loads the target through
  the existing `CMapLoader::loadNewMap(...)` path, swaps the active map, transfers the same player object, and copies the
  old turn counter. Duplicate requests while pending or transitioning are logged and ignored. Added pybind exposure and
  MCP handle allowlist coverage for `CGame.getSceneManager()` and the small transition-inspection API. During the rebase
  onto current `main`, the native C++ coverage was moved from the deleted legacy `tests/unit/test_coords.cpp` into
  `tests/unit/test_map.cpp`.
- Why the change is correct: The transition execution sequence remains the legacy sequence, only moved behind a reusable
  per-game boundary with observable state. The duplicate policy is deliberately conservative: while a transition is
  pending or executing, the first accepted target wins and later requests are rejected without replacing the pending
  target. A nested redirect requested by a destination entry trigger is covered explicitly and remains on the first
  destination. Old-map caching/restoration is intentionally still out of scope, so the `todo.txt` entry about returning to
  the old map remains open.
- Tests added: C++ unit coverage for lifecycle state, duplicate rejection, turn copy, same-player transfer, controller
  usability after a switch, repeated sequential switches, null-game rejection, empty-map compatibility, and missing-map
  legacy compatibility. Python integration coverage covers deferred event-loop switching, duplicate request policy, real
  `test -> ritual -> siege` transitions, nested destination-entry redirect rejection, save/load after a transition, and
  the authored Nouraajd -> ritual -> siege campaign route. MCP stdio coverage drives a real server session through
  `CGame.changeMap("ritual")` and asserts active map, player state, inventory, turn, quest, and manager state.
- Validation performed before this rebase:
  - `cmake -G Ninja -B cmake-build-release -S . -DCMAKE_BUILD_TYPE=Release`
  - `cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)`
  - `ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests`
  - `python3 -m unittest test.McpServerTest.test_export_module_includes_pybind_class_methods
    test.GameTest.test_change_map_waits_for_event_loop_after_move_event
    test.GameTest.test_scene_manager_duplicate_transition_keeps_first_request
    test.GameTest.test_scene_manager_real_map_transitions_preserve_player_state_and_triggers
    test.GameTest.test_save_load_after_scene_manager_transition_preserves_active_map_player_state
    test.GameTest.test_campaign_transitions_preserve_player_and_start_siege
    test.McpServerTest.test_stdio_scene_manager_map_transition_walkthrough` -> `Ran 7 tests`, `OK`
  - `python3 -m unittest test.GameTest.test_gui_includes_display_only_minimap_layout` -> `Ran 1 test`, `OK`
  - `python3 -m unittest test.GameTest.test_scene_manager_duplicate_transition_keeps_first_request
    test.GameTest.test_scene_manager_real_map_transitions_preserve_player_state_and_triggers
    test.GameTest.test_scene_manager_rejects_nested_transition_from_destination_entry
    test.GameTest.test_save_load_after_scene_manager_transition_preserves_active_map_player_state
    test.McpServerTest.test_stdio_scene_manager_map_transition_walkthrough` -> `Ran 5 tests`, `OK`
  - `python3 test.py` -> completed successfully
  - `./scripts/run_coverage.sh` -> C++ tests passed, embedded `python3 test.py` passed, and report generation passed with
    `lines: 90.17% (9493 out of 10528)`
- Blockers if unresolved: None.
