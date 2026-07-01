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


class _FakeObjectHandler:
    def __init__(self, subtypes):
        self._subtypes = list(subtypes)

    def getAllSubTypes(self, base_type):
        assert base_type == "CCreatureRace"
        return list(self._subtypes)


class _FakeRace:
    def __init__(self, type_id, player_selectable, label=""):
        self._type_id = type_id
        self._player_selectable = player_selectable
        self._label = label

    def getBoolProperty(self, name):
        assert name == "playerSelectable"
        return self._player_selectable

    def getStringProperty(self, name):
        assert name == "label"
        return self._label


class _FakeGame:
    def __init__(self, races):
        self._races = races
        self._handler = _FakeObjectHandler(races.keys())

    def getObjectHandler(self):
        return self._handler

    def createObject(self, type_id):
        return self._races[type_id]


class PlayerRaceOptionsTest(unittest.TestCase):
    def test_player_race_options_match_native_filter(self):
        g = game.CGameLoader.loadGame()
        options = game.player_race_options(g)

        expected_options = {}
        for race_type in sorted(g.getObjectHandler().getAllSubTypes("CCreatureRace")):
            race = g.createObject(race_type)
            if not race.getBoolProperty("playerSelectable"):
                continue
            label = race.getStringProperty("label") or race_type
            expected_options[label] = race_type

        self.assertEqual(expected_options, options)

    def test_player_race_options_filters_and_labels(self):
        g = _FakeGame(
            {
                "humanRace": _FakeRace("humanRace", True, "Human"),
                "elfRace": _FakeRace("elfRace", True, "Elf"),
                "goblinRace": _FakeRace("goblinRace", False, "Goblin"),
                "wraithRace": _FakeRace("wraithRace", True),
            }
        )
        self.assertEqual(
            {"Human": "humanRace", "Elf": "elfRace", "wraithRace": "wraithRace"},
            game.player_race_options(g),
        )

    def test_player_race_options_rejects_duplicate_labels(self):
        g = _FakeGame(
            {
                "humanRace": _FakeRace("humanRace", True, "Human"),
                "highHumanRace": _FakeRace("highHumanRace", True, "Human"),
            }
        )
        with self.assertRaises(ValueError):
            game.player_race_options(g)


class _FakeStats:
    def __init__(self, strength=0, agility=0, stamina=0, intelligence=0):
        self._strength = strength
        self._agility = agility
        self._stamina = stamina
        self._intelligence = intelligence

    def getStrength(self):
        return self._strength

    def getAgility(self):
        return self._agility

    def getStamina(self):
        return self._stamina

    def getIntelligence(self):
        return self._intelligence


class _FakeRaceWithStats:
    def __init__(self, base_stats):
        self._base_stats = base_stats

    def getBaseStats(self):
        return self._base_stats


class RaceStatPreviewTest(unittest.TestCase):
    def test_neutral_race_reads_balanced(self):
        self.assertEqual("Balanced", game.race_stat_preview(_FakeRaceWithStats(_FakeStats())))

    def test_missing_base_stats_reads_balanced(self):
        self.assertEqual("Balanced", game.race_stat_preview(_FakeRaceWithStats(None)))

    def test_deltas_are_formatted_in_order_with_signs(self):
        base = _FakeStats(strength=1, agility=-1, stamina=2, intelligence=-2)
        self.assertEqual("STR+1 AGI-1 STA+2 INT-2", game.race_stat_preview(_FakeRaceWithStats(base)))

    def test_only_nonzero_deltas_are_shown(self):
        base = _FakeStats(agility=2, intelligence=1)
        self.assertEqual("AGI+2 INT+1", game.race_stat_preview(_FakeRaceWithStats(base)))


if __name__ == "__main__":
    unittest.main()
