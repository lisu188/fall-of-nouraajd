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
"""Invariant lock: project Python must never invoke a subprocess with
``shell=True``.

``shell=True`` runs the command through ``/bin/sh``, so any attacker-influenced
value interpolated into the command string becomes shell-executable (the same
command-injection class fixed in the ``subagent_registry`` sweep, which built an
operator command from untrusted branch/worktree fields). Every subprocess call
site in this repo already passes an explicit argv list; this test pins that so a
``shell=True`` call cannot silently reappear. Prefer ``subprocess.run([...])``
and, when composing a human-facing command string, ``shlex.join``/``shlex.quote``.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Directories that hold this project's own Python (the code we control). Excludes
# submodules and build trees, which are not part of this repository's sources.
SOURCE_DIRS = ("scripts", "res", "tests", "src")
ROOT_MODULES = ("mcp.py", "test.py", "game_simulation.py", "play.py", "quest_state.py")

SHELL_TRUE = re.compile(r"shell\s*=\s*True")


def _iter_python_files():
    seen: set[Path] = set()
    for name in ROOT_MODULES:
        path = REPO_ROOT / name
        if path.is_file():
            seen.add(path)
    for directory in SOURCE_DIRS:
        base = REPO_ROOT / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            seen.add(path)
    return sorted(seen)


class NoShellTrueTest(unittest.TestCase):
    def test_no_project_python_uses_subprocess_shell_true(self):
        this_file = Path(__file__).resolve()
        offenders: list[str] = []
        for path in _iter_python_files():
            if path.resolve() == this_file:
                # This file names the pattern in its regex/docstring on purpose.
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if SHELL_TRUE.search(text):
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(
            [],
            offenders,
            "shell=True runs commands through the shell and makes any interpolated value "
            "injectable; use subprocess.run([...]) with an argv list instead. Offending files: "
            f"{offenders}",
        )


if __name__ == "__main__":
    unittest.main()
