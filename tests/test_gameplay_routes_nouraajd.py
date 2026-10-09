# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure Nouraajd service sequencing and finite earned-funding regressions."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests import gameplay_routes_nouraajd as nouraajd
from tests.test_gameplay_route_dialogs import authoredFunction


class GameplayNouraajdServiceRoutesTest(unittest.TestCase):
    def testPaidRaceAidEarnsTheGoobyRewardAfterRolfsUnpaidQuest(self):
        class ReachedUnneededAid(Exception):
            pass

        for race_id in ("outlanderRace", "highlanderRace", "wandererRace"):
            with self.subTest(race=race_id):
                state = {"gold": 0, "completed": [], "claims": set(), "order": []}
                player = SimpleNamespace(
                    getGold=lambda: state["gold"],
                    addGold=lambda amount: state.update(gold=state["gold"] + amount),
                    getHp=lambda: 100,
                    getHpMax=lambda: 100,
                    getMana=lambda: 100,
                    getManaMax=lambda: 100,
                )
                game_map = SimpleNamespace(getPlayer=lambda: player)
                game = SimpleNamespace(getMap=lambda: game_map, getGuiHandler=lambda: SimpleNamespace(notify=Mock()))

                def claim_once(owner, name):
                    if name in state["claims"]:
                        return False
                    state["claims"].add(name)
                    return True

                rolf_complete = authoredFunction("res/maps/nouraajd/script.py", "onComplete", class_id="RolfQuest")
                gooby_complete = authoredFunction(
                    "res/maps/nouraajd/script.py",
                    "onComplete",
                    class_id="MainQuest",
                    claim_once=claim_once,
                    MAIN_QUEST_GOLD_REWARD=200,
                    rewardSnapshot=Mock(return_value={}),
                    showRewardReceipt=Mock(),
                )
                apply_aid = authoredFunction(
                    "res/maps/nouraajd/script.py", "_applyRaceService", class_id="TownHallDialog", showReader=Mock()
                )
                owner = SimpleNamespace(getGame=lambda: game)
                dialog = SimpleNamespace(
                    getGame=lambda: game, _canOfferRaceService=lambda identity: identity == race_id
                )

                def prepare(driver):
                    rolf_complete(owner)
                    state["completed"].append("rolfQuest")
                    state["order"].append("rolf-unpaid")
                    self.assertEqual(0, state["gold"], "Rolf's authored quest completion pays no gold")

                def hunt(method, *args):
                    if method == "finishOriginalMainQuest":
                        gooby_complete(owner)
                        state["completed"].append("mainQuest")
                        state["order"].append("gooby-reward")
                    elif method == "recoverOnRoadPair":
                        state["order"].append("actual-road-recovery")
                    else:
                        self.fail((method, args))

                def check(branch, condition, **evidence):
                    self.assertTrue(condition, (branch, evidence))
                    if branch.endswith(".unneeded"):
                        state["order"].append("funded-unneeded-aid")
                        raise ReachedUnneededAid

                def choose(dialog_id, action, **kwargs):
                    _suffix, _gold, hp, mana = nouraajd.RACES[race_id]
                    self.assertFalse(apply_aid(dialog, race_id, 5, hp, mana, "aid"))

                def call(handle, method, *args):
                    if method == "getBoolProperty":
                        return False
                    return getattr(player, method)()

                driver = SimpleNamespace(
                    test=self,
                    race_id=race_id,
                    player={"__handle__": "player"},
                    gold=player.getGold,
                    navigateTo=Mock(),
                    condition=lambda dialog_id, name: name == "canOffer" + nouraajd.RACES[race_id][0],
                    choose=choose,
                    check=check,
                    call=call,
                    hunt=Mock(side_effect=hunt),
                    questNames=lambda completed=False: list(state["completed"]) if completed else [],
                )
                with patch.object(nouraajd, "start"), patch.object(nouraajd, "prepareRolf", side_effect=prepare):
                    with self.assertRaises(ReachedUnneededAid):
                        nouraajd.raceAid(driver)
                self.assertEqual(200, state["gold"])
                self.assertEqual(
                    ["rolf-unpaid", "gooby-reward", "actual-road-recovery", "funded-unneeded-aid"], state["order"]
                )

    def testLetterAndRelicJournalAssertionsFollowTheNextOrdinaryNativeTurn(self):
        for route, quest_class, quest_id, predicate in (
            (nouraajd.letter, "DeliverLetterQuest", "deliverLetterQuest", "is_letter_delivered"),
            (nouraajd.handInRelic, "RetrieveRelicQuest", "retrieveRelicQuest", "is_relic_returned"),
        ):
            with self.subTest(quest=quest_id):
                state = {"resolved": False, "item": 1, "completed": [], "order": []}
                quest_system = SimpleNamespace(**{predicate: lambda: state["resolved"]})
                is_completed = authoredFunction(
                    "res/maps/nouraajd/script.py",
                    "isCompleted",
                    class_id=quest_class,
                    _quest_system_from=lambda owner: quest_system,
                )

                def choose(*args, **kwargs):
                    state.update(resolved=True, item=0)
                    self.assertTrue(is_completed(None))
                    self.assertEqual([], state["completed"], "Dialog callbacks do not run CPlayer.checkQuests")
                    state["order"].append("actual-delivery")

                def tick():
                    self.assertTrue(is_completed(None))
                    state["completed"].append(quest_id)
                    state["order"].append("native-player-onTurn")

                driver = SimpleNamespace(
                    test=self,
                    player={"__handle__": "player"},
                    navigateTo=Mock(),
                    choose=Mock(side_effect=choose),
                    select=Mock(side_effect=lambda *args: state["order"].append("dialog-closed")),
                    count=lambda identity: state["item"],
                    condition=lambda dialog, condition: condition == "has_letter_quest",
                    call=lambda *args: True,
                    questNames=lambda completed=False: state["completed"] if completed else [quest_id],
                    tick=Mock(side_effect=tick),
                )
                with patch.object(nouraajd, "verifyJournals", side_effect=lambda d: state["order"].append("journal")):
                    route(driver)
                self.assertEqual(
                    ["actual-delivery", "dialog-closed", "native-player-onTurn", "journal"], state["order"][-4:]
                )
                driver.tick.assert_called_once_with()

    def testFreshServicesVisitBothActualStationsAndDeclareEveryAvailableRejection(self):
        driver = object()
        with (
            patch.object(nouraajd, "start") as start,
            patch.object(nouraajd, "marketAttempt") as market,
            patch.object(nouraajd, "readSignpost") as sign,
            patch.object(nouraajd, "openStation") as station,
            patch.object(nouraajd, "recipeAttempt") as recipe,
        ):
            nouraajd.authoredServices(driver)
        start.assert_called_once_with(driver)
        market.assert_called_once_with(driver, "market1", "nouraajd.market.insufficientGold", purchased=False)
        sign.assert_called_once_with(driver, "nouraajdSign")
        self.assertEqual(["alchemyTable1", "scribeDesk1"], [call.args[1] for call in station.call_args_list])
        actual = {call.args[2]: (call.args[1], call.kwargs["outcome"]) for call in recipe.call_args_list}
        expected = {
            identity: (
                "alchemyTable1" if value["station"] == "alchemyTable" else "scribeDesk1",
                "locked" if value.get("unlockFlag") else "missingIngredients",
            )
            for identity, value in nouraajd.recipeDefinitions().items()
        }
        self.assertEqual(expected, actual)
        self.assertEqual(len(expected), recipe.call_count)

    def testEarnedFundingNeverSellsStartingEquipmentQuestItemsOrRecipeReagents(self):
        items = {name: {"__handle__": name} for name in ("starter", "loot", "second", "reagent", "quest")}
        state = {"gold": 0}
        market = {"__handle__": "market"}

        def call(handle, method, *args):
            if method == "getObjectProperty":
                return market
            if method == "getItems":
                return list(items.values())
            if method == "getTypeId":
                return "ManaPotion" if handle == items["reagent"] else "Sword"
            if method == "hasTag":
                return handle == items["quest"]
            if method == "getBuyCost":
                return 500 if args[0] == items["loot"] else 300
            if method == "getName":
                return handle["__handle__"]
            raise AssertionError((handle, method, args))

        def sell(name, item):
            self.assertEqual("market1", name)
            self.assertIn(item["__handle__"], {"loot", "second"})
            state["gold"] += call(market, "getBuyCost", item)

        driver = SimpleNamespace(
            test=self,
            player={"__handle__": "player"},
            navigateTo=Mock(),
            object=Mock(),
            call=call,
            gold=lambda: state["gold"],
            sellAt=Mock(side_effect=sell),
        )
        earned = {"loot", "second", "reagent", "quest"}
        nouraajd.fundEarnedCrafting(driver, earned, 700)
        self.assertEqual(["loot", "second"], [call.args[1]["__handle__"] for call in driver.sellAt.call_args_list])
        self.assertEqual(800, state["gold"])

    def testInsufficientActualEarnedFundingFailsWithoutRepeatingSales(self):
        driver = SimpleNamespace(
            test=self,
            player={"__handle__": "player"},
            navigateTo=Mock(),
            object=Mock(),
            call=Mock(side_effect=lambda handle, method, *args: [] if method == "getItems" else None),
            gold=lambda: 0,
            sellAt=Mock(),
        )
        with self.assertRaisesRegex(AssertionError, "Actual earned loot did not fund"):
            nouraajd.fundEarnedCrafting(driver, set(), 20)
        driver.sellAt.assert_not_called()

    def testManaIngredientRequiresActualVictorVictoryAndItsOriginalFiniteMarket(self):
        state = {"gold": 200, "rescued": False, "order": []}
        mana = {"__handle__": "actual-mana"}

        def fight(name):
            self.assertEqual("cultLeaderQuest", name)
            state.update(gold=700, rescued=True)
            state["order"].append("actual-fight")

        driver = SimpleNamespace(
            test=self,
            hunt=Mock(side_effect=lambda *args: state["order"].append("real-Gooby")),
            questNames=lambda completed=False: {"mainQuest"},
            gold=lambda: state["gold"],
            fight=fight,
            string=lambda name: "good_end" if state["rescued"] else "encounter_active",
            flag=lambda name: state["rescued"],
            check=Mock(),
        )

        def purchase(d, market, item_type, earned, *, protected_types):
            self.assertTrue(state["rescued"])
            self.assertEqual(("victorMarket", "ManaPotion", {"loot", "actual-mana"}), (market, item_type, earned))
            self.assertIn("LesserManaPotion", protected_types)
            self.assertIn("Scroll", protected_types)
            state["order"].append("actual-purchase")
            return mana

        with (
            patch.object(nouraajd, "meetVictor", side_effect=lambda *args: state["order"].append("authored-dialog")),
            patch.object(nouraajd, "purchaseCallbackItem", side_effect=purchase),
            patch.object(nouraajd, "ownedIdentities", return_value={"starting", "loot", "actual-mana"}),
        ):
            nouraajd.earnVictorCraftingMana(driver, {"starting"})
        self.assertEqual(["real-Gooby", "authored-dialog", "actual-fight", "actual-purchase"], state["order"])
        self.assertEqual(2, driver.check.call_count)

    def testEarnedRecipesUnlockBeforeMissingWitnessThenUseOnlyActuallyPurchasedInputs(self):
        for has_mana in (False, True):
            with self.subTest(has_mana=has_mana):
                state = {"counts": {"Scroll": 0, "LesserLifePotion": 0, "ManaPotion": int(has_mana)}, "order": []}
                stock = [
                    {"__handle__": "paper", "type": "Scroll"},
                    {"__handle__": "small1", "type": "LesserLifePotion"},
                    {"__handle__": "small2", "type": "LesserLifePotion"},
                ]
                market = {"__handle__": "market"}

                def call(handle, method, *args):
                    if method == "getObjectProperty":
                        return market
                    if method == "getItems":
                        return stock
                    if method == "getTypeId":
                        return handle["type"]
                    if method == "getSellCost":
                        return 200 if args[0]["type"] == "Scroll" else 400
                    raise AssertionError((handle, method, args))

                def buy(name, identity, count):
                    state["counts"][identity] += count
                    state["order"].append(("purchase", identity, count))

                def attempt(d, station, recipe, branch, *, outcome):
                    state["order"].append((recipe, outcome))
                    if outcome == "success":
                        if recipe == "brew_life_potion":
                            self.assertGreaterEqual(state["counts"]["LesserLifePotion"], 2)
                        else:
                            self.assertGreaterEqual(state["counts"]["Scroll"], 1)
                            self.assertGreaterEqual(state["counts"]["ManaPotion"], 1)

                driver = SimpleNamespace(
                    test=self,
                    player={"__handle__": "player"},
                    navigateTo=Mock(),
                    object=Mock(),
                    call=call,
                    count=lambda identity: state["counts"].get(identity, 0),
                    buyAt=Mock(side_effect=buy),
                )
                with (
                    patch.object(nouraajd, "start", side_effect=lambda d: state["order"].append("start")),
                    patch.object(nouraajd, "letter", side_effect=lambda d: state["order"].append("earned-unlock")),
                    patch.object(nouraajd, "prepareRolf", side_effect=lambda d: state["order"].append("real-Rolf")),
                    patch.object(
                        nouraajd,
                        "earnVictorCraftingMana",
                        side_effect=lambda d, initial: state["order"].append("actual-Victor-market"),
                    ),
                    patch.object(nouraajd, "ownedIdentities", side_effect=({"starting"}, {"starting", "loot"})),
                    patch.object(nouraajd, "recipeAttempt", side_effect=attempt),
                    patch.object(nouraajd, "fundEarnedCrafting") as funding,
                    patch.object(
                        nouraajd, "marketAttempt", side_effect=lambda *args, **kwargs: buy("market1", "Scroll", 1)
                    ),
                ):
                    if has_mana:
                        nouraajd.earnedCrafting(driver)
                    else:
                        with self.assertRaisesRegex(AssertionError, "actually earned ManaPotion"):
                            nouraajd.earnedCrafting(driver)
                funding.assert_called_once_with(driver, {"loot"}, 1055)
                self.assertEqual(
                    [
                        "start",
                        "earned-unlock",
                        ("craft_town_portal_scroll", "missingIngredients"),
                        ("scribe_emergency_portal_scroll", "missingIngredients"),
                        "real-Rolf",
                    ],
                    state["order"][:5],
                )
                self.assertLess(
                    state["order"].index("actual-Victor-market"), state["order"].index(("brew_life_potion", "success"))
                )
                self.assertIn(("brew_life_potion", "success"), state["order"])
                self.assertEqual(has_mana, ("craft_town_portal_scroll", "success") in state["order"])


if __name__ == "__main__":
    unittest.main()
