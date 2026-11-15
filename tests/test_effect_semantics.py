# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authored passive-effect contracts; empty tick hooks do not imply missing mechanics."""

import ast
from contextlib import contextmanager
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import types
import unittest
import uuid
from unittest.mock import Mock, patch

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
# Additional configured hostile IDs; existing32 immediate damage families stay in their original matrix.
REMAINING_HOSTILE_CASES = (
    ("AbyssalShadows", "AbyssalShadowsEffect", 4, "victim", None),
    ("Chloroform", "ChloroformEffect", 4, "victim", None),
    ("EndlessPain", "EndlessPainEffect", 2, "victim", None),
    ("Stunner", "Stun", 2, "victim", None),
    ("Cloudkill", "CloudkillEffect", 4, "victim", None),
    ("Doom", "DoomEffect", 4, "victim", None),
    ("HoldPerson", "HoldPersonEffect", 2, "victim", None),
    ("Slow", "SlowEffect", 3, "victim", None),
    ("Web", "WebEffect", 3, "victim", None),
    ("enemyBrace", "enemyBraceEffect", 1, "caster", {"normal": 12}),
    ("enemyArcaneBolt", "enemyArcaneBoltEffect", 1, "caster", {"normal": 11, "frost": 1}),
    ("enemyOpeningStrike", "enemyOpeningStrikeEffect", 1, "victim", {"normal": 12}),
    ("enemyRitualHex", "enemyRitualHexEffect", 1, "victim", {"normal": 11, "shadow": 1}),
    ("octobogzCharge", None, 0, "victim", {"normal": 12}),
    ("octobogzShadowPulse", "octobogzShadowPulseEffect", 1, "victim", {"normal": 11, "shadow": 1}),
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
        victim = types.SimpleNamespace(hurtFrom=lambda cause, packet: packets.append(packet))
        for result in (1, 8):
            roll[0] = result
            classes["ChillTouch"]().performAction(caster, victim)
        self.assertEqual([{"frost": 3}, {"frost": 10}], [packet.values for packet in packets])
        results = []
        for result in (1, 2, 3):
            roll[0] = result
            results.append(classes["HoldPerson"]().configureEffect(None))
        self.assertEqual([False, True, True], results)

    def testDeclaredProducerMatricesCoverEveryConfiguredHostileAction(self):
        source = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        runtime = next(
            node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "EffectSemanticRuntimeTest"
        )
        method = next(
            node
            for node in runtime.body
            if isinstance(node, ast.FunctionDef) and node.name == "nativeProducerSnapshots"
        )
        immediate_families = next(
            ast.literal_eval(node.value)
            for node in method.body
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "action_ids"
        )
        actions = json.loads((ROOT / "res/config/interactions.json").read_text(encoding="utf-8"))
        effects = json.loads((ROOT / "res/config/effects.json").read_text(encoding="utf-8"))
        hostile = {key for key, value in actions.items() if value["properties"].get("offensive", False)}
        covered = {key for key in hostile if actions[key]["class"] in immediate_families}
        remaining = {row[0] for row in REMAINING_HOSTILE_CASES}
        self.assertEqual(32, len(covered))
        self.assertEqual(15, len(remaining))
        self.assertFalse(covered & remaining)
        self.assertEqual(hostile, covered | remaining)
        for action_id, effect_id, duration, recipient_id, _packet in REMAINING_HOSTILE_CASES:
            with self.subTest(action=action_id):
                props = actions[action_id]["properties"]
                configured_effect = props.get("effect") or props.get("roleEffect")
                self.assertEqual("caster" if props.get("selfTarget", False) else "victim", recipient_id)
                if effect_id is None:
                    self.assertIsNone(configured_effect)
                    self.assertEqual(0, duration)
                else:
                    self.assertEqual(effect_id, configured_effect["ref"])
                    self.assertEqual(duration, effects[effect_id]["properties"]["duration"])

    def testControlledHoldPersonUsesActualAuthoredClosureCellAndRestoresIt(self):
        from tests.test_native_combat_producers import loadProducers

        classes, _random_calls = loadProducers()
        action = classes["HoldPerson"]()
        case = EffectSemanticRuntimeTest("testHoldPersonRefusalStillCommitsOnlyItsAttemptAndMana")
        cell = case.configuredRollCell(action)
        original = cell.cell_contents
        self.assertFalse(action.configureEffect(None))
        for value, expected in ((1, False), (2, True)):
            with case.forcedConfigureRoll(action, value) as controlled:
                self.assertEqual(expected, action.configureEffect(None))
            controlled.assert_called_once_with(1, 3)
            self.assertIs(original, cell.cell_contents)
        self.assertFalse(action.configureEffect(None))
        with self.assertRaisesRegex(RuntimeError, "fixture abort"):
            with case.forcedConfigureRoll(action, 2):
                raise RuntimeError("fixture abort")
        self.assertIs(original, cell.cell_contents)


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

    def testMigratedCombatProducersPreserveNativeResultsAndRandomStreamWhenObserved(self):
        script = (
            "import sys; from tests.test_effect_semantics import _writeNativeProducerSnapshot; "
            "_writeNativeProducerSnapshot(int(sys.argv[1]), sys.argv[2] == '1', sys.argv[3])"
        )
        with tempfile.TemporaryDirectory(prefix="native-combat-producers-") as directory:
            for seed in (188, 991):
                snapshots = {}
                for enabled in (False, True):
                    output = Path(directory) / (str(seed) + str(enabled) + ".json")
                    result = subprocess.run(
                        [sys.executable, "-c", script, str(seed), str(int(enabled)), str(output)],
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                        timeout=90,
                    )
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                    snapshots[enabled] = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(snapshots[False].keys(), snapshots[True].keys())
                for type_id in snapshots[False]:
                    with self.subTest(producer=type_id, seed=seed):
                        self.assertEqual(snapshots[False][type_id], snapshots[True][type_id])

    def nativeProducerSnapshots(self, enabled, seed):
        engine = self.engine
        action_ids = (
            "Attack",
            "ElemStaff",
            "DoubleAttack",
            "SneakAttack",
            "Strike",
            "ChaosBlast",
            "Devour",
            "FrostBolt",
            "MagicMissile",
            "ShadowBolt",
            "Mutilation",
            "LethalPoison",
            "Bloodlash",
            "Backstab",
            "DeathStrike",
            "BloodThirst",
            "ExposeCorruption",
            "SmugglersMark",
            "BurningHands",
            "AgannazarsScorcher",
            "Fireball",
            "FlameStrike",
            "LightningBolt",
            "ChromaticOrb",
            "ConeOfCold",
            "SkullTrap",
            "LarlochsMinorDrain",
            "VampiricTouch",
            "FingerOfDeath",
            "SpiritualHammer",
            "MelfsAcidArrow",
            "ChillTouch",
        )
        effect_ids = (
            "EndlessPainEffect",
            "AbyssalShadowsEffect",
            "MutilationEffect",
            "LethalPoisonEffect",
            "BloodlashEffect",
            "ExposeCorruptionEffect",
            "SmugglersMarkEffect",
            "MelfsAcidArrowEffect",
            "CloudkillEffect",
        )
        random_probe = self.actor("NativeRandomContinuationProbe")
        for name, value in (("dmgMin", 1), ("dmgMax", 1000000), ("damage", 0), ("hit", 1000), ("crit", 0)):
            random_probe.getObjectProperty("baseStats").setNumericProperty(name, value)

        def runProducer(type_id, enabled, seed, pulse):
            case_id = type_id + str(seed) + ("Observed" if enabled else "Ordinary")
            caster = self.actor(case_id + "Caster")
            victim = self.actor(case_id + "Victim")
            self.assertIs(caster, self.gameMap.getObjectByName(caster.getName()))
            self.assertIs(victim, self.gameMap.getObjectByName(victim.getName()))
            for actor in (caster, victim):
                stats = actor.getObjectProperty("baseStats")
                for name, value in (
                    ("stamina", 1000),
                    ("intelligence", 1000),
                    ("hit", 1000),
                    ("dmgMin", 12),
                    ("dmgMax", 12),
                    ("damage", 0),
                    ("crit", 0),
                    ("block", 0),
                    ("armor", 0),
                    ("normalResist", 0),
                    ("shadowResist", 0),
                ):
                    stats.setNumericProperty(name, value)
                actor.heal(0)
                actor.setMana(actor.getManaMax())
            caster.setHp(caster.getHpMax() // 2)
            caster_hp_before = caster.getHp()
            if type_id == "Strike":
                weapon = self.game.createObject("Sword")
                caster.addItem(weapon)
                caster.equipItem("0", weapon)
                self.assertIs(weapon, caster.getWeapon())
            observations = []
            observers = []

            class Observer(engine.CTrigger):
                def trigger(observer, actor, event):
                    self.assertIs(victim, actor)
                    self.assertIs(caster, event.getCause())
                    observations.append(
                        (event.getStringProperty("combatKind"), event.getObjectProperty("combatProducer"))
                    )

            observer_type = case_id + "Observer"
            self.game.getObjectHandler().registerType(observer_type, Observer)
            for kind in ("onCombatAttempt", "onCombatRoll", "onCombatPacket"):
                observer = self.game.createObject(observer_type)
                observer.setStringProperty("object", victim.getName())
                observer.setStringProperty("event", kind)
                self.gameMap.getEventHandler().registerTrigger(observer)
                observers.append(observer)
            producer = self.game.createObject(type_id)
            if not pulse:
                caster.addAction(producer)
                self.assertTrue(any(action is producer for action in caster.getEffectiveInteractions()))
            self.gameMap.setBoolProperty("nativeCombatFacts", enabled)
            if pulse:
                producer.setCaster(caster)
                producer.setVictim(victim)
                producer.apply(victim)
            else:
                caster.useAction(producer, victim)
            healing = {"Devour": 9, "BloodThirst": 2, "LarlochsMinorDrain": 10, "VampiricTouch": 9}
            if not pulse and type_id in healing:
                self.assertEqual(caster_hp_before + healing[type_id], caster.getHp())
            snapshot = (
                caster.getHp(),
                caster.getMana(),
                victim.getHp(),
                self.values(caster),
                self.values(victim),
                sorted((effect.getTypeId(), effect.getTimeLeft()) for effect in caster.getEffects()),
                sorted((effect.getTypeId(), effect.getTimeLeft()) for effect in victim.getEffects()),
                producer.getTimeLeft() if pulse else None,
                engine.randint(1, 1000000),
                tuple(random_probe.getDmg(False) for _ in range(8)),
            )
            if enabled:
                kinds = [kind for kind, _ in observations]
                self.assertIn("onCombatPacket", kinds)
                self.assertEqual(0 if pulse else 1, kinds.count("onCombatAttempt"))
                self.assertTrue(all(owner is producer for kind, owner in observations if kind == "onCombatAttempt"))
                if pulse:
                    self.assertTrue(all(owner is producer for kind, owner in observations if kind == "onCombatPacket"))
            else:
                self.assertEqual([], observations)
            return snapshot

        self.addCleanup(self.gameMap.setBoolProperty, "nativeCombatFacts", False)
        return {
            type_id: runProducer(type_id, enabled, seed, pulse)
            for pulse, type_ids in ((False, action_ids), (True, effect_ids))
            for type_id in type_ids
        }

    def combatProbe(self, label, *, enabled=True):
        caster, victim = self.actor(label + "Caster"), self.actor(label + "Victim")
        for actor in (caster, victim):
            stats = actor.getObjectProperty("baseStats")
            for key, value in {
                "stamina": 1000,
                "intelligence": 1000,
                "attack": 0,
                "hit": 1000,
                "crit": 0,
                "dmgMin": 12,
                "dmgMax": 12,
                "damage": 0,
                "armor": 0,
                "block": 0,
                "normalResist": 0,
                "shadowResist": 0,
                "fireResist": 0,
                "frostResist": 0,
                "thunderResist": 0,
            }.items():
                stats.setNumericProperty(key, value)
            actor.heal(0)
            actor.setMana(actor.getManaMax())
        caster.setHp(caster.getHpMax() // 2)
        events, observers = [], []

        class Observer(self.engine.CTrigger):
            def trigger(observer, actor, event):
                self.assertIs(victim, actor)
                self.assertIs(caster, event.getCause())
                events.append(
                    {
                        "kind": event.getStringProperty("combatKind"),
                        "producer": event.getObjectProperty("combatProducer"),
                        "connected": event.getBoolProperty("combatConnected"),
                        "damage": event.getNumericProperty("combatDamage"),
                        "mana": event.getNumericProperty("combatManaAtCommit"),
                        "packet": {
                            channel: event.getNumericProperty("combat" + channel.title())
                            for channel in ("normal", "fire", "frost", "thunder", "shadow")
                            if event.getNumericProperty("combat" + channel.title())
                        },
                    }
                )

        type_id = label + "Observer"
        self.game.getObjectHandler().registerType(type_id, Observer)
        for kind in ("onCombatAttempt", "onCombatRoll", "onCombatPacket"):
            observer = self.game.createObject(type_id)
            observer.setStringProperty("object", victim.getName())
            observer.setStringProperty("event", kind)
            self.gameMap.getEventHandler().registerTrigger(observer)
            observers.append(observer)
        self.assertEqual(3, len(observers))
        self.gameMap.setBoolProperty("nativeCombatFacts", enabled)
        self.addCleanup(self.gameMap.setBoolProperty, "nativeCombatFacts", False)
        return caster, victim, events, observers

    def combatProbeState(self, caster, victim):
        def actorState(actor):
            return (
                actor.getHp(),
                actor.getMana(),
                self.values(actor),
                sorted(
                    (effect.getTypeId(), effect.getTimeLeft(), effect.hasTag(self.engine.CTag.STUN))
                    for effect in actor.getEffects()
                ),
            )

        return (
            actorState(caster),
            actorState(victim),
            caster.getStringProperty("octobogzCombatPhase"),
            tuple(
                caster.getBoolProperty(key)
                for key in (
                    "enemyRoleUsed",
                    "enemyRoleEffectApplied",
                    "octobogzPulseUsed",
                    "octobogzPulseEffectApplied",
                )
            ),
        )

    def testRemainingHostileActionsKeepAttemptsEffectsAndBoundedExpiry(self):
        for case in REMAINING_HOSTILE_CASES:
            with self.subTest(action=case[0]):
                ordinary = self.remainingHostileSnapshot(case, False)
                observed = self.remainingHostileSnapshot(case, True)
                self.assertEqual(ordinary, observed)

    def configuredRollCell(self, action):
        authored = action.configureEffect.__func__
        return authored.__closure__[authored.__code__.co_freevars.index("randint")]

    @contextmanager
    def forcedConfigureRoll(self, action, value):
        cell = self.configuredRollCell(action)
        original = cell.cell_contents
        controlled = Mock(return_value=value)
        cell.cell_contents = controlled
        try:
            yield controlled
        finally:
            cell.cell_contents = original

    def remainingHostileSnapshot(self, case, enabled):
        action_id, effect_id, duration, recipient_id, immediate_packet = case
        caster, victim, events, observers = self.combatProbe(
            action_id + ("ObservedRemaining" if enabled else "OrdinaryRemaining"), enabled=enabled
        )
        action = self.game.createObject(action_id)
        caster.addAction(action)
        if immediate_packet is not None:
            caster.addAction(self.game.createObject("Attack"))
            caster.setHp(caster.getHpMax() // 5)
            victim.getObjectProperty("baseStats").setNumericProperty("shadowResist", 20)
        if action_id == "octobogzShadowPulse":
            caster.setStringProperty("octobogzCombatPhase", "charged")
        if action_id == "Chloroform":
            victim.setHp(victim.getHpMax() // 4)
        if action_id == "Web":
            victim.getObjectProperty("baseStats").setNumericProperty("agility", 1000)
        before = (caster.getMana(), caster.getHp(), victim.getHp())
        before_stats = {"caster": self.values(caster), "victim": self.values(victim)}
        if action_id == "HoldPerson":
            # This fixture forces only the Python configure gate, not native attack rolls or packet work.
            with self.forcedConfigureRoll(action, 2) as configure_roll:
                caster.useAction(action, victim)
            configure_roll.assert_called_once_with(1, 3)
        else:
            caster.useAction(action, victim)
        attempts = [event for event in events if event["kind"] == "onCombatAttempt"]
        packets = [event for event in events if event["kind"] == "onCombatPacket"]
        if enabled:
            self.assertEqual(1, len(attempts))
            self.assertIs(action, attempts[0]["producer"])
        else:
            self.assertEqual([], events)
        self.assertEqual(before[0] - action.getNumericProperty("manaCost"), caster.getMana())
        if enabled:
            self.assertEqual(caster.getMana(), attempts[0]["mana"])
        self.assertEqual(before[1], caster.getHp())
        self.assertEqual(
            [] if immediate_packet is None or not enabled else [immediate_packet],
            [event["packet"] for event in packets],
        )
        if immediate_packet is None:
            self.assertEqual(before[2], victim.getHp())
        else:
            self.assertLess(victim.getHp(), before[2])
        frames = [self.combatProbeState(caster, victim)]
        recipient = caster if recipient_id == "caster" else victim
        other = victim if recipient is caster else caster
        self.assertEqual([], list(other.getEffects()))
        effects = list(recipient.getEffects())
        if effect_id is None:
            self.assertEqual([], effects)
            self.assertEqual("charged", caster.getStringProperty("octobogzCombatPhase"))
            return frames
        self.assertEqual(1, len(effects))
        effect = effects[0]
        self.assertEqual(effect_id, effect.getTypeId())
        self.assertIs(caster, effect.getCaster())
        self.assertIs(recipient, effect.getVictim())
        self.assertEqual(duration, effect.getTimeLeft())
        if action_id.startswith("enemy"):
            self.assertTrue(caster.getBoolProperty("enemyRoleUsed"))
        if action_id == "octobogzShadowPulse":
            self.assertEqual("spent", caster.getStringProperty("octobogzCombatPhase"))
            self.assertTrue(caster.getBoolProperty("octobogzPulseUsed"))
            self.assertTrue(action.getBoolProperty("octobogzPulseCommitted"))
        for time_left in range(duration - 1, -1, -1):
            self.engine.CFightHandler.applyEffects(recipient)
            self.assertEqual(time_left, effect.getTimeLeft())
            frames.append(self.combatProbeState(caster, victim))
            if action_id == "Chloroform":
                self.assertTrue(effect.hasTag(self.engine.CTag.STUN))
            if action_id == "Web":
                self.assertFalse(effect.hasTag(self.engine.CTag.STUN))
        self.engine.CFightHandler.applyEffects(recipient)
        self.assertEqual([], list(recipient.getEffects()))
        frames.append(self.combatProbeState(caster, victim))
        self.assertEqual(before_stats[recipient_id], self.values(recipient))
        self.assertEqual(int(enabled), len([event for event in events if event["kind"] == "onCombatAttempt"]))
        return frames

    def testHoldPersonRefusalStillCommitsOnlyItsAttemptAndMana(self):
        caster, victim, events, observers = self.combatProbe("RejectedHoldPerson")
        action = self.game.createObject("HoldPerson")
        caster.addAction(action)
        before = (caster.getMana(), caster.getHp(), victim.getHp())
        with self.forcedConfigureRoll(action, 1) as configure_roll:
            caster.useAction(action, victim)
        configure_roll.assert_called_once_with(1, 3)
        self.assertEqual(before[0] - action.getNumericProperty("manaCost"), caster.getMana())
        self.assertEqual(before[1:], (caster.getHp(), victim.getHp()))
        self.assertEqual([], list(caster.getEffects()) + list(victim.getEffects()))
        self.assertEqual(["onCombatAttempt"], [event["kind"] for event in events])
        self.assertIs(action, events[0]["producer"])

    def testNativeZeroMissCriticalMitigationAndConditionalPacketsStayDistinct(self):
        cases = (
            ("Attack", "zero", [(True, 0)], [], 0, 0),
            ("Attack", "miss", [(False, 0)], [], 0, 0),
            ("Attack", "critical", [(True, 24)], [{"normal": 24}], 24, 0),
            ("Attack", "blocked", [(True, 12)], [{"normal": 12}], 0, 0),
            ("Attack", "resisted", [(True, 12)], [{"normal": 12}], 0, 0),
            ("Devour", "critical-disabled", [(True, 12)], [{"normal": 12}], 12, 9),
            ("BloodThirst", "miss-minimum", [(False, 0)], [{"normal": 1}], 1, 1),
            ("DeathStrike", "second-packet", [(True, 12), (True, 12)], [{"normal": 24}, {"normal": 18}], 42, 0),
            ("FingerOfDeath", "second-packet", [(True, 12), (True, 12)], [{"shadow": 24}, {"normal": 18}], 42, 0),
        )
        for action_id, branch, expected_rolls, expected_packets, loss, healing in cases:
            with self.subTest(action=action_id, branch=branch):
                caster, victim, events, observers = self.combatProbe(action_id + branch.replace("-", ""))
                caster_stats, victim_stats = caster.getObjectProperty("baseStats"), victim.getObjectProperty(
                    "baseStats"
                )
                if branch == "zero":
                    for key in ("dmgMin", "dmgMax"):
                        caster_stats.setNumericProperty(key, 0)
                if branch in ("miss", "miss-minimum"):
                    caster_stats.setNumericProperty("hit", 0)
                if branch in ("critical", "critical-disabled"):
                    caster_stats.setNumericProperty("crit", 1000)
                if branch == "blocked":
                    victim_stats.setNumericProperty("block", 1000)
                if branch == "resisted":
                    victim_stats.setNumericProperty("normalResist", 100)
                if branch == "second-packet":
                    victim.setHp(50)
                action = self.game.createObject(action_id)
                caster.addAction(action)
                before = (caster.getHp(), victim.getHp(), caster.getMana())
                caster.useAction(action, victim)
                self.assertEqual(
                    expected_rolls,
                    [(event["connected"], event["damage"]) for event in events if event["kind"] == "onCombatRoll"],
                )
                self.assertEqual(
                    expected_packets, [event["packet"] for event in events if event["kind"] == "onCombatPacket"]
                )
                self.assertEqual(before[0] + healing, caster.getHp())
                self.assertEqual(before[1] - loss, victim.getHp())
                self.assertEqual(before[2] - action.getNumericProperty("manaCost"), caster.getMana())
                attempts = [event for event in events if event["kind"] == "onCombatAttempt"]
                self.assertEqual(1, len(attempts))
                self.assertIs(action, attempts[0]["producer"])

    def testAbyssalInitialAndFinalNativePulsesKeepDifferentExactPackets(self):
        for duration, shadow in ((2, 5), (1, 12)):
            with self.subTest(duration=duration):
                caster, victim, events, observers = self.combatProbe("AbyssalPulse" + str(duration))
                effect = self.game.createObject("AbyssalShadowsEffect")
                effect.setNumericProperty("duration", duration)
                effect.setCaster(caster)
                effect.setVictim(victim)
                hp_before = victim.getHp()
                effect.apply(victim)
                self.assertEqual(duration - 1, effect.getTimeLeft())
                self.assertEqual(hp_before - shadow, victim.getHp())
                self.assertEqual(
                    [{"shadow": shadow}], [event["packet"] for event in events if event["kind"] == "onCombatPacket"]
                )
                self.assertTrue(
                    all(event["producer"] is effect for event in events if event["kind"] == "onCombatPacket")
                )
                self.assertEqual(
                    [(True, 12)],
                    [(event["connected"], event["damage"]) for event in events if event["kind"] == "onCombatRoll"],
                )
                self.assertFalse(any(event["kind"] == "onCombatAttempt" for event in events))

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


def _writeNativeProducerSnapshot(seed, enabled, output):
    import test as harness

    harness.load_game_module()
    import _game

    _game._seedRandomForTests(seed)
    case = EffectSemanticRuntimeTest("testMigratedCombatProducersPreserveNativeResultsAndRandomStreamWhenObserved")
    try:
        case.setUp()
        Path(output).write_text(json.dumps(case.nativeProducerSnapshots(enabled, seed)), encoding="utf-8")
    finally:
        case.doCleanups()
