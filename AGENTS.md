# AGENTS.md

## Scope

These instructions apply to the entire repository unless a more specific `AGENTS.md` exists deeper in the tree.

The default branch is `main`.

Keep changes narrow. Do not modify unrelated files, generated build output, packaged artifacts, dependency lock state, or submodule SHAs unless the task explicitly requires it. Do not rebase or update from `main` unless asked. If a task requires touching `random-dungeon-generator` or `vstd`, state that clearly and rerun the full validation workflow.

## Pull request merge policy

Never push directly to `main`. Publish reviewable pull requests and use squash merging only.

For every PR, run focused local validation, open the PR, and let the GitHub Actions `build` workflow supply
compilation, full-suite, and coverage evidence. Wait for the selected required checks to succeed before merging.

Auto-merge is not an unconditional default; it requires explicit authorization before you run
`gh pr merge <PR_NUMBER> --auto --squash`:

- allowed: the repository reports `allow_auto_merge=true` and branch protection/check state permits it, so enable
  squash auto-merge.
- user-authorized: the user or a newer system instruction explicitly directs this merge even though the default probe
  is not conclusive, so enable squash auto-merge per that explicit authorization.
- disallowed: the repository reports auto-merge disabled or branch protection/check state blocks it, so leave the PR
  open, request the repository setting change or explicit alternate merge authorization, and report the exact blocker.
- unknown: authorization cannot be verified from the repository, so leave the PR open and report a blocker; do NOT
  auto-merge on an unverified default.

If validation or auto-merge is blocked, or the authorization state is disallowed or unknown, report the exact blocker
and leave the PR intact.

## Project overview

`fall-of-nouraajd` is a C++ dark-fantasy 2D game with Python scripts/plugins, JSON resource configuration, SDL assets, CMake builds, and a pybind11 `_game` extension module.

Important paths:

- `src/core/` — engine core, loaders, wrappers, type registry, Python bindings.
- `src/handler/` — gameplay handlers and script/event handling.
- `src/object/` — game object model.
- `src/gui/` — GUI objects, layouts, panels, and rendering-facing classes.
- `res/config/` — global JSON configuration for items, effects, tiles, panels, monsters, slots, and related content.
- `res/maps/<map>/` — map JSON, dialogs, and map scripts.
- `res/plugins/` — Python plugin definitions loaded into the game.
- `tests/unit/` — native C++ tests.
- `test.py` — Python/data/integration/GUI-oriented test suite.
- `scripts/` — coverage and repository helper scripts.
- `cmake/` — CMake modules and platform triplets.
- `random-dungeon-generator/`, `vstd/` — external submodules.

## Fresh checkout setup

Run commands from the repository root.

Linux:

```sh
git submodule update --init --recursive
./configure.sh
```

The README’s Ubuntu setup uses Python and pybind11 headers before configuration; JSON parsing is vendored in the tree.

Windows:

- Use Visual Studio 2022 with Desktop development with C++ and CMake tools.
- Use Python 3.12.
- Bootstrap vcpkg and set `VCPKG_ROOT`.
- Run `configure.bat` from a normal `cmd.exe` shell.

Do not add new production dependencies without explicit approval. Prefer existing CMake, vcpkg, Python, and system-package setup.

## Build and run

Linux build:

```sh
cmake --build cmake-build-release --target _game -j$(nproc)
```

Windows Release build:

```bat
cmake --build cmake-build-release --config Release --target _game
set GAME_BUILD_CONFIG=Release
```

Run the game:

```sh
python3 play.py
```

Run the MCP engine API server:

```sh
cmake --build cmake-build-release --target _game -j$(nproc)
python3 mcp.py
```

For stdio transport:

```sh
python3 mcp.py --stdio --repo-root . --build-dir cmake-build-release
```

On Windows Visual Studio builds, add `--build-config Release` when required.

When adding stdio MCP subprocess tests, drain `stderr` concurrently while the server runs. The server logs tool
activity to `stderr`, and long walkthrough-style tests can block if the pipe is left unread. Prefer setting the MCP
session log level to `critical` after initialization and use `--native-log-sink disabled` or a file sink when native
logs are not part of the assertion. Full-map `jsonify(map)` MCP calls can take longer than ordinary tool calls during
large walkthrough tests, especially under full-suite load; give those calls a wider response timeout than the default
quick protocol checks.

## Required validation

