# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Observe authored hooks at their real suspension boundaries without a native build."""

import ast
import gc
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import weakref

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "res") not in sys.path:
    sys.path.insert(0, str(ROOT / "res"))

import ui


def objectClasses():
    registered = {}
    api = ModuleType("game")
    from tests.hook_flow_support import installHookFlows

    installHookFlows(api)
    api.resumableHook, api.uiRequest, api.flowGame = ui.resumableHook, ui.uiRequest, ui.flowGame
    api.showRewardReceiptFlow = lambda *args: None
    api.showReader = Mock(side_effect=AssertionError("A native hook entered its synchronous reader"))
    api.requirementMessage, api.randint = Mock(), Mock()
    api.CBuilding, api.CScroll = object, object
    api.Coords = lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)
    api.register = lambda _context: lambda cls: registered.setdefault(cls.__name__, cls)

    def claim(owner, flag):
        if owner.getBoolProperty(flag):
            return False
        owner.setBoolProperty(flag, True)
        return True

    api.claim_once = claim
    specification = importlib.util.spec_from_file_location("async_authored_objects", ROOT / "res/plugins/object.py")
    module = importlib.util.module_from_spec(specification)
    with patch.dict(sys.modules, {"game": api}):
        specification.loader.exec_module(module)
        module.load(None, None)
    return registered, api


