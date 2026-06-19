#!/usr/bin/env python3
# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import importlib.util
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class BoolPropertyOwner:
    def __init__(self):
        self.bool_properties = {}

    def getBoolProperty(self, name):
        return self.bool_properties.get(name, False)

    def setBoolProperty(self, name, value):
        self.bool_properties[name] = bool(value)


def load_game_with_native_stub():
    native = types.ModuleType("_game")
    native.CDialogBase2 = type("CDialogBase2", (), {})
    native.configure_playtest_trace = lambda *args, **kwargs: None
    native.get_playtest_trace_records = lambda: []
    native.drain_playtest_trace_records = lambda: []
    native.record_playtest_trace_json = lambda *args, **kwargs: None
    native.playtest_trace_enabled = lambda: False
    native.set_logger_sink = lambda *args, **kwargs: None

    original_native = sys.modules.get("_game")
    sys.modules["_game"] = native
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    try:
        spec = importlib.util.spec_from_file_location("claim_once_game_under_test", REPO_ROOT / "res" / "game.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if original_native is None:
            sys.modules.pop("_game", None)
        else:
            sys.modules["_game"] = original_native


class ClaimOnceHelperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = load_game_with_native_stub()

    def test_claim_once_sets_unclaimed_bool_property(self):
        owner = BoolPropertyOwner()

        self.assertTrue(self.game.claim_once(owner, "reward_claimed"))
        self.assertTrue(owner.getBoolProperty("reward_claimed"))

    def test_claim_once_rejects_repeated_claim_without_clearing_property(self):
        owner = BoolPropertyOwner()

        self.assertTrue(self.game.claim_once(owner, "reward_claimed"))
        self.assertFalse(self.game.claim_once(owner, "reward_claimed"))
        self.assertTrue(owner.getBoolProperty("reward_claimed"))


if __name__ == "__main__":
    unittest.main()
