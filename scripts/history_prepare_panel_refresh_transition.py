"""Linux build-copy repair for the refresh signals and event references across the panel revisions."""

import hashlib
from pathlib import Path

COMMON = {
    "game/CGameView.cpp": (
        "7b5a6488507d1a46a45ad558d603541516a237a70c18f74ccbbf1b5187dc91c7",
        "3ecb3cb16a0db911dabc522369d68df82598c6ac9b228fda0cab51e434333e38",
        [
            (b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"'),
            (
                b"connect ( player,&CCreature::inventoryChanged,scene->getMap()->getGuiHandler(),&"
                b"CGuiHandler::refresh );",
                b"connect(player, SIGNAL(inventoryChanged()), scene->getMap()->getGuiHandler(), SL" b"OT(refresh()));",
            ),
            (
                b"connect ( player,&CCreature::equippedChanged,scene->getMap()->getGuiHandler(),&C"
                b"GuiHandler::refresh );",
                b"connect(player, SIGNAL(equippedChanged()), scene->getMap()->getGuiHandler(), SLO" b"T(refresh()));",
            ),
            (
                b"connect ( player,&CCreature::skillsChanged,scene->getMap()->getGuiHandler(),&CGu"
                b"iHandler::refresh );",
                b"connect(player, SIGNAL(skillsChanged()), scene->getMap()->getGuiHandler(), SLOT(" b"refresh()));",
            ),
        ],
    ),
    "game/CMapObject.cpp": (
        "f0006dbd81a5b40f59f4b0f6b0d9d7f4bb4e42b550fefe925b39388af9ce9e84",
        "f8fda33ba86ec6ff8beef27dbf0b1d58f1813eba8896afc47d7cda764f400de5",
        [(b"boost::ref ( this )", b"boost::ref ( *this )")],
    ),
}
FIRST_ENGINE = (
    "ee9e9c7481c1671e0deb196a2554548669fc9bcc3f14fd46a5c98e5f88ea00e8",
    "c8f89bc8530c97902f0e90d86a6edc6fd26227d1a02a1ad2893ab79c71a5f94b",
    [
        (
            b"\t    Py_Finalize(); )",
            b"\t    main_namespace = boost::python::object();\n\t    main_module = boost::python::object();\n\t    Py_Finalize(); )",
        )
    ],
)
LATER_ENGINE = (
    "2349dd540d6dfefc3011726bd3a88fbf6d727a14dcacee0883f6ae37d366201d",
    "263e2828b0a38343092589f048715de6a31a7306c8cbf58ba2fca560bd7cd001",
    [
        (
            b"\t    Py_Finalize(); )",
            b"\t    main_namespace = boost::python::object();\n\t    main_module = boost::python::object();\n\t    Py_Finalize(); )",
        )
    ],
)
PROFILES = {
    "fe01b5980ebbec1a29dc3b2210597e7003ff729f": {**COMMON, "game/CScriptEngine.cpp": FIRST_ENGINE},
    "cd9f1194b608d647a67b040689f48730dfa921e5": {**COMMON, "game/CScriptEngine.cpp": LATER_ENGINE},
    "25124a740fb59242695fb5b477d318b40e7d0121": {**COMMON, "game/CScriptEngine.cpp": LATER_ENGINE},
}
PURPOSE = "Connect Qt signals, pass the named event by reference, and release the Python handles"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Panel refresh transition source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Panel refresh transition input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Panel refresh transition output differs from the reviewed revision: {name}")
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
    if preparation.get("identity", {}).get("panelRefreshTransition") != identity(commit) or actual != rows:
        raise ValueError("Panel refresh transition evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["panelRefreshTransition"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
