# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source-executing recipe funding checks; fake markets confer no native gameplay credit."""

from collections import Counter
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests import gameplay_routes_crafting as crafting
from tests import gameplay_routes_recipe_gold as routes
from tests.test_gameplay_route_dialogs import authoredFunction

ROOT = Path(__file__).resolve().parents[1]


class GameplayRecipeGoldRoutesTest(unittest.TestCase):
    def nourDriver(self, *, ingredient_lost=False):
        state = {"gold": 0, "flags": {}, "victor": "encounter_active"}
        types = {
            "portal": "TownPortalScroll",
            "starter": "Staff",
            "letter": "letterFromRolf",
            "skull": "skullOfRolf",
            "small1": "LesserLifePotion",
            "small2": "LesserLifePotion",
            "small3": "LesserLifePotion",
        }
        owned, stock = {"portal", "starter", "letter"}, {"small1", "small2", "small3"}
        player, game_map, market = ({"__handle__": name} for name in ("player", "map", "market"))
        transactions, order = [], []
        equipped = {"0": {"__handle__": "starter"}}

        def claim_once(world, key):
            if state["flags"].get(key):
                return False
            state["flags"][key] = True
            return True

        native_player = SimpleNamespace(
            getGold=lambda: state["gold"],
            addGold=lambda value: state.update(gold=state["gold"] + value),
            getHp=lambda: 70,
            getHpMax=lambda: 70,
            getMana=lambda: 35,
            getManaMax=lambda: 35,
            healProc=Mock(),
            setBoolProperty=lambda key, value: state["flags"].update({key: value}),
            setStringProperty=Mock(),
            getNumericProperty=lambda name: state["gold"] if name == "gold" else 0,
            countItems=lambda item_type: sum(types[identity] == item_type for identity in owned),
            removeItem=Mock(side_effect=AssertionError("A gold refusal cannot consume an ingredient")),
        )
        game = SimpleNamespace(getGuiHandler=lambda: SimpleNamespace(showTrade=Mock()))
        world = SimpleNamespace(
            getGame=lambda: game,
            getPlayer=lambda: native_player,
            getBoolProperty=lambda key: state["flags"].get(key, False),
        )
        game.getMap = lambda: world
        game.createObject = lambda identity: SimpleNamespace(getStates=lambda: [])
        source = "res/maps/nouraajd/script.py"
        apply_aid = authoredFunction(source, "_applyRaceService", class_id="TownHallDialog", showReader=Mock())
        aid_dialog = SimpleNamespace(
            getGame=lambda: game, _canOfferRaceService=lambda identity: identity == "humanRace"
        )
        aid_dialog._applyRaceService = lambda *args: apply_aid(aid_dialog, *args)
        aid = authoredFunction(source, "claimHumanRation", class_id="TownHallDialog")
        gooby = authoredFunction(
            source,
            "onComplete",
            class_id="MainQuest",
            claim_once=claim_once,
            rewardSnapshot=Mock(),
            showRewardReceipt=Mock(),
            MAIN_QUEST_GOLD_REWARD=200,
        )
        quest_system = SimpleNamespace(
            get_state=lambda identity: state["victor"], mark_victor_good_end=lambda: state.update(victor="good_end")
        )
        rescue = authoredFunction(
            source,
            "trigger",
            class_id="CultLeaderQuestTrigger",
            _quest_system_from=lambda obj: quest_system,
            claim_once=claim_once,
            rewardSnapshot=Mock(),
            showRewardReceipt=Mock(),
            narrative=SimpleNamespace(victorResponse=lambda game: ""),
            _clear_victor_encounter=Mock(),
        )

        def call(handle, method, *args):
            identity = handle["__handle__"]
            if method == "getItems":
                return [{"__handle__": key} for key in sorted(owned if handle == player else stock)]
            if method == "getTypeId":
                return types[identity]
            if method == "getName":
                return identity
            if method == "getEquipped":
                return dict(equipped)
            if method == "getObjectProperty":
                self.assertEqual(("market1", "market"), (identity, args[0]))
                return market
            if method == "hasTag":
                return identity in {"letter", "skull"}
            if method == "getSellCost":
                return 400
            if method == "getBuyCost":
                return 160 if args[0]["__handle__"] == "portal" else 320
            if method == "sellItem":
                selected = args[1]["__handle__"]
                self.assertIn(selected, stock)
                self.assertGreaterEqual(state["gold"], 400)
                stock.remove(selected)
                owned.add(selected)
                state["gold"] -= 400
                transactions.append(("purchase", selected, 400, state["gold"]))
                return True
            if method == "getBoolProperty":
                return False
            if method in {"getHp", "getMana", "getTurn", "getNumericProperty"}:
                return 12
            raise AssertionError((identity, method, args))

        def sellAt(name, item):
            self.assertEqual("market1", name)
            identity = item["__handle__"]
            self.assertIn(identity, owned)
            price = 160 if identity == "portal" else 320
            owned.remove(identity)
            stock.add(identity)
            state["gold"] += price
            transactions.append(("sale", identity, price, state["gold"]))

        namespace = {"randint": Mock(side_effect=AssertionError("The gold branch cannot roll"))}
        tree = ast.parse((ROOT / "res/plugins/crafting.py").read_text(encoding="utf-8"))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        exec(compile(ast.Module(body=functions, type_ignores=[]), "res/plugins/crafting.py", "exec"), namespace)

        def engine(name, game_handle, station, recipe_id):
            self.assertEqual(("craftRecipe", "brew_life_potion"), (name, recipe_id))
            recipe = crafting.recipeDefinitions()[recipe_id]
            return namespace["apply_recipe"](
                game,
                native_player,
                {"inputs": namespace["_normalize_item_entries"](recipe["inputs"]), "gold": recipe["gold"]},
            )

        def raceAid(driver):
            order.append("human-aid")
            self.assertTrue(aid(aid_dialog))

        def prepare(driver):
            order.append("real-Rolf")
            owned.add("skull")

        def hunt(method):
            self.assertEqual("finishOriginalMainQuest", method)
            order.append("real-Gooby")
            gooby(SimpleNamespace(getGame=lambda: game))

        def victor(driver, approach, **kwargs):
            self.assertEqual("deescalated", approach)
            self.assertEqual({"direct": False, "saved": True, "start_new": False, "ask_girl": True}, kwargs)
            order.append("real-Victor")
            rescue(SimpleNamespace(getGame=lambda: game), object(), object())

        def station(driver, name, *, navigate=None):
            self.assertEqual("alchemyTable1", name)
            if ingredient_lost:
                owned.remove("small1")
            return ({"id": "brew_life_potion", "enabled": False},)

        driver = SimpleNamespace(
            test=self,
            player=player,
            game_map=game_map,
            game={"__handle__": "game"},
            race_id="humanRace",
            recoveryEnabled=True,
            call=call,
            gold=lambda: state["gold"],
            hunt=hunt,
            questNames=lambda completed=False: ["mainQuest"],
            coords=lambda: (105, 110, 0),
            object=lambda name: {"__handle__": name},
            record=Mock(),
            sellAt=sellAt,
            engine=Mock(side_effect=engine),
            pump=Mock(),
            check=Mock(),
            navigateTo=Mock(),
        )
        for target, name, function in (
            (routes, "raceAid", raceAid),
            (routes, "prepareRolf", prepare),
            (routes, "victorRoute", victor),
            (routes, "visitService", Mock()),
            (crafting, "openStation", station),
        ):
            patcher = patch.object(target, name, function)
            patcher.start()
            self.addCleanup(patcher.stop)
        return driver, state, owned, stock, transactions, order

    def testNourGoldRefusalUsesActualHumanAidGoobyAndVictorPayoutsThenOneFiniteReagentBuyback(self):
        driver, state, owned, stock, transactions, order = self.nourDriver()
        routes.nourLifeGoldRefusal(driver)
        self.assertEqual(["human-aid", "real-Rolf", "real-Gooby", "real-Victor"], order)
        self.assertEqual(
            [
                ("sale", "portal", 160, 880),
                ("purchase", "small1", 400, 480),
                ("purchase", "small2", 400, 80),
                ("sale", "small1", 320, 400),
                ("purchase", "small1", 400, 0),
            ],
            transactions,
        )
        self.assertEqual({"starter", "letter", "skull", "small1", "small2"}, owned)
        self.assertEqual({"small3", "portal"}, stock)
        self.assertEqual(0, state["gold"])
        driver.engine.assert_called_once()
        self.assertEqual({"ok": False, "reason": "missing:gold"}, driver.check.call_args.kwargs["result"])
        self.assertTrue(driver.recoveryEnabled)

    def testNourGoldRefusalDoesNotCountAnIngredientConsumedOnTheActualStationApproach(self):
        driver, _state, _owned, _stock, _transactions, _order = self.nourDriver(ingredient_lost=True)
        with self.assertRaisesRegex(AssertionError, "every actual ingredient"):
            routes.nourLifeGoldRefusal(driver)
        driver.engine.assert_not_called()
        driver.check.assert_not_called()
        self.assertTrue(driver.recoveryEnabled)

    def driver(self, *, corruption=None):
        definitions = {}
        for source in ("res/config/items.json", "res/config/potions.json", "res/maps/ninemarches/config.json"):
            definitions.update(json.loads((ROOT / source).read_text(encoding="utf-8")))
        stock_types = [entry["ref"] for entry in definitions["gravewatchMarket"]["properties"]["items"]]
        items = {"stock-" + item_type: item_type for item_type in stock_types}
        items.update({"entry-scroll": "TownPortalScroll", "starter-weapon": "Sword", "gift": "aegisOfHalda"})
        owned, stock = {"entry-scroll", "starter-weapon"}, {"stock-" + item_type for item_type in stock_types}
        state = {"gold": 0, "reputation": 0, "flags": {}, "coords": (500, 662, 0)}
        transactions, attempts = [], []
        player, game_map, market = ({"__handle__": identity} for identity in ("player", "map", "market"))
        equipped = {"0": {"__handle__": "starter-weapon"}}

        def quote(identity, *, buying):
            power = definitions[items[identity]]["properties"]["power"]
            price = min(5000 if buying else 100000, 2**power * 200 * (80 if buying else 100) // 100)
            return price + (1 if corruption == "quote" and identity == "stock-Scroll" and not buying else 0)

        def handles(identities):
            return [{"__handle__": identity} for identity in sorted(identities)]

        def call(handle, method, *args):
            identity = handle["__handle__"]
            if method == "getItems":
                return handles(owned if handle == player else stock)
            if method == "getTypeId":
                return items[identity]
            if method == "getName":
                return "townPortalScroll" if identity == "entry-scroll" else identity
            if method == "getEquipped":
                return dict(equipped)
            if method == "hasTag":
                return False
            if method == "getObjectProperty":
                self.assertEqual(("gravewatchBarter", "market"), (identity, args[0]))
                return market
            if method in {"getSellCost", "getBuyCost"}:
                return quote(args[0]["__handle__"], buying=method == "getBuyCost")
            if method == "sellItem":
                self.assertEqual(player, args[0])
                bought = args[1]["__handle__"]
                price = quote(bought, buying=False)
                self.assertIn(bought, stock)
                self.assertGreaterEqual(state["gold"], price)
                stock.remove(bought)
                owned.add(bought)
                state["gold"] -= price
                transactions.append(("purchase", bought, price, state["gold"]))
                if corruption == "stock-transfer" and bought == "stock-LifePotion":
                    stock.add(bought)
                return True
            if method == "getBoolProperty":
                return True if args[0] == "enabled" else state["flags"].get(args[0], False)
            if method == "getType":
                return "CraftingStation"
            if method == "getStringProperty":
                return "scribeDesk" if args[0] == "craftingStationId" else "Gravewatch Scribe"
            if method in {"getTurn", "getHp", "getMana"}:
                return {"getTurn": 12, "getHp": 70, "getMana": 35}[method]
            if method == "getNumericProperty":
                return state.get(args[0], 0)
            raise AssertionError((identity, method, args))

        def sellAt(name, item):
            self.assertEqual("gravewatchBarter", name)
            identity = item["__handle__"]
            self.assertNotEqual("starter-weapon", identity)
            self.assertIn(identity, owned)
            owned.remove(identity)
            stock.add(identity)
            price = quote(identity, buying=True)
            state["gold"] += price
            transactions.append(("sale", identity, price, state["gold"]))

        def addItem(item_type):
            self.assertEqual("aegisOfHalda", item_type)
            owned.add("gift")

        native_player = SimpleNamespace(
            isPlayer=lambda: True,
            addGold=lambda value: state.update(gold=state["gold"] + value),
            healProc=Mock(),
            addItem=addItem,
            checkQuests=Mock(),
            getNumericProperty=lambda name: state.get(name, 0),
            setNumericProperty=lambda name, value: state.update({name: value}),
            countItems=lambda item_type: sum(items[identity] == item_type for identity in owned),
        )
        game = SimpleNamespace(getGuiHandler=lambda: SimpleNamespace(notify=Mock()))
        world = SimpleNamespace(
            getGame=lambda: game,
            getPlayer=lambda: native_player,
            getBoolProperty=lambda name: state["flags"].get(name, False),
            setBoolProperty=lambda name, value: state["flags"].update({name: value}),
        )
        game.getMap = lambda: world
        learning = authoredFunction("res/maps/ninemarches/script.py", "onEnter", class_id="LearningStone")
        recruit = authoredFunction(
            "res/maps/ninemarches/script.py",
            "recruit",
            class_id="CompanionDialog",
            adjust_reputation=authoredFunction("res/maps/ninemarches/script.py", "adjust_reputation"),
            rewardSnapshot=Mock(),
            showRewardReceipt=Mock(),
        )

        def walk(driver, name, adjacent=False):
            state["coords"] = (520, 644, 0) if name == "learningStone" else (514, 652, 0)
            if name == "learningStone":
                learning(SimpleNamespace(getMap=lambda: world), SimpleNamespace(getCause=lambda: native_player))
            if name == "gravewatchScribe" and corruption == "ingredient-consumed":
                owned.discard("stock-ManaPotion")

        def recruitNine(driver, companion):
            self.assertEqual("halda", companion)
            recruit(
                SimpleNamespace(
                    getGame=lambda: game,
                    can_recruit=lambda: True,
                    JOINED_FLAG="halda_joined",
                    BOON="aegisOfHalda",
                )
            )
            return "companionKnight", "knightDialog", "aegisOfHalda"

        source = "res/plugins/crafting.py"
        status = authoredFunction(source, "_status")
        verify = authoredFunction(
            source,
            "verify_inventory_requirements",
            count_inventory_matches=authoredFunction(source, "count_inventory_matches"),
            _status=status,
        )
        mutation = Mock(side_effect=AssertionError("A gold refusal must not consume anything or roll"))
        apply_recipe = authoredFunction(
            source,
            "apply_recipe",
            verify_inventory_requirements=verify,
            has_enough_gold=authoredFunction(source, "has_enough_gold", _status=status),
            remove_required_items=mutation,
            deduct_gold=mutation,
            randint=mutation,
            create_reward_objects=mutation,
            _status=status,
        )
        normalize_entries = authoredFunction(
            source, "_normalize_item_entries", _coerce_count=authoredFunction(source, "_coerce_count")
        )

        def engine(name, _game, _station, recipe_id):
            self.assertEqual("craftRecipe", name)
            recipe = crafting.recipeDefinitions()[recipe_id]
            result = apply_recipe(
                game,
                native_player,
                {"inputs": normalize_entries(recipe["inputs"]), "gold": recipe["gold"]},
            )
            attempts.append(result)
            return result

        def visit(driver, name, event, *, navigate=None):
            navigate(name, adjacent=True)
            navigate(name)
            if event == "trade_requested":
                return ({"seq": 1},)
            self.assertEqual(("gravewatchScribe", "choice_requested"), (name, event))
            choices = [
                {"id": identity, "enabled": False}
                for identity, recipe in crafting.recipeDefinitions().items()
                if recipe["station"] == "scribeDesk"
            ]
            payload = json.dumps(choices)
            return (
                {
                    "seq": 2,
                    "title": "Gravewatch Scribe",
                    "headless": True,
                    "choicesJson": payload,
                    "choicesJsonLength": len(payload.encode()),
                    "actionLabel": "Craft",
                    "backLabel": "Leave station",
                    "playerCoords": dict(zip("xyz", state["coords"])),
                    "player": {"name": "player"},
                },
            )

        driver = SimpleNamespace(
            test=self,
            player=player,
            game_map=game_map,
            game={"__handle__": "game"},
            gold=lambda: state["gold"],
            call=call,
            coords=lambda: state["coords"],
            count=native_player.countItems,
            flag=world.getBoolProperty,
            object=lambda name: {"__handle__": name},
            sellAt=sellAt,
            engine=Mock(side_effect=engine),
            pump=Mock(),
            record=Mock(),
            check=Mock(),
            questNames=lambda completed=False: [],
            recoveryEnabled=True,
            _marches_retreat_scroll_name="townPortalScroll",
        )
        for target, method, replacement in (
            (routes, "startNine", Mock()),
            (routes, "walkNine", walk),
            (routes, "recruitNine", recruitNine),
            (routes, "visitService", visit),
            (crafting, "visitService", visit),
        ):
            patcher = patch.object(target, method, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        return driver, state, owned, stock, transactions, attempts, mutation

    def testAuthoredFundingSpendsFiniteStockOnceAndPreservesTheActualRecipeInputs(self):
        driver, state, owned, stock, transactions, attempts, mutation = self.driver()
        routes.nineScrollGoldRefusal(driver)
        self.assertEqual(2, state["reputation"], "Real Halda recruitment gives reputation and a gift, never gold")
        self.assertEqual(("sale", "gift", 5000, 5120), transactions[0])
        self.assertEqual(5, len(transactions[1:6]))
        self.assertEqual(520, transactions[5][3])
        self.assertEqual(
            [
                ("sale", "stock-LifePotion", 640, 1160),
                ("purchase", "stock-LifePotion", 800, 360),
                ("sale", "stock-GreaterLifePotion", 1280, 1640),
                ("purchase", "stock-GreaterLifePotion", 1600, 40),
                ("sale", "entry-scroll", 160, 200),
                ("purchase", "entry-scroll", 200, 0),
            ],
            transactions[6:],
        )
        sales = Counter(identity for role, identity, *_ in transactions if role == "sale")
        self.assertEqual(
            Counter({"gift": 1, "stock-LifePotion": 1, "stock-GreaterLifePotion": 1, "entry-scroll": 1}), sales
        )
        self.assertTrue({"starter-weapon", "entry-scroll", "stock-Scroll", "stock-ManaPotion"} <= owned)
        self.assertEqual({"gift"}, stock)
        self.assertEqual(0, state["gold"])
        self.assertEqual([{"ok": False, "reason": "missing:gold"}], attempts)
        mutation.assert_not_called()
        driver.engine.assert_called_once()
        driver.check.assert_called_once()
        self.assertTrue(driver.recoveryEnabled)

    def testConsumedIngredientCannotBeCountedAsAGoldRefusal(self):
        driver, _state, _owned, _stock, _transactions, attempts, mutation = self.driver(
            corruption="ingredient-consumed"
        )
        with self.assertRaisesRegex(AssertionError, "every actual ingredient"):
            routes.nineScrollGoldRefusal(driver)
        self.assertEqual([], attempts)
        driver.engine.assert_not_called()
        driver.check.assert_not_called()
        mutation.assert_not_called()
        self.assertTrue(driver.recoveryEnabled)

    def testChangedQuoteOrIncorrectTransferFailsWithoutRetryOrCreditingTheBranch(self):
        for corruption in ("quote", "stock-transfer"):
            with self.subTest(corruption=corruption):
                driver, _state, _owned, _stock, transactions, attempts, _mutation = self.driver(corruption=corruption)
                with self.assertRaises(AssertionError):
                    routes.nineScrollGoldRefusal(driver)
                self.assertEqual([], attempts)
                self.assertLessEqual(len(transactions), 4)
                driver.engine.assert_not_called()
                driver.check.assert_not_called()
                self.assertTrue(driver.recoveryEnabled)

    def testTheIndependentCaseRetainsAllFiveClassesAndOnlyItsWitnessedGoldBranch(self):
        case = next(value for value in routes.CASES if value.id == "ninemarches_recipe_gold_scroll")
        self.assertEqual(("Warrior", "Sorcerer", "Assasin", "Inquisitor", "Wayfarer"), case.classes)
        self.assertEqual(("ninemarches.crafting.craft_town_portal_scroll.insufficientGold",), case.branches)
        nour = next(value for value in routes.CASES if value.id == "nouraajd_recipe_gold_life")
        self.assertEqual(case.classes, nour.classes)
        self.assertEqual("humanRace", nour.race)
        self.assertIn("nouraajd.crafting.brew_life_potion.insufficientGold", nour.branches)
