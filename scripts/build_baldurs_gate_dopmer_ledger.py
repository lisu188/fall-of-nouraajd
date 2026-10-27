# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Retain every audited DOPMER obligation without granting native or classic acceptance."""

import ast
import hashlib
import json

STOCK_PATH = "tests/fixtures/baldurs_gate_seven_suns_stock.json"
DOPMER_PATH = "tests/fixtures/baldurs_gate_seven_suns_merchants.json"
DIALOGUE_SHA = "e0410b2b978573d0e921a63bf3a55fd53d49c291f556b6e0a045db63762030a7"
CREATURE_SHA = "3a94bcb25ad1dccf2f0b78dcafe1529e57802a69b566bf8aa566e7c74c8ceee1"
SPELL_SHA = "d18e8b8d1575e57481b63bccaff62b5c2b0a18da9cc86a81f9d5d292cce4c1fc"
WEAPON_SHA = "44c02f993700e11ec0994567ad9edb9ad4c1737eab6761dbe6767887f6cc343a"
EFFECTIVE_WEAPON_SHA = "29045d90fb11e54d672cafed2d4550606a0672355d93b211e9df8a0be7cc0f1f"
RANDOM_SHA = "e2b6333f09da3cae56e798a9f22541716dc44c37cef3fb60ad329655f8fdf85d"
LINEAGES = (
    ("cityAr0601Actor1", "AR0601#actor1", "AR0601"),
    ("cityAr0601Actor3", "AR0601#actor3", "AR0601"),
    ("cityAr0602Actor1", "AR0602#actor1", "AR0602"),
    ("cityAr0602Actor2", "AR0602#actor2", "AR0602"),
)
GLOBALS = ("CheckedSevenSuns", "Doppleganger", "Laola")
DIALOG_METHODS = {"isSevenSunsMerchantActor", "validSevenSunsMerchantView", "conversationSevenSunsMerchant"}
ROUTE_METHODS = {
    "sevenSunsMerchantRoute",
    "sevenSunsMerchantCases",
    "merchantCounterRoute",
    "merchantScheduleRoute",
    "merchantSharedGlobalRoute",
    "merchantNaturalTurn",
}
DEFINITION = {"version": 1, "dialogue": "DOPMER", "fingerprint": DIALOGUE_SHA, "stockContract": "doppss-native-v1"}
REPLACEMENT_ID = "citySevenSunsRevealedDoppss"
WEAPON_ID = "citySevenSunsDoppssWeapon"


