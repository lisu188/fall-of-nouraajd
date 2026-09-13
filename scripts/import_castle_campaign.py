#!/usr/bin/env python3
"""Author native Castle maps from the owner's original Long Live the Queen data.

This deliberately supports only the three RoE maps in GOOD1.H3C. It is an
offline authoring tool, not a runtime Heroes III importer. No original prose,
graphics, sounds, or binary resources are written to the output directory.

Binary field descriptions were checked against VCMI's MapFormatH3M.cpp,
MapFeaturesH3M.cpp, ObjectTemplate.cpp, and CampaignHandler.cpp:
https://github.com/vcmi/vcmi/tree/develop/lib/mapping
https://github.com/vcmi/vcmi/tree/develop/lib/campaign
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
import zlib
from collections import Counter, defaultdict, deque
from pathlib import Path

CAMPAIGN_SHA256 = "73c04fb5d3f6beb7d2398d4bbb0128dfc6450fab74922fd4c855bb83508e0a1f"
SCENARIOS = (("castleHomecoming", 72), ("castleGuardianAngels", 36), ("castleGriffinCliff", 72))
MAX_MEMBER_SIZE = 2_000_000
TERRAIN_GIDS = (10, 8, 11, 5, 3, 7, 10, 9, 2, 12)
HERO_TYPES = {34, 62, 70, 214}
MONSTER_TYPES = {54, 71, 72, 73, 74, 75, 162, 163, 164}
ARTIFACT_TYPES = {5, 65, 66, 67, 68, 69}
STATIC_TYPES = (
    {
        2,
        3,
        4,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        21,
        22,
        23,
        24,
        25,
        27,
        28,
        29,
        30,
        31,
        32,
        35,
        37,
        38,
        39,
        41,
        43,
        44,
        45,
        46,
        47,
        48,
        49,
        50,
        51,
        52,
        55,
        56,
        57,
        58,
        60,
        61,
        63,
        64,
        78,
        80,
        82,
        84,
        85,
        86,
        92,
        94,
        95,
        96,
        97,
        99,
        100,
        101,
        102,
        103,
        104,
        105,
        106,
        107,
        108,
        109,
        110,
        111,
        112,
        113,
        212,
        213,
    }
    | set(range(114, 139))
    | {143}
    | set(range(147, 162))
)


class ImportError(ValueError):
    """Invalid, truncated, or unsupported original campaign input."""


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.position = 0

    def take(self, count: int) -> bytes:
        if count < 0 or self.position + count > len(self.data):
            raise ImportError(f"Truncated input at byte {self.position}: wanted {count} bytes")
        value = self.data[self.position : self.position + count]
        self.position += count
        return value

    def u8(self) -> int:
        return self.take(1)[0]

    def u16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def boolean(self) -> bool:
        value = self.u8()
        if value > 1:
            raise ImportError(f"Invalid boolean {value} at byte {self.position - 1}")
        return bool(value)

    def string(self) -> bytes:
        count = self.u32()
        if count > 100_000:
            raise ImportError(f"Unbounded string at byte {self.position - 4}")
        return self.take(count)

    def xyz(self) -> list[int]:
        return list(self.take(3))

    def count(self, maximum: int = 10_000) -> int:
        value = self.u32()
        if value > maximum:
            raise ImportError(f"Excessive record count {value} at byte {self.position - 4}")
        return value

    def zero(self, count: int) -> None:
        if any(self.take(count)):
            raise ImportError(f"Nonzero reserved bytes before byte {self.position}")


def decompressBounded(data: bytes, window: int = zlib.MAX_WBITS) -> bytes:
    decoder = zlib.decompressobj(window)
    result = decoder.decompress(data, MAX_MEMBER_SIZE + 1)
    if len(result) > MAX_MEMBER_SIZE or decoder.unconsumed_tail:
        raise ImportError("Compressed resource exceeds the authoring size limit")
    if not decoder.eof or decoder.unused_data:
        raise ImportError("Invalid compressed resource boundary")
    return result


def readLodEntry(path: Path, name: str = "GOOD1.H3C") -> bytes:
    """Seek only the directory and one entry, avoiding loading an entire LOD."""
    with path.open("rb") as stream:
        header = stream.read(92)
        if len(header) != 92 or header[:4] != b"LOD\x00":
            raise ImportError("Expected a Heroes III LOD archive")
        count = struct.unpack_from("<I", header, 8)[0]
        if count > 100_000:
            raise ImportError("Unbounded LOD directory")
        found = []
        for _ in range(count):
            entry = stream.read(32)
            if len(entry) != 32:
                raise ImportError("Truncated LOD directory")
            entry_name = entry[:16].split(b"\0", 1)[0].decode("ascii").upper()
            if entry_name == name.upper():
                found.append(struct.unpack_from("<IIII", entry, 16))
        if len(found) != 1:
            raise ImportError(f"Expected exactly one {name} entry; found {len(found)}")
        offset, full_size, _, compressed_size = found[0]
        stored_size = compressed_size or full_size
        if not (0 < stored_size <= MAX_MEMBER_SIZE and 0 < full_size <= MAX_MEMBER_SIZE):
            raise ImportError("Invalid LOD resource size")
        stream.seek(offset)
        data = stream.read(stored_size)
        if len(data) != stored_size:
            raise ImportError("Truncated LOD resource")
    result = decompressBounded(data) if compressed_size else data
    if len(result) != full_size:
        raise ImportError("LOD resource size does not match its directory entry")
    return result


def splitCampaign(data: bytes) -> list[bytes]:
    members = []
    while data:
        if len(members) >= 4 or not data.startswith(b"\x1f\x8b"):
            raise ImportError("Expected exactly four gzip members without trailing data")
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        member = decoder.decompress(data, MAX_MEMBER_SIZE + 1)
        if len(member) > MAX_MEMBER_SIZE or decoder.unconsumed_tail or not decoder.eof:
            raise ImportError("Invalid or oversized H3C member")
        members.append(member)
        data = decoder.unused_data
    if len(members) != 4:
        raise ImportError(f"Expected campaign header and three maps; got {len(members)} members")
    if Reader(members[0]).u32() not in (4, 5):
        raise ImportError("Expected a RoE/AB campaign container")
    return members


def readArmy(reader: Reader, slots: int = 7) -> list[dict]:
    army = []
    for _ in range(slots):
        creature, count = reader.u8(), reader.u16()
        if creature != 255:
            army.append({"creature": creature, "count": count})
    return army


def readResources(reader: Reader) -> list[int]:
    return [reader.i32() for _ in range(7)]


def readGuards(reader: Reader, record: dict) -> None:
    if reader.boolean():
        reader.string()
        if reader.boolean():
            record["army"] = readArmy(reader)
        reader.zero(4)


def readTimedEvent(reader: Reader) -> dict:
    reader.string()
    reader.string()
    event = {"resources": readResources(reader), "players": reader.u8(), "computer": reader.boolean()}
    event["firstDay"], event["repeatDays"] = reader.u16(), reader.u16()
    reader.zero(16)
    return event


def readHero(reader: Reader, record: dict) -> None:
    record["owner"], record["heroId"] = reader.u8(), reader.u8()
    if reader.boolean():
        reader.string()
    record["experience"] = reader.u32()
    if reader.boolean():
        record["portrait"] = reader.u8()
    if reader.boolean():
        record["skills"] = [list(reader.take(2)) for _ in range(reader.count(28))]
    if reader.boolean():
        record["army"] = readArmy(reader)
    record["formation"] = reader.u8()
    if reader.boolean():
        record["artifacts"] = list(reader.take(18))
        record["backpack"] = list(reader.take(reader.u16()))
    record["patrolRadius"] = reader.u8()
    reader.zero(16)


def readTown(reader: Reader, record: dict) -> None:
    record["owner"] = reader.u8()
    if reader.boolean():
        reader.string()
    if reader.boolean():
        record["army"] = readArmy(reader)
    record["formation"] = reader.u8()
    if reader.boolean():
        record["builtBuildings"] = list(reader.take(6))
        record["forbiddenBuildings"] = list(reader.take(6))
    else:
        record["hasFort"] = reader.boolean()
    record["spellMask"] = list(reader.take(9))
    events = []
    for _ in range(reader.count(1000)):
        event = readTimedEvent(reader)
        event["buildings"] = list(reader.take(6))
        event["creatureGrowth"] = [reader.u16() for _ in range(7)]
        reader.zero(4)
        events.append(event)
    if events:
        record["events"] = events
    reader.zero(3)


def readBox(reader: Reader, record: dict) -> None:
    readGuards(reader, record)
    record["experience"], record["mana"] = reader.u32(), reader.i32()
    record["morale"], record["luck"] = reader.u8(), reader.u8()
    record["resources"] = readResources(reader)
    record["primarySkills"] = list(reader.take(4))
    record["skills"] = [list(reader.take(2)) for _ in range(reader.u8())]
    record["artifacts"] = list(reader.take(reader.u8()))
    record["spells"] = list(reader.take(reader.u8()))
    record["rewardArmy"] = readArmy(reader, reader.u8())
    reader.zero(8)


def readSeer(reader: Reader, record: dict) -> None:
    artifact = reader.u8()
    if artifact == 255:
        reader.zero(1)
    else:
        record["questArtifact"] = artifact
        reward_type = reader.u8()
        record["rewardType"] = reward_type
        sizes = {0: 0, 1: 4, 2: 4, 3: 1, 4: 1, 5: 5, 6: 2, 7: 2, 8: 1, 9: 1, 10: 3}
        if reward_type not in sizes:
            raise ImportError(f"Unknown seer reward {reward_type}")
        reward = reader.take(sizes[reward_type])
        if reward_type == 10:
            record["rewardArmy"] = [{"creature": reward[0], "count": struct.unpack_from("<H", reward, 1)[0]}]
        elif reward_type in (1, 2):
            record["rewardValue"] = struct.unpack("<I", reward)[0]
        elif reward:
            record["reward"] = list(reward)
    reader.zero(2)


def readPayload(reader: Reader, record: dict) -> None:
    object_type = record["type"]
    if object_type in (34, 62, 70):
        readHero(reader, record)
    elif object_type == 214:
        record["owner"], record["heroId"] = reader.u8(), reader.u8()
        if record["heroId"] == 255:
            record["powerRank"] = reader.u8()
    elif object_type in MONSTER_TYPES:
        record["army"] = [{"creature": record["subtype"], "count": reader.u16()}]
        record["disposition"] = reader.u8()
        if reader.boolean():
            reader.string()
            record["resources"] = readResources(reader)
            record["artifact"] = reader.u8()
        record["neverFlees"], record["noGrowth"] = reader.boolean(), reader.boolean()
        reader.zero(2)
    elif object_type in (59, 91):
        reader.string()
        reader.zero(4)
    elif object_type == 83:
        readSeer(reader, record)
    elif object_type == 81:
        record["reward"] = list(reader.take(2))
        reader.zero(6)
    elif object_type == 33:
        record["owner"] = reader.u32()
        record["army"] = readArmy(reader)
        reader.zero(8)
    elif object_type in ARTIFACT_TYPES:
        readGuards(reader, record)
    elif object_type == 93:
        readGuards(reader, record)
        record["spell"] = reader.u32()
    elif object_type in (76, 79):
        readGuards(reader, record)
        record["amount"] = reader.u32()
        reader.zero(4)
    elif object_type in (77, 98):
        readTown(reader, record)
    elif object_type in (17, 18, 19, 20, 42, 53, 87):
        record["owner"] = reader.u32()
    elif object_type in (88, 89, 90):
        record["spell"] = reader.u32()
    elif object_type in (6, 26):
        readBox(reader, record)
        if object_type == 26:
            record["players"] = reader.u8()
            record["computer"], record["removeAfterVisit"] = reader.boolean(), reader.boolean()
            reader.zero(4)
    elif object_type == 36:
        record["radius"] = reader.u32()
    elif object_type not in STATIC_TYPES:
        raise ImportError(f"Unsupported RoE object type {object_type} at byte {reader.position}")


def readHeader(reader: Reader) -> dict:
    if reader.u32() != 14:
        raise ImportError("Only original RoE H3M version 14 is supported")
    reader.boolean()
    size, underground = reader.u32(), reader.boolean()
    if size not in (36, 72):
        raise ImportError(f"Unsupported Castle scenario size {size}")
    reader.string()
    reader.string()
    difficulty = reader.u8()
    players = []
    for owner in range(8):
        human, computer = reader.boolean(), reader.boolean()
        if not human and not computer:
            reader.take(6)
            continue
        player = {"owner": owner, "human": human, "computer": computer, "tactic": reader.u8()}
        player["factions"] = reader.u8()
        reader.boolean()
        if reader.boolean():
            player["mainTown"] = reader.xyz()
        reader.boolean()
        if reader.u8() != 255:
            reader.u8()
            reader.string()
        players.append(player)
    victory = {"type": reader.u8()}
    if victory["type"] != 255:
        victory["normalAllowed"], victory["appliesToAI"] = reader.boolean(), reader.boolean()
        if victory["type"] == 6:
            victory["target"] = reader.xyz()
        elif victory["type"] != 8:
            raise ImportError(f"Unsupported Castle victory condition {victory['type']}")
    if reader.u8() != 255:
        raise ImportError("Unsupported Castle loss condition")
    teams = reader.u8()
    team_ids = list(reader.take(8)) if teams else []
    reader.take(16)
    reader.zero(31)
    for _ in range(reader.count(1000)):
        reader.string()
        reader.string()
    return {
        "width": size,
        "height": size,
        "layers": 2 if underground else 1,
        "difficulty": difficulty,
        "players": players,
        "teams": team_ids,
        "victory": victory,
    }


def footprint(template: dict, anchor: list[int], mask_name: str, invert: bool = False) -> list[list[int]]:
    cells = []
    for row, mask in enumerate(template[mask_name]):
        for bit in range(8):
            if bool(mask & (1 << bit)) != invert:
                cells.append([anchor[0] - 7 + bit, anchor[1] - 5 + row, anchor[2]])
    return sorted(cells, key=lambda point: (-point[1], -point[0]))


def readMap(data: bytes, scenario_id: str) -> dict:
    reader = Reader(data)
    result = readHeader(reader)
    result.update(
        schemaVersion=1,
        scenarioId=scenario_id[6:7].lower() + scenario_id[7:],
        mapId=scenario_id,
        sourceSha256=CAMPAIGN_SHA256,
        mapSha256=hashlib.sha256(data).hexdigest(),
    )
    tile_count = result["width"] * result["height"]
    result["terrain"] = [[list(reader.take(7)) for _ in range(tile_count)] for _ in range(result["layers"])]
    if any(cell[0] > 9 or cell[2] > 4 or cell[4] > 3 for layer in result["terrain"] for cell in layer):
        raise ImportError("Invalid RoE terrain, river, or road identifier")
    templates = []
    for index in range(reader.count(2000)):
        template = {"index": index, "animationName": reader.string().decode("ascii")}
        template["blockMask"], template["visitMask"] = list(reader.take(6)), list(reader.take(6))
        template["terrainMasks"] = [reader.u16(), reader.u16()]
        template["type"], template["subtype"] = reader.u32(), reader.u32()
        template["class"], template["priority"] = reader.u8(), reader.u8()
        reader.zero(16)
        templates.append(template)
    result["templates"] = templates
    objects = []
    for index in range(reader.count(10_000)):
        start = reader.position
        anchor, template_index = reader.xyz(), reader.u32()
        if (
            template_index >= len(templates)
            or anchor[2] >= result["layers"]
            or anchor[0] >= result["width"] + 8
            or anchor[1] >= result["height"] + 8
        ):
            raise ImportError(f"Invalid object template/layer at byte {start}")
        template = templates[template_index]
        record = {
            "index": index,
            "type": template["type"],
            "subtype": template["subtype"],
            "template": template_index,
            "anchor": anchor,
        }
        visits = footprint(template, anchor, "visitMask")
        record["visit"] = visits[0] if visits else anchor.copy()
        record["visitable"] = bool(visits)
        if visits and not (0 <= record["visit"][0] < result["width"] and 0 <= record["visit"][1] < result["height"]):
            raise ImportError(f"Interaction tile outside map for object {index}")
        reader.zero(5)
        try:
            readPayload(reader, record)
        except (ImportError, UnicodeDecodeError) as error:
            raise ImportError(f"Object {index}, type {record['type']}, at {anchor}, byte {start}: {error}") from error
        objects.append(record)
    result["objects"] = objects
    result["events"] = [readTimedEvent(reader) for _ in range(reader.count(1000))]
    if any(reader.take(len(data) - reader.position)):
        raise ImportError("Unexpected trailing map data")
    result["portals"] = pairPortals(objects)
    return result


def pairPortals(objects: list[dict]) -> list[dict]:
    pairs = []
    gates = [record for record in objects if record["type"] == 103]
    remaining = [record for record in gates if record["anchor"][2] == 1]
    for gate in sorted(
        (record for record in gates if record["anchor"][2] == 0),
        key=lambda record: (record["anchor"][0], record["anchor"][1]),
    ):
        if not remaining:
            raise ImportError("Unpaired subterranean gate")
        target = min(
            remaining,
            key=lambda other: (sum((gate["anchor"][i] - other["anchor"][i]) ** 2 for i in range(2)), other["index"]),
        )
        remaining.remove(target)
        pairs.append(
            {
                "kind": "crossZ",
                "from": gate["visit"],
                "to": target["visit"],
                "objects": [gate["index"], target["index"]],
            }
        )
    if remaining:
        raise ImportError("Unpaired subterranean gate")
    monoliths = [record for record in objects if record["type"] == 45]
    for subtype in sorted({record["subtype"] for record in monoliths}):
        group = [record for record in monoliths if record["subtype"] == subtype]
        if len(group) != 2:
            raise ImportError("Only paired two-way monoliths are supported")
        pairs.append(
            {
                "kind": "twoWay",
                "from": group[0]["visit"],
                "to": group[1]["visit"],
                "objects": [record["index"] for record in group],
            }
        )
    whirlpools = [record for record in objects if record["type"] == 111]
    if whirlpools:
        if len(whirlpools) != 2:
            raise ImportError("Only paired whirlpools are supported")
        pairs.append(
            {
                "kind": "whirlpool",
                "from": whirlpools[0]["visit"],
                "to": whirlpools[1]["visit"],
                "objects": [record["index"] for record in whirlpools],
            }
        )
    if any(record["type"] in (43, 44) for record in objects):
        raise ImportError("Unsupported one-way portal in Castle source")
    return pairs


def buildBoatRoutes(source: dict, blocked: set[tuple]) -> list[dict]:
    """A ferry adaptation of the original landing boats and western coastal boat."""
    if source["scenarioId"] != "homecoming":
        return []
    boats = {tuple(record["visit"]): record for record in source["objects"] if record["type"] == 8}
    boat_start, boat_end = (66, 59, 0), (6, 56, 0)
    if boat_start not in boats or boat_end not in boats:
        raise ImportError("The verified Homecoming ferry boats are missing")
    width = source["width"]
    water = {
        (index % width, index // width, 0)
        for index, tile in enumerate(source["terrain"][0])
        if tile[0] == 8 and (index % width, index // width, 0) not in blocked
    }
    previous = {boat_start: None}
    queue = deque([boat_start])
    while queue and boat_end not in previous:
        x, y, z = queue.popleft()
        for dx, dy in ((-1, 0), (0, -1), (1, 0), (0, 1)):
            neighbor = (x + dx, y + dy, z)
            if neighbor in water and neighbor not in previous:
                previous[neighbor] = (x, y, z)
                queue.append(neighbor)
    if boat_end not in previous:
        raise ImportError("Original source sea does not connect the two ferry boats")
    water_path = []
    current = boat_end
    while current is not None:
        water_path.append(list(current))
        current = previous[current]
    water_path.reverse()
    for shore in ((66, 58, 0), (7, 56, 0)):
        if shore in blocked or source["terrain"][0][shore[1] * width + shore[0]][0] in (8, 9):
            raise ImportError("Original ferry shore is not traversable")
    return [
        {
            "kind": "boat",
            "from": [66, 58, 0],
            "to": [7, 56, 0],
            "objects": [boats[boat_start]["index"], boats[boat_end]["index"]],
            "waterPath": water_path,
        }
    ]


def buildDiagonalRoutes(source: dict, blocked: set[tuple]) -> list[dict]:
    """Restore necessary original diagonal steps with a pruned spanning forest.

    The host engine otherwise moves cardinally. These are explicit adaptations,
    separate from the source portals; every edge joins adjacent original land
    cells and leaves terrain and object masks unchanged.
    """
    width = source["width"]
    walkable = {
        (index % width, index // width, z)
        for z, layer in enumerate(source["terrain"])
        for index, tile in enumerate(layer)
        if tile[0] not in (8, 9) and (index % width, index // width, z) not in blocked
    }
    parents = {point: point for point in walkable}

    def find(point):
        while parents[point] != point:
            parents[point] = parents[parents[point]]
            point = parents[point]
        return point

    def join(first, second):
        first, second = find(first), find(second)
        if first == second:
            return False
        parents[second] = first
        return True

    for x, y, z in sorted(walkable):
        for dx, dy in ((1, 0), (0, 1)):
            neighbor = (x + dx, y + dy, z)
            if neighbor in walkable:
                join((x, y, z), neighbor)
    transit = source["portals"] + source["boatRoutes"]
    for route in transit:
        first, second = tuple(route["from"]), tuple(route["to"])
        if first in walkable and second in walkable:
            join(first, second)
    components = {point: find(point) for point in walkable}
    reserved = {tuple(record["visit"]) for record in source["objects"] if record["visitable"]}
    required = {tuple(source["spawn"])}
    for record in source["objects"]:
        if record["type"] in (9, 10, 17, 34, 62, 70, 77, 83, 98, 214):
            required.add(tuple(record["visit"]))
    for route in transit:
        if route["kind"] != "whirlpool":
            required.update((tuple(route["from"]), tuple(route["to"])))
    if not required <= walkable:
        raise ImportError("A required source landmark is outside traversable land")
    required_components = {components[point] for point in required}
    candidates = []
    for first in sorted(walkable):
        x, y, z = first
        for dx in (-1, 1):
            second = (x + dx, y + 1, z)
            if second in walkable and components[first] != components[second]:
                candidates.append((int(first in reserved) + int(second in reserved), first, second))
    chosen = [(first, second) for _, first, second in sorted(candidates) if join(first, second)]
    if len({find(point) for point in required}) != 1:
        raise ImportError("Original diagonal routes cannot connect the required campaign landmarks")
    graph = defaultdict(dict)
    for index, (first, second) in enumerate(chosen):
        graph[components[first]][components[second]] = index
        graph[components[second]][components[first]] = index
    removed = set()
    leaves = deque(point for point in graph if len(graph[point]) == 1 and point not in required_components)
    while leaves:
        leaf = leaves.popleft()
        if not graph[leaf]:
            continue
        neighbor, index = next(iter(graph[leaf].items()))
        removed.add(index)
        graph[leaf].clear()
        del graph[neighbor][leaf]
        if len(graph[neighbor]) == 1 and neighbor not in required_components:
            leaves.append(neighbor)
    routes = [
        {"kind": "diagonalPassage", "from": list(first), "to": list(second)}
        for index, (first, second) in enumerate(chosen)
        if index not in removed
    ]
    if len(routes) > 64:
        raise ImportError("Castle diagonal navigation exceeds the reviewed 64-edge authoring budget")
    return routes


def buildNativeMap(source: dict, tileset: dict) -> dict:
    size = source["width"]
    layers = []
    blocked = set()
    visits = set()
    for record in source["objects"]:
        template = source["templates"][record["template"]]
        blocked.update(tuple(cell) for cell in footprint(template, record["anchor"], "blockMask", True))
        if record["visitable"]:
            visits.add(tuple(record["visit"]))
    blocked -= visits
    source["blockedCells"] = [list(cell) for cell in sorted(blocked) if 0 <= cell[0] < size and 0 <= cell[1] < size]
    source["boatRoutes"] = buildBoatRoutes(source, blocked)
    for z, terrain in enumerate(source["terrain"]):
        data = []
        for index, tile in enumerate(terrain):
            x, y = index % size, index // size
            gid = TERRAIN_GIDS[tile[0]]
            if (x, y, z) in blocked:
                gid = 12
            elif tile[4] and tile[0] not in (8, 9):
                gid = 15 if tile[2] else 6
            elif tile[2] and tile[0] not in (8, 9):
                gid = 14
            data.append(gid)
        properties = {
            "default": "MountainTile",
            "outOfBounds": "MountainTile",
            "level": str(z),
            "xBound": str(size - 1),
            "yBound": str(size - 1),
        }
        layers.append(
            {
                "type": "tilelayer",
                "name": f"Level {z} Floor",
                "height": size,
                "width": size,
                "opacity": 1,
                "visible": True,
                "x": 0,
                "y": 0,
                "properties": properties,
                "propertytypes": {key: "string" for key in properties},
                "data": data,
            }
        )
        layers.append(
            {
                "type": "objectgroup",
                "name": f"Level {z} Objects",
                "opacity": 1,
                "visible": True,
                "x": 0,
                "y": 0,
                "draworder": "topdown",
                "properties": {"level": str(z)},
                "propertytypes": {"level": "string"},
                "objects": [],
            }
        )
    heroes = [record for record in source["objects"] if record["type"] in HERO_TYPES and record.get("owner") == 0]
    primary = [
        record
        for record in heroes
        if (record.get("heroId") == 6 and record["type"] == 34)
        or (record["type"] == 70 and record.get("experience") == 1)
    ]
    if len(primary) != 1:
        raise ImportError("Expected exactly one Christian/primary carryover hero spawn")
    hero = primary[0]
    source["spawn"] = hero["visit"]
    source["diagonalRoutes"] = buildDiagonalRoutes(source, blocked)
    return {
        "width": size,
        "height": size,
        "tilewidth": 32,
        "tileheight": 32,
        "nextobjectid": 1,
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "tiledversion": "1.2.0",
        "type": "map",
        "version": 1.2,
        "properties": dict(zip(("x", "y", "z"), map(str, source["spawn"]))),
        "propertytypes": {"x": "string", "y": "string", "z": "string"},
        "layers": layers,
        "tilesets": [tileset],
    }


def importCampaign(
    source_path: Path, output_root: Path, author_module: Path | None = None, metadata_root: Path | None = None
) -> list[dict]:
    campaign = readLodEntry(source_path)
    if hashlib.sha256(campaign).hexdigest() != CAMPAIGN_SHA256:
        raise ImportError("GOOD1.H3C does not match the verified source edition; review its geography before importing")
    members = splitCampaign(campaign)
    sources = [readMap(data, name) for data, (name, _) in zip(members[1:], SCENARIOS)]
    if any(source["width"] != size or source["layers"] != 2 for source, (_, size) in zip(sources, SCENARIOS)):
        raise ImportError("Unexpected campaign scenario dimensions")
    repo_root = Path(__file__).resolve().parents[1]
    metadata_root = metadata_root or output_root.parent / "campaigns/longLiveTheQueen/sources"
    tileset = json.loads((repo_root / "res/maps/multilevel/map.json").read_text(encoding="utf-8"))["tilesets"][0]
    # The campaign's roads must not inherit RoadTile's healing behavior.
    tileset["tileproperties"]["5"]["type"] = "castleRoadTile"
    for index, tile_type in ((13, "castleRiverTile"), (14, "castleBridgeTile")):
        tileset["tileproperties"][str(index)] = {"type": tile_type}
        tileset["tilepropertytypes"][str(index)] = {"type": "string"}
    author = None
    if author_module:
        spec = importlib.util.spec_from_file_location("castle_campaign_author", author_module)
        author = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(author)
    documents = []
    for source in sources:
        native_map = buildNativeMap(source, tileset)
        if author:
            native_map = author.authorMap(native_map, source)
        documents.append((source, native_map))
    for source, native_map in documents:
        directory = output_root / source["mapId"]
        directory.mkdir(parents=True, exist_ok=True)
        metadata_root.mkdir(parents=True, exist_ok=True)
        (metadata_root / f"{source['mapId']}.json").write_text(
            json.dumps(source, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n"
        )
        (directory / "map.json").write_text(json.dumps(native_map, indent=2) + "\n", encoding="utf-8", newline="\n")
    return sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source", type=Path, help="Owner's Data/H3pbitma.lod")
    source_group.add_argument("--heroes-dir", type=Path, help="Owner's original Heroes III installation directory")
    parser.add_argument("--output-root", type=Path, default=Path(__file__).resolve().parents[1] / "res/maps")
    parser.add_argument(
        "--author-module",
        type=Path,
        default=Path(__file__).with_name("author_castle_campaign.py"),
        help="Gameplay authoring module",
    )
    parser.add_argument("--base-only", action="store_true", help="Emit geometry without gameplay authoring")
    parser.add_argument(
        "--metadata-root", type=Path, help="Source metadata directory outside runtime map config folders"
    )
    args = parser.parse_args()
    try:
        source_path = args.source or args.heroes_dir / "Data/H3pbitma.lod"
        sources = importCampaign(
            source_path, args.output_root, None if args.base_only else args.author_module, args.metadata_root
        )
    except (ImportError, OSError, zlib.error) as error:
        parser.exit(1, f"Castle campaign import failed: {error}\n")
    for source in sources:
        counts = Counter(record["type"] for record in source["objects"])
        print(
            f"{source['scenarioId']}: {source['width']}x{source['height']}x{source['layers']}, "
            f"{len(source['objects'])} source objects, {len(source['portals'])} portal pairs; "
            f"types={dict(sorted(counts.items()))}"
        )


if __name__ == "__main__":
    main()
