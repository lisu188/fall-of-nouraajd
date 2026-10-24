#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare native city custody actors and authored text over the bounded factual source graph."""

from copy import deepcopy
import re

DISTRICTS = ("AR0100", "AR0200", "AR0300", "AR0600", "AR0700", "AR0800", "AR1100", "AR1200", "AR1300")
ANGELO_ID = "cityCustodyAngelo"
ESCORT_IDS = ["cityCustodyEscortFlame" + str(index) for index in range(1, 5)]
STATE_TEXT = {
    "FFHUNT": {
        0: "Stop. Angelo Dosan has ordered your arrest for murder. Come peacefully or his orders require us to fight.",
        1: "I distrust these charges too, but Angelo commands the Fist now. Friendship cannot release me from his orders.",
        2: "Come with us. You may state your defense before Angelo.",
        3: "Scar is dead. Angelo holds his command, and we must follow his orders. Surrender or defend yourselves.",
        4: "Keep your money. The Fist's duty cannot be bought. Will you surrender?",
        5: "Then we must carry out Angelo's sentence. Defend yourselves.",
    },
    "FLAMC7": {
        6: "Your escape is over. Put away your weapons and surrender.",
        7: "Eltan is gravely ill. Angelo Dosan commands us in his place.",
        8: "Commander Dosan, we have brought the people accused of the Iron Throne murders.",
    },
    "ANGELO": {
        0: "The accused have arrived. I am Commander Angelo Dosan, and I shall decide your guilt and punishment.",
        1: "You choose to insult me? Guards, make an example of one of their companions.",
        2: "You cannot offer enough to make me betray Sarevok. Your money changes nothing.",
        3: "Enough threats. Guards, put them in the cells.",
        4: "I find you guilty of the charges against you. You will be held here until you are hanged.",
        5: "Who interrupts these proceedings?",
        6: "I acknowledge no such relationship. Take them to the cells.",
        7: "Shar-Teel, I will not explain myself. Our past earns you this one escape. Leave quickly; the guards' deaths will be blamed on you.",
        8: "You caught them again. Carry out the sentence immediately.",
        9: "You choose to insult me? Guards, make an example of one of their companions.",
    },
    "SHARTJ": {
        0: "Angelo, what reason can you have for treating us this way?",
        1: "You know me. I am your daughter, Shar-Teel.",
    },
    "NEB": {
        0: "Out of your cell already? You are the prisoners wanted for murder. I am Neb, another guest of this jail.",
        1: "There is no need to snap at me. I was offering conversation.",
        2: "They imprisoned me for killing children from the streets. I take no shame in it.",
        3: "Eltan has fallen sick. Scar was murdered, so Angelo rules the Fist now. A busy week for the city.",
        4: "Growing tired of these cells?",
        5: "I know an exit you will never discover by searching. I concealed it well.",
        6: "My magic conceals the passage. Would you let another killer lead you to freedom?",
        7: "Solve this and I will show you the exit. My victims followed the sequence 1, 2, 4, 7, 12, 20. Which number comes next?",
        8: "Thirty-three is correct. My tunnel waits behind this wall. Follow me out.",
        9: "Thirty-three! That was the number. Come back when you can answer me.",
        10: "Then enjoy your prison. I can wait.",
        11: "Another puzzle: what returns your gaze and copies your moving lips, yet has neither sight nor voice of its own?",
        12: "An incorrect answer. Perhaps another puzzle will suit you better.",
        13: "A mirror. You have answered correctly, so I will lead you through my hidden tunnel.",
        14: "Try again: I have never arrived and cannot be seen. The wise prepare for me, though when we meet I no longer bear that name. What am I?",
        15: "Tomorrow is the answer. Follow me through the concealed passage.",
        16: "That answer will not free you. Try speaking to me again when you have thought about it.",
        17: "Enough! I am leaving. Use my concealed route and leave me alone.",
    },
}
REPLY_TEXT = {
    "FFHUNT": {
        0: "I will come peacefully and prove my innocence.",
        1: "I will not answer to Angelo. Scar should command you.",
        2: "Could a payment persuade you to leave us?",
        6: "I surrender. Let us answer the charges.",
        7: "I will fight, despite what that may do to our reputation.",
        8: "Very well. Take us to face the charges.",
        9: "Scar is your commander. We refuse Angelo's authority.",
    },
    "FLAMC7": {
        9: "We surrender. Bring us to Duke Eltan.",
        10: "We refuse to surrender.",
        11: "Then we withdraw our surrender.",
        12: "Take us to Angelo instead.",
    },
    "ANGELO": {
        0: "Eltan deserves the command. You are an unworthy pretender.",
        1: "Eltan deserves the command. You are an unworthy pretender.",
        2: "Eltan deserves the command. You are an unworthy pretender.",
        3: "We can pay more than Sarevok. Release us.",
        4: "You will regret this when we get our hands on you.",
        5: "Please release us. We would be grateful for your mercy.",
    },
    "SHARTJ": {},
    "NEB": {
        0: "Keep your name and your chatter to yourself.",
        1: "Tell us what is happening in the city.",
        2: "What crime brought you here?",
        4: "I will hear no more from a child killer.",
        5: "What has happened in Baldur's Gate?",
        9: "Help us escape. We have urgent work outside.",
        10: "I would rather remain a prisoner than owe you anything.",
        11: "Thirty-eight.",
        12: "Twenty-six.",
        13: "Eighteen.",
        14: "Forty-one.",
        15: "Thirty-three.",
        16: "Seventy-six.",
        17: "Thirty.",
        18: "Thirty-eight; may you face judgment for it.",
        22: "A potato.",
        23: "A mannequin.",
        24: "A squid.",
        25: "The wind.",
        26: "A doppelganger.",
        27: "A lover.",
        28: "A mirror.",
        29: "Time.",
        32: "Death.",
        33: "Tomorrow.",
        34: "Old age.",
        35: "Sleep.",
        36: "Night.",
        37: "Judgment.",
        38: "The ocean tide.",
    },
}


