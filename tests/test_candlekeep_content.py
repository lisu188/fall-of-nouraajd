# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Candlekeep source and model regressions; these confer no native gameplay credit."""

import ast
from collections import deque
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

from tests.hook_flow_support import installHookFlows

ROOT = Path(__file__).resolve().parents[1]
MAP_ROOT = ROOT / "res/maps/candlekeep"
QUEST_KEYS = ("firebead", "phlydia", "dreppin", "hull", "fuller", "reevor")


def readDocument(name):
    return json.loads((MAP_ROOT / name).read_text(encoding="utf-8"))


def authoredObjects():
    document = readDocument("map.json")
    return {
        obj["name"]: (obj, int(layer["properties"]["level"]))
        for layer in document["layers"]
        if layer["type"] == "objectgroup"
        for obj in layer["objects"]
        if obj.get("name")
    }


class ModelObject:
    def __init__(self, game=None, name="", **properties):
        self.game, self.name, self.properties = game, name, properties
        self.items, self.equipped, self.effects = [], {}, []

    def getGame(self):
        return self.game

    def getMap(self):
        return self.game.game_map

    def getName(self):
        return self.name

    def getTypeId(self):
        return self.properties.get("typeId", self.name)

    def getStringProperty(self, key):
        return str(self.properties.get(key, ""))

    def setStringProperty(self, key, value):
        self.properties[key] = value
        if key == "name":
            self.name = value

    def getNumericProperty(self, key):
        return self.properties.get(key, 0)

    def setNumericProperty(self, key, value):
        self.properties[key] = value

    def getBoolProperty(self, key):
        return bool(self.properties.get(key, False))

    def setBoolProperty(self, key, value):
        self.properties[key] = value

    def incProperty(self, key, value=1):
        self.properties[key] = self.getNumericProperty(key) + value

    def getObjectProperty(self, key):
        return self.properties.get(key)

    def setObjectProperty(self, key, value):
        self.properties[key] = value

    def getCoords(self):
        return SimpleNamespace(
            x=self.properties.get("posx", 0), y=self.properties.get("posy", 0), z=self.properties.get("posz", 0)
        )

    def moveTo(self, x, y, z):
        self.properties.update(posx=x, posy=y, posz=z)

    def setPosX(self, value):
        self.properties["posx"] = value

    def setPosY(self, value):
        self.properties["posy"] = value

    def setPosZ(self, value):
        self.properties["posz"] = value

    def setController(self, value):
        self.properties["controller"] = value

    def setNpc(self, value):
        self.properties["npc"] = value

    def setCaster(self, value):
        self.properties["caster"] = value

    def setVictim(self, value):
        self.properties["victim"] = value

    def isPlayer(self):
        return False

    def isAlive(self):
        return self.properties.get("hp", 1) > 0

    def getItems(self):
        return list(self.items)

    def getEquipped(self):
        return dict(self.equipped)

    def equipItem(self, slot, item):
        self.equipped[slot] = item

    def removeTag(self, tag):
        self.properties["tags"] = [value for value in self.properties.get("tags", []) if value != tag]

    def hasTag(self, tag):
        return tag in self.properties.get("tags", [])

    def getEffects(self):
        return list(self.effects)

    def setEffects(self, effects):
        self.effects = list(effects)

    def removeItem(self, predicate, allow_quest):
        if not callable(predicate):
            raise TypeError("Native removeItem requires predicate(item), allowQuest")
        for item in self.items:
            if predicate(item):
                self.items.remove(item)
                break

    def removeQuestItem(self, predicate):
        if not callable(predicate):
            raise TypeError("Native removeQuestItem requires predicate(item)")
        self.removeItem(predicate, True)

    def getEffectiveInteractions(self):
        return [
            self.game.createObject(entry.get("ref", entry.get("class"))) for entry in self.properties.get("actions", [])
        ]


class ModelPlayer(ModelObject):
    def __init__(self, game, **stats):
        super().__init__(game, "hero", gold=100, exp=0, hp=100, mana=100, affiliation="hero")
        self.stats = ModelObject(game, **{"strength": 5, "agility": 5, "intelligence": 5, **stats})
        self.base_stats = ModelObject(game, strength=99, agility=99, intelligence=99)
        self.items, self.quests, self.completed = [], [], []
        self.effects = []

    def isPlayer(self):
        return True

    def getStats(self):
        return self.stats

    def getBaseStats(self):
        return self.base_stats

    def getGold(self):
        return self.properties["gold"]

    def addGold(self, amount):
        self.properties["gold"] += amount

    def takeGold(self, amount):
        self.properties["gold"] -= amount

    def getExp(self):
        return self.properties["exp"]

    def addExp(self, amount):
        self.properties["exp"] += amount

    def getHp(self):
        return self.properties["hp"]

    def getHpMax(self):
        return 100

    def heal(self, amount):
        self.properties["hp"] = 100 if amount == 0 else min(100, self.getHp() + amount)

    def healProc(self, amount):
        self.heal(int(100 * amount))

    def countItems(self, type_id):
        return sum(item.getTypeId() == type_id for item in self.items)

    def getItems(self):
        return list(self.items)

    def addItem(self, item):
        self.items.append(self.game.createObject(item) if isinstance(item, str) else item)

    def removeItem(self, predicate, allow_quest):
        if not callable(predicate):
            raise TypeError("Native removeItem requires predicate(item), allowQuest")
        for item in self.items:
            if predicate(item):
                self.items.remove(item)
                break

    def removeQuestItem(self, predicate):
        if not callable(predicate):
            raise TypeError("Native removeQuestItem requires predicate(item)")
        self.removeItem(predicate, True)

    def addEffect(self, effect):
        self.effects.append(effect)

    def setHp(self, value):
        self.properties["hp"] = value

    def setMana(self, value):
        self.properties["mana"] = value

    def addMana(self, value):
        self.properties["mana"] = 100 if value == 0 else min(100, self.properties["mana"] + value)

    def getQuests(self):
        return list(self.quests)

    def getCompletedQuests(self):
        return list(self.completed)

    def addQuest(self, quest_id):
        self.quests.append(self.game.createObject(quest_id))

    def checkQuests(self):
        for quest in list(self.quests):
            if quest.isCompleted():
                quest.onComplete()
                self.quests.remove(quest)
                self.completed.append(quest)


