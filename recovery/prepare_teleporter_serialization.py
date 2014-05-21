#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned #176 teleporter preparation, including its whitespace-only conflict."""

import hashlib
import json
from pathlib import Path

try:
    from scripts import history_prepare_teleporter as original
    from scripts import history_prepare_conflicts as conflicts
except ModuleNotFoundError:
    import history_prepare_teleporter as original
    import history_prepare_conflicts as conflicts

SOURCE = original.SOURCE
TARGET = original.TARGET
ATTACHMENT = original.ATTACHMENT
ARGUMENTS = original.ARGUMENTS
BOUNDARY = original.BOUNDARY
INPUTS = next(state["inputs"] for state in original.STATES if state["position"] == 176)
OUTPUT_SHA256 = "fca4cf9cf0ccceba59a4869a6fdd80a39a8557b4579ed3c2417364ccc608692a"
containedPath = original.containedPath
writeSource = original.writeSource


def reviewedIdentity(inputs: dict) -> dict | None:
    if inputs != INPUTS:
        return None
    identity = original.reviewedIdentity(inputs)
    identity["sha256"] = OUTPUT_SHA256
    identity["provenance"]["whitespaceConflicts"] = "Remove only the original whitespace-equivalent merge conflict from the derived translation unit"
    identity["baseReplaySha256"] = hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest()
    identity["conflictReplaySha256"] = hashlib.sha256(Path(conflicts.__file__).read_bytes()).hexdigest()
    identity["replaySha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return identity


def teleporterPlan(root: Path) -> dict | None:
    plan = original.teleporterPlan(root)
    if plan is None or plan["inputs"] != INPUTS:
        return None
    data = conflicts.resolveConflicts(plan["data"])
    identity = reviewedIdentity(plan["inputs"])
    if hashlib.sha256(data).hexdigest() != OUTPUT_SHA256:
        raise ValueError("Derived #176 teleporter differs from reviewed conflict resolution")
    return {**identity, "data": data}


def prepareTeleporter(root: Path, evidence: Path) -> bool:
    preparation = json.loads((evidence / "source-preparation.json").read_text())
    plan = teleporterPlan(root)
    if preparation.get("status") != "success" or plan is None:
        raise ValueError("#176 teleporter inputs or preparation status differ")
    if preparation.get("identity", {}).get("teleporterSerialization") != {key: value for key, value in plan.items() if key != "data"} or preparation.get("qmakeArguments") != ARGUMENTS:
        raise ValueError("#176 teleporter metadata differs from reviewed semantics")
    outputs = preparation.get("outputs", [])
    matching = [entry for entry in outputs if entry.get("path") == TARGET]
    if outputs != preparation.get("identity", {}).get("outputs") or len(matching) != 1 or matching[0].get("before") is not None or matching[0].get("after") != {"kind": "file", "sha256": OUTPUT_SHA256}:
        raise ValueError("#176 teleporter output fingerprints differ")
    attachment = evidence / ATTACHMENT
    if attachment.is_symlink() or not attachment.is_file() or attachment.read_bytes() != plan["data"]:
        raise ValueError("#176 teleporter attachment differs from reviewed output")
    return writeSource(root, plan["data"])


def main() -> int:
    evidence = Path(__file__).resolve().parent
    print("Prepared #176 teleporter:", prepareTeleporter(evidence.parent, evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
