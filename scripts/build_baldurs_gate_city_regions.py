# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Project factual non-travel ARE regions; unsupported effects never become guessed native damage."""

import json
import math
from collections import Counter

SOURCE_PIXELS_PER_CELL = 64
MAX_CANDIDATE_CELLS = 4096
AREA_FORMAT = "https://gibberlings3.github.io/iesdp/file_formats/ie_formats/are_v1.htm"


def areaBounds(atlas, area_id):
    row = atlas[area_id]
    bounds = row["bounds"] if isinstance(row, dict) else row
    if len(bounds) != 5 or any(type(value) is not int for value in bounds) or min(bounds[3:]) <= 0:
        raise ValueError("Malformed native atlas bounds: " + area_id)
    return bounds


def clipPolygon(polygon, axis, boundary, keep_greater):
    """Clip a simple polygon against one cell edge, retaining the source's concave outline."""
    if not polygon:
        return []
    output = []
    previous = polygon[-1]
    previous_inside = previous[axis] >= boundary if keep_greater else previous[axis] <= boundary
    for point in polygon:
        inside = point[axis] >= boundary if keep_greater else point[axis] <= boundary
        if inside != previous_inside:
            fraction = (boundary - previous[axis]) / (point[axis] - previous[axis])
            intersection = [previous[n] + fraction * (point[n] - previous[n]) for n in (0, 1)]
            intersection[axis] = boundary
            output.append(intersection)
        if inside:
            output.append(point)
        previous, previous_inside = point, inside
    return output


def polygonArea(polygon):
    return (
        abs(
            sum(
                first[0] * second[1] - second[0] * first[1] for first, second in zip(polygon, polygon[1:] + polygon[:1])
            )
        )
        / 2
    )


def regionCells(polygon, bounds):
    """Include each 64px source cell with positive polygon overlap; edge contact alone is insufficient."""
    if len(polygon) < 3 or any(len(point) != 2 or any(type(n) is not int for n in point) for point in polygon):
        raise ValueError("Region needs an explicit integer source polygon")
    if polygonArea(polygon) == 0:
        raise ValueError("Region polygon has no area")
    x, y, z, width, height = bounds
    left = max(0, math.floor(min(point[0] for point in polygon) / SOURCE_PIXELS_PER_CELL))
    top = max(0, math.floor(min(point[1] for point in polygon) / SOURCE_PIXELS_PER_CELL))
    right = min(width - 1, math.ceil(max(point[0] for point in polygon) / SOURCE_PIXELS_PER_CELL) - 1)
    bottom = min(height - 1, math.ceil(max(point[1] for point in polygon) / SOURCE_PIXELS_PER_CELL) - 1)
    candidate_cells = max(0, right - left + 1) * max(0, bottom - top + 1)
    if candidate_cells > MAX_CANDIDATE_CELLS:
        raise ValueError("Region projection exceeds its bounded cell budget")
    cells = []
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            clipped = polygon
            for axis, boundary, keep_greater in (
                (0, column * 64, True),
                (0, (column + 1) * 64, False),
                (1, row * 64, True),
                (1, (row + 1) * 64, False),
            ):
                clipped = clipPolygon(clipped, axis, boundary, keep_greater)
            if polygonArea(clipped) > 0:
                cells.append([x + column, y + row, z])
    if not cells:
        raise ValueError("Source region has no overlap with its native area")
    return cells, candidate_cells


