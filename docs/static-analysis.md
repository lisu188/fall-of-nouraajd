# Static analysis

Static analysis complements, but never replaces, the required C++/Python tests and the 90% eligible-line coverage policy. All tools scan first-party code; third-party submodules and generated CMake build trees are excluded where applicable.

## CI entrypoints

| Entry point | Analyzer | Coverage | Initial policy |
| --- | --- | --- | --- |
| `.github/workflows/static-analysis.yml` / `python-static` | Ruff | All first-party Python, including gameplay content | Syntax-critical rules block; expanded diagnostics are advisory |
| `python-static` | Mypy | `scripts/run_clang_tidy.py` (strict baseline) | Blocking; expand typed scope as code is annotated |
| `python-static` | Bandit | MCP, launcher, resource scripts and tooling | Advisory findings, tool failure blocks |
| `python-static` | Semgrep | Custom Python security and C++ unsafe-API rules | Rule validation blocks, findings are advisory |
| `static-analysis.yml` / `workflow-static` | Actionlint | `.github/workflows/*.yml` | Advisory findings, tool failure blocks |
| `workflow-static` | ShellCheck | Tracked first-party `*.sh` | Advisory findings, tool failure blocks |
| `static-analysis.yml` / `native-static` | Clang-Tidy 20 | Changed first-party C++ translation units on PRs; all units on main/manual/weekly runs | Advisory |
| `native-static` | Cppcheck | All CMake compilation database units | Advisory |
| `native-static` | Clang Static Analyzer | Debug native build; manual and weekly runs | Advisory |
| `.github/workflows/codeql.yml` | CodeQL 4, `security-and-quality` | Python and GitHub Actions workflows | Uploads code-scanning alerts |
| `.github/workflows/android.yml` | Android Lint | Debug ARM64 Android application after dependency bootstrap | Advisory; lint reports uploaded |

Advisory checks are **executed**, but findings do not fail the pull request while the pre-existing baseline is not reviewed. Tool bootstrap, config validation and the blocking Python checks still fail on errors. Do not mark advisory findings as resolved without inspecting the uploaded reports. Promote a check to blocking only after addressing existing actionable findings and suppressing verified false positives narrowly.

The project requires C++26 and intentionally has no C++23 fallback. Clang-Tidy reads the GCC 15 compilation database with unity builds and PCH disabled. Cppcheck reads the same database. The Clang Static Analyzer uses a separate, non-unity Clang 20 build. Diagnostics due to incomplete analyzer/front-end C++26 compatibility should be investigated rather than resolved by lowering the production language standard.

CodeQL C/C++ is intentionally **not** enabled as a security gate: the documented language matrix lists C++23, not C++26. Review this restriction after upstream support changes. Python and GitHub Actions analyses require no native engine compilation.

## Local Python and content analysis

Install the additional, development-only tooling:

```sh
python3 -m pip install -r requirements-static-analysis.txt
```

Run the blocking baseline first:

```sh
ruff check . --select E9,F63,F7
mypy --config-file mypy.ini
python3 scripts/validate_content.py --repo-root .
```

Explore expanded findings:

```sh
ruff check .
bandit -r -ll -ii mcp.py play.py scripts res
semgrep scan --validate --config .semgrep/engine-security.yml
semgrep scan --config .semgrep/engine-security.yml mcp.py scripts res src native_plugins
```

Ruff's `ruff.toml` opts into broader defect/readability categories for the advisory report and ignores interpreter-provided symbols in dynamic map/plugin scripts. It is not a blanket rule suppression. Mypy starts with the typed C++ analyzer runner; additional modules should be added after annotating their actual engine boundary types. Semgrep rules live at `.semgrep/engine-security.yml` and target unsafe shell execution, resource-script dynamic execution, unsafe deserialization, externally exposed MCP listeners and unsafe native C string operations.

For gameplay JSON and Python content relationships, `scripts/validate_content.py` remains the authoritative specialized static validator and runs in the normal required build workflow.

## Local native analysis

After installing the native dependencies specified by `README.md`, configure the compilation database with GCC 15:

```sh
export CC=gcc-15 CXX=g++-15
export GAME_CONFIGURE_SKIP_APT=1 GAME_CONFIGURE_SKIP_SUBMODULES=1
export GAME_CONFIGURE_BUILD_TYPES=Release
export GAME_CONFIGURE_BUILD_PREFIX=cmake-build-gcc15-static
./configure.sh
cmake -S . -B cmake-build-gcc15-static-release \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DGAME_ENABLE_UNITY_BUILD=OFF \
    -DGAME_ENABLE_PCH=OFF
python3 scripts/run_clang_tidy.py --build-dir cmake-build-gcc15-static-release --jobs 2
cppcheck --project=cmake-build-gcc15-static-release/compile_commands.json \
    --enable=warning,performance,portability --suppress=missingIncludeSystem
```

To scan only changed C++ files, pass `--changed-base origin/main` to the clang-tidy runner. It selects compilation database entries rooted under `src/` or `native_plugins/` and writes per-file findings to `analysis-reports/clang-tidy/`.

Run the Clang Static Analyzer in a separate Clang 20 build using the commands in `native-static`. Since its invocation compiles much of the native engine, it runs on the weekly/manual CI schedule instead of each pull request.

## Android analysis

Android Lint is performed after `gradle :app:assembleDebug` in the existing Android ARM64 workflow, reusing the bootstrapped Python/SDL/NDK dependencies. Reports are uploaded from `android/app/build/reports/lint-results-*`. Running Gradle Lint without the full bootstrap is not equivalent: the project's Gradle configuration requires external native and embedded-Python prefixes.

## Maintenance

Pin analyzer Python dependencies in `requirements-static-analysis.txt`. Update them deliberately and review the generated findings after upgrades. Only raise severity thresholds or expand required jobs based on an observed clean baseline.

Do not set the optional `native-static`, `python-static`, CodeQL or Android-Lint jobs as required branch-protection checks until their first GitHub Actions runs have been verified. Existing `build / linux`, `build / windows-deps`, and `build / windows` checks remain authoritative.

Security findings are hypotheses, not proofs of vulnerabilities. Review source and sink context, pybind11 lifetime ownership, plugin trust boundaries, and actual exploitability before changing production behavior.
