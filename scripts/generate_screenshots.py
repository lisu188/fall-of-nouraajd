#!/usr/bin/env python3

# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
"""Regenerate the project's coverage screenshot set.

``AGENTS.md`` requires that, after every major UI change, the screenshot set is
regenerated and that it covers, at minimum:

* at least one screenshot showing each type of panel declared in
    ``res/config/panels.json``; and
* at least one screenshot from each map directory under ``res/maps/`` plus one
    from a randomly generated map.

This script drives a real (GUI) headless game session -- the same
:class:`game_simulation.GameSimulation` driver and SDL ``read_pixels`` readback
used by the screenshot tests -- to produce that set:

* ``panel-<resourceId>.png`` for every panel in ``res/config/panels.json``,
    including the ``creatureView`` and ``statsView`` views (which also appear
    nested inside ``fightPanel``). Each panel is seeded with representative
    content so the frame is meaningful rather than empty.
* ``map-<name>.png`` for every map directory under ``res/maps/``.
* ``map-random.png`` for a freshly generated random map.
* ``frontend-<state>.png`` for the real main menu, character creation, settings,
    disabled and selected choices, overflowing content, save naming, confirmations,
    loading, errors, defeat, chapter outcomes and campaign completion.
* Service, ability and expanded-map states use disposable native fixtures. Crafting
    results and defeat acknowledgements follow actual resolved engine operations;
    all other previews cancel before committing their displayed action.

Requirements: the ``_game`` module must be built (see the project README) and
``pillow`` installed (``pip install -r requirements-dev.txt``). A real SDL
renderer is needed, so on Linux the script re-executes itself under
``xvfb-run`` automatically; you can also run it explicitly::

    xvfb-run -a --server-args="-screen 0 1920x1080x24" \\
        python3 scripts/generate_screenshots.py

Usage::

    python3 scripts/generate_screenshots.py --output-dir screenshots
    python3 scripts/generate_screenshots.py --panels-only
    python3 scripts/generate_screenshots.py --acceptance-only
    python3 scripts/generate_screenshots.py --maps nouraajd ritual --no-random
"""

import argparse
import os
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REEXEC_SENTINEL = "NOURAAJD_SCREENSHOTS_REEXEC"
PANELS_MAP = "nouraajd"  # content-rich campaign map used as the backdrop for panels
NATIVE_GUI_HELPERS = {}


# ---------------------------------------------------------------------------
# Environment bootstrap (mirrors scripts/generate_walkthrough_video.py)
# ---------------------------------------------------------------------------
def _reexec_under_xvfb_if_needed():
    """Capture only through an isolated display; never create desktop windows."""
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["SDL_RENDER_DRIVER"] = "software"
    os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
    if os.name != "posix":
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        return
    if os.environ.get("SDL_VIDEODRIVER") in ("dummy", "offscreen"):
        return
    if os.environ.get(REEXEC_SENTINEL) == "1":
        return
    import shutil

    if shutil.which("xvfb-run") is None or shutil.which("xauth") is None:
        raise RuntimeError("Screenshot capture requires xvfb-run and xauth, or SDL dummy/offscreen rendering.")

    env = dict(os.environ)
    env[REEXEC_SENTINEL] = "1"
    env["SDL_VIDEODRIVER"] = "x11"
    env.setdefault("SDL_AUDIODRIVER", "dummy")
    env.setdefault("SDL_RENDER_DRIVER", "software")
    env.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    os.execvpe(
        "xvfb-run",
        [
            "xvfb-run",
            "-a",
            "--server-args=-screen 0 1920x1080x24",
            sys.executable,
            str(Path(__file__).resolve()),
            *sys.argv[1:],
        ],
        env,
    )


def _bootstrap_paths():
    """Replicate ``play.py``'s path setup so ``import game`` finds ``_game``."""
    build_dir = REPO_ROOT / (os.environ.get("GAME_BUILD_DIR") or "cmake-build-release")
    if not build_dir.exists():
        build_dir = REPO_ROOT / "cmake-build-debug"

    def insert(entry: Path):
        if entry.exists() and str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

    # game_simulation lives at the repository root.
    insert(REPO_ROOT)
    if build_dir.exists():
        insert(build_dir)
        build_config = os.environ.get("GAME_BUILD_CONFIG")
        configs = [build_config] if build_config else ["Release", "Debug", "RelWithDebInfo", "MinSizeRel"]
        for config in configs:
            insert(build_dir / config)
        insert(REPO_ROOT / "res")
        insert(REPO_ROOT / "res" / "plugins")
        os.chdir(build_dir)
    else:
        insert(REPO_ROOT / "res")
        os.chdir(REPO_ROOT / "res")


def _suppress_blocking_popups(game):
    """Turn modal popups into non-blocking no-ops for headless capture.

    Starting a map and opening panels can fire modal message/question panels
    that block the SDL event loop waiting for a keypress. In an automated
    capture there is no interactive keyboard, so we replace those handlers with
    auto-dismissing stubs (questions cancel), exactly as the GUI tests and
    the walkthrough recorder do. The panels we open explicitly still render
    normally.
    """
    handler = game.CGuiHandler
    for name in (
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
    ):
        NATIVE_GUI_HELPERS[name] = getattr(handler, name)
    handler.showMessage = lambda self, message: None
    handler.showInfo = lambda self, message, centered=False: None
    handler.showQuestion = lambda self, message: False
    handler.showSelection = lambda self, *args, **kwargs: ""
    handler.showLoot = lambda self, *args, **kwargs: None
    handler.showTrade = lambda self, *args, **kwargs: None
    handler.showDialog = lambda self, *args, **kwargs: None
    handler.showCampaignSelection = lambda self, *args, **kwargs: ""
    handler.showCampaignScreen = lambda self, *args, **kwargs: None
    handler.showCampaignArtworkScreen = lambda self, *args, **kwargs: None
    handler.showChoice = lambda self, *args, **kwargs: ""
    handler.showConfirm = lambda self, *args, **kwargs: False
    handler.showCharacterCreationOptions = lambda self, *args, **kwargs: ("", "")
    handler.showCharacterCreation = lambda self, *args, **kwargs: ("", "")
    handler.showTextInput = lambda self, *args, **kwargs: ""
    handler.showLoading = lambda self, *args, **kwargs: None
    handler.hideLoading = lambda self, *args, **kwargs: None
    handler.showPauseMenu = lambda self, *args, **kwargs: None
    handler.showSaveMenu = lambda self, *args, **kwargs: None


def _load_game_module():
    import importlib

    try:
        return importlib.import_module("game")
    except Exception as exc:  # noqa: BLE001 - surface a clear, actionable message
        raise SystemExit(
            "Failed to import the game engine ('_game').\n"
            f"  underlying error: {exc!r}\n"
            "Build it first, e.g.:\n"
            "  ./configure.sh\n"
            "  cmake --build cmake-build-release --target _game -j$(nproc)\n"
        )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
def discover_maps():
    """Return the sorted names of every map directory under ``res/maps/``."""
    maps_dir = REPO_ROOT / "res" / "maps"
    return sorted(entry.name for entry in maps_dir.iterdir() if (entry / "map.json").is_file())


def discover_panels():
    """Return the panel resource ids declared in ``res/config/panels.json``."""
    import json

    panels = json.loads((REPO_ROOT / "res" / "config" / "panels.json").read_text(encoding="utf-8"))
    return sorted(panels)


def verifyScreenshot(path):
    from PIL import Image

    if path.suffix.lower() != ".png" or not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Missing or invalid screenshot artifact: {path}")
    with Image.open(path) as screenshot:
        if screenshot.format != "PNG" or screenshot.width <= 0 or screenshot.height <= 0:
            raise ValueError(f"Invalid PNG dimensions: {path}")
        screenshot.verify()


