"""Check that reconstructed historical configs retain observed creature state."""

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "creature_recovery", ROOT / "recovery/upstream/config/reconstruct_creatures.py"
)
CREATURES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CREATURES)


class HistoricalCreatureConfigTest(unittest.TestCase):
    def testSavedCreatureStatsAndActionsRemainIntact(self):
        saved = {
            "hp": 49,
            "mana": 56,
            "initStats": {"strength": 8, "stamina": 7, "main": "I"},
            "actions": ["Attack"],
            "isPlayer": False,
        }
        source = {"state": {"Monster": {"PritzMage": [saved]}}}
        config = CREATURES.buildCreatureConfig(["images/monsters/pritzmage/0.png.REMOVED.git-id"], source)
        for key, value in saved.items():
            self.assertEqual(config["PritzMage"][key], value)

    def testSpeciesAndMainStatsFollowHistoricalImageIds(self):
        paths = ["images/players/assasin/0.png", "images/players/sorcerer/0.png", "images/monsters/pritz/0.png"]
        config = CREATURES.buildCreatureConfig(paths, {})
        self.assertEqual(set(config), {"Assasin", "Sorcerer", "Pritz"})
        self.assertEqual(config["Assasin"]["initStats"]["main"], "A")
        self.assertEqual(config["Sorcerer"]["initStats"]["main"], "I")
        self.assertTrue(config["Assasin"]["isPlayer"])
        self.assertFalse(config["Pritz"]["isPlayer"])
        for entry in config.values():
            self.assertGreater(entry["hp"], 0)
            self.assertGreater(entry["mana"], 0)
            self.assertTrue(entry["actions"])
            self.assertTrue(entry["levelStats"])

    def testUnknownOrEmptySpeciesCannotBecomeEmptyStub(self):
        for paths in ([], ["images/monsters/unknown/0.png"]):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                CREATURES.buildCreatureConfig(paths, {})


if __name__ == "__main__":
    unittest.main()
