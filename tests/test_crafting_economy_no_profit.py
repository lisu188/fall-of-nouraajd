"""[EPIC_10][STORY_01][SUBSTORY_01] Crafting economy has no positive-margin resale loop.

Closes the repeatable craft-then-buyback gold loop: for every crafting recipe, the vendor
buyback of the output must not exceed the purchase cost of the recipe inputs plus the crafting
fee. Otherwise a player can buy the inputs, craft, and sell the output back at a profit
indefinitely.

Pure source/data check (no built ``_game`` needed) mirroring the live market math in
``src/object/CMarket.cpp``:

- base price of an item = ``2**power * 200``
- player BUY price  = ``getSellCost``  = ``min(base * 100/100, 100000)``            (sell% = 100)
- vendor BUYBACK    = ``getBuyCost``   = ``min(min(base * 80/100, 5000), buyPrice)`` (buy% = 80)

so buyback = ``min(int(base * 0.8), 5000)`` (the buy-price cap never binds because 0.8*base < base).
"""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "res" / "config"
CRAFTING_PATH = CONFIG_DIR / "crafting.json"

# Mirror of src/object/CMarket.cpp constants.
MAX_MARKET_SELL_PRICE = 100000
MAX_MARKET_BUYBACK_PRICE = 5000
MARKET_SELL_PERCENT = 100  # what the player pays to buy
MARKET_BUY_PERCENT = 80  # what the vendor pays back


def _load_item_powers():
    """Map item type id -> power by scanning every res/config/*.json object definition."""
    powers = {}
    for path in sorted(CONFIG_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        for key, value in data.items():
            if isinstance(value, dict):
                props = value.get("properties", {})
                if isinstance(props, dict) and "power" in props:
                    powers[key] = int(props["power"])
    return powers


def _bounded_market_cost(power, percent, max_price):
    base = (2 ** power) * 200
    scaled = base * percent / 100.0
    if scaled >= max_price:
        return max_price
    return int(scaled)


def _buy_price(power):
    # getSellCost: what the player pays to buy the item from a market.
    return _bounded_market_cost(power, MARKET_SELL_PERCENT, MAX_MARKET_SELL_PRICE)


def _vendor_buyback(power):
    # getBuyCost: min(boundedMarketCost(buy%, 5000), getSellCost).
    return min(_bounded_market_cost(power, MARKET_BUY_PERCENT, MAX_MARKET_BUYBACK_PRICE), _buy_price(power))


class CraftingEconomyNoProfitTest(unittest.TestCase):
    def setUp(self):
        self.recipes = json.loads(CRAFTING_PATH.read_text(encoding="utf-8"))
        self.powers = _load_item_powers()

    def _require_power(self, item):
        self.assertIn(item, self.powers, f"no power/config found for crafting item {item!r}")
        return self.powers[item]

    def test_every_recipe_output_buyback_not_above_input_cost_plus_fee(self):
        # Acceptance: for every craftable output, vendor buyback <= (input purchase cost +
        # crafting fee). This removes the positive-margin buy->craft->sell loop.
        offenders = {}
        for name, recipe in self.recipes.items():
            if not isinstance(recipe, dict) or "output" not in recipe:
                continue
            input_cost = sum(_buy_price(self._require_power(inp["item"])) * inp.get("count", 1)
                             for inp in recipe.get("inputs", []))
            fee = int(recipe.get("gold", 0))
            output = recipe["output"]
            buyback = _vendor_buyback(self._require_power(output["item"])) * output.get("count", 1)
            if buyback > input_cost + fee:
                offenders[name] = {
                    "input_cost": input_cost,
                    "fee": fee,
                    "output_buyback": buyback,
                    "margin": buyback - (input_cost + fee),
                }
        self.assertEqual(
            {},
            offenders,
            "Recipes whose output buyback exceeds input cost + fee (repeatable gold exploit): "
            f"{json.dumps(offenders, sort_keys=True)}",
        )

    def test_target_recipes_have_specified_fees_and_inputs(self):
        # The SUBSTORY's three explicit levers must be exactly as specified.
        brew_mana = self.recipes["brew_mana_potion"]
        self.assertEqual(640, brew_mana["gold"], "brew_mana_potion fee must be 640")
        self.assertEqual([{"item": "LesserManaPotion", "count": 2}], brew_mana["inputs"])
        self.assertEqual({"item": "ManaPotion", "count": 1}, brew_mana["output"])

        brew_full_life = self.recipes["brew_full_life_potion"]
        self.assertEqual([{"item": "MaxLifePotion", "count": 2}], brew_full_life["inputs"])
        self.assertEqual({"item": "FullLifePotion", "count": 1}, brew_full_life["output"])

        brew_full_mana = self.recipes["brew_full_mana_potion"]
        self.assertEqual([{"item": "MaxManaPotion", "count": 2}], brew_full_mana["inputs"])
        self.assertEqual({"item": "FullManaPotion", "count": 1}, brew_full_mana["output"])

    def test_potion_powers_unchanged(self):
        # The economy is rebalanced via recipe fees/inputs only -- potion potency (power) must
        # not change. Pin the powers the balance relies on.
        expected = {
            "LesserManaPotion": 1,
            "LesserLifePotion": 1,
            "LifePotion": 2,
            "ManaPotion": 3,
            "GreaterLifePotion": 3,
            "GreaterManaPotion": 3,
            "MaxLifePotion": 4,
            "MaxManaPotion": 4,
            "FullLifePotion": 5,
            "FullManaPotion": 5,
        }
        for item, power in expected.items():
            self.assertEqual(power, self._require_power(item), f"{item} power changed")


if __name__ == "__main__":
    unittest.main()
