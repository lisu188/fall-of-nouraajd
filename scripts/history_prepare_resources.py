#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay the recorded supplemental Qt resource manifest on a separate build copy."""

import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

TARGET = "recovery_supplemental_images.qrc"
ARGUMENT = "RESOURCES+=$$_PRO_FILE_PWD_/" + TARGET
ORIGINALS = {"images.qrc", "animation/animationprovider.cpp", "config/interactions.json"}


def prepareResources(root: Path, evidence: Path) -> bool:
    root = root.resolve()
    preparation = json.loads((evidence / "source-preparation.json").read_text())
    supplement = preparation.get("identity", {}).get("supplementalResources", {})
    if preparation.get("status") != "success" or supplement.get("path") != TARGET:
        raise ValueError("Supplemental Qt resource preparation metadata is absent or unexpected")
    if supplement.get("qmakeArgument") != ARGUMENT:
        raise ValueError("Supplemental Qt resource qmake argument differs from the reviewed literal")
    inputs = supplement.get("inputs", {})
    if not isinstance(inputs, dict) or not ORIGINALS.issubset(inputs):
        raise ValueError("Supplemental Qt resource original input fingerprints are absent")
    images = set(inputs) - ORIGINALS
    if not images or any(not re.fullmatch(r"images/interactions/[a-z0-9]+/0\.png", name) for name in images):
        raise ValueError("Supplemental Qt resource image paths are unexpected")
    for name, expected in inputs.items():
        path = root / name
        if (
            not isinstance(expected, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected)
            or not path.is_file()
            or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents if parent != root)
            or not path.resolve().is_relative_to(root)
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError(f"Supplemental Qt resource input differs from its recorded original: {name}")
    attachment = evidence / "supplemental_images.qrc"
    if not attachment.is_file() or attachment.is_symlink():
        raise ValueError("Supplemental Qt resource attachment is absent or symlinked")
    data = attachment.read_bytes()
    if hashlib.sha256(data).hexdigest() != supplement.get("sha256"):
        raise ValueError("Supplemental Qt resource attachment differs from its verified bytes")
    resource = ET.fromstring(data)
    groups = resource.findall("qresource")
    if (
        resource.tag != "RCC"
        or len(groups) != 1
        or groups[0].attrib != {"prefix": "/"}
        or any(node.tag != "file" or node.attrib for node in groups[0])
        or len(groups[0]) != len(images)
        or {node.text for node in groups[0]} != images
    ):
        raise ValueError("Supplemental Qt resource aliases differ from its pinned image inputs")
    target = root / TARGET
    if target.is_symlink():
        raise ValueError("Supplemental Qt resource output is symlinked")
    if target.exists():
        if not target.is_file() or target.read_bytes() != data:
            raise ValueError("Supplemental Qt resource output already exists with different bytes")
        return False
    with target.open("xb") as output:
        output.write(data)
    return True


def main() -> int:
    evidence = Path(__file__).resolve().parent
    created = prepareResources(evidence.parent, evidence)
    print(
        "Created supplemental Qt resource manifest"
        if created
        else "Verified existing supplemental Qt resource manifest"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
