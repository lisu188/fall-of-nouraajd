#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay explicit build-only completion of an original unfinished refactor with the developer's own next lines."""

import hashlib
import json
from pathlib import Path

# Catalog #224 makes GameScene's player, map and view accessors instance members, but its unchanged monster.cpp,
# playerlistview.cpp and tile.cpp still call them statically, so it cannot compile as committed. #225 rewrites those
# calls and comments out RoadTile, yet tile.cpp's step table still names it, so #225 cannot compile either. #226
# keeps RoadTile with its body commented out. Every replacement below is a block of the developer's own lines from
# the commit it names; only the lines that use the removed static accessors or the missing RoadTile change.
NEXT = "38bba6a98d8a17324de69e30d7eee433da922962"
SETTLED = "e43a91c0533f3ded4b560e92b0d735fc3613e8bf"
ROAD_TILE = "void RoadTile() { /*GameScene::getPlayer()->heal(1); */}"
# The edited files are unchanged from earlier commits that still compile; only together with the scene header that
# made the accessors instance members (identical at #224-#226) do they form the unfinished states.
INSTANCE_SCENE = {"src/gamescene.h": "ed87b8cd8a11e77507546942ea8334cfb117130f028ddc8265cd138afd1d954f"}
CONTEXT = {
    "39356696f34ba87148a75f7ca6b8f808edf6303d": INSTANCE_SCENE,
    "38bba6a98d8a17324de69e30d7eee433da922962": INSTANCE_SCENE,
}
STATES = {
    "39356696f34ba87148a75f7ca6b8f808edf6303d": {
        "src/monster.cpp": {
            "sha256": "feedbb1eef266498fdbf9e25ae9f31fa12ca2847c37fb50d53f9f90f25ae96bc",
            "lines": [
                (
                    "  if ((this->getCoords().getDist(GameScene::getPlayer()->getCoords())) < 25) {",
                    "  if ((this->getCoords().getDist(this->getMap()->getScene()->getPlayer()->getCoords())) < 25) {",
                    NEXT,
                ),
                (
                    "  GameScene::getPlayer()->addToFightList(this);",
                    "  map->getScene()->getPlayer()->addToFightList(this);",
                    NEXT,
                ),
            ],
        },
        "src/playerlistview.cpp": {
            "sha256": "83fe471fe11c1d3e34f5744ed26dfdccb677678e8522b1e234a971054fb7a8b1",
            "lines": [
                (
                    "    if (GameScene::getPlayer() &&\n"
                    "        item->getMap() != GameScene::getPlayer()->getMap()) {\n"
                    "      item->setMap(GameScene::getPlayer()->getMap());\n"
                    "    }\n",
                    "    if (item->getMap()->getScene()->getPlayer()) {\n"
                    "      item->setMap(item->getMap()->getScene()->getPlayer()->getMap());\n"
                    "  }\n",
                    NEXT,
                ),
                (
                    "  item->onUse(GameScene::getPlayer());",
                    "  item->onUse(this->getMap()->getScene()->getPlayer());",
                    NEXT,
                ),
            ],
        },
        "src/tile.cpp": {
            "sha256": "e1e9e10c30b8c739ea6ef2eee58083874151d0ae6df979f0fd8979d93ef7134c",
            "lines": [("void RoadTile() { GameScene::getPlayer()->heal(1); }", ROAD_TILE, SETTLED)],
        },
    },
    NEXT: {
        "src/tile.h": {
            "sha256": "f327e9198eb7eb7d31121bb2128f98b77796656ab302c7de43af7b22f020711f",
            "lines": [("//void RoadTile();", "void RoadTile();", SETTLED)],
        },
        "src/tile.cpp": {
            "sha256": "5c24f4774a8bedf5c5f4b75ba9182fa43455d53b7d645c696fccc450121d0b0b",
            "lines": [("//void RoadTile() { GameScene::getPlayer()->heal(1); }", ROAD_TILE, SETTLED)],
        },
    },
}
PROVENANCE = {
    "operation": (
        "Replace only the lines that still use GameScene's removed static accessors, or that leave RoadTile "
        "undeclared, with the developer's own lines from the commit recorded beside each replacement"
    ),
    "settledCommit": SETTLED,
}
BOUNDARY = (
    "Game startup with build-only completion of an original unfinished refactor using the developer's own lines "
    "from the following commits; original sources unchanged in the snapshot"
)


