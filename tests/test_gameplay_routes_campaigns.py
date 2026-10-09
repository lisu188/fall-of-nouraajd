# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure source-callback regressions for authored campaign route expectations."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from tests.gameplay_routes_campaigns import ritualCountdownAfterTurn


class GameplayCampaignRouteTest(unittest.TestCase):
    def testRitualCountdownUsesTurnBeforeNativeIncrement(self):
        path = Path(__file__).resolve().parents[1] / "res/maps/ritual/script.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        loader = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load")
        trigger = next(
            node for node in loader.body if isinstance(node, ast.ClassDef) and node.name == "RitualTurnTrigger"
        )
        trigger.decorator_list = []
        namespace = {"CTrigger": object, "spawn_wave": Mock()}
        exec(compile(ast.Module(body=[trigger], type_ignores=[]), str(path), "exec"), namespace)
        properties = {"ritual_countdown": 14, "ritual_last_tick_turn": 0, "ritual_last_wave_turn": 0}
        current = {"turn": 0}
        game_map = SimpleNamespace(
            getBoolProperty=lambda name: name == "ritual_active",
            getNumericProperty=lambda name: properties[name],
            setNumericProperty=lambda name, value: properties.update({name: value}),
            getTurn=lambda: current["turn"],
        )
        actor = SimpleNamespace(getMap=lambda: game_map)
        for turn in range(7):
            current["turn"] = turn
            before, last_tick = properties["ritual_countdown"], properties["ritual_last_tick_turn"]
            namespace["RitualTurnTrigger"]().trigger(actor, None)
            self.assertEqual(ritualCountdownAfterTurn(turn, before, last_tick), properties["ritual_countdown"])
        self.assertEqual(14, ritualCountdownAfterTurn(4, 14, 0))
        self.assertEqual(13, ritualCountdownAfterTurn(5, 14, 0))
        self.assertEqual(5, properties["ritual_last_tick_turn"])


if __name__ == "__main__":
    unittest.main()
