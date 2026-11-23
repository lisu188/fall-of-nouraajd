#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay the missing #176 translation unit from the sole change in its immediate child."""

import hashlib
import json
from pathlib import Path
import subprocess

COMMIT = "7022f82ba68e4b740e85915b1710dd0502837efe"
CHILD = "779fb803ff021de5e74ed3b24d7c31a9adcaa236"
BLOB = "312d41bd4abc4ad98ea62978f07fc628b6a4946f"
TARGET = "pathfinder/pathfindercache.cpp"
ATTACHMENT = "pathfindercache.cpp"
SHA256 = "21621e8fa9f86452560abf98530a3bd094691e8d59a53ba9da10fb92b5dd3f92"
INPUTS = {
    "Game.pro": "e2b7c8cc57f98bdf564df7b6528ab5138a8e52380460d24d28d4b2493b43439b",
    "pathfinder/pathfindercache.h": "3a8fcc728b96d82063854563cf5eaa3323980bd79b35245976e16a1c856d5044",
}
PURPOSE = "Pathfinder cache implementation from the immediate child on the isolated build copy"


def identity() -> dict:
    return {
        "sourceCommit": COMMIT,
        "donorCommit": CHILD,
        "donorBlob": BLOB,
        "path": TARGET,
        "sha256": SHA256,
        "inputs": INPUTS,
        "validationBoundary": PURPOSE,
        "replaySha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def donorBytes(repo_root: Path) -> bytes:
    result = subprocess.run(["git", "-C", str(repo_root), "show", CHILD + ":" + TARGET], capture_output=True)
    if result.returncode or hashlib.sha256(result.stdout).hexdigest() != SHA256:
        raise ValueError("Pathfinder cache donor differs from the pinned original child source")
    return result.stdout


def containedPath(root: Path, name: str) -> Path:
    path = root / name
    if path.is_symlink() or path.resolve() != root.resolve() / name:
        raise ValueError("Pathfinder cache preparation crosses a symlink: " + name)
    return path


def apply(root: Path, data: bytes, *, replay: bool = False) -> None:
    for name, digest in INPUTS.items():
        path = containedPath(root, name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Pathfinder cache project or header differs from the reviewed input")
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Pathfinder cache attachment differs from the reviewed donor")
    target = containedPath(root, TARGET)
    if replay and target.is_file() and target.read_bytes() == data:
        return
    with target.open("xb") as output:
        output.write(data)


def validate(preparation: dict) -> None:
    outputs = preparation.get("outputs", [])
    matching = [entry for entry in outputs if entry.get("path") == TARGET]
    if (
        preparation.get("status") != "success"
        or preparation.get("identity", {}).get("childPathfinderCache") != identity()
        or preparation["identity"].get("outputs") != outputs
        or matching
        != [{"path": TARGET, "before": None, "after": {"kind": "file", "sha256": SHA256}, "purpose": PURPOSE}]
    ):
        raise ValueError("Pathfinder cache preparation lacks exact child-donor and output fingerprints")


def main() -> None:
    evidence = Path(__file__).resolve().parent
    validate(json.loads((evidence / "source-preparation.json").read_text()))
    apply(evidence.parent, containedPath(evidence, ATTACHMENT).read_bytes(), replay=True)


if __name__ == "__main__":
    main()
