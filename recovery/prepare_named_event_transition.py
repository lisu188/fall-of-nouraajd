"""Linux build-copy repair for the namespaced event revision’s object references and Python shutdown."""

import hashlib
from pathlib import Path

COMMIT = "2f1b611df0ace34f501a30acdf50c0c14282cf0c"
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
        "ee9e9c7481c1671e0deb196a2554548669fc9bcc3f14fd46a5c98e5f88ea00e8",
        "c8f89bc8530c97902f0e90d86a6edc6fd26227d1a02a1ad2893ab79c71a5f94b",
        [
            (
                b"\t    Py_Finalize(); )",
                b"\t    main_namespace = boost::python::object();\n\t    main_module = boost::python::object();\n\t    Py_Finalize(); )",
            )
        ],
    ),
    "game/CMapObject.cpp": (
        "f0006dbd81a5b40f59f4b0f6b0d9d7f4bb4e42b550fefe925b39388af9ce9e84",
        "f8fda33ba86ec6ff8beef27dbf0b1d58f1813eba8896afc47d7cda764f400de5",
        [(b"boost::ref ( this )", b"boost::ref ( *this )")],
    ),
}
PURPOSE = "Connect Qt signals, pass the named event by reference, and release the Python handles"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root):
    pending = {}
    for name, (before, after, edits) in PINS.items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Named event transition source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Named event transition input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Named event transition output differs from the reviewed revision: {name}")
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
    if preparation.get("identity", {}).get("namedEventTransition") != identity() or actual != rows:
        raise ValueError("Named event transition evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    validate(record)
    apply(evidence.parent)
