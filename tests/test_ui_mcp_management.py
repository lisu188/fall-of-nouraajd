# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Management route checks through the existing stream-draining stdio MCP harness."""

import ast
import json
import os
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch


class CraftRecipeLocationTest(unittest.TestCase):
    def testMcpSetResultsExposeEachValueAsAReusableHandle(self):
        import mcp

        root = Path(__file__).resolve().parents[1]
        server = mcp.EngineMcpServer(root, root / "cmake-build-release")
        first, second = object(), object()
        for collection in ({first, second}, frozenset((first, second))):
            result = server._serialize_result(collection)
            self.assertIsInstance(result, list)
            self.assertEqual(2, len(result))
            self.assertEqual({first, second}, {server._resolve_handle_references(value) for value in result})
        self.assertEqual(2, len(server.handles), "Repeated collection reads must reuse object handles")

    def testCraftingRequiresTheActiveStationAndMatchingPlayerLocation(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "res/game.py").read_text(encoding="utf-8"))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "craftRecipe")
        building = type("CBuilding", (), {})
        namespace = {"CBuilding": building}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "craftRecipe", "exec"), namespace)
        station = building()
        station.getName = lambda: "alchemyTable1"
        station.getType = lambda: "CraftingStation"
        station.getBoolProperty = lambda name: True
        station.getCoords = lambda: types.SimpleNamespace(x=4, y=5, z=0)
        player = types.SimpleNamespace(getCoords=lambda: types.SimpleNamespace(x=0, y=0, z=0))
        game_map = types.SimpleNamespace(getPlayer=lambda: player, getObjectByName=lambda name: station)
        game_instance = types.SimpleNamespace(getMap=lambda: game_map)
        crafting = types.SimpleNamespace(
            get_runtime=lambda: types.SimpleNamespace(get_recipe=lambda name: {"station": "alchemyTable"}),
            _get_station_identifier=lambda value: "alchemyTable",
            craft_recipe=Mock(return_value={"ok": True, "reason": "success"}),
        )
        with patch.dict("sys.modules", plugins=types.SimpleNamespace(crafting=crafting)):
            craft = namespace["craftRecipe"]
            self.assertEqual("missing:player", craft(None, station, "brew_life_potion")["reason"])
            self.assertEqual("invalid:station", craft(game_instance, None, "brew_life_potion")["reason"])
            self.assertEqual("distant:station", craft(game_instance, station, "brew_life_potion")["reason"])
            player.getCoords = station.getCoords
            game_map.getObjectByName = lambda name: None
            self.assertEqual("invalid:station", craft(game_instance, station, "brew_life_potion")["reason"])
            game_map.getObjectByName = lambda name: station
            station.getBoolProperty = lambda name: False
            self.assertEqual("disabled:station", craft(game_instance, station, "brew_life_potion")["reason"])
            station.getBoolProperty = lambda name: True
            eligible_runtime = crafting.get_runtime
            crafting.get_runtime = lambda: types.SimpleNamespace(get_recipe=lambda name: None)
            self.assertEqual("missing:recipe", craft(game_instance, station, "unknown_recipe")["reason"])
            crafting.get_runtime = eligible_runtime
            crafting._get_station_identifier = lambda value: "scribeDesk"
            self.assertEqual("invalid:recipeStation", craft(game_instance, station, "brew_life_potion")["reason"])
            crafting.craft_recipe.assert_not_called()
            crafting._get_station_identifier = lambda value: "alchemyTable"
            self.assertTrue(craft(game_instance, station, "brew_life_potion")["ok"])
            crafting.craft_recipe.assert_called_once_with(game_instance, player, "brew_life_potion")