def patrolIds(area):
    return ["cityCustodyPatrol" + area.title() + suffix for suffix in ("One", "Two")]


def identity(source_id):
    return "city" + "".join(word[:1].upper() + word[1:].lower() for word in source_id.replace("#", " ").split())


def namedActorIds(audit):
    result = {"ANGELO": ANGELO_ID, **dict(zip(("FLAME1", "FLAME2", "FLAME3", "FLAME4"), ESCORT_IDS))}
    names = {"NEB": "NEB", "FLAM13": "DICKSMOK", "FERGUS": "Fergus", "CHIMP5": "Chimp5"}
    for index, actor in enumerate(audit["prison"]["actors"], 1):
        if actor["creature"] in names:
            result[names[actor["creature"]]] = identity("AR0607#actor" + str(index))
    if not set(names.values()) <= result.keys():
        raise ValueError("Prison named actor evidence is incomplete")
    return result


def sceneSpawn(audit, scene, creature):
    matches = [
        row for row in audit["scenes"][scene] if row["op"] == "CreateCreature" and row["strings"][0].upper() == creature
    ]
    if len(matches) != 1:
        raise ValueError("Ambiguous custody actor source: " + creature)
    row = matches[0]
    return row["integers"][1:3], f"{scene}.BCS#offset{row['offset']}"


def prepareCustodyActors(source, audit):
    """Add deferred actors to the generator's copied source, preserving original creature ownership."""
    additions = []
    for area in DISTRICTS:
        patrol = audit["patrols"][area]
        for native_id, offset in zip(patrolIds(area), patrol["spawnRecordOffsets"]):
            additions.append((area, native_id, "FFHUNT", patrol["position"], f"{area}.BCS#offset{offset}", "patrol"))
    for creature, native_id in [("ANGELO", ANGELO_ID), *zip(("FLAME1", "FLAME2", "FLAME3", "FLAME4"), ESCORT_IDS)]:
        point, fact = sceneSpawn(audit, "CAPCUT03" if creature == "ANGELO" else "CAPCUT01", creature)
        additions.append(("AR0607", native_id, creature, point, fact, "angelo" if creature == "ANGELO" else "escort"))
    all_ids = {actor.get("nativeId") for area in source["areas"].values() for actor in area["actors"]}
    neb_actors = [actor for actor in source["areas"]["AR0607"]["actors"] if actor["creature"] == "NEB"]
    if len(neb_actors) != 1:
        raise ValueError("Custody requires exactly one existing Neb actor")
    for area, native_id, creature, point, fact, role in additions:
        if area not in source["areas"] or creature not in source["creatures"]:
            raise ValueError("Custody source metadata is missing: " + area + "/" + creature)
        if native_id in all_ids:
            raise ValueError("Custody actor already exists: " + native_id)
        all_ids.add(native_id)
    for area, native_id, creature, point, fact, role in additions:
        policy = {"sourceId": fact, "phase": 7}
        if role != "patrol":
            policy["requiresFlag"] = "custodyHearing"
        source["areas"][area]["actors"].append(
            {
                "sourceId": fact,
                "nativeId": native_id,
                "name": creature,
                "displayName": (
                    "Angelo Dosan"
                    if creature == "ANGELO"
                    else "Flaming Fist patrol" if role == "patrol" else "Flaming Fist escort"
                ),
                "creature": creature,
                "creatureMetadata": creature,
                "position": list(point),
                "dialogue": "FLAMC7" if creature == "FLAME4" else "",
                "schedule": 0xFFFFFF,
                "scriptedPolicy": policy,
                "custodyRole": role,
                "patrolArea": area if role == "patrol" else "",
            }
        )
    neb_actors[0]["custodyRole"] = "neb"
    neb_actors[0]["patrolArea"] = ""
    return {"angelo": ANGELO_ID, "escorts": list(ESCORT_IDS), "neb": namedActorIds(audit)["NEB"]}


