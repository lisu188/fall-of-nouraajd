# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage the retained seven-graph poison port without enabling an incomplete source cutover."""

from copy import deepcopy
import json

POISON_AREAS = {
    "MAREK": ("AR0300", "AR0115"),
    "LOTHAN": ("AR0300", "AR0700", "AR0106"),
    "DIVINE": ("AR0700",),
    "PUMBERL": ("AR0609",),
    "JALANT": ("AR0609",),
    "CHANTH": ("AR0132",),
    "TENYA2": ("AR0609",),
}
FACTORIES = {
    "MAREK1": "cityPoisonMarek1",
    "LOTHAN": "cityPoisonLothander",
    "TENYA2": "cityPoisonTenya2",
    "JALANT": "cityAr0609ScriptActorJalant",
}


def encoded(value):
    return "city-json:" + json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def sourcePointKey(area, point):
    return area + "#" + str(point[0]) + "," + str(point[1])


def sourcePositions(graphs, project):
    pairs = {("AR0700", 2361, 1090), ("AR0115", 406, 344)}

    def inspect(node, areas):
        operation, arguments = node["operation"], node["arguments"]
        if operation == "ActionOverride":
            inspect(arguments[1], areas)
        elif operation in ("MoveToPoint", "CreateCreature"):
            point = arguments[0] if operation == "MoveToPoint" else arguments[1]
            pairs.update((area, point["x"], point["y"]) for area in areas)
        elif operation == "EscapeAreaMove":
            pairs.add((arguments[0]["value"], arguments[1]["value"], arguments[2]["value"]))

    for graph in graphs:
        for edge in graph["edges"]:
            for action in edge["actions"]:
                inspect(action, POISON_AREAS[graph["resource"].removesuffix(".DLG")])
    return {sourcePointKey(area, (x, y)): list(project(area, [x, y])) for area, x, y in sorted(pairs)}


def preparePoisonSource(document, config, source, dialogue, followup, authored, project):
    # This authored map policy also applies to already-initialized saves through the resume/bootstrap callback.
    document["properties"].update(verifiedLoadResumeReceiver="cityClock", plugin_citySourceKillXp=True)
    document.setdefault("propertytypes", {}).update(verifiedLoadResumeReceiver="string", plugin_citySourceKillXp="bool")
    creatures = source.get("creatures", {})
    if not (set(POISON_AREAS) | {"MAREK1"}).issubset(creatures):
        return False  # Compact generator fixtures do not declare this source inventory.
    graphs = dialogue["dialogues"] + [followup["dialogue"]]
    if (len(graphs), sum(len(g["states"]) for g in graphs), sum(len(g["edges"]) for g in graphs)) != (7, 84, 135):
        raise ValueError("The retained poison graph inventory is incomplete")
    state_ids = {state["sourceId"] for graph in graphs for state in graph["states"]}
    edge_ids = {edge["sourceId"] for graph in graphs for edge in graph["edges"]}
    if set(authored.get("states", {})) != state_ids or set(authored.get("edges", {})) != edge_ids:
        raise ValueError("The authored poison meanings do not cover the exact source graph")
    legacy_dialogs = {identity for identity in config if identity.endswith("Dialog")}
    initial = []
    for identity, row in config.items():
        props = row.get("properties", {})
        code = props.get("sourceCreature")
        if code in ("MAREK", "LOTHAN", "DIVINE", "PUMBERL", "CHANTH") and row.get("class") == "CCreature":
            initial.append(
                {
                    "id": identity,
                    "typeId": identity,
                    "resource": code,
                    "area": props["sourceArea"],
                    "sourceActor": props["sourceActor"],
                }
            )
    if len(initial) != 5:
        raise ValueError("The initial poison source owners are not the exact five placements")
    for code, identity in FACTORIES.items():
        facts = creatures[code]
        if code == "JALANT":
            if config[identity]["properties"]["sourceCreature"] != code:
                raise ValueError("The staged Jalantha factory belongs to another source owner")
            continue
        actor = deepcopy(config["cityAr0300Actor29"])
        area = "AR0115" if code == "MAREK1" else "AR0700" if code == "LOTHAN" else "AR0609"
        props = actor["properties"]
        props.update(
            label=facts["displayName"],
            sourceCreature=code,
            sourceDialogue=facts["dialogue"],
            sourceArea=area,
            simulationRegion=area,
            sourceActor=identity,
            sourceKillXp=facts["kill_xp"],
            gold=facts["gold"],
            sourceInventory=encoded([dict(item, sourceIndex=index) for index, item in enumerate(facts["items"])]),
            sourceItemSlots=encoded(facts["itemSlots"]),
            phaseMin=5,
            phaseMax=7,
        )
        props["baseStats"]["properties"]["stamina"] = max(1, (facts["max_hit_points"] + 6) // 7)
        if code == "MAREK1":
            props["sourceSpawnFact"] = "AR0115.BCS#spawn0"
        config[identity] = actor
        dialog = deepcopy(config["cityAr0300Actor29Dialog"])
        dialog["properties"].update(actorId=identity, speaker=facts["displayName"])
        for state in dialog["properties"]["states"]:
            if state["properties"]["stateId"] == "ENTRY":
                state["properties"]["text"] = facts["displayName"]
        config[identity + "Dialog"] = dialog
    source_dialogs = {}
    for identity in [row["id"] for row in initial] + list(FACTORIES.values()):
        legacy_id = identity + "Dialog"
        dialog_id = identity + "SourceDialog" if legacy_id in legacy_dialogs else legacy_id
        if dialog_id != legacy_id:
            config[dialog_id] = deepcopy(config[legacy_id])
        source_dialogs[identity] = dialog_id
        for state in config[dialog_id]["properties"]["states"]:
            for option in state["properties"].get("options", []):
                if option["properties"].get("action") == "talk":
                    option["properties"]["nextStateId"] = "EXIT"
    for row in initial:
        row["dialogId"] = source_dialogs[row["typeId"]]
    store_dialog = deepcopy(config["cityAr0132Actor1Dialog"])
    for state in store_dialog["properties"]["states"]:
        state["properties"]["options"] = [
            option
            for option in state["properties"].get("options", [])
            if "StoreTem0132" in option["properties"].get("action", "") or not option["properties"].get("action")
        ]
    config["cityPoisonStoreTEM0132Dialog"] = store_dialog
    definitions = {
        "dialogues": graphs,
        "initialActors": initial,
        "factories": {
            code: {
                "typeId": identity,
                "area": config[identity]["properties"]["sourceArea"],
                "dialogId": source_dialogs[identity],
            }
            for code, identity in FACTORIES.items()
        },
        "positions": sourcePositions(graphs, project),
        "sourceEdition": dialogue["sourceEdition"],
        "originalParityEstablished": False,
    }
    config["cityClock"]["properties"].update(
        poisonSourceDefinitions=encoded(definitions),
        poisonAuthoredText=encoded(authored),
        plugin_cityPoisonSourceEnabled=False,
    )
    return True
