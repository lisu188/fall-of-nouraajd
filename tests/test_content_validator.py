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

from scripts.validate_content import (
    ArchetypeMigrationException,
    ContentValidator,
    ScriptPropertyHygieneAllowance,
    classify_creature_templates,
    inventory_creature_overrides,
    iter_cpp_template_type_names,
    report_legacy_class_checks,
    report_unmigrated_creatures,
    tile_types_by_id,
    validate_repo,
)


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

    def test_duplicate_json_object_keys_are_flagged(self):
        root = self.make_fixture()
        map_path = root / "res/maps/broken/map.json"
        # Inject a literal duplicate key. Python's json keeps the last value, but
        # the engine's strict C++ loader rejects the whole document, so the
        # validator must flag it. write_json cannot emit duplicates -- patch raw text.
        text = map_path.read_text(encoding="utf-8")
        patched = text.replace('"layers":', '"width": 24,\n  "width": 24,\n  "layers":', 1)
        self.assertNotEqual(text, patched, "expected to inject a duplicate key")
        map_path.write_text(patched, encoding="utf-8")

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/map.json",
            'duplicate JSON object key "width"',
        )

    def _declare_map_assets(self, root, assets):
        map_path = root / "res/maps/broken/map.json"
        map_data = read_json(map_path)
        map_data["assets"] = assets
        write_json(map_path, map_data)
        return map_path

    def _make_asset_files(self, root):
        map_dir = root / "res/maps/broken"
        (map_dir / "images").mkdir(parents=True, exist_ok=True)
        (map_dir / "images/portrait.png").write_text("png")
        (map_dir / "frames").mkdir(parents=True, exist_ok=True)
        (map_dir / "frames/0.png").write_text("png")
        (map_dir / "sprites").mkdir(parents=True, exist_ok=True)
        (map_dir / "sprites/0.png").write_text("png")
        (map_dir / "anim").mkdir(parents=True, exist_ok=True)
        (map_dir / "anim/walk.png").write_text("png")

    def test_map_assets_valid_declarations_pass_validation(self):
        root = self.make_fixture()
        self._make_asset_files(root)
        self._declare_map_assets(
            root,
            [
                {"path": "images/portrait.png", "kind": "file"},
                {"path": "frames", "kind": "directory"},
                {"path": "anim/walk", "kind": "animationRoot"},
                {"path": "sprites", "kind": "animationRoot"},
                {"path": "hero.combat.idle", "kind": "logicalId"},
            ],
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_map_assets_non_array_is_flagged(self):
        root = self.make_fixture()
        self._declare_map_assets(root, {"path": "images/portrait.png", "kind": "file"})

        issues = validate_repo(root)

        self.assertIssueContains(issues, "res/maps/broken/map.json", "assets", "expected array")

    def test_map_assets_unsafe_path_is_flagged(self):
        root = self.make_fixture()
        self._declare_map_assets(root, [{"path": "../escape.png", "kind": "file"}])

        issues = validate_repo(root)

        self.assertIssueContains(issues, "res/maps/broken/map.json", "assets[0].path", "safe relative path")

    def test_map_assets_missing_target_is_flagged(self):
        root = self.make_fixture()
        self._declare_map_assets(
            root,
            [
                {"path": "images/missing.png", "kind": "file"},
                {"path": "nodir", "kind": "directory"},
                {"path": "anim/none", "kind": "animationRoot"},
            ],
        )

        issues = validate_repo(root)

        self.assertIssueContains(issues, "assets[0].path", "declared file asset not found: images/missing.png")
        self.assertIssueContains(issues, "assets[1].path", "declared directory asset not found: nodir")
        self.assertIssueContains(issues, "assets[2].path", "animation root resolves to neither")

    def test_map_assets_invalid_entry_shape_is_flagged(self):
        root = self.make_fixture()
        self._make_asset_files(root)
        self._declare_map_assets(
            root,
            [
                "notanobject",
                {"kind": "file"},
                {"path": "images/portrait.png", "kind": "sprite"},
            ],
        )

        issues = validate_repo(root)

        self.assertIssueContains(issues, "assets[0]", "expected object with 'path' and 'kind'")
        self.assertIssueContains(issues, "assets[1].path", "expected non-empty string")
        self.assertIssueContains(issues, "assets[2].kind", "expected one of")

    def test_map_assets_duplicate_path_is_flagged(self):
        root = self.make_fixture()
        self._declare_map_assets(
            root,
            [
                {"path": "shared.id", "kind": "logicalId"},
                {"path": "shared.id", "kind": "logicalId"},
            ],
        )

        issues = validate_repo(root)

        self.assertIssueContains(issues, "assets[1].path", "duplicate asset declaration: shared.id")

    def _reference_map_animation(self, root, animation):
        # Add a map object whose ``properties.animation`` references a map-local asset by its
        # bare, map-relative name -- exactly the reference site _iter_map_asset_reference_sites
        # collects (``layers[].objects[].properties.animation``). The object carries no name so
        # it stays clear of the placed-name / trigger-recognition checks.
        map_path = root / "res/maps/broken/map.json"
        map_data = read_json(map_path)
        map_data["layers"][1]["objects"].append(
            {
                "id": 2,
                "type": "StartEvent",
                "x": 1,
                "y": 1,
                "width": 1,
                "height": 1,
                "properties": {"animation": animation},
            }
        )
        write_json(map_path, map_data)
        return map_path

    def test_map_asset_reference_to_declared_animation_passes_validation(self):
        root = self.make_fixture()
        self._make_asset_files(root)
        self._declare_map_assets(root, [{"path": "anim/walk", "kind": "animationRoot"}])
        self._reference_map_animation(root, "anim/walk")

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_map_asset_reference_to_undeclared_animation_is_flagged(self):
        root = self.make_fixture()
        self._make_asset_files(root)
        # The map declares an unrelated asset, so the consistency check runs, but the
        # referenced map-local animation ("anim/walk", which exists on disk as anim/walk.png)
        # is never declared -- it would not be staged into the build, so it is flagged.
        self._declare_map_assets(root, [{"path": "images/portrait.png", "kind": "file"}])
        self._reference_map_animation(root, "anim/walk")

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/map.json",
            "layers[1].objects[1].properties.animation",
            "references map-local asset 'anim/walk' that is not declared in the map's 'assets' array",
        )

    def test_map_asset_reference_to_global_asset_is_not_flagged(self):
        root = self.make_fixture()
        # A global asset packaged independently of the map under res/. Even though the map
        # declares an assets array (activating the consistency check), a reference that
        # resolves through the base res/ search path must never be treated as map-local.
        (root / "res/images").mkdir(parents=True, exist_ok=True)
        (root / "res/images/global_sprite.png").write_text("png")
        self._declare_map_assets(root, [{"path": "hero.combat.idle", "kind": "logicalId"}])
        self._reference_map_animation(root, "images/global_sprite")

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_panels_charsheet_uses_flattened_primitive_and_validates(self):
        # EPIC_03/STORY_04/SUBSTORY_05: CGameCharacterPanel.charSheet (a CMapStringString wrapper) was
        # migrated from the legacy schema-1 object-shape to the current flattened shape (a bare JSON
        # object with no class/properties envelope). Confirm the real content is authored in the
        # flattened form and that metadata-aware validation of the full repo accepts it -- i.e. the
        # flattened primitive representation is a valid alternative to the legacy object-shape while
        # every other resource file remains valid.
        panels = json.loads((REPO_ROOT / "res/config/panels.json").read_text(encoding="utf-8"))
        char_sheet = panels["characterPanel"]["properties"]["charSheet"]
        self.assertNotIn("class", char_sheet)
        self.assertNotIn("properties", char_sheet)
        self.assertEqual("getPlayerClassId", char_sheet.get("Class"))
        self.assertEqual([], [str(issue) for issue in validate_repo(REPO_ROOT)])

    def _valid_class_profile(self):
        return {
            "warrior": {
                "profileKind": "playerClass",
                "label": "Warrior",
                "actions": ["Attack"],
                "levelling": {"1": "Strike", "2": "Barrier"},
                "statContribution": {"strength": 3, "stamina": 2},
                "startingEquipment": {"policy": "fixed", "slots": {"0": "Sword"}},
            }
        }

    def _valid_race_profile(self):
        return {
            "human": {
                "profileKind": "playerRace",
                "label": "Human",
                "baseStatContribution": {"strength": 5, "agility": 5},
                "traits": ["humanoid"],
                "resistances": {},
                "visual": {"animation": "images/players/warrior"},
            }
        }

    def test_class_and_race_profiles_valid_pass_validation(self):
        root = self.make_fixture()
        write_json(root / "res/config/classes.json", self._valid_class_profile())
        write_json(root / "res/config/races.json", self._valid_race_profile())

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_class_profile_missing_and_mistyped_fields_are_flagged(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/classes.json",
            {
                "warrior": {
                    "profileKind": "playerRace",
                    "label": "",
                    "actions": ["Attack", ""],
                    "statContribution": {"strength": "high"},
                    "startingEquipment": {"policy": "bogus"},
                    "extra": 1,
                }
            },
        )

        issues = validate_repo(root)

        self.assertIssueContains(issues, "res/config/classes.json", "warrior.profileKind", 'expected "playerClass"')
        self.assertIssueContains(issues, "warrior.label", "expected non-empty string")
        self.assertIssueContains(issues, "warrior.actions[1]", "expected non-empty string")
        self.assertIssueContains(issues, "warrior.levelling", "expected object")
        self.assertIssueContains(issues, "warrior.statContribution.strength", "expected integer")
        self.assertIssueContains(issues, "warrior.startingEquipment.policy", "expected one of")
        self.assertIssueContains(issues, "warrior", "unsupported profile keys: extra")

    def test_race_profile_invalid_types_are_flagged(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/races.json",
            {
                "human": {
                    "profileKind": "playerRace",
                    "label": "Human",
                    "baseStatContribution": {"strength": 1.5},
                    "traits": ["ok", 2],
                    "resistances": {"fire": True},
                }
            },
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues, "res/config/races.json", "human.baseStatContribution.strength", "expected integer"
        )
        self.assertIssueContains(issues, "human.traits[1]", "expected non-empty string")
        self.assertIssueContains(issues, "human.resistances.fire", "expected integer")

    PLAYER_TEMPLATES = {
        "Warrior": {"class": "CPlayer", "properties": {"label": "Warrior"}},
        "Sorcerer": {"class": "CPlayer", "properties": {"label": "Sorcerer"}},
    }

    def test_valid_player_class_id_reference_passes_validation(self):
        root = self.make_fixture(
            class_check='player.getPlayerClassId() == "Warrior"',
            player_templates=self.PLAYER_TEMPLATES,
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_unknown_player_class_id_reference_is_flagged(self):
        root = self.make_fixture(
            class_check='player.getPlayerClassId() == "Bogus"',
            player_templates=self.PLAYER_TEMPLATES,
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'getPlayerClassId() == "Bogus"',
            'unknown class id "Bogus"',
        )

    def test_membership_player_class_id_reference_flags_only_unknown_member(self):
        root = self.make_fixture(
            class_check='player.getPlayerClassId() in ("Warrior", "Ghost")',
            player_templates=self.PLAYER_TEMPLATES,
        )

        issues = validate_repo(root)

        issue_text = "\n".join(str(issue) for issue in issues)
        self.assertIn('unknown class id "Ghost"', issue_text)
        self.assertNotIn('unknown class id "Warrior"', issue_text)

    def test_explicit_player_class_id_property_is_a_valid_reference(self):
        templates = {
            "ChampionTemplate": {
                "class": "CPlayer",
                "properties": {"label": "Champion", "playerClassId": "Champion"},
            }
        }
        root = self.make_fixture(
            class_check='player.getPlayerClassId() == "Champion"',
            player_templates=templates,
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_legacy_gettypeid_class_check_is_non_fatal_but_reported(self):
        root = self.make_fixture(
            class_check='player.getTypeId() == "Warrior"',
            player_templates=self.PLAYER_TEMPLATES,
        )

        issues = validate_repo(root)
        self.assertEqual([], [str(issue) for issue in issues])

        legacy = report_legacy_class_checks(root)
        self.assertEqual(1, len(legacy))
        self.assertEqual("Warrior", legacy[0].class_id)
        self.assertEqual("res/maps/broken/script.py", legacy[0].path)
        self.assertIn("class_condition", legacy[0].context)

    def test_non_player_gettypeid_check_is_ignored(self):
        root = self.make_fixture(
            class_check='monster.getTypeId() == "Ghost"',
            player_templates=self.PLAYER_TEMPLATES,
        )

        issues = validate_repo(root)
        self.assertEqual([], [str(issue) for issue in issues])
        self.assertEqual([], report_legacy_class_checks(root))

    def test_interaction_with_buff_effect_and_self_target_passes(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/combat.json",
            {
                "BuffFx": {"class": "CEffect", "properties": {"tags": ["buff"]}},
                "SelfBuff": {
                    "class": "CInteraction",
                    "properties": {"effect": {"ref": "BuffFx"}, "selfTarget": True},
                },
            },
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_interaction_with_buff_effect_without_self_target_is_flagged(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/combat.json",
            {
                "BuffFx": {"class": "CEffect", "properties": {"tags": ["buff"]}},
                "LegacyBuff": {"class": "CInteraction", "properties": {"effect": {"ref": "BuffFx"}}},
            },
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/combat.json",
            "LegacyBuff.properties.selfTarget",
            'must declare "selfTarget": true',
        )

    def test_interaction_inherits_self_target_through_ref(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/combat.json",
            {
                "BuffFx": {"class": "CEffect", "properties": {"tags": ["buff"]}},
                "SelfBuff": {
                    "class": "CInteraction",
                    "properties": {"effect": {"ref": "BuffFx"}, "selfTarget": True},
                },
                "GrantedBuff": {"ref": "SelfBuff"},
            },
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_interaction_with_non_buff_effect_needs_no_self_target(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/combat.json",
            {
                "PoisonFx": {"class": "CEffect", "properties": {"tags": ["stun"]}},
                "Poison": {"class": "CInteraction", "properties": {"effect": {"ref": "PoisonFx"}}},
            },
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_interaction_with_explicit_self_target_false_is_flagged(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/combat.json",
            {
                "BuffFx": {"class": "CEffect", "properties": {"tags": ["buff"]}},
                "MislabeledBuff": {
                    "class": "CInteraction",
                    "properties": {"effect": {"ref": "BuffFx"}, "selfTarget": False},
                },
            },
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/combat.json",
            "MislabeledBuff.properties.selfTarget",
            'must declare "selfTarget": true',
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

    def _set_dialog_callback(self, root, *, action=None, condition=None):
        dialog_path = root / "res/maps/broken/dialog.json"
        dialog = read_json(dialog_path)
        option = dialog["brokenDialog"]["properties"]["states"][0]["properties"]["options"][0]["properties"]
        if action is not None:
            option["action"] = action
        if condition is not None:
            option["condition"] = condition
        write_json(dialog_path, dialog)
        return dialog_path

    def test_valid_dialog_callbacks_pass_validation(self):
        root = self.make_fixture()
        self._set_dialog_callback(root, action="valid_action", condition="valid_condition")

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_empty_dialog_callback_name_is_flagged(self):
        root = self.make_fixture()
        self._set_dialog_callback(root, action="", condition="")

        issues = validate_repo(root)

        self.assertIssueContains(issues, "properties.action", "empty dialog action name")
        self.assertIssueContains(issues, "properties.condition", "empty dialog condition name")

    def test_non_identifier_dialog_callback_name_is_flagged(self):
        root = self.make_fixture()
        self._set_dialog_callback(root, action="valid action", condition="9condition")

        issues = validate_repo(root)

        self.assertIssueContains(issues, "properties.action", 'dialog action "valid action" is not a valid method name')
        self.assertIssueContains(
            issues, "properties.condition", 'dialog condition "9condition" is not a valid method name'
        )

    def test_private_and_dunder_dialog_callback_names_are_flagged(self):
        root = self.make_fixture()
        self._set_dialog_callback(root, action="_private_action", condition="__dunder__")

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "properties.action",
            'dialog action "_private_action" is private and is rejected by the reflective dispatch',
        )
        self.assertIssueContains(
            issues,
            "properties.condition",
            'dialog condition "__dunder__" is private and is rejected by the reflective dispatch',
        )

    def test_dispatch_entry_point_dialog_callback_name_is_flagged(self):
        root = self.make_fixture()
        self._set_dialog_callback(root, action="invokeAction", condition="invokeCondition")

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "properties.action",
            'dialog action "invokeAction" is the reflective dispatch entry point and cannot be a callback',
        )
        self.assertIssueContains(
            issues,
            "properties.condition",
            'dialog condition "invokeCondition" is the reflective dispatch entry point and cannot be a callback',
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

    def test_script_analyzer_collects_quest_state_and_property_usage(self):
        root = self.make_fixture()
        script_path = root / "res/maps/broken/script.py"
        script_path.write_text(
            textwrap.dedent("""
                def load(self, context):
                    from game import CQuest
                    from game import LegacyBoolFlag
                    from game import QuestStateStore
                    from game import register

                    TRANSITION_GUARD = "transition_guard"

                    def _grant_quest(player, quest_name):
                        player.addQuest(quest_name)

                    def _set_bool_property_default(obj, name, value):
                        if not hasattr(obj, name):
                            obj.setBoolProperty(name, value)

                    def _quest_system_from(obj):
                        return QuestSystem(obj.getGame().getMap())

                    class QuestSystem(QuestStateStore):
                        QUEST_KEYS = {
                            "main": "quest_state_main",
                            "side": "quest_state_side",
                        }

                        QUEST_DEFAULTS = {
                            "main": "locked",
                            "side": "not_started",
                        }

                        LEGACY_BOOL_FLAGS = (
                            LegacyBoolFlag("MAIN_DONE", "main", states=("done",)),
                            LegacyBoolFlag("SIDE_OPEN", "side", excluded_states=("locked",)),
                        )

                        def advance(self, player):
                            if self.get_state("main") == "locked":
                                self._set_state("main", "active")
                                _grant_quest(player, "goodQuest")
                                player.addQuest("bonusQuest")
                            side_state = self.get_state("side")
                            if side_state in ("not_started", "active"):
                                self._set_state("side", "done")
                            self.set_state("side", "public_done")
                            next_state = "done" if player.getBoolProperty("has_relic") else "failed"
                            self._set_state("main", next_state)
                            if player.getBoolProperty(TRANSITION_GUARD):
                                player.setBoolProperty(TRANSITION_GUARD, False)
                            self.map.setBoolProperty("MAIN_DONE", True)
                            self.map.setNumericProperty("MAIN_TURN", self.map.getTurn())
                            self.map.getNumericProperty("MAIN_TURN")
                            _set_bool_property_default(player, "skill_flag", False)

                        def main_done(self):
                            return self.get_state("main") in ("done", "failed")

                        def side_done(self):
                            return self.state_in("side", ("done",))

                    @register(context)
                    class GoodQuest(CQuest):
                        def isCompleted(self):
                            return _quest_system_from(self).get_state("main") == "done"
                """).lstrip(),
            encoding="utf-8",
        )
        info = ContentValidator(root)._parse_script(script_path)
        self.assertIsNotNone(info)
        if info is None:
            return

        main_state = info.quest_states["main"]
        self.assertEqual("quest_state_main", main_state.storage_key)
        self.assertEqual("locked", main_state.default_state)
        self.assertEqual({"locked", "done", "failed"}, main_state.read_states)
        self.assertEqual({"active", "done", "failed"}, main_state.written_states)
        self.assertEqual({"done", "failed"}, main_state.terminal_check_states)

        side_state = info.quest_states["side"]
        self.assertEqual("quest_state_side", side_state.storage_key)
        self.assertEqual("not_started", side_state.default_state)
        self.assertEqual({"not_started", "active", "done"}, side_state.read_states)
        self.assertEqual({"done", "public_done"}, side_state.written_states)
        self.assertEqual({"done"}, side_state.terminal_check_states)

        legacy_flags = {flag.name: flag for flag in info.legacy_bool_flags}
        self.assertEqual("main", legacy_flags["MAIN_DONE"].quest)
        self.assertEqual(("done",), legacy_flags["MAIN_DONE"].states)
        self.assertEqual("side", legacy_flags["SIDE_OPEN"].quest)
        self.assertEqual(("locked",), legacy_flags["SIDE_OPEN"].excluded_states)

        quest_grants = {(call.name, call.value) for call in info.quest_grants}
        self.assertIn(("_grant_quest", "goodQuest"), quest_grants)
        self.assertIn(("addQuest", "bonusQuest"), quest_grants)

        property_reads = {(access.owner, access.name, access.method) for access in info.property_reads}
        property_writes = {(access.owner, access.name, access.method) for access in info.property_writes}
        self.assertIn(("player", "has_relic", "getBoolProperty"), property_reads)
        self.assertIn(("player", "transition_guard", "getBoolProperty"), property_reads)
        self.assertIn(("map", "MAIN_TURN", "getNumericProperty"), property_reads)
        self.assertIn(("player", "transition_guard", "setBoolProperty"), property_writes)
        self.assertIn(("map", "MAIN_DONE", "setBoolProperty"), property_writes)
        self.assertIn(("map", "MAIN_TURN", "setNumericProperty"), property_writes)
        self.assertIn(("player", "skill_flag", "setBoolProperty"), property_writes)

    def test_script_analyzer_inventories_runtime_spawned_creatures(self):
        root = self.make_fixture()
        script_path = root / "res/maps/broken/script.py"
        script_path.write_text(
            textwrap.dedent("""
                def load(self, context):
                    from game import CTrigger
                    from game import register

                    NAME_PREFIX = "wave"

                    def spawn_quest_actors(game, game_map):
                        leader = game.createObject("CultLeader")
                        leader.setStringProperty("name", "cultLeaderQuest")
                        game_map.addObject(leader)

                        controller = game.createObject("CTargetController")
                        controller.setTarget("player")

                        for index in range(3):
                            mob = game.createObject("Cultist")
                            mob.setStringProperty("name", f"{NAME_PREFIX}{index}")
                            game_map.addObject(mob)

                        game_map.addObjectByName("siegePritz", game_map.getCoords())
                """).lstrip(),
            encoding="utf-8",
        )
        info = ContentValidator(root)._parse_script(script_path)
        self.assertIsNotNone(info)
        if info is None:
            return

        spawns = {(c.spawn_call, c.template, c.runtime_name) for c in info.spawned_creatures}

        # createObject template ids are recorded with their literal post-spawn names.
        self.assertIn(("createObject", "CultLeader", "cultLeaderQuest"), spawns)
        # createObject without a name write stays anonymous (controllers, etc.).
        self.assertIn(("createObject", "CTargetController", None), spawns)
        # A computed (f-string) name is NOT inferred -- only literal names are kept.
        self.assertIn(("createObject", "Cultist", None), spawns)
        # addObjectByName spawns are anonymous: template preserved, no runtime name.
        self.assertIn(("addObjectByName", "siegePritz", None), spawns)

        # Template ids and runtime names are tracked separately so a migration can
        # preserve both for the trigger validators that special-case quest actors.
        templates = {c.template for c in info.spawned_creatures}
        runtime_names = {c.runtime_name for c in info.spawned_creatures if c.runtime_name is not None}
        self.assertEqual({"CultLeader", "CTargetController", "Cultist", "siegePritz"}, templates)
        self.assertEqual({"cultLeaderQuest"}, runtime_names)

    def test_script_analyzer_inventories_real_quest_creature_spawns(self):
        # Names must come from real script source, never from design docs.
        info = ContentValidator(REPO_ROOT)._parse_script(REPO_ROOT / "res/maps/nouraajd/script.py")
        self.assertIsNotNone(info)
        if info is None:
            return
        named = {c.template: c.runtime_name for c in info.spawned_creatures if c.runtime_name is not None}
        self.assertEqual("cultLeaderQuest", named.get("CultLeader"))
        self.assertEqual("gooby1", named.get("gooby"))
        self.assertEqual("amuletGoblin", named.get("goblinThief"))

    def test_real_gooby_quest_runtime_names_preserved(self):
        # The real nouraajd chain (createObject("gooby") -> name "gooby1", onDestroy
        # trigger on "gooby1") must satisfy the runtime-name preservation guard.
        issues = validate_repo(REPO_ROOT)
        gooby_issues = [str(issue) for issue in issues if "gooby" in str(issue).lower()]
        self.assertEqual([], gooby_issues)

    def test_renamed_gooby_template_breaks_chain(self):
        root = self.make_fixture()
        write_gooby_chain_script(
            root / "res/maps/broken/script.py",
            template="goobyMonster",  # template renamed away from "gooby"
            runtime="gooby1",
            trigger_target="gooby1",
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'no spawn of template "gooby" remains',
        )

    def test_renamed_gooby_runtime_name_breaks_chain(self):
        root = self.make_fixture()
        write_gooby_chain_script(
            root / "res/maps/broken/script.py",
            template="gooby",
            runtime="goobyAlive",  # runtime name renamed away from "gooby1"
            trigger_target="goobyAlive",
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'does not rename the runtime object to "gooby1"',
        )

    def test_gooby_runtime_name_without_trigger_breaks_chain(self):
        root = self.make_fixture()
        write_gooby_chain_script(
            root / "res/maps/broken/script.py",
            template="gooby",
            runtime="gooby1",
            trigger_target=None,  # nothing recognizes "gooby1" anymore
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'no trigger recognizes "gooby1"',
        )

    def test_intact_gooby_chain_fixture_passes_guard(self):
        # The synthetic chain, when intact, raises no Gooby preservation issue
        # (proving the rule is load-bearing rather than always-failing).
        root = self.make_fixture()
        write_gooby_chain_script(
            root / "res/maps/broken/script.py",
            template="gooby",
            runtime="gooby1",
            trigger_target="gooby1",
        )

        issues = validate_repo(root)

        gooby_issues = [str(issue) for issue in issues if "gooby" in str(issue).lower()]
        self.assertEqual([], gooby_issues)

    def test_given_player_bool_read_without_default_when_validating_then_reports_uninitialized_property(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            @register(context)
            class StartEvent(CEvent):
                def onEnter(self, event):
                    player = self.getMap().getPlayer()
                    if player.getBoolProperty("has_relic"):
                        player.addGold(1)
            """,
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            "StartEvent.onEnter",
            'getBoolProperty("has_relic")',
            'player bool property "has_relic" is read without a write/default',
        )

    def test_given_stale_map_bool_write_when_validating_then_reports_write_only_property(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            @register(context)
            class StartEvent(CEvent):
                def onEnter(self, event):
                    game_map = self.getMap()
                    game_map.setBoolProperty("STALE_FLAG", True)
            """,
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            "StartEvent.onEnter",
            'setBoolProperty("STALE_FLAG")',
            'write-only map bool property "STALE_FLAG"',
        )

    def test_given_stale_player_bool_write_when_validating_then_reports_write_only_property(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            @register(context)
            class StartEvent(CEvent):
                def onEnter(self, event):
                    player = self.getMap().getPlayer()
                    player.setBoolProperty("STALE_PLAYER_FLAG", True)
            """,
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            "StartEvent.onEnter",
            'setBoolProperty("STALE_PLAYER_FLAG")',
            'write-only player bool property "STALE_PLAYER_FLAG"',
        )

    def test_given_map_and_player_bool_name_collision_when_validating_then_reports_owner_collision(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            @register(context)
            class StartEvent(CEvent):
                def onEnter(self, event):
                    game_map = self.getMap()
                    player = game_map.getPlayer()
                    game_map.setBoolProperty("shared_flag", True)
                    game_map.getBoolProperty("shared_flag")
                    player.setBoolProperty("shared_flag", True)
                    player.getBoolProperty("shared_flag")
            """,
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'bool property "shared_flag" is used on multiple owners: map, player',
        )

    def test_given_unknown_receiver_for_reviewed_bool_when_validating_then_reports_manual_review(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            @register(context)
            class StartEvent(CEvent):
                def onEnter(self, event):
                    game_map = self.getMap()
                    game_map.setBoolProperty("reviewed_flag", True)
                    game_map.getBoolProperty("reviewed_flag")
                    if holder.getBoolProperty("reviewed_flag"):
                        game_map.getPlayer().addGold(1)
            """,
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'getBoolProperty("reviewed_flag")',
            'bool property "reviewed_flag" has unknown receiver; manual review required',
        )

    def test_given_unknown_legacy_bool_quest_key_when_validating_then_reports_missing_mapping(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            class QuestSystem(QuestStateStore):
                QUEST_KEYS = {"main": "quest_state_main"}
                LEGACY_BOOL_FLAGS = (
                    LegacyBoolFlag("BROKEN_LEGACY_FLAG", "missing", states=("done",)),
                )

            @register(context)
            class StartEvent(CEvent):
                pass
            """,
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'LegacyBoolFlag("BROKEN_LEGACY_FLAG")',
            'legacy bool flag "BROKEN_LEGACY_FLAG" references unknown quest key "missing"',
        )

    def test_given_valid_legacy_bool_sync_when_validating_then_accepts_map_flag_read(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            class QuestSystem(QuestStateStore):
                QUEST_KEYS = {"main": "quest_state_main"}
                QUEST_DEFAULTS = {"main": "locked"}
                LEGACY_BOOL_FLAGS = (
                    LegacyBoolFlag("MAIN_DONE", "main", states=("done",)),
                )

                def complete(self):
                    self._set_state("main", "done")

            @register(context)
            class StartEvent(CEvent):
                def onEnter(self, event):
                    game_map = self.getMap()
                    if game_map.getBoolProperty("MAIN_DONE"):
                        game_map.getPlayer().addGold(1)
            """,
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_given_allowlisted_compatibility_flag_when_validating_then_suppresses_write_only_diagnostic(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            @register(context)
            class StartEvent(CEvent):
                def onEnter(self, event):
                    game_map = self.getMap()
                    game_map.setBoolProperty("STALE_FLAG", True)
            """,
        )
        allowance = ScriptPropertyHygieneAllowance(
            path="res/maps/broken/script.py",
            owner="map",
            name="STALE_FLAG",
            reason="Regression fixture for an externally read compatibility flag.",
        )

        issues = ContentValidator(root, property_hygiene_allowlist=(allowance,)).validate()

        self.assertEqual([], [str(issue) for issue in issues])

    def test_given_default_for_undeclared_quest_key_when_validating_then_reports_missing_declaration(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            class QuestSystem(QuestStateStore):
                QUEST_KEYS = {"main": "quest_state_main"}
                QUEST_DEFAULTS = {"main": "locked", "ghost": "not_started"}

            @register(context)
            class StartEvent(CEvent):
                pass
            """,
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'quest "ghost"',
            'quest default "not_started" references undeclared quest key "ghost" (missing from QUEST_KEYS)',
        )

    def test_given_transition_target_for_undeclared_quest_key_when_validating_then_reports_missing_declaration(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            class QuestSystem(QuestStateStore):
                QUEST_KEYS = {"main": "quest_state_main"}
                QUEST_DEFAULTS = {"main": "locked"}

                def advance(self):
                    self._set_state("ghost", "active")

            @register(context)
            class StartEvent(CEvent):
                pass
            """,
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'quest "ghost"',
            'transition target "active" writes undeclared quest key "ghost" (missing from QUEST_KEYS)',
        )

    def test_given_state_read_for_undeclared_quest_key_when_validating_then_reports_missing_declaration(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            class QuestSystem(QuestStateStore):
                QUEST_KEYS = {"main": "quest_state_main"}
                QUEST_DEFAULTS = {"main": "locked"}

                def check(self):
                    return self.get_state("ghost") == "active"

            @register(context)
            class StartEvent(CEvent):
                pass
            """,
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'quest "ghost"',
            'state read "active" references undeclared quest key "ghost" (missing from QUEST_KEYS)',
        )

    def test_given_unreachable_terminal_state_when_validating_then_reports_unreachable_terminal(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            class QuestSystem(QuestStateStore):
                QUEST_KEYS = {"main": "quest_state_main"}
                QUEST_DEFAULTS = {"main": "locked"}

                def advance(self):
                    self._set_state("main", "active")

                def isCompleted(self):
                    return self.get_state("main") == "finished"

            @register(context)
            class StartEvent(CEvent):
                pass
            """,
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'quest "main"',
            'terminal state "finished" is unreachable: it is neither the default nor a transition target',
        )

    def test_given_reachable_quest_state_machine_when_validating_then_accepts_transitions(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            class QuestSystem(QuestStateStore):
                QUEST_KEYS = {"main": "quest_state_main"}
                QUEST_DEFAULTS = {"main": "locked"}

                def advance(self):
                    if self.get_state("main") == "locked":
                        self._set_state("main", "active")
                    if self.get_state("main") == "active":
                        self._set_state("main", "finished")

                def isCompleted(self):
                    return self.get_state("main") == "finished"

            @register(context)
            class StartEvent(CEvent):
                pass
            """,
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_given_default_terminal_state_when_validating_then_treats_default_as_reachable(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            class QuestSystem(QuestStateStore):
                QUEST_KEYS = {"main": "quest_state_main"}
                QUEST_DEFAULTS = {"main": "resolved"}

                def isCompleted(self):
                    return self.get_state("main") == "resolved"

            @register(context)
            class StartEvent(CEvent):
                pass
            """,
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_given_bad_quest_transition_when_running_standard_validation_path_then_reported_as_error(self):
        # Regression for E07/S01/SS04: the quest-state-transition validator must run in
        # the NORMAL validation path (validate_repo -> ContentValidator.validate ->
        # _validate_map_context), not only via a direct helper call. A synthetic map with
        # an unreachable terminal state must be caught by the default end-to-end run and
        # surfaced as a standard ValidationIssue error.
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            class QuestSystem(QuestStateStore):
                QUEST_KEYS = {"main": "quest_state_main"}
                QUEST_DEFAULTS = {"main": "locked"}

                def advance(self):
                    self._set_state("main", "active")

                def isCompleted(self):
                    return self.get_state("main") == "unreachable"

            @register(context)
            class StartEvent(CEvent):
                pass
            """,
        )

        unreachable_message = (
            'terminal state "unreachable" is unreachable: it is neither the default nor a transition target'
        )

        # The default end-to-end run (the exact entrypoint scripts/validate_content.py
        # invokes) must report the bad transition; it is not gated behind a runtime-only test.
        end_to_end_issues = validate_repo(root)
        self.assertIssueContains(end_to_end_issues, "res/maps/broken/script.py", 'quest "main"', unreachable_message)

        # ContentValidator.validate() (which main()/validate_repo() call) must produce the
        # same error, and the quest validator must stay wired into _validate_map_context so
        # a future refactor cannot silently drop it from the standard path.
        validate_issues = ContentValidator(root).validate()
        self.assertTrue(
            any(unreachable_message in str(issue) for issue in validate_issues),
            "quest-state-transition validator did not run inside ContentValidator.validate()",
        )
        self.assertTrue(
            hasattr(ContentValidator, "_validate_quest_state_transitions"),
            "quest-state-transition validator helper is missing",
        )

        # Pin the wiring: _validate_map_context must invoke the quest-state validator so it
        # always runs after map config, dialog JSON, map.json, and script.py are loaded.
        import inspect

        map_context_source = inspect.getsource(ContentValidator._validate_map_context)
        self.assertIn("_validate_quest_state_transitions", map_context_source)

    def test_given_script_granted_quest_id_missing_from_config_when_validating_then_reports_unknown_quest(self):
        root = self.make_fixture()
        write_property_hygiene_script(
            root / "res/maps/broken/script.py",
            """
            class QuestSystem(QuestStateStore):
                QUEST_KEYS = {"main": "quest_state_main"}
                QUEST_DEFAULTS = {"main": "locked"}

            @register(context)
            class StartEvent(CEvent):
                def onEnter(self, event):
                    event.getCause().addQuest("phantomQuest")
            """,
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'addQuest("phantomQuest")',
            'unknown quest id "phantomQuest"',
        )

    def test_creature_archetype_naming_policy_accepts_conforming_ids(self):
        root = self.make_fixture()
        # Register the archetype classes statically (without V_META) so the object
        # nodes are constructible: entries must carry "class"/"ref" to be registered
        # by the runtime config loader at all, like the real archetype content.
        type_registration = root / "src/object/CObjectTypeRegistration.cpp"
        type_registration.parent.mkdir(parents=True, exist_ok=True)
        type_registration.write_text(
            "void registerObjectTypes() {\n"
            "    CTypes::register_type<CCreatureRace, CGameObject>();\n"
            "    CTypes::register_type<CCreatureClass, CGameObject>();\n"
            "}\n",
            encoding="utf-8",
        )
        write_json(
            root / "res/config/creature_races.json",
            {"humanRace": {"class": "CCreatureRace", "properties": {"creatureClass": {"ref": "warriorClass"}}}},
        )
        write_json(
            root / "res/config/creature_classes.json",
            {"warriorClass": {"class": "CCreatureClass", "properties": {"label": "Warrior"}}},
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_creature_race_id_without_race_suffix_is_reported(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/creature_races.json",
            {"human": {"properties": {"label": "Human"}}},
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_races.json",
            "human",
            'creature_races.json template id "human" must end with "Race"',
        )

    def test_creature_class_id_without_class_suffix_is_reported(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/creature_classes.json",
            {"warrior": {"properties": {"label": "Warrior"}}},
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_classes.json",
            "warrior",
            'creature_classes.json template id "warrior" must end with "Class"',
        )

    def test_creature_class_reference_via_reserved_class_key_is_reported(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/creature_races.json",
            {"humanRace": {"properties": {"class": {"ref": "warriorClass"}}}},
        )
        write_json(
            root / "res/config/creature_classes.json",
            {"warriorClass": {"properties": {"label": "Warrior"}}},
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_races.json",
            "humanRace.properties.class",
            'class reference must use property "creatureClass"',
            'never the reserved object-constructor key "class"',
        )

    def _register_creature_class_type(self, root):
        # CCreatureClass is not a builtin; register it statically (without V_META) so
        # the synthetic configs are constructible and carry no metadata property
        # schema, leaving only the actions/levelling validator to fire.
        type_registration = root / "src/object/CObjectTypeRegistration.cpp"
        type_registration.parent.mkdir(parents=True, exist_ok=True)
        type_registration.write_text(
            "void registerObjectTypes() { CTypes::register_type<CCreatureClass, CGameObject>(); }\n",
            encoding="utf-8",
        )

    def _write_creature_class(self, root, properties):
        write_json(
            root / "res/config/creature_classes.json",
            {"warriorClass": {"class": "CCreatureClass", "properties": properties}},
        )

    def test_creature_class_actions_and_levelling_resolving_to_interaction_pass(self):
        root = self.make_fixture()
        self._register_creature_class_type(root)
        self._write_creature_class(
            root,
            {
                "actions": [
                    {"ref": "Attack"},
                    {"class": "CInteraction", "properties": {"effect": {"ref": "HitEffect"}}},
                ],
                "levelling": {"1": {"class": "CInteraction"}, "2": {"class": "CInteraction"}},
            },
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_creature_class_action_not_resolving_to_interaction_is_reported(self):
        root = self.make_fixture()
        self._register_creature_class_type(root)
        self._write_creature_class(root, {"actions": [{"ref": "LifePotion"}]})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_classes.json",
            "warriorClass.properties.actions[0]",
            'expected object resolving to "CInteraction"; got "CPotion"',
        )

    def test_creature_class_levelling_value_not_resolving_to_interaction_is_reported(self):
        root = self.make_fixture()
        self._register_creature_class_type(root)
        self._write_creature_class(root, {"levelling": {"1": {"ref": "LifePotion"}}})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_classes.json",
            'warriorClass.properties.levelling["1"]',
            'expected object resolving to "CInteraction"; got "CPotion"',
        )

    def test_creature_class_non_integer_levelling_key_is_reported(self):
        root = self.make_fixture()
        self._register_creature_class_type(root)
        self._write_creature_class(root, {"levelling": {"one": {"ref": "Attack"}}})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_classes.json",
            "warriorClass.properties.levelling.one",
            'levelling key "one" must be a positive-integer string',
        )

    def test_creature_class_non_positive_levelling_key_is_reported(self):
        root = self.make_fixture()
        self._register_creature_class_type(root)
        self._write_creature_class(root, {"levelling": {"0": {"ref": "Attack"}}})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_classes.json",
            'warriorClass.properties.levelling["0"]',
            'levelling key "0" must be a positive-integer string',
        )

    def test_creature_class_duplicate_action_id_is_reported(self):
        root = self.make_fixture()
        self._register_creature_class_type(root)
        self._write_creature_class(
            root,
            {"actions": [{"ref": "Attack"}], "levelling": {"1": {"ref": "Attack"}}},
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_classes.json",
            'warriorClass.properties.levelling["1"]',
            'duplicate action id "Attack", previously granted at warriorClass.properties.actions[0]',
        )

    def _write_creature_with_creature_class(self, root, creature_class_value):
        # A concrete CCreature carrying its class template through the "creatureClass"
        # *property* (never the top-level constructor key "class").  CCreatureClass is
        # registered statically so the definition is constructible.
        self._register_creature_class_type(root)
        write_json(
            root / "res/config/creature_classes.json",
            {"warriorClass": {"class": "CCreatureClass", "properties": {"label": "Warrior"}}},
        )
        write_json(
            root / "res/config/monsters.json",
            {
                "Goblin": {
                    "class": "CCreature",
                    "properties": {"creatureClass": creature_class_value, "label": "Goblin"},
                }
            },
        )

    def test_creature_class_property_resolving_to_creature_class_passes(self):
        root = self.make_fixture()
        self._write_creature_with_creature_class(root, {"ref": "warriorClass"})

        issues = validate_repo(root)

        creature_class_issues = [
            str(issue) for issue in issues if "creatureClass" in str(issue) and "Goblin" in str(issue)
        ]
        self.assertEqual([], creature_class_issues)

    def test_creature_class_property_inline_creature_class_passes(self):
        root = self.make_fixture()
        self._register_creature_class_type(root)
        write_json(
            root / "res/config/monsters.json",
            {
                "Goblin": {
                    "class": "CCreature",
                    "properties": {
                        "creatureClass": {"class": "CCreatureClass", "properties": {"label": "Warrior"}},
                        "label": "Goblin",
                    },
                }
            },
        )

        issues = validate_repo(root)

        creature_class_issues = [
            str(issue) for issue in issues if "creatureClass" in str(issue) and "Goblin" in str(issue)
        ]
        self.assertEqual([], creature_class_issues)

    def test_creature_class_property_missing_reference_is_reported(self):
        root = self.make_fixture()
        self._register_creature_class_type(root)
        write_json(
            root / "res/config/monsters.json",
            {
                "Goblin": {
                    "class": "CCreature",
                    "properties": {"creatureClass": {"ref": "ghostClass"}, "label": "Goblin"},
                }
            },
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/monsters.json",
            "Goblin.properties.creatureClass",
            'property "creatureClass" expected an object resolving to "CCreatureClass"; '
            "reference does not resolve to a known config",
        )

    def test_creature_class_property_wrong_target_class_is_reported(self):
        root = self.make_fixture()
        self._write_creature_with_creature_class(root, {"ref": "LifePotion"})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/monsters.json",
            "Goblin.properties.creatureClass",
            'property "creatureClass" expected an object resolving to "CCreatureClass"; got "CPotion"',
        )

    def test_creature_class_property_wrong_typed_value_is_reported(self):
        root = self.make_fixture()
        self._write_creature_with_creature_class(root, "warriorClass")

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/monsters.json",
            "Goblin.properties.creatureClass",
            'property "creatureClass" expected an object resolving to "CCreatureClass"; got string',
        )

    def test_creature_top_level_class_key_is_not_mistaken_for_creature_class_property(self):
        root = self.make_fixture()
        self._register_creature_class_type(root)
        # The creature's top-level "class": "CCreature" constructor key must never be
        # treated as the "creatureClass" reference property: a creature that omits the
        # property is vacuously satisfied and emits no creatureClass diagnostic.
        write_json(
            root / "res/config/monsters.json",
            {"Goblin": {"class": "CCreature", "properties": {"label": "Goblin"}}},
        )

        issues = validate_repo(root)

        creature_class_issues = [str(issue) for issue in issues if "creatureClass" in str(issue)]
        self.assertEqual([], creature_class_issues)

    def test_archetype_id_as_map_object_type_is_rejected(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/creature_classes.json",
            {"warriorClass": {"class": "CCreatureClass", "properties": {"label": "Warrior"}}},
        )
        map_path = root / "res/maps/broken/map.json"
        map_data = read_json(map_path)
        map_data["layers"][1]["objects"][0]["type"] = "warriorClass"
        write_json(map_path, map_data)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/map.json",
            "layers[1].objects[0].type",
            'object type "warriorClass" is a creature archetype definition',
            "cannot be used as a concrete spawn target",
        )

    def test_archetype_id_as_tile_type_is_rejected(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/creature_races.json",
            {"humanRace": {"class": "CCreatureRace", "properties": {"label": "Human"}}},
        )
        map_path = root / "res/maps/broken/map.json"
        map_data = read_json(map_path)
        map_data["tilesets"][0]["tileproperties"] = {"0": {"type": "humanRace"}}
        map_data["layers"][0]["data"] = [1, 0, 0, 0]
        write_json(map_path, map_data)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/map.json",
            "layers[0].data[0]",
            'tile type "humanRace" is a creature archetype definition',
            "cannot be used as a concrete spawn target",
        )

    def test_archetype_id_as_add_object_by_name_target_is_rejected(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/creature_classes.json",
            {"warriorClass": {"class": "CCreatureClass", "properties": {"label": "Warrior"}}},
        )
        script_path = root / "res/maps/broken/script.py"
        script_path.write_text(
            script_path.read_text(encoding="utf-8").replace(
                'self.getGame().createObject("validMarket")',
                'self.getMap().addObjectByName("warriorClass", None)',
            ),
            encoding="utf-8",
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'addObjectByName("warriorClass")',
            'object ref or class "warriorClass" is a creature archetype definition',
            "cannot be used as a concrete spawn target",
        )

    def test_archetype_id_as_create_object_target_is_rejected(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/creature_classes.json",
            {"warriorClass": {"class": "CCreatureClass", "properties": {"label": "Warrior"}}},
        )
        script_path = root / "res/maps/broken/script.py"
        script_path.write_text(
            script_path.read_text(encoding="utf-8").replace(
                'self.getGame().createObject("validMarket")',
                'self.getGame().createObject("warriorClass")',
            ),
            encoding="utf-8",
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'createObject("warriorClass")',
            'object ref or class "warriorClass" is a creature archetype definition',
            "cannot be used as a concrete spawn target",
        )

    def test_creature_template_id_as_spawn_target_is_rejected(self):
        # CCreatureTemplate overlays (EPIC_08) are referenced definitions carried via
        # CCreature.templates; runtime createObject<CMapObject> on one returns null and
        # silently skips the spawn, so the validator must reject them as spawn targets
        # exactly like race/class definitions.
        root = self.make_fixture()
        write_json(
            root / "res/config/creature_templates.json",
            {"eliteTemplate": {"class": "CCreatureTemplate", "properties": {"label": "Elite"}}},
        )
        map_path = root / "res/maps/broken/map.json"
        map_data = read_json(map_path)
        map_data["layers"][1]["objects"][0]["type"] = "eliteTemplate"
        write_json(map_path, map_data)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/map.json",
            "layers[1].objects[0].type",
            'object type "eliteTemplate" is a creature archetype definition',
            "cannot be used as a concrete spawn target",
        )

    def test_class_track_id_as_create_object_target_is_rejected(self):
        # CCreatureClassTrack multiclass records (EPIC_08) are referenced definitions
        # carried via CCreature.classTracks; they are constructible metadata, never
        # spawnable actors, so a script spawn ref naming one must be rejected. Track
        # records have no dedicated config file, so the guard must catch them purely by
        # effective engine class.
        root = self.make_fixture()
        write_json(
            root / "res/config/monsters.json",
            {
                "warriorTrack": {
                    "class": "CCreatureClassTrack",
                    "properties": {"label": "Warrior track", "level": 2},
                }
            },
        )
        script_path = root / "res/maps/broken/script.py"
        script_path.write_text(
            script_path.read_text(encoding="utf-8").replace(
                'self.getGame().createObject("validMarket")',
                'self.getGame().createObject("warriorTrack")',
            ),
            encoding="utf-8",
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'createObject("warriorTrack")',
            'object ref or class "warriorTrack" is a creature archetype definition',
            "cannot be used as a concrete spawn target",
        )

    def test_concrete_creature_spawn_alongside_archetype_definitions_passes(self):
        root = self.make_fixture()
        write_json(
            root / "res/config/creature_races.json",
            {"humanRace": {"class": "CCreatureRace", "properties": {"label": "Human"}}},
        )
        write_json(
            root / "res/config/creature_classes.json",
            {"warriorClass": {"class": "CCreatureClass", "properties": {"label": "Warrior"}}},
        )
        write_json(
            root / "res/config/monsters.json",
            {
                "Goblin": {
                    "class": "CCreature",
                    "properties": {"creatureClass": {"ref": "warriorClass"}, "label": "Goblin"},
                }
            },
        )
        script_path = root / "res/maps/broken/script.py"
        script_path.write_text(
            script_path.read_text(encoding="utf-8").replace(
                'self.getGame().createObject("validMarket")',
                'self.getGame().createObject("Goblin")',
            ),
            encoding="utf-8",
        )

        issues = validate_repo(root)

        archetype_issues = [str(issue) for issue in issues if "creature archetype definition" in str(issue)]
        self.assertEqual([], archetype_issues)

    def _register_creature_race_type(self, root):
        # CCreatureRace is not a builtin; register it statically (without V_META) so the
        # synthetic race configs are constructible and carry no metadata property schema,
        # leaving only the label-uniqueness validator to fire.
        type_registration = root / "src/object/CObjectTypeRegistration.cpp"
        type_registration.parent.mkdir(parents=True, exist_ok=True)
        type_registration.write_text(
            "void registerObjectTypes() { CTypes::register_type<CCreatureRace, CGameObject>(); }\n",
            encoding="utf-8",
        )

    def test_distinct_player_selectable_race_labels_pass(self):
        root = self.make_fixture()
        self._register_creature_race_type(root)
        write_json(
            root / "res/config/creature_races.json",
            {
                "humanRace": {
                    "class": "CCreatureRace",
                    "properties": {"playerSelectable": True, "label": "Human"},
                },
                "elfRace": {
                    "class": "CCreatureRace",
                    "properties": {"playerSelectable": True, "label": "Elf"},
                },
            },
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_duplicate_player_selectable_race_labels_are_reported(self):
        root = self.make_fixture()
        self._register_creature_race_type(root)
        write_json(
            root / "res/config/creature_races.json",
            {
                "humanRace": {
                    "class": "CCreatureRace",
                    "properties": {"playerSelectable": True, "label": "Human"},
                },
                "northernerRace": {
                    "class": "CCreatureRace",
                    "properties": {"playerSelectable": True, "label": "Human"},
                },
            },
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_races.json",
            "humanRace",
            'player-selectable race selection label "Human" is not unique',
            "it collides with northernerRace",
        )
        self.assertIssueContains(
            issues,
            "northernerRace",
            "it collides with humanRace",
        )

    def test_player_selectable_race_without_label_collides_by_id(self):
        root = self.make_fixture()
        self._register_creature_race_type(root)
        # One race carries an explicit label equal to the other's id; the label-less race
        # falls back to its id "humanRace", so the two collide on the "humanRace" key.
        write_json(
            root / "res/config/creature_races.json",
            {
                "humanRace": {
                    "class": "CCreatureRace",
                    "properties": {"playerSelectable": True},
                },
                "elfRace": {
                    "class": "CCreatureRace",
                    "properties": {"playerSelectable": True, "label": "humanRace"},
                },
            },
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_races.json",
            "humanRace",
            'player-selectable race selection label "humanRace" is not unique',
            "it collides with elfRace",
        )

    def test_non_player_selectable_duplicate_race_labels_are_ignored(self):
        root = self.make_fixture()
        self._register_creature_race_type(root)
        write_json(
            root / "res/config/creature_races.json",
            {
                "humanRace": {
                    "class": "CCreatureRace",
                    "properties": {"playerSelectable": True, "label": "Human"},
                },
                "spectralHumanRace": {
                    "class": "CCreatureRace",
                    "properties": {"playerSelectable": False, "label": "Human"},
                },
                "undeclaredHumanRace": {
                    "class": "CCreatureRace",
                    "properties": {"label": "Human"},
                },
            },
        )

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

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

    def test_metadata_declared_unregistered_class_reports_distinctly(self):
        root = self.make_fixture()
        declared_header = root / "src/object/CDeclaredOnly.h"
        declared_header.parent.mkdir(parents=True)
        declared_header.write_text(
            textwrap.dedent("""
                class CDeclaredOnly {
                    V_META(CDeclaredOnly, CGameObject, vstd::meta::empty())
                };
            """).lstrip(),
            encoding="utf-8",
        )
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["declaredOnly"] = {"class": "CDeclaredOnly"}
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "declaredOnly.class",
            'class "CDeclaredOnly" is declared in metadata but is not registered as constructible content',
        )

    def test_cpp_property_schema_accepts_known_and_inherited_properties(self):
        root = self.make_fixture()
        self.write_property_schema_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["schemaKnown"] = {
            "class": "CPropertyDerived",
            "properties": {
                "count": 2,
                "loot": [{"ref": "LifePotion"}],
                "name": "Known Schema Object",
            },
        }
        write_json(config_path, config)

        validator = ContentValidator(root)
        validator._collect_engine_classes()
        property_schema = validator._metadata_property_schema("CPropertyDerived")

        self.assertIsNotNone(property_schema)
        if property_schema is not None:
            self.assertEqual("int", property_schema["count"].type_token)
            self.assertEqual("CPropertyDerived", property_schema["count"].owner_class)
            self.assertEqual("std::set<std::shared_ptr<CItem>>", property_schema["loot"].type_token)
            self.assertEqual("CPropertyBase", property_schema["loot"].owner_class)
            self.assertEqual("std::string", property_schema["name"].type_token)
            self.assertEqual("CGameObject", property_schema["name"].owner_class)

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_cpp_property_schema_reports_unknown_property(self):
        root = self.make_fixture()
        self.write_property_schema_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["schemaUnknown"] = {
            "class": "CPropertyDerived",
            "properties": {"count": 2, "bogus": True},
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "schemaUnknown.properties.bogus",
            'unknown property "bogus" for class "CPropertyDerived"',
        )

    def test_creature_class_main_stat_numeric_stat_passes(self):
        root = self.make_fixture()
        self.write_creature_class_main_stat_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["WarriorClass"] = {
            "class": "CCreatureClass",
            "properties": {"mainStat": "strength"},
        }
        write_json(config_path, config)

        validator = ContentValidator(root)
        validator._collect_engine_classes()

        self.assertEqual({"strength", "agility", "intelligence"}, validator._numeric_main_stat_names())
        self.assertEqual([], [str(issue) for issue in validate_repo(root)])

    def test_creature_class_main_stat_typo_reports_class_path(self):
        root = self.make_fixture()
        self.write_creature_class_main_stat_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["WarriorClass"] = {
            "class": "CCreatureClass",
            "properties": {"mainStat": "strenght"},
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "WarriorClass.properties.mainStat",
            'property "mainStat" for class "CCreatureClass" value "strenght" is not a numeric CStats property',
            "expected one of agility, intelligence, strength",
        )

    def test_creature_class_main_stat_non_numeric_stat_reports_class_path(self):
        root = self.make_fixture()
        self.write_creature_class_main_stat_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        # "mainStat" itself is a std::string CStats property -- present but non-numeric.
        config["MageClass"] = {
            "class": "CCreatureClass",
            "properties": {"mainStat": "mainStat"},
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "MageClass.properties.mainStat",
            'property "mainStat" for class "CCreatureClass" value "mainStat" is not a numeric CStats property',
        )

    def test_creature_class_main_stat_empty_reports_class_path(self):
        root = self.make_fixture()
        self.write_creature_class_main_stat_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["EmptyClass"] = {
            "class": "CCreatureClass",
            "properties": {"mainStat": ""},
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "EmptyClass.properties.mainStat",
            'property "mainStat" for class "CCreatureClass" expected a non-empty numeric CStats property name; '
            "got string",
        )

    def test_cpp_property_schema_reports_scalar_type_mismatches(self):
        root = self.make_fixture()
        self.write_property_schema_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["schemaWrongScalars"] = {
            "class": "CPropertyDerived",
            "properties": {
                "active": 1,
                "count": "2",
                "name": False,
            },
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "schemaWrongScalars.properties.active",
            'property "active" for class "CPropertyDerived" expected bool; got int',
        )
        self.assertIssueContains(
            issues,
            "schemaWrongScalars.properties.count",
            'property "count" for class "CPropertyDerived" expected int; got string',
        )
        self.assertIssueContains(
            issues,
            "schemaWrongScalars.properties.name",
            'property "name" for class "CPropertyDerived" expected string; got bool',
        )

    def test_cpp_property_schema_reports_scalar_container_shape_mismatches(self):
        root = self.make_fixture()
        self.write_property_schema_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["schemaWrongShapes"] = {
            "class": "CPropertyDerived",
            "properties": {
                "count": [2],
                "name": {"ref": "LifePotion"},
            },
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "schemaWrongShapes.properties.count",
            'property "count" for class "CPropertyDerived" expected int; got array',
        )
        self.assertIssueContains(
            issues,
            "schemaWrongShapes.properties.name",
            'property "name" for class "CPropertyDerived" expected string; got object',
        )

    def test_cpp_property_schema_reports_array_and_object_shape_mismatches(self):
        root = self.make_fixture()
        self.write_property_schema_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["schemaWrongContainers"] = {
            "class": "CPropertyDerived",
            "properties": {
                "loot": {"ref": "LifePotion"},
                "target": "LifePotion",
            },
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "schemaWrongContainers.properties.loot",
            'property "loot" for class "CPropertyDerived" expected array; got object',
        )
        self.assertIssueContains(
            issues,
            "schemaWrongContainers.properties.target",
            'property "target" for class "CPropertyDerived" expected object; got string',
        )

    def test_cpp_property_schema_accepts_reviewed_dynamic_property_namespace(self):
        root = self.make_fixture()
        self.write_property_schema_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["schemaDynamic"] = {
            "class": "CPropertyDerived",
            "properties": {
                "campaign_gate_open": True,
                "plugin_checkpoint": {"state": "armed"},
                "quest_state_main": "done",
            },
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_cpp_property_schema_resolves_ref_override_class(self):
        root = self.make_fixture()
        self.write_property_schema_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["schemaBase"] = {
            "class": "CPropertyDerived",
            "properties": {"count": 2},
        }
        config["schemaOverride"] = {
            "ref": "schemaBase",
            "properties": {
                "loot": [{"ref": "LifePotion"}],
                "bogusOverride": False,
            },
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "schemaOverride.properties.bogusOverride",
            'unknown property "bogusOverride" for class "CPropertyDerived"',
        )
        issue_text = "\n".join(str(issue) for issue in issues)
        self.assertNotIn("schemaOverride.properties.loot", issue_text)

    def test_cpp_property_schema_reports_wrong_controller_ref_type(self):
        root = self.make_fixture()
        self.write_property_schema_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["badController"] = {
            "class": "CCreature",
            "properties": {"controller": {"ref": "LifePotion"}},
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "badController.properties.controller",
            'property "controller" for class "CCreature" expected object inheriting from "CController"; got "CPotion"',
        )

    def test_cpp_property_schema_reports_wrong_item_ref_type(self):
        root = self.make_fixture()
        self.write_property_schema_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["validMarket"]["properties"]["items"][0]["ref"] = "HitEffect"
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "validMarket.properties.items[0]",
            'property "items" for class "CMarket" expected object inheriting from "CItem"; got "CEffect"',
        )

    def test_cpp_property_schema_reports_wrong_dialog_state_ref_type(self):
        root = self.make_fixture()
        self.write_property_schema_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["badDialog"] = {
            "class": "CDialog",
            "properties": {"states": [{"ref": "exitOption"}]},
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "badDialog.properties.states[0]",
            (
                'property "states" for class "CDialog" expected object inheriting from "CDialogState"; '
                'got "CDialogOption"'
            ),
        )

    def test_cpp_property_schema_accepts_valid_inherited_object_types(self):
        root = self.make_fixture()
        self.write_property_schema_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["validCreature"] = {
            "class": "CCreature",
            "properties": {
                "controller": {"class": "CPlayerController"},
                "fightController": {"class": "CMonsterFightController"},
                "items": [{"ref": "LifePotion"}],
                "actions": [{"ref": "Attack"}],
                "effects": [{"ref": "HitEffect"}],
            },
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_reviewed_registration_exclusion_reports_reason_and_owner(self):
        root = self.make_fixture()
        self.write_declared_cpp_class(root, "CReviewedMetadataOnly")
        self.write_registration_exclusions(
            root,
            [
                {
                    "className": "CReviewedMetadataOnly",
                    "reason": "Fixture-only metadata carrier.",
                    "ownerModule": "tests/content-validator",
                }
            ],
        )
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["reviewedMetadataOnly"] = {"class": "CReviewedMetadataOnly"}
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "reviewedMetadataOnly.class",
            'class "CReviewedMetadataOnly" is excluded from content instantiation',
            "Fixture-only metadata carrier.",
            "owner/module: tests/content-validator",
        )

    def test_reviewed_registration_exclusion_can_allow_exact_config_use(self):
        root = self.make_fixture()
        self.write_declared_cpp_class(root, "CReviewedAllowed")
        self.write_registration_exclusions(
            root,
            [
                {
                    "className": "CReviewedAllowed",
                    "reason": "Fixture-only metadata carrier.",
                    "ownerModule": "tests/content-validator",
                    "allowedUses": [
                        {
                            "path": "res/maps/broken/config.json",
                            "location": "reviewedAllowed.class",
                            "reason": "Regression fixture for exact reviewed allowance.",
                        }
                    ],
                }
            ],
        )
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["reviewedAllowed"] = {"class": "CReviewedAllowed"}
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_reviewed_registration_exclusion_rejects_unknown_allowlisted_class(self):
        root = self.make_fixture()
        self.write_registration_exclusions(
            root,
            [
                {
                    "className": "CReviewedTypo",
                    "reason": "Fixture typo should not be trusted.",
                    "ownerModule": "tests/content-validator",
                    "allowedUses": [
                        {
                            "path": "res/maps/broken/config.json",
                            "location": "reviewedTypo.class",
                            "reason": "This exact allowance must not hide an unknown class.",
                        }
                    ],
                }
            ],
        )
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["reviewedTypo"] = {"class": "CReviewedTypo"}
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "scripts/type_registration_exclusions.json",
            "exclusions[0].className",
            'excluded class "CReviewedTypo" is not metadata-declared or registered',
        )
        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "reviewedTypo.class",
            'unknown class "CReviewedTypo"',
        )

    def test_static_type_registration_makes_class_constructible(self):
        root = self.make_fixture()
        self.write_declared_cpp_class(root, "CStaticRegistered")
        type_registration = root / "src/object/CObjectTypeRegistration.cpp"
        type_registration.parent.mkdir(parents=True, exist_ok=True)
        type_registration.write_text(
            "void registerObjectTypes() { CTypes::register_type<CStaticRegistered, CGameObject>(); }\n",
            encoding="utf-8",
        )
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["staticRegistered"] = {"class": "CStaticRegistered"}
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_manifest_native_plugin_registration_makes_class_constructible(self):
        root = self.make_fixture()
        self.write_native_registration_fixture(root, "CManifestNative")
        write_json(
            root / "res/plugins/manifest.json",
            {
                "global": [
                    {
                        "kind": "dynamic",
                        "id": "nativeOptional",
                        "library": "plugins/native/native_optional",
                        "entry": "native_optional_load_v1",
                    }
                ],
                "maps": {},
            },
        )
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["manifestNative"] = {"class": "CManifestNative"}
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_unloaded_native_plugin_registration_reports_manifest_diagnostic(self):
        root = self.make_fixture()
        self.write_native_registration_fixture(root, "CUnloadedNative")
        write_json(root / "res/plugins/manifest.json", {"global": [], "maps": {}})
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["unloadedNative"] = {"class": "CUnloadedNative"}
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "unloadedNative.class",
            'class "CUnloadedNative" is registered by native plugin code',
            "native_optional:native_optional_load_v1",
        )

    def write_declared_cpp_class(self, root, class_name):
        declared_header = root / "src/object/CDeclaredOnly.h"
        declared_header.parent.mkdir(parents=True, exist_ok=True)
        declared_header.write_text(
            textwrap.dedent(f"""
                class {class_name} {{
                    V_META({class_name}, CGameObject, vstd::meta::empty())
                }};
            """).lstrip(),
            encoding="utf-8",
        )

    def write_native_registration_fixture(self, root, class_name):
        self.write_declared_cpp_class(root, class_name)
        native_plugin = root / "src/plugin/NativePlugin.cpp"
        native_plugin.parent.mkdir(parents=True, exist_ok=True)
        native_plugin.write_text(
            textwrap.dedent(f"""
                namespace native_plugin {{
                bool register_optional(const NativePluginHostV1 *host) {{
                    bool registered = true;
                    registered = register_type<{class_name}, CGameObject>(host) && registered;
                    return registered;
                }}
                }}
            """).lstrip(),
            encoding="utf-8",
        )
        native_entry = root / "native_plugins/native_optional.cpp"
        native_entry.parent.mkdir(parents=True, exist_ok=True)
        native_entry.write_text(
            textwrap.dedent("""
                extern "C" NATIVE_PLUGIN_EXPORT bool native_optional_load_v1(const NativePluginHostV1 *host) {
                    return native_plugin::register_optional(host);
                }
            """).lstrip(),
            encoding="utf-8",
        )

    def write_property_schema_fixture(self, root):
        header = root / "src/object/CPropertySchemaFixture.h"
        header.parent.mkdir(parents=True, exist_ok=True)
        header.write_text(
            textwrap.dedent("""
                class CGameObject {
                    V_META(CGameObject, vstd::meta::empty,
                        V_PROPERTY(CGameObject, std::string, name, getName, setName))
                };

                class CController {
                    V_META(CController, CGameObject, vstd::meta::empty())
                };

                class CPlayerController {
                    V_META(CPlayerController, CController, vstd::meta::empty())
                };

                class CFightController {
                    V_META(CFightController, CGameObject, vstd::meta::empty())
                };

                class CMonsterFightController {
                    V_META(CMonsterFightController, CFightController, vstd::meta::empty())
                };

                class CEffect {
                    V_META(CEffect, CGameObject, vstd::meta::empty())
                };

                class CInteraction {
                    V_META(CInteraction, CGameObject,
                        V_PROPERTY(CInteraction, std::shared_ptr<CEffect>, effect, getEffect, setEffect))
                };

                class CItem {
                    V_META(CItem, CGameObject,
                        V_PROPERTY(CItem, std::shared_ptr<CInteraction>, interaction, getInteraction, setInteraction))
                };

                class CPotion {
                    V_META(CPotion, CItem, vstd::meta::empty())
                };

                class CCreature {
                    V_META(CCreature, CGameObject,
                        V_PROPERTY(CCreature, std::set<std::shared_ptr<CInteraction>>, actions, getActions,
                            setActions),
                        V_PROPERTY(CCreature, std::set<std::shared_ptr<CItem>>, items, getItems, setItems),
                        V_PROPERTY(CCreature, std::set<std::shared_ptr<CEffect>>, effects, getEffects, setEffects),
                        V_PROPERTY(CCreature, std::shared_ptr<CController>, controller, getController, setController),
                        V_PROPERTY(CCreature, std::shared_ptr<CFightController>, fightController, getFightController,
                            setFightController))
                };

                class CMarket {
                    V_META(CMarket, CGameObject,
                        V_PROPERTY(CMarket, std::set<std::shared_ptr<CItem>>, items, getItems, setItems))
                };

                class CDialogOption {
                    V_META(CDialogOption, CGameObject,
                        V_PROPERTY(CDialogOption, int, number, getNumber, setNumber),
                        V_PROPERTY(CDialogOption, std::string, nextStateId, getNextStateId, setNextStateId),
                        V_PROPERTY(CDialogOption, std::string, text, getText, setText),
                        V_PROPERTY(CDialogOption, std::string, condition, getCondition, setCondition),
                        V_PROPERTY(CDialogOption, std::string, action, getAction, setAction))
                };

                class CDialogState {
                    V_META(CDialogState, CGameObject,
                        V_PROPERTY(CDialogState, std::set<std::shared_ptr<CDialogOption>>, options, getOptions,
                            setOptions),
                        V_PROPERTY(CDialogState, std::string, stateId, getStateId, setStateId),
                        V_PROPERTY(CDialogState, std::string, text, getText, setText))
                };

                class CDialog {
                    V_META(CDialog, CGameObject,
                        V_PROPERTY(CDialog, std::set<std::shared_ptr<CDialogState>>, states, getStates, setStates))
                };

                class CPropertyBase {
                    V_META(CPropertyBase, CGameObject,
                        V_PROPERTY(CPropertyBase, std::set<std::shared_ptr<CItem>>, loot, getLoot, setLoot))
                };

                class CPropertyDerived {
                    V_META(CPropertyDerived, CPropertyBase,
                        V_PROPERTY(CPropertyDerived, int, count, getCount, setCount),
                        V_PROPERTY(CPropertyDerived, bool, active, getActive, setActive),
                        V_PROPERTY(CPropertyDerived, std::shared_ptr<CGameObject>, target, getTarget, setTarget))
                };
            """).lstrip(),
            encoding="utf-8",
        )
        type_registration = root / "src/object/CObjectTypeRegistration.cpp"
        type_registration.write_text(
            textwrap.dedent("""
                void registerObjectTypes() {
                    CTypes::register_type<CPropertyBase, CGameObject>();
                    CTypes::register_type<CPropertyDerived, CPropertyBase, CGameObject>();
                }
            """).lstrip(),
            encoding="utf-8",
        )

    def write_registration_exclusions(self, root, exclusions):
        manifest = root / "scripts/type_registration_exclusions.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        write_json(manifest, {"exclusions": exclusions})

    def write_creature_class_main_stat_fixture(self, root):
        """Declare synthetic CStats + CCreatureClass metadata for mainStat checks.

        CCreatureClass does not exist on real content, so the validator is vacuously
        satisfied there; these synthetic headers let the test exercise the forward
        guard.  CStats mirrors src/core/CStats.h closely enough to drive the numeric
        property derivation: a couple of int stats plus the std::string mainStat.
        """
        header = root / "src/object/CCreatureClassFixture.h"
        header.parent.mkdir(parents=True, exist_ok=True)
        header.write_text(
            textwrap.dedent("""
                class CGameObject {
                    V_META(CGameObject, vstd::meta::empty,
                        V_PROPERTY(CGameObject, std::string, name, getName, setName))
                };

                class CStats {
                    V_META(CStats, CGameObject,
                        V_PROPERTY(CStats, int, strength, getStrength, setStrength),
                        V_PROPERTY(CStats, int, agility, getAgility, setAgility),
                        V_PROPERTY(CStats, int, intelligence, getIntelligence, setIntelligence),
                        V_PROPERTY(CStats, std::string, mainStat, getMainStat, setMainStat))
                };

                class CCreatureClass {
                    V_META(CCreatureClass, CGameObject,
                        V_PROPERTY(CCreatureClass, std::string, mainStat, getMainStat, setMainStat))
                };
            """).lstrip(),
            encoding="utf-8",
        )
        type_registration = root / "src/object/CCreatureClassTypeRegistration.cpp"
        type_registration.write_text(
            textwrap.dedent("""
                void registerCreatureClassTypes() {
                    CTypes::register_type<CStats, CGameObject>();
                    CTypes::register_type<CCreatureClass, CGameObject>();
                }
            """).lstrip(),
            encoding="utf-8",
        )

    def write_creature_race_fixture(self, root):
        """Declare synthetic CCreature + CCreatureRace metadata for race checks.

        CCreature configs do not declare a "race" property on real content, so the
        validator is vacuously satisfied there; these synthetic headers let the test
        exercise the forward guard.  CCreatureRace and a sibling non-race class are
        registered statically (without V_META registration) so they are constructible
        and the inheritance check can confirm the resolved race class lineage.
        """
        header = root / "src/object/CCreatureRaceFixture.h"
        header.parent.mkdir(parents=True, exist_ok=True)
        header.write_text(
            textwrap.dedent("""
                class CGameObject {
                    V_META(CGameObject, vstd::meta::empty,
                        V_PROPERTY(CGameObject, std::string, name, getName, setName))
                };

                class CCreature {
                    V_META(CCreature, CGameObject,
                        V_PROPERTY(CCreature, std::string, name, getName, setName))
                };

                class CCreatureRace {
                    V_META(CCreatureRace, CGameObject,
                        V_PROPERTY(CCreatureRace, std::string, label, getLabel, setLabel))
                };

                class CCreatureClass {
                    V_META(CCreatureClass, CGameObject,
                        V_PROPERTY(CCreatureClass, std::string, label, getLabel, setLabel))
                };
            """).lstrip(),
            encoding="utf-8",
        )
        type_registration = root / "src/object/CCreatureRaceTypeRegistration.cpp"
        type_registration.write_text(
            textwrap.dedent("""
                void registerCreatureRaceTypes() {
                    CTypes::register_type<CCreatureRace, CGameObject>();
                    CTypes::register_type<CCreatureClass, CGameObject>();
                }
            """).lstrip(),
            encoding="utf-8",
        )

    def write_creature_race_stats_fixture(self, root):
        """Declare synthetic CStats metadata + register CCreatureRace for stat/action/type checks.

        CCreatureRace does not exist on real content, so the validator is vacuously
        satisfied there; this fixture exercises the forward guard for the
        baseStats/actions/creatureType/subtypes validator.  CStats carries V_META
        mirroring src/core/CStats.h closely enough to drive the baseStats key
        derivation.  CCreatureRace is registered statically WITHOUT V_META so the
        synthetic configs are constructible and recognised as race definitions while
        carrying no metadata property schema -- leaving only the race-field validator
        (not the generic property-schema validator) to fire on its baseStats/actions/
        creatureType/subtypes fields.  Kept separate from write_creature_race_fixture
        (which backs the race-resolution tests) so the two helpers do not shadow.
        """
        header = root / "src/object/CCreatureRaceStatsFixture.h"
        header.parent.mkdir(parents=True, exist_ok=True)
        header.write_text(
            textwrap.dedent("""
                class CGameObject {
                    V_META(CGameObject, vstd::meta::empty,
                        V_PROPERTY(CGameObject, std::string, name, getName, setName))
                };

                class CStats {
                    V_META(CStats, CGameObject,
                        V_PROPERTY(CStats, int, strength, getStrength, setStrength),
                        V_PROPERTY(CStats, int, agility, getAgility, setAgility),
                        V_PROPERTY(CStats, int, intelligence, getIntelligence, setIntelligence),
                        V_PROPERTY(CStats, std::string, mainStat, getMainStat, setMainStat))
                };
            """).lstrip(),
            encoding="utf-8",
        )
        type_registration = root / "src/object/CCreatureRaceStatsTypeRegistration.cpp"
        type_registration.write_text(
            textwrap.dedent("""
                void registerCreatureRaceStatsTypes() {
                    CTypes::register_type<CStats, CGameObject>();
                    CTypes::register_type<CCreatureRace, CGameObject>();
                }
            """).lstrip(),
            encoding="utf-8",
        )

    def test_creature_race_ref_to_creature_race_passes(self):
        root = self.make_fixture()
        self.write_creature_race_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["humanRace"] = {"class": "CCreatureRace", "properties": {"label": "Human"}}
        config["Townsfolk"] = {
            "class": "CCreature",
            "properties": {"race": {"ref": "humanRace"}},
        }
        write_json(config_path, config)

        self.assertEqual([], [str(issue) for issue in validate_repo(root)])

    def test_creature_race_unknown_ref_reports_ref_path(self):
        root = self.make_fixture()
        self.write_creature_race_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["Townsfolk"] = {
            "class": "CCreature",
            "properties": {"race": {"ref": "missingRace"}},
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "Townsfolk.properties.race.ref",
            'property "race" for class "CCreature" references unknown id "missingRace"; '
            'expected a "CCreatureRace" definition',
        )

    def test_creature_race_ref_to_non_race_reports_ref_path(self):
        root = self.make_fixture()
        self.write_creature_race_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        # CCreatureClass is constructible but is not a CCreatureRace lineage.
        config["warriorClass"] = {"class": "CCreatureClass", "properties": {"label": "Warrior"}}
        config["Townsfolk"] = {
            "class": "CCreature",
            "properties": {"race": {"ref": "warriorClass"}},
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "Townsfolk.properties.race.ref",
            'property "race" for class "CCreature" expected object inheriting from '
            '"CCreatureRace"; got "CCreatureClass"',
        )

    def test_creature_race_wrong_typed_value_reports_race_path(self):
        root = self.make_fixture()
        self.write_creature_race_fixture(root)
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["Townsfolk"] = {
            "class": "CCreature",
            "properties": {"race": "humanRace"},
        }
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "Townsfolk.properties.race",
            'property "race" for class "CCreature" expected object inheriting from ' '"CCreatureRace"; got string',
        )

    def _write_creature_race(self, root, properties):
        write_json(
            root / "res/config/creature_races.json",
            {"humanRace": {"class": "CCreatureRace", "properties": properties}},
        )

    def _write_creature_type_catalog(self, root, types):
        write_json(
            root / "res/config/creature_types.json",
            {"creatureTypeCatalog": {"catalogKind": "creatureType", "types": types}},
        )

    def test_creature_race_valid_base_stats_actions_and_types_pass(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        self._write_creature_type_catalog(root, {"humanoid": {"description": "Human-shaped folk."}})
        self._write_creature_race(
            root,
            {
                "baseStats": {
                    "class": "CStats",
                    "properties": {"strength": 5, "agility": 3, "mainStat": "strength"},
                },
                "actions": [
                    {"ref": "Attack"},
                    {"class": "CInteraction", "properties": {"effect": {"ref": "HitEffect"}}},
                ],
                "creatureType": "humanoid",
                "subtypes": ["human", "noble"],
            },
        )

        self.assertEqual([], [str(issue) for issue in validate_repo(root)])

    def test_creature_race_unknown_base_stats_key_is_reported(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        self._write_creature_race(root, {"baseStats": {"class": "CStats", "properties": {"strenght": 5}}})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_races.json",
            "humanRace.properties.baseStats.properties.strenght",
            '"strenght" is not a CStats property; expected one of agility, intelligence, mainStat, name, strength',
        )

    def test_creature_race_flat_base_stats_without_envelope_is_reported(self):
        # A bare/flat stat map fails to deserialize under the engine's strict object envelope
        # ({"class": "CStats", "properties": {...}}), so the validator must reject it up front
        # rather than green-light content that crashes at load time.
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        self._write_creature_race(root, {"baseStats": {"strength": 5}})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_races.json",
            "humanRace.properties.baseStats",
            "expected a CStats object node",
        )

    def test_creature_race_action_not_resolving_to_interaction_is_reported(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        self._write_creature_race(root, {"actions": [{"ref": "LifePotion"}]})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_races.json",
            "humanRace.properties.actions[0]",
            'expected object resolving to "CInteraction"; got "CPotion"',
        )

    def test_creature_race_empty_creature_type_is_reported(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        self._write_creature_race(root, {"creatureType": ""})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_races.json",
            "humanRace.properties.creatureType",
            '"creatureType" expected a non-empty string; got string',
        )

    def test_creature_race_empty_subtype_string_is_reported(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        self._write_creature_race(root, {"subtypes": ["human", ""]})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_races.json",
            "humanRace.properties.subtypes[1]",
            "expected a non-empty string; got string",
        )

    # --- Creature type catalog (EPIC_08/STORY_01/SUBSTORY_01) -------------------------
    # creatureType strings are validated against res/config/creature_types.json.
    # Validation-only: no runtime mechanic reads the catalog.

    def test_creature_race_unknown_creature_type_is_reported(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        self._write_creature_type_catalog(root, {"humanoid": {"description": "Human-shaped folk."}})
        self._write_creature_race(root, {"creatureType": "demon"})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_races.json",
            "humanRace.properties.creatureType",
            'unknown creatureType "demon"; expected one of humanoid',
            "add the new type to res/config/creature_types.json or fix the value",
        )

    def test_creature_type_without_catalog_file_fails_closed(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        self._write_creature_race(root, {"creatureType": "humanoid"})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_races.json",
            "humanRace.properties.creatureType",
            'creatureType "humanoid" cannot be validated: the creature type catalog '
            "res/config/creature_types.json is missing or malformed",
        )

    def test_creature_race_without_creature_type_needs_no_catalog(self):
        # Absent creatureType keeps the current content rules: nothing to check against
        # the catalog, so a fixture repo without creature_types.json stays valid.
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        self._write_creature_race(root, {"subtypes": ["human"]})

        self.assertEqual([], [str(issue) for issue in validate_repo(root)])

    def test_creature_type_catalog_missing_entry_fails_closed(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        # Types authored as top-level keys instead of under the "creatureTypeCatalog"
        # entry would collide with the global config id namespace; reject the shape.
        write_json(root / "res/config/creature_types.json", {"humanoid": {"description": "Human-shaped folk."}})
        self._write_creature_race(root, {"creatureType": "humanoid"})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_types.json",
            'creature type catalog must declare only the "creatureTypeCatalog" entry; unexpected entries: humanoid',
            'creature type catalog is missing the "creatureTypeCatalog" entry',
        )
        self.assertIssueContains(
            issues,
            "humanRace.properties.creatureType",
            'creatureType "humanoid" cannot be validated',
        )

    def test_creature_type_catalog_malformed_types_fails_closed(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        write_json(
            root / "res/config/creature_types.json",
            {"creatureTypeCatalog": {"catalogKind": "creatureType", "types": ["humanoid"]}},
        )
        self._write_creature_race(root, {"creatureType": "humanoid"})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_types.json",
            "creatureTypeCatalog.types",
            "expected object mapping creature type ids to definitions; got array",
        )
        self.assertIssueContains(
            issues,
            "humanRace.properties.creatureType",
            'creatureType "humanoid" cannot be validated',
        )

    def test_creature_type_catalog_empty_types_fails_closed(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        self._write_creature_type_catalog(root, {})
        self._write_creature_race(root, {"creatureType": "humanoid"})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_types.json",
            "creatureTypeCatalog.types",
            "creature type catalog must declare at least one type",
        )
        self.assertIssueContains(
            issues,
            "humanRace.properties.creatureType",
            'creatureType "humanoid" cannot be validated',
        )

    def test_creature_type_catalog_wrong_kind_is_reported(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        write_json(
            root / "res/config/creature_types.json",
            {
                "creatureTypeCatalog": {
                    "catalogKind": "monsterType",
                    "types": {"humanoid": {"description": "Human-shaped folk."}},
                }
            },
        )
        self._write_creature_race(root, {"creatureType": "humanoid"})

        issues = validate_repo(root)

        # The kind mismatch is reported, but the parsed type set stays usable so the
        # valid usage is not double-flagged as unverifiable.
        self.assertIssueContains(
            issues,
            "res/config/creature_types.json",
            "creatureTypeCatalog.catalogKind",
            'expected "creatureType"',
        )
        issue_text = "\n".join(str(issue) for issue in issues)
        self.assertNotIn("cannot be validated", issue_text)
        self.assertNotIn("unknown creatureType", issue_text)

    def test_creature_type_catalog_bad_description_is_reported(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        self._write_creature_type_catalog(root, {"humanoid": {"description": ""}})
        self._write_creature_race(root, {"creatureType": "humanoid"})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_types.json",
            "creatureTypeCatalog.types.humanoid.description",
            "expected non-empty string; got string",
        )
        issue_text = "\n".join(str(issue) for issue in issues)
        self.assertNotIn("cannot be validated", issue_text)

    def test_script_spawn_of_data_only_config_is_reported(self):
        # The runtime config loader (CObjectHandler::registerConfig) skips data-only
        # entries such as the creature type catalog, so a createObject against one
        # can never resolve at runtime and must be rejected here.
        root = self.make_fixture()
        self._write_creature_type_catalog(root, {"humanoid": {"description": "Human-shaped folk."}})
        script_path = root / "res/maps/broken/script.py"
        script_path.write_text(
            script_path.read_text(encoding="utf-8").replace(
                'self.getGame().createObject("validMarket")',
                'self.getGame().createObject("creatureTypeCatalog")',
            ),
            encoding="utf-8",
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'createObject("creatureTypeCatalog")',
            'object ref or class "creatureTypeCatalog" names a data-only config entry',
            "the runtime config loader never registers such entries",
        )

    def test_item_grant_of_data_only_config_is_reported(self):
        root = self.make_fixture()
        self._write_creature_type_catalog(root, {"humanoid": {"description": "Human-shaped folk."}})
        script_path = root / "res/maps/broken/script.py"
        script_path.write_text(
            script_path.read_text(encoding="utf-8").replace(
                'event.getCause().addItem("LifePotion")',
                'event.getCause().addItem("creatureTypeCatalog")',
            ),
            encoding="utf-8",
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            'addItem("creatureTypeCatalog")',
            'item ref "creatureTypeCatalog" names a data-only config entry',
            "the runtime config loader never registers such entries",
        )

    def test_object_node_ref_to_data_only_config_is_reported(self):
        root = self.make_fixture()
        self._write_creature_type_catalog(root, {"humanoid": {"description": "Human-shaped folk."}})
        config_path = root / "res/maps/broken/config.json"
        config = read_json(config_path)
        config["catalogCave"] = {"class": "CBuilding", "properties": {"monster": {"ref": "creatureTypeCatalog"}}}
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/config.json",
            "catalogCave.properties.monster.ref",
            'ref "creatureTypeCatalog" names a data-only config entry',
            "the runtime config loader never registers such entries",
        )

    def test_creature_type_catalog_matches_observed_content_types(self):
        # The catalog is the observed creatureType set by construction: every type
        # declared by real content is catalogued, and the catalog carries no extras.
        catalog = read_json(REPO_ROOT / "res/config/creature_types.json")
        catalogued = set(catalog["creatureTypeCatalog"]["types"])
        races = read_json(REPO_ROOT / "res/config/creature_races.json")
        observed = {
            race["properties"]["creatureType"]
            for race in races.values()
            if isinstance(race, dict) and "creatureType" in race.get("properties", {})
        }
        self.assertEqual(observed, catalogued)

    def test_amulet_quest_carrier_and_runtime_actor_pass_validation(self):
        root = self.make_amulet_fixture()

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_amulet_quest_item_removed_from_carrier_is_reported(self):
        root = self.make_amulet_fixture()
        config_path = root / "res/maps/amulet/config.json"
        config = read_json(config_path)
        # Simulate the migration moving the quest item off the thief carrier (e.g. onto a
        # shared GoblinRace/thief class template) by dropping it from the carrier items.
        config["goblinThief"]["properties"]["items"] = []
        write_json(config_path, config)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/amulet/config.json",
            "goblinThief.properties.items",
            'must carry quest item "preciousAmulet" as instance inventory',
        )

    def test_amulet_quest_runtime_actor_name_broken_is_reported(self):
        root = self.make_amulet_fixture()
        script_path = root / "res/maps/amulet/script.py"
        # Break only the runtime name assigned to the spawned carrier.
        script_path.write_text(
            script_path.read_text(encoding="utf-8").replace('"amuletGoblin"', '"strayGoblin"'),
            encoding="utf-8",
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/amulet/script.py",
            'createObject("goblinThief")',
            'runtime actor name "amuletGoblin" must be assigned to a spawned "goblinThief"',
        )

    def test_amulet_quest_guard_is_load_bearing(self):
        # Removing the registration must make the broken-item fixture stop being rejected,
        # proving the guard (not some sibling rule) is what catches the violation.
        root = self.make_amulet_fixture()
        config_path = root / "res/maps/amulet/config.json"
        config = read_json(config_path)
        config["goblinThief"]["properties"]["items"] = []
        write_json(config_path, config)

        validator = ContentValidator(root)
        validator._validate_amulet_quest_actor = lambda *args, **kwargs: None
        issue_text = "\n".join(str(issue) for issue in validator.validate())

        self.assertNotIn('must carry quest item "preciousAmulet"', issue_text)

    def make_amulet_fixture(self):
        root = self.make_fixture()
        (root / "res/maps/amulet").mkdir(parents=True)
        write_json(
            root / "res/config/items.json",
            {
                "LifePotion": {"class": "CPotion"},
                "HitEffect": {"class": "CEffect"},
                "Attack": {"class": "CInteraction", "properties": {"effect": {"ref": "HitEffect"}}},
                "GoblinThief": {"class": "CCreature"},
                "preciousAmulet": {"class": "CItem", "properties": {"name": "preciousAmulet"}},
            },
        )
        write_json(
            root / "res/maps/amulet/map.json",
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
                                "type": "AmuletEvent",
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
            root / "res/maps/amulet/config.json",
            {
                "goblinThief": {
                    "ref": "GoblinThief",
                    "properties": {"items": [{"ref": "preciousAmulet"}]},
                },
            },
        )
        write_amulet_script(root / "res/maps/amulet/script.py")
        return root

    def make_campaign_fixture(self, manifest=None, campaign_id="trial", **script_kwargs):
        root = self.make_fixture()
        write_campaign_script(root / "res/maps/broken/script.py", **script_kwargs)
        campaign_dir = root / "res/campaigns" / campaign_id
        campaign_dir.mkdir(parents=True)
        write_json(campaign_dir / "campaign.json", valid_campaign_manifest() if manifest is None else manifest)
        return root

    def test_valid_campaign_fixture_passes_validation(self):
        root = self.make_campaign_fixture()

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_campaign_directory_without_manifest_is_flagged(self):
        root = self.make_campaign_fixture()
        (root / "res/campaigns/empty").mkdir()

        issues = validate_repo(root)

        self.assertIssueContains(issues, "res/campaigns/empty/campaign.json", "missing required JSON file")

    def test_campaign_manifest_missing_keys_and_wrong_header_are_flagged(self):
        manifest = valid_campaign_manifest()
        manifest["format"] = "wrong-format"
        manifest["schemaVersion"] = 2
        manifest["bogus"] = True
        del manifest["title"]
        root = self.make_campaign_fixture(manifest=manifest)

        issues = validate_repo(root)

        self.assertIssueContains(issues, "$.format", 'expected "fall-of-nouraajd-campaign"')
        self.assertIssueContains(issues, "$.schemaVersion", "expected 1")
        self.assertIssueContains(issues, 'missing required key "title"')
        self.assertIssueContains(issues, 'unknown key "bogus"')

    def test_campaign_id_must_match_directory_name(self):
        manifest = valid_campaign_manifest()
        manifest["campaignId"] = "other"
        root = self.make_campaign_fixture(manifest=manifest)

        issues = validate_repo(root)

        self.assertIssueContains(issues, "$.campaignId", 'must match its directory name "trial"')

    def test_campaign_start_and_next_targets_must_name_scenarios(self):
        manifest = valid_campaign_manifest()
        manifest["start"] = "nowhere"
        manifest["scenarios"]["one"]["next"] = {"completed": "missing"}
        root = self.make_campaign_fixture(manifest=manifest)

        issues = validate_repo(root)

        self.assertIssueContains(issues, "$.start", "must name a scenario in this campaign")
        self.assertIssueContains(issues, "$.scenarios.one.next.completed", "must name a scenario in this campaign")

    def test_campaign_scenario_map_must_exist(self):
        manifest = valid_campaign_manifest()
        manifest["scenarios"]["two"]["map"] = "missing"
        root = self.make_campaign_fixture(manifest=manifest)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues, "$.scenarios.two.map", "map transition target is missing res/maps/missing/map.json"
        )

    def test_campaign_unreachable_scenario_is_flagged(self):
        manifest = valid_campaign_manifest()
        manifest["scenarios"]["orphan"] = {
            "map": "broken",
            "title": "Orphan",
            "briefing": "Unreached.",
            "next": {},
        }
        root = self.make_campaign_fixture(manifest=manifest)

        issues = validate_repo(root)

        self.assertIssueContains(issues, "$.scenarios.orphan", 'unreachable from the campaign "start" scenario')

    def test_campaign_cycle_and_missing_terminal_are_flagged(self):
        manifest = valid_campaign_manifest()
        manifest["scenarios"]["two"]["next"] = {"completed": "one"}
        root = self.make_campaign_fixture(manifest=manifest)

        issues = validate_repo(root)

        self.assertIssueContains(issues, "$.scenarios", "campaign scenario graph must be acyclic")

    def test_campaign_missing_terminal_scenario_is_flagged(self):
        manifest = valid_campaign_manifest()
        manifest["scenarios"]["two"]["next"] = {"completed": "ghost"}
        root = self.make_campaign_fixture(manifest=manifest)

        issues = validate_repo(root)

        self.assertIssueContains(issues, "$.scenarios.two.next.completed", "must name a scenario in this campaign")
        self.assertIssueContains(issues, "no reachable terminal scenario")

    def test_campaign_routed_outcome_must_be_declared_by_map_script(self):
        manifest = valid_campaign_manifest()
        manifest["scenarios"]["one"]["next"] = {"undeclared": "two"}
        root = self.make_campaign_fixture(manifest=manifest)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "$.scenarios.one.next.undeclared",
            "outcome is not declared in res/maps/broken/script.py CAMPAIGN_OUTCOMES",
        )

    def test_campaign_reported_outcome_must_be_routed_by_non_terminal_scenario(self):
        manifest = valid_campaign_manifest()
        manifest["scenarios"]["one"]["next"] = {"other": "two"}
        root = self.make_campaign_fixture(manifest=manifest, outcomes='("completed", "other")')

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "$.scenarios.one.next",
            'can report outcome "completed"',
            "which this non-terminal scenario does not route",
        )

    def test_campaign_routes_require_script_outcome_declaration(self):
        root = self.make_campaign_fixture(outcomes=None, completion_call=None)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "$.scenarios.one.next",
            'map "broken" script declares no CAMPAIGN_OUTCOMES but this scenario routes outcomes',
        )

    def test_campaign_carryover_shape_is_validated(self):
        manifest = valid_campaign_manifest()
        manifest["scenarios"]["one"]["carryover"] = {
            "gold_max": -5,
            "items_allow": ["NoSuchItem"],
            "items_deny": ["LifePotion"],
            "bogus": 1,
        }
        root = self.make_campaign_fixture(manifest=manifest)

        issues = validate_repo(root)

        self.assertIssueContains(issues, "$.scenarios.one.carryover", 'unknown carryover key "bogus"')
        self.assertIssueContains(issues, '"items_allow" or "items_deny", not both')
        self.assertIssueContains(issues, "$.scenarios.one.carryover.gold_max", "must be a non-negative integer")
        self.assertIssueContains(issues, "$.scenarios.one.carryover.items_allow", 'unknown item ref "NoSuchItem"')

    def test_script_complete_scenario_requires_outcome_declaration(self):
        root = self.make_campaign_fixture(manifest=None, outcomes=None)
        manifest_path = root / "res/campaigns/trial/campaign.json"
        manifest = read_json(manifest_path)
        manifest["scenarios"]["one"]["next"] = {}
        write_json(manifest_path, manifest)

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/maps/broken/script.py",
            "complete_scenario is used but the script declares no CAMPAIGN_OUTCOMES",
        )

    def test_script_complete_scenario_outcome_must_be_declared(self):
        root = self.make_campaign_fixture(outcomes='("something_else",)')

        issues = validate_repo(root)

        self.assertIssueContains(
            issues, "res/maps/broken/script.py", 'outcome "completed" is not declared in CAMPAIGN_OUTCOMES'
        )

    def test_script_complete_scenario_fallback_map_must_exist(self):
        root = self.make_campaign_fixture(
            completion_call='campaign.complete_scenario(self.getGame(), "completed", fallback_map="missingmap")'
        )

        issues = validate_repo(root)

        self.assertIssueContains(
            issues, "res/maps/broken/script.py", "map transition target is missing res/maps/missingmap/map.json"
        )

    def test_script_campaign_outcomes_must_be_literal_strings(self):
        root = self.make_campaign_fixture(outcomes="tuple(dynamic_outcomes)")

        issues = validate_repo(root)

        self.assertIssueContains(
            issues, "res/maps/broken/script.py", "CAMPAIGN_OUTCOMES must be a literal tuple or list of outcome strings"
        )

    def _write_crafting_fixture(self, root, recipes):
        write_json(
            root / "res/config/buildings.json",
            {
                "AlchemyTable": {
                    "class": "CBuilding",
                    "properties": {"label": "Alchemist's Table", "craftingStationId": "alchemyTable"},
                }
            },
        )
        write_json(root / "res/config/crafting.json", recipes)

    def _valid_recipe(self, **overrides):
        recipe = {
            "station": "alchemyTable",
            "inputs": [{"item": "LifePotion", "count": 2}],
            "output": {"item": "LifePotion", "count": 1},
            "gold": 20,
            "successChance": 90,
        }
        recipe.update(overrides)
        return recipe

    def test_crafting_valid_recipe_passes_validation(self):
        root = self.make_fixture()
        self._write_crafting_fixture(root, {"brew": self._valid_recipe()})

        issues = validate_repo(root)

        self.assertEqual([], [str(issue) for issue in issues])

    def test_crafting_outputs_list_is_validated(self):
        root = self.make_fixture()
        recipe = self._valid_recipe(outputs=[{"item": "LifePotion"}, {"item": "MissingItem"}])
        del recipe["output"]
        self._write_crafting_fixture(root, {"brew": recipe})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues, "res/config/crafting.json", "brew.outputs[1].item", 'unknown recipe item "MissingItem"'
        )

    def test_crafting_output_and_outputs_together_are_flagged(self):
        root = self.make_fixture()
        recipe = self._valid_recipe(outputs=[{"item": "LifePotion"}])
        self._write_crafting_fixture(root, {"brew": recipe})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues, "res/config/crafting.json", 'recipe defines both "output" and "outputs"; use one'
        )

    def test_crafting_duplicate_input_items_are_flagged(self):
        root = self.make_fixture()
        recipe = self._valid_recipe(inputs=[{"item": "LifePotion", "count": 1}, {"item": "LifePotion", "count": 1}])
        self._write_crafting_fixture(root, {"brew": recipe})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/crafting.json",
            "brew.inputs[1].item",
            'duplicate input item "LifePotion"',
        )

    def test_crafting_scalar_fields_are_validated(self):
        root = self.make_fixture()
        recipe = self._valid_recipe(gold=-5, successChance=150, unlockFlag="   ", unlockHint="")
        recipe["inputs"][0]["count"] = 0
        self._write_crafting_fixture(root, {"brew": recipe})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/crafting.json",
            "brew.gold",
            "expected non-negative integer gold cost",
            "brew.successChance",
            "expected integer success chance in 0..100",
            "brew.unlockFlag",
            "expected non-empty string flag name",
            "brew.unlockHint",
            "expected non-empty string hint text",
            "brew.inputs[0].count",
            "expected positive integer count",
        )

    def assertIssueContains(self, issues, *substrings):
        issue_text = "\n".join(str(issue) for issue in issues)
        for substring in substrings:
            with self.subTest(substring=substring):
                self.assertIn(substring, issue_text)

    # --- Artifact set (compound artifact) validation --------------------------------

    _ARTIFACT_SLOTS = {
        "slotConfiguration": {
            "class": "CSlotConfig",
            "properties": {
                "configuration": {
                    "0": {"class": "CSlot", "properties": {"slotName": "RightHand", "types": ["CWeapon"]}},
                    "1": {"class": "CSlot", "properties": {"slotName": "LeftHand", "types": ["CSmallWeapon", "CShield"]}},
                    "2": {"class": "CSlot", "properties": {"slotName": "Head", "types": ["CHelmet"]}},
                    "3": {"class": "CSlot", "properties": {"slotName": "Chest", "types": ["CArmor"]}},
                    "5": {"class": "CSlot", "properties": {"slotName": "Feet", "types": ["CBoots"]}},
                    "6": {"class": "CSlot", "properties": {"slotName": "Legs", "types": ["CPants"]}},
                }
            },
        }
    }

    def _run_artifact_sets(self, sets, items):
        """Drive _validate_artifact_sets directly with hand-built config state."""
        from scripts.validate_content import ConfigEntry, ContentValidator

        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        validator = ContentValidator(Path(temp_dir.name))
        config_dir = validator.repo_root / "res" / "config"
        validator.global_files[config_dir / "slots.json"] = self._ARTIFACT_SLOTS
        validator.global_files[config_dir / "artifact_sets.json"] = sets
        for item_id, data in items.items():
            validator.global_entries[item_id] = ConfigEntry(key=item_id, data=data, path=config_dir / "items.json")
        validator._validate_artifact_sets()
        return [str(issue) for issue in validator.issues]

    @staticmethod
    def _valid_artifact_items():
        return {
            "PieceHelm": {"class": "CHelmet", "properties": {"power": 3}},
            "PieceArmor": {"class": "CArmor", "properties": {"power": 5}},
            "PieceBlade": {"class": "CWeapon", "properties": {"power": 4}},
            "TheCombined": {
                "class": "CArmor",
                "properties": {"coveredSlots": ["0", "2"], "tags": ["compound"]},
            },
        }

    @staticmethod
    def _valid_artifact_set():
        return {
            "demoSet": {
                "label": "Demo Set",
                "pieces": ["PieceHelm", "PieceArmor", "PieceBlade"],
                "combined": "TheCombined",
            }
        }

    def test_valid_artifact_set_passes_validation(self):
        issues = self._run_artifact_sets(self._valid_artifact_set(), self._valid_artifact_items())
        self.assertEqual([], issues)

    def test_artifact_set_unknown_piece_is_flagged(self):
        sets = self._valid_artifact_set()
        sets["demoSet"]["pieces"] = ["PieceHelm", "PieceArmor", "MissingPiece"]
        issues = self._run_artifact_sets(sets, self._valid_artifact_items())
        self.assertIssueContains(issues, "artifact_sets.json", "demoSet.pieces[2]", 'unknown piece item "MissingPiece"')

    def test_artifact_set_duplicate_slot_is_flagged(self):
        items = self._valid_artifact_items()
        items["PieceBlade"] = {"class": "CHelmet", "properties": {}}  # second helmet -> slot clash on Head
        issues = self._run_artifact_sets(self._valid_artifact_set(), items)
        self.assertIssueContains(issues, "demoSet.pieces[2]", "occupies slot 2 already used by another piece")

    def test_artifact_set_covered_slots_mismatch_is_flagged(self):
        items = self._valid_artifact_items()
        items["TheCombined"]["properties"]["coveredSlots"] = ["0"]  # missing head slot 2
        issues = self._run_artifact_sets(self._valid_artifact_set(), items)
        self.assertIssueContains(issues, "demoSet.combined", "coveredSlots", "must equal the non-primary piece slots")

    def test_artifact_set_missing_compound_tag_is_flagged(self):
        items = self._valid_artifact_items()
        items["TheCombined"]["properties"]["tags"] = []
        issues = self._run_artifact_sets(self._valid_artifact_set(), items)
        self.assertIssueContains(issues, "demoSet.combined", 'must declare the "compound" tag')

    def test_artifact_set_combined_cannot_be_a_piece(self):
        sets = self._valid_artifact_set()
        sets["demoSet"]["pieces"] = ["PieceHelm", "PieceArmor", "TheCombined"]
        issues = self._run_artifact_sets(sets, self._valid_artifact_items())
        self.assertIssueContains(issues, "demoSet.combined", "combined item cannot also be a set piece")

    def test_artifact_set_shared_piece_across_sets_is_flagged(self):
        sets = self._valid_artifact_set()
        sets["otherSet"] = {"label": "Other", "pieces": ["PieceHelm", "PieceArmor"], "combined": "TheCombined"}
        issues = self._run_artifact_sets(sets, self._valid_artifact_items())
        self.assertIssueContains(issues, "already belongs to set")

    def test_artifact_set_quest_piece_requires_quest_combined(self):
        items = self._valid_artifact_items()
        items["PieceHelm"]["properties"]["tags"] = ["quest"]
        issues = self._run_artifact_sets(self._valid_artifact_set(), items)
        self.assertIssueContains(issues, "demoSet.combined", 'must declare the "quest" tag')

    def make_fixture(self, script_quest="goodQuest", script_map="broken", class_check=None, player_templates=None):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "res/config").mkdir(parents=True)
        (root / "res/plugins").mkdir(parents=True)
        (root / "res/maps/broken").mkdir(parents=True)

        if player_templates is not None:
            write_json(root / "res/config/players.json", player_templates)

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
        write_script(
            root / "res/maps/broken/script.py",
            script_quest=script_quest,
            script_map=script_map,
            class_check=class_check,
        )
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


def write_script(path, script_quest, script_map, class_check=None):
    class_check_method = ""
    if class_check is not None:
        class_check_method = textwrap.indent(
            textwrap.dedent(f"""
                def class_condition(self):
                    return {class_check}
            """),
            " " * 20,
        )
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
{class_check_method}
                @trigger(context, "onEnter", "start")
                class StartTrigger(CEvent):
                    pass
            """).lstrip(),
        encoding="utf-8",
    )


def valid_campaign_manifest():
    return {
        "format": "fall-of-nouraajd-campaign",
        "schemaVersion": 1,
        "campaignId": "trial",
        "title": "Trial Campaign",
        "description": "Two chapters on one map.",
        "start": "one",
        "completionText": "The trial ends.",
        "scenarios": {
            "one": {
                "map": "broken",
                "title": "Chapter I",
                "briefing": "Begin the trial.",
                "epilogue": "Onward.",
                "carryover": {"gold_max": 100, "items_deny": ["LifePotion"]},
                "next": {"completed": "two"},
            },
            "two": {
                "map": "broken",
                "title": "Chapter II",
                "briefing": "Finish the trial.",
                "next": {},
            },
        },
    }


def write_campaign_script(
    path,
    outcomes='("completed",)',
    completion_call='campaign.complete_scenario(self.getGame(), "completed", fallback_map="broken")',
):
    """Write the fixture map script with campaign declarations.

    Mirrors write_script but reports a campaign outcome instead of a direct
    changeMap so campaign validation paths can be exercised. ``outcomes=None``
    omits the CAMPAIGN_OUTCOMES declaration; ``completion_call=None`` omits the
    complete_scenario report.
    """
    outcomes_line = f"CAMPAIGN_OUTCOMES = {outcomes}" if outcomes else ""
    completion_line = completion_call or "pass"
    path.write_text(
        textwrap.dedent(f"""
            def load(self, context):
                from game import CDialog
                from game import CEvent
                from game import CQuest
                from game import register
                from game import trigger

                from game import campaign

                {outcomes_line}

                def ensure_quest(player, quest_name):
                    player.addQuest(quest_name)

                @register(context)
                class StartEvent(CEvent):
                    def onEnter(self, event):
                        self.getGame().createObject("validMarket")
                        ensure_quest(event.getCause(), "goodQuest")
                        event.getCause().addItem("LifePotion")
                        self.getMap().getObjectByName("start")
                        {completion_line}

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


def write_amulet_script(path):
    path.write_text(
        textwrap.dedent("""
            def load(self, context):
                from game import CEvent
                from game import register

                @register(context)
                class AmuletEvent(CEvent):
                    def onEnter(self, event):
                        game = self.getGame()
                        game_map = game.getMap()
                        goblin = game.createObject("goblinThief")
                        goblin.setStringProperty("name", "amuletGoblin")
                        game_map.addObject(goblin)

                    def complete(self):
                        amulet_goblin = self.getMap().getObjectByName("amuletGoblin")
                        if amulet_goblin:
                            self.getMap().removeObject(amulet_goblin)
            """).lstrip(),
        encoding="utf-8",
    )


def write_gooby_chain_script(path, template, runtime, trigger_target):
    """Write a script whose CaveTrigger spawns ``template`` and renames it to ``runtime``.

    Mirrors the real nouraajd Gooby chain so the runtime-name preservation guard can be
    exercised: a createObject spawn, a setStringProperty("name", ...) rename, and an
    optional onDestroy trigger against ``trigger_target``.  The template config entry is
    written alongside so unrelated ref checks stay quiet.  Pass ``trigger_target=None`` to
    omit the recognizing trigger.
    """
    config_path = path.parent / "config.json"
    config = read_json(config_path)
    config[template] = {"class": "CCreature"}
    write_json(config_path, config)

    trigger_block = ""
    if trigger_target is not None:
        trigger_block = textwrap.dedent(f"""
            @trigger(context, "onDestroy", "{trigger_target}")
            class GoobyTrigger(CTrigger):
                def trigger(self, obj, event):
                    pass
            """)
    trigger_block = textwrap.indent(trigger_block.strip(), "    ")

    path.write_text(
        textwrap.dedent(f"""
            def load(self, context):
                from game import CEvent
                from game import CQuest
                from game import CTrigger
                from game import register
                from game import trigger

                @register(context)
                class StartEvent(CEvent):
                    def onEnter(self, event):
                        pass

                @register(context)
                class GoodQuest(CQuest):
                    pass

                @trigger(context, "onDestroy", "cave1")
                class CaveTrigger(CTrigger):
                    def trigger(self, obj, event):
                        game = self.getGame()
                        gooby = game.createObject("{template}")
                        gooby.setStringProperty("name", "{runtime}")
                        game.getMap().addObject(gooby)

            """).lstrip() + trigger_block + "\n",
        encoding="utf-8",
    )


def write_property_hygiene_script(path, body):
    header = textwrap.dedent("""
        def load(self, context):
            from game import CDialog
            from game import CEvent
            from game import CQuest
            from game import LegacyBoolFlag
            from game import QuestStateStore
            from game import register
        """).lstrip()
    script_body = textwrap.indent(textwrap.dedent(body).strip(), "    ")
    trailer = textwrap.indent(
        textwrap.dedent("""
            @register(context)
            class GoodQuest(CQuest):
                pass

            @register(context)
            class BrokenDialog(CDialog):
                def valid_action(self):
                    pass

                def valid_condition(self):
                    return True
            """).strip(),
        "    ",
    )
    path.write_text(f"{header}\n{script_body}\n\n{trailer}\n", encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class CreatureOverrideInventoryTest(unittest.TestCase):
    def test_repo_inventory_lists_known_map_local_overrides(self):
        overrides = {
            (override.path, override.location): override for override in inventory_creature_overrides(REPO_ROOT)
        }

        siege_mage = overrides[("res/maps/siege/config.json", "siegePritzMage")]
        self.assertEqual("PritzMage", siege_mage.template)
        self.assertEqual(("controller", "affiliation", "items"), siege_mage.properties)

        nested_pritz = overrides[("res/maps/nouraajd/config.json", "cave1.properties.monster")]
        self.assertEqual("cave1", nested_pritz.key)
        self.assertEqual("Pritz", nested_pritz.template)
        self.assertEqual(("controller", "affiliation"), nested_pritz.properties)

        anchor = overrides[("res/maps/ritual/config.json", "ritualAnchorNorth.properties.monster")]
        self.assertEqual("Cultist", anchor.template)
        self.assertEqual(("controller",), anchor.properties)

    def test_inventory_detects_nested_overrides_and_ignores_non_creatures(self):
        root = self.make_creature_fixture()

        overrides = inventory_creature_overrides(root)
        by_location = {override.location: override for override in overrides}

        self.assertIn("townGuard", by_location)
        self.assertEqual("Soldier", by_location["townGuard"].template)
        self.assertEqual(("controller", "items"), by_location["townGuard"].properties)

        self.assertIn("spawner.properties.monster", by_location)
        self.assertEqual(("affiliation",), by_location["spawner.properties.monster"].properties)

        # A creature ref that overrides no watched property and a non-creature ref are excluded.
        self.assertNotIn("plainSoldier", by_location)
        self.assertNotIn("loot", by_location)

    def make_creature_fixture(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "res/config").mkdir(parents=True)
        (root / "res/plugins").mkdir(parents=True)
        (root / "res/maps/keep").mkdir(parents=True)

        write_json(
            root / "res/config/monsters.json",
            {"Soldier": {"class": "CCreature", "properties": {"animation": "images/monsters/soldier"}}},
        )
        write_json(
            root / "res/config/items.json",
            {"Sword": {"class": "CItem"}},
        )
        write_json(
            root / "res/config/buildings.json",
            {"Spawner": {"class": "CBuilding"}},
        )
        write_json(
            root / "res/maps/keep/map.json",
            {
                "type": "map",
                "width": 1,
                "height": 1,
                "layers": [{"type": "tilelayer", "width": 1, "height": 1, "data": [0]}],
                "tilesets": [{"firstgid": 1, "tileproperties": {}}],
                "nextobjectid": 1,
            },
        )
        write_json(
            root / "res/maps/keep/config.json",
            {
                "townGuard": {
                    "ref": "Soldier",
                    "properties": {
                        "controller": {"class": "CTargetController", "properties": {"target": "player"}},
                        "items": [{"ref": "Sword"}],
                    },
                },
                "plainSoldier": {"ref": "Soldier", "properties": {"message": "Just passing through."}},
                "loot": {"ref": "Sword", "properties": {"animation": "images/item"}},
                "spawner": {
                    "ref": "Spawner",
                    "properties": {"monster": {"ref": "Soldier", "properties": {"affiliation": "keep"}}},
                },
            },
        )
        return root


class CreatureClassificationTest(unittest.TestCase):
    # Concrete player template ids shipped in res/config/monsters.json. These are
    # the "class": "CPlayer" entries; the classification must derive playerhood from
    # CPlayer metadata inheritance, never from these names.
    EXPECTED_PLAYER_TEMPLATES = ("Assasin", "Inquisitor", "Sorcerer", "Warrior", "Wayfarer")

    def test_repo_classification_lists_concrete_player_templates_as_players(self):
        classification = classify_creature_templates(REPO_ROOT)

        for player in self.EXPECTED_PLAYER_TEMPLATES:
            with self.subTest(player=player):
                self.assertIn(player, classification.player_templates)
                # A player template must never be silently treated as a monster.
                self.assertNotIn(player, classification.monster_templates)

    def test_repo_classification_separates_monsters_from_players(self):
        classification = classify_creature_templates(REPO_ROOT)

        self.assertEqual(set(self.EXPECTED_PLAYER_TEMPLATES), set(classification.player_templates))
        self.assertTrue(classification.monster_templates)
        # Known non-player creatures must land in the monster partition.
        self.assertIn("Cultist", classification.monster_templates)
        self.assertIn("Pritz", classification.monster_templates)
        # Player and monster partitions are disjoint.
        self.assertEqual(
            set(),
            set(classification.player_templates) & set(classification.monster_templates),
        )

    def test_player_templates_are_flagged_in_creature_enumeration(self):
        # CPlayer inherits CCreature, so getAllSubTypes("CCreature") (used by the
        # random-encounter table builder) enumerates every player template. The
        # classification must surface exactly these so encounter code can exclude them.
        classification = classify_creature_templates(REPO_ROOT)

        self.assertEqual(
            set(self.EXPECTED_PLAYER_TEMPLATES),
            set(classification.players_in_creature_enumeration),
        )
        self.assertEqual(
            set(classification.player_templates),
            set(classification.players_in_creature_enumeration),
        )

    def test_classification_is_derived_from_metadata_inheritance_not_names(self):
        # A creature template whose id looks like a monster but whose class is a
        # CPlayer subclass must classify as a player; a player-sounding id on a plain
        # CCreature must classify as a monster. This proves lineage, not naming, drives
        # the decision.
        root = self.make_classification_fixture()

        classification = classify_creature_templates(root)

        self.assertIn("grumpyOgre", classification.player_templates)
        self.assertNotIn("grumpyOgre", classification.monster_templates)
        self.assertIn("heroLookalike", classification.monster_templates)
        self.assertNotIn("heroLookalike", classification.player_templates)
        self.assertIn("grumpyOgre", classification.players_in_creature_enumeration)
        self.assertNotIn("heroLookalike", classification.players_in_creature_enumeration)

    def make_classification_fixture(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "res/config").mkdir(parents=True)
        (root / "src/object").mkdir(parents=True)

        # Engine metadata: CPlayer derives from CCreature, mirroring src/object/CPlayer.h.
        (root / "src/object/CCreatures.h").write_text(
            textwrap.dedent("""
                class CMapObject {
                    V_META(CMapObject, CGameObject, vstd::meta::empty())
                };

                class CCreature {
                    V_META(CCreature, CMapObject, vstd::meta::empty())
                };

                class CPlayer {
                    V_META(CPlayer, CCreature, vstd::meta::empty())
                };
            """).lstrip(),
            encoding="utf-8",
        )
        write_json(
            root / "res/config/monsters.json",
            {
                # Monster-sounding id, but a CPlayer subtype -> classified as player.
                "grumpyOgre": {"class": "CPlayer", "properties": {"label": "Ogre"}},
                # Hero-sounding id, but a plain CCreature -> classified as monster.
                "heroLookalike": {"class": "CCreature", "properties": {"label": "Hero"}},
            },
        )
        return root


class UnmigratedCreatureReportTest(unittest.TestCase):
    def make_unmigrated_fixture(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "res/config").mkdir(parents=True)
        (root / "src/object").mkdir(parents=True)

        # Engine metadata: CPlayer derives from CCreature, mirroring src/object/CPlayer.h.
        (root / "src/object/CCreatures.h").write_text(
            textwrap.dedent("""
                class CMapObject {
                    V_META(CMapObject, CGameObject, vstd::meta::empty())
                };

                class CCreature {
                    V_META(CCreature, CMapObject, vstd::meta::empty())
                };

                class CPlayer {
                    V_META(CPlayer, CCreature, vstd::meta::empty())
                };
            """).lstrip(),
            encoding="utf-8",
        )
        write_json(
            root / "res/config/monsters.json",
            {
                # Fully migrated creature: carries both archetype references.
                "MigratedGoblin": {
                    "class": "CCreature",
                    "properties": {"race": {"ref": "GoblinRace"}, "creatureClass": {"ref": "BruteClass"}},
                },
                # Missing only the class reference.
                "NoClassGoblin": {
                    "class": "CCreature",
                    "properties": {"race": {"ref": "GoblinRace"}},
                },
                # Missing only the race reference.
                "NoRaceGoblin": {
                    "class": "CCreature",
                    "properties": {"creatureClass": {"ref": "BruteClass"}},
                },
                # Unmigrated creature: missing both (and no properties block at all path).
                "LegacyGoblin": {"class": "CCreature", "properties": {"label": "Goblin"}},
                # Player template (CPlayer inherits CCreature) -- also subject to migration.
                "LegacyHero": {"class": "CPlayer", "properties": {"label": "Hero"}},
                # Not a creature -- must never appear in the report.
                "PlainItem": {"class": "CItem", "properties": {"label": "Sword"}},
            },
        )
        return root

    def test_report_lists_only_creatures_missing_archetype_references(self):
        root = self.make_unmigrated_fixture()

        report = report_unmigrated_creatures(root)
        missing_by_id = {creature.config_id: creature.missing for creature in report}

        self.assertEqual(
            {
                "NoClassGoblin": ("creatureClass",),
                "NoRaceGoblin": ("race",),
                "LegacyGoblin": ("creatureClass", "race"),
                "LegacyHero": ("creatureClass", "race"),
            },
            missing_by_id,
        )
        # Fully migrated creatures and non-creatures never appear.
        self.assertNotIn("MigratedGoblin", missing_by_id)
        self.assertNotIn("PlainItem", missing_by_id)

    def test_report_output_is_deterministically_sorted(self):
        root = self.make_unmigrated_fixture()

        report = report_unmigrated_creatures(root)

        ids = [creature.config_id for creature in report]
        self.assertEqual(sorted(ids), ids)
        for creature in report:
            self.assertEqual(sorted(creature.missing), list(creature.missing))
            self.assertEqual("res/config/monsters.json", creature.path)

    def test_report_does_not_affect_normal_validation(self):
        # Every shipped creature is unmigrated today, yet the normal validation run
        # must still pass -- the report is informational and shares no failing path.
        self.assertEqual([], [str(issue) for issue in validate_repo(REPO_ROOT)])

        report = report_unmigrated_creatures(REPO_ROOT)
        # The report is non-empty on current content (migration is still in progress)
        # and the not-yet-migrated production player templates surface as still needing
        # migration.
        self.assertTrue(report)
        report_ids = {creature.config_id for creature in report}
        # All five production player templates have been migrated to a creatureClass
        # (Warrior/Sorcerer/Assasin/Inquisitor/Wayfarer, EPIC_04/STORY_02/SUBSTORY_01–05);
        # each still surfaces in the report but now only lacks a race. Other unmigrated
        # creatures keep the report non-empty.
        for migrated in ("Warrior", "Sorcerer", "Assasin", "Inquisitor", "Wayfarer"):
            self.assertIn(migrated, report_ids)
            self.assertEqual(("race",), next(c.missing for c in report if c.config_id == migrated))


class RequiredProductionArchetypeTest(unittest.TestCase):
    """EPIC_06/STORY_04/SUBSTORY_01 -- required production archetypes after migration.

    The enforcement rule is gated behind the migration-complete switch.  These tests
    drive it with the switch explicitly ON over synthetic in-memory content (never the
    real monsters.json) to prove it flags every production creature missing race/class
    in one run, honors the reviewed exception manifest, and stays inert with the switch
    OFF (the default that keeps current full validation green).
    """

    def make_archetype_fixture(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "res/config").mkdir(parents=True)
        (root / "src/object").mkdir(parents=True)

        # Engine metadata: CPlayer derives from CCreature, mirroring src/object/CPlayer.h.
        (root / "src/object/CCreatures.h").write_text(
            textwrap.dedent("""
                class CMapObject {
                    V_META(CMapObject, CGameObject, vstd::meta::empty())
                };

                class CCreature {
                    V_META(CCreature, CMapObject, vstd::meta::empty())
                };

                class CPlayer {
                    V_META(CPlayer, CCreature, vstd::meta::empty())
                };
            """).lstrip(),
            encoding="utf-8",
        )
        write_json(
            root / "res/config/monsters.json",
            {
                # Fully migrated creature: declares both archetype references.
                "MigratedGoblin": {
                    "class": "CCreature",
                    "properties": {"race": {"ref": "GoblinRace"}, "creatureClass": {"ref": "BruteClass"}},
                },
                # Missing only the class reference.
                "NoClassGoblin": {
                    "class": "CCreature",
                    "properties": {"race": {"ref": "GoblinRace"}},
                },
                # Missing only the race reference.
                "NoRaceGoblin": {
                    "class": "CCreature",
                    "properties": {"creatureClass": {"ref": "BruteClass"}},
                },
                # Unmigrated creature: missing both.
                "LegacyGoblin": {"class": "CCreature", "properties": {"label": "Goblin"}},
                # Player template (CPlayer inherits CCreature) -- also subject to the rule.
                "LegacyHero": {"class": "CPlayer", "properties": {"label": "Hero"}},
                # Not a creature -- must never be flagged.
                "PlainItem": {"class": "CItem", "properties": {"label": "Sword"}},
            },
        )
        return root

    @staticmethod
    def _archetype_locations(issues):
        # Only the locations of this rule's diagnostics; the synthetic refs/labels in the
        # fixture intentionally trip other validators (unknown ref/property), which are
        # irrelevant to the required-archetype rule under test.
        return {issue.location for issue in issues if "must declare archetype property" in str(issue)}

    def test_switch_on_flags_all_production_creatures_missing_archetypes(self):
        root = self.make_archetype_fixture()

        issues = ContentValidator(root, archetype_migration_complete=True).validate()
        flagged = self._archetype_locations(issues)

        # Every missing archetype across every production creature is reported in ONE run,
        # one issue per absent property at the exact "<id>.properties.<prop>" path.  The
        # fully migrated creature and the non-creature never appear; CPlayer templates do
        # (CPlayer inherits CCreature).
        self.assertEqual(
            {
                "NoClassGoblin.properties.creatureClass",
                "NoRaceGoblin.properties.race",
                "LegacyGoblin.properties.race",
                "LegacyGoblin.properties.creatureClass",
                "LegacyHero.properties.race",
                "LegacyHero.properties.creatureClass",
            },
            flagged,
        )

    def test_manifest_exempted_entry_is_not_flagged(self):
        root = self.make_archetype_fixture()
        exceptions = (
            ArchetypeMigrationException(
                path="res/config/monsters.json",
                key="LegacyGoblin",
                reason="Low-level test fixture exempted from archetype migration.",
            ),
        )

        issues = ContentValidator(
            root,
            archetype_migration_complete=True,
            archetype_migration_exceptions=exceptions,
        ).validate()
        flagged = self._archetype_locations(issues)

        # The exact path+key exemption suppresses BOTH of LegacyGoblin's archetype
        # diagnostics, while every other unmigrated creature is still flagged.
        self.assertEqual(
            {
                "NoClassGoblin.properties.creatureClass",
                "NoRaceGoblin.properties.race",
                "LegacyHero.properties.race",
                "LegacyHero.properties.creatureClass",
            },
            flagged,
        )

    def test_switch_off_is_inert_even_with_unmigrated_creatures(self):
        root = self.make_archetype_fixture()

        # Default constructor (switch defaults to ARCHETYPE_MIGRATION_COMPLETE == False).
        default_issues = ContentValidator(root).validate()
        explicit_off_issues = ContentValidator(root, archetype_migration_complete=False).validate()

        for issues in (default_issues, explicit_off_issues):
            archetype_issues = [str(issue) for issue in issues if "must declare archetype property" in str(issue)]
            self.assertEqual([], archetype_issues)

    def test_manifest_only_matches_exact_path_and_key(self):
        root = self.make_archetype_fixture()
        # A manifest entry whose key matches but whose path points at a different file
        # must NOT suppress the diagnostic (exact path AND key are required).
        exceptions = (
            ArchetypeMigrationException(
                path="res/config/other.json",
                key="LegacyGoblin",
                reason="Wrong file -- must not exempt the real LegacyGoblin.",
            ),
        )

        issues = ContentValidator(
            root,
            archetype_migration_complete=True,
            archetype_migration_exceptions=exceptions,
        ).validate()
        flagged = self._archetype_locations(issues)

        self.assertIn("LegacyGoblin.properties.race", flagged)
        self.assertIn("LegacyGoblin.properties.creatureClass", flagged)


class NouraajdCatacombsContentTest(unittest.TestCase):
    """Content-level guards for the relocated, dedicated-art catacombs entrance.

    These checks run without the native _game module: they operate purely on the
    JSON map/config plus the pure-Python passability rules mirrored from
    res/config/tiles.json and CMap::canStep (a tile is steppable when no blocking
    object occupies it AND the underlying tile type is steppable).
    """

    MAP_DIR = REPO_ROOT / "res/maps/nouraajd"
    TILE_SIZE = 32

    @classmethod
    def setUpClass(cls):
        cls.map_data = read_json(cls.MAP_DIR / "map.json")
        cls.config = read_json(cls.MAP_DIR / "config.json")
        cls.tiles = read_json(REPO_ROOT / "res/config/tiles.json")
        cls.script = (cls.MAP_DIR / "script.py").read_text(encoding="utf-8")

        # tile-type -> canStep, from tiles.json
        cls.tile_can_step = {
            entry["properties"]["tileType"]: bool(entry["properties"].get("canStep", True))
            for entry in cls.tiles.values()
            if isinstance(entry, dict) and "tileType" in entry.get("properties", {})
        }
        # local-tile-id -> tile type (Tiled tileproperties keys are 0-based local ids;
        # map data stores gid = local_id + firstgid).
        cls.tile_types = tile_types_by_id(cls.map_data)
        cls.firstgid = cls.map_data["tilesets"][0].get("firstgid", 1)
        cls.width = cls.map_data["width"]
        cls.height = cls.map_data["height"]
        tile_layers = [L for L in cls.map_data["layers"] if L.get("type") == "tilelayer"]
        cls.tile_data = tile_layers[0]["data"]

        cls.objects = []
        for layer in cls.map_data["layers"]:
            if layer.get("type") == "objectgroup":
                for obj in layer.get("objects", []):
                    tx = obj["x"] // cls.TILE_SIZE
                    ty = obj["y"] // cls.TILE_SIZE
                    cls.objects.append((tx, ty, obj))

        # Object entries whose config resolves to canStep:true do not block movement.
        # Everything else (caves, catacombs, buildings, walls) blocks its tile.
        cls.non_blocking_types = {"StartEvent"}

    # --- helpers -------------------------------------------------------------
    def _config_can_step(self, type_name):
        entry = self.config.get(type_name)
        if not isinstance(entry, dict):
            return False
        props = entry.get("properties", {})
        if isinstance(props, dict) and props.get("canStep") is True:
            return True
        return False

    def _gid_at(self, tx, ty):
        if 0 <= tx < self.width and 0 <= ty < self.height:
            return self.tile_data[ty * self.width + tx]
        return 0

    def _tile_type_at(self, tx, ty):
        gid = self._gid_at(tx, ty)
        if gid == 0:
            return None
        return self.tile_types.get(gid - self.firstgid)

    def _tile_steppable(self, tx, ty):
        tile_type = self._tile_type_at(tx, ty)
        if tile_type is None:
            return False
        return self.tile_can_step.get(tile_type, True)

    def _object_blocks(self, tx, ty):
        for ox, oy, obj in self.objects:
            if (ox, oy) != (tx, ty):
                continue
            type_name = obj.get("type", "")
            if type_name.startswith("ambient"):
                continue
            if type_name in self.non_blocking_types:
                continue
            if self._config_can_step(type_name) or self._config_can_step(obj.get("name", "")):
                continue
            return True
        return False

    def _passable(self, tx, ty):
        return self._tile_steppable(tx, ty) and not self._object_blocks(tx, ty)

    def _reachable_tiles(self):
        from collections import deque

        starts = [(tx, ty) for tx, ty, obj in self.objects if obj.get("type") == "StartEvent"]
        seen = set()
        queue = deque()
        for sx, sy in starts:
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                cell = (sx + dx, sy + dy)
                if self._passable(*cell):
                    seen.add(cell)
                    queue.append(cell)
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cell = (x + dx, y + dy)
                if cell not in seen and self._passable(*cell):
                    seen.add(cell)
                    queue.append(cell)
        return seen

    def _catacombs_object(self):
        matches = [obj for _, _, obj in self.objects if obj.get("name") == "catacombs"]
        return matches

    def _object_tile(self, name):
        for tx, ty, obj in self.objects:
            if obj.get("name") == name:
                return tx, ty
        return None

    # --- tests ---------------------------------------------------------------
    def test_catacombs_animation_uses_dedicated_asset(self):
        """The catacombs config entry overrides Cave art with the dedicated asset,
        and that asset file resolves on disk."""
        entry = self.config["catacombs"]
        self.assertEqual(entry.get("ref"), "Cave")
        animation = entry["properties"]["animation"]
        self.assertEqual(animation, "images/buildings/catacombs")
        # Resolver appends .png to the extension-less animation key.
        asset = REPO_ROOT / "res" / f"{animation}.png"
        self.assertTrue(asset.is_file(), f"missing catacombs art: {asset}")

    def test_base_cave_art_unchanged(self):
        """cave1/cave2 must keep the shared Cave art -- no per-object animation
        override that would divert them onto catacombs art."""
        base_cave = read_json(REPO_ROOT / "res/config/buildings.json")["Cave"]
        self.assertEqual(base_cave["properties"]["animation"], "images/buildings/cave")
        for cave_name in ("cave1", "cave2"):
            props = self.config[cave_name].get("properties", {})
            self.assertNotIn(
                "animation",
                props,
                f"{cave_name} must not override animation (would break shared Cave art)",
            )

    def test_exactly_one_catacombs_map_object(self):
        matches = self._catacombs_object()
        self.assertEqual(len(matches), 1, "expected exactly one map object named 'catacombs'")
        obj = matches[0]
        self.assertEqual(obj.get("type"), "catacombs")
        self.assertTrue(obj.get("visible"))
        self.assertEqual(obj.get("width"), self.TILE_SIZE)
        self.assertEqual(obj.get("height"), self.TILE_SIZE)

    def test_catacombs_relocated_away_from_cave1(self):
        """The relocated entrance must be visually/geographically distinct from
        cave1 (not clustered in the same NW cave maze)."""
        catacombs = self._object_tile("catacombs")
        cave1 = self._object_tile("cave1")
        self.assertIsNotNone(catacombs)
        self.assertIsNotNone(cave1)
        manhattan = abs(catacombs[0] - cave1[0]) + abs(catacombs[1] - cave1[1])
        self.assertGreater(
            manhattan,
            30,
            f"catacombs {catacombs} too close to cave1 {cave1} (manhattan {manhattan})",
        )

    def test_catacombs_tile_unoccupied_by_other_objects(self):
        cx, cy = self._object_tile("catacombs")
        others = [
            obj.get("name") or obj.get("type")
            for tx, ty, obj in self.objects
            if (tx, ty) == (cx, cy) and obj.get("name") != "catacombs"
        ]
        self.assertEqual(others, [], f"catacombs tile ({cx},{cy}) also occupied by {others}")

    def test_catacombs_reachable_from_player_start(self):
        """The player must be able to reach a tile adjacent to the catacombs to
        destroy it (the underlying tile is steppable and at least one orthogonal
        neighbour is reachable from the StartEvent spawn)."""
        cx, cy = self._object_tile("catacombs")
        self.assertTrue(
            self._tile_steppable(cx, cy),
            f"catacombs underlying tile ({cx},{cy}) is not a steppable tile type",
        )
        reachable = self._reachable_tiles()
        adjacent = [
            (cx + dx, cy + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if (cx + dx, cy + dy) in reachable
        ]
        self.assertTrue(
            adjacent,
            f"no reachable tile adjacent to catacombs ({cx},{cy}); entrance is unreachable",
        )

    def test_catacombs_trigger_wiring_intact(self):
        """Exactly one onDestroy trigger targets 'catacombs', grants holyRelic, and
        marks the relic obtained for the Beren return chain."""
        occurrences = self.script.count('@trigger(context, "onDestroy", "catacombs")')
        self.assertEqual(occurrences, 1, "expected exactly one catacombs onDestroy trigger")
        # holyRelic is granted and the beren_chain state advances in the same script.
        self.assertIn('player.addItem("holyRelic")', self.script)
        self.assertIn("mark_relic_obtained", self.script)
        self.assertIn("holyRelic", self.config)


class TypeRegistrationCoverageAuditTest(unittest.TestCase):
    """Guards the exhaustive V_META registration audit (todo.txt: "add exhaustive audit
    to ensure every runtime-instantiable V_META type is covered by static or plugin
    registration")."""

    def _collected_validator(self):
        validator = ContentValidator(REPO_ROOT)
        validator._collect_engine_classes()
        validator._collect_plugin_classes()
        validator._load_type_registration_exclusions()
        return validator

    def _registered_classes(self, validator):
        return (
            validator.fallback_registered_classes
            | validator.static_registered_classes
            | validator.native_plugin_registered_classes
            | validator.python_registered_classes
        )

    def test_every_metadata_type_is_registered_or_excluded(self):
        validator = self._collected_validator()
        registered = self._registered_classes(validator)
        excluded = set(validator.registration_exclusions)

        # Sanity: the collectors actually found the reflected engine types and the
        # registration sources, so an empty-scan false pass cannot slip through.
        self.assertIn("CItem", validator.metadata_declared_classes)
        self.assertIn("CItem", registered)

        uncovered = sorted(validator.metadata_declared_classes - registered - excluded)
        self.assertEqual(
            [],
            uncovered,
            "V_META types neither registered nor excluded (register them via CTypes or "
            f"add an exclusion entry with a reason): {uncovered}",
        )

    def test_ccustomtrigger_is_excluded_not_registered(self):
        validator = self._collected_validator()
        self.assertIn("CCustomTrigger", validator.metadata_declared_classes)
        self.assertNotIn("CCustomTrigger", self._registered_classes(validator))
        self.assertIn("CCustomTrigger", validator.registration_exclusions)

    def test_audit_flags_metadata_type_without_registration_or_exclusion(self):
        validator = self._collected_validator()
        validator.metadata_declared_classes.add("CFakeUnregisteredType")
        validator.metadata_class_bases["CFakeUnregisteredType"] = "CGameObject"

        validator._validate_type_registration_coverage()

        flagged = [issue for issue in validator.issues if "CFakeUnregisteredType" in issue.message]
        self.assertEqual(1, len(flagged), [str(i) for i in validator.issues])
        self.assertEqual("scripts/type_registration_exclusions.json", flagged[0].path)
        self.assertEqual("exclusions", flagged[0].location)
        self.assertIn('extends "CGameObject"', flagged[0].message)

    def test_audit_ignores_registered_and_excluded_types(self):
        validator = self._collected_validator()
        validator._validate_type_registration_coverage()
        self.assertFalse([issue for issue in validator.issues if "CItem" in issue.message])
        self.assertFalse([issue for issue in validator.issues if '"CCustomTrigger"' in issue.message])

    def test_commented_registration_is_not_counted_as_registration(self):
        # A commented-out (runtime-disabled) registration must NOT be treated as a
        # live one; otherwise a reflected type whose only registration is commented
        # out passes the coverage audit and then fails at runtime when built by
        # name. iter_cpp_metadata_declarations already strips comments, so this
        # scan must too, or the two disagree.
        self.assertEqual(
            {"CFoo"}, iter_cpp_template_type_names("CTypes::register_type<CFoo, CBar>();", "register_type")
        )
        self.assertEqual(set(), iter_cpp_template_type_names("// CTypes::register_type<CFoo>();", "register_type"))
        self.assertEqual(
            set(),
            iter_cpp_template_type_names("/* CTypes::register_type<CFoo, CBar>(); */", "register_type"),
        )
        # A live registration next to a commented one still resolves to the live type only.
        mixed = "CTypes::register_type<CLive, CBase>();\n// CTypes::register_type<CDisabled, CBase>();\n"
        self.assertEqual({"CLive"}, iter_cpp_template_type_names(mixed, "register_type"))

    def test_single_argument_and_nested_wrapper_registrations_are_detected(self):
        # The first template argument is bounded by the matching top-level `>` or
        # `,`, honoring nested `<...>`. A single-argument (base-less) registration
        # and a nested wrapper must both be detected -- a plain `[^,;]` capture
        # swallowed the trailing `>()` and dropped these, so a future
        # `register_type<CNewRoot>()` would be falsely flagged as unregistered.
        def names(src):
            return iter_cpp_template_type_names(src, "register_type")

        self.assertEqual({"CGameObject"}, names("register_type<CGameObject>();"))
        self.assertEqual({"CRoot"}, names("CTypes::register_type<CRoot>(host);"))
        self.assertEqual({"CInner"}, names("register_type<CWrapper<CInner>>();"))
        self.assertEqual({"CInner"}, names("register_type<CWrapper<CInner>, CBase>();"))
        self.assertEqual({"CSpaced"}, names("register_type< CSpaced >();"))
        # Multi-argument detection is unchanged (first argument only).
        self.assertEqual({"CDerived"}, names("register_type<CDerived, CBase>();"))


if __name__ == "__main__":
    unittest.main()
