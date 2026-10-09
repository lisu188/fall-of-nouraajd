# Testing

## Repository prep
Run from the repository root after a fresh checkout:

```bash
git submodule update --init --recursive
./configure.sh
```

`requirements-dev.txt` is the source of truth for pip-managed developer and test Python packages used by CI, such as
Pillow and Black. Native build dependencies, including pybind11 headers and CMake config files, still come from
`pybind11-dev` on Linux and vcpkg on Windows. Run the pip command in the same Python environment that will run
`test.py`.

```bash
python -m pip install --upgrade -r requirements-dev.txt
```

## Normal test workflow
Run from the repository root:

```bash
python3 scripts/validate_content.py --repo-root .
python3 -m unittest tests.test_content_validator
cmake --build cmake-build-release --target _game for_unit_tests performance_guard_tests -j$(nproc)
ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests
ctest --test-dir cmake-build-release --output-on-failure --verbose -L performance
python3 test.py
```

The content JSON validator and its focused fixture tests use only the Python
standard library and do not require the compiled `_game` module. They are run
early in CI before the native build so broken map/config/dialog refs fail before
expensive gameplay tests.

### Quest-state-transition validation
Content validation also checks each map's quest state machine. The check is wired
into the standard `scripts/validate_content.py` path: it lives in
`ContentValidator._validate_quest_state_transitions(context)`, which
`ContentValidator._validate_map_context(context)` invokes after that map's config
JSON, dialog JSON, `map.json`, and `script.py` are loaded and after the other
per-map checks run. Because `_validate_map_context` is called from
`ContentValidator.validate()` (the entry point behind `validate_repo()` and the
`scripts/validate_content.py` CLI), the quest check runs on every normal
validation, not as a later runtime-only test, and its findings are reported as
ordinary `ValidationIssue` errors that fail the run.

For each quest key a map script declares (via `QUEST_KEYS`, `QUEST_DEFAULTS`, and
`set_state`/`state_in`/`get_state` usage parsed by `ScriptAnalyzer` — the legacy
`_set_state` spelling is still recognized), the check
reports: defaults, transition writes, or state reads that reference an undeclared
quest key (missing from `QUEST_KEYS`), and terminal completion states that are
unreachable because they are neither the quest default nor any transition target.
Run it the same way as the rest of content validation:

```bash
python3 scripts/validate_content.py --repo-root .
python3 -m unittest tests.test_content_validator
```

`tests/test_content_validator.py` covers the quest-transition rules through the
end-to-end `validate_repo()` run, including
`test_given_bad_quest_transition_when_running_standard_validation_path_then_reported_as_error`,
which pins that the quest validator runs inside the standard
`ContentValidator.validate()` path rather than only via a direct helper call.

### Quest journal integrity

Map-local quest classes use `@mapQuest("mapId")` from `game`. A shared class may instead provide a source-map
resolver, as the Castle mission class does with its existing scenario id. The decorator keeps live source-map
gameplay authoritative and stores journal text on the quest object that travels with the player. Completed
history is fixed; active off-map quests use their last captured text and cannot complete from destination flags.

`CQuest.captureJournal(completed)` records text without granting rewards. `CPlayer.captureQuestJournal()` passes
active/completed collection membership to each callback. The engine captures after completion, before loading a
destination, and before serialization. The additive `questJournal*` properties use version 1 without changing
the save envelope. Older saves retain completion status and use neutral unavailable-detail text when the source
outcome cannot be recovered; existing Victor and Castle player outcome properties remain usable.

The no-extension regression matrix covers all 27 configured quests and checks empty captured text, source reloads,
failed captures, destination-state isolation, and property round trips:

```bash
python3 -m unittest tests.test_quest_journal tests.test_nouraajd_quest_journal
```

Native completion regressions and the bounded journal-capture guard run in the normal native/coverage workflow.
The gameplay suite includes real save/load and movement-based stdio MCP journal checks, and the UI suite checks
the `j` shortcut and rendered active/completed journal history under Xvfb.

For Windows Visual Studio Release builds, use the same target and CTest label with the active configuration:

