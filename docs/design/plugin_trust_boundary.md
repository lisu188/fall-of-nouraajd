# Python Resource-Plugin Trust Boundary

Status: Approved. Scope: Python resource plugins, map scripts, and resource files.

## Trust model

Authored repository content under the packaged resource roots is trusted. Content outside those roots
must not be read or executed. The checks are implemented in `src/core/CProvider.cpp` and
`src/core/CLoader.cpp`. Python resource scripts are still executed with restricted builtins
and a module-import allow-list as defense in depth.

The supported executable resource paths are:

- `plugins/**/*.py` for Python gameplay plugins.
- `maps/<validMapName>/script.py` for authored map scripts.

Compiled C++ gameplay objects are part of `game_core`, not loadable plugin libraries.
The engine no longer accepts native or C++ plugin kinds in the Python plugin manifest
and does not invoke `dlopen` or `LoadLibrary` to load gameplay extensions.

## Enforced boundaries

1. `CResourcesProvider` canonicalizes candidate paths and confines resolved resources to
   `isWithinResourceRoot`. Absolute paths, traversal outside a root, and escaping symlinks
   are rejected. The scoped resource resolver does not grant permission to execute arbitrary
   map-local paths as Python.
2. `is_allowed_python_plugin_path` in `src/core/CLoader.cpp` rejects paths other than
   approved Python plugin and map-script paths before `CPluginLoader::loadPlugin` calls
   `pybind11::exec`. Map names pass `CSaveFormat::isValidMapName`.
3. The restricted Python import handler allows safe proxy modules for `game` and `json`
   instead of unrestricted filesystem access, imports, or interpreter builtins.
4. `res/plugins/manifest.json` accepts only `kind: "python"`. Unlisted Python plugin files
   are auto-discovered; listed scripts can select order and map scope.

## Regression coverage

- `tests/unit/test_resource.cpp`: resource-root containment, scoped/base lookup, and safe
  Python script-path checks.
- `tests/security/test_python_plugin_sandbox.py`: import restrictions, builtins restrictions,
  and absence of native plugin loading in the game loader.
- `tests/test_content_validator.py`: Python-only manifest schema and built-in gameplay
  registration source checks.
