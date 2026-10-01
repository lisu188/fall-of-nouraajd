# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stable character identities, shared frontend routes, and virtual-display chooser acceptance."""

import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "res") not in sys.path:
    sys.path.insert(0, str(ROOT / "res"))
import ui

CLASSES = ("Assasin", "Inquisitor", "Sorcerer", "Warrior", "Wayfarer")
RACES = ("highlanderRace", "humanRace", "outlanderRace", "wandererRace")


class CharacterCreationFlowTest(unittest.TestCase):
    def choices(self):
        return (
            [{"id": value, "label": value} for value in CLASSES],
            [{"id": value, "label": value} for value in RACES],
        )

    def session(self):
        game = Mock()
        game.getMap.return_value = None
        game.getContext.return_value.isActive.return_value = True
        game.getResourcesProvider.return_value.getFiles.return_value = ["test"]
        return game

    def testExistingRosterHasExactlyTwentyCompositions(self):
        monsters = json.loads((ROOT / "res/config/monsters.json").read_text())
        races = json.loads((ROOT / "res/config/creature_races.json").read_text())
        self.assertEqual(set(CLASSES), {key for key, value in monsters.items() if value.get("class") == "CPlayer"})
        self.assertEqual(
            set(RACES), {key for key, value in races.items() if value.get("properties", {}).get("playerSelectable")}
        )
        self.assertEqual(20, len(CLASSES) * len(RACES))

    def testEveryCompositionPassesTheSameStableIdsThroughEachNewAdventureRoute(self):
        for class_id in CLASSES:
            for race_id in RACES:
                for mode in ("scenario", "campaign", "random"):
                    with self.subTest(class_id=class_id, race_id=race_id, mode=mode):
                        game = self.session()
                        game.getGuiHandler.return_value.showCharacterCreationOptions.return_value = (class_id, race_id)
                        loader = Mock()
                        loaded = Mock()

                        def start(*args):
                            game.getMap.return_value = loaded

                        loader.startGameWithPlayer.side_effect = start
                        loader.startRandomGameWithPlayer.side_effect = start
                        campaign_start = Mock(side_effect=start)
                        with (
                            patch.dict(sys.modules, _game=types.SimpleNamespace(CGameLoader=loader)),
                            patch.object(ui, "choose", side_effect=[mode, "test"] if mode == "scenario" else [mode]),
                            patch.object(ui, "chooseCampaign", return_value="fallOfNouraajd"),
                            patch.object(ui, "characterChoices", return_value=self.choices()),
                            patch.object(ui.campaign, "list_campaigns", return_value=[]),
                            patch.object(ui.campaign, "start", campaign_start),
                        ):
                            self.assertTrue(ui.newAdventure(game))
                        game.getGuiHandler.return_value.showCharacterCreationOptions.assert_called_once()
                        game.getGuiHandler.return_value.showSelection.assert_not_called()
                        if mode == "scenario":
                            loader.startGameWithPlayer.assert_called_once_with(game, "test", class_id, race_id)
                            loader.startRandomGameWithPlayer.assert_not_called()
                            campaign_start.assert_not_called()
                        elif mode == "random":
                            loader.startRandomGameWithPlayer.assert_called_once_with(game, class_id, race_id)
                            loader.startGameWithPlayer.assert_not_called()
                            campaign_start.assert_not_called()
                        else:
                            campaign_start.assert_called_once_with(game, "fallOfNouraajd", class_id, race_id)
                            loader.startGameWithPlayer.assert_not_called()
                            loader.startRandomGameWithPlayer.assert_not_called()

    def testCancelAndInvalidIdentityNeverStartAnAdventureAndReturnToTheModeChooser(self):
        for selection in (("", ""), ("missing", "humanRace"), ("Warrior", "missing")):
            game = self.session()
            game.getGuiHandler.return_value.showCharacterCreationOptions.return_value = selection
            loader = Mock()
            with (
                patch.dict(sys.modules, _game=types.SimpleNamespace(CGameLoader=loader)),
                patch.object(ui, "choose", side_effect=["random", ""]) as choose,
                patch.object(ui, "characterChoices", return_value=self.choices()),
            ):
                self.assertFalse(ui.newAdventure(game))
            self.assertEqual(["New adventure", "New adventure"], [call.args[1] for call in choose.call_args_list])
            loader.startGameWithPlayer.assert_not_called()
            loader.startRandomGameWithPlayer.assert_not_called()
            self.assertIsNone(game.getMap())

    def testLoadBypassesCharacterCreationAndPreservesTheLoadedPlayer(self):
        game = self.session()
        loaded = Mock()
        loaded.getPlayer.return_value.getPlayerClassId.return_value = "Sorcerer"
        loaded.getPlayer.return_value.getRaceId.return_value = "highlanderRace"
        loader = Mock()
        loader.loadSavedGame.side_effect = lambda *args: setattr(game.getMap, "return_value", loaded)
        with (
            patch.dict(sys.modules, _game=types.SimpleNamespace(CGameLoader=loader)),
            patch.object(ui, "savedGames", return_value=[{"id": "fixture", "detail": "Existing Sorcerer"}]),
            patch.object(ui, "choose", side_effect=["load", "fixture"]),
            patch.object(ui, "chooseCharacter") as choose_character,
        ):
            self.assertTrue(ui.mainMenu(game))
        loader.loadSavedGame.assert_called_once_with(game, "fixture")
        choose_character.assert_not_called()
        game.getGuiHandler.return_value.showCharacterCreationOptions.assert_not_called()
        self.assertIs(loaded, game.getMap())
        self.assertEqual("Sorcerer", game.getMap().getPlayer().getPlayerClassId())
        self.assertEqual("highlanderRace", game.getMap().getPlayer().getRaceId())


