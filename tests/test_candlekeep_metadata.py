# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Metadata coercion models and deferred real-extension checks; no original-parity credit."""

import ast
from contextlib import ExitStack
import json
import textwrap
from unittest import TestCase
from unittest.mock import patch

from tests.test_candlekeep_content import CandlekeepModel, ModelObject, readDocument
from tests import test_python_callback_lifecycle as callback_lifecycle

PREFIX = "candlekeep-json:"
ENTRY_FIELDS = {
    "winthrop": ("shopEntries", "drinkEntries"),
    "templePriest": ("shopEntries", "serviceEntries"),
}
TRAINING_FIELDS = ("candlekeepTrainingInventoryNames", "candlekeepTrainingEquipment")


def decodeData(value):
    return json.loads(value.removeprefix(PREFIX))


def nativeLoadedValue(value):
    """Model only the unknown string branch of CSerialization::coerceStringProperty."""
    try:
        parsed = json.loads(value)
    except ValueError:
        return value
    return parsed if not isinstance(parsed, str) else value


def applyStringBoundary(obj, fields):
    for key in fields:
        obj.properties[key] = nativeLoadedValue(obj.properties[key])
    original = obj.getStringProperty

    def strictString(key):
        if key in fields and not isinstance(obj.properties[key], str):
            raise RuntimeError("bad_any_cast: " + key)
        return original(key)

    obj.getStringProperty = strictString


