# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Fast authored-content checks without initializing SDL or the native engine."""

import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import quest_state

ROOT = Path(__file__).resolve().parents[1]
CLASS_PERKS = (
    ("Warrior", "Barrier", "warrior_barricades"),
    ("Assasin", "SneakAttack", "assasin_trails"),
    ("Sorcerer", "FrostBolt", "sorcerer_sigils"),
)
RACE_SERVICES = (
    ("humanRace", "HumanRation", 20, 0, 0),
    ("outlanderRace", "OutlanderRations", -5, 5, 5),
    ("highlanderRace", "HighlanderAid", -5, 10, 0),
    ("wandererRace", "WandererFocus", -5, 0, 10),
)


class ContentPlayer:
    def __init__(self, game, class_id="Warrior", race_id="humanRace"):
        self.game = game
        self.game_map = game.getMap()
        self.class_id = class_id
        self.race_id = race_id
        self.properties = {}
        self.gold, self.hp, self.mana = 30, 30, 30
        self.player = True
        self.race = types.SimpleNamespace(getTypeId=lambda: "outlanderRace")

    def getGame(self):
        return self.game

    def getMap(self):
        return self.game_map

    def isPlayer(self):
        return self.player

    def getPlayerClassId(self):
        return self.class_id

    def getRaceId(self):
        return self.race_id

    def getRace(self):
        return self.race

    def getNumericProperty(self, key):
        return self.properties.get(key, 0)

    def getBoolProperty(self, key):
        return bool(self.properties.get(key, False))

    def setBoolProperty(self, key, value):
        self.properties[key] = value

    def setStringProperty(self, key, value):
        self.properties[key] = value

    def getGold(self):
        return self.gold

    def addGold(self, amount):
        self.gold += amount

    def getHp(self):
        return self.hp

    def getHpMax(self):
        return 100

    def heal(self, amount):
        self.hp = min(100, self.hp + amount)

    def getMana(self):
        return self.mana

    def getManaMax(self):
        return 100

    def addMana(self, amount):
        self.mana = min(100, self.mana + amount)


