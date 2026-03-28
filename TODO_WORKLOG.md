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
