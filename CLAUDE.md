# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`fall-of-nouraajd` is a C++ dark-fantasy 2D game. The C++ engine compiles into a
pybind11 module (`_game`) that Python drives: gameplay content (maps, dialogs,
config, plugins) is authored in JSON + Python under `res/`, and the game itself
is launched from Python (`play.py`). There is no standalone C++ binary for
normal play — the engine is always loaded as a Python extension.

## Build

The `_game` extension must be built before any test that exercises gameplay.

```sh
git submodule update --init --recursive     # pulls vstd + random-dungeon-generator
./configure.sh                              # Ubuntu native deps + submodule init
python3 -m pip install --upgrade -r requirements-dev.txt
cmake --build cmake-build-release --target _game -j$(nproc)
```

The CMake project is configured by `./configure.sh` (Linux) / `configure.bat`
(Windows, vcpkg). Native deps (SDL2/SDL2_image/SDL2_ttf, Python3, pybind11,
simdjson) come from the OS on Linux and vcpkg on Windows; `requirements-dev.txt`
is the pinned source only for pip-managed Python test tools.

Key CMake targets (see `CMakeLists.txt`):
- `game_core_objects` (OBJECT) → `game_core` (SHARED) → `_game` (pybind module). The
  engine is compiled once as objects, linked into a shared lib, then wrapped by pybind.
- `for_unit_tests` — aggregate of the C++ unit-test executables (run via ctest).
- `performance_guard_tests` — perf-labeled C++ tests.
- Native gameplay plugins under `native_plugins/` build as separate `MODULE` libraries.

Windows builds add `--config Release` / `-C Release` and require
`GAME_BUILD_DIR=cmake-build-release` + `GAME_BUILD_CONFIG=Release` in the env
before running Python.

## Test & validate

Running tests is mandatory after any code change. Full workflow from the repo root:

```sh
python3 scripts/validate_content.py --repo-root .          # JSON/dialog/quest content validation (no _game needed)
python3 -m unittest tests.test_content_validator
cmake --build cmake-build-release --target _game for_unit_tests performance_guard_tests -j$(nproc)
ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests
ctest --test-dir cmake-build-release --output-on-failure --verbose -L performance
python3 test.py                                            # main Python/gameplay suite
```

- **Single Python test:** `python3 test.py GameTest.test_map_walkthrough_nouraajd`
  (standard `unittest` name filtering).
- **Named suites:** `python3 test.py --suite fast|gameplay|ui|coverage-safe|full`.
  UI/xvfb tests parallelize with `GAME_XVFB_JOBS=4`.
- **Content validation runs first in CI** and needs only the Python stdlib (no
  `_game`), so broken map/config/dialog/quest refs fail fast. It validates each
  map's quest state machine against the keys declared in its `script.py`.
- **Coverage:** run `./scripts/run_coverage.sh` when a change touches `test.py`,
  `tests/unit/**`, `src/core/**`, `src/handler/**`, `src/object/**`, `src/gui/**`,
  `native_plugins/**`, or coverage tooling (the authoritative path list is
  `COVERAGE_PATH_PATTERNS` in `scripts/ci_change_classifier.py`). It enforces a
  90% eligible-line gate.
- **Playtest trace** (debugging gameplay flows):
  `GAME_PLAYTEST_TRACE=1 GAME_PLAYTEST_TRACE_FILE=trace.jsonl python3 test.py GameTest.test_map_walkthrough_nouraajd`.

C++ formatting uses `.clang-format` (LLVM base, 4-space indent, 120 col, no include sorting).

## Architecture

### Engine layers (`src/`)
- **`src/core/`** — game loop, loader, serialization, plugin host, RNG, scene
  management. `CGame` is the root context; `CLoader` reads JSON content;
  `CProvider`/`CResource*` abstract resource loading (config/map/plugin/save).
  `CModuleEntry.cpp` / `CModule.cpp` is the pybind entry point that builds the
  `_game` module.
- **`src/object/`** — gameplay entities: `CGameObject` (base), `CCreature`,
  `CPlayer`, `CItem`, `CQuest`, `CDialog`, `CTile`, `CBuilding`, `CEffect`,
  `CInteraction`, `CTrigger`, `CMarket`, `CEvent`, `CCreatureClass`/`CCreatureRace`.
- **`src/handler/`** — subsystem controllers held by the game: `CFightHandler`,
  `CQuestHandler`, `CGuiHandler`, `CEventHandler`, `CObjectHandler`,
  `CScriptHandler`, `CRngHandler`, `CTooltipHandler`.
