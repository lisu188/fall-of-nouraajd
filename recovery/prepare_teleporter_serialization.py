#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare a derived teleporter TU that preserves coordinates and enabled in a JSON object."""

import hashlib
import json
from pathlib import Path
import re

SOURCE = "buildings/teleporter.cpp"
TARGET = "buildings/recovery_teleporter.cpp"
ATTACHMENT = "teleporter_serialization.cpp"
ARGUMENTS = ["-after", "SOURCES-=" + SOURCE, "SOURCES+=$$_PRO_FILE_PWD_/" + TARGET]
BOUNDARY = "Game startup and shutdown with coordinate-and-enabled teleporter serialization compatibility; original sources unchanged"
STATES = [
    {
        "commit": "b4d315b857f8df32b17422f64b381a36f3d90d1d",
        "inputs": {
            "buildings/teleporter.cpp": "317099f84b236b4f32e84d7169d4374d94393a084ac73c4c55f80b2a5f72c7ef",
            "buildings/teleporter.h": "79a3726ec0eaf317770b5d4e2c65d19743658f6b90ca9ba8f6bd06f829491ca8",
            "json/json_value.cpp": "1c1a791ab8542f558b261757999067c82ce36d1d51a55323193b1a884b26f1d4",
        },
        "position": 164,
    },
    {
        "commit": "fb2bcb07e3b2267e7f24c5a7cd48604180b1be0f",
        "inputs": {
            "buildings/teleporter.cpp": "d3a55cfb9105f65e1023fb00569e15b3580075657852a0169dbfb137408cea75",
            "buildings/teleporter.h": "83ba3da4c963f2c2ee135557e4f86dd06621f0a86278eb230b7cf90d03bd4064",
            "json/json_value.cpp": "1c1a791ab8542f558b261757999067c82ce36d1d51a55323193b1a884b26f1d4",
        },
        "position": 175,
    },
    {
        "commit": "7022f82ba68e4b740e85915b1710dd0502837efe",
        "inputs": {
            "buildings/teleporter.cpp": "515e4087e4b9e43301c096ce0af4e271773604f6fbea60a5a8ed593e365e2258",
            "buildings/teleporter.h": "83ba3da4c963f2c2ee135557e4f86dd06621f0a86278eb230b7cf90d03bd4064",
            "json/json_value.cpp": "1c1a791ab8542f558b261757999067c82ce36d1d51a55323193b1a884b26f1d4",
        },
        "position": 176,
    },
    {
        "commit": "b79e759b0babe370c4cee4508ba9c5cb566d9d33",
        "inputs": {
            "buildings/teleporter.cpp": "9ae1cae5155437bf82b045609a46e8ccb20f13a232197ce632661f302b8ef127",
            "buildings/teleporter.h": "44bbca334d314cca3734d12b910759719fc9def89d3c6aded3d89940b203fa6d",
            "json/json_value.cpp": "1c1a791ab8542f558b261757999067c82ce36d1d51a55323193b1a884b26f1d4",
        },
        "position": 178,
    },
]
OUTPUTS = {
    "317099f84b236b4f32e84d7169d4374d94393a084ac73c4c55f80b2a5f72c7ef": "3da78d7450b99710c79aed3d0587f6d00e74a319941ad2ea2f2d0a388c3a3e3e",
    "d3a55cfb9105f65e1023fb00569e15b3580075657852a0169dbfb137408cea75": "46c94b9e354c7fcb43885909fee405f7141ad9e941e065468a826184b88fdd87",
    "515e4087e4b9e43301c096ce0af4e271773604f6fbea60a5a8ed593e365e2258": "a66e5cd0e67bcb00309ee1967b3ce45132c27d6c8611b8baab940e5dd93539d1",
    "9ae1cae5155437bf82b045609a46e8ccb20f13a232197ce632661f302b8ef127": "67cb28924233d74992cbe9bb107043c118afd330c22c6a763747bc2a9417d7cc",
}
SAVE_BODY = """    Json::Value config;
    config["x"] = getPosX();
    config["y"] = getPosY();
    config["z"] = getPosZ();
    config["enabled"] = enabled;
    return config;"""
LOAD_BODY = """    if (config.isArray()) {
        this->moveTo(config[(unsigned int)0].asInt(), config[(unsigned int)1].asInt(),
                     config[(unsigned int)2].asInt(), true);
        return;
    }
    int x = config["x"].asInt();
    int y = config["y"].asInt();
    int z = config["z"].asInt();
    enabled = config["enabled"].asBool();
    this->moveTo(x, y, z, true);"""


