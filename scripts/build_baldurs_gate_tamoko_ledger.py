#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Required supporting-EE Tamoko source inventory; never native, original-game or owner credit."""

import ast
from copy import deepcopy
import hashlib
import json

TAMOKO_PATH = "tests/fixtures/baldurs_gate_city_tamoko_dialogue.json"
TAMOKO_ROUTES_PATH = "tests/gameplay_routes_baldurs_gate.py"
JOURNAL_IDS = (27461, 27462, 27463)
SOURCE_GAP = "Installed EE evidence does not authenticate original BG1 behavior or journal categories."
NATIVE_GAP = "Exact-head native dialogue, journal panel, save/reload, lifecycle and owner acceptance remain pending."


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def sourceGraph(supplement):
    if (
        not isinstance(supplement, dict)
        or supplement.get("kind") != "TamokoDialogueSourceMappingSupplement"
        or type(supplement.get("schemaVersion")) is not int
        or supplement["schemaVersion"] != 1
    ):
        raise ValueError("Required Tamoko source supplement has an unsupported schema")
    states = supplement.get("states")
    if (
        not isinstance(states, list)
        or len(states) != 26
        or any(not isinstance(row, dict) or not isinstance(row.get("edges"), list) for row in states)
        or [row.get("state") for row in states] != list(range(26))
        or any(type(row.get("state")) is not int for row in states)
        or supplement.get("sourceJournalIds") != list(JOURNAL_IDS)
    ):
        raise ValueError("Required Tamoko inventory must contain all26 states and three journal IDs")
    edges = [(state["state"], index, edge) for state in states for index, edge in enumerate(state.get("edges", []))]
    if (
        len(edges) != 50
        or any(not isinstance(edge, dict) or type(edge.get("edge")) is not int for _, _, edge in edges)
        or sorted(edge["edge"] for _, _, edge in edges) != list(range(50))
    ):
        raise ValueError("Required Tamoko inventory must contain all50 unique edges")
    digest = supplement.get("dialogFingerprint", {}).get("baseSha256", "")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("Required Tamoko DLG fingerprint is missing")
    for _, _, edge in edges:
        if edge.get("targetState") is not None and (
            type(edge["targetState"]) is not int or edge["targetState"] not in range(26)
        ):
            raise ValueError("Unknown Tamoko source state target")
        if edge.get("targetResource") not in ("", "TAMOKO"):
            raise ValueError("External Tamoko dialogue is outside this finite inventory")
        if edge.get("journalStrref") is not None and edge["journalStrref"] not in JOURNAL_IDS:
            raise ValueError("Unknown Tamoko journal add")
        if edge.get("journalEraseStrrefs") and edge["journalEraseStrrefs"] != list(JOURNAL_IDS):
            raise ValueError("Tamoko journal erase order differs from source")
    return states, edges, digest


def requiredTamokoIds(supplement):
    sourceGraph(supplement)
    return (
        {f"TAMOKO.DLG:state{index}" for index in range(26)}
        | {f"TAMOKO.DLG:edge{index}" for index in range(50)}
        | {f"TAMOKO.DLG:journal{number}" for number in JOURNAL_IDS}
    )


def plannedCases(route_source):
    """Read literal authored plans without importing or executing route/game code."""
    plans = {}
    for node in ast.walk(ast.parse(route_source)):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.func.id != "RouteCase"
            or not node.args
            or not isinstance(node.args[0], ast.Constant)
            or not isinstance(node.args[0].value, str)
            or not node.args[0].value.startswith(("baldurs-gate-native-early-tamoko-", "baldurs-gate-native-tamoko-"))
        ):
            continue
        if len(node.args) < 5:
            raise ValueError("Malformed Tamoko RouteCase")
        callback = node.args[4]
        if (
            not isinstance(callback, ast.Call)
            or not isinstance(callback.func, ast.Name)
            or callback.func.id != "partial"
            or not callback.args
            or not isinstance(callback.args[0], ast.Name)
            or callback.args[0].id not in ("tamokoEarlyTopology", "tamokoFinalTopology")
        ):
            raise ValueError("Unsupported Tamoko planned callback")
        case_id = node.args[0].value
        if case_id in plans:
            raise ValueError("Duplicate Tamoko planned case")
        options = {keyword.arg: ast.literal_eval(keyword.value) for keyword in callback.keywords}
        plans[case_id] = (callback.args[0].id, options)
    return plans


