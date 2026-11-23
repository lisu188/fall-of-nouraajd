#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay the authored manifest correction for one exact original deleted-resource state."""

import hashlib
import json
from pathlib import Path

TARGET = "recovery_maps.qrc"
ATTACHMENT = "maps_manifest.qrc"
ARGUMENTS = ["-after", "RESOURCES-=maps.qrc", "RESOURCES+=$$_PRO_FILE_PWD_/" + TARGET]
BOUNDARY = "Game startup with the authored removal of a deleted trigger resource; original sources unchanged"
INPUTS = {"maps.qrc": "d4ddf84877d2e3ec3214c8609ad16346a79875fe61b0d2c063cfbd35c87b4d46"}
ABSENT_INPUTS = ["maps/map1/trigger.json"]
REMOVED_LINE = b"        <file>maps/map1/trigger.json</file>\n"
OUTPUT_SHA256 = "dcd6a9f30facdd3f9329cf456aa61c66012b803b399607ae88a6fa67834cb3e5"
PROVENANCE = {
    "sourceCommit": "3858af6ada96f937e75eadc42785b9b17d586caf",
    "operation": "Use the authored maps.qrc deletion of only the genuinely absent maps/map1/trigger.json entry",
}


def originalInput(root: Path, name: str) -> bytes | None:
    path = root / name
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
        raise ValueError(f"Maps manifest compatibility input crosses a symlink: {name}")
    if not path.exists():
        return None
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Maps manifest compatibility input is not a contained regular file: {name}")
    return path.read_bytes()


def mapsManifestPlan(root: Path) -> dict | None:
    data = originalInput(root, "maps.qrc")
    if data is None or hashlib.sha256(data).hexdigest() != INPUTS["maps.qrc"]:
        return None
    for name in ABSENT_INPUTS:
        if originalInput(root, name) is not None:
            return None
    if data.count(REMOVED_LINE) != 1:
        raise ValueError("Pinned maps manifest does not have its exact reviewed deleted-resource entry")
    derived = data.replace(REMOVED_LINE, b"", 1)
    if hashlib.sha256(derived).hexdigest() != OUTPUT_SHA256:
        raise ValueError("Derived maps manifest differs from the authored correction")
    return {
        "path": TARGET,
        "sha256": OUTPUT_SHA256,
        "inputs": INPUTS,
        "absentInputs": ABSENT_INPUTS,
        "qmakeArguments": ARGUMENTS,
        "provenance": PROVENANCE,
        "validationBoundary": BOUNDARY,
        "replaySha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "data": derived,
    }


def writeManifest(root: Path, data: bytes) -> bool:
    target = root / TARGET
    if target.is_symlink():
        raise ValueError("Maps manifest compatibility output is symlinked")
    if target.exists():
        if not target.is_file() or target.read_bytes() != data:
            raise ValueError("Maps manifest compatibility output already exists with different bytes")
        return False
    with target.open("xb") as output:
        output.write(data)
    return True


def prepareMapsManifest(root: Path, evidence: Path) -> bool:
    root = root.resolve()
    preparation = json.loads((evidence / "source-preparation.json").read_text())
    compatibility = preparation.get("identity", {}).get("mapsManifest", {})
    plan = mapsManifestPlan(root)
    if preparation.get("status") != "success" or plan is None:
        raise ValueError("Maps manifest compatibility original inputs, absence state, or preparation status differ")
    expected = {key: value for key, value in plan.items() if key != "data"}
    if compatibility != expected or preparation.get("qmakeArguments") != ARGUMENTS:
        raise ValueError("Maps manifest compatibility metadata differs from the reviewed authored correction")
    outputs = preparation.get("outputs", [])
    matching = [entry for entry in outputs if entry.get("path") == TARGET]
    if (
        outputs != preparation.get("identity", {}).get("outputs")
        or len(matching) != 1
        or matching[0].get("before") is not None
        or matching[0].get("after") != {"kind": "file", "sha256": OUTPUT_SHA256}
    ):
        raise ValueError("Maps manifest compatibility derived output fingerprints differ")
    attachment = evidence / ATTACHMENT
    if not attachment.is_file() or attachment.is_symlink() or attachment.read_bytes() != plan["data"]:
        raise ValueError("Maps manifest compatibility attachment differs from its reviewed bytes")
    return writeManifest(root, plan["data"])


def main() -> int:
    evidence = Path(__file__).resolve().parent
    created = prepareMapsManifest(evidence.parent, evidence)
    print("Created maps manifest compatibility" if created else "Verified existing maps manifest compatibility")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
