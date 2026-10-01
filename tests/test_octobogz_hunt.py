# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
import builtins
import importlib.util
import json
import re
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

    def getObjectProperty(self, name):
        return self.properties.get(name)

    def setObjectProperty(self, name, value):
        self.properties[name] = value

    def setCaster(self, actor):
        self.caster = actor

    def setVictim(self, actor):
        self.victim = actor

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
        self.stats = Properties()
        self.stats.properties.update(normalResist=10, shadowResist=0)

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

    def addAction(self, action):
        self.actions[action.getTypeId()] = action

    def getActions(self):
        return list(self.actions.values())

    def getEffectiveInteractions(self):
        return self.getActions()

    def getStats(self):
        return self.stats

    def getWeapon(self):
        return getattr(self, "weapon", None)

    def addEffect(self, effect):
        self.effects.append(effect)

    def getController(self):
        return getattr(self, "controller", None)

    def setController(self, controller):
        self.controller = controller

    def getDmg(self):
        self.damage_rolls += 1
        return self.getNumericProperty("damageRoll")

    def hurt(self, packet):
        damage = (
            packet
            if isinstance(packet, int)
            else sum(packet.getNumericProperty(channel) for channel in ("normal", "frost", "shadow"))
        )
        self.setHp(self.getHp() - damage)


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
        loader = (ROOT / "src/core/CLoader.cpp").read_text(encoding="utf-8")
        allowed = loader.split("allowedNames =", 1)[1].split("};", 1)[0]
        sandbox_builtins = {name: getattr(builtins, name) for name in re.findall(r'"([^"]+)"', allowed)}
        sandbox_builtins["__import__"] = builtins.__import__
        self.registered = {}
        self.pending = []
        game_stub = types.ModuleType("game")
        for name in ("CBuilding", "CEffect", "CEvent", "CInteraction", "CTrigger"):
            setattr(game_stub, name, type(name, (Properties,), {}))
        game_stub.Coords = lambda x, y, z: types.SimpleNamespace(x=x, y=y, z=z)
        game_stub.randint = Mock()
        game_stub.register = lambda context: lambda cls: self.registered.setdefault(cls.__name__, cls)
        game_stub.event_loop = types.SimpleNamespace(instance=lambda: types.SimpleNamespace(invoke=self.pending.append))
        with patch.dict(sys.modules, {"game": game_stub}):
            attack_spec = importlib.util.spec_from_file_location(
                "hunt_attack_under_test", ROOT / "res/plugins/interaction.py"
            )
            attack_module = importlib.util.module_from_spec(attack_spec)
            attack_module.__dict__["__builtins__"] = sandbox_builtins
            attack_spec.loader.exec_module(attack_module)
            attack_module.load(None, None)
            spec = importlib.util.spec_from_file_location(
                "octobogz_hunt_under_test", ROOT / "res/plugins/octobogz_hunt.py"
            )
            self.module = importlib.util.module_from_spec(spec)
            self.module.__dict__["__builtins__"] = sandbox_builtins
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
        elif type_id == "CRangeController":
            result = Mock()
        else:
            result = self.registered.get(mapping.get(type_id, type_id), Properties)()
        result.game = self.game
        result.setStringProperty("typeId", type_id)
        if type_id == "octobogzShadowPulse":
            result.setObjectProperty("roleDamage", Properties())
            result.setObjectProperty("roleEffect", self.createObject("OctobogzShadowPulseEffect"))
            result.setNumericProperty("manaCost", 5)
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

    def testRegistryUsesAnOpaqueStringEnvelopeAndReadsLegacyJson(self):
        self.director.start(self.game_map)
        expected = self.state()
        text = self.game_map.getStringProperty(self.module.REGISTRY_PROPERTY)
        self.assertTrue(text.startswith("octobogzHunt.v1:"))
        # The native dynamic-property loader attempts to coerce JSON-looking strings into objects.
        with self.assertRaises(json.JSONDecodeError):
            json.loads(text)
        self.assertEqual(expected, json.loads(text.removeprefix(self.module.REGISTRY_PREFIX)))
        self.game_map.setStringProperty(self.module.REGISTRY_PROPERTY, json.dumps(expected))
        self.assertEqual(expected, self.state())
        self.director.synchronize(self.game_map)
        self.assertTrue(self.game_map.getStringProperty(self.module.REGISTRY_PROPERTY).startswith("octobogzHunt.v1:"))

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

    def testHuntCallsUseThePublishedNativeObjectApi(self):
        bindings = (ROOT / "src/core/CModule.cpp").read_text(encoding="utf-8")
        published = set(re.findall(r'\.def(?:_static)?\s*\(\s*"([^"]+)"', bindings))
        source = (ROOT / "res/plugins/octobogz_hunt.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        local = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        python_methods = {"append", "capitalize", "dumps", "get", "index", "loads", "removeprefix", "sort", "values"}
        self.assertEqual(set(), called - published - local - python_methods)
        self.assertTrue({"getEffectiveInteractions", "setCaster", "setVictim", "addEffect", "addAction"} <= published)
        self.assertNotIn("getInteractions", called)
        self.assertNotIn("getManaCost", called)
        self.assertNotIn("getLabel", called)

    def testMcpHuntCallsUseExistingPublishedExportsAndHandleMethods(self):
        module = ast.parse((ROOT / "mcp.py").read_text(encoding="utf-8"))
        assignments = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in module.body
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"MCP_ALLOWED_EXPORTS", "MCP_ALLOWED_HANDLE_METHODS"}
        }
        published = assignments["MCP_ALLOWED_EXPORTS"]
        methods = set().union(*assignments["MCP_ALLOWED_HANDLE_METHODS"].values())
        tree = ast.parse((ROOT / "tests/test_octobogz_mcp.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            index = 0 if node.func.attr == "engine" else 1 if node.func.attr == "call" else None
            if index is not None and len(node.args) > index and isinstance(node.args[index], ast.Constant):
                self.assertIn(node.args[index].value, published if index == 0 else methods)
                if index == 1 and isinstance(node.args[0], ast.Name) and node.args[0].id == "tile":
                    self.assertIn(node.args[index].value, assignments["MCP_ALLOWED_HANDLE_METHODS"]["CGameObject"])

    def testMcpRouteUsesOnlyAdjacentNativeMovementAndActualMapTurnsAfterBlockersOrRollback(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player, walker.game_map = "player", "map"
        walker.walkable = {(x, y, 0) for x in range(3) for y in range(2)}
        walker.movement_steps = 0
        state = {"coords": (0, 0, 0), "turn": 0, "target": None}
        calls = []
        walker.coords = lambda handle=None: state["coords"]
        walker.pump = lambda: None

        def call(handle, method, *args):
            calls.append((handle, method, args))
            if method == "getTile":
                return tuple(args)
            if method == "getBoolProperty":
                self.assertEqual("canStep", args[0])
                return handle != (1, 0, 0)
            if method == "getStringProperty":
                self.assertEqual("uiDefeatReceipt", args[0])
                return ""
            if method == "moveTo":
                self.assertEqual("player", handle)
                self.assertEqual(1, sum(abs(a - b) for a, b in zip(state["coords"], args)))
                state["target"] = args
                if state["turn"]:
                    state["coords"] = state["target"]
            if method == "getTurn":
                return state["turn"]
            if method == "isAlive":
                return True
            if method == "move":
                # A first-turn combat rollback must cause replanning from the live position.
                state["turn"] += 1

        walker.call = call
        walker.walkCoords((2, 0, 0))
        self.assertEqual((2, 0, 0), state["coords"])
        self.assertEqual(5, state["turn"])
        self.assertEqual(state["turn"], walker.movement_steps)
        self.assertEqual(5, sum(method == "moveTo" for _, method, _ in calls))
        self.assertNotIn("getCoords", [method for _, method, _ in calls])
        self.assertNotIn("setTarget", [method for _, method, _ in calls])
        self.assertNotIn((1, 0, 0), [args for _, method, args in calls if method == "moveTo"])
        native = (ROOT / "src/object/CMapObject.cpp").read_text(encoding="utf-8")
        self.assertIn("if (is_registered && is_step_move)", native)
        self.assertIn("const bool can_step = map->canStep(target)", native)

    def testMcpAdjacentMovementRejectsLiveRespawnAndUnexplainedTransit(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        for respawn in (True, False):
            with self.subTest(respawn=respawn):
                walker = OctobogzMcpWalkthroughTest("runTest")
                walker.player, walker.game_map = "player", "map"
                walker.movement_steps = 0
                walker.pump = lambda: None
                walker.snapshot = lambda stage: stage
                state = {"coords": (165, 21, 0), "turn": 0, "receipt": ""}
                walker.coords = lambda handle=None: state["coords"]

                def call(handle, method, *args):
                    if method == "getStringProperty":
                        self.assertEqual("uiDefeatReceipt", args[0])
                        return state["receipt"]
                    if method == "getTile":
                        return "tile"
                    if method in ("getBoolProperty", "isAlive"):
                        return True
                    if method == "getTurn":
                        return state["turn"]
                    if method == "move":
                        state["turn"] += 1
                        state["coords"] = (110, 111, 0)
                        state["receipt"] = "defeated" if respawn else ""

                walker.call = call
                expected = "lost authored combat and respawned" if respawn else "Unexpected movement"
                with self.assertRaisesRegex(AssertionError, expected):
                    walker.step((166, 21, 0))
                self.assertEqual(0, walker.movement_steps)

    def testEachHuntSlotPreservesTheOriginalCaveAnchorAndTenCellRange(self):
        self.director.start(self.game_map)
        scout = self.kill("scout")
        for slot in self.module.SLOT_NAMES:
            actor = scout if slot == "scout" else self.game_map.getObjectByName(self.state()["slots"][slot]["name"])
            controller = actor.getController()
            self.assertEqual("cave2", actor.getStringProperty("octobogzHuntTarget"))
            controller.setTarget.assert_called_once_with("cave2")
            controller.setDistance.assert_called_once_with(10)
        scout.setStringProperty("octobogzHuntTarget", "player")
        self.director.configureActor(scout, "scout")
        scout.getController().setTarget.assert_called_once_with("cave2")
        scout.getController().setDistance.assert_called_once_with(10)

    def testMcpActorObservationsKeepActualPacketAndStateAfterObjectRemovalWithoutMutations(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        actor, packet = Actor("retainedAlpha"), Properties()
        actor.properties.update(
            hp=0,
            octobogzCombatPhase="spent",
            octobogzPulseUsed=True,
            octobogzPulseEffectApplied=True,
            enemyRoleAttackBudget=11,
            enemyRoleDamagePacket=packet,
        )
        packet.properties.update(normal=10, shadow=1)
        before = actor.properties.copy()
        walker.phase_observations = []
        walker.call = lambda handle, method, *args: getattr(handle, method)(*args)
        with patch("builtins.print"):
            walker.observeActors("after combat", {"alpha": actor})
        self.assertEqual(before, actor.properties)
        self.assertEqual(1, len(walker.phase_observations))
        observed = walker.phase_observations[0]
        self.assertEqual(
            ("spent", True, True, 11, 10, 1, False),
            tuple(observed[key] for key in ("phase", "pulse", "effect", "damage_roll", "normal", "shadow", "alive")),
        )
        source = (ROOT / "tests/test_octobogz_mcp.py").read_text(encoding="utf-8")
        self.assertIn('observed["pulse"] and observed["damage_roll"] > 0 and observed["shadow"] == 1', source)
        self.assertNotRegex(source, r'"(?:setHp|setMana|setLevel|setNumericProperty|setBoolProperty)"')

    def testRuntimeChildrenUseOnlyPublishedNativeCallsAndExistingScriptMethods(self):
        import textwrap

        bindings = (ROOT / "src/core/CModule.cpp").read_text(encoding="utf-8")
        published = set(re.findall(r'\.def(?:_static)?\s*\(\s*"([^"]+)"', bindings))
        tree = ast.parse((ROOT / "tests/test_octobogz_runtime.py").read_text(encoding="utf-8"))
        python_methods = {"loads", "uuid4", "unlink", "get", "append", "removeprefix", "startswith", "read_text"}
        script_methods = {"start", "synchronize", "accept_quest"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "runChild":
                calls = {
                    call.func.attr
                    for call in ast.walk(ast.parse(textwrap.dedent(node.args[0].value)))
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                }
                self.assertEqual(set(), calls - published - python_methods - script_methods - {"Coords"})

    def phaseActor(self, roll=11):
        actor = Actor("alpha")
        actor.game = self.game
        actor.properties["damageRoll"] = roll
        attack = self.registered["Attack"]()
        attack.getTypeId = lambda: "Attack"
        actor.addAction(attack)
        return actor, attack

    def testChargeAndPulseRetainOneConfiguredAttackEachAndCannotRepeatAfterSave(self):
        actor, _ = self.phaseActor()
        target = self.game_map.player
        before = target.getHp()
        charge = self.createObject("octobogzCharge")
        pulse = self.createObject("octobogzShadowPulse")
        packet = pulse.getObjectProperty("roleDamage")
        effect = pulse.getObjectProperty("roleEffect")
        self.game.createObject.reset_mock()
        charge.performAction(actor, target)
        self.assertEqual("charged", actor.getStringProperty("octobogzCombatPhase"))
        self.assertEqual(1, actor.damage_rolls)
        self.assertEqual(before - 11, target.getHp())
        self.game.getGuiHandler().notify.assert_called_once()
        pulse.performAction(actor, target)
        self.assertEqual(2, actor.damage_rolls)
        self.assertEqual({"normal": 10, "shadow": 1}, packet.properties)
        self.assertEqual(11, actor.getNumericProperty("enemyRoleAttackBudget"))
        self.assertEqual(before - 22, target.getHp())
        self.assertIsNone(pulse.getObjectProperty("roleEffect"))
        self.assertEqual([effect], target.effects)
        self.assertIs(effect.caster, actor)
        self.assertIs(effect.victim, target)
        self.assertEqual(0, pulse.getCommittedManaRefund(actor))
        self.assertFalse(actor.getBoolProperty("enemyRoleArcaneAttack"))
        self.assertEqual("", actor.getStringProperty("enemyRoleDamageChannel"))
        flags = {key: value for key, value in actor.properties.items() if isinstance(value, (str, int, bool))}
        actor.properties.update(json.loads(json.dumps(flags)))
        charge.performAction(actor, target)
        pulse.performAction(actor, target)
        self.assertEqual(2, actor.damage_rolls)
        self.assertEqual(5, pulse.getCommittedManaRefund(actor))
        self.assertEqual(1, len(target.effects))
        self.game.createObject.assert_not_called()

    def testShadowPacketPreservesWeaponProcAndCannotLeakAcrossMissOrLaterAttack(self):
        actor, attack = self.phaseActor()
        weapon, proc = Mock(), Mock()
        weapon.getInteraction.return_value = proc
        actor.weapon = weapon
        actor.setStringProperty("octobogzCombatPhase", "charged")
        pulse = self.createObject("octobogzShadowPulse")
        pulse.performAction(actor, self.game_map.player)
        proc.onAction.assert_called_once_with(actor, self.game_map.player)
        self.assertFalse(actor.getBoolProperty("enemyRoleArcaneAttack"))
        attack.performAction(actor, self.game_map.player)
        self.assertEqual(2, proc.onAction.call_count)
        self.assertEqual(2, actor.damage_rolls)
        actor, attack = self.phaseActor(0)
        actor.weapon = weapon
        actor.setStringProperty("octobogzCombatPhase", "charged")
        pulse = self.createObject("octobogzShadowPulse")
        target = Actor("missTarget")
        target.hurt = Mock()
        pulse.performAction(actor, target)
        target.hurt.assert_not_called()
        self.assertEqual({}, pulse.getObjectProperty("roleDamage").properties)
        self.assertEqual(2, proc.onAction.call_count)
        self.assertEqual(1, actor.damage_rolls)
        self.assertFalse(actor.getBoolProperty("enemyRoleArcaneAttack"))
        self.assertEqual("", actor.getStringProperty("enemyRoleDamageChannel"))

    def testFixedNoRestComparisonRetainsKnownVictoriesAndEveryClassResourceGate(self):
        source = (ROOT / "tests/unit/test_monster_balance.cpp").read_text(encoding="utf-8")
        route = source.split("void testStagedHuntPreservesOriginalThreeActorRouteWinsAndResourceBudget", 1)[1].split(
            "\n} // namespace", 1
        )[0]
        self.assertIn('std::string(playerType) == "Assasin"', route)
        self.assertIn('std::string(playerType) == "Inquisitor"', route)
        self.assertIn("if (originallyWinningClass)", route)
        self.assertIn("expect_true(baselineWins > 0", route)
        self.assertIn("expect_true(median(baselineHp) > 0", route)
        self.assertIn("!baseline.won || hunt.resources.won", route)
        self.assertIn("seed < 111", route)
        for resource in ("Hp", "Mana", "Items"):
            self.assertIn(
                f"std::abs(median(hunt{resource}) - median(baseline{resource})) * 10 <= median(baseline{resource})",
                route,
            )
        self.assertIn("if (huntPulse || huntCharge) {\n                    expect_true(actor->getMana() == 5", source)
        self.assertIn("testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(false, false, true)", source)
        controller = (ROOT / "src/core/CController.cpp").read_text(encoding="utf-8")
        phases = controller.split('const auto phase = me->getStringProperty("octobogzCombatPhase")', 1)[1].split(
            '} else if (action->getTypeId() == "Attack")', 1
        )[0]
        self.assertIn('(huntRole == "shadow" || me->getHpRatio() <= 50)', phases)
        self.assertIn(
            "testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(true, false, false, true)", source
        )
        self.assertIn("testCultistShadowPacketAndExpiryFollowActualFightInitiativeBoundaries(true)", source)
        boundary = source.split("void testCultistShadowPacketAndExpiryFollowActualFightInitiativeBoundaries", 1)[
            1
        ].split("void testMonsterRolesPreserveOrdinaryLoadoutWinsAndResourceBudget", 1)[0]
        self.assertIn("for (bool cultistFirst : {false, true})", boundary)
        self.assertIn("CFightHandler::fightManyResult", boundary)
        self.assertIn("damage.front() == (enabled ? 2 : 1)", boundary)
        self.assertIn("actor->getMana() == (enabled ? 0 : 5)", boundary)

    def testEqualWardsKeepOrdinaryAttackPathBeforeApplyingOwnedShadowDebuff(self):
        actor, _ = self.phaseActor()
        target = self.game_map.player
        target.stats.properties.update(normalResist=10, shadowResist=10)
        actor.setStringProperty("octobogzCombatPhase", "charged")
        pulse = self.createObject("octobogzShadowPulse")
        effect = pulse.getObjectProperty("roleEffect")
        weapon, proc = Mock(), Mock()
        weapon.getInteraction.return_value = proc
        actor.weapon = weapon
        before = target.getHp()
        pulse.performAction(actor, target)
        self.assertEqual(before - 11, target.getHp())
        self.assertEqual(1, actor.damage_rolls)
        self.assertEqual({}, pulse.getObjectProperty("roleDamage").properties)
        self.assertNotIn("enemyRoleAttackBudget", actor.properties)
        self.assertNotIn("enemyRoleDamagePacket", actor.properties)
        proc.onAction.assert_called_once_with(actor, target)
        self.assertEqual("spent", actor.getStringProperty("octobogzCombatPhase"))
        self.assertTrue(actor.getBoolProperty("octobogzPulseUsed"))
        self.assertEqual([effect], target.effects)
        self.assertIsNone(pulse.getObjectProperty("roleEffect"))
        self.assertEqual(0, pulse.getCommittedManaRefund(actor))
        self.assertFalse(actor.getBoolProperty("enemyRoleArcaneAttack"))

    def testRejectedOrCancelledPulseClearsHookAndRefundsPaidManaWithoutConsumingPhase(self):
        actor, attack = self.phaseActor()
        actor.setStringProperty("octobogzCombatPhase", "charged")
        pulse = self.createObject("octobogzShadowPulse")
        actor.actions.clear()
        pulse.performAction(actor, self.game_map.player)
        self.assertEqual(5, pulse.getCommittedManaRefund(actor))
        self.assertFalse(actor.getBoolProperty("octobogzPulseUsed"))
        actor.addAction(attack)
        attack.performAction = Mock(side_effect=RuntimeError("cancelled attack"))
        with self.assertRaisesRegex(RuntimeError, "cancelled attack"):
            pulse.performAction(actor, self.game_map.player)
        self.assertFalse(actor.getBoolProperty("enemyRoleArcaneAttack"))
        self.assertEqual("", actor.getStringProperty("enemyRoleDamageChannel"))
        self.assertEqual("charged", actor.getStringProperty("octobogzCombatPhase"))
        self.assertFalse(actor.getBoolProperty("octobogzPulseUsed"))
        self.assertEqual(5, pulse.getCommittedManaRefund(actor))
        self.assertEqual([], self.game_map.player.effects)
        pulse.performAction(actor, None)
        self.assertEqual(5, pulse.getCommittedManaRefund(actor))

    def testOnlyExplicitFrostOrShadowPacketChannelsCanChangeOrdinaryAttack(self):
        actor, attack = self.phaseActor()
        actor.setBoolProperty("enemyRoleArcaneAttack", True)
        actor.setStringProperty("enemyRoleDamageChannel", "fire")
        packet = Properties()
        actor.setObjectProperty("enemyRoleDamagePacket", packet)
        attack.performAction(actor, self.game_map.player)
        self.assertEqual({}, packet.properties)
        self.assertFalse(actor.getBoolProperty("enemyRoleArcaneAttack"))
        self.assertEqual("", actor.getStringProperty("enemyRoleDamageChannel"))
        config = json.loads((ROOT / "res/config/interactions.json").read_text(encoding="utf-8"))
        props = config["octobogzShadowPulse"]["properties"]
        self.assertEqual(5, props["manaCost"])
        self.assertNotIn("effect", props)
        self.assertEqual({"class": "CDamage"}, props["roleDamage"])
        effects = json.loads((ROOT / "res/config/effects.json").read_text(encoding="utf-8"))
        props = effects["octobogzShadowPulseEffect"]["properties"]
        self.assertEqual(1, props["duration"])
        self.assertEqual({"shadowResist": -1}, props["bonus"]["properties"])
        self.createObject("OctobogzShadowPulseEffect").onEffect()


if __name__ == "__main__":
    unittest.main()
