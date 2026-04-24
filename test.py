# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2025  Andrzej Lis
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
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import ast
import builtins
import importlib
import json
import os
import queue
import re
import select
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import types
from pathlib import Path
import unittest

import mcp

REPO_ROOT = Path(__file__).resolve().parent
TEST_OUTPUT_DIR = REPO_ROOT / "test"
runtime_dir_id = os.getuid() if hasattr(os, "getuid") else os.getpid()
XDG_RUNTIME_DIR = Path(tempfile.gettempdir()) / f"xdg-runtime-{runtime_dir_id}"

if "XDG_RUNTIME_DIR" not in os.environ:
    XDG_RUNTIME_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.environ["XDG_RUNTIME_DIR"] = str(XDG_RUNTIME_DIR)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_RENDER_DRIVER", "software")
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

build_dir = REPO_ROOT / "cmake-build-release"
build_dir_override = os.environ.get("GAME_BUILD_DIR")
if build_dir_override:
    build_dir = (REPO_ROOT / build_dir_override).resolve()
if build_dir.exists():
    os.chdir(build_dir)

if str(Path.cwd()) not in sys.path:
    sys.path.insert(0, str(Path.cwd()))
build_config = os.environ.get("GAME_BUILD_CONFIG")
extension_dirs = []
if build_config:
    extension_dirs.append(build_dir / build_config)
else:
    extension_dirs.extend(build_dir / config for config in ("Release", "Debug", "RelWithDebInfo", "MinSizeRel"))
for extension_dir in reversed(extension_dirs):
    if extension_dir.exists() and str(extension_dir) not in sys.path:
        sys.path.insert(0, str(extension_dir))
if str(REPO_ROOT / "res") not in sys.path:
    sys.path.insert(1, str(REPO_ROOT / "res"))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(2, str(REPO_ROOT))
plugins_path = REPO_ROOT / "res" / "plugins"
if str(plugins_path) not in sys.path:
    sys.path.insert(3, str(plugins_path))

# Silence the native engine logger so regression tests don't flood stdout.
try:
    import _game  # type: ignore

    _game.set_logger_sink("disabled")
except Exception:
    pass

MCP_PROTOCOL_VERSION = "2025-11-25"


def load_game_module():
    game = importlib.import_module("game")
    builtins.game = game
    return game


def make_temp_log_path():
    fd, path = tempfile.mkstemp(prefix="fon-log-", suffix=".txt")
    os.close(fd)
    return Path(path)


def game_test(f):
    def wrapper(self):
        n = f.__name__.split("test_")[1]
        TEST_OUTPUT_DIR.mkdir(exist_ok=True)
        result = f(self)
        success = result[0]
        log = result[1]
        (TEST_OUTPUT_DIR / f"{n}.json").write_text(str(log))
        self.assertTrue(success)

    return wrapper


def advance(g, turns):
    game = load_game_module()
    current_turn = g.getMap().getNumericProperty("turn")
    for i in range(turns):
        g.getMap().move()
    while g.getMap().getNumericProperty("turn") < turns + current_turn:
        game.event_loop.instance().run()


def pump_event_loop(iterations=30):
    game = load_game_module()
    for _ in range(iterations):
        game.event_loop.instance().run()


def get_map_proxy_child_counts(g):
    game = load_game_module()
    gui_tree = json.loads(game.jsonify(g.getGui()))
    children = gui_tree.get("properties", {}).get("children") or []
    map_graph = next(child for child in children if child.get("class") == "CMapGraphicsObject")
    proxies = map_graph.get("properties", {}).get("children") or []
    return [len(proxy.get("properties", {}).get("children") or []) for proxy in proxies]


def materialized_tile_type(game, game_map, coords):
    game_map.getMovementCost(coords)
    serialized_map = json.loads(game.jsonify(game_map))
    for tile in serialized_map.get("properties", {}).get("tiles", []):
        properties = tile.get("properties", {})
        if (properties.get("posx"), properties.get("posy"), properties.get("posz")) == (coords.x, coords.y, coords.z):
            return properties.get("typeId")
    return None


MAPS_DIR = REPO_ROOT / "res/maps"
DEFAULT_PLAYER = "Warrior"
NOURAAJD_VICTOR_TIMEOUT = 75
TILED_FLIP_FLAG_MASK = 0xF0000000
SUPPORTED_TILED_LAYER_TYPES = {"tilelayer", "objectgroup"}


def discover_maps():
    playable_maps = []
    for path in sorted(MAPS_DIR.iterdir()):
        if not path.is_dir():
            continue
        map_path = path / "map.json"
        if not map_path.exists():
            continue
        data = json.loads(map_path.read_text())
        properties = data.get("properties", {})
        if all(key in properties for key in ("x", "y", "z")):
            playable_maps.append(path.name)
    return playable_maps


def load_map_data(map_name):
    return json.loads((MAPS_DIR / map_name / "map.json").read_text())


def load_game_map(map_name):
    game = load_game_module()
    g = game.CGameLoader.loadGame()
    game.CGameLoader.startGame(g, map_name)
    return g, g.getMap()


def load_game_map_with_player(map_name, player_name=DEFAULT_PLAYER):
    game = load_game_module()
    g = game.CGameLoader.loadGame()
    game.CGameLoader.startGameWithPlayer(g, map_name, player_name)
    game_map = g.getMap()
    player = game_map.getPlayer()
    return g, game_map, player


def get_player_controller(player):
    controller = player.getController()
    if not hasattr(controller, "setTarget"):
        raise AssertionError(f"Expected a CPlayerController, got {type(controller)!r}.")
    return controller


def set_player_target(player, coords):
    controller = get_player_controller(player)
    controller.setTarget(player, coords)
    return controller


def find_adjacent_walkable_tile(game_map, origin):
    game = load_game_module()
    for delta in (game.Coords(1, 0, 0), game.Coords(-1, 0, 0), game.Coords(0, 1, 0), game.Coords(0, -1, 0)):
        target = game.Coords(origin.x + delta.x, origin.y + delta.y, origin.z + delta.z)
        if game_map.canStep(target):
            return target
    raise AssertionError(f"Expected an adjacent walkable tile near {origin.x},{origin.y},{origin.z}.")


def get_panel_proxy_child_totals(panel):
    game = load_game_module()
    panel_data = json.loads(game.jsonify(panel))
    totals = []
    for child in panel_data.get("properties", {}).get("children") or []:
        proxy_children = child.get("properties", {}).get("children") or []
        totals.append(sum(len(proxy.get("properties", {}).get("children") or []) for proxy in proxy_children))
    return totals


def advance_turns(g, turns):
    advance(g, turns)
    return g.getMap().getTurn()


def advance_map_only(game_map, turns):
    for i in range(turns):
        game_map.move()
    return game_map.getTurn()


def force_nouraajd_victor_timeout(game_map):
    advance_map_only(game_map, NOURAAJD_VICTOR_TIMEOUT + 1)
    return game_map.getStringProperty("quest_state_victor")


def find_runtime_object(game_map, object_name):
    obj = game_map.getObjectByName(object_name)
    if obj is None:
        raise AssertionError(f"Could not find runtime object '{object_name}' on map '{game_map.getName()}'.")
    return obj


def find_map_object_definition(map_name, object_name):
    map_data = load_map_data(map_name)
    for layer in map_data.get("layers", []):
        if layer.get("type") != "objectgroup":
            continue
        for obj in layer.get("objects", []):
            if obj.get("name") == object_name:
                return obj
    raise AssertionError(f"Could not find object definition '{object_name}' in res/maps/{map_name}/map.json.")


def load_object_configs(map_name=None):
    configs = {}
    for path in sorted((REPO_ROOT / "res/config").glob("*.json")):
        configs.update(json.loads(path.read_text()))
    if map_name is not None:
        configs.update(json.loads((MAPS_DIR / map_name / "config.json").read_text()))
    return configs


def map_validation_issue(
    path,
    category,
    message,
    *,
    field=None,
    layer_name=None,
    layer_index=None,
    object_name=None,
    object_id=None,
):
    issue = {
        "category": category,
        "message": message,
        "path": str(path.relative_to(REPO_ROOT)),
    }
    if field is not None:
        issue["field"] = field
    if layer_index is not None:
        issue["layer_index"] = layer_index
    if layer_name is not None:
        issue["layer_name"] = layer_name
    if object_id is not None:
        issue["object_id"] = object_id
    if object_name is not None:
        issue["object_name"] = object_name
    return issue


def is_integral_json_number(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return value.is_integer()
    return False


def parse_engine_int_string(value):
    if not isinstance(value, str):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def is_loader_bool(value):
    if isinstance(value, bool):
        return True
    if isinstance(value, int) and not isinstance(value, bool):
        return True
    if isinstance(value, str):
        return value in {"true", "false", "1", "0"}
    return False


def get_legacy_properties(owner, path, issues, *, scope, required=False, **location):
    if "properties" not in owner:
        if required:
            issues.append(
                map_validation_issue(
                    path,
                    "loader_assumption",
                    f"{scope} must define a legacy object-style 'properties' map because CMapLoader indexes it directly.",
                    field="properties",
                    **location,
                )
            )
        return {}

    properties = owner["properties"]
    if isinstance(properties, dict):
        return properties

    if isinstance(properties, list):
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                f"{scope} uses Tiled's typed property array, but CMapLoader expects a legacy object-style 'properties' map.",
                field="properties",
                **location,
            )
        )
        return None

    issues.append(
        map_validation_issue(
            path,
            "tiled_semantics",
            f"{scope} has a non-object 'properties' value.",
            field="properties",
            **location,
        )
    )
    return None


def require_engine_int_string(properties, key, path, issues, *, scope, **location):
    if key not in properties:
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                f"{scope} is missing required '{key}' property.",
                field=key,
                **location,
            )
        )
        return None

    value = properties[key]
    parsed = parse_engine_int_string(value)
    if parsed is None:
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                f"{scope} property '{key}' must remain a string parseable as int because CMapLoader reads it with get<std::string>().",
                field=key,
                **location,
            )
        )
    return parsed


def validate_tiled_object(obj, path, issues, warnings, *, layer, layer_index, tile_width, tile_height):
    object_name = obj.get("name")
    object_id = obj.get("id")
    prefix = f"object {object_name or '<unnamed>'}"

    for field in ("name", "type"):
        if not isinstance(obj.get(field), str):
            issues.append(
                map_validation_issue(
                    path,
                    "loader_assumption",
                    f"{prefix} must provide string '{field}' because handleObjectLayer() reads it directly.",
                    field=field,
                    layer_name=layer.get("name"),
                    layer_index=layer_index,
                    object_name=object_name,
                    object_id=object_id,
                )
            )

    numeric_fields = {}
    for field in ("x", "y", "width", "height"):
        value = obj.get(field)
        if not is_integral_json_number(value):
            issues.append(
                map_validation_issue(
                    path,
                    "loader_assumption",
                    f"{prefix} field '{field}' must be an integer-valued JSON number because handleObjectLayer() reads it as int.",
                    field=field,
                    layer_name=layer.get("name"),
                    layer_index=layer_index,
                    object_name=object_name,
                    object_id=object_id,
                )
            )
            continue
        numeric_fields[field] = int(value)

    width = numeric_fields.get("width")
    height = numeric_fields.get("height")
    x_pos = numeric_fields.get("x")
    y_pos = numeric_fields.get("y")
    if width is not None and width <= 0:
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                f"{prefix} width must be greater than zero because handleObjectLayer() divides x by width.",
                field="width",
                layer_name=layer.get("name"),
                layer_index=layer_index,
                object_name=object_name,
                object_id=object_id,
            )
        )
    if height is not None and height <= 0:
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                f"{prefix} height must be greater than zero because handleObjectLayer() divides y by height.",
                field="height",
                layer_name=layer.get("name"),
                layer_index=layer_index,
                object_name=object_name,
                object_id=object_id,
            )
        )

    if width and tile_width and width != tile_width:
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                f"{prefix} width must match map tilewidth ({tile_width}) because the engine maps object pixels to tile coords via width.",
                field="width",
                layer_name=layer.get("name"),
                layer_index=layer_index,
                object_name=object_name,
                object_id=object_id,
            )
        )
    if height and tile_height and height != tile_height:
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                f"{prefix} height must match map tileheight ({tile_height}) because the engine maps object pixels to tile coords via height.",
                field="height",
                layer_name=layer.get("name"),
                layer_index=layer_index,
                object_name=object_name,
                object_id=object_id,
            )
        )

    if width and height and x_pos is not None and y_pos is not None:
        if x_pos % width or y_pos % height:
            warnings.append(
                map_validation_issue(
                    path,
                    "warning",
                    f"{prefix} is placed at pixel coords ({x_pos}, {y_pos}) that do not align to whole width/height steps; the loader will truncate with integer division.",
                    field="x/y",
                    layer_name=layer.get("name"),
                    layer_index=layer_index,
                    object_name=object_name,
                    object_id=object_id,
                )
            )

    if obj.get("rotation", 0) not in (0, 0.0):
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                f"{prefix} uses rotation, but the engine ignores object rotation when loading map objects.",
                field="rotation",
                layer_name=layer.get("name"),
                layer_index=layer_index,
                object_name=object_name,
                object_id=object_id,
            )
        )

    unsupported_fields = {
        "gid": "tile objects use TMX/Tiled tile-object semantics that handleObjectLayer() does not resolve.",
        "template": "template instances are valid Tiled data, but the engine does not resolve external object templates.",
        "ellipse": "ellipse objects are not supported because handleObjectLayer() assumes rectangle dimensions.",
        "point": "point objects are not supported because handleObjectLayer() divides by width/height.",
        "polygon": "polygon objects are not supported because handleObjectLayer() only consumes rectangle bounds.",
        "polyline": "polyline objects are not supported because handleObjectLayer() only consumes rectangle bounds.",
        "text": "text objects are not supported because handleObjectLayer() only instantiates map objects by type.",
        "capsule": "capsule objects are not supported because handleObjectLayer() only consumes rectangle bounds.",
    }
    for field, reason in unsupported_fields.items():
        if field in obj:
            issues.append(
                map_validation_issue(
                    path,
                    "loader_assumption",
                    f"{prefix} uses '{field}', but {reason}",
                    field=field,
                    layer_name=layer.get("name"),
                    layer_index=layer_index,
                    object_name=object_name,
                    object_id=object_id,
                )
            )

    properties = get_legacy_properties(
        obj,
        path,
        issues,
        scope=prefix,
        required=False,
        layer_name=layer.get("name"),
        layer_index=layer_index,
        object_name=object_name,
        object_id=object_id,
    )
    if properties is None:
        return


def validate_tiled_layer(
    layer, path, issues, warnings, *, layer_index, map_width, map_height, tile_width, tile_height, tileproperties
):
    layer_name = layer.get("name")
    layer_type = layer.get("type")
    prefix = f"layer {layer_name or layer_index}"

    if not isinstance(layer_type, str):
        issues.append(
            map_validation_issue(
                path,
                "tiled_semantics",
                f"{prefix} must define string field 'type'.",
                field="type",
                layer_name=layer_name,
                layer_index=layer_index,
            )
        )
        return

    if layer_type not in SUPPORTED_TILED_LAYER_TYPES:
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                f"{prefix} uses unsupported layer type '{layer_type}'. The engine only handles tilelayer and objectgroup.",
                field="type",
                layer_name=layer_name,
                layer_index=layer_index,
            )
        )
        return

    for field in ("x", "y"):
        if layer.get(field, 0) not in (0, 0.0):
            issues.append(
                map_validation_issue(
                    path,
                    "loader_assumption",
                    f"{prefix} has non-zero {field} offset, but CMapLoader ignores layer offsets.",
                    field=field,
                    layer_name=layer_name,
                    layer_index=layer_index,
                )
            )

    properties = get_legacy_properties(
        layer,
        path,
        issues,
        scope=prefix,
        required=True,
        layer_name=layer_name,
        layer_index=layer_index,
    )
    if properties is None:
        return

    require_engine_int_string(
        properties,
        "level",
        path,
        issues,
        scope=prefix,
        layer_name=layer_name,
        layer_index=layer_index,
    )

    if layer_type == "tilelayer":
        if "default" not in properties or not isinstance(properties.get("default"), str):
            issues.append(
                map_validation_issue(
                    path,
                    "loader_assumption",
                    f"{prefix} must define string property 'default' because CMapLoader uses it as the fallback tile id.",
                    field="default",
                    layer_name=layer_name,
                    layer_index=layer_index,
                )
            )

        if "outOfBounds" in properties and not isinstance(properties.get("outOfBounds"), str):
            issues.append(
                map_validation_issue(
                    path,
                    "loader_assumption",
                    f"{prefix} property 'outOfBounds' must be a string because CMapLoader uses it as the out-of-bounds tile id.",
                    field="outOfBounds",
                    layer_name=layer_name,
                    layer_index=layer_index,
                )
            )

        for key in ("xBound", "yBound"):
            require_engine_int_string(
                properties,
                key,
                path,
                issues,
                scope=prefix,
                layer_name=layer_name,
                layer_index=layer_index,
            )

        for key in ("wrapX", "wrapY"):
            if key in properties and not is_loader_bool(properties[key]):
                issues.append(
                    map_validation_issue(
                        path,
                        "loader_assumption",
                        f"{prefix} property '{key}' must be bool, integer, or 'true'/'false'/'1'/'0' because read_bool_property() only supports those forms.",
                        field=key,
                        layer_name=layer_name,
                        layer_index=layer_index,
                    )
                )

        if "chunks" in layer or layer.get("infinite") is True:
            issues.append(
                map_validation_issue(
                    path,
                    "loader_assumption",
                    f"{prefix} uses chunked or infinite tile data, but handleTileLayer() only reads flat layer['data'].",
                    field="chunks",
                    layer_name=layer_name,
                    layer_index=layer_index,
                )
            )

        if "encoding" in layer or "compression" in layer:
            issues.append(
                map_validation_issue(
                    path,
                    "loader_assumption",
                    f"{prefix} uses encoded or compressed tile data, but handleTileLayer() expects a raw integer array.",
                    field="data",
                    layer_name=layer_name,
                    layer_index=layer_index,
                )
            )

        width = layer.get("width")
        height = layer.get("height")
        if not is_integral_json_number(width) or int(width) <= 0:
            issues.append(
                map_validation_issue(
                    path,
                    "tiled_semantics",
                    f"{prefix} must define positive integer 'width'.",
                    field="width",
                    layer_name=layer_name,
                    layer_index=layer_index,
                )
            )
            width = None
        else:
            width = int(width)
        if not is_integral_json_number(height) or int(height) <= 0:
            issues.append(
                map_validation_issue(
                    path,
                    "tiled_semantics",
                    f"{prefix} must define positive integer 'height'.",
                    field="height",
                    layer_name=layer_name,
                    layer_index=layer_index,
                )
            )
            height = None
        else:
            height = int(height)

        if width is not None and height is not None and (width != map_width or height != map_height):
            issues.append(
                map_validation_issue(
                    path,
                    "tiled_semantics",
                    f"{prefix} has dimensions {width}x{height}, but fixed-size Tiled tile layers should match the map dimensions {map_width}x{map_height}.",
                    field="width",
                    layer_name=layer_name,
                    layer_index=layer_index,
                )
            )

        data = layer.get("data")
        if not isinstance(data, list):
            issues.append(
                map_validation_issue(
                    path,
                    "loader_assumption",
                    f"{prefix} must use a raw integer 'data' array because handleTileLayer() indexes layer['data'] directly.",
                    field="data",
                    layer_name=layer_name,
                    layer_index=layer_index,
                )
            )
            return

        if width is not None and height is not None and len(data) != width * height:
            issues.append(
                map_validation_issue(
                    path,
                    "tiled_semantics",
                    f"{prefix} data length {len(data)} does not match width * height ({width * height}) for a finite tile layer.",
                    field="data",
                    layer_name=layer_name,
                    layer_index=layer_index,
                )
            )

        if width is not None and height is not None and width != height:
            issues.append(
                map_validation_issue(
                    path,
                    "loader_assumption",
                    f"{prefix} is rectangular ({width}x{height}), but the current handleTileLayer() implementation swaps width and height and is only safe for square layers.",
                    field="width",
                    layer_name=layer_name,
                    layer_index=layer_index,
                )
            )

        for cell_index, gid in enumerate(data):
            if not is_integral_json_number(gid) or int(gid) < 0:
                issues.append(
                    map_validation_issue(
                        path,
                        "loader_assumption",
                        f"{prefix} data[{cell_index}] must be a non-negative integer GID.",
                        field="data",
                        layer_name=layer_name,
                        layer_index=layer_index,
                    )
                )
                continue

            gid = int(gid)
            if gid == 0:
                continue
            if gid & TILED_FLIP_FLAG_MASK:
                issues.append(
                    map_validation_issue(
                        path,
                        "loader_assumption",
                        f"{prefix} data[{cell_index}] uses flipped/rotated global tile ID flags, but handleTileLayer() never clears Tiled flip bits.",
                        field="data",
                        layer_name=layer_name,
                        layer_index=layer_index,
                    )
                )
                continue

            tile = tileproperties.get(str(gid - 1))
            if not isinstance(tile, dict) or not isinstance(tile.get("type"), str):
                issues.append(
                    map_validation_issue(
                        path,
                        "loader_assumption",
                        f"{prefix} data[{cell_index}] resolves to local tile id {gid - 1}, but tilesets[0].tileproperties[{gid - 1!r}].type is missing.",
                        field="tilesets[0].tileproperties",
                        layer_name=layer_name,
                        layer_index=layer_index,
                    )
                )

        return

    objects = layer.get("objects")
    if not isinstance(objects, list):
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                f"{prefix} must define an 'objects' array because handleObjectLayer() iterates layer['objects'].",
                field="objects",
                layer_name=layer_name,
                layer_index=layer_index,
            )
        )
        return

    for obj in objects:
        if not isinstance(obj, dict):
            issues.append(
                map_validation_issue(
                    path,
                    "tiled_semantics",
                    f"{prefix} contains a non-object entry in 'objects'.",
                    field="objects",
                    layer_name=layer_name,
                    layer_index=layer_index,
                )
            )
            continue
        validate_tiled_object(
            obj,
            path,
            issues,
            warnings,
            layer=layer,
            layer_index=layer_index,
            tile_width=tile_width,
            tile_height=tile_height,
        )