class FirstPartyHookFlowTest(unittest.TestCase):
    def testDialogActionFlowValidatesBothNamesAndDefersItsTraceUntilExecution(self):
        tree = ast.parse((ROOT / "res/game.py").read_text(encoding="utf-8"))
        dialog = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "CDialog")
        trace, failures = [], []
        namespace = {
            "CDialogBase2": object,
            "record_playtest_trace": lambda event, **kwargs: trace.append((event, kwargs)),
            "playtest_object_ref": lambda _dialog: {},
            "_reportDialogFailure": lambda *args: failures.append(args),
            "logger": Mock(),
        }
        exec(compile(ast.Module(body=[dialog], type_ignores=[]), "authored_dialog", "exec"), namespace)

        class Dialog(namespace["CDialog"]):
            def action(self):
                raise AssertionError("The native action called the synchronous adapter")

            def actionFlow(self):
                yield ui.uiRequest("gui.showConfirm", "Question", "Body", "Yes", "No")
                raise ValueError("Original authored action failure")

            def orphanFlow(self):
                yield ui.uiRequest("gui.showMessage", "Unregistered original action")

        receiver = Dialog()
        for action in ("missing", "_private", "orphan", "action()"):
            self.assertIsNone(receiver.getActionFlow(action))
        callback = receiver.getActionFlow("action")
        self.assertEqual([], trace)
        flow = callback()
        self.addCleanup(flow.close)
        self.assertEqual("gui.showConfirm", next(flow)["operation"])
        self.assertEqual(["dialog_action"], [event for event, _kwargs in trace])
        with self.assertRaisesRegex(ValueError, "Original authored action failure"):
            flow.send(True)
        self.assertEqual(["dialog_action", "dialog_action_failed"], [event for event, _kwargs in trace])
        self.assertEqual("ValueError", trace[-1][1]["error"])
        self.assertEqual(1, len(failures))

    def testDialogCancellationDoesNotBecomeAnAuthoredFailure(self):
        tree = ast.parse((ROOT / "res/game.py").read_text(encoding="utf-8"))
        dialog = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "CDialog")
        failures = []
        namespace = {
            "CDialogBase2": object,
            "record_playtest_trace": Mock(),
            "playtest_object_ref": lambda _dialog: {},
            "_reportDialogFailure": lambda *args: failures.append(args),
            "logger": Mock(),
        }
        exec(compile(ast.Module(body=[dialog], type_ignores=[]), "authored_dialog", "exec"), namespace)

        class Dialog(namespace["CDialog"]):
            def action(self):
                pass

            def actionFlow(self):
                yield ui.uiRequest("gui.showMessage", "Acknowledgment")

        flow = Dialog().getActionFlow("action")()
        next(flow)
        flow.close()
        self.assertEqual([], failures)

    def testChestClaimsBeforeSuspendingAndPreservesTheNativeLootArguments(self):
        from tests.test_chest_rewards import ChestRewardsTest

        fixture = ChestRewardsTest()
        fixture.setUp()
        flow = fixture.chest.onEnterFlow(fixture.event)
        self.addCleanup(flow.close)
        self.assertEqual({"operation": "gui.addRandomLoot", "args": (fixture.player, 60), "kwargs": {}}, next(flow))
        self.assertTrue(fixture.properties["looted"])
        fixture.engine.getRngHandler.return_value.addRandomLoot.assert_not_called()
        flow.close()
        with self.assertRaises(StopIteration):
            next(fixture.chest.onEnterFlow(fixture.event))

    def testTownPortalWaitsForAuthoredArrivalHooksWithoutCallingSynchronousMovement(self):
        classes, _api = objectClasses()
        scroll = classes["TownPortalScroll"]()
        player = Mock()
        player.getMap.return_value = SimpleNamespace(getEntryX=lambda: 12, getEntryY=lambda: 8, getEntryZ=lambda: 2)
        flow = scroll.onUseFlow(SimpleNamespace(getCause=lambda: player))
        self.addCleanup(flow.close)
        self.assertEqual({"operation": "gui.itemMoveTo", "args": (player, 12, 8, 2), "kwargs": {}}, next(flow))
        player.moveTo.assert_not_called()
        with self.assertRaises(StopIteration):
            flow.send(None)
        self.assertTrue(scroll.isDisposable())

    def testTownPortalCancellationBeforePositionDispatchCannotPrecommitItsUse(self):
        classes, _api = objectClasses()
        scroll = classes["TownPortalScroll"]()
        player = Mock()
        player.getMap.return_value = SimpleNamespace(getEntryX=lambda: 12, getEntryY=lambda: 8, getEntryZ=lambda: 2)
        flow = scroll.onUseFlow(SimpleNamespace(getCause=lambda: player))
        request = next(flow)
        self.assertEqual("gui.itemMoveTo", request["operation"])
        self.assertEqual((player, 12, 8, 2), request["args"])
        flow.close()
        player.moveTo.assert_not_called()
        with self.assertRaises(StopIteration):
            next(flow)

    def testTownPortalItemMovementOpcodeKeepsTheSynchronousPythonBoundary(self):
        player = Mock()

        def flow():
            yield ui.uiRequest("gui.itemMoveTo", player, 12, 8, 2)

        ui.runUiFlow(None, flow())
        player.moveTo.assert_called_once_with(12, 8, 2)

    def testMultilevelStairsAwaitArrivalBeforeRecordingTheTransition(self):
        from tests.test_narrative_consequences import loadMapClasses

        stairs = loadMapClasses("multilevel")["LevelStairs"]()
        game_map, player = Mock(), Mock()
        game_map.canStep.return_value = True
        game_map.getNumericProperty.return_value = 2
        player.getBoolProperty.return_value = False
        player.isPlayer.return_value = True
        stairs.getMap = lambda: game_map
        stairs.target = lambda: SimpleNamespace(x=4, y=1, z=1)
        stairs.getCoords = lambda: SimpleNamespace(x=4, y=1, z=0)
        stairs.getName = lambda: "stairsUp"
        flow = stairs.onEnterFlow(SimpleNamespace(getCause=lambda: player))
        self.addCleanup(flow.close)
        self.assertEqual((player, 4, 1, 1), next(flow)["args"])
        player.setBoolProperty.assert_called_once_with("multilevelTransitionGuard", True)
        game_map.setStringProperty.assert_not_called()
        player.setCoords.assert_not_called()
        with self.assertRaises(StopIteration):
            flow.send(None)
        game_map.setStringProperty.assert_called_once_with("lastLevelTransition", "stairsUp")
        game_map.setNumericProperty.assert_called_once_with("levelTransitionCount", 3)
        game_map.setBoolProperty.assert_called_once_with("used_stairs_up", True)
        player.getBoolProperty.return_value = True
        with self.assertRaises(StopIteration):
            next(stairs.onEnterFlow(SimpleNamespace(getCause=lambda: player)))
        self.assertEqual(("multilevelTransitionGuard", False), player.setBoolProperty.call_args.args)

    def testCaveRegistersEachSpawnBeforeAwaitingMovementAndPreservesItsRoll(self):
        classes, api = objectClasses()
        cave = classes["Cave"]()
        game_map, player, monster = Mock(), Mock(), Mock()
        player.isPlayer.return_value = True
        game_map.canStep.side_effect = lambda coords: coords.x == 7 and coords.y == 7
        game_map.getObjectByName.return_value = cave
        cave.getMap = lambda: game_map
        cave.getCoords = lambda: SimpleNamespace(x=8, y=8, z=0)
        flags, values, strings = {"enabled": True}, {"chance": 100, "monsters": 1}, {}
        cave.getBoolProperty = lambda name: flags.get(name, False)
        cave.setBoolProperty = lambda name, value: flags.__setitem__(name, value)
        cave.setNumericProperty = lambda name, value: values.__setitem__(name, value)
        cave.getStringProperty = lambda name: strings.get(name, "")
        cave.setStringProperty = lambda name, value: strings.__setitem__(name, value)
        monster.getName.return_value = "spawnedMonster"
        cave.getObjectProperty = lambda _name: SimpleNamespace(clone=lambda: monster)
        cave.getName = lambda: "cave1"
        cave.incProperty = Mock()
        cave.getNumericProperty = lambda name: values.get(name, 0)
        flow = cave.onEnterFlow(SimpleNamespace(getCause=lambda: player))
        self.addCleanup(flow.close)
        self.assertEqual((monster, 7, 7, 0), next(flow)["args"])
        game_map.addObject.assert_called_once_with(monster)
        monster.moveTo.assert_not_called()
        self.assertEqual("gui.removeObject", flow.send(None)["operation"])
        self.assertEqual(8, game_map.canStep.call_count)
        with self.assertRaises(StopIteration):
            flow.send(None)
        api.randint.assert_not_called()
        game_map.addObject.reset_mock()
        flags.update(enabled=True, lairOpened=False)
        api.randint.return_value = 50
        flow = cave.onTurnFlow(None)
        self.addCleanup(flow.close)
        self.assertEqual((monster, 8, 8, 0), next(flow)["args"])
        api.randint.assert_called_once_with(1, 100)
        game_map.addObject.assert_called_once_with(monster)
        cave.incProperty.assert_called_once_with("monsters", -1)
        with self.assertRaises(StopIteration):
            flow.send(None)
        cave.incProperty.assert_called_once_with("monsters", -1)

    def testRemovalFlowsPreserveNameOrderAndExcludeNewSnapshotEntries(self):
        tree = ast.parse((ROOT / "res/game.py").read_text(encoding="utf-8"))
        names = {"removeObjectFlow", "removeObjectByNameFlow", "removeObjectsFlow"}
        namespace = {"uiRequest": ui.uiRequest}
        exec(
            compile(
                ast.Module(
                    body=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names],
                    type_ignores=[],
                ),
                "authored_removal",
                "exec",
            ),
            namespace,
        )
        objects = [SimpleNamespace(getName=lambda name=name: name) for name in ("b", "a", "c")]
        game_map = SimpleNamespace(getObjects=lambda: objects, getObjectByName=lambda _name: None)
        observed = []

        def predicate(obj):
            observed.append(obj.getName())
            return True

        flow = namespace["removeObjectsFlow"](game_map, predicate)
        self.addCleanup(flow.close)
        self.assertEqual("a", next(flow)["args"][1].getName())
        objects[:] = [objects[2], SimpleNamespace(getName=lambda: "d")]
        self.assertEqual("b", flow.send(None)["args"][1].getName())
        self.assertEqual("c", flow.send(None)["args"][1].getName())
        with self.assertRaises(StopIteration):
            flow.send(None)
        self.assertEqual(["a", "b", "c"], observed)
        with self.assertRaises(StopIteration):
            next(namespace["removeObjectByNameFlow"](game_map, "missing"))

    def testCompoundArtifactWaitsForTheChoiceAndUnwrapsTheGameOnlyForTheGrant(self):
        from tests.test_session_deferred_work import Session, SessionDeferredWorkTest

        artifacts, _legacy = SessionDeferredWorkTest().artifactModule()
        definition = {"id": "demoSet", "label": "Demo set"}
        runtime = SimpleNamespace(
            set_for_combined=lambda _identity: definition,
            assemblyDetail=lambda *_args, **_kwargs: "The existing equipment preview.",
            disassemble=Mock(return_value=True),
        )
        artifacts.get_runtime = lambda: runtime
        session, player, item = Session(), Mock(), Mock()
        player.isPlayer.return_value = True
        player.getGame.return_value = session
        player.getSlotWithItem.return_value = None
        flow = artifacts.offerDisassemblyFlow(item, player)
        self.addCleanup(flow.close)
        self.assertEqual("gui.showChoice", next(flow)["operation"])
        session.handler.showChoice.assert_not_called()
        runtime.disassemble.assert_not_called()
        with self.assertRaises(StopIteration):
            flow.send("demoSet")
        runtime.disassemble.assert_called_once_with(session, player, item)
        session.handler.notify.assert_called_once_with("You separate the Demo set into its pieces.")

    def testCraftingWaitsForSelectionAndKeepsItsExistingRecipeAndRngConsumption(self):
        from tests.test_ui_dialogue import CraftingChoiceTest, FakeItem

        fixture = CraftingChoiceTest()
        fixture.setUp()
        fixture.recipe["success_chance"] = 99
        fixture.runtime._recipes = {fixture.recipe["id"]: fixture.recipe}
        fixture.module._RUNTIME = fixture.runtime
        fixture.module.randint = Mock(return_value=50)
        handler = SimpleNamespace(showChoice=Mock())
        session = SimpleNamespace(
            getGuiHandler=lambda: handler,
            getObjectHandler=lambda: SimpleNamespace(createObject=lambda _game, item_id: FakeItem(item_id)),
        )
        station = SimpleNamespace(
            getGame=lambda: session,
            getStringProperty=lambda name: {"craftingStationId": "alchemy", "label": "Alchemy"}.get(name, ""),
        )
        flow = fixture.module.openCraftingStationFlow(station, fixture.player)
        self.addCleanup(flow.close)
        self.assertEqual("gui.showChoice", next(flow)["operation"])
        self.assertEqual(1, fixture.player.countItems("Herb"))
        self.assertEqual(10, fixture.player.gold)
        fixture.module.randint.assert_not_called()
        self.assertEqual("gui.showChoice", flow.send("firstRecipe")["operation"])
        self.assertEqual(0, fixture.player.countItems("Herb"))
        self.assertEqual(1, fixture.player.countItems("PotionA"))
        self.assertEqual(7, fixture.player.gold)
        fixture.module.randint.assert_called_once_with(1, 100)
        handler.showChoice.assert_not_called()
        with self.assertRaises(StopIteration):
            flow.send("")

    def testSpawnGroupRecoverySkipsPlacedOrRemovedActorsWithoutNewGrants(self):
        tree = ast.parse((ROOT / "res/game.py").read_text(encoding="utf-8"))
        spawn = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "spawnObjectsFlow"
        )
        namespace = {
            "json": json,
            "uiRequest": ui.uiRequest,
            "Coords": lambda x, y, z: SimpleNamespace(x=x, y=y, z=z),
        }
        exec(compile(ast.Module(body=[spawn], type_ignores=[]), "authored_spawn", "exec"), namespace)
        progress, registered, created = {}, {}, []
        owner, game_map, session = Mock(), Mock(), Mock()
        owner.getStringProperty.side_effect = lambda name: progress.get(name, "")
        owner.setStringProperty.side_effect = lambda name, value: progress.__setitem__(name, value)
        game_map.getGame.return_value = session
        game_map.canStep.return_value = True
        game_map.getObjectByName.side_effect = registered.get
        game_map.addObject.side_effect = lambda actor: registered.__setitem__(actor.getName(), actor)

        def create(_type_id):
            actor = Mock()
            actor.getName.return_value = "spawn" + str(len(created))
            created.append(actor)
            return actor

        session.createObject.side_effect = create
        placements = [("monster", 7 + index, 8, 0) for index in range(3)]
        spawn_flow = namespace["spawnObjectsFlow"]
        first = spawn_flow(game_map, owner, "pending", placements)
        self.assertEqual("gui.moveTo", next(first)["operation"])
        created[0].getCoords.return_value = SimpleNamespace(x=7, y=8, z=0)
        first.close()
        saved = json.loads(progress["pending"])
        self.assertEqual(0, saved["index"])
        self.assertEqual("spawn0", saved["actor"])
        # The actual move finished before cancellation reached its posted Python continuation.
        second = spawn_flow(game_map, owner, "pending", placements)
        request = next(second)
        self.assertIs(created[1], request["args"][0])
        second.close()
        # A pending actor killed by its entry hook must not be recreated on restore.
        registered.pop("spawn1")
        third = spawn_flow(game_map, owner, "pending", placements)
        self.addCleanup(third.close)
        request = next(third)
        self.assertIs(created[2], request["args"][0])
        with self.assertRaises(StopIteration):
            third.send(None)
        self.assertEqual("", progress["pending"])
        self.assertEqual(3, len(created))
        self.assertEqual(3, game_map.addObject.call_count)
        self.assertEqual(3, game_map.canStep.call_count)

    def testSynchronousSpawnOpcodeAdapterPreservesItsCoordinatesAndAnswer(self):
        game_map = Mock()
        game_map.addObjectByName.return_value = "createdType"
        coords = lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)

        def flow():
            return (yield ui.uiRequest("gui.addObjectByName", game_map, "monster", 7, 8, 2))

        with patch.dict(sys.modules, {"game": SimpleNamespace(Coords=coords)}):
            self.assertEqual("createdType", ui.runUiFlow(None, flow()))
        kind, target = game_map.addObjectByName.call_args.args
        self.assertEqual("monster", kind)
        self.assertEqual((7, 8, 2), (target.x, target.y, target.z))

    def testCampfireLootPrecedesItsNotificationAndRemoval(self):
        classes, api = objectClasses()
        campfire = classes["Campfire"]()
        player = Mock()
        player.isPlayer.return_value = True
        player.gold = 0
        player.addGold.side_effect = lambda amount: setattr(player, "gold", player.gold + amount)
        engine, game_map = Mock(), Mock()
        game_map.getGame.return_value = engine
        game_map.getObjectByName.return_value = campfire
        campfire.getMap = lambda: game_map
        campfire.getName = lambda: "campfire"
        campfire.getNumericProperty = lambda name: {"gold": 23, "value": 17}[name]
        flags = {}
        campfire.getBoolProperty = lambda name: flags.get(name, False)
        campfire.setBoolProperty = lambda name, value: flags.__setitem__(name, value)
        flow = campfire.onEnterFlow(SimpleNamespace(getCause=lambda: player))
        self.addCleanup(flow.close)
        self.assertEqual((player, 17), next(flow)["args"])
        self.assertEqual(23, player.gold)
        engine.getGuiHandler.return_value.notify.assert_not_called()
        game_map.removeObjectByName.assert_not_called()
        removal = flow.send(None)
        self.assertEqual("gui.removeObject", removal["operation"])
        self.assertEqual((game_map, campfire), removal["args"])
        engine.getGuiHandler.return_value.notify.assert_called_once()
        game_map.removeObjectByName.assert_not_called()
        game_map.removeObject.assert_not_called()
        with self.assertRaises(StopIteration):
            flow.send(None)
        api.randint.assert_not_called()

    def testCancelledCampfireLootCannotGrantAgainBeforeItsRemoval(self):
        classes, _api = objectClasses()
        campfire = classes["Campfire"]()
        flags = {}
        campfire.getBoolProperty = lambda name: flags.get(name, False)
        campfire.setBoolProperty = lambda name, value: flags.__setitem__(name, value)
        campfire.getNumericProperty = lambda name: {"gold": 23, "value": 17}[name]
        campfire.getName = lambda: "campfire"
        game_map, player = Mock(), Mock()
        game_map.getObjectByName.return_value = campfire
        campfire.getMap = lambda: game_map
        player.isPlayer.return_value = True
        event = SimpleNamespace(getCause=lambda: player)
        flow = campfire.onEnterFlow(event)
        self.assertEqual("gui.addRandomLoot", next(flow)["operation"])
        flow.close()
        # Ordinary serialized properties restore the claimed object before cleanup resumes.
        saved_flags = dict(flags)
        flags.clear()
        flags.update(saved_flags)
        retry = campfire.onEnterFlow(event)
        self.addCleanup(retry.close)
        self.assertEqual("gui.removeObject", next(retry)["operation"])
        player.addGold.assert_called_once_with(23)
        with self.assertRaises(StopIteration):
            retry.send(None)

    def testCancelledCaveTurnConsumesItsRegisteredSpawnBudget(self):
        classes, api = objectClasses()
        cave = classes["Cave"]()
        values = {"chance": 100, "monsters": 1}
        cave.getNumericProperty = lambda name: values[name]
        cave.incProperty = lambda name, amount: values.__setitem__(name, values[name] + amount)
        cave.getBoolProperty = lambda name: name == "enabled"
        cave.getCoords = lambda: SimpleNamespace(x=8, y=8, z=0)
        monster, game_map = Mock(), Mock()
        cave.getMap = lambda: game_map
        cave.getObjectProperty = lambda _name: SimpleNamespace(clone=lambda: monster)
        api.randint.return_value = 1
        flow = cave.onTurnFlow(None)
        self.assertEqual("gui.moveTo", next(flow)["operation"])
        flow.close()
        self.assertEqual(0, values["monsters"])
        with self.assertRaises(StopIteration):
            next(cave.onTurnFlow(None))
        game_map.addObject.assert_called_once_with(monster)
        api.randint.assert_called_once_with(1, 100)

    def testCancelledCaveOpeningResumesItsExactActorAndBoundedRemainingCells(self):
        classes, api = objectClasses()
        cave = classes["Cave"]()
        flags, values, strings, actors = {"enabled": True}, {}, {}, {}
        cave.getBoolProperty = lambda name: flags.get(name, False)
        cave.setBoolProperty = lambda name, value: flags.__setitem__(name, value)
        cave.getNumericProperty = lambda name: values.get(name, 0)
        cave.setNumericProperty = lambda name, value: values.__setitem__(name, value)
        cave.getStringProperty = lambda name: strings.get(name, "")
        cave.setStringProperty = lambda name, value: strings.__setitem__(name, value)
        cave.getCoords = lambda: SimpleNamespace(x=8, y=8, z=0)
        cave.getName = lambda: "cave"
        cave.getObjectProperty = Mock()
        cloned = []

        def clone():
            actor = Mock()
            actor.getName.return_value = "lairMonster" + str(len(cloned))
            cloned.append(actor)
            return actor

        cave.getObjectProperty.return_value.clone.side_effect = clone
        game_map = Mock()
        cave.getMap = lambda: game_map
        game_map.getObjectByName.side_effect = lambda name: cave if name == "cave" else actors.get(name)
        game_map.addObject.side_effect = lambda actor: actors.__setitem__(actor.getName(), actor)
        game_map.canStep.return_value = True
        event = SimpleNamespace(getCause=lambda: SimpleNamespace(isPlayer=lambda: True))
        first = cave.onEnterFlow(event)
        initial = next(first)
        self.assertEqual((cloned[0], 7, 7, 0), initial["args"])
        first.close()
        self.assertFalse(flags["enabled"])
        # Simulate restoring the serialized cursor/name and actor graph after a save.
        restored = classes["Cave"]()
        restored.__dict__.update(cave.__dict__)
        recovery = restored.onTurnFlow(None)
        self.addCleanup(recovery.close)
        resumed = next(recovery)
        self.assertIs(cloned[0], resumed["args"][0])
        destinations = [resumed["args"][1:]]
        while True:
            request = recovery.send(None)
            if request["operation"] == "gui.removeObject":
                break
            destinations.append(request["args"][1:])
        self.assertEqual(8, len(cloned))
        self.assertEqual(8, len(set(destinations)))
        self.assertNotIn((8, 8, 0), destinations)
        self.assertEqual(8, values["lairSpawnIndex"])
        self.assertEqual("", strings["lairSpawnName"])
        recovery.close()
        cleanup = restored.onTurnFlow(None)
        self.addCleanup(cleanup.close)
        self.assertEqual("gui.removeObject", next(cleanup)["operation"])
        self.assertEqual(8, len(cloned))
        api.randint.assert_not_called()

    def testTombAppliesItsExistingHpTollOnlyAfterLootFinishes(self):
        classes, _api = objectClasses()
        tomb = classes["WarriorsTomb"]()
        flags = {"enabled": True}
        tomb.getBoolProperty = lambda name: flags.get(name, False)
        tomb.setBoolProperty = lambda name, value: flags.__setitem__(name, value)
        tomb.getNumericProperty = lambda name: {"damage": 30, "value": 90}[name]
        engine = Mock()
        tomb.getMap = lambda: SimpleNamespace(getGame=lambda: engine)
        player = Mock()
        player.isPlayer.return_value = True
        player.getHp.return_value, player.getHpMax.return_value = 50, 100
        flow = tomb.onEnterFlow(SimpleNamespace(getCause=lambda: player))
        self.addCleanup(flow.close)
        self.assertEqual((player, 90), next(flow)["args"])
        self.assertFalse(flags["enabled"])
        player.setHp.assert_not_called()
        with self.assertRaises(StopIteration):
            flow.send(None)
        player.setHp.assert_called_once_with(20)

    def testCancelledTombLootSettlesItsTollOnceWithoutUsingTheClosedSession(self):
        classes, _api = objectClasses()
        tomb = classes["WarriorsTomb"]()
        flags = {"enabled": True}
        tomb.getBoolProperty = lambda name: flags.get(name, False)
        tomb.setBoolProperty = lambda name, value: flags.__setitem__(name, value)
        tomb.getNumericProperty = lambda name: {"damage": 30, "value": 90}[name]
        engine, player = Mock(), Mock()
        tomb.getMap = lambda: SimpleNamespace(getGame=lambda: engine)
        player.isPlayer.return_value = True
        player.getHp.return_value, player.getHpMax.return_value = 50, 100
        event = SimpleNamespace(getCause=lambda: player)
        flow = tomb.onEnterFlow(event)
        self.assertEqual("gui.addRandomLoot", next(flow)["operation"])
        # Loot selection settlement survives context shutdown; the guardian's toll must too.
        player.getHpMax.side_effect = AssertionError("The inactive context cannot recompute stats")
        tomb.getMap = Mock(side_effect=AssertionError("Cancelled settlement cannot obtain a session service"))
        flow.close()
        flow.close()
        player.setHp.assert_called_once_with(20)
        self.assertFalse(flags["enabled"])
        engine.getGuiHandler.assert_not_called()

    def testNouraajdSpawnCancellationRetainsCommittedQuestStateAndItems(self):
        from tests.test_ui_dialogue import FakeDialog, loadClasses

        for name, method, state_name in (
            ("CaveTrigger", "trigger", "rolf"),
            ("QuestDialog", "start_amulet_quest", "amulet"),
        ):
            with self.subTest(hook=name):
                session, game_map, player, actor = Mock(), Mock(), Mock(), Mock()
                session.getMap.return_value = game_map
                session.createObject.return_value = actor
                game_map.getPlayer.return_value = player
                progress = {"amulet": "not_started"}
                state = SimpleNamespace(
                    get_state=lambda key: progress.get(key, "not_started"),
                    start_amulet=lambda: progress.update(amulet="active"),
                    mark_rolf_skull_found=lambda _player: progress.update(rolf="skull_recovered"),
                )
                namespace = {
                    "CTrigger": FakeDialog,
                    "CDialog": FakeDialog,
                    "_quest_system_from": lambda _obj: state,
                    "_grant_quest": Mock(),
                }
                loadClasses("res/maps/nouraajd/script.py", [name], namespace)
                obj = namespace[name]()
                obj.game = session
                flow = getattr(obj, method + "Flow")(*(Mock(), None) if method == "trigger" else ())
                self.assertEqual("gui.moveTo", next(flow)["operation"])
                flow.close()
                self.assertEqual(
                    "active" if state_name == "amulet" else "skull_recovered", progress.get(state_name, "not_started")
                )
                if state_name == "amulet":
                    namespace["_grant_quest"].assert_called_once_with(player, "amuletQuest")
                    with self.assertRaises(StopIteration):
                        next(obj.start_amulet_questFlow())
                    session.createObject.assert_called_once_with("goblinThief")
                else:
                    player.addItem.assert_called_once_with("skullOfRolf")

    def testCancelledVictorRewardCannotBecomeATimeoutOrRepeatTheGrant(self):
        from tests.test_ui_dialogue import FakeDialog, loadClasses

        session, game_map, player = Mock(), Mock(), Mock()
        session.getMap.return_value = game_map
        game_map.getPlayer.return_value = player
        flags, progress = {}, {"state": "encounter_active"}
        game_map.getBoolProperty.side_effect = lambda flag: flags.get(flag, False)
        game_map.setBoolProperty.side_effect = lambda flag, value: flags.__setitem__(flag, value)
        session.createObject.return_value.getStates.return_value = []
        state = SimpleNamespace(
            get_state=lambda _key: progress["state"],
            mark_victor_good_end=lambda: progress.update(state="good_end"),
        )

        def claim(owner, key):
            if owner.getBoolProperty(key):
                return False
            owner.setBoolProperty(key, True)
            return True

        def receipt(*_args):
            yield ui.uiRequest("gui.showMessage", "Rescued daughter")

        namespace = {
            "CTrigger": FakeDialog,
            "_quest_system_from": lambda _obj: state,
            "claim_once": claim,
            "rewardSnapshot": lambda _player: {},
            "showRewardReceiptFlow": receipt,
            "narrative": SimpleNamespace(victorResponse=lambda _game: ""),
        }
        loadClasses("res/maps/nouraajd/script.py", ["CultLeaderQuestTrigger"], namespace)
        trigger = namespace["CultLeaderQuestTrigger"]()
        trigger.game = session
        flow = trigger.triggerFlow(None, None)
        self.assertEqual("gui.showMessage", next(flow)["operation"])
        flow.close()
        self.assertEqual("good_end", progress["state"])
        self.assertTrue(flags["pendingVictorCleanup"])
        with self.assertRaises(StopIteration):
            next(trigger.triggerFlow(None, None))
        player.addGold.assert_called_once_with(500)
        player.healProc.assert_called_once_with(100)

    def testVictorEncounterRestoresItsSpawnCursorAndExactRegisteredActors(self):
        tree = ast.parse((ROOT / "res/maps/nouraajd/script.py").read_text(encoding="utf-8"))
        spawn = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "spawnVictorEncounterFlow"
        )
        flags, actors, created, clears = {}, {}, [], []
        game_map, session = Mock(), Mock()
        session.getMap.return_value = game_map
        game_map.getStringProperty.side_effect = lambda key: flags.get(key, "")
        game_map.setStringProperty.side_effect = lambda key, value: flags.__setitem__(key, value)
        game_map.getObjectByName.side_effect = actors.get
        game_map.addObject.side_effect = lambda actor: actors.__setitem__(actor.name, actor)
        state = SimpleNamespace(
            get_state=lambda _key: "courtyard_known", victor_good_end=lambda: False, mark_victor_encounter_active=Mock()
        )

        def create(kind):
            actor = Mock()
            if kind != "CTargetController":
                actor.setStringProperty.side_effect = lambda _key, value: setattr(actor, "name", value)
                created.append(actor)
            return actor

        def clear(game_map):
            clears.append(game_map)
            yield from ()

        def find(_map, preferred, reserved):
            reserved.add(preferred)
            return SimpleNamespace(x=preferred[0], y=preferred[1], z=preferred[2])

        session.createObject.side_effect = create
        namespace = {
            "json": json,
            "flowGame": lambda game: game,
            "uiRequest": ui.uiRequest,
            "_quest_system_from": lambda _owner: state,
            "clearVictorEncounterFlow": clear,
            "_find_victor_spawn_coords": find,
            "VICTOR_COURTYARD_LEADER_SPAWN": (45, 100, 0),
            "VICTOR_COURTYARD_SPAWNS": [(44, 100, 0), (46, 100, 0)],
            "VICTOR_CULTIST_PREFIX": "victorCultist",
        }
        exec(compile(ast.Module(body=[spawn], type_ignores=[]), "victor_spawn_flow", "exec"), namespace)
        owner = SimpleNamespace(getGame=lambda: session)
        spawn_flow = namespace["spawnVictorEncounterFlow"]
        first = spawn_flow(owner)
        self.assertEqual("gui.moveTo", next(first)["operation"])
        created[0].getCoords.return_value = SimpleNamespace(x=45, y=100, z=0)
        first.close()
        second = spawn_flow(owner)
        target = next(second)
        self.assertIs(created[1], target["args"][0])
        second.close()
        flags.update(json.loads(json.dumps(flags)))
        third = spawn_flow(owner)
        self.assertIs(created[1], next(third)["args"][0])
        request = third.send(None)
        self.assertIs(created[2], request["args"][0])
        with self.assertRaises(StopIteration) as stopped:
            third.send(None)
        self.assertTrue(stopped.exception.value)
        self.assertEqual(3, len(created))
        self.assertEqual([game_map], clears)
        self.assertEqual("", flags["pendingVictorEncounter"])
        game_map.setNumericProperty.assert_called_once_with("VICTOR_CULTISTS_PLACED", 2)
        state.mark_victor_encounter_active.assert_called_once()

    def testRitualLeaderRecoverySkipsAnAlreadyCompletedPlacement(self):
        tree = ast.parse((ROOT / "res/maps/ritual/script.py").read_text(encoding="utf-8"))
        spawn = next(
            node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "trySpawnLeaderFlow"
        )
        namespace = {"uiRequest": ui.uiRequest}
        exec(compile(ast.Module(body=[spawn], type_ignores=[]), "ritual_leader_flow", "exec"), namespace)
        flags, registered = {}, {}
        game_map, session, leader = Mock(), Mock(), Mock()
        game_map.getGame.return_value = session
        session.createObject.return_value = leader
        marker = SimpleNamespace(getCoords=lambda: SimpleNamespace(x=7, y=8, z=0))
        game_map.getObjectByName.side_effect = lambda name: marker if name == "bossSpawn" else registered.get(name)
        game_map.getBoolProperty.side_effect = lambda key: flags.get(key, False)
        game_map.setBoolProperty.side_effect = lambda key, value: flags.__setitem__(key, value)
        game_map.addObject.side_effect = lambda actor: registered.__setitem__("ritualLeader", actor)
        flow = namespace["trySpawnLeaderFlow"](game_map)
        self.assertEqual("gui.moveTo", next(flow)["operation"])
        leader.getCoords.return_value = marker.getCoords()
        flow.close()
        with self.assertRaises(StopIteration):
            next(namespace["trySpawnLeaderFlow"](game_map))
        self.assertTrue(flags["leader_spawned"])
        session.createObject.assert_called_once_with("ritualLeaderTemplate")
        game_map.addObject.assert_called_once_with(leader)

    def testRecoveredRitualWaveFinalizesDestroyedAnchorsBeforeTheNextTick(self):
        from tests.test_ui_dialogue import FakeDialog, loadClasses

        values = {"ritual_last_tick_turn": 1, "ritual_last_wave_turn": 1, "anchors_destroyed_count": 3}
        flags = {"ritual_active": True}
        pending = {"pendingRitualWave": "saved wave"}
        game_map = Mock()
        game_map.getBoolProperty.side_effect = lambda key: flags.get(key, False)
        game_map.setBoolProperty.side_effect = lambda key, value: flags.__setitem__(key, value)
        game_map.getStringProperty.side_effect = lambda key: pending.get(key, "")
        game_map.getNumericProperty.side_effect = lambda key: values.get(key, 0)
        game_map.setNumericProperty.side_effect = lambda key, value: values.__setitem__(key, value)
        game_map.getTurn.return_value = 1

        def wave(_map):
            yield ui.uiRequest("gui.moveTo", "pending-wave-actor", 7, 8, 0)
            pending.clear()

        def leader(_map):
            yield ui.uiRequest("gui.moveTo", "ritual-leader", 9, 8, 0)

        namespace = {"CTrigger": FakeDialog, "spawnWaveFlow": wave, "trySpawnLeaderFlow": leader}
        tree = ast.parse((ROOT / "res/maps/ritual/script.py").read_text(encoding="utf-8"))
        update = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "updateAnchorProgressFlow"
        )
        exec(compile(ast.Module(body=[update], type_ignores=[]), "ritual_anchor_flow", "exec"), namespace)
        loadClasses("res/maps/ritual/script.py", ["RitualTurnTrigger"], namespace)
        trigger = namespace["RitualTurnTrigger"]()
        flow = trigger.triggerFlow(SimpleNamespace(getMap=lambda: game_map), None)
        self.addCleanup(flow.close)
        self.assertEqual("pending-wave-actor", next(flow)["args"][0])
        self.assertEqual("ritual-leader", flow.send(None)["args"][0])
        self.assertTrue(flags["anchors_destroyed"])

    def testSuspendedReaderKeepsOnlyAWeakGameResolver(self):
        classes, api = objectClasses()

        class Session:
            pass

        session = Session()
        reference = weakref.ref(session)
        game_map = SimpleNamespace(getGame=reference)
        sign = classes["SignPost"]()
        sign.getMap = lambda: game_map
        sign.getStringProperty = lambda _name: "Authored sign text"
        flow = sign.onEnterFlow(SimpleNamespace(getCause=lambda: SimpleNamespace(isPlayer=lambda: True)))
        self.addCleanup(flow.close)
        request = next(flow)
        self.assertEqual("showReader", request["operation"])
        self.assertEqual(("Signpost", "Authored sign text"), request["args"][1:])
        self.assertIsInstance(request["args"][0], ui.UiFlowGame)
        del session
        gc.collect()
        self.assertIsNone(reference())
        api.showReader.assert_not_called()

    def testRewardReceiptFlowMatchesTheSynchronousBodyWithoutKeepingTheGameAlive(self):
        tree = ast.parse((ROOT / "res/game.py").read_text(encoding="utf-8"))
        names = {"rewardSnapshot", "rewardReceiptText", "showRewardReceipt", "showRewardReceiptFlow"}
        received = []
        namespace = {
            "flowGame": ui.flowGame,
            "uiRequest": ui.uiRequest,
            "showReader": lambda _game, title, body: received.append((title, body)),
        }
        exec(
            compile(
                ast.Module(
                    body=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names],
                    type_ignores=[],
                ),
                "authored_receipt",
                "exec",
            ),
            namespace,
        )
        player = SimpleNamespace(
            getItems=lambda: [], getEquipped=lambda: {}, getGold=lambda: 40, getNumericProperty=lambda _name: 70
        )

        class Session:
            def getMap(self):
                return SimpleNamespace(getPlayer=lambda: player)

        session = Session()
        reference = weakref.ref(session)
        before = {"gold": 10, "experience": 20, "items": {}}
        namespace["showRewardReceipt"](session, "Title", before, "Authored acknowledgment")
        flow = namespace["showRewardReceiptFlow"](session, "Title", before, "Authored acknowledgment")
        self.addCleanup(flow.close)
        request = next(flow)
        self.assertEqual("showReader", request["operation"])
        self.assertEqual(received[0], request["args"][1:])
        self.assertIn("Gold: +30", request["args"][2])
        self.assertIn("Experience: +50", request["args"][2])
        del session
        gc.collect()
        self.assertIsNone(reference())

    def testRewardCommitMarkerFollowsTheGrantAndPrecedesAcknowledgment(self):
        from tests.test_narrative_consequences import loadMapClasses

        classes = loadMapClasses("siege")
        session = Mock()
        session.player.gold = 7
        session.map.getPlayer.return_value = session.player
        session.getMap.return_value = session.map
        session.map.getGame.return_value = session
        flags = {}
        session.map.getBoolProperty.side_effect = lambda name: flags.get(name, False)
        session.map.setBoolProperty.side_effect = lambda name, value: flags.__setitem__(name, value)
        session.player.addGold.side_effect = lambda amount: setattr(
            session.player, "gold", session.player.gold + amount
        )
        quest = classes["DefendSiegeQuest"](session)
        flow = quest.onCompleteFlow()
        self.addCleanup(flow.close)
        request = next(flow)
        self.assertEqual("gui.questCommitted", request["operation"])
        self.assertTrue(flags["siege_reward_claimed"])
        self.assertTrue(flags["campaign_completed"])
        self.assertGreater(session.player.gold, 7)
        session.getGuiHandler.return_value.showCampaignScreen.assert_not_called()
        flow.close()
        with self.assertRaises(StopIteration):
            next(quest.onCompleteFlow())

    def testFinalHuntDeathAwaitsQuestReceiptsAfterSavingItsClearedState(self):
        from tests.test_octobogz_hunt import OctobogzHuntTest

        fixture = OctobogzHuntTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.director.start(fixture.game_map)
        fixture.kill("scout")
        fixture.kill("alpha")
        brood = fixture.game_map.getObjectByName(fixture.state()["slots"]["brood"]["name"])
        brood.setHp(0)
        flow = fixture.director.actorRemovedFlow(brood)
        self.addCleanup(flow.close)
        request = next(flow)
        self.assertEqual("gui.removeObject", request["operation"])
        self.assertIs(fixture.game_map, request["args"][0])
        fixture.game_map.removeObject(request["args"][1])
        request = flow.send(None)
        self.assertEqual("gui.checkQuests", request["operation"])
        self.assertIs(fixture.game_map.player, request["args"][0])
        self.assertEqual("cleared", fixture.state()["stage"])
        self.assertTrue(fixture.game_map.getBoolProperty("octobogzHuntCleared"))
        self.assertIsNone(fixture.game_map.getObjectByName("cave2"))
        fixture.game_map.player.checkQuests.assert_not_called()
        with self.assertRaises(StopIteration):
            flow.send(None)

    def testAuthoredFlowMethodsContainNoDirectModalOrQuestPollingCalls(self):
        modal_names = {
            "showReader",
            "showRewardReceipt",
            "showDialog",
            "showTrade",
            "showInfo",
            "showQuestion",
            "showConfirm",
            "showChoice",
            "showSelection",
            "addRandomLoot",
            "checkQuests",
            "complete_scenario",
            "retryPending",
        }
        paths = [
            *sorted((ROOT / "res/maps").glob("*/script.py")),
            ROOT / "res/plugins/object.py",
            ROOT / "res/plugins/castle_campaign.py",
            ROOT / "res/plugins/crafting.py",
            ROOT / "res/plugins/artifact_sets.py",
            ROOT / "res/plugins/octobogz_hunt.py",
        ]
        checked = 0
        for path in paths:
            for method in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(method, ast.FunctionDef):
                    continue
                if not any(isinstance(item, ast.Name) and item.id == "resumableHook" for item in method.decorator_list):
                    continue
                checked += 1
                for node in ast.walk(method):
                    if isinstance(node, ast.Call):
                        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                        self.assertNotIn(name, modal_names, (path.name, method.name, node.lineno))
        self.assertGreaterEqual(checked, 80)

    def testCancelledIntroductionsCommitTheirMainQuestBeforeTheReader(self):
        from tests.test_narrative_consequences import loadMapClasses

        for name, cls_name in (
            ("hearthfall", "HearthfallStart"),
            ("gravemoor", "GravemoorStart"),
            ("usurpergate", "UsurpergateStart"),
        ):
            with self.subTest(map=name):
                flags = {}
                session, game_map, player = Mock(), Mock(), Mock()
                session.getMap.return_value = game_map
                game_map.getGame.return_value = session
                game_map.getPlayer.return_value = player
                game_map.getNumericProperty.return_value = 0
                game_map.getBoolProperty.side_effect = lambda flag: flags.get(flag, False)
                game_map.setBoolProperty.side_effect = lambda flag, value: flags.__setitem__(flag, value)
                player.getQuests.return_value = []
                player.getStringProperty.return_value = ""
                player.isPlayer.return_value = True
                start = loadMapClasses(name)[cls_name](session)
                start.getName = lambda: "start"
                game_map.getObjects.return_value = [start]
                event = SimpleNamespace(getCause=lambda: player)
                flow = start.onEnterFlow(event)
                self.assertEqual("showReader", next(flow)["operation"])
                flow.close()
                self.assertTrue(flags.get(name + "_intro", False))
                player.addQuest.assert_called_once_with(name + "Quest")
                retried = start.onEnterFlow(event)
                self.addCleanup(retried.close)
                self.assertEqual("gui.removeObject", next(retried)["operation"])
                player.addQuest.assert_called_once_with(name + "Quest")
                self.assertTrue(flags[name + "_intro"])

    def testCancelledBossReceiptsResumeWithoutRepeatingRewardsOrRegisteredSpawns(self):
        from tests.test_narrative_consequences import loadMapClasses

        def receipt(*_args, **_kwargs):
            yield ui.uiRequest("gui.showMessage", "Boss reward receipt")

        for name, cls_name, claim in (
            ("kadath", "OnyxThrone", "throne_taken"),
            ("ninemarches", "DigSite", "crown_taken"),
            ("sunderedmarch", "DigSite", "crown_taken"),
            ("vhulmarn", "AltarThreshold", "tithe_taken"),
        ):
            with self.subTest(map=name):
                flags, registered = {}, {}
                session, game_map, player, boss, controller = Mock(), Mock(), Mock(), Mock(), Mock()
                session.getMap.return_value = game_map
                session.createObject.side_effect = lambda kind: controller if kind == "CTargetController" else boss
                game_map.getGame.return_value = session
                game_map.getPlayer.return_value = player
                game_map.getBoolProperty.side_effect = lambda flag: flags.get(flag, False)
                game_map.setBoolProperty.side_effect = lambda flag, value: flags.__setitem__(flag, value)
                game_map.getNumericProperty.return_value = 6
                game_map.getObjectByName.side_effect = registered.get
                boss_name = []
                boss.setStringProperty.side_effect = lambda _key, value: boss_name.append(value)
                game_map.addObject.side_effect = lambda obj: registered.__setitem__(boss_name[-1], obj)
                player.isPlayer.return_value = True
                player.gold = 0
                event = SimpleNamespace(getCause=lambda: player)
                obj = loadMapClasses(name, {"showRewardReceiptFlow": receipt})[cls_name](session)
                flow = obj.onEnterFlow(event)
                self.assertEqual("gui.showMessage", next(flow)["operation"])
                self.assertTrue(flags[claim])
                flow.close()
                player.addItem.assert_called_once()
                session.createObject.assert_not_called()
                # Restoring ordinary flags after the receipt must still wake the authored boss.
                flags.update(dict(flags))
                recovery = obj.onTurnFlow(None)
                self.assertEqual("gui.moveTo", next(recovery)["operation"])
                recovery.close()
                self.assertFalse(flags.get("boss_woken", False))
                self.assertEqual(1, len(registered))
                # Cancellation during movement reuses that exact registered actor on retry.
                recovery = obj.onTurnFlow(None)
                self.addCleanup(recovery.close)
                self.assertEqual(boss, next(recovery)["args"][0])
                self.assertEqual("gui.checkQuests", recovery.send(None)["operation"])
                self.assertTrue(flags["boss_woken"])
                with self.assertRaises(StopIteration):
                    recovery.send(None)
                with self.assertRaises(StopIteration):
                    next(obj.onTurnFlow(None))
                game_map.addObject.assert_called_once_with(boss)
                player.addItem.assert_called_once()
                self.assertEqual(2, session.createObject.call_count)
