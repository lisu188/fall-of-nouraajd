# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Finite source/presentation checks; the protocol oracle is not native replacement or stock proof."""

import ast
from copy import deepcopy
import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests import test_baldurs_gate_city_content as city_content

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "res/maps/baldursGate/script.py"
FACTS = json.loads((ROOT / "tests/fixtures/baldurs_gate_seven_suns_merchants.json").read_text(encoding="utf-8"))
STATES = {row["id"]: row for row in FACTS["states"]}
EDGES = {row["id"]: row for row in FACTS["edges"]}


class MerchantSourceProjection:
    """Source graph/counter oracle only. It never creates, replaces or retires a game actor."""

    def __init__(self, lineage, count=0, *, source_known=True, generic_count=0, globals_=None):
        self.lineage, self.count = lineage, count
        self.source_known, self.generic_count = source_known, generic_count
        self.globals = globals_ if globals_ is not None else {}
        self.state, self.revision, self.edges, self.status, self.reason = -1, 0, [], "closed", None
        self.reveal = False

    def begin(self):
        if not self.source_known and self.generic_count > 0:
            self.status, self.reason = "refused", "legacyCountUnknown"
        elif self.count >= 3:
            self.status, self.reason = "refused", "noAuditedEntry"
        else:
            self.state = (0, 7, 10)[self.count]
            self.count += 1
            self.revision += 1
            self.edges, self.status, self.reason, self.reveal = [], "ready", None, False
        return self.view()

    def view(self):
        ready = self.status == "ready"
        state = STATES.get(self.state)
        return {
            "status": self.status,
            "capabilityVersion": 1,
            "dialogue": "DOPMER",
            "lineage": self.lineage,
            "state": self.state,
            "revision": self.revision,
            "sourceTalkCount": self.count,
            "choices": state["edges"] if ready and state["automaticEdge"] is None else [],
            "automaticEdge": state["automaticEdge"] if ready else None,
            "attackRevealSupported": False,
            "revealRequested": self.reveal,
            "reason": self.reason,
        }

    def advance(self, revision, edge):
        if revision != self.revision or self.status != "ready" or edge not in STATES[self.state]["edges"]:
            raise ValueError("Stale or unreachable source transition")
        row = EDGES[edge]
        self.edges.append(edge)
        for action in row["orderedActions"]:
            name, scope, value = [argument["value"] for argument in action["arguments"]]
            if action["name"] != "SetGlobal" or scope != "GLOBAL":
                raise ValueError("Unexpected source action")
            key = next((key for key in self.globals if key.casefold() == name.casefold()), name)
            self.globals[key] = value
        self.revision += 1
        if row["terminal"]:
            self.status, self.reveal = "closed", row["reveals"]
        else:
            self.state = row["to"]
        return self.view()

    def close(self):
        self.status = "closed"
        return self.view()