class ModelMap(ModelObject):
    def __init__(self, game):
        super().__init__(game, "candlekeep")
        self.objects = {}
        self.navigation_edges = set()
        self.registered_triggers = []

    def getPlayer(self):
        return self.game.player

    def getObjects(self):
        return list(self.objects.values())

    def getObjectByName(self, name):
        return self.objects.get(name)

    def addObjectByName(self, name, coords):
        obj = self.game.createObject(name)
        obj.moveTo(coords.x, coords.y, coords.z)
        self.objects[name] = obj
        return obj

    def removeObject(self, obj):
        self.objects.pop(obj.getName(), None)

    def addObject(self, obj):
        self.objects[obj.getName()] = obj

    def unregisterNavigationEdgesForObject(self, name):
        self.navigation_edges = {edge for edge in self.navigation_edges if edge[2] != name}

    @staticmethod
    def coordsKey(coords):
        return coords.x, coords.y, coords.z

    def hasNavigationEdge(self, origin, target, name):
        return (self.coordsKey(origin), self.coordsKey(target), name) in self.navigation_edges

    def registerNavigationEdge(self, origin, target, _enabled, _bidirectional, _cost, name):
        self.navigation_edges.add((self.coordsKey(origin), self.coordsKey(target), name))

    def canStep(self, *_args):
        return True

    def getEventHandler(self):
        return self

    def registerTrigger(self, trigger):
        self.registered_triggers.append(trigger)


class CandlekeepModel:
    """Small native-shaped doubles executing the complete authored load function."""

    def __init__(self, **stats):
        self.types = {}
        self.trigger_types = {}
        self.gui = Mock()
        self.choice_answers, self.choice_requests = [], []
        self.reader_requests = []
        self.game_map = ModelMap(self)
        self.player = ModelPlayer(self, **stats)
        self.resources = {**readDocument("config.json"), **readDocument("dialog.json")}
        api = ModuleType("game")
        for name in (
            "CEvent",
            "CDialog",
            "CQuest",
            "CTrigger",
            "CBuilding",
            "CCreature",
            "CMonsterController",
            "CScroll",
        ):
            setattr(api, name, type(name, (ModelObject,), {}))
        self.native_types = {"CCreature": api.CCreature}

        def register(_context):
            def decorate(cls):
                self.types[cls.__name__] = cls
                return cls

            return decorate

        def trigger(_context, event_name, object_name):
            def decorate(cls):
                self.types[cls.__name__] = cls
                self.trigger_types[(event_name, object_name)] = cls
                return cls

            return decorate

        def claimOnce(game_map, flag):
            if game_map.getBoolProperty(flag):
                return False
            game_map.setBoolProperty(flag, True)
            return True

        api.register, api.trigger = register, trigger
        api.mapQuest = lambda *_args: lambda cls: cls
        api.claim_once = claimOnce
        api.Coords = lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)
        installHookFlows(api)
        api.showReader = lambda *_args: self.reader_requests.append(_args)

        def choose(_game, title, rows, _action):
            self.choice_requests.append((title, rows))
            answer = self.choice_answers.pop(0) if self.choice_answers else ""
            return answer if any(row["id"] == answer and row.get("enabled", True) for row in rows) else ""

        api.choose = choose
        namespace = {}
        with patch.dict(sys.modules, game=api):
            exec(
                compile((MAP_ROOT / "script.py").read_text(encoding="utf-8"), "candlekeep/script.py", "exec"), namespace
            )
            namespace["load"](None, self)
        self.namespace = namespace
        for name in self.resources:
            entry = self.resources[name]
            if entry.get("class") in {"CandlekeepContainer", "CandlekeepPortal"} or name in namespace["NPC_IDS"]:
                self.game_map.objects[name] = self.createObject(name)
        self.createObject("candlekeepStart").onEnter(SimpleNamespace(getCause=lambda: self.player))

    def getMap(self):
        return self.game_map

    def getGuiHandler(self):
        return self.gui

    def createObject(self, name):
        entry = self.resources.get(name, {})
        class_name = entry.get("class", name)
        cls = self.types.get(class_name, self.native_types.get(class_name, ModelObject))
        obj = cls(self, name, typeId=name, **entry.get("properties", {}))
        for value in entry.get("properties", {}).get("items", []):
            obj.items.append(self.createObject(value.get("ref", value.get("class"))))
        for slot, value in entry.get("properties", {}).get("equipped", {}).items():
            item = self.createObject(value.get("ref", value.get("class")))
            obj.items.append(item)
            obj.equipped[slot] = item
        return obj

    def dialog(self, name):
        return self.createObject(name + "Dialog")

    def enter(self, name, cause=None):
        cls = self.trigger_types[("onEnter", name)]
        event = SimpleNamespace(getCause=lambda: cause or self.player)
        cls(self).trigger(self.game_map.getObjectByName(name), event)

    def rewardSnapshot(self):
        return self.player.getGold(), self.player.getExp(), sorted(item.getTypeId() for item in self.player.getItems())


