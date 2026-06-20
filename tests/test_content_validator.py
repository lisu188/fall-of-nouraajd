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

from scripts.validate_content import ContentValidator, validate_repo


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

                class CPropertyBase {
                    V_META(CPropertyBase, CGameObject,
                            V_PROPERTY(CPropertyBase, std::set<std::shared_ptr<CItem>>, loot, getLoot, setLoot))
                };

                class CPropertyDerived {
                    V_META(CPropertyDerived, CPropertyBase,
                            V_PROPERTY(CPropertyDerived, int, count, getCount, setCount))
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
