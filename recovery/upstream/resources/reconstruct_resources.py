#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Derive explicitly unverified legacy resources from surviving authored data."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts import recover_history as recovery

MAP_DONOR = "55e6516e"
OBJECT_DONOR = "e8b7c3d0e6da989122a0587943a98504342da3cd"


def addProperties(parent, values):
    if values:
        properties = ET.SubElement(parent, "properties")
        for key, value in sorted(values.items()):
            ET.SubElement(
                properties, "property", name=key, value=str(value).lower() if isinstance(value, bool) else str(value)
            )


def tiledXml(data):
    root = ET.Element(
        "map",
        {
            key: str(data[key])
            for key in ("version", "orientation", "renderorder", "width", "height", "tilewidth", "tileheight")
            if key in data
        },
    )
    addProperties(root, data.get("properties", {}))
    for tileset in data.get("tilesets", []):
        element = ET.SubElement(
            root,
            "tileset",
            {
                key: str(tileset[key])
                for key in ("firstgid", "name", "tilewidth", "tileheight", "spacing", "margin")
                if key in tileset
            },
        )
        if "image" in tileset:
            ET.SubElement(
                element,
                "image",
                source=tileset["image"],
                width=str(tileset["imagewidth"]),
                height=str(tileset["imageheight"]),
            )
        for tile, properties in sorted(tileset.get("tileproperties", {}).items(), key=lambda item: int(item[0])):
            addProperties(ET.SubElement(element, "tile", id=tile), properties)
    for layer in data.get("layers", []):
        attributes = {key: str(layer[key]) for key in ("name", "width", "height", "opacity") if key in layer}
        if layer.get("type") == "tilelayer":
            element = ET.SubElement(root, "layer", attributes)
            contents = ET.SubElement(element, "data")
            for tile in layer["data"]:
                ET.SubElement(contents, "tile", gid=str(tile))
        elif layer.get("type") == "objectgroup":
            element = ET.SubElement(root, "objectgroup", attributes)
            for item in layer.get("objects", []):
                obj = ET.SubElement(
                    element,
                    "object",
                    {
                        key: str(item[key])
                        for key in ("id", "name", "type", "x", "y", "width", "height", "rotation", "gid")
                        if key in item
                    },
                )
                addProperties(obj, item.get("properties", {}))
        else:
            raise recovery.RecoveryError(f"Unsupported historical Tiled layer: {layer.get('type')}")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def flattenPrototype(entry):
    result = copy.deepcopy(entry.get("properties", entry))
    for key in ("class", "handler"):
        if key in entry:
            result[key] = entry[key]
    if "class" in result:
        class_name = result["class"].split(".")[-1]
        if class_name.startswith("C") and len(class_name) > 1 and class_name[1].isupper():
            class_name = class_name[1:]
        result["class"] = class_name
        result["type"] = class_name
    if "animation" in result:
        result["path"] = result["animation"].rstrip("/") + "/"
    return result


def reconstruct(repo_root, catalog, output_dir):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    map_data = json.loads(recovery.gitCommand(repo_root, "show", MAP_DONOR + ":maps/map1/map.json"))
    donor_paths = recovery.gitCommand(repo_root, "ls-tree", "-r", "--name-only", OBJECT_DONOR).decode().splitlines()
    prototypes = {}
    for path in donor_paths:
        if path.startswith("config/objects/") and path.endswith(".json"):
            source = json.loads(recovery.gitCommand(repo_root, "show", OBJECT_DONOR + ":" + path))
            prototypes.update({name: flattenPrototype(entry) for name, entry in source.items()})
    # Species templates retain the documented uncertainty of their separate reconstruction catalog.
    species_catalog = recovery.readJson(Path(repo_root) / "recovery/upstream/config/catalog.json")
    species_entries = {entry["tree"]: entry for entry in species_catalog["entries"]}
    species_fallback = max(
        species_catalog["entries"],
        key=lambda entry: len(recovery.readJson(Path(repo_root) / "recovery/upstream/config" / entry["source"])),
    )
    entries = []
    with recovery.GitObjects(repo_root) as objects:
        for snapshot in catalog["trees"]:
            targets = [
                entry["path"]
                for entry in snapshot["entries"]
                if entry["path"]
                in (
                    "config/object.json",
                    "res/config/object.json",
                    "config/map.tmx",
                    "maps/map.tmx",
                    "res/config/map.tmx",
                )
            ]
            if not targets:
                continue
            files = objects.files(snapshot["tree"])
            for path in targets:
                if path.endswith(".tmx"):
                    source_data = copy.deepcopy(map_data)
                    script = source_data.get("properties", {}).get("script")
                    if script and script not in files:
                        source_data["properties"].pop("script")
                    content = tiledXml(source_data)
                    provenance = (
                        f"unverified donor reconstruction; authored Tiled geometry/object coordinates from "
                        f"{MAP_DONOR}:maps/map1/map.json converted to XML; missing target script reference omitted"
                    )
                    suffix = ".tmx"
                else:
                    data = copy.deepcopy(prototypes)
                    species_entry = species_entries.get(snapshot["tree"], species_fallback)
                    if species_entry:
                        species_path = Path(repo_root) / "recovery/upstream/config" / species_entry["source"]
                        for name, species in recovery.readJson(species_path).items():
                            class_name = "Player" if species.get("isPlayer") else "Monster"
                            data[name] = {**species, "class": class_name, "type": class_name}
                    for candidate in (
                        "config/tiles.json",
                        "res/config/tiles.json",
                        "config/interactions.json",
                        "res/config/interactions.json",
                    ):
                        if candidate in files:
                            local = json.loads(objects.read(files[candidate]["blob"], "blob"))
                            for name, properties in local.items():
                                data[name] = {**data.get(name, {}), **properties}
                    content = (json.dumps(data, sort_keys=True, indent=2) + "\n").encode()
                    provenance = (
                        f"unverified donor reconstruction; split object descriptors {OBJECT_DONOR}:config/objects "
                        "flattened to observed legacy class/path API; target tile/interaction entries preserved; "
                        "species stats retain uncertainty of reconstructed creatures catalog"
                    )
                    suffix = ".json"
                digest = hashlib.sha256(content).hexdigest()
                name = digest + suffix
                (output / name).write_bytes(content)
                entries.append(
                    {"tree": snapshot["tree"], "path": path, "source": name, "sha256": digest, "provenance": provenance}
                )
    recovery.writeJson(output / "catalog.json", {"schemaVersion": 1, "entries": entries, "verified": False})
    return {"entries": len(entries), "payloads": len({entry["source"] for entry in entries}), "verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--catalog", type=Path, default=Path("recovery/catalog.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("recovery/upstream/resources"))
    args = parser.parse_args()
    print(json.dumps(reconstruct(args.repo_root, recovery.readJson(args.catalog), args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