def authoredDialogues(audit):
    result = deepcopy(audit["dialogues"])
    for name, states in result.items():
        for state in states:
            state["text"] = STATE_TEXT[name][state["id"]]
            state["speaker"] = "SHARTEEL" if name == "SHARTJ" else name
            for edge in state["transitions"]:
                edge["reply"] = None if edge["replyStrref"] is None else REPLY_TEXT[name][edge["id"]]
                edge.pop("actionSha256", None)
    return result


def custodyDefinitions(audit, usablePosition):
    """Project audited source points; party landings reserve distinct walkable native cells."""
    interpreted = audit["interpretation"]
    actor_ids = {"angelo": ANGELO_ID, "escorts": list(ESCORT_IDS), "neb": namedActorIds(audit)["NEB"]}
    result = {
        "actorIds": actor_ids,
        "namedActors": namedActorIds(audit),
        "patrols": {},
        "dialogues": authoredDialogues(audit),
        "points": {},
        "sourceOriginalParityVerified": False,
        "editionCaveats": deepcopy(interpreted["acceptanceBlockers"]),
        "sourceIdentity": {"custodyAngelo": "ANGELO", "finaleAngelo": "GALDOR", "separateSourceInventories": True},
    }
    for area, patrol in audit["patrols"].items():
        result["patrols"][area] = {
            "actors": patrolIds(area),
            "sourcePosition": list(patrol["position"]),
            "conditions": deepcopy(patrol["conditions"]),
            "oneShotGlobal": patrol["oneShotGlobal"],
            "oneShotValue": patrol["oneShotValue"],
        }
    for key, area, source_key, group in [
        ("hearing", "AR0607", "hearingPartyPositions", "custody"),
        ("jail", "AR0607", "jailPartyPositions", "custody"),
        ("escape", "AR1100", "escapePartyPositions", "neb"),
        ("release", "AR1100", "sharteelEscapePartyPositions", "neb"),
    ]:
        points = interpreted[group][source_key]
        if len(points) != 6:
            raise ValueError("Custody party transfer requires all six audited source slots")
        result[key] = {
            "area": area,
            "partyPositions": [list(usablePosition(area, point, reserve=True)) for point in points],
            "sourcePartyPositions": deepcopy(points),
        }
    result["hearing"]["advanceMinutes"] = interpreted["custody"]["hearingAdvanceWorldMinutes"]

    def addPoint(symbol):
        match = re.fullmatch(r"\[(-?\d+)\.(-?\d+)\]", symbol)
        if match:
            point = [int(match[1]), int(match[2])]
            result["points"][symbol] = list(usablePosition("AR0607", point))

    def walk(value):
        if isinstance(value, dict):
            if value.get("op") in {"JumpToPoint", "MoveToPoint", "MoveToPointNoInterrupt"}:
                argument = value["args"][0]
                if isinstance(argument, dict) and "symbol" in argument:
                    addPoint(argument["symbol"])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(result["dialogues"])
    for scene in ("CAPCUT03", "CAPCUT05"):
        for row in audit["scenes"][scene]:
            if row["op"] in {"JumpToPoint", "MoveToPoint", "MoveToPointNoInterrupt"}:
                addPoint(f"[{row['integers'][1]}.{row['integers'][2]}]")
    # The party's stage landing is authoritative when the projected native grid would merge source points.
    for source_point, native_point in zip(
        interpreted["custody"]["jailPartyPositions"], result["jail"]["partyPositions"]
    ):
        result["points"][f"[{source_point[0]}.{source_point[1]}]"] = list(native_point)
    return result