For every code change, satisfy this full workflow. For agent PR delivery, do not run these native-build-heavy commands
locally unless a focused local reproduction is necessary or GitHub Actions cannot provide the needed evidence; normally
use focused local checks, open the PR, and poll the path-selected build workflow checks. Local equivalents are:

```sh
cmake --build cmake-build-release --target _game for_unit_tests performance_guard_tests -j$(nproc)
ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests
ctest --test-dir cmake-build-release --output-on-failure --verbose -L performance
python3 test.py
```

During iteration, use named Python suites for narrower feedback before the required full workflow:

```sh
python3 test.py --suite fast
python3 test.py --suite gameplay
GAME_XVFB_JOBS=4 python3 test.py --suite ui
```

`python3 test.py` and `python3 test.py --suite full` both run the full Python suite. `./scripts/run_coverage.sh` uses
`python3 test.py --suite coverage-safe` for the coverage Python phase.

Prefer GitHub Actions as the default path for heavy validation. Run focused local checks that exercise the
changed behavior, open the pull request, and wait for the GitHub Actions `build` workflow to reach a final successful
conclusion instead of running local compilation, native tests, the full Python suite, and required coverage locally.
Passing the selected build workflow checks is sufficient PR delivery evidence for the validation class selected by
`scripts/ci_change_classifier.py`: native/source/content changes require `linux`, `windows-deps`, and `windows`;
workflow-only docs/tooling changes require the terminal `linux` check and skip unrelated native-heavy steps after
focused workflow validation. Coverage is satisfied by CI only when the workflow's path rule runs the `coverage` step
somewhere in the selected build workflow run, currently in the conditional `linux-coverage` job. Run heavy local
validation only when the PR workflow cannot cover the required evidence, a focused local reproduction is necessary
before opening the PR, or GitHub Actions is unavailable or blocked. Report local commands, skipped or blocked local
commands, and CI job names/conclusions separately; never imply a skipped local command passed. If GitHub merges before
checks finish being observed, fetch `origin/main`, verify the merge, and continue from the merged state.

### CI validation authority for workflow/classifier changes

A pull request must not be able to weaken its own required validation. Changes that touch the validation-authority
files — `.github/workflows/build.yml` and `scripts/ci_change_classifier.py` — cannot self-classify as lightweight.
`scripts/ci_change_classifier.py` marks them as an authority change (`authority-change=true`,
`human-review-required=true`) and forces strict native + coverage validation regardless of the edited logic. A PR
editing the routing/classifier therefore cannot drop required native/coverage checks by relabeling, skipping, or
re-routing. Such changes additionally require explicit human review before merge; do not auto-merge an authority
change on PR-controlled logic alone.

Windows Release equivalent:

```bat
cmake --build cmake-build-release --config Release --target _game for_unit_tests performance_guard_tests
ctest --test-dir cmake-build-release -C Release --output-on-failure -R for_unit_tests
ctest --test-dir cmake-build-release -C Release --output-on-failure --verbose -L performance
set GAME_BUILD_DIR=cmake-build-release
set GAME_BUILD_CONFIG=Release
python test.py
```

The Python tests require the compiled `_game` module for most runtime paths. Tests that do not need `_game` should still be able to run, so import optional `game`/`_game` modules inside the individual tests that need them.

Windows validation portability notes:

- When tests need build-local DLLs such as `SDL2.dll`, resolve them from the active `GAME_BUILD_DIR` and
  `GAME_BUILD_CONFIG` before falling back to system library names.
- Keep temporary backups of build resources such as `save/` inside the build tree; moving OneDrive-backed files through
  `%TEMP%` can fail if the cloud provider is unavailable.
- Python tooling checks should fall back to `python -m <tool>` with the current interpreter when console scripts are not
  present on `PATH`.
- On Windows multi-config builds, the compiled `_game` module lives under a config directory such as `Release/`, while
  copied resources may live in the build root. Resource lookup and MCP tests should account for both locations and treat
  missing config-local resource directories as normal misses, not canonicalization failures.

When validation cannot be run, do not imply that it passed. Report the exact command that was skipped or failed and the reason.

Every bug fix must include at least one corresponding automated test (unit, integration, or regression) that fails before the fix and passes after it. Treat this as required bugfix test coverage; do not mark a bug fix complete without a regression test covering the fixed behavior.

## Build, test, and coverage time optimization

