"""Linux build-copy repairs for two incomplete scene and tile transitions."""

import hashlib
from pathlib import Path

SCENE = "39356696f34ba87148a75f7ca6b8f808edf6303d"
TILE = "38bba6a98d8a17324de69e30d7eee433da922962"
EDITS = {
    SCENE: {
        "src/tile.cpp": (
            (b"std::function<void()>", b"std::function<void(Map *)>"),
            (b"steps[typeName]();", b"steps[typeName](map);"),
            (
                b"void RoadTile() { GameScene::getPlayer()->heal(1); }",
                b"void RoadTile(Map *map) { if (map && map->getScene()->getPlayer()) map->getScene()->getPlayer()->heal(1); }",
            ),
        ),
        "src/tile.h": (
            (b"std::function<void()>", b"std::function<void(Map *)>"),
            (b"void RoadTile();", b"void RoadTile(Map *map);"),
        ),
        "src/monster.cpp": ((b"GameScene::getPlayer()", b"getMap()->getScene()->getPlayer()"),),
        "src/playerlistview.cpp": (
            (
                b"    if (GameScene::getPlayer() &&",
                b"    GameScene *activeScene = qobject_cast<GameScene *>(scene());\n    if (activeScene && activeScene->getPlayer() &&",
            ),
            (b"GameScene::getPlayer()", b"activeScene->getPlayer()"),
            (
                b"  item->onUse(activeScene->getPlayer());",
                b"  GameScene *activeScene = qobject_cast<GameScene *>(scene());\n  if (activeScene && activeScene->getPlayer()) {\n    item->onUse(activeScene->getPlayer());\n  }",
            ),
        ),
    },
    TILE: {
        "src/tile.cpp": (
            (
                b"//void RoadTile() { GameScene::getPlayer()->heal(1); }",
                b"void RoadTile() { /*GameScene::getPlayer()->heal(1); */}",
            ),
        ),
        "src/tile.h": ((b"//void RoadTile();", b"void RoadTile();"),),
    },
}
PINS = {
    "38bba6a98d8a17324de69e30d7eee433da922962": {
        "src/tile.cpp": (
            "5c24f4774a8bedf5c5f4b75ba9182fa43455d53b7d645c696fccc450121d0b0b",
            "4a61d762057e14592f99037eeea2bae9fd67b94d35f6b79bee8306630452de13",
        ),
        "src/tile.h": (
            "f327e9198eb7eb7d31121bb2128f98b77796656ab302c7de43af7b22f020711f",
            "302f8e20585fcef72032b0596f349702dbf33f43d99d0f045100cfd9a96af844",
        ),
    },
    "39356696f34ba87148a75f7ca6b8f808edf6303d": {
        "src/monster.cpp": (
            "feedbb1eef266498fdbf9e25ae9f31fa12ca2847c37fb50d53f9f90f25ae96bc",
            "8e79abbf2a8a14c56ffef1e0ede9356afab0cd46fb81dd3a651bb668b78f4b27",
        ),
        "src/playerlistview.cpp": (
            "83fe471fe11c1d3e34f5744ed26dfdccb677678e8522b1e234a971054fb7a8b1",
            "8a810437fb2b205c820c8e4520827b59ab894ab61d928c61fceb81ff36deffc8",
        ),
        "src/tile.cpp": (
            "e1e9e10c30b8c739ea6ef2eee58083874151d0ae6df979f0fd8979d93ef7134c",
            "0b08bf394ca299e2d81dbc3e91c0ed94cfa78bb89be98c03bf14324e990f0056",
        ),
        "src/tile.h": (
            "302f8e20585fcef72032b0596f349702dbf33f43d99d0f045100cfd9a96af844",
            "3da739c8a7c74a4442529931dcda128c0f2729c44b6e993a6f53e6235a8b1400",
        ),
    },
}
PURPOSE = "Refresh surviving call sites for the instance scene or restore the authored RoadTile no-op"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rewrite(commit, name, data):
    for before, after in EDITS[commit][name]:
        if before not in data:
            raise ValueError(f"Reviewed transition pattern missing from {name}")
        data = data.replace(before, after)
    return data


def apply(root, commit):
    pending = {}
    for name, (before, after) in PINS[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Scene transition source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Scene transition input differs from the reviewed revision: {name}")
        updated = rewrite(commit, name, data)
        if digest(updated) != after:
            raise ValueError(f"Scene transition output differs from the reviewed revision: {name}")
        pending[path] = updated
    for path, updated in pending.items():
        path.write_bytes(updated)


def validate(commit, preparation):
    expected = {
        "sourceCommit": commit,
        "files": {name: list(hashes) for name, hashes in PINS[commit].items()},
        "replaySha256": digest(Path(__file__).read_bytes()),
    }
    rows = [
        {
            "path": name,
            "before": {"kind": "file", "sha256": before},
            "after": {"kind": "file", "sha256": after},
            "purpose": PURPOSE,
        }
        for name, (before, after) in sorted(PINS[commit].items())
    ]
    actual = [row for row in preparation.get("outputs", []) if row.get("path") in PINS[commit]]
    if preparation.get("identity", {}).get("sceneTransition") != expected or actual != rows:
        raise ValueError("Scene transition evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["sceneTransition"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
