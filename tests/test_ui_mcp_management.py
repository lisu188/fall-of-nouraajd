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
