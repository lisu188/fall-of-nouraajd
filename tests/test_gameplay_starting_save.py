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
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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
        game = SimpleNamespace(getMap=lambda: world, getGui=lambda: None)
        loop = SimpleNamespace(run=Mock())
        native = SimpleNamespace(
            CGameLoader=SimpleNamespace(loadGame=Mock(return_value=game), startGameWithPlayer=Mock()),
            CMapLoader=SimpleNamespace(saveWithResult=Mock(return_value=True)),
            event_loop=SimpleNamespace(instance=lambda: loop),
            jsonify=lambda object: json.dumps({"properties": object.properties}),
        )
        server = SimpleNamespace(_game_module=native, import_modules=Mock())
        module = SimpleNamespace(EngineMcpServer=Mock(return_value=server))
        return player, world, game, native, loop, module

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