def buildRegions(source, atlas, config, objects, *, usablePosition, region_manifest=None):
    """Append region objects/config using the caller's collision-safe anchor allocator; return provenance."""
    rows = []
    candidate_cells = 0
    used_ids = {record["id"] for records in objects.values() for record in records}
    next_id = max(used_ids, default=0) + 1
    source_ids = set()
    for area_id, area in sorted(source["areas"].items()):
        bounds = areaBounds(atlas, area_id)
        for index, region in enumerate(area.get("regions", []), 1):
            if region.get("destination"):
                continue
            source_id = region.get("sourceId", f"{area_id}#region{index}")
            if source_id in source_ids:
                raise ValueError("Duplicate non-travel region source identity: " + source_id)
            source_ids.add(source_id)
            region_type = region["type"]
            if region_type not in {0, 1}:
                raise ValueError("Unsupported non-travel region type: " + source_id)
            name = "city" + area_id.title() + "Region" + str(index)
            if name in config:
                raise ValueError("Region resource identity already exists: " + name)
            cells, candidates = regionCells(region["polygon"], bounds)
            candidate_cells += candidates
            flags, script = region["flags"], region.get("script", "")
            text_pending = region_type == 1 and not flags & 128 and region["text_strref"] not in {-1, 0xFFFFFFFF}
            script_metadata = source.get("references", {}).get(script + ".BCS", {}) if script else {}
            script_status = "unsupportedScript" if script_metadata else "missingScript" if script else "noScript"
            point = (
                region["use_point"]
                if flags & 1024
                else [
                    (region["bounding_box"][0] + region["bounding_box"][2]) // 2,
                    (region["bounding_box"][1] + region["bounding_box"][3]) // 2,
                ]
            )
            position = list(usablePosition(area_id, point, reserve=True))
            x, y, z, width, height = bounds
            if (
                len(position) != 3
                or position[2] != z
                or not (x <= position[0] < x + width and y <= position[1] < y + height)
            ):
                raise ValueError("Region anchor allocator escaped its native area: " + source_id)
            props = {
                "label": "Information point" if region_type == 1 else "",
                "animation": "images/misc/signpost" if region_type == 1 else "",
                "canStep": True,
                "sourceArea": area_id,
                "simulationRegion": area_id,
                "sourceRegion": source_id,
                "sourceRegionName": region["name"],
                "sourceRegionType": region_type,
                "sourceFlags": flags,
                "sourceScript": script,
                "sourceScriptSha256": script_metadata.get("sha256", ""),
                "sourceTextStrref": region["text_strref"],
                "sourceKey": region.get("key", ""),
                "sourceTrapDetection": region["trap_difficulty"],
                "sourceTrapRemoval": region["trap_removal"],
                "trapped": bool(region["trapped"]),
                "sourceKeyRequired": bool(flags & 1),
                "sourceResetTrap": bool(flags & 2),
                "sourceDetectable": bool(flags & 8),
                "sourceNpcActivates": bool(flags & 16),
                "sourceTutorialOnly": bool(flags & 32),
                "sourceAnyoneActivates": bool(flags & 64),
                "sourceNoString": bool(flags & 128),
                "sourceDeactivated": bool(flags & 256),
                "sourcePartyOnly": bool(flags & 512),
                "sourceAlternativePoint": bool(flags & 1024),
                "sourceDoorClosed": bool(flags & 2048),
                "regionEnabled": not bool(flags & (32 | 256)),
                "regionCells": json.dumps(cells, separators=(",", ":")),
                "sourceRegionPolygon": json.dumps(region["polygon"], separators=(",", ":")),
                "sourceRegionBounds": json.dumps(region["bounding_box"], separators=(",", ":")),
                "sourceUsePoint": json.dumps(region["use_point"], separators=(",", ":")),
                "regionScriptStatus": script_status,
                "regionScriptPending": bool(script),
                "regionInfoTextPending": bool(text_pending),
                "regionEffectApproved": False,
                "regionDamageSupported": False,
                "forbidDetecting": not bool(flags & 8) or region["trap_difficulty"] >= 100,
                "disarmAgility": 18 if region["trap_removal"] >= 80 else 16 if region["trap_removal"] >= 40 else 12,
            }
            config[name] = {"class": "BaldursGateRegion", "properties": props}
            objects.setdefault(z, []).append(
                {
                    "id": next_id,
                    "name": name,
                    "type": name,
                    "x": position[0] * 32,
                    "y": position[1] * 32,
                    "width": 32,
                    "height": 32,
                    "rotation": 0,
                    "visible": region_type == 1,
                }
            )
            next_id += 1
            rows.append(
                {
                    "sourceId": source_id,
                    "sourceArea": area_id,
                    "sourceAreaSha256": area["sha256"],
                    "object": name,
                    "position": position,
                    "cells": cells,
                    "type": region_type,
                    "flags": flags,
                    "trapped": bool(region["trapped"]),
                    "script": script,
                    "scriptStatus": script_status,
                    "textStrref": region["text_strref"],
                    "infoTextPending": bool(text_pending),
                    "effectApproved": False,
                    "damageSupported": False,
                    "anchorOutsideProjectedRegion": position not in cells,
                }
            )
    result = {
        "schemaVersion": 1,
        "formatAuthority": AREA_FORMAT,
        "sourcePixelsPerNativeCell": 64,
        "originalParityEstablished": False,
        "regions": rows,
        "unsupportedScripts": sorted({row["script"] for row in rows if row["script"]}),
        "conversion": "All cells with positive source-polygon overlap; 64px aggregation can widen a footprint. Anchors may move to native walkable cells; projected activation cells never move with them.",
        "effectPolicy": "Unsupported scripts and unrewritten info text are pending. Never apply guessed damage, remove a trap or award completion for a pending effect.",
        "counts": {
            "regions": len(rows),
            "types": dict(sorted(Counter(str(row["type"]) for row in rows).items())),
            "trapped": sum(row["trapped"] for row in rows),
            "candidateCells": candidate_cells,
            "projectedCells": sum(len(row["cells"]) for row in rows),
        },
    }
    if region_manifest is not None:
        region_manifest.clear()
        region_manifest.update(result)
        return region_manifest
    return result
