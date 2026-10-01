# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real-player routing contracts through the stream-draining stdio MCP harness."""

import json
import os
import unittest
from unittest.mock import patch


class NavigationCallbackTest(unittest.TestCase):
    def testMapMoveAllowsWorkerNavigationToCallPythonTileFactory(self):
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        child = PythonCallbackLifecycleTest(methodName="runTest")
        output = child.runChild("""
            import json
            import threading
            import time
            current = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(current, 'multilevel', 'Warrior')
            world = current.getMap()
            player = world.getPlayer()
            assert current.getGui() is None
            owner_thread = threading.get_ident()
            factory_threads = []
            worker_callback = threading.Event()
            main_callbacks = []
            observing_move = False
            def makeMountain():
                caller = threading.get_ident()
                if observing_move:
                    factory_threads.append(caller)
                    if caller == owner_thread:
                        main_callbacks.append(worker_callback.wait(5))
                    else:
                        worker_callback.set()
                # A supported Python factory can release the GIL. It must not
                # retain the map mutex while another controller queries tiles.
                time.sleep(.001)
                tile = current.createObject('CTile')
                tile.setBoolProperty('canStep', False)
                return tile
            handler = current.getObjectHandler()
            handler.registerType('navigationPythonMountain', makeMountain)
            handler.registerConfigJson('MountainTile', json.dumps({'class': 'navigationPythonMountain'}))
            first_name, second_name = 'navigationFirstActor', 'navigationSecondActor'
            for name, y in ((first_name, 1), (second_name, 3)):
                actor = current.createObject('Gooby')
                actor.setStringProperty('name', name)
                actor.setNumericProperty('posx', 6)
                actor.setNumericProperty('posy', y)
                world.addObject(actor)
            actors = []
            world.forObjects(actors.append, lambda obj: obj.getName() in (first_name, second_name))
            assert len(actors) == 2
            chaser, range_actor = actors
            chaser.relocateWithoutMoveHooks(game.Coords(6, 1, 0))
            range_actor.relocateWithoutMoveHooks(game.Coords(6, 3, 0))
            controller = current.createObject('CTargetController')
            controller.setTarget(player.getName())
            chaser.setController(controller)
            range_controller = current.createObject('CRangeController')
            range_controller.setTarget(player.getName())
            range_controller.setDistance(20)
            range_actor.setController(range_controller)
            before_turn = world.getTurn()
            factory_threads.clear()
            observing_move = True
            print('starting Python tile factory navigation', flush=True)
            world.move()
            loop.run()
            assert world.getTurn() == before_turn + 1
            assert (chaser.getCoords().x, chaser.getCoords().y, chaser.getCoords().z) == (5, 1, 0)
            assert (player.getCoords().x, player.getCoords().y, player.getCoords().z) == (1, 1, 0)
            assert factory_threads, 'The route must actually exercise the dynamic fallback factory'
            assert any(thread != owner_thread for thread in factory_threads), factory_threads
            assert main_callbacks and all(main_callbacks), 'Synchronous controller must overlap worker callbacks'
            ranged_coords = range_actor.getCoords()
            assert ranged_coords.z == 0
            assert max(abs(ranged_coords.x - 6), abs(ranged_coords.y - 3)) <= 1
            assert world.canStep(ranged_coords)
            print('worker Python tile callback completed one real mixed-controller map turn', flush=True)
            current.getContext().shutdown()
            """)
        self.assertIn("worker Python tile callback completed one real mixed-controller map turn", output)


