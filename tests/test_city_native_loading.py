# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real staged city construction/fallback regression; no model or original-parity credit."""

import unittest

from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest


class CityNativeLoadingRuntimeTest(unittest.TestCase):
    runChild = PythonCallbackLifecycleTest.runChild

    def testCityLoadsNativePlacedAndDeferredActorsWithBlockedLayerFallback(self):
        output = self.runChild("""
            import time
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


if __name__ == "__main__":
    unittest.main()
