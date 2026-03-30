# Native C++ Plugins

## Why this design
The current repository builds the engine directly into the `_game` Python
extension. That means there is no standalone engine shared library for an
external `.so`/`.dylib`/`.dll` plugin to link against safely. Splitting the
engine into a separate runtime library would be a much larger refactor than
this task requires.

The first native plugin implementation is therefore:
- compiled into `_game`
- discovered through a native plugin registry
- loaded by name per `CGame` instance
- compatible with the existing Python plugin and map-script startup path

This is the smallest safe fit for the current codebase and leaves a clean seam
for a future external shared-library loader if the engine is later split into a
separately linkable core.

## Startup order
`CGameLoader.loadGame()` now initializes extension content in this order:
1. built-in engine object constructors
2. JSON object configurations
3. configured native C++ plugins
4. existing Python plugins from `res/plugins/*.py`

Map-specific Python `load(context)` scripts still run later when a map is
loaded. Existing Python behavior is unchanged unless a native plugin is
explicitly requested.

## Plugin contract
Native plugins live behind `src/core/CNativePlugin.h`.

Each plugin provides:
- `CNativePluginInfo info() const`
- `void registerContent(CNativePluginContext &context)`

`CNativePluginContext` stages registrations instead of mutating the game
directly. A plugin can currently stage:
- runtime type constructors with `registerType(...)`
- config aliases with `registerConfig(...)`

The loader applies those registrations to the game’s `CObjectHandler` only if
the plugin returns successfully. That keeps a failing native plugin from
partially mutating the Python startup path.

## Registration and loading
Plugins register themselves through the `REGISTER_NATIVE_PLUGIN(...)` macro.
The registry tracks:
- plugin name
- version
- description

The engine exposes three Python-callable entry points on `CGameLoader`:
- `getAvailableNativePlugins()`
- `loadConfiguredNativePlugins(game)`
- `loadNativePlugin(game, name)`

`loadGame()` automatically calls `loadConfiguredNativePlugins(game)`.

## Runtime discovery
Configured native plugins are selected through the `FON_NATIVE_PLUGINS`
environment variable.

Format:
```bash
FON_NATIVE_PLUGINS=example_native_plugin
FON_NATIVE_PLUGINS=example_native_plugin,another_plugin
```

If `FON_NATIVE_PLUGINS` is unset, native plugins are not loaded automatically.
That preserves the repository’s current startup behavior by default.

## Diagnostics
Every `CGame` instance now exposes:
- `getLoadedNativePlugins()`
- `getNativePluginErrors()`

Successful loads are recorded as `name -> version`.
Failures are recorded as `name -> actionable error message`.

Missing-plugin diagnostics include the available registered plugin names and
versions. Loader failures are logged and recorded, but they do not abort the
rest of the Python-driven startup path.

## Example plugin
The example plugin lives at:
- `native_plugins/example/CExampleNativePlugin.cpp`

It registers:
- the native C++ class `CExampleNativePluginMarker`
- the config alias `exampleNativePluginMarker`

After loading `example_native_plugin`, Python can create the example object
without changing the existing Python plugin flow:

```python
import play
import game

g = game.CGameLoader.loadGame()
game.CGameLoader.loadNativePlugin(g, "example_native_plugin")
marker = g.createObject("exampleNativePluginMarker")
print(marker.getType(), marker.getStringProperty("label"))
```

## Build
Build the engine and the example plugin target from the repository root:

```bash
cmake --build cmake-build-release --target native_plugins _game -j$(nproc)
```

The `native_plugins` target builds the example native plugin object code, and
`_game` links it into the Python extension.

## Coexistence boundary with Python
This system extends the existing Python architecture; it does not replace it.

Unchanged behavior:
- `res/game.py` still provides `register(context)` and `trigger(...)`
- `res/plugins/*.py` still load during `loadGame()`
- map `script.py` files still use `load(context)` and load when maps start

Native plugins are an additional registration path for engine/runtime objects.
They should be used when a type or registration path is better expressed in C++,
not as a replacement for existing Python content.
