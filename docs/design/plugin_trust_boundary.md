# Resource-Plugin Trust Boundary

Status: Approved (security design). Scope: defines and documents the trust model
that governs how Python and Lua resource plugins, map scripts, native plugin
libraries, and resource files are loaded and executed. This document records the
decision that backs the enforcement present in `src/core/CProvider.cpp`,
`src/core/CLoader.cpp`, `src/plugin/CNativePluginRuntime.cpp`, and
`src/handler/CLuaHandler.cpp`.

Tracking issue: GitHub #670 ("Define and enforce the Python resource-plugin trust
boundary").

## Trust model decision

**Authored repository content shipped under the resource roots is TRUSTED.
Everything outside the resource roots is UNTRUSTED and must not be executed or
read.**

Concretely:

- The files packaged under `res/` (notably `res/plugins/*.py`,
  `res/plugins/*.lua`, `res/maps/<map>/script.py`, `res/maps/<map>/*.json`,
  `res/config/*.json`, `res/game.py`, and `res/plugins/native/*`) are part of the
  game and are trusted to run with the privileges of the engine. They are
  reviewed as ordinary source.
- A *resource root* is a directory on the provider search path
  (`CResourcesProvider::searchPath`, derived from the module directory by
  `buildResourceSearchPath()`). At install time this is the directory that holds
  the packaged `res/` payload. The trust boundary is the **real, symlink-resolved
  filesystem subtree of a resource root**.
- Any path that, after canonicalization, resolves *outside* every resource root is
  untrusted. This includes absolute paths, `..` traversal, and symlinks inside a
  resource root that point outside it. Untrusted paths are refused: untrusted
  Python is never `exec`'d, untrusted native libraries are never `dlopen`'d, and
  untrusted resource files are never read.

The project's stance is deliberately *not* "resources are untrusted code that must
be sandboxed from the engine." The Python sandbox (restricted builtins, import
allow-list) and the Lua sandbox (allow-listed environment) are defense-in-depth
that limits the blast radius of a mistake in authored content; they are **not**
the trust boundary. The trust boundary is the path/root enforcement at the
engine/script boundary described below.

## Where untrusted paths could enter

All plugin/script/resource loads funnel through a small number of entry points.
The relevant ones (file:line are approximate and tracked against current source):

- `CResourcesProvider::getPath` / `load` / `loadJson`
  (`src/core/CProvider.cpp`): the single resolver every resource read goes
  through. This is the authoritative engine/script boundary check.
- `CPluginLoader::loadPlugin` (`src/core/CLoader.cpp`): executes a Python
  resource plugin or map script (`pybind11::exec`).
- `CPluginLoader::loadLuaPlugin` (`src/core/CLoader.cpp`): executes a Lua
  resource plugin in the sandboxed per-game `lua_State`
  (`src/handler/CLuaHandler.cpp`).
- `CPluginLoader::loadDynamicPlugin` / `plugin_runtime::loadNativePlugin` /
  `resolve_dynamic_library_path` (`src/plugin/CNativePluginRuntime.cpp`):
  `dlopen`s a native plugin library and performs the `CPluginHostV2` entry
  handshake (`src/plugin/CPluginAbi.h`) that hands the plugin its
  `CPluginRegistrar`.
- `CPluginLoader::loadMapPlugins` / `getScriptPath` / `getMapPath` /
  `getConfigPaths` (`src/core/CLoader.cpp`): derive map-relative resource paths
  from a caller-supplied map name.

Untrusted input reaches these through manifest entries (`plugins/manifest.json`),
caller-supplied map names (map transitions, save documents), and any future call
site that forwards an externally-influenced path string.

## Enforcement (already implemented)

The trusted-content stance is enforced by *constraining untrusted/external loads*,
not by sandboxing trusted in-root content:

1. **Resource-root containment (the boundary).**
   `normalizeSafeRelativeResourcePath` rejects empty, absolute, root-name, and
   `..`-traversal paths up front. `CResourcesProvider::getPath` then resolves the
   candidate with `std::filesystem::weakly_canonical` (which follows symlinks) and
   confirms the *resolved* path is still `isWithinResourceRoot` of a canonical
   resource root. A symlink inside the root that points outside it therefore
   resolves out of the subtree and is rejected. This is the load-time check that
   does **not** rely on Python sandbox names.

2. **Python plugin/script path allow-list.** `is_allowed_python_plugin_path`
   restricts `exec`'able Python to `plugins/**.py` and
   `maps/<validMapName>/script.py` (map name validated by
   `CSaveFormat::isValidMapName`). `CPluginLoader::loadPlugin` refuses anything
   else *before* reading or executing it.

3. **Lua plugin path allow-list.** `is_allowed_lua_plugin_path` restricts Lua
   plugins to `plugins/**.lua` (there is no map `script.lua` surface).
   `CPluginLoader::loadLuaPlugin` refuses anything else *before* reading or
   executing it.

4. **Native library allow-list.** `is_allowed_dynamic_library_path` restricts
   `dlopen` to `plugins/native/**`, resolved through the resource provider so the
   containment check above also applies. Native plugins are load-only by design:
   registration donates factories and serializers whose code lives in the plugin
   module, so libraries stay pinned until process exit and no unload entry point
   exists.

5. **Python sandbox (defense-in-depth, not the boundary).**
   `build_restricted_plugin_builtins` injects a reduced `__builtins__` and an
   `__import__` that only yields safe proxies for the `game` and `json` modules,
   so trusted plugins cannot accidentally reach `open`/`eval`/`exec`/arbitrary
   imports.

6. **Lua sandbox (defense-in-depth, not the boundary).** Plugin chunks are
   compiled with the text-only `"t"` mode (precompiled bytecode is rejected) and
   run with their `_ENV` replaced by the allow-listed table built by
   `build_lua_sandbox_env` (`src/handler/CLuaHandler.cpp`): a curated base
   function set, `print` routed to the engine log, and copies of `math` (minus
   `randomseed`), `string` (minus `dump`), and `table`. The `io`, `os`,
   `package`, `debug`, and `coroutine` libraries are never opened
   (`luaL_openlibs` is never called), and `load`/`loadfile`/`dofile`/metatable
   access are absent from the environment.

Trusted in-root loads (`plugins/effect.py`, `maps/nouraajd/script.py`,
`config/items.json`, normal Nouraajd start/load) take the same paths and are
unaffected: they are relative, contained within a resource root, and match the
allow-lists, so they load exactly as before.

## Regression coverage

- `tests/unit/test_resource.cpp`
  (`test_resource_plugin_trust_boundary_rejects_escapes`): behavioral checks that
  a symlink escaping the resource root is rejected by `getPath`/`load`, that an
  out-of-root / traversal Python plugin path is rejected by
  `CPluginLoader::loadPlugin` without executing, and that a trusted in-root plugin
  path is accepted and executed.
- `tests/unit/test_lua.cpp`: behavioral checks of the Lua path allow-list, the
  sandbox environment (blocked globals unreachable from a running plugin),
  bytecode rejection, and error containment.
- `tests/security/test_python_plugin_sandbox.py`: source-level assertions that the
  builtins restriction, import allow-list, path allow-list, native-library
  allow-list, and provider containment checks remain wired in.
- `tests/security/test_lua_plugin_sandbox.py`: source-level assertions that the
  Lua sandbox environment builder, text-only chunk mode, closed standard
  libraries, and Lua path allow-list remain wired in.
