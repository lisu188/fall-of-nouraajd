# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded diagnostic-reader contracts; these tests provide no native survival evidence."""

import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests import test_octobogz_mcp as hunt


class OctobogzEarlyTraceTest(unittest.TestCase):
    def record(self, seq, turn, event="movement", **fields):
        return {"seq": seq, "map": "nouraajd", "turn": turn, "event": event, **fields}

    def write(self, path, records, mode="w"):
        with path.open(mode, encoding="utf-8") as stream:
            for record in records:
                stream.write(json.dumps(record) + "\n")

    def testCollectorRetainsEarlyActualOrderAndPlayerEventsWithoutArbitraryPayloads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.jsonl"
            player = {"name": "hero", "typeId": "Sorcerer", "isPlayer": True}
            self.write(
                path,
                [
                    self.record(
                        1, 0, object={"name": "npcB", "typeId": "Pritz", "isPlayer": False}, to={"x": 2, "y": 1, "z": 0}
                    ),
                    self.record(2, 0, object=player, to={"x": 1, "y": 1, "z": 0}, secret="MUST_NOT_APPEAR"),
                    self.record(3, 94, "experience_changed", actor=player, before=750, after=1250, delta=500),
                    self.record(
                        4,
                        95,
                        "inventory_added",
                        owner=player,
                        item={"name": "earned", "typeId": "FountainOfYouthTonic"},
                    ),
                    self.record(5, 96, object=player),
                ],
            )
            collector = hunt.EarlyNativeTraceDiagnostics()
            collector.capture(path)
            report = collector.report("before Rolf", "Sorcerer")
            self.assertEqual(["npcB", "hero"], [row["object"]["name"] for row in report["movements"]])
            self.assertEqual(
                ["experience_changed", "inventory_added"], [row["event"] for row in report["playerEvents"]]
            )
            self.assertEqual([0, 94, 95], [row["turn"] for row in report["turns"]])
            self.assertEqual("observedTracePrefix", report["coverage"])
            self.assertFalse(report["nativeAcceptance"])
            self.assertNotIn("MUST_NOT_APPEAR", json.dumps(report))

    def testCollectorReadsIncrementallyAndDeduplicatesAvailableRotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.jsonl"
            self.write(path, [self.record(1, 0), self.record(2, 1)])
            collector = hunt.EarlyNativeTraceDiagnostics()
            collector.capture(path)
            first_bytes = collector.read_bytes
            collector.capture(path)
            self.assertEqual(first_bytes, collector.read_bytes)
            Path(str(path) + ".1").write_bytes(path.read_bytes())
            self.write(path, [self.record(3, 2)])
            collector.capture(path)
            self.assertEqual([1, 2, 3], [row["seq"] for row in collector.report("checkpoint", "Warrior")["movements"]])
            self.assertEqual([], collector.issues)

    def testUnavailableMissingPrefixAndMalformedEvidenceAreExplicitlyPartial(self):
        collector = hunt.EarlyNativeTraceDiagnostics()
        collector.capture(None)
        self.assertIn("traceUnavailable", collector.report("entry", "Sorcerer")["issues"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.jsonl"
            self.write(path, [self.record(10, 3), self.record(12, 4)])
            with path.open("a", encoding="utf-8") as stream:
                stream.write("not JSON\n")
            collector = hunt.EarlyNativeTraceDiagnostics()
            collector.capture(path)
            report = collector.report("available only", "Sorcerer")
            self.assertEqual("partialTraceOnly", report["coverage"])
            self.assertTrue({"missingPrefix", "sequenceGap", "malformedRecord"} <= set(report["issues"]))

    def testReadDetailsAndPrintedOutputRemainBounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.jsonl"
            self.write(
                path, [self.record(i + 1, i % 95, object={"name": "x" * 300, "isPlayer": True}) for i in range(300)]
            )
            collector = hunt.EarlyNativeTraceDiagnostics(read_limit=4096, output_limit=2048)
            for _ in range(8):
                collector.capture(path)
            report = collector.report("capped", "Sorcerer")
            self.assertLessEqual(collector.read_bytes, 4096)
            self.assertLessEqual(len(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()), 2048)
            self.assertIn("readLimit", report["issues"])
            self.assertTrue(report["detailsTruncated"])

    def testPendingChunksContinueWithoutFileChangesAndReportsDoNotDuplicateFacts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.jsonl"
            self.write(
                path, [self.record(i + 1, i % 95, object={"name": "actor", "isPlayer": False}) for i in range(900)]
            )
            collector = hunt.EarlyNativeTraceDiagnostics()
            collector.capture(path)
            first_seq = collector.seq
            self.assertLess(first_seq, 900)
            first = collector.report("first available", "Sorcerer")
            for _ in range(4):
                collector.capture(path)
            self.assertEqual(900, collector.seq)
            second = collector.report("next available", "Sorcerer")
            self.assertFalse({row["seq"] for row in first["movements"]} & {row["seq"] for row in second["movements"]})
            for _ in range(12):
                collector.report("bounded checkpoint", "Sorcerer")
            self.assertLessEqual(collector.emitted_bytes, collector.output_limit)

    def testRotatedBacklogIsConsumedBeforeNewerActiveTraceCanCompleteTheWindow(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.jsonl"
            older = Path(str(path) + ".1")
            player = {"name": "hero", "typeId": "Sorcerer", "isPlayer": True}
            records = [
                self.record(i + 1, i % 95, object={"name": "actualActor", "isPlayer": False}) for i in range(900)
            ]
            records[-1] = self.record(900, 94, "experience_changed", actor=player, before=750, after=1250, delta=500)
            self.write(older, records)
            self.assertGreater(older.stat().st_size, 65536)
            self.write(path, [self.record(901, 96, object=player)])
            collector = hunt.EarlyNativeTraceDiagnostics()
            collector.capture(path)
            self.assertFalse(collector.complete, "A newer late-turn record cannot overtake the older unread prefix")
            self.assertLess(collector.seq, 900)
            self.assertLessEqual(collector.read_bytes, 65536)
            for _ in range(4):
                before = collector.read_bytes
                collector.capture(path)
                self.assertLessEqual(collector.read_bytes - before, 65536)
            self.assertTrue(collector.complete)
            self.assertEqual(901, collector.seq)
            self.assertEqual([], collector.issues)
            report = collector.report("all available early records", "Sorcerer")
            self.assertEqual(900, report["playerEvents"][0]["seq"])
            self.assertEqual(500, report["playerEvents"][0]["delta"])

    def testActualNativeRewardRecipientAndDefeatedFieldsRetainTheFirstCombatReward(self):
        collector = hunt.EarlyNativeTraceDiagnostics()
        player = {"name": "hero", "typeId": "Sorcerer", "isPlayer": True}
        enemy = {"name": "actualPritz", "typeId": "Pritz", "isPlayer": False}
        collector.accept(
            self.record(
                1,
                17,
                "reward_granted",
                recipient=player,
                defeated=enemy,
                scale=2,
                ownedGold=0,
                items=[{"name": "earnedTonic", "typeId": "FountainOfYouthTonic"}],
            )
        )
        collector.accept(
            self.record(2, 17, "combat_finished", attacker=player, opponents=[enemy], survivor=player, outcome=1)
        )
        report = collector.report("first actual combat", "Sorcerer")
        self.assertEqual(["reward_granted", "combat_finished"], [row["event"] for row in report["playerEvents"]])
        self.assertEqual(player, report["playerEvents"][0]["recipient"])
        self.assertEqual(enemy, report["playerEvents"][0]["defeated"])
        self.assertEqual(2, report["playerEvents"][0]["scale"])
        self.assertEqual(0, report["playerEvents"][0]["ownedGold"])
        self.assertEqual("FountainOfYouthTonic", report["playerEvents"][0]["items"][0]["typeId"])
        self.assertEqual(1, report["playerEvents"][1]["outcome"])

    def testDiagnosticHookUsesOnlyExistingTraceAndDoesNotReplaceOriginalPumpErrors(self):
        fixture = hunt.OctobogzMcpWalkthroughTest(methodName="runTest")
        original = RuntimeError("original engine failure")
        fixture.engine = Mock(side_effect=original)
        fixture.captureEarlyNativeTrace = Mock()
        with self.assertRaises(RuntimeError) as caught:
            fixture.pump()
        self.assertIs(original, caught.exception)
        fixture.captureEarlyNativeTrace.assert_not_called()
        tree = ast.parse(Path(hunt.__file__).read_text(encoding="utf-8"))
        helper = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "EarlyNativeTraceDiagnostics"
        )
        calls = {
            node.func.attr
            for node in ast.walk(helper)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertFalse({"engine", "call", "moveTo", "setTarget", "randint", "sleep", "run"} & calls)

    def testUnavailableTraceAndFailedDiagnosticOutputDoNotTouchTheEngineOrRaise(self):
        fixture = hunt.OctobogzMcpWalkthroughTest(methodName="runTest")
        fixture.nativeHuntTracePath = Mock(side_effect=FileNotFoundError("trace unavailable"))
        fixture.engine, fixture.call = Mock(), Mock()
        with patch("builtins.print", side_effect=OSError("diagnostic output unavailable")):
            self.assertIsNone(fixture.captureEarlyNativeTrace("checkpoint"))
        fixture.engine.assert_not_called()
        fixture.call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
