"""Pinned Linux build repairs for the first Python effect subclasses."""

import hashlib
from pathlib import Path

PROFILES = {
    "9968ca5001e0a5844399ae8c2a2134c9798ce039": {
        "CGameView.cpp": (
            "c744328939671011bb8ccf1436c1957f9dfae7bf911e50821fa0de7af5445179",
            "ee71e30959da3274a4b4d9cd307346655962fcc036af0913efd3e7c2680e398a",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CScriptEngine.cpp": (
            "0b0052b4d226433d983f8746ca714c0eb42ccb5d92b3f64ee1e56fe951882267",
            "557009619927f7fae3b0e850cad460411d63d58ec8b7976c9c8462ee85029719",
            [(b'\tPy_Finalize();', b'\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n\tPy_Finalize();')],
        ),
    },
    "58259116b3208867a11fdc532caa0c8b8afd5be7": {
        "CGameView.cpp": (
            "c744328939671011bb8ccf1436c1957f9dfae7bf911e50821fa0de7af5445179",
            "ee71e30959da3274a4b4d9cd307346655962fcc036af0913efd3e7c2680e398a",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CScriptEngine.cpp": (
            "0b0052b4d226433d983f8746ca714c0eb42ccb5d92b3f64ee1e56fe951882267",
            "557009619927f7fae3b0e850cad460411d63d58ec8b7976c9c8462ee85029719",
            [(b'\tPy_Finalize();', b'\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n\tPy_Finalize();')],
        ),
    },
    "559ead9db96da50ae2e451d4c15fc0eb9985aa8f": {
        "CGameView.cpp": (
            "c744328939671011bb8ccf1436c1957f9dfae7bf911e50821fa0de7af5445179",
            "ee71e30959da3274a4b4d9cd307346655962fcc036af0913efd3e7c2680e398a",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CScriptEngine.cpp": (
            "0b0052b4d226433d983f8746ca714c0eb42ccb5d92b3f64ee1e56fe951882267",
            "557009619927f7fae3b0e850cad460411d63d58ec8b7976c9c8462ee85029719",
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
        raise ValueError("Unknown Python effect revision")
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Python effect source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Python effect input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Python effect output differs from the reviewed revision: {name}")
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
        raise ValueError("Unknown Python effect revision")
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
    if preparation.get("identity", {}).get("pythonEffects") != identity(commit) or actual != rows:
        raise ValueError("Python effect evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["pythonEffects"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