class CandlekeepMetadataSourceTest(TestCase):
    def rejectUnavailableNativeSetters(self):
        guard = ExitStack()
        for name in ("setPosX", "setPosY", "setPosZ", "setNpc"):
            guard.enter_context(
                patch.object(ModelObject, name, side_effect=AssertionError("Unbound native method: " + name))
            )
        return guard

    def testTrainingSpawnUsesBoundPropertySettersAndExactConfiguredActors(self):
        model = CandlekeepModel()
        with self.rejectUnavailableNativeSetters():
            self.assertTrue(model.dialog("gatewarden").acceptTraining())
            self.assertTrue(model.dialog("obe").beginTraining())
        for index in range(1, 7):
            actor = model.game_map.getObjectByName("trainingFoe" + str(index))
            self.assertIsInstance(actor, model.native_types["CCreature"])
            self.assertEqual("candlekeepTrainingFoe", actor.getTypeId())
            point = actor.getCoords()
            self.assertEqual((26 + index * 2, 48, 1), (point.x, point.y, point.z))
        for index, name in enumerate(("arkanis", "canderous", "deder", "mordaine", "osprey")):
            actor = model.game_map.getObjectByName(name)
            identity = "candlekeepTraining" + name.title()
            self.assertIsInstance(actor, model.native_types["CCreature"])
            self.assertEqual(identity, actor.getTypeId())
            point = actor.getCoords()
            self.assertEqual((30 + index * 2, 44, 1), (point.x, point.y, point.z))
            configured = model.resources[identity]["properties"].get("items", [])
            self.assertEqual([row["ref"] for row in configured], [item.getTypeId() for item in actor.getItems()])

    def testHostilityAndDepartureUseBoundNpcPropertyWithoutDroppingActors(self):
        model = CandlekeepModel()
        actor = model.game_map.getObjectByName("firebead")
        with self.rejectUnavailableNativeSetters():
            self.assertTrue(model.dialog("firebead").attack())
            self.assertFalse(actor.getBoolProperty("npc"))
            self.assertEqual("candlekeepHostile", actor.getStringProperty("affiliation"))
            self.assertIsNotNone(model.game_map.getObjectByName("candlekeepWatch1"))
            model.dialog("gorion").leaveCandlekeep()
        self.assertIs(actor, model.game_map.getObjectByName("firebead"))
        self.assertTrue(actor.getBoolProperty("npc"))
        self.assertTrue(model.game_map.getObjectByName("candlekeepWatch1").getBoolProperty("npc"))
        self.assertTrue(model.game_map.getBoolProperty("candlekeepDeparted"))

    def testConfiguredEntriesSurviveUnknownPropertyCoercionAsExactText(self):
        model = CandlekeepModel()
        dialogs = readDocument("dialog.json")
        seen = 0
        for actor, fields in ENTRY_FIELDS.items():
            for key in fields:
                with self.subTest(actor=actor, field=key):
                    dialog = model.dialog(actor)
                    expected = decodeData(dialogs[actor + "Dialog"]["properties"][key])
                    applyStringBoundary(dialog, fields)
                    self.assertEqual(expected, dialog._entries(key))
                    self.assertTrue(dialog.getStringProperty(key).startswith(PREFIX))
                    seen += 1
        self.assertEqual(4, seen)

    def testConfiguredBoltsPurchaseUsesExactBundlePriceAndSharedCounter(self):
        model = CandlekeepModel()
        dialog = model.dialog("winthrop")
        applyStringBoundary(dialog, ENTRY_FIELDS["winthrop"])
        before = model.player.getGold()
        for _ in range(2):
            self.assertTrue(dialog.buyBolts())
        self.assertEqual(before - 2, model.player.getGold())
        bolts = [item for item in model.player.getItems() if item.getTypeId() == "candlekeepBolts"]
        self.assertEqual(2, len(bolts))
        self.assertIsNot(bolts[0], bolts[1])
        self.assertEqual([20, 20], [item.getNumericProperty("plugin_candlekeepQuantity") for item in bolts])
        self.assertEqual(2, model.game_map.getNumericProperty("candlekeepStockBought_winthrop_BOLT01"))

    def testTrainingSnapshotsRemainTextAndRestoreExactOwnedObjectsAfterModelReload(self):
        model = CandlekeepModel()
        original = model.createObject("candlekeepDagger")
        original.setStringProperty("name", "trainingOriginal")
        model.player.addItem(original)
        model.player.equipItem("0", original)
        self.assertTrue(model.dialog("gatewarden").acceptTraining())
        self.assertTrue(model.dialog("obe").beginTraining())
        expected = {
            "candlekeepTrainingInventoryNames": ["trainingOriginal"],
            "candlekeepTrainingEquipment": {"0": "trainingOriginal"},
        }
        saved = json.loads(json.dumps({key: model.player.properties[key] for key in TRAINING_FIELDS}))
        for key, encoded in saved.items():
            with self.subTest(field=key):
                reloaded = nativeLoadedValue(encoded)
                self.assertIsInstance(reloaded, str)
                self.assertTrue(reloaded.startswith(PREFIX))
                self.assertEqual(expected[key], decodeData(reloaded))
                model.player.properties[key] = reloaded
        applyStringBoundary(model.player, TRAINING_FIELDS)
        model.dialog("obe").forceExitTraining()
        self.assertEqual([original], model.player.getItems())
        self.assertEqual({"0": original}, model.player.getEquipped())
        self.assertEqual("abandoned", model.game_map.getStringProperty("candlekeep_trainingStage"))

    def testTrainingCleanupAcceptsLegacyPlainTextSnapshots(self):
        model = CandlekeepModel()
        original = model.createObject("candlekeepDagger")
        original.setStringProperty("name", "legacyTrainingOriginal")
        model.player.addItem(original)
        self.assertTrue(model.dialog("gatewarden").acceptTraining())
        self.assertTrue(model.dialog("obe").beginTraining())
        for key in TRAINING_FIELDS:
            model.player.setStringProperty(key, model.player.getStringProperty(key).removeprefix(PREFIX))
        model.dialog("obe").forceExitTraining()
        self.assertEqual([original], model.player.getItems())
        self.assertEqual("abandoned", model.game_map.getStringProperty("candlekeep_trainingStage"))

    def testEntriesKeepPlainJsonCompatibilityAndRejectMalformedTables(self):
        model = CandlekeepModel()
        dialog = model.dialog("winthrop")
        rows = [{"id": "plain", "price": 1}]
        dialog.setStringProperty("shopEntries", json.dumps(rows))
        self.assertEqual(rows, dialog._entries("shopEntries"))
        for value in (PREFIX + "not-json", PREFIX + "{}", "not-json"):
            with self.subTest(value=value):
                dialog.setStringProperty("shopEntries", value)
                self.assertEqual([], dialog._entries("shopEntries"))

    def testDeferredNativeProbeCoversActualCleanupWithoutSettingProgressFlags(self):
        case = CandlekeepMetadataRuntimeTest()
        programs = []
        marker = "native Candlekeep purchase and training metadata saved as exact text"
        with patch.object(case, "runChild", side_effect=lambda program: programs.append(program) or marker):
            case.testNativeConfiguredPurchaseAndTrainingSnapshotTextSurviveSaveReload()
        self.assertEqual(1, len(programs))
        program = programs[0]
        ast.parse(textwrap.dedent(program))
        self.assertEqual(2, program.count("cleanup.invokeAction('forceExitTraining')"))
        self.assertIn("assert bag(saved_player) == baseline_bag", program)
        self.assertIn("assert equipped(saved_player) == baseline_equipped", program)
        self.assertIn("borrower.invokeAction('borrowSelectedEquipment')", program)
        self.assertIn("for actor in (saved_player, *allies):", program)
        self.assertNotIn("setBoolProperty(", program)
        self.assertNotIn("setNumericProperty(", program)


