"""Prepare isolated builds for the three revisions immediately before the jsoncpp repair."""

import hashlib
import json
from pathlib import Path

COMMITS = (
    "6cc78c34d64fdee43adca1b829ccf687daa62ced",
    "8d1b776c2730296dd7f1ed3b3918e83bcb3a4ab6",
    "09df518e2037d12f912da6c774635a91c886c097",
)
DONOR = "d07f08fe3e53a161b193f4d7bf1ebabc3ee59aa9"
COMPANIONS = ("json_internalarray.inl", "json_internalmap.inl", "json_valueiterator.inl")
FORWARDS = {
    "buildings/building.h": ("cave", "dungeon", "teleporter"),
    "items/item.h": ("armor", "belt", "boots", "gloves", "helmet", "smallweapon", "weapon"),
    "pathfinder/pathfinder.h": ("dumbpathfinder", "randompathfinder", "smartpathfinder"),
}
PURPOSE = "Merged-header and jsoncpp compatibility on an isolated build-source copy"
PINS = {
    "09df518e2037d12f912da6c774635a91c886c097": {
        "lib/json/json_value.cpp": "cd68d881764d28c310351545d30c317253bb8e3b032a4bef3db7f29d08c295c2"
    },
    "6cc78c34d64fdee43adca1b829ccf687daa62ced": {
        "lib/json/json_value.cpp": "cd68d881764d28c310351545d30c317253bb8e3b032a4bef3db7f29d08c295c2",
        "src/buildings/building.h": "102b07e24a3f7d4be7fbf31ab900ad7dd886838d6bd20c7f134c496220a07967",
        "src/interactions/interaction.h": "19085596af03c3fd9f6399dc57b43b41d5e627bdca6ba803116a5a77e283c0e7",
        "src/items/item.h": "9c8004f44df254caf6df774149dcd7062c1ef015fd5a0147ef14ad42a092c3db",
        "src/main.cpp": "43c3b43b1ce639f8aba3c524230058b212f85bcef60fcadbb22b2bc2e6a017ff",
        "src/pathfinder/pathfinder.h": "15d65f217389f8961857e43c6ac3f4b28d3f37e66ef76014a3d0617e3deadf64",
    },
    "8d1b776c2730296dd7f1ed3b3918e83bcb3a4ab6": {
        "lib/json/json_value.cpp": "cd68d881764d28c310351545d30c317253bb8e3b032a4bef3db7f29d08c295c2",
        "src/buildings/building.h": "102b07e24a3f7d4be7fbf31ab900ad7dd886838d6bd20c7f134c496220a07967",
        "src/interactions/interaction.h": "19085596af03c3fd9f6399dc57b43b41d5e627bdca6ba803116a5a77e283c0e7",
        "src/items/item.h": "9c8004f44df254caf6df774149dcd7062c1ef015fd5a0147ef14ad42a092c3db",
        "src/main.cpp": "43c3b43b1ce639f8aba3c524230058b212f85bcef60fcadbb22b2bc2e6a017ff",
        "src/map/map.h": "c8116f101a6955bf14e40a0c22408e5321209f25c0682f0399e4bff2e61403cd",
        "src/pathfinder/pathfinder.h": "3455f3b943ce96f8c1d9882742fe1d6d6144ab6e054db963163aaae26b897743",
        "src/stats/stats.h": "462ead5a1e2f69858c6574e13efeb3dcc157d82f48dbf6d7968335f6af0d8bef",
    },
}
DONOR_PINS = {
    "json_internalarray.inl": "1485f419dfb5a1dac1660ce6bfa7eaf86151e729e0c5c7222a993b7a7ee410a1",
    "json_internalmap.inl": "b22ffa1d13f98c2478d4c0c80d7d58fb57c619c7c1c420d846453b593ee0e73c",
    "json_valueiterator.inl": "3de2050b9aa170dfb0ee9caa37e482193bdc6ac140ed21262eba410bbb5d45dc",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def outputs(root, commit, companions):
    if commit not in PINS:
        raise ValueError("Unknown merged-header revision")
    if {name: sha(content) for name, content in companions.items()} != DONOR_PINS:
        raise ValueError("jsoncpp companions differ from the reviewed #183 restoration")
    for name, digest in PINS[commit].items():
        path = root / name
        if path.resolve() != root.resolve() / name or not path.is_file() or sha(path.read_bytes()) != digest:
            raise ValueError(f"Merged-header input differs from the reviewed revision: {name}")
    return generatedOutputs(commit, companions)


def generatedOutputs(commit, companions):
    data = {"lib/json/" + name: companions[name] for name in COMPANIONS}
    if commit in COMMITS[:2]:
        groups = dict(FORWARDS)
        if commit == COMMITS[1]:
            groups["stats/stats.h"] = ("damage",)
            groups["map/map.h"] = ("coords", "playeranimation")
        for target, names in groups.items():
            header = Path(target)
            for name in names:
                data[(Path("src") / header.parent / (name + ".h")).as_posix()] = (
                    '#include "' + header.name + '"\n'
                ).encode()
    if commit in COMMITS[:2]:
        data["src/buildings/cave.h"] += b'#include "../interactions/interaction.h"\n'
    return data


def apply(root, data):
    for name in data:
        path = root / name
        if path.is_symlink() or path.resolve() != root.resolve() / name or path.exists():
            raise ValueError(f"Merged-header output already exists or traverses a symlink: {name}")
    for name, content in data.items():
        with (root / name).open("xb") as stream:
            stream.write(content)


def donorFiles(repo):
    base = repo / "recovery/upstream/libraries/jsoncpp-0.5.0"
    return {name: (base / ("lib__json__" + name)).read_bytes() for name in COMPANIONS}


def identity(commit, data):
    return {
        "sourceCommit": commit,
        "donorCommit": DONOR,
        "inputs": PINS[commit],
        "outputs": {name: sha(content) for name, content in data.items()},
        "replaySha256": sha(Path(__file__).read_bytes()),
    }


def validate(commit, preparation, companions):
    if {name: sha(content) for name, content in companions.items()} != DONOR_PINS:
        raise ValueError("jsoncpp companions differ from the pinned donor")
    data = generatedOutputs(commit, companions)
    if preparation.get("identity", {}).get("mergedHeaders") != identity(commit, data):
        raise ValueError("Merged-header compatibility record differs from the pinned outputs")
    selected = [row for row in preparation["outputs"] if row["path"] in data]
    if len(selected) != len(data) or any(
        row.get("before") is not None
        or row.get("after") != {"kind": "file", "sha256": sha(data[row["path"]])}
        or row.get("purpose") != PURPOSE
        for row in selected
    ):
        raise ValueError("Merged-header compatibility lacks exact output fingerprints")
    return data


if __name__ == "__main__":
    evidence = Path(__file__).resolve().parent
    report = json.loads((evidence / "source-preparation.json").read_bytes())
    commit = report["identity"]["mergedHeaders"]["sourceCommit"]
    companions = {name: (evidence / name).read_bytes() for name in COMPANIONS}
    validate(commit, report, companions)
    apply(evidence.parent, outputs(evidence.parent, commit, companions))
