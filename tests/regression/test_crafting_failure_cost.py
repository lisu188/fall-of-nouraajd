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
"""Regression: a failed craft must still consume its reagents and gold.

The success-chance roll used to ``return`` on failure before any cost was
paid, which turned ``successChance`` into a free retry (no reagents lost).
These tests pin the contract that the cost is paid on BOTH the success and
failure paths, while outputs are granted only on success.
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_crafting_with_fake_game(randint_fn):
    fake_game = types.ModuleType("game")
    fake_game.randint = randint_fn
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
            "crafting_under_test_failure_cost", REPO_ROOT / "res" / "plugins" / "crafting.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if old_game is None:
            sys.modules.pop("game", None)
        else:
            sys.modules["game"] = old_game


class FakeObjectHandler:
    def __init__(self):
        self.created = []

    def createObject(self, game_instance, item_id):
        self.created.append(item_id)
        return {"item_id": item_id}


class FakeGame:
    def __init__(self):
        self.object_handler = FakeObjectHandler()

    def getObjectHandler(self):
        return self.object_handler


class FakePlayer:
    """Tracks inventory counts and gold so we can assert what was consumed."""

    def __init__(self, item_counts, gold):
        self.item_counts = dict(item_counts)
        self.gold = gold
        self.added_items = []

    def countItems(self, item_id):
        return self.item_counts.get(item_id, 0)

    def removeItem(self, predicate, *_args):
        # The plugin closes over the required item id via a default argument,
        # so probe each held item id to discover which one matches.
        for item_id, count in self.item_counts.items():
            if count <= 0:
                continue
            if predicate(_FakeItem(item_id)):
                self.item_counts[item_id] = count - 1
                return True
        return False

    def getNumericProperty(self, key):
        return self.gold if key == "gold" else 0

    def setNumericProperty(self, key, value):
        if key == "gold":
            self.gold = value

    def addItem(self, item):
        self.added_items.append(item)


class _FakeItem:
    def __init__(self, item_id):
        self._id = item_id

    def getTypeId(self):
        return self._id


def make_recipe(success_chance):
    return {
        "id": "brew_life_potion",
        "inputs": [{"item_id": "LesserLifePotion", "count": 2}],
        "outputs": [{"item_id": "LifePotion", "count": 1}],
        "gold": 20,
        "success_chance": success_chance,
    }


class CraftingFailureCostTest(unittest.TestCase):
    def test_failed_craft_consumes_inputs_and_gold_without_outputs(self):
        # randint always returns the max so any success_chance < 100 fails.
        crafting = load_crafting_with_fake_game(lambda lower, upper: upper)
        game_instance = FakeGame()
        player = FakePlayer({"LesserLifePotion": 5}, gold=50)

        result = crafting.apply_recipe(game_instance, player, make_recipe(0))

        self.assertFalse(result["ok"])
        self.assertEqual("failed", result["reason"])
        # Reagents consumed even on failure (5 - 2 = 3 remaining).
        self.assertEqual(3, player.item_counts["LesserLifePotion"])
        # Gold deducted even on failure (50 - 20 = 30).
        self.assertEqual(30, player.gold)
        # No outputs granted on failure.
        self.assertEqual([], player.added_items)
        self.assertEqual([], game_instance.object_handler.created)

    def test_successful_craft_consumes_cost_and_grants_outputs(self):
        # randint returns the min so a 1% chance still succeeds; 100% never rolls.
        crafting = load_crafting_with_fake_game(lambda lower, upper: lower)
        game_instance = FakeGame()
        player = FakePlayer({"LesserLifePotion": 5}, gold=50)

        result = crafting.apply_recipe(game_instance, player, make_recipe(100))

        self.assertTrue(result["ok"])
        self.assertEqual(3, player.item_counts["LesserLifePotion"])
        self.assertEqual(30, player.gold)
        self.assertEqual(["LifePotion"], game_instance.object_handler.created)
        self.assertEqual(1, len(player.added_items))

    def test_insufficient_reagents_pays_nothing(self):
        crafting = load_crafting_with_fake_game(lambda lower, upper: upper)
        game_instance = FakeGame()
        player = FakePlayer({"LesserLifePotion": 1}, gold=50)

        result = crafting.apply_recipe(game_instance, player, make_recipe(0))

        self.assertFalse(result["ok"])
        self.assertTrue(result["reason"].startswith("missing:"))
        # Precondition gate fires before any cost is paid.
        self.assertEqual(1, player.item_counts["LesserLifePotion"])
        self.assertEqual(50, player.gold)
        self.assertEqual([], game_instance.object_handler.created)

    def test_insufficient_gold_pays_nothing(self):
        crafting = load_crafting_with_fake_game(lambda lower, upper: upper)
        game_instance = FakeGame()
        player = FakePlayer({"LesserLifePotion": 5}, gold=5)

        result = crafting.apply_recipe(game_instance, player, make_recipe(0))

        self.assertFalse(result["ok"])
        self.assertEqual("missing:gold", result["reason"])
        # Gold gate fires before reagents are removed or gold deducted.
        self.assertEqual(5, player.item_counts["LesserLifePotion"])
        self.assertEqual(5, player.gold)


if __name__ == "__main__":
    unittest.main()
