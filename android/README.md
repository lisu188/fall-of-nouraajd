# Android MVP build

The Android port keeps the existing C++/SDL engine, Python map/quest scripts, Lua support, JSON content, and `_game` pybind11 bindings. The Android host builds them into `libmain.so`, embeds CPython, extracts packaged content into app-private storage, and calls `game.new()`.

## Current target

- ABI: `arm64-v8a`
- minimum Android API: 26
- orientation: landscape
- Android Gradle Plugin: 9.3.1
- Java: 17
- game native code: C++23

The Gradle wrapper is not committed yet. AGP 9.3 requires Gradle 9.5.0 or newer in the 9.5 line.

## Required external inputs

The build deliberately does not vendor another SDL or Python copy into the repository. Supply these paths through Gradle properties or the equivalent environment variables. Copy `gradle.properties.example` to a local `gradle.properties` or export the environment variables.

| Gradle property | Environment variable | Required layout |
| --- | --- | --- |
| `gameAndroidPythonPrefix` | `GAME_ANDROID_PYTHON_PREFIX` | CPython Android release/build `prefix` directory containing `include/python3.*`, `lib/libpython3.*.so`, and `lib/python3.*` |
| `gameAndroidDependencyPrefix` | `GAME_ANDROID_DEPENDENCY_PREFIX` | Android dependency prefix containing CMake packages and ARM64 libraries for the repository's existing `pybind11`, SDL2, SDL2main, SDL2_image, and SDL2_ttf dependencies |
| `gameAndroidSdlJavaDir` | `GAME_ANDROID_SDL_JAVA_DIR` | SDL2 Android Java source root containing `org/libsdl/app/SDLActivity.java` |

Use SDL Java sources from the same SDL2 version as the native SDL2 library in the dependency prefix.

Official CPython Android distributions are supported by the layout above. The application copies the Python standard library into `files/python/lib/pythonX.Y` and packages only the documented `libpython*.*.so` and `lib*_python.so` support libraries as JNI libraries. The Gradle asset ignore pattern is disabled so underscore-prefixed Python modules and directories are not dropped from the APK.

## Dependency prefix with vcpkg

The repository already declares `pybind11`, `sdl2`, `sdl2-image`, and `sdl2-ttf` in `vcpkg.json`. An `arm64-android` vcpkg installation can therefore be used as `GAME_ANDROID_DEPENDENCY_PREFIX` when `ANDROID_NDK_HOME` is configured and the installed tree provides the matching Android CMake packages and libraries.

The Android CMake build itself is `android/CMakeLists.txt`; it does not modify or replace the desktop `CMakeLists.txt` build graph.

## Build

Set the three paths above, then from `android/` run:

```text
gradle :app:assembleDebug
```

The Gradle build:

1. stages `res/` at `assets/runtime/`;
2. adds root `quest_state.py` to the runtime payload;
3. stages the CPython standard library under `assets/python/lib/pythonX.Y`;
4. packages the required CPython JNI libraries plus ARM64 shared dependencies from the dependency prefix;
5. invokes `android/CMakeLists.txt` to produce `libmain.so`.

At first launch `RuntimeAssets` extracts the packaged Python and game payloads into app-private storage. A package-version marker avoids repeating the extraction until the app version changes. The `files/user` directory is intentionally not deleted during upgrades and is the writable resource/save root.

## Native startup

`src/platform/android/CAndroidMain.cpp` performs the Android-specific startup:

1. obtains SDL's app-private internal storage path;
2. configures `CResourcesProvider` with `files/runtime` and `files/user`;
3. supplies `TMPDIR` under private writable storage when Android has not provided one;
4. registers the existing `_game` module as a built-in CPython module;
5. sets an isolated CPython configuration with `files/python` as Python home and lets CPython derive its standard-library and native-module paths from that prefix;
6. prepends only the extracted game runtime to `sys.path`;
7. imports `game` and calls `game.new()`.

The packaged manifest's existing `plugins/native/native_gameplay` and `plugins/native/native_marker_plugin` ids are preserved. On Android they resolve to code linked into `libmain.so`; desktop builds retain the existing `dlopen`/`LoadLibrary` behavior.

## First device acceptance gate

Before touch-layout work starts, verify on a physical ARM64 device:

- APK installs and launches without linker errors;
- runtime extraction completes once and survives restart;
- `_game` imports successfully;
- `game.new()` reaches the existing start menu;
- the native gameplay plugin registrations are present;
- Nouraajd loads and renders;
- a tap reaches the existing SDL mouse-event path and moves the player;
- a save is written beneath `files/user/save` and remains loadable after force-stop/relaunch.

Touch thresholds, long-press/right-click mapping, mobile panel geometry, pause/resume handling, and automated Android CI are later slices and are not claimed complete by this MVP bootstrap.
