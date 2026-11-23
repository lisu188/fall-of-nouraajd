"""Release the owned Python handles before interpreter shutdown in the split core."""

import hashlib
import json
from pathlib import Path

COMMITS = (
    "1b30a29102065bad6bd0e3cf4d0d4dd652d856b9",
    "e4a4821fb1ed08fe7f72f63e49748c23390f16ac",
    "c4d43a9f8ddd1980f4b39a659d63c68c6a2de31c",
)
TARGET = "core/src/CScriptEngine.cpp"
ANDROID_COMMIT = "8d5eb7f18f89ff70ea633f463a57b72f46aaf2e4"
TARGETS = {**dict.fromkeys(COMMITS, TARGET), ANDROID_COMMIT: "game/CScriptEngine.cpp"}
INPUT = "782640aad36636a8eeb9eece47ae03e2ae06b18df1e7fbfa1be25940efcb3892"
OUTPUT = "e3c73972358732cb25915b9c734a94dda15934042ac5e77d33c76eba65a690d0"
PURPOSE = "Release Boost.Python module and namespace handles before interpreter finalization"
OLD = b"\t    Py_Finalize(); )"
NEW = b"\t    main_namespace = boost::python::object();\n\t    main_module = boost::python::object();\n\t    Py_Finalize(); )"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(commit):
    return {
        "sourceCommit": commit,
        "inputSha256": INPUT,
        "outputSha256": OUTPUT,
        "replaySha256": digest(Path(__file__).read_bytes()),
    }


def apply(root, commit):
    if commit not in TARGETS:
        raise ValueError("Unreviewed Python shutdown revision")
    target = TARGETS[commit]
    path = root / target
    if path.is_symlink() or path.resolve() != root.resolve() / target:
        raise ValueError("Python shutdown source traverses a symbolic link")
    data = path.read_bytes()
    if digest(data) != INPUT:
        raise ValueError("Python shutdown input differs from the reviewed source")
    result = data.replace(OLD, NEW)
    if digest(result) != OUTPUT:
        raise ValueError("Python shutdown output differs from the reviewed source")
    path.write_bytes(result)


def validate(commit, preparation):
    target = TARGETS.get(commit)
    outputs = [entry for entry in preparation.get("outputs", []) if entry["path"] == target]
    if (
        commit not in TARGETS
        or preparation.get("identity", {}).get("pythonShutdown") != identity(commit)
        or outputs
        != [
            {
                "path": target,
                "before": {"kind": "file", "sha256": INPUT},
                "after": {"kind": "file", "sha256": OUTPUT},
                "purpose": PURPOSE,
            }
        ]
    ):
        raise ValueError("Python shutdown evidence lacks the exact source fingerprints")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    record = json.loads((root / "source-preparation.json").read_bytes())
    commit = record["identity"]["pythonShutdown"]["sourceCommit"]
    validate(commit, record)
    apply(root.parent, commit)