def validateDopmerSource(source, fixture):
    reference = source.get("references", {}).get("DOPMER.DLG", {})
    if (
        reference.get("sha256") != DIALOGUE_SHA
        or reference.get("size") != 1687
        or reference.get("states") != 14
        or reference.get("transitions") != 24
        or fixture.get("dialogueFingerprint") != {"bytes": 1687, "sha256": DIALOGUE_SHA}
    ):
        raise ValueError("DOPMER source fingerprint/counts do not match the reviewed14-state24-edge graph")
    if (
        any(type(reference.get(key)) is not int for key in ("size", "states", "transitions"))
        or type(fixture.get("dialogueFingerprint", {}).get("bytes")) is not int
    ):
        raise ValueError("DOPMER source lengths/counts must be ordinary integers")
    states, edges = fixture.get("states", []), fixture.get("edges", [])
    if (
        len(states) != 14
        or any(type(row.get("id")) is not int for row in states)
        or {row["id"] for row in states} != set(range(14))
    ):
        raise ValueError("DOPMER must retain every source state exactly once")
    if (
        len(edges) != 24
        or any(type(row.get("id")) is not int for row in edges)
        or {row["id"] for row in edges} != set(range(24))
    ):
        raise ValueError("DOPMER must retain every source edge exactly once")
    for state in states:
        if state.get("edges") != [edge["id"] for edge in edges if edge.get("from") == state["id"]]:
            raise ValueError("DOPMER state/edge ownership changed")
    for edge in edges:
        if (
            type(edge.get("from")) is not int
            or edge["from"] not in range(14)
            or type(edge.get("terminal")) is not bool
            or (edge["to"] is None) != edge["terminal"]
            or edge["to"] is not None
            and (type(edge["to"]) is not int or edge["to"] not in range(14))
        ):
            raise ValueError("DOPMER transition target or terminal flag is invalid")
    for edge in edges:
        expected_writes = (
            [("CheckedSevenSuns", 2)]
            if edge["id"] in {0, 1, 2}
            else [("Doppleganger", 1), ("Laola", 1)] if edge["id"] in {12, 17, 21, 22, 23} else []
        )
        expected_actions = [
            {
                "kind": "call",
                "name": "SetGlobal",
                "arguments": [
                    {"kind": "string", "value": name},
                    {"kind": "string", "value": "GLOBAL"},
                    {"kind": "integer", "value": value},
                ],
            }
            for name, value in expected_writes
        ]
        if edge.get("orderedActions") != expected_actions or any(
            type(action["arguments"][2]["value"]) is not int for action in edge["orderedActions"]
        ):
            raise ValueError("DOPMER ordered source actions changed")
    expected_lineages = [
        {"id": name, "sourceActor": actor, "sourceArea": area, "sourceCreature": "DOPMER", "sourceDialogue": "DOPMER"}
        for name, actor, area in LINEAGES
    ]
    if (
        fixture.get("lineages") != expected_lineages
        or fixture.get("entriesByPriorSourceTalkCount") != {"0": 0, "1": 7, "2": 10}
        or fixture.get("sharedGlobals", {}).get("scope") != "GLOBAL"
        or fixture["sharedGlobals"].get("names") != list(GLOBALS)
    ):
        raise ValueError("DOPMER lineages, counter entries or shared GLOBAL bindings changed")
    if any(type(value) is not int for value in fixture["entriesByPriorSourceTalkCount"].values()):
        raise ValueError("DOPMER entry counters must be ordinary integers")
    bindings = fixture.get("sourceBindings", {})
    expected = {
        "spell": ("SPWI993.SPL", 346, SPELL_SHA),
        "replacementCreature": ("DOPPSS.CRE", 1116, CREATURE_SHA),
        "weapon": ("S1-12.ITM", 170, WEAPON_SHA),
        "randomPlaceholder": ("RNDTRE05.ITM", 114, RANDOM_SHA),
    }
    for key, (resource, size, digest) in expected.items():
        if bindings.get(key, {}).get("resource") != resource or bindings[key].get("base") != {
            "bytes": size,
            "sha256": digest,
        }:
            raise ValueError("DOPMER replacement/stock literal source binding changed: " + key)
        if (
            type(bindings[key]["base"].get("bytes")) is not int
            or key != "weapon"
            and bindings[key].get("effective") != bindings[key]["base"]
        ):
            raise ValueError("DOPMER replacement/stock source view or byte length changed: " + key)
        if type(bindings[key].get("effective", {}).get("bytes")) is not int:
            raise ValueError("DOPMER effective byte length must be an ordinary integer")
    if (
        bindings["weapon"].get("effective") != {"bytes": 218, "sha256": EFFECTIVE_WEAPON_SHA}
        or bindings["weapon"].get("baseEffectiveEqual") is not False
        or bindings.get("nativeStockContract") != "doppss-native-v1"
    ):
        raise ValueError("DOPMER base/effective weapon distinction or stock contract changed")
    if (
        source.get("creatures", {}).get("DOPPSS", {}).get("sha256") != CREATURE_SHA
        or source.get("items", {}).get("S1-12", {}).get("sha256") != WEAPON_SHA
        or source.get("items", {}).get("RNDTRE05", {}).get("sha256") != RANDOM_SHA
    ):
        raise ValueError("DOPMER stock/creature fixture fingerprints disagree with source inventory")
    replacement = fixture.get("replacement", {})
    if (
        replacement.get("resource") != "DOPPSS"
        or replacement.get("spell") != "SPWI993"
        or type(replacement.get("opcode")) is not int
        or replacement["opcode"] != 151
        or type(replacement.get("style")) is not int
        or replacement["style"] != 0
    ):
        raise ValueError("DOPMER replacement opcode/style/resource changed")


