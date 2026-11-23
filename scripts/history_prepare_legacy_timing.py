#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Restore exact renamed timing bytes under the legacy resource names in a build copy."""

import hashlib
import json
from pathlib import Path

BOUNDARY = "Game startup with legacy timing resource aliases; original manifest and provider unchanged"
INPUTS = {
    "creatures.qrc": "f09c147301607f7818a7c9742bc38bd1617c4a76da182d81b0606afb88411d0c",
    "animation/animationprovider.cpp": "c4e7844230f5b7f26ab7153e6377e15a66b8693015749b09135393e66fceae1c",
}
RENAMED_INPUTS = {
    "images/monsters/pritzmage/time.json": "519aa7377c37920c3c6b2f10e49d49ccc2ca889a92c52e00d031265480f4f561",
    "images/monsters/pritz/time.json": "cf42b5494746314548e6a655cdc881e188260f1b2d500934b9d44893ca2f8d19",
    "images/monsters/octobogz/time.json": "cf42b5494746314548e6a655cdc881e188260f1b2d500934b9d44893ca2f8d19",
}
PROVENANCE = {
    "sourceCommit": "856d7792e59d09f1e9cff08d9abb81052a47c7a3",
    "authoredCorrectionCommit": "bf32a4c93e396bd645769a9957eacd6a75106b62",
    "operation": "Copy the same-commit byte-identical renamed time.json inputs to the three absent time.txt paths",
    "boundary": "The next authored commit changes both manifest and provider to JSON; this replays no later code",
}


def containedPath(root: Path, name: str) -> Path:
    path = root / name
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
        raise ValueError(f"Legacy timing resource crosses a symlink: {name}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Legacy timing resource escapes the source tree: {name}")
    return path


def originalInput(root: Path, name: str) -> bytes | None:
    path = containedPath(root, name)
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"Legacy timing resource is not a regular file: {name}")
    return path.read_bytes()


def legacyTimingPlan(root: Path, *, allow_generated: bool = False) -> dict | None:
    for name, expected in INPUTS.items():
        data = originalInput(root, name)
        if data is None or hashlib.sha256(data).hexdigest() != expected:
            return None
    data = {}
    for name, expected in RENAMED_INPUTS.items():
        renamed = originalInput(root, name)
        if renamed is None:
            return None
        if hashlib.sha256(renamed).hexdigest() != expected:
            raise ValueError(f"Legacy timing renamed input differs from its original bytes: {name}")
        target = name.removesuffix(".json") + ".txt"
        existing = originalInput(root, target)
        if existing is not None:
            if not allow_generated:
                return None
            if existing != renamed:
                raise ValueError(f"Legacy timing generated output differs: {target}")
        data[target] = renamed
    return {
        "paths": sorted(data),
        "sha256": {name: hashlib.sha256(value).hexdigest() for name, value in sorted(data.items())},
        "inputs": {**INPUTS, **RENAMED_INPUTS},
        "absentInputs": sorted(data),
        "provenance": PROVENANCE,
        "validationBoundary": BOUNDARY,
        "replaySha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "data": data,
    }


def writeTimingResources(root: Path, data: dict[str, bytes]) -> bool:
    expected_paths = {name.removesuffix(".json") + ".txt" for name in RENAMED_INPUTS}
    if set(data) != expected_paths:
        raise ValueError("Legacy timing output paths differ from the reviewed three aliases")
    targets = []
    for name, value in sorted(data.items()):
        path = containedPath(root, name)
        source = name.removesuffix(".txt") + ".json"
        if hashlib.sha256(value).hexdigest() != RENAMED_INPUTS[source]:
            raise ValueError(f"Legacy timing output bytes differ: {name}")
        if path.exists():
            if not path.is_file() or path.read_bytes() != value:
                raise ValueError(f"Legacy timing output already exists with different bytes: {name}")
        else:
            if not path.parent.is_dir():
                raise ValueError(f"Legacy timing original parent directory is absent: {name}")
            targets.append((path, value))
    for path, value in targets:
        with path.open("xb") as output:
            output.write(value)
    return bool(targets)


def prepareLegacyTiming(root: Path, evidence: Path) -> bool:
    root = root.resolve()
    preparation = json.loads((evidence / "source-preparation.json").read_text())
    plan = legacyTimingPlan(root, allow_generated=True)
    if preparation.get("status") != "success" or plan is None:
        raise ValueError("Legacy timing original inputs or preparation status differ")
    expected = {key: value for key, value in plan.items() if key != "data"}
    if preparation.get("identity", {}).get("legacyTimingResources") != expected:
        raise ValueError("Legacy timing metadata differs from the reviewed compatibility")
    outputs = preparation.get("outputs", [])
    if outputs != preparation.get("identity", {}).get("outputs"):
        raise ValueError("Legacy timing output identity differs")
    for name, expected_sha in plan["sha256"].items():
        matching = [entry for entry in outputs if entry.get("path") == name]
        if (
            len(matching) != 1
            or matching[0].get("before") is not None
            or matching[0].get("after") != {"kind": "file", "sha256": expected_sha}
        ):
            raise ValueError(f"Legacy timing output fingerprints differ: {name}")
    return writeTimingResources(root, plan["data"])


def main() -> int:
    evidence = Path(__file__).resolve().parent
    created = prepareLegacyTiming(evidence.parent, evidence)
    print("Created legacy timing resource aliases" if created else "Verified existing legacy timing resource aliases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
