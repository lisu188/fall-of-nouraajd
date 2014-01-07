#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply only hash-pinned historical include edits to a separate snapshot build copy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


def containedFile(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
        raise ValueError("Include preparation path is not a contained relative path")
    path = root / relative
    if not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError("Include preparation file is absent or escapes the build copy")
    if any(part.is_symlink() for part in [path, *path.parents] if part.is_relative_to(root)):
        raise ValueError("Include preparation cannot traverse symlinks")
    return path


def applyRecordedIncludes(root: Path, preparation: dict) -> list[str]:
    root = root.resolve()
    planned = []
    for entry in preparation.get("identity", {}).get("includeSeparators", []):
        path = containedFile(root, entry["path"])
        before = path.read_bytes()
        for key in ("beforeSha256", "afterSha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", entry.get(key, "")):
                raise ValueError("Include preparation needs explicit source hashes")
        digest = hashlib.sha256(before).hexdigest()
        if digest == entry["afterSha256"]:
            continue
        if digest != entry["beforeSha256"]:
            raise ValueError("Build source differs from its recorded include preimage: " + entry["path"])
        lines = before.splitlines(keepends=True)
        for include in entry["includes"]:
            original = include["originalInclude"]
            prepared = include["preparedInclude"]
            if (
                "\\" not in original
                or prepared != original.replace("\\", "/")
                or prepared.startswith("/")
                or ":" in prepared
            ):
                raise ValueError("Only literal Windows include separators can be prepared")
            header = containedFile(root, include["resolvedHeader"]).resolve()
            candidates = {
                (directory / prepared).resolve()
                for directory in (path.parent, root)
                if (directory / prepared).is_file()
            }
            if candidates != {header}:
                raise ValueError("Recorded include no longer has one contained matching target")
            number = include["line"]
            if not isinstance(number, int) or isinstance(number, bool) or not 1 <= number <= len(lines):
                raise ValueError("Include preparation has an invalid source line")
            pattern = rb'(^[ \t]*#[ \t]*include[ \t]*")' + re.escape(original.encode()) + rb'(")'
            lines[number - 1], count = re.subn(
                pattern, lambda match: match[1] + prepared.encode() + match[2], lines[number - 1], count=1
            )
            if count != 1:
                raise ValueError("Recorded literal include is absent from its original source line")
        after = b"".join(lines)
        if hashlib.sha256(after).hexdigest() != entry["afterSha256"]:
            raise ValueError("Prepared include source differs from its verified postimage")
        planned.append((path, after))
    for path, data in planned:
        path.write_bytes(data)
    return [path.relative_to(root).as_posix() for path, _ in planned]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    preparation = json.loads((root / "recovery/source-preparation.json").read_text(encoding="utf-8"))
    for name in applyRecordedIncludes(root, preparation):
        print("Prepared Windows include separators:", name)


if __name__ == "__main__":
    main()
