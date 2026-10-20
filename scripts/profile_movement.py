#!/usr/bin/env python3
# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in real-input movement profile; automatically uses an isolated Xvfb display on Linux."""

import argparse
import ctypes
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time


class SdlKeysym(ctypes.Structure):
    _fields_ = [
        ("scancode", ctypes.c_int),
        ("sym", ctypes.c_int),
        ("mod", ctypes.c_uint16),
        ("unused", ctypes.c_uint32),
    ]


class SdlKeyboardEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("timestamp", ctypes.c_uint32),
        ("windowID", ctypes.c_uint32),
        ("state", ctypes.c_uint8),
        ("repeat", ctypes.c_uint8),
        ("padding2", ctypes.c_uint8),
        ("padding3", ctypes.c_uint8),
        ("keysym", SdlKeysym),
    ]


class SdlMouseButtonEvent(ctypes.Structure):
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


class SdlEvent(ctypes.Union):
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("key", SdlKeyboardEvent),
        ("button", SdlMouseButtonEvent),
        ("padding", ctypes.c_uint8 * 56),
    ]


def loadSdl():
    sdl = ctypes.CDLL(ctypes.util.find_library("SDL2-2.0") or "libSDL2-2.0.so.0")
    sdl.SDL_GetKeyboardFocus.restype = ctypes.c_void_p
    sdl.SDL_GetMouseFocus.restype = ctypes.c_void_p
    sdl.SDL_GetWindowID.argtypes = [ctypes.c_void_p]
    sdl.SDL_GetWindowID.restype = ctypes.c_uint32
    sdl.SDL_PushEvent.argtypes = [ctypes.POINTER(SdlEvent)]
    sdl.SDL_PushEvent.restype = ctypes.c_int
    return sdl