- **`src/gui/`** — SDL rendering, layout, animation, texture/text caching, and
  panel/widget objects under `src/gui/object/`.
- **`src/plugin/`** — the native-plugin ABI (`CPluginAbi.h`, `NativePlugin`) used
  to load `native_plugins/*` MODULE libs at runtime.

### Reflection & type registration
The engine uses a reflection macro from the **`vstd`** submodule: `V_META(Class,
Base, ...properties)` with `V_PROPERTY(...)` declarations (see any header in
`src/object/` or `src/gui/object/`). This drives JSON (de)serialization —
objects are constructed by type name from JSON and their properties round-trip
through the meta system. Each source area registers its types via
`register*Types()` (declared in `src/core/CTypeRegistration.h`, implemented in the
`C*TypeRegistration.cpp` files). When adding a new engine object type, wire it
into the matching registration file or it won't be constructible from content.

### Content pipeline (`res/`)
- **`res/config/*.json`** — global definitions (items, weapons, armors, monsters,
  tiles, effects, potions, crafting, buildings, panels, slots, graphics).
- **`res/maps/<name>/`** — a map is a directory of `map.json` (Tiled-style layers),
  one or more `dialog*.json`, a per-map `config.json`, and a `script.py` that
  drives quest state (declares `QUEST_KEYS`/`QUEST_DEFAULTS`, uses
  `set_state`/`state_in`/`get_state`). Maps: `nouraajd`, `ritual`, `siege`,
  `multilevel`, `ninemarches`, `hearthfall`, `gravemoor`, `usurpergate`,
  `sunderedmarch`, `kadath`, `vhulmarn`, `test`.
- **`res/plugins/*.py`** — Python gameplay plugins (crafting, interactions,
  effects, potions, tiles, objects). Every `.py` in the directory is
  auto-discovered by `CPluginLoader`; `res/plugins/manifest.json` declares
  native/dynamic plugin entries and optional per-map plugin lists.
- **`res/game.py`** — the Python-side facade over `_game`; wraps native trace
  helpers and quest-state integration (`quest_state.py`).
- Content schemas are documented in `docs/content.md`; the authoritative checker
  is `scripts/validate_content.py`.

### Native vs. Python plugins
Gameplay behavior exists in two forms: C++ in `native_plugins/` (registered
through the `NativePluginHostV1` ABI, `*_load_v1` entry points) and Python in
`res/plugins/`. Both extend the same object/interaction/effect surface.

## Entry points & tooling

- **`play.py`** — launches the game (start menu: NEW / LOAD / RANDOM). Locates the
  build dir (`cmake-build-release` or `cmake-build-debug`) and resource root
  automatically.
- **`mcp.py`** — HTTP (default `127.0.0.1:8765`) or stdio MCP server exposing a
  unified `engine` surface over `game` + `_game` for headless inspection and
  automated walkthroughs (`engine_list`, `engine_call`, `engine_handle_call`,
  `map_design_brief`). `python3 mcp.py --build` builds the extension first;
  `--stdio --repo-root . --build-dir cmake-build-release` for stdio transport.
- **`scripts/generate_walkthrough_video.py`** — drives a headless GUI session
  through an entire `res/campaigns/` manifest (default `fallOfNouraajd`:
  nouraajd → ritual → siege), following the async map transitions between
  chapters, and encodes to MP4 with title cards (auto-wraps in `xvfb-run` on
  Linux). `--campaign <id>` picks another campaign; `--single-map` renders one
  map's storyboard.
- Tests run headless via `SDL_VIDEODRIVER=dummy` (set by `test.py`); UI tests use xvfb.

## Response conventions

- Prefix every reply/message with a timestamp in the **Europe/Warsaw** timezone
  (e.g. `[2026-07-01 14:32 Europe/Warsaw]`).

## Repository conventions

- **`AGENTS.md` is the authoritative process doc** for pull-request, merge, and the
  Codex "queue controller" workflow (workbook at
  `planning/fall_of_nouraajd_issue_proposals.xlsx`, scripts under `scripts/` like
  `issue_queue.py`, `poll_pr_checks.py`, `pr_review_audit.py`,
  `controller_resource_audit.py`, `workflow_observations.py`). The default branch is
  `main`; never push directly to it; squash-merge only. Consult AGENTS.md before any
  PR/merge/queue action.
- Keep changes narrow: do not modify unrelated files, build output, dependency
  locks, or submodule SHAs (`vstd`, `random-dungeon-generator`) unless the task
  requires it — and if it does, say so and rerun the full validation workflow.
- When this file conflicts with the code, tests, or build scripts, trust the code
  and update this file as part of the fix.
