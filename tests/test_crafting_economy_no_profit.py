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
"""Economy invariant: no crafting recipe yields a positive vendor-buyback margin.

The town market prices every item from its ``power`` field (``src/object/CMarket.cpp``,
``src/object/CMarket.h``):

* base price   = ``2 ** power * 200``
* a player BUYS at ``sell`` percent (default 100), so an input bought from the market
  costs ``base`` gold;
* a player SELLS back at ``getBuyCost`` = ``min(base * buy% , 5000)`` (default ``buy`` = 80),
  clamped to ``[1, 5000]``.

A crafting recipe is *exploitable* when the buyback value of its output exceeds the total
cost of its inputs (each input's buyback value) plus the recipe's ``gold`` cost: the player
can repeatedly buy inputs, craft, and sell the output for a net gold profit. Because market
price doubles per power level, ``2`` inputs at power ``N`` are worth exactly one item at
power ``N + 1``; any recipe whose output sits two or more power tiers above its inputs (or
whose output buyback otherwise outruns its inputs, e.g. via the 5000 buyback cap) prints
free gold.

This test derives input/output buyback values straight from ``crafting.json`` +
``potions.json`` + ``items.json`` using the documented market formula and asserts the margin
is ``<= 0`` for every craftable recipe. It is a balance contract, not a frozen baseline:
re-introducing a profitable recipe (raising an output power, lowering a recipe gold cost,
or pointing a recipe at cheaper inputs) fails it with a per-recipe margin breakdown. It runs
in the lightweight content-config CI step; no native ``_game`` module is required.
"""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CRAFTING_PATH = REPO_ROOT / "res" / "config" / "crafting.json"
POTIONS_PATH = REPO_ROOT / "res" / "config" / "potions.json"
ITEMS_PATH = REPO_ROOT / "res" / "config" / "items.json"

# Mirror of the market constants/defaults in CMarket.cpp / CMarket.h.
MARKET_BASE_PER_POWER = 200.0
MAX_MARKET_BUYBACK_PRICE = 5000
DEFAULT_MARKET_BUY_PERCENT = 80  # CMarket.h: `int buy = 80;`


def _load_powers():
    """Map every item typeId that declares a ``power`` to its integer power."""
    powers = {}
    for path in (POTIONS_PATH, ITEMS_PATH):
        data = json.loads(path.read_text(encoding="utf-8"))
        for type_id, body in data.items():
            properties = (body or {}).get("properties", {}) or {}
            if "power" in properties:
                powers[type_id] = properties["power"]
    return powers


def market_buyback(power, buy_percent=DEFAULT_MARKET_BUY_PERCENT):
    """Replicate ``CMarket::getBuyCost`` for an item of the given power.

    ``getBuyCost`` = ``min(boundedMarketCost(buy%), getSellCost)``; for the default
    ``buy`` (80) < ``sell`` (100) the buy-side bound always wins, so this is the gold a
    player receives when selling the item back to the market.
    """
    base_price = (2.0 ** power) * MARKET_BASE_PER_POWER
    scaled = base_price * buy_percent / 100.0
    if scaled >= MAX_MARKET_BUYBACK_PRICE:
        return MAX_MARKET_BUYBACK_PRICE
    if scaled < 1.0:
        return 1
    return int(scaled)


def _recipe_margins():
    """Return ``{recipe_name: (input_value, gold, output_buyback, margin)}``.

    ``input_value`` sums each input item's buyback times its count; ``margin`` is
    ``output_buyback - (input_value + gold)``. A positive margin is an exploit.
    """
    powers = _load_powers()
    recipes = json.loads(CRAFTING_PATH.read_text(encoding="utf-8"))
    margins = {}
    for name, recipe in recipes.items():
        input_value = 0
        for entry in recipe.get("inputs", []):
            input_value += market_buyback(powers[entry["item"]]) * entry.get("count", 1)
        gold = recipe.get("gold", 0)
        output = recipe["output"]
        output_buyback = market_buyback(powers[output["item"]]) * output.get("count", 1)
        margin = output_buyback - (input_value + gold)
        margins[name] = (input_value, gold, output_buyback, margin)
    return margins


class CraftingEconomyNoProfitTest(unittest.TestCase):
    def test_no_recipe_yields_positive_buyback_margin(self):
        """Every craftable recipe's output buyback must not exceed its input cost."""
        offenders = {
            name: data
            for name, data in _recipe_margins().items()
            if data[3] > 0
        }
        if offenders:
            lines = [
                f"  {name}: inputs={iv} + gold={g} = {iv + g} -> output_buyback={ob} "
                f"(margin +{m})"
                for name, (iv, g, ob, m) in sorted(offenders.items())
            ]
            self.fail(
                "Profitable crafting recipe(s) detected (output sells back for more than "
                "its inputs cost), enabling a repeatable gold exploit:\n"
                + "\n".join(lines)
                + "\nClose the margin by lowering the output power, raising the recipe "
                "gold cost, or requiring higher-power inputs."
            )

    def test_every_recipe_item_has_a_known_power(self):
        """Every input/output item referenced by a recipe resolves to a power value.

        Guards the invariant itself: if an item loses its ``power`` declaration the margin
        computation would silently ``KeyError`` instead of asserting balance.
        """
        powers = _load_powers()
        recipes = json.loads(CRAFTING_PATH.read_text(encoding="utf-8"))
        missing = set()
        for recipe in recipes.values():
            for entry in recipe.get("inputs", []):
                if entry["item"] not in powers:
                    missing.add(entry["item"])
            if recipe["output"]["item"] not in powers:
                missing.add(recipe["output"]["item"])
        self.assertEqual(
            set(),
            missing,
            f"Recipe items lack a power declaration in potions.json/items.json: {sorted(missing)}",
        )

    def test_a_profitable_recipe_would_be_detected(self):
        """Sanity check: an output two power tiers above its inputs is flagged.

        Mirrors the original exploit shape (2x power-1 inputs -> power-3 output) to prove
        the margin computation actually catches a positive margin.
        """
        two_power_one_inputs = 2 * market_buyback(1)
        power_three_output = market_buyback(3)
        margin = power_three_output - (two_power_one_inputs + 20)
        self.assertGreater(
            margin,
            0,
            "The buyback formula must score a 2x(power-1) -> power-3 recipe as profitable.",
        )


if __name__ == "__main__":
    unittest.main()
