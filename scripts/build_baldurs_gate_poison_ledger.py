#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Required finite supporting-EE poison inventory; this module awards no gameplay acceptance."""

from copy import deepcopy
import re

POISON_PATH = "tests/fixtures/baldurs_gate_city_poison_dialogue.json"
DIALOGUE_LAYOUTS = {
    "MAREK.DLG": ("83a5c9ffc48350bbb082f182bfd7ce7a4e2e0c856b4a2101ad4a30ccdec8a1f2", 1145, 7, 10),
    "LOTHAN.DLG": ("42d4e4bd6c649a2f3e199e22e7fc59328014a46b6b57359569b828a2aaa53618", 2718, 18, 27),
    "DIVINE.DLG": ("83b63b945f32a43b8beaf5f5499adbafa10994a6fd7a8984122ca69dbb72956b", 1509, 11, 18),
    "PUMBERL.DLG": ("b35b9a470bd0f8e1a161b9f75d800a263d70c6b0446ba337801df39932cf3de6", 1593, 13, 19),
    "JALANT.DLG": ("dcd56094b1789cf34bad765aba92a31e1ae7f18df5ab6c9dfcfff894019fba41", 1987, 17, 28),
    "CHANTH.DLG": ("19aef36b761640cc5bc9c3c686aed5af70997cd9a4fc3b5e0afe66e2eacfddd8", 947, 6, 10),
}
SCRIPT_LAYOUTS = {
    "AR0115.BCS": ("851997a27dbe87b3305f2eb7f451a9669afa82770a040099406da8a18bfbbaa0", 485, {0: 5}),
    "AR0700.BCS": ("f31121870a7d672531a7c82f65f221bb9a391aa552b3fd2a0f4bcfa66084f3a4", 3158, {3: 6, 4: 4}),
    "BALDUR.BCS": (
        "99eca6550e686e9c594a01bff1cf30c7e354223854588f967ba01fb1868a9322",
        33279,
        {0: 7, 35: 7, 36: 5, 37: 3, 43: 21, 44: 21},
    ),
}
ITEM_LAYOUTS = {
    "BOOK08.ITM": ("d622d0ed5ea5a99e2f83a3be23b1b0b1e9096888204b3d4dfc90ea34e533c1f8", 362, 1, 4),
    "SCRLJALA.ITM": ("575b28204a086e911ce32f66d3dc42a8c68d33c48164da3666dac1c9062b919a", 114, 0, 0),
    "LOPOTN20.ITM": ("6a4319349b8036b87ea2013a236aadfd500c9d76563205a41814be2e41e648f5", 114, 0, 0),
    "POTN47.ITM": ("2c83039fd2433d23a829feb2efe189df9e1dd4df812146268cd47dfedf90ff7b", 506, 1, 7),
}
FRONTIER_IDS = (
    "BDMAREK.SPL:poisonCausality",
    "BALDUR.BCS:unpublishedBlocks",
    "AR0700.BCS:unpublishedBlocks",
    "SHOUT.BCS:poisonListeners",
    "LOTHAN.DLG:priestIdentityAndHistory",
    "POISON:classicAuthority",
    "POISON:scriptScheduling",
    "POTN47.ITM:applicationCausality",
)
SOURCE_GAP = "Installed EE facts do not authenticate original BG1 behavior or effect/journal semantics."
NATIVE_GAP = "Native routes, ownership, scheduling, item effects, save/reload and owner acceptance remain pending."


def require(condition, message):
    if not condition:
        raise ValueError("Required poison source inventory: " + message)


def digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def indexRows(rows, expected, label):
    require(type(rows) is list and all(type(row) is dict for row in rows), label + " list")
    require(all(type(row.get("index")) is int for row in rows), label + " integer indexes")
    require([row["index"] for row in rows] == list(expected), label + " complete ordered indexes")


