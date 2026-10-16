# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Contract regressions for service evidence, identity, finite stock and real re-entry."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.gameplay_branch_driver import readNewNativeTrace
from tests.gameplay_routes_services import marketAttempt, readSignpost, useOwnedScroll, visitService


class GameplayRouteServicesTest(unittest.TestCase):
    def marketDriver(self, *, gold=0, owned=(), corrupt=None):
        player, market, shop, item, loot = (
            {"__handle__": name} for name in ("player", "market", "shop", "item", "loot")
        )
        state = {"gold": gold, "stock": [item], "owned": list(owned), "sales": []}
        checks = []

        def call(handle, method, *args):
            if method == "getObjectProperty":
                return market
            if method == "getName":
                return handle["__handle__"]
            if method == "getTypeId":
                return "LifePotion"
            if method == "getItems":
                return list(state["owned"] if handle == player else state["stock"])
            if method == "getSellCost":
                return 10
            if method == "getBuyCost":
                return 25
            if method == "hasTag":
                return False
            if method == "sellItem":
                actual_item = args[1]
                if actual_item not in state["stock"] or state["gold"] < 10:
                    if corrupt == "refusalCharges":
                        state["gold"] -= 1
                    return False
                state["gold"] -= 9 if corrupt == "wrongPayment" else 10
                if corrupt != "stockRetained":
                    state["stock"].remove(actual_item)
                state["owned"].append({"__handle__": "replacement"} if corrupt == "differentIdentity" else actual_item)
                return True
            self.fail((handle, method, args))

        def sell(name, actual_item):
            self.assertEqual("shop", name)
            self.assertIn(actual_item, state["owned"])
            state["owned"].remove(actual_item)
            state["stock"].append(actual_item)
            state["gold"] += 25
            state["sales"].append(actual_item)

        def check(branch, condition, **evidence):
            self.assertTrue(condition, (branch, evidence))
            checks.append((branch, evidence))

        d = SimpleNamespace(
            test=self,
            player=player,
            object=lambda name: shop,
            call=call,
            gold=lambda: state["gold"],
            sellAt=sell,
            check=check,
        )
        return d, state, checks, loot

    def testRefusalAndPurchaseHaveSeparatePrerequisitesAndExactTransfers(self):
        with patch(
            "tests.gameplay_routes_services.visitService", return_value=({"market": {"name": "market"}, "seq": 9},)
        ):
            d, state, checks, loot = self.marketDriver()
            marketAttempt(d, "shop", "map.market.insufficientGold", purchased=False)
            self.assertEqual({"gold": 0, "stock": [{"__handle__": "item"}], "owned": [], "sales": []}, state)
            state["owned"].append(loot)
            item = marketAttempt(d, "shop", "map.market.purchased", purchased=True, earned_items={"loot"})
            self.assertEqual({"__handle__": "item"}, item)
            self.assertEqual(15, state["gold"])
            self.assertEqual([loot], state["stock"])
            self.assertEqual([item], state["owned"])
            self.assertEqual([loot], state["sales"])
            self.assertEqual(["map.market.insufficientGold", "map.market.purchased"], [entry[0] for entry in checks])
            self.assertEqual(["loot"], checks[1][1]["soldEarnedItems"])

    def testPurchaseNeverSellsUnapprovedStartingInventory(self):
        with patch(
            "tests.gameplay_routes_services.visitService", return_value=({"market": {"name": "market"}, "seq": 9},)
        ):
            d, state, checks, loot = self.marketDriver(owned=({"__handle__": "loot"},))
            with self.assertRaisesRegex(AssertionError, "Real earned funds"):
                marketAttempt(d, "shop", "map.market.purchased", purchased=True)
            self.assertEqual([loot], state["owned"])
            self.assertEqual([], state["sales"])
            self.assertEqual([], checks)

    def testDeclaredOutcomeCannotBeConditionalOnWhateverTheMarketDid(self):
        with patch(
            "tests.gameplay_routes_services.visitService", return_value=({"market": {"name": "market"}, "seq": 9},)
        ):
            d, _, checks, _ = self.marketDriver(gold=10)
            with self.assertRaisesRegex(AssertionError, "actually insufficient gold"):
                marketAttempt(d, "shop", "map.market.insufficientGold", purchased=False)
            self.assertEqual([], checks)

    def testIdentityPaymentAndStockCorruptionNeverReceiveCredit(self):
        with patch(
            "tests.gameplay_routes_services.visitService", return_value=({"market": {"name": "market"}, "seq": 9},)
        ):
            for corrupt in ("refusalCharges", "wrongPayment", "stockRetained", "differentIdentity"):
                with self.subTest(corrupt=corrupt):
                    purchased = corrupt != "refusalCharges"
                    d, _, checks, _ = self.marketDriver(gold=10 if purchased else 0, corrupt=corrupt)
                    with self.assertRaises(AssertionError):
                        marketAttempt(d, "shop", "map.market", purchased=purchased)
                    self.assertEqual([], checks)

    def testServiceReentersAnOccupiedTargetAndUsesFreshCallbackEvidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.jsonl"
            path.write_text(json.dumps({"seq": 1, "event": "map_started", "map": "test"}) + "\n", encoding="utf-8")
            target = {"__handle__": "sign"}
            coords, positions = [(2, 3, 0)], {}
            d = SimpleNamespace(
                test=self,
                trace_path=path,
                map_name="test",
                _combat_trace_seq=0,
                _combat_trace_positions=positions,
                object=lambda name: target,
                coords=lambda handle=None: (2, 3, 0) if handle else coords[0],
            )

            def read():
                records = readNewNativeTrace(path, positions, d._combat_trace_seq)
                if records:
                    d._combat_trace_seq = records[-1]["seq"]

            def revisit(name):
                self.assertEqual("sign", name)
                coords[0] = (3, 3, 0)
                coords[0] = (2, 3, 0)
                with path.open("a", encoding="utf-8") as output:
                    output.write(json.dumps({"seq": 2, "event": "reader_requested", "map": "test"}) + "\n")
                read()

            d.assertNativeCombatOutcomes = read
            d.navigateTo = Mock()
            d.revisit = Mock(side_effect=revisit)
            events = visitService(d, "sign", "reader_requested")
            self.assertEqual((2,), tuple(event["seq"] for event in events))
            d.revisit.assert_called_once_with("sign")

    def scrollDriver(self, corrupt=None):
        player, world, item = ({"__handle__": name} for name in ("player", "map", "scroll"))
        state = {"coords": (2, 3, 0), "owned": [item], "checks": []}

        def call(handle, method, *args):
            if method == "getTypeId":
                return "TownPortalScroll"
            if method == "getItems":
                return state["owned"][:]
            if method.startswith("getEntry"):
                return {"getEntryX": 1, "getEntryY": 1, "getEntryZ": 0}[method]
            if method == "useItem":
                self.assertIn(args[0], state["owned"])
                if corrupt != "notConsumed":
                    state["owned"].remove(args[0])
                if corrupt != "noMovement":
                    state["coords"] = (1, 1, 0)
                return None
            self.fail(method)

        def check(branch, condition, **evidence):
            self.assertTrue(condition)
            state["checks"].append(branch)

        return (
            SimpleNamespace(
                test=self,
                player=player,
                game_map=world,
                call=call,
                coords=lambda: state["coords"],
                pump=Mock(),
                assertSurvival=Mock(),
                check=check,
            ),
            item,
            state,
        )

    def testScrollMustBeOwnedConsumedAndReachItsActualEntry(self):
        d, item, state = self.scrollDriver()
        useOwnedScroll(d, item, "map.scroll.retreat")
        self.assertEqual(["map.scroll.retreat"], state["checks"])
        for corrupt in ("notConsumed", "noMovement"):
            with self.subTest(corrupt=corrupt):
                d, item, state = self.scrollDriver(corrupt)
                with self.assertRaises(AssertionError):
                    useOwnedScroll(d, item, "map.scroll.retreat")
                self.assertEqual([], state["checks"])

    def testScrollCannotReceiveCreditAtItsDestinationOrWithoutOwnership(self):
        for setup in ("atEntry", "unowned"):
            with self.subTest(setup=setup):
                d, item, state = self.scrollDriver()
                state["coords"] = (1, 1, 0) if setup == "atEntry" else state["coords"]
                state["owned"] = [] if setup == "unowned" else state["owned"]
                with self.assertRaises(AssertionError):
                    useOwnedScroll(d, item, "map.scroll.retreat")
                self.assertEqual([], state["checks"])

    def testSignRequiresExactUtf8BodyAndAnInertRepeat(self):
        player, sign = ({"__handle__": name} for name in ("player", "sign"))
        checks = []
        body = "The warden's road — open."

        def call(handle, method, *args):
            if method == "getStringProperty":
                return body
            if method == "getItems":
                return []
            if method == "getNumericProperty":
                return 0
            self.fail(method)

        def check(branch, condition, **evidence):
            self.assertTrue(condition)
            checks.append(branch)

        d = SimpleNamespace(
            test=self,
            player=player,
            map_name="map",
            navigateTo=Mock(),
            object=lambda name: sign,
            call=call,
            gold=lambda: 50,
            questNames=lambda completed=False: [],
            check=check,
        )
        event = {"seq": 8, "title": "Signpost", "body": body, "bodyLength": len(body.encode()), "headless": True}
        with patch("tests.gameplay_routes_services.visitService", return_value=(event,)) as visit:
            readSignpost(d, "sign")
            self.assertEqual(2, visit.call_count)
        self.assertEqual(["map.signpost.read", "map.signpost.repeat"], checks)
        checks.clear()
        with patch("tests.gameplay_routes_services.visitService", return_value=({**event, "body": "Wrong sign"},)):
            with self.assertRaises(AssertionError):
                readSignpost(d, "sign")
        self.assertEqual([], checks)
