#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a bounded, factual city fixture; never export dialogue, artwork or original binaries."""

import argparse
from collections import Counter, deque
import json
from pathlib import Path
import re
import sys

try:
    from . import audit_candlekeep_source as source
except ImportError:
    import audit_candlekeep_source as source


SOURCES = {
    "areaCatalogue": "https://gibberlings3.github.io/iesdp/appendices/area_lists/bg1aref.htm",
    "areaFormat": "https://gibberlings3.github.io/iesdp/file_formats/ie_formats/are_v1.htm",
    "searchFormat": "https://gibberlings3.github.io/iesdp/appendices/search.html",
    "gameFormat": "https://gibberlings3.github.io/iesdp/file_formats/ie_formats/gam_v1.1.htm",
    "reputationRules": "https://gibberlings3.github.io/iesdp/files/2da/2da_tob/reputati.htm",
    "classicCity": "https://www.forgottenwars.com/bg1/ar0800.htm",
}
EDITION_ITEM_CONVERSIONS = {
    "OHRING16": {
        "original": "RING16",
        "reason": "Classic Petrine accepts an ordinary Angel Skin Ring",
        "source": "https://www.gamebanshee.com/baldursgate/walkthrough/baldursgatenorthern.php",
    },
    "OHAMUL13": {
        "original": "AMUL13",
        "reason": "Classic Arkion possession is an ordinary Bloodstone Amulet",
        "source": "https://www.forgottenwars.com/bg1/ar0800.htm",
    },
    "OHRING12": {
        "original": "RING12",
        "reason": "Classic Nemphre possession is an ordinary Onyx Ring",
        "source": "https://www.forgottenwars.com/bg1/ar1300.htm",
    },
}
EDITION_EXCLUDED_CREATURES = {
    "ULF": "Tales of the Sword Coast sea-chart quest",
    "KIERES": "Tales of the Sword Coast sea-chart quest",
    "NEMEKLIN": "Enhanced Edition Neera encounter",
    "NEERA": "Enhanced Edition companion",
    "DORN": "Enhanced Edition companion",
    "BDTARGET": "Siege of Dragonspear helper actor",
}


def chapterDepartureRule(parsed):
    """Normalize only the verified single-block Chapter7/DestroySelf script, never a general script."""
    text = parsed["compiled_text"]
    markers = [match for match in re.finditer(r'"[^"]*"|(?P<block>CR)(?=\s|$)', text) if match.group("block")]
    records = parsed["records"]
    triggers = [row for row in records if row["kind"] == "TR"]
    actions = [row for row in records if row["kind"] == "AC"]
    if len(markers) != 2 or len(triggers) != 1 or len(actions) != 1:
        raise source.AuditError("LEAVECH7 departure rule no longer has one condition/action block")
    trigger, action = triggers[0], actions[0]
    fields = trigger["integer_fields"]
    if not (
        (trigger.get("signature") or "").startswith("Global(")
        and trigger["strings"] == ["GLOBALChapter", ""]
        and len(fields) >= 2
        and fields[0] == 7
        and not fields[1] & 1
        and (action.get("signature") or "").startswith("DestroySelf(")
        and all(markers[0].start() < row["offset"] < markers[1].end() for row in records)
    ):
        raise source.AuditError("LEAVECH7 departure condition/action differs from the verified source rule")
    return {
        "condition": {"global": "Chapter", "scope": "GLOBAL", "equals": 7},
        "actions": ["DestroySelf"],
        "sourceStatus": "Supporting installed EE base script; classic BG1 behavior remains unverified.",
    }


