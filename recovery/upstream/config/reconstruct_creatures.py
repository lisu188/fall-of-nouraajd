#!/usr/bin/env python3
"""Prepare explicitly unverified creature templates from surviving historical data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
NAMES = {
    "assasin": "Assasin",
    "mage": "Mage",
    "rogue": "Rogue",
    "sorcerer": "Sorcerer",
    "warrior": "Warrior",
    "pritz": "Pritz",
    "pritzmage": "PritzMage",
    "octobogz": "OctoBogz",
}
STATS = {
    "strength": 10,
    "stamina": 10,
    "agility": 10,
    "intelligence": 10,
    "armor": 0,
    "block": 0,
    "dmgMin": 1,
    "dmgMax": 3,
    "hit": 75,
    "crit": 5,
    "fireResist": 0,
    "frostResist": 0,
    "thunderResist": 0,
    "normalResist": 0,
    "shadowResist": 0,
    "damage": 0,
    "attack": 0,
    "main": "S",
}


def collectSavedCreatures(value: object) -> dict[str, dict]:
    found = {}
    if isinstance(value, dict):
        for name, instances in value.items():
            if isinstance(instances, list):
                for instance in instances:
                    if isinstance(instance, dict) and "initStats" in instance and "isPlayer" in instance:
                        found[name] = instance
            found.update(collectSavedCreatures(instances))
    elif isinstance(value, list):
        for child in value:
            found.update(collectSavedCreatures(child))
    return found


def buildCreatureConfig(paths: list[str], saved_map: object) -> dict:
    """Preserve saved creature state and fill absent historical templates explicitly."""
    saved = collectSavedCreatures(saved_map)
    result = {}
    species = set()
    for path in paths:
        parts = path.split("/")
        if len(parts) > 3 and parts[0] == "images" and parts[1] in {"players", "monsters"}:
            species.add((parts[1], parts[2]))
    for group, directory in sorted(species):
        if directory not in NAMES:
            raise ValueError("Unrecognized historical creature image directory: " + directory)
        name = NAMES[directory]
        is_player = group == "players"
        stats = dict(STATS)
        if directory in {"mage", "sorcerer", "pritzmage"}:
            stats["main"] = "I"
        elif directory in {"rogue", "assasin"}:
            stats["main"] = "A"
        state = {
            "actions": ["Attack"],
            "coords": {"x": 0, "y": 0, "z": 0},
            "exp": 0,
            "hp": 70,
            "initStats": stats,
            "isPlayer": is_player,
            "level": 1,
            "mana": 70,
            "path": "images/" + group + "/" + directory + "/",
            "sw": 0 if is_player else 2,
        }
        if name in saved:
            state.update(saved[name])
        # The surviving header exposes getLevelStats(); its lost config encoding
        # is unavailable. Keep this inferred progression distinguishable in provenance.
        state["levelStats"] = {
            "strength": 1,
            "stamina": 1,
            "agility": 1,
            "intelligence": 1,
            "dmgMin": 1,
            "dmgMax": 1,
            "hit": 1,
            "crit": 1,
        }
        result[name] = state
    if not result:
        raise ValueError("No historical creature templates can be identified")
    return result


def main() -> None:
    directory = Path(__file__).resolve().parent
    catalog = json.loads((ROOT / "recovery/catalog.json").read_text())
    entries = []
    for tree in catalog["trees"]:
        damaged = [entry for entry in tree["entries"] if entry["path"] == "config/creatures.json"]
        if not damaged:
            continue
        commit = tree["commits"][0]
        paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit], cwd=ROOT, text=True)
        saved_map = {}
        if "config/map.json" in paths.splitlines():
            raw_map = subprocess.check_output(["git", "show", commit + ":config/map.json"], cwd=ROOT)
            try:
                saved_map = json.loads(raw_map)
            except ValueError:
                pass
        payload = (
            json.dumps(buildCreatureConfig(paths.splitlines(), saved_map), indent=4, sort_keys=True) + "\n"
        ).encode()
        checksum = hashlib.sha256(payload).hexdigest()
        name = "creatures-" + checksum[:16] + ".json"
        (directory / name).write_bytes(payload)
        entries.append(
            {
                "tree": tree["tree"],
                "path": "config/creatures.json",
                "source": name,
                "sha256": checksum,
                "provenance": {
                    "kind": "reconstructed-config",
                    "verified": False,
                    "sourceCommit": commit,
                    "evidence": ["historical image directory IDs", "config/map.json saved creature state when present"],
                    "inferred": ["missing initial stats", "levelStats encoding and progression"],
                    "note": "Saved state is retained; absent stats are positive synthetic defaults. Build/startup unverified.",
                },
            }
        )
    (directory / "catalog.json").write_text(json.dumps({"schemaVersion": 1, "entries": entries}, indent=4) + "\n")
    print(json.dumps({"trees": len(entries), "payloads": len({entry["source"] for entry in entries})}))


if __name__ == "__main__":
    main()
