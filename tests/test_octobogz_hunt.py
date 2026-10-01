# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class Properties:
    def __init__(self):
        self.properties = {}
        self.game = None
        self.game_map = None
        self.coords = types.SimpleNamespace(x=0, y=0, z=0)

    def getStringProperty(self, name):
        return self.properties.get(name, "")

    def setStringProperty(self, name, value):
        self.properties[name] = value

    def getBoolProperty(self, name):
        return self.properties.get(name, False)

    def setBoolProperty(self, name, value):
        self.properties[name] = value

    def getNumericProperty(self, name):
        return self.properties.get(name, 0)

    def setNumericProperty(self, name, value):
        self.properties[name] = value

    def getGame(self):
        return self.game

    def getMap(self):
        return self.game_map

    def getName(self):
        return self.getStringProperty("name")

    def getTypeId(self):
        return self.getStringProperty("typeId")

    def getCoords(self):
        return self.coords

    def relocateWithoutMoveHooks(self, coords):
        self.coords = coords


class Actor(Properties):
    def __init__(self, name="", player=False):
        super().__init__()
        self.properties.update(name=name, typeId="OctoBogz", affiliation="bogz", hp=49, mana=70, level=1)
        self.player = player
        self.actions = {}
        self.effects = []
        self.checkQuests = Mock()
        self.damage_rolls = 0

    def isPlayer(self):
        return self.player

    def isAlive(self):
        return self.getHp() > 0

    def getHp(self):
        return self.getNumericProperty("hp")

    def getMana(self):
        return self.getNumericProperty("mana")

    def getLevel(self):
        return self.getNumericProperty("level")

    def getHpMax(self):
        return 49

    def getManaMax(self):
        return 70

    def setHp(self, value):
        self.properties["hp"] = value

    def setMana(self, value):
        self.properties["mana"] = value

    def getLabel(self):
        return self.getStringProperty("label") or "OctoBogz"

    def addAction(self, action):
        self.actions[action.getTypeId()] = action

    def getActions(self):
        return list(self.actions.values())

    def getController(self):
        return getattr(self, "controller", None)

    def setController(self, controller):
        self.controller = controller

    def getDmg(self):
        self.damage_rolls += 1
        return self.getNumericProperty("damageRoll")

    def hurt(self, packet):
        self.setHp(self.getHp() - packet.getNumericProperty("shadow"))


class HuntMap(Properties):
    mapName = "nouraajd"

    def __init__(self, game):
        super().__init__()
        self.game = game
        self.objects = {}
        self.triggers = {}
        self.player = Actor("player", True)
        self.player.game = game
        self.player.game_map = self
        self.objects["player"] = self.player
        self.blocked = set()
        self.block_all = False
        self.completed = 0
        self.added = []

    def getObjects(self):
        return list(self.objects.values())

    def getPlayer(self):
        return self.player

    def getObjectByName(self, name):
        return self.objects.get(name)

    def getObjectsAtCoords(self, coords):
        return [
            obj
            for obj in self.objects.values()
            if (obj.coords.x, obj.coords.y, obj.coords.z) == (coords.x, coords.y, coords.z)
        ]

    def canStep(self, coords):
        return not self.block_all and (coords.x, coords.y, coords.z) not in self.blocked

    def addObject(self, obj):
        self.assertUnused(obj.getName())
        obj.game_map = self
        obj.game = self.game
        self.objects[obj.getName()] = obj
        self.added.append(obj.getName())
        if isinstance(obj, Actor):
            if obj.getLevel() == 0:
                obj.setNumericProperty("level", 1)
            obj.setHp(obj.getHpMax())
            obj.setMana(obj.getManaMax())

    def assertUnused(self, name):
        if name in self.objects:
            raise AssertionError("Duplicate runtime actor: " + name)

    def removeObject(self, obj):
        self.objects.pop(obj.getName())
        if isinstance(obj, Actor):
            obj.effects.clear()
        if obj.getName() == "cave2" and self.getBoolProperty("octobogzHuntCleared"):
            self.completed += 1
        for trigger in list(self.triggers.values()):
            if trigger.getStringProperty("object") == obj.getName():
                trigger.trigger(obj, None)
        obj.game_map = None

    def getEventHandler(self):
        return self

    def registerTrigger(self, trigger):
        self.triggers[(trigger.getName(), trigger.getStringProperty("object"))] = trigger