def compiledSpawnFacts(parsed):
    text = parsed["compiled_text"]
    markers = [match for match in re.finditer(r'"[^"]*"|(?P<block>CR)(?=\s|$)', text) if match.group("block")]
    blocks = [(start.start(), end.end()) for start, end in zip(markers[::2], markers[1::2])]
    facts = []
    for record in parsed["records"]:
        signature = record.get("signature") or ""
        if record["kind"] != "AC" or not signature.lower().startswith("createcreature"):
            continue
        parameters = re.findall(r"S:([^,)]*)", signature)
        creatures = [
            value.upper()
            for parameter, value in zip(parameters, record["strings"])
            if source.referenceType(signature.split("(", 1)[0], parameter) == "CRE" and value
        ]
        block_number = next((i for i, (start, end) in enumerate(blocks) if start < record["offset"] < end), None)
        conditions = []
        if block_number is not None:
            start, end = blocks[block_number]
            for trigger in parsed["records"]:
                if trigger["kind"] == "TR" and start < trigger["offset"] < end:
                    fields = trigger["integer_fields"]
                    conditions.append(
                        {
                            "opcode": trigger["opcode"],
                            "signature": trigger["signature"],
                            "strings": trigger["strings"],
                            "integerFields": fields,
                            "negated": bool(fields[1] & 1) if len(fields) > 1 else None,
                        }
                    )
        integers = record["integer_fields"]
        for creature in creatures:
            facts.append(
                {
                    "creature": creature,
                    "opcode": record["opcode"],
                    "signature": signature,
                    "recordOffset": record["offset"],
                    "block": block_number,
                    "conditions": conditions,
                    "position": integers[1:3] if "P:" in signature and len(integers) >= 3 else None,
                    "integerFields": integers,
                    "conditionSemanticsEvaluated": False,
                }
            )
    return facts


def dialogueSpawnFacts(parsed, action_ids, trigger_ids):
    facts = []
    for number, transition in enumerate(parsed["transitions"]):
        text = transition["action"] or ""
        refs = source.textReferences(text, action_ids, trigger_ids)
        creates = [
            row for row in refs if row and row["type"] == "CRE" and row["reason"].lower().startswith("createcreature")
        ]
        for row in creates:
            point = re.search(
                r'CreateCreature\w*\("' + re.escape(row["name"]) + r'"\s*,\s*\[(-?\d+)\.(-?\d+)\]', text, re.I
            )
            state_ids = [
                i
                for i, state in enumerate(parsed["states"])
                if state["first_transition"] <= number < state["first_transition"] + state["transition_count"]
            ]
            triggers = [parsed["states"][i]["trigger"] or "" for i in state_ids] + [transition["trigger"] or ""]
            facts.append(
                {
                    "creature": row["name"],
                    "signature": row["reason"],
                    "transition": number,
                    "states": state_ids,
                    "position": [int(point.group(1)), int(point.group(2))] if point else None,
                    "conditionFunctions": sorted(
                        {name for trigger in triggers for name in re.findall(r"(\w+)\(", trigger)}
                    ),
                    "conditionSha256": [source.sha256(trigger.encode("ascii")) for trigger in triggers],
                    "conditionSemanticsEvaluated": False,
                }
            )
    return facts


