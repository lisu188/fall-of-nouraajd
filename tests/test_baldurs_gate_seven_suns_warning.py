# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Finite source and presentation contracts; the native retirement service is not simulated as proof."""

import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import quest_state
from tests import test_baldurs_gate_city_content as city_content

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "res/maps/baldursGate/script.py"
FACTS = json.loads((ROOT / "tests/fixtures/baldurs_gate_seven_suns_warning.json").read_text(encoding="utf-8"))
STATES = {state["id"]: state for state in FACTS["states"]}
ACTOR = "cityAr0601Actor2"


class SourceProjection:
    """Small source-graph oracle. It does not move, retire, reward, or mutate a game actor."""

    def __init__(self, asked=0, shared_globals=None):
        self.state = 0
        self.revision = 0
        self.shared_globals = (
            shared_globals
            if shared_globals is not None
            else {"GLOBAL:AskedForTour": asked, "GLOBAL:CheckedSevenSuns": 91}
        )
        self.effects = []
        self.edges = []
        self.journals = []
        self.escaped = False
        self.closed = False

    @property
    def globals(self):
        return {name: self.shared_globals.get("GLOBAL:" + name, 0) for name in ("AskedForTour", "CheckedSevenSuns")}

    def eligible(self):
        return [
            edge
            for edge in STATES[self.state]["transitions"]
            if all(
                test["op"] == "Global"
                and test["args"][1] == "GLOBAL"
                and self.globals.get(test["args"][0], 0) == test["args"][2]
                for test in edge["conditions"]
            )
        ]

    def view(self):
        if self.escaped:
            return {
                "status": "retired",
                "capabilityVersion": 1,
                "state": self.state,
                "revision": self.revision,
                "choices": [],
                "automaticEdge": None,
                "journal": {"strref": 26986, "rawFlags": 92},
            }
        edges = self.eligible()
        automatic = [edge["id"] for edge in edges if edge["replyStrref"] is None]
        return {
            "status": "ready",
            "capabilityVersion": 1,
            "state": self.state,
            "revision": self.revision,
            "choices": [edge["id"] for edge in edges if edge["replyStrref"] is not None],
            "automaticEdge": automatic[0] if automatic else None,
            "journal": None,
        }

    def advance(self, revision, edge_id):
        if revision != self.revision or self.closed or self.escaped:
            raise ValueError("Stale or closed source-projection cursor")
        edge = next((edge for edge in self.eligible() if edge["id"] == edge_id), None)
        if edge is None:
            raise ValueError("Ineligible source-projection edge")
        self.edges.append(edge_id)
        for effect in edge["effects"]:
            self.effects.append(deepcopy(effect))
            if effect["op"] == "SetGlobal" and effect["args"][1] == "GLOBAL":
                self.shared_globals[effect["args"][1] + ":" + effect["args"][0]] = effect["args"][2]
            elif effect == {"op": "EscapeArea", "args": []}:
                self.escaped = True
            else:
                raise ValueError("Outside the implemented source projection")
        if edge["journal"] is not None:
            self.journals.append(deepcopy(edge["journal"]))
        if edge["next"] is not None:
            if edge["next"][0] != "DOPPSM":
                raise ValueError("External dialogue is not implemented")
            self.state = edge["next"][1]
        self.revision += 1
        return self.view()


def sourcePaths(asked):
    paths = []

    def visit(model):
        if len(model.edges) > 3:
            raise AssertionError("Source transition budget exceeded")
        if model.escaped:
            paths.append(model)
            return
        for edge in model.eligible():
            successor = deepcopy(model)
            successor.advance(model.revision, edge["id"])
            visit(successor)

    visit(SourceProjection(asked))
    return paths


