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
    ContentValidator,
    ScriptPropertyHygieneAllowance,
    classify_creature_templates,
    inventory_creature_overrides,
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
        write_json(
            root / "res/config/creature_races.json",
            {"humanRace": {"properties": {"creatureClass": {"ref": "warriorClass"}}}},
        )
        write_json(
            root / "res/config/creature_classes.json",
            {"warriorClass": {"properties": {"label": "Warrior"}}},
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

    def test_creature_race_valid_base_stats_actions_and_types_pass(self):
        root = self.make_fixture()
        self.write_creature_race_stats_fixture(root)
        self._write_creature_race(
            root,
            {
                "baseStats": {"strength": 5, "agility": 3, "mainStat": "strength"},
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
        self._write_creature_race(root, {"baseStats": {"strenght": 5}})

        issues = validate_repo(root)

        self.assertIssueContains(
            issues,
            "res/config/creature_races.json",
            "humanRace.properties.baseStats.strenght",
            '"strenght" is not a CStats property; expected one of agility, intelligence, mainStat, name, strength',
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


if __name__ == "__main__":
    unittest.main()
