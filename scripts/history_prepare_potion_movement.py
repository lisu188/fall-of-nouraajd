"""Pinned Linux build repairs for the scripted potions, movement and player views."""

import hashlib
from pathlib import Path

PROFILES = {
    "a5fc4556044a945e8c88d949177499a9ff7c95de": {
        "CGameView.cpp": (
            "c744328939671011bb8ccf1436c1957f9dfae7bf911e50821fa0de7af5445179",
            "ee71e30959da3274a4b4d9cd307346655962fcc036af0913efd3e7c2680e398a",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CScriptEngine.cpp": (
            "06575b2705261b4b69b3852a6311b633ae506afbbced636a63570971751a23b2",
            "586922933de9b2d73bc3527cf2de0ea6d6473d9ef38180d34d8f0a295f7c2bb3",
            [(b'\tPy_Finalize();', b'\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n\tPy_Finalize();')],
        ),
    },
    "eae1adecf2efe90f29c1b9b4a136c82de041a796": {
        "CGameView.cpp": (
            "2d2e5f25f5470845e72312e4c0c6866523ff0ae455ef01611e36eb3196f73e46",
            "132376c51990a0f49bf7f4b966161f9844be78dfd336a65b914c3feb74d58e7c",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CScriptEngine.cpp": (
            "06575b2705261b4b69b3852a6311b633ae506afbbced636a63570971751a23b2",
            "586922933de9b2d73bc3527cf2de0ea6d6473d9ef38180d34d8f0a295f7c2bb3",
            [(b'\tPy_Finalize();', b'\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n\tPy_Finalize();')],
        ),
    },
    "b544b03385befb58c2f805109ebafecd632cdef0": {
        "CGameView.cpp": (
            "66cf029497fc319eb87200150081041261e9cf674a9d431dd4f9c33a48ce4ec3",
            "706b041b742cd767410d9bc9034d2be26345509d3baa5b3a2989d01c5ddbf11d",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CScriptEngine.cpp": (
            "06575b2705261b4b69b3852a6311b633ae506afbbced636a63570971751a23b2",
            "586922933de9b2d73bc3527cf2de0ea6d6473d9ef38180d34d8f0a295f7c2bb3",
            [(b'\tPy_Finalize();', b'\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n\tPy_Finalize();')],
        ),
    },
}
COMMITS = tuple(PROFILES)
PURPOSE = "Carry forward reviewed Qt signal and Python lifetime repairs"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    if commit not in COMMITS:
        raise ValueError("Unknown potion movement revision")
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Potion movement source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Potion movement input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Potion movement output differs from the reviewed revision: {name}")
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
        raise ValueError("Unknown potion movement revision")
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
    if preparation.get("identity", {}).get("potionMovement") != identity(commit) or actual != rows:
        raise ValueError("Potion movement evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["potionMovement"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