def refreshScreenshotAliases(output_dir, written):
    """Keep the README's existing image links on the freshly captured frames."""
    import shutil

    aliases = {
        "combat.png": ("management-fightPanel-selected.png", "panel-fightPanel.png"),
        "inventory.png": ("management-inventoryPanel-selected.png", "panel-inventoryPanel.png"),
        "quest-log.png": ("management-questPanel-selected.png", "panel-questPanel.png"),
        "nouraajd-exploration.png": ("map-nouraajd.png",),
    }
    captured = {path.name for path in written}
    refreshed = []
    for alias, sources in aliases.items():
        source = next((name for name in sources if name in captured), None)
        if source is not None:
            path = output_dir / alias
            shutil.copyfile(output_dir / source, path)
            refreshed.append(path)
    return refreshed


def captureSdl():
    """Resolve the active build's SDL library and verify the isolated display."""
    import ctypes
    import ctypes.util

    build_dir = REPO_ROOT / (os.environ.get("GAME_BUILD_DIR") or "cmake-build-release")
    config = os.environ.get("GAME_BUILD_CONFIG", "Release")
    candidates = [build_dir / config / "SDL2.dll", build_dir / "SDL2.dll"]
    candidates += [ctypes.util.find_library("SDL2"), "libSDL2-2.0.so.0", "libSDL2.so"]
    sdl = None
    for candidate in candidates:
        if candidate:
            try:
                sdl = ctypes.CDLL(str(candidate))
                break
            except OSError:
                pass
    if sdl is None:
        raise RuntimeError("Cannot load SDL2 to resize the isolated capture display.")
    sdl.SDL_GetCurrentVideoDriver.restype = ctypes.c_char_p
    driver = sdl.SDL_GetCurrentVideoDriver()
    if driver not in (b"dummy", b"offscreen") and not (driver == b"x11" and os.environ.get(REEXEC_SENTINEL) == "1"):
        raise RuntimeError("Refusing to resize a display that is not isolated for capture.")
    return sdl


def resizeCaptureWindow(sim, width, height):
    """Resize only this process's isolated SDL display, including renderer output."""
    import ctypes

    sdl = captureSdl()
    sdl.SDL_GetWindowFromID.argtypes = [ctypes.c_uint32]
    sdl.SDL_GetWindowFromID.restype = ctypes.c_void_p
    sdl.SDL_SetWindowSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    found = False
    for window_id in range(1, 256):
        window = sdl.SDL_GetWindowFromID(window_id)
        if window:
            sdl.SDL_SetWindowSize(window, width, height)
            found = True
    if not found:
        raise RuntimeError("No isolated SDL capture window is available.")
    gui = sim.gameInstance.getGui()
    gui.setNumericProperty("width", width)
    gui.setNumericProperty("height", height)
    sim.pumpEvents(2)


def clickCaptureWidget(sim, widget, row=False):
    """Send a paired SDL click through normal GUI routing, including drag cleanup."""
    import ctypes

    class MouseButtonEvent(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_uint32),
            ("timestamp", ctypes.c_uint32),
            ("windowID", ctypes.c_uint32),
            ("which", ctypes.c_uint32),
            ("button", ctypes.c_uint8),
            ("state", ctypes.c_uint8),
            ("clicks", ctypes.c_uint8),
            ("padding1", ctypes.c_uint8),
            ("x", ctypes.c_int32),
            ("y", ctypes.c_int32),
        ]

    class Event(ctypes.Union):
        _fields_ = [("button", MouseButtonEvent), ("padding", ctypes.c_uint8 * 56)]

    x, y, width, height = widget.getResolvedRect()
    gui = sim.gameInstance.getGui()
    event = Event()
    event.button.button = 1
    event.button.clicks = 1
    event.button.x = x + width // 2
    event.button.y = y + (min(height, widget.getCellSize(gui)) // 2 if row else height // 2)
    sdl = captureSdl()
    sdl.SDL_PushEvent.argtypes = [ctypes.POINTER(Event)]
    sdl.SDL_PushEvent.restype = ctypes.c_int
    for event_type in (1025, 1026):
        event.button.type = event_type
        event.button.state = event_type == 1025
        if sdl.SDL_PushEvent(ctypes.byref(event)) != 1:
            raise RuntimeError("Could not queue the isolated capture click.")
        sim.pumpEvents(2)


def keyCapture(sim, key):
    """Route a complete key press through the GUI's modal and focus owners."""
    import ctypes

    class Keysym(ctypes.Structure):
        _fields_ = [
            ("scancode", ctypes.c_int),
            ("sym", ctypes.c_int),
            ("mod", ctypes.c_uint16),
            ("unused", ctypes.c_uint32),
        ]

    class KeyboardEvent(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_uint32),
            ("timestamp", ctypes.c_uint32),
            ("windowID", ctypes.c_uint32),
            ("state", ctypes.c_uint8),
            ("repeat", ctypes.c_uint8),
            ("padding2", ctypes.c_uint8),
            ("padding3", ctypes.c_uint8),
            ("keysym", Keysym),
        ]

    class Event(ctypes.Union):
        _fields_ = [("key", KeyboardEvent), ("padding", ctypes.c_uint8 * 56)]

    sdl = captureSdl()
    sdl.SDL_GetScancodeFromKey.argtypes = [ctypes.c_int]
    sdl.SDL_GetScancodeFromKey.restype = ctypes.c_int
    sdl.SDL_PushEvent.argtypes = [ctypes.POINTER(Event)]
    sdl.SDL_PushEvent.restype = ctypes.c_int
    event = Event()
    event.key.keysym.sym = key
    event.key.keysym.scancode = sdl.SDL_GetScancodeFromKey(key)
    for event_type in (768, 769):
        event.key.type = event_type
        event.key.state = event_type == 768
        if sdl.SDL_PushEvent(ctypes.byref(event)) != 1:
            raise RuntimeError("Could not queue the isolated capture key.")
        sim.pumpEvents(2)


def searchCaptureSelection(sim, view, label):
    import ctypes

    class TextInputEvent(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_uint32),
            ("timestamp", ctypes.c_uint32),
            ("windowID", ctypes.c_uint32),
            ("text", ctypes.c_char * 32),
        ]

    class Event(ctypes.Union):
        _fields_ = [("text", TextInputEvent), ("padding", ctypes.c_uint8 * 56)]

    before = sim.gameMap.getNumericProperty("turn")
    clickCaptureWidget(sim, view, row=True)
    keyCapture(sim, ord("/"))
    event = Event()
    event.text.type = 771
    event.text.text = label.encode("utf-8")
    sdl = captureSdl()
    sdl.SDL_PushEvent.argtypes = [ctypes.POINTER(Event)]
    sdl.SDL_PushEvent.restype = ctypes.c_int
    if sdl.SDL_PushEvent(ctypes.byref(event)) != 1:
        raise RuntimeError("Could not queue search text for capture.")
    sim.pumpEvents(2)
    keyCapture(sim, 1073741898)  # Home selects the first matching row.
    keyCapture(sim, 27)  # Escape ends search; the inspected object remains selected.
    if sim.gameMap.getNumericProperty("turn") != before:
        raise RuntimeError("Searching and inspecting advanced a game turn.")