def typedValue(value, depth=0):
    require(depth <= 8 and type(value) is dict, "typed expression depth")
    kind = value.get("type")
    if kind == "integer":
        require(type(value.get("value")) is int, "typed integer")
    elif kind in ("identifier", "symbol", "selectorSymbol"):
        require(
            type(value.get("value")) is str and re.fullmatch(r"[A-Za-z0-9_]*", value["value"]) is not None,
            "typed source identifier",
        )
    elif kind == "point":
        require(type(value.get("x")) is int and type(value.get("y")) is int, "typed point")
    elif kind == "call":
        require(
            type(value.get("operation")) is str and re.fullmatch(r"[A-Za-z0-9_]+", value["operation"]) is not None,
            "typed operation",
        )
        require(
            type(value.get("negated")) is bool
            and type(value.get("arguments")) is list
            and len(value["arguments"]) <= 8,
            "typed call arguments",
        )
        for argument in value["arguments"]:
            typedValue(argument, depth + 1)
    else:
        require(False, "unknown typed expression")


def calls(values):
    require(type(values) is list, "condition/action list")
    for value in values:
        typedValue(value)
        require(value["type"] == "call", "condition/action call")


def typedStorage(row):
    for key, value in row.items():
        width = next((bits for bits in (8, 16, 32) if key.endswith("U" + str(bits))), None)
        if width is not None:
            require(type(value) is int and 0 <= value < 2**width, "unsigned storage field")
        elif key.endswith(("Signed32", "Signed32View")):
            require(type(value) is int and -(2**31) <= value < 2**31, "signed storage view")


def noRawPayload(value):
    if type(value) is dict:
        require(
            not ({"raw", "compiled_text", "compiledText", "prose", "text", "objectSelectors"} & value.keys()),
            "raw script, selector or prose field",
        )
        for child in value.values():
            noRawPayload(child)
    elif type(value) is list:
        for child in value:
            noRawPayload(child)
    elif type(value) is str:
        require(
            len(value) <= 128
            and re.fullmatch(r"[A-Za-z0-9_:/#.@-]*", value) is not None
            and re.search(r"[A-Za-z]:[/\\]", value) is None,
            "non-factual string or private path",
        )


