#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only, bounded Infinity Engine source audit; proprietary text stays in local output.

Format authority: https://gibberlings3.github.io/iesdp/file_formats/ie_formats/
This is a structural inventory, not an Infinity Engine interpreter or parity certificate.
"""

import argparse
from collections import Counter, deque
import hashlib
import gzip
import json
from pathlib import Path
import re
import struct
import sys

RESOURCE_TYPES = {
    1: "BMP",
    1000: "BAM",
    1001: "WED",
    1002: "CHU",
    1003: "TIS",
    1004: "MOS",
    1005: "ITM",
    1006: "SPL",
    1007: "BCS",
    1008: "IDS",
    1009: "CRE",
    1010: "ARE",
    1011: "DLG",
    1012: "2DA",
    1013: "GAM",
    1014: "STO",
    1015: "WMP",
    1016: "EFF",
    1017: "BS",
}
TYPE_CODES = {value: key for key, value in RESOURCE_TYPES.items()}
PROLOGUE_AREAS = frozenset({"AR2600", "AR2602", "AR2605", "AR2606", "AR2607", "AR2616", "AR2617", "AR2618", "AR2643"})
EXTERNAL_SCRIPTS = {
    "CH1CUT02": "road ambush after the Candlekeep departure handoff",
    "CUTSKIP1": "Enhanced Edition generic skip controller branches into other chapters",
}
MAX_RESOURCE_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 1000000
NONE_REFS = {"", "NONE", "*"}
CITY_EXTERIORS = {
    "AR0100": "Northwest ward",
    "AR0200": "North ward",
    "AR0300": "Northeast ward",
    "AR0600": "West ward",
    "AR0700": "Central ward",
    "AR0800": "East ward",
    "AR1100": "Southwest ward",
    "AR1200": "Docks ward",
    "AR1300": "Southeast ward",
}
CITY_UNDERGROUND = {
    "AR0112": "Undercellar",
    "AR0123": "Undercity",
    "AR0125": "Temple finale",
    "AR0146": "Thieves' Maze",
    "AR0224": "West sewers",
    "AR0225": "Central sewers",
    "AR0226": "East sewers",
}
# Explicit membership: checked city ARE-region graph and IESDP's BG1 area catalogue.
# Prefixes alone do not establish inclusion or authenticate original-edition contents.
CITY_AREA_IDS = frozenset(
    """AR0002 AR0004 AR0005 AR0006 AR0007 AR0008 AR0009 AR0010 AR0011 AR0012 AR0013 AR0014 AR0015 AR0016
    AR0017 AR0018 AR0019 AR0020 AR0021 AR0100 AR0101 AR0102 AR0103 AR0104 AR0105 AR0106 AR0107 AR0108
    AR0109 AR0110 AR0111 AR0112 AR0114 AR0115 AR0116 AR0117 AR0118 AR0119 AR0120 AR0121 AR0123 AR0125
    AR0126 AR0127 AR0128 AR0129 AR0130 AR0131 AR0132 AR0133 AR0134 AR0135 AR0136 AR0137 AR0138 AR0139
    AR0140 AR0141 AR0142 AR0143 AR0144 AR0145 AR0146 AR0148 AR0149 AR0150 AR0151 AR0152 AR0153 AR0154
    AR0155 AR0156 AR0157 AR0158 AR0159 AR0160 AR0161 AR0162 AR0163 AR0164 AR0165 AR0166 AR0167 AR0168
    AR0169 AR0170 AR0171 AR0200 AR0224 AR0225 AR0226 AR0300 AR0302 AR0303 AR0304 AR0305 AR0306 AR0307
    AR0308 AR0600 AR0601 AR0602 AR0603 AR0606 AR0607 AR0608 AR0609 AR0611 AR0612 AR0613 AR0614 AR0615
    AR0616 AR0617 AR0618 AR0619 AR0620 AR0621 AR0700 AR0702 AR0703 AR0704 AR0705 AR0706 AR0707 AR0708
    AR0709 AR0710 AR0711 AR0712 AR0713 AR0714 AR0715 AR0716 AR0717 AR0718 AR0719 AR0720 AR0721 AR0722
    AR0723 AR0724 AR0725 AR0726 AR0800 AR0801 AR0802 AR0803 AR0804 AR0805 AR0806 AR0807 AR0808 AR0809
    AR0810 AR0811 AR0812 AR0813 AR0814 AR1100 AR1101 AR1102 AR1103 AR1104 AR1105 AR1106 AR1107 AR1108
    AR1109 AR1110 AR1111 AR1112 AR1113 AR1114 AR1115 AR1116 AR1117 AR1200 AR1201 AR1202 AR1203 AR1204
    AR1205 AR1206 AR1207 AR1208 AR1209 AR1210 AR1211 AR1212 AR1213 AR1214 AR1215 AR1300 AR1301 AR1302
    AR1303 AR1304 AR1305 AR1306 AR1307 AR1308 AR1309 AR1310 AR1311 AR1312 AR1313 AR1314 AR1315 AR1316
    AR1317 AR1320""".split()
)
CITY_BOUNDARIES = {"AR0900": "Wyrm's Crossing is outside the selected playable city scope"}
SEARCH_MAP_BLOCKED = frozenset({0, 8, 10, 12, 13, 14})


class AuditError(ValueError):
    """Unsupported or malformed input, never silently interpreted as an empty resource."""


class Binary:
    def __init__(self, data):
        self.data = data

    def span(self, offset, size):
        if offset < 0 or size < 0 or offset > len(self.data) or size > len(self.data) - offset:
            raise AuditError(f"out-of-bounds span offset={offset} size={size} length={len(self.data)}")
        return self.data[offset : offset + size]

    def number(self, offset, kind="I"):
        return struct.unpack("<" + kind, self.span(offset, struct.calcsize("<" + kind)))[0]

    def text(self, offset, size=8):
        return self.span(offset, size).split(b"\0", 1)[0].decode("ascii", errors="strict").strip()

    def ref(self, offset):
        return self.text(offset).upper()

    def table(self, offset, count, stride):
        if count > MAX_RECORDS:
            raise AuditError(f"excessive record count: {count}")
        self.span(offset, count * stride)
        return range(offset, offset + count * stride, stride)

    def signature(self, expected, minimum):
        self.span(0, minimum)
        if self.span(0, 8) != expected:
            raise AuditError(f"unsupported signature/version {self.span(0, 8)!r}; expected {expected!r}")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def hashFile(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safePath(root, relative):
    parts = relative.replace("\\", "/").split("/")
    if any(part == ".." for part in parts) or Path(relative).is_absolute() or ":" in relative:
        raise AuditError(f"unsafe resource path {relative!r}")
    candidate = root.joinpath(*parts).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise AuditError(f"resource path escapes game root: {relative!r}")
    if not candidate.exists():
        # Original installations often contain uppercase KEY paths on case-sensitive filesystems.
        candidate = root
        for part in parts:
            matches = [entry for entry in candidate.iterdir() if entry.name.casefold() == part.casefold()]
            if len(matches) != 1:
                raise AuditError(f"missing or ambiguous resource path {relative!r}")
            candidate = matches[0]
        candidate = candidate.resolve()
        if not candidate.is_relative_to(root.resolve()):
            raise AuditError(f"resource path escapes game root: {relative!r}")
    return candidate


class ResourceIndex:
    """Index KEY and only the file tables of BIFFs actually used; seek individual payloads."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.key_path = safePath(self.root, "chitin.key")
        data = self.key_path.read_bytes()
        reader = Binary(data)
        reader.signature(b"KEY V1  ", 24)
        self.key_hash = sha256(data)
        self.biffs = []
        for offset in reader.table(reader.number(16), reader.number(8), 12):
            name = reader.text(reader.number(offset + 4), reader.number(offset + 8, "H"))
            self.biffs.append({"path": name, "declared_size": reader.number(offset)})
        self.entries = {}
        self.duplicates = []
        for offset in reader.table(reader.number(20), reader.number(12), 14):
            ext = RESOURCE_TYPES.get(reader.number(offset + 8, "H"))
            if ext:
                key = (reader.ref(offset), ext)
                if key in self.entries:
                    self.duplicates.append(".".join(key))
                self.entries[key] = reader.number(offset + 10)
        self.overrides = {}
        override_dir = self.root / "override"
        if override_dir.is_dir():
            for path in sorted(override_dir.iterdir()):
                if path.is_file():
                    if not path.resolve().is_relative_to(self.root):
                        raise AuditError(f"override escapes game root: {path.name}")
                    self.overrides[(path.stem.upper(), path.suffix[1:].upper())] = path
        self.biff_tables = {}
        self.biff_evidence = {}

    def has(self, name, ext, view="effective"):
        key = (name.upper(), ext)
        return key in self.entries or (view == "effective" and key in self.overrides)

    def read(self, name, ext, view="effective"):
        key = (name.upper(), ext)
        if view == "effective" and key in self.overrides:
            path = self.overrides[key]
            size = path.stat().st_size
            if size > MAX_RESOURCE_BYTES:
                raise AuditError(f"oversized override {path.name}: {size}")
            return path.read_bytes(), {"source": "override", "path": str(path.relative_to(self.root))}
        if key not in self.entries:
            raise AuditError(f"missing {view} resource {name}.{ext}")
        locator = self.entries[key]
        biff_index = locator >> 20
        if biff_index >= len(self.biffs):
            raise AuditError(f"invalid BIFF index {biff_index} for {name}.{ext}")
        if biff_index not in self.biff_tables:
            descriptor = self.biffs[biff_index]
            path = safePath(self.root, descriptor["path"])
            size = path.stat().st_size
            with path.open("rb") as stream:
                header = Binary(stream.read(20))
                header.signature(b"BIFFV1  ", 20)
                count = header.number(8)
                offset = header.number(16)
                if count > MAX_RECORDS or offset > size or count * 16 > size - offset:
                    raise AuditError(f"invalid BIFF table {descriptor['path']}")
                stream.seek(offset)
                table = Binary(stream.read(count * 16))
                entries = {}
                for position in table.table(0, count, 16):
                    entry = (table.number(position + 4), table.number(position + 8))
                    if entry[0] > size or entry[1] > size - entry[0]:
                        raise AuditError(f"BIFF payload outside archive {descriptor['path']}")
                    entries[(table.number(position) & 0x3FFF, table.number(position + 12, "H"))] = entry
                self.biff_tables[biff_index] = (path, entries)
                self.biff_evidence[descriptor["path"]] = {
                    "size": size,
                    "header_and_file_table_sha256": sha256(header.data + table.data),
                    "whole_archive_hashed": False,
                }
        path, entries = self.biff_tables[biff_index]
        location = entries.get((locator & 0x3FFF, TYPE_CODES[ext]))
        if location is None:
            raise AuditError(f"KEY/BIFF locator mismatch for {name}.{ext}")
        offset, size = location
        if size > MAX_RESOURCE_BYTES:
            raise AuditError(f"oversized resource {name}.{ext}: {size}")
        with path.open("rb") as stream:
            stream.seek(offset)
            data = stream.read(size)
        if len(data) != size:
            raise AuditError(f"truncated resource {name}.{ext}")
        return data, {
            "source": "key_biff",
            "path": str(path.relative_to(self.root)),
            "offset": offset,
            "size": size,
            "locator": locator,
        }


