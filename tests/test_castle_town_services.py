# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Paid town rest, using the real plugin with lightweight engine stand-ins."""

import copy
import json
import sys
import types
import unittest
from unittest import mock

from tests.test_castle_campaign import FakeMap, FakeObject, FakePlayer, loadCastleModule


class TownPlayer(FakePlayer):
    def __init__(self, game_map):
        super().__init__(game_map)
        self.hp = 4
        self.max_hp = 20
        self.items = []

    def getHp(self):
        return self.hp

    def getHpMax(self):
        return self.max_hp

    def healProc(self, percent):
        self.hp = min(self.max_hp, self.hp + self.max_hp * percent // 100)

    def addItem(self, name):
        self.items.append(name)


class DialogObject(FakeObject):
    def setOptions(self, options):
        self.options = options

    def setStates(self, states):
        self.states = states


class CastleTownServicesTest(unittest.TestCase):
    def setUp(self):
        self.castle = loadCastleModule()
        self.game_map = FakeMap()
        self.game_map.setStringProperty("mapName", "castleGriffinCliff")
        self.player = self.game_map.player = TownPlayer(self.game_map)
        self.dialogs = []
        self.registry = {}
        self.game = self.game_map.game
        self.game.getGuiHandler = lambda: types.SimpleNamespace(
            showMessage=self.game_map.messages.append, showDialog=self.dialogs.append
        )
        self.game.createObject = lambda kind: self.registry.get(kind, DialogObject)(game_map=self.game_map)

        def register(context):
            def remember(cls):
                self.registry[cls.__name__] = cls
                return cls

            return remember

        def claimOnce(game_map, flag):
            if game_map.getBoolProperty(flag):
                return False
            game_map.setBoolProperty(flag, True)
            return True

        game_api = types.SimpleNamespace(
            CBuilding=DialogObject,
            CDialog=DialogObject,
            CEvent=DialogObject,
            CQuest=DialogObject,
            CTrigger=DialogObject,
            Coords=lambda x, y, z: types.SimpleNamespace(x=x, y=y, z=z),
            claim_once=claimOnce,
            register=register,
            campaign=types.SimpleNamespace(state=lambda game: None),
        )
        patcher = mock.patch.dict(sys.modules, {"game": game_api})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.castle.load(None, None)
        mission = {"captureIds": ["town", "pending"], "objectiveIds": ["town", "pending"], "scenarioId": "test"}
        self.game_map.objects["castleMission"] = FakeObject(
            "castleMission", self.game_map, campaign_mission=json.dumps(mission)
        )
        self.town = self.makeTown()
        self.event = types.SimpleNamespace(getCause=lambda: self.player)

    def makeTown(self, loyal=True):
        town = self.registry["CastleSupply" if loyal else "CastleObjective"](
            "town",
            self.game_map,
            campaign_isTown=True,
            campaign_loyalTown=loyal,
            campaign_objectiveId="town" if not loyal else "",
            campaign_rewardGold=25 if loyal else 50,
            label="Castle town",
        )
        self.game_map.objects["town"] = town
        return town

    def testPaidRestHealsAndChargesOnceUntilInjuredAgain(self):
        self.assertTrue(self.castle.restAtTown(self.town, self.player))
        self.assertEqual((self.player.getHp(), self.player.getGold()), (20, 27))
        self.assertFalse(self.castle.restAtTown(self.town, self.player))
        self.assertEqual(self.player.getGold(), 27)
        self.player.hp = 19
        self.assertTrue(self.castle.restAtTown(self.town, self.player))
        self.assertEqual((self.player.getHp(), self.player.getGold()), (20, 17))
        self.assertEqual(self.player.items, [])

    def testCannotRestWithInsufficientGoldOrFullHealth(self):
        self.player.gold = 9
        self.assertFalse(self.castle.restAtTown(self.town, self.player))
        self.assertEqual((self.player.getHp(), self.player.getGold()), (4, 9))
        self.player.gold = 10
        self.player.hp = 20
        self.assertFalse(self.castle.restAtTown(self.town, self.player))
        self.assertEqual(self.player.getGold(), 10)
        self.player.hp = 1
        self.assertTrue(self.castle.restAtTown(self.town, self.player))
        self.assertEqual((self.player.getHp(), self.player.getGold()), (20, 0))

    def testCapturedTownRequiresPersistedCaptureFlag(self):
        self.town = self.makeTown(loyal=False)
        self.assertFalse(self.castle.restAtTown(self.town, self.player))
        self.game_map.setBoolProperty(self.castle.objectiveFlag("town"), True)
        # Eligibility comes from serialized map properties, without transient visit state.
        saved_properties = json.loads(json.dumps(self.game_map.properties))
        self.game_map.properties = saved_properties
        self.assertTrue(self.castle.restAtTown(self.town, self.player))
        self.assertEqual(self.player.getGold(), 27)
        self.assertTrue(self.game_map.getBoolProperty(self.castle.objectiveFlag("town")))

    def testTowerAndFieldAidCannotOfferTownRest(self):
        for loyal in (True, False):
            with self.subTest(loyal=loyal):
                self.town = self.makeTown(loyal)
                self.town.setBoolProperty("campaign_isTown", False)
                self.game_map.setBoolProperty(self.castle.objectiveFlag("town"), True)
                self.assertFalse(self.castle.canUseTown(self.town, self.player))
                self.assertFalse(self.castle.restAtTown(self.town, self.player))
                self.assertFalse(self.castle.showTownServices(self.town, self.player))
        self.assertEqual((self.player.getHp(), self.player.getGold()), (4, 37))
        self.assertEqual(self.dialogs, [])

    def testRejectsRemoteWrongFloorDeadAndWrongPlayer(self):
        initial_coords = copy.copy(self.player.coords)
        for coords in ((5, 3, 0), (3, 3, 1)):
            self.player.coords = types.SimpleNamespace(x=coords[0], y=coords[1], z=coords[2])
            self.assertFalse(self.castle.restAtTown(self.town, self.player))
        self.player.coords = initial_coords
        self.player.alive = False
        self.assertFalse(self.castle.restAtTown(self.town, self.player))
        self.player.alive = True
        impostor = TownPlayer(self.game_map)
        self.assertFalse(self.castle.restAtTown(self.town, impostor))
        self.assertFalse(self.castle.restAtTown(self.town, FakeObject(game_map=self.game_map)))
        self.assertFalse(self.castle.restAtTown(self.town, None))
        self.assertEqual((self.player.getHp(), self.player.getGold()), (4, 37))

    def testRejectsRemovedTownInactiveMapAndForeignCaptureId(self):
        self.game_map.objects.pop("town")
        self.assertFalse(self.castle.restAtTown(self.town, self.player))
        self.game_map.objects["town"] = self.town
        self.game.getMap = lambda: None
        self.assertFalse(self.castle.restAtTown(self.town, self.player))
        self.game.getMap = lambda: self.game_map
        self.town = self.makeTown(loyal=False)
        self.town.setStringProperty("campaign_objectiveId", "foreignTown")
        self.game_map.setBoolProperty(self.castle.objectiveFlag("foreignTown"), True)
        self.assertFalse(self.castle.restAtTown(self.town, self.player))

    def testLoyalTownKeepsFirstAidThenRequiresExplicitPaidRest(self):
        self.town.onEnter(self.event)
        self.assertEqual((self.player.getHp(), self.player.getGold()), (20, 62))
        self.assertEqual(self.player.items, ["LifePotion"])
        self.assertEqual(len(self.dialogs), 1)
        self.assertFalse(self.dialogs[-1].canRest())
        self.assertFalse(self.dialogs[-1].rest())
        self.assertEqual(self.player.getGold(), 62)
        self.player.hp = 4
        self.town.onEnter(self.event)
        self.assertEqual((self.player.getHp(), self.player.getGold()), (4, 62))
        self.assertEqual(self.player.items, ["LifePotion"])
        self.assertTrue(self.dialogs[-1].canRest())
        self.assertTrue(self.dialogs[-1].rest())
        self.assertEqual((self.player.getHp(), self.player.getGold()), (20, 52))

    def testCapturedTownRevisitDoesNotRepeatCaptureReward(self):
        self.town = self.makeTown(loyal=False)
        self.assertTrue(self.town.onEnter(self.event))
        self.assertEqual(self.player.getGold(), 87)
        self.assertEqual(self.dialogs, [])
        self.assertTrue(self.town.onEnter(self.event))
        self.assertEqual(self.player.getGold(), 87)
        self.assertTrue(self.dialogs[-1].rest())
        self.assertEqual((self.player.getHp(), self.player.getGold()), (20, 77))
        self.town.onEnter(self.event)
        self.assertFalse(self.dialogs[-1].rest())
        self.assertEqual(self.player.getGold(), 77)

    def testFieldAidStillOnlyGivesSuppliesOnceWithoutDialog(self):
        self.town.setBoolProperty("campaign_isTown", False)
        self.town.onEnter(self.event)
        self.player.hp = 4
        self.town.onEnter(self.event)
        self.assertEqual((self.player.getHp(), self.player.getGold()), (4, 62))
        self.assertEqual(self.player.items, ["LifePotion"])
        self.assertEqual(self.dialogs, [])

    def testDialogHasWorkingActionAndExitAndRevalidatesAtActionTime(self):
        self.assertTrue(self.castle.showTownServices(self.town, self.player))
        dialog = self.dialogs[-1]
        state = next(iter(dialog.states))
        self.assertEqual(state.getStringProperty("stateId"), "ENTRY")
        rest, leave = sorted(state.options, key=lambda option: option.getNumericProperty("number"))
        self.assertEqual(rest.getStringProperty("action"), "rest")
        self.assertEqual(rest.getStringProperty("condition"), "canRest")
        self.assertEqual(rest.getStringProperty("nextStateId"), "EXIT")
        self.assertEqual(leave.getStringProperty("nextStateId"), "EXIT")
        self.player.coords.x += 2
        self.assertFalse(dialog.canRest())
        self.assertFalse(dialog.rest())
        self.player.coords.x -= 2
        self.player.gold = 9
        self.assertFalse(dialog.rest())
        self.player.gold = 37
        self.game_map.setStringProperty("mapName", "anotherMap")
        self.assertFalse(dialog.rest())
        self.assertEqual((self.player.getHp(), self.player.getGold()), (4, 37))


if __name__ == "__main__":
    unittest.main()
