#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay explicit build-only forwarding headers for headers an original refactor merged away mid-commit."""

import hashlib
import json
from pathlib import Path

# Catalog #180 ('refactor') and #181 ('reafactor') moved the game under src/ and lib/ and merged each item,
# building and pathfinder class into one header per family, but their unchanged main.cpp, monster.cpp and
# playerstatsview.cpp (and at #181 creature.h) still include the merged-away headers; #182 rewrites those
# includes. Every class those headers declared is still declared, unchanged in name, by the header each
# forwarder includes. Each forwarder carries the include set of the #179 header it replaces.
ITEM = ("src/items/item.h",)
WEAPON = ("src/items/item.h", "src/interactions/interaction.h")
BUILDING = ("src/buildings/building.h",)
PATHFINDER = ("src/pathfinder/pathfinder.h",)
FORWARDERS = {
    "src/items/armor.h": WEAPON,
    "src/items/weapon.h": WEAPON,
    "src/items/smallweapon.h": WEAPON,
    "src/items/belt.h": ITEM,
    "src/items/boots.h": ITEM,
    "src/items/gloves.h": ITEM,
    "src/items/helmet.h": ITEM,
    "src/buildings/cave.h": BUILDING,
    "src/buildings/dungeon.h": BUILDING,
    "src/buildings/teleporter.h": BUILDING,
    "src/pathfinder/dumbpathfinder.h": PATHFINDER,
    "src/pathfinder/randompathfinder.h": PATHFINDER,
    "src/pathfinder/smartpathfinder.h": PATHFINDER,
    "src/stats/damage.h": ("src/stats/stats.h",),
}
INCLUDERS = {
    "src/main.cpp": "43c3b43b1ce639f8aba3c524230058b212f85bcef60fcadbb22b2bc2e6a017ff",
    "src/creatures/monster.cpp": "18742dbfecd4e6988fba3195b6cb7afb29abbd9e8e5194d53d3783589582da70",
    "src/view/playerstatsview.cpp": "65063f51e5ab546d0c60c5d176435f7cfb6d9273a98912b9baaa43e19cda1fd5",
    "src/creatures/creature.h": "30d92e586109a7a5c29bb11310b634b5123e41391d41a2afbf06660a39f827c5",
}
COMMON_TARGETS = {
    "src/items/item.h": "9c8004f44df254caf6df774149dcd7062c1ef015fd5a0147ef14ad42a092c3db",
    "src/buildings/building.h": "102b07e24a3f7d4be7fbf31ab900ad7dd886838d6bd20c7f134c496220a07967",
    "src/interactions/interaction.h": "19085596af03c3fd9f6399dc57b43b41d5e627bdca6ba803116a5a77e283c0e7",
}
STATES = {
    "6cc78c34d64fdee43adca1b829ccf687daa62ced": {
        "targets": {
            **COMMON_TARGETS,
            "src/pathfinder/pathfinder.h": "15d65f217389f8961857e43c6ac3f4b28d3f37e66ef76014a3d0617e3deadf64",
        },
        "forwarders": sorted(set(FORWARDERS) - {"src/stats/damage.h"}),
    },
    "8d1b776c2730296dd7f1ed3b3918e83bcb3a4ab6": {
        "targets": {
            **COMMON_TARGETS,
            "src/pathfinder/pathfinder.h": "3455f3b943ce96f8c1d9882742fe1d6d6144ab6e054db963163aaae26b897743",
            "src/stats/stats.h": "462ead5a1e2f69858c6574e13efeb3dcc157d82f48dbf6d7968335f6af0d8bef",
        },
        "forwarders": sorted(FORWARDERS),
    },
}
PROVENANCE = {
    "includeFixCommit": "09df518e2037d12f912da6c774635a91c886c097",
    "operation": (
        "Supply each header the unchanged original sources still include as a forwarder to the header that "
        "now declares the same classes, carrying the include set of the #179 header it replaces"
    ),
}
BOUNDARY = (
    "Game startup with build-only forwarding headers for headers an original refactor merged away while its "
    "unchanged sources still include them; original sources unchanged"
)


def forwarderBytes(name: str) -> bytes:
    lines = [
        "// Build-only compatibility: original sources of this commit still include this merged-away header.",
        *(f"#include <{target}>" for target in FORWARDERS[name]),
    ]
    return ("\n".join(lines) + "\n").encode()


def originalInput(root: Path, name: str) -> bytes | None:
    path = root / name
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
        raise ValueError(f"Forwarding header input crosses a symlink: {name}")
    if not path.is_file():
        return None
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Forwarding header input escapes the source tree: {name}")
    return path.read_bytes()


def matches(root: Path, pins: dict[str, str]) -> bool:
    for name, expected in pins.items():
        data = originalInput(root, name)
        if data is None or hashlib.sha256(data).hexdigest() != expected:
            return False
    return True


def forwarderPlan(root: Path) -> dict | None:
    """Recognize only the exact pinned original refactor states; never replace an existing header."""
    if not matches(root, INCLUDERS):
        return None
    for commit, state in STATES.items():
        if not matches(root, state["targets"]):
            continue
        data = {}
        for name in state["forwarders"]:
            existing = originalInput(root, name)
            if existing is not None and existing != forwarderBytes(name):
                return None
            data[name] = forwarderBytes(name)
        return {
            "state": commit,
            "forwarders": {
                name: {"includes": list(FORWARDERS[name]), "sha256": hashlib.sha256(content).hexdigest()}
                for name, content in sorted(data.items())
            },
            "inputs": {**INCLUDERS, **state["targets"]},
            "provenance": PROVENANCE,
            "validationBoundary": BOUNDARY,
            "replaySha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "data": data,
        }
    return None


def writeForwarders(root: Path, data: dict[str, bytes]) -> bool:
    created = False
    for name, content in sorted(data.items()):
        if name not in FORWARDERS or content != forwarderBytes(name):
            raise ValueError(f"Unexpected forwarding header output: {name}")
        path = root / name
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
            raise ValueError(f"Forwarding header output crosses a symlink: {name}")
        if path.exists():
            if not path.is_file() or path.read_bytes() != content:
                raise ValueError(f"Forwarding header output already exists with different bytes: {name}")
            continue
        with path.open("xb") as output:
            output.write(content)
        created = True
    return created


def prepareForwarders(root: Path, evidence: Path) -> bool:
    root = root.resolve()
    preparation = json.loads((evidence / "source-preparation.json").read_text())
    recorded = preparation.get("identity", {}).get("forwardingHeaders", {})
    plan = forwarderPlan(root)
    if preparation.get("status") != "success" or plan is None:
        raise ValueError("Forwarding header original inputs or preparation status differ")
    expected = {key: value for key, value in plan.items() if key != "data"}
    if recorded != expected or preparation.get("qmakeArguments"):
        raise ValueError("Forwarding header metadata differs from the reviewed original input hashes")
    return writeForwarders(root, plan["data"])


def main() -> int:
    evidence = Path(__file__).resolve().parent
    created = prepareForwarders(evidence.parent, evidence)
    print("Created forwarding headers" if created else "Verified existing forwarding headers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
