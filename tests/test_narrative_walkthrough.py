# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source-only survival regressions for the narrative MCP route driver."""

import json
import unittest

from tests.narrative_walkthrough import NarrativeWalkthrough


def mcpHandle(identity, class_name="CItem"):
    return {"__handle__": identity, "__type__": class_name, "repr": f"<{class_name} {identity}>"}


class RouteSession:
    def __init__(self, *, defeat_on=None, receipt="", victory_rollback=False, blocked=False):
        self.position = (0, 0, 0)
        self.hp = 10
        self.hpMax = 10
        self.mana = 4
        self.gold = 20
        self.experience = 100
        self.level = 1
        self.quests = ["active-quest-two", "active-quest-one"]
        self.completedQuests = ["completed-quest-two", "completed-quest-one"]
        self.receipt = receipt
        self.defeatOn = defeat_on
        self.victoryRollback = victory_rollback
        self.blocked = blocked
        self.pending = None
        self.defeated = False
        self.moves = self.turns = 0
        self.nativeTurn = 41
        self.calls = []

    def engineCall(self, name, args):
        if name == "event_loop.instance":
            return "loop"
        if name == "jsonify":
            if args == ["player"]:
                properties = {
                    "posx": self.position[0],
                    "posy": self.position[1],
                    "posz": self.position[2],
                    "hp": self.hp,
                    "mana": self.mana,
                    "uiDefeatReceipt": self.receipt,
                }
            elif args == ["leader"]:
                properties = {"posx": 1, "posy": 0, "posz": 0, "hp": 9, "mana": 3}
            elif args == ["spawn"]:
                properties = {"posx": 1, "posy": 0, "posz": 0}
            else:
                raise AssertionError((name, args))
            return json.dumps({"properties": properties})
        raise AssertionError((name, args))

    def handleCall(self, handle, method, args):
        self.calls.append((handle, method, args))
        if handle == "player":
            if method == "isAlive":
                return self.hp > 0
            if method == "getStringProperty" and args == ["uiDefeatReceipt"]:
                return self.receipt
            if method == "moveTo":
                self.moves += 1
                self.position = tuple(args)
                self.pending = "movement"
                return None
            if method in ("getHp", "getHpMax", "getMana", "getManaMax"):
                return {"getHp": self.hp, "getHpMax": self.hpMax, "getMana": self.mana, "getManaMax": 8}[method]
            if method == "getGold":
                return self.gold
            if method == "getTypeId":
                return "Warrior"
            if method == "getLevel":
                return self.level
            if method == "getNumericProperty" and args == ["exp"]:
                return self.experience
            if method in ("getQuests", "getCompletedQuests"):
                return [
                    mcpHandle(identity, "CQuest")
                    for identity in (self.quests if method == "getQuests" else self.completedQuests)
                ]
            if method == "countItems" and args[0] in ("LifePotion", "ManaPotion"):
                return 6
        if handle == "map":
            if method == "move":
                self.turns += 1
                self.nativeTurn += 1
                self.pending = "turn"
                return None
            if method == "getTurn":
                return self.nativeTurn
            if method == "getStringProperty" and args == ["mapName"]:
                return "ritual"
            if method == "getObjectByName":
                return {"ritualLeader": "leader", "bossSpawn": "spawn"}[args[0]]
        if handle == "loop" and method == "run":
            if self.defeatOn is not None and self.pending == self.defeatOn and not self.defeated:
                self.receipt = json.dumps({"map": "Ritual", "hp": 0, "x": 1, "y": 0, "z": 0, "lostItemCount": 12})
                self.hp = 1
                self.position = (0, 0, 0)
                self.defeated = True
            elif self.pending == "movement" and (self.blocked or (self.victoryRollback and self.moves == 1)):
                self.position = (0, 0, 0)
            self.pending = None
            return None
        raise AssertionError((handle, method, args))

    def driver(self):
        driver = NarrativeWalkthrough(self.engineCall, self.handleCall, "game", "map", "player")
        driver.walkable = {(0, 0, 0), (1, 0, 0)}
        driver.objects = {"bossSpawn": (1, 0, 0)}
        return driver


