"""Pinned Linux build repairs for the class-based combat and creature-aware events."""

import hashlib
from pathlib import Path

PROFILES = {
    "30f2226a11e58b114692d6990323f26af5646e58": {
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
    "8c67b6c5800deaa0bd6b95d636e4e9de72b80490": {
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
PROFILES["471be57fbbd86d75c56133e610a1f28bb68446bb"] = PROFILES["8c67b6c5800deaa0bd6b95d636e4e9de72b80490"]
COMMITS = tuple(PROFILES)
PURPOSE = "Carry forward reviewed Qt signal and Python lifetime repairs"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    if commit not in COMMITS:
        raise ValueError("Unknown creature events revision")
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Creature events source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Creature events input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Creature events output differs from the reviewed revision: {name}")
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
        raise ValueError("Unknown creature events revision")
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
    if preparation.get("identity", {}).get("creatureEvents") != identity(commit) or actual != rows:
        raise ValueError("Creature events evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["creatureEvents"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
