# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a unique starting save through the current engine's ordinary startup path."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.gameplay_branch_types import PLAYER_CLASSES

# These initial values exercise otherwise unreachable low-reputation dialog branches.
APPROVED_REPUTATIONS = frozenset({-7, -6, -3})


def buildStartingSave(args):
    import mcp

    if not re.fullmatch(r"mcp-branch-[0-9a-f]{32}", args.slot):
        raise ValueError("Starting fixtures require a unique task-owned mcp-branch save slot")
    if args.reputation is not None and (args.map != "ninemarches" or args.reputation not in APPROVED_REPUTATIONS):
        raise ValueError("Only documented Nine Marches initial reputation changes are permitted")
    directory = Path(args.build_dir).resolve(strict=True)
    for candidate in (directory / args.build_config if args.build_config else directory, directory):
        if os.name == "nt" and candidate.is_dir():
            os.environ["PATH"] = str(candidate) + os.pathsep + os.environ.get("PATH", "")
    server = mcp.EngineMcpServer(
        ROOT, directory, build_config=args.build_config, native_log_sink="disabled", test_seed=args.seed
    )
    server.import_modules()
    native = server._game_module
    game = native.CGameLoader.loadGame()
    if args.campaign:
        import campaign

        campaign.start(game, args.campaign, args.class_id, args.race_id)
    else:
        native.CGameLoader.startGameWithPlayer(game, args.map, args.class_id, args.race_id)
    loop = native.event_loop.instance()
    for _ in range(3):
        loop.run()
    world = game.getMap()
    if world is None or world.getPlayer() is None or game.getGui() is not None:
        raise RuntimeError("Ordinary initial state could not be created offscreen")
    player = world.getPlayer()
    before = json.loads(native.jsonify(player))["properties"]
    if args.reputation is not None:
        player.setNumericProperty("reputation", args.reputation)
    after = json.loads(native.jsonify(player))["properties"]
    changed = {key for key in set(before) | set(after) if before.get(key) != after.get(key)}
    if changed - {"reputation"}:
        raise AssertionError(f"Starting fixture changed more than initial reputation: {sorted(changed)}")
    if not native.CMapLoader.saveWithResult(world, args.slot):
        raise RuntimeError("The engine refused to save its initial state")
    print(
        json.dumps(
            {
                "slot": args.slot,
                "map": world.getStringProperty("mapName"),
                "class": args.class_id,
                "campaign": args.campaign,
                "initialReputation": args.reputation,
                "seed": args.seed,
                "changedPlayerProperties": sorted(changed),
            }
        )
    )


def main(argv=None):
    import mcp

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--build-config", default=os.environ.get("GAME_BUILD_CONFIG"))
    parser.add_argument("--class-id", required=True, choices=PLAYER_CLASSES)
    parser.add_argument("--race-id", required=True)
    parser.add_argument("--slot", required=True)
    parser.add_argument("--seed", required=True, type=mcp.parseTestSeed)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--campaign")
    target.add_argument("--map")
    parser.add_argument("--reputation", type=int)
    args = parser.parse_args(argv)
    for key, value in {
        "SDL_VIDEODRIVER": "dummy",
        "SDL_AUDIODRIVER": "dummy",
        "SDL_RENDER_DRIVER": "software",
        "LIBGL_ALWAYS_SOFTWARE": "1",
    }.items():
        os.environ[key] = value
    buildStartingSave(args)


if __name__ == "__main__":
    main()