def sourceCallbacks(script, owner, method):
    for node in ast.walk(ast.parse(script)):
        if isinstance(node, ast.ClassDef) and node.name == owner:
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == method:
                    return {
                        call.func.attr
                        for call in ast.walk(child)
                        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    }
    return set()


def dopmerMapping(config, methods, fixture, script):
    if not DIALOG_METHODS <= methods.get("BaldursGateDialog", set()) or not {
        "settleSevenSunsMerchants",
        "onTurn",
    } <= methods.get("BaldursGateClock", set()):
        return []
    if "conversationSevenSunsMerchantFlow" not in sourceCallbacks(
        script, "BaldursGateDialog", "talk"
    ) or "settleSevenSunsMerchantsFlow" not in sourceCallbacks(script, "BaldursGateClock", "onTurn"):
        return []
    for lineage in fixture["lineages"]:
        actor = config.get(lineage["id"], {}).get("properties", {})
        if (
            any(actor.get(key) != value for key, value in lineage.items() if key != "id")
            or type(actor.get("sourceAllegiance")) is not int
            or actor["sourceAllegiance"] != 128
        ):
            return []
    try:
        definition = json.loads(
            config.get("cityClock", {})
            .get("properties", {})
            .get("sevenSunsMerchantDefinition", "")
            .removeprefix("city-json:")
        )
    except (ValueError, TypeError, AttributeError):
        return []
    if not isinstance(definition, dict) or type(definition.get("version")) is not int or definition != DEFINITION:
        return []
    return [row["id"] for row in fixture["lineages"]] + ["cityClock.sevenSunsMerchantDefinition"]


