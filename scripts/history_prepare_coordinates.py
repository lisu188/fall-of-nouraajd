#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay explicit build-only coordinate hashing compatibility for one original coordinate source state."""

import hashlib
import json
from pathlib import Path

TARGET = "recovery_coordinates_hash.h"
ATTACHMENT = "coordinates_hash.h"
ARGUMENT = "QMAKE_CXXFLAGS+=-include $$_PRO_FILE_PWD_/" + TARGET
BOUNDARY = "Game startup with coordinate hashing delegated to original CoordsHasher; original sources unchanged"
INPUTS = {
    "pathfinder/smartpathfinder.cpp": "dfdf97905b268c029f221b88ad2ac8eab3375f172cfcc5edd66e8dd25dd9fae5",
    "map/coords.h": "a15fa3a6583c1f421551535d4a2a9a266af92e8af77cda284b3e5e65e57d7264",
    "map/coords.cpp": "64acf00cab276e850f453b2a7bc5b0cd5f8162d43f46e7288f8354f605fbefd3",
}
PROVENANCE = {
    "sourceCommit": "169b592c32924654d830fbf0571e86c5de9dc692",
    "operation": "Provide std::hash<Coords> by delegating to the unchanged original CoordsHasher implementation",
}
HEADER = (
    "// Build-only compatibility: delegate standard hashing to the original coordinate hasher.\n"
    '#pragma once\n#include <functional>\n#include "map/coords.h"\n'
    "namespace std {\n"
    "template<> struct hash<Coords> {\n"
    "    size_t operator()(const Coords &value) const { return CoordsHasher()(value); }\n"
    "};\n}\n"
).encode()


def originalInput(root: Path, name: str) -> bytes | None:
    path = root / name
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
        raise ValueError(f"Coordinate hash compatibility input crosses a symlink: {name}")
    if not path.is_file():
        return None
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Coordinate hash compatibility input escapes the source tree: {name}")
    return path.read_bytes()


def coordinateHashPlan(root: Path) -> dict | None:
    for name, expected in INPUTS.items():
        data = originalInput(root, name)
        if data is None or hashlib.sha256(data).hexdigest() != expected:
            return None
    return {
        "path": TARGET,
        "sha256": hashlib.sha256(HEADER).hexdigest(),
        "inputs": INPUTS,
        "qmakeArgument": ARGUMENT,
        "provenance": PROVENANCE,
        "validationBoundary": BOUNDARY,
        "replaySha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "data": HEADER,
    }


def writeHeader(root: Path, data: bytes) -> bool:
    target = root / TARGET
    if target.is_symlink():
        raise ValueError("Coordinate hash compatibility output is symlinked")
    if target.exists():
        if not target.is_file() or target.read_bytes() != data:
            raise ValueError("Coordinate hash compatibility output already exists with different bytes")
        return False
    with target.open("xb") as output:
        output.write(data)
    return True


def prepareCoordinateHash(root: Path, evidence: Path) -> bool:
    root = root.resolve()
    preparation = json.loads((evidence / "source-preparation.json").read_text())
    compatibility = preparation.get("identity", {}).get("coordinatesHash", {})
    plan = coordinateHashPlan(root)
    if preparation.get("status") != "success" or plan is None:
        raise ValueError("Coordinate hash compatibility original inputs or preparation status differ")
    expected = {key: value for key, value in plan.items() if key != "data"}
    if compatibility != expected or preparation.get("qmakeArguments") != [ARGUMENT]:
        raise ValueError(
            "Coordinate hash compatibility metadata differs from the reviewed original input hashes and hasher delegation"
        )
    outputs = preparation.get("outputs", [])
    matching = [entry for entry in outputs if entry.get("path") == TARGET]
    if (
        outputs != preparation.get("identity", {}).get("outputs")
        or len(matching) != 1
        or matching[0].get("after") != {"kind": "file", "sha256": expected["sha256"]}
    ):
        raise ValueError("Coordinate hash compatibility derived output fingerprints differ")
    attachment = evidence / ATTACHMENT
    if not attachment.is_file() or attachment.is_symlink() or attachment.read_bytes() != HEADER:
        raise ValueError("Coordinate hash compatibility header differs from its reviewed bytes")
    return writeHeader(root, HEADER)


def main() -> int:
    evidence = Path(__file__).resolve().parent
    created = prepareCoordinateHash(evidence.parent, evidence)
    print(
        "Created reflection coordinate hash compatibility header"
        if created
        else "Verified existing compatibility header"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
