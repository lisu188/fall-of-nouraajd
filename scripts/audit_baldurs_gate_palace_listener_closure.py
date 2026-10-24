# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded palace source-reference audit; stdlib only, no game or ledger execution."""

from collections import Counter
from contextlib import contextmanager
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
import types
import uuid

REVIEWED_FILENAME = "baldurs_gate_city_palace_listener_closure.json"
MAX_OUTPUT_BYTES = 192 * 1024
SOURCE_HELPERS = (
    "audit_candlekeep_source",
    "audit_baldurs_gate_palace",
    "audit_baldurs_gate_palace_shout",
    "build_baldurs_gate_prison_source_fixture",
    "build_baldurs_gate_source_fixture",
)
SOURCE_HELPER_POLICY = "CRLF-to-LF bytes; all other bytes preserved"
RESOURCE_ORIGIN_POLICY = "Backslash separators in relative source-origin metadata"
FIXTURE_PINS = {
    "baldurs_gate_city_palace_shout.json": (
        51952,
        "f400d2acc70a761df9415ab96422305a41ff336e02aa4fc6a6362b259062c3ef",
        22,
    ),
    "baldurs_gate_palace_scene_audit.json": (
        180717,
        "91d9ddfb7dd7760a6d874f306ce4de09ff653cb72c5fa1b3721cc5b5b36d6207",
        43,
    ),
}

