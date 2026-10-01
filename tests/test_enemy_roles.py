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
SIGNATURES = ("EnemyBrace", "EnemyArcaneBolt", "EnemyOpeningStrike", "EnemyRitualHex")


class EnemyRolesTest(unittest.TestCase):
    def setUp(self):
        self.registered = {}
        game = types.ModuleType("game")
        game.CEffect = type("CEffect", (), {})
        game.CInteraction = type("CInteraction", (), {})
        game.randint = Mock()
        game.register = lambda context: lambda cls: self.registered.setdefault(cls.__name__, cls)
        with patch.dict(sys.modules, {"game": game}):
            for filename in ("interaction", "enemy_roles"):
                spec = importlib.util.spec_from_file_location(
                    filename + "_under_test", ROOT / f"res/plugins/{filename}.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.load(None, None)
        self.properties = {}
        self.object_properties = {}
        self.actor = Mock()
        self.actor.getBoolProperty.side_effect = lambda name: self.properties.get(name, False)
        self.actor.setBoolProperty.side_effect = lambda name, value: self.properties.__setitem__(name, value)
        self.actor.getObjectProperty.side_effect = lambda name: self.object_properties[name]
        self.actor.setObjectProperty.side_effect = lambda name, value: self.object_properties.__setitem__(name, value)
        self.actor.getDmg.return_value = 11
        self.actor.getWeapon.return_value = None
        self.actor.isAlive.return_value = True
        self.target = Mock()
        self.target.isAlive.return_value = True
        self.attack = self.registered["Attack"]()
        self.attack.getTypeId = lambda: "Attack"
        self.actor.getInteractions.return_value = [self.attack]

    def makeSignature(self, class_name):
        action = self.registered[class_name]()
        effect, packet = Mock(), Mock()
        owned = {"roleEffect": effect, "roleDamage": packet}
        action.getObjectProperty = Mock(side_effect=owned.__getitem__)
        action.setObjectProperty = Mock(side_effect=lambda name, value: owned.__setitem__(name, value))
        action.getBoolProperty = Mock(return_value=class_name in ("EnemyBrace", "EnemyArcaneBolt"))
        return action, effect, packet

    def testSignaturesDecorateExactlyOneConfiguredAttackAndCannotRepeatAfterSave(self):
        for class_name in SIGNATURES:
            with self.subTest(class_name=class_name):
                self.properties.clear()
                self.actor.getDmg.reset_mock()
                self.target.hurt.reset_mock()
                action, effect, _ = self.makeSignature(class_name)
                action.performAction(self.actor, self.target)
                saved = json.loads(json.dumps(self.properties))
                self.properties.clear()
                self.properties.update(saved)
                action.performAction(self.actor, self.target)
                self.assertTrue(self.properties["enemyRoleUsed"])
                self.assertTrue(self.properties["enemyRoleEffectApplied"])
                self.actor.getDmg.assert_called_once_with()
                self.target.hurt.assert_called_once()
                action.setObjectProperty.assert_called_once_with("roleEffect", None)
                self.assertIsNone(action.getObjectProperty("roleEffect"))
                effect.setCaster.assert_called_once_with(self.actor)
                recipient = self.actor if class_name in ("EnemyBrace", "EnemyArcaneBolt") else self.target
                effect.setVictim.assert_called_once_with(recipient)
                recipient.addEffect.assert_called_with(effect)
                self.actor.getGame.assert_not_called()

    def testArcaneHookConvertsOnePointFromTheExistingRollWithoutFactoryCalls(self):
        for roll in (1, 11, 12):
            with self.subTest(roll=roll):
                self.properties.clear()
                self.actor.getDmg.return_value = roll
                self.actor.getDmg.reset_mock()
                self.target.hurt.reset_mock()
                action, _, packet = self.makeSignature("EnemyArcaneBolt")
                action.performAction(self.actor, self.target)
                channels = dict(call.args for call in packet.setNumericProperty.call_args_list)
                self.assertEqual({"normal": roll - 1, "frost": 1}, channels)
                self.assertEqual(roll, sum(channels.values()))
                self.target.hurt.assert_called_once_with(packet)
                self.actor.getDmg.assert_called_once_with()
                self.assertFalse(self.properties["enemyRoleArcaneAttack"])
                self.actor.getGame.assert_not_called()

    def testDefaultAttackRetainsItsDamageAndConfiguredWeaponProcSequence(self):
        trace = []
        weapon, proc = Mock(), Mock()
        weapon.getInteraction.return_value = proc
        self.actor.getWeapon.side_effect = lambda: trace.append("weapon") or weapon
        self.actor.getDmg.side_effect = lambda: trace.append("roll") or 11
        self.target.hurt.side_effect = lambda damage: trace.append(("hurt", damage))
        proc.onAction.side_effect = lambda first, second: trace.append("proc")
        self.attack.performAction(self.actor, self.target)
        self.assertEqual(["roll", ("hurt", 11), "weapon", "proc"], trace)
        self.actor.getObjectProperty.assert_not_called()
        self.actor.setBoolProperty.assert_not_called()
        self.actor.getGame.assert_not_called()

    def testArcaneHookRetainsWeaponProcAndDoesNotLeakToAnotherAttack(self):
        weapon, proc = Mock(), Mock()
        weapon.getInteraction.return_value = proc
        self.actor.getWeapon.return_value = weapon
        action, _, packet = self.makeSignature("EnemyArcaneBolt")
        action.performAction(self.actor, self.target)
        proc.onAction.assert_called_once_with(self.actor, self.target)
        self.assertFalse(self.properties["enemyRoleArcaneAttack"])
        self.target.hurt.reset_mock()
        self.attack.performAction(self.actor, self.target)
        self.target.hurt.assert_called_once_with(11)
        self.assertEqual(2, proc.onAction.call_count)
        self.assertIs(packet, self.object_properties["enemyRoleDamagePacket"])
        other = Mock()
        other.getBoolProperty.return_value = False
        other.getDmg.return_value = 7
        other.getWeapon.return_value = None
        self.attack.performAction(other, self.target)
        self.target.hurt.assert_called_with(7)
        other.getObjectProperty.assert_not_called()

    def testMissesDoNotConsumeBlockDiceOrWeaponProcAndAlwaysClearHook(self):
        self.actor.getDmg.return_value = 0
        for class_name in SIGNATURES:
            with self.subTest(class_name=class_name):
                self.properties.clear()
                self.target.hurt.reset_mock()
                self.actor.getWeapon.reset_mock()
                action, _, packet = self.makeSignature(class_name)
                action.performAction(self.actor, self.target)
                self.target.hurt.assert_not_called()
                self.actor.getWeapon.assert_not_called()
                packet.setNumericProperty.assert_not_called()
                self.assertFalse(self.properties.get("enemyRoleArcaneAttack", False))
                self.actor.getGame.assert_not_called()

    def testMissingAttackAndRejectedExecutionCannotLeaveAnArmedHook(self):
        self.actor.getInteractions.return_value = []
        action, effect, _ = self.makeSignature("EnemyArcaneBolt")
        action.performAction(self.actor, self.target)
        self.assertFalse(self.properties.get("enemyRoleUsed", False))
        action.getObjectProperty.assert_not_called()
        effect.setCaster.assert_not_called()
        attack = Mock()
        attack.getTypeId.return_value = "Attack"
        attack.performAction.side_effect = RuntimeError("rejected attack")
        self.actor.getInteractions.return_value = [attack]
        with self.assertRaisesRegex(RuntimeError, "rejected attack"):
            action.performAction(self.actor, self.target)
        self.assertFalse(self.properties["enemyRoleArcaneAttack"])

    def testRoleEffectsHaveNoTickDamage(self):
        self.registered["EnemyRoleEffect"]().onEffect()
        self.target.hurt.assert_not_called()

    def testRoleConfigKeepsRosterNumericStatsAndBoundedOwnedEffects(self):
        classes = json.loads((ROOT / "res/config/creature_classes.json").read_text(encoding="utf-8"))
        interactions = json.loads((ROOT / "res/config/interactions.json").read_text(encoding="utf-8"))
        effects = json.loads((ROOT / "res/config/effects.json").read_text(encoding="utf-8"))
        expected = {
            "bruteClass": "enemyBrace",
            "mageClass": "enemyArcaneBolt",
            "thiefClass": "enemyOpeningStrike",
            "cultistClass": "enemyRitualHex",
        }
        bonuses = {
            "enemyBrace": {"normalResist": 1, "frostResist": -1},
            "enemyArcaneBolt": {"normalResist": -1},
            "enemyOpeningStrike": {"block": -1},
            "enemyRitualHex": {"shadowResist": -1},
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
            self.assertNotIn("effect", action)
            effect = effects[action["roleEffect"]["ref"]]["properties"]
            self.assertEqual(1, effect["duration"])
            self.assertEqual(bonuses[action_id], effect["bonus"]["properties"])
        self.assertEqual("CDamage", interactions["enemyArcaneBolt"]["properties"]["roleDamage"]["class"])
        self.assertEqual(
            set(expected), {key for key, value in classes.items() if value["properties"].get("combatRole")}
        )


if __name__ == "__main__":
    unittest.main()
