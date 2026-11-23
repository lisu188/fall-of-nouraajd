#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay the exact historical tile configuration transition on a private build copy."""

import hashlib
import json
from pathlib import Path, PurePosixPath

TARGET = "config/tiles.json"
ATTACHMENT = "legacy_tiles.json"
OUTPUT_SHA256 = "8f47dda1738b3ae9fbfc0ed306ab527ce77ab17c0d6e877c2bbf92651a4120b8"
BOUNDARY = (
    "Game startup with legacy tile configuration derived from unchanged original object configuration; "
    "original loader and configuration bytes remain unchanged"
)
INPUTS = {
    "src/CTile.cpp": "885fe0cd8557ef7ef8e0c8e8a7e8910a31e10321ae7eda82ef1c952f72650124",
    "config/objects/tiles.json": "b95264f9ddef82b4196f80b823c161978fa6d11b3d3329964ab23254f0874b71",
}
PROVENANCE = {
    "sourceCommit": "9fc9416b1025044633a6b789212f67c56ecaafba",
    "operation": "Flatten each original properties object; rename animation to path and preserve canStep",
    "reason": "Original CTile::loadFromJson still reads config/tiles.json after configuration moved to config/objects",
    "inferredCompatibility": True,
}


def containedPath(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
        raise ValueError("Legacy tile compatibility path escapes the source tree")
    root = root.resolve()
    path = root / relative
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("Legacy tile compatibility path crosses a symlink")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Legacy tile compatibility path escapes the source tree")
    return path


def legacyTilePlan(root: Path) -> dict | None:
    for name, expected in INPUTS.items():
        path = containedPath(root, name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            return None
    original = json.loads(containedPath(root, "config/objects/tiles.json").read_bytes())
    if not isinstance(original, dict) or not original:
        raise ValueError("Legacy tile compatibility requires the original tile object dictionary")
    legacy = {}
    for name, entry in original.items():
        if not isinstance(entry, dict) or set(entry) != {"properties"}:
            raise ValueError("Legacy tile compatibility tile entry schema differs")
        properties = entry["properties"]
        if not isinstance(properties, dict) or set(properties) != {"animation", "canStep"}:
            raise ValueError("Legacy tile compatibility properties differ")
        animation = properties["animation"]
        if not isinstance(animation, str) or not isinstance(properties["canStep"], bool):
            raise ValueError("Legacy tile compatibility animation/passability types differ")
        animation_path = PurePosixPath(animation)
        if animation_path.parts[:2] != ("images", "tiles") or ".." in animation_path.parts:
            raise ValueError("Legacy tile compatibility animation does not use the original tile image directory")
        containedPath(root, animation)
        legacy[name] = {"path": animation, "canStep": properties["canStep"]}
    data = (json.dumps(legacy, sort_keys=True, indent=2) + "\n").encode()
    if hashlib.sha256(data).hexdigest() != OUTPUT_SHA256:
        raise ValueError("Legacy tile compatibility derived bytes differ from the reviewed output")
    return {
        "path": TARGET,
        "sha256": hashlib.sha256(data).hexdigest(),
        "inputs": dict(INPUTS),
        "provenance": dict(PROVENANCE),
        "validationBoundary": BOUNDARY,
        "replaySha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "data": data,
    }


def writeConfiguration(root: Path, data: bytes) -> bool:
    target = containedPath(root, TARGET)
    if target.exists():
        if not target.is_file() or target.read_bytes() != data:
            raise ValueError("Legacy tile compatibility output already exists with different bytes")
        return False
    if not target.parent.is_dir():
        raise ValueError("Legacy tile compatibility configuration directory is absent")
    with target.open("xb") as output:
        output.write(data)
    return True


def prepareLegacyTiles(root: Path, evidence: Path) -> bool:
    preparation = json.loads((evidence / "source-preparation.json").read_bytes())
    plan = legacyTilePlan(root)
    if preparation.get("status") != "success" or plan is None:
        raise ValueError("Legacy tile compatibility original inputs or preparation status differ")
    expected = {key: value for key, value in plan.items() if key != "data"}
    if preparation.get("identity", {}).get("legacyTileConfiguration") != expected:
        raise ValueError("Legacy tile compatibility metadata differs from its reviewed inputs and transformation")
    outputs = preparation.get("outputs", [])
    matching = [entry for entry in outputs if entry.get("path") == TARGET]
    if (
        outputs != preparation.get("identity", {}).get("outputs")
        or len(matching) != 1
        or matching[0].get("before") is not None
        or matching[0].get("after") != {"kind": "file", "sha256": expected["sha256"]}
    ):
        raise ValueError("Legacy tile compatibility output fingerprints differ")
    attachment = evidence / ATTACHMENT
    if attachment.is_symlink() or not attachment.is_file() or attachment.read_bytes() != plan["data"]:
        raise ValueError("Legacy tile compatibility attachment differs from its derived bytes")
    return writeConfiguration(root, plan["data"])


def main() -> int:
    evidence = Path(__file__).resolve().parent
    created = prepareLegacyTiles(evidence.parent, evidence)
    print("Created legacy tile configuration" if created else "Verified existing legacy tile configuration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
