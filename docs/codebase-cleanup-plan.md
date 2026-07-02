# Codebase Cleanup Plan

Date: 2026-07-02. Prepared from a four-track survey of the repository (C++ engine,
Python layer, process/tooling, repository hygiene). Every finding below carries
file evidence, an effort estimate (S/M/L) and a risk rating (low/med/high).

## Purpose and ground rules

This plan inventories cleanup debt and sequences it into phases that respect the
repository's existing constraints:

- **Coverage gate:** any change touching `test.py`, `tests/unit/**`, `src/core/**`,
  `src/handler/**`, `src/object/**`, `src/gui/**` (per
  `scripts/ci_change_classifier.py:14`), or `native_plugins/**` must pass the 90%
  eligible-line gate (`scripts/run_coverage.sh:6`, `MIN_COVERAGE=90`).
- **Narrow PRs, squash-merge only, never push to `main`** (AGENTS.md). Each item
  below is scoped to be an independent PR.
- **Queue integration:** implementation work is dispatched through
  `planning/fall_of_nouraajd_issue_proposals.xlsx` via `scripts/issue_queue.py`.
  Existing epics run 01–07; new cleanup items should be proposed as **EPIC_08+**
  using `scripts/issue_queue.py propose`. Items that overlap epics already in the
  queue are flagged **[queued: EPIC_xx]** and must NOT be re-proposed.
- **Validation:** every item runs the standard workflow from CLAUDE.md
  (content validation, `_game` + unit + performance builds, ctest, `python3
  test.py`), plus `./scripts/run_coverage.sh` when the coverage paths are touched.

## Phase 0 — Quick wins (S effort, low risk, no engine behavior change)

Deletions and hygiene fixes that shrink the repo and remove dead weight. Each is
an independent one-commit PR.

| # | Item | Evidence | Notes |
|---|------|----------|-------|
| 0.1 | Delete `cmake/cotire.cmake` (175 KB) | Zero references outside the file itself; no `include(cotire)` anywhere | Largest single dead file in the repo |
| 0.2 | Delete redundant CI workflow `.github/workflows/export-planning-workbook.yml` | Its single artifact (`..._github_issues_implementation_workbook_migrated.xlsx`) is a subset of `export-planning-workbooks.yml`'s `planning/*.xlsx` glob; both trigger on every PR | Halves duplicate artifact uploads per PR |
| 0.3 | Delete 4 orphaned screenshots (~3.5 MB): `screenshots/vhulmarn_map.png`, `fight.png`, `kadath_map.png`, `maze.png` | No references in README.md or docs/ | Keep the 6 README-referenced files |
| 0.4 | Remove `res/images/paper.png` (1.8 MB) | Zero references in `res/config`, `res/maps`, `res/plugins`, `src`, `res/game.py` (assets resolve by base name; the base name `paper` has no hits) | Confirm with a full-tree grep at PR time |
| 0.5 | Untrack `.idea/workspace.xml` | `.idea/` is in `.gitignore` yet 8 `.idea/` files are tracked; `workspace.xml` is per-developer IDE state | Keep `runConfigurations/*.xml` if they are intentionally shared |
| 0.6 | Extend `.gitignore`: `__pycache__/`, `.coverage`, `coverage/`, `htmlcov/`, `build/`, playtest-trace output (`*.jsonl` traces) | Current file only covers `*.pyc`/`*.pyo` and `/cmake-build-*`; `run_coverage.sh` writes `coverage/`, `CPlaytestTrace` writes trace files | Nothing offending is tracked today — this is prevention |
| 0.7 | Delete dead C++ blocks: commented-out `CMap::applyEffects()` (`src/core/CMap.cpp:532-542`), stray commented lines (`src/object/CBuilding.cpp:23`, `src/handler/CObjectHandler.cpp:97`) | Verified commented-out code, no `#if 0` regions exist elsewhere | Touches `src/core|object|handler` → coverage run required |
| 0.8 | Sweep stale TODO comments: 5× `// TODO: cache` in `src/gui/panel/CListView.cpp` (432, 436, 470, 478, 541) — file itself notes "no performance impact" | Delete the TODOs (not the code) or convert to queue proposals | Pair with 0.7 in one "dead-comment sweep" PR |

## Phase 1 — Consistency, docs drift, and CI correctness (S–M effort)

Fixes where documentation, CI, or conventions have drifted from reality. Highest
risk-reduction per line changed.

### 1.1 CI silently skips most of `tests/` (S effort, HIGH value)

