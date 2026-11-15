# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
import json
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = ("normal", "thunder", "frost", "fire", "shadow")


class Packet:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def setNumericProperty(self, name, value):
        self.values[name] = value

    def getNumericProperty(self, name):
        return self.values.get(name, 0)


class Actor:
    def __init__(self, roll=12):
        self.roll = roll
        self.rolls = []
        self.packets = []
        self.healing = []
        self.legacy = []
        self.properties = {}
        self.weapon = None
        self.hp_ratio = 30
        self.stats = Packet({"strength": 10, "agility": 12, "intelligence": 8, "damage": 5})

    def getDmg(self, allowCrit=True):
        self.legacy.append("roll")
        return self.roll

    def getDmgFor(self, victim, allowCrit=True):
        self.rolls.append((victim, allowCrit))
        return self.roll

    def hurt(self, amount):
        self.legacy.append("packet")
        self.record(None, amount)

    def hurtFrom(self, cause, amount):
        self.record(cause, amount)

    def record(self, cause, amount):
        values = amount.values if isinstance(amount, Packet) else {"normal": amount}
        self.packets.append((cause, dict(values)))

    def getStats(self):
        return self.stats

    def getGame(self):
        return types.SimpleNamespace(createObject=lambda name: Packet())

    def getLevel(self):
        return 4

    def getMana(self):
        return 100

    def getHpRatio(self):
        return self.hp_ratio

    def isAlive(self):
        return True

    def getWeapon(self):
        return self.weapon

    def getBoolProperty(self, name):
        return self.properties.get(name, False)

    def getNumericProperty(self, name):
        return self.properties.get(name, 0)

    def getStringProperty(self, name):
        return self.properties.get(name, "")

    def getType(self):
        return "CCreature"

    def heal(self, amount):
        self.healing.append(amount)


def loadProducers():
    registered = {}
    random_calls = []

    class Interaction:
        def onAction(self, first, second):
            self.performAction(first, second)

    class Effect:
        def getCaster(self):
            return self.caster

        def getVictim(self):
            return self.victim

        def getTimeLeft(self):
            return self.time_left

        def getNumericProperty(self, name):
            return 0

        def hurtVictim(self, amount):
            self.victim.hurtFrom(self.caster, amount)

    def randint(low, high):
        random_calls.append((low, high))
        return low

    module = types.ModuleType("game")
    module.CInteraction = Interaction
    module.CEffect = Effect
    module.CTag = types.SimpleNamespace(STUN="stun")
    module.randint = randint
    module.register = lambda context: lambda cls: registered.setdefault(cls.__name__, cls)
    with patch.dict(sys.modules, game=module):
        for plugin in ("interaction", "effect"):
            runpy.run_path(str(ROOT / "res/plugins" / (plugin + ".py")))["load"](None, None)
    return registered, random_calls


