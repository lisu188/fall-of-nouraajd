"""Development-only palace scene audit; emits facts, never original dialogue or script dumps."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

try:
    from . import audit_candlekeep_source as source
    from .build_baldurs_gate_prison_source_fixture import expressionFacts
except ImportError:
    import audit_candlekeep_source as source
    from build_baldurs_gate_prison_source_fixture import expressionFacts


RESOURCES = {
    "ARE": ("AR0108",),
    "IDS": ("GTIMES",),
    "BCS": ("AR0108", "BELT", "LIIA", "SAREVOK", "SARDOPP", "ENDCUT01", "CUTBELT", "FLAM10", "FLAM10A"),
    "CRE": (
        "BELT",
        "LIIA",
        "SAREVO2",
        "SAREVO",
        "WINSKI",
        "GDOPP7",
        "GDOPP71",
        "GDOPP72",
        "GDOPP73",
        "GDOPP74",
        "GDOPP75",
    ),
    "DLG": ("BILL", "FLAM10", "BELT", "LIIA", "SAREVO", "FLAM7", "FLAM9", "NOBLPA1", "NOBLPA2", "NOBLPA3"),
    "SPL": ("SPWI990", "SPWI961", "SPWI962", "SPWI963", "SPWI964", "SPWI965"),
    "ITM": ("MISC78", "SCRL2K", "SCRL3F", "SAREVO", "MINHP1"),
}


def scriptObjects(record):
    """Retain selector numbers and script names, without copying a compiled record."""
    result = []
    for value in re.findall(r"OB\r?\n([^\r\n]+?)OB", record["raw"]):
        match = re.fullmatch(r'([\d -]+)\s+"([^"\r\n]*)"', value)
        if not match:
            raise ValueError("unsupported compiled object selector")
        numbers = [int(number) for number in match[1].split()]
        if len(numbers) != 12:
            raise ValueError("unsupported compiled object selector width")
        result.append({"ids": numbers, "name": match[2]})
    return result


def responseFacts(parsed):
    """Attach source response weights to actions; do not infer condition semantics."""
    text = parsed["compiled_text"]
    result = []
    for match in re.finditer(r"(?m)^RE\r?\n(\d+)AC\r?\n", text):
        end = re.search(r"(?m)^RE\r?$", text[match.end() :])
        if end is None:
            raise ValueError("unterminated script response")
        stop = match.end() + end.start()
        records = [r for r in parsed["records"] if r["kind"] == "AC" and match.start() <= r["offset"] < stop]
        result.append({"weight": int(match[1]), "records": records})
    return result


def spellReplacements(data):
    """Read only opcode 151 replacements from documented V1 spell feature tables."""
    if len(data) < 0x72 or data[:8] != b"SPL V1  ":
        raise ValueError("unsupported or truncated SPL V1 header")
    header_offset = struct.unpack_from("<I", data, 0x64)[0]
    header_count = struct.unpack_from("<H", data, 0x68)[0]
    effect_offset = struct.unpack_from("<I", data, 0x6A)[0]
    casting_index, casting_count = struct.unpack_from("<HH", data, 0x6E)
    if header_count > 1024 or header_offset > len(data) or header_offset + header_count * 40 > len(data):
        raise ValueError("SPL extended headers escape payload")
    indexes = set(range(casting_index, casting_index + casting_count))
    for index in range(header_count):
        count, start = struct.unpack_from("<HH", data, header_offset + index * 40 + 0x1E)
        indexes.update(range(start, start + count))
    if effect_offset > len(data) or any(effect_offset + (index + 1) * 48 > len(data) for index in indexes):
        raise ValueError("SPL feature blocks escape payload")
    result = []
    for index in sorted(indexes):
        offset = effect_offset + index * 48
        if struct.unpack_from("<H", data, offset)[0] != 151:
            continue
        resource = data[offset + 20 : offset + 28].split(b"\0", 1)[0].decode("ascii").upper()
        result.append(
            {
                "featureIndex": index,
                "opcode": 151,
                "mode": struct.unpack_from("<I", data, offset + 8)[0],
                "creature": resource,
            }
        )
    return result


def creatureMetadata(data):
    """Retain complete inventory records and raw V1 slots, without interpreting effects or treasure."""
    parsed = source.parseCreature(data)[0]
    reader = source.Binary(data)
    slots = reader.number(0x2B8)
    if not slots:
        raise source.AuditError("CRE item-slot table is absent; complete slot metadata is unavailable")
    result = {
        key: parsed[key]
        for key in (
            "death_variable",
            "hit_points",
            "kill_xp",
            "items",
            "gold",
            "known_spells",
            "memorized_spells",
            "effect_count",
            "effects_interpreted",
        )
    }
    result["sha256"] = source.sha256(data)
    result["itemSlots"] = [reader.number(offset, "H") for offset in reader.table(slots, 40, 2)]
    return result


def itemGates(dialogue):
    return sorted(
        {
            item.upper()
            for transition in dialogue["transitions"]
            for item in re.findall(r'PartyHasItem\("([A-Za-z0-9_]+)"\)', transition.get("trigger") or "", re.IGNORECASE)
        }
    )


def actionNames(dialogue):
    return sorted(
        {
            name
            for transition in dialogue["transitions"]
            for name in re.findall(r"([A-Za-z][A-Za-z0-9_]*)\s*\(", transition.get("action") or "")
        }
    )


MAX_OUTPUT_BYTES = 256 * 1024

TIME_SYMBOLS = ("ONE_MINUTE", "TWO_MINUTES", "THREE_MINUTES", "ONE_HOUR", "ONE_DAY", "TEN_DAYS")


def timeConstants(data):
    """Resolve selected named constants, rejecting aliases with contradictory values."""
    rows = re.findall(r"(?m)^\s*(0x[0-9a-fA-F]+|[0-9]+)\s+(\w+)\s*(?://.*)?$", data.decode("ascii"))
    result = {}
    for name in TIME_SYMBOLS:
        values = [int(value, 16 if value.lower().startswith("0x") else 10) for value, symbol in rows if symbol == name]
        if len(values) != 1:
            raise ValueError("Missing or ambiguous GTIMES symbol: " + name)
        result[name] = values[0]
    return result


def dialogueStateFact(resource, number, parsed):
    """Retain selected DLG topology and operation arguments, without dialogue prose."""
    if type(number) is not int or not 0 <= number < len(parsed["states"]):
        raise ValueError("Invalid dialogue state: " + resource)
    state = parsed["states"][number]
    first, count = state["first_transition"], state["transition_count"]
    if min(first, count) < 0 or first + count > len(parsed["transitions"]):
        raise ValueError("Dialogue edges escape state: " + resource)
    edges = []
    for index in range(first, first + count):
        edge = parsed["transitions"][index]
        edges.append(
            {
                "sourceId": resource + ".DLG#state" + str(number) + "/transition" + str(index),
                "index": index,
                "flags": edge.get("flags", 0),
                "replyStrref": edge.get("text_strref"),
                "journalStrref": edge.get("journal_strref"),
                "conditions": expressionFacts(edge.get("trigger")),
                "actions": expressionFacts(edge.get("action")),
                "target": {"dialogue": edge["next_dialogue"].upper(), "state": edge["next_state"]},
            }
        )
    return {
        "sourceId": resource + ".DLG#state" + str(number),
        "speaker": resource,
        "state": number,
        "entryConditions": expressionFacts(state.get("trigger")),
        "edges": edges,
    }


def ceremonyFacts(dialogues):
    """Follow the actual single-edge ceremony chain; an unknown branch cannot become a guessed continuation."""
    result, visited = [], set()
    resource, state = "BELT", 0
    while True:
        if (resource, state) in visited or resource not in dialogues or len(result) >= 64:
            raise ValueError("Cyclic, missing or unbounded ceremony speaker/state")
        visited.add((resource, state))
        row = dialogueStateFact(resource, state, dialogues[resource])
        if len(row["edges"]) != 1:
            raise ValueError("Ceremony contains an unaudited reply branch")
        result.append(row)
        if (resource, state) == ("SAREVO", 7):
            if row["edges"][0]["target"] != {"dialogue": "", "state": None}:
                raise ValueError("Transformation edge no longer terminates the ceremony")
            return result
        target = row["edges"][0]["target"]
        resource, state = target["dialogue"], target["state"]


def compiledBlockFacts(resource, number, parsed):
    """Retain selected condition/action records and their order, never compiled bodies."""
    markers = [m for m in re.finditer(r'"[^"\n]*"|(?P<block>CR)(?=\s|$)', parsed["compiled_text"]) if m.group("block")]
    if len(markers) % 2 or type(number) is not int or not 0 <= number < len(markers) // 2:
        raise ValueError("Invalid compiled condition/action block: " + resource)
    start, stop = markers[number * 2].start(), markers[number * 2 + 1].end()
    conditions, actions = [], []
    for record in parsed["records"]:
        if not start < record["offset"] < stop:
            continue
        if not record.get("signature"):
            raise ValueError("Unknown operation in selected scene block: " + resource)
        fact = {
            "sourceId": resource + ".BCS#offset" + str(record["offset"]),
            "operation": record["signature"].split("(")[0],
            "integers": list(record["integer_fields"]),
            "strings": list(record["strings"]),
            "selectors": scriptObjects(record),
        }
        if record["kind"] == "TR":
            if len(fact["integers"]) < 2:
                raise ValueError("Truncated condition in selected scene block")
            fact["negated"] = bool(fact["integers"][1] & 1)
            conditions.append(fact)
        elif record["kind"] == "AC":
            actions.append(fact)
        else:
            raise ValueError("Unknown record kind in selected scene block")
    return {
        "sourceId": resource + ".BCS#block" + str(number),
        "conditions": conditions,
        "actions": actions,
        "semanticsEvaluated": False,
    }


def selectedDialogueStates(dialogues, selection):
    return [
        dialogueStateFact(resource, state, dialogues[resource]) for resource, states in selection for state in states
    ]


def sceneFacts(scripts, dialogues, fingerprints):
    facts = {
        "ceremony": {"start": compiledBlockFacts("BELT", 1, scripts["BELT"]), "steps": ceremonyFacts(dialogues)},
        "spawn": compiledBlockFacts("AR0108", 2, scripts["AR0108"]),
        "postBattle": {
            "belt": compiledBlockFacts("BELT", 2, scripts["BELT"]),
            "liia": compiledBlockFacts("LIIA", 1, scripts["LIIA"]),
        },
        "proofTransitions": selectedDialogueStates(
            dialogues, (("BELT", (6, 7, 9, 10)), ("LIIA", (3, 4, 6, 7)), ("SAREVO", (9, 24, 25)))
        ),
        "extraction": {
            "confrontation": dialogueStateFact("SAREVO", 10, dialogues["SAREVO"]),
            "gate": compiledBlockFacts("AR0108", 5, scripts["AR0108"]),
            "dialogue": dialogueStateFact("SAREVO", 11, dialogues["SAREVO"]),
            "cutscene": compiledBlockFacts("ENDCUT01", 0, scripts["ENDCUT01"]),
        },
        "failureTransitions": {
            "bothDukesDead": dialogueStateFact("SAREVO", 8, dialogues["SAREVO"]),
            "areaFailure": compiledBlockFacts("AR0108", 0, scripts["AR0108"]),
            "timerExecutions": [compiledBlockFacts("AR0108", n, scripts["AR0108"]) for n in (3, 4)],
        },
    }
    resources = set()

    def collect(value):
        if isinstance(value, dict):
            if "sourceId" in value:
                resources.add(value["sourceId"].split("#", 1)[0])
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(facts)
    facts["sourceResources"] = {name: fingerprints[name]["sha256"] for name in sorted(resources)}
    return facts


def auditPalace(game_root):
    index = source.ResourceIndex(Path(game_root))
    actions = source.parseIds(index.read("ACTION", "IDS", "base")[0])
    triggers = source.parseIds(index.read("TRIGGER", "IDS", "base")[0])
    fingerprints = {}
    payloads = {}
    for extension, names in RESOURCES.items():
        for name in names:
            data, origin = index.read(name, extension, "base")
            payloads[name, extension] = data
            fingerprint = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "source": "baseArchive"}
            if (name, extension) in index.overrides:
                effective = index.read(name, extension, "effective")[0]
                fingerprint["overrideSha256"] = hashlib.sha256(effective).hexdigest()
                fingerprint["overrideDiffers"] = data != effective
            fingerprints[name + "." + extension] = fingerprint
    scripts = {name: source.parseScript(payloads[name, "BCS"], actions, triggers)[0] for name in RESOURCES["BCS"]}
    dialogues = {name: source.parseDialogue(payloads[name, "DLG"])[0] for name in RESOURCES["DLG"]}
    creatures = {name: source.parseCreature(payloads[name, "CRE"])[0] for name in RESOURCES["CRE"]}
    spawns = [
        {"recordOffset": r["offset"], "creature": r["strings"][0].upper(), "position": r["integer_fields"][1:3]}
        for r in scripts["AR0108"]["records"]
        if r["kind"] == "AC" and r["signature"].startswith("CreateCreature(")
    ]
    attacks = []
    for response in responseFacts(scripts["SARDOPP"]):
        for record in response["records"]:
            if record["signature"].startswith(("Attack(", "AttackReevaluate(")):
                objects = scriptObjects(record)
                attacks.append(
                    {
                        "recordOffset": record["offset"],
                        "weight": response["weight"],
                        "action": record["signature"].split("(")[0],
                        "target": objects[1],
                    }
                )
    escape_timer = []
    for n, transition in enumerate(dialogues["SAREVO"]["transitions"]):
        for timer, units in re.findall(
            r'SetGlobalTimer\("([^"\r\n]+)","GLOBAL",([A-Z_]+)\)', transition.get("action") or ""
        ):
            escape_timer.append({"transition": n, "timer": timer, "units": units})
    hp_checks = [
        {"resource": name + ".BCS", "recordOffset": r["offset"], "signature": r["signature"]}
        for name in ("AR0108", "SAREVOK")
        for r in scripts[name]["records"]
        if r["kind"] == "TR" and re.match(r"(?:HP|HPP|HitPoint)", r["signature"] or "", re.IGNORECASE)
    ]
    transformation = []
    for noble, spell in zip(("NOBLPA", "NOBLPA1", "NOBLPA2", "NOBLPA3", "NOBLPA4", "NOBLPA5"), RESOURCES["SPL"]):
        transformation.append(
            {"disguise": noble, "spell": spell, "replacements": spellReplacements(payloads[spell, "SPL"])}
        )
    return {
        "schemaVersion": 1,
        "scope": "AR0108 coronation and palace entrance/supporting guard branches",
        "sourceEdition": "Installed BG1EE base archives; overrides fingerprinted separately",
        "originalParityEstablished": False,
        "keySha256": index.key_hash,
        "sources": {
            "classicWalkthrough": "https://www.forgottenwars.com/bg1/ar0200b.htm",
            "mixedEditionWalkthrough": "https://www.gamebanshee.com/baldursgate/walkthrough/ducalpalace.php",
            "spellFormat": "https://gibberlings3.github.io/iesdp/file_formats/ie_formats/spl_v1.htm",
            "replacementOpcode": "https://gibberlings3.github.io/iesdp/opcodes/bgee.htm#op151",
        },
        "resourceFingerprints": fingerprints,
        "palaceSpawns": spawns,
        "creatureMetadata": {
            name: creatureMetadata(payloads[name, "CRE"]) for name in RESOURCES["CRE"] if name.startswith("GDOPP7")
        },
        "identities": {
            name: {
                "deathVariable": c["death_variable"],
                "hitPoints": c["hit_points"],
                "killXp": c["kill_xp"],
                "items": [item["item"] for item in c["items"]],
            }
            for name, c in creatures.items()
        },
        "invitationGates": {name: itemGates(dialogues[name]) for name in ("BILL", "FLAM10")},
        "evidenceGates": {name: itemGates(dialogues[name]) for name in ("BELT", "LIIA")},
        "dukeDialogueActionNames": {name: actionNames(dialogues[name]) for name in ("BELT", "LIIA")},
        "transformations": transformation,
        "doppelgangerAttackResponses": attacks,
        "sarevokTimers": escape_timer,
        "timerConstants": {"sourceId": "GTIMES.IDS", "values": timeConstants(payloads["GTIMES", "IDS"])},
        "sceneFacts": sceneFacts(scripts, dialogues, fingerprints),
        "hpTriggersInPalaceAndSarevokScripts": hp_checks,
        "limitations": [
            "Authenticated patched original BG1 bytes are unavailable; these facts do not establish classic parity.",
            "GameBanshee describes damage-triggered escape; audited EE records gate extraction on SarevokRun timer expiry and visibility, with no HP trigger in AR0108/SAREVOK.",
            "Beamdog-named ar0108bd_once and bd_belt_liia globals are present in installed base scripts/dialogues; original behavior requires separate corroboration.",
            "A replacement audit does not interpret other spell or creature effects, source AI execution, engine hardcoding, random treasure, or reward scaling.",
            "Resource hashes identify archive bytes, not proof of runtime or complete source parity.",
            "Ordered source actions do not prove engine queue timing: Belt dialogue is followed by four exit activations, while Liia has no such actions.",
            "GTIMES constants are source units; map/encounter clock conversion, queued waits and expiry ordering remain unimplemented and unverified.",
            "GDOPP7 through GDOPP75 retain RNDTRE05 as an unresolved item reference; random-treasure table expansion and resulting loot are not established.",
            "Opcode 151 mode-zero replacement targets are factual, but transfer or removal of the disguise's inventory, gold, spells and effects remains unestablished.",
        ],
    }


def encodeReport(report):
    encoded = json.dumps(report, indent=2) + "\n"
    if len(encoded.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ValueError("Palace factual report exceeds its bounded output limit")
    return encoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = auditPalace(args.game_root)
    encoded = encodeReport(result).encode("utf-8")
    with args.output.open("xb") as stream:
        stream.write(encoded)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "resources": len(result["resourceFingerprints"]),
                "originalParityEstablished": False,
            }
        )
    )


if __name__ == "__main__":
    main()