Treat build, test, and coverage runtime as a first-class maintenance concern. Optimize aggressively for fast
feedback while preserving the required validation guarantees.

- During iteration, prefer the narrowest reliable build or test command that exercises the changed behavior, then satisfy
  heavy compilation, native tests, full Python suites, and coverage through completed GitHub Actions polling for the PR
  head before finishing.
- Avoid local native builds for PR delivery when GitHub Actions can run them. If a local build is genuinely necessary,
  use available parallelism such as `-j$(nproc)` without hiding failures or racing shared test state.
- Avoid unnecessary clean builds, dependency reinstalls, broad resource recopies, full-suite reruns, or repo-wide
  formatting when a targeted command is sufficient.
- Keep new and updated tests deterministic, focused, and reasonably scoped; split slow end-to-end coverage from fast
  regression checks when correctness allows.
- When adding scripts, CI steps, fixtures, MCP walkthroughs, or coverage checks, account for their runtime cost and avoid
  repeated expensive setup inside loops or per-test fixtures.
- If a required validation command is slow or native-build-heavy, do not block PR delivery on duplicating it locally when
  GitHub Actions can run the same evidence. Push the PR, poll the selected job, and report exact blockers only when
  neither local execution nor CI polling can supply the evidence.

## Performance regression testing

Native performance guards are part of normal validation. Build them with the `performance_guard_tests` target and run
them through CTest label `performance` with visible output:

```sh
cmake --build cmake-build-release --target performance_guard_tests -j$(nproc)
ctest --test-dir cmake-build-release --output-on-failure --verbose -L performance
```

On Windows Visual Studio Release builds, include `--config Release` on the build command and `-C Release` on the CTest
command.

Profile before claiming a bottleneck or changing performance-sensitive behavior. Add or update a performance guard for
changes to pathfinding, AI/controllers, map turns, spatial caches, serialization/loading, rendering hot paths, or any
measured hot loop. Do not rely on intuition alone.

Performance guards must be deterministic CI gates, not diagnostic-only measurements. Prefer bounded work, expansion,
callback, cache-entry, and reuse/invalidation counts over elapsed time. Keep workloads fixed, avoid external services and
non-deterministic inputs, and keep output visible enough to diagnose the failing budget in CI logs. The guard target must
remain safe on Linux and Windows and must not add new dependencies without explicit approval.

Timing is supplemental evidence only. If timing is used, run Release builds with warm-up and repeated samples, report a
median or ratio with enough headroom for CI variance, and never make a tight one-shot millisecond assertion the sole
gate. Large benchmarks stay opt-in and outside PR gates.

Any budget change must include before/after evidence, platform and build details, the exact commands used, and a
rationale. Do not weaken, delete, skip, or silently rebaseline a budget merely to make CI pass. Intentional algorithmic
changes must update the guard and rationale in the same change.

Final reports for performance-sensitive work must include exact before/after commands and results. If a performance
command cannot be run, report the unavailable or skipped command honestly with the blocker.

## MCP game-session validation

When a change affects maps, quests, dialogs, triggers, map scripts, gameplay-facing C++ bindings, or MCP tooling
used to drive gameplay, validate it with an MCP game session in addition to the automated tests.

Use the stdio MCP server after building `_game` so it exercises the current binary and copied resources:

```sh
python3 mcp.py --stdio --repo-root . --build-dir cmake-build-release
```

On Windows Visual Studio builds, include the build config when needed:

```bat
python mcp.py --stdio --repo-root . --build-dir cmake-build-release --build-config Release
```

For gameplay changes, the MCP session must drive a real game instance rather than only mutating flags:

- Start the target map with `CGameLoader.loadGame` and `CGameLoader.startGameWithPlayer`.
- Obtain the active map and player handles, usually through `CGame.getMap` and `CMap.getPlayer`.
- Move the actual player through the authored route with `CMapObject.moveTo` or controller movement before firing
  quest, dialog, combat, or trigger progress.
- Move to relevant authored object coordinates such as start events, NPCs, caves, doors, teleporters, or encounter
  leaders before invoking related actions.
- Pump queued work with `event_loop.instance().run()` after movement, dialogs, `changeMap`, and other queued engine actions.
- Assert observable state through MCP, including active and completed quests, map flags/properties, inventory changes,
  rewards, spawned or removed objects, and final map transitions.

