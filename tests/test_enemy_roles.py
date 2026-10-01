# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class EnemyRolesTest(unittest.TestCase):
    def setUp(self):
        self.registered = {}
        game = types.ModuleType("game")
        game.CEffect = type("CEffect", (), {})
        game.CInteraction = type("CInteraction", (), {})
        game.register = lambda context: lambda cls: self.registered.setdefault(cls.__name__, cls)
        with patch.dict(sys.modules, {"game": game}):
            spec = importlib.util.spec_from_file_location("enemy_roles_under_test", ROOT / "res/plugins/enemy_roles.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.load(None, None)
        self.properties = {}
        self.actor = Mock()
        self.actor.getBoolProperty.side_effect = lambda name: self.properties.get(name, False)
        self.actor.setBoolProperty.side_effect = lambda name, value: self.properties.__setitem__(name, value)
        self.actor.getDmg.return_value = 11
        self.target = Mock()

    def testSignaturesRollAtMostOneAttackAndCannotRepeatAfterSave(self):
        for class_name, expected_rolls in (
            ("EnemyBrace", 0),
            ("EnemyArcaneBolt", 1),
            ("EnemyOpeningStrike", 1),
            ("EnemyRitualHex", 0),
        ):
            with self.subTest(class_name=class_name):
                self.properties.clear()
                self.actor.getDmg.reset_mock()
                self.target.hurt.reset_mock()
                action = self.registered[class_name]()
                action.performAction(self.actor, self.target)
                self.assertTrue(self.properties["enemyRoleUsed"])
                saved = json.loads(json.dumps(self.properties))
                self.properties.clear()
                self.properties.update(saved)
                action.performAction(self.actor, self.target)
                self.assertEqual(expected_rolls, self.actor.getDmg.call_count)
                self.assertEqual(expected_rolls, self.target.hurt.call_count)
                self.actor.getWeapon.assert_not_called()

    def testArcaneBoltSplitsOneRollWithoutIncreasingItsBudget(self):
        action = self.registered["EnemyArcaneBolt"]()
        for roll in (1, 11, 12):
            self.properties.clear()
            self.actor.getDmg.return_value = roll
            self.actor.getDmg.reset_mock()
            packet = Mock()
            self.actor.getGame.return_value.createObject.return_value = packet
            action.performAction(self.actor, self.target)
            channels = dict(call.args for call in packet.setNumericProperty.call_args_list)
            self.assertEqual({"normal": roll // 2, "frost": roll - roll // 2}, channels)
            self.assertEqual(roll, sum(channels.values()))
            self.actor.getDmg.assert_called_once_with()

    def testOpeningStrikeFloorsEightyPercentIncludingMisses(self):
        action = self.registered["EnemyOpeningStrike"]()
        for roll in (0, 1, 11, 12):
            self.properties.clear()
            self.actor.getDmg.return_value = roll
            self.target.hurt.reset_mock()
            action.performAction(self.actor, self.target)
            if roll * 80 // 100:
                self.target.hurt.assert_called_once_with(roll * 80 // 100)
            else:
                self.target.hurt.assert_not_called()

    def testMissesDoNotConsumeBlockRollsThroughZeroDamage(self):
        self.actor.getDmg.return_value = 0
        for class_name in ("EnemyArcaneBolt", "EnemyOpeningStrike"):
            with self.subTest(class_name=class_name):
                self.properties.clear()
                self.target.hurt.reset_mock()
                self.actor.getGame.reset_mock()
                self.registered[class_name]().performAction(self.actor, self.target)
                self.target.hurt.assert_not_called()
                self.actor.getGame.assert_not_called()

    def testEffectsCannotBeAppliedTwiceAndHaveNoTickDamage(self):
        effect = Mock()
        effect.getCaster.return_value = self.actor
        for class_name in ("EnemyBrace", "EnemyArcaneBolt", "EnemyOpeningStrike", "EnemyRitualHex"):
            self.properties.clear()
            action = self.registered[class_name]()
            self.assertTrue(action.configureEffect(effect))
            self.assertFalse(action.configureEffect(effect))
        self.registered["EnemyRoleEffect"]().onEffect()
        self.target.hurt.assert_not_called()

    def testRoleConfigKeepsPlayerRosterAndNumericClassStatsUnchanged(self):
        classes = json.loads((ROOT / "res/config/creature_classes.json").read_text())
        interactions = json.loads((ROOT / "res/config/interactions.json").read_text())
        effects = json.loads((ROOT / "res/config/effects.json").read_text())
        expected = {
            "bruteClass": "enemyBrace",
            "mageClass": "enemyArcaneBolt",
            "thiefClass": "enemyOpeningStrike",
            "cultistClass": "enemyRitualHex",
        }
        bonuses = {
            "enemyBrace": {"block": 5, "normalResist": 5, "hit": -5},
            "enemyArcaneBolt": {"normalResist": -5},
            "enemyOpeningStrike": {"block": -5},
            "enemyRitualHex": {"hit": -5, "shadowResist": -5},
        }
        for class_id, action_id in expected.items():
            properties = classes[class_id]["properties"]
            self.assertNotIn("baseStats", properties)
            self.assertNotIn("levelStats", properties)
            self.assertEqual([{"ref": action_id}], properties["actions"])
            action = interactions[action_id]["properties"]
            self.assertTrue(action["enemySignature"])
            self.assertEqual(properties["combatRole"], action["enemyRole"])
            self.assertEqual(0, action["manaCost"])
            effect = effects[action["effect"]["ref"]]["properties"]
            self.assertGreater(effect["duration"], 0)
            self.assertLessEqual(effect["duration"], 2)
            self.assertEqual(bonuses[action_id], effect["bonus"]["properties"])
        self.assertEqual(
            set(expected), {key for key, value in classes.items() if value["properties"].get("combatRole")}
        )


if __name__ == "__main__":
    unittest.main()