def pushInput(sdl, kind, direction, width, height, tile_size):
    window = sdl.SDL_GetKeyboardFocus() or sdl.SDL_GetMouseFocus()
    window_id = sdl.SDL_GetWindowID(window) if window else 0
    for pressed in (True, False):
        event = SdlEvent()
        if kind == "keyboard":
            event.key.type = 0x300 if pressed else 0x301
            event.key.windowID = window_id
            event.key.state = int(pressed)
            event.key.keysym.scancode = 79 if direction > 0 else 80
            event.key.keysym.sym = (1 << 30) | event.key.keysym.scancode
        else:
            event.button.type = 0x401 if pressed else 0x402
            event.button.windowID = window_id
            event.button.button = 1
            event.button.state = int(pressed)
            event.button.clicks = 1
            event.button.x = ((width // tile_size + 1) // 2 + direction) * tile_size + tile_size // 2
            event.button.y = ((height // tile_size + 1) // 2) * tile_size + tile_size // 2
        if sdl.SDL_PushEvent(ctypes.byref(event)) != 1:
            raise RuntimeError("SDL_PushEvent rejected a movement event")


def coords(point):
    return [point.x, point.y, point.z]


def actorSnapshot(world):
    return {actor.getName(): (actor.getType(), coords(actor.getCoords())) for actor in world.getObjects()}


def loadedCoreLibrary():
    libraries = {
        Path(line.split(maxsplit=5)[-1]).resolve()
        for line in Path("/proc/self/maps").read_text().splitlines()
        if line.split(maxsplit=5)[-1].endswith("/libgame_core.so")
    }
    if len(libraries) != 1:
        raise RuntimeError(f"Expected one identifiable loaded game core library, found {libraries}")
    return libraries.pop()


def findRoute(game, world, spawn):
    for radius in range(10):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                start = game.Coords(spawn.x + dx, spawn.y + dy, spawn.z)
                end = game.Coords(start.x + 1, start.y, start.z)
                if all(world.canStep(point) and not world.getObjectsAtCoords(point) for point in (start, end)):
                    return [coords(start), coords(end)]
    raise RuntimeError("No unoccupied adjacent horizontal route near the authored spawn")


def ensureIsolatedDisplay():
    if os.name != "posix" or shutil.which("xvfb-run") is None or shutil.which("xauth") is None:
        raise RuntimeError("Movement profiling requires Linux/Unix with xvfb-run and xauth")
    if os.environ.get("GAME_MOVEMENT_PROFILE_CHILD") == "1":
        if os.environ.get("SDL_VIDEODRIVER") != "x11" or not os.environ.get("DISPLAY"):
            raise RuntimeError("The isolated profile child requires an Xvfb x11 display")
        return
    environment = os.environ.copy()
    environment.update(
        GAME_MOVEMENT_PROFILE_CHILD="1",
        SDL_VIDEODRIVER="x11",
        SDL_AUDIODRIVER="dummy",
        SDL_RENDER_DRIVER="software",
        LIBGL_ALWAYS_SOFTWARE="1",
    )
    command = [
        "xvfb-run",
        "-a",
        "--server-args=-screen 0 1920x1080x24",
        sys.executable,
        str(Path(__file__).resolve()),
        *sys.argv[1:],
    ]
    raise SystemExit(subprocess.call(command, env=environment))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--map", default="nouraajd")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input", choices=("keyboard", "mouse"), default="keyboard")
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--seed", type=int, default=241)
    parser.add_argument("--movement-timeout", type=float, default=300)
    parser.add_argument("--callgrind-client", type=Path)
    args = parser.parse_args()
    if not args.build_dir.is_absolute():
        parser.error("--build-dir must be absolute to identify the runtime explicitly")
    if args.warmups < 0 or args.samples < 1 or args.movement_timeout <= 0 or not 0 <= args.seed <= 0xFFFFFFFF:
        parser.error("warmups >= 0, samples >= 1, timeout > 0, and an unsigned 32-bit seed are required")
    args.output = args.output.resolve()
    ensureIsolatedDisplay()
    root = Path(__file__).resolve().parents[1]
    build = args.build_dir.resolve(strict=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    os.environ["GAME_BUILD_DIR"] = str(build)
    sys.path[:0] = [str(build), str(root), str(root / "res")]
    os.chdir(build)
    import _game

    if not Path(_game.__file__).resolve().is_relative_to(build):
        raise RuntimeError(f"Compiled game module was loaded outside the requested build: {_game.__file__}")
    _game.set_logger_sink("disabled")
    _game._seedRandomForTests(args.seed)
    random.seed(args.seed)
    import game

    game.set_logger_sink("disabled")
    client = ctypes.CDLL(str(args.callgrind_client.resolve(strict=True))) if args.callgrind_client else None
    source_files = (
        "src/core/CAsync.h",
        "src/core/CFuture.cpp",
        "src/core/CModule.cpp",
        "src/gui/object/CMapGraphicsObject.cpp",
    )
    source_files += tuple(
        path.relative_to(root).as_posix()
        for path in sorted((root / "src/core/bindings").iterdir())
        if path.suffix in {".cpp", ".h"}
    )
    source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_files}
    core_library = loadedCoreLibrary()
    records = []
    result = {
        "status": "incomplete",
        "map": args.map,
        "input": args.input,
        "seed": args.seed,
        "source": str(root),
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        "build": str(build),
        "native_module": str(_game.__file__),
        "native_module_sha256": hashlib.sha256(Path(_game.__file__).read_bytes()).hexdigest(),
        "core_library": str(core_library),
        "core_library_sha256": hashlib.sha256(core_library.read_bytes()).hexdigest(),
        "source_hashes": source_hashes,
        "source_hashes_note": "Current working source snapshot; use binary hashes and the build manifest for provenance",
        "source_fingerprint_sha256": hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest(),
        "python_module": str(game.__file__),
        "display": os.environ["DISPLAY"],
        "warmups": args.warmups,
        "samples": args.samples,
        "timing_is_gate": False,
        "frame_count_method": "Python event_loop.run() calls; nested modal frames are not counted",
        "animation_estimate_method": "Visible cardinal actor coordinate changes times 150 ms; non-wrapping route estimate",
        "measurements": records,
    }
    current = None
    collecting = False
    with tempfile.TemporaryDirectory(prefix="nouraajd-movement-ui-", dir=args.output.parent) as ui_directory:
        os.environ["GAME_UI_PREFERENCES_PATH"] = str(Path(ui_directory) / "preferences.json")
        try:
            current = game.CGameLoader.loadGame()
            game.CGameLoader.loadGui(current)
            game.CGameLoader.startGameWithPlayer(current, args.map, "Warrior")
            loop = game.event_loop.instance()
            for _ in range(5):
                loop.run()
            world, gui = current.getMap(), current.getGui()
            player = world.getPlayer()
            spawn = coords(player.getCoords())
            route = findRoute(game, world, player.getCoords())
            # Setup relocation avoids spawn narrative cells; all measured turns use real SDL input.
            player.relocateWithoutMoveHooks(game.Coords(*route[0]))
            gui.findChild("CMapGraphicsObject").refreshAll()
            for _ in range(3):
                loop.run()
            width, height = gui.getNumericProperty("width"), gui.getNumericProperty("height")
            tile_size = gui.getNumericProperty("tileSize")
            if min(width, height, tile_size) <= 0:
                raise RuntimeError("GUI dimensions and tile size must be positive")
            initial_state = {
                "actors": sorted(actorSnapshot(world).values()),
                "spawn": spawn,
                "route": route,
                "turn": world.getTurn(),
                "player_hp": player.getHp(),
                "inventory": sorted(item.getType() for item in player.getItems()),
            }
            result.update(
                route=route,
                authored_spawn=spawn,
                objects=len(world.getObjects()),
                initial_state=initial_state,
                initial_state_sha256=hashlib.sha256(json.dumps(initial_state, sort_keys=True).encode()).hexdigest(),
                ui_preferences=json.loads(gui.getUiPreferences()),
                gui_dimensions=[width, height],
                tile_size=tile_size,
                animation_duration_ms=150,
            )
            sdl = loadSdl()
            for index in range(-args.warmups, args.samples):
                if index == 0 and client:
                    client.navigationProfileStart()
                    collecting = True
                origin = coords(player.getCoords())
                if origin not in route:
                    raise RuntimeError(f"Player unexpectedly left the profiling route: {origin}")
                direction = 1 if origin == route[0] else -1
                target = [origin[0] + direction, origin[1], origin[2]]
                before = actorSnapshot(world)
                turn = world.getTurn()
                frames = 0
                result["active_measurement"] = {
                    "sample": index,
                    "warmup": index < 0,
                    "origin": origin,
                    "target": target,
                    "turn_before": turn,
                }
                args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                wall_start, cpu_start = time.perf_counter(), time.process_time()
                pushInput(sdl, args.input, direction, width, height, tile_size)
                while world.getTurn() == turn or world.isMoving():
                    loop.run()
                    frames += 1
                    if time.perf_counter() - wall_start > args.movement_timeout:
                        raise TimeoutError(f"Movement timed out at {origin}, turn={turn}, frame pumps={frames}")
                wall_ms, cpu_ms = (time.perf_counter() - wall_start) * 1000, (time.process_time() - cpu_start) * 1000
                destination = coords(player.getCoords())
                if destination != target or world.getTurn() != turn + 1:
                    raise RuntimeError(
                        f"Wrong movement result: {origin} -> {destination}; turn {turn}->{world.getTurn()}"
                    )
                after = actorSnapshot(world)
                visible_moves = 0
                for name, (_, old_coords) in before.items():
                    if name not in after:
                        continue
                    new_coords = after[name][1]
                    if old_coords[2] != destination[2] or new_coords[2] != destination[2]:
                        continue
                    if sum(abs(a - b) for a, b in zip(old_coords, new_coords)) != 1:
                        continue
                    if any(
                        abs(point[0] - destination[0]) <= (width // tile_size + 1) // 2 + 1
                        and abs(point[1] - destination[1]) <= (height // tile_size + 1) // 2 + 1
                        for point in (old_coords, new_coords)
                    ):
                        visible_moves += 1
                record = {
                    "sample": index,
                    "warmup": index < 0,
                    "wall_ms": wall_ms,
                    "cpu_ms": cpu_ms,
                    "paced_frame_pumps": frames,
                    "turn_before": turn,
                    "turn_after": world.getTurn(),
                    "origin": origin,
                    "destination": destination,
                    "visible_cardinal_actor_moves": visible_moves,
                    "nominal_sequential_animation_ms_estimate": visible_moves * 150,
                }
                records.append(record)
                result.pop("active_measurement")
                args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                print(json.dumps(record, sort_keys=True), flush=True)
                for _ in range(3):
                    loop.run()
            measured = [record for record in records if not record["warmup"]]
            result.update(
                status="passed",
                median_wall_ms=statistics.median(record["wall_ms"] for record in measured),
                median_cpu_ms=statistics.median(record["cpu_ms"] for record in measured),
                measured_paced_frame_pumps=[record["paced_frame_pumps"] for record in measured],
            )
        except BaseException as error:
            result["status"] = "failed"
            result["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            cleanup_errors = []
            for label, cleanup in (
                ("callgrind stop", (lambda: client.navigationProfileStop()) if collecting else None),
                ("context shutdown", (lambda: current.getContext().shutdown()) if current is not None else None),
            ):
                if cleanup is not None:
                    try:
                        cleanup()
                    except BaseException as error:
                        cleanup_errors.append(f"{label}: {type(error).__name__}: {error}")
            if cleanup_errors:
                result.update(status="failed", cleanup_errors=cleanup_errors)
            try:
                args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            except BaseException as error:
                if "error" not in result:
                    raise
                print(f"Unable to save the failed profile: {type(error).__name__}: {error}", file=sys.stderr)
            if cleanup_errors and "error" not in result:
                raise RuntimeError("; ".join(cleanup_errors))


if __name__ == "__main__":
    main()
