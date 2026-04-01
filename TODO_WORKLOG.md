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