class NarrativeWalkthroughSurvivalTest(unittest.TestCase):
    def assertDefeatState(self, error, session, *, target, movement_steps, map_turns):
        state = error.exception.args[0]
        self.assertEqual("Walkthrough player was defeated", state["reason"])
        self.assertEqual(session.receipt, state["uiDefeatReceipt"])
        self.assertEqual(session.position, state["playerCoords"])
        self.assertEqual(session.nativeTurn, state["nativeTurn"])
        self.assertEqual(movement_steps, state["movementSteps"])
        self.assertEqual(map_turns, state["mapTurns"])
        self.assertEqual(target, state["target"]["coords"])
        self.assertEqual(1, state["player"]["hp"])
        self.assertEqual(
            {"hp": 1, "hpMax": 10, "mana": 4, "manaMax": 8, "LifePotion": 6, "ManaPotion": 6}, state["resources"]
        )
        if target:
            self.assertEqual(9, state["target"]["objects"]["ritualLeader"]["hp"])
            self.assertEqual(3, state["target"]["objects"]["ritualLeader"]["mana"])

    def testFreshFixtureRejectsAnExistingReceiptWithoutClearingIt(self):
        session = RouteSession(receipt='{"map":"Earlier defeat"}')
        with self.assertRaises(AssertionError) as error:
            session.driver()
        self.assertEqual("fresh fixture", error.exception.args[0]["stage"])
        self.assertEqual(session.receipt, error.exception.args[0]["uiDefeatReceipt"])
        self.assertEqual(0, session.moves + session.turns)
        self.assertFalse(any(method.startswith("set") for _, method, _ in session.calls))

    def testMoveToPumpRejectsRevivedDefeatBeforeAnotherMapTurn(self):
        session = RouteSession(defeat_on="movement")
        driver = session.driver()
        with self.assertRaises(AssertionError) as error:
            driver.walkTo((1, 0, 0))
        self.assertDefeatState(error, session, target=(1, 0, 0), movement_steps=1, map_turns=0)
        self.assertEqual(1, session.moves)
        self.assertEqual(0, session.turns)
        self.assertTrue(session.hp > 0)

    def testMapMovePumpRejectsRevivedDefeat(self):
        session = RouteSession(defeat_on="turn")
        driver = session.driver()
        with self.assertRaises(AssertionError) as error:
            driver.tick()
        self.assertDefeatState(error, session, target=None, movement_steps=0, map_turns=1)
        self.assertEqual(1, session.turns)
        self.assertTrue(session.hp > 0)

    def testArrivalAndStopCannotHideAnExistingDefeatReceipt(self):
        for stop in (None, lambda: True):
            with self.subTest(stop=stop is not None):
                session = RouteSession()
                driver = session.driver()
                session.receipt = "defeat recorded since the previous pump"
                with self.assertRaises(AssertionError):
                    driver.walkTo((0, 0, 0), stop=stop)
                self.assertEqual(0, session.moves + session.turns)

    def testOrdinaryVictoryRollbackCanRetryWithAnEmptyReceipt(self):
        session = RouteSession(victory_rollback=True)
        driver = session.driver()
        driver.walkTo((1, 0, 0))
        self.assertEqual((1, 0, 0), session.position)
        self.assertEqual("", session.receipt)
        self.assertEqual(2, session.moves)
        self.assertEqual(2, session.turns)
        self.assertEqual(2, driver.log["movementSteps"])
        self.assertEqual(2, driver.log["mapTurns"])

    def testEmptyReceiptAllowsOrdinaryMovementAndTurns(self):
        session = RouteSession()
        driver = session.driver()
        driver.walkTo((1, 0, 0))
        driver.tick()
        self.assertEqual("", session.receipt)
        self.assertEqual(1, session.moves)
        self.assertEqual(2, session.turns)

    def testHealthyMovementBudgetFailureIncludesResourcesAndKeeps256Steps(self):
        session = RouteSession(blocked=True)
        driver = session.driver()
        with self.assertRaises(AssertionError) as error:
            driver.walkTo((1, 0, 0))
        state = error.exception.args[0]
        self.assertEqual("Movement did not reach the authored target", state["reason"])
        self.assertEqual("movement budget", state["stage"])
        self.assertEqual("", state["uiDefeatReceipt"])
        self.assertEqual(256, session.moves)
        self.assertEqual(256, session.turns)
        self.assertEqual(297, state["nativeTurn"])
        self.assertEqual(10, state["resources"]["hp"])
        self.assertEqual(6, state["resources"]["LifePotion"])
        self.assertEqual(6, state["resources"]["ManaPotion"])
        self.assertEqual(9, state["target"]["objects"]["ritualLeader"]["hp"])

    def testMissingAuthoredRouteIncludesResourcesAndTheOriginalRouteError(self):
        session = RouteSession()
        driver = session.driver()
        driver.walkable = {(0, 0, 0)}
        with self.assertRaises(AssertionError) as error:
            driver.walkTo((1, 0, 0))
        state = error.exception.args[0]
        self.assertEqual("No adjacent authored route", state["reason"])
        self.assertEqual("", state["uiDefeatReceipt"])
        self.assertEqual(41, state["nativeTurn"])
        self.assertEqual(10, state["resources"]["hp"])
        self.assertEqual(9, state["target"]["objects"]["ritualLeader"]["hp"])
        self.assertIn("No authored walkable route", str(error.exception.__cause__))
        self.assertEqual(0, session.moves + session.turns)