def plannedPaths(states, route_source):
    """Associate only literal paths; never evaluate native reaction or source conditions."""
    paths = {}
    for case_id, (callback, options) in plannedCases(route_source).items():
        visits, transitions = set(), set()

        def walk(start, replies, terminal=None, rescued=False, outcome=""):
            remaining = list(replies)
            current = start
            for _ in range(32):
                visits.add(current)
                edges = states[current]["edges"]
                automatic = [edge for edge in edges if edge.get("replyId") is None]
                if automatic:
                    if len(automatic) == 1:
                        candidates = automatic
                    elif current == 8:
                        candidates = [
                            edge
                            for edge in automatic
                            if any(
                                fact.get("name") == "RescuedEltan"
                                and fact.get("scope") == "GLOBAL"
                                and fact.get("value") == int(rescued)
                                for fact in (edge.get("condition") or {}).get("globalNumericFacts", [])
                            )
                        ]
                    else:
                        raise ValueError("Unaudited automatic Tamoko plan branch")
                else:
                    if not remaining:
                        raise ValueError("Incomplete Tamoko planned reply sequence")
                    reply = remaining.pop(0)
                    candidates = [edge for edge in edges if edge.get("replyId") == reply]
                    if len(candidates) > 1 and current == 23 and reply == "philosophy":
                        target = 25 if outcome == "complete" else 24 if outcome == "fight" else None
                        candidates = [edge for edge in candidates if edge.get("targetState") == target]
                if len(candidates) != 1:
                    raise ValueError("Ambiguous or invalid Tamoko literal plan")
                edge = candidates[0]
                transitions.add(edge["edge"])
                if edge.get("targetState") is None:
                    if remaining or terminal is not None and current != terminal:
                        raise ValueError("Tamoko planned terminal mismatch")
                    if outcome and current not in (
                        {21, 24} if outcome == "fight" else {25} if outcome == "complete" else set()
                    ):
                        raise ValueError("Tamoko planned outcome does not match its terminal")
                    return
                current = edge["targetState"]
            raise ValueError("Tamoko planned path exceeds finite graph bound")

        if callback == "tamokoEarlyTopology":
            walk(0, options["first_choices"], options["first_terminal"])
            walk(8, options["second_choices"], options["second_terminal"], options.get("rescue_before_second", False))
        else:
            walk(20, options["choices"], outcome=options["outcome_key"])
        paths[case_id] = (visits, transitions)
    return paths