# ---------------------------------------------------------------------------
# Panel configuration
#
# Each entry knows how to give its panel some representative content so the
# screenshot is meaningful rather than an empty frame. The nested views
# (creatureView, statsView) are drawn inside fightPanel and are handled there.
# ---------------------------------------------------------------------------
def _configure_panel(game_instance, panel_name, panel):
    """Populate ``panel`` with representative content. Best effort per panel."""
    if panel_name == "campaignPanel":
        import campaign

        manifest = campaign.list_campaigns()[0]
        chapter = manifest["scenarios"][manifest["start"]]
        panel.setStringProperty("title", chapter["title"])
        panel.setStringProperty("body", chapter["briefing"])
        panel.setStringProperty("artwork", chapter.get("artwork", ""))
        panel.setStringProperty("actionLabel", "Begin chapter")
        panel.setCloseable(False)
        for child in panel.getChildren():
            if child.getType() == "CButton":
                child.setStringProperty("text", "Begin chapter")
    elif panel_name == "infoPanel":
        import ui

        panel.setTitle("Exploration guide")
        panel.setText(ui.helpText(game_instance))
    elif panel_name == "textPanel":
        import campaign

        manifest = campaign.list_campaigns()[0]
        chapter = manifest["scenarios"][manifest["start"]]
        panel.setTitle(chapter["title"])
        panel.setText(chapter["briefing"])
    elif panel_name == "questionPanel":
        panel.setTitle("Replace this save?")
        panel.setStringProperty("question", "The selected save will be replaced by your current adventure.")
        panel.setStringProperty("confirmLabel", "Replace save")
        panel.setStringProperty("cancelLabel", "Cancel")
    elif panel_name == "fightPanel":
        enemy = game_instance.createObject("GoblinThief")
        enemy.name = "screenshotGoblin"
        enemy.setHp(enemy.getHpMax())
        panel.setEnemy(enemy)  # also drives the nested creatureView / statsView
    elif panel_name == "tradePanel":
        market = game_instance.createObject("CMarket")
        market.setItems({game_instance.createObject("Scroll"), game_instance.createObject("Sword")})
        panel.setMarket(market)
    # characterPanel, inventoryPanel and questPanel render the live player,
    # which is prepared by _prepare_player_for_panels before capture.


def _captureNativeCall(game, sim, helper_name, panel_class, arguments, path, prepare=None, open_action=None):
    """Capture a deliberately opened native modal, then cancel without triggering its action."""
    captured = {}

    def captureAndClose():
        panel = sim.gameInstance.getGui().findChild(panel_class)
        if panel is None and open_action is not None:
            captured["attempts"] = captured.get("attempts", 0) + 1
            if captured["attempts"] < 1000:
                game.event_loop.instance().invoke(captureAndClose)
                return
            captured["error"] = f"{open_action} did not open {panel_class}"
            sim.gameInstance.getContext().shutdown()
            return
        try:
            if panel is None:
                raise RuntimeError(f"Native helper {helper_name} did not open {panel_class}")
            sim.pumpEvents(2)
            if prepare:
                prepare(panel, sim.gameInstance.getGui())
                sim.pumpEvents(2)
            captured.update(sim.captureGuiScreenshot(path=path))
        except Exception as exc:
            captured["error"] = repr(exc)
        finally:
            if panel is not None:
                close = getattr(panel, "close", None)
                if callable(close):
                    close()
                else:
                    resource = {
                        "CGameCampaignBrowserPanel": "campaignBrowserPanel",
                        "CGameTextPanel": "infoPanel",
                        "CGameQuestionPanel": "questionPanel",
                        "CGameDialogPanel": "dialogPanel",
                        "CGameLootPanel": "lootPanel",
                        "CGamePanel": "selectionPanel",
                    }[panel_class]
                    sim.gameInstance.getGuiHandler().flipPanel(resource, "x")

    game.event_loop.instance().invoke(captureAndClose)
    result = (
        open_action() if open_action else NATIVE_GUI_HELPERS[helper_name](sim.gameInstance.getGuiHandler(), *arguments)
    )
    if "error" in captured or "bytes" not in captured:
        raise RuntimeError(captured.get("error", f"No capture callback ran for {helper_name}"))
    return result, captured


def _captureNativePanel(game, sim, panel_name, path):
    """Use native helpers for panels whose initialization is not exposed to Python."""
    game_instance = sim.gameInstance
    if panel_name == "campaignBrowserPanel":
        import campaign
        import json

        helper_name, panel_class = "showChoice", "CGameCampaignBrowserPanel"
        manifests = campaign.list_campaigns()
        rows = [
            {
                "id": manifest["campaignId"],
                "label": manifest["title"],
                "detail": manifest.get("description", "") + f"\n\n{campaign.chapterCount(manifest)} chapters",
                "image": manifest.get("artwork", ""),
            }
            for manifest in manifests
        ]
        arguments = ("Choose a campaign", json.dumps(rows), "Select campaign", "Back")
    elif panel_name == "dialogPanel":
        helper_name, panel_class = "showDialog", "CGameDialogPanel"
        arguments = (game_instance.createObject("questDialog"),)
    elif panel_name == "lootPanel":
        helper_name, panel_class = "showLoot", "CGameLootPanel"
        arguments = (
            game_instance.createObject("GoblinThief"),
            {game_instance.createObject("Scroll"), game_instance.createObject("Sword")},
        )
    else:
        helper_name, panel_class = "showSelection", "CGameCampaignBrowserPanel"
        choices = game_instance.createObject("CListString")
        for label in ("Accept the contract", "Decline", "Ask for more gold"):
            choices.addValue(label)
        arguments = (choices,)
    return _captureNativeCall(game, sim, helper_name, panel_class, arguments, path)[1]


def _prepare_player_for_panels(sim):
    """Give the player items and (if possible) an active quest for the panels.

    The inventory / character / quest panels render live player state, so seed a
    little inventory and trigger the map's StartEvent to activate a quest. Both
    are best effort -- a bare player still renders a valid panel.
    """
    player = sim.player
    for item_id in ("Sword", "Scroll", "LeatherArmor"):
        try:
            player.addItem(sim.gameInstance.createObject(item_id))
        except Exception:  # noqa: BLE001 - seeding inventory is best effort
            pass
    try:
        start_events = [
            obj for obj in sim.gameMap.getObjects() if obj.getTypeId() == "StartEvent" or obj.getType() == "StartEvent"
        ]
        if start_events:
            coords = start_events[0].getCoords()
            player.moveTo(coords.x, coords.y, coords.z)
            sim.pumpEvents(5)
            player.checkQuests()
            sim.pumpEvents(3)
    except Exception:  # noqa: BLE001 - activating a quest is best effort
        pass
    player.addQuest("mainQuest")


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------
def capture_panels(game, output_dir, player_class, panels):
    """Open, configure and capture each panel over the campaign map."""
    import game_simulation

    sim = game_simulation.GameSimulation.startGame(game, PANELS_MAP, player_class, load_gui=True)
    _prepare_player_for_panels(sim)
    gui_handler = sim.gameInstance.getGuiHandler()

    written = []
    for panel_name in panels:
        path = output_dir / f"panel-{panel_name}.png"
        panel = None
        try:
            if panel_name in {"campaignBrowserPanel", "dialogPanel", "lootPanel", "selectionPanel"}:
                info = _captureNativePanel(game, sim, panel_name, path)
                written.append(path)
                print(f"  [ok]   panel {panel_name}: {path.name} ({info.get('bytes', 0)} bytes)", flush=True)
                continue
            # These resources are child views, not CGamePanel subclasses; opening
            # them directly through openPanel would pass a null panel to the GUI.
            host_name = "fightPanel" if panel_name in {"creatureView", "statsView"} else panel_name
            panel = gui_handler.openPanel(host_name)
            if panel is None:
                print(f"  [skip] panel {panel_name}: openPanel returned None", flush=True)
                continue
            _configure_panel(sim.gameInstance, host_name, panel)
            sim.pumpEvents(5)
            info = sim.captureGuiScreenshot(path=path)
            written.append(path)
            print(f"  [ok]   panel {panel_name}: {path.name} ({info.get('bytes', 0)} bytes)", flush=True)
        except Exception:  # noqa: BLE001 - keep going so one panel can't abort the set
            print(f"  [fail] panel {panel_name}:\n{traceback.format_exc()}", flush=True)
        finally:
            try:
                if panel is not None:
                    panel.close()
                    sim.pumpEvents(2)
            except Exception:  # noqa: BLE001 - closing is best effort
                pass
    sim.gameInstance.getContext().shutdown()
    return written


