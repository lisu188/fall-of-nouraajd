"""Linux build-copy repair for the first game panel map and Python shutdown."""

import hashlib
from pathlib import Path

COMMIT = "2017b1ead3293bf0b53bfe1a7b3804310911173b"
PINS = {
    "game/CGameView.cpp": (
        "625e83b50a91a2971071b874cd87bf8ba9cef0d2ad1496071c94dd5f2da14ae0",
        "09ea14b3400bd1372a57c15ba3b8a882b84455bf43322426340b7200c64c8cf3",
        b"AGamePanel *panel=*it;",
        b"AGamePanel *panel=it->second;",
    ),
    "game/CScriptEngine.cpp": (
        "782640aad36636a8eeb9eece47ae03e2ae06b18df1e7fbfa1be25940efcb3892",
        "e3c73972358732cb25915b9c734a94dda15934042ac5e77d33c76eba65a690d0",
        b"\t    Py_Finalize(); )",
        b"\t    main_namespace = boost::python::object();\n\t    main_module = boost::python::object();\n\t    Py_Finalize(); )",
    ),
}
PURPOSE = "Resolve the panel iterator and release the owned Python handles"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root):
    pending = {}
    for name, (before, after, old, new) in PINS.items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Panel transition source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Panel transition input differs from the reviewed revision: {name}")
        updated = data.replace(old, new)
        if digest(updated) != after:
            raise ValueError(f"Panel transition output differs from the reviewed revision: {name}")
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
    if preparation.get("identity", {}).get("panelTransition") != identity() or actual != rows:
        raise ValueError("Panel transition evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    validate(record)
    apply(evidence.parent)
