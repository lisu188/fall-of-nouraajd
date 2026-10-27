#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Inventory city source obligations and current adaptation mappings without awarding gameplay parity."""

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

if __package__:
    from scripts.build_baldurs_gate_seven_suns_ledger import WARNING_PATH, addWarningObligations
else:
    from build_baldurs_gate_seven_suns_ledger import WARNING_PATH, addWarningObligations

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = "tests/fixtures/baldurs_gate_city_source.json"
QUEST_PATH = "tests/fixtures/baldurs_gate_city_quests.json"
CONFIG_PATH = "res/maps/baldursGate/config.json"
SCRIPT_PATH = "res/maps/baldursGate/script.py"
OUTPUT_PATH = "tests/fixtures/baldurs_gate_city_ledger.json"
STATUSES = {"missing", "planned", "partial", "excluded"}
SOURCE_GAP = "The target is original BG1 base; installed EE metadata cannot establish classic behavior."
NATIVE_GAP = "No exact-head native route, save/reload, visual, or owner acceptance evidence is attached."


def readJson(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def methodNames(script):
    return {
        node.name: {child.name for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for node in ast.walk(ast.parse(script))
        if isinstance(node, ast.ClassDef)
    }


def selectorsMatch(properties, selector, target=""):
    return (
        (not selector.get("area") or selector["area"] == properties.get("sourceArea"))
        and (not selector.get("creature") or selector["creature"] == properties.get("sourceCreature"))
        and (
            not selector.get("label")
            or selector["label"].strip().casefold() == properties.get("label", "").strip().casefold()
            or selector["label"] == target
        )
    )


def dialogActions(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"action", "condition"} and isinstance(child, str):
                yield child
            else:
                yield from dialogActions(child)
    elif isinstance(value, list):
        for child in value:
            yield from dialogActions(child)


def buildLedger(source, quests, config, script, warning=None):
    """All obligations originate in source rows, never in the set of implemented objects."""
    entries = []
    methods = methodNames(script)
    indexed = defaultdict(list)
    for name, record in sorted(config.items()):
        for key, value in record.get("properties", {}).items():
            if key.startswith("source") and isinstance(value, str):
                indexed[(key, value)].append(name)
    clock = config.get("cityClock", {}).get("properties", {})
    actor_definitions = {
        row["id"]: row for row in json.loads(clock.get("actorDefinitions", "[]").removeprefix("city-json:"))
    }
    geometry_doors = {
        row["sourceDoor"] for row in json.loads(clock.get("geometryDoors", "[]").removeprefix("city-json:"))
    }
    actor_configs = {
        name: record["properties"]
        for name, record in config.items()
        if record.get("properties", {}).get("sourceCreature")
    }
    actor_dialogs = defaultdict(list)
    for name, record in config.items():
        if record.get("properties", {}).get("actorId"):
            actor_dialogs[record["properties"]["actorId"]].append((name, set(dialogActions(record))))

    def evidence(pointer, sha256="", resource="", quest=False):
        value = {"fixture": QUEST_PATH if quest else SOURCE_PATH, "pointer": pointer}
        if sha256:
            value["sha256"] = sha256
        if resource:
            value["resource"] = resource
        return value

    def add(
        obligation_id,
        family,
        proof,
        *,
        area="",
        facts=None,
        prerequisites=None,
        choices=None,
        effects=None,
        ownership=None,
        timers=None,
        conversion=None,
        targets=None,
        status=None,
        gaps=None,
        excluded="",
        phase=None,
        callbacks=None,
        urls=None,
    ):
        targets = sorted(set(targets or []))
        status = "excluded" if excluded else status or ("partial" if targets else "missing")
        row = {
            "id": obligation_id,
            "family": family,
            "evidence": proof,
            "phase": phase or {"source": "conditions not fully interpreted", "scenarioChapters": [5, 7]},
            "prerequisites": prerequisites or {},
            "choices": choices or [],
            "effects": effects or {},
            "ownership": ownership or {},
            "timers": timers or {},
            "nativeConversion": conversion or {},
            "implementation": {"status": status, "targets": targets, "callbacks": callbacks or []},
            "testStatus": {"inventoryContract": "structural only", "native": "pending", "coverage": "not established"},
            "editionDifferences": [SOURCE_GAP] + ([excluded] if excluded else []),
            "gaps": ([] if excluded else list(gaps or [])),
        }
        if area:
            row["area"] = area
        if facts:
            row["facts"] = facts
        if urls:
            row["sourceUrls"] = urls
        entries.append(row)

    def selectTargets(selectors):
        return sorted(
            name
            for name, properties in actor_configs.items()
            if any(selectorsMatch(properties, selector, name) for selector in selectors)
        )

    for index, actor in enumerate(source.get("campaignNpcs", [])):
        source_id = actor["sourceId"]
        targets = sorted(
            set(
                indexed[("sourceCampaignNpc", source_id)]
                + indexed[("sourceGameNpc", source_id)]
                + indexed[("sourceActor", source_id)]
            )
        )
        cre = source["creatures"].get(actor.get("creatureMetadata", actor["creature"]), {})
        proof = [evidence(f"/campaignNpcs/{index}", actor["sourceSha256"], "BALDUR.GAM")]
        if cre.get("sha256"):
            proof.append(
                evidence(
                    "/creatures/" + actor.get("creatureMetadata", actor["creature"]),
                    cre["sha256"],
                    actor["creature"] + ".CRE",
                )
            )
        add(
            source_id,
            "campaignNpc",
            proof,
            area=actor["area"],
            targets=targets,
            facts={key: value for key, value in actor.items() if key not in {"sourceSha256", "creatureSha256"}},
            ownership={"owner": source_id, "items": cre.get("items", []), "gold": cre.get("gold", 0)},
            prerequisites={"selectionFlags": actor["selection_flags"], "partyOrder": actor["party_order"]},
            timers={"sourceTalkCount": actor["talk_count"]},
            conversion={
                "recruitment": "Persistent native follower; original companion checks/interactions need audit.",
                "explicitHistoryRequired": actor["scopeClassification"] != "city",
                "outsidePlayableAreaForbidden": actor["scopeClassification"] != "city",
            },
            gaps=[
                "GAM position/state does not establish recruitment, party interaction, departure or level-variant behavior."
            ],
        )
        if cre.get("dialogue"):
            dialogs = [
                name
                for target in targets
                for name, actions in actor_dialogs[target]
                if any(action.startswith(("accept", "quest")) for action in actions)
            ]
            add(
                source_id + ":conversation",
                "actorConversation",
                proof,
                area=actor["area"],
                targets=dialogs,
                facts={"dialogue": cre["dialogue"]},
                gaps=["Generic recruitment/Speak callbacks do not cover original NPC and party DLG branches."],
            )

    for area_id, area in sorted(source["areas"].items()):
        prefix = "/areas/" + area_id
        sha256 = area["sha256"]
        if area.get("rest_interruptions"):
            add(
                area_id + ":restInterruptions",
                "restInterruption",
                [evidence(prefix + "/rest_interruptions", sha256, area_id + ".ARE")],
                area=area_id,
                facts=area["rest_interruptions"],
                gaps=["Source rest encounters and interruption probabilities have no complete authored mapping."],
            )
        for index, actor in enumerate(area.get("actors", [])):
            source_id = actor.get("sourceId", f"{area_id}#actor{index + 1}")
            cre = source["creatures"].get(actor.get("creatureMetadata", actor["creature"]), {})
            targets = indexed[("sourceActor", source_id)]
            proof = [evidence(f"{prefix}/actors/{index}", sha256, area_id + ".ARE")]
            if cre.get("sha256"):
                proof.append(
                    evidence(
                        "/creatures/" + actor.get("creatureMetadata", actor["creature"]),
                        cre["sha256"],
                        actor["creature"] + ".CRE",
                    )
                )
            excluded = source.get("editionExcludedCreatures", {}).get(actor["creature"], "")
            if not isinstance(excluded, str):
                excluded = json.dumps(excluded, sort_keys=True)
            add(
                source_id,
                "actor",
                proof,
                area=area_id,
                targets=targets,
                excluded=excluded,
                facts={
                    "creature": actor["creature"],
                    "position": actor["position"],
                    "dialogue": actor.get("dialogue") or cre.get("dialogue", ""),
                    "scripts": actor.get("scripts", []),
                    "creatureScripts": cre.get("scripts", []),
                },
                prerequisites={"flags": actor["flags"], "allegiance": cre.get("allegiance")},
                ownership={"owner": source_id, "items": cre.get("items", []), "gold": cre.get("gold", 0)},
                timers={"scheduleMask": actor["schedule"], "itemExpiration": "raw item expiration fields retained"},
                conversion={"combat": "native stats, actions and equipment; source spell/effect behavior unaudited"},
                phase={
                    "source": "source script predicates unresolved",
                    "nativeBounds": [
                        {
                            "target": target,
                            "min": config[target]["properties"].get("phaseMin", 5),
                            "max": config[target]["properties"].get("phaseMax", 7),
                        }
                        for target in targets
                    ],
                },
                gaps=["Placement, inventory and generic hooks do not establish source actor AI or conversations."],
            )
            dialogue = actor.get("dialogue") or cre.get("dialogue", "")
            if dialogue:
                authored = []
                for target in targets:
                    authored.extend(
                        name
                        for name, actions in actor_dialogs[target]
                        if any(action.startswith(("accept", "quest")) for action in actions)
                    )
                add(
                    source_id + ":conversation",
                    "actorConversation",
                    proof,
                    area=area_id,
                    facts={"dialogue": dialogue},
                    targets=authored,
                    status="partial" if authored else "missing",
                    excluded=excluded,
                    gaps=[
                        "Generic Speak/inspection/theft/attack choices are not original conversation branches.",
                        "Quest callbacks map selected choices only; complete DLG conditions and repeat talks remain pending.",
                    ],
                )
        for family, singular in (
            ("containers", "container"),
            ("doors", "door"),
            ("regions", "region"),
            ("spawns", "spawnPoint"),
        ):
            for index, record in enumerate(area.get(family, [])):
                source_id = record.get("sourceId", f"{area_id}#{singular}{index + 1}")
                property_key = {
                    "container": "sourceContainer",
                    "door": "sourceDoor",
                    "region": "sourceRegion",
                    "spawnPoint": "sourceSpawnPoint",
                }[singular]
                targets = indexed[(property_key, source_id)]
                geometry_only = singular == "door" and source_id in geometry_doors
                if geometry_only:
                    targets = ["cityClock.geometryDoors:" + source_id]
                locks = {
                    key: record[key]
                    for key in (
                        "flags",
                        "lock_difficulty",
                        "break_difficulty",
                        "key",
                        "owner",
                        "trapped",
                        "trap_detection",
                        "trap_difficulty",
                        "trap_removal",
                        "enabled",
                        "method",
                    )
                    if key in record
                }
                effects = {
                    key: record[key]
                    for key in (
                        "destination",
                        "entrance",
                        "destinationPosition",
                        "script",
                        "dialogue",
                        "travel_trigger",
                        "creatures",
                        "text_strref",
                    )
                    if key in record
                }
                gaps = [
                    "Native interaction mapping is partial; source scripts, traps and crime outcomes require review."
                ]
                if geometry_only:
                    gaps.append("A retained geometry-only door record is not an executable door interaction.")
                if singular == "region" and not record.get("destination"):
                    gaps.append(
                        "Non-travel region triggers, including traps and information points, require authored behavior."
                    )
                add(
                    source_id,
                    singular,
                    [evidence(f"{prefix}/{family}/{index}", sha256, area_id + ".ARE")],
                    area=area_id,
                    targets=targets,
                    facts={key: record[key] for key in ("name", "type", "position") if key in record},
                    prerequisites=locks,
                    effects=effects,
                    ownership={"owner": source_id, "items": record["items"]} if "items" in record else {},
                    conversion=(
                        {
                            "lockPicking": {"routine": 12, "difficult": 16, "exceptional": 18},
                            "forcingStrength": [12, 14],
                            "sourceForbiddenMethodsTakePrecedence": True,
                            "assignedChecks": [
                                {
                                    "target": target,
                                    **{
                                        key: config[target]["properties"][key]
                                        for key in ("lockAgility", "forceStrength", "forbidPicking", "forbidForcing")
                                        if key in config[target]["properties"]
                                    },
                                }
                                for target in targets
                                if target in config
                            ],
                        }
                        if singular in {"container", "door"}
                        else {}
                    ),
                    gaps=gaps,
                )

    for index, link in enumerate(source.get("worldMapLinks", [])):
        source_id = f"WORLDMAP.WMP#cityLink{index + 1}"
        targets = [
            name
            for name, record in config.items()
            if all(
                record.get("properties", {}).get(key) == value
                for key, value in (
                    ("sourceArea", link["source"]),
                    ("destinationArea", link["destination"]),
                    ("sourceDirection", link["direction"]),
                    ("sourceEntrance", link["entrance"]),
                )
            )
        ]
        add(
            source_id,
            "worldMapLink",
            [evidence(f"/worldMapLinks/{index}", source.get("worldMapSha256", ""), "WORLDMAP.WMP")],
            area=link["source"],
            facts=link,
            targets=targets,
            effects={"outsideCity": link["outsideCity"], "destination": link["destination"]},
            timers={"travelTimeQuarters": link["travel_time_quarters"]},
            conversion={"outsideCity": "explicit history/interlude only; no external playable map"},
            gaps=["Source encounter/travel-time and chapter gating remain acceptance obligations."],
        )

    for index, actor in enumerate(source.get("scriptedActors", [])):
        source_id = actor["sourceId"]
        targets = sorted(
            set(
                indexed[("sourceSpawn", source_id)]
                + indexed[("sourceSpawnId", source_id)]
                + indexed[("sourceSpawnFact", source_id)]
                + indexed[("sourceActor", source_id)]
            )
        )
        excluded = "Known excluded EE/Tales actor addition." if actor.get("excludedAddition") else ""
        add(
            source_id,
            "scriptedActor",
            [evidence(f"/scriptedActors/{index}", actor["sourceSha256"], actor["sourceResource"])],
            targets=targets,
            excluded=excluded,
            facts={
                key: actor[key]
                for key in (
                    "creature",
                    "areas",
                    "position",
                    "signature",
                    "block",
                    "transition",
                    "recordOffset",
                    "states",
                )
                if key in actor
            },
            prerequisites={
                key: actor[key]
                for key in ("conditions", "conditionFunctions", "conditionSha256", "conditionSemanticsEvaluated")
                if key in actor
            },
            ownership={"owner": source_id, "items": source["creatures"].get(actor["creature"], {}).get("items", [])},
            conversion={
                "placement": "Shared-script context is a candidate set; it does not authorize unconditional spawning.",
                "authoredPolicies": [actor_definitions[target] for target in targets if target in actor_definitions],
            },
            gaps=[
                "All condition branches, actual area context, spawn timing and repeated-action behavior require verification."
            ],
        )

    for resource, metadata in sorted(source.get("references", {}).items()):
        if resource.rsplit(".", 1)[-1] not in {"BCS", "DLG"}:
            continue
        is_dialogue = resource.endswith(".DLG")
        resource_id = resource.rsplit(".", 1)[0]
        targets = indexed[("sourceDialogue" if is_dialogue else "sourceScript", resource_id)]
        # Merely copying a DLG/BCS resref onto an actor is provenance, not implementation.
        add(
            resource + ":behavior",
            "dialogueResource" if is_dialogue else "scriptResource",
            [evidence("/references/" + resource, metadata["sha256"], resource)],
            facts={key: metadata[key] for key in ("states", "transitions", "storeReferences") if key in metadata},
            targets=targets,
            status="planned" if targets else "missing",
            gaps=[
                "Referenced source program has not been translated exhaustively; resref retention alone provides no behavior coverage."
            ],
        )

    for creature_id, creature in sorted(source.get("creatures", {}).items()):
        targets = indexed[("sourceCreature", creature_id)]
        add(
            creature_id + ":creature",
            "creatureBehavior",
            [evidence("/creatures/" + creature_id, creature["sha256"], creature_id + ".CRE")],
            targets=targets,
            status="partial" if targets else "planned",
            excluded="Known excluded EE/Tales creature addition." if creature.get("excludedAddition") else "",
            facts={
                key: creature[key]
                for key in (
                    "dialogue",
                    "scripts",
                    "known_spells",
                    "memorized_spells",
                    "effect_count",
                    "effects_interpreted",
                    "itemSlots",
                )
                if key in creature
            },
            ownership={
                "owner": "per actual placed/spawned instance",
                "items": creature.get("items", []),
                "gold": creature.get("gold", 0),
            },
            conversion={"statsAndSpells": "Native creature composition; source spell/effect semantics remain pending."},
            gaps=[
                "CRE references are a structural dependency set; unused/shared-script candidates are not unconditional spawns."
            ],
        )

    loaded_stores = json.loads(clock.get("storeDefinitions", "{}").removeprefix("city-json:"))
    for store_id, store in sorted(source.get("stores", {}).items()):
        targets = indexed[("sourceStore", store_id)]
        proof = [evidence("/stores/" + store_id, store["sha256"], store_id + ".STO")]
        available = bool(targets and store_id in loaded_stores)
        services = [
            name
            for name in ("browseStock", "browseServices", "sell", "buy", "donate", "identify")
            if name in methods.get("BaldursGateDialog", set())
        ]
        status = "partial" if available and services else "planned" if store_id in loaded_stores else "missing"
        add(
            store_id + ":store",
            "store",
            proof,
            targets=targets,
            status=status,
            prerequisites={key: store[key] for key in ("flags", "store_type", "steal_failure", "purchased_types")},
            effects={key: store[key] for key in ("sell_markup", "buy_markup", "depreciation", "identify_price")},
            ownership={"owner": store_id, "stockCount": len(store["stock"])},
            callbacks=services,
            gaps=[
                "Store dependencies may be shared; actor access and all price/service outcomes need source and native validation."
            ],
        )
        rows = [("stock", row) for row in store["stock"]] + [("drink", row) for row in store["drinks"]]
        rows += [("cure", row) for row in store["cures"]]
        rows += [
            ("room", {"tier": tier, "price": price, "enabled": bool(store["room_flags"] & (1 << tier))})
            for tier, price in enumerate(store["room_prices"])
        ]
        counters = Counter()
        for kind, row in rows:
            index = counters[kind]
            counters[kind] += 1
            add(
                f"{store_id}:{kind}{index + 1}",
                "storeService",
                proof,
                targets=targets,
                status=status,
                prerequisites={"kind": kind, "source": row},
                choices=[{"kind": kind, "sourceIndex": index}],
                effects={"source": row},
                ownership={"owner": store_id, "infinite": row.get("infinite", False)},
                timers={"rest": "Source room tier healing/rest effects pending."} if kind == "room" else {},
                conversion={"services": "Native HP/conditions and currency require individual outcome mapping."},
                gaps=[
                    "Retained stock, drink, cure or room metadata is not proof that this exact service is executable."
                ],
            )

    loaded_rules = json.loads(clock.get("numericSourceRules", "{}").removeprefix("city-json:"))
    for resource, rule in sorted(source.get("numericSourceRules", {}).items()):
        targets = ["cityClock.numericSourceRules"] if loaded_rules.get(resource) == rule else []
        available = targets and "donate" in methods.get("BaldursGateDialog", set())
        add(
            resource + ":rule",
            "numericSourceRule",
            [evidence("/numericSourceRules/" + resource, rule["sha256"], resource)],
            targets=targets,
            status="partial" if available else "planned" if targets else "missing",
            facts={key: rule[key] for key in ("columns", "rows", "default", "donationColumns") if key in rule},
            effects={
                "sourceNumericModifiers": "Rows retain original raw units; native conversion needs explicit validation."
            },
            conversion={
                "reputation": "Stored BG reputation uses tenths; donation unit conversion is an adaptation inference."
            },
            gaps=[
                "Numeric rule retention does not establish donation affordability, reward, repetition or classic parity."
            ],
        )

    for item_id, item in sorted(source.get("items", {}).items()):
        targets = [
            name
            for name, record in config.items()
            if record.get("properties", {}).get("plugin_citySourceItem") == item_id
        ]
        excluded = source.get("editionExcludedItems", {}).get(item_id, "")
        if not isinstance(excluded, str):
            excluded = json.dumps(excluded, sort_keys=True)
        conversion = source.get("editionItemConversions", {}).get(item_id, {})
        add(
            item_id + ":item",
            "itemBehavior",
            [evidence("/items/" + item_id, item["sha256"], item_id + ".ITM")],
            targets=targets,
            excluded=excluded,
            facts={
                key: item[key]
                for key in (
                    "flags",
                    "item_type",
                    "price",
                    "stack_size",
                    "lore",
                    "enchantment",
                    "ability_count",
                    "effects_interpreted",
                )
                if key in item
            },
            conversion={
                "editionIdentity": conversion,
                "behavior": "Native gear conversion; original spells/effects remain pending.",
            },
            gaps=[
                "Source item identity and fixed ownership do not establish all item abilities, charges, curses or identification effects."
            ],
        )

    for index, row in enumerate(quests.get("quests", [])):
        key = row["id"][:1].upper() + row["id"][1:]
        choices = [
            (
                "accept",
                row["givers"],
                row.get("acceptConditions", {}),
                row.get("acceptEffects", {}),
                "accept" + key,
                "canAccept" + key,
            )
        ]
        choices += [
            (
                outcome["id"],
                outcome.get("at", row["givers"]),
                outcome.get("conditions", {}),
                outcome.get("effects", {}),
                "quest" + key + outcome["id"][:1].upper() + outcome["id"][1:],
                "canQuest" + key + outcome["id"][:1].upper() + outcome["id"][1:],
            )
            for outcome in row["outcomes"]
        ]
        for choice_id, selectors, conditions, effects, action, condition in choices:
            targets = selectTargets(selectors)
            wired = [
                name
                for name in targets
                if any({action, condition} <= actions for _dialog, actions in actor_dialogs[name])
            ]
            callbacks = methods.get("BaldursGateDialog", set())
            status = "partial" if wired and {action, condition} <= callbacks else "planned"
            gaps = list(row.get("acceptanceGaps", []))
            if not targets:
                gaps.append("No authored actor currently matches this choice's source selector.")
            if targets and not wired:
                gaps.append("Actor exists but no configured dialog exposes both this action and condition.")
            if not {action, condition} <= callbacks:
                gaps.append("Concrete action/condition callback methods are missing.")
            gaps.append(
                "Guide-supported selected choice; original DLG branch completeness and native outcome evidence pending."
            )
            add(
                f"quest:{row['id']}:{choice_id}",
                "questChoice",
                [evidence(f"/quests/{index}", fingerprint(row), quest=True)],
                phase={"sourceGuideChapter": row.get("phase", 5), "adaptation": row.get("phase", 5)},
                facts={"questId": row["id"], "selectors": selectors, "repeatable": row.get("repeatable", False)},
                prerequisites=conditions,
                choices=[choice_id],
                effects=effects,
                ownership={
                    "takeItems": effects.get("takeItems", []),
                    "rewardItems": effects.get("items", []),
                    "rule": "Reward and theft must transfer from the same persistent owner inventory.",
                },
                timers={"deadlineHours": row.get("deadlineHours"), "clearTimer": effects.get("clearTimer")},
                conversion={
                    "social": quests.get("standing", {}).get("social", "pending"),
                    "externalPrerequisites": "saved starting history or explicit off-map interlude only",
                },
                targets=targets,
                status=status,
                callbacks=[action, condition],
                gaps=gaps,
                urls=row.get("sources", []),
            )

    if warning is not None:
        addWarningObligations(source, config, methods, warning, add, entries)

    entries.sort(key=lambda row: row["id"])
    return {
        "schemaVersion": 1,
        "scope": "original BG1 base city; nine wards, interiors and bounded underground",
        "sourceEdition": source["sourceEdition"],
        "originalParityEstablished": False,
        "acceptanceReady": False,
        "inputs": {
            SOURCE_PATH: fingerprint(source),
            QUEST_PATH: fingerprint(quests),
            CONFIG_PATH: fingerprint(config),
            SCRIPT_PATH: hashlib.sha256(script.encode()).hexdigest(),
            **({WARNING_PATH: fingerprint(warning)} if warning is not None else {}),
        },
        "evidencePolicy": {
            "inventoryBoundary": "Complete enumeration of the audited fixture is not proof that the fixture includes every original game obligation.",
            "partial": "Some adaptation mapping exists; it does not establish full interaction coverage.",
            "planned": "A source reference/quest definition exists but executable choice mapping is incomplete.",
            "missing": "No executable mapping identified; generic talk never covers source conversation branches.",
            "excluded": "Known EE/Tales addition excluded from original-base target; classic identity still needs verification.",
            "automated": "Ledger tests validate source/mapping contracts only; they award no native gameplay or parity credit.",
        },
        "automatedContracts": {
            "inventoryContract": [
                "tests.test_baldurs_gate_city_ledger.BaldursGateCityLedgerFixtureTest."
                "testSavedLedgerCoversEverySourceObligationAndMatchesCurrentInputs",
                "tests.test_baldurs_gate_city_ledger.BaldursGateCityLedgerFixtureTest."
                "testEveryEvidencePointerResolvesAndFingerprintIsAvailable",
            ],
            "nativeExecutionReceipts": [],
            "nativeCoverageReceipts": [],
            "ownerApprovalReceipts": [],
        },
        "acceptanceBlockers": [
            SOURCE_GAP,
            NATIVE_GAP,
            (
                "GAM recruitment conditions and NPC level-variant selection require classic validation."
                if source.get("campaignNpcs")
                else "Campaign GAM NPC placement has not been audited in this source fixture."
            ),
        ]
        + source.get("uncertainties", [])
        + quests.get("acceptanceBlockers", []),
        "unresolvedSourceReferences": source.get("unresolved", []),
        "counts": {
            "entries": len(entries),
            "families": dict(sorted(Counter(row["family"] for row in entries).items())),
            "implementation": dict(sorted(Counter(row["implementation"]["status"] for row in entries).items())),
        },
        "entries": entries,
    }


def validateLedger(ledger, expected=None, require_mapped=False, require_acceptance=False):
    """Fail closed for dropped rows, malformed provenance or claimed evidence beyond this artifact."""
    problems = []
    entries = ledger.get("entries", [])
    identifiers = [row.get("id") for row in entries]
    if len(identifiers) != len(set(identifiers)):
        problems.append("Duplicate obligation IDs")
    if expected is not None and ledger != expected:
        expected_ids = {row["id"] for row in expected["entries"]}
        actual_ids = set(identifiers)
        problems.append("Ledger differs from current source and implementation inputs")
        problems.extend("Missing obligation: " + key for key in sorted(expected_ids - actual_ids))
        problems.extend("Unknown obligation: " + key for key in sorted(actual_ids - expected_ids))
    required = {
        "evidence",
        "phase",
        "prerequisites",
        "choices",
        "effects",
        "ownership",
        "timers",
        "nativeConversion",
        "implementation",
        "testStatus",
        "editionDifferences",
        "gaps",
    }
    for row in entries:
        key = row.get("id", "<missing>")
        if not required <= row.keys() or not row.get("evidence") or not row.get("editionDifferences"):
            problems.append("Incomplete obligation: " + key)
        status = row.get("implementation", {}).get("status")
        if status not in STATUSES:
            problems.append("Unsupported implementation status: " + key)
        if status == "partial" and not row.get("implementation", {}).get("targets"):
            problems.append("Partial mapping has no implementation target: " + key)
        if row.get("testStatus", {}).get("native") != "pending":
            problems.append("Native evidence cannot be awarded by this metadata generator: " + key)
        if row.get("testStatus", {}).get("coverage") != "not established":
            problems.append("Coverage cannot be awarded by this metadata generator: " + key)
        for proof in row.get("evidence", []):
            if not proof.get("pointer", "").startswith("/") or proof.get("fixture") not in {
                SOURCE_PATH,
                QUEST_PATH,
                WARNING_PATH,
            }:
                problems.append("Invalid source pointer: " + key)
            if proof.get("fixture") == WARNING_PATH and WARNING_PATH not in ledger.get("inputs", {}):
                problems.append("Missing warning input fingerprint: " + key)
            digest = proof.get("sha256", "")
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                problems.append("Invalid source fingerprint: " + key)
        if require_mapped and status in {"missing", "planned"}:
            problems.append("Unmapped source obligation: " + key)
    if ledger.get("counts", {}).get("entries") != len(entries):
        problems.append("Ledger count mismatch")
    if ledger.get("counts", {}).get("families") != dict(Counter(row.get("family") for row in entries)):
        problems.append("Ledger family count mismatch")
    if ledger.get("counts", {}).get("implementation") != dict(
        Counter(row.get("implementation", {}).get("status") for row in entries)
    ):
        problems.append("Ledger implementation count mismatch")
    if require_acceptance:
        if not ledger.get("acceptanceReady") or not ledger.get("originalParityEstablished"):
            problems.append("Original BG1 and native acceptance remain blocked")
        if ledger.get("unresolvedSourceReferences"):
            problems.append("Unresolved source references remain")
        if any(row.get("implementation", {}).get("status") != "excluded" for row in entries):
            problems.append("Adaptation mappings are partial and carry no native/classic acceptance proof")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the saved ledger is current without writing.")
    parser.add_argument(
        "--require-mapped", action="store_true", help="Fail on any missing or planned interaction mapping."
    )
    parser.add_argument(
        "--require-acceptance", action="store_true", help="Fail until native and original-source parity are proven."
    )
    args = parser.parse_args(argv)
    ledger = buildLedger(
        readJson(ROOT / SOURCE_PATH),
        readJson(ROOT / QUEST_PATH),
        readJson(ROOT / CONFIG_PATH),
        (ROOT / SCRIPT_PATH).read_text(encoding="utf-8"),
        warning=readJson(ROOT / WARNING_PATH) if (ROOT / WARNING_PATH).is_file() else None,
    )
    destination = ROOT / OUTPUT_PATH
    problems = validateLedger(ledger, require_mapped=args.require_mapped, require_acceptance=args.require_acceptance)
    if args.check:
        if not destination.is_file():
            problems.append("Missing saved ledger: " + OUTPUT_PATH)
        else:
            problems += validateLedger(readJson(destination), expected=ledger)
    elif not validateLedger(ledger):
        destination.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "counts": ledger["counts"],
                "acceptanceReady": False,
                "problems": len(problems),
                "firstProblems": problems[:12],
            },
            sort_keys=True,
        )
    )
    return 2 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
