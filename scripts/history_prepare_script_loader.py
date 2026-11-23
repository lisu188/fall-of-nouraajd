"""Linux build-copy repair for the first Qt resource-backed Python script loader."""

import hashlib
from pathlib import Path

COMMITS = ("161a04cd7a7b4e57e4170b925f32dfd5d14ee66c",)
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
        "ce79f69a05e6fcb3506c31b7b7dbda0b624f11085f937d481018eab75009fe9b",
        "aa2b7d401ce1ccbd2a4e58e0d7252c863acce034bcc26666b9aedd9f57a2d921",
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
        "7a99b7631f1fd9498e317088154beeede88e83e4c78909563b6e2f4463dd8958",
        "7c6e26f13b6cacdaaaff7ff41799239cfac9f9c446c492bf7fa4ffa37bfe3713",
        [(b"-L../python -lresources", b"-L../resources -lresources")],
    ),
}
PURPOSE = "Link the split resource library and carry the reviewed Qt and Python build repairs"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    if commit not in COMMITS:
        raise ValueError("Unknown script loader revision")
    pending = {}
    for name, (before, after, edits) in PINS.items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Script loader source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Script loader input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Script loader output differs from the reviewed revision: {name}")
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
        raise ValueError("Unknown script loader revision")
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
    if preparation.get("identity", {}).get("scriptLoader") != identity(commit) or actual != rows:
        raise ValueError("Script loader evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["scriptLoader"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
