# AGENTS.md

## Scope

These instructions apply to the entire repository unless a more specific `AGENTS.md` exists deeper in the tree.

The default branch is `main`.

Keep changes narrow. Do not modify unrelated files, generated build output, packaged artifacts, dependency lock state, or submodule SHAs unless the task explicitly requires it. Do not merge, rebase, or update from `main` unless asked. If a task requires touching `random-dungeon-generator` or `vstd`, state that clearly and rerun the full validation workflow.

When this file conflicts with the current code, tests, or build scripts, trust the code and update this file as part of the fix.

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

The README’s Ubuntu setup uses Python, pybind11 headers, and nlohmann-json development packages before configuration.

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

## Required validation

For every code change, run this full workflow from the repository root unless the environment makes it impossible:

```sh
cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc)
ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests
python3 test.py
```

Windows Release equivalent:

```bat
cmake --build cmake-build-release --config Release --target _game for_unit_tests
ctest --test-dir cmake-build-release -C Release --output-on-failure -R for_unit_tests
set GAME_BUILD_DIR=cmake-build-release
set GAME_BUILD_CONFIG=Release
python test.py
```

The Python tests require the compiled `_game` module for most runtime paths. Tests that do not need `_game` should still be able to run, so import optional `game`/`_game` modules inside the individual tests that need them.

When validation cannot be run, do not imply that it passed. Report the exact command that was skipped or failed and the reason.

## Coverage

Run coverage when a change touches:

- `test.py`
- `tests/unit/**`
- `scripts/run_coverage.sh`
- coverage tooling
- `src/core/**`
- `src/handler/**`
- `src/object/**`

Coverage command:

```sh
./scripts/run_coverage.sh
```

The scoped line coverage threshold is 90%. Do not finish coverage-relevant work below that threshold without explicitly reporting it.

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

## Code style

General:

- Use four spaces for indentation in C++ and Python.
- Keep lines under 120 characters where practical.
- Keep changes minimal and local to the requested behavior.
- Do not rewrite broad areas only for style.
- Do not add comments that merely restate obvious code.

Python:

- Use `snake_case` for functions, methods, and local variables.
- Use `UPPER_SNAKE_CASE` for global flags and constant-like values.
- Use `CamelCase` for classes.
- Trigger classes decorated with `@trigger` must use `CamelCase` and end with `Trigger`.

C++:

- Use `CamelCase` for class names.
- Existing engine methods exposed to Python may keep their current `CamelCase` names.
- New Python-only methods should use `snake_case`.

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
4. Register the type hierarchy in `src/core/CTypes.cpp` with `CTypes::register_type<...>()`.
5. Register wrapper types in `CTypes.cpp` when wrapped Python-overridable types are involved.
6. Add or update Python plugin classes under `res/plugins/` when the new type is intended to be instantiated from scripts or config.
7. Build `_game`, run C++ tests, and run `python3 test.py`.

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

The main build workflow validates Linux and Windows builds, runs C++ tests, runs Python tests, runs coverage on Linux, packages artifacts, and uploads build artifacts.

Before proposing a change, reproduce the relevant local parts of CI as closely as the environment allows.

## Commits and pull requests

Do not commit unless explicitly asked.

When asked to commit:

- use a clear, specific commit message;
- keep one logical change per commit where practical;
- do not bundle unrelated cleanup with feature or bug-fix work.

Before finishing, summarize:

- files changed;
- tests and coverage commands run;
- commands that failed or could not be run;
- any risky assumptions;
- any follow-up work that is genuinely required.

## Copyright

When modifying source files with copyright headers, preserve the existing owner text and update the year or year range to include the current calendar year.

Do not change license text unless the task explicitly requires it.
