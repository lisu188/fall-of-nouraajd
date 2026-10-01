# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import unittest
import uuid

from tests import test_ui_mcp_dialogue as dialogue_mcp


class OctobogzMcpWalkthroughTest(unittest.TestCase):
    setUp = dialogue_mcp.DialogueMcpWalkthroughTest.setUp
    engine = dialogue_mcp.DialogueMcpWalkthroughTest.engine
    call = dialogue_mcp.DialogueMcpWalkthroughTest.call
    pump = dialogue_mcp.DialogueMcpWalkthroughTest.pump
    object = dialogue_mcp.DialogueMcpWalkthroughTest.object
    walkTo = dialogue_mcp.DialogueMcpWalkthroughTest.walkTo
    dialog = dialogue_mcp.DialogueMcpWalkthroughTest.dialog
    action = dialogue_mcp.DialogueMcpWalkthroughTest.action
    questNames = dialogue_mcp.DialogueMcpWalkthroughTest.questNames

    def state(self):
        return json.loads(self.call(self.game_map, "getStringProperty", "octobogzHuntRegistry"))

    def refresh(self):
        self.game_map = self.call(self.game, "getMap")
        self.player = self.call(self.game_map, "getPlayer")

    def useOrdinaryCombatController(self, player_class):
        # Attachment and save restoration install the interactive controller.
        template = self.call(self.game, "createObject", player_class)
        self.call(self.player, "setFightController", self.call(template, "getFightController"))

    def defeat(self, slot):
        record = self.state()["slots"][slot]
        self.assertEqual("living", record["status"])
        self.walkTo(record["name"])
        self.assertGreater(
            self.call(self.player, "getNumericProperty", "hp"), 0, "Ordinary player loadout failed against " + slot
        )
        self.assertIsNone(
            self.call(self.game_map, "getObjectByName", record["name"]), "Real movement and combat must defeat " + slot
        )
        self.assertEqual("dead", self.state()["slots"][slot]["status"])

    def testWarriorAndSorcererFinishThreeRealEncountersWithPartialReloadAndRewardOnce(self):
        for player_class in ("Warrior", "Sorcerer"):
            with self.subTest(player_class=player_class):
                self.game = self.engine("CGameLoader.loadGame")
                self.engine("CGameLoader.startGameWithPlayer", self.game, "nouraajd", player_class)
                self.refresh()
                self.pump()
                starting_blades = self.call(self.player, "countItems", "ShadowBlade")
                # The template's existing AI uses ordinary spells, equipment and carried potions.
                self.useOrdinaryCombatController(player_class)
                # Earn the authored class discovery reward through its NPC action.
                if player_class == "Warrior":
                    self.walkTo("nouraajdDoor")
                    self.action(self.dialog("doorDialog"), "brace_gate")
                else:
                    self.walkTo("nouraajdChapel")
                    self.action(self.dialog("berenDialog"), "decode_stained_glass_ward")
                self.walkTo("questGiver")
                if player_class == "Warrior":
                    self.action(self.dialog("dialog"), "accept_quest")
                    self.assertIn("octoBogzQuest", self.questNames())
                self.walkTo("ambientOctobogzNet")
                self.walkTo("cave2")
                self.assertEqual("scout", self.state()["stage"])
                self.defeat("scout")
                self.assertEqual("brood", self.state()["stage"])
                self.assertFalse(self.call(self.game_map, "getBoolProperty", "octobogzHuntCleared"))

                slot = "mcp-octobogz-" + uuid.uuid4().hex
                save_path = self.build_dir / "save" / (slot + ".json")
                self.assertFalse(save_path.exists())
                try:
                    self.engine("CMapLoader.save", self.game_map, slot)
                    self.assertTrue(save_path.is_file())
                    old_state = self.state()
                    self.game = self.engine("CGameLoader.loadGame")
                    self.engine("CGameLoader.loadSavedGame", self.game, slot)
                    self.refresh()
                    self.pump()
                    self.assertEqual(old_state, self.state())
                    self.useOrdinaryCombatController(player_class)
                    self.defeat("alpha")
                    self.assertIsNotNone(self.call(self.game_map, "getObjectByName", "cave2"))
                    self.assertFalse(self.call(self.game_map, "getBoolProperty", "OCTOBOGZ_SLAIN"))
                    gold_before_final = self.call(self.player, "getGold")
                    self.defeat("brood")
                    self.assertEqual("cleared", self.state()["stage"])
                    self.assertTrue(self.call(self.game_map, "getBoolProperty", "OCTOBOGZ_SLAIN"))
                    self.assertIsNone(self.call(self.game_map, "getObjectByName", "cave2"))
                    self.walkTo("questGiver")
                    gold_before_claim = self.call(self.player, "getGold")
                    self.action(self.dialog("dialog"), "accept_quest")
                    gold_after_claim = self.call(self.player, "getGold")
                    if player_class == "Sorcerer":
                        self.assertEqual(gold_before_claim + 1000, gold_after_claim)
                    else:
                        self.assertGreaterEqual(gold_before_claim, gold_before_final + 1000)
                        self.assertEqual(gold_before_claim, gold_after_claim)
                    self.assertEqual(starting_blades + 1, self.call(self.player, "countItems", "ShadowBlade"))
                    self.assertIn("octoBogzQuest", self.questNames("getCompletedQuests"))
                    self.action(self.dialog("dialog"), "accept_quest")
                    self.assertEqual(gold_after_claim, self.call(self.player, "getGold"))
                    self.assertEqual(starting_blades + 1, self.call(self.player, "countItems", "ShadowBlade"))
                    print("MCP OctoBogz real combat completed for", player_class, flush=True)
                finally:
                    save_path.unlink(missing_ok=True)
                    save_path.with_suffix(".json.bak").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
