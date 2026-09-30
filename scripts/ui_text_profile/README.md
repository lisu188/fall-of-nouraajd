# Supplemental text profile

This opt-in Windows harness links an existing MSVC x64 Release object build. It does not recompile the engine or
run as a CI timing gate. The ordinary `performance_guard_tests` target supplies deterministic cache/render gates.
The executable forces SDL dummy video, dummy audio, software rendering and an isolated preferences directory,
and refuses to run if the active driver does not match.

Build the selected checkout's `performance_guard_tests` first. Point `GAME_SOURCE_DIR` and `GAME_BUILD_DIR` at that
same checkout and its build. Do not link while engine objects are being written. Use a separate harness build
directory and writable data directory for each revision. With PowerShell variables naming absolute paths:

```powershell
cmake -S scripts/ui_text_profile -B cmake-build-profile-current -G "Visual Studio 17 2022" -A x64 `
  "-DCMAKE_TOOLCHAIN_FILE=$toolchainPath" -DVCPKG_MANIFEST_INSTALL=OFF `
  "-DVCPKG_INSTALLED_DIR=$dependencyRoot" "-DPython3_EXECUTABLE=$pythonExecutable" `
  "-DGAME_SOURCE_DIR=$gameSource" "-DGAME_BUILD_DIR=$gameBuild" -DCMAKE_SUPPRESS_REGENERATION=ON
cmake --build cmake-build-profile-current --config Release --target ui_profile --parallel 2
$env:PYTHONHOME = Split-Path $pythonExecutable
$env:PATH = "$dependencyRoot/x64-windows/bin;" + $env:PATH
& ./cmake-build-profile-current/Release/ui_profile.exe "$gameSource/res" ./cmake-build-profile-current/data
```

The retained September 8, 2026 samples used Visual Studio 2022 / MSVC 19.44.35226, x64 Release, Python 3.12.13,
the same dependency installation, and this exact source harness. The original source was commit
`065b5d6010bffa6044b422e0ff6292557bfcf313`; the redesigned sample included the new fonts/style cache before later
layout refinements. Baseline engine configuration omitted `CMAKE_BUILD_TYPE`, so that checkout did not enable the
current unity/PCH options. Both used MSVC Release optimization, but the compiler setup and rendered font assets
were not identical. Keep those limitations when interpreting the preserved samples.

The workload uses 200 fixed strings at width 600, then 200 cached lookups, then 200 redraw passes of ten strings.
One warm-up precedes seven samples. Each sample requires 2,000 successful copies and no skipped/failed copies.
Timing never changes a pass/fail threshold. The font constructor is outside cold timing; lazy font loads within
the first lookup are inside it. There is no frame presentation in the redraw loop. `baseline-results.txt` and
`redesign-results.txt` preserve every measured sample rather than just the medians.

## Choice-list cache profile

The separate `ui_choice_profile` target draws the same 700 named choices five times and reports texture loads and
retained cache entries per frame. Use the configuration and environment above, then run:

```powershell
cmake --build cmake-build-profile-current --config Release --target ui_choice_profile --parallel 2
& ./cmake-build-profile-current/Release/ui_choice_profile.exe "$gameSource/res" ./cmake-build-profile-current/data
& ./cmake-build-profile-current/Release/ui_choice_profile.exe "$gameSource/res" ./cmake-build-profile-current/data --unattached-fixture
```

The default fixture supplies a real 1800x1000 layout. `test_choice_layout_does_not_rasterize_hidden_rows_on_redraw`
in the ordinary performance suite uses that geometry, asserts a usable viewport, warms two frames, then requires
zero additional texture loads across four unchanged redraws. Reconfiguring the choices and viewport must invalidate
the metrics. Neither the 512-texture budget nor the zero-load assertion was relaxed.

`choice-baseline-results.txt` preserves the original development probe before row-metric reuse: each unchanged
redraw rasterized 723 strings and churned the bounded texture cache. That early diagnostic fixture omitted a
`CLayout`, so its samples establish repeated hidden-row work rather than realistic screen layout. The optional
`--unattached-fixture` mode retains that setup for comparison; default-mode results and the CI guard cover the
corrected geometry. The baseline predates the commit containing this overhaul; it is a retained development
measurement, not a benchmark reproduced from `065b5d6` (which did not contain the new chooser).

The September 19, 2026 rerun used the commands above with `cmake-build-release/ui-choice-profile-final` as the
harness build directory. `choice-redesign-results.txt` retains both complete outputs. With valid layout, frame
texture loads were `729, 6, 0, 0, 0`, settling at 223 cache entries. The original unattached fixture yielded
`715, 6, 0, 0, 0`, settling at 209 entries. Both stop rasterizing after warm-up; the historical unoptimized probe
continued to load 723 textures per unchanged frame. These are operation counts, not elapsed-time speedup claims.

## Long reward receipt rendering

The September 19, 2026 receipt regression uses 241 distinct rewards, scrolls to the end, changes only the final
reward label beyond byte 4096, and compares the rendered SDL pixels. Before switching receipts to the shared
paragraph layout, the pixels did not change: the full-string texture path discarded the final reward. The same
assertion passes with the paragraph layout. Reading and scrolling leave inventory and the map turn unchanged.

The accompanying deterministic performance case uses 700 rows in a 600x180 viewport. It scrolls to the end,
clears the text cache, renders once, then measures 25 unchanged frames. Both versions used Windows x64 Release,
Visual Studio 2022 / MSVC 19.44, Python 3.12, and the same offscreen environment:

```powershell
$env:SDL_VIDEODRIVER = "dummy"
$env:SDL_AUDIODRIVER = "dummy"
$env:SDL_RENDER_DRIVER = "software"
$env:PYTHONHOME = "C:/Users/andrz/git/fall-of-nouraajd/vcpkg_installed/x64-windows/tools/python3"
ctest --test-dir cmake-build-release -C Release --output-on-failure -V `
  -R '^(for_unit_tests.ui_management_unit_tests|performance.performance_guard_tests)$'
```

