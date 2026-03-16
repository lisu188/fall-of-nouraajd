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
import re
import sys
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parent
TEST_OUTPUT_DIR = REPO_ROOT / "test"
XDG_RUNTIME_DIR = Path("/tmp") / f"xdg-runtime-{os.getuid()}"

if "XDG_RUNTIME_DIR" not in os.environ:
    XDG_RUNTIME_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.environ["XDG_RUNTIME_DIR"] = str(XDG_RUNTIME_DIR)

build_dir = REPO_ROOT / "cmake-build-release"
build_dir_override = os.environ.get("GAME_BUILD_DIR")
if build_dir_override:
    build_dir = (REPO_ROOT / build_dir_override).resolve()
if build_dir.exists():
    os.chdir(build_dir)

if str(Path.cwd()) not in sys.path:
    sys.path.insert(0, str(Path.cwd()))
if str(REPO_ROOT / "res") not in sys.path:
    sys.path.insert(1, str(REPO_ROOT / "res"))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(2, str(REPO_ROOT))


def load_game_module():
    game = importlib.import_module("game")
    builtins.game = game
    return game


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
    def test_combat_invariants(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        attacker = g.createObject("Warrior")
        defender = g.createObject("Goblin")
        g.getMap().addObject(attacker)
        g.getMap().addObject(defender)

        attacker_hp_before = attacker.getHpRatio()
        defender_hp_before = defender.getHpRatio()
        game.CFightHandler.fight(attacker, defender)

        self.assertGreaterEqual(attacker.getHpRatio(), 0.0)
        self.assertLessEqual(attacker.getHpRatio(), 1.0)
        self.assertGreaterEqual(defender.getHpRatio(), 0.0)
        self.assertLessEqual(defender.getHpRatio(), 1.0)

        one_side_took_damage = attacker.getHpRatio() < attacker_hp_before or defender.getHpRatio() < defender_hp_before
        self.assertTrue(one_side_took_damage)
        return True, ""

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
    def test_turns(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "nouraajd", "Warrior")
        advance(g, 100)
        return True, game.jsonify(g.getMap().ptr())  # TODO: why we need ptr? in all _bjects we dont!

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
            with open(path) as f:
                data = json.load(f)
            for key, value in data.items():
                if not isinstance(value, dict):
                    continue
                if value.get("class") == "CDialogOption":
                    option_defs[key] = value
                if isinstance(value.get("class"), str) and value.get("class").endswith("Dialog"):
                    dialog_defs[key] = value

        with open(dialog_dir / "script.py") as f:
            tree = ast.parse(f.read())
        methods_by_class = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith("Dialog"):
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
        for state in dialog3["tavernDialog2"]["properties"]["states"]:
            if state.get("properties", {}).get("stateId") == "COURTYARD_PATH":
                courtyard_state = state
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
    def test_json_validity(self):
        errors = []
        for path in (REPO_ROOT / "res").rglob("*.json"):
            try:
                with open(path) as f:
                    json.load(f)
            except Exception:
                errors.append(str(path))
        return errors == [], json.dumps(errors)

    @game_test
    def test_plugin_load_function(self):
        missing = []
        for path in (REPO_ROOT / "res/plugins").rglob("*.py"):
            with open(path) as f:
                tree = ast.parse(f.read())
            if not any(isinstance(n, ast.FunctionDef) and n.name == "load" for n in tree.body):
                missing.append(str(path))
        for path in (REPO_ROOT / "res/maps").rglob("script.py"):
            with open(path) as f:
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
            if "random-dungeon-generator" in parts or "vstd" in parts:
                continue
            with open(path) as f:
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
            with open(path) as f:
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


if __name__ == "__main__":
    unittest.main(testRunner=unittest.TextTestRunner())