```bat
python scripts/validate_content.py --repo-root .
python -m unittest tests.test_content_validator
cmake --build cmake-build-release --config Release --target _game for_unit_tests performance_guard_tests
ctest --test-dir cmake-build-release -C Release --output-on-failure -R for_unit_tests
ctest --test-dir cmake-build-release -C Release --output-on-failure --verbose -L performance
set GAME_BUILD_DIR=cmake-build-release
set GAME_BUILD_CONFIG=Release
python test.py
```

The CI Windows job uses a single-config Ninja Release build, so its `ctest` commands omit `-C Release`.

## Python test suites
`python3 test.py` remains the full Python regression suite. For faster feedback, the runner also accepts named suites:

```bash
python3 test.py --suite fast
python3 test.py --suite gameplay
python3 test.py --suite gameplay-core
python3 test.py --suite mcp-branches
GAME_XVFB_JOBS=4 python3 test.py --suite ui
python3 test.py --suite coverage-safe
python3 test.py --suite full
```

- `fast` runs runner, bootstrap, manifest, coverage-report, and lightweight MCP protocol checks that do not require the
  compiled `_game` module.
- `gameplay` runs deterministic engine, map, save/load, quest, combat, and MCP gameplay checks after `_game` is built.
- `mcp-branches` runs the explicit authored branch/class matrix through a fresh stdio MCP process per case.
- `gameplay-core` runs the other gameplay checks. CI runs it with the native build, then runs `mcp-branches` in
  separate Linux and Windows shards against that same workflow head's binary and copied resources.
  Windows stages the already built runtime through `cmake --install`, which also resolves and copies its dependent
  DLLs, before archiving the flat installed package. Shards verify and extract that package without compiling again.
- `ui` runs the Xvfb parent test and GUI layout manifest checks; it is intended for Linux/Unix environments with
  `xvfb-run` and `xauth`.
- `coverage-safe` is the Python suite used by `./scripts/run_coverage.sh`; it keeps deterministic coverage drivers and
  GUI coverage, but omits duplicate subprocess walkthrough checks that are already covered by the normal gameplay CI
  suite.
- `full` is the default full-suite behavior and is equivalent to omitting `--suite`.

Use `--jobs <n>` with any suite to enable the existing sharded runner, for example
`python3 test.py --suite gameplay --jobs "$(nproc)"`.

### Exhaustive authored MCP branches

The source catalog is `tests/gameplay_branch_catalog.py`; the route modules declare named obligations and their
source callbacks. A catalog entry is a test obligation. Only a passing native route receipt establishes played
coverage. Structural audits account for dialog actions/conditions, registered callbacks, campaign outcomes, and
explicit defensive contracts. Unreachable authored content remains a reported obligation, rather than becoming a
passing fixture-only route.

The current catalog declares 774 branches across 83 cases and 395 case/class executions, with 34 unresolved
gameplay obligations. Thirteen are disconnected authored Castle defenders. Another obligation is
`usurpergate.throne.premature`, required in all four Warden campaign/standalone routes for all five classes:
enter the actual throne while the Usurper remains alive and verify no reward or quest/campaign progress.
The source callback test verifies that refusal, but no real route witness has been established. A permissive
source movement model omitting housecarls finds a path only when the player commits before the pursuing boss;
native map turns apply actors in unordered-container order. This evidence does not establish an executable
route or justify defensive credit. These 14 obligations remain mandatory and receive no played-coverage credit.

Shared callback discovery resolves actual map actor types through global/map configuration references and
Python inheritance, respecting persistent plugin registrations. It also follows authored nested stock and
literal constructor references, including the hunt's installed defeat trigger. The current inventory contains
26 shared callback identities; unused library types add no manufactured gameplay branch. Unknown resource
references or classes fail the audit. Owner-specific WayPoint edge removal remains an explicit destruction
contract, backed by its focused cleanup test.

