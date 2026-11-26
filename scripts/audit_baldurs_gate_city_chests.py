#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Record chest indices in the exact base ARE files used by the city source fixture."""

import argparse
import hashlib
import json
from pathlib import Path

try:
    from scripts.audit_candlekeep_source import Binary, ResourceIndex
except ModuleNotFoundError:
    from audit_candlekeep_source import Binary, ResourceIndex

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
OUTPUT = FIXTURES / "baldurs_gate_city_chests.json"


def areaChests(data, area):
    fingerprint = hashlib.sha256(data).hexdigest()
    if fingerprint != area["sha256"]:
        raise ValueError("ARE fingerprint differs from the city source fixture")
    reader = Binary(data)
    reader.signature(b"AREAV1.0", 0x11C)
    count = reader.number(0x74, "H")
    if count != len(area["containers"]):
        raise ValueError("ARE container count differs from the city source fixture")
    chests = []
    for index, offset in enumerate(reader.table(reader.number(0x70), count, 0xC0)):
        expected = area["containers"][index]
        position = [reader.number(offset + 0x20, "H"), reader.number(offset + 0x22, "H")]
        if reader.text(offset, 32) != expected["name"] or position != expected["position"]:
            raise ValueError("ARE container identity differs from the city source fixture")
        if reader.number(offset + 0x24, "H") == 2:
            chests.append(index + 1)
    return {"sha256": fingerprint, "containerCount": count, "chestIndices": chests}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = json.loads((FIXTURES / "baldurs_gate_city_source.json").read_text(encoding="utf-8"))
    index = ResourceIndex(args.game_root)
    areas = {
        code: areaChests(index.read(code, "ARE", view="base")[0], area)
        for code, area in sorted(source["areas"].items())
    }
    result = {
        "sourceEdition": "Installed BG1EE base archives",
        "originalParityEstablished": False,
        "areas": areas,
    }
    if args.check:
        return int(result != json.loads(args.output.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
