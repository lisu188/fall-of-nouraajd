#!/usr/bin/env python3
"""Profile a current-only authored route through a real game without opening a GUI."""

# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import ctypes
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--callgrind-client", type=Path)
    parser.add_argument("--import-only", action="store_true", help="Import the same module without creating a game")
    args = parser.parse_args()
    source, build = args.source.resolve(), args.build_dir.resolve()
    client = args.callgrind_client.resolve() if args.callgrind_client else None
    sys.path[:0] = [str(build), str(source), str(source / "res")]
    os.chdir(build)
    os.environ.update(
        SDL_VIDEODRIVER="dummy",
        SDL_AUDIODRIVER="dummy",
        SDL_RENDER_DRIVER="software",
        LIBGL_ALWAYS_SOFTWARE="1",
    )
    import game

    game.set_logger_sink("disabled")
    if args.import_only:
        print(json.dumps({"control": "import-only", "game_created": False}), flush=True)
        return
    current = game.CGameLoader.loadGame()
    loop = game.event_loop.instance()
    profile = ctypes.CDLL(str(client)) if client else None
    if profile:
        profile.navigationProfileStart.restype = None
        profile.navigationProfileStop.restype = None

    def position(player):
        coords = player.getCoords()
        return [coords.x, coords.y, coords.z]

    try:
        game.CGameLoader.startGameWithPlayer(current, "multilevel", "Warrior")
        loop.run()
        loop.run()
        assert current.getGui() is None
        world = current.getMap()
        player = world.getPlayer()
        controller = player.getController()
        before = (position(player), world.getTurn(), player.getHp(), player.getMana(), len(player.getItems()))
        targets = ("stairsUp", "multilevelUpperGoal", "stairsDown", "multilevelLowerGoal")
        arrived = []
        if profile:
            profile.navigationProfileStart()
        for name in targets:
            target = world.getObjectByName(name)
            assert target is not None, name
            planned_from = (position(player), world.getTurn(), player.getHp(), player.getMana(), len(player.getItems()))
            for _ in range(9):
                controller.setTarget(player, target.getCoords())
            assert (
                position(player),
                world.getTurn(),
                player.getHp(),
                player.getMana(),
                len(player.getItems()),
            ) == planned_from
            for _ in range(24):
                coords = position(player)
                if name == "stairsUp" and coords == [4, 1, 1]:
                    break
                if name == "stairsDown" and coords[2] == 0:
                    break
                if name == "multilevelUpperGoal" and coords == [6, 4, 1]:
                    break
                if name == "multilevelLowerGoal" and coords == [6, 5, 0]:
                    break
                world.move()
                loop.run()
                loop.run()
            else:
                raise AssertionError((name, position(player)))
            arrived.append({"object": name, "coords": position(player), "turn": world.getTurn()})
        if profile:
            profile.navigationProfileStop()
        flags = ("used_stairs_up", "visited_upper_goal", "used_stairs_down", "visited_lower_goal")
        assert all(world.getBoolProperty(flag) for flag in flags)
        assert world.getTurn() > before[1]
        assert player.getHp() == before[2] and player.getMana() == before[3] and len(player.getItems()) == before[4]
        assert current.getGui() is None
        print(
            json.dumps(
                {
                    "current_only": True,
                    "map": "multilevel",
                    "hero": "Warrior",
                    "plan_calls": 36,
                    "turns_advanced": world.getTurn() - before[1],
                    "arrivals": arrived,
                    "flags": {flag: world.getBoolProperty(flag) for flag in flags},
                    "no_gui": True,
                    "resources_preserved": True,
                }
            ),
            flush=True,
        )
    finally:
        current.getContext().shutdown()


if __name__ == "__main__":
    main()
