"""Pinned Linux build repairs for the Python map event classes and native resource loader."""

import hashlib
from pathlib import Path

PROFILES = {
    "77581ebb8c9133ed56b11e6ecf6d5a10980f73e4": {
        "CGameView.cpp": (
            "c744328939671011bb8ccf1436c1957f9dfae7bf911e50821fa0de7af5445179",
            "ee71e30959da3274a4b4d9cd307346655962fcc036af0913efd3e7c2680e398a",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CScriptEngine.cpp": (
            "71c9a49ddfea3c0672b126e42237f8015f6aca95ec0a0269a98704d7f6733387",
            "947c7de492cd9b4d2ae8a0cbe6a2c7cd0fca606106bf159684816ff6e84ee438",
            [(b'\tPy_Finalize();', b'\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n\tPy_Finalize();')],
        ),
    },
    "104edb40b2c18764b57630d15a6e1c12630752da": {
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
}
COMMITS = tuple(PROFILES)
PURPOSE = "Carry forward reviewed Qt signal and Python lifetime repairs"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    if commit not in COMMITS:
        raise ValueError("Unknown class loader revision")
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Class loader source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Class loader input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Class loader output differs from the reviewed revision: {name}")
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
        raise ValueError("Unknown class loader revision")
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
    if preparation.get("identity", {}).get("classLoaders") != identity(commit) or actual != rows:
        raise ValueError("Class loader evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["classLoaders"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
