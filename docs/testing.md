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
GAME_XVFB_JOBS=4 python3 test.py --suite ui
python3 test.py --suite coverage-safe
python3 test.py --suite full
```

- `fast` runs runner, bootstrap, manifest, coverage-report, and lightweight MCP protocol checks that do not require the
  compiled `_game` module.
- `gameplay` runs deterministic engine, map, save/load, quest, combat, and MCP gameplay checks after `_game` is built.
- `ui` runs the Xvfb parent test and GUI layout manifest checks; it is intended for Linux/Unix environments with
  `xvfb-run` and `xauth`.
- `coverage-safe` is the Python suite used by `./scripts/run_coverage.sh`; it keeps deterministic coverage drivers and
  GUI coverage, but omits duplicate subprocess walkthrough checks that are already covered by the normal gameplay CI
  suite.
- `full` is the default full-suite behavior and is equivalent to omitting `--suite`.

Use `--jobs <n>` with any suite to enable the existing sharded runner, for example
`python3 test.py --suite gameplay --jobs "$(nproc)"`.

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
necessary. Workflow-only docs/prompts/tooling PRs still produce terminal `linux` check evidence, but native-heavy Linux
steps and Windows jobs are skipped after focused workflow validation. The workflow also has a conditional
`linux-coverage` job that runs `./scripts/run_coverage.sh` when changed paths match the coverage rule; because it is
path-gated, do not configure it as an always-present branch-protection check.

## CI-Polled Validation
For local agents, prefer the PR build workflow as the default delivery path for heavy validation. Run focused local
checks first, open the pull request, and poll the path-selected required checks to a successful conclusion instead of
duplicating local compilation, native tests, full Python tests, or coverage:

```bash
python3 scripts/poll_pr_checks.py <PR_NUMBER>
```

When no `--check` is supplied, the poller inspects PR paths with `scripts/ci_change_classifier.py`: lightweight
workflow/docs/tooling PRs require `linux`, while native/source/content PRs require `linux`, `windows-deps`, and
`windows`. Use explicit `--check` values only to intentionally override the path-selected set for a documented reason:

```bash
python3 scripts/poll_pr_checks.py <PR_NUMBER> --check linux --check windows-deps --check windows
```

For coverage-relevant changes, the poller auto-requires the conditional coverage step when changed paths match the
workflow coverage rule. Passing `--require-step coverage` explicitly is still valid when the caller wants to force that
check:

```bash
python3 scripts/poll_pr_checks.py <PR_NUMBER> --require-step coverage
```

Run heavy local validation only when CI cannot cover the required evidence, a focused local reproduction is
necessary before opening the PR, or GitHub Actions polling is unavailable or blocked. Passing the path-selected checks
is sufficient PR delivery evidence for the classifier-selected validation class: native/source/content changes require
Linux and Windows build jobs, while workflow-only changes keep a terminal Linux check and skip unrelated native-heavy
steps. It proves coverage only when the workflow's changed-path rule runs the `coverage` step somewhere in the selected
build workflow run, currently in `linux-coverage`; the poller auto-adds that step for coverage-relevant PR paths. Record
the polled job names, conclusions, and URLs separately from local commands. Do not report skipped local commands as
passed, and do not enable auto-merge until the selected CI-polled validation has passed when it is the only
full-validation evidence.

Manual repository settings for `main`:
- require a pull request before merging
- require status checks to pass before merging
- require branches to be up to date before merging
- select the `linux`, `windows-deps`, and `windows` checks from the `build` workflow

Audit the live repository settings before merge-policy or cleanup decisions with:

```bash
python3 scripts/controller_resource_audit.py --json --skip-run-tree-sizes --github-repo lisu188/fall-of-nouraajd
```

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
