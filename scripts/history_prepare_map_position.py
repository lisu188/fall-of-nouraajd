"""Disambiguate the graphics position in the authored legacy MapObject."""

import hashlib
import json
from pathlib import Path

COMMIT = "8965c542530e1e58bb2917bf8d6b756735f57561"
TARGET = "map/map.cpp"
INPUT = "58c08222bc273519ec215aa3ccbe3e84c8c09fd98d3dd1ca51d641c638d8b532"
OUTPUT = "bc8eb1b418428a937e9b1e832b474e55912a7438e7f145c8cc984f3731c3dd1d"
PURPOSE = "Resolve the authored position call to QGraphicsItem"
OLD = b"QPointF from = pos();"
NEW = b"QPointF from = QGraphicsItem::pos();"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity():
    return {
        "sourceCommit": COMMIT,
        "inputSha256": INPUT,
        "outputSha256": OUTPUT,
        "replaySha256": digest(Path(__file__).read_bytes()),
    }


def apply(root):
    path = root / TARGET
    if path.is_symlink() or path.resolve() != root.resolve() / TARGET:
        raise ValueError("Map position source traverses a symbolic link")
    data = path.read_bytes()
    if digest(data) != INPUT:
        raise ValueError("Map position differs from the reviewed original")
    repaired = data.replace(OLD, NEW)
    if digest(repaired) != OUTPUT:
        raise ValueError("Map position output differs from the reviewed repair")
    path.write_bytes(repaired)


def validate(preparation):
    rows = [entry for entry in preparation.get("outputs", []) if entry["path"] == TARGET]
    if preparation.get("identity", {}).get("mapPosition") != identity() or rows != [
        {
            "path": TARGET,
            "before": {"kind": "file", "sha256": INPUT},
            "after": {"kind": "file", "sha256": OUTPUT},
            "purpose": PURPOSE,
        }
    ]:
        raise ValueError("Map position preparation is missing the pinned proof")


if __name__ == "__main__":
    evidence = Path(__file__).resolve().parent
    validate(json.loads((evidence / "source-preparation.json").read_bytes()))
    apply(evidence.parent)
