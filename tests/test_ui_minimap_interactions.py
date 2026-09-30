# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch


class UiMinimapInteractionTest(unittest.TestCase):
    def setUp(self):
        if os.environ.get("GAME_MINIMAP_UI_CHILD") != self._testMethodName:
            return
        import test as harness

        self.harness = harness
        try:
            self.game = harness.load_game_module()
        except ModuleNotFoundError as error:
            if error.name == "_game":
                self.skipTest(str(error))
            raise
        self.instance = self.game.CGameLoader.loadGame()
        self.addCleanup(self.closeSession)
        self.game.CGameLoader.loadGui(self.instance)
        self.game.CGameLoader.startGameWithPlayer(self.instance, "test", "Warrior")
        self.gui = self.instance.getGui()
        self.game_map = self.instance.getMap()
        self.player = self.game_map.getPlayer()
        for obj in list(self.game_map.getObjects()):
            if obj != self.player:
                self.game_map.removeObject(obj)
        harness.pump_event_loop(3)
        self.minimap = next(obj for obj in self.gui.getChildren() if obj.getType() == "CMinimapGraphicsObject")

    def closeSession(self):
        instance = self.instance
        self.minimap = self.gui = self.player = self.game_map = self.instance = None
        instance.getContext().shutdown()

    def runInChild(self):
        if os.environ.get("GAME_MINIMAP_UI_CHILD") == self._testMethodName:
            return False
        command = [
            sys.executable,
            "-m",
            "unittest",
            f"tests.test_ui_minimap_interactions.UiMinimapInteractionTest.{self._testMethodName}",
            "-v",
        ]
        if os.name == "posix":
            for tool in ("xvfb-run", "xauth"):
                if shutil.which(tool) is None:
                    self.skipTest(f"{tool} is required for isolated minimap GUI tests.")
            command = ["xvfb-run", "-a", "--server-args=-screen 0 1920x1080x24", *command]
        with tempfile.TemporaryDirectory(prefix="nouraajd-minimap-ui-") as directory:
            environment = os.environ.copy()
            environment.update(
                GAME_MINIMAP_UI_CHILD=self._testMethodName,
                SDL_VIDEODRIVER="x11" if os.name == "posix" else "dummy",
                SDL_AUDIODRIVER="dummy",
                SDL_RENDER_DRIVER="software",
                LIBGL_ALWAYS_SOFTWARE="1",
                GAME_UI_PREFERENCES_PATH=str(Path(directory) / "preferences.json"),
                GAME_TEST_OUTPUT_DIR=str(Path(directory) / "test-output"),
            )
            process = subprocess.Popen(
                command,
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=(os.name == "posix"),
            )
            timeout = 90 if os.environ.get("GAME_COVERAGE_RUN") == "1" else 30
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
                stdout, stderr = process.communicate()
                self.fail(f"{self._testMethodName} timed out after {timeout}s.\nstdout:\n{stdout}\nstderr:\n{stderr}")
        self.assertEqual(0, process.returncode, stdout + stderr)
        if "OK (skipped=1)" in stderr:
            self.skipTest(stderr.strip())
        return True

    def testTimeoutTerminatesProcessGroupAndRetainsDiagnostics(self):
        for platform in ("posix", "nt"):
            with self.subTest(platform=platform):
                process = Mock(pid=4312)
                process.communicate.side_effect = [
                    subprocess.TimeoutExpired("minimap child", 30),
                    ("partial standard output", "partial standard error"),
                ]
                isolated_os = SimpleNamespace(name=platform, environ={}, killpg=Mock())
                with (
                    patch(__name__ + ".os", isolated_os),
                    patch(__name__ + ".signal", SimpleNamespace(SIGKILL=9)),
                    patch(__name__ + ".shutil.which", return_value="available"),
                    patch(__name__ + ".subprocess.Popen", return_value=process) as launch,
                    patch(__name__ + ".subprocess.run", side_effect=subprocess.TimeoutExpired("minimap child", 30)),
                ):
                    with self.assertRaisesRegex(AssertionError, "timed out") as failure:
                        self.runInChild()
                    self.assertIn("partial standard output", str(failure.exception))
                    self.assertIn("partial standard error", str(failure.exception))
                    self.assertEqual(platform == "posix", launch.call_args.kwargs["start_new_session"])
                    self.assertEqual([call(timeout=30), call()], process.communicate.call_args_list)
                    if platform == "posix":
                        isolated_os.killpg.assert_called_once_with(process.pid, 9)
                        process.kill.assert_not_called()
                    else:
                        isolated_os.killpg.assert_not_called()
                        process.kill.assert_called_once_with()

    def state(self):
        return self.harness.coords_tuple(self.player.getCoords()), self.game_map.getTurn(), self.player.getGold()

    def key(self, keycode):
        self.harness.push_sdl_key_event(keycode, 0, self.harness.SDL_KEYDOWN)
        self.harness.push_sdl_key_event(keycode, 0, self.harness.SDL_KEYUP)
        self.harness.pump_event_loop(3)

    def expandedPanel(self):
        panels = [obj for obj in self.gui.getChildren() if obj.getStringProperty("title") == "Map & landmarks"]
        self.assertEqual(1, len(panels))
        return panels[0]

    def openMap(self):
        self.key(ord("m"))
        return self.expandedPanel()

    def browse(self, inspect, dismiss):
        panel = self.expandedPanel()
        button = next(
            obj
            for obj in self.harness.find_descendants_by_type(panel, "CButton")
            if obj.getStringProperty("click") == "browseLandmarks"
        )

        def action():
            self.harness.push_sdl_mouse_click(*self.harness.rect_center(self.harness.resolved_rect(button)))
            self.harness.pump_event_loop(3)

        return self.harness.run_blocking_panel_inspection(
            self,
            self.game,
            self.instance,
            "CGameCampaignBrowserPanel",
            action,
            inspect,
            dismiss,
        )[1]

    def addLandmark(self, name, label, coords):
        marker = self.instance.createObject("CMapObject")
        marker.name = name
        marker.setStringProperty("label", label)
        marker.setCoords(coords)
        self.game_map.addObject(marker)
        return marker

    def nearbyLandmarks(self):
        origin = self.player.getCoords()
        targets = [
            self.game.Coords(origin.x + dx, origin.y + dy, origin.z)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if self.game_map.canStep(self.game.Coords(origin.x + dx, origin.y + dy, origin.z))
        ]
        self.assertGreaterEqual(len(targets), 2)
        return [
            self.addLandmark("minimapFirst", "First landmark", targets[0]),
            self.addLandmark("minimapSecond", "Second landmark", targets[1]),
        ]

    def testMouseAndKeyboardExpansionConsumeInputWithoutWorldActions(self):
        if self.runInChild():
            return
        before = self.state()
        self.harness.push_sdl_mouse_click(*self.harness.rect_center(self.harness.resolved_rect(self.minimap)))
        self.harness.pump_event_loop(3)
        panel = self.expandedPanel()
        expanded = self.harness.find_descendants_by_type(panel, "CMinimapGraphicsObject")[0]
        self.assertNotEqual(self.harness.resolved_rect(self.minimap), self.harness.resolved_rect(expanded))
        data, width, height = self.gui.read_pixels()
        self.assertEqual((1920, 1080), (width, height))
        self.assertEqual(width * height * 4, len(data))
        self.assertGreater(
            self.harness.panel_pixel_summary(bytes(data), width, height, self.harness.resolved_rect(panel))["inside"], 0
        )
        x, y, w, h = self.harness.resolved_rect(expanded)
        for button in (self.harness.SDL_BUTTON_LEFT, self.harness.SDL_BUTTON_RIGHT):
            self.harness.push_sdl_mouse_click(x + w // 2, y + h // 3, button)
            self.harness.pump_event_loop(2)
        self.key(ord("m"))
        self.assertEqual(panel, self.expandedPanel())
        self.assertEqual(before, self.state())
        self.key(27)
        self.assertFalse(any(obj.getStringProperty("title") == "Map & landmarks" for obj in self.gui.getChildren()))
        self.assertEqual(before, self.state())
        self.openMap()
        self.key(27)
        self.assertEqual(before, self.state())

    def testLandmarksFilterElevationAndPreviewWithoutCommittingMovement(self):
        if self.runInChild():
            return
        landmarks = self.nearbyLandmarks()
        origin = self.player.getCoords()
        self.addLandmark("minimapOtherLevel", "Hidden elevation", self.game.Coords(origin.x, origin.y, origin.z + 1))
        self.addLandmark("minimapUnnamed", "", self.game.Coords(origin.x + 2, origin.y, origin.z))
        before = self.state()
        self.openMap()

        def inspect(panel):
            self.assertEqual("Known landmarks", panel.getStringProperty("title"))
            self.assertEqual("0", panel.getSelectedId())
            details = [panel.getDetailText()]
            panel.keyboardEvent(self.gui, self.harness.SDL_KEYDOWN, self.harness.SDLK_DOWN)
            self.assertEqual("1", panel.getSelectedId())
            details.append(panel.getDetailText())
            panel.keyboardEvent(self.gui, self.harness.SDL_KEYDOWN, self.harness.SDLK_DOWN)
            self.assertEqual("1", panel.getSelectedId(), "Other elevations and unnamed objects must remain absent.")
            for marker in landmarks:
                coords = marker.getCoords()
                self.assertTrue(any(marker.getStringProperty("label") in text for text in details))
                self.assertTrue(any(f"Destination: {coords.x}, {coords.y}" in text for text in details))
            self.assertEqual(before, self.state())

        self.browse(inspect, lambda panel: panel.keyboardEvent(self.gui, self.harness.SDL_KEYDOWN, 27))
        self.expandedPanel()
        self.assertEqual(before, self.state())
        self.key(27)
        self.assertEqual(before, self.state())

    def testExplicitTravelMovesPlayerToSelectedLandmarkAndClosesExpandedMap(self):
        if self.runInChild():
            return
        landmarks = self.nearbyLandmarks()
        before = self.state()
        self.openMap()

        def inspect(panel):
            panel.keyboardEvent(self.gui, self.harness.SDL_KEYDOWN, self.harness.SDLK_DOWN)
            detail = panel.getDetailText()
            target = next(marker.getCoords() for marker in landmarks if marker.getStringProperty("label") in detail)
            self.assertEqual(before, self.state())
            return self.harness.coords_tuple(target)

        target = self.browse(
            inspect, lambda panel: panel.keyboardEvent(self.gui, self.harness.SDL_KEYDOWN, self.harness.SDLK_RETURN)
        )
        self.assertEqual(target, self.harness.coords_tuple(self.player.getCoords()))
        self.assertGreater(self.game_map.getTurn(), before[1])
        self.assertEqual(before[2], self.player.getGold())
        self.assertFalse(any(obj.getStringProperty("title") == "Map & landmarks" for obj in self.gui.getChildren()))
        settled = self.state()
        self.harness.pump_event_loop(5)
        self.assertEqual(settled, self.state(), "Closing the chooser must not replay movement input.")

    def testEmptyLandmarksAndSceneTransitionCannotCommitStaleTravel(self):
        if self.runInChild():
            return
        before = self.state()
        self.openMap()

        def inspect_empty(panel):
            self.assertEqual("", panel.getSelectedId())
            panel.keyboardEvent(self.gui, self.harness.SDL_KEYDOWN, self.harness.SDLK_RETURN)
            self.assertFalse(panel.hasChoice())

        self.browse(inspect_empty, lambda panel: panel.keyboardEvent(self.gui, self.harness.SDL_KEYDOWN, 27))
        self.assertEqual(before, self.state())
        self.nearbyLandmarks()
        replacement = {}

        def replace_scene(panel):
            panel.keyboardEvent(self.gui, self.harness.SDL_KEYDOWN, self.harness.SDLK_RETURN)
            self.game.CGameLoader.startGameWithPlayer(self.instance, "test", "Warrior")
            replacement["map"] = self.instance.getMap()
            replacement["player"] = replacement["map"].getPlayer()
            replacement["coords"] = self.harness.coords_tuple(replacement["player"].getCoords())
            replacement["turn"] = replacement["map"].getTurn()

        self.browse(lambda panel: None, replace_scene)
        self.assertNotEqual(self.game_map, replacement["map"])
        self.assertEqual(replacement["coords"], self.harness.coords_tuple(replacement["player"].getCoords()))
        self.assertEqual(replacement["turn"], replacement["map"].getTurn())
        self.assertEqual(before, self.state())


if __name__ == "__main__":
    unittest.main()
