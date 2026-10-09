# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Potion witnesses reject resource, ownership and native identity mismatches."""

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.gameplay_routes_potions import (
    consumePotionsAtDeficits,
    observePotionConsumptions,
    potionUseWitness,
    preparePotionStock,
    requirePotionConsumptions,
    useOwnedPotion,
)


def potionCallback(class_id):
    path = Path(__file__).resolve().parents[1] / "res/plugins/potion.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    loader = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load")
    node = next(node for node in loader.body if isinstance(node, ast.ClassDef) and node.name == class_id)
    node.decorator_list = []
    namespace = {"CPotion": object}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[class_id]


def nativePotionRecord(*, category="life", before=25, maximum=100, capped=False):
    type_id, power = ("LifePotion", 2) if category == "life" else ("ManaPotion", 3)
    record = {
        "event": "item_used",
        "seq": 7,
        "map": "nouraajd",
        "actor": {"name": "actual-player", "isPlayer": True},
        "item": {"name": "potion-identity-1", "type": type_id, "typeId": type_id},
        "itemNameLength": len("potion-identity-1"),
        "power": power,
        "disposable": True,
        "restoresHp": category == "life",
        "restoresMana": category == "mana",
        "hpBefore": 100,
        "hpAfter": 100,
        "hpMaxBefore": 100,
        "hpMaxAfter": 100,
        "manaBefore": 100,
        "manaAfter": 100,
        "manaMaxBefore": 100,
        "manaMaxAfter": 100,
        "ownedBefore": True,
        "ownedAfter": False,
        "inventoryBeforeCount": 3,
        "inventoryAfterCount": 2,
        "removedCount": 1,
        "addedCount": 0,
        "onlyUsedItemRemoved": True,
        "equipmentUnchanged": True,
    }
    key = "hp" if category == "life" else "mana"
    record[key + "Before"] = before
    record[key + "MaxBefore"] = record[key + "MaxAfter"] = maximum
    record[key + "After"] = maximum if capped else before + (40 if category == "life" else 60)
    return record


