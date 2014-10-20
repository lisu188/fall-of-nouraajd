"""Pinned Linux build repairs for the typed event and movement revisions."""

import hashlib
from pathlib import Path

PROFILES = {
    "45e6a749a37b534f9c7edf3df6d536fa0bf3cc9d": {
        "CGameView.cpp": (
            "3c1d43ba889c7cfbc7620956f6600630f9e29457e89dbb318c15dc7565b3e1ec",
            "e59eb1034b607134ee90d56c0af643fc7dafb2d34b11fb7c1188cf3c7a8b19da",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CGameScene.cpp": (
            "abb8f922b177f3eb7c8f5745674dce62a3bd2743a550023b0070102c5b61a06c",
            "094b09f8e9b8630f8a3ed781ee5ab738995bcbc6dae882389a23145f32750219",
            [(b'CGameScene::~CGameScene() {', b'CGameScene::~CGameScene() {\n\tdelete map;\n\tmap = nullptr;')],
        ),
        "CScriptEngine.cpp": (
            "38fe619e7738ddf7453d15f4ad14f26c97cfbb1bfc0bd181bc8f35567e8e8f00",
            "9a032d901ac3ab7357f07ca279cf324934bec551639f63b7cc407acbccf12a8f",
            [(b'\tPy_Finalize();', b'\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n\tPy_Finalize();')],
        ),
        "scripts/game/object.py": (
            "367e026670b6bdbe9f71ed02d5aa3948f76a16149fd67856c546ce907ecd80f8",
            "8ba5ee3cc1fc598ec35c68a1c29f07a996eb33696fe9c8e96300c20291662f4e",
            [(b' and self.getVisitor().isPlayer()', b'')],
        ),
    },
    "34edc762d65df823025750663241ff65fd6c060d": {
        "CGameView.cpp": (
            "3c1d43ba889c7cfbc7620956f6600630f9e29457e89dbb318c15dc7565b3e1ec",
            "e59eb1034b607134ee90d56c0af643fc7dafb2d34b11fb7c1188cf3c7a8b19da",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CGameScene.cpp": (
            "7aab95314daec4f0b7efefecd196704ece62c53abe4cee9bf257b618bfda390e",
            "b3331fd102b90741eb26b75834e9bd193ff7430d4b82b92440c7acc3c0c4f92b",
            [(b'CGameScene::~CGameScene() {', b'CGameScene::~CGameScene() {\n\tdelete map;\n\tmap = nullptr;')],
        ),
        "CScriptEngine.cpp": (
            "38fe619e7738ddf7453d15f4ad14f26c97cfbb1bfc0bd181bc8f35567e8e8f00",
            "9a032d901ac3ab7357f07ca279cf324934bec551639f63b7cc407acbccf12a8f",
            [(b'\tPy_Finalize();', b'\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n\tPy_Finalize();')],
        ),
        "scripts/game/object.py": (
            "367e026670b6bdbe9f71ed02d5aa3948f76a16149fd67856c546ce907ecd80f8",
            "8ba5ee3cc1fc598ec35c68a1c29f07a996eb33696fe9c8e96300c20291662f4e",
            [(b' and self.getVisitor().isPlayer()', b'')],
        ),
    },
    "b26490a1d5564b1e59a32bbd9feee48cbf800ff8": {
        "CGameView.cpp": (
            "3c1d43ba889c7cfbc7620956f6600630f9e29457e89dbb318c15dc7565b3e1ec",
            "e59eb1034b607134ee90d56c0af643fc7dafb2d34b11fb7c1188cf3c7a8b19da",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CGameScene.cpp": (
            "d71895c9b668ad3b616bbeb81995b24fd01b3b24ccda8ad518ca27a27f16ddb6",
            "ac6bb906f168c4265ac4cbed6c9c8782ce316a3b80a9eaee198fcc067ba6343c",
            [(b'CGameScene::~CGameScene() {', b'CGameScene::~CGameScene() {\n\tdelete map;\n\tmap = nullptr;')],
        ),
        "CScriptEngine.cpp": (
            "38fe619e7738ddf7453d15f4ad14f26c97cfbb1bfc0bd181bc8f35567e8e8f00",
            "9a032d901ac3ab7357f07ca279cf324934bec551639f63b7cc407acbccf12a8f",
            [(b'\tPy_Finalize();', b'\tmain_namespace = boost::python::object();\n\tmain_module = boost::python::object();\n\tPy_Finalize();')],
        ),
        "CAnimatedObject.h": (
            "9b9da24e06f101502a7f9edc394859765604d59b7ae85117c5887fae346e366d",
            "522bff353e14c398cf09039342c5fe13262e74eb5f39ebc2e7d580e19c02886e",
            [(b'QString getAnimation();', b'QString getAnimation();\n\tQGraphicsItem *toGraphicsItem() { return this; }')],
        ),
    },
    "a763a6322c2e2d3dc7785ffbb04fc54f1e71c2e3": {
        "CGameView.cpp": (
            "3c1d43ba889c7cfbc7620956f6600630f9e29457e89dbb318c15dc7565b3e1ec",
            "e59eb1034b607134ee90d56c0af643fc7dafb2d34b11fb7c1188cf3c7a8b19da",
            [(b'#include "CGuiHandler.h"', b'#include "CGuiHandler.h"\n#include "CMap.h"')],
        ),
        "CGameScene.cpp": (
            "d71895c9b668ad3b616bbeb81995b24fd01b3b24ccda8ad518ca27a27f16ddb6",
            "ac6bb906f168c4265ac4cbed6c9c8782ce316a3b80a9eaee198fcc067ba6343c",
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
PURPOSE = "Preserve map and Python lifetimes and bridge the surviving event and view interfaces"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(root, commit):
    if commit not in COMMITS:
        raise ValueError("Unknown typed events revision")
    pending = {}
    for name, (before, after, edits) in PROFILES[commit].items():
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name:
            raise ValueError(f"Typed events source traverses a symbolic link: {name}")
        data = path.read_bytes()
        if digest(data) != before:
            raise ValueError(f"Typed events input differs from the reviewed revision: {name}")
        updated = data
        for old, new in edits:
            updated = updated.replace(old, new, 1)
        if digest(updated) != after:
            raise ValueError(f"Typed events output differs from the reviewed revision: {name}")
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
        raise ValueError("Unknown typed events revision")
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
    if preparation.get("identity", {}).get("typedEvents") != identity(commit) or actual != rows:
        raise ValueError("Typed events evidence differs from the pinned original and repaired bytes")


if __name__ == "__main__":
    import json

    evidence = Path(__file__).resolve().parent
    record = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = record["identity"]["typedEvents"]["sourceCommit"]
    validate(commit, record)
    apply(evidence.parent, commit)
