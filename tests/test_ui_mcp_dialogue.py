# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authored dialogue routes through the stdio MCP server and actual player movement."""

import json
import os
import unittest
from unittest.mock import patch


class DialogueMcpWalkthroughTest(unittest.TestCase):
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
        destination = self.call(self.game, "getMap")
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
        destination = self.call(self.game, "getMap")
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


if __name__ == "__main__":
    unittest.main()