CREATURES = (
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
)
CUTSCENES = ("CUTBELT", "ENDCUT01", "CAPCUT04", "CAPCUT05")
TRANSFORMATIONS = ("SPWI990", "SPWI961", "SPWI962", "SPWI963", "SPWI964", "SPWI965")
MUTATORS = {"ChangeAIScript", "SetAIScript", "SetAreaScript"}
PREEMPTION_CONTEXT = {"SHOUT", "SEEENEMY", "RUNENEMY", "WDASIGHT", "WDRUNSGT", "WTRUNSGT", "WTASIGHT"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sourceTextFingerprint(data):
    canonical = data.replace(b"\r\n", b"\n")
    return {"bytes": len(canonical), "sha256": digest(canonical)}


def canonicalOrigin(origin):
    result = dict(origin)
    if "path" in result:
        result["path"] = result["path"].replace("/", "\\")
    return result


@contextmanager
def loadSourceHelpers(project_root):
    """Fresh private package; imports definitions only and never invokes generator entrypoints."""
    folder = Path(project_root).resolve() / "scripts"
    prefix = "_palaceListenerAuditSources_" + uuid.uuid4().hex
    package = types.ModuleType(prefix)
    package.__path__ = [str(folder)]
    previous_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.modules[prefix] = package
    try:
        modules = {name: importlib.import_module(prefix + "." + name) for name in SOURCE_HELPERS}
        for module in modules.values():
            require(Path(module.__file__).resolve().parent == folder, "Source helper escaped project scripts")
        yield modules
    finally:
        for name in list(sys.modules):
            if name == prefix or name.startswith(prefix + "."):
                del sys.modules[name]
        sys.dont_write_bytecode = previous_bytecode


def buildEvidence(game_root, project_root):
    """Return metadata for fixed palace refs; never writes, traverses areas or imports the game."""
    with loadSourceHelpers(project_root) as modules:
        return buildWithHelpers(game_root, project_root, modules)


def buildWithHelpers(game_root, project_root, modules):
    project = Path(project_root).resolve()
    source = modules["audit_candlekeep_source"]
    palace = modules["audit_baldurs_gate_palace"]
    shout = modules["audit_baldurs_gate_palace_shout"]
    index = source.ResourceIndex(Path(game_root).resolve())
    fingerprints = {}

    def read(name, ext):
        key = name.upper() + "." + ext
        base, base_origin = index.read(name, ext, view="base")
        effective, effective_origin = index.read(name, ext, view="effective")
        fingerprints[key] = {
            "bytes": len(base),
            "sha256": digest(base),
            "baseOrigin": canonicalOrigin(base_origin),
            "effectiveBytes": len(effective),
            "effectiveSha256": digest(effective),
            "effectiveOrigin": canonicalOrigin(effective_origin),
            "overridePresent": (name.upper(), ext) in index.overrides,
            "baseEqualsEffective": base == effective,
        }
        return effective

    actions = source.parseIds(read("ACTION", "IDS"))
    triggers = source.parseIds(read("TRIGGER", "IDS"))
    ea_ids = source.parseIds(read("EA", "IDS"))
    object_ids = source.parseIds(read("OBJECT", "IDS"))
    fixtures = {}
    for filename, (expected_bytes, expected_sha, count) in FIXTURE_PINS.items():
        path = project / "tests" / "fixtures" / filename
        payload = path.read_bytes()
        require(
            len(payload) == expected_bytes and digest(payload) == expected_sha, "Unreviewed source fixture: " + filename
        )
        fixture = json.loads(payload)
        require(len(fixture["resourceFingerprints"]) == count, "fixture resource count changed: " + filename)
        require(fixture["keySha256"] == index.key_hash, "fixture KEY mismatch: " + filename)
        for key, pinned in fixture["resourceFingerprints"].items():
            name, ext = key.rsplit(".", 1)
            read(name, ext)
            require(fingerprints[key]["sha256"] == pinned["sha256"], "fixture digest mismatch: " + key)
            require(fingerprints[key]["bytes"] == pinned["bytes"], "fixture byte count mismatch: " + key)
        fixtures[filename] = {"bytes": len(payload), "sha256": digest(payload), "allPinnedResourcesVerified": count}

    area = source.parseArea(read("AR0108", "ARE"))[0]
    require(len(area["actors"]) == 11, "actor roster changed")
    creatures = {}
    for name in CREATURES:
        data = read(name, "CRE")
        parsed = source.parseCreature(data)[0]
        reader = source.Binary(data)
        effect_size = 0x30 if reader.number(0x33, "B") == 0 else 0x108
        opcodes = Counter(
            reader.number(offset, "H" if effect_size == 0x30 else "I")
            for offset in reader.table(reader.number(0x2C4), reader.number(0x2C8), effect_size)
        )
        creatures[name] = {
            "deathVariable": parsed["death_variable"],
            "allegiance": parsed["allegiance"],
            "scripts": dict(zip(shout.CRE_SLOTS, parsed["scripts"])),
            "dialogue": parsed["dialogue"],
            "intrinsicEffectOpcodeCounts": dict(sorted(opcodes.items())),
            "intrinsicOpcode82Count": opcodes[82],
        }

    area_actors = []
    for number, actor in enumerate(area["actors"]):
        require("embedded_creature" not in actor, "embedded creature requires a separate audit")
        selected = shout.sourceScripts(actor["scripts"], list(creatures[actor["creature"]]["scripts"].values()))
        area_actors.append(
            {
                "sourceId": "AR0108.ARE#actor" + str(number),
                "creature": actor["creature"],
                "position": actor["position"],
                "areaScripts": dict(zip(shout.ARE_SLOTS, actor["scripts"])),
                "selectedScriptsBySlot": selected,
            }
        )
    direct_scripts = (
        {area["script"]}
        | {shout.scriptName(name) for creature in creatures.values() for name in creature["scripts"].values()}
        | {row["resource"] for actor in area_actors for row in actor["selectedScriptsBySlot"].values()}
    )
    direct_scripts.discard("")
    require(len(direct_scripts) == 23, "direct script closure changed")
    dialogue_names = {shout.scriptName(creature["dialogue"]) for creature in creatures.values()} - {""}
    require(len(dialogue_names) == 10, "actor dialogue references changed")

    def recordFact(record):
        return {
            "sourceOffset": record["offset"],
            "operation": record["signature"].split("(")[0],
            "integers": record["integer_fields"],
            "strings": record["strings"],
            "selectors": palace.scriptObjects(record),
        }

    def blocks(parsed, name):
        return [palace.compiledBlockFacts(name, n, parsed) for n in range(shout.blockCount(parsed))]

    def compactFact(row):
        """Sparse selector metadata; absent array cells are zero, absent strings empty."""
        result = {"sourceOffset": int(row["sourceId"].rsplit("offset", 1)[1]), "operation": row["operation"]}
        if any(row["integers"]):
            result["integers"] = row["integers"]
        if any(row["strings"]):
            result["strings"] = row["strings"]
        objects = {}
        for number, selector in enumerate(row["selectors"]):
            value = {str(n): item for n, item in enumerate(selector["ids"]) if item}
            if selector["name"]:
                value["name"] = selector["name"]
            if value:
                objects[str(number)] = value
        if objects:
            result["objects"] = objects
        if row.get("negated"):
            result["negated"] = True
        return result

    scripts, listener_blocks, preemption, dynamic, crossguards = {}, {}, {}, [], {}
    for name in sorted(direct_scripts | set(CUTSCENES)):
        parsed, refs, _ = source.parseScript(read(name, "BCS"), actions, triggers)
        require(not parsed["warnings"], "unknown source operation: " + name)
        selected_blocks = blocks(parsed, name)
        script_refs = [row for row in refs if row and row["type"] == "BCS"]
        require(not script_refs, "unfollowed BCS reference: " + name)
        scripts[name] = {
            "blockCount": len(selected_blocks),
            "recordCount": len(parsed["records"]),
            "role": "directActorOrArea" if name in direct_scripts else "actorDialogueCutsceneBoundary",
            "operationCounts": dict(
                sorted(Counter(row["signature"].split("(")[0] for row in parsed["records"]).items())
            ),
            "heard": [
                {"blockSourceId": b["sourceId"], **row}
                for b in selected_blocks
                for row in b["conditions"]
                if row["operation"] == "Heard"
            ],
            "shout": [recordFact(row) for row in parsed["records"] if row["signature"].startswith("Shout(")],
            "BCSReferences": script_refs,
            "areaDepartureResources": sorted({row["name"] for row in refs if row and row["type"] == "ARE"}),
        }
        for block in selected_blocks:
            if any(row["operation"] == "Heard" and row["integers"][0] in (2, 50) for row in block["conditions"]):
                listener_blocks[block["sourceId"]] = block
            for row in block["actions"]:
                if row["operation"] in MUTATORS:
                    dynamic.append({"blockSourceId": block["sourceId"], **row})
        if name in ("FLAM10", "FLAM10A", "SARRUN"):
            preemption[name] = selected_blocks[0]
        if name in PREEMPTION_CONTEXT:
            crossguards[name] = [
                {
                    "sourceId": block["sourceId"],
                    "conditions": [compactFact(row) for row in block["conditions"]],
                    "actions": [compactFact(row) for row in block["actions"]],
                }
                for block in selected_blocks
            ]
        if name == "SARDOPP":
            preemption[name] = {
                "behavior3AllegianceBlock": selected_blocks[0],
                "behavior3AttackConditions": selected_blocks[1]["conditions"],
                "behavior3WeightedResponses": [
                    {"weight": row["weight"], "actions": [recordFact(record) for record in row["records"]]}
                    for row in palace.responseFacts(parsed)
                    if row["records"] and 386 <= row["records"][0]["offset"] <= 778
                ],
            }

    dialogues = {}
    for name in sorted(dialogue_names):
        parsed = source.parseDialogue(read(name, "DLG"))[0]
        script_refs, mutators, cutscenes = [], [], []
        for kind, rows in (("state", parsed["states"]), ("transition", parsed["transitions"])):
            for number, row in enumerate(rows):
                for field in ("trigger", "action"):
                    text = row.get(field) or ""
                    script_refs.extend(
                        r for r in source.textReferences(text, actions, triggers) if r and r["type"] == "BCS"
                    )
                    for match in re.finditer(
                        r"\b(ChangeAIScript|SetAIScript|SetAreaScript|StartCutSceneEx|StartCutScene)\(([^\n]*)\)",
                        text,
                        re.I,
                    ):
                        fact = {
                            "sourceId": name + ".DLG#" + kind + str(number),
                            "field": field,
                            "operation": match[1],
                            "argumentText": match[2],
                        }
                        (mutators if match[1] in MUTATORS else cutscenes).append(fact)
        require({row["name"] for row in script_refs} <= set(CUTSCENES), "unfollowed dialogue BCS reference: " + name)
        dialogues[name] = {
            "stateCount": len(parsed["states"]),
            "transitionCount": len(parsed["transitions"]),
            "BCSReferences": script_refs,
            "AIScriptMutations": mutators,
            "cutsceneReferences": cutscenes,
        }
        dynamic.extend(mutators)

    transforms = {name: palace.spellReplacements(read(name, "SPL")) for name in TRANSFORMATIONS}
    for name, rows in transforms.items():
        require(len(rows) == 1 and rows[0]["creature"] in CREATURES, "unfollowed replacement: " + name)
    for name in ("NOBLPA", "NOBLPA1", "NOBLPA2", "NOBLPA3", "NOBLPA4", "NOBLPA5"):
        parsed = source.parseScript(read(name, "BCS"), actions, triggers)[0]
        spells = [row["integer_fields"][0] for row in parsed["records"] if row["signature"].startswith("ForceSpell(")]
        require(len(spells) == 1, "unexpected noble transformation count")
        creatures[name]["replacementSpellNumber"] = spells[0]

    require(len(dynamic) == 1 and dynamic[0]["sourceId"] == "SAREVO.DLG#transition12", "dynamic closure changed")
    require(all(row["intrinsicOpcode82Count"] == 0 for row in creatures.values()), "intrinsic AI-script effect exists")
    require(
        set(listener_blocks) == {"FLAM10.BCS#block2", "FLAM10A.BCS#block3", "SARRUN.BCS#block1", "SARRUN.BCS#block2"},
        "listener closure changed",
    )
    require(
        all(row["baseEqualsEffective"] for key, row in fingerprints.items() if not key.endswith(".ITM")),
        "effective script-closure overrides require separate analysis",
    )
    effective_differences = {key: row for key, row in fingerprints.items() if not row["baseEqualsEffective"]}
    result = {
        "schemaVersion": 2,
        "scope": "boundedAR0108ActorScriptReferenceClosure",
        "sourceEdition": "BG1EE installed data; supporting evidence for original BG1 only",
        "sourceView": "base and effective compared",
        "keySha256": index.key_hash,
        "fixtureCrossBindings": fixtures,
        "resourceFingerprints": dict(sorted(fingerprints.items())),
        "effectiveDifferencesOutsideScriptClosure": effective_differences,
        "sourceHelperFingerprintPolicy": SOURCE_HELPER_POLICY,
        "resourceOriginPathPolicy": RESOURCE_ORIGIN_POLICY,
        "sourceHelpers": {
            name + ".py": sourceTextFingerprint((project / "scripts" / (name + ".py")).read_bytes())
            for name in SOURCE_HELPERS
        },
        "areaActors": area_actors,
        "creatures": creatures,
        "scripts": scripts,
        "actorDialogues": dialogues,
        "dynamicAIScriptClosure": dynamic,
        "spellReplacements": transforms,
        "selectedHeard2And50Blocks": listener_blocks,
        "preemptionAndBehavior3Facts": preemption,
        "higherAndFallbackScriptCrossguards": {
            "format": "12-cell selectors represented sparsely; absent cells zero; absent strings empty",
            "blocks": crossguards,
        },
        "selectedIDS": {
            "EA": {str(n): ea_ids.get(n) for n in (2, 28, 29, 30, 128, 200, 255)},
            "OBJECT": {str(n): object_ids.get(n) for n in (1, 12, 20)},
        },
        "closureCounts": {
            "actorCreatureResources": len(creatures),
            "directActorBCS": 22,
            "areaBCS": 1,
            "dialogueBCSBoundaries": 4,
            "allBCSInventoried": len(scripts),
            "actorDialogues": len(dialogues),
            "selectedHeard2And50Blocks": len(listener_blocks),
            "resourceFingerprints": len(fingerprints),
        },
        "unresolvedBoundaries": [
            "Original patched BG1 resources and original engine scheduling are not authenticated by EE archives.",
            "The retained 43-base manifest includes SAREVO.ITM whose installed effective override differs; item/effect behavior is outside this script-reference closure.",
            "Syntactic closure is complete for ARE/CRE script refs, audited script references, ten CRE-dialogue script refs, six selected replacement spells and direct CRE effect82 absence; it is not a general effect/spell/equipment or every-dialogue-target closure.",
            "Script-slot execution priority, queued action preemption, event expiry/retention, Continue, response selection and inter-actor ordering need engine evidence.",
            "Higher SHOUT override scripts can execute status/attack/Heard99 branches before class/specific listeners; actual state must be evaluated.",
            "No guarantee that behavior3 guards reach Heard2 before independent Enemy, or that SARRUN reaches Heard2 before Global3 EscapeArea.",
            "Retired noble ownership and replacement liveness, all actor death/corpse states, distances, EscapeArea path/destination and task-native conversion remain unverified.",
            "Cutscene boundary scripts were checked for Heard and AI-script refs, but out-of-area ARE resources and unrelated dialogue target chains were not followed.",
            "NearestEnemyOf cannot be reduced to Player1; living SARDOPP actors can change to GOODBUTRED28 before target resolution.",
        ],
        "acceptance": {
            "nativeImplementationReady": False,
            "nativeExecutionVerified": False,
            "originalParityEstablished": False,
            "originalAcceptanceReady": False,
            "ledgerCompletionCredit": False,
        },
    }
    return result


def evidenceBytes(evidence):
    payload = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf8")
    require(len(payload) < MAX_OUTPUT_BYTES, "bounded metadata output exceeded limit")
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument(
        "--reviewed-evidence",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tests" / "fixtures" / REVIEWED_FILENAME,
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = buildEvidence(args.game_root, args.project_root)
    payload = evidenceBytes(result)
    reviewed_path = args.reviewed_evidence
    matches = reviewed_path.exists() and payload == reviewed_path.read_bytes()
    require(matches, "Fresh bounded source metadata differs from reviewed evidence")
    if args.output:
        require(not args.output.exists(), "Refusing to overwrite existing evidence")
        with args.output.open("xb") as stream:
            stream.write(payload)
    print(
        json.dumps(
            {
                "bytes": len(payload),
                "sha256": digest(payload),
                "counts": result["closureCounts"],
                "matchesReviewedBytes": matches,
                "output": str(args.output) if args.output else None,
                "allAcceptanceFalse": not any(result["acceptance"].values()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
