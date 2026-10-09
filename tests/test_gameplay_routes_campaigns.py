# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure source-callback regressions for authored campaign route expectations."""

import ast
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import ANY, Mock, patch

from tests.castle_walkthrough import MAP_NAMES, TransitRoutes, authoredMap
from tests import gameplay_routes_campaigns as campaigns
from tests.gameplay_routes_campaigns import AUTHORED_UNREACHABLE, CASES, castleTownRest, ritualCountdownAfterTurn
from tests.gameplay_routes_maps import testMarket as authoredTestMarket
from tests.test_gameplay_route_dialogs import authoredFunction


class GameplayCampaignRouteTest(unittest.TestCase):
    def testCastleSupplyRepeatSnapshotsAfterCrossingAnUnclaimedAdjacentSupply(self):
        authored = authoredMap("castleHomecoming")[1]
        target_name = "castleHomecomingAlly1426"
        source = authored[target_name]["coords"]
        for adjacent_name in ("castleHomecomingAlly1430", "castleHomecomingSupportPikeman"):
            with self.subTest(adjacent=adjacent_name):
                neighbor = authored[adjacent_name]["coords"]
                self.assertEqual(1, sum(abs(a - b) for a, b in zip(source, neighbor)))
                state = {"gold": 0, "flags": set(), "position": source, "items": [], "entries": []}
                player = SimpleNamespace(
                    healProc=Mock(),
                    addItem=state["items"].append,
                    addGold=lambda amount: state.update(gold=state["gold"] + amount),
                )
                game_map, game = object(), object()

                def claim_once(owner, key):
                    if key in state["flags"]:
                        return False
                    state["flags"].add(key)
                    return True

                on_enter = authoredFunction(
                    "res/plugins/castle_campaign.py",
                    "onEnter",
                    class_id="CastleSupply",
                    canInteract=lambda actor, cause: cause is player,
                    claim_once=claim_once,
                    rewardSnapshot=Mock(return_value={}),
                    showRewardReceipt=Mock(),
                    showTownServices=Mock(),
                )
                actors = {
                    name: SimpleNamespace(
                        getMap=lambda: game_map,
                        getGame=lambda: game,
                        getName=lambda name=name: name,
                        getNumericProperty=lambda key, name=name: int(authored[name]["properties"][key]),
                        getStringProperty=lambda key: "",
                    )
                    for name in (target_name, adjacent_name)
                }

                def enter(coords):
                    state["position"] = coords
                    for name in (target_name, adjacent_name):
                        if authored[name]["coords"] == coords:
                            state["entries"].append(name)
                            on_enter(actors[name], SimpleNamespace(getCause=lambda: player))

                def step(coords):
                    self.assertEqual(1, sum(abs(a - b) for a, b in zip(state["position"], coords)))
                    enter(coords)

                def revisit(name):
                    enter(neighbor)
                    enter(source)

                driver = SimpleNamespace(
                    test=self,
                    map_name="castleHomecoming",
                    gold=lambda: state["gold"],
                    flag=lambda key: key in state["flags"],
                    coords=lambda: state["position"],
                    step=step,
                    revisit=revisit,
                    check=lambda branch, condition, **evidence: self.assertTrue(condition, branch),
                )
                with patch.object(campaigns, "castleNavigate", side_effect=lambda d, coords, *args: enter(coords)):
                    campaigns.castleSupply(
                        driver, target_name, authored, {source, neighbor}, TransitRoutes(), (100, 100, 0)
                    )
                self.assertEqual([target_name, adjacent_name, target_name], state["entries"])
                self.assertEqual(
                    sum(int(authored[name]["properties"]["campaign_rewardGold"]) for name in actors), state["gold"]
                )
                self.assertEqual(["LifePotion", "LifePotion"], state["items"])

    def testPrematureThroneEntryPreservesRewardsQuestsAndCampaign(self):
        path = Path(__file__).resolve().parents[1] / "res/maps/usurpergate/script.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        loader = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load")
        callback = next(
            node for node in loader.body if isinstance(node, ast.ClassDef) and node.name == "ObsidianThrone"
        )
        callback.decorator_list = []
        defaults = next(
            node
            for node in loader.body
            if isinstance(node, ast.FunctionDef) and node.name == "usurpergate_flags_default"
        )
        namespace = {
            "CEvent": object,
            "requirementMessage": Mock(),
            "claim_once": Mock(),
            "campaign": SimpleNamespace(complete_scenario=Mock()),
            "rewardSnapshot": Mock(),
            "showRewardReceipt": Mock(),
            "THRONE_GOLD_REWARD": 500,
        }
        exec(compile(ast.Module(body=[defaults, callback], type_ignores=[]), str(path), "exec"), namespace)
        for mercy in (False, True):
            with self.subTest(mercy=mercy):
                namespace["requirementMessage"].reset_mock()
                flags = {
                    "usurpergate_intro": True,
                    "usurper_defeated": False,
                    "throne_taken": False,
                    "throne_reward_claimed": False,
                    "mercy_route_applied": mercy,
                }
                initial = dict(flags)
                player = SimpleNamespace(isPlayer=lambda: True, addGold=Mock(), checkQuests=Mock())
                game = object()
                game_map = SimpleNamespace(
                    getBoolProperty=lambda name: flags.get(name, False),
                    setBoolProperty=lambda name, value: flags.update({name: value}),
                    getGame=lambda: game,
                    getPlayer=Mock(return_value=player),
                )
                throne = namespace["ObsidianThrone"]()
                throne.getMap = lambda: game_map
                throne.getGame = Mock(return_value=game)
                throne.onEnter(SimpleNamespace(getCause=lambda: player))
                self.assertEqual(initial, flags)
                namespace["requirementMessage"].assert_called_once_with(game, throne, ANY)
                player.addGold.assert_not_called()
                player.checkQuests.assert_not_called()
                game_map.getPlayer.assert_not_called()
                throne.getGame.assert_not_called()
                namespace["claim_once"].assert_not_called()
                namespace["rewardSnapshot"].assert_not_called()
                namespace["showRewardReceipt"].assert_not_called()
                namespace["campaign"].complete_scenario.assert_not_called()

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
