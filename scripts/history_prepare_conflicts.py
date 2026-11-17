#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay explicit build-only resolution of original whitespace-only merge-conflict hunks."""

import base64
import hashlib
import json
from pathlib import Path
import re

# Catalog #176 and #177 were committed with unresolved merge-conflict markers in seven files. In every hunk the
# HEAD and origin/master sides differ only in whitespace (two formattings of the same code); at #176 the
# origin/master side reproduces the parent commit's file byte for byte. #178 ("rebase") resolves them.
INPUTS = {
    "animation/animatedobject.h": "7e85d1dcb2ebed205c5c6aaeff309284812c0176ce0a798e87075f7c85ab1c9d",
    "animation/animationprovider.h": "f84f275c7e63b50c87509e960dc6e72146b7fcb64bfc5e67097b2ef184239cc9",
    "buildings/teleporter.cpp": "515e4087e4b9e43301c096ce0af4e271773604f6fbea60a5a8ed593e365e2258",
    "config/tiles.json": "6353c5dd320c88cda0dd685a1cdbeefed4ba9b2743788a030392549bf362011d",
    "destroyer/destroyer.h": "5cec48d3ab0a473cd2562c63a26e82f3e39455216fed13f93da57f69a6166ab8",
    "items/belt.cpp": "8ed17c91e7cea1165dbf4e9a30ab4a54159df4f328bcaffa0b4a61bd8f3ab6e9",
    "tmx/TmxPropertySet.cpp": "f9b5e40641fc9f2694a918925061c739947a8eadad65c2c82ff25666c3f027d4",
}
SIDE = "refs/remotes/origin/master"
# #176 also omitted pathfinder/pathfindercache.cpp, which its headers declare and #177 ("cache") adds two minutes
# later without changing the project. Where the file is absent it is supplied with #177's exact bytes.
SUPPLIED_PATH = "pathfinder/pathfindercache.cpp"
SUPPLIED_SHA256 = "21621e8fa9f86452560abf98530a3bd094691e8d59a53ba9da10fb92b5dd3f92"
SUPPLIED_COMMIT = "779fb803ff021de5e74ed3b24d7c31a9adcaa236"
SUPPLIED = base64.b64decode(
    "I2luY2x1ZGUgInBhdGhmaW5kZXJjYWNoZS5oIgojaW5jbHVkZSA8UURlYnVnPgoKUGF0aEZpbmRlckNhY2hlOjpQYXRoRmluZGVy"
    "Q2FjaGUoKSB7Cn0KClBhdGhGaW5kZXJDYWNoZSAmUGF0aEZpbmRlckNhY2hlOjpnZXRJbnN0YW5jZSgpIHsKICAgIHN0YXRpYyBQ"
    "YXRoRmluZGVyQ2FjaGUgICAgaW5zdGFuY2U7CiAgICByZXR1cm4gaW5zdGFuY2U7Cn0KCnZvaWQgUGF0aEZpbmRlckNhY2hlOjpz"
    "ZXRQYXRoKHN0ZDo6dmVjdG9yPENlbGw+IHBhdGgpIHsKCXRoaXMtPnBhdGggPSBwYXRoOwogICAgcURlYnVnKCk8PCJTZXR0aW5n"
    "IHBhdGggaW4gY2FjaGUuIjsKICAgIGZvcihpbnQgaT0wO2k8cGF0aC5zaXplKCk7aSsrKXsKICAgICAgICBxRGVidWcoKTw8cGF0"
    "aC5hdChpKS54PDxwYXRoLmF0KGkpLnk7CiAgICB9Cn0KCnN0ZDo6dmVjdG9yPENlbGw+IFBhdGhGaW5kZXJDYWNoZTo6Z2V0UGF0"
    "aCgpIHsKCXJldHVybiBwYXRoOwp9CgpDZWxsOjpDZWxsKGludCB4LCBpbnQgeSwgQ29vcmRzIGdvYWwpCgkJOiB4KHgpLCB5KHkp"
    "LCBnb2FsKGdvYWwpIHsKfQoKYm9vbCBDZWxsQ29tcGFyZTo6b3BlcmF0b3IoKShjb25zdCBDZWxsICZhLCBjb25zdCBDZWxsICZi"
    "KSB7CglpbnQgZGlzdGEgPSBzcXJ0KAoJICAgICAgICAoYS54IC0gYS5nb2FsLngpICogKGEueCAtIGEuZ29hbC54KQoJICAgICAg"
    "ICAgICAgICAgICsgKGEueSAtIGEuZ29hbC55KSAqIChhLnkgLSBhLmdvYWwueSkpOwoJaW50IGRpc3RiID0gc3FydCgKCSAgICAg"
    "ICAgKGIueCAtIGIuZ29hbC54KSAqIChiLnggLSBiLmdvYWwueCkKCSAgICAgICAgICAgICAgICArIChiLnkgLSBiLmdvYWwueSkg"
    "KiAoYi55IC0gYi5nb2FsLnkpKTsKCWlmIChkaXN0YSAhPSBkaXN0YikKCQlyZXR1cm4gZGlzdGEgPCBkaXN0YjsKCWlmIChhLngg"
    "IT0gYi54KQoJCXJldHVybiBhLnggPCBiLng7CglyZXR1cm4gYS55IDwgYi55Owp9Cg=="
)
PROVENANCE = {
    "sourceCommits": [
        "7022f82ba68e4b740e85915b1710dd0502837efe",
        "779fb803ff021de5e74ed3b24d7c31a9adcaa236",
    ],
    "parentCommit": "fb2bcb07e3b2267e7f24c5a7cd48604180b1be0f",
    "resolutionCommit": "b79e759b0babe370c4cee4508ba9c5cb566d9d33",
    "operation": (
        "Keep the origin/master side of each committed conflict hunk; every hunk's sides differ only in "
        "whitespace, and at the first affected commit that side equals the parent commit's file"
    ),
}
BOUNDARY = (
    "Game startup with build-only resolution of original whitespace-only merge-conflict hunks and, where the "
    "commit omitted it, the following commit's pathfindercache.cpp; original sources unchanged in the snapshot"
)
START, MIDDLE, END = b"<<<<<<< ", b"=======", b">>>>>>> "


