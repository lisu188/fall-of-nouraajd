# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis

import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import generate_screenshots
from scripts import generate_walkthrough_video


class ScreenshotDisplayIsolationTest(unittest.TestCase):
    def testCapturePreferencesAreIsolatedAndRemovedEvenAfterFailure(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                player_preferences = output / "player-preferences.json"
                player_preferences.write_text('{"textScale":150}', encoding="utf-8")

                def capture(args, output_dir):
                    isolated = Path(generate_screenshots.os.environ["GAME_UI_PREFERENCES_PATH"])
                    self.assertNotEqual(player_preferences, isolated)
                    self.assertEqual("1", generate_screenshots.os.environ["GAME_ENABLE_PYTHON_CONSOLE"])
                    isolated.write_text("{}", encoding="utf-8")
                    if fail:
                        raise RuntimeError("capture failed")

                with (
                    patch.object(generate_screenshots.sys, "argv", ["capture", "--output-dir", directory]),
                    patch.dict(
                        generate_screenshots.os.environ,
                        {"GAME_UI_PREFERENCES_PATH": str(player_preferences), "GAME_ENABLE_PYTHON_CONSOLE": "0"},
                    ),
                    patch.object(generate_screenshots, "generateScreenshots", side_effect=capture),
                ):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, "capture failed"):
                            generate_screenshots.main()
                    else:
                        generate_screenshots.main()
                    self.assertEqual(
                        str(player_preferences), generate_screenshots.os.environ["GAME_UI_PREFERENCES_PATH"]
                    )
                    self.assertEqual("0", generate_screenshots.os.environ["GAME_ENABLE_PYTHON_CONSOLE"])
                self.assertFalse((output / ".capture-preferences.json").exists())
                self.assertEqual('{"textScale":150}', player_preferences.read_text(encoding="utf-8"))

    def testWindowsAlwaysUsesOffscreenSoftwareRendering(self):
        with (
            patch.object(generate_screenshots.os, "name", "nt"),
            patch.dict(generate_screenshots.os.environ, {"SDL_VIDEODRIVER": "windows"}, clear=True),
        ):
            generate_screenshots._reexec_under_xvfb_if_needed()
            self.assertEqual("dummy", generate_screenshots.os.environ["SDL_VIDEODRIVER"])
            self.assertEqual("software", generate_screenshots.os.environ["SDL_RENDER_DRIVER"])
            self.assertEqual("dummy", generate_screenshots.os.environ["SDL_AUDIODRIVER"])

    def testExistingLinuxDesktopIsNeverAnImplicitFallback(self):
        with (
            patch.object(generate_screenshots.os, "name", "posix"),
            patch.dict(generate_screenshots.os.environ, {"DISPLAY": ":0"}, clear=True),
            patch("shutil.which", return_value=None),
            patch.object(generate_screenshots.os, "execvpe") as reexec,
        ):
            with self.assertRaisesRegex(RuntimeError, "requires xvfb-run and xauth"):
                generate_screenshots._reexec_under_xvfb_if_needed()
            reexec.assert_not_called()

    def testVideoCaptureCannotFallBackToThePlayersDesktop(self):
        with (
            patch.object(generate_walkthrough_video.os, "name", "posix"),
            patch.dict(generate_walkthrough_video.os.environ, {"DISPLAY": ":0", "SDL_VIDEODRIVER": "x11"}, clear=True),
            patch("shutil.which", return_value=None),
        ):
            with self.assertRaisesRegex(RuntimeError, "requires xvfb-run and xauth"):
                generate_walkthrough_video._reexec_under_xvfb_if_needed()
        with (
            patch.object(generate_walkthrough_video.os, "name", "nt"),
            patch.dict(generate_walkthrough_video.os.environ, {}, clear=True),
        ):
            generate_walkthrough_video._reexec_under_xvfb_if_needed()
            self.assertEqual("dummy", generate_walkthrough_video.os.environ["SDL_VIDEODRIVER"])
            self.assertEqual("software", generate_walkthrough_video.os.environ["SDL_RENDER_DRIVER"])

    def testExplicitOffscreenLinuxCaptureDoesNotNeedXvfb(self):
        with (
            patch.object(generate_screenshots.os, "name", "posix"),
            patch.dict(generate_screenshots.os.environ, {"SDL_VIDEODRIVER": "offscreen"}, clear=True),
            patch.object(generate_screenshots.os, "execvpe") as reexec,
        ):
            generate_screenshots._reexec_under_xvfb_if_needed()
            self.assertEqual("offscreen", generate_screenshots.os.environ["SDL_VIDEODRIVER"])
            reexec.assert_not_called()


