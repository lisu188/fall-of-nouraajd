# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure source-callback regressions for authored campaign route expectations."""

import ast
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.castle_walkthrough import MAP_NAMES, TransitRoutes, authoredMap
from tests.gameplay_routes_campaigns import AUTHORED_UNREACHABLE, CASES, castleTownRest, ritualCountdownAfterTurn
from tests.gameplay_routes_maps import testMarket as authoredTestMarket


class GameplayCampaignRouteTest(unittest.TestCase):
    def testMapMarketRequiresBothAffordabilityOutcomesAndExactIdentityTransfer(self):
        player, market, shop, item, loot = (
            {"__handle__": name} for name in ("player", "market", "shop", "item", "loot")
        )
        state = {"gold": 0, "stock": [item], "owned": []}
        checks, sales = [], []

        def call(handle, method, *args):
            if method == "getObjectProperty":
                return market
            if method == "getItems":
                return list(state["owned"] if handle == player else state["stock"])
            if method == "getSellCost":
                return 10
            if method == "getBuyCost":
                return 25
            if method == "sellItem":
                if state["gold"] < 10:
                    return False
                self.assertIn(args[1], state["stock"])
                state["gold"] -= 10
                state["stock"].remove(args[1])
                state["owned"].append(args[1])
                return True
            self.fail(method)

        def sell(name, actual_item):
            self.assertEqual("market1", name)
            self.assertEqual(loot, actual_item)
            self.assertIn(loot, state["owned"])
            state["owned"].remove(loot)
            state["stock"].append(loot)
            state["gold"] += 25
            sales.append(actual_item)

        def check(branch, condition, **evidence):
            self.assertTrue(condition, branch)
            checks.append(branch)

        driver = SimpleNamespace(
            test=self,
            player=player,
            navigateTo=Mock(),
            object=lambda name: shop,
            call=call,
            gold=lambda: state["gold"],
            sellAt=sell,
            check=check,
        )
        authoredTestMarket(driver, False)
        self.assertEqual({"gold": 0, "stock": [item], "owned": []}, state)
        state["owned"].append(loot)
        authoredTestMarket(driver, True, {"loot"})
        self.assertEqual(["test.market.insufficientGold", "test.market.purchased"], checks)
        self.assertEqual([loot], sales)
        self.assertEqual({"gold": 15, "stock": [loot], "owned": [item]}, state)

    def testFinalCastleCapturePaysExactlyCaptureAndVictoryRewardsOnce(self):
        path = Path(__file__).resolve().parents[1] / "res/plugins/castle_campaign.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        callbacks = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in ("captureObjective", "finishMission")
        ]
        for map_name in MAP_NAMES:
            with self.subTest(map=map_name):
                _, objects, _, _, mission = authoredMap(map_name)
                target = mission["objectiveIds"][-1]
                target_properties = objects[target]["properties"]
                flags = {"captured:" + name: name != target for name in mission["objectiveIds"]}
                flags.update({"defeated:" + name: True for name in mission["defenderIds"]})
                state = {"gold": 137}
                campaign = SimpleNamespace(state=lambda game: None, complete_scenario=Mock())
                game_map = SimpleNamespace(
                    getBoolProperty=lambda name: flags.get(name, False),
                    setBoolProperty=lambda name, value: flags.update({name: value}),
                )
                game = SimpleNamespace(getMap=lambda: game_map)
                player = SimpleNamespace(
                    isAlive=lambda: True,
                    getGold=lambda: state["gold"],
                    addGold=lambda value: state.update(gold=state["gold"] + value),
                    setBoolProperty=Mock(),
                    addQuest=Mock(),
                    checkQuests=Mock(),
                )
                game_map.getPlayer, game_map.getGame = lambda: player, lambda: game
                marker = SimpleNamespace(
                    getMap=lambda: game_map,
                    getGame=lambda: game,
                    setStringProperty=Mock(),
                    getNumericProperty=lambda name: target_properties[name],
                    getStringProperty=lambda name: (
                        target if name == "campaign_objectiveId" else target_properties.get(name, "")
                    ),
                )
                namespace = {
                    "missionData": lambda game_map: mission,
                    "canInteract": lambda marker, player: True,
                    "objectiveFlag": lambda name: "captured:" + name,
                    "defeatedFlag": lambda name: "defeated:" + name,
                }
                game_module = SimpleNamespace(
                    campaign=campaign,
                    requirementMessage=Mock(),
                    rewardSnapshot=lambda player: {"gold": player.getGold()},
                    showRewardReceipt=Mock(),
                )
                exec(compile(ast.Module(body=callbacks, type_ignores=[]), str(path), "exec"), namespace)
                with patch.dict(sys.modules, {"game": game_module}):
                    self.assertTrue(namespace["captureObjective"](marker, player))
                    self.assertEqual(
                        137 + target_properties["campaign_rewardGold"] + mission["victoryGold"], state["gold"]
                    )
                    self.assertFalse(namespace["captureObjective"](marker, player))
                    self.assertEqual(
                        137 + target_properties["campaign_rewardGold"] + mission["victoryGold"], state["gold"]
                    )
                campaign.complete_scenario.assert_called_once()
                player.checkQuests.assert_called_once()

    def testTownRestUsesAnEarlierNaturalInjuryAndRetainsBlockedDefenders(self):
        positions = {"town": (0, 0, 0), "ally": (1, 0, 0), "harmless": (2, 0, 0), "optional": (9, 0, 0)}
        positions.update({"injures" + str(index): (index + 3, 0, 0) for index in range(6)})
        objects = {name: {"coords": coords, "properties": {}} for name, coords in positions.items()}
        for name in ("town", "ally", "optional"):
            objects[name]["class"] = "CastleSupply"
        objects["town"]["properties"] = {"campaign_loyalTown": True, "campaign_isTown": True}
        state = {"coords": (0, 0, 0), "hp": 20, "gold": 0, "townVisits": 0}
        claimed = set()
        checks, visits = [], []
        driver = SimpleNamespace(
            test=self,
            player={"__handle__": "player"},
            recoveryEnabled=True,
            coords=lambda: state["coords"],
            gold=lambda: state["gold"],
            flag=lambda name: name in claimed,
            object=lambda name, required=False: {"__handle__": name},
            call=lambda handle, method: state["hp"] if method == "getHp" else 20,
        )

        def navigate(driver, coords, walkable, portals, reserved):
            state["coords"] = coords
            visits.append(coords)
            if len(visits) > 1:
                self.assertNotIn(positions["optional"], walkable)
            if coords == positions["town"]:
                state["townVisits"] += 1
                if state["townVisits"] == 1:
                    state.update(hp=20, gold=25)
                    claimed.add("campaign_castleSupply_town")
            elif coords == positions["ally"]:
                state.update(hp=20, gold=state["gold"] + 25)
                claimed.add("campaign_castleSupply_ally")
            elif coords in {positions["injures" + str(index)] for index in range(6)}:
                state["hp"] = 12

        def rest(name):
            self.assertEqual("town", name)
            self.assertEqual(positions["town"], state["coords"])
            self.assertFalse(driver.recoveryEnabled)
            if state["hp"] == 20 or state["gold"] < 10:
                return False
            self.assertGreaterEqual(state["gold"], 10)
            state.update(hp=20, gold=state["gold"] - 10)
            return True

        def check(branch, condition, **evidence):
            self.assertTrue(condition, branch)
            checks.append(branch)

        driver.restAtTown, driver.check = rest, check
        with patch("tests.gameplay_routes_campaigns.castleNavigate", side_effect=navigate):
            castleTownRest(
                driver,
                objects,
                set(positions.values()),
                TransitRoutes(),
                (10, 0, 0),
                {"defenderIds": ["harmless", *("injures" + str(index) for index in range(6))]},
            )
        self.assertEqual(["castle.town.rest", "castle.town.fullHealth"] * 5 + ["castle.town.insufficientGold"], checks)
        self.assertEqual(0, state["gold"])
        self.assertEqual(12, state["hp"])
        self.assertTrue(driver.recoveryEnabled)
        self.assertEqual([positions["town"], positions["ally"], positions["harmless"]], visits[:3])
        self.assertEqual(positions["town"], visits[-1])
        self.assertNotIn(positions["optional"], visits)
        castle = next(case for case in CASES if case.id == "castle-all-authored-content")
        for name, blocker in AUTHORED_UNREACHABLE.items():
            self.assertIn("castle." + blocker["map"] + ".defender." + name, castle.branches)

    def testRitualCountdownUsesTurnBeforeNativeIncrement(self):
        path = Path(__file__).resolve().parents[1] / "res/maps/ritual/script.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        loader = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load")
        trigger = next(
            node for node in loader.body if isinstance(node, ast.ClassDef) and node.name == "RitualTurnTrigger"
        )
        trigger.decorator_list = []
        namespace = {"CTrigger": object, "spawn_wave": Mock()}
        exec(compile(ast.Module(body=[trigger], type_ignores=[]), str(path), "exec"), namespace)
        properties = {"ritual_countdown": 14, "ritual_last_tick_turn": 0, "ritual_last_wave_turn": 0}
        current = {"turn": 0}
        game_map = SimpleNamespace(
            getBoolProperty=lambda name: name == "ritual_active",
            getNumericProperty=lambda name: properties[name],
            setNumericProperty=lambda name, value: properties.update({name: value}),
            getTurn=lambda: current["turn"],
        )
        actor = SimpleNamespace(getMap=lambda: game_map)
        for turn in range(7):
            current["turn"] = turn
            before, last_tick = properties["ritual_countdown"], properties["ritual_last_tick_turn"]
            namespace["RitualTurnTrigger"]().trigger(actor, None)
            self.assertEqual(ritualCountdownAfterTurn(turn, before, last_tick), properties["ritual_countdown"])
        self.assertEqual(14, ritualCountdownAfterTurn(4, 14, 0))
        self.assertEqual(13, ritualCountdownAfterTurn(5, 14, 0))
        self.assertEqual(5, properties["ritual_last_tick_turn"])


if __name__ == "__main__":
    unittest.main()
