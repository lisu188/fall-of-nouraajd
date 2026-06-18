#!/usr/bin/env python3
# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import importlib.util
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_crafting_with_fake_game():
    fake_game = types.ModuleType("game")
    fake_game.randint = lambda lower, upper: lower
    fake_game.list_string = lambda game_instance, options: list(options)

    class FakeResourcesProvider:
        @classmethod
        def getInstance(cls):
            return cls()

        def load(self, filename):
            return "{}"

    fake_game.CResourcesProvider = FakeResourcesProvider
    old_game = sys.modules.get("game")
    sys.modules["game"] = fake_game
    try:
        spec = importlib.util.spec_from_file_location(
            "crafting_under_test", REPO_ROOT / "res" / "plugins" / "crafting.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if old_game is None:
            sys.modules.pop("game", None)
        else:
            sys.modules["game"] = old_game


class FakeHandler:
    def __init__(self):
        self.menus = []
        self.messages = []

    def showSelection(self, options):
        self.menus.append(list(options))
        if len(self.menus) == 1:
            return self.menus[-1][0]
        return "Leave"

    def showInfo(self, message, centered=True):
        self.messages.append((message, centered))


class FakeGame:
    def __init__(self, handler):
        self.handler = handler

    def getGuiHandler(self):
        return self.handler


class FakeStation:
    def __init__(self, handler):
        self.game = FakeGame(handler)

    def getStringProperty(self, key):
        return {"craftingStationId": "alchemyTable", "label": "Alchemy Table"}.get(key, "")

    def getTypeId(self):
        return "AlchemyTable"

    def getGame(self):
        return self.game


class FakePlayer:
    def __init__(self):
        self.item_count = 2
        self.gold = 20

    def isPlayer(self):
        return True

    def countItems(self, item_id):
        return self.item_count

    def getNumericProperty(self, key):
        return self.gold if key == "gold" else 0

    def getBoolProperty(self, key):
        return False

    def getMap(self):
        return None


class FakeRuntime:
    def __init__(self):
        self.station_option_calls = 0
        self.recipe = {
            "id": "brew_life_potion",
            "inputs": [{"item_id": "LesserLifePotion", "count": 2}],
            "outputs": [{"item_id": "LifePotion", "count": 1}],
            "gold": 20,
            "success_chance": 100,
        }

    def station_options(self, player, station_id):
        self.station_option_calls += 1
        description = self.describe_recipe_for_player(player, self.recipe)
        return [self.recipe], {description: self.recipe}

    def is_unlocked(self, player, recipe):
        return True

    def describe_recipe(self, recipe):
        return "Life Potion [brew_life_potion]: 2x Lesser Life Potion, 20g -> 1x Life Potion (100% success)"

    def describe_recipe_for_player(self, player, recipe):
        state = "READY" if player.item_count >= 2 and player.gold >= 20 else "MISSING"
        return f"{state} - {self.describe_recipe(recipe)}"

    def execute_recipe(self, game_instance, player, recipe):
        player.item_count = 0
        player.gold = 0
        return {"ok": True, "reason": ""}

    def get_item_label(self, item_id):
        return {"LifePotion": "Life Potion", "LesserLifePotion": "Lesser Life Potion"}.get(item_id, item_id)


class CraftingGuiRefreshTest(unittest.TestCase):
    def test_crafting_station_refreshes_recipe_menu_after_attempt(self):
        crafting = load_crafting_with_fake_game()
        runtime = FakeRuntime()
        crafting.get_runtime = lambda: runtime
        handler = FakeHandler()
        player = FakePlayer()

        crafting.open_crafting_station(FakeStation(handler), player)

        self.assertEqual(2, runtime.station_option_calls)
        self.assertEqual(2, len(handler.menus))
        self.assertIn("READY -", handler.menus[0][0])
        self.assertIn("MISSING -", handler.menus[1][0])
        self.assertEqual(("You crafted Life Potion.", True), handler.messages[-1])


if __name__ == "__main__":
    unittest.main()