If copied build resources are stale, rebuild or report the blocker. Do not edit generated build output to force the MCP
run. If an MCP game-session check cannot be run, report the exact command or step that was blocked and why.

## Coverage

For PR delivery, use the PR `linux` GitHub Actions job with `--require-step coverage` when a change touches:

- `test.py`
- `tests/unit/**`
- `scripts/run_coverage.sh`
- coverage tooling
- `native_plugins/**`
- `src/core/**`
- `src/handler/**`
- `src/object/**`

Local coverage is a fallback only when CI cannot cover the required evidence, polling is unavailable, or a focused local
coverage reproduction is necessary. Local coverage command:

```sh
./scripts/run_coverage.sh
```

`scripts/run_coverage.sh` uses the repository Python coverage reporter as the default line gate. Use
`COVERAGE_REPORTER=gcovr ./scripts/run_coverage.sh` only for diagnostic comparison; gcovr has counted extra
instrumented/generated lines differently in this repo and can fail the gate even when the canonical reporter passes.
The script builds and runs the native `performance_guard_tests` CTest entry as part of coverage validation.
Coverage line exclusions are not supported; every instrumented line in scope is part of the line gate.

The default eligible-line coverage threshold is 90%. Do not finish coverage-relevant work below that threshold without
explicitly reporting it.

Coverage reports are generated under `coverage/`.

## GUI and screenshot tests

When adding or updating GUI-focused tests in `test.py`, follow the existing `XvfbGameplayTest` and `XvfbGameplayProcessTest` style.

Guard platform/tooling preconditions and skip cleanly when unavailable:

- `os.name == "posix"`
- `xvfb-run`
- `xauth`

Run GUI child processes with:

```sh
xvfb-run -a --server-args="-screen 0 1920x1080x24"
```

Use these environment settings for GUI child tests:

```sh
SDL_VIDEODRIVER=x11
SDL_AUDIODRIVER=dummy
SDL_RENDER_DRIVER=software
LIBGL_ALWAYS_SOFTWARE=1
```

Prefer behavior-based assertions: input handling, panel visibility, map turn progression, and rendered map/proxy cell checks.

For screenshot or image artifacts produced by tests, verify at least:

- the output file exists;
- the file is non-empty;
- the extension is expected, usually `.png`;
- the file is loadable or has expected dimensions/metadata;
- deterministic baselines are compared when such baselines exist.

### Screenshot regeneration and coverage

Regenerate screenshots after every major UI change (layout, panels, widgets, rendering, or theming). Stale
screenshots must not be left behind once the rendered result has changed.

When regenerating, the screenshot set must cover, at minimum:

- at least one screenshot showing each type of panel (one per resource id declared in `res/config/panels.json`);
- at least one screenshot from each map directory under `res/maps/`, plus one from a randomly generated map.

`scripts/generate_screenshots.py` produces exactly this set (`panel-<id>.png` for every panel and `map-<name>.png`
for every map plus `map-random.png`). It drives a real headless GUI session, so it needs the `_game` build and, on
Linux, re-executes itself under `xvfb-run` automatically:

```sh
python3 scripts/generate_screenshots.py --output-dir screenshots
```

## Code style

General:

- Use four spaces for indentation in C++ and Python.
- Keep lines under 120 characters where practical.
- Keep changes minimal and local to the requested behavior.
- Do not rewrite broad areas only for style.
- Do not add comments that merely restate obvious code.
- Do not introduce or reintroduce the legacy three-letter project acronym formed from `F` + `O` + `N`.
  Use `game`, `nouraajd`, or another explicit domain name for code, config, docs, scripts, environment variables,
  filenames, branch names, temporary paths, and generated identifiers.

Python:

- Use `camelCase` for functions and methods, including methods exposed to or called from C++/JSON.
- Use `snake_case` for local variables.
- Use `UPPER_SNAKE_CASE` for global flags and constant-like values.
- Use `CamelCase` for classes.
- Trigger classes decorated with `@trigger` must use `CamelCase` and end with `Trigger`.

C++:

- Use `CamelCase` for class names.
- Use `camelCase` for all methods, including methods exposed to Python.

JSON/resource IDs:

- Keep object and item identifiers in JSON as `camelCase`.
- Use exactly the same IDs when referencing them from Python, map files, dialog definitions, and script calls.

Formatting:

```sh
clang-format -i <modified-cpp-or-header-files>
black -l 120 <modified-python-files>
```