def capture_map(game, output_dir, player_class, map_name, random_map=False):
    """Start a fresh GUI session for ``map_name`` and capture the map view."""
    import game_simulation

    label = "random" if random_map else map_name
    path = output_dir / f"map-{label}.png"
    if random_map:
        game_instance = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(game_instance)
        game.CGameLoader.startRandomGameWithPlayer(game_instance, player_class)
        sim = game_simulation.GameSimulation(game, game_instance, "random", player_class)
        sim.pumpEvents(5)
    else:
        sim = game_simulation.GameSimulation.startGame(game, map_name, player_class, load_gui=True)
    # Pump a few frames so the map view is fully composited before readback.
    sim.pumpEvents(5)
    try:
        info = sim.captureGuiScreenshot(path=path)
        print(f"  [ok]   map {label}: {path.name} ({info.get('bytes', 0)} bytes)", flush=True)
        return path
    finally:
        sim.gameInstance.getContext().shutdown()


def capture_management(game, output_dir, player_class):
    """Capture real selected controls, restrictions, and every compact management region."""
    import game_simulation
    import json

    written = []
    for panel_name, collection in (
        ("inventoryPanel", "inventoryCollection"),
        ("tradePanel", "marketCollection"),
        ("fightPanel", "interactionsCollection"),
        ("questPanel", "questCollection"),
    ):
        sim = game_simulation.GameSimulation.startGame(game, PANELS_MAP, player_class, load_gui=True)
        gui = sim.gameInstance.getGui()
        panel = None
        try:
            gui.applyUiPreferences("{}")
            resizeCaptureWindow(sim, 1920, 1080)
            _prepare_player_for_panels(sim)
            if panel_name == "inventoryPanel":
                item_ids = json.loads((REPO_ROOT / "res/config/items.json").read_text(encoding="utf-8"))
                for item_id in sorted(item_ids)[:24]:
                    sim.player.addItem(sim.gameInstance.createObject(item_id))
                combined = sim.gameInstance.createObject("ArmorOfTheDamned")
                sim.player.addItem(combined)
                for slot in ("0", "1", "2", "3"):
                    sim.player.equipItem(slot, None)
                sim.player.equipItem("3", combined)
                if sim.player.getEquipped().get("3") != combined:
                    raise RuntimeError("Could not prepare equipped compound-artifact capture.")
            panel = sim.gameInstance.getGuiHandler().openPanel(panel_name)
            _configure_panel(sim.gameInstance, panel_name, panel)
            if panel_name == "fightPanel":
                enemies = [sim.gameInstance.createObject(name) for name in ("GoblinThief", "Gooby")]
                for index, enemy in enumerate(enemies):
                    enemy.name = f"captureEnemy{index}"
                    enemy.heal(0)
                # Populate the reader with authoritative engine events from a deterministic
                # no-progress encounter; no fabricated damage or initiative values.
                player_controller = sim.player.getFightController()
                sim.player.setFightController(sim.gameInstance.createObject("CFightController"))
                enemies[1].setFightController(sim.gameInstance.createObject("CFightController"))
                sim.gameMap.addObject(enemies[1])
                try:
                    game.CFightHandler.fightManyOutcome(sim.player, [enemies[1]])
                finally:
                    sim.player.setFightController(player_controller)
                    sim.gameMap.removeObject(enemies[1])
                history = json.loads(sim.gameMap.getStringProperty("combatHistory"))
                if not history or not history[0].startswith("Combat round 1 begins."):
                    raise RuntimeError("The combat log capture has no authoritative encounter history.")
                panel.setEnemies(enemies)
                panel.enemiesCallback(gui, 1, enemies[1])
                sim.player.setMana(0)
            sim.pumpEvents(3)
            view = next(
                child
                for child in panel.getChildren()
                if child.getType() == "CListView" and child.getStringProperty("collection") == collection
            )
            if panel_name == "fightPanel":
                interaction = next(
                    action for action in panel.interactionsCollection(gui) if action.getTypeId() == "Strike"
                )
                panel.interactionsCallback(gui, 0, interaction)
            else:
                labels = {"inventoryPanel": "Crown, scale, greaves", "tradePanel": "Sword", "questPanel": "Gooby"}
                searchCaptureSelection(sim, view, labels[panel_name])
            if panel_name == "tradePanel":
                add = next(
                    child
                    for child in panel.getChildren()
                    if child.getStringProperty("click") == "addSelectedForPurchase"
                )
                clickCaptureWidget(sim, add)
                if panel.getTotalBuyCost() <= sim.player.getGold():
                    raise RuntimeError("Trade capture did not show an unaffordable selected purchase.")

            def captureState(name, dimensions):
                path = output_dir / ("management-" + panel_name + "-" + name + ".png")
                sim.pumpEvents(3)
                info = sim.captureGuiScreenshot(path=path)
                if (info.get("width"), info.get("height")) != dimensions:
                    raise RuntimeError(f"Unexpected screenshot dimensions for {path.name}")
                written.append(path)
                print(f"  [ok]   management {panel_name} {name}: {path.name}", flush=True)

            captureState("selected", (1920, 1080))
            if panel_name == "fightPanel":
                log_button = next(
                    child for child in panel.getChildren() if child.getStringProperty("click") == "showCombatLog"
                )
                before_turn = sim.gameMap.getNumericProperty("turn")
                before_status = panel.getCombatStatus(gui)
                clickCaptureWidget(sim, log_button)
                reader = gui.findChild("CGameTextPanel")
                if reader is None or "Combat round 1 begins." not in reader.getText():
                    raise RuntimeError("The Combat log button did not open the encounter reader.")
                captureState("combat-log", (1920, 1080))
                keyCapture(sim, 1073741901)  # End shows the latest recorded outcome.
                captureState("combat-log-ending", (1920, 1080))
                keyCapture(sim, 27)
                if (
                    panel.isCancelled()
                    or sim.gameMap.getNumericProperty("turn") != before_turn
                    or panel.getCombatStatus(gui) != before_status
                ):
                    raise RuntimeError("Reading combat history changed the encounter or advanced a turn.")
            for width, height in ((1280, 720), (3840, 2160)):
                resizeCaptureWindow(sim, width, height)
                if not gui.applyUiPreferences('{"uiScale":200,"textScale":200}'):
                    raise RuntimeError("Could not apply compact management capture scale.")
                sim.pumpEvents(3)
                groups = sorted({child.getStringProperty("uiGroup") for child in panel.getChildren()} - {""})
                for index in range(len(groups)):
                    visible = {
                        child.getStringProperty("uiGroup")
                        for child in panel.getChildren()
                        if child.isVisible() and child.getStringProperty("uiGroup")
                    }
                    if visible != {groups[index]}:
                        raise RuntimeError(f"Compact region {groups[index]} is not visible: {visible}")
                    captureState(f"{width}x{height}-200-region{index + 1}", (width, height))
                    keyCapture(sim, ord("]"))
                    sim.pumpEvents(2)
        finally:
            if panel is not None:
                panel.close()
            gui.applyUiPreferences("{}")
            sim.gameInstance.getContext().shutdown()
    written.extend(captureRewardReceipts(game, output_dir, player_class))
    return written