class PlayerIdentityContentTest(unittest.TestCase):
    def setUp(self):
        self.types = {}
        self.receipts = []
        game_module = types.ModuleType("game")
        for name in ("CEvent", "CTrigger", "CQuest", "CDialog", "CInteraction"):
            setattr(game_module, name, type(name, (), {}))
        game_module.CPlayer = ContentPlayer
        for name in ("LegacyBoolFlag", "PlayerQuestRegistry", "QuestStateStore"):
            setattr(game_module, name, getattr(quest_state, name))
        game_module.register = lambda _context: lambda cls: self.types.setdefault(cls.__name__, cls)
        game_module.trigger = lambda _context, *_args: game_module.register(None)
        game_module.showReader = lambda _game, title, text: self.receipts.append((title, text))
        game_module.showRewardReceipt = lambda *_args: None
        game_module.rewardSnapshot = lambda _player: {}
        for name in ("Coords", "claim_once", "remove_runtime_actors", "ensure_quest", "randint"):
            setattr(game_module, name, lambda *_args, **_kwargs: None)
        game_module.event_loop = types.SimpleNamespace(
            instance=lambda: types.SimpleNamespace(invoke=lambda _task: None)
        )
        game_module.campaign = types.SimpleNamespace()
        with patch.dict(sys.modules, {"game": game_module}):
            for relative in ("res/plugins/interaction.py", "res/maps/nouraajd/script.py"):
                namespace = {}
                exec(compile((ROOT / relative).read_text(), relative, "exec"), namespace)
                namespace["load"](None, types.SimpleNamespace(getMap=lambda: None))

    def createPlayer(self, class_id="Warrior", race_id="humanRace"):
        game_map = types.SimpleNamespace()
        game = types.SimpleNamespace(getMap=lambda: game_map)
        player = ContentPlayer(game, class_id, race_id)
        game_map.getPlayer = lambda: player
        dialog = self.types["TownHallDialog"]()
        dialog.getGame = lambda: game
        return player, dialog

    def test_mcp_exposes_paid_commit_and_resource_reads_but_rejects_raw_callbacks(self):
        import mcp

        calls = []
        interaction = type(
            "CInteraction",
            (),
            {
                "getCommittedManaRefund": lambda _self, _caster: 3,
                "onAction": lambda _self, *_args: calls.append("committed"),
                "performAction": lambda _self, *_args: calls.append("raw"),
                "configureEffect": lambda _self, *_args: calls.append("configured"),
            },
        )()
        creature = type(
            "CCreature",
            (),
            {
                "getHp": lambda _self: 30,
                "getHpMax": lambda _self: 100,
                "getManaMax": lambda _self: 70,
                "getEffects": lambda _self: [],
            },
        )()
        server = mcp.EngineMcpServer(repo_root=ROOT, build_dir=ROOT / "build")
        registry = mcp.HandleRegistry(handles={"ability": interaction, "caster": creature})
        caster = {"__handle__": "caster"}
        result = server._engine_handle_call(
            {"handle": "ability", "method": "getCommittedManaRefund", "args": [caster]}, registry
        )
        self.assertFalse(result["isError"], result)
        self.assertEqual(3, result["structuredContent"]["result"])
        self.assertEqual([], calls)
        result = server._engine_handle_call(
            {"handle": "ability", "method": "onAction", "args": [caster, caster]}, registry
        )
        self.assertFalse(result["isError"], result)
        for callback in ("performAction", "configureEffect"):
            result = server._engine_handle_call(
                {"handle": "ability", "method": callback, "args": [caster, caster]}, registry
            )
            self.assertTrue(result["isError"], result)
        self.assertEqual(["committed"], calls)
        for method, expected in (("getHp", 30), ("getHpMax", 100), ("getManaMax", 70), ("getEffects", [])):
            result = server._engine_handle_call({"handle": "caster", "method": method}, registry)
            self.assertFalse(result["isError"], result)
            self.assertEqual(expected, result["structuredContent"]["result"])

    def test_class_perks_are_pure_bounded_and_require_the_active_matching_player(self):
        for class_id, ability_id, counter in CLASS_PERKS:
            with self.subTest(class_id=class_id):
                player, _dialog = self.createPlayer(class_id)
                ability = self.types[ability_id]()
                self.assertEqual(0, ability.getCommittedManaRefund(player))
                player.properties[counter] = 1
                before = (player.mana, dict(player.properties))
                for _ in range(3):
                    self.assertEqual(3, ability.getCommittedManaRefund(player))
                    self.assertEqual(before, (player.mana, player.properties))
                player.properties[counter] = 9
                self.assertEqual(3, ability.getCommittedManaRefund(player))
                player.class_id = "Inquisitor"
                self.assertEqual(0, ability.getCommittedManaRefund(player))
                player.class_id = class_id
                player.player = False
                self.assertEqual(0, ability.getCommittedManaRefund(player))
                player.player = True
                player.game_map.getPlayer = lambda: object()
                self.assertEqual(0, ability.getCommittedManaRefund(player))
                player.game_map.getPlayer = lambda: player
                player.game_map = object()
                self.assertEqual(0, ability.getCommittedManaRefund(player))
                player.game = None
                self.assertEqual(0, ability.getCommittedManaRefund(player))
                self.assertEqual(0, ability.getCommittedManaRefund(None))

    def test_every_existing_class_race_combination_receives_exactly_one_optional_aid(self):
        for class_id in ("Warrior", "Assasin", "Sorcerer", "Inquisitor", "Wayfarer"):
            for race_id, suffix, gold, hp, mana in RACE_SERVICES:
                with self.subTest(class_id=class_id, race_id=race_id):
                    player, dialog = self.createPlayer(class_id, race_id)
                    for other_race, other_suffix, *_amounts in RACE_SERVICES:
                        eligible = other_race == race_id
                        self.assertEqual(eligible, getattr(dialog, "canOffer" + other_suffix)())
                        if not eligible:
                            self.assertFalse(getattr(dialog, "claim" + other_suffix)())
                    self.assertTrue(getattr(dialog, "claim" + suffix)())
                    self.assertEqual((30 + gold, 30 + hp, 30 + mana), (player.gold, player.hp, player.mana))
                    self.assertTrue(player.properties["nouraajdRaceServiceClaimed"])
                    self.assertEqual(race_id, player.properties["nouraajdRaceServiceKind"])
                    for other_race, other_suffix, *_amounts in RACE_SERVICES:
                        player.race_id = other_race
                        self.assertFalse(getattr(dialog, "canOffer" + other_suffix)())
                        self.assertFalse(getattr(dialog, "claim" + other_suffix)())
                    self.assertEqual((30 + gold, 30 + hp, 30 + mana), (player.gold, player.hp, player.mana))

    def test_paid_services_reject_empty_wallet_and_unneeded_recovery_without_consuming_claim(self):
        for race_id, suffix, *_amounts in RACE_SERVICES[1:]:
            player, dialog = self.createPlayer(race_id=race_id)
            player.gold = 4
            self.assertFalse(getattr(dialog, "claim" + suffix)())
            self.assertEqual((4, 30, 30), (player.gold, player.hp, player.mana))
            self.assertFalse(player.getBoolProperty("nouraajdRaceServiceClaimed"))
            player.gold, player.hp, player.mana = 5, 100, 100
            self.assertFalse(getattr(dialog, "claim" + suffix)())
            self.assertEqual(5, player.gold)
            self.assertFalse(player.getBoolProperty("nouraajdRaceServiceClaimed"))
        player, dialog = self.createPlayer(race_id="outlanderRace")
        player.gold, player.hp, player.mana = 5, 99, 100
        self.assertTrue(dialog.claimOutlanderRations())
        self.assertEqual((0, 100, 100), (player.gold, player.hp, player.mana))
        self.assertIn("Health: +1", self.receipts[-1][1])
        self.assertNotIn("Mana: +", self.receipts[-1][1])

    def test_race_identity_takes_priority_and_unknown_identity_falls_back_to_archetype(self):
        player, dialog = self.createPlayer(race_id="wandererRace")
        self.assertTrue(dialog.canOfferWandererFocus())
        self.assertFalse(dialog.canOfferOutlanderRations())
        player.race_id = ""
        self.assertTrue(dialog.canOfferOutlanderRations())
        player.race = None
        self.assertFalse(dialog.canOfferOutlanderRations())

    def test_claim_is_persistent_before_resource_callbacks_can_reenter(self):
        for race_id, suffix, gold, hp, mana in RACE_SERVICES:
            with self.subTest(race_id=race_id):
                player, dialog = self.createPlayer(race_id=race_id)
                original_grant = player.addGold
                nested_results = []

                def reenterGrant(amount):
                    self.assertTrue(player.getBoolProperty("nouraajdRaceServiceClaimed"))
                    self.assertEqual(race_id, player.properties["nouraajdRaceServiceKind"])
                    nested_results.append(getattr(dialog, "claim" + suffix)())
                    original_grant(amount)

                player.addGold = reenterGrant
                self.assertTrue(getattr(dialog, "claim" + suffix)())
                self.assertEqual([False], nested_results)
                self.assertEqual((30 + gold, 30 + hp, 30 + mana), (player.gold, player.hp, player.mana))

    def test_claim_also_blocks_reentry_during_origin_persistence(self):
        for race_id, suffix, gold, hp, mana in RACE_SERVICES:
            with self.subTest(race_id=race_id):
                player, dialog = self.createPlayer(race_id=race_id)
                original_write = player.setStringProperty
                nested_results = []

                def reenterOrigin(key, value):
                    self.assertTrue(player.getBoolProperty("nouraajdRaceServiceClaimed"))
                    nested_results.append(getattr(dialog, "claim" + suffix)())
                    original_write(key, value)

                player.setStringProperty = reenterOrigin
                self.assertTrue(getattr(dialog, "claim" + suffix)())
                self.assertEqual([False], nested_results)
                self.assertEqual(race_id, player.properties["nouraajdRaceServiceKind"])
                self.assertEqual((30 + gold, 30 + hp, 30 + mana), (player.gold, player.hp, player.mana))

    def test_authored_options_resolve_to_methods_and_preserve_the_existing_roster_and_costs(self):
        config = json.loads((ROOT / "res/maps/nouraajd/dialog4.json").read_text())
        entry = config["townHallDialog"]["properties"]["states"][0]["properties"]
        self.assertEqual("ENTRY", entry["stateId"])
        options = [option["properties"] for option in entry["options"]]
        self.assertEqual(len(options), len({option["number"] for option in options}))
        for _race_id, suffix, *_amounts in RACE_SERVICES:
            option = next(option for option in options if option.get("action") == "claim" + suffix)
            self.assertEqual("canOffer" + suffix, option["condition"])
            self.assertEqual("EXIT", option["nextStateId"])
            self.assertTrue(callable(getattr(self.types["TownHallDialog"], option["action"])))
        interactions = json.loads((ROOT / "res/config/interactions.json").read_text())
        for _class_id, ability_id, _counter in CLASS_PERKS:
            self.assertEqual(
                {"Barrier": 17, "SneakAttack": 15, "FrostBolt": 20}[ability_id],
                interactions[ability_id]["properties"]["manaCost"],
            )
        races = json.loads((ROOT / "res/config/creature_races.json").read_text())
        self.assertEqual(
            {row[0] for row in RACE_SERVICES},
            {key for key, value in races.items() if value["properties"].get("playerSelectable")},
        )
