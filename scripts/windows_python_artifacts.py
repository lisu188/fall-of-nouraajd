#!/usr/bin/env python3
# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
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
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Resolve the development artifacts belonging to the active Windows Python 3.12."""

import re
import sys
import sysconfig
from pathlib import Path


def resolvePythonArtifacts():
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Python 3.12 is required for the Windows build.")

    include_dir = Path(sysconfig.get_path("include")).resolve()
    version_header = include_dir / "patchlevel.h"
    if not (include_dir / "Python.h").is_file() or not version_header.is_file():
        raise ValueError(f"Python 3.12 development headers are missing from {include_dir}.")
    header_text = version_header.read_text(encoding="utf-8")
    for part, value in (("MAJOR", 3), ("MINOR", 12)):
        if not re.search(rf"^\s*#\s*define\s+PY_{part}_VERSION\s+{value}\b", header_text, re.MULTILINE):
            raise ValueError(f"Python development headers at {include_dir} do not match Python 3.12.")

    library_candidates = [Path(sys.base_prefix) / "libs" / "python312.lib"]
    if include_dir.name == "python3.12" and include_dir.parent.name == "include":
        library_candidates.append(include_dir.parent.parent / "lib" / "python312.lib")
    for library_path in library_candidates:
        if library_path.is_file():
            debug_candidates = [library_path.with_name("python312_d.lib")]
            if library_path.parent.name == "lib":
                debug_candidates.append(library_path.parent.parent / "debug" / "lib" / "python312_d.lib")
            debug_library = next((path.resolve() for path in debug_candidates if path.is_file()), None)
            return include_dir, library_path.resolve(), debug_library
    raise ValueError("Python 3.12 development import library python312.lib is missing; install a complete Python SDK.")


def main():
    try:
        include_dir, library_path, debug_library = resolvePythonArtifacts()
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"PYTHON_INCLUDE_DIR={include_dir}")
    print(f"PYTHON_LIBRARY={library_path}")
    print(f"PYTHON_LIBRARY_DEBUG={debug_library or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
