# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authored passive-effect contracts; empty tick hooks do not imply missing mechanics."""

import ast
import json
from pathlib import Path
import runpy
import sys
import types
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = (
    ("Slow", "SlowEffect", 25, 3, False),
    ("ChillTouch", "ChillTouchEffect", 10, 3, False),
    ("Doom", "DoomEffect", 12, 4, False),
    ("Haste", "HasteEffect", 30, 3, True),
    ("MirrorImage", "MirrorImageEffect", 20, 3, True),
    ("Stoneskin", "StoneskinEffect", 45, 4, True),
    ("Bless", "BlessEffect", 10, 4, True),
    ("ArmorOfFaith", "ArmorOfFaithEffect", 12, 4, True),
    ("DrawUponHolyMight", "DrawUponHolyMightEffect", 25, 3, True),
    ("Barrier", "BarrierEffect", 17, 3, True),
    ("Stunner", "Stun", 40, 2, False),
    ("HoldPerson", "HoldPersonEffect", 35, 2, False),
)
STAT_NAMES = (
    "strength",
    "agility",
    "stamina",
    "hit",
    "block",
    "crit",
    "attack",
    "armor",
    "normalResist",
    "shadowResist",
)


def expectedBonus(action, level, armor):
    return {
        "Slow": {"agility": -(2 + level // 2), "hit": -(3 + level // 3), "block": -4},
        "ChillTouch": {"hit": -(2 + level // 3)},
        "Doom": {"armor": -(2 + level // 2), "block": -2, "hit": -2},
        "Haste": {"agility": 3 + level // 2, "hit": 3, "crit": 2},
        "MirrorImage": {"block": 15 + 2 * level},
        "Stoneskin": {"armor": 6 + armor // 2, "normalResist": 5},
        "Bless": {"hit": 2 + level // 4, "attack": 1},
        "ArmorOfFaith": {"armor": 3 + level // 2, "normalResist": 3, "shadowResist": 3},
        "DrawUponHolyMight": {stat: 2 + level // 3 for stat in ("strength", "agility", "stamina")},
        "Barrier": {"normalResist": 10},
        "Stunner": {},
        "HoldPerson": {},
    }[action]


class Stats:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def setNumericProperty(self, name, value):
        self.values[name] = value

    def getNumericProperty(self, name):
        return self.values.get(name, 0)


def sourceInteractions(roll):
    classes = {}
    module = types.ModuleType("game")
    module.CInteraction = type("CInteraction", (), {})
    module.randint = lambda low, high: roll[0]

    def register(context):
        def capture(cls):
            classes[cls.__name__] = cls
            return cls

        return capture

    module.register = register
    with patch.dict(sys.modules, game=module):
        runpy.run_path(str(ROOT / "res/plugins/interaction.py"))["load"](None, None)
    return classes


class EffectContractTest(unittest.TestCase):
    def testRuntimeActorFixtureUsesTheBoundNamePropertySetter(self):
        actor_properties, stat_properties, added = {}, {}, []
        actor = types.SimpleNamespace(
            setObjectProperty=lambda name, value: actor_properties.update({name: value}),
            setNumericProperty=lambda name, value: actor_properties.update({name: value}),
            setStringProperty=lambda name, value: actor_properties.update({name: value}),
            heal=lambda amount: None,
            setMana=lambda value: None,
            getManaMax=lambda: 280,
            setEffects=lambda value: None,
        )
        stats = types.SimpleNamespace(
            setNumericProperty=lambda name, value: stat_properties.update({name: value}),
            setStringProperty=lambda name, value: stat_properties.update({name: value}),
        )
        fixture = types.SimpleNamespace(
            game=types.SimpleNamespace(createObject=lambda type_id: actor if type_id == "CCreature" else stats),
            gameMap=types.SimpleNamespace(addObject=added.append),
            addCleanup=lambda *args: None,
        )
        self.assertFalse(hasattr(actor, "setName"), "CGameObject does not bind setName to Python")
        self.assertIs(actor, EffectSemanticRuntimeTest.actor(fixture, "effectProbe"))
        self.assertEqual("effectProbe", actor_properties["name"])
        self.assertEqual("intelligence", stat_properties["mainStat"])
        self.assertEqual([actor], added)

    def testAllConfiguredEmptyTickHooksHaveAnExplicitPassiveContract(self):
        tree = ast.parse((ROOT / "res/plugins/effect.py").read_text(encoding="utf-8"))
        empty = {
            cls.name
            for cls in ast.walk(tree)
            if isinstance(cls, ast.ClassDef)
            for method in cls.body
            if isinstance(method, ast.FunctionDef)
            and method.name == "onEffect"
            and len(method.body) == 1
            and isinstance(method.body[0], ast.Pass)
        }
        self.assertEqual({effect for _, effect, _, _, _ in CONTRACTS}, empty)
        interactions = json.loads((ROOT / "res/config/interactions.json").read_text())
        effects = json.loads((ROOT / "res/config/effects.json").read_text())
        for action, effect, cost, duration, self_target in CONTRACTS:
            with self.subTest(action=action):
                props = interactions[action]["properties"]
                self.assertEqual(effect, props["effect"]["ref"])
                self.assertEqual(cost, props["manaCost"])
                self.assertEqual(self_target, props.get("selfTarget", False))
                self.assertEqual(duration, effects[effect]["properties"]["duration"])
                if effect in ("Stun", "HoldPersonEffect"):
                    self.assertIn("stun", effects[effect]["properties"]["tags"])

    def testConfiguredBonusFormulasAtTwoLevelsAndMissingCasterRejection(self):
        classes = sourceInteractions([1])
        for level, armor in ((1, 4), (6, 17)):
            caster = types.SimpleNamespace(
                getLevel=lambda: level,
                getStats=lambda: Stats({"armor": armor}),
                getGame=lambda: types.SimpleNamespace(createObject=lambda name: Stats()),
            )
            for action, _, _, _, _ in CONTRACTS[:10]:
                with self.subTest(action=action, level=level):
                    result = {}
                    effect = types.SimpleNamespace(
                        getCaster=lambda: caster, setBonus=lambda value: result.update(value.values)
                    )
                    self.assertTrue(classes[action]().configureEffect(effect))
                    self.assertEqual(expectedBonus(action, level, armor), result)
                    effect.getCaster = lambda: None
                    self.assertFalse(classes[action]().configureEffect(effect))

    def testChillTouchHasOneImmediateFrostPacketAndHoldPersonHasTwoSuccessfulRolls(self):
        roll = [1]
        classes = sourceInteractions(roll)
        packets = []
        caster = types.SimpleNamespace(getGame=lambda: types.SimpleNamespace(createObject=lambda name: Stats()))
        victim = types.SimpleNamespace(hurt=packets.append)
        for result in (1, 8):
            roll[0] = result
            classes["ChillTouch"]().performAction(caster, victim)
        self.assertEqual([{"frost": 3}, {"frost": 10}], [packet.values for packet in packets])
        results = []
        for result in (1, 2, 3):
            roll[0] = result
            results.append(classes["HoldPerson"]().configureEffect(None))
        self.assertEqual([False, True, True], results)


class EffectSemanticRuntimeTest(unittest.TestCase):
    def setUp(self):
        import test as harness

        if not any(
            list(path.glob("_game*.pyd")) + list(path.glob("_game*.so"))
            for path in (harness.build_dir, *harness.extension_dirs)
        ):
            self.skipTest("Current compiled _game required for effect semantic regression tests")
        self.engine = harness.load_game_module()
        self.game = self.engine.CGameLoader.loadGame()
        self.addCleanup(self.game.getContext().shutdown)
        self.engine.CGameLoader.startGameWithPlayer(self.game, "test", "Warrior")
        self.gameMap = self.game.getMap()

    def actor(self, name):
        actor = self.game.createObject("CCreature")
        stats = self.game.createObject("CStats")
        for stat, value in {
            "strength": 40,
            "agility": 30,
            "stamina": 40,
            "intelligence": 40,
            "armor": 16,
            "hit": 40,
            "block": 8,
            "crit": 5,
            "attack": 7,
            "mainStat": "intelligence",
        }.items():
            if isinstance(value, str):
                stats.setStringProperty(stat, value)
            else:
                stats.setNumericProperty(stat, value)
        actor.setObjectProperty("baseStats", stats)
        actor.setNumericProperty("level", 6)
        actor.setStringProperty("name", name)
        self.gameMap.addObject(actor)
        actor.heal(0)
        actor.setMana(actor.getManaMax())
        self.addCleanup(actor.setEffects, set())
        return actor

    def values(self, actor):
        return {name: actor.getStats().getNumericProperty(name) for name in STAT_NAMES}

    def attachTagEffect(self, caster, victim, effect_id):
        # Actor links are native-only fields; the cast pipeline supplies them.
        probe = self.engine.CInteraction()
        probe.effect = self.game.createObject(effect_id)
        probe.onAction(caster, victim)
        effect = next(effect for effect in victim.getEffects() if effect.getTypeId() == effect_id)
        self.assertIs(caster, effect.getCaster())
        self.assertIs(victim, effect.getVictim())

    def testPassiveEffectsHaveObservableBonusesOrTagsAndExpireWithoutRepeatedDamage(self):
        for action_id, effect_id, cost, duration, self_target in CONTRACTS[:-1]:
            with self.subTest(action=action_id):
                caster, victim = self.actor(action_id + "Caster"), self.actor(action_id + "Victim")
                if action_id == "ChillTouch":
                    for name in ("armor", "block"):
                        victim.getObjectProperty("baseStats").setNumericProperty(name, 0)
                target = caster if self_target else victim
                baseline = self.values(target)
                bonus = expectedBonus(action_id, caster.getLevel(), caster.getStats().getNumericProperty("armor"))
                hp_before = victim.getHp()
                object_count = len(self.gameMap.getObjects())
                caster.setMana(cost)
                self.game.createObject(action_id).onAction(caster, victim)
                self.assertEqual(0, caster.getMana())
                self.assertEqual(1, len(target.getEffects()))
                self.assertEqual(0, len((victim if self_target else caster).getEffects()))
                effect = next(iter(target.getEffects()))
                self.assertEqual(effect_id, effect.getTypeId())
                self.assertIs(effect.getCaster(), caster)
                self.assertIs(effect.getVictim(), target)
                if effect_id == "Stun":
                    self.assertTrue(effect.hasTag(self.engine.CTag.STUN))
                self.assertEqual(duration, effect.getTimeLeft())
                self.assertEqual(
                    {name: value + bonus.get(name, 0) for name, value in baseline.items()}, self.values(target)
                )
                if action_id == "ChillTouch":
                    self.assertIn(hp_before - victim.getHp(), range(3, 11))
                else:
                    self.assertEqual(hp_before, victim.getHp())
                self.assertEqual(object_count, len(self.gameMap.getObjects()), "Passive spells create no extra actors")
                hp_after = target.getHp()
                for time_left in range(duration - 1, -1, -1):
                    self.engine.CFightHandler.applyEffects(target)
                    self.assertEqual(time_left, effect.getTimeLeft())
                    self.assertEqual(hp_after, target.getHp())
                self.engine.CFightHandler.applyEffects(target)
                self.assertEqual([], list(target.getEffects()))
                self.assertEqual(baseline, self.values(target))

    def testUnaffordableCastsCannotSpendManaDamageOrAttachAnEffect(self):
        for action_id, _, cost, _, _ in CONTRACTS:
            with self.subTest(action=action_id):
                caster, victim = self.actor(action_id + "PoorCaster"), self.actor(action_id + "UntouchedVictim")
                caster.setMana(cost - 1)
                before = (caster.getMana(), caster.getHp(), victim.getHp(), self.values(caster), self.values(victim))
                self.game.createObject(action_id).onAction(caster, victim)
                self.assertEqual(
                    before, (caster.getMana(), caster.getHp(), victim.getHp(), self.values(caster), self.values(victim))
                )
                self.assertEqual([], list(caster.getEffects()))
                self.assertEqual([], list(victim.getEffects()))

    def testAllTwelveEffectsRetainTheirPartialDurationBonusTagsAndActorIdentityAcrossSave(self):
        player = self.gameMap.getPlayer()
        self.addCleanup(player.setEffects, set())
        baseline = self.values(player)
        for action_id, effect_id, cost, _, _ in CONTRACTS:
            player.setMana(cost)
            if action_id == "HoldPerson":
                self.attachTagEffect(player, player, effect_id)
            else:
                self.game.createObject(action_id).onAction(player, player)
        self.engine.CFightHandler.applyEffects(player)

        def snapshot(actor):
            return {
                effect.getTypeId(): {
                    "timeLeft": effect.getTimeLeft(),
                    "duration": effect.getNumericProperty("duration"),
                    "bonus": (
                        {name: effect.getBonus().getNumericProperty(name) for name in STAT_NAMES}
                        if effect.getBonus()
                        else {}
                    ),
                    "stun": effect.hasTag(self.engine.CTag.STUN),
                    "buff": effect.hasTag(self.engine.CTag.BUFF),
                }
                for effect in actor.getEffects()
            }

        before, effective_stats = snapshot(player), self.values(player)
        self.assertEqual(12, len(before))
        slot = "effect-contract-" + uuid.uuid4().hex
        self.assertTrue(self.engine.CMapLoader.saveWithResult(self.gameMap, slot))
        path = Path(self.game.getResourcesProvider().getPath("save/" + slot + ".json"))
        self.addCleanup(path.unlink, missing_ok=True)
        self.addCleanup(path.with_name(path.name + ".bak").unlink, missing_ok=True)
        loaded_game = self.engine.CGameLoader.loadGame()
        self.addCleanup(loaded_game.getContext().shutdown)
        self.engine.CGameLoader.loadSavedGame(loaded_game, slot)
        loaded_player = loaded_game.getMap().getPlayer()
        self.addCleanup(loaded_player.setEffects, set())
        self.assertEqual(before, snapshot(loaded_player))
        self.assertEqual(effective_stats, self.values(loaded_player))
        for effect in loaded_player.getEffects():
            self.assertIs(effect.getCaster(), loaded_player)
            self.assertIs(effect.getVictim(), loaded_player)
        for _ in range(4):
            self.engine.CFightHandler.applyEffects(loaded_player)
        self.assertEqual([], list(loaded_player.getEffects()))
        self.assertEqual(baseline, self.values(loaded_player))

    def testBothTagOnlyStunsSkipExactlyTwoCreatureActions(self):
        engine = self.engine
        for effect_id in ("Stun", "HoldPersonEffect"):
            with self.subTest(effect=effect_id):
                caster, victim = self.actor(effect_id + "Attacker"), self.actor(effect_id + "Defender")
                caster.getObjectProperty("baseStats").setNumericProperty("agility", 40)
                turns = {"attacker": 0, "defender": 0}

                class CountingAction(engine.CInteraction):
                    def __init__(self, key):
                        super().__init__()
                        self.key = key

                    def performAction(self, actor, opponent):
                        turns[self.key] += 1
                        opponent.setHp(0 if self.key == "defender" else opponent.getHp() - 1)

                actions = [CountingAction("attacker"), CountingAction("defender")]
                for actor, action in zip((caster, victim), actions):
                    archetype = self.game.createObject("CCreatureClass")
                    archetype.setActions({action})
                    actor.setObjectProperty("creatureClass", archetype)
                    actor.setFightController(self.game.createObject("Warrior").getFightController())
                self.attachTagEffect(caster, victim, effect_id)
                engine.CFightHandler.fight(caster, victim)
                self.assertEqual({"attacker": 3, "defender": 1}, turns)
                self.assertEqual([], list(victim.getEffects()))