def captureRewardReceipts(game, output_dir, player_class):
    """Keep long automatic reward acknowledgements and their ending in the visual gallery."""
    import game_simulation

    sim = game_simulation.GameSimulation.startGame(game, PANELS_MAP, player_class, load_gui=True)
    gui = sim.gameInstance.getGui()
    written = []
    try:
        rewards = []
        for index in range(240):
            item = sim.gameInstance.createObject("Scroll")
            item.name = f"receiptCaptureScroll{index}"
            item.label = f"Recovered scroll {index:03} from the forgotten archive"
            rewards.append(item)
        rewards[-1].label = "ZZZ Final receipt reward"
        before_items = set(sim.player.getItems())
        before_turn = sim.gameMap.getNumericProperty("turn")
        for name, width, height, scale, at_end in (
            ("overflow", 1920, 1080, 100, False),
            ("ending", 1920, 1080, 100, True),
            ("1280x720-200-ending", 1280, 720, 200, True),
        ):
            resizeCaptureWindow(sim, width, height)
            gui.applyUiPreferences(f'{{"uiScale":{scale},"textScale":{scale}}}')

            def prepare(panel, active_gui):
                if at_end:
                    for _ in rewards:
                        panel.keyboardEvent(active_gui, 0x300, 1073741902)  # Page Down

            path = output_dir / f"management-lootPanel-{name}.png"
            _, info = _captureNativeCall(
                game, sim, "showLoot", "CGameLootPanel", (sim.player, set(rewards)), path, prepare
            )
            if (info.get("width"), info.get("height")) != (width, height):
                raise RuntimeError("The reward receipt capture has unexpected dimensions.")
            if set(sim.player.getItems()) != before_items or sim.gameMap.getNumericProperty("turn") != before_turn:
                raise RuntimeError("Reading the reward receipt changed inventory or spent a turn.")
            written.append(path)
            print(f"  [ok]   reward receipt {name}: {path.name}", flush=True)
    finally:
        gui.applyUiPreferences("{}")
        sim.gameInstance.getContext().shutdown()
    return written


def capture_frontend(game, output_dir, player_class):
    """Exercise real frontend flows; capture and cancel each native modal at its first rendered state."""
    import game_simulation
    import ui
    import campaign
    from unittest.mock import patch

    class FrontendSession(game_simulation.GameSimulation):
        def refreshHandles(self):
            self.gameMap = self.gameInstance.getMap()
            self.player = self.gameMap.getPlayer() if self.gameMap is not None else None
            return self

        def pumpEvents(self, times=1):
            for _ in range(times):
                game.event_loop.instance().run()
            self.refreshHandles()

    written = []
    expected_dimensions = (1920, 1080)

    def key(*keys):
        def prepare(panel, gui):
            for value in keys:
                panel.keyboardEvent(gui, 768, value)  # SDL_KEYDOWN

        return prepare

    def capture_flow(sim, name, flow, helper="showChoice", prepare=None, preceding_choices=None):
        path = output_dir / f"frontend-{name}.png"
        panel_class = {
            "showInfo": "CGameTextPanel",
            "showConfirm": "CGameQuestionPanel",
            "showCampaignScreen": "CGameCampaignPanel",
            "showCampaignArtworkScreen": "CGameCampaignPanel",
        }.get(helper, "CGameCampaignBrowserPanel")
        captures = []
        choices_to_skip = dict(preceding_choices or {})

        def capture(self, *arguments):
            if helper == "showChoice" and arguments[0] in choices_to_skip:
                return choices_to_skip.pop(arguments[0])
            if captures:
                return ""
            result, info = _captureNativeCall(game, sim, helper, panel_class, arguments, path, prepare)
            captures.append(info)
            return result

        with patch.object(game.CGuiHandler, helper, capture):
            if helper != "showChoice" and preceding_choices:
                with patch.object(
                    game.CGuiHandler, "showChoice", lambda self, title, *args: choices_to_skip.pop(title, "")
                ):
                    flow(sim.gameInstance)
            else:
                flow(sim.gameInstance)
        if len(captures) != 1:
            raise RuntimeError(f"Expected one native capture for {name}, received {len(captures)}")
        dimensions = (captures[0].get("width"), captures[0].get("height"))
        if dimensions != expected_dimensions:
            raise RuntimeError(f"Capture {name} has dimensions {dimensions}, expected {expected_dimensions}.")
        written.append(path)
        print(f"  [ok]   frontend {name}: {path.name} ({captures[0].get('bytes', 0)} bytes)", flush=True)

    # A fresh session gives the actual initial menu without a map or fabricated player.
    empty_game = game.CGameLoader.loadGame()
    game.CGameLoader.loadGui(empty_game)
    if not empty_game.getGui().applyUiPreferences("{}"):
        raise RuntimeError("Cannot initialize isolated capture preferences.")
    empty_sim = FrontendSession(game, empty_game, "", player_class)
    try:
        with patch.object(ui, "savedGames", return_value=[]):
            capture_flow(empty_sim, "main-disabled", ui.mainMenu)
    finally:
        empty_game.getContext().shutdown()

    sim = FrontendSession.startGame(game, PANELS_MAP, player_class, load_gui=True)
    try:
        capture_flow(
            sim, "main-selected", lambda current: ui.mainMenu(current, in_session=True), prepare=key(1073741905)
        )
        capture_flow(sim, "new-adventure", ui.newAdventure)
        capture_flow(sim, "scenario-preview", ui.newAdventure, preceding_choices={"New adventure": "scenario"})
        capture_flow(sim, "character-preview", ui.chooseCharacter, "showCharacterCreationOptions", key(9, 1073741905))
        capture_flow(sim, "campaign", ui.chooseCampaign)
        manifest = campaign.list_campaigns()[0]
        chapter = manifest["scenarios"][manifest["start"]]

        def chapterArtwork(current):
            campaign._show_screen(
                current, chapter["title"], chapter["briefing"], "Begin chapter", artwork=chapter.get("artwork", "")
            )

        capture_flow(sim, "chapter-artwork", chapterArtwork, "showCampaignArtworkScreen")
        capture_flow(sim, "pause", ui.pause)
        capture_flow(sim, "settings", ui.showSettings)
        capture_flow(sim, "settings-selected", ui.showSettings, prepare=key(1073741901))
        capture_flow(sim, "settings-reset", ui.showSettings, "showConfirm", preceding_choices={"Settings": "reset"})
        capture_flow(
            sim,
            "controls-disabled",
            lambda current: ui.configureBinding(current, ui.preferences(current)),
            preceding_choices={"Controls": "save"},
        )
        capture_flow(
            sim,
            "controls-overflow",
            lambda current: ui.configureBinding(current, ui.preferences(current)),
            prepare=key(1073741901),
            preceding_choices={"Controls": "save"},
        )
        capture_flow(sim, "help-overflow", ui.showHelp, "showCampaignScreen", key(1073741902))
        capture_flow(sim, "save-name", ui.saveMenu, "showTextInput", preceding_choices={"Save adventure": "newSave"})
        capture_flow(
            sim,
            "load-error",
            lambda current: ui.showError(
                current, "The saved adventure could not be loaded. Choose another save or its recovery copy."
            ),
            "showInfo",
        )
        capture_flow(
            sim,
            "save-confirmation",
            lambda current: ui.confirm(
                current,
                "Replace this save?",
                "The selected save will be replaced by your current adventure.",
                "Replace save",
            ),
            "showConfirm",
        )
        path = output_dir / "frontend-loading.png"
        handler = sim.gameInstance.getGuiHandler()
        NATIVE_GUI_HELPERS["showLoading"](handler, "Loading saved adventure...")
        try:
            sim.pumpEvents(2)
            sim.captureGuiScreenshot(path=path)
            written.append(path)
            print(f"  [ok]   frontend loading: {path.name}", flush=True)
        finally:
            NATIVE_GUI_HELPERS["hideLoading"](handler)
        for width, height, ui_scale, text_scale in (
            (1280, 720, 100, 100),
            (1280, 720, 200, 200),
            (1280, 720, 100, 200),
            (3840, 2160, 200, 200),
        ):
            resizeCaptureWindow(sim, width, height)
            expected_dimensions = (width, height)
            if not sim.gameInstance.getGui().applyUiPreferences(f'{{"uiScale":{ui_scale},"textScale":{text_scale}}}'):
                raise RuntimeError("Cannot apply isolated capture scale.")
            suffix = (
                f"{width}x{height}-{ui_scale}"
                if ui_scale == text_scale
                else f"{width}x{height}-ui{ui_scale}-text{text_scale}"
            )
            capture_flow(sim, "settings-" + suffix, ui.showSettings)
            capture_flow(sim, "character-" + suffix, ui.chooseCharacter, "showCharacterCreationOptions", key(9, 9))
            if width == 1280 and ui_scale == text_scale == 200:
                capture_flow(sim, "campaign-artwork-" + suffix, ui.chooseCampaign, prepare=key(9))
                capture_flow(sim, "chapter-artwork-" + suffix, chapterArtwork, "showCampaignArtworkScreen")
                capture_flow(
                    sim,
                    "chapter-artwork-overflow-" + suffix,
                    chapterArtwork,
                    "showCampaignArtworkScreen",
                    key(1073741901),
                )
                capture_flow(sim, "character-class-" + suffix, ui.chooseCharacter, "showCharacterCreationOptions")
                capture_flow(
                    sim, "character-race-" + suffix, ui.chooseCharacter, "showCharacterCreationOptions", key(9)
                )

                def previewEnd(panel, gui):
                    key(9, 9)(panel, gui)
                    sim.pumpEvents(2)
                    key(1073741901)(panel, gui)

                capture_flow(
                    sim, "character-overflow-" + suffix, ui.chooseCharacter, "showCharacterCreationOptions", previewEnd
                )
                for name, prepare in (("letter-reader", None), ("letter-reader-overflow", key(1073741901))):
                    capture_flow(
                        sim,
                        name + "-" + suffix,
                        lambda current: game.showReader(
                            current,
                            "Letter from Rolf",
                            current.createObject("letterFromRolf").getStringProperty("text"),
                        ),
                        "showCampaignScreen",
                        prepare,
                    )
    finally:
        sim.gameInstance.getGui().applyUiPreferences("{}")
        sim.gameInstance.getContext().shutdown()
    return written


