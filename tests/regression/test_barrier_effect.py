import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeInteraction:
    pass


class FakeStats:
    def __init__(self):
        self.values = {}

    def setNumericProperty(self, name, value):
        self.values[name] = value

    def getNumericProperty(self, name):
        return self.values.get(name, 0)


class FakeGame:
    def createObject(self, type_id):
        if type_id != "CStats":
            raise AssertionError(f"unexpected object type: {type_id}")
        return FakeStats()


class FakeCaster:
    def __init__(self):
        self.game = FakeGame()

    def getGame(self):
        return self.game


class FakeEffect:
    def __init__(self, caster):
        self.caster = caster
        self.bonus = None

    def getCaster(self):
        return self.caster

    def setBonus(self, bonus):
        self.bonus = bonus


class BarrierEffectRegressionTest(unittest.TestCase):
    def setUp(self):
        self.registered = {}
        self.previous_game_module = sys.modules.get("game")

        game_module = types.ModuleType("game")
        game_module.CInteraction = FakeInteraction
        game_module.randint = lambda lower, upper: lower

        def register(_context):
            def decorator(cls):
                self.registered[cls.__name__] = cls
                return cls

            return decorator

        game_module.register = register
        sys.modules["game"] = game_module

        spec = importlib.util.spec_from_file_location(
            "barrier_interaction_plugin",
            REPO_ROOT / "res/plugins/interaction.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.load(None, object())

    def tearDown(self):
        if self.previous_game_module is None:
            sys.modules.pop("game", None)
        else:
            sys.modules["game"] = self.previous_game_module

    def test_barrier_configures_focused_normal_damage_resistance(self):
        effect = FakeEffect(FakeCaster())

        configured = self.registered["Barrier"]().configureEffect(effect)

        self.assertTrue(configured)
        self.assertIsNotNone(effect.bonus)
        self.assertEqual({"normalResist": 10}, effect.bonus.values)

    def test_barrier_rejects_effect_without_caster(self):
        effect = FakeEffect(None)

        configured = self.registered["Barrier"]().configureEffect(effect)

        self.assertFalse(configured)
        self.assertIsNone(effect.bonus)

    def test_barrier_keeps_existing_duration_cost_and_unlocks(self):
        effects = json.loads((REPO_ROOT / "res/config/effects.json").read_text(encoding="utf-8"))
        interactions = json.loads((REPO_ROOT / "res/config/interactions.json").read_text(encoding="utf-8"))
        classes = json.loads((REPO_ROOT / "res/config/creature_classes.json").read_text(encoding="utf-8"))

        barrier_effect = effects["BarrierEffect"]["properties"]
        self.assertEqual(3, barrier_effect["duration"])
        self.assertIn("buff", barrier_effect["tags"])

        barrier = interactions["Barrier"]["properties"]
        self.assertEqual("BarrierEffect", barrier["effect"]["ref"])
        self.assertEqual(17, barrier["manaCost"])
        self.assertTrue(barrier["selfTarget"])

        self.assertEqual("Barrier", classes["WarriorClass"]["properties"]["levelling"]["2"]["ref"])
        self.assertEqual("Barrier", classes["InquisitorClass"]["properties"]["levelling"]["5"]["ref"])


if __name__ == "__main__":
    unittest.main()
