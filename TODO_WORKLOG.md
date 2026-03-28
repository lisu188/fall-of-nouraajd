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
