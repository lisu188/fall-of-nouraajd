# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis

import unittest
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from scripts import generate_screenshots
from scripts import generate_walkthrough_video


class ScreenshotDisplayIsolationTest(unittest.TestCase):
    def sdlFixture(self, accepted, driver=b"dummy"):
        ctypes = ModuleType("ctypes")
        ctypes.__path__ = []
        utility = ModuleType("ctypes.util")
        ctypes.util = utility
        ctypes.c_char_p = object()
        sdl = SimpleNamespace(SDL_GetCurrentVideoDriver=Mock(return_value=driver))

        def load(name):
            if name == accepted:
                return sdl
            raise OSError("Simulated unavailable SDL candidate")

        ctypes.CDLL = Mock(side_effect=load)
        utility.find_library = Mock(return_value=None)
        return ctypes, utility, sdl

    def testCaptureSdlResolvesRegisteredWindowsDependencyWhenAppLocalCopyIsAbsent(self):
        build_dir = Path("selected-build")
        ctypes, utility, sdl = self.sdlFixture("SDL2.dll")
        with (
            patch.object(generate_screenshots, "_selected_build_dir", return_value=build_dir),
            patch.object(generate_screenshots.os, "name", "nt"),
            patch.dict(generate_screenshots.os.environ, {"GAME_BUILD_CONFIG": "Release"}, clear=True),
            patch.dict("sys.modules", {"ctypes": ctypes, "ctypes.util": utility}),
        ):
            try:
                loaded = generate_screenshots.captureSdl()
            except RuntimeError:
                loaded = None
        self.assertIs(
            sdl, loaded, "Windows must resolve an already-loaded/registered SDL2.dll after build-local misses"
        )
        self.assertEqual(
            [str(build_dir / "Release/SDL2.dll"), str(build_dir / "SDL2.dll"), "SDL2.dll"],
            [call.args[0] for call in ctypes.CDLL.call_args_list],
        )

    def testCaptureSdlStillPrefersTheActiveBuildConfiguration(self):
        build_dir = Path("selected-build")
        expected = str(build_dir / "Release/SDL2.dll")
        ctypes, utility, sdl = self.sdlFixture(expected, b"offscreen")
        with (
            patch.object(generate_screenshots, "_selected_build_dir", return_value=build_dir),
            patch.object(generate_screenshots.os, "name", "nt"),
            patch.dict(generate_screenshots.os.environ, {"GAME_BUILD_CONFIG": "Release"}, clear=True),
            patch.dict("sys.modules", {"ctypes": ctypes, "ctypes.util": utility}),
        ):
            self.assertIs(sdl, generate_screenshots.captureSdl())
        self.assertEqual([expected], [call.args[0] for call in ctypes.CDLL.call_args_list])

    def testCaptureSdlKeepsPosixLookupOrder(self):
        build_dir = Path("selected-build")
        expected = "/existing/libSDL2.so"
        ctypes, utility, sdl = self.sdlFixture(expected)
        utility.find_library.return_value = expected
        with (
            patch.object(generate_screenshots, "_selected_build_dir", return_value=build_dir),
            patch.object(generate_screenshots.os, "name", "posix"),
            patch.dict(generate_screenshots.os.environ, {"GAME_BUILD_CONFIG": "Release"}, clear=True),
            patch.dict("sys.modules", {"ctypes": ctypes, "ctypes.util": utility}),
        ):
            self.assertIs(sdl, generate_screenshots.captureSdl())
        self.assertEqual(
            [str(build_dir / "Release/SDL2.dll"), str(build_dir / "SDL2.dll"), expected],
            [call.args[0] for call in ctypes.CDLL.call_args_list],
        )

    def testCaptureSdlStillRejectsNonisolatedVideoDrivers(self):
        build_dir = Path("selected-build")
        expected = str(build_dir / "Release/SDL2.dll")
        for driver in (b"windows", b"x11"):
            ctypes, utility, _sdl = self.sdlFixture(expected, driver)
            with (
                self.subTest(driver=driver),
                patch.object(generate_screenshots, "_selected_build_dir", return_value=build_dir),
                patch.object(generate_screenshots.os, "name", "nt"),
                patch.dict(generate_screenshots.os.environ, {"GAME_BUILD_CONFIG": "Release"}, clear=True),
                patch.dict("sys.modules", {"ctypes": ctypes, "ctypes.util": utility}),
                self.assertRaisesRegex(RuntimeError, "not isolated"),
            ):
                generate_screenshots.captureSdl()

    def testCaptureUsesTheCompilerSpecificBuild(self):
        import os

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            name = "cmake-build-clangcl20-release" if os.name == "nt" else "cmake-build-gcc15-release"
            (root / name).mkdir()
            (root / "cmake-build-release").mkdir()
            with patch.object(generate_screenshots, "REPO_ROOT", root), patch.dict(os.environ, {"GAME_BUILD_DIR": ""}):
                self.assertEqual(root / name, generate_screenshots._selected_build_dir())

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
    def mapPreviewFixture(self, failure=None):
        import ast

        events = []
        context = SimpleNamespace(shutdown=lambda: events.append("shutdown"))
        instance = SimpleNamespace(gui_loaded=False, getContext=lambda: context)

        def step(name):
            events.append(name)
            if failure == name:
                raise RuntimeError("Preview failure: " + name)

        def loadGame():
            step("loadGame")
            return instance

        def loadGui(current):
            self.assertIs(instance, current)
            step("loadGui")
            instance.gui_loaded = True

        def start(current, *args):
            self.assertIs(instance, current)
            events.append(("guiAtStart", current.gui_loaded))
            step("start")

        game = SimpleNamespace(
            CGameLoader=SimpleNamespace(
                loadGame=loadGame, loadGui=loadGui, startGameWithPlayer=start, startRandomGameWithPlayer=start
            )
        )

        class Simulation:
            def __init__(self, module, current, map_name, player):
                self.gameInstance = current
                step("construct")

            def pumpEvents(self, count):
                events.append(("pump", count))
                step("pump")

            def captureGuiScreenshot(self, path):
                events.append(("capturePath", path))
                step("capture")
                return {"bytes": 123}

        source = (generate_screenshots.REPO_ROOT / "game_simulation.py").read_text(encoding="utf-8")
        definition = next(
            node for node in ast.parse(source).body if isinstance(node, ast.ClassDef) and node.name == "GameSimulation"
        )
        start_method = next(
            node for node in definition.body if isinstance(node, ast.FunctionDef) and node.name == "startGame"
        )
        namespace = {}
        exec(
            compile(ast.Module(body=[start_method], type_ignores=[]), "actual-GameSimulation.startGame", "exec"),
            namespace,
        )
        Simulation.startGame = namespace["startGame"]
        module = ModuleType("game_simulation")
        module.GameSimulation = Simulation
        return game, module, events

    def testPosedMapPreviewInitializesBeforeGuiForAuthoredAndRandomMaps(self):
        for random_map in (False, True):
            game, module, events = self.mapPreviewFixture()
            with self.subTest(random=random_map), patch.dict("sys.modules", {"game_simulation": module}):
                path = generate_screenshots.capture_map(
                    game, Path("preview-output"), "Warrior", "candlekeep", random_map
                )
                expected = Path("preview-output") / ("map-random.png" if random_map else "map-candlekeep.png")
                self.assertEqual(expected, path)
                self.assertEqual(
                    [("guiAtStart", False)],
                    [event for event in events if isinstance(event, tuple) and event[0] == "guiAtStart"],
                )
                self.assertLess(events.index("start"), events.index("loadGui"))
                self.assertLess(events.index("loadGui"), events.index("construct"))
                self.assertEqual(
                    [("pump", 5), ("pump", 5)],
                    [event for event in events if isinstance(event, tuple) and event[0] == "pump"],
                )
                self.assertIn(("capturePath", expected), events)
                self.assertEqual(1, events.count("shutdown"))

    def testPosedMapPreviewShutsDownAfterSetupAndCaptureFailures(self):
        for failure in ("start", "loadGui", "construct", "pump", "capture"):
            game, module, events = self.mapPreviewFixture(failure)
            with self.subTest(failure=failure), patch.dict("sys.modules", {"game_simulation": module}):
                with self.assertRaisesRegex(RuntimeError, "Preview failure: " + failure):
                    generate_screenshots.capture_map(game, Path("preview-output"), "Warrior", "candlekeep")
                self.assertEqual(1, events.count("shutdown"))
                if failure != "capture":
                    self.assertNotIn("capture", events)

    def artifactCaptureFixture(self, fail_piece=""):
        import ast
        import inspect

        source = (generate_screenshots.REPO_ROOT / "res/plugins/artifact_sets.py").read_text(encoding="utf-8")
        schedule = next(
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef) and node.name == "_schedule_assembly_offer"
        )
        offers = []
        namespace = {"maybeOfferAssemblyFlow": lambda player: offers.append(player)}
        exec(
            compile(ast.Module(body=[schedule], type_ignores=[]), "actual-artifact-offer-scheduler", "exec"), namespace
        )

        class Game:
            def __init__(self):
                self.queue = []

            def runUiFlowLater(self, callback):
                self.queue.append(callback)

            def createObject(self, item_id):
                return SimpleNamespace(item_id=item_id)

            def getSlotConfiguration(self):
                return SimpleNamespace(getFittingSlots=lambda item: {item.item_id})

        instance = Game()
        original_post = Game.runUiFlowLater
        old_item = SimpleNamespace(item_id="originalEquipment")
        inventory = {}
        equipped = {"originalSlot": old_item}
        created = []

        class Player:
            def isPlayer(self):
                return True

            def getGame(self):
                return instance

            def getEquipped(self):
                return dict(equipped)

            def addItem(self, item):
                inventory[item.item_id] = item
                created.append(item)

            def equipItem(self, slot, item):
                old = equipped.pop(slot, None)
                if old:
                    inventory[old.item_id] = old
                if item:
                    namespace["_schedule_assembly_offer"](SimpleNamespace(getCause=lambda: self))
                    if item.item_id == fail_piece:
                        raise RuntimeError("Posed equip failure")
                    equipped[slot] = item
                    inventory.pop(item.item_id)

        player = Player()
        pumps = []

        def pump(count):
            pumps.append((count, Game.runUiFlowLater is original_post, len(instance.queue)))
            while instance.queue:
                instance.queue.pop(0)()

        sim = SimpleNamespace(gameInstance=instance, player=player, pumpEvents=pump)
        module = SimpleNamespace(CGame=Game)
        definition = {"pieces": ["pieceA", "pieceB", "pieceC", "pieceD"]}
        function = ast.parse(inspect.getsource(generate_screenshots.captureAcceptanceStates)).body[0]
        body = next(node.body for node in function.body if isinstance(node, ast.Try))
        start = next(
            index
            for index, node in enumerate(body)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "definition" for target in node.targets)
        )
        stop = next(
            index
            for index in range(start + 1, len(body))
            if isinstance(body[index], ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "before" for target in body[index].targets)
        )
        held_setup = compile(
            ast.Module(body=body[start + 1 : stop], type_ignores=[]), "actual-artifact-capture-setup", "exec"
        )

        def seed():
            exec(held_setup, {"game": module, "player": player, "sim": sim, "definition": definition, "patch": patch})

        return seed, instance, player, definition, old_item, inventory, equipped, created, offers, pumps, original_post

    def testPosedArtifactEquipmentCannotPostCompetingNativeOffers(self):
        seed, instance, player, definition, old, inventory, equipped, created, offers, pumps, original = (
            self.artifactCaptureFixture()
        )
        seed()
        self.assertEqual([], offers, "Posed set seeding must not open automatic native assembly modals")
        self.assertEqual([], instance.queue)
        self.assertEqual([(3, True, 0)], pumps, "Restore real posting before the unchanged event pumps")
        self.assertEqual(set(definition["pieces"]), set(equipped))
        self.assertEqual(created, [equipped[item_id] for item_id in definition["pieces"]])
        self.assertEqual({old.item_id: old}, inventory)
        self.assertIs(original, type(instance).runUiFlowLater)
        instance.runUiFlowLater(lambda: offers.append(player))
        self.assertEqual(1, len(instance.queue), "Deliberate/native offers must work after fixture setup")
        instance.queue.pop()()
        self.assertEqual([player], offers)

    def testPosedArtifactOfferSuppressionRestoresPostingAfterEquipFailure(self):
        seed, instance, player, _definition, _old, _inventory, _equipped, _created, offers, pumps, original = (
            self.artifactCaptureFixture(fail_piece="pieceB")
        )
        with self.assertRaisesRegex(RuntimeError, "Posed equip failure"):
            seed()
        self.assertIs(original, type(instance).runUiFlowLater)
        self.assertEqual([], instance.queue, "Failed posed setup must not orphan automatic UI work")
        self.assertEqual([], offers)
        self.assertEqual([], pumps)
        instance.runUiFlowLater(lambda: offers.append(player))
        self.assertEqual(1, len(instance.queue))
        instance.queue.pop()()
        self.assertEqual([player], offers)

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

    def testPanelPreparationDoesNotEnterAStoryReaderBeforeTheFirstCapture(self):
        items = []
        quests = []
        story_entries = []
        origin = (110, 111, 0)
        position = [origin]

        def enterStory(x, y, z):
            position[0] = (x, y, z)
            story_entries.append(position[0])
            raise RuntimeError("A native campaign reader now needs dismissal")

        start_event = SimpleNamespace(
            getTypeId=lambda: "StartEvent",
            getCoords=lambda: SimpleNamespace(x=109, y=110, z=0),
        )
        player = SimpleNamespace(
            addItem=items.append,
            addQuest=quests.append,
            moveTo=enterStory,
            checkQuests=Mock(),
        )
        sim = SimpleNamespace(
            player=player,
            gameInstance=SimpleNamespace(createObject=lambda item: item),
            gameMap=SimpleNamespace(getObjects=lambda: [start_event]),
            pumpEvents=Mock(),
        )

        generate_screenshots._prepare_player_for_panels(sim)

        self.assertEqual((origin, []), (position[0], story_entries))
        self.assertEqual(["Sword", "Scroll", "LeatherArmor"], items)
        self.assertEqual(["mainQuest"], quests)

    def testPanelPreparationKeepsRepresentativeQuestWhenAnOptionalItemIsUnavailable(self):
        items = []
        quests = []

        def createItem(item):
            if item == "Scroll":
                raise ValueError("Optional screenshot item unavailable")
            return item

        sim = SimpleNamespace(
            player=SimpleNamespace(addItem=items.append, addQuest=quests.append),
            gameInstance=SimpleNamespace(createObject=createItem),
        )

        generate_screenshots._prepare_player_for_panels(sim)

        self.assertEqual(["Sword", "LeatherArmor"], items)
        self.assertEqual(["mainQuest"], quests)

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
