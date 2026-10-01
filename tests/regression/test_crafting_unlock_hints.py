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
"""Regression: crafting unlock hints come from content, and duplicate recipe
inputs are merged into one requirement.

Hints used to live in a hardcoded UNLOCK_HINTS dict inside the plugin (with the
raw flag name leaking into the fallback text), so a station on any map other
than nouraajd showed guidance about NPCs that do not exist there. They now
resolve station override -> recipe unlockHint -> generic text.

Duplicate input entries used to be verified independently, so a recipe listing
the same item twice would pass the inventory check with fewer items than it
actually costs (removal silently no-ops when nothing matches).
"""

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

RECIPES = {
    "craft_scroll": {
        "station": "scribeDesk",
        "inputs": [{"item": "Scroll", "count": 1}],
        "output": {"item": "TownPortalScroll", "count": 1},
        "gold": 10,
        "unlockFlag": "CAN_CRAFT_SCROLLS",
        "unlockHint": "Someone lettered must first grant you the scribe's craft.",
    },
    "craft_scroll_no_hint": {
        "station": "scribeDesk",
        "inputs": [{"item": "Scroll", "count": 1}],
        "output": {"item": "TownPortalScroll", "count": 1},
        "unlockFlag": "CAN_CRAFT_SCROLLS",
    },
    "craft_duplicated_inputs": {
        "station": "scribeDesk",
        "inputs": [
            {"item": "Scroll", "count": 1},
            {"item": "Scroll", "count": 1},
        ],
        "output": {"item": "TownPortalScroll", "count": 1},
    },
}


def load_crafting_with_fake_game():
    fake_game = types.ModuleType("game")
    fake_game.randint = lambda lower, upper: lower
    fake_game.list_string = lambda game_instance, options: list(options)

    class FakeResourcesProvider:
        @classmethod
        def getInstance(cls):
            return cls()

        def load(self, filename):
            if filename == "config/crafting.json":
                return json.dumps(RECIPES)
            return "{}"

    fake_game.CResourcesProvider = FakeResourcesProvider
    old_game = sys.modules.get("game")
    sys.modules["game"] = fake_game
    try:
        spec = importlib.util.spec_from_file_location(
            "crafting_under_test_unlock_hints", REPO_ROOT / "res" / "plugins" / "crafting.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if old_game is None:
            sys.modules.pop("game", None)
        else:
            sys.modules["game"] = old_game


class FakeStation:
    def __init__(self, hints=None):
        self.hints = hints or {}

    def getStringProperty(self, key):
        return self.hints.get(key, "")


class FakePlayer:
    def __init__(self, item_counts=None, gold=0):
        self.item_counts = dict(item_counts or {})
        self.gold = gold

    def countItems(self, item_id):
        return self.item_counts.get(item_id, 0)

    def getNumericProperty(self, key):
        return self.gold if key == "gold" else 0

    def getBoolProperty(self, key):
        return False

    def getMap(self):
        return None


class CraftingUnlockHintTest(unittest.TestCase):
    def setUp(self):
        self.crafting = load_crafting_with_fake_game()
        self.runtime = self.crafting.CraftingRuntime()

    def test_recipe_unlock_hint_defaults_to_content_hint(self):
        recipe = self.runtime.get_recipe("craft_scroll")
        self.assertEqual(
            "Someone lettered must first grant you the scribe's craft.",
            self.runtime.recipe_unlock_hint(recipe),
        )

    def test_station_override_wins_over_recipe_hint(self):
        recipe = self.runtime.get_recipe("craft_scroll")
        station = FakeStation({"unlockHint_CAN_CRAFT_SCROLLS": "Study Gravewatch's learning stone."})
        self.assertEqual(
            "Study Gravewatch's learning stone.",
            self.runtime.recipe_unlock_hint(recipe, station),
        )

    def test_missing_hint_falls_back_without_leaking_flag_name(self):
        recipe = self.runtime.get_recipe("craft_scroll_no_hint")
        hint = self.runtime.recipe_unlock_hint(recipe, FakeStation())
        self.assertEqual(self.crafting.DEFAULT_LOCKED_HINT, hint)
        self.assertNotIn("CAN_CRAFT_SCROLLS", hint)

    def test_locked_description_uses_station_override(self):
        recipe = self.runtime.get_recipe("craft_scroll")
        station = FakeStation({"unlockHint_CAN_CRAFT_SCROLLS": "Study Gravewatch's learning stone."})
        description = self.runtime.describe_recipe_for_player(FakePlayer(), recipe, station)
        self.assertIn("LOCKED", description)
        self.assertIn("Study Gravewatch's learning stone.", description)


class CraftingDuplicateInputTest(unittest.TestCase):
    def setUp(self):
        self.crafting = load_crafting_with_fake_game()
        self.runtime = self.crafting.CraftingRuntime()

    def test_duplicate_entries_merge_into_combined_count(self):
        recipe = self.runtime.get_recipe("craft_duplicated_inputs")
        self.assertEqual([{"item_id": "Scroll", "count": 2}], recipe["inputs"])

    def test_single_item_no_longer_satisfies_duplicated_requirement(self):
        recipe = self.runtime.get_recipe("craft_duplicated_inputs")
        player = FakePlayer({"Scroll": 1})
        status = self.crafting.verify_inventory_requirements(player, recipe["inputs"])
        self.assertFalse(status["ok"])
        self.assertEqual("missing:Scroll", status["reason"])


if __name__ == "__main__":
    unittest.main()
