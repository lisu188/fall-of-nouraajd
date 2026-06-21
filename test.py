# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2025-2026  Andrzej Lis
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
import concurrent.futures
import contextlib
import http.client
import io
import importlib
import importlib.util
import json
import os
import queue
import re
import select
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import types
from http import HTTPStatus
from pathlib import Path
import unittest

import game_simulation
import mcp
import quest_state

REPO_ROOT = Path(__file__).resolve().parent


def resolve_test_output_dir():
    output_dir = os.environ.get("GAME_TEST_OUTPUT_DIR")
    if not output_dir:
        return REPO_ROOT / "test"
    path = Path(output_dir)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


TEST_OUTPUT_DIR = resolve_test_output_dir()


def resolve_test_timings_file():
    timings_file = os.environ.get("GAME_TEST_TIMINGS_FILE")
    if not timings_file:
        return TEST_OUTPUT_DIR / "test-timings.json"
    path = Path(timings_file)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


TEST_TIMINGS_FILE = resolve_test_timings_file()
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
MCP_STDIO_TOOL_TIMEOUT_SECONDS = 10
MCP_STDIO_MAP_JSON_TIMEOUT_SECONDS = 60
MCP_STDIO_SHUTDOWN_TIMEOUT_SECONDS = 30
GAME_TEST_WORKER = os.environ.get("GAME_TEST_WORKER") == "1"
XVFB_GAMEPLAY_PARENT_TEST = "XvfbGameplayTest.test_keyboard_gameplay_under_xvfb"
VALID_TEST_SUITES = ("fast", "gameplay", "ui", "coverage-safe", "full")
FAST_TEST_PREFIXES = (
    "CoverageReportTest.",
    "PlayBootstrapTest.",
    "QuestStateHelperTest.",
    "SaveFixtureTest.",
    "TestRunnerSuiteTest.",
)
FAST_TEST_NAMES = {
    "McpServerTest.test_engine_call_resolves_handle_arguments_for_python_methods",
    "McpServerTest.test_engine_handle_call_rejects_private_methods",
    "McpServerTest.test_engine_handle_call_scopes_controller_access_to_players",
    "McpServerTest.test_http_notification_response_declares_empty_body",
    "McpServerTest.test_initialize_response_preserves_request_id",
    "McpServerTest.test_map_design_brief_rejects_path_traversal",
    "McpServerTest.test_serialize_result_lists_python_methods_for_handles",
    "McpServerTest.test_stdio_batch_handles_initialize_and_tool_listing",
    "PanelLayoutManifestTest.test_panel_layout_manifest_matches_panels_json",
}
GAMEPLAY_TEST_PREFIXES = (
    "ConsoleEventIsolationTest.",
    "ConsoleEventProcessTest.",
    "GameTest.",
    "McpServerTest.",
)
GAMEPLAY_EXCLUDED_TEST_NAMES = {
    "McpServerTest.test_http_notification_response_declares_empty_body",
}
COVERAGE_SAFE_EXCLUDED_TEST_NAMES = {
    "ConsoleEventIsolationTest.test_console_key_history_in_fresh_process",
    "GameTest.test_map_walkthroughs",
    "McpServerTest.test_stdio_map_walkthrough_multilevel",
    "McpServerTest.test_stdio_map_walkthrough_nouraajd",
    "McpServerTest.test_stdio_map_walkthrough_ritual",
    "McpServerTest.test_stdio_map_walkthrough_siege",
    "McpServerTest.test_stdio_map_walkthrough_test",
    "McpServerTest.test_stdio_scene_manager_map_transition_walkthrough",
}
SERIAL_TEST_NAMES = {
    "GameTest.test_load_saved_map_slot_name_does_not_override_object_type_configs",
    "GameTest.test_missing_save_resource_directory_lists_empty",
    XVFB_GAMEPLAY_PARENT_TEST,
}
SERIAL_TEST_PREFIXES = ("McpServerTest.test_stdio_map_walkthrough_",)
DEFAULT_TEST_DURATIONS = {
    "McpServerTest.test_stdio_map_walkthrough_multilevel": 25.0,
    "McpServerTest.test_stdio_map_walkthrough_nouraajd": 45.0,
    "McpServerTest.test_stdio_map_walkthrough_ritual": 45.0,
    "McpServerTest.test_stdio_map_walkthrough_siege": 30.0,
    "McpServerTest.test_stdio_map_walkthrough_test": 20.0,
    "McpServerTest.test_stdio_scene_manager_map_transition_walkthrough": 20.0,
    XVFB_GAMEPLAY_PARENT_TEST: 90.0,
    "GameTest.test_map_walkthrough_multilevel": 12.0,
    "GameTest.test_map_walkthrough_nouraajd": 25.0,
    "GameTest.test_map_walkthrough_ritual": 20.0,
    "GameTest.test_map_walkthrough_siege": 15.0,
    "GameTest.test_map_walkthrough_test": 10.0,
    "GameTest.test_multilevel_map_loads_authored_z_layers": 6.0,
    "GameTest.test_multilevel_map_player_uses_stairs_both_directions": 8.0,
    "GameTest.test_multilevel_map_stale_collision_cache_is_z_scoped": 6.0,
    "GameTest.test_multilevel_map_z_state_persists_after_save_load": 8.0,
    "GameTest.test_playthrough": 20.0,
    "GameTest.test_campaign_transitions_preserve_player_and_start_siege": 20.0,
    "GameTest.test_map_walkthroughs": 20.0,
    "GameTest.test_nouraajd_quest_state_machine": 14.0,
    "GameTest.test_quest_journal_shows_objectives_rewards_and_hints": 12.0,
    "GameTest.test_generated_tiled_map_exercises_loader_metadata_and_objects": 10.0,
    "GameTest.test_fights": 8.0,
    "GameTest.test_level": 8.0,
    "ConsoleEventIsolationTest.test_console_key_history_in_fresh_process": 6.0,
    "McpServerTest.test_stdio_handshake_and_tool_listing": 10.0,
    "McpServerTest.test_stdio_batch_handles_initialize_and_tool_listing": 8.0,
    "McpServerTest.test_map_design_brief_summarizes_selected_map_hooks": 6.0,
}


def parse_positive_int(value, name):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a positive integer, got: {value}") from None
    if parsed < 1:
        raise ValueError(f"{name} must be a positive integer, got: {value}")
    return parsed


def default_xvfb_jobs():
    cpu_count = os.cpu_count() or 1
    if os.name == "posix" and cpu_count > 1:
        return min(4, cpu_count)
    return 1


def parse_name_filter(value):
    if not value:
        return set()
    return {name.strip() for name in value.split(",") if name.strip()}


def unique_save_name(prefix):
    shard = os.environ.get("GAME_TEST_SHARD")
    shard_part = f"-{shard}" if shard else ""
    return f"{prefix}{shard_part}-{os.getpid()}-{time.time_ns()}"


SAVE_FORMAT = "fall-of-nouraajd-save"
SAVE_SCHEMA_VERSION = 1
SAVE_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "save_compatibility"


def save_primary_path(slot_name):
    return Path.cwd() / "save" / f"{slot_name}.json"


def save_backup_path(slot_name):
    return Path.cwd() / "save" / f"{slot_name}.json.bak"


def cleanup_save_slot(slot_name):
    primary = save_primary_path(slot_name)
    backup = save_backup_path(slot_name)
    primary.unlink(missing_ok=True)
    if backup.exists() and backup.is_dir():
        shutil.rmtree(backup)
    else:
        backup.unlink(missing_ok=True)
    if primary.parent.exists():
        for path in primary.parent.glob(f".{slot_name}.json.*.tmp"):
            path.unlink(missing_ok=True)


def save_temp_paths(slot_name):
    save_dir = Path.cwd() / "save"
    if not save_dir.exists():
        return []
    return list(save_dir.glob(f".{slot_name}.json.*.tmp"))


def save_snapshot(saved_document):
    if saved_document.get("format") == SAVE_FORMAT:
        return saved_document.get("snapshot", {})
    return saved_document


def assert_save_envelope(test_case, saved_document, map_name):
    test_case.assertEqual(SAVE_FORMAT, saved_document.get("format"))
    test_case.assertEqual(SAVE_SCHEMA_VERSION, saved_document.get("schemaVersion"))
    test_case.assertEqual(map_name, saved_document.get("mapName"))
    snapshot = saved_document.get("snapshot")
    test_case.assertIsInstance(snapshot, dict)
    test_case.assertEqual("CMap", snapshot.get("class"))
    test_case.assertEqual(map_name, snapshot.get("properties", {}).get("mapName"))
    return snapshot


IMMUTABLE_SAVE_FIXTURE_EXPECTATIONS = {
    "legacy_unversioned_test_map": {
        "primary": "legacy_unversioned_test_map.json",
        "summary": {
            "encoding": "legacy",
            "map": "test",
            "turn": 11,
            "description": "immutable legacy unversioned fixture",
            "player": {
                "class": "CPlayer",
                "name": "player",
                "typeId": "Warrior",
                "coords": [1, 2, 0],
                "activeQuests": [],
                "completedQuests": [],
                "items": [],
            },
            "questStates": {},
            "trueFlags": [],
            "numericProperties": {},
            "objects": [],
        },
    },
    "schema_v1_test_map": {
        "primary": "schema_v1_test_map.json",
        "summary": {
            "encoding": "versioned",
            "schemaVersion": 1,
            "map": "test",
            "turn": 12,
            "description": "immutable schema v1 fixture",
            "player": {
                "class": "CPlayer",
                "name": "player",
                "typeId": "Warrior",
                "coords": [2, 3, 0],
                "activeQuests": [],
                "completedQuests": [],
                "items": [],
            },
            "questStates": {},
            "trueFlags": [],
            "numericProperties": {},
            "objects": [],
        },
    },
    "invalid_primary_valid_backup": {
        "primary": "invalid_primary_valid_backup.json",
        "backup": "invalid_primary_valid_backup.json.bak",
        "primaryInvalidJson": True,
        "summary": {
            "encoding": "versioned",
            "schemaVersion": 1,
            "map": "test",
            "turn": 13,
            "description": "immutable backup recovery fixture",
            "player": {
                "class": "CPlayer",
                "name": "player",
                "typeId": "Warrior",
                "coords": [3, 4, 0],
                "activeQuests": [],
                "completedQuests": [],
                "items": [],
            },
            "questStates": {},
            "trueFlags": [],
            "numericProperties": {},
            "objects": [],
        },
    },
    "nouraajd_active_quests_v1": {
        "primary": "nouraajd_active_quests_v1.json",
        "summary": {
            "encoding": "versioned",
            "schemaVersion": 1,
            "map": "nouraajd",
            "turn": 77,
            "description": "immutable Nouraajd active quest fixture",
            "player": {
                "class": "CPlayer",
                "name": "player",
                "typeId": "Warrior",
                "coords": [43, 99, 0],
                "activeQuests": ["rolfQuest", "victorQuest"],
                "completedQuests": [],
                "items": [],
            },
            "questStates": {
                "amulet": "not_started",
                "beren_chain": "letter_pending",
                "main": "locked",
                "octobogz_contract": "not_started",
                "rolf": "awaiting_skull",
                "victor": "met_victor",
            },
            "trueFlags": [],
            "numericProperties": {},
            "objects": [],
        },
    },
    "nouraajd_runtime_spawned_quest_actors_v1": {
        "primary": "nouraajd_runtime_spawned_quest_actors_v1.json",
        "summary": {
            "encoding": "versioned",
            "schemaVersion": 1,
            "map": "nouraajd",
            "turn": 104,
            "description": "immutable Nouraajd runtime quest actor fixture",
            "player": {
                "class": "CPlayer",
                "name": "player",
                "typeId": "Warrior",
                "coords": [45, 100, 0],
                "activeQuests": ["amuletQuest", "victorQuest"],
                "completedQuests": [],
                "items": [],
            },
            "questStates": {
                "amulet": "active",
                "beren_chain": "letter_pending",
                "main": "locked",
                "octobogz_contract": "not_started",
                "rolf": "awaiting_skull",
                "victor": "encounter_active",
            },
            "trueFlags": ["VICTOR_COURTYARD_FOUND", "VICTOR_CULTISTS_SPAWNED"],
            "numericProperties": {"VICTOR_COURTYARD_TURN": 100},
            "objects": [
                {"name": "amuletGoblin", "typeId": "goblinThief"},
                {"name": "cultLeaderQuest", "typeId": "CultLeader"},
                {"name": "victorCultist1", "typeId": "Cultist"},
            ],
        },
    },
    "ritual_progression_v1": {
        "primary": "ritual_progression_v1.json",
        "summary": {
            "encoding": "versioned",
            "schemaVersion": 1,
            "map": "ritual",
            "turn": 39,
            "description": "immutable ritual progression fixture",
            "player": {
                "class": "CPlayer",
                "name": "player",
                "typeId": "Warrior",
                "coords": [3, 22, 0],
                "activeQuests": [
                    "destroyAnchorsQuest",
                    "finalResolutionQuest",
                    "rescueCaptiveQuest",
                    "ritualQuest",
                ],
                "completedQuests": [],
                "items": [],
            },
            "questStates": {},
            "trueFlags": ["anchors_destroyed", "leader_spawned", "ritual_initialized", "ritual_started"],
            "numericProperties": {"anchors_destroyed_count": 3, "ritual_countdown": 62},
            "objects": [{"name": "ritualLeader", "typeId": "ritualLeaderTemplate"}],
        },
    },
    "siege_progression_v1": {
        "primary": "siege_progression_v1.json",
        "summary": {
            "encoding": "versioned",
            "schemaVersion": 1,
            "map": "siege",
            "turn": 51,
            "description": "immutable siege progression fixture",
            "player": {
                "class": "CPlayer",
                "name": "player",
                "typeId": "Warrior",
                "coords": [12, 8, 0],
                "activeQuests": ["defendSiegeQuest"],
                "completedQuests": [],
                "items": ["magicWand"],
            },
            "questStates": {},
            "trueFlags": ["siege_initialized"],
            "numericProperties": {},
            "objects": [{"name": "spawnPoint1", "typeId": "SiegeSpawnPoint"}],
        },
    },
}


def fixture_document_snapshot(document):
    if document.get("format") == SAVE_FORMAT:
        return "versioned", document.get("snapshot", {})
    return "legacy", document


def fixture_object_type_id(obj):
    properties = obj.get("properties", {}) if isinstance(obj, dict) else {}
    return properties.get("typeId") or obj.get("ref") or obj.get("class")


def fixture_named_objects(snapshot):
    objects = []
    for obj in snapshot.get("properties", {}).get("objects", []):
        properties = obj.get("properties", {}) if isinstance(obj, dict) else {}
        name = properties.get("name")
        if name and name != "player":
            objects.append({"name": name, "typeId": fixture_object_type_id(obj)})
    return sorted(objects, key=lambda item: item["name"])


def fixture_player_summary(snapshot):
    for obj in snapshot.get("properties", {}).get("objects", []):
        properties = obj.get("properties", {}) if isinstance(obj, dict) else {}
        if obj.get("class") == "CPlayer" or properties.get("name") == "player":
            return {
                "class": obj.get("class") or obj.get("ref"),
                "name": properties.get("name"),
                "typeId": properties.get("typeId"),
                "coords": [properties.get("posx", 0), properties.get("posy", 0), properties.get("posz", 0)],
                "activeQuests": fixture_quest_ids(properties.get("quests", [])),
                "completedQuests": fixture_quest_ids(properties.get("completedQuests", [])),
                "items": fixture_item_ids(properties.get("items", [])),
            }
    raise AssertionError("Save fixture snapshot does not contain a canonical player object.")


def fixture_quest_ids(quests):
    quest_ids = []
    for quest in quests:
        if not isinstance(quest, dict):
            continue
        properties = quest.get("properties", {})
        quest_ids.append(properties.get("typeId") or properties.get("name") or quest.get("ref") or quest.get("class"))
    return sorted(quest_id for quest_id in quest_ids if quest_id)


def fixture_item_ids(items):
    item_ids = []
    for item in items:
        if not isinstance(item, dict):
            continue
        properties = item.get("properties", {})
        item_ids.append(properties.get("typeId") or properties.get("name") or item.get("ref") or item.get("class"))
    return sorted(item_id for item_id in item_ids if item_id)


def save_fixture_summary(document):
    encoding, snapshot = fixture_document_snapshot(document)
    properties = snapshot.get("properties", {})
    summary = {
        "encoding": encoding,
        "map": properties.get("mapName"),
        "turn": properties.get("turn", 0),
        "description": properties.get("description", ""),
        "player": fixture_player_summary(snapshot),
        "questStates": {
            key.removeprefix("quest_state_"): value
            for key, value in sorted(properties.items())
            if key.startswith("quest_state_")
        },
        "trueFlags": sorted(
            key for key, value in properties.items() if isinstance(value, bool) and value and key != "canStep"
        ),
        "numericProperties": {
            key: value
            for key, value in sorted(properties.items())
            if key
            in {
                "VICTOR_COURTYARD_TURN",
                "anchors_destroyed_count",
                "ritual_countdown",
            }
        },
        "objects": fixture_named_objects(snapshot),
    }
    if encoding == "versioned":
        summary["schemaVersion"] = document.get("schemaVersion")
    return summary


class SaveFixtureTest(unittest.TestCase):
    maxDiff = None

    def test_immutable_save_fixture_summaries_match_expected(self):
        self.assertTrue(SAVE_FIXTURE_DIR.is_dir(), f"Missing fixture directory: {SAVE_FIXTURE_DIR}")
        expected_files = set()
        for expected in IMMUTABLE_SAVE_FIXTURE_EXPECTATIONS.values():
            expected_files.add(expected["primary"])
            if expected.get("backup"):
                expected_files.add(expected["backup"])

        actual_files = {path.name for path in SAVE_FIXTURE_DIR.iterdir() if path.is_file()}
        self.assertEqual(expected_files, actual_files)

        for fixture_name, expected in IMMUTABLE_SAVE_FIXTURE_EXPECTATIONS.items():
            primary = SAVE_FIXTURE_DIR / expected["primary"]
            self.assertTrue(primary.is_file(), fixture_name)
            if expected.get("primaryInvalidJson"):
                with self.assertRaises(json.JSONDecodeError, msg=fixture_name):
                    json.loads(primary.read_text(encoding="utf-8"))
                document_path = SAVE_FIXTURE_DIR / expected["backup"]
            else:
                document_path = primary

            document = json.loads(document_path.read_text(encoding="utf-8"))
            if document.get("format") == SAVE_FORMAT:
                assert_save_envelope(self, document, expected["summary"]["map"])
            self.assertEqual(expected["summary"], save_fixture_summary(document), fixture_name)


class ProgressTextTestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.showAll = False
        self.dots = False
        self.total_tests = 0
        self.test_index = 0
        self._test_start_times = {}
        self.test_durations = {}

    def startTest(self, test):
        self.test_index += 1
        self._test_start_times[id(test)] = time.monotonic()
        self._write_progress(test, "start")
        super().startTest(test)

    def addSuccess(self, test):
        unittest.TestResult.addSuccess(self, test)
        duration = self._duration(test)
        self._record_duration(test, duration)
        self._write_progress(test, "ok", duration)

    def addFailure(self, test, err):
        unittest.TestResult.addFailure(self, test, err)
        duration = self._duration(test)
        self._record_duration(test, duration)
        self._write_progress(test, "FAIL", duration)

    def addError(self, test, err):
        unittest.TestResult.addError(self, test, err)
        duration = self._duration(test)
        self._record_duration(test, duration)
        self._write_progress(test, "ERROR", duration)

    def addSkip(self, test, reason):
        unittest.TestResult.addSkip(self, test, reason)
        duration = self._duration(test)
        self._record_duration(test, duration)
        self._write_progress(test, "skip", duration, reason)

    def addExpectedFailure(self, test, err):
        unittest.TestResult.addExpectedFailure(self, test, err)
        duration = self._duration(test)
        self._record_duration(test, duration)
        self._write_progress(test, "expected-failure", duration)

    def addUnexpectedSuccess(self, test):
        unittest.TestResult.addUnexpectedSuccess(self, test)
        duration = self._duration(test)
        self._record_duration(test, duration)
        self._write_progress(test, "UNEXPECTED-SUCCESS", duration)

    def _duration(self, test):
        started_at = self._test_start_times.pop(id(test), None)
        if started_at is None:
            return None
        return time.monotonic() - started_at

    def _record_duration(self, test, duration):
        if duration is not None:
            self.test_durations[self._subprocess_name(test)] = duration

    def _write_progress(self, test, status, duration=None, detail=None):
        total = self.total_tests or "?"
        test_name = self._test_name(test)
        duration_text = "" if duration is None else f" {duration:.3f}s"
        detail_text = "" if detail is None else f" {detail}"
        self.stream.write(f"[test {self.test_index}/{total} {status}{duration_text}] {test_name}{detail_text}\n")
        self.stream.flush()

    @staticmethod
    def _test_name(test):
        test_id = test.id()
        if test_id.startswith("__main__."):
            return f"test.{test_id[len('__main__.'):]}"
        return test_id

    @staticmethod
    def _subprocess_name(test):
        test_id = test.id()
        for prefix in (f"{__name__}.", "__main__."):
            if test_id.startswith(prefix):
                return test_id[len(prefix) :]
        return test_id


class ProgressTextTestRunner(unittest.TextTestRunner):
    resultclass = ProgressTextTestResult

    def run(self, test):
        self._total_tests = test.countTestCases()
        result = super().run(test)
        write_test_timings(TEST_TIMINGS_FILE, result.test_durations)
        return result

    def _makeResult(self):
        result = super()._makeResult()
        result.total_tests = getattr(self, "_total_tests", 0)
        return result


def load_game_module():
    game = importlib.import_module("game")
    builtins.game = game
    return game


def event_names(trace):
    return [record.get("event") for record in trace]


def trace_tail_from_file(path, limit=80):
    path = Path(path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [json.loads(line) for line in lines[-limit:] if line.strip()]


def make_temp_log_path():
    fd, path = tempfile.mkstemp(prefix="game-log-", suffix=".txt")
    os.close(fd)
    return Path(path)


def load_type_registration_exclusions():
    path = REPO_ROOT / "scripts" / "type_registration_exclusions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    exclusions = {}
    for entry in data.get("exclusions", []):
        class_name = entry.get("className")
        if not isinstance(class_name, str) or not class_name:
            continue
        exclusions[class_name] = {
            "reason": entry.get("reason", ""),
            "ownerModule": entry.get("ownerModule", ""),
        }
    return exclusions


def iter_global_runtime_config_files():
    config_root = REPO_ROOT / "res" / "config"
    if config_root.exists():
        yield from sorted(config_root.glob("*.json"))


def iter_map_runtime_config_files():
    maps_root = REPO_ROOT / "res" / "maps"
    if maps_root.exists():
        yield from sorted(maps_root.glob("*/config.json"))


def iter_runtime_config_files():
    yield from iter_global_runtime_config_files()
    yield from iter_map_runtime_config_files()


def load_runtime_config_entry_records(path, category):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
    return [
        {
            "category": category,
            "config": value,
            "owner": path.relative_to(REPO_ROOT).as_posix(),
            "typeId": type_id,
        }
        for type_id, value in sorted(data.items())
        if isinstance(value, dict) and ("class" in value or "ref" in value)
    ]


def load_global_runtime_config_entry_records():
    records = []
    for path in iter_global_runtime_config_files():
        records.extend(load_runtime_config_entry_records(path, "global-config"))
    return records


def load_map_runtime_config_entry_records(map_name):
    path = REPO_ROOT / "res" / "maps" / map_name / "config.json"
    return load_runtime_config_entry_records(path, f"map-config:{map_name}")


def runtime_config_values(records):
    return {record["typeId"]: record["config"] for record in records}


def resolve_runtime_config_class(type_id, visible_configs, seen=None):
    seen = seen or set()
    if type_id in seen:
        return ""
    value = visible_configs.get(type_id)
    if not isinstance(value, dict):
        return type_id if type_id.startswith("C") else ""
    class_name = value.get("class")
    if isinstance(class_name, str):
        return class_name
    ref = value.get("ref")
    if isinstance(ref, str):
        return resolve_runtime_config_class(ref, visible_configs, seen | {type_id})
    return ""


def resolve_runtime_config_name(type_id, visible_configs, seen=None):
    seen = seen or set()
    if type_id in seen:
        return None
    value = visible_configs.get(type_id)
    if not isinstance(value, dict):
        return None
    properties = value.get("properties")
    if isinstance(properties, dict) and isinstance(properties.get("name"), str):
        return properties["name"]
    ref = value.get("ref")
    if isinstance(ref, str):
        return resolve_runtime_config_name(ref, visible_configs, seen | {type_id})
    return None


RUNTIME_CONFIG_INHERITANCE_BASES = (
    "CGameObject",
    "CMapObject",
    "CBuilding",
    "CEvent",
    "CInteraction",
    "CDamage",
    "CStats",
    "CTile",
    "CItem",
    "CWeapon",
    "CSmallWeapon",
    "CArmor",
    "CPotion",
    "CScroll",
    "CMarket",
    "CDialog",
    "CDialogOption",
    "CDialogState",
    "CTrigger",
    "CQuest",
    "CController",
    "CFightController",
    "CCreature",
    "CPlayer",
    "CGameGraphicsObject",
    "CGui",
    "CAnimation",
    "CGamePanel",
    "CListView",
)


def runtime_config_inheritance_matches(handler, type_id, expected_class, subtype_cache):
    bases = []
    if expected_class:
        bases.append(expected_class)
    bases.extend(RUNTIME_CONFIG_INHERITANCE_BASES)
    matches = []
    for base in dict.fromkeys(bases):
        if not base:
            continue
        if base not in subtype_cache:
            try:
                subtype_cache[base] = set(handler.getAllSubTypes(base))
            except Exception:
                subtype_cache[base] = set()
        if type_id in subtype_cache[base]:
            matches.append(base)
    return matches


def check_runtime_config_entry_creation(g, records, visible_configs):
    handler = g.getObjectHandler()
    subtype_cache = {}
    created = []
    failed = []
    for record in records:
        type_id = record["typeId"]
        expected_class = resolve_runtime_config_class(type_id, visible_configs)
        expected_name = resolve_runtime_config_name(type_id, visible_configs)
        details = {
            "category": record["category"],
            "expectedClass": expected_class,
            "expectedName": expected_name,
            "owner": record["owner"],
            "typeId": type_id,
        }
        try:
            obj = g.createObject(type_id)
        except Exception as exc:
            failed.append({**details, "errors": [f"{type(exc).__name__}: {exc}"]})
            continue
        if obj is None:
            failed.append({**details, "errors": ["createObject returned None"]})
            continue

        actual = {
            "class": obj.getType(),
            "inheritance": runtime_config_inheritance_matches(handler, type_id, expected_class, subtype_cache),
            "name": obj.getName(),
            "typeId": obj.getTypeId(),
        }
        errors = []
        if not expected_class:
            errors.append("expected class could not be resolved from class/ref chain")
        elif actual["class"] != expected_class:
            errors.append(f"created class {actual['class']!r} did not match expected {expected_class!r}")
        if actual["typeId"] != type_id:
            errors.append(f"created typeId {actual['typeId']!r} did not match requested {type_id!r}")
        if not actual["name"]:
            errors.append("created object name was empty")
        if expected_name is not None and actual["name"] != expected_name:
            errors.append(f"created name {actual['name']!r} did not match configured {expected_name!r}")
        if not actual["inheritance"]:
            errors.append(f"{type_id!r} was not reported as a subtype of any known runtime base")
        if expected_class in RUNTIME_CONFIG_INHERITANCE_BASES and expected_class not in actual["inheritance"]:
            errors.append(f"{type_id!r} was not reported as a subtype of expected class {expected_class!r}")

        created.append({**details, "actual": actual})
        if errors:
            failed.append({**details, "actual": actual, "errors": errors})
    return created, failed


def load_runtime_config_type_metadata():
    configs = {}
    for path in iter_runtime_config_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for type_id, value in data.items():
            if isinstance(value, dict) and ("class" in value or "ref" in value):
                configs[type_id] = (value, path)

    def resolve_class(type_id, seen=None):
        seen = seen or set()
        if type_id in seen:
            return ""
        entry = configs.get(type_id)
        if not entry:
            return type_id if type_id.startswith("C") else ""
        value, _path = entry
        class_name = value.get("class")
        if isinstance(class_name, str):
            return class_name
        ref = value.get("ref")
        if isinstance(ref, str):
            return resolve_class(ref, seen | {type_id})
        return ""

    metadata = {}
    for type_id, (_value, path) in configs.items():
        if path.parent == REPO_ROOT / "res" / "config":
            category = "global-config"
        else:
            category = f"map-config:{path.parent.name}"
        metadata[type_id] = {
            "category": category,
            "owner": path.relative_to(REPO_ROOT).as_posix(),
            "className": resolve_class(type_id),
        }
    return metadata


def load_registered_class_categories():
    sources = {
        "core-registration": REPO_ROOT / "src" / "core" / "CCoreTypeRegistration.cpp",
        "handler-registration": REPO_ROOT / "src" / "handler" / "CHandlerTypeRegistration.cpp",
        "object-registration": REPO_ROOT / "src" / "object" / "CObjectTypeRegistration.cpp",
        "gui-registration": REPO_ROOT / "src" / "gui" / "CGuiTypeRegistration.cpp",
        "animation-registration": REPO_ROOT / "src" / "gui" / "CAnimationTypeRegistration.cpp",
        "widget-registration": REPO_ROOT / "src" / "gui" / "object" / "CGuiWidgetTypeRegistration.cpp",
        "panel-registration": REPO_ROOT / "src" / "gui" / "panel" / "CGuiPanelTypeRegistration.cpp",
        "native-plugin-registration": REPO_ROOT / "src" / "plugin" / "NativePlugin.cpp",
    }
    categories = {}
    pattern = re.compile(r"register_type(?:_metadata)?<([^>;]+?)>")
    for category, path in sources.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            class_name = match.group(1).split(",", 1)[0].strip()
            if class_name.startswith("CWrapper<") or not class_name:
                continue
            categories.setdefault(
                class_name,
                {
                    "category": category,
                    "owner": path.relative_to(REPO_ROOT).as_posix(),
                    "className": class_name,
                },
            )
    return categories


def runtime_type_details(type_id, config_metadata, class_categories):
    if type_id in config_metadata:
        details = dict(config_metadata[type_id])
    elif type_id in class_categories:
        details = dict(class_categories[type_id])
    else:
        details = {
            "category": "runtime-registration",
            "owner": "CObjectHandler.registerType",
            "className": type_id if type_id.startswith("C") else "",
        }
    details["typeId"] = type_id
    return details


def game_test(f):
    def wrapper(self):
        n = f.__name__.split("test_")[1]
        TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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


def pump_event_loop_until(predicate, *, timeout=1.0, min_iterations=1):
    game = load_game_module()
    deadline = time.monotonic() + timeout
    iterations = 0
    while True:
        game.event_loop.instance().run()
        iterations += 1
        try:
            ready = predicate()
        except Exception:
            ready = False
        if iterations >= min_iterations and ready:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.001)


SDL_KEYDOWN = 0x300
SDL_KEYUP = 0x301
SDL_QUIT = 0x100
SDL_WINDOWEVENT = 0x200
SDL_WINDOWEVENT_SIZE_CHANGED = 0x06
SDL_INIT_EVENTS = 0x00004000
SDL_MOUSEMOTION = 0x400
SDL_MOUSEBUTTONDOWN = 0x401
SDL_MOUSEBUTTONUP = 0x402
SDL_PRESSED = 1
SDL_RELEASED = 0
SDL_SCANCODE_MASK = 1 << 30
SDLK_BACKSPACE = 8
SDLK_TAB = 9
SDLK_RETURN = 13
SDLK_DOWN = 1073741905
SDLK_UP = 1073741906
SDL_BUTTON_LEFT = 1
SDL_BUTTON_RIGHT = 3
SDL_PIXELFORMAT_RGBA32 = 376840196

GUI_WIDTH = 1920
GUI_HEIGHT = 1080
GUI_TILE_SIZE = 50
MINIMAP_RECT = (1700, 820, 220, 220)
MINIMAP_PLAYER_RGB = (255, 255, 0)
MINIMAP_VIEWPORT_RGB = (255, 255, 255)
ROOT_800_600 = (560, 240, 800, 600)
ROOT_400_300 = (760, 390, 400, 300)
ROOT_SELECTION_BASE = (810, 390, 300, 300)
PANEL_LAYOUT_CASES = {
    "characterPanel": {
        "kind": "panel",
        "class": "CGameCharacterPanel",
        "root": ROOT_800_600,
        "tests": ("test_text_centric_panel_layouts",),
    },
    "creatureView": {
        "kind": "nested",
        "class": "CCreatureView",
        "parent": "fightPanel",
        "tests": ("test_fight_panel_and_nested_views_layout",),
    },
    "questionPanel": {
        "kind": "panel",
        "class": "CGameQuestionPanel",
        "root": ROOT_400_300,
        "tests": ("test_choice_panel_layouts_and_hitboxes",),
    },
    "fightPanel": {
        "kind": "panel",
        "class": "CGameFightPanel",
        "root": ROOT_800_600,
        "tests": ("test_fight_panel_and_nested_views_layout",),
    },
    "selectionPanel": {
        "kind": "panel",
        "class": "CGamePanel",
        "root": ROOT_SELECTION_BASE,
        "tests": ("test_choice_panel_layouts_and_hitboxes",),
    },
    "infoPanel": {
        "kind": "panel",
        "class": "CGameTextPanel",
        "root": ROOT_400_300,
        "tests": ("test_text_centric_panel_layouts", "test_panel_harness_info_artifacts"),
    },
    "inventoryPanel": {
        "kind": "panel",
        "class": "CGameInventoryPanel",
        "root": ROOT_800_600,
        "tests": ("test_inventory_loot_trade_list_layouts", "test_all_list_views_capacity_paging_and_shrink"),
    },
    "questPanel": {
        "kind": "panel",
        "class": "CGameQuestPanel",
        "root": ROOT_800_600,
        "tests": ("test_text_centric_panel_layouts",),
    },
    "statsView": {
        "kind": "nested",
        "class": "CStatsGraphicsObject",
        "parent": "fightPanel",
        "tests": ("test_fight_panel_and_nested_views_layout",),
    },
    "lootPanel": {
        "kind": "panel",
        "class": "CGameLootPanel",
        "root": ROOT_400_300,
        "tests": ("test_inventory_loot_trade_list_layouts", "test_all_list_views_capacity_paging_and_shrink"),
    },
    "textPanel": {
        "kind": "panel",
        "class": "CGameTextPanel",
        "root": ROOT_800_600,
        "tests": ("test_text_centric_panel_layouts",),
    },
    "tradePanel": {
        "kind": "panel",
        "class": "CGameTradePanel",
        "root": ROOT_800_600,
        "tests": ("test_inventory_loot_trade_list_layouts", "test_all_list_views_capacity_paging_and_shrink"),
    },
    "dialogPanel": {
        "kind": "panel",
        "class": "CGameDialogPanel",
        "root": ROOT_800_600,
        "tests": ("test_choice_panel_layouts_and_hitboxes",),
    },
}
COMBAT_STALE_LOOP_TIMEOUT_SECONDS = 5.0 if os.environ.get("GAME_COVERAGE_RUN") == "1" else 2.0
XVFB_GAMEPLAY_CHILD_TIMEOUT = 300 if os.environ.get("GAME_COVERAGE_RUN") == "1" else 90
XVFB_GAMEPLAY_CHILD_TESTS = (
    "test_keyboard_input_moves_player",
    "test_mouse_click_moves_player",
    "test_window_resize_event_updates_gui_dimensions",
    "test_screenshot_readback_has_rendered_pixels",
    "test_screenshot_minimap_has_rendered_pixels",
    "test_screenshot_after_keyboard_move_has_rendered_pixels",
    "test_screenshot_after_mouse_move_has_rendered_pixels",
    "test_screenshot_after_save_hotkey_has_rendered_pixels",
    "test_screenshot_after_wait_hotkey_has_rendered_pixels",
    "test_screenshot_character_panel_has_rendered_pixels",
    "test_screenshot_info_panel_has_rendered_pixels",
    "test_screenshot_inventory_equipped_selection_has_rendered_pixels",
    "test_screenshot_inventory_item_selection_has_rendered_pixels",
    "test_screenshot_inventory_panel_has_rendered_pixels",
    "test_inventory_drag_release_outside_source_equips_item",
    "test_inventory_preselected_drag_release_equips_item",
    "test_inventory_drag_rejects_invalid_equipment_slot",
    "test_inventory_drag_unequips_to_inventory",
    "test_inventory_drag_quest_item_rejection",
    "test_inventory_equipped_selection_resets_inventory_selection",
    "test_inventory_quest_item_selection_is_ignored",
    "test_fight_quest_item_selection_is_ignored",
    "test_screenshot_question_panel_has_rendered_pixels",
    "test_screenshot_quest_panel_with_active_quest_has_rendered_pixels",
    "test_panel_harness_info_artifacts",
    "test_all_panel_root_layout_contracts",
    "test_all_top_level_panels_block_outside_map_clicks",
    "test_text_centric_panel_layouts",
    "test_choice_panel_layouts_and_hitboxes",
    "test_inventory_loot_trade_list_layouts",
    "test_fight_panel_and_nested_views_layout",
    "test_all_list_views_capacity_paging_and_shrink",
    "test_full_nouraajd_quest_walkthrough_ui",
    "test_sidebar_mouse_opens_inventory_until_hotkey_closes_it",
    "test_save_hotkey_writes_loadable_map",
)
XVFB_SAVE_MUTATING_CHILD_TESTS = {
    "test_screenshot_after_save_hotkey_has_rendered_pixels",
    "test_save_hotkey_writes_loadable_map",
}
XVFB_LONG_CHILD_TESTS = {
    "test_full_nouraajd_quest_walkthrough_ui",
}
XVFB_BATCHABLE_CHILD_TESTS = {
    "test_screenshot_readback_has_rendered_pixels",
    "test_screenshot_minimap_has_rendered_pixels",
    "test_screenshot_character_panel_has_rendered_pixels",
    "test_screenshot_info_panel_has_rendered_pixels",
    "test_screenshot_inventory_panel_has_rendered_pixels",
    "test_window_resize_event_updates_gui_dimensions",
    "test_screenshot_question_panel_has_rendered_pixels",
    "test_screenshot_quest_panel_with_active_quest_has_rendered_pixels",
    "test_panel_harness_info_artifacts",
    "test_all_panel_root_layout_contracts",
}
XVFB_GAMEPLAY_CHILD_DURATION_HINTS = {
    "test_full_nouraajd_quest_walkthrough_ui": 90,
    "test_choice_panel_layouts_and_hitboxes": 12,
    "test_inventory_loot_trade_list_layouts": 12,
    "test_fight_panel_and_nested_views_layout": 12,
    "test_all_list_views_capacity_paging_and_shrink": 12,
    "test_text_centric_panel_layouts": 10,
    "test_all_top_level_panels_block_outside_map_clicks": 45,
    "test_screenshot_after_save_hotkey_has_rendered_pixels": 8,
    "test_save_hotkey_writes_loadable_map": 8,
    "test_screenshot_minimap_has_rendered_pixels": 6,
    "test_screenshot_inventory_equipped_selection_has_rendered_pixels": 6,
    "test_screenshot_inventory_item_selection_has_rendered_pixels": 6,
    "test_inventory_drag_release_outside_source_equips_item": 6,
    "test_inventory_preselected_drag_release_equips_item": 6,
    "test_inventory_drag_rejects_invalid_equipment_slot": 6,
    "test_inventory_drag_unequips_to_inventory": 6,
    "test_inventory_drag_quest_item_rejection": 6,
    "test_inventory_equipped_selection_resets_inventory_selection": 6,
    "test_inventory_quest_item_selection_is_ignored": 6,
    "test_fight_quest_item_selection_is_ignored": 6,
}
NOURAAJD_QUEST_LOG_SCREENSHOT_CHECKPOINTS = {
    "xvfb_nouraajd_quest_log_rolf_initial",
    "xvfb_nouraajd_quest_log_rolf_completed_main_active",
    "xvfb_nouraajd_quest_log_deliver_letter_active",
    "xvfb_nouraajd_quest_log_beren_cleanse_active",
    "xvfb_nouraajd_quest_log_victor_encounter_active",
    "xvfb_nouraajd_quest_log_amulet_active",
    "xvfb_nouraajd_quest_log_amulet_completed",
    "xvfb_nouraajd_quest_log_all_quests_completed",
}

NOURAAJD_QUEST_DESCRIPTIONS = {
    "rolfQuest": "Unravel the fate of Sergeant Rolf.",
    "mainQuest": "Vanquish the Dreaded Gooby",
    "deliverLetterQuest": "Bring Mayor Irvin's letter to Father Beren",
    "retrieveRelicQuest": "Recover the holy relic from the catacombs",
    "cleanseCaveQuest": "Use the relic to cleanse the OctoBogz cave",
    "octoBogzQuest": "Clear the OctoBogz from the cave east of Nouraajd.",
    "victorQuest": "Find Victor's daughter by following tavern and town-hall clues to the courtyard.",
    "amuletQuest": "Find the stolen amulet for the old woman.",
}
NOURAAJD_QUEST_REWARDS = {
    "rolfQuest": "Starts the Gooby hunt.",
    "mainQuest": "200 gold from relieved townsfolk.",
    "deliverLetterQuest": "Unlocks scribe-desk scroll crafting.",
    "retrieveRelicQuest": "Unlocks stronger alchemy recipes.",
    "cleanseCaveQuest": "Opens the road to the ritual chapel.",
    "octoBogzQuest": "1000 gold and the Shadow Blade.",
    "victorQuest": (
        "500 gold, healing, and one-time access to buy Victor's remaining potions "
        "if you reach the courtyard in time."
    ),
    "amuletQuest": "50 gold.",
}


def load_sdl_library():
    import ctypes
    import ctypes.util

    library_names = [ctypes.util.find_library("SDL2")]
    for extension_dir in extension_dirs:
        library_names.append(extension_dir / "SDL2.dll")
    library_names.extend(
        [
            build_dir / "vcpkg_installed" / "x64-windows" / "bin" / "SDL2.dll",
            "SDL2.dll",
            "libSDL2-2.0.so.0",
            "libSDL2.so",
        ]
    )

    for library_name in library_names:
        if not library_name:
            continue
        try:
            return ctypes.CDLL(str(library_name))
        except OSError:
            continue
    raise AssertionError("Could not load SDL2 for gameplay event injection.")


def sdl_x11_video_driver_available():
    child_env = {
        "SDL_VIDEODRIVER": "x11",
        "SDL_AUDIODRIVER": "dummy",
        "SDL_RENDER_DRIVER": "software",
        "LIBGL_ALWAYS_SOFTWARE": "1",
    }
    wrapper_env = os.environ.copy()
    for key in child_env:
        wrapper_env.pop(key, None)
    script = r"""
import ctypes
import ctypes.util
import sys

for library_name in (ctypes.util.find_library("SDL2"), "libSDL2-2.0.so.0", "libSDL2.so"):
    if not library_name:
        continue
    try:
        sdl = ctypes.CDLL(library_name)
        break
    except OSError:
        pass
else:
    sys.stderr.write("Could not load SDL2.")
    sys.exit(1)

sdl.SDL_Init.argtypes = [ctypes.c_uint32]
sdl.SDL_Init.restype = ctypes.c_int
sdl.SDL_GetError.restype = ctypes.c_char_p
if sdl.SDL_Init(0x20) != 0:
    error = sdl.SDL_GetError()
    sys.stderr.write(error.decode("utf-8", errors="replace") if error else "SDL_Init failed.")
    sys.exit(1)
sdl.SDL_Quit()
"""
    try:
        completed = subprocess.run(
            [
                "xvfb-run",
                "-a",
                "--server-args=-screen 0 1920x1080x24",
                "env",
                *[f"{key}={value}" for key, value in sorted(child_env.items())],
                sys.executable,
                "-c",
                script,
            ],
            cwd=REPO_ROOT,
            env=wrapper_env,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return False, "SDL x11 initialization under xvfb timed out."
    if completed.returncode == 0:
        return True, ""
    message = (completed.stderr or completed.stdout or "SDL x11 initialization under xvfb failed.").strip()
    return False, message


def focused_sdl_window():
    import ctypes

    sdl = load_sdl_library()
    sdl.SDL_GetKeyboardFocus.restype = ctypes.c_void_p
    sdl.SDL_GetMouseFocus.restype = ctypes.c_void_p
    return sdl.SDL_GetKeyboardFocus() or sdl.SDL_GetMouseFocus()


def push_sdl_key_event(keycode, scancode, event_type=SDL_KEYDOWN):
    import ctypes

    class SDL_Keysym(ctypes.Structure):
        _fields_ = [
            ("scancode", ctypes.c_int),
            ("sym", ctypes.c_int),
            ("mod", ctypes.c_uint16),
            ("unused", ctypes.c_uint32),
        ]

    class SDL_KeyboardEvent(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_uint32),
            ("timestamp", ctypes.c_uint32),
            ("windowID", ctypes.c_uint32),
            ("state", ctypes.c_uint8),
            ("repeat", ctypes.c_uint8),
            ("padding2", ctypes.c_uint8),
            ("padding3", ctypes.c_uint8),
            ("keysym", SDL_Keysym),
        ]

    class SDL_Event(ctypes.Union):
        _fields_ = [
            ("type", ctypes.c_uint32),
            ("key", SDL_KeyboardEvent),
            ("padding", ctypes.c_uint8 * 56),
        ]

    sdl = load_sdl_library()
    event = SDL_Event()
    event.type = event_type
    event.key.type = event_type
    event.key.state = SDL_PRESSED if event_type == SDL_KEYDOWN else SDL_RELEASED
    event.key.repeat = 0
    event.key.keysym.scancode = scancode
    event.key.keysym.sym = keycode

    sdl.SDL_GetWindowID.argtypes = [ctypes.c_void_p]
    sdl.SDL_GetWindowID.restype = ctypes.c_uint32
    focused_window = focused_sdl_window()
    if focused_window:
        event.key.windowID = sdl.SDL_GetWindowID(focused_window)

    sdl.SDL_PushEvent.argtypes = [ctypes.POINTER(SDL_Event)]
    sdl.SDL_PushEvent.restype = ctypes.c_int
    pushed = sdl.SDL_PushEvent(ctypes.byref(event))
    if pushed != 1:
        raise AssertionError(f"SDL_PushEvent returned {pushed}.")


def push_sdl_mouse_button_event(x, y, button=SDL_BUTTON_LEFT, event_type=SDL_MOUSEBUTTONDOWN):
    import ctypes

    class SDL_MouseButtonEvent(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_uint32),
            ("timestamp", ctypes.c_uint32),
            ("windowID", ctypes.c_uint32),
            ("which", ctypes.c_uint32),
            ("button", ctypes.c_uint8),
            ("state", ctypes.c_uint8),
            ("clicks", ctypes.c_uint8),
            ("padding1", ctypes.c_uint8),
            ("x", ctypes.c_int32),
            ("y", ctypes.c_int32),
        ]

    class SDL_Event(ctypes.Union):
        _fields_ = [
            ("type", ctypes.c_uint32),
            ("button", SDL_MouseButtonEvent),
            ("padding", ctypes.c_uint8 * 56),
        ]

    sdl = load_sdl_library()
    event = SDL_Event()
    event.type = event_type
    event.button.type = event_type
    event.button.button = button
    event.button.state = SDL_PRESSED if event_type == SDL_MOUSEBUTTONDOWN else SDL_RELEASED
    event.button.clicks = 1
    event.button.x = x
    event.button.y = y

    sdl.SDL_GetWindowID.argtypes = [ctypes.c_void_p]
    sdl.SDL_GetWindowID.restype = ctypes.c_uint32
    focused_window = focused_sdl_window()
    if focused_window:
        event.button.windowID = sdl.SDL_GetWindowID(focused_window)

    sdl.SDL_PushEvent.argtypes = [ctypes.POINTER(SDL_Event)]
    sdl.SDL_PushEvent.restype = ctypes.c_int
    pushed = sdl.SDL_PushEvent(ctypes.byref(event))
    if pushed != 1:
        raise AssertionError(f"SDL_PushEvent returned {pushed}.")


def push_sdl_mouse_motion_event(x, y, xrel=0, yrel=0):
    import ctypes

    class SDL_MouseMotionEvent(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_uint32),
            ("timestamp", ctypes.c_uint32),
            ("windowID", ctypes.c_uint32),
            ("which", ctypes.c_uint32),
            ("state", ctypes.c_uint32),
            ("x", ctypes.c_int32),
            ("y", ctypes.c_int32),
            ("xrel", ctypes.c_int32),
            ("yrel", ctypes.c_int32),
        ]

    class SDL_Event(ctypes.Union):
        _fields_ = [
            ("type", ctypes.c_uint32),
            ("motion", SDL_MouseMotionEvent),
            ("padding", ctypes.c_uint8 * 56),
        ]

    sdl = load_sdl_library()
    event = SDL_Event()
    event.type = SDL_MOUSEMOTION
    event.motion.type = SDL_MOUSEMOTION
    event.motion.state = 1 << (SDL_BUTTON_LEFT - 1)
    event.motion.x = x
    event.motion.y = y
    event.motion.xrel = xrel
    event.motion.yrel = yrel

    sdl.SDL_GetWindowID.argtypes = [ctypes.c_void_p]
    sdl.SDL_GetWindowID.restype = ctypes.c_uint32
    focused_window = focused_sdl_window()
    if focused_window:
        event.motion.windowID = sdl.SDL_GetWindowID(focused_window)

    sdl.SDL_PushEvent.argtypes = [ctypes.POINTER(SDL_Event)]
    sdl.SDL_PushEvent.restype = ctypes.c_int
    pushed = sdl.SDL_PushEvent(ctypes.byref(event))
    if pushed != 1:
        raise AssertionError(f"SDL_PushEvent returned {pushed}.")


def push_sdl_window_size_changed_event(width, height):
    import ctypes

    class SDL_WindowEvent(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_uint32),
            ("timestamp", ctypes.c_uint32),
            ("windowID", ctypes.c_uint32),
            ("event", ctypes.c_uint8),
            ("padding1", ctypes.c_uint8),
            ("padding2", ctypes.c_uint8),
            ("padding3", ctypes.c_uint8),
            ("data1", ctypes.c_int32),
            ("data2", ctypes.c_int32),
        ]

    class SDL_Event(ctypes.Union):
        _fields_ = [
            ("type", ctypes.c_uint32),
            ("window", SDL_WindowEvent),
            ("padding", ctypes.c_uint8 * 56),
        ]

    sdl = load_sdl_library()
    focused_window = focused_sdl_window()
    if not focused_window:
        raise AssertionError("Expected a focused SDL window for resize event injection.")

    sdl.SDL_SetWindowSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    sdl.SDL_SetWindowSize(focused_window, width, height)

    actual_width = ctypes.c_int()
    actual_height = ctypes.c_int()
    sdl.SDL_GetWindowSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    sdl.SDL_GetWindowSize(focused_window, ctypes.byref(actual_width), ctypes.byref(actual_height))
    if actual_width.value <= 0 or actual_height.value <= 0:
        raise AssertionError(f"SDL_GetWindowSize returned {actual_width.value}x{actual_height.value}.")

    sdl.SDL_GetWindowID.argtypes = [ctypes.c_void_p]
    sdl.SDL_GetWindowID.restype = ctypes.c_uint32

    event = SDL_Event()
    event.type = SDL_WINDOWEVENT
    event.window.type = SDL_WINDOWEVENT
    event.window.windowID = sdl.SDL_GetWindowID(focused_window)
    event.window.event = SDL_WINDOWEVENT_SIZE_CHANGED
    event.window.data1 = actual_width.value
    event.window.data2 = actual_height.value

    sdl.SDL_PushEvent.argtypes = [ctypes.POINTER(SDL_Event)]
    sdl.SDL_PushEvent.restype = ctypes.c_int
    pushed = sdl.SDL_PushEvent(ctypes.byref(event))
    if pushed != 1:
        raise AssertionError(f"SDL_PushEvent returned {pushed}.")
    return actual_width.value, actual_height.value


def push_sdl_mouse_click(x, y, button=SDL_BUTTON_LEFT):
    push_sdl_mouse_button_event(x, y, button, SDL_MOUSEBUTTONDOWN)
    push_sdl_mouse_button_event(x, y, button, SDL_MOUSEBUTTONUP)


def push_sdl_quit_event():
    import ctypes

    class SDL_Event(ctypes.Union):
        _fields_ = [
            ("type", ctypes.c_uint32),
            ("padding", ctypes.c_uint8 * 56),
        ]

    sdl = load_sdl_library()
    sdl.SDL_InitSubSystem.argtypes = [ctypes.c_uint32]
    sdl.SDL_InitSubSystem.restype = ctypes.c_int
    if sdl.SDL_InitSubSystem(SDL_INIT_EVENTS) != 0:
        sdl.SDL_GetError.restype = ctypes.c_char_p
        error = sdl.SDL_GetError()
        message = error.decode("utf-8", errors="replace") if error else "SDL_InitSubSystem failed."
        raise AssertionError(message)

    event = SDL_Event()
    event.type = SDL_QUIT
    sdl.SDL_PushEvent.argtypes = [ctypes.POINTER(SDL_Event)]
    sdl.SDL_PushEvent.restype = ctypes.c_int
    pushed = sdl.SDL_PushEvent(ctypes.byref(event))
    if pushed != 1:
        raise AssertionError(f"SDL_PushEvent returned {pushed}.")


def drain_sdl_events():
    import ctypes

    class SDL_Event(ctypes.Union):
        _fields_ = [("padding", ctypes.c_uint8 * 56)]

    sdl = load_sdl_library()
    sdl.SDL_PollEvent.argtypes = [ctypes.POINTER(SDL_Event)]
    sdl.SDL_PollEvent.restype = ctypes.c_int

    event = SDL_Event()
    while sdl.SDL_PollEvent(ctypes.byref(event)) == 1:
        pass


def capture_sdl_screenshot(path, gui=None):
    import ctypes
    from PIL import Image

    data = None
    width = None
    height = None
    read_pixels = None
    if gui is not None:
        read_pixels = getattr(gui, "read_pixels", None) or getattr(gui, "readPixels", None)
    if read_pixels is not None:
        try:
            pixels, width, height = read_pixels()
            data = bytes(pixels)
        except RuntimeError:
            pass
    if data is None:
        sdl = load_sdl_library()
        window = focused_sdl_window()
        if not window:
            sdl.SDL_GetWindowFromID.argtypes = [ctypes.c_uint32]
            sdl.SDL_GetWindowFromID.restype = ctypes.c_void_p
            for window_id in range(1, 256):
                window = sdl.SDL_GetWindowFromID(window_id)
                if window:
                    break
        if not window:
            raise AssertionError("Could not find the focused SDL window for screenshot capture.")

        sdl.SDL_GetRenderer.argtypes = [ctypes.c_void_p]
        sdl.SDL_GetRenderer.restype = ctypes.c_void_p
        renderer = sdl.SDL_GetRenderer(window)
        if not renderer:
            raise AssertionError("Could not find the SDL renderer for screenshot capture.")

        width_value = ctypes.c_int()
        height_value = ctypes.c_int()
        sdl.SDL_GetRendererOutputSize.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        sdl.SDL_GetRendererOutputSize.restype = ctypes.c_int
        if sdl.SDL_GetRendererOutputSize(renderer, ctypes.byref(width_value), ctypes.byref(height_value)) != 0:
            raise_sdl_error(sdl, "SDL_GetRendererOutputSize")

        width = width_value.value
        height = height_value.value
        pitch = width * 4
        pixels = (ctypes.c_uint8 * (pitch * height))()
        sdl.SDL_RenderReadPixels.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        sdl.SDL_RenderReadPixels.restype = ctypes.c_int
        if sdl.SDL_RenderReadPixels(renderer, None, SDL_PIXELFORMAT_RGBA32, pixels, pitch) != 0:
            raise_sdl_error(sdl, "SDL_RenderReadPixels")
        data = bytes(pixels)

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.frombytes("RGBA", (width, height), data).save(path)
    return data, width, height


def raise_sdl_error(sdl, function_name):
    import ctypes

    sdl.SDL_GetError.restype = ctypes.c_char_p
    error = sdl.SDL_GetError()
    message = error.decode("utf-8", errors="replace") if error else "unknown SDL error"
    raise AssertionError(f"{function_name} failed: {message}")


def screenshot_pixel_summary(image):
    rgb_image = image.convert("RGB")
    colors = rgb_image.getcolors(maxcolors=9)
    unique_rgb = 10 if colors is None else len(colors)
    histogram = rgb_image.convert("L").histogram()
    non_black_pixels = sum(histogram[1:])
    return {"unique_rgb": unique_rgb, "non_black_pixels": non_black_pixels}


def screenshot_pixel_rgb(data, width, x, y):
    offset = (y * width + x) * 4
    return tuple(data[offset : offset + 3])


def screenshot_rect_summary(data, width, rect):
    x, y, w, h = rect
    unique_rgb = set()
    non_black_pixels = 0
    color_counts = {}
    for row in range(y, y + h):
        for col in range(x, x + w):
            rgb = screenshot_pixel_rgb(data, width, col, row)
            unique_rgb.add(rgb)
            color_counts[rgb] = color_counts.get(rgb, 0) + 1
            if rgb != (0, 0, 0):
                non_black_pixels += 1
    return {"unique_rgb": len(unique_rgb), "non_black_pixels": non_black_pixels, "color_counts": color_counts}


def resolved_rect(obj):
    x, y, w, h = obj.getResolvedRect()
    return int(x), int(y), int(w), int(h)


def rect_right(rect):
    return rect[0] + rect[2]


def rect_bottom(rect):
    return rect[1] + rect[3]


def rect_area(rect):
    return max(0, rect[2]) * max(0, rect[3])


def rect_contains(outer, inner):
    return (
        inner[0] >= outer[0]
        and inner[1] >= outer[1]
        and rect_right(inner) <= rect_right(outer)
        and rect_bottom(inner) <= rect_bottom(outer)
    )


def rect_contains_point(rect, x, y):
    return rect[0] <= x < rect_right(rect) and rect[1] <= y < rect_bottom(rect)


def rect_intersection(left, right):
    x0 = max(left[0], right[0])
    y0 = max(left[1], right[1])
    x1 = min(rect_right(left), rect_right(right))
    y1 = min(rect_bottom(left), rect_bottom(right))
    return x0, y0, max(0, x1 - x0), max(0, y1 - y0)


def rect_center(rect):
    return rect[0] + rect[2] // 2, rect[1] + rect[3] // 2


def centered_screen_rect(width, height):
    return GUI_WIDTH // 2 - width // 2, GUI_HEIGHT // 2 - height // 2, width, height


def same_gui_object(left, right):
    if left is right:
        return True
    try:
        if left == right:
            return True
    except Exception:
        pass
    return (
        left.getType(),
        left.getTypeId() if hasattr(left, "getTypeId") else "",
        left.getName() if hasattr(left, "getName") else "",
        resolved_rect(left),
    ) == (
        right.getType(),
        right.getTypeId() if hasattr(right, "getTypeId") else "",
        right.getName() if hasattr(right, "getName") else "",
        resolved_rect(right),
    )


def gui_has_child_object(g, target):
    return any(same_gui_object(child, target) for child in g.getGui().getChildren())


def assert_positive_rect(test_case, label, rect):
    test_case.assertGreater(rect[2], 0, f"{label} should have positive width: {rect}")
    test_case.assertGreater(rect[3], 0, f"{label} should have positive height: {rect}")


def assert_rect_on_screen(test_case, label, rect, width=GUI_WIDTH, height=GUI_HEIGHT):
    assert_positive_rect(test_case, label, rect)
    test_case.assertTrue(rect_contains((0, 0, width, height), rect), f"{label} escapes screen: {rect}")


def assert_child_inside(test_case, parent_label, parent_rect, child_label, child_rect):
    test_case.assertTrue(
        rect_contains(parent_rect, child_rect),
        f"{child_label} {child_rect} should be inside {parent_label} {parent_rect}",
    )


def assert_no_overlap(test_case, left_label, left_rect, right_label, right_rect):
    overlap = rect_intersection(left_rect, right_rect)
    test_case.assertEqual(
        0,
        rect_area(overlap),
        f"{left_label} {left_rect} overlaps {right_label} {right_rect} at {overlap}",
    )


def assert_runtime_rect(test_case, label, obj, expected):
    actual = resolved_rect(obj)
    test_case.assertEqual(expected, actual, f"{label} resolved rectangle mismatch.")
    return actual


def gui_child_sort_key(child):
    return (
        child.getPriority() if hasattr(child, "getPriority") else 0,
        child.getType() if hasattr(child, "getType") else "",
        child.getName() if hasattr(child, "getName") else "",
        child.getTypeId() if hasattr(child, "getTypeId") else "",
    )


def collect_gui_descendants(root):
    result = []
    stack = [root]
    while stack:
        current = stack.pop()
        result.append(current)
        children = sorted(list(current.getChildren()), key=gui_child_sort_key)
        stack.extend(reversed(children))
    return result


def find_descendants_by_type(root, class_name):
    return [child for child in collect_gui_descendants(root) if child.getType() == class_name]


def find_top_level_panel(g, class_name):
    matches = [child for child in g.getGui().getChildren() if child.getType() == class_name]
    return sorted(matches, key=gui_child_sort_key)[-1] if matches else None


def find_list_view(root, collection):
    matches = [
        child
        for child in find_descendants_by_type(root, "CListView")
        if getattr(child, "getCollection", lambda: "")() == collection
    ]
    if not matches:
        raise AssertionError(f"Could not find CListView with collection {collection}.")
    return matches[0]


def list_runtime_grid(list_view, gui):
    columns, rows = list_view.getRuntimeGridSize(gui)
    return int(columns), int(rows)


def list_cell_rect(list_view, column, row):
    x, y, _, _ = resolved_rect(list_view)
    tile = list_view.getTileSize()
    return x + column * tile, y + row * tile, tile, tile


def click_rect_center(rect, button=SDL_BUTTON_LEFT):
    x, y = rect_center(rect)
    push_sdl_mouse_click(x, y, button)


def click_list_cell(list_view, column, row, button=SDL_BUTTON_LEFT):
    click_rect_center(list_cell_rect(list_view, column, row), button=button)


def activate_list_cell(list_view, gui, column, row, button=SDL_BUTTON_LEFT):
    tile = list_view.getTileSize()
    x = column * tile + tile // 2
    y = row * tile + tile // 2
    list_view.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, button, x, y)
    list_view.mouseEvent(gui, SDL_MOUSEBUTTONUP, button, x, y)


def drag_list_cell_to_cell(test_case, g, source_list, source_column, source_row, target_list, target_column, target_row):
    start_x, start_y = rect_center(list_cell_rect(source_list, source_column, source_row))
    target_x, target_y = rect_center(list_cell_rect(target_list, target_column, target_row))

    push_sdl_mouse_button_event(start_x, start_y, SDL_BUTTON_LEFT, SDL_MOUSEBUTTONDOWN)
    pump_event_loop(3)
    test_case.assertTrue(g.getGui().hasDragSession())
    test_case.assertTrue(g.getGui().hasPointerCapture())

    push_sdl_mouse_motion_event(target_x, target_y, target_x - start_x, target_y - start_y)
    pump_event_loop(3)
    test_case.assertTrue(g.getGui().hasDragSession())
    test_case.assertTrue(g.getGui().hasPointerCapture())

    push_sdl_mouse_button_event(target_x, target_y, SDL_BUTTON_LEFT, SDL_MOUSEBUTTONUP)
    pump_event_loop(5)
    test_case.assertFalse(g.getGui().hasDragSession())
    test_case.assertFalse(g.getGui().hasPointerCapture())


def activate_first_proxy_graphic(list_view, gui, column, row, button=SDL_BUTTON_LEFT):
    for graphic in list_view.getProxiedObjects(gui, column, row):
        if graphic.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, button, 1, 1):
            return True
    return False


def activate_widget(widget, gui):
    rect = resolved_rect(widget)
    x = rect[2] // 2
    y = rect[3] // 2
    widget.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, x, y)
    widget.mouseEvent(gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, x, y)


def queue_question_answer(game, g, button_index):
    observed = {"attempts": 0}

    def answer():
        panel = find_top_level_panel(g, "CGameQuestionPanel")
        if panel is None:
            observed["attempts"] += 1
            if observed["attempts"] > 1000:
                raise AssertionError("CGameQuestionPanel was not visible for queued answer.")
            game.event_loop.instance().invoke(answer)
            return
        buttons = sorted(find_descendants_by_type(panel, "CButton"), key=lambda child: resolved_rect(child)[0])
        activate_widget(buttons[button_index], g.getGui())

    game.event_loop.instance().invoke(answer)


def list_cell_objects(list_view, gui, column, row):
    objects = []
    for graphic in list_view.getProxiedObjects(gui, column, row):
        get_object = getattr(graphic, "getObject", None)
        represented = get_object() if get_object else None
        if represented is not None and represented.getType() != "CGameObject":
            objects.append(represented)
    return objects


def list_visible_object_cells(list_view, gui):
    columns, rows = list_runtime_grid(list_view, gui)
    for row in range(rows):
        for column in range(columns):
            for obj in list_cell_objects(list_view, gui, column, row):
                yield column, row, obj


def click_first_list_object(test_case, list_view, gui, predicate=None, button=SDL_BUTTON_LEFT):
    columns, rows = list_runtime_grid(list_view, gui)
    for row in range(rows):
        for column in range(columns):
            for graphic in list_view.getProxiedObjects(gui, column, row):
                get_object = getattr(graphic, "getObject", None)
                obj = get_object() if get_object else None
                if obj is None or obj.getType() == "CGameObject":
                    continue
                if predicate is None or predicate(obj):
                    if graphic.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, button, 1, 1):
                        tile = list_view.getTileSize()
                        list_view.mouseEvent(
                            gui, SDL_MOUSEBUTTONUP, button, column * tile + tile // 2, row * tile + tile // 2
                        )
                    return obj
    raise AssertionError(f"No matching object found in {list_view.getCollection()} list.")


def list_visible_object_names(list_view, gui):
    return [obj.getName() or obj.getTypeId() for _, _, obj in list_visible_object_cells(list_view, gui)]


def gui_object_record(obj):
    record = {
        "type": obj.getType(),
        "typeId": obj.getTypeId() if hasattr(obj, "getTypeId") else "",
        "name": obj.getName() if hasattr(obj, "getName") else "",
        "priority": obj.getPriority() if hasattr(obj, "getPriority") else 0,
        "rect": list(resolved_rect(obj)),
    }
    for key, getter_name in (
        ("collection", "getCollection"),
        ("callback", "getCallback"),
        ("select", "getSelect"),
    ):
        getter = getattr(obj, getter_name, None)
        if getter:
            record[key] = getter()
    return record


def panel_pixel_summary(data, width, height, panel_rect, regions=None):
    regions = regions or {}
    summary = {
        "inside": 0,
        "outside": 0,
        "tightBounds": None,
        "regions": {name: 0 for name in regions},
    }
    bounds = None
    for pixel_index in range(width * height):
        offset = pixel_index * 4
        if data[offset : offset + 3] == b"\x00\x00\x00":
            continue
        x = pixel_index % width
        y = pixel_index // width
        if rect_contains_point(panel_rect, x, y):
            summary["inside"] += 1
        else:
            summary["outside"] += 1
        bounds = (
            (x, y, x, y)
            if bounds is None
            else (min(bounds[0], x), min(bounds[1], y), max(bounds[2], x), max(bounds[3], y))
        )
        for name, rect in regions.items():
            if rect_contains_point(rect, x, y):
                summary["regions"][name] += 1
    if bounds is not None:
        summary["tightBounds"] = [bounds[0], bounds[1], bounds[2] - bounds[0] + 1, bounds[3] - bounds[1] + 1]
    return summary


def pixel_diff_bounds(before, after, width, rect):
    bounds = None
    changed = 0
    for row in range(rect[1], rect_bottom(rect)):
        for col in range(rect[0], rect_right(rect)):
            offset = (row * width + col) * 4
            if before[offset : offset + 3] == after[offset : offset + 3]:
                continue
            changed += 1
            bounds = (
                (col, row, col, row)
                if bounds is None
                else (min(bounds[0], col), min(bounds[1], row), max(bounds[2], col), max(bounds[3], row))
            )
    if bounds is None:
        return None, 0
    return (bounds[0], bounds[1], bounds[2] - bounds[0] + 1, bounds[3] - bounds[1] + 1), changed


def annotate_panel_layout(source_path, output_path, summary):
    from PIL import Image, ImageDraw

    with Image.open(source_path) as image:
        annotated = image.convert("RGBA")
    draw = ImageDraw.Draw(annotated)
    panel_rect = summary["panel"]["rect"]
    draw.rectangle(
        [panel_rect[0], panel_rect[1], rect_right(panel_rect), rect_bottom(panel_rect)],
        outline=(255, 255, 0, 255),
        width=3,
    )
    for obj in summary["objects"][:80]:
        rect = obj["rect"]
        if rect[2] <= 0 or rect[3] <= 0:
            continue
        draw.rectangle([rect[0], rect[1], rect_right(rect), rect_bottom(rect)], outline=(0, 255, 255, 255), width=1)
        label = obj.get("collection") or obj["type"]
        draw.text((rect[0] + 2, rect[1] + 2), label, fill=(255, 255, 255, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    annotated.save(output_path)


def capture_panel_layout(test_case, g, scenario, panel, regions=None, outside_tolerance=0):
    regions = regions or {}
    pump_event_loop(3)
    screenshot_path = TEST_OUTPUT_DIR / f"{scenario}.png"
    try:
        data, width, height = capture_sdl_screenshot(screenshot_path, g.getGui())
    except RuntimeError as exc:
        test_case.skipTest(f"SDL renderer is not available for screenshot readback: {exc}")
    test_case.assertEqual((GUI_WIDTH, GUI_HEIGHT), (width, height))
    panel_rect = resolved_rect(panel)
    objects = sorted((gui_object_record(obj) for obj in collect_gui_descendants(panel)), key=lambda item: item["rect"])
    summary = {
        "scenario": scenario,
        "screen": [width, height],
        "panel": gui_object_record(panel),
        "objects": objects,
        "pixels": panel_pixel_summary(data, width, height, panel_rect, regions=regions),
    }
    json_path = TEST_OUTPUT_DIR / f"{scenario}-layout.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    annotated_path = TEST_OUTPUT_DIR / f"{scenario}-annotated.png"
    annotate_panel_layout(screenshot_path, annotated_path, summary)

    test_case.assertTrue(screenshot_path.exists())
    test_case.assertGreater(screenshot_path.stat().st_size, 0)
    test_case.assertTrue(annotated_path.exists())
    test_case.assertGreater(annotated_path.stat().st_size, 0)
    test_case.assertTrue(json_path.exists())
    test_case.assertGreater(summary["pixels"]["inside"], 0, f"{scenario} has no pixels inside {panel_rect}.")
    test_case.assertLessEqual(
        summary["pixels"]["outside"],
        outside_tolerance,
        f"{scenario} rendered {summary['pixels']['outside']} pixels outside {panel_rect}.",
    )
    return summary


def assert_region_has_pixels(test_case, summary, region, minimum=1):
    actual = summary["pixels"]["regions"].get(region, 0)
    test_case.assertGreaterEqual(actual, minimum, f"{summary['scenario']} region {region} has {actual} pixels.")


@contextlib.contextmanager
def isolated_gui_panel(g, panel):
    gui = g.getGui()
    removed = [child for child in gui.getChildren() if not same_gui_object(child, panel)]
    for child in removed:
        gui.removeChild(child)
    pump_event_loop(3)
    try:
        yield
    finally:
        for child in removed:
            gui.addChild(child)
        pump_event_loop(3)


def assert_screenshot_has_rendered_pixels(test_case, g, name):
    from PIL import Image

    screenshot_path = TEST_OUTPUT_DIR / f"{name}.png"
    try:
        data, width, height = capture_sdl_screenshot(screenshot_path, g.getGui())
    except RuntimeError as exc:
        test_case.skipTest(f"SDL renderer is not available for screenshot readback: {exc}")

    test_case.assertEqual(".png", screenshot_path.suffix)
    test_case.assertEqual((GUI_WIDTH, GUI_HEIGHT), (width, height))
    test_case.assertTrue(screenshot_path.exists())
    test_case.assertGreater(screenshot_path.stat().st_size, 0)
    with Image.open(screenshot_path) as image:
        image.load()
        test_case.assertEqual((width, height), image.size)
        summary = screenshot_pixel_summary(image)
    test_case.assertGreater(summary["unique_rgb"], 8)
    test_case.assertGreater(summary["non_black_pixels"], width * height // 100)
    assert_rendered_map_proxy_cells(test_case, g)
    return summary


def assert_minimap_has_rendered_pixels(test_case, g, name):
    from PIL import Image

    screenshot_path = TEST_OUTPUT_DIR / f"{name}.png"
    try:
        data, width, height = capture_sdl_screenshot(screenshot_path, g.getGui())
    except RuntimeError as exc:
        test_case.skipTest(f"SDL renderer is not available for screenshot readback: {exc}")
    summary = screenshot_rect_summary(data, width, MINIMAP_RECT)

    test_case.assertEqual((GUI_WIDTH, GUI_HEIGHT), (width, height))
    test_case.assertTrue(screenshot_path.exists())
    test_case.assertGreater(screenshot_path.stat().st_size, 0)
    with Image.open(screenshot_path) as image:
        image.load()
        test_case.assertEqual((width, height), image.size)

    minimap_area = MINIMAP_RECT[2] * MINIMAP_RECT[3]
    test_case.assertGreater(summary["unique_rgb"], 3)
    test_case.assertGreater(summary["non_black_pixels"], minimap_area * 9 // 10)
    test_case.assertGreater(summary["color_counts"].get(MINIMAP_PLAYER_RGB, 0), 0)
    test_case.assertGreater(summary["color_counts"].get(MINIMAP_VIEWPORT_RGB, 0), 0)
    return summary


def find_adjacent_walkable_direction(game_map, origin):
    game = load_game_module()
    directions = (
        (game.Coords(1, 0, 0), SDL_SCANCODE_MASK | 79, 79),
        (game.Coords(-1, 0, 0), SDL_SCANCODE_MASK | 80, 80),
        (game.Coords(0, 1, 0), SDL_SCANCODE_MASK | 81, 81),
        (game.Coords(0, -1, 0), SDL_SCANCODE_MASK | 82, 82),
    )
    for delta, keycode, scancode in directions:
        target = game.Coords(origin.x + delta.x, origin.y + delta.y, origin.z + delta.z)
        if game_map.canStep(target):
            return target, keycode, scancode
    raise AssertionError(f"Expected an adjacent walkable tile near {origin.x},{origin.y},{origin.z}.")


def visible_map_cell_center(origin, target):
    dx = target.x - origin.x
    dy = target.y - origin.y
    center_cell_x = (GUI_WIDTH // GUI_TILE_SIZE + 1) // 2
    center_cell_y = (GUI_HEIGHT // GUI_TILE_SIZE + 1) // 2
    return (
        (center_cell_x + dx) * GUI_TILE_SIZE + GUI_TILE_SIZE // 2,
        (center_cell_y + dy) * GUI_TILE_SIZE + GUI_TILE_SIZE // 2,
    )


def gui_contains_class(g, class_name):
    game = load_game_module()
    gui_tree = json.loads(game.jsonify(g.getGui()))
    stack = [gui_tree]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        if node.get("class") == class_name:
            return True
        stack.extend(node.get("properties", {}).get("children") or [])
    return False


def collect_gui_children(root, class_name):
    matches = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.getType() == class_name:
            matches.append(node)
        stack.extend(node.getChildren())
    return matches


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
NOURAAJD_VICTOR_FALLBACK_RADIUS = 3
NOURAAJD_VICTOR_LEADER_SPAWN = (45, 100, 0)
NOURAAJD_VICTOR_PREFERRED_SPAWNS = (
    (44, 100, 0),
    (46, 100, 0),
    (45, 99, 0),
    (45, 101, 0),
    (45, 100, 0),
)
TILED_FLIP_FLAG_MASK = 0xF0000000
SUPPORTED_TILED_LAYER_TYPES = {"tilelayer", "objectgroup"}
_git_changed_files_cache = None


def git_changed_files():
    global _git_changed_files_cache
    if _git_changed_files_cache is not None:
        return list(_git_changed_files_cache)

    if shutil.which("git") is None:
        return []

    changed = set()

    def collect(cmd):
        return_code, output, _ = run_command(cmd)
        if return_code != 0 or not output:
            return
        changed.update(line.strip() for line in output.splitlines() if line.strip())

    base_ref = None
    for candidate in ("origin/main", "main"):
        return_code, _, _ = run_command(["git", "rev-parse", "--verify", candidate])
        if return_code == 0:
            base_ref = candidate
            break

    if base_ref is not None:
        merge_base_code, merge_base, _ = run_command(["git", "merge-base", base_ref, "HEAD"])
        if merge_base_code == 0 and merge_base:
            collect(["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", f"{merge_base.strip()}...HEAD"])

    collect(["git", "diff", "--name-only", "--diff-filter=ACMRTUXB"])
    collect(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB"])
    collect(["git", "ls-files", "--others", "--exclude-standard"])

    _git_changed_files_cache = tuple(sorted(path for path in changed if (REPO_ROOT / path).is_file()))
    return list(_git_changed_files_cache)


def git_tracked_files(*patterns):
    if shutil.which("git") is None:
        return []

    command = ["git", "ls-files"]
    command.extend(patterns)
    return_code, output, _ = run_command(command)
    if return_code != 0 or not output:
        return []
    return sorted(line.strip() for line in output.splitlines() if line.strip() and (REPO_ROOT / line.strip()).is_file())


def iter_python_source_files():
    for file_path in git_changed_files():
        path = REPO_ROOT / file_path
        if path.suffix == ".py":
            yield path


def iter_cpp_source_files():
    for file_path in git_changed_files():
        path = REPO_ROOT / file_path
        if path.relative_to(REPO_ROOT).parts[:1] == ("third_party",):
            continue
        if path.suffix in {".h", ".hpp", ".c", ".cc", ".cpp", ".cxx"}:
            yield path


def run_command(args):
    proc = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
    output = proc.stdout.strip()
    errors = proc.stderr.strip()
    return proc.returncode, output, errors


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


def coords_tuple(coords):
    return coords.x, coords.y, coords.z


def drive_player_to_target(game_map, player, target, *, until=None, max_turns=24):
    controller = set_player_target(player, target)

    def reached():
        return until() if until else coords_tuple(player.getCoords()) == coords_tuple(target)

    if reached():
        return controller
    for _ in range(max_turns):
        game_map.move()
        pump_event_loop(2)
        if reached():
            return controller
    raise AssertionError(
        f"Player did not reach target {coords_tuple(target)} from {coords_tuple(player.getCoords())} "
        f"after {max_turns} turns."
    )


def multilevel_object_layer_levels():
    levels = {}
    for layer in load_map_data("multilevel").get("layers", []):
        if layer.get("type") != "objectgroup":
            continue
        layer_level = int(layer.get("properties", {}).get("level", 0))
        for obj in layer.get("objects", []):
            if obj.get("name"):
                levels[obj["name"]] = layer_level
    return levels


def drive_multilevel_route(game_map, player):
    stairs_up = find_runtime_object(game_map, "stairsUp")
    stairs_down = find_runtime_object(game_map, "stairsDown")
    upper_goal = find_runtime_object(game_map, "multilevelUpperGoal")
    lower_goal = find_runtime_object(game_map, "multilevelLowerGoal")

    start_turn = game_map.getTurn()
    drive_player_to_target(game_map, player, stairs_up.getCoords(), until=lambda: player.getCoords().z == 1)
    upper_landing = coords_tuple(player.getCoords())
    drive_player_to_target(game_map, player, upper_goal.getCoords())
    upper_goal_coords = coords_tuple(player.getCoords())
    drive_player_to_target(game_map, player, stairs_down.getCoords(), until=lambda: player.getCoords().z == 0)
    lower_landing = coords_tuple(player.getCoords())
    drive_player_to_target(game_map, player, lower_goal.getCoords())
    lower_goal_coords = coords_tuple(player.getCoords())

    return {
        "turns": game_map.getTurn() - start_turn,
        "upper_landing": upper_landing,
        "upper_goal": upper_goal_coords,
        "lower_landing": lower_landing,
        "lower_goal": lower_goal_coords,
    }


def get_panel_proxy_child_totals_by_collection(panel):
    game = load_game_module()
    panel_data = json.loads(game.jsonify(panel))
    totals = {}
    for child in panel_data.get("properties", {}).get("children") or []:
        properties = child.get("properties", {})
        collection = properties.get("collection")
        if not collection:
            continue
        proxy_children = properties.get("children") or []
        totals[collection] = sum(len(proxy.get("properties", {}).get("children") or []) for proxy in proxy_children)
    return totals


def get_panel_selection_box_counts_by_collection(panel):
    game = load_game_module()
    panel_data = json.loads(game.jsonify(panel))
    counts = {}

    def child_nodes(node):
        return node.get("properties", {}).get("children") or []

    def visit(node):
        properties = node.get("properties", {})
        collection = properties.get("collection")
        if collection:
            counts[collection] = sum(
                1
                for proxy in child_nodes(node)
                for child in child_nodes(proxy)
                if child.get("class") == "CSelectionBox"
            )
        for child in child_nodes(node):
            visit(child)

    visit(panel_data)
    return counts


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


def add_nouraajd_victor_spawn_blocker(g, game_map, coords, index):
    game = load_game_module()
    blocker = g.createObject("CEvent")
    blocker.setStringProperty("name", f"victorSpawnBlocker{index}")
    blocker.setBoolProperty("canStep", False)
    game_map.addObject(blocker)
    blocker.moveTo(coords[0], coords[1], coords[2])
    game_coords = game.Coords(coords[0], coords[1], coords[2])
    if game_map.canStep(game_coords):
        raise AssertionError(f"Expected Victor spawn blocker at {coords} to block stepping.")
    return blocker


def nouraajd_victor_spawn_candidates(preferred):
    x, y, z = preferred
    yield preferred
    for radius in range(1, NOURAAJD_VICTOR_FALLBACK_RADIUS + 1):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if abs(dx) + abs(dy) == radius:
                    yield x + dx, y + dy, z


def add_nouraajd_victor_preferred_spawn_blockers(g, game_map):
    return [
        add_nouraajd_victor_spawn_blocker(g, game_map, coords, index)
        for index, coords in enumerate(NOURAAJD_VICTOR_PREFERRED_SPAWNS, start=1)
    ]


def add_nouraajd_victor_leader_fallback_blockers(g, game_map):
    return [
        add_nouraajd_victor_spawn_blocker(g, game_map, coords, index)
        for index, coords in enumerate(nouraajd_victor_spawn_candidates(NOURAAJD_VICTOR_LEADER_SPAWN), start=1)
    ]


def find_runtime_object(game_map, object_name):
    obj = game_map.getObjectByName(object_name)
    if obj is None:
        raise AssertionError(f"Could not find runtime object '{object_name}' on map '{game_map.getName()}'.")
    return obj


NOURAAJD_QUEST_STATE_NAMES = (
    "rolf",
    "main",
    "beren_chain",
    "octobogz_contract",
    "amulet",
    "victor",
)

NOURAAJD_MAP_BOOL_FLAGS = (
    "completed_rolf",
    "completed_gooby",
    "DELIVERED_LETTER",
    "RELIC_RETURNED",
    "OCTOBOGZ_SLAIN",
    "OCTOBOGZ_CLEARED",
    "CAVE_PURGED",
    "completed_octobogz",
    "AMULET_QUEST_STARTED",
    "AMULET_RETURNED",
    "VICTOR_QUEST_STARTED",
    "VICTOR_COURTYARD_FOUND",
    "VICTOR_CULTISTS_SPAWNED",
    "VICTOR_GOOD_END",
    "VICTOR_BAD_END",
    "VICTOR_HELP",
    "VICTOR_REWARD_CLAIMED",
)

NOURAAJD_PLAYER_BOOL_FLAGS = (
    "CAN_CRAFT_SCROLLS",
    "CAN_BREW_GREATER_POTIONS",
)

NOURAAJD_INVENTORY_ITEMS = (
    "letterFromRolf",
    "skullOfRolf",
    "letterToBeren",
    "holyRelic",
    "preciousAmulet",
    "ShadowBlade",
)


def completed_quest_names(player):
    if not hasattr(player, "getCompletedQuests"):
        return []
    return sorted(player_quest_id(quest) for quest in player.getCompletedQuests())


def named_object_presence(game_map, names):
    return {name: game_map.getObjectByName(name) is not None for name in names}


def named_object_prefix_counts(game_map, prefixes):
    counts = {prefix: 0 for prefix in prefixes}
    for obj in game_map.getObjects():
        name = obj.getName()
        if not name:
            continue
        for prefix in prefixes:
            if name.startswith(prefix):
                counts[prefix] += 1
    return counts


def nouraajd_quest_state_snapshot(game_map):
    return {quest: game_map.getStringProperty(f"quest_state_{quest}") for quest in NOURAAJD_QUEST_STATE_NAMES}


def player_item_counts(player, item_ids):
    return {item_id: player.countItems(item_id) for item_id in item_ids}


def nouraajd_save_load_snapshot(game_map, player, *, object_names=(), object_prefixes=()):
    return {
        "map": game_map.mapName,
        "player": coords_tuple(player.getCoords()),
        "turn": game_map.getTurn(),
        "quest_states": nouraajd_quest_state_snapshot(game_map),
        "map_flags": {flag: game_map.getBoolProperty(flag) for flag in NOURAAJD_MAP_BOOL_FLAGS},
        "victor_turn": game_map.getNumericProperty("VICTOR_COURTYARD_TURN"),
        "player_flags": {flag: player.getBoolProperty(flag) for flag in NOURAAJD_PLAYER_BOOL_FLAGS},
        "items": player_item_counts(player, NOURAAJD_INVENTORY_ITEMS),
        "active_quests": quest_names(player),
        "completed_quests": completed_quest_names(player),
        "objects": named_object_presence(game_map, object_names),
        "object_prefix_counts": named_object_prefix_counts(game_map, object_prefixes),
    }


def save_load_roundtrip(game, game_map, prefix):
    save_name = unique_save_name(prefix)
    save_path = Path.cwd() / "save" / f"{save_name}.json"
    game.CMapLoader.save(game_map, save_name)
    loaded_game = game.CGameLoader.loadGame()
    game.CGameLoader.loadSavedGame(loaded_game, save_name)
    loaded_map = loaded_game.getMap()
    loaded_player = loaded_map.getPlayer()
    return save_path, loaded_game, loaded_map, loaded_player


def assert_nouraajd_save_load_roundtrip(test_case, game, game_map, prefix, save_paths, **snapshot_kwargs):
    before = nouraajd_save_load_snapshot(game_map, game_map.getPlayer(), **snapshot_kwargs)
    save_path, loaded_game, loaded_map, loaded_player = save_load_roundtrip(game, game_map, prefix)
    save_paths.append(save_path)
    after = nouraajd_save_load_snapshot(loaded_map, loaded_player, **snapshot_kwargs)

    test_case.assertEqual(before, after)
    test_case.assertIsNotNone(get_player_controller(loaded_player))
    test_case.assertIsNotNone(loaded_player.getFightController())
    return loaded_game, loaded_map, loaded_player, after


def find_map_object_definition(map_name, object_name):
    map_data = load_map_data(map_name)
    for layer in map_data.get("layers", []):
        if layer.get("type") != "objectgroup":
            continue
        for obj in layer.get("objects", []):
            if obj.get("name") == object_name:
                return obj
    raise AssertionError(f"Could not find object definition '{object_name}' in res/maps/{map_name}/map.json.")


def map_source_mentions(map_name, token):
    map_dir = MAPS_DIR / map_name
    if not map_dir.is_dir():
        raise AssertionError(f"Could not find source directory res/maps/{map_name}.")

    mentions = []
    for path in sorted(map_dir.glob("*")):
        if path.suffix not in {".json", ".py"}:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if token in line:
                mentions.append(f"{path.relative_to(REPO_ROOT)}:{line_number}")
    return mentions


def map_dialog_sources(map_name):
    map_dir = MAPS_DIR / map_name
    if not map_dir.is_dir():
        raise AssertionError(f"Could not find source directory res/maps/{map_name}.")

    dialogs = {}
    for path in sorted(map_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for dialog_id, value in data.items():
            if isinstance(value, dict) and str(value.get("class", "")).endswith("Dialog"):
                dialogs[dialog_id] = {"path": path, "definition": value}
    return dialogs


def require_source_dialog(map_name, dialog_id):
    dialogs = map_dialog_sources(map_name)
    if dialog_id in dialogs:
        return dialogs[dialog_id]

    available = ", ".join(sorted(dialogs)) or "none"
    raise AssertionError(
        f"Could not find dialog id '{dialog_id}' in res/maps/{map_name}/*.json. "
        f"Available source dialog ids: {available}."
    )


def collect_source_dialog_hooks(dialog_definition):
    actions = {}
    conditions = {}

    def visit(node):
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                action = properties.get("action")
                condition = properties.get("condition")
                if isinstance(action, str) and action:
                    source_conditions = actions.setdefault(action, set())
                    source_conditions.add(condition if isinstance(condition, str) and condition else None)
                if isinstance(condition, str) and condition:
                    source_actions = conditions.setdefault(condition, set())
                    source_actions.add(action if isinstance(action, str) and action else None)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(dialog_definition)
    return actions, conditions


def assert_mcp_engine_export(name):
    if name not in mcp.MCP_ALLOWED_EXPORTS:
        raise AssertionError(f"MCP scenario helper requires exported engine call {name}.")


def assert_mcp_handle_method(class_name, method_name):
    if method_name not in mcp.MCP_ALLOWED_HANDLE_METHODS.get(class_name, set()):
        raise AssertionError(f"MCP scenario helper requires exported handle method {class_name}.{method_name}.")


class McpScenarioHarness:
    """Headless scenario helper that mirrors the MCP handle surface used by subagent tests.

    Start with `McpScenarioHarness.start("nouraajd")`, use `invokeDialogAction()` for source-backed dialog
    actions, use `removeObjectByName()` for authored destroy-trigger scenarios, and call `snapshot()` for stable
    quest, inventory, flag, and object assertions without GUI state.
    """

    def __init__(self, game_instance, map_name):
        self.gameInstance = game_instance
        self.mapName = map_name
        self.refresh()

    @classmethod
    def start(cls, map_name="nouraajd", player_name=DEFAULT_PLAYER, pump_iterations=5, enter_start_event=True):
        for name in (
            "CGameLoader.loadGame",
            "CGameLoader.startGameWithPlayer",
            "event_loop.instance",
        ):
            assert_mcp_engine_export(name)
        for class_name, method_name in (
            ("CGame", "getMap"),
            ("CMap", "getPlayer"),
        ):
            assert_mcp_handle_method(class_name, method_name)

        game_module = load_game_module()
        game_instance = game_module.CGameLoader.loadGame()
        game_module.CGameLoader.startGameWithPlayer(game_instance, map_name, player_name)
        scenario = cls(game_instance, map_name)
        if enter_start_event:
            scenario.enterStartEvent(pump_iterations=pump_iterations)
        else:
            scenario.pump(pump_iterations)
        return scenario

    def refresh(self):
        self.gameMap = self.gameInstance.getMap()
        self.player = self.gameMap.getPlayer()
        return self

    def pump(self, iterations=1):
        assert_mcp_engine_export("event_loop.instance")
        assert_mcp_handle_method("event_loop", "run")
        game_module = load_game_module()
        loop = game_module.event_loop.instance()
        for _ in range(max(int(iterations), 0)):
            loop.run()
        return self.refresh()

    def enterStartEvent(self, *, pump_iterations=5):
        for class_name, method_name in (
            ("CMap", "getObjects"),
            ("CGameObject", "getType"),
            ("CGameObject", "getTypeId"),
            ("CMapObject", "getCoords"),
            ("CMapObject", "moveTo"),
        ):
            assert_mcp_handle_method(class_name, method_name)

        start_events = [
            obj for obj in self.gameMap.getObjects() if obj.getTypeId() == "StartEvent" or obj.getType() == "StartEvent"
        ]
        if not start_events:
            return False

        start_coords = start_events[0].getCoords()
        self.player.moveTo(start_coords.x, start_coords.y, start_coords.z)
        self.pump(pump_iterations)
        return True

    def runtimeObject(self, object_name):
        assert_mcp_handle_method("CMap", "getObjectByName")
        obj = self.gameMap.getObjectByName(object_name)
        if obj is not None:
            return obj

        mentions = map_source_mentions(self.mapName, object_name)
        if mentions:
            source_note = "source mentions: " + ", ".join(mentions[:6])
        else:
            source_note = f"no source mention found under res/maps/{self.mapName}"
        raise AssertionError(f"Could not find runtime object '{object_name}' on map '{self.mapName}' ({source_note}).")

    def createDialog(self, dialog_id):
        source = require_source_dialog(self.mapName, dialog_id)
        assert_mcp_handle_method("CGame", "createObject")
        dialog = self.gameInstance.createObject(dialog_id)
        if dialog is None or not hasattr(dialog, "invokeAction") or not hasattr(dialog, "invokeCondition"):
            path = source["path"].relative_to(REPO_ROOT)
            raise AssertionError(f"Source dialog '{dialog_id}' from {path} did not create a CDialog-compatible object.")
        return dialog, source

    def invokeDialogAction(self, dialog_id, action, *, condition=None, require_condition=True, pump_iterations=3):
        dialog, source = self.createDialog(dialog_id)
        source_actions, source_conditions = collect_source_dialog_hooks(source["definition"])
        source_path = source["path"].relative_to(REPO_ROOT)
        if action not in source_actions:
            available = ", ".join(sorted(source_actions)) or "none"
            raise AssertionError(
                f"Dialog action '{dialog_id}.{action}' is not declared in {source_path}; "
                f"available source actions: {available}."
            )

        action_conditions = sorted(item for item in source_actions[action] if item)
        condition_name = condition
        if condition_name is None and len(action_conditions) == 1:
            condition_name = action_conditions[0]
        if condition_name is not None:
            if condition_name not in source_conditions:
                available = ", ".join(sorted(source_conditions)) or "none"
                raise AssertionError(
                    f"Dialog condition '{dialog_id}.{condition_name}' is not declared in {source_path}; "
                    f"available source conditions: {available}."
                )
            assert_mcp_handle_method("CDialog", "invokeCondition")
            condition_value = dialog.invokeCondition(condition_name)
            if require_condition and not condition_value:
                raise AssertionError(
                    f"Source condition '{dialog_id}.{condition_name}' returned false before action '{action}'."
                )

        assert_mcp_handle_method("CDialog", "invokeAction")
        dialog.invokeAction(action)
        self.pump(pump_iterations)
        return dialog

    def removeObjectByName(self, object_name, *, check_quests=True, pump_iterations=3):
        obj = self.runtimeObject(object_name)
        assert_mcp_handle_method("CGameObject", "getName")
        assert_mcp_handle_method("CMap", "removeObjectByName")
        runtime_name = obj.getName() or object_name
        self.gameMap.removeObjectByName(runtime_name)
        self.pump(pump_iterations)
        if check_quests:
            assert_mcp_handle_method("CPlayer", "checkQuests")
            self.player.checkQuests()
            self.pump(1)
        return runtime_name

    def snapshot(
        self,
        *,
        quest_state_names=NOURAAJD_QUEST_STATE_NAMES,
        map_flags=NOURAAJD_MAP_BOOL_FLAGS,
        player_flags=NOURAAJD_PLAYER_BOOL_FLAGS,
        item_ids=NOURAAJD_INVENTORY_ITEMS,
        object_names=(),
        object_prefixes=(),
        object_bool_properties=None,
    ):
        self.refresh()
        object_bool_properties = object_bool_properties or {}
        return {
            "map": self.gameMap.mapName,
            "turn": self.gameMap.getTurn(),
            "quest_states": {
                quest: self.gameMap.getStringProperty(f"quest_state_{quest}") for quest in quest_state_names
            },
            "map_flags": {flag: self.gameMap.getBoolProperty(flag) for flag in map_flags},
            "player_flags": {flag: self.player.getBoolProperty(flag) for flag in player_flags},
            "items": {item_id: self.player.countItems(item_id) for item_id in item_ids},
            "active_quests": quest_names(self.player),
            "completed_quests": completed_quest_names(self.player),
            "objects": named_object_presence(self.gameMap, object_names),
            "object_prefix_counts": named_object_prefix_counts(self.gameMap, object_prefixes),
            "object_bool_properties": {
                object_name: {flag: self.runtimeObject(object_name).getBoolProperty(flag) for flag in flags}
                for object_name, flags in object_bool_properties.items()
            },
        }


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
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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

    def quest_state(name):
        return game_map.getStringProperty(f"quest_state_{name}")

    def assert_active(quest_id):
        assert quest_id in quest_names(player), f"{quest_id} should be active."

    def assert_completed(quest_id):
        assert quest_id in completed_quest_names(player), f"{quest_id} should be completed."

    start_events = [
        obj for obj in game_map.getObjects() if obj.getTypeId() == "StartEvent" or obj.getType() == "StartEvent"
    ]
    assert start_events, "The Nouraajd walkthrough should start from an authored StartEvent."
    start_coords = start_events[0].getCoords()
    initial_skulls = player.countItems("skullOfRolf")
    player.moveTo(start_coords.x, start_coords.y, start_coords.z)
    pump_event_loop(5)
    assert player.countItems("letterFromRolf") >= 1, "StartEvent should grant Rolf's letter."
    assert quest_state("rolf") == "awaiting_skull"
    assert_active("rolfQuest")

    game_map.removeObjectByName("cave1")
    player.checkQuests()
    assert quest_state("rolf") == "skull_recovered"
    assert quest_state("main") == "awaiting_gooby"
    assert player.countItems("skullOfRolf") == initial_skulls + 1
    assert game_map.getBoolProperty("completed_rolf")
    assert find_runtime_object(game_map, "gooby1") is not None
    assert_completed("rolfQuest")
    assert_active("mainQuest")

    gooby = find_runtime_object(game_map, "gooby1")
    gooby_gold = player.getGold()
    game_map.removeObjectByName(gooby.getName())
    player.checkQuests()
    assert quest_state("main") == "gooby_slain"
    assert player.getGold() == gooby_gold + 200
    assert game_map.getBoolProperty("GOOBY_REWARD_CLAIMED")
    assert game_map.getBoolProperty("completed_gooby")
    assert_completed("mainQuest")
    main_quest = find_player_quest(player, "mainQuest")
    main_quest.onComplete()
    assert player.getGold() == gooby_gold + 200

    town_hall = g.createObject("townHallDialog")
    beren = g.createObject("berenDialog")
    travelers = g.createObject("dialog")
    town_hall.give_letter()
    assert quest_state("beren_chain") == "letter_in_hand"
    assert player.countItems("letterToBeren") == 1
    assert_active("deliverLetterQuest")

    beren.deliver_letter()
    player.checkQuests()
    assert quest_state("beren_chain") == "letter_delivered"
    assert player.countItems("letterToBeren") == 0
    assert player.getBoolProperty("CAN_CRAFT_SCROLLS")
    assert game_map.getBoolProperty("DELIVERED_LETTER")
    assert_completed("deliverLetterQuest")
    assert_active("retrieveRelicQuest")

    game_map.removeObjectByName("catacombs")
    assert quest_state("beren_chain") == "relic_obtained"
    assert player.countItems("holyRelic") == 1

    beren.return_relic()
    player.checkQuests()
    assert quest_state("beren_chain") == "relic_returned_waiting_kill"
    assert player.countItems("holyRelic") == 0
    assert player.getBoolProperty("CAN_BREW_GREATER_POTIONS")
    assert game_map.getBoolProperty("RELIC_RETURNED")
    assert_completed("retrieveRelicQuest")
    assert_active("cleanseCaveQuest")

    travelers.accept_quest()
    assert quest_state("octobogz_contract") == "active"
    assert_active("octoBogzQuest")

    octobogz_gold = player.getGold()
    octobogz_shadow_blades = player.countItems("ShadowBlade")
    game_map.removeObjectByName("cave2")
    player.checkQuests()
    assert quest_state("beren_chain") == "ready_to_report"
    assert quest_state("octobogz_contract") == "completed"
    assert game_map.getBoolProperty("OCTOBOGZ_SLAIN")
    assert game_map.getBoolProperty("OCTOBOGZ_CLEARED")
    assert game_map.getBoolProperty("completed_octobogz")
    assert player.getGold() == octobogz_gold + 1000
    assert player.countItems("ShadowBlade") == octobogz_shadow_blades + 1
    assert_completed("octoBogzQuest")

    tavern_intro = g.createObject("tavernDialog1")
    tavern = g.createObject("tavernDialog2")
    tavern_intro.asked_about_girl()
    tavern.talked_to_victor()
    assert quest_state("victor") == "met_victor"
    assert_active("victorQuest")
    town_hall.spawn_cultists()
    leader = find_runtime_object(game_map, "cultLeaderQuest")
    cultists = [obj for obj in game_map.getObjects() if obj.getName() and obj.getName().startswith("victorCultist")]
    assert quest_state("victor") == "encounter_active"
    assert game_map.getBoolProperty("VICTOR_COURTYARD_FOUND")
    assert game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED")
    assert cultists, "Victor good-ending path should spawn cultists."

    victor_gold = player.getGold()
    game_map.removeObjectByName(leader.getName())
    player.checkQuests()
    assert quest_state("victor") == "good_end"
    assert player.getGold() == victor_gold + 500
    assert game_map.getBoolProperty("VICTOR_GOOD_END")
    assert game_map.getBoolProperty("VICTOR_REWARD_CLAIMED")
    assert game_map.getObjectByName("cultLeaderQuest") is None
    assert not any(obj.getName() and obj.getName().startswith("victorCultist") for obj in game_map.getObjects())
    assert_completed("victorQuest")

    quest_dialog = g.createObject("questDialog")
    quest_return_dialog = g.createObject("questReturnDialog")
    quest_dialog.start_amulet_quest()
    assert quest_state("amulet") == "active"
    assert game_map.getObjectByName("amuletGoblin") is not None
    assert_active("amuletQuest")
    amulet_gold = player.getGold()
    player.addItem("preciousAmulet")
    quest_return_dialog.complete_amulet_quest()
    player.checkQuests()
    assert quest_state("amulet") == "returned"
    assert player.getGold() == amulet_gold + 50
    assert player.countItems("preciousAmulet") == 0
    assert game_map.getObjectByName("oldWoman") is None
    assert game_map.getObjectByName("amuletGoblin") is None
    assert_completed("amuletQuest")

    beren.finish_cleanse()
    pump_event_loop(10)
    assert quest_state("beren_chain") == "purged"
    assert game_map.getBoolProperty("CAVE_PURGED")
    assert_completed("cleanseCaveQuest")
    assert g.getMap().mapName == "ritual"

    g_bad, game_map_bad, player_bad = load_game_map_with_player("nouraajd")
    tavern_bad = g_bad.createObject("tavernDialog2")
    town_hall_bad = g_bad.createObject("townHallDialog")
    tavern_bad.talked_to_victor()
    town_hall_bad.spawn_cultists()
    assert game_map_bad.getStringProperty("quest_state_victor") == "encounter_active"
    bad_start_gold = player_bad.getGold()
    force_nouraajd_victor_timeout(game_map_bad)
    player_bad.checkQuests()
    assert game_map_bad.getStringProperty("quest_state_victor") == "bad_end"
    assert player_bad.getGold() == bad_start_gold
    assert game_map_bad.getBoolProperty("VICTOR_BAD_END")
    assert not game_map_bad.getBoolProperty("VICTOR_REWARD_CLAIMED")
    assert game_map_bad.getObjectByName("cultLeaderQuest") is None
    assert not any(obj.getName() and obj.getName().startswith("victorCultist") for obj in game_map_bad.getObjects())
    assert "victorQuest" in completed_quest_names(player_bad)
    victor_bad_quest = find_player_quest(player_bad, "victorQuest")
    assert victor_bad_quest.getReward() == "No reward if Victor's daughter is taken."

    return {
        "map": "nouraajd",
        "quest_states": nouraajd_quest_state_snapshot(game_map),
        "bad_victor_state": game_map_bad.getStringProperty("quest_state_victor"),
        "items": player_item_counts(player, NOURAAJD_INVENTORY_ITEMS),
        "gold": player.getGold(),
        "active_quests": quest_names(player),
        "completed_quests": completed_quest_names(player),
        "gooby_reward_claimed": game_map.getBoolProperty("GOOBY_REWARD_CLAIMED"),
        "current_map": g.getMap().mapName,
    }


def walkthrough_multilevel_map():
    _g, game_map, player = load_game_map_with_player("multilevel")
    route = drive_multilevel_route(game_map, player)

    assert game_map.getBoolProperty("used_stairs_up"), "The route should use the upper stairs."
    assert game_map.getBoolProperty("used_stairs_down"), "The route should use the lower stairs."
    assert game_map.getBoolProperty("visited_upper_goal"), "The upper authored target should be visited."
    assert game_map.getBoolProperty("visited_lower_goal"), "The lower authored target should be visited."
    assert game_map.canStep(load_game_module().Coords(2, 2, 1)), "Level 0 blocker should not block level 1."
    assert game_map.canStep(load_game_module().Coords(5, 2, 0)), "Level 1 blocker should not block level 0."

    return {
        "map": "multilevel",
        "route": route,
        "turn": game_map.getTurn(),
        "used_stairs_up": game_map.getBoolProperty("used_stairs_up"),
        "used_stairs_down": game_map.getBoolProperty("used_stairs_down"),
        "visited_upper_goal": game_map.getBoolProperty("visited_upper_goal"),
        "visited_lower_goal": game_map.getBoolProperty("visited_lower_goal"),
    }


WALKTHROUGHS = {
    "multilevel": walkthrough_multilevel_map,
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
    child_output_dir = TEST_OUTPUT_DIR / "walkthroughs" / map_name
    env = os.environ.copy()
    env.update(
        {
            "GAME_TEST_WORKER": "1",
            "GAME_TEST_JOBS": "1",
            "GAME_TEST_OUTPUT_DIR": str(child_output_dir),
        }
    )
    timeout = max(30, test_duration_weight(f"GameTest.test_map_walkthrough_{map_name}", {}) * 6)
    if os.environ.get("GAME_COVERAGE_RUN") == "1":
        timeout *= 4
    try:
        completed = subprocess.run(command, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        log = {
            "map": map_name,
            "timeout_seconds": timeout,
            "stdout": (exc.stdout or "").strip(),
            "stderr": (exc.stderr or "").strip(),
            "walkthrough": fn.__name__,
        }
        write_walkthrough_log(map_name, log)
        return False, log
    log = {}
    log_path = child_output_dir / f"walkthrough_{map_name}.json"
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
    def test_resolved_rect_binding_defaults_to_empty_rect(self):
        game = load_game_module()
        bound_doc = getattr(game.CGameGraphicsObject.getResolvedRect, "__doc__", "") or ""
        self.assertIn("Return resolved runtime layout", bound_doc)

        g = game.CGameLoader.loadGame()
        plain_graphic = g.createObject("CGameGraphicsObject")
        self.assertEqual((0, 0, 0, 0), resolved_rect(plain_graphic))
        return True, ""

    @game_test
    def test_non_square_tmx_tile_layer_preserves_row_major_tile_positions(self):
        game = load_game_module()
        map_name = "unit_non_square_tmx"
        map_dir = Path.cwd() / "maps" / map_name
        map_dir.mkdir(parents=True, exist_ok=True)
        (map_dir / "config.json").write_text("{}")
        (map_dir / "script.py").write_text("")
        (map_dir / "map.json").write_text(
            json.dumps(
                {
                    "type": "map",
                    "orientation": "orthogonal",
                    "width": 3,
                    "height": 2,
                    "tilewidth": 32,
                    "tileheight": 32,
                    "properties": {"x": "0", "y": "0", "z": "0"},
                    "tilesets": [
                        {
                            "firstgid": 1,
                            "tileproperties": {
                                "0": {"type": "GrassTile"},
                                "1": {"type": "WaterTile"},
                                "2": {"type": "MountainTile"},
                            },
                        }
                    ],
                    "layers": [
                        {
                            "type": "tilelayer",
                            "name": "ground",
                            "width": 3,
                            "height": 2,
                            "properties": {
                                "level": "0",
                                "default": "GrassTile",
                                "outOfBounds": "WaterTile",
                                "xBound": "3",
                                "yBound": "2",
                            },
                            "data": [1, 2, 3, 3, 2, 99],
                        }
                    ],
                }
            )
        )

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, map_name)
        game_map = g.getMap()

        expected_tile_types = {
            (0, 0): "grass",
            (1, 0): "water",
            (2, 0): "mountain",
            (0, 1): "mountain",
            (1, 1): "water",
            (2, 1): "grass",
        }
        for (x_pos, y_pos), tile_type in expected_tile_types.items():
            self.assertEqual(tile_type, game_map.getTile(x_pos, y_pos, 0).getTileType())
        return True, ""

    @game_test
    def test_binding_validation_rejects_invalid_logger_and_dynamic_values(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        obj = g.createObject("CGameObject")

        with self.assertRaisesRegex(TypeError, "jsonify"):
            game.jsonify({"not": "a game object"})

        with self.assertRaisesRegex(TypeError, "Unsupported CGameObject property type"):
            obj.unsupported_dynamic_value = []

        try:
            with tempfile.TemporaryDirectory() as log_dir:
                try:
                    log_path = Path(log_dir) / "native.log"
                    game.set_logger_sink("stdout")
                    game.logger("stdout logger coverage")
                    game.set_logger_sink("stderr")
                    game.logger("stderr logger coverage")
                    game.set_logger_sink("file", str(log_path))
                    game.logger("file logger coverage")
                finally:
                    game.set_logger_sink("disabled", None)

            with self.assertRaisesRegex(ValueError, "Unknown logger sink"):
                game.set_logger_sink("unit-test-invalid-sink", None)

            with self.assertRaisesRegex(ValueError, "File logger sink requires a path"):
                game.set_logger_sink("file", None)
        finally:
            game.set_logger_sink("disabled", None)

        return True, json.dumps({"checked": ["jsonify", "dynamic_value", "logger_sink"]}, sort_keys=True)

    @game_test
    def test_detached_creature_player_check_and_zero_hp_ratio_are_safe(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        creature = g.createObject("CCreature")
        creature.baseStats.stamina = 0
        creature.levelStats.stamina = 0
        creature.level = 0
        creature.hp = 0

        self.assertFalse(creature.isPlayer())
        self.assertEqual(0, creature.getHpMax())
        self.assertEqual(0, creature.getHpRatio())

        creature.hp = 1
        self.assertEqual(100, creature.getHpRatio())

        return True, json.dumps({"hp_max": creature.getHpMax(), "is_player": creature.isPlayer()}, sort_keys=True)

    @game_test
    def test_cpp_plugin_manifest_registers_native_content(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        marker = g.createObject("nativePluginMarker")

        self.assertIsNotNone(marker)
        self.assertEqual("Native plugin marker", marker.getStringProperty("label"))
        self.assertEqual("Registered by a compiled C++ plugin.", marker.getStringProperty("description"))
        self.assertTrue(marker.getBoolProperty("nativePluginLoaded"))
        self.assertTrue(game.CPluginLoader.loadCppPlugin(g, "CNativeContentPlugin"))
        self.assertFalse(game.CPluginLoader.loadCppPlugin(g, "DefinitelyMissingPlugin"))

        report = {
            "marker": marker.getStringProperty("label"),
            "native": marker.getBoolProperty("nativePluginLoaded"),
        }
        return True, json.dumps(report, sort_keys=True)

    @game_test
    def test_dynamic_plugin_manifest_registers_native_content(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        marker = g.createObject("dynamicNativePluginMarker")

        self.assertIsNotNone(marker)
        self.assertEqual("Dynamic native plugin marker", marker.getStringProperty("label"))
        self.assertEqual("Registered by a dynamic C++ plugin.", marker.getStringProperty("description"))
        self.assertTrue(marker.getBoolProperty("nativePluginLoaded"))
        self.assertTrue(marker.getBoolProperty("dynamicPluginLoaded"))

        report = {
            "dynamic": marker.getBoolProperty("dynamicPluginLoaded"),
            "marker": marker.getStringProperty("label"),
        }
        return True, json.dumps(report, sort_keys=True)

    @game_test
    def test_dynamic_plugin_direct_load_and_failures(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        sample_library = "plugins/native/native_marker_plugin"

        self.assertTrue(game.CPluginLoader.loadDynamicPlugin(g, sample_library, "game_plugin_load_direct_v1"))
        marker = g.createObject("directDynamicPluginMarker")
        self.assertIsNotNone(marker)
        self.assertEqual("Direct dynamic plugin marker", marker.getStringProperty("label"))
        self.assertTrue(marker.getBoolProperty("directDynamicPluginLoaded"))

        self.assertFalse(game.CPluginLoader.loadDynamicPlugin(g, "plugins/native/definitely_missing_plugin"))
        self.assertFalse(game.CPluginLoader.loadDynamicPlugin(g, sample_library, "game_plugin_load_missing_v1"))
        self.assertFalse(game.CPluginLoader.loadDynamicPlugin(g, sample_library, "game_plugin_load_bad_api_v1"))
        self.assertFalse(game.CPluginLoader.loadDynamicPlugin(g, sample_library, "game_plugin_load_false_v1"))

        report = {
            "direct": marker.getBoolProperty("directDynamicPluginLoaded"),
            "marker": marker.getStringProperty("label"),
        }
        return True, json.dumps(report, sort_keys=True)

    @game_test
    def test_dynamic_domain_plugins_register_gameplay_classes(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()

        class_names = [
            "CEffect",
            "CInteraction",
            "CItem",
            "CWeapon",
            "CSmallWeapon",
            "CArmor",
            "CPotion",
            "CScroll",
            "CTile",
            "CMapObject",
            "CBuilding",
            "CEvent",
            "CMarket",
            "CDialog",
            "CDialogOption",
            "CDialogState",
            "CTrigger",
            "CQuest",
            "CController",
            "CTargetController",
            "CRandomController",
            "CNpcRandomController",
            "CGroundController",
            "CRangeController",
            "CPlayerController",
            "CFightController",
            "CPlayerFightController",
            "CMonsterFightController",
            "CCreature",
            "CPlayer",
        ]
        for class_name in class_names:
            with self.subTest(class_name=class_name):
                obj = g.createObject(class_name)
                self.assertIsNotNone(obj)
                self.assertEqual(class_name, obj.getType())

        item_types = set(g.getObjectHandler().getAllSubTypes("CItem"))
        map_object_types = set(g.getObjectHandler().getAllSubTypes("CMapObject"))
        player_types = set(g.getObjectHandler().getAllSubTypes("CPlayer"))
        tile_types = set(g.getObjectHandler().getAllSubTypes("CTile"))

        self.assertIn("BladeOfDarkDreams", item_types)
        self.assertIn("BladeOfDarkDreams", map_object_types)
        self.assertIn("Assasin", player_types)
        self.assertIn("BeachTile", tile_types)

        report = {
            "classes": len(class_names),
            "items": len(item_types),
            "players": sorted(player_types),
        }
        return True, json.dumps(report, sort_keys=True)

    @game_test
    def test_static_module_type_registration_initializes_runtime_factories(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        representative_types = {
            "object": ["CGameObject"],
            "core": ["CGame", "CMap", "CStats", "CListString", "CSlot", "CScript"],
            "object_model": ["CPlayer", "CTile", "CItem"],
            "handler": ["CGameEvent", "CGameEventCaused"],
            "gui": ["CLayout", "CProxyGraphicsLayout", "CGameGraphicsObject", "CStatsGraphicsObject"],
            "panel": ["CGamePanel", "CGameDialogPanel", "CGameInventoryPanel", "CListView"],
            "widget": ["CWidget", "CTextWidget", "CButton"],
            "animation": ["CAnimation", "CStaticAnimation", "CDynamicAnimation", "CSelectionBox", "CTooltip"],
        }

        created = {}
        missing = {}
        wrong_type = {}
        for category, type_names in representative_types.items():
            for type_name in type_names:
                obj = g.createObject(type_name)
                if obj is None:
                    missing.setdefault(category, []).append(type_name)
                    continue
                if obj.getType() != type_name:
                    wrong_type[type_name] = obj.getType()
                    continue
                created[type_name] = obj.getType()

        self.assertEqual({}, missing)
        self.assertEqual({}, wrong_type)
        self.assertIsNotNone(g.getObjectHandler())
        self.assertIsNotNone(g.getRngHandler())

        json_defined_types = {
            "panelKeys": "CMapStringString",
            "questionPanel": "CGameQuestionPanel",
        }
        for type_id, expected_class in json_defined_types.items():
            with self.subTest(type_id=type_id):
                obj = g.createObject(type_id)
                self.assertIsNotNone(obj)
                self.assertEqual(expected_class, obj.getType())
                self.assertEqual(type_id, obj.getTypeId())

        return True, json.dumps({"registered": sorted(created), "json": json_defined_types}, sort_keys=True)

    @game_test
    def test_config_entries_create_in_global_and_map_contexts(self):
        game = load_game_module()
        global_records = load_global_runtime_config_entry_records()
        global_visible_configs = runtime_config_values(global_records)
        checked_contexts = []
        all_created = []
        all_failed = []

        g = game.CGameLoader.loadGame()
        created, failed = check_runtime_config_entry_creation(g, global_records, global_visible_configs)
        checked_contexts.append(
            {"created": len(created), "entries": len(global_records), "failed": len(failed), "name": "global"}
        )
        all_created.extend(created)
        all_failed.extend(failed)

        for path in iter_map_runtime_config_files():
            map_name = path.parent.name
            map_records = load_map_runtime_config_entry_records(map_name)
            g = game.CGameLoader.loadGame()
            game.CGameLoader.startGame(g, map_name)
            visible_configs = dict(global_visible_configs)
            visible_configs.update(runtime_config_values(map_records))
            created, failed = check_runtime_config_entry_creation(g, map_records, visible_configs)
            checked_contexts.append(
                {"created": len(created), "entries": len(map_records), "failed": len(failed), "name": map_name}
            )
            all_created.extend(created)
            all_failed.extend(failed)

        report = {
            "contexts": checked_contexts,
            "created": len(all_created),
            "failed": all_failed,
            "totalEntries": sum(context["entries"] for context in checked_contexts),
        }
        self.assertEqual([], all_failed, json.dumps(report, sort_keys=True))
        return True, json.dumps(report, sort_keys=True)

    @game_test
    def test_game_context_owns_runtime_services_and_preserves_creation(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        context = g.getContext()
        self.assertIsNotNone(context)
        self.assertIs(context, g.getContext())

        object_handler = context.getObjectHandler()
        gui_handler = context.getGuiHandler()
        script_handler = context.getScriptHandler()
        rng_handler = context.getRngHandler()

        self.assertIs(object_handler, context.getObjectHandler())
        self.assertIs(gui_handler, context.getGuiHandler())
        self.assertIs(script_handler, context.getScriptHandler())
        self.assertIs(rng_handler, context.getRngHandler())
        self.assertIs(object_handler, g.getObjectHandler())
        self.assertIs(gui_handler, g.getGuiHandler())
        self.assertIs(rng_handler, g.getRngHandler())

        other_game = game.CGameLoader.loadGame()
        self.assertIsNot(context, other_game.getContext())
        self.assertIsNot(object_handler, other_game.getObjectHandler())
        self.assertIsNot(gui_handler, other_game.getGuiHandler())

        object_handler.registerConfigJson(
            "contextOwnedProbe",
            json.dumps(
                {
                    "class": "CGameObject",
                    "properties": {
                        "label": "context owned",
                    },
                }
            ),
        )

        probe = g.createObject("contextOwnedProbe")
        self.assertIsNotNone(probe)
        self.assertEqual("context owned", probe.getStringProperty("label"))
        self.assertIs(g, probe.getGame())
        self.assertIsNone(other_game.createObject("contextOwnedProbe"))

        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        game_map = g.getMap()
        self.assertIsNotNone(game_map)
        player = game_map.getPlayer()
        self.assertIsNotNone(player)
        self.assertEqual("CPlayer", player.getType())
        self.assertIs(g, game_map.getGame())
        self.assertIs(g, player.getGame())
        self.assertIs(context, g.getContext())

        report = {
            "map": game_map.getType(),
            "player": player.getType(),
            "probe": probe.getStringProperty("label"),
        }
        return True, json.dumps(report, sort_keys=True)

    @game_test
    def test_chest_on_enter_grants_random_loot_to_real_player(self):
        g, game_map, player = load_game_map_with_player("test", "Warrior")
        chest = game_map.getGame().createObject("chest")
        self.assertIsNotNone(chest)
        chest.setNumericProperty("value", 20)
        game_map.addObject(chest)

        class FakeEvent:
            def __init__(self, cause):
                self.cause = cause

            def getCause(self):
                return self.cause

        before_items = len(player.getItems())
        self.assertFalse(hasattr(g, "getLootHandler"))
        chest.onEnter(FakeEvent(player))
        after_items = len(player.getItems())

        self.assertGreater(after_items, before_items)
        return True, json.dumps({"before": before_items, "after": after_items}, sort_keys=True)

    @game_test
    def test_array_deserialize_skips_bad_entries_and_consumers_are_safe(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        handler = g.getObjectHandler()
        handler.registerConfigJson(
            "ArrayDeserializeRegressionCreature",
            json.dumps(
                {
                    "class": "CCreature",
                    "properties": {
                        "actions": [{"ref": "Strike"}, {"ref": "DefinitelyMissingInteraction"}],
                        "effects": [{"class": "CEffect"}, {"class": "DefinitelyMissingEffectClass"}],
                        "items": [{"ref": "LifePotion"}, {"ref": "DefinitelyMissingItem"}],
                    },
                }
            ),
        )

        creature = g.createObject("ArrayDeserializeRegressionCreature")
        self.assertIsNotNone(creature)

        actions = list(creature.getActions())
        effects = list(creature.getEffects())
        items = list(creature.getItems())

        self.assertTrue(actions)
        self.assertTrue(effects)
        self.assertTrue(items)
        self.assertNotIn(None, actions)
        self.assertNotIn(None, effects)
        self.assertNotIn(None, items)
        self.assertEqual(["Strike"], sorted(action.getTypeId() for action in actions))
        self.assertEqual(["LifePotion"], sorted(item.getTypeId() for item in items))

        # High-risk consumers should tolerate nulls defensively even if a caller bypasses deserialization.
        creature.setItems({None, g.createObject("ManaPotion")})
        creature.addItems({None, g.createObject("LesserLifePotion")})
        creature.setEffects({None, g.createObject("CEffect")})
        game.CFightHandler.applyEffects(creature)

        self.assertNotIn(None, list(creature.getItems()))
        self.assertNotIn(None, list(creature.getEffects()))
        self.assertEqual(2, len(creature.getItems()))

        return True, json.dumps(
            {
                "actions": sorted(action.getTypeId() for action in actions),
                "effects": len(effects),
                "items": sorted(item.getTypeId() for item in items),
            },
            sort_keys=True,
        )

    @game_test
    def test_dynamic_domain_plugins_serialize_clone_and_load_gameplay_content(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()

        effect = g.createObject("CEffect")
        effect.setNumericProperty("duration", 3)
        effect.setStringProperty("roundTripMarker", "effect")
        effect_clone_json = json.loads(game.jsonify(effect.clone()))
        self.assertEqual("CEffect", effect_clone_json.get("class"))
        self.assertEqual(3, effect_clone_json.get("properties", {}).get("duration"))
        self.assertEqual("effect", effect_clone_json.get("properties", {}).get("roundTripMarker"))

        market = g.createObject("CMarket")
        market.setNumericProperty("sell", 125)
        market.add(g.createObject("BladeOfDarkDreams"))
        market.add(g.createObject("LifePotion"))
        market_clone_json = json.loads(game.jsonify(market.clone()))
        market_items = market_clone_json.get("properties", {}).get("items") or []
        self.assertEqual("CMarket", market_clone_json.get("class"))
        self.assertEqual(125, market_clone_json.get("properties", {}).get("sell"))
        self.assertEqual({"BladeOfDarkDreams", "LifePotion"}, {item["properties"]["typeId"] for item in market_items})

        creature = g.createObject("CCreature")
        creature.addItem(g.createObject("BladeOfDarkDreams"))
        creature.setController(g.createObject("CTargetController"))
        creature.setFightController(g.createObject("CFightController"))
        creature_clone_json = json.loads(game.jsonify(creature.clone()))
        creature_properties = creature_clone_json.get("properties", {})
        creature_items = creature_properties.get("items") or []
        self.assertEqual("CCreature", creature_clone_json.get("class"))
        self.assertEqual({"BladeOfDarkDreams"}, {item["properties"]["typeId"] for item in creature_items})
        self.assertEqual("CTargetController", creature_properties.get("controller", {}).get("class"))
        self.assertEqual("CFightController", creature_properties.get("fightController", {}).get("class"))

        save_name = f"dynamic_domain_plugin_roundtrip_{os.getpid()}_{time.time_ns()}"
        object_name = "dynamicDomainRoundTripBlade"
        round_trip_game, game_map, _ = load_game_map_with_player("test")
        round_trip_item = round_trip_game.createObject("BladeOfDarkDreams")
        round_trip_item.name = object_name
        round_trip_item.setStringProperty("roundTripMarker", save_name)
        game_map.addObject(round_trip_item)
        round_trip_item.moveTo(game_map.getEntryX(), game_map.getEntryY(), game_map.getEntryZ())

        try:
            game.CMapLoader.save(game_map, save_name)

            loaded_game = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(loaded_game, save_name)
            loaded_item = loaded_game.getMap().getObjectByName(object_name)

            self.assertIsNotNone(loaded_item)
            self.assertEqual("CWeapon", loaded_item.getType())
            self.assertEqual("BladeOfDarkDreams", loaded_item.getTypeId())
            self.assertEqual(save_name, loaded_item.getStringProperty("roundTripMarker"))

            report = {
                "cloned_effect": effect_clone_json.get("class"),
                "cloned_market_items": sorted(item["properties"]["typeId"] for item in market_items),
                "cloned_creature_items": sorted(item["properties"]["typeId"] for item in creature_items),
                "loaded_item": {
                    "type": loaded_item.getType(),
                    "typeId": loaded_item.getTypeId(),
                },
            }
            return True, json.dumps(report, sort_keys=True)
        finally:
            cleanup_save_slot(save_name)

    @game_test
    def test_python_plugin_loader_rejects_non_resource_paths(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
            tmp.write("def load(context, game):\n    pass\n")
            absolute_path = tmp.name

        try:
            self.assertFalse(game.CPluginLoader.loadPlugin(g, absolute_path))
            self.assertFalse(game.CPluginLoader.loadPlugin(g, "../res/plugins/effect.py"))
            self.assertFalse(game.CPluginLoader.loadPlugin(g, "maps/nouraajd/not_script.py"))
            self.assertTrue(game.CPluginLoader.loadPlugin(g, "plugins/effect.py"))

            report = {
                "absolute_path_rejected": absolute_path,
                "relative_parent_rejected": "../res/plugins/effect.py",
                "non_script_map_rejected": "maps/nouraajd/not_script.py",
            }
            return True, json.dumps(report, sort_keys=True)
        finally:
            os.unlink(absolute_path)

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
        assert crafted_count == 1, "Player should receive exactly one crafted item."
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
        player.setBoolProperty("CAN_BREW_GREATER_POTIONS", True)
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
    def test_crafting_unlocks_follow_story_progression(self):
        import crafting

        g, game_map, player = load_game_map_with_player("nouraajd")
        runtime = crafting.get_runtime()

        initial_alchemy_recipes = {recipe["id"] for recipe in runtime.available_recipes(player, "alchemyTable")}
        self.assertIn("brew_life_potion", initial_alchemy_recipes)
        self.assertNotIn("blend_greater_life_potion", initial_alchemy_recipes)
        self.assertNotIn("brew_full_life_potion", initial_alchemy_recipes)
        self.assertNotIn(
            "craft_town_portal_scroll",
            {recipe["id"] for recipe in runtime.available_recipes(player, "scribeDesk")},
        )
        town_hall = g.createObject("townHallDialog")
        beren = g.createObject("berenDialog")
        town_hall.give_letter()
        beren.deliver_letter()
        scribe_recipes = {recipe["id"] for recipe in runtime.available_recipes(player, "scribeDesk")}
        self.assertIn("craft_town_portal_scroll", scribe_recipes)
        self.assertIn("scribe_emergency_portal_scroll", scribe_recipes)

        game_map.removeObjectByName("catacombs")
        beren.return_relic()
        alchemy_recipes = {recipe["id"] for recipe in runtime.available_recipes(player, "alchemyTable")}
        self.assertIn("blend_greater_life_potion", alchemy_recipes)
        self.assertIn("blend_greater_mana_potion", alchemy_recipes)
        self.assertIn("brew_full_life_potion", alchemy_recipes)
        self.assertIn("brew_full_mana_potion", alchemy_recipes)

        return True, json.dumps(
            {
                "alchemy_recipes": sorted(alchemy_recipes),
                "can_brew_greater": player.getBoolProperty("CAN_BREW_GREATER_POTIONS"),
                "can_craft_scrolls": player.getBoolProperty("CAN_CRAFT_SCROLLS"),
                "scribe_recipes": sorted(scribe_recipes),
            },
            sort_keys=True,
        )

    @game_test
    def test_crafting_locked_recipe_attempt_is_atomic(self):
        import crafting

        g, _game_map, player = load_game_map_with_player("nouraajd")
        player.setNumericProperty("gold", 500)
        player.addItem("Scroll")
        player.addItem("ManaPotion")
        player.addItem("GreaterLifePotion")
        player.addItem("GreaterLifePotion")

        before = {
            "gold": player.getNumericProperty("gold"),
            "scroll": player.countItems("Scroll"),
            "mana": player.countItems("ManaPotion"),
            "greater_life": player.countItems("GreaterLifePotion"),
            "town_portal": player.countItems("TownPortalScroll"),
            "full_life": player.countItems("FullLifePotion"),
        }

        scroll_result = crafting.craft_recipe(g, player, "craft_town_portal_scroll")
        potion_result = crafting.craft_recipe(g, player, "brew_full_life_potion")

        self.assertEqual({"ok": False, "reason": "locked"}, scroll_result)
        self.assertEqual({"ok": False, "reason": "locked"}, potion_result)
        self.assertEqual(before["gold"], player.getNumericProperty("gold"))
        self.assertEqual(before["scroll"], player.countItems("Scroll"))
        self.assertEqual(before["mana"], player.countItems("ManaPotion"))
        self.assertEqual(before["greater_life"], player.countItems("GreaterLifePotion"))
        self.assertEqual(before["town_portal"], player.countItems("TownPortalScroll"))
        self.assertEqual(before["full_life"], player.countItems("FullLifePotion"))

        return True, json.dumps({"scroll_result": scroll_result, "potion_result": potion_result}, sort_keys=True)

    @game_test
    def test_crafting_invalid_recipe_id_is_atomic(self):
        import crafting

        g, _game_map, player = load_game_map_with_player("nouraajd")
        player.setNumericProperty("gold", 123)
        player.addItem("LesserLifePotion")
        before_items = player.countItems("LesserLifePotion")

        result = crafting.craft_recipe(g, player, "not_a_real_recipe")

        self.assertEqual({"ok": False, "reason": "missing:recipe"}, result)
        self.assertEqual(123, player.getNumericProperty("gold"))
        self.assertEqual(before_items, player.countItems("LesserLifePotion"))

        return True, json.dumps(result, sort_keys=True)

    @game_test
    def test_crafting_station_options_show_recipe_states(self):
        import crafting

        game = load_game_module()
        g, game_map, player = load_game_map_with_player("nouraajd")
        player.setNumericProperty("gold", 100)
        player.addItem("LesserLifePotion")
        player.addItem("LesserLifePotion")

        class FakeEvent:
            def __init__(self, cause):
                self.cause = cause

            def getCause(self):
                return self.cause

        captured_options = []
        captured_infos = []
        original_show_selection = game.CGuiHandler.showSelection
        original_show_info = game.CGuiHandler.showInfo

        def capture_selection(self, list_string):
            options = sorted(list_string.getValues())
            captured_options.append(options)
            return crafting.LEAVE_OPTION

        def capture_info(self, message, centered=True):
            captured_infos.append((message, centered))

        try:
            game.CGuiHandler.showSelection = capture_selection
            game.CGuiHandler.showInfo = capture_info
            find_runtime_object(game_map, "alchemyTable1").onEnter(FakeEvent(player))
            find_runtime_object(game_map, "scribeDesk1").onEnter(FakeEvent(player))
        finally:
            game.CGuiHandler.showSelection = original_show_selection
            game.CGuiHandler.showInfo = original_show_info

        self.assertEqual(2, len(captured_options))
        alchemy_options, scribe_options = captured_options
        self.assertTrue(
            any(option.startswith("READY -") and "[brew_life_potion]" in option for option in alchemy_options)
        )
        self.assertTrue(
            any(option.startswith("MISSING -") and "[brew_mana_potion]" in option for option in alchemy_options)
        )
        self.assertTrue(
            any(option.startswith("LOCKED -") and "[blend_greater_life_potion]" in option for option in alchemy_options)
        )
        self.assertTrue(
            any(option.startswith("LOCKED -") and "[brew_full_life_potion]" in option for option in alchemy_options)
        )
        self.assertTrue(any("Output:" in option and "Requires:" in option for option in alchemy_options))
        self.assertTrue(
            any(option.startswith("LOCKED -") and "[craft_town_portal_scroll]" in option for option in scribe_options)
        )
        self.assertEqual([], captured_infos)

        return True, json.dumps({"alchemy": alchemy_options, "scribe": scribe_options}, sort_keys=True)

    @game_test
    def test_crafting_station_locked_missing_and_success_paths(self):
        import crafting

        game = load_game_module()
        g, game_map, player = load_game_map_with_player("nouraajd")
        player.setNumericProperty("gold", 200)

        def clear_item(item_id):
            while player.countItems(item_id) > 0:
                player.removeItem(lambda it, tid=item_id: it.getTypeId() == tid, True)

        for item_id in ("Scroll", "ManaPotion", "TownPortalScroll", "LesserLifePotion", "LifePotion"):
            clear_item(item_id)

        class FakeEvent:
            def __init__(self, cause):
                self.cause = cause

            def getCause(self):
                return self.cause

        selections = []
        captured_infos = []
        original_show_selection = game.CGuiHandler.showSelection
        original_show_info = game.CGuiHandler.showInfo

        def select_recipe(recipe_id):
            def select(options):
                return next(option for option in options if f"[{recipe_id}]" in option)

            return select

        def queued_selection(self, list_string):
            options = sorted(list_string.getValues())
            choice = selections.pop(0) if selections else crafting.LEAVE_OPTION
            return choice(options) if callable(choice) else choice

        def capture_info(self, message, centered=True):
            captured_infos.append(message)

        try:
            game.CGuiHandler.showSelection = queued_selection
            game.CGuiHandler.showInfo = capture_info

            player.addItem("Scroll")
            player.addItem("ManaPotion")
            selections[:] = [select_recipe("craft_town_portal_scroll"), crafting.LEAVE_OPTION]
            find_runtime_object(game_map, "scribeDesk1").onEnter(FakeEvent(player))
            self.assertEqual(1, player.countItems("Scroll"))
            self.assertEqual(1, player.countItems("ManaPotion"))
            self.assertEqual(0, player.countItems("TownPortalScroll"))

            player.setBoolProperty("CAN_CRAFT_SCROLLS", True)
            clear_item("Scroll")
            selections[:] = [select_recipe("craft_town_portal_scroll"), crafting.LEAVE_OPTION]
            find_runtime_object(game_map, "scribeDesk1").onEnter(FakeEvent(player))
            self.assertEqual(1, player.countItems("ManaPotion"))
            self.assertEqual(0, player.countItems("TownPortalScroll"))

            player.addItem("LesserLifePotion")
            player.addItem("LesserLifePotion")
            selections[:] = [select_recipe("brew_life_potion"), crafting.LEAVE_OPTION]
            find_runtime_object(game_map, "alchemyTable1").onEnter(FakeEvent(player))
        finally:
            game.CGuiHandler.showSelection = original_show_selection
            game.CGuiHandler.showInfo = original_show_info

        self.assertTrue(any("locked" in message.lower() for message in captured_infos))
        self.assertTrue(any("missing" in message.lower() and "Scroll" in message for message in captured_infos))
        self.assertTrue(any("You crafted Life Potion." == message for message in captured_infos))
        self.assertEqual(0, player.countItems("LesserLifePotion"))
        self.assertEqual(1, player.countItems("LifePotion"))
        self.assertEqual(180, player.getNumericProperty("gold"))

        return True, json.dumps({"messages": captured_infos}, sort_keys=True)

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
    def test_replacing_non_origin_tile_preserves_origin_tile(self):
        game = load_game_module()
        _g, game_map, player = load_game_map_with_player("test", "Warrior")
        game_map.removeAll(lambda obj: obj.getName() != "player")

        origin = game.Coords(0, 0, 0)
        adjacent = game.Coords(1, 0, 0)

        game_map.replaceTile("WaterTile", origin)
        self.assertFalse(game_map.canStep(origin))

        game_map.replaceTile("GroundTile", adjacent)

        self.assertFalse(game_map.canStep(origin))
        self.assertTrue(game_map.canStep(adjacent))

        return True, json.dumps(
            {
                "origin_walkable": game_map.canStep(origin),
                "adjacent_walkable": game_map.canStep(adjacent),
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
        game = load_game_module()
        _g, game_map, _player = load_game_map_with_player("test", "Warrior")
        active_teleporter = find_runtime_object(game_map, "teleporter1")
        teleporter = find_runtime_object(game_map, "teleporter2")
        ground_hole = find_runtime_object(game_map, "groundHole")
        active_teleporter_coords = active_teleporter.getCoords()
        teleporter_coords = teleporter.getCoords()
        ground_hole_coords = ground_hole.getCoords()
        ground_hole_target = game.Coords(ground_hole_coords.x, ground_hole_coords.y, ground_hole_coords.z - 1)

        def navigation_neighbors(obj):
            return sorted(coords_tuple(coord) for coord in game_map.getNavigationNeighbors(obj.getCoords()))

        self.assertFalse(teleporter.getBoolProperty("waypoint"))

        advance_map_only(game_map, 1)

        self.assertTrue(active_teleporter.getBoolProperty("waypoint"))
        self.assertEqual(teleporter_coords.x, active_teleporter.getNumericProperty("x"))
        self.assertEqual(teleporter_coords.y, active_teleporter.getNumericProperty("y"))
        self.assertEqual(teleporter_coords.z, active_teleporter.getNumericProperty("z"))
        self.assertIn(coords_tuple(teleporter_coords), navigation_neighbors(active_teleporter))
        self.assertFalse(teleporter.getBoolProperty("enabled"))
        self.assertFalse(teleporter.getBoolProperty("waypoint"))
        self.assertNotIn(coords_tuple(active_teleporter_coords), navigation_neighbors(teleporter))
        self.assertTrue(ground_hole.getBoolProperty("waypoint"))
        self.assertEqual(ground_hole_target.x, ground_hole.getNumericProperty("x"))
        self.assertEqual(ground_hole_target.y, ground_hole.getNumericProperty("y"))
        self.assertEqual(ground_hole_target.z, ground_hole.getNumericProperty("z"))
        self.assertIn(coords_tuple(ground_hole_target), navigation_neighbors(ground_hole))

        stable_revision = game_map.getNavigationRevision()
        active_teleporter.onTurn(None)
        ground_hole.onTurn(None)

        self.assertEqual(stable_revision, game_map.getNavigationRevision())

        active_teleporter.setBoolProperty("enabled", False)
        active_teleporter.onTurn(None)

        self.assertGreater(game_map.getNavigationRevision(), stable_revision)
        self.assertFalse(active_teleporter.getBoolProperty("waypoint"))
        self.assertNotIn(coords_tuple(teleporter_coords), navigation_neighbors(active_teleporter))

        return True, json.dumps(
            {
                "active_name": active_teleporter.getName(),
                "active_waypoint": active_teleporter.getBoolProperty("waypoint"),
                "disabled_name": teleporter.getName(),
                "disabled_enabled": teleporter.getBoolProperty("enabled"),
                "disabled_waypoint": teleporter.getBoolProperty("waypoint"),
                "revision_after_publish": stable_revision,
                "revision_after_disable": game_map.getNavigationRevision(),
            },
            sort_keys=True,
        )

    @game_test
    def test_take_mana_clamps_at_zero(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")

        creature = g.createObject("CCreature")
        stats = g.createObject("CStats")
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
        scene_manager = g.getSceneManager()
        lifecycle = []
        self.assertEqual("Idle", scene_manager.getTransitionStateName())

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
        self.assertEqual("TransitionPending", scene_manager.getTransitionStateName())
        self.assertTrue(scene_manager.isTransitionPending())
        self.assertEqual("ritual", scene_manager.getPendingMapName())
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
        self.assertEqual("Idle", scene_manager.getTransitionStateName())
        self.assertFalse(scene_manager.isTransitionPending())
        self.assertEqual("", scene_manager.getPendingMapName())

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
    def test_scene_manager_duplicate_transition_keeps_first_request(self):
        game = load_game_module()

        g, game_map, player = load_game_map_with_player("test")
        scene_manager = g.getSceneManager()
        game_map.setNumericProperty("turn", 12)

        self.assertTrue(scene_manager.requestMapChange(g, "ritual"))
        self.assertEqual("TransitionPending", scene_manager.getTransitionStateName())
        self.assertEqual("ritual", scene_manager.getPendingMapName())
        self.assertFalse(scene_manager.requestMapChange(g, "siege"))
        self.assertEqual("ritual", scene_manager.getPendingMapName())
        self.assertEqual("test", g.getMap().mapName)

        self.assertTrue(
            pump_event_loop_until(
                lambda: g.getMap().mapName == "ritual" and not scene_manager.isTransitionPending(),
                timeout=2.0,
                min_iterations=2,
            )
        )

        self.assertEqual("ritual", g.getMap().mapName)
        self.assertEqual(12, g.getMap().getTurn())
        self.assertTrue(g.getMap().getPlayer() == player)
        self.assertEqual("Idle", scene_manager.getTransitionStateName())
        self.assertEqual("", scene_manager.getPendingMapName())

        return True, json.dumps(
            {
                "destination": g.getMap().mapName,
                "pending": scene_manager.getPendingMapName(),
                "player": player.getName(),
                "turn": g.getMap().getTurn(),
            },
            sort_keys=True,
        )

    @game_test
    def test_scene_manager_real_map_transitions_preserve_player_state_and_triggers(self):
        game = load_game_module()

        g, game_map, player = load_game_map_with_player("test")
        scene_manager = g.getSceneManager()
        origin = player.getCoords()
        target = find_adjacent_walkable_tile(game_map, origin)
        player.addItem("LesserLifePotion")
        player.setNumericProperty("gold", 123)
        player.setStringProperty("sceneTransitionMarker", "kept")

        set_player_target(player, target)
        game_map.move()
        turn_after_move = game_map.getTurn()
        self.assertEqual(
            (target.x, target.y, target.z),
            (player.getCoords().x, player.getCoords().y, player.getCoords().z),
        )

        g.changeMap("ritual")
        self.assertEqual("TransitionPending", scene_manager.getTransitionStateName())
        self.assertTrue(
            pump_event_loop_until(
                lambda: g.getMap().mapName == "ritual" and not scene_manager.isTransitionPending(),
                timeout=2.0,
                min_iterations=2,
            )
        )

        ritual_map = g.getMap()
        ritual_coords = player.getCoords()
        self.assertEqual("ritual", ritual_map.mapName)
        self.assertTrue(ritual_map.getPlayer() == player)
        self.assertEqual(turn_after_move, ritual_map.getTurn())
        self.assertEqual(
            (ritual_map.getEntryX(), ritual_map.getEntryY(), ritual_map.getEntryZ()),
            (ritual_coords.x, ritual_coords.y, ritual_coords.z),
        )
        self.assertEqual("kept", player.getStringProperty("sceneTransitionMarker"))
        self.assertEqual(123, player.getNumericProperty("gold"))
        self.assertGreaterEqual(player.countItems("LesserLifePotion"), 1)
        self.assertTrue(ritual_map.getBoolProperty("ritual_initialized"))
        self.assertIn("ritualQuest", quest_names(player))

        expected_siege_turn = ritual_map.getTurn() + 2
        ritual_map.setNumericProperty("turn", expected_siege_turn)
        g.changeMap("siege")
        self.assertEqual("TransitionPending", scene_manager.getTransitionStateName())
        self.assertTrue(
            pump_event_loop_until(
                lambda: g.getMap().mapName == "siege" and not scene_manager.isTransitionPending(),
                timeout=2.0,
                min_iterations=2,
            )
        )

        siege_map = g.getMap()
        siege_coords = player.getCoords()
        self.assertEqual("siege", siege_map.mapName)
        self.assertTrue(siege_map.getPlayer() == player)
        self.assertEqual(expected_siege_turn, siege_map.getTurn())
        self.assertEqual(
            (siege_map.getEntryX(), siege_map.getEntryY(), siege_map.getEntryZ()),
            (siege_coords.x, siege_coords.y, siege_coords.z),
        )
        self.assertTrue(siege_map.getBoolProperty("siege_initialized"))
        self.assertIn("defendSiegeQuest", quest_names(player))
        self.assertGreaterEqual(player.countItems("magicWand"), 1)
        self.assertEqual("kept", player.getStringProperty("sceneTransitionMarker"))
        self.assertEqual("Idle", scene_manager.getTransitionStateName())

        return True, json.dumps(
            {
                "destination": siege_map.mapName,
                "player": player.getName(),
                "quests": quest_names(player),
                "turn": siege_map.getTurn(),
                "wands": player.countItems("magicWand"),
            },
            sort_keys=True,
        )

    @game_test
    def test_scene_manager_rejects_nested_transition_from_destination_entry(self):
        game = load_game_module()

        g, game_map, player = load_game_map_with_player("test")
        scene_manager = g.getSceneManager()
        game_map.setNumericProperty("turn", 14)

        class RedirectingStartEvent(game.CEvent):
            def onEnter(self, event):
                if event.getCause().getName() != "player":
                    return
                self.getMap().setBoolProperty("nested_redirect_seen", True)
                self.getMap().getGame().changeMap("siege")

        g.getObjectHandler().registerType("StartEvent", RedirectingStartEvent)
        g.changeMap("ritual")
        self.assertEqual("TransitionPending", scene_manager.getTransitionStateName())

        self.assertTrue(
            pump_event_loop_until(
                lambda: g.getMap().mapName == "ritual" and not scene_manager.isTransitionPending(),
                timeout=2.0,
                min_iterations=2,
            )
        )
        pump_event_loop(5)

        self.assertEqual("ritual", g.getMap().mapName)
        self.assertTrue(g.getMap().getPlayer() == player)
        self.assertEqual(14, g.getMap().getTurn())
        self.assertTrue(g.getMap().getBoolProperty("nested_redirect_seen"))
        self.assertEqual("Idle", scene_manager.getTransitionStateName())
        self.assertEqual("", scene_manager.getPendingMapName())

        return True, json.dumps(
            {
                "destination": g.getMap().mapName,
                "nested_redirect_seen": g.getMap().getBoolProperty("nested_redirect_seen"),
                "player": player.getName(),
                "turn": g.getMap().getTurn(),
            },
            sort_keys=True,
        )

    @game_test
    def test_save_load_after_scene_manager_transition_preserves_active_map_player_state(self):
        game = load_game_module()

        g, _game_map, player = load_game_map_with_player("test")
        scene_manager = g.getSceneManager()
        save_name = unique_save_name("scene_manager_transition_roundtrip")
        save_path = Path.cwd() / "save" / f"{save_name}.json"
        player.addItem("LesserLifePotion")
        player.setNumericProperty("gold", 77)
        player.setStringProperty("sceneTransitionMarker", save_name)

        try:
            g.changeMap("ritual")
            self.assertTrue(
                pump_event_loop_until(
                    lambda: g.getMap().mapName == "ritual" and not scene_manager.isTransitionPending(),
                    timeout=2.0,
                    min_iterations=2,
                )
            )
            ritual_map = g.getMap()
            self.assertTrue(ritual_map.getPlayer() == player)
            self.assertTrue(ritual_map.getBoolProperty("ritual_initialized"))
            self.assertIn("ritualQuest", quest_names(player))

            game.CMapLoader.save(ritual_map, save_name)

            loaded_game = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(loaded_game, save_name)
            loaded_map = loaded_game.getMap()
            loaded_player = loaded_map.getPlayer()
            loaded_coords = loaded_player.getCoords()

            self.assertEqual("ritual", loaded_map.mapName)
            self.assertEqual(
                (loaded_map.getEntryX(), loaded_map.getEntryY(), loaded_map.getEntryZ()),
                (loaded_coords.x, loaded_coords.y, loaded_coords.z),
            )
            self.assertEqual(save_name, loaded_player.getStringProperty("sceneTransitionMarker"))
            self.assertEqual(77, loaded_player.getNumericProperty("gold"))
            self.assertGreaterEqual(loaded_player.countItems("LesserLifePotion"), 1)
            self.assertTrue(loaded_map.getBoolProperty("ritual_initialized"))
            self.assertIn("ritualQuest", quest_names(loaded_player))

            return True, json.dumps(
                {
                    "map": loaded_map.mapName,
                    "player": loaded_player.getName(),
                    "quests": quest_names(loaded_player),
                    "save": save_name,
                },
                sort_keys=True,
            )
        finally:
            save_path.unlink(missing_ok=True)

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

        save_name = unique_save_name("toroidal_wrap_regression")
        try:
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
                    "save_slot": save_name,
                    "wrapped_horizontal": [after_horizontal.x, after_horizontal.y, after_horizontal.z],
                    "wrapped_vertical": [after_vertical.x, after_vertical.y, after_vertical.z],
                    "loaded_player": [
                        loaded_player.getCoords().x,
                        loaded_player.getCoords().y,
                        loaded_player.getCoords().z,
                    ],
                }
            )
        finally:
            cleanup_save_slot(save_name)

    @game_test
    def test_load_saved_map_slot_name_does_not_override_object_type_configs(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        save_name = "Sword"
        save_path = Path.cwd() / "save" / f"{save_name}.json"
        backup_path = save_backup_path(save_name)
        existing_save = save_path.read_text(encoding="utf-8") if save_path.exists() else None
        existing_backup = (
            backup_path.read_text(encoding="utf-8") if backup_path.exists() and backup_path.is_file() else None
        )

        try:
            game.CMapLoader.save(g.getMap(), save_name)

            loaded_game = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(loaded_game, save_name)

            sword = loaded_game.createObject("Sword")
            self.assertIsNotNone(sword)
            self.assertEqual("CWeapon", sword.getType())

            return True, json.dumps(
                {
                    "save_slot": save_name,
                    "created_type": sword.getType(),
                },
                sort_keys=True,
            )
        finally:
            if existing_save is None:
                save_path.unlink(missing_ok=True)
            else:
                save_path.parent.mkdir(exist_ok=True)
                save_path.write_text(existing_save, encoding="utf-8")
            if existing_backup is None:
                backup_path.unlink(missing_ok=True)
            else:
                backup_path.write_text(existing_backup, encoding="utf-8")

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
    def test_gui_includes_display_only_minimap_layout(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        pump_event_loop()

        gui_tree = json.loads(game.jsonify(g.getGui()))
        children = gui_tree.get("properties", {}).get("children") or []
        minimap = next((child for child in children if child.get("class") == "CMinimapGraphicsObject"), None)
        self.assertIsNotNone(minimap, "The root GUI should include the minimap HUD child.")

        minimap_props = minimap.get("properties", {})
        layout = minimap_props.get("layout", {})
        layout_props = layout.get("properties", {})
        self.assertEqual(1, minimap_props.get("priority"))
        self.assertEqual("CLayout", layout.get("class"))
        self.assertEqual(
            {"horizontal": "RIGHT", "vertical": "DOWN", "w": 220, "h": 220},
            {
                "horizontal": layout_props.get("horizontal"),
                "vertical": layout_props.get("vertical"),
                "w": int(layout_props.get("w")),
                "h": int(layout_props.get("h")),
            },
        )
        self.assertEqual("CScript", minimap_props.get("visible", {}).get("class"))

        return True, json.dumps(
            {
                "class": minimap.get("class"),
                "priority": minimap_props.get("priority"),
                "layout": {key: layout_props.get(key) for key in ("horizontal", "vertical", "w", "h")},
            },
            sort_keys=True,
        )

    @game_test
    def test_map_proxy_refresh_reuses_children_and_updates_changed_cells(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        pump_event_loop()

        gui = g.getGui()
        game_map = g.getMap()
        player = game_map.getPlayer()
        map_graph = next(child for child in collect_gui_children(gui, "CMapGraphicsObject"))

        def represented_object(graphic):
            try:
                return graphic.getObject()
            except AttributeError:
                return None

        def proxy_with_object(object_name):
            for proxy in map_graph.getChildren():
                for child in proxy.getChildren():
                    represented = represented_object(child)
                    if represented and represented.getName() == object_name:
                        return proxy
            return None

        def proxy_has_type_id(proxy, type_id):
            return any(
                represented and represented.getTypeId() == type_id
                for represented in (represented_object(child) for child in proxy.getChildren())
            )

        def has_footprint_overlay():
            for proxy in map_graph.getChildren():
                for child in proxy.getChildren():
                    represented = represented_object(child)
                    if represented and represented.getStringProperty("animation") == "images/footprint":
                        return True
            return False

        player_proxy = proxy_with_object(player.getName())
        self.assertIsNotNone(player_proxy)
        player_graphic = next(child for child in player_proxy.getChildren() if represented_object(child) == player)
        player_graphic.setNumericProperty("proxyReuseMarker", 17)
        map_graph.refreshObject(player.getCoords())
        player_proxy = proxy_with_object(player.getName())
        refreshed_player_graphic = next(
            child for child in player_proxy.getChildren() if represented_object(child) == player
        )
        self.assertEqual(17, refreshed_player_graphic.getNumericProperty("proxyReuseMarker"))

        player_coords = player.getCoords()
        marker = g.createObject("CEvent")
        marker.setStringProperty("name", "mapProxyRefreshMarker")
        marker.moveTo(player_coords.x, player_coords.y, player_coords.z)
        game_map.addObject(marker)
        pump_event_loop(5)
        self.assertIsNotNone(proxy_with_object("mapProxyRefreshMarker"))

        game_map.removeObject(marker)
        pump_event_loop(5)
        self.assertIsNone(proxy_with_object("mapProxyRefreshMarker"))

        game_map.replaceTile("LavaTile", player_coords)
        pump_event_loop(5)
        self.assertTrue(proxy_has_type_id(proxy_with_object(player.getName()), "LavaTile"))

        game_map.setBoolProperty("showCoordinates", True)
        map_graph.refreshObject(player_coords)
        self.assertTrue(
            any(child.getType() == "CTextWidget" for child in proxy_with_object(player.getName()).getChildren())
        )

        target, _, _ = find_adjacent_walkable_direction(game_map, player_coords)
        get_player_controller(player).setTarget(player, target)
        map_graph.refreshAll()
        self.assertTrue(has_footprint_overlay())

        map_graph.refreshObject(game.Coords(-1, player_coords.y, player_coords.z))
        self.assertEqual(0, sum(count == 0 for count in get_map_proxy_child_counts(g)))

        gui.setNumericProperty("width", 100)
        gui.setNumericProperty("height", 100)
        map_graph.refresh()
        self.assertGreaterEqual(len(map_graph.getChildren()), 9)

        return True, json.dumps(
            {
                "marker_removed": proxy_with_object("mapProxyRefreshMarker") is None,
                "proxy_count_after_resize": len(map_graph.getChildren()),
                "footprint_overlay": has_footprint_overlay(),
            },
            sort_keys=True,
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
        before_totals = get_panel_proxy_child_totals_by_collection(panel)

        sword = g.createObject("Sword")
        player.addItem(sword)
        after_add_without_pump = get_panel_proxy_child_totals_by_collection(panel)
        pump_event_loop()
        after_add_with_pump = get_panel_proxy_child_totals_by_collection(panel)

        player.removeItem(lambda item: item == sword, False)
        after_remove_without_pump = get_panel_proxy_child_totals_by_collection(panel)
        pump_event_loop()
        after_remove_with_pump = get_panel_proxy_child_totals_by_collection(panel)

        self.assertEqual(before_totals, after_add_without_pump)
        self.assertEqual(before_totals["inventoryCollection"] + 1, after_add_with_pump["inventoryCollection"])
        self.assertEqual(before_totals["equippedCollection"], after_add_with_pump["equippedCollection"])
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

        save_name = unique_save_name("out_of_bounds_tile_override_regression")
        try:
            game.CMapLoader.save(game_map, save_name)

            loaded_game = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(loaded_game, save_name)
            loaded_map = loaded_game.getMap()
            loaded_player = loaded_map.getPlayer()

            loaded_coords = game.Coords(25, loaded_player.getCoords().y, 0)
            self.assertEqual("WaterTile", materialized_tile_type(game, loaded_map, loaded_coords))

            return True, json.dumps(
                {
                    "save_slot": save_name,
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
        finally:
            cleanup_save_slot(save_name)

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
    def test_target_controller_flow_field_invalidates_after_navigation_change(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        game_map = g.getMap()

        for coords in [
            game.Coords(10, 10, 0),
            game.Coords(11, 10, 0),
            game.Coords(12, 10, 0),
            game.Coords(10, 11, 0),
            game.Coords(11, 11, 0),
            game.Coords(12, 11, 0),
        ]:
            game_map.replaceTile("RoadTile", coords)

        target = g.createObject("CEvent")
        target.setStringProperty("name", "flowTarget")
        game_map.addObject(target)
        target.moveTo(12, 10, 0)

        chaser = g.createObject("Cultist")
        controller = g.createObject("CTargetController")
        controller.setTarget("flowTarget")
        chaser.setController(controller)
        chaser.setBoolProperty("npc", True)
        game_map.addObject(chaser)
        chaser.moveTo(10, 10, 0)

        game_map.move()
        first_step = chaser.getCoords()
        self.assertEqual((first_step.x, first_step.y, first_step.z), (11, 10, 0))

        chaser.moveTo(10, 10, 0)
        game_map.replaceTile("WaterTile", game.Coords(11, 10, 0))
        game_map.replaceTile("WaterTile", game.Coords(9, 10, 0))
        game_map.replaceTile("WaterTile", game.Coords(10, 9, 0))

        game_map.move()
        second_step = chaser.getCoords()
        self.assertEqual((second_step.x, second_step.y, second_step.z), (10, 11, 0))
        return True, json.dumps(
            {
                "first_step": [first_step.x, first_step.y, first_step.z],
                "second_step": [second_step.x, second_step.y, second_step.z],
            }
        )

    @game_test
    def test_dynamic_controller_plugins_drive_map_movement_modes(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        game_map = g.getMap()
        player = game_map.getPlayer()

        player_start = game.Coords(20, 10, 0)
        player_target = game.Coords(21, 10, 0)
        ground_start = game.Coords(20, 12, 0)
        ground_target = ground_start
        for coords, tile_type in (
            (player_start, "RoadTile"),
            (player_target, "RoadTile"),
            (ground_start, "GroundTile"),
            (game.Coords(19, 12, 0), "WaterTile"),
            (game.Coords(20, 11, 0), "WaterTile"),
            (game.Coords(20, 13, 0), "WaterTile"),
        ):
            game_map.replaceTile(tile_type, coords)

        player.moveTo(player_start.x, player_start.y, player_start.z)
        player_controller = get_player_controller(player)
        player_controller.setTarget(player, player_target)
        self.assertFalse(player_controller.isCompleted(player))

        ground_walker = g.createObject("GoblinThief")
        ground_walker.name = "unitGroundWalker"
        ground_walker.setHp(ground_walker.getHpMax())
        ground_walker.setBoolProperty("npc", True)
        ground_walker.moveTo(ground_start.x, ground_start.y, ground_start.z)
        ground_controller = g.createObject("CGroundController")
        ground_controller.setTileType("unitMissingTileType")
        ground_walker.setController(ground_controller)
        game_map.addObject(ground_walker)

        temp_item = g.createObject("CItem")
        temp_item.name = "unitControllerTempItem"
        game_map.addObject(temp_item)
        temp_item.moveTo(22, 12, 0)
        self.assertEqual("CItem", game_map.addObjectByName("CItem", game.Coords(23, 12, 0)))
        game_map.removeAll(lambda obj: obj.getName() == "unitControllerTempItem")
        self.assertIsNone(game_map.getObjectByName("unitControllerTempItem"))

        waypoint = g.createObject("CEvent")
        waypoint.name = "unitControllerWaypoint"
        waypoint.waypoint = True
        waypoint.x = player_target.x
        waypoint.y = player_target.y
        waypoint.z = player_target.z
        game_map.addObject(waypoint)
        waypoint.moveTo(24, 12, 0)

        game_map.move()
        player_coords = player.getCoords()
        ground_coords = ground_walker.getCoords()
        self.assertEqual(
            (player_target.x, player_target.y, player_target.z), (player_coords.x, player_coords.y, player_coords.z)
        )
        self.assertEqual(
            (ground_target.x, ground_target.y, ground_target.z), (ground_coords.x, ground_coords.y, ground_coords.z)
        )
        self.assertTrue(player_controller.isCompleted(player))
        self.assertEqual("unitMissingTileType", ground_controller.getTileType())

        return True, json.dumps(
            {
                "ground": [ground_coords.x, ground_coords.y, ground_coords.z],
                "player": [player_coords.x, player_coords.y, player_coords.z],
                "turn": game_map.getTurn(),
            },
            sort_keys=True,
        )

    @game_test
    def test_generated_tiled_map_exercises_loader_metadata_and_objects(self):
        game = load_game_module()
        map_name = "generated_loader_unit"
        generated_dir = Path.cwd() / "maps" / map_name
        generated_dir.mkdir(parents=True, exist_ok=True)
        (generated_dir / "script.py").write_text("def load(self, context):\n    pass\n")
        (generated_dir / "map.json").write_text(
            json.dumps(
                {
                    "height": 3,
                    "width": 3,
                    "tileheight": 32,
                    "tilewidth": 32,
                    "type": "map",
                    "version": 1,
                    "properties": {"x": "1", "y": "1", "z": "0"},
                    "tilesets": [
                        {
                            "firstgid": 1,
                            "tileheight": 32,
                            "tilewidth": 32,
                            "tileproperties": {
                                "-1": {"type": "GroundTile"},
                                "0": {"type": "GroundTile"},
                                "1": {"type": "RoadTile"},
                                "2": {"type": "WaterTile"},
                            },
                            "tilepropertytypes": {
                                "-1": {"type": "string"},
                                "0": {"type": "string"},
                                "1": {"type": "string"},
                                "2": {"type": "string"},
                            },
                        }
                    ],
                    "layers": [
                        {
                            "data": [1, 2, 0, 2, 1, 2, 0, 2, 1],
                            "height": 3,
                            "name": "wrapped level",
                            "properties": {
                                "default": "GroundTile",
                                "level": "0",
                                "outOfBounds": "WaterTile",
                                "wrapX": "true",
                                "wrapY": 1,
                                "xBound": "2",
                                "yBound": "2",
                            },
                            "type": "tilelayer",
                            "width": 3,
                        },
                        {
                            "data": [1, 0, 0, 1],
                            "height": 2,
                            "name": "plain level",
                            "properties": {
                                "default": "GroundTile",
                                "level": "1",
                                "wrapX": False,
                                "wrapY": "0",
                                "xBound": "1",
                                "yBound": "1",
                            },
                            "type": "tilelayer",
                            "width": 2,
                        },
                        {
                            "draworder": "topdown",
                            "name": "objects",
                            "objects": [
                                {
                                    "height": 32,
                                    "name": "generatedEvent",
                                    "properties": {"enabled": True, "label": "Generated event"},
                                    "rotation": 0,
                                    "type": "CEvent",
                                    "visible": True,
                                    "width": 32,
                                    "x": 32,
                                    "y": 32,
                                },
                                {
                                    "height": 32,
                                    "name": "missingGeneratedObject",
                                    "rotation": 0,
                                    "type": "MissingGeneratedObject",
                                    "visible": True,
                                    "width": 32,
                                    "x": 64,
                                    "y": 64,
                                },
                            ],
                            "properties": {"level": "0"},
                            "type": "objectgroup",
                        },
                    ],
                },
                indent=2,
            )
        )

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, map_name)
        generated_map = g.getMap()
        generated_event = generated_map.getObjectByName("generatedEvent")

        self.assertEqual((1, 1, 0), (generated_map.getEntryX(), generated_map.getEntryY(), generated_map.getEntryZ()))
        self.assertEqual(map_name, generated_map.mapName)
        self.assertIsNotNone(generated_event)
        self.assertTrue(generated_event.enabled)
        self.assertEqual("Generated event", generated_event.label)
        self.assertIsNone(generated_map.getObjectByName("missingGeneratedObject"))
        self.assertTrue(generated_map.canStep(game.Coords(3, 1, 0)))
        self.assertFalse(generated_map.canStep(game.Coords(1, 3, 1)))

        return True, json.dumps(
            {
                "entry": [generated_map.getEntryX(), generated_map.getEntryY(), generated_map.getEntryZ()],
                "event": generated_event.getName(),
                "map": generated_map.mapName,
            },
            sort_keys=True,
        )

    @game_test
    def test_saved_quest_dependency_loader_uses_class_and_type_refs(self):
        game = load_game_module()
        map_root = Path.cwd() / "maps"
        save_name = unique_save_name("quest_dependency_loader")
        save_path = Path.cwd() / "save" / f"{save_name}.json"
        map_dirs = [
            map_root / "unit_class_source",
            map_root / "unit_type_source",
            map_root / "unit_empty_config",
            map_root / "unit_scalar_config",
            map_root / "unit_bad@map",
        ]

        try:
            class_source = map_dirs[0]
            class_source.mkdir(parents=True, exist_ok=True)
            (class_source / "script.py").write_text(
                "\n".join(
                    [
                        "def load(self, context):",
                        "    from game import CQuest, register",
                        "    @register(context)",
                        "    class UnitClassOnlyQuest(CQuest):",
                        "        pass",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (class_source / "config.json").write_text(
                json.dumps(
                    {
                        "unitClassOnlyAlias": {
                            "class": "UnitClassOnlyQuest",
                            "properties": {"description": "Class-only dependency quest"},
                        }
                    }
                ),
                encoding="utf-8",
            )

            type_source = map_dirs[1]
            type_source.mkdir(parents=True, exist_ok=True)
            (type_source / "script.py").write_text("def load(self, context):\n    pass\n", encoding="utf-8")
            (type_source / "config.json").write_text(
                json.dumps(
                    {
                        "unitTypeOnlyAlias": {
                            "class": "UnitTypeOnlyQuest",
                            "properties": {"typeId": "externalTypeQuest"},
                        }
                    }
                ),
                encoding="utf-8",
            )

            empty_config = map_dirs[2]
            empty_config.mkdir(parents=True, exist_ok=True)
            (empty_config / "config.json").write_text("[]\n", encoding="utf-8")

            scalar_config = map_dirs[3]
            scalar_config.mkdir(parents=True, exist_ok=True)
            (scalar_config / "config.json").write_text('{"notObject": false}\n', encoding="utf-8")

            invalid_map = map_dirs[4]
            invalid_map.mkdir(parents=True, exist_ok=True)

            save_path.parent.mkdir(exist_ok=True)
            save_path.write_text(
                json.dumps(
                    {
                        "class": "CMap",
                        "properties": {
                            "mapName": "ritual",
                            "turn": 7,
                            "tiles": [],
                            "triggers": [],
                            "objects": [
                                {
                                    "class": "CPlayer",
                                    "properties": {
                                        "name": "player",
                                        "posx": 3,
                                        "posy": 22,
                                        "posz": 0,
                                        "quests": [
                                            False,
                                            {"class": "CQuest"},
                                            {
                                                "class": "UnitClassOnlyQuest",
                                                "properties": {
                                                    "name": "classQuest",
                                                    "typeId": "externalClassQuest",
                                                },
                                            },
                                            {
                                                "class": "CQuest",
                                                "properties": {
                                                    "name": "typeQuest",
                                                    "typeId": "externalTypeQuest",
                                                },
                                            },
                                        ],
                                        "completedQuests": [
                                            {
                                                "class": "CQuest",
                                                "properties": {
                                                    "name": "genericCompletedQuest",
                                                    "typeId": "genericCompletedQuest",
                                                },
                                            }
                                        ],
                                    },
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )

            g = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(g, save_name)
            loaded_map = g.getMap()
            loaded_player = loaded_map.getPlayer()

            self.assertEqual("ritual", loaded_map.mapName)
            self.assertEqual(7, loaded_map.getTurn())
            self.assertEqual((3, 22, 0), coords_tuple(loaded_player.getCoords()))
            self.assertIn("externalClassQuest", quest_names(loaded_player))
            self.assertIn("externalTypeQuest", quest_names(loaded_player))
            self.assertIn("genericCompletedQuest", completed_quest_names(loaded_player))

            return True, json.dumps(
                {
                    "active": quest_names(loaded_player),
                    "completed": completed_quest_names(loaded_player),
                    "map": loaded_map.mapName,
                },
                sort_keys=True,
            )
        finally:
            save_path.unlink(missing_ok=True)
            for map_dir in map_dirs:
                shutil.rmtree(map_dir, ignore_errors=True)

    @game_test
    def test_multilevel_map_loads_authored_z_layers(self):
        game = load_game_module()
        _g, game_map, player = load_game_map_with_player("multilevel")
        object_levels = multilevel_object_layer_levels()

        self.assertEqual("multilevel", game_map.mapName)
        self.assertEqual((1, 1, 0), (game_map.getEntryX(), game_map.getEntryY(), game_map.getEntryZ()))
        self.assertEqual((1, 1, 0), coords_tuple(player.getCoords()))

        for name in (
            "multilevelStart",
            "stairsUp",
            "level0ObjectBlocker",
            "multilevelLowerGoal",
            "stairsDown",
            "level1ObjectBlocker",
            "multilevelUpperGoal",
        ):
            runtime_object = find_runtime_object(game_map, name)
            self.assertEqual(object_levels[name], runtime_object.getCoords().z)

        self.assertEqual("GroundTile", game_map.getTile(1, 1, 0).getTypeId())
        self.assertEqual("MountainTile", game_map.getTile(1, 1, 1).getTypeId())
        self.assertTrue(game_map.canStep(game.Coords(1, 1, 0)))
        self.assertFalse(game_map.canStep(game.Coords(1, 1, 1)))
        self.assertFalse(game_map.canStep(game.Coords(3, 2, 0)))
        self.assertFalse(game_map.canStep(game.Coords(5, 3, 1)))
        self.assertFalse(game_map.canStep(game.Coords(2, 2, 0)))
        self.assertTrue(game_map.canStep(game.Coords(2, 2, 1)))
        self.assertTrue(game_map.canStep(game.Coords(5, 2, 0)))
        self.assertFalse(game_map.canStep(game.Coords(5, 2, 1)))

        advance_map_only(game_map, 1)
        stairs_up = find_runtime_object(game_map, "stairsUp")
        stairs_down = find_runtime_object(game_map, "stairsDown")
        upper_goal = find_runtime_object(game_map, "multilevelUpperGoal")
        stairs_up_neighbors = sorted(
            coords_tuple(coord) for coord in game_map.getNavigationNeighbors(stairs_up.getCoords())
        )
        stairs_down_neighbors = sorted(
            coords_tuple(coord) for coord in game_map.getNavigationNeighbors(stairs_down.getCoords())
        )
        self.assertTrue(stairs_up.getBoolProperty("waypoint"))
        self.assertEqual((4, 1, 1), (stairs_up.x, stairs_up.y, stairs_up.z))
        self.assertIn((4, 1, 1), stairs_up_neighbors)
        self.assertTrue(stairs_down.getBoolProperty("waypoint"))
        self.assertEqual((4, 1, 0), (stairs_down.x, stairs_down.y, stairs_down.z))
        self.assertIn((4, 1, 0), stairs_down_neighbors)
        self.assertEqual("images/buildings/catacombs", upper_goal.getStringProperty("animation"))

        stable_revision = game_map.getNavigationRevision()
        stairs_up.onTurn(None)
        stairs_down.onTurn(None)

        self.assertEqual(stable_revision, game_map.getNavigationRevision())

        return True, json.dumps(
            {
                "entry": [game_map.getEntryX(), game_map.getEntryY(), game_map.getEntryZ()],
                "objects": {
                    name: coords_tuple(find_runtime_object(game_map, name).getCoords()) for name in object_levels
                },
                "player": coords_tuple(player.getCoords()),
                "navigation_revision": stable_revision,
            },
            sort_keys=True,
        )

    @game_test
    def test_multilevel_map_player_uses_stairs_both_directions(self):
        _game_module = load_game_module()
        _g, game_map, player = load_game_map_with_player("multilevel")
        player_name = player.getName()
        player_hp_max = player.getHpMax()
        potion_count = player.countItems("LesserLifePotion")
        player.addItem("LesserLifePotion")

        route = drive_multilevel_route(game_map, player)
        controller = get_player_controller(player)

        self.assertEqual((6, 5, 0), coords_tuple(player.getCoords()))
        self.assertTrue(controller.isCompleted(player))
        self.assertIsNotNone(player.getFightController())
        self.assertEqual(player_name, player.getName())
        self.assertEqual(player_hp_max, player.getHpMax())
        self.assertEqual(potion_count + 1, player.countItems("LesserLifePotion"))
        self.assertTrue(game_map.getBoolProperty("used_stairs_up"))
        self.assertTrue(game_map.getBoolProperty("used_stairs_down"))
        self.assertTrue(game_map.getBoolProperty("visited_upper_goal"))
        self.assertTrue(game_map.getBoolProperty("visited_lower_goal"))
        self.assertGreater(route["turns"], 0)

        return True, json.dumps(
            {
                "final_player": coords_tuple(player.getCoords()),
                "potion_count": player.countItems("LesserLifePotion"),
                "route": route,
                "turn": game_map.getTurn(),
            },
            sort_keys=True,
        )

    @game_test
    def test_multilevel_map_z_state_persists_after_save_load(self):
        game = load_game_module()
        _g, game_map, player = load_game_map_with_player("multilevel")
        stairs_up = find_runtime_object(game_map, "stairsUp")
        upper_goal = find_runtime_object(game_map, "multilevelUpperGoal")
        drive_player_to_target(game_map, player, stairs_up.getCoords(), until=lambda: player.getCoords().z == 1)
        drive_player_to_target(game_map, player, upper_goal.getCoords())
        saved_coords = coords_tuple(player.getCoords())
        saved_turn = game_map.getTurn()

        save_name = unique_save_name("multilevel_z_roundtrip")
        try:
            game.CMapLoader.save(game_map, save_name)

            loaded_game = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(loaded_game, save_name)
            loaded_map = loaded_game.getMap()
            loaded_player = loaded_map.getPlayer()

            self.assertEqual("multilevel", loaded_map.mapName)
            self.assertEqual(saved_coords, coords_tuple(loaded_player.getCoords()))
            self.assertEqual(saved_turn, loaded_map.getTurn())
            self.assertTrue(loaded_map.getBoolProperty("used_stairs_up"))
            self.assertTrue(loaded_map.getBoolProperty("visited_upper_goal"))
            self.assertIsNotNone(get_player_controller(loaded_player))
            self.assertIsNotNone(loaded_player.getFightController())

            loaded_stairs_down = find_runtime_object(loaded_map, "stairsDown")
            drive_player_to_target(
                loaded_map,
                loaded_player,
                loaded_stairs_down.getCoords(),
                until=lambda: loaded_player.getCoords().z == 0,
            )
            self.assertEqual((4, 1, 0), coords_tuple(loaded_player.getCoords()))
            self.assertTrue(loaded_map.getBoolProperty("used_stairs_down"))

            return True, json.dumps(
                {
                    "loaded_player": coords_tuple(loaded_player.getCoords()),
                    "save_slot": save_name,
                    "saved_player": saved_coords,
                    "turn": loaded_map.getTurn(),
                },
                sort_keys=True,
            )
        finally:
            cleanup_save_slot(save_name)

    @game_test
    def test_multilevel_map_stale_collision_cache_is_z_scoped(self):
        game = load_game_module()
        g, game_map, _player = load_game_map_with_player("multilevel")
        lower_probe = game.Coords(6, 1, 0)
        upper_probe = game.Coords(6, 1, 1)
        self.assertTrue(game_map.canStep(lower_probe))
        self.assertTrue(game_map.canStep(upper_probe))

        blocker = g.createObject("CEvent")
        blocker.name = "dynamicZBlocker"
        blocker.canStep = False
        game_map.addObject(blocker)
        try:
            blocker.moveTo(lower_probe.x, lower_probe.y, lower_probe.z)
            self.assertFalse(game_map.canStep(lower_probe))
            self.assertTrue(game_map.canStep(upper_probe))
            self.assertIn(blocker, game_map.getObjectsAtCoords(lower_probe))
            self.assertNotIn(blocker, game_map.getObjectsAtCoords(upper_probe))

            blocker.moveTo(upper_probe.x, upper_probe.y, upper_probe.z)
            self.assertTrue(game_map.canStep(lower_probe))
            self.assertFalse(game_map.canStep(upper_probe))
            self.assertNotIn(blocker, game_map.getObjectsAtCoords(lower_probe))
            self.assertIn(blocker, game_map.getObjectsAtCoords(upper_probe))

            return True, json.dumps(
                {
                    "blocker": blocker.getName(),
                    "lower_probe": coords_tuple(lower_probe),
                    "upper_probe": coords_tuple(upper_probe),
                },
                sort_keys=True,
            )
        finally:
            game_map.removeObject(blocker)

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

        menu_options = game.player_class_options(g)
        self.assertEqual("Warrior", menu_options.get("Warrior"))
        self.assertEqual("Inquisitor", menu_options.get("Inquisitor"))
        self.assertFalse(any(" - " in option for option in menu_options))

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

    def add_counting_event(self, game, g, game_map, type_name, object_name, coords, hits):
        class CountingEvent(game.CEvent):
            def onEnter(self, event):
                hits.append((self.getName(), event.getCause().getName()))

        g.getObjectHandler().registerType(type_name, CountingEvent)
        event = g.createObject(type_name)
        event.name = object_name
        game_map.addObject(event)
        event.moveTo(coords.x, coords.y, coords.z)
        return event

    def add_counting_tile(self, game, g, game_map, type_name, coords, hits):
        class CountingTile(game.CTile):
            def onStep(self, creature):
                hits.append((type_name, creature.getName()))

        g.getObjectHandler().registerType(type_name, CountingTile)
        g.getObjectHandler().registerConfigJson(
            type_name,
            json.dumps(
                {
                    "class": type_name,
                    "properties": {
                        "canStep": True,
                        "label": type_name,
                        "tileType": type_name,
                    },
                }
            ),
        )
        game_map.replaceTile(type_name, coords)

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
    def test_combat_initiative_status_uses_agility_order(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        attacker = g.createObject("Warrior")
        attacker.name = "slowWarrior"
        attacker.baseStats.agility = 1
        attacker.baseStats.hit = 0
        attacker.baseStats.dmgMin = 0
        attacker.baseStats.dmgMax = 0
        attacker.setFightController(g.createObject("CFightController"))
        attacker.moveTo(0, 0, 0)
        g.getMap().addObject(attacker)

        defender = g.createObject("GoblinThief")
        defender.name = "quickGoblin"
        defender.baseStats.agility = 50
        defender.baseStats.hit = 0
        defender.baseStats.dmgMin = 0
        defender.baseStats.dmgMax = 0
        defender.setFightController(g.createObject("CFightController"))
        defender.moveTo(1, 0, 0)
        g.getMap().addObject(defender)

        result = game.CFightHandler.fightMany(attacker, [defender])
        status = g.getMap().getStringProperty("combatStatus")
        self.assertFalse(result)
        self.assertIn("Initiative:", status)
        initiative_line = status.split("Initiative:", 1)[1]
        self.assertLess(initiative_line.index("Goblin Thief"), initiative_line.index("Warrior"))

        gui = g.createObject("gui")
        panel = g.createObject("CGameFightPanel")
        panel.setEnemy(defender)
        self.assertIn("Initiative:", panel.getCombatStatus(gui))

        return True, json.dumps({"resolved": result, "status": status}, sort_keys=True)

    @game_test
    def test_combat_sanitizes_opponents_and_preserves_player_quest_loot(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "empty", "Warrior")
        game_map = g.getMap()
        player = game_map.getPlayer()
        player.moveTo(0, 0, 0)
        player.setFightController(g.createObject("CFightController"))
        player.unequipArmor()
        player.setHp(1)
        player.baseStats.agility = 1
        player.baseStats.armor = 0
        player.baseStats.block = 0
        player.baseStats.hit = 0
        player.baseStats.dmgMin = 0
        player.baseStats.dmgMax = 0
        player.baseStats.crit = 0

        quest_item = g.createObject("CItem")
        quest_item.name = "unitQuestKeepsake"
        quest_item.typeId = "unitQuestKeepsake"
        quest_item.addTag(game.CTag.QUEST)
        player.addItem(quest_item)
        player.addItem("Scroll")

        winner = g.createObject("GoblinThief")
        winner.name = "unitWinningGoblin"
        winner.baseStats.agility = 100
        winner.baseStats.hit = 100
        winner.baseStats.dmgMin = 500
        winner.baseStats.dmgMax = 500
        winner.baseStats.crit = 0
        winner.moveTo(1, 0, 0)
        game_map.addObject(winner)

        dead = g.createObject("GoblinThief")
        dead.name = "unitDeadOpponent"
        dead.moveTo(1, 0, 0)
        game_map.addObject(dead)
        dead.setHp(0)

        no_controller = g.createObject("GoblinThief")
        no_controller.name = "unitNoControllerOpponent"
        no_controller.setFightController(None)
        no_controller.setHp(1)
        no_controller.moveTo(1, 0, 0)
        game_map.addObject(no_controller)

        missing_from_map = g.createObject("GoblinThief")
        missing_from_map.name = "unitMissingOpponent"

        self.assertFalse(game.CFightHandler.fightMany(winner, []))
        result = game.CFightHandler.fightMany(winner, [missing_from_map, dead, winner, no_controller, player, player])

        self.assertTrue(result)
        self.assertIsNotNone(game_map.getObjectByName(winner.getName()))
        self.assertIsNone(game_map.getObjectByName(no_controller.getName()))
        self.assertTrue(player.hasItem(lambda item: item.getName() == "unitQuestKeepsake"))
        self.assertFalse(player.hasItem(lambda item: item.getTypeId() == "Scroll"))
        self.assertTrue(winner.hasItem(lambda item: item.getTypeId() == "Scroll"))
        self.assertIn("Goblin Thief survives the encounter.", game_map.getStringProperty("combatStatus"))

        return True, json.dumps(
            {
                "quest_item_retained": player.hasItem(lambda item: item.getName() == "unitQuestKeepsake"),
                "winner": winner.getName(),
                "winner_scrolls": winner.countItems("Scroll"),
                "no_controller_removed": game_map.getObjectByName(no_controller.getName()) is None,
            },
            sort_keys=True,
        )

    @game_test
    def test_fight_bool_wrappers_preserve_outcome_compatibility(self):
        game = load_game_module()

        def new_session():
            session = game.CGameLoader.loadGame()
            game.CGameLoader.startGame(session, "empty")
            return session, session.getMap()

        def add_creature(session, game_map, type_name, name, x, hp=10):
            creature = session.createObject(type_name)
            creature.name = name
            creature.moveTo(x, 0, 0)
            game_map.addObject(creature)
            creature.setHp(hp)
            return creature

        def configure_passive(creature):
            creature.baseStats.agility = 10
            creature.baseStats.hit = 0
            creature.baseStats.dmgMin = 0
            creature.baseStats.dmgMax = 0
            creature.baseStats.crit = 0
            creature.setFightController(creature.getGame().createObject("CFightController"))

        invalid_session, invalid_map = new_session()
        invalid_attacker = add_creature(invalid_session, invalid_map, "CCreature", "unitBoolInvalidAttacker", 0)
        configure_passive(invalid_attacker)
        invalid_result = game.CFightHandler.fightMany(invalid_attacker, [])

        victory_session, victory_map = new_session()
        victor = add_creature(victory_session, victory_map, "GoblinThief", "unitBoolVictoryAttacker", 0)
        defeated = add_creature(victory_session, victory_map, "GoblinThief", "unitBoolVictoryDefender", 1, hp=1)
        victor.baseStats.agility = 100
        victor.baseStats.hit = 100
        victor.baseStats.dmgMin = 500
        victor.baseStats.dmgMax = 500
        victor.baseStats.crit = 0
        defeated.baseStats.hit = 0
        defeated.baseStats.dmgMin = 0
        defeated.baseStats.dmgMax = 0
        defeated.baseStats.crit = 0
        victory_result = game.CFightHandler.fight(victor, defeated)

        defeat_session, defeat_map = new_session()
        defeated_attacker = add_creature(defeat_session, defeat_map, "CCreature", "unitBoolDefeatedAttacker", 0, hp=1)
        killer = add_creature(defeat_session, defeat_map, "GoblinThief", "unitBoolDefeatKiller", 1)
        configure_passive(defeated_attacker)
        defeated_attacker.baseStats.agility = 1
        killer.baseStats.agility = 100
        killer.baseStats.hit = 100
        killer.baseStats.dmgMin = 500
        killer.baseStats.dmgMax = 500
        killer.baseStats.crit = 0
        defeat_result = game.CFightHandler.fightMany(defeated_attacker, [killer])

        stalled_session, stalled_map = new_session()
        stalled_attacker = add_creature(stalled_session, stalled_map, "CCreature", "unitBoolStalledAttacker", 0)
        stalled_defender = add_creature(stalled_session, stalled_map, "CCreature", "unitBoolStalledDefender", 1)
        configure_passive(stalled_attacker)
        configure_passive(stalled_defender)
        started = time.monotonic()
        stalled_result = game.CFightHandler.fightMany(stalled_attacker, [stalled_defender])
        stalled_elapsed = time.monotonic() - started

        cancelled_session, cancelled_map = new_session()
        cancelled_attacker = add_creature(cancelled_session, cancelled_map, "CCreature", "unitBoolCancelledAttacker", 0)
        cancelled_defender = add_creature(cancelled_session, cancelled_map, "CCreature", "unitBoolCancelledDefender", 1)
        configure_passive(cancelled_attacker)
        configure_passive(cancelled_defender)
        drain_sdl_events()
        push_sdl_quit_event()
        try:
            cancelled_result = game.CFightHandler.fightMany(cancelled_attacker, [cancelled_defender])
        finally:
            drain_sdl_events()

        self.assertFalse(invalid_result)
        self.assertTrue(victory_result)
        self.assertTrue(defeat_result)
        self.assertFalse(stalled_result)
        self.assertFalse(cancelled_result)
        self.assertLess(stalled_elapsed, COMBAT_STALE_LOOP_TIMEOUT_SECONDS)

        return True, json.dumps(
            {
                "cancelled": cancelled_result,
                "defeat": defeat_result,
                "invalid": invalid_result,
                "stalled": stalled_result,
                "stalled_elapsed": stalled_elapsed,
                "victory": victory_result,
            },
            sort_keys=True,
        )

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
        self.assertLess(elapsed, COMBAT_STALE_LOOP_TIMEOUT_SECONDS)
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
    def test_movement_combat_outcome_gates_visitable_on_enter(self):
        game = load_game_module()
        drain_sdl_events()

        # No-combat movement still dispatches destination visitables once.
        no_combat_game = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(no_combat_game, "empty")
        no_combat_map = no_combat_game.getMap()
        no_combat_hits = []
        no_combat_mover = no_combat_game.createObject("CCreature")
        no_combat_mover.name = "unitNoCombatMover"
        no_combat_map.addObject(no_combat_mover)
        no_combat_mover.setHp(10)
        no_combat_target = game.Coords(1, 0, 0)
        no_combat_tile_hits = []
        self.add_counting_tile(
            game,
            no_combat_game,
            no_combat_map,
            "UnitNoCombatTile",
            no_combat_target,
            no_combat_tile_hits,
        )
        self.add_counting_event(
            game,
            no_combat_game,
            no_combat_map,
            "UnitNoCombatCounter",
            "unitNoCombatCounter",
            no_combat_target,
            no_combat_hits,
        )
        no_combat_mover.moveTo(no_combat_target.x, no_combat_target.y, no_combat_target.z)
        self.assertEqual([("UnitNoCombatTile", "unitNoCombatMover")], no_combat_tile_hits)
        self.assertEqual([("unitNoCombatCounter", "unitNoCombatMover")], no_combat_hits)

        # Stalemated combat leaves the destination visitable untouched.
        stalemate_game = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(stalemate_game, "empty")
        stalemate_map = stalemate_game.getMap()
        stalemate_hits = []
        stalemate_tile_hits = []
        stalemate_mover = stalemate_game.createObject("CCreature")
        stalemate_mover.name = "unitStalemateMover"
        stalemate_mover.setFightController(stalemate_game.createObject("CFightController"))
        stalemate_map.addObject(stalemate_mover)
        stalemate_mover.setHp(10)
        stalemate_target = game.Coords(1, 0, 0)
        stale_defender = stalemate_game.createObject("CCreature")
        stale_defender.name = "unitStalemateDefender"
        stale_defender.setFightController(stalemate_game.createObject("CFightController"))
        stale_defender.moveTo(stalemate_target.x, stalemate_target.y, stalemate_target.z)
        stalemate_map.addObject(stale_defender)
        stale_defender.setHp(10)
        self.add_counting_tile(
            game,
            stalemate_game,
            stalemate_map,
            "UnitStalemateTile",
            stalemate_target,
            stalemate_tile_hits,
        )
        self.add_counting_event(
            game,
            stalemate_game,
            stalemate_map,
            "UnitStalemateCounter",
            "unitStalemateCounter",
            stalemate_target,
            stalemate_hits,
        )
        stalemate_mover.moveTo(stalemate_target.x, stalemate_target.y, stalemate_target.z)
        self.assertEqual([], stalemate_tile_hits)
        self.assertEqual([], stalemate_hits)
        self.assertIsNotNone(stalemate_map.getObjectByName("unitStalemateMover"))
        self.assertIsNotNone(stalemate_map.getObjectByName("unitStalemateDefender"))

        # Cancelled combat leaves the hostile destination tile and visitable untouched.
        cancel_game = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(cancel_game, "empty")
        cancel_map = cancel_game.getMap()
        cancel_tile_hits = []
        cancel_hits = []
        cancel_mover = cancel_game.createObject("CCreature")
        cancel_mover.name = "unitCancelMover"
        cancel_mover.setFightController(cancel_game.createObject("CFightController"))
        cancel_map.addObject(cancel_mover)
        cancel_mover.setHp(10)
        cancel_target = game.Coords(1, 0, 0)
        cancel_defender = cancel_game.createObject("CCreature")
        cancel_defender.name = "unitCancelDefender"
        cancel_defender.setFightController(cancel_game.createObject("CFightController"))
        cancel_defender.moveTo(cancel_target.x, cancel_target.y, cancel_target.z)
        cancel_map.addObject(cancel_defender)
        cancel_defender.setHp(10)
        self.add_counting_tile(
            game,
            cancel_game,
            cancel_map,
            "UnitCancelTile",
            cancel_target,
            cancel_tile_hits,
        )
        self.add_counting_event(
            game,
            cancel_game,
            cancel_map,
            "UnitCancelCounter",
            "unitCancelCounter",
            cancel_target,
            cancel_hits,
        )
        push_sdl_quit_event()
        try:
            cancel_mover.moveTo(cancel_target.x, cancel_target.y, cancel_target.z)
        finally:
            drain_sdl_events()
        self.assertEqual([], cancel_tile_hits)
        self.assertEqual([], cancel_hits)
        self.assertIsNotNone(cancel_map.getObjectByName("unitCancelMover"))
        self.assertIsNotNone(cancel_map.getObjectByName("unitCancelDefender"))

        # Attacker victory allows the original destination tile and visitable to run once.
        victory_game, victory_session, victory_attacker, victory_defenders = self.make_multi_enemy_combat_fixture()
        victory_map = victory_session.getMap()
        victory_hits = []
        victory_tile_hits = []
        victory_target = victory_defenders[0].getCoords()
        self.add_counting_tile(
            victory_game,
            victory_session,
            victory_map,
            "UnitVictoryTile",
            victory_target,
            victory_tile_hits,
        )
        self.add_counting_event(
            victory_game,
            victory_session,
            victory_map,
            "UnitVictoryCounter",
            "unitVictoryCounter",
            victory_target,
            victory_hits,
        )
        victory_attacker.moveTo(victory_target.x, victory_target.y, victory_target.z)
        self.assertEqual([("UnitVictoryTile", victory_attacker.getName())], victory_tile_hits)
        self.assertEqual([("unitVictoryCounter", victory_attacker.getName())], victory_hits)

        # After victorious combat, tile effects can move the creature again and suppress stale destination onEnter.
        relocation_game = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(relocation_game, "empty")
        relocation_map = relocation_game.getMap()
        relocation_target = game.Coords(1, 0, 0)
        relocated_target = find_adjacent_walkable_tile(relocation_map, relocation_target)
        relocation_tile_hits = []
        relocation_enter_hits = []

        class UnitRelocatingTile(game.CTile):
            def onStep(self, creature):
                relocation_tile_hits.append(("UnitRelocatingTile", creature.getName()))
                creature.moveTo(relocated_target.x, relocated_target.y, relocated_target.z)

        relocation_game.getObjectHandler().registerType("UnitRelocatingTile", UnitRelocatingTile)
        relocation_game.getObjectHandler().registerConfigJson(
            "UnitRelocatingTile",
            json.dumps(
                {
                    "class": "UnitRelocatingTile",
                    "properties": {
                        "canStep": True,
                        "label": "Relocating tile",
                        "tileType": "relocating",
                    },
                }
            ),
        )
        relocation_mover = relocation_game.createObject("Warrior")
        relocation_mover.name = "unitRelocationMover"
        relocation_mover.baseStats.hit = 100
        relocation_mover.baseStats.dmgMin = 500
        relocation_mover.baseStats.dmgMax = 500
        relocation_mover.baseStats.crit = 0
        relocation_map.addObject(relocation_mover)
        relocation_mover.setHp(10)
        relocation_defender = relocation_game.createObject("GoblinThief")
        relocation_defender.name = "unitRelocationDefender"
        relocation_defender.baseStats.hit = 0
        relocation_defender.baseStats.dmgMin = 0
        relocation_defender.baseStats.dmgMax = 0
        relocation_defender.baseStats.crit = 0
        relocation_defender.hp = 1
        relocation_defender.moveTo(relocation_target.x, relocation_target.y, relocation_target.z)
        relocation_map.addObject(relocation_defender)
        self.add_counting_event(
            game,
            relocation_game,
            relocation_map,
            "UnitRelocationCounter",
            "unitRelocationCounter",
            relocation_target,
            relocation_enter_hits,
        )
        relocation_map.replaceTile("UnitRelocatingTile", relocation_target)
        relocation_mover.moveTo(relocation_target.x, relocation_target.y, relocation_target.z)

        self.assertIsNone(relocation_map.getObjectByName("unitRelocationDefender"))
        self.assertEqual([("UnitRelocatingTile", "unitRelocationMover")], relocation_tile_hits)
        self.assertEqual([], relocation_enter_hits)
        self.assertEqual(
            (relocated_target.x, relocated_target.y, relocated_target.z),
            (relocation_mover.getCoords().x, relocation_mover.getCoords().y, relocation_mover.getCoords().z),
        )

        # Player defeat respawns silently and does not leak destination tile, destination onEnter, or entry onEnter.
        defeat_game = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(defeat_game, "empty", "Warrior")
        defeat_map = defeat_game.getMap()
        player = defeat_map.getPlayer()
        player.setFightController(defeat_game.createObject("CFightController"))
        player.unequipArmor()
        player.setHp(1)
        defeat_hits = []
        defeat_tile_hits = []
        entry = player.getCoords()
        defeat_target = find_adjacent_walkable_tile(defeat_map, entry)
        killer = defeat_game.createObject("GoblinThief")
        killer.name = "unitDefeatKiller"
        killer.baseStats.agility = 100
        killer.baseStats.hit = 100
        killer.baseStats.dmgMin = 500
        killer.baseStats.dmgMax = 500
        killer.baseStats.crit = 0
        killer.moveTo(defeat_target.x, defeat_target.y, defeat_target.z)
        defeat_map.addObject(killer)
        self.add_counting_tile(
            game,
            defeat_game,
            defeat_map,
            "UnitDefeatTile",
            defeat_target,
            defeat_tile_hits,
        )
        self.add_counting_event(
            game, defeat_game, defeat_map, "UnitEntryCounter", "unitEntryCounter", entry, defeat_hits
        )
        self.add_counting_event(
            game, defeat_game, defeat_map, "UnitDefeatCounter", "unitDefeatCounter", defeat_target, defeat_hits
        )
        player.moveTo(defeat_target.x, defeat_target.y, defeat_target.z)

        self.assertEqual([], defeat_tile_hits)
        self.assertEqual([], defeat_hits)
        self.assertEqual(
            (entry.x, entry.y, entry.z), (player.getCoords().x, player.getCoords().y, player.getCoords().z)
        )
        self.assertEqual(1, player.getHp())

        return True, json.dumps(
            {
                "cancel_hits": cancel_hits,
                "cancel_tile_hits": cancel_tile_hits,
                "defeat_tile_hits": defeat_tile_hits,
                "no_combat_hits": no_combat_hits,
                "no_combat_tile_hits": no_combat_tile_hits,
                "relocation_defender_present": relocation_map.getObjectByName("unitRelocationDefender") is not None,
                "relocation_enter_hits": relocation_enter_hits,
                "relocation_tile_hits": relocation_tile_hits,
                "stalemate_hits": stalemate_hits,
                "stalemate_tile_hits": stalemate_tile_hits,
                "victory_hits": victory_hits,
                "victory_tile_hits": victory_tile_hits,
                "defeat_hits": defeat_hits,
            },
            sort_keys=True,
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
        self.assertLess(elapsed, COMBAT_STALE_LOOP_TIMEOUT_SECONDS)
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
        stats = g.createObject("CStats")
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
        stats = g.createObject("CStats")
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
        base_stats = g.createObject("CStats")
        base_stats.hit = 0
        base_stats.crit = 0
        base_stats.dmgMin = 1
        base_stats.dmgMax = 1
        base_stats.damage = 0
        creature.baseStats = base_stats

        level_stats = g.createObject("CStats")
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
        save_dir = Path.cwd() / "save"
        save_dir.mkdir(exist_ok=True)
        save_path = save_dir / f"{save_name}.json"
        save_path.write_text('{"properties":', encoding="utf-8")

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        active_map = g.getMap()
        active_map.description = "active-before-invalid-load"
        log_path = make_temp_log_path()
        try:
            game.set_logger_sink("file", str(log_path))
            game.CGameLoader.loadSavedGame(g, save_name)
        finally:
            game.set_logger_sink("disabled", None)
            save_path.unlink(missing_ok=True)

        log_text = log_path.read_text()
        log_path.unlink(missing_ok=True)

        self.assertTrue(g.getMap() == active_map)
        self.assertEqual("active-before-invalid-load", g.getMap().description)
        self.assertIn("WARNING: Failed to parse json from", log_text)
        self.assertIn(f"save/{save_name}.json", log_text)
        self.assertIn('preview: {"properties":', log_text)
        self.assertIn("Saved game was not loaded; keeping the active map unchanged", log_text)

        return True, json.dumps({"log": log_text.strip(), "map_description": g.getMap().description})

    @game_test
    def test_legacy_save_loads_and_resaves_as_versioned_format(self):
        game = load_game_module()

        save_name = unique_save_name("legacy_save_migration")
        save_path = save_primary_path(save_name)
        cleanup_save_slot(save_name)
        save_path.parent.mkdir(exist_ok=True)
        g, game_map, _player = load_game_map_with_player("test")
        marker = f"legacy-marker-{time.time_ns()}"
        game_map.description = marker
        legacy_save = json.loads(game.jsonify(game_map))
        for obj in legacy_save.get("properties", {}).get("objects", []):
            if obj.get("properties", {}).get("name") == "player":
                obj["properties"].pop("controller", None)
                obj["properties"].pop("fightController", None)
        save_path.write_text(json.dumps(legacy_save), encoding="utf-8")

        try:
            loaded_game = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(loaded_game, save_name)
            loaded_map = loaded_game.getMap()
            loaded_player = loaded_map.getPlayer()
            self.assertEqual(marker, loaded_map.description)
            self.assertIsNotNone(get_player_controller(loaded_player))
            self.assertIsNotNone(loaded_player.getFightController())

            game.CMapLoader.save(loaded_map, save_name)
            saved_json = json.loads(save_path.read_text(encoding="utf-8"))
            snapshot = assert_save_envelope(self, saved_json, "test")
            self.assertEqual(marker, snapshot.get("properties", {}).get("description"))

            return True, json.dumps(
                {
                    "legacy_loaded": True,
                    "resaved_format": saved_json.get("format"),
                    "player_controller": type(loaded_player.getController()).__name__,
                },
                sort_keys=True,
            )
        finally:
            cleanup_save_slot(save_name)

    @game_test
    def test_old_schema_save_envelope_loads_through_migration_registry(self):
        game = load_game_module()

        save_name = unique_save_name("old_schema_migration")
        save_path = save_primary_path(save_name)
        cleanup_save_slot(save_name)
        save_path.parent.mkdir(exist_ok=True)
        _source_game, source_map, _player = load_game_map_with_player("test")
        marker = f"old-schema-marker-{time.time_ns()}"
        source_map.description = marker
        old_schema_save = {
            "format": SAVE_FORMAT,
            "schemaVersion": 0,
            "mapName": "test",
            "snapshot": json.loads(game.jsonify(source_map)),
        }
        save_path.write_text(json.dumps(old_schema_save), encoding="utf-8")

        try:
            loaded_game = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(loaded_game, save_name)
            loaded_map = loaded_game.getMap()
            self.assertEqual(marker, loaded_map.description)

            game.CMapLoader.save(loaded_map, save_name)
            saved_json = json.loads(save_path.read_text(encoding="utf-8"))
            snapshot = assert_save_envelope(self, saved_json, "test")
            self.assertEqual(marker, snapshot.get("properties", {}).get("description"))

            return True, json.dumps(
                {
                    "old_schema_loaded": True,
                    "resaved_schema": saved_json.get("schemaVersion"),
                },
                sort_keys=True,
            )
        finally:
            cleanup_save_slot(save_name)

    @game_test
    def test_legacy_save_rejects_noncanonical_player_name_without_activation(self):
        game = load_game_module()

        save_name = unique_save_name("legacy_bad_player_name")
        cleanup_save_slot(save_name)
        save_primary_path(save_name).parent.mkdir(exist_ok=True)
        _g, game_map, _player = load_game_map_with_player("test")
        legacy_save = json.loads(game.jsonify(game_map))
        for obj in legacy_save.get("properties", {}).get("objects", []):
            if obj.get("properties", {}).get("name") == "player":
                obj["properties"]["name"] = "unitPlayer"
                break
        save_primary_path(save_name).write_text(json.dumps(legacy_save), encoding="utf-8")

        loaded_game = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(loaded_game, "test", "Warrior")
        active_map = loaded_game.getMap()
        active_map.description = "active-before-bad-player"
        log_path = make_temp_log_path()
        try:
            game.set_logger_sink("file", str(log_path))
            game.CGameLoader.loadSavedGame(loaded_game, save_name)
        finally:
            game.set_logger_sink("disabled", None)
            cleanup_save_slot(save_name)

        log_text = log_path.read_text()
        log_path.unlink(missing_ok=True)
        self.assertTrue(loaded_game.getMap() == active_map)
        self.assertEqual("active-before-bad-player", loaded_game.getMap().description)
        self.assertIn("saved player object is not named player", log_text)

        return True, json.dumps({"active_description": loaded_game.getMap().description}, sort_keys=True)

    @game_test
    def test_legacy_save_rejects_invalid_nested_object_property_without_activation(self):
        game = load_game_module()

        save_name = unique_save_name("legacy_bad_nested_property")
        cleanup_save_slot(save_name)
        save_primary_path(save_name).parent.mkdir(exist_ok=True)
        _g, game_map, _player = load_game_map_with_player("test")
        legacy_save = json.loads(game.jsonify(game_map))
        for obj in legacy_save.get("properties", {}).get("objects", []):
            if obj.get("properties", {}).get("name") == "player":
                obj["properties"]["baseStats"] = {"class": "DefinitelyMissingSavedClass"}
                break
        save_primary_path(save_name).write_text(json.dumps(legacy_save), encoding="utf-8")

        loaded_game = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(loaded_game, "test", "Warrior")
        active_map = loaded_game.getMap()
        active_map.description = "active-before-bad-nested-property"
        log_path = make_temp_log_path()
        try:
            game.set_logger_sink("file", str(log_path))
            game.CGameLoader.loadSavedGame(loaded_game, save_name)
        finally:
            game.set_logger_sink("disabled", None)
            cleanup_save_slot(save_name)

        log_text = log_path.read_text()
        log_path.unlink(missing_ok=True)
        self.assertTrue(loaded_game.getMap() == active_map)
        self.assertEqual("active-before-bad-nested-property", loaded_game.getMap().description)
        self.assertIn("Cannot deserialize unresolved game object: DefinitelyMissingSavedClass", log_text)

        return True, json.dumps({"active_description": loaded_game.getMap().description}, sort_keys=True)

    @game_test
    def test_same_process_save_overwrite_loads_fresh_snapshot(self):
        game = load_game_module()

        save_name = unique_save_name("fresh_overwrite")
        cleanup_save_slot(save_name)
        g, game_map, _player = load_game_map_with_player("test")
        try:
            game_map.description = "overwrite-A"
            game.CMapLoader.save(game_map, save_name)

            first_loaded = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(first_loaded, save_name)
            self.assertEqual("overwrite-A", first_loaded.getMap().description)

            game_map.description = "overwrite-B"
            game.CMapLoader.save(game_map, save_name)

            second_loaded = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(second_loaded, save_name)
            self.assertEqual("overwrite-B", second_loaded.getMap().description)
            saved_json = json.loads(save_primary_path(save_name).read_text(encoding="utf-8"))
            snapshot = assert_save_envelope(self, saved_json, "test")
            self.assertEqual("overwrite-B", snapshot.get("properties", {}).get("description"))
            backup_json = json.loads(save_backup_path(save_name).read_text(encoding="utf-8"))
            backup_snapshot = assert_save_envelope(self, backup_json, "test")
            self.assertEqual("overwrite-A", backup_snapshot.get("properties", {}).get("description"))
            self.assertEqual([], save_temp_paths(save_name))

            return True, json.dumps(
                {
                    "backup_exists": save_backup_path(save_name).exists(),
                    "loaded_description": second_loaded.getMap().description,
                },
                sort_keys=True,
            )
        finally:
            cleanup_save_slot(save_name)

    @game_test
    def test_corrupt_primary_recovers_valid_backup(self):
        game = load_game_module()

        save_name = unique_save_name("backup_recovery")
        cleanup_save_slot(save_name)
        g, game_map, _player = load_game_map_with_player("test")
        game_map.description = "backup-valid"
        try:
            game.CMapLoader.save(game_map, save_name)
            shutil.copyfile(save_primary_path(save_name), save_backup_path(save_name))
            save_primary_path(save_name).write_text('{"snapshot":', encoding="utf-8")

            log_path = make_temp_log_path()
            try:
                game.set_logger_sink("file", str(log_path))
                loaded_game = game.CGameLoader.loadGame()
                game.CGameLoader.loadSavedGame(loaded_game, save_name)
            finally:
                game.set_logger_sink("disabled", None)

            log_text = log_path.read_text()
            log_path.unlink(missing_ok=True)

            self.assertEqual("backup-valid", loaded_game.getMap().description)
            self.assertIn("Recovered save slot from backup", log_text)
            self.assertIn("Repaired save primary from recovered backup", log_text)
            repaired_json = json.loads(save_primary_path(save_name).read_text(encoding="utf-8"))
            repaired_snapshot = assert_save_envelope(self, repaired_json, "test")
            self.assertEqual("backup-valid", repaired_snapshot.get("properties", {}).get("description"))

            return True, json.dumps({"recovered_description": loaded_game.getMap().description}, sort_keys=True)
        finally:
            cleanup_save_slot(save_name)

    @game_test
    def test_failed_primary_restore_does_not_poison_backup_recovery(self):
        game = load_game_module()

        save_name = unique_save_name("backup_after_failed_restore")
        cleanup_save_slot(save_name)
        _g, game_map, _player = load_game_map_with_player("test")
        game_map.description = "backup-after-strict-failure"
        try:
            game.CMapLoader.save(game_map, save_name)
            shutil.copyfile(save_primary_path(save_name), save_backup_path(save_name))
            primary_json = json.loads(save_primary_path(save_name).read_text(encoding="utf-8"))
            primary_json["snapshot"]["properties"]["objects"].append(
                {"class": "DefinitelyMissingSavedClass", "properties": {"name": "badPrimaryObject"}}
            )
            save_primary_path(save_name).write_text(json.dumps(primary_json), encoding="utf-8")

            log_path = make_temp_log_path()
            try:
                game.set_logger_sink("file", str(log_path))
                loaded_game = game.CGameLoader.loadGame()
                game.CGameLoader.loadSavedGame(loaded_game, save_name)
            finally:
                game.set_logger_sink("disabled", None)

            log_text = log_path.read_text()
            log_path.unlink(missing_ok=True)
            self.assertEqual("backup-after-strict-failure", loaded_game.getMap().description)
            self.assertIn("Cannot deserialize unresolved game object: DefinitelyMissingSavedClass", log_text)
            self.assertIn("Recovered save slot from backup", log_text)

            return True, json.dumps({"recovered_description": loaded_game.getMap().description}, sort_keys=True)
        finally:
            cleanup_save_slot(save_name)

    @game_test
    def test_corrupt_and_future_saves_do_not_replace_active_map(self):
        game = load_game_module()

        corrupt_name = unique_save_name("corrupt_both")
        future_name = unique_save_name("future_version")
        cleanup_save_slot(corrupt_name)
        cleanup_save_slot(future_name)
        save_primary_path(corrupt_name).parent.mkdir(exist_ok=True)
        try:
            save_primary_path(corrupt_name).write_text('{"properties":', encoding="utf-8")
            save_backup_path(corrupt_name).write_text('{"properties":', encoding="utf-8")

            g = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
            active_map = g.getMap()
            active_map.description = "active-map"
            game.CGameLoader.loadSavedGame(g, corrupt_name)
            self.assertTrue(g.getMap() == active_map)
            self.assertEqual("active-map", g.getMap().description)

            game.CMapLoader.save(active_map, future_name)
            future_json = json.loads(save_primary_path(future_name).read_text(encoding="utf-8"))
            future_json["schemaVersion"] = SAVE_SCHEMA_VERSION + 1
            save_primary_path(future_name).write_text(json.dumps(future_json), encoding="utf-8")
            save_backup_path(future_name).unlink(missing_ok=True)
            game.CGameLoader.loadSavedGame(g, future_name)
            self.assertTrue(g.getMap() == active_map)
            self.assertEqual("active-map", g.getMap().description)

            return True, json.dumps({"active_description": g.getMap().description}, sort_keys=True)
        finally:
            cleanup_save_slot(corrupt_name)
            cleanup_save_slot(future_name)

    @game_test
    def test_save_listing_filters_backup_temp_and_directory_artifacts(self):
        game = load_game_module()

        slot_name = unique_save_name("listed_slot")
        save_dir = Path.cwd() / "save"
        save_dir.mkdir(exist_ok=True)
        artifacts = [
            save_dir / f"{slot_name}.json",
            save_dir / f"{slot_name}.json.bak",
            save_dir / f"{slot_name}.json.tmp",
            save_dir / f".{slot_name}.json",
            save_dir / f".{slot_name}.json.123.tmp",
            save_dir / f"{slot_name}.txt",
        ]
        backup_only_slot = unique_save_name("backup_only_slot")
        backup_only_path = save_dir / f"{backup_only_slot}.json.bak"
        directory_artifact = save_dir / f"{slot_name}_dir.json"
        try:
            for path in artifacts:
                path.write_text("{}", encoding="utf-8")
            backup_only_path.write_text("{}", encoding="utf-8")
            directory_artifact.mkdir(exist_ok=True)

            listed = set(game.CResourcesProvider.getInstance().getFiles("SAVE"))
            self.assertIn(slot_name, listed)
            self.assertIn(backup_only_slot, listed)
            self.assertNotIn(f"{slot_name}.json", listed)
            self.assertNotIn(f"{slot_name}_dir", listed)
            self.assertNotIn(f".{slot_name}", listed)

            return True, json.dumps({"listed": sorted(name for name in listed if slot_name in name)}, sort_keys=True)
        finally:
            for path in artifacts:
                path.unlink(missing_ok=True)
            backup_only_path.unlink(missing_ok=True)
            if directory_artifact.exists():
                shutil.rmtree(directory_artifact)

    @game_test
    def test_failed_save_rotation_preserves_existing_primary(self):
        game = load_game_module()

        save_name = unique_save_name("failed_rotation")
        cleanup_save_slot(save_name)
        g, game_map, _player = load_game_map_with_player("test")
        try:
            game_map.description = "before-failed-rotation"
            game.CMapLoader.save(game_map, save_name)
            original_bytes = save_primary_path(save_name).read_bytes()

            backup_dir = save_backup_path(save_name)
            backup_dir.mkdir(exist_ok=True)
            (backup_dir / "blocker").write_text("block", encoding="utf-8")

            game_map.description = "after-failed-rotation"
            game.CMapLoader.save(game_map, save_name)

            self.assertEqual(original_bytes, save_primary_path(save_name).read_bytes())
            saved_json = json.loads(save_primary_path(save_name).read_text(encoding="utf-8"))
            snapshot = assert_save_envelope(self, saved_json, "test")
            self.assertEqual("before-failed-rotation", snapshot.get("properties", {}).get("description"))
            self.assertEqual([], save_temp_paths(save_name))

            return True, json.dumps({"primary_preserved": True}, sort_keys=True)
        finally:
            cleanup_save_slot(save_name)

    @game_test
    def test_python_backed_nouraajd_object_round_trips_through_save(self):
        game = load_game_module()

        save_name = unique_save_name("python_backed_object")
        cleanup_save_slot(save_name)
        g, game_map, player = load_game_map_with_player("nouraajd")
        marker = f"python-backed-{time.time_ns()}"
        event = g.createObject("StartEvent")
        event.name = "unitPythonBackedStartEvent"
        event.setStringProperty("roundTripMarker", marker)
        game_map.addObject(event)
        event.moveTo(player.getCoords().x, player.getCoords().y, player.getCoords().z)
        try:
            game.CMapLoader.save(game_map, save_name)

            loaded_game = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(loaded_game, save_name)
            loaded_event = loaded_game.getMap().getObjectByName("unitPythonBackedStartEvent")

            self.assertIsNotNone(loaded_event)
            self.assertEqual("StartEvent", loaded_event.getType())
            self.assertEqual("StartEvent", loaded_event.getTypeId())
            self.assertEqual(marker, loaded_event.getStringProperty("roundTripMarker"))

            return True, json.dumps(
                {
                    "loaded_type": loaded_event.getType(),
                    "marker": loaded_event.getStringProperty("roundTripMarker"),
                },
                sort_keys=True,
            )
        finally:
            cleanup_save_slot(save_name)

    @game_test
    def test_nouraajd_snapshot_restores_runtime_state_and_single_claim_rewards(self):
        game = load_game_module()
        original_show_message = game.CGuiHandler.showMessage
        try:
            game.CGuiHandler.showMessage = lambda self, message: None
            save_name = unique_save_name("nouraajd_state_roundtrip")
            cleanup_save_slot(save_name)
            g, game_map, player = load_game_map_with_player("nouraajd")

            target = find_adjacent_walkable_tile(game_map, player.getCoords())
            drive_player_to_target(game_map, player, target, max_turns=4)
            player.addItem("LifePotion")
            player.addQuest("octoBogzQuest")
            game_map.setBoolProperty("unitSaveFlag", True)

            weapon = player.getWeapon()
            weapon_type = weapon.getTypeId() if weapon else ""

            game_map.removeObjectByName("cave1")
            self.assertIsNone(game_map.getObjectByName("cave1"))
            self.assertIsNotNone(game_map.getObjectByName("gooby1"))
            game_map.removeObjectByName("catacombs")
            game_map.removeObjectByName("cave2")
            player.checkQuests()

            saved_coords = coords_tuple(player.getCoords())
            saved_turn = game_map.getTurn()
            saved_gold = player.getGold()
            saved_shadow_blades = player.countItems("ShadowBlade")
            saved_life_potions = player.countItems("LifePotion")

            game.CMapLoader.save(game_map, save_name)

            loaded_game = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(loaded_game, save_name)
            loaded_map = loaded_game.getMap()
            loaded_player = loaded_map.getPlayer()

            self.assertEqual("nouraajd", loaded_map.mapName)
            self.assertEqual(saved_coords, coords_tuple(loaded_player.getCoords()))
            self.assertEqual(saved_turn, loaded_map.getTurn())
            self.assertTrue(loaded_map.getBoolProperty("unitSaveFlag"))
            self.assertEqual(saved_life_potions, loaded_player.countItems("LifePotion"))
            self.assertEqual(weapon_type, loaded_player.getWeapon().getTypeId() if loaded_player.getWeapon() else "")
            self.assertIsNone(loaded_map.getObjectByName("cave1"))
            self.assertIsNone(loaded_map.getObjectByName("catacombs"))
            self.assertIsNone(loaded_map.getObjectByName("cave2"))
            self.assertIsNotNone(loaded_map.getObjectByName("gooby1"))
            self.assertTrue(loaded_player.hasItem(lambda it: it.getName() == "skullOfRolf"))
            self.assertTrue(loaded_player.hasItem(lambda it: it.getName() == "holyRelic"))
            self.assertEqual(saved_gold, loaded_player.getGold())
            self.assertEqual(saved_shadow_blades, loaded_player.countItems("ShadowBlade"))
            self.assertIsNotNone(get_player_controller(loaded_player))
            self.assertIsNotNone(loaded_player.getFightController())

            loaded_player.checkQuests()
            self.assertEqual(saved_gold, loaded_player.getGold())
            self.assertEqual(saved_shadow_blades, loaded_player.countItems("ShadowBlade"))

            loaded_map.removeObjectByName("gooby1")
            self.assertTrue(loaded_map.getBoolProperty("completed_gooby"))

            return True, json.dumps(
                {
                    "coords": saved_coords,
                    "turn": saved_turn,
                    "gold": loaded_player.getGold(),
                    "shadow_blades": loaded_player.countItems("ShadowBlade"),
                    "weapon": weapon_type,
                },
                sort_keys=True,
            )
        finally:
            game.CGuiHandler.showMessage = original_show_message
            cleanup_save_slot(save_name)

    @game_test
    def test_invalid_save_slot_names_are_rejected(self):
        game = load_game_module()

        unique = str(time.time_ns())
        invalid_slots = [f"../evil_{unique}", f"a/b_{unique}", f".hidden_{unique}"]
        potential_writes = [
            Path.cwd() / f"evil_{unique}.json",
            Path.cwd() / f"evil_{unique}.json.bak",
            Path.cwd() / "save" / "a" / f"b_{unique}.json",
            Path.cwd() / "save" / "a" / f"b_{unique}.json.bak",
            Path.cwd() / "save" / f".hidden_{unique}.json",
            Path.cwd() / "save" / f".hidden_{unique}.json.bak",
        ]

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        game_map = g.getMap()

        log_path = make_temp_log_path()
        try:
            game.set_logger_sink("file", str(log_path))
            for slot_name in invalid_slots:
                game.CMapLoader.save(game_map, slot_name)
                loaded_game = game.CGameLoader.loadGame()
                game.CGameLoader.startGameWithPlayer(loaded_game, "test", "Warrior")
                active_map = loaded_game.getMap()
                game.CGameLoader.loadSavedGame(loaded_game, slot_name)
                self.assertTrue(loaded_game.getMap() == active_map)
        finally:
            game.set_logger_sink("disabled", None)

        log_text = log_path.read_text()
        log_path.unlink(missing_ok=True)

        for written_path in potential_writes:
            self.assertFalse(written_path.exists(), f"Unexpected write for invalid slot: {written_path}")
        self.assertIn("WARNING: Rejected invalid save slot name during save:", log_text)
        self.assertIn("WARNING: Rejected invalid save slot name during load:", log_text)

        return True, json.dumps(
            {
                "invalid_slots": invalid_slots,
                "blocked_paths": [str(path) for path in potential_writes],
            }
        )

    @game_test
    def test_malformed_save_envelopes_are_rejected_without_activation(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        active_map = g.getMap()
        active_marker = f"active-envelope-guard-{time.time_ns()}"
        active_map.description = active_marker
        valid_snapshot = json.loads(game.jsonify(active_map))
        mismatched_snapshot = json.loads(json.dumps(valid_snapshot))
        mismatched_snapshot["properties"]["mapName"] = "empty"
        wrong_class_snapshot = json.loads(json.dumps(valid_snapshot))
        wrong_class_snapshot["class"] = "CCreature"

        cases = [
            (
                "root_array",
                [],
                "save root is not a JSON object",
            ),
            (
                "wrong_format",
                {"format": "other-format", "schemaVersion": SAVE_SCHEMA_VERSION},
                "unsupported save format",
            ),
            (
                "missing_schema",
                {"format": SAVE_FORMAT, "mapName": "test", "snapshot": valid_snapshot},
                "save envelope is missing integer schemaVersion",
            ),
            (
                "missing_map_name",
                {"format": SAVE_FORMAT, "schemaVersion": SAVE_SCHEMA_VERSION, "snapshot": valid_snapshot},
                "save envelope is missing string mapName",
            ),
            (
                "invalid_map_name",
                {
                    "format": SAVE_FORMAT,
                    "schemaVersion": SAVE_SCHEMA_VERSION,
                    "mapName": "../test",
                    "snapshot": valid_snapshot,
                },
                "save envelope contains invalid mapName",
            ),
            (
                "missing_snapshot",
                {"format": SAVE_FORMAT, "schemaVersion": SAVE_SCHEMA_VERSION, "mapName": "test"},
                "save envelope is missing object snapshot",
            ),
            (
                "wrong_snapshot_class",
                {
                    "format": SAVE_FORMAT,
                    "schemaVersion": SAVE_SCHEMA_VERSION,
                    "mapName": "test",
                    "snapshot": wrong_class_snapshot,
                },
                "save snapshot is missing a valid CMap mapName",
            ),
            (
                "map_mismatch",
                {
                    "format": SAVE_FORMAT,
                    "schemaVersion": SAVE_SCHEMA_VERSION,
                    "mapName": "test",
                    "snapshot": mismatched_snapshot,
                },
                "save envelope mapName does not match snapshot mapName",
            ),
        ]

        slots = []
        log_path = make_temp_log_path()
        try:
            game.set_logger_sink("file", str(log_path))
            for suffix, document, _expected in cases:
                slot_name = unique_save_name(f"malformed_envelope_{suffix}")
                slots.append(slot_name)
                cleanup_save_slot(slot_name)
                save_primary_path(slot_name).parent.mkdir(exist_ok=True)
                save_primary_path(slot_name).write_text(json.dumps(document), encoding="utf-8")

                game.CGameLoader.loadSavedGame(g, slot_name)
                self.assertTrue(g.getMap() == active_map)
                self.assertEqual(active_marker, g.getMap().description)
        finally:
            game.set_logger_sink("disabled", None)
            for slot_name in slots:
                cleanup_save_slot(slot_name)

        log_text = log_path.read_text()
        log_path.unlink(missing_ok=True)
        for _suffix, _document, expected in cases:
            self.assertIn(expected, log_text)

        return True, json.dumps(
            {
                "cases": [suffix for suffix, _document, _expected in cases],
                "active_description": g.getMap().description,
            },
            sort_keys=True,
        )

    @game_test
    def test_strict_save_deserialization_rejects_partial_snapshot_without_activation(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        active_map = g.getMap()
        active_marker = f"active-strict-guard-{time.time_ns()}"
        active_map.description = active_marker
        snapshot = json.loads(game.jsonify(active_map))
        cases = [
            (
                "missing_class",
                {},
                "Cannot deserialize unresolved game object: <unknown>",
            ),
            (
                "non_object",
                None,
                "Cannot deserialize a missing or non-object game object",
            ),
            (
                "missing_type",
                {"class": "DefinitelyMissingSavedClass", "properties": {"name": "badSavedObject"}},
                "Cannot deserialize unresolved game object: DefinitelyMissingSavedClass",
            ),
        ]

        slots = []
        log_path = make_temp_log_path()
        try:
            game.set_logger_sink("file", str(log_path))
            for suffix, bad_object, _expected in cases:
                slot_name = unique_save_name(f"strict_restore_{suffix}")
                slots.append(slot_name)
                cleanup_save_slot(slot_name)
                save_primary_path(slot_name).parent.mkdir(exist_ok=True)
                saved_document = {
                    "format": SAVE_FORMAT,
                    "schemaVersion": SAVE_SCHEMA_VERSION,
                    "mapName": "test",
                    "snapshot": json.loads(json.dumps(snapshot)),
                }
                saved_document["snapshot"]["properties"]["objects"].append(bad_object)
                save_primary_path(slot_name).write_text(json.dumps(saved_document), encoding="utf-8")

                game.CGameLoader.loadSavedGame(g, slot_name)
                self.assertTrue(g.getMap() == active_map)
                self.assertEqual(active_marker, g.getMap().description)
        finally:
            game.set_logger_sink("disabled", None)
            for slot_name in slots:
                cleanup_save_slot(slot_name)

        log_text = log_path.read_text()
        log_path.unlink(missing_ok=True)
        for _suffix, _bad_object, expected in cases:
            self.assertIn(expected, log_text)

        return True, json.dumps(
            {
                "cases": [suffix for suffix, _bad_object, _expected in cases],
                "active_description": g.getMap().description,
            },
            sort_keys=True,
        )

    @game_test
    def test_strict_save_rejects_duplicate_object_names_without_activation(self):
        game = load_game_module()

        save_name = unique_save_name("strict_restore_duplicate_object")
        cleanup_save_slot(save_name)
        save_primary_path(save_name).parent.mkdir(exist_ok=True)
        _source_game, source_map, _player = load_game_map_with_player("test")
        saved_document = {
            "format": SAVE_FORMAT,
            "schemaVersion": SAVE_SCHEMA_VERSION,
            "mapName": "test",
            "snapshot": json.loads(game.jsonify(source_map)),
        }
        player_object = None
        for obj in saved_document["snapshot"]["properties"]["objects"]:
            if obj.get("properties", {}).get("name") == "player":
                player_object = json.loads(json.dumps(obj))
                break
        self.assertIsNotNone(player_object)
        saved_document["snapshot"]["properties"]["objects"].append(player_object)
        save_primary_path(save_name).write_text(json.dumps(saved_document), encoding="utf-8")

        loaded_game = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(loaded_game, "test", "Warrior")
        active_map = loaded_game.getMap()
        active_map.description = "active-before-duplicate-object"
        log_path = make_temp_log_path()
        try:
            game.set_logger_sink("file", str(log_path))
            game.CGameLoader.loadSavedGame(loaded_game, save_name)
        finally:
            game.set_logger_sink("disabled", None)
            cleanup_save_slot(save_name)

        log_text = log_path.read_text()
        log_path.unlink(missing_ok=True)
        self.assertTrue(loaded_game.getMap() == active_map)
        self.assertEqual("active-before-duplicate-object", loaded_game.getMap().description)
        self.assertIn("Saved map contains duplicate object name: player", log_text)

        return True, json.dumps({"active_description": loaded_game.getMap().description}, sort_keys=True)

    @game_test
    def test_objects(self):
        game = load_game_module()

        exclusions = load_type_registration_exclusions()
        config_metadata = load_runtime_config_type_metadata()
        class_categories = load_registered_class_categories()
        failed = []
        skipped = []
        created = []
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        for type_id in sorted(g.getObjectHandler().getAllTypes()):
            details = runtime_type_details(type_id, config_metadata, class_categories)
            exclusion = exclusions.get(type_id) or exclusions.get(details["className"])
            if exclusion:
                skipped.append({**details, "exclusion": exclusion})
                continue
            try:
                obj = g.createObject(type_id)
            except Exception as exc:
                failed.append({**details, "error": f"{type(exc).__name__}: {exc}"})
                continue
            if not obj:
                failed.append({**details, "error": "createObject returned None"})
                continue
            created.append({**details, "actualType": obj.getType(), "actualTypeId": obj.getTypeId()})
        report = {
            "created": len(created),
            "failed": failed,
            "skippedReviewedExclusions": skipped,
            "totalTypes": len(created) + len(failed) + len(skipped),
        }
        self.assertEqual([], failed, json.dumps(report, sort_keys=True))
        return True, json.dumps(report, sort_keys=True)

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

        stats = g.createObject("CStats")
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

        damage = g.createObject("CDamage")
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
        self.assertFalse(dialog.invokeCondition("missing"))
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
    def test_python_registered_gameplay_wrappers_survive_native_plugin_split(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        handler = g.getObjectHandler()
        calls = []

        class PyBuilding(game.CBuilding):
            def onEnter(self, event):
                calls.append(("building_enter", self.getName()))

        class PyEvent(game.CEvent):
            def onCreate(self, event):
                calls.append(("event_create", self.getName()))

        class PyInteraction(game.CInteraction):
            def performAction(self, first, second):
                calls.append(("interaction_perform", first.getName(), second.getName()))

            def configureEffect(self, effect):
                calls.append(("interaction_configure", effect.getName()))
                return True

        class PyEffect(game.CEffect):
            def onEffect(self):
                calls.append(("effect_tick", self.getName()))

        class PyTile(game.CTile):
            def onStep(self, creature):
                calls.append(("tile_step", creature.getName()))

        class PyPotion(game.CPotion):
            def onUse(self, event):
                calls.append(("potion_use", self.getName()))

        class PyScroll(game.CScroll):
            def onUse(self, event):
                calls.append(("scroll_use", self.getName()))

            def isDisposable(self):
                return True

        class PyTrigger(game.CTrigger):
            def trigger(self, obj, event):
                calls.append(("trigger", self.getName()))

        class PyQuest(game.CQuest):
            def isCompleted(self):
                return True

            def getObjective(self):
                return "Python registered objective"

        class PyPlugin(game.CPlugin):
            def load(self, context):
                calls.append(("plugin_load", context.getType()))

        class PyDialog(game.CDialog):
            def invokeAction(self, action):
                calls.append(("dialog_action", action))

            def invokeCondition(self, condition):
                calls.append(("dialog_condition", condition))
                return condition == "ready"

        registered_classes = {
            "PyBuilding": PyBuilding,
            "PyEvent": PyEvent,
            "PyInteraction": PyInteraction,
            "PyEffect": PyEffect,
            "PyTile": PyTile,
            "PyPotion": PyPotion,
            "PyScroll": PyScroll,
            "PyTrigger": PyTrigger,
            "PyQuest": PyQuest,
            "PyPlugin": PyPlugin,
            "PyDialog": PyDialog,
        }
        for name, cls in registered_classes.items():
            handler.registerType(name, cls)

        created = {name: handler.createObject(g, name) for name in registered_classes}
        for name, obj in created.items():
            obj.name = name
            self.assertEqual(name, obj.getName())

        actor = g.createObject("CCreature")
        actor.name = "pyActor"
        effect = created["PyEffect"]
        game.CBuilding.onEnter(created["PyBuilding"], None)
        game.CEvent.onCreate(created["PyEvent"], None)
        game.CInteraction.performAction(created["PyInteraction"], actor, actor)
        self.assertTrue(game.CInteraction.configureEffect(created["PyInteraction"], effect))
        game.CEffect.onEffect(effect)
        game.CTile.onStep(created["PyTile"], actor)
        game.CPotion.onUse(created["PyPotion"], None)
        game.CScroll.onUse(created["PyScroll"], None)
        self.assertTrue(game.CScroll.isDisposable(created["PyScroll"]))
        game.CTrigger.trigger(created["PyTrigger"], None, None)
        self.assertTrue(game.CQuest.isCompleted(created["PyQuest"]))
        self.assertEqual("Python registered objective", game.CQuest.getObjective(created["PyQuest"]))
        game.CPlugin.load(created["PyPlugin"], g)
        game.CDialogBase2.invokeAction(created["PyDialog"], "open")
        self.assertTrue(game.CDialogBase2.invokeCondition(created["PyDialog"], "ready"))

        return True, json.dumps({"calls": calls, "registered": sorted(created)}, sort_keys=True)

    @game_test
    def test_quest_callbacks_cover_base_registered_and_wrapper_paths(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")

        base = g.createObject("CQuest")
        self.assertEqual("", base.getObjective())
        self.assertEqual("", base.getReward())
        self.assertEqual("", base.getHint())
        base.description = "Inspect the old road."
        base.objective = "Find the missing stones."
        base.reward = "A tidy sum."
        base.hint = "Start near the gate."
        self.assertEqual("Find the missing stones.", base.getObjective())
        self.assertEqual("A tidy sum.", base.getReward())
        self.assertEqual("Start near the gate.", base.getHint())

        direct_calls = []

        class DirectQuest(game.CQuest):
            def isCompleted(self):
                return True

            def onComplete(self):
                direct_calls.append("complete")

            def getObjective(self):
                return "Direct objective"

            def getReward(self):
                return "Direct reward"

            def getHint(self):
                return "Direct hint"

        direct = DirectQuest()
        self.assertTrue(direct.isCompleted())
        direct.onComplete()
        self.assertEqual(["complete"], direct_calls)
        self.assertEqual("Direct objective", direct.getObjective())
        self.assertEqual("Direct reward", direct.getReward())
        self.assertEqual("Direct hint", direct.getHint())
        self.assertTrue(game.CQuest.isCompleted(direct))
        game.CQuest.onComplete(direct)
        self.assertEqual(["complete", "complete"], direct_calls)
        self.assertEqual("Direct objective", game.CQuest.getObjective(direct))
        self.assertEqual("Direct reward", game.CQuest.getReward(direct))
        self.assertEqual("Direct hint", game.CQuest.getHint(direct))

        event_calls = []

        class DirectEvent(game.CEvent):
            def onEnter(self, event):
                event_calls.append(("enter", event))

            def onLeave(self, event):
                event_calls.append(("leave", event))

        direct_event = DirectEvent()
        game.CEvent.onEnter(direct_event, None)
        game.CEvent.onLeave(direct_event, None)
        self.assertEqual([("enter", None), ("leave", None)], event_calls)

        dialog_calls = []

        class DirectDialog(game.CDialog):
            def invokeAction(self, action):
                dialog_calls.append(action)

            def invokeCondition(self, condition):
                return condition == "ready"

        direct_dialog = DirectDialog()
        game.CDialogBase2.invokeAction(direct_dialog, "open")
        self.assertTrue(game.CDialogBase2.invokeCondition(direct_dialog, "ready"))
        self.assertEqual(["open"], dialog_calls)

        class RaisingTextQuest(game.CQuest):
            def getObjective(self):
                raise RuntimeError("objective failed")

            def getReward(self):
                raise RuntimeError("reward failed")

            def getHint(self):
                raise RuntimeError("hint failed")

        raising = RaisingTextQuest()
        raising.objective = "Fallback objective"
        raising.reward = "Fallback reward"
        raising.hint = "Fallback hint"
        self.assertEqual("Fallback objective", game.CQuest.getObjective(raising))
        self.assertEqual("Fallback reward", game.CQuest.getReward(raising))
        self.assertEqual("Fallback hint", game.CQuest.getHint(raising))

        @game.register(g)
        class UnitRegisteredQuest(game.CQuest):
            def isCompleted(self):
                return True

            def onComplete(self):
                self.setBoolProperty("unit_completed", True)

            def getObjective(self):
                return "Registered objective"

            def getReward(self):
                return "Registered reward"

            def getHint(self):
                return "Registered hint"

        registered = g.createObject("UnitRegisteredQuest")
        self.assertTrue(game.CQuest.isCompleted(registered))
        game.CQuest.onComplete(registered)
        self.assertTrue(registered.getBoolProperty("unit_completed"))
        self.assertEqual("Registered objective", game.CQuest.getObjective(registered))
        self.assertEqual("Registered reward", game.CQuest.getReward(registered))
        self.assertEqual("Registered hint", game.CQuest.getHint(registered))

        serialized = json.loads(game.jsonify(base))["properties"]
        return True, json.dumps(
            {
                "base": {
                    "description": serialized["description"],
                    "hint": base.getHint(),
                    "objective": base.getObjective(),
                    "reward": base.getReward(),
                },
                "registered": {
                    "hint": registered.getHint(),
                    "objective": registered.getObjective(),
                    "reward": registered.getReward(),
                },
            },
            sort_keys=True,
        )

    @game_test
    def test_stats_bonus_text_and_custom_collection_roundtrips(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")

        base = g.createObject("CStats")
        base.mainStat = "strength"
        base.strength = 4
        base.agility = 2
        base.dmgMin = 1
        base.dmgMax = 3
        base.hit = 50
        base.crit = 5

        bonus = g.createObject("CStats")
        bonus.strength = 6
        bonus.damage = 2
        bonus.attack = 10
        bonus.block = 3
        bonus.armor = 7

        base.addBonus(bonus)
        self.assertEqual(10, base.getMainValue())
        self.assertEqual(3, base.dmgMin + base.damage)
        text_after_bonus = base.getText(7)
        self.assertIn("Level: 7", text_after_bonus)
        self.assertIn("Strength: 10", text_after_bonus)
        self.assertIn("Damage: 3-5", text_after_bonus)
        self.assertIn("Hit: 60%", text_after_bonus)
        self.assertIn("Armor: 7%", text_after_bonus)

        base.removeBonus(bonus)
        self.assertEqual(4, base.getMainValue())
        self.assertEqual(0, base.damage)
        self.assertEqual(0, base.attack)

        list_string = g.createObject("CListString")
        list_string.setValues({"north", "south"})
        list_string.addValue("west")

        list_int = g.createObject("CListInt")
        list_int.setValues({1, 3})
        list_int.addValue(5)

        map_string_string = g.createObject("CMapStringString")
        map_string_string.setValues({"i": "inventoryPanel", "j": "questPanel"})

        map_string_int = g.createObject("CMapStringInt")
        map_string_int.setValues({"CMapObject": 1, "CCreature": 2})

        map_int_string = g.createObject("CMapIntString")
        map_int_string.setValues({0: "GroundTile", 1: "WaterTile"})

        map_int_int = g.createObject("CMapIntInt")
        map_int_int.setValues({0: 25, 1: 51})

        tagged = g.createObject("CItem")
        tagged.addTag(game.CTag.HEAL)
        tagged.addTag("mana")

        roundtrip_objects = {
            "list_string": list_string,
            "list_int": list_int,
            "map_string_string": map_string_string,
            "map_string_int": map_string_int,
            "map_int_string": map_int_string,
            "map_int_int": map_int_int,
            "tagged": tagged,
        }
        serialized = {name: json.loads(game.jsonify(obj))["properties"] for name, obj in roundtrip_objects.items()}
        clones = {name: obj.clone() for name, obj in roundtrip_objects.items()}

        self.assertEqual({"north", "south", "west"}, set(clones["list_string"].getValues()))
        self.assertEqual({1, 3, 5}, set(clones["list_int"].getValues()))
        self.assertEqual({"i": "inventoryPanel", "j": "questPanel"}, dict(clones["map_string_string"].getValues()))
        self.assertEqual({"CMapObject": 1, "CCreature": 2}, dict(clones["map_string_int"].getValues()))
        self.assertEqual({0: "GroundTile", 1: "WaterTile"}, dict(clones["map_int_string"].getValues()))
        self.assertEqual({0: 25, 1: 51}, dict(clones["map_int_int"].getValues()))
        self.assertTrue(clones["tagged"].hasTag(game.CTag.HEAL))
        self.assertTrue(clones["tagged"].hasTag(game.CTag.MANA))

        return True, json.dumps(
            {
                "stats_text": text_after_bonus.splitlines(),
                "serialized": serialized,
            },
            sort_keys=True,
        )

    @game_test
    def test_domain_helpers_and_serialized_collections(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")

        tile = g.createObject("CTile")
        tile.canStep = True
        tile.posx = 3
        tile.posy = 4
        tile.posz = 1
        tile.tileType = "covered"
        serialized_tile = json.loads(game.jsonify(tile))
        self.assertTrue(serialized_tile["properties"]["canStep"])
        self.assertEqual(serialized_tile["properties"]["posx"], 3)
        self.assertEqual(serialized_tile["properties"]["tileType"], "covered")

        weapon_slot = g.createObject("CSlot")
        weapon_slot.setSlotName("weapon")
        weapon_slot.setTypes({"CWeapon"})
        self.assertEqual("weapon", weapon_slot.getSlotName())
        self.assertEqual({"CWeapon"}, set(weapon_slot.getTypes()))
        slot_config = g.createObject("CSlotConfig")
        slot_config.setConfiguration({"weapon": weapon_slot})
        weapon = g.createObject("CWeapon")
        generic_item = g.createObject("CItem")
        self.assertTrue(slot_config.canFit("weapon", weapon))
        self.assertFalse(slot_config.canFit("weapon", generic_item))
        self.assertFalse(slot_config.canFit("missing", weapon))
        self.assertEqual(set(slot_config.getFittingSlots(weapon)), {"weapon"})

        market = g.createObject("CMarket")
        market.sell = 50
        market.buy = 25
        sale_item = g.createObject("CItem")
        sale_item.name = "saleItem"
        sale_item.power = 1
        expensive_item = g.createObject("CItem")
        expensive_item.name = "expensiveItem"
        expensive_item.power = 3
        market.setItems({sale_item, expensive_item})
        self.assertEqual(len(market.getItems()), 2)
        market.remove(expensive_item)
        market.remove(expensive_item)
        market.add(expensive_item)

        buyer = g.createObject("CCreature")
        buyer.addGold(1000)
        sell_cost = market.getSellCost(sale_item)
        self.assertTrue(market.sellItem(buyer, sale_item))
        self.assertEqual(buyer.getGold(), 1000 - sell_cost)
        self.assertTrue(buyer.hasItem(lambda item: item.getName() == "saleItem"))

        poor_buyer = g.createObject("CCreature")
        poor_buyer.addGold(1)
        self.assertFalse(market.sellItem(poor_buyer, expensive_item))
        self.assertEqual(poor_buyer.getGold(), 1)

        seller = g.createObject("CCreature")
        owned_item = g.createObject("CItem")
        owned_item.name = "ownedItem"
        owned_item.power = 2
        seller.addItem(owned_item)
        buy_cost = market.getBuyCost(owned_item)
        market.buyItem(seller, owned_item)
        self.assertEqual(seller.getGold(), buy_cost)
        self.assertFalse(seller.hasItem(lambda item: item.getName() == "ownedItem"))

        attacker = g.createObject("CCreature")
        defender = g.createObject("CCreature")
        attacker.setMana(10)
        interaction = g.createObject("CInteraction")
        interaction.manaCost = 3
        damage_effect = g.createObject("CEffect")
        interaction.effect = damage_effect
        interaction.onAction(attacker, defender)
        self.assertEqual(attacker.getMana(), 7)

        buff_interaction = g.createObject("CInteraction")
        buff_effect = g.createObject("CEffect")
        buff_effect.addTag(game.CTag.BUFF)
        buff_interaction.effect = buff_effect
        buff_interaction.onAction(attacker, defender)

        tooltip_item = g.createObject("CItem")
        tooltip_item.label = "Practice blade"
        tooltip_item.description = "Blunt but balanced."
        bonus = g.createObject("CStats")
        bonus.strength = 2
        bonus.damage = 1
        tooltip_item.bonus = bonus
        tooltip = game.CTooltipHandler.buildTooltip(tooltip_item)
        self.assertIn("Practice blade", tooltip)
        self.assertIn("Blunt but balanced.", tooltip)
        self.assertIn("Strength: 2", tooltip)
        self.assertIn("Damage: 1", tooltip)

        return True, json.dumps(
            {
                "market_items": sorted(item.getName() for item in market.getItems()),
                "slot_fits": sorted(slot_config.getFittingSlots(weapon)),
                "tile": serialized_tile["properties"],
                "tooltip": tooltip.splitlines(),
            },
            sort_keys=True,
        )

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
    def test_map_object_properties_and_coordinates_are_available_during_on_create(self):
        _g, game_map = load_game_map("test")
        probe = game_map.getObjectByName("initializationProbe")

        self.assertIsNotNone(probe)
        self.assertEqual("configured-before-create", probe.getStringProperty("observedMarker"))
        self.assertEqual(3, probe.getNumericProperty("observedX"))
        self.assertEqual(4, probe.getNumericProperty("observedY"))
        self.assertEqual(0, probe.getNumericProperty("observedZ"))
        self.assertEqual({probe.getName()}, {obj.getName() for obj in game_map.getObjectsAtCoords(probe.getCoords())})

        return True, json.dumps(
            {
                "coords": [
                    probe.getNumericProperty("observedX"),
                    probe.getNumericProperty("observedY"),
                    probe.getNumericProperty("observedZ"),
                ],
                "marker": probe.getStringProperty("observedMarker"),
                "objects_at_coords": sorted(obj.getName() for obj in game_map.getObjectsAtCoords(probe.getCoords())),
            },
            sort_keys=True,
        )

    @game_test
    def test_python_wrapper_exceptions_are_caught_by_native_bridges(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")

        calls = []

        def fail(name):
            calls.append(name)
            raise RuntimeError(name)

        class RaisingBuilding(game.CBuilding):
            def onCreate(self, event):
                fail("building_create")

            def onTurn(self, event):
                fail("building_turn")

            def onDestroy(self, event):
                fail("building_destroy")

            def onEnter(self, event):
                fail("building_enter")

            def onLeave(self, event):
                fail("building_leave")

        class RaisingEvent(game.CEvent):
            def onCreate(self, event):
                fail("event_create")

            def onTurn(self, event):
                fail("event_turn")

            def onDestroy(self, event):
                fail("event_destroy")

            def onEnter(self, event):
                fail("event_enter")

            def onLeave(self, event):
                fail("event_leave")

        class RaisingInteraction(game.CInteraction):
            def performAction(self, first, second):
                fail("interaction_perform")

            def configureEffect(self, effect):
                fail("interaction_configure")

        class RaisingEffect(game.CEffect):
            def onEffect(self):
                fail("effect")

        class RaisingTile(game.CTile):
            def onStep(self, creature):
                fail("tile")

        class RaisingPotion(game.CPotion):
            def onUse(self, event):
                fail("potion")

        class RaisingScroll(game.CScroll):
            def onUse(self, event):
                fail("scroll_use")

            def isDisposable(self):
                fail("scroll_disposable")

        class RaisingTrigger(game.CTrigger):
            def trigger(self, obj, event):
                fail("trigger")

        class RaisingQuest(game.CQuest):
            def isCompleted(self):
                fail("quest_completed")

            def onComplete(self):
                fail("quest_complete")

        class RaisingPlugin(game.CPlugin):
            def load(self, game_instance):
                fail("plugin")

        class RaisingDialog(game.CDialogBase):
            def invokeAction(self, action):
                fail(f"dialog_action_{action}")

            def invokeCondition(self, condition):
                fail(f"dialog_condition_{condition}")

        creature = g.createObject("CCreature")
        effect = g.createObject("CEffect")

        for obj, base in ((RaisingBuilding(), game.CBuilding), (RaisingEvent(), game.CEvent)):
            base.onCreate(obj, None)
            base.onTurn(obj, None)
            base.onDestroy(obj, None)
            base.onEnter(obj, None)
            base.onLeave(obj, None)

        interaction = RaisingInteraction()
        game.CInteraction.performAction(interaction, creature, creature)
        self.assertFalse(game.CInteraction.configureEffect(interaction, effect))

        game.CEffect.onEffect(RaisingEffect())
        game.CTile.onStep(RaisingTile(), creature)
        game.CPotion.onUse(RaisingPotion(), None)

        scroll = RaisingScroll()
        game.CScroll.onUse(scroll, None)
        self.assertFalse(game.CScroll.isDisposable(scroll))

        game.CTrigger.trigger(RaisingTrigger(), creature, None)

        quest = RaisingQuest()
        self.assertFalse(game.CQuest.isCompleted(quest))
        game.CQuest.onComplete(quest)

        game.CPlugin.load(RaisingPlugin(), g)

        dialog = RaisingDialog()
        game.CDialogBase.invokeAction(dialog, "open")
        self.assertTrue(game.CDialogBase.invokeCondition(dialog, "ready"))

        expected = {
            "building_create",
            "building_turn",
            "building_destroy",
            "building_enter",
            "building_leave",
            "event_create",
            "event_turn",
            "event_destroy",
            "event_enter",
            "event_leave",
            "interaction_perform",
            "interaction_configure",
            "effect",
            "tile",
            "potion",
            "scroll_use",
            "scroll_disposable",
            "trigger",
            "quest_completed",
            "quest_complete",
            "plugin",
            "dialog_action_open",
            "dialog_condition_ready",
        }
        self.assertEqual(expected, set(calls))
        return True, json.dumps(sorted(calls))

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

        save_name = unique_save_name("typed_tags_roundtrip")
        try:
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
                "save_slot": save_name,
                "saved_object": {
                    "name": tagged_object_name,
                    "loaded_has_heal": loaded_object.hasTag(game.CTag.HEAL),
                },
            }
            return True, json.dumps(report, sort_keys=True)
        finally:
            cleanup_save_slot(save_name)

    @game_test
    def test_missing_save_resource_directory_lists_empty(self):
        game = load_game_module()
        provider = game.CResourcesProvider.getInstance()

        save_path = Path.cwd() / "save"
        backup_root = None
        backup_path = None
        if save_path.exists():
            backup_root = Path(tempfile.mkdtemp(prefix="save-backup-", dir=save_path.parent))
            backup_path = backup_root / "save"
            shutil.move(str(save_path), str(backup_path))

        try:
            self.assertFalse(save_path.exists())
            self.assertEqual([], list(provider.getFiles("SAVE")))
        finally:
            if backup_path is not None and backup_path.exists():
                if save_path.exists():
                    shutil.rmtree(save_path)
                shutil.move(str(backup_path), str(save_path))
            if backup_root is not None and backup_root.exists():
                shutil.rmtree(backup_root)

        return True, json.dumps({"save": []}, sort_keys=True)

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
    def test_empty_selection_list_returns_without_waiting(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)

        empty_selection = g.createObject("CListString")
        started_at = time.monotonic()
        selected = g.getGuiHandler().showSelection(empty_selection)

        self.assertEqual("", selected)
        self.assertLess(time.monotonic() - started_at, 1.0)
        return True, json.dumps({"selected": selected})

    def test_new_game_load_with_no_saves_reports_message(self):
        game = load_game_module()

        class FakeListString:
            def __init__(self):
                self.values = []

            def addValue(self, value):
                self.values.append(value)

            def getValues(self):
                return set(self.values)

        class FakeGuiHandler:
            def __init__(self):
                self.messages = []
                self.selections = []

            def showSelection(self, list_string):
                self.selections.append(sorted(list_string.getValues()))
                return "LOAD"

            def showInfo(self, message, centered):
                self.messages.append((message, centered))

        class FakeGame:
            def __init__(self):
                self.gui_handler = FakeGuiHandler()

            def createObject(self, type_id):
                if type_id != "CListString":
                    raise AssertionError(f"unexpected fake object type: {type_id}")
                return FakeListString()

            def getGuiHandler(self):
                return self.gui_handler

        fake_game = FakeGame()

        class FakeGameLoader:
            loaded_save = None

            @staticmethod
            def loadGame():
                return fake_game

            @staticmethod
            def loadGui(g):
                pass

            @staticmethod
            def loadSavedGame(g, save):
                FakeGameLoader.loaded_save = save

        class FakeResourcesProvider:
            @staticmethod
            def getInstance():
                return FakeResourcesProvider()

            def getFiles(self, kind):
                return [] if kind == "SAVE" else ["nouraajd"]

        original_loader = game.CGameLoader
        original_provider = game.CResourcesProvider
        original_event_loop = game.event_loop
        try:
            game.CGameLoader = FakeGameLoader
            game.CResourcesProvider = FakeResourcesProvider
            game.event_loop = types.SimpleNamespace(instance=lambda: None)
            game.new()
        finally:
            game.CGameLoader = original_loader
            game.CResourcesProvider = original_provider
            game.event_loop = original_event_loop

        self.assertEqual([["LOAD", "NEW", "RANDOM"]], fake_game.gui_handler.selections)
        self.assertEqual([("No saved games are available.", True)], fake_game.gui_handler.messages)
        self.assertIsNone(FakeGameLoader.loaded_save)

    @game_test
    def test_blocking_modal_gui_helpers_drive_panels(self):
        game = load_game_module()
        drain_sdl_events()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        game.CGameLoader.startGameWithPlayer(g, "nouraajd", "Warrior")
        pump_event_loop(5)

        gui_handler = g.getGuiHandler()
        player = g.getMap().getPlayer()

        selection = g.createObject("CListString")
        selection.addValue("FIRST")
        selection.addValue("SECOND")
        queue_sdl_inputs(game, lambda: push_sdl_mouse_click(960, 575))
        self.assertEqual("SECOND", gui_handler.showSelection(selection))

        queue_sdl_inputs(game, push_space_key)
        gui_handler.showMessage("blocking message workflow")

        queue_sdl_inputs(game, push_space_key)
        gui_handler.showInfo("blocking info workflow", False)

        queue_sdl_inputs(game, lambda: push_sdl_mouse_click(860, 650))
        self.assertTrue(gui_handler.showQuestion("confirm yes?"))

        queue_sdl_inputs(game, lambda: push_sdl_mouse_click(1060, 650))
        self.assertFalse(gui_handler.showQuestion("confirm no?"))

        def close_question_panel():
            panel = find_top_level_panel(g, "CGameQuestionPanel")
            if panel:
                panel.close()

        game.event_loop.instance().invoke(close_question_panel)
        self.assertFalse(gui_handler.showQuestion("externally closed question?"))
        self.assertFalse(gui_contains_class(g, "CGameQuestionPanel"))

        closed_selection = g.createObject("CListString")
        closed_selection.addValue("CLOSED")

        def close_selection_panel():
            panel = find_top_level_panel(g, "CGamePanel")
            if panel:
                panel.close()

        game.event_loop.instance().invoke(close_selection_panel)
        self.assertEqual("", gui_handler.showSelection(closed_selection))
        self.assertFalse(gui_contains_class(g, "CGamePanel"))

        market = g.createObject("CMarket")
        market.sell = 50
        market.buy = 25
        market_item = g.createObject("Sword")
        market.setItems({market_item})
        player.addGold(1000)
        player.addItem("Sword")

        def close_trade_panel():
            panel = find_top_level_panel(g, "CGameTradePanel")
            if panel:
                panel.close()

        game.event_loop.instance().invoke(close_trade_panel)
        gui_handler.showTrade(market)
        self.assertFalse(gui_contains_class(g, "CGameTradePanel"))

        queue_sdl_inputs(game, lambda: push_digit_key(2))
        gui_handler.showDialog(g.createObject("questDialog"))
        self.assertFalse(gui_contains_class(g, "CGameDialogPanel"))

        loot_creature = g.createObject("GoblinThief")
        loot_item = g.createObject("Sword")
        queue_sdl_inputs(game, lambda: push_sdl_mouse_click(585, 265), push_space_key)
        gui_handler.showLoot(loot_creature, {loot_item})
        self.assertFalse(gui_contains_class(g, "CGameLootPanel"))

        gui_handler.showTooltip("workflow tooltip", 960, 540)
        pump_event_loop(2)
        self.assertTrue(gui_contains_class(g, "CTooltip"))

        def close_inventory_panel():
            panel = find_top_level_panel(g, "CGameInventoryPanel")
            if panel:
                panel.close()

        game.event_loop.instance().invoke(close_inventory_panel)
        gui_handler.flipPanel("inventoryPanel", "i")
        self.assertFalse(gui_contains_class(g, "CGameInventoryPanel"))

        return True, json.dumps(
            {
                "market_items": len(market.getItems()),
                "player_swords": player.countItems("Sword"),
            },
            sort_keys=True,
        )

    @game_test
    def test_inventory_right_click_inspects_scroll_without_opening_it(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        game.CGameLoader.startGameWithPlayer(g, "nouraajd", "Warrior")
        player = g.getMap().getPlayer()
        player.addItem("letterFromRolf")

        inventory_panel = g.getGuiHandler().openPanel("inventoryPanel")
        pump_event_loop(5)
        inventory_list = next(
            list_view
            for list_view in collect_gui_children(inventory_panel, "CListView")
            if list_view.getCollection() == "inventoryCollection"
        )
        inventory_list.setTileSize(50)
        inventory_list.setXPrefferedSize(8)
        inventory_list.setYPrefferedSize(8)
        inventory_list.refresh()

        target_graphic = None
        for y in range(8):
            for x in range(8):
                for graphic in inventory_list.getProxiedObjects(g.getGui(), x, y):
                    obj = graphic.getObject() if hasattr(graphic, "getObject") else None
                    if obj and obj.getTypeId() == "letterFromRolf":
                        target_graphic = graphic
                        break
                if target_graphic:
                    break
            if target_graphic:
                break

        self.assertIsNotNone(target_graphic)
        target_graphic.mouseEvent(g.getGui(), SDL_MOUSEBUTTONDOWN, SDL_BUTTON_RIGHT, 1, 1)
        pump_event_loop(2)
        self.assertTrue(gui_contains_class(g, "CTooltip"))
        self.assertFalse(gui_contains_class(g, "CGameTextPanel"))

        return True, json.dumps({"rolf_letters": player.countItems("letterFromRolf")}, sort_keys=True)

    @game_test
    def test_detached_inventory_list_view_ignores_stale_item_callbacks(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        game.CGameLoader.startGameWithPlayer(g, "nouraajd", "Warrior")
        player = g.getMap().getPlayer()
        player.addItem("letterFromRolf")

        inventory_panel = g.getGuiHandler().openPanel("inventoryPanel")
        pump_event_loop(5)
        inventory_list = next(
            list_view
            for list_view in collect_gui_children(inventory_panel, "CListView")
            if list_view.getCollection() == "inventoryCollection"
        )
        inventory_list.setTileSize(50)
        inventory_list.setXPrefferedSize(8)
        inventory_list.setYPrefferedSize(8)
        inventory_list.refresh()

        target_graphic = None
        for y in range(8):
            for x in range(8):
                for graphic in inventory_list.getProxiedObjects(g.getGui(), x, y):
                    obj = graphic.getObject() if hasattr(graphic, "getObject") else None
                    if obj and obj.getTypeId() == "letterFromRolf":
                        target_graphic = graphic
                        break
                if target_graphic:
                    break
            if target_graphic:
                break

        self.assertIsNotNone(target_graphic)
        inventory_panel.close()
        pump_event_loop(2)
        self.assertFalse(gui_contains_class(g, "CGameInventoryPanel"))

        target_graphic.mouseEvent(g.getGui(), SDL_MOUSEBUTTONDOWN, SDL_BUTTON_RIGHT, 1, 1)
        pump_event_loop(2)
        self.assertFalse(gui_contains_class(g, "CTooltip"))

        return True, json.dumps({"rolf_letters": player.countItems("letterFromRolf")}, sort_keys=True)

    @game_test
    def test_inventory_double_select_uses_selected_item(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        game.CGameLoader.startGameWithPlayer(g, "nouraajd", "Warrior")
        pump_event_loop(5)

        gui = g.getGui()
        player = g.getMap().getPlayer()
        for item in list(player.getItems()):
            player.removeItem(lambda current, target=item: current == target, True)

        potion = g.createObject("LesserLifePotion")
        player.addItem(potion)
        player.setHp(max(1, player.getHpMax() - 10))

        inventory_panel = g.getGuiHandler().openPanel("inventoryPanel")
        pump_event_loop(5)
        inventory_list = next(
            list_view
            for list_view in collect_gui_children(inventory_panel, "CListView")
            if list_view.getCollection() == "inventoryCollection"
        )
        inventory_list.setTileSize(50)
        inventory_list.setXPrefferedSize(2)
        inventory_list.setYPrefferedSize(2)
        inventory_list.setDragStart("")
        inventory_list.refresh()

        self.assertTrue(inventory_list.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 1, 1))
        self.assertGreater(
            get_panel_selection_box_counts_by_collection(inventory_panel).get("inventoryCollection", 0), 0
        )
        self.assertTrue(inventory_list.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 1, 1))

        self.assertEqual(0, player.countItems("LesserLifePotion"))
        self.assertEqual(0, get_panel_selection_box_counts_by_collection(inventory_panel).get("inventoryCollection", 0))

        return True, json.dumps(
            {"hp_ratio": player.getHpRatio(), "potions": player.countItems("LesserLifePotion")}, sort_keys=True
        )

    @game_test
    def test_fight_panel_callbacks_and_list_views(self):
        game = load_game_module()
        drain_sdl_events()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        pump_event_loop(5)

        gui = g.getGui()
        player = g.getMap().getPlayer()
        player.setMana(999)
        player.addItem("Sword")
        player.addItem("Sword")

        console = collect_gui_children(gui, "CConsoleGraphicsObject")[0]
        console.consoleState = "logger('console coverage')"
        self.assertEqual("logger('console coverage')", console.consoleState)
        console.consoleState = ""
        self.assertEqual("", console.consoleState)

        static_object = g.createObject("CItem")
        static_object.animation = "images/item"
        static_animation = g.createObject("CStaticAnimation")
        static_animation.renderObject(gui, 0, 0, 24, 24, 0)
        missing_static_object = g.createObject("CGameObject")
        missing_static_object.animation = "images/does-not-exist"
        missing_static_animation = g.createObject("CStaticAnimation")
        missing_static_animation.setObject(missing_static_object)
        missing_static_animation.renderObject(gui, 0, 0, 24, 24, 0)
        static_animation.setObject(static_object)
        static_animation.renderObject(gui, 0, 0, 24, 24, 0)
        static_animation.setColorMod(200, 100, 50, 180)
        static_animation.setRotation(90)
        static_animation.renderObject(gui, 0, 0, 24, 24, 1)
        static_animation.clearColorMod()
        self.assertEqual(90, static_animation.getRotation())

        dynamic_object = g.createObject("CGameObject")
        dynamic_object.animation = "images/monsters/octobogz"
        dynamic_animation = g.createObject("CDynamicAnimation")
        dynamic_animation.setObject(dynamic_object)
        dynamic_animation.initialize()
        pump_event_loop(5)
        dynamic_animation.renderObject(gui, 0, 0, 24, 24, 100)
        pritzmage_object = g.createObject("CGameObject")
        pritzmage_object.animation = "images/monsters/pritzmage"
        pritzmage_animation = g.createObject("CDynamicAnimation")
        pritzmage_animation.setObject(pritzmage_object)
        pritzmage_animation.initialize()
        pump_event_loop(5)
        pritzmage_animation.renderObject(gui, 0, 0, 24, 24, 250)

        def write_animation_fixture(name, timings=None, copy_frames=True):
            fixture_dir = Path("images") / f"unit_{name}_{time.time_ns()}"
            fixture_dir.mkdir(parents=True, exist_ok=True)
            if timings is not None:
                (fixture_dir / "time.json").write_text(json.dumps(timings), encoding="utf-8")
                if copy_frames:
                    source_frame = Path("images") / "monsters" / "octobogz" / "0.png"
                    for key in timings:
                        shutil.copyfile(source_frame, fixture_dir / f"{key}.png")
            return fixture_dir.as_posix()

        for animation_path, should_render in (
            (write_animation_fixture("positive", {"0": 100}), True),
            (write_animation_fixture("missing_frame", {"0": 100}, copy_frames=False), True),
            (write_animation_fixture("missing_time", None), False),
            (write_animation_fixture("invalid_time", {"0": "bad"}), False),
            (write_animation_fixture("zero_time", {"0": 0}), False),
        ):
            fixture_object = g.createObject("CGameObject")
            fixture_object.animation = animation_path
            fixture_animation = g.createObject("CDynamicAnimation")
            fixture_animation.setObject(fixture_object)
            fixture_animation.initialize()
            pump_event_loop(5)
            if should_render:
                fixture_animation.renderObject(gui, 0, 0, 24, 24, 100)

        selection_box = g.createObject("CSelectionBox")
        selection_box.setThickness(3)
        selection_box.renderObject(gui, 0, 0, 24, 24, 0)
        self.assertEqual(3, selection_box.getThickness())
        self.assertFalse(selection_box.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 0, 0))

        quest_item = g.createObject("CItem")
        quest_item.name = "unitQuestMarker"
        quest_item.typeId = "unitQuestMarker"
        quest_item.addTag(game.CTag.QUEST)
        player.addItem(quest_item)

        panel = g.createObject("CGameFightPanel")
        self.assertEqual("CGameFightPanel", panel.getType())

        enemy_a = g.createObject("GoblinThief")
        enemy_a.name = "unitFightEnemyA"
        enemy_a.setHp(enemy_a.getHpMax())
        enemy_b = g.createObject("GoblinThief")
        enemy_b.name = "unitFightEnemyB"
        enemy_b.setHp(enemy_b.getHpMax())
        dead_enemy = g.createObject("GoblinThief")
        dead_enemy.name = "unitFightEnemyDead"
        dead_enemy.setHp(0)

        panel.setEnemy(enemy_a)
        self.assertEqual("unitFightEnemyA", panel.getEnemy().getName())
        panel.setEnemy(dead_enemy)
        self.assertIsNone(panel.getEnemy())
        panel.setEnemies([enemy_a, enemy_b, enemy_a, dead_enemy, None])
        self.assertEqual(
            ["unitFightEnemyA", "unitFightEnemyB"], [enemy.getName() for enemy in panel.enemiesCollection(gui)]
        )
        panel.enemiesCallback(gui, 1, enemy_b)
        self.assertTrue(panel.enemiesSelect(gui, 1, enemy_b))
        self.assertFalse(panel.enemiesSelect(gui, 0, enemy_a))

        interactions = panel.interactionsCollection(gui)
        self.assertTrue(interactions)
        action = interactions[0]
        panel.interactionsCallback(gui, 0, action)
        self.assertTrue(panel.interactionsSelect(gui, 0, action))
        panel.interactionsCallback(gui, 0, action)
        self.assertEqual(action.getName(), panel.selectInteraction().getName())
        self.assertFalse(panel.interactionsSelect(gui, 0, action))

        items = panel.itemsCollection(gui)
        normal_item = next(item for item in items if not item.hasTag(game.CTag.QUEST))
        panel.itemsCallback(gui, 0, quest_item)
        self.assertFalse(panel.itemsSelect(gui, 0, quest_item))
        panel.itemsCallback(gui, 0, normal_item)
        self.assertTrue(panel.itemsSelect(gui, 0, normal_item))
        self.assertFalse(panel.itemsRightClickCallback(gui, 0, quest_item))
        self.assertTrue(panel.itemsRightClickCallback(gui, 0, normal_item))
        self.assertFalse(panel.itemsSelect(gui, 0, normal_item))

        inventory_panel = g.getGuiHandler().openPanel("inventoryPanel")
        pump_event_loop(5)
        list_views = collect_gui_children(inventory_panel, "CListView")
        self.assertGreaterEqual(len(list_views), 2)
        inventory_list = next(
            list_view for list_view in list_views if list_view.getCollection() == "inventoryCollection"
        )
        equipped_list = next(list_view for list_view in list_views if list_view.getCollection() == "equippedCollection")
        for list_view in (inventory_list, equipped_list):
            list_view.setTileSize(50)
            list_view.setXPrefferedSize(2)
            list_view.setYPrefferedSize(2)
            list_view.setAllowOversize(True)
            list_view.setDragStart("")
            list_view.setDragValidate("")
            list_view.setDrop("")
            list_view.refresh()

        def populated_cell(list_view):
            list_view.refresh()
            for y in range(2):
                for x in range(2):
                    if list_view.getProxiedObjects(gui, x, y):
                        return x, y
            return None

        def empty_cell(list_view):
            list_view.refresh()
            for y in range(2):
                for x in range(2):
                    if not list_view.getProxiedObjects(gui, x, y):
                        return x, y
            return 1, 1

        inventory_cell = populated_cell(inventory_list)
        self.assertIsNotNone(inventory_cell)
        self.assertTrue(
            inventory_list.mouseEvent(
                gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, inventory_cell[0] * 50 + 1, inventory_cell[1] * 50 + 1
            )
        )
        self.assertTrue(equipped_list.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 1, 1))
        equipped_cell = populated_cell(equipped_list)
        self.assertIsNotNone(equipped_cell)
        self.assertTrue(
            equipped_list.mouseEvent(
                gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, equipped_cell[0] * 50 + 1, equipped_cell[1] * 50 + 1
            )
        )
        inventory_empty_cell = empty_cell(inventory_list)
        self.assertTrue(
            inventory_list.mouseEvent(
                gui,
                SDL_MOUSEBUTTONDOWN,
                SDL_BUTTON_LEFT,
                inventory_empty_cell[0] * 50 + 1,
                inventory_empty_cell[1] * 50 + 1,
            )
        )
        inventory_list.mouseEvent(
            gui,
            SDL_MOUSEBUTTONDOWN,
            SDL_BUTTON_RIGHT,
            inventory_empty_cell[0] * 50 + 1,
            inventory_empty_cell[1] * 50 + 1,
        )
        self.assertTrue(inventory_panel.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_RIGHT, 0, 0))
        proxied_counts = {}
        for index, list_view in enumerate(list_views):
            list_view.setTileSize(50)
            list_view.setXPrefferedSize(2)
            list_view.setYPrefferedSize(2)
            list_view.setAllowOversize(True)
            list_view.refresh()
            first_cell = list_view.getProxiedObjects(gui, 0, 0)
            proxied_counts[f"{index}:first"] = len(first_cell)
            self.assertTrue(first_cell or not list_view.getShowEmpty())
            for graphic in first_cell:
                graphic.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_RIGHT, 1, 1)
                graphic.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 1, 1)
            self.assertTrue(list_view.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 1, 1))
            list_view.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_RIGHT, 1, 1)
            self.assertTrue(list_view.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 999, 999))

            for graphic in list_view.getProxiedObjects(gui, 1, 1):
                graphic.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 1, 1)
            for graphic in list_view.getProxiedObjects(gui, 0, 1):
                graphic.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 1, 1)

        panel.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_RIGHT, 0, 0)
        inventory_panel.close()
        self.assertFalse(gui_contains_class(g, "CGameInventoryPanel"))

        configured_fight_panel = g.getGuiHandler().openPanel("fightPanel")
        configured_fight_panel.setEnemies([enemy_a, enemy_b])
        configured_fight_panel.refreshViews()
        pump_event_loop(5)
        effect_lists = [
            list_view
            for creature_view in collect_gui_children(configured_fight_panel, "CCreatureView")
            for list_view in collect_gui_children(creature_view, "CListView")
            if list_view.getCollection() == "getEffects"
        ]
        self.assertGreaterEqual(len(effect_lists), 2)
        for list_view in effect_lists:
            list_view.refresh()
            list_view.getProxiedObjects(gui, 0, 0)
        configured_fight_panel.close()

        return True, json.dumps(
            {
                "enemies": [enemy.getName() for enemy in panel.enemiesCollection(gui)],
                "effect_lists": len(effect_lists),
                "list_views": len(list_views),
                "proxied_counts": proxied_counts,
            },
            sort_keys=True,
        )

    @game_test
    def test_fight_panel_enemy_list_pages_all_living_targets(self):
        game = load_game_module()
        drain_sdl_events()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        gui = g.getGui()

        panel = g.getGuiHandler().openPanel("fightPanel")
        enemy_list = next(
            list_view
            for list_view in collect_gui_children(panel, "CListView")
            if list_view.getCollection() == "enemiesCollection"
        )
        self.assertTrue(enemy_list.getAllowOversize())
        enemy_list.setTileSize(50)
        enemy_list.setXPrefferedSize(4)
        enemy_list.setYPrefferedSize(1)

        enemies = []
        for index in range(6):
            enemy = g.createObject("GoblinThief")
            enemy.name = f"unitPagedEnemy{index}"
            enemy.setHp(enemy.getHpMax())
            enemies.append(enemy)

        def click_cell(x_index):
            graphics = enemy_list.getProxiedObjects(gui, x_index, 0)
            for graphic in graphics:
                graphic.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 1, 1)
            return panel.getEnemy()

        panel.setEnemies(enemies)
        enemy_list.refresh()
        self.assertEqual(
            [enemy.getName() for enemy in enemies], [enemy.getName() for enemy in panel.enemiesCollection(gui)]
        )

        for _ in range(4):
            for graphic in enemy_list.getProxiedObjects(gui, 3, 0):
                graphic.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 1, 1)

        selected = click_cell(1)
        self.assertEqual(enemies[4], selected)
        self.assertTrue(panel.enemiesSelect(gui, 4, enemies[4]))

        enemies[4].setHp(0)
        panel.setEnemies(enemies)
        enemy_list.refreshAll()
        self.assertNotEqual(enemies[4], panel.getEnemy())
        self.assertTrue(panel.getEnemy().isAlive())

        selected_after_shrink = click_cell(2)
        self.assertEqual(enemies[5], selected_after_shrink)

        panel.setEnemies(enemies[:2])
        enemy_list.refreshAll()
        selected_after_underflow = click_cell(1)
        self.assertEqual(enemies[1], selected_after_underflow)
        panel.close()

        return True, json.dumps(
            {
                "selected_after_shrink": selected_after_shrink.getName(),
                "selected_after_underflow": selected_after_underflow.getName(),
                "visible_count": len(panel.enemiesCollection(gui)),
            },
            sort_keys=True,
        )

    @game_test
    def test_graphics_object_tree_helpers_are_bound(self):
        game = load_game_module()

        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        gui = g.getGui()

        root = g.createObject("CGameGraphicsObject")
        branch = g.createObject("CGameGraphicsObject")
        leaf = g.createObject("CStatsGraphicsObject")

        root.pushChild(branch)
        branch.addChild(leaf)

        self.assertEqual(["CGameGraphicsObject"], [child.getType() for child in root.getChildren()])
        self.assertEqual("CGameGraphicsObject", branch.getParent().getType())
        self.assertEqual("CStatsGraphicsObject", root.findChild("CStatsGraphicsObject").getType())
        self.assertIsNone(root.findChild("DefinitelyMissingGraphicsObject"))
        self.assertFalse(root.keyboardEvent(gui, SDL_KEYDOWN, SDLK_TAB))
        self.assertFalse(root.mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 5, 6))

        root.removeChild(branch)
        self.assertEqual([], list(root.getChildren()))

        return True, ""

    @game_test
    def test_render_only_widget_ignores_mouse_clicks(self):
        game = load_game_module()
        drain_sdl_events()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        game.CGameLoader.startGameWithPlayer(g, "nouraajd", "Warrior")
        panel = g.getGuiHandler().openPanel("questionPanel")
        panel.setStringProperty("question", "Render-only widget event coverage?")
        pump_event_loop(5)

        push_sdl_mouse_click(960, 500, SDL_BUTTON_RIGHT)
        push_sdl_mouse_click(960, 500, SDL_BUTTON_LEFT)
        pump_event_loop(5)

        self.assertTrue(gui_contains_class(g, "CGameQuestionPanel"))
        panel.close()

        return True, ""

    @game_test
    def test_resource_provider_resolves_and_loads_known_files(self):
        game = load_game_module()
        provider = game.CResourcesProvider.getInstance()

        text_samples = {
            "config/tiles.json": "GroundTile",
            "maps/test/map.json": '"layers"',
            "plugins/effect.py": "def load",
        }
        resolved = {}
        for resource_path, needle in text_samples.items():
            full_path = provider.getPath(resource_path)
            self.assertTrue(full_path, resource_path)
            self.assertTrue(Path(full_path).exists(), full_path)
            self.assertIn(needle, provider.load(resource_path), resource_path)
            resolved[resource_path] = full_path

        for resource_path in ("fonts/ampersand.ttf", "images/item.png"):
            full_path = provider.getPath(resource_path)
            self.assertTrue(full_path, resource_path)
            self.assertTrue(Path(full_path).exists(), full_path)
            resolved[resource_path] = full_path

        resource_root = Path(provider.getPath("config/items.json")).parents[1]
        self.assertIn("test", provider.getFiles("MAP"))

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            malicious_plugins = tmp_path / "plugins"
            malicious_plugins.mkdir()
            (malicious_plugins / "aardvark.py").write_text(
                "def load(context):\n    raise RuntimeError('untrusted cwd plugin executed')\n",
                encoding="utf-8",
            )
            (tmp_path / "maps" / "test").mkdir(parents=True)
            (tmp_path / "maps" / "test" / "config.json").write_text("{}", encoding="utf-8")
            (tmp_path / "maps" / "zzFake").mkdir(parents=True)
            (tmp_path / "images").mkdir()
            (tmp_path / "images" / "item.png").write_text("not a packaged texture", encoding="utf-8")
            (tmp_path / "fonts").mkdir()
            (tmp_path / "fonts" / "ampersand.ttf").write_text("not a packaged font", encoding="utf-8")
            (tmp_path / "save").mkdir()
            save_name = unique_save_name("provider_root_cwd")
            provider_save_path = resource_root / "save" / f"{save_name}.json"
            provider_backup_path = resource_root / "save" / f"{save_name}.json.bak"
            cwd_save_path = tmp_path / "save" / f"{save_name}.json"

            original_cwd = Path.cwd()
            try:
                provider_save_path.unlink(missing_ok=True)
                provider_backup_path.unlink(missing_ok=True)
                os.chdir(tmp_path)
                self.assertFalse(provider.getPath("plugins/aardvark.py"))
                self.assertNotIn("plugins/aardvark.py", provider.getFiles("PLUGIN"))
                self.assertNotIn("zzFake", provider.getFiles("MAP"))

                g = game.CGameLoader.loadGame()
                game.CGameLoader.loadGui(g)
                game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
                self.assertEqual("test", g.getMap().mapName)

                panel = g.getGuiHandler().openPanel("questionPanel")
                panel.setStringProperty("question", "Provider font smoke")
                static_object = g.createObject("CGameObject")
                static_object.animation = "images/item"
                static_animation = g.createObject("CStaticAnimation")
                static_animation.setObject(static_object)
                static_animation.renderObject(g.getGui(), 0, 0, 24, 24, 0)
                pump_event_loop(5)

                game.CMapLoader.save(g.getMap(), save_name)
                self.assertTrue(provider_save_path.exists(), provider_save_path)
                self.assertFalse(cwd_save_path.exists(), cwd_save_path)
                self.assertEqual(provider_save_path.resolve(), Path(provider.getPath(f"save/{save_name}.json")))

                loaded_game = game.CGameLoader.loadGame()
                game.CGameLoader.loadSavedGame(loaded_game, save_name)
                self.assertEqual("test", loaded_game.getMap().mapName)
            finally:
                os.chdir(original_cwd)
                provider_save_path.unlink(missing_ok=True)
                provider_backup_path.unlink(missing_ok=True)

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
    def test_map_navigation_edge_bindings(self):
        game = load_game_module()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        game_map = g.getMap()

        origin = game.Coords(2, 2, 0)
        portal_target = game.Coords(9, 9, 0)
        disabled_target = game.Coords(8, 8, 0)
        bridge_source = game.Coords(6, 2, 0)

        def coord_values(coords):
            return sorted((coord.x, coord.y, coord.z) for coord in coords)

        base_neighbors = coord_values(game_map.getNavigationNeighbors(origin))
        self_neighbors = coord_values(game_map.getNavigationNeighbors(origin, True))

        game_map.registerNavigationEdge(origin, portal_target, True, False, 1, "portal")
        game_map.registerNavigationEdge(origin, disabled_target, False, False, 1, "portal")
        game_map.registerNavigationEdge(bridge_source, origin, True, True, 1, "bridge")

        edge_neighbors = coord_values(game_map.getNavigationNeighbors(origin))
        removed = game_map.unregisterNavigationEdgesForObject("portal")
        remaining_neighbors = coord_values(game_map.getNavigationNeighbors(origin))
        missing_removed = game_map.unregisterNavigationEdgesForObject("missing")

        expected_cardinal = {(3, 2, 0), (1, 2, 0), (2, 3, 0), (2, 1, 0)}
        success = (
            expected_cardinal.issubset(set(base_neighbors))
            and (2, 2, 0) not in base_neighbors
            and (2, 2, 0) in self_neighbors
            and (9, 9, 0) in edge_neighbors
            and (8, 8, 0) not in edge_neighbors
            and (6, 2, 0) in edge_neighbors
            and removed == 2
            and (9, 9, 0) not in remaining_neighbors
            and (6, 2, 0) in remaining_neighbors
            and missing_removed == 0
        )
        return success, json.dumps(
            {
                "baseNeighbors": base_neighbors,
                "edgeNeighbors": edge_neighbors,
                "missingRemoved": missing_removed,
                "remainingNeighbors": remaining_neighbors,
                "removed": removed,
                "selfNeighbors": self_neighbors,
            },
            sort_keys=True,
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
    def test_nouraajd_restored_map_layout_topology(self):
        map_data = load_map_data("nouraajd")
        config = json.loads((REPO_ROOT / "res/maps/nouraajd/config.json").read_text())
        script = (REPO_ROOT / "res/maps/nouraajd/script.py").read_text()

        width = map_data["width"]
        height = map_data["height"]
        tile_layer = next(layer for layer in map_data["layers"] if layer.get("type") == "tilelayer")
        data = tile_layer["data"]
        objects = []
        for layer in map_data["layers"]:
            if layer.get("type") == "objectgroup":
                objects.extend(layer.get("objects", []))

        by_name = {obj["name"]: obj for obj in objects if obj.get("name")}
        duplicate_names = sorted(
            name for name in by_name if len([obj for obj in objects if obj.get("name") == name]) > 1
        )

        def tile_of(name):
            obj = by_name[name]
            return int(obj["x"] // map_data["tilewidth"]), int(obj["y"] // map_data["tileheight"])

        def prop_value(obj, key):
            props = obj.get("properties", {})
            if isinstance(props, dict):
                return props.get(key)
            for prop in props:
                if prop.get("name") == key:
                    return prop.get("value")
            return None

        gate_blockers = {
            (int(obj["x"] // map_data["tilewidth"]), int(obj["y"] // map_data["tileheight"]))
            for obj in objects
            if obj.get("name", "").startswith("nouraajdDoorTrigger")
        }
        permanent_blockers = {
            (int(obj["x"] // map_data["tilewidth"]), int(obj["y"] // map_data["tileheight"]))
            for obj in objects
            if obj.get("type") == "brickWall"
            or (
                str(prop_value(obj, "canStep")).lower() == "false"
                and not obj.get("name", "").startswith("nouraajdDoorTrigger")
            )
        }
        impassable_gids = {2, 12}

        def walkable(tile, include_gate_blockers=True):
            x, y = tile
            if not (0 <= x < width and 0 <= y < height):
                return False
            if data[y * width + x] in impassable_gids:
                return False
            if tile in permanent_blockers:
                return False
            return not include_gate_blockers or tile not in gate_blockers

        start = (
            int(map_data["properties"]["x"]),
            int(map_data["properties"]["y"]),
        )

        def flood(include_gate_blockers=True):
            seen = {start}
            queue_tiles = [start]
            while queue_tiles:
                x, y = queue_tiles.pop(0)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    nxt = (nx, ny)
                    if nxt not in seen and walkable(nxt, include_gate_blockers=include_gate_blockers):
                        seen.add(nxt)
                        queue_tiles.append(nxt)
            return seen

        closed_seen = flood(include_gate_blockers=True)
        open_seen = flood(include_gate_blockers=False)

        expected_tiles = {
            "cave1": (19, 10),
            "catacombs": (22, 17),
            "cave2": (166, 21),
            "nouraajdSign": (106, 110),
            "market1": (106, 111),
            "scribeDesk1": (105, 109),
            "alchemyTable1": (105, 110),
            "questGiver": (107, 111),
            "nouraajdTownHall": (43, 101),
            "nouraajdChapel": (50, 101),
            "nouraajdTavern": (48, 99),
            "nouraajdDoor": (44, 106),
            "oldWoman": (190, 5),
        }
        gated_town_names = {"nouraajdTownHall", "nouraajdChapel", "nouraajdTavern"}

        road_gid = 6

        layout_failures = []
        if duplicate_names:
            layout_failures.append(f"duplicate names: {duplicate_names}")
        if map_data.get("nextobjectid", 0) <= max(obj["id"] for obj in objects):
            layout_failures.append("nextobjectid must be greater than every object id")
        for name, expected in expected_tiles.items():
            if name not in by_name:
                layout_failures.append(f"{name} missing")
                continue
            actual = tile_of(name)
            if actual != expected:
                layout_failures.append(f"{name} at {actual}, expected {expected}")
            reachable_tiles = open_seen if name in gated_town_names else closed_seen
            if actual not in reachable_tiles:
                layout_failures.append(f"{name} is unreachable from spawn")
            if not walkable(actual, include_gate_blockers=False):
                layout_failures.append(f"{name} sits on impassable terrain")

        script_checks = {
            "victor_leader": "VICTOR_COURTYARD_LEADER_SPAWN = (45, 100, 0)" in script,
            "victor_cultists": "VICTOR_COURTYARD_SPAWNS = [(44, 100, 0), (46, 100, 0), (45, 99, 0), (45, 101, 0)]"
            in script,
            "gooby_fixed": "gooby.moveTo(100, 100, 0)" in script,
            "amulet_goblin_near_old_woman": "goblin.moveTo(195, 8, 0)" in script,
        }
        for name, ok in script_checks.items():
            if not ok:
                layout_failures.append(f"script check failed: {name}")

        removed_route_signs = {
            "ridgeSign",
            "pritzRoadSign",
            "labyrinthTurnSign",
            "catacombsSign",
            "swampRoadSign",
            "eastReturnSign",
            "courtyardSign",
            "outskirtsSign",
        }
        remaining_route_sign_configs = sorted(sign for sign in removed_route_signs if sign in config)
        if remaining_route_sign_configs:
            layout_failures.append(f"route sign configs should be restored away: {remaining_route_sign_configs}")
        remaining_route_sign_objects = sorted(sign for sign in removed_route_signs if sign in by_name)
        if remaining_route_sign_objects:
            layout_failures.append(f"route sign objects should be restored away: {remaining_route_sign_objects}")

        ambient_config_names = {name for name in config if name.startswith("ambient")}
        ambient_object_names = {name for name in by_name if name.startswith("ambient")}
        if len(ambient_config_names) != 33:
            layout_failures.append(f"ambient config count {len(ambient_config_names)}, expected 33")
        if ambient_config_names != ambient_object_names:
            layout_failures.append(
                "ambient config/object mismatch: "
                f"{sorted(ambient_config_names.symmetric_difference(ambient_object_names))}"
            )

        expected_terrain = {
            (19, 10): 10,
            (22, 17): 10,
            (166, 21): 7,
            (44, 106): road_gid,
            (105, 109): 11,
            (105, 110): 11,
            (106, 111): road_gid,
            (107, 111): road_gid,
            (190, 5): 9,
            (195, 8): 9,
        }
        for tile, expected_gid in expected_terrain.items():
            actual_gid = data[tile[1] * width + tile[0]]
            if actual_gid != expected_gid:
                layout_failures.append(f"terrain {tile} gid {actual_gid}, expected {expected_gid}")

        spawn_checks = [(100, 100), (44, 100), (45, 99), (45, 100), (45, 101), (46, 100), (195, 8)]
        for tile in spawn_checks:
            reachable_tiles = (
                open_seen if tile in {(44, 100), (45, 99), (45, 100), (45, 101), (46, 100)} else closed_seen
            )
            if tile not in reachable_tiles:
                layout_failures.append(f"scripted spawn {tile} is unreachable")
            if not walkable(tile, include_gate_blockers=False):
                layout_failures.append(f"scripted spawn {tile} sits on impassable terrain")

        log = {
            "failures": layout_failures,
            "expected_tiles": expected_tiles,
            "closed_reachable_tiles": len(closed_seen),
            "open_reachable_tiles": len(open_seen),
            "script_checks": script_checks,
        }
        return layout_failures == [], json.dumps(log, sort_keys=True)

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
    def test_nouraajd_restored_map_text_contract(self):
        script = (REPO_ROOT / "res/maps/nouraajd/script.py").read_text()
        config = json.loads((REPO_ROOT / "res/maps/nouraajd/config.json").read_text())
        dialog2 = (REPO_ROOT / "res/maps/nouraajd/dialog2.json").read_text()
        dialog3 = (REPO_ROOT / "res/maps/nouraajd/dialog3.json").read_text()
        dialog4 = (REPO_ROOT / "res/maps/nouraajd/dialog4.json").read_text()
        dialog5 = (REPO_ROOT / "res/maps/nouraajd/dialog5.json").read_text()

        text = "\n".join(
            [
                script,
                json.dumps(config, ensure_ascii=False),
                dialog2,
                dialog3,
                dialog4,
                dialog5,
            ]
        ).lower()
        sign_texts = {
            name: value.get("properties", {}).get("text", "").lower()
            for name, value in config.items()
            if value.get("ref") == "signPost"
        }
        removed_route_signs = {
            "ridgeSign",
            "pritzRoadSign",
            "labyrinthTurnSign",
            "catacombsSign",
            "swampRoadSign",
            "eastReturnSign",
            "courtyardSign",
            "outskirtsSign",
        }
        ambient_config_names = {name for name in config if name.startswith("ambient")}

        checks = {
            "spawn_sign_points_east": "east" in sign_texts.get("nouraajdSign", ""),
            "route_signs_removed": not any(sign in config for sign in removed_route_signs),
            "ambient_overlay_preserved": len(ambient_config_names) == 33 and "ambientGateTriageNotice" in config,
            "rolf_old_route_text": "search the cave outside town" in text
            and "the cave entrance lies beyond nouraajd's roads" in text,
            "octobogz_old_route_text": "eastern road beyond the river" in text
            and "half-buried under boulders and sand" in text,
            "catacombs_old_text": "descend into the catacombs" in text
            and "the catacombs hide the relic beren needs" in text,
            "victor_timer_start_visible": (
                "VICTOR_COURTYARD_TIMEOUT_TURNS = 75" in script
                and "the cultists began their rite" in script.lower()
                and "press on now" in dialog3.lower()
                and "the rite has already begun" in dialog4.lower()
            ),
            "amulet_old_route_text": "near the village edge" in text and "nearby grove" in text,
        }
        failed = sorted(name for name, ok in checks.items() if not ok)
        return failed == [], json.dumps({"failed": failed, "checks": checks}, sort_keys=True)

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
    def test_nouraajd_cleanse_quest_completes_before_ritual_transition(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        town_hall = g.createObject("townHallDialog")
        beren = g.createObject("berenDialog")

        town_hall.give_letter()
        beren.deliver_letter()
        game_map.removeObjectByName("catacombs")
        beren.return_relic()
        game_map.removeObjectByName("cave2")
        self.assertIn("cleanseCaveQuest", quest_names(player))
        self.assertTrue(beren.can_finish_cleanse())

        beren.finish_cleanse()
        pump_event_loop(10)

        completed_quest_ids = sorted(player_quest_id(quest) for quest in player.getCompletedQuests())
        self.assertEqual("ritual", g.getMap().mapName)
        self.assertTrue(game_map.getBoolProperty("CAVE_PURGED"))
        self.assertNotIn("cleanseCaveQuest", quest_names(player))
        self.assertIn("cleanseCaveQuest", completed_quest_ids)

        return True, json.dumps(
            {
                "active": quest_names(player),
                "completed": completed_quest_ids,
                "current_map": g.getMap().mapName,
                "quest_state_beren_chain": game_map.getStringProperty("quest_state_beren_chain"),
            },
            sort_keys=True,
        )

    @game_test
    def test_player_add_quest_does_not_reopen_completed_type_id(self):
        g, game_map, player = load_game_map_with_player("nouraajd")

        player.addQuest("rolfQuest")
        self.assertIn("rolfQuest", quest_names(player))

        game_map.removeObjectByName("cave1")
        player.checkQuests()
        completed_quest_ids = sorted(player_quest_id(quest) for quest in player.getCompletedQuests())
        self.assertIn("rolfQuest", completed_quest_ids)
        self.assertNotIn("rolfQuest", quest_names(player))

        player.addQuest("rolfQuest")
        reopened_quests = quest_names(player)
        self.assertNotIn("rolfQuest", reopened_quests)

        return True, json.dumps(
            {
                "active": reopened_quests,
                "completed": sorted(player_quest_id(quest) for quest in player.getCompletedQuests()),
                "quest_state_rolf": game_map.getStringProperty("quest_state_rolf"),
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
    def test_nouraajd_market_economy_assumptions(self):
        game = load_game_module()
        config = json.loads((REPO_ROOT / "res/maps/nouraajd/config.json").read_text())
        economy_doc = (REPO_ROOT / "docs/nouraajd-economy.md").read_text(encoding="utf-8")
        g, game_map, player = load_game_map_with_player("nouraajd")

        def market_refs(market_id):
            return [item["ref"] for item in config[market_id]["properties"]["items"]]

        general_refs = market_refs("exampleMarket")
        victor_refs = market_refs("victorMarket")
        tavern_refs = market_refs("tavernBeerMarket")

        self.assertEqual(player.getGold(), 0)
        self.assertEqual(player.countItems("LesserLifePotion"), 0)
        self.assertEqual(player.countItems("LesserManaPotion"), 0)
        self.assertEqual(general_refs.count("LesserLifePotion"), 3)
        self.assertEqual(general_refs.count("LesserManaPotion"), 1)
        self.assertEqual(general_refs.count("Scroll"), 1)
        self.assertEqual(general_refs.count("DaggerOfVileHeart"), 1)
        self.assertNotIn("LifePotion", general_refs)
        self.assertNotIn("ManaPotion", general_refs)
        self.assertEqual(victor_refs, ["LesserLifePotion", "LifePotion", "LesserManaPotion", "ManaPotion"])
        self.assertEqual(tavern_refs, ["DarkBeer", "DarkBeer", "SpicedBeer"])

        market = g.createObject("exampleMarket")
        expected_sell_costs = {
            "Scroll": 200,
            "LesserLifePotion": 400,
            "LesserManaPotion": 400,
            "DarkBeer": 400,
            "SpicedBeer": 400,
            "LifePotion": 800,
            "ManaPotion": 1600,
            "DaggerOfVileHeart": 100000,
            "ShadowBlade": 100000,
        }
        sell_costs = {item_id: market.getSellCost(g.createObject(item_id)) for item_id in expected_sell_costs}
        buyback_costs = {
            item_id: market.getBuyCost(g.createObject(item_id)) for item_id in ("DaggerOfVileHeart", "ShadowBlade")
        }

        self.assertEqual(expected_sell_costs, sell_costs)
        self.assertEqual({"DaggerOfVileHeart": 5000, "ShadowBlade": 5000}, buyback_costs)
        self.assertLess(200, sell_costs["LesserLifePotion"])
        self.assertLess(player.getGold() + 200 + 1000 + 500, sell_costs["DaggerOfVileHeart"])
        self.assertIn("Starting gold: 0", economy_doc)
        self.assertIn("Merchant buyback prices are capped at 5000 gold", economy_doc)
        self.assertIn("main Gooby quest pays 200 gold once", economy_doc)

        return True, json.dumps(
            {
                "general_refs": general_refs,
                "victor_refs": victor_refs,
                "tavern_refs": tavern_refs,
                "sell_costs": sell_costs,
                "buyback_costs": buyback_costs,
            },
            sort_keys=True,
        )

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
        self.assertTrue(town_hall.can_discuss_victor_records())

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
        self.assertFalse(town_hall.can_discuss_victor_records())
        self.assertTrue(town_hall.victor_encounter_active())
        victor_quest = find_player_quest(player, "victorQuest")
        self.assertIn("Defeat the cultists in the courtyard", victor_quest.getObjective())
        self.assertIn("75 turns", victor_quest.getHint())
        self.assertEqual(leader.getName(), "cultLeaderQuest")
        self.assertTrue(cultists)

        return True, json.dumps(
            {
                "quest_state_victor": game_map.getStringProperty("quest_state_victor"),
                "victor_started": game_map.getBoolProperty("VICTOR_QUEST_STARTED"),
                "victor_courtyard_found": game_map.getBoolProperty("VICTOR_COURTYARD_FOUND"),
                "victor_cultists_spawned": game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED"),
                "victor_hint": victor_quest.getHint(),
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
    def test_nouraajd_victor_blocked_preferred_spawns_use_courtyard_fallbacks(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        tavern = g.createObject("tavernDialog2")
        town_hall = g.createObject("townHallDialog")
        blocked = set(NOURAAJD_VICTOR_PREFERRED_SPAWNS)

        tavern.talked_to_victor()
        blockers = add_nouraajd_victor_preferred_spawn_blockers(g, game_map)
        town_hall.spawn_cultists()

        leader = find_runtime_object(game_map, "cultLeaderQuest")
        cultists = sorted(
            (obj for obj in game_map.getObjects() if obj.getName() and obj.getName().startswith("victorCultist")),
            key=lambda obj: obj.getName(),
        )
        encounter_coords = []
        for obj in [leader] + cultists:
            coords = obj.getCoords()
            coord_tuple = (coords.x, coords.y, coords.z)
            encounter_coords.append(coord_tuple)
            self.assertNotIn(coord_tuple, blocked)

        self.assertEqual(game_map.getStringProperty("quest_state_victor"), "encounter_active")
        self.assertEqual(game_map.getNumericProperty("VICTOR_CULTISTS_PLACED"), 4)
        self.assertEqual(len(cultists), 4)
        self.assertTrue(game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED"))
        self.assertTrue(all(blocker.getName().startswith("victorSpawnBlocker") for blocker in blockers))

        return True, json.dumps(
            {
                "quest_state_victor": game_map.getStringProperty("quest_state_victor"),
                "blocked": sorted(blocked),
                "encounter_coords": sorted(encounter_coords),
                "cultists_placed": game_map.getNumericProperty("VICTOR_CULTISTS_PLACED"),
            },
            sort_keys=True,
        )

    @game_test
    def test_nouraajd_victor_fully_blocked_leader_spawn_does_not_start_timer(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        tavern = g.createObject("tavernDialog2")
        town_hall = g.createObject("townHallDialog")

        tavern.talked_to_victor()
        blockers = add_nouraajd_victor_leader_fallback_blockers(g, game_map)
        town_hall.spawn_cultists()

        self.assertEqual(game_map.getStringProperty("quest_state_victor"), "courtyard_known")
        self.assertFalse(game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED"))
        self.assertEqual(game_map.getNumericProperty("VICTOR_COURTYARD_TURN"), -1)
        self.assertIsNone(game_map.getObjectByName("cultLeaderQuest"))
        self.assertFalse(
            any(obj.getName() and obj.getName().startswith("victorCultist") for obj in game_map.getObjects())
        )

        advance_map_only(game_map, NOURAAJD_VICTOR_TIMEOUT + 1)

        self.assertEqual(game_map.getStringProperty("quest_state_victor"), "courtyard_known")
        self.assertFalse(game_map.getBoolProperty("VICTOR_BAD_END"))
        self.assertTrue(all(blocker.getName().startswith("victorSpawnBlocker") for blocker in blockers))

        return True, json.dumps(
            {
                "quest_state_victor": game_map.getStringProperty("quest_state_victor"),
                "victor_cultists_spawned": game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED"),
                "victor_bad_end": game_map.getBoolProperty("VICTOR_BAD_END"),
                "blocked_count": len(blockers),
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
            self.assertFalse(game_map.getBoolProperty("VICTOR_BAD_END"))
            self.assertTrue(game_map.getBoolProperty("VICTOR_REWARD_CLAIMED"))
            self.assertEqual(game_map.getNumericProperty("VICTOR_COURTYARD_TURN"), -1)
            self.assertIn("victorRewardDialog", captured["dialogs"])
            self.assertIn("victorMarket", captured["trades"])
            config = json.loads((REPO_ROOT / "res/maps/nouraajd/config.json").read_text())
            self.assertEqual(
                ["LesserLifePotion", "LifePotion", "LesserManaPotion", "ManaPotion"],
                [item["ref"] for item in config["victorMarket"]["properties"]["items"]],
            )
            self.assertTrue(town_hall.victor_good_end())
            victor_quest = find_player_quest(player, "victorQuest")
            self.assertIn("survived", victor_quest.getObjective())

            town_hall.spawn_cultists()
            self.assertIsNone(game_map.getObjectByName("cultLeaderQuest"))
            self.assertFalse(
                any(
                    obj.getName() and (obj.getName() == "cultLeaderQuest" or obj.getName().startswith("victorCultist"))
                    for obj in game_map.getObjects()
                )
            )

            duplicate_leader = g.createObject("CultLeader")
            duplicate_leader.setStringProperty("name", "cultLeaderQuest")
            game_map.addObject(duplicate_leader)
            game_map.removeObjectByName("cultLeaderQuest")

            self.assertEqual(player.getGold() - start_gold, 500)
            self.assertEqual(heal_amounts, [100])
            self.assertEqual(captured["dialogs"].count("victorRewardDialog"), 1)
            self.assertEqual(captured["trades"].count("victorMarket"), 1)

            return True, json.dumps(
                {
                    "quest_state_victor": game_map.getStringProperty("quest_state_victor"),
                    "dialogs": captured["dialogs"],
                    "trades": captured["trades"],
                    "heal_amounts": heal_amounts,
                    "gold_delta": player.getGold() - start_gold,
                    "victor_objective": victor_quest.getObjective(),
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
        start_gold = player.getGold()
        town_hall.spawn_cultists()
        spawn_turn = game_map.getNumericProperty("VICTOR_COURTYARD_TURN")
        self.assertIsNotNone(game_map.getObjectByName("cultLeaderQuest"))

        advance_map_only(game_map, NOURAAJD_VICTOR_TIMEOUT)
        self.assertEqual(game_map.getStringProperty("quest_state_victor"), "encounter_active")
        self.assertEqual(game_map.getNumericProperty("VICTOR_COURTYARD_TURN"), spawn_turn)

        advance_map_only(game_map, 1)

        self.assertEqual(game_map.getStringProperty("quest_state_victor"), "bad_end")
        self.assertTrue(game_map.getBoolProperty("VICTOR_BAD_END"))
        self.assertFalse(game_map.getBoolProperty("VICTOR_GOOD_END"))
        self.assertFalse(game_map.getBoolProperty("VICTOR_REWARD_CLAIMED"))
        self.assertEqual(game_map.getNumericProperty("VICTOR_COURTYARD_TURN"), -1)
        self.assertEqual(player.getGold(), start_gold)
        self.assertTrue(town_hall.victor_bad_end())
        victor_quest = find_player_quest(player, "victorQuest")
        self.assertIn("was taken", victor_quest.getObjective())
        self.assertEqual("No reward if Victor's daughter is taken.", victor_quest.getReward())
        self.assertIn("scrubbed clean", victor_quest.getHint())
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
                "victor_objective": victor_quest.getObjective(),
                "spawn_turn": spawn_turn,
                "turn": game_map.getTurn(),
            },
            sort_keys=True,
        )

    @game_test
    def test_nouraajd_victor_optional_does_not_block_main_progression(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        town_hall = g.createObject("townHallDialog")
        beren = g.createObject("berenDialog")

        self.assertEqual(game_map.getStringProperty("quest_state_victor"), "not_started")
        self.assertFalse(game_map.getBoolProperty("VICTOR_QUEST_STARTED"))
        self.assertNotIn("victorQuest", quest_names(player))

        game_map.removeObjectByName("cave1")
        gooby = find_runtime_object(game_map, "gooby1")
        game_map.removeObjectByName(gooby.getName())
        town_hall.give_letter()
        beren.deliver_letter()
        game_map.removeObjectByName("catacombs")
        beren.return_relic()
        game_map.removeObjectByName("cave2")
        beren.finish_cleanse()
        pump_event_loop()

        self.assertEqual(game_map.getStringProperty("quest_state_victor"), "not_started")
        self.assertFalse(game_map.getBoolProperty("VICTOR_QUEST_STARTED"))
        self.assertFalse(game_map.getBoolProperty("VICTOR_COURTYARD_FOUND"))
        self.assertFalse(game_map.getBoolProperty("VICTOR_GOOD_END"))
        self.assertFalse(game_map.getBoolProperty("VICTOR_BAD_END"))
        self.assertNotIn("victorQuest", quest_names(player))
        self.assertEqual(g.getMap().mapName, "ritual")

        return True, json.dumps(
            {
                "quest_state_victor": game_map.getStringProperty("quest_state_victor"),
                "victor_started": game_map.getBoolProperty("VICTOR_QUEST_STARTED"),
                "map": g.getMap().mapName,
                "quests": quest_names(player),
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
        self.assertTrue(game_map.getBoolProperty("AMULET_RETURNED"))
        self.assertIsNone(game_map.getObjectByName("amuletGoblin"))
        self.assertIsNone(game_map.getObjectByName("oldWoman"))
        assert_player_quest_state(self, player, "amuletQuest", completed=True)

        quest_dialog.start_amulet_quest()
        self.assertEqual(game_map.getStringProperty("quest_state_amulet"), "returned")
        self.assertIsNone(game_map.getObjectByName("amuletGoblin"))

        player.addItem("preciousAmulet")
        quest_return_dialog.complete_amulet_quest()
        self.assertEqual(player.getGold() - start_gold, 50)
        self.assertEqual(game_map.getStringProperty("quest_state_amulet"), "returned")
        self.assertTrue(player.hasItem(lambda it: it.getName() == "preciousAmulet"))

        return True, json.dumps(
            {
                "quest_state_amulet": game_map.getStringProperty("quest_state_amulet"),
                "gold_delta": player.getGold() - start_gold,
                "duplicate_amulet_present": player.hasItem(lambda it: it.getName() == "preciousAmulet"),
                "old_woman_present": game_map.getObjectByName("oldWoman") is not None,
                "amulet_goblin_present": game_map.getObjectByName("amuletGoblin") is not None,
            },
            sort_keys=True,
        )

    @game_test
    def test_nouraajd_octobogz_unique_reward_is_not_duplicated(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        travelers = g.createObject("dialog")
        start_gold = player.getGold()

        travelers.accept_quest()
        self.assertEqual(game_map.getStringProperty("quest_state_octobogz_contract"), "active")
        self.assertIn("octoBogzQuest", quest_names(player))
        game_map.removeObjectByName("cave2")
        player.checkQuests()

        self.assertEqual(player.getGold() - start_gold, 1000)
        self.assertEqual(player.countItems("ShadowBlade"), 1)
        self.assertTrue(game_map.getBoolProperty("OCTOBOGZ_REWARD_CLAIMED"))
        assert_player_quest_state(self, player, "octoBogzQuest", completed=True)

        quest = find_player_quest(player, "octoBogzQuest")
        quest.onComplete()
        self.assertEqual(player.getGold() - start_gold, 1000)
        self.assertEqual(player.countItems("ShadowBlade"), 1)

        return True, json.dumps(
            {
                "gold_delta": player.getGold() - start_gold,
                "shadow_blades": player.countItems("ShadowBlade"),
                "reward_claimed": game_map.getBoolProperty("OCTOBOGZ_REWARD_CLAIMED"),
                "quest_state_octobogz_contract": game_map.getStringProperty("quest_state_octobogz_contract"),
            },
            sort_keys=True,
        )

    @game_test
    def test_nouraajd_octobogz_late_contract_claims_existing_clear_reward(self):
        g, game_map, player = load_game_map_with_player("nouraajd")
        travelers = g.createObject("dialog")
        start_gold = player.getGold()

        game_map.removeObjectByName("cave2")
        self.assertEqual(game_map.getStringProperty("quest_state_octobogz_contract"), "completed")
        self.assertNotIn("octoBogzQuest", quest_names(player))
        self.assertFalse(game_map.getBoolProperty("OCTOBOGZ_REWARD_CLAIMED"))

        travelers.accept_quest()

        self.assertEqual(player.getGold() - start_gold, 1000)
        self.assertEqual(player.countItems("ShadowBlade"), 1)
        self.assertTrue(game_map.getBoolProperty("OCTOBOGZ_REWARD_CLAIMED"))
        assert_player_quest_state(self, player, "octoBogzQuest", completed=True)

        travelers.accept_quest()
        self.assertEqual(player.getGold() - start_gold, 1000)
        self.assertEqual(player.countItems("ShadowBlade"), 1)

        return True, json.dumps(
            {
                "gold_delta": player.getGold() - start_gold,
                "shadow_blades": player.countItems("ShadowBlade"),
                "reward_claimed": game_map.getBoolProperty("OCTOBOGZ_REWARD_CLAIMED"),
                "quest_state_octobogz_contract": game_map.getStringProperty("quest_state_octobogz_contract"),
            },
            sort_keys=True,
        )

    @game_test
    def test_new_class_dialog_hooks(self):
        script = (REPO_ROOT / "res/maps/nouraajd/script.py").read_text()
        dialog = json.loads((REPO_ROOT / "res/maps/nouraajd/dialog.json").read_text())
        dialog4 = json.loads((REPO_ROOT / "res/maps/nouraajd/dialog4.json").read_text())
        dialog5 = json.loads((REPO_ROOT / "res/maps/nouraajd/dialog5.json").read_text())

        door_entry = dialog["doorDialog"]["properties"]["states"][0]["properties"]["options"]
        tavern_cultist_options = None
        for state in dialog["tavernDialog1"]["properties"]["states"]:
            if state.get("properties", {}).get("stateId") == "INKEEPER_ABOUT_CULTISTS":
                tavern_cultist_options = state["properties"]["options"]
                break
        town_hall_entry = dialog4["townHallDialog"]["properties"]["states"][0]["properties"]["options"]
        beren_entry = dialog5["berenDialog"]["properties"]["states"][0]["properties"]["options"]
        door_states = {
            state.get("properties", {}).get("stateId") for state in dialog["doorDialog"]["properties"]["states"]
        }
        tavern_states = {
            state.get("properties", {}).get("stateId") for state in dialog["tavernDialog1"]["properties"]["states"]
        }
        beren_states = {
            state.get("properties", {}).get("stateId") for state in dialog5["berenDialog"]["properties"]["states"]
        }

        checks = {
            "warrior_condition_method": "def can_brace_gate(self):" in script,
            "warrior_action_method": "def brace_gate(self):" in script,
            "warrior_player_property": "warrior_barricades" in script and "braced_nouraajd_gate" in script,
            "warrior_dialog_option": any(
                option.get("properties", {}).get("condition") == "can_brace_gate"
                and option.get("properties", {}).get("action") == "brace_gate"
                for option in door_entry
            ),
            "warrior_dialog_state": "WARRIOR_GATE" in door_states,
            "assasin_condition_method": "def can_shadow_robed_men(self):" in script,
            "assasin_action_method": "def shadow_robed_men(self):" in script,
            "assasin_player_property": "assasin_trails" in script and "shadowed_robed_men" in script,
            "assasin_dialog_option": tavern_cultist_options is not None
            and any(
                option.get("properties", {}).get("condition") == "can_shadow_robed_men"
                and option.get("properties", {}).get("action") == "shadow_robed_men"
                for option in tavern_cultist_options
            ),
            "assasin_dialog_state": "ASSASIN_TRAIL" in tavern_states,
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
            "sorcerer_condition_method": "def can_decode_stained_glass_ward(self):" in script,
            "sorcerer_action_method": "def decode_stained_glass_ward(self):" in script,
            "sorcerer_player_property": "sorcerer_sigils" in script and "decoded_stained_glass_ward" in script,
            "sorcerer_dialog_option": any(
                option.get("properties", {}).get("condition") == "can_decode_stained_glass_ward"
                and option.get("properties", {}).get("action") == "decode_stained_glass_ward"
                for option in beren_entry
            ),
            "sorcerer_dialog_state": "SORCERER_WARD" in beren_states,
        }

        failed = sorted([name for name, ok in checks.items() if not ok])
        return failed == [], json.dumps({"failed": failed, "checks": checks})

    @game_test
    def test_nouraajd_class_specific_dialog_routes_unlock_for_type_ids(self):
        cases = [
            {
                "player_type": "Warrior",
                "dialog_type": "doorDialog",
                "condition": "can_brace_gate",
                "action": "brace_gate",
                "counter": "warrior_barricades",
                "flag": "braced_nouraajd_gate",
            },
            {
                "player_type": "Assasin",
                "dialog_type": "tavernDialog1",
                "condition": "can_shadow_robed_men",
                "action": "shadow_robed_men",
                "counter": "assasin_trails",
                "flag": "shadowed_robed_men",
            },
            {
                "player_type": "Wayfarer",
                "dialog_type": "townHallDialog",
                "condition": "can_chart_wayfarer_route",
                "action": "chart_wayfarer_route",
                "counter": "wayfarer_routes",
                "flag": "charted_smuggler_route",
            },
            {
                "player_type": "Inquisitor",
                "dialog_type": "berenDialog",
                "condition": "can_inspect_stained_glass",
                "action": "inspect_stained_glass",
                "counter": "inquisitor_clues",
                "flag": "inspected_stained_glass",
            },
            {
                "player_type": "Sorcerer",
                "dialog_type": "berenDialog",
                "condition": "can_decode_stained_glass_ward",
                "action": "decode_stained_glass_ward",
                "counter": "sorcerer_sigils",
                "flag": "decoded_stained_glass_ward",
                "item": "Scroll",
            },
        ]
        results = {}

        for case in cases:
            g, game_map, player = load_game_map_with_player("nouraajd", case["player_type"])
            dialog = g.createObject(case["dialog_type"])
            before_items = player.countItems(case["item"]) if case.get("item") else None

            self.assertEqual("CPlayer", player.getType())
            self.assertEqual(case["player_type"], player.getTypeId())
            for other in cases:
                other_dialog = (
                    dialog if other["dialog_type"] == case["dialog_type"] else g.createObject(other["dialog_type"])
                )
                expected = other["player_type"] == case["player_type"]
                self.assertEqual(
                    expected,
                    getattr(other_dialog, other["condition"])(),
                    f"{case['player_type']} visibility for {other['condition']}",
                )

            self.assertTrue(getattr(dialog, case["condition"])())
            getattr(dialog, case["action"])()
            self.assertFalse(getattr(dialog, case["condition"])())
            self.assertEqual(1, player.getNumericProperty(case["counter"]))
            self.assertTrue(player.getBoolProperty(case["flag"]))

            if case["player_type"] == "Warrior":
                town_gate = game_map.getObjectByName("nouraajdDoor")
                self.assertIsNotNone(town_gate)
                self.assertTrue(town_gate.getBoolProperty("opened"))
                self.assertFalse(any(obj.getName().startswith("nouraajdDoorTrigger") for obj in game_map.getObjects()))
            elif case["player_type"] == "Assasin":
                self.assertTrue(game_map.getBoolProperty("ASKED_ABOUT_GIRL"))
            elif case.get("item"):
                self.assertEqual(before_items + 1, player.countItems(case["item"]))

            getattr(dialog, case["action"])()
            self.assertEqual(1, player.getNumericProperty(case["counter"]))
            if case.get("item"):
                self.assertEqual(before_items + 1, player.countItems(case["item"]))

            results[case["player_type"]] = {
                "counter": player.getNumericProperty(case["counter"]),
                "flag": player.getBoolProperty(case["flag"]),
                "item_count": player.countItems(case["item"]) if case.get("item") else None,
                "asked_about_girl": game_map.getBoolProperty("ASKED_ABOUT_GIRL"),
            }

        return True, json.dumps(results, sort_keys=True)

    @game_test
    def test_nouraajd_start_event_preserves_existing_class_progression(self):
        game = load_game_module()
        cases = [
            {
                "player_type": "Wayfarer",
                "counter": "wayfarer_routes",
                "counter_value": 3,
                "flag": "charted_smuggler_route",
                "default_counter": "inquisitor_clues",
                "default_flag": "inspected_stained_glass",
            },
            {
                "player_type": "Inquisitor",
                "counter": "inquisitor_clues",
                "counter_value": 2,
                "flag": "inspected_stained_glass",
                "default_counter": "wayfarer_routes",
                "default_flag": "charted_smuggler_route",
            },
        ]
        results = {}
        save_names = []

        try:
            for case in cases:
                save_name = unique_save_name(f"nouraajd_{case['player_type'].lower()}_class_progression")
                save_names.append(save_name)
                cleanup_save_slot(save_name)
                _g, game_map, player = load_game_map_with_player("nouraajd", case["player_type"])
                start_events = [
                    obj
                    for obj in game_map.getObjects()
                    if obj.getTypeId() == "StartEvent" or obj.getType() == "StartEvent"
                ]

                self.assertTrue(start_events, "The Nouraajd map should author StartEvent tiles.")
                self.assertFalse(hasattr(player, case["default_counter"]))
                self.assertFalse(hasattr(player, case["default_flag"]))

                player.setNumericProperty(case["counter"], case["counter_value"])
                player.setBoolProperty(case["flag"], True)
                game_map.setBoolProperty("ASKED_ABOUT_GIRL", True)

                start_coords = start_events[0].getCoords()
                player.moveTo(start_coords.x, start_coords.y, start_coords.z)
                pump_event_loop(5)

                self.assertEqual(case["counter_value"], player.getNumericProperty(case["counter"]))
                self.assertTrue(player.getBoolProperty(case["flag"]))
                self.assertTrue(hasattr(player, case["default_counter"]))
                self.assertTrue(hasattr(player, case["default_flag"]))
                self.assertEqual(0, player.getNumericProperty(case["default_counter"]))
                self.assertFalse(player.getBoolProperty(case["default_flag"]))
                self.assertFalse(game_map.getBoolProperty("ASKED_ABOUT_GIRL"))

                game.CMapLoader.save(game_map, save_name)
                loaded_game = game.CGameLoader.loadGame()
                game.CGameLoader.loadSavedGame(loaded_game, save_name)
                loaded_player = loaded_game.getMap().getPlayer()

                self.assertEqual(case["counter_value"], loaded_player.getNumericProperty(case["counter"]))
                self.assertTrue(loaded_player.getBoolProperty(case["flag"]))

                results[case["player_type"]] = {
                    "counter": loaded_player.getNumericProperty(case["counter"]),
                    "flag": loaded_player.getBoolProperty(case["flag"]),
                    "default_counter": loaded_player.getNumericProperty(case["default_counter"]),
                    "default_flag": loaded_player.getBoolProperty(case["default_flag"]),
                    "asked_about_girl": loaded_game.getMap().getBoolProperty("ASKED_ABOUT_GIRL"),
                }

            return True, json.dumps(results, sort_keys=True)
        finally:
            for save_name in save_names:
                cleanup_save_slot(save_name)

    @game_test
    def test_nouraajd_main_quest_remains_completable_by_every_class(self):
        class_ids = ("Assasin", "Inquisitor", "Sorcerer", "Warrior", "Wayfarer")
        results = {}

        for player_type in class_ids:
            g, game_map, player = load_game_map_with_player("nouraajd", player_type)
            self.assertEqual(player_type, player.getTypeId())

            game_map.removeObjectByName("cave1")
            self.assertEqual("skull_recovered", game_map.getStringProperty("quest_state_rolf"))
            self.assertEqual("awaiting_gooby", game_map.getStringProperty("quest_state_main"))
            self.assertIn("mainQuest", quest_names(player))

            gooby = find_runtime_object(game_map, "gooby1")
            start_gold = player.getGold()
            game_map.removeObjectByName(gooby.getName())
            player.checkQuests()

            self.assertEqual("gooby_slain", game_map.getStringProperty("quest_state_main"))
            self.assertTrue(game_map.getBoolProperty("completed_gooby"))
            self.assertTrue(game_map.getBoolProperty("GOOBY_REWARD_CLAIMED"))
            self.assertEqual(start_gold + 200, player.getGold())
            assert_player_quest_state(self, player, "mainQuest", completed=True)
            main_quest = find_player_quest(player, "mainQuest")
            main_quest.onComplete()
            self.assertEqual(start_gold + 200, player.getGold())

            results[player_type] = {
                "quest_state_rolf": game_map.getStringProperty("quest_state_rolf"),
                "quest_state_main": game_map.getStringProperty("quest_state_main"),
                "completed_gooby": game_map.getBoolProperty("completed_gooby"),
                "gooby_reward_claimed": game_map.getBoolProperty("GOOBY_REWARD_CLAIMED"),
                "gold_delta": player.getGold() - start_gold,
                "completed_quests": completed_quest_names(player),
            }

        return True, json.dumps(results, sort_keys=True)

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
    def test_ritual_static_integrity(self):
        ritual_config = json.loads((REPO_ROOT / "res/maps/ritual/config.json").read_text())
        configs = load_object_configs("ritual")
        map_data = load_map_data("ritual")
        script_path = REPO_ROOT / "res/maps/ritual/script.py"
        script = script_path.read_text()
        tree = ast.parse(script)

        placed_objects = {}
        for layer in map_data.get("layers", []):
            if layer.get("type") != "objectgroup":
                continue
            for obj in layer.get("objects", []):
                name = obj.get("name")
                if name:
                    placed_objects[name] = obj

        script_classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        methods_by_class = {
            node.name: {method.name for method in node.body if isinstance(method, ast.FunctionDef)}
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        }

        required_objects = {
            "anchorCrypt",
            "anchorNorth",
            "anchorSanctum",
            "bossSpawn",
            "chapelRecords",
            "ritualCaptive",
            "ritualStart",
            "ritualTurnAnchor",
            "ritualWitness",
            "sanctumThreshold",
            "waveSpawnEast",
            "waveSpawnNorth",
            "waveSpawnWest",
        }
        required_config_entries = {
            "capturedSoulDialog",
            "chapelWarningDialog",
            "destroyAnchorsQuest",
            "finalResolutionQuest",
            "recordsDialog",
            "rescueCaptiveQuest",
            "ritualAnchorCrypt",
            "ritualAnchorNorth",
            "ritualAnchorSanctum",
            "ritualCaptive",
            "ritualCultist",
            "ritualLeaderTemplate",
            "ritualMage",
            "ritualPritz",
            "ritualQuest",
            "ritualStart",
            "ritualWitness",
        }
        resource_entries = {
            "res/maps/ritual/config.json",
            "res/maps/ritual/map.json",
            "res/maps/ritual/script.py",
        }

        trigger_targets = set(re.findall(r'@trigger\(context,\s*"[^"]+",\s*"([^"]+)"\)', script))
        lookup_refs = set(re.findall(r'getObjectByName\(\s*"([^"]+)"\s*\)', script))
        spawn_refs = set(re.findall(r'addObjectByName\(\s*"([^"]+)"', script))
        create_refs = set(re.findall(r'createObject\(\s*"([^"]+)"\s*\)', script))
        item_refs = set(re.findall(r'addItem\(\s*"([^"]+)"\s*\)', script))
        quest_refs = set(re.findall(r'ensure_quest\(player,\s*"([^"]+)"\)', script))

        allowed_engine_types = {"CEvent"}
        allowed_runtime_objects = {"player", "ritualLeader"}
        map_types = {obj.get("type") for obj in placed_objects.values() if obj.get("type")}
        missing_map_types = sorted(
            type_name
            for type_name in map_types
            if type_name not in configs and type_name not in script_classes and type_name not in allowed_engine_types
        )
        missing_trigger_targets = sorted(
            target
            for target in trigger_targets
            if target not in placed_objects and target not in allowed_runtime_objects
        )
        missing_lookup_refs = sorted(
            ref for ref in lookup_refs if ref not in placed_objects and ref not in allowed_runtime_objects
        )
        missing_spawn_refs = sorted(ref for ref in spawn_refs if ref not in configs)
        missing_create_refs = sorted(ref for ref in create_refs if ref not in configs)
        missing_item_refs = sorted(ref for ref in item_refs if ref not in configs)
        missing_quest_refs = sorted(ref for ref in quest_refs if ref not in ritual_config)

        dialog_issues = []
        for dialog_id, dialog in ritual_config.items():
            dialog_class = dialog.get("class") if isinstance(dialog, dict) else None
            if not isinstance(dialog_class, str) or not dialog_class.endswith("Dialog"):
                continue
            states = dialog.get("properties", {}).get("states", [])
            state_ids = {state.get("properties", {}).get("stateId") for state in states}
            if "ENTRY" not in state_ids:
                dialog_issues.append(f"{dialog_id}:missing ENTRY")
            for state in states:
                state_id = state.get("properties", {}).get("stateId")
                for option in state.get("properties", {}).get("options", []):
                    properties = option.get("properties", {})
                    next_state = properties.get("nextStateId")
                    if next_state and next_state != "EXIT" and next_state not in state_ids:
                        dialog_issues.append(f"{dialog_id}:{state_id}:bad nextStateId {next_state}")
                    for hook in ("action", "condition"):
                        method_name = properties.get(hook)
                        if method_name and method_name not in methods_by_class.get(dialog_class, set()):
                            dialog_issues.append(f"{dialog_id}:{state_id}:missing {hook} {method_name}")

        cmake_text = (REPO_ROOT / "CMakeLists.txt").read_text()
        issues = {
            "missing_required_objects": sorted(required_objects - set(placed_objects)),
            "missing_required_config_entries": sorted(required_config_entries - set(ritual_config)),
            "missing_resource_entries": sorted(entry for entry in resource_entries if entry not in cmake_text),
            "missing_map_types": missing_map_types,
            "missing_trigger_targets": missing_trigger_targets,
            "missing_lookup_refs": missing_lookup_refs,
            "missing_spawn_refs": missing_spawn_refs,
            "missing_create_refs": missing_create_refs,
            "missing_item_refs": missing_item_refs,
            "missing_quest_refs": missing_quest_refs,
            "dialog_issues": dialog_issues,
        }
        failing_issues = {key: value for key, value in issues.items() if value}
        return not failing_issues, json.dumps({"issues": issues}, sort_keys=True)

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
    def test_ritual_happy_path_frees_captive_and_starts_siege(self):
        g, game_map, player = load_game_map_with_player("ritual")
        start_gold = player.getGold()
        start_life_potions = player.countItems("LifePotion")

        game_map.removeObjectByName("anchorNorth")
        advance(g, 1)
        game_map.removeObjectByName("anchorCrypt")
        game_map.removeObjectByName("anchorSanctum")
        self.assertTrue(game_map.getBoolProperty("anchors_destroyed"))
        self.assertTrue(game_map.getBoolProperty("leader_spawned"))

        game_map.removeObjectByName("ritualLeader")
        advance(g, 1)
        self.assertTrue(game_map.getBoolProperty("leader_defeated"))

        captured = g.createObject("capturedSoulDialog")
        self.assertTrue(captured.can_free_captive())
        captured.free_captive()
        pump_event_loop(10)

        self.assertEqual("siege", g.getMap().mapName)
        self.assertTrue(g.getMap().getPlayer() == player)
        self.assertTrue(game_map.getBoolProperty("captive_freed"))
        self.assertTrue(game_map.getBoolProperty("good_ending"))
        self.assertTrue(game_map.getBoolProperty("reward_claimed"))
        self.assertEqual(start_gold + 300, player.getGold())
        self.assertEqual(start_life_potions + 1, player.countItems("LifePotion"))
        self.assertIn("defendSiegeQuest", quest_names(player))

        return True, json.dumps(
            {
                "current_map": g.getMap().mapName,
                "gold_delta": player.getGold() - start_gold,
                "life_potion_delta": player.countItems("LifePotion") - start_life_potions,
                "quests": quest_names(player),
                "ritual_flags": {
                    "captive_freed": game_map.getBoolProperty("captive_freed"),
                    "good_ending": game_map.getBoolProperty("good_ending"),
                    "reward_claimed": game_map.getBoolProperty("reward_claimed"),
                },
            },
            sort_keys=True,
        )

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
    def test_map_walkthrough_multilevel(self):
        return execute_walkthrough("multilevel")

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
    def test_siege_spawn_points_start_closed_and_unsealed(self):
        _g, game_map, _player = load_game_map_with_player("siege")
        spawn_names = ["spawnPoint1", "spawnPoint2", "spawnPoint3", "spawnPoint4"]
        spawn_states = {}

        for name in spawn_names:
            spawn_point = find_runtime_object(game_map, name)
            spawn_states[name] = {
                "animation": spawn_point.getStringProperty("animation"),
                "destroyed": spawn_point.getBoolProperty("destroyed"),
                "enabled": spawn_point.getBoolProperty("enabled"),
                "pendingSeal": spawn_point.getBoolProperty("pendingSeal"),
            }
            self.assertFalse(spawn_states[name]["enabled"])
            self.assertFalse(spawn_states[name]["destroyed"])
            self.assertFalse(spawn_states[name]["pendingSeal"])
            self.assertEqual("images/misc/closed_door", spawn_states[name]["animation"])

        return True, json.dumps(spawn_states, sort_keys=True)

    @game_test
    def test_siege_spawn_point_defers_blocking_sealed_occupied_gate(self):
        class FakeEvent:
            def __init__(self, cause):
                self.cause = cause

            def getCause(self):
                return self.cause

        game = load_game_module()
        original_show_question = game.CGuiHandler.showQuestion

        try:
            game.CGuiHandler.showQuestion = lambda self, message: True
            _g, game_map, player = load_game_map_with_player("siege")
            spawn_point = find_runtime_object(game_map, "spawnPoint1")
            spawn_coords = spawn_point.getCoords()
            player.moveTo(spawn_coords.x, spawn_coords.y, spawn_coords.z)
            player.addItem("magicWand")
            spawn_point.setBoolProperty("enabled", True)
            spawn_point.setBoolProperty("canStep", True)
            spawn_point.onEnter(FakeEvent(player))

            self.assertTrue(spawn_point.getBoolProperty("destroyed"))
            self.assertTrue(spawn_point.getBoolProperty("pendingSeal"))
            self.assertTrue(spawn_point.getBoolProperty("canStep"))

            exit_coords = find_adjacent_walkable_tile(game_map, spawn_coords)
            player.moveTo(exit_coords.x, exit_coords.y, exit_coords.z)
            spawn_point.onTurn(None)

            self.assertTrue(spawn_point.getBoolProperty("destroyed"))
            self.assertFalse(spawn_point.getBoolProperty("pendingSeal"))
            self.assertFalse(spawn_point.getBoolProperty("canStep"))
        finally:
            game.CGuiHandler.showQuestion = original_show_question

        return True, json.dumps(
            {
                "canStep": spawn_point.getBoolProperty("canStep"),
                "destroyed": spawn_point.getBoolProperty("destroyed"),
                "pendingSeal": spawn_point.getBoolProperty("pendingSeal"),
            },
            sort_keys=True,
        )

    @game_test
    def test_siege_spawn_point_seal_consumes_one_wand_once_while_pending(self):
        class FakeEvent:
            def __init__(self, cause):
                self.cause = cause

            def getCause(self):
                return self.cause

        game = load_game_module()
        original_show_question = game.CGuiHandler.showQuestion
        question_calls = []

        def confirm_seal(_self, _message):
            question_calls.append(True)
            return True

        try:
            game.CGuiHandler.showQuestion = confirm_seal
            _g, game_map, player = load_game_map_with_player("siege")
            spawn_point = find_runtime_object(game_map, "spawnPoint1")
            spawn_coords = spawn_point.getCoords()
            player.moveTo(spawn_coords.x, spawn_coords.y, spawn_coords.z)
            player.addItem("magicWand")
            player.addItem("magicWand")
            starting_wands = player.countItems("magicWand")
            spawn_point.setBoolProperty("enabled", True)
            spawn_point.setBoolProperty("canStep", True)

            spawn_point.onEnter(FakeEvent(player))
            after_first_seal_wands = player.countItems("magicWand")
            spawn_point.onEnter(FakeEvent(player))
            after_second_enter_wands = player.countItems("magicWand")

            self.assertEqual(starting_wands - 1, after_first_seal_wands)
            self.assertEqual(after_first_seal_wands, after_second_enter_wands)
            self.assertEqual(1, len(question_calls))
            self.assertFalse(spawn_point.getBoolProperty("enabled"))
            self.assertTrue(spawn_point.getBoolProperty("destroyed"))
            self.assertTrue(spawn_point.getBoolProperty("pendingSeal"))
            self.assertEqual("images/misc/closed_door", spawn_point.getStringProperty("animation"))
        finally:
            game.CGuiHandler.showQuestion = original_show_question

        return True, json.dumps(
            {
                "after_first_seal_wands": after_first_seal_wands,
                "after_second_enter_wands": after_second_enter_wands,
                "destroyed": spawn_point.getBoolProperty("destroyed"),
                "enabled": spawn_point.getBoolProperty("enabled"),
                "pendingSeal": spawn_point.getBoolProperty("pendingSeal"),
                "question_calls": len(question_calls),
                "starting_wands": starting_wands,
            },
            sort_keys=True,
        )

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
        missing_tests = [
            map_name for map_name in discovered_maps if not hasattr(self, f"test_map_walkthrough_{map_name}")
        ]
        summary = {
            "discovered_maps": discovered_maps,
            "walkthroughs": {map_name: WALKTHROUGHS[map_name].__name__ for map_name in discovered_maps},
            "missing_tests": missing_tests,
        }
        return missing_tests == [], json.dumps(summary)

    @game_test
    def test_game_simulation_nouraajd_quest_walkthrough(self):
        simulation = game_simulation.GameSimulation.startGame(load_game_module(), "nouraajd", DEFAULT_PLAYER)
        result = simulation.runSteps(
            [
                {"action": "interact_object", "object": "cave1", "name": "recover Rolf skull"},
                {"action": "move_to_object", "object": "nouraajdSign", "mode": "direct", "name": "stand at gate sign"},
                {"action": "interact_object", "object": "gooby1", "name": "defeat Gooby"},
                {"action": "interact_object", "object": "catacombs", "name": "recover relic"},
                {"action": "interact_object", "object": "cave2", "name": "clear OctoBogz"},
                {"action": "assert_map_bool", "property": "completed_rolf"},
                {"action": "assert_map_bool", "property": "completed_gooby"},
                {"action": "assert_map_bool", "property": "OCTOBOGZ_SLAIN"},
                {"action": "assert_inventory_contains", "item": "skullOfRolf"},
                {"action": "assert_inventory_contains", "item": "holyRelic"},
            ]
        )

        flag_state = simulation.readMapState(
            include_objects=False,
            bool_flags=["completed_rolf", "completed_gooby", "OCTOBOGZ_SLAIN"],
            string_properties=["quest_state_rolf", "quest_state_main", "quest_state_beren_chain"],
        )
        summary = {
            "steps": [step["step"] for step in result["steps"]],
            "approaches": [
                step["result"].get("approach") for step in result["steps"] if step["action"] == "interact_object"
            ],
            "flags": flag_state["boolFlags"],
            "quest_states": flag_state["stringProperties"],
            "inventory": [item["name"] for item in simulation.readInventory()],
            "quest_log": simulation.readQuestLog(),
        }
        ok = (
            flag_state["boolFlags"]["completed_rolf"]
            and flag_state["boolFlags"]["completed_gooby"]
            and flag_state["boolFlags"]["OCTOBOGZ_SLAIN"]
            and "skullOfRolf" in summary["inventory"]
            and "holyRelic" in summary["inventory"]
            and flag_state["stringProperties"]["quest_state_rolf"] == "skull_recovered"
            and flag_state["stringProperties"]["quest_state_main"] == "gooby_slain"
            and all(
                step["result"].get("approach")
                and step["result"]["approach"]["target"] == step["result"]["object"]["coords"]
                and step["result"]["approach"]["distance"] <= 1
                for step in result["steps"]
                if step["action"] == "interact_object"
            )
        )
        return ok, json.dumps(summary, sort_keys=True)

    @game_test
    def test_mcp_scenario_harness_drives_nouraajd_rolf_gooby(self):
        scenario = McpScenarioHarness.start("nouraajd", DEFAULT_PLAYER)
        door_triggers = ("nouraajdDoorTrigger1", "nouraajdDoorTrigger2", "nouraajdDoorTrigger3")
        watched_objects = ("cave1", "gooby1", "nouraajdDoor", *door_triggers)

        initial = scenario.snapshot(
            object_names=watched_objects,
            object_bool_properties={"nouraajdDoor": ("opened",)},
        )
        self.assertEqual("awaiting_skull", initial["quest_states"]["rolf"])
        self.assertEqual("locked", initial["quest_states"]["main"])
        self.assertGreaterEqual(initial["items"]["letterFromRolf"], 1)
        self.assertIn("rolfQuest", initial["active_quests"])
        self.assertTrue(initial["objects"]["cave1"])
        self.assertFalse(initial["objects"]["gooby1"])

        scenario.invokeDialogAction("doorDialog", "open_door")
        after_door = scenario.snapshot(
            object_names=watched_objects,
            object_bool_properties={"nouraajdDoor": ("opened",)},
        )
        self.assertTrue(after_door["object_bool_properties"]["nouraajdDoor"]["opened"])
        self.assertFalse(any(after_door["objects"][name] for name in door_triggers))

        scenario.removeObjectByName("cave1")
        after_rolf = scenario.snapshot(object_names=watched_objects)
        self.assertEqual("skull_recovered", after_rolf["quest_states"]["rolf"])
        self.assertEqual("awaiting_gooby", after_rolf["quest_states"]["main"])
        self.assertEqual(initial["items"]["skullOfRolf"] + 1, after_rolf["items"]["skullOfRolf"])
        self.assertTrue(after_rolf["map_flags"]["completed_rolf"])
        self.assertIn("rolfQuest", after_rolf["completed_quests"])
        self.assertIn("mainQuest", after_rolf["active_quests"])
        self.assertTrue(after_rolf["objects"]["gooby1"])

        scenario.removeObjectByName("gooby1")
        after_gooby = scenario.snapshot(object_names=watched_objects)
        self.assertEqual("gooby_slain", after_gooby["quest_states"]["main"])
        self.assertTrue(after_gooby["map_flags"]["completed_gooby"])
        self.assertIn("mainQuest", after_gooby["completed_quests"])
        self.assertFalse(after_gooby["objects"]["gooby1"])

        with self.assertRaisesRegex(AssertionError, "available source actions"):
            scenario.invokeDialogAction("doorDialog", "missing_action")
        with self.assertRaisesRegex(AssertionError, "no source mention found"):
            scenario.runtimeObject("missingScenarioObject")

        return True, json.dumps(
            {
                "initial": {
                    "quest_states": initial["quest_states"],
                    "items": initial["items"],
                    "objects": initial["objects"],
                },
                "after_door": {
                    "door": after_door["object_bool_properties"]["nouraajdDoor"],
                    "objects": after_door["objects"],
                },
                "after_rolf": {
                    "quest_states": after_rolf["quest_states"],
                    "items": after_rolf["items"],
                    "objects": after_rolf["objects"],
                },
                "after_gooby": {
                    "quest_states": after_gooby["quest_states"],
                    "flags": after_gooby["map_flags"],
                    "objects": after_gooby["objects"],
                },
            },
            sort_keys=True,
        )

    @game_test
    def test_game_simulation_gui_tree_and_screenshot_helpers(self):
        simulation = game_simulation.GameSimulation.startGame(
            load_game_module(),
            "test",
            DEFAULT_PLAYER,
            load_gui=True,
        )
        panel_result = simulation.openPanel("inventoryPanel")
        screenshot_path = TEST_OUTPUT_DIR / "simulation_inventory_panel.png"

        def write_test_screenshot(path, _gui):
            from PIL import Image

            Image.new("RGBA", (320, 200), (31, 47, 63, 255)).save(path)
            return None, 320, 200

        screenshot = simulation.captureGuiScreenshot(screenshot_path, write_test_screenshot)
        from PIL import Image

        with Image.open(screenshot_path) as image:
            image.load()
            loaded_size = image.size
        inline_screenshot = simulation.runSteps(
            [{"action": "capture_gui_screenshot", "name": "capture inline screenshot"}]
        )["steps"][0]["result"]
        ok = (
            "CGameInventoryPanel" in panel_result["guiClasses"]
            and simulation.guiContainsClass("CGameInventoryPanel")
            and screenshot["suffix"] == ".png"
            and screenshot["bytes"] > 0
            and screenshot["width"] == 320
            and screenshot["height"] == 200
            and loaded_size == (320, 200)
            and inline_screenshot["suffix"] == ".png"
            and inline_screenshot["bytes"] > 0
            and inline_screenshot["width"] > 0
            and inline_screenshot["height"] > 0
            and len(inline_screenshot["pngBase64"]) > 0
        )
        return ok, json.dumps(
            {
                "panel": panel_result,
                "screenshot": screenshot,
                "inline_screenshot": {
                    key: (len(value) if key == "pngBase64" else value) for key, value in inline_screenshot.items()
                },
            },
            sort_keys=True,
        )

    @game_test
    def test_game_simulation_errors_include_step_and_state(self):
        simulation = game_simulation.GameSimulation.startGame(load_game_module(), "test", DEFAULT_PLAYER)
        try:
            simulation.runSteps(
                [{"action": "move_to_object", "object": "missingSimulationTarget", "name": "missing target"}]
            )
        except game_simulation.SimulationError as exc:
            payload = exc.asDict()
            ok = (
                payload["step"] == "missing target"
                and "missingSimulationTarget" in payload["error"]
                and payload["state"].get("map") == "test"
                and "player" in payload["state"]
            )
            return ok, json.dumps(payload, sort_keys=True)
        return False, "SimulationError was not raised"

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
    def test_python_black_formatting(self):
        python_files = [str(path.relative_to(REPO_ROOT)) for path in iter_python_source_files()]
        if not python_files:
            return True, json.dumps({"checked_files": [], "skipped": "no changed Python files"}, sort_keys=True)

        black_executable = shutil.which("black")
        black_command = [black_executable] if black_executable else [sys.executable, "-m", "black"]

        return_code, output, errors = run_command([*black_command, "--check", "-l", "120", *python_files])
        log = {
            "command": " ".join([*black_command, "--check", "-l", "120"]),
            "stdout": output,
            "stderr": errors,
            "checked_files": python_files,
        }
        return return_code == 0, json.dumps(log, indent=2, sort_keys=True)

    @game_test
    def test_cpp_clang_formatting(self):
        cxx_files = [str(path.relative_to(REPO_ROOT)) for path in iter_cpp_source_files()]
        if not cxx_files:
            return True, json.dumps({"checked_files": [], "skipped": "no changed C++ files"}, sort_keys=True)

        if shutil.which("clang-format") is None:
            return False, json.dumps({"error": "clang-format executable is required to enforce formatting policy"})

        return_code, output, errors = run_command(["clang-format", "--dry-run", "--Werror", *cxx_files])
        log = {
            "command": "clang-format --dry-run --Werror",
            "stdout": output,
            "stderr": errors,
            "checked_files": cxx_files,
        }
        return return_code == 0, json.dumps(log, indent=2, sort_keys=True)

    @game_test
    def test_indentation(self):
        offenders = []
        for file_path in git_tracked_files("*.py"):
            path = REPO_ROOT / file_path
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
    def test_campaign_transitions_preserve_player_and_start_siege(self):
        game = load_game_module()

        g, game_map, player = load_game_map_with_player("nouraajd")
        scene_manager = g.getSceneManager()
        town_hall = g.createObject("townHallDialog")
        beren = g.createObject("berenDialog")

        town_hall.give_letter()
        beren.deliver_letter()
        game_map.removeObjectByName("catacombs")
        beren.return_relic()
        game_map.removeObjectByName("cave2")
        chapel = game_map.getObjectByName("nouraajdChapel")
        chapel_coords = chapel.getCoords()
        player.moveTo(chapel_coords.x, chapel_coords.y, chapel_coords.z)
        beren.finish_cleanse()
        self.assertEqual("TransitionPending", scene_manager.getTransitionStateName())
        pump_event_loop(10)

        self.assertEqual("ritual", g.getMap().mapName)
        self.assertTrue(g.getMap().getPlayer() == player)
        self.assertEqual("Idle", scene_manager.getTransitionStateName())

        ritual_map = g.getMap()
        ritual_map.setBoolProperty("anchors_destroyed", True)
        ritual_map.setBoolProperty("leader_defeated", True)
        captive_marker = ritual_map.getObjectByName("ritualCaptive")
        captive_coords = captive_marker.getCoords()
        player.moveTo(captive_coords.x, captive_coords.y, captive_coords.z)
        captured = g.createObject("capturedSoulDialog")
        captured.free_captive()
        self.assertEqual("TransitionPending", scene_manager.getTransitionStateName())
        pump_event_loop(10)

        self.assertEqual("siege", g.getMap().mapName)
        self.assertTrue(g.getMap().getPlayer() == player)
        self.assertEqual("Idle", scene_manager.getTransitionStateName())
        self.assertIn("defendSiegeQuest", quest_names(player))
        self.assertGreaterEqual(player.countItems("magicWand"), 1)

        return True, json.dumps(
            {
                "current_map": g.getMap().mapName,
                "manager": scene_manager.getTransitionStateName(),
                "player_name": player.getName(),
                "quests": quest_names(player),
                "wands": player.countItems("magicWand"),
            },
            sort_keys=True,
        )

    @game_test
    def test_quest_journal_shows_objectives_rewards_and_hints(self):
        game = load_game_module()

        g, game_map, player = load_game_map_with_player("nouraajd")
        player.addQuest("rolfQuest")
        game.CGameLoader.loadGui(g)
        quest_panel = g.createObject("questPanel")
        text = quest_panel.getText(g.getGui())

        self.assertIn("[Active] Unravel the fate of Sergeant Rolf.", text)
        self.assertIn("Objective: Recover Sergeant Rolf's skull from the Pritscher cave", text)
        self.assertIn("Reward: Starts the Gooby hunt.", text)
        self.assertIn("Hint: The cave entrance lies beyond Nouraajd's roads.", text)

        g_rewards, _reward_map, reward_player = load_game_map_with_player("nouraajd")
        for quest_id in NOURAAJD_QUEST_REWARDS:
            reward_player.addQuest(quest_id)
        game.CGameLoader.loadGui(g_rewards)
        reward_panel = g_rewards.createObject("questPanel")
        reward_text = reward_panel.getText(g_rewards.getGui())
        for reward in NOURAAJD_QUEST_REWARDS.values():
            self.assertIn(f"Reward: {reward}", reward_text)

        g_completed, completed_map, completed_player = load_game_map_with_player("nouraajd")
        completed_player.addQuest("rolfQuest")
        completed_map.removeObjectByName("cave1")
        completed_player.checkQuests()
        game.CGameLoader.loadGui(g_completed)
        completed_panel = g_completed.createObject("questPanel")
        text_after_completion = completed_panel.getText(g_completed.getGui())
        self.assertIn("[Completed] Unravel the fate of Sergeant Rolf.", text_after_completion)
        self.assertIn("Status: Completed", text_after_completion)
        self.assertIn("[Active] Vanquish the Dreaded Gooby", text_after_completion)

        return True, json.dumps(
            {"before": text, "all_rewards": reward_text, "after": text_after_completion},
            sort_keys=True,
        )

    @game_test
    def test_nouraajd_save_load_quest_milestones(self):
        game = load_game_module()
        save_paths = []

        try:
            g, game_map, player = load_game_map_with_player("nouraajd")
            player.addItem("letterFromRolf")
            player.addQuest("rolfQuest")

            self.assertEqual("awaiting_skull", game_map.getStringProperty("quest_state_rolf"))
            self.assertEqual("locked", game_map.getStringProperty("quest_state_main"))
            g, game_map, player, initial = assert_nouraajd_save_load_roundtrip(
                self,
                game,
                game_map,
                "nouraajd_initial_invariants",
                save_paths,
                object_names=("cave1", "catacombs", "cave2"),
            )
            self.assertGreaterEqual(initial["items"]["letterFromRolf"], 1)
            self.assertIn("rolfQuest", initial["active_quests"])

            game_map.removeObjectByName("cave1")
            player.checkQuests()
            pump_event_loop(3)
            gooby = find_runtime_object(game_map, "gooby1")
            game_map.removeObjectByName(gooby.getName())
            player.checkQuests()
            pump_event_loop(3)

            town_hall = g.createObject("townHallDialog")
            beren = g.createObject("berenDialog")
            town_hall.give_letter()
            beren.deliver_letter()
            player.checkQuests()
            pump_event_loop(3)

            self.assertEqual("skull_recovered", game_map.getStringProperty("quest_state_rolf"))
            self.assertEqual("gooby_slain", game_map.getStringProperty("quest_state_main"))
            self.assertEqual("letter_delivered", game_map.getStringProperty("quest_state_beren_chain"))
            self.assertTrue(player.getBoolProperty("CAN_CRAFT_SCROLLS"))
            g, game_map, player, mid = assert_nouraajd_save_load_roundtrip(
                self,
                game,
                game_map,
                "nouraajd_mid_invariants",
                save_paths,
                object_names=("cave1", "gooby1", "catacombs", "cave2"),
            )
            self.assertFalse(mid["objects"]["cave1"])
            self.assertFalse(mid["objects"]["gooby1"])
            self.assertTrue(mid["objects"]["catacombs"])
            self.assertIn("rolfQuest", mid["completed_quests"])
            self.assertIn("mainQuest", mid["completed_quests"])
            self.assertIn("retrieveRelicQuest", mid["active_quests"])

            beren = g.createObject("berenDialog")
            travelers = g.createObject("dialog")
            game_map.removeObjectByName("catacombs")
            beren.return_relic()
            travelers.accept_quest()
            game_map.removeObjectByName("cave2")
            player.checkQuests()
            pump_event_loop(3)

            self.assertEqual("ready_to_report", game_map.getStringProperty("quest_state_beren_chain"))
            self.assertEqual("completed", game_map.getStringProperty("quest_state_octobogz_contract"))
            self.assertTrue(player.getBoolProperty("CAN_BREW_GREATER_POTIONS"))
            g, game_map, player, late = assert_nouraajd_save_load_roundtrip(
                self,
                game,
                game_map,
                "nouraajd_late_invariants",
                save_paths,
                object_names=("catacombs", "cave2"),
            )
            self.assertFalse(late["objects"]["catacombs"])
            self.assertFalse(late["objects"]["cave2"])
            self.assertTrue(late["map_flags"]["RELIC_RETURNED"])
            self.assertTrue(late["map_flags"]["OCTOBOGZ_CLEARED"])
            self.assertTrue(late["map_flags"]["completed_octobogz"])
            self.assertGreaterEqual(late["items"]["ShadowBlade"], 1)
            self.assertIn("octoBogzQuest", late["completed_quests"])
            self.assertIn("cleanseCaveQuest", late["active_quests"])

            return True, json.dumps(
                {
                    "initial": initial["quest_states"],
                    "mid": mid["quest_states"],
                    "late": late["quest_states"],
                    "save_count": len(save_paths),
                },
                sort_keys=True,
            )
        finally:
            for save_path in save_paths:
                save_path.unlink(missing_ok=True)

    @game_test
    def test_nouraajd_save_load_optional_quest_object_state(self):
        game = load_game_module()
        save_paths = []

        try:
            g, game_map, player = load_game_map_with_player("nouraajd")
            tavern_dialog = g.createObject("tavernDialog2")
            tavern_dialog.talked_to_victor()
            town_hall = g.createObject("townHallDialog")
            town_hall.spawn_cultists()

            self.assertEqual("encounter_active", game_map.getStringProperty("quest_state_victor"))
            g, game_map, player, encounter = assert_nouraajd_save_load_roundtrip(
                self,
                game,
                game_map,
                "nouraajd_victor_encounter_invariants",
                save_paths,
                object_names=("cultLeaderQuest",),
                object_prefixes=("victorCultist",),
            )
            self.assertTrue(encounter["objects"]["cultLeaderQuest"])
            self.assertGreater(encounter["object_prefix_counts"]["victorCultist"], 0)
            self.assertGreaterEqual(encounter["victor_turn"], 0)

            leader = find_runtime_object(game_map, "cultLeaderQuest")
            game_map.removeObjectByName(leader.getName())
            player.checkQuests()
            pump_event_loop(5)

            self.assertEqual("good_end", game_map.getStringProperty("quest_state_victor"))
            g, game_map, player, victor_done = assert_nouraajd_save_load_roundtrip(
                self,
                game,
                game_map,
                "nouraajd_victor_good_invariants",
                save_paths,
                object_names=("cultLeaderQuest",),
                object_prefixes=("victorCultist",),
            )
            self.assertFalse(victor_done["objects"]["cultLeaderQuest"])
            self.assertEqual(0, victor_done["object_prefix_counts"]["victorCultist"])
            self.assertTrue(victor_done["map_flags"]["VICTOR_GOOD_END"])
            self.assertTrue(victor_done["map_flags"]["VICTOR_REWARD_CLAIMED"])
            self.assertIn("victorQuest", victor_done["completed_quests"])

            quest_dialog = g.createObject("questDialog")
            quest_dialog.start_amulet_quest()
            self.assertEqual("active", game_map.getStringProperty("quest_state_amulet"))
            g, game_map, player, amulet_active = assert_nouraajd_save_load_roundtrip(
                self,
                game,
                game_map,
                "nouraajd_amulet_active_invariants",
                save_paths,
                object_names=("oldWoman", "amuletGoblin"),
            )
            self.assertTrue(amulet_active["objects"]["oldWoman"])
            self.assertTrue(amulet_active["objects"]["amuletGoblin"])

            player.addItem("preciousAmulet")
            quest_return_dialog = g.createObject("questReturnDialog")
            quest_return_dialog.complete_amulet_quest()
            player.checkQuests()
            pump_event_loop(3)

            self.assertEqual("returned", game_map.getStringProperty("quest_state_amulet"))
            g, game_map, player, amulet_returned = assert_nouraajd_save_load_roundtrip(
                self,
                game,
                game_map,
                "nouraajd_amulet_returned_invariants",
                save_paths,
                object_names=("oldWoman", "amuletGoblin"),
            )
            self.assertFalse(amulet_returned["objects"]["oldWoman"])
            self.assertFalse(amulet_returned["objects"]["amuletGoblin"])
            self.assertTrue(amulet_returned["map_flags"]["AMULET_RETURNED"])
            self.assertEqual(0, amulet_returned["items"]["preciousAmulet"])
            self.assertIn("amuletQuest", amulet_returned["completed_quests"])

            return True, json.dumps(
                {
                    "victor": victor_done["quest_states"]["victor"],
                    "amulet": amulet_returned["quest_states"]["amulet"],
                    "save_count": len(save_paths),
                },
                sort_keys=True,
            )
        finally:
            for save_path in save_paths:
                save_path.unlink(missing_ok=True)

    @game_test
    def test_nouraajd_save_load_after_ritual_transition(self):
        game = load_game_module()
        g, game_map, player = load_game_map_with_player("nouraajd")
        town_hall = g.createObject("townHallDialog")
        beren = g.createObject("berenDialog")

        town_hall.give_letter()
        beren.deliver_letter()
        game_map.removeObjectByName("catacombs")
        beren.return_relic()
        game_map.removeObjectByName("cave2")
        player.checkQuests()
        pump_event_loop(3)

        self.assertTrue(beren.can_finish_cleanse())
        beren.finish_cleanse()
        pump_event_loop(10)

        ritual_map = g.getMap()
        ritual_player = ritual_map.getPlayer()
        self.assertEqual("ritual", ritual_map.mapName)

        before = {
            "map": ritual_map.mapName,
            "player": coords_tuple(ritual_player.getCoords()),
            "turn": ritual_map.getTurn(),
            "active_quests": quest_names(ritual_player),
            "completed_quests": completed_quest_names(ritual_player),
            "player_flags": {flag: ritual_player.getBoolProperty(flag) for flag in NOURAAJD_PLAYER_BOOL_FLAGS},
        }

        save_path, loaded_game, loaded_map, loaded_player = save_load_roundtrip(
            game,
            ritual_map,
            "nouraajd_ritual_transition_invariants",
        )
        try:
            after = {
                "map": loaded_map.mapName,
                "player": coords_tuple(loaded_player.getCoords()),
                "turn": loaded_map.getTurn(),
                "active_quests": quest_names(loaded_player),
                "completed_quests": completed_quest_names(loaded_player),
                "player_flags": {flag: loaded_player.getBoolProperty(flag) for flag in NOURAAJD_PLAYER_BOOL_FLAGS},
            }

            self.assertEqual(before, after)
            self.assertEqual("ritual", loaded_map.mapName)
            self.assertNotIn("cleanseCaveQuest", after["active_quests"])
            self.assertIn("cleanseCaveQuest", after["completed_quests"])
            self.assertIsNotNone(get_player_controller(loaded_player))
            self.assertIsNotNone(loaded_player.getFightController())

            return True, json.dumps(after, sort_keys=True)
        finally:
            save_path.unlink(missing_ok=True)

    @game_test
    def test_playtest_trace_records_core_gameplay_events(self):
        game = load_game_module()
        game.configure_playtest_trace(True)
        try:
            g, game_map, player = load_game_map_with_player("nouraajd")
            target = find_adjacent_walkable_tile(game_map, player.getCoords())
            player.moveTo(target.x, target.y, target.z)
            player.addItem("letterFromRolf")
            player.addQuest("rolfQuest")
            game_map.removeObjectByName("cave1")

            _combat_game, _session, attacker, defenders = self.make_multi_enemy_combat_fixture()
            attacker.addGold(25)
            game.CFightHandler.fightMany(attacker, defenders)

            g.changeMap("ritual")
            pump_event_loop(10)

            trace = game.drain_playtest_trace()
        finally:
            game.configure_playtest_trace(False)

        names = event_names(trace)
        for expected in (
            "movement",
            "inventory_added",
            "quest_added",
            "quest_state_changed",
            "gold_changed",
            "combat_started",
            "combat_finished",
            "reward_granted",
            "map_transition_requested",
            "map_transition_completed",
        ):
            self.assertIn(expected, names)

        self.assertTrue(any(record.get("map") == "nouraajd" for record in trace))
        self.assertTrue(
            any(
                record.get("event") == "inventory_added" and (record.get("item") or {}).get("id") == "letterFromRolf"
                for record in trace
            )
        )
        self.assertTrue(
            any(
                record.get("event") == "quest_state_changed"
                and record.get("quest") == "rolf"
                and record.get("current") == "skull_recovered"
                for record in trace
            )
        )
        self.assertTrue(
            any(
                record.get("event") == "map_transition_completed" and record.get("toMap") == "ritual"
                for record in trace
            )
        )
        return True, json.dumps({"events": names, "trace": trace}, sort_keys=True)

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


class ConsoleEventIsolationTest(unittest.TestCase):
    def test_console_key_history_in_fresh_process(self):
        if os.environ.get("GAME_CONSOLE_EVENT_CHILD") == "1":
            self.skipTest("console event child process runs only the focused console test.")
        if os.name != "posix":
            self.skipTest("console event isolation test is Linux/Unix only.")

        env = os.environ.copy()
        env.update(
            {
                "GAME_CONSOLE_EVENT_CHILD": "1",
                "GAME_TEST_WORKER": "1",
                "GAME_TEST_JOBS": "1",
                "GAME_TEST_OUTPUT_DIR": str(TEST_OUTPUT_DIR / "console"),
                "SDL_VIDEODRIVER": "dummy",
                "SDL_AUDIODRIVER": "dummy",
                "SDL_RENDER_DRIVER": "software",
                "LIBGL_ALWAYS_SOFTWARE": "1",
                "GAME_ENABLE_PYTHON_CONSOLE": "1",
            }
        )
        child_timeout = 180 if os.environ.get("GAME_COVERAGE_RUN") == "1" else 45
        completed = subprocess.run(
            [sys.executable, str(REPO_ROOT / "test.py"), "ConsoleEventProcessTest.test_console_key_history"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=child_timeout,
        )

        self.assertEqual(
            0,
            completed.returncode,
            f"console event child failed.\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )


class ConsoleEventProcessTest(unittest.TestCase):
    def setUp(self):
        if os.environ.get("GAME_CONSOLE_EVENT_CHILD") != "1":
            self.skipTest("Run through ConsoleEventIsolationTest so the event loop is isolated.")

    def test_console_key_history(self):
        game = load_game_module()
        drain_sdl_events()
        g = game.CGameLoader.loadGame()
        game.CGameLoader.loadGui(g)
        game.CGameLoader.startGameWithPlayer(g, "test", "Warrior")
        pump_event_loop(5)

        console = collect_gui_children(g.getGui(), "CConsoleGraphicsObject")[0]
        command = "logger('console child coverage')"

        push_sdl_key_event(SDLK_TAB, 0)
        pump_event_loop(2)
        console.consoleState = command
        push_sdl_key_event(SDLK_RETURN, 0)
        pump_event_loop(2)
        self.assertEqual("", console.consoleState)

        push_sdl_key_event(SDLK_TAB, 0)
        pump_event_loop(2)
        push_sdl_key_event(SDLK_UP, 0)
        pump_event_loop(2)
        self.assertEqual(command, console.consoleState)
        push_sdl_key_event(SDLK_DOWN, 0)
        pump_event_loop(2)
        self.assertEqual("", console.consoleState)

        console.consoleState = "first"
        push_sdl_key_event(SDLK_BACKSPACE, 0)
        pump_event_loop(2)
        self.assertEqual("firs", console.consoleState)
        push_sdl_key_event(SDLK_TAB, 0)
        pump_event_loop(2)
        self.assertEqual("", console.consoleState)


class XvfbGameplayTest(unittest.TestCase):
    def test_keyboard_gameplay_under_xvfb(self):
        if os.environ.get("GAME_XVFB_GAMEPLAY_CHILD") == "1":
            self.skipTest("xvfb child process runs only the focused gameplay test.")
        if os.name != "posix":
            self.skipTest("xvfb gameplay test is Linux/Unix only.")
        if shutil.which("xvfb-run") is None:
            self.skipTest("xvfb-run is not available.")
        if shutil.which("xauth") is None:
            self.skipTest("xauth is not available for xvfb-run.")
        available, reason = sdl_x11_video_driver_available()
        if not available:
            self.skipTest(f"SDL x11 video driver is not available under xvfb: {reason}")

        child_env_defaults = {
            "GAME_XVFB_GAMEPLAY_CHILD": "1",
            "GAME_TEST_WORKER": "1",
            "GAME_TEST_JOBS": "1",
            "SDL_VIDEODRIVER": "x11",
            "SDL_AUDIODRIVER": "dummy",
            "SDL_RENDER_DRIVER": "software",
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        wrapper_env = os.environ.copy()
        for key in child_env_defaults:
            wrapper_env.pop(key, None)
        command = [
            "xvfb-run",
            "-a",
            "--server-args=-screen 0 1920x1080x24",
            "env",
            sys.executable,
            str(REPO_ROOT / "test.py"),
        ]

        try:
            xvfb_jobs = parse_positive_int(
                os.environ.get("GAME_XVFB_JOBS", str(default_xvfb_jobs())),
                "GAME_XVFB_JOBS",
            )
        except ValueError as exc:
            self.fail(str(exc))

        def run_child_group(group_name, child_tests):
            child_env = child_env_defaults | {
                "GAME_TEST_OUTPUT_DIR": str(TEST_OUTPUT_DIR / "xvfb" / group_name),
                "GAME_TEST_SHARD": f"xvfb-{group_name}",
            }
            child_env_args = [f"{key}={value}" for key, value in sorted(child_env.items())]
            child_test_args = [f"XvfbGameplayProcessTest.{child_test}" for child_test in child_tests]
            duration_hint = sum(XVFB_GAMEPLAY_CHILD_DURATION_HINTS.get(child_test, 1) for child_test in child_tests)
            timeout = max(XVFB_GAMEPLAY_CHILD_TIMEOUT * max(1, len(child_tests)), duration_hint * 3)
            proc = None
            try:
                proc = subprocess.Popen(
                    command[:4] + child_env_args + command[4:] + child_test_args,
                    cwd=REPO_ROOT,
                    env=wrapper_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=(os.name == "posix"),
                )
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                if proc is not None:
                    if os.name == "posix":
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    else:
                        proc.kill()
                    stdout, stderr = proc.communicate()
                else:
                    stdout = exc.stdout or ""
                    stderr = exc.stderr or ""
                return (
                    f"{group_name} timed out while running {', '.join(child_tests)}.\n"
                    f"stdout:\n{stdout}\nstderr:\n{stderr}"
                )

            if proc.returncode != 0:
                return (
                    f"{group_name} failed with {proc.returncode} while running {', '.join(child_tests)}.\n"
                    f"stdout:\n{stdout}\nstderr:\n{stderr}"
                )
            return None

        selected_child_tests = list(XVFB_GAMEPLAY_CHILD_TESTS)
        only_child_tests = parse_name_filter(os.environ.get("GAME_XVFB_ONLY_CHILD_TESTS"))
        if only_child_tests:
            selected_child_tests = [child_test for child_test in selected_child_tests if child_test in only_child_tests]
        skipped_child_tests = parse_name_filter(os.environ.get("GAME_XVFB_SKIP_CHILD_TESTS"))
        if skipped_child_tests:
            selected_child_tests = [
                child_test for child_test in selected_child_tests if child_test not in skipped_child_tests
            ]

        parallel_child_tests = [
            child_test for child_test in selected_child_tests if child_test not in XVFB_SAVE_MUTATING_CHILD_TESTS
        ]
        serial_child_tests = [
            child_test for child_test in selected_child_tests if child_test in XVFB_SAVE_MUTATING_CHILD_TESTS
        ]
        isolate_children = os.environ.get("GAME_XVFB_ISOLATE") == "1"
        if isolate_children:
            parallel_child_groups = [(child_test, [child_test]) for child_test in parallel_child_tests]
        else:
            batchable_child_tests = [
                child_test for child_test in parallel_child_tests if child_test in XVFB_BATCHABLE_CHILD_TESTS
            ]
            isolated_child_tests = [
                child_test for child_test in parallel_child_tests if child_test not in XVFB_BATCHABLE_CHILD_TESTS
            ]
            child_jobs = min(xvfb_jobs, len(batchable_child_tests)) if batchable_child_tests else 0
            parallel_child_groups = [
                (f"group-{index}", group)
                for index, group in enumerate(
                    shard_test_names(
                        batchable_child_tests,
                        child_jobs,
                        XVFB_GAMEPLAY_CHILD_DURATION_HINTS,
                    ),
                    start=1,
                )
            ]
            parallel_child_groups.extend((child_test, [child_test]) for child_test in isolated_child_tests)

        failure_by_group = {}
        if parallel_child_tests:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(xvfb_jobs, len(parallel_child_groups))
            ) as executor:
                futures = {
                    executor.submit(run_child_group, group_name, child_tests): group_name
                    for group_name, child_tests in parallel_child_groups
                }
                for future in concurrent.futures.as_completed(futures):
                    group_name = futures[future]
                    failure = future.result()
                    if failure:
                        failure_by_group[group_name] = failure

        for child_test in serial_child_tests:
            failure = run_child_group(child_test, [child_test])
            if failure:
                failure_by_group[child_test] = failure

        child_group_order = [*parallel_child_groups, *((child_test, [child_test]) for child_test in serial_child_tests)]
        failures = [
            failure_by_group[group_name] for group_name, _ in child_group_order if group_name in failure_by_group
        ]

        self.assertFalse(
            failures,
            "xvfb gameplay scenarios failed:\n\n" + "\n\n".join(failures),
        )


def create_xvfb_gameplay_session(test_case, map_name="test", player_name=DEFAULT_PLAYER):
    test_case.assertEqual("x11", os.environ.get("SDL_VIDEODRIVER"))
    test_case.assertIn("DISPLAY", os.environ)

    game = load_game_module()
    g = game.CGameLoader.loadGame()
    game.CGameLoader.loadGui(g)
    game.CGameLoader.startGameWithPlayer(g, map_name, player_name)
    pump_event_loop(5)
    return game, g, g.getMap(), g.getMap().getPlayer()


def wait_for_panel_class(test_case, g, class_name, timeout=5.0):
    test_case.assertTrue(
        pump_event_loop_until(lambda: gui_contains_class(g, class_name), timeout=timeout),
        f"Expected {class_name} to be visible.",
    )


def assert_player_moves_to_key_target(test_case, game_map, player, target, keycode, scancode):
    initial_turn = game_map.getTurn()
    push_sdl_key_event(keycode, scancode, SDL_KEYDOWN)
    push_sdl_key_event(keycode, scancode, SDL_KEYUP)
    pump_event_loop(5)

    moved = player.getCoords()
    test_case.assertEqual((target.x, target.y, target.z), (moved.x, moved.y, moved.z))
    test_case.assertGreater(game_map.getTurn(), initial_turn)


def assert_rendered_map_proxy_cells(test_case, g):
    proxy_counts = get_map_proxy_child_counts(g)
    test_case.assertTrue(proxy_counts, "Expected rendered map proxy cells after xvfb gameplay.")
    test_case.assertEqual(0, sum(count == 0 for count in proxy_counts))


def queue_panel_observer(game, g, class_name):
    observed = {"open": False}

    def observe():
        observed["open"] = gui_contains_class(g, class_name)

    game.event_loop.instance().invoke(observe)
    return observed


def queue_sdl_inputs(game, *callbacks):
    def dispatch():
        for callback in callbacks:
            callback()

    game.event_loop.instance().invoke(dispatch)


def push_space_key():
    push_sdl_key_event(ord(" "), 44, SDL_KEYDOWN)
    push_sdl_key_event(ord(" "), 44, SDL_KEYUP)


def push_digit_key(digit):
    push_sdl_key_event(ord(str(digit)), 0, SDL_KEYDOWN)
    push_sdl_key_event(ord(str(digit)), 0, SDL_KEYUP)


def push_letter_key(letter):
    push_sdl_key_event(ord(letter), 0, SDL_KEYDOWN)
    push_sdl_key_event(ord(letter), 0, SDL_KEYUP)


def push_quest_log_key():
    push_letter_key("j")


def dialog_input_callbacks(inputs):
    callbacks = []
    for input_value in inputs:
        if input_value == "space":
            callbacks.append(push_space_key)
        else:
            callbacks.append(lambda digit=input_value: push_digit_key(digit))
    return callbacks


def run_blocking_gui_action(game, action, *callbacks):
    if callbacks:
        queue_sdl_inputs(game, *callbacks)
    result = action()
    pump_event_loop(5)
    return result


def show_dialog_with_keyboard(test_case, game, g, dialog, inputs):
    observed = queue_panel_observer(game, g, "CGameDialogPanel")
    queue_sdl_inputs(game, *dialog_input_callbacks(inputs))
    g.getGuiHandler().showDialog(dialog)
    pump_event_loop_until(lambda: observed["open"], timeout=1.0)
    test_case.assertTrue(observed["open"], f"{dialog.getTypeId()} should open a dialog panel.")


def open_quest_log_panel(test_case, g):
    panel = g.getGuiHandler().openPanel("questPanel")
    pump_event_loop_until(lambda: gui_contains_class(g, "CGameQuestPanel"), timeout=1.0)
    test_case.assertTrue(gui_contains_class(g, "CGameQuestPanel"))
    return panel


def assert_quest_log_hotkey_opens_panel(test_case, game, g, active=(), completed=()):
    observed = {"open": False, "text": ""}

    def observe_open_panel():
        observed["open"] = gui_contains_class(g, "CGameQuestPanel")
        if observed["open"]:
            observed["text"] = g.getGuiHandler().openPanel("questPanel").getText(g.getGui())

    push_quest_log_key()
    game.event_loop.instance().invoke(observe_open_panel)
    push_quest_log_key()
    pump_event_loop(10)

    test_case.assertTrue(observed["open"], "The j hotkey should open the quest log panel.")
    test_case.assertFalse(gui_contains_class(g, "CGameQuestPanel"), "The second j hotkey should close the quest log.")
    for quest_id in active:
        test_case.assertIn(nouraajd_quest_status_line("Active", quest_id), observed["text"])
    for quest_id in completed:
        test_case.assertIn(nouraajd_quest_status_line("Completed", quest_id), observed["text"])


def nouraajd_quest_status_line(status, quest_id):
    return f"[{status}] {NOURAAJD_QUEST_DESCRIPTIONS[quest_id]}"


def assert_nouraajd_quest_log(test_case, g, active=(), completed=()):
    quest_panel = open_quest_log_panel(test_case, g)
    text = quest_panel.getText(g.getGui())
    for quest_id in active:
        test_case.assertIn(nouraajd_quest_status_line("Active", quest_id), text)
    for quest_id in completed:
        test_case.assertIn(nouraajd_quest_status_line("Completed", quest_id), text)
    return text


def capture_nouraajd_quest_log(test_case, g, name, active=(), completed=()):
    text = assert_nouraajd_quest_log(test_case, g, active=active, completed=completed)
    if name in NOURAAJD_QUEST_LOG_SCREENSHOT_CHECKPOINTS:
        assert_screenshot_has_rendered_pixels(test_case, g, name)
    g.getGuiHandler().openPanel("questPanel").close()
    pump_event_loop(2)
    return text


def player_quest_id(quest):
    if hasattr(quest, "getTypeId"):
        quest_id = quest.getTypeId()
        if quest_id:
            return quest_id
    return quest.getName()


def find_player_quest(player, quest_id):
    quests = list(player.getQuests())
    if hasattr(player, "getCompletedQuests"):
        quests.extend(player.getCompletedQuests())
    for quest in quests:
        if player_quest_id(quest) == quest_id:
            return quest
    return None


def assert_player_quest_state(test_case, player, quest_id, completed):
    quest = find_player_quest(player, quest_id)
    test_case.assertIsNotNone(quest, f"{quest_id} should be present in the player's quest journal.")
    test_case.assertEqual(completed, quest.isCompleted(), f"{quest_id} completion state mismatch.")
    return quest


def open_panel_for_screenshot(test_case, g, panel_name, class_name):
    panel = g.getGuiHandler().openPanel(panel_name)
    wait_for_panel_class(test_case, g, class_name)
    return panel


def wait_for_panel_closed(test_case, g, class_name, timeout=2.0):
    test_case.assertTrue(
        pump_event_loop_until(lambda: not gui_contains_class(g, class_name), timeout=timeout),
        f"Expected {class_name} to be closed.",
    )


def configure_panel_for_layout(g, panel_name, panel):
    if panel_name in {"infoPanel", "textPanel"}:
        panel.setText(f"{panel_name} layout verification")
    elif panel_name == "questionPanel":
        panel.setStringProperty("question", "Continue layout verification?")
    elif panel_name == "fightPanel":
        enemy = g.createObject("GoblinThief")
        enemy.name = "layoutRootGoblin"
        enemy.setHp(enemy.getHpMax())
        panel.setEnemy(enemy)
    elif panel_name == "tradePanel":
        market = g.createObject("CMarket")
        market.setItems({g.createObject("Scroll")})
        panel.setMarket(market)


def open_layout_panel(test_case, g, panel_name):
    expected_class = PANEL_LAYOUT_CASES[panel_name]["class"]
    panel = g.getGuiHandler().openPanel(panel_name)
    wait_for_panel_class(test_case, g, expected_class)
    configure_panel_for_layout(g, panel_name, panel)
    pump_event_loop(3)
    return panel


def run_blocking_panel_inspection(test_case, game, g, class_name, action, inspect, close_input):
    observed = {}

    def inspect_then_close():
        panel = find_top_level_panel(g, class_name)
        if panel is None:
            observed["attempts"] = observed.get("attempts", 0) + 1
            if observed["attempts"] > 1000:
                observed["error"] = f"{class_name} was not visible during blocking inspection."
                return
            game.event_loop.instance().invoke(inspect_then_close)
            return
        try:
            observed["result"] = inspect(panel)
        except Exception:
            observed["error"] = traceback.format_exc()
        finally:
            close_input(panel)

    game.event_loop.instance().invoke(inspect_then_close)
    return_value = action()
    pump_event_loop(5)
    if "error" in observed:
        raise AssertionError(observed["error"])
    test_case.assertIn("result", observed, f"{class_name} inspection did not run.")
    return return_value, observed["result"]


def make_ui_layout_quest(g, index, completed=False):
    quest = g.createObject("CQuest")
    status = "completed" if completed else "active"
    quest.name = f"uiLayoutQuest{index}{status}"
    quest.typeId = quest.name
    quest.description = f"Quest {index}: inspect the panel layout under dense {status} journal content."
    quest.objective = f"Objective {index}: verify wrapped objective text stays inside the quest panel rectangle."
    quest.reward = f"Reward {index}: deterministic diagnostics for the layout harness."
    quest.hint = f"Hint {index}: this hint should only appear while the quest is active."
    return quest


def make_dialog_state(g, state_id, text, option_texts, next_state="EXIT"):
    state = g.createObject("CDialogState")
    state.stateId = state_id
    state.text = text
    options = set()
    for number, option_text in enumerate(option_texts):
        option = g.createObject("CDialogOption")
        option.number = number
        option.text = option_text
        option.nextStateId = next_state
        options.add(option)
    state.setOptions(options)
    return state


def make_dialog(g, states):
    dialog = g.createObject("CDialog")
    dialog.setStates(set(states))
    return dialog


def make_unique_scroll_items(g, count, prefix):
    items = []
    for index in range(count):
        item = g.createObject("Scroll")
        item.name = f"{prefix}Scroll{index}"
        item.typeId = f"{prefix}ScrollType{index}"
        item.animation = "images/items/scroll"
        items.append(item)
    return items


class PanelLayoutManifestTest(unittest.TestCase):
    def test_panel_layout_manifest_matches_panels_json(self):
        panel_defs = json.loads((REPO_ROOT / "res" / "config" / "panels.json").read_text())
        self.assertEqual(set(panel_defs), set(PANEL_LAYOUT_CASES))

        xvfb_methods = {name for name in dir(XvfbGameplayProcessTest) if name.startswith("test_")}
        for resource_id, case in PANEL_LAYOUT_CASES.items():
            with self.subTest(resource_id=resource_id):
                self.assertIn("class", case)
                self.assertEqual(panel_defs[resource_id].get("class"), case["class"])
                for test_name in case["tests"]:
                    self.assertIn(test_name, xvfb_methods)
                    self.assertIn(test_name, XVFB_GAMEPLAY_CHILD_TESTS)
                if case["kind"] == "panel":
                    self.assertIn("layout", panel_defs[resource_id].get("properties", {}))
                    self.assertIn("root", case)
                else:
                    self.assertIn("parent", case)


class XvfbGameplayProcessTest(unittest.TestCase):
    def setUp(self):
        if os.environ.get("GAME_XVFB_GAMEPLAY_CHILD") != "1":
            self.skipTest("Run through XvfbGameplayTest so SDL uses xvfb instead of the dummy video driver.")

    def test_keyboard_input_moves_player(self):
        _, g, game_map, player = create_xvfb_gameplay_session(self)
        initial = player.getCoords()
        target, keycode, scancode = find_adjacent_walkable_direction(game_map, initial)

        assert_player_moves_to_key_target(self, game_map, player, target, keycode, scancode)
        assert_rendered_map_proxy_cells(self, g)

    def test_mouse_click_moves_player(self):
        _, g, game_map, player = create_xvfb_gameplay_session(self)
        initial = player.getCoords()
        target, _, _ = find_adjacent_walkable_direction(game_map, initial)
        click_x, click_y = visible_map_cell_center(initial, target)
        initial_turn = game_map.getTurn()

        push_sdl_mouse_click(click_x, click_y)
        pump_event_loop(5)

        moved = player.getCoords()
        self.assertEqual((target.x, target.y, target.z), (moved.x, moved.y, moved.z))
        self.assertGreater(game_map.getTurn(), initial_turn)
        assert_rendered_map_proxy_cells(self, g)

    def test_window_resize_event_updates_gui_dimensions(self):
        _, g, _, _ = create_xvfb_gameplay_session(self)
        gui = g.getGui()
        map_graph = next(child for child in collect_gui_children(gui, "CMapGraphicsObject"))

        width, height = push_sdl_window_size_changed_event(800, 600)
        tile_size = gui.getNumericProperty("tileSize")
        expected_proxy_count = (width // tile_size + 1) * (height // tile_size + 1)

        self.assertTrue(
            pump_event_loop_until(
                lambda: (
                    gui.getNumericProperty("width") == width
                    and gui.getNumericProperty("height") == height
                    and len(map_graph.getChildren()) == expected_proxy_count
                ),
                timeout=2.0,
                min_iterations=2,
            )
        )
        self.assertEqual((0, 0, width, height), tuple(gui.getResolvedRect()))
        self.assertEqual((0, 0, width, height), tuple(map_graph.getResolvedRect()))
        self.assertEqual(expected_proxy_count, len(map_graph.getChildren()))
        assert_rendered_map_proxy_cells(self, g)

    def test_screenshot_readback_has_rendered_pixels(self):
        _, g, _, _ = create_xvfb_gameplay_session(self)
        assert_screenshot_has_rendered_pixels(self, g, "xvfb_gameplay_screenshot")

    def test_screenshot_minimap_has_rendered_pixels(self):
        _, g, _, _ = create_xvfb_gameplay_session(self)
        summary = assert_minimap_has_rendered_pixels(self, g, "xvfb_minimap_screenshot")
        self.assertTrue(gui_contains_class(g, "CMinimapGraphicsObject"))
        self.assertGreaterEqual(summary["color_counts"].get(MINIMAP_PLAYER_RGB, 0), 20)

    def test_screenshot_after_keyboard_move_has_rendered_pixels(self):
        _, g, game_map, player = create_xvfb_gameplay_session(self)
        initial = player.getCoords()
        target, keycode, scancode = find_adjacent_walkable_direction(game_map, initial)

        assert_player_moves_to_key_target(self, game_map, player, target, keycode, scancode)
        assert_screenshot_has_rendered_pixels(self, g, "xvfb_keyboard_move_screenshot")

    def test_screenshot_after_mouse_move_has_rendered_pixels(self):
        _, g, game_map, player = create_xvfb_gameplay_session(self)
        initial = player.getCoords()
        target, _, _ = find_adjacent_walkable_direction(game_map, initial)
        click_x, click_y = visible_map_cell_center(initial, target)

        push_sdl_mouse_click(click_x, click_y)
        pump_event_loop(5)

        moved = player.getCoords()
        self.assertEqual((target.x, target.y, target.z), (moved.x, moved.y, moved.z))
        assert_screenshot_has_rendered_pixels(self, g, "xvfb_mouse_move_screenshot")

    def test_screenshot_after_save_hotkey_has_rendered_pixels(self):
        _, g, game_map, _ = create_xvfb_gameplay_session(self)
        marker = f"xvfb-screenshot-{os.getpid()}-{time.monotonic_ns()}"
        game_map.setStringProperty("xvfb_save_marker", marker)

        push_sdl_key_event(ord("s"), 0, SDL_KEYDOWN)
        push_sdl_key_event(ord("s"), 0, SDL_KEYUP)
        pump_event_loop(5)

        assert_screenshot_has_rendered_pixels(self, g, "xvfb_save_hotkey_screenshot")

    def test_screenshot_after_wait_hotkey_has_rendered_pixels(self):
        _, g, game_map, _ = create_xvfb_gameplay_session(self)
        initial_turn = game_map.getTurn()

        push_sdl_key_event(ord(" "), 44, SDL_KEYDOWN)
        push_sdl_key_event(ord(" "), 44, SDL_KEYUP)
        pump_event_loop(5)

        self.assertGreater(game_map.getTurn(), initial_turn)
        assert_screenshot_has_rendered_pixels(self, g, "xvfb_wait_hotkey_screenshot")

    def test_screenshot_character_panel_has_rendered_pixels(self):
        _, g, _, _ = create_xvfb_gameplay_session(self)
        open_panel_for_screenshot(self, g, "characterPanel", "CGameCharacterPanel")
        assert_screenshot_has_rendered_pixels(self, g, "xvfb_character_panel_screenshot")

    def test_screenshot_info_panel_has_rendered_pixels(self):
        _, g, _, _ = create_xvfb_gameplay_session(self)
        panel = open_panel_for_screenshot(self, g, "infoPanel", "CGameTextPanel")
        panel.setStringProperty("text", "xvfb screenshot verification")
        pump_event_loop(5)
        assert_screenshot_has_rendered_pixels(self, g, "xvfb_info_panel_screenshot")

    def test_screenshot_inventory_panel_has_rendered_pixels(self):
        _, g, _, player = create_xvfb_gameplay_session(self)
        player.addItem("Sword")
        open_panel_for_screenshot(self, g, "inventoryPanel", "CGameInventoryPanel")
        assert_screenshot_has_rendered_pixels(self, g, "xvfb_inventory_panel_screenshot")

    def test_screenshot_inventory_item_selection_has_rendered_pixels(self):
        _, g, _, player = create_xvfb_gameplay_session(self)
        player.addItem("Sword")
        open_panel_for_screenshot(self, g, "inventoryPanel", "CGameInventoryPanel")

        push_sdl_mouse_click(585, 265)
        pump_event_loop(5)

        assert_screenshot_has_rendered_pixels(self, g, "xvfb_inventory_item_selection_screenshot")

    def test_screenshot_inventory_equipped_selection_has_rendered_pixels(self):
        _, g, _, player = create_xvfb_gameplay_session(self)
        player.addItem("Sword")
        open_panel_for_screenshot(self, g, "inventoryPanel", "CGameInventoryPanel")

        push_sdl_mouse_click(585, 265)
        push_sdl_mouse_click(1185, 265)
        pump_event_loop(5)

        assert_screenshot_has_rendered_pixels(self, g, "xvfb_inventory_equipped_selection_screenshot")

    def test_inventory_equipped_selection_resets_inventory_selection(self):
        _, g, _, player = create_xvfb_gameplay_session(self)
        player.addItem("Sword")
        panel = open_panel_for_screenshot(self, g, "inventoryPanel", "CGameInventoryPanel")

        push_sdl_mouse_click(585, 265)
        pump_event_loop(5)
        selected_after_inventory = get_panel_selection_box_counts_by_collection(panel)

        push_sdl_mouse_click(1185, 265)
        pump_event_loop(5)
        selected_after_equip = get_panel_selection_box_counts_by_collection(panel)

        push_sdl_mouse_click(1185, 265)
        pump_event_loop(5)
        selected_after_equipped_click = get_panel_selection_box_counts_by_collection(panel)

        self.assertEqual(1, selected_after_inventory.get("inventoryCollection", 0))
        self.assertEqual(0, selected_after_equip.get("inventoryCollection", 0))
        self.assertEqual(0, selected_after_equip.get("equippedCollection", 0))
        self.assertEqual(0, selected_after_equipped_click.get("inventoryCollection", 0))
        self.assertEqual(1, selected_after_equipped_click.get("equippedCollection", 0))

    def test_inventory_drag_release_outside_source_equips_item(self):
        _, g, _, player = create_xvfb_gameplay_session(self)
        player.addItem("ChaosSword")
        panel = open_panel_for_screenshot(self, g, "inventoryPanel", "CGameInventoryPanel")
        list_views = collect_gui_children(panel, "CListView")
        inventory_list = next(
            list_view for list_view in list_views if list_view.getCollection() == "inventoryCollection"
        )
        equipped_list = next(list_view for list_view in list_views if list_view.getCollection() == "equippedCollection")
        inventory_rect = inventory_list.getResolvedRect()
        equipped_rect = equipped_list.getResolvedRect()
        start_x = inventory_rect[0] + 25
        start_y = inventory_rect[1] + 25
        outside_source_x = inventory_rect[0] + inventory_rect[2] + 20
        outside_source_y = start_y
        target_x = equipped_rect[0] + 25
        target_y = equipped_rect[1] + 25
        inventory_before = player.countItems("ChaosSword")

        push_sdl_mouse_button_event(start_x, start_y, SDL_BUTTON_LEFT, SDL_MOUSEBUTTONDOWN)
        pump_event_loop(3)
        self.assertTrue(g.getGui().hasDragSession())
        self.assertTrue(g.getGui().hasPointerCapture())

        push_sdl_mouse_motion_event(outside_source_x, outside_source_y, outside_source_x - start_x, 0)
        pump_event_loop(3)
        self.assertTrue(g.getGui().hasDragSession())
        self.assertTrue(g.getGui().hasPointerCapture())

        push_sdl_mouse_button_event(target_x, target_y, SDL_BUTTON_LEFT, SDL_MOUSEBUTTONUP)
        pump_event_loop(5)

        self.assertFalse(g.getGui().hasDragSession())
        self.assertFalse(g.getGui().hasPointerCapture())
        self.assertEqual(inventory_before - 1, player.countItems("ChaosSword"))
        self.assertEqual("ChaosSword", player.getWeapon().getTypeId())

    def test_inventory_preselected_drag_release_equips_item(self):
        _, g, _, player = create_xvfb_gameplay_session(self)
        player.addItem("ChaosSword")
        panel = open_panel_for_screenshot(self, g, "inventoryPanel", "CGameInventoryPanel")
        list_views = collect_gui_children(panel, "CListView")
        inventory_list = next(
            list_view for list_view in list_views if list_view.getCollection() == "inventoryCollection"
        )
        equipped_list = next(list_view for list_view in list_views if list_view.getCollection() == "equippedCollection")
        inventory_rect = inventory_list.getResolvedRect()
        equipped_rect = equipped_list.getResolvedRect()
        start_x = inventory_rect[0] + 25
        start_y = inventory_rect[1] + 25
        outside_source_x = inventory_rect[0] + inventory_rect[2] + 20
        outside_source_y = start_y
        target_x = equipped_rect[0] + 25
        target_y = equipped_rect[1] + 25

        push_sdl_mouse_click(start_x, start_y)
        pump_event_loop(5)
        self.assertEqual(1, get_panel_selection_box_counts_by_collection(panel).get("inventoryCollection", 0))

        inventory_before = player.countItems("ChaosSword")
        push_sdl_mouse_button_event(start_x, start_y, SDL_BUTTON_LEFT, SDL_MOUSEBUTTONDOWN)
        pump_event_loop(3)
        self.assertTrue(g.getGui().hasDragSession())
        self.assertTrue(g.getGui().hasPointerCapture())

        push_sdl_mouse_motion_event(outside_source_x, outside_source_y, outside_source_x - start_x, 0)
        pump_event_loop(3)
        self.assertTrue(g.getGui().hasDragSession())
        self.assertTrue(g.getGui().hasPointerCapture())

        push_sdl_mouse_button_event(target_x, target_y, SDL_BUTTON_LEFT, SDL_MOUSEBUTTONUP)
        pump_event_loop(5)

        self.assertFalse(g.getGui().hasDragSession())
        self.assertFalse(g.getGui().hasPointerCapture())
        self.assertEqual(inventory_before - 1, player.countItems("ChaosSword"))
        self.assertEqual("ChaosSword", player.getWeapon().getTypeId())

    def test_inventory_drag_rejects_invalid_equipment_slot(self):
        _, g, _, player = create_xvfb_gameplay_session(self)
        player.addItem("ChaosSword")
        panel = open_panel_for_screenshot(self, g, "inventoryPanel", "CGameInventoryPanel")
        inventory_list = find_list_view(panel, "inventoryCollection")
        equipped_list = find_list_view(panel, "equippedCollection")
        inventory_before = player.countItems("ChaosSword")
        weapon_before = player.getWeapon().getTypeId() if player.getWeapon() else None

        drag_list_cell_to_cell(self, g, inventory_list, 0, 0, equipped_list, 3, 0)

        weapon_after = player.getWeapon().getTypeId() if player.getWeapon() else None
        self.assertEqual(inventory_before, player.countItems("ChaosSword"))
        self.assertEqual(weapon_before, weapon_after)

    def test_inventory_drag_unequips_to_inventory(self):
        _, g, _, player = create_xvfb_gameplay_session(self)
        player.addItem("ChaosSword")
        panel = open_panel_for_screenshot(self, g, "inventoryPanel", "CGameInventoryPanel")
        inventory_list = find_list_view(panel, "inventoryCollection")
        equipped_list = find_list_view(panel, "equippedCollection")

        drag_list_cell_to_cell(self, g, inventory_list, 0, 0, equipped_list, 0, 0)
        self.assertEqual("ChaosSword", player.getWeapon().getTypeId())
        self.assertEqual(0, player.countItems("ChaosSword"))

        drag_list_cell_to_cell(self, g, equipped_list, 0, 0, inventory_list, 1, 0)

        self.assertIsNone(player.getWeapon())
        self.assertEqual(1, player.countItems("ChaosSword"))

    def test_inventory_drag_quest_item_rejection(self):
        game, g, _, player = create_xvfb_gameplay_session(self, map_name="nouraajd")
        quest_item = g.createObject("letterToBeren")
        self.assertTrue(quest_item.hasTag(game.CTag.QUEST))
        player.addItem(quest_item)
        panel = open_panel_for_screenshot(self, g, "inventoryPanel", "CGameInventoryPanel")
        inventory_list = find_list_view(panel, "inventoryCollection")
        equipped_list = find_list_view(panel, "equippedCollection")
        weapon_before = player.getWeapon().getTypeId() if player.getWeapon() else None
        start_x, start_y = rect_center(list_cell_rect(inventory_list, 0, 0))
        target_x, target_y = rect_center(list_cell_rect(equipped_list, 0, 0))

        push_sdl_mouse_button_event(start_x, start_y, SDL_BUTTON_LEFT, SDL_MOUSEBUTTONDOWN)
        pump_event_loop(3)
        self.assertFalse(g.getGui().hasDragSession())
        self.assertFalse(g.getGui().hasPointerCapture())

        push_sdl_mouse_motion_event(target_x, target_y, target_x - start_x, target_y - start_y)
        push_sdl_mouse_button_event(target_x, target_y, SDL_BUTTON_LEFT, SDL_MOUSEBUTTONUP)
        pump_event_loop(5)

        self.assertEqual(1, player.countItems("letterToBeren"))
        weapon_after = player.getWeapon().getTypeId() if player.getWeapon() else None
        self.assertEqual(weapon_before, weapon_after)

    def test_inventory_quest_item_selection_is_ignored(self):
        game, g, _, player = create_xvfb_gameplay_session(self, map_name="nouraajd")
        quest_item = g.createObject("letterToBeren")
        self.assertTrue(quest_item.hasTag(game.CTag.QUEST))
        player.addItem(quest_item)
        panel = open_panel_for_screenshot(self, g, "inventoryPanel", "CGameInventoryPanel")

        push_sdl_mouse_click(585, 265)
        pump_event_loop(5)
        selected_after_quest_click = get_panel_selection_box_counts_by_collection(panel)

        self.assertEqual(0, selected_after_quest_click.get("inventoryCollection", 0))
        self.assertEqual(0, selected_after_quest_click.get("equippedCollection", 0))

    def test_fight_quest_item_selection_is_ignored(self):
        game, g, _, player = create_xvfb_gameplay_session(self, map_name="nouraajd")
        quest_item = g.createObject("letterToBeren")
        self.assertTrue(quest_item.hasTag(game.CTag.QUEST))
        player.addItem(quest_item)
        panel = g.getGuiHandler().openPanel("fightPanel")
        panel.setEnemy(g.createObject("GoblinThief"))
        wait_for_panel_class(self, g, "CGameFightPanel")

        push_sdl_mouse_click(585, 745)
        pump_event_loop(5)
        selected_after_quest_click = get_panel_selection_box_counts_by_collection(panel)

        self.assertEqual(0, selected_after_quest_click.get("itemsCollection", 0))

    def test_screenshot_question_panel_has_rendered_pixels(self):
        _, g, _, _ = create_xvfb_gameplay_session(self)
        panel = open_panel_for_screenshot(self, g, "questionPanel", "CGameQuestionPanel")
        panel.setStringProperty("question", "Continue xvfb screenshot verification?")
        pump_event_loop(5)
        assert_screenshot_has_rendered_pixels(self, g, "xvfb_question_panel_screenshot")

    def test_screenshot_quest_panel_with_active_quest_has_rendered_pixels(self):
        _, g, _, player = create_xvfb_gameplay_session(self, map_name="nouraajd")
        player.addQuest("mainQuest")
        open_panel_for_screenshot(self, g, "questPanel", "CGameQuestPanel")
        assert_screenshot_has_rendered_pixels(self, g, "xvfb_quest_panel_screenshot")

    def test_panel_harness_info_artifacts(self):
        _, g, _, _ = create_xvfb_gameplay_session(self)
        panel = open_layout_panel(self, g, "infoPanel")
        sibling = None
        panel.setText("isolated panel harness verification")

        try:
            with isolated_gui_panel(g, panel):
                summary = capture_panel_layout(self, g, "layout_harness_info_panel", panel)
            sibling = open_layout_panel(self, g, "inventoryPanel")
            self.assertTrue(gui_has_child_object(g, sibling))
            with self.assertRaises(AssertionError):
                with isolated_gui_panel(g, panel):
                    self.assertFalse(gui_has_child_object(g, sibling))
                    capture_panel_layout(
                        self, g, "layout_harness_info_panel_expected_failure", panel, outside_tolerance=-1
                    )
            self.assertTrue(gui_has_child_object(g, sibling))
        finally:
            if sibling is not None:
                sibling.close()
            panel.close()
            pump_event_loop(3)

        self.assertEqual(list(ROOT_400_300), summary["panel"]["rect"])
        self.assertFalse(any("0x" in json.dumps(obj) for obj in summary["objects"]))
        assert_rendered_map_proxy_cells(self, g)

    def test_all_panel_root_layout_contracts(self):
        _, g, _, _ = create_xvfb_gameplay_session(self)
        top_level_cases = [
            (resource_id, case) for resource_id, case in PANEL_LAYOUT_CASES.items() if case["kind"] == "panel"
        ]
        for resource_id, case in top_level_cases:
            with self.subTest(resource_id=resource_id):
                panel = open_layout_panel(self, g, resource_id)
                try:
                    rect = assert_runtime_rect(self, resource_id, panel, case["root"])
                    assert_rect_on_screen(self, resource_id, rect)
                    self.assertTrue(gui_has_child_object(g, panel))
                    with isolated_gui_panel(g, panel):
                        capture_panel_layout(self, g, f"layout_root_{resource_id}", panel)
                finally:
                    panel.close()
                    pump_event_loop(3)
                self.assertEqual(0, sum(1 for child in g.getGui().getChildren() if child.getType() == case["class"]))
                reopened = open_layout_panel(self, g, resource_id)
                try:
                    assert_runtime_rect(self, f"{resource_id} reopened", reopened, case["root"])
                    self.assertEqual(
                        1, sum(1 for child in g.getGui().getChildren() if child.getType() == case["class"])
                    )
                finally:
                    reopened.close()
                    pump_event_loop(3)
                self.assertEqual(0, sum(1 for child in g.getGui().getChildren() if child.getType() == case["class"]))

    def test_all_top_level_panels_block_outside_map_clicks(self):
        _, g, game_map, player = create_xvfb_gameplay_session(self)
        candidates = ((25, 25), (GUI_WIDTH - 25, 25), (25, GUI_HEIGHT - 25), (960, 100))
        for resource_id, case in PANEL_LAYOUT_CASES.items():
            if case["kind"] != "panel":
                continue
            with self.subTest(resource_id=resource_id):
                panel = open_layout_panel(self, g, resource_id)
                try:
                    panel_rect = resolved_rect(panel)
                    click_point = next(point for point in candidates if not rect_contains_point(panel_rect, *point))
                    before = player.getCoords()
                    before_turn = game_map.getTurn()
                    push_sdl_mouse_click(*click_point)
                    pump_event_loop(5)
                    after = player.getCoords()
                    self.assertEqual((before.x, before.y, before.z), (after.x, after.y, after.z))
                    self.assertEqual(before_turn, game_map.getTurn())
                    self.assertTrue(gui_has_child_object(g, panel))
                finally:
                    panel.close()
                    pump_event_loop(3)

    def test_text_centric_panel_layouts(self):
        _, g, _, player = create_xvfb_gameplay_session(self)
        player.setNumericProperty("gold", 999999)
        player.setNumericProperty("level", 42)
        player.setHp(player.getHpMax())
        player.setMana(999)

        character = open_layout_panel(self, g, "characterPanel")
        try:
            root = assert_runtime_rect(self, "characterPanel", character, ROOT_800_600)
            actions = find_list_view(character, "interactionsCollection")
            action_rect = assert_runtime_rect(self, "character actions", actions, (560, 780, 800, 60))
            assert_child_inside(self, "characterPanel", root, "actions", action_rect)
            assert_no_overlap(self, "character content", (560, 240, 800, 540), "actions", action_rect)
            with isolated_gui_panel(g, character):
                summary = capture_panel_layout(
                    self,
                    g,
                    "layout_character_panel",
                    character,
                    regions={"actions": action_rect},
                )
            assert_region_has_pixels(self, summary, "actions")
        finally:
            character.close()
            pump_event_loop(3)

        info = open_layout_panel(self, g, "infoPanel")
        try:
            assert_runtime_rect(self, "infoPanel", info, ROOT_400_300)
            for centered, text in (
                (True, "Short centered info."),
                (
                    False,
                    "Wrapped info panel text that should occupy the top-left content area without leaving the panel.",
                ),
            ):
                with isolated_gui_panel(g, info):
                    info.setText("")
                    pump_event_loop(3)
                    empty_data, width, _ = capture_sdl_screenshot(
                        TEST_OUTPUT_DIR / f"layout_info_panel_{centered}_empty.png", g.getGui()
                    )
                    info.setCentered(centered)
                    info.setText(text)
                    pump_event_loop(3)
                    text_data, _, _ = capture_sdl_screenshot(
                        TEST_OUTPUT_DIR / f"layout_info_panel_{centered}_text.png", g.getGui()
                    )
                    text_bounds, changed = pixel_diff_bounds(empty_data, text_data, width, ROOT_400_300)
                    self.assertGreater(changed, 0)
                    assert_child_inside(self, "infoPanel", ROOT_400_300, "info text", text_bounds)
                    if centered:
                        expected_center = rect_center(ROOT_400_300)
                        actual_center = rect_center(text_bounds)
                        self.assertLess(abs(expected_center[0] - actual_center[0]), 70)
                        self.assertLess(abs(expected_center[1] - actual_center[1]), 70)
                    else:
                        self.assertLessEqual(text_bounds[0], ROOT_400_300[0] + 25)
                        self.assertLessEqual(text_bounds[1], ROOT_400_300[1] + 25)
                    capture_panel_layout(self, g, f"layout_info_panel_{centered}", info)
        finally:
            info.close()
            pump_event_loop(3)

        text_panel = open_layout_panel(self, g, "textPanel")
        try:
            assert_runtime_rect(self, "textPanel", text_panel, ROOT_800_600)
            with isolated_gui_panel(g, text_panel):
                text_panel.setText("")
                pump_event_loop(3)
                empty_data, width, _ = capture_sdl_screenshot(
                    TEST_OUTPUT_DIR / "layout_text_panel_empty.png", g.getGui()
                )
                text_panel.setText("Short message.")
                pump_event_loop(3)
                short_data, _, _ = capture_sdl_screenshot(
                    TEST_OUTPUT_DIR / "layout_text_panel_short_text.png", g.getGui()
                )
                short_bounds, changed = pixel_diff_bounds(empty_data, short_data, width, ROOT_800_600)
                self.assertGreater(changed, 0)
                short_summary = capture_panel_layout(self, g, "layout_text_panel_short", text_panel)
            long_text = "\n".join(
                ["Long layout paragraph with enough words to wrap inside the text panel." for _ in range(18)]
            )
            with isolated_gui_panel(g, text_panel):
                text_panel.setText(long_text)
                pump_event_loop(3)
                long_data, _, _ = capture_sdl_screenshot(
                    TEST_OUTPUT_DIR / "layout_text_panel_long_text.png", g.getGui()
                )
                long_bounds, changed = pixel_diff_bounds(empty_data, long_data, width, ROOT_800_600)
                self.assertGreater(changed, 0)
                long_summary = capture_panel_layout(self, g, "layout_text_panel_long", text_panel)
            self.assertGreater(long_text.count("\n"), 1)
            self.assertGreater(long_bounds[3], short_bounds[3])
            self.assertGreaterEqual(long_summary["pixels"]["inside"], short_summary["pixels"]["inside"])
            near_limit_text = " ".join(["near-limit wrapped layout content"] * 100)
            self.assertLess(len(near_limit_text), 4096)
            text_panel.setText(near_limit_text)
            pump_event_loop(3)
            with isolated_gui_panel(g, text_panel):
                capture_panel_layout(self, g, "layout_text_panel_near_limit", text_panel)
            push_space_key()
            pump_event_loop(5)
            self.assertFalse(gui_contains_class(g, "CGameTextPanel"))
            reopened_text = open_layout_panel(self, g, "textPanel")
            try:
                assert_runtime_rect(self, "textPanel reopened", reopened_text, ROOT_800_600)
            finally:
                reopened_text.close()
                pump_event_loop(3)
        finally:
            if text_panel in list(g.getGui().getChildren()):
                text_panel.close()
                pump_event_loop(3)

        def assert_quest_panel_state(active_quests, completed_quests, scenario):
            player.setQuests(set(active_quests))
            player.setCompletedQuests(set(completed_quests))
            quest_panel = open_layout_panel(self, g, "questPanel")
            try:
                assert_runtime_rect(self, "questPanel", quest_panel, ROOT_800_600)
                quest_text = quest_panel.getText(g.getGui())
                with isolated_gui_panel(g, quest_panel):
                    capture_panel_layout(self, g, scenario, quest_panel)
                return quest_text
            finally:
                quest_panel.close()
                pump_event_loop(3)

        empty_text = assert_quest_panel_state([], [], "layout_quest_panel_empty")
        self.assertNotIn("uiLayoutQuest", empty_text)

        single_quest = make_ui_layout_quest(g, 0)
        single_text = assert_quest_panel_state([single_quest], [], "layout_quest_panel_single")
        self.assertIn("[Active] Quest 0:", single_text)
        self.assertIn("Objective 0:", single_text)
        self.assertIn("Reward 0:", single_text)
        self.assertIn("Hint 0:", single_text)

        active_quests = [make_ui_layout_quest(g, index) for index in range(4)]
        completed_quests = [make_ui_layout_quest(g, index, completed=True) for index in range(2)]
        dense_text = assert_quest_panel_state(active_quests, completed_quests, "layout_quest_panel_dense")
        self.assertIn("[Active] Quest 0:", dense_text)
        self.assertIn("[Completed] Quest 0:", dense_text)
        completed_block = dense_text.split("[Completed] Quest 0:", 1)[1].split("[", 1)[0]
        self.assertNotIn("Hint 0:", completed_block)

    def test_choice_panel_layouts_and_hitboxes(self):
        game, g, _, _ = create_xvfb_gameplay_session(self)

        def inspect_question(expected_rect, click_rect):
            def inspect(panel):
                root = assert_runtime_rect(self, "questionPanel", panel, ROOT_400_300)
                question = next(child for child in panel.getChildren() if child.getType() == "CWidget")
                question_rect = assert_runtime_rect(self, "question text", question, (760, 390, 400, 225))
                buttons = sorted(find_descendants_by_type(panel, "CButton"), key=lambda child: resolved_rect(child)[0])
                self.assertEqual(2, len(buttons))
                left = assert_runtime_rect(self, "question yes", buttons[0], (760, 615, 200, 75))
                right = assert_runtime_rect(self, "question no", buttons[1], (960, 615, 200, 75))
                assert_no_overlap(self, "YES", left, "NO", right)
                assert_child_inside(self, "questionPanel", root, "YES", left)
                assert_child_inside(self, "questionPanel", root, "NO", right)
                with isolated_gui_panel(g, panel):
                    question_text = panel.question
                    panel.question = ""
                    pump_event_loop(3)
                    empty_data, width, _ = capture_sdl_screenshot(
                        TEST_OUTPUT_DIR / f"layout_question_{expected_rect}_empty.png", g.getGui()
                    )
                    panel.question = question_text
                    pump_event_loop(3)
                    text_data, _, _ = capture_sdl_screenshot(
                        TEST_OUTPUT_DIR / f"layout_question_{expected_rect}_text.png", g.getGui()
                    )
                    text_bounds, changed = pixel_diff_bounds(empty_data, text_data, width, root)
                    self.assertGreater(changed, 0)
                    assert_child_inside(self, "question text", question_rect, "rendered question", text_bounds)
                    assert_no_overlap(self, "rendered question", text_bounds, "YES", left)
                    assert_no_overlap(self, "rendered question", text_bounds, "NO", right)
                    capture_panel_layout(self, g, f"layout_question_{expected_rect}", panel)
                activate_widget(next(button for button in buttons if resolved_rect(button) == click_rect), g.getGui())
                return {"left": left, "right": right}

            return inspect

        answer, _ = run_blocking_panel_inspection(
            self,
            game,
            g,
            "CGameQuestionPanel",
            lambda: g.getGuiHandler().showQuestion("Confirm yes?"),
            inspect_question("yes", (760, 615, 200, 75)),
            lambda panel: None,
        )
        self.assertTrue(answer)
        answer, _ = run_blocking_panel_inspection(
            self,
            game,
            g,
            "CGameQuestionPanel",
            lambda: g.getGuiHandler().showQuestion(
                "Confirm no with a wrapped question prompt that spans enough words to exercise the upper "
                "question rectangle without entering either button hitbox?"
            ),
            inspect_question("no", (960, 615, 200, 75)),
            lambda panel: None,
        )
        self.assertFalse(answer)

        for count in (1, 3, 8):
            options = [f"option{index:02d}" for index in range(count)]
            for selected_index in (0, count - 1):
                selection = g.createObject("CListString")
                for option in options:
                    selection.addValue(option)
                expected_root = centered_screen_rect(300, 75 * count)

                def inspect_selection(panel, selected_index=selected_index, expected_root=expected_root):
                    root = assert_runtime_rect(self, f"selection {count}", panel, expected_root)
                    buttons = sorted(
                        find_descendants_by_type(panel, "CButton"), key=lambda child: resolved_rect(child)[1]
                    )
                    self.assertEqual(count, len(buttons))
                    last_rect = None
                    for index, button in enumerate(buttons):
                        button_rect = resolved_rect(button)
                        assert_positive_rect(self, f"selection button {index}", button_rect)
                        assert_child_inside(self, "selectionPanel", root, f"selection button {index}", button_rect)
                        self.assertEqual(options[index], button.text)
                        if last_rect is not None:
                            assert_no_overlap(
                                self, "previous selection button", last_rect, "selection button", button_rect
                            )
                        last_rect = button_rect
                    with isolated_gui_panel(g, panel):
                        capture_panel_layout(self, g, f"layout_selection_{count}_{selected_index}", panel)
                    activate_widget(buttons[selected_index], g.getGui())
                    return [resolved_rect(button) for button in buttons]

                selected, _ = run_blocking_panel_inspection(
                    self,
                    game,
                    g,
                    "CGamePanel",
                    lambda selection=selection: g.getGuiHandler().showSelection(selection),
                    inspect_selection,
                    lambda panel: None,
                )
                self.assertEqual(options[selected_index], selected)

        entry = make_dialog_state(
            g,
            "ENTRY",
            "Entry dialog text that verifies state reload and wrapped option layout.",
            ["Move to next state"],
            next_state="NEXT",
        )
        next_state = make_dialog_state(
            g,
            "NEXT",
            "Next dialog state with fresh widgets.",
            ["Exit dialog"],
            next_state="EXIT",
        )
        dialog = make_dialog(g, [entry, next_state])

        def inspect_dialog(panel):
            root = assert_runtime_rect(self, "dialogPanel", panel, ROOT_800_600)
            entry_widgets = sorted(
                find_descendants_by_type(panel, "CTextWidget"), key=lambda child: resolved_rect(child)[1]
            )
            self.assertGreaterEqual(len(entry_widgets), 2)
            previous = None
            for widget in entry_widgets:
                widget_rect = resolved_rect(widget)
                assert_positive_rect(self, "dialog widget", widget_rect)
                assert_child_inside(self, "dialogPanel", root, "dialog widget", widget_rect)
                if previous is not None:
                    assert_no_overlap(self, "previous dialog widget", previous, "dialog widget", widget_rect)
                previous = widget_rect
            entry_texts = {widget.text for widget in entry_widgets}
            with isolated_gui_panel(g, panel):
                capture_panel_layout(self, g, "layout_dialog_entry", panel)

            self.assertTrue(panel.keyboardEvent(g.getGui(), SDL_KEYDOWN, ord("1")))
            next_widgets = sorted(
                find_descendants_by_type(panel, "CTextWidget"), key=lambda child: resolved_rect(child)[1]
            )
            self.assertGreaterEqual(len(next_widgets), 2)
            self.assertEqual(ROOT_800_600, resolved_rect(panel))
            next_texts = {widget.text for widget in next_widgets}
            self.assertFalse(any("Entry dialog text" in text for text in next_texts))
            self.assertNotEqual(entry_texts, next_texts)
            with isolated_gui_panel(g, panel):
                capture_panel_layout(self, g, "layout_dialog_next", panel)
            self.assertTrue(panel.keyboardEvent(g.getGui(), SDL_KEYDOWN, ord("1")))
            return {"entry_widgets": len(entry_widgets), "next_widgets": len(next_widgets)}

        run_blocking_panel_inspection(
            self,
            game,
            g,
            "CGameDialogPanel",
            lambda: g.getGuiHandler().showDialog(dialog),
            inspect_dialog,
            lambda panel: None,
        )

        dense_options = [
            (
                f"Dense option {index} with wrapped text that should receive a positive non-overlapping rectangle "
                "inside the dialog option area."
            )
            for index in range(6)
        ]
        dense_state = make_dialog_state(
            g,
            "ENTRY",
            "Dense dialog state with enough options to exercise proportional option layout.",
            dense_options,
            next_state="EXIT",
        )
        dense_dialog = make_dialog(g, [dense_state])

        def inspect_dense_dialog(panel):
            root = assert_runtime_rect(self, "dialogPanel dense", panel, ROOT_800_600)
            widgets = sorted(find_descendants_by_type(panel, "CTextWidget"), key=lambda child: resolved_rect(child)[1])
            self.assertEqual(1 + len(dense_options), len(widgets))
            previous = None
            for widget in widgets:
                widget_rect = resolved_rect(widget)
                assert_positive_rect(self, "dense dialog widget", widget_rect)
                assert_child_inside(self, "dialogPanel", root, "dense dialog widget", widget_rect)
                if previous is not None:
                    assert_no_overlap(
                        self, "previous dense dialog widget", previous, "dense dialog widget", widget_rect
                    )
                previous = widget_rect
            with isolated_gui_panel(g, panel):
                capture_panel_layout(self, g, "layout_dialog_dense_options", panel)
            self.assertTrue(panel.keyboardEvent(g.getGui(), SDL_KEYDOWN, ord(str(len(dense_options)))))
            return {"widgets": len(widgets)}

        run_blocking_panel_inspection(
            self,
            game,
            g,
            "CGameDialogPanel",
            lambda: g.getGuiHandler().showDialog(dense_dialog),
            inspect_dense_dialog,
            lambda panel: None,
        )
        self.assertFalse(gui_contains_class(g, "CGameDialogPanel"))

    def test_inventory_loot_trade_list_layouts(self):
        game, g, _, player = create_xvfb_gameplay_session(self)
        player.addItem("Sword")
        player.addItem("Scroll")
        duplicate = g.createObject("Scroll")
        duplicate.name = "inventoryDuplicateScroll"
        player.addItem(duplicate)
        quest_item = g.createObject("CItem")
        quest_item.name = "layoutQuestItem"
        quest_item.typeId = "layoutQuestItem"
        quest_item.animation = "images/items/scroll"
        quest_item.addTag(game.CTag.QUEST)
        player.addItem(quest_item)

        inventory = open_layout_panel(self, g, "inventoryPanel")
        try:
            root = assert_runtime_rect(self, "inventoryPanel", inventory, ROOT_800_600)
            inventory_list = find_list_view(inventory, "inventoryCollection")
            equipped_list = find_list_view(inventory, "equippedCollection")
            inventory_rect = assert_runtime_rect(self, "inventory list", inventory_list, (560, 240, 200, 600))
            equipped_rect = assert_runtime_rect(self, "equipped list", equipped_list, (1160, 240, 200, 600))
            assert_child_inside(self, "inventoryPanel", root, "inventory list", inventory_rect)
            assert_child_inside(self, "inventoryPanel", root, "equipped list", equipped_rect)
            assert_no_overlap(self, "inventory list", inventory_rect, "equipped list", equipped_rect)
            self.assertEqual((4, 2), list_runtime_grid(equipped_list, g.getGui()))

            click_first_list_object(
                self,
                inventory_list,
                g.getGui(),
                lambda item: item.getTypeId() == "Sword",
            )
            pump_event_loop(5)
            selected_after_inventory = get_panel_selection_box_counts_by_collection(inventory)
            self.assertEqual(1, selected_after_inventory.get("inventoryCollection", 0))
            activate_list_cell(equipped_list, g.getGui(), 0, 0)
            pump_event_loop(5)
            selected_after_equip = get_panel_selection_box_counts_by_collection(inventory)
            self.assertEqual(0, selected_after_equip.get("inventoryCollection", 0))
            click_first_list_object(
                self,
                inventory_list,
                g.getGui(),
                lambda item: not item.hasTag(game.CTag.QUEST),
                button=SDL_BUTTON_RIGHT,
            )
            pump_event_loop(5)
            selected_after_reset = get_panel_selection_box_counts_by_collection(inventory)
            self.assertEqual(0, selected_after_reset.get("inventoryCollection", 0))

            with isolated_gui_panel(g, inventory):
                capture_panel_layout(
                    self,
                    g,
                    "layout_inventory_panel",
                    inventory,
                    regions={"inventory": inventory_rect, "equipped": equipped_rect},
                )
        finally:
            inventory.close()
            pump_event_loop(3)

        loot_creature = g.createObject("GoblinThief")

        def run_loot_case(items, scenario, overflow=False):
            def inspect_loot(panel):
                root = assert_runtime_rect(self, "lootPanel", panel, ROOT_400_300)
                items_list = find_list_view(panel, "itemsCollection")
                list_rect = assert_runtime_rect(self, "loot items", items_list, ROOT_400_300)
                self.assertEqual((8, 6), list_runtime_grid(items_list, g.getGui()))
                first_page = list_visible_object_names(items_list, g.getGui())
                result = {"first": first_page}
                if overflow:
                    for graphic in items_list.getProxiedObjects(g.getGui(), 7, 5):
                        graphic.mouseEvent(g.getGui(), SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 1, 1)
                    second_page = list_visible_object_names(items_list, g.getGui())
                    self.assertNotEqual(first_page, second_page)
                    result["second"] = second_page
                assert_child_inside(self, "lootPanel", root, "loot list", list_rect)
                with isolated_gui_panel(g, panel):
                    capture_panel_layout(self, g, scenario, panel, regions={"items": list_rect})
                panel.keyboardEvent(g.getGui(), SDL_KEYDOWN, ord(" "))
                return result

            _, result = run_blocking_panel_inspection(
                self,
                game,
                g,
                "CGameLootPanel",
                lambda: g.getGuiHandler().showLoot(loot_creature, set(items)),
                inspect_loot,
                lambda panel: None,
            )
            self.assertFalse(gui_contains_class(g, "CGameLootPanel"))
            return result

        self.assertEqual([], run_loot_case([], "layout_loot_panel_empty")["first"])
        self.assertEqual(
            1, len(run_loot_case(make_unique_scroll_items(g, 1, "lootSingle"), "layout_loot_panel_single")["first"])
        )
        grouped_loot = [g.createObject("Scroll") for _ in range(3)]
        for index, item in enumerate(grouped_loot):
            item.name = f"lootGroupedScroll{index}"
        self.assertEqual(1, len(run_loot_case(grouped_loot, "layout_loot_panel_grouped")["first"]))
        exact_loot = make_unique_scroll_items(g, 48, "lootExact")
        self.assertEqual(48, len(run_loot_case(exact_loot, "layout_loot_panel_exact_capacity")["first"]))
        overflow_result = run_loot_case(
            make_unique_scroll_items(g, 49, "lootLayout"), "layout_loot_panel_overflow", True
        )
        self.assertIn("second", overflow_result)

        market = g.createObject("CMarket")
        market.sell = 50
        market.buy = 25
        market_item = g.createObject("Sword")
        market_item.name = "layoutMarketSword"
        market.setItems({market_item})
        player.addGold(1000)
        player.addItem("Sword")
        trade = open_layout_panel(self, g, "tradePanel")
        trade.setMarket(market)
        pump_event_loop(3)
        try:
            root = assert_runtime_rect(self, "tradePanel", trade, ROOT_800_600)
            player_list = find_list_view(trade, "inventoryCollection")
            market_list = find_list_view(trade, "marketCollection")
            player_rect = assert_runtime_rect(self, "trade player list", player_list, (560, 240, 200, 600))
            market_rect = assert_runtime_rect(self, "trade market list", market_list, (1160, 240, 200, 600))
            sell_cost_rect = (760, 240, 200, 200)
            buy_cost_rect = (960, 240, 200, 200)
            sell_button_rect = (760, 740, 200, 100)
            buy_button_rect = (960, 740, 200, 100)
            for label, rect in (
                ("player list", player_rect),
                ("market list", market_rect),
                ("sell cost", sell_cost_rect),
                ("buy cost", buy_cost_rect),
                ("sell button", sell_button_rect),
                ("buy button", buy_button_rect),
            ):
                assert_child_inside(self, "tradePanel", root, label, rect)
            assert_no_overlap(self, "player list", player_rect, "market list", market_rect)
            assert_no_overlap(self, "sell cost", sell_cost_rect, "sell button", sell_button_rect)
            assert_no_overlap(self, "buy cost", buy_cost_rect, "buy button", buy_button_rect)
            click_first_list_object(self, player_list, g.getGui(), lambda item: not item.hasTag(game.CTag.QUEST))
            click_first_list_object(self, market_list, g.getGui())
            pump_event_loop(5)
            self.assertGreater(trade.getTotalSellCost(), 0)
            self.assertGreater(trade.getTotalBuyCost(), 0)
            selected_trade = get_panel_selection_box_counts_by_collection(trade)
            self.assertEqual(1, selected_trade.get("inventoryCollection", 0))
            self.assertEqual(1, selected_trade.get("marketCollection", 0))
            buttons = {button.text: button for button in find_descendants_by_type(trade, "CButton")}
            self.assertEqual(sell_button_rect, resolved_rect(buttons["SELL"]))
            self.assertEqual(buy_button_rect, resolved_rect(buttons["BUY"]))
            queue_question_answer(game, g, 1)
            activate_widget(buttons["SELL"], g.getGui())
            pump_event_loop(5)
            self.assertFalse(gui_contains_class(g, "CGameQuestionPanel"))
            self.assertTrue(gui_has_child_object(g, trade))
            queue_question_answer(game, g, 1)
            activate_widget(buttons["BUY"], g.getGui())
            pump_event_loop(5)
            self.assertFalse(gui_contains_class(g, "CGameQuestionPanel"))
            trade.mouseEvent(g.getGui(), SDL_MOUSEBUTTONDOWN, SDL_BUTTON_RIGHT, 1, 1)
            pump_event_loop(5)
            self.assertEqual(0, trade.getTotalSellCost())
            self.assertEqual(0, trade.getTotalBuyCost())
            with isolated_gui_panel(g, trade):
                summary = capture_panel_layout(
                    self,
                    g,
                    "layout_trade_panel",
                    trade,
                    regions={
                        "player": player_rect,
                        "market": market_rect,
                        "sellCost": sell_cost_rect,
                        "buyCost": buy_cost_rect,
                        "sellButton": sell_button_rect,
                        "buyButton": buy_button_rect,
                    },
                )
            for region in ("player", "market", "sellCost", "buyCost", "sellButton", "buyButton"):
                assert_region_has_pixels(self, summary, region)
        finally:
            trade.close()
            pump_event_loop(3)

    def test_fight_panel_and_nested_views_layout(self):
        game, g, game_map, player = create_xvfb_gameplay_session(self)
        player.addItem("Sword")
        quest_item = g.createObject("CItem")
        quest_item.name = "fightLayoutQuestItem"
        quest_item.typeId = "fightLayoutQuestItem"
        quest_item.animation = "images/items/scroll"
        quest_item.addTag(game.CTag.QUEST)
        player.addItem(quest_item)
        enemies = []
        for index in range(6):
            enemy = g.createObject("GoblinThief")
            enemy.name = f"layoutEnemy{index}"
            enemy.setHp(max(1, enemy.getHpMax() - index))
            enemies.append(enemy)
        enemies[4].setEffects(
            {g.createObject("Stun"), g.createObject("BarrierEffect"), g.createObject("BloodlashEffect")}
        )
        enemies[5].setEffects(
            {
                g.createObject("Stun"),
                g.createObject("BarrierEffect"),
                g.createObject("BloodlashEffect"),
                g.createObject("LethalPoisonEffect"),
                g.createObject("MutilationEffect"),
            }
        )
        game_map.setStringProperty("combatStatus", "Initiative: player\nChoose a target and action.")

        fight = open_layout_panel(self, g, "fightPanel")
        fight.setEnemies(enemies)
        pump_event_loop(5)
        try:
            root = assert_runtime_rect(self, "fightPanel", fight, ROOT_800_600)
            direct_children = sorted(fight.getChildren(), key=lambda child: resolved_rect(child))
            cards = [child for child in direct_children if child.getType() == "CGameGraphicsObject"]
            self.assertEqual(2, len(cards))
            player_card = assert_runtime_rect(self, "player card", cards[0], (710, 340, 200, 300))
            enemy_card = assert_runtime_rect(self, "enemy card", cards[1], (1010, 340, 200, 300))
            enemy_selector = find_list_view(fight, "enemiesCollection")
            selector_rect = assert_runtime_rect(self, "enemy selector", enemy_selector, (800, 270, 320, 60))
            items_row = assert_runtime_rect(
                self, "items row", find_list_view(fight, "itemsCollection"), (560, 720, 800, 60)
            )
            actions_row = assert_runtime_rect(
                self,
                "actions row",
                find_list_view(fight, "interactionsCollection"),
                (560, 780, 800, 60),
            )
            status_widgets = [
                child for child in fight.getChildren() if child.getType() == "CWidget" and resolved_rect(child)[1] < 720
            ]
            self.assertEqual(1, len(status_widgets))
            status_rect = assert_runtime_rect(self, "combat status", status_widgets[0], (640, 642, 640, 78))
            for label, rect in (
                ("player card", player_card),
                ("enemy card", enemy_card),
                ("enemy selector", selector_rect),
                ("status", status_rect),
                ("items", items_row),
                ("actions", actions_row),
            ):
                assert_child_inside(self, "fightPanel", root, label, rect)
            assert_no_overlap(self, "player card", player_card, "enemy card", enemy_card)
            assert_no_overlap(self, "status", status_rect, "items", items_row)
            assert_no_overlap(self, "items", items_row, "actions", actions_row)

            creature_views = sorted(
                find_descendants_by_type(fight, "CCreatureView"), key=lambda child: resolved_rect(child)
            )
            stats_views = sorted(
                find_descendants_by_type(fight, "CStatsGraphicsObject"),
                key=lambda child: resolved_rect(child),
            )
            expected_nested = {
                (710, 340, 200, 200),
                (710, 540, 200, 100),
                (1010, 340, 200, 200),
                (1010, 540, 200, 100),
            }
            self.assertEqual(expected_nested, {resolved_rect(child) for child in creature_views + stats_views})
            for card_rect in (player_card, enemy_card):
                nested = [
                    child for child in creature_views + stats_views if rect_contains(card_rect, resolved_rect(child))
                ]
                self.assertEqual(2, len(nested))
                assert_no_overlap(
                    self, "nested upper", resolved_rect(nested[0]), "nested lower", resolved_rect(nested[1])
                )

            self.assertEqual(6, len(fight.enemiesCollection(g.getGui())))
            self.assertTrue(enemy_selector.getAllowOversize())
            self.assertEqual((4, 1), list_runtime_grid(enemy_selector, g.getGui()))
            for _ in range(4):
                self.assertTrue(activate_first_proxy_graphic(enemy_selector, g.getGui(), 3, 0))
                pump_event_loop(3)
            self.assertTrue(activate_first_proxy_graphic(enemy_selector, g.getGui(), 1, 0))
            pump_event_loop(5)
            self.assertEqual("layoutEnemy4", fight.getEnemy().getName())
            self.assertTrue(activate_first_proxy_graphic(enemy_selector, g.getGui(), 2, 0))
            pump_event_loop(5)
            self.assertEqual("layoutEnemy5", fight.getEnemy().getName())
            self.assertEqual(5, len(fight.getEnemy().getEffects()))

            enemy_effect_lists = [
                list_view
                for view in creature_views
                for list_view in find_descendants_by_type(view, "CListView")
                if list_view.getCollection() == "getEffects"
            ]
            self.assertEqual(2, len(enemy_effect_lists))
            for list_view in enemy_effect_lists:
                effect_rect = resolved_rect(list_view)
                assert_child_inside(self, "creatureView", resolved_rect(list_view.getParent()), "effects", effect_rect)
                self.assertEqual((1, 4), list_runtime_grid(list_view, g.getGui()))
                for column, row, _ in list_visible_object_cells(list_view, g.getGui()):
                    assert_child_inside(
                        self,
                        "effects",
                        effect_rect,
                        "effect cell",
                        list_cell_rect(list_view, column, row),
                    )

            fight.setEnemies(enemies[:3])
            pump_event_loop(5)
            self.assertEqual(3, len(fight.enemiesCollection(g.getGui())))
            self.assertEqual("layoutEnemy0", fight.getEnemy().getName())
            shrunk_enemy_names = set(list_visible_object_names(enemy_selector, g.getGui()))
            self.assertTrue(shrunk_enemy_names)
            self.assertTrue(shrunk_enemy_names.issubset({enemy.getName() for enemy in enemies[:3]}))

            with isolated_gui_panel(g, fight):
                capture_panel_layout(
                    self,
                    g,
                    "layout_fight_panel",
                    fight,
                    regions={
                        "selector": selector_rect,
                        "status": status_rect,
                        "items": items_row,
                        "actions": actions_row,
                    },
                )
        finally:
            fight.close()
            pump_event_loop(3)

    def test_all_list_views_capacity_paging_and_shrink(self):
        _, g, _, player = create_xvfb_gameplay_session(self)
        panels_to_collections = {
            "characterPanel": {"interactionsCollection"},
            "fightPanel": {"enemiesCollection", "itemsCollection", "interactionsCollection", "getEffects"},
            "inventoryPanel": {"inventoryCollection", "equippedCollection"},
            "lootPanel": {"itemsCollection"},
            "tradePanel": {"inventoryCollection", "marketCollection"},
        }

        inventory_items = make_unique_scroll_items(g, 7, "capacity")
        player.setItems(set(inventory_items))
        inventory = open_layout_panel(self, g, "inventoryPanel")
        try:
            inventory_list = find_list_view(inventory, "inventoryCollection")
            inventory_list.setXPrefferedSize(2)
            inventory_list.setYPrefferedSize(2)
            inventory_list.setAllowOversize(True)
            inventory_list.setGrouping(False)
            inventory_list.refreshAll()
            first_page = list_visible_object_names(inventory_list, g.getGui())
            for graphic in inventory_list.getProxiedObjects(g.getGui(), 1, 1):
                graphic.mouseEvent(g.getGui(), SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 1, 1)
            final_page = list_visible_object_names(inventory_list, g.getGui())
            self.assertNotEqual(first_page, final_page)

            player.setItems(set(inventory_items[:3]))
            inventory_list.refreshAll()
            shrunk_page = list_visible_object_names(inventory_list, g.getGui())
            self.assertTrue(shrunk_page)

            player.setItems(set(inventory_items[:2]))
            inventory_list.refreshAll()
            below_capacity = list_visible_object_names(inventory_list, g.getGui())
            self.assertEqual(2, len(below_capacity))

            duplicates = [g.createObject("Scroll") for _ in range(7)]
            for index, item in enumerate(duplicates):
                item.name = f"groupedCapacityScroll{index}"
            player.setItems(set(duplicates))
            inventory_list.setGrouping(True)
            inventory_list.refreshAll()
            grouped_names = list_visible_object_names(inventory_list, g.getGui())
            self.assertEqual(1, len(set(grouped_names)))
        finally:
            inventory.close()
            pump_event_loop(3)

        fight = open_layout_panel(self, g, "fightPanel")
        try:
            enemies = []
            for index in range(6):
                enemy = g.createObject("GoblinThief")
                enemy.name = f"matrixEnemy{index}"
                enemy.setHp(enemy.getHpMax())
                enemies.append(enemy)
            fight.setEnemies(enemies)
            found = {list_view.getCollection() for list_view in find_descendants_by_type(fight, "CListView")}
            self.assertTrue(panels_to_collections["fightPanel"].issubset(found))
        finally:
            fight.close()
            pump_event_loop(3)

        for panel_name in ("characterPanel", "inventoryPanel"):
            panel = open_layout_panel(self, g, panel_name)
            try:
                found = {list_view.getCollection() for list_view in find_descendants_by_type(panel, "CListView")}
                self.assertTrue(panels_to_collections[panel_name].issubset(found))
            finally:
                panel.close()
                pump_event_loop(3)

        trade = open_layout_panel(self, g, "tradePanel")
        try:
            market = g.createObject("CMarket")
            market.setItems({g.createObject("Scroll")})
            trade.setMarket(market)
            found = {list_view.getCollection() for list_view in find_descendants_by_type(trade, "CListView")}
            self.assertTrue(panels_to_collections["tradePanel"].issubset(found))
        finally:
            trade.close()
            pump_event_loop(3)

        loot_items = set(make_unique_scroll_items(g, 2, "matrixLoot"))
        result = {}

        def inspect_loot_matrix(panel):
            found = {list_view.getCollection() for list_view in find_descendants_by_type(panel, "CListView")}
            self.assertTrue(panels_to_collections["lootPanel"].issubset(found))
            result["loot"] = True
            panel.keyboardEvent(g.getGui(), SDL_KEYDOWN, ord(" "))
            return found

        run_blocking_panel_inspection(
            self,
            load_game_module(),
            g,
            "CGameLootPanel",
            lambda: g.getGuiHandler().showLoot(g.createObject("GoblinThief"), loot_items),
            inspect_loot_matrix,
            lambda panel: None,
        )
        self.assertTrue(result["loot"])

    def test_full_nouraajd_quest_walkthrough_ui(self):
        game, g, game_map, player = create_xvfb_gameplay_session(self, map_name="nouraajd")
        all_quest_ids = set(NOURAAJD_QUEST_DESCRIPTIONS)
        completed_quests = set()

        def quest_state(name):
            return game_map.getStringProperty(f"quest_state_{name}")

        def assert_active(quest_id):
            assert_player_quest_state(self, player, quest_id, completed=False)

        def assert_completed(quest_id):
            assert_player_quest_state(self, player, quest_id, completed=True)
            completed_quests.add(quest_id)

        self.assertEqual("nouraajd", game_map.mapName)
        start_events = [
            obj for obj in game_map.getObjects() if obj.getTypeId() == "StartEvent" or obj.getType() == "StartEvent"
        ]
        self.assertTrue(start_events, "The Nouraajd map should author StartEvent tiles.")
        start_coords = start_events[0].getCoords()
        run_blocking_gui_action(
            game,
            lambda: player.moveTo(start_coords.x, start_coords.y, start_coords.z),
            push_space_key,
        )
        self.assertGreaterEqual(player.countItems("letterFromRolf"), 1)
        self.assertEqual("awaiting_skull", quest_state("rolf"))
        assert_active("rolfQuest")
        assert_quest_log_hotkey_opens_panel(self, game, g, active=("rolfQuest",))
        capture_nouraajd_quest_log(
            self,
            g,
            "xvfb_nouraajd_quest_log_rolf_initial",
            active=("rolfQuest",),
        )

        run_blocking_gui_action(game, lambda: game_map.removeObjectByName("cave1"), push_space_key)
        run_blocking_gui_action(game, player.checkQuests, push_space_key)
        self.assertTrue(player.hasItem(lambda it: it.getName() == "skullOfRolf"))
        self.assertTrue(game_map.getBoolProperty("completed_rolf"))
        self.assertEqual("skull_recovered", quest_state("rolf"))
        self.assertEqual("awaiting_gooby", quest_state("main"))
        assert_completed("rolfQuest")
        assert_active("mainQuest")
        main_quest_text = capture_nouraajd_quest_log(
            self,
            g,
            "xvfb_nouraajd_quest_log_rolf_completed_main_active",
            active=("mainQuest",),
            completed=completed_quests,
        )
        self.assertIn("Reward: 200 gold from relieved townsfolk.", main_quest_text)

        gooby = find_runtime_object(game_map, "gooby1")
        gooby_gold = player.getGold()
        run_blocking_gui_action(game, lambda: game_map.removeObjectByName(gooby.getName()), push_space_key)
        run_blocking_gui_action(game, player.checkQuests, push_space_key)
        self.assertTrue(game_map.getBoolProperty("completed_gooby"))
        self.assertEqual("gooby_slain", quest_state("main"))
        self.assertEqual(gooby_gold + 200, player.getGold())
        self.assertTrue(game_map.getBoolProperty("GOOBY_REWARD_CLAIMED"))
        assert_completed("mainQuest")

        town_hall = g.createObject("townHallDialog")
        show_dialog_with_keyboard(self, game, g, town_hall, [2])
        run_blocking_gui_action(game, town_hall.give_letter, push_space_key)
        self.assertEqual("letter_in_hand", quest_state("beren_chain"))
        self.assertTrue(player.hasItem(lambda it: it.getName() == "letterToBeren"))
        assert_active("deliverLetterQuest")
        capture_nouraajd_quest_log(
            self,
            g,
            "xvfb_nouraajd_quest_log_deliver_letter_active",
            active=("deliverLetterQuest",),
            completed=completed_quests,
        )

        beren = g.createObject("berenDialog")
        show_dialog_with_keyboard(self, game, g, beren, [2])
        run_blocking_gui_action(game, beren.deliver_letter, push_space_key)
        player.checkQuests()
        pump_event_loop(5)
        self.assertEqual("letter_delivered", quest_state("beren_chain"))
        self.assertFalse(player.hasItem(lambda it: it.getName() == "letterToBeren"))
        self.assertTrue(player.getBoolProperty("CAN_CRAFT_SCROLLS"))
        assert_completed("deliverLetterQuest")
        assert_active("retrieveRelicQuest")

        run_blocking_gui_action(game, lambda: game_map.removeObjectByName("catacombs"), push_space_key)
        self.assertEqual("relic_obtained", quest_state("beren_chain"))
        self.assertTrue(player.hasItem(lambda it: it.getName() == "holyRelic"))
        show_dialog_with_keyboard(self, game, g, beren, [2])
        run_blocking_gui_action(game, beren.return_relic, push_space_key)
        player.checkQuests()
        pump_event_loop(5)
        self.assertEqual("relic_returned_waiting_kill", quest_state("beren_chain"))
        self.assertFalse(player.hasItem(lambda it: it.getName() == "holyRelic"))
        self.assertTrue(player.getBoolProperty("CAN_BREW_GREATER_POTIONS"))
        assert_completed("retrieveRelicQuest")
        assert_active("cleanseCaveQuest")
        capture_nouraajd_quest_log(
            self,
            g,
            "xvfb_nouraajd_quest_log_beren_cleanse_active",
            active=("cleanseCaveQuest",),
            completed=completed_quests,
        )

        show_dialog_with_keyboard(self, game, g, g.createObject("dialog"), [1, 2, 1, 1])
        self.assertEqual("active", quest_state("octobogz_contract"))
        assert_active("octoBogzQuest")

        octobogz_gold = player.getGold()
        octobogz_shadow_blades = player.countItems("ShadowBlade")
        run_blocking_gui_action(game, lambda: game_map.removeObjectByName("cave2"), push_space_key)
        run_blocking_gui_action(game, player.checkQuests, push_space_key)
        self.assertEqual("ready_to_report", quest_state("beren_chain"))
        self.assertEqual("completed", quest_state("octobogz_contract"))
        self.assertTrue(game_map.getBoolProperty("completed_octobogz"))
        self.assertTrue(game_map.getBoolProperty("OCTOBOGZ_CLEARED"))
        self.assertEqual(octobogz_gold + 1000, player.getGold())
        self.assertEqual(octobogz_shadow_blades + 1, player.countItems("ShadowBlade"))
        assert_completed("octoBogzQuest")

        show_dialog_with_keyboard(self, game, g, g.createObject("tavernDialog1"), [1, 1, 2, 3])
        self.assertTrue(game_map.getBoolProperty("ASKED_ABOUT_GIRL"))
        show_dialog_with_keyboard(self, game, g, g.createObject("tavernDialog2"), [1, 2, 2, 2, 1])
        self.assertEqual("met_victor", quest_state("victor"))
        self.assertTrue(game_map.getBoolProperty("TALKED_TO_VICTOR"))
        assert_active("victorQuest")
        show_dialog_with_keyboard(self, game, g, g.createObject("townHallDialog"), [1, 1, "space"])
        leader = find_runtime_object(game_map, "cultLeaderQuest")
        cultists = [obj for obj in game_map.getObjects() if obj.getName() and obj.getName().startswith("victorCultist")]
        self.assertEqual("encounter_active", quest_state("victor"))
        self.assertTrue(game_map.getBoolProperty("VICTOR_COURTYARD_FOUND"))
        self.assertTrue(game_map.getBoolProperty("VICTOR_CULTISTS_SPAWNED"))
        self.assertTrue(cultists)
        victor_text = capture_nouraajd_quest_log(
            self,
            g,
            "xvfb_nouraajd_quest_log_victor_encounter_active",
            active=("cleanseCaveQuest", "victorQuest"),
            completed=completed_quests,
        )
        self.assertIn("Objective: Defeat the cultists in the courtyard", victor_text)

        captured_reward_ui = {"dialogs": [], "trades": []}
        heal_amounts = []
        original_show_dialog = game.CGuiHandler.showDialog
        original_show_trade = game.CGuiHandler.showTrade
        original_heal_proc = game.CPlayer.healProc
        victor_gold = player.getGold()
        try:

            def capture_show_dialog(self, dialog):
                captured_reward_ui["dialogs"].append(dialog.getTypeId())
                queue_sdl_inputs(game, lambda: push_digit_key(1))
                return original_show_dialog(self, dialog)

            def capture_show_trade(self, market):
                captured_reward_ui["trades"].append(market.getTypeId())
                queue_sdl_inputs(game, push_space_key)
                return original_show_trade(self, market)

            def capture_heal_proc(self, amount):
                heal_amounts.append(amount)
                return original_heal_proc(self, amount)

            game.CGuiHandler.showDialog = capture_show_dialog
            game.CGuiHandler.showTrade = capture_show_trade
            game.CPlayer.healProc = capture_heal_proc
            game_map.removeObjectByName(leader.getName())
            pump_event_loop(5)
        finally:
            game.CGuiHandler.showDialog = original_show_dialog
            game.CGuiHandler.showTrade = original_show_trade
            game.CPlayer.healProc = original_heal_proc

        player.checkQuests()
        pump_event_loop(5)
        self.assertEqual("good_end", quest_state("victor"))
        self.assertEqual(victor_gold + 500, player.getGold())
        self.assertEqual([100], heal_amounts)
        self.assertTrue(game_map.getBoolProperty("VICTOR_GOOD_END"))
        self.assertTrue(game_map.getBoolProperty("VICTOR_REWARD_CLAIMED"))
        self.assertIn("victorRewardDialog", captured_reward_ui["dialogs"])
        self.assertIn("victorMarket", captured_reward_ui["trades"])
        self.assertFalse(
            any(
                obj.getName() and (obj.getName() == "cultLeaderQuest" or obj.getName().startswith("victorCultist"))
                for obj in game_map.getObjects()
            )
        )
        assert_completed("victorQuest")

        show_dialog_with_keyboard(self, game, g, g.createObject("questDialog"), [1, 1, 1])
        self.assertEqual("active", quest_state("amulet"))
        self.assertIsNotNone(game_map.getObjectByName("amuletGoblin"))
        assert_active("amuletQuest")
        capture_nouraajd_quest_log(
            self,
            g,
            "xvfb_nouraajd_quest_log_amulet_active",
            active=("cleanseCaveQuest", "amuletQuest"),
            completed=completed_quests,
        )

        amulet_gold = player.getGold()
        player.addItem("preciousAmulet")
        show_dialog_with_keyboard(self, game, g, g.createObject("questReturnDialog"), [1, "space"])
        player.checkQuests()
        pump_event_loop(5)
        self.assertEqual("returned", quest_state("amulet"))
        self.assertEqual(amulet_gold + 50, player.getGold())
        self.assertFalse(player.hasItem(lambda it: it.getName() == "preciousAmulet"))
        self.assertIsNone(game_map.getObjectByName("amuletGoblin"))
        self.assertIsNone(game_map.getObjectByName("oldWoman"))
        assert_completed("amuletQuest")
        capture_nouraajd_quest_log(
            self,
            g,
            "xvfb_nouraajd_quest_log_amulet_completed",
            active=("cleanseCaveQuest",),
            completed=completed_quests,
        )

        transitions = []
        original_change_map = game.CGame.changeMap
        try:

            def capture_change_map(self, map_name):
                transitions.append(map_name)

            game.CGame.changeMap = capture_change_map
            show_dialog_with_keyboard(self, game, g, beren, [2])
            run_blocking_gui_action(game, beren.finish_cleanse, push_space_key)
        finally:
            game.CGame.changeMap = original_change_map

        player.checkQuests()
        pump_event_loop(5)
        self.assertEqual(["ritual"], transitions)
        self.assertEqual("purged", quest_state("beren_chain"))
        self.assertTrue(game_map.getBoolProperty("CAVE_PURGED"))
        assert_completed("cleanseCaveQuest")
        journal_quest_ids = {player_quest_id(quest) for quest in player.getQuests()}
        journal_quest_ids.update(player_quest_id(quest) for quest in player.getCompletedQuests())
        self.assertTrue(all_quest_ids.issubset(journal_quest_ids))
        capture_nouraajd_quest_log(
            self,
            g,
            "xvfb_nouraajd_quest_log_all_quests_completed",
            completed=all_quest_ids,
        )

        self.assertEqual("nouraajd", g.getMap().mapName)

    def test_sidebar_mouse_opens_inventory_until_hotkey_closes_it(self):
        game, g, _, _ = create_xvfb_gameplay_session(self)

        push_sdl_mouse_click(1820, 25)
        observed = queue_panel_observer(game, g, "CGameInventoryPanel")
        push_sdl_key_event(ord("i"), 0, SDL_KEYDOWN)
        push_sdl_key_event(ord("i"), 0, SDL_KEYUP)
        pump_event_loop(5)

        self.assertTrue(observed["open"])
        self.assertFalse(gui_contains_class(g, "CGameInventoryPanel"))

    def test_save_hotkey_writes_loadable_map(self):
        _, g, game_map, _ = create_xvfb_gameplay_session(self)
        game = load_game_module()
        marker = f"xvfb-{os.getpid()}-{time.monotonic_ns()}"
        original_description = game_map.description
        game_map.description = marker

        save_name = game_map.mapName
        save_path = Path.cwd() / "save" / f"{save_name}.json"
        backup_path = save_backup_path(save_name)
        existing_save = save_path.read_bytes() if save_path.exists() else None
        existing_backup = backup_path.read_bytes() if backup_path.exists() and backup_path.is_file() else None

        def saved_marker_matches():
            if not save_path.exists():
                return False
            try:
                saved_json = json.loads(save_path.read_text())
            except json.JSONDecodeError:
                return False
            return marker == save_snapshot(saved_json).get("properties", {}).get("description")

        try:
            save_path.unlink(missing_ok=True)
            push_sdl_key_event(ord("s"), 0, SDL_KEYDOWN)
            push_sdl_key_event(ord("s"), 0, SDL_KEYUP)
            self.assertTrue(pump_event_loop_until(saved_marker_matches, timeout=1.0))
            saved_json = json.loads(save_path.read_text())
            snapshot = assert_save_envelope(self, saved_json, save_name)
            self.assertEqual(marker, snapshot.get("properties", {}).get("description"))

            loaded = game.CGameLoader.loadGame()
            game.CGameLoader.loadSavedGame(loaded, save_name)
            self.assertEqual(marker, loaded.getMap().description)
        finally:
            game_map.description = original_description
            if existing_save is None:
                save_path.unlink(missing_ok=True)
            else:
                save_path.parent.mkdir(exist_ok=True)
                save_path.write_bytes(existing_save)
            if existing_backup is None:
                backup_path.unlink(missing_ok=True)
            else:
                backup_path.write_bytes(existing_backup)


class PlayBootstrapTest(unittest.TestCase):
    def assertSamePath(self, expected, actual):
        self.assertTrue(os.path.samefile(expected, actual), f"{Path(expected)} != {Path(actual)}")

    def assertPathIn(self, expected, paths):
        for path in paths:
            if path and Path(path).exists() and os.path.samefile(expected, path):
                return
        self.fail(f"{Path(expected)} not found in path list")

    def _load_play_namespace(self, script_path=None):
        script_path = script_path or (REPO_ROOT / "play.py")
        module = ast.parse((REPO_ROOT / "play.py").read_text())
        isolated_module = ast.Module(
            body=[node for node in module.body if isinstance(node, ast.FunctionDef)],
            type_ignores=[],
        )
        ast.fix_missing_locations(isolated_module)
        namespace = {"os": os, "Path": Path, "sys": sys, "__file__": str(script_path)}
        exec(compile(isolated_module, str(REPO_ROOT / "play.py"), "exec"), namespace)
        return namespace

    def _load_play_function(self, function_name):
        return self._load_play_namespace()[function_name]

    def test_ensure_workdir_switches_to_trusted_dir_even_when_cwd_has_config(self):
        ensure_workdir = self._load_play_function("_ensure_workdir")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            attacker_cwd = tmp / "attacker"
            trusted_dir = tmp / "trusted-build"
            attacker_cwd.mkdir()
            trusted_dir.mkdir()
            (attacker_cwd / "config").mkdir()
            (attacker_cwd / "plugins").mkdir()

            original_cwd = Path.cwd()
            try:
                os.chdir(attacker_cwd)
                ensure_workdir(trusted_dir)
                self.assertSamePath(trusted_dir, Path.cwd())
            finally:
                os.chdir(original_cwd)

    def test_bootstrap_uses_packaged_resource_root_without_res_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir) / "package"
            for resource_dir in ("config", "maps", "plugins"):
                (package_root / resource_dir).mkdir(parents=True)

            namespace = self._load_play_namespace(package_root / "play.py")
            original_cwd = Path.cwd()
            original_sys_path = list(sys.path)
            try:
                namespace["_bootstrap"]()
                self.assertSamePath(package_root, Path.cwd())
                self.assertSamePath(package_root, sys.path[0])
            finally:
                os.chdir(original_cwd)
                sys.path[:] = original_sys_path

    def test_bootstrap_uses_build_dir_for_source_tree_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir) / "source"
            build_root = source_root / "cmake-build-release"
            resource_root = source_root / "res"
            build_root.mkdir(parents=True)
            for resource_dir in ("config", "maps", "plugins"):
                (resource_root / resource_dir).mkdir(parents=True)

            namespace = self._load_play_namespace(source_root / "play.py")
            original_cwd = Path.cwd()
            original_sys_path = list(sys.path)
            try:
                namespace["_bootstrap"]()
                self.assertSamePath(build_root, Path.cwd())
                self.assertPathIn(build_root, sys.path)
                self.assertPathIn(resource_root, sys.path)
            finally:
                os.chdir(original_cwd)
                sys.path[:] = original_sys_path


class CoverageReportTest(unittest.TestCase):
    def _load_coverage_report_module(self):
        module_path = REPO_ROOT / "scripts" / "coverage_report.py"
        spec = importlib.util.spec_from_file_location("coverage_report_for_test", module_path)
        module = importlib.util.module_from_spec(spec)
        self.assertIsNotNone(spec.loader)
        spec.loader.exec_module(module)
        return module

    def test_coverage_report_counts_all_instrumented_lines(self):
        coverage_report = self._load_coverage_report_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "src" / "sample.cpp"
            source.parent.mkdir()
            source.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

            merged = {source.resolve(): {1: 1, 2: 0, 3: 0, 4: 1}}
            summary, covered, total, percentage = coverage_report.summarize(root, merged)

            self.assertEqual((covered, total, percentage), (2, 4, 50.0))
            self.assertEqual(summary[0]["missing"], [2, 3])
            self.assertNotIn("excluded", summary[0])
            self.assertFalse(hasattr(coverage_report, "load_line_exclusions"))

    def test_coverage_report_rejects_line_exclusion_flags(self):
        coverage_report = self._load_coverage_report_module()

        base_argv = [
            "coverage_report.py",
            "--root",
            ".",
            "--build-dir",
            "cmake-build-coverage",
            "--report-dir",
            "coverage",
            "--min-line",
            "90",
        ]
        original_argv = sys.argv[:]
        try:
            for flag, extra in (("--line-exclusions", ["old_manifest.json"]), ("--audit-exclusions", [])):
                sys.argv = [*base_argv, flag, *extra]
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                    coverage_report.parse_args()
                self.assertEqual(2, raised.exception.code)
        finally:
            sys.argv = original_argv

    def test_coverage_include_prefixes_scope_reported_files(self):
        coverage_report = self._load_coverage_report_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "src" / "sample.cpp"
            test_source = root / "tests" / "sample_test.cpp"
            source.parent.mkdir()
            test_source.parent.mkdir()
            source.write_text("one\ntwo\n", encoding="utf-8")
            test_source.write_text("one\n", encoding="utf-8")

            reports = [
                {
                    "current_working_directory": str(root),
                    "files": [
                        {
                            "file": str(source),
                            "lines": [
                                {"line_number": 1, "count": 1},
                                {"line_number": 2, "count": 0},
                            ],
                        },
                        {
                            "file": str(test_source),
                            "lines": [
                                {"line_number": 1, "count": 0},
                            ],
                        },
                    ],
                }
            ]

            include_prefixes = coverage_report.load_include_prefixes(root, ["src"])
            merged = coverage_report.merge_line_counts(root, reports, include_prefixes)

            self.assertEqual(set(merged), {source.resolve()})
            summary, covered, total, percentage = coverage_report.summarize(root, merged)
            self.assertEqual((covered, total, percentage), (1, 2, 50.0))
            self.assertEqual(summary[0]["path"], Path("src/sample.cpp"))

    def test_coverage_paths_accept_noncanonical_root(self):
        coverage_report = self._load_coverage_report_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            real_root = Path(tmpdir) / "real"
            alias_root = Path(tmpdir) / "alias"
            real_root.mkdir()
            try:
                os.symlink(real_root, alias_root, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink root setup is unavailable: {exc}")

            source = alias_root / "src" / "sample.cpp"
            source.parent.mkdir()
            source.write_text("one\ntwo\n", encoding="utf-8")
            reports = [
                {
                    "current_working_directory": str(alias_root),
                    "files": [
                        {
                            "file": str(source),
                            "lines": [
                                {"line_number": 1, "count": 1},
                                {"line_number": 2, "count": 0},
                            ],
                        }
                    ],
                }
            ]

            include_prefixes = coverage_report.load_include_prefixes(alias_root, ["src"])
            merged = coverage_report.merge_line_counts(alias_root, reports, include_prefixes)
            summary, covered, total, percentage = coverage_report.summarize(alias_root, merged)

            self.assertEqual(set(merged), {source.resolve()})
            self.assertEqual((covered, total, percentage), (1, 2, 50.0))
            self.assertEqual(summary[0]["path"], Path("src/sample.cpp"))

            with self.assertRaisesRegex(ValueError, "glob"):
                coverage_report.load_include_prefixes(alias_root, ["src/*.cpp"])

    def test_coverage_include_prefixes_reject_globs(self):
        coverage_report = self._load_coverage_report_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with self.assertRaisesRegex(ValueError, "glob"):
                coverage_report.load_include_prefixes(root, ["src/*.cpp"])

    def test_coverage_report_gcov_timeout_reports_data_file(self):
        coverage_report = self._load_coverage_report_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gcda = root / "sample.gcda"
            gcda.write_bytes(b"")

            original_run = coverage_report.subprocess.run

            def fake_run(*args, **kwargs):
                self.assertEqual(7.5, kwargs.get("timeout"))
                raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

            coverage_report.subprocess.run = fake_run
            try:
                with self.assertRaisesRegex(RuntimeError, r"gcov timed out after 7.5s for .*sample\.gcda"):
                    coverage_report.collect_reports_for_gcda(gcda, root / "gcov-output", 7.5)
            finally:
                coverage_report.subprocess.run = original_run


class QuestStateHelperTest(unittest.TestCase):
    class FakeMap:
        def __init__(self):
            self.strings = {}
            self.bools = {}
            self.numerics = {}

        def getStringProperty(self, name):
            return self.strings.get(name, "")

        def setStringProperty(self, name, value):
            self.strings[name] = value

        def getBoolProperty(self, name):
            return self.bools.get(name, False)

        def setBoolProperty(self, name, value):
            self.bools[name] = bool(value)

        def getNumericProperty(self, name):
            return self.numerics.get(name, 0)

        def setNumericProperty(self, name, value):
            self.numerics[name] = value

    class DemoQuestStore(quest_state.QuestStateStore):
        QUEST_KEYS = {
            "alpha": "quest_state_alpha",
            "beta": "quest_state_beta",
        }
        QUEST_DEFAULTS = {
            "alpha": "pending",
            "beta": "locked",
        }
        QUEST_NUMERIC_DEFAULTS = {
            "demo_turn": -1,
        }
        LEGACY_BOOL_FLAGS = (
            quest_state.LegacyBoolFlag("alpha_done", "alpha", states=("done",)),
            quest_state.LegacyBoolFlag("beta_unlocked", "beta", excluded_states=("locked",)),
        )

    class FakeQuest:
        def __init__(self, name="", type_id=""):
            self._name = name
            self._type_id = type_id

        def getName(self):
            return self._name

        def getTypeId(self):
            return self._type_id

    class FakePlayer:
        def __init__(self):
            self.added_quests = []

        def addQuest(self, quest_name):
            self.added_quests.append(quest_name)

    class NativeQuestPlayer(FakePlayer):
        def __init__(self, quests):
            super().__init__()
            self._quests = quests

        def getQuests(self):
            return self._quests

    def test_quest_state_store_initializes_resets_and_syncs_legacy_flags(self):
        fake_map = self.FakeMap()
        fake_map.setStringProperty("quest_state_alpha", "done")
        fake_map.setNumericProperty("demo_turn", 42)
        store = self.DemoQuestStore(fake_map)

        self.assertTrue(store.initialize_defaults())
        self.assertEqual("done", fake_map.getStringProperty("quest_state_alpha"))
        self.assertEqual("locked", fake_map.getStringProperty("quest_state_beta"))
        self.assertEqual(-1, fake_map.getNumericProperty("demo_turn"))
        self.assertTrue(fake_map.getBoolProperty("alpha_done"))
        self.assertFalse(fake_map.getBoolProperty("beta_unlocked"))

        store.set_state("beta", "active")
        self.assertEqual("active", fake_map.getStringProperty("quest_state_beta"))
        self.assertTrue(fake_map.getBoolProperty("beta_unlocked"))

        store.reset_all()
        self.assertEqual("pending", fake_map.getStringProperty("quest_state_alpha"))
        self.assertEqual("locked", fake_map.getStringProperty("quest_state_beta"))
        self.assertEqual(-1, fake_map.getNumericProperty("demo_turn"))
        self.assertFalse(fake_map.getBoolProperty("alpha_done"))
        self.assertFalse(fake_map.getBoolProperty("beta_unlocked"))

    def test_ensure_quest_uses_type_ids_and_python_fallback_registry(self):
        native_player = self.NativeQuestPlayer([self.FakeQuest(name="displayName", type_id="existingQuest")])
        self.assertFalse(quest_state.ensure_quest(native_player, "existingQuest"))
        self.assertTrue(quest_state.ensure_quest(native_player, "newQuest"))
        self.assertEqual(["newQuest"], native_player.added_quests)

        fallback_player = self.FakePlayer()
        registry = quest_state.PlayerQuestRegistry()
        self.assertTrue(quest_state.ensure_quest(fallback_player, "fallbackQuest", registry=registry))
        self.assertFalse(quest_state.ensure_quest(fallback_player, "fallbackQuest", registry=registry))
        self.assertEqual(["fallbackQuest"], fallback_player.added_quests)
        self.assertEqual(["fallbackQuest"], [quest.getTypeId() for quest in registry._quests.values()])

        class PythonOnlyPlayer(self.FakePlayer):
            pass

        installed_registry = quest_state.PlayerQuestRegistry()
        installed_registry.install_on(PythonOnlyPlayer)
        installed_player = PythonOnlyPlayer()
        self.assertTrue(quest_state.ensure_quest(installed_player, "installedQuest", registry=installed_registry))
        self.assertFalse(quest_state.ensure_quest(installed_player, "installedQuest", registry=installed_registry))
        self.assertEqual(["installedQuest"], installed_player.added_quests)
        self.assertEqual(["installedQuest"], [quest.getTypeId() for quest in installed_player.getQuests()])

    def test_nouraajd_quest_state_uses_shared_helpers_and_stable_keys(self):
        script = (REPO_ROOT / "res/maps/nouraajd/script.py").read_text(encoding="utf-8")
        game_module = (REPO_ROOT / "res/game.py").read_text(encoding="utf-8")
        cmake = (REPO_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

        self.assertIn("from quest_state import QuestStateStore", game_module)
        self.assertIn("configure_file(quest_state.py quest_state.py)", cmake)
        self.assertIn("from game import QuestStateStore", script)
        self.assertIn("class QuestSystem(QuestStateStore)", script)
        self.assertNotIn("class _TrackedQuest", script)
        self.assertNotIn("_player_quests = {}", script)
        for quest_name in NOURAAJD_QUEST_STATE_NAMES:
            self.assertIn(f'"{quest_name}": "quest_state_{quest_name}"', script)


class TestRunnerSuiteTest(unittest.TestCase):
    def test_parse_runner_args_accepts_suite_names(self):
        jobs, suite_name, unittest_argv = parse_runner_args(
            ["test.py", "--suite", "gameplay", "--jobs=3", "GameTest.test_turns"]
        )

        self.assertEqual(3, jobs)
        self.assertEqual("gameplay", suite_name)
        self.assertEqual(["test.py", "GameTest.test_turns"], unittest_argv)

    def test_parse_runner_args_rejects_unknown_suite(self):
        with self.assertRaisesRegex(ValueError, "--suite must be one of"):
            parse_runner_args(["test.py", "--suite", "slow"])

    def test_suite_filters_keep_runtime_groups_distinct(self):
        sample_names = [
            "CoverageReportTest.test_coverage_paths_accept_noncanonical_root",
            "GameTest.test_map_walkthrough_nouraajd",
            "McpServerTest.test_stdio_map_walkthrough_test",
            "PanelLayoutManifestTest.test_panel_layout_manifest_matches_panels_json",
            XVFB_GAMEPLAY_PARENT_TEST,
            "XvfbGameplayProcessTest.test_screenshot_inventory_panel_has_rendered_pixels",
        ]

        self.assertEqual(
            [
                "CoverageReportTest.test_coverage_paths_accept_noncanonical_root",
                "PanelLayoutManifestTest.test_panel_layout_manifest_matches_panels_json",
            ],
            filter_test_names_by_suite(sample_names, "fast"),
        )
        self.assertEqual(
            ["GameTest.test_map_walkthrough_nouraajd", "McpServerTest.test_stdio_map_walkthrough_test"],
            filter_test_names_by_suite(sample_names, "gameplay"),
        )
        self.assertEqual(
            [
                "PanelLayoutManifestTest.test_panel_layout_manifest_matches_panels_json",
                XVFB_GAMEPLAY_PARENT_TEST,
            ],
            filter_test_names_by_suite(sample_names, "ui"),
        )
        self.assertEqual(
            [
                "CoverageReportTest.test_coverage_paths_accept_noncanonical_root",
                "GameTest.test_map_walkthrough_nouraajd",
                "PanelLayoutManifestTest.test_panel_layout_manifest_matches_panels_json",
                XVFB_GAMEPLAY_PARENT_TEST,
                "XvfbGameplayProcessTest.test_screenshot_inventory_panel_has_rendered_pixels",
            ],
            filter_test_names_by_suite(sample_names, "coverage-safe"),
        )

    def test_suite_commands_are_documented_and_used_by_automation(self):
        build_workflow = (REPO_ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
        release_workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        coverage_script = (REPO_ROOT / "scripts" / "run_coverage.sh").read_text(encoding="utf-8")
        testing_docs = (REPO_ROOT / "docs" / "testing.md").read_text(encoding="utf-8")

        self.assertIn("python3 test.py --suite fast", build_workflow)
        self.assertIn("python3 test.py --suite gameplay", build_workflow)
        self.assertIn("python3 test.py --suite ui", build_workflow)
        self.assertIn("python test.py --suite fast", build_workflow)
        self.assertIn("python test.py --suite gameplay", build_workflow)
        self.assertIn("python3 test.py --suite full", release_workflow)
        self.assertIn("python3 test.py --suite coverage-safe", coverage_script)
        self.assertIn("COVERAGE_PYTHON_TIMEOUT_SECONDS", coverage_script)
        self.assertIn("--gcov-timeout", coverage_script)

        for suite_name in VALID_TEST_SUITES:
            self.assertIn(f"--suite {suite_name}", testing_docs)


class McpServerTest(unittest.TestCase):
    MCP_WALKTHROUGHS = {
        "multilevel": "_mcp_walkthrough_multilevel",
        "nouraajd": "_mcp_walkthrough_nouraajd",
        "ritual": "_mcp_walkthrough_ritual",
        "siege": "_mcp_walkthrough_siege",
        "test": "_mcp_walkthrough_test",
    }

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

    def test_export_module_uses_security_allowlist(self):
        server = self.make_stub_server()
        module = types.ModuleType("game_stub")

        def top_level():
            return "top-level"

        def jsonify():
            return "{}"

        def set_logger_sink(sink_name, path=None):
            return sink_name, path

        class CGameLoader:
            @staticmethod
            def loadGame():
                return "game"

        class NativeLike:
            append = list.append

        class CPluginLoader:
            loadDynamicPlugin = staticmethod(len)

        class event_loop:
            instance = staticmethod(len)

        module.top_level = top_level
        module.jsonify = jsonify
        module.set_logger_sink = set_logger_sink
        module.CGameLoader = CGameLoader
        module.NativeLike = NativeLike
        module.CPluginLoader = CPluginLoader
        module.event_loop = event_loop

        server._export_module_callables(module, source="game")

        self.assertNotIn("top_level", server.exports)
        self.assertIn("jsonify", server.exports)
        self.assertIn("CGameLoader.loadGame", server.exports)
        self.assertIn("event_loop.instance", server.exports)
        self.assertNotIn("CPluginLoader.loadDynamicPlugin", server.exports)
        self.assertNotIn("NativeLike.append", server.exports)
        self.assertNotIn("set_logger_sink", server.exports)
        self.assertEqual(server.exports["CGameLoader.loadGame"].source, "game.CGameLoader")

    def test_export_module_includes_pybind_class_methods(self):
        server = mcp.EngineMcpServer(repo_root=REPO_ROOT, build_dir=build_dir)
        server.import_modules()
        server.inspect_and_export()

        self.assertIn("CGameLoader.loadGame", server.exports)
        self.assertIn("CGameLoader.loadGui", server.exports)
        self.assertIn("CGameLoader.startGameWithPlayer", server.exports)
        self.assertIn("event_loop.instance", server.exports)
        self.assertNotIn("CPluginLoader.loadDynamicPlugin", server.exports)
        self.assertNotIn("CGuiHandler.openPanel", server.exports)

        game_module = server.game_module
        g = game_module.CGameLoader.loadGame()
        game_module.CGameLoader.startGameWithPlayer(g, "test", DEFAULT_PLAYER)
        game_handle = server._serialize_result(g)
        scene_manager_handle = server._engine_handle_call(
            {
                "handle": game_handle["__handle__"],
                "method": "getSceneManager",
            }
        )
        self.assertFalse(scene_manager_handle["isError"])
        method_names = {
            method["name"] for method in scene_manager_handle["structuredContent"]["result"].get("pythonMethods", [])
        }
        self.assertTrue({"getTransitionStateName", "requestMapChange"}.issubset(method_names))

    def test_simulation_run_tool_executes_nouraajd_steps(self):
        server = mcp.EngineMcpServer(repo_root=REPO_ROOT, build_dir=build_dir)
        server.import_modules()

        result = server._call_tool(
            {
                "name": "simulation_run",
                "arguments": {
                    "map": "nouraajd",
                    "player_class": DEFAULT_PLAYER,
                    "steps": [
                        {"action": "interact_object", "object": "cave1", "name": "recover Rolf skull"},
                        {"action": "interact_object", "object": "gooby1", "name": "defeat Gooby"},
                        {"action": "interact_object", "object": "catacombs", "name": "recover relic"},
                        {"action": "interact_object", "object": "cave2", "name": "clear OctoBogz"},
                        {
                            "action": "read_map_state",
                            "include_objects": False,
                            "bool_flags": ["completed_rolf", "completed_gooby", "OCTOBOGZ_SLAIN"],
                        },
                        {"action": "assert_inventory_contains", "item": "skullOfRolf"},
                        {"action": "assert_inventory_contains", "item": "holyRelic"},
                    ],
                },
            },
            transport="stdio",
            session_id=None,
        )

        self.assertFalse(result["isError"], result["structuredContent"])
        structured = result["structuredContent"]
        self.assertEqual("nouraajd", structured["map"])
        inventory_names = {item["name"] for item in structured["inventory"]}
        self.assertTrue({"skullOfRolf", "holyRelic"}.issubset(inventory_names))
        self.assertTrue(
            all(
                step["result"].get("approach")
                and step["result"]["approach"]["target"] == step["result"]["object"]["coords"]
                and step["result"]["approach"]["distance"] <= 1
                for step in structured["steps"][:4]
            )
        )
        flag_step = structured["steps"][4]["result"]["boolFlags"]
        self.assertTrue(flag_step["completed_rolf"])
        self.assertTrue(flag_step["completed_gooby"])
        self.assertTrue(flag_step["OCTOBOGZ_SLAIN"])

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

        class CDialog:
            def invokeAction(self, action):
                return action

            def invokeCondition(self, condition):
                return condition

            def invoke(self, action):
                return action

        handle = server._serialize_result(CDialog())

        self.assertEqual(handle["__type__"], "CDialog")
        method_names = {method["name"] for method in handle["pythonMethods"]}
        self.assertEqual({"invokeAction", "invokeCondition"}, method_names)

    def test_engine_handle_call_rejects_private_methods(self):
        server = self.make_stub_server()

        class Dialog:
            def invoke(self, action):
                return action

        handle = server._serialize_result(Dialog())
        response = server._engine_handle_call(
            {
                "handle": handle["__handle__"],
                "method": "__getattribute__",
                "args": ["invoke"],
            }
        )

        self.assertTrue(response["isError"])
        self.assertEqual(
            response["structuredContent"], {"error": "Method `__getattribute__` is not exported for handle calls"}
        )

    def test_engine_handle_call_scopes_controller_access_to_players(self):
        server = self.make_stub_server()

        class CCreature:
            def getController(self):
                return "creature-controller"

        class CPlayer(CCreature):
            def getController(self):
                return "player-controller"

        creature_handle = server._serialize_result(CCreature())
        creature_response = server._engine_handle_call(
            {
                "handle": creature_handle["__handle__"],
                "method": "getController",
                "args": [],
            }
        )
        self.assertTrue(creature_response["isError"])
        self.assertEqual(
            creature_response["structuredContent"], {"error": "Method `getController` is not exported for handle calls"}
        )

        player_handle = server._serialize_result(CPlayer())
        player_response = server._engine_handle_call(
            {
                "handle": player_handle["__handle__"],
                "method": "getController",
                "args": [],
            }
        )
        self.assertFalse(player_response["isError"])
        self.assertEqual(player_response["structuredContent"]["result"], "player-controller")

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
        self.assertTrue({"engine_list", "engine_call", "engine_handle_call", "simulation_run"}.issubset(tool_names))

    def test_map_design_brief_summarizes_selected_map_hooks(self):
        server = self.make_stub_server()

        result = server._call_tool(
            {
                "name": "map_design_brief",
                "arguments": {
                    "map_name": "ritual",
                    "include_resource_catalog": True,
                    "max_objects": 5,
                    "max_ids_per_catalog": 5,
                },
            },
            transport="stdio",
            session_id=None,
        )

        self.assertFalse(result["isError"])
        brief = result["structuredContent"]
        map_names = {item["name"] for item in brief["maps"]}
        self.assertIn("ritual", map_names)
        self.assertEqual(brief["selectedMap"]["name"], "ritual")
        self.assertIn("destroyAnchorsQuest", brief["selectedMap"]["config"]["categories"]["quest"])
        trigger_targets = {trigger.get("target") for trigger in brief["selectedMap"]["script"]["triggers"]}
        self.assertIn("anchorNorth", trigger_targets)
        dialog_actions = {
            item["dialog"]: set(item["methods"]) for item in brief["selectedMap"]["script"]["dialogActions"]
        }
        self.assertIn("free_captive", dialog_actions["CapturedSoulDialog"])
        catalog_names = {item["name"] for item in brief["resourceCatalog"]}
        self.assertIn("items", catalog_names)

    def test_map_design_brief_uses_packaged_resource_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir) / "package"
            repo_root = Path(tmpdir) / "source"
            package_map = package_root / "maps" / "packaged"
            for resource_dir in ("config", "plugins"):
                (package_root / resource_dir).mkdir(parents=True)
            package_map.mkdir(parents=True)
            repo_root.mkdir()
            (package_root / "config" / "items.json").write_text(
                json.dumps({"packagedItem": {"class": "CItem"}}),
                encoding="utf-8",
            )
            (package_map / "map.json").write_text(json.dumps({"layers": []}), encoding="utf-8")
            (package_map / "config.json").write_text(
                json.dumps({"packagedQuest": {"class": "CQuest"}}), encoding="utf-8"
            )

            server = mcp.EngineMcpServer(repo_root=repo_root, build_dir=package_root)
            result = server._call_tool(
                {
                    "name": "map_design_brief",
                    "arguments": {
                        "map_name": "packaged",
                        "include_resource_catalog": True,
                    },
                },
                transport="stdio",
                session_id=None,
            )

            self.assertFalse(result["isError"])
            brief = result["structuredContent"]
            self.assertEqual(["packaged"], [item["name"] for item in brief["maps"]])
            self.assertEqual("packaged", brief["selectedMap"]["name"])
            catalog = {item["name"]: item for item in brief["resourceCatalog"]}
            self.assertEqual(["packagedItem"], catalog["items"]["ids"])

    def test_map_design_brief_rejects_path_traversal(self):
        server = self.make_stub_server()

        with self.assertRaisesRegex(mcp.ProtocolError, "direct child"):
            server._call_tool(
                {"name": "map_design_brief", "arguments": {"map_name": "../nouraajd"}},
                transport="stdio",
                session_id=None,
            )

    def test_http_notification_response_declares_empty_body(self):
        server = self.make_stub_server()
        httpd = mcp.EngineHttpServer(("127.0.0.1", 0), mcp.EngineHttpRequestHandler, server)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=5)
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        try:
            conn.request(
                "POST",
                "/mcp",
                body=json.dumps(
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
                ),
                headers=headers,
            )
            initialize_response = conn.getresponse()
            self.assertEqual(HTTPStatus.OK, initialize_response.status)
            session_id = initialize_response.getheader("MCP-Session-Id")
            self.assertTrue(session_id)
            initialize_response.read()

            notification_headers = dict(headers)
            notification_headers["MCP-Session-Id"] = session_id
            conn.request(
                "POST",
                "/mcp",
                body=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
                headers=notification_headers,
            )
            notification_response = conn.getresponse()

            self.assertEqual(HTTPStatus.ACCEPTED, notification_response.status)
            self.assertEqual("0", notification_response.getheader("Content-Length"))
            self.assertEqual(session_id, notification_response.getheader("MCP-Session-Id"))
            self.assertEqual(MCP_PROTOCOL_VERSION, notification_response.getheader("MCP-Protocol-Version"))
            self.assertEqual(b"", notification_response.read())
        finally:
            conn.close()
            httpd.shutdown()
            httpd.server_close()

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
            self.assertTrue({"engine_list", "engine_call", "engine_handle_call", "simulation_run"}.issubset(tool_names))

            game_handle = self._call_tool(proc, 3, "engine_call", {"name": "CGameLoader.loadGame"})["result"]
            self._call_tool(proc, 4, "engine_call", {"name": "CGameLoader.loadGui", "args": [game_handle]})
            self._call_tool(
                proc,
                5,
                "engine_call",
                {"name": "CGameLoader.startGameWithPlayer", "args": [game_handle, "test", DEFAULT_PLAYER]},
            )
            gui_handler_handle = self._call_tool(
                proc,
                6,
                "engine_handle_call",
                {"handle": game_handle["__handle__"], "method": "getGuiHandler"},
            )["result"]
            panel_handle = self._call_tool(
                proc,
                7,
                "engine_handle_call",
                {"handle": gui_handler_handle["__handle__"], "method": "openPanel", "args": ["inventoryPanel"]},
            )["result"]
            self.assertEqual(panel_handle["__type__"], "CGameInventoryPanel")
            gui_handle = self._call_tool(
                proc,
                8,
                "engine_handle_call",
                {"handle": game_handle["__handle__"], "method": "getGui"},
            )["result"]
            gui_tree = json.loads(
                self._call_tool(proc, 9, "engine_call", {"name": "jsonify", "args": [gui_handle]})["result"]
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

    def test_stdio_map_walkthroughs_cover_all_maps(self):
        discovered_maps = discover_maps()
        self.assertEqual(set(discovered_maps), set(self.MCP_WALKTHROUGHS))

        summary = {
            "discovered_maps": discovered_maps,
            "walkthroughs": self.MCP_WALKTHROUGHS,
        }
        TEST_OUTPUT_DIR.mkdir(exist_ok=True)
        (TEST_OUTPUT_DIR / "mcp_walkthroughs.json").write_text(json.dumps(summary, indent=2, sort_keys=True))

    def test_stdio_map_walkthrough_nouraajd(self):
        self._assert_mcp_walkthrough("nouraajd")

    def test_stdio_map_walkthrough_multilevel(self):
        self._assert_mcp_walkthrough("multilevel")

    def test_stdio_map_walkthrough_ritual(self):
        self._assert_mcp_walkthrough("ritual")

    def test_stdio_map_walkthrough_siege(self):
        self._assert_mcp_walkthrough("siege")

    def test_stdio_map_walkthrough_test(self):
        self._assert_mcp_walkthrough("test")

    def test_stdio_scene_manager_map_transition_walkthrough(self):
        proc = None
        try:
            proc = self._start_stdio_mcp_process()
            self._initialize_stdio_mcp(proc)
            session = {"proc": proc, "next_request_id": 3}

            game_handle, map_handle, player_handle = self._mcp_load_game_map_with_player(session, "test")
            manager_handle = self._mcp_handle_call(session, game_handle, "getSceneManager")
            self._mcp_handle_call(session, player_handle, "addItem", ["LesserLifePotion"])
            self._mcp_handle_call(session, player_handle, "setNumericProperty", ["gold", 45])
            self._mcp_handle_call(session, player_handle, "setStringProperty", ["sceneTransitionMarker", "mcp"])
            self._mcp_handle_call(session, map_handle, "setNumericProperty", ["turn", 6])

            self._mcp_handle_call(session, game_handle, "changeMap", ["ritual"])
            self.assertEqual(
                "TransitionPending", self._mcp_handle_call(session, manager_handle, "getTransitionStateName")
            )

            event_loop_handle = self._mcp_engine_call(session, "event_loop.instance")
            for _ in range(10):
                self._mcp_handle_call(session, event_loop_handle, "run")

            ritual_map_handle = self._mcp_handle_call(session, game_handle, "getMap")
            ritual_player_handle = self._mcp_handle_call(session, ritual_map_handle, "getPlayer")
            ritual_map = self._mcp_serialized_map(session, ritual_map_handle)
            ritual_player = self._serialized_player(ritual_map)
            ritual_properties = ritual_map.get("properties", {})
            player_properties = ritual_player.get("properties", {})

            self.assertEqual("Idle", self._mcp_handle_call(session, manager_handle, "getTransitionStateName"))
            self.assertEqual("ritual", ritual_properties.get("mapName"))
            self.assertEqual(6, ritual_properties.get("turn"))
            self.assertTrue(ritual_properties.get("ritual_initialized"))
            self.assertEqual("mcp", player_properties.get("sceneTransitionMarker"))
            self.assertEqual(45, self._mcp_handle_call(session, ritual_player_handle, "getNumericProperty", ["gold"]))
            self.assertGreaterEqual(
                self._mcp_handle_call(session, ritual_player_handle, "countItems", ["LesserLifePotion"]), 1
            )
            self.assertIn("ritualQuest", self._serialized_quest_ids(ritual_player))
            self.assertTrue(self._serialized_inventory_has(ritual_player, "LesserLifePotion"))
        finally:
            if proc is not None:
                self._shutdown_process(proc)

    def _assert_mcp_walkthrough(self, map_name):
        discovered_maps = discover_maps()
        self.assertIn(map_name, discovered_maps)
        self.assertIn(map_name, self.MCP_WALKTHROUGHS)
        success, log = self._run_mcp_walkthrough(map_name)
        self.assertTrue(success, json.dumps(log, sort_keys=True))

    def _run_mcp_walkthrough(self, map_name):
        proc = None
        success = False
        log = {}
        try:
            proc = self._start_stdio_mcp_process(map_name)
            self._initialize_stdio_mcp(proc)
            session = {"proc": proc, "next_request_id": 3}
            log = getattr(self, self.MCP_WALKTHROUGHS[map_name])(session)
            success = True
        except Exception as exc:
            log = {
                "map": map_name,
                "error": str(exc),
                "exception_type": type(exc).__name__,
                "traceback": traceback.format_exc(),
            }
        finally:
            if proc is not None:
                try:
                    self._shutdown_process(proc)
                except Exception as exc:
                    success = False
                    log.setdefault("map", map_name)
                    log["shutdown_error"] = str(exc)
                    log["shutdown_exception_type"] = type(exc).__name__
                    log["shutdown_traceback"] = traceback.format_exc()
            trace_path = getattr(proc, "_playtest_trace_path", None) if proc is not None else None
            if map_name == "nouraajd" and trace_path is not None and trace_path.exists():
                log["playtest_trace_path"] = str(trace_path)
                if not success:
                    log["playtest_trace_tail"] = trace_tail_from_file(trace_path)
            self._write_mcp_walkthrough_log(map_name, log)
        return success, log

    def _start_stdio_mcp_process(self, map_name=None):
        script = REPO_ROOT / "mcp.py"
        self.assertTrue(script.exists(), "MCP entry point is missing")
        trace_path = None
        env = None
        if map_name == "nouraajd":
            TEST_OUTPUT_DIR.mkdir(exist_ok=True)
            trace_path = TEST_OUTPUT_DIR / "mcp_walkthrough_nouraajd_trace.jsonl"
            trace_path.unlink(missing_ok=True)
            env = os.environ.copy()
            env["GAME_PLAYTEST_TRACE"] = "1"
            env["GAME_PLAYTEST_TRACE_FILE"] = str(trace_path)
        command = [
            sys.executable,
            str(script),
            "--stdio",
            "--repo-root",
            str(REPO_ROOT),
            "--build-dir",
            str(build_dir),
            "--native-log-sink",
            "disabled",
        ]
        if build_config:
            command.extend(["--build-config", build_config])
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            cwd=str(REPO_ROOT),
            env=env,
        )
        proc._playtest_trace_path = trace_path
        proc._mcp_stderr_chunks = []

        def drain_stderr():
            if proc.stderr is None:
                return
            for chunk in iter(lambda: proc.stderr.read(4096), b""):
                proc._mcp_stderr_chunks.append(chunk)

        proc._mcp_stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
        proc._mcp_stderr_thread.start()
        return proc

    def _initialize_stdio_mcp(self, proc):
        self._send_rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-walkthrough-test", "version": "1.0"},
                },
            },
        )
        initialize_response = self._read_rpc(proc)
        self.assertNotIn("error", initialize_response)
        self.assertEqual(initialize_response.get("id"), 1)
        self._send_rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        self._send_rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "logging/setLevel",
                "params": {"level": "critical"},
            },
        )
        log_level_response = self._read_rpc(proc)
        self.assertNotIn("error", log_level_response)
        self.assertEqual(log_level_response.get("id"), 2)

    def _write_mcp_walkthrough_log(self, map_name, log):
        TEST_OUTPUT_DIR.mkdir(exist_ok=True)
        path = TEST_OUTPUT_DIR / f"mcp_walkthrough_{map_name}.json"
        path.write_text(json.dumps(log, indent=2, sort_keys=True))

    def _mcp_tool(self, session, name, arguments, timeout=MCP_STDIO_TOOL_TIMEOUT_SECONDS):
        request_id = session["next_request_id"]
        session["next_request_id"] += 1
        return self._call_tool(session["proc"], request_id, name, arguments, timeout=timeout)

    def _mcp_engine_call(self, session, name, args=None, kwargs=None, timeout=MCP_STDIO_TOOL_TIMEOUT_SECONDS):
        arguments = {"name": name}
        if args is not None:
            arguments["args"] = args
        if kwargs is not None:
            arguments["kwargs"] = kwargs
        return self._mcp_tool(session, "engine_call", arguments, timeout=timeout)["result"]

    def _mcp_handle_call(self, session, handle, method, args=None, kwargs=None, timeout=MCP_STDIO_TOOL_TIMEOUT_SECONDS):
        handle_id = handle["__handle__"] if isinstance(handle, dict) else handle
        arguments = {"handle": handle_id, "method": method}
        if args is not None:
            arguments["args"] = args
        if kwargs is not None:
            arguments["kwargs"] = kwargs
        return self._mcp_tool(session, "engine_handle_call", arguments, timeout=timeout)["result"]

    def _mcp_load_game_map(self, session, map_name):
        game_handle = self._mcp_engine_call(session, "CGameLoader.loadGame")
        self._mcp_engine_call(session, "CGameLoader.startGame", [game_handle, map_name])
        map_handle = self._mcp_handle_call(session, game_handle, "getMap")
        return game_handle, map_handle

    def _mcp_load_game_map_with_player(self, session, map_name, player_name=DEFAULT_PLAYER):
        game_handle = self._mcp_engine_call(session, "CGameLoader.loadGame")
        self._mcp_engine_call(session, "CGameLoader.startGameWithPlayer", [game_handle, map_name, player_name])
        map_handle = self._mcp_handle_call(session, game_handle, "getMap")
        player_handle = self._mcp_handle_call(session, map_handle, "getPlayer")
        return game_handle, map_handle, player_handle

    def _mcp_get_object_by_name(self, session, map_handle, object_name):
        obj = self._mcp_handle_call(session, map_handle, "getObjectByName", [object_name])
        self.assertIsInstance(obj, dict, f"Expected object handle for {object_name}.")
        self.assertIn("__handle__", obj, f"Could not find runtime object {object_name}.")
        return obj

    def _mcp_serialized_map(self, session, map_handle):
        return json.loads(
            self._mcp_engine_call(session, "jsonify", [map_handle], timeout=MCP_STDIO_MAP_JSON_TIMEOUT_SECONDS)
        )

    def _mcp_advance_map(self, session, map_handle, turns):
        for _ in range(turns):
            self._mcp_handle_call(session, map_handle, "move")
        return self._mcp_handle_call(session, map_handle, "getTurn")

    def _mcp_pump_event_loop(self, session):
        loop = self._mcp_engine_call(session, "event_loop.instance")
        self._mcp_handle_call(session, loop, "run")

    def _serialized_objects(self, map_data):
        return map_data.get("properties", {}).get("objects") or []

    def _serialized_object_by_name(self, map_data, object_name):
        for obj in self._serialized_objects(map_data):
            if obj.get("properties", {}).get("name") == object_name:
                return obj
        raise AssertionError(f"Could not find serialized object {object_name}.")

    def _serialized_player(self, map_data):
        for obj in self._serialized_objects(map_data):
            properties = obj.get("properties", {})
            if obj.get("class") == "CPlayer" or properties.get("name") == "player":
                return obj
        raise AssertionError("Could not find serialized player object.")

    def _serialized_coords(self, obj):
        properties = obj.get("properties", {})
        return [properties.get("posx"), properties.get("posy"), properties.get("posz")]

    def _serialized_inventory_has(self, player_data, item_name):
        items = player_data.get("properties", {}).get("items") or []
        if isinstance(items, dict):
            items = items.values()
        for item in items:
            properties = item.get("properties", {}) if isinstance(item, dict) else {}
            if properties.get("name") == item_name or properties.get("typeId") == item_name:
                return True
        return False

    def _serialized_quest_ids(self, player_data):
        quest_ids = []
        for key in ("quests", "completedQuests"):
            for quest in player_data.get("properties", {}).get(key) or []:
                properties = quest.get("properties", {}) if isinstance(quest, dict) else {}
                quest_id = properties.get("typeId") or properties.get("name")
                if quest_id:
                    quest_ids.append(quest_id)
        return sorted(quest_ids)

    def _mcp_serialized_player_coords(self, session, map_handle):
        return self._serialized_coords(self._serialized_player(self._mcp_serialized_map(session, map_handle)))

    def _mcp_drive_player_to_target(self, session, map_handle, player_handle, target_handle, *, until, max_turns=24):
        controller = self._mcp_handle_call(session, player_handle, "getController")
        target_coords = self._mcp_handle_call(session, target_handle, "getCoords")
        self._mcp_handle_call(session, controller, "setTarget", [player_handle, target_coords])
        for _ in range(max_turns):
            player_coords = self._mcp_serialized_player_coords(session, map_handle)
            if until(player_coords):
                return player_coords
            self._mcp_handle_call(session, map_handle, "move")
            self._mcp_pump_event_loop(session)
            player_coords = self._mcp_serialized_player_coords(session, map_handle)
            if until(player_coords):
                return player_coords
        raise AssertionError(f"Player did not satisfy MCP movement predicate after {max_turns} turns.")

    def _mcp_walkthrough_test(self, session):
        _, map_handle, player_handle = self._mcp_load_game_map_with_player(session, "test")
        teleporter_1_def = find_map_object_definition("test", "teleporter1")
        teleporter_2_def = find_map_object_definition("test", "teleporter2")
        ground_hole_def = find_map_object_definition("test", "groundHole")

        teleporter = self._mcp_get_object_by_name(session, map_handle, "teleporter1")
        teleporter_coords = self._mcp_handle_call(session, teleporter, "getCoords")
        self._mcp_handle_call(session, player_handle, "setCoords", [teleporter_coords])
        after_teleport_map = self._mcp_serialized_map(session, map_handle)
        after_teleport = self._serialized_coords(self._serialized_player(after_teleport_map))

        ground_hole = self._mcp_get_object_by_name(session, map_handle, "groundHole")
        ground_hole_coords = self._mcp_handle_call(session, ground_hole, "getCoords")
        self._mcp_handle_call(session, player_handle, "setCoords", [ground_hole_coords])
        after_ground_hole_map = self._mcp_serialized_map(session, map_handle)
        after_ground_hole = self._serialized_coords(self._serialized_player(after_ground_hole_map))

        self.assertEqual([teleporter_2_def["x"] // 32, teleporter_2_def["y"] // 32, 0], after_teleport)
        self.assertEqual([ground_hole_def["x"] // 32, ground_hole_def["y"] // 32, -1], after_ground_hole)
        return {
            "map": "test",
            "teleporter_from": [teleporter_1_def["x"] // 32, teleporter_1_def["y"] // 32, 0],
            "teleporter_to": after_teleport,
            "ground_hole_exit": after_ground_hole,
        }

    def _mcp_walkthrough_multilevel(self, session):
        _, map_handle, player_handle = self._mcp_load_game_map_with_player(session, "multilevel")
        for name in (
            "stairsUp",
            "stairsDown",
            "level0ObjectBlocker",
            "level1ObjectBlocker",
            "multilevelUpperGoal",
            "multilevelLowerGoal",
        ):
            find_map_object_definition("multilevel", name)

        initial_map = self._mcp_serialized_map(session, map_handle)
        initial_player = self._serialized_player(initial_map)
        self.assertEqual([1, 1, 0], self._serialized_coords(initial_player))
        self.assertEqual(
            [4, 1, 0],
            self._serialized_coords(self._serialized_object_by_name(initial_map, "stairsUp")),
        )
        self.assertEqual(
            [4, 1, 1],
            self._serialized_coords(self._serialized_object_by_name(initial_map, "stairsDown")),
        )

        stairs_up = self._mcp_get_object_by_name(session, map_handle, "stairsUp")
        stairs_down = self._mcp_get_object_by_name(session, map_handle, "stairsDown")
        upper_goal = self._mcp_get_object_by_name(session, map_handle, "multilevelUpperGoal")
        lower_goal = self._mcp_get_object_by_name(session, map_handle, "multilevelLowerGoal")

        upper_landing = self._mcp_drive_player_to_target(
            session, map_handle, player_handle, stairs_up, until=lambda coords: coords == [4, 1, 1]
        )
        upper_goal_coords = self._mcp_drive_player_to_target(
            session, map_handle, player_handle, upper_goal, until=lambda coords: coords == [6, 4, 1]
        )
        lower_landing = self._mcp_drive_player_to_target(
            session, map_handle, player_handle, stairs_down, until=lambda coords: coords == [4, 1, 0]
        )
        lower_goal_coords = self._mcp_drive_player_to_target(
            session, map_handle, player_handle, lower_goal, until=lambda coords: coords == [6, 5, 0]
        )

        flags = {
            "used_stairs_up": self._mcp_handle_call(session, map_handle, "getBoolProperty", ["used_stairs_up"]),
            "used_stairs_down": self._mcp_handle_call(session, map_handle, "getBoolProperty", ["used_stairs_down"]),
            "visited_upper_goal": self._mcp_handle_call(session, map_handle, "getBoolProperty", ["visited_upper_goal"]),
            "visited_lower_goal": self._mcp_handle_call(session, map_handle, "getBoolProperty", ["visited_lower_goal"]),
        }
        for value in flags.values():
            self.assertTrue(value)

        return {
            "map": "multilevel",
            **flags,
            "lower_goal": lower_goal_coords,
            "lower_landing": lower_landing,
            "upper_goal": upper_goal_coords,
            "upper_landing": upper_landing,
        }

    def _mcp_walkthrough_nouraajd(self, session):
        _, map_handle, player_handle = self._mcp_load_game_map_with_player(session, "nouraajd")
        for name in ("cave1", "catacombs", "cave2"):
            find_map_object_definition("nouraajd", name)

        def quest_state(active_map, name):
            return self._mcp_handle_call(session, active_map, "getStringProperty", [f"quest_state_{name}"])

        def map_bool(active_map, name):
            return self._mcp_handle_call(session, active_map, "getBoolProperty", [name])

        self._mcp_handle_call(session, map_handle, "removeObjectByName", ["cave1"])
        self._mcp_handle_call(session, player_handle, "checkQuests")
        self.assertEqual("skull_recovered", quest_state(map_handle, "rolf"))
        self.assertEqual("awaiting_gooby", quest_state(map_handle, "main"))

        gooby = self._mcp_get_object_by_name(session, map_handle, "gooby1")
        gooby_name = self._mcp_handle_call(session, gooby, "getName")
        self._mcp_handle_call(session, map_handle, "removeObjectByName", [gooby_name])
        self._mcp_handle_call(session, player_handle, "checkQuests")
        self.assertEqual("gooby_slain", quest_state(map_handle, "main"))

        self._mcp_handle_call(session, map_handle, "removeObjectByName", ["catacombs"])
        self._mcp_handle_call(session, map_handle, "removeObjectByName", ["cave2"])
        self._mcp_handle_call(session, player_handle, "checkQuests")
        self.assertEqual("octobogz_slain_pending_letter", quest_state(map_handle, "beren_chain"))
        self.assertEqual("completed", quest_state(map_handle, "octobogz_contract"))

        flags = {
            "completed_rolf": map_bool(map_handle, "completed_rolf"),
            "completed_gooby": map_bool(map_handle, "completed_gooby"),
            "octobogz_slain": map_bool(map_handle, "OCTOBOGZ_SLAIN"),
            "completed_octobogz": map_bool(map_handle, "completed_octobogz"),
        }
        map_data = self._mcp_serialized_map(session, map_handle)
        player_data = self._serialized_player(map_data)
        has_skull = self._serialized_inventory_has(player_data, "skullOfRolf")
        has_relic = self._serialized_inventory_has(player_data, "holyRelic")

        self.assertTrue(flags["completed_rolf"])
        self.assertTrue(flags["completed_gooby"])
        self.assertTrue(flags["octobogz_slain"])
        self.assertTrue(flags["completed_octobogz"])
        self.assertTrue(has_skull)
        self.assertTrue(has_relic)
        return {
            "map": "nouraajd",
            **flags,
            "quest_states": {name: quest_state(map_handle, name) for name in NOURAAJD_QUEST_STATE_NAMES},
            "has_skull_of_rolf": has_skull,
            "has_holy_relic": has_relic,
            "quests": self._serialized_quest_ids(player_data),
        }

    def _mcp_walkthrough_ritual(self, session):
        _, map_handle = self._mcp_load_game_map(session, "ritual")
        for name in ("anchorNorth", "anchorCrypt", "anchorSanctum"):
            find_map_object_definition("ritual", name)

        self._mcp_handle_call(session, map_handle, "removeObjectByName", ["anchorNorth"])
        turn_after_countdown = self._mcp_advance_map(session, map_handle, 5)
        self._mcp_handle_call(session, map_handle, "removeObjectByName", ["anchorCrypt"])
        self._mcp_handle_call(session, map_handle, "removeObjectByName", ["anchorSanctum"])
        self._mcp_get_object_by_name(session, map_handle, "ritualLeader")
        self._mcp_advance_map(session, map_handle, 70)

        flags = {
            "ritual_started": self._mcp_handle_call(session, map_handle, "getBoolProperty", ["ritual_started"]),
            "anchors_destroyed": self._mcp_handle_call(session, map_handle, "getBoolProperty", ["anchors_destroyed"]),
            "leader_spawned": self._mcp_handle_call(session, map_handle, "getBoolProperty", ["leader_spawned"]),
            "captive_lost": self._mcp_handle_call(session, map_handle, "getBoolProperty", ["captive_lost"]),
            "bad_ending": self._mcp_handle_call(session, map_handle, "getBoolProperty", ["bad_ending"]),
            "ritual_finished": self._mcp_handle_call(session, map_handle, "getBoolProperty", ["ritual_finished"]),
        }
        for value in flags.values():
            self.assertTrue(value)
        return {
            "map": "ritual",
            **flags,
            "anchors_destroyed_count": self._mcp_handle_call(
                session, map_handle, "getNumericProperty", ["anchors_destroyed_count"]
            ),
            "countdown_after_turns": self._mcp_handle_call(
                session, map_handle, "getNumericProperty", ["ritual_countdown"]
            ),
            "turn_after_countdown": turn_after_countdown,
            "note": "MCP walkthrough covers the deterministic no-player ritual failure path.",
        }

    def _mcp_walkthrough_siege(self, session):
        _, map_handle, player_handle = self._mcp_load_game_map_with_player(session, "siege")
        spawn_point = self._mcp_get_object_by_name(session, map_handle, "spawnPoint1")
        spawn_coords = self._mcp_handle_call(session, spawn_point, "getCoords")
        self._mcp_handle_call(session, spawn_point, "setBoolProperty", ["enabled", True])
        self._mcp_handle_call(session, spawn_point, "setStringProperty", ["animation", "images/misc/open_door"])
        self._mcp_handle_call(session, map_handle, "replaceTile", ["SwampTile", spawn_coords])
        spawned_name = self._mcp_handle_call(session, map_handle, "addObjectByName", ["siegePritz", spawn_coords])

        map_data = self._mcp_serialized_map(session, map_handle)
        spawn_data = self._serialized_object_by_name(map_data, "spawnPoint1")
        siege_units = sorted(
            obj.get("properties", {}).get("name")
            for obj in self._serialized_objects(map_data)
            if obj.get("properties", {}).get("affiliation") == "siege"
        )
        wand_count = self._mcp_handle_call(session, player_handle, "countItems", ["magicWand"])
        player_data = self._serialized_player(map_data)

        self.assertTrue(spawn_data.get("properties", {}).get("enabled"))
        self.assertEqual("siegePritz", spawned_name)
        self.assertTrue(siege_units)
        self.assertGreaterEqual(wand_count, 1)
        return {
            "map": "siege",
            "enabled_gates": ["spawnPoint1"],
            "spawned_enemies": siege_units,
            "wands": wand_count,
            "quests": self._serialized_quest_ids(player_data),
        }

    def _send_rpc(self, proc, payload):
        if proc.stdin is None:
            self.fail("Process stdin not available")
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        proc.stdin.write(line.encode("utf-8"))
        proc.stdin.flush()

    def _call_tool(self, proc, request_id: int, name: str, arguments: dict, timeout=MCP_STDIO_TOOL_TIMEOUT_SECONDS):
        self._send_rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )
        response = self._read_rpc(proc, timeout=timeout)
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
            # Coverage-instrumented native teardown can finish several seconds after stdio closes.
            proc.wait(timeout=MCP_STDIO_SHUTDOWN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        stderr_chunks = getattr(proc, "_mcp_stderr_chunks", None)
        stderr_thread = getattr(proc, "_mcp_stderr_thread", None)
        if stderr_thread is not None:
            stderr_thread.join(timeout=1.0)
            stderr_output = b"".join(stderr_chunks or []).decode("utf-8", errors="ignore")
        else:
            stderr_output = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()
        if proc.returncode not in (0, None):
            self.fail(f"MCP server exited with {proc.returncode}: {stderr_output}")


def parse_runner_args(argv):
    jobs = None
    suite_name = "full"
    unittest_argv = [argv[0]]
    index = 1
    while index < len(argv):
        arg = argv[index]
        if arg == "--jobs":
            if index + 1 >= len(argv):
                raise ValueError("--jobs requires a positive integer argument")
            jobs = parse_positive_int(argv[index + 1], "--jobs")
            index += 2
            continue
        if arg.startswith("--jobs="):
            jobs = parse_positive_int(arg.split("=", 1)[1], "--jobs")
            index += 1
            continue
        if arg == "--suite":
            if index + 1 >= len(argv):
                raise ValueError(f"--suite requires one of: {', '.join(VALID_TEST_SUITES)}")
            suite_name = argv[index + 1]
            if suite_name not in VALID_TEST_SUITES:
                raise ValueError(f"--suite must be one of: {', '.join(VALID_TEST_SUITES)}")
            index += 2
            continue
        if arg.startswith("--suite="):
            suite_name = arg.split("=", 1)[1]
            if suite_name not in VALID_TEST_SUITES:
                raise ValueError(f"--suite must be one of: {', '.join(VALID_TEST_SUITES)}")
            index += 1
            continue
        unittest_argv.append(arg)
        index += 1
    return jobs, suite_name, unittest_argv


def selected_unittest_args(unittest_argv):
    return [arg for arg in unittest_argv[1:] if not arg.startswith("-")]


def test_name_matches_suite(test_name, suite_name):
    if suite_name == "coverage-safe":
        return test_name not in COVERAGE_SAFE_EXCLUDED_TEST_NAMES
    if suite_name == "full":
        return True
    if suite_name == "fast":
        return test_name in FAST_TEST_NAMES or test_name.startswith(FAST_TEST_PREFIXES)
    if suite_name == "gameplay":
        return test_name not in GAMEPLAY_EXCLUDED_TEST_NAMES and test_name.startswith(GAMEPLAY_TEST_PREFIXES)
    if suite_name == "ui":
        return test_name == XVFB_GAMEPLAY_PARENT_TEST or test_name.startswith("PanelLayoutManifestTest.")
    raise ValueError(f"--suite must be one of: {', '.join(VALID_TEST_SUITES)}")


def filter_test_names_by_suite(test_names, suite_name):
    return [test_name for test_name in test_names if test_name_matches_suite(test_name, suite_name)]


def load_test_timings(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    timings = {}
    if isinstance(data, dict):
        for test_name, duration in data.items():
            try:
                timings[test_name] = max(float(duration), 0.001)
            except (TypeError, ValueError):
                continue
    return timings


def write_test_timings(path, timings):
    if not timings:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_test_timings(path)
    existing.update({test_name: round(float(duration), 6) for test_name, duration in timings.items()})
    path.write_text(json.dumps(dict(sorted(existing.items())), indent=2, sort_keys=True), encoding="utf-8")


def test_duration_weight(test_name, timings):
    if test_name in timings:
        return timings[test_name]
    if test_name in DEFAULT_TEST_DURATIONS:
        return DEFAULT_TEST_DURATIONS[test_name]
    if test_name.startswith("McpServerTest.test_stdio_map_walkthrough_"):
        return 30.0
    if test_name.startswith("XvfbGameplayProcessTest."):
        return 10.0
    if "walkthrough" in test_name:
        return 8.0
    if test_name.startswith("McpServerTest."):
        return 6.0
    return 1.0


def is_serial_test_name(test_name):
    return test_name in SERIAL_TEST_NAMES or any(test_name.startswith(prefix) for prefix in SERIAL_TEST_PREFIXES)


def runner_jobs(cli_jobs, unittest_argv, suite_name="full"):
    if GAME_TEST_WORKER:
        return 1
    if cli_jobs is not None:
        return cli_jobs
    env_jobs = os.environ.get("GAME_TEST_JOBS")
    if env_jobs:
        return parse_positive_int(env_jobs, "GAME_TEST_JOBS")
    has_unittest_options = any(arg.startswith("-") for arg in unittest_argv[1:])
    if not has_unittest_options and (suite_name != "full" or not selected_unittest_args(unittest_argv)):
        return os.cpu_count() or 1
    return 1


def flatten_suite(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten_suite(test)
        else:
            yield test


def subprocess_test_name(test):
    test_id = test.id()
    for prefix in (f"{__name__}.", "__main__."):
        if test_id.startswith(prefix):
            return test_id[len(prefix) :]
    return test_id


def discover_unittest_test_names(unittest_argv):
    loader = unittest.defaultTestLoader
    selected = selected_unittest_args(unittest_argv)
    if selected:
        suite = loader.loadTestsFromNames(selected, module=sys.modules[__name__])
    else:
        suite = loader.loadTestsFromModule(sys.modules[__name__])

    tests = list(flatten_suite(suite))
    if any(test.__class__.__name__ == "_FailedTest" for test in tests):
        return None
    return [subprocess_test_name(test) for test in tests]


def shard_test_names(test_names, jobs, timings=None):
    groups = [[] for _ in range(min(jobs, len(test_names)))]
    group_weights = [0.0 for _ in groups]
    timings = timings or {}
    weighted_tests = sorted(
        ((test_duration_weight(test_name, timings), index, test_name) for index, test_name in enumerate(test_names)),
        key=lambda item: (-item[0], item[1]),
    )
    for weight, _, test_name in weighted_tests:
        group_index = min(range(len(groups)), key=lambda index: group_weights[index])
        groups[group_index].append(test_name)
        group_weights[group_index] += weight
    return groups


def test_group_timeout_seconds(test_names, timings=None):
    timings = timings or {}
    duration_hint = sum(test_duration_weight(test_name, timings) for test_name in test_names)
    multiplier = 8 if os.environ.get("GAME_COVERAGE_RUN") == "1" else 4
    return max(30, int(duration_hint * multiplier))


def run_test_subprocess(test_names, shard_name, extra_env=None):
    output_dir = TEST_OUTPUT_DIR / "workers" / shard_name
    timings_file = output_dir / "test-timings.json"
    env = os.environ.copy()
    env.update(
        {
            "GAME_TEST_WORKER": "1",
            "GAME_TEST_JOBS": "1",
            "GAME_TEST_OUTPUT_DIR": str(output_dir),
            "GAME_TEST_SHARD": shard_name,
            "GAME_TEST_TIMINGS_FILE": str(timings_file),
            "PYTHONUNBUFFERED": "1",
        }
    )
    if extra_env:
        env.update(extra_env)
    command = [sys.executable, str(REPO_ROOT / "test.py"), *test_names]
    print(f"[test shard {shard_name}] running {len(test_names)} test(s)", flush=True)
    return subprocess.Popen(command, cwd=REPO_ROOT, env=env, start_new_session=(os.name == "posix"))


def wait_test_subprocess(proc, shard_name, test_names, timeout_seconds):
    try:
        return proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            proc.kill()
        proc.wait()
        print(
            f"[test shard {shard_name}] timed out after {timeout_seconds}s while running {', '.join(test_names)}",
            file=sys.stderr,
            flush=True,
        )
        return 124


def run_sharded_tests(test_names, jobs, *, allow_xvfb_sidecar=False):
    sidecar_tests = []
    long_xvfb_tests = []
    if allow_xvfb_sidecar and jobs > 1 and XVFB_GAMEPLAY_PARENT_TEST in test_names:
        sidecar_tests = [XVFB_GAMEPLAY_PARENT_TEST]
        long_xvfb_tests = [XVFB_GAMEPLAY_PARENT_TEST]

    reserved_jobs = len(sidecar_tests)
    worker_jobs = max(1, jobs - reserved_jobs)
    serial_tests = [
        test_name for test_name in test_names if is_serial_test_name(test_name) and test_name not in sidecar_tests
    ]
    parallel_tests = [
        test_name for test_name in test_names if not is_serial_test_name(test_name) and test_name not in sidecar_tests
    ]
    timings = load_test_timings(TEST_TIMINGS_FILE)
    failures = []

    processes = []
    for sidecar_test in sidecar_tests:
        processes.append(
            (
                "xvfb",
                [sidecar_test],
                run_test_subprocess(
                    [sidecar_test],
                    "xvfb",
                    extra_env={"GAME_XVFB_SKIP_CHILD_TESTS": ",".join(sorted(XVFB_LONG_CHILD_TESTS))},
                ),
            )
        )

    if parallel_tests:
        for index, group in enumerate(shard_test_names(parallel_tests, worker_jobs, timings), start=1):
            processes.append((f"{index}", group, run_test_subprocess(group, f"{index}")))

    for shard_name, group, proc in processes:
        return_code = wait_test_subprocess(proc, shard_name, group, test_group_timeout_seconds(group, timings))
        if return_code != 0:
            failures.append((shard_name, return_code))

    if serial_tests:
        serial_proc = run_test_subprocess(serial_tests, "serial")
        return_code = wait_test_subprocess(
            serial_proc,
            "serial",
            serial_tests,
            test_group_timeout_seconds(serial_tests, timings),
        )
        if return_code != 0:
            failures.append(("serial", return_code))

    for long_xvfb_test in long_xvfb_tests:
        long_proc = run_test_subprocess(
            [long_xvfb_test],
            "xvfb-long",
            extra_env={"GAME_XVFB_ONLY_CHILD_TESTS": ",".join(sorted(XVFB_LONG_CHILD_TESTS))},
        )
        return_code = wait_test_subprocess(
            long_proc,
            "xvfb-long",
            [long_xvfb_test],
            test_group_timeout_seconds([long_xvfb_test], timings),
        )
        if return_code != 0:
            failures.append(("xvfb-long", return_code))

    if failures:
        for shard_name, return_code in failures:
            print(f"[test shard {shard_name}] failed with exit code {return_code}", file=sys.stderr, flush=True)
        return 1

    combined_timings = {}
    for timings_path in (TEST_OUTPUT_DIR / "workers").glob("*/test-timings.json"):
        combined_timings.update(load_test_timings(timings_path))
    write_test_timings(TEST_TIMINGS_FILE, combined_timings)
    return 0


def main():
    try:
        cli_jobs, suite_name, unittest_argv = parse_runner_args(sys.argv)
        jobs = runner_jobs(cli_jobs, unittest_argv, suite_name)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)

    has_unittest_options = any(arg.startswith("-") for arg in unittest_argv[1:])
    if suite_name != "full" and has_unittest_options:
        print("--suite cannot be combined with unittest runner options", file=sys.stderr)
        sys.exit(2)

    selected_args = selected_unittest_args(unittest_argv)
    full_suite = suite_name in {"coverage-safe", "full"} and not has_unittest_options and not selected_args
    should_discover = (suite_name != "full" or jobs > 1) and not has_unittest_options
    if should_discover:
        test_names = discover_unittest_test_names(unittest_argv)
        if test_names is not None and suite_name != "full":
            test_names = filter_test_names_by_suite(test_names, suite_name)
        if test_names and len(test_names) > 1 and jobs > 1:
            sys.exit(run_sharded_tests(test_names, jobs, allow_xvfb_sidecar=full_suite))
        if test_names:
            unittest_argv = [unittest_argv[0], *test_names]
        elif test_names == []:
            print(f"No tests matched --suite {suite_name}", file=sys.stderr)
            sys.exit(1)

    unittest.main(argv=unittest_argv, testRunner=ProgressTextTestRunner)


if __name__ == "__main__":
    main()
