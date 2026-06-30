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
        self._font = self._load_font()
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
    def _load_font():
        from PIL import ImageFont

        for candidate in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ):
            try:
                return ImageFont.truetype(candidate, 30)
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

    def close(self):
        self._writer.close()
        return self.output_path


# ---------------------------------------------------------------------------
# Movement helpers
# ---------------------------------------------------------------------------
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


def _approach_path(sim, destination, distance):
    """Return a connected tile path ending at ``destination``, ~``distance`` long.

    Breadth-first search outward from the objective over walkable neighbours,
    tracking parents, then reconstruct the path from the farthest tile reached
    (capped at ``distance`` rings) back to the objective. The result is a list of
    ``Coords`` from a staging tile to ``destination``, every tile walkable and
    connected, so the hero can glide along it without invoking the engine's
    expensive per-turn pathfinding.
    """
    Coords = sim.gameModule.Coords
    can_step = sim.gameMap.canStep
    start = (int(destination.x), int(destination.y), int(destination.z))
    parent = {start: None}
    frontier = [start]
    farthest = start
    rings = 0
    while frontier and rings < distance:
        nxt = []
        for node in frontier:
            x, y, z = node
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cand = (x + dx, y + dy, z)
                if cand in parent:
                    continue
                if can_step(Coords(*cand)):
                    parent[cand] = node
                    nxt.append(cand)
                    farthest = cand
        if not nxt:
            break
        frontier = nxt
        rings += 1

    # Walk parents from the farthest staging tile back to the objective; this
    # yields the path already ordered staging -> destination.
    path = []
    node = farthest
    while node is not None:
        path.append(Coords(node[0], node[1], node[2]))
        node = parent[node]
    return path


def scene_at(sim, recorder, object_name, caption, approach_tiles=10, stop_distance=2, frames_per_tile=1):
    """Stage a short cinematic approach to the named object, if it exists.

    Computes a connected path a few tiles long ending near the objective, then
    glides the hero along it with ``setCoords`` (which, unlike engine
    pathfinding, is instant), capturing a frame per tile. The walk halts
    ``stop_distance`` tiles short of the objective so the hero never ends a turn
    adjacent to a (possibly hostile) objective and trips blocking combat; the
    caller resolves the objective by removing it. Returns ``True`` if the object
    was present.
    """
    obj = sim.gameMap.getObjectByName(object_name)
    if obj is None:
        return False
    target = obj.getCoords()
    destination = sim._interactionCoords(target)
    path = _approach_path(sim, destination, approach_tiles)
    _log_progress(sim, f"approach {object_name}: {len(path)} tiles -> ({destination.x},{destination.y}) :: {caption}")
    for coords in path:
        if abs(coords.x - target.x) + abs(coords.y - target.y) <= stop_distance:
            break
        sim.player.setCoords(coords)
        recorder.capture(caption=caption, hold=frames_per_tile, advance_turn=True)
    sim.refreshHandles()
    _log_progress(sim, f"arrived at ({sim.player.getCoords().x},{sim.player.getCoords().y})")
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