def resolveConflicts(data: bytes) -> bytes | None:
    """Return the origin/master resolution, or None unless every hunk is a whitespace-only conflict."""
    lines = data.split(b"\n")
    output, ours, theirs, state, hunks = [], [], [], 0, 0
    for line in lines:
        stripped = line.rstrip(b"\r")
        if state == 0 and line.startswith(START):
            state, ours, theirs = 1, [], []
        elif state == 1 and stripped == MIDDLE:
            state = 2
        elif state == 2 and line.startswith(END):
            if stripped[len(END) :].decode("utf-8", "replace") != SIDE:
                return None
            if re.sub(rb"\s+", b"", b"\n".join(ours)) != re.sub(rb"\s+", b"", b"\n".join(theirs)):
                return None
            output.extend(theirs)
            state, hunks = 0, hunks + 1
        elif state == 1:
            ours.append(line)
        elif state == 2:
            theirs.append(line)
        elif line.startswith((START, END)) or stripped == MIDDLE:
            return None
        else:
            output.append(line)
    if state != 0 or hunks == 0:
        return None
    return b"\n".join(output)


def originalInput(root: Path, name: str) -> bytes | None:
    path = root / name
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
        raise ValueError(f"Conflict resolution input crosses a symlink: {name}")
    if not path.is_file():
        return None
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Conflict resolution input escapes the source tree: {name}")
    return path.read_bytes()


