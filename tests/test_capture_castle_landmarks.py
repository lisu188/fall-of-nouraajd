# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Screen isolation and viewport evidence without loading SDL or native game code."""

import os
import types
import unittest
from unittest import mock

from scripts import capture_castle_landmarks as capture


class CastleLandmarkCaptureTest(unittest.TestCase):
    def simulation(self, *, cell_size=32, player_position=(64, 64), include_landmark=True, landmark_z=1):
        player = types.SimpleNamespace(getName=lambda: "player", getCoords=lambda: types.SimpleNamespace(z=1))
        landmark = types.SimpleNamespace(
            getName=lambda: "Terraneus", getCoords=lambda: types.SimpleNamespace(z=landmark_z)
        )

        def proxy(represented, coords):
            return types.SimpleNamespace(
                getResolvedRect=lambda: (*coords, cell_size, cell_size),
                getChildren=lambda: [types.SimpleNamespace(getObject=lambda: represented)],
            )

        proxies = [proxy(player, player_position)]
        if include_landmark:
            proxies.append(proxy(landmark, (32, 64)))
        map_graph = types.SimpleNamespace(
            refresh=mock.Mock(),
            refreshAll=mock.Mock(),
            getChildren=lambda: proxies,
            getResolvedRect=lambda: (0, 0, 96, 96),
        )
        gui = types.SimpleNamespace(findChild=lambda name: map_graph, getNumericProperty=lambda name: 96)
        return types.SimpleNamespace(
            gameInstance=types.SimpleNamespace(getGui=lambda: gui),
            player=player,
            pumpEvents=mock.Mock(),
            objectByName=lambda name: landmark,
        )

    def test_captured_evidence_uses_refreshed_native_rectangles(self):
        simulation = self.simulation()
        evidence = capture.viewportEvidence(simulation, "Terraneus", 32)
        self.assertEqual([64, 64, 32, 32], evidence["playerRect"])
        self.assertEqual([32, 64, 32, 32], evidence["landmarkRect"])
        simulation.gameInstance.getGui().findChild("CMapGraphicsObject").refreshAll.assert_called_once()

    def test_stale_size_camera_missing_landmark_and_wrong_floor_are_rejected(self):
        cases = (
            {"cell_size": 50},
            {"player_position": (0, 0)},
            {"include_landmark": False},
            {"landmark_z": 0},
        )
        for parameters in cases:
            with self.subTest(parameters=parameters), self.assertRaises(RuntimeError):
                capture.viewportEvidence(self.simulation(**parameters), "Terraneus", 32)

    def test_windows_always_uses_an_offscreen_software_renderer(self):
        with (
            mock.patch.object(capture.os, "name", "nt"),
            mock.patch.dict(os.environ, {"SDL_VIDEODRIVER": "windows"}, clear=True),
        ):
            capture.ensureVirtualScreen()
            self.assertEqual("dummy", os.environ["SDL_VIDEODRIVER"])
            self.assertEqual("dummy", os.environ["SDL_AUDIODRIVER"])
            self.assertEqual("software", os.environ["SDL_RENDER_DRIVER"])

    def test_linux_launches_dedicated_xvfb_even_when_desktop_display_exists(self):
        with (
            mock.patch.object(capture.os, "name", "posix"),
            mock.patch.dict(os.environ, {"DISPLAY": ":0"}, clear=True),
            mock.patch.object(capture.shutil, "which", side_effect=lambda name: "/usr/bin/" + name),
            mock.patch.object(capture.os, "execvpe") as execute,
        ):
            capture.ensureVirtualScreen()
            executable, arguments, environment = execute.call_args.args
            self.assertEqual("/usr/bin/xvfb-run", executable)
            self.assertIn("--server-args=-screen 0 1920x1080x24", arguments)
            self.assertEqual("1", environment["GAME_CASTLE_VIRTUAL_SCREEN"])
            self.assertEqual("x11", environment["SDL_VIDEODRIVER"])


if __name__ == "__main__":
    unittest.main()
