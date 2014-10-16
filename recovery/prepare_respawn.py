"""Pinned Linux build repairs for the respawn revisions."""

import hashlib
from pathlib import Path

PROFILES = {
    "6eb12953a0d2c7ec9eebe1ea778b93d93b221f9e": {
        "CGameView.cpp": (
            "3c1d43ba889c7cfbc7620956f6600630f9e29457e89dbb318c15dc7565b3e1ec",
            "e59eb1034b607134ee90d56c0af643fc7dafb2d34b11fb7c1188cf3c7a8b19da",
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
    "d9cc0f0666ba2908f25e4d7a6c45c54e631a9b66": {
        "CGameView.cpp": (
            "3c1d43ba889c7cfbc7620956f6600630f9e29457e89dbb318c15dc7565b3e1ec",
            "e59eb1034b607134ee90d56c0af643fc7dafb2d34b11fb7c1188cf3c7a8b19da",
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
COMMITS = tuple(PROFILES)
PURPOSE = "Include the map declaration and release map and Python state before their owning runtimes"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    if commit not in COMMITS:
        raise ValueError("Unknown respawn revision")
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Respawn source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Respawn input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Respawn output differs from the reviewed revision: {name}")
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
        raise ValueError("Unknown respawn revision")
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
    if preparation.get("identity", {}).get("respawn") != identity(commit) or actual != rows:
        raise ValueError("Respawn evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["respawn"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