def buildTamokoObligations(supplement, config, script, route_source=""):
    states, edges, digest = sourceGraph(supplement)
    paths = plannedPaths(states, route_source)
    code_methods = {
        node.name for node in ast.walk(ast.parse(script)) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    rows = []

    def add(identifier, family, pointer, facts, callbacks, cases, *, choices=None, effects=None, ownership=None):
        callbacks = sorted(set(callbacks))
        targets = ["res/maps/baldursGate/script.py:" + name for name in callbacks if name in code_methods]
        gaps = [SOURCE_GAP, NATIVE_GAP]
        if not cases:
            gaps.append("No reviewed literal natural-route plan currently targets this exact source obligation.")
        rows.append(
            {
                "id": identifier,
                "family": family,
                "evidence": [{"fixture": TAMOKO_PATH, "pointer": pointer, "sha256": digest, "resource": "TAMOKO.DLG"}],
                "phase": {
                    "source": "Retained source conditions, not evaluated here",
                    "nativePrerequisites": "Read actual planned route prerequisites; timing and chapter admission remain pending",
                },
                "facts": deepcopy(facts),
                "prerequisites": {
                    "sourceConditions": "Retained in facts; native/source timing and reaction remain pending"
                },
                "choices": choices or [],
                "effects": deepcopy(effects or {}),
                "ownership": ownership or {"actor": "cityAr0800ScriptActorTamoko", "sourceCreature": "TAMOKO"},
                "timers": {"sourceExecutionTiming": "pending"},
                "nativeConversion": {
                    "plannedCaseIds": sorted(cases),
                    "plannedCaseSource": TAMOKO_ROUTES_PATH,
                    "planIsNotNativeCoverage": True,
                    "conditionEvaluation": "No reaction, GLOBAL or engine condition is executed by this helper",
                },
                "implementation": {"status": "planned", "targets": targets, "callbacks": callbacks},
                "testStatus": {
                    "inventoryContract": "structural only",
                    "native": "pending",
                    "coverage": "not established",
                    "original": "pending",
                    "owner": "pending",
                },
                "editionDifferences": [SOURCE_GAP],
                "gaps": gaps,
            }
        )

    for index, state in enumerate(states):
        cases = {case_id for case_id, (visits, _) in paths.items() if index in visits}
        add(
            f"TAMOKO.DLG:state{index}",
            "dialogueState",
            f"/states/{index}",
            {
                key: state[key]
                for key in ("state", "npcStrref", "npcParaphrase", "condition", "meeting")
                if key in state
            },
            [state["callback"]],
            cases,
            choices=[edge["edge"] for edge in state["edges"]],
        )
    for state_id, index, edge in edges:
        cases = {case_id for case_id, (_, transitions) in paths.items() if edge["edge"] in transitions}
        add(
            f"TAMOKO.DLG:edge{edge['edge']}",
            "dialogueEdge",
            f"/states/{state_id}/edges/{index}",
            {
                "sourceState": state_id,
                **{
                    key: edge[key]
                    for key in (
                        "edge",
                        "replyStrref",
                        "paraphrase",
                        "flags",
                        "targetResource",
                        "targetState",
                        "condition",
                        "action",
                        "journalStrref",
                        "journalEraseStrrefs",
                    )
                    if key in edge
                },
            },
            [edge["callback"], edge["implementation"]],
            cases,
            choices=[edge["replyId"]] if edge.get("replyId") is not None else [],
            effects={
                "action": edge.get("action"),
                "journalAdd": edge.get("journalStrref"),
                "journalErase": edge.get("journalEraseStrrefs", []),
            },
        )
    for index, number in enumerate(JOURNAL_IDS):
        additions = [edge["edge"] for _, _, edge in edges if edge.get("journalStrref") == number]
        erasures = [edge["edge"] for _, _, edge in edges if number in edge.get("journalEraseStrrefs", [])]
        cases = {case_id for case_id, (_, transitions) in paths.items() if transitions & set(additions + erasures)}
        add(
            f"TAMOKO.DLG:journal{number}",
            "dialogueJournal",
            f"/sourceJournalIds/{index}",
            {"strref": number, "addEdges": additions, "eraseEdges": erasures, "rawAddFlags": 92},
            ["writeTamokoEarlyJournal", "syncTamokoJournal", "commitTamokoFinalMeeting"],
            cases,
            effects={
                "addAtEdges": additions,
                "eraseAtEdges": erasures,
                "category": "Map-local active informational projection; original journal category unresolved",
            },
            ownership={
                "owner": "native player",
                "onlyFixedTamokoNotesMayBeErased": True,
                "preserveUnrelatedActiveAndCompletedQuests": True,
                "reward": "none",
            },
        )
    if {row["id"] for row in rows} != requiredTamokoIds(supplement):
        raise ValueError("Required Tamoko obligations were dropped")
    return rows
