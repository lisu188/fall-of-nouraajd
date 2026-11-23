"""Linux build-copy repair for the text-panel revision’s Python shutdown."""

import hashlib
from pathlib import Path

COMMIT = "23add7278f50e9ad1c7b232eb7717597ff3ea0ae"
PINS = {
    "game/CScriptEngine.cpp": (
        "aa5c41e293fc0bf1e9356a85c9eeaeac7302736fa365bf038c22ad4f5ae5ccc4",
        "8c5c4c8db69b59b01885200cb87267b5013773ff1cf35dc4f5cffabadcc2e654",
        b"\t    Py_Finalize(); )",
        b"\t    main_namespace = boost::python::object();\n\t    main_module = boost::python::object();\n\t    Py_Finalize(); )",
    )
}
PURPOSE = "Release the owned Python handles before interpreter finalization"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root):
    pending = {}
    for name, (before, after, old, new) in PINS.items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Text-panel shutdown source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Text-panel shutdown input differs from the reviewed revision: {name}")
        updated = data.replace(old, new)
        if digest(updated) != after:
            raise ValueError(f"Text-panel shutdown output differs from the reviewed revision: {name}")
        pending[path] = updated
    for path, updated in pending.items():
        path.write_bytes(updated)


def identity():
    return {
        "sourceCommit": COMMIT,
        "files": {name: list(entry[:2]) for name, entry in PINS.items()},
        "replaySha256": digest(Path(__file__).read_bytes()),
    }


def validate(preparation):
    rows = [
        {
            "path": name,
            "before": {"kind": "file", "sha256": before},
            "after": {"kind": "file", "sha256": after},
            "purpose": PURPOSE,
        }
        for name, (before, after, _, _) in sorted(PINS.items())
    ]
    actual = [row for row in preparation.get("outputs", []) if row.get("path") in PINS]
    if preparation.get("identity", {}).get("textPanelShutdown") != identity() or actual != rows:
        raise ValueError("Text-panel shutdown evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    validate(record)
    apply(evidence.parent)
