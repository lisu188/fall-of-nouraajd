# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authored dialogue routes through the stdio MCP server and actual player movement."""

import ast
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch


def waitForRemoteTransition(game, expected_map_name, engine, call, wait_until):
    loop = engine("event_loop.instance")
    manager = call(game, "getSceneManager")
    destination = None

    def completed():
        nonlocal destination
        current = call(game, "getMap")
        if current is None or call(current, "getStringProperty", "mapName") != expected_map_name:
            return False
        if call(manager, "isTransitionPending"):
            return False
        destination = current
        return True

    if wait_until(completed, timeout=1.0, pump=lambda: call(loop, "run")):
        return destination
    return None


class DialogueMcpWalkthroughTest(unittest.TestCase):
    def testNonblockingDialogReturnsTheUniqueNativePanelBeforeKeyboardInput(self):
        self.startMap("nouraajd")
        dialog = self.dialog("tavernDialog1")
        handler = self.call(self.game, "getGuiHandler")
        self.assertIsNone(self.call(handler, "openDialog", dialog))
        self.engine("CGameLoader.loadGui", self.game)
        gui = self.call(self.game, "getGui")
        self.assertIsNotNone(gui)
        panel = self.call(handler, "openDialog", dialog)
        self.assertIsNotNone(panel, "opening must return before the next keyboard RPC")
        panels = [child for child in self.call(gui, "getChildren") if self.call(child, "getType") == "CGameDialogPanel"]
        self.assertEqual([panel], panels, "the returned handle must be the unique actual attached dialog panel")
        self.assertEqual(gui, self.call(panel, "getParent"))
        self.assertTrue(self.call(panel, "keyboardEvent", gui, 768, 27))
        self.assertNotIn(panel, self.call(gui, "getChildren"))
        self.assertIsNone(self.call(panel, "getParent"))

    def setUp(self):
        # Import the existing stream-draining harness only for native integration tests.
        import test as harness

        extension_dirs = [harness.build_dir, *harness.extension_dirs]
        if not any(list(path.glob("_game*.pyd")) + list(path.glob("_game*.so")) for path in extension_dirs):
            self.skipTest("The current _game extension is required for dialogue MCP walkthroughs")
        self.environment = patch.dict(
            os.environ,
            SDL_VIDEODRIVER="dummy",
            SDL_AUDIODRIVER="dummy",
            SDL_RENDER_DRIVER="software",
            LIBGL_ALWAYS_SOFTWARE="1",
            GAME_UI_PREFERENCES_PATH=str(harness.build_dir / "dialogue-mcp-preferences.json"),
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.harness = harness.McpServerTest(methodName="runTest")
        self.build_dir = harness.build_dir
        self.process = self.harness._start_stdio_mcp_process()
        self.addCleanup(self.harness._shutdown_process, self.process)
        self.harness._initialize_stdio_mcp(self.process)
        self.session = {"proc": self.process, "next_request_id": 3}

    def engine(self, name, *args):
        return self.harness._mcp_engine_call(self.session, name, list(args), timeout=90)

    def call(self, handle, method, *args):
        return self.harness._mcp_handle_call(self.session, handle, method, list(args), timeout=90)

    def startMap(self, name):
        self.game = self.engine("CGameLoader.loadGame")
        self.engine("CGameLoader.startGameWithPlayer", self.game, name, "Warrior")
        self.game_map = self.call(self.game, "getMap")
        self.assertIsNotNone(self.game_map, f"Could not load {name} with current build resources")
        self.player = self.call(self.game_map, "getPlayer")
        self.assertIsNotNone(self.player)
        self.pump()

    def pump(self):
        loop = self.engine("event_loop.instance")
        for _ in range(3):
            self.call(loop, "run")

    def awaitTransition(self, expected_map_name):
        import test as harness

        destination = waitForRemoteTransition(
            self.game, expected_map_name, self.engine, self.call, harness.pump_event_loop_until
        )
        self.assertIsNotNone(destination, f"Transition to {expected_map_name} did not finish within one second")
        return destination

    def object(self, name):
        result = self.call(self.game_map, "getObjectByName", name)
        self.assertIsNotNone(result, name)
        return result

    def walkTo(self, name):
        target = self.object(name)
        data = json.loads(self.engine("jsonify", target))["properties"]
        destination = [data[key] for key in ("posx", "posy", "posz")]
        self.call(self.player, "moveTo", *destination)
        self.pump()
        return target

    def dialog(self, name):
        return self.call(self.game, "createObject", name)

    def action(self, dialog, action):
        self.call(dialog, "invokeAction", action)
        self.pump()

    def condition(self, dialog, condition):
        return self.call(dialog, "invokeCondition", condition)

    def questNames(self, method="getQuests"):
        properties = json.loads(self.engine("jsonify", self.player))["properties"]
        key = "completedQuests" if method == "getCompletedQuests" else "quests"
        return [
            quest["properties"].get("typeId") or quest["properties"].get("name") for quest in properties.get(key) or []
        ]

    def testAmuletAcceptanceAndReturnAreExplicitAndRewardIsGuarded(self):
        self.startMap("nouraajd")
        tavern = json.dumps(json.loads(self.engine("jsonify", self.dialog("tavernDialog1"))), ensure_ascii=False)
        self.assertIn("Matulog\u2019s", tavern)
        self.assertIn("Hmph\u2026", tavern)
        self.walkTo("oldWoman")
        self.assertEqual("not_started", self.call(self.game_map, "getStringProperty", "quest_state_amulet"))
        self.assertNotIn("amuletQuest", self.questNames())
        accept = self.dialog("questDialog")
        self.action(accept, "start_amulet_quest")
        self.assertIn("amuletQuest", self.questNames())
        self.assertEqual("active", self.call(self.game_map, "getStringProperty", "quest_state_amulet"))
        goblin = self.object("amuletGoblin")
        self.action(accept, "start_amulet_quest")
        self.assertEqual(goblin, self.object("amuletGoblin"))

        # Reach the authored thief before resolving this focused quest fixture's loot.
        # The native management suite separately exercises combat and automatic receipts.
        self.walkTo("amuletGoblin")
        thief_items = self.call(goblin, "getItems")
        self.assertEqual(1, self.call(goblin, "countItems", "preciousAmulet"))
        for item in thief_items:
            self.call(self.player, "addItem", item)
        self.call(self.game_map, "removeObjectByName", "amuletGoblin")
        self.pump()
        self.walkTo("oldWoman")
        before = self.call(self.player, "getGold")
        self.assertEqual(1, self.call(self.player, "countItems", "preciousAmulet"))
        hand_in = self.dialog("questReturnDialog")
        self.action(hand_in, "complete_amulet_quest")
        self.call(self.player, "checkQuests")
        self.assertEqual(before + 50, self.call(self.player, "getGold"))
        self.assertEqual(0, self.call(self.player, "countItems", "preciousAmulet"))
        self.assertEqual("returned", self.call(self.game_map, "getStringProperty", "quest_state_amulet"))
        self.assertIn("amuletQuest", self.questNames("getCompletedQuests"))
        self.assertIsNone(self.call(self.game_map, "getObjectByName", "oldWoman"))
        self.action(hand_in, "complete_amulet_quest")
        self.assertEqual(before + 50, self.call(self.player, "getGold"))

    def testCompanionReminderAndDepartureFollowAuthoredState(self):
        self.startMap("ninemarches")
        self.walkTo("ninemarchesStart")
        self.walkTo("companionKnight")
        dialog = self.dialog("knightDialog")
        self.assertFalse(self.condition(dialog, "questInProgress"))
        self.action(dialog, "start")
        self.assertTrue(self.condition(dialog, "questInProgress"))
        self.assertIn("haldaQuest", self.questNames())
        self.walkTo("banditCache")
        self.assertEqual(1, self.call(self.player, "countItems", "banditLedger"))
        self.walkTo("companionKnight")
        self.assertFalse(self.condition(dialog, "questInProgress"))
        self.assertTrue(self.condition(dialog, "can_recruit"))
        self.action(dialog, "recruit")
        self.assertTrue(self.condition(dialog, "is_joined"))
        self.assertEqual(1, self.call(self.player, "countItems", "aegisOfHalda"))
        # Reputation is an explicit boundary fixture; recruitment and movement above are real.
        self.call(self.player, "setNumericProperty", "reputation", -5)
        self.action(dialog, "banter")
        self.assertTrue(self.condition(dialog, "has_left"))
        self.assertFalse(self.condition(dialog, "is_joined"))
        self.action(dialog, "banter")
        self.assertEqual(1, self.call(self.player, "countItems", "aegisOfHalda"))

    def testUnreadLegacyVictorEndingSurvivesLoadAndDeparture(self):
        for outcome, objective in (("good_end", "survived"), ("bad_end", "was taken")):
            with self.subTest(outcome=outcome):
                self.startMap("nouraajd")
                self.walkTo("nouraajdTavern")
                self.action(self.dialog("tavernDialog1"), "asked_about_girl")
                self.action(self.dialog("tavernDialog2"), "talked_to_victor")
                self.walkTo("nouraajdTownHall")
                self.action(self.dialog("townHallDialog"), "spawn_cultists")
                gold_before = self.call(self.player, "getGold")
                if outcome == "good_end":
                    self.walkTo("cultLeaderQuest")
                    # Resolve the authored encounter as in the other focused quest fixtures.
                    self.call(self.game_map, "removeObjectByName", "cultLeaderQuest")
                    self.pump()
                else:
                    self.walkTo("nouraajdTavern")
                    for _ in range(76):
                        self.call(self.game_map, "move")
                    self.pump()
                gold_after = gold_before + (500 if outcome == "good_end" else 0)
                self.assertEqual(gold_after, self.call(self.player, "getGold"))
                self.assertEqual(outcome, self.call(self.game_map, "getStringProperty", "quest_state_victor"))
                self.call(self.player, "checkQuests")
                self.assertIn("victorQuest", self.questNames("getCompletedQuests"))
                self.walkTo("nouraajdChapel")

                # Recreate the pre-snapshot save format from a resolved, real-player route.
                # Retain all map defaults: their presence is what bypassed the old migration.
                snapshot = json.loads(self.engine("jsonify", self.game_map))
                properties = snapshot["properties"]
                for key in ("rolf", "main", "beren_chain", "octobogz_contract", "amulet", "victor"):
                    self.assertTrue(properties[f"quest_state_{key}"])
                saved_player = next(obj["properties"] for obj in properties["objects"] if obj.get("class") == "CPlayer")
                saved_player.pop("nouraajdVictorState", None)
                slot = "ui-legacy-victor-" + uuid.uuid4().hex
                save_path = self.build_dir / "save" / f"{slot}.json"
                save_path.parent.mkdir(exist_ok=True)
                self.assertFalse(save_path.exists())
                try:
                    save_path.write_text(json.dumps(snapshot), encoding="utf-8")
                    self.game = self.engine("CGameLoader.loadGame")
                    self.engine("CGameLoader.loadSavedGame", self.game, slot)
                    self.game_map = self.call(self.game, "getMap")
                    self.player = self.call(self.game_map, "getPlayer")
                    self.assertEqual(gold_after, self.call(self.player, "getGold"))
                    self.assertEqual(
                        outcome == "good_end", self.call(self.game_map, "getBoolProperty", "VICTOR_REWARD_GRANTED")
                    )
                    # Do not inspect/serialize the player or read a quest before leaving:
                    # computed journal properties used to hide the missing load-time migration.
                    # Queue departure before any event-loop pump, using the saved chapel position.
                    self.call(self.game, "changeMap", "ritual")
                    self.pump()
                    self.game_map = self.call(self.game, "getMap")
                    self.player = self.call(self.game_map, "getPlayer")
                    self.assertEqual("ritual", self.call(self.game_map, "getStringProperty", "mapName"))
                    self.assertEqual(gold_after, self.call(self.player, "getGold"))
                    self.assertEqual(outcome, self.call(self.player, "getStringProperty", "nouraajdVictorState"))
                    quests = self.call(self.player, "getCompletedQuests")
                    victor = next(quest for quest in quests if self.call(quest, "getTypeId") == "victorQuest")
                    journal = json.loads(self.engine("jsonify", victor))["properties"]
                    self.assertIn(objective, journal["objective"])
                    self.assertIn("No reward" if outcome == "bad_end" else "500 gold", journal["reward"])
                    self.assertEqual("", self.call(self.game_map, "getStringProperty", "quest_state_victor"))
                    # A later fresh source-map visit must not re-migrate an existing ending to its default.
                    self.call(self.game, "changeMap", "nouraajd")
                    self.pump()
                    self.game_map = self.call(self.game, "getMap")
                    self.player = self.call(self.game_map, "getPlayer")
                    self.assertEqual("nouraajd", self.call(self.game_map, "getStringProperty", "mapName"))
                    self.assertEqual(outcome, self.call(self.player, "getStringProperty", "nouraajdVictorState"))
                    self.assertEqual(gold_after, self.call(self.player, "getGold"))
                    quests = self.call(self.player, "getCompletedQuests")
                    victor = next(quest for quest in quests if self.call(quest, "getTypeId") == "victorQuest")
                    returned_journal = json.loads(self.engine("jsonify", victor))["properties"]
                    self.assertEqual(journal, returned_journal)
                    self.assertEqual(outcome, self.call(self.player, "getStringProperty", "nouraajdVictorState"))
                    self.assertEqual("not_started", self.call(self.game_map, "getStringProperty", "quest_state_victor"))
                    self.assertFalse(self.call(self.game_map, "getBoolProperty", "VICTOR_REWARD_GRANTED"))
                    self.assertEqual(gold_after, self.call(self.player, "getGold"))
                    self.walkTo("oldWoman")
                    self.action(self.dialog("questDialog"), "start_amulet_quest")
                    self.assertEqual("active", self.call(self.game_map, "getStringProperty", "quest_state_amulet"))
                    self.assertIn("amuletQuest", self.questNames())
                    self.assertEqual(outcome, self.call(self.player, "getStringProperty", "nouraajdVictorState"))
                    self.assertEqual(journal, json.loads(self.engine("jsonify", victor))["properties"])
                    self.assertEqual(gold_after, self.call(self.player, "getGold"))
                finally:
                    save_path.unlink(missing_ok=True)

    def testVossRequiresAllCagesAndCommitsOneSceneTransition(self):
        self.startMap("gravemoor")
        source_map = self.game_map
        self.walkTo("gravemoorStart")
        self.walkTo("quartermasterVoss")
        dialog = self.dialog("vossDialog")
        self.assertTrue(self.condition(dialog, "captives_missing"))
        self.assertFalse(self.condition(dialog, "ready_to_judge"))
        initial_gold = self.call(self.player, "getGold")
        self.action(dialog, "execute_voss")
        self.assertFalse(self.call(source_map, "getBoolProperty", "voss_judged"))
        self.assertEqual(initial_gold, self.call(self.player, "getGold"))
        for index, cage in enumerate(("loyalistCageWest", "loyalistCageEast", "loyalistCageNorth"), 1):
            self.walkTo(cage)
            self.assertEqual(index, self.call(source_map, "getNumericProperty", "loyalists_freed"))
            self.assertIsNone(self.call(source_map, "getObjectByName", cage))
        self.walkTo("quartermasterVoss")
        self.assertTrue(self.condition(dialog, "ready_to_judge"))
        self.assertFalse(self.condition(dialog, "captives_missing"))
        self.action(dialog, "execute_voss")
        destination = self.awaitTransition("usurpergate")
        self.assertNotEqual(source_map, destination)
        self.assertEqual("usurpergate", self.call(destination, "getStringProperty", "mapName"))
        self.assertTrue(self.call(source_map, "getBoolProperty", "voss_judged"))
        self.assertFalse(self.call(source_map, "getBoolProperty", "voss_spared"))
        self.assertTrue(self.call(source_map, "getBoolProperty", "judgment_reward_claimed"))
        self.assertIn("gravemoorQuest", self.questNames("getCompletedQuests"))

    def testCaptiveRequiresAnchorsAndLeaderBeforeRewardAndTransition(self):
        self.startMap("ritual")
        source_map = self.game_map
        self.assertTrue(self.call(source_map, "getBoolProperty", "ritual_initialized"))
        self.walkTo("ritualCaptive")
        dialog = self.dialog("capturedSoulDialog")
        self.assertTrue(self.condition(dialog, "need_more_work"))
        self.assertFalse(self.condition(dialog, "can_free_captive"))
        before_gold = self.call(self.player, "getGold")
        before_potions = self.call(self.player, "countItems", "LifePotion")
        self.action(dialog, "free_captive")
        self.assertFalse(self.call(source_map, "getBoolProperty", "captive_freed"))
        for anchor in ("anchorNorth", "anchorCrypt", "anchorSanctum"):
            self.walkTo(anchor)
            self.call(source_map, "removeObjectByName", anchor)
            self.pump()
        self.assertTrue(self.call(source_map, "getBoolProperty", "anchors_destroyed"))
        self.assertFalse(self.condition(dialog, "can_free_captive"))
        self.walkTo("ritualLeader")
        self.call(source_map, "removeObjectByName", "ritualLeader")
        self.pump()
        self.walkTo("ritualCaptive")
        self.assertTrue(self.condition(dialog, "can_free_captive"))
        self.assertFalse(self.condition(dialog, "need_more_work"))
        self.action(dialog, "free_captive")
        destination = self.awaitTransition("siege")
        self.assertNotEqual(source_map, destination)
        self.assertEqual("siege", self.call(destination, "getStringProperty", "mapName"))
        for flag in ("captive_freed", "good_ending", "ritual_finished", "reward_claimed"):
            self.assertTrue(self.call(source_map, "getBoolProperty", flag))
        self.assertEqual(before_gold + 300, self.call(self.player, "getGold"))
        self.assertEqual(before_potions + 1, self.call(self.player, "countItems", "LifePotion"))

    def testSeerReminderRewardAndMissingGateRequirementUseActualRoute(self):
        self.startMap("sunderedmarch")
        self.walkTo("gateThreshold")
        self.assertFalse(self.call(self.game_map, "getBoolProperty", "gate_open"))
        self.assertIsNotNone(self.call(self.game_map, "getObjectByName", "borderGate"))
        self.walkTo("keymasterCache")
        self.assertEqual(1, self.call(self.player, "countItems", "ironKey"))
        self.walkTo("gateThreshold")
        self.assertTrue(self.call(self.game_map, "getBoolProperty", "gate_open"))
        self.assertIsNone(self.call(self.game_map, "getObjectByName", "borderGate"))
        self.walkTo("seerHut")
        dialog = self.dialog("seerDialog")
        self.action(dialog, "start_seer_hunt")
        self.assertTrue(self.condition(dialog, "questInProgress"))
        self.action(dialog, "finish_seer_hunt")
        self.assertFalse(self.call(self.game_map, "getBoolProperty", "seer_done"))
        self.walkTo("bannerCache")
        self.walkTo("seerHut")
        self.assertFalse(self.condition(dialog, "questInProgress"))
        self.assertTrue(self.condition(dialog, "can_return_banner"))
        before_gold = self.call(self.player, "getGold")
        before_potions = self.call(self.player, "countItems", "GreaterLifePotion")
        self.action(dialog, "finish_seer_hunt")
        self.assertEqual(before_gold + 300, self.call(self.player, "getGold"))
        self.assertEqual(before_potions + 1, self.call(self.player, "countItems", "GreaterLifePotion"))
        self.action(dialog, "finish_seer_hunt")
        self.assertEqual(before_gold + 300, self.call(self.player, "getGold"))
        self.assertEqual(before_potions + 1, self.call(self.player, "countItems", "GreaterLifePotion"))


class DialogueTransitionBoundaryTest(unittest.TestCase):
    def sharedWait(self, model):
        source = Path(__file__).resolve().parents[1] / "test.py"
        module = ast.parse(source.read_text(encoding="utf-8"))
        helper = next(
            node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "pump_event_loop_until"
        )

        def rejectNativeImport():
            self.fail("Remote transition polling must not load a native engine in the test runner")

        namespace = {
            "time": SimpleNamespace(monotonic=lambda: model.now, sleep=model.sleep),
            "load_game_module": rejectNativeImport,
        }
        exec(compile(ast.Module(body=[helper], type_ignores=[]), str(source), "exec"), namespace)
        return namespace["pump_event_loop_until"]

    def model(self, *, destination_after=5, idle_after=13, destination_name="siege"):
        class Remote:
            def __init__(self):
                self.now = 0.0
                self.snapshots = 0
                self.pending_observations = []

            def sleep(self, seconds):
                self.now += seconds

            def engine(self, name):
                self.assertEqual("event_loop.instance", name)
                return "remoteLoop"

            def call(self, handle, method, *arguments):
                if (handle, method) == ("remoteLoop", "run"):
                    self.snapshots += 1
                    self.now += 0.01
                    return True
                if (handle, method) == ("game", "getSceneManager"):
                    return "manager"
                if (handle, method) == ("game", "getMap"):
                    return (
                        "destination"
                        if destination_after is not None and self.snapshots >= destination_after
                        else "source"
                    )
                if method == "getStringProperty":
                    self.assertEqual(("mapName",), arguments)
                    return destination_name if handle == "destination" else "sourceMap"
                if (handle, method) == ("manager", "isTransitionPending"):
                    pending = idle_after is None or self.snapshots < idle_after
                    self.pending_observations.append((self.snapshots, pending))
                    return pending
                raise AssertionError((handle, method, arguments))

        remote = Remote()
        remote.assertEqual = self.assertEqual
        return remote

    def wait(self, model, expected="siege"):
        return waitForRemoteTransition("game", expected, model.engine, model.call, self.sharedWait(model))

    def testRemoteTransitionWaitsPastTenSnapshotsForDestinationAndIdle(self):
        model = self.model()
        for _ in range(3):
            model.call("remoteLoop", "run")
        self.assertEqual("source", model.call("game", "getMap"))
        self.assertEqual("destination", self.wait(model))
        self.assertEqual(13, model.snapshots)
        self.assertTrue(any(pending for _phase, pending in model.pending_observations))
        self.assertEqual((13, False), model.pending_observations[-1])

    def testInstalledDestinationRemainsPendingUntilEntryFinishes(self):
        model = self.model(destination_after=1, idle_after=7)
        self.assertEqual("destination", self.wait(model))
        self.assertEqual(7, model.snapshots)
        self.assertEqual((1, True), model.pending_observations[0])

    def testIdleSourceCannotForgeDestinationSuccess(self):
        model = self.model(destination_after=None, idle_after=1)
        self.assertIsNone(self.wait(model))
        self.assertGreaterEqual(model.now, 1.0)
        self.assertEqual("source", model.call("game", "getMap"))

    def testStuckDestinationTimesOutWithoutForgingSuccess(self):
        model = self.model(destination_after=1, idle_after=None)
        self.assertIsNone(self.wait(model))
        self.assertGreaterEqual(model.now, 1.0)
        self.assertTrue(all(pending for _phase, pending in model.pending_observations))

    def testWrongDestinationTimesOutWithoutForgingSuccess(self):
        model = self.model(destination_after=1, idle_after=1, destination_name="wrongMap")
        self.assertIsNone(self.wait(model))
        self.assertGreaterEqual(model.now, 1.0)
        self.assertEqual([], model.pending_observations)

    def testOnlyTheTwoTransitionBoundariesWaitForObservableCompletion(self):
        module = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        runtime = next(
            node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "DialogueMcpWalkthroughTest"
        )
        waits = {
            method.name: [
                call.args[0].value
                for call in ast.walk(method)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "awaitTransition"
            ]
            for method in runtime.body
            if isinstance(method, ast.FunctionDef) and method.name.startswith("test")
        }
        self.assertEqual(
            {
                "testVossRequiresAllCagesAndCommitsOneSceneTransition": ["usurpergate"],
                "testCaptiveRequiresAnchorsAndLeaderBeforeRewardAndTransition": ["siege"],
            },
            {name: destinations for name, destinations in waits.items() if destinations},
        )


if __name__ == "__main__":
    unittest.main()
