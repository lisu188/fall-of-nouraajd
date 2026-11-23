#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay the missing runtime configuration lookups in the two Qt JSON transition commits."""

import hashlib
import json
from pathlib import Path

BOUNDARY = "Game startup with derived legacy configuration paths and default animation timings"
# The digest covers the file names and bytes of the original callers and restored configuration inputs.
INPUT_PINS = {
    "70dc75ede4bbdda080775689a32f1f9edfe75ffa": "f1ff545180ba57aa481906eff2e04c8fbc06abd32135b00557072e5075b89a7c",
    "d1a71d9688c4c1df824ec5b1661a6855e82ba5d9": "db7c16e2a6995c3f2d1656e16d9c02d0a39fa983cea02ca0a6b0697939e3ce94",
}
OUTPUT_PINS = {
    "70dc75ede4bbdda080775689a32f1f9edfe75ffa": "8b8ff22c8b43aae614f3ffdfb09d05b1b6b290fe557e32ae6b513b9a707d8084",
    "d1a71d9688c4c1df824ec5b1661a6855e82ba5d9": "5ac720ee89da6da5cd535aa37c4007e60c7e8636bb915724535bdb315ed912bb",
}
CALLERS = ("src/CConfigurationProvider.cpp", "src/CAnimationProvider.cpp", "src/CBuilding.cpp", "src/CTile.cpp")
TABLES = ("armors", "buildings", "effects", "interactions", "items", "misc", "monsters", "potions", "tiles", "weapons")
# CAnimationProvider appends time.json to each path. An empty array selects its own 250 ms default.
ANIMATIONS = (
    "buildings/cave",
    "buildings/teleporter",
    "items/weapons/chaossword",
    "interactions/chaosblast",
    "players/assasin",
    "interactions/attack",
    "items/potions/life",
    "items/potions/mana",
    "items/weapons/dagger",
    "items/armors/leatherarmor",
    "interactions/sneakattack",
    "arrows/right/",
    "arrows/left/",
    "tiles/grass",
    "tiles/road",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def contained(root, name):
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe configuration path {name}")
    path = root / relative
    if not path.is_relative_to(root) or any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(root)):
        raise ValueError(f"Unsafe configuration path {name}")
    return path


def inputFiles(root):
    names = [*CALLERS, *(f"config/objects/{table}.json" for table in TABLES)]
    return {name: contained(root, name).read_bytes() for name in names}


def plan(root, commit):
    if commit not in INPUT_PINS:
        return None
    files = inputFiles(root)
    pin = digest(encoded({name: digest(data) for name, data in files.items()}))
    if pin != INPUT_PINS[commit]:
        raise ValueError("Runtime configuration inputs differ from the reviewed revision")
    objects = {}
    for table in TABLES:
        values = json.loads(files[f"config/objects/{table}.json"])
        if objects.keys() & values.keys():
            raise ValueError("Duplicate object ID in split configuration tables")
        objects.update(values)
    outputs = {"config/object.json": encoded(objects), "config/tiles.json": files["config/objects/tiles.json"]}
    for animation in ANIMATIONS:
        image = "images/" + animation + ("0.png" if animation.endswith("/") else ".png")
        if not contained(root, image).is_file():
            raise ValueError(f"Missing animation image {image}")
        outputs["images/" + animation + "time.json"] = b"[]\n"
    identity = {
        "sourceCommit": commit,
        "inputsSha256": pin,
        "outputs": {name: digest(data) for name, data in outputs.items()},
        "replaySha256": digest(Path(__file__).read_bytes()),
        "validationBoundary": BOUNDARY,
    }
    validateIdentity(commit, identity)
    return identity, outputs


def validateIdentity(commit, identity):
    if (
        commit not in INPUT_PINS
        or identity.get("sourceCommit") != commit
        or identity.get("inputsSha256") != INPUT_PINS[commit]
        or digest(encoded(identity.get("outputs"))) != OUTPUT_PINS[commit]
        or identity.get("replaySha256") != digest(Path(__file__).read_bytes())
        or identity.get("validationBoundary") != BOUNDARY
    ):
        raise ValueError("Runtime configuration evidence differs from the reviewed revision")


def writeOutputs(root, outputs):
    pending = []
    for name, data in outputs.items():
        path = contained(root, name)
        if path.exists():
            if not path.is_file() or path.read_bytes() != data:
                raise ValueError(f"Runtime configuration would replace existing bytes at {name}")
        else:
            if not path.parent.is_dir():
                raise ValueError(f"Missing runtime configuration directory for {name}")
            pending.append((path, data))
    for path, data in pending:
        with path.open("xb") as stream:
            stream.write(data)


if __name__ == "__main__":
    evidence = Path(__file__).resolve().parent
    report = json.loads((evidence / "verification.json").read_bytes())
    identity, outputs = plan(evidence.parent, report["sourceCommit"])
    if identity != report["runtimeConfiguration"]:
        raise SystemExit("Runtime configuration identity differs from verification")
    writeOutputs(evidence.parent, outputs)
