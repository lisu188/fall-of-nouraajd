# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded development-only palace listener evidence; no runtime or parity acceptance."""

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

REVIEWED_EVIDENCE_SHA256 = "b05e19a9f339b7d6925bc7d1c1f313e8c8e21374cff4a178e95750aa654a029d"
MAX_OUTPUT_BYTES = 96 * 1024
ARE_SLOTS = ("override", "general", "class", "race", "default", "specific")
CRE_SLOTS = ("override", "class", "race", "general", "default")
CREATURES = ("FLAM10", "NOBW5", "NOBL12", "FLAME", "ANGELO", "SAREVO2")
HEARING_SELECTION = {"FLAM10": 2, "FLAM10A": 3, "SARRUN": 1}
FALSE_ACCEPTANCE = {
    "nativeImplementationReady": False,
    "nativeExecutionVerified": False,
    "originalParityEstablished": False,
    "originalAcceptanceReady": False,
    "ledgerCompletionCredit": False,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf8")
    return hashlib.sha256(encoded).hexdigest()


def scriptName(name):
    return name.upper() if name and name.upper() != "NONE" else ""


def sourceScripts(area_scripts, creature_scripts):
    """Keep slot identity: the ARE and CRE arrays have different physical orders."""
    require(len(area_scripts) == 6 and len(creature_scripts) == 5, "Unexpected source script-slot width")
    result = {}
    creature = dict(zip(CRE_SLOTS, creature_scripts))
    for slot, area in zip(ARE_SLOTS, area_scripts):
        selected = scriptName(area) if area else scriptName(creature.get(slot, ""))
        origin = "area" if area else "creature" if creature.get(slot) else "none"
        result[slot] = {"resource": selected, "origin": origin}
    return result


def blockCount(parsed):
    markers = [m for m in re.finditer(r'"[^"\n]*"|(?P<block>CR)(?=\s|$)', parsed["compiled_text"]) if m.group("block")]
    require(len(markers) % 2 == 0, "Unbalanced source script blocks")
    return len(markers) // 2


def buildEvidence(game_root, project_root, palace_audit):
    """Read only fixed palace resources and their actor-script references, never a city walk."""
    project = Path(project_root).resolve()
    sys.path.insert(0, str(project))
    try:
        from scripts import audit_candlekeep_source as source
        from scripts import audit_baldurs_gate_palace as palace
    finally:
        sys.path.pop(0)
    index = source.ResourceIndex(game_root)
    resources = {}

    def read(name, ext):
        key = name.upper() + "." + ext
        data, origin = index.read(name, ext, view="base")
        effective, effective_origin = index.read(name, ext, view="effective")
        resources[key] = {
            "bytes": len(data),
            "sha256": source.sha256(data),
            "baseOrigin": origin,
            "overridePresent": (name.upper(), ext) in index.overrides,
            "effectiveBytes": len(effective),
            "effectiveSha256": source.sha256(effective),
            "effectiveOrigin": effective_origin,
            "baseEqualsEffective": data == effective,
        }
        return data

    actions = source.parseIds(read("ACTION", "IDS"))
    triggers = source.parseIds(read("TRIGGER", "IDS"))
    area = source.parseArea(read("AR0108", "ARE"))[0]
    require(len(area["actors"]) == 11, "Unexpected palace original actor roster")
    creatures = {}
    for name in CREATURES:
        creature = source.parseCreature(read(name, "CRE"))[0]
        creatures[name] = {
            "deathVariable": creature["death_variable"],
            "allegiance": creature["allegiance"],
            "scripts": creature["scripts"],
        }
    scripts = sorted(
        {scriptName(n) for c in creatures.values() for n in c["scripts"]}
        | {scriptName(n) for a in area["actors"] for n in a["scripts"]}
    )
    hearing_inventory, selected_blocks = {}, {}
    for name in filter(None, scripts):
        parsed = source.parseScript(read(name, "BCS"), actions, triggers)[0]
        require(not parsed["warnings"], "Unknown script operation in " + name)
        blocks = [palace.compiledBlockFacts(name, number, parsed) for number in range(blockCount(parsed))]
        hearing_inventory[name] = {
            "blockCount": len(blocks),
            "recordCount": len(parsed["records"]),
            "operationCounts": dict(sorted(Counter(r["signature"].split("(")[0] for r in parsed["records"]).items())),
            "heardTriggers": [
                dict(blockSourceId=block["sourceId"], **row)
                for block in blocks
                for row in block["conditions"]
                if row["operation"] == "Heard"
            ],
        }
        if name in HEARING_SELECTION:
            selected_blocks[name] = blocks[HEARING_SELECTION[name]]
    dialogue = source.parseDialogue(read("SAREVO", "DLG"))[0]
    source_state = palace.dialogueStateFact("SAREVO", 8, dialogue)
    transition = source_state["edges"][0]
    require(transition["sourceId"] == "SAREVO.DLG#state8/transition9", "Failure transition changed")
    require(transition["actions"][16] == {"op": "Shout", "args": [2]}, "Failure Shout source action changed")
    actor_rows = []
    for number, actor in enumerate(area["actors"], 1):
        code = actor["creature"]
        require(code in ("FLAM10", "NOBW5", "NOBL12"), "Unexpected palace listener creature")
        slots = sourceScripts(actor["scripts"], creatures[code]["scripts"])
        listeners = [
            {"slot": slot, "script": row["resource"], "blockSourceId": selected_blocks[row["resource"]]["sourceId"]}
            for slot, row in slots.items()
            if row["resource"] in selected_blocks
        ]
        actor_rows.append(
            {
                "sourceId": "AR0108.ARE#actor" + str(number - 1),
                "areaActorIndex": number - 1,
                "proposedNativeId": "cityAr0108Actor" + str(number),
                "sourceCreature": code,
                "sourcePosition": actor["position"],
                "sourceFlags": actor["flags"],
                "sourceSchedule": actor["schedule"],
                "areaScripts": actor["scripts"],
                "selectedScriptsBySlot": slots,
                "shout2Listeners": listeners,
            }
        )
    missing_listeners = {}
    for code in ("FLAME", "ANGELO"):
        names = sorted({scriptName(n) for n in creatures[code]["scripts"]} - {""})
        missing_listeners[code] = {
            "referencedScripts": names,
            "matchingHeard2": [
                row for name in names for row in hearing_inventory[name]["heardTriggers"] if row["integers"][0] == 2
            ],
            "scope": "complete Heard trigger inventory of this base CRE's nonempty referenced scripts only",
        }
    pins = palace_audit["resourceFingerprints"]
    require(len(pins) == 43, "Original palace manifest must contain exactly43 resources")
    overlaps = sorted(set(pins).intersection(resources))
    for resource in overlaps:
        require(resources[resource]["sha256"] == pins[resource]["sha256"], "Palace pin differs: " + resource)
        require(resources[resource]["bytes"] == pins[resource]["bytes"], "Palace byte count differs: " + resource)
    require(index.key_hash == palace_audit["keySha256"], "Different source installation KEY")
    return {
        "schemaVersion": 1,
        "scope": "selectedPalaceShoutListeners",
        "sourceEdition": "BG1EE installed base archives; supporting evidence only",
        "sourceView": "base",
        "keySha256": index.key_hash,
        "palaceManifest": {"resourceCount": 43, "sha256": digest(pins), "overlapResources": overlaps},
        "resourceFingerprints": resources,
        "sourceShout": {
            "sourceId": transition["sourceId"] + "/action16",
            "sourceAction": transition["actions"][16],
            "sourceStateConditions": source_state["entryConditions"],
            "speakerCreature": "SAREVO2",
            "speakerDeathVariable": creatures["SAREVO2"]["deathVariable"],
        },
        "scriptSlotLayout": {
            "area": {slot: hex(0x50 + n * 8) for n, slot in enumerate(ARE_SLOTS)},
            "creature": {slot: hex(0x248 + n * 8) for n, slot in enumerate(CRE_SLOTS)},
            "mergePolicy": "nonempty area slot overrides the corresponding creature slot",
            "nativeScriptInterpreterImplemented": False,
        },
        "creatureScripts": creatures,
        "areaActors": actor_rows,
        "selectedListenerBlocks": selected_blocks,
        "scriptHearingInventory": hearing_inventory,
        "spawnedActorNonListeners": missing_listeners,
        "documentedRadiusEvidence": {
            "BG1": {
                "pixels": 448,
                "feet": 28,
                "url": "https://gibberlings3.github.io/iesdp/scripting/actions/bg1actions.htm#106",
            },
            "BGEE": {
                "visualRangeMultiplier": 1.5,
                "defaultPixels": 672,
                "defaultFeet": 42,
                "url": "https://gibberlings3.github.io/iesdp/scripting/actions/bgeeactions.htm#106",
            },
            "installedRadiusAudited": False,
            "nativeRadiusConversion": None,
        },
        "primaryFormatReferences": [
            "https://gibberlings3.github.io/iesdp/file_formats/ie_formats/are_v1.htm",
            "https://gibberlings3.github.io/iesdp/file_formats/ie_formats/cre_v1.htm",
            "https://github.com/gemrb/gemrb/blob/master/gemrb/plugins/AREImporter/AREImporter.cpp",
        ],
        "limitations": [
            "Patched original BG1 archives are not authenticated by installed EE data or GemRB.",
            "Script-slot selection is factual input, not proof of original engine scheduling or trigger precedence.",
            "Recipient distance, visibility and transient Heard event delivery are not implemented or audited at runtime.",
            "Shout50 listeners and effects, EscapeArea destinations, pursuit and bounded attack rounds remain pending.",
            "Names proposed for existing native actors are identifiers, not native identity or ownership proof.",
            "Source hashes bind reviewed records; they do not authenticate the game installation or prove binary semantics.",
        ],
        "acceptance": deepcopy(FALSE_ACCEPTANCE),
    }


def compileShoutContract(evidence, palace_audit):
    """Fail closed on changed facts, then return detached source obligations, not executable actions."""
    require(isinstance(evidence, dict), "Expected supplemental evidence object")
    require(digest(evidence) == REVIEWED_EVIDENCE_SHA256, "Unreviewed supplemental shout evidence")
    pins = palace_audit.get("resourceFingerprints", {})
    require(len(pins) == 43, "Original palace manifest changed")
    require(digest(pins) == evidence["palaceManifest"]["sha256"], "Original palace fingerprints changed")
    require(palace_audit.get("keySha256") == evidence["keySha256"], "Source KEY cross-binding mismatch")
    source_shout = evidence["sourceShout"]
    speaker = palace_audit.get("identities", {}).get(source_shout["speakerCreature"], {})
    require(
        speaker.get("deathVariable") == source_shout["speakerDeathVariable"], "Palace speaker cross-binding mismatch"
    )
    failure = palace_audit.get("sceneFacts", {}).get("failureTransitions", {}).get("bothDukesDead", {})
    edges = failure.get("edges", [])
    require(
        failure.get("sourceId") == "SAREVO.DLG#state8"
        and failure.get("entryConditions") == source_shout["sourceStateConditions"]
        and len(edges) == 1
        and edges[0].get("sourceId") == "SAREVO.DLG#state8/transition9"
        and len(edges[0].get("actions", [])) > 16
        and edges[0]["actions"][16] == source_shout["sourceAction"],
        "Palace failure summary cross-binding mismatch",
    )
    for resource in evidence["palaceManifest"]["overlapResources"]:
        fingerprint = evidence["resourceFingerprints"][resource]
        require(pins[resource]["sha256"] == fingerprint["sha256"], "Source fingerprint cross-binding mismatch")
        require(pins[resource]["bytes"] == fingerprint["bytes"], "Source byte count cross-binding mismatch")
    rows = []
    for actor in evidence["areaActors"]:
        expected = sourceScripts(actor["areaScripts"], evidence["creatureScripts"][actor["sourceCreature"]]["scripts"])
        require(expected == actor["selectedScriptsBySlot"], "Actor script-slot cross-binding mismatch")
        for listener in actor["shout2Listeners"]:
            block = evidence["selectedListenerBlocks"][listener["script"]]
            require(expected[listener["slot"]]["resource"] == listener["script"], "Wrong actor listener slot")
            require(block["sourceId"] == listener["blockSourceId"], "Wrong listener block")
            rows.append({"actor": deepcopy(actor), "listener": deepcopy(listener), "sourceBlock": deepcopy(block)})
    return {
        "sourceShout": deepcopy(evidence["sourceShout"]),
        "listenerObligations": rows,
        "spawnedActorNonListeners": deepcopy(evidence["spawnedActorNonListeners"]),
        "documentedRadiusEvidence": deepcopy(evidence["documentedRadiusEvidence"]),
        "acceptance": deepcopy(FALSE_ACCEPTANCE),
        "supplementalEvidenceSha256": digest(evidence),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", required=True)
    parser.add_argument("--project-root", required=True, help="Checkout containing existing development auditors")
    parser.add_argument("--palace-audit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    palace_audit = json.loads(Path(args.palace_audit).read_text(encoding="utf8"))
    evidence = buildEvidence(args.game_root, args.project_root, palace_audit)
    compileShoutContract(evidence, palace_audit)
    encoded = (json.dumps(evidence, sort_keys=True, indent=2) + "\n").encode("utf8")
    require(len(encoded) <= MAX_OUTPUT_BYTES, "Bounded shout evidence output exceeded its cap")
    output = Path(args.output)
    require(not output.exists(), "Refusing to overwrite existing evidence")
    with output.open("xb") as stream:
        stream.write(encoded)
    print(
        json.dumps(
            {"bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest(), "factsSha256": digest(evidence)}
        )
    )


if __name__ == "__main__":
    main()