class HealingRouteSession(RouteSession):
    def __init__(self, *, hp=10, movement_damage=0, turn_damage=0, ineffective=False, corrupt_use=None):
        super().__init__()
        self.hp = hp
        self.movementDamage = movement_damage
        self.turnDamage = turn_damage
        self.ineffective = ineffective
        self.corruptUse = corrupt_use
        self.items = {f"life{index}": {"typeId": "LifePotion", "power": 2, "heal": True} for index in range(6)}
        self.items.update({f"mana{index}": {"typeId": "ManaPotion", "power": 3, "heal": False} for index in range(6)})

    def handleCall(self, handle, method, args):
        if isinstance(handle, dict):
            handle = handle["__handle__"]
        if handle == "player" and method == "getItems":
            self.calls.append((handle, method, args))
            return [
                mcpHandle(identity, item.get("class", "LifePotion" if item["heal"] else "ManaPotion"))
                for identity, item in self.items.items()
            ]
        if handle == "player" and method == "countItems":
            self.calls.append((handle, method, args))
            return sum(item["typeId"] == args[0] for item in self.items.values())
        if handle in self.items:
            self.calls.append((handle, method, args))
            item = self.items[handle]
            if method == "hasTag":
                return item["heal"] if args == ["heal"] else item.get("mana", False)
            if method == "getType":
                return item.get("class", "LifePotion" if item["heal"] else "ManaPotion")
            if method == "getNumericProperty" and args == ["power"]:
                return item["power"]
            if method == "getPower":
                return item["power"]
            if method == "getTypeId":
                return item["typeId"]
            if method == "getName":
                return handle
        if handle == "player" and method == "useItem":
            self.calls.append((handle, method, args))
            item_id = args[0]["__handle__"]
            item = self.items.pop(item_id)
            if not self.ineffective:
                amount = max(1, int(item["power"] * 20 / 100.0 * self.hpMax))
                self.hp = min(self.hpMax, self.hp + amount)
            if self.corruptUse:
                self.corruptUse(self, item_id, item)
            return None
        pending = self.pending
        result = super().handleCall(handle, method, args)
        if handle == "loop" and method == "run":
            damage = self.movementDamage if pending == "movement" else self.turnDamage if pending == "turn" else 0
            self.hp -= damage
            if self.hp <= 0:
                self.receipt = json.dumps({"hp": 1, "lostItemCount": len(self.items)})
                self.items.clear()
                self.hp = 1
                self.position = (0, 0, 0)
                self.defeated = True
        return result