| Receipt renderer | Final-label pixel regression | Visible texture loads | New loads over 25 warm frames | Copies |
| --- | --- | ---: | ---: | ---: |
| Full-string renderer | Failed (truncated content) | 1 | 0 | 25 |
| Shared paragraph layout | Passed | 7 | 0 | 150 |
| Deterministic budget | Must pass | 1-16 | 0 | 1-400 |

The earlier run returned exit 8 because the functional regression failed; the corrected run returned exit 0
(management 0.33s, performance 2.08s). The higher visible work renders the actual final rows and scroll cue;
the truncated result is not a valid performance target. No budget was relaxed. The receipt guard is part of the
normal `performance_guard_tests` target, and the screenshot generator retains overflow, ending, and 720p/200%
ending captures through `captureRewardReceipts`.

## Screenshot pixel analysis

The source-only `pixel_analysis.py` harness measures the two screenshot assertion helpers without importing
the game or opening a display. It extracts only their AST definitions from `--source`. Both revisions use
the same fixed 1920x1080 RGBA buffers: RGB `(17,19,23)` with opaque alpha before, and RGB `(17,20,23)` with
zero alpha after. The summary panel is `(20,30,1880,1020)` with two clipped regions; the diff covers the
whole frame. Each helper gets one warm-up and three measured samples, followed by a separate Python-work
observation. The observation stops after 2,000 helper line events; it does not affect the timing samples.

The September 26, 2026 comparison used Windows 11 x64, Python 3.12.13, Pillow 12.3.0, and these commands from
the repository root. The baseline file is an ignored diagnostic input, not modified game/build resources.

```powershell
$pythonExecutable = "C:/Users/andrz/git/fall-of-nouraajd/vcpkg_installed/x64-windows/tools/python3/python.exe"
$env:PYTHONPATH = "C:/Users/andrz/.codex/worktrees/ui-capture-python"
& $pythonExecutable -c "import pathlib, subprocess; pathlib.Path('cmake-build-release/ui-pixel-baseline-e0228b60.py').write_bytes(subprocess.check_output(['git', '-c', 'core.excludesFile=', 'show', 'e0228b60:test.py']))"
& $pythonExecutable scripts/ui_text_profile/pixel_analysis.py --source cmake-build-release/ui-pixel-baseline-e0228b60.py
& $pythonExecutable scripts/ui_text_profile/pixel_analysis.py --source test.py
& $pythonExecutable -m unittest tests.test_ui_pixel_analysis tests.test_test_runner_packaging -v
& $pythonExecutable test.py --jobs 1 UiPixelAnalysisTest TestRunnerSuiteTest
```

| Helper | Baseline samples (seconds) | Pillow samples (seconds) | Baseline median | Pillow median | Python line events before / after |
| --- | --- | --- | ---: | ---: | ---: |
| `panel_pixel_summary` | 2.503553, 2.444670, 2.399151 | 0.014754, 0.014558, 0.014636 | 2.444670 | 0.014636 | >2,000 / 40 |
| `pixel_diff_bounds` | 1.239284, 1.239606, 1.239951 | 0.020920, 0.020754, 0.020419 | 1.239606 | 0.020754 | >2,000 / 14 |

Both versions return 1,917,600 inside pixels, 156,000 outside pixels, region counts 518,400 and 200, and
tight bounds `[0,0,1920,1080]`. Both return 2,073,600 changed pixels with the same full-frame diff bounds.
The regression suite separately checks independent small-image oracles, negative/clipped and overlapping
summary regions, zero/empty input, sparse tight bounds, all three RGB channels including values of one,
and alpha-only changes. Diff inputs retain the existing in-bounds screenshot-rectangle contract.

