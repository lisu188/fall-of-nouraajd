# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Paid-rest sequencing through finite encounters, without native gameplay credit."""

from types import SimpleNamespace
import unittest

from tests.castle_walkthrough import TransitRoutes
from tests.gameplay_branch_driver import GameplayBranchDriver
from tests.gameplay_routes_campaigns import castleTownRest


class GameplayCastleTownRestTest(unittest.TestCase):
    def fixture(self, *, recovery_enabled=True, healed_by_native=(), fail_combat=False, defenders=3):
        town, supply, objective, reserved = (0, 0, 0), (1, 1, 0), (1, 0, 0), (4, 0, 0)
        objects = {
            "town": {
                "class": "CastleSupply",
                "coords": town,
                "properties": {"campaign_loyalTown": True, "campaign_isTown": True},
            },
            "reservedSupply": {"class": "CastleSupply", "coords": supply, "properties": {}},
            "uncapturedObjective": {"class": "CastleObjective", "coords": objective, "properties": {}},
        }
        for index, coords in enumerate(((2, 0, 0), (3, 1, 0), (4, 2, 0), (4, 3, 0))[:defenders]):
            objects["defender" + str(index)] = {"class": "CCreature", "coords": coords, "properties": {}}
        actors = {name: {"__handle__": name, "coords": value["coords"]} for name, value in objects.items()}
        required = tuple(name for name in objects if name.startswith("defender"))
        state = {
            "coords": (0, 1, 0),
            "hp": 100,
            "gold": 0,
            "exp": 0,
            "turns": 0,
            "living": set(required),
            "claimed": set(),
            "items": {"briefing-life-1", "briefing-life-2"},
            "events": [],
            "branches": [],
            "entered": [],
        }
        walkable = {(x, y, 0) for x in range(5) for y in range(4)}
        blockers = {supply, objective, reserved}

        def objectByName(name, required=True):
            if name.startswith("defender") and name not in state["living"]:
                if required:
                    self.fail(("Missing live fixture defender", name))
                return None
            return actors[name]

        def call(handle, method, *args):
            state["events"].append((method, args))
            if method == "getHp":
                return state["hp"]
            if method == "getHpMax":
                return 100
            if method == "getNumericProperty" and args == ("exp",):
                return state["exp"]
            if method == "isAlive":
                return handle["__handle__"] in state["living"]
            self.fail(("Unexpected fixture API", handle, method, args))

        def advance(target):
            self.assertEqual(1, sum(abs(a - b) for a, b in zip(state["coords"], target)))
            self.assertNotIn(
                target, blockers, "Rest preparation must preserve unclaimed income and the final objective"
            )
            if driver.recoveryEnabled and state["hp"] < 75 and state["items"]:
                state["items"].pop()
                state["hp"] = min(100, state["hp"] + 40)
                state["events"].append(("supplementalRecovery", target))
            state["turns"] += 1
            enemy = next((name for name in state["living"] if objects[name]["coords"] == target), None)
            if enemy is not None:
                state["events"].append(("nativeCombat", enemy, driver.recoveryEnabled))
                if fail_combat:
                    raise AssertionError("Unresolved native player combat")
                state["living"].remove(enemy)
                state["exp"] += 250
                state["hp"] = 100 if enemy in healed_by_native else 60
                # A native victory restores the attacker's origin without entering the defeated cell.
                return
            state["coords"] = target
            state["entered"].append(target)
            if target == town and "campaign_castleSupply_town" not in state["claimed"]:
                state["claimed"].add("campaign_castleSupply_town")
                state["gold"] += 25
                state["hp"] = 100
                state["items"].add("town-life")

        def navigateCoords(target):
            for _ in range(24):
                if state["coords"] == tuple(target):
                    return
                advance(tuple(target))
            self.fail("Native coordinate navigation stalled in fixture")

        def navigateTo(name):
            target = objects[name]["coords"]
            for _ in range(24):
                if objectByName(name, required=False) is None or state["coords"] == target:
                    return
                advance(target)
            self.fail("Native actor approach stalled in fixture")

        def restAtTown(name):
            self.assertEqual("town", name)
            self.assertEqual(town, state["coords"])
            self.assertFalse(driver.recoveryEnabled)
            accepted = state["hp"] < 100 and state["gold"] >= 10
            state["events"].append(("paidRest", accepted, state["gold"], state["hp"]))
            if accepted:
                state["gold"] -= 10
                state["hp"] = 100
            return accepted

        def check(branch, condition, **evidence):
            self.assertTrue(condition, (branch, evidence))
            state["branches"].append(branch)

        driver = SimpleNamespace(
            test=self,
            player={"__handle__": "player"},
            coords=lambda handle=None: handle["coords"] if handle else state["coords"],
            object=objectByName,
            call=call,
            flag=lambda name: name in state["claimed"],
            gold=lambda: state["gold"],
            recoveryEnabled=recovery_enabled,
            navigateCoords=navigateCoords,
            navigateTo=navigateTo,
            restAtTown=restAtTown,
            check=check,
            snapshot=lambda: dict(state),
            combats=0,
        )
        driver.fight = lambda name: GameplayBranchDriver.fight(driver, name)
        return driver, state, (objects, walkable, TransitRoutes(), reserved, {"defenderIds": required})

    def testPaidRestPreservesCombatInjuryAndStopsBeforeRedundantEmptyCellEntry(self):
        driver, state, args = self.fixture()
        castleTownRest(driver, *args)
        self.assertTrue(driver.recoveryEnabled)
        self.assertEqual(3, driver.combats)
        self.assertEqual(750, state["exp"])
        self.assertEqual(5, state["gold"])
        self.assertEqual(60, state["hp"])
        self.assertEqual({"briefing-life-1", "briefing-life-2", "town-life"}, state["items"])
        self.assertEqual(
            ["castle.town.rest", "castle.town.fullHealth"] * 2 + ["castle.town.insufficientGold"], state["branches"]
        )
        objects = args[0]
        self.assertFalse(
            {objects[name]["coords"] for name in objects if name.startswith("defender")} & set(state["entered"])
        )
        self.assertEqual({"campaign_castleSupply_town"}, state["claimed"])
        self.assertNotIn("supplementalRecovery", [event[0] for event in state["events"]])
        self.assertTrue(all(event[2] is False for event in state["events"] if event[0] == "nativeCombat"))

    def testNativeControllerHealingRemainsAuthoritativeAndDoesNotCreditAnInjury(self):
        driver, state, args = self.fixture(healed_by_native={"defender0"}, defenders=4)
        castleTownRest(driver, *args)
        self.assertEqual(4, driver.combats)
        self.assertEqual(5, state["gold"])
        self.assertEqual(2, sum(event[0] == "paidRest" and event[1] for event in state["events"]))
        self.assertEqual("castle.town.insufficientGold", state["branches"][-1])

    def testRecoverySettingIsRestoredWhenNativeCombatFailsWithoutRetryOrRestCredit(self):
        for initially_enabled in (False, True):
            with self.subTest(initially_enabled=initially_enabled):
                driver, state, args = self.fixture(recovery_enabled=initially_enabled, fail_combat=True)
                with self.assertRaisesRegex(AssertionError, "Unresolved native player combat"):
                    castleTownRest(driver, *args)
                self.assertIs(initially_enabled, driver.recoveryEnabled)
                self.assertEqual(1, sum(event[0] == "nativeCombat" for event in state["events"]))
                self.assertEqual([], state["branches"])
                self.assertEqual(0, driver.combats)

    def testFiniteEncountersThatAllEndFullyHealedRemainAnExplicitFailure(self):
        driver, state, args = self.fixture(healed_by_native={"defender0", "defender1", "defender2"})
        with self.assertRaisesRegex(AssertionError, "did not produce enough natural injuries"):
            castleTownRest(driver, *args)
        self.assertTrue(driver.recoveryEnabled)
        self.assertEqual(3, driver.combats)
        self.assertEqual(25, state["gold"])
        self.assertEqual([], state["branches"])


if __name__ == "__main__":
    unittest.main()
