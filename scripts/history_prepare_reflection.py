#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay explicit build-only registration compatibility for one original source state."""

import hashlib
import json
from pathlib import Path

TARGET = "recovery_reflection_registration.h"
ATTACHMENT = "reflection_registration.h"
ARGUMENT = "QMAKE_CXXFLAGS+=-include $$_PRO_FILE_PWD_/" + TARGET
BOUNDARY = "Game startup with immediate-parent reflection registration compatibility; original sources unchanged"
INPUTS = {
    "CReflection.h": "524490e5a60d8bd94d9ff85c95d6e5f2c33d3961daa8430d4b0a7c0d98169035",
    "ReflectTypes.cpp": "96e2d7dde59798f88f1c2d11501d97e83d944e41a74fc5edf0580c9326a73487",
    "handler/CTypeHandler.cpp": "4f97d9857f4e4a21ab825e5077d5ab9d54ca73b6597dfd0aa91067f31506c1dd",
}
PROVENANCE = {
    "sourceCommit": "71ceeb3834f44a22d5683e0eb2a5623c333dbd0f",
    "donorCommit": "ae762f9c3572c5384c143690da32f8364fa39bcc",
    "donorHeaderBlob": "5a2c17e7095979cc8675a8cf5da9fadedc7ba737",
    "operation": "Restore only the immediate-parent REFLECT macro through a compiler forced include",
}
HEADER = (
    "// Build-only compatibility: restore the immediate parent registration macro.\n"
    '#pragma once\n#include "CReflection.h"\n#undef REFLECT\n'
    "#define REFLECT(CLASS) \\\n"
    "Q_DECLARE_METATYPE(CLASS) \\\n"
    "Q_DECLARE_METATYPE(CLASS*) \\\n"
    "CReflectionHelper<CLASS> UNIQUE_NAME(CReflectionHelper##CLASS##BASE) ; \\\n"
    "CReflectionHelper<CLASS*> UNIQUE_NAME(CReflectionHelper##CLASS##POINTER) ; \\\n"
).encode()


def originalInput(root: Path, name: str) -> bytes | None:
    path = root / name
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
        raise ValueError(f"Reflection compatibility input crosses a symlink: {name}")
    if not path.is_file():
        return None
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Reflection compatibility input escapes the source tree: {name}")
    return path.read_bytes()


def reflectionPlan(root: Path) -> dict | None:
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
        raise ValueError("Reflection compatibility output is symlinked")
    if target.exists():
        if not target.is_file() or target.read_bytes() != data:
            raise ValueError("Reflection compatibility output already exists with different bytes")
        return False
    with target.open("xb") as output:
        output.write(data)
    return True


def prepareReflection(root: Path, evidence: Path) -> bool:
    root = root.resolve()
    preparation = json.loads((evidence / "source-preparation.json").read_text())
    compatibility = preparation.get("identity", {}).get("reflectionRegistration", {})
    plan = reflectionPlan(root)
    if preparation.get("status") != "success" or plan is None:
        raise ValueError("Reflection compatibility original inputs or preparation status differ")
    expected = {key: value for key, value in plan.items() if key != "data"}
    if compatibility != expected or preparation.get("qmakeArguments") != [ARGUMENT]:
        raise ValueError("Reflection compatibility metadata differs from the reviewed input hashes and macro")
    outputs = preparation.get("outputs", [])
    matching = [entry for entry in outputs if entry.get("path") == TARGET]
    if (
        outputs != preparation.get("identity", {}).get("outputs")
        or len(matching) != 1
        or matching[0].get("after") != {"kind": "file", "sha256": expected["sha256"]}
    ):
        raise ValueError("Reflection compatibility derived output fingerprints differ")
    attachment = evidence / ATTACHMENT
    if not attachment.is_file() or attachment.is_symlink() or attachment.read_bytes() != HEADER:
        raise ValueError("Reflection compatibility header differs from its reviewed bytes")
    return writeHeader(root, HEADER)


def main() -> int:
    evidence = Path(__file__).resolve().parent
    created = prepareReflection(evidence.parent, evidence)
    print(
        "Created reflection registration compatibility header" if created else "Verified existing compatibility header"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