# ---------------------------------------------------------------------------
# The storyboard
# ---------------------------------------------------------------------------
def run_walkthrough(sim, recorder, fps):
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
    recorder.capture(caption="Fall of Nouraajd - a ruined town awaits", hold=finale)
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

    # --- Rolf: recover the skull from the cave ----------------------------
    scene_at(sim, recorder, "cave1", "Descending into the haunted cave")
    if game_map.getObjectByName("cave1") is not None:
        game_map.removeObjectByName("cave1")
    player.checkQuests()
    checkpoint("Rolf's skull recovered - the townsfolk are relieved")
    show_panel(sim, recorder, "inventoryPanel", "Inventory: the skull of Rolf is yours", panel_beat)

    # --- Gooby: the main quest -------------------------------------------
    if scene_at(sim, recorder, "gooby1", "Tracking the beast Gooby"):
        gooby = game_map.getObjectByName("gooby1")
        if gooby is not None:
            game_map.removeObjectByName(gooby.getName())
    player.checkQuests()
    checkpoint("Gooby slain - 200 gold from grateful townsfolk")
    show_panel(sim, recorder, "questPanel", "Quest log: the main path opens", panel_beat)

    # --- Beren's chain: deliver the letter, fetch and return the relic ----
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
    leader = game_map.getObjectByName("cultLeaderQuest")
    # Do not walk into the cultist swarm (a packed melee would trip blocking
    # combat); the encounter is shown via the quest log and resolved directly.
    checkpoint("Cultists ambush the courtyard - defend Victor")
    if leader is not None and game_map.getObjectByName(leader.getName()) is not None:
        game_map.removeObjectByName(leader.getName())
    player.checkQuests()
    sim.pumpEvents(5)
    checkpoint("Cult leader defeated - Victor is saved (good end)")
    show_panel(sim, recorder, "questPanel", "Quest log: Victor's fate resolved", panel_beat)

    # --- The amulet: a final errand --------------------------------------
    create("questDialog").start_amulet_quest()
    sim.refreshHandles()
    checkpoint("A final quest: recover the precious amulet")
    if scene_at(sim, recorder, "amuletGoblin", "Chasing the amulet thief"):
        goblin = game_map.getObjectByName("amuletGoblin")
        if goblin is not None:
            game_map.removeObjectByName(goblin.getName())
    player.addItem("preciousAmulet")
    create("questReturnDialog").complete_amulet_quest()
    player.checkQuests()
    sim.pumpEvents(5)
    checkpoint("The amulet is returned - every quest complete")

    # --- Finale: show the completed journal -------------------------------
    show_panel(sim, recorder, "questPanel", "The Fall of Nouraajd - all quests completed", finale)
    recorder.capture(caption="Fall of Nouraajd", hold=finale)


def summarize(sim):
    """Return a short report proving the gameplay actually progressed."""
    state = sim.readMapState(
        include_objects=False,
        bool_flags=["completed_rolf", "completed_gooby", "OCTOBOGZ_SLAIN", "VICTOR_GOOD_END"],
        string_properties=["quest_state_rolf", "quest_state_main", "quest_state_beren_chain", "quest_state_victor"],
    )
    inventory = [item.get("name") for item in sim.readInventory()]
    return state, inventory


def main():
    parser = argparse.ArgumentParser(description="Generate a Nouraajd walkthrough video.")
    parser.add_argument("--output", default=str(REPO_ROOT / "screenshots" / "nouraajd-walkthrough.mp4"))
    parser.add_argument("--map", default="nouraajd")
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
    sim = game_simulation.GameSimulation.startGame(game, args.map, args.player, load_gui=True)
    recorder = FrameRecorder(sim, args.output, args.fps, size=size, captions=not args.no_captions)

    try:
        run_walkthrough(sim, recorder, args.fps)
    finally:
        output_path = recorder.close()

    # Write first/last stills for quick human inspection.
    first_png = Path(args.output).with_name(Path(args.output).stem + "-first.png")
    last_png = Path(args.output).with_name(Path(args.output).stem + "-last.png")
    if recorder.first_frame is not None:
        recorder.first_frame.save(first_png)
    if recorder.last_frame is not None:
        recorder.last_frame.save(last_png)

    state, inventory = summarize(sim)
    size_bytes = output_path.stat().st_size
    duration = recorder.frame_count / float(args.fps)
    print(f"Wrote {output_path} ({size_bytes/1_000_000:.2f} MB, {recorder.frame_count} frames, {duration:.1f}s)")
    print(f"Quest flags : {state.get('boolFlags')}")
    print(f"Quest states: {state.get('stringProperties')}")
    print(f"Inventory   : {sorted(set(inventory))}")
    if size_bytes < 50_000:
        raise SystemExit("Generated video is suspiciously small; aborting.")


if __name__ == "__main__":
    main()