class SevenSunsWarningSourceTest(unittest.TestCase):
    def testReadsSharedSerializedGlobalsWithoutWarningReceipt(self):
        saved = '{"GLOBAL:AskedForTour":1,"GLOBAL:CheckedSevenSuns":7,"GLOBAL:Unrelated":28}'
        shared = json.loads(saved)
        projection = SourceProjection(shared_globals=shared)
        projection.advance(0, 2)
        self.assertEqual([3, 4, 5, 6], projection.view()["choices"])
        self.assertEqual(2, shared["GLOBAL:CheckedSevenSuns"])
        self.assertEqual(1, shared["GLOBAL:AskedForTour"])
        self.assertEqual(28, shared["GLOBAL:Unrelated"])
        self.assertEqual(shared, json.loads(json.dumps(shared)))

    def testRetainedDopmerGlobalWriteSharesNamespaceWithoutInventedTourWriter(self):
        shared = {"GLOBAL:CheckedSevenSuns": 0, "GLOBAL:Other": 4}
        # The retained DOPMER metadata proves this fixed SetGlobal write; it
        # does not prove an outside DOPPSM AskedForTour writer or native route.
        for effect in FACTS["sharedGlobals"]["provenOtherDialogueWrites"]:
            self.assertEqual("DOPMER", effect["dialogue"])
            shared[effect["scope"] + ":" + effect["name"]] = effect["value"]
        projection = SourceProjection(shared_globals=shared)
        self.assertEqual(2, projection.globals["CheckedSevenSuns"])
        self.assertEqual(0, projection.globals["AskedForTour"])
        self.assertEqual(4, shared["GLOBAL:Other"])
        self.assertEqual([], projection.effects)
        self.assertFalse(projection.escaped)

    def testCompleteReachableClosureAndExplicitEntry(self):
        self.assertEqual(9, len(STATES))
        self.assertEqual(17, sum(len(row["transitions"]) for row in STATES.values()))
        self.assertEqual([{"op": "True", "args": []}], STATES[0]["entry"])
        self.assertTrue(all(row["entry"] is None for key, row in STATES.items() if key != 0))
        paths = sourcePaths(0) + sourcePaths(1)
        reached = {0}
        edges = set()
        for path in paths:
            state = 0
            for edge_id in path.edges:
                edge = next(edge for edge in STATES[state]["transitions"] if edge["id"] == edge_id)
                edges.add(edge_id)
                if edge["next"]:
                    state = edge["next"][1]
                    reached.add(state)
        self.assertEqual(set(FACTS["reachableStates"]), reached)
        self.assertEqual(set(FACTS["reachableEdges"]), edges)
        self.assertEqual({0, 1, 2, 3, 7, 8}, reached)

    def testAllNineOrTenCompletePathsPreserveActionsAndJournal(self):
        self.assertEqual(9, len(sourcePaths(0)))
        self.assertEqual(10, len(sourcePaths(1)))
        self.assertEqual(9, len(sourcePaths(2)), "AskedForTour tests equality to1, not truthiness")
        self.assertEqual(
            {(0, 7, 9), (0, 8, 16), (1, 3, 15), (1, 4, 9), (1, 5, 16), (1, 6, 16), (2, 3, 15), (2, 4, 9), (2, 6, 16)},
            {tuple(path.edges) for path in sourcePaths(0)},
        )
        for asked in (0, 1, 2):
            for path in sourcePaths(asked):
                with self.subTest(asked=asked, path=path.edges):
                    expected = [{"op": "SetGlobal", "args": ["CheckedSevenSuns", "GLOBAL", 2]}]
                    if path.edges[0] == 1:
                        expected.insert(0, {"op": "SetGlobal", "args": ["AskedForTour", "GLOBAL", 1]})
                    self.assertEqual(expected + [{"op": "EscapeArea", "args": []}], path.effects)
                    self.assertEqual([{"strref": 26986, "rawFlags": 92}], path.journals)
                    self.assertEqual(2, path.globals["CheckedSevenSuns"])
                    self.assertEqual(1 if path.edges[0] == 1 else asked, path.globals["AskedForTour"])
                    self.assertEqual(3, len(path.edges))

    def testConditionalReplyIsDistinctFromUnconditionalFarewell(self):
        self.assertEqual(
            [{"op": "Global", "args": ["AskedForTour", "GLOBAL", 1]}], STATES[1]["transitions"][2]["conditions"]
        )
        self.assertEqual([], STATES[1]["transitions"][3]["conditions"])
        for asked, expected in ((0, [3, 4, 6]), (1, [3, 4, 5, 6]), (2, [3, 4, 6])):
            projection = SourceProjection(asked)
            projection.advance(0, 2)
            self.assertEqual(expected, projection.view()["choices"])

    def testUnreachableEnemyAndExternalLinkStayExplicit(self):
        self.assertEqual(["SSUNGU", 5], STATES[5]["transitions"][0]["next"])
        self.assertEqual([{"op": "Enemy", "args": []}], STATES[6]["transitions"][0]["effects"])
        self.assertTrue(
            all(STATES[index]["classification"].startswith("noPathFromAuditedEntry") for index in (4, 5, 6))
        )
        self.assertFalse(FACTS["edition"]["originalParity"])
        self.assertFalse(FACTS["acceptance"]["native"])


