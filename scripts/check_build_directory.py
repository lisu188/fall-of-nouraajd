#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Refuse to repurpose a configured build directory for another toolchain."""

import argparse
import os
import shutil
from pathlib import Path


def validateBuildDirectory(build_dir: Path, generator: str, compiler: str) -> None:
    cache_path = build_dir / "CMakeCache.txt"
    if not cache_path.exists():
        return
    entries = {}
    for line in cache_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(("#", "//")) or "=" not in line or ":" not in line.split("=", 1)[0]:
            continue
        key, value = line.split("=", 1)
        entries[key.split(":", 1)[0]] = value
    selected_compiler = Path(shutil.which(compiler) or compiler).resolve()
    cached_compiler = entries.get("CMAKE_CXX_COMPILER")
    compiler_matches = cached_compiler and os.path.normcase(str(Path(cached_compiler).resolve())) == os.path.normcase(
        str(selected_compiler)
    )
    if entries.get("CMAKE_GENERATOR") != generator or not compiler_matches:
        raise ValueError(
            f"Preserving existing build directory {build_dir.resolve()}: its generator/compiler differs. "
            "Choose a new compiler-specific build directory; cached files and saves will not be removed."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--generator", required=True)
    parser.add_argument("--compiler", required=True)
    args = parser.parse_args()
    try:
        validateBuildDirectory(args.build_dir, args.generator, args.compiler)
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
