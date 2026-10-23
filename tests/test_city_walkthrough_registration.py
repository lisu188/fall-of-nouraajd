# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source and model checks for walkthrough wiring and explicit test-only modal fixtures.

These checks do not establish native UI, MCP, or scenario acceptance.
"""

import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class CityWalkthroughRegistrationTest(unittest.TestCase):
    def setUp(self):
        global harness
        import test as harness

    def testBothRegistriesContainRealCanonicalCityRoutes(self):
        from tests.gameplay_branch_catalog import getCases

        expected = {"candlekeep": "candlekeep-prologue", "baldursGate": "baldurs-gate-tour"}
        cases = {case.id: case for case in getCases()}
        self.assertEqual(expected, harness.CITY_WALKTHROUGH_CASES)
        for map_name, case_id in expected.items():
            self.assertIn(map_name, harness.WALKTHROUGHS)
            method = harness.McpServerTest.MCP_WALKTHROUGHS[map_name]
            self.assertTrue(callable(getattr(harness.McpServerTest, method)))
            self.assertEqual((map_name,), cases[case_id].maps)
            self.assertEqual(harness.cityWalkthroughCase(map_name), cases[case_id])
            self.assertTrue(cases[case_id].branches)

    def testBothWalkthroughRegistriesCoverEveryDiscoveredMap(self):
        discovered = set(harness.discover_maps())
        self.assertEqual(discovered, set(harness.WALKTHROUGHS))
        self.assertEqual(discovered, set(harness.McpServerTest.MCP_WALKTHROUGHS))

    def testEveryCanonicalCityRouteHasAnExecutableGameTestEntry(self):
        source = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        game_tests = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "GameTest")
        for map_name in harness.CITY_WALKTHROUGH_CASES:
            name = "test_map_walkthrough_" + map_name
            with self.subTest(map=map_name):
                self.assertTrue(callable(getattr(harness.GameTest, name, None)), name)
                method = next(
                    node for node in game_tests.body if isinstance(node, ast.FunctionDef) and node.name == name
                )
                method.decorator_list = []
                seen, result = [], object()
                namespace = {"execute_walkthrough": lambda key: seen.append(key) or result}
                exec(compile(ast.Module(body=[method], type_ignores=[]), "canonical-city-entry", "exec"), namespace)
                self.assertIs(result, namespace[name](self))
                self.assertEqual([map_name], seen)


    def testQueuedWaitPumpsUntilObservedStateAndDoesNotHideErrors(self):
        observed = []
        with patch.object(harness.time, "sleep", side_effect=AssertionError("sleep is not queue progress")):
            self.assertTrue(harness.pumpQueuedUntil(lambda: len(observed) == 3, pump=lambda: observed.append("pump")))
        self.assertEqual(["pump"] * 3, observed)
        observed.clear()
        with patch.object(harness.time, "monotonic", side_effect=(0, 2)):
            self.assertFalse(harness.pumpQueuedUntil(lambda: False, timeout=1, pump=lambda: observed.append("pump")))
        self.assertEqual(["pump"], observed)
        with self.assertRaisesRegex(ValueError, "observable failure"):
            harness.pumpQueuedUntil(lambda: (_ for _ in ()).throw(ValueError("observable failure")), pump=lambda: None)

    def testWalkthroughAdaptersRunActualRouteFinishAndCleanup(self):
        events = []
        case = SimpleNamespace(id="city-test", classes=("Warrior",), sources=("res/maps/test/script.py",))
        case.run = lambda driver: events.append(("run", driver))

        class Driver:
            def __init__(self, *args):
                events.append(("create", args))

            def finish(self):
                events.append(("finish", self))

            def receipt(self):
                return {"case": case.id, "steps": 3, "branches": {"actual": {}}}

            def cleanup(self):
                events.append(("cleanup", self))

        session = {"proc": SimpleNamespace(_playtest_trace_path=Path("unit.trace.jsonl"))}
        with (
            patch.object(harness, "cityWalkthroughCase", return_value=case),
            patch("tests.gameplay_branch_driver.GameplayBranchDriver", Driver),
            patch("tests.test_gameplay_branches_mcp.verifyCopiedSources") as verify,
        ):
            result = harness.runCityMcpWalkthrough(self, session, "candlekeep")
        self.assertEqual("candlekeep", result["map"])
        self.assertEqual(3, result["steps"])
        self.assertEqual(["create", "run", "finish", "cleanup"], [entry[0] for entry in events])
        verify.assert_called_once()
        self.assertEqual(Path("unit.trace.jsonl"), events[1][1].trace_path)

    def testCanonicalWalkthroughStartsWithTheDriversReproducibleSeed(self):
        from tests.gameplay_branch_driver import caseSeed

        client = harness.McpServerTest(methodName="runTest")
        process = SimpleNamespace(_playtest_trace_path=None)
        trace_names = []
        for map_name in ("candlekeep", "candlekeep", "baldursGate"):
            case = harness.cityWalkthroughCase(map_name)
            method = client.MCP_WALKTHROUGHS[map_name]
            with (
                patch.object(client, "_start_stdio_mcp_process", return_value=process) as start,
                patch.object(client, "_initialize_stdio_mcp"),
                patch.object(client, method, return_value={"map": map_name}),
                patch.object(client, "_shutdown_process") as shutdown,
                patch.object(client, "_write_mcp_walkthrough_log"),
            ):
                success, result = client._run_mcp_walkthrough(map_name)
            self.assertTrue(success, result)
            start.assert_called_once()
            self.assertEqual((map_name,), start.call_args.args)
            self.assertEqual(caseSeed(case.id, case.classes[0]), start.call_args.kwargs["test_seed"])
            trace_name = start.call_args.kwargs["trace_name"]
            self.assertRegex(trace_name, "^" + map_name + "-[0-9a-f]{32}$")
            trace_names.append(trace_name)
            shutdown.assert_called_once_with(process)
        self.assertEqual(
            3, len(set(trace_names)), "Parallel direct/MCP walkthroughs must retain separate native traces"
        )

    def testModalModelFixtureResumesOnlyExplicitlyMockedRequestsAndKeepsTokens(self):
        sys.path.insert(0, str(ROOT / "res"))
        self.addCleanup(sys.path.remove, str(ROOT / "res"))
        import ui

        class NativeModel:
            pass

        actual = NativeModel()
        seen, answers = [], []

        def callback():
            answers.append((yield ui.uiRequest("gui.showChoice", "Choose", [actual])))
            yield ui.uiRequest("gui.showMessage", "Unmocked native request")

        original = ui.UiFlow.advance
        with (
            patch.dict(sys.modules, _game=SimpleNamespace(CGameObject=NativeModel)),
            harness.mockNativeUiRequests(
                {"showChoice": lambda title, values: seen.append((title, values[0])) or "picked"}
            ),
        ):
            flow = ui.UiFlow.fromCallback(callback)
            self.addCleanup(flow.close)
            request = json.loads(flow.advance("null"))
            self.assertEqual("showMessage", request["operation"])
            self.assertEqual(["picked"], answers)
            self.assertEqual([("Choose", actual)], seen)
            self.assertEqual({}, flow.objectArguments)
        self.assertIs(original, ui.UiFlow.advance)

    def testModalModelFixtureDoesNotAutoAnswerUnsupportedRequestsOrSwallowFailures(self):
        import ui

        def callback():
            yield ui.uiRequest("gui.unsupportedUnitOperation", "Untouched")

        with harness.mockNativeUiRequests({"showMessage": self.fail}):
            flow = ui.UiFlow.fromCallback(callback)
            self.addCleanup(flow.close)
            self.assertEqual("unsupportedUnitOperation", json.loads(flow.advance("null"))["operation"])

        def failure():
            yield ui.uiRequest("gui.showMessage", "Bad fixture")

        with harness.mockNativeUiRequests(
            {"showMessage": lambda *_args: (_ for _ in ()).throw(ValueError("sentinel"))}
        ):
            flow = ui.UiFlow.fromCallback(failure)
            self.addCleanup(flow.close)
            with self.assertRaisesRegex(ValueError, "sentinel"):
                flow.advance("null")

    def testRuntimeLoadingAndSourceFixturesKeepSeparateSuiteSelection(self):
        names = harness.discover_unittest_test_names(["test.py", "CityNativeLoadingRuntimeTest"])
        self.assertEqual(
            {
                "CityNativeLoadingRuntimeTest.testCityLoadsNativePlacedAndDeferredActorsWithBlockedLayerFallback",
                "CityNativeLoadingRuntimeTest.testCityStructuredMetadataAndOwnedItemsSurviveSaveReload",
                "CityNativeLoadingRuntimeTest.testNativeSaveDiagnosticsAreSilentByDefaultAndPreserveTheSavedDocument",
            },
            set(names),
        )
        self.assertEqual([], harness.filter_test_names_by_suite(names, "fast"))
        for suite in ("gameplay", "coverage-safe", "full"):
            self.assertEqual(names, harness.filter_test_names_by_suite(names, suite))
        source_names = harness.discover_unittest_test_names(["test.py", "CityWalkthroughRegistrationTest"])
        self.assertEqual(source_names, harness.filter_test_names_by_suite(source_names, "fast"))

    def testMockModalBudgetIsBoundedAndCannotHideAnEndlessFlow(self):
        import ui

        def callback():
            while True:
                yield ui.uiRequest("gui.showMessage", "Repeated model prompt")

        with harness.mockNativeUiRequests({"showMessage": lambda *_args: None}):
            flow = ui.UiFlow.fromCallback(callback)
            self.addCleanup(flow.close)
            with self.assertRaisesRegex(AssertionError, "bounded request budget"):
                flow.advance("null")

    def testTurnProbeUsesConstructibleWrappedEventAndRetainsTurnAssertion(self):
        tree = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        function = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "test_map_turn_progress_binding_tracks_real_turn_hooks"
        )
        probe = next(n for n in ast.walk(function) if isinstance(n, ast.ClassDef) and n.name == "TurnProgressProbe")
        self.assertEqual("game.CEvent", ast.unparse(probe.bases[0]))
        self.assertTrue(any(isinstance(n, ast.FunctionDef) and n.name == "onTurn" for n in probe.body))

    def testAuthoredTagFixtureDecodesUtf8InsteadOfTheHostLocale(self):
        source = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        function = next(
            node
            for node in ast.walk(source)
            if isinstance(node, ast.FunctionDef) and node.name == "test_authored_tag_strings_are_canonical"
        )
        function.decorator_list = []
        raw = json.dumps({"effect": {"label": "Duke\u201d", "tags": ["buff"]}}, ensure_ascii=False).encode("utf-8")
        with self.assertRaises(UnicodeDecodeError):
            raw.decode("cp1252")
        encodings, tags = [], set()

        class AuthoredPath:
            def read_text(self, encoding=None):
                encodings.append(encoding)
                return raw.decode(encoding or "cp1252")

            def relative_to(self, _root):
                return "res/maps/city/config.json"

        class Resources:
            def __truediv__(self, part):
                if part != "res":
                    raise AssertionError(part)
                return self

            def rglob(self, pattern):
                if pattern != "*.json":
                    raise AssertionError(pattern)
                return [AuthoredPath()]

        probe = SimpleNamespace(addTag=tags.add, hasTag=tags.__contains__, removeTag=tags.remove)
        instance = SimpleNamespace(createObject=lambda _type_id: probe)
        api = SimpleNamespace(CGameLoader=SimpleNamespace(loadGame=lambda: instance))
        namespace = {"load_game_module": lambda: api, "json": json, "REPO_ROOT": Resources()}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "authored-tag-encoding-model", "exec"), namespace)
        success, log = namespace[function.name](self)
        self.assertTrue(success)
        self.assertEqual({"res/maps/city/config.json": {"effect.tags": ["buff"]}}, json.loads(log))
        self.assertEqual(["utf-8"], encodings)
        self.assertEqual(set(), tags)

    def runCombatTransitionModel(self, *, commit_during_fight, pending_state="TransitionPending"):
        """Run the real test contract against explicit scheduling models, without native credit."""
        tree = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "test_scene_manager_transition_requested_during_combat_preserves_source_map"
        )
        function.decorator_list = []
        calls, registered, configs = [], {}, {}

        class Creature:
            def __init__(self):
                self.baseStats, self.hp, self.name = SimpleNamespace(), 10, "player"

            def setHp(self, hp):
                self.hp = hp

            def hurt(self, amount):
                self.hp -= amount

            def isAlive(self):
                return self.hp > 0

            def isPlayer(self):
                return self.name == "player"

            def getName(self):
                return self.name

            def moveTo(self, *_coords):
                pass

            def setFightController(self, _controller):
                pass

        player = Creature()

        class World:
            def __init__(self, name):
                self.mapName = name
                self.properties, self.objects = {"turn": 0}, {player.name: player}

            def getPlayer(self):
                return self.objects.get(player.name)

            def getObjects(self):
                return list(self.objects.values())

            def getObjectByName(self, name):
                return self.objects.get(name)

            def addObject(self, actor):
                self.objects[actor.name] = actor

            def setNumericProperty(self, name, value):
                self.properties[name] = value

            def setStringProperty(self, name, value):
                self.properties[name] = value

            def getStringProperty(self, name):
                return self.properties.get(name, "")

            def getTurn(self):
                return self.properties["turn"]

        source = World("empty")

        class Scene:
            state, pending = "Idle", ""

            def getTransitionStateName(self):
                return self.state

            def getPendingMapName(self):
                return self.pending

            def isTransitionPending(self):
                return self.state != "Idle"

            def commit(self):
                if self.pending:
                    calls.append("commit")
                    instance.active = World(self.pending)
                    instance.active.properties["turn"] = source.getTurn()
                    source.objects.pop(player.name)
                    self.state, self.pending = "Idle", ""

        scene = Scene()

        class Game:
            active = source

            def getMap(self):
                return self.active

            def getSceneManager(self):
                return scene

            def changeMap(self, target):
                calls.append("request")
                scene.state, scene.pending = pending_state, target

            def getObjectHandler(self):
                return self

            def registerType(self, name, cls):
                registered[name] = cls

            def registerConfigJson(self, name, document):
                configs[name] = json.loads(document)

            def createObject(self, _type_id):
                return Creature()

        instance = Game()

        def fightMany(attacker, defenders):
            self.assertEqual(1, len(defenders))
            defender = defenders[0]
            self.assertEqual("TransitionStrike", configs["CombatTransitionStrike"]["class"])
            try:
                registered["TransitionStrike"]().performAction(attacker, defender)
            except AssertionError:
                calls.append("callback assertion swallowed by native wrapper model")
            self.assertFalse(defender.isAlive())
            source.objects.pop(defender.name)
            if commit_during_fight:
                scene.commit()
            calls.append("fight returned")
            return True

        def pumpUntil(predicate, *, timeout, min_iterations):
            self.assertEqual((2.0, 2), (timeout, min_iterations), "Keep the existing bounded wait contract")
            for _ in range(min_iterations):
                calls.append("pump")
                scene.commit()
            return predicate()

        api = SimpleNamespace(
            CGameLoader=SimpleNamespace(loadGame=lambda: instance, startGameWithPlayer=lambda *_args: None),
            CInteraction=object,
            CFightHandler=SimpleNamespace(fightMany=fightMany),
        )
        namespace = {
            "load_game_module": lambda: api,
            "json": json,
            "count_player_objects": harness.count_player_objects,
            "transition_source_map_snapshot": harness.transition_source_map_snapshot,
            "assert_transition_source_map_unchanged": harness.assert_transition_source_map_unchanged,
            "pump_event_loop_until": pumpUntil,
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), "combat-transition-model", "exec"), namespace)
        success, log = namespace[function.name](self)
        self.assertTrue(success)
        self.assertEqual("ritual", json.loads(log)["destination"])
        self.assertEqual(1, calls.count("request"))
        self.assertEqual(1, calls.count("commit"))
        return calls

    def testCombatTransitionChecksRequestTimeStateWhenSyncFightCommitsQueuedSceneWork(self):
        calls = self.runCombatTransitionModel(commit_during_fight=True)
        self.assertLess(calls.index("commit"), calls.index("fight returned"))

    def testCombatTransitionRetainsFinalWaitWhenCommitFollowsTheSyncFight(self):
        calls = self.runCombatTransitionModel(commit_during_fight=False)
        self.assertLess(calls.index("fight returned"), calls.index("commit"))

    def testCombatTransitionChecksImmediatePhaseOutsideTheNativeCallback(self):
        with self.assertRaisesRegex(AssertionError, "TransitionPending"):
            self.runCombatTransitionModel(commit_during_fight=True, pending_state="Idle")

    def testNarrativeWaitUsesObservedDestinationAndBoundedOuterPumping(self):
        from tests.narrative_walkthrough import NarrativeWalkthrough

        calls = []
        driver = object.__new__(NarrativeWalkthrough)
        driver.game, driver.gameMap = "game", "ritual"
        driver.pump = lambda: calls.append("pump")

        def call(handle, method, args=None):
            if (handle, method) == ("game", "getSceneManager"):
                return "scene"
            if (handle, method) == ("game", "getMap"):
                return "siege" if len(calls) >= 4 else "ritual"
            if method == "getStringProperty":
                return handle
            if (handle, method) == ("scene", "isTransitionPending"):
                return len(calls) < 4
            raise AssertionError((handle, method, args))

        driver.call = call
        driver.waitForMap("siege", timeout=1)
        self.assertEqual(["pump"] * 4, calls)
        self.assertEqual("siege", driver.gameMap)
        driver.gameMap = "ritual"
        calls.clear()
        with patch("tests.narrative_walkthrough.monotonic", side_effect=(0, 2)):
            with self.assertRaisesRegex(AssertionError, "siege"):
                driver.waitForMap("siege", timeout=1)
        self.assertEqual(["pump"], calls)


if __name__ == "__main__":
    unittest.main()