The shared coverage floor includes 103 named requirements, including 45 applicable recipe-specific outcomes.
A locked outcome applies only to a recipe with an authored unlock flag, and a failure outcome applies only
below 100 percent success chance. The remaining 20 pending shared requirements are recipe outcomes.
Connector publication now has source-ordered creation and later-turn
oracles. Passive cave observers use existing route turns to prove a new matching clone's native placement,
an exact one-monster decrement, and two later exhausted turns; they add no waiting loop and stop after
both outcomes. Two ordinary pre-activation ritual turns also verify all three zero-stock anchors remain
inactive. These are implemented runtime assertions; a source or pure-test pass gives no played credit.
They are attached to real cases for all five classes; a route must produce its own receipt before `finish`
can pass. Missing ingredients cannot stand in for insufficient gold when a recipe requires both, and
conditional recovery cannot stand in for guaranteed potion/scroll use. Crafting code and recipe data are
inside the reviewed source digest. Implemented service assertions remain source/test evidence until native
CI supplies passing route receipts.

All 11 ordinary life/mana consumption obligations now have mandatory route assertions. The native `item_used`
receipt identifies the actual player and item, proves an existing resource deficit, verifies the configured
percentage with its exact cap, and requires that only the used owned identity disappeared while equipment
stayed unchanged. Rejuvenation, NPC consumption, absent records and full-resource uses cannot earn these
branches. Fixed routes obtain finite stock before remaining fights, funded by actual quest gifts, collected
weapons or first-cave loot. Nine Marches consumes at observed postcombat deficits before its normal road
recovery. A final assertion fails if gameplay never produces a qualifying use; implementation does not establish
native acceptance. An expired effect may lower the untouched resource's derived maximum without clamping its
stored value; the potion oracle still requires that resource to remain exactly unchanged and the restored
resource to have a real deficit and receive the exact capped amount.

The timed courtyard escape derives its sole exit from the raw authored wall objects, then checks a six-step
continuation against native passability and current pursuer coordinates. Each decision permits at most 64 distinct
native cell probes, with memoization and bounded rejection diagnostics. Pure pursuit models verify route planning
and the authored 74/75/76-turn boundary; passing native receipts are still required for actual timeout credit.
Earned hunt preparation also checks native object passability before committing a step. An incidental Victor rescue
requires a recent validated actual-player victory against the leader, its original deadline, and the exact payout;
cleanup of other cultists earns no invented combat experience. Nine Marches keeps the original collected retreat
scroll through its first Halda approach and credits only its verified consumption and movement to the map entry.

The missing-wand Siege refusal has its own fresh standalone case for every class. It consumes actual wands
through successful seals, then requires an enabled, unsealed breach at the player's actual coordinates before
checking refusal and unchanged state. A campaign's carried or newly looted wands cannot stand in for that
prerequisite. Nouraajd's portal-scroll and greater-life insufficient-gold routes plan from observed finite loot
quotes and original market identities before any sale, retain the exact ingredients, and require the ordinary
unlock and crafting refusal. Unsatisfiable quotes fail without retrying startup or recreating stock.

```bash
python3 test.py --suite mcp-branches --branch-class Wayfarer
python3 test.py --suite mcp-branches --branch-group ninemarches
python3 scripts/mcp_branch_shards.py matrix
```

Every shared route runs for Warrior, Sorcerer, Assasin, Inquisitor, and Wayfarer. Race service cases use the existing
required race; owner-specific deeds test their own action and other classes' rejection. Starting campaign saves
come from `campaign.start`; only the catalog's documented initial Nine Marches reputation values may differ from
ordinary startup. All slots and preference files have unique task-owned names and are cleaned after each case.

`mcp.py --stdio --test-seed <uint32>` seeds both native random sources before importing the game bootstrap. The
private hook is unavailable through MCP exports. Stable SHA-256 case/class seeds, ordered action journals, bounded
native trace history, failure diagnostics, elapsed time, and branch receipts are written under the selected
`GAME_TEST_OUTPUT_DIR`. Reproduce a failure from process startup with the recorded seed and action sequence;
save checkpoints preserve game state, and do not serialize RNG state. Random sequences are checked within each
platform; Linux and Windows need not produce identical sequences. Generated object names include process-local
identity, so the seed tests establish native random-source repeatability. The recorded case and action sequence
are failure diagnostics; they do not establish identical whole-route execution across fresh processes.
Navigation target actions retain known coordinate triples after temporary MCP coordinate handles are released.