class ScreenshotPanelSetupTest(unittest.TestCase):
    def modifierFixture(self):
        sim = Mock()
        gui = sim.gameInstance.getGui.return_value
        panel = Mock()
        panel.getParent.return_value = gui
        panel.isVisible.return_value = True
        button = Mock()
        button.getStringProperty.return_value = "inspectModifiers"
        button.isVisible.return_value = True
        panel.getChildren.return_value = [button]
        reader = Mock()
        reader.getParent.return_value = gui
        reader.isVisible.return_value = True
        reader.getStringProperty.return_value = "Stat modifiers"
        reader.getText.return_value = "Hero base\nStrength: +5\nCurrent totals\nStrength: +8"
        displayed = {"CGameCharacterPanel": panel}
        gui.findChild.side_effect = lambda name: displayed.get(name)
        return sim, gui, panel, button, reader, displayed

    def testModifiersCannotCaptureAfterCharacterHasClosedOrBecomeHidden(self):
        for unavailable in ("detached", "hidden", "replaced"):
            with self.subTest(unavailable=unavailable):
                sim, gui, panel, button, reader, displayed = self.modifierFixture()
                if unavailable == "detached":
                    panel.getParent.return_value = None
                    displayed.clear()
                elif unavailable == "hidden":
                    panel.isVisible.return_value = False
                else:
                    displayed["CGameCharacterPanel"] = Mock()
                record = Mock()
                with (
                    patch.object(generate_screenshots, "clickCaptureWidget") as click,
                    patch.object(generate_screenshots, "keyCapture") as key,
                    self.assertRaisesRegex(RuntimeError, "Character panel is not attached and visible"),
                ):
                    generate_screenshots.captureCharacterModifiers(sim, panel, record)
                click.assert_not_called()
                key.assert_not_called()
                record.assert_not_called()

    def testModifiersCannotCaptureWorldOrAnotherReaderAfterClick(self):
        for invalid_reader in ("missing", "wrong title", "hidden", "detached", "empty"):
            with self.subTest(invalid_reader=invalid_reader):
                sim, gui, panel, button, reader, displayed = self.modifierFixture()
                if invalid_reader == "wrong title":
                    reader.getStringProperty.return_value = "Discovery"
                elif invalid_reader == "hidden":
                    reader.isVisible.return_value = False
                elif invalid_reader == "detached":
                    reader.getParent.return_value = None
                elif invalid_reader == "empty":
                    reader.getText.return_value = ""

                def click(*args):
                    if invalid_reader != "missing":
                        displayed["CGameTextPanel"] = reader

                record = Mock()
                with (
                    patch.object(generate_screenshots, "clickCaptureWidget", side_effect=click),
                    patch.object(generate_screenshots, "keyCapture") as key,
                    self.assertRaisesRegex(RuntimeError, "Stat modifiers reader is not attached and visible"),
                ):
                    generate_screenshots.captureCharacterModifiers(sim, panel, record)
                record.assert_not_called()
                key.assert_not_called()

    def testModifiersCaptureRequiresVisibleReaderAndPreservesCharacterAfterDismissal(self):
        sim, gui, panel, button, reader, displayed = self.modifierFixture()

        def click(actual_sim, actual_button):
            self.assertIs(sim, actual_sim)
            self.assertIs(button, actual_button)
            displayed["CGameTextPanel"] = reader

        def record(name):
            self.assertEqual("management-character-modifiers", name)
            self.assertIs(reader, displayed["CGameTextPanel"])
            self.assertIs(panel, displayed["CGameCharacterPanel"])

        def dismiss(actual_sim, key):
            self.assertIs(sim, actual_sim)
            self.assertEqual(27, key)
            del displayed["CGameTextPanel"]

        with (
            patch.object(generate_screenshots, "clickCaptureWidget", side_effect=click) as click_mock,
            patch.object(generate_screenshots, "keyCapture", side_effect=dismiss) as key_mock,
        ):
            generate_screenshots.captureCharacterModifiers(sim, panel, record)
        click_mock.assert_called_once()
        key_mock.assert_called_once()
        self.assertIs(panel, displayed["CGameCharacterPanel"])

    def testTargetedAcceptanceCaptureDoesNotRepeatTheBaselineAndVerifiesEveryArtifact(self):
        args = SimpleNamespace(
            maps=None,
            player="Warrior",
            maps_only=False,
            management_only=False,
            frontend_only=False,
            acceptance_only=True,
            panels_only=False,
            no_random=False,
        )
        output = Path("screenshots")
        paths = [output / "frontend-defeat.png", output / "management-crafting-failure.png"]
        with (
            patch.object(generate_screenshots, "_reexec_under_xvfb_if_needed"),
            patch.object(generate_screenshots, "_bootstrap_paths"),
            patch.object(generate_screenshots, "_load_game_module", return_value=Mock()),
            patch.object(generate_screenshots, "_suppress_blocking_popups"),
            patch.object(generate_screenshots, "captureAcceptanceStates", return_value=paths) as capture,
            patch.object(generate_screenshots, "capture_panels") as panels,
            patch.object(generate_screenshots, "capture_management") as management,
            patch.object(generate_screenshots, "capture_frontend") as frontend,
            patch.object(generate_screenshots, "capture_map") as maps,
            patch.object(generate_screenshots, "verifyScreenshot") as verify,
        ):
            generate_screenshots.generateScreenshots(args, output)
        capture.assert_called_once()
        for omitted in (panels, management, frontend, maps):
            omitted.assert_not_called()
        self.assertEqual(paths, [call.args[0] for call in verify.call_args_list])

    def testTargetedAcceptanceCaptureFailureCannotReportSuccess(self):
        args = SimpleNamespace(
            maps=None,
            player="Warrior",
            maps_only=False,
            management_only=False,
            frontend_only=False,
            acceptance_only=True,
            panels_only=False,
            no_random=False,
        )
        with (
            patch.object(generate_screenshots, "_reexec_under_xvfb_if_needed"),
            patch.object(generate_screenshots, "_bootstrap_paths"),
            patch.object(generate_screenshots, "_load_game_module", return_value=Mock()),
            patch.object(generate_screenshots, "_suppress_blocking_popups"),
            patch.object(generate_screenshots, "captureAcceptanceStates", side_effect=RuntimeError("no receipt")),
        ):
            with self.assertRaisesRegex(SystemExit, "1 screenshot target"):
                generate_screenshots.generateScreenshots(args, Path("screenshots"))

    def testReadmeAliasesRefreshOnlyFromThisRunsCapturedFrames(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            fresh = output / "panel-inventoryPanel.png"
            fresh.write_bytes(b"fresh capture")
            (output / "inventory.png").write_bytes(b"old capture")
            (output / "combat.png").write_bytes(b"separate capture")
            aliases = generate_screenshots.refreshScreenshotAliases(output, [fresh])
            self.assertEqual([output / "inventory.png"], aliases)
            self.assertEqual(b"fresh capture", (output / "inventory.png").read_bytes())
            self.assertEqual(b"separate capture", (output / "combat.png").read_bytes())
            selected = output / "management-inventoryPanel-selected.png"
            selected.write_bytes(b"selected details")
            generate_screenshots.refreshScreenshotAliases(output, [fresh, selected])
            self.assertEqual(b"selected details", (output / "inventory.png").read_bytes())

    def testScreenshotVerificationDecodesPngAndRejectsBrokenOutput(self):
        from game_simulation import GameSimulation

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.png"
            path.write_bytes(GameSimulation._encodePng(bytes([32, 37, 44, 255]), 1, 1))
            generate_screenshots.verifyScreenshot(path)
            path.write_bytes(b"broken PNG")
            with self.assertRaises((OSError, ValueError)):
                generate_screenshots.verifyScreenshot(path)

    def testNestedViewsUseConfiguredFightPanelBeforeRendering(self):
        for resource in ("creatureView", "statsView", "fightPanel"):
            with self.subTest(resource=resource):
                events = []
                panel = Mock()
                handler = Mock()

                def openPanel(name):
                    self.assertEqual("fightPanel", name)
                    events.append("open")
                    return panel

                handler.openPanel.side_effect = openPanel
                sim = Mock()
                sim.gameInstance.getGuiHandler.return_value = handler
                sim.pumpEvents.side_effect = lambda count: self.assertIn("configure", events)
                sim.captureGuiScreenshot.return_value = {"bytes": 123}
                simulation_module = SimpleNamespace(GameSimulation=SimpleNamespace(startGame=Mock(return_value=sim)))
                with (
                    patch.dict("sys.modules", {"game_simulation": simulation_module}),
                    patch.object(generate_screenshots, "_prepare_player_for_panels"),
                    patch.object(
                        generate_screenshots,
                        "_configure_panel",
                        side_effect=lambda instance, name, widget: events.append("configure"),
                    ) as configure,
                ):
                    written = generate_screenshots.capture_panels(Mock(), Path("screenshots"), "Warrior", [resource])
                self.assertEqual([Path("screenshots") / f"panel-{resource}.png"], written)
                configure.assert_called_once_with(sim.gameInstance, "fightPanel", panel)
                self.assertEqual(["open", "configure"], events)
                panel.close.assert_called_once()

    def testNativePanelsAreConfiguredBeforeCaptureAndClosedThroughHandler(self):
        panel_types = {
            "campaignBrowserPanel": ("showChoice", "CGameCampaignBrowserPanel"),
            "dialogPanel": ("showDialog", "CGameDialogPanel"),
            "lootPanel": ("showLoot", "CGameLootPanel"),
            "selectionPanel": ("showSelection", "CGameCampaignBrowserPanel"),
        }
        for panel_name, (helper_name, panel_class) in panel_types.items():
            with self.subTest(panel=panel_name):
                events = []
                callbacks = []
                # Some native panels downcast only to CGameObject in Python and
                # consequently expose no close() or panel-specific setters.
                panel = SimpleNamespace(setStringProperty=Mock())
                sim = Mock()
                handler = sim.gameInstance.getGuiHandler.return_value
                sim.gameInstance.getGui.return_value.findChild.return_value = panel
                sim.pumpEvents.side_effect = lambda count: self.assertEqual(["configured"], events)
                sim.captureGuiScreenshot.return_value = {"bytes": 123}
                game = SimpleNamespace(
                    event_loop=SimpleNamespace(instance=lambda: SimpleNamespace(invoke=callbacks.append))
                )

                def showPanel(actual_handler, *arguments):
                    self.assertIs(handler, actual_handler)
                    self.assertTrue(arguments)
                    events.append("configured")
                    callbacks.pop()()

                campaigns = SimpleNamespace(
                    chapterCount=lambda manifest: "1",
                    list_campaigns=lambda: [
                        {"campaignId": "testCampaign", "title": "Test campaign", "scenarios": ["map"]}
                    ],
                )
                path = Path("screenshots") / f"panel-{panel_name}.png"
                with (
                    patch.dict("sys.modules", {"campaign": campaigns}),
                    patch.dict(generate_screenshots.NATIVE_GUI_HELPERS, {helper_name: showPanel}),
                ):
                    info = generate_screenshots._captureNativePanel(game, sim, panel_name, path)
                self.assertEqual({"bytes": 123}, info)
                sim.gameInstance.getGui.return_value.findChild.assert_called_once_with(panel_class)
                sim.captureGuiScreenshot.assert_called_once_with(path=path)
                handler.flipPanel.assert_called_once_with(
                    "campaignBrowserPanel" if panel_name == "selectionPanel" else panel_name, "x"
                )

    def testCampaignButtonUsesTheExposedPropertyApi(self):
        child = SimpleNamespace(getType=lambda: "CButton", setStringProperty=Mock())
        panel = SimpleNamespace(setStringProperty=Mock(), setCloseable=Mock(), getChildren=lambda: [child])
        campaigns = SimpleNamespace(
            list_campaigns=lambda: [
                {
                    "start": "first",
                    "scenarios": {"first": {"title": "The first chapter", "briefing": "Follow the road."}},
                }
            ]
        )
        with patch.dict("sys.modules", {"campaign": campaigns}):
            generate_screenshots._configure_panel(Mock(), "campaignPanel", panel)
        child.setStringProperty.assert_called_once_with("text", "Begin chapter")
        panel.setStringProperty.assert_any_call("body", "Follow the road.")
        panel.setCloseable.assert_called_once_with(False)

    def testNewFrontendModalsCancelDuringMapSetup(self):
        names = (
            "showMessage",
            "showInfo",
            "showQuestion",
            "showSelection",
            "showLoot",
            "showTrade",
            "showDialog",
            "showCampaignSelection",
            "showCampaignScreen",
            "showCampaignArtworkScreen",
            "showChoice",
            "showConfirm",
            "showCharacterCreationOptions",
            "showCharacterCreation",
            "showTextInput",
            "showLoading",
            "hideLoading",
            "showPauseMenu",
            "showSaveMenu",
        )
        handler = type("CaptureHandler", (), {name: Mock() for name in names})
        originals = {name: getattr(handler, name) for name in names}
        with patch.dict(generate_screenshots.NATIVE_GUI_HELPERS, {}, clear=True):
            generate_screenshots._suppress_blocking_popups(SimpleNamespace(CGuiHandler=handler))
            instance = handler()
            self.assertEqual("", instance.showChoice("Title", "[]", "Select", "Back"))
            self.assertEqual("", instance.showTextInput("Save", "Name", "Suggested"))
            self.assertEqual(("", ""), instance.showCharacterCreationOptions("[]", "[]"))
            self.assertFalse(instance.showConfirm("Confirm", "Body", "Accept", "Cancel"))
            self.assertEqual(originals, generate_screenshots.NATIVE_GUI_HELPERS)

    def testDeliberateNativeCaptureClosesEvenWhenScreenshotFails(self):
        panel = Mock()
        sim = Mock()
        sim.gameInstance.getGui.return_value.findChild.return_value = panel
        sim.captureGuiScreenshot.side_effect = OSError("Cannot write PNG")
        callbacks = []
        game = SimpleNamespace(event_loop=SimpleNamespace(instance=lambda: SimpleNamespace(invoke=callbacks.append)))
        native = lambda *args: callbacks.pop()()
        with patch.dict(generate_screenshots.NATIVE_GUI_HELPERS, {"showChoice": native}):
            with self.assertRaisesRegex(RuntimeError, "Cannot write PNG"):
                generate_screenshots._captureNativeCall(
                    game,
                    sim,
                    "showChoice",
                    "CGameCampaignBrowserPanel",
                    ("Title", "[]", "Select", "Back"),
                    Path("unwritable.png"),
                )
        panel.close.assert_called_once()

    def testNativeButtonCaptureWaitsForItsModalInsteadOfCapturingTheUnderlyingPanel(self):
        panel = Mock()
        sim = Mock()
        sim.gameInstance.getGui.return_value.findChild.side_effect = [None, panel]
        sim.captureGuiScreenshot.return_value = {"bytes": 100}
        callbacks = []
        game = SimpleNamespace(event_loop=SimpleNamespace(instance=lambda: SimpleNamespace(invoke=callbacks.append)))

        def click():
            callbacks.pop(0)()
            sim.captureGuiScreenshot.assert_not_called()
            callbacks.pop(0)()

        info = generate_screenshots._captureNativeCall(
            game, sim, "showChoice", "CGameCampaignBrowserPanel", (), Path("landmarks.png"), open_action=click
        )[1]
        self.assertEqual(100, info["bytes"])
        panel.close.assert_called_once()

    def testNativeButtonCaptureCannotPassOnOnlyAnAttemptWithoutAnArtifact(self):
        sim = Mock()
        sim.gameInstance.getGui.return_value.findChild.return_value = None
        callbacks = []
        game = SimpleNamespace(event_loop=SimpleNamespace(instance=lambda: SimpleNamespace(invoke=callbacks.append)))
        with self.assertRaisesRegex(RuntimeError, "No capture callback"):
            generate_screenshots._captureNativeCall(
                game,
                sim,
                "showChoice",
                "CGameCampaignBrowserPanel",
                (),
                Path("missing.png"),
                open_action=lambda: callbacks.pop(0)(),
            )
        sim.captureGuiScreenshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