Verified: CI hand-lists only 7 of 16 `tests/test_*.py` modules
(`build.yml:373-375, 652-654` runs `test_content_validator`,
`test_creature_stat_scale_baseline`, `test_creature_equipment_inventory_baseline`;
`build.yml:48,55,56` runs `test_workflow_observations`, `test_issue_queue`,
`test_prompt_inventory`; `workbook-queues.yml:26` runs `test_workbook_queue`).
The other **9 modules are never executed by CI** — `test_ci_change_classifier`,
`test_claim_once_helper`, `test_controller_resource_audit`, `test_coverage_report`,
`test_object_comparison_audit`, `test_player_class_options`, `test_poll_pr_checks`,
`test_pr_review_audit`, `test_slot_context_ownership` — and `test.py` does not
discover them either. **Fix:** replace the hand-list with
`python3 -m unittest discover -s tests -t .` (or a glob-derived list) so new
modules can't silently drop out. Risk: med (some of the 9 may currently fail —
run them first and fix or quarantine explicitly).

### 1.2 Docs drift (S effort, low risk)

- Add `src/gui/**` to the coverage-trigger list in CLAUDE.md (§ Test & validate)
  and README.md:154 — `ci_change_classifier.py:14` already treats it as
  coverage-relevant.
- Add a header note to `TODO_WORKLOG.md` stating the current gate is 90%; its
  batch entries cite 80% (`:14`, `:76`) and 95% (`:533`) from historical gates.
  Do not rewrite the historical entries.
- Align `release.yml` with the rest of CI: it uses Python 3.11 + ubuntu-22.04
  while every other workflow uses Python 3.12 + ubuntu-24.04. Risk: med
  (release path — verify the release artifact still builds).
- Add a path filter to `workbook-queues.yml` so it runs only when
  `planning/**`, `scripts/issue_queue.py`, or `scripts/workbook_queue.py` change.

### 1.3 TODO tracking consolidation (M effort, low risk)

Three parallel tracking systems exist: `todo.txt` (~15 open free-text items),
`TODO_WORKLOG.md` (28 batches, ~24 resolved), and the xlsx queue. Several
`todo.txt` lines are already queued epics. **Fix:**

- For each open `todo.txt` item, either mark it **[queued: EPIC_xx]** or propose
  it via `issue_queue.py propose`; then delete `todo.txt`.
  Already-queued mappings: static providers → EPIC_02_STORY_01; return-to-oldMap →
  EPIC_02_STORY_03; primitive unfolding → EPIC_03_STORY_04; panel resizing →
  EPIC_05_STORY_02; `SDL_RenderCopy` encapsulation → EPIC_05_STORY_03;
  buff/selfTarget → EPIC_06_STORY_01; class/race split → EPIC_06_STORY_02.
- Move `TODO_WORKLOG.md` to `docs/todo-worklog.md` as a frozen archive (no code
  references either file; move-cost verified S).

### 1.4 Python bootstrap unification (M effort, med risk)

The build-dir/resource-root bootstrap (probe `cmake-build-release`/`-debug`,
insert config subdir, `os.chdir`, `sys.path` insert) is reimplemented four times:
`play.py:27-66`, `mcp.py:347-352` + `2725-2737`, `test.py:85-109`,
`scripts/generate_screenshots.py:107-109` — with two env-var conventions
(`GAME_BUILD_DIR` vs `GAME_BUILD_CONFIG`) split across them. **Fix:** extract one
shared `bootstrap.py` helper at repo root (the root is already the installed
runtime set per `CMakeLists.txt:505` — add the new file to that install list),
then point all four call sites at it. Also centralize the
`set_logger_sink("disabled")` call, which is currently made with different arity
in `res/game.py:11` and `test.py:114`.

### 1.5 Small Python cleanups (S effort, low risk)

- Hoist the 7 inline `class FakeEvent:` definitions in `test.py` (5484, 5504,
  5966, 6032, 14829, 14877, 15037) into one shared test double.
- Collapse the `quest_state.py` alias pairs `_set_state`/`set_state` (:65-66) and
  `_sync_legacy_flags`/`sync_legacy_flags` (:93-94) to one naming convention and
  update `res/maps/nouraajd/script.py` call sites.
- Resolve the two in-code Python TODOs: `res/maps/siege/script.py:141`,
  `res/maps/test/script.py:21` (fix or convert to queue proposals).
- ~~Replace hardcoded `/tmp/...` fixture paths in
  `tests/test_controller_resource_audit.py` with `tempfile`~~ — verified
  no-change-needed: those paths are inert string fixtures inside parsed
  porcelain text, never created on disk.

## Phase 2 — Structural refactors (M–L effort, coverage-gated)

The engine-level debt. Each story here should be proposed as an EPIC_08+ story
with substories sized to one PR each.

### 2.1 Unify type registration (L effort, HIGH value — top structural item)

The type hierarchy is maintained in **three parallel hand-edited lists**:

1. `src/core/CModule.cpp:329-384` — `CTypes::register_type_metadata<...>` for the
   Python binding;