class CandlekeepMetadataRuntimeTest(TestCase):
    runChild = callback_lifecycle.PythonCallbackLifecycleTest.runChild

    def testNativeConfiguredPurchaseAndTrainingSnapshotTextSurviveSaveReload(self):
        output = self.runChild("""
            import json
            import os
            from pathlib import Path
            import time
            prefix = 'candlekeep-json:'
            slot = 'candlekeep-metadata-' + str(os.getpid()) + '-' + str(time.time_ns())
            instance = game.CGameLoader.loadGame()
            restored = None
            completed = False
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'candlekeep', 'Warrior')
                loop.run()
                world = instance.getMap()
                player = world.getPlayer()
                dialog = instance.createObject('winthropDialog')
                encoded = dialog.getStringProperty('shopEntries')
                assert encoded.startswith(prefix)
                row = next(row for row in json.loads(encoded.removeprefix(prefix)) if row['id'] == 'BOLT01')
                assert (row['price'], row['quantity'], row['limit']) == (1, 20, 0)
                before_gold = player.getGold()
                before_count = player.countItems('candlekeepBolts')
                dialog.invokeAction('buyBolts')
                loop.run()
                assert player.getGold() == before_gold - 1
                assert player.countItems('candlekeepBolts') == before_count + 1
                bolts = [item for item in player.getItems() if item.getTypeId() == 'candlekeepBolts']
                assert all(item.getNumericProperty('plugin_candlekeepQuantity') == 20 for item in bolts)
                def bag(actor):
                    return sorted((item.getName(), item.getTypeId()) for item in actor.getItems())
                def equipped(actor):
                    return {key: (item.getName(), item.getTypeId()) for key, item in actor.getEquipped().items() if item}
                baseline_bag, baseline_equipped = bag(player), equipped(player)
                baseline_rewards = (player.getGold(), player.getNumericProperty('exp'))
                instance.createObject('gatewardenDialog').invokeAction('acceptTraining')
                instance.createObject('obeDialog').invokeAction('beginTraining')
                loop.run()
                assert world.getStringProperty('candlekeep_trainingStage') == 'active'
                arkanis = world.getObjectByName('arkanis')
                selected = sorted(arkanis.getItems(), key=lambda item: item.getName())[0]
                borrower = instance.createObject('arkanisDialog')
                # Native callback test supplies the actual owned-item selection; no GUI acceptance is claimed.
                borrower.setStringProperty('selectedBorrow', selected.getName())
                borrower.invokeAction('borrowSelectedEquipment')
                loop.run()
                assert selected in player.getItems() and selected not in arkanis.getItems()
                assert selected.getBoolProperty('plugin_candlekeepTemporary')
                fields = ('candlekeepTrainingInventoryNames', 'candlekeepTrainingEquipment')
                snapshots = {key: player.getStringProperty(key) for key in fields}
                assert all(value.startswith(prefix) for value in snapshots.values())
                owned = sorted((item.getName(), item.getTypeId()) for item in player.getItems())
                equipment = {key: item.getName() for key, item in player.getEquipped().items() if item}
                assert game.CMapLoader.saveWithResult(world, slot)
                restored = game.CGameLoader.loadGame()
                game.CGameLoader.loadSavedGame(restored, slot)
                loop.run()
                saved_world = restored.getMap()
                saved_player = saved_world.getPlayer()
                assert {key: saved_player.getStringProperty(key) for key in fields} == snapshots
                assert sorted((item.getName(), item.getTypeId()) for item in saved_player.getItems()) == owned
                assert {key: item.getName() for key, item in saved_player.getEquipped().items() if item} == equipment
                assert saved_world.getNumericProperty('candlekeepStockBought_winthrop_BOLT01') == 1
                assert saved_player.getGold() == before_gold - 1
                assert saved_player.countItems('candlekeepBolts') == before_count + 1
                allies = [saved_world.getObjectByName(name) for name in
                          ('arkanis', 'canderous', 'deder', 'mordaine', 'osprey')]
                assert all(allies)
                assert any(item.getBoolProperty('plugin_candlekeepTemporary') for item in saved_player.getItems())
                cleanup = restored.createObject('obeDialog')
                cleanup.invokeAction('forceExitTraining')
                loop.run()
                assert saved_world.getStringProperty('candlekeep_trainingStage') == 'abandoned'
                assert bag(saved_player) == baseline_bag
                assert equipped(saved_player) == baseline_equipped
                assert (saved_player.getGold(), saved_player.getNumericProperty('exp')) == baseline_rewards
                for actor in (saved_player, *allies):
                    assert not any(item.getBoolProperty('plugin_candlekeepTemporary')
                                   for item in (*actor.getItems(), *actor.getEquipped().values()) if item)
                assert all(saved_world.getObjectByName(actor.getName()) is None for actor in allies)
                cleanup.invokeAction('forceExitTraining')
                loop.run()
                assert saved_world.getStringProperty('candlekeep_trainingStage') == 'abandoned'
                assert bag(saved_player) == baseline_bag and equipped(saved_player) == baseline_equipped
                assert (saved_player.getGold(), saved_player.getNumericProperty('exp')) == baseline_rewards
                completed = True
                print('native Candlekeep purchase and training metadata saved as exact text', flush=True)
            finally:
                if restored is not None:
                    restored.getContext().shutdown()
                instance.getContext().shutdown()
                if completed:
                    for suffix in ('.json', '.json.bak'):
                        (Path('save') / (slot + suffix)).unlink(missing_ok=True)
            """)
        self.assertIn("native Candlekeep purchase and training metadata saved as exact text", output)
