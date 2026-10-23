"""Synthetic parser and factual contract checks; no native game or original assets required."""

import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from scripts import audit_baldurs_gate_palace as audit

FIXTURE = Path(__file__).parent / "fixtures" / "baldurs_gate_palace_scene_audit.json"


def syntheticSpell():
    data = bytearray(0x72 + 40 + 48)
    data[:8] = b"SPL V1  "
    struct.pack_into("<IHIHH", data, 0x64, 0x72, 1, 0x72 + 40, 0, 1)
    struct.pack_into("<HH", data, 0x72 + 0x1E, 1, 0)
    struct.pack_into("<H", data, 0x72 + 40, 151)
    struct.pack_into("<I", data, 0x72 + 40 + 8, 0)
    data[0x72 + 40 + 20 : 0x72 + 40 + 28] = b"imposter"
    return data


def syntheticCreature(effect_version=0):
    known, memorized, effects = 0x2D4, 0x2E0, 0x2EC
    items = effects + (0x108 if effect_version else 0x30)
    slots = items + 40
    data = bytearray(slots + 80)
    data[:8] = b"CRE V1.0"
    struct.pack_into("<I", data, 20, 9000)
    struct.pack_into("<I", data, 28, 123456)
    struct.pack_into("<hh", data, 0x24, 58, 60)
    data[0x33] = effect_version
    data[0x280:0x288] = b"TESTCRE\0"
    struct.pack_into("<II", data, 0x2A0, known, 1)
    struct.pack_into("<II", data, 0x2B0, memorized, 1)
    struct.pack_into("<I", data, 0x2B8, slots)
    struct.pack_into("<II", data, 0x2BC, items, 2)
    struct.pack_into("<II", data, 0x2C4, effects, 1)
    data[known : known + 8] = b"SPWI001\0"
    data[memorized : memorized + 8] = b"SPPR001\0"
    for offset, resource, expiration, charges, flags in (
        (items, b"SYNTH1\0\0", 0x1234, (1, 2, 3), 0x89ABCDEF),
        (items + 20, b"SYNTH2\0\0", 0xFFFF, (0xFFFF, 100, 0), 0xFFFFFFFF),
    ):
        data[offset : offset + 8] = resource
        struct.pack_into("<HHHHI", data, offset + 8, expiration, *charges, flags)
    values = [0xFFFF] * 40
    values[0], values[9], values[38], values[39] = 1, 0, 1, 0
    struct.pack_into("<40H", data, slots, *values)
    return data


