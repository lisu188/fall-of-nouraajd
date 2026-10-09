# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure source/catalog regressions; these do not stand in for MCP gameplay receipts."""

import ast
from collections import deque
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch

from tests import gameplay_branch_catalog as catalog
from tests.gameplay_branch_types import PLAYER_CLASSES, testName


def sourceMethod(source, class_id, method_name, **namespace):
    tree = ast.parse((catalog.ROOT / source).read_text(encoding="utf-8"))
    cls = next(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == class_id)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    exec(compile(ast.Module(body=[method], type_ignores=[]), source, "exec"), namespace)
    return namespace[method_name]


class GameplayBranchCatalogTest(unittest.TestCase):
    def testEveryAuthoredMapAndApplicableClassHasNamedRoutes(self):
        cases = catalog.getCases()
        self.assertEqual(len(cases), len({case.id for case in cases}))
        for case in cases:
            with self.subTest(case=case.id):
                self.assertTrue(callable(case.run))
                self.assertTrue(case.maps)
                self.assertTrue(case.classes)
                self.assertTrue(set(case.classes) <= set(PLAYER_CLASSES))
                self.assertEqual(len(case.classes), len(set(case.classes)))
                self.assertTrue(case.branches)
                self.assertEqual(len(case.branches), len(set(case.branches)))
                self.assertGreater(case.duration_seconds, 0)
                self.assertTrue(case.sources)
                for source in case.sources:
                    self.assertFalse(Path(source).is_absolute())
                    resolved = (catalog.ROOT / source).resolve()
                    self.assertTrue(resolved.is_relative_to(catalog.ROOT))
                    self.assertTrue(resolved.is_file(), source)
        self.assertEqual(set(catalog.AUTHORED_MAPS), {name for case in cases for name in case.maps})
        for map_name in catalog.AUTHORED_MAPS:
            self.assertEqual(
                set(PLAYER_CLASSES),
                {class_id for case in cases if map_name in case.maps for class_id in case.classes},
                map_name,
            )

    def testSelectorsReturnExactlyTheCanonicalCaseClassProduct(self):
        cases = catalog.getCases()
        expected = tuple(testName(case, class_id) for case in cases for class_id in case.classes)
        self.assertEqual(expected, catalog.selectedTestNames())
        self.assertEqual(len(expected), len(set(expected)))
        for class_id in PLAYER_CLASSES:
            self.assertEqual(
                tuple(testName(case, class_id) for case in cases if class_id in case.classes),
                catalog.selectedTestNames(class_id=class_id),
            )
        for group in {case.group for case in cases}:
            self.assertEqual(
                tuple(testName(case, class_id) for case in cases if case.group == group for class_id in case.classes),
                catalog.selectedTestNames(group=group),
            )
        for args in ({"class_id": "unknown"}, {"group": "unknown"}):
            with self.assertRaises(ValueError):
                catalog.selectedTestNames(**args)

    def testAuthoredCallbacksAndCampaignEdgesHaveExplicitMappings(self):
        report = catalog.auditCatalog()
        self.assertEqual((), report["issues"])
        self.assertIn("structural-only", report["proof"])
        self.assertEqual(catalog.campaignEdges(), frozenset(catalog.CAMPAIGN_EDGE_BRANCHES))

    def testReviewedSourceDigestRequiresReviewForNewInternalBranches(self):
        self.assertEqual(
            catalog.REVIEWED_GAMEPLAY_DIGEST,
            catalog.sourceReviewDigest(),
            "Authored content changed: review branch obligations before updating the source digest",
        )

    def testSharedObjectCallbackMutationInvalidatesReviewedDigest(self):
        source = catalog.ROOT / "res/plugins/object.py"
        original_read = Path.read_text

        def changed_read(path, *args, **kwargs):
            text = original_read(path, *args, **kwargs)
            if path == source:
                guard = "if cause in active_waypoint_causes:"
                self.assertIn(guard, text)
                return text.replace(guard, "if False and cause in active_waypoint_causes:", 1)
            return text

        before = catalog.sourceReviewDigest()
        with patch.object(Path, "read_text", changed_read):
            after = catalog.sourceReviewDigest()
        self.assertNotEqual(before, after, "The shared authored object callbacks must remain inside the source audit")

    def testAstNormalizationIgnoresOnlyEmptyVersionSpecificTypeParameters(self):
        source = (
            "class Quest:\n    def completed(self):\n        return True\n    async def advance(self):\n        pass\n"
        )
        legacy, modern = ast.parse(source), ast.parse(source)
        definition_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        for node in ast.walk(legacy):
            if isinstance(node, definition_types):
                node._fields = tuple(name for name in node._fields if name != "type_params")
                if hasattr(node, "type_params"):
                    del node.type_params
        for node in ast.walk(modern):
            if isinstance(node, definition_types):
                if "type_params" not in node._fields:
                    node._fields = (*node._fields, "type_params")
                node.type_params = []
        self.assertNotEqual(ast.dump(legacy), ast.dump(modern), "The fixture must reproduce the version mismatch")
        self.assertEqual(ast.dump(legacy), catalog.stableAstDump(legacy))
        self.assertEqual(catalog.stableAstDump(legacy), catalog.stableAstDump(modern))
        modern.body[0].type_params = [ast.Name(id="QuestState", ctx=ast.Load())]
        self.assertNotEqual(catalog.stableAstDump(legacy), catalog.stableAstDump(modern))
        self.assertIn("type_params", catalog.stableAstDump(modern))

    def testReviewedDigestIsPortableWithPython312DefinitionFields(self):
        original_parse = ast.parse

        def parseWithTypeParameters(*args, **kwargs):
            tree = original_parse(*args, **kwargs)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if "type_params" not in node._fields:
                        node._fields = (*node._fields, "type_params")
                    node.type_params = []
            return tree

        with patch.object(catalog.ast, "parse", parseWithTypeParameters):
            self.assertEqual(catalog.REVIEWED_GAMEPLAY_DIGEST, catalog.sourceReviewDigest())

    def testAstNormalizationRetainsNewInternalBranches(self):
        original = "def completed(self):\n    return self.cleared\n"
        formatted = "def completed( self ):\n    # formatting is not gameplay\n    return (self.cleared)\n"
        changed = "def completed(self):\n    if self.failed:\n        return False\n    return self.cleared\n"
        normalized = catalog.stableAstDump(ast.parse(original))
        self.assertEqual(normalized, catalog.stableAstDump(ast.parse(formatted)))
        self.assertNotEqual(normalized, catalog.stableAstDump(ast.parse(changed)))

    def testEveryDefensiveContractNamesAnExistingAutomatedRegression(self):
        evidence = catalog.contractEvidence()
        self.assertEqual(set(catalog.defensiveContracts()), set(evidence))
        parsed = {}
        for contract, (proof, test_id) in evidence.items():
            with self.subTest(contract=contract):
                self.assertIn(proof, {"native-direct", "source-double", "structural"})
                source, test_name = test_id.split(":", 1)
                if source not in parsed:
                    tree = ast.parse((catalog.ROOT / source).read_text(encoding="utf-8"))
                    parsed[source] = {
                        node.name + "." + method.name
                        for node in ast.walk(tree)
                        if isinstance(node, ast.ClassDef)
                        for method in node.body
                        if isinstance(method, ast.FunctionDef)
                    }
                self.assertIn(test_name, parsed[source])

    def testMissingAndDanglingWitnessesFailTheStructuralAudit(self):
        self.assertEqual(
            ("Unmapped authored callback: script:NewDialog.choose",),
            catalog.auditMappings({"script:NewDialog.choose"}, {}, {}, set()),
        )
        issues = catalog.auditMappings({"script:Dialog.choose"}, {"script:Dialog.choose": ("missing",)}, {}, {"known"})
        self.assertEqual(("Unknown branch witness: script:Dialog.choose -> missing",), issues)
        self.assertEqual(
            (), catalog.auditMappings({"script:Dialog.guard"}, {}, {"script:Dialog.guard": "contract"}, set())
        )
        self.assertTrue(catalog.auditMappings((), {"script:Dialog.choose": ()}, {}, set()))

    def testResolvedDialogReferencesRetainActionsConditionsAndPostActionEdges(self):
        resources = {
            "baseOption": {
                "class": "CDialogOption",
                "properties": {
                    "number": 0,
                    "action": "accept",
                    "condition": "can_accept",
                    "nextStateId": "JOINED",
                    "afterCondition": "has_left",
                    "afterStateId": "GONE",
                },
            },
            "dialog": {
                "class": "CompanionDialog",
                "properties": {
                    "states": [
                        {
                            "class": "CDialogState",
                            "properties": {"stateId": "ENTRY", "options": [{"ref": "baseOption"}]},
                        },
                        {"class": "CDialogState", "properties": {"stateId": "JOINED", "options": []}},
                        {"class": "CDialogState", "properties": {"stateId": "GONE", "options": []}},
                    ]
                },
            },
        }
        self.assertEqual(
            ("CompanionDialog", frozenset({"accept", "can_accept", "has_left"})),
            catalog.dialogCallbacks(resources["dialog"], resources),
        )
        resources["baseOption"]["properties"]["afterStateId"] = "MISSING"
        with self.assertRaisesRegex(ValueError, "Missing dialog state"):
            catalog.dialogCallbacks(resources["dialog"], resources)

    def testDialogAuditsRejectCyclesMissingReferencesAndAmbiguousOptions(self):
        for value, resources in (({"ref": "absent"}, {}), ({"ref": "loop"}, {"loop": {"ref": "loop"}})):
            with self.assertRaises(ValueError):
                catalog.resolveResource(value, resources)
        dialog = {
            "class": "CDialog",
            "properties": {
                "states": [
                    {
                        "class": "CDialogState",
                        "properties": {
                            "stateId": "ENTRY",
                            "options": [
                                {"class": "CDialogOption", "properties": {"number": 0, "nextStateId": "EXIT"}},
                                {"class": "CDialogOption", "properties": {"number": 0, "nextStateId": "EXIT"}},
                            ],
                        },
                    },
                ]
            },
        }
        with self.assertRaisesRegex(ValueError, "Duplicate dialog option"):
            catalog.dialogCallbacks(dialog, {})

    def testDynamicTownRestOptionsAreIncludedInTheCallbackInventory(self):
        source = "res/plugins/castle_campaign.py"
        tree = ast.parse((catalog.ROOT / source).read_text(encoding="utf-8"))
        expected = {source + ":CastleTownRestDialog." + method for method in ("configureTown", "canRest", "rest")}
        self.assertEqual(expected, set(catalog.dynamicDialogCallbacks(tree, source)))
        self.assertTrue(expected <= catalog.sourceCallbacks())
        for identity in expected:
            self.assertIn("castle.town.insufficientGold", catalog.sourceBranches()[identity])
        self.assertNotIn("castle.town.insufficientGold", catalog.defensiveContracts())
        self.assertNotIn("castle.town.insufficientGold", catalog.contractEvidence())

    def testDynamicDialogAuditRejectsMissingAndUnresolvedAuthoredCallbacks(self):
        source = """
class TownDialog:
    def configure(self):
        for number, (label, action, condition) in enumerate((("Rest", "rest", "canRest"), ("Leave", "", ""))):
            option.setStringProperty("action", action)
            option.setStringProperty("condition", condition)
        self.setStates({state})
    def rest(self):
        pass
    def canRest(self):
        pass
"""
        expected = {"script:TownDialog." + method for method in ("configure", "canRest", "rest")}
        self.assertEqual(expected, set(catalog.dynamicDialogCallbacks(ast.parse(source), "script")))
        with self.assertRaisesRegex(ValueError, "Missing exact dynamic dialog callback.*newRest"):
            catalog.dynamicDialogCallbacks(ast.parse(source.replace('"rest"', '"newRest"')), "script")
        with self.assertRaisesRegex(ValueError, "Unresolved dynamic dialog callback"):
            catalog.dynamicDialogCallbacks(
                ast.parse(source.replace('"action", action', '"action", unresolved')), "script"
            )
        with self.assertRaisesRegex(ValueError, "Unresolved dynamic dialog callback"):
            catalog.dynamicDialogCallbacks(
                ast.parse(source.replace('("Leave", "", "")', '("Leave", computedAction, "")')), "script"
            )

    def testEveryDeclaredBranchHasReviewedPrerequisitesOutcomesAndSources(self):
        entries = catalog.branchCatalog()
        self.assertEqual({branch for case in catalog.getCases() for branch in case.branches}, set(entries))
        for branch, entry in entries.items():
            with self.subTest(branch=branch):
                self.assertTrue(entry["prerequisites"])
                self.assertTrue(entry["outcomes"])
                self.assertTrue(entry["sources"])
                self.assertTrue(entry["cases"])
                expected_classes = (
                    {branch.rsplit(".", 1)[-1]}
                    if branch.startswith("nouraajd.deed.") and (branch.rsplit(".", 1)[-1] in PLAYER_CLASSES)
                    else None
                )
                if expected_classes:
                    self.assertEqual(expected_classes, set(entry["classes"]))

    def testPendingCastleDefendersRemainRequiredAndSeparateFromContracts(self):
        pending = catalog.pendingGameplayObligations()
        self.assertTrue(pending)
        declared = {branch for case in catalog.getCases() for branch in case.branches}
        self.assertTrue(set(pending) <= declared)
        self.assertFalse(set(pending) & set(catalog.defensiveContracts()))
        for branch, evidence in pending.items():
            if not branch.startswith("castle."):
                continue
            self.assertIn(".defender.", branch)
            self.assertGreater(evidence["componentCells"], 0)
            self.assertEqual(3, len(evidence["coords"]))
            self.assertIn("disconnected", evidence["reason"])

    def testPrematureThroneRemainsMandatoryForEveryWardenRouteAndClass(self):
        branch = "usurpergate.throne.premature"
        pending = catalog.pendingGameplayObligations()
        self.assertEqual(14, len(pending))
        self.assertIn(branch, pending)
        self.assertNotIn(branch, catalog.defensiveContracts())
        self.assertNotIn(branch, catalog.contractEvidence())
        entry = catalog.branchCatalog()[branch]
        self.assertEqual(
            {"wardens-mercy", "wardens-wrath", "wardens-standalone-spared", "wardens-standalone-executed"},
            set(entry["cases"]),
        )
        self.assertEqual(set(PLAYER_CLASSES), set(entry["classes"]))
        self.assertIn("res/maps/usurpergate/script.py:ObsidianThrone.onEnter", entry["callbacks"])
        self.assertEqual((12, 3, 0), pending[branch]["coords"])
        self.assertIn("unordered", pending[branch]["reason"])
        self.assertIn("unresolved", entry["outcomes"])

    def testTestMapMarketRequiresSeparatePurchaseAndInsufficientFundsWitnesses(self):
        entries = catalog.branchCatalog()
        identity = "res/plugins/object.py:Market.onEnter"
        branches = {"test.market.insufficientGold", "test.market.purchased"}
        self.assertNotIn("test.market", entries, "One outcome must not substitute for the other market branch")
        self.assertIn(identity, catalog.sourceCallbacks())
        self.assertTrue(branches <= set(catalog.sourceBranches()[identity]))
        for branch in branches:
            entry = entries[branch]
            self.assertEqual(set(PLAYER_CLASSES), set(entry["classes"]))
            self.assertIn(identity, entry["callbacks"])
            self.assertIn("src/object/CMarket.cpp", entry["sources"])
        self.assertIn("before", entries["test.market.insufficientGold"]["prerequisites"])
        self.assertIn("enough earned gold", entries["test.market.purchased"]["prerequisites"])

    def testLegacyTransitionHasNoAuthoredActor(self):
        directory = catalog.ROOT / "res/maps/nouraajd"
        resources = {}
        for path in (catalog.ROOT / "res/config").glob("*.json"):
            resources.update(json.loads(path.read_text(encoding="utf-8")))
        for path in directory.glob("*.json"):
            if path.name != "map.json":
                resources.update(json.loads(path.read_text(encoding="utf-8")))
        document = json.loads((directory / "map.json").read_text(encoding="utf-8"))
        for layer in document["layers"]:
            for actor in layer.get("objects", ()):
                definition = catalog.resolveResource(resources.get(actor["type"], {"class": actor["type"]}), resources)
                self.assertNotEqual("ChangeMap", definition.get("class"), actor.get("name"))

    def testNineMarchesNonplayerEventsAreInertContracts(self):
        event = types.SimpleNamespace(getCause=lambda: types.SimpleNamespace(isPlayer=lambda: False))
        actor = types.SimpleNamespace(getMap=lambda: self.fail("Nonplayer entry reached player gameplay effects"))
        for class_id in (
            "StartEvent",
            "LearningStone",
            "WitchHut",
            "GoldMine",
            "KeymasterCache",
            "GateThreshold",
            "Obelisk",
            "ItemCache",
            "DigSite",
        ):
            with self.subTest(class_id=class_id):
                sourceMethod("res/maps/ninemarches/script.py", class_id, "onEnter")(actor, event)

    def testConnectorDestructionUnregistersOnlyItsOwnPublishedEdges(self):
        for source, class_id in (
            ("res/maps/multilevel/script.py", "LevelStairs"),
            ("res/plugins/castle_campaign.py", "CastlePortal"),
        ):
            with self.subTest(class_id=class_id):
                removed = []
                world = types.SimpleNamespace(unregisterNavigationEdgesForObject=removed.append)
                actor = types.SimpleNamespace(getMap=lambda: world, getName=lambda: "authoredConnector")
                if class_id == "LevelStairs":
                    actor.clearNavigationEdge = types.MethodType(
                        sourceMethod(source, class_id, "clearNavigationEdge"), actor
                    )
                sourceMethod(source, class_id, "onDestroy")(actor, None)
                self.assertEqual(["authoredConnector"], removed)

    def testRetainedChapterDialogsRejectAlreadySettledActions(self):
        for map_name, class_id, settled, query in (
            ("hearthfall", "ElderDialog", "victory_reported", "victory_reported"),
            ("gravemoor", "VossDialog", "voss_judged", "already_judged"),
        ):
            with self.subTest(map_name=map_name):
                world = types.SimpleNamespace(
                    getBoolProperty=lambda key: key == settled,
                    getPlayer=lambda: self.fail("Retained settled action attempted a reward"),
                )
                game = types.SimpleNamespace(getMap=lambda: world)
                actor = types.SimpleNamespace(getGame=lambda: game)
                source = "res/maps/" + map_name + "/script.py"
                self.assertTrue(sourceMethod(source, class_id, query)(actor))
                if map_name == "hearthfall":
                    actor.captain_down = lambda: False
                    sourceMethod(source, class_id, "report_victory")(actor)
                else:
                    actor.ready_to_judge = lambda: False
                    actor._pass_judgment = types.MethodType(sourceMethod(source, class_id, "_pass_judgment"), actor)
                    sourceMethod(source, class_id, "spare_voss")(actor)
                    sourceMethod(source, class_id, "execute_voss")(actor)

    def testCastlePaidRestRejectsInsufficientGoldAndFullHealth(self):
        source = "res/plugins/castle_campaign.py"
        tree = ast.parse((catalog.ROOT / source).read_text(encoding="utf-8"))
        function = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "canRestAtTown"
        )
        namespace = {"canUseTown": lambda *_args: True, "TOWN_REST_GOLD": 10}
        exec(compile(ast.Module(body=[function], type_ignores=[]), source, "exec"), namespace)
        values = {"hp": 2, "max": 10, "gold": 9}
        player = types.SimpleNamespace(
            getHp=lambda: values["hp"], getHpMax=lambda: values["max"], getGold=lambda: values["gold"]
        )
        self.assertFalse(namespace["canRestAtTown"](object(), player))
        values["gold"] = 10
        self.assertTrue(namespace["canRestAtTown"](object(), player))
        values["hp"] = 10
        self.assertFalse(namespace["canRestAtTown"](object(), player))

    def testVhulmarnBellIsOnEveryAuthoredRouteToTheFinale(self):
        from tests.narrative_walkthrough import authoredRegion

        objects, walkable = authoredRegion("vhulmarn")

        def reachable(blocked):
            queue = deque([objects["vhulmarnStart"]])
            seen = set(queue)
            while queue:
                x, y, z = queue.popleft()
                for candidate in ((x - 1, y, z), (x + 1, y, z), (x, y - 1, z), (x, y + 1, z)):
                    if candidate in walkable and candidate not in seen and candidate != blocked:
                        seen.add(candidate)
                        queue.append(candidate)
            return seen

        self.assertIn(objects["altarThreshold"], reachable(None))
        self.assertNotIn(objects["altarThreshold"], reachable(objects["tideBell"]))


if __name__ == "__main__":
    unittest.main()