class NativeCombatProducerTest(unittest.TestCase):
    def testAllImmediateDamageProducersRetainPacketsAndExplicitCause(self):
        expected = {
            "Attack": [{"normal": 12}],
            "ElemStaff": [{"fire": 1, "frost": 1, "thunder": 1}],
            "DoubleAttack": [{"normal": 12}, {"normal": 12}],
            "SneakAttack": [{"normal": 12}],
            "Strike": [{"normal": 17}],
            "ChaosBlast": [{"fire": 50, "thunder": 50}],
            "Devour": [{"normal": 12}],
            "FrostBolt": [{"normal": 12}, {"frost": 6}],
            "MagicMissile": [{"normal": 6}],
            "ShadowBolt": [{"shadow": 27}],
            "Mutilation": [{"normal": 18}],
            "LethalPoison": [{"normal": 12}],
            "Bloodlash": [{"normal": 18}],
            "Backstab": [{"normal": 21}],
            "DeathStrike": [{"normal": 24}],
            "BloodThirst": [{"normal": 2}],
            "ExposeCorruption": [{"normal": 12}, {"fire": 8}],
            "SmugglersMark": [{"normal": 6}],
            "BurningHands": [{"fire": 11}],
            "AgannazarsScorcher": [{"fire": 10}],
            "Fireball": [{"fire": 4}],
            "FlameStrike": [{"fire": 18}],
            "LightningBolt": [{"thunder": 4}],
            "ChromaticOrb": [{"fire": 10}],
            "ConeOfCold": [{"frost": 16}],
            "SkullTrap": [{"shadow": 4}],
            "LarlochsMinorDrain": [{"shadow": 8}],
            "VampiricTouch": [{"shadow": 14}],
            "FingerOfDeath": [{"shadow": 24}],
            "SpiritualHammer": [{"normal": 10}],
            "MelfsAcidArrow": [{"normal": 5}],
            "ChillTouch": [{"frost": 3}],
        }
        healing = {"Devour": [9], "BloodThirst": [2], "LarlochsMinorDrain": [8], "VampiricTouch": [7]}
        dice = {
            "MagicMissile": [(1, 4)] * 3,
            "Fireball": [(1, 6)] * 4,
            "LightningBolt": [(1, 6)] * 4,
            "SkullTrap": [(1, 6)] * 4,
            "ChromaticOrb": [(0, 4)],
            "MelfsAcidArrow": [(1, 4)],
            "ChillTouch": [(1, 8)],
            "SneakAttack": [(1, 100)],
        }
        rolls = {
            "Attack",
            "DoubleAttack",
            "SneakAttack",
            "Strike",
            "Devour",
            "FrostBolt",
            "ShadowBolt",
            "Mutilation",
            "LethalPoison",
            "Bloodlash",
            "Backstab",
            "DeathStrike",
            "BloodThirst",
            "ExposeCorruption",
            "FingerOfDeath",
        }
        for name, packets in expected.items():
            with self.subTest(action=name):
                classes, random_calls = loadProducers()
                caster, victim = Actor(), Actor()
                if name == "Strike":
                    caster.weapon = types.SimpleNamespace(getInteraction=lambda: None)
                classes[name]().performAction(caster, victim)
                self.assertEqual(packets, [packet for _, packet in victim.packets])
                self.assertTrue(all(cause is caster for cause, _ in victim.packets))
                self.assertEqual(healing.get(name, []), caster.healing)
                self.assertEqual(dice.get(name, []), random_calls)
                self.assertEqual(2 if name == "DoubleAttack" else int(name in rolls), len(caster.rolls))
                self.assertTrue(all(target is victim for target, _ in caster.rolls))
                self.assertTrue(all(allow is (name != "Devour") for _, allow in caster.rolls))
                self.assertEqual([], caster.legacy + victim.legacy)

    def testDamageEffectPulsesKeepTheirActualCasterAndExistingArithmetic(self):
        expected = {
            "EndlessPainEffect": {"normal": 1},
            "AbyssalShadowsEffect": {"shadow": 5},
            "MutilationEffect": {"normal": 3},
            "LethalPoisonEffect": {"normal": 8},
            "BloodlashEffect": {"normal": 9},
            "ExposeCorruptionEffect": {"fire": 6},
            "SmugglersMarkEffect": {"normal": 6},
            "MelfsAcidArrowEffect": {"normal": 4},
            "CloudkillEffect": {"shadow": 7},
        }
        rolled = {"EndlessPainEffect", "AbyssalShadowsEffect", "LethalPoisonEffect", "BloodlashEffect"}
        for name, packet in expected.items():
            with self.subTest(effect=name):
                classes, random_calls = loadProducers()
                caster, victim = Actor(), Actor()
                effect = classes[name]()
                effect.caster, effect.victim, effect.time_left = caster, victim, 2
                effect.onEffect()
                self.assertEqual([(caster, packet)], victim.packets)
                self.assertEqual(int(name in rolled), len(caster.rolls))
                self.assertTrue(all(target is victim for target, _ in caster.rolls))
                self.assertEqual([], caster.legacy + victim.legacy + random_calls)
                if name == "AbyssalShadowsEffect":
                    effect.time_left = 1
                    effect.onEffect()
                    self.assertEqual((caster, {"shadow": 12}), victim.packets[-1])

    def testConditionalSecondPacketsAndMissMinimumDoNotReroll(self):
        for name, expected in (
            ("DeathStrike", [{"normal": 24}, {"normal": 18}]),
            ("FingerOfDeath", [{"shadow": 24}, {"normal": 18}]),
        ):
            with self.subTest(action=name):
                classes, _ = loadProducers()
                caster, victim = Actor(), Actor()
                victim.hp_ratio = 10
                classes[name]().performAction(caster, victim)
                self.assertEqual(expected, [packet for _, packet in victim.packets])
                self.assertEqual([(victim, True)] * 2, caster.rolls)
                self.assertTrue(all(cause is caster for cause, _ in victim.packets))
        classes, _ = loadProducers()
        caster, victim = Actor(roll=0), Actor()
        classes["BloodThirst"]().performAction(caster, victim)
        self.assertEqual([(victim, True)], caster.rolls)
        self.assertEqual([(caster, {"normal": 1})], victim.packets)
        self.assertEqual([1], caster.healing)

    def testOffensiveFlagsCoverHostileActionsWithoutMarkingSelfBuffs(self):
        actions = json.loads((ROOT / "res/config/interactions.json").read_text())
        hostile_self_target = {"enemyBrace", "enemyArcaneBolt"}
        for name, action in actions.items():
            props = action["properties"]
            expected = not props.get("selfTarget", False) or name in hostile_self_target
            with self.subTest(action=name):
                self.assertEqual(expected, props.get("offensive", False))

    def testShippedProducerPluginsHaveNoUnattributedDamageOrRollCalls(self):
        for plugin in ("interaction", "effect"):
            tree = ast.parse((ROOT / "res/plugins" / (plugin + ".py")).read_text())
            calls = [
                node.func.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            ]
            with self.subTest(plugin=plugin):
                self.assertNotIn("hurt", calls)
                self.assertNotIn("getDmg", calls)


if __name__ == "__main__":
    unittest.main()
