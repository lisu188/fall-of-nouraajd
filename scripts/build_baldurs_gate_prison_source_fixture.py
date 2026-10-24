#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Export bounded prison scene facts from BGEE base archives, never original dialogue or scripts.

This is development evidence, not an Infinity Engine emulator or proof of original BG1 parity.
"""

import argparse
import json
from pathlib import Path
import re

MAX_OUTPUT_BYTES = 256 * 1024

try:
    from . import audit_candlekeep_source as source
    from .build_baldurs_gate_source_fixture import compiledSpawnFacts
except ImportError:
    import audit_candlekeep_source as source
    from build_baldurs_gate_source_fixture import compiledSpawnFacts


DISTRICTS = ("AR0100", "AR0200", "AR0300", "AR0600", "AR0700", "AR0800", "AR1100", "AR1200", "AR1300")
DIALOGUES = {"FFHUNT": None, "FLAMC7": (6, 7, 8), "ANGELO": None, "NEB": None, "SHARTJ": (0, 1)}
SCENES = ("FFHUNT", "INITNEB", "CAPCUT01", "CAPCUT02", "CAPCUT03", "CAPCUT04", "CAPCUT05")
CREATURES = ("FFHUNT", "ANGELO", "NEB", "FLAME1", "FLAME2", "FLAME3", "FLAME4", "FLAM13", "GALDOR")
VERIFIED_SHA256 = {
    "FFHUNT.DLG": "303dbef89fae44e0169a70d804cb2bf76f32cdfc6eade9586af4869c521a3f8b",
    "FLAMC7.DLG": "6ab97d87d5ebfa0313d722eabb7b8fe25141564cd8e0a80c4ede611e39e25c15",
    "ANGELO.DLG": "3ba30f6c68d7b3aa05dac6480859239aeef5493b624852fe59acdc81ff35e5d8",
    "NEB.DLG": "761f314509e95d730dc9c26fe07e94ecf3398551137ff361341d8375c5e0c2aa",
    "SHARTJ.DLG": "96a8661391f5fbcd49bc13c70cde2571962b9caebbf0a8d2216cf12707d0f4e8",
    "CAPCUT01.BCS": "72b378c804e8d87eeae4ec0b2f78333c8f8024f4dbe8a5c674a5077c58f3b984",
    "CAPCUT02.BCS": "30fcdfbcc129217aa6456fc4e2ee22ab9d302e349c513136dedb858e744ff0af",
    "CAPCUT03.BCS": "926b069387e5932a322155dd42abf401939972047af82f52755544eeb1a69ca2",
    "CAPCUT04.BCS": "9e98eeb2621a947aa0dd560840034fc98bbaffd4887d12f5dfb68dedb06aef78",
    "CAPCUT05.BCS": "cdef9e33eaf0b91cafc4e30fa986d6da3f25ad1ee7cad21e1253c254145475e1",
    "AR0607.ARE": "47e8d03bae271ecc60878ae960e5f551239fb5e5ddf99fd1331bf043f64024d1",
}
MATERIAL_ACTIONS = {
    "SetGlobal",
    "AddJournalEntry",
    "EraseJournalEntry",
    "StartCutScene",
    "JumpToPoint",
    "MoveBetweenAreas",
    "DestroySelf",
    "Kill",
    "ApplyDamagePercent",
    "CreateCreature",
    "EscapeArea",
    "Enemy",
    "Shout",
    "AdvanceTime",
    "SetNumTimesTalkedTo",
    "SetDialog",
    "LeaveAreaLUA",
    "LeaveAreaLUAPanic",
    "CutSceneId",
    "MoveToPoint",
    "MoveToPointNoInterrupt",
    "ApplyDamage",
    "Dialogue",
    "StartDialogueNoSet",
    "StartDialogNoSet",
    "Delay",
}
COSMETIC_ACTIONS = {
    "ClearAllActions",
    "StartCutSceneMode",
    "EndCutSceneMode",
    "Wait",
    "SmallWait",
    "FadeToColor",
    "FadeFromColor",
    "MoveViewPoint",
    "Face",
    "FaceObject",
    "SetSequence",
    "MultiPlayerSync",
    "SetMasterArea",
    "DisplayStringWait",
    "DisplayStringHead",
}


def verifyFingerprint(identity, data, expected=VERIFIED_SHA256):
    fingerprint = source.sha256(data)
    if identity in expected and fingerprint != expected[identity]:
        raise source.AuditError(f"{identity} changed: review scene semantics before replacing the factual fixture")
    return fingerprint


def splitArguments(text):
    """Split call arguments without losing nested actions, object lists or quoted commas."""
    result, start, depth, quoted = [], 0, 0, False
    for index, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        elif not quoted:
            if char in "([":
                depth += 1
            elif char in ")]":
                depth -= 1
                if depth < 0:
                    raise source.AuditError("unbalanced scene expression")
            elif char == "," and depth == 0:
                result.append(text[start:index].strip())
                start = index + 1
    if quoted or depth:
        raise source.AuditError("unterminated scene expression")
    if text[start:].strip():
        result.append(text[start:].strip())
    return result


def expressionFact(text):
    text = text.strip()
    if text.startswith("!"):
        return {"not": expressionFact(text[1:])}
    match = re.fullmatch(r"(\w+)\((.*)\)", text, re.S)
    if match:
        return {"op": match[1], "args": [expressionFact(value) for value in splitArguments(match[2])]}
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r'"[^"\r\n]*"', text):
        return text[1:-1]
    if re.fullmatch(r"\[\w+(?:\.-?\d+)?\]|\w+", text):
        return {"symbol": text}
    raise source.AuditError("unsupported scene expression token")


def expressionFacts(text):
    return [expressionFact(line) for line in (text or "").splitlines() if line.strip()]


def materialFacts(text):
    result = []
    for fact in expressionFacts(text):
        if fact.get("op") == "ActionOverride":
            if len(fact["args"]) != 2 or not isinstance(fact["args"][1], dict):
                raise source.AuditError("malformed ActionOverride in prison scene")
            nested_op = fact["args"][1].get("op")
            if nested_op in MATERIAL_ACTIONS:
                result.append(fact)
            elif nested_op not in COSMETIC_ACTIONS:
                raise source.AuditError(f"unreviewed nested prison action {nested_op}")
        elif fact.get("op") in MATERIAL_ACTIONS:
            result.append(fact)
        elif fact.get("op") not in COSMETIC_ACTIONS:
            raise source.AuditError(f"unreviewed prison action {fact.get('op')}")
    return result


def dialogueFacts(name, parsed, selected=None, entry_weights=None):
    states = range(len(parsed["states"])) if selected is None else selected
    result = []
    for state_id in states:
        if not 0 <= state_id < len(parsed["states"]):
            raise source.AuditError("selected dialogue state outside table")
        state = parsed["states"][state_id]
        edges = []
        first, count = state["first_transition"], state["transition_count"]
        if first < 0 or count < 0 or first + count > len(parsed["transitions"]):
            raise source.AuditError("scene transition range outside table")
        for edge_id in range(first, first + count):
            edge = parsed["transitions"][edge_id]
            if edge["next_dialogue"] in ("", name) and edge["next_state"] is not None:
                if not 0 <= edge["next_state"] < len(parsed["states"]):
                    raise source.AuditError("scene dialogue target outside table")
            edges.append(
                {
                    "id": edge_id,
                    "replyStrref": edge["text_strref"],
                    "conditions": expressionFacts(edge["trigger"]),
                    "journalStrref": edge["journal_strref"],
                    "flags": edge["flags"],
                    "effects": materialFacts(edge["action"]),
                    "actionSha256": source.sha256((edge["action"] or "").encode()),
                    "next": None if edge["next_state"] is None else [edge["next_dialogue"] or name, edge["next_state"]],
                }
            )
        result.append(
            {
                "id": state_id,
                "strref": state["text_strref"],
                "conditions": expressionFacts(state["trigger"]),
                "entryWeight": None if entry_weights is None else entry_weights[state_id],
                "transitions": edges,
            }
        )
    return result


def objectFacts(raw):
    markers = [m for m in re.finditer(r'"[^\"]*"|(?P<marker>OB)(?=\s|$)', raw) if m.group("marker")]
    if len(markers) % 2:
        raise source.AuditError("unbalanced object selectors")
    result = []
    for start, end in zip(markers[::2], markers[1::2]):
        text = raw[start.end() : end.start()].strip()
        match = re.fullmatch(r'((?:-?\d+\s+){12})"([^\"]*)"', text)
        if not match:
            raise source.AuditError("unsupported compiled object selector")
        numbers = [int(number) for number in match[1].split()]
        selected = {"fields": [[i, value] for i, value in enumerate(numbers) if value]} if any(numbers) else {}
        if match[2]:
            selected["name"] = match[2]
        result.append(selected or None)
    return result if any(result) else []


def scriptFacts(parsed):
    result = []
    markers = [m for m in re.finditer(r'"[^\"]*"|(?P<marker>CR)(?=\s|$)', parsed["compiled_text"]) if m.group("marker")]
    if len(markers) % 2:
        raise source.AuditError("unbalanced scene blocks")
    blocks = list(zip(markers[::2], markers[1::2]))
    for record in parsed["records"]:
        op = (record.get("signature") or "").split("(", 1)[0]
        if not op:
            raise source.AuditError("unknown prison scene opcode")
        if record["kind"] == "AC" and op not in MATERIAL_ACTIONS:
            if op not in COSMETIC_ACTIONS:
                raise source.AuditError(f"unreviewed compiled prison action {op}")
            continue
        block = next((i for i, (start, end) in enumerate(blocks) if start.start() < record["offset"] < end.end()), None)
        if block is None:
            raise source.AuditError("scene record outside condition/response block")
        result.append(
            {
                "kind": record["kind"],
                "op": op,
                "integers": record["integer_fields"],
                "strings": record["strings"],
                "objects": objectFacts(record["raw"]),
                "offset": record["offset"],
                "block": block,
            }
        )
    return result


def patrolFacts(name, parsed):
    spawns = [fact for fact in compiledSpawnFacts(parsed) if fact["creature"] == "FFHUNT"]
    one_shot = f"Capture{int(name[2:])}"
    expected_conditions = [("GLOBALChapter", 7), ("GLOBAL" + one_shot, 0), ("GLOBALDukeThanks", 0)]
    if len(spawns) != 2 or spawns[0]["position"] != spawns[1]["position"]:
        raise source.AuditError(f"{name} patrol layout changed")
    for spawn in spawns:
        conditions = spawn["conditions"]
        if len(conditions) != 3 or spawn["block"] != spawns[0]["block"]:
            raise source.AuditError(f"{name} patrol block changed")
        for condition, (variable, value) in zip(conditions, expected_conditions):
            if not (
                (condition.get("signature") or "").startswith("Global(")
                and condition["strings"] == [variable, ""]
                and condition["integerFields"] == [value, 0, 0, 0]
            ):
                raise source.AuditError(f"{name} patrol condition changed")
    # The verified one-shot assignment immediately precedes both spawns in their response.
    records = parsed["records"]
    before_spawn = [record for record in records if record["offset"] < spawns[0]["recordOffset"]]
    assignment = before_spawn[-1] if before_spawn else {}
    if not (
        assignment.get("kind") == "AC"
        and (assignment.get("signature") or "").startswith("SetGlobal(")
        and assignment["strings"] == ["GLOBAL" + one_shot, ""]
        and assignment["integer_fields"] == [1, 0, 0, 0, 0]
    ):
        raise source.AuditError(f"{name} patrol one-shot assignment changed")
    return {
        "count": 2,
        "position": spawns[0]["position"],
        "conditions": spawns[0]["conditions"],
        "block": spawns[0]["block"],
        "spawnRecordOffsets": [fact["recordOffset"] for fact in spawns],
        "oneShotGlobal": one_shot,
        "oneShotValue": 1,
    }


def buildFixture(game_root, language="en_US"):
    if not re.fullmatch(r"[A-Za-z_]+", language):
        raise source.AuditError("language must be a language-directory identifier")
    index = source.ResourceIndex(game_root)
    fingerprints = {}

    def read(name, extension):
        identity = f"{name}.{extension}"
        data, origin = index.read(name, extension, "base")
        effective, effective_origin = index.read(name, extension, "effective")
        fingerprints[identity] = {
            "sha256": verifyFingerprint(identity, data),
            "size": len(data),
            "origin": origin,
            "effectiveDiffers": effective != data,
            "effectiveOrigin": effective_origin,
            "effectiveSha256": source.sha256(effective),
        }
        return data

    actions, triggers = (source.parseIds(read(name, "IDS")) for name in ("ACTION", "TRIGGER"))
    game_times = source.parseIds(read("GTIMES", "IDS"))
    table_path = source.safePath(index.root, f"lang/{language}/dialog.tlk")
    table = source.TalkTable(table_path)
    dialogues = {}
    for name, selected in DIALOGUES.items():
        data = read(name, "DLG")
        reader = source.Binary(data)
        entry_weights = [reader.number(offset + 12) for offset in reader.table(reader.number(12), reader.number(8), 16)]
        entry_weights = [None if weight == 0xFFFFFFFF else weight for weight in entry_weights]
        dialogues[name] = dialogueFacts(name, source.parseDialogue(data)[0], selected, entry_weights)
    scenes = {name: scriptFacts(source.parseScript(read(name, "BCS"), actions, triggers)[0]) for name in SCENES}
    patrols = {}
    for name in DISTRICTS:
        parsed = source.parseScript(read(name, "BCS"), actions, triggers)[0]
        patrols[name] = patrolFacts(name, parsed)
    creatures = {}
    for name in CREATURES:
        parsed = source.parseCreature(read(name, "CRE"))[0]
        creatures[name] = {
            key: parsed[key] for key in ("dialogue", "scripts", "death_variable", "items", "gold", "kill_xp")
        }
    area = source.parseArea(read("AR0607", "ARE"))[0]
    prison = {
        "actors": area["actors"],
        "doors": [
            {
                key: row[key]
                for key in ("name", "flags", "lock_difficulty", "key", "script", "dialogue", "travel_trigger")
            }
            for row in area["doors"]
        ],
        "travelRegions": [
            {key: row[key] for key in ("name", "destination", "entrance", "flags")}
            for row in area["regions"]
            if row["type"] == 2
        ],
        "cellDoorRegions": [
            {key: row[key] for key in ("name", "type", "text_strref", "flags", "script")}
            for row in area["regions"]
            if row["name"] == "CELLDOOR"
        ],
    }
    refs = {32176, 26841, 26842, 26843, 26844, 26845, 26846, 26847, 27317, 32175}
    for states in dialogues.values():
        for state in states:
            refs.add(state["strref"])
            for edge in state["transitions"]:
                refs.update(ref for ref in (edge["replyStrref"], edge["journalStrref"]) if ref is not None)
    strings = []
    for ref in sorted(refs):
        entry = table.get(ref)
        if not entry or entry.get("unresolved"):
            raise source.AuditError(f"unresolved prison TLK strref {ref}")
        strings.append({"strref": ref, "textSha256": source.sha256(entry["text"].encode("utf-8"))})
    if table.errors:
        raise source.AuditError("prison dialogue TLK contains decoding errors")
    return {
        "schemaVersion": 1,
        "edition": "Installed BGEE base archives; supporting evidence only",
        "originalParityVerified": False,
        "language": language,
        "keySha256": index.key_hash,
        "sourceFingerprints": fingerprints,
        "dialogues": dialogues,
        "scenes": scenes,
        "patrols": patrols,
        "gameTimeConstants": {str(value): game_times[value] for value in (300, 600, 7200)},
        "creatures": creatures,
        "prison": prison,
        "strings": strings,
        "textExported": False,
        "scriptTextExported": False,
        "interpretation": interpretationFacts(),
    }


def interpretationFacts():
    return {
        "sources": {
            "classicGuide": "https://www.forgottenwars.com/bg1/ar1100b.htm",
            "mixedEditionGuide": "https://www.gamebanshee.com/baldursgate/walkthrough/baldursgatechapter7.php",
            "dlgFormat": "https://gibberlings3.github.io/iesdp/file_formats/ie_formats/dlg_v1.htm",
            "automaticPriority": "https://weidu.org/WeiDU/README-WeiDU.html",
            "timeAction": "https://gibberlings3.github.io/iesdp/scripting/actions/bgeeactions.htm#353",
        },
        "arrest": {
            "dialogue": "FFHUNT",
            "initialState": 0,
            "surrenderState": 2,
            "surrenderEdge": 5,
            "conditions": {"Captured": 0, "timesTalkedTo": 0},
            "bribeDeductsGold": False,
            "repeatCapturedBehavior": "FFHUNT script makes a neutral patrol hostile when Captured=1",
            "plotCleanup": "DukeThanks=1 destroys patrols; this is not a combat kill",
        },
        "angelo": {
            "soloInsultState": 4,
            "twoToFiveAliveInsultState": 1,
            "sixAliveInsultState": 9,
            "automaticTransitionOrder": "highest transition index first",
            "sharteelPriorityEdges": [11, 14, 16, 26],
            "twoToFiveVictimPriority": ["Player6", "Player5", "Player4", "Player3", "Player2"],
            "victimCondition": "InParty(slot), except unconditional Player2 fallback; not a living-slot filter",
            "finalTempleCreature": "GALDOR",
            "custodyCreature": "ANGELO",
            "sixAliveRandomEdges": {
                "21": [5, 5, "Player2"],
                "22": [5, 4, "Player3"],
                "23": [5, 3, "Player4"],
                "24": [5, 2, "Player5"],
                "25": [5, 1, "Player6"],
            },
            "jailPlayer1": [1298, 216],
            "threatJournals": [26841],
            "sentenceJournals": [26842, 26841],
            "sharteelPath": [
                ["SHARTJ", 0],
                ["ANGELO", 5],
                ["SHARTJ", 1],
                ["ANGELO", 6],
                "CAPCUT05",
                ["ANGELO", 7],
                "CAPCUT04",
            ],
        },
        "custody": {
            "area": "AR0607",
            "hearingPlayer1": [951, 774],
            "hearingAdvanceTime": 600,
            "hearingAdvanceWorldMinutes": 120,
            "gameTimeConversion": "GTIMES.IDS maps600 to TWO_HOURS; native city clock conversion must be documented",
            "hearingPartyPositions": [[951, 774], [986, 794], [857, 734], [841, 702], [1089, 837], [1128, 804]],
            "jailPartyPositions": [[1298, 216], [1222, 304], [1134, 397], [1610, 375], [1519, 458], [1441, 544]],
            "equipmentConfiscatedByAuditedActions": False,
            "goldOrXpReward": 0,
            "cellDoor": "CELLDOOR is an information region, not a door actor; guide says the cell starts open",
            "ordinaryExitRegionsRemainInArea": True,
        },
        "neb": {
            "initialTalkStates": [0, 4, 5, 6, 11, 14],
            "correctAnswerEdges": {"33": 15, "mirror": 28, "tomorrow": 33},
            "wrongAnswerStates": [9, 12, 16],
            "refusalState": 10,
            "repeatedRiddleState": 14,
            "escapeEdges": [19, 31, 39, 41],
            "attackState": 17,
            "attackFlag": ["AR0607", "AttackNEB", 1],
            "normalEscapeJournal": 27317,
            "attackEscapeJournal": 32175,
            "erasedJournals": [26843, 26844, 26845, 26841, 26842, 26846],
            "escapeArea": "AR1100",
            "escapePlayer1": [1768, 635],
            "sharteelEscapePlayer1": [1511, 1407],
            "escapePartyPositions": [[1768, 635], [1732, 581], [1706, 530], [1721, 478], [1754, 533], [1789, 566]],
            "sharteelEscapePartyPositions": [
                [1511, 1407],
                [1559, 1396],
                [1608, 1385],
                [1542, 1435],
                [1593, 1423],
                [1641, 1411],
            ],
            "itemCreatedOrGranted": False,
            "goldOrXpReward": 0,
            "hostileHandling": "INITNEB reacts to AttackedBy([GOODCUTOFF],DEFAULT) while neutral, sets flag then starts dialogue",
        },
        "classicCorroboration": [
            "Classic guide describes Angelo execution and Shar-Teel release",
            "Both guides describe repeat Neb conversations and three correct answers",
            "Mixed-edition guide says later patrols attack and the cell door starts open",
        ],
        "acceptanceBlockers": [
            "No unmodded patched original BG1 resource fingerprints available",
            "Classic guard, cell, script and journal equivalence remains unverified",
            "AdvanceTime353 is documented EE-only, so custody two-hour advancement may differ from classic BG1",
            "Original-engine random trigger scheduling and victim distribution unverified",
            "Native clock and persistent follower-slot conversions require runtime acceptance",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--language", default="en_US")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z_]+", args.language):
        parser.error("language must be a language-directory identifier")
    result = buildFixture(args.game_root, args.language)
    encoded = (json.dumps(result, indent=2) + "\n").encode("utf-8")
    if len(encoded) > MAX_OUTPUT_BYTES:
        raise ValueError("Prison factual report exceeds its bounded output limit")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(encoded)
    print(
        f"Wrote {len(result['sourceFingerprints'])} source fingerprints and bounded prison scene facts to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