class GameplayPotionConsumptionTest(unittest.TestCase):
    def witness(self, record):
        return potionUseWitness(record, player_name="actual-player", map_name="nouraajd")

    def testBothActualCallbacksRestoreExactConfiguredPercentWithCaps(self):
        for category, expected in (("life", 65), ("mana", 85)):
            with self.subTest(category=category):
                record = nativePotionRecord(category=category)
                key = "hp" if category == "life" else "mana"
                values = {"resource": record[key + "Before"]}

                def restore(percent):
                    self.assertEqual(40 if category == "life" else 60, percent)
                    values["resource"] = min(100, values["resource"] + int(percent))

                creature = SimpleNamespace(healProc=restore, addManaProc=restore)
                potion = potionCallback(record["item"]["type"])()
                potion.getNumericProperty = lambda key: record["power"]
                potion.onUse(SimpleNamespace(getCause=lambda: creature))
                self.assertEqual(expected, values["resource"])
                actual_category, evidence = self.witness(record)
                self.assertEqual(category, actual_category)
                self.assertEqual(expected, evidence["resourceAfter"])
                capped = nativePotionRecord(category=category, before=99, capped=True)
                self.assertEqual(100, self.witness(capped)[1]["resourceAfter"])

    def testPositivePercentageUsesNativeMinimumOneRatherThanFullRestore(self):
        record = nativePotionRecord(category="mana", before=0, maximum=3)
        record["item"]["typeId"] = "LesserManaPotion"
        record["power"] = 1
        record["manaAfter"] = 1
        self.assertEqual(1, self.witness(record)[1]["resourceAfter"])
        record["manaAfter"] = 3
        with self.assertRaisesRegex(AssertionError, "exact capped percentage"):
            self.witness(record)

    def testOrdinaryCallbacksPreserveUntouchedResourcesAboveTheirReducedMaximum(self):
        cases = (
            ("DarkBeer", "life", 1, 10, 63, 126, 112, 22),
            ("LifePotion", "life", 2, 45, 77, 156, 154, 75),
            ("ManaPotion", "mana", 3, 10, 63, 126, 112, 47),
        )
        for type_id, category, power, before, maximum, other_value, other_maximum, expected in cases:
            with self.subTest(type_id=type_id):
                key, other = ("hp", "mana") if category == "life" else ("mana", "hp")
                record = nativePotionRecord(category=category, before=before, maximum=maximum)
                record["item"]["typeId"], record["power"] = type_id, power
                record[other + "Before"] = record[other + "After"] = other_value
                record[other + "MaxBefore"] = record[other + "MaxAfter"] = other_maximum
                values = {key: before, other: other_value}

                def restore(percent):
                    values[key] = min(maximum, values[key] + max(1, int(percent / 100.0 * maximum)))

                unused = Mock(side_effect=AssertionError("An ordinary potion touched the other resource"))
                creature = SimpleNamespace(
                    healProc=restore if category == "life" else unused,
                    addManaProc=restore if category == "mana" else unused,
                )
                potion = potionCallback(record["item"]["type"])()
                potion.getNumericProperty = lambda name: power
                potion.onUse(SimpleNamespace(getCause=lambda: creature))
                self.assertEqual({key: expected, other: other_value}, values)
                unused.assert_not_called()
                record[key + "After"] = values[key]
                self.assertEqual(expected, self.witness(record)[1]["resourceAfter"])

    def testUntouchedOverflowCannotHideInvalidRestorationOwnershipOrResourceChanges(self):
        for category in ("life", "mana"):
            key, other = ("hp", "mana") if category == "life" else ("mana", "hp")
            original = nativePotionRecord(category=category)
            original[other + "Before"] = original[other + "After"] = 126
            original[other + "MaxBefore"] = original[other + "MaxAfter"] = 112
            mutations = (
                {other + "After": 125},
                {other + "After": 112},
                {key + "Before": 100, key + "After": 100},
                {key + "Before": 101, key + "After": 100},
                {key + "After": original[key + "After"] + 1},
                {"hpBefore": 0},
                {"manaBefore": -1},
                {"hpBefore": True},
                {"manaMaxAfter": 0},
                {"ownedBefore": False},
                {"onlyUsedItemRemoved": False},
                {"equipmentUnchanged": False},
            )
            for mutation in mutations:
                with self.subTest(category=category, mutation=mutation):
                    record = deepcopy(original)
                    record.update(mutation)
                    with self.assertRaises(AssertionError):
                        self.witness(record)

    def testUnrelatedNpcOtherPlayerMapAndRejuvenationGiveNoOrdinaryPotionCredit(self):
        for defect in ("npc", "other-player", "other-map", "other-event", "rejuvenation", "unknown-library-item"):
            with self.subTest(defect=defect):
                record = nativePotionRecord()
                if defect == "npc":
                    record["actor"]["isPlayer"] = False
                elif defect == "other-player":
                    record["actor"]["name"] = "different-player"
                elif defect == "other-map":
                    record["map"] = "ritual"
                elif defect == "other-event":
                    record["event"] = "inventory_removed"
                else:
                    record["item"]["typeId"] = (
                        "RejuvenationPotion" if defect == "rejuvenation" else "uninstantiatedLibraryPotion"
                    )
                self.assertIsNone(self.witness(record))

    def testTruncatedAndMissingNativeFieldsCannotProveConsumption(self):
        original = nativePotionRecord()
        original["item"]["name"] = "draught-ą"
        original["itemNameLength"] = len(original["item"]["name"].encode("utf-8"))
        self.assertIsNotNone(self.witness(original))
        for key in ("hpBefore", "manaMaxAfter", "inventoryBeforeCount", "equipmentUnchanged", "itemNameLength", "seq"):
            with self.subTest(key=key):
                record = deepcopy(original)
                record.pop(key)
                with self.assertRaises(AssertionError):
                    self.witness(record)
        original["itemNameLength"] += 1
        with self.assertRaisesRegex(AssertionError, "truncated"):
            self.witness(original)

    def testNoDeficitWrongRestoreChangedMaxOrOtherResourceCannotPass(self):
        mutations = (
            {"hpBefore": 100, "hpAfter": 100},
            {"hpAfter": 66},
            {"hpMaxAfter": 101},
            {"manaAfter": 99},
            {"hpBefore": 0},
            {"power": 3},
            {"restoresMana": True},
            {"disposable": False},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                record = nativePotionRecord()
                record.update(mutation)
                with self.assertRaises(AssertionError):
                    self.witness(record)

    def testExactNativeOwnershipRemovalAndEquipmentAreMandatory(self):
        mutations = (
            {"ownedBefore": False},
            {"ownedAfter": True},
            {"inventoryAfterCount": 3},
            {"removedCount": 2},
            {"addedCount": 1},
            {"onlyUsedItemRemoved": False},
            {"equipmentUnchanged": False},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                record = nativePotionRecord()
                record.update(mutation)
                with self.assertRaises(AssertionError):
                    self.witness(record)

    def testObserverCreditsOnlyDeclaredActualReceiptsOnce(self):
        receipts = {}

        def check(branch, condition, **evidence):
            self.assertTrue(condition)
            receipts[branch] = evidence

        driver = SimpleNamespace(
            map_name="nouraajd",
            case=SimpleNamespace(branches=("nouraajd.potion.life.used",)),
            branches=receipts,
            check=check,
        )
        observePotionConsumptions(driver, [], player_name="actual-player")
        self.assertEqual({}, receipts)
        observePotionConsumptions(
            driver, [nativePotionRecord(), nativePotionRecord(category="mana")], player_name="actual-player"
        )
        self.assertEqual({"nouraajd.potion.life.used"}, set(receipts))
        driver.check = Mock(side_effect=AssertionError("A duplicate native record cannot create another receipt"))
        observePotionConsumptions(driver, [nativePotionRecord()], player_name="actual-player")
        driver.check.assert_not_called()

    def manualDriver(self):
        record = nativePotionRecord()
        record["inventoryBeforeCount"], record["inventoryAfterCount"] = 2, 1
        item, player, world = ({"__handle__": name} for name in ("potion", "player", "map"))
        state = {"hp": 25, "mana": 100, "owned": [item, {"__handle__": "retained-item"}], "events": []}
        creature = SimpleNamespace(
            healProc=lambda percent: state.__setitem__("hp", min(100, state["hp"] + int(percent))),
            addManaProc=Mock(side_effect=AssertionError("Life potion must not restore mana")),
        )
        actual_potion = potionCallback("LifePotion")()
        actual_potion.getNumericProperty = lambda key: 2

        def call(handle, method, *args):
            if handle == world:
                self.assertEqual("getTurn", method)
                return 5
            if handle == item:
                return {
                    "getTypeId": "LifePotion",
                    "getType": "LifePotion",
                    "getNumericProperty": 2,
                    "getName": record["item"]["name"],
                }[method]
            if handle == {"__handle__": "retained-item"}:
                self.assertEqual("getTypeId", method)
                return "retainedSword"
            self.assertEqual(player, handle)
            if method == "useItem":
                self.assertEqual(item, args[0])
                actual_potion.onUse(SimpleNamespace(getCause=lambda: creature))
                state["owned"].remove(item)
                state["events"].append(record)
                return
            return {
                "getItems": state["owned"],
                "getHp": state["hp"],
                "getMana": state["mana"],
                "getHpMax": 100,
                "getManaMax": 100,
                "getName": "actual-player",
            }[method]

        driver = SimpleNamespace(
            test=self,
            case=SimpleNamespace(branches=("nouraajd.potion.life.used",)),
            map_name="nouraajd",
            game_map=world,
            player=player,
            item=item,
            state=state,
            coords=lambda: (4, 5, 0),
            call=call,
            pump=Mock(),
            assertSurvival=Mock(),
            check=Mock(),
        )
        return driver

    def stockDriver(self, *, gold=0):
        handles = {
            name: {"__handle__": name}
            for name in ("player", "shop", "market", "life", "mana", "gift", "starter", "quest", "kept-potion")
        }
        state = {
            "gold": gold,
            "stock": [handles["life"], handles["mana"]],
            "owned": [handles[name] for name in ("gift", "starter", "quest", "kept-potion")],
            "sold": [],
            "bought": [],
        }
        types = {"life": "LifePotion", "mana": "ManaPotion", "kept-potion": "LesserLifePotion"}
        prices = {"life": 800, "mana": 1600}

        def call(handle, method, *args):
            identity = handle["__handle__"]
            if method == "getObjectProperty":
                return handles["market"]
            if method == "getItems":
                return list(state["owned"] if identity == "player" else state["stock"])
            if method == "getEquipped":
                return {"hand": handles["starter"]}
            if method == "getTypeId":
                return types.get(identity, identity)
            if method == "getName":
                return identity
            if method == "hasTag":
                return identity == "quest"
            if method == "getSellCost":
                return prices[args[0]["__handle__"]]
            if method == "getBuyCost":
                return 5000
            if method == "sellItem":
                actual_item = args[1]
                price = prices[actual_item["__handle__"]]
                self.assertIn(actual_item, state["stock"])
                self.assertGreaterEqual(state["gold"], price)
                state["gold"] -= price
                state["stock"].remove(actual_item)
                state["owned"].append(actual_item)
                state["bought"].append(actual_item)
                return True
            self.fail((handle, method, args))

        def sell(name, item):
            self.assertEqual("shop", name)
            self.assertIn(item, state["owned"])
            state["owned"].remove(item)
            state["stock"].append(item)
            state["gold"] += 5000
            state["sold"].append(item)

        driver = SimpleNamespace(
            test=self,
            map_name="nouraajd",
            player=handles["player"],
            case=SimpleNamespace(branches=("nouraajd.potion.life.used", "nouraajd.potion.mana.used")),
            branches={},
            call=call,
            object=lambda name: handles["shop"],
            navigateTo=Mock(),
            sellAt=sell,
            gold=lambda: state["gold"],
        )
        return driver, state, handles

    def testStockPreparationUsesOnlyFiniteEarnedNonQuestUnequippedLoot(self):
        driver, state, handles = self.stockDriver()
        preparePotionStock(driver, "shop", {"gift", "starter", "quest", "kept-potion"})
        self.assertEqual([handles["gift"]], state["sold"])
        self.assertEqual(
            [handles["mana"]], state["bought"], "An existing ordinary life potion needs no replacement purchase"
        )
        self.assertEqual(3400, state["gold"])
        self.assertTrue(all(handles[name] in state["owned"] for name in ("starter", "quest", "kept-potion", "mana")))

    def testUnfundedStockNeverSellsStartingOrQuestItemsOrClaimsCredit(self):
        driver, state, _handles = self.stockDriver()
        with self.assertRaisesRegex(AssertionError, "Actual earned funds/loot"):
            preparePotionStock(driver, "shop", {"starter", "quest", "kept-potion"})
        self.assertEqual([], state["sold"])
        self.assertEqual([], state["bought"])
        self.assertEqual({}, driver.branches)

    def testMandatoryConsumptionCannotPassWithoutAnActualEventOrDeficit(self):
        driver = self.manualDriver()
        driver.branches = {}
        driver.assertNativeCombatOutcomes = Mock()
        driver.state["hp"] = 100
        with self.assertRaisesRegex(AssertionError, "actual native item-use event"):
            requirePotionConsumptions(driver, categories=("life",))
        driver.check.assert_not_called()
        driver.state["hp"] = 25
        driver.check = lambda branch, condition, **evidence: driver.branches.__setitem__(branch, evidence)
        with patch("tests.gameplay_routes_services.nativeCheckpoint", return_value=0), patch(
            "tests.gameplay_routes_services.nativeEventsSince", side_effect=lambda *args: driver.state["events"]
        ):
            requirePotionConsumptions(driver, categories=("life",))
        self.assertIn("nouraajd.potion.life.used", driver.branches)
        self.assertEqual(1, len(driver.state["events"]))
        consumePotionsAtDeficits(driver, categories=("life",))
        self.assertEqual(1, len(driver.state["events"]), "One witnessed branch never spends another potion")

    def testCaveFundingHookRunsAfterFirstActualEncounterBeforeRemainingCaves(self):
        from tests.gameplay_routes_maps import visitCaves

        actions = []
        entered = set()
        driver = SimpleNamespace(
            test=self,
            object=lambda name, required=False: None if name in entered else {"__handle__": name},
            call=lambda *args: 0,
            navigateTo=lambda name: (actions.append("enter-" + name), entered.add(name)),
            check=lambda branch, condition, **evidence: (self.assertTrue(condition), actions.append(branch)),
        )
        with patch("tests.gameplay_routes_maps.clearHostiles", side_effect=lambda d: actions.append("combat")):
            visitCaves(driver, ("first", "second"), "map", after_first=lambda: actions.append("buy-owned-potions"))
        self.assertEqual(
            [
                "enter-first",
                "combat",
                "map.cave.first",
                "buy-owned-potions",
                "enter-second",
                "combat",
                "map.cave.second",
            ],
            actions,
        )

    def testNineResolvedCombatConsumesAtActualDeficitBeforeRoadRecovery(self):
        from tests.gameplay_routes_ninemarches import afterCombat

        state = {"hp": 50, "mana": 80}
        actions = []
        driver = SimpleNamespace(
            test=self,
            player={"__handle__": "player"},
            recoveryEnabled=True,
            _marches_combat_seq=7,
            call=lambda handle, method: (
                state["hp" if method == "getHp" else "mana"] if method in ("getHp", "getMana") else 100
            ),
            roadRecoveryTarget=lambda **kwargs: (1, 1, 0),
            record=Mock(),
        )

        def recover(**kwargs):
            actions.append("road-recovery")
            state.update(hp=100, mana=100)
            return 2

        driver.recoverOnAuthoredRoad = recover
        with patch("tests.gameplay_routes_ninemarches.newCombatWitness", return_value=True), patch(
            "tests.gameplay_routes_ninemarches.consumePotionsAtDeficits",
            side_effect=lambda d: actions.append(("actual-deficit-potion-hook", dict(state))),
        ), patch("tests.gameplay_routes_ninemarches.recoveryRoadCells", return_value=frozenset()):
            afterCombat(driver)
        self.assertEqual([("actual-deficit-potion-hook", {"hp": 50, "mana": 80}), "road-recovery"], actions)
        with patch("tests.gameplay_routes_ninemarches.newCombatWitness", return_value=False), patch(
            "tests.gameplay_routes_ninemarches.consumePotionsAtDeficits"
        ) as consume:
            afterCombat(driver)
        consume.assert_not_called()

    def testNinePotionRouteRetainsQuestFundedOwnedStockForRegionalCombat(self):
        from tests import gameplay_routes_consumables as routes

        player, gift, potion = ({"__handle__": name} for name in ("player", "earned-aegis", "owned-potion"))
        state = {"owned": [], "actions": []}
        driver = SimpleNamespace(
            test=self,
            player=player,
            call=lambda handle, method: list(state["owned"]) if method == "getItems" else "aegisOfHalda",
        )

        def recruit(d, companion):
            self.assertEqual("halda", companion)
            state["actions"].append("actual-recruit-gift")
            state["owned"].append(gift)
            return "companionKnight", "knightDialog", "aegisOfHalda"

        def stock(d, market, earned, **kwargs):
            self.assertEqual("gravewatchBarter", market)
            self.assertEqual({"earned-aegis"}, earned)
            state["actions"].append("finite-purchase")
            state["owned"].append(potion)

        def combat(d, *, start_new):
            self.assertFalse(start_new, "Restarting would discard real earned stock")
            self.assertIn(potion, state["owned"])
            state["actions"].append("regional-combat-with-owned-potion")

        with patch.object(routes, "startMarches", side_effect=lambda d: state["actions"].append("start")), patch.object(
            routes, "walk", side_effect=lambda d, name: state["actions"].append(name)
        ), patch.object(routes, "recruit", side_effect=recruit), patch.object(
            routes, "preparePotionStock", side_effect=stock
        ), patch.object(
            routes, "regionalCombat", side_effect=combat
        ), patch.object(
            routes,
            "requirePotionConsumptions",
            side_effect=lambda d: state["actions"].append("mandatory-native-receipts"),
        ):
            routes.marchesPotions(driver)
        self.assertEqual(
            [
                "start",
                "learningStone",
                "actual-recruit-gift",
                "finite-purchase",
                "regional-combat-with-owned-potion",
                "mandatory-native-receipts",
            ],
            state["actions"],
        )

    def testTestMapGuaranteedSwordFundsPotionBeforeRemainingCombat(self):
        from tests import gameplay_routes_maps as routes

        class StopAfterCombat(Exception):
            pass

        player, sword, potion = ({"__handle__": name} for name in ("player", "actual-chaos-sword", "purchased-life"))
        state = {"owned": [], "actions": []}

        def navigate(name):
            self.assertEqual("chaosSword", name)
            state["owned"].append(sword)
            state["actions"].append("actual-sword-pickup")

        driver = SimpleNamespace(
            test=self,
            player=player,
            game_map={"__handle__": "map"},
            startMap=Mock(),
            tick=Mock(),
            coords=lambda: (1, 1, 0),
            call=lambda handle, method: list(state["owned"]) if method == "getItems" else 1,
            count=lambda type_id: int(sword in state["owned"]),
            navigateTo=navigate,
            check=lambda branch, condition, **evidence: self.assertTrue(condition),
        )

        def market(d, purchased, earned_items=()):
            if purchased:
                self.assertEqual({"actual-chaos-sword"}, earned_items)
                state["owned"].remove(sword)
                state["owned"].append(potion)
                state["actions"].append("purchased-owned-life")
            else:
                self.assertEqual([], state["owned"])
                state["actions"].append("initial-refusal")

        def combat(d):
            self.assertIn(potion, state["owned"])
            state["actions"].append("remaining-native-combat")
            raise StopAfterCombat

        positions = {
            name: (1, 1, 0) for name in ("chest", "groundHole", "teleporter1", "teleporter2", "teleporter3", "market1")
        }
        with patch.object(routes, "verifyWaypointPublication"), patch.object(
            routes, "hostiles", return_value=["enemy"]
        ), patch("tests.narrative_walkthrough.authoredRegion", return_value=(positions, {(1, 1, 0)})), patch(
            "tests.castle_walkthrough.shortestRoute", return_value=()
        ), patch.object(
            routes, "testMarket", side_effect=market
        ), patch.object(
            routes, "clearHostiles", side_effect=combat
        ):
            with self.assertRaises(StopAfterCombat):
                routes.testMap(driver)
        self.assertEqual(
            ["initial-refusal", "actual-sword-pickup", "purchased-owned-life", "remaining-native-combat"],
            state["actions"],
        )

    def testManualOwnedUseNeedsActualCallbackExactStateAndNativeReceipt(self):
        driver = self.manualDriver()
        with patch("tests.gameplay_routes_services.nativeCheckpoint", return_value=0), patch(
            "tests.gameplay_routes_services.nativeEventsSince", side_effect=lambda *args: driver.state["events"]
        ):
            useOwnedPotion(driver, driver.item, "nouraajd.potion.life.used")
        self.assertEqual(65, driver.state["hp"])
        self.assertEqual([{"__handle__": "retained-item"}], driver.state["owned"])
        driver.check.assert_called_once()
        self.assertEqual("potion", driver.check.call_args.kwargs["ownedIdentity"])

    def testManualUseRejectsBorrowedFullResourceAndMissingReceipt(self):
        for defect in ("borrowed", "no-deficit", "missing-receipt"):
            with self.subTest(defect=defect):
                driver = self.manualDriver()
                if defect == "borrowed":
                    driver.state["owned"].remove(driver.item)
                elif defect == "no-deficit":
                    driver.state["hp"] = 100
                with patch("tests.gameplay_routes_services.nativeCheckpoint", return_value=0), patch(
                    "tests.gameplay_routes_services.nativeEventsSince", return_value=[]
                ):
                    with self.assertRaises(AssertionError):
                        useOwnedPotion(driver, driver.item, "nouraajd.potion.life.used")
                driver.check.assert_not_called()
