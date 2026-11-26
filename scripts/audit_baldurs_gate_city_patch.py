#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare the city resources available in the international BG1 1.1.4315 patch and installed EE base."""

import argparse
import json
import re
from pathlib import Path

if __package__:
    from . import audit_candlekeep_source as reader
else:
    import audit_candlekeep_source as reader


ROOT = Path(__file__).resolve().parents[1]
CITY_SOURCE = ROOT / "tests/fixtures/baldurs_gate_city_source.json"
PATCH_SHA256 = "42d66f2e273e7c7c34a25616787e322158c87d48c0f012e179e3b51cb4cd2cfa"
# SHA-256 of sorted compact JSON mapping the 45 city member names to their payload hashes.
CITY_MEMBERS_SHA256 = "7e7ef9021b9adf1d9e861a17d1a3f306bab6f20da4dc78a8fee1cca906860e1d"
TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[a-zA-Z0-9_]+|[^\s"]')
PARSERS = {"ARE": reader.parseArea, "CRE": reader.parseCreature, "ITM": reader.parseItem}
AREA_FIELDS = {
    "actors": ("name", "creature", "position", "schedule", "flags", "dialogue", "scripts"),
    "containers": ("name", "position", "lock_difficulty"),
    "doors": ("name", "travel_trigger"),
}


def scriptTokens(script):
    if script is None:
        return None
    tokens = []
    position = 0
    for match in TOKEN.finditer(script):
        if script[position : match.start()].strip():
            raise reader.AuditError("unsupported or unterminated quoted DLG operand")
        tokens.append(match.group())
        position = match.end()
    if script[position:].strip():
        raise reader.AuditError("unsupported or unterminated quoted DLG operand")
    return tokens


def stateRecord(dialogue, index):
    state = dialogue["states"][index]
    first = state["first_transition"]
    choices = []
    for edge in dialogue["transitions"][first : first + state["transition_count"]]:
        choices.append(dict(edge, trigger=scriptTokens(edge["trigger"]), action=scriptTokens(edge["action"])))
    return {
        "text_strref": state["text_strref"],
        "trigger": scriptTokens(state["trigger"]),
        "triggerPoolIndex": state["triggerPoolIndex"],
    }, choices


def readDialogue(data):
    dialogue, _, _ = reader.parseDialogue(data)
    raw = reader.Binary(data)
    offset = raw.number(12)
    if offset not in (48, 52):
        raise reader.AuditError("unexpected state offset in the audited patch dialogue")
    dialogue["headerFlags"] = raw.number(48) if offset == 52 else None
    for index, state in enumerate(dialogue["states"]):
        trigger = raw.number(offset + index * 16 + 12)
        state["triggerPoolIndex"] = None if trigger == 0xFFFFFFFF else trigger
    return dialogue


def compareDialogue(classic, enhanced):
    # Compare local choice positions within the same numbered state. The result is positional evidence only.
    changed = []
    for index in range(max(len(classic["states"]), len(enhanced["states"]))):
        if index >= min(len(classic["states"]), len(enhanced["states"])):
            changed.append({"state": index, "presentIn": "classic" if index < len(classic["states"]) else "ee"})
            continue
        old_state, old_choices = stateRecord(classic, index)
        new_state, new_choices = stateRecord(enhanced, index)
        fields = [key for key in old_state if old_state[key] != new_state[key]]
        choices = []
        for slot, (old, new) in enumerate(zip(old_choices, new_choices)):
            differences = [key for key in old if old[key] != new[key]]
            if differences:
                choices.append({"slot": slot, "fields": differences})
        row = {"state": index}
        if fields:
            row["fields"] = fields
        if len(old_choices) != len(new_choices):
            row["choiceCounts"] = [len(old_choices), len(new_choices)]
        if choices:
            row["changedChoices"] = choices
        if len(row) > 1:
            changed.append(row)
    return {
        "headerFlags": [classic["headerFlags"], enhanced["headerFlags"]],
        "classicCounts": [len(classic["states"]), len(classic["transitions"])],
        "eeCounts": [len(enhanced["states"]), len(enhanced["transitions"])],
        "changedStates": changed,
    }


def cityReferences(source):
    references = dict(source["references"])
    for section, ext in (("areas", "ARE"), ("creatures", "CRE"), ("items", "ITM")):
        for name, record in source[section].items():
            references[name + "." + ext] = record
    return references


def readCityMembers(directory, references):
    members = {}
    total_bytes = 0
    directory = directory.resolve(strict=True)
    for path in directory.iterdir():
        name = path.name.upper()
        if name not in references:
            continue
        if name in members or not path.is_file() or path.resolve().parent != directory:
            raise reader.AuditError(f"ambiguous or nonlocal city patch member {name}")
        total_bytes += path.stat().st_size
        if len(members) >= 128 or total_bytes > 8 * 1024 * 1024:
            raise reader.AuditError("city patch resources exceed the extraction bounds")
        members[name] = path.read_bytes()
    hashes = {name: reader.sha256(data) for name, data in members.items()}
    digest = reader.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode("ascii"))
    if digest != CITY_MEMBERS_SHA256:
        raise reader.AuditError("city patch member set or contents differ from the audited extraction")
    return members


