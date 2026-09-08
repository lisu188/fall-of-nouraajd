# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Screenshot coverage must mount embedded graphics views in their real panel."""

import base64
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from scripts import generate_screenshots


class ScreenshotPanelCoverageTest(unittest.TestCase):
    def testWindowsDefaultsToSoftwareVirtualDisplay(self):
        with mock.patch.object(generate_screenshots.os, "name", "nt"), mock.patch.dict("os.environ", {}, clear=True):
            generate_screenshots._reexec_under_xvfb_if_needed()
            self.assertEqual("dummy", generate_screenshots.os.environ["SDL_VIDEODRIVER"])
            self.assertEqual("software", generate_screenshots.os.environ["SDL_RENDER_DRIVER"])

    def testWindowsRejectsVisibleDesktopDriver(self):
        with (
            mock.patch.object(generate_screenshots.os, "name", "nt"),
            mock.patch.dict("os.environ", {"SDL_VIDEODRIVER": "windows"}, clear=True),
        ):
            with self.assertRaisesRegex(SystemExit, "not a desktop display"):
                generate_screenshots._reexec_under_xvfb_if_needed()

    def testLinuxWithoutVirtualDisplayCannotFallBackToDesktop(self):
        with (
            mock.patch.object(generate_screenshots.os, "name", "posix"),
            mock.patch.dict("os.environ", {"DISPLAY": ":0", "SDL_VIDEODRIVER": "x11"}, clear=True),
            mock.patch("shutil.which", return_value=None),
        ):
            with self.assertRaisesRegex(SystemExit, "require xvfb-run"):
                generate_screenshots._reexec_under_xvfb_if_needed()

    def makeModalSession(self, fail_capture=False):
        callbacks, children, calls = [], [], []
        sim = mock.Mock()
        sim.gameInstance.getGui.return_value.getChildren.side_effect = lambda: list(children)
        sim.gameInstance.getGui.return_value.removeChild.side_effect = children.remove

        def createObject(name):
            value = mock.Mock()
            value.resource_id = name
            return value

        sim.gameInstance.createObject.side_effect = createObject

        class Handler:
            def show(self, name, *arguments):
                panel = mock.Mock(spec=["getType"])
                panel.getType.return_value = generate_screenshots.MODAL_PANELS[name][1]
                children.append(panel)
                calls.append((name, arguments, panel))
                callbacks.pop(0)()
                if children:
                    raise AssertionError("The capture callback must close the blocking native panel")

            def showDialog(self, dialog):
                self.show("dialogPanel", dialog)

            def showLoot(self, creature, items):
                self.show("lootPanel", creature, items)

            def showSelection(self, selection):
                self.show("selectionPanel", selection)

        handler = Handler()
        sim.gameInstance.getGuiHandler.return_value = handler
        game = types.SimpleNamespace(
            CGuiHandler=Handler,
            event_loop=types.SimpleNamespace(instance=lambda: types.SimpleNamespace(invoke=callbacks.append)),
        )

        def captureScreenshot(path):
            self.assertEqual(1, len(children), "Capture must run while the native modal remains attached")
            if fail_capture:
                raise ValueError("Readback failed")
            path.write_bytes(b"\x89PNG\r\n\x1a\n")
            return {"bytes": path.stat().st_size}

        sim.captureGuiScreenshot.side_effect = captureScreenshot
        return game, sim, calls

    def testModalCaptureUsesOriginalNativeBuildersAfterPopupSuppression(self):
        game, sim, calls = self.makeModalSession()
        handlers = generate_screenshots._suppress_blocking_popups(game)
        with tempfile.TemporaryDirectory() as directory:
            for name in generate_screenshots.MODAL_PANELS:
                info = generate_screenshots.captureModalPanel(
                    game, sim, name, Path(directory) / (name + ".png"), handlers
                )
                self.assertGreater(info["bytes"], 0)
        self.assertEqual(list(generate_screenshots.MODAL_PANELS), [call[0] for call in calls])
        self.assertEqual("questDialog", calls[0][1][0].resource_id)
        self.assertEqual({"Scroll", "Sword"}, {item.resource_id for item in calls[1][1][1]})
        self.assertEqual(3, calls[2][1][0].addValue.call_count)
        self.assertEqual(3, sim.gameInstance.getGui.return_value.removeChild.call_count)
        self.assertIsNone(sim.gameInstance.getGuiHandler().showDialog(object()), "Incidental popups remain suppressed")

    def testModalCaptureClosesPanelWhenReadbackFails(self):
        game, sim, calls = self.makeModalSession(fail_capture=True)
        handlers = generate_screenshots._suppress_blocking_popups(game)
        with self.assertRaisesRegex(ValueError, "Readback failed"):
            generate_screenshots.captureModalPanel(game, sim, "lootPanel", Path("unused.png"), handlers)
        sim.gameInstance.getGui.return_value.removeChild.assert_called_once_with(calls[0][2])

    def test_embedded_views_are_captured_inside_fight_panel(self):
        simulation = mock.Mock()
        panel = mock.Mock()
        opened = []

        def openPanel(name):
            if name != "fightPanel":
                raise AssertionError("Embedded graphics views cannot be opened as CGamePanel")
            opened.append(name)
            return panel

        simulation.gameInstance.getGuiHandler.return_value.openPanel.side_effect = openPanel
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jG9sAAAAASUVORK5CYII="
        )

        def captureScreenshot(path):
            path.write_bytes(png)
            return {"bytes": len(png)}

        simulation.captureGuiScreenshot.side_effect = captureScreenshot
        module = types.SimpleNamespace(GameSimulation=types.SimpleNamespace(startGame=lambda *a, **kw: simulation))
        with tempfile.TemporaryDirectory() as directory:
            with (
                mock.patch.dict("sys.modules", {"game_simulation": module}),
                mock.patch.object(generate_screenshots, "_prepare_player_for_panels"),
                mock.patch.object(generate_screenshots, "_configure_panel") as configure,
            ):
                written = generate_screenshots.capture_panels(
                    object(), Path(directory), "Warrior", ["creatureView", "statsView"]
                )
            self.assertEqual(["fightPanel", "fightPanel"], opened)
            self.assertEqual(["panel-creatureView.png", "panel-statsView.png"], [path.name for path in written])
            self.assertEqual(2, panel.close.call_count)
            self.assertEqual(["fightPanel", "fightPanel"], [call.args[1] for call in configure.call_args_list])
            for path in written:
                self.assertEqual(".png", path.suffix)
                self.assertGreater(path.stat().st_size, 0)
                self.assertEqual(b"\x89PNG\r\n\x1a\n", path.read_bytes()[:8])


if __name__ == "__main__":
    unittest.main()