def conflictResolutionPlan(root: Path) -> dict | None:
    """Recognize only the exact original conflicted files; resolve each whitespace-only hunk."""
    data = {}
    for name, expected in INPUTS.items():
        original = originalInput(root, name)
        if original is None or hashlib.sha256(original).hexdigest() != expected:
            return None
        resolved = resolveConflicts(original)
        if resolved is None:
            raise ValueError(f"Conflict resolution input has a non-whitespace hunk: {name}")
        data[name] = resolved
    if hashlib.sha256(SUPPLIED).hexdigest() != SUPPLIED_SHA256:
        raise ValueError("Embedded following-commit source differs from its pinned bytes")
    supplied = {}
    existing = originalInput(root, SUPPLIED_PATH)
    if existing is None:
        supplied = {SUPPLIED_PATH: {"sha256": SUPPLIED_SHA256, "sourceCommit": SUPPLIED_COMMIT}}
    elif hashlib.sha256(existing).hexdigest() != SUPPLIED_SHA256:
        return None
    return {
        "files": {
            name: {"beforeSha256": INPUTS[name], "afterSha256": hashlib.sha256(content).hexdigest()}
            for name, content in sorted(data.items())
        },
        "supplied": supplied,
        "side": SIDE,
        "provenance": PROVENANCE,
        "validationBoundary": BOUNDARY,
        "replaySha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "data": {**data, **({SUPPLIED_PATH: SUPPLIED} if supplied else {})},
    }


def writeResolutions(root: Path, data: dict[str, bytes]) -> bool:
    changed = False
    for name, content in sorted(data.items()):
        if name not in INPUTS and not (name == SUPPLIED_PATH and content == SUPPLIED):
            raise ValueError(f"Unexpected conflict resolution output: {name}")
        path = root / name
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
            raise ValueError(f"Conflict resolution output crosses a symlink: {name}")
        if name == SUPPLIED_PATH:
            if path.exists():
                if not path.is_file() or path.read_bytes() != content:
                    raise ValueError(f"Supplied following-commit source already differs: {name}")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as output:
                output.write(content)
            changed = True
            continue
        current = path.read_bytes()
        if current == content:
            continue
        if hashlib.sha256(current).hexdigest() != INPUTS[name]:
            raise ValueError(f"Conflict resolution target differs from its original bytes: {name}")
        path.write_bytes(content)
        changed = True
    return changed


def prepareConflictResolution(root: Path, evidence: Path) -> bool:
    root = root.resolve()
    preparation = json.loads((evidence / "source-preparation.json").read_text())
    recorded = preparation.get("identity", {}).get("conflictResolution", {})
    if preparation.get("status") != "success" or recorded.get("files", {}).keys() != INPUTS.keys():
        raise ValueError("Conflict resolution original inputs or preparation status differ")
    pending = {}
    for name, hashes in recorded["files"].items():
        current = originalInput(root, name)
        digest = hashlib.sha256(current).hexdigest() if current is not None else None
        if digest == hashes.get("afterSha256"):
            continue
        if digest != INPUTS[name] or hashes.get("beforeSha256") != INPUTS[name]:
            raise ValueError("Conflict resolution original inputs or preparation status differ")
        resolved = resolveConflicts(current)
        if resolved is None or hashlib.sha256(resolved).hexdigest() != hashes.get("afterSha256"):
            raise ValueError("Conflict resolution output differs from its recorded fingerprint")
        pending[name] = resolved
    supplied = recorded.get("supplied")
    if supplied not in ({}, {SUPPLIED_PATH: {"sha256": SUPPLIED_SHA256, "sourceCommit": SUPPLIED_COMMIT}}):
        raise ValueError("Conflict resolution supplied-source metadata differs from the reviewed file")
    if supplied:
        pending[SUPPLIED_PATH] = SUPPLIED
    expected = {key: value for key, value in recorded.items() if key not in ("files", "supplied", "replaySha256")}
    if expected != {
        "side": SIDE,
        "provenance": PROVENANCE,
        "validationBoundary": BOUNDARY,
    } or recorded.get("replaySha256") != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError("Conflict resolution metadata differs from the reviewed side and provenance")
    return writeResolutions(root, pending)


def main() -> int:
    evidence = Path(__file__).resolve().parent
    changed = prepareConflictResolution(evidence.parent, evidence)
    print("Resolved original conflict hunks" if changed else "Verified existing conflict resolutions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