class SevenSunsMerchantSourceTest(unittest.TestCase):
    def testAllSourceStatesEdgesAndThirteenPathsStayVisible(self):
        self.assertEqual((14, 24, 13), (len(STATES), len(EDGES), len(FACTS["completePaths"])))
        self.assertEqual(set(range(24)), {edge for path in FACTS["completePaths"] for edge in path["edges"]})
        self.assertEqual(6, sum(path["setsRevealGlobal"] for path in FACTS["completePaths"]))
        self.assertEqual(29, FACTS["privateTextSelection"]["entries"])
        self.assertFalse(FACTS["privateTextSelection"]["fullOriginalTextInFixture"])
        self.assertTrue(FACTS["acceptanceGaps"])

    def testCounterAndOrderedSharedGlobalProjectionForEveryPath(self):
        for path in FACTS["completePaths"]:
            prior = {0: 0, 7: 1, 10: 2}[path["entryState"]]
            shared = {"cHeCkEdSeVeNsUnS": 17, "other": 91}
            projection = MerchantSourceProjection(FACTS["lineages"][0]["id"], prior, globals_=shared)
            projection.begin()
            for edge in path["edges"]:
                projection.advance(projection.revision, edge)
            self.assertEqual(prior + 1, projection.count)
            self.assertEqual(path["edges"], projection.edges)
            self.assertEqual(path["setsRevealGlobal"], projection.reveal)
            self.assertEqual(91, shared["other"])
            self.assertEqual(2 if prior == 0 else 17, shared["cHeCkEdSeVeNsUnS"])
            if projection.reveal:
                self.assertEqual(1, shared["Doppleganger"])
                self.assertEqual(1, shared["Laola"])
            else:
                self.assertNotIn("Doppleganger", shared)

    def testInitiationCountsCancellationAndExhaustedEntryWithoutSaturation(self):
        projection = MerchantSourceProjection(FACTS["lineages"][0]["id"])
        for expected_state, expected_count in ((0, 1), (7, 2), (10, 3)):
            view = projection.begin()
            self.assertEqual((expected_state, expected_count), (view["state"], view["sourceTalkCount"]))
            projection.close()
            self.assertEqual({}, projection.globals)
        before = deepcopy(projection.__dict__)
        refused = projection.begin()
        self.assertEqual(
            ("refused", "noAuditedEntry", 3), (refused["status"], refused["reason"], refused["sourceTalkCount"])
        )
        self.assertEqual(before["revision"], refused["revision"])
        self.assertEqual({}, projection.globals)

    def testLegacyBookkeepingIsNotSilentlyAResetOrAuthoritativeSourceCount(self):
        projection = MerchantSourceProjection(FACTS["lineages"][0]["id"], source_known=False, generic_count=2)
        self.assertEqual("legacyCountUnknown", projection.begin()["reason"])
        self.assertEqual((0, 0, {}), (projection.count, projection.revision, projection.globals))
        explicit = MerchantSourceProjection(FACTS["lineages"][0]["id"], source_known=True, generic_count=11)
        self.assertEqual(0, explicit.begin()["state"])

    def testBuilderPublishesExactProtectedDefinitionAndOnlyFourAllegiances(self):
        path = ROOT / "scripts/build_baldurs_gate_city.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"protectCityData", "definition", "sevenSunsMerchantProperties"}
        ]
        namespace = {"json": json, "CITY_JSON_PREFIX": "city-json:"}
        exec(
            compile(ast.Module(body=functions, type_ignores=[]), "actual-merchant-builder-functions", "exec"), namespace
        )
        for lineage in FACTS["lineages"]:
            self.assertEqual(
                {"sourceAllegiance": 128},
                namespace["sevenSunsMerchantProperties"](lineage["id"], "DOPMER", {"allegiance": 128}),
            )
            with self.assertRaises(ValueError):
                namespace["sevenSunsMerchantProperties"](lineage["id"], "DOPMER", {"allegiance": 255})
        self.assertEqual({}, namespace["sevenSunsMerchantProperties"]("cityAr0601Actor2", "DOPPSM", {}))
        row = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "config"
                and isinstance(target.slice, ast.Constant)
                and target.slice.value == "cityClock"
                for target in node.targets
            )
        )
        keyword = next(value for value in row.value.keywords if value.arg == "sevenSunsMerchantDefinition")
        encoded = eval(compile(ast.Expression(keyword.value), "actual-merchant-definition", "eval"), {"json": json})
        actual = namespace["definition"]("BaldursGateClock", sevenSunsMerchantDefinition=encoded)["properties"][
            "sevenSunsMerchantDefinition"
        ]
        self.assertTrue(actual.startswith("city-json:"))
        self.assertEqual(
            {
                "version": 1,
                "dialogue": "DOPMER",
                "fingerprint": FACTS["dialogueFingerprint"]["sha256"],
                "stockContract": "doppss-native-v1",
            },
            json.loads(actual.removeprefix("city-json:")),
        )
        self.assertLessEqual(len(actual.encode()), 1024)

    def testAuthoritativeBuilderLoadsFiniteStockAndPreservesExistingResources(self):
        path = ROOT / "scripts/build_baldurs_gate_merchant_stock.py"
        spec = importlib.util.spec_from_file_location("preparedMerchantStockCompiler", path)
        compiler = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compiler)
        fixture = ROOT / "tests/fixtures/baldurs_gate_seven_suns_stock.json"
        document = json.loads(fixture.read_text(encoding="utf-8"))
        tree = ast.parse((ROOT / "scripts/build_baldurs_gate_city.py").read_text(encoding="utf-8"))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "compileCity")
        start = next(
            index
            for index, node in enumerate(function.body)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "stock_config" for target in node.targets)
        )
        instructions = function.body[start : start + 3]
        self.assertEqual([ast.Assign, ast.If, ast.Expr], [type(node) for node in instructions])
        original = {"S1-12": {"class": "CItem", "properties": {"unrelated": 91}}}
        namespace = {
            "stockDefinitions": compiler.stockDefinitions,
            "json": json,
            "MERCHANT_STOCK_SOURCE": fixture,
            "config": deepcopy(original),
        }
        exec(
            compile(ast.Module(body=instructions, type_ignores=[]), "actual-builder-stock-integration", "exec"),
            namespace,
        )
        config = namespace["config"]
        self.assertEqual(100, len(config))
        self.assertEqual(original["S1-12"], config["S1-12"])
        self.assertEqual("CCreature", config["citySevenSunsRevealedDoppss"]["class"])
        self.assertEqual("CWeapon", config["citySevenSunsDoppssWeapon"]["class"])
        self.assertEqual(97, sum(key.startswith("citySevenSunsTreasure") for key in config))
        self.assertTrue(all(row["abilitiesPending"] for row in document["items"].values()))
        namespace["config"] = {"citySevenSunsDoppssWeapon": {"class": "unreviewed"}}
        with self.assertRaisesRegex(ValueError, "collide"):
            exec(
                compile(ast.Module(body=instructions, type_ignores=[]), "actual-builder-stock-collision", "exec"),
                namespace,
            )