2. `src/plugin/NativePlugin.cpp:57-174` — `register_type<...>` for the plugin ABI;
3. `scripts/type_registration_exclusions.json` — a 15-class allowlist of V_META
   types deliberately not content-registered.

Plus an 11-branch manual downcast chain in `CModule.cpp:288-323`
(`cast_registered_python_object`). A new V_META type can be registered in one
list but not the other, or in neither, and only fail at runtime — exactly the
audit `todo.txt:1` asks for. **Fix:** one shared type-list (X-macro table or
generated source) that drives both registration paths and the downcast dispatch,
making the exclusion audit mechanical. Do this before adding more object types.

### 2.2 Finish the `CGameContext` provider migration [queued: EPIC_02_STORY_01]

25 call sites still use `CResourcesProvider::getInstance()` /
`CConfigurationProvider::getInstance()` (singletons defined at
`src/core/CProvider.cpp:321, 350`): heavy in `src/core/CLoader.cpp` (310, 696,
703, 712, 720, 840, 993, 1309), plus `src/gui/CTextureCache.cpp:103`,
`src/gui/CTextManager.cpp:71`, `src/core/CProvider.cpp:316`. `CLoader.cpp:1111`
already shows the target pattern. This is exactly the remaining
EPIC_02_STORY_01 substories (03–05, NOT_STARTED) — **work the existing queue
items; do not re-propose.**

### 2.3 Split the god-files (M–L effort each)

Ranked by TODO density and mixed responsibilities:

- `src/core/CLoader.cpp` (1500 lines) — save/load, map resolution, backup,
  config scan, player/trigger wiring in one unit (misplaced-responsibility TODOs
  at :1051, :1209).
- `src/core/CModule.cpp` (1260 lines) — pybind setup, type metadata, downcast
  dispatch, RNG bridge, logging config. Shrinks substantially if 2.1 lands first.
- `src/object/CCreature.cpp` (1067 lines) — 8 TODOs about inventory/equip/level/
  action logic; largest concentration of "rethink" comments.
- `native_plugins/native_gameplay_*.cpp` — 7 near-identical 22-line boilerplate
  files plus `native_gameplay.cpp` re-exporting all 7; collapse behind a macro.
  Also extract the repeated `register_*` scaffold in `NativePlugin.cpp:57-174`
  into a variadic helper (S, pairs naturally with 2.1).

### 2.4 Split the Python monoliths (L effort)

- `test.py` is **21,567 lines**; `GameTest` alone is ~11,800 lines / 531 methods
  (:4970-16805). Split into a package by concern: runner/sharding infra,
  `McpScenarioHarness` (:3345-4970, ~1,625 lines), gameplay walkthroughs, quest
  logic, crafting, UI/xvfb. Preserve the `python3 test.py` entry point and
  `--suite` semantics; migrate incrementally (one extracted module per PR) to
  keep the coverage gate green.
- While splitting, merge the duplicate suites: `CoverageReportTest` exists in
  both `test.py:19164` and `tests/test_coverage_report.py:10`;
  player-class-options and `claim_once` behavior are each covered in both
  `test.py` and `tests/`. Pick one home per behavior (prefer `tests/`, which CI
  will fully run after 1.1).
- `mcp.py` — `EngineMcpServer` is ~2,050 of 2,773 lines (:273-2324); split
  tool dispatch, resource-root resolution, and protocol handling. Audit the 14
  broad `except Exception:` handlers while touching each region.
- `res/maps/nouraajd/script.py` (1,057 lines) — extract the quest-state machine
  from dialog callbacks; cache the `QuestSystem` accessor instead of
  constructing a fresh one at each of 40+ call sites (:154-155).

### 2.5 Error-handling and logging policy (M effort, med risk)

The engine logs 127× `vstd::logger::warn` vs 19× `error`, with 44 `throw` sites
and no runtime asserts — many warns likely swallow conditions that should fail
loudly. The Python layer uses three logging idioms (stdlib `logging` in
`mcp.py`, native `logger(...)` in `res/game.py`/map scripts, `print(...,
file=sys.stderr)` in `test.py:21540-21560`). **Fix:** write a one-page policy in
docs/ (when to throw vs error vs warn; one Python idiom per layer), then apply
it opportunistically in PRs that already touch a file. No big-bang sweep.

## Phase 3 — Larger / deferred (decide before scheduling)

Items with real payoff but nontrivial risk or workflow impact. Each needs an
explicit go/no-go decision, not a default yes.

