"""Linux build-copy repair for the sparse-map revision’s Qt signals and Python shutdown."""

import hashlib
from pathlib import Path

COMMIT = "75d178f1ac4574316543e76af9234f93e38ead59"
PINS = {
    "game/CGameView.cpp": (
        "cb3371692cb0419b57061490fc5639fc2c78ffbb32a6a2672c7f18bd80526e89",
        "0f936e9a2211aa8b4f5256b8946bddc398dafbc9cd7543031a88ede88c5ac5c9",
        [
            (b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"'),
            (
                b"connect ( player,&CCreature::inventoryChanged,scene->getMap()->getGuiHandler(),&CGuiHandler::refresh );",
                b"connect(player, SIGNAL(inventoryChanged()), scene->getMap()->getGuiHandler(), SLOT(refresh()));",
            ),
            (
                b"connect ( player,&CCreature::equippedChanged,scene->getMap()->getGuiHandler(),&CGuiHandler::refresh );",
                b"connect(player, SIGNAL(equippedChanged()), scene->getMap()->getGuiHandler(), SLOT(refresh()));",
            ),
        ],
    ),
    "game/CScriptEngine.cpp": (
        "68bdf4ba92f9c2b4f11ad495710b9231e71a48781f63b1835ccb76616b37c028",
        "af9b8465718b0584004328ae277f53dabbc6119c996b268e2dc82c4506722f3e",
        [
            (
                b"\t    Py_Finalize(); )",
                b"\t    main_namespace = boost::python::object();\n\t    main_module = boost::python::object();\n\t    Py_Finalize(); )",
            )
        ],
    ),
}
PURPOSE = "Connect surviving Qt signals and release Python handles before finalization"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root):
    pending = {}
    for name, (before, after, edits) in PINS.items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Sparse map transition source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Sparse map transition input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Sparse map transition output differs from the reviewed revision: {name}")
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
        for name, (before, after, _) in sorted(PINS.items())
    ]
    actual = [row for row in preparation.get("outputs", []) if row.get("path") in PINS]
    if preparation.get("identity", {}).get("sparseMapTransition") != identity() or actual != rows:
        raise ValueError("Sparse map transition evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    validate(record)
    apply(evidence.parent)
