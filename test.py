# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2019  Andrzej Lis
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
import json
import os
from pathlib import Path
import unittest


def game_test(f):
    def wrapper(self):
        n = f.__name__.split("test_")[1]
        os.makedirs("test", exist_ok=True)
        result = f(self)
        success = result[0]
        log = result[1]
        open(os.path.join("test", n + ".json"), "w").write(str(log))
        self.assertTrue(success)

    return wrapper


def advance(g, turns):
    import game

    current_turn = g.getMap().getNumericProperty("turn")
    for i in range(turns):
        g.getMap().move()
    while g.getMap().getNumericProperty("turn") < turns + current_turn:
        game.event_loop.instance().run()


class GameTest(unittest.TestCase):
    @game_test
    def test_objects(self):
        import game

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
        import game

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
        import game

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
        import game

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "nouraajd", "Warrior")
        advance(g, 100)
        return True, game.jsonify(g.getMap().ptr())  # TODO: why we need ptr? in all _bjects we dont!

    @game_test
    def test_pathfinder(self):
        import game

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "nouraajd", "Warrior")
        g.getMap().dumpPaths("test/pathfinder.png")
        return True, "test/pathfinder.png"

    @game_test
    def test_load(self):
        import game

        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadSavedGame(g, "gooby")
        return True, ""

    @game_test
    def test_random(self):
        import game

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startRandomGameWithPlayer(g, "Warrior")
        g.getMap().dumpPaths("test/random.png")
        return True, "test/random.png"

    @game_test
    def test_dialogs(self):
        option_defs = {}
        dialog_defs = {}

        misc = Path("res/config/misc.json")
        if misc.exists():
            with open(misc) as f:
                data = json.load(f)
                for key, value in data.items():
                    if isinstance(value, dict) and value.get("class") == "CDialogOption":
                        option_defs[key] = value

        dialog_dir = Path("res/maps/nouraajd")
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

        success = not (missing_actions or missing_states or unreachable_states)
        log = {
            "missing_actions": sorted(missing_actions),
            "missing_states": sorted(missing_states),
            "unreachable_states": sorted(unreachable_states),
        }
        return success, json.dumps(log)

    @game_test
    def test_json_validity(self):
        errors = []
        for path in Path("res").rglob("*.json"):
            try:
                with open(path) as f:
                    json.load(f)
            except Exception:
                errors.append(str(path))
        return errors == [], json.dumps(errors)

    @game_test
    def test_plugin_load_function(self):
        missing = []
        for path in Path("res/plugins").rglob("*.py"):
            with open(path) as f:
                tree = ast.parse(f.read())
            if not any(isinstance(n, ast.FunctionDef) and n.name == "load" for n in tree.body):
                missing.append(str(path))
        for path in Path("res/maps").rglob("script.py"):
            with open(path) as f:
                tree = ast.parse(f.read())
            if not any(isinstance(n, ast.FunctionDef) and n.name == "load" for n in tree.body):
                missing.append(str(path))
        return missing == [], json.dumps(missing)

    @game_test
    def test_indentation(self):
        offenders = []
        for path in Path(".").rglob("*.py"):
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
        for path in Path("res/config").rglob("*.json"):
            with open(path) as f:
                data = json.load(f)
            for key, val in self._collect_resource_paths(data):
                base = Path("res") / val
                if base.exists():
                    continue
                candidate = base if base.suffix else base.with_suffix(".png")
                if not candidate.exists():
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