The native driver uses controller targets, adjacent movement, actual map turns, class combat controllers, owned
consumables, finite stock, and real payments/ingredients. It rejects fixture mutations, unexpected defeat,
unauthored relocation, stalled routes, and exhausted action/turn budgets. Adjacent steps use native controller
targets and map turns, and step counters count actual arrivals. Moving NPC approaches follow their current
cells; hostile pursuits retain their committed path until arrival or interruption. The actual native trace writer
must remain healthy before combat receipts are trusted. Validated victories are retained in a bounded cache so
later recovery turns do not erase the evidence a secondary observer still needs. Victor's completed quest is
evaluated through the native player API after its actual rescue callback, without an extra movement turn.
Save/reload checks preserve inventory, equipment, quests, journal text, campaign state, and player attributes;
map transitions preserve player identity.

Castle defender visits select the nearest reachable remaining authored position from the current player coordinate,
using the same directed connectors and reserved final objective as the source route planner. Every defender still
requires its defeat receipt; a remaining live defender with no authored route fails with its exact name.
A source-only traversal estimate of the three chapters falls from 20,116 turns / 100,663 recorded movement actions
in mission-index order to 8,652 / 43,343 with nearest-defender ordering. This model visits every reachable defender
at its authored position, excludes combat delays and paid rest, and treats the 13 disconnected defenders as pending
obligations rather than completed visits. The mandatory waypoint-only estimate is 5,539 turns / 27,778 actions.
The generic limits remain 20,000 turns and 50,000 recorded actions. Complete native runtime headroom is unproven:
six nearest Homecoming town round trips add 284 source hops, while visiting all 48 reachable rest encounters and
returning after each can add 15,120 hops. Combat, fixed actions, and natural injuries require native receipts before
any budget decision; these source estimates do not establish a successful whole-campaign runtime bound.

CI shards must partition the complete selected matrix exactly once. Their initial duration estimates are
provisional until the first native receipts supply measured weights; the planner targets 20 minutes per shard.
`GAME_MCP_BRANCH_REQUIRED=1` turns unavailable native prerequisites into failures. The terminal `mcp-branches`
check requires both platform matrices and all selected native/full-suite/coverage jobs to succeed. An uploaded
exact-head runtime lets diagnostic shards run even when a later parent test fails; that failure still blocks
the terminal check. This workflow change retains strict validation authority and requires explicit human
review before merge. Canonical coverage drivers remain in `coverage-safe`;
the exhaustive subprocess matrix is separate from the 90% eligible-line coverage gate.

The console and expanded-map interaction checks run once in `gameplay`, `full`, and `coverage-safe`. To run only
these checks, use `python3 test.py ConsoleUiInteractionTest UiMinimapInteractionTest`. Their children use guarded
Xvfb on Linux and SDL dummy/software rendering on Windows, with separate preferences and silent audio. They verify
console editing, history bounds, cancellation and focus restoration, plus landmark inspection, explicit travel,
empty lists and stale scene transitions. Missing `_game` or Linux display tooling is reported as a skip; other
import errors and child failures remain failures.

## Campaign scenario gates
Campaign, quest, dialog, trigger, and content-routing changes should report which scenario subset ran. A skipped
scenario is not a pass; include the skip reason in the issue or PR final report.

Fast content validation catches resource ids, dialog actions, quest grants, and script/config wiring before native
builds:

```bash
python3 scripts/validate_content.py --repo-root .
python3 -m unittest tests.test_content_validator
```

The fast Nouraajd smoke scenario checks the MCP-style scenario harness, the Rolf-to-Gooby quest path, door wiring,
spawned objects, inventory, and quest-state snapshots after `_game` is built:

```bash
python3 test.py GameTest.test_mcp_scenario_harness_drives_nouraajd_rolf_gooby
```

The targeted quest-state and reward cleanup subset covers high-value Nouraajd state-machine, timeout cleanup, and
single-claim reward regressions without running the full route:

```bash
python3 test.py \
  GameTest.test_nouraajd_quest_state_machine \
  GameTest.test_nouraajd_victor_timeout_cleanup_regression \
  GameTest.test_nouraajd_octobogz_unique_reward_is_not_duplicated \
  GameTest.test_nouraajd_octobogz_late_contract_claims_existing_clear_reward
```

The slower full-route campaign subset drives the authored Nouraajd route through direct game tests and MCP stdio, then
checks campaign transition into the later maps:

