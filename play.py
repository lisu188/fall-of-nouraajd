# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2025-2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
import argparse
import importlib
import os
from pathlib import Path
import sys


def _insert_path(entry: Path) -> None:
    if not entry.exists():
        return
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)


def _find_build_dir(root: Path) -> Path | None:
    build_dir_override = os.environ.get("GAME_BUILD_DIR")
    if build_dir_override:
        return (root / build_dir_override).resolve()
    for candidate in (root / "cmake-build-release", root / "cmake-build-debug"):
        if candidate.exists():
            return candidate
    return None


def _is_resource_root(path: Path) -> bool:
    return (path / "config").is_dir() and (path / "maps").is_dir() and (path / "plugins").is_dir()


def _insert_extension_paths(build_dir: Path) -> None:
    build_config = os.environ.get("GAME_BUILD_CONFIG")
    if build_config:
        _insert_path(build_dir / build_config)
        return
    for config in reversed(("Release", "Debug", "RelWithDebInfo", "MinSizeRel")):
        _insert_path(build_dir / config)


def _ensure_workdir(trusted_dir: Path) -> None:
    os.chdir(trusted_dir)


def _bootstrap() -> None:
    script_dir = Path(__file__).resolve().parent
    source_res_dir = script_dir / "res"
    build_dir = _find_build_dir(script_dir)
    if build_dir:
        _insert_path(build_dir)
        _insert_extension_paths(build_dir)
        _insert_path(source_res_dir)
        _ensure_workdir(build_dir)
        return
    if _is_resource_root(script_dir):
        _insert_path(script_dir)
        _insert_extension_paths(script_dir)
        _ensure_workdir(script_dir)
        return
    _insert_path(source_res_dir)
    _ensure_workdir(source_res_dir)


def parseArgs(argv=None):
    parser = argparse.ArgumentParser(description="Start the game")
    parser.add_argument("--debug", action="store_true", default=None, help="Write a per-run debugging bundle")
    parser.add_argument("--debug-dir", default=None, help="Debug output directory (relative to the game root)")
    return parser.parse_args(argv)


def main(argv=None):
    import game_diagnostics

    args = parseArgs(argv)
    script_dir = Path(__file__).resolve().parent
    build_dir = _find_build_dir(script_dir)
    if build_dir is None:
        build_dir = script_dir if _is_resource_root(script_dir) else script_dir / "cmake-build-release"
    session = game_diagnostics.startSession(
        repo_root=script_dir,
        build_dir=build_dir,
        entrypoint="play",
        debug=args.debug,
        debug_dir=args.debug_dir,
    )
    try:
        _bootstrap()
        if session is not None:
            native_module = importlib.import_module("_game")
            session.applyNative(native_module)
            session.configureTrace(native_module)
        game_module = importlib.import_module("game")
        if session is not None:
            resource_root = next(
                (
                    candidate
                    for candidate in (Path.cwd(), script_dir, script_dir / "res")
                    if _is_resource_root(candidate)
                ),
                None,
            )
            build_config = os.environ.get("GAME_BUILD_CONFIG")
            extension_dirs = (
                [build_dir / build_config]
                if build_config
                else [build_dir / config for config in ("Release", "Debug", "RelWithDebInfo", "MinSizeRel")]
            )
            session.updateManifest(
                gameModule=str(getattr(game_module, "__file__", "<unknown>")),
                cwd=str(Path.cwd()),
                resourceRoot=str(resource_root) if resource_root is not None else None,
                buildConfig=build_config,
                extensionDirs=[str(path) for path in extension_dirs if path.exists()],
            )
        game_module.new()
        if session is not None:
            session.finish()
        return 0
    except Exception as error:
        if session is not None:
            session.finish(status="failed", error=error)
        raise
    except BaseException:
        if session is not None:
            session.finish(status="interrupted")
        raise
    finally:
        if session is not None:
            session.close()


if __name__ == "__main__":
    raise SystemExit(main())
else:
    _bootstrap()
    import game
