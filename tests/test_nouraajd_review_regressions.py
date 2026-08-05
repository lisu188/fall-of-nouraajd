import ast
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOURAAJD_SCRIPT = REPO_ROOT / "res" / "maps" / "nouraajd" / "script.py"
NOURAAJD_DIALOG2 = REPO_ROOT / "res" / "maps" / "nouraajd" / "dialog2.json"
GAME_PY = REPO_ROOT / "res" / "game.py"
DIALOG_H = REPO_ROOT / "src" / "object" / "CDialog.h"
DIALOG_CPP = REPO_ROOT / "src" / "object" / "CDialog.cpp"
DIALOG_PANEL_CPP = REPO_ROOT / "src" / "gui" / "panel" / "CGameDialogPanel.cpp"
GAME_CONTEXT_H = REPO_ROOT / "src" / "core" / "CGameContext.h"
GAME_CONTEXT_CPP = REPO_ROOT / "src" / "core" / "CGameContext.cpp"
SCENE_MANAGER_CPP = REPO_ROOT / "src" / "core" / "CSceneManager.cpp"


def _find_nested_class(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"missing class {name}")


def _method(class_node, name):
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"missing method {class_node.name}.{name}")


def _returned_string(method):
    for node in ast.walk(method):
        if (
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    raise AssertionError(f"missing literal string return in {method.name}")


class NouraajdReviewRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script_source = NOURAAJD_SCRIPT.read_text(encoding="utf-8")
        cls.script_tree = ast.parse(cls.script_source, filename=str(NOURAAJD_SCRIPT))
        cls.game_source = GAME_PY.read_text(encoding="utf-8")
        cls.game_tree = ast.parse(cls.game_source, filename=str(GAME_PY))

    def test_octobogz_completed_dialog_settles_late_reward(self):
        document = json.loads(NOURAAJD_DIALOG2.read_text(encoding="utf-8"))
        states = document["dialog"]["properties"]["states"]
        entry = next(state for state in states if state["properties"]["stateId"] == "ENTRY")
        options = entry["properties"]["options"]
        completed = next(
            option
            for option in options
            if option.get("properties", {}).get("condition") == "contract_completed"
        )
        self.assertEqual("accept_quest", completed["properties"].get("action"))
        self.assertEqual("COMPLETED_THANKS", completed["properties"].get("nextStateId"))

        dialog_class = _find_nested_class(self.script_tree, "OctoBogzDialog")
        accept = _method(dialog_class, "accept_quest")
        calls = {
            node.func.attr
            for node in ast.walk(accept)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertIn("checkQuests", calls)

    def test_dialog_action_dispatch_reports_failure_and_panel_does_not_advance(self):
        dialog_class = _find_nested_class(self.game_tree, "CDialog")
        invoke_action = _method(dialog_class, "invokeAction")
        returned_constants = {
            node.value.value
            for node in ast.walk(invoke_action)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant)
        }
        self.assertIn(False, returned_constants)
        self.assertIn(True, returned_constants)

        dialog_h = DIALOG_H.read_text(encoding="utf-8")
        dialog_cpp = DIALOG_CPP.read_text(encoding="utf-8")
        panel_cpp = DIALOG_PANEL_CPP.read_text(encoding="utf-8")
        self.assertIn("bool invokeActionChecked(std::string action);", dialog_h)
        self.assertIn("bool CDialog::invokeActionChecked(std::string action)", dialog_cpp)
        self.assertIn("!dialog->invokeActionChecked(option->getAction())", panel_cpp)

        guard = panel_cpp.index("!dialog->invokeActionChecked(option->getAction())")
        advance = panel_cpp.index("currentStateId = option->getNextStateId().empty()")
        self.assertLess(guard, advance)

    def test_reused_retained_session_restores_departure_coordinate(self):
        context_h = GAME_CONTEXT_H.read_text(encoding="utf-8")
        context_cpp = GAME_CONTEXT_CPP.read_text(encoding="utf-8")
        scene_cpp = SCENE_MANAGER_CPP.read_text(encoding="utf-8")
        self.assertIn("setReturnCoords", context_h)
        self.assertIn("getReturnCoords", context_h)
        self.assertIn("returnCoordinates", context_h)
        self.assertIn("returnCoordinates.clear();", context_cpp)
        self.assertIn(
            "store->setReturnCoords(oldMap->getMapName(), request.returnAnchor, player->getCoords())",
            scene_cpp,
        )
        self.assertIn("reusedSession && retainedReturnCoords", scene_cpp)
        self.assertIn("game->getMap()->attachPlayer(player, *retainedReturnCoords)", scene_cpp)

        explicit_target = scene_cpp.index("if (request.targetCoords)")
        retained_target = scene_cpp.index("reusedSession && retainedReturnCoords")
        entry_fallback = scene_cpp.index("game->getMap()->attachPlayer(player);", retained_target)
        self.assertLess(explicit_target, retained_target)
        self.assertLess(retained_target, entry_fallback)

    def test_cleanse_quest_text_matches_order_independent_state_machine(self):
        quest = _find_nested_class(self.script_tree, "CleanseCaveQuest")
        objective = _returned_string(_method(quest, "getObjective"))
        hint = _returned_string(_method(quest, "getHint"))
        self.assertIn("Return the holy relic to Beren", objective)
        self.assertIn("destroy the OctoBogz", objective)
        self.assertNotIn("after the relic", hint)
        self.assertIn("relic back", hint)
        self.assertIn("OctoBogz must be dead", hint)

    def test_victor_encounter_objective_names_actual_success_target(self):
        quest = _find_nested_class(self.script_tree, "VictorQuest")
        objective_method = _method(quest, "getObjective")
        encounter_texts = [
            node.value.value
            for node in ast.walk(objective_method)
            if isinstance(node, ast.Return)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and "courtyard" in node.value.value
        ]
        self.assertIn(
            "Defeat the cult leader in the courtyard before Victor's daughter is taken.",
            encounter_texts,
        )

        leader_trigger = _find_nested_class(self.script_tree, "CultLeaderQuestTrigger")
        trigger_method = _method(leader_trigger, "trigger")
        called_methods = {
            node.func.attr
            for node in ast.walk(trigger_method)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertIn("mark_victor_good_end", called_methods)


if __name__ == "__main__":
    unittest.main()
