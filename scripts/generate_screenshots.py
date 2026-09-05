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

Requirements: the ``_game`` module must be built (see the project README) and
``pillow`` installed (``pip install -r requirements-dev.txt``). A real SDL
renderer is needed, so on Linux the script re-executes itself under
``xvfb-run`` automatically; you can also run it explicitly::

    xvfb-run -a --server-args="-screen 0 1920x1080x24" \\
        python3 scripts/generate_screenshots.py

Usage::

    python3 scripts/generate_screenshots.py --output-dir screenshots
    python3 scripts/generate_screenshots.py --panels-only
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
    """Re-run this process under ``xvfb-run`` with the x11 SDL driver.

    A genuine SDL renderer (not the ``dummy`` driver) is required for pixel
    readback, and on headless Linux that means an X server. This mirrors the
    invocation used by the project's GUI tests.
    """
    if os.name != "posix":
        return
    if os.environ.get(REEXEC_SENTINEL) == "1":
        return
    if os.environ.get("SDL_VIDEODRIVER") == "x11" and os.environ.get("DISPLAY"):
        return
    import shutil

    if shutil.which("xvfb-run") is None:
        # No xvfb available; fall through and let SDL try whatever is configured.
        return

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
    auto-dismissing stubs (questions auto-confirm), exactly as the GUI tests and
    the walkthrough recorder do. The panels we open explicitly still render
    normally.
    """
    handler = game.CGuiHandler
    for name in ("showSelection", "showLoot", "showDialog", "showCampaignSelection"):
        NATIVE_GUI_HELPERS[name] = getattr(handler, name)
    handler.showMessage = lambda self, message: None
    handler.showInfo = lambda self, message, centered=False: None
    handler.showQuestion = lambda self, message: True
    handler.showSelection = lambda self, *args, **kwargs: None
    handler.showLoot = lambda self, *args, **kwargs: None
    handler.showTrade = lambda self, *args, **kwargs: None
    handler.showDialog = lambda self, *args, **kwargs: None


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
        panel.setStringProperty("title", "Chapter I - The Ruined Town")
        panel.setStringProperty("body", "Recover Sergeant Rolf's letter and cleanse the corruption beneath Nouraajd.")
        panel.setStringProperty("actionLabel", "BEGIN")
        for child in panel.getChildren():
            if child.getType() == "CButton":
                child.setStringProperty("text", "BEGIN")
    elif panel_name in {"infoPanel", "textPanel"}:
        panel.setText(f"{panel_name}: rendered for screenshot coverage")
    elif panel_name == "questionPanel":
        panel.setStringProperty("question", "Regenerate the screenshots?")
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


def _populateCampaignBrowser(game_instance, panel):
    import campaign

    manifests = campaign.list_campaigns()
    if manifests:
        first = manifests[0]
        panel.setStringProperty("selectedId", first["campaignId"])
        panel.setStringProperty(
            "detailText", f"{first['title']}\n\n{first.get('description', '')}\n\nChapters: {len(first['scenarios'])}"
        )


def _captureNativePanel(game, sim, panel_name, path):
    """Use native helpers for panels whose initialization is not exposed to Python."""
    game_instance = sim.gameInstance
    if panel_name == "campaignBrowserPanel":
        import campaign

        helper_name, panel_class = "showCampaignSelection", "CGameCampaignBrowserPanel"
        manifests = campaign.list_campaigns()
        titles = game_instance.createObject("CMapStringString")
        titles.setValues({manifest["campaignId"]: manifest["title"] for manifest in manifests})
        descriptions = game_instance.createObject("CMapStringString")
        descriptions.setValues({manifest["campaignId"]: manifest.get("description", "") for manifest in manifests})
        counts = game_instance.createObject("CMapStringInt")
        counts.setValues({manifest["campaignId"]: len(manifest["scenarios"]) for manifest in manifests})
        arguments = (titles, descriptions, counts)
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
        helper_name, panel_class = "showSelection", "CGamePanel"
        choices = game_instance.createObject("CListString")
        for label in ("Accept the contract", "Decline", "Ask for more gold"):
            choices.addValue(label)
        arguments = (choices,)
    captured = {}

    def captureAndClose():
        panel = game_instance.getGui().findChild(panel_class)
        if panel is None:
            raise RuntimeError(f"Native helper did not open {panel_name}")
        try:
            if panel_name == "campaignBrowserPanel":
                _populateCampaignBrowser(game_instance, panel)
            sim.pumpEvents(5)
            captured.update(sim.captureGuiScreenshot(path=path))
        finally:
            game_instance.getGuiHandler().flipPanel(panel_name, "x")

    game.event_loop.instance().invoke(captureAndClose)
    NATIVE_GUI_HELPERS[helper_name](game_instance.getGuiHandler(), *arguments)
    return captured


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
    info = sim.captureGuiScreenshot(path=path)
    print(f"  [ok]   map {label}: {path.name} ({info.get('bytes', 0)} bytes)", flush=True)
    return path


def main():
    parser = argparse.ArgumentParser(description="Regenerate the coverage screenshot set.")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "screenshots"))
    parser.add_argument("--player", default="Warrior")
    parser.add_argument("--maps", nargs="*", default=None, help="Map names to capture (default: all under res/maps/).")
    parser.add_argument("--panels-only", action="store_true", help="Capture only the panel screenshots.")
    parser.add_argument("--maps-only", action="store_true", help="Capture only the map screenshots.")
    parser.add_argument("--no-random", action="store_true", help="Skip the random-map screenshot.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    maps = args.maps if args.maps is not None else discover_maps()
    panels = discover_panels()

    _reexec_under_xvfb_if_needed()
    _bootstrap_paths()
    game = _load_game_module()

    _suppress_blocking_popups(game)

    written = []
    failures = 0

    if not args.maps_only:
        print(f"Capturing {len(panels)} panel screenshots on the '{PANELS_MAP}' map...", flush=True)
        written.extend(capture_panels(game, output_dir, args.player, panels))

    if not args.panels_only:
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

    print(f"\nWrote {len(written)} screenshot(s) to {output_dir}", flush=True)

    # Report panel coverage against the manifest so a missing panel is obvious.
    if not args.maps_only:
        captured_panels = {p.stem[len("panel-") :] for p in written if p.stem.startswith("panel-")}
        missing = [name for name in panels if name not in captured_panels]
        if missing:
            print(f"WARNING: no screenshot produced for panels: {', '.join(missing)}", flush=True)
            failures += 1

    if failures:
        raise SystemExit(f"{failures} screenshot target(s) failed; see the log above.")


if __name__ == "__main__":
    main()