def containedPath(root: Path, name: str) -> Path:
    path = root / name
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
        raise ValueError(f"Teleporter compatibility path crosses a symlink: {name}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Teleporter compatibility path escapes the build source: {name}")
    return path


def methodBody(data: bytes, name: str) -> tuple[int, int]:
    pattern = rb"\bTeleporter::" + name.encode() + rb"\s*\([^)]*\)\s*\{"
    matches = list(re.finditer(pattern, data))
    if len(matches) != 1:
        raise ValueError("Pinned teleporter source lacks its unique reviewed method: " + name)
    start = matches[0].end()
    depth = 1
    end = start
    while depth and end < len(data):
        depth += (data[end] == ord("{")) - (data[end] == ord("}"))
        end += 1
    if depth:
        raise ValueError("Pinned teleporter source has an unterminated reviewed method")
    return start, end - 1


def derivedSource(data: bytes) -> bytes:
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    edits = []
    for name, body in [("saveToJson", SAVE_BODY), ("loadFromJson", LOAD_BODY)]:
        start, end = methodBody(data, name)
        edits.append((start, end, newline + body.encode().replace(b"\n", newline) + newline))
    for start, end, replacement in sorted(edits, reverse=True):
        data = data[:start] + replacement + data[end:]
    return data


def reviewedIdentity(inputs: dict) -> dict | None:
    state = next((state for state in STATES if state["inputs"] == inputs), None)
    if state is None:
        return None
    return {
        "path": TARGET,
        "sha256": OUTPUTS[inputs[SOURCE]],
        "inputs": dict(inputs),
        "qmakeArguments": ARGUMENTS,
        "provenance": {
            "sourceCommit": state["commit"],
            "operation": "Replace only Teleporter save/load bodies with inverse JSON object coordinate-and-enabled storage",
            "legacyArrays": "Retain current enabled for legacy coordinate arrays; every reviewed original header initializes it to true",
        },
        "validationBoundary": BOUNDARY,
        "replaySha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def teleporterPlan(root: Path) -> dict | None:
    names = [SOURCE, "buildings/teleporter.h", "json/json_value.cpp"]
    inputs = {}
    data = None
    for name in names:
        path = containedPath(root, name)
        if not path.is_file():
            return None
        payload = path.read_bytes()
        inputs[name] = hashlib.sha256(payload).hexdigest()
        if name == SOURCE:
            data = payload
    identity = reviewedIdentity(inputs)
    if identity is None:
        return None
    derived = derivedSource(data)
    if hashlib.sha256(derived).hexdigest() != identity["sha256"]:
        raise ValueError("Derived teleporter source differs from its reviewed exact method replacement")
    return {**identity, "data": derived}


def writeSource(root: Path, data: bytes) -> bool:
    target = containedPath(root, TARGET)
    if target.exists():
        if not target.is_file() or target.read_bytes() != data:
            raise ValueError("Teleporter compatibility output already exists with different bytes")
        return False
    with target.open("xb") as output:
        output.write(data)
    return True


def prepareTeleporter(root: Path, evidence: Path) -> bool:
    root = root.resolve()
    preparation = json.loads((evidence / "source-preparation.json").read_text())
    plan = teleporterPlan(root)
    if preparation.get("status") != "success" or plan is None:
        raise ValueError(
            "Teleporter compatibility original source, header, JsonCpp inputs or preparation status differ"
        )
    expected = {key: value for key, value in plan.items() if key != "data"}
    if (
        preparation.get("identity", {}).get("teleporterSerialization") != expected
        or preparation.get("qmakeArguments") != ARGUMENTS
    ):
        raise ValueError("Teleporter compatibility metadata differs from its reviewed serialization semantics")
    outputs = preparation.get("outputs", [])
    matching = [entry for entry in outputs if entry.get("path") == TARGET]
    if (
        outputs != preparation.get("identity", {}).get("outputs")
        or len(matching) != 1
        or matching[0].get("before") is not None
        or matching[0].get("after") != {"kind": "file", "sha256": expected["sha256"]}
    ):
        raise ValueError("Teleporter compatibility output fingerprints differ")
    attachment = evidence / ATTACHMENT
    if attachment.is_symlink() or not attachment.is_file() or attachment.read_bytes() != plan["data"]:
        raise ValueError("Teleporter compatibility attachment differs from its reviewed derived source")
    return writeSource(root, plan["data"])


def main() -> int:
    evidence = Path(__file__).resolve().parent
    created = prepareTeleporter(evidence.parent, evidence)
    print("Created teleporter serialization compatibility" if created else "Verified existing teleporter compatibility")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
