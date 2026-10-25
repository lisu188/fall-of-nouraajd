# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Proposal-only immutable source contract. This helper performs no game actions."""

from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path

REVIEWED_FILENAME = "baldurs_gate_city_palace_listener_closure.json"
REVIEWED_EVIDENCE_SHA256 = "88889a146d1a3f22de428eef4440e766e213ee879b070c780a1eaa8f28a58d12"
EXPECTED_COUNTS = {
    "actorCreatureResources": 21,
    "directActorBCS": 22,
    "areaBCS": 1,
    "dialogueBCSBoundaries": 4,
    "allBCSInventoried": 27,
    "actorDialogues": 10,
    "selectedHeard2And50Blocks": 4,
    "resourceFingerprints": 79,
}
ARE_SLOTS = ("override", "general", "class", "race", "default", "specific")
CRE_SLOTS = ("override", "class", "race", "general", "default")
EXPECTED_CREATURES = {
    "FLAM10",
    "NOBW5",
    "NOBL12",
    "NOBLPA",
    "NOBLPA1",
    "NOBLPA2",
    "NOBLPA3",
    "NOBLPA4",
    "NOBLPA5",
    "GDOPP7",
    "GDOPP71",
    "GDOPP72",
    "GDOPP73",
    "GDOPP74",
    "GDOPP75",
    "BELT",
    "LIIA",
    "SAREVO2",
    "FLAME",
    "ANGELO",
    "WINSKI",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def selectedSlots(area_scripts, creature_scripts):
    require(set(area_scripts) == set(ARE_SLOTS), "ARE slot names changed")
    require(set(creature_scripts) == set(CRE_SLOTS), "CRE slot names changed")
    result = {}
    for slot in ARE_SLOTS:
        area = area_scripts[slot]
        creature = creature_scripts.get(slot, "")
        value = area if area else creature
        result[slot] = {
            "resource": value.upper() if value and value.upper() != "NONE" else "",
            "origin": "area" if area else "creature" if creature else "none",
        }
    return result


def checkRecord(row, operation, offset, integers, selector=None, strings=None):
    require(
        row["operation"] == operation and row["sourceId"].endswith("#offset" + str(offset)),
        "Source operation/offset mismatch",
    )
    require(row["integers"] == integers, "Source integer arguments mismatch")
    require(row["strings"] == (strings if strings is not None else ["", ""]), "Source string arguments mismatch")
    if selector is not None:
        slot, sparse, name = selector
        target = row["selectors"][slot]
        expected = [0] * 12
        for index, value in sparse.items():
            expected[index] = value
        require(target == {"ids": expected, "name": name}, "Source object selector mismatch")
    require(not row.get("negated", False), "Source condition unexpectedly negated")


def validateBlockOwnership(block, resource):
    require(block["sourceId"].startswith(resource + ".BCS#block"), "Source block ownership mismatch")
    for field in ("conditions", "actions"):
        require(
            all(row["sourceId"].startswith(resource + ".BCS#offset") for row in block[field]),
            "Source record ownership mismatch",
        )


def validateLogicalEvidence(evidence):
    """Check cross-fields independently of the immutable review digest; never interprets a game."""
    require(evidence["scope"] == "boundedAR0108ActorScriptReferenceClosure", "Wrong evidence scope")
    require(
        evidence["schemaVersion"] == 2
        and evidence["sourceHelperFingerprintPolicy"] == "CRLF-to-LF bytes; all other bytes preserved",
        "Helper fingerprint normalization policy mismatch",
    )
    require(
        evidence["resourceOriginPathPolicy"] == "Backslash separators in relative source-origin metadata",
        "Resource-origin normalization policy mismatch",
    )
    require(
        set(evidence["sourceHelpers"])
        == {
            name + ".py"
            for name in (
                "audit_candlekeep_source",
                "audit_baldurs_gate_palace",
                "audit_baldurs_gate_palace_shout",
                "build_baldurs_gate_prison_source_fixture",
                "build_baldurs_gate_source_fixture",
            )
        },
        "Source helper dependency inventory mismatch",
    )
    expected_flags = {
        "nativeImplementationReady",
        "nativeExecutionVerified",
        "originalParityEstablished",
        "originalAcceptanceReady",
        "ledgerCompletionCredit",
    }
    require(
        set(evidence["acceptance"]) == expected_flags
        and all(value is False for value in evidence["acceptance"].values()),
        "Acceptance must remain exactly false",
    )
    creatures, scripts, actors = evidence["creatures"], evidence["scripts"], evidence["areaActors"]
    require(set(creatures) == EXPECTED_CREATURES and len(actors) == 11, "Source actor population changed")
    for name, creature in creatures.items():
        expected_ea = 255 if name.startswith("GDOPP7") or name == "FLAME" else 128
        require(creature["allegiance"] == expected_ea, "Initial source allegiance changed")
        require(creature["intrinsicOpcode82Count"] == 0, "Intrinsic AI-script effect added")
    direct = {"AR0108"} | {
        value
        for creature in creatures.values()
        for value in creature["scripts"].values()
        if value and value.upper() != "NONE"
    }
    for index, actor in enumerate(actors):
        require(actor["sourceId"] == "AR0108.ARE#actor" + str(index), "ARE index mismatch")
        expected_creature = "FLAM10" if index < 6 else "NOBW5" if index < 8 else "NOBL12"
        require(actor["creature"] == expected_creature, "ARE creature mismatch")
        expected_area = {slot: "" for slot in ARE_SLOTS}
        if index == 3:
            expected_area["class"] = "FLAM10A"
        if index >= 6:
            expected_area["specific"] = "SARRUN"
        require(actor["areaScripts"] == expected_area, "ARE physical slot assignment mismatch")
        selected = selectedSlots(actor["areaScripts"], creatures[actor["creature"]]["scripts"])
        require(actor["selectedScriptsBySlot"] == selected, "ARE/CRE slot precedence mismatch")
        direct.update(row["resource"] for row in selected.values() if row["resource"])
    require(
        direct == {name for name, row in scripts.items() if row["role"] == "directActorOrArea"},
        "Direct script closure summary mismatch",
    )
    for name, script in scripts.items():
        require(script["recordCount"] == sum(script["operationCounts"].values()), "Record summary mismatch")
        require(len(script["heard"]) == script["operationCounts"].get("Heard", 0), "Heard summary mismatch")
        require(len(script["shout"]) == script["operationCounts"].get("Shout", 0), "Shout summary mismatch")
        require(not script["BCSReferences"], "Unfollowed script reference")
        require(name + ".BCS" in evidence["resourceFingerprints"], "Missing script resource pin")
    listeners = evidence["selectedHeard2And50Blocks"]
    require(
        set(listeners)
        == {
            row["blockSourceId"]
            for script in scripts.values()
            for row in script["heard"]
            if row["integers"][0] in (2, 50)
        },
        "Listener inventory summary mismatch",
    )
    for source_id, block in listeners.items():
        name = source_id.split(".", 1)[0]
        validateBlockOwnership(block, name)
        matching = [
            {key: value for key, value in row.items() if key != "blockSourceId"}
            for row in scripts[name]["heard"]
            if row["blockSourceId"] == source_id
        ]
        require(block["conditions"] == matching, "Listener condition/inventory cross-binding mismatch")
    crossguards = evidence["higherAndFallbackScriptCrossguards"]["blocks"]
    require(
        set(crossguards) == {"SHOUT", "SEEENEMY", "RUNENEMY", "WDASIGHT", "WDRUNSGT", "WTRUNSGT", "WTASIGHT"},
        "Crossguard script population changed",
    )
    for name, blocks in crossguards.items():
        require(
            [row["sourceId"] for row in blocks]
            == [name + ".BCS#block" + str(n) for n in range(scripts[name]["blockCount"])],
            "Crossguard block inventory mismatch",
        )
        counts = Counter(
            record["operation"] for block in blocks for field in ("conditions", "actions") for record in block[field]
        )
        require(dict(counts) == scripts[name]["operationCounts"], "Crossguard operation summary mismatch")
    for name, block_index, trigger_offset, action_offset in (("FLAM10", 2, 705, 779), ("FLAM10A", 3, 1223, 1297)):
        leading = evidence["preemptionAndBehavior3Facts"][name]
        validateBlockOwnership(leading, name)
        require(
            leading["sourceId"] == name + ".BCS#block0"
            and len(leading["conditions"]) == 2
            and len(leading["actions"]) == 1,
            "Guard leading branch changed",
        )
        checkRecord(leading["conditions"][0], "Allegiance", 9, [128, 0, 0, 0], (0, {7: 1}, ""))
        checkRecord(leading["conditions"][1], "Global", 69, [3, 0, 0, 0], strings=["GLOBALSarevokBehavior", ""])
        checkRecord(leading["actions"][0], "Enemy", 160, [0] * 5)
        listener = listeners[name + ".BCS#block" + str(block_index)]
        require(len(listener["conditions"]) == 1 and len(listener["actions"]) == 1, "Guard listener branch changed")
        checkRecord(listener["conditions"][0], "Heard", trigger_offset, [2, 0, 0, 0], (0, {}, "Sarevok"))
        checkRecord(listener["actions"][0], "Attack", action_offset, [0] * 5, (1, {}, "Sarevok"))
    noble = evidence["preemptionAndBehavior3Facts"]["SARRUN"]
    validateBlockOwnership(noble, "SARRUN")
    require(
        noble["sourceId"] == "SARRUN.BCS#block0" and len(noble["conditions"]) == len(noble["actions"]) == 1,
        "Noble leading branch changed",
    )
    checkRecord(noble["conditions"][0], "Global", 9, [3, 0, 0, 0], strings=["GLOBALSarevokBehavior", ""])
    checkRecord(noble["actions"][0], "EscapeArea", 100, [0] * 5)
    for number, heard_id, trigger_offset, action_offsets in ((1, 2, 235, (309, 430)), (2, 50, 565, (633,))):
        block = listeners["SARRUN.BCS#block" + str(number)]
        require(
            len(block["conditions"]) == 1 and len(block["actions"]) == len(action_offsets),
            "Noble listener shape changed",
        )
        checkRecord(
            block["conditions"][0],
            "Heard",
            trigger_offset,
            [heard_id, 0, 0, 0],
            (0, {}, "Sarevok" if heard_id == 2 else ""),
        )
        for row, offset in zip(block["actions"], action_offsets):
            checkRecord(
                row, "Shout" if offset == 309 else "EscapeArea", offset, [50, 0, 0, 0, 0] if offset == 309 else [0] * 5
            )
    mutant = evidence["preemptionAndBehavior3Facts"]["SARDOPP"]
    leading = mutant["behavior3AllegianceBlock"]
    validateBlockOwnership(leading, "SARDOPP")
    require(
        all(row["sourceId"].startswith("SARDOPP.BCS#offset") for row in mutant["behavior3AttackConditions"]),
        "Source record ownership mismatch",
    )
    require(
        leading["sourceId"] == "SARDOPP.BCS#block0"
        and len(leading["conditions"]) == 2
        and len(leading["actions"]) == 1
        and len(mutant["behavior3AttackConditions"]) == 1,
        "Mutant behavior3 branch shape changed",
    )
    checkRecord(leading["conditions"][0], "Allegiance", 9, [255, 0, 0, 0], (0, {7: 1}, ""))
    checkRecord(leading["conditions"][1], "Global", 69, [3, 0, 0, 0], strings=["GLOBALSarevokBehavior", ""])
    checkRecord(leading["actions"][0], "ChangeEnemyAlly", 160, [28, 0, 0, 0, 0], (1, {7: 1}, ""))
    require(evidence["selectedIDS"]["EA"]["28"] == "GOODBUTRED", "EA28 identity changed")
    checkRecord(
        mutant["behavior3AttackConditions"][0], "Global", 296, [3, 0, 0, 0], strings=["GLOBALSarevokBehavior", ""]
    )
    responses = mutant["behavior3WeightedResponses"]
    require([row["weight"] for row in responses] == [15, 35, 25, 25], "Weighted response selection changed")
    for response, offset, target in zip(
        responses, (386, 515, 645, 778), (({0: 2}, ""), ({7: 1, 8: 12}, ""), ({}, "Liia"), ({}, "Belt"))
    ):
        require(len(response["actions"]) == 1, "Weighted response is not one alternative action")
        action = response["actions"][0]
        require(
            action["operation"] == "AttackReevaluate"
            and action["sourceOffset"] == offset
            and action["integers"] == [30, 0, 0, 0, 0],
            "Weighted attack arguments changed",
        )
        selector = action["selectors"][1]
        expected = [0] * 12
        for index, value in target[0].items():
            expected[index] = value
        require(selector == {"ids": expected, "name": target[1]}, "Weighted attack target changed")
    require(
        evidence["dynamicAIScriptClosure"]
        == [
            {
                "sourceId": "SAREVO.DLG#transition12",
                "field": "action",
                "operation": "ChangeAIScript",
                "argumentText": '"",OVERRIDE',
            }
        ],
        "Dynamic AI-script boundary changed",
    )
    require(
        evidence["dynamicAIScriptClosure"]
        == [row for dialogue in evidence["actorDialogues"].values() for row in dialogue["AIScriptMutations"]],
        "Dynamic AI-script dialogue summary mismatch",
    )
    for suffix in ("", "1", "2", "3", "4", "5"):
        noble_name = "NOBLPA" + suffix
        spell = "SPWI990" if not suffix else "SPWI96" + suffix
        target = "GDOPP7" + suffix
        number = 2990 if not suffix else 2960 + int(suffix)
        require(
            creatures[noble_name]["replacementSpellNumber"] == number
            and evidence["spellReplacements"][spell]
            == [{"featureIndex": 0, "opcode": 151, "mode": 0, "creature": target}],
            "Noble replacement script closure mismatch",
        )
    differences = {
        name: row for name, row in evidence["resourceFingerprints"].items() if not row["baseEqualsEffective"]
    }
    require(
        set(differences) == {"SAREVO.ITM"} and evidence["effectiveDifferencesOutsideScriptClosure"] == differences,
        "Effective override boundary mismatch",
    )
    derived = {
        "actorCreatureResources": len(creatures),
        "directActorBCS": len(direct - {"AR0108"}),
        "areaBCS": 1,
        "dialogueBCSBoundaries": len(scripts) - len(direct),
        "allBCSInventoried": len(scripts),
        "actorDialogues": len(evidence["actorDialogues"]),
        "selectedHeard2And50Blocks": len(listeners),
        "resourceFingerprints": len(evidence["resourceFingerprints"]),
    }
    require(evidence["closureCounts"] == derived == EXPECTED_COUNTS, "Logical closure counts mismatch")
    return True


def validateReview(payload, fixtures):
    require(type(payload) is bytes, "Expected original reviewed metadata bytes")
    require(hashlib.sha256(payload).hexdigest() == REVIEWED_EVIDENCE_SHA256, "Unreviewed palace closure metadata")
    evidence = json.loads(payload)
    validateLogicalEvidence(evidence)
    require(evidence["closureCounts"] == EXPECTED_COUNTS, "Unexpected closure counts")
    require(all(value is False for value in evidence["acceptance"].values()), "Acceptance must remain exactly false")
    require(set(fixtures) == set(evidence["fixtureCrossBindings"]), "Missing or extra source fixtures")
    for name, data in fixtures.items():
        pin = evidence["fixtureCrossBindings"][name]
        require(type(data) is bytes and len(data) == pin["bytes"], "Source fixture byte count mismatch: " + name)
        require(hashlib.sha256(data).hexdigest() == pin["sha256"], "Source fixture digest mismatch: " + name)
        fixture = json.loads(data)
        require(fixture["keySha256"] == evidence["keySha256"], "Source fixture KEY mismatch")
        require(
            len(fixture["resourceFingerprints"]) == pin["allPinnedResourcesVerified"], "Source fixture count mismatch"
        )
        for resource, resource_pin in fixture["resourceFingerprints"].items():
            actual = evidence["resourceFingerprints"][resource]
            require(
                actual["bytes"] == resource_pin["bytes"] and actual["sha256"] == resource_pin["sha256"],
                "Source fixture resource mismatch: " + resource,
            )
    return {
        "scope": evidence["scope"],
        "counts": dict(evidence["closureCounts"]),
        "candidateListenerSourceIds": sorted(evidence["selectedHeard2And50Blocks"]),
        "sourceGuardBehavior3Enemy": {
            name: evidence["preemptionAndBehavior3Facts"][name]["sourceId"] for name in ("FLAM10", "FLAM10A")
        },
        "sourceNobleBehavior3Escape": evidence["preemptionAndBehavior3Facts"]["SARRUN"]["sourceId"],
        "sourceDoppelgangerBehavior3Allegiance": 28,
        "scriptSchedulingResolved": False,
        "acceptance": dict(evidence["acceptance"]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument(
        "--evidence", type=Path, default=Path(__file__).resolve().parents[1] / "tests" / "fixtures" / REVIEWED_FILENAME
    )
    args = parser.parse_args(argv)
    folder = Path(__file__).resolve().parent
    fixtures = {
        name: (args.project_root / "tests" / "fixtures" / name).read_bytes()
        for name in ("baldurs_gate_palace_scene_audit.json", "baldurs_gate_city_palace_shout.json")
    }
    print(json.dumps(validateReview(args.evidence.read_bytes(), fixtures), indent=2))


if __name__ == "__main__":
    main()