```bash
python3 test.py \
  GameTest.test_map_walkthrough_nouraajd \
  McpServerTest.test_stdio_map_walkthrough_nouraajd \
  GameTest.test_campaign_transitions_preserve_player_and_start_siege \
  GameTest.test_campaign_driver_routes_full_campaign_with_carryover
```

Normal pull request CI runs content validation plus the fast Nouraajd smoke and targeted quest/reward gates whenever
native validation is required. The existing `gameplay` and `ui` suites still run after those gates; the campaign gates
are early, named checks, not a replacement for required gameplay validation.

The dedicated full-route campaign gate runs in the Linux job on the weekly schedule, when manually dispatched with
`run-campaign-scenarios=true`, or when a pull request has the `campaign-scenarios` label. These four tests also belong
to the normal `gameplay` suite. A skip message for the dedicated gate does not mean they were excluded from that
suite; inspect the individual test results before reporting whether a route ran. A skipped gate itself is never
counted as passed.

For any quest, campaign, dialog-trigger, or content-routing issue final report, include:
- which of the fast content validation, fast smoke, targeted quest/reward, and full-route subsets ran;
- the exact command or CI job name for each subset;
- why any full-route gate was skipped, for example "PR label not set and this was not a scheduled or manual campaign
  run";
- any blocked command and its blocker.

## Deterministic simulation helpers
Use `game_simulation.py` for new Python gameplay walkthroughs that need stable setup, bounded movement, object
interaction, map/inventory/quest inspection, GUI tree assertions, or screenshot capture callbacks. The helper raises
`SimulationError` with the failed step and a compact current-state snapshot when a step cannot complete.

Codex and MCP workflows can use the `simulation_run` MCP tool for the same high-level step model without raw handle
or method calls. `capture_gui_screenshot` returns PNG metadata and inline base64 data for MCP callers instead of
writing arbitrary server-side paths. Prefer this layer for new walkthrough coverage, then drop to `engine_call` or
`engine_handle_call` only when the helper does not expose the needed engine operation.

MCP stdio subprocess tests must drain `stderr` while the server is running. The server and native layer can write enough
diagnostic output to block a long walkthrough if the pipe is not consumed. Keep fast smoke requests on the normal
10-second tool timeout, use the documented 60-second timeout only for full map serialization or other known long-route
operations, and include request id, method, map name when known, elapsed time, plus bounded stdout/stderr tails in
timeout failures.

## Debug diagnostics

Use `python play.py --debug` or `python mcp.py --stdio --debug` to retain diagnostics
for one run without changing ordinary logging defaults. Add `--build-config Release`
to MCP on Windows when using a Visual Studio Release build. `GAME_DEBUG=1` enables the
same preset; `--debug-dir` overrides `GAME_DEBUG_DIR`. Relative debug directories resolve
against the source/package root before the launcher changes its working directory.

Each unique run folder contains `manifest.json`, `runtime.log`, `native.log`, and
`gameplay.jsonl`, subject to explicit channel overrides or reported write failures.
The manifest records build/resource/module paths, effective destinations and outcome;
the launcher prints the absolute folder to stderr. Python startup/runtime exceptions
and caught dialog/native Python callback failures retain their original traceback.
MCP call summaries include request ID, a unique invocation sequence, a non-secret
session label, actual callable/method, elapsed time and `isError`. Debug mode does not
enable raw payload tracing. `--trace-messages` independently enables bounded previews.
By default MCP keeps DEBUG summaries in the file and prints only warnings/errors
alongside the folder path. Explicit `--log-level` controls both destinations, while
`--trace-messages` also enables verbose terminal output.
Diagnostic output must never use stdout while serving stdio MCP.

Debug gameplay traces retain the latest 1,000 in-memory events. The active JSONL file
and `gameplay.jsonl.1` each contain at most 1,000 events; inspect the backup before the
active file to read retained history in sequence order. Existing trace callers keep
their first-event limit and single truncation marker. The optional
`game.configure_playtest_trace(..., retain_recent=True)` argument enables recent
history explicitly, as does `GAME_PLAYTEST_TRACE_RETAIN_RECENT=1` with an enabled trace.
Recent-history files require fresh destinations. Existing evidence is preserved on
collision, with a warning and continued in-memory retention. Draining the memory buffer
does not reset disk rotation counters. The native text sink remains append-only for
each run; the rolling limits apply to gameplay history and bounded MCP previews.

