# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from scripts import audit_baldurs_gate_city_patch as audit


def sampleGraph():
    edge = {
        "flags": 12,
        "text_strref": None,
        "journal_strref": None,
        "action": 'Mark("A B",1)',
        "trigger": None,
        "next_dialogue": "",
        "next_state": None,
    }
    return {
        "headerFlags": None,
        "states": [
            {
                "text_strref": 10,
                "trigger": None,
                "triggerPoolIndex": None,
                "first_transition": 0,
                "transition_count": 1,
            },
            {
                "text_strref": 20,
                "trigger": "True()",
                "triggerPoolIndex": 0,
                "first_transition": 1,
                "transition_count": 1,
            },
        ],
        "transitions": [dict(edge), dict(edge)],
    }


class CityPatchAuditTest(unittest.TestCase):
    def testEntryPriorityAndHostileInterruptFlagsSurviveIdenticalTriggerText(self):
        def payload(header, triggers):
            pool = header + 32
            data = bytearray(pool + 16)
            struct.pack_into("<8s10I", data, 0, b"DLG V1.0", 2, header, 0, pool, pool, 2, pool, 0, pool, 0)
            if header == 52:
                struct.pack_into("<I", data, 48, 2)
            for i, trigger in enumerate(triggers):
                struct.pack_into("<4I", data, header + i * 16, i, 0, 0, trigger)
                struct.pack_into("<2I", data, pool + i * 8, len(data), 6)
                data.extend(b"True()")
            return bytes(data)

        classic, enhanced = payload(48, [0, 1]), payload(52, [1, 0])
        index = Mock()
        index.read.return_value = (enhanced, {})
        report = audit.compareResource("SAMPLE.DLG", classic, index, {"sha256": audit.reader.sha256(enhanced)})
        self.assertEqual(report["dialogue"]["headerFlags"], [None, 2])
        self.assertEqual(
            report["dialogue"]["changedStates"],
            [{"state": 0, "fields": ["triggerPoolIndex"]}, {"state": 1, "fields": ["triggerPoolIndex"]}],
        )

    def testWhitespaceBetweenTokensAndPoolOrderDoNotChangeStateChoices(self):
        old = sampleGraph()
        new = copy.deepcopy(old)
        new["transitions"][1]["action"] = '\tMark  ( "A B" ,  1 )\r\n'
        new["actions"] = ["unused", "pool entries are dereferenced by the binary reader"]
        self.assertEqual(audit.compareDialogue(old, new)["changedStates"], [])

    def testQuotedWhitespaceTokenBoundariesOrderingAndEmptyTriggersAreDistinct(self):
        self.assertNotEqual(audit.scriptTokens('"A B"'), audit.scriptTokens('"AB"'))
        self.assertNotEqual(audit.scriptTokens("A B()"), audit.scriptTokens("AB()"))
        self.assertNotEqual(audit.scriptTokens("A() B()"), audit.scriptTokens("B() A()"))
        self.assertNotEqual(audit.scriptTokens(None), audit.scriptTokens(""))
        self.assertEqual(audit.scriptTokens(r'Name("A\" B")'), ["Name", "(", r'"A\" B"', ")"])
        with self.assertRaises(audit.reader.AuditError):
            audit.scriptTokens('Name("unfinished)')

    def testInsertedChoiceLeavesSubsequentStatesIdentifiable(self):
        old = sampleGraph()
        new = copy.deepcopy(old)
        new["transitions"].insert(0, dict(new["transitions"][0], flags=8, action=None))
        new["states"][0]["transition_count"] = 2
        new["states"][1]["first_transition"] = 2
        new["states"].append(dict(new["states"][1], transition_count=0))
        result = audit.compareDialogue(old, new)
        self.assertEqual(
            result["changedStates"],
            [
                {"state": 0, "choiceCounts": [1, 2], "changedChoices": [{"slot": 0, "fields": ["flags", "action"]}]},
                {"state": 2, "presentIn": "ee"},
            ],
        )
        self.assertNotIn("Mark", json.dumps(result))

    def testReplyJournalTargetAndEntryTriggerAreCompared(self):
        old = sampleGraph()
        new = copy.deepcopy(old)
        new["states"][1]["trigger"] = "False()"
        new["transitions"][1].update(text_strref=5, journal_strref=12, next_dialogue="OTHER", next_state=1)
        self.assertEqual(
            audit.compareDialogue(old, new)["changedStates"],
            [
                {
                    "state": 1,
                    "fields": ["trigger"],
                    "changedChoices": [
                        {"slot": 0, "fields": ["text_strref", "journal_strref", "next_dialogue", "next_state"]}
                    ],
                }
            ],
        )

    def testEeArchiveAndBothFingerprintBoundaries(self):
        index = Mock()
        index.read.return_value = (b"base", {})
        reference = {"sha256": audit.reader.sha256(b"base")}
        row = audit.compareResource("TEST.BCS", b"classic", index, reference)
        index.read.assert_called_once_with("TEST", "BCS", "base")
        self.assertEqual(row["comparison"], "fingerprintsOnly")
        self.assertFalse(row["byteEqual"])
        with self.assertRaisesRegex(audit.reader.AuditError, "differs from the city source"):
            audit.compareResource("TEST.BCS", b"classic", index, {"sha256": "wrong"})
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            member = path / "test.bcs"
            member.write_bytes(b"classic")
            with self.assertRaisesRegex(audit.reader.AuditError, "city patch member set"):
                audit.readCityMembers(path, {"TEST.BCS": reference})
            with self.assertRaisesRegex(audit.reader.AuditError, "international BG1"):
                audit.buildAudit(member, path, path)

    def testCheckedInPatchCoversThePinnedCityMembersWithoutAwardingParity(self):
        report = json.loads((audit.ROOT / "tests/fixtures/baldurs_gate_city_classic_patch.json").read_bytes())
        rows = report["resources"]
        pins = {name: row["classicSha256"] for name, row in rows.items()}
        self.assertEqual(
            audit.reader.sha256(json.dumps(pins, sort_keys=True, separators=(",", ":")).encode()),
            audit.CITY_MEMBERS_SHA256,
        )
        sources = audit.cityReferences(json.loads(audit.CITY_SOURCE.read_bytes()))
        for name, row in rows.items():
            self.assertEqual(row["eeSha256"], sources[name]["sha256"], name)
            self.assertEqual(row["byteEqual"], row["eeSha256"] == row["classicSha256"], name)
        self.assertFalse(report["originalParityEstablished"])
        self.assertFalse(report["fullOriginalInstallationVerified"])
        self.assertEqual(report["classicPatchSha256"], audit.PATCH_SHA256)
        self.assertEqual(rows["LOTHAN.DLG"]["dialogue"]["classicCounts"], [16, 24])
        self.assertEqual(rows["LOTHAN.DLG"]["dialogue"]["eeCounts"], [18, 27])
        diviner = rows["DIVINE.DLG"]["dialogue"]["changedStates"][0]
        self.assertEqual(diviner, {"state": 0, "changedChoices": [{"slot": 1, "fields": ["flags", "trigger"]}]})
        self.assertEqual(rows["FENTEN.DLG"]["dialogue"]["classicCounts"], [6, 6])
        self.assertEqual(rows["FENTEN.DLG"]["dialogue"]["eeCounts"], [6, 9])
        self.assertIn("actors", rows["AR0111.ARE"]["changedParsedFields"])
        self.assertTrue(rows["BENJY.CRE"]["byteEqual"])
        self.assertEqual(rows["SAREVOK.BCS"]["comparison"], "fingerprintsOnly")
