# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Select the matching GCC5 archive plugin for reviewed original static-LTO projects."""

from __future__ import annotations

import hashlib
from pathlib import Path

ARGUMENT = "QMAKE_AR=gcc-ar-5 cqs"
# Original dependency/common qmake inputs; applications and game source stay untouched.
REVIEWED_INPUT_SETS = (
    {
        "python/python.pro": "7c0d47ddaf518073f3a8d7139794ba5caeaa777a14fc166411134d8865bce44e",
        "game.pri": "fc2fef3d262326d7298a0350ea337086114f8226a3041b29832d870ae3b94092",
    },
    {
        "python/python.pro": "1e47f28b9dcb5905f16529484e2addc944dc8babefa5b09f46c2a554bde47fe1",
        "game.pri": "88f1988e0d1e7709c166c59e35c75aee7690e438139c4ed6530d2ae0398ec8d6",
    },
    {
        "python/python.pro": "1e47f28b9dcb5905f16529484e2addc944dc8babefa5b09f46c2a554bde47fe1",
        "game.pri": "415d2654f778c99df6fc8ba7cc57982f4e8dcd9f58f7f3f08dd8cac02f0b6d19",
    },
    {
        "python/python.pro": "f67d934305b60572f861a189b0e6b96e516a6fb7b173887ec9e3b2a037bd43f4",
        "game.pri": "415d2654f778c99df6fc8ba7cc57982f4e8dcd9f58f7f3f08dd8cac02f0b6d19",
    },
)


def inputMatches(source_root: Path, relative: str, expected: str) -> bool:
    path = source_root
    for component in Path(relative).parts:
        path = path / component
        if path.is_symlink():
            return False
    if not path.is_file() or not path.resolve().is_relative_to(source_root.resolve()):
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == expected


def recipeForSource(recipe: dict, source_root: Path) -> dict:
    """Keep genuine static-LTO inputs and record the GCC5 plugin in ordinary qmake argv."""
    arguments = list(recipe.get("qmakeArguments", []))
    configured_cxx = str(recipe.get("compilerCommand", ""))
    for argument in arguments:
        if argument.startswith("QMAKE_CXX="):
            configured_cxx = argument.split("=", 1)[1]
    if Path(configured_cxx).name != "g++-5":
        return recipe
    if any(argument.startswith("QMAKE_AR=") for argument in arguments):
        return recipe
    if not any(
        all(inputMatches(source_root, relative, expected) for relative, expected in inputs.items())
        for inputs in REVIEWED_INPUT_SETS
    ):
        return recipe
    return {**recipe, "qmakeArguments": [*arguments, ARGUMENT]}
