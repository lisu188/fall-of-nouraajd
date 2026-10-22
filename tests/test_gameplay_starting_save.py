# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Starting fixtures use normal native startup and only the approved reputation change."""

import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import mcp

from tests.gameplay_starting_save import buildStartingSave


class GameplayStartingSaveTest(unittest.TestCase):
    def arguments(self, directory, **changes):
        values = dict(
            build_dir=directory,
            build_config=None,
            slot="mcp-branch-" + "a" * 32,
            reputation=None,
            campaign=None,
            map="ninemarches",
            class_id="Warrior",
            race_id="humanRace",
            seed=17,
        )
        values.update(changes)
        return argparse.Namespace(**values)

    def fixture(self):
        player = SimpleNamespace(properties={"hp": 20, "gold": 10, "reputation": 0})
        player.setNumericProperty = lambda name, value: player.properties.__setitem__(name, value)
        # CMap.getMapName is not a bound Python method. Use the reflected accessor.
        world = SimpleNamespace(getPlayer=lambda: player, getStringProperty=lambda name: "ninemarches")
        context = SimpleNamespace(shutdown=Mock())
        game = SimpleNamespace(getMap=lambda: world, getGui=lambda: None, getContext=lambda: context)
        loop = SimpleNamespace(run=Mock())
        native = SimpleNamespace(
            CGameLoader=SimpleNamespace(loadGame=Mock(return_value=game), startGameWithPlayer=Mock()),
            CMapLoader=SimpleNamespace(saveWithResult=Mock(return_value=True)),
            event_loop=SimpleNamespace(instance=lambda: loop),
            jsonify=lambda object: json.dumps({"properties": object.properties}),
        )
        server = SimpleNamespace(
            _game_module=native,
            _engine_owner=SimpleNamespace(run=lambda callback: callback()),
            import_modules=Mock(),
            close=Mock(),
        )
        module = SimpleNamespace(EngineMcpServer=Mock(return_value=server))
        return player, world, game, native, loop, module

    def threadedFixture(self, failure=""):
        owner, events = mcp.EngineOwner(), []
        self.addCleanup(owner.close, lambda: None)

        def record(action):
            events.append((action, threading.get_ident()))
            if threading.current_thread() is not owner._thread:
                raise RuntimeError("Native fixture called outside its initialized engine owner: " + action)

        class Owned:
            def __init__(self, label):
                self.label = label
                record("created." + label)

            def __del__(self):
                events.append(("released." + self.label, threading.get_ident()))

        class Player(Owned):
            def __init__(self):
                super().__init__("player")
                self.properties = {"hp": 20, "gold": 10, "reputation": 0}

            def setNumericProperty(self, name, value):
                record("player.setNumericProperty")
                self.properties[name] = value

        class World(Owned):
            def __init__(self):
                super().__init__("world")
                self.player = Player()

            def getPlayer(self):
                record("world.getPlayer")
                return self.player

            def getStringProperty(self, name):
                record("world.getStringProperty")
                return "ninemarches"

        class Context(Owned):
            def __init__(self):
                super().__init__("context")

            def shutdown(self):
                record("context.shutdown")

        class Game(Owned):
            def __init__(self):
                super().__init__("game")
                self.world, self.context = World(), Context()

            def getMap(self):
                record("game.getMap")
                return self.world

            def getGui(self):
                record("game.getGui")
                return object() if failure == "gui" else None

            def getContext(self):
                record("game.getContext")
                return self.context

        class Loop(Owned):
            def __init__(self):
                super().__init__("loop")

            def run(self):
                record("loop.run")

        def loadGame():
            record("loadGame")
            return Game()

        def startGame(*arguments):
            record("startGame")
            if failure == "start":
                raise RuntimeError("fixture startup failure")

        def save(world, slot):
            record("save")
            return failure != "save"

        def jsonify(player):
            record("jsonify")
            return json.dumps({"properties": player.properties})

        class Server:
            def __init__(self, *args, **kwargs):
                self._engine_owner = owner
                self._game_module = None

            def import_modules(self):
                def initialize():
                    record("import")
                    if failure == "import":
                        raise RuntimeError("fixture import failure")
                    self._game_module = SimpleNamespace(
                        CGameLoader=SimpleNamespace(loadGame=loadGame, startGameWithPlayer=startGame),
                        CMapLoader=SimpleNamespace(saveWithResult=save),
                        event_loop=SimpleNamespace(instance=Loop),
                        jsonify=jsonify,
                    )

                owner.run(initialize)

            def close(self):
                def cleanup():
                    record("server.cleanup")
                    self._game_module = None

                owner.run(cleanup)

        def startCampaign(*arguments):
            record("campaign.start")
            startGame(*arguments)

        return SimpleNamespace(EngineMcpServer=Server), SimpleNamespace(start=startCampaign), owner, events

    def testNativeStartupAndFinalReleaseStayOnActualEngineOwner(self):
        for campaign_id in (None, "wardensRoad"):
            with self.subTest(campaign=campaign_id), tempfile.TemporaryDirectory() as directory:
                module, campaign, owner, events = self.threadedFixture()
                output = io.StringIO()
                with patch.dict("sys.modules", mcp=module, campaign=campaign), contextlib.redirect_stdout(output):
                    buildStartingSave(self.arguments(directory, campaign=campaign_id, reputation=-3))
                labels = [action for action, _identity in events]
                self.assertEqual({owner._thread.ident}, {identity for _action, identity in events})
                self.assertNotEqual(threading.get_ident(), owner._thread.ident)
                self.assertEqual(3, labels.count("loop.run"))
                self.assertEqual(2, labels.count("jsonify"))
                self.assertEqual(1, labels.count("save"))
                self.assertEqual(1, labels.count("context.shutdown"))
                self.assertEqual(1 if campaign_id else 0, labels.count("campaign.start"))
                self.assertEqual("server.cleanup", labels[-1])
                self.assertEqual(
                    {"released.game", "released.context", "released.world", "released.player", "released.loop"},
                    {label for label in labels if label.startswith("released.")},
                )
                self.assertEqual(["reputation"], json.loads(output.getvalue())["changedPlayerProperties"])

    def testNativeFailuresReleaseSessionAndCloseServerOnOwner(self):
        for failure, message in (
            ("import", "fixture import failure"),
            ("start", "fixture startup failure"),
            ("gui", "Ordinary initial state"),
            ("save", "engine refused to save"),
        ):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                module, campaign, owner, events = self.threadedFixture(failure)
                output = io.StringIO()
                with patch.dict("sys.modules", mcp=module, campaign=campaign), contextlib.redirect_stdout(output):
                    with self.assertRaisesRegex(RuntimeError, message):
                        buildStartingSave(self.arguments(directory))
                labels = [action for action, _identity in events]
                self.assertEqual({owner._thread.ident}, {identity for _action, identity in events})
                self.assertEqual("server.cleanup", labels[-1])
                self.assertEqual(0 if failure == "import" else 1, labels.count("context.shutdown"))
                self.assertEqual(
                    {label.removeprefix("created.") for label in labels if label.startswith("created.")},
                    {label.removeprefix("released.") for label in labels if label.startswith("released.")},
                )
                self.assertEqual("", output.getvalue())

    def testOrdinaryStartupUsesBoundMapAccessorAndLeavesPlayerUnchanged(self):
        player, world, game, native, loop, module = self.fixture()
        with tempfile.TemporaryDirectory() as directory, patch.dict("sys.modules", mcp=module):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                buildStartingSave(self.arguments(directory))
        native.CGameLoader.startGameWithPlayer.assert_called_once_with(game, "ninemarches", "Warrior", "humanRace")
        self.assertEqual(3, loop.run.call_count)
        self.assertEqual({"hp": 20, "gold": 10, "reputation": 0}, player.properties)
        receipt = json.loads(output.getvalue())
        self.assertEqual("ninemarches", receipt["map"])
        self.assertEqual([], receipt["changedPlayerProperties"])
        self.assertEqual(17, module.EngineMcpServer.call_args.kwargs["test_seed"])

    def testApprovedReputationChangesOnlyTheInitialReputation(self):
        for reputation in (-7, -6, -3):
            player, world, game, native, loop, module = self.fixture()
            with self.subTest(reputation=reputation), tempfile.TemporaryDirectory() as directory:
                with patch.dict("sys.modules", mcp=module), contextlib.redirect_stdout(io.StringIO()) as output:
                    buildStartingSave(self.arguments(directory, reputation=reputation))
                self.assertEqual(["reputation"], json.loads(output.getvalue())["changedPlayerProperties"])
                self.assertEqual({"hp": 20, "gold": 10, "reputation": reputation}, player.properties)

    def testCampaignUsesRealCampaignStartup(self):
        player, world, game, native, loop, module = self.fixture()
        campaign = SimpleNamespace(start=Mock())
        with tempfile.TemporaryDirectory() as directory, patch.dict("sys.modules", mcp=module, campaign=campaign):
            with contextlib.redirect_stdout(io.StringIO()):
                buildStartingSave(self.arguments(directory, campaign="wardensRoad", map=None))
        campaign.start.assert_called_once_with(game, "wardensRoad", "Warrior", "humanRace")
        native.CGameLoader.startGameWithPlayer.assert_not_called()

    def testUnownedSlotsAndUnapprovedReputationAreRejectedBeforeNativeStartup(self):
        for changes in ({"slot": "player-save"}, {"reputation": -8}, {"reputation": -3, "map": "test"}):
            player, world, game, native, loop, module = self.fixture()
            with self.subTest(changes=changes), patch.dict("sys.modules", mcp=module), self.assertRaises(ValueError):
                buildStartingSave(self.arguments(".", **changes))
            module.EngineMcpServer.assert_not_called()

    def testHeadlessAndSaveFailuresRemainFailures(self):
        for failure in ("gui", "save"):
            player, world, game, native, loop, module = self.fixture()
            if failure == "gui":
                game.getGui = lambda: object()
            else:
                native.CMapLoader.saveWithResult.return_value = False
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                with patch.dict("sys.modules", mcp=module), self.assertRaises(RuntimeError):
                    buildStartingSave(self.arguments(directory))
