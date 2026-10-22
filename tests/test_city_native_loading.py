# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real staged city construction/fallback regression; no model or original-parity credit."""

import ast
import textwrap
import unittest
from unittest.mock import patch

from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest


class CityNativeLoadingRuntimeTest(unittest.TestCase):
    runChild = PythonCallbackLifecycleTest.runChild

    def testCityLoadsNativePlacedAndDeferredActorsWithBlockedLayerFallback(self):
        output = self.runChild("""
            import time
            from collections import Counter
            import json
            def decodeCityData(encoded):
                return json.loads(encoded.removeprefix('city-json:'))
            started = time.perf_counter()
            instance = game.CGameLoader.loadGame()
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'baldursGate', 'Warrior')
                loop.run()
                world = instance.getMap()
                assert world.getStringProperty('mapName') == 'baldursGate'
                assert world.getPlayer() is not None
                assert sum(isinstance(actor, game.CPlayer) for actor in world.getObjects()) == 1
                marek = world.getObjectByName('cityAr0300Actor29')
                assert isinstance(marek, game.CCreature)
                assert marek.getType() == 'CCreature', marek.getType()
                assert marek.getTypeId() == 'cityAr0300Actor29'
                assert marek.getStringProperty('sourceCreature') == 'MAREK'
                assert marek.getStringProperty('sourceArea') == 'AR0300'
                assert marek.getStringProperty('sourceInventory')
                inventory = decodeCityData(marek.getStringProperty('sourceInventory'))
                assert inventory and isinstance(inventory, list)
                assert len(decodeCityData(marek.getStringProperty('sourceItemSlots'))) == 40
                assert marek.getBoolProperty('plugin_cityInventoryInitialized')
                owned = {id(item): item for item in (*marek.getItems(), *marek.getEquipped().values()) if item}
                assert Counter(item.getStringProperty('plugin_citySourceItem') for item in owned.values()) == Counter(
                    row['item'] for row in inventory if row['item'] != 'MISC07'
                )
                clock = world.getObjectByName('cityClock')
                assert decodeCityData(clock.getStringProperty('questDefinitions'))['quests']
                assert 'AR0800' in decodeCityData(clock.getStringProperty('areaAtlas'))
                assert decodeCityData(clock.getStringProperty('actorDefinitions'))
                assert isinstance(decodeCityData(clock.getStringProperty('regionDefinitions')), dict)
                assert world.getStringProperty('plugin_cityStartingProfile').startswith('city-json:')
                clone = marek.clone()
                assert clone.getStringProperty('sourceInventory') == marek.getStringProperty('sourceInventory')
                assert clone.getStringProperty('sourceItemSlots') == marek.getStringProperty('sourceItemSlots')
                assert clone.getBoolProperty('plugin_cityInventoryInitialized')
                for suffix in ('Noblpa', 'Noblpa1', 'Noblpa2', 'Noblpa3', 'Noblpa4', 'Noblpa5'):
                    name = 'cityAr0108ScriptActor' + suffix
                    actor = instance.createObject(name)
                    assert isinstance(actor, game.CCreature)
                    assert actor.getType() == 'CCreature', actor.getType()
                    assert actor.getTypeId() == name
                    assert actor.getStringProperty('sourceCreature') == suffix.upper()
                    assert actor.getStringProperty('sourceArea') == 'AR0108'
                    assert isinstance(actor.getFightController(), game.CFightController)
                    assert actor.getFightController().getType() == 'CMonsterFightController'
                for level in range(5):
                    for x, y in ((223, 191), (-1, 0), (224, 192)):
                        tile = world.getTile(x, y, level)
                        point = tile.getCoords()
                        assert (point.x, point.y, point.z) == (x, y, level), (point.x, point.y, point.z)
                        assert tile.getTypeId() == 'cityWallTile', tile.getTypeId()
                        assert not world.canStep(game.Coords(x, y, level)), (x, y, level)
                print(
                    'native city construction and five-level blocked fallback verified',
                    time.perf_counter() - started,
                    flush=True,
                )
            finally:
                instance.getContext().shutdown()
            """)
        self.assertIn("native city construction and five-level blocked fallback verified", output)

    def testCityStructuredMetadataAndOwnedItemsSurviveSaveReload(self):
        output = self.runChild("""
            import os
            from pathlib import Path
            import time
            import json
            def decodeCityData(encoded):
                return json.loads(encoded.removeprefix('city-json:'))
            slot = 'city-metadata-' + str(os.getpid()) + '-' + str(time.time_ns())
            instance = game.CGameLoader.loadGame()
            restored = None
            completed = False
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'baldursGate', 'Warrior')
                loop.run()
                world = instance.getMap()
                marek = world.getObjectByName('cityAr0300Actor29')
                clock = world.getObjectByName('cityClock')
                def snapshot(actor):
                    owned = {id(item): item for item in (*actor.getItems(), *actor.getEquipped().values()) if item}
                    return sorted(
                        (item.getStringProperty('plugin_citySourceItem'), item.getNumericProperty('plugin_cityQuantity'))
                        for item in owned.values()
                    )
                before = snapshot(marek)
                assert before and marek.getBoolProperty('plugin_cityInventoryInitialized')
                inventory = marek.getStringProperty('sourceInventory')
                definitions = clock.getStringProperty('questDefinitions')
                profile = world.getStringProperty('plugin_cityStartingProfile')
                assert all(value.startswith('city-json:') for value in (inventory, definitions, profile))
                assert game.CMapLoader.saveWithResult(world, slot)
                restored = game.CGameLoader.loadGame()
                game.CGameLoader.loadSavedGame(restored, slot)
                loop.run()
                saved_world = restored.getMap()
                assert saved_world.getStringProperty('mapName') == 'baldursGate'
                saved_actor = saved_world.getObjectByName('cityAr0300Actor29')
                saved_clock = saved_world.getObjectByName('cityClock')
                assert saved_actor.getStringProperty('sourceInventory') == inventory
                assert saved_clock.getStringProperty('questDefinitions') == definitions
                assert saved_world.getStringProperty('plugin_cityStartingProfile') == profile
                assert decodeCityData(saved_actor.getStringProperty('sourceInventory'))
                assert decodeCityData(saved_clock.getStringProperty('questDefinitions'))['quests']
                assert saved_actor.getBoolProperty('plugin_cityInventoryInitialized')
                assert snapshot(saved_actor) == before
                completed = True
                print('native city metadata and item ownership survived save reload', flush=True)
            finally:
                if restored is not None:
                    restored.getContext().shutdown()
                instance.getContext().shutdown()
                if completed:
                    for suffix in ('.json', '.json.bak'):
                        (Path('save') / (slot + suffix)).unlink(missing_ok=True)
            """)
        self.assertIn("native city metadata and item ownership survived save reload", output)


