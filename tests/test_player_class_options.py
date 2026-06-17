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
import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = REPO_ROOT / "cmake-build-release"

if str(BUILD_DIR) not in sys.path:
    sys.path.insert(0, str(BUILD_DIR))
for config in ("Release", "Debug", "RelWithDebInfo", "MinSizeRel"):
    config_dir = BUILD_DIR / config
    if config_dir.exists() and str(config_dir) not in sys.path:
        sys.path.insert(0, str(config_dir))
if str(REPO_ROOT / "res") not in sys.path:
    sys.path.insert(1, str(REPO_ROOT / "res"))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(2, str(REPO_ROOT))

try:
    game = importlib.import_module("game")
except Exception as exc:  # pragma: no cover - mirrors runtime dependency availability.
    raise unittest.SkipTest(f"game module is unavailable: {exc}") from exc


class PlayerClassOptionsTest(unittest.TestCase):
    def test_player_class_options_use_class_labels_without_descriptions(self):
        g = game.CGameLoader.loadGame()
        options = game.player_class_options(g)

        expected_options = {}
        for player_type in sorted(g.getObjectHandler().getAllSubTypes("CPlayer")):
            player = g.createObject(player_type)
            label = player.getStringProperty("label") or player_type
            expected_options[label] = player_type

        self.assertEqual(expected_options, options)
        self.assertGreater(len(options), 0)
        for option in options:
            with self.subTest(option=option):
                self.assertNotIn(" - ", option)


if __name__ == "__main__":
    unittest.main()