class OctobogzHuntTest(unittest.TestCase):
    def setUp(self):
        self.registered = {}
        self.pending = []
        game_stub = types.ModuleType("game")
        for name in ("CBuilding", "CEffect", "CEvent", "CInteraction", "CTrigger"):
            setattr(game_stub, name, type(name, (Properties,), {}))
        game_stub.Coords = lambda x, y, z: types.SimpleNamespace(x=x, y=y, z=z)
        game_stub.register = lambda context: lambda cls: self.registered.setdefault(cls.__name__, cls)
        game_stub.event_loop = types.SimpleNamespace(instance=lambda: types.SimpleNamespace(invoke=self.pending.append))
        with patch.dict(sys.modules, {"game": game_stub}):
            spec = importlib.util.spec_from_file_location(
                "octobogz_hunt_under_test", ROOT / "res/plugins/octobogz_hunt.py"
            )
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)
            self.module.load(None, None)
        self.game = Mock()
        self.game_map = HuntMap(self.game)
        self.game.getMap.return_value = self.game_map
        self.game.createObject.side_effect = self.createObject
        self.director = self.createObject("OctobogzHuntDirector")
        lair = self.createObject("cave2")
        self.game_map.addObject(lair)

    def createObject(self, type_id):
        mapping = {
            "cave2": "OctobogzLair",
            "octobogzCharge": "OctobogzCharge",
            "octobogzShadowPulse": "OctobogzShadowPulse",
        }
        if type_id == "OctoBogz":
            result = Actor()
        elif type_id == "CTargetController":
            result = Mock()
        else:
            result = self.registered.get(mapping.get(type_id, type_id), Properties)()
        result.game = self.game
        result.setStringProperty("typeId", type_id)
        if type_id == "cave2":
            result.setStringProperty("name", "cave2")
            result.relocateWithoutMoveHooks(types.SimpleNamespace(x=166, y=21, z=0))
        return result

    def state(self):
        return self.module.huntState(self.game_map)

    def pump(self):
        while self.pending:
            self.pending.pop(0)()

    def kill(self, slot):
        name = self.state()["slots"][slot]["name"]
        actor = self.game_map.getObjectByName(name)
        actor.setHp(0)
        self.game_map.removeObject(actor)
        self.pump()
        return actor

    def testLairUsesSharedCaveArtworkAndPreservesOriginalDialogue(self):
        config = json.loads((ROOT / "res/maps/nouraajd/config.json").read_text(encoding="utf-8"))
        buildings = json.loads((ROOT / "res/config/buildings.json").read_text(encoding="utf-8"))
        self.assertEqual("octobogzLair", config["cave2"]["ref"])
        self.assertNotIn("animation", config["cave2"]["properties"])
        self.assertEqual("OctobogzLair", buildings["octobogzLair"]["class"])
        self.assertEqual(
            buildings["Cave"]["properties"]["animation"], buildings["octobogzLair"]["properties"]["animation"]
        )
        self.assertIn("you\u2014common", config["cave1"]["properties"]["message"])
        self.assertIn("knives\u2014please", json.dumps(config, ensure_ascii=False))

    def testFreshHuntHasExactlyThreeDeathsAndRepeatInteractionsCannotCompleteEarly(self):
        self.director.start(self.game_map)
        self.director.start(self.game_map)
        self.assertEqual(["cave2", "octobogzScout"], self.game_map.added)
        lair = self.game_map.getObjectByName("cave2")
        self.game_map.removeObject(lair)
        self.assertEqual(0, self.game_map.completed)
        self.assertFalse(self.game_map.getBoolProperty("octobogzHuntCleared"))
        self.director.synchronize(self.game_map)
        scout = self.kill("scout")
        self.assertEqual("brood", self.state()["stage"])
        self.assertEqual(
            3,
            sum(
                record["status"] == "living" or record["status"] == "dead" for record in self.state()["slots"].values()
            ),
        )
        self.kill("alpha")
        self.assertEqual(0, self.game_map.completed)
        self.assertIn("2/3", self.director.objectiveText(self.game_map))
        self.kill("brood")
        self.assertEqual("cleared", self.state()["stage"])
        self.assertEqual(1, self.game_map.completed)
        self.assertIsNone(self.game_map.getObjectByName("cave2"))
        self.director.actorRemoved(scout)
        self.director.start(self.game_map)
        self.assertEqual(1, self.game_map.completed)
        self.game_map.player.checkQuests.assert_called_once_with()

    def testRepeatedTurnsReuseActionsAndControllersAndBoundBlockedPlacement(self):
        self.director.start(self.game_map)
        self.kill("scout")
        actors = [self.game_map.getObjectByName(self.state()["slots"][slot]["name"]) for slot in ("brood", "alpha")]
        actions = [actor.getActions() for actor in actors]
        controllers = [actor.getController() for actor in actors]
        created_before = self.game.createObject.call_count
        for _ in range(20):
            self.director.synchronize(self.game_map)
        self.assertEqual(actions, [actor.getActions() for actor in actors])
        self.assertEqual(controllers, [actor.getController() for actor in actors])
        self.assertEqual(created_before + 40, self.game.createObject.call_count)
        self.assertEqual(3, len(self.game_map.triggers))
        self.game_map.block_all = True
        self.game_map.canStep = Mock(wraps=self.game_map.canStep)
        self.assertIsNone(self.director.findPlacement(self.game_map, (166, 21, 0)))
        self.assertEqual(25, self.game_map.canStep.call_count)

    def testLegacyOneTwoAndExtraActorsAreAdoptedWithoutDuplicatingLivingBrood(self):
        for count in (1, 2, 3, 6):
            with self.subTest(count=count):
                self.setUp()
                originals = []
                for index in range(count):
                    actor = Actor("legacy" + str(index))
                    actor.coords = types.SimpleNamespace(x=165, y=21, z=0)
                    self.game_map.addObject(actor)
                    actor.setHp(7 + index)
                    actor.setMana(11 + index)
                    originals.append(actor)
                self.director.synchronize(self.game_map)
                adopted = min(count, 3)
                for index, slot in enumerate(self.module.SLOT_NAMES[:adopted]):
                    self.assertIs(originals[index], self.game_map.getObjectByName(self.state()["slots"][slot]["name"]))
                    self.assertEqual(7 + index, originals[index].getHp())
                    self.assertEqual(11 + index, originals[index].getMana())
                self.kill("scout")
                self.assertEqual(
                    max(0, 3 - count), len([name for name in self.game_map.added if name.startswith("octobogz")])
                )
                if count >= 2:
                    self.assertIs(originals[1], self.game_map.getObjectByName("legacy1"))
                self.kill("brood")
                self.kill("alpha")
                self.assertEqual("cleared", self.state()["stage"])
                self.assertEqual(1, self.game_map.completed)
                for extra in originals[3:]:
                    self.assertIs(extra, self.game_map.getObjectByName(extra.getName()))
                    self.assertEqual("", extra.getStringProperty("octobogzHuntSlot"))

    def testAdoptedBroodCanDieBeforeScoutAndIsNeverRespawned(self):
        for name, x in (("legacy0", 165), ("legacy1", 166)):
            actor = Actor(name)
            actor.coords = types.SimpleNamespace(x=x, y=21, z=0)
            self.game_map.addObject(actor)
        self.director.synchronize(self.game_map)
        self.kill("brood")
        self.assertEqual("dead", self.state()["slots"]["brood"]["status"])
        self.kill("scout")
        self.assertIsNone(self.game_map.getObjectByName("legacy1"))
        self.assertIsNotNone(self.game_map.getObjectByName("octobogzAlpha"))

    def testLivingRemovalRestoresSameNameHealthManaAndConsumedPhasesOnce(self):
        self.director.start(self.game_map)
        self.kill("scout")
        alpha = self.game_map.getObjectByName("octobogzAlpha")
        alpha.setHp(9)
        alpha.setMana(6)
        alpha.setStringProperty("octobogzCombatPhase", "charged")
        alpha.setBoolProperty("enemyRoleUsed", True)
        alpha.effects = ["transient"]
        self.game_map.removeObject(alpha)
        self.assertEqual("pending", self.state()["slots"]["alpha"]["status"])
        self.assertEqual(0, self.game_map.completed)
        self.pump()
        restored = self.game_map.getObjectByName("octobogzAlpha")
        self.assertIsNot(alpha, restored)
        self.assertEqual((9, 6), (restored.getHp(), restored.getMana()))
        self.assertEqual("charged", restored.getStringProperty("octobogzCombatPhase"))
        self.assertTrue(restored.getBoolProperty("enemyRoleUsed"))
        self.assertEqual([], restored.effects)
        self.director.actorRemoved(alpha)
        self.director.synchronize(self.game_map)
        self.assertIs(restored, self.game_map.getObjectByName("octobogzAlpha"))

    def testMissingLivingActorRecoversFromLastTurnSnapshotAfterBlockedSave(self):
        self.director.start(self.game_map)
        scout = self.game_map.getObjectByName("octobogzScout")
        scout.setHp(5)
        scout.setMana(4)
        self.director.synchronize(self.game_map)
        self.game_map.objects.pop("octobogzScout")
        self.game_map.block_all = True
        self.director.synchronize(self.game_map)
        saved = json.loads(json.dumps(self.game_map.properties))
        self.game_map.properties = saved
        self.director.synchronize(self.game_map)
        self.assertEqual("pending", self.state()["slots"]["scout"]["status"])
        self.assertEqual(1, self.game.getGuiHandler.return_value.notify.call_count - 1)
        self.game_map.block_all = False
        self.director.synchronize(self.game_map)
        recovered = self.game_map.getObjectByName("octobogzScout")
        self.assertEqual((5, 4), (recovered.getHp(), recovered.getMana()))
        self.assertEqual(0, self.game_map.completed)

    def testNormalSaveReusePreservesNativeActorHealthManaAndEffects(self):
        self.director.start(self.game_map)
        scout = self.game_map.getObjectByName("octobogzScout")
        scout.setHp(3)
        scout.setMana(2)
        scout.effects = ["nativeSavedEffect"]
        self.game_map.properties = json.loads(json.dumps(self.game_map.properties))
        self.director.synchronize(self.game_map)
        self.assertIs(scout, self.game_map.getObjectByName("octobogzScout"))
        self.assertEqual((3, 2, ["nativeSavedEffect"]), (scout.getHp(), scout.getMana(), scout.effects))
        self.assertEqual(1, self.game_map.added.count("octobogzScout"))
        self.assertEqual(1, len(self.game_map.triggers))

    def testBlockedPlacementRetriesBoundedlyAndSkipsOccupiedCells(self):
        self.game_map.block_all = True
        self.director.start(self.game_map)
        self.assertEqual("pending", self.state()["slots"]["scout"]["status"])
        self.game_map.block_all = False
        marker = Properties()
        marker.setStringProperty("name", "occupiedPreferred")
        marker.coords = types.SimpleNamespace(x=165, y=21, z=0)
        self.game_map.addObject(marker)
        self.director.synchronize(self.game_map)
        actor = self.game_map.getObjectByName("octobogzScout")
        self.assertEqual((164, 21), (actor.coords.x, actor.coords.y))

    def testCompletedLegacyContractsAreGrandfatheredAndForeignMapsCannotSpawn(self):
        for flag in ("OCTOBOGZ_SLAIN", "completed_octobogz", "quest_state_octobogz_contract"):
            with self.subTest(flag=flag):
                self.setUp()
                self.game_map.properties[flag] = "completed" if flag.startswith("quest_state") else True
                self.director.start(self.game_map)
                self.assertEqual("cleared", self.state()["stage"])
                self.assertEqual(["cave2"], self.game_map.added)
                self.assertEqual(0, self.game_map.completed)
        self.setUp()
        self.game_map.mapName = "ritual"
        self.director.start(self.game_map)
        self.assertIn("Return to", self.director.objectiveText(self.game_map))
        self.assertIsNone(self.state())

    def testLairRequiresActualActivePlayerAtAuthoredCoordinates(self):
        lair = self.game_map.getObjectByName("cave2")
        player = self.game_map.player
        event = types.SimpleNamespace(getCause=lambda: player)
        lair.onEnter(event)
        self.assertIsNone(self.state())
        player.coords = lair.coords
        lair.onEnter(event)
        self.assertEqual("scout", self.state()["stage"])
        self.assertIsNotNone(self.game_map.getObjectByName("cave2"))

    def testPulseCapturesOneBasicRollAndDistributesExactlyItsBoundedBudget(self):
        actor = Actor("alpha")
        actor.game = self.game
        actor.properties["damageRoll"] = 11
        pulse = self.createObject("octobogzShadowPulse")
        effect = self.createObject("OctobogzShadowPulseEffect")
        effect.getCaster = lambda: actor
        effect.getVictim = lambda: self.game_map.player
        effect.getTimeLeft = lambda: 2
        pulse.performAction(actor, self.game_map.player)
        self.assertTrue(pulse.configureEffect(effect))
        self.assertEqual(1, actor.damage_rolls)
        self.assertEqual(8, effect.getNumericProperty("octobogzDamageBudget"))
        before = self.game_map.player.getHp()
        effect.onEffect()
        effect.getTimeLeft = lambda: 1
        effect.onEffect()
        self.assertEqual(before - 8, self.game_map.player.getHp())
        self.assertEqual(1, actor.damage_rolls)
        self.assertEqual("spent", actor.getStringProperty("octobogzCombatPhase"))
        self.assertTrue(actor.getBoolProperty("octobogzPulseUsed"))
        pulse.performAction(actor, self.game_map.player)
        duplicate = self.createObject("OctobogzShadowPulseEffect")
        duplicate.getCaster = lambda: actor
        self.assertFalse(pulse.configureEffect(duplicate))
        self.assertEqual(1, actor.damage_rolls)
        self.assertEqual(0, duplicate.getNumericProperty("octobogzDamageBudget"))


if __name__ == "__main__":
    unittest.main()