class CityNativeLoadingSourceTest(unittest.TestCase):
    def program(self, method_name, marker):
        case = CityNativeLoadingRuntimeTest(method_name)
        programs = []
        with patch.object(
            case, "runChild", side_effect=lambda program, **kwargs: programs.append((program, kwargs)) or marker
        ):
            getattr(case, method_name)()
        self.assertEqual(1, len(programs))
        program, kwargs = programs[0]
        ast.parse(textwrap.dedent(program))
        self.assertEqual({}, kwargs, "Keep the shared bounded child timeout")
        return program

    def testConstructionProbeChecksActualInitializedItemsAndTextMetadata(self):
        program = self.program(
            "testCityLoadsNativePlacedAndDeferredActorsWithBlockedLayerFallback",
            "native city construction and five-level blocked fallback verified",
        )
        self.assertIn("assert marek.getStringProperty('sourceInventory')", program)
        self.assertIn("marek.getBoolProperty('plugin_cityInventoryInitialized')", program)
        self.assertIn("*marek.getItems(), *marek.getEquipped().values()", program)
        self.assertIn("clock.getStringProperty('questDefinitions')", program)
        self.assertIn("clone = marek.clone()", program)

    def testSaveProbeUsesNativePersistenceAndPreservesFailedDiagnostics(self):
        program = self.program(
            "testCityStructuredMetadataAndOwnedItemsSurviveSaveReload",
            "native city metadata and item ownership survived save reload",
        )
        self.assertIn("assert game.CMapLoader.saveWithResult(world, slot)", program)
        self.assertIn("game.CGameLoader.loadSavedGame(restored, slot)", program)
        self.assertIn("assert snapshot(saved_actor) == before", program)
        self.assertIn("if completed:", program)


if __name__ == "__main__":
    unittest.main()