class SevenSunsMerchantPresentationTest(unittest.TestCase):
    def setUp(self):
        source_patch = patch.object(city_content, "SCRIPT", SOURCE)
        source_patch.start()
        self.addCleanup(source_patch.stop)

    def model(self, lineage=None, capability=True):
        row = lineage or FACTS["lineages"][0]
        model = city_content.CityModel()
        model.resources[row["id"]] = {
            "class": "CCreature",
            "properties": {
                **{key: row[key] for key in ("sourceActor", "sourceArea", "sourceCreature", "sourceDialogue")},
                "sourceAllegiance": 128,
                "label": "Merchant",
                "hp": 34,
            },
        }
        actor = model.createObject(row["id"])
        model.game_map.addObject(actor)
        model.gui = SimpleNamespace(supportsSevenSunsMerchants=lambda: capability)
        return model, actor, model.dialog(actor)

    def snapshot(self, model, actor):
        return deepcopy(
            (
                model.game_map.properties,
                model.clock.properties,
                actor.properties,
                model.player.properties,
                model.player.getItems(),
                model.player.getQuests(),
            )
        )

    def drive(self, dialog, projection, choices):
        flow, answer, requests = dialog.conversationSevenSunsMerchantFlow(), None, []
        choices = iter(choices)
        while True:
            try:
                request = flow.send(answer)
            except StopIteration as result:
                return result.value, requests
            requests.append(request)
            operation, args = request["operation"], request["args"]
            if operation == "gui.beginSevenSunsMerchant":
                self.assertEqual(2, len(args))
                answer = projection.begin()
            elif operation == "gui.showCampaignScreen":
                self.assertEqual(STATES[projection.state]["body"], args[-1])
                answer = None
            elif operation == "gui.showChoice":
                rows = json.loads(args[1])
                self.assertEqual([str(index) for index in projection.view()["choices"]], [row["id"] for row in rows])
                answer = next(choices)
            elif operation == "gui.advanceSevenSunsMerchant":
                answer = projection.advance(*args)
            elif operation == "gui.endSevenSunsMerchant":
                answer = projection.close()
            else:
                self.fail("Unexpected Python authority: " + operation)

    def testEveryCompletePathAndLineageDelegatesEffectsToOwnedNativeIntents(self):
        for lineage in FACTS["lineages"]:
            for path in FACTS["completePaths"]:
                with self.subTest(lineage=lineage["id"], edges=path["edges"]):
                    model, actor, dialog = self.model(lineage)
                    before = self.snapshot(model, actor)
                    projection = MerchantSourceProjection(lineage["id"], {0: 0, 7: 1, 10: 2}[path["entryState"]])
                    choices = [str(edge) for edge in path["edges"] if EDGES[edge]["reply"] is not None]
                    completed, requests = self.drive(dialog, projection, choices)
                    self.assertTrue(completed)
                    self.assertEqual(path["edges"], projection.edges)
                    self.assertEqual(
                        before, self.snapshot(model, actor), "The oracle is not a game mutation or replacement proof"
                    )
                    self.assertEqual(
                        len(path["edges"]),
                        sum(request["operation"] == "gui.advanceSevenSunsMerchant" for request in requests),
                    )
                    self.assertFalse(
                        any("settle" in request["operation"] for request in requests),
                        "Dialogue is not the source script scheduler",
                    )

    def testCancellationAtEveryChoicePrefixKeepsCommittedSourceCounterAndGlobals(self):
        path = (1, 5, 11, 12)
        for prefix in ((), (1,), (1, 5)):
            model, actor, dialog = self.model()
            before = self.snapshot(model, actor)
            projection = MerchantSourceProjection(actor.getName())
            completed, _requests = self.drive(dialog, projection, [*(str(edge) for edge in prefix), None])
            self.assertFalse(completed)
            self.assertEqual(1, projection.count)
            self.assertEqual(list(prefix), projection.edges)
            self.assertEqual({"CheckedSevenSuns": 2} if prefix else {}, projection.globals)
            self.assertEqual(before, self.snapshot(model, actor))

    def testMissingOrNonBooleanCapabilityAndWrongIdentityBypassGenericTalk(self):
        for capability in (False, 1, "yes", None):
            model, actor, dialog = self.model(capability=capability)
            before = self.snapshot(model, actor)
            with self.assertRaises(StopIteration) as result:
                next(dialog.talkFlow())
            self.assertFalse(result.exception.value)
            self.assertEqual(before, self.snapshot(model, actor))
        for field in ("sourceActor", "sourceArea", "sourceCreature", "sourceDialogue"):
            model, actor, dialog = self.model()
            actor.setStringProperty(field, "wrong")
            before = self.snapshot(model, actor)
            with self.assertRaises(StopIteration) as result:
                next(dialog.talkFlow())
            self.assertFalse(result.exception.value)
            self.assertEqual(before, self.snapshot(model, actor))

    def testLegacyOrExhaustedNativeRefusalNeverShowsAReplyOrMutatesPythonState(self):
        for projection in (
            MerchantSourceProjection(FACTS["lineages"][0]["id"], 3),
            MerchantSourceProjection(FACTS["lineages"][0]["id"], source_known=False, generic_count=1),
        ):
            model, actor, dialog = self.model()
            before = self.snapshot(model, actor)
            completed, requests = self.drive(dialog, projection, [])
            self.assertFalse(completed)
            self.assertEqual(["gui.beginSevenSunsMerchant"], [row["operation"] for row in requests])
            self.assertEqual(before, self.snapshot(model, actor))

    def testMalformedViewsCannotChangeCursorCounterOrClaimReplacement(self):
        _model, actor, dialog = self.model()
        projection = MerchantSourceProjection(actor.getName())
        baseline = projection.begin()
        for mutation in (
            {"state": 14},
            {"revision": True},
            {"sourceTalkCount": True},
            {"choices": [False, 1, 2]},
            {"automaticEdge": True},
            {"lineage": "other"},
            {"attackRevealSupported": True},
            {"status": "replaced"},
        ):
            self.assertFalse(dialog.validSevenSunsMerchantView({**baseline, **mutation}, actor.getName()), mutation)
        flow = dialog.conversationSevenSunsMerchantFlow()
        next(flow)
        with self.assertRaises(StopIteration) as result:
            flow.send({**baseline, "state": 7, "choices": [13, 14, 15]})
        self.assertFalse(result.exception.value)

    def testNextTurnSettlementIsCapabilityGatedAndOnlyAnOwnedNativeRequest(self):
        model, actor, _dialog = self.model()
        before = self.snapshot(model, actor)
        flow = model.clock.settleSevenSunsMerchantsFlow()
        request = next(flow)
        self.assertEqual(("gui.settleSevenSunsMerchants", (model.clock,)), (request["operation"], request["args"]))
        with self.assertRaises(StopIteration) as result:
            flow.send({"status": "retry"})
        self.assertEqual({"status": "retry"}, result.exception.value)
        self.assertEqual(before, self.snapshot(model, actor))
        model.gui = SimpleNamespace()
        with self.assertRaises(StopIteration):
            next(model.clock.settleSevenSunsMerchantsFlow())

    def testPythonPresentationContainsNoItemReplacementOrGlobalFallback(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        owner = next(
            node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == "BaldursGateDialog"
        )
        method = next(
            node
            for node in owner.body
            if isinstance(node, ast.FunctionDef) and node.name == "conversationSevenSunsMerchant"
        )
        calls = {
            node.func.attr
            for node in ast.walk(method)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertFalse(
            calls
            & {
                "setStringProperty",
                "setNumericProperty",
                "setBoolProperty",
                "removeObject",
                "createObject",
                "addItem",
                "addGold",
                "addExp",
                "setController",
                "advanceTurns",
            }
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
