# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Route-planning and assertion regressions; these doubles are not native MCP gameplay evidence."""

import ast
from collections import Counter
import json
from pathlib import Path
import unittest

from scripts.build_baldurs_gate_city import decodeCityData
from tests import gameplay_routes_baldurs_gate as routes
from tests.gameplay_branch_types import PLAYER_CLASSES

ROOT = Path(__file__).resolve().parents[1]


class BaldursGateCityRoutesTest(unittest.TestCase):
    def testAuthoredEastToNortheastPortalRunsWithExactNativePluginBuiltins(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        from tests.test_baldurs_gate_city_content import CityModel

        model = CityModel()
        self.assertNotIn("next", model.namespace["__builtins__"])
        link = next(
            row for row in routes.documents()["geometry"]["connections"] if row["object"] == "cityAr0800Boundary15"
        )
        self.assertEqual(("AR0800", "AR0300"), (link["from"], link["to"]))
        portal = model.createObject("BaldursGatePortal")
        portal.setStringProperty("name", link["object"])
        portal.properties.update(routes.documents()["config"][link["object"]]["properties"])
        portal.moveTo(*link["origin"])
        model.game_map.addObject(portal)
        model.player.moveTo(*link["origin"])
        model.game_map.setStringProperty("activeSimulationRegion", link["from"])
        model.clock.applySchedules = Mock()
        self.assertTrue(portal.usable())
        self.assertEqual(tuple(link["target"]), tuple(vars(portal.target()).values()))
        portal.onEnter(SimpleNamespace(getCause=lambda: model.player))
        self.assertEqual(tuple(link["target"]), tuple(vars(model.player.getCoords()).values()))
        self.assertEqual(link["to"], model.game_map.getStringProperty("activeSimulationRegion"))
        self.assertIn(link["to"], routes.decodeCityData(model.game_map.getStringProperty("plugin_cityVisitedAreas")))
        self.assertEqual("", model.player.getStringProperty("plugin_cityPortalGuard"))
        model.clock.applySchedules.assert_called_once_with()

    def testNativeTradePlanRejectsWrongGoldAndDuplicatedSoldInstances(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        for mutation in (None, "wrongGold", "duplicate"):
            with self.subTest(mutation=mutation):
                state = {
                    "gold": 1000,
                    "hero": {},
                    "shop": {},
                    "checks": [],
                    "saves": [],
                    "selections": [],
                }
                item = {
                    "name": "source-dart-instance",
                    "plugin_citySourceItem": "DART02",
                    "plugin_cityQuantity": 5,
                    "plugin_cityValue": 8,
                    "plugin_citySoldToStore": False,
                }
                driver = SimpleNamespace(
                    test=self,
                    player="hero",
                    gold=lambda: state["gold"],
                    object=lambda name: "clock" if name == "cityClock" else "shop",
                    saveAndReload=lambda label: state["saves"].append(label),
                    check=lambda branch, condition, **evidence: state["checks"].append(branch),
                )

                def call(owner, method, *args):
                    if method == "getItems":
                        return list(state[owner].values())
                    if method == "getName":
                        return owner["name"]
                    if method == "getNumericProperty":
                        return 10000 if owner == "hero" else owner.get(args[0], 0)
                    if method == "getBoolProperty":
                        return owner.get(args[0], False)
                    if method == "getStringProperty":
                        if owner == "clock":
                            return json.dumps({"STOBLACK": {"buy_markup": 50, "sell_markup": 200}})
                        return owner.get(args[0], "")
                    raise AssertionError((owner, method, args))

                def buy(_dialog, action):
                    self.assertEqual("buyStoreStoblack1", action)
                    state["gold"] -= 80
                    state["hero"][item["name"]] = item

                def choose(_dialog, action, *, selected_id):
                    self.assertEqual(item["name"], selected_id)
                    state["selections"].append(action)
                    if action == "sell":
                        state["shop"][selected_id] = state["hero"].pop(selected_id)
                        item["plugin_citySoldToStore"] = True
                        state["gold"] += 21 if mutation == "wrongGold" else 20
                    else:
                        self.assertEqual("buyBack", action)
                        state["hero"][selected_id] = state["shop"][selected_id]
                        if mutation != "duplicate":
                            del state["shop"][selected_id]
                        item["plugin_citySoldToStore"] = False
                        state["gold"] -= 80
                    return {"kind": "sourceModelOnly"}

                driver.call, driver.choose, driver.chooseUi = call, buy, choose
                with patch.object(routes, "start"), patch.object(
                    routes, "QuestRoute", return_value=SimpleNamespace(contact=Mock())
                ):
                    if mutation:
                        with self.assertRaises(AssertionError):
                            routes.tradeUi(driver)
                    else:
                        routes.tradeUi(driver)
                        self.assertEqual(["sell", "buyBack"], state["selections"])
                        self.assertEqual(3, len(state["saves"]))
                        self.assertEqual(
                            ["baldursGate.trade.nativeSell", "baldursGate.trade.nativeBuyBack"], state["checks"]
                        )

    def testInventorySelectionCallbacksHaveExplicitIsolatedNativePlans(self):
        cases = {case.id: case for case in routes.CASES if case.isolated_gui}
        self.assertEqual(
            {
                "baldurs-gate-native-inventory",
                "baldurs-gate-native-failed-theft",
                "baldurs-gate-native-trading",
                "baldurs-gate-native-companion-inventory",
            },
            set(cases),
        )
        covered = {branch for case in cases.values() for branch in case.branches}
        for callback in ("showInventory", "pickPocket", "sell", "buyBack", "inspectCompanion", "takeCompanionItem"):
            identity = "res/maps/baldursGate/script.py:BaldursGateDialog." + callback
            self.assertTrue(set(routes.SOURCE_BRANCHES[identity]) <= covered)
        tree = ast.parse((ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8"))
        for method in ("inventoryUi", "tradeUi", "companionInventoryUi"):
            source = ast.unparse(
                next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == method)
            )
            self.assertIn("d.chooseUi", source)
            self.assertIn("saveAndReload", source)
            self.assertIn("itemInstances", source)
        self.assertFalse(any(case.isolated_gui for case in routes.generatedQuestCases()))

    def testCityHasNaturalRoutePlansForAllFiveExistingHeroClasses(self):
        self.assertEqual(set(PLAYER_CLASSES), {hero for case in routes.CASES for hero in case.classes})
        self.assertTrue(all(case.group == "baldursGate" and case.maps == ("baldursGate",) for case in routes.CASES))
        identifiers = [case.id for case in routes.CASES]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertTrue(all(case.initial_reputation is None for case in routes.CASES))
        self.assertTrue(all(case.duration_seconds <= 1200 for case in routes.CASES))

    def testSourceDistrictsInteriorsSaveHistoryAndLockAlternativesRemainExplicit(self):
        declared = {branch for case in routes.CASES for branch in case.branches}
        self.assertTrue({"baldursGate.travel." + area for area in routes.WARDS} <= declared)
        self.assertTrue(
            {
                "baldursGate.history.helped",
                "baldursGate.history.killed",
                "baldursGate.interlude.earlyReturnRefused",
                "baldursGate.ownership.exactLootAndReload",
                "baldursGate.locks.picked",
                "baldursGate.locks.forced",
                "baldursGate.locks.refused",
                "baldursGate.travel.revisitAndReload",
            }
            <= declared
        )
        for identity, witnesses in routes.SOURCE_BRANCHES.items():
            path, method = identity.split(":")
            self.assertTrue((ROOT / path).is_file())
            self.assertTrue(set(witnesses) <= declared, method)

    def testDirectedSourceNavigationHonorsBlockedBranchesAndCannotInventReverseEdges(self):
        links = [
            {"object": "ab", "from": "A", "to": "B"},
            {"object": "ac", "from": "A", "to": "C"},
            {"object": "cb", "from": "C", "to": "B"},
        ]
        chosen = routes.pathBetween("A", "B", links, lambda edge: edge["object"] != "ab")
        self.assertEqual(["ac", "cb"], [edge["object"] for edge in chosen])
        self.assertEqual((), routes.pathBetween("A", "A", links, lambda edge: True))
        with self.assertRaisesRegex(AssertionError, "No currently permitted source route"):
            routes.pathBetween("B", "A", links, lambda edge: True)

    def testEveryUnresolvedSourceObligationRemainsPendingWithoutCatalogAcceptanceCredit(self):
        ledger = json.loads((ROOT / "tests/fixtures/baldurs_gate_city_ledger.json").read_text(encoding="utf-8"))
        expected = {entry["id"] for entry in ledger["entries"] if entry["implementation"]["status"] != "excluded"}
        actual = {entry["sourceId"] for entry in routes.PENDING_GAMEPLAY_OBLIGATIONS.values()}
        self.assertEqual(expected, actual)
        self.assertTrue(all("pending" in entry["reason"] for entry in routes.PENDING_GAMEPLAY_OBLIGATIONS.values()))
        self.assertFalse(ledger["acceptanceReady"])
        self.assertFalse(ledger["originalParityEstablished"])

    def testRouteCodeCannotSetProgressMoveActorsDirectlyOrAnswerNativeChoiceByFixture(self):
        tree = ast.parse((ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8"))
        forbidden = {
            "setBoolProperty",
            "setStringProperty",
            "setNumericProperty",
            "setObjectProperty",
            "moveTo",
            "setCoords",
            "addItem",
            "addGold",
            "addExp",
            "heal",
            "hurt",
            "removeObject",
            "addObject",
            "invokeAction",
            "chooseMock",
            "setFightController",
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, forbidden)
                if node.func.attr == "call" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    self.assertNotIn(node.args[1].value, forbidden)
        self.assertIn("d.startMap(MAP)", ast.unparse(tree))
        self.assertIn("d.navigateTo", ast.unparse(tree))
        self.assertIn("d.choose", ast.unparse(tree))

    def ownershipDriver(self, *, duplicate=False, wrong_gold=False):
        test = self

        class Driver:
            def __init__(self):
                self.test, self.player, self.game_map = test, "hero", "map"
                self.class_id = "Wayfarer"
                self.gold_value, self.exp = 1000, 10000
                self.items, self.looted = {}, False
                self.contents = [{"item": "RING10", "quantity": 2}, {"item": "MISC07", "charges": [17, 0, 0]}]
                self.actions = []

            def call(self, owner, method, *args):
                if method == "getStringProperty":
                    return json.dumps(self.contents) if owner == "chest" else self.items[owner][args[0]]
                if method == "getNumericProperty":
                    return self.exp if owner == "hero" else self.items[owner][args[0]]
                if method == "getBoolProperty":
                    return self.looted if args[0] == "looted" else False
                if method == "getItems":
                    return list(self.items)
                raise AssertionError((owner, method, args))

            def gold(self):
                return self.gold_value

            def object(self, name):
                return "chest"

            def navigateTo(self, name):
                self.actions.append(("navigate", name))

            def condition(self, *_args):
                return False

            def choose(self, dialog, action):
                self.actions.append(("choice", dialog, action))
                if action == "open" and (not self.looted or duplicate):
                    self.gold_value += 18 if wrong_gold else 17
                    self.items["ring" + str(len(self.items))] = {
                        "plugin_citySourceItem": "RING10",
                        "plugin_cityQuantity": 2,
                    }
                    self.looted, self.contents = True, []

        return Driver()

    def testOwnershipRouteRequiresNaturalContactExactDeltasAndAnInertRepeatedOpen(self):
        from unittest.mock import patch

        driver = self.ownershipDriver()
        with patch.object(routes, "travel") as travel:
            after = routes.openContainer(driver, "cityAr0800Container1")
        travel.assert_called_once_with(driver, "AR0800")
        self.assertEqual((1017, 10000, Counter({"RING10": 2})), after)
        self.assertEqual(("navigate", "cityAr0800Container1"), driver.actions[0])
        self.assertEqual(2, sum(action[0] == "choice" for action in driver.actions))
        for mutations in ({"duplicate": True}, {"wrong_gold": True}):
            with self.subTest(mutations=mutations), patch.object(routes, "travel"):
                with self.assertRaises(AssertionError):
                    routes.openContainer(self.ownershipDriver(**mutations), "cityAr0800Container1")

    def testEveryAuthoredQuestOutcomeHasAnIndividualSourceNamedNaturalRoutePlan(self):
        declared = {branch for case in routes.CASES for branch in case.branches}
        for quest in routes.documents()["quests"]:
            for outcome in quest["outcomes"]:
                branch = "baldursGate.quest." + quest["id"] + "." + outcome["id"]
                self.assertIn(branch, declared)
                action = "quest" + routes.upperFirst(quest["id"]) + routes.upperFirst(outcome["id"])
                callback = "res/maps/baldursGate/script.py:BaldursGateDialog." + action
                self.assertIn(branch, routes.SOURCE_BRANCHES[callback])

    def testOnlyActualStoreOwnersReceiveConcreteRowPlansAndOutsideClosureStoresRemainPending(self):
        from scripts.build_baldurs_gate_city_dialogs import storeDialogRows

        config = routes.documents()["config"]
        stores = decodeCityData(config["cityClock"]["properties"]["storeDefinitions"])
        owners = {
            entry["properties"]["sourceStore"]
            for entry in config.values()
            if entry.get("class") in routes.ACTOR_CLASSES and entry["properties"].get("sourceStore")
        }
        cases = routes.generatedStoreCases()
        self.assertEqual(owners, {case.id.removeprefix("baldurs-gate-store-") for case in cases})
        for case in cases:
            store_id = case.id.removeprefix("baldurs-gate-store-")
            expected = {
                "baldursGate.store." + store_id + "." + row["action"]
                for row in storeDialogRows(store_id, stores[store_id])
            }
            self.assertEqual(expected, set(case.branches))
        self.assertNotIn("TEM2601", owners, "Candlekeep's source store has no city owner")

    def testContainerQuantityExpectationsDistinguishActualAmmoStacksFromWandCharges(self):
        self.assertEqual(10, routes.sourceQuantity({"item": "BULL02", "charges": [10, 0, 0]}))
        self.assertEqual(1, routes.sourceQuantity({"item": "WAND05", "charges": [20, 20, 0]}))
        self.assertEqual(17, routes.sourceQuantity({"item": "MISC07", "charges": [17, 0, 0]}))
        self.assertEqual(3, routes.sourceQuantity({"item": "BULL02", "quantity": 3, "charges": [20, 0, 0]}))

    def testActiveQuestDependenciesDoNotCompleteThePoisonQuestBeforeItsSubquests(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        driver = SimpleNamespace(
            test=self,
            player="hero",
            number=lambda key: 10,
            call=lambda owner, method, *args: "stats" if method == "getStats" else 20,
        )
        planner = routes.QuestRoute(driver)
        planner.accept, planner.settle = Mock(), Mock()
        planner.conditions({"questStages": {"marekPoison": "active", "scarSevenSuns": "completed"}})
        planner.accept.assert_called_once_with("marekPoison")
        planner.settle.assert_called_once_with("scarSevenSuns")

    def testIdentificationRouteRequiresOneActualFlagChangeEvenWhenTheSourceServiceIsFree(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        def exercise(price, mutation):
            state = {"gold": 1000, "unknown": {"sourceStaff", "sourcePotion"}, "count": 0}

            def choose(dialog, action):
                self.assertEqual(("sourceOwnerDialog", "identifyStoreSource"), (dialog, action))
                if mutation != "noIdentification":
                    state["unknown"].remove("sourceStaff")
                    state["count"] += 1
                if mutation == "twoItems":
                    state["unknown"].clear()
                state["gold"] -= price + int(mutation == "wrongGold")

            driver = SimpleNamespace(
                test=self,
                object=lambda name: name,
                number=lambda key: state["count"] if key == "plugin_cityIdentifications" else 0,
                choose=choose,
                check=Mock(),
                saveAndReload=Mock(),
            )
            store = {"flags": 4, "identify_price": price}
            with (
                patch.object(routes, "start"),
                patch.object(routes, "QuestRoute"),
                patch.object(routes, "prepareIdentification"),
                patch.object(routes, "read", return_value={"SOURCE": store}),
                patch.object(routes, "resources", side_effect=lambda unused: (state["gold"], 10000, {"STAF25": 1})),
                patch.object(routes, "unknownPossessions", side_effect=lambda unused: state["unknown"].copy()),
            ):
                routes.storeRequests(driver, "SOURCE", "sourceOwner")
            driver.check.assert_called_once()

        for price in (0, 100):
            with self.subTest(price=price, mutation="none"):
                exercise(price, "none")
            for mutation in ("noIdentification", "twoItems", "wrongGold"):
                with self.subTest(price=price, mutation=mutation):
                    with self.assertRaises(AssertionError):
                        exercise(price, mutation)

    def testNarlenWarningWaitsForActualSourceOfficerAfterBeginningTheNightLookout(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        def exercise(spawn_fact):
            state = {"plugin_cityTicks": 0, "plugin_cityNarlenOfficerAt": 0}
            flags, choices = set(), []

            def waitTurns(limit, predicate):
                for _ in range(limit):
                    if predicate():
                        return
                    state["plugin_cityTicks"] += 1
                    if "plugin_cityFlag_narlenLookoutStarted" in flags:
                        if state["plugin_cityTicks"] >= state["plugin_cityNarlenOfficerAt"]:
                            flags.add("plugin_cityFlag_narlenOfficerDue")
                self.assertTrue(predicate())

            def choose(dialog, action):
                self.assertEqual("actualNarlenDialog", dialog)
                choices.append((action, state["plugin_cityTicks"]))
                if action == "beginNarlenLookout":
                    flags.add("plugin_cityFlag_narlenLookoutStarted")
                    state["plugin_cityNarlenOfficerAt"] = state["plugin_cityTicks"] + 20
                elif action == "warnNarlen":
                    self.assertIn("plugin_cityFlag_narlenOfficerDue", flags)
                    flags.add("plugin_cityFlag_narlenWarning")

            driver = SimpleNamespace(
                test=self,
                number=lambda key: state.get(key, 0),
                flag=lambda key: key in flags,
                condition=lambda dialog, method: method == "canBeginNarlenLookout",
                object=lambda name: name,
                call=lambda owner, method, *args: True if method == "isAlive" else spawn_fact,
                waitTurns=waitTurns,
                choose=choose,
            )
            planner = routes.QuestRoute(driver)
            planner.accept, planner.contact = Mock(), Mock()
            planner.actorName = lambda selectors: (
                "actualNarlen" if selectors[0]["creature"] == "NARLEN" else "actualOfficer"
            )
            with patch.object(routes, "travel") as travel:
                planner.narlenLookout(warn=True)
            travel.assert_called_once_with(driver, "AR0300")
            self.assertEqual([("beginNarlenLookout", 700), ("warnNarlen", 720)], choices)

        exercise("AR0300.BCS#spawn7")
        with self.assertRaises(AssertionError):
            exercise("inventedOfficer")

    def testCanonicalRelocatedActorMatchesLaterAreaAlternativeWithoutCreatingAnotherActor(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        properties = {"sourceArea": "AR0123", "sourceCreature": "TAMOKO", "label": "Tamoko"}
        driver = SimpleNamespace(
            test=self,
            object=lambda name, required=False: "actualTamoko",
            call=lambda actor, method, key: properties[key] if method == "getStringProperty" else False,
        )
        data = {
            "config": {"canonicalTamoko": {"class": "CCreature", "properties": dict(properties, sourceArea="AR0800")}},
            "quests": [],
        }
        with patch.object(routes, "documents", return_value=data):
            planner = routes.QuestRoute(driver)
            selected = planner.actorName(
                [{"creature": "TAMOKO", "area": "AR1100"}, {"creature": "TAMOKO", "area": "AR0123"}]
            )
        self.assertEqual("canonicalTamoko", selected)

    def testNativeCombatWitnessBeginsBeforeTravelAndRetainsAnOpponentKilledDuringArrival(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        events = []
        alive = [True]
        driver = SimpleNamespace(
            test=self,
            _combat_trace_seq=41,
            combats=0,
            object=lambda name, required=True: "foe" if alive[0] else None,
            assertNativeCombatOutcomes=lambda: events.append("trace"),
            call=lambda owner, method, *args: alive[0] if method == "isAlive" else False,
            navigateTo=lambda name: self.fail("A resolved arrival fight must not move toward the removed actor"),
            playerVictoryAgainst=lambda map_name, name, after_seq: {"seq": 42} if after_seq == 41 else None,
        )

        def arrive(*_args):
            events.append("travel")
            alive[0] = False

        with patch.object(routes, "travel", side_effect=arrive), patch.object(
            routes, "currentArea", return_value="AR0224"
        ), patch.object(
            routes, "documents", return_value={"config": {"opponent": {"properties": {"sourceArea": "AR0224"}}}}
        ):
            routes.nativeVictory(driver, "opponent")
        self.assertEqual(["trace", "travel", "trace"], events)
        self.assertEqual(1, driver.combats)

    def testHostileAlreadySharingHeroCellRequiresFreshNativeDepartureAndCombatEntry(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        alive, revisits = [True], []

        def revisit(name):
            revisits.append(name)
            alive[0] = False

        driver = SimpleNamespace(
            test=self,
            _combat_trace_seq=10,
            combats=0,
            object=lambda name, required=True: "foe" if alive[0] else None,
            assertNativeCombatOutcomes=lambda: None,
            call=lambda owner, method, *args: alive[0] if method == "isAlive" else False,
            coords=lambda owner=None: (3, 4, 0),
            revisit=revisit,
            navigateTo=lambda name: self.fail("An overlapping hostile cannot count as a completed ordinary visit"),
            playerVictoryAgainst=lambda *_args, **_kwargs: {"seq": 11},
        )
        with patch.object(routes, "travel"), patch.object(routes, "currentArea", return_value="AR0123"):
            routes.nativeVictory(driver, "opponent")
        self.assertEqual(["opponent"], revisits)
        self.assertEqual(1, driver.combats)


if __name__ == "__main__":
    unittest.main()
