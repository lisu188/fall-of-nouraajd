#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve only reviewed whitespace-equivalent conflicts in a private build copy."""

import hashlib
import json
from pathlib import Path
import re

BOUNDARY = "Build with exact-pinned whitespace-only conflict resolution on an isolated source copy"
FILES = {
    "animation/animatedobject.h": (
        "7e85d1dcb2ebed205c5c6aaeff309284812c0176ce0a798e87075f7c85ab1c9d",
        "1085453e4e5b77f6d4cf6bd99ae0422fb49d1784d1fc8114256cbc33f51cbcd6",
    ),
    "animation/animationprovider.h": (
        "f84f275c7e63b50c87509e960dc6e72146b7fcb64bfc5e67097b2ef184239cc9",
        "08ad22e3814f5d3dd0a8c5fe1b4ca53cb9a2e91cc02136e0011e8ef653bee22e",
    ),
    "destroyer/destroyer.h": (
        "5cec48d3ab0a473cd2562c63a26e82f3e39455216fed13f93da57f69a6166ab8",
        "75acda2316c0db4e342d950ca14d7190425db85c94822e892df3216be7a61bee",
    ),
    "items/belt.cpp": (
        "8ed17c91e7cea1165dbf4e9a30ab4a54159df4f328bcaffa0b4a61bd8f3ab6e9",
        "858972734e993f14e0e3ee44ba6b076f139349149c2a45f704a7eae251a99157",
    ),
    "tmx/TmxPropertySet.cpp": (
        "f9b5e40641fc9f2694a918925061c739947a8eadad65c2c82ff25666c3f027d4",
        "db778ffa4e04790d5ef6f06385952f0782a1cb56801dd99426e2869009c92351",
    ),
}
CONFLICT = re.compile(
    rb"^<<<<<<< HEAD\r?\n(.*?)^=======\r?\n(.*?)^>>>>>>> refs/remotes/origin/master(?:\r?\n|$)",
    re.MULTILINE | re.DOTALL,
)


def resolveConflicts(data: bytes) -> bytes:
    def replacement(match):
        left, right = match.groups()
        if re.sub(rb"\s+", b"", left) != re.sub(rb"\s+", b"", right):
            raise ValueError("Conflict alternatives differ beyond whitespace")
        return left

    result, count = CONFLICT.subn(replacement, data)
    if not count or re.search(rb"^(?:<<<<<<<|=======|>>>>>>>)", result, re.MULTILINE):
        raise ValueError("Conflict is absent, malformed or nested")
    return result


def containedFile(root: Path, name: str) -> Path:
    path = root / name
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
        raise ValueError("Conflict preparation path crosses a symlink: " + name)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Conflict preparation path escapes the build copy: " + name)
    return path


def reviewedIdentity() -> dict:
    return {
        "files": {name: {"beforeSha256": before, "afterSha256": after} for name, (before, after) in FILES.items()},
        "provenance": {
            "sourceCommit": "7022f82ba68e4b740e85915b1710dd0502837efe",
            "operation": "Retain HEAD alternatives only after exact input pins and whitespace-equivalence checks",
            "originals": "Original Git inputs remain unchanged; only the isolated build copy is prepared",
        },
        "validationBoundary": BOUNDARY,
        "replaySha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def conflictPlan(root: Path, allow_prepared: bool = False) -> dict | None:
    outputs = {}
    for name, (before, after) in FILES.items():
        path = containedFile(root, name)
        if not path.is_file():
            return None
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if allow_prepared and digest == after:
            outputs[name] = data
            continue
        if digest != before:
            return None
        resolved = resolveConflicts(data)
        if hashlib.sha256(resolved).hexdigest() != after:
            raise ValueError("Conflict resolution differs from the exact reviewed output")
        outputs[name] = resolved
    return {**reviewedIdentity(), "data": outputs}


def writeSources(root: Path, outputs: dict[str, bytes]) -> int:
    planned = []
    for name, data in outputs.items():
        if name not in FILES or hashlib.sha256(data).hexdigest() != FILES[name][1]:
            raise ValueError("Unexpected conflict preparation output")
        path = containedFile(root, name)
        current = hashlib.sha256(path.read_bytes()).hexdigest()
        if current not in FILES[name]:
            raise ValueError("Conflict preparation source changed before writing")
        if current != FILES[name][1]:
            planned.append((path, data))
    for path, data in planned:
        path.write_bytes(data)
    return len(planned)


def validatePreparation(preparation: dict) -> None:
    if preparation.get("status") != "success" or preparation.get("identity", {}).get("trivialConflicts") != reviewedIdentity():
        raise ValueError("Conflict preparation metadata differs from reviewed semantics")
    outputs = preparation.get("outputs", [])
    if outputs != preparation.get("identity", {}).get("outputs"):
        raise ValueError("Conflict preparation output fingerprints differ")
    for name, (before, after) in FILES.items():
        matching = [entry for entry in outputs if entry.get("path") == name]
        if len(matching) != 1 or matching[0].get("before") != {"kind": "file", "sha256": before} or matching[0].get("after") != {"kind": "file", "sha256": after}:
            raise ValueError("Conflict preparation lacks its exact before/after fingerprint")


def prepareConflicts(root: Path, evidence: Path) -> int:
    preparation = json.loads((evidence / "source-preparation.json").read_text())
    validatePreparation(preparation)
    plan = conflictPlan(root, allow_prepared=True)
    if plan is None:
        raise ValueError("Conflict preparation source differs from exact reviewed inputs")
    return writeSources(root, plan["data"])


def main() -> int:
    evidence = Path(__file__).resolve().parent
    print("Prepared", prepareConflicts(evidence.parent, evidence), "whitespace-only conflict files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
