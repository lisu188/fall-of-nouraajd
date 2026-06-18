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
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_content import validate_repo


class ContentValidatorTest(unittest.TestCase):
    def test_current_content_passes_validation(self):
        issues = validate_repo(REPO_ROOT)
        self.assertEqual([], [str(issue) for issue in issues])

    def test_missing_refs_report_path_entry_and_field(self):
        root = self.make_fixture()
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["brokenCave"] = {"class": "CBuilding", "properties": {"monster": {"ref": "MissingMonster"}}}
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "brokenCave.properties.monster.ref",
            'unknown ref "MissingMonster"',
        )

    def test_duplicate_map_object_names_report_both_locations(self):
        root = self.make_fixture()
        map_path = root / "res/maps/broken/map.json"
        map_data = read_json(map_path)
        map_data["layers"][1]["objects"].append(
            {"id": 2, "name": "start", "type": "StartEvent", "x": 1, "y": 1, "width": 1, "height": 1}
        )
        write_json(map_path, map_data)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/map.json",
            "layers[1].objects[1].name",
            'duplicate object name "start"',
            "previously defined at layers[1].objects[0]",
        )

    def test_unreachable_dialog_state_reports_dialog_and_state(self):
        root = self.make_fixture()
        dialog_path = root / "res/maps/broken/dialog.json"
        dialog = read_json(dialog_path)
        dialog["brokenDialog"]["properties"]["states"].append(
            {
                "class": "CDialogState",
                "properties": {
                    "stateId": "ORPHAN_STATE",
                    "text": "Nobody can reach this.",
                    "options": [{"ref": "exitOption", "properties": {"number": 0}}],
                },
            }
        )
        write_json(dialog_path, dialog)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/dialog.json",
            "brokenDialog.properties.states[2].properties.stateId",
            "ORPHAN_STATE",
            "unreachable from ENTRY",
        )

    def test_invalid_dialog_action_and_condition_report_script_class_context(self):
        root = self.make_fixture()
        dialog_path = root / "res/maps/broken/dialog.json"
        dialog = read_json(dialog_path)
        option = dialog["brokenDialog"]["properties"]["states"][0]["properties"]["options"][0]["properties"]
        option["action"] = "missing_action"
        option["condition"] = "missing_condition"
        write_json(dialog_path, dialog)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/dialog.json",
            "properties.action",
            'dialog action "missing_action" is not defined on BrokenDialog',
            "res/maps/broken/script.py",
        )
        self.assertIssueContains(
            issues,
            "res/maps/broken/dialog.json",
            "properties.condition",
            'dialog condition "missing_condition" is not defined on BrokenDialog',
            "res/maps/broken/script.py",
        )

    def test_invalid_market_refs_report_market_field(self):
        root = self.make_fixture()
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["validMarket"]["properties"]["items"][0]["ref"] = "MissingPotion"
        config["brokenStand"] = {"class": "CBuilding", "properties": {"market": {"ref": "MissingMarket"}}}
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "validMarket.properties.items[0].ref",
            'unknown ref "MissingPotion"',
        )
        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "brokenStand.properties.market.ref",
            'unknown ref "MissingMarket"',
        )

    def test_invalid_script_quest_ids_report_call_location(self):
        root = self.make_fixture(script_quest="missingQuest")

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'ensure_quest("missingQuest")',
            'unknown quest id "missingQuest"',
        )

    def test_invalid_transition_targets_report_map_name(self):
        root = self.make_fixture(script_map="missingMap")

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'changeMap("missingMap")',
            "map transition target is missing res/maps/missingMap/map.json",
        )

    def test_invalid_class_names_report_object_and_field(self):
        root = self.make_fixture()
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["brokenEvent"] = {"class": "MissingEventClass"}
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "brokenEvent.class",
            'unknown class "MissingEventClass"',
        )

    def assertIssueContains(self, issues, *substrings):
        issue_text = "\n".join(str(issue) for issue in issues)
        for substring in substrings:
            with self.subTest(substring=substring):
                self.assertIn(substring, issue_text)

    def make_fixture(self, script_quest="goodQuest", script_map="broken"):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "res/config").mkdir(parents=True)
        (root / "res/plugins").mkdir(parents=True)
        (root / "res/maps/broken").mkdir(parents=True)

        write_json(
            root / "res/config/items.json",
            {
                "LifePotion": {"class": "CPotion"},
                "HitEffect": {"class": "CEffect"},
                "Attack": {"class": "CInteraction", "properties": {"effect": {"ref": "HitEffect"}}},
            },
        )
        write_json(
            root / "res/config/misc.json",
            {
                "exitOption": {
                    "class": "CDialogOption",
                    "properties": {"text": "Leave.", "nextStateId": "EXIT"},
                }
            },
        )
        write_json(
            root / "res/maps/broken/map.json",
            {
                "type": "map",
                "width": 2,
                "height": 2,
                "layers": [
                    {"type": "tilelayer", "width": 2, "height": 2, "data": [0, 0, 0, 0]},
                    {
                        "type": "objectgroup",
                        "objects": [
                            {
                                "id": 1,
                                "name": "start",
                                "type": "StartEvent",
                                "x": 0,
                                "y": 0,
                                "width": 1,
                                "height": 1,
                            }
                        ],
                    },
                ],
                "tilesets": [{"firstgid": 1, "tileproperties": {}}],
                "nextobjectid": 2,
            },
        )
        write_json(
            root / "res/maps/broken/config.json",
            {
                "goodQuest": {"class": "GoodQuest"},
                "validMarket": {"class": "CMarket", "properties": {"items": [{"ref": "LifePotion"}]}},
            },
        )
        write_json(root / "res/maps/broken/dialog.json", valid_dialog_config())
        write_script(root / "res/maps/broken/script.py", script_quest=script_quest, script_map=script_map)
        return root


def valid_dialog_config():
    return {
        "brokenDialog": {
            "class": "BrokenDialog",
            "properties": {
                "states": [
                    {
                        "class": "CDialogState",
                        "properties": {
                            "stateId": "ENTRY",
                            "text": "Start.",
                            "options": [
                                {
                                    "class": "CDialogOption",
                                    "properties": {
                                        "number": 0,
                                        "text": "Continue.",
                                        "nextStateId": "DONE",
                                        "action": "valid_action",
                                        "condition": "valid_condition",
                                    },
                                }
                            ],
                        },
                    },
                    {
                        "class": "CDialogState",
                        "properties": {
                            "stateId": "DONE",
                            "text": "Done.",
                            "options": [{"ref": "exitOption", "properties": {"number": 0}}],
                        },
                    },
                ]
            },
        }
    }


def write_script(path, script_quest, script_map):
    path.write_text(
        textwrap.dedent(f"""
            def load(self, context):
                from game import CDialog
                from game import CEvent
                from game import CQuest
                from game import register
                from game import trigger

                def ensure_quest(player, quest_name):
                    player.addQuest(quest_name)

                @register(context)
                class StartEvent(CEvent):
                    def onEnter(self, event):
                        self.getGame().createObject("validMarket")
                        self.getGame().changeMap("{script_map}")
                        ensure_quest(event.getCause(), "{script_quest}")
                        event.getCause().addItem("LifePotion")
                        self.getMap().getObjectByName("start")

                @register(context)
                class GoodQuest(CQuest):
                    pass

                @register(context)
                class BrokenDialog(CDialog):
                    def valid_action(self):
                        pass

                    def valid_condition(self):
                        return True

                @trigger(context, "onEnter", "start")
                class StartTrigger(CEvent):
                    pass
            """).lstrip(),
        encoding="utf-8",
    )


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
