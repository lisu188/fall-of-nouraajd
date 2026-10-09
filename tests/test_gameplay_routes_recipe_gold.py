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
    def greaterPlan(self, loot_quotes, **kwargs):
        return routes.finiteGreaterLifeGoldPlan(
            720,
            loot_quotes,
            ("life", 800, 640),
            (("small1", 400, 320), ("small2", 400, 320)),
            (("small3", 400, 320), ("lesserMana", 400, 320), ("scroll", 200, 160)),
            ("portal", 200, 160),
            **kwargs,
        )

    def testGreaterLifePlanRetainsTheActualVictorPotionAndUsesOnlyFiniteOnceSoldIdentities(self):
        recipes = crafting.recipeDefinitions()
        self.assertEqual((20, 100), (recipes["brew_life_potion"]["gold"], recipes["brew_life_potion"]["successChance"]))
        self.assertEqual(45, recipes["blend_greater_life_potion"]["gold"])
        self.assertEqual([{"item": "LifePotion", "count": 2}], recipes["blend_greater_life_potion"]["inputs"])
        for quotes in ((("actual-loot", 960),), (("actual-loot", 1280),), (("a", 640), ("b", 640))):
            with self.subTest(quotes=quotes):
                plan = self.greaterPlan(quotes)
                self.assertIsNotNone(plan)
                self.assertEqual(0, plan["portalMode"], "Prefer to preserve the collected entry scroll")
                self.assertEqual((("purchase", "life", 800),), plan["callbackActions"])
                self.assertEqual(20, plan["remaining"])
                self.assertEqual(720 + sum(dict(quotes)[identity] for identity in plan["loot"]), plan["expense"] + 20)
                actions = plan["callbackActions"] + plan["actions"]
                for action in ("purchase", "sale"):
                    identities = [identity for operation, identity, _price in actions if operation == action]
                    self.assertEqual(len(identities), len(set(identities)), "An original finite identity cannot repeat")
                self.assertNotIn("life", [identity for action, identity, _ in actions if action == "sale"])
                self.assertNotIn("small1", [identity for action, identity, _ in actions if action == "sale"])
                self.assertNotIn("small2", [identity for action, identity, _ in actions if action == "sale"])
                if any(identity == "small3" for _, identity, _ in actions):
                    self.assertIn(
                        ("sale", "small3", 320), actions, "A third lesser cannot remain for predicate removal"
                    )

    def testGreaterLifePlanIncludesRequiredExtraReagentSalesOrRefusesBeforeAnyTransaction(self):
        plan = self.greaterPlan((("actual-loot", 960),), required_sales=(("already-earned-lesser", 320),))
        self.assertIsNotNone(plan)
        self.assertIn("already-earned-lesser", plan["loot"])
        for quotes in ((), (("too-small", 640),), (("too-large", 5000),)):
            with self.subTest(quotes=quotes):
                self.assertIsNone(self.greaterPlan(quotes))
        for quotes, required in (
            ((("life", 1280),), ()),
            ((("same", 640), ("same", 640)), ()),
            ((("a", True),), ()),
            ((("a", 5001),), ()),
            ((("a", 1280),), (("a", 320),)),
            ((("a", 1280),), (("extra", 0),)),
            (tuple((str(index), 160) for index in range(129)), ()),
        ):
            with self.subTest(quotes=quotes, required=required), self.assertRaises(ValueError):
                self.greaterPlan(quotes, required_sales=required)

    def greaterDriver(self, *, ingredient_lost=False, extra_lesser=False, **kwargs):
        driver, state, owned, stock, transactions, order = self.nourDriver(portal_refusal=True, **kwargs)
        fixture = state["fixture"]
        native_player, game, types = fixture.player, fixture.game, fixture.types
        removed, attempts = [], []

        def item(identity):
            return SimpleNamespace(getName=lambda: identity, getTypeId=lambda: types[identity])

        def addItem(value):
            if isinstance(value, str):
                identity = value
                types[identity] = value
            else:
                identity = value.getName()
            owned.add(identity)

        def removeItem(predicate, quest):
            self.assertIs(quest, True)
            match = next(identity for identity in sorted(owned) if predicate(item(identity)))
            owned.remove(match)
            removed.append(match)

        native_player.addItem = addItem
        native_player.removeItem = removeItem
        native_player.setNumericProperty = lambda key, value: (
            state.update(gold=value) if key == "gold" else self.fail(key)
        )
        native_player.hasItem = lambda predicate: any(predicate(item(identity)) for identity in owned)

        def createObject(game_instance, type_id):
            self.assertIs(game_instance, game)
            self.assertEqual("LifePotion", type_id)
            identity = "crafted-life"
            self.assertNotIn(identity, types, "The guaranteed recipe must run once")
            types[identity] = type_id
            return item(identity)

        game.getObjectHandler = lambda: SimpleNamespace(createObject=createObject)
        quest_system = SimpleNamespace(
            mark_relic_obtained=Mock(),
            mark_relic_returned=Mock(),
            is_cave_purged=lambda: False,
        )
        source = "res/maps/nouraajd/script.py"
        obtain = authoredFunction(
            source, "trigger", class_id="CatacombsTrigger", _quest_system_from=lambda obj: quest_system
        )
        returned = authoredFunction(
            source, "return_relic", class_id="BerenDialog", _quest_system_from=lambda obj: quest_system
        )

        def relic(driver):
            order.append("actual-catacombs-relic")
            obtain(
                SimpleNamespace(getGame=lambda: game), SimpleNamespace(getStringProperty=lambda key: "relic"), object()
            )
            self.assertIn("holyRelic", owned)
            self.assertNotIn("CAN_BREW_GREATER_POTIONS", state["flags"])
            if extra_lesser:
                # An observed loot variation must be sold once before buying the exact original pair.
                types["earned-lesser"] = "LesserLifePotion"
                owned.add("earned-lesser")

        def handIn(driver):
            order.append("actual-relic-return")
            returned(
                SimpleNamespace(
                    getGame=lambda: game, can_return_relic=lambda: "holyRelic" in owned, _ensure_quest=Mock()
                )
            )
            self.assertNotIn("holyRelic", owned)
            self.assertTrue(state["flags"]["CAN_BREW_GREATER_POTIONS"])

        def station(driver, name, *, navigate=None):
            self.assertEqual("alchemyTable1", name)
            state.setdefault("stationNavigators", []).append(navigate)
            if ingredient_lost and "crafted-life" in owned:
                owned.remove("life")
            return tuple(
                {
                    "id": recipe_id,
                    "enabled": (
                        all(native_player.countItems(entry["item"]) >= entry["count"] for entry in recipe["inputs"])
                        and state["gold"] >= recipe["gold"]
                        and (not recipe.get("unlockFlag") or state["flags"].get(recipe["unlockFlag"], False))
                    ),
                }
                for recipe_id, recipe in crafting.recipeDefinitions().items()
                if recipe["station"] == "alchemyTable"
            )

        def engine(name, game_handle, station, recipe_id):
            self.assertEqual("craftRecipe", name)
            self.assertIn(recipe_id, {"brew_life_potion", "blend_greater_life_potion"})
            recipe = crafting.recipeDefinitions()[recipe_id]
            namespace = fixture.namespace
            actual = {
                "inputs": namespace["_normalize_item_entries"](recipe["inputs"]),
                "outputs": namespace["_normalize_item_entries"]([recipe["output"]]),
                "gold": recipe["gold"],
                "success_chance": recipe.get("successChance", 100),
            }
            result = namespace["apply_recipe"](game, native_player, actual)
            attempts.append((recipe_id, result))
            return result

        driver.engine = Mock(side_effect=engine)
        navigator = Mock(side_effect=lambda name, adjacent=False: driver.navigateTo(name))
        state["recipeNavigator"] = navigator
        state["recipeNavigatorFactory"] = Mock(return_value=navigator)
        for target, name, function in (
            (routes, "relic", relic),
            (routes, "handInRelic", handIn),
            (crafting, "openStation", station),
            (routes, "nourRecipeNavigator", state["recipeNavigatorFactory"]),
        ):
            patcher = patch.object(target, name, function)
            patcher.start()
            self.addCleanup(patcher.stop)
        return driver, state, owned, stock, transactions, order, removed, attempts

    def testGreaterLifeMarketAndBothCraftAttemptsUseTheSameGuardedNativeCorridor(self):
        driver, state, _owned, _stock, _transactions, _order, _removed, attempts = self.greaterDriver()
        routes.nourGreaterLifeGoldRefusal(driver)
        state["recipeNavigatorFactory"].assert_called_once_with(driver)
        state["recipeNavigator"].assert_called_once_with("market1")
        self.assertEqual([state["recipeNavigator"], state["recipeNavigator"]], state["stationNavigators"])
        self.assertEqual(2, len(attempts))

    def corridorDriver(self, *, origin=(44, 105, 0), pritz=(45, 107, 0), controller="CGroundController", blocked=()):
        player = {"__handle__": "player", "__type__": "CPlayer"}
        actor = {"__handle__": "actual-pritz", "__type__": "CCreature"}
        ground = {"__handle__": "actual-controller", "__type__": controller}
        positions = {"player": origin, "actual-pritz": pritz, "market1": (106, 111, 0), "alchemyTable1": (105, 110, 0)}
        steps, calls = [], []
        _door, courtyard = routes.courtyardExitDistances()
        cells = set(routes.authoredRoadCells("nouraajd")) | set(courtyard) | {(105, 110, 0)}

        def call(handle, method, *args):
            calls.append((handle["__handle__"], method))
            if method == "getObjects":
                return [player, actor]
            if method == "isAlive":
                return True
            if method == "isNpc":
                return False
            if method == "getTypeId":
                return "Pritz"
            if method == "getObjectProperty" and args == ("controller",):
                return ground
            if method == "getStringProperty" and args == ("tileType",):
                return "grass"
            if method == "getName":
                return "actual-pritz"
            self.fail((handle, method, args))

        def step(point):
            self.assertEqual(1, sum(abs(a - b) for a, b in zip(positions["player"], point)))
            self.assertIn(point, cells)
            self.assertNotIn(point, blocked)
            positions["player"] = point
            steps.append(point)

        driver = SimpleNamespace(
            test=self,
            map_name="nouraajd",
            player=player,
            game_map={"__handle__": "map"},
            string=lambda key: "good_end" if key == "quest_state_victor" else 'octobogzHunt.v1:{"stage":"dormant"}',
            object=lambda name, required=True: None if name in {"cave1", "catacombs"} else {"__handle__": name},
            call=call,
            coords=lambda handle=None: positions[(handle or player)["__handle__"]],
            canStep=lambda point: point in cells and point not in blocked,
            step=step,
            navigateTo=Mock(side_effect=AssertionError("The shortest grass approach would consume a protected potion")),
        )
        return driver, positions, steps, calls

    def testRecipeCorridorUsesNativeRoadStepsAndRoadStagingForBothStationVisits(self):
        driver, positions, steps, _calls = self.corridorDriver()
        navigate = routes.nourRecipeNavigator(driver)
        navigate("market1", adjacent=True)
        self.assertEqual((105, 111, 0), positions["player"])
        navigate("market1")
        self.assertEqual((106, 111, 0), positions["player"])
        self.assertEqual(76, len(steps))
        roads = routes.authoredRoadCells("nouraajd")
        self.assertTrue(set(steps) <= roads)
        self.assertNotIn((45, 107, 0), steps, "The actual failed native grass collision must be avoided")
        for _attempt in range(2):
            navigate("alchemyTable1", adjacent=True)
            self.assertEqual((105, 111, 0), positions["player"])
            navigate("alchemyTable1")
            self.assertEqual((105, 110, 0), positions["player"])
        self.assertEqual([(105, 111, 0), (105, 110, 0), (105, 111, 0), (105, 110, 0)], steps[-4:])
        self.assertNotIn((106, 110, 0), steps, "Repeat entry cannot use the generic grass-side revisit")
        driver.navigateTo.assert_not_called()

    def testStationEntryReservesTheNextExitTickAndExitRechecksItsActualGrassOrigin(self):
        for origin, pritz, adjacent in (
            ((105, 111, 0), (105, 108, 0), False),
            ((105, 110, 0), (105, 109, 0), True),
        ):
            with self.subTest(origin=origin, pritz=pritz):
                driver, _positions, steps, _calls = self.corridorDriver(origin=origin, pritz=pritz)
                navigate = routes.nourRecipeNavigator(driver)
                with self.assertRaisesRegex(AssertionError, "safe immediate native entry/exit"):
                    navigate("alchemyTable1", adjacent=adjacent)
                self.assertEqual([], steps, "Unsafe contact cannot be retried, waited out or credited")

    def testRecipeCorridorRejectsUnknownControllersRoadOccupantsAndActualBlockedCells(self):
        for kwargs, message in (
            ({"controller": "CTargetController"}, "chasing hostile"),
            ({"pritz": (44, 107, 0)}, "already on a road"),
        ):
            with self.subTest(kwargs=kwargs):
                driver, _positions, steps, _calls = self.corridorDriver(**kwargs)
                with self.assertRaisesRegex(AssertionError, message):
                    routes.nourRecipeNavigator(driver)
                self.assertEqual([], steps)
        driver, _positions, steps, _calls = self.corridorDriver(blocked={(44, 108, 0)})
        navigate = routes.nourRecipeNavigator(driver)
        with self.assertRaisesRegex(AssertionError, "live authored recipe corridor is blocked"):
            navigate("market1", adjacent=True)
        self.assertEqual([(44, 106, 0), (44, 107, 0)], steps)
        self.assertNotIn((45, 107, 0), steps, "A live wall cannot authorize a fallback through grass")

    def testAuthoredRoadCorridorHasNoCaveSpawnsAndTheDistantLairHasNoAmbientTurnCallback(self):
        from tests.narrative_walkthrough import authoredRegion

        positions, _tiles = authoredRegion("nouraajd")
        roads = routes.authoredRoadCells("nouraajd")
        configs = json.loads((ROOT / "res/maps/nouraajd/config.json").read_text())
        tiles = json.loads((ROOT / "res/config/tiles.json").read_text())
        self.assertEqual("road", tiles["RoadTile"]["properties"]["tileType"])
        self.assertEqual(75, len(routes.nourRecipeRoadPath((44, 106, 0), positions["market1"])))
        self.assertNotIn(positions["alchemyTable1"], roads)
        for name in ("cave1", "catacombs"):
            monster = configs[name]["properties"]["monster"]["properties"]["controller"]
            self.assertEqual("CGroundController", monster["class"])
            self.assertIn(monster["properties"]["tileType"], {"ground", "grass"})
            x, y, z = positions[name]
            spawn_cells = {(x + dx, y + dy, z) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
            self.assertFalse(spawn_cells & roads, "Neither timed nor entrance clones may begin on the safe road")
        source = (ROOT / "src/core/CController.cpp").read_text()
        ground_source = source.split("CGroundController::control", 1)[1].split("CRangeController::CRangeController", 1)[
            0
        ]
        self.assertIn("getAdjacentCoords(creature->getCoords(), true)", ground_source)
        self.assertIn("type == self->getTileType() && map->canStep(c)", ground_source)
        mcp = ast.parse((ROOT / "mcp.py").read_text())
        allowed = ast.literal_eval(
            next(
                node.value
                for node in mcp.body
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "MCP_ALLOWED_HANDLE_METHODS"
                    for target in node.targets
                )
            )
        )
        self.assertTrue({"getObjectProperty", "getStringProperty"} <= allowed["CGameObject"])
        self.assertIn("controller, getController, setController", (ROOT / "src/object/CCreature.h").read_text())
        self.assertIn("tileType, getTileType, setTileType", (ROOT / "src/core/CController.h").read_text())
        plugin = ast.parse((ROOT / "res/plugins/octobogz_hunt.py").read_text())
        lair = next(node for node in ast.walk(plugin) if isinstance(node, ast.ClassDef) and node.name == "OctobogzLair")
        self.assertNotIn("onTurn", {node.name for node in lair.body if isinstance(node, ast.FunctionDef)})
        spawn_cells = ast.literal_eval(
            next(
                node.value
                for node in plugin.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "SPAWN_CELLS" for target in node.targets)
            )
        )
        self.assertTrue(
            all(sum(abs(a - b) for a, b in zip(cell, positions["alchemyTable1"])) > 1 for cell in spawn_cells)
        )

    def testGreaterLifeRouteExecutesEarnedRelicUnlockGuaranteedBrewAndGoldRefusalForEveryClass(self):
        for class_id in routes.CASES[0].classes:
            with self.subTest(class_id=class_id):
                driver, state, owned, stock, transactions, order, removed, attempts = self.greaterDriver()
                driver.class_id = class_id
                routes.nourGreaterLifeGoldRefusal(driver)
                self.assertLess(order.index("actual-letter-unlock"), order.index("actual-catacombs-relic"))
                self.assertLess(order.index("actual-relic-return"), order.index("actual-Victor-callback"))
                self.assertTrue(state["victorSettled"])
                self.assertEqual(20, state["gold"])
                self.assertTrue({"starter", "letter", "skull", "portal", "life", "crafted-life"} <= owned)
                self.assertEqual(["holyRelic", "small1", "small2"], removed)
                self.assertEqual(
                    [
                        ("brew_life_potion", {"ok": True, "reason": ""}),
                        ("blend_greater_life_potion", {"ok": False, "reason": "missing:gold"}),
                    ],
                    attempts,
                )
                self.assertEqual(2, driver.engine.call_count)
                self.assertTrue(driver.recoveryEnabled)
                state["fixture"].namespace["randint"].assert_not_called()
                sales = Counter(identity for action, identity, *_ in transactions if action == "sale")
                self.assertTrue(all(count == 1 for count in sales.values()))
                for protected in ("starter", "letter", "skull", "life", "small1", "small2"):
                    self.assertNotIn(protected, sales)

    def testGreaterLifeRouteSellsOnlyObservedExtraLesserOnceToPreserveExactOriginalRecipeInputs(self):
        driver, state, owned, stock, transactions, _order, removed, attempts = self.greaterDriver(extra_lesser=True)
        routes.nourGreaterLifeGoldRefusal(driver)
        self.assertIn("earned-lesser", stock | {identity for action, identity, *_ in transactions if action == "sale"})
        self.assertEqual(
            1, sum(action == "sale" and identity == "earned-lesser" for action, identity, *_ in transactions)
        )
        self.assertNotIn("earned-lesser", owned)
        self.assertEqual(["holyRelic", "small1", "small2"], removed)
        self.assertEqual(2, len(attempts))
        state["fixture"].namespace["randint"].assert_not_called()

    def testGreaterLifeMarketReturnReportsTheActualLostProtectedIdentityWithoutProceeding(self):
        driver, state, owned, _stock, _transactions, _order, _removed, attempts = self.greaterDriver()
        original_call, original_navigate = driver.call, driver.navigateTo.side_effect

        def call(handle, method, *args):
            if method == "getObjects":
                return []
            if method in {"getHpMax", "getManaMax"}:
                return 70
            return original_call(handle, method, *args)

        def navigate(name):
            original_navigate(name)
            owned.remove("portal")

        driver.call = call
        driver.navigateTo.side_effect = navigate
        with self.assertRaisesRegex(AssertionError, "greater-life.after-market-entry") as caught:
            routes.nourGreaterLifeGoldRefusal(driver)
        message = str(caught.exception)
        for actual in ("portal", "TownPortalScroll", "nouraajd", "130", "missing", "currentInventory", "hp"):
            self.assertIn(actual, message)
        self.assertEqual([], attempts, "An observed inventory loss must stop before either recipe attempt")
        driver.engine.assert_not_called()
        self.assertTrue(driver.recoveryEnabled)

    def testRecipePreservationDiagnosticsAreLazyBoundedAndReadOnly(self):
        player, game_map = {"__handle__": "player"}, {"__handle__": "map"}
        calls = []
        owned = [{"__handle__": "owned-" + str(index)} for index in range(15)]
        actors = [{"__handle__": "actor-" + str(index), "__type__": "CCreature"} for index in range(11)]

        def call(handle, method, *args):
            calls.append((handle["__handle__"], method))
            if method == "getItems":
                return owned
            if method == "getObjects":
                return actors
            if method == "getName":
                return "actual-" + handle["__handle__"]
            if method == "getTypeId":
                return "LesserManaPotion" if handle["__handle__"].startswith("lost-") else "Pritz"
            if method == "isAlive":
                return True
            if method in {"getHp", "getHpMax", "getMana", "getManaMax", "getTurn"}:
                return 12
            self.fail((handle, method, args))

        driver = SimpleNamespace(
            test=self,
            player=player,
            game_map=game_map,
            map_name="nouraajd",
            call=call,
            coords=lambda handle=None: (130, 110, 0),
            gold=lambda: 20,
            record=Mock(),
        )
        routes.assertRecipeInventoryPreserved(driver, {"owned-0"}, "before-movement")
        self.assertEqual([("player", "getItems")], calls, "Passing checks must add no diagnostic RPCs")
        calls.clear()
        expected = {"lost-" + str(index) for index in range(15)}
        with self.assertRaises(AssertionError):
            routes.assertRecipeInventoryPreserved(driver, expected, "after-movement")
        diagnostic = driver.record.call_args.args[0]["recipeInventoryFailure"]
        self.assertEqual("after-movement", diagnostic["stage"])
        self.assertEqual(15, diagnostic["missingCount"])
        self.assertEqual((12, 3), (len(diagnostic["missing"]), diagnostic["missingOmitted"]))
        self.assertEqual((12, 3), (len(diagnostic["currentInventory"]), diagnostic["inventoryOmitted"]))
        self.assertEqual((8, 3), (len(diagnostic["remainingActors"]), diagnostic["actorsOmitted"]))
        self.assertTrue(
            all(
                method
                in {
                    "getItems",
                    "getObjects",
                    "getName",
                    "getTypeId",
                    "isAlive",
                    "getHp",
                    "getHpMax",
                    "getMana",
                    "getManaMax",
                    "getTurn",
                }
                for _, method in calls
            )
        )
        self.assertEqual(12, diagnostic["hp"])
        self.assertEqual(20, diagnostic["gold"])

    def testGreaterLifeRouteRejectsUnsatisfiableFundingAndLostInputsWithoutFalseBranchCredit(self):
        for kwargs, expected_attempts in (
            ({"loot_value": 5000}, 0),
            ({"callback_invalid": True}, 0),
            ({"ingredient_lost": True}, 1),
        ):
            with self.subTest(kwargs=kwargs):
                driver, state, owned, _stock, transactions, _order, _removed, attempts = self.greaterDriver(**kwargs)
                with self.assertRaises(AssertionError):
                    routes.nourGreaterLifeGoldRefusal(driver)
                self.assertEqual(expected_attempts, len(attempts))
                if expected_attempts == 0:
                    self.assertEqual([], transactions, "A failed precomputed plan cannot greedily sell then retry")
                    self.assertTrue({"starter", "letter", "skull", "portal", "earned"} <= owned)
                self.assertFalse(any(call.args[0].endswith("insufficientGold") for call in driver.check.call_args_list))
                self.assertTrue(driver.recoveryEnabled)

    def testGreaterLifeCaseRegistersAllFiveClassesAndItsPreviouslyPendingGoldOutcome(self):
        from tests import gameplay_branch_catalog as catalog

        case = next(value for value in routes.CASES if value.id == "nouraajd_recipe_gold_greater_life")
        self.assertEqual(("Warrior", "Sorcerer", "Assasin", "Inquisitor", "Wayfarer"), case.classes)
        self.assertEqual(("nouraajd",), case.maps)
        self.assertEqual(("humanRace", "fallOfNouraajd"), (case.race, case.campaign))
        self.assertIs(case.run, routes.nourGreaterLifeGoldRefusal)
        branch = "nouraajd.crafting.blend_greater_life_potion.insufficientGold"
        self.assertIn(branch, case.branches)
        self.assertIn("nouraajd.crafting.brew_life_potion.success", case.branches)
        self.assertIn("res/config/crafting.json", case.sources)
        self.assertIn("src/object/CMarket.cpp", case.sources)
        current = (len(catalog.getCases()), len(catalog.selectedTestNames()), len(catalog.pendingGameplayObligations()))
        self.assertNotIn(branch, catalog.pendingGameplayObligations())
        with patch.object(routes, "CASES", tuple(value for value in routes.CASES if value.id != case.id)):
            previous = (
                len(catalog.getCases()),
                len(catalog.selectedTestNames()),
                len(catalog.pendingGameplayObligations()),
            )
            self.assertIn(branch, catalog.pendingGameplayObligations())
        self.assertEqual((previous[0] + 1, previous[1] + 5, previous[2] - 1), current)

    def portalPlan(self, loot_quotes):
        return routes.finitePortalGoldPlan(
            720,
            loot_quotes,
            1600,
            200,
            (("a", 400, 320), ("b", 400, 320), ("c", 400, 320), ("d", 400, 320)),
            ("portal", 200, 160),
            ("life", 800, 640),
        )

    def testFinitePlannerUsesActualQuotesForDifferentEarnedLootWithoutRepeatingAnIdentity(self):
        config = json.loads((ROOT / "res/maps/nouraajd/config.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [
                "DaggerOfVileHeart",
                "LesserLifePotion",
                "LesserLifePotion",
                "LesserLifePotion",
                "LesserManaPotion",
                "Scroll",
            ],
            [entry["ref"] for entry in config["exampleMarket"]["properties"]["items"]],
        )
        self.assertEqual(
            ["LifePotion", "ManaPotion"], [entry["ref"] for entry in config["victorMarket"]["properties"]["items"]]
        )
        weapons = json.loads((ROOT / "res/config/weapons.json").read_text(encoding="utf-8"))
        self.assertEqual(3, weapons["LongSword"]["properties"]["power"])
        for quotes in ((("actual-loot", 1280),), (("actual-loot", 2560),), (("loot-a", 640), ("loot-b", 640))):
            with self.subTest(quotes=quotes):
                plan = self.portalPlan(quotes)
                self.assertIsNotNone(plan)
                self.assertEqual(0, plan["remaining"])
                self.assertEqual(len(plan["loot"]), len(set(plan["loot"])))
                sales = [identity for action, identity, _price in plan["actions"] if action == "sale"]
                purchases = [identity for action, identity, _price in plan["actions"] if action == "purchase"]
                self.assertEqual(len(sales), len(set(sales)))
                self.assertEqual(len(purchases), len(set(purchases)))
                self.assertEqual(720 + sum(dict(quotes)[identity] for identity in plan["loot"]), plan["expense"])
        self.assertEqual(0, self.portalPlan((("actual-loot", 1280),))["lifeMode"])
        self.assertNotEqual(0, self.portalPlan((("actual-loot", 2560),))["lifeMode"])

    def testFinitePlannerRejectsUnavailableFundingAndMalformedOrDuplicateQuotesBeforeSales(self):
        for quotes in ((), (("too-small", 640),), (("too-large", 5000),)):
            with self.subTest(quotes=quotes):
                self.assertIsNone(self.portalPlan(quotes))
        for quotes in ((("a", 1280),), (("same", 640), ("same", 640)), (("free", 0),), (("above-native-cap", 5001),)):
            with self.subTest(quotes=quotes), self.assertRaises(ValueError):
                self.portalPlan(quotes)
        with self.assertRaises(ValueError):
            self.portalPlan(tuple((str(index), 160) for index in range(129)))

    def testNourPortalGoldRefusalUsesTheLiveVictorMarketBeforeMovementAndPreservesExactInputs(self):
        driver, state, owned, stock, transactions, order = self.nourDriver(portal_refusal=True)
        routes.nourPortalGoldRefusal(driver)
        self.assertEqual(
            ["human-aid", "real-Rolf", "real-Gooby", "real-Victor-meeting", "real-Victor", "actual-Victor-callback"],
            order[:6],
        )
        self.assertEqual(("sale", "earned", 1280, 2000), transactions[0])
        self.assertEqual(("purchase", "mana", 1600, 400), transactions[1])
        self.assertEqual("actual-move:market1", order[6])
        self.assertIn("actual-letter-unlock", order)
        self.assertEqual(("purchase", "scroll", 200, 0), transactions[-1])
        self.assertEqual(0, state["gold"])
        self.assertTrue({"starter", "letter", "skull", "portal", "mana", "scroll"} <= owned)
        self.assertNotIn("earned", owned)
        sales = Counter(identity for action, identity, *_rest in transactions if action == "sale")
        self.assertTrue(all(count == 1 for count in sales.values()))
        self.assertNotIn("mana", sales)
        self.assertNotIn("scroll", sales)
        self.assertNotIn("starter", sales)
        self.assertNotIn("letter", sales)
        self.assertNotIn("skull", sales)
        driver.engine.assert_called_once()
        credit = next(call for call in driver.check.call_args_list if call.args[0].endswith("insufficientGold"))
        self.assertEqual({"ok": False, "reason": "missing:gold"}, credit.kwargs["result"])
        driver.saveAndReload.assert_called_once_with("portal-gold-victor-rescued")
        self.assertTrue(driver.recoveryEnabled)

    def testNourPortalGoldRefusalDoesNotSellAnythingWhenActualFundingOrCallbackIsUnavailable(self):
        for kwargs in ({"loot_value": 5000}, {"callback_invalid": True}):
            with self.subTest(kwargs=kwargs):
                driver, _state, owned, _stock, transactions, _order = self.nourDriver(portal_refusal=True, **kwargs)
                with self.assertRaises(AssertionError):
                    routes.nourPortalGoldRefusal(driver)
                self.assertEqual([], transactions)
                self.assertTrue({"starter", "letter", "portal", "earned"} <= owned)
                driver.engine.assert_not_called()
                self.assertFalse(any(call.args[0].endswith("insufficientGold") for call in driver.check.call_args_list))
                self.assertTrue(driver.recoveryEnabled)

    def testNourPortalGoldRefusalFailsIfNativeTravelConsumedTheManaInput(self):
        driver, _state, _owned, _stock, _transactions, _order = self.nourDriver(
            portal_refusal=True, ingredient_lost=True
        )
        with self.assertRaisesRegex(AssertionError, "every actual ingredient"):
            routes.nourPortalGoldRefusal(driver)
        driver.engine.assert_not_called()
        self.assertFalse(any(call.args[0].endswith("insufficientGold") for call in driver.check.call_args_list))
        self.assertTrue(driver.recoveryEnabled)

    def nourDriver(self, *, ingredient_lost=False, portal_refusal=False, loot_value=1280, callback_invalid=False):
        state = {"gold": 0, "flags": {}, "victor": "encounter_active", "callback": False, "coords": (105, 110, 0)}
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
        callback_market = {"__handle__": "callback-market"}
        callback_stock = {"life", "mana"}
        if portal_refusal:
            types.update(
                {
                    "life": "LifePotion",
                    "mana": "ManaPotion",
                    "scroll": "Scroll",
                    "lesserMana": "LesserManaPotion",
                    "dagger": "DaggerOfVileHeart",
                    "earned": "LongSword",
                    "sealedLetter": "letterToBeren",
                }
            )
            stock.update({"scroll", "lesserMana", "dagger"})
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

        def showTrade(actual_market):
            self.assertIs(actual_market, callback_market)
            state["callback"] = not callback_invalid
            order.append("actual-Victor-callback")

        gui = SimpleNamespace(showTrade=Mock(side_effect=showTrade) if portal_refusal else Mock(), notify=Mock())
        game = SimpleNamespace(getGuiHandler=lambda: gui)
        world = SimpleNamespace(
            getGame=lambda: game,
            getPlayer=lambda: native_player,
            getBoolProperty=lambda key: state["flags"].get(key, False),
        )
        game.getMap = lambda: world
        game.createObject = lambda identity: (
            callback_market if portal_refusal and identity == "victorMarket" else SimpleNamespace(getStates=lambda: [])
        )
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

        def price(identity, buying=False):
            if identity == "earned":
                return loot_value
            sell = {"portal": 200, "scroll": 200, "life": 800, "mana": 1600, "dagger": 100000}.get(identity, 400)
            return min(5000, sell * 80 // 100) if buying else sell

        def call(handle, method, *args):
            identity = handle["__handle__"]
            if method == "getItems":
                values = owned if handle == player else callback_stock if handle == callback_market else stock
                return [{"__handle__": key} for key in sorted(values)]
            if method == "getTypeId":
                if handle == callback_market:
                    return "victorMarket"
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
                return price(args[0]["__handle__"])
            if method == "getBuyCost":
                return price(args[0]["__handle__"], buying=True)
            if method == "getRequestedTradeMarket":
                self.assertTrue(state["callback"], "No stale callback market may fund the recipe")
                return callback_market
            if method == "getGuiHandler":
                return {"__handle__": "handler"}
            if method == "checkQuests":
                self.assertEqual("good_end", state["victor"], "Quest evaluation must follow the real rescue callback")
                state["victorSettled"] = True
                return None
            if method == "sellItem":
                selected = args[1]["__handle__"]
                target_stock = callback_stock if handle == callback_market else stock
                if selected not in target_stock:
                    return False
                amount = price(selected)
                self.assertGreaterEqual(state["gold"], amount)
                target_stock.remove(selected)
                owned.add(selected)
                state["gold"] -= amount
                transactions.append(("purchase", selected, amount, state["gold"]))
                return True
            if method == "buyItem":
                selected = args[1]["__handle__"]
                target_stock = callback_stock if handle == callback_market else stock
                if handle == callback_market:
                    self.assertTrue(state["callback"])
                self.assertIn(selected, owned)
                owned.remove(selected)
                target_stock.add(selected)
                amount = price(selected, buying=True)
                state["gold"] += amount
                transactions.append(("sale", selected, amount, state["gold"]))
                return None
            if method == "getBoolProperty":
                return state["flags"].get(args[0], False)
            if method == "getStringProperty":
                return "deescalated"
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
            self.assertEqual(
                ("craftRecipe", "craft_town_portal_scroll" if portal_refusal else "brew_life_potion"), (name, recipe_id)
            )
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
            if portal_refusal:
                owned.add("earned")

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
            self.assertEqual("scribeDesk1" if portal_refusal else "alchemyTable1", name)
            if ingredient_lost:
                owned.remove("mana" if portal_refusal else "small1")
            return ({"id": "craft_town_portal_scroll" if portal_refusal else "brew_life_potion", "enabled": False},)

        def navigate(name):
            state["callback"] = False
            state["coords"] = (130, 110, 0)
            order.append("actual-move:" + name)

        def actualLetter(driver):
            order.append("actual-letter-unlock")
            original_add = getattr(native_player, "addItem", None)
            original_has = getattr(native_player, "hasItem", None)
            issued = authoredFunction(
                source,
                "give_letter",
                class_id="TownHallDialog",
                _quest_system_from=lambda obj: SimpleNamespace(
                    needs_letter_delivery=lambda: True, give_letter=lambda player: True
                ),
            )
            native_player.hasItem = lambda predicate: any(
                predicate(SimpleNamespace(getName=lambda key=key: key)) for key in owned
            )
            native_player.addItem = lambda item_type: owned.add("sealedLetter")
            is_letter = lambda item: item.getName() == "sealedLetter"
            issued(SimpleNamespace(getGame=lambda: game, _is_letter_to_beren=is_letter))
            delivered = authoredFunction(
                source,
                "deliver_letter",
                class_id="BerenDialog",
                _quest_system_from=lambda obj: SimpleNamespace(
                    mark_letter_delivered=Mock(), is_relic_returned=lambda: True
                ),
            )
            original_remove = native_player.removeItem
            native_player.removeItem = lambda predicate, all_matching: owned.difference_update(
                key for key in tuple(owned) if predicate(SimpleNamespace(getName=lambda key=key: key))
            )
            delivered(
                SimpleNamespace(
                    getGame=lambda: game,
                    can_deliver_letter=lambda: "sealedLetter" in owned,
                    _is_letter_to_beren=is_letter,
                )
            )
            native_player.removeItem = original_remove
            native_player.addItem = original_add
            native_player.hasItem = original_has
            self.assertNotIn("sealedLetter", owned)
            self.assertTrue(state["flags"].get("CAN_CRAFT_SCROLLS"))

        def fight(name):
            self.assertEqual("cultLeaderQuest", name)
            order.append("real-Victor")
            rescue(SimpleNamespace(getGame=lambda: game), object(), object())

        def meet(driver, approach, direct):
            self.assertEqual(("deescalated", False), (approach, direct))
            order.append("real-Victor-meeting")

        def check(branch, condition, **evidence):
            self.assertTrue(condition, branch)

        driver = SimpleNamespace(
            test=self,
            player=player,
            game_map=game_map,
            game={"__handle__": "game"},
            map_name="nouraajd",
            race_id="humanRace",
            recoveryEnabled=True,
            call=call,
            gold=lambda: state["gold"],
            hunt=hunt,
            questNames=lambda completed=False: ["mainQuest"] + (["victorQuest"] if state.get("victorSettled") else []),
            coords=lambda: state["coords"],
            object=lambda name, required=True: {"__handle__": name},
            record=Mock(),
            sellAt=sellAt,
            engine=Mock(side_effect=engine),
            pump=Mock(),
            check=Mock(side_effect=check),
            navigateTo=Mock(side_effect=navigate),
            fight=fight,
            string=lambda key: state["victor"],
            flag=lambda key: state["flags"].get(key, False),
            condition=lambda dialog, condition: state["victor"] == "good_end",
            saveAndReload=Mock(),
            tradeRequests=lambda: [
                {"market": {"typeId": "victorMarket", "name": "callback-market"}, "map": "nouraajd"}
            ],
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
        if portal_refusal:
            for name, function in (
                ("meetVictor", meet),
                ("victorCountdownCheckpoint", Mock()),
                ("letter", actualLetter),
                (
                    "visitService",
                    lambda driver, name, event, *, navigate=None: (navigate or driver.navigateTo)(name),
                ),
            ):
                patcher = patch.object(routes, name, function)
                patcher.start()
                self.addCleanup(patcher.stop)
        state["fixture"] = SimpleNamespace(
            types=types, player=native_player, game=game, world=world, equipped=equipped, namespace=namespace
        )
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
        from tests import gameplay_branch_catalog as catalog

        portal = next(value for value in routes.CASES if value.id == "nouraajd_recipe_gold_scroll")
        self.assertEqual(case.classes, portal.classes)
        self.assertEqual("humanRace", portal.race)
        branch = "nouraajd.crafting.craft_town_portal_scroll.insufficientGold"
        self.assertIn(branch, portal.branches)
        current = (len(catalog.getCases()), len(catalog.selectedTestNames()), len(catalog.pendingGameplayObligations()))
        self.assertNotIn(branch, catalog.pendingGameplayObligations())
        with patch.object(routes, "CASES", tuple(value for value in routes.CASES if value.id != portal.id)):
            previous = (
                len(catalog.getCases()),
                len(catalog.selectedTestNames()),
                len(catalog.pendingGameplayObligations()),
            )
            self.assertIn(branch, catalog.pendingGameplayObligations())
        self.assertEqual((previous[0] + 1, previous[1] + 5, previous[2] - 1), current)