def capture_dialogue_context(game, output_dir, player_class):
    """Accept the authored amulet offer, then inspect its live objective without replaying it."""
    import game_simulation

    sim = game_simulation.GameSimulation.startGame(game, PANELS_MAP, player_class, load_gui=True)
    gui = sim.gameInstance.getGui()
    written = []
    try:
        gui.applyUiPreferences("{}")
        resizeCaptureWindow(sim, 1920, 1080)

        def acceptQuest(panel, current_gui):
            keyCapture(sim, ord("1"))
            keyCapture(sim, ord("1"))
            if not any(quest.getTypeId() == "amuletQuest" for quest in sim.player.getQuests()):
                raise RuntimeError("Authored amulet acceptance did not create the objective for capture.")

        path = output_dir / "dialogue-active-objective.png"
        _captureNativeCall(
            game,
            sim,
            "showDialog",
            "CGameDialogPanel",
            (sim.gameInstance.createObject("questDialog"),),
            path,
            acceptQuest,
        )
        written.append(path)
        print(f"  [ok]   dialogue accepted objective: {path.name}", flush=True)
        before = sim.gameMap.getNumericProperty("turn")

        def readObjective(panel, current_gui):
            keyCapture(sim, ord("o"))
            if panel.getStringProperty("title") != "Current objective":
                raise RuntimeError("The dialogue objective reader was not opened by its keyboard shortcut.")

        for width, height, scale in ((1920, 1080, 100), (1280, 720, 200)):
            resizeCaptureWindow(sim, width, height)
            gui.applyUiPreferences(f'{{"uiScale":{scale},"textScale":{scale}}}')
            path = output_dir / f"dialogue-objective-reader-{width}x{height}-{scale}.png"
            _, info = _captureNativeCall(
                game,
                sim,
                "showDialog",
                "CGameDialogPanel",
                (sim.gameInstance.createObject("questDialog"),),
                path,
                readObjective,
            )
            if (info.get("width"), info.get("height")) != (width, height):
                raise RuntimeError("Dialogue capture output did not match its isolated display size.")
            written.append(path)
            print(f"  [ok]   dialogue objective reader: {path.name}", flush=True)
        if sim.gameMap.getNumericProperty("turn") != before:
            raise RuntimeError("Reading dialogue objectives advanced a game turn.")
    finally:
        gui.applyUiPreferences("{}")
        sim.gameInstance.getContext().shutdown()
    return written