def sourceInventory(document):
    require(
        type(document) is dict
        and type(document.get("schemaVersion")) is int
        and document["schemaVersion"] == 1
        and document.get("kind") == "CityPoisonSourceInventory",
        "schema",
    )
    noRawPayload(document)
    groups = (("dialogues", DIALOGUE_LAYOUTS), ("scripts", SCRIPT_LAYOUTS), ("items", ITEM_LAYOUTS))
    for name, layouts in groups:
        rows = document.get(name)
        require(
            type(rows) is list and len(rows) == len(layouts) and all(type(row) is dict for row in rows),
            name + " resources",
        )
        require({row.get("resource") for row in rows} == set(layouts), name + " exact resource names")
        for row in rows:
            layout = layouts[row["resource"]]
            require(
                row.get("sha256") == layout[0] and type(row.get("bytes")) is int and row["bytes"] == layout[1],
                "published resource fingerprint",
            )
    for row in document["dialogues"]:
        resource = row["resource"]
        indexRows(row.get("states"), range(DIALOGUE_LAYOUTS[resource][2]), resource + " states")
        indexRows(row.get("edges"), range(DIALOGUE_LAYOUTS[resource][3]), resource + " edges")
        owners = {edge["index"]: [] for edge in row["edges"]}
        for state in row["states"]:
            require(state.get("sourceId") == resource + ":state" + str(state["index"]), "state source ID")
            require(type(state.get("edges")) is list, "state edges")
            for number in state["edges"]:
                require(type(number) is int and number in owners, "owned edge index")
                owners[number].append(state["index"])
            calls(state.get("entryConditions"))
        for edge in row["edges"]:
            require(
                edge.get("sourceId") == resource + ":edge" + str(edge["index"])
                and edge.get("owners") == owners[edge["index"]]
                and owners[edge["index"]],
                "edge ownership",
            )
            require(type(edge.get("rawFlags")) is int, "raw transition flags")
            require(edge.get("targetResource") in ("", resource[:-4]), "external dialogue frontier")
            target = edge.get("targetState")
            require(target is None or type(target) is int and 0 <= target < len(row["states"]), "state target")
            for name in ("replyStrref", "journalStrref"):
                require(edge.get(name) is None or type(edge[name]) is int and edge[name] >= 0, "strref")
            calls(edge.get("conditions"))
            calls(edge.get("actions"))
    for row in document["scripts"]:
        resource = row["resource"]
        layout = SCRIPT_LAYOUTS[resource][2]
        indexRows(row.get("blocks"), layout, resource + " selected blocks")
        for block in row["blocks"]:
            require(block.get("sourceId") == resource + ":block" + str(block["index"]), "block source ID")
            records = block.get("records")
            require(type(records) is list and len(records) == layout[block["index"]], "complete selected block")
            require([record.get("order") for record in records] == list(range(len(records))), "record order")
            for record in records:
                require(
                    record.get("kind") in ("condition", "action") and type(record.get("opcode")) is int,
                    "typed compiled record",
                )
                require(
                    type(record.get("recordOffset")) is int
                    and record["recordOffset"] >= 0
                    and type(record.get("operation")) is str
                    and re.fullmatch(r"[A-Za-z0-9_]+", record["operation"]) is not None,
                    "compiled operation identity",
                )
                require(
                    type(record.get("storedIdentifiers")) is list
                    and len(record["storedIdentifiers"]) == 2
                    and all(type(value) is str for value in record["storedIdentifiers"]),
                    "stored identifiers",
                )
                require(record.get("semanticsEvaluated") is False, "compiled semantics remain pending")
                require(
                    type(record.get("integerFieldsInStorageOrder")) is list
                    and all(type(value) is int for value in record["integerFieldsInStorageOrder"]),
                    "stored integers",
                )
                require(type(record.get("selectors")) is list and len(record["selectors"]) <= 3, "sparse selectors")
                for selector in record["selectors"]:
                    require(
                        type(selector.get("name")) is str and type(selector.get("nonzeroFilterFields")) is list,
                        "named sparse selector",
                    )
                    for field in selector["nonzeroFilterFields"]:
                        require(
                            type(field.get("position")) is int
                            and 0 <= field["position"] < 12
                            and type(field.get("value")) is int
                            and field["value"] != 0,
                            "sparse selector field",
                        )
    for row in document["items"]:
        resource = row["resource"]
        header = row.get("header", {})
        typedStorage(header)
        require(header.get("sourceId") == resource + ":header" and header.get("headerBytes") == 114, "item header")
        indexRows(row.get("abilities"), range(ITEM_LAYOUTS[resource][2]), resource + " abilities")
        indexRows(row.get("effects"), range(ITEM_LAYOUTS[resource][3]), resource + " effects")
        require(header.get("abilityCountU16") == len(row["abilities"]), "declared ability count")
        referenced = list(header.get("equippingEffectIndicesInOrder", []))
        for ability in row["abilities"]:
            typedStorage(ability)
            require(
                ability.get("sourceId") == resource + ":ability" + str(ability["index"])
                and digest(ability.get("recordSha256")),
                "ability record identity",
            )
            indices = ability.get("featureIndicesInOrder")
            require(
                type(indices) is list
                and all(type(index) is int for index in indices)
                and indices
                == list(
                    range(ability["firstFeatureIndexU16"], ability["firstFeatureIndexU16"] + ability["featureCountU16"])
                ),
                "ordered effect references",
            )
            require(
                ability.get("offset") == header["abilityOffsetU32"] + 56 * ability["index"], "ability record offset"
            )
            referenced.extend(indices)
        require(set(referenced) == {effect["index"] for effect in row["effects"]}, "all referenced effects")
        for effect in row["effects"]:
            typedStorage(effect)
            require(
                effect.get("sourceId") == resource + ":effect" + str(effect["index"])
                and digest(effect.get("recordSha256"))
                and effect.get("bytes") == 48,
                "effect record identity",
            )
            require(effect.get("offset") == header["effectOffsetU32"] + 48 * effect["index"], "effect record offset")
    frontiers = document.get("frontiers")
    require(
        type(frontiers) is list and [row.get("sourceId") for row in frontiers] == list(FRONTIER_IDS),
        "explicit frontiers",
    )
    resources = {row["resource"]: row["sha256"] for name, _ in groups for row in document[name]}
    for row in frontiers:
        require(row.get("originSha256") == resources.get(row.get("originResource")), "frontier origin fingerprint")
    require(document.get("counts", {}).get("obligations") == 218, "complete obligation count")
    return document


