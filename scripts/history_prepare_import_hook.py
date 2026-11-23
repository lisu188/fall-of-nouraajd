"""Linux build-copy repair for the Python 3.4 resource and project transitions."""

import hashlib
from pathlib import Path

_IMPORT_HOOK = {
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
        "5411d923d8acddc06f8ad1a62a680f8bc997accbdb8e778b3705b168595c893b",
        "e7acfd9636ac0617c656e2581009e4f676efff07b33cd36de70d7f7f12741ba8",
        [
            (
                b"\t    Py_Finalize(); )",
                b"\t    main_namespace = boost::python::object();\n\t    main_module = boost::python::object();\n\t    Py_Finalize(); )",
            )
        ],
    ),
    "game/CMapObject.cpp": (
        "c6caca2440285f2076c3f6e04a7f7822ea8d7bb180e9a524546bab78d50a1961",
        "c304cdc03afaa0febbd316874ab74e34073ba23bf4b905800247a2f3b3784be5",
        [(b"boost::ref ( this )", b"boost::ref ( *this )")],
    ),
}

PROFILES = {
    "b18ba43aca75315aeee3f07bd2ca269a0060d1ce": _IMPORT_HOOK,
    "e5b5c9b397541ae896c999ee1810f0f293cf10fa": {
        "game/CGameView.cpp": _IMPORT_HOOK["game/CGameView.cpp"],
        "game/CScriptEngine.cpp": (
            "e843b12bb0260eeefec7582f5f910036a53aabd68426c8d7b4b3a2ada7d489b5",
            "1ea9ed0fb2ec7d3872fa42e7b1d8bda4a3ac0eb7261fc3a7f0ba33bdc381af96",
            _IMPORT_HOOK["game/CScriptEngine.cpp"][2],
        ),
        "game/CMapObject.cpp": _IMPORT_HOOK["game/CMapObject.cpp"],
    },
    "00d9708014417b8142294022d65ec201ccdfa29a": {
        "CGameView.cpp": _IMPORT_HOOK["game/CGameView.cpp"],
        "CScriptEngine.cpp": (
            "e843b12bb0260eeefec7582f5f910036a53aabd68426c8d7b4b3a2ada7d489b5",
            "1ea9ed0fb2ec7d3872fa42e7b1d8bda4a3ac0eb7261fc3a7f0ba33bdc381af96",
            _IMPORT_HOOK["game/CScriptEngine.cpp"][2],
        ),
    },
    "be7f9ca9af9d2f73ab4833a4ef884e71b798eb79": {
        "CGameView.cpp": _IMPORT_HOOK["game/CGameView.cpp"],
        "CScriptEngine.cpp": (
            "e843b12bb0260eeefec7582f5f910036a53aabd68426c8d7b4b3a2ada7d489b5",
            "1ea9ed0fb2ec7d3872fa42e7b1d8bda4a3ac0eb7261fc3a7f0ba33bdc381af96",
            _IMPORT_HOOK["game/CScriptEngine.cpp"][2],
        ),
    },
}
COMMITS = tuple(PROFILES)
PURPOSE = "Carry forward reviewed Qt signal and Python lifetime repairs"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    if commit not in COMMITS:
        raise ValueError("Unknown import hook revision")
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Import hook source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Import hook input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Import hook output differs from the reviewed revision: {name}")
        pending[path] = updated
    for path, updated in pending.items():
        path.write_bytes(updated)


def identity(commit):
    return {
        "sourceCommit": commit,
        "files": {name: list(entry[:2]) for name, entry in PROFILES[commit].items()},
        "replaySha256": digest(Path(__file__).read_bytes()),
    }


def validate(commit, preparation):
    if commit not in COMMITS:
        raise ValueError("Unknown import hook revision")
    rows = [
        {
            "path": name,
            "before": {"kind": "file", "sha256": before},
            "after": {"kind": "file", "sha256": after},
            "purpose": PURPOSE,
        }
        for name, (before, after, _) in sorted(PROFILES[commit].items())
    ]
    actual = [row for row in preparation.get("outputs", []) if row.get("path") in PROFILES[commit]]
    if preparation.get("identity", {}).get("importHook") != identity(commit) or actual != rows:
        raise ValueError("Import hook evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["importHook"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
