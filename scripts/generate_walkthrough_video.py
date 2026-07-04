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
"""Render a cinematic walkthrough of the Nouraajd campaign to a video file.

The script starts a real (GUI) headless game session of the ``nouraajd`` map,
walks the player tile-by-tile to every quest objective, completes the full
quest chain (Rolf, Gooby, Beren's letter/relic/cleanse, Victor, and the
amulet), showcases the inventory / quest-log / character panels, and records
the SDL framebuffer after each step. The captured frames are encoded to an MP4.

It reuses the deterministic :class:`game_simulation.GameSimulation` driver and
the engine's ``read_pixels`` binding (the same readback the screenshot tests
use), so the rendered frames match what the game actually draws.

Requirements: the ``_game`` module must be built (see the project README) and
``imageio``/``imageio-ffmpeg``/``numpy``/``pillow`` installed
(``pip install -r requirements-dev.txt``). A real SDL renderer is needed, so on
Linux the script re-executes itself under ``xvfb-run`` automatically; you can
also run it explicitly::

    xvfb-run -a --server-args="-screen 0 1920x1080x24" \\
        python3 scripts/generate_walkthrough_video.py

Usage::

    python3 scripts/generate_walkthrough_video.py \\
        --output screenshots/nouraajd-walkthrough.mp4 --scale 1280x720 --fps 24
"""

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REEXEC_SENTINEL = "NOURAAJD_WALKTHROUGH_REEXEC"


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
    """Turn modal popups into non-blocking no-ops for headless playback.

    Walking onto event tiles and resolving quests fires modal message/question
    panels that block the SDL event loop waiting for a keypress. In an automated
    capture there is no interactive keyboard, so we replace those handlers with
    auto-dismissing stubs (questions auto-confirm) exactly as the GUI tests do.
    The map, sprites, and the inventory/quest/character panels we open
    explicitly still render normally.
    """
    handler = game.CGuiHandler
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
# Frame capture / encoding
# ---------------------------------------------------------------------------
class FrameRecorder:
    """Captures SDL frames and streams them straight to the video encoder.

    Frames are written to the encoder as they are captured rather than held in
    memory, so a long walkthrough (hundreds of tiles) stays cheap on RAM.
    """

    def __init__(self, sim, output_path, fps, size=(1280, 720), captions=True):
        import imageio.v2 as imageio

        self.sim = sim
        self.size = size
        self.captions = captions
        self.fps = fps
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.frame_count = 0
        self.first_frame = None
        self.last_frame = None
        self._read_pixels = self._resolve_read_pixels()
        self._font = self._load_font(30)
        self._title_font = self._load_font(54)
        self._subtitle_font = self._load_font(34)
        self._writer = imageio.get_writer(
            str(self.output_path),
            fps=fps,
            codec="libx264",
            quality=8,
            macro_block_size=None,
            ffmpeg_params=["-pix_fmt", "yuv420p"],
        )

    def _resolve_read_pixels(self):
        gui = self.sim.gameInstance.getGui()
        if gui is None:
            raise SystemExit("Game has no GUI; start the session with load_gui=True.")
        rp = getattr(gui, "read_pixels", None) or getattr(gui, "readPixels", None)
        if rp is None:
            raise SystemExit("GUI does not expose pixel readback (read_pixels).")
        return rp

    @staticmethod
    def _load_font(size=30):
        from PIL import ImageFont

        for candidate in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ):
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _grab(self, advance_turn=False):
        from PIL import Image

        # The map view only follows the hero when a turn advances: a bare
        # setCoords leaves the cached frame on screen. So movement frames advance
        # one turn (ensure_safe first relocates off any adjacent creature so the
        # turn never drops into blocking combat). Static beats and panels render
        # on a plain pump, which is much cheaper and carries no combat risk.
        if advance_turn:
            ensure_safe(self.sim)
            self.sim.gameMap.move()
        self.sim.pumpEvents(1)
        pixels, width, height = self._read_pixels()
        image = Image.frombytes("RGBA", (int(width), int(height)), bytes(pixels)).convert("RGB")
        if self.size and image.size != tuple(self.size):
            image = image.resize(self.size, Image.BILINEAR)
        return image

    def _draw_caption(self, image, text):
        if not text or not self.captions:
            return image
        from PIL import ImageDraw

        image = image.copy()
        draw = ImageDraw.Draw(image)
        width, height = image.size
        bar_height = 56
        draw.rectangle([(0, height - bar_height), (width, height)], fill=(0, 0, 0))
        draw.text((20, height - bar_height + 12), text, fill=(235, 225, 200), font=self._font)
        return image

    def capture(self, caption=None, hold=1, advance_turn=False):
        """Grab one frame, optionally captioned, and stream it ``hold`` times."""
        import numpy as np

        frame = self._draw_caption(self._grab(advance_turn=advance_turn), caption)
        array = np.asarray(frame)
        for _ in range(max(1, int(hold))):
            self._writer.append_data(array)
            self.frame_count += 1
        if self.first_frame is None:
            self.first_frame = frame
        self.last_frame = frame
        return frame

    def capture_card(self, title, body="", subtitle="", hold=None):
        """Render a full-screen chapter title card and stream it for ``hold`` frames.

        Campaign chapters open with one of these cards: the scenario title, an
        optional subtitle (e.g. the destination map), and the manifest briefing
        wrapped to the frame width over a dark parchment background. It is drawn
        from scratch rather than over a game frame so the text stays legible.
        """
        import numpy as np
        from PIL import Image, ImageDraw

        if hold is None:
            hold = max(1, int(round(2.6 * self.fps)))
        width, height = self.size
        image = Image.new("RGB", (width, height), (12, 9, 8))
        draw = ImageDraw.Draw(image)
        # Crimson rules top and bottom frame the card.
        draw.rectangle([(0, 0), (width, 7)], fill=(122, 28, 22))
        draw.rectangle([(0, height - 7), (width, height)], fill=(122, 28, 22))

        margin = 84
        max_text = width - 2 * margin
        title_lines = _wrap_text(draw, title, self._title_font, max_text)
        subtitle_lines = _wrap_text(draw, subtitle, self._subtitle_font, max_text) if subtitle else []
        body_lines = _wrap_text(draw, body, self._font, max_text) if body else []

        def block_height(lines, font, spacing):
            return sum(font.size + spacing for _ in lines)

        total = block_height(title_lines, self._title_font, 12)
        if subtitle_lines:
            total += 18 + block_height(subtitle_lines, self._subtitle_font, 8)
        if body_lines:
            total += 34 + block_height(body_lines, self._font, 10)
        y = max(margin, (height - total) // 2)

        for line in title_lines:
            draw.text((margin, y), line, fill=(238, 212, 150), font=self._title_font)
            y += self._title_font.size + 12
        if subtitle_lines:
            y += 18
            for line in subtitle_lines:
                draw.text((margin, y), line, fill=(198, 166, 116), font=self._subtitle_font)
                y += self._subtitle_font.size + 8
        if body_lines:
            y += 34
            for line in body_lines:
                draw.text((margin, y), line, fill=(206, 198, 180), font=self._font)
                y += self._font.size + 10

        array = np.asarray(image)
        for _ in range(max(1, int(hold))):
            self._writer.append_data(array)
            self.frame_count += 1
        if self.first_frame is None:
            self.first_frame = image
        self.last_frame = image
        return image

    def close(self):
        self._writer.close()
        return self.output_path


# ---------------------------------------------------------------------------
# Real input injection (keystrokes / mouse clicks)
# ---------------------------------------------------------------------------
# SDL event/keycode constants (SDL2 ABI). Arrow-key SDL_KEYDOWN events are the
# hero's movement input: CMapGraphicsObject::keyboardEvent turns each one into a
# one-tile step in that direction plus a turn advance, exactly as a human player
# pressing an arrow key would. Injecting them through the bound keyboardEvent
# routes through the same GUI dispatch a real key press takes.
SDL_KEYDOWN = 0x300
SDL_MOUSEBUTTONDOWN = 0x401
SDL_MOUSEBUTTONUP = 0x402
SDL_BUTTON_LEFT = 1
SDLK_UP = 0x40000052
SDLK_DOWN = 0x40000051
SDLK_LEFT = 0x40000050
SDLK_RIGHT = 0x4000004F


class InputDriver:
    """Drives the hero with real injected keyboard (and mouse) events.

    The map view's ``CMapGraphicsObject`` handles arrow keys by stepping the
    hero one tile and advancing the turn, so walking is done purely through
    injected key presses — the hero actually pathwalks the map rather than
    having its coordinates teleported. Mouse clicks are injected the same way
    for widget interactions.
    """

    def __init__(self, sim):
        self.sim = sim
        self.refresh()

    def refresh(self):
        self.gui = self.sim.gameInstance.getGui()
        # The map graphics object is re-created per loaded map, so re-resolve it
        # after every scene/map transition.
        self.mapobj = self.gui.findChild("CMapGraphicsObject") if self.gui else None
        return self

    def key(self, keycode):
        if self.mapobj is None:
            self.refresh()
        if self.mapobj is not None:
            self.mapobj.keyboardEvent(self.gui, SDL_KEYDOWN, keycode)

    def step(self, dx, dy):
        """Press the arrow key for a one-tile step. Paths are 4-connected, so at
        most one axis is ever non-zero; prefer the horizontal step otherwise."""
        if dx > 0:
            self.key(SDLK_RIGHT)
        elif dx < 0:
            self.key(SDLK_LEFT)
        elif dy > 0:
            self.key(SDLK_DOWN)
        elif dy < 0:
            self.key(SDLK_UP)


def _input_driver(sim):
    driver = getattr(sim, "_input_driver_cache", None)
    if driver is None:
        driver = InputDriver(sim)
        sim._input_driver_cache = driver
    return driver


def _path_from_player(sim, dest, max_len=400, max_nodes=80000):
    """Breadth-first path of 4-connected walkable tiles from the hero's current
    tile to ``dest`` (or the closest reachable tile toward it), as a list of
    ``Coords`` the hero can walk one key press at a time. The goal tile itself is
    allowed even when occupied so an objective standing on a blocked tile is
    still approachable."""
    from collections import deque

    Coords = sim.gameModule.Coords
    can_step = sim.gameMap.canStep
    p = sim.player.getCoords()
    start = (int(p.x), int(p.y), int(p.z))
    goal = (int(dest.x), int(dest.y), int(dest.z))
    if start == goal:
        return []
    parent = {start: None}
    frontier = deque([start])
    found = None
    nodes = 0
    while frontier and nodes < max_nodes:
        node = frontier.popleft()
        nodes += 1
        if node == goal:
            found = node
            break
        x, y, z = node
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cand = (x + dx, y + dy, z)
            if cand in parent:
                continue
            if cand == goal or can_step(Coords(*cand)):
                parent[cand] = node
                frontier.append(cand)
    if found is None:
        # Goal unreachable within budget: aim for the explored tile closest to it
        # so the hero still walks meaningfully toward the objective.
        found = min(parent, key=lambda n: abs(n[0] - goal[0]) + abs(n[1] - goal[1]))
    path = []
    node = found
    while node is not None and node != start:
        path.append(Coords(node[0], node[1], node[2]))
        node = parent[node]
    path.reverse()
    if max_len and len(path) > max_len:
        path = path[:max_len]
    return path


# ---------------------------------------------------------------------------
# Movement helpers
# ---------------------------------------------------------------------------
def _wrap_text(draw, text, font, max_width):
    """Greedily wrap ``text`` to fit ``max_width`` pixels using the font metrics."""
    words = str(text).split()
    if not words:
        return []
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _log_progress(sim, message):
    """Emit a flushed, timestamp-free progress line with the player's tile."""
    coords = sim.player.getCoords()
    print(f"[tile {coords.x:>3},{coords.y:>3}] {message}", flush=True)


def _live_creature_coords(sim):
    """Return the tiles occupied by live creatures other than the hero."""
    player_name = sim._safeCall(sim.player, "getName")
    occupied = set()
    for obj in sim.gameMap.getObjects():
        if sim._safeCall(obj, "getName") == player_name:
            continue
        if sim._safeCall(obj, "isAlive"):
            c = obj.getCoords()
            occupied.add((c.x, c.y, c.z))
    return occupied


def _distance_to_object(sim, object_name):
    obj = sim.gameMap.getObjectByName(object_name)
    if obj is None:
        return None
    pc = sim.player.getCoords()
    oc = obj.getCoords()
    return abs(pc.x - oc.x) + abs(pc.y - oc.y) + abs(pc.z - oc.z)


def ensure_safe(sim):
    """Nudge the hero off any tile adjacent to a live creature.

    Each captured frame advances a game turn; standing next to a live creature
    triggers a turn-based combat that blocks on a fight-panel selection in a
    headless session. Relocating to the nearest creature-free walkable tile
    keeps the recording moving without ever entering blocking combat.
    """
    Coords = sim.gameModule.Coords
    p = sim.player.getCoords()
    creatures = _live_creature_coords(sim)
    if not creatures:
        return

    def adjacent(x, y, z):
        return any(abs(x - cx) + abs(y - cy) <= 1 and z == cz for cx, cy, cz in creatures)

    if not adjacent(p.x, p.y, p.z):
        return
    for radius in range(1, 9):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if abs(dx) + abs(dy) != radius:
                    continue
                nx, ny = p.x + dx, p.y + dy
                cand = Coords(nx, ny, p.z)
                if sim._safeCall(sim.gameMap, "canStep", cand) and not adjacent(nx, ny, p.z):
                    sim.player.setCoords(cand)
                    return


def scene_at(sim, recorder, object_name, caption, approach_tiles=10, stop_distance=2, frames_per_tile=1, pre_step=None):
    """Walk the hero to the named object through real keyboard input, if present.

    Computes a connected walkable path from the hero's *current* tile to a tile
    beside the objective, then walks it one arrow-key press at a time (each press
    is a real input event that steps the hero and advances a turn), capturing a
    frame per tile so the traversal is fully visible. The walk halts
    ``stop_distance`` tiles short of the objective so the hero never ends a turn
    on a (possibly hostile) objective; the caller resolves it. ``pre_step`` lets
    hostile-heavy chapters neutralize threats before each step so a walk never
    ends a turn boxed in by combat. Returns ``True`` if the object was present.
    """
    obj = sim.gameMap.getObjectByName(object_name)
    if obj is None:
        return False
    target = obj.getCoords()
    destination = sim._interactionCoords(target)
    # By default, keep the immediate area clear as the hero walks so a stray
    # creature never traps the turn in the modal fight panel; hostile-heavy
    # chapters pass their own pre_step (freeze the rite, clear the whole field).
    if pre_step is None:
        pre_step = _clear_nearby_hostiles
    driver = _input_driver(sim).refresh()
    path = _path_from_player(sim, destination)
    # Long walks still show the whole journey, but capture only every ``stride``
    # steps so a cross-map trek stays a few seconds of video rather than tens.
    stride = max(1, len(path) // 120)
    _log_progress(
        sim,
        f"walk {object_name}: {len(path)} tiles via keys (stride {stride}) "
        f"-> ({destination.x},{destination.y}) :: {caption}",
    )
    for index, tile in enumerate(path):
        if abs(tile.x - target.x) + abs(tile.y - target.y) <= stop_distance:
            break
        if pre_step is not None:
            pre_step(sim)
            driver.refresh()
        cur = sim.player.getCoords()
        dx = (tile.x > cur.x) - (tile.x < cur.x)
        dy = (tile.y > cur.y) - (tile.y < cur.y)
        if dx == 0 and dy == 0:
            continue
        driver.step(dx, dy)
        sim.pumpEvents(1)
        sim.refreshHandles()
        if index % stride == 0 or index == len(path) - 1:
            recorder.capture(caption=caption, hold=frames_per_tile, advance_turn=False)
        now = sim.player.getCoords()
        if now.x == cur.x and now.y == cur.y:
            # The step did not land (a creature moved into the way); stop walking
            # rather than spin, and let the caller resolve the objective.
            _log_progress(sim, f"blocked at ({cur.x},{cur.y}) heading ({dx},{dy})")
            break
    sim.refreshHandles()
    _log_progress(sim, f"arrived at ({sim.player.getCoords().x},{sim.player.getCoords().y})")
    return True


def _is_fightable(sim, obj):
    return obj is not None and sim._safeCall(obj, "isAlive") is True and (sim._safeCall(obj, "getHpMax") or 0) > 0


def stage_fight(sim, recorder, enemy, caption, fps, rounds_cap=40):
    """Play out a real, visible fight against ``enemy`` in the fight panel.

    Opens the game's fight panel (both combatants, live HP bars) and resolves the
    encounter one round at a time with the player's actual attack interaction —
    the enemy's HP visibly drops each captured frame until it dies. Frames are
    captured with ``advance_turn=False`` so no map turn passes during the fight,
    which is what keeps the enemy from acting and the headless session from
    dropping into the engine's own blocking (nested-event-loop) combat.
    """
    g = sim.gameInstance
    gui = g.getGui()
    panel = g.createObject("fightPanel")
    panel.setEnemies([enemy])
    gui.pushChild(panel)
    sim.pumpEvents(3)
    interactions = panel.interactionsCollection(gui)
    attack = interactions[0] if interactions else None
    beat = max(1, round(0.5 * fps))
    for _ in range(rounds_cap):
        if not sim._safeCall(enemy, "isAlive"):
            break
        hp = sim._safeCall(enemy, "getHp")
        mx = sim._safeCall(enemy, "getHpMax")
        recorder.capture(caption=f"{caption} ({hp}/{mx} HP)", hold=beat, advance_turn=False)
        if attack is not None:
            sim.player.useAction(attack, enemy)
        else:
            try:
                enemy.hurt(20)
            except Exception:  # noqa: BLE001
                break
        sim.pumpEvents(1)
        try:
            sim.player.heal(0)  # keep the hero at full health across the recording
        except Exception:  # noqa: BLE001
            pass
    recorder.capture(caption=f"{caption} - defeated", hold=max(1, round(1.0 * fps)), advance_turn=False)
    try:
        panel.close()
    except Exception:  # noqa: BLE001
        pass
    sim.pumpEvents(2)
    sim.refreshHandles()


def approach_and_fight(sim, recorder, enemy_name, caption, fps, fight_range=9, max_steps=260):
    """Walk the hero toward the live enemy via real key presses, then fight it.

    Greedily steps toward the enemy's *current* tile (it may pursue), clearing
    incidental threats but keeping the target, and halts ``fight_range`` tiles
    short — close enough to read as a confrontation, far enough that no step ends
    a turn adjacent (which would trip the blocking fight panel). Then it stages a
    visible round-by-round fight against that real, fully-statted enemy. Returns
    ``True`` if the enemy was present.
    """
    if sim.gameMap.getObjectByName(enemy_name) is None:
        return False
    driver = _input_driver(sim).refresh()
    stuck = 0
    for _ in range(max_steps):
        enemy = sim.gameMap.getObjectByName(enemy_name)
        if enemy is None:
            break
        p = sim.player.getCoords()
        c = enemy.getCoords()
        if abs(p.x - c.x) + abs(p.y - c.y) <= fight_range:
            break
        _clear_nearby_hostiles(sim, radius=3, keep_names=(enemy_name,))
        driver.refresh()
        dx = (c.x > p.x) - (c.x < p.x)
        dy = (c.y > p.y) - (c.y < p.y)
        if abs(c.x - p.x) >= abs(c.y - p.y) and dx != 0:
            driver.step(dx, 0)
        elif dy != 0:
            driver.step(0, dy)
        else:
            driver.step(dx, 0)
        sim.pumpEvents(1)
        sim.refreshHandles()
        recorder.capture(caption=caption, hold=1, advance_turn=False)
        now = sim.player.getCoords()
        if now.x == p.x and now.y == p.y:
            stuck += 1
            if stuck >= 3:
                break
        else:
            stuck = 0
    enemy = sim.gameMap.getObjectByName(enemy_name)
    if _is_fightable(sim, enemy):
        _log_progress(sim, f"fight {enemy_name}: {sim._safeCall(enemy, 'getHpMax')} HP :: {caption}")
        stage_fight(sim, recorder, enemy, caption, fps)
    return True


def show_panel(sim, recorder, panel_name, caption, hold):
    """Open a GUI panel, capture it for a beat, then close it again."""
    panel = None
    try:
        panel = sim.gameInstance.getGuiHandler().openPanel(panel_name)
        sim.pumpEvents(3)
        recorder.capture(caption=caption, hold=hold)
    finally:
        try:
            if panel is not None:
                panel.close()
                sim.pumpEvents(2)
        except Exception:  # noqa: BLE001 - closing is best-effort for cinematics
            pass


def _open_panel(sim, recorder, panel_name, caption, hold, text=None):
    """Open a panel via the gui handler (the same call the game makes when a
    player opens one), optionally seed a text panel with content, capture it,
    then close it. Best-effort: a panel that fails to open is skipped."""
    panel = None
    try:
        panel = sim.gameInstance.getGuiHandler().openPanel(panel_name)
        if text is not None and panel is not None and hasattr(panel, "setText"):
            try:
                panel.setText(text)
            except Exception:  # noqa: BLE001
                pass
        sim.pumpEvents(3)
        recorder.capture(caption=caption, hold=hold)
    except Exception:  # noqa: BLE001
        pass
    finally:
        try:
            if panel is not None:
                panel.close()
                sim.pumpEvents(2)
        except Exception:  # noqa: BLE001
            pass


def _capture_panel(sim, recorder, panel, caption, hold):
    """Push an already-populated panel, capture it, then close it."""
    try:
        sim.gameInstance.getGui().pushChild(panel)
        sim.pumpEvents(3)
        recorder.capture(caption=caption, hold=hold)
    except Exception:  # noqa: BLE001
        pass
    finally:
        try:
            panel.close()
            sim.pumpEvents(2)
        except Exception:  # noqa: BLE001
            pass


def showcase_hud(sim, recorder, fps):
    """Tour the always-available HUD panels (character / inventory / journal /
    info), each rendering the hero's live state. The contextual panels — trade,
    loot, dialog and the fight screen — are wired to real in-world encounters
    instead (a market building, a fallen foe, an NPC, a battle)."""
    hold = max(1, round(1.6 * fps))
    recorder.capture_card(
        "The Hero's HUD",
        "The panels a player checks anywhere: the character sheet, inventory and quest journal.",
        subtitle="Character - Inventory - Journal",
        hold=max(1, round(2.4 * fps)),
    )
    show_panel(sim, recorder, "characterPanel", "Character sheet: class, race and combat stats", hold)
    show_panel(sim, recorder, "inventoryPanel", "Inventory: weapons, armour and quest items", hold)
    show_panel(sim, recorder, "questPanel", "Quest journal: objectives, rewards and hints", hold)
    _open_panel(
        sim,
        recorder,
        "infoPanel",
        "Info panel: lore and status messages",
        hold,
        text="The dead of Nouraajd do not rest. Every wand, coin and cured soul buys one more night.",
    )


def open_trade_at(sim, recorder, market_object_name, caption, fps):
    """Walk to a market building and open its own market's trade panel.

    Reads the building's real ``market`` object property — the same market the
    building's onEnter would open in play — so the wares on sale are the map's
    actual stock, shown where the market stands."""
    if sim.gameMap.getObjectByName(market_object_name) is None:
        return False
    scene_at(sim, recorder, market_object_name, "Approaching the town market", stop_distance=1)
    market_object = sim.gameMap.getObjectByName(market_object_name)
    market = None
    try:
        market = market_object.getObjectProperty("market")
    except Exception:  # noqa: BLE001
        market = None
    if market is None:
        return False
    trade = sim.gameInstance.createObject("tradePanel")
    trade.setMarket(market)
    _capture_panel(sim, recorder, trade, caption, max(1, round(2.0 * fps)))
    return True


def drive_dialog(sim, recorder, panel, caption, fps, max_steps=4):
    """Play out a dialog interactively by pressing its option number keys.

    The dialog panel selects an option when a digit key is pressed (its own
    ``keyboardEvent``, exactly as a human player picks a line), so injecting
    ``1`` walks the conversation forward state by state — each reply and its new
    options are captured — until an option ends the talk (option count drops to
    zero) or the step budget runs out.
    """
    gui = sim.gameInstance.getGui()
    recorder.capture(caption=caption, hold=max(1, round(2.0 * fps)))
    for _ in range(max_steps):
        try:
            if panel.getOptionCount() <= 0:
                break
        except Exception:  # noqa: BLE001
            break
        # Press the '1' key to choose the first line; the panel advances and
        # rebuilds itself for the next state.
        panel.keyboardEvent(gui, SDL_KEYDOWN, ord("1"))
        sim.pumpEvents(3)
        try:
            if panel.getOptionCount() <= 0:
                break
        except Exception:  # noqa: BLE001
            break
        recorder.capture(caption=caption, hold=max(1, round(1.5 * fps)))


def open_dialog_at(sim, recorder, npc_object_name, dialog_id, caption, fps):
    """Walk to a townsfolk NPC and hold the very conversation its onEnter opens,
    driving the options with real key presses."""
    if sim.gameMap.getObjectByName(npc_object_name) is None:
        return False
    scene_at(sim, recorder, npc_object_name, "Approaching the townsfolk", stop_distance=1)
    g = sim.gameInstance
    dialog = g.createObject(dialog_id)
    if dialog is None:
        return False
    panel = g.createObject("dialogPanel")
    panel.setDialog(dialog)
    g.getGui().pushChild(panel)
    try:
        panel.reload()
        sim.pumpEvents(3)
        drive_dialog(sim, recorder, panel, caption, fps)
    finally:
        try:
            panel.close()
            sim.pumpEvents(2)
        except Exception:  # noqa: BLE001
            pass
    return True


def open_loot(sim, recorder, creature, item_ids, caption, fps):
    """Open a loot panel for a fallen foe's spoils, at the kill."""
    g = sim.gameInstance
    items = set()
    for item_id in item_ids:
        item = g.createObject(item_id)
        if item is not None:
            items.add(item)
    if not items:
        return False
    loot = g.createObject("lootPanel")
    try:
        if creature is not None:
            loot.setCreature(creature)
        loot.setItems(items)
    except Exception:  # noqa: BLE001
        return False
    _capture_panel(sim, recorder, loot, caption, max(1, round(2.0 * fps)))
    return True


# ---------------------------------------------------------------------------
# Campaign driver helpers
# ---------------------------------------------------------------------------
def _chapter_helpers(sim, recorder, fps):
    """Return the shared cadence values and beat/checkpoint helpers used by
    every chapter solver, all bound to the live simulation handles."""
    beat = max(1, round(0.9 * fps))  # ~0.9s hold for interaction beats
    panel_beat = max(1, round(1.4 * fps))  # ~1.4s hold for panels
    finale = max(1, round(2.6 * fps))  # ~2.6s hold for chapter openers/closers

    def fortify():
        # Each captured frame advances a game turn, so keep the hero at full
        # health over the recording (heal(0) restores to max, which reads
        # naturally in the HP bar).
        try:
            sim.player.heal(0)
        except Exception:  # noqa: BLE001 - healing is best-effort
            pass

    def checkpoint(caption, hold=beat, advance_turn=True):
        sim.refreshHandles()
        fortify()
        # Advancing one (combat-safe) turn lets map changes such as removed
        # quest objects show up in the rendered frame.
        recorder.capture(caption=caption, hold=hold, advance_turn=advance_turn)
        _log_progress(sim, f"beat: {caption}")

    return beat, panel_beat, finale, fortify, checkpoint


def _step_on_tile(sim, object_name, pump=5):
    """Place the hero directly on a named object's tile and pump the loop.

    Start-event and cage tiles are not walkable targets for the cinematic
    pathfinder, so campaign chapters trigger them the way the gameplay tests
    do: teleport onto the tile and let its onEnter handler fire. Returns
    ``True`` when the object existed.
    """
    obj = sim.gameMap.getObjectByName(object_name)
    if obj is None:
        return False
    c = obj.getCoords()
    sim.player.setCoords(sim.gameModule.Coords(c.x, c.y, c.z))
    sim.pumpEvents(pump)
    sim.refreshHandles()
    return True


def _clear_nearby_hostiles(sim, radius=3, keep_names=()):
    """Remove live creatures within ``radius`` tiles of the hero.

    The hero moves through real key presses, and each press advances a turn; if a
    live enemy is adjacent when that turn resolves, the engine opens a modal fight
    panel that spins its own nested event loop awaiting a click — which a
    single-threaded headless driver can never deliver, so it hangs. Sweeping the
    immediate area before each step keeps the walk clear of that trap without
    touching distant objectives. Returns the number removed.
    """
    sim.refreshHandles()
    player = sim.player
    pc = player.getCoords()
    player_name = sim._safeCall(player, "getName")
    keep = set(keep_names) | ({player_name} if player_name else set())
    victims = []
    for obj in sim.gameMap.getObjects():
        name = sim._safeCall(obj, "getName")
        if not name or name in keep or not sim._safeCall(obj, "isAlive"):
            continue
        c = obj.getCoords()
        if c.z == pc.z and abs(c.x - pc.x) + abs(c.y - pc.y) <= radius:
            victims.append(name)
    for name in victims:
        sim.gameMap.removeObjectByName(name)
    if victims:
        sim.refreshHandles()
    return len(victims)


def _nearest_live_enemy_name(sim):
    """Return the name of the nearest live non-player creature on the hero's
    level, or ``None``."""
    sim.refreshHandles()
    p = sim.player.getCoords()
    player_name = sim._safeCall(sim.player, "getName")
    best_name = None
    best_dist = None
    for obj in sim.gameMap.getObjects():
        name = sim._safeCall(obj, "getName")
        if not name or name == player_name or not sim._safeCall(obj, "isAlive"):
            continue
        c = obj.getCoords()
        if c.z != p.z:
            continue
        d = abs(c.x - p.x) + abs(c.y - p.y)
        if best_dist is None or d < best_dist:
            best_dist = d
            best_name = name
    return best_name


def _clear_live_hostiles(sim, keep_names=()):
    """Remove every live creature except the hero (and any kept objectives).

    Each captured movement frame advances a real turn, so a live enemy left on
    the field can end a turn adjacent to the hero and drop the headless session
    into a blocking fight panel. Hostile-heavy chapters (the ritual sanctum, the
    besieged gatehouse) clear the field before the cinematic walk so movement
    never trips combat. Returns the number removed.
    """
    sim.refreshHandles()
    player_name = sim._safeCall(sim.player, "getName")
    keep = set(keep_names) | ({player_name} if player_name else set())
    victims = []
    for obj in sim.gameMap.getObjects():
        name = sim._safeCall(obj, "getName")
        if name and name not in keep and sim._safeCall(obj, "isAlive"):
            victims.append(name)
    for name in victims:
        sim.gameMap.removeObjectByName(name)
    sim.refreshHandles()
    return len(victims)


def _settle_transition(sim, max_pumps=90):
    """Pump the loop until the scene manager finishes any pending map change.

    Scenario completion asks the engine to change maps asynchronously; the
    scene manager applies it over the next event-loop iterations. Wait until it
    returns to ``Idle`` (or immediately, for a terminal scenario that never
    started a transition), then re-acquire the map/player handles.
    """
    scene = sim.gameInstance.getSceneManager()
    for _ in range(max_pumps):
        if scene.getTransitionStateName() == "Idle":
            break
        sim.pumpEvents(1)
    sim.refreshHandles()
    return sim.gameInstance.getMap().mapName


# ---------------------------------------------------------------------------
# Chapter storyboards
# ---------------------------------------------------------------------------
def chapter_nouraajd(sim, recorder, fps, close_transition=True):
    """Chapter I: the full Nouraajd quest chain. When ``close_transition`` is
    set (campaign mode) it ends by cleansing the cave, which routes the
    campaign on to the ritual chapel; otherwise it closes on the finished
    journal (legacy single-map render)."""
    game = sim.gameModule
    game_map = sim.gameMap
    player = sim.player
    g = sim.gameInstance

    beat = max(1, round(0.9 * fps))  # ~0.9s hold for interaction beats
    panel_beat = max(1, round(1.4 * fps))  # ~1.4s hold for panels
    finale = max(1, round(2.6 * fps))  # ~2.6s hold for the finale

    def checkpoint(caption, hold=beat):
        sim.refreshHandles()
        fortify()
        # Advance one (combat-safe) turn so map changes such as removed quest
        # objects are reflected in the rendered frame.
        recorder.capture(caption=caption, hold=hold, advance_turn=True)
        _log_progress(sim, f"beat: {caption}")

    def create(type_id):
        return g.createObject(type_id)

    def fortify():
        # Each captured frame advances a game turn, so keep the hero at full
        # health over the course of the recording (heal(0) restores to max,
        # which reads naturally in the HP bar).
        try:
            player.heal(0)
        except Exception:  # noqa: BLE001 - healing is best-effort
            pass

    # --- Opening: establish the hero and the town -------------------------
    fortify()
    recorder.capture(caption="A ruined town awaits", hold=finale)
    show_panel(sim, recorder, "characterPanel", "The hero: a Warrior of Nouraajd", panel_beat)

    # The authored StartEvent hands the player Sergeant Rolf's letter.
    start_events = [
        obj for obj in game_map.getObjects() if obj.getTypeId() == "StartEvent" or obj.getType() == "StartEvent"
    ]
    if start_events:
        # The StartEvent tile itself is not walkable, so place the hero on it
        # directly to trigger the letter grant rather than pathfinding into it.
        sc = start_events[0].getCoords()
        sim.player.setCoords(sim.gameModule.Coords(sc.x, sc.y, sc.z))
        sim.pumpEvents(5)
        recorder.capture(caption="Sergeant Rolf's last request reaches you", hold=beat)
    checkpoint("Quest: recover the skull of Sergeant Rolf")
    show_panel(sim, recorder, "questPanel", "Quest log: Rolf's plea is now active", panel_beat)

    # --- The town market: real trade panel wired to the market building ----
    open_trade_at(sim, recorder, "market1", "The town market: buy and sell the map's wares", fps)

    # --- Rolf: recover the skull from the cave ----------------------------
    scene_at(sim, recorder, "cave1", "Descending into the haunted cave")
    if game_map.getObjectByName("cave1") is not None:
        game_map.removeObjectByName("cave1")
    player.checkQuests()
    checkpoint("Rolf's skull recovered - the townsfolk are relieved")
    show_panel(sim, recorder, "inventoryPanel", "Inventory: the skull of Rolf is yours", panel_beat)

    # --- Gooby: the main quest (a real, on-screen fight) -----------------
    approach_and_fight(sim, recorder, "gooby1", "Tracking the beast Gooby", fps)
    if game_map.getObjectByName("gooby1") is not None:
        game_map.removeObjectByName("gooby1")
    player.checkQuests()
    checkpoint("Gooby slain - 200 gold from grateful townsfolk")
    show_panel(sim, recorder, "questPanel", "Quest log: the main path opens", panel_beat)

    # --- Beren's chain: visit the Town Hall NPC, take the letter ----------
    open_dialog_at(sim, recorder, "nouraajdTownHall", "townHallDialog", "Town Hall: a letter for Father Beren", fps)
    town_hall = create("townHallDialog")
    town_hall.give_letter()
    checkpoint("The Town Hall entrusts a letter for Father Beren")

    beren = create("berenDialog")
    beren.deliver_letter()
    player.checkQuests()
    sim.pumpEvents(5)
    checkpoint("Letter delivered - Beren teaches you to craft scrolls")

    scene_at(sim, recorder, "catacombs", "Into the catacombs for the holy relic")
    if game_map.getObjectByName("catacombs") is not None:
        game_map.removeObjectByName("catacombs")
    sim.refreshHandles()
    checkpoint("The holy relic is recovered")

    beren.return_relic()
    player.checkQuests()
    sim.pumpEvents(5)
    checkpoint("Relic returned - greater potions unlocked")
    show_panel(sim, recorder, "questPanel", "Quest log: cleanse the infested cave", panel_beat)

    # --- OctoBogz contract: cleanse the second cave -----------------------
    travelers = create("dialog")
    travelers.accept_quest()
    checkpoint("Travelers offer a contract: clear the OctoBogz")

    if scene_at(sim, recorder, "cave2", "Hunting the OctoBogz brood"):
        if game_map.getObjectByName("cave2") is not None:
            game_map.removeObjectByName("cave2")
    player.checkQuests()
    checkpoint("OctoBogz cleared - 1000 gold and a ShadowBlade")
    show_panel(sim, recorder, "inventoryPanel", "Inventory: a ShadowBlade joins your arsenal", panel_beat)

    # --- Victor: the courtyard cult --------------------------------------
    create("tavernDialog1").asked_about_girl()
    tavern = create("tavernDialog2")
    tavern.talked_to_victor()
    checkpoint("In the tavern: Victor's tale leads to a cult")

    town_hall.spawn_cultists()
    sim.refreshHandles()
    checkpoint("Cultists ambush the courtyard - defend Victor")
    # Fight the cult leader head-on; incidental cultists are cleared as the hero
    # closes so the approach never stalls in the packed melee.
    approach_and_fight(sim, recorder, "cultLeaderQuest", "Duel with the cult leader", fps)
    leader = game_map.getObjectByName("cultLeaderQuest")
    if leader is not None:
        game_map.removeObjectByName(leader.getName())
    player.checkQuests()
    sim.pumpEvents(5)
    checkpoint("Cult leader defeated - Victor is saved (good end)")
    show_panel(sim, recorder, "questPanel", "Quest log: Victor's fate resolved", panel_beat)

    # --- The amulet: a final errand --------------------------------------
    create("questDialog").start_amulet_quest()
    sim.refreshHandles()
    checkpoint("A final quest: recover the precious amulet")
    approach_and_fight(sim, recorder, "amuletGoblin", "Chasing the amulet thief", fps)
    # The fallen thief yields the amulet - shown in a real loot panel at the kill.
    goblin = game_map.getObjectByName("amuletGoblin")
    open_loot(sim, recorder, goblin, ["preciousAmulet"], "Loot: the stolen amulet is recovered", fps)
    if goblin is not None:
        game_map.removeObjectByName("amuletGoblin")
    player.addItem("preciousAmulet")
    create("questReturnDialog").complete_amulet_quest()
    player.checkQuests()
    sim.pumpEvents(5)
    checkpoint("The amulet is returned - every Nouraajd quest complete")

    # --- HUD tour: the always-available panels with the hero fully kitted out --
    showcase_hud(sim, recorder, fps)

    if close_transition:
        # --- Chapter close: cleanse the cave, which routes on to the ritual --
        sim.refreshHandles()
        beren.finish_cleanse()
        sim.pumpEvents(3)
        _log_progress(sim, "chapter close: finish_cleanse -> ritual")
    else:
        # --- Legacy single-map finale: show the completed journal -----------
        show_panel(sim, recorder, "questPanel", "The Fall of Nouraajd - all quests completed", finale)
        recorder.capture(caption="Fall of Nouraajd", hold=finale)


def chapter_ritual(sim, recorder, fps):
    """Chapter II: shatter the ritual's anchors, fell its leader, and free the
    captive soul (the good ending), which routes the campaign on to the siege."""
    beat, panel_beat, finale, fortify, checkpoint = _chapter_helpers(sim, recorder, fps)
    sim.refreshHandles()
    fortify()

    def freeze(s):
        # Every anchor's onDestroy trigger re-arms the rite (start_ritual) and
        # spawns a fresh wave, and the sanctum hazard tiles summon more while the
        # rite is active. Re-assert the frozen, cleared state before each turn so
        # the cinematic never ends a turn next to a live enemy (which hangs the
        # headless fight panel). leader_spawned blocks the pursuing Ritual Leader.
        s.gameMap.setBoolProperty("ritual_active", False)
        s.gameMap.setBoolProperty("anchors_destroyed", True)
        s.gameMap.setBoolProperty("leader_spawned", True)
        _clear_live_hostiles(s, keep_names=("ritualCaptive",))

    def safe_beat(caption, hold=beat):
        freeze(sim)
        checkpoint(caption, hold=hold)

    freeze(sim)
    recorder.capture(caption="The chapel pulses with a soul-binding rite", hold=finale, advance_turn=True)

    for anchor, label in (
        ("anchorNorth", "the north anchor"),
        ("anchorCrypt", "the crypt anchor"),
        ("anchorSanctum", "the sanctum anchor"),
    ):
        if scene_at(sim, recorder, anchor, f"Shatter {label}", approach_tiles=6, pre_step=freeze):
            if sim.gameMap.getObjectByName(anchor) is not None:
                sim.gameMap.removeObjectByName(anchor)
            safe_beat(f"{label.capitalize()} shatters")

    # Let the Ritual Leader descend (one turn with the rite briefly re-armed, but
    # anchors_destroyed keeps the waves suppressed), then duel it on-screen.
    sim.gameMap.setBoolProperty("anchors_destroyed", True)
    sim.gameMap.setBoolProperty("leader_spawned", False)
    sim.gameMap.setBoolProperty("ritual_active", True)
    _input_driver(sim).refresh().key(SDLK_UP)
    sim.pumpEvents(2)
    sim.refreshHandles()
    sim.gameMap.setBoolProperty("ritual_active", False)
    if _is_fightable(sim, sim.gameMap.getObjectByName("ritualLeader")):
        approach_and_fight(sim, recorder, "ritualLeader", "Duel with the Ritual Leader", fps)
        if sim.gameMap.getObjectByName("ritualLeader") is not None:
            sim.gameMap.removeObjectByName("ritualLeader")
    sim.gameMap.setBoolProperty("leader_defeated", True)
    safe_beat("The Ritual Leader is cut down - the anchors lie broken")

    scene_at(sim, recorder, "ritualCaptive", "Free the soul held in the stained glass", pre_step=freeze)
    freeze(sim)
    captured = sim.gameInstance.createObject("capturedSoulDialog")
    captured.free_captive()
    sim.pumpEvents(3)
    checkpoint("The captive soul is freed - the good ending", hold=finale)


def chapter_siege(sim, recorder, fps):
    """Chapter III (finale): seal every breach with a charged mage-wand, which
    completes the campaign."""
    beat, panel_beat, finale, fortify, checkpoint = _chapter_helpers(sim, recorder, fps)
    sim.refreshHandles()
    fortify()
    def clear(s):
        # The gatehouse keeps spawning attackers each turn (and an onTurn trigger
        # re-enables disabled gates), so clear the field before every frame's turn
        # to keep the walk between breaches combat-safe.
        _clear_live_hostiles(s)

    def safe_beat(caption, hold=beat):
        clear(sim)
        checkpoint(caption, hold=hold)

    clear(sim)
    recorder.capture(caption="The last gatehouse stands besieged", hold=finale, advance_turn=True)
    show_panel(sim, recorder, "inventoryPanel", "Charged mage-wands to seal the breaches", panel_beat)

    # Let the assault spawn, then cut down one attacker on-screen before sealing.
    for _ in range(8):
        if _nearest_live_enemy_name(sim) is not None:
            break
        sim.gameMap.move()
        sim.pumpEvents(1)
        sim.refreshHandles()
    foe = _nearest_live_enemy_name(sim)
    if foe is not None:
        approach_and_fight(sim, recorder, foe, "Cut down a siege attacker", fps)
    clear(sim)

    for index, name in enumerate(("spawnPoint1", "spawnPoint2", "spawnPoint3", "spawnPoint4"), start=1):
        if sim.gameMap.getObjectByName(name) is None:
            continue
        scene_at(sim, recorder, name, f"Seal breach {index} with a charged wand", approach_tiles=5, pre_step=clear)
        gate = sim.gameMap.getObjectByName(name)
        if gate is not None:
            # Sealing a breach both destroys it and stops it spawning again.
            gate.setBoolProperty("destroyed", True)
            gate.setBoolProperty("enabled", False)
        safe_beat(f"Breach {index} sealed")

    clear(sim)
    sim.player.checkQuests()
    sim.pumpEvents(3)
    checkpoint("The last breach is sealed - Nouraajd survives the night", hold=finale)


def chapter_hearthfall(sim, recorder, fps):
    """Warden's Road I: break the occupation of Hearthfall and report victory,
    routing on to the Gravemoor."""
    beat, panel_beat, finale, fortify, checkpoint = _chapter_helpers(sim, recorder, fps)
    sim.refreshHandles()
    fortify()
    recorder.capture(caption="An exile returns to occupied Hearthfall", hold=finale, advance_turn=True)
    _step_on_tile(sim, "hearthfallStart")
    _clear_live_hostiles(sim, keep_names=("watchCaptain",))

    scene_at(sim, recorder, "watchCaptain", "Break Watch-Captain Osric's grip on the square")
    if sim.gameMap.getObjectByName("watchCaptain") is not None:
        sim.gameMap.removeObjectByName("watchCaptain")
    checkpoint("Watch-Captain Osric is defeated")

    sim.gameInstance.createObject("elderDialog").report_victory()
    sim.pumpEvents(3)
    checkpoint("Hearthfall is free - Elder Maren points north", hold=finale)


def chapter_gravemoor(sim, recorder, fps, branch="spared"):
    """Warden's Road II: free the caged loyalists, then judge the quartermaster.
    ``branch`` selects mercy (``spared``) or wrath (``executed``)."""
    beat, panel_beat, finale, fortify, checkpoint = _chapter_helpers(sim, recorder, fps)
    sim.refreshHandles()
    fortify()
    recorder.capture(caption="The moor hides three barrow-cages", hold=finale, advance_turn=True)
    _step_on_tile(sim, "gravemoorStart")
    _clear_live_hostiles(sim)

    for cage, label in (
        ("loyalistCageWest", "the western cage"),
        ("loyalistCageEast", "the eastern cage"),
        ("loyalistCageNorth", "the northern cage"),
    ):
        if scene_at(sim, recorder, cage, f"Free the loyalists in {label}"):
            _step_on_tile(sim, cage)
            checkpoint(f"Loyalists freed from {label}")

    voss = sim.gameInstance.createObject("vossDialog")
    if branch == "executed":
        voss.execute_voss()
        caption = "Quartermaster Voss is executed - the wrath road"
    else:
        voss.spare_voss()
        caption = "Quartermaster Voss is spared - the mercy road"
    sim.pumpEvents(3)
    checkpoint(caption, hold=finale)


def chapter_usurpergate(sim, recorder, fps):
    """Warden's Road III (finale): fell the Usurper and take the obsidian
    throne, completing the campaign."""
    beat, panel_beat, finale, fortify, checkpoint = _chapter_helpers(sim, recorder, fps)
    sim.refreshHandles()
    fortify()
    recorder.capture(caption="One curtain wall stands between you and the throne", hold=finale, advance_turn=True)
    _step_on_tile(sim, "usurpergateStart")
    _clear_live_hostiles(sim, keep_names=("theUsurper",))

    scene_at(sim, recorder, "theUsurper", "Fell the Usurper before the obsidian throne")
    if sim.gameMap.getObjectByName("theUsurper") is not None:
        sim.gameMap.removeObjectByName("theUsurper")
    checkpoint("The Usurper falls")

    scene_at(sim, recorder, "obsidianThrone", "The obsidian throne waits")
    _step_on_tile(sim, "obsidianThrone")
    checkpoint("The throne is taken - the marches are yours", hold=finale)


CHAPTER_SOLVERS = {
    "nouraajd": lambda sim, recorder, fps, branch: chapter_nouraajd(sim, recorder, fps, close_transition=True),
    "ritual": lambda sim, recorder, fps, branch: chapter_ritual(sim, recorder, fps),
    "siege": lambda sim, recorder, fps, branch: chapter_siege(sim, recorder, fps),
    "hearthfall": lambda sim, recorder, fps, branch: chapter_hearthfall(sim, recorder, fps),
    "gravemoor": lambda sim, recorder, fps, branch: chapter_gravemoor(sim, recorder, fps, branch),
    "usurpergate": lambda sim, recorder, fps, branch: chapter_usurpergate(sim, recorder, fps),
}


# ---------------------------------------------------------------------------
# Campaign driver
# ---------------------------------------------------------------------------
def run_campaign(sim, recorder, fps, manifest, store, branch):
    """Drive an entire multi-scenario campaign, chapter by chapter.

    Each scenario opens with a manifest-driven title card, then the map's
    chapter solver plays it to its outcome; the map scripts report that outcome
    through ``campaign.complete_scenario``, which asynchronously routes to the
    next map. We wait for that transition, re-acquire handles, and repeat until
    the campaign reports finished.
    """
    finale = max(1, round(2.6 * fps))
    recorder.capture_card(
        manifest["title"],
        manifest.get("description", ""),
        subtitle="A multi-map campaign",
        hold=finale,
    )

    guard = 0
    while True:
        scenario_id = store.scenario()
        scenario = manifest["scenarios"][scenario_id]
        map_name = sim.gameMap.mapName
        recorder.capture_card(scenario["title"], scenario.get("briefing", ""), subtitle=f"Map: {map_name}")
        _log_progress(sim, f"chapter start: {scenario_id} ({map_name})")

        solver = CHAPTER_SOLVERS.get(map_name)
        if solver is None:
            raise SystemExit(f"No chapter solver for campaign map '{map_name}'.")
        solver(sim, recorder, fps, branch)

        _settle_transition(sim)
        guard += 1
        if store.finished() or guard > len(manifest["scenarios"]) + 1:
            break

    recorder.capture_card(
        "Campaign complete",
        manifest.get("completionText", ""),
        subtitle=manifest["title"],
        hold=finale,
    )


def summarize_campaign(sim, store):
    """Return a short report proving the campaign actually reached its end."""
    report = {
        "campaign": store.campaign_id(),
        "scenario": store.scenario(),
        "finished": store.finished(),
        "history": store.history(),
        "final_map": sim.gameInstance.getMap().mapName,
    }
    inventory = [item.get("name") for item in sim.readInventory()]
    return report, inventory


def summarize_single_map(sim):
    """Legacy single-map report proving the Nouraajd chain progressed."""
    state = sim.readMapState(
        include_objects=False,
        bool_flags=["completed_rolf", "completed_gooby", "OCTOBOGZ_SLAIN", "VICTOR_GOOD_END"],
        string_properties=["quest_state_rolf", "quest_state_main", "quest_state_beren_chain", "quest_state_victor"],
    )
    inventory = [item.get("name") for item in sim.readInventory()]
    return state, inventory


def _save_stills(args, recorder):
    first_png = Path(args.output).with_name(Path(args.output).stem + "-first.png")
    last_png = Path(args.output).with_name(Path(args.output).stem + "-last.png")
    if recorder.first_frame is not None:
        recorder.first_frame.save(first_png)
    if recorder.last_frame is not None:
        recorder.last_frame.save(last_png)


def main():
    parser = argparse.ArgumentParser(description="Generate a Fall of Nouraajd campaign walkthrough video.")
    parser.add_argument("--output", default=str(REPO_ROOT / "screenshots" / "nouraajd-walkthrough.mp4"))
    parser.add_argument(
        "--campaign",
        default="fallOfNouraajd",
        help="Campaign id under res/campaigns/ to drive end to end (default: fallOfNouraajd).",
    )
    parser.add_argument(
        "--branch",
        default="spared",
        choices=["spared", "executed"],
        help="Branch to take at a campaign fork (e.g. Warden's Road judgment). Default: spared.",
    )
    parser.add_argument(
        "--single-map",
        action="store_true",
        help="Render only the standalone Nouraajd storyboard (legacy one-map mode).",
    )
    parser.add_argument("--map", default="nouraajd", help="Map for --single-map mode.")
    parser.add_argument("--player", default="Warrior")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--scale", default="1280x720", help="WIDTHxHEIGHT, or 'native' for 1920x1080.")
    parser.add_argument("--no-captions", action="store_true")
    args = parser.parse_args()

    if args.scale.lower() in ("native", "full", "1920x1080"):
        size = (1920, 1080)
    else:
        w, _, h = args.scale.lower().partition("x")
        size = (int(w), int(h))

    # Resolve the output path before bootstrap changes the working directory to
    # the build dir, so a relative --output is written where the user expects.
    args.output = str(Path(args.output).resolve())

    _reexec_under_xvfb_if_needed()
    _bootstrap_paths()
    game = _load_game_module()
    import game_simulation

    _suppress_blocking_popups(game)

    if args.single_map:
        sim = game_simulation.GameSimulation.startGame(game, args.map, args.player, load_gui=True)
        recorder = FrameRecorder(sim, args.output, args.fps, size=size, captions=not args.no_captions)
        try:
            chapter_nouraajd(sim, recorder, args.fps, close_transition=False)
        finally:
            output_path = recorder.close()
        _save_stills(args, recorder)
        state, inventory = summarize_single_map(sim)
        size_bytes = output_path.stat().st_size
        duration = recorder.frame_count / float(args.fps)
        print(f"Wrote {output_path} ({size_bytes/1_000_000:.2f} MB, {recorder.frame_count} frames, {duration:.1f}s)")
        print(f"Quest flags : {state.get('boolFlags')}")
        print(f"Quest states: {state.get('stringProperties')}")
        print(f"Inventory   : {sorted(set(inventory))}")
        if size_bytes < 50_000:
            raise SystemExit("Generated video is suspiciously small; aborting.")
        return

    import campaign as campaign_module

    manifest = campaign_module.get_manifest(args.campaign)
    g = game.CGameLoader.loadGame()
    game.CGameLoader.loadGui(g)
    store = campaign_module.start(g, args.campaign, args.player)
    first_map = manifest["scenarios"][manifest["start"]]["map"]
    sim = game_simulation.GameSimulation(game, g, first_map, args.player)
    sim.pumpEvents(5)
    recorder = FrameRecorder(sim, args.output, args.fps, size=size, captions=not args.no_captions)

    try:
        run_campaign(sim, recorder, args.fps, manifest, store, args.branch)
    finally:
        output_path = recorder.close()

    _save_stills(args, recorder)

    report, inventory = summarize_campaign(sim, store)
    size_bytes = output_path.stat().st_size
    duration = recorder.frame_count / float(args.fps)
    print(f"Wrote {output_path} ({size_bytes/1_000_000:.2f} MB, {recorder.frame_count} frames, {duration:.1f}s)")
    print(f"Campaign    : {report['campaign']} (finished={report['finished']})")
    print(f"Final map   : {report['final_map']}")
    print(f"History     : {report['history']}")
    print(f"Inventory   : {sorted(set(inventory))}")
    if not report["finished"]:
        raise SystemExit(f"Campaign '{report['campaign']}' did not reach completion; aborting.")
    if size_bytes < 50_000:
        raise SystemExit("Generated video is suspiciously small; aborting.")


if __name__ == "__main__":
    main()
