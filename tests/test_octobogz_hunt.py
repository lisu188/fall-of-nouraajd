# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
import builtins
from copy import deepcopy
import importlib.util
import json
import re
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
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

    def testLegacyQuestBoundaryMcpUsesOnlyExportedHandleMethods(self):
        module = ast.parse((ROOT / "mcp.py").read_text(encoding="utf-8"))
        allowed = next(
            ast.literal_eval(node.value)
            for node in module.body
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "MCP_ALLOWED_HANDLE_METHODS"
        )
        methods = set().union(*allowed.values())
        tree = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        fixture = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_mcp_walkthrough_nouraajd"
        )
        for node in ast.walk(fixture):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_mcp_handle_call"
                and len(node.args) > 2
                and isinstance(node.args[2], ast.Constant)
            ):
                self.assertIn(node.args[2].value, methods)

    def testExistingTriggerTargetValidationRecognizesTheAttachedPlayer(self):
        tree = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        checker = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "test_nouraajd_trigger_targets"
        )
        checker.decorator_list = []
        namespace = {"REPO_ROOT": ROOT, "json": json, "re": re}
        exec(compile(ast.Module(body=[checker], type_ignores=[]), "trigger-target-check", "exec"), namespace)
        success, log = namespace[checker.name](self)
        self.assertTrue(success, log)

    def testMcpDiagnosticCallsForwardExactArgumentsResultsAndFailuresWithoutExtraRpc(self):
        from tests import test_ui_mcp_dialogue as dialogue
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        result = {"actual": "native result"}
        failure = RuntimeError("original RPC failure")
        with (
            patch.object(dialogue.DialogueMcpWalkthroughTest, "engine", return_value=result) as engine,
            patch.object(dialogue.DialogueMcpWalkthroughTest, "call", side_effect=failure) as call,
            patch("tests.test_octobogz_mcp.perf_counter", side_effect=(10.0, 12.0, 20.0, 23.0)),
        ):
            self.assertIs(result, walker.engine("jsonify", "actor"))
            with self.assertRaises(RuntimeError) as caught:
                walker.call("player", "getNumericProperty", "posx")
        self.assertIs(failure, caught.exception)
        engine.assert_called_once_with(walker, "jsonify", "actor")
        call.assert_called_once_with(walker, "player", "getNumericProperty", "posx")
        self.assertEqual(
            {
                "export:jsonify": {"count": 1, "seconds": 2.0, "max": 2.0, "failures": 0},
                "handle:getNumericProperty": {"count": 1, "seconds": 3.0, "max": 3.0, "failures": 1},
            },
            walker.mcp_method_profile,
        )

    def testMcpDiagnosticReportIsBoundedReadonlyAndRetainsCompleteTotals(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.mcp_profile_class, walker.mcp_profile_started, walker.movement_steps = "Warrior", 10.0, 128
        walker.mcp_method_profile = {
            "method" + str(index): {"count": index + 1, "seconds": float(index), "max": float(index), "failures": 0}
            for index in range(70)
        }
        before = json.loads(json.dumps(walker.mcp_method_profile))
        walker.engine, walker.call = Mock(), Mock()
        with patch("tests.test_octobogz_mcp.perf_counter", return_value=15.0), patch("builtins.print") as report:
            walker.reportMcpProfile("adjacent movement checkpoint")
        walker.engine.assert_not_called()
        walker.call.assert_not_called()
        self.assertEqual(before, walker.mcp_method_profile)
        payload = report.call_args.args[1]
        self.assertEqual("MCP hunt method profile", report.call_args.args[0])
        self.assertTrue(report.call_args.kwargs["flush"])
        self.assertEqual(64, len(payload["methods"]))
        self.assertEqual(6, payload["omittedMethods"])
        self.assertEqual(sum(range(1, 71)), payload["calls"])
        self.assertEqual(sum(range(70)), payload["rpcSeconds"])
        self.assertEqual(5.0, payload["elapsed"])
        self.assertEqual("method69", payload["methods"][0]["method"])

    def testMcpDiagnosticProfileResetsBetweenClassesAndReportsEvery128ActualSteps(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.mcp_method_profile = {"previous class": {"count": 99}}
        with patch("tests.test_octobogz_mcp.perf_counter", return_value=42.0):
            walker.resetMcpProfile("Sorcerer")
        self.assertEqual({}, walker.mcp_method_profile)
        self.assertEqual("Sorcerer", walker.mcp_profile_class)
        self.assertEqual(42.0, walker.mcp_profile_started)
        walker.player, walker.game_map, walker.movement_steps = "player", "map", 126
        state = {"coords": (0, 0, 0), "turn": 0}
        walker.coords = lambda handle=None: state["coords"]
        walker.pump = Mock()
        walker.reportMcpProfile = Mock()

        def call(handle, method, *args):
            if method == "getStringProperty":
                return ""
            if method == "getTile":
                return "actual tile"
            if method in ("getBoolProperty", "isAlive"):
                return True
            if method == "moveTo":
                state["coords"] = tuple(args)
            if method == "getTurn":
                return state["turn"]
            if method == "move":
                state["turn"] += 1

        walker.call = Mock(side_effect=call)
        self.assertEqual((1, 0, 0), walker.step((1, 0, 0)))
        walker.reportMcpProfile.assert_not_called()
        self.assertEqual((2, 0, 0), walker.step((2, 0, 0)))
        walker.reportMcpProfile.assert_called_once_with("adjacent movement checkpoint")
        self.assertEqual(128, walker.movement_steps)
        self.assertEqual(2, state["turn"])
        self.assertEqual(4, walker.pump.call_count)
        self.assertEqual(2, sum(call.args[1] == "moveTo" for call in walker.call.call_args_list))
        self.assertEqual(2, sum(call.args[1] == "move" for call in walker.call.call_args_list))

    def testMcpMovementCoordinatesUseThreeScalarReadsAndNeverSerializeOrCacheTheActor(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player = "player"
        positions = {"player": {"posx": 57, "posy": 115, "posz": 0}, "actor": {"posx": 165, "posy": 20, "posz": 0}}
        calls = []

        def call(handle, method, name):
            calls.append((handle, method, name))
            self.assertEqual("getNumericProperty", method)
            return positions[handle][name]

        walker.call = call
        walker.engine = Mock(side_effect=AssertionError("Movement must not serialize the actor"))
        walker.fullJsonCoords = Mock(side_effect=AssertionError("The full JSON reader is reserved for explicit probes"))
        self.assertEqual((57, 115, 0), walker.coords())
        self.assertEqual((165, 20, 0), walker.coords("actor"))
        positions["player"]["posx"] = 58
        self.assertEqual((58, 115, 0), walker.coords())
        self.assertEqual(
            [
                (handle, "getNumericProperty", "pos" + axis)
                for handle in ("player", "actor", "player")
                for axis in "xyz"
            ],
            calls,
        )
        walker.engine.assert_not_called()
        walker.fullJsonCoords.assert_not_called()

    def testMcpScalarCoordinatesFollowReloadedPlayerAndPreserveSignedFloorsAndNativeErrors(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player = "restored-player"
        walker.call = Mock(side_effect=(-3, 0, -1))
        walker.engine = Mock(side_effect=AssertionError("Coordinate reads must not fall back to serialization"))
        self.assertEqual((-3, 0, -1), walker.coords())
        self.assertEqual(
            [("restored-player", "getNumericProperty", "pos" + axis) for axis in "xyz"],
            [call.args for call in walker.call.call_args_list],
        )
        failure = RuntimeError("actual native getter failure")
        walker.call = Mock(side_effect=(57, failure))
        with self.assertRaises(RuntimeError) as caught:
            walker.coords()
        self.assertIs(failure, caught.exception)
        self.assertEqual(2, walker.call.call_count)
        walker.engine.assert_not_called()

    def testMcpJourneyChecksScalarCoordinatesAgainstItsExistingNativeSnapshotWithoutAnotherJsonRead(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        for wrong_x in (False, True):
            with self.subTest(wrong_x=wrong_x):
                walker = OctobogzMcpWalkthroughTest("runTest")
                walker.player, walker.game_map = "player", "map"
                data = {"posx": 57, "posy": 115, "posz": 0, "hp": 84, "items": []}
                walker.engine = Mock(return_value=json.dumps({"properties": data}))
                walker.reportMcpProfile = Mock()

                def call(handle, method, *args):
                    if method == "getNumericProperty":
                        return {**data, "posx": 58 if wrong_x else 57, "exp": 4000}[args[0]]
                    return {"getLevel": 3, "getMana": 154, "getGold": 0, "getTurn": 459, "getStringProperty": ""}[
                        method
                    ]

                walker.call = call
                with patch("builtins.print"):
                    if wrong_x:
                        with self.assertRaises(AssertionError):
                            walker.snapshot("prepared checkpoint")
                    else:
                        self.assertEqual((57, 115, 0), walker.snapshot("prepared checkpoint")["coords"])
                walker.engine.assert_called_once_with("jsonify", "player")

    def testMcpPairedCoordinateProbeMeasuresTwentyReadonlyPairsAfterWarmup(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player, walker.game_map = "player", "map"
        walker.coords = Mock(side_effect=AssertionError("The measured baseline must remain explicit full JSON"))
        walker.engine = Mock(return_value=json.dumps({"properties": {"posx": 57, "posy": 115, "posz": 0}}))
        walker.state = Mock(return_value={"stage": "dormant"})
        walker.pump = Mock()

        def call(handle, method, *args):
            if handle == "map":
                self.assertEqual("getTurn", method)
                return 250
            self.assertEqual("player", handle)
            if method == "getNumericProperty":
                return {"posx": 57, "posy": 115, "posz": 0}[args[0]]
            return {"getHp": 98, "getMana": 126}[method]

        walker.call = Mock(side_effect=call)
        with patch("tests.test_octobogz_mcp.perf_counter", side_effect=range(84)), patch("builtins.print") as report:
            walker.probeCoordinateReadCosts()
        walker.pump.assert_not_called()
        walker.coords.assert_not_called()
        self.assertEqual(22, walker.engine.call_count)
        self.assertTrue(all(call.args == ("jsonify", "player") for call in walker.engine.call_args_list))
        self.assertEqual(22, walker.state.call_count)
        self.assertEqual(63, sum(call.args[1] == "getNumericProperty" for call in walker.call.call_args_list))
        self.assertEqual(
            {"getTurn", "getNumericProperty", "getHp", "getMana"}, {call.args[1] for call in walker.call.call_args_list}
        )
        payload = report.call_args.args[1]
        self.assertEqual("MCP hunt paired coordinate read probe", report.call_args.args[0])
        self.assertTrue(report.call_args.kwargs["flush"])
        self.assertEqual((20, 1), (payload["samples"], payload["warmup"]))
        self.assertEqual((1, 3), (payload["fullJsonRpcPerSample"], payload["scalarRpcPerSample"]))
        self.assertEqual((1, 1), (payload["fullJsonMedianSeconds"], payload["scalarMedianSeconds"]))
        self.assertEqual((20, 20), (payload["fullJsonTotalSeconds"], payload["scalarTotalSeconds"]))

    def testMcpPairedReadonlyProbeRejectsDifferentCoordinatesTurnsOrObjectiveState(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        for failure in ("coordinates", "turn", "state"):
            with self.subTest(failure=failure):
                walker = OctobogzMcpWalkthroughTest("runTest")
                walker.player, walker.game_map = "player", "map"
                walker.fullJsonCoords = lambda: (57, 115, 0)
                walker.state = (
                    Mock(side_effect=({"stage": "dormant"}, {"stage": "cleared"})) if failure == "state" else lambda: {}
                )
                reads = []

                def call(handle, method, *args):
                    reads.append(method)
                    if method == "getTurn":
                        return 1 if failure == "turn" and reads.count(method) > 1 else 0
                    if method == "getNumericProperty":
                        return {"posx": 58 if failure == "coordinates" else 57, "posy": 115, "posz": 0}[args[0]]
                    return {"getHp": 98, "getMana": 126}[method]

                walker.call = call
                with self.assertRaises(AssertionError), patch("builtins.print"):
                    walker.probeCoordinateReadCosts()
                self.assertFalse(set(reads) & {"moveTo", "move", "heal", "setHp", "setMana"})

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
            if method == "getObjects":
                return []
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

    def testMcpRouteRetainsWalkableCellAcrossThreeVictoriousCombatRollbacks(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player, walker.game_map = "player", "map"
        walker.walkable = {(0, 0, 0), (1, 0, 0)}
        walker.movement_steps = 0
        walker.pump = lambda: None
        state = {"coords": (0, 0, 0), "turn": 0, "wins": 0, "object_reads": 0}
        walker.coords = lambda handle=None: state["coords"]

        def call(handle, method, *args):
            if method == "getTile":
                return "tile"
            if method in ("getBoolProperty", "isAlive"):
                return True
            if method == "getStringProperty":
                return ""
            if method == "getObjects":
                state["object_reads"] += 1
                return []
            if method == "moveTo":
                self.assertEqual((1, 0, 0), args)
                if state["wins"] < 3:
                    state["wins"] += 1
                else:
                    state["coords"] = args
            if method == "getTurn":
                return state["turn"]
            if method == "move":
                state["turn"] += 1

        walker.call = call
        walker.walkCoords((1, 0, 0))
        self.assertEqual(3, state["wins"])
        self.assertEqual(4, walker.movement_steps)
        self.assertEqual(1, state["object_reads"])
        self.assertIn((1, 0, 0), walker.walkable)

    def testMcpRouteChecksTheLiveNativeBlockerAfterItsRemoval(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player, walker.game_map = "player", "map"
        walker.walkable = {(0, 0, 0), (1, 0, 0)}
        walker.movement_steps = 0
        walker.pump = lambda: None
        state = {"coords": (0, 0, 0), "turn": 0, "native_checks": 0}
        walker.coords = lambda handle=None: (1, 0, 0) if handle == "removed-blocker" else state["coords"]

        def call(handle, method, *args):
            if method == "getTile":
                return "tile"
            if method == "getBoolProperty":
                return handle != "removed-blocker"
            if method == "getObjects":
                return ["removed-blocker"]
            if method == "getCoords":
                self.assertEqual("removed-blocker", handle)
                return "real-coords-handle"
            if method == "canStep":
                self.assertEqual(("real-coords-handle",), args)
                state["native_checks"] += 1
                return True
            if method == "getStringProperty":
                return ""
            if method == "isAlive":
                return True
            if method == "moveTo" and state["turn"]:
                state["coords"] = args
            if method == "getTurn":
                return state["turn"]
            if method == "move":
                state["turn"] += 1

        walker.call = call
        walker.walkCoords((1, 0, 0))
        self.assertEqual(1, state["native_checks"])
        self.assertEqual(2, walker.movement_steps)
        self.assertIn((1, 0, 0), walker.walkable)

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

    def testPreparedMcpRouteUsesAuthoredRoadsAndNaturalRolfProgression(self):
        source = json.loads((ROOT / "res/maps/nouraajd/map.json").read_text(encoding="utf-8"))
        tile_types = source["tilesets"][0]["tileproperties"]
        layer = next(layer for layer in source["layers"] if layer["type"] == "tilelayer")
        for x, y in (
            (44, 106),
            (44, 107),
            (9, 36),
            (9, 37),
            (109, 100),
            (109, 101),
            (118, 21),
            (118, 20),
            (110, 111),
            (109, 111),
            (57, 115),
            (58, 115),
            (30, 115),
        ):
            tile = layer["data"][x + y * source["width"]]
            self.assertEqual("RoadTile", tile_types[str(tile - 1)]["type"], (x, y))
        route = (ROOT / "tests/test_octobogz_mcp.py").read_text(encoding="utf-8")
        self.assertIn('self.walkTo("cave1", allow_removed=True)', route)
        self.assertIn('self.walkTo("gooby1", allow_removed=True)', route)
        self.assertIn('self.assertGreater(after["exp"], before["exp"]', route)
        self.assertIn('self.assertIn("mainQuest", self.questNames("getCompletedQuests"))', route)
        self.assertIn('self.call(self.player, "getHp") == self.call(self.player, "getHpMax")', route)
        self.assertIn('self.call(self.player, "getManaMax")', route)
        called_methods = {
            node.args[1].value
            for node in ast.walk(ast.parse(route))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "call"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
        }
        self.assertEqual(
            set(),
            called_methods
            & {"addExp", "addExpScaled", "addItem", "addItems", "addGold", "heal", "setHp", "setMana", "setLevel"},
        )

    def testRolfEnemyDiscoveryUsesOnlyLivingAuthoredNearbyPritschers(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.game_map = "map"
        near, far, dead, wrong_type, wrong_affiliation = [
            Actor(name) for name in ("near", "far", "dead", "type", "side")
        ]
        for actor in (near, far, dead, wrong_type, wrong_affiliation):
            actor.properties.update(typeId="Pritz", affiliation="gooby")
            actor.coords = types.SimpleNamespace(x=20, y=10, z=0)
        far.coords.x = 100
        dead.setHp(0)
        wrong_type.properties["typeId"] = "Cultist"
        wrong_affiliation.properties["affiliation"] = "bogz"
        walker.coords = lambda handle=None: (19, 10, 0) if handle is None else tuple(vars(handle.coords).values())
        walker.call = lambda handle, method, *args: (
            [near, far, dead, wrong_type, wrong_affiliation] if handle == "map" else getattr(handle, method)(*args)
        )
        self.assertEqual([(1, "near")], walker.nearbyRolfEnemies())

    def testCatacombsPreparationEarnsLiveLevelFourFromExistingFoesWithoutAssumingEighteenKills(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player, walker.game_map = "player", "map"
        state = {"exp": 5750, "relics": 0, "catacombs": True, "living": ["catOne", "catTwo"]}
        walker.snapshot = lambda stage: {"exp": state["exp"], "stage": stage}
        walker.recoverOnRoadPair = Mock()
        walker.walkCoords = Mock()
        walker.nearbyAuthoredPritz = Mock(
            side_effect=lambda anchor: [(index, name) for index, name in enumerate(state["living"])]
        )

        def call(handle, method, *args):
            if method == "getLevel":
                return 4 if state["exp"] >= 6000 else 3
            if method == "getNumericProperty":
                self.assertEqual(("exp",), args)
                return state["exp"]
            if method == "getHpRatio":
                return 100
            if method == "countItems":
                self.assertEqual(("holyRelic",), args)
                return state["relics"]
            if method == "getObjectByName":
                return args[0] if args[0] in state["living"] or args[0] == "catacombs" and state["catacombs"] else None
            self.fail(method)

        def walk(name, **kwargs):
            if name == "catacombs":
                state["catacombs"] = False
                state["relics"] += 1
            else:
                state["living"].remove(name)
                state["exp"] += 125

        walker.call = call
        walker.walkTo = Mock(side_effect=walk)
        walker.prepareThroughCatacombs()
        self.assertEqual(
            [(9, 39, 0), (8, 39, 0), (8, 49, 0), (9, 49, 0), (9, 81, 0), (30, 81, 0), (30, 115, 0)],
            [call.args[0] for call in walker.walkCoords.call_args_list],
        )
        self.assertEqual(6000, state["exp"])
        self.assertEqual([], state["living"])
        self.assertEqual(3, walker.walkTo.call_count)
        self.assertEqual(2, walker.nearbyAuthoredPritz.call_count)
        self.assertTrue(all(call.args == ((57, 103, 0),) for call in walker.nearbyAuthoredPritz.call_args_list))
        self.assertEqual(2, walker.recoverOnRoadPair.call_count)
        for call in walker.recoverOnRoadPair.call_args_list:
            self.assertEqual(((57, 115, 0), (58, 115, 0)), call.args[:2])
        source = (ROOT / "tests/test_octobogz_mcp.py").read_text(encoding="utf-8")
        self.assertIn("for _ in range(18):", source)
        self.assertIn("for _ in range(32):", source)
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "assertGreater"
                and isinstance(node.args[-1], ast.Constant)
                and str(node.args[-1].value).startswith("Catacombs preparation must earn real combat")
                for node in ast.walk(ast.parse(source))
            )
        )
        self.assertIn('self.assertGreaterEqual(self.call(self.player, "getLevel"), 4', source)
        self.assertIn('self.assertGreaterEqual(self.call(self.player, "getNumericProperty", "exp"), 6000)', source)

    def testCatacombsControllerMatchesItsAuthoredGrassNeighborhoodWithoutChangingTheEncounter(self):
        config = json.loads((ROOT / "res/maps/nouraajd/config.json").read_text(encoding="utf-8"))
        document = json.loads((ROOT / "res/maps/nouraajd/map.json").read_text(encoding="utf-8"))
        tiles = json.loads((ROOT / "res/config/tiles.json").read_text(encoding="utf-8"))
        cat = config["catacombs"]["properties"]
        monster = cat["monster"]
        controller = monster["properties"]["controller"]
        self.assertEqual("Pritz", monster["ref"])
        self.assertEqual("gooby", monster["properties"]["affiliation"])
        self.assertEqual("CGroundController", controller["class"])
        self.assertEqual(("10", "10"), (cat["chance"], cat["monsters"]))
        self.assertEqual(
            "ground", config["cave1"]["properties"]["monster"]["properties"]["controller"]["properties"]["tileType"]
        )
        objects = [obj for layer in document["layers"] if layer["type"] == "objectgroup" for obj in layer["objects"]]
        authored_cat = next(obj for obj in objects if obj["name"] == "catacombs")
        anchor = (int(authored_cat["x"] / document["tilewidth"]), int(authored_cat["y"] / document["tileheight"]))
        self.assertEqual((57, 103), anchor)
        layer = next(layer for layer in document["layers"] if layer["type"] == "tilelayer")
        tileset = document["tilesets"][0]
        for x in range(anchor[0] - 2, anchor[0] + 3):
            for y in range(anchor[1] - 2, anchor[1] + 3):
                gid = layer["data"][x + y * document["width"]]
                tile_type = tileset["tileproperties"][str(gid - tileset["firstgid"])]["type"]
                properties = tiles[tile_type]["properties"]
                self.assertEqual("GrassTile", tile_type, (x, y))
                self.assertTrue(properties["canStep"])
                self.assertEqual(properties["tileType"], controller["properties"]["tileType"], (x, y))

    def testCatacombsRecoveryDetourStaysOnAuthoredRoadsAndAvoidsTheStackedCaveBeforeRealEntry(self):
        from tests.castle_walkthrough import TransitRoutes, shortestRoute
        from tests.narrative_walkthrough import authoredRegion

        objects, walkable = authoredRegion("nouraajd")
        cave, road = objects["catacombs"], (57, 115, 0)
        waypoints = ((9, 39, 0), (8, 39, 0), (8, 49, 0), (9, 49, 0), (9, 81, 0), (30, 81, 0), (30, 115, 0), road)
        document = json.loads((ROOT / "res/maps/nouraajd/map.json").read_text(encoding="utf-8"))
        tiles = document["tilesets"][0]["tileproperties"]
        layer = next(layer for layer in document["layers"] if layer["type"] == "tilelayer")
        self.assertEqual((57, 103, 0), cave)
        for origin in ((9, 36, 0), (9, 37, 0)):
            with self.subTest(origin=origin):
                direct = shortestRoute(walkable, TransitRoutes(), origin, road)
                detour, current = [], origin
                for waypoint in waypoints:
                    detour += shortestRoute(walkable, TransitRoutes(), current, waypoint)
                    current = waypoint
                self.assertIn(cave, [step for step, arrival in direct])
                self.assertNotIn(cave, [step for step, arrival in detour])
                self.assertLessEqual(len(detour), 512)
                self.assertEqual(2, len(detour) - len(direct))
                for step, arrival in detour:
                    x, y, z = step
                    self.assertEqual(0, z)
                    tile = layer["data"][x + y * document["width"]]
                    self.assertEqual("RoadTile", tiles[str(tile - 1)]["type"], step)
        source = (ROOT / "tests/test_octobogz_mcp.py").read_text(encoding="utf-8")
        methods = {node.name: node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef)}
        preparation = ast.get_source_segment(source, methods["prepareThroughCatacombs"])
        self.assertLess(preparation.index("self.walkCoords(waypoint)"), preparation.index("self.recoverOnRoadPair("))
        self.assertLess(preparation.index("self.recoverOnRoadPair("), preparation.index("self.assertIsNotNone("))
        self.assertLess(preparation.index("self.assertIsNotNone("), preparation.index('self.walkTo("catacombs"'))
        route = ast.get_source_segment(
            source, methods["testWarriorAndSorcererFinishThreeRealEncountersWithPartialReloadAndRewardOnce"]
        )
        self.assertLess(route.index("self.prepareThroughRolf("), route.index("self.probeCoordinateReadCosts("))
        self.assertLess(route.index("self.probeCoordinateReadCosts("), route.index("self.prepareThroughCatacombs("))

    def testCatacombsRecoveryMustLeaveTheCaveUntouchedBeforeItsActualEntry(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player, walker.game_map = "player", "map"
        walker.walkCoords, walker.recoverOnRoadPair, walker.walkTo = Mock(), Mock(), Mock()
        walker.snapshot = Mock(return_value={})
        walker.call = Mock(side_effect=lambda handle, method, *args: {"getLevel": 3, "countItems": 0}.get(method))
        with self.assertRaises(AssertionError):
            walker.prepareThroughCatacombs()
        walker.recoverOnRoadPair.assert_called_once_with(
            (57, 115, 0), (58, 115, 0), "before original catacombs road recovery"
        )
        walker.walkTo.assert_not_called()

    def testCatacombsDiscoveryUsesOnlyLivingAuthoredNearbyPritzOnTheSameFloor(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.game_map = "map"
        near, far, underground, dead, wrong_type, wrong_side = [Actor(str(index)) for index in range(6)]
        for actor in (near, far, underground, dead, wrong_type, wrong_side):
            actor.properties.update(typeId="Pritz", affiliation="gooby")
            actor.coords = types.SimpleNamespace(x=57, y=103, z=0)
        far.coords.x = 113
        underground.coords.z = 1
        dead.setHp(0)
        wrong_type.properties["typeId"] = "Cultist"
        wrong_side.properties["affiliation"] = "bogz"
        walker.coords = lambda handle=None: (57, 115, 0) if handle is None else tuple(vars(handle.coords).values())
        walker.call = lambda handle, method, *args: (
            [near, far, underground, dead, wrong_type, wrong_side]
            if handle == "map"
            else getattr(handle, method)(*args)
        )
        self.assertEqual([(12, "0")], walker.nearbyAuthoredPritz((57, 103, 0)))

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
        walker.engine = lambda export, handle: json.dumps({"properties": {"enemyRoleDamagePacket": "owned"}})
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

    def testMcpActorObservationDoesNotReadAnAbsentNativePacketProperty(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        actor = Actor("scout")
        actor.getObjectProperty = Mock(side_effect=IndexError("Native dynamic object property is absent"))
        walker.phase_observations = []
        walker.call = lambda handle, method, *args: getattr(handle, method)(*args)
        walker.engine = lambda export, handle: json.dumps({"properties": {}})
        with patch("builtins.print"):
            walker.observeActors("after scout", {"scout": actor})
        actor.getObjectProperty.assert_not_called()
        observed = walker.phase_observations[0]
        self.assertEqual((0, 0), (observed["normal"], observed["shadow"]))

    def testMcpLairEntryCapturesTheSpawnedScoutBeforeItsFirstNaturalCombatTurn(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player, walker.game_map = Actor("player", player=True), "map"
        walker.player.setNumericProperty("exp", 3000)
        walker.player.getItems = lambda: []
        walker.walkable, walker.movement_steps = {(0, 0, 0), (1, 0, 0)}, 0
        walker.hunt_actors, walker.confirmed_dead, walker.phase_observations = {}, set(), []
        walker.pump = lambda: None
        lair = Properties()
        lair.coords = (1, 0, 0)
        objects = {"cave2": lair}
        registry = {
            "stage": "dormant",
            "slots": {slot: {"name": slot, "status": "pending"} for slot in ("scout", "brood", "alpha")},
        }
        position, turn = [(0, 0, 0)], [0]
        walker.state = lambda: registry
        walker.snapshot = lambda stage: {"exp": walker.player.getNumericProperty("exp")}
        walker.coords = lambda handle=None: position[0] if handle is None else handle.coords
        walker.engine = lambda export, handle: json.dumps({"properties": {}})

        def call(handle, method, *args):
            if handle == "map":
                if method == "getObjectByName":
                    return objects.get(args[0])
                if method == "getTile":
                    return "tile"
                if method == "getBoolProperty":
                    return False
                if method == "getTurn":
                    return turn[0]
                if method == "move":
                    self.assertIs(objects["scout"], walker.hunt_actors["scout"])
                    self.assertTrue(walker.hunt_actors["scout"].isAlive())
                    objects.pop("scout").setHp(0)
                    registry["stage"], registry["slots"]["scout"]["status"] = "brood", "dead"
                    for slot in ("brood", "alpha"):
                        objects[slot] = Actor(slot)
                        registry["slots"][slot]["status"] = "living"
                    walker.player.setNumericProperty("exp", 3250)
                    turn[0] += 1
                    return
            if handle == "tile":
                self.assertEqual("getBoolProperty", method)
                return True
            if handle is walker.player and method == "moveTo":
                self.assertEqual((1, 0, 0), args)
                position[0] = args
                objects["scout"] = Actor("scout")
                registry["stage"], registry["slots"]["scout"]["status"] = "scout", "living"
                return
            return getattr(handle, method)(*args)

        walker.call = call
        with patch("builtins.print"):
            walker.enterHunt()
        self.assertEqual({"scout"}, walker.confirmed_dead)
        self.assertEqual("brood", registry["stage"])
        self.assertTrue(walker.hunt_actors["alpha"].isAlive())
        self.assertTrue(walker.hunt_actors["brood"].isAlive())
        self.assertEqual(1, turn[0])
        self.assertEqual(1, walker.movement_steps)

    def testMcpCaptureKeepsTheLivingActorBeforeDirectMovementCombat(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player, walker.game_map = Actor("player", player=True), "map"
        walker.hunt_actors, walker.confirmed_dead = {}, set()
        walker.observeActors = Mock()
        walker.hunt_lair_coords, walker.movement_steps = (1, 0, 0), 0
        walker.capture_before_move = walker.captureHuntActors
        walker.pump = lambda: None
        alpha = Actor("alpha")
        registry = {"slots": {"alpha": {"name": "alpha", "status": "living"}}}
        present, turn = [True], [0]
        walker.state = lambda: registry
        walker.coords = lambda handle=None: (0, 0, 0)

        def call(handle, method, *args):
            if handle == "map":
                if method == "getObjectByName":
                    return alpha if present[0] else None
                if method == "getTile":
                    return "tile"
                if method == "getTurn":
                    return turn[0]
                if method == "move":
                    turn[0] += 1
                    return
            if handle == "tile":
                self.assertEqual("getBoolProperty", method)
                return True
            if handle is walker.player and method == "moveTo":
                self.assertIs(alpha, walker.hunt_actors["alpha"])
                alpha.setHp(0)
                registry["slots"]["alpha"]["status"], present[0] = "dead", False
                return
            return getattr(handle, method)(*args)

        walker.call = call
        with patch("builtins.print"):
            self.assertEqual((0, 0, 0), walker.step((1, 0, 0)))
        walker.assertSlotDefeated("alpha")
        self.assertEqual({"alpha"}, walker.confirmed_dead)

    def testMcpPartialReloadRebindsLivingIdentityAndCannotConfirmAFlagOnlyDeath(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.game_map = "map"
        old, restored = Actor("alpha"), Actor("alpha")
        walker.hunt_actors, walker.confirmed_dead = {"alpha": old}, set()
        walker.observeActors = Mock()
        registry = {"slots": {"alpha": {"name": "alpha", "status": "living"}}}
        walker.state = lambda: registry
        present = [restored]

        def call(handle, method, *args):
            if handle == "map":
                self.assertEqual("getObjectByName", method)
                return present[0]
            return getattr(handle, method)(*args)

        walker.call = call
        with patch("builtins.print"):
            walker.trackLivingHuntActors()
        self.assertIs(restored, walker.hunt_actors["alpha"])
        registry["slots"]["alpha"]["status"], present[0] = "dead", None
        with self.assertRaises(AssertionError):
            walker.assertSlotDefeated("alpha")
        self.assertEqual(set(), walker.confirmed_dead)
        restored.setHp(0)
        walker.assertSlotDefeated("alpha")
        self.assertEqual({"alpha"}, walker.confirmed_dead)
        self.assertTrue(old.isAlive(), "The retained pre-save actor must never stand in for the loaded actor")

    def testMcpAlreadyDeadSlotRetainsTheActualPulsePacketExactlyOnce(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.game_map, walker.phase_observations = "map", []
        actor, packet = Actor("alpha"), Properties()
        actor.setHp(0)
        actor.setBoolProperty("octobogzPulseUsed", True)
        actor.setNumericProperty("enemyRoleAttackBudget", 11)
        packet.properties.update(normal=10, shadow=1)
        actor.setObjectProperty("enemyRoleDamagePacket", packet)
        walker.hunt_actors, walker.confirmed_dead = {"alpha": actor}, set()
        walker.state = lambda: {"slots": {"alpha": {"name": "alpha", "status": "dead"}}}
        walker.engine = lambda export, handle: json.dumps({"properties": {"enemyRoleDamagePacket": {}}})

        def call(handle, method, *args):
            if handle == "map":
                self.assertEqual("getObjectByName", method)
                return None
            return getattr(handle, method)(*args)

        walker.call = call
        with patch("builtins.print"):
            walker.defeat("alpha")
            walker.defeat("alpha")
        self.assertEqual({"alpha"}, walker.confirmed_dead)
        self.assertEqual(1, len(walker.phase_observations))
        observation = walker.phase_observations[0]
        self.assertEqual((11, 10, 1), tuple(observation[key] for key in ("damage_roll", "normal", "shadow")))
        self.assertTrue(observation["pulse"])
        self.assertFalse(observation["alive"])

    def portalWalker(self, failure=None):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player, walker.game_map, walker.game = Actor("player", player=True), "map", "game"
        scroll = Properties()
        scroll.setStringProperty("typeId", "TownPortalScroll")
        inventory = [] if failure == "unowned" else [scroll]
        position = [(166, 21, 0)]
        registry = {"stage": "brood", "slots": {"scout": "dead", "alpha": "dead", "brood": "living"}}
        walker.state = lambda: json.loads(json.dumps(registry))
        walker.snapshot = lambda stage: {"defeat": ""}
        walker.coords = lambda handle=None: position[0]
        walker.pump = Mock()
        walker.recoverOnRoadPair = Mock()
        calls = []

        def call(handle, method, *args):
            calls.append((handle, method, args))
            if handle == "game":
                self.assertEqual("getMap", method)
                return "wrong map" if failure == "map" else "map"
            if handle == "map":
                if method == "getPlayer":
                    return Actor("wrong player") if failure == "player" else walker.player
                return {"getEntryX": 110, "getEntryY": 111, "getEntryZ": 0}[method]
            if handle is walker.player:
                if method == "getItems":
                    return list(inventory)
                if method == "countItems":
                    self.assertEqual(("TownPortalScroll",), args)
                    return len(inventory)
                if method == "useItem":
                    self.assertEqual((scroll,), args)
                    self.assertIn(scroll, inventory)
                    if failure != "unconsumed":
                        inventory.remove(scroll)
                    position[0] = (109, 111, 0) if failure == "arrival" else (110, 111, 0)
                    if failure == "defeat":
                        walker.player.setStringProperty("uiDefeatReceipt", "native defeat")
                    if failure == "objectives":
                        registry["stage"] = "cleared"
                    return
            return getattr(handle, method)(*args)

        walker.call = call
        return walker, calls

    def testMcpOwnedAuthoredPortalPreservesIdentityObjectivesAndConsumesOneRealItem(self):
        walker, calls = self.portalWalker()
        with patch("builtins.print"):
            walker.retreatWithOwnedAuthoredScroll()
        self.assertEqual(1, sum(method == "useItem" for _, method, _ in calls))
        self.assertFalse(any(method in ("moveTo", "move", "heal", "setHp") for _, method, _ in calls))
        walker.pump.assert_called_once_with()
        walker.recoverOnRoadPair.assert_called_once_with((110, 111, 0), (109, 111, 0), "town portal road recovery")

    def testMcpPortalRejectsUnownedUnconsumedDefeatWrongArrivalOrChangedIdentityAndObjectives(self):
        for failure in ("unowned", "unconsumed", "defeat", "arrival", "objectives", "map", "player"):
            with self.subTest(failure=failure):
                walker, calls = self.portalWalker(failure)
                with self.assertRaises(AssertionError), patch("builtins.print"):
                    walker.retreatWithOwnedAuthoredScroll()
                walker.recoverOnRoadPair.assert_not_called()
                if failure == "unowned":
                    self.assertFalse(any(method == "useItem" for _, method, _ in calls))

    def testMcpRouteUsesEarnedRolfSuppliesBeforeHuntAndStillCompletesTheOriginalMainQuest(self):
        source = (ROOT / "tests/test_octobogz_mcp.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        methods = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        preparation = ast.get_source_segment(source, methods["prepareThroughRolf"])
        self.assertNotIn('self.walkTo("gooby1"', preparation)
        self.assertIn('"before hunt Rolf road recovery"', preparation)
        completion = ast.get_source_segment(source, methods["finishOriginalMainQuest"])
        self.assertIn('self.walkTo("gooby1", allow_removed=True)', completion)
        self.assertIn('self.assertIn("mainQuest", self.questNames("getCompletedQuests"))', completion)
        route = ast.get_source_segment(
            source, methods["testWarriorAndSorcererFinishThreeRealEncountersWithPartialReloadAndRewardOnce"]
        )
        names = (
            "collectAuthoredRetreatScroll",
            "prepareThroughRolf",
            "prepareThroughCatacombs",
            "enterHunt",
            "retreatWithOwnedAuthoredScroll",
            "finishOriginalMainQuest",
        )
        indexes = [route.index("self." + name + "(") for name in names]
        self.assertEqual(sorted(indexes), indexes)
        self.assertLess(route.index('self.assertEqual("cleared"'), indexes[-1])
        self.assertIn('"MCP hunt actual earned healing stock"', source)
        objects, _ = __import__("tests.narrative_walkthrough", fromlist=["authoredRegion"]).authoredRegion("nouraajd")
        self.assertEqual((108, 110, 0), objects["townPortalScroll"])

    def runtimeDiagnosticFixture(self, shared_runner):
        from tests import test_python_callback_lifecycle as lifecycle

        source = (ROOT / "tests/test_octobogz_runtime.py").read_text(encoding="utf-8")
        namespace = {"__name__": "huntRuntimeDiagnosticFixture"}
        with patch.object(lifecycle.PythonCallbackLifecycleTest, "runChild", shared_runner):
            exec(compile(source, "hunt-runtime-diagnostic-fixture", "exec"), namespace)
        return namespace["OctobogzRuntimeTest"]("runTest")

    def testNativePartialCoverageWatchdogIsScopedToTheExactFlagAndOtherChildrenKeepTheirDefault(self):
        import os
        from tests.test_octobogz_runtime import OctobogzRuntimeTest

        for flag in ("", "0", "true", "01", "1"):
            with self.subTest(flag=flag), patch.dict(os.environ, {"GAME_COVERAGE_RUN": flag}):
                fixture = OctobogzRuntimeTest("runTest")
                fixture.runChild = Mock()
                fixture.testNativeActorDeathsPartialSaveAndLivingRecoveryPreserveIdentityAndRewardOnce()
                self.assertEqual(
                    60 if flag == "1" else 30, fixture.runChild.call_args.kwargs.get("timeout_seconds", 30)
                )
                fixture.runChild.reset_mock()
                fixture.testNativeLegacyAdoptionAddsActionsWithoutChangingHealthOrExtraActors()
                self.assertEqual({}, fixture.runChild.call_args.kwargs)

    def testSharedCallbackAndRoleChildrenKeepThirtySecondsUnlessExplicitlyScoped(self):
        import os
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest
        from tests.test_enemy_role_runtime import EnemyRoleRuntimeTest

        self.assertIs(PythonCallbackLifecycleTest.runChild, EnemyRoleRuntimeTest.runChild)
        result = types.SimpleNamespace(returncode=0, stdout="verified", stderr="")
        for fixture_type in (PythonCallbackLifecycleTest, EnemyRoleRuntimeTest):
            with self.subTest(fixture=fixture_type.__name__), patch.dict(os.environ, {"GAME_COVERAGE_RUN": "1"}):
                fixture = fixture_type("runTest")
                with patch("tests.test_python_callback_lifecycle.subprocess.run", return_value=result) as run:
                    self.assertEqual("verified", fixture.runChild("the original complete workload"))
                    self.assertEqual(30, run.call_args.kwargs["timeout"])
                if fixture_type is PythonCallbackLifecycleTest:
                    with patch("tests.test_python_callback_lifecycle.subprocess.run", return_value=result) as run:
                        self.assertEqual(
                            "verified", fixture.runChild("the explicitly scoped workload", timeout_seconds=60)
                        )
                        self.assertEqual(60, run.call_args.kwargs["timeout"])

    def testNativePartialExplicitCoverageTimeoutRetainsItsCapturedFailureAndBoundedStreams(self):
        import io
        import subprocess
        from contextlib import redirect_stderr

        failure = subprocess.TimeoutExpired(
            ["python", "child"], 60, output=b"native hunt stage save2 begin", stderr=b"actual failure"
        )
        shared_runner = Mock(side_effect=failure)
        fixture = self.runtimeDiagnosticFixture(shared_runner)
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(subprocess.TimeoutExpired) as caught:
            fixture.runChild("the original complete native workload", timeout_seconds=60)
        shared_runner.assert_called_once_with("the original complete native workload", timeout_seconds=60)
        self.assertIs(failure, caught.exception)
        self.assertEqual(60, caught.exception.timeout)
        self.assertEqual(failure.output, caught.exception.output)
        self.assertEqual(failure.stderr, caught.exception.stderr)
        self.assertIn("native hunt stage save2 begin", stderr.getvalue())
        self.assertIn("actual failure", stderr.getvalue())

    def testNativePartialTimeoutDiagnosticsRetainBoundedStreamsAndTheOriginalThirtySecondFailure(self):
        import io
        import subprocess
        from contextlib import redirect_stderr

        failure = subprocess.TimeoutExpired(
            ["python", "child"],
            30,
            output=b"discarded stdout prefix" + b"x" * 9000 + b"\nnative hunt stage save1 begin",
            stderr=b"discarded stderr prefix" + b"y" * 9000 + b"\nFAULT\xff",
        )
        shared_runner = Mock(side_effect=failure)
        fixture = self.runtimeDiagnosticFixture(shared_runner)
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(subprocess.TimeoutExpired) as caught:
            fixture.runChild("the original complete native workload")
        shared_runner.assert_called_once_with("the original complete native workload")
        self.assertIs(failure, caught.exception)
        self.assertEqual(30, caught.exception.timeout)
        self.assertEqual(["python", "child"], caught.exception.cmd)
        self.assertEqual(failure.output, caught.exception.output)
        self.assertEqual(failure.stderr, caught.exception.stderr)
        output = stderr.getvalue()
        self.assertIn("stdout:", output)
        self.assertIn("stderr:", output)
        self.assertIn("native hunt stage save1 begin", output)
        self.assertIn("FAULT\ufffd", output)
        self.assertEqual(2, output.count("[omitted "))
        self.assertNotIn("discarded stdout prefix", output)
        self.assertNotIn("discarded stderr prefix", output)
        self.assertLess(len(output), 16600)

    def testNativePartialDiagnosticsPreserveSuccessAndEmptyOrTextTimeoutStreams(self):
        import io
        import subprocess
        from contextlib import redirect_stderr

        result = object()
        shared_runner = Mock(return_value=result)
        fixture = self.runtimeDiagnosticFixture(shared_runner)
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertIs(result, fixture.runChild("unchanged workload"))
        shared_runner.assert_called_once_with("unchanged workload")
        self.assertEqual("", stderr.getvalue())
        for stdout, error_output in ((None, None), ("stage save2", "actual failure")):
            with self.subTest(stdout=stdout):
                failure = subprocess.TimeoutExpired(["python"], 30, output=stdout, stderr=error_output)
                fixture = self.runtimeDiagnosticFixture(Mock(side_effect=failure))
                stderr = io.StringIO()
                with redirect_stderr(stderr), self.assertRaises(subprocess.TimeoutExpired) as caught:
                    fixture.runChild("unchanged workload")
                self.assertIs(failure, caught.exception)
                self.assertNotIn("[omitted ", stderr.getvalue())
                self.assertIn("stage save2" if stdout else "stdout:\n\nstderr:", stderr.getvalue())
                if error_output:
                    self.assertIn(error_output, stderr.getvalue())

    def testNativePartialStageDiagnosticsRetainCompleteMapTraversalAndBothFullSaveLoads(self):
        import textwrap

        tree = ast.parse((ROOT / "tests/test_octobogz_runtime.py").read_text(encoding="utf-8"))
        fixture = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "testNativeActorDeathsPartialSaveAndLivingRecoveryPreserveIdentityAndRewardOnce"
        )
        code = next(
            node.args[0].value
            for node in ast.walk(fixture)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "runChild"
        )
        child = ast.parse(textwrap.dedent(code))
        calls = [node for node in ast.walk(child) if isinstance(node, ast.Call)]
        self.assertEqual(48, sum(isinstance(node, ast.Assert) for node in ast.walk(child)))
        self.assertEqual(
            2, sum(isinstance(node.func, ast.Attribute) and node.func.attr == "saveWithResult" for node in calls)
        )
        self.assertEqual(
            2, sum(isinstance(node.func, ast.Attribute) and node.func.attr == "loadSavedGame" for node in calls)
        )
        self.assertEqual(
            1,
            sum(
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "jsonify"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "game_map"
                for node in calls
            ),
        )
        stages = {
            node.args[0].value
            for node in calls
            if isinstance(node.func, ast.Name)
            and node.func.id == "markStage"
            and isinstance(node.args[0], ast.Constant)
        }
        for operation in (
            "load",
            "map start",
            "map jsonify",
            "save1",
            "reload1",
            "save2",
            "reload2",
            "pulse",
            "reward",
        ):
            self.assertTrue({operation + " begin", operation + " end"} <= stages, operation)
        marker = next(
            node for node in ast.walk(child) if isinstance(node, ast.FunctionDef) and node.name == "markStage"
        )
        print_call = next(node for node in ast.walk(marker) if isinstance(node, ast.Call) and node.func.id == "print")
        self.assertTrue(next(keyword.value.value for keyword in print_call.keywords if keyword.arg == "flush"))

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

    def decisionReplayFixture(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        expected = {
            "saveSlot": "partial",
            "playerBefore": {"name": "earnedWarrior", "level": 4, "hp": 27, "mana": 123},
            "actorsBefore": [{"slot": "brood", "name": "actualBrood", "hp": 70, "mana": 105}],
            "registryBefore": "octobogzHunt.v1:actual-partial-state",
        }
        result = {
            **deepcopy(expected),
            "seed": 100,
            "success": True,
            "mode": "deterministic-manual-earned-save",
            "playerComposedStatsBefore": {"class": "CStats", "properties": {"normalResist": 0}},
            "cardinalVerified": True,
            "movements": 3,
            "playerAlive": True,
            "defeatReceiptUnchanged": True,
            "sourceUnchanged": True,
            "paidBarriers": 2,
            "decisions": [
                {"action": "Barrier", "manaBefore": 123, "manaAfter": 106, "cost": 17, "refund": 0},
                {"action": "Barrier", "manaBefore": 106, "manaAfter": 106, "cost": 17, "refund": 17},
                {"action": "Attack", "manaBefore": 106, "manaAfter": 106, "cost": 0, "refund": 0},
            ],
            "positivePackets": [
                {
                    "slot": "brood",
                    "damage_roll": 18,
                    "normal": 17,
                    "shadow": 1,
                    "pulse": True,
                    "effect": True,
                    "enemyManaBefore": 105,
                    "enemyManaAfter": 100,
                    "linkedEffect": {
                        "typeId": "octobogzShadowPulseEffect",
                        "caster": "actualBrood",
                        "victim": "earnedWarrior",
                        "duration": 1,
                        "time": 1,
                        "timeTotal": 1,
                        "bonus": {"class": "CStats", "properties": {"shadowResist": -1, "normalResist": 0}},
                    },
                }
            ],
        }
        return walker, expected, result

    def testSavedHeroReplayRequiresExactIdentityRealPaidBarrierAndFiveManaPositivePacket(self):
        walker, expected, result = self.decisionReplayFixture()
        self.assertEqual(result["positivePackets"], walker.validateDecisionReplay(result, expected))
        changes = (
            ("success", False),
            ("mode", "manufactured-combat"),
            ("saveSlot", "other-save"),
            ("playerBefore", {"name": "fabricatedHero", "level": 4, "hp": 27, "mana": 123}),
            ("actorsBefore", [{"slot": "brood", "name": "clone", "hp": 70, "mana": 105}]),
            ("registryBefore", "changed"),
            ("seed", 101),
            ("cardinalVerified", False),
            ("movements", 0),
            ("movements", 513),
            ("playerAlive", False),
            ("defeatReceiptUnchanged", False),
            ("sourceUnchanged", False),
            ("paidBarriers", 0),
            ("positivePackets", []),
        )
        for field, value in changes:
            with self.subTest(field=field, value=value):
                altered = deepcopy(result)
                altered[field] = value
                with self.assertRaises(AssertionError):
                    walker.validateDecisionReplay(altered, expected)
        for field, value in (
            ("shadow", 0),
            ("normal", 18),
            ("pulse", False),
            ("effect", False),
            ("enemyManaAfter", 99),
        ):
            with self.subTest(packet=field):
                altered = deepcopy(result)
                altered["positivePackets"][0][field] = value
                with self.assertRaises(AssertionError):
                    walker.validateDecisionReplay(altered, expected)
        altered = deepcopy(result)
        altered["decisions"][0]["manaAfter"] = 104
        with self.assertRaises(AssertionError):
            walker.validateDecisionReplay(altered, expected)

    def testDecisionReplayCaptureKeepsTheUuidSaveSlotAndExactSerializedCompositionInputs(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player, walker.game_map, walker.mcp_profile_class = "player", "map", "Warrior"
        item = {"properties": {"name": "earnedSword", "typeId": "Sword", "power": 1}}
        data = {
            "properties": {
                "exp": 6125,
                "hp": 27,
                "mana": 123,
                "raceId": "humanRace",
                "posx": 165,
                "posy": 21,
                "posz": 0,
                "baseStats": {"class": "CStats", "properties": {"strength": 7}},
                "levelStats": {"class": "CStats", "properties": {"strength": 2}},
                "effects": [{"class": "BarrierEffect", "properties": {"duration": 2}}],
                "equipped": {"weapon": item},
                "items": [item],
            }
        }
        walker.engine = Mock(return_value=json.dumps(data))
        walker.livingActors = lambda: {"brood": "broodActor", "alpha": "alphaActor"}
        fields = {
            "getName": "actualWarrior",
            "getTypeId": "Warrior",
            "getLevel": 4,
            "getGold": 200,
            "getHpMax": 112,
            "getManaMax": 147,
            "getArchetypeRaceId": "humanRace",
            "getArchetypeClassId": "warriorClass",
        }

        def call(handle, method, *args):
            if handle == "player":
                return fields[method]
            if handle == "map":
                self.assertEqual(("getStringProperty", "octobogzHuntRegistry"), (method, *args))
                return "octobogzHunt.v1:actual-raw-registry"
            if method == "getStringProperty":
                return "charged" if args[0] == "octobogzCombatPhase" else "shadow"
            return {"getName": handle, "getTypeId": "OctoBogz", "getLevel": 1, "getHp": 70, "getMana": 105}[method]

        walker.call = call
        slot = "mcp-octobogz-0123456789abcdef"
        captured = walker.captureDecisionReplayState(slot)
        self.assertEqual(slot, captured["saveSlot"])
        self.assertEqual(["alpha", "brood"], [actor["slot"] for actor in captured["actorsBefore"]])
        for field in ("baseStats", "levelStats", "effects"):
            self.assertEqual(data["properties"][field], captured["playerBefore"][field])
        self.assertEqual("humanRace", captured["playerBefore"]["raceId"])
        self.assertEqual(
            {"name": "earnedSword", "typeId": "Sword", "power": 1}, captured["playerBefore"]["equipment"]["weapon"]
        )
        walker.engine.assert_called_once_with("jsonify", "player")
        data["properties"]["effects"] = None
        walker.engine.return_value = json.dumps(data)
        self.assertIsNone(walker.captureDecisionReplayState(slot)["playerBefore"]["effects"])

    def testReplayRequiresTheActuallyLinkedPulseEffectAndAcceptsAttachedTimeZeroBeforeRemoval(self):
        walker, expected, result = self.decisionReplayFixture()
        for time_left in (0, 1):
            result["positivePackets"][0]["linkedEffect"]["time"] = time_left
            walker.validateDecisionReplay(result, expected)
        for field, value in (
            ("typeId", "flagOnly"),
            ("caster", "otherEnemy"),
            ("victim", "otherPlayer"),
            ("duration", 2),
            ("timeTotal", 2),
            ("time", -1),
            ("time", 2),
        ):
            with self.subTest(field=field, value=value):
                altered = deepcopy(result)
                altered["positivePackets"][0]["linkedEffect"][field] = value
                with self.assertRaises(AssertionError):
                    walker.validateDecisionReplay(altered, expected)
        for field, value in (("shadowResist", 0), ("normalResist", 1)):
            altered = deepcopy(result)
            altered["positivePackets"][0]["linkedEffect"]["bonus"]["properties"][field] = value
            with self.assertRaises(AssertionError):
                walker.validateDecisionReplay(altered, expected)
        del result["positivePackets"][0]["linkedEffect"]
        with self.assertRaises(KeyError):
            walker.validateDecisionReplay(result, expected)

    def testReplayRecoveryConsumesOnlyTheActualLoadedPotionOnceWithItsNativeCappedHeal(self):
        walker, expected, result = self.decisionReplayFixture()
        potion = {"name": "earnedLifePotion", "typeId": "LifePotion", "power": 2}
        expected["playerBefore"]["inventory"] = [potion]
        result["playerBefore"]["inventory"] = [potion]
        healing = {
            "action": "UseItem",
            "item": potion,
            "hpBefore": 28,
            "hpAfter": 72,
            "hpMax": 112,
            "manaBefore": 78,
            "manaAfter": 78,
            "enemyHpBefore": 13,
            "enemyHpAfter": 13,
            "enemyManaBefore": 100,
            "enemyManaAfter": 100,
            "consumedOnce": True,
            "healOnlyDisposable": True,
            "cost": 0,
            "refund": 0,
            "inventoryCountBefore": 4,
            "inventoryCountAfter": 3,
        }
        result["decisions"].append(healing)
        walker.validateDecisionReplay(result, expected)
        for field, value in (
            ("hpAfter", 73),
            ("manaAfter", 79),
            ("enemyHpAfter", 0),
            ("enemyManaAfter", 95),
            ("consumedOnce", False),
            ("healOnlyDisposable", False),
            ("inventoryCountAfter", 4),
            ("item", {"name": "fabricatedPotion", "typeId": "LifePotion", "power": 2}),
        ):
            with self.subTest(field=field):
                altered = deepcopy(result)
                altered["decisions"][-1][field] = value
                with self.assertRaises(AssertionError):
                    walker.validateDecisionReplay(altered, expected)
        result["decisions"].append(healing)
        with self.assertRaises(AssertionError):
            walker.validateDecisionReplay(result, expected)

    def authoredMarketFixture(self, corruption=None):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        walker = OctobogzMcpWalkthroughTest("runTest")
        walker.player, walker.game_map = "player", "map"
        walker.walkTo = Mock()
        actor, market = {"__handle__": "authoredMarketActor"}, {"__handle__": "authoredMarket"}
        metadata = {
            "weak": {
                "name": "earnedBeer",
                "typeId": "DarkBeer",
                "power": 1,
                "heal": True,
                "mana": False,
                "singleUse": True,
            },
            "strong": {
                "name": "earnedLife",
                "typeId": "LifePotion",
                "power": 2,
                "heal": True,
                "mana": False,
                "singleUse": True,
            },
            "mana": {
                "name": "manaBeer",
                "typeId": "SpicedBeer",
                "power": 1,
                "heal": False,
                "mana": True,
                "singleUse": True,
            },
            "dual": {
                "name": "dualPotion",
                "typeId": "RejuvenationPotion",
                "power": 1,
                "heal": True,
                "mana": True,
                "singleUse": True,
            },
            "reusable": {
                "name": "reusableHeal",
                "typeId": "reusableHeal",
                "power": 1,
                "heal": True,
                "mana": False,
                "singleUse": False,
            },
        }
        handles = {name: {"__handle__": name} for name in metadata}
        inventory = list(handles.values())
        stock, purchases, gold = [], [], [200]
        properties = {
            "hp": 91,
            "mana": 175,
            "exp": 6000,
            "level": 4,
            "equipped": {"body": "actualRobe"},
            "uiDefeatReceipt": "",
        }
        walker.object = lambda name: actor
        walker.coords = lambda handle=None: (106, 111, 0)
        walker.questNames = lambda *args: ["unchangedQuest"]

        def engine(name, handle):
            self.assertEqual(("jsonify", "player"), (name, handle))
            return json.dumps({"properties": {**properties, "gold": gold[0], "items": inventory}})

        def call(handle, method, *args):
            if handle == "map":
                return 930 if method == "getTurn" else "unchanged-hunt-registry"
            if handle == "player":
                return list(inventory) if method == "getItems" else gold[0]
            if handle == actor:
                self.assertEqual(("getObjectProperty", "market"), (method, *args))
                return market
            if handle == market:
                if method == "getItems":
                    return list(stock)
                if method == "getBuyCost":
                    return 320
                self.assertEqual("buyItem", method)
                self.assertEqual("player", args[0])
                item = args[1]
                self.assertIn(item, inventory)
                purchases.append(item)
                gold[0] += 319 if corruption == "price" else 320
                stock.append({"__handle__": "fabricatedClone"} if corruption == "clone" else item)
                if corruption != "retained":
                    inventory.remove(item)
                if corruption == "resources":
                    properties["mana"] -= 1
                if corruption == "equipment":
                    properties["equipped"]["body"] = "replacementRobe"
                if corruption == "strong":
                    inventory.remove(handles["strong"])
                return
            data = metadata[handle["__handle__"]]
            if method == "hasTag":
                return data[args[0]]
            if method in ("getNumericProperty", "getBoolProperty"):
                return data[args[0]]
            return data["typeId"] if method == "getTypeId" else data["name"]

        walker.engine, walker.call = engine, call
        walker.fixture_metadata, walker.fixture_properties = metadata, properties
        return walker, handles, inventory, stock, purchases, gold

    def testSorcererMarketPreparationSellsOnlyOwnedWeakHealAndKeepsAllOtherStockAndComposition(self):
        walker, handles, inventory, stock, purchases, gold = self.authoredMarketFixture()
        with patch("builtins.print"):
            walker.sellWeakHealingStockAtAuthoredMarket()
        walker.walkTo.assert_called_once_with("market1")
        self.assertEqual([handles["weak"]], purchases)
        self.assertEqual([handles["weak"]], stock)
        self.assertEqual([handles[name] for name in ("strong", "mana", "dual", "reusable")], inventory)
        self.assertEqual(520, gold[0])
        with patch("builtins.print"):
            walker.sellWeakHealingStockAtAuthoredMarket()
        self.assertEqual([handles["weak"]], purchases)
        self.assertEqual(520, gold[0])

    def testMarketPreparationRejectsClonedRetainedMispricedItemsAndChangedNativeResourcesOrGear(self):
        for corruption in ("price", "clone", "retained", "resources", "equipment", "strong"):
            with self.subTest(corruption=corruption):
                walker, *rest = self.authoredMarketFixture(corruption)
                with patch("builtins.print"), self.assertRaises(AssertionError):
                    walker.sellWeakHealingStockAtAuthoredMarket()
        walker, handles, inventory, stock, purchases, gold = self.authoredMarketFixture()
        inventory.remove(handles["strong"])
        with self.assertRaises(AssertionError):
            walker.sellWeakHealingStockAtAuthoredMarket()
        self.assertEqual([], purchases)
        self.assertEqual(200, gold[0])

    def testOrdinaryMarketPreparationRequiresActualArrivalAndPrecedesTheUnchangedHuntAi(self):
        walker, *rest = self.authoredMarketFixture()
        walker.coords = lambda handle=None: (106, 111, 0) if handle else (107, 111, 0)
        with self.assertRaises(AssertionError):
            walker.sellWeakHealingStockAtAuthoredMarket()
        source = (ROOT / "tests/test_octobogz_mcp.py").read_text(encoding="utf-8")
        methods = {node.name: node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef)}
        route = ast.get_source_segment(
            source, methods["testWarriorAndSorcererFinishThreeRealEncountersWithPartialReloadAndRewardOnce"]
        )
        self.assertLess(
            route.index("self.prepareThroughCatacombs()"), route.index("self.prepareHealingStockAtAuthoredMarket()")
        )
        self.assertLess(
            route.index("self.prepareHealingStockAtAuthoredMarket()"), route.index('self.walkTo("ambientOctobogzNet")')
        )
        self.assertLess(route.index("self.prepareHealingStockAtAuthoredMarket()"), route.index("self.enterHunt()"))
        self.assertIn(
            'if player_class == "Sorcerer":\n                    self.prepareHealingStockAtAuthoredMarket()', route
        )

    def authoredBrewingFixture(self, lessers=6, beers=4, strong_count=5, corruption=None):
        walker, handles, inventory, stock, sales, gold = self.authoredMarketFixture()
        walker.game = "game"
        metadata, properties = walker.fixture_metadata, walker.fixture_properties
        inventory.remove(handles["weak"])
        actor = {"__handle__": "authoredMarketActor"}
        market = {"__handle__": "authoredMarket"}
        station = {"__handle__": "authoredAlchemy"}
        position = [(106, 111, 0)]
        purchases, crafts = [], []

        def add_item(identity, type_id, power, destination):
            item = {"__handle__": identity}
            metadata[identity] = {
                "name": identity,
                "typeId": type_id,
                "power": power,
                "heal": True,
                "mana": False,
                "singleUse": True,
            }
            destination.append(item)
            return item

        for index in range(lessers):
            add_item(f"earnedLesser{index}", "LesserLifePotion", 1, inventory)
        for index in range(beers):
            add_item(f"earnedBeer{index}", "DarkBeer", 1, inventory)
        for index in range(strong_count - 1):
            add_item(f"earnedStrong{index}", "LifePotion", 2, inventory)
        original_stock = [add_item(f"originalShopLesser{index}", "LesserLifePotion", 1, stock) for index in range(3)]
        original_engine, original_call = walker.engine, walker.call
        walker.object = lambda name: station if name == "alchemyTable1" else actor
        walker.coords = lambda handle=None: (
            (105, 110, 0) if handle == station else (106, 111, 0) if handle == actor else position[0]
        )
        walker.walkTo = lambda name: position.__setitem__(
            0, (105, 110, 0) if name == "alchemyTable1" else (106, 111, 0)
        )
        walker.snapshot, walker.pump = Mock(), Mock()

        def call(handle, method, *args):
            if handle == station:
                return {
                    "getType": "CBuilding" if corruption == "stationClass" else "CraftingStation",
                    "getTypeId": "AlchemyTable" if corruption == "stationType" else "alchemyTable1",
                    "getStringProperty": "scribeDesk" if corruption == "stationId" else "alchemyTable",
                    "getBoolProperty": True,
                }[method]
            if handle == market and method == "getSellCost":
                return 400
            if handle == market and method == "sellItem":
                self.assertEqual("player", args[0])
                item = args[1]
                self.assertIn(item, stock)
                purchases.append(item)
                stock.remove(item)
                inventory.append({"__handle__": "clonedPurchase"} if corruption == "purchasedClone" else item)
                gold[0] -= 399 if corruption == "purchasePrice" else 400
                return True
            return original_call(handle, method, *args)

        def engine(name, *args):
            if name != "craftRecipe":
                return original_engine(name, *args)
            self.assertEqual(("game", station, "brew_life_potion"), args)
            self.assertEqual((105, 110, 0), position[0])
            ingredients = [item for item in inventory if metadata[item["__handle__"]]["typeId"] == "LesserLifePotion"]
            self.assertGreaterEqual(len(ingredients), 2)
            self.assertGreaterEqual(gold[0], 20)
            if corruption != "retainedIngredient":
                inventory.remove(ingredients[0])
                inventory.remove(handles["strong"] if corruption == "wrongIngredient" else ingredients[1])
            output = add_item(
                f"craftedLife{len(crafts)}", "LifePotion", 1 if corruption == "outputPower" else 2, inventory
            )
            gold[0] -= 19 if corruption == "craftPrice" else 20
            if corruption == "craftResources":
                properties["mana"] += 1
            crafts.append({"inputs": ingredients[:2], "output": output})
            return {"ok": True, "reason": ""}

        walker.engine, walker.call = engine, call
        return walker, metadata, inventory, stock, sales, purchases, crafts, gold, original_stock, add_item

    def testBasicBrewingUsesTheAuthoredOuterStationAliasAndRejectsOtherStationIdentities(self):
        map_data = json.loads((ROOT / "res/maps/nouraajd/map.json").read_text(encoding="utf-8"))
        authored_station = next(
            obj
            for layer in map_data["layers"]
            for obj in layer.get("objects", [])
            if obj.get("name") == "alchemyTable1"
        )
        self.assertEqual("alchemyTable1", authored_station["type"])
        self.assertEqual(
            (105, 110),
            (authored_station["x"] // authored_station["width"], authored_station["y"] // authored_station["height"]),
        )
        config = json.loads((ROOT / "res/maps/nouraajd/config.json").read_text(encoding="utf-8"))
        buildings = json.loads((ROOT / "res/config/buildings.json").read_text(encoding="utf-8"))
        prototype = buildings[config[authored_station["type"]]["ref"]]
        self.assertEqual("CraftingStation", prototype["class"])
        self.assertEqual("alchemyTable", prototype["properties"]["craftingStationId"])
        walker, _, _, _, _, _, crafts, *_ = self.authoredBrewingFixture(2, 0, 5)
        station = walker.object(authored_station["name"])
        self.assertEqual(authored_station["type"], walker.call(station, "getTypeId"))
        with patch("builtins.print"):
            self.assertEqual(1, walker.brewOwnedBasicLifePotions())
        self.assertEqual(1, len(crafts))
        for corruption in ("stationClass", "stationType", "stationId"):
            with self.subTest(corruption=corruption):
                walker, _, _, _, _, _, crafts, *_ = self.authoredBrewingFixture(2, 0, 5, corruption)
                with self.assertRaises(AssertionError):
                    walker.brewOwnedBasicLifePotions()
                self.assertEqual([], crafts)

    def testBasicPreparationConvertsActualIngredientsAndRetainsTheFiniteThirdForScoutLoot(self):
        walker, metadata, inventory, stock, sales, purchases, crafts, gold, original_stock, add_item = (
            self.authoredBrewingFixture()
        )
        with patch("builtins.print"):
            walker.prepareHealingStockAtAuthoredMarket()
        self.assertEqual(4, len(crafts))
        self.assertEqual(original_stock[:2], purchases)
        self.assertIn(original_stock[2], stock)
        self.assertEqual("originalShopLesser2", walker.retained_lesser_shop_name)
        self.assertEqual(4, len(sales))
        self.assertTrue(all(metadata[item["__handle__"]]["typeId"] == "DarkBeer" for item in sales))
        self.assertEqual(600, gold[0])
        self.assertEqual(9, len([item for item in inventory if metadata[item["__handle__"]]["power"] > 1]))
        self.assertEqual([], walker.basicLesserIngredients(inventory))
        # Actual newly looted stock in this source regression pairs with the untouched third shop identity.
        add_item("actualScoutLesser", "LesserLifePotion", 1, inventory)
        with patch("builtins.print"):
            walker.prepareHealingStockAtAuthoredMarket(initial=False)
        self.assertEqual(original_stock, purchases)
        self.assertEqual(5, len(crafts))
        self.assertEqual(180, gold[0])
        self.assertNotIn(original_stock[2], stock)
        self.assertEqual([], walker.basicLesserIngredients(inventory))
        with patch("builtins.print"):
            walker.prepareHealingStockAtAuthoredMarket(initial=False)
        self.assertEqual(5, len(crafts), "Consumed shop stock must not be recreated or cycled")
        self.assertEqual(original_stock, purchases)

    def testBasicPreparationAdaptsToMeasuredLinuxAndCoverageStockWithoutUnaffordablePurchases(self):
        for lessers, beers, strong, expected_gold, expected_crafts, expected_buys in (
            (0, 0, 17, 200, 0, 0),
            (1, 1, 9, 100, 1, 1),
        ):
            with self.subTest(lessers=lessers, beers=beers):
                walker, metadata, inventory, stock, sales, buys, crafts, gold, original_stock, add_item = (
                    self.authoredBrewingFixture(lessers, beers, strong)
                )
                with patch("builtins.print"):
                    walker.prepareHealingStockAtAuthoredMarket()
                self.assertEqual(expected_gold, gold[0])
                self.assertEqual(expected_crafts, len(crafts))
                self.assertEqual(expected_buys, len(buys))
                self.assertIn(original_stock[-1], stock)
                self.assertEqual([], walker.basicLesserIngredients(inventory))

    def testBasicIngredientPurchaseReservesTheActualBrewingFeeAndNeverBuysAnUnpairableOddItem(self):
        for current_lessers, available_gold, initial, expected_count in (
            (1, 400, False, 0),
            (1, 419, False, 0),
            (1, 420, False, 1),
            (0, 800, False, 0),
            (0, 819, False, 0),
            (0, 820, False, 2),
            (0, 819, True, 0),
            (0, 820, True, 2),
        ):
            with self.subTest(lessers=current_lessers, gold=available_gold, initial=initial):
                walker, metadata, inventory, stock, sales, buys, crafts, gold, original_stock, add_item = (
                    self.authoredBrewingFixture(current_lessers, 0, 5)
                )
                gold[0] = available_gold
                walker.retained_lesser_shop_name = "originalShopLesser2"
                walker.original_lesser_shop_names = tuple(
                    metadata[item["__handle__"]]["name"] for item in original_stock
                )
                walker.purchased_lesser_shop_names = set()
                with patch("builtins.print"):
                    bought = walker.buyFiniteBasicIngredientsAtAuthoredMarket(initial)
                self.assertEqual(expected_count, bought)
                self.assertEqual(expected_count, len(buys))
                self.assertEqual(available_gold - expected_count * 400, gold[0])
                if expected_count == 0:
                    self.assertEqual(original_stock, stock)
                else:
                    self.assertEqual(20, gold[0], "A funded ingredient batch must retain its real brewing fee")
                    self.assertTrue(all(item in inventory and item not in stock for item in buys))

    def testLaterHealingPreparationUsesAffordableUntouchedOriginalPairsAfterReloadWithoutBuyback(self):
        walker, metadata, inventory, stock, sales, buys, crafts, gold, original_stock, add_item = (
            self.authoredBrewingFixture(1, 0, 10)
        )
        with patch("builtins.print"):
            walker.prepareHealingStockAtAuthoredMarket()
        self.assertEqual(520, gold[0])
        self.assertEqual([], buys)
        self.assertTrue(all(item in stock for item in original_stock))
        # The sold earned ingredient must not become eligible alongside the original stock.
        self.assertEqual(4, len(walker.basicLesserIngredients(stock)))
        for original in original_stock:
            identity = original["__handle__"]
            replacement = {"__handle__": "reloaded_" + identity}
            metadata[replacement["__handle__"]] = dict(metadata[identity])
            stock[stock.index(original)] = replacement
        add_item("actualScoutDarkBeer", "DarkBeer", 1, inventory)
        with patch("builtins.print"):
            walker.prepareHealingStockAtAuthoredMarket(initial=False)
        self.assertEqual(1, len(crafts))
        self.assertEqual(20, gold[0])
        self.assertEqual(
            ["originalShopLesser0", "originalShopLesser1"], [metadata[item["__handle__"]]["name"] for item in buys]
        )
        self.assertIn(sales[0], stock, "The sold earned Lesser must never be repurchased")
        self.assertEqual(2, len(walker.basicLesserIngredients(stock)))
        add_item("actualAlphaDarkBeer", "DarkBeer", 1, inventory)
        with patch("builtins.print"):
            walker.prepareHealingStockAtAuthoredMarket(initial=False)
        self.assertEqual(1, len(crafts), "A lone original ingredient must not be paired with a buyback item")
        self.assertEqual(2, len(buys))
        self.assertEqual(340, gold[0])

    def testFiniteOriginalIngredientNamesNeverReenrollPurchasedOrSoldStock(self):
        walker, metadata, inventory, stock, sales, buys, crafts, gold, original_stock, add_item = (
            self.authoredBrewingFixture(1, 1, 5)
        )
        with patch("builtins.print"):
            walker.prepareHealingStockAtAuthoredMarket()
        self.assertEqual(original_stock[:1], buys)
        self.assertEqual(1, len(crafts))
        gold[0] = 820
        with patch("builtins.print"):
            walker.prepareHealingStockAtAuthoredMarket(initial=False)
        self.assertEqual(original_stock, buys, "Both untouched originals remain usable after an initial odd pair")
        self.assertEqual(2, len(crafts))
        self.assertEqual(0, gold[0])
        # Simulate later stock containing an already purchased name and a new unrelated buyback identity.
        add_item("unrelatedSoldLesser", "LesserLifePotion", 1, stock)
        stock.extend(original_stock)
        gold[0] = 2000
        with patch("builtins.print"):
            self.assertEqual(0, walker.buyFiniteBasicIngredientsAtAuthoredMarket(False))
            self.assertEqual(0, walker.buyFiniteBasicIngredientsAtAuthoredMarket(True))
        self.assertEqual(original_stock, buys)
        self.assertEqual(2000, gold[0])

    def testBasicBrewingRejectsWrongInputsOutputPaymentResourcesAndNativePurchaseIdentity(self):
        for corruption in (
            "retainedIngredient",
            "wrongIngredient",
            "outputPower",
            "craftPrice",
            "craftResources",
            "purchasedClone",
            "purchasePrice",
        ):
            with self.subTest(corruption=corruption):
                walker, *rest = self.authoredBrewingFixture(corruption=corruption)
                with patch("builtins.print"), self.assertRaises(AssertionError):
                    walker.prepareHealingStockAtAuthoredMarket()
        walker, *rest = self.authoredBrewingFixture()
        walker.coords = lambda handle=None: (105, 110, 0) if handle else (105, 111, 0)
        with self.assertRaises(AssertionError):
            walker.brewOwnedBasicLifePotions()

    def testBasicPreparationUsesTheExistingCertainRecipeAndServicesRealNewLootBetweenEncounters(self):
        recipes = json.loads((ROOT / "res/config/crafting.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "station": "alchemyTable",
                "inputs": [{"item": "LesserLifePotion", "count": 2}],
                "output": {"item": "LifePotion", "count": 1},
                "gold": 20,
                "successChance": 100,
            },
            recipes["brew_life_potion"],
        )
        source = (ROOT / "tests/test_octobogz_mcp.py").read_text(encoding="utf-8")
        self.assertIn('self.engine("craftRecipe", self.game, station, "brew_life_potion")', source)
        methods = {node.name: node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef)}
        route = ast.get_source_segment(
            source, methods["testWarriorAndSorcererFinishThreeRealEncountersWithPartialReloadAndRewardOnce"]
        )
        after_portal = route[route.index("self.retreatWithOwnedAuthoredScroll()") :]
        self.assertLess(after_portal.index("initial=False"), after_portal.index('self.defeat("alpha")'))
        after_alpha = after_portal[after_portal.index('self.defeat("alpha")') :]
        self.assertLess(after_alpha.index("initial=False"), after_alpha.index('self.defeat("brood")'))
        self.assertEqual(1, route.count("self.retreatWithOwnedAuthoredScroll()"))
        self.assertNotIn("randint", ast.get_source_segment(source, methods["brewOwnedBasicLifePotions"]))

    def testAutomaticActualKillsWithoutPulseStillRequireAnIndependentOrdinaryDecisionWitness(self):
        walker, expected, result = self.decisionReplayFixture()
        walker.phase_observations = [{"pulse": False, "damage_roll": 0, "normal": 0, "shadow": 0}] * 3
        walker.manual_phase_observations = []
        with self.assertRaises(AssertionError):
            walker.assertMeaningfulPulseWitness()
        walker.phase_observations.append(result["positivePackets"][0])
        with self.assertRaises(AssertionError):
            walker.assertMeaningfulPulseWitness()
        walker.manual_phase_observations = walker.validateDecisionReplay(result, expected)
        walker.assertMeaningfulPulseWitness()

    def testNativeDecisionReplayUsesOriginalPrimaryHashAndDoesNotMutateTheActiveMcpSession(self):
        from tests import test_octobogz_mcp as module

        walker, expected, result = self.decisionReplayFixture()
        with TemporaryDirectory() as temporary:
            walker.build_dir = Path(temporary)
            executable = walker.build_dir / (
                "monster_balance_unit_tests.exe" if module.os.name == "nt" else "monster_balance_unit_tests"
            )
            executable.touch()
            save_path = walker.build_dir / "partial.json"
            save_path.write_bytes(b"genuinely-earned-save")
            walker.game, walker.game_map, walker.player = "game", "map", "player"
            walker.state = lambda: {"stage": "cleared"}
            walker.coords = lambda: (110, 111, 0)
            walker.call = lambda handle, method: {"getTurn": 1000, "getHp": 112, "getMana": 147}[method]
            fake_harness = types.SimpleNamespace(extension_dirs=[])
            completed = types.SimpleNamespace(
                returncode=0, stdout="NATIVE_HUNT_DECISION_RESULT " + json.dumps(result) + "\n", stderr=""
            )
            with (
                patch.dict(sys.modules, {"test": fake_harness}),
                patch.object(module.subprocess, "run", return_value=completed) as run,
                patch("builtins.print"),
            ):
                self.assertEqual(
                    result["positivePackets"],
                    walker.replaySavedOrdinaryDefensiveDecisions("partial", save_path, expected),
                )
            self.assertEqual([str(executable), "--hunt-decision", "partial"], run.call_args.args[0])
            self.assertEqual(30, run.call_args.kwargs["timeout"])
            self.assertEqual(walker.build_dir, run.call_args.kwargs["cwd"])
            self.assertTrue(run.call_args.kwargs["capture_output"])
            self.assertEqual(b"genuinely-earned-save", save_path.read_bytes())
            for corruption in ("primary", "session", "resources"):
                with self.subTest(corruption=corruption):
                    save_path.write_bytes(b"genuinely-earned-save")
                    walker.game = "game"
                    walker.coords = lambda: (110, 111, 0)

                    def corrupt(*args, **kwargs):
                        if corruption == "primary":
                            save_path.write_bytes(b"rewritten-by-loader")
                        elif corruption == "session":
                            walker.game = "replaced-game"
                        else:
                            walker.coords = lambda: (109, 111, 0)
                        return completed

                    with (
                        patch.dict(sys.modules, {"test": fake_harness}),
                        patch.object(module.subprocess, "run", side_effect=corrupt),
                        patch("builtins.print"),
                        self.assertRaises(AssertionError),
                    ):
                        walker.replaySavedOrdinaryDefensiveDecisions("partial", save_path, expected)

    def testNativeDecisionReplayCannotSilentlySkipAMissingBinaryInCi(self):
        from tests import test_octobogz_mcp as module

        walker, expected, result = self.decisionReplayFixture()
        with TemporaryDirectory() as temporary:
            walker.build_dir = Path(temporary)
            with (
                patch.dict(sys.modules, {"test": types.SimpleNamespace(extension_dirs=[])}),
                patch.dict(module.os.environ, {"CI": "true"}),
                self.assertRaises(AssertionError),
            ):
                walker.replaySavedOrdinaryDefensiveDecisions("partial", walker.build_dir / "partial.json", expected)
            with (
                patch.dict(sys.modules, {"test": types.SimpleNamespace(extension_dirs=[])}),
                patch.dict(module.os.environ, {"CI": ""}),
                self.assertRaises(unittest.SkipTest),
            ):
                walker.requireDecisionReplayExecutable()

    def testSavedHeroReplayRemainsSeparateFromAutomaticVictoriesAndImmutableSeededComparisons(self):
        source = (ROOT / "tests/test_octobogz_mcp.py").read_text(encoding="utf-8")
        methods = {node.name: node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef)}
        route = ast.get_source_segment(
            source, methods["testWarriorAndSorcererFinishThreeRealEncountersWithPartialReloadAndRewardOnce"]
        )
        self.assertLess(route.index("self.requireDecisionReplayExecutable()"), route.index("for player_class in"))
        self.assertLess(
            route.index('self.snapshot("partial reload")'), route.index("self.captureDecisionReplayState(slot)")
        )
        self.assertLess(
            route.index("self.captureDecisionReplayState(slot)"), route.index("self.retreatWithOwnedAuthoredScroll()")
        )
        self.assertLess(
            route.index('self.snapshot("completed")'), route.index("self.replaySavedOrdinaryDefensiveDecisions(")
        )
        self.assertLess(route.index("self.replaySavedOrdinaryDefensiveDecisions("), route.index("save_path.unlink("))
        self.assertIn('if player_class == "Warrior" else None', route)
        native = (ROOT / "tests/unit/test_monster_balance.cpp").read_text(encoding="utf-8")
        self.assertIn('"--hunt-decision"', native)


if __name__ == "__main__":
    unittest.main()
