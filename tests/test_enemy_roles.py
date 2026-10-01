# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
import builtins
import importlib.util
import json
import re
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
        loader = (ROOT / "src/core/CLoader.cpp").read_text(encoding="utf-8")
        allowed = loader.split("allowedNames =", 1)[1].split("};", 1)[0]
        sandbox_builtins = {name: getattr(builtins, name) for name in re.findall(r'"([^"]+)"', allowed)}
        sandbox_builtins["__import__"] = builtins.__import__
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
                module.__dict__["__builtins__"] = sandbox_builtins
                spec.loader.exec_module(module)
                module.load(None, None)
        self.properties = {}
        self.object_properties = {}
        self.actor = Mock(
            spec_set=[
                "getBoolProperty",
                "setBoolProperty",
                "getObjectProperty",
                "setObjectProperty",
                "getDmg",
                "getWeapon",
                "isAlive",
                "getGame",
                "getEffectiveInteractions",
                "addEffect",
                "getNumericProperty",
                "setNumericProperty",
                "getStringProperty",
                "setStringProperty",
            ]
        )
        self.actor.getBoolProperty.side_effect = lambda name: self.properties.get(name, False)
        self.actor.setBoolProperty.side_effect = lambda name, value: self.properties.__setitem__(name, value)
        self.actor.getStringProperty.side_effect = lambda name: self.properties.get(name, "")
        self.actor.setStringProperty.side_effect = lambda name, value: self.properties.__setitem__(name, value)
        self.actor.setNumericProperty.side_effect = lambda name, value: self.properties.__setitem__(name, value)
        self.actor.getNumericProperty.side_effect = lambda name: self.properties.get(name, 0)
        self.actor.getObjectProperty.side_effect = lambda name: self.object_properties[name]
        self.actor.setObjectProperty.side_effect = lambda name, value: self.object_properties.__setitem__(name, value)
        self.actor.getDmg.return_value = 11
        self.actor.getWeapon.return_value = None
        self.actor.isAlive.return_value = True
        self.target = Mock()
        self.target.isAlive.return_value = True
        self.wards = {"normalResist": 10, "shadowResist": 0}
        self.target.getStats.return_value.getNumericProperty.side_effect = self.wards.__getitem__
        self.attack = self.registered["Attack"]()
        self.attack.getTypeId = lambda: "Attack"
        self.actor.getEffectiveInteractions.return_value = [self.attack]

    def makeSignature(self, class_name):
        action = self.registered[class_name]()
        effect, packet = Mock(), Mock()
        owned = {"roleEffect": effect, "roleDamage": packet}
        action.getObjectProperty = Mock(side_effect=owned.__getitem__)
        action.setObjectProperty = Mock(side_effect=lambda name, value: owned.__setitem__(name, value))
        action.getBoolProperty = Mock(return_value=class_name in ("EnemyBrace", "EnemyArcaneBolt"))
        action.getNumericProperty = Mock(return_value=10 if class_name == "EnemyRitualHex" else 0)
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
        for class_name, channel, roll in (
            (class_name, channel, roll)
            for class_name, channel in (("EnemyArcaneBolt", "frost"), ("EnemyRitualHex", "shadow"))
            for roll in (1, 11, 12)
        ):
            with self.subTest(class_name=class_name, roll=roll):
                self.properties.clear()
                self.actor.getDmg.return_value = roll
                self.actor.getDmg.reset_mock()
                self.target.hurt.reset_mock()
                action, _, packet = self.makeSignature(class_name)
                action.performAction(self.actor, self.target)
                channels = dict(call.args for call in packet.setNumericProperty.call_args_list)
                if class_name == "EnemyRitualHex" and roll < 10:
                    self.assertEqual({}, channels)
                    self.target.hurt.assert_called_once_with(roll)
                else:
                    self.assertEqual({"normal": roll - 1, channel: 1}, channels)
                    self.assertEqual(roll, sum(channels.values()))
                    self.target.hurt.assert_called_once_with(packet)
                self.actor.getDmg.assert_called_once_with()
                self.assertFalse(self.properties["enemyRoleArcaneAttack"])
                self.assertEqual("", self.properties["enemyRoleDamageChannel"])
                self.assertEqual(0, self.properties["enemyRoleDamageMinimum"])
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

    def testRitualNinePointHitKeepsOrdinaryPacketAndTenPointHitConvertsExactlyOnePoint(self):
        for roll in (9, 10):
            with self.subTest(roll=roll):
                self.properties.clear()
                self.actor.getDmg.return_value = roll
                self.actor.getDmg.reset_mock()
                self.target.hurt.reset_mock()
                weapon, proc = Mock(), Mock()
                weapon.getInteraction.return_value = proc
                self.actor.getWeapon.return_value = weapon
                action, _, packet = self.makeSignature("EnemyRitualHex")
                action.performAction(self.actor, self.target)
                self.actor.getDmg.assert_called_once_with()
                proc.onAction.assert_called_once_with(self.actor, self.target)
                if roll == 9:
                    packet.setNumericProperty.assert_not_called()
                    self.target.hurt.assert_called_once_with(9)
                else:
                    self.assertEqual(
                        {"normal": 9, "shadow": 1}, dict(call.args for call in packet.setNumericProperty.call_args_list)
                    )
                    self.target.hurt.assert_called_once_with(packet)
                self.assertEqual(0, self.properties["enemyRoleDamageMinimum"])

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

    def testDamagePacketHookRejectsChannelsOutsideFrostAndShadow(self):
        self.properties["enemyRoleArcaneAttack"] = True
        self.properties["enemyRoleDamageChannel"] = "fire"
        self.attack.performAction(self.actor, self.target)
        self.target.hurt.assert_called_once_with(11)
        self.actor.getObjectProperty.assert_not_called()
        self.assertFalse(self.properties["enemyRoleArcaneAttack"])
        self.assertEqual("", self.properties["enemyRoleDamageChannel"])

    def testRitualEqualWardsRetainOrdinaryDamageAndProcWithoutArmingPacket(self):
        for ward in (0, 15):
            with self.subTest(ward=ward):
                self.properties.clear()
                self.object_properties.clear()
                self.wards.update(normalResist=ward, shadowResist=ward)
                self.actor.getDmg.reset_mock()
                self.target.hurt.reset_mock()
                weapon, proc = Mock(), Mock()
                weapon.getInteraction.return_value = proc
                self.actor.getWeapon.return_value = weapon
                action, effect, packet = self.makeSignature("EnemyRitualHex")
                action.performAction(self.actor, self.target)
                self.actor.getDmg.assert_called_once_with()
                self.target.hurt.assert_called_once_with(11)
                proc.onAction.assert_called_once_with(self.actor, self.target)
                packet.setNumericProperty.assert_not_called()
                self.assertNotIn("enemyRoleDamagePacket", self.object_properties)
                self.assertNotIn("enemyRoleArcaneAttack", self.properties)
                self.assertTrue(self.properties["enemyRoleUsed"])
                self.assertIsNone(action.getObjectProperty("roleEffect"))
                effect.setVictim.assert_called_once_with(self.target)

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
        self.actor.getEffectiveInteractions.return_value = []
        action, effect, _ = self.makeSignature("EnemyArcaneBolt")
        action.performAction(self.actor, self.target)
        self.assertFalse(self.properties.get("enemyRoleUsed", False))
        action.getObjectProperty.assert_not_called()
        effect.setCaster.assert_not_called()
        attack = Mock()
        attack.getTypeId.return_value = "Attack"
        attack.performAction.side_effect = RuntimeError("rejected attack")
        self.actor.getEffectiveInteractions.return_value = [attack]
        with self.assertRaisesRegex(RuntimeError, "rejected attack"):
            action.performAction(self.actor, self.target)
        self.assertFalse(self.properties["enemyRoleArcaneAttack"])

    def testRoleEffectsHaveNoTickDamage(self):
        self.registered["EnemyRoleEffect"]().onEffect()
        self.target.hurt.assert_not_called()

    def testRolePluginCallsUseThePublishedNativeObjectApi(self):
        bindings = (ROOT / "src/core/CModule.cpp").read_text(encoding="utf-8")
        published = set(re.findall(r'\.def(?:_static)?\s*\(\s*"([^"]+)"', bindings))
        source = (ROOT / "res/plugins/enemy_roles.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        local = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertEqual(set(), called - published - local)
        self.assertTrue({"getEffectiveInteractions", "setCaster", "setVictim", "addEffect"} <= published)
        self.assertIn('"setCaster", &CEffect::setCaster', bindings)
        self.assertIn('"setVictim", &CEffect::setVictim', bindings)
        self.assertIn('"addEffect", &CCreature::addEffect', bindings)

    def testNativeWitnessScopeRetainsOriginalPairsAndOnlyMeasuredExceptions(self):
        source = (ROOT / "tests/unit/test_monster_balance.cpp").read_text(encoding="utf-8")
        scope = source.split("const bool originalAllLosingPair =", 1)[1].split("std::cout", 1)[0]
        required = re.search(r"const bool originallyRequiredDamage =([^;]+);", scope)
        self.assertIsNotNone(required)
        self.assertEqual(["Pritz", "OctoBogz"], re.findall(r'"([^"]+)"', required.group(1)))
        hp_guard = re.search(r"if \(([^)]+)\)\s*\{\s*expect_true\(median\(baselineHp\)", scope)
        self.assertIsNotNone(hp_guard)
        self.assertEqual("originallyRequiredDamage && !originalHarmlessMedianPair", hp_guard.group(1).strip())
        self.assertIn('std::string(playerType) == "Assasin" && std::string(monsterType) == "Pritz"', scope)
        self.assertIn('std::string(playerType) == "Sorcerer" && std::string(monsterType) == "CultLeader"', scope)
        self.assertRegex(scope, r"if \(!originalAllLosingPair\)\s*\{\s*expect_true\(baselineWins > 0")
        self.assertEqual(3, source.count("std::abs(median(role"))

    def testRuntimeChildCallsUseThePublishedNativeObjectApi(self):
        bindings = (ROOT / "src/core/CModule.cpp").read_text(encoding="utf-8")
        published = set(re.findall(r'\.def(?:_static)?\s*\(\s*"([^"]+)"', bindings))
        source = (ROOT / "tests/test_enemy_role_runtime.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        child = next(
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "runChild"
        )
        import textwrap

        calls = {
            node.func.attr
            for node in ast.walk(ast.parse(textwrap.dedent(child)))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertEqual(set(), calls - published - {"loads", "items", "values", "get", "uuid4", "unlink"})

    def testOrdinaryBarrierPriorityFixtureRegistersClonedBonusBeforeSecondControl(self):
        source = (ROOT / "tests/unit/test_controller.cpp").read_text(encoding="utf-8")
        registration = source.split("void register_effect_and_interaction", 1)[1].split("\n}", 1)[0]
        self.assertIn("register_type_metadata<CStats, CGameObject>()", registration)
        self.assertIn('registerType("CStats"', registration)
        priority = source.split("void testMonsterSignatureNeverReplacesAnOrdinaryDefensiveCast", 1)[1].split("\n}", 1)[
            0
        ]
        self.assertIn("clonedBonus != nullptr", priority)
        self.assertIn("if (clonedBonus)", priority)
        self.assertEqual(2, priority.count("controller.control(monster, opponent)"))
        self.assertIn('ordinaryBarrier->setTypeId("ordinaryBarrier")', priority)
        self.assertIn("(*effects.begin())->getTypeId() == ordinaryBarrier->getTypeId()", priority)
        self.assertIn("monster->getEffects().size() == 1", priority)
        self.assertIn("opponent->setHp(opponent->getHpMax())", priority)
        self.assertIn("monster->isAlive() && opponent->isAlive()", priority)

    def testRitualTraceObservesUnchangedNativeControllerAndReportsEligibleTurn(self):
        source = (ROOT / "tests/unit/test_monster_balance.cpp").read_text(encoding="utf-8")
        snapshot = source.split("RitualTurnState observeRitualTurn", 1)[1].split("\n}", 1)[0]
        self.assertNotRegex(snapshot, r"\b(?:set\w+|useAction|hurt|randint|seed)\s*\(")
        controller = source.split("class ObservedFightController", 1)[1].split("\n};", 1)[0]
        self.assertEqual(1, controller.count("delegate->control(me, opponent)"))
        self.assertIn("observeRitualTurn(me, opponent)", controller)
        self.assertIn('printRitualTrace(roles, "roles", playerType, monsterType, seed, false)', source)
        self.assertIn('printRitualTrace(baseline, "baseline", playerType, monsterType, seed, true)', source)

    def testRuntimeRitualReserveMatchesZeroCostEligibility(self):
        source = (ROOT / "tests/test_enemy_role_runtime.py").read_text(encoding="utf-8")
        self.assertIn("reserve_mana = 5 if signature_id == 'enemyRitualHex' else 0", source)
        self.assertIn("actor.setMana(reserve_mana)", source)
        self.assertIn("assert actor.getMana() == reserve_mana", source)
        self.assertIn("health_divisor = 4 if signature_id == 'enemyRitualHex' else 2", source)
        self.assertIn("actor.getHpMax() // health_divisor", source)
        controller = (ROOT / "src/core/CController.cpp").read_text(encoding="utf-8")
        self.assertIn('(trigger == "critical" && criticalHealth)', controller)
        self.assertIn("criticalHpMax > 0 && static_cast<std::int64_t>(me->getHp()) * 4 <= criticalHpMax", controller)
        native = (ROOT / "tests/unit/test_monster_balance.cpp").read_text(encoding="utf-8")
        packet = native.split("void testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks", 1)[1].split(
            "class HexTurnProbe", 1
        )[0]
        self.assertRegex(packet, r"if \(cultistHex\)\s*\{\s*actor->setHp\(std::max\(1, actor->getHpMax\(\) / 4\)\)")
        self.assertIn("const int ritualHealthDivisor = 4", native)
        self.assertIn("actor->getHpMax() / ritualHealthDivisor", native)

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
            if action_id == "enemyRitualHex":
                self.assertEqual("critical", action["enemyRoleTrigger"])
                self.assertEqual(5, action["minimumMana"])
                self.assertEqual(10, action["minimumPacketHit"])
            self.assertNotIn("effect", action)
            effect = effects[action["roleEffect"]["ref"]]["properties"]
            self.assertEqual(1, effect["duration"])
            self.assertEqual(bonuses[action_id], effect["bonus"]["properties"])
        self.assertEqual("CDamage", interactions["enemyArcaneBolt"]["properties"]["roleDamage"]["class"])
        self.assertEqual("CDamage", interactions["enemyRitualHex"]["properties"]["roleDamage"]["class"])
        self.assertEqual(
            set(expected), {key for key, value in classes.items() if value["properties"].get("combatRole")}
        )


if __name__ == "__main__":
    unittest.main()