class ManagementMcpWalkthroughTest(unittest.TestCase):
    def setUp(self):
        import test as harness

        if not any(
            list(path.glob("_game*.pyd")) + list(path.glob("_game*.so"))
            for path in [harness.build_dir, *harness.extension_dirs]
        ):
            self.skipTest("Current _game extension required for management MCP walkthroughs")
        environment = patch.dict(
            os.environ,
            SDL_VIDEODRIVER="dummy",
            SDL_AUDIODRIVER="dummy",
            SDL_RENDER_DRIVER="software",
            LIBGL_ALWAYS_SOFTWARE="1",
            GAME_UI_PREFERENCES_PATH=str(harness.build_dir / "management-mcp-preferences.json"),
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.harness = harness.McpServerTest(methodName="runTest")
        self.process = self.harness._start_stdio_mcp_process()
        self.addCleanup(self.harness._shutdown_process, self.process)
        self.harness._initialize_stdio_mcp(self.process)
        self.session = {"proc": self.process, "next_request_id": 3}
        self.game = self.engine("CGameLoader.loadGame")
        self.engine("CGameLoader.startGameWithPlayer", self.game, "nouraajd", "Warrior")
        self.game_map = self.call(self.game, "getMap")
        self.player = self.call(self.game_map, "getPlayer")
        self.pump()

    def engine(self, name, *args):
        return self.harness._mcp_engine_call(self.session, name, list(args), timeout=90)

    def call(self, handle, method, *args):
        return self.harness._mcp_handle_call(self.session, handle, method, list(args), timeout=90)

    def pump(self):
        loop = self.engine("event_loop.instance")
        for _ in range(3):
            self.call(loop, "run")

    def walkTo(self, name):
        target = self.call(self.game_map, "getObjectByName", name)
        self.assertIsNotNone(target, name)
        properties = json.loads(self.engine("jsonify", target))["properties"]
        destination = [properties[key] for key in ("posx", "posy", "posz")]
        self.call(self.player, "moveTo", *destination)
        self.pump()
        player_data = json.loads(self.engine("jsonify", self.player))["properties"]
        self.assertEqual(destination, [player_data[key] for key in ("posx", "posy", "posz")])
        return target

    def testCraftingAtTheAuthoredStationConsumesExactCostsAndRevalidates(self):
        station = self.call(self.game_map, "getObjectByName", "alchemyTable1")
        self.assertEqual(
            "distant:station", self.engine("craftRecipe", self.game, station, "brew_life_potion")["reason"]
        )
        self.walkTo("alchemyTable1")
        self.call(self.player, "setNumericProperty", "gold", 100)
        for _ in range(2):
            self.call(self.player, "addItem", "LesserLifePotion")
        before = self.call(self.player, "countItems", "LesserLifePotion")
        outputs = self.call(self.player, "countItems", "LifePotion")
        self.assertEqual(
            "invalid:recipeStation",
            self.engine("craftRecipe", self.game, station, "craft_town_portal_scroll")["reason"],
        )
        self.assertEqual(before, self.call(self.player, "countItems", "LesserLifePotion"))
        result = self.engine("craftRecipe", self.game, station, "brew_life_potion")
        self.pump()
        self.assertTrue(result["ok"], result)
        self.assertEqual(before - 2, self.call(self.player, "countItems", "LesserLifePotion"))
        self.assertEqual(outputs + 1, self.call(self.player, "countItems", "LifePotion"))
        self.assertEqual(80, self.call(self.player, "getGold"))
        self.call(self.player, "setNumericProperty", "gold", 0)
        remaining = self.call(self.player, "countItems", "LesserLifePotion")
        rejected = self.engine("craftRecipe", self.game, station, "brew_life_potion")
        self.assertFalse(rejected["ok"])
        self.assertEqual(remaining, self.call(self.player, "countItems", "LesserLifePotion"))
        self.assertEqual(outputs + 1, self.call(self.player, "countItems", "LifePotion"))

    def testTradeUsesTheVisitedMerchantsActualStockAndRevalidatesOwnership(self):
        merchant = self.walkTo("market1")
        market = self.call(merchant, "getObjectProperty", "market")
        self.assertIsNotNone(market)
        item = self.call(self.game, "createObject", "Scroll")
        self.call(self.player, "addItem", item)
        self.call(self.player, "setNumericProperty", "gold", 10000)
        before = self.call(self.player, "countItems", "Scroll")
        sale_price = self.call(market, "getBuyCost", item)
        buy_price = self.call(market, "getSellCost", item)
        self.assertGreater(sale_price, 0)
        self.assertEqual(before, self.call(self.player, "countItems", "Scroll"))
        self.assertEqual(10000, self.call(self.player, "getGold"))
        self.call(market, "buyItem", self.player, item)
        self.assertEqual(before - 1, self.call(self.player, "countItems", "Scroll"))
        self.assertEqual(10000 + sale_price, self.call(self.player, "getGold"))
        self.call(market, "buyItem", self.player, item)
        self.assertEqual(10000 + sale_price, self.call(self.player, "getGold"))
        self.assertTrue(self.call(market, "sellItem", self.player, item))
        self.assertEqual(before, self.call(self.player, "countItems", "Scroll"))
        self.assertEqual(10000 + sale_price - buy_price, self.call(self.player, "getGold"))
        self.assertFalse(self.call(market, "sellItem", self.player, item))
        self.assertEqual(before, self.call(self.player, "countItems", "Scroll"))

    def testInspectionAtTheAuthoredMerchantLoadsAbilityDescriptionsAndItemBonusesWithoutTakingTurns(self):
        merchant = self.walkTo("market1")
        market = self.call(merchant, "getObjectProperty", "market")
        stock = self.call(market, "getItems")
        weapon = next((item for item in stock if self.call(item, "getTypeId") == "DaggerOfVileHeart"), None)
        self.assertIsNotNone(weapon, "The visited merchant must offer its authored Dagger of Vile Heart")
        actions = self.call(self.player, "getEffectiveInteractions")
        attack = next((action for action in actions if self.call(action, "getTypeId") == "Attack"), None)
        self.assertIsNotNone(attack, "Inspection must use the real Warrior's owned Attack ability")
        description = self.call(attack, "getStringProperty", "description")
        self.assertIn("attack", description.lower(), "The owned ability must explain its authored effect")
        mana_cost = self.call(attack, "getNumericProperty", "manaCost")
        self.assertEqual(0, mana_cost, "Inspection must retain the authored Attack mana cost")
        self.assertFalse(self.call(attack, "getBoolProperty", "selfTarget"))
        bonus = self.call(weapon, "getObjectProperty", "bonus")
        stat_values = {
            label: self.call(bonus, "getNumericProperty", key)
            for key, label in (
                ("dmgMin", "Minimum damage"),
                ("dmgMax", "Maximum damage"),
                ("crit", "Critical chance"),
            )
        }
        self.assertTrue(all(value > 0 for value in stat_values.values()), "The stock item must have real stat bonuses")

        def snapshot():
            return {
                "turn": self.call(self.game_map, "getTurn"),
                "player": json.loads(self.engine("jsonify", self.player)),
                "market": json.loads(self.engine("jsonify", market)),
            }

        before = snapshot()
        for _ in range(3):
            self.assertEqual(description, self.call(attack, "getStringProperty", "description"))
            self.assertEqual(mana_cost, self.call(attack, "getNumericProperty", "manaCost"))
            self.assertFalse(self.call(attack, "getBoolProperty", "selfTarget"))
            self.assertEqual("Dagger of Vile Heart", self.call(weapon, "getStringProperty", "label"))
            for key, label in (("dmgMin", "Minimum damage"), ("dmgMax", "Maximum damage"), ("crit", "Critical chance")):
                self.assertEqual(stat_values[label], self.call(bonus, "getNumericProperty", key))
        self.pump()
        self.assertEqual(before, snapshot(), "Repeated inspection must preserve turns, resources, equipment, and stock")

    def testNarrativeRecoveryConsumesOwnedNativeHealingWithoutTakingTurns(self):
        from tests.narrative_walkthrough import NarrativeWalkthrough

        self.walkTo("market1")
        healing = self.call(self.game, "createObject", "FullLifePotion")
        mana = self.call(self.game, "createObject", "ManaPotion")
        mixed = self.call(self.game, "createObject", "OasisWater")
        reusable = self.call(self.game, "createObject", "CItem")
        self.call(reusable, "addTag", "heal")
        self.call(reusable, "setNumericProperty", "power", 1)
        for item in (healing, mana, mixed, reusable):
            self.call(self.player, "addItem", item)
        hp_max = self.call(self.player, "getHpMax")
        wounded_hp = max(1, hp_max * 2 // 5)
        self.call(self.player, "setNumericProperty", "hp", wounded_hp)
        self.call(self.player, "takeMana", max(1, self.call(self.player, "getManaMax") // 2))
        self.assertTrue(self.call(healing, "hasTag", "heal"))
        self.assertFalse(self.call(healing, "hasTag", "mana"))
        self.assertEqual("LifePotion", self.call(healing, "getType"))
        self.assertTrue(self.call(healing, "getBoolProperty", "singleUse"))
        power = self.call(healing, "getNumericProperty", "power")
        self.assertEqual(5, power)
        self.assertFalse(self.call(mana, "hasTag", "heal"))
        self.assertTrue(self.call(mixed, "hasTag", "heal"))
        self.assertTrue(self.call(mixed, "hasTag", "mana"))
        self.assertFalse(self.call(reusable, "getBoolProperty", "singleUse"))
        self.assertLess(wounded_hp * 4, hp_max * 3)
        self.assertGreater(wounded_hp + hp_max, hp_max, "The native potion must overflow HP before capping")
        expected_hp = min(hp_max, wounded_hp + max(1, int(power * 20 / 100.0 * hp_max)))

        driver = NarrativeWalkthrough(
            lambda name, args: self.engine(name, *args),
            lambda handle, method, args: self.call(handle, method, *args),
            self.game,
            self.game_map,
            self.player,
        )

        def snapshot():
            return {
                "turn": self.call(self.game_map, "getTurn"),
                "mana": self.call(self.player, "getMana"),
                "manaMax": self.call(self.player, "getManaMax"),
                "hpMax": self.call(self.player, "getHpMax"),
                "gold": self.call(self.player, "getGold"),
                "experience": self.call(self.player, "getNumericProperty", "exp"),
                "level": self.call(self.player, "getLevel"),
                "class": self.call(self.player, "getTypeId"),
                "quests": sorted(quest["__handle__"] for quest in self.call(self.player, "getQuests")),
                "completedQuests": sorted(
                    quest["__handle__"] for quest in self.call(self.player, "getCompletedQuests")
                ),
                "equipped": json.loads(self.engine("jsonify", self.player))["properties"].get("equipped"),
                "coords": driver.coords(),
            }

        before = snapshot()
        owned_before = {item["__handle__"] for item in self.call(self.player, "getItems")}
        self.assertIn(healing["__handle__"], owned_before)
        self.assertIn(mana["__handle__"], owned_before)
        driver.recoverBeforeAction("native inventory regression")
        self.pump()
        self.assertEqual(expected_hp, self.call(self.player, "getHp"))
        self.assertEqual(hp_max, expected_hp)
        owned_after = {item["__handle__"] for item in self.call(self.player, "getItems")}
        self.assertNotIn(healing["__handle__"], owned_after)
        self.assertIn(mana["__handle__"], owned_after)
        self.assertEqual(owned_before - {healing["__handle__"]}, owned_after)
        self.assertEqual(before, snapshot(), "Native recovery must preserve progression, resources, and turns")
        self.assertEqual("", self.call(self.player, "getStringProperty", "uiDefeatReceipt"))
        self.assertEqual(0, driver.log["movementSteps"])
        self.assertEqual(0, driver.log["mapTurns"])
        self.assertEqual(["FullLifePotion"], [entry["typeId"] for entry in driver.log["recoveryItems"]])

        self.call(self.player, "addItem", "LesserLifePotion")
        self.call(self.player, "setNumericProperty", "hp", wounded_hp)
        receipt = '{"map":"Controlled earlier defeat","hp":0,"lostItemCount":0}'
        self.call(self.player, "setStringProperty", "uiDefeatReceipt", receipt)
        guarded_before = snapshot()
        guarded_items = {item["__handle__"] for item in self.call(self.player, "getItems")}
        recovery_before = list(driver.log["recoveryItems"])
        with self.assertRaises(AssertionError) as error:
            driver.recoverBeforeAction("native direct-call receipt regression")
        self.assertEqual("Walkthrough player was defeated", error.exception.args[0]["reason"])
        self.assertEqual(receipt, error.exception.args[0]["uiDefeatReceipt"])
        self.assertEqual(receipt, self.call(self.player, "getStringProperty", "uiDefeatReceipt"))
        self.assertEqual(wounded_hp, self.call(self.player, "getHp"))
        self.assertEqual(guarded_items, {item["__handle__"] for item in self.call(self.player, "getItems")})
        self.assertEqual(guarded_before, snapshot())
        self.assertEqual(recovery_before, driver.log["recoveryItems"])

    def testCombatActionAtTheAuthoredEnemyUsesAnOwnedAbility(self):
        self.walkTo("cave1")
        self.call(self.game_map, "removeObjectByName", "cave1")
        self.call(self.player, "checkQuests")
        self.pump()
        enemy = self.call(self.game_map, "getObjectByName", "gooby1")
        self.assertIsNotNone(enemy, "Destroying the authored cave must spawn Gooby")
        enemy_data = json.loads(self.engine("jsonify", enemy))["properties"]
        destination = [enemy_data[key] for key in ("posx", "posy", "posz")]
        approach = [destination[0] - 1, destination[1], destination[2]]
        self.call(self.player, "moveTo", *approach)
        self.pump()
        player_data = json.loads(self.engine("jsonify", self.player))["properties"]
        self.assertEqual(approach, [player_data[key] for key in ("posx", "posy", "posz")])
        self.call(self.player, "moveTo", *destination)
        self.pump()
        player_data = json.loads(self.engine("jsonify", self.player))["properties"]
        self.assertEqual(approach, [player_data[key] for key in ("posx", "posy", "posz")])
        self.assertIn("cancelled", self.call(self.game_map, "getStringProperty", "combatStatus"))
        stored_history = self.call(self.game_map, "getStringProperty", "combatHistory")
        self.assertTrue(stored_history, "The authored encounter must retain its combat history")
        history = json.loads(stored_history)
        self.assertTrue(history[0].startswith("Combat round 1 begins."))
        self.assertIn("cancelled", history[-1])
        self.assertLessEqual(len(history), 64)
        self.assertGreaterEqual(self.call(self.game_map, "getNumericProperty", "combatRound"), 1)
        actions = self.call(self.player, "getEffectiveInteractions")
        attack = next((action for action in actions if self.call(action, "getTypeId") == "Attack"), None)
        self.assertIsNotNone(attack, "The authored Warrior must have its actual Attack ability")
        initial_hp = self.call(enemy, "getNumericProperty", "hp")
        initial_mana = self.call(self.player, "getMana")
        self.assertGreater(initial_hp, 0)
        self.assertEqual(0, self.call(attack, "getNumericProperty", "manaCost"))
        # A guaranteed-hit fixture removes random miss retries; the owned ability,
        # authored enemy, damage rules and real player position remain authoritative.
        base_stats = self.call(self.player, "getObjectProperty", "baseStats")
        self.call(base_stats, "setNumericProperty", "hit", 100)
        self.call(self.player, "useAction", attack, enemy)
        self.pump()
        self.assertLess(self.call(enemy, "getNumericProperty", "hp"), initial_hp)
        self.assertEqual(initial_mana, self.call(self.player, "getMana"))


if __name__ == "__main__":
    unittest.main()