def compareResource(name, classic, index, reference):
    stem, ext = name.split(".")
    enhanced, _ = index.read(stem, ext, "base")
    if reader.sha256(enhanced) != reference["sha256"]:
        raise reader.AuditError(f"EE base differs from the city source inventory for {name}")
    row = {"classicSha256": reader.sha256(classic), "eeSha256": reference["sha256"], "byteEqual": classic == enhanced}
    if ext == "DLG":
        row["dialogue"] = compareDialogue(readDialogue(classic), readDialogue(enhanced))
    elif ext in PARSERS:
        old, new = PARSERS[ext](classic)[0], PARSERS[ext](enhanced)[0]
        row["changedParsedFields"] = sorted(
            old.keys() ^ new.keys() | {key for key in old.keys() & new.keys() if old[key] != new[key]}
        )
        if ext == "ARE":
            row["placements"] = compareAreaPlacements(old, new)
    else:
        row["comparison"] = "fingerprintsOnly"
    return row


def compareAreaPlacements(classic, enhanced):
    changes = []
    for collection, fields in AREA_FIELDS.items():
        old_rows, new_rows = classic[collection], enhanced[collection]
        for index in range(max(len(old_rows), len(new_rows))):
            old = old_rows[index] if index < len(old_rows) else None
            new = new_rows[index] if index < len(new_rows) else None
            selected = fields if old is None or new is None else [key for key in fields if old[key] != new[key]]
            if selected:
                changes.append(
                    {
                        "collection": collection,
                        "index": index,
                        "classic": {key: old[key] for key in selected} if old is not None else None,
                        "ee": {key: new[key] for key in selected} if new is not None else None,
                    }
                )
    return changes


def buildAudit(patch_file, override_dir, ee_root):
    digest = reader.hashFile(patch_file)
    if digest != PATCH_SHA256:
        raise reader.AuditError("expected the audited international BG1 1.1.4315 installer")
    references = cityReferences(json.loads(CITY_SOURCE.read_bytes()))
    members = readCityMembers(override_dir, references)
    index = reader.ResourceIndex(ee_root)
    return {
        "classicSource": "International BG1 1.1.4315 patch, city members only",
        "classicPatchSha256": digest,
        "comparisonSource": "Installed EE base archives, hash matched to the city inventory",
        "fullOriginalInstallationVerified": False,
        "originalParityEstablished": False,
        "resources": {name: compareResource(name, members[name], index, references[name]) for name in sorted(members)},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch-file", type=Path, required=True)
    parser.add_argument("--patch-override", type=Path, required=True, help="extracted patch Override directory")
    parser.add_argument("--ee-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if (
        output == args.patch_file.resolve()
        or output.is_relative_to(args.patch_override.resolve())
        or output.is_relative_to(args.ee_root.resolve())
    ):
        parser.error("place the report outside the patch inputs and game installation")
    report = buildAudit(args.patch_file, args.patch_override, args.ee_root)
    if args.check:
        if not args.output.exists() or json.loads(args.output.read_bytes()) != report:
            parser.exit(1, "city patch audit differs from output\n")
    else:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(report['resources'])} patched city resources")


if __name__ == "__main__":
    main()