def captureAcceptanceStates(game, output_dir, player_class):
    """Capture real service and outcome flows in a disposable, isolated game session.

    Inventory, stats and campaign position are explicit fixture setup, not a gameplay
    walkthrough. Costs, rewards, defeat receipts and outcome copy come from production
    operations. Browsing and cancelled previews must preserve the prepared state.
    """
    import campaign
    import crafting
    import artifact_sets
    import game_simulation
    import json
    import ui
    import uuid
    from unittest.mock import patch

    sim = game_simulation.GameSimulation.startGame(game, PANELS_MAP, player_class, load_gui=True)
    gui = sim.gameInstance.getGui()
    player = sim.player
    written = []
    save_paths = []

    def state():
        coords = player.getCoords()
        return (
            sim.gameMap.getNumericProperty("turn"),
            (coords.x, coords.y, coords.z),
            player.getGold(),
            player.getHp(),
            player.getMana(),
            tuple(sorted(item.getName() for item in player.getItems())),
            tuple(sorted((slot, item.getName()) for slot, item in player.getEquipped().items() if item)),
        )

    def record(name):
        path = output_dir / (name + ".png")
        sim.pumpEvents(2)
        info = sim.captureGuiScreenshot(path=path)
        if (info.get("width"), info.get("height")) != (1920, 1080):
            raise RuntimeError(f"Unexpected acceptance capture dimensions: {name}")
        written.append(path)
        print(f"  [ok]   acceptance {name}: {info.get('bytes', 0)} bytes", flush=True)

    def previewChoice(panel, choice_id, limit=100):
        for _ in range(limit):
            if panel.getSelectedId() == choice_id:
                return
            keyCapture(sim, 1073741905)
        raise RuntimeError(f"Could not select capture choice {choice_id}")

    def flowCaptures(flow, names, helper="showChoice", decisions=(), prepare=None):
        captures = []
        panel_class = (
            "CGameCampaignPanel"
            if helper in ("showCampaignScreen", "showCampaignArtworkScreen")
            else "CGameCampaignBrowserPanel"
        )

        def capture(handler, *arguments):
            index = len(captures)
            if index >= len(names):
                raise RuntimeError(f"Unexpected extra {helper} while capturing {names}")
            name = names[index]
            path = output_dir / (name + ".png")

            def inspect(panel, current_gui):
                if index and index <= len(decisions):
                    if panel.getSelectedId() != decisions[index - 1] or "Last result" not in panel.getDetailText():
                        raise RuntimeError("The recipe result is not shown beside the selected recipe's details.")
                if index < len(decisions):
                    previewChoice(panel, decisions[index], len(json.loads(arguments[1])))
                if prepare:
                    prepare(panel, current_gui)

            result, info = _captureNativeCall(game, sim, helper, panel_class, arguments, path, inspect)
            if (info.get("width"), info.get("height")) != (1920, 1080):
                raise RuntimeError(f"Unexpected acceptance capture dimensions: {name}")
            captures.append(path)
            print(f"  [ok]   acceptance {name}: {info.get('bytes', 0)} bytes", flush=True)
            return decisions[index] if index < len(decisions) else result

        with patch.object(game.CGuiHandler, helper, capture):
            flow()
        if len(captures) != len(names):
            raise RuntimeError(f"Expected captures {names}; received {len(captures)}")
        written.extend(captures)

    try:
        gui.applyUiPreferences("{}")
        resizeCaptureWindow(sim, 1920, 1080)

        # Only this disposable slot appears in the list: never expose or modify a player's saves.
        provider = sim.gameInstance.getResourcesProvider()
        existing_slots = set(provider.getFiles("SAVE"))
        slot = "Before-the-northern-gate-" + uuid.uuid4().hex[:8]
        while slot in existing_slots:
            slot = "Before-the-northern-gate-" + uuid.uuid4().hex[:8]
        if not game.CMapLoader.saveWithResult(sim.gameMap, slot):
            raise RuntimeError("Could not create the isolated save-list fixture.")
        save_path = Path(provider.getPath("save/" + slot + ".json"))
        save_paths.append(save_path)
        row = ui.readSavePreview(provider, slot)
        if "Map:" not in row["detail"] or "Saved:" not in row["detail"]:
            raise RuntimeError("Save-list capture has no native save metadata.")
        before = state()
        with patch.object(ui, "savedGames", return_value=[row]):
            flowCaptures(lambda: ui.loadMenu(sim.gameInstance), ["frontend-load-list"])
            flowCaptures(lambda: ui.saveMenu(sim.gameInstance), ["frontend-save-list"])
        if state() != before:
            raise RuntimeError("Cancelling save/load browsing changed the session.")

        panel = sim.gameInstance.getGuiHandler().openPanel("characterPanel")
        try:
            if not list(player.getEffectiveInteractions()):
                raise RuntimeError("Character capture needs an owned ability.")
            sim.pumpEvents(2)
            abilities = next(
                child
                for child in panel.getChildren()
                if child.getStringProperty("collection") == "interactionsCollection"
            )
            clickCaptureWidget(sim, abilities, row=True)
            record("management-character-ability-selected")
            modifiers = next(
                child for child in panel.getChildren() if child.getStringProperty("click") == "inspectModifiers"
            )
            clickCaptureWidget(sim, modifiers)
            record("management-character-modifiers")
            keyCapture(sim, 27)
        finally:
            panel.close()
        keyCapture(sim, ord("m"))
        record("management-expanded-map")
        map_panel = next(child for child in gui.getChildren() if child.getStringProperty("title") == "Map & landmarks")
        map_view = next(child for child in map_panel.getChildren() if child.getType() == "CMinimapGraphicsObject")
        landmarks = next(
            child for child in map_view.getChildren() if child.getStringProperty("click") == "browseLandmarks"
        )
        path = output_dir / "management-map-landmarks.png"
        _captureNativeCall(
            game,
            sim,
            "showChoice",
            "CGameCampaignBrowserPanel",
            (),
            path,
            open_action=lambda: clickCaptureWidget(sim, landmarks),
        )
        written.append(path)
        keyCapture(sim, 27)
        if state() != before:
            raise RuntimeError("Inspecting abilities, modifiers or landmarks changed the session.")

        # The authored recipe controls produce their own ingredient counts and restrictions.
        station = sim.gameMap.getObjectByName("alchemyTable1")
        player.setNumericProperty("gold", 2000)
        for item_id in ("LesserLifePotion", "LesserManaPotion"):
            for _ in range(2):
                player.addItem(sim.gameInstance.createObject(item_id))
        before = state()
        flowCaptures(
            lambda: crafting.open_crafting_station(station, player),
            ["management-crafting-ready"],
            prepare=lambda panel, current_gui: previewChoice(panel, "brew_life_potion"),
        )
        if state() != before:
            raise RuntimeError("Cancelling recipe browsing consumed ingredients.")
        gold_before = player.getGold()
        life_before = player.countItems("LifePotion")
        life_reagents_before = player.countItems("LesserLifePotion")
        flowCaptures(
            lambda: crafting.open_crafting_station(station, player),
            ["management-crafting-review", "management-crafting-success"],
            decisions=("brew_life_potion",),
        )
        if (
            player.getGold() != gold_before - 20
            or player.countItems("LifePotion") != life_before + 1
            or player.countItems("LesserLifePotion") != life_reagents_before - 2
        ):
            raise RuntimeError("The captured successful craft did not resolve its authoritative cost/output.")
        gold_before = player.getGold()
        mana_before = player.countItems("ManaPotion")
        mana_reagents_before = player.countItems("LesserManaPotion")
        # Force a legal failed roll; the production craft still owns payment and result text.
        with patch.object(crafting, "randint", return_value=100):
            flowCaptures(
                lambda: crafting.open_crafting_station(station, player),
                ["management-crafting-failure-review", "management-crafting-failure"],
                decisions=("brew_mana_potion",),
            )
        if (
            player.getGold() != gold_before - 640
            or player.countItems("ManaPotion") != mana_before
            or player.countItems("LesserManaPotion") != mana_reagents_before - 2
        ):
            raise RuntimeError("The captured failed craft did not consume its authoritative cost.")

        runtime = artifact_sets.get_runtime()
        definition = runtime.set_for_combined("ArmorOfTheDamned")
        for slot_id in list(player.getEquipped()):
            player.equipItem(slot_id, None)
        for piece_id in definition["pieces"]:
            piece = sim.gameInstance.createObject(piece_id)
            player.addItem(piece)
            slot_id = next(iter(sim.gameInstance.getSlotConfiguration().getFittingSlots(piece)))
            player.equipItem(slot_id, piece)
        sim.pumpEvents(3)  # Drain the ordinary on-equip offers through the global cancel adapter.
        before = state()
        flowCaptures(lambda: artifact_sets.maybe_offer_assembly(player), ["management-artifact-assembly"])
        flowCaptures(
            lambda: artifact_sets.maybe_offer_assembly(player),
            ["management-artifact-assembly-ending"],
            prepare=lambda panel, current_gui: keyCapture(sim, 1073741902),
        )
        if state() != before:
            raise RuntimeError("Cancelling assembly changed equipment.")
        if not runtime.assemble(sim.gameInstance, player, definition):
            raise RuntimeError("Could not resolve the disposable artifact fixture.")
        combined = player.getItemAtSlot("3")
        before = state()
        flowCaptures(lambda: artifact_sets.offer_disassembly(combined, player), ["management-artifact-disassembly"])
        flowCaptures(
            lambda: artifact_sets.offer_disassembly(combined, player),
            ["management-artifact-disassembly-ending"],
            prepare=lambda panel, current_gui: keyCapture(sim, 1073741902),
        )
        if state() != before:
            raise RuntimeError("Cancelling disassembly changed equipment.")

        # Drive the production defeat resolver, then display its committed receipt once.
        # The artifact's 250 armor would clamp physical hits to zero in this fixture.
        player.equipItem("3", None)
        enemy = sim.gameInstance.createObject("GoblinThief")
        enemy.name = "captureDefeatOpponent"
        enemy.setCoords(player.getCoords())
        sim.gameMap.addObject(enemy)
        enemy.setHp(enemy.getHpMax())
        enemy.setMana(enemy.getManaMax())
        enemy_stats = enemy.getObjectProperty("baseStats")
        for property_name in ("hit", "dmgMin", "dmgMax"):
            enemy_stats.setNumericProperty(property_name, 10000)
        player.setFightController(sim.gameInstance.createObject("CFightController"))
        player.setHp(1)
        outcome = game.CFightHandler.fightManyOutcome(enemy, [player])
        raw_receipt = player.getStringProperty("uiDefeatReceipt")
        if not raw_receipt:
            raise RuntimeError(f"No defeat receipt after {outcome}: " + sim.gameMap.getStringProperty("combatHistory"))
        receipt = json.loads(raw_receipt)
        if receipt.get("hp") != 1 or receipt.get("lostItemCount", 0) == 0:
            raise RuntimeError("Defeat capture has no resolved one-HP recovery and item losses.")
        entry = (sim.gameMap.getEntryX(), sim.gameMap.getEntryY(), sim.gameMap.getEntryZ())
        if tuple(receipt[key] for key in ("x", "y", "z")) != entry or receipt.get("map") != PANELS_MAP:
            raise RuntimeError("Defeat capture did not identify the actual map entrance recovery.")
        before = state()
        flowCaptures(lambda: ui.showDefeat(sim.gameInstance), ["frontend-defeat"])
        if state() != before or player.getStringProperty("uiDefeatReceipt"):
            raise RuntimeError("Defeat acknowledgement replayed losses or retained a stale receipt.")

        # A terminal authored chapter produces both the outcome and completion screen.
        manifest = next(row for row in campaign.list_campaigns() if row["campaignId"] == "longLiveTheQueen")
        terminal_id = next(key for key, chapter in manifest["scenarios"].items() if not chapter.get("next"))
        store = campaign.state(sim.gameInstance)
        store.begin(manifest["campaignId"], terminal_id)
        flowCaptures(
            lambda: campaign.complete_scenario(sim.gameInstance, "completed"),
            ["frontend-chapter-outcome", "frontend-campaign-complete"],
            helper="showCampaignScreen",
        )
        if not store.finished() or store.history() != [(terminal_id, "completed")]:
            raise RuntimeError("Campaign outcome acknowledgement did not preserve its committed result.")
    finally:
        gui.applyUiPreferences("{}")
        sim.gameInstance.getContext().shutdown()
        for path in save_paths:
            path.unlink(missing_ok=True)
        ui.SAVE_PREVIEW_CACHE.clear()
    return written