class NavigationMcpWalkthroughTest(unittest.TestCase):
    def setUp(self):
        import test as harness

        if not any(
            list(path.glob("_game*.pyd")) + list(path.glob("_game*.so"))
            for path in [harness.build_dir, *harness.extension_dirs]
        ):
            self.skipTest("The current _game extension is required for navigation MCP walkthroughs")
        environment = patch.dict(
            os.environ,
            SDL_VIDEODRIVER="dummy",
            SDL_AUDIODRIVER="dummy",
            SDL_RENDER_DRIVER="software",
            LIBGL_ALWAYS_SOFTWARE="1",
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.harness = harness.McpServerTest(methodName="runTest")
        self.process = self.harness._start_stdio_mcp_process()
        self.addCleanup(self.harness._shutdown_process, self.process)
        self.harness._initialize_stdio_mcp(self.process)
        self.session = {"proc": self.process, "next_request_id": 3}
        self.game = self.engine("CGameLoader.loadGame")
        self.engine("CGameLoader.startGameWithPlayer", self.game, "multilevel", "Warrior")
        self.world = self.call(self.game, "getMap")
        self.player = self.call(self.world, "getPlayer")
        self.controller = self.call(self.player, "getController")
        self.assertIsNone(self.call(self.game, "getGui"), "The walkthrough must never create a desktop window")
        self.pump()

    def engine(self, name, *args):
        return self.harness._mcp_engine_call(self.session, name, list(args), timeout=90)

    def call(self, handle, method, *args):
        return self.harness._mcp_handle_call(self.session, handle, method, list(args), timeout=90)

    def pump(self):
        loop = self.engine("event_loop.instance")
        for _ in range(2):
            self.call(loop, "run")

    def playerState(self):
        properties = json.loads(self.engine("jsonify", self.player))["properties"]
        return {
            "coords": [properties.get(key) for key in ("posx", "posy", "posz")],
            "hp": properties.get("hp"),
            "mana": self.call(self.player, "getMana"),
            "items": properties.get("items"),
            "turn": self.call(self.world, "getTurn"),
        }

    def target(self, name):
        obj = self.call(self.world, "getObjectByName", name)
        self.assertIsNotNone(obj, name)
        coords = self.call(obj, "getCoords")
        self.call(self.controller, "setTarget", self.player, coords)
        return coords

    def advance(self):
        self.call(self.world, "move")
        self.pump()
        return self.playerState()

    def reach(self, predicate, max_turns=24):
        for _ in range(max_turns):
            state = self.playerState()
            if predicate(state["coords"]):
                return state
            self.advance()
        self.fail(f"Real player did not reach the authored destination: {self.playerState()}")

    def testRepeatedPlanningIsReadOnlyAndAuthoredStairsRemainTraversable(self):
        before = self.playerState()
        for _ in range(4):
            self.target("stairsUp")
            self.assertFalse(self.call(self.controller, "isCompleted", self.player))
        self.assertEqual(before, self.playerState(), "Planning cannot move, advance turns or consume resources")
        upper = self.reach(lambda coords: coords[2] == 1)
        self.assertEqual([4, 1, 1], upper["coords"])
        self.assertTrue(self.call(self.world, "getBoolProperty", "used_stairs_up"))
        self.target("multilevelUpperGoal")
        self.reach(lambda coords: coords == [6, 4, 1])
        self.assertTrue(self.call(self.world, "getBoolProperty", "visited_upper_goal"))
        self.target("stairsDown")
        self.reach(lambda coords: coords[2] == 0)
        self.assertTrue(self.call(self.world, "getBoolProperty", "used_stairs_down"))
        self.target("multilevelLowerGoal")
        final = self.reach(lambda coords: coords == [6, 5, 0])
        self.assertTrue(self.call(self.world, "getBoolProperty", "visited_lower_goal"))
        self.assertGreater(final["turn"], before["turn"])
        self.assertEqual(before["items"], final["items"])

    def testBlockedCommittedDestinationDoesNotResumeUntilExplicitRetarget(self):
        stairs = self.target("stairsUp")
        first = self.advance()
        self.assertEqual([2, 1, 0], first["coords"], "The real player must begin the authored route")
        self.call(self.world, "replaceTile", "MountainTile", stairs)
        self.assertFalse(self.call(self.world, "canStep", stairs))
        stopped = self.advance()
        self.assertEqual(first["coords"], stopped["coords"])
        self.assertTrue(self.call(self.controller, "isCompleted", self.player))
        self.call(self.world, "replaceTile", "GroundTile", stairs)
        self.assertTrue(self.call(self.world, "canStep", stairs))
        reopened = self.advance()
        self.assertEqual(
            stopped["coords"], reopened["coords"], "Reopening the route must not restore an abandoned order"
        )
        self.assertTrue(self.call(self.controller, "isCompleted", self.player))
        self.target("stairsUp")
        self.reach(lambda coords: coords[2] == 1)
        self.assertTrue(self.call(self.world, "getBoolProperty", "used_stairs_up"))


if __name__ == "__main__":
    unittest.main()