class NarrativeWalkthroughRecoveryTest(unittest.TestCase):
    def usedItems(self, session):
        return [
            args[0]["__handle__"]
            for handle, method, args in session.calls
            if handle == "player" and method == "useItem"
        ]

    def testWoundedPlayerRecoversBeforeMovingIntoTheNextEncounter(self):
        session = HealingRouteSession(hp=4, movement_damage=6)
        driver = session.driver()
        driver.walkTo((1, 0, 0))
        methods = [method for _, method, _ in session.calls]
        self.assertLess(methods.index("useItem"), methods.index("moveTo"))
        self.assertFalse(session.defeated)
        self.assertEqual("", session.receipt)
        self.assertEqual(1, session.moves)
        self.assertEqual(1, session.turns)
        self.assertEqual(42, session.nativeTurn)
        self.assertEqual(6 - len(self.usedItems(session)), driver.call("player", "countItems", ["LifePotion"]))
        self.assertEqual(6, driver.call("player", "countItems", ["ManaPotion"]))

    def testMovementWoundRecoversBeforePursuersActOnTheFollowingTurn(self):
        session = HealingRouteSession(movement_damage=6, turn_damage=6)
        driver = session.driver()
        driver.walkTo((1, 0, 0))
        methods = [method for _, method, _ in session.calls]
        self.assertLess(methods.index("moveTo"), methods.index("useItem"))
        self.assertLess(methods.index("useItem"), methods.index("move"))
        self.assertEqual(["life0"], self.usedItems(session))
        self.assertEqual(2, session.hp)
        self.assertEqual("", session.receipt)
        self.assertEqual(1, driver.log["movementSteps"])
        self.assertEqual(1, driver.log["mapTurns"])

    def testWaitingTurnRecoversWithOwnedItemsWithoutExtraTurns(self):
        session = HealingRouteSession(hp=4, turn_damage=6)
        driver = session.driver()
        driver.tick()
        self.assertEqual(["life0"], self.usedItems(session))
        self.assertEqual(2, session.hp)
        self.assertEqual(5, driver.call("player", "countItems", ["LifePotion"]))
        self.assertEqual(6, driver.call("player", "countItems", ["ManaPotion"]))
        self.assertEqual(0, session.moves)
        self.assertEqual(1, session.turns)
        self.assertEqual("", session.receipt)

    def testRecoveryUsesWeakerTaggedSuppliesFirstAndCapsHealth(self):
        session = HealingRouteSession(hp=4)
        session.items = {
            "life": {"typeId": "FullLifePotion", "power": 5, "heal": True},
            "beer": {"typeId": "DarkBeer", "power": 1, "heal": True},
            "mana": {"typeId": "ManaPotion", "power": 3, "heal": False},
        }
        driver = session.driver()
        driver.tick()
        self.assertEqual(["beer", "life"], self.usedItems(session))
        self.assertEqual(10, session.hp)
        self.assertEqual(["mana"], list(session.items))
        self.assertEqual(1, session.turns)

    def testHealthyArrivalAndSatisfiedStopDoNotConsumeItems(self):
        for hp, target, stop in ((10, (1, 0, 0), None), (4, (0, 0, 0), None), (4, (1, 0, 0), lambda: True)):
            with self.subTest(hp=hp, target=target, stop=stop is not None):
                session = HealingRouteSession(hp=hp)
                driver = session.driver()
                driver.walkTo(target, stop=stop)
                self.assertEqual([], self.usedItems(session))
                self.assertEqual(12, len(session.items))

    def testMissingOrNonHealingItemsNeverManufactureRecovery(self):
        for items in (
            {},
            {"mana": {"typeId": "ManaPotion", "power": 3, "heal": False}},
            {"empty": {"typeId": "EmptyPotion", "power": 0, "heal": True}},
        ):
            with self.subTest(items=items):
                session = HealingRouteSession(hp=4)
                session.items = items.copy()
                driver = session.driver()
                driver.tick()
                self.assertEqual([], self.usedItems(session))
                self.assertEqual(4, session.hp)
                self.assertEqual(items, session.items)
                self.assertEqual(1, session.turns)

    def testDefeatReceiptRejectsBeforeAnyRecoveryOrProgress(self):
        session = HealingRouteSession(hp=4)
        driver = session.driver()
        session.receipt = "recorded defeat"
        with self.assertRaises(AssertionError):
            driver.tick()
        self.assertEqual([], self.usedItems(session))
        self.assertEqual(12, len(session.items))
        self.assertEqual(0, session.moves + session.turns)

    def testIneffectiveNativeItemFailsAfterOneUseWithoutAdvancingTheMap(self):
        session = HealingRouteSession(hp=4, ineffective=True)
        driver = session.driver()
        with self.assertRaises(AssertionError) as error:
            driver.tick()
        state = error.exception.args[0]
        self.assertEqual("Carried healing item did not restore health", state["reason"])
        self.assertEqual(41, state["nativeTurn"])
        self.assertEqual(5, state["resources"]["LifePotion"])
        self.assertEqual(6, state["resources"]["ManaPotion"])
        self.assertEqual(["life0"], self.usedItems(session))
        self.assertEqual(0, session.moves + session.turns)

    def testDirectRecoveryRejectsDeadAndRecordedDefeatsBeforeReadingInventory(self):
        for hp, receipt in ((0, ""), (4, "recorded defeat"), (10, "recorded defeat")):
            with self.subTest(hp=hp, receipt=receipt):
                session = HealingRouteSession()
                driver = session.driver()
                session.hp, session.receipt = hp, receipt
                before = session.items.copy()
                with self.assertRaises(AssertionError):
                    driver.recoverBeforeAction("direct recovery")
                self.assertEqual([], self.usedItems(session))
                self.assertEqual(before, session.items)
                self.assertEqual(hp, session.hp)
                self.assertEqual(0, session.moves + session.turns)

    def testRecoveryRejectsReusableMixedAndInvalidHealingCandidates(self):
        session = HealingRouteSession(hp=4)
        session.items = {
            "reusable": {"typeId": "HealingItem", "class": "CItem", "power": 1, "heal": True},
            "dual": {"typeId": "DualPotion", "power": 5, "heal": True, "mana": True},
            "mixed": {"typeId": "OasisWater", "class": "RejuvenationPotion", "power": 2, "heal": True},
            "negative": {"typeId": "InvalidPotion", "power": -1, "heal": True},
            "untagged": {"typeId": "UntaggedPotion", "class": "LifePotion", "power": 1, "heal": False},
        }
        before = session.items.copy()
        driver = session.driver()
        driver.recoverBeforeAction("candidate regression")
        self.assertEqual([], self.usedItems(session))
        self.assertEqual(before, session.items)
        self.assertEqual(4, session.hp)
        self.assertEqual(0, session.moves + session.turns)

    def testRecoveryMatchesNativeTruncationMinimumAndMaximumHealth(self):
        for hp_max, hp, power, expected in ((91, 20, 1, 38), (70, 1, 2, 29), (3, 1, 1, 2), (10, 4, 5, 10)):
            with self.subTest(hp_max=hp_max, hp=hp, power=power):
                session = HealingRouteSession(hp=hp)
                session.hpMax = hp_max
                session.items = {"life": {"typeId": "LifePotion", "power": power, "heal": True}}
                driver = session.driver()
                driver.recoverBeforeAction("native formula regression")
                self.assertEqual(expected, session.hp)
                self.assertEqual({}, session.items)
                self.assertEqual(["life"], self.usedItems(session))
                self.assertEqual(0, session.moves + session.turns)

    def testUnexpectedHealingAmountFailsBeforeProgress(self):
        session = HealingRouteSession(hp=4, corrupt_use=lambda state, *_: setattr(state, "hp", state.hp + 1))
        driver = session.driver()
        with self.assertRaises(AssertionError) as error:
            driver.recoverBeforeAction("health regression")
        self.assertEqual("Carried healing item restored unexpected health", error.exception.args[0]["reason"])
        self.assertEqual(["life0"], self.usedItems(session))
        self.assertEqual(0, session.moves + session.turns)

    def testUnexpectedInventoryChangesFailBeforeProgress(self):
        corruptions = (
            lambda state, handle, item: state.items.update({handle: item}),
            lambda state, *_: state.items.pop("mana0"),
            lambda state, _, item: state.items.update({"new-item": item}),
        )
        for corruption in corruptions:
            with self.subTest(corruption=corruption):
                session = HealingRouteSession(hp=4, corrupt_use=corruption)
                driver = session.driver()
                with self.assertRaises(AssertionError) as error:
                    driver.recoverBeforeAction("inventory regression")
                self.assertEqual("Inventory recovery changed unexpected items", error.exception.args[0]["reason"])
                self.assertEqual(["life0"], self.usedItems(session))
                self.assertEqual(0, session.moves + session.turns)

    def testUnrelatedResourcesAndProgressionChangesFailBeforeProgress(self):
        for attribute, value in (
            ("mana", 5),
            ("gold", 21),
            ("experience", 101),
            ("level", 2),
            ("hpMax", 11),
            ("nativeTurn", 42),
            ("position", (1, 0, 0)),
            ("quests", []),
            ("completedQuests", []),
        ):
            with self.subTest(attribute=attribute):
                corruption = lambda state, *_, attr=attribute, changed=value: setattr(state, attr, changed)
                session = HealingRouteSession(hp=4, corrupt_use=corruption)
                driver = session.driver()
                with self.assertRaises(AssertionError) as error:
                    driver.recoverBeforeAction("state regression")
                self.assertEqual("Inventory recovery changed unrelated state", error.exception.args[0]["reason"])
                self.assertEqual(["life0"], self.usedItems(session))
                self.assertEqual(0, session.moves + session.turns)

    def testRecoveryUsesOnlyMcpExportedMethods(self):
        import mcp

        session = HealingRouteSession(hp=4)
        driver = session.driver()
        driver.recoverBeforeAction("MCP protocol regression")
        for handle, method, _ in session.calls:
            classes = ["CGameObject"]
            if handle == "player":
                classes.extend(("CCreature", "CPlayer"))
            elif handle == "map":
                classes.append("CMap")
            allowed = set().union(*(mcp.MCP_ALLOWED_HANDLE_METHODS[name] for name in classes))
            self.assertIn(method, allowed, (handle, method))

    def testMcpCollectionsCompareIdentityDespiteChangingHandleMetadata(self):
        session = HealingRouteSession(hp=4)
        driver = session.driver()
        self.assertEqual(2, len(driver.call("player", "getQuests")))
        self.assertEqual(2, len(driver.call("player", "getCompletedQuests")))
        item = driver.call("player", "getItems")[0]
        self.assertEqual({"__handle__", "__type__", "repr"}, set(item))
        native_call = session.handleCall

        def changingMetadata(handle, method, args):
            result = native_call(handle, method, args)
            if method in ("getItems", "getQuests", "getCompletedQuests"):
                for value in result:
                    value["repr"] = f"inspection {len(session.calls)}"
            return result

        driver.handleCall = changingMetadata
        driver.recoverBeforeAction("identity regression")
        self.assertEqual(["life0"], self.usedItems(session))
        self.assertEqual(8, session.hp)
        self.assertEqual(5, driver.call("player", "countItems", ["LifePotion"]))
        self.assertEqual(6, driver.call("player", "countItems", ["ManaPotion"]))
        self.assertEqual(0, session.moves + session.turns)

    def testRecoveryRechecksOwnershipBeforeUsingEachCapturedCandidate(self):
        session = HealingRouteSession(hp=4)
        driver = session.driver()
        native_call = session.handleCall
        reads = 0

        def ownershipChanged(handle, method, args):
            nonlocal reads
            if handle == "player" and method == "getItems":
                reads += 1
                if reads == 2:
                    session.items.pop("life0")
            return native_call(handle, method, args)

        driver.handleCall = ownershipChanged
        with self.assertRaises(AssertionError) as error:
            driver.recoverBeforeAction("ownership regression")
        self.assertEqual("Carried healing item was no longer owned", error.exception.args[0]["reason"])
        self.assertEqual([], self.usedItems(session))
        self.assertEqual(4, session.hp)
        self.assertEqual(0, session.moves + session.turns)


if __name__ == "__main__":
    unittest.main()