def originalInput(root: Path, name: str) -> bytes | None:
    path = root / name
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
        raise ValueError(f"Refactor completion input crosses a symlink: {name}")
    if not path.is_file():
        return None
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Refactor completion input escapes the source tree: {name}")
    return path.read_bytes()


def completeLines(original: bytes, lines) -> bytes:
    """Apply each reviewed replacement block, which must occur exactly once in the original."""
    output = original
    for old, new, _source in lines:
        if original.count(old.encode()) != 1 or output.count(old.encode()) != 1:
            raise ValueError("Refactor completion line is not unique in its original file")
        output = output.replace(old.encode(), new.encode(), 1)
    return output


def contextMatches(root: Path, commit: str) -> bool:
    """The unchanged inputs that make this an unfinished state rather than an earlier compiling one."""
    for name, expected in CONTEXT.get(commit, {}).items():
        data = originalInput(root, name)
        if data is None or hashlib.sha256(data).hexdigest() != expected:
            return False
    return True


def refactorLinesPlan(root: Path) -> dict | None:
    """Recognize only the exact pinned original states; replace only the reviewed lines."""
    for commit, files in STATES.items():
        originals = {name: originalInput(root, name) for name in files}
        if any(
            data is None or hashlib.sha256(data).hexdigest() != files[name]["sha256"]
            for name, data in originals.items()
        ) or not contextMatches(root, commit):
            continue
        data = {name: completeLines(originals[name], files[name]["lines"]) for name in sorted(files)}
        return {
            "state": commit,
            "files": {
                name: {
                    "beforeSha256": files[name]["sha256"],
                    "afterSha256": hashlib.sha256(content).hexdigest(),
                    "lines": [list(line) for line in files[name]["lines"]],
                }
                for name, content in data.items()
            },
            "context": dict(CONTEXT.get(commit, {})),
            "provenance": PROVENANCE,
            "validationBoundary": BOUNDARY,
            "replaySha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "data": data,
        }
    return None


def writeCompletions(root: Path, state: str, data: dict[str, bytes]) -> bool:
    files = STATES.get(state, {})
    changed = False
    for name, content in sorted(data.items()):
        if name not in files:
            raise ValueError(f"Unexpected refactor completion output: {name}")
        path = root / name
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
            raise ValueError(f"Refactor completion output crosses a symlink: {name}")
        current = path.read_bytes()
        if current == content:
            continue
        if hashlib.sha256(current).hexdigest() != files[name]["sha256"]:
            raise ValueError(f"Refactor completion target differs from its original bytes: {name}")
        path.write_bytes(content)
        changed = True
    return changed


def prepareRefactorLines(root: Path, evidence: Path) -> bool:
    root = root.resolve()
    preparation = json.loads((evidence / "source-preparation.json").read_text())
    recorded = preparation.get("identity", {}).get("refactorCompletion", {})
    state = recorded.get("state")
    files = STATES.get(state)
    if (
        preparation.get("status") != "success"
        or files is None
        or recorded.get("files", {}).keys() != files.keys()
        or recorded.get("context") != CONTEXT.get(state, {})
        or not contextMatches(root, state)
    ):
        raise ValueError("Refactor completion original inputs or preparation status differ")
    pending = {}
    for name, hashes in recorded["files"].items():
        current = originalInput(root, name)
        digest = hashlib.sha256(current).hexdigest() if current is not None else None
        if digest == hashes.get("afterSha256"):
            continue
        if digest != files[name]["sha256"] or hashes.get("beforeSha256") != files[name]["sha256"]:
            raise ValueError("Refactor completion original inputs or preparation status differ")
        if hashes.get("lines") != [list(line) for line in files[name]["lines"]]:
            raise ValueError("Refactor completion lines differ from the reviewed replacements")
        completed = completeLines(current, files[name]["lines"])
        if hashlib.sha256(completed).hexdigest() != hashes.get("afterSha256"):
            raise ValueError("Refactor completion output differs from its recorded fingerprint")
        pending[name] = completed
    if (
        recorded.get("provenance") != PROVENANCE
        or recorded.get("validationBoundary") != BOUNDARY
        or recorded.get("replaySha256") != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    ):
        raise ValueError("Refactor completion metadata differs from the reviewed provenance")
    return writeCompletions(root, state, pending)


def main() -> int:
    evidence = Path(__file__).resolve().parent
    changed = prepareRefactorLines(evidence.parent, evidence)
    print("Completed the unfinished refactor lines" if changed else "Verified completed refactor lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