| # | Item | Effort/Risk | Recommendation |
|---|------|-------------|----------------|
| 3.1 | Migrate the mutable queue workbook off binary xlsx. `issue_queue.py` (2,383 lines of hand-rolled xlsx I/O) rewrites `planning/fall_of_nouraajd_issue_proposals.xlsx` (100 KB) on every claim/heartbeat — an unmergeable, undiffable binary churned in git history. The `workflow_observations` ledger already demonstrates the target pattern (one immutable JSON file per record). | L / high | Do it when queue churn next causes a merge conflict or repo-size complaint; design first (text format keeping `issue_queue.py`'s CLI surface) |
| 3.2 | De-vendor simdjson: `third_party/simdjson` is a 10 MB committed amalgamation (`simdjson.h` 7.7 MB + `simdjson.cpp` 2.7 MB), built at `CMakeLists.txt:68` — the sole source (not in `vcpkg.json`, no `find_package`). Convert to submodule or `FetchContent`. | M / med | Worth doing; verify offline/CI build reproducibility and pin the current version |
| 3.3 | Asset weight: `res/images` is 106 MB of high-resolution source PNGs (sampled: 1024×1536, 1440×900; 1.6–2.4 MB each); no duplicates found (md5-verified). Add a lossless/near-lossless recompression pass (e.g. `oxipng`/`pngquant`) and consider downscaling to game-native resolution. | M / med | Recompress losslessly first (safe); downscaling needs visual review |
| 3.4 | Git history / LFS: pack is 129 MiB, roughly the current binary footprint — history is not yet bloated. `screenshots/nouraajd-walkthrough.mp4` (8.2 MB) is the main churn-prone media file. | L / high | **Defer.** Revisit only if clone size becomes a real problem; a history rewrite forces coordinated force-pushes |
| 3.5 | Consolidate the queue-controller doc/prompt surface: AGENTS.md (765 lines) overlaps `docs/codex-agent-queue.md` (32 KB), `docs/multi-workbook-queue.md`, `prompts/codex-queue-controller.md` (41 KB) and its multi-workbook variant — the same workflow described in 3+ places. Also extract the copy-pasted `subprocess` gh/git plumbing in `poll_pr_checks.py`, `controller_resource_audit.py`, `workflow_observations.py`, `pr_review_audit.py` into a shared `scripts/_gh.py`. | L / med | Fold multi-workbook variants into base docs first (S); note `tests/test_prompt_inventory.py` pins the prompt files — update it in the same PR |
| 3.6 | Root-layout reorg (move `game_simulation.py`, `quest_state.py`, `prompts/`): all are path-coupled — `CMakeLists.txt:490,505` install rules, `mcp.py:24`, `res/game.py:4-9`, and multiple scripts/tests embed the paths. | M / med | **Defer** — cost exceeds benefit; revisit only if 1.4's `bootstrap.py` makes a `tools/` package natural |

## Explicitly out of scope

- Anything already queued under EPIC_01–07 (fight outcomes, movement atomicity,
  serialization primitives, map-local assets, panel resize, RenderCopy,
  targeting, class/race split, creature rewards). This plan adds no duplicates.
- Submodule (`vstd`, `random-dungeon-generator`) changes.
- Gameplay/content changes — this is cleanup only.

## Implementation status (2026-07-02)

Implemented on this branch: all of Phase 0 (0.1–0.8), 1.1 (linux-fast now runs
`unittest discover` over `tests/` — 478 tests including the previously-unrun
`tests/regression/` and `tests/security/` suites; `__init__.py` files added to
make discovery work; Windows jobs keep their three content-validation smoke
modules), 1.2 (coverage-path docs, worklog gate note, `release.yml` version
parity, `workbook-queues.yml` path filter), 1.3 (`todo.txt` annotated with
queue mappings, worklog archived to `docs/todo-worklog.md`), and the safe
subset of 1.5 (`quest_state.py` alias collapse; the `tempfile` item was a
false positive — see above).

Not implemented here, still open: 1.4 (bootstrap unification) and the rest of
1.5 (`test.py` FakeEvent hoist, map-script TODOs) — these need a locally
runnable engine to validate, which this environment cannot build (submodule
access unavailable); route them through the queue with the Phase 2 epics.

## Suggested sequencing

1. **Week 1 (quick wins):** Phase 0 items 0.1–0.8 as ~5 small PRs, plus 1.1
   (CI test discovery — do this first; it changes the safety net everything else
   relies on) and 1.2 (docs drift).
2. **Week 2:** 1.3 (TODO consolidation → queue proposals for EPIC_08+),
   1.4 (bootstrap helper), 1.5 (small Python cleanups).
3. **Then, via the queue:** propose Phase 2 as epics — suggested split:
   EPIC_08 "Type registration single source of truth" (2.1 + native-plugin
   boilerplate from 2.3), EPIC_09 "Test-suite restructure" (2.4 test.py split +
   suite dedup), EPIC_10 "Engine god-file decomposition" (2.3), EPIC_11
   "Diagnostics policy" (2.5). Work EPIC_02_STORY_01 (2.2) from the existing
   queue in parallel.
4. **Phase 3:** bring 3.1–3.3 to a go/no-go decision; keep 3.4/3.6 deferred.
