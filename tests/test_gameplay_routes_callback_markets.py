# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure guards for actual callback-market identity, lifetime, funds and finite stock."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from tests.gameplay_routes_callback_markets import purchaseCallbackItem


class GameplayCallbackMarketRoutesTest(unittest.TestCase):
    def driver(self, *, corrupt=None, gold=100, loot=True):
        handles = {
            key: {"__handle__": key}
            for key in (
                "game",
                "map",
                "player",
                "handler",
                "market",
                "mana",
                "life",
                "loot",
                "starter",
                "quest",
                "equipped",
                "reagent",
            )
        }
        stock = [handles["mana"], handles["life"]]
        owned = [handles[key] for key in ("starter", "quest", "equipped", "reagent")]
        if loot:
            owned.append(handles["loot"])
        state = {"gold": gold, "stock": stock, "owned": owned, "sales": [], "reads": 0, "purchases": []}
        types = {"mana": "ManaPotion", "life": "LifePotion", "reagent": "Scroll"}
        request = {"market": {"typeId": "victorMarket", "name": "market"}, "map": "nouraajd"}

        def call(handle, method, *args):
            key = handle["__handle__"]
            if method == "getTurn":
                return 9
            if method == "getGuiHandler":
                return handles["handler"]
            if method == "getRequestedTradeMarket":
                state["reads"] += 1
                return None if corrupt == "expired" and state["reads"] > 1 else handles["market"]
            if method == "getTypeId":
                return "victorMarket" if key == "market" else types.get(key, "Sword")
            if method == "getName":
                return key
            if method == "getEquipped":
                return {"weapon": handles["equipped"]}
            if method == "getItems":
                return list(state["owned"] if key == "player" else state["stock"])
            if method == "getSellCost":
                return 1600
            if method == "getBuyCost":
                return 1500
            if method == "hasTag":
                return key == "quest"
            if method == "buyItem":
                item = args[1]
                state["owned"].remove(item)
                state["stock"].append(item)
                state["gold"] += 1500
                state["sales"].append(item["__handle__"])
                return None
            if method == "sellItem":
                item = args[1]
                if item not in state["stock"] or state["gold"] < 1600:
                    return False
                state["gold"] -= 1599 if corrupt == "wrongPayment" else 1600
                if corrupt != "retainedStock":
                    state["stock"].remove(item)
                state["owned"].append(handles["life"] if corrupt == "wrongIdentity" else item)
                state["purchases"].append(item["__handle__"])
                return True
            self.fail((handle, method, args))

        d = SimpleNamespace(
            test=self,
            game=handles["game"],
            game_map=handles["map"],
            player=handles["player"],
            map_name="nouraajd",
            coords=lambda: (10, 20, 0),
            call=call,
            gold=lambda: state["gold"],
            tradeRequests=lambda: [request],
            record=Mock(),
        )
        return d, state, handles

    def testOriginalCallbackMarketFundsAndTransfersExactlyOneFiniteIdentity(self):
        d, state, handles = self.driver()
        item = purchaseCallbackItem(
            d, "victorMarket", "ManaPotion", {"loot", "quest", "equipped", "reagent"}, protected_types={"Scroll"}
        )
        self.assertEqual(handles["mana"], item)
        self.assertEqual(["loot"], state["sales"])
        self.assertEqual(["mana"], state["purchases"])
        self.assertEqual(0, state["gold"])
        self.assertNotIn(item, state["stock"])
        self.assertIn(item, state["owned"])
        self.assertGreaterEqual(state["reads"], 4)
        d.record.assert_called_once()

    def testMissingEarnedFundsNeverSellsStarterQuestEquippedOrRecipeItems(self):
        d, state, _ = self.driver(loot=False)
        with self.assertRaisesRegex(AssertionError, "cannot afford"):
            purchaseCallbackItem(
                d, "victorMarket", "ManaPotion", {"quest", "equipped", "reagent"}, protected_types={"Scroll"}
            )
        self.assertEqual([], state["sales"])
        self.assertEqual([], state["purchases"])

    def testExpiredRequestFailsBeforeAStaleHandleCanTrade(self):
        d, state, _ = self.driver(corrupt="expired")
        with self.assertRaises(AssertionError):
            purchaseCallbackItem(d, "victorMarket", "ManaPotion", {"loot"})
        self.assertEqual([], state["sales"])
        self.assertEqual([], state["purchases"])

    def testChangedPaymentStockOrTransferredIdentityCannotEarnEvidence(self):
        for corruption in ("wrongPayment", "retainedStock", "wrongIdentity"):
            with self.subTest(corruption=corruption):
                d, _, _ = self.driver(corrupt=corruption, gold=1600)
                with self.assertRaises(AssertionError):
                    purchaseCallbackItem(d, "victorMarket", "ManaPotion", set())
                d.record.assert_not_called()

    def testMismatchedNativeCallbackNameOrMapCannotSupplyTheMarket(self):
        for key, value in (("name", "replacement"), ("map", "different")):
            d, state, _ = self.driver(gold=1600)
            request = d.tradeRequests()[0]
            if key == "map":
                request[key] = value
            else:
                request["market"][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                purchaseCallbackItem(d, "victorMarket", "ManaPotion", set())
            self.assertEqual([], state["purchases"])


if __name__ == "__main__":
    unittest.main()
