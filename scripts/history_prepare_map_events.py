"""Pinned Linux build repairs for the per-map event and effect revisions."""

import hashlib
from pathlib import Path

PROFILES = {
    "18f71340e6334db61d3abc88ac99ac118270d7d1": {
        "CGameView.cpp": (
            "c744328939671011bb8ccf1436c1957f9dfae7bf911e50821fa0de7af5445179",
            "ee71e30959da3274a4b4d9cd307346655962fcc036af0913efd3e7c2680e398a",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CMapObject.cpp": (
            "838224d0724159cc00909b40efafffb973df431faad7e828f552b60967eefacd",
            "ae4640b87bbffdacb222c05b460d5d4f0b0faba069d87f5dd8b61a595441fec1",
            [(b'boost::ref ( this )', b'boost::ref ( *this )')],
        ),
        "CScriptEngine.cpp": (
            "616b0b87aff45eeea0531d88f31f08bf218e5f0bd6312299cc3d8282f6279f1b",
            "274b4aa0b9f8102926e9ec4835a130810e39e37bc3f4e5bacc15f05e6e6a8e88",
            [(b'\t    Py_Finalize();', b'\t    main_namespace = boost::python::object();\n\t    main_module = boost::python::object();\n\t    Py_Finalize();')],
        ),
    },
    "712b84e04439d96e4baeb4a9b739895370185682": {
        "CGameView.cpp": (
            "c744328939671011bb8ccf1436c1957f9dfae7bf911e50821fa0de7af5445179",
            "ee71e30959da3274a4b4d9cd307346655962fcc036af0913efd3e7c2680e398a",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CMapObject.cpp": (
            "fbea8ea978946da128f53e36d9421d219463c9e7a2a8accc71eeb287399a594d",
            "099d65a949fc5bba49acf49e7d557d276873b9425e957c85b0b4b30460676b8d",
            [(b'boost::ref ( this )', b'boost::ref ( *this )')],
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
        raise ValueError("Unknown map event revision")
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Map event source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Map event input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Map event output differs from the reviewed revision: {name}")
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
        raise ValueError("Unknown map event revision")
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
    if preparation.get("identity", {}).get("mapEvents") != identity(commit) or actual != rows:
        raise ValueError("Map event evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["mapEvents"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