def validate_map_json_tiled_compatibility(path):
    issues = []
    warnings = []

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        issues.append(
            map_validation_issue(
                path,
                "invalid_json",
                f"Invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}.",
            )
        )
        return issues, warnings

    if not isinstance(data, dict):
        issues.append(map_validation_issue(path, "tiled_semantics", "Root document must be a JSON object."))
        return issues, warnings

    if data.get("type") != "map":
        issues.append(
            map_validation_issue(
                path,
                "tiled_semantics",
                "Root field 'type' must be 'map' for Tiled/TMX-compatible map data.",
                field="type",
            )
        )

    if data.get("orientation") not in (None, "orthogonal"):
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                "Only orthogonal maps are supported by the current loader assumptions.",
                field="orientation",
            )
        )

    if data.get("infinite") is True:
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                "Infinite maps are valid Tiled data, but the current loader does not support chunked layers.",
                field="infinite",
            )
        )

    for field in ("width", "height", "tilewidth", "tileheight"):
        value = data.get(field)
        if not is_integral_json_number(value) or int(value) <= 0:
            issues.append(
                map_validation_issue(
                    path,
                    "tiled_semantics",
                    f"Root field '{field}' must be a positive integer.",
                    field=field,
                )
            )

    map_width = int(data.get("width", 0)) if is_integral_json_number(data.get("width")) else None
    map_height = int(data.get("height", 0)) if is_integral_json_number(data.get("height")) else None
    tile_width = int(data.get("tilewidth", 0)) if is_integral_json_number(data.get("tilewidth")) else None
    tile_height = int(data.get("tileheight", 0)) if is_integral_json_number(data.get("tileheight")) else None

    properties = get_legacy_properties(data, path, issues, scope="map")
    if properties is not None:
        for key in ("x", "y", "z"):
            if key in properties:
                require_engine_int_string(properties, key, path, issues, scope="map")

    layers = data.get("layers")
    if not isinstance(layers, list):
        issues.append(
            map_validation_issue(
                path,
                "tiled_semantics",
                "Root field 'layers' must be an array.",
                field="layers",
            )
        )
        return issues, warnings

    tilesets = data.get("tilesets")
    if not isinstance(tilesets, list) or not tilesets:
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                "The current loader requires one embedded tileset at tilesets[0].",
                field="tilesets",
            )
        )
        return issues, warnings

    if len(tilesets) != 1:
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                f"The current loader only consumes tilesets[0], so maps must not define multiple tilesets (found {len(tilesets)}).",
                field="tilesets",
            )
        )

    first_tileset = tilesets[0]
    if not isinstance(first_tileset, dict):
        issues.append(
            map_validation_issue(
                path,
                "tiled_semantics",
                "tilesets[0] must be an object.",
                field="tilesets[0]",
            )
        )
        return issues, warnings

    if first_tileset.get("source"):
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                "External TSX/JSON tilesets are not supported because CMapLoader only reads embedded tilesets[0].tileproperties.",
                field="tilesets[0].source",
            )
        )

    if first_tileset.get("firstgid") != 1:
        issues.append(
            map_validation_issue(
                path,
                "loader_assumption",
                "The loader assumes the first tileset starts at gid 1 and never remaps by firstgid.",
                field="tilesets[0].firstgid",
            )
        )

    tileproperties = first_tileset.get("tileproperties")
    if not isinstance(tileproperties, dict):
        message = (
            "The loader requires legacy tilesets[0].tileproperties. Modern Tiled exports store per-tile metadata in "
            "tilesets[0].tiles[]."
        )
        issues.append(map_validation_issue(path, "loader_assumption", message, field="tilesets[0].tileproperties"))
        tileproperties = {}

    for layer_index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            issues.append(
                map_validation_issue(
                    path,
                    "tiled_semantics",
                    "Each layer entry must be an object.",
                    field="layers",
                    layer_index=layer_index,
                )
            )
            continue
        validate_tiled_layer(
            layer,
            path,
            issues,
            warnings,
            layer_index=layer_index,
            map_width=map_width,
            map_height=map_height,
            tile_width=tile_width,
            tile_height=tile_height,
            tileproperties=tileproperties,
        )

    return issues, warnings


def resolve_object_class(configs, type_name):
    conf = configs.get(type_name, {"class": type_name})
    seen = set()
    while isinstance(conf, dict) and "ref" in conf:
        ref = conf["ref"]
        if ref in seen:
            raise AssertionError(f"Circular ref while resolving {type_name}: {ref}")
        seen.add(ref)
        conf = configs.get(ref, {"class": ref})
    return conf.get("class")


def quest_names(player):
    names = []
    for quest in player.getQuests():
        if hasattr(quest, "getTypeId"):
            quest_id = quest.getTypeId()
            if quest_id:
                names.append(quest_id)
                continue
        names.append(quest.getName())
    return sorted(names)


def walkthrough_log_path(map_name):
    TEST_OUTPUT_DIR.mkdir(exist_ok=True)
    return TEST_OUTPUT_DIR / f"walkthrough_{map_name}.json"


def write_walkthrough_log(map_name, log):
    walkthrough_log_path(map_name).write_text(json.dumps(log, indent=2, sort_keys=True))