class CharacterPreviewRuntimeTest(unittest.TestCase):
    def testEveryAuthoredPreviewMatchesTheActualPlayerWithTheSameClassAndRace(self):
        import test as harness

        if not any(
            list(path.glob("_game*.pyd")) + list(path.glob("_game*.so"))
            for path in (harness.build_dir, *harness.extension_dirs)
        ):
            self.skipTest("Current compiled _game required for twenty-composition preview acceptance")
        engine = harness.load_game_module()
        game = engine.CGameLoader.loadGame()
        self.addCleanup(game.getContext().shutdown)
        classes, races = ui.characterChoices(game)
        self.assertEqual(set(CLASSES), {row["id"] for row in classes})
        self.assertEqual(set(RACES), {row["id"] for row in races})
        for row in classes:
            self.assertEqual(set(RACES), set(row["previews"]))
            for race in races:
                with self.subTest(class_id=row["id"], race_id=race["id"]):
                    engine.CGameLoader.startGameWithPlayer(game, "test", row["id"], race["id"])
                    player = game.getMap().getPlayer()
                    self.assertEqual(row["id"], player.getPlayerClassId())
                    self.assertEqual(race["id"], player.getRaceId())
                    preview = row["previews"][race["id"]]
                    self.assertIn(ui.statSummary(player.getStats()), preview)
                    self.assertIn(f"Health {player.getHpMax()}", preview)
                    self.assertIn(f"Mana {player.getManaMax()}", preview)
                    for action in player.getEffectiveInteractions():
                        self.assertIn(action.getStringProperty("label") or action.getTypeId(), preview)
                    for item in player.getEquipped().values():
                        if item is not None:
                            self.assertIn(item.getStringProperty("label") or item.getTypeId(), preview)


def exerciseCharacterChooser(test_case):
    """One GUI session covers all twenty choices at three resolutions through real SDL input."""
    import test as harness

    engine, game, game_map, player = harness.create_xvfb_gameplay_session(test_case)
    classes, races = ui.characterChoices(game)
    test_case.assertEqual(20, len(classes) * len(races))
    initial_turn = game_map.getTurn()
    initial_coords = harness.coords_tuple(player.getCoords())

    def press(key, scancode=0):
        harness.push_sdl_key_event(key, scancode, harness.SDL_KEYDOWN)
        harness.push_sdl_key_event(key, scancode, harness.SDL_KEYUP)
        harness.pump_event_loop(3)

    def show():
        return game.getGuiHandler().showCharacterCreationOptions(json.dumps(classes), json.dumps(races))

    for width, height in ((800, 600), (1280, 720), (1920, 1080)):
        actual_size = harness.push_sdl_window_size_changed_event(width, height)
        test_case.assertEqual((width, height), actual_size)
        harness.pump_event_loop(3)
        for class_index, row in enumerate(classes):
            for race_index, race in enumerate(races):
                with test_case.subTest(size=(width, height), class_id=row["id"], race_id=race["id"]):

                    def inspect(panel):
                        press(1073741898, 74)  # Home selects the first class, irrespective of previous preview.
                        for _ in range(class_index):
                            press(harness.SDLK_DOWN, 81)
                        press(1073741903, 79)  # Right focuses the race column/page.
                        press(1073741898, 74)
                        for _ in range(race_index):
                            press(harness.SDLK_DOWN, 81)
                        press(harness.SDLK_TAB, 43)  # Focus preview, including the compact page at 800x600.
                        text = panel.getDetailText()
                        test_case.assertIn(row["previews"][race["id"]], text)
                        test_case.assertIn(row["label"], text)
                        test_case.assertIn(race["label"], text)
                        test_case.assertFalse(panel.hasChoice(), "Preview changes must await explicit confirmation")
                        harness.assert_rect_on_screen(
                            test_case, "character chooser", harness.resolved_rect(panel), width, height
                        )
                        if (class_index, race_index) in ((0, 0), (len(classes) - 1, len(races) - 1)):
                            harness.assert_screenshot_has_rendered_pixels(
                                test_case, game, f"character-matrix-{width}-{height}-{row['id']}-{race['id']}"
                            )
                        return text

                    selected, _ = harness.run_blocking_panel_inspection(
                        test_case,
                        engine,
                        game,
                        "CGameCampaignBrowserPanel",
                        show,
                        inspect,
                        lambda panel: press(harness.SDLK_RETURN, 40),
                    )
                    test_case.assertEqual((row["id"], race["id"]), tuple(selected))
                    test_case.assertFalse(harness.gui_contains_class(game, "CGameCampaignBrowserPanel"))
        cancelled, _ = harness.run_blocking_panel_inspection(
            test_case,
            engine,
            game,
            "CGameCampaignBrowserPanel",
            show,
            lambda panel: panel.getDetailText(),
            lambda panel: press(27, 41),
        )
        test_case.assertEqual(("", ""), tuple(cancelled))
        test_case.assertEqual(initial_turn, game_map.getTurn())
        test_case.assertEqual(initial_coords, harness.coords_tuple(player.getCoords()))
    torn_down, _ = harness.run_blocking_panel_inspection(
        test_case,
        engine,
        game,
        "CGameCampaignBrowserPanel",
        show,
        lambda panel: panel.getDetailText(),
        lambda panel: game.getGui().removeChild(panel),
    )
    test_case.assertEqual(("", ""), tuple(torn_down))
