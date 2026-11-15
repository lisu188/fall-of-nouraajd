# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Inventory the complete audited warning graph without awarding native or classic acceptance."""

import json

WARNING_PATH = "tests/fixtures/baldurs_gate_seven_suns_warning.json"
WARNING_METHODS = {"isSevenSunsWarningActor", "conversationSevenSunsWarning", "validSevenSunsWarningView"}
ACTOR = {
    "id": "cityAr0601Actor2",
    "sourceActor": "AR0601#actor2",
    "sourceArea": "AR0601",
    "sourceCreature": "DOPPSM",
    "sourceDialogue": "DOPPSM",
}
REACHABLE_STATES = {0, 1, 2, 3, 7, 8}
REACHABLE_EDGES = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16}
GLOBAL_NAMES = ("AskedForTour", "CheckedSevenSuns")


def validateWarningSource(source, warning):
    reference = source.get("references", {}).get("DOPPSM.DLG", {})
    proof = warning.get("sources", {}).get("dialogueFingerprint", {})
    if (
        not reference.get("sha256")
        or proof.get("sha256") != reference["sha256"]
        or proof.get("bytes") != reference.get("size")
        or reference.get("states") != 9
        or reference.get("transitions") != 17
    ):
        raise ValueError("Seven Suns warning source fingerprint/counts do not match DOPPSM.DLG reference")
    states = warning.get("states", [])
    if (
        len(states) != 9
        or any(type(row.get("id")) is not int for row in states)
        or {row.get("id") for row in states} != set(range(9))
    ):
        raise ValueError("Seven Suns warning must retain all nine source states")
    edges = [edge for state in states for edge in state.get("transitions", [])]
    if (
        len(edges) != 17
        or any(type(edge.get("id")) is not int for edge in edges)
        or {edge.get("id") for edge in edges} != set(range(17))
    ):
        raise ValueError("Seven Suns warning must retain all seventeen source edges")
    if (
        warning.get("actor") != ACTOR
        or warning.get("entryState") != 0
        or set(warning.get("reachableStates", [])) != REACHABLE_STATES
        or set(warning.get("reachableEdges", [])) != REACHABLE_EDGES
        or warning.get("sourceGlobalsScope") != "GLOBAL"
        or warning.get("journal", {}).get("strref") != 26986
        or warning.get("journal", {}).get("rawFlags") != 92
    ):
        raise ValueError("Seven Suns warning identity, reachability or journal source facts changed")


def warningMapping(config, methods, warning):
    actor = config.get(ACTOR["id"], {}).get("properties", {})
    if any(actor.get(key) != value for key, value in ACTOR.items() if key != "id"):
        return []
    if not WARNING_METHODS <= methods.get("BaldursGateDialog", set()):
        return []
    encoded = config.get("cityClock", {}).get("properties", {}).get("sevenSunsWarningDefinition", "")
    try:
        definition = json.loads(encoded.removeprefix("city-json:"))
    except (TypeError, ValueError, AttributeError):
        return []
    if not isinstance(definition, dict) or type(definition.get("version")) is not int:
        return []
    journal = warning["journal"]
    if definition != {
        "version": 1,
        "dialogue": "DOPPSM",
        "fingerprint": warning["sources"]["dialogueFingerprint"]["sha256"],
        "journalQuest": journal["nativeQuestId"],
    }:
        return []
    lead = config.get(journal["nativeQuestId"], {})
    if lead.get("class") != journal["nativeClass"] or journal["nativeClass"] not in methods:
        return []
    return [ACTOR["id"], "cityClock.sevenSunsWarningDefinition", journal["nativeQuestId"]]


