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