class SevenSunsWarningPresentationTest(unittest.TestCase):
    def setUp(self):
        self.source_patch = patch.object(city_content, "SCRIPT", SOURCE)
        self.source_patch.start()
        self.addCleanup(self.source_patch.stop)

    def model(self, capable=True):
        model = city_content.CityModel()
        model.resources[ACTOR] = {
            "class": "CCreature",
            "properties": {
                "label": "Merchant",
                "sourceActor": "AR0601#actor2",
                "sourceArea": "AR0601",
                "sourceCreature": "DOPPSM",
                "sourceDialogue": "DOPPSM",
                "hp": 14,
            },
        }
        actor = model.createObject(ACTOR)
        model.game_map.addObject(actor)
        model.gui = SimpleNamespace(supportsSevenSunsWarning=lambda: capable)
        return model, actor, model.dialog(actor)

    def state(self, model, actor):
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

    def drive(self, dialog, projection, choices, final_refusal=False):
        flow = dialog.conversationSevenSunsWarningFlow()
        answer, requests = None, []
        choices = iter(choices)
        while True:
            try:
                request = flow.send(answer)
            except StopIteration as completed:
                return completed.value, requests
            requests.append(request)
            operation, args = request["operation"], request["args"]
            if operation == "gui.beginSevenSunsWarning":
                self.assertEqual(2, len(args))
                answer = projection.view()
            elif operation == "gui.showCampaignScreen":
                self.assertEqual(3, len(args))
                answer = None
            elif operation == "gui.showChoice":
                rows = json.loads(args[1])
                self.assertEqual([str(edge) for edge in projection.view()["choices"]], [row["id"] for row in rows])
                answer = next(choices)
            elif operation == "gui.advanceSevenSunsWarning":
                revision, edge = args
                if final_refusal and edge in (9, 15, 16):
                    answer = {**projection.view(), "status": "refused", "choices": [], "automaticEdge": None}
                else:
                    answer = projection.advance(revision, edge)
            elif operation == "gui.endSevenSunsWarning":
                projection.closed = True
                answer = {"status": "closed"}
            else:
                self.fail("Unexpected presentation authority: " + operation)

    def testEveryReachablePathUsesOnlyNativeOwnedIntents(self):
        for asked in (0, 1, 2):
            for path in sourcePaths(asked):
                with self.subTest(asked=asked, path=path.edges):
                    model, actor, dialog = self.model()
                    before = self.state(model, actor)
                    projection = SourceProjection(asked)
                    completed, requests = self.drive(dialog, projection, [str(edge) for edge in path.edges[:2]])
                    self.assertTrue(completed, "Only acknowledgement of the oracle's explicit retired view")
                    self.assertEqual(path.edges, projection.edges)
                    self.assertEqual(before, self.state(model, actor), "Python itself must grant no effects")
                    operations = [request["operation"] for request in requests]
                    self.assertEqual(3, operations.count("gui.advanceSevenSunsWarning"))
                    self.assertEqual(3, operations.count("gui.showCampaignScreen"))
                    self.assertEqual(2, operations.count("gui.showChoice"))

    def testCancellationBeforeAndAfterEveryFirstChoice(self):
        for first in (None, 0, 1, 2):
            with self.subTest(first=first):
                model, actor, dialog = self.model()
                before = self.state(model, actor)
                projection = SourceProjection()
                choices = [""] if first is None else [str(first), ""]
                completed, requests = self.drive(dialog, projection, choices)
                self.assertFalse(completed)
                self.assertTrue(projection.closed)
                self.assertFalse(projection.escaped)
                self.assertEqual([], projection.journals)
                self.assertEqual(91 if first is None else 2, projection.globals["CheckedSevenSuns"])
                self.assertEqual(1 if first == 1 else 0, projection.globals["AskedForTour"])
                self.assertEqual(before, self.state(model, actor))
                self.assertEqual("gui.endSevenSunsWarning", requests[-1]["operation"])

    def testFlowUnwindAtEachPresentationBoundaryProducesNoPythonEffects(self):
        for boundary in range(5):
            model, actor, dialog = self.model()
            before = self.state(model, actor)
            flow, projection = dialog.conversationSevenSunsWarningFlow(), SourceProjection()
            answer, seen = None, 0
            for _request in range(12):
                request = flow.send(answer)
                operation, args = request["operation"], request["args"]
                if operation in ("gui.showCampaignScreen", "gui.showChoice"):
                    if seen == boundary:
                        flow.close()
                        break
                    seen += 1
                if operation == "gui.beginSevenSunsWarning":
                    answer = projection.view()
                elif operation == "gui.advanceSevenSunsWarning":
                    answer = projection.advance(*args)
                elif operation == "gui.showChoice":
                    answer = "0" if projection.state == 0 else "7"
                else:
                    answer = None
            else:
                self.fail("Expected bounded presentation boundary")
            self.assertFalse(projection.escaped)
            self.assertEqual([], projection.journals)
            self.assertEqual(before, self.state(model, actor))

    def testUnavailableRuntimeBypassesGenericTalkWithoutMutation(self):
        for capability in ("missing", "false"):
            model, actor, dialog = self.model(capable=False)
            if capability == "missing":
                model.gui = SimpleNamespace()
            before = self.state(model, actor)
            with self.assertRaises(StopIteration) as result:
                next(dialog.talkFlow())
            self.assertFalse(result.exception.value)
            self.assertEqual(before, self.state(model, actor))

    def testWrongIdentityCannotUseWarningFlowOrFallback(self):
        for field in ("sourceActor", "sourceArea", "sourceCreature", "sourceDialogue"):
            model, actor, dialog = self.model()
            actor.setStringProperty(field, "wrong")
            before = self.state(model, actor)
            with self.subTest(field=field), self.assertRaises(StopIteration) as result:
                next(dialog.talkFlow())
            self.assertFalse(result.exception.value)
            self.assertEqual(before, self.state(model, actor))

    def testInvalidOrHiddenSelectionRefusesAndKeepsEarlierGlobals(self):
        model, actor, dialog = self.model()
        projection = SourceProjection()
        completed, _requests = self.drive(dialog, projection, ["2", "5"])
        self.assertFalse(completed)
        self.assertEqual([2], projection.edges)
        self.assertEqual(2, projection.globals["CheckedSevenSuns"])
        self.assertTrue(projection.closed)
        self.assertFalse(projection.escaped)

    def testNativeRefusalNeverBecomesEffectSuccess(self):
        _model, _actor, dialog = self.model()
        projection = SourceProjection()
        completed, _requests = self.drive(dialog, projection, ["0", "7"], final_refusal=True)
        self.assertFalse(completed)
        self.assertEqual([0, 7], projection.edges)
        self.assertFalse(projection.escaped)
        self.assertEqual([], projection.journals)

    def testMalformedViewsAndUnreachableStatesRefuse(self):
        _model, _actor, dialog = self.model()
        baseline = SourceProjection().view()
        for mutation in (
            {"state": 4},
            {"state": 5},
            {"state": 6},
            {"revision": True},
            {"capabilityVersion": 2},
            {"choices": [0, 0, 2]},
            {"automaticEdge": 9},
        ):
            with self.subTest(mutation=mutation):
                self.assertFalse(dialog.validSevenSunsWarningView({**baseline, **mutation}))

    def testEntryOrSuccessorJumpCannotSkipSourceChoices(self):
        _model, _actor, dialog = self.model()
        flow = dialog.conversationSevenSunsWarningFlow()
        self.assertEqual("gui.beginSevenSunsWarning", next(flow)["operation"])
        with self.assertRaises(StopIteration) as result:
            flow.send(
                {
                    "status": "ready",
                    "capabilityVersion": 1,
                    "state": 3,
                    "revision": 0,
                    "choices": [],
                    "automaticEdge": 9,
                    "journal": None,
                }
            )
        self.assertFalse(result.exception.value)
        flow = dialog.conversationSevenSunsWarningFlow()
        next(flow)
        self.assertEqual("gui.showCampaignScreen", flow.send(SourceProjection().view())["operation"])
        self.assertEqual("gui.showChoice", flow.send(None)["operation"])
        self.assertEqual("gui.advanceSevenSunsWarning", flow.send("0")["operation"])
        with self.assertRaises(StopIteration) as result:
            flow.send({**SourceProjection().view(), "revision": 1})
        self.assertFalse(result.exception.value)

    def testJournalLeadUsesPersistentVisibleQuestWithoutScarProgress(self):
        model, _actor, _dialog = self.model()
        fragment = (
            json.loads((ROOT / "generated-config-entry.json").read_text())
            if (ROOT / "generated-config-entry.json").exists()
            else {
                "citySevenSunsWarningLead": {
                    "class": "BaldursGateSevenSunsWarningLeadQuest",
                    "properties": {"description": "Seven Suns: a merchant's warning"},
                }
            }
        )
        model.resources.update(fragment)
        quest_type = model.types["BaldursGateSevenSunsWarningLeadQuest"]
        quest_state.mapQuest("baldursGate")(quest_type)
        note = model.createObject("citySevenSunsWarningLead")
        model.game_map.mapName = "baldursGate"
        model.player.quests.append(note)
        before_gold = model.player.getGold()
        note.captureJournal(False)
        self.assertFalse(note.isCompleted())
        self.assertEqual(1, note.getNumericProperty("questJournalVersion"))
        self.assertEqual("baldursGate", note.getStringProperty("questJournalOrigin"))
        self.assertIn("shapechangers", note.getObjective())
        self.assertIn("no gold", note.getReward())
        self.assertEqual([], model.player.getCompletedQuests())
        self.assertEqual("", model.game_map.getStringProperty("plugin_cityQuest_scarSevenSuns"))
        self.assertEqual(before_gold, model.player.getGold())
        self.assertIsNone(note.onComplete())
        expected = note.getObjective(), note.getReward(), note.getHint()
        model.game_map.mapName = "anotherMap"
        self.assertEqual(expected, (note.getObjective(), note.getReward(), note.getHint()))
        self.assertFalse(note.isCompleted())

    def testCallbackSourceContainsNoEffectOrRemovalFallback(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        owner = next(
            node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == "BaldursGateDialog"
        )
        callback = next(
            node
            for node in owner.body
            if isinstance(node, ast.FunctionDef) and node.name == "conversationSevenSunsWarning"
        )
        forbidden = {
            "setStringProperty",
            "setNumericProperty",
            "setBoolProperty",
            "addQuest",
            "removeObject",
            "addExp",
            "addGold",
            "createObject",
            "advanceTurns",
            "spawnActors",
            "applyEffects",
        }
        calls = {
            node.func.attr
            for node in ast.walk(callback)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertFalse(forbidden & calls)
        self.assertIn("supportsSevenSunsWarning", ast.get_source_segment(SOURCE.read_text(encoding="utf-8"), callback))

    def testGeneratorDefinesTheSeparateLeadQuest(self):
        tree = ast.parse((ROOT / "scripts/build_baldurs_gate_city.py").read_text(encoding="utf-8"))
        row = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "config"
                and isinstance(target.slice, ast.Constant)
                and target.slice.value == "citySevenSunsWarningLead"
                for target in node.targets
            )
        )
        self.assertEqual("BaldursGateSevenSunsWarningLeadQuest", ast.literal_eval(row.value.args[0]))
        self.assertEqual("Seven Suns: a merchant's warning", ast.literal_eval(row.value.keywords[0].value))

    def testGeneratorPublishesProtectedNativeClockDefinition(self):
        source = (ROOT / "scripts/build_baldurs_gate_city.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
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
        encoded = next(keyword.value for keyword in row.value.keywords if keyword.arg == "sevenSunsWarningDefinition")
        functions = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in {"protectCityData", "definition"}
        ]
        namespace = {"json": json, "CITY_JSON_PREFIX": "city-json:"}
        exec(
            compile(ast.Module(body=functions, type_ignores=[]), "actual-city-definition-functions", "exec"), namespace
        )
        value = eval(compile(ast.Expression(encoded), "actual-clock-warning-definition", "eval"), {"json": json})
        actual = namespace["definition"]("BaldursGateClock", sevenSunsWarningDefinition=value)["properties"][
            "sevenSunsWarningDefinition"
        ]
        self.assertTrue(actual.startswith("city-json:"))
        self.assertLessEqual(len(actual.encode()), 1024)
        self.assertEqual(
            {
                "version": 1,
                "dialogue": "DOPPSM",
                "fingerprint": FACTS["sources"]["dialogueFingerprint"]["sha256"],
                "journalQuest": "citySevenSunsWarningLead",
            },
            json.loads(actual.removeprefix("city-json:")),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
