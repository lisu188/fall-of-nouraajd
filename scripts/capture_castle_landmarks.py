# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Capture Castle campaign landmarks through the real SDL renderer.

These are visual inspection scenes: the camera/player is relocated beside the
landmark without completing its quest. Automated gameplay and MCP walkthroughs
provide separate evidence that the authored routes and objectives work.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENES = (
    ("castle-camp", "castleHomecoming", None, False),
    ("castle-terraneus", "castleHomecoming", "castleHomecomingObjective1453", False),
    ("castle-griffin-tower", "castleGriffinCliff", "castleGriffinCliffObjective1015", False),
    ("castle-terraneus-after-combat", "castleHomecoming", "castleHomecomingObjective1453", True),
    ("castle-griffin-tower-after-combat", "castleGriffinCliff", "castleGriffinCliffObjective1015", True),
)


def ensureVirtualScreen():
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["SDL_RENDER_DRIVER"] = "software"
    os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
    if os.name == "nt":
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        return
    if os.name != "posix":
        raise RuntimeError("No virtual-screen backend is configured for this platform")
    os.environ["SDL_VIDEODRIVER"] = "x11"
    if os.environ.get("GAME_CASTLE_VIRTUAL_SCREEN") == "1":
        return
    launcher = shutil.which("xvfb-run")
    if not launcher or not shutil.which("xauth"):
        raise RuntimeError("Castle screenshots require xvfb-run and xauth; visible desktop rendering is disabled")
    environment = dict(os.environ, GAME_CASTLE_VIRTUAL_SCREEN="1")
    os.execvpe(
        launcher,
        [launcher, "-a", "--server-args=-screen 0 1920x1080x24", sys.executable, *sys.argv],
        environment,
    )


def positionBeside(simulation, object_name):
    marker = simulation.objectByName(object_name)
    center = marker.getCoords()
    occupied = {
        (obj.getCoords().x, obj.getCoords().y, obj.getCoords().z)
        for obj in simulation.gameMap.getObjects()
        if obj != simulation.player
    }
    candidates = [
        (center.x + dx, center.y + dy, center.z)
        for radius in range(1, 5)
        for dy in range(-radius, radius + 1)
        for dx in range(-radius, radius + 1)
        if max(abs(dx), abs(dy)) == radius
    ]
    target = next(
        (
            coords
            for coords in candidates
            if coords not in occupied and simulation.gameMap.canStep(simulation.gameModule.Coords(*coords))
        ),
        None,
    )
    if target is None:
        raise RuntimeError("No unoccupied camera position beside " + object_name)
    simulation.moveToCoords(*target, mode="direct")
    simulation.pumpEvents(5)