Before the optimization, both helpers fail the fixed Full HD Python-work guard; afterward both pass its
unchanged 2,000-line bound with identical results. Timing is supplemental only. No GUI timeout was extended:
the real offscreen choice-layout and cave-defeat CLI regressions subsequently passed in 5.954s and 2.453s.

## Current ability availability and inspection labels

The September 30, 2026 follow-up used Windows x64 Release, Visual Studio 2022 / MSVC 19.44, Python 3.12 and
SDL dummy/software. The native management regression first ran against the old inspection behavior with only
the Character detail getter extracted for testing. It reported 48 failed assertions: 18 abbreviated stat labels
and 30 missing targeting/availability explanations. The same behavior checks pass after using shared metadata.

Exact baseline and final commands from the repository root:

```powershell
$env:SDL_VIDEODRIVER = "dummy"
$env:SDL_AUDIODRIVER = "dummy"
$env:SDL_RENDER_DRIVER = "software"
$env:PYTHONHOME = "C:/Users/andrz/git/fall-of-nouraajd/vcpkg_installed/x64-windows/tools/python3"
cmake --build cmake-build-release --config Release --target ui_management_unit_tests --parallel 8
ctest --test-dir cmake-build-release -C Release --output-on-failure --verbose -R '^for_unit_tests.ui_management_unit_tests$'
cmake --build cmake-build-release --config Release --target performance_guard_tests --parallel 8
cmake -S . -B cmake-build-release
ctest --test-dir cmake-build-release -C Release --output-on-failure --verbose -L performance

# After the shared inspection change and the combined ownership/mana regressions:
cmake -S . -B cmake-build-release
cmake --build cmake-build-release --config Release --target ui_management_unit_tests performance_guard_tests _game --parallel 8
ctest --test-dir cmake-build-release -C Release --output-on-failure --verbose -R '^(for_unit_tests.ui_management_unit_tests|performance.performance_guard_tests)$'
```

The first performance attempt used stale local build resources and failed three sparse-map path checks. Rebuilding
the unchanged guard and configuring the source resources restored the baseline; no assertions or budgets changed.
The final combined run passes both CTest entries. Operation counts are the performance evidence, not a timing ratio:

| Workload | Before inspection change | After inspection change |
| --- | --- | --- |
| 200 cached strings, 2,000 copies | 0 new texture loads | 0 new texture loads |
| 700 choices, four warm redraws | 0 new texture loads | 0 new texture loads |
| 700 detail paragraphs, 25 warm redraws | 6 visible loads, 0 warm loads | 6 visible loads, 0 warm loads |
| 700 receipt rows, 25 warm redraws | 7 visible loads, 0 warm loads | 7 visible loads, 0 warm loads |
| Selected Character ability, available | Availability absent | 1 initial load, 0 loads over 25 warm redraws |
| Same ability after mana shortage | Availability absent | 1 refresh load, 0 loads over 25 warm redraws |

The new Character guard uses a real player-owned action with wrapped prose. It checks the current exact mana
shortage, bounded refresh work (budget 16), successful software-renderer copies and unchanged HP/mana/world turn.
Native management fixtures additionally cover explicit caster targeting, legacy Buff targeting, enemy targeting,
exact-cost availability, lost ownership, defeat and combined restrictions. Defeat and lost ownership take priority
over mana shortages because replenishing mana cannot restore those actions. No existing guard was weakened.

## Non-closeable loading reader

The final visual audit found that the loading reader rendered Continue and accepted dismissal input despite
`setCloseable(false)`. Windows x64 Release checks used the same SDL dummy/software environment as above. A GUI-routed
input regression produced nine failed assertions before the fix and passes afterward, including a mouse press
whose release arrives after dismissal has been disabled. Ordinary readers and programmatic `hideLoading` still close.

Exact baseline and final commands (with the respective reader implementation):

```powershell
cmake --build cmake-build-release --config Release --target ui_frontend_unit_tests performance_guard_tests _game -j 4
ctest --test-dir cmake-build-release -C Release --output-on-failure -R '^for_unit_tests.ui_frontend_unit_tests$'
ctest --test-dir cmake-build-release -C Release --output-on-failure --verbose -R '^performance.performance_guard_tests$'
cmake -S . -B cmake-build-release
```

The unchanged waiting-reader workload records six initial texture loads (budget eight) and zero new loads across
25 warm redraws both before and after the fix. It also requires successful software-renderer copies and an attached
reader. The Character, text, chooser, paragraph and receipt counts above remain unchanged; no existing budget is
relaxed. These deterministic operation counts are the comparison, not a claimed elapsed-time improvement.
