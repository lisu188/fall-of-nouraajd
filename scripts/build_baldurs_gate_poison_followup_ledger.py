#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Project retained supporting-EE facts without granting gameplay or original-game acceptance."""

from copy import deepcopy
import hashlib
import json

try:
    from scripts.build_baldurs_gate_poison_ledger import NATIVE_GAP, SOURCE_GAP, noRawPayload, require
except ModuleNotFoundError:
    from build_baldurs_gate_poison_ledger import NATIVE_GAP, SOURCE_GAP, noRawPayload, require

FOLLOWUP_PATH = "tests/fixtures/baldurs_gate_city_poison_followup.json"
FACTUAL_SHA256 = "bdb0544293524349042b9f8549cab593d7a1564b5f9550fc920d22d0c9ee05b0"


def sourceInventory(document):
    """Admit only the reviewed finite fact set; changed facts require another source review."""
    require(type(document) is dict, "follow-up document")
    noRawPayload(document)
    actual = hashlib.sha256(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    require(actual == FACTUAL_SHA256, "follow-up facts differ from reviewed source projection")
    return document


def requiredFollowupIds(document):
    sourceInventory(document)
    result = {"TENYA2.DLG:state" + str(index) for index in range(12)}
    result.update("TENYA2.DLG:edge" + str(index) for index in range(23))
    result.update(
        (
            "BDMAREK.SPL:header",
            "BDMAREK.SPL:ability0",
            "BDMAREK.SPL:effect0",
            "BDMAREK.SPL:effect1",
            "GTIMES.IDS:ONE_DAY",
            "GTIMES.IDS:TEN_DAYS",
        )
    )
    require(len(result) == 41, "follow-up unique obligation IDs")
    return result


def buildFollowupObligations(document):
    sourceInventory(document)
    rows = []

    def add(value, family, pointer, resource, sha256, *, choices=None, effects=None):
        rows.append(
            {
                "id": value["sourceId"],
                "family": family,
                "evidence": [{"fixture": FOLLOWUP_PATH, "pointer": pointer, "sha256": sha256, "resource": resource}],
                "phase": {"sourceConditions": "Retained typed syntax; not evaluated"},
                "facts": deepcopy(value),
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

    dialogue = document["dialogue"]
    for index, state in enumerate(dialogue["states"]):
        add(
            {**state, "unlinked": index in dialogue["unlinkedWithinRetainedGraph"]},
            "dialogueState",
            f"/dialogue/states/{index}",
            dialogue["resource"],
            dialogue["sha256"],
            choices=state["edges"],
        )
    for index, edge in enumerate(dialogue["edges"]):
        add(
            edge,
            "dialogueEdge",
            f"/dialogue/edges/{index}",
            dialogue["resource"],
            dialogue["sha256"],
            effects={"actions": edge["actions"], "journalStrref": edge["journalStrref"], "rawFlags": edge["rawFlags"]},
        )
    spell = document["spell"]
    add(spell["header"], "spellHeader", "/spell/header", spell["resource"], spell["sha256"])
    for key, family in (("abilities", "spellAbility"), ("effects", "spellEffect")):
        for index, value in enumerate(spell[key]):
            add(value, family, f"/spell/{key}/{index}", spell["resource"], spell["sha256"])
    timers = document["timers"]
    for index, value in enumerate(timers["constants"]):
        add(value, "sourceTimerConstant", f"/timers/constants/{index}", timers["resource"], timers["sha256"])
    require({row["id"] for row in rows} == requiredFollowupIds(document), "follow-up obligation dropped")
    return rows
