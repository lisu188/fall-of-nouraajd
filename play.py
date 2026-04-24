# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2025  Andrzej Lis
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
    for candidate in (root / "cmake-build-release", root / "cmake-build-debug"):
        if candidate.exists():
            return candidate
    return None


def _insert_extension_paths(build_dir: Path) -> None:
    build_config = os.environ.get("GAME_BUILD_CONFIG")
    if build_config:
        _insert_path(build_dir / build_config)
        return
    for config in ("Release", "Debug", "RelWithDebInfo", "MinSizeRel"):
        _insert_path(build_dir / config)


def _ensure_workdir(build_dir: Path | None) -> None:
    if build_dir and not (Path.cwd() / "config").exists():
        os.chdir(build_dir)


def _bootstrap() -> None:
    repo_root = Path(__file__).resolve().parent
    res_dir = repo_root / "res"
    _insert_path(res_dir)
    build_dir = _find_build_dir(repo_root)
    if build_dir:
        _insert_path(build_dir)
        _insert_extension_paths(build_dir)
    _ensure_workdir(build_dir)


_bootstrap()
import game

if __name__ == "__main__":
    game.new()
