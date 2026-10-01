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
import textwrap
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = """
import faulthandler
faulthandler.enable(all_threads=True)

def mark(stage):
    print('console-ui:' + stage, flush=True)

mark('engine-import')
import ctypes
import os
from pathlib import Path
import unittest
import test as harness
try:
    import play
except ModuleNotFoundError as error:
    if error.name == '_game':
        raise SystemExit(77)
    raise
import _game as game
game.set_logger_sink('disabled')
check = unittest.TestCase()
mark('game-load')
g = game.CGameLoader.loadGame()
mark('gui-load')
game.CGameLoader.loadGui(g)
mark('player-start')
game.CGameLoader.startGameWithPlayer(g, 'test', 'Warrior')
harness.pump_event_loop(5)
harness.drain_sdl_events()
gui = g.getGui()
world = g.getMap()
player = world.getPlayer()
console = harness.collect_gui_children(gui, 'CConsoleGraphicsObject')[0]
mark('gui-ready')

def press(key):
    harness.push_sdl_key_event(key, 0)
    harness.push_sdl_key_event(key, 0, harness.SDL_KEYUP)
    harness.pump_event_loop(2)

def typeText(value):
    expected = (console.consoleState + value)[:1024]
    class TextInput(ctypes.Structure):
        _fields_ = [('type', ctypes.c_uint32), ('timestamp', ctypes.c_uint32),
                    ('windowID', ctypes.c_uint32), ('text', ctypes.c_char * 32)]
    class Event(ctypes.Union):
        _fields_ = [('text', TextInput), ('padding', ctypes.c_uint8 * 56)]
    sdl = harness.load_sdl_library()
    sdl.SDL_PushEvent.argtypes = [ctypes.POINTER(Event)]
    sdl.SDL_PushEvent.restype = ctypes.c_int
    sdl.SDL_HasEvent.argtypes = [ctypes.c_uint32]
    sdl.SDL_HasEvent.restype = ctypes.c_int
    sdl.SDL_IsTextInputActive.restype = ctypes.c_int
    for start in range(0, len(value), 31):
        event = Event()
        event.text.type = 0x303
        event.text.text = value[start:start + 31].encode('ascii')
        check.assertEqual(1, sdl.SDL_PushEvent(ctypes.byref(event)))
    ready = harness.pump_event_loop_until(
        lambda: console.consoleState == expected and not sdl.SDL_HasEvent(0x303), timeout=2.0
    )
    check.assertTrue(
        ready,
        f'console={console.consoleState!r}; expected={expected!r}; '
        f'modal={console.getBoolProperty("modal")}; textActive={sdl.SDL_IsTextInputActive()}',
    )

def snapshot():
    coords = player.getCoords()
    return (coords.x, coords.y, coords.z, world.getTurn())

"""