If a diagnostics channel cannot be created or written, a concise stderr warning
identifies the failed channel while usable channels and gameplay continue. Gameplay
file writes stop after a failure until tracing is reconfigured. Diagnostics must never
replace the original error or change callback fallback values. These local files may
contain native messages and exception text; structured authentication/session fields
are redacted, but the entire native text stream is not sanitized.

Gameplay channel status is refreshed at startup and shutdown from native output health.
It becomes `memory_only` when output is absent or has failed, while tracing continues to
retain events in memory. Older native modules without the output-health query report
`unverified` rather than claiming active file output. The health query reports detected
failures without probing the filesystem or resetting the trace.

Focused checks without a compiled extension:

```sh
python -B -m unittest tests.test_game_diagnostics tests.test_mcp_diagnostics tests.test_mcp_stdio_encoding
```

`NativeDiagnosticsRuntimeTest` additionally validates native callback/dialog tracebacks
and a real offscreen MCP player route. Run it against the current binary and copied
resources, using `python test.py NativeDiagnosticsRuntimeTest`. Native retention and
rotation regressions run in the core unit tests; the normal performance guard includes
a fixed 10,000-event workload with a 32-event retention window.

## Native performance guards
The deterministic native performance guard suite is built with the `performance_guard_tests` target and run through
CTest label `performance`:

```bash
cmake --build cmake-build-release --target performance_guard_tests -j$(nproc)
ctest --test-dir cmake-build-release --output-on-failure --verbose -L performance
```

These guards are CI gates, not profiling tools. They should use fixed workloads, fixed seeds where randomness is
involved, local repo data, and explicit pass/fail budgets. The CTest wrapper also applies a finite timeout to each
native guard executable and the verbose command keeps timing and test output visible in logs.

Diagnostic performance checks are separate. Use tools such as callgrind, platform profilers, or ad hoc repeated timing
runs to investigate a regression or choose a threshold, but do not use diagnostic-only output as a substitute for the
deterministic `performance` CTest label.

Thresholds should be derived from repeated Release-build measurements on CI-like hardware or the closest available
local equivalent. Choose a budget that leaves headroom for ordinary CI variance while still failing material regressions,
and document the measured baseline, candidate result, platform, build type, command, sample count, and chosen budget.

Budget changes are reviewable behavior changes. Tightening a budget is acceptable when before/after evidence supports
it. Loosening a budget requires a clear reason, updated evidence, and the matching test or documentation update in the
same change; do not raise a threshold only to make a failing run pass.

When submitting performance-sensitive work, include before/after evidence from the exact guard command whenever
possible. If evidence cannot be collected, state which command was blocked and why.

## Branch protection checks
Use `.github/workflows/build.yml` as the required pull request workflow for `main`.

Recommended required status checks:
- `linux` (shown in some GitHub branch-protection UI as `build / linux`)
- `windows-deps` (shown in some GitHub branch-protection UI as `build / windows-deps`)
- `windows` (shown in some GitHub branch-protection UI as `build / windows`)

These jobs cover the current PR build, native C++ tests, native performance guards, Python regression suite, dependency
cache validation, and packaging on Linux and Windows when `scripts/ci_change_classifier.py` marks native validation
necessary. Workflow-only docs/tooling PRs still produce terminal `linux` check evidence, but native-heavy Linux
steps and Windows jobs are skipped after focused workflow validation. The workflow also has a conditional
`linux-coverage` job that runs `./scripts/run_coverage.sh` when changed paths match the coverage rule; because it is
path-gated, do not configure it as an always-present branch-protection check.

Alongside the `native-needed` / `coverage-needed` gate outputs, `scripts/ci_change_classifier.py` also emits an
additive change-**kind** taxonomy: `coverage-relevant`, `native-gui`,
`native-engine`, `content-json-python`, `workflow-python`, and `prompts-docs`. Each changed path is
assigned exactly one primary kind (GUI C++ before generic engine code, `res/` content before tooling), and **every
`src/gui/**` descendant is coverage-relevant** so GUI C++ never skips coverage. These booleans do not change native/coverage need (still taken from the
`NATIVE`/`COVERAGE` pattern sets); they let the workflow route jobs by kind and are covered by a path-matrix test in
`tests/test_ci_change_classifier.py`.