class PalaceAuditParserTest(unittest.TestCase):

    def testRawCompiledSourceKeepsHeardNegationSelectorsAndWeightedAlternatives(self):
        from scripts import audit_baldurs_gate_palace_shout as shout

        def objectRecord(name):
            return 'OB\n0 0 0 0 0 0 0 0 0 0 0 0 "' + name + '"OB\n'

        trigger = 'TR\n1000 2 1 0 0 "" ""\n' + objectRecord("sourceSpeaker") + "TR\n"
        action = '2000 50 0 0 0 0 "" ""\n' + objectRecord("") * 3
        escape = '2001 0 0 0 0 0 "" ""\n' + objectRecord("") * 3
        text = (
            "SC\nCR\nCO\n"
            + trigger
            + "CO\nRS\nRE\n15AC\n"
            + action
            + "AC\nRE\nRE\n35AC\n"
            + escape
            + "AC\nRE\nRS\nCR\nSC\n"
        )
        text = text.replace("\\n", "\n")
        actions = audit.source.parseIds(b"2000 Shout(I:ID*SHOUTIDS)\n2001 EscapeArea()\n".replace(b"\\n", b"\n"))
        triggers = audit.source.parseIds(b"1000 Heard(O:Object*,I:ID*SHOUTIDS)\n".replace(b"\\n", b"\n"))
        parsed, references, warnings = audit.source.parseScript(text.encode("ascii"), actions, triggers)
        self.assertEqual(([], [], 1), (references, warnings, shout.blockCount(parsed)))
        block = audit.compiledBlockFacts("SYNTHETIC", 0, parsed)
        self.assertEqual("Heard", block["conditions"][0]["operation"])
        self.assertEqual([2, 1, 0, 0], block["conditions"][0]["integers"])
        self.assertTrue(block["conditions"][0]["negated"])
        self.assertEqual("sourceSpeaker", block["conditions"][0]["selectors"][0]["name"])
        self.assertEqual(["Shout", "EscapeArea"], [row["operation"] for row in block["actions"]])
        responses = audit.responseFacts(parsed)
        self.assertEqual([15, 35], [row["weight"] for row in responses])
        self.assertEqual(
            [["Shout"], ["EscapeArea"]],
            [[row["signature"].split("(")[0] for row in response["records"]] for response in responses],
        )
        self.assertFalse(parsed["semantics_evaluated"])
        self.assertFalse(block["semanticsEvaluated"])
        self.assertNotIn("raw", json.dumps(block))

    def testRawCompiledSourceRejectsMalformedPairsAndUnknownSelectedOperations(self):
        actions = audit.source.parseIds(b"2000 Shout(I:ID*SHOUTIDS)\n".replace(b"\\n", b"\n"))
        triggers = audit.source.parseIds(b"1000 Heard(O:Object*,I:ID*SHOUTIDS)\n".replace(b"\\n", b"\n"))
        with self.assertRaises(audit.source.AuditError):
            audit.source.parseScript(
                b'SC\nCR\nTR\n1000 2 0 0 0 "" ""\nCR\nSC\n'.replace(b"\\n", b"\n"), actions, triggers
            )
        text = 'SC\nCR\nAC\n99999 0 0 0 0 0 "" ""\nAC\nCR\nSC\n'.replace("\\n", "\n")
        parsed, references, warnings = audit.source.parseScript(text.encode("ascii"), actions, triggers)
        self.assertTrue(parsed["warnings"])
        with self.assertRaisesRegex(ValueError, "Unknown operation"):
            audit.compiledBlockFacts("SYNTHETIC", 0, parsed)

    def testRawAreaAndCreatureSlotsMergeByNameRatherThanArrayIndex(self):
        from scripts import audit_baldurs_gate_palace_shout as shout

        creature = syntheticCreature()
        creature_scripts = ("OVERRIDE", "CLASSCRE", "RACECRE", "GENERAL", "DEFAULT")
        for offset, value in zip(range(0x248, 0x270, 8), creature_scripts):
            creature[offset : offset + 8] = value.encode("ascii").ljust(8, b"\0")
        area = bytearray(0x11C + 0x110)
        area[:8] = b"AREAV1.0"
        struct.pack_into("<I", area, 0x54, 0x11C)
        struct.pack_into("<H", area, 0x58, 1)
        area[0x11C + 0x60 : 0x11C + 0x68] = b"CLASSARE"
        area[0x11C + 0x78 : 0x11C + 0x80] = b"SPECIFIC"
        area[0x11C + 0x80 : 0x11C + 0x88] = b"BASECRE\0"
        parsed_area = audit.source.parseArea(bytes(area))[0]["actors"][0]
        parsed_creature = audit.source.parseCreature(bytes(creature))[0]
        self.assertEqual(["", "", "CLASSARE", "", "", "SPECIFIC"], parsed_area["scripts"])
        self.assertEqual(list(creature_scripts), parsed_creature["scripts"])
        merged = shout.sourceScripts(parsed_area["scripts"], parsed_creature["scripts"])
        self.assertEqual({"resource": "CLASSARE", "origin": "area"}, merged["class"])
        self.assertEqual({"resource": "OVERRIDE", "origin": "creature"}, merged["override"])
        self.assertEqual({"resource": "GENERAL", "origin": "creature"}, merged["general"])
        self.assertEqual({"resource": "SPECIFIC", "origin": "area"}, merged["specific"])
        area[0x11C + 0x50 : 0x11C + 0x58] = b"NONE\0\0\0\0"
        suppressor = audit.source.parseArea(bytes(area))[0]["actors"][0]["scripts"]
        self.assertEqual(
            {"resource": "", "origin": "area"}, shout.sourceScripts(suppressor, parsed_creature["scripts"])["override"]
        )

    def testRawDialogueExpressionParserKeepsNestedSelectorsQuotedCommasAndNegation(self):
        text = (
            '!Global("phase","GLOBAL",3)\n'
            'ActionOverride("actor",AttackOneRound(NearestEnemyOf(Myself)))\n'
            'SetGlobal("quoted,comma","GLOBAL",-3)\n'
            'ChangeAIScript("",OVERRIDE)'
        )
        text = text.replace("\\n", "\n")
        self.assertEqual(
            [
                {"not": {"op": "Global", "args": ["phase", "GLOBAL", 3]}},
                {
                    "op": "ActionOverride",
                    "args": [
                        "actor",
                        {"op": "AttackOneRound", "args": [{"op": "NearestEnemyOf", "args": [{"symbol": "Myself"}]}]},
                    ],
                },
                {"op": "SetGlobal", "args": ["quoted,comma", "GLOBAL", -3]},
                {"op": "ChangeAIScript", "args": ["", {"symbol": "OVERRIDE"}]},
            ],
            audit.expressionFacts(text),
        )

    def testRawDialogueExpressionParserRejectsTruncationAndUnbalancedInputs(self):
        for text in ('ActionOverride("actor",Attack("target")', "Call([1.2)", 'SetGlobal("unterminated,GLOBAL,1)', ")"):
            with self.subTest(source=text), self.assertRaises(audit.source.AuditError):
                audit.expressionFacts(text)

    def assertCliPreservesEvidence(self, module, builder, raced):
        with tempfile.TemporaryDirectory(prefix="palace-audit-output-") as directory:
            output = Path(directory) / "retained.json"
            retained = b"retained evidence\n"
            if not raced:
                output.write_bytes(retained)
            original_open = Path.open
            injected = False

            def racedOpen(path, mode="r", *args, **kwargs):
                nonlocal injected
                if raced and path == output and not injected:
                    with original_open(path, "xb") as stream:
                        stream.write(retained)
                    injected = True
                return original_open(path, mode, *args, **kwargs)

            metadata = {"resourceFingerprints": {}, "sourceFingerprints": {}}
            args = ["source-audit", "--game-root", "unused", "--output", str(output)]
            with patch.object(module, builder, return_value=metadata), patch("sys.argv", args):
                with patch.object(Path, "open", racedOpen), patch("builtins.print"):
                    with self.assertRaises(FileExistsError):
                        module.main()
            self.assertEqual(retained, output.read_bytes())
            self.assertEqual(raced, injected)

    def testPalaceCliRefusesExistingEvidence(self):
        self.assertCliPreservesEvidence(audit, "auditPalace", False)

    def testPalaceCliRacingCreatePreservesEvidence(self):
        self.assertCliPreservesEvidence(audit, "auditPalace", True)

    def testPrisonCliRefusesExistingEvidence(self):
        from scripts import build_baldurs_gate_prison_source_fixture as prison

        self.assertCliPreservesEvidence(prison, "buildFixture", False)

    def testPrisonCliRacingCreatePreservesEvidence(self):
        from scripts import build_baldurs_gate_prison_source_fixture as prison

        self.assertCliPreservesEvidence(prison, "buildFixture", True)

    def testCliMetadataCapsAreCheckedBeforeOpeningOutput(self):
        from scripts import build_baldurs_gate_prison_source_fixture as prison

        for module, builder in ((audit, "auditPalace"), (prison, "buildFixture")):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "bounded.json"
                metadata = {"resourceFingerprints": {}, "sourceFingerprints": {}}
                args = ["source-audit", "--game-root", "unused", "--output", str(output)]
                with patch.object(module, builder, return_value=metadata), patch("sys.argv", args):
                    with patch.object(module, "MAX_OUTPUT_BYTES", 1, create=True):
                        with patch.object(Path, "open", side_effect=AssertionError("opened before output cap")):
                            with self.assertRaisesRegex(ValueError, "bounded"):
                                module.main()
                self.assertFalse(output.exists())

    def testCeremonyFollowsIndividualSpeakerEdgesWithoutDialogueText(self):
        dialogues = {
            "BELT": {
                "states": [{"first_transition": 0, "transition_count": 1, "trigger": "NumTimesTalkedTo(0)"}],
                "transitions": [{"next_dialogue": "SAREVO", "next_state": 7}],
            },
            "SAREVO": {
                "states": [{}] * 7 + [{"first_transition": 0, "transition_count": 1}],
                "transitions": [
                    {"next_dialogue": "", "next_state": None, "action": 'SetGlobal("NobleDopple","GLOBAL",1)'}
                ],
            },
        }
        rows = audit.ceremonyFacts(dialogues)
        self.assertEqual([row["sourceId"] for row in rows], ["BELT.DLG#state0", "SAREVO.DLG#state7"])
        self.assertEqual(rows[0]["edges"][0]["target"], {"dialogue": "SAREVO", "state": 7})
        self.assertEqual(rows[1]["edges"][0]["actions"], [{"op": "SetGlobal", "args": ["NobleDopple", "GLOBAL", 1]}])
        self.assertNotIn("text", rows[0])

    def testCeremonyRejectsCyclesChoicesAndMissingSpeakers(self):
        for target, count in (("BELT", 1), ("MISSING", 1), ("SAREVO", 2)):
            parsed = {
                "states": [{"first_transition": 0, "transition_count": count}],
                "transitions": [{"next_dialogue": target, "next_state": 0}] * count,
            }
            with self.subTest(target=target, count=count), self.assertRaises(ValueError):
                audit.ceremonyFacts({"BELT": parsed})

    def testClockConstantsRejectMissingOrAmbiguousSelectedSymbols(self):
        valid = (
            b"IDS V1.0\n5 ONE_MINUTE\n10 TWO_MINUTES\n15 THREE_MINUTES\n300 ONE_HOUR\n7200 ONE_DAY\n72000 TEN_DAYS\n"
        )
        self.assertEqual(audit.timeConstants(valid)["ONE_HOUR"], 300)
        with self.assertRaises(ValueError):
            audit.timeConstants(valid.replace(b"10 TWO_MINUTES\n", b""))
        with self.assertRaises(ValueError):
            audit.timeConstants(valid + b"11 TWO_MINUTES\n")

    def testCompiledBlockFactsKeepConditionNegationAndActionOrder(self):
        selector = 'OB\n0 0 0 0 0 0 0 0 0 0 0 0 "target"OB'
        parsed = {"compiled_text": "SC\nCR\ncondition\naction1\naction2\nCR\nSC", "records": []}
        for kind, offset, operation, values in (
            ("TR", 6, "Global", [3, 1, 0, 0]),
            ("AC", 18, "Dialogue", [0] * 5),
            ("AC", 26, "TriggerActivation", [1, 0, 0, 0, 0]),
        ):
            parsed["records"].append(
                {
                    "kind": kind,
                    "offset": offset,
                    "signature": operation + "()",
                    "integer_fields": values,
                    "strings": ["", ""],
                    "raw": selector,
                }
            )
        row = audit.compiledBlockFacts("BELT", 0, parsed)
        self.assertTrue(row["conditions"][0]["negated"])
        self.assertEqual([r["operation"] for r in row["actions"]], ["Dialogue", "TriggerActivation"])
        self.assertEqual(row["actions"][1]["selectors"][0]["name"], "target")
        self.assertFalse(row["semanticsEvaluated"])
        with self.assertRaises(ValueError):
            audit.compiledBlockFacts("BELT", 1, parsed)

    def testReportOutputIsDeterministicBoundedAndDoesNotRequireArtifactWrites(self):
        self.assertEqual(audit.encodeReport({"sourceId": "GTIMES.IDS"}), '{\n  "sourceId": "GTIMES.IDS"\n}\n')
        with self.assertRaises(ValueError):
            audit.encodeReport({"facts": "x" * audit.MAX_OUTPUT_BYTES})

    def testCreatureInventoryPreservesEveryRecordFieldAndAllRawSlots(self):
        data = syntheticCreature()
        metadata = audit.creatureMetadata(data)
        self.assertEqual(
            metadata["items"],
            [
                {"item": "SYNTH1", "expiration": 0x1234, "charges": [1, 2, 3], "flags": 0x89ABCDEF},
                {"item": "SYNTH2", "expiration": 0xFFFF, "charges": [0xFFFF, 100, 0], "flags": 0xFFFFFFFF},
            ],
        )
        self.assertEqual(len(metadata["itemSlots"]), 40)
        self.assertEqual(metadata["itemSlots"][:2], [1, 0xFFFF])
        self.assertEqual(metadata["itemSlots"][9], 0)
        self.assertEqual(metadata["itemSlots"][38:], [1, 0])
        self.assertEqual(metadata["death_variable"], "TESTCRE")
        self.assertEqual(metadata["hit_points"], 58)
        self.assertEqual(metadata["kill_xp"], 9000)
        self.assertEqual(metadata["gold"], 123456)
        self.assertEqual(metadata["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(metadata, audit.creatureMetadata(bytes(data)))

    def testCreatureSpellReferencesAndBothEffectFormatsRemainUninterpreted(self):
        for effect_version in (0, 1):
            with self.subTest(effect_version=effect_version):
                metadata = audit.creatureMetadata(syntheticCreature(effect_version))
                self.assertEqual(metadata["known_spells"], ["SPWI001"])
                self.assertEqual(metadata["memorized_spells"], ["SPPR001"])
                self.assertEqual(metadata["effect_count"], 1)
                self.assertFalse(metadata["effects_interpreted"])
                self.assertNotIn("effects", metadata)

    def testCreatureEmptyTablesAreRecordedWithoutInventedContents(self):
        data = syntheticCreature()
        for count_field in (0x2A4, 0x2B4, 0x2C0, 0x2C8):
            struct.pack_into("<I", data, count_field, 0)
        metadata = audit.creatureMetadata(data)
        for key in ("items", "known_spells", "memorized_spells"):
            self.assertEqual(metadata[key], [])
        self.assertEqual(metadata["effect_count"], 0)
        self.assertEqual(len(metadata["itemSlots"]), 40)

    def testCreatureMissingOrTruncatedSlotTablesFailClosed(self):
        for slots in (0, len(syntheticCreature()) - 79, 0xFFFFFFFF):
            data = syntheticCreature()
            struct.pack_into("<I", data, 0x2B8, slots)
            with self.subTest(slots=slots), self.assertRaises(audit.source.AuditError):
                audit.creatureMetadata(data)

    def testCreatureMalformedInventorySpellAndEffectTablesFailClosed(self):
        for count_field in (0x2A4, 0x2B4, 0x2C0, 0x2C8):
            data = syntheticCreature()
            struct.pack_into("<I", data, count_field, 0xFFFFFFFF)
            with self.subTest(count_field=count_field), self.assertRaises(audit.source.AuditError):
                audit.creatureMetadata(data)
        with self.assertRaises(audit.source.AuditError):
            audit.creatureMetadata(b"CRE V1.0")

    def testReplacementDeduplicatesCastingAndAbilityFeature(self):
        self.assertEqual(
            audit.spellReplacements(syntheticSpell()),
            [{"featureIndex": 0, "opcode": 151, "mode": 0, "creature": "IMPOSTER"}],
        )

    def testUnrelatedSpellEffectIsNotAReplacement(self):
        data = syntheticSpell()
        struct.pack_into("<H", data, 0x72 + 40, 141)
        self.assertEqual(audit.spellReplacements(data), [])

    def testRejectsUnsupportedAndTruncatedSpellHeaders(self):
        for data in (b"", b"SPL V1  ", b"SPL V2  " + bytes(200)):
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                audit.spellReplacements(data)

    def testRejectsOutOfBoundsSpellTables(self):
        for offset, value, kind in ((0x64, 9999, "I"), (0x68, 1025, "H"), (0x6A, 9999, "I"), (0x70, 2, "H")):
            data = syntheticSpell()
            struct.pack_into("<" + kind, data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                audit.spellReplacements(data)

    def testObjectSelectorsKeepActionOwnerAndTargetDistinct(self):
        raw = 'AC\n3OB\n0 0 0 0 0 0 0 0 0 0 0 0 "caster"OB\nOB\n0 0 0 0 0 0 0 0 0 0 0 0 "target"OB\n'
        self.assertEqual([v["name"] for v in audit.scriptObjects({"raw": raw})], ["caster", "target"])

    def testRejectsUnknownObjectSelectorWidth(self):
        with self.assertRaises(ValueError):
            audit.scriptObjects({"raw": 'OB\n0 0 "target"OB'})
        with self.assertRaises(ValueError):
            audit.scriptObjects({"raw": 'OB\nunknown "target"OB'})

    def testResponseWeightsDoNotLeakToNextResponse(self):
        text = "RE\n15AC\nfirst\nRE\nRE\n25AC\nsecond\nRE\n"
        first = {"kind": "AC", "offset": text.index("AC"), "signature": "Attack()"}
        second = {"kind": "AC", "offset": text.index("AC", first["offset"] + 2), "signature": "Attack()"}
        self.assertEqual(
            audit.responseFacts({"compiled_text": text, "records": [first, second]}),
            [{"weight": 15, "records": [first]}, {"weight": 25, "records": [second]}],
        )

    def testRejectsUnterminatedResponse(self):
        with self.assertRaises(ValueError):
            audit.responseFacts({"compiled_text": "RE\n25AC\nbody", "records": []})

    def testItemGatesDoNotTreatActionsAsPossessionChecks(self):
        dialogue = {
            "transitions": [
                {"trigger": 'PartyHasItem("proof")', "action": 'GiveItemCreate("reward",Player1,1,0,0)'},
                {"trigger": None, "action": 'PartyHasItem("not_a_gate")'},
            ]
        }
        self.assertEqual(audit.itemGates(dialogue), ["PROOF"])
        self.assertIn("GiveItemCreate", audit.actionNames(dialogue))


class PalaceSceneSourceContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def testArchiveFingerprintsAndParityLimitAreExplicit(self):
        self.assertFalse(self.fixture["originalParityEstablished"])
        self.assertEqual(len(self.fixture["resourceFingerprints"]), 43)
        additions = {"GTIMES.IDS", "NOBLPA1.DLG", "NOBLPA2.DLG", "NOBLPA3.DLG"}
        original = {key: value for key, value in self.fixture["resourceFingerprints"].items() if key not in additions}
        self.assertEqual(len(original), 39)
        fingerprint_json = json.dumps(original, sort_keys=True, separators=(",", ":"))
        self.assertEqual(
            hashlib.sha256(fingerprint_json.encode()).hexdigest(),
            "619f9b3aae78a5101caa1bf6e5260e6f9c4e1fa01ff649204161e0bcb0baf198",
            "The 39 pre-existing palace fingerprints must remain unchanged",
        )
        for value in self.fixture["resourceFingerprints"].values():
            self.assertRegex(value["sha256"], r"^[a-f0-9]{64}$")
            self.assertGreater(value["bytes"], 0)
        self.assertTrue(self.fixture["resourceFingerprints"]["SAREVO.ITM"]["overrideDiffers"])
        self.assertNotIn('"compiled_text"', json.dumps(self.fixture))
        self.assertNotIn('"text_strref"', json.dumps(self.fixture))

    def testCompleteCeremonyHasEachRealSpeakerInOrderAndOneTransformationCommit(self):
        facts = self.fixture["sceneFacts"]["ceremony"]
        expected = [
            ("BELT", 0),
            ("LIIA", 0),
            ("BELT", 1),
            ("NOBLPA1", 0),
            ("NOBLPA2", 0),
            ("NOBLPA3", 0),
            ("NOBLPA2", 2),
            ("NOBLPA2", 1),
            ("BELT", 2),
            ("NOBLPA1", 1),
            ("LIIA", 1),
            ("NOBLPA3", 1),
            ("LIIA", 2),
            ("NOBLPA1", 2),
            ("BELT", 3),
            ("BELT", 4),
            ("SAREVO", 5),
            ("SAREVO", 6),
            ("BELT", 5),
            ("NOBLPA3", 2),
            ("SAREVO", 7),
        ]
        self.assertEqual([(row["speaker"], row["state"]) for row in facts["steps"]], expected)
        for row, target in zip(facts["steps"], expected[1:]):
            self.assertEqual(row["edges"][0]["target"], {"dialogue": target[0], "state": target[1]})
        self.assertEqual(facts["start"]["sourceId"], "BELT.BCS#block1")
        self.assertEqual([r["operation"] for r in facts["start"]["conditions"]], ["Range", "NumberOfTimesTalkedTo"])
        self.assertEqual(facts["start"]["conditions"][0]["integers"][0], 15)
        last = facts["steps"][-1]["edges"][0]
        self.assertEqual(last["sourceId"], "SAREVO.DLG#state7/transition8")
        self.assertEqual(last["actions"][2], {"op": "SetGlobal", "args": ["NobleDopple", "GLOBAL", 1]})
        self.assertEqual([r["op"] for r in last["actions"]][3:], ["TriggerActivation"] * 4)
        self.assertTrue(
            all(r["args"][1] == {"symbol": "FALSE"} for r in last["actions"] if r["op"] == "TriggerActivation")
        )

    def testPostBattleDukeConditionsAndExitReopeningKeepTheirDifferentOrder(self):
        facts = self.fixture["sceneFacts"]["postBattle"]
        belt, liia = facts["belt"], facts["liia"]
        self.assertEqual(belt["sourceId"], "BELT.BCS#block2")
        self.assertEqual(liia["sourceId"], "LIIA.BCS#block1")
        self.assertEqual([r["operation"] for r in belt["actions"]], ["Dialogue"] + ["TriggerActivation"] * 4)
        self.assertEqual([r["operation"] for r in liia["actions"]], ["Dialogue"])
        self.assertEqual(
            [r["selectors"][1]["name"] for r in belt["actions"][1:]], ["Door0200", "Door0109a", "Door0109b", "Door0111"]
        )
        self.assertTrue(all(r["integers"][0] == 1 for r in belt["actions"][1:]))
        for row in (belt, liia):
            dead = [r["strings"][0] for r in row["conditions"] if r["operation"] == "Dead"]
            self.assertEqual(dead[:6], ["GDOPP7", "GDOPP71", "GDOPP72", "GDOPP73", "GDOPP74", "GDOPP75"])
            self.assertFalse(row["semanticsEvaluated"])
        self.assertEqual(liia["conditions"][-1]["strings"][0], "Belt")
        self.assertTrue(next(r for r in belt["conditions"] if r["operation"] == "See")["negated"])
        self.assertEqual(next(r for r in belt["conditions"] if r["operation"] == "CombatCounter")["integers"][0], 0)

    def testProofTransitionsKeepBothItemOpportunitiesAndUnconditionalNoProofDeath(self):
        states = {r["sourceId"]: r for r in self.fixture["sceneFacts"]["proofTransitions"]}
        for code, first, second in (("BELT", 6, 9), ("LIIA", 3, 6)):
            for state in (first, second):
                edges = states[code + ".DLG#state" + str(state)]["edges"]
                items = [c["args"][0] for e in edges for c in e["conditions"] if c.get("op") == "PartyHasItem"]
                self.assertEqual(items, ["SCRL2K", "SCRL3F"])
        death = states["SAREVO.DLG#state25"]["edges"][0]
        self.assertEqual(death["sourceId"], "SAREVO.DLG#state25/transition36")
        self.assertEqual(death["actions"][0], {"op": "SetGlobal", "args": ["SarevokBehavior", "GLOBAL", 10]})
        self.assertEqual(death["actions"][-1], {"op": "Kill", "args": [{"symbol": "Player1"}]})
        self.assertEqual([a["args"][0] for a in death["actions"] if a["op"] == "Wait"], [1, 2])

    def testExtractionRetainsTimerVisibilityWinskiAndCutsceneGates(self):
        facts = self.fixture["sceneFacts"]["extraction"]
        edge = facts["confrontation"]["edges"][0]
        self.assertEqual(edge["sourceId"], "SAREVO.DLG#state10/transition11")
        self.assertEqual(edge["actions"][0], {"op": "SetGlobal", "args": ["SarevokBehavior", "GLOBAL", 4]})
        timer = next(a for a in edge["actions"] if a["op"] == "SetGlobalTimer")
        self.assertEqual(timer["args"], ["SarevokRun", "GLOBAL", {"symbol": "TWO_MINUTES"}])
        gate = facts["gate"]
        self.assertEqual(gate["sourceId"], "AR0108.BCS#block5")
        self.assertEqual(
            [r["operation"] for r in gate["conditions"]],
            ["NextTriggerObject", "See", "GlobalTimerExpired", "Global", "Exists"],
        )
        self.assertEqual(gate["conditions"][0]["selectors"][0]["name"], "sarevok")
        self.assertTrue(gate["conditions"][-1]["negated"])
        self.assertEqual(gate["conditions"][-1]["selectors"][0]["name"], "Winski")
        self.assertEqual([r["operation"] for r in gate["actions"]][-5:], ["TriggerActivation"] * 4 + ["StartDialog"])
        handoff = facts["dialogue"]["edges"][0]
        self.assertEqual(handoff["sourceId"], "SAREVO.DLG#state11/transition12")
        self.assertEqual(handoff["actions"][0], {"op": "SetGlobal", "args": ["SarevokBehavior", "GLOBAL", 1]})
        self.assertEqual(facts["cutscene"]["sourceId"], "ENDCUT01.BCS#block0")

    def testBothDukeDeathAndAreaFailureRetainDistinctSourceTimerAndExecutionGates(self):
        facts = self.fixture["sceneFacts"]["failureTransitions"]
        state = facts["bothDukesDead"]
        self.assertEqual(state["sourceId"], "SAREVO.DLG#state8")
        self.assertEqual(
            state["edges"][0]["actions"][0],
            {
                "op": "SetGlobalTimerRandom",
                "args": ["EndGame", "GLOBAL", {"symbol": "ONE_MINUTE"}, {"symbol": "THREE_MINUTES"}],
            },
        )
        self.assertEqual(facts["areaFailure"]["sourceId"], "AR0108.BCS#block0")
        self.assertEqual(facts["areaFailure"]["conditions"][1]["strings"][0], "ar0108bd_once")
        self.assertEqual([b["sourceId"] for b in facts["timerExecutions"]], ["AR0108.BCS#block3", "AR0108.BCS#block4"])
        self.assertTrue(facts["timerExecutions"][0]["conditions"][-1]["negated"])
        self.assertFalse(facts["timerExecutions"][1]["conditions"][-1]["negated"])
        self.assertEqual([r["operation"] for r in facts["timerExecutions"][0]["actions"]].count("CreateCreature"), 1)
        self.assertNotIn("CreateCreature", [r["operation"] for r in facts["timerExecutions"][1]["actions"]])
        self.assertTrue(all(any(r["operation"] == "Kill" for r in b["actions"]) for b in facts["timerExecutions"]))

    def testClockValuesAndSelectedResourcesAreFingerprintedWithoutNativeTimeClaims(self):
        self.assertEqual(
            self.fixture["timerConstants"],
            {
                "sourceId": "GTIMES.IDS",
                "values": {
                    "ONE_MINUTE": 5,
                    "TWO_MINUTES": 10,
                    "THREE_MINUTES": 15,
                    "ONE_HOUR": 300,
                    "ONE_DAY": 7200,
                    "TEN_DAYS": 72000,
                },
            },
        )
        self.assertEqual(
            self.fixture["resourceFingerprints"]["GTIMES.IDS"]["sha256"],
            "d0fef0f123b4f7cdf7bf093dcd6359fdffcbeb159082c7f40404779ddc85b41c",
        )
        for resource, digest in self.fixture["sceneFacts"]["sourceResources"].items():
            self.assertEqual(digest, self.fixture["resourceFingerprints"][resource]["sha256"])
        self.assertLess(FIXTURE.stat().st_size, audit.MAX_OUTPUT_BYTES)
        self.assertTrue(any("GTIMES constants" in value for value in self.fixture["limitations"]))
        self.assertTrue(any("Ordered source actions" in value for value in self.fixture["limitations"]))

    def testPalaceAndFinaleSarevokAreDistinctSourceActors(self):
        identities = self.fixture["identities"]
        self.assertEqual(identities["SAREVO2"]["hitPoints"], 999)
        self.assertEqual(identities["SAREVO"]["hitPoints"], 135)
        self.assertEqual(self.fixture["palaceSpawns"][0]["creature"], "SAREVO2")
        self.assertEqual(self.fixture["palaceSpawns"][0]["position"], [581, 344])

    def testAllSixDisguisesReplaceToIndependentlyMortalAttackers(self):
        replacements = self.fixture["transformations"]
        self.assertEqual(len(replacements), 6)
        ids = [value["replacements"][0]["creature"] for value in replacements]
        self.assertEqual(ids, ["GDOPP7", "GDOPP71", "GDOPP72", "GDOPP73", "GDOPP74", "GDOPP75"])
        for value in replacements:
            self.assertEqual(value["replacements"][0]["mode"], 0)
        for name in ids:
            self.assertEqual(self.fixture["identities"][name]["deathVariable"], name)
            self.assertEqual(self.fixture["identities"][name]["killXp"], 4000)

    def testAllSixReplacementInventoriesHaveCompleteFactualMetadata(self):
        metadata = self.fixture["creatureMetadata"]
        codes = ["GDOPP7", "GDOPP71", "GDOPP72", "GDOPP73", "GDOPP74", "GDOPP75"]
        self.assertEqual(list(metadata), codes)
        expected_slots = [0xFFFF] * 40
        for index, value in ((4, 3), (5, 2), (9, 0), (18, 1), (38, 0), (39, 0)):
            expected_slots[index] = value
        for code in codes:
            with self.subTest(creature=code):
                row = metadata[code]
                self.assertEqual(row["sha256"], self.fixture["resourceFingerprints"][code + ".CRE"]["sha256"])
                self.assertEqual(row["death_variable"], self.fixture["identities"][code]["deathVariable"])
                self.assertEqual(row["hit_points"], 58)
                self.assertEqual(row["kill_xp"], 4000)
                self.assertEqual(
                    row["items"],
                    [
                        {"item": item, "expiration": 0, "charges": [0, 0, 0], "flags": 0}
                        for item in ("S1-12", "RNDTRE05", "MAGE04", "MAGE06")
                    ],
                )
                self.assertEqual([item["item"] for item in row["items"]], self.fixture["identities"][code]["items"])
                self.assertEqual(row["itemSlots"], expected_slots)
                self.assertEqual(row["gold"], 0)
                self.assertEqual(row["known_spells"], [])
                self.assertEqual(row["memorized_spells"], [])
                self.assertEqual(row["effect_count"], 0)
                self.assertFalse(row["effects_interpreted"])

    def testRandomTreasureAndReplacementInventorySemanticsRemainUnresolved(self):
        self.assertTrue(
            any("RNDTRE05" in value and "not established" in value for value in self.fixture["limitations"])
        )
        self.assertTrue(
            any("Opcode 151" in value and "remains unestablished" in value for value in self.fixture["limitations"])
        )
        self.assertFalse(self.fixture["originalParityEstablished"])

    def testDoppelgangerAttackChoicesIncludeBothDukes(self):
        responses = self.fixture["doppelgangerAttackResponses"]
        normal = [r for r in responses if r["action"] == "Attack"]
        self.assertEqual([r["weight"] for r in normal], [30, 30, 30])
        self.assertEqual([r["target"]["name"] for r in normal], ["", "Liia", "Belt"])
        failure = [r for r in responses if r["action"] == "AttackReevaluate"]
        self.assertEqual([r["weight"] for r in failure], [15, 35, 25, 25])

    def testBothDukesAcceptEitherProofItemWithoutConsumptionOrReward(self):
        for name in ("BELT", "LIIA"):
            self.assertEqual(self.fixture["evidenceGates"][name], ["SCRL2K", "SCRL3F"])
            for action in self.fixture["dukeDialogueActionNames"][name]:
                self.assertNotRegex(action, r"(?i)(?:TakePartyItem|DestroyItem|GiveItem|AddXP|AddGold|Reputation)")
        self.assertEqual(self.fixture["invitationGates"], {"BILL": ["MISC78"], "FLAM10": ["MISC78"]})

    def testEscapeTimingDoesNotClaimUnobservedHitPointThreshold(self):
        self.assertEqual(
            self.fixture["sarevokTimers"], [{"transition": 11, "timer": "SarevokRun", "units": "TWO_MINUTES"}]
        )
        self.assertEqual(self.fixture["hpTriggersInPalaceAndSarevokScripts"], [])
        self.assertTrue(any("damage-triggered" in value for value in self.fixture["limitations"]))


if __name__ == "__main__":
    unittest.main()
