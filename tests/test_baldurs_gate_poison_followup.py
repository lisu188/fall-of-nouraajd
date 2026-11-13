# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Retained source facts and required obligations; no native or original-game credit."""

import ast
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import build_baldurs_gate_city_ledger as ledger_builder
from scripts.build_baldurs_gate_city_ledger import buildLedger, validateLedger
from scripts.build_baldurs_gate_poison_ledger import POISON_PATH, requiredPoisonIds
from scripts.build_baldurs_gate_poison_followup_ledger import (
    FOLLOWUP_PATH,
    buildFollowupObligations,
    requiredFollowupIds,
    sourceInventory,
)

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class BaldursGatePoisonFollowupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = read(FOLLOWUP_PATH)
        cls.poison = read(POISON_PATH)
        cls.rows = buildFollowupObligations(cls.document)

    def testAllFortyOneFactsRemainIndependentRequiredPlannedRecords(self):
        expected = {"TENYA2.DLG:state" + str(index) for index in range(12)}
        expected.update("TENYA2.DLG:edge" + str(index) for index in range(23))
        expected.update(
            (
                "BDMAREK.SPL:header",
                "BDMAREK.SPL:ability0",
                "BDMAREK.SPL:effect0",
                "BDMAREK.SPL:effect1",
                "GTIMES.IDS:ONE_DAY",
                "GTIMES.IDS:TEN_DAYS",
            )
        )
        self.assertEqual(41, len(expected))
        self.assertEqual(expected, requiredFollowupIds(self.document))
        self.assertEqual(expected, {row["id"] for row in self.rows})
        self.assertFalse(expected & requiredPoisonIds(self.poison))
        for row in self.rows:
            self.assertEqual({"status": "planned", "targets": [], "callbacks": []}, row["implementation"])
            self.assertEqual("pending", row["testStatus"]["native"])
            self.assertEqual("not established", row["testStatus"]["coverage"])
            self.assertEqual("pending", row["testStatus"]["original"])
            self.assertEqual("pending", row["testStatus"]["owner"])

    def testEvidenceResolvesToRetainedRecordAndWholeResourceFingerprint(self):
        for row in self.rows:
            self.assertEqual(1, len(row["evidence"]))
            proof = row["evidence"][0]
            self.assertEqual(FOLLOWUP_PATH, proof["fixture"])
            value = self.document
            for part in proof["pointer"].lstrip("/").split("/"):
                value = value[int(part)] if isinstance(value, list) else value[part]
            self.assertEqual(row["id"], value["sourceId"])
            group = self.document[proof["pointer"].split("/")[1]]
            self.assertEqual(group["resource"], proof["resource"])
            self.assertEqual(group["sha256"], proof["sha256"])

    def testEveryExistingLedgerRowAndThePriorPoisonInventoryStayExact(self):
        args = (
            read("tests/fixtures/baldurs_gate_city_source.json"),
            read("tests/fixtures/baldurs_gate_city_quests.json"),
            read("res/maps/baldursGate/config.json"),
            (ROOT / "res/maps/baldursGate/script.py").read_text(encoding="utf-8"),
        )
        old = buildLedger(*args, poison=self.poison)
        expanded = buildLedger(*args, poison=self.poison, followup=self.document)
        old_rows = {row["id"]: row for row in old["entries"]}
        new_rows = {row["id"]: row for row in expanded["entries"]}
        self.assertEqual(old_rows, {key: new_rows[key] for key in old_rows})
        self.assertEqual(41, len(new_rows) - len(old_rows))
        self.assertEqual(218, len(requiredPoisonIds(self.poison)))
        self.assertEqual([], validateLedger(expanded))
        self.assertTrue(validateLedger(expanded, require_mapped=True))
        self.assertTrue(validateLedger(expanded, require_acceptance=True))
        self.assertFalse(expanded["acceptanceReady"])
        self.assertFalse(expanded["originalParityEstablished"])
        self.assertEqual(
            old["inputs"], {key: value for key, value in expanded["inputs"].items() if key != FOLLOWUP_PATH}
        )

    def testActualPendingProducerAndCatalogAggregatorRetainEveryNewObligation(self):
        route = ast.parse((ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8"))
        producer = next(
            node
            for node in route.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "PENDING_GAMEPLAY_OBLIGATIONS" for target in node.targets
            )
        )
        catalog = ast.parse((ROOT / "tests/gameplay_branch_catalog.py").read_text(encoding="utf-8"))
        aggregator = next(
            node
            for node in catalog.body
            if isinstance(node, ast.FunctionDef) and node.name == "pendingGameplayObligations"
        )
        rows = self.rows

        class LedgerPath:
            def __truediv__(self, name):
                if name != "tests/fixtures/baldurs_gate_city_ledger.json":
                    raise AssertionError(name)
                return self

            def read_text(self, encoding):
                return json.dumps({"entries": rows})

        def pending(producer_node, aggregator_node):
            scope = {"ROOT": LedgerPath(), "json": json, "MAP": "baldursGate"}
            exec(
                compile(ast.fix_missing_locations(ast.Module(body=[producer_node], type_ignores=[])), "route", "exec"),
                scope,
            )
            module = SimpleNamespace(PENDING_GAMEPLAY_OBLIGATIONS=scope["PENDING_GAMEPLAY_OBLIGATIONS"], CASES=())
            scope.update(routeModules=lambda: (module,), sharedServiceObligations=lambda: {}, PLAYER_CLASSES=())
            exec(
                compile(
                    ast.fix_missing_locations(ast.Module(body=[aggregator_node], type_ignores=[])), "catalog", "exec"
                ),
                scope,
            )
            actual = scope["pendingGameplayObligations"]()
            self.assertEqual({"baldursGate.source." + row["id"] for row in rows}, set(actual))
            self.assertTrue(all(row["implementationStatus"] == "planned" for row in actual.values()))

        pending(deepcopy(producer), deepcopy(aggregator))
        dropped = deepcopy(producer)
        dropped.value = ast.Dict(keys=[], values=[])
        with self.assertRaises(AssertionError):
            pending(dropped, deepcopy(aggregator))
        disconnected = deepcopy(aggregator)
        update = next(
            node
            for node in ast.walk(disconnected)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "update"
        )
        update.args = [ast.Dict(keys=[], values=[])]
        with self.assertRaises(AssertionError):
            pending(deepcopy(producer), disconnected)

    def testCliRequiresTheFollowupAndPassesTheActualDocumentToTheProducer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (
                ledger_builder.SOURCE_PATH,
                ledger_builder.QUEST_PATH,
                ledger_builder.CONFIG_PATH,
                ledger_builder.SCRIPT_PATH,
                ledger_builder.OUTPUT_PATH,
                POISON_PATH,
                FOLLOWUP_PATH,
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            with patch.object(ledger_builder, "ROOT", root), patch.object(
                ledger_builder, "buildLedger", wraps=ledger_builder.buildLedger
            ) as producer, redirect_stdout(io.StringIO()):
                self.assertEqual(0, ledger_builder.main(["--check"]))
                self.assertEqual(1, producer.call_count)
                self.assertEqual(self.document, producer.call_args.kwargs["followup"])
                (root / FOLLOWUP_PATH).unlink()
                with self.assertRaises(FileNotFoundError):
                    ledger_builder.main(["--check"])
                self.assertEqual(1, producer.call_count)

    def testMainRunnerRegistersTheSourceClassExactlyOnceWithoutImportingNativeCode(self):
        def check(tree):
            prefixes = next(
                node.value
                for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "FAST_TEST_PREFIXES" for target in node.targets)
            )
            self.assertEqual(1, ast.literal_eval(prefixes).count("BaldursGatePoisonFollowupTest."))
            imports = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module == "tests.test_baldurs_gate_poison_followup"
            ]
            self.assertEqual(1, len(imports))
            self.assertEqual(
                [("BaldursGatePoisonFollowupTest", "_BaldursGatePoisonFollowupTest")],
                [(row.name, row.asname) for row in imports[0].names],
            )
            wrappers = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef) and node.name == "BaldursGatePoisonFollowupTest"
            ]
            self.assertEqual(1, len(wrappers))
            self.assertEqual(["_BaldursGatePoisonFollowupTest"], [base.id for base in wrappers[0].bases])
            deletions = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Delete)
                and any(
                    isinstance(target, ast.Name) and target.id == "_BaldursGatePoisonFollowupTest"
                    for target in node.targets
                )
            ]
            self.assertEqual(1, len(deletions))
            scope = {"_BaldursGatePoisonFollowupTest": type(self)}
            exec(
                compile(
                    ast.fix_missing_locations(ast.Module(body=[wrappers[0], deletions[0]], type_ignores=[])),
                    "source-registration",
                    "exec",
                ),
                scope,
            )
            self.assertNotIn("_BaldursGatePoisonFollowupTest", scope)
            self.assertEqual(
                unittest.defaultTestLoader.getTestCaseNames(type(self)),
                unittest.defaultTestLoader.getTestCaseNames(scope["BaldursGatePoisonFollowupTest"]),
            )

        actual = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        check(actual)
        changed = deepcopy(actual)
        prefixes = next(
            node.value
            for node in changed.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "FAST_TEST_PREFIXES" for target in node.targets)
        )
        prefixes.elts = [node for node in prefixes.elts if node.value != "BaldursGatePoisonFollowupTest."]
        with self.assertRaises(AssertionError):
            check(changed)

    def testTenyaGiftDepartureAndSelfCreationHostilityRemainDifferent(self):
        dialogue = self.document["dialogue"]
        self.assertEqual([0, 6, 11], dialogue["entryCandidatesInStateOrder"])
        self.assertEqual([1], dialogue["unlinkedWithinRetainedGraph"])
        self.assertFalse(dialogue["states"][1]["hasEntryTrigger"])
        gifts = []
        for edge in dialogue["edges"]:
            if any(call["operation"] == "GiveItemCreate" for call in edge["actions"]):
                gifts.append(edge["index"])
                call = next(call for call in edge["actions"] if call["operation"] == "GiveItemCreate")
                self.assertEqual({"type": "symbol", "value": "LastTalkedToBy"}, call["arguments"][1])
                self.assertEqual("EscapeArea", edge["actions"][-1]["operation"])
        self.assertEqual([10, 11, 12, 13, 18, 19, 20], gifts)
        self.assertEqual(8, sum(path["edges"][-1] in gifts for path in dialogue["syntacticPaths"]))
        self.assertEqual(
            ["Shout", "SetGlobal", "CreateItem", "Enemy"],
            [call["operation"] for call in dialogue["edges"][21]["actions"]],
        )
        self.assertFalse(dialogue["externalEntryOrActorAvailabilityEstablished"])

    def testDistinctTimersAndSelectedSpellTableNeverEstablishWholeCureChain(self):
        self.assertEqual(
            [("PoisonParty", "GLOBAL", "ONE_DAY", 7200), ("PoisonParty2", "GLOBAL", "TEN_DAYS", 72000)],
            [
                (row["name"], row["scope"], row["constant"], row["value"])
                for row in self.document["timerBindings"]["separateNamedTimers"]
            ],
        )
        self.assertTrue(self.document["timerBindings"]["timersAreNotSummed"])
        self.assertFalse(self.document["timerBindings"]["sourceSchedulingEvaluated"])
        self.assertFalse(self.document["timerBindings"]["allBaldurMechanismsPublished"])
        spell = self.document["spell"]
        self.assertEqual([215, 142], [row["opcodeU16"] for row in spell["effects"]])
        self.assertFalse(spell["declared309EffectPresent"])
        self.assertFalse(spell["causalExclusivityEstablished"])
        self.assertFalse(spell["resourceFieldsFollowed"])
        self.assertFalse(self.document["originalParityEstablished"])

    def testChangedFactualOwnershipTimersSpellFieldsOrInventedCreditFailClosed(self):
        mutations = (
            lambda value: value["timerBindings"]["separateNamedTimers"][1].update(name="PoisonParty"),
            lambda value: value["dialogue"]["states"][1].update(hasEntryTrigger=True),
            lambda value: value["dialogue"]["edges"][21]["actions"][2].update(operation="GiveItemCreate"),
            lambda value: value["spell"]["effects"][1].update(parameter2U32=0),
            lambda value: value.update(nativeValidated=True),
        )
        for mutate in mutations:
            changed = deepcopy(self.document)
            mutate(changed)
            with self.assertRaisesRegex(ValueError, "follow-up facts differ"):
                sourceInventory(changed)
        for forbidden in ("raw", "compiledText", "prose", "objectSelectors"):
            changed = deepcopy(self.document)
            changed[forbidden] = "forbidden"
            with self.assertRaisesRegex(ValueError, "raw script"):
                sourceInventory(changed)


if __name__ == "__main__":
    unittest.main()
