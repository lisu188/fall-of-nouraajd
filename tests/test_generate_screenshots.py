# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import generate_screenshots


class ScreenshotPanelSetupTest(unittest.TestCase):
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
            "campaignBrowserPanel": ("showCampaignSelection", "CGameCampaignBrowserPanel"),
            "dialogPanel": ("showDialog", "CGameDialogPanel"),
            "lootPanel": ("showLoot", "CGameLootPanel"),
            "selectionPanel": ("showSelection", "CGamePanel"),
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
                    list_campaigns=lambda: [
                        {"campaignId": "testCampaign", "title": "Test campaign", "scenarios": ["map"]}
                    ]
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
                handler.flipPanel.assert_called_once_with(panel_name, "x")

    def testCampaignButtonUsesTheExposedPropertyApi(self):
        child = SimpleNamespace(getType=lambda: "CButton", setStringProperty=Mock())
        panel = SimpleNamespace(setStringProperty=Mock(), getChildren=lambda: [child])
        generate_screenshots._configure_panel(Mock(), "campaignPanel", panel)
        child.setStringProperty.assert_called_once_with("text", "BEGIN")


if __name__ == "__main__":
    unittest.main()