class TalkTable:
    def __init__(self, path, encoding="utf-8"):
        self.path = Path(path)
        self.encoding = encoding
        self.size = self.path.stat().st_size
        with self.path.open("rb") as stream:
            header = Binary(stream.read(18))
        header.signature(b"TLK V1  ", 18)
        self.count = header.number(10)
        self.offset = header.number(14)
        if (
            self.count > MAX_RECORDS
            or 18 + self.count * 26 > self.size
            or not 18 + self.count * 26 <= self.offset <= self.size
        ):
            raise AuditError("invalid TLK table")
        self.cache = {}
        self.errors = []

    def get(self, strref):
        if strref in (-1, 0xFFFFFFFF):
            return None
        if strref in self.cache:
            return self.cache[strref]
        if not 0 <= strref < self.count:
            self.errors.append({"strref": strref, "error": "outside TLK table"})
            return {"strref": strref, "unresolved": True}
        with self.path.open("rb") as stream:
            stream.seek(18 + strref * 26)
            entry = Binary(stream.read(26))
            offset, length = entry.number(18), entry.number(22)
            if (
                length > MAX_RESOURCE_BYTES
                or self.offset + offset > self.size
                or length > self.size - self.offset - offset
            ):
                raise AuditError(f"TLK string {strref} outside text section")
            stream.seek(self.offset + offset)
            data = stream.read(length)
        try:
            text = data.decode(self.encoding).rstrip("\0")
        except UnicodeDecodeError as error:
            self.errors.append({"strref": strref, "error": str(error)})
            text = data.decode(self.encoding, errors="replace").rstrip("\0")
        result = {"strref": strref, "text": text, "sound": entry.ref(2), "flags": entry.number(0, "H")}
        self.cache[strref] = result
        return result