def buildCityFixture(game_root, language="en_US", encoding=None, *, itemEffects=False):
    index = source.ResourceIndex(game_root)
    if not re.fullmatch(r"[A-Za-z]{2}_[A-Za-z]{2}", language):
        raise source.AuditError("language must be a locale such as en_US")
    is_ee = (index.root / "engine.lua").exists() or (index.root / "Baldur.lua").exists()
    tlk_relative = (
        f"lang/{language}/dialog.tlk" if (index.root / "lang" / language / "dialog.tlk").exists() else "dialog.tlk"
    )
    talk_path = source.safePath(index.root, tlk_relative)
    talk = source.TalkTable(talk_path, encoding or ("utf-8" if is_ee else "cp1252"))
    fixture = {
        "schemaVersion": 1,
        "scope": "baldursGateCity",
        "sourceEdition": (
            "installed BG1EE base archives; supporting evidence only"
            if is_ee
            else "classic candidate; not authenticated"
        ),
        "originalParityEstablished": False,
        "sources": SOURCES,
        "keySha256": index.key_hash,
        "tlkSha256": source.hashFile(talk_path),
        "language": language,
        "overrideCount": len(index.overrides),
        "exteriors": source.CITY_EXTERIORS,
        "underground": source.CITY_UNDERGROUND,
        "boundaries": source.CITY_BOUNDARIES,
        "editionItemConversions": EDITION_ITEM_CONVERSIONS,
        "editionExcludedCreatures": EDITION_EXCLUDED_CREATURES,
        "editionExcludedItems": {
            "MISC1C": "Tales of the Sword Coast sea charts",
            "SW1H43": "Enhanced Edition weapon",
            "SW1H46": "Enhanced Edition weapon",
            "SW1H48": "Enhanced Edition weapon",
        },
        "excludedAreaResources": sorted(
            name for name, ext in index.entries if ext == "ARE" and name not in source.CITY_AREA_IDS
        ),
        "editionPolicy": {
            "included": "Explicit 212-area city manifest; no resource-prefix inclusion",
            "outsideAreas": "Every area outside the explicit manifest is excluded from playable scope",
            "tales": "No Tales of the Sword Coast areas included; original base payloads remain unauthenticated",
            "ee": "EE-added areas excluded; EE changes inside shared areas and script-spawned actors remain unresolved",
            "mods": "Overrides excluded from payload selection; KEY bytes can still contain installed changes",
        },
        "searchMapRule": {
            "sourceCellPixels": [16, 12],
            "encoding": "Each row alternates run length, raw terrain index, starting at x=0; rows top to bottom",
            "supportingBlockedIndices": sorted(source.SEARCH_MAP_BLOCKED),
            "authority": SOURCES["searchFormat"],
            "limitation": "IESDP documents BG2 terrain rules; original BG1 terrain and door-state parity needs review",
        },
        "areas": {},
        "creatures": {},
        "items": {},
        "stores": {},
        "references": {},
        "worldMapLinks": [],
        "scriptedActors": [],
        "campaignNpcs": [],
        "numericSourceRules": {},
        "scriptSourceRules": {},
        "unresolved": [],
        "uncertainties": [
            "No authenticated original BG1 base installation; EE archive bytes do not prove classic parity",
            "Area membership has geographic corroboration, but individual EE-added interactions require reconciliation",
            "Script-spawned actors are structural candidates; chapter and shared-script conditions remain unaudited",
            "Campaign GAM recruitment and NPC level-variant selection require original-game verification",
            "Search-map indices retain source collision metadata; native aggregation can change corridor topology",
            "Original dialogue text, artwork and binaries are intentionally absent",
            "Dudleyville includes explicitly labelled DudleyFixes branches; those do not establish original behavior",
        ],
    }
    pending_refs = set()
    resource_areas, children, spawn_facts = {}, {}, {}
    ids = {name: source.parseIds(index.read(name, "IDS", "base")[0]) for name in ("ACTION", "TRIGGER")}

    def addReferences(refs, area_id=None):
        pending_refs.update((row["name"], row["type"]) for row in refs if row)
        if area_id:
            for row in refs:
                if row:
                    resource_areas.setdefault((row["name"], row["type"]), set()).add(area_id)

    def creatureMetadata(data, area_id=None):
        parsed, refs, _ = source.parseCreature(data)
        addReferences(refs, area_id)
        name = talk.get(parsed["name_strref"])
        parsed["displayName"] = name.get("text", "") if name else ""
        reader = source.Binary(data)
        slots = reader.number(0x2B8)
        parsed["itemSlots"] = [reader.number(slots + n * 2, "H") for n in range(40)] if slots else []
        return parsed

    for area_id in sorted(source.CITY_AREA_IDS):
        data, origin = index.read(area_id, "ARE", "base")
        parsed, refs, _ = source.parseArea(data)
        addReferences(refs, area_id)
        wed_data, _ = index.read(parsed["wed"], "WED", "base")
        wed = source.Binary(wed_data)
        wed.signature(b"WED V1.3", 32)
        overlay = wed.number(16)
        parsed["dimensions"] = [wed.number(overlay, "H") * 64, wed.number(overlay + 2, "H") * 64]
        parsed["sha256"] = source.sha256(data)
        parsed["origin"] = origin
        parsed["wedSha256"] = source.sha256(wed_data)
        parsed["classification"] = (
            "exterior"
            if area_id in source.CITY_EXTERIORS
            else "underground" if area_id in source.CITY_UNDERGROUND else "interior"
        )
        parsed["label"] = source.CITY_EXTERIORS.get(area_id, source.CITY_UNDERGROUND.get(area_id, area_id))
        search_name = parsed["wed"] + "SR"
        try:
            search_data, _ = index.read(search_name, "BMP", "base")
            parsed["searchMap"] = {**source.parseSearchMap(search_data), "sha256": source.sha256(search_data)}
        except (source.AuditError, OSError) as error:
            fixture["unresolved"].append({"resource": search_name + ".BMP", "error": str(error)})
        parsed.pop("items")  # Each item's actual container retains its complete fixed record.
        for number, actor in enumerate(parsed["actors"], 1):
            actor["sourceId"] = f"{area_id}#actor{number}"
            creature_id = actor["creature"]
            if "embedded_creature" in actor:
                creature_id = f"{area_id}#embedded{number}"
                fixture["creatures"][creature_id] = actor.pop("embedded_creature")
            elif creature_id and creature_id not in fixture["creatures"]:
                try:
                    creature_data, _ = index.read(creature_id, "CRE", "base")
                    fixture["creatures"][creature_id] = {
                        **creatureMetadata(creature_data, area_id),
                        "sha256": source.sha256(creature_data),
                    }
                except (source.AuditError, OSError) as error:
                    fixture["unresolved"].append({"resource": creature_id + ".CRE", "error": str(error)})
            creature = fixture["creatures"].get(creature_id, {})
            addReferences(
                [source.reference(name, "BCS", "placed creature script") for name in creature.get("scripts", [])]
                + [source.reference(creature.get("dialogue", ""), "DLG", "placed creature dialogue")],
                area_id,
            )
            actor["displayName"] = creature.get("displayName", "")
            actor["creatureMetadata"] = creature_id
            actor["creatureSha256"] = creature.get("sha256", actor.get("embedded_creature_sha256", ""))
        for number, container in enumerate(parsed["containers"], 1):
            container["sourceId"] = f"{area_id}#container{number}"
        for number, region in enumerate(parsed["regions"], 1):
            region["sourceId"] = f"{area_id}#region{number}"
        fixture["areas"][area_id] = parsed

    def resolveEntrance(area_id, name):
        area = fixture["areas"].get(area_id)
        if not area:
            return None
        matches = [row["position"] for row in area["entrances"] if row["name"].casefold() == name.casefold()]
        return matches[0] if len(matches) == 1 else None

    for area_id, area in fixture["areas"].items():
        for region in area["regions"]:
            if region["destination"]:
                region["destinationPosition"] = resolveEntrance(region["destination"], region["entrance"])
                region["outsideCity"] = region["destination"] not in source.CITY_AREA_IDS
    world_data, _ = index.read("WORLDMAP", "WMP", "base")
    world, _, _ = source.parseWorldMap(world_data)
    fixture["worldMapSha256"] = source.sha256(world_data)
    world_areas = {row["area"]: row for group in world["worlds"] for row in group["areas"]}
    for area_id in source.CITY_EXTERIORS:
        for link in world_areas.get(area_id, {}).get("links", []):
            target = link["destination"]
            reverse = [row for row in world_areas.get(target, {}).get("links", []) if row["destination"] == area_id]
            fixture["worldMapLinks"].append(
                {
                    **link,
                    "source": area_id,
                    "sourcePosition": resolveEntrance(area_id, reverse[0]["entrance"]) if len(reverse) == 1 else None,
                    "destinationPosition": resolveEntrance(target, link["entrance"]),
                    "outsideCity": target not in source.CITY_AREA_IDS,
                }
            )

    game_data, game_origin = index.read("BALDUR", "GAM", "base")
    game, _, _ = source.parseGame(game_data)
    fixture["campaignGame"] = {
        "resource": "BALDUR.GAM",
        "sha256": source.sha256(game_data),
        "origin": game_origin,
        "version": game["version"],
        "nonPartyCount": len(game["non_party_members"]),
        "partyCount": len(game["party_members"]),
    }
    if ("BALDUR", "GAM") in index.overrides:
        effective_game, _ = index.read("BALDUR", "GAM", "effective")
        fixture["campaignGame"]["overrideDiffers"] = source.sha256(effective_game) != source.sha256(game_data)
    for actor in game["non_party_members"]:
        area_id, creature_id = actor["area"], actor["creature"]
        if area_id not in source.CITY_AREA_IDS and creature_id not in {"QUAYLE", "ELDOTH"}:
            continue
        actor = dict(actor)
        actor["sourceId"] = "BALDUR.GAM#npc" + str(actor["sourceIndex"])
        actor["sourceSha256"] = fixture["campaignGame"]["sha256"]
        actor["scopeClassification"] = (
            "city"
            if area_id in source.CITY_AREA_IDS
            else "boundaryHistory" if area_id in source.CITY_BOUNDARIES else "externalHistory"
        )
        actor["scopePolicy"] = (
            "Factual city placement; source recruitment and level checks remain pending."
            if area_id in source.CITY_AREA_IDS
            else "Explicit gate excursion/history may recruit a persistent native follower; source area is not playable."
        )
        try:
            if "embedded_creature" in actor:
                creature_id = actor["sourceId"]
                actor.pop("embedded_creature")
                offset, size = actor["embedded_creature_offset"], actor["embedded_creature_size"]
                creature = creatureMetadata(
                    game_data[offset : offset + size], area_id if area_id in source.CITY_AREA_IDS else None
                )
                creature["sha256"] = actor["embedded_creature_sha256"]
                fixture["creatures"][creature_id] = creature
            elif creature_id not in fixture["creatures"]:
                creature_data, _ = index.read(creature_id, "CRE", "base")
                fixture["creatures"][creature_id] = {
                    **creatureMetadata(creature_data, area_id if area_id in source.CITY_AREA_IDS else None),
                    "sha256": source.sha256(creature_data),
                }
            creature = fixture["creatures"][creature_id]
            actor["creatureMetadata"] = creature_id
            actor["creatureSha256"] = creature["sha256"]
            name_text = talk.get(creature["name_strref"])
            actor["displayName"] = name_text.get("text", "") if name_text else ""
            if not actor["embedded_creature_size"]:
                addReferences([source.reference(actor["creature"], "CRE", "GAM recruitment candidate")])
        except (source.AuditError, OSError) as error:
            fixture["unresolved"].append({"resource": creature_id + ".CRE", "error": str(error)})
        fixture["campaignNpcs"].append(actor)

    reputation_data, reputation_origin = index.read("REPUTATI", "2DA", "base")
    reputation, _, _ = source.parseNumericTwoDa(reputation_data)
    fixture["numericSourceRules"]["REPUTATI.2DA"] = {
        **reputation,
        "sha256": source.sha256(reputation_data),
        "origin": reputation_origin,
        "sourceStatus": "Supporting installed EE base table; classic BG1 parity remains unverified.",
        "donationColumns": {"threshold": "BASE_CHURCH", "modifier": "MONEY_CHURCH"},
        "interpretation": "Raw numeric cells only; native reputation-unit conversion and donation outcomes require validation.",
    }

    # Follow resource identifiers only. Parsed dialogue/script text never enters the fixture.
    queue = deque(sorted(pending_refs))
    seen = set()
    while queue:
        name, ext = queue.popleft()
        if (name, ext) in seen or ext not in {"BCS", "DLG", "ITM", "CRE", "SPL", "STO"}:
            continue
        seen.add((name, ext))
        if len(seen) > 3000:
            raise source.AuditError("city factual dependency closure exceeds 3000 resources")
        try:
            data, origin = index.read(name, ext, "base")
            row = {"sha256": source.sha256(data), "size": len(data), "origin": origin}
            if (name, ext) in index.overrides:
                effective, _ = index.read(name, ext, "effective")
                row["overrideDiffers"] = source.sha256(effective) != row["sha256"]
            if ext == "DLG":
                parsed, refs, _ = source.parseDialogue(data)
                row["states"] = len(parsed["states"])
                row["transitions"] = len(parsed["transitions"])
                for pool in ("state_triggers", "transition_triggers", "actions"):
                    for text in parsed[pool]:
                        refs.extend(source.textReferences(text, ids["ACTION"], ids["TRIGGER"]))
                row["storeReferences"] = sorted({ref["name"] for ref in refs if ref and ref["type"] == "STO"})
                spawn_facts[(name, ext)] = dialogueSpawnFacts(parsed, ids["ACTION"], ids["TRIGGER"])
                children[(name, ext)] = [(ref["name"], ref["type"]) for ref in refs if ref]
                queue.extend((ref["name"], ref["type"]) for ref in refs if ref)
            elif ext == "BCS":
                parsed, refs, _ = source.parseScript(data, ids["ACTION"], ids["TRIGGER"])
                if name == "LEAVECH7":
                    fixture["scriptSourceRules"]["LEAVECH7.BCS"] = {
                        **chapterDepartureRule(parsed),
                        "sha256": row["sha256"],
                    }
                row["storeReferences"] = sorted({ref["name"] for ref in refs if ref and ref["type"] == "STO"})
                spawn_facts[(name, ext)] = compiledSpawnFacts(parsed)
                children[(name, ext)] = [(ref["name"], ref["type"]) for ref in refs if ref]
                queue.extend((ref["name"], ref["type"]) for ref in refs if ref)
            elif ext == "CRE":
                if name not in fixture["creatures"]:
                    fixture["creatures"][name] = {**creatureMetadata(data), "sha256": row["sha256"]}
                _, refs, _ = source.parseCreature(data)
                children[(name, ext)] = [(ref["name"], ref["type"]) for ref in refs if ref]
                queue.extend(children[(name, ext)])
            elif ext == "ITM":
                parsed, _, _ = source.parseItem(data, itemEffects=True) if itemEffects else source.parseItem(data)
                name_text = talk.get(parsed["identified_name_strref"])
                row["displayName"] = name_text.get("text", "") if name_text else ""
                unidentified = talk.get(parsed["name_strref"])
                fixture["items"][name] = {
                    **parsed,
                    "displayName": row["displayName"],
                    "sha256": row["sha256"],
                    "unidentifiedName": unidentified.get("text", "") if unidentified else "",
                    "excludedAddition": name in fixture["editionExcludedItems"],
                    "editionClassification": (
                        "eeIdentitySubstitution"
                        if name in EDITION_ITEM_CONVERSIONS
                        else (
                            "excludedKnownEeAddition"
                            if name in {"SW1H43", "SW1H46", "SW1H48"}
                            else "originalBaseCandidateUnverified"
                        )
                    ),
                }
            elif ext == "STO":
                parsed, refs, _ = source.parseStore(data)
                name_text = talk.get(parsed["name_strref"])
                parsed["displayName"] = name_text.get("text", "") if name_text else ""
                parsed["sha256"] = row["sha256"]
                parsed["excludedEeStock"] = [
                    entry for entry in parsed["stock"] if entry["item"] in {"SW1H43", "SW1H46", "SW1H48"}
                ]
                parsed["stock"] = [
                    entry for entry in parsed["stock"] if entry["item"] not in {"SW1H43", "SW1H46", "SW1H48"}
                ]
                for drink in parsed["drinks"]:
                    name_text = talk.get(drink["name_strref"])
                    drink["displayName"] = name_text.get("text", "") if name_text else ""
                fixture["stores"][name] = parsed
                queue.extend((ref["name"], ref["type"]) for ref in refs if ref)
            fixture["references"][name + "." + ext] = row
        except (source.AuditError, OSError) as error:
            fixture["unresolved"].append({"resource": name + "." + ext, "error": str(error)})
    context_queue = deque((key, area_id) for key, areas in resource_areas.items() for area_id in areas)
    visited_contexts = set()
    while context_queue:
        key, area_id = context_queue.popleft()
        if (key, area_id) in visited_contexts:
            continue
        visited_contexts.add((key, area_id))
        resource_areas.setdefault(key, set()).add(area_id)
        context_queue.extend((child, area_id) for child in children.get(key, []))
    for key, facts in sorted(spawn_facts.items()):
        contexts = (
            [key[0]] if key[1] == "BCS" and key[0] in source.CITY_AREA_IDS else sorted(resource_areas.get(key, []))
        )
        for number, fact in enumerate(facts):
            creature = fixture["creatures"].get(fact["creature"], {})
            fixture["scriptedActors"].append(
                {
                    **fact,
                    "sourceResource": ".".join(key),
                    "sourceSha256": fixture["references"][".".join(key)]["sha256"],
                    "sourceId": ".".join(key) + "#spawn" + str(number),
                    "areas": contexts,
                    "displayName": creature.get("displayName", ""),
                    "creatureSha256": creature.get("sha256", ""),
                    "scopeStatus": "structural candidate; conditions and shared-script area context require review",
                    "excludedAddition": fact["creature"] in EDITION_EXCLUDED_CREATURES,
                }
            )
    for creature_id, creature in fixture["creatures"].items():
        creature["excludedAddition"] = creature_id in EDITION_EXCLUDED_CREATURES
    fixture["counts"] = {
        "areas": len(fixture["areas"]),
        "campaignNpcs": len(fixture["campaignNpcs"]),
        "classifications": dict(Counter(row["classification"] for row in fixture["areas"].values())),
        **{
            key: sum(len(area[key]) for area in fixture["areas"].values())
            for key in ("actors", "regions", "containers", "doors")
        },
    }
    return fixture


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--language", default="en_US")
    parser.add_argument("--encoding", help="override the source TLK encoding")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--item-effects", action="store_true", help="decode bounded ITM V1 inline fields without following resources"
    )
    args = parser.parse_args(argv)
    root, output = args.game_root.resolve(), args.output.resolve()
    if output == root or output.is_relative_to(root):
        parser.error("output must be outside the original game installation")
    item_options = {"itemEffects": True} if args.item_effects else {}
    fixture = buildCityFixture(root, args.language, args.encoding, **item_options)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(fixture, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "bytes": output.stat().st_size,
                "counts": fixture["counts"],
                "unresolved": len(fixture["unresolved"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