class ConsoleUiInteractionTest(unittest.TestCase):
    def runChild(self, code, enabled=True):
        command = [sys.executable, "-c"]
        if os.name == "posix":
            for tool in ("xvfb-run", "xauth"):
                if shutil.which(tool) is None:
                    self.skipTest(f"{tool} is required for isolated console GUI tests.")
            command = ["xvfb-run", "-a", "--server-args=-screen 0 1920x1080x24", *command]
        environment = os.environ.copy()
        if environment.get("GAME_BUILD_DIR"):
            environment["GAME_BUILD_DIR"] = str((ROOT / environment["GAME_BUILD_DIR"]).resolve())
        with tempfile.TemporaryDirectory(prefix="nouraajd-console-ui-") as temporary:
            environment.update(
                SDL_VIDEODRIVER="x11" if os.name == "posix" else "dummy",
                SDL_AUDIODRIVER="dummy",
                SDL_RENDER_DRIVER="software",
                LIBGL_ALWAYS_SOFTWARE="1",
                GAME_ENABLE_PYTHON_CONSOLE="1" if enabled else "0",
                GAME_UI_PREFERENCES_PATH=str(Path(temporary) / "preferences.json"),
                GAME_TEST_OUTPUT_DIR=str(Path(temporary) / "test-output"),
            )
            source = BOOTSTRAP + "\ntry:\n" + textwrap.indent(textwrap.dedent(code), "    ")
            source += (
                "\n    mark('assertions-complete')\nfinally:\n"
                "    mark('shutdown-begin')\n    g.getContext().shutdown()\n    mark('shutdown-complete')\n"
            )
            process = subprocess.Popen(
                [*command, source],
                cwd=ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=(os.name == "posix"),
            )
            try:
                stdout, stderr = process.communicate(timeout=90 if os.environ.get("GAME_COVERAGE_RUN") == "1" else 30)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
                stdout, stderr = process.communicate()
                self.fail("Console UI child timed out.\n" + stdout + stderr)
        if process.returncode == 77:
            self.skipTest("The compiled _game module is unavailable.")
        self.assertEqual(0, process.returncode, stdout + stderr)

    def testTimeoutTerminatesTheIsolatedProcessAndRetainsDiagnostics(self):
        for platform in ("posix", "nt"):
            with self.subTest(platform=platform):
                process = Mock(pid=4312)
                process.communicate.side_effect = [
                    subprocess.TimeoutExpired("console child", 30),
                    ("partial standard output", "partial standard error"),
                ]
                isolated_os = SimpleNamespace(name=platform, environ={}, killpg=Mock())
                with (
                    patch(__name__ + ".os", isolated_os),
                    patch(__name__ + ".signal", SimpleNamespace(SIGKILL=9)),
                    patch(__name__ + ".shutil.which", return_value="available"),
                    patch(__name__ + ".subprocess.Popen", return_value=process) as launch,
                ):
                    with self.assertRaisesRegex(AssertionError, "timed out") as failure:
                        self.runChild("")
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

    def testChildEnablesFaultDiagnosticsBeforeEngineImportsAndMarksShutdown(self):
        import ast

        process = Mock(returncode=0)
        process.communicate.return_value = ("", "")
        with (
            patch(__name__ + ".os", SimpleNamespace(name="nt", environ={})),
            patch(__name__ + ".subprocess.Popen", return_value=process) as launch,
        ):
            self.runChild("pass")
        tree = ast.parse(launch.call_args.args[0][-1])
        enabled = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "faulthandler"
            and node.func.attr == "enable"
        ]
        self.assertEqual(1, len(enabled))
        self.assertEqual({"all_threads": True}, {keyword.arg: keyword.value.value for keyword in enabled[0].keywords})
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(alias.name in {"test", "play", "_game"} for alias in node.names):
                self.assertLess(enabled[0].lineno, node.lineno)
        marker = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "mark")
        namespace = {"print": Mock()}
        exec(compile(ast.Module(body=[marker], type_ignores=[]), "<console-stage>", "exec"), namespace)
        namespace["mark"]("probe")
        namespace["print"].assert_called_once_with("console-ui:probe", flush=True)
        child = tree.body[-1]
        self.assertIsInstance(child, ast.Try)
        self.assertEqual("assertions-complete", child.body[-1].value.args[0].value)
        self.assertEqual("shutdown-begin", child.finalbody[0].value.args[0].value)
        self.assertEqual("shutdown", child.finalbody[1].value.func.attr)
        self.assertEqual("shutdown-complete", child.finalbody[2].value.args[0].value)

    def testFatalChildExitPreservesStagesAndFaultHandlerOutput(self):
        process = Mock(returncode=3221225477)
        stdout = "console-ui:input-bounds\n"
        stderr = "Windows fatal exception: access violation\nCurrent thread: typeText\n"
        process.communicate.return_value = (stdout, stderr)
        with (
            patch(__name__ + ".os", SimpleNamespace(name="nt", environ={})),
            patch(__name__ + ".subprocess.Popen", return_value=process),
        ):
            with self.assertRaises(AssertionError) as failure:
                self.runChild("pass")
        self.assertIn("3221225477", str(failure.exception))
        self.assertIn(stdout, str(failure.exception))
        self.assertIn(stderr, str(failure.exception))

    def testChildResolvesRelativeBuildDirectoryAgainstSourceRoot(self):
        for build_dir in ("cmake-build-release", "alternate-build/Debug tree", str(ROOT / "absolute-build")):
            with self.subTest(build_dir=build_dir):
                process = Mock(returncode=0)
                process.communicate.return_value = ("", "")
                environment = {"GAME_BUILD_DIR": build_dir, "GAME_BUILD_CONFIG": "Release"}
                with (
                    patch(__name__ + ".os", SimpleNamespace(name="nt", environ=environment)),
                    patch(__name__ + ".subprocess.Popen", return_value=process) as launch,
                ):
                    self.runChild("")
                child_environment = launch.call_args.kwargs["env"]
                self.assertEqual(str((ROOT / build_dir).resolve()), child_environment["GAME_BUILD_DIR"])
                self.assertTrue(Path(child_environment["GAME_BUILD_DIR"]).is_absolute())
                self.assertEqual("Release", child_environment["GAME_BUILD_CONFIG"])
                self.assertEqual(ROOT, launch.call_args.kwargs["cwd"])
                self.assertEqual(
                    build_dir, environment["GAME_BUILD_DIR"], "The parent environment must remain unchanged."
                )

    def testDisabledConsoleDoesNotOpenOrConsumeWorldMovement(self):
        self.runChild(
            """
            before = snapshot()
            press(harness.SDLK_F12)
            check.assertFalse(console.getBoolProperty('modal'))
            check.assertEqual(before, snapshot())
            target, key, scancode = harness.find_adjacent_walkable_direction(world, player.getCoords())
            harness.assert_player_moves_to_key_target(check, world, player, target, key, scancode)
            """,
            enabled=False,
        )

    def testEnabledConsoleEditsExecutesAndRestoresWorldFocus(self):
        self.runChild("""
            from PIL import Image
            before = snapshot()
            path = Path(os.environ['GAME_TEST_OUTPUT_DIR']) / 'closed.png'
            closed, width, height = harness.capture_sdl_screenshot(path, gui)
            press(harness.SDLK_F12)
            check.assertTrue(console.getBoolProperty('modal'))
            check.assertGreater(
                console.getNumericProperty('priority'),
                max(child.getNumericProperty('priority') for child in gui.getChildren()
                    if not harness.same_gui_object(child, console)),
                'the modal console must own input above every exploration HUD region',
            )
            path = path.with_name('opened.png')
            opened, opened_width, opened_height = harness.capture_sdl_screenshot(path, gui)
            check.assertEqual((width, height), (opened_width, opened_height))
            check.assertTrue(path.is_file())
            check.assertGreater(path.stat().st_size, 0)
            with Image.open(path) as image:
                check.assertEqual('PNG', image.format)
                check.assertEqual((width, height), image.size)
            drawer = (0, height * 2 // 3, width, height // 3)
            check.assertGreater(harness.pixel_diff_bounds(closed, opened, width, drawer)[1], 0)
            for key in (ord('i'), ord('j'), ord('c'), ord(' '), 1073741903, harness.SDLK_TAB):
                press(key)
                check.assertEqual(before, snapshot())
                check.assertTrue(console.getBoolProperty('modal'))
                for panel_class in ('CGameInventoryPanel', 'CGameQuestPanel', 'CGameCharacterPanel'):
                    check.assertFalse(harness.gui_contains_class(g, panel_class), panel_class)
            press(harness.SDLK_RETURN)
            check.assertTrue(console.getBoolProperty('modal'), 'empty Enter must not dismiss input')
            command = "game.getMap().getPlayer().setNumericProperty('consoleProbe', 9)"
            typeText(command + 'x')
            press(harness.SDLK_BACKSPACE)
            check.assertEqual(command, console.consoleState)
            press(harness.SDLK_RETURN)
            check.assertFalse(console.getBoolProperty('modal'))
            check.assertEqual(9, player.getNumericProperty('consoleProbe'))
            check.assertEqual('', console.consoleState)
            check.assertEqual(before, snapshot(), 'executing this diagnostic must not advance the world')
            press(harness.SDLK_F12)
            press(harness.SDLK_UP)
            check.assertEqual(command, console.consoleState)
            press(27)
            target, key, scancode = harness.find_adjacent_walkable_direction(world, player.getCoords())
            harness.assert_player_moves_to_key_target(check, world, player, target, key, scancode)
            """)

    def testHistoryNavigationInputBoundsAndCancellationPreserveState(self):
        self.runChild("""
            before = snapshot()
            # The history boundary needs many inputs, but no repeated world-map rasterization.
            mark('hud-detach')
            for child in list(gui.getChildren()):
                if not harness.same_gui_object(child, console):
                    gui.removeChild(child)
            mark('history-navigation')
            for entry in ('first', 'second', 'third'):
                press(harness.SDLK_F12)
                console.consoleState = entry
                press(27)
            press(harness.SDLK_F12)
            press(harness.SDLK_UP)
            check.assertEqual('third', console.consoleState)
            press(harness.SDLK_UP)
            check.assertEqual('second', console.consoleState)
            press(harness.SDLK_DOWN)
            check.assertEqual('third', console.consoleState)
            press(harness.SDLK_DOWN)
            check.assertEqual('', console.consoleState)
            press(harness.SDLK_BACKSPACE)
            check.assertEqual('', console.consoleState)
            mark('input-bounds')
            console.consoleState = 'x' * 1010
            typeText('y' * 31)
            check.assertEqual('x' * 1010 + 'y' * 14, console.consoleState)
            typeText('ignored')
            check.assertEqual(1024, len(console.consoleState))
            console.consoleState = 'z' * 1100
            check.assertEqual('z' * 1024, console.consoleState)
            press(27)
            mark('history-cap')
            for index in range(70):
                press(harness.SDLK_F12)
                console.consoleState = f'command-{index}'
                press(27)
            press(harness.SDLK_F12)
            for index in reversed(range(6, 70)):
                press(harness.SDLK_UP)
                check.assertEqual(f'command-{index}', console.consoleState)
            press(harness.SDLK_UP)
            check.assertEqual('command-69', console.consoleState, 'history must retain exactly the latest 64 entries')
            mark('cancellation')
            command = "game.getMap().getPlayer().setNumericProperty('cancelledProbe', 1)"
            console.consoleState = command
            press(27)
            check.assertFalse(console.getBoolProperty('modal'))
            check.assertEqual('', console.consoleState)
            check.assertEqual(0, player.getNumericProperty('cancelledProbe'))
            press(harness.SDLK_F12)
            press(harness.SDLK_DOWN)
            press(harness.SDLK_UP)
            check.assertEqual(command, console.consoleState)
            press(harness.SDLK_F12)
            check.assertFalse(console.getBoolProperty('modal'))
            check.assertEqual(before, snapshot())
            """)


if __name__ == "__main__":
    unittest.main()
