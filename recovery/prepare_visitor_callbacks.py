"""Pinned Linux build repairs for the named objects and visitor callbacks."""

import hashlib
from pathlib import Path

PROFILES = {
    "3439d0c4e5572aa51cd1ba324b0e844a9633bc82": {
        "CGameView.cpp": (
            "e4dea2cc362f4efc898f313db765302bc73a3da82f8924317e2af315884489cd",
            "09af51dc2112f684603ecbe347aa4d59b1bc07019df9873d2efceeaa7c4e6209",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CGameScene.cpp": (
            "ebf81a980024bc6be61956698953a8b89776f5c7567a723e24ad3e4fb65e0318",
            "56d51702c432c6d57a1a916e1c50b45a1c6dc15bab2d00519148ce24a03a61d9",
            [(b'CGameScene::~CGameScene() {', b'CGameScene::~CGameScene() {\n\tdelete map;\n\tmap = nullptr;')],
        ),
        "CScriptEngine.cpp": (
            "7b2d4e8bd567e4211ceeb14b29362e24554701e653a9bac0b0f16ff36201910a",
            "99bbe98b12e94cee9b67a59323e01cb1b747a0d827cc863eb08961ffcdc38df3",
            [(b'\tPy_Finalize();', b'\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n\tPy_Finalize();')],
        ),
    },
    "3a87a3a1483b24b496abcd2f849ed45b8ea6e36d": {
        "CGameView.cpp": (
            "f8ba6408ddfaa4fd4e5ab6b981015849dc04080238b7da1fea826fcf49c351ed",
            "bfa3da48e71ea463d4a72e5a939001d20d86d9435e208776f9809c91f8acb395",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CGameScene.cpp": (
            "8c98327a87c8d55bd30c05abd2e2f0c8b6db3789d615600f5740dd17d408b557",
            "c55555aeb7406205132066cf3afe0f425a3b346b921a88b68e431b66f54388d3",
            [(b'CGameScene::~CGameScene() {', b'CGameScene::~CGameScene() {\n\tdelete map;\n\tmap = nullptr;')],
        ),
        "CScriptEngine.cpp": (
            "38fe619e7738ddf7453d15f4ad14f26c97cfbb1bfc0bd181bc8f35567e8e8f00",
            "9a032d901ac3ab7357f07ca279cf324934bec551639f63b7cc407acbccf12a8f",
            [(b'\tPy_Finalize();', b'\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n\tPy_Finalize();')],
        ),
    },
}
PROFILES["86dedc767b8d8012c8b20121feb74a0d4bf810f4"] = PROFILES["3a87a3a1483b24b496abcd2f849ed45b8ea6e36d"]
COMMITS = tuple(PROFILES)
PURPOSE = "Include the map declaration and release map and Python state before their owning runtimes"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    if commit not in COMMITS:
        raise ValueError("Unknown visitor callbacks revision")
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Visitor callbacks source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Visitor callbacks input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Visitor callbacks output differs from the reviewed revision: {name}")
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
        raise ValueError("Unknown visitor callbacks revision")
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
    if preparation.get("identity", {}).get("visitorCallbacks") != identity(commit) or actual != rows:
        raise ValueError("Visitor callbacks evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["visitorCallbacks"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