Run formatters only on files relevant to the task unless the task is explicitly repo-wide formatting.

## Resource files and CMake

When adding files under `res/`, update the root `CMakeLists.txt` so the new files are copied or installed.

Use the existing pattern:

- `configure_file(...)` for explicit configured/copied resources.
- `COPYONLY` for binary/static assets.
- `install(DIRECTORY ...)` where the existing install rules already cover whole directories.

Before finishing, verify the new `res/**` files are not missing from CMake resource handling.

## Adding item, tile, effect, potion, building, or similar types

Follow this workflow:

1. Add or update the Python plugin class under `res/plugins/`.
2. Define plugin classes inside `load(context)`.
3. Decorate plugin classes with `@register(context)`.
4. Add the matching JSON entry under `res/config/`, for example `items.json`, `potions.json`, `effects.json`, `tiles.json`, or `buildings.json`.
5. Use the JSON entry key as the stable item/object id.
6. Reference the new id from map configuration, usually under `res/maps/<map>/config.json`.
7. Use `ref` when pointing to a configured object id, or `class` only when defining a class directly.
8. Cross-check every id used in JSON, Python, dialog definitions, and calls such as `createObject("...")`.
9. Run the required validation workflow.

Mismatched ids cause runtime loading or spawning failures.

Plugins may also be authored in Lua (`res/plugins/*.lua`, auto-discovered like
Python): define `load(context)` and call `context.registerType(name, {base =
"CTile", onStep = function(self, creature) ... end})`. Lua supports the bases
CTile, CEffect, CPotion, CScroll, CInteraction, CTrigger, CBuilding, and CEvent
with a curated object API (property get/set, heal/hurt/healProc, getCause,
createObject, randint, log); prefer Python for anything beyond that surface. A
brand-new C++ gameplay class instead needs an `FN_TYPE`/`FN_WRAPPED` row in
`src/plugin/CGameplayTypeTable.h`.

## Adding a creature race, class, or monster archetype

The creature archetype model (races/classes composed onto concrete monster and
player templates) is documented in `docs/design/creature_archetypes.md`; read its
**Developer guide: adding a race, a class, or a monster** section before touching
archetype content. Key rules:

- Author races in `res/config/creature_races.json` (`CCreatureRace`), classes in
  `res/config/creature_classes.json` (`CCreatureClass`), and assign them on
  concrete templates in `res/config/monsters.json` via `{"ref": "..."}`. Both
  archetype objects are already registered through
  `src/plugin/CGameplayTypeTable.h`; new *ids* need only JSON.
- Follow the naming policy (suffix `Race` / `Class`, lowerCamelCase) and never let
  a class id duplicate a concrete template id.
- **Do not rename** concrete monster/player template ids, or any quest/dialog id.
- **Do not make a race player-selectable or add a new player race/class.**
  `CCreatureRace.playerSelectable` defaults to `false`; player-facing roster
  changes are content-owner-gated and must not be inferred by an agent. Assigning
  an existing archetype to a *monster* is fine.
- Keep monster assignments baseline-preserving unless the task changes balance, and
  regenerate `tests/fixtures/creature_stat_scale_baseline.json` if composed stats
  change. New config files also need an explicit `configure_file` line in
  `CMakeLists.txt` (see "Resource files and CMake").

## Dialogs

To add dialog interaction for an item, NPC, or map object:

- Add or update the relevant `CDialog` object in map config or script.
- Use `CDialogState` and `CDialogOption` definitions consistently.
- Ensure every `action`, `condition`, and `nextStateId` matches a real method or state id.
- Implement each custom dialog `action` as a Python method on the dialog class.
- The method name must exactly match the JSON `action` string.
- `ENTRY` and `EXIT` are conventional state ids checked by the dialog panel when opening and closing dialogs; do not treat them as general language keywords.
- The C++ panel class is `CGameDialogPanel`; do not invent a separate `CDialogPanel` type.

## Quest integrity

When adding or changing quests:

1. Ensure every quest id in `res/maps/<map>/config.json` matches the class name in that map’s `script.py`.
2. Keep quest-log descriptions brief, preferably one sentence.
3. Build the game and run it with `python3 play.py` when gameplay behavior changed.
4. Accept each changed quest and open the quest log with `j`.
5. Verify active quests appear correctly.
6. Progress objectives and verify completed quests move to the completed section.
7. Run the required validation workflow.

## Exposing C++ types to Python

