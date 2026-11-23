"""Keep the annotated trigger class available under its authored module name."""

import hashlib
import json
from pathlib import Path

COMMIT = "4c0be0149008787ff79b4479307f1945b28c9507"
TARGET = "scripts/game/__init__.py"
INPUT = "d33fbe171fadebafc6c54b8c74e3ba2e9b8f949beb1669149598a9bd62f89b06"
OUTPUT = "17b426746455720c21e236e156e8fd7e28323a387451c277d36abd8a09510fcf"
PURPOSE = "Preserve the class returned by the historical trigger decorator"
OLD = b"    registerType(tr.__name__,tr)"
NEW = b"    registerType(tr.__name__,tr)\n    return tr"


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
        raise ValueError("Trigger decorator source traverses a symbolic link")
    data = path.read_bytes()
    if digest(data) != INPUT:
        raise ValueError("Trigger decorator differs from the reviewed original")
    repaired = data.replace(OLD, NEW)
    if digest(repaired) != OUTPUT:
        raise ValueError("Trigger decorator output differs from the reviewed repair")
    path.write_bytes(repaired)


def validate(preparation):
    rows = [entry for entry in preparation.get("outputs", []) if entry["path"] == TARGET]
    if preparation.get("identity", {}).get("triggerDecorator") != identity() or rows != [
        {
            "path": TARGET,
            "before": {"kind": "file", "sha256": INPUT},
            "after": {"kind": "file", "sha256": OUTPUT},
            "purpose": PURPOSE,
        }
    ]:
        raise ValueError("Trigger decorator preparation is missing the pinned proof")


if __name__ == "__main__":
    evidence = Path(__file__).resolve().parent
    validate(json.loads((evidence / "source-preparation.json").read_bytes()))
    apply(evidence.parent)