def reference(name, ext, reason):
    name = name.upper()
    return {"name": name, "type": ext, "reason": reason} if name not in NONE_REFS else None


def parseItemEntry(reader, offset):
    return {
        "item": reader.ref(offset),
        "expiration": reader.number(offset + 8, "H"),
        "charges": [reader.number(offset + value, "H") for value in (10, 12, 14)],
        "flags": reader.number(offset + 16),
    }


def parseArea(data):
    reader = Binary(data)
    reader.signature(b"AREAV1.0", 0x11C)
    refs, embedded = [], []
    vertex_table = [
        [reader.number(offset, "H"), reader.number(offset + 2, "H")]
        for offset in reader.table(reader.number(0x7C), reader.number(0x80, "H"), 4)
    ]

    def vertices(first, count):
        if not count:
            return []
        if first > len(vertex_table) or count > len(vertex_table) - first:
            raise AuditError("polygon vertex range outside area vertex table")
        return vertex_table[first : first + count]

    result = {
        "wed": reader.ref(8),
        "flags": reader.number(0x14),
        "type_flags": reader.number(0x48, "H"),
        "script": reader.ref(0x94),
        "actors": [],
        "regions": [],
        "containers": [],
        "doors": [],
        "spawns": [],
        "entrances": [],
        "items": [],
        "adjacency": [
            {"direction": direction, "area": reader.ref(offset), "flags": reader.number(offset + 8)}
            for direction, offset in (("north", 0x18), ("east", 0x24), ("south", 0x30), ("west", 0x3C))
            if reader.ref(offset)
        ],
    }
    refs.append(reference(result["script"], "BCS", "area script"))
    refs.extend(reference(row["area"], "ARE", "area header adjacency") for row in result["adjacency"])
    for offset in reader.table(reader.number(0x54), reader.number(0x58, "H"), 0x110):
        actor = {
            "name": reader.text(offset, 32),
            "position": [reader.number(offset + n, "H") for n in (32, 34)],
            "flags": reader.number(offset + 0x28),
            "schedule": reader.number(offset + 0x40),
            "dialogue": reader.ref(offset + 0x48),
            "creature": reader.ref(offset + 0x80),
            "scripts": [reader.ref(offset + n) for n in range(0x50, 0x80, 8)],
        }
        refs.append(reference(actor["dialogue"], "DLG", "area actor dialogue"))
        refs.extend(reference(name, "BCS", "area actor script") for name in actor["scripts"])
        cre_offset, cre_size = reader.number(offset + 0x88), reader.number(offset + 0x8C)
        if cre_size:
            actor["embedded_creature_sha256"] = sha256(reader.span(cre_offset, cre_size))
            parsed, children, unused = parseCreature(reader.span(cre_offset, cre_size))
            actor["embedded_creature"] = parsed
            refs.extend(children)
        else:
            refs.append(reference(actor["creature"], "CRE", "area actor creature"))
        result["actors"].append(actor)
    for offset in reader.table(reader.number(0x5C), reader.number(0x5A, "H"), 0xC4):
        region = {
            "name": reader.text(offset, 32),
            "type": reader.number(offset + 0x20, "H"),
            "bounding_box": [reader.number(offset + value, "H") for value in (0x22, 0x24, 0x26, 0x28)],
            "destination": reader.ref(offset + 0x38),
            "entrance": reader.text(offset + 0x40, 32),
            "flags": reader.number(offset + 0x60),
            "text_strref": reader.number(offset + 0x64),
            "trap_difficulty": reader.number(offset + 0x68, "H"),
            "trap_removal": reader.number(offset + 0x6A, "H"),
            "trapped": reader.number(offset + 0x6C, "H"),
            "key": reader.ref(offset + 0x74),
            "script": reader.ref(offset + 0x7C),
            "polygon": vertices(reader.number(offset + 0x2C), reader.number(offset + 0x2A, "H")),
            "use_point": [reader.number(offset + n, "H") for n in (0x84, 0x86)],
        }
        result["regions"].append(region)
        for field, ext in (("destination", "ARE"), ("key", "ITM"), ("script", "BCS")):
            refs.append(reference(region[field], ext, f"region {region['name']} {field}"))
    for offset in reader.table(reader.number(0x78), reader.number(0x76, "H"), 0x14):
        result["items"].append(parseItemEntry(reader, offset))
    refs.extend(reference(item["item"], "ITM", "area item") for item in result["items"])
    for offset in reader.table(reader.number(0x70), reader.number(0x74, "H"), 0xC0):
        first, count = reader.number(offset + 0x40), reader.number(offset + 0x44)
        if first > len(result["items"]) or count > len(result["items"]) - first:
            raise AuditError("container item range outside area items")
        container = {
            "name": reader.text(offset, 32),
            "position": [reader.number(offset + n, "H") for n in (32, 34)],
            "lock_difficulty": reader.number(offset + 0x26, "H"),
            "flags": reader.number(offset + 0x28),
            "trap_detection": reader.number(offset + 0x2C, "H"),
            "trap_removal": reader.number(offset + 0x2E, "H"),
            "trapped": reader.number(offset + 0x30, "H"),
            "owner": reader.text(offset + 0x58, 32),
            "key": reader.ref(offset + 0x78),
            "script": reader.ref(offset + 0x48),
            "break_difficulty": reader.number(offset + 0x80),
            "items": result["items"][first : first + count],
            "polygon": vertices(reader.number(offset + 0x50), reader.number(offset + 0x54, "H")),
        }
        result["containers"].append(container)
        refs.extend(
            [
                reference(container["key"], "ITM", "container key"),
                reference(container["script"], "BCS", "container script"),
            ]
        )
    for offset in reader.table(reader.number(0xA8), reader.number(0xA4), 0xC8):
        door = {
            "name": reader.text(offset, 32),
            "flags": reader.number(offset + 0x28),
            "use_points": [reader.number(offset + value, "H") for value in (0x90, 0x92, 0x94, 0x96)],
            "lock_difficulty": reader.number(offset + 0x8C),
            "key": reader.ref(offset + 0x78),
            "script": reader.ref(offset + 0x80),
            "dialogue": reader.ref(offset + 0xB8),
            "trapped": reader.number(offset + 0x70, "H"),
            "travel_trigger": reader.text(offset + 0x9C, 24),
            "open_polygon": vertices(reader.number(offset + 0x2C), reader.number(offset + 0x30, "H")),
            "closed_polygon": vertices(reader.number(offset + 0x34), reader.number(offset + 0x32, "H")),
            "open_impeded": vertices(reader.number(offset + 0x48), reader.number(offset + 0x4C, "H")),
            "closed_impeded": vertices(reader.number(offset + 0x50), reader.number(offset + 0x4E, "H")),
            "trap_detection": reader.number(offset + 0x6C, "H"),
            "trap_removal": reader.number(offset + 0x6E, "H"),
        }
        result["doors"].append(door)
        for field, ext in (("key", "ITM"), ("script", "BCS"), ("dialogue", "DLG")):
            refs.append(reference(door[field], ext, "door " + field))
    for offset in reader.table(reader.number(0x60), reader.number(0x64), 0xC8):
        count = reader.number(offset + 0x74, "H")
        if count > 10:
            raise AuditError("spawn table exceeds ten creature slots")
        creatures = [reader.ref(offset + 0x24 + n * 8) for n in range(count)]
        result["spawns"].append(
            {
                "name": reader.text(offset, 32),
                "creatures": creatures,
                "method": reader.number(offset + 0x7A, "H"),
                "enabled": reader.number(offset + 0x86, "H"),
            }
        )
        refs.extend(reference(name, "CRE", "spawn creature or SPAWNGRP.2DA key") for name in creatures)
    for offset in reader.table(reader.number(0x68), reader.number(0x6C), 0x68):
        result["entrances"].append(
            {"name": reader.text(offset, 32), "position": [reader.number(offset + n, "H") for n in (32, 34)]}
        )
    rest_offset = reader.number(0xC0)
    if rest_offset:
        reader.span(rest_offset, 0xE4)
        count = reader.number(rest_offset + 0x98, "H")
        if count > 10:
            raise AuditError("rest interruption exceeds ten creature slots")
        creatures = [reader.ref(rest_offset + 0x48 + n * 8) for n in range(count)]
        result["rest_interruptions"] = {
            "creatures": creatures,
            "explanation_strrefs": [reader.number(rest_offset + 0x20 + n * 4) for n in range(10)],
            "raw_sha256": sha256(reader.span(rest_offset, 0xE4)),
        }
        refs.extend(reference(name, "CRE", "rest creature or SPAWNGRP.2DA key") for name in creatures)
    return result, refs, embedded


