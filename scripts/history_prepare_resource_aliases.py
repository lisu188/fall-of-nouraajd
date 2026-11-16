#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay explicit build-only aliases for resources one original manifest names under their pre-rename paths."""

import hashlib
import json
from pathlib import Path

# Catalog #128 renamed each monster's time.txt to time.json (Git R100, identical bytes), but its unchanged
# creatures.qrc still names time.txt, so rcc cannot compile the original manifest. #129 updates the manifest.
ALIASES = {
    "images/monsters/octobogz/time.txt": "images/monsters/octobogz/time.json",
    "images/monsters/pritz/time.txt": "images/monsters/pritz/time.json",
    "images/monsters/pritzmage/time.txt": "images/monsters/pritzmage/time.json",
}
INPUTS = {
    "creatures.qrc": "f09c147301607f7818a7c9742bc38bd1617c4a76da182d81b0606afb88411d0c",
    "animation/animationprovider.cpp": "c4e7844230f5b7f26ab7153e6377e15a66b8693015749b09135393e66fceae1c",
    "images/monsters/octobogz/time.json": "cf42b5494746314548e6a655cdc881e188260f1b2d500934b9d44893ca2f8d19",
    "images/monsters/pritz/time.json": "cf42b5494746314548e6a655cdc881e188260f1b2d500934b9d44893ca2f8d19",
    "images/monsters/pritzmage/time.json": "519aa7377c37920c3c6b2f10e49d49ccc2ca889a92c52e00d031265480f4f561",
}
PROVENANCE = {
    "sourceCommit": "856d7792e59d09f1e9cff08d9abb81052a47c7a3",
    "parentCommit": "eef1a4ed9e2148f334fc0da05e924b556e2f355e",
    "manifestFixCommit": "bf32a4c93e396bd645769a9957eacd6a75106b62",
    "operation": (
        "Supply each manifest-named time.txt with the bytes of its original rename target; the parent commit "
        "held these exact files under the manifest-named paths"
    ),
}
BOUNDARY = (
    "Game startup with build-only aliases for resources renamed after their unchanged original manifest; "
    "original manifest and sources unchanged"
)


def originalInput(root: Path, name: str) -> bytes | None:
    path = root / name
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
        raise ValueError(f"Resource alias compatibility input crosses a symlink: {name}")
    if not path.is_file():
        return None
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Resource alias compatibility input escapes the source tree: {name}")
    return path.read_bytes()


def resourceAliasPlan(root: Path) -> dict | None:
    """Recognize only the exact original #128 manifest state; every alias copies a pinned original file."""
    contents = {}
    for name, expected in INPUTS.items():
        data = originalInput(root, name)
        if data is None or hashlib.sha256(data).hexdigest() != expected:
            return None
        contents[name] = data
    for target, source in ALIASES.items():
        existing = originalInput(root, target)
        if existing is not None and existing != contents[source]:
            return None
    data = {target: contents[source] for target, source in ALIASES.items()}
    return {
        "aliases": {
            target: {"source": source, "sha256": hashlib.sha256(data[target]).hexdigest()}
            for target, source in sorted(ALIASES.items())
        },
        "inputs": INPUTS,
        "provenance": PROVENANCE,
        "validationBoundary": BOUNDARY,
        "replaySha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "data": data,
    }


def writeAliases(root: Path, data: dict[str, bytes]) -> bool:
    created = False
    for target, content in sorted(data.items()):
        if target not in ALIASES:
            raise ValueError(f"Unexpected resource alias output: {target}")
        path = root / target
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
            raise ValueError(f"Resource alias output crosses a symlink: {target}")
        if path.exists():
            if not path.is_file() or path.read_bytes() != content:
                raise ValueError(f"Resource alias output already exists with different bytes: {target}")
            continue
        with path.open("xb") as output:
            output.write(content)
        created = True
    return created


def prepareResourceAliases(root: Path, evidence: Path) -> bool:
    root = root.resolve()
    preparation = json.loads((evidence / "source-preparation.json").read_text())
    compatibility = preparation.get("identity", {}).get("resourceAliases", {})
    plan = resourceAliasPlan(root)
    if preparation.get("status") != "success" or plan is None:
        raise ValueError("Resource alias compatibility original inputs or preparation status differ")
    expected = {key: value for key, value in plan.items() if key != "data"}
    if compatibility != expected or preparation.get("qmakeArguments"):
        raise ValueError("Resource alias compatibility metadata differs from the reviewed original input hashes")
    outputs = preparation.get("outputs", [])
    recorded = {entry.get("path"): entry.get("after") for entry in outputs if entry.get("path") in ALIASES}
    if outputs != preparation.get("identity", {}).get("outputs") or recorded != {
        target: {"kind": "file", "sha256": alias["sha256"]} for target, alias in expected["aliases"].items()
    }:
        raise ValueError("Resource alias compatibility derived output fingerprints differ")
    return writeAliases(root, plan["data"])


def main() -> int:
    evidence = Path(__file__).resolve().parent
    created = prepareResourceAliases(evidence.parent, evidence)
    print("Created resource alias compatibility files" if created else "Verified existing resource aliases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
