# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Narrow build-only repairs for surviving historical qmake source layouts."""

import hashlib
from pathlib import Path

PROVIDER_INCLUDE = "INCLUDEPATH+=$$_PRO_FILE_PWD_/provider"


PROVIDER_INPUTS = {
    "object/CAnimatedObject.cpp": "ee7fe978f580eb94df97805a13a9fd6f5e3e8e182c566b019118ced36bf93c8f",
    "provider/CAnimationProvider.h": "015a97f5baf7bc207dfeaa950df73903416578a42ffb292c8edbd773fcf011b1",
}


def recipeForSource(recipe: dict, source_root: Path) -> dict:
    """Resolve the hash-pinned unqualified provider include without source edits."""
    for name, expected in PROVIDER_INPUTS.items():
        path = source_root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            return recipe
    arguments = list(recipe.get("qmakeArguments", []))
    if PROVIDER_INCLUDE in arguments:
        return recipe
    arguments.append(PROVIDER_INCLUDE)
    return {**recipe, "qmakeArguments": arguments}