def walkthrough_test_map():
    g, game_map, player = load_game_map_with_player("test")
    teleporter_1_def = find_map_object_definition("test", "teleporter1")
    teleporter_2_def = find_map_object_definition("test", "teleporter2")
    ground_hole_def = find_map_object_definition("test", "groundHole")
    teleporter = find_runtime_object(game_map, "teleporter1")
    ground_hole = find_runtime_object(game_map, "groundHole")

    player.setCoords(teleporter.getCoords())
    after_teleport = player.getCoords()

    turn_after_advance = game_map.getTurn()

    player.setCoords(ground_hole.getCoords())
    after_ground_hole = player.getCoords()

    assert (after_teleport.x, after_teleport.y, after_teleport.z) == (
        teleporter_2_def["x"] // 32,
        teleporter_2_def["y"] // 32,
        0,
    )
    assert (after_ground_hole.x, after_ground_hole.y, after_ground_hole.z) == (
        ground_hole_def["x"] // 32,
        ground_hole_def["y"] // 32,
        -1,
    )
    return {
        "map": "test",
        "teleporter_from": [teleporter_1_def["x"] // 32, teleporter_1_def["y"] // 32, 0],
        "teleporter_to": [after_teleport.x, after_teleport.y, after_teleport.z],
        "ground_hole_exit": [after_ground_hole.x, after_ground_hole.y, after_ground_hole.z],
        "turn_after_advance": turn_after_advance,
    }


def walkthrough_siege_map():
    game = load_game_module()
    original_randint = game.randint
    try:
        randint_values = iter([25, 10, 1, 25, 1])

        def deterministic_randint(lower, upper):
            return next(randint_values, lower)

        game.randint = deterministic_randint

        g, game_map, player = load_game_map_with_player("siege")
        spawn_names = ["spawnPoint1", "spawnPoint2", "spawnPoint3", "spawnPoint4"]
        for name in spawn_names:
            find_map_object_definition("siege", name)

        advance_turns(g, 2)

        enabled_spawn_points = [
            find_runtime_object(game_map, name)
            for name in spawn_names
            if game_map.getObjectByName(name).getBoolProperty("enabled")
        ]
        siege_units = []
        game_map.forObjects(
            lambda ob: siege_units.append(ob.getName()),
            lambda ob: ob.getStringProperty("affiliation") == "siege",
        )

        assert enabled_spawn_points, "No siege spawn point was enabled during the deterministic walkthrough."
        assert siege_units, "No siege attackers spawned from the enabled gate."
        return {
            "map": "siege",
            "enabled_gates": [gate.getName() for gate in enabled_spawn_points],
            "player_coords": [player.getCoords().x, player.getCoords().y, player.getCoords().z],
            "spawned_enemies": sorted(siege_units),
        }
    finally:
        game.randint = original_randint


def walkthrough_ritual_map():
    g, game_map = load_game_map("ritual")
    for name in ("anchorNorth", "anchorCrypt", "anchorSanctum"):
        find_map_object_definition("ritual", name)

    game_map.removeObjectByName("anchorNorth")
    turn_after_countdown = advance_map_only(game_map, 5)
    game_map.removeObjectByName("anchorCrypt")
    game_map.removeObjectByName("anchorSanctum")
    leader = find_runtime_object(game_map, "ritualLeader")
    advance_map_only(game_map, 70)

    assert game_map.getBoolProperty("ritual_started"), "The ritual should start during the walkthrough."
    assert game_map.getBoolProperty("anchors_destroyed"), "All ritual anchors should be destroyed."
    assert game_map.getBoolProperty("leader_spawned"), "The ritual leader should spawn after all anchors fall."
    assert leader.getName() == "ritualLeader", "The ritual leader should be present after the anchor phase."
    assert game_map.getBoolProperty("captive_lost"), "The countdown failure path should mark the captive lost."
    assert game_map.getBoolProperty("bad_ending"), "The ritual walkthrough should reach the bad ending."
    assert game_map.getBoolProperty("ritual_finished"), "The ritual should finish after the countdown expires."
    return {
        "map": "ritual",
        "anchors_destroyed_count": game_map.getNumericProperty("anchors_destroyed_count"),
        "countdown_after_turns": game_map.getNumericProperty("ritual_countdown"),
        "turn_after_countdown": turn_after_countdown,
        "leader_spawned": game_map.getBoolProperty("leader_spawned"),
        "captive_lost": game_map.getBoolProperty("captive_lost"),
        "bad_ending": game_map.getBoolProperty("bad_ending"),
        "note": "Ritual currently cannot be started with startGameWithPlayer, so this walkthrough covers the deterministic no-player failure path.",
    }


def walkthrough_nouraajd_map():
    g, game_map, player = load_game_map_with_player("nouraajd")
    for name in ("cave1", "gooby1", "catacombs", "cave2"):
        if name != "gooby1":
            find_map_object_definition("nouraajd", name)

    game_map.removeObjectByName("cave1")
    gooby = find_runtime_object(game_map, "gooby1")
    game_map.removeObjectByName(gooby.getName())
    game_map.removeObjectByName("catacombs")
    game_map.removeObjectByName("cave2")

    assert game_map.getBoolProperty("completed_rolf"), "The cave1 trigger should complete the Rolf lead."
    assert player.hasItem(lambda it: it.getName() == "skullOfRolf"), "The cave1 trigger should award Rolf's skull."
    assert game_map.getBoolProperty("completed_gooby"), "Defeating Gooby should complete the main quest flag."
    assert player.hasItem(lambda it: it.getName() == "holyRelic"), "The catacombs trigger should award the holy relic."
    assert game_map.getBoolProperty("OCTOBOGZ_SLAIN"), "The cave2 trigger should mark the OctoBogz slain."
    return {
        "map": "nouraajd",
        "completed_rolf": game_map.getBoolProperty("completed_rolf"),
        "completed_gooby": game_map.getBoolProperty("completed_gooby"),
        "octobogz_slain": game_map.getBoolProperty("OCTOBOGZ_SLAIN"),
        "has_skull_of_rolf": player.hasItem(lambda it: it.getName() == "skullOfRolf"),
        "has_holy_relic": player.hasItem(lambda it: it.getName() == "holyRelic"),
        "quests": quest_names(player),
    }


WALKTHROUGHS = {
    "nouraajd": walkthrough_nouraajd_map,
    "ritual": walkthrough_ritual_map,
    "siege": walkthrough_siege_map,
    "test": walkthrough_test_map,
}


def execute_walkthrough(map_name):
    try:
        log = WALKTHROUGHS[map_name]()
        success = True
    except Exception as exc:
        success = False
        log = {
            "map": map_name,
            "error": str(exc),
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc(),
        }
    write_walkthrough_log(map_name, log)
    return success, json.dumps(log)


def run_walkthrough(map_name, fn):
    command = [sys.executable, str(REPO_ROOT / "test.py"), f"GameTest.test_map_walkthrough_{map_name}"]
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    log = {}
    log_path = walkthrough_log_path(map_name)
    if log_path.exists():
        try:
            log = json.loads(log_path.read_text())
        except json.JSONDecodeError:
            log = {"map": map_name, "raw_log": log_path.read_text()}

    if completed.returncode != 0:
        log.update(
            {
                "map": map_name,
                "returncode": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
                "walkthrough": fn.__name__,
            }
        )
        write_walkthrough_log(map_name, log)
        return False, log

    if not log:
        log = {"map": map_name, "stdout": completed.stdout.strip(), "walkthrough": fn.__name__}
        write_walkthrough_log(map_name, log)
    return True, log


class GameTest(unittest.TestCase):
    @game_test
    def test_invalid_inputs(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        self.assertIsNone(g.createObject("DefinitelyMissingType"))
        self.assertIsNone(g.getMap().getObjectByName("DefinitelyMissingObject"))
        g.getMap().removeObjectByName("DefinitelyMissingObject")
        return True, ""

    @game_test
    def test_crafting_runtime_applies_recipe(self):
        import crafting

        g, game_map, player = load_game_map_with_player("nouraajd")
        player.setNumericProperty("gold", 100)

        while player.countItems("LesserLifePotion") > 0:
            player.removeItem(lambda it: it.getTypeId() == "LesserLifePotion", True)
        while player.countItems("LifePotion") > 0:
            player.removeItem(lambda it: it.getTypeId() == "LifePotion", True)

        player.addItem("LesserLifePotion")
        player.addItem("LesserLifePotion")

        before = crafting.count_inventory_matches(player, "LesserLifePotion")
        result = crafting.craft_recipe(g, player, "brew_life_potion")
        after = crafting.count_inventory_matches(player, "LesserLifePotion")
        crafted_count = player.countItems("LifePotion")
        remaining_gold = player.getNumericProperty("gold")

        assert result["ok"], f"Crafting failed: {result}"
        assert before == 2 and after == 0, f"Unexpected reagent counts: before={before}, after={after}"
        assert crafted_count >= 1, "Player did not receive the crafted item."
        assert remaining_gold == 80, f"Expected 80 gold after crafting, got {remaining_gold}"

        return True, {
            "before_reagents": before,
            "after_reagents": after,
            "crafted_count": crafted_count,
            "remaining_gold": remaining_gold,
        }

    @game_test
    def test_crafting_transactions_are_atomic(self):
        import crafting

        g, game_map, player = load_game_map_with_player("nouraajd")
        base_gold = 100

        def clear_item(item_id):
            while player.countItems(item_id) > 0:
                player.removeItem(lambda it, tid=item_id: it.getTypeId() == tid, True)

        def reset():
            player.setNumericProperty("gold", base_gold)
            for item_id in ("LesserLifePotion", "LifePotion", "GreaterLifePotion", "ManaPotion"):
                clear_item(item_id)

        reset()

        # Missing ingredient never consumes existing reagents or gold
        player.addItem("LesserLifePotion")
        result = crafting.craft_recipe(g, player, "brew_life_potion")
        assert not result["ok"] and result["reason"] == "missing:LesserLifePotion"
        assert player.countItems("LesserLifePotion") == 1
        assert player.getNumericProperty("gold") == base_gold

        # Insufficient gold keeps inventory intact
        reset()
        player.addItem("LesserLifePotion")
        player.addItem("LesserLifePotion")
        player.setNumericProperty("gold", 10)
        result = crafting.craft_recipe(g, player, "brew_life_potion")
        assert not result["ok"] and result["reason"] == "missing:gold"
        assert player.countItems("LesserLifePotion") == 2
        assert player.getNumericProperty("gold") == 10

        # Successful craft consumes reagents and gold exactly once
        reset()
        player.addItem("LesserLifePotion")
        player.addItem("LesserLifePotion")
        result = crafting.craft_recipe(g, player, "brew_life_potion")
        assert result["ok"]
        assert player.countItems("LesserLifePotion") == 0
        assert player.countItems("LifePotion") >= 1
        assert player.getNumericProperty("gold") == base_gold - 20

        # RNG failure leaves inventory and gold untouched
        reset()
        player.addItem("LifePotion")
        player.addItem("LifePotion")
        player.setNumericProperty("gold", 200)
        original_randint = crafting.randint

        def always_fail(*args, **kwargs):
            return 100

        crafting.randint = always_fail
        try:
            result = crafting.craft_recipe(g, player, "blend_greater_life_potion")
        finally:
            crafting.randint = original_randint

        assert not result["ok"] and result["reason"] == "failed"
        assert player.countItems("LifePotion") == 2
        assert player.countItems("GreaterLifePotion") == 0
        assert player.getNumericProperty("gold") == 200

        return True, ""

    @game_test
    def test_potions_are_not_consumed_at_full_resources(self):
        g, _game_map, player = load_game_map_with_player("nouraajd", "Sorcerer")

        def clear_item(item_id):
            while player.countItems(item_id) > 0:
                player.removeItem(lambda it, tid=item_id: it.getTypeId() == tid, True)

        clear_item("LesserLifePotion")
        clear_item("LesserManaPotion")

        life_potion = g.createObject("LesserLifePotion")
        mana_potion = g.createObject("LesserManaPotion")
        player.addItem(life_potion)
        player.addItem(mana_potion)
        player.setHp(player.getHpMax())
        player.addManaProc(0)
        full_mana = player.getMana()

        hp_ratio_before = player.getHpRatio()
        mana_before = player.getMana()

        player.useItem(life_potion)
        player.useItem(mana_potion)

        assert player.getHpRatio() == hp_ratio_before
        assert player.getMana() == mana_before
        assert player.countItems("LesserLifePotion") == 1
        assert player.countItems("LesserManaPotion") == 1

        player.setHp(max(1, player.getHpMax() - 10))
        player.setMana(max(0, full_mana - 10))

        player.useItem(life_potion)
        player.useItem(mana_potion)

        assert player.getHpRatio() == 100
        assert player.getMana() == full_mana
        assert player.countItems("LesserLifePotion") == 0
        assert player.countItems("LesserManaPotion") == 0

        return True, json.dumps(
            {
                "hp_ratio_before": hp_ratio_before,
                "mana_before": mana_before,
                "hp_ratio_after": player.getHpRatio(),
                "mana_after": player.getMana(),
                "life_potions": player.countItems("LesserLifePotion"),
                "mana_potions": player.countItems("LesserManaPotion"),
            },
            sort_keys=True,
        )

    @game_test
    def test_lava_tile_is_walkable(self):
        game = load_game_module()
        g, game_map, player = load_game_map_with_player("test", "Warrior")
        game_map.removeAll(lambda obj: obj.getName() != "player")

        start = player.getCoords()
        lava = game.Coords(start.x + 1, start.y, start.z)
        game_map.replaceTile("LavaTile", lava)

        self.assertTrue(game_map.canStep(lava))
        set_player_target(player, lava)
        game_map.move()

        coords = player.getCoords()
        self.assertEqual((coords.x, coords.y, coords.z), (lava.x, lava.y, lava.z))

        return True, json.dumps(
            {
                "lava": [lava.x, lava.y, lava.z],
                "player": [coords.x, coords.y, coords.z],
            },
            sort_keys=True,
        )

    @game_test
    def test_road_tile_heals_only_on_successful_step(self):
        game = load_game_module()
        g, game_map, player = load_game_map_with_player("test", "Warrior")
        game_map.removeAll(lambda obj: obj.getName() != "player")

        start = player.getCoords()
        road = game.Coords(start.x + 1, start.y, start.z)
        game_map.replaceTile("RoadTile", road)

        player.setHp(max(1, player.getHpMax() - 3))
        hp_before_step = player.getNumericProperty("hp")
        set_player_target(player, road)
        game_map.move()
        self.assertEqual(player.getNumericProperty("hp"), hp_before_step + 1)
        self.assertEqual((player.getCoords().x, player.getCoords().y, player.getCoords().z), (road.x, road.y, road.z))

        hp_on_road = player.getNumericProperty("hp")
        game_map.move()
        self.assertEqual(player.getNumericProperty("hp"), hp_on_road)

        return True, json.dumps(
            {
                "hp_before_step": hp_before_step,
                "hp_after_step": player.getNumericProperty("hp"),
                "coords_after_step": [player.getCoords().x, player.getCoords().y, player.getCoords().z],
            },
            sort_keys=True,
        )

    @game_test
    def test_disabled_teleporter_does_not_publish_waypoint(self):
        _g, game_map, _player = load_game_map_with_player("test", "Warrior")
        active_teleporter = find_runtime_object(game_map, "teleporter1")
        teleporter = find_runtime_object(game_map, "teleporter2")
        teleporter_coords = teleporter.getCoords()

        self.assertFalse(teleporter.getBoolProperty("waypoint"))

        advance_map_only(game_map, 1)

        self.assertTrue(active_teleporter.getBoolProperty("waypoint"))
        self.assertEqual(teleporter_coords.x, active_teleporter.getNumericProperty("x"))
        self.assertEqual(teleporter_coords.y, active_teleporter.getNumericProperty("y"))
        self.assertEqual(teleporter_coords.z, active_teleporter.getNumericProperty("z"))
        self.assertFalse(teleporter.getBoolProperty("enabled"))
        self.assertFalse(teleporter.getBoolProperty("waypoint"))

        return True, json.dumps(
            {
                "active_name": active_teleporter.getName(),
                "active_waypoint": active_teleporter.getBoolProperty("waypoint"),
                "disabled_name": teleporter.getName(),
                "disabled_enabled": teleporter.getBoolProperty("enabled"),
                "disabled_waypoint": teleporter.getBoolProperty("waypoint"),
            },
            sort_keys=True,
        )

    @game_test
    def test_take_mana_clamps_at_zero(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")

        creature = g.createObject("CCreature")
        stats = g.createObject("Stats")
        stats.mainStat = "intelligence"
        stats.intelligence = 2
        creature.baseStats = stats

        mana_max = 14
        creature.setMana(mana_max)
        creature.takeMana(3)
        mana_after_partial_use = creature.getMana()
        creature.takeMana(mana_max + 20)

        assert mana_after_partial_use == mana_max - 3
        assert creature.getMana() == 0

        return True, json.dumps(
            {
                "mana_max": mana_max,
                "mana_after_partial_use": mana_after_partial_use,
                "mana_after_overdraw": creature.getMana(),
            },
            sort_keys=True,
        )

    @game_test
    def test_unequipping_armor_clamps_hp_and_mana_to_new_caps(self):
        _g_hp, _game_map_hp, warrior = load_game_map_with_player("test", "Warrior")
        warrior_hp_with_armor = warrior.getHpMax()
        warrior.setHp(warrior_hp_with_armor)
        warrior.unequipArmor()
        warrior_hp_without_armor = warrior.getHpMax()

        self.assertGreater(warrior_hp_with_armor, warrior_hp_without_armor)
        self.assertEqual(warrior_hp_without_armor, warrior.getNumericProperty("hp"))
        self.assertEqual(100, warrior.getHpRatio())

        _g_mana, _game_map_mana, sorcerer = load_game_map_with_player("test", "Sorcerer")
        sorcerer_stats = sorcerer.getStats()
        sorcerer_mana_with_armor = sorcerer_stats.getNumericProperty(sorcerer_stats.getStringProperty("mainStat")) * 7
        sorcerer.addManaProc(0)
        sorcerer.unequipArmor()
        sorcerer_stats_after_unequip = sorcerer.getStats()
        sorcerer_mana_without_armor = (
            sorcerer_stats_after_unequip.getNumericProperty(sorcerer_stats_after_unequip.getStringProperty("mainStat"))
            * 7
        )

        self.assertGreater(sorcerer_mana_with_armor, sorcerer_mana_without_armor)
        self.assertEqual(sorcerer_mana_without_armor, sorcerer.getMana())

        return True, json.dumps(
            {
                "warrior_hp_with_armor": warrior_hp_with_armor,
                "warrior_hp_without_armor": warrior_hp_without_armor,
                "warrior_hp": warrior.getNumericProperty("hp"),
                "sorcerer_mana_with_armor": sorcerer_mana_with_armor,
                "sorcerer_mana_without_armor": sorcerer_mana_without_armor,
                "sorcerer_mana": sorcerer.getMana(),
            },
            sort_keys=True,
        )

    @game_test
    def test_crafting_config_is_valid(self):
        crafting_path = REPO_ROOT / "res/config/crafting.json"
        buildings_path = REPO_ROOT / "res/config/buildings.json"
        crafting_data = json.loads(crafting_path.read_text())
        building_data = json.loads(buildings_path.read_text())
        configs = load_object_configs()

        station_ids = {
            props.get("properties", {}).get("craftingStationId")
            for props in building_data.values()
            if isinstance(props, dict)
        }
        station_ids.discard(None)

        errors = []
        seen_recipes = set()

        def normalize_entries(entries):
            normalized = []
            for entry in entries or []:
                if isinstance(entry, str):
                    normalized.append({"item": entry, "count": 1})
                elif isinstance(entry, dict):
                    item_id = entry.get("item") or entry.get("item_id") or entry.get("itemId") or entry.get("id")
                    normalized.append({"item": item_id, "count": entry.get("count", 1)})
                else:
                    normalized.append({"item": None, "count": None})
            return normalized

        def normalized_outputs(recipe):
            outputs = recipe.get("outputs")
            if outputs is None and isinstance(recipe.get("output"), dict):
                outputs = [recipe["output"]]
            return normalize_entries(outputs or [])

        for recipe_id, recipe in crafting_data.items():
            if recipe_id in seen_recipes:
                errors.append(f"Duplicate recipe id: {recipe_id}")
                continue
            seen_recipes.add(recipe_id)

            station_id = recipe.get("station")
            if not station_id:
                errors.append(f"{recipe_id}: missing station")
            elif station_id not in station_ids:
                errors.append(f"{recipe_id}: unknown station '{station_id}'")

            inputs = normalize_entries(recipe.get("inputs", []))
            if not inputs:
                errors.append(f"{recipe_id}: no inputs defined")
            for entry in inputs:
                item_id = entry["item"]
                count = entry["count"]
                if not item_id:
                    errors.append(f"{recipe_id}: input missing item id")
                    continue
                if item_id not in configs:
                    errors.append(f"{recipe_id}: input item '{item_id}' is undefined")
                try:
                    numeric_count = int(count)
                except (TypeError, ValueError):
                    errors.append(f"{recipe_id}: input '{item_id}' has invalid count '{count}'")
                    continue
                if numeric_count <= 0:
                    errors.append(f"{recipe_id}: input '{item_id}' has non-positive count {count}")

            outputs = normalized_outputs(recipe)
            if not outputs:
                errors.append(f"{recipe_id}: no outputs defined")
            for entry in outputs:
                item_id = entry["item"]
                count = entry["count"]
                if not item_id:
                    errors.append(f"{recipe_id}: output missing item id")
                    continue
                if item_id not in configs:
                    errors.append(f"{recipe_id}: output item '{item_id}' is undefined")
                try:
                    numeric_count = int(count)
                except (TypeError, ValueError):
                    errors.append(f"{recipe_id}: output '{item_id}' has invalid count '{count}'")
                    continue
                if numeric_count <= 0:
                    errors.append(f"{recipe_id}: output '{item_id}' has non-positive count {count}")

            gold_cost = recipe.get("gold", recipe.get("gold_cost", 0))
            try:
                gold_value = int(gold_cost)
            except (TypeError, ValueError):
                errors.append(f"{recipe_id}: gold cost '{gold_cost}' is invalid")
                gold_value = None
            if gold_value is not None and gold_value < 0:
                errors.append(f"{recipe_id}: gold cost {gold_cost} is negative")

            success_chance = recipe.get("successChance", recipe.get("success_chance", 100))
            if not isinstance(success_chance, int):
                try:
                    success_chance = int(success_chance)
                except (TypeError, ValueError):
                    errors.append(f"{recipe_id}: success chance '{success_chance}' is invalid")
                    success_chance = None
            if success_chance is not None and not (0 <= success_chance <= 100):
                errors.append(f"{recipe_id}: success chance {success_chance} is outside 0-100")

            if "unlockQuest" in recipe:
                errors.append(f"{recipe_id}: unlockQuest is unsupported")
            unlock_flag = recipe.get("unlockFlag")
            if unlock_flag is not None and not str(unlock_flag).strip():
                errors.append(f"{recipe_id}: unlockFlag is empty")

        return not errors, json.dumps({"errors": errors})

    @game_test
    def test_map_transition_and_bounds(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "nouraajd", "Warrior")
        nouraajd = g.getMap()
        player = nouraajd.getPlayer()
        self.assertTrue(nouraajd.canStep(player.getCoords()))
        self.assertFalse(nouraajd.canStep(game.Coords(-1, -1, 0)))
        self.assertFalse(nouraajd.canStep(game.Coords(9999, 9999, 0)))

        return True, ""

    @game_test
    def test_moveable_objects_respect_non_steppable_map_objects(self):
        game = load_game_module()

        g, game_map, player = load_game_map_with_player("test")
        origin = player.getCoords()

        target = None
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            candidate = game.Coords(origin.x + dx, origin.y + dy, origin.z)
            if game_map.canStep(candidate):
                target = candidate
                break

        self.assertIsNotNone(target, "Expected at least one adjacent walkable tile on the test map")

        blocker = g.createObject("CEvent")
        blocker.setStringProperty("name", "movementBlocker")
        blocker.setBoolProperty("canStep", False)
        game_map.addObject(blocker)
        blocker.moveTo(target.x, target.y, target.z)

        self.assertFalse(game_map.canStep(target))

        player.moveTo(target.x, target.y, target.z)
        current = player.getCoords()
        self.assertEqual((current.x, current.y, current.z), (origin.x, origin.y, origin.z))

        return True, json.dumps(
            {
                "origin": [origin.x, origin.y, origin.z],
                "target": [target.x, target.y, target.z],
                "player": [current.x, current.y, current.z],
            }
        )

    @game_test
    def test_change_map_waits_for_event_loop_after_move_event(self):
        game = load_game_module()

        g, game_map, player = load_game_map_with_player("test")
        origin = player.getCoords()
        target = find_adjacent_walkable_tile(game_map, origin)
        controller = get_player_controller(player)
        lifecycle = []

        class DeferredChangeMap(game.CEvent):
            def onEnter(self, event):
                lifecycle.append(
                    {
                        "phase": "entered",
                        "map": self.getMap().mapName,
                        "turn": self.getMap().getTurn(),
                        "cause": event.getCause().getName(),
                    }
                )
                self.getMap().getGame().changeMap("ritual")

        g.getObjectHandler().registerType("DeferredChangeMap", DeferredChangeMap)
        switcher = g.createObject("DeferredChangeMap")
        switcher.name = "deferredChangeMap"
        game_map.addObject(switcher)
        switcher.moveTo(target.x, target.y, target.z)

        controller.setTarget(player, target)
        game_map.move()

        self.assertEqual("test", g.getMap().mapName)
        self.assertEqual(1, g.getMap().getTurn())
        self.assertEqual(
            (target.x, target.y, target.z), (player.getCoords().x, player.getCoords().y, player.getCoords().z)
        )
        self.assertEqual(
            [{"phase": "entered", "map": "test", "turn": 0, "cause": "player"}],
            lifecycle,
            "onEnter should run during the move, before the deferred map swap is processed.",
        )

        pump_event_loop(3)

        self.assertEqual("ritual", g.getMap().mapName)
        self.assertEqual(1, g.getMap().getTurn())
        self.assertTrue(g.getMap().getPlayer() == player)

        return True, json.dumps(
            {
                "before_event_loop": {
                    "map": "test",
                    "turn": 1,
                    "player": [target.x, target.y, target.z],
                },
                "after_event_loop": {
                    "map": g.getMap().mapName,
                    "turn": g.getMap().getTurn(),
                    "player": [
                        g.getMap().getPlayer().getCoords().x,
                        g.getMap().getPlayer().getCoords().y,
                        g.getMap().getPlayer().getCoords().z,
                    ],
                },
                "lifecycle": lifecycle,
            },
            sort_keys=True,
        )

    @game_test
    def test_toroidal_map_wraps_and_survives_save_load(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        game_map = g.getMap()
        player = game_map.getPlayer()

        initial_y = player.getCoords().y
        self.assertTrue(game_map.canStep(game.Coords(-1, initial_y, 0)))
        self.assertTrue(game_map.canStep(game.Coords(player.getCoords().x, -1, 0)))

        player.moveTo(-1, initial_y, 0)
        after_horizontal = player.getCoords()
        self.assertEqual((after_horizontal.x, after_horizontal.y, after_horizontal.z), (25, initial_y, 0))

        player.moveTo(after_horizontal.x, -1, 0)
        after_vertical = player.getCoords()
        self.assertEqual((after_vertical.x, after_vertical.y, after_vertical.z), (25, 25, 0))

        save_name = "toroidal_wrap_regression"
        game.CMapLoader.save(game_map, save_name)

        loaded_game = game.CGameLoader.loadGame()
        game.CGameLoader.loadSavedGame(loaded_game, save_name)
        loaded_map = loaded_game.getMap()
        loaded_player = loaded_map.getPlayer()

        self.assertTrue(loaded_map.canStep(game.Coords(-1, loaded_player.getCoords().y, 0)))
        loaded_player.moveTo(-1, loaded_player.getCoords().y, 0)
        self.assertEqual(
            (loaded_player.getCoords().x, loaded_player.getCoords().y, loaded_player.getCoords().z), (25, 25, 0)
        )

        return True, json.dumps(
            {
                "wrapped_horizontal": [after_horizontal.x, after_horizontal.y, after_horizontal.z],
                "wrapped_vertical": [after_vertical.x, after_vertical.y, after_vertical.z],
                "loaded_player": [
                    loaded_player.getCoords().x,
                    loaded_player.getCoords().y,
                    loaded_player.getCoords().z,
                ],
            }
        )

    @game_test
    def test_map_proxy_cells_remain_populated_after_player_move(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        game.CGameLoader.startGameWithPlayer(g, "test", "Sorcerer")
        pump_event_loop()

        initial_counts = get_map_proxy_child_counts(g)
        self.assertTrue(initial_counts, "Expected serialized map proxies after GUI initialization")
        self.assertEqual(sum(count == 0 for count in initial_counts), 0)

        game_map = g.getMap()
        player = game_map.getPlayer()
        controller = get_player_controller(player)

        def move_player(dx):
            coords = player.getCoords()
            target = game.Coords(coords.x + dx, coords.y, coords.z)
            self.assertTrue(game_map.canStep(target), f"Expected walkable move target {target.x},{target.y},{target.z}")
            controller.setTarget(player, target)
            game_map.move()
            pump_event_loop()
            return get_map_proxy_child_counts(g)

        east_counts = move_player(1)
        west_counts = move_player(-1)

        self.assertEqual(sum(count == 0 for count in east_counts), 0)
        self.assertEqual(sum(count == 0 for count in west_counts), 0)

        return True, json.dumps(
            {
                "initial_proxy_count": len(initial_counts),
                "initial_empty_proxies": sum(count == 0 for count in initial_counts),
                "empty_after_east_move": sum(count == 0 for count in east_counts),
                "empty_after_west_move": sum(count == 0 for count in west_counts),
            }
        )

    @game_test
    def test_inventory_panel_refreshes_only_after_event_loop_drains(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        panel = g.getGuiHandler().openPanel("inventoryPanel")
        pump_event_loop()

        player = g.getMap().getPlayer()
        before_totals = get_panel_proxy_child_totals(panel)

        sword = g.createObject("Sword")
        player.addItem(sword)
        after_add_without_pump = get_panel_proxy_child_totals(panel)
        pump_event_loop()
        after_add_with_pump = get_panel_proxy_child_totals(panel)

        player.removeItem(lambda item: item == sword, False)
        after_remove_without_pump = get_panel_proxy_child_totals(panel)
        pump_event_loop()
        after_remove_with_pump = get_panel_proxy_child_totals(panel)

        self.assertEqual(before_totals, after_add_without_pump)
        self.assertEqual(before_totals[0] + 1, after_add_with_pump[0])
        self.assertEqual(after_add_with_pump, after_remove_without_pump)
        self.assertEqual(before_totals, after_remove_with_pump)

        return True, json.dumps(
            {
                "before": before_totals,
                "after_add_without_pump": after_add_without_pump,
                "after_add_with_pump": after_add_with_pump,
                "after_remove_without_pump": after_remove_without_pump,
                "after_remove_with_pump": after_remove_with_pump,
            },
            sort_keys=True,
        )

    @game_test
    def test_out_of_bounds_tile_override_survives_save_load(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "ritual", "Warrior")
        game_map = g.getMap()
        player = game_map.getPlayer()

        initial_coords = game.Coords(-1, player.getCoords().y, 0)
        self.assertEqual("WaterTile", materialized_tile_type(game, game_map, initial_coords))

        save_name = "out_of_bounds_tile_override_regression"
        game.CMapLoader.save(game_map, save_name)

        loaded_game = game.CGameLoader.loadGame()
        game.CGameLoader.loadSavedGame(loaded_game, save_name)
        loaded_map = loaded_game.getMap()
        loaded_player = loaded_map.getPlayer()

        loaded_coords = game.Coords(25, loaded_player.getCoords().y, 0)
        self.assertEqual("WaterTile", materialized_tile_type(game, loaded_map, loaded_coords))

        return True, json.dumps(
            {
                "initial_out_of_bounds_tile": {
                    "coords": [initial_coords.x, initial_coords.y, initial_coords.z],
                    "typeId": materialized_tile_type(game, game_map, initial_coords),
                },
                "loaded_out_of_bounds_tile": {
                    "coords": [loaded_coords.x, loaded_coords.y, loaded_coords.z],
                    "typeId": materialized_tile_type(game, loaded_map, loaded_coords),
                },
            }
        )

    @game_test
    def test_player_recovery_from_map_objects_preserves_state(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        recovered_player = g.getMap().getPlayer()

        game.CGameLoader.startGame(g, "test")
        game_map = g.getMap()
        game_map.removeAll(lambda obj: True)
        recovered_player.moveTo(1, 2, 0)
        game_map.addObject(recovered_player)

        recovered_player = game_map.getPlayer()
        recovered_again = game_map.getPlayer()
        player_count = sum(1 for obj in game_map.getObjects() if obj.getName() == "player")
        recovered_coords = recovered_player.getCoords()
        recovered_again_coords = recovered_again.getCoords()

        self.assertEqual((1, 2, 0), (recovered_coords.x, recovered_coords.y, recovered_coords.z))
        self.assertEqual((1, 2, 0), (recovered_again_coords.x, recovered_again_coords.y, recovered_again_coords.z))
        self.assertEqual(1, player_count)
        self.assertIsNotNone(recovered_player.getController())
        self.assertIsNotNone(recovered_player.getFightController())

        stats = recovered_player.getStats()
        main_value = getattr(stats, stats.mainStat)
        expected_mana_regen = main_value // 10 + 1
        mana_max = main_value * 7

        recovered_player.setMana(0)
        game_map.move()
        mana_after_first_turn = recovered_player.getMana()
        game_map.move()
        mana_after_second_turn = recovered_player.getMana()

        self.assertEqual(expected_mana_regen, mana_after_first_turn)
        self.assertEqual(min(expected_mana_regen * 2, mana_max), mana_after_second_turn)
        recovered_coords = recovered_player.getCoords()
        self.assertEqual(1, sum(1 for obj in game_map.getObjects() if obj.getName() == "player"))

        return True, json.dumps(
            {
                "coords": [recovered_coords.x, recovered_coords.y, recovered_coords.z],
                "player_count": player_count,
                "mana_after_first_turn": mana_after_first_turn,
                "mana_after_second_turn": mana_after_second_turn,
                "expected_mana_regen": expected_mana_regen,
            }
        )

    @game_test
    def test_toroidal_target_controller_prefers_wrapped_step(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        game_map = g.getMap()
        game_map.replaceTile("RoadTile", game.Coords(25, 13, 0))
        game_map.replaceTile("SwampTile", game.Coords(1, 13, 0))

        target = g.createObject("CEvent")
        target.setStringProperty("name", "wrapTarget")
        game_map.addObject(target)
        target.moveTo(25, 13, 0)

        chaser = g.createObject("Cultist")
        controller = g.createObject("CTargetController")
        controller.setTarget("wrapTarget")
        chaser.setController(controller)
        chaser.setBoolProperty("npc", True)
        game_map.addObject(chaser)
        chaser.moveTo(0, 13, 0)

        game_map.move()

        coords = chaser.getCoords()
        self.assertEqual((coords.x, coords.y, coords.z), (25, 13, 0))
        return True, json.dumps({"chaser_coords": [coords.x, coords.y, coords.z]})

    @game_test
    def test_new_player_classes_and_resources(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        player_types = set(g.getObjectHandler().getAllSubTypes("CPlayer"))
        self.assertIn("Inquisitor", player_types)
        self.assertIn("Wayfarer", player_types)

        expected_animations = {
            "Inquisitor": "images/players/inquisitor",
            "Wayfarer": "images/players/wayfarer",
        }
        for player_type in ("Inquisitor", "Wayfarer"):
            g = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(g, "nouraajd", player_type)
            player = g.getMap().getPlayer()
            self.assertEqual(player.getStringProperty("label"), player_type)
            self.assertEqual(player.getStringProperty("animation"), expected_animations[player_type])

        for image_name in ("inquisitor.png", "wayfarer.png"):
            self.assertTrue((build_dir / "images" / "players" / image_name).exists(), image_name)

        required_types = (
            "ExposeCorruption",
            "SanctifiedWard",
            "WayfarersStride",
            "SmugglersMark",
            "ExposeCorruptionEffect",
            "SanctifiedWardEffect",
            "WayfarersStrideEffect",
            "SmugglersMarkEffect",
        )
        missing = [type_name for type_name in required_types if g.createObject(type_name) is None]
        self.assertEqual(missing, [])

        return True, ""

    def make_multi_enemy_combat_fixture(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        attacker = g.createObject("Warrior")
        attacker.baseStats.hit = 100
        attacker.baseStats.dmgMin = 10
        attacker.baseStats.dmgMax = 10
        attacker.baseStats.crit = 0
        attacker.moveTo(0, 0, 0)
        g.getMap().addObject(attacker)

        defenders = []
        for item_id in ("Scroll", "TownPortalScroll"):
            defender = g.createObject("GoblinThief")
            defender.baseStats.hit = 0
            defender.baseStats.dmgMin = 0
            defender.baseStats.dmgMax = 0
            defender.baseStats.crit = 0
            defender.level = 0
            defender.sw = 0
            defender.hp = 1
            defender.addItem(item_id)
            defender.moveTo(1, 0, 0)
            g.getMap().addObject(defender)
            defenders.append(defender)

        return game, g, attacker, defenders

    def expected_scaled_exp_gain(self, attacker, defenders):
        attacker_level = attacker.getLevel()
        return sum(int(250 * pow(2, -(attacker_level - (defender.level + defender.sw)))) for defender in defenders)

    @game_test
    def test_combat_invariants(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        attacker = g.createObject("Warrior")
        defender = g.createObject("GoblinThief")
        g.getMap().addObject(attacker)
        g.getMap().addObject(defender)

        attacker_hp_before = attacker.getHpRatio()
        defender_hp_before = defender.getHpRatio()
        game.CFightHandler.fight(attacker, defender)

        self.assertGreaterEqual(attacker.getHpRatio(), -100.0)
        self.assertLessEqual(attacker.getHpRatio(), 100.0)
        self.assertGreaterEqual(defender.getHpRatio(), -100.0)
        self.assertLessEqual(defender.getHpRatio(), 100.0)

        one_side_took_damage = attacker.getHpRatio() < attacker_hp_before or defender.getHpRatio() < defender_hp_before
        self.assertTrue(one_side_took_damage)
        return True, ""

    @game_test
    def test_shadow_bolt_can_configure_its_effect(self):
        game = load_game_module()
        original_randint = game.randint
        try:
            game.randint = lambda lower, upper: lower
            g = game.CGameLoader.loadGame()

            shadow_bolt = g.createObject("ShadowBolt")
            effect = g.createObject("AbyssalShadowsEffect")

            self.assertTrue(shadow_bolt.configureEffect(effect))
        finally:
            game.randint = original_randint
        return True, ""

    @game_test
    def test_monster_fight_controller_uses_only_one_heal_item_per_turn(self):
        g, game_map, _player = load_game_map_with_player("test")
        monster = g.createObject("GoblinThief")
        monster.name = "unitTestMonsterController"
        game_map.addObject(monster)
        monster.moveTo(1, 1, 0)
        monster.setHp(max(1, monster.getHpMax() // 4))

        weak_potion = g.createObject("CPotion")
        weak_potion.name = "unitTestWeakHeal"
        weak_potion.typeId = "unitTestWeakHealPotion"
        weak_potion.addTag("heal")
        weak_potion.power = 1

        strong_potion = g.createObject("CPotion")
        strong_potion.name = "unitTestStrongHeal"
        strong_potion.typeId = "unitTestStrongHealPotion"
        strong_potion.addTag("heal")
        strong_potion.power = 2

        monster.addItem(weak_potion)
        monster.addItem(strong_potion)

        acted = monster.getFightController().control(monster, game_map.getPlayer())

        self.assertTrue(acted)
        self.assertEqual(0, monster.countItems("unitTestWeakHealPotion"))
        self.assertEqual(1, monster.countItems("unitTestStrongHealPotion"))

        return True, json.dumps(
            {
                "acted": acted,
                "weak_remaining": monster.countItems("unitTestWeakHealPotion"),
                "strong_remaining": monster.countItems("unitTestStrongHealPotion"),
            },
            sort_keys=True,
        )

    @game_test
    def test_multi_enemy_combat_resolves_and_rewards_once(self):
        game, g, attacker, defenders = self.make_multi_enemy_combat_fixture()

        exp_before = attacker.exp
        scroll_before = attacker.countItems("Scroll")
        town_portal_before = attacker.countItems("TownPortalScroll")
        expected_exp = exp_before + self.expected_scaled_exp_gain(attacker, defenders)
        started = time.monotonic()
        result = game.CFightHandler.fightMany(attacker, defenders)
        elapsed = time.monotonic() - started

        remaining = [defender.getName() for defender in defenders if g.getMap().getObjectByName(defender.getName())]

        self.assertTrue(result)
        self.assertLess(elapsed, 2.0)
        self.assertTrue(attacker.isAlive())
        self.assertEqual([], remaining)
        self.assertEqual(expected_exp, attacker.exp)
        self.assertEqual(scroll_before + 1, attacker.countItems("Scroll"))
        self.assertEqual(town_portal_before + 1, attacker.countItems("TownPortalScroll"))

        return True, json.dumps(
            {
                "elapsed": elapsed,
                "exp_before": exp_before,
                "exp_after": attacker.exp,
                "scrolls": attacker.countItems("Scroll"),
                "town_portal_scrolls": attacker.countItems("TownPortalScroll"),
                "remaining": remaining,
            }
        )

    @game_test
    def test_multi_enemy_combat_from_movement_path(self):
        game, g, attacker, defenders = self.make_multi_enemy_combat_fixture()

        fight_coords = defenders[0].getCoords()
        before_names = sorted(obj.getName() for obj in g.getMap().getObjectsAtCoords(fight_coords))
        exp_before = attacker.exp
        expected_exp = exp_before + self.expected_scaled_exp_gain(attacker, defenders)
        attacker.moveTo(fight_coords.x, fight_coords.y, fight_coords.z)

        remaining = [defender.getName() for defender in defenders if g.getMap().getObjectByName(defender.getName())]
        occupant_names = sorted(obj.getName() for obj in g.getMap().getObjectsAtCoords(attacker.getCoords()))

        self.assertEqual(2, len(before_names))
        self.assertEqual([], remaining)
        self.assertEqual([attacker.getName()], occupant_names)
        self.assertEqual(expected_exp, attacker.exp)

        return True, json.dumps(
            {
                "before_names": before_names,
                "occupants_after": occupant_names,
                "remaining": remaining,
                "exp_before": exp_before,
                "exp_after": attacker.exp,
            }
        )

    @game_test
    def test_affiliated_creatures_do_not_fight_on_overlap(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        allies = []
        for x_pos in (0, 1):
            creature = g.createObject("GoblinThief")
            creature.baseStats.hit = 100
            creature.baseStats.dmgMin = 10
            creature.baseStats.dmgMax = 10
            creature.baseStats.crit = 0
            creature.hp = 1
            creature.setStringProperty("affiliation", "encounter-pack")
            g.getMap().addObject(creature)
            creature.moveTo(x_pos, 0, 0)
            allies.append(creature)

        allies[1].moveTo(0, 0, 0)

        remaining = sorted(creature.getName() for creature in allies if g.getMap().getObjectByName(creature.getName()))
        occupants = sorted(obj.getName() for obj in g.getMap().getObjectsAtCoords(allies[0].getCoords()))

        expected = sorted(creature.getName() for creature in allies)
        self.assertEqual(expected, remaining)
        self.assertEqual(expected, occupants)

        return True, json.dumps(
            {
                "occupants": occupants,
                "remaining": remaining,
            }
        )

    @game_test
    def test_multi_enemy_combat_stale_loop_terminates(self):
        game, g, attacker, defenders = self.make_multi_enemy_combat_fixture()

        attacker.setFightController(g.createObject("CFightController"))
        for defender in defenders:
            defender.setFightController(g.createObject("CFightController"))

        exp_before = attacker.exp
        started = time.monotonic()
        result = game.CFightHandler.fightMany(attacker, defenders)
        elapsed = time.monotonic() - started

        remaining = sorted(
            defender.getName() for defender in defenders if g.getMap().getObjectByName(defender.getName())
        )

        self.assertFalse(result)
        self.assertLess(elapsed, 2.0)
        self.assertTrue(attacker.isAlive())
        self.assertEqual(exp_before, attacker.exp)
        self.assertEqual(sorted(defender.getName() for defender in defenders), remaining)

        return True, json.dumps(
            {
                "elapsed": elapsed,
                "exp_before": exp_before,
                "exp_after": attacker.exp,
                "remaining": remaining,
            }
        )

    @game_test
    def test_single_opponent_fight_wrapper_still_works(self):
        game, g, attacker, defenders = self.make_multi_enemy_combat_fixture()

        defender = defenders[0]
        exp_before = attacker.exp
        expected_exp = exp_before + self.expected_scaled_exp_gain(attacker, [defender])

        result = game.CFightHandler.fight(attacker, defender)

        self.assertTrue(result)
        self.assertIsNone(g.getMap().getObjectByName(defender.getName()))
        self.assertIsNotNone(g.getMap().getObjectByName(defenders[1].getName()))
        self.assertEqual(expected_exp, attacker.exp)

        return True, json.dumps(
            {
                "defeated": defender.getName(),
                "remaining": defenders[1].getName(),
                "exp_before": exp_before,
                "exp_after": attacker.exp,
            }
        )

    @game_test
    def test_creature_damage_roll_normalizes_inverted_range(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")

        creature = g.createObject("CCreature")
        stats = g.createObject("Stats")
        stats.dmgMin = 8
        stats.dmgMax = 3
        stats.hit = 100
        stats.crit = 0
        stats.damage = 0
        stats.mainStat = "strength"
        stats.strength = 1
        creature.baseStats = stats

        rolls = [creature.getDmg() for i in range(25)]
        valid_rolls = all(3 <= roll <= 8 for roll in rolls)
        return valid_rolls, json.dumps({"rolls": rolls})

    @game_test
    def test_block_chance_uses_percentage_scale(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")

        creature = g.createObject("CCreature")
        stats = g.createObject("Stats")
        stats.stamina = 10
        stats.strength = 10
        stats.mainStat = "strength"
        stats.armor = 0
        stats.block = 100
        stats.normalResist = 0
        stats.thunderResist = 0
        stats.frostResist = 0
        stats.fireResist = 0
        stats.shadowResist = 0
        creature.baseStats = stats
        creature.setHp(creature.getHpMax())

        blocked_hp_before = creature.getHpRatio()
        creature.hurt(5)
        blocked_hp_after = creature.getHpRatio()

        stats.block = 0
        creature.setHp(creature.getHpMax())
        creature.hurt(5)
        unblocked_hp_after = creature.getHpRatio()

        self.assertEqual(blocked_hp_before, blocked_hp_after)
        self.assertLess(unblocked_hp_after, blocked_hp_before)

        return True, json.dumps(
            {
                "blocked_hp_before": blocked_hp_before,
                "blocked_hp_after": blocked_hp_after,
                "unblocked_hp_after": unblocked_hp_after,
            }
        )

    @game_test
    def test_attack_bonus_reflection_affects_hit_rolls(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")

        creature = g.createObject("CCreature")
        base_stats = g.createObject("Stats")
        base_stats.hit = 0
        base_stats.crit = 0
        base_stats.dmgMin = 1
        base_stats.dmgMax = 1
        base_stats.damage = 0
        creature.baseStats = base_stats

        level_stats = g.createObject("Stats")
        level_stats.attack = 100
        creature.levelStats = level_stats
        creature.level = 1

        rolls = [creature.getDmg() for _ in range(20)]

        self.assertEqual([1] * len(rolls), rolls)

        return True, json.dumps({"rolls": rolls})

    @game_test
    def test_create_object_without_config_logs_fallback(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        log_path = make_temp_log_path()
        try:
            game.set_logger_sink("file", str(log_path))
            creature = g.createObject("CCreature")
        finally:
            game.set_logger_sink("disabled", None)

        log_text = log_path.read_text()
        log_path.unlink(missing_ok=True)

        self.assertIsNotNone(creature)
        self.assertEqual("CCreature", creature.getType())
        self.assertEqual("CCreature", creature.getTypeId())
        self.assertIn("DEBUG: No config found for: CCreature", log_text)
        self.assertIn("falling back to class-name construction", log_text)

        return True, json.dumps({"log": log_text.strip()})

    @game_test
    def test_invalid_saved_game_logs_parse_failure(self):
        game = load_game_module()

        save_name = f"invalid_save_{time.time_ns()}"
        save_dir = build_dir / "save"
        save_dir.mkdir(exist_ok=True)
        save_path = save_dir / f"{save_name}.json"
        save_path.write_text('{"properties":', encoding="utf-8")

        g = game.CGameLoader.loadGame()
        log_path = make_temp_log_path()
        try:
            game.set_logger_sink("file", str(log_path))
            game.CGameLoader.loadSavedGame(g, save_name)
        finally:
            game.set_logger_sink("disabled", None)
            save_path.unlink(missing_ok=True)

        log_text = log_path.read_text()
        log_path.unlink(missing_ok=True)

        self.assertIsNotNone(g.getMap())
        self.assertEqual("CMap", g.getMap().getType())
        self.assertIn("WARNING: Failed to parse json from", log_text)
        self.assertIn(f"save/{save_name}.json", log_text)
        self.assertIn('preview: {"properties":', log_text)

        return True, json.dumps({"log": log_text.strip(), "map_type": g.getMap().getType()})

    @game_test
    def test_objects(self):
        game = load_game_module()

        failed = []
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        for type in g.getObjectHandler().getAllTypes():
            object = g.createObject(type)
            if not object:
                failed.append(type)
        return failed == [], failed

    @game_test
    def test_effect_apply_uses_full_duration(self):
        game = load_game_module()
        seen_time_left = []

        class CountingEffect(game.CEffect):
            def onEffect(self):
                seen_time_left.append(self.getTimeLeft())

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")

        creature = g.createObject("CCreature")
        effect = CountingEffect()
        effect.duration = 3

        effect.apply(creature)
        effect.apply(creature)
        effect.apply(creature)
        effect.apply(creature)

        self.assertEqual(
            [3, 2, 1],
            seen_time_left,
            "A duration-N effect should tick exactly N times and expose the final tick to onEffect().",
        )
        self.assertEqual(0, effect.getTimeLeft())

        return True, json.dumps(
            {
                "seen_time_left": seen_time_left,
                "time_left": effect.getTimeLeft(),
            },
            sort_keys=True,
        )

    @game_test
    def test_fights(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        creatures = g.getObjectHandler().getAllSubTypes("CCreature")
        values = []
        for type1 in creatures:
            for type2 in creatures:
                object1 = g.createObject(type1)
                object2 = g.createObject(type2)
                g.getMap().addObject(object1)
                g.getMap().addObject(object2)
                if not game.CFightHandler.fight(object1, object2):
                    values.append((type1, type2, "none"))
                if object1.isAlive() and not object2.isAlive():
                    values.append((type1, type2, "first"))
                if object2.isAlive() and not object1.isAlive():
                    values.append((type1, type2, "second"))
                if not object1.isAlive() and not object2.isAlive():
                    values.append((type1, type2, "both"))
        return True, json.dumps(values)

    @game_test
    def test_level(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        creatures = g.getObjectHandler().getAllSubTypes("CCreature")
        values = []
        for type1 in creatures:
            object = g.createObject(type1)
            g.getMap().addObject(object)
            while object.getLevel() < 25:
                object.addExp(1000)
            values.append(json.loads(game.jsonify(object)))
        return True, json.dumps(values)

    @game_test
    def test_binding_docstrings(self):
        game = load_game_module()
        checks = {
            "CGameObject": getattr(game.CGameObject, "__doc__", "") or "",
            "CMap": getattr(game.CMap, "__doc__", "") or "",
            "CCreature": getattr(game.CCreature, "__doc__", "") or "",
            "CCreature.hurt": getattr(game.CCreature.hurt, "__doc__", "") or "",
            "randint": getattr(game.randint, "__doc__", "") or "",
            "jsonify": getattr(game.jsonify, "__doc__", "") or "",
            "logger": getattr(game.logger, "__doc__", "") or "",
        }
        missing = sorted([name for name, doc in checks.items() if not doc.strip()])
        return missing == [], json.dumps({"missing": missing, "doc_sizes": {k: len(v) for k, v in checks.items()}})

    @game_test
    def test_runtime_binding_properties(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")

        stats = g.createObject("Stats")
        for name, value in {
            "strength": 1,
            "agility": 2,
            "stamina": 3,
            "intelligence": 4,
            "armor": 5,
            "block": 6,
            "dmgMin": 7,
            "dmgMax": 8,
            "hit": 9,
            "crit": 10,
            "fireResist": 11,
            "frostResist": 12,
            "normalResist": 13,
            "thunderResist": 14,
            "shadowResist": 15,
            "damage": 16,
            "mainStat": "agility",
        }.items():
            setattr(stats, name, value)
            self.assertEqual(getattr(stats, name), value)

        damage = g.createObject("Damage")
        for name, value in {
            "fire": 21,
            "frost": 22,
            "thunder": 23,
            "shadow": 24,
            "normal": 25,
        }.items():
            setattr(damage, name, value)
            self.assertEqual(getattr(damage, name), value)

        dialog = g.createObject("CDialog")
        self.assertTrue(dialog.invokeCondition("missing"))
        dialog.invokeAction("missing")

        dialog_state = g.createObject("CDialogState")
        dialog_state.stateId = "ENTRY"
        dialog_state.text = "Hello there"
        self.assertEqual(dialog_state.stateId, "ENTRY")
        self.assertEqual(dialog_state.text, "Hello there")

        dialog_option = g.createObject("CDialogOption")
        dialog_option.number = 3
        dialog_option.text = "Continue"
        dialog_option.action = "act"
        dialog_option.condition = "cond"
        dialog_option.nextStateId = "EXIT"
        self.assertEqual(dialog_option.number, 3)
        self.assertEqual(dialog_option.text, "Continue")
        self.assertEqual(dialog_option.action, "act")
        self.assertEqual(dialog_option.condition, "cond")
        self.assertEqual(dialog_option.nextStateId, "EXIT")

        quest = g.createObject("CQuest")
        quest.description = "Investigate"
        self.assertEqual(quest.description, "Investigate")
        self.assertFalse(quest.isCompleted())
        quest.onComplete()

        trigger = g.createObject("CTrigger")
        trigger.object = "gate"
        trigger.event = "open"
        self.assertEqual(trigger.object, "gate")
        self.assertEqual(trigger.event, "open")
        trigger.trigger(None, None)

        event = g.createObject("CEvent")
        event.enabled = False
        self.assertFalse(event.enabled)
        event.onEnter(None)
        event.onLeave(None)

        building = g.createObject("CBuilding")
        building.enabled = False
        self.assertFalse(building.enabled)
        building.onEnter(None)
        building.onLeave(None)

        effect = g.createObject("CEffect")
        effect.duration = 4
        effect.cumulative = True
        effect.setBonus(stats)
        self.assertEqual(effect.duration, 4)
        self.assertTrue(effect.cumulative)
        self.assertIsNotNone(effect.getBonus())
        self.assertEqual(effect.getTimeLeft(), 4)
        self.assertIsNone(effect.getCaster())
        self.assertIsNone(effect.getVictim())
        effect.onEffect()

        creature = g.createObject("CCreature")
        creature.baseStats = stats
        self.assertEqual(creature.baseStats.getStringProperty("mainStat"), "agility")

        item = g.createObject("CItem")
        item.power = 2
        self.assertEqual(item.power, 2)

        potion = g.createObject("CPotion")
        potion.onUse(None)

        scroll = g.createObject("CScroll")
        scroll.text = "Lore"
        self.assertEqual(scroll.text, "Lore")
        self.assertFalse(scroll.isDisposable())
        scroll.onUse(None)

        market = g.createObject("CMarket")
        market.sell = 130
        market.buy = 60
        self.assertEqual(market.sell, 130)
        self.assertEqual(market.buy, 60)

        list_string = g.createObject("CListString")
        list_string.addValue("north")

        report = {
            "stats": {name: getattr(stats, name) for name in ("strength", "agility", "damage", "mainStat")},
            "damage": {name: getattr(damage, name) for name in ("fire", "frost", "thunder", "shadow", "normal")},
            "dialog": {"state": dialog_state.stateId, "option": dialog_option.text},
            "market": {"sell": market.sell, "buy": market.buy},
            "effect_time_left": effect.getTimeLeft(),
        }
        return True, json.dumps(report, sort_keys=True)

    @game_test
    def test_event_handler_dispatches_lifecycle_triggers_and_item_use(self):
        game = load_game_module()

        g, game_map, player = load_game_map_with_player("test")
        controller = get_player_controller(player)
        lifecycle = []
        trigger_hits = []
        use_hits = []

        class LifecycleEvent(game.CEvent):
            def onCreate(self, event):
                lifecycle.append(("create", self.getName()))

            def onDestroy(self, event):
                lifecycle.append(("destroy", self.getName()))

            def onEnter(self, event):
                lifecycle.append(("enter", self.getName(), event.getCause().getName()))

            def onLeave(self, event):
                lifecycle.append(("leave", self.getName(), event.getCause().getName()))

        class EnterTrigger(game.CTrigger):
            def trigger(self, obj, event):
                trigger_hits.append((obj.getName(), event.getCause().getName()))

        class LoggedPotion(game.CPotion):
            def onUse(self, event):
                use_hits.append((self.getName(), event.getCause().getName()))

        g.getObjectHandler().registerType("LifecycleEvent", LifecycleEvent)
        g.getObjectHandler().registerType("EnterTrigger", EnterTrigger)
        g.getObjectHandler().registerType("LoggedPotion", LoggedPotion)

        event_object = g.createObject("LifecycleEvent")
        event_object.name = "lifecycleEvent"
        game_map.addObject(event_object)

        origin = player.getCoords()
        enter_target = find_adjacent_walkable_tile(game_map, origin)
        event_object.moveTo(enter_target.x, enter_target.y, enter_target.z)

        matching_trigger = g.createObject("EnterTrigger")
        matching_trigger.object = "lifecycleEvent"
        matching_trigger.event = "onEnter"
        game_map.getEventHandler().registerTrigger(matching_trigger)

        wrong_trigger = g.createObject("EnterTrigger")
        wrong_trigger.object = "otherObject"
        wrong_trigger.event = "onEnter"
        game_map.getEventHandler().registerTrigger(wrong_trigger)

        controller.setTarget(player, enter_target)
        game_map.move()

        leave_target = find_adjacent_walkable_tile(game_map, player.getCoords())
        if leave_target == enter_target:
            raise AssertionError("Expected a different adjacent tile for the leave test.")
        controller.setTarget(player, leave_target)
        game_map.move()

        potion = g.createObject("LoggedPotion")
        potion.name = "loggedPotion"
        game_map.addObject(potion)
        pickup_target = find_adjacent_walkable_tile(game_map, player.getCoords())
        potion.moveTo(pickup_target.x, pickup_target.y, pickup_target.z)

        controller.setTarget(player, pickup_target)
        game_map.move()

        self.assertEqual(1, player.countItems("LoggedPotion"))
        self.assertIsNone(game_map.getObjectByName("loggedPotion"))

        player.useItem(potion)

        game_map.removeObjectByName("lifecycleEvent")

        self.assertEqual(
            [
                ("create", "lifecycleEvent"),
                ("enter", "lifecycleEvent", "player"),
                ("leave", "lifecycleEvent", "player"),
                ("destroy", "lifecycleEvent"),
            ],
            lifecycle,
        )
        self.assertEqual([("lifecycleEvent", "player")], trigger_hits)
        self.assertEqual([("loggedPotion", "player")], use_hits)
        self.assertEqual(0, player.countItems("LoggedPotion"))

        return True, json.dumps(
            {
                "lifecycle": lifecycle,
                "trigger_hits": trigger_hits,
                "use_hits": use_hits,
                "pickup_target": [pickup_target.x, pickup_target.y, pickup_target.z],
            },
            sort_keys=True,
        )

    @game_test
    def test_tags_are_typed_in_bindings_and_persist_through_save_load(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "siege", "Warrior")

        heal_potion = g.createObject("LesserLifePotion")
        barrier_effect = g.createObject("BarrierEffect")
        magic_wand = g.createObject("magicWand")
        chloroform_effect = g.createObject("ChloroformEffect")

        self.assertTrue(heal_potion.hasTag(game.CTag.HEAL))
        self.assertTrue(heal_potion.hasTag("heal"))
        self.assertTrue(barrier_effect.hasTag(game.CTag.BUFF))
        self.assertTrue(magic_wand.hasTag(game.CTag.QUEST))
        self.assertTrue(magic_wand.hasTag(game.CTag.WAND))

        chloroform_effect.addTag(game.CTag.STUN)
        self.assertTrue(chloroform_effect.hasTag(game.CTag.STUN))
        chloroform_effect.removeTag("stun")
        self.assertFalse(chloroform_effect.hasTag(game.CTag.STUN))

        with self.assertRaises(ValueError):
            heal_potion.hasTag("unknownTag")
        with self.assertRaises(ValueError):
            heal_potion.addTag("unknownTag")
        with self.assertRaises(ValueError):
            heal_potion.removeTag("unknownTag")

        tagged_object_name = "typedTagPotion"
        heal_potion.name = tagged_object_name
        siege_map = g.getMap()
        siege_map.addObject(heal_potion)
        heal_potion.moveTo(2, 2, 0)

        save_name = "typed_tags_roundtrip"
        game.CMapLoader.save(siege_map, save_name)

        loaded_game = game.CGameLoader.loadGame()
        game.CGameLoader.loadSavedGame(loaded_game, save_name)
        loaded_object = loaded_game.getMap().getObjectByName(tagged_object_name)

        self.assertIsNotNone(loaded_object)
        self.assertTrue(loaded_object.hasTag(game.CTag.HEAL))
        self.assertTrue(loaded_object.hasTag("heal"))

        report = {
            "enum_checks": {
                "heal": heal_potion.hasTag(game.CTag.HEAL),
                "buff": barrier_effect.hasTag(game.CTag.BUFF),
                "quest": magic_wand.hasTag(game.CTag.QUEST),
                "wand": magic_wand.hasTag(game.CTag.WAND),
            },
            "saved_object": {
                "name": tagged_object_name,
                "loaded_has_heal": loaded_object.hasTag(game.CTag.HEAL),
            },
        }
        return True, json.dumps(report, sort_keys=True)

    @game_test
    def test_headless_handlers_and_resources(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()

        gui_handler = g.getGuiHandler()
        market = g.createObject("CMarket")
        dialog = g.createObject("CDialog")
        creature = g.createObject("CCreature")
        item = g.createObject("CItem")

        gui_handler.showMessage("message")
        gui_handler.showInfo("info", True)
        answer = gui_handler.showQuestion("question?")
        gui_handler.showTrade(market)
        gui_handler.showDialog(dialog)
        gui_handler.showLoot(creature, {item})

        rng_handler = g.getRngHandler()
        object_handler = g.getObjectHandler()
        g.loadPlugin(lambda: g.createObject("CPlugin"))

        provider = game.CResourcesProvider.getInstance()
        (Path.cwd() / "save").mkdir(exist_ok=True)
        resources = {
            "config": sorted(provider.getFiles("CONFIG"))[:3],
            "plugins": sorted(provider.getFiles("PLUGIN"))[:3],
            "maps": sorted(provider.getFiles("MAP")),
            "save": sorted(provider.getFiles("SAVE")),
        }

        self.assertFalse(answer)
        self.assertIsNotNone(rng_handler)
        self.assertIsNotNone(object_handler)
        self.assertIn("nouraajd", resources["maps"])
        self.assertTrue(any(path.endswith(".json") for path in resources["config"]))
        self.assertTrue(any(path.endswith(".py") for path in resources["plugins"]))

        return True, json.dumps(resources, sort_keys=True)

    @game_test
    def test_resource_provider_resolves_and_loads_known_files(self):
        game = load_game_module()
        provider = game.CResourcesProvider.getInstance()

        samples = {
            "config/tiles.json": "GroundTile",
            "maps/test/map.json": '"layers"',
            "plugins/effect.py": "def load",
        }
        resolved = {}
        for resource_path, needle in samples.items():
            full_path = provider.getPath(resource_path)
            self.assertTrue(full_path, resource_path)
            self.assertTrue(Path(full_path).exists(), full_path)
            self.assertIn(needle, provider.load(resource_path), resource_path)
            resolved[resource_path] = full_path

        return True, json.dumps(resolved, sort_keys=True)

    @game_test
    def test_turns(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "nouraajd", "Warrior")
        advance(g, 100)
        return True, game.jsonify(g.getMap())

    @game_test
    def test_map_objects_at_coords_binding(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        coords = player.getCoords()
        objects = game_map.getObjectsAtCoords(coords)
        names = sorted(obj.getName() for obj in objects)
        success = isinstance(objects, list) and player.getName() in names
        return success, json.dumps(
            {
                "coords": [coords.x, coords.y, coords.z],
                "count": len(objects),
                "names": names,
            }
        )

    @game_test
    def test_pathfinder(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "nouraajd", "Warrior")
        output_path = TEST_OUTPUT_DIR / "pathfinder.png"
        g.getMap().dumpPaths(str(output_path))
        return True, str(output_path)

    @game_test
    def test_load(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadSavedGame(g, "gooby")
        return True, ""

    @game_test
    def test_random(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startRandomGameWithPlayer(g, "Warrior")
        output_path = TEST_OUTPUT_DIR / "random.png"
        g.getMap().dumpPaths(str(output_path))
        return True, str(output_path)

    @game_test
    def test_dialogs(self):
        option_defs = {}
        dialog_defs = {}

        misc = REPO_ROOT / "res/config/misc.json"
        if misc.exists():
            with open(misc) as f:
                data = json.load(f)
                for key, value in data.items():
                    if isinstance(value, dict) and value.get("class") == "CDialogOption":
                        option_defs[key] = value

        dialog_dir = REPO_ROOT / "res/maps/nouraajd"
        for path in dialog_dir.glob("*.json"):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                if not isinstance(value, dict):
                    continue
                if value.get("class") == "CDialogOption":
                    option_defs[key] = value
                if isinstance(value.get("properties", {}).get("states"), list):
                    dialog_defs[key] = value

        with open(dialog_dir / "script.py") as f:
            tree = ast.parse(f.read())
        methods_by_class = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods_by_class[node.name] = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}

        missing_actions = []
        missing_states = []
        duplicate_state_ids = []
        unreachable_states = []

        for dialog_id, dialog in dialog_defs.items():
            cls = dialog.get("class")
            states = dialog.get("properties", {}).get("states", [])
            state_map = {}
            edges = {}
            entry_states = []
            for state in states:
                props = state.get("properties", {})
                sid = props.get("stateId")
                if sid in state_map:
                    duplicate_state_ids.append(f"{dialog_id}:{sid}")
                state_map[sid] = props
                if sid == "ENTRY":
                    entry_states.append(sid)
            for state in states:
                sid = state.get("properties", {}).get("stateId")
                for opt in state.get("properties", {}).get("options", []):
                    resolved = {}
                    if "ref" in opt:
                        resolved.update(option_defs.get(opt["ref"], {}).get("properties", {}))
                    resolved.update(opt.get("properties", {}))
                    next_id = resolved.get("nextStateId")
                    if next_id and next_id != "EXIT" and next_id not in state_map:
                        missing_states.append(f"{dialog_id}:{sid}->{next_id}")
                    if next_id and next_id != "EXIT":
                        edges.setdefault(sid, []).append(next_id)
                    action = resolved.get("action")
                    if action and action not in methods_by_class.get(cls, set()):
                        missing_actions.append(f"{dialog_id}:{action}")
            visited = set()
            stack = list(entry_states)
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                for nxt in edges.get(current, []):
                    if nxt in state_map:
                        stack.append(nxt)
            for sid, props in state_map.items():
                if sid != "EXIT" and sid not in visited and not props.get("condition"):
                    unreachable_states.append(f"{dialog_id}:{sid}")

        success = not (missing_actions or missing_states or duplicate_state_ids or unreachable_states)
        log = {
            "missing_actions": sorted(missing_actions),
            "missing_states": sorted(missing_states),
            "duplicate_state_ids": sorted(duplicate_state_ids),
            "unreachable_states": sorted(unreachable_states),
        }
        return success, json.dumps(log)

    @game_test
    def test_nouraajd_trigger_targets(self):
        script_path = REPO_ROOT / "res/maps/nouraajd/script.py"
        with open(script_path) as f:
            script = f.read()

        trigger_targets = set(re.findall(r'@trigger\(context,\s*"[^"]+",\s*"([^"]+)"\)', script))

        with open(REPO_ROOT / "res/maps/nouraajd/map.json") as f:
            map_data = json.load(f)
        placed_names = set()
        for layer in map_data.get("layers", []):
            if layer.get("type") == "objectgroup":
                for obj in layer.get("objects", []):
                    name = obj.get("name")
                    if name:
                        placed_names.add(name)

        runtime_spawned_targets = {"gooby1", "amuletGoblin", "cultLeaderQuest"}
        missing_targets = sorted(
            target for target in trigger_targets if target not in placed_names and target not in runtime_spawned_targets
        )
        return missing_targets == [], json.dumps(missing_targets)

    @game_test
    def test_nouraajd_quest_integrity_regression(self):
        script_path = REPO_ROOT / "res/maps/nouraajd/script.py"
        with open(script_path) as f:
            script = f.read()

        dialog5 = json.loads((REPO_ROOT / "res/maps/nouraajd/dialog5.json").read_text())
        entry_options = dialog5["berenDialog"]["properties"]["states"][0]["properties"]["options"]
        beren_conditions = {
            opt.get("properties", {}).get("text"): opt.get("properties", {}).get("condition")
            for opt in entry_options
            if opt.get("class") == "CDialogOption"
        }

        dialog3 = json.loads((REPO_ROOT / "res/maps/nouraajd/dialog3.json").read_text())
        courtyard_state = None
        courtyard_action = None
        for state in dialog3["tavernDialog2"]["properties"]["states"]:
            if state.get("properties", {}).get("stateId") == "COURTYARD_PATH":
                courtyard_state = state
                courtyard_action = state["properties"]["options"][0]["properties"].get("action")
                break

        dialog4 = json.loads((REPO_ROOT / "res/maps/nouraajd/dialog4.json").read_text())
        clue_action = None
        for state in dialog4["townHallDialog"]["properties"]["states"]:
            if state.get("properties", {}).get("stateId") == "VICTOR_CLUE":
                clue_action = state["properties"]["options"][0]["properties"].get("action")
                break

        config = json.loads((REPO_ROOT / "res/maps/nouraajd/config.json").read_text())

        checks = {
            "beren_can_deliver_condition": beren_conditions.get("I carry a letter for you.") == "can_deliver_letter",
            "beren_can_return_condition": beren_conditions.get("I recovered the relic.") == "can_return_relic",
            "beren_can_finish_condition": beren_conditions.get("The cave has been cleansed.") == "can_finish_cleanse",
            "beren_condition_methods_exist": (
                "def can_deliver_letter(self):" in script
                and "def can_return_relic(self):" in script
                and "def can_finish_cleanse(self):" in script
            ),
            "octobogz_split_flags": (
                "OCTOBOGZ_SLAIN" in script
                and "OCTOBOGZ_CLEARED" in script
                and 'setBoolProperty("OCTOBOGZ_SLAIN", True)' in script
            ),
            "octobogz_out_of_order_fix": (
                'if game_map.getBoolProperty("OCTOBOGZ_SLAIN")' in script
                and 'game_map.setBoolProperty("OCTOBOGZ_CLEARED", True)' in script
            ),
            "victor_quest_declared": "victorQuest" in config,
            "victor_spawn_not_player_coords": "player.getCoords()" not in script,
            "victor_courtyard_stable_spawns": "COURTYARD_SPAWNS" in script and "COURTYARD_LEADER_SPAWN" in script,
            "victor_clue_spawns_encounter": clue_action == "spawn_cultists",
            "victor_direct_courtyard_spawns_encounter": courtyard_action == "spawn_cultists",
            "victor_mutual_exclusive_guard": (
                "VICTOR_BAD_END" in script
                and "VICTOR_GOOD_END" in script
                and "VICTOR_REWARD_CLAIMED" in script
                and 'getBoolProperty("VICTOR_REWARD_CLAIMED")' in script
                and 'getBoolProperty("VICTOR_GOOD_END")' in script
                and 'setBoolProperty("VICTOR_BAD_END", False)' in script
            ),
            "victor_reward_once_guard": (
                "player.addGold(500)" in script and 'getBoolProperty("VICTOR_REWARD_CLAIMED")' in script
            ),
            "victor_dialog_coherent": (
                courtyard_state is not None
                and "already sacrificed" not in courtyard_state.get("properties", {}).get("text", "").lower()
                and "Victor drinks a vial of poison" not in courtyard_state.get("properties", {}).get("text", "")
            ),
        }

        failed = sorted([name for name, ok in checks.items() if not ok])
        return failed == [], json.dumps({"failed": failed, "checks": checks})

    @game_test
    def test_nouraajd_quest_progression(self):
        game = load_game_module()
        original_show_message = game.CGuiHandler.showMessage
        try:
            game.CGuiHandler.showMessage = lambda self, message: None
            g, game_map, player = load_game_map_with_player("nouraajd")

            game_map.removeObjectByName("cave1")
            self.assertTrue(game_map.getBoolProperty("completed_rolf"))
            self.assertTrue(player.hasItem(lambda it: it.getName() == "skullOfRolf"))
            self.assertFalse(game_map.getBoolProperty("completed_gooby"))

            game_map.removeObjectByName("gooby1")
            self.assertTrue(game_map.getBoolProperty("completed_gooby"))

            game_map.removeObjectByName("catacombs")
            self.assertTrue(player.hasItem(lambda it: it.getName() == "holyRelic"))

            game_map.removeObjectByName("cave2")
            self.assertTrue(game_map.getBoolProperty("OCTOBOGZ_SLAIN"))
            self.assertFalse(
                game_map.getBoolProperty("OCTOBOGZ_CLEARED"),
                "OctoBogz cave should not be marked cleared before the relic is returned.",
            )

            g_with_relic, map_with_relic, player_with_relic = load_game_map_with_player("nouraajd")
            map_with_relic.setBoolProperty("RELIC_RETURNED", True)
            map_with_relic.removeObjectByName("cave2")
            self.assertTrue(map_with_relic.getBoolProperty("OCTOBOGZ_SLAIN"))
            self.assertTrue(
                map_with_relic.getBoolProperty("OCTOBOGZ_CLEARED"),
                "OctoBogz cave should be marked cleared when relic has already been returned.",
            )

            map_with_relic.removeObjectByName("catacombs")
            self.assertTrue(player_with_relic.hasItem(lambda it: it.getName() == "holyRelic"))

            log = {
                "flags": {
                    "completed_rolf": game_map.getBoolProperty("completed_rolf"),
                    "completed_gooby": game_map.getBoolProperty("completed_gooby"),
                    "relic_item_awarded": player.hasItem(lambda it: it.getName() == "holyRelic"),
                    "octobogz_slain": game_map.getBoolProperty("OCTOBOGZ_SLAIN"),
                    "octobogz_cleared": game_map.getBoolProperty("OCTOBOGZ_CLEARED"),
                    "octobogz_cleared_with_relic": map_with_relic.getBoolProperty("OCTOBOGZ_CLEARED"),
                    "relic_item_awarded_with_relic_path": player_with_relic.hasItem(
                        lambda it: it.getName() == "holyRelic"
                    ),
                },
            }
            return True, json.dumps(log, sort_keys=True)
        finally:
            game.CGuiHandler.showMessage = original_show_message

    @game_test
    def test_nouraajd_relic_before_letter_regression(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        town_hall = g.createObject("townHallDialog")
        beren = g.createObject("berenDialog")

        game_map.removeObjectByName("catacombs")
        self.assertTrue(player.hasItem(lambda it: it.getName() == "holyRelic"))
        self.assertEqual(game_map.getStringProperty("quest_state_beren_chain"), "letter_pending")
        self.assertFalse(beren.can_return_relic())

        town_hall.give_letter()
        beren.deliver_letter()

        self.assertEqual(
            game_map.getStringProperty("quest_state_beren_chain"),
            "relic_obtained",
            "Delivering the letter after finding the relic should preserve relic progress.",
        )
        self.assertTrue(
            beren.can_return_relic(),
            "Father Beren should accept the relic after the delayed letter delivery path.",
        )

        return True, json.dumps(
            {
                "quest_state_beren_chain": game_map.getStringProperty("quest_state_beren_chain"),
                "can_return_relic": beren.can_return_relic(),
                "has_holy_relic": player.hasItem(lambda it: it.getName() == "holyRelic"),
            },
            sort_keys=True,
        )

    @game_test
    def test_nouraajd_letter_relic_and_cleanse_report_regression(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        town_hall = g.createObject("townHallDialog")
        beren = g.createObject("berenDialog")

        self.assertTrue(town_hall.can_offer_letter_work())
        self.assertFalse(town_hall.has_letter_quest())

        town_hall.give_letter()
        self.assertEqual(game_map.getStringProperty("quest_state_beren_chain"), "letter_in_hand")
        self.assertTrue(town_hall.has_letter_quest())
        self.assertFalse(town_hall.can_offer_letter_work())
        self.assertTrue(player.hasItem(lambda it: it.getName() == "letterToBeren"))

        beren.deliver_letter()
        self.assertEqual(game_map.getStringProperty("quest_state_beren_chain"), "letter_delivered")
        self.assertFalse(player.hasItem(lambda it: it.getName() == "letterToBeren"))
        self.assertIn("retrieveRelicQuest", quest_names(player))

        game_map.removeObjectByName("catacombs")
        self.assertEqual(game_map.getStringProperty("quest_state_beren_chain"), "relic_obtained")
        self.assertTrue(beren.can_return_relic())

        beren.return_relic()
        self.assertEqual(game_map.getStringProperty("quest_state_beren_chain"), "relic_returned_waiting_kill")
        self.assertFalse(player.hasItem(lambda it: it.getName() == "holyRelic"))
        self.assertIn("cleanseCaveQuest", quest_names(player))
        self.assertFalse(beren.can_finish_cleanse())

        game_map.removeObjectByName("cave2")
        self.assertEqual(game_map.getStringProperty("quest_state_beren_chain"), "ready_to_report")
        self.assertTrue(beren.can_finish_cleanse())

        beren.finish_cleanse()
        self.assertEqual(game_map.getStringProperty("quest_state_beren_chain"), "purged")
        self.assertTrue(game_map.getBoolProperty("CAVE_PURGED"))

        return True, json.dumps(
            {
                "quest_state_beren_chain": game_map.getStringProperty("quest_state_beren_chain"),
                "quests": quest_names(player),
                "cave_purged": game_map.getBoolProperty("CAVE_PURGED"),
            },
            sort_keys=True,
        )

    @game_test
    def test_nouraajd_letter_reissue_and_quest_tag_regression(self):
        game = load_game_module()
        g, game_map, player = load_game_map_with_player("nouraajd")
        town_hall = g.createObject("townHallDialog")

        town_hall.give_letter()
        self.assertTrue(
            player.hasItem(lambda it: it.getName() == "letterToBeren" and it.hasTag(game.CTag.QUEST)),
            "The mayor's letter should be tagged as a quest item so it cannot be sold or dropped.",
        )
        self.assertTrue(town_hall.has_letter_quest())
        self.assertFalse(town_hall.can_offer_letter_work())

        player.removeQuestItem(lambda it: it.getName() == "letterToBeren")
        self.assertFalse(player.hasItem(lambda it: it.getName() == "letterToBeren"))
        self.assertEqual(game_map.getStringProperty("quest_state_beren_chain"), "letter_in_hand")
        self.assertFalse(town_hall.has_letter_quest())
        self.assertTrue(
            town_hall.can_offer_letter_work(),
            "The mayor should reissue the letter if an older save or scripted state has lost the item.",
        )

        town_hall.give_letter()
        self.assertTrue(
            player.hasItem(lambda it: it.getName() == "letterToBeren" and it.hasTag(game.CTag.QUEST)),
            "Reissued letters should stay protected as quest items.",
        )
        self.assertIn("deliverLetterQuest", quest_names(player))

        return True, json.dumps(
            {
                "quest_state_beren_chain": game_map.getStringProperty("quest_state_beren_chain"),
                "has_letter": player.hasItem(lambda it: it.getName() == "letterToBeren"),
                "letter_is_quest_item": player.hasItem(
                    lambda it: it.getName() == "letterToBeren" and it.hasTag(game.CTag.QUEST)
                ),
                "quests": quest_names(player),
            },
            sort_keys=True,
        )

    @game_test
    def test_nouraajd_octobogz_before_letter_and_relic_return_regression(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        town_hall = g.createObject("townHallDialog")
        beren = g.createObject("berenDialog")

        game_map.removeObjectByName("cave2")
        self.assertEqual(game_map.getStringProperty("quest_state_beren_chain"), "octobogz_slain_pending_letter")
        self.assertTrue(game_map.getBoolProperty("OCTOBOGZ_SLAIN"))
        self.assertTrue(town_hall.can_offer_letter_work())

        town_hall.give_letter()
        self.assertTrue(beren.can_deliver_letter())
        beren.deliver_letter()
        self.assertEqual(game_map.getStringProperty("quest_state_beren_chain"), "octobogz_slain_no_relic")
        self.assertFalse(beren.can_return_relic())

        game_map.removeObjectByName("catacombs")
        self.assertTrue(player.hasItem(lambda it: it.getName() == "holyRelic"))
        self.assertTrue(beren.can_return_relic())

        beren.return_relic()
        self.assertEqual(game_map.getStringProperty("quest_state_beren_chain"), "ready_to_report")
        self.assertTrue(game_map.getBoolProperty("OCTOBOGZ_CLEARED"))
        self.assertTrue(beren.can_finish_cleanse())

        beren.finish_cleanse()
        self.assertEqual(game_map.getStringProperty("quest_state_beren_chain"), "purged")

        return True, json.dumps(
            {
                "quest_state_beren_chain": game_map.getStringProperty("quest_state_beren_chain"),
                "octobogz_slain": game_map.getBoolProperty("OCTOBOGZ_SLAIN"),
                "octobogz_cleared": game_map.getBoolProperty("OCTOBOGZ_CLEARED"),
            },
            sort_keys=True,
        )

    @game_test
    def test_nouraajd_tavern_beer_vendor(self):
        game = load_game_module()
        config = json.loads((REPO_ROOT / "res/maps/nouraajd/config.json").read_text())
        potions = json.loads((REPO_ROOT / "res/config/potions.json").read_text())
        g, game_map, player = load_game_map_with_player("nouraajd")
        original_show_trade = game.CGuiHandler.showTrade
        captured = {}

        try:

            def capture_trade(self, market):
                captured["market"] = market

            game.CGuiHandler.showTrade = capture_trade
            g.createObject("tavernDialog1").sell_beer()

            market = captured.get("market")
            self.assertIsNotNone(market, "sell_beer should open a tavern market.")

            market_data = json.loads(game.jsonify(market))
            raw_items = market_data.get("properties", {}).get("items", market_data.get("items", []))
            labels = sorted(
                item.get("properties", {}).get("label") or item.get("label") or item.get("name") for item in raw_items
            )
            market_refs = [item["ref"] for item in config["tavernBeerMarket"]["properties"]["items"]]

            self.assertEqual(market.getTypeId(), "tavernBeerMarket")
            self.assertEqual(market_refs, ["DarkBeer", "DarkBeer", "SpicedBeer"])
            self.assertEqual(labels, ["Dark Beer", "Dark Beer", "Spiced Beer"])
            self.assertTrue(
                all(ref in potions for ref in market_refs),
                "Configured tavern beers should exist in potions.json",
            )

            log = {
                "market_type": market.getTypeId(),
                "market_refs": market_refs,
                "labels": labels,
                "item_count": len(raw_items),
            }
            return True, json.dumps(log, sort_keys=True)
        finally:
            game.CGuiHandler.showTrade = original_show_trade

    @game_test
    def test_nouraajd_victor_town_hall_clue_regression(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        tavern_intro = g.createObject("tavernDialog1")
        tavern = g.createObject("tavernDialog2")
        town_hall = g.createObject("townHallDialog")

        self.assertFalse(tavern.asked_about_girl())
        tavern_intro.asked_about_girl()
        self.assertTrue(tavern.asked_about_girl())

        self.assertFalse(town_hall.talked_to_victor())
        tavern.talked_to_victor()
        self.assertTrue(town_hall.talked_to_victor())
        self.assertEqual(game_map.getStringProperty("quest_state_victor"), "met_victor")
        self.assertTrue(game_map.getBoolProperty("VICTOR_QUEST_STARTED"))
        self.assertIn("victorQuest", quest_names(player))

        town_hall.spawn_cultists()

        leader = find_runtime_object(game_map, "cultLeaderQuest")
        cultists = sorted(
            obj.getName()
            for obj in game_map.getObjects()
            if obj.getName() and obj.getName().startswith("victorCultist")
        )

        self.assertEqual(game_map.getStringProperty("quest_state_victor"), "encounter_active")
        self.assertTrue(game_map.getBoolProperty("VICTOR_COURTYARD_FOUND"))
        self.assertTrue(game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED"))
        self.assertEqual(leader.getName(), "cultLeaderQuest")
        self.assertTrue(cultists)

        return True, json.dumps(
            {
                "quest_state_victor": game_map.getStringProperty("quest_state_victor"),
                "victor_started": game_map.getBoolProperty("VICTOR_QUEST_STARTED"),
                "victor_courtyard_found": game_map.getBoolProperty("VICTOR_COURTYARD_FOUND"),
                "victor_cultists_spawned": game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED"),
                "cultists": cultists,
            },
            sort_keys=True,
        )

    @game_test
    def test_nouraajd_victor_direct_courtyard_branch_regression(self):
        dialog3 = json.loads((REPO_ROOT / "res/maps/nouraajd/dialog3.json").read_text())
        courtyard_option = None
        for state in dialog3["tavernDialog2"]["properties"]["states"]:
            if state.get("properties", {}).get("stateId") == "COURTYARD_PATH":
                courtyard_option = state["properties"]["options"][0]["properties"]
                break

        self.assertIsNotNone(courtyard_option)
        self.assertEqual(courtyard_option.get("action"), "spawn_cultists")

        g, game_map, player = load_game_map_with_player("nouraajd")
        tavern = g.createObject("tavernDialog2")

        tavern.talked_to_victor()
        tavern.spawn_cultists()

        leader = find_runtime_object(game_map, "cultLeaderQuest")
        cultists = sorted(
            obj.getName()
            for obj in game_map.getObjects()
            if obj.getName() and obj.getName().startswith("victorCultist")
        )
        self.assertEqual(game_map.getStringProperty("quest_state_victor"), "encounter_active")
        self.assertTrue(cultists)
        self.assertEqual(leader.getName(), "cultLeaderQuest")

        return True, json.dumps(
            {
                "quest_state_victor": game_map.getStringProperty("quest_state_victor"),
                "leader": leader.getName(),
                "cultists": cultists,
            },
            sort_keys=True,
        )

    @game_test
    def test_nouraajd_victor_reward_unlock_regression(self):
        game = load_game_module()
        original_show_dialog = game.CGuiHandler.showDialog
        original_show_trade = game.CGuiHandler.showTrade
        original_heal_proc = game.CPlayer.healProc
        captured = {"dialogs": [], "trades": []}
        heal_amounts = []

        try:

            def capture_dialog(self, dialog):
                captured["dialogs"].append(dialog.getTypeId())

            def capture_trade(self, market):
                captured["trades"].append(market.getTypeId())

            def capture_heal(self, amount):
                heal_amounts.append(amount)
                return original_heal_proc(self, amount)

            game.CGuiHandler.showDialog = capture_dialog
            game.CGuiHandler.showTrade = capture_trade
            game.CPlayer.healProc = capture_heal

            g, game_map, player = load_game_map_with_player("nouraajd")
            tavern = g.createObject("tavernDialog2")
            town_hall = g.createObject("townHallDialog")

            self.assertFalse(town_hall.talked_to_victor())
            tavern.talked_to_victor()
            self.assertTrue(town_hall.talked_to_victor())

            start_gold = player.getGold()

            town_hall.spawn_cultists()
            leader = find_runtime_object(game_map, "cultLeaderQuest")
            self.assertEqual(game_map.getStringProperty("quest_state_victor"), "encounter_active")

            game_map.removeObjectByName(leader.getName())

            self.assertEqual(game_map.getStringProperty("quest_state_victor"), "good_end")
            self.assertEqual(player.getGold() - start_gold, 500)
            self.assertEqual(heal_amounts, [100])
            self.assertTrue(game_map.getBoolProperty("VICTOR_GOOD_END"))
            self.assertTrue(game_map.getBoolProperty("VICTOR_REWARD_CLAIMED"))
            self.assertIn("victorRewardDialog", captured["dialogs"])
            self.assertIn("victorMarket", captured["trades"])

            town_hall.spawn_cultists()
            self.assertIsNone(game_map.getObjectByName("cultLeaderQuest"))
            self.assertFalse(
                any(
                    obj.getName() and (obj.getName() == "cultLeaderQuest" or obj.getName().startswith("victorCultist"))
                    for obj in game_map.getObjects()
                )
            )

            return True, json.dumps(
                {
                    "quest_state_victor": game_map.getStringProperty("quest_state_victor"),
                    "dialogs": captured["dialogs"],
                    "trades": captured["trades"],
                    "heal_amounts": heal_amounts,
                    "gold_delta": player.getGold() - start_gold,
                },
                sort_keys=True,
            )
        finally:
            game.CGuiHandler.showDialog = original_show_dialog
            game.CGuiHandler.showTrade = original_show_trade
            game.CPlayer.healProc = original_heal_proc

    @game_test
    def test_nouraajd_victor_timeout_cleanup_regression(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        tavern = g.createObject("tavernDialog2")
        town_hall = g.createObject("townHallDialog")

        tavern.talked_to_victor()
        town_hall.spawn_cultists()
        self.assertIsNotNone(game_map.getObjectByName("cultLeaderQuest"))

        force_nouraajd_victor_timeout(game_map)

        self.assertEqual(game_map.getStringProperty("quest_state_victor"), "bad_end")
        self.assertTrue(game_map.getBoolProperty("VICTOR_BAD_END"))
        self.assertIsNone(game_map.getObjectByName("cultLeaderQuest"))
        self.assertFalse(
            any(obj.getName() and obj.getName().startswith("victorCultist") for obj in game_map.getObjects())
        )

        town_hall.spawn_cultists()
        self.assertIsNone(game_map.getObjectByName("cultLeaderQuest"))

        return True, json.dumps(
            {
                "quest_state_victor": game_map.getStringProperty("quest_state_victor"),
                "victor_bad_end": game_map.getBoolProperty("VICTOR_BAD_END"),
            },
            sort_keys=True,
        )

    @game_test
    def test_nouraajd_amulet_cleanup_and_repeat_regression(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        quest_dialog = g.createObject("questDialog")
        quest_return_dialog = g.createObject("questReturnDialog")

        start_gold = player.getGold()
        self.assertIsNotNone(game_map.getObjectByName("oldWoman"))
        self.assertIsNone(game_map.getObjectByName("amuletGoblin"))

        quest_dialog.start_amulet_quest()
        self.assertEqual(game_map.getStringProperty("quest_state_amulet"), "active")
        self.assertIn("amuletQuest", quest_names(player))
        self.assertIsNotNone(game_map.getObjectByName("amuletGoblin"))

        quest_dialog.start_amulet_quest()
        self.assertEqual(game_map.getStringProperty("quest_state_amulet"), "active")

        player.addItem("preciousAmulet")
        quest_return_dialog.complete_amulet_quest()

        self.assertEqual(game_map.getStringProperty("quest_state_amulet"), "returned")
        self.assertEqual(player.getGold() - start_gold, 50)
        self.assertFalse(player.hasItem(lambda it: it.getName() == "preciousAmulet"))
        self.assertIsNone(game_map.getObjectByName("amuletGoblin"))
        self.assertIsNone(game_map.getObjectByName("oldWoman"))

        quest_dialog.start_amulet_quest()
        self.assertEqual(game_map.getStringProperty("quest_state_amulet"), "returned")
        self.assertIsNone(game_map.getObjectByName("amuletGoblin"))

        return True, json.dumps(
            {
                "quest_state_amulet": game_map.getStringProperty("quest_state_amulet"),
                "gold_delta": player.getGold() - start_gold,
                "old_woman_present": game_map.getObjectByName("oldWoman") is not None,
                "amulet_goblin_present": game_map.getObjectByName("amuletGoblin") is not None,
            },
            sort_keys=True,
        )

    @game_test
    def test_new_class_dialog_hooks(self):
        script = (REPO_ROOT / "res/maps/nouraajd/script.py").read_text()
        dialog4 = json.loads((REPO_ROOT / "res/maps/nouraajd/dialog4.json").read_text())
        dialog5 = json.loads((REPO_ROOT / "res/maps/nouraajd/dialog5.json").read_text())

        town_hall_entry = dialog4["townHallDialog"]["properties"]["states"][0]["properties"]["options"]
        beren_entry = dialog5["berenDialog"]["properties"]["states"][0]["properties"]["options"]

        checks = {
            "wayfarer_condition_method": "def can_chart_wayfarer_route(self):" in script,
            "wayfarer_action_method": "def chart_wayfarer_route(self):" in script,
            "wayfarer_player_property": "wayfarer_routes" in script,
            "wayfarer_dialog_option": any(
                option.get("properties", {}).get("condition") == "can_chart_wayfarer_route"
                and option.get("properties", {}).get("action") == "chart_wayfarer_route"
                for option in town_hall_entry
            ),
            "inquisitor_condition_method": "def can_inspect_stained_glass(self):" in script,
            "inquisitor_action_method": "def inspect_stained_glass(self):" in script,
            "inquisitor_player_property": "inquisitor_clues" in script,
            "inquisitor_dialog_option": any(
                option.get("properties", {}).get("condition") == "can_inspect_stained_glass"
                and option.get("properties", {}).get("action") == "inspect_stained_glass"
                for option in beren_entry
            ),
        }

        failed = sorted([name for name, ok in checks.items() if not ok])
        return failed == [], json.dumps({"failed": failed, "checks": checks})

    @game_test
    def test_nouraajd_class_specific_dialog_routes_unlock_for_type_ids(self):
        g_wayfarer, _, wayfarer = load_game_map_with_player("nouraajd", "Wayfarer")
        town_hall_wayfarer = g_wayfarer.createObject("townHallDialog")
        beren_wayfarer = g_wayfarer.createObject("berenDialog")

        self.assertEqual("CPlayer", wayfarer.getType())
        self.assertEqual("Wayfarer", wayfarer.getTypeId())
        self.assertTrue(town_hall_wayfarer.can_chart_wayfarer_route())
        self.assertFalse(beren_wayfarer.can_inspect_stained_glass())

        town_hall_wayfarer.chart_wayfarer_route()
        self.assertEqual(1, wayfarer.getNumericProperty("wayfarer_routes"))
        self.assertFalse(town_hall_wayfarer.can_chart_wayfarer_route())

        g_inquisitor, _, inquisitor = load_game_map_with_player("nouraajd", "Inquisitor")
        town_hall_inquisitor = g_inquisitor.createObject("townHallDialog")
        beren_inquisitor = g_inquisitor.createObject("berenDialog")

        self.assertEqual("CPlayer", inquisitor.getType())
        self.assertEqual("Inquisitor", inquisitor.getTypeId())
        self.assertFalse(town_hall_inquisitor.can_chart_wayfarer_route())
        self.assertTrue(beren_inquisitor.can_inspect_stained_glass())

        beren_inquisitor.inspect_stained_glass()
        self.assertEqual(1, inquisitor.getNumericProperty("inquisitor_clues"))
        self.assertFalse(beren_inquisitor.can_inspect_stained_glass())

        return True, json.dumps(
            {
                "wayfarer_type": wayfarer.getType(),
                "wayfarer_type_id": wayfarer.getTypeId(),
                "wayfarer_routes": wayfarer.getNumericProperty("wayfarer_routes"),
                "inquisitor_type": inquisitor.getType(),
                "inquisitor_type_id": inquisitor.getTypeId(),
                "inquisitor_clues": inquisitor.getNumericProperty("inquisitor_clues"),
            },
            sort_keys=True,
        )

    @game_test
    def test_ritual_dialog_integrity(self):
        config = json.loads((REPO_ROOT / "res/maps/ritual/config.json").read_text())
        dialog_defs = {
            key: val
            for key, val in config.items()
            if isinstance(val, dict) and isinstance(val.get("class"), str) and val.get("class").endswith("Dialog")
        }

        with open(REPO_ROOT / "res/maps/ritual/script.py") as f:
            tree = ast.parse(f.read())

        methods_by_class = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith("Dialog"):
                methods_by_class[node.name] = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}

        missing_actions = []
        missing_states = []

        for dialog_id, dialog in dialog_defs.items():
            states = dialog.get("properties", {}).get("states", [])
            state_ids = {state.get("properties", {}).get("stateId") for state in states}
            for state in states:
                sid = state.get("properties", {}).get("stateId")
                for opt in state.get("properties", {}).get("options", []):
                    props = opt.get("properties", {})
                    next_state = props.get("nextStateId")
                    action = props.get("action")
                    if next_state and next_state != "EXIT" and next_state not in state_ids:
                        missing_states.append(f"{dialog_id}:{sid}->{next_state}")
                    if action and action not in methods_by_class.get(dialog.get("class"), set()):
                        missing_actions.append(f"{dialog_id}:{action}")

        success = not (missing_actions or missing_states)
        return success, json.dumps({"missing_actions": missing_actions, "missing_states": missing_states})

    @game_test
    def test_ritual_has_no_static_cplayer_objects(self):
        configs = load_object_configs("ritual")
        map_data = load_map_data("ritual")

        player_like_objects = []
        explicit_player_names = []
        for layer in map_data.get("layers", []):
            if layer.get("type") != "objectgroup":
                continue
            for obj in layer.get("objects", []):
                obj_type = obj.get("type")
                obj_name = obj.get("name")
                resolved_class = resolve_object_class(configs, obj_type)
                if resolved_class == "CPlayer":
                    player_like_objects.append({"name": obj_name, "type": obj_type})
                if obj_name == "player":
                    explicit_player_names.append({"name": obj_name, "type": obj_type})

        log = {
            "player_like_objects": player_like_objects,
            "explicit_player_names": explicit_player_names,
        }
        return not (player_like_objects or explicit_player_names), json.dumps(log)

    @game_test
    def test_ritual_start_grants_quests(self):
        g, game_map, player = load_game_map_with_player("ritual")

        self.assertTrue(game_map.getBoolProperty("ritual_initialized"))
        self.assertEqual(
            quest_names(player),
            ["destroyAnchorsQuest", "finalResolutionQuest", "rescueCaptiveQuest", "ritualQuest"],
        )

        return True, json.dumps({"quests": quest_names(player)}, sort_keys=True)

    @game_test
    def test_ritual_quest_requires_successful_disruption(self):
        g, game_map, player = load_game_map_with_player("ritual")

        game_map.removeObjectByName("anchorNorth")
        advance(g, 1)
        self.assertTrue(game_map.getBoolProperty("ritual_started"))
        self.assertIn(
            "ritualQuest",
            quest_names(player),
            "Starting the ritual should not immediately complete the main ritual quest.",
        )

        game_map.removeObjectByName("anchorCrypt")
        game_map.removeObjectByName("anchorSanctum")
        self.assertTrue(game_map.getBoolProperty("leader_spawned"))

        game_map.removeObjectByName("ritualLeader")
        advance(g, 1)
        self.assertTrue(game_map.getBoolProperty("leader_defeated"))
        self.assertFalse(game_map.getBoolProperty("captive_lost"))
        self.assertNotIn(
            "ritualQuest",
            quest_names(player),
            "Defeating the leader before the captive is lost should complete the ritual disruption quest.",
        )

        return True, json.dumps(
            {
                "ritual_started": game_map.getBoolProperty("ritual_started"),
                "leader_spawned": game_map.getBoolProperty("leader_spawned"),
                "leader_defeated": game_map.getBoolProperty("leader_defeated"),
                "captive_lost": game_map.getBoolProperty("captive_lost"),
                "quests": quest_names(player),
            },
            sort_keys=True,
        )

    @game_test
    def test_ritual_quest_failure_does_not_complete(self):
        g, game_map, player = load_game_map_with_player("ritual")

        game_map.removeObjectByName("anchorNorth")
        advance(g, 71)
        self.assertTrue(game_map.getBoolProperty("ritual_started"))
        self.assertTrue(game_map.getBoolProperty("captive_lost"))
        self.assertTrue(game_map.getBoolProperty("bad_ending"))
        self.assertIn(
            "ritualQuest",
            quest_names(player),
            "The ritual quest should not complete on the bad ending path where the ritual succeeds.",
        )

        return True, json.dumps(
            {
                "ritual_started": game_map.getBoolProperty("ritual_started"),
                "captive_lost": game_map.getBoolProperty("captive_lost"),
                "bad_ending": game_map.getBoolProperty("bad_ending"),
                "quests": quest_names(player),
            },
            sort_keys=True,
        )

    @game_test
    def test_ritual_captive_stays_at_prison(self):
        g, game_map = load_game_map("ritual")
        captive_definition = find_map_object_definition("ritual", "ritualCaptive")
        captive = find_runtime_object(game_map, "ritualCaptive")
        initial_coords = captive.getCoords()
        expected_coords = (captive_definition["x"] // 32, captive_definition["y"] // 32, 0)

        advance_map_only(game_map, 20)

        captive = find_runtime_object(game_map, "ritualCaptive")
        current_coords = captive.getCoords()
        current_triplet = (current_coords.x, current_coords.y, current_coords.z)
        initial_triplet = (initial_coords.x, initial_coords.y, initial_coords.z)

        self.assertEqual(expected_coords, initial_triplet)
        self.assertEqual(expected_coords, current_triplet)

        return True, json.dumps({"initial_coords": initial_triplet, "current_coords": current_triplet}, sort_keys=True)

    @game_test
    def test_ritual_trigger_targets(self):
        script_path = REPO_ROOT / "res/maps/ritual/script.py"
        with open(script_path) as f:
            script = f.read()

        trigger_targets = set(re.findall(r'@trigger\(context,\s*"[^"]+",\s*"([^"]+)"\)', script))

        with open(REPO_ROOT / "res/maps/ritual/map.json") as f:
            map_data = json.load(f)

        placed_names = set()
        for layer in map_data.get("layers", []):
            if layer.get("type") == "objectgroup":
                for obj in layer.get("objects", []):
                    name = obj.get("name")
                    if name:
                        placed_names.add(name)

        runtime_spawned_targets = {"ritualLeader"}
        missing_targets = sorted(
            target for target in trigger_targets if target not in placed_names and target not in runtime_spawned_targets
        )
        return missing_targets == [], json.dumps(missing_targets)

    @game_test
    def test_map_walkthrough_nouraajd(self):
        return execute_walkthrough("nouraajd")

    @game_test
    def test_map_walkthrough_ritual(self):
        return execute_walkthrough("ritual")

    @game_test
    def test_map_walkthrough_siege(self):
        return execute_walkthrough("siege")

    @game_test
    def test_map_walkthrough_test(self):
        return execute_walkthrough("test")

    @game_test
    def test_all_maps_have_walkthroughs(self):
        discovered_maps = discover_maps()
        walkthrough_maps = sorted(WALKTHROUGHS)
        missing = sorted(set(discovered_maps) - set(walkthrough_maps))
        extra = sorted(set(walkthrough_maps) - set(discovered_maps))
        log = {
            "discovered_maps": discovered_maps,
            "walkthrough_maps": walkthrough_maps,
            "missing_walkthroughs": missing,
            "unknown_walkthroughs": extra,
        }
        return not (missing or extra), json.dumps(log)

    @game_test
    def test_map_walkthroughs(self):
        discovered_maps = discover_maps()
        results = {}
        failed = {}
        for map_name in discovered_maps:
            success, log = run_walkthrough(map_name, WALKTHROUGHS[map_name])
            results[map_name] = log
            if not success:
                failed[map_name] = log
        summary = {
            "discovered_maps": discovered_maps,
            "walkthroughs": {map_name: WALKTHROUGHS[map_name].__name__ for map_name in discovered_maps},
            "failed": failed,
            "results": results,
        }
        return failed == {}, json.dumps(summary)

    @game_test
    def test_json_validity(self):
        errors = []
        for path in (REPO_ROOT / "res").rglob("*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    json.load(f)
            except Exception:
                errors.append(str(path))
        return errors == [], json.dumps(errors)

    @game_test
    def test_authored_tag_strings_are_canonical(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        probe = g.createObject("CEffect")
        checked = {}

        def visit(node, collected, trail=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    next_trail = f"{trail}.{key}" if trail else key
                    if key == "tags" and isinstance(value, list):
                        collected[next_trail] = list(value)
                        for tag in value:
                            probe.addTag(tag)
                            self.assertTrue(probe.hasTag(tag))
                            probe.removeTag(tag)
                    visit(value, collected, next_trail)
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    visit(value, collected, f"{trail}[{index}]")

        for path in sorted((REPO_ROOT / "res").rglob("*.json")):
            data = json.loads(path.read_text())
            rel_path = str(path.relative_to(REPO_ROOT))
            collected = {}
            visit(data, collected)
            if collected:
                checked[rel_path] = collected

        return True, json.dumps(checked, sort_keys=True)

    @game_test
    def test_map_json_tiled_compatibility(self):
        issues_by_file = {}
        warnings_by_file = {}
        for path in sorted(MAPS_DIR.glob("*/map.json")):
            issues, warnings = validate_map_json_tiled_compatibility(path)
            if issues:
                issues_by_file[str(path.relative_to(REPO_ROOT))] = issues
            if warnings:
                warnings_by_file[str(path.relative_to(REPO_ROOT))] = warnings

        issue_counts = {
            "invalid_json": sum(
                1 for issues in issues_by_file.values() for issue in issues if issue["category"] == "invalid_json"
            ),
            "tiled_semantics": sum(
                1 for issues in issues_by_file.values() for issue in issues if issue["category"] == "tiled_semantics"
            ),
            "loader_assumption": sum(
                1 for issues in issues_by_file.values() for issue in issues if issue["category"] == "loader_assumption"
            ),
            "warning": sum(
                1 for warnings in warnings_by_file.values() for warning in warnings if warning["category"] == "warning"
            ),
        }
        log = {
            "checked_files": [str(path.relative_to(REPO_ROOT)) for path in sorted(MAPS_DIR.glob("*/map.json"))],
            "issue_counts": issue_counts,
            "issues_by_file": issues_by_file,
            "warnings_by_file": warnings_by_file,
        }
        return issues_by_file == {}, json.dumps(log, indent=2, sort_keys=True)

    def test_map_json_tiled_compatibility_allows_default_entry_coordinates(self):
        TEST_OUTPUT_DIR.mkdir(exist_ok=True)
        map_data = {
            "type": "map",
            "orientation": "orthogonal",
            "width": 1,
            "height": 1,
            "tilewidth": 40,
            "tileheight": 40,
            "layers": [
                {
                    "type": "tilelayer",
                    "name": "ground",
                    "width": 1,
                    "height": 1,
                    "x": 0,
                    "y": 0,
                    "properties": {
                        "level": "0",
                        "default": "0",
                        "xBound": "1",
                        "yBound": "1",
                    },
                    "data": [1],
                }
            ],
            "tilesets": [
                {
                    "firstgid": 1,
                    "tileproperties": {
                        "0": {
                            "type": "grass",
                        }
                    },
                }
            ],
        }

        class InlineMapPath:
            def read_text(self):
                return json.dumps(map_data)

            def relative_to(self, root):
                return Path("inline/map.json")

        issues, warnings = validate_map_json_tiled_compatibility(InlineMapPath())

        self.assertEqual([], issues)
        self.assertEqual([], warnings)

    @game_test
    def test_plugin_load_function(self):
        missing = []
        for path in (REPO_ROOT / "res/plugins").rglob("*.py"):
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            if not any(isinstance(n, ast.FunctionDef) and n.name == "load" for n in tree.body):
                missing.append(str(path))
        for path in (REPO_ROOT / "res/maps").rglob("script.py"):
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            if not any(isinstance(n, ast.FunctionDef) and n.name == "load" for n in tree.body):
                missing.append(str(path))
        return missing == [], json.dumps(missing)

    @game_test
    def test_indentation(self):
        offenders = []
        for path in REPO_ROOT.rglob("*.py"):
            parts = set(path.parts)
            if "json" in parts and ("tools" in parts or "tests" in parts):
                continue
            if any(p.startswith("cmake-build") for p in parts):
                continue
            if (
                "random-dungeon-generator" in parts
                or "vstd" in parts
                or "vcpkg_installed" in parts
                or "windows-tools" in parts
            ):
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if line.startswith("\t"):
                        offenders.append(f"{path}:{i}")
                    else:
                        stripped = line.lstrip(" ")
                        if stripped and (len(line) - len(stripped)) % 4 != 0:
                            offenders.append(f"{path}:{i}")
        return offenders == [], json.dumps(offenders)

    @game_test
    def test_resource_paths(self):
        missing = []
        json_paths = list((REPO_ROOT / "res/config").rglob("*.json"))
        json_paths.extend((REPO_ROOT / "res/maps").rglob("*.json"))
        for path in json_paths:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for key, val in self._collect_resource_paths(data):
                if val == "string":
                    continue
                base = REPO_ROOT / "res" / val
                local = (path.parent / val).resolve()
                if base.exists() or local.exists():
                    continue
                candidate = base if base.suffix else base.with_suffix(".png")
                local_candidate = local if local.suffix else local.with_suffix(".png")
                if not candidate.exists() and not local_candidate.exists():
                    missing.append(f"{path}:{key}:{val}")
        return missing == [], json.dumps(missing)

    def _collect_resource_paths(self, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("animation", "image") and isinstance(v, str):
                    yield k, v
                else:
                    yield from self._collect_resource_paths(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from self._collect_resource_paths(item)

    @game_test
    def test_playthrough(self):
        _, game_map, player = load_game_map_with_player("nouraajd")
        find_map_object_definition("nouraajd", "catacombs")
        find_map_object_definition("nouraajd", "cave1")
        find_map_object_definition("nouraajd", "cave2")

        game_map.removeObjectByName("catacombs")
        game_map.removeObjectByName("cave1")
        gooby = find_runtime_object(game_map, "gooby1")
        game_map.removeObjectByName(gooby.getName())
        game_map.removeObjectByName("cave2")

        success = (
            game_map.getBoolProperty("completed_gooby")
            and game_map.getBoolProperty("completed_octobogz")
            and player.hasItem(lambda it: it.getName() == "holyRelic")
        )
        log = {
            "completed_gooby": game_map.getBoolProperty("completed_gooby"),
            "completed_octobogz": game_map.getBoolProperty("completed_octobogz"),
            "has_holy_relic": player.hasItem(lambda it: it.getName() == "holyRelic"),
            "player_coords": [player.getCoords().x, player.getCoords().y, player.getCoords().z],
            "gooby_spawned": [gooby.getCoords().x, gooby.getCoords().y, gooby.getCoords().z],
        }
        return success, json.dumps(log, sort_keys=True)

    @game_test
    def test_nouraajd_quest_state_machine(self):
        game = load_game_module()

        def quest_state(map_object, name):
            return map_object.getStringProperty(f"quest_state_{name}")

        # Scenario A: Rolf, letter chain, OctoBogz, and amulet quests
        g1, game_map1, player1 = load_game_map_with_player("nouraajd")
        town_hall = g1.createObject("townHallDialog")
        beren = g1.createObject("berenDialog")
        quest_dialog = g1.createObject("questDialog")
        quest_return_dialog = g1.createObject("questReturnDialog")
        travelers = g1.createObject("dialog")

        assert quest_state(game_map1, "rolf") == "awaiting_skull"
        assert quest_state(game_map1, "main") == "locked"
        assert quest_state(game_map1, "beren_chain") == "letter_pending"
        assert quest_state(game_map1, "octobogz_contract") == "not_started"
        assert quest_state(game_map1, "amulet") == "not_started"

        # Trigger Rolf/Gooby path
        game_map1.removeObjectByName("cave1")
        gooby = find_runtime_object(game_map1, "gooby1")
        game_map1.removeObjectByName(gooby.getName())
        assert quest_state(game_map1, "rolf") == "skull_recovered"
        assert quest_state(game_map1, "main") == "gooby_slain"

        # Letter delivery flow
        town_hall.give_letter()
        assert quest_state(game_map1, "beren_chain") == "letter_in_hand"
        beren.deliver_letter()
        assert quest_state(game_map1, "beren_chain") == "letter_delivered"

        # Retrieve relic
        game_map1.removeObjectByName("catacombs")
        assert quest_state(game_map1, "beren_chain") == "relic_obtained"
        beren.return_relic()
        assert quest_state(game_map1, "beren_chain") == "relic_returned_waiting_kill"

        # OctoBogz travelers quest and cave clear
        travelers.accept_quest()
        assert quest_state(game_map1, "octobogz_contract") == "active"
        game_map1.removeObjectByName("cave2")
        assert quest_state(game_map1, "beren_chain") == "ready_to_report"
        assert quest_state(game_map1, "octobogz_contract") == "completed"
        beren.finish_cleanse()
        assert quest_state(game_map1, "beren_chain") == "purged"

        # Amulet quest start and completion
        quest_dialog.start_amulet_quest()
        assert quest_state(game_map1, "amulet") == "active"
        player1.addItem("preciousAmulet")
        quest_return_dialog.complete_amulet_quest()
        assert quest_state(game_map1, "amulet") == "returned"

        # Scenario B: Victor good-ending
        g2, game_map2, player2 = load_game_map_with_player("nouraajd")
        tavern_dialog2 = g2.createObject("tavernDialog2")
        tavern_dialog2.talked_to_victor()
        town_hall2 = g2.createObject("townHallDialog")
        town_hall2.spawn_cultists()
        leader = find_runtime_object(game_map2, "cultLeaderQuest")
        game_map2.removeObjectByName(leader.getName())
        assert quest_state(game_map2, "victor") == "good_end"

        # Scenario C: Victor bad-ending via timeout
        g3, game_map3, player3 = load_game_map_with_player("nouraajd")
        tavern_dialog2b = g3.createObject("tavernDialog2")
        tavern_dialog2b.talked_to_victor()
        town_hall3 = g3.createObject("townHallDialog")
        town_hall3.spawn_cultists()
        force_nouraajd_victor_timeout(game_map3)
        assert quest_state(game_map3, "victor") == "bad_end"
        assert game_map3.getObjectByName("cultLeaderQuest") is None
        assert not any(obj.getName() and obj.getName().startswith("victorCultist") for obj in game_map3.getObjects())
        town_hall3.spawn_cultists()
        assert game_map3.getObjectByName("cultLeaderQuest") is None

        log = {
            "scenario_a": {
                "rolf": quest_state(game_map1, "rolf"),
                "main": quest_state(game_map1, "main"),
                "beren_chain": quest_state(game_map1, "beren_chain"),
                "octobogz_contract": quest_state(game_map1, "octobogz_contract"),
                "amulet": quest_state(game_map1, "amulet"),
            },
            "victor_good_end": quest_state(game_map2, "victor"),
            "victor_bad_end": quest_state(game_map3, "victor"),
        }
        return True, json.dumps(log, sort_keys=True)


class McpServerTest(unittest.TestCase):
    def make_stub_server(self):
        server = mcp.EngineMcpServer(repo_root=REPO_ROOT, build_dir=build_dir)
        server.exports["echo"] = mcp.ExportedCallable(
            name="echo",
            source="test",
            target_name="echo",
            callable_obj=lambda value=None: value,
            signature="(value=None)",
        )
        return server

    def test_export_module_includes_python_class_methods(self):
        server = self.make_stub_server()
        module = types.ModuleType("game_stub")

        def top_level():
            return "top-level"

        class Dialog:
            def invoke(self, action):
                return action

            @classmethod
            def class_invoke(cls, action):
                return action

            @staticmethod
            def static_invoke(action):
                return action

        class NativeLike:
            append = list.append

        module.top_level = top_level
        module.Dialog = Dialog
        module.NativeLike = NativeLike

        server._export_module_callables(module, source="game")

        self.assertIn("top_level", server.exports)
        self.assertIn("Dialog", server.exports)
        self.assertIn("Dialog.invoke", server.exports)
        self.assertIn("Dialog.class_invoke", server.exports)
        self.assertIn("Dialog.static_invoke", server.exports)
        self.assertNotIn("NativeLike.append", server.exports)
        self.assertEqual(server.exports["Dialog"].source, "game")
        self.assertEqual(server.exports["Dialog.invoke"].source, "game.Dialog")

    def test_export_module_includes_pybind_class_methods(self):
        server = mcp.EngineMcpServer(repo_root=REPO_ROOT, build_dir=build_dir)
        server.import_modules()
        server.inspect_and_export()

        self.assertIn("CGameLoader.loadGame", server.exports)
        self.assertIn("CGameLoader.loadGui", server.exports)
        self.assertIn("CGameLoader.startGameWithPlayer", server.exports)
        self.assertIn("CGuiHandler.openPanel", server.exports)

    def test_engine_call_resolves_handle_arguments_for_python_methods(self):
        server = self.make_stub_server()

        class Dialog:
            def invoke(self, action):
                return f"invoked:{action}"

        server.exports["Dialog.invoke"] = mcp.ExportedCallable(
            name="Dialog.invoke",
            source="test.Dialog",
            target_name="invoke",
            callable_obj=Dialog.invoke,
            signature="(self, action)",
        )

        handle = server._serialize_result(Dialog())
        response = server._engine_call(
            {
                "name": "Dialog.invoke",
                "args": [handle, "open"],
            }
        )

        self.assertFalse(response["isError"])
        self.assertEqual(response["structuredContent"]["result"], "invoked:open")

    def test_serialize_result_lists_python_methods_for_handles(self):
        server = self.make_stub_server()

        class Dialog:
            def invoke(self, action):
                return action

        handle = server._serialize_result(Dialog())

        self.assertEqual(handle["__type__"], "Dialog")
        self.assertEqual(handle["pythonMethods"], [{"name": "invoke", "signature": "(self, action)"}])

    def test_initialize_response_preserves_request_id(self):
        server = self.make_stub_server()
        response = server._handle_stdio_payload(
            {
                "jsonrpc": "2.0",
                "id": 41,
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-test", "version": "1.0"},
                },
            }
        )
        self.assertIsInstance(response, dict)
        self.assertEqual(response.get("id"), 41)
        self.assertEqual(response.get("result", {}).get("protocolVersion"), MCP_PROTOCOL_VERSION)

    def test_stdio_batch_handles_initialize_and_tool_listing(self):
        server = self.make_stub_server()
        init_response = server._handle_stdio_payload(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "mcp-test", "version": "1.0"},
                    },
                }
            ]
        )
        self.assertIsInstance(init_response, list)
        self.assertEqual(len(init_response), 1)
        self.assertEqual(init_response[0].get("id"), 1)
        self.assertEqual(init_response[0].get("result", {}).get("protocolVersion"), MCP_PROTOCOL_VERSION)
        self.assertIsNotNone(server.stdio_state)
        server.stdio_state.log_level = "critical"

        batch_response = server._handle_stdio_payload(
            [
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ]
        )
        self.assertIsInstance(batch_response, list)
        self.assertEqual(len(batch_response), 1)
        self.assertEqual(batch_response[0].get("id"), 2)
        tools = batch_response[0].get("result", {}).get("tools", [])
        tool_names = {tool.get("name") for tool in tools}
        self.assertTrue({"engine_list", "engine_call", "engine_handle_call"}.issubset(tool_names))

    def test_stdio_handshake_and_tool_listing(self):
        script = REPO_ROOT / "mcp.py"
        self.assertTrue(script.exists(), "MCP entry point is missing")
        proc = subprocess.Popen(
            [
                sys.executable,
                str(script),
                "--stdio",
                "--repo-root",
                str(REPO_ROOT),
                "--build-dir",
                str(build_dir),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            cwd=str(REPO_ROOT),
        )
        try:
            self._send_rpc(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "mcp-test", "version": "1.0"},
                    },
                },
            )
            initialize_response = self._read_rpc(proc)
            self.assertNotIn("error", initialize_response)
            self.assertEqual(initialize_response.get("id"), 1)
            result = initialize_response.get("result", {})
            server_info = result.get("serverInfo", {})
            self.assertEqual(server_info.get("name"), "fall-of-nouraajd-engine-mcp")

            self._send_rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

            self._send_rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            tools_response = self._read_rpc(proc)
            self.assertEqual(tools_response.get("id"), 2)
            tools = tools_response.get("result", {}).get("tools", [])
            tool_names = {tool.get("name") for tool in tools}
            self.assertTrue({"engine_list", "engine_call", "engine_handle_call"}.issubset(tool_names))
        finally:
            self._shutdown_process(proc)

    def test_stdio_gui_inventory_dump_from_repo_root(self):
        script = REPO_ROOT / "mcp.py"
        self.assertTrue(script.exists(), "MCP entry point is missing")
        proc = subprocess.Popen(
            [
                sys.executable,
                str(script),
                "--stdio",
                "--repo-root",
                str(REPO_ROOT),
                "--build-dir",
                str(build_dir),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            cwd=str(REPO_ROOT),
        )
        try:
            self._send_rpc(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "mcp-test", "version": "1.0"},
                    },
                },
            )
            initialize_response = self._read_rpc(proc)
            self.assertNotIn("error", initialize_response)
            self.assertEqual(initialize_response.get("id"), 1)

            self._send_rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

            game_handle = self._call_tool(proc, 2, "engine_call", {"name": "CGameLoader.loadGame"})["result"]
            self._call_tool(proc, 3, "engine_call", {"name": "CGameLoader.loadGui", "args": [game_handle]})
            self._call_tool(
                proc,
                4,
                "engine_call",
                {"name": "CGameLoader.startGameWithPlayer", "args": [game_handle, "test", DEFAULT_PLAYER]},
            )
            gui_handler_handle = self._call_tool(
                proc,
                5,
                "engine_handle_call",
                {"handle": game_handle["__handle__"], "method": "getGuiHandler"},
            )["result"]
            panel_handle = self._call_tool(
                proc,
                6,
                "engine_handle_call",
                {"handle": gui_handler_handle["__handle__"], "method": "openPanel", "args": ["inventoryPanel"]},
            )["result"]
            self.assertEqual(panel_handle["__type__"], "CGameInventoryPanel")
            gui_handle = self._call_tool(
                proc,
                7,
                "engine_handle_call",
                {"handle": game_handle["__handle__"], "method": "getGui"},
            )["result"]
            gui_tree = json.loads(
                self._call_tool(proc, 8, "engine_call", {"name": "jsonify", "args": [gui_handle]})["result"]
            )

            children = gui_tree.get("properties", {}).get("children") or []
            inventory_panels = [child for child in children if child.get("class") == "CGameInventoryPanel"]
            self.assertEqual(len(inventory_panels), 1, gui_tree)
            list_views = [
                child
                for child in (inventory_panels[0].get("properties", {}).get("children") or [])
                if child.get("class") == "CListView"
            ]
            self.assertEqual(len(list_views), 2, inventory_panels[0])
            self.assertIn(
                "inventoryRightClickCallback",
                [child.get("properties", {}).get("rightClickCallback") for child in list_views],
            )
        finally:
            self._shutdown_process(proc)

    def _send_rpc(self, proc, payload):
        if proc.stdin is None:
            self.fail("Process stdin not available")
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        proc.stdin.write(line.encode("utf-8"))
        proc.stdin.flush()

    def _call_tool(self, proc, request_id: int, name: str, arguments: dict):
        self._send_rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )
        response = self._read_rpc(proc)
        self.assertEqual(response.get("id"), request_id)
        result = response.get("result", {})
        self.assertFalse(result.get("isError"), result)
        return result.get("structuredContent", {})

    def _read_rpc(self, proc, timeout: float = 10.0):
        if proc.stdout is None:
            self.fail("Process stdout not available")
        deadline = time.monotonic() + timeout
        while True:
            line = self._readline(proc.stdout, deadline)
            if line in (b"", b"\r\n", b"\n"):
                continue
            payload = json.loads(line.decode("utf-8"))
            if "id" not in payload and "method" in payload:
                continue
            return payload

    def _readline(self, stream, deadline: float) -> bytes:
        if os.name == "nt":
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.fail("Timed out waiting for MCP response header")
            result_queue = queue.Queue(maxsize=1)

            def read_line():
                result_queue.put(stream.readline())

            threading.Thread(target=read_line, daemon=True).start()
            try:
                return result_queue.get(timeout=remaining)
            except queue.Empty:
                self.fail("Timed out waiting for MCP response header")

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.fail("Timed out waiting for MCP response header")
            readable, _, _ = select.select([stream], [], [], remaining)
            if readable:
                line = stream.readline()
                if not line:
                    return b""
                return line

    def _shutdown_process(self, proc):
        if proc.stdin:
            proc.stdin.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        stderr_output = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()
        if proc.returncode not in (0, None):
            self.fail(f"MCP server exited with {proc.returncode}: {stderr_output}")


if __name__ == "__main__":
    unittest.main(testRunner=unittest.TextTestRunner())