def parseSearchMap(data):
    """Read indexed collision metadata only; no palette or graphics are exported."""
    reader = Binary(data)
    if reader.span(0, 2) != b"BM" or reader.number(14) < 40:
        raise AuditError("unsupported search-map BMP header")
    width, signed_height = reader.number(18, "i"), reader.number(22, "i")
    depth = reader.number(28, "H")
    if reader.number(26, "H") != 1 or reader.number(30) != 0 or depth not in (4, 8):
        raise AuditError("search map must be an uncompressed 4-bit or 8-bit indexed BMP")
    height = abs(signed_height)
    if width <= 0 or not height or width * height > MAX_RECORDS:
        raise AuditError("invalid or excessive search-map dimensions")
    stride = ((width * depth + 31) // 32) * 4
    raster = reader.span(reader.number(10), stride * height)
    rows = []
    for y in range(height):
        source_y = height - y - 1 if signed_height > 0 else y
        raw = raster[source_y * stride : (source_y + 1) * stride]
        values = [raw[x] if depth == 8 else (raw[x // 2] >> (4 if x % 2 == 0 else 0)) & 15 for x in range(width)]
        runs = []
        for value in values:
            if runs and runs[-1] == value:
                runs[-2] += 1
            else:
                runs.extend((1, value))
        rows.append(runs)
    return {"width": width, "height": height, "sourceCellPixels": [16, 12], "terrainRowsRle": rows}


def parseWorldMap(data):
    reader = Binary(data)
    reader.signature(b"WMAPV1.0", 16)
    worlds, refs = [], []
    for offset in reader.table(reader.number(12), reader.number(8), 0xB8):
        area_offsets = list(reader.table(reader.number(offset + 0x24), reader.number(offset + 0x20), 0xF0))
        link_offsets = list(reader.table(reader.number(offset + 0x28), reader.number(offset + 0x2C), 0xD8))
        names = [reader.ref(position) for position in area_offsets]
        areas = []
        for position, name in zip(area_offsets, names):
            links = []
            refs.append(reference(name, "ARE", "world map area"))
            for direction, field in (("north", 0x50), ("west", 0x58), ("south", 0x60), ("east", 0x68)):
                first, count = reader.number(position + field), reader.number(position + field + 4)
                if first > len(link_offsets) or count > len(link_offsets) - first:
                    raise AuditError("world map area link range outside table")
                for link in link_offsets[first : first + count]:
                    target = reader.number(link)
                    if target >= len(names):
                        raise AuditError("world map destination outside area table")
                    encounters = [reader.ref(link + field) for field in range(0x2C, 0x54, 8)]
                    refs.extend(reference(value, "ARE", "world map random encounter") for value in encounters)
                    links.append(
                        {
                            "direction": direction,
                            "destination": names[target],
                            "entrance": reader.text(link + 4, 32),
                            "travel_time_quarters": reader.number(link + 0x24),
                            "arrival_flags": reader.number(link + 0x28),
                            "random_encounters": [value for value in encounters if value not in NONE_REFS],
                            "encounter_chance": reader.number(link + 0x54),
                        }
                    )
            areas.append({"area": name, "flags": reader.number(position + 0x30), "links": links})
        worlds.append({"areas": areas})
    return {"worlds": worlds}, refs, []


def parseNumericTwoDa(data):
    """Read a fully specified numeric 2DA, refusing string/default-expansion ambiguities."""
    try:
        lines = [line.split() for line in data.decode("ascii").splitlines() if line.strip()]
    except UnicodeDecodeError as error:
        raise AuditError("numeric 2DA must use ASCII tokens") from error
    if len(lines) < 3 or lines[0] != ["2DA", "V1.0"] or len(lines[1]) != 1:
        raise AuditError("unsupported numeric 2DA header")
    columns = lines[2]
    if not columns or len(columns) != len(set(columns)) or len(lines) - 3 > MAX_RECORDS:
        raise AuditError("invalid numeric 2DA columns or excessive record count")
    rows = {}
    try:
        default = int(lines[1][0])
        for tokens in lines[3:]:
            if len(tokens) != len(columns) + 1 or tokens[0] in rows:
                raise AuditError("numeric 2DA needs unique row IDs and explicit cells for every column")
            rows[tokens[0]] = dict(zip(columns, (int(value) for value in tokens[1:])))
    except ValueError as error:
        if isinstance(error, AuditError):
            raise
        raise AuditError("numeric 2DA contains a non-integer cell") from error
    return {"default": default, "columns": columns, "rows": rows}, [], []


def parseGame(data):
    """Read BG-family GAM party/NPC placement records, retaining embedded CRE state when present."""
    reader = Binary(data)
    signature = reader.span(0, 8)
    if signature not in (b"GAMEV1.1", b"GAMEV2.0"):
        raise AuditError(f"unsupported BG-family GAM signature/version {signature!r}")
    reader.signature(signature, 0xB4)
    result = {"version": signature[4:].decode("ascii"), "party_members": [], "non_party_members": []}
    refs = []
    for table, offset_field, count_field in (("party_members", 0x20, 0x24), ("non_party_members", 0x30, 0x34)):
        for index, offset in enumerate(reader.table(reader.number(offset_field), reader.number(count_field), 0x160)):
            creature_offset, creature_size = reader.number(offset + 4), reader.number(offset + 8)
            if bool(creature_offset) != bool(creature_size):
                raise AuditError("GAM embedded CRE offset and size must both be zero or both be present")
            row = {
                "sourceIndex": index,
                "recordOffset": offset,
                "selection_flags": reader.number(offset, "H"),
                "party_order": reader.number(offset + 2, "H"),
                "creature": reader.ref(offset + 0xC),
                "orientation": reader.number(offset + 0x14),
                "area": reader.ref(offset + 0x18),
                "position": [reader.number(offset + 0x20, "H"), reader.number(offset + 0x22, "H")],
                "modal_action": reader.number(offset + 0x28, "H"),
                "happiness": reader.number(offset + 0x2A, "H"),
                "talk_count": reader.number(offset + 0xE0),
                "embedded_creature_offset": creature_offset,
                "embedded_creature_size": creature_size,
            }
            if creature_size:
                creature_data = reader.span(creature_offset, creature_size)
                creature, children, _ = parseCreature(creature_data)
                row["embedded_creature"] = creature
                row["embedded_creature_sha256"] = sha256(creature_data)
                refs.extend(children)
            else:
                refs.append(reference(row["creature"], "CRE", "GAM NPC creature"))
            refs.append(reference(row["area"], "ARE", "GAM NPC current area"))
            result[table].append(row)
    return result, refs, []


def parseCreature(data):
    reader = Binary(data)
    reader.signature(b"CRE V1.0", 0x2D4)
    scripts = [reader.ref(offset) for offset in range(0x248, 0x270, 8)]
    result = {
        "name_strref": reader.number(8),
        "short_name_strref": reader.number(12),
        "flags": reader.number(16),
        "kill_xp": reader.number(20),
        "gold": reader.number(28),
        "hit_points": reader.number(0x24, "h"),
        "max_hit_points": reader.number(0x26, "h"),
        "allegiance": reader.number(0x270, "B"),
        "race": reader.number(0x272, "B"),
        "class": reader.number(0x273, "B"),
        "alignment": reader.number(0x27B, "B"),
        "death_variable": reader.text(0x280, 32),
        "dialogue": reader.ref(0x2CC),
        "scripts": scripts,
        "items": [],
        "known_spells": [],
        "memorized_spells": [],
    }
    refs = [reference(name, "BCS", "creature script") for name in scripts]
    refs.append(reference(result["dialogue"], "DLG", "creature dialogue"))
    for offset in reader.table(reader.number(0x2BC), reader.number(0x2C0), 0x14):
        item = parseItemEntry(reader, offset)
        result["items"].append(item)
        refs.append(reference(item["item"], "ITM", "creature inventory"))
    for field, offset_field, count_field in (("known_spells", 0x2A0, 0x2A4), ("memorized_spells", 0x2B0, 0x2B4)):
        for offset in reader.table(reader.number(offset_field), reader.number(count_field), 12):
            result[field].append(reader.ref(offset))
            refs.append(reference(reader.ref(offset), "SPL", "creature " + field))
    effect_size = 0x30 if reader.number(0x33, "B") == 0 else 0x108
    effects = list(reader.table(reader.number(0x2C4), reader.number(0x2C8), effect_size))
    result["effect_count"] = len(effects)
    result["effects_interpreted"] = False
    return result, refs, []


def parseDialogue(data):
    reader = Binary(data)
    reader.signature(b"DLG V1.0", 0x30)
    pools = {}
    for name, offset_field, count_field in (
        ("state_triggers", 24, 28),
        ("transition_triggers", 32, 36),
        ("actions", 40, 44),
    ):
        pools[name] = [
            reader.span(reader.number(offset), reader.number(offset + 4)).decode("ascii")
            for offset in reader.table(reader.number(offset_field), reader.number(count_field), 8)
        ]

    def poolValue(name, index):
        if index >= len(pools[name]):
            raise AuditError(f"DLG {name} index {index} outside pool")
        return pools[name][index]

    transitions, refs = [], []
    for offset in reader.table(reader.number(20), reader.number(16), 32):
        flags = reader.number(offset)
        target = reader.ref(offset + 20) if not flags & 8 else ""
        transition = {
            "flags": flags,
            "text_strref": reader.number(offset + 4) if flags & 1 else None,
            "journal_strref": reader.number(offset + 8) if flags & 16 else None,
            "trigger": poolValue("transition_triggers", reader.number(offset + 12)) if flags & 2 else None,
            "action": poolValue("actions", reader.number(offset + 16)) if flags & 4 else None,
            "next_dialogue": target,
            "next_state": reader.number(offset + 28) if not flags & 8 else None,
        }
        transitions.append(transition)
        refs.append(reference(target, "DLG", "dialogue transition"))
    states = []
    for offset in reader.table(reader.number(12), reader.number(8), 16):
        first, count = reader.number(offset + 4), reader.number(offset + 8)
        if first > len(transitions) or count > len(transitions) - first:
            raise AuditError("DLG state transition range outside table")
        index = reader.number(offset + 12)
        states.append(
            {
                "text_strref": reader.number(offset),
                "first_transition": first,
                "transition_count": count,
                "trigger": None if index == 0xFFFFFFFF else poolValue("state_triggers", index),
            }
        )
    for transition in transitions:
        if transition["next_dialogue"] == "" and transition["next_state"] is not None:
            if transition["next_state"] >= len(states):
                raise AuditError("DLG internal target outside states")
    return {"states": states, "transitions": transitions, **pools}, refs, []


def parseStore(data):
    reader = Binary(data)
    reader.signature(b"STORV1.0", 0x9C)
    result = {
        "store_type": reader.number(8),
        "name_strref": reader.number(12),
        "flags": reader.number(16),
        "sell_markup": reader.number(20),
        "buy_markup": reader.number(24),
        "depreciation": reader.number(28),
        "steal_failure": reader.number(32, "H"),
        "identify_price": reader.number(0x40),
        "room_flags": reader.number(0x5C),
        "room_prices": [reader.number(n) for n in range(0x60, 0x70, 4)],
        "stock": [],
        "drinks": [],
        "cures": [],
    }
    refs = []
    for offset in reader.table(reader.number(0x34), reader.number(0x38), 28):
        item = {
            **parseItemEntry(reader, offset),
            "stock": reader.number(offset + 20),
            "infinite": reader.number(offset + 24),
        }
        result["stock"].append(item)
        refs.append(reference(item["item"], "ITM", "store stock"))
    for offset in reader.table(reader.number(0x4C), reader.number(0x50), 20):
        result["drinks"].append(
            {
                "rumour": reader.ref(offset),
                "name_strref": reader.number(offset + 8),
                "price": reader.number(offset + 12),
                "strength": reader.number(offset + 16),
            }
        )
        refs.append(reference(reader.ref(offset), "DLG", "drink rumour"))
    for offset in reader.table(reader.number(0x70), reader.number(0x74), 12):
        result["cures"].append({"spell": reader.ref(offset), "price": reader.number(offset + 8)})
        refs.append(reference(reader.ref(offset), "SPL", "temple cure"))
    result["purchased_types"] = [
        reader.number(offset) for offset in reader.table(reader.number(0x2C), reader.number(0x30), 4)
    ]
    refs.extend(reference(reader.ref(offset), "DLG", "store rumour") for offset in (0x44, 0x54))
    return result, refs, []


def parseItem(data):
    reader = Binary(data)
    reader.signature(b"ITM V1  ", 0x72)
    replacement = reader.ref(0x10)
    abilities = list(reader.table(reader.number(0x64), reader.number(0x68, "H"), 0x38))
    return (
        {
            "name_strref": reader.number(8),
            "identified_name_strref": reader.number(12),
            "description_strref": reader.number(0x50),
            "identified_description_strref": reader.number(0x54),
            "flags": reader.number(0x18),
            "item_type": reader.number(0x1C, "H"),
            "unusable_mask": reader.number(0x1E),
            "price": reader.number(0x34),
            "stack_size": reader.number(0x38, "H"),
            "lore": reader.number(0x42, "H"),
            "weight": reader.number(0x4C),
            "enchantment": reader.number(0x60),
            "replacement": replacement,
            "ability_count": len(abilities),
            "effects_interpreted": False,
        },
        [reference(replacement, "ITM", "replacement item")],
        [],
    )


class IdsTable(dict):
    """Keep textual aliases as well as the first signature for each compiled opcode."""

    def __init__(self):
        super().__init__()
        self.signatures = []


def parseIds(data):
    result = IdsTable()
    for line in data.decode("ascii", errors="replace").splitlines():
        match = re.match(r"^\s*(0x[\da-fA-F]+|\d+)\s+(.+?)\s*(?://.*)?$", line)
        if match:
            raw = match.group(1)
            signature = match.group(2)
            result.setdefault(int(raw, 16 if raw.lower().startswith("0x") else 10), signature)
            result.signatures.append(signature)
    return result


def referenceType(function, parameter):
    name = function.lower()
    parameter = parameter.strip().lower().removeprefix("s:")
    if name in {"giveitem", "useitem"} and parameter.partition("*")[0].strip() == "object":
        return "ITM"
    if "item" in name and ("item" in parameter or "resref" in parameter):
        return "ITM"
    if "creature" in name and any(label in parameter for label in ("creature", "resref", "newobject")):
        return "CRE"
    if "store" in name and ("store" in parameter or "resref" in parameter):
        return "STO"
    if "dialog" in parameter or "dialog" in name and "resref" in parameter:
        return "DLG"
    if "script" in parameter or "cutscene" in parameter:
        return "BCS"
    if "area" in parameter and name.startswith(("leavearea", "movebetweenareas", "areacheck", "setmasterarea")):
        return "ARE"
    if "spell" in parameter and "res" in name:
        return "SPL"
    return None


def parseScript(data, actions, triggers):
    text = data.decode("ascii")
    if not text.strip().startswith("SC") or not text.strip().endswith("SC"):
        raise AuditError("unsupported compiled script envelope")
    records, refs, warnings = [], [], []
    token_pattern = r'"[^"]*"|(?P<marker>AC|TR|OB)(?=\s|$)'

    def markers(source, marker):
        return [match for match in re.finditer(token_pattern, source) if match.group("marker") == marker]

    for marker, table in (("TR", triggers), ("AC", actions)):
        matches = markers(text, marker)
        if len(matches) % 2:
            raise AuditError(f"unbalanced {marker} records")
        for opening, closing in zip(matches[::2], matches[1::2]):
            raw = text[opening.end() : closing.start()].strip()
            id_match = re.match(r"-?\d+", raw)
            if not id_match:
                raise AuditError(f"{marker} record has no opcode")
            opcode = int(id_match.group())
            signature = table.get(opcode)
            objects = markers(raw, "OB")
            if len(objects) % 2:
                raise AuditError(f"unbalanced OB records in {marker}")
            no_objects = raw
            for start, end in reversed(list(zip(objects[::2], objects[1::2]))):
                no_objects = no_objects[: start.start()] + " " + no_objects[end.end() :]
            strings = re.findall(r'"([^"]*)"', no_objects)
            integers = [int(value) for value in re.findall(r"-?\d+", re.sub(r'"[^"]*"', "", no_objects))]
            record = {
                "kind": marker,
                "opcode": opcode,
                "signature": signature,
                "strings": strings,
                "integer_fields": integers[1:],
                "raw": raw,
                "offset": opening.start(),
            }
            records.append(record)
            if signature is None:
                warnings.append(f"unknown {marker} opcode {opcode}")
                continue
            function = signature.split("(", 1)[0]
            parameters = re.findall(r"S:([^,)]*)", signature)
            for parameter, value in zip(parameters, strings):
                ext = referenceType(function, parameter)
                if ext:
                    refs.append(reference(value, ext, signature))
    records.sort(key=lambda entry: entry["offset"])
    return {"compiled_text": text, "records": records, "warnings": warnings, "semantics_evaluated": False}, refs, []


def textReferences(text, action_ids, trigger_ids):
    refs = []
    signatures = {}
    for signature in list(getattr(action_ids, "signatures", action_ids.values())) + list(
        getattr(trigger_ids, "signatures", trigger_ids.values())
    ):
        signatures[signature.split("(", 1)[0].lower()] = signature
    for match in re.finditer(r"(\w+)\(", text):
        function = match.group(1)
        signature = signatures.get(function.lower())
        if not signature:
            continue
        # Split the actual argument list at its own nesting level, not object/action arguments.
        arguments, start, depth, quoted = [], match.end(), 1, False
        for position in range(start, len(text)):
            char = text[position]
            if char == '"':
                quoted = not quoted
            elif not quoted:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        arguments.append(text[start:position].strip())
                        break
                elif char == "," and depth == 1:
                    arguments.append(text[start:position].strip())
                    start = position + 1
        if depth:
            continue
        parameters = signature.partition("(")[2].rstrip(")").split(",")
        for parameter, value in zip(parameters, arguments):
            if not parameter.strip().startswith("S:") or not re.fullmatch(r'"[^"]*"', value):
                continue
            ext = referenceType(function, parameter)
            if ext:
                refs.append(reference(value[1:-1], ext, signature))
    return refs


def attachText(value, talk):
    if isinstance(value, list):
        for entry in value:
            attachText(entry, talk)
    elif isinstance(value, dict):
        for key, entry in list(value.items()):
            if key.endswith("_strref") and entry is not None:
                value[key[:-7] + "_tlk"] = talk.get(entry)
            else:
                attachText(entry, talk)


def auditInstallation(game_root, language="en_US", area="AR2600", encoding=None, scope="candlekeep"):
    if scope == "city":
        try:
            from scripts.build_baldurs_gate_source_fixture import buildCityFixture
        except ModuleNotFoundError:
            from build_baldurs_gate_source_fixture import buildCityFixture

        return buildCityFixture(game_root, language, encoding)
    if scope != "candlekeep":
        raise AuditError(f"unsupported audit scope: {scope}")
    if area.upper() != "AR2600":
        raise AuditError("only the Candlekeep prologue root AR2600 is supported")
    if not re.fullmatch(r"[A-Za-z]{2}_[A-Za-z]{2}", language):
        raise AuditError("language must be a locale such as en_US")
    index = ResourceIndex(game_root)
    is_ee = (index.root / "engine.lua").exists() or (index.root / "Baldur.lua").exists()
    tlk_relative = (
        f"lang/{language}/dialog.tlk" if (index.root / "lang" / language / "dialog.tlk").exists() else "dialog.tlk"
    )
    talk = TalkTable(safePath(index.root, tlk_relative), encoding or ("utf-8" if is_ee else "cp1252"))
    report = {
        "schema_version": 1,
        "root_area": area.upper(),
        "language": language,
        "edition": "enhanced_edition_supporting_only" if is_ee else "classic_candidate_not_authenticated",
        "original_parity_established": False,
        "game_root": str(index.root),
        "key_sha256": index.key_hash,
        "tlk": {"path": tlk_relative, "sha256": hashFile(talk.path), "encoding": talk.encoding},
        "views": {},
        "override_count": len(index.overrides),
        "key_duplicates": index.duplicates,
        "all_interactions_accounted_for": False,
        "mods": [],
        "limitations": [
            "Structural closure, not reachability or branch semantics; conditions are retained, not executed.",
            "KEY base means installed archive bytes, not proof of unmodified original BG1 resources.",
            "Only nine prologue areas are allowed; library, return visit and roads are excluded explicitly.",
            "Effects, global scripts, engine hardcoding, random tables, DLC archives and dynamic resource names need review.",
            "BCS retains full compiled blocks and IDS signatures; integer/object fields are not a decompiled program.",
            "Male/default TLK only; dialogf.tlk and non-English classic encodings need separate review.",
        ],
    }
    for path in sorted(index.root.iterdir()):
        if path.is_file() and (
            path.name.lower().startswith("weidu")
            or path.name.lower().startswith("setup-")
            or path.name.lower() in {"engine.lua", "baldur.lua"}
        ):
            evidence = {"path": path.name, "size": path.stat().st_size, "sha256": hashFile(path)}
            if path.name.lower() == "weidu.log" and path.stat().st_size < 1024 * 1024:
                evidence["declared_components"] = [
                    line
                    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                    if line.strip().startswith("~")
                ]
            report["mods"].append(evidence)
    parsers = {
        "ARE": parseArea,
        "CRE": parseCreature,
        "DLG": parseDialogue,
        "STO": parseStore,
        "ITM": parseItem,
        "GAM": parseGame,
    }
    for view in ("base", "effective"):
        ids = {}
        ids_evidence = {}
        for name in ("ACTION", "TRIGGER"):
            try:
                data, origin = index.read(name, "IDS", view)
                ids[name] = parseIds(data)
                ids_evidence[name] = {"sha256": sha256(data), "origin": origin, "entries": len(ids[name])}
            except AuditError as error:
                ids[name] = {}
                ids_evidence[name] = {"error": str(error)}
        queue = deque([(area.upper(), "ARE", "audit root")])
        resources, unresolved, excluded, excluded_resources, edges = {}, [], [], [], []
        while queue:
            name, ext, reason = queue.popleft()
            key = name + "." + ext
            if key in resources:
                continue
            if ext == "ARE" and name not in PROLOGUE_AREAS:
                excluded.append({"resource": key, "reason": reason})
                continue
            if ext == "BCS" and name in EXTERNAL_SCRIPTS:
                excluded_resources.append({"resource": key, "reason": EXTERNAL_SCRIPTS[name], "from": reason})
                continue
            try:
                data, origin = index.read(name, ext, view)
                record = {"sha256": sha256(data), "size": len(data), "origin": origin}
                resources[key] = record
                if ext == "BCS":
                    parsed, refs, unused = parseScript(data, ids["ACTION"], ids["TRIGGER"])
                elif ext in parsers:
                    parsed, refs, unused = parsers[ext](data)
                elif ext == "IDS":
                    parsed, refs = {"entries": parseIds(data)}, []
                else:
                    parsed, refs = {"metadata_only": True, "format_not_interpreted": ext}, []
                if ext == "ARE":
                    try:
                        wed_data, wed_origin = index.read(parsed["wed"], "WED", view)
                        wed = Binary(wed_data)
                        wed.signature(b"WED V1.3", 32)
                        overlay = wed.number(16)
                        parsed["dimensions"] = {
                            "width": wed.number(overlay, "H") * 64,
                            "height": wed.number(overlay + 2, "H") * 64,
                            "wed_sha256": sha256(wed_data),
                            "origin": wed_origin,
                        }
                    except AuditError as error:
                        parsed["dimension_error"] = str(error)
                if ext == "DLG":
                    for pool in ("state_triggers", "transition_triggers", "actions"):
                        for text in parsed[pool]:
                            refs.extend(textReferences(text, ids["ACTION"], ids["TRIGGER"]))
                attachText(parsed, talk)
                record["parsed"] = parsed
                for ref in refs:
                    if ref:
                        edge = {"from": key, "to": ref["name"] + "." + ref["type"], "reason": ref["reason"]}
                        edges.append(edge)
                        queue.append((ref["name"], ref["type"], key + ": " + ref["reason"]))
            except (AuditError, UnicodeError, OSError, struct.error) as error:
                unresolved.append({"resource": key, "reason": reason, "error": str(error)})
                resources.setdefault(key, {})["error"] = str(error)
            if len(resources) > 5000:
                raise AuditError("resource closure exceeded 5000 entries; refusing unbounded traversal")
        report["views"][view] = {
            "resources": resources,
            "edges": edges,
            "unresolved": unresolved,
            "ids": ids_evidence,
            "excluded_areas": excluded,
            "excluded_resources": excluded_resources,
            "counts": dict(sorted(Counter(key.rsplit(".", 1)[1] for key in resources).items())),
        }
    report["tlk_errors"] = talk.errors
    report["used_biffs"] = index.biff_evidence
    base = report["views"]["base"]["resources"]
    effective = report["views"]["effective"]["resources"]
    report["base_effective_differences"] = [
        key
        for key in sorted(set(base) | set(effective))
        if base.get(key, {}).get("sha256") != effective.get(key, {}).get("sha256")
    ]
    report["overrides"] = [
        {"resource": ".".join(key), "size": path.stat().st_size, "in_audit_closure": ".".join(key) in effective}
        for key, path in sorted(index.overrides.items())
    ]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--language", default="en_US")
    parser.add_argument("--area", default="AR2600")
    parser.add_argument(
        "--scope",
        choices=("candlekeep", "city"),
        default="candlekeep",
        help="Candlekeep closure or the explicit nine-ward city manifest; --area applies to Candlekeep",
    )
    parser.add_argument("--encoding", help="classic TLK encoding override; EE defaults to UTF-8")
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="local ignored output; contains copyrighted dialogue"
    )
    args = parser.parse_args(argv)
    try:
        output = args.output_dir.resolve()
        game_root = args.game_root.resolve()
        if output == game_root or output.is_relative_to(game_root):
            raise AuditError("output must be outside the game installation")
        report = auditInstallation(game_root, args.language, args.area, args.encoding, args.scope)
        output.mkdir(parents=True, exist_ok=True)
        destination = output / ("city-source-audit.json.gz" if args.scope == "city" else "source-audit.json.gz")
        with gzip.open(destination, "wt", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, separators=(",", ":"))
        if args.scope == "city":
            print(
                json.dumps(
                    {
                        "scope": "city",
                        "output": str(destination),
                        "counts": report["counts"],
                        "unresolved": len(report["unresolved"]),
                        "originalParityEstablished": False,
                    },
                    indent=2,
                )
            )
            return 2 if report["unresolved"] else 0
        summary = {
            "edition": report["edition"],
            "output": str(destination),
            "views": {
                name: {
                    "counts": view["counts"],
                    "unresolved": len(view["unresolved"]),
                    "excluded_areas": sorted({entry["resource"] for entry in view["excluded_areas"]}),
                }
                for name, view in report["views"].items()
            },
            "differences": len(report["base_effective_differences"]),
        }
        print(json.dumps(summary, indent=2))
        return 2 if any(view["unresolved"] for view in report["views"].values()) else 0
    except (AuditError, OSError, UnicodeError, struct.error) as error:
        print(f"Audit failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