def requiredPoisonIds(document):
    sourceInventory(document)
    result = {state["sourceId"] for row in document["dialogues"] for state in row["states"]}
    result.update(edge["sourceId"] for row in document["dialogues"] for edge in row["edges"])
    result.update(block["sourceId"] for row in document["scripts"] for block in row["blocks"])
    for row in document["items"]:
        result.add(row["header"]["sourceId"])
        result.update(ability["sourceId"] for ability in row["abilities"])
        result.update(effect["sourceId"] for effect in row["effects"])
    result.update(row["sourceId"] for row in document["frontiers"])
    require(len(result) == 218, "unique obligation IDs")
    return result


def buildPoisonObligations(document):
    sourceInventory(document)
    rows = []

    def add(identifier, family, pointer, resource, sha256, facts, *, choices=None, effects=None):
        rows.append(
            {
                "id": identifier,
                "family": family,
                "evidence": [{"fixture": POISON_PATH, "pointer": pointer, "sha256": sha256, "resource": resource}],
                "phase": {"sourceConditions": "Retained typed syntax; not evaluated"},
                "facts": deepcopy(facts),
                "prerequisites": {"sourceEvaluation": "pending"},
                "choices": deepcopy(choices or []),
                "effects": deepcopy(effects or {}),
                "ownership": {"sourceIdentityAndNativeBinding": "pending"},
                "timers": {"sourceClockAndScheduling": "pending"},
                "nativeConversion": {
                    "plannedCaseIds": [],
                    "planIsNotNativeCoverage": True,
                    "conditionAndEffectExecution": "pending",
                },
                "implementation": {"status": "planned", "targets": [], "callbacks": []},
                "testStatus": {
                    "inventoryContract": "structural only",
                    "native": "pending",
                    "coverage": "not established",
                    "original": "pending",
                    "owner": "pending",
                },
                "editionDifferences": [SOURCE_GAP],
                "gaps": [SOURCE_GAP, NATIVE_GAP],
            }
        )

    for group_index, row in enumerate(document["dialogues"]):
        for index, state in enumerate(row["states"]):
            facts = {
                **state,
                "unlinked": index in row["unlinkedStates"],
                "falseEntry": index in row["falseEntryStates"],
                "entryPriority": row["entryPriority"],
            }
            add(
                state["sourceId"],
                "dialogueState",
                f"/dialogues/{group_index}/states/{index}",
                row["resource"],
                row["sha256"],
                facts,
                choices=state["edges"],
            )
        for index, edge in enumerate(row["edges"]):
            add(
                edge["sourceId"],
                "dialogueEdge",
                f"/dialogues/{group_index}/edges/{index}",
                row["resource"],
                row["sha256"],
                edge,
                effects={
                    "actions": edge["actions"],
                    "journalStrref": edge["journalStrref"],
                    "rawFlags": edge["rawFlags"],
                },
            )
    for group_index, row in enumerate(document["scripts"]):
        for index, block in enumerate(row["blocks"]):
            add(
                block["sourceId"],
                "scriptBlock",
                f"/scripts/{group_index}/blocks/{index}",
                row["resource"],
                row["sha256"],
                {**block, "responseWeightsDecoded": False},
            )
    for group_index, row in enumerate(document["items"]):
        add(
            row["header"]["sourceId"],
            "itemHeader",
            f"/items/{group_index}/header",
            row["resource"],
            row["sha256"],
            row["header"],
        )
        for key, family in (("abilities", "itemAbility"), ("effects", "itemEffect")):
            for index, value in enumerate(row[key]):
                add(
                    value["sourceId"],
                    family,
                    f"/items/{group_index}/{key}/{index}",
                    row["resource"],
                    row["sha256"],
                    value,
                )
    for index, frontier in enumerate(document["frontiers"]):
        add(
            frontier["sourceId"],
            "sourceFrontier",
            f"/frontiers/{index}",
            frontier["originResource"],
            frontier["originSha256"],
            frontier,
        )
    require({row["id"] for row in rows} == requiredPoisonIds(document), "obligation dropped")
    return rows