This project uses pybind11 for the `_game` module.

When exposing a new C++ class to Python:

1. Add or update a `CWrapper<YourClass>` specialization in `src/core/CWrapper.h` if Python subclasses need to override virtual behavior.
2. Add the pybind11 binding in `src/core/CModule.cpp` inside `PYBIND11_MODULE(_game, m)`.
3. Use `py::class_<...>` with the correct base class, wrapper class when needed, and `std::shared_ptr<...>`.
4. For gameplay object types, add the `FN_TYPE` row (or `FN_WRAPPED` when a `CWrapper<T>` trampoline exists) to `src/plugin/CGameplayTypeTable.h` — it feeds native registration, pybind metadata, and the Python downcast dispatch from one list. Core/GUI framework types register in the owning `C*TypeRegistration.cpp` unit with `CTypes::register_type<...>()`.
5. Add or update Python plugin classes under `res/plugins/` when the new type is intended to be instantiated from scripts or config.
6. Build `_game`, run C++ tests, and run `python3 test.py`.

Do not use Boost.Python patterns for new bindings.

## Map NPC vs player template rule

For all maps under `res/maps/*`, do not place player-class templates as normal map actors in `config.json`.

Player-class refs include:

- `Sorcerer`
- `Warrior`
- `Assasin`

Keep the existing `Assasin` spelling where it is part of a resource id.

Using player-class refs as regular actors creates extra player objects at load time and can produce debug output such as `Loaded object: CPlayer:<objectName>(...)`.

For NPCs and scripted actors, use non-player creature templates based on `CCreature` and keep `npc: true` or controller settings as needed.

To control the real player’s starting position, set map entry coordinates in each map’s `map.json` top-level `properties`:

- `x`
- `y`
- `z`

Do not add a separate player object for the spawn point.

## Debugging and profiling

Use `valgrind` for native memory diagnostics and runtime error investigation.

Use callgrind for profiling hot paths or performance regressions:

```sh
valgrind --tool=callgrind <command>
```

Prefer small, reproducible failing cases. Add tests for regressions when practical.

## CI expectations

The main build workflow validates Linux and Windows builds, runs C++ tests, runs native performance guards, runs Python
tests, runs coverage on Linux, packages artifacts, and uploads build artifacts.

Before proposing a change, run focused local checks that exercise the changed behavior. Let GitHub Actions supply
compilation, full-suite, and coverage evidence for PR delivery whenever the workflow covers the required checks.

## Commits and pull requests

After finishing a change, always complete the repository delivery workflow:

1. Review the final diff and ensure it contains only intended files.
2. Run focused local validation, then use CI polling for heavy compilation, full-suite tests, and coverage when the PR
   workflow covers the required evidence. Run local heavy validation only for CI gaps, necessary focused reproduction, or
   unavailable polling.
3. Commit the change with a clear, specific commit message.
4. Push the branch to the remote.
5. Open a pull request targeting `main`.
6. Wait for the selected GitHub Actions evidence to succeed before merging when CI is replacing local heavy
   validation.
7. After required evidence is present, resolve the auto-merge authorization state per the pull request merge policy
   (allowed / user-authorized / disallowed / unknown). Run `gh pr merge <PR_NUMBER> --auto --squash` only when the
   state is allowed or user-authorized; when it is disallowed or unknown, leave the PR open and report the blocker
   instead of auto-merging. Replace `<PR_NUMBER>` with the pull request just opened.
8. If GitHub queues auto-merge and the PR has already merged, stop waiting on its Actions run, fetch `origin/main`,
   and continue from the merged commit.

Keep one logical change per commit where practical. Do not bundle unrelated cleanup with feature or bug-fix work. Do not bypass failing required checks or unresolved merge conflicts unless the user explicitly instructs that specific bypass. If pushing, opening, merging, or enabling auto-merge is blocked by missing remotes, authentication, permissions, unavailable checks, merge conflicts, or platform failures, report the exact blocker and leave the branch and pull request intact.

When working on a GitHub issue, close it only after the fixing pull request has been merged.

Before finishing, summarize:

- files changed;
- tests and coverage commands run;
- commands that failed or could not be run;
- any risky assumptions;
- any follow-up work that is genuinely required.


## Copyright

When modifying source files with copyright headers, preserve the existing owner text and update the year or year range to include the current calendar year.

Do not change license text unless the task explicitly requires it.
