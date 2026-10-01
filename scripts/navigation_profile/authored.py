#!/usr/bin/env python3
# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in read-only route planning profile on real authored maps; never creates a GUI."""

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", default="cmake-build-release")
    parser.add_argument("--build-config", default="Release")
    parser.add_argument("--map", action="append", dest="maps")
    parser.add_argument("--case", action="append", choices=("short", "center", "far"), dest="cases")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    build = (root / args.build_dir).resolve()
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["SDL_RENDER_DRIVER"] = "software"
    sys.path[:0] = [str(build / args.build_config), str(build), str(root), str(root / "res")]
    os.chdir(build)
    import game

    game.set_logger_sink("disabled")
    maps = args.maps or ["nouraajd", "ninemarches", "castleHomecoming"]
    for map_name in maps:
        current = game.CGameLoader.loadGame()
        try:
            game.CGameLoader.startGameWithPlayer(current, map_name, "Warrior")
            assert current.getGui() is None, "The profile must never create a GUI."
            world = current.getMap()
            player = world.getPlayer()
            origin = player.getCoords()
            authored = json.loads((root / "res/maps" / map_name / "map.json").read_text())
            floor = next(
                layer
                for layer in authored["layers"]
                if layer.get("type") == "tilelayer" and int(layer["properties"].get("level", 0)) == origin.z
            )
            width = int(floor["properties"]["xBound"]) + 1
            height = int(floor["properties"]["yBound"]) + 1
            requested = {
                "short": (origin.x, max(0, origin.y - 12)),
                "center": (width // 2, height // 2),
                "far": (1, 1),
            }
            goals = []
            for case in args.cases or ("short", "center"):
                x, y = requested[case]
                for radius in range(16):
                    candidates = sorted(
                        (abs(dx) + abs(dy), x + dx, y + dy)
                        for dx in range(-radius, radius + 1)
                        for dy in range(-radius, radius + 1)
                        if max(abs(dx), abs(dy)) == radius
                    )
                    goal = next(
                        (
                            game.Coords(gx, gy, origin.z)
                            for _, gx, gy in candidates
                            if 0 <= gx < width and 0 <= gy < height and world.canStep(game.Coords(gx, gy, origin.z))
                        ),
                        None,
                    )
                    if goal is not None:
                        break
                if goal is None:
                    raise RuntimeError(f"No traversable goal near {(x, y)} on {map_name}")
                goals.append((case, goal))
            controller = player.getController()
            state = (player.getHp(), player.getMana(), world.getTurn(), len(player.getItems()))
            for case, goal in goals:
                timings = []
                for sample in range(-2, 7):
                    started = time.perf_counter()
                    controller.setTarget(player, goal)
                    elapsed = (time.perf_counter() - started) * 1000
                    if sample >= 0:
                        timings.append(elapsed)
                assert (player.getHp(), player.getMana(), world.getTurn(), len(player.getItems())) == state
                assert (player.getCoords().x, player.getCoords().y, player.getCoords().z) == (
                    origin.x,
                    origin.y,
                    origin.z,
                )
                print(
                    json.dumps(
                        {
                            "map": map_name,
                            "case": case,
                            "dimensions": [width, height],
                            "origin": [origin.x, origin.y, origin.z],
                            "goal": [goal.x, goal.y, goal.z],
                            "route_pending": not controller.isCompleted(player),
                            "warmups": 2,
                            "samples_ms": timings,
                            "median_ms": statistics.median(timings),
                            "timing_is_gate": False,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
        finally:
            current.getContext().shutdown()


if __name__ == "__main__":
    main()