def addDopmerObligations(source, config, methods, fixture, add, *, script, routes=None, stock=None):
    validateDopmerSource(source, fixture)
    if stock is not None:
        validateStockSource(source, stock)
    targets = dopmerMapping(config, methods, fixture, script)
    callbacks = (
        ["BaldursGateDialog." + name for name in sorted(DIALOG_METHODS)]
        + ["BaldursGateClock.settleSevenSunsMerchants", "BaldursGateClock.onTurn"]
        if targets
        else []
    )
    if routes is not None and targets:
        functions = {
            node.name for node in ast.parse(routes).body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        callbacks += ["tests/gameplay_routes_baldurs_gate.py:" + name for name in sorted(functions & ROUTE_METHODS)]
    ownership = {
        "lineages": fixture["lineages"],
        "oldActor": "Quietly retain the same old actor and its actual effects/item aliases; never victory/death/loot/XP.",
        "replacement": fixture["replacement"],
        "stock": source["creatures"]["DOPPSS"]["items"],
        "newOwner": "Distinct DOPPSS with independently materialized stock, not old-owner inventory transfer.",
    }
    timers = {
        "nativeSettlement": "Approved adaptation: settle on the next turn of the current source region.",
        "sourceScheduling": "Original script scheduling, INITDLG and compiled selector/IDS parity remain pending.",
        "sourceCounter": fixture["sourceCountConversion"],
        "cancellation": "Accepted begin increments source counter before first UI; selected-edge writes persist. Original cancellation-count parity remains pending.",
    }
    conversion = {
        "sourceEdition": "Installed EE/base support is not authenticated original BG1.",
        "counter": fixture["sourceCountConversion"],
        "replacement": fixture["replacement"],
        "stockContract": fixture["sourceBindings"]["nativeStockContract"],
        "weaponScope": "Base S1-12 only; effective CIFGAIN, enchantment immunity and other item abilities remain separate gaps.",
        "nativeAcceptance": "No native, save/reload, coverage, visual or owner credit.",
    }
    common_gaps = list(fixture["acceptanceGaps"]) + [
        "Original script timing and cancellation-count parity remain unproved.",
        "Authored source/route callbacks are mappings, not native execution receipts.",
        "Item abilities and classic random-weight/default-charge parity remain unproved.",
    ]
    if not targets:
        common_gaps.append(
            "Exact four actor identities/allegiance, clock definition or wired merchant/settlement callbacks are absent."
        )

    def proof(pointer, digest=DIALOGUE_SHA, resource="DOPMER.DLG", source_pointer="/references/DOPMER.DLG"):
        result = [{"fixture": DOPMER_PATH, "pointer": pointer, "sha256": digest, "resource": resource}]
        if source_pointer:
            result.append(
                {
                    "fixture": "tests/fixtures/baldurs_gate_city_source.json",
                    "pointer": source_pointer,
                    "sha256": digest,
                    "resource": resource,
                }
            )
        return result

    def row(
        identifier,
        family,
        evidence,
        *,
        facts,
        prerequisites=None,
        choices=None,
        effects=None,
        own=None,
        mapped=None,
        extra_gaps=None,
    ):
        selected = targets if mapped is None else mapped
        add(
            identifier,
            family,
            evidence,
            phase={"source": "DOPMER count0/1/2 entries and selected source actions", "scenarioChapters": [5, 7]},
            facts=facts,
            prerequisites=prerequisites,
            choices=choices,
            effects=effects,
            ownership=ownership if own is None else own,
            timers=timers,
            conversion=conversion,
            targets=selected,
            status="partial" if selected else "planned",
            callbacks=callbacks if selected else [],
            gaps=common_gaps + list(extra_gaps or []),
        )

    for index, state in enumerate(fixture["states"]):
        row(
            f"DOPMER.DLG#state{state['id']}",
            "dialogueState",
            proof(f"/states/{index}"),
            facts={key: value for key, value in state.items() if key != "body"},
            prerequisites={"sourceEntry": state["entryCondition"]},
            choices=state["edges"],
            effects={
                "selectedEdges": [
                    {key: value for key, value in edge.items() if key != "reply"}
                    for edge in fixture["edges"]
                    if edge["id"] in state["edges"]
                ]
            },
        )
    for index, edge in enumerate(fixture["edges"]):
        row(
            f"DOPMER.DLG#edge{edge['id']}",
            "dialogueEdge",
            proof(f"/edges/{index}"),
            facts={key: value for key, value in edge.items() if key != "reply"},
            prerequisites={"sourceState": edge["from"]},
            choices=[edge["id"]],
            effects={
                "orderedActions": edge["orderedActions"],
                "next": edge["to"],
                "terminal": edge["terminal"],
                "revealGlobalRequested": edge["reveals"],
            },
        )
    for name in GLOBALS:
        writers = [
            {"edge": edge["id"], "action": action}
            for edge in fixture["edges"]
            for action in edge["orderedActions"]
            if action.get("name") == "SetGlobal" and action["arguments"][0].get("value") == name
        ]
        row(
            "DOPMER.DLG#global" + name,
            "sourceGlobal",
            proof("/sharedGlobals"),
            facts={"name": name, "scope": "GLOBAL"},
            prerequisites={
                "variableNames": "ASCII case-insensitive; scope exact GLOBAL",
                "reveal": "Doppleganger exactly1 and source allegiance128; Laola is not an additional predicate.",
            },
            choices=[item["edge"] for item in writers],
            effects={
                "dialogueWrites": writers,
                "attackedScriptOrder": fixture["sharedGlobals"]["attackedScriptOrder"],
                "unknownValues": "Preserve unrelated keys/scopes and incoming integer values; no truthiness/clamping.",
            },
            own={"sharedNamespace": "plugin_citySourceGlobals.GLOBAL", "perActorReceiptIsNotGlobalAuthority": True},
        )
    for index, lineage in enumerate(fixture["lineages"]):
        area_rows = source.get("areas", {}).get(lineage["sourceArea"], {}).get("actors", [])
        actor_index = next(
            (i for i, actor in enumerate(area_rows) if actor.get("sourceId") == lineage["sourceActor"]), None
        )
        evidence = proof(f"/lineages/{index}") + proof("/sourceCountConversion")[:1]
        if actor_index is not None:
            evidence.append(
                {
                    "fixture": "tests/fixtures/baldurs_gate_city_source.json",
                    "pointer": f"/areas/{lineage['sourceArea']}/actors/{actor_index}",
                    "sha256": source["areas"][lineage["sourceArea"]]["sha256"],
                    "resource": lineage["sourceArea"] + ".ARE",
                }
            )
        row(
            "DOPMER.DLG#talkCounter:" + lineage["sourceActor"],
            "sourceCounter",
            evidence,
            facts={"lineage": lineage, "entriesByPriorSourceTalkCount": fixture["entriesByPriorSourceTalkCount"]},
            prerequisites={
                "authoritativeField": "plugin_cityDopmerTalkCount",
                "genericCountIsNotSourceCounter": True,
                "legacyUnknown": "Refuse migration rather than infer/reset.",
            },
            effects={"acceptedBegin": fixture["sourceCountConversion"], "noAuditedEntryAtOrAbove": 3},
            own={"owner": lineage["id"], "independentFromOtherThreeLineages": True},
        )
    replacement_targets = (
        targets + [REPLACEMENT_ID, WEAPON_ID]
        if targets
        and config.get(REPLACEMENT_ID, {}).get("class") == "CCreature"
        and config.get(WEAPON_ID, {}).get("class") == "CWeapon"
        else []
    )
    unresolved = (
        [
            "Actual dedicated replacement/weapon resource definitions are absent; root-owned native factory and ownership evidence remain separate prerequisites."
        ]
        if not replacement_targets
        else []
    )
    row(
        "SPWI993.SPL#replacement",
        "creatureReplacement",
        proof("/sourceBindings/spell", SPELL_SHA, "SPWI993.SPL", None)
        + proof("/sourceBindings/replacementCreature", CREATURE_SHA, "DOPPSS.CRE", "/creatures/DOPPSS"),
        facts={
            "opcode": 151,
            "style": 0,
            "spell": "SPWI993",
            "newResource": "DOPPSS",
            "fourLineages": fixture["lineages"],
            "sourceStats": {
                name: source["creatures"]["DOPPSS"][name]
                for name in ("hit_points", "max_hit_points", "kill_xp", "gold", "death_variable")
            },
        },
        prerequisites={"sourceRevealPredicate": "GLOBAL Doppleganger ==1 and affected source allegiance128"},
        effects={
            "operation": "remove target and create distinct specified creature",
            "quietRetirementCredit": {"death": False, "xp": 0, "loot": []},
        },
        mapped=replacement_targets,
        extra_gaps=unresolved,
    )
    for index, (item, binding, digest) in enumerate(
        [("S1-12", "weapon", WEAPON_SHA), ("RNDTRE05", "randomPlaceholder", RANDOM_SHA)]
    ):
        row(
            "DOPPSS.CRE#stock:" + item,
            "replacementStock",
            proof("/sourceBindings/" + binding, digest, item + ".ITM", "/items/" + item)
            + (
                [stockProof("/rows", STOCK_FIXTURE_SHA, "baldurs_gate_seven_suns_stock.json")]
                if stock is not None and item == "RNDTRE05"
                else []
            ),
            facts={
                "sourceItem": source["creatures"]["DOPPSS"]["items"][index],
                "sourceSlots": source["creatures"]["DOPPSS"]["itemSlots"],
                "sourceBinding": fixture["sourceBindings"][binding],
                **(
                    {"sourceEnchantment": {"value": stock["weapon"]["enchantment"], "metadataOnly": True}}
                    if stock is not None and item == "S1-12"
                    else {}
                ),
                **({"finiteNativeConversion": stockFacts(stock)} if stock is not None and item == "RNDTRE05" else {}),
            },
            prerequisites={"stockContract": "doppss-native-v1", "baseWeaponSelected": item == "S1-12"},
            effects={
                "nativeOwnership": "Materialize actual independently owned concrete items/gold/no-item once; preserve chosen provenance across retry/save.",
                "placeholderIsNotActualStockProof": item == "RNDTRE05",
            },
            mapped=replacement_targets,
            extra_gaps=unresolved
            + [
                "Random-stock and item-ability behavior require actual resolver/ownership/defeat evidence; generic placeholder inventory is insufficient."
            ],
        )


STOCK_FIXTURE_SHA = "dabc0e83fe66a519991787985a9e6ee50822ae42570c9965e50ba6cda8913b73"
NEW_STOCK_ITEMS = {
    "BOLT05": "5de41b770a3b79b116ca189ddfe575e2455ae53c018e96ddcc52c7454629b2dd",
    "SCRL1J": "5ae85ad19bf64605c79746b464bb5a0f2e414f5ac6a127e3f44edbfe75b9ca16",
    "SCRL2I": "b44430b32135bd3f1aa42f80152dcd0c2a6ee9b81e506bd373b27aef67a0c8e3",
}
STOCK_FAMILIES = {"RNDTRE05", "RNDMAG01", "RNDMAG02", "RNDSCR01", "RNDSCR02", "RNDSCR03"}
STOCK_INPUTS = {
    "itemHeaders": "639d77f27b026237e271b56dc8b6fec561ee8365e0b12de21d2309710e18d3e0",
    "scrollFrontier": "d409e1732500017cc3026ffc0688c64da46c112cbf79f91b21679883fd151ae0",
    "priorClosure": "638ff1ad4c788852e7b106a57ea253ba9747d79542cc9cdd08c2144d7906b218",
    "rootTable": "98dfa0a21e31b3fb0d25d75665baa5044b3eda26d984abe6b75dd366cbf99d6e",
}


def validateStockSource(source, stock):
    reviewed = hashlib.sha256(
        json.dumps(stock, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if reviewed != "d41fbaade7bb744267f68b6d12d24f74e54cdc29260732a7be1cd961809ba988":
        raise ValueError("Stock fixture differs from the reviewed finite source facts")
    if (
        stock.get("schema") != "baldurs-gate-seven-suns-stock.v1"
        or stock.get("originalParity") is not False
        or stock.get("itemAbilitiesEstablished") is not False
        or stock.get("sourceDiceRuleEstablished") is not False
        or stock.get("nativeDiceRule") != "oneNativeD20PerSelectedRow"
        or stock.get("inputFingerprints") != STOCK_INPUTS
    ):
        raise ValueError("Unreviewed stock source/acceptance contract")
    items, rows = stock.get("items", {}), stock.get("rows", {})
    if len(items) != 97 or set(rows) != STOCK_FAMILIES:
        raise ValueError("Stock must retain all97 items and six finite rows")
    if set(items) - set(source["items"]) != set(NEW_STOCK_ITEMS):
        raise ValueError("Stock item extension must retain exactly the three newly audited item obligations")
    tokens = set()
    for family, row in rows.items():
        first_column = 1 if family.startswith("RNDSCR") else 2
        if row.get("columns") != list(range(first_column, 21)) or len(row.get("cells", [])) != 21 - first_column:
            raise ValueError("Stock source columns/cells changed")
        for token in row["cells"]:
            if not isinstance(token, str):
                raise ValueError("Stock token must be source text")
            if token not in STOCK_FAMILIES and not token.isdecimal():
                tokens.add(token.split("*")[0])
    if tokens != set(items):
        raise ValueError("Stock concrete item closure changed")
    for code, item in items.items():
        digest = NEW_STOCK_ITEMS.get(code, source["items"].get(code, {}).get("sha256"))
        header = item.get("headerEvidence", {}).get("fingerprint", {})
        if item.get("baseSha256") != digest or header.get("sha256") != digest:
            raise ValueError("Stock base item fingerprint disagrees with retained source: " + code)
        if (
            type(header.get("bytes")) is not int
            or header["bytes"] <= 0
            or item.get("abilitiesPending") is not True
            or type(item.get("abilityCount")) is not int
            or len(item.get("abilityEffectCounts", [])) != item["abilityCount"]
            or any(type(value) is not int or value < 0 for value in item["abilityEffectCounts"])
            or type(item.get("equippedEffectCount")) is not int
            or item["equippedEffectCount"] < 0
            or len(item.get("charges", [])) != 3
            or any(type(value) is not int or not 0 <= value <= 65535 for value in item["charges"])
            or item.get("resourceId") != "citySevenSunsTreasure" + code[0] + code[1:].lower()
        ):
            raise ValueError("Stock header/effect-count/charge facts changed: " + code)
    if (
        stock.get("weapon", {}).get("baseSha256") != WEAPON_SHA
        or stock["weapon"].get("effectiveSha256") != EFFECTIVE_WEAPON_SHA
        or stock.get("sourceCreature", {}).get("sha256") != CREATURE_SHA
    ):
        raise ValueError("Stock replacement or base/effective weapon source binding changed")


def stockProof(pointer, digest, resource):
    return {"fixture": STOCK_PATH, "pointer": pointer, "sha256": digest, "resource": resource}


def stockFacts(stock):
    return {
        "selectionRows": stock["rows"],
        "concreteItems": sorted(stock["items"]),
        "sourceEnchantment": {
            "weapon": stock["weapon"]["enchantment"],
            "metadataOnly": True,
            "immunityOrBonusEstablished": False,
        },
        "nativeDiceRule": stock["nativeDiceRule"],
        "sourceDiceRuleEstablished": False,
        "nativeChargeRule": stock["nativeChargeRule"],
        "materializationPolicy": "Base headers only; effective class/mod overrides are retained as separate facts.",
        "effectiveOverridesExcluded": sorted(
            code for code, item in stock["items"].items() if not item["baseEffectiveBytesMatch"]
        ),
        "suffixPolicy": "A token suffix is a stack count only for stackable items; it is not a wand charge count.",
        "abilitiesEstablished": False,
        "abilityObligations": "All97 remain pending:94 retained itemBehavior rows plus three new rows.",
    }


def addStockItemObligations(source, config, stock, add):
    validateStockSource(source, stock)
    for code, digest in NEW_STOCK_ITEMS.items():
        item = stock["items"][code]
        definition = config.get(item["resourceId"], {})
        properties = definition.get("properties", {})
        mapped = (
            definition.get("class") == "CItem"
            and properties.get("plugin_citySourceItem") == code
            and properties.get("plugin_citySourceItemFingerprint") == digest
            and properties.get("plugin_cityAbilitiesPending") is True
        )
        add(
            code + ":item",
            "itemBehavior",
            [stockProof("/items/" + code, digest, code + ".ITM")],
            phase={"source": "DOPPSS finite random-stock closure", "scenarioChapters": [5, 7]},
            facts={key: value for key, value in item.items() if key not in {"label", "animation"}},
            prerequisites={
                "selection": "Selected RNDTRE05 closure row resolves this concrete base resource.",
                "sourceAuthority": "Base ITM header/effect counts only; effect bodies were not audited here.",
            },
            effects={
                "sourceAbilitiesInterpreted": False,
                "nativeMaterialization": "Real CItem ownership only.",
                "nativeChargeRule": stock["nativeChargeRule"],
            },
            ownership={
                "configuredResource": item["resourceId"],
                "stockActor": "Distinct new DOPPSS",
                "oldActorInventoryTransferred": False,
                "sourceAbilitiesRemainPending": True,
            },
            timers={"materialization": "Once per replacement provenance; runtime save/reload/defeat evidence pending."},
            conversion={
                "materializationPolicy": "Base headers only",
                "originalParity": False,
                "defaultCharges": stock["nativeChargeRule"],
                "itemAbilitiesEstablished": False,
            },
            targets=[item["resourceId"]] if mapped else [],
            status="partial" if mapped else "planned",
            callbacks=[],
            gaps=list(stock["acceptanceGaps"])
            + [
                "Concrete item ownership does not implement source spell, ammunition or item effects.",
                "Native execution, save/reload, defeat/loot, coverage and owner acceptance remain pending.",
            ],
        )