The campaign-specific PR gates run inside `linux` when native validation is required. Full-route campaign scenarios are
scheduled, manual, or label-selected gates inside the same job, so they do not add a separate always-present branch
protection check.

## CI Validation Delivery
Prefer the PR build workflow as the default delivery path for heavy validation. Run focused local checks first, open
the pull request, and wait for the path-selected required checks to reach a successful conclusion instead of
duplicating local compilation, native tests, full Python tests, or coverage. `scripts/ci_change_classifier.py`
selects the validation class from PR paths: lightweight workflow/docs/tooling PRs require `linux`, while
native/source/content PRs require `linux`, `windows-deps`, and `windows`. For coverage-relevant changes the
conditional `coverage` step runs inside the path-gated `linux-coverage` job.

Run heavy local validation only when CI cannot cover the required evidence, a focused local reproduction is
necessary before opening the PR, or GitHub Actions is unavailable or blocked. Record the observed job names,
conclusions, and URLs separately from local commands. Do not report skipped local commands as passed, and do not
enable auto-merge until the selected CI validation has passed when it is the only full-validation evidence.

Manual repository settings for `main`:
- require a pull request before merging
- require status checks to pass before merging
- require branches to be up to date before merging
- select the `linux`, `windows-deps`, and `windows` checks from the `build` workflow


Do not use `Release / build` as a required PR check; `.github/workflows/release.yml` runs only for version tags.
If future work splits fast, gameplay, UI/Xvfb, or coverage runs into separate PR jobs, add those jobs to branch
protection only after they finish deterministically in CI.

## Coverage Workflow
For PR delivery, satisfy coverage by polling the selected build workflow run; the `coverage` step currently runs in the
conditional `linux-coverage` job. Run local coverage only when CI cannot cover the required evidence, polling is
unavailable, or a focused local coverage reproduction is necessary. Coverage is required when a change touches tests,
for example
`test.py` or `tests/unit/**`), `src/core/**`, `src/handler/**`,
`src/object/**`, `native_plugins/**`, or the coverage tooling:

```bash
./scripts/run_coverage.sh
```

The script:
- configures a dedicated coverage build (`cmake-build-coverage`)
- reuses the existing coverage configure by default; set `COVERAGE_FRESH_CONFIGURE=1` to force a fresh configure
- builds `_game`, `for_unit_tests`, and `performance_guard_tests` with GCC/Clang coverage flags
- runs native CTest, including the deterministic `performance` label guard
- runs `python3 test.py --suite coverage-safe` against the coverage build with a finite outer timeout
- generates reports in `coverage/coverage.txt` and `coverage/coverage.html`
- uses the repo-local Python reporter by default; set `COVERAGE_REPORTER=gcovr` only for diagnostic comparison
- rejects line-exclusion controls; every instrumented line in scope is part of the gate
- fails if eligible line coverage is below the default `MIN_COVERAGE=90` gate

Optional coverage speed controls:
- `COVERAGE_CXX_COMPILER_LAUNCHER=<launcher>` overrides the compiler launcher for the coverage build
- `COVERAGE_CXX_COMPILER_LAUNCHER=` disables the compiler launcher
- when `COVERAGE_CXX_COMPILER_LAUNCHER` is unset, the script uses `ccache` automatically if it is available
- `COVERAGE_JOBS=<n>` controls parallel coverage build and report collection jobs
- `COVERAGE_PYTHON_TIMEOUT_SECONDS=<seconds>` bounds the coverage Python phase; the default is 1800 seconds
- `COVERAGE_GCOV_TIMEOUT_SECONDS=<seconds>` bounds each `gcov` JSON extraction; the default is 120 seconds

## Coverage scope
The canonical coverage report is scoped to production/native plugin code by default:

```bash
COVERAGE_INCLUDE_PREFIXES="src native_plugins" ./scripts/run_coverage.sh
```

`scripts/run_coverage.sh` uses that scope unless `COVERAGE_INCLUDE_PREFIXES` is overridden. Coverage line exclusions are
not supported; every instrumented line under the active scope is part of the line gate.