def main():
    parser = argparse.ArgumentParser(description="Regenerate the coverage screenshot set.")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "screenshots"))
    parser.add_argument("--player", default="Warrior")
    parser.add_argument("--maps", nargs="*", default=None, help="Map names to capture (default: all under res/maps/).")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--panels-only", action="store_true", help="Capture panel, management, and frontend screenshots."
    )
    selection.add_argument("--maps-only", action="store_true", help="Capture only the map screenshots.")
    selection.add_argument(
        "--management-only", action="store_true", help="Capture only selected and compact management states."
    )
    selection.add_argument("--frontend-only", action="store_true", help="Capture only frontend states.")
    selection.add_argument(
        "--acceptance-only", action="store_true", help="Capture service, session outcome, ability and map states."
    )
    parser.add_argument("--no-random", action="store_true", help="Skip the random-map screenshot.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # Captures must not read or overwrite the player's persisted interface settings.
    preference_path = output_dir / ".capture-preferences.json"
    previous_preferences = os.environ.get("GAME_UI_PREFERENCES_PATH")
    os.environ["GAME_UI_PREFERENCES_PATH"] = str(preference_path)
    try:
        generateScreenshots(args, output_dir)
    finally:
        preference_path.unlink(missing_ok=True)
        if previous_preferences is None:
            os.environ.pop("GAME_UI_PREFERENCES_PATH", None)
        else:
            os.environ["GAME_UI_PREFERENCES_PATH"] = previous_preferences


def generateScreenshots(args, output_dir):

    maps = args.maps if args.maps is not None else discover_maps()
    panels = discover_panels()

    _reexec_under_xvfb_if_needed()
    _bootstrap_paths()
    game = _load_game_module()

    _suppress_blocking_popups(game)

    written = []
    failures = 0

    acceptance_only = getattr(args, "acceptance_only", False)
    capture_registered = not (args.maps_only or args.management_only or args.frontend_only or acceptance_only)
    if capture_registered:
        print(f"Capturing {len(panels)} panel screenshots on the '{PANELS_MAP}' map...", flush=True)
        written.extend(capture_panels(game, output_dir, args.player, panels))
    if not (args.maps_only or args.frontend_only or acceptance_only):
        try:
            written.extend(capture_management(game, output_dir, args.player))
            written.extend(capture_dialogue_context(game, output_dir, args.player))
        except Exception:
            failures += 1
            print(f"  [fail] management states:\n{traceback.format_exc()}", flush=True)
    if not (args.maps_only or args.management_only or acceptance_only):
        try:
            written.extend(capture_frontend(game, output_dir, args.player))
        except Exception:
            failures += 1
            print(f"  [fail] frontend states:\n{traceback.format_exc()}", flush=True)

    if acceptance_only or not (args.maps_only or args.management_only or args.frontend_only):
        try:
            written.extend(captureAcceptanceStates(game, output_dir, args.player))
        except Exception:
            failures += 1
            print(f"  [fail] acceptance states:\n{traceback.format_exc()}", flush=True)

    if not (args.panels_only or args.management_only or args.frontend_only or acceptance_only):
        print(f"Capturing {len(maps)} map screenshots...", flush=True)
        for map_name in maps:
            try:
                written.append(capture_map(game, output_dir, args.player, map_name))
            except Exception:  # noqa: BLE001 - keep going so one map can't abort the set
                failures += 1
                print(f"  [fail] map {map_name}:\n{traceback.format_exc()}", flush=True)
        if not args.no_random:
            try:
                written.append(capture_map(game, output_dir, args.player, "random", random_map=True))
            except Exception:  # noqa: BLE001
                failures += 1
                print(f"  [fail] map random:\n{traceback.format_exc()}", flush=True)

    written.extend(refreshScreenshotAliases(output_dir, written))
    for path in written:
        try:
            verifyScreenshot(path)
        except Exception as exc:
            failures += 1
            print(f"  [fail] screenshot verification {path.name}: {exc}", flush=True)
    print(f"\nWrote {len(written)} screenshot(s) to {output_dir}", flush=True)

    # Report panel coverage against the manifest so a missing panel is obvious.
    if capture_registered:
        captured_panels = {p.stem[len("panel-") :] for p in written if p.stem.startswith("panel-")}
        missing = [name for name in panels if name not in captured_panels]
        if missing:
            print(f"WARNING: no screenshot produced for panels: {', '.join(missing)}", flush=True)
            failures += 1

    if failures:
        raise SystemExit(f"{failures} screenshot target(s) failed; see the log above.")


if __name__ == "__main__":
    main()
