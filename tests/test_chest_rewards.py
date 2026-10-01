# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class ChestRewardsTest(unittest.TestCase):
    def setUp(self):
        registered = {}
        game = types.ModuleType("game")
        for name in ("CBuilding", "CScroll", "Coords"):
            setattr(game, name, type(name, (), {}))
        for name in ("showReader", "requirementMessage", "randint"):
            setattr(game, name, Mock())
        game.register = lambda context: lambda cls: registered.setdefault(cls.__name__, cls)

        def claim(owner, name):
            if owner.getBoolProperty(name):
                return False
            owner.setBoolProperty(name, True)
            return True

        game.claim_once = claim
        with patch.dict(sys.modules, {"game": game}):
            spec = importlib.util.spec_from_file_location("chest_plugin_under_test", ROOT / "res/plugins/object.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.load(None, None)
        self.chest = registered["Chest"]()
        self.properties = {}
        self.chest.getBoolProperty = lambda name: self.properties.get(name, False)
        self.chest.setBoolProperty = lambda name, value: self.properties.__setitem__(name, value)
        self.chest.getNumericProperty = lambda name: 60
        self.player = Mock()
        self.player.isPlayer.return_value = True
        self.player.isAlive.return_value = True
        self.map = Mock()
        self.map.getPlayer.return_value = self.player
        self.map.getObjectByName.return_value = self.chest
        self.chest.getMap = lambda: self.map
        self.chest.getName = lambda: "valeChest"
        self.engine = Mock()
        self.chest.getGame = lambda: self.engine
        self.event = types.SimpleNamespace(getCause=lambda: self.player)

    def testRepeatedVisitsAndReloadCannotPayTwice(self):
        self.chest.onEnter(self.event)
        saved_properties = dict(self.properties)
        self.chest.onEnter(self.event)
        self.properties.clear()
        self.properties.update(saved_properties)
        self.chest.onEnter(self.event)
        self.engine.getRngHandler.return_value.addRandomLoot.assert_called_once_with(self.player, 60)

    def testNpcMissingAndForeignPlayerVisitsCannotPay(self):
        npc = Mock()
        npc.isPlayer.return_value = False
        foreign = Mock()
        foreign.isPlayer.return_value = True
        for cause in (None, npc, foreign):
            self.chest.onEnter(types.SimpleNamespace(getCause=lambda value=cause: value))
        self.chest.onEnter(None)
        self.engine.getRngHandler.return_value.addRandomLoot.assert_not_called()
        self.assertFalse(self.properties)

    def testReentrantLootVisitCannotPayTwice(self):
        rng = self.engine.getRngHandler.return_value

        def revisit(*args):
            if rng.addRandomLoot.call_count == 1:
                self.chest.onEnter(self.event)

        rng.addRandomLoot.side_effect = revisit
        self.chest.onEnter(self.event)
        rng.addRandomLoot.assert_called_once_with(self.player, 60)


if __name__ == "__main__":
    unittest.main()