class CandlekeepContentTest(unittest.TestCase):
    def testSixQuestIdsAndDialogIdsAreStableAndSelectable(self):
        config = readDocument("config.json")
        dialogs = readDocument("dialog.json")
        for actor in QUEST_KEYS:
            with self.subTest(quest=actor):
                quest = config[actor + "Quest"]
                self.assertEqual("CandlekeepQuest", quest["class"])
                self.assertEqual(actor, quest["properties"]["questKey"])
                self.assertTrue(quest["properties"]["description"].strip())
                self.assertIn(actor + "Dialog", dialogs)
        self.assertIn("candlekeep", {path.name for path in (ROOT / "res/maps").iterdir() if path.is_dir()})

    def testEachMapResourceHasAnExplicitCmakeCopyRule(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        for name in ("config.json", "dialog.json", "map.json", "script.py"):
            self.assertIn(f"configure_file(res/maps/candlekeep/{name} maps/candlekeep/{name}", cmake)

    def testOnlyRealPlayerSpawnIsAuthoredAndActorsAreUnique(self):
        document, config = readDocument("map.json"), readDocument("config.json")
        for key in ("x", "y", "z"):
            self.assertIn(key, document["properties"])
        named = [
            obj["name"]
            for layer in document["layers"]
            if layer["type"] == "objectgroup"
            for obj in layer["objects"]
            if obj.get("name")
        ]
        self.assertEqual(len(named), len(set(named)))
        forbidden = {"Sorcerer", "Warrior", "Assasin", "Inquisitor", "Wayfarer"}
        for name, (obj, _level) in authoredObjects().items():
            definition = config.get(name, {})
            self.assertNotIn(definition.get("ref"), forbidden, name)
            self.assertNotIn(obj.get("type"), forbidden, name)
            self.assertNotEqual("CPlayer", definition.get("class"), name)

    def testEveryAuthoredInteractionIsReachableThroughWalkableFloorsAndDeclaredDoors(self):
        document, config = readDocument("map.json"), readDocument("config.json")
        tile_types = document["tilesets"][0]["tileproperties"]
        global_tiles = json.loads((ROOT / "res/config/tiles.json").read_text(encoding="utf-8"))
        walkable = set()
        for layer in document["layers"]:
            if layer["type"] != "tilelayer":
                continue
            width, level = layer["width"], int(layer["properties"]["level"])
            for offset, gid in enumerate(layer["data"]):
                tile_id = tile_types[str(gid - 1)]["type"] if gid else layer["properties"]["default"]
                if global_tiles[tile_id]["properties"].get("canStep", False):
                    walkable.add((offset % width, offset // width, level))
        objects = authoredObjects()
        edges = {}
        for name, (obj, level) in objects.items():
            properties = config[name].get("properties", {})
            if config[name].get("class") != "CandlekeepPortal":
                continue
            origin = (int(obj["x"] // 32), int(obj["y"] // 32), level)
            target = tuple(properties["target" + axis] for axis in ("X", "Y", "Z"))
            self.assertIn(origin, walkable, (name, "blocked origin"))
            self.assertIn(target, walkable, (name, "blocked destination"))
            edges.setdefault(origin, set()).add(target)
        start = tuple(int(document["properties"][axis]) for axis in ("x", "y", "z"))
        self.assertIn(start, walkable)
        queue, reached = deque([start]), {start}
        while queue:
            x, y, z = queue.popleft()
            adjacent = {(x + dx, y + dy, z) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
            for destination in (adjacent | edges.get((x, y, z), set())) & walkable - reached:
                reached.add(destination)
                queue.append(destination)
        for name, (obj, level) in objects.items():
            destination = (int(obj["x"] // 32), int(obj["y"] // 32), level)
            self.assertIn(destination, reached, (name, destination, "unreachable authored interaction"))

    def testIndependentSourceLedgerHasImplementationsAndDeclaredWitnesses(self):
        from tests.gameplay_routes_candlekeep import CASES

        ledger = json.loads((ROOT / "tests/fixtures/candlekeep_interactions.json").read_text(encoding="utf-8"))
        records = ledger["interactions"]
        self.assertTrue(records)
        self.assertEqual(len(records), len({entry["id"] for entry in records}))
        branches = {branch for case in CASES for branch in case.branches}
        objects = authoredObjects()
        dialogs = readDocument("dialog.json")
        sources = {entry["id"] for entry in ledger["sources"]}
        for entry in records:
            with self.subTest(interaction=entry["id"]):
                self.assertTrue(entry["sourceIds"])
                self.assertLessEqual(set(entry["sourceIds"]), sources)
                self.assertTrue(entry["conditions"])
                self.assertTrue(entry["outcomes"])
                self.assertIn(entry["objectId"], objects)
                if entry["dialogId"]:
                    self.assertIn(entry["dialogId"], dialogs)
                self.assertTrue(entry["branches"])
                self.assertFalse(
                    set(entry["branches"]) - branches, "Source interaction lacks a declared route obligation"
                )

    def testEveryDialogActionAndConditionHasAnActualMethod(self):
        tree = ast.parse((MAP_ROOT / "script.py").read_text(encoding="utf-8"))
        methods = {
            method.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "CandlekeepDialog"
            for method in node.body
            if isinstance(method, ast.FunctionDef)
        }
        for dialog_id, definition in readDocument("dialog.json").items():
            for node in self.walkJson(definition):
                for field in ("action", "condition", "afterCondition"):
                    if node.get(field):
                        self.assertIn(node[field], methods, (dialog_id, field, node[field]))

    @staticmethod
    def walkJson(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from CandlekeepContentTest.walkJson(child)
        elif isinstance(value, list):
            for child in value:
                yield from CandlekeepContentTest.walkJson(child)


class CandlekeepModelTest(unittest.TestCase):
    def routeDriver(self):
        model = CandlekeepModel(strength=18, agility=18)
        for name, (obj, level) in authoredObjects().items():
            actor = model.game_map.getObjectByName(name)
            if actor:
                actor.moveTo(int(obj["x"] // 32), int(obj["y"] // 32), level)
        choices, movement = [], []

        def position(actor):
            coords = actor.getCoords()
            return coords.x, coords.y, coords.z

        def navigateTo(name):
            destination = position(model.game_map.getObjectByName(name))
            movement.append((position(model.player), destination))
            model.player.moveTo(*destination)

        def choose(dialog_id, action):
            dialog = model.createObject(dialog_id)
            actor = model.game_map.getObjectByName(dialog.actorId())
            self.assertEqual(
                position(actor), position(model.player), f"{dialog_id}.{action} requires an authored approach"
            )
            choices.append((dialog.actorId(), action, position(model.player)))
            return getattr(dialog, action)()

        driver = SimpleNamespace(
            test=self,
            case=SimpleNamespace(branches=("candlekeep.training.accept",)),
            player=model.player,
            game_map=model.game_map,
            navigateTo=navigateTo,
            choose=choose,
            call=lambda actor, method, *args: getattr(actor, method)(*args),
            object=lambda name, required=True: model.game_map.getObjectByName(name),
            condition=lambda dialog_id, method: getattr(model.createObject(dialog_id), method)(),
            gold=model.player.getGold,
            count=model.player.countItems,
            flag=model.game_map.getBoolProperty,
            string=model.game_map.getStringProperty,
            check=lambda branch, condition, **_evidence: self.assertTrue(condition, branch),
            startMap=lambda name: self.assertEqual("candlekeep", name),
            saveAndReload=Mock(),
        )
        return driver, model, choices, movement

    def testTrainingRouteReturnsToObeAfterCombatBeforeProgressAndExitChoices(self):
        from tests.gameplay_routes_candlekeep import training

        for abandon in (False, True):
            with self.subTest(abandon=abandon):
                driver, model, choices, movement = self.routeDriver()
                combat_origins = []

                def fight(name):
                    origin = model.player.getCoords()
                    combat_origins.append((origin.x, origin.y, origin.z))
                    model.game_map.removeObject(model.game_map.getObjectByName(name))

                def waitTurns(_limit, predicate):
                    for number in range(2, 7):
                        actor = model.game_map.getObjectByName("trainingFoe" + str(number))
                        if actor:
                            model.game_map.removeObject(actor)
                    self.assertTrue(predicate())

                driver.fight, driver.waitTurns = fight, waitTurns
                training(driver, abandon=abandon)
                self.assertTrue(movement)
                obe_choices = [choice for choice in choices if choice[0] == "obe"]
                self.assertEqual("forceExitTraining", obe_choices[-1][1])
                if abandon:
                    driver.saveAndReload.assert_called_once()
                else:
                    self.assertEqual(2, len(combat_origins))
                    self.assertNotEqual(obe_choices[0][2], combat_origins[0])
                    self.assertEqual(2, sum(choice[1] == "trainingRound" for choice in obe_choices))

    def testForcedContainerRouteReapproachesLootAfterGuardCombat(self):
        from tests.gameplay_routes_candlekeep import container

        driver, model, choices, _movement = self.routeDriver()

        def clearWatch(_driver):
            model.player.moveTo(4, 2, 1)

        with patch("tests.gameplay_routes_candlekeep.clearWatch", side_effect=clearWatch):
            container(driver, "priestChest", force=True)
        self.assertEqual(["forceContainer", "stealContainer"], [choice[1] for choice in choices])
        self.assertTrue(model.game_map.getBoolProperty("candlekeepLooted_priestChest"))

    def testQuestRewardAndClinicGiftTransferTheActualOwnersItemsWithoutCloning(self):
        model = CandlekeepModel(intelligence=12)
        phlydia = model.game_map.getObjectByName("phlydia")
        gem = next(item for item in phlydia.getItems() if item.getTypeId() == "candlekeepLynxEyeGem")
        model.player.addItem("candlekeepHistoryHalruaa")
        model.dialog("phlydia").acceptQuest()
        model.dialog("phlydia").returnQuest()
        self.assertIn(gem, model.player.getItems())
        self.assertNotIn(gem, phlydia.getItems())
        for gift_first in (True, False):
            with self.subTest(gift_first=gift_first):
                model = CandlekeepModel(agility=100)
                priest = model.game_map.getObjectByName("clinicPriest")
                original = {id(item) for item in priest.getItems() if item.getTypeId() == "candlekeepHealingPotion"}
                self.assertEqual(2, len(original))
                dialog = model.dialog("clinicPriest")
                first, second = (
                    (dialog.acceptPotion, dialog.pickpocket) if gift_first else (dialog.pickpocket, dialog.acceptPotion)
                )
                self.assertTrue(first())
                self.assertTrue(second())
                self.assertEqual(
                    original,
                    {id(item) for item in model.player.getItems() if item.getTypeId() == "candlekeepHealingPotion"},
                )
                self.assertFalse(priest.getItems())
                self.assertFalse(dialog.acceptPotion())
                self.assertFalse(dialog.pickpocket())

    def testRetainedDialogsCannotSettleErrandsOrGrantItemsAfterTheNpcDies(self):
        model = CandlekeepModel(intelligence=12, agility=100)
        fuller = model.dialog("fuller")
        fuller.acceptQuest()
        model.player.addItem("candlekeepBolts")
        actor = model.game_map.getObjectByName("fuller")
        actor.properties["hp"] = 0
        model.game_map.removeObject(actor)
        before = model.rewardSnapshot()
        self.assertFalse(fuller.returnQuest())
        self.assertFalse(fuller.pickpocket())
        self.assertEqual(before, model.rewardSnapshot())
        self.assertEqual("active", model.game_map.getStringProperty("candlekeep_fullerStage"))
        clinic = model.dialog("clinicPriest")
        actor = model.game_map.getObjectByName("clinicPriest")
        actor.properties["hp"] = 0
        model.game_map.removeObject(actor)
        self.assertFalse(clinic.acceptPotion())
        self.assertEqual(before, model.rewardSnapshot())
        for removed in (False, True):
            with self.subTest(gorionRemoved=removed):
                model = CandlekeepModel()
                gorion = model.dialog("gorion")
                actor = model.game_map.getObjectByName("gorion")
                actor.properties["hp"] = 0
                if removed:
                    model.game_map.removeObject(actor)
                model.player.setHp(47)
                readers_before = list(model.reader_requests)
                gorion.leaveCandlekeep()
                self.assertFalse(model.game_map.getBoolProperty("candlekeepDeparted"))
                self.assertFalse(model.game_map.getBoolProperty("candlekeepGorionAdvice"))
                self.assertFalse(model.game_map.getBoolProperty("candlekeepEpilogueShown"))
                self.assertEqual(47, model.player.getHp())
                self.assertEqual(readers_before, model.reader_requests)

    def testTempleHealChargesExactSourcePriceOnlyForAnActualHealthDeficit(self):
        model = CandlekeepModel()
        dialog, before = model.dialog("templePriest"), model.rewardSnapshot()
        self.assertFalse(dialog.healAtTemple())
        self.assertEqual(before, model.rewardSnapshot())
        model.player.setHp(47)
        gold = model.player.getGold()
        self.assertTrue(dialog.healAtTemple())
        self.assertEqual(gold - 50, model.player.getGold())
        self.assertEqual(100, model.player.getHp())

    def testIdentifyScrollConsumesOnlyAfterIdentificationAndThenCannotCompleteTheErrand(self):
        model = CandlekeepModel()
        model.enter("firebead")
        model.dialog("tethtoril").deliverScroll()
        scroll = next(item for item in model.player.getItems() if item.getTypeId() == "candlekeepIdentifyScroll")
        event = SimpleNamespace(getCause=lambda: model.player)
        self.assertFalse(scroll.onUse(event))
        self.assertIn(scroll, model.player.getItems())
        dagger = model.createObject("candlekeepDaggerPlusOne")
        model.player.addItem(dagger)
        self.assertTrue(scroll.onUse(event))
        self.assertNotIn(scroll, model.player.getItems())
        self.assertFalse(dagger.getBoolProperty("plugin_candlekeepUnidentified"))
        self.assertFalse(model.dialog("firebead").canReturnQuest())
        self.assertEqual("active", model.game_map.getStringProperty("candlekeep_firebeadStage"))
        self.assertFalse(scroll.onUse(event), "An unowned consumed scroll cannot run its effect twice")
        self.assertEqual(1, model.game_map.getNumericProperty("candlekeepIdentifications"))

    def testArmorScrollCommitsOneNativeEffectAndUnsupportedVisionKeepsItsOwnedScroll(self):
        model = CandlekeepModel()
        armor, vision = model.createObject("candlekeepArmorScroll"), model.createObject("candlekeepInfravisionScroll")
        model.player.addItem(armor)
        model.player.addItem(vision)
        event = SimpleNamespace(getCause=lambda: model.player)
        self.assertTrue(armor.onUse(event))
        self.assertFalse(armor.onUse(event))
        self.assertEqual(1, len(model.player.getEffects()))
        self.assertEqual("candlekeepArmorEffect", model.player.getEffects()[0].getTypeId())
        self.assertNotIn(armor, model.player.getItems())
        self.assertFalse(vision.onUse(event))
        self.assertIn(vision, model.player.getItems())
        self.assertEqual(1, len(model.player.getEffects()))

    def testAuditedStockSelectionAndQuickPurchaseShareFiniteCountersAndExactPrices(self):
        model = CandlekeepModel()
        player, dialog = model.player, model.dialog("templePriest")
        rows = json.loads(dialog.getStringProperty("shopEntries").removeprefix("candlekeep-json:"))
        row = next(row for row in rows if row["itemId"] == "candlekeepHealingPotion")
        self.assertEqual((112, 20), (row["price"], row["limit"]))
        player.properties["gold"] = 10000
        model.choice_answers.append(row["id"])
        dialog.browseStock()
        self.assertEqual(10000 - 112, player.getGold())
        self.assertEqual(1, player.countItems(row["itemId"]))
        for _ in range(row["limit"] - 1):
            self.assertTrue(dialog.buyHealingPotion())
        before = model.rewardSnapshot()
        self.assertFalse(dialog.buyHealingPotion())
        dialog.setStringProperty("selectedStock", row["id"])
        self.assertFalse(dialog.buyStock())
        self.assertEqual(before, model.rewardSnapshot())
        self.assertEqual(
            row["limit"], model.game_map.getNumericProperty("candlekeepStockBought_templePriest_" + row["id"])
        )
        self.assertFalse(
            model.dialog("winthrop").buyHealingPotion(), "An absent stock row must not fall back to an invented offer"
        )

    def testStockInsufficientMoneyCancellationAndBoltsBundlePreserveExactOwnership(self):
        model = CandlekeepModel()
        temple, winthrop = model.dialog("templePriest"), model.dialog("winthrop")
        model.player.properties["gold"] = 111
        before = model.rewardSnapshot()
        self.assertFalse(temple.buyHealingPotion())
        self.assertEqual(before, model.rewardSnapshot())
        temple.browseStock()
        self.assertEqual(before, model.rewardSnapshot())
        self.assertEqual(4, len(model.choice_requests[-1][1]))
        before_gold = model.player.getGold()
        self.assertTrue(winthrop.buyBolts())
        self.assertEqual(before_gold - 1, model.player.getGold())
        bolts = next(item for item in model.player.getItems() if item.getTypeId() == "candlekeepBolts")
        self.assertEqual(20, bolts.getNumericProperty("plugin_candlekeepQuantity"))
        self.assertEqual(1, model.player.countItems("candlekeepBolts"))

    def testSelectedSaleUsesPredicateRemovalAndPaysOnlyTheSelectedOwnedItem(self):
        model = CandlekeepModel()
        first, second = model.createObject("candlekeepDagger"), model.createObject("candlekeepStarSapphire")
        first.setStringProperty("name", "firstItem")
        second.setStringProperty("name", "selectedItem")
        model.player.addItem(first)
        model.player.addItem(second)
        before = model.player.getGold()
        model.choice_answers.append("selectedItem")
        model.dialog("winthrop").sellItem()
        self.assertIn(first, model.player.getItems())
        self.assertNotIn(second, model.player.getItems())
        self.assertEqual(
            before + max(1, second.getNumericProperty("plugin_candlekeepSellPrice")), model.player.getGold()
        )

    def testInventoryDoubleRejectsItemObjectsUnsupportedByTheNativeBindings(self):
        model = CandlekeepModel()
        item = model.createObject("candlekeepBolts")
        model.player.addItem(item)
        with self.assertRaises(TypeError):
            model.player.removeQuestItem(item)
        with self.assertRaises(TypeError):
            model.player.removeItem(item, False)
        self.assertEqual([item], model.player.getItems())
        model.player.removeQuestItem(lambda candidate: candidate == item)
        self.assertEqual([], model.player.getItems())

    def testEachQuestConsumesItsObjectiveAndPaysExactlyOnce(self):
        expected_items = {
            "firebead": ["candlekeepHealingPotion"],
            "phlydia": ["candlekeepLynxEyeGem"],
        }
        for actor in QUEST_KEYS:
            with self.subTest(quest=actor):
                model = CandlekeepModel(intelligence=7)
                dialog, player, game_map = model.dialog(actor), model.player, model.game_map
                self.assertFalse(dialog.returnQuest(), "An unaccepted errand cannot pay")
                if actor == "dreppin":
                    model.enter(actor)
                    model.enter(actor)
                    self.assertTrue(dialog.questActive())
                else:
                    self.assertTrue(dialog.acceptQuest())
                self.assertFalse(dialog.acceptQuest(), "An accepted errand cannot duplicate its journal")
                self.assertFalse(dialog.returnQuest(), "The objective must be owned or the rats defeated")
                if actor == "reevor":
                    game_map.setNumericProperty("candlekeepRatsSlain", 5)
                else:
                    player.addItem(model.namespace["QUEST_ITEMS"][actor])
                before_gold, before_exp = player.getGold(), player.getExp()
                self.assertTrue(dialog.returnQuest())
                self.assertEqual(50, player.getExp() - before_exp)
                self.assertEqual({"hull": 10, "fuller": 10, "reevor": 5}.get(actor, 0), player.getGold() - before_gold)
                self.assertEqual(expected_items.get(actor, []), sorted(item.getTypeId() for item in player.getItems()))
                self.assertEqual([actor + "Quest"], [quest.getName() for quest in player.getCompletedQuests()])
                self.assertEqual([], player.getQuests())
                before = model.rewardSnapshot()
                self.assertFalse(dialog.returnQuest())
                self.assertEqual(before, model.rewardSnapshot())
                if actor == "firebead":
                    self.assertEqual(1, len(player.effects))
                    self.assertTrue(game_map.getBoolProperty("candlekeepFirebeadProtected"))
                if actor == "dreppin":
                    self.assertTrue(game_map.getBoolProperty("candlekeepNessaCured"))

    def testObjectiveCollectedBeforeAcceptanceSurvivesAcceptAndCompletion(self):
        for actor in QUEST_KEYS:
            if actor == "reevor":
                continue
            with self.subTest(quest=actor):
                model = CandlekeepModel()
                item_id = model.namespace["QUEST_ITEMS"][actor]
                model.player.addItem(item_id)
                dialog = model.dialog(actor)
                if actor == "dreppin":
                    model.enter(actor)
                    model.enter(actor)
                    self.assertTrue(dialog.questActive())
                else:
                    self.assertTrue(dialog.acceptQuest())
                self.assertEqual(1, model.player.countItems(item_id))
                self.assertTrue(dialog.returnQuest())
                self.assertEqual(0, model.player.countItems(item_id))

    def testSocialReactionUsesCurrentNativeIntelligenceAndStandingAtExactBoundaries(self):
        for score, low, high in ((6, True, False), (7, False, False), (11, False, False), (12, False, True)):
            with self.subTest(score=score):
                model = CandlekeepModel(intelligence=score - 2)
                model.game_map.setNumericProperty("candlekeepStanding", 2)
                dialog = model.dialog("hull")
                self.assertEqual(score, dialog.socialScore())
                self.assertEqual(low, dialog.lowReaction())
                self.assertEqual(high, dialog.highReaction())
                model.player.addItem("candlekeepHullSword")
                dialog.acceptQuest()
                gold = model.player.getGold()
                dialog.returnQuest()
                self.assertEqual(20 if high else 10, model.player.getGold() - gold)

    def testPhlydiaRewardBoundaryAndFullerUniqueDaggerAreSharedAcrossTheftAndQuest(self):
        for score in (6, 7):
            model = CandlekeepModel(intelligence=score)
            model.player.addItem("candlekeepHistoryHalruaa")
            dialog = model.dialog("phlydia")
            dialog.acceptQuest()
            dialog.returnQuest()
            self.assertEqual(int(score >= 7), model.player.countItems("candlekeepLynxEyeGem"))
        for theft_first in (False, True):
            with self.subTest(theft_first=theft_first):
                model = CandlekeepModel(intelligence=12, agility=100)
                fuller = model.dialog("fuller")
                if theft_first:
                    self.assertTrue(fuller.pickpocket())
                model.player.addItem("candlekeepBolts")
                fuller.acceptQuest()
                fuller.returnQuest()
                if not theft_first:
                    self.assertFalse(
                        fuller.canPickpocket(), "Quest reward removes Fuller's shared dagger from his pockets"
                    )
                    self.assertFalse(fuller.pickpocket())
                self.assertEqual(1, model.player.countItems("candlekeepDaggerPlusOne"))
                self.assertTrue(model.game_map.getBoolProperty("candlekeepFullerDaggerClaimed"))
                self.assertFalse(fuller.pickpocket())

    def testLockAndForceChecksUseCurrentAgilityAndStrengthAtTheAuthoredThreshold(self):
        for stat, condition, action, threshold in (
            ("agility", "canUnlock", "unlockContainer", "lockAgility"),
            ("strength", "canForce", "forceContainer", "forceStrength"),
        ):
            for delta in (-1, 0):
                with self.subTest(stat=stat, delta=delta):
                    model = CandlekeepModel()
                    actor = model.game_map.getObjectByName("innSapphireDrawer")
                    actor.setBoolProperty("owned", False)
                    actor.setBoolProperty("locked", True)
                    model.player.stats.setNumericProperty(stat, actor.getNumericProperty(threshold) + delta)
                    dialog = model.dialog("innSapphireDrawer")
                    self.assertEqual(delta == 0, getattr(dialog, condition)())
                    self.assertEqual(delta == 0, getattr(dialog, action)())
                    self.assertEqual(delta != 0, actor.getBoolProperty("locked"))

    def testOwnedLootAndPickpocketUseNativeAgilityAndSummonRealGuardObjects(self):
        for delta in (-1, 0):
            with self.subTest(delta=delta):
                model = CandlekeepModel()
                actor = model.game_map.getObjectByName("clinicPriest")
                threshold = actor.getNumericProperty("plugin_candlekeepTheftThreshold") or 16
                model.player.stats.setNumericProperty("agility", threshold + delta)
                dialog = model.dialog("clinicPriest")
                self.assertEqual(delta == 0, dialog.pickpocket())
                self.assertEqual(delta < 0, model.game_map.getBoolProperty("candlekeepGuardsAlerted"))
                if delta < 0:
                    self.assertEqual(-2, model.game_map.getNumericProperty("candlekeepStanding"))
                    self.assertIsNotNone(model.game_map.getObjectByName("candlekeepWatch1"))
        model = CandlekeepModel(agility=100)
        actor = model.game_map.getObjectByName("priestChest")
        actor.setBoolProperty("locked", False)
        actor.setBoolProperty("owned", True)
        actor.setBoolProperty("alwaysGuard", True)
        dialog = model.dialog("priestChest")
        self.assertFalse(dialog.openContainer())
        self.assertTrue(dialog.stealContainer())
        self.assertTrue(model.game_map.getBoolProperty("candlekeepGuardsAlerted"))
        before = model.rewardSnapshot()
        self.assertFalse(dialog.stealContainer())
        self.assertEqual(before, model.rewardSnapshot())
        self.assertEqual(1, model.game_map.getNumericProperty("candlekeepCrimes"))

    def testHullChestRequiresAnActiveErrandAndCannotDuplicateEitherObjective(self):
        model = CandlekeepModel()
        dialog = model.dialog("hullChest")
        self.assertFalse(dialog.openContainer())
        model.enter("dreppin")
        model.enter("dreppin")
        self.assertTrue(dialog.openContainer())
        self.assertEqual(1, model.player.countItems("candlekeepAntidote"))
        self.assertEqual(1, model.player.countItems("candlekeepHullSword"))
        before = model.rewardSnapshot()
        self.assertFalse(dialog.openContainer())
        self.assertEqual(before, model.rewardSnapshot())

    def testThirtyFirebeadConversationsHaveOneExactReward(self):
        model = CandlekeepModel()
        dialog, before = model.dialog("firebead"), model.player.getGold()
        for _ in range(35):
            dialog.talk()
        self.assertEqual(
            before, model.player.getGold(), "Repeated options inside one conversation cannot farm openings"
        )
        for _ in range(29):
            model.enter("firebead")
        self.assertEqual(before, model.player.getGold())
        model.enter("firebead")
        self.assertEqual(before + 300, model.player.getGold())
        for _ in range(5):
            dialog.talk()
        self.assertEqual(before + 300, model.player.getGold())

    def testNpcEntryAutomaticallyAcceptsAuthoredErrandsButDreppinFirstGivesHisBookHint(self):
        model = CandlekeepModel()
        for actor in ("firebead", "phlydia", "hull", "reevor"):
            model.enter(actor)
            self.assertEqual("active", model.game_map.getStringProperty("candlekeep_" + actor + "Stage"))
            model.enter(actor)
            self.assertEqual(1, sum(quest.getName() == actor + "Quest" for quest in model.player.getQuests()))
        model.enter("dreppin")
        self.assertEqual("notStarted", model.game_map.getStringProperty("candlekeep_dreppinStage"))
        self.assertTrue(model.game_map.getBoolProperty("candlekeepDreppinBookHint"))
        model.enter("dreppin")
        self.assertEqual("active", model.game_map.getStringProperty("candlekeep_dreppinStage"))

    def testTwoTrainingDeclinesCloseBothGateStateAndNavigation(self):
        model = CandlekeepModel()
        gate = model.dialog("gatewarden")
        self.assertFalse(gate.canDeclineSecond())
        self.assertFalse(gate.closeTrainingGate())
        self.assertEqual(0, model.game_map.getNumericProperty("candlekeepGatewardenDeclines"))
        self.assertTrue(gate.declineTraining())
        self.assertTrue(gate.canDeclineSecond())
        self.assertTrue(gate.trainingAvailable())
        self.assertTrue(gate.declineTraining())
        self.assertFalse(gate.trainingAvailable())
        self.assertFalse(gate.acceptTraining())
        self.assertTrue(model.game_map.getBoolProperty("candlekeepTrainingClosed"))
        self.assertFalse(model.game_map.getBoolProperty("candlekeepTrainingAccepted"))
        self.assertFalse(model.game_map.getObjectByName("trainingEntrance").getBoolProperty("waypoint"))

    def testObeRequiresRealEnemyDefeatsAndRestoresHeroAndTemporaryActors(self):
        model = CandlekeepModel()
        gate, obe, player = model.dialog("gatewarden"), model.dialog("obe"), model.player
        self.assertFalse(obe.beginTraining())
        gate.acceptTraining()
        player.setHp(47)
        player.setMana(33)
        self.assertTrue(obe.beginTraining())
        self.assertFalse(obe.beginTraining())
        self.assertEqual("candlekeepTraining", player.getStringProperty("affiliation"))
        for name in model.namespace["TRAINING_ALLIES"]:
            self.assertIsNotNone(model.game_map.getObjectByName(name))
            self.assertTrue(model.game_map.getBoolProperty("candlekeepTrainingParticipated_" + name))
        self.assertFalse(obe.trainingRound())
        self.assertFalse(obe.finishTraining())
        for round_number in (1, 2):
            self.assertEqual(round_number, model.game_map.getNumericProperty("candlekeepTrainingRound"))
            for number in range(1, 7):
                model.game_map.objects.pop("trainingFoe" + str(number))
            self.assertTrue(obe.trainingRound())
        self.assertEqual("completed", model.game_map.getStringProperty("candlekeep_trainingStage"))
        self.assertEqual("hero", player.getStringProperty("affiliation"))
        self.assertEqual((47, 33), (player.getHp(), player.getNumericProperty("mana")))
        self.assertFalse(any(name in model.game_map.objects for name in model.namespace["TRAINING_ALLIES"]))
        self.assertFalse(obe.finishTraining())

    def testAbandoningTrainingAndDepartureNeverLeavePracticeAlliesOrAlterQuestHistory(self):
        for leave in (False, True):
            with self.subTest(departure=leave):
                model = CandlekeepModel()
                model.dialog("hull").acceptQuest()
                model.dialog("gatewarden").acceptTraining()
                model.dialog("obe").beginTraining()
                if leave:
                    model.dialog("gorion").leaveCandlekeep()
                    self.assertTrue(model.game_map.getBoolProperty("candlekeepDeparted"))
                    self.assertTrue(model.game_map.getBoolProperty("candlekeepEpilogueShown"))
                else:
                    model.dialog("obe").forceExitTraining()
                    self.assertTrue(model.game_map.getBoolProperty("candlekeepTrainingForcedExit"))
                self.assertEqual("abandoned", model.game_map.getStringProperty("candlekeep_trainingStage"))
                self.assertEqual("hero", model.player.getStringProperty("affiliation"))
                self.assertEqual(["hullQuest"], [quest.getName() for quest in model.player.getQuests()])
                self.assertEqual([], model.player.getCompletedQuests())
                self.assertFalse(any(name.startswith("trainingFoe") for name in model.game_map.objects))

    def testTrainingTimerRetainsItsSavedBudgetAndForcesCleanupAtExactly120Turns(self):
        model = CandlekeepModel()
        model.dialog("gatewarden").acceptTraining()
        model.dialog("obe").beginTraining()
        callback = model.types["CandlekeepTrainingTimerTrigger"](model)
        obe = model.game_map.getObjectByName("obe")
        for _ in range(119):
            callback.trigger(obe, None)
        self.assertEqual(119, model.game_map.getNumericProperty("candlekeepTrainingTurns"))
        self.assertEqual(120, model.game_map.getNumericProperty("candlekeepTrainingTurnLimit"))
        self.assertFalse(model.game_map.getBoolProperty("candlekeepTrainingTimedOut"))
        callback.trigger(obe, None)
        self.assertTrue(model.game_map.getBoolProperty("candlekeepTrainingTimedOut"))
        self.assertEqual("abandoned", model.game_map.getStringProperty("candlekeep_trainingStage"))
        self.assertFalse(any(name.startswith("trainingFoe") for name in model.game_map.objects))
        callback.trigger(obe, None)
        self.assertEqual(120, model.game_map.getNumericProperty("candlekeepTrainingTurns"))

    def testPortalDestructionUnregistersOnlyItsOwnPublishedNavigationEdge(self):
        model = CandlekeepModel()
        first, second = (model.game_map.getObjectByName(name) for name in ("innEntrance", "innExit"))
        first.publishEdge()
        second.publishEdge()
        owners = {edge[2] for edge in model.game_map.navigation_edges}
        self.assertEqual({"innEntrance", "innExit"}, owners)
        first.onDestroy(None)
        self.assertEqual({"innExit"}, {edge[2] for edge in model.game_map.navigation_edges})

    def testNativeHeroDefeatCleanupContractRestoresTrainingStateAndEquipment(self):
        for observer_first in (True, False):
            with self.subTest(observer_first=observer_first):
                model = CandlekeepModel()
                original, bagged = model.createObject("candlekeepDagger"), model.createObject("candlekeepStarSapphire")
                original.setStringProperty("name", "originalBlade")
                bagged.setStringProperty("name", "originalBagItem")
                model.player.addItem(original)
                model.player.addItem(bagged)
                model.player.equipItem("0", original)
                model.dialog("gatewarden").acceptTraining()
                model.player.setHp(47)
                model.player.setMana(33)
                model.dialog("obe").beginTraining()
                temporary = model.createObject("candlekeepDagger")
                temporary.setStringProperty("name", "loanedBlade")
                temporary.setBoolProperty("plugin_candlekeepTemporary", True)
                temporary.properties["tags"] = ["cursed"]
                model.player.addItem(temporary)
                model.player.equipItem("0", temporary)
                # CFightHandler transfers unequipped nonquest loot before native destroy observers.
                for original_item in (original, bagged):
                    model.player.removeItem(lambda item: item == original_item, False)
                    model.game_map.getObjectByName("trainingFoe1").items.append(original_item)
                model.player.setHp(0)
                observer = model.types["CandlekeepTrainingDefeatTrigger"](model)
                if observer_first:
                    observer.trigger(model.player, None)
                    model.player.setHp(1)
                else:
                    model.player.setHp(1)
                    observer.trigger(model.player, None)
                self.assertTrue(model.game_map.getBoolProperty("candlekeepTrainingDefeatPending"))
                self.assertEqual("active", model.game_map.getStringProperty("candlekeep_trainingStage"))
                model.types["CandlekeepTrainingTimerTrigger"](model).trigger(
                    model.game_map.getObjectByName("obe"), None
                )
                self.assertTrue(model.game_map.getBoolProperty("candlekeepTrainingDefeat"))
                self.assertFalse(model.game_map.getBoolProperty("candlekeepTrainingDefeatPending"))
                self.assertEqual("abandoned", model.game_map.getStringProperty("candlekeep_trainingStage"))
                self.assertEqual((47, 33), (model.player.getHp(), model.player.getNumericProperty("mana")))
                self.assertEqual(original, model.player.getEquipped()["0"])
                self.assertIn(bagged, model.player.getItems())
                self.assertNotIn(temporary, model.player.getItems())

    def testTrainingDefeatReclaimsOriginalPossessionsFromSummonedGuardWithoutDuplicatingThem(self):
        model = CandlekeepModel()
        original = model.createObject("candlekeepStarSapphire")
        original.setStringProperty("name", "originalTrainingPossession")
        model.player.addItem(original)
        model.player.setHp(47)
        model.dialog("gatewarden").acceptTraining()
        model.dialog("obe").beginTraining()
        model.dialog("arkanis").attack()
        guard = next(actor for actor in model.game_map.getObjects() if actor.getName().startswith("candlekeepWatch"))
        guard_item = model.createObject("candlekeepDagger")
        guard.items.append(guard_item)
        noncreature = model.game_map.getObjectByName("innEntrance")
        same_named_item = model.createObject("candlekeepStarSapphire")
        same_named_item.setStringProperty("name", original.getName())
        noncreature.items.append(same_named_item)
        # Mirror the native winner receiving the hero's nonquest loot before onDestroy.
        model.player.removeItem(lambda item: item == original, False)
        guard.items.append(original)
        model.player.setHp(0)
        model.types["CandlekeepTrainingDefeatTrigger"](model).trigger(model.player, None)
        self.assertIn(original, model.player.getItems())
        self.assertNotIn(original, guard.getItems())
        model.player.setHp(1)
        timer = model.types["CandlekeepTrainingTimerTrigger"](model)
        timer.trigger(model.game_map.getObjectByName("obe"), None)
        timer.trigger(model.game_map.getObjectByName("obe"), None)
        self.assertEqual("abandoned", model.game_map.getStringProperty("candlekeep_trainingStage"))
        self.assertEqual(47, model.player.getHp())
        self.assertEqual(1, model.player.getItems().count(original))
        self.assertEqual([guard_item], guard.getItems())
        self.assertIs(guard, model.game_map.getObjectByName(guard.getName()))
        self.assertEqual([same_named_item], noncreature.getItems())

    def testDepartureRestoresTrainingThenHealsOnceAndShowsOneEpilogue(self):
        model = CandlekeepModel()
        model.player.setHp(47)
        model.dialog("gatewarden").acceptTraining()
        model.dialog("obe").beginTraining()
        before_readers = len(model.reader_requests)
        model.dialog("gorion").leaveCandlekeep()
        self.assertEqual("abandoned", model.game_map.getStringProperty("candlekeep_trainingStage"))
        self.assertEqual(100, model.player.getHp())
        self.assertEqual(before_readers + 1, len(model.reader_requests))
        model.player.setHp(25)
        model.dialog("gorion").leaveCandlekeep()
        self.assertEqual(25, model.player.getHp(), "A repeated already-committed departure cannot grant another heal")
        self.assertEqual(before_readers + 1, len(model.reader_requests))

    def testSourceOnlyDefensiveContractsDoNotExemptUnknownProgressionCallbacks(self):
        from tests import gameplay_branch_catalog as catalog

        identities = {
            "res/maps/candlekeep/script.py:CandlekeepPortal.onDestroy",
            "res/maps/candlekeep/script.py:CandlekeepTrainingDefeatTrigger.trigger",
        }
        contracts = catalog.defensiveContracts()
        evidence = catalog.contractEvidence()
        for identity in identities:
            self.assertIn(identity, contracts)
            self.assertEqual("source-double", evidence[identity][0])
            self.assertTrue(evidence[identity][1].startswith("tests/test_candlekeep_content.py:CandlekeepModelTest."))
            self.assertNotIn(identity, catalog.sourceBranches())
        callback = "res/maps/candlekeep/script.py:UnreviewedQuest.complete"
        self.assertTrue(catalog.auditMappings({callback}, {}, contracts, set()))

    def testSelectedGuiOutcomesRemainExplicitlyPendingWithoutNativeBranchCredit(self):
        from tests import gameplay_branch_catalog as catalog
        from tests.gameplay_routes_candlekeep import PENDING_GAMEPLAY_OBLIGATIONS

        required = {
            "candlekeep.services.stockSelected",
            "candlekeep.services.drinkSelected",
            "candlekeep.services.serviceSelected",
            "candlekeep.services.saleSelected",
            "candlekeep.training.borrowSelected",
        }
        self.assertEqual(required, set(PENDING_GAMEPLAY_OBLIGATIONS))
        declared = {branch for case in catalog.getCases() for branch in case.branches}
        pending = catalog.pendingGameplayObligations()
        self.assertFalse(required & declared)
        self.assertFalse(required & set(catalog.defensiveContracts()))
        for branch in required:
            self.assertEqual(PENDING_GAMEPLAY_OBLIGATIONS[branch], pending[branch])
            self.assertIn(pending[branch]["callback"], catalog.sourceCallbacks())
            self.assertIn("pending", pending[branch]["reason"].lower())


if __name__ == "__main__":
    unittest.main()