def viewportEvidence(simulation, object_name, tile_size):
    gui = simulation.gameInstance.getGui()
    map_graph = gui.findChild("CMapGraphicsObject")
    if map_graph is None:
        raise RuntimeError("The live GUI has no map viewport")
    map_graph.refresh()
    map_graph.refreshAll()
    simulation.pumpEvents(3)
    proxy_rects = {}
    cell_sizes = set()
    for proxy in map_graph.getChildren():
        rect = list(proxy.getResolvedRect())
        cell_sizes.add(tuple(rect[2:]))
        for graphic in proxy.getChildren():
            represented = graphic.getObject() if hasattr(graphic, "getObject") else None
            if represented:
                proxy_rects[represented.getName()] = rect
    if cell_sizes != {(tile_size, tile_size)}:
        raise RuntimeError(f"Rendered cell sizes {sorted(cell_sizes)} do not match requested {tile_size}px")
    player_rect = proxy_rects.get(simulation.player.getName())
    viewport_rect = list(map_graph.getResolvedRect())
    expected_center = [
        viewport_rect[0] + (gui.getNumericProperty("width") // tile_size + 1) // 2 * tile_size,
        viewport_rect[1] + (gui.getNumericProperty("height") // tile_size + 1) // 2 * tile_size,
    ]
    if player_rect is None or player_rect[:2] != expected_center:
        raise RuntimeError(f"The rendered player is not centered: {player_rect}; expected {expected_center}")
    target_rect = proxy_rects.get(object_name) if object_name else None
    if object_name and not target_rect:
        raise RuntimeError("The requested landmark is absent from the refreshed map viewport: " + object_name)
    if object_name and simulation.objectByName(object_name).getCoords().z != simulation.player.getCoords().z:
        raise RuntimeError("The requested landmark and rendered player are on different map levels")
    return {"playerRect": player_rect, "landmarkRect": target_rect, "viewportRect": viewport_rect}


def defeatGarrison(simulation, object_name):
    marker = simulation.objectByName(object_name)
    guards = [simulation.objectByName(name) for name in marker.getStringProperty("campaign_guards").split(",") if name]
    if not guards or any(not guard.isAlive() for guard in guards):
        raise RuntimeError("The visual encounter must begin with a living authored garrison")
    template = simulation.gameInstance.createObject("Warrior")
    simulation.player.setFightController(template.getFightController())
    origin = simulation.player.getCoords()
    target = marker.getCoords()
    hp_before = simulation.player.getNumericProperty("hp")
    simulation.player.moveTo(target.x, target.y, target.z)
    simulation.pumpEvents(3)
    captured = simulation.gameMap.getBoolProperty("campaign_castleCaptured_" + object_name)
    if not simulation.player.isAlive() or any(guard.isAlive() for guard in guards) or captured:
        raise RuntimeError("The visual battle must defeat the garrison and leave the landmark uncaptured")
    after = simulation.player.getCoords()
    if (after.x, after.y, after.z) != (origin.x, origin.y, origin.z):
        raise RuntimeError("The post-combat view must retain the player's approach square")
    return {
        "guardIds": [guard.getName() for guard in guards],
        "defeatedGuards": len(guards),
        "objectiveCaptured": captured,
        "playerHpBeforeCombat": hp_before,
        "playerHpAfterCombat": simulation.player.getNumericProperty("hp"),
        "combatTarget": [target.x, target.y, target.z],
    }


def captureScenes(game, output_dir, tile_size):
    from game_simulation import GameSimulation

    captures = []
    for scene_name, map_name, object_name, after_combat in SCENES:
        instance = game.CGameLoader.loadGame()
        if not after_combat:
            game.CGameLoader.loadGui(instance)
            instance.getGui().setNumericProperty("tileSize", tile_size)
        game.CGameLoader.startGameWithPlayer(instance, map_name, "Warrior")
        simulation = GameSimulation(game, instance, map_name, "Warrior")
        simulation.pumpEvents(5)
        mission = simulation.objectByName("castleMission")
        if not mission.getStringProperty("campaign_mission").startswith("castleMission:"):
            raise RuntimeError("The selected resource directory did not load the authored Castle map")
        if object_name:
            positionBeside(simulation, object_name)
        simulation.advanceTurns(1)
        combat = defeatGarrison(simulation, object_name) if after_combat else {}
        if after_combat:
            game.CGameLoader.loadGui(instance)
            instance.getGui().setNumericProperty("tileSize", tile_size)
            simulation.pumpEvents(5)
        viewport = viewportEvidence(simulation, object_name, tile_size)
        path = output_dir / f"{scene_name}-{tile_size}px.png"
        info = simulation.captureGuiScreenshot(path)
        if info["suffix"] != ".png" or info["bytes"] <= 0 or min(info["width"], info["height"]) <= 0:
            raise RuntimeError("Invalid screenshot: " + str(path))
        coords = simulation.player.getCoords()
        info["path"] = path.name
        info.update(
            map=map_name,
            target=object_name,
            tileSize=tile_size,
            playerPosition=[coords.x, coords.y, coords.z],
            playerRelocated=bool(object_name),
            stage="afterGarrisonCombat" if after_combat else "beforeCombat",
            virtualScreen=os.environ.get("SDL_VIDEODRIVER"),
            **combat,
            **viewport,
        )
        captures.append(info)
        print(json.dumps(info, sort_keys=True), flush=True)
    return captures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "screenshots"))
    parser.add_argument("--tile-size", type=int, default=32, choices=(32, 50))
    args = parser.parse_args()
    ensureVirtualScreen()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO_ROOT))
    from scripts import generate_screenshots

    generate_screenshots._bootstrap_paths()
    game = generate_screenshots._load_game_module()
    generate_screenshots._suppress_blocking_popups(game)
    game.CGuiHandler.showCampaignScreen = lambda self, *args, **kwargs: None
    captures = captureScenes(game, output_dir, args.tile_size)
    (output_dir / "castle-landmark-captures.json").write_text(json.dumps(captures, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
