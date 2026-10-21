"""Synthetic parser regression fixtures; contains no original game assets or dialogue."""

import importlib.util
import gzip
import io
import json
from collections import Counter
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_candlekeep_source.py"
SPEC = importlib.util.spec_from_file_location("candlekeep_source", MODULE_PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def putNumber(data, offset, value, kind="I"):
    struct.pack_into("<" + kind, data, offset, value)


def putText(data, offset, value):
    encoded = value.encode("ascii")
    data[offset : offset + len(encoded)] = encoded


def emptyArea():
    data = bytearray(0x11C)
    putText(data, 0, "AREAV1.0")
    return data


def creature(dialogue="QUEST"):
    data = bytearray(0x2D4)
    putText(data, 0, "CRE V1.0")
    putText(data, 0x2CC, dialogue)
    return bytes(data)


def dialogue():
    # One NPC state; one conditional player response with action and journal.
    strings = [b"NumTimesTalkedTo(0)", b"ReactionLT(LastTalkedToBy,15)", b'GiveItemCreate("TOKEN",Player1,1,0,0)']
    data = bytearray(0x30 + 16 + 32 + 24)
    putText(data, 0, "DLG V1.0")
    for offset, value in (
        (8, 1),
        (12, 0x30),
        (16, 1),
        (20, 0x40),
        (24, 0x60),
        (28, 1),
        (32, 0x68),
        (36, 1),
        (40, 0x70),
        (44, 1),
    ):
        putNumber(data, offset, value)
    for offset, value in ((0x30, 0), (0x34, 0), (0x38, 1), (0x3C, 0), (0x40, 1 | 2 | 4 | 8 | 16), (0x44, 1), (0x48, 2)):
        putNumber(data, offset, value)
    for index, value in enumerate(strings):
        putNumber(data, 0x60 + index * 8, len(data))
        putNumber(data, 0x64 + index * 8, len(value))
        data.extend(value)
    return bytes(data)


def talkTable(strings):
    data = bytearray(18 + 26 * len(strings))
    putText(data, 0, "TLK V1  ")
    putNumber(data, 10, len(strings))
    putNumber(data, 14, len(data))
    text_offset = 0
    for index, text in enumerate(strings):
        value = text.encode("utf-8")
        offset = 18 + index * 26
        putNumber(data, offset, 1, "H")
        putNumber(data, offset + 18, text_offset)
        putNumber(data, offset + 22, len(value))
        data.extend(value)
        text_offset += len(value)
    return bytes(data)


def installation(root, resources):
    name = b"data/test.bif\0"
    data_dir = root / "data"
    data_dir.mkdir()
    payload = bytearray(20 + 16 * len(resources))
    putText(payload, 0, "BIFFV1  ")
    putNumber(payload, 8, len(resources))
    putNumber(payload, 16, 20)
    key = bytearray(24 + 12 + len(name) + 14 * len(resources))
    putText(key, 0, "KEY V1  ")
    for offset, value in ((8, 1), (12, len(resources)), (16, 24), (20, 36 + len(name)), (28, 36)):
        putNumber(key, offset, value)
    putNumber(key, 32, len(name), "H")
    key[36 : 36 + len(name)] = name
    for index, (name, ext, content) in enumerate(resources):
        # Deliberately use non-sequential locator values, not table row ordinal.
        locator = index + 53
        offset = 20 + index * 16
        putNumber(payload, offset, locator)
        putNumber(payload, offset + 4, len(payload))
        putNumber(payload, offset + 8, len(content))
        putNumber(payload, offset + 12, audit.TYPE_CODES[ext], "H")
        payload.extend(content)
        offset = 36 + len(b"data/test.bif\0") + index * 14
        putText(key, offset, name)
        putNumber(key, offset + 8, audit.TYPE_CODES[ext], "H")
        putNumber(key, offset + 10, locator)
    putNumber(key, 24, len(payload))
    (data_dir / "test.bif").write_bytes(payload)
    (root / "chitin.key").write_bytes(key)
    (root / "dialog.tlk").write_bytes(talkTable(["synthetic NPC", "synthetic answer", "synthetic journal"]))


class BinaryParserTests(unittest.TestCase):
    def testNumericTwoDaRetainsDonationCellsAndRejectsAmbiguousRows(self):
        data = b"2DA V1.0\n0\nMONEY_CHURCH BASE_CHURCH\n10 10 300\n18 0 0\n"
        parsed, refs, strings = audit.parseNumericTwoDa(data)
        self.assertEqual({"MONEY_CHURCH": 10, "BASE_CHURCH": 300}, parsed["rows"]["10"])
        self.assertEqual({"MONEY_CHURCH": 0, "BASE_CHURCH": 0}, parsed["rows"]["18"])
        self.assertEqual(([], []), (refs, strings))
        for malformed in (
            data.replace(b"10 10 300", b"10 10"),
            data + b"10 0 100\n",
            data.replace(b"10 10 300", b"10 10 unknown"),
        ):
            with self.subTest(malformed=malformed), self.assertRaises(audit.AuditError):
                audit.parseNumericTwoDa(malformed)

    def testGameNpcPlacementUsesDocumentedTablesAndPreservesState(self):
        for version in ("GAMEV1.1", "GAMEV2.0"):
            with self.subTest(version=version):
                data = bytearray(0xB4 + 2 * 0x160)
                putText(data, 0, version)
                putNumber(data, 0x20, 0xB4)
                putNumber(data, 0x24, 1)
                putNumber(data, 0x30, 0xB4 + 0x160)
                putNumber(data, 0x34, 1)
                putText(data, 0xB4 + 0xC, "PARTY")
                offset = 0xB4 + 0x160
                putNumber(data, offset, 0x8001, "H")
                putNumber(data, offset + 2, 0xFFFF, "H")
                putText(data, offset + 0xC, "ALORA")
                putText(data, offset + 0x18, "AR0130")
                putNumber(data, offset + 0x20, 759, "H")
                putNumber(data, offset + 0x22, 764, "H")
                putNumber(data, offset + 0x14, 7)
                putNumber(data, offset + 0xE0, 37)
                parsed, refs, strings = audit.parseGame(data)
                self.assertEqual("PARTY", parsed["party_members"][0]["creature"])
                row = parsed["non_party_members"][0]
                self.assertEqual(("ALORA", "AR0130", [759, 764]), (row["creature"], row["area"], row["position"]))
                self.assertEqual(
                    (0x8001, 0xFFFF, 7, 37),
                    (row["selection_flags"], row["party_order"], row["orientation"], row["talk_count"]),
                )
                self.assertIn(("ALORA", "CRE"), {(ref["name"], ref["type"]) for ref in refs if ref})
                self.assertEqual([], strings)

    def testGameEmbeddedCreatureAndMalformedRecordsFailClosed(self):
        data = bytearray(0xB4 + 0x160)
        putText(data, 0, "GAMEV1.1")
        putNumber(data, 0x30, 0xB4)
        putNumber(data, 0x34, 1)
        embedded = creature("QUEST")
        putNumber(data, 0xB4 + 4, len(data))
        putNumber(data, 0xB4 + 8, len(embedded))
        data.extend(embedded)
        parsed, refs, _ = audit.parseGame(data)
        row = parsed["non_party_members"][0]
        self.assertEqual("QUEST", row["embedded_creature"]["dialogue"])
        self.assertEqual(audit.sha256(embedded), row["embedded_creature_sha256"])
        self.assertTrue(any(ref and ref["name"] == "QUEST" and ref["type"] == "DLG" for ref in refs))
        with self.assertRaises(audit.AuditError):
            audit.parseGame(data[:-1])
        putNumber(data, 0xB4 + 4, 0)
        with self.assertRaises(audit.AuditError):
            audit.parseGame(data)
        putText(data, 0, "GAMEV9.9")
        with self.assertRaises(audit.AuditError):
            audit.parseGame(data)
        data = bytearray(0xB4)
        putText(data, 0, "GAMEV1.1")
        putNumber(data, 0x30, 0xB4)
        putNumber(data, 0x34, 1)
        with self.assertRaises(audit.AuditError):
            audit.parseGame(data)

    def testAreaAdjacencyAndTravelPolygon(self):
        data = emptyArea()
        putText(data, 0x18, "AR0200")
        putNumber(data, 0x20, 3)
        putNumber(data, 0x5C, len(data))
        putNumber(data, 0x5A, 1, "H")
        region = len(data)
        data.extend(bytes(0xC4))
        putText(data, region, "Exit")
        putText(data, region + 0x38, "AR0101")
        putNumber(data, region + 0x2A, 3, "H")
        putNumber(data, 0x7C, len(data))
        putNumber(data, 0x80, 3, "H")
        for point in ((4, 5), (7, 5), (7, 9)):
            data.extend(struct.pack("<HH", *point))
        parsed, refs, _ = audit.parseArea(data)
        self.assertEqual(parsed["adjacency"], [{"direction": "north", "area": "AR0200", "flags": 3}])
        self.assertEqual(parsed["regions"][0]["polygon"], [[4, 5], [7, 5], [7, 9]])
        self.assertIn("AR0200", [ref["name"] for ref in refs if ref])
        putNumber(data, region + 0x2A, 4, "H")
        with self.assertRaisesRegex(audit.AuditError, "polygon vertex range"):
            audit.parseArea(data)

    def testSearchMapIndexedRowsOrientationPaddingAndBounds(self):
        for depth, top_down in ((4, False), (8, True)):
            with self.subTest(depth=depth, top_down=top_down):
                width, height = 3, 2
                stride = ((width * depth + 31) // 32) * 4
                data = bytearray(54 + stride * height)
                putText(data, 0, "BM")
                for offset, value in ((10, 54), (14, 40), (18, width)):
                    putNumber(data, offset, value)
                putNumber(data, 22, -height if top_down else height, "i")
                putNumber(data, 26, 1, "H")
                putNumber(data, 28, depth, "H")
                rows = [[0, 7, 7], [10, 15, 8]]
                for source_y, row in enumerate(rows if top_down else reversed(rows)):
                    values = row if depth == 8 else [(row[0] << 4) | row[1], row[2] << 4]
                    data[54 + source_y * stride : 54 + source_y * stride + len(values)] = bytes(values)
                parsed = audit.parseSearchMap(data)
                self.assertEqual(parsed["terrainRowsRle"], [[1, 0, 2, 7], [1, 10, 1, 15, 1, 8]])
                self.assertEqual(parsed["sourceCellPixels"], [16, 12])
                with self.assertRaises(audit.AuditError):
                    audit.parseSearchMap(data[:-1])
                putNumber(data, 30, 1)
                with self.assertRaisesRegex(audit.AuditError, "uncompressed"):
                    audit.parseSearchMap(data)

    def testWorldMapLinksPreserveEntryFlagsAndRejectInvalidDestination(self):
        data = bytearray(16 + 0xB8 + 2 * 0xF0 + 0xD8)
        putText(data, 0, "WMAPV1.0")
        putNumber(data, 8, 1)
        putNumber(data, 12, 16)
        areas = 16 + 0xB8
        link = areas + 2 * 0xF0
        for field, value in ((0x20, 2), (0x24, areas), (0x28, link), (0x2C, 1)):
            putNumber(data, 16 + field, value)
        putText(data, areas, "AR0100")
        putText(data, areas + 0xF0, "AR0200")
        putNumber(data, areas + 0x6C, 1)
        putNumber(data, link, 1)
        putText(data, link + 4, "WestEntry")
        putNumber(data, link + 0x24, 4)
        putNumber(data, link + 0x28, 8)
        parsed, refs, _ = audit.parseWorldMap(data)
        row = parsed["worlds"][0]["areas"][0]["links"][0]
        self.assertEqual((row["direction"], row["destination"], row["entrance"]), ("east", "AR0200", "WestEntry"))
        self.assertEqual((row["travel_time_quarters"], row["arrival_flags"]), (4, 8))
        putNumber(data, link, 2)
        with self.assertRaisesRegex(audit.AuditError, "destination outside"):
            audit.parseWorldMap(data)

    def testBoundsAndVersionRejection(self):
        for operation in (
            lambda: audit.Binary(b"x").span(2, 0),
            lambda: audit.parseArea(b"AREA"),
            lambda: audit.parseCreature(b"CRE V9.0" + bytes(0x400)),
            lambda: audit.Binary(bytes(12)).table(0, 0xFFFFFFFF, 4),
        ):
            with self.assertRaises(audit.AuditError):
                operation()

    def testAreaActorsAndEmbeddedCreature(self):
        data = emptyArea()
        putNumber(data, 0x54, len(data))
        putNumber(data, 0x58, 1, "H")
        offset = len(data)
        data.extend(bytes(0x110))
        putText(data, offset, "synthetic actor")
        putText(data, offset + 0x80, "ACTOR")
        putNumber(data, offset + 0x88, len(data))
        content = creature("LOCALDLG")
        putNumber(data, offset + 0x8C, len(content))
        data.extend(content)
        parsed, refs, unused = audit.parseArea(data)
        self.assertEqual(parsed["actors"][0]["embedded_creature"]["dialogue"], "LOCALDLG")
        self.assertIn("LOCALDLG", [entry["name"] for entry in refs if entry])
        self.assertNotIn("ACTOR", [entry["name"] for entry in refs if entry])

    def testContainerItemsAndOwnership(self):
        data = emptyArea()
        putNumber(data, 0x70, len(data))
        putNumber(data, 0x74, 1, "H")
        offset = len(data)
        data.extend(bytes(0xC0))
        putText(data, offset, "chest")
        putText(data, offset + 0x58, "OWNER")
        putNumber(data, offset + 0x26, 70, "H")
        putNumber(data, offset + 0x28, 1)
        putNumber(data, offset + 0x44, 1)
        putNumber(data, 0x78, len(data))
        putNumber(data, 0x76, 1, "H")
        data.extend(bytes(20))
        putText(data, len(data) - 20, "TOKEN")
        parsed, refs, unused = audit.parseArea(data)
        self.assertEqual(parsed["containers"][0]["owner"], "OWNER")
        self.assertEqual(parsed["containers"][0]["lock_difficulty"], 70)
        self.assertEqual(parsed["containers"][0]["items"][0]["item"], "TOKEN")
        putNumber(data, offset + 0x44, 2)
        with self.assertRaisesRegex(audit.AuditError, "container item range"):
            audit.parseArea(data)

    def testDialoguePoolsAndMalformedIndices(self):
        parsed, refs, unused = audit.parseDialogue(dialogue())
        self.assertEqual(parsed["states"][0]["trigger"], "NumTimesTalkedTo(0)")
        self.assertIn("ReactionLT", parsed["transitions"][0]["trigger"])
        self.assertEqual(parsed["transitions"][0]["journal_strref"], 2)
        malformed = bytearray(dialogue())
        putNumber(malformed, 0x4C, 20)
        with self.assertRaisesRegex(audit.AuditError, "outside pool"):
            audit.parseDialogue(malformed)
        putNumber(malformed, 0x4C, 0)
        putNumber(malformed, 0x34, 20)
        with self.assertRaisesRegex(audit.AuditError, "transition range"):
            audit.parseDialogue(malformed)

    def testStoreAndItemMetadata(self):
        data = bytearray(0x9C + 28)
        putText(data, 0, "STORV1.0")
        putNumber(data, 0x34, 0x9C)
        putNumber(data, 0x38, 1)
        putText(data, 0x9C, "TOKEN")
        putNumber(data, 0x9C + 20, 7)
        parsed, refs, unused = audit.parseStore(data)
        self.assertEqual(parsed["stock"][0]["stock"], 7)
        item = bytearray(0x72)
        putText(item, 0, "ITM V1  ")
        putNumber(item, 0x34, 125)
        putNumber(item, 0x60, 1)
        parsed, refs, unused = audit.parseItem(item)
        self.assertEqual((parsed["price"], parsed["enchantment"]), (125, 1))

    def testCompiledScriptGluedMarkersAndReferences(self):
        obj = 'OB\n0 0 0 0 0 0 0 0 0 0 0 0 "OBJECT"OB\n'
        content = (
            'SC\nCR\nCO\nTR\n16399 1 1 0 0 "GLOBALflag" "" '
            + obj
            + "TR\nCO\nRS\nRE\n100AC\n7"
            + obj * 3
            + '0 1 2 0 0"GUARD" "" AC\nRE\nRS\nCR\nSC\n'
        ).encode("ascii")
        parsed, refs, unused = audit.parseScript(
            content,
            {7: "CreateCreature(S:NewObject*,P:Location*,I:Face*DIR)"},
            {16399: "Global(S:Name*,S:Area*,I:Value*)"},
        )
        self.assertEqual(len(parsed["records"]), 2)
        self.assertEqual(parsed["records"][1]["strings"], ["GUARD", ""])
        self.assertEqual([entry["name"] for entry in refs if entry], ["GUARD"])
        with self.assertRaises(audit.AuditError):
            audit.parseScript(b"SC\nAC\n1\nSC", {}, {})

    def testNestedDialogueReferenceAndNoGlobalAreaFalsePositive(self):
        refs = audit.textReferences(
            'ActionOverride(Player1,CreateCreature("GUARD",[1.2],0))\n' 'Global("AR2600","GLOBAL",1)',
            {7: "CreateCreature(S:NewObject*,P:Location*,I:Face*DIR)"},
            {1: "Global(S:Name*,S:Area*,I:Value*)"},
        )
        self.assertEqual([entry["name"] for entry in refs if entry], ["GUARD"])

    def testCompiledItemObjectArgumentsAreResourceReferences(self):
        obj = 'OB\n0 0 0 0 0 0 0 0 0 0 0 0 "TARGET"OB\n'
        content = (
            "SC\nAC\n7" + obj * 3 + '0 0 0 0 0 "TOKEN" "" AC\nAC\n8' + obj * 3 + '0 0 0 0 0 "POTION" "" AC\nSC\n'
        ).encode("ascii")
        parsed, refs, unused = audit.parseScript(
            content,
            {7: "GiveItem(S:Object*,O:Target*)", 8: "UseItem(S:Object*,O:Target*)"},
            {},
        )
        self.assertEqual(len(parsed["records"]), 2)
        self.assertEqual(
            [(entry["name"], entry["type"]) for entry in refs if entry],
            [("TOKEN", "ITM"), ("POTION", "ITM")],
        )

    def testDialogueItemObjectArgumentsAreResourceReferences(self):
        refs = audit.textReferences(
            'ActionOverride(Player1,GiveItem("TOKEN",Player1))\n'
            'UseItem("POTION",LastTalkedToBy())\n'
            "GiveItem(Player1,Player1)\n"
            'Name("ACTOR",Player1)',
            {7: "GiveItem(S:Object*,O:Target*)", 8: "UseItem(S:Object*,O:Target*)"},
            {9: "Name(S:Name*,O:Object*)"},
        )
        self.assertEqual(
            [(entry["name"], entry["type"]) for entry in refs if entry],
            [("TOKEN", "ITM"), ("POTION", "ITM")],
        )

    def testStoreReferenceWithNestedObjectArgument(self):
        refs = audit.textReferences(
            'StartStore("SHOP",LastTalkedToBy())\nSetDialogue("NEXT")',
            {1: "StartStore(S:Store*,O:Target*)", 2: "SetDialogue(S:DialogFile*)"},
            {},
        )
        self.assertEqual(
            [(entry["name"], entry["type"]) for entry in refs if entry], [("SHOP", "STO"), ("NEXT", "DLG")]
        )

    def testIdsAliasesPreserveDepartureCutsceneReference(self):
        ids = audit.parseIds(b"120 StartCutScene(S:CutScene*)\n120 StartCutSceneEx(S:CutScene*,I:Flag*)\n")
        self.assertEqual(ids[120], "StartCutScene(S:CutScene*)")
        refs = audit.textReferences('StartCutScene("DEPART")\nStartCutSceneEx("OTHER",1)', ids, {})
        self.assertEqual(
            [(entry["name"], entry["type"]) for entry in refs if entry], [("DEPART", "BCS"), ("OTHER", "BCS")]
        )

    def testRestInterruptionRangeAndCreatureReference(self):
        data = emptyArea()
        putNumber(data, 0xC0, len(data))
        offset = len(data)
        data.extend(bytes(0xE4))
        putNumber(data, offset + 0x98, 1, "H")
        putText(data, offset + 0x48, "GUARD")
        parsed, refs, unused = audit.parseArea(data)
        self.assertEqual(parsed["rest_interruptions"]["creatures"], ["GUARD"])
        self.assertIn("GUARD", [entry["name"] for entry in refs if entry])
        putNumber(data, offset + 0x98, 11, "H")
        with self.assertRaisesRegex(audit.AuditError, "ten creature slots"):
            audit.parseArea(data)


class SourceAuditTests(unittest.TestCase):
    def testCityDonationThresholdsRetainSourceFingerprintAndReputationRows(self):
        fixture = json.loads(
            (MODULE_PATH.parents[1] / "tests/fixtures/baldurs_gate_city_source.json").read_text(encoding="utf-8")
        )
        rule = fixture["numericSourceRules"]["REPUTATI.2DA"]
        self.assertEqual("65ab70beb4b455b35545a83e690bc439b092032025ac2a3a9fb71c4ef4ac680d", rule["sha256"])
        self.assertEqual(
            [1500, 1200, 1000, 600, 500, 300, 150, 100, 200, 300, 500, 800, 1000, 1500, 2000, 2500, 5000, 0, 0, 0],
            [rule["rows"][str(value)]["BASE_CHURCH"] for value in range(1, 21)],
        )
        self.assertEqual([10] * 17 + [0] * 3, [rule["rows"][str(value)]["MONEY_CHURCH"] for value in range(1, 21)])
        self.assertFalse(fixture["originalParityEstablished"])

    def testCityCampaignNpcPlacementsRemainFactualAndExternalMapsStayExcluded(self):
        fixture = json.loads(
            (MODULE_PATH.parents[1] / "tests/fixtures/baldurs_gate_city_source.json").read_text(encoding="utf-8")
        )
        rows = {row["creature"]: row for row in fixture["campaignNpcs"]}
        expected = {
            "ALORA": ("AR0130", [759, 764], "city"),
            "TIAX": ("AR1100", [1445, 1615], "city"),
            "SKIE": ("AR0102", [701, 1262], "city"),
            "QUAYLE": ("AR0900", [483, 803], "boundaryHistory"),
            "ELDOTH": ("AR1600", [3181, 3493], "externalHistory"),
        }
        self.assertEqual(set(expected), set(rows))
        for creature_id, values in expected.items():
            row = rows[creature_id]
            self.assertEqual(values, (row["area"], row["position"], row["scopeClassification"]))
            self.assertEqual(fixture["campaignGame"]["sha256"], row["sourceSha256"])
            self.assertIn(row["creatureMetadata"], fixture["creatures"])
            self.assertTrue(row["displayName"])
            self.assertRegex(row["creatureSha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(36, fixture["campaignGame"]["nonPartyCount"])
        self.assertEqual(5, fixture["counts"]["campaignNpcs"])
        self.assertNotIn("AR0900", fixture["areas"])
        self.assertNotIn("AR1600", fixture["areas"])

    def testCityAuditScopeIsBoundedAndUnknownScopesFailClosed(self):
        with patch(
            "scripts.build_baldurs_gate_source_fixture.buildCityFixture", return_value={"scope": "city"}
        ) as build:
            self.assertEqual(
                audit.auditInstallation("source-root", language="pl_PL", encoding="cp1250", scope="city"),
                {"scope": "city"},
            )
            build.assert_called_once_with("source-root", "pl_PL", "cp1250")
        with self.assertRaisesRegex(audit.AuditError, "unsupported audit scope"):
            audit.auditInstallation("source-root", scope="all-world")

    def testCityAuditCliPreservesHistoricalCandlekeepReport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "audit"
            output.mkdir()
            historical = output / "source-audit.json.gz"
            historical.write_bytes(b"historical retained audit")
            report = {"counts": {"areas": 212}, "unresolved": [{"resource": "OPTIONAL.BCS"}]}
            with patch.object(audit, "auditInstallation", return_value=report) as run:
                with patch("sys.stdout", new_callable=io.StringIO):
                    result = audit.main(
                        ["--game-root", str(root / "game"), "--scope", "city", "--output-dir", str(output)]
                    )
            self.assertEqual(result, 2)
            self.assertEqual(run.call_args.args[-1], "city")
            self.assertEqual(historical.read_bytes(), b"historical retained audit")
            with gzip.open(output / "city-source-audit.json.gz", "rt", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream), report)

    def testCityScriptedActorsUseVerifiedCoordinatesAndRetainConditions(self):
        from scripts.build_baldurs_gate_source_fixture import compiledSpawnFacts

        obj = 'OB\n0 0 0 0 0 0 0 0 0 0 0 0 "TARGET"OB\n'
        content = (
            'SC\nCR\nCO\nTR\n1 7 1 0 0 "GLOBALChapter" "" '
            + obj
            + "TR\nCO\nRS\nRE\n100AC\n7"
            + obj * 3
            + '14 56 78 9 10 "SCAR" "" AC\nRE\nRS\nCR\nSC\n'
        ).encode("ascii")
        parsed, _, _ = audit.parseScript(
            content, {7: "CreateCreature(S:NewObject*,P:Location*,I:Face*DIR)"}, {1: "Global(S:Name*,S:Area*,I:Value*)"}
        )
        fact = compiledSpawnFacts(parsed)[0]
        self.assertEqual(fact["position"], [56, 78])
        self.assertEqual(fact["block"], 0)
        self.assertTrue(fact["conditions"][0]["negated"])
        self.assertEqual(fact["conditions"][0]["strings"][0], "GLOBALChapter")
        self.assertFalse(fact["conditionSemanticsEvaluated"])
        fixture = json.loads(
            (MODULE_PATH.parents[1] / "tests/fixtures/baldurs_gate_city_source.json").read_text(encoding="utf-8")
        )
        expected = {
            "SCAR": ("AR0607", [1515, 1050]),
            "SLYTHE": ("AR0112", [1278, 969]),
            "KRYSTI": ("AR0112", [1349, 973]),
            "BELT": ("AR0108", [735, 371]),
            "LIIA": ("AR0108", [680, 356]),
            "GERVIS": ("AR0162", [807, 497]),
        }
        for creature, (area, point) in expected.items():
            matches = [
                row
                for row in fixture["scriptedActors"]
                if row["creature"] == creature and row["areas"] == [area] and row["position"] == point
            ]
            self.assertTrue(matches, creature)
            self.assertIn(creature, fixture["creatures"])
            self.assertTrue(all(len(row["sourceSha256"]) == 64 for row in matches))

    def testCityFixtureIsExplicitBoundedAndContainsNoDialogueDump(self):
        path = MODULE_PATH.parents[1] / "tests/fixtures/baldurs_gate_city_source.json"
        fixture = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(fixture["areas"]), audit.CITY_AREA_IDS)
        self.assertEqual(fixture["counts"]["classifications"], {"interior": 196, "exterior": 9, "underground": 7})
        self.assertFalse(fixture["originalParityEstablished"])
        self.assertIn("AR0900", fixture["excludedAreaResources"])
        self.assertLess(path.stat().st_size, 4 * 1024 * 1024)

        def assertNoDump(value):
            if isinstance(value, dict):
                self.assertTrue({"compiled_text", "state_triggers", "transition_triggers", "raw"}.isdisjoint(value))
                for child in value.values():
                    assertNoDump(child)
            elif isinstance(value, list):
                for child in value:
                    assertNoDump(child)

        assertNoDump(fixture)
        for area in fixture["areas"].values():
            raster = area["searchMap"]
            self.assertEqual(len(raster["terrainRowsRle"]), raster["height"])
            for row in raster["terrainRowsRle"]:
                self.assertEqual(len(row) % 2, 0)
                self.assertEqual(sum(row[::2]), raster["width"])
                self.assertTrue(all(length > 0 for length in row[::2]))
            for region in area["regions"]:
                if region["destination"]:
                    self.assertIn(region["destination"], fixture["areas"])
                    self.assertIsNotNone(region["destinationPosition"])
        boundary = [row for row in fixture["worldMapLinks"] if row["outsideCity"]]
        self.assertEqual([(row["source"], row["destination"]) for row in boundary], [("AR0800", "AR0900")])
        self.assertTrue(all(row["sourcePosition"] is not None for row in fixture["worldMapLinks"]))

    def testCityFixedInventoryAndStoresHaveFactualItemMetadata(self):
        fixture = json.loads(
            (MODULE_PATH.parents[1] / "tests/fixtures/baldurs_gate_city_source.json").read_text(encoding="utf-8")
        )
        referenced = {
            row["item"]
            for area in fixture["areas"].values()
            for container in area["containers"]
            for row in container["items"]
        }
        referenced.update(row["item"] for creature in fixture["creatures"].values() for row in creature["items"])
        missing = {row["resource"] for row in fixture["unresolved"]}
        self.assertTrue(
            all(name in audit.NONE_REFS or name in fixture["items"] or name + ".ITM" in missing for name in referenced)
        )
        for store in fixture["stores"].values():
            self.assertTrue(all(row["item"] not in {"SW1H43", "SW1H46", "SW1H48"} for row in store["stock"]))
            self.assertTrue(
                all(row["item"] in fixture["items"] or row["item"] + ".ITM" in missing for row in store["stock"])
            )
        for item in fixture["items"].values():
            self.assertTrue(
                {"displayName", "unidentifiedName", "price", "lore", "flags", "stack_size", "item_type"} <= item.keys()
            )
            self.assertEqual(len(item["sha256"]), 64)

    def testKeyBiffLocatorAndOverridePrecedence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installation(root, [("ACTOR", "CRE", creature())])
            (root / "override").mkdir()
            (root / "override" / "actor.cre").write_bytes(creature("OTHER"))
            index = audit.ResourceIndex(root)
            self.assertEqual(audit.parseCreature(index.read("ACTOR", "CRE", "base")[0])[0]["dialogue"], "QUEST")
            data, origin = index.read("ACTOR", "CRE")
            self.assertEqual(audit.parseCreature(data)[0]["dialogue"], "OTHER")
            self.assertEqual(origin["source"], "override")

    def testMalformedBiffPayloadAndUnsafeKeyPath(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installation(root, [("ACTOR", "CRE", creature())])
            path = root / "data" / "test.bif"
            data = bytearray(path.read_bytes())
            putNumber(data, 24, len(data) + 1)
            path.write_bytes(data)
            with self.assertRaisesRegex(audit.AuditError, "outside archive"):
                audit.ResourceIndex(root).read("ACTOR", "CRE")
            with self.assertRaisesRegex(audit.AuditError, "unsafe"):
                audit.safePath(root, "../outside.bif")

    def testTalkTableUtf8AndMalformedSpan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dialog.tlk"
            path.write_bytes(talkTable(["Zażółć test"]))
            talk = audit.TalkTable(path)
            self.assertEqual(talk.get(0)["text"], "Zażółć test")
            self.assertTrue(talk.get(50)["unresolved"])
            data = bytearray(path.read_bytes())
            putNumber(data, 18 + 22, 10000)
            path.write_bytes(data)
            with self.assertRaisesRegex(audit.AuditError, "outside text"):
                audit.TalkTable(path).get(0)

    def testAuditDerivesDialogueAndExcludesChapterSix(self):
        area = emptyArea()
        putNumber(area, 0x54, len(area))
        putNumber(area, 0x58, 1, "H")
        offset = len(area)
        area.extend(bytes(0x110))
        putText(area, offset + 0x80, "ACTOR")
        putNumber(area, 0x5C, len(area))
        putNumber(area, 0x5A, 1, "H")
        offset = len(area)
        area.extend(bytes(0xC4))
        putNumber(area, offset + 0x20, 2, "H")
        putText(area, offset + 0x38, "AR2608")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installation(
                root, [("AR2600", "ARE", bytes(area)), ("ACTOR", "CRE", creature()), ("QUEST", "DLG", dialogue())]
            )
            report = audit.auditInstallation(root)
            resources = report["views"]["base"]["resources"]
            self.assertIn("QUEST.DLG", resources)
            self.assertNotIn("FIREBE.DLG", resources)
            self.assertNotIn("AR2608.ARE", resources)
            self.assertEqual(report["views"]["base"]["excluded_areas"][0]["resource"], "AR2608.ARE")
            self.assertFalse(report["original_parity_established"])
            self.assertEqual(resources["QUEST.DLG"]["parsed"]["states"][0]["text_tlk"]["text"], "synthetic NPC")
            json.dumps(report)

    def testAuditRecordsOverrideDifferencesAndMissingReferences(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            area = emptyArea()
            putText(area, 0x94, "MISSING")
            installation(root, [("AR2600", "ARE", bytes(area))])
            (root / "override").mkdir()
            putNumber(area, 0x14, 1)
            (root / "override" / "AR2600.ARE").write_bytes(area)
            report = audit.auditInstallation(root)
            self.assertEqual(report["base_effective_differences"], ["AR2600.ARE"])
            self.assertEqual(report["views"]["base"]["unresolved"][0]["resource"], "MISSING.BCS")
            self.assertEqual(report["views"]["effective"]["resources"]["AR2600.ARE"]["origin"]["source"], "override")
            self.assertFalse(report["all_interactions_accounted_for"])

    def testRejectUnsupportedRootAndInvalidLanguage(self):
        with self.assertRaisesRegex(audit.AuditError, "AR2600"):
            audit.auditInstallation("unused", area="AR2626")
        with self.assertRaisesRegex(audit.AuditError, "locale"):
            audit.auditInstallation("unused", language="../../dialog")

    def testAuditedShopRowsPreserveFiniteStockAndBundles(self):
        root = MODULE_PATH.parents[1]
        fixture = json.loads((root / "tests/fixtures/candlekeep_shop_stock.json").read_text(encoding="utf-8"))
        dialogs = json.loads((root / "res/maps/candlekeep/dialog.json").read_text(encoding="utf-8"))
        config = json.loads((root / "res/maps/candlekeep/config.json").read_text(encoding="utf-8"))
        self.assertFalse(fixture["source"]["originalParityEstablished"])
        for store_id, dialog_id, expected_count in (
            ("INN2616", "winthropDialog", 44),
            ("TEM2601", "templePriestDialog", 4),
        ):
            store = fixture["stores"][store_id]
            rows = json.loads(dialogs[dialog_id]["properties"]["shopEntries"])
            self.assertEqual(len(rows), expected_count)
            self.assertEqual(len({row["id"] for row in rows}), len(rows))
            source = {row["id"]: row for row in store["stock"] if not row["excludedEnhancedEditionAddition"]}
            self.assertEqual({row["id"] for row in rows}, set(source))
            for row in rows:
                item = source[row["id"]]
                self.assertEqual(row["limit"], 0 if item["infinite"] else item["stock"])
                self.assertEqual(row["quantity"], max(1, item["charges"][0]))
                expected_price = 1 if item["itemType"] in {5, 14, 31} else max(1, item["basePrice"] * 150 // 100)
                self.assertEqual(row["price"], expected_price)
                properties = config[row["itemId"]]["properties"]
                self.assertEqual(properties["plugin_candlekeepOriginalResource"], row["id"])
                self.assertEqual(properties["plugin_candlekeepSellPrice"], item["basePrice"] * 50 // 100)
                self.assertEqual(properties["plugin_candlekeepQuantity"], row["quantity"])
        inn = json.loads(dialogs["winthropDialog"]["properties"]["shopEntries"])
        self.assertEqual(next(row for row in inn if row["id"] == "BOLT01")["itemId"], "candlekeepBolts")
        self.assertTrue({"SW1H48", "SW1H43", "SW1H46"}.isdisjoint(row["id"] for row in inn))
        self.assertEqual(sum(row["id"].startswith("SHLD") for row in inn), 12)

    def testAuditedDrinksAndTempleServices(self):
        root = MODULE_PATH.parents[1]
        dialogs = json.loads((root / "res/maps/candlekeep/dialog.json").read_text(encoding="utf-8"))
        drinks = json.loads(dialogs["winthropDialog"]["properties"]["drinkEntries"])
        self.assertEqual(
            [(row["label"], row["price"]) for row in drinks],
            [("Blood Wine", 8), ("Firewine", 1), ("Mead", 4), ("Bitter Black Ale", 1), ("Arabellan Dry Wine", 2)],
        )
        services = json.loads(dialogs["templePriestDialog"]["properties"]["serviceEntries"])
        self.assertEqual(
            [(row["id"], row["price"]) for row in services],
            [("SPPR103", 50), ("SPPR303", 200), ("SPPR307", 500), ("SPPR401", 100), ("SPPR212", 150), ("SPPR504", 750)],
        )

    def testShopShieldsAndHelmetFitExistingNativeSlots(self):
        root = MODULE_PATH.parents[1]
        config = json.loads((root / "res/maps/candlekeep/config.json").read_text(encoding="utf-8"))
        fixture = json.loads((root / "tests/fixtures/candlekeep_shop_stock.json").read_text(encoding="utf-8"))
        slots = json.loads((root / "res/config/slots.json").read_text(encoding="utf-8"))
        slots = slots["slotConfiguration"]["properties"]["configuration"]
        armors = json.loads((root / "res/config/armors.json").read_text(encoding="utf-8"))
        equipment_count = 0
        for source_id, conversion in fixture["nativeConversions"].items():
            if not (source_id.startswith("SHLD") or source_id == "HELM01"):
                continue
            item = config[conversion["itemId"]]
            slot = "1" if source_id.startswith("SHLD") else "2"
            self.assertIn(item["class"], slots[slot]["properties"]["types"])
            self.assertEqual(conversion["slot"], slot)
            self.assertEqual(item["properties"]["bonus"], armors[conversion["bonusTemplate"]]["properties"]["bonus"])
            self.assertNotIn("unavailable", item["properties"]["description"])
            animation = root / "res" / (item["properties"]["animation"] + ".png")
            self.assertTrue(animation.is_file(), str(animation))
            equipment_count += 1
        self.assertEqual(equipment_count, 13)

    def testFixedNpcItemsUseRealCreatureInventories(self):
        root = MODULE_PATH.parents[1]
        config = json.loads((root / "res/maps/candlekeep/config.json").read_text(encoding="utf-8"))
        fixture = json.loads((root / "tests/fixtures/candlekeep_shop_stock.json").read_text(encoding="utf-8"))
        expected = {
            "phlydia": {
                "candlekeepGoldNecklace": 1,
                "candlekeepLynxEyeGem": 1,
                "candlekeepDagger": 1,
                "candlekeepPhlydiaRobe": 1,
            },
            "fuller": {"candlekeepDaggerPlusOne": 1, "candlekeepStockStaf01": 1, "candlekeepFullerPlateArmor": 1},
            "clinicPriest": {"candlekeepHealingPotion": 2},
        }
        pocket_actors = {
            actor_id
            for actor_id, entry in config.items()
            if entry.get("properties", {}).get("plugin_candlekeepPocketItems")
        }
        self.assertEqual(pocket_actors, set(expected))
        for actor_id, counts in expected.items():
            properties = config[actor_id]["properties"]
            actual = Counter(item["ref"] for item in properties.get("items", []))
            self.assertEqual(actual, counts, actor_id)
            self.assertEqual(fixture["npcPossessions"][actor_id]["nativeItems"], counts)
            for item_id in counts:
                self.assertIn(item_id, config)
            self.assertTrue(set(properties["plugin_candlekeepPocketItems"].split(",")).issubset(actual))
        self.assertEqual(fixture["npcPossessions"]["clinicPriest"]["sourceItems"], {"POTN08": 2})
        for actor_id in ("thurston", "lovey", "watcher"):
            self.assertEqual(config[actor_id]["properties"]["plugin_candlekeepPocketItems"], "")
        self.assertEqual(config["candlekeepFullerPlateArmor"]["ref"], "PlateArmor")
        self.assertEqual(config["candlekeepPhlydiaRobe"]["ref"], "Robe")
        self.assertIn("fire resistance", config["candlekeepPhlydiaRobe"]["properties"]["description"])

    def testNativeTrainingOpponentsHaveNoDamage(self):
        root = MODULE_PATH.parents[1]
        config = json.loads((root / "res/maps/candlekeep/config.json").read_text(encoding="utf-8"))
        stats = config["candlekeepTrainingFoe"]["properties"]["baseStats"]["properties"]
        self.assertEqual((stats["dmgMin"], stats["dmgMax"]), (0, 0))
        self.assertEqual(config["candlekeepPracticeFoe"]["ref"], "candlekeepTrainingFoe")

    def testAllSourceContainersRemainSeparateWithFixedContents(self):
        root = MODULE_PATH.parents[1]
        config = json.loads((root / "res/maps/candlekeep/config.json").read_text(encoding="utf-8"))
        dialogs = json.loads((root / "res/maps/candlekeep/dialog.json").read_text(encoding="utf-8"))
        fixture = json.loads((root / "tests/fixtures/candlekeep_shop_stock.json").read_text(encoding="utf-8"))
        containers = {key: entry for key, entry in config.items() if entry.get("class") == "CandlekeepContainer"}
        self.assertEqual(len(containers), 37)
        source = fixture["containers"]
        self.assertEqual(set(containers), set(source))
        self.assertEqual(
            Counter(row["area"] for row in source.values()),
            {
                "AR2600": 5,
                "AR2602": 5,
                "AR2605": 1,
                "AR2606": 3,
                "AR2607": 1,
                "AR2616": 2,
                "AR2617": 5,
                "AR2618": 5,
                "AR2643": 10,
            },
        )
        self.assertEqual(sum(row["gold"] for row in source.values()), 175)
        self.assertEqual(sum(bool(row["flags"] & 1) for row in source.values()), 13)
        self.assertEqual(len({(row["area"], row["container"]) for row in source.values()}), 37)
        for actor_id, row in source.items():
            properties = containers[actor_id]["properties"]
            self.assertEqual(properties["gold"], row["gold"], actor_id)
            self.assertEqual(properties["contents"].split(",") if properties["contents"] else [], row["nativeItems"])
            self.assertEqual(properties["locked"], bool(row["flags"] & 1), actor_id)
            self.assertEqual(properties["plugin_candlekeepSourceContainer"], f"{row['area']}#{row['container']}")
            active_script = row["script"] if row["trapped"] else ""
            count = 1 if active_script == "ACT10" else 2 if active_script in {"ACT11", "ACT11NOB"} else 0
            self.assertEqual(properties["plugin_candlekeepGuardCount"], count)
            self.assertEqual(properties["alwaysGuard"], active_script == "ACT10")
            if properties["locked"]:
                tier = 12 if row["lockDifficulty"] <= 20 else 16 if row["lockDifficulty"] <= 40 else 18
                self.assertEqual(properties["lockAgility"], tier)
                self.assertEqual(properties["forceStrength"], 14 if tier == 18 else 12)
            dialog = dialogs[actor_id + "Dialog"]["properties"]
            self.assertEqual(dialog["actorId"], actor_id)
            self.assertEqual(len(row["areaSha256"]), 64)
        self.assertEqual(source["innClarityDrawer"]["gold"], 36)
        self.assertEqual(source["innJewelryDrawer"]["gold"], 86)
        self.assertEqual(source["innSilverDrawer"]["nativeItems"], ["candlekeepSilverNecklace"])
        self.assertEqual(source["priestCrates"]["nativeItems"], ["candlekeepWarhammer"])
        self.assertTrue(all(source[f"trainingChest{i}"]["nativeItems"] == [] for i in range(1, 11)))

    def testNeutralLootSalePricesUseAuditedStoreMarkup(self):
        root = MODULE_PATH.parents[1]
        config = json.loads((root / "res/maps/candlekeep/config.json").read_text(encoding="utf-8"))
        fixture = json.loads((root / "tests/fixtures/candlekeep_shop_stock.json").read_text(encoding="utf-8"))
        expected = {
            "candlekeepDaggerPlusOne": ("DAGG02", 300, 150),
            "candlekeepGoldNecklace": ("AMUL10", 60, 30),
            "candlekeepSilverNecklace": ("AMUL09", 10, 5),
            "candlekeepSilverRing": ("RING11", 5, 2),
            "candlekeepFlamedanceRing": ("RING17", 125, 62),
            "candlekeepClarityPotion": ("POTN21", 700, 350),
        }
        for item_id, (resource, base_price, sell_price) in expected.items():
            with self.subTest(item_id=item_id):
                self.assertEqual(config[item_id]["properties"]["plugin_candlekeepSellPrice"], sell_price)
                source = fixture["lootNeutralSalePrices"][item_id]
                self.assertEqual(source["resource"], resource)
                self.assertEqual(source["basePrice"], base_price)
                self.assertEqual(source["buyMarkup"], 50)
                self.assertEqual(source["neutralSellPrice"], base_price * source["buyMarkup"] // 100)
                self.assertEqual(len(source["itemSha256"]), 64)


if __name__ == "__main__":
    unittest.main()