def addWarningObligations(source, config, methods, warning, add, entries):
    validateWarningSource(source, warning)
    targets = warningMapping(config, methods, warning)
    digest = warning["sources"]["dialogueFingerprint"]["sha256"]
    phase = {"source": "DOPPSM entry predicates and selected transitions", "scenarioChapters": [5, 7]}
    ownership = {
        "sourceOwner": ACTOR["sourceActor"],
        "nativeActor": ACTOR["id"],
        "stock": source.get("creatures", {}).get("DOPPSM", {}).get("items", []),
        "retirement": warning["conversion"]["retirement"],
        "journal": "One separate active lead; no Scar quest acceptance/completion or reward.",
    }
    timers = {
        "sourceTimers": "No timer action appears in the retained warning graph; external timing remains unproved.",
        "cancellation": warning["cancellation"],
        "workBudget": warning["conversion"]["workBudget"],
    }
    conversion = {
        "classic": warning["edition"],
        "nativeProposal": warning["conversion"],
        "automaticEntry": warning["boundaries"]["automaticInitdlg"],
        "externalEntry": warning["boundaries"]["externalLink"],
        "acceptance": "Source/model mapping only; native, save/reload, visual, owner and original parity pending.",
    }
    common_gaps = [
        "INITDLG automatic initiation and external source entry remain unaudited.",
        "Original BG1 journal flag conversion, timing and complete surrounding quest context remain unproved.",
        "No native route, save/reload, coverage, visual or owner acceptance is awarded by this ledger.",
    ]

    def proof(pointer):
        return [
            {"fixture": WARNING_PATH, "pointer": pointer, "sha256": digest, "resource": "DOPPSM.DLG"},
            {
                "fixture": "tests/fixtures/baldurs_gate_city_source.json",
                "pointer": "/references/DOPPSM.DLG",
                "sha256": digest,
                "resource": "DOPPSM.DLG",
            },
        ]

    def status(reachable):
        return "partial" if reachable and targets else "planned"

    def gaps(state_id, reachable):
        result = list(common_gaps)
        if not targets:
            result.append(
                "Exact warning actor, presentation helpers, protected clock definition or journal lead mapping is absent."
            )
        if not reachable:
            result.append(warning["boundaries"]["state" + str(state_id)])
            result.append(
                "Retained original-source obligation; no path from the audited explicit entry is implemented."
            )
        return result

    for state_index, state in enumerate(warning["states"]):
        reachable = state["id"] in REACHABLE_STATES
        add(
            f"DOPPSM.DLG#state{state['id']}",
            "dialogueState",
            proof(f"/states/{state_index}"),
            area=ACTOR["sourceArea"],
            phase=phase,
            facts={key: value for key, value in state.items() if key != "transitions"},
            prerequisites={"entryPredicates": state["entry"], "reachableFromExplicitEntry": reachable},
            choices=[edge["id"] for edge in state["transitions"]],
            effects={
                "selectedEdges": [{"id": edge["id"], "effects": edge["effects"]} for edge in state["transitions"]]
            },
            ownership=ownership,
            timers=timers,
            conversion=conversion,
            targets=targets if reachable else [],
            status=status(reachable),
            callbacks=sorted(WARNING_METHODS) if reachable and targets else [],
            gaps=gaps(state["id"], reachable),
        )
        for edge_index, edge in enumerate(state["transitions"]):
            reachable = edge["id"] in REACHABLE_EDGES
            add(
                f"DOPPSM.DLG#edge{edge['id']}",
                "dialogueEdge",
                proof(f"/states/{state_index}/transitions/{edge_index}"),
                area=ACTOR["sourceArea"],
                phase=phase,
                facts={"sourceState": state["id"], **edge},
                prerequisites={"conditions": edge["conditions"], "reachableFromExplicitEntry": reachable},
                choices=[edge["id"]],
                effects={"actions": edge["effects"], "next": edge["next"], "journal": edge["journal"]},
                ownership=ownership,
                timers=timers,
                conversion=conversion,
                targets=targets if reachable else [],
                status=status(reachable),
                callbacks=sorted(WARNING_METHODS) if reachable and targets else [],
                gaps=gaps(state["id"], reachable),
            )
    add(
        "DOPPSM.DLG#journal26986",
        "dialogueJournal",
        proof("/journal"),
        area=ACTOR["sourceArea"],
        phase=phase,
        facts=warning["journal"],
        prerequisites={"selectedEscapeEdges": warning["terminalEscapeEdges"]},
        choices=warning["terminalEscapeEdges"],
        effects={"journalStrref": 26986, "rawFlags": 92, "sourceActions": [{"op": "EscapeArea", "args": []}]},
        ownership=ownership,
        timers=timers,
        conversion=conversion,
        targets=targets,
        status=status(True),
        callbacks=sorted(WARNING_METHODS) if targets else [],
        gaps=gaps(3, True),
    )
    for name in GLOBAL_NAMES:
        readers, writers = [], []
        for state in warning["states"]:
            for edge in state["transitions"]:
                for condition in edge["conditions"]:
                    if condition["op"] == "Global" and condition["args"][:2] == [name, "GLOBAL"]:
                        readers.append({"edge": edge["id"], "predicate": condition})
                for action in edge["effects"]:
                    if action["op"] == "SetGlobal" and action["args"][:2] == [name, "GLOBAL"]:
                        writers.append({"edge": edge["id"], "action": action})
        add(
            "DOPPSM.DLG#global" + name,
            "sourceGlobal",
            proof("/sharedGlobals") + proof("/globalDefaults/" + name)[:1],
            area=ACTOR["sourceArea"],
            phase=phase,
            facts={"name": name, "scope": "GLOBAL", "missingDefault": warning["globalDefaults"][name]},
            prerequisites={"sourceReads": readers, "variableNames": "ASCII case-insensitive; scope exact GLOBAL"},
            choices=[row["edge"] for row in writers],
            effects={
                "selectedEdgeWrites": writers,
                "existingIntegers": "Preserve unknown integer values and unrelated keys; no 0/1 or 0/2 clamp.",
            },
            ownership={
                "sharedNamespace": "plugin_citySourceGlobals.GLOBAL",
                "privateWarningReceiptIsAuthoritative": False,
            },
            timers=timers,
            conversion={**conversion, "sharedGlobals": warning["sharedGlobals"]},
            targets=targets,
            status=status(True),
            callbacks=sorted(WARNING_METHODS) if targets else [],
            gaps=gaps(0, True),
        )
    if targets:
        for row in entries:
            if row["id"] in {"DOPPSM.DLG:behavior", "AR0601#actor2:conversation"}:
                row["implementation"] = {
                    "status": "partial",
                    "targets": sorted(targets),
                    "callbacks": sorted(WARNING_METHODS),
                }
                row["gaps"] += common_gaps + [
                    "Only explicit-entry states 0/1/2/3/7/8 and twelve reachable edges have a presentation mapping.",
                    "States 4/5/6, edges 10-14, SSUNGU external entry, INITDLG and hostility remain planned, not excluded.",
                ]
