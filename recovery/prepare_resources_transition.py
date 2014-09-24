"""Linux build-copy repair for the split Qt resources project."""

import hashlib
from pathlib import Path

COMMITS = ("9843aa0b06bc706fdaeee61f20339c29a9d3a6de",)
PINS = {
    "game/CGameView.cpp": (
        "7b5a6488507d1a46a45ad558d603541516a237a70c18f74ccbbf1b5187dc91c7",
        "3ecb3cb16a0db911dabc522369d68df82598c6ac9b228fda0cab51e434333e38",
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
            (
                b"connect ( player,&CCreature::skillsChanged,scene->getMap()->getGuiHandler(),&CGuiHandler::refresh );",
                b"connect(player, SIGNAL(skillsChanged()), scene->getMap()->getGuiHandler(), SLOT(refresh()));",
            ),
        ],
    ),
    "game/CScriptEngine.cpp": (
        "2349dd540d6dfefc3011726bd3a88fbf6d727a14dcacee0883f6ae37d366201d",
        "263e2828b0a38343092589f048715de6a31a7306c8cbf58ba2fca560bd7cd001",
        [
            (
                b"\t    Py_Finalize(); )",
                b"\t    main_namespace = boost::python::object();\n\t    main_module = boost::python::object();\n\t    Py_Finalize(); )",
            )
        ],
    ),
    "game/CMapObject.cpp": (
        "b30647c71eb7c4f0cd3ccd988cedc4db84df449137aeec0ea994756348c8a8ce",
        "4a8462bec5abd35eb0530366897dceb934536c890a22f1a6b8593ca52d3b9e03",
        [(b"boost::ref ( this )", b"boost::ref ( *this )")],
    ),
    "game/game.pro": (
        "c7c9902a08cfebf4a31f3a5395567826d9122148c9acb58de9ad1abaabe59587",
        "c96fc2305498bcb5e7e109bc75f41b6b025491cdf94d4dbde5adcd78a3fd0599",
        [(b"-L../python -lresources", b"-L../resources -lresources")],
    ),
}
PURPOSE = "Link the split resource library and carry the reviewed Qt and Python build repairs"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    if commit not in COMMITS:
        raise ValueError("Unknown resources transition revision")
    pending = {}
    for name, (before, after, edits) in PINS.items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Resources transition source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Resources transition input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Resources transition output differs from the reviewed revision: {name}")
        pending[path] = updated
    for path, updated in pending.items():
        path.write_bytes(updated)


def identity(commit):
    return {
        "sourceCommit": commit,
        "files": {name: list(entry[:2]) for name, entry in PINS.items()},
        "replaySha256": digest(Path(__file__).read_bytes()),
    }


def validate(commit, preparation):
    if commit not in COMMITS:
        raise ValueError("Unknown resources transition revision")
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
    if preparation.get("identity", {}).get("resourcesTransition") != identity(commit) or actual != rows:
        raise ValueError("Resources transition evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["resourcesTransition"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
