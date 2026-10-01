# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Real stdio MCP movement, authored discoveries, combat and race services."""

import unittest

from tests.test_ui_mcp_dialogue import DialogueMcpWalkthroughTest


class PlayerIdentityMcpTest(unittest.TestCase):
    def setUp(self):
        self.driver = DialogueMcpWalkthroughTest(methodName="runTest")
        self.addCleanup(self.driver.doCleanups)
        self.driver.setUp()

    def startIdentityMap(self, class_id, race_id="humanRace"):
        driver = self.driver
        driver.game = driver.engine("CGameLoader.loadGame")
        driver.engine("CGameLoader.startGameWithPlayer", driver.game, "nouraajd", class_id, race_id)
        driver.game_map = driver.call(driver.game, "getMap")
        driver.player = driver.call(driver.game_map, "getPlayer")
        driver.pump()

    def testAuthoredClassDiscoveriesLeadToRepeatedPaidCombatRefunds(self):
        driver = self.driver
        cases = (
            ("Warrior", "nouraajdDoor", "doorDialog", "brace_gate", "warrior_barricades", "Barrier", 17),
            ("Assasin", "nouraajdTavern", "tavernDialog1", "shadow_robed_men", "assasin_trails", "SneakAttack", 15),
            (
                "Sorcerer",
                "nouraajdChapel",
                "berenDialog",
                "decode_stained_glass_ward",
                "sorcerer_sigils",
                "FrostBolt",
                20,
            ),
        )
        for class_id, landmark, dialog_id, action, counter, ability_id, cost in cases:
            with self.subTest(class_id=class_id):
                self.startIdentityMap(class_id)
                driver.walkTo(landmark)
                dialog = driver.dialog(dialog_id)
                driver.action(dialog, action)
                self.assertEqual(1, driver.call(driver.player, "getNumericProperty", counter))
                driver.action(dialog, action)
                self.assertEqual(1, driver.call(driver.player, "getNumericProperty", counter))
                ability = driver.dialog(ability_id)
                self.assertEqual(cost, driver.call(ability, "getNumericProperty", "manaCost"))
                driver.walkTo("ambientMarketRationLedger")
                coords = driver.call(driver.player, "getCoords")
                spawned_template = driver.call(driver.game_map, "addObjectByName", "Cultist", coords)
                self.assertEqual("Cultist", spawned_template)
                enemies = [
                    actor
                    for actor in driver.call(driver.game_map, "getObjectsAtCoords", coords)
                    if driver.call(actor, "getTypeId") == "Cultist"
                ]
                self.assertEqual(1, len(enemies), "the combat fixture must register one Cultist on the market cell")
                enemy = enemies[0]
                driver.call(enemy, "healProc", 100)
                hp_before = driver.call(enemy, "getHp")
                for _ in range(2):
                    driver.call(driver.player, "setNumericProperty", "mana", cost)
                    self.assertEqual(3, driver.call(ability, "getCommittedManaRefund", driver.player))
                    self.assertEqual(cost, driver.call(driver.player, "getMana"))
                    driver.call(ability, "onAction", driver.player, driver.player if class_id == "Warrior" else enemy)
                    driver.pump()
                    self.assertEqual(3, driver.call(driver.player, "getMana"))
                if class_id == "Sorcerer":
                    self.assertLess(
                        driver.call(enemy, "getHp"), hp_before, "the real frost cast must damage its opponent"
                    )
                driver.call(driver.player, "setNumericProperty", "mana", cost - 1)
                effect_count = len(driver.call(driver.player, "getEffects"))
                driver.call(ability, "onAction", driver.player, driver.player if class_id == "Warrior" else enemy)
                self.assertEqual(cost - 1, driver.call(driver.player, "getMana"))
                self.assertEqual(effect_count, len(driver.call(driver.player, "getEffects")))

    def testExistingClueAndRouteDiscoveriesStillStrengthenPaidEffects(self):
        driver = self.driver
        cases = (
            (
                "Inquisitor",
                "nouraajdChapel",
                "berenDialog",
                "inspect_stained_glass",
                "inquisitor_clues",
                "SanctifiedWard",
                "SanctifiedWardEffect",
                "normalResist",
                5,
            ),
            (
                "Wayfarer",
                "nouraajdTownHall",
                "townHallDialog",
                "chart_wayfarer_route",
                "wayfarer_routes",
                "WayfarersStride",
                "WayfarersStrideEffect",
                "block",
                6,
            ),
        )
        for class_id, landmark, dialog_id, action, counter, ability_id, effect_id, stat, value in cases:
            with self.subTest(class_id=class_id):
                self.startIdentityMap(class_id)
                driver.walkTo(landmark)
                dialog = driver.dialog(dialog_id)
                driver.action(dialog, action)
                driver.action(dialog, action)
                self.assertEqual(1, driver.call(driver.player, "getNumericProperty", counter))
                ability = driver.dialog(ability_id)
                driver.call(
                    driver.player, "setNumericProperty", "mana", driver.call(ability, "getNumericProperty", "manaCost")
                )
                driver.call(ability, "onAction", driver.player, driver.player)
                driver.pump()
                effect = next(
                    effect
                    for effect in driver.call(driver.player, "getEffects")
                    if driver.call(effect, "getTypeId") == effect_id
                )
                self.assertEqual(1, driver.call(effect, "getNumericProperty", counter))
                bonus = driver.call(effect, "getObjectProperty", "bonus")
                self.assertEqual(value, driver.call(bonus, "getNumericProperty", stat))
                self.assertEqual(0, driver.call(ability, "getCommittedManaRefund", driver.player))

    def testRaceAidRequiresTownHallMovementAndCannotBeReclaimed(self):
        driver = self.driver
        cases = (
            ("humanRace", "HumanRation", 20, 0, 0),
            ("outlanderRace", "OutlanderRations", -5, 5, 5),
            ("highlanderRace", "HighlanderAid", -5, 10, 0),
            ("wandererRace", "WandererFocus", -5, 0, 10),
        )
        for race_id, suffix, gold_delta, hp_bonus, mana_bonus in cases:
            with self.subTest(race_id=race_id):
                self.startIdentityMap("Warrior", race_id)
                driver.walkTo("nouraajdTownHall")
                max_hp = driver.call(driver.player, "getHpMax")
                max_mana = driver.call(driver.player, "getManaMax")
                hp = max(1, max_hp - 12)
                mana = max(0, max_mana - 12)
                driver.call(driver.player, "setNumericProperty", "hp", hp)
                driver.call(driver.player, "setNumericProperty", "mana", mana)
                driver.call(driver.player, "setNumericProperty", "gold", 30)
                dialog = driver.dialog("townHallDialog")
                self.assertTrue(driver.condition(dialog, "canOffer" + suffix))
                driver.call(driver.player, "setStringProperty", "raceId", "legacyUnknownRace")
                self.assertTrue(driver.condition(dialog, "canOffer" + suffix))
                driver.action(dialog, "claim" + suffix)
                expected = (30 + gold_delta, min(max_hp, hp + hp_bonus), min(max_mana, mana + mana_bonus))
                observed = tuple(driver.call(driver.player, method) for method in ("getGold", "getHp", "getMana"))
                self.assertEqual(expected, observed)
                self.assertTrue(driver.call(driver.player, "getBoolProperty", "nouraajdRaceServiceClaimed"))
                self.assertEqual(race_id, driver.call(driver.player, "getStringProperty", "nouraajdRaceServiceKind"))
                self.assertFalse(driver.condition(dialog, "canOffer" + suffix))
                driver.action(dialog, "claim" + suffix)
                self.assertEqual(
                    expected, tuple(driver.call(driver.player, method) for method in ("getGold", "getHp", "getMana"))
                )
