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

"""Unit tests for the res/campaign.py campaign driver.

campaign.py deliberately has no module-level engine imports, so everything
except campaign.start() is testable with plain fakes before the native
extension is built (mirroring how scripts/validate_content.py runs first in CI).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "res") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "res"))

import campaign


def manifest_fixture():
    return {
        "format": "fall-of-nouraajd-campaign",
        "schemaVersion": 1,
        "campaignId": "trial",
        "title": "Trial Campaign",
        "description": "A short trial.",
        "start": "one",
        "completionText": "The trial ends.",
        "scenarios": {
            "one": {
                "map": "mapOne",
                "title": "Chapter I",
                "briefing": "Begin.",
                "epilogue": "Onward.",
                "next": {"completed": "two", "sidetracked": "aside"},
            },
            "aside": {
                "map": "mapAside",
                "title": "Interlude",
                "briefing": "A detour.",
                "next": {"completed": "two"},
            },
            "two": {
                "map": "mapTwo",
                "title": "Chapter II",
                "briefing": "End.",
                "carryover": {"gold_max": 100, "items_deny": ["cursedIdol"]},
                "next": {},
            },
        },
    }


class FakeItem:
    def __init__(self, name):
        self._name = name

    def getName(self):
        return self._name


class FakePlayer:
    def __init__(self, gold=0, items=()):
        self.gold = gold
        self.items = [FakeItem(name) for name in items]
        self.string_properties = {}
        self.bool_properties = {}

    def getStringProperty(self, name):
        return self.string_properties.get(name, "")

    def setStringProperty(self, name, value):
        self.string_properties[name] = value

    def getBoolProperty(self, name):
        return self.bool_properties.get(name, False)

    def setBoolProperty(self, name, value):
        self.bool_properties[name] = value

    def getGold(self):
        return self.gold

    def addGold(self, amount):
        self.gold += amount

    def removeItem(self, predicate, remove_all=False):
        kept = []
        removed = False
        for item in self.items:
            if predicate(item) and (remove_all or not removed):
                removed = True
                continue
            kept.append(item)
        self.items = kept

    def item_names(self):
        return sorted(item.getName() for item in self.items)


class FakeGuiHandler:
    def __init__(self):
        self.messages = []

    def showMessage(self, text):
        self.messages.append(text)


class ScreenFakeGuiHandler(FakeGuiHandler):
    """A GUI double exposing the engine's blocking campaign-presentation call.

    When showCampaignScreen exists the driver must route every briefing,
    epilogue, and completion through it (with BEGIN/CONTINUE/RETURN action
    labels) instead of the legacy showMessage fallback.
    """

    def __init__(self):
        super().__init__()
        self.screens = []

    def showCampaignScreen(self, title, body, action_label):
        self.screens.append((title, body, action_label))


class FakeMap:
    def __init__(self, player):
        self.player = player

    def getPlayer(self):
        return self.player


class FakeGame:
    def __init__(self, player):
        self.map = FakeMap(player)
        self.gui_handler = FakeGuiHandler()
        self.map_changes = []

    def getMap(self):
        return self.map

    def getGuiHandler(self):
        return self.gui_handler

    def changeMap(self, map_name):
        self.map_changes.append(map_name)


class ManifestTest(unittest.TestCase):
    def write_campaign(self, root, data, campaign_id="trial"):
        campaign_dir = Path(root) / campaign_id
        campaign_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = campaign_dir / campaign.CAMPAIGN_MANIFEST_NAME
        manifest_path.write_text(json.dumps(data), encoding="utf-8")
        return manifest_path

    def make_root(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return Path(temp_dir.name)

    def test_validate_manifest_accepts_fixture(self):
        self.assertEqual(manifest_fixture(), campaign.validate_manifest(manifest_fixture()))

    def test_validate_manifest_rejects_structural_errors(self):
        cases = [
            ("format", "wrong"),
            ("schemaVersion", 2),
            ("start", "missing"),
            ("scenarios", {}),
            ("title", ""),
            ("unexpected", True),
        ]
        for key, value in cases:
            with self.subTest(key=key):
                data = manifest_fixture()
                data[key] = value
                with self.assertRaises(campaign.CampaignError):
                    campaign.validate_manifest(data)

    def test_validate_manifest_rejects_scenario_errors(self):
        breakages = [
            lambda s: s["one"].pop("briefing"),
            lambda s: s["one"].__setitem__("map", ""),
            lambda s: s["one"].__setitem__("next", {"completed": "missing"}),
            lambda s: s["one"].__setitem__("bogus", 1),
            lambda s: s["two"].__setitem__("carryover", {"bogus": 1}),
            lambda s: s["two"].__setitem__("carryover", {"gold_max": -1}),
            lambda s: s["two"].__setitem__("carryover", {"gold_max": True}),
            lambda s: s["two"].__setitem__("carryover", {"items_allow": ["a"], "items_deny": ["b"]}),
            lambda s: s["two"].__setitem__("carryover", {"items_allow": [""]}),
        ]
        for index, breakage in enumerate(breakages):
            with self.subTest(case=index):
                data = manifest_fixture()
                breakage(data["scenarios"])
                with self.assertRaises(campaign.CampaignError):
                    campaign.validate_manifest(data)

    def test_validate_manifest_rejects_non_string_start(self):
        # A non-string "start" must raise CampaignError, not an unguarded
        # TypeError from the ``start in scenarios`` membership test.
        for bad_start in ([], {}, 3, None):
            with self.subTest(start=bad_start):
                data = manifest_fixture()
                data["start"] = bad_start
                with self.assertRaises(campaign.CampaignError):
                    campaign.validate_manifest(data)

    def test_validate_manifest_rejects_history_delimiters(self):
        # Scenario ids and outcome keys are serialized into campaign history as
        # "<id>:<outcome>" entries joined by ",", so neither may contain those
        # delimiters or the recorded history would be corrupted.
        colon_id = manifest_fixture()
        colon_id["scenarios"]["on:e"] = colon_id["scenarios"].pop("one")
        colon_id["start"] = "on:e"

        comma_outcome = manifest_fixture()
        comma_outcome["scenarios"]["one"]["next"] = {"completed,extra": "two"}

        for label, data in (("colon-in-id", colon_id), ("comma-in-outcome", comma_outcome)):
            with self.subTest(case=label):
                with self.assertRaises(campaign.CampaignError):
                    campaign.validate_manifest(data)

    def test_list_campaigns_returns_sorted_manifests(self):
        root = self.make_root()
        second = manifest_fixture()
        second["campaignId"] = "another"
        self.write_campaign(root, manifest_fixture())
        self.write_campaign(root, second, campaign_id="another")
        (root / "notACampaign").mkdir()

        manifests = campaign.list_campaigns(root)

        self.assertEqual(["another", "trial"], [manifest["campaignId"] for manifest in manifests])

    def test_list_campaigns_rejects_id_directory_mismatch(self):
        root = self.make_root()
        self.write_campaign(root, manifest_fixture(), campaign_id="renamed")

        with self.assertRaises(campaign.CampaignError):
            campaign.list_campaigns(root)

    def test_get_manifest_loads_by_id_and_rejects_unknown(self):
        root = self.make_root()
        self.write_campaign(root, manifest_fixture())

        manifest = campaign.get_manifest("trial", root)

        self.assertEqual("Trial Campaign", manifest["title"])
        with self.assertRaises(campaign.CampaignError):
            campaign.get_manifest("unknown", root)

    def test_get_manifest_rejects_path_traversal_ids(self):
        # campaign_id can originate from an untrusted save; a traversal id must be
        # refused before it is joined into the manifest filesystem path.
        root = self.make_root()
        self.write_campaign(root, manifest_fixture())
        for bad_id in ("../trial", "a/b", "..", ".", "", "a\\b"):
            with self.subTest(campaign_id=bad_id):
                with self.assertRaises(campaign.CampaignError):
                    campaign.get_manifest(bad_id, root)

    def test_shipped_campaigns_load_and_validate(self):
        manifests = campaign.list_campaigns()

        self.assertIn("fallOfNouraajd", [manifest["campaignId"] for manifest in manifests])
        self.assertIn("wardensRoad", [manifest["campaignId"] for manifest in manifests])
        for manifest in manifests:
            with self.subTest(campaign=manifest["campaignId"]):
                campaign.validate_manifest(manifest)

    def test_wardens_road_routes_both_judgments_to_terminal_finales(self):
        manifest = campaign.get_manifest("wardensRoad")

        self.assertEqual("homecoming", manifest["start"])
        self.assertEqual("rescue", campaign.next_scenario(manifest, "homecoming", "completed"))
        self.assertEqual("assault_mercy", campaign.next_scenario(manifest, "rescue", "spared"))
        self.assertEqual("assault_wrath", campaign.next_scenario(manifest, "rescue", "executed"))
        # Both finales reuse the usurpergate map and are terminal.
        for finale in ("assault_mercy", "assault_wrath"):
            with self.subTest(finale=finale):
                self.assertEqual("usurpergate", manifest["scenarios"][finale]["map"])
                self.assertIsNone(campaign.next_scenario(manifest, finale, "completed"))
        # The wrath route enters the finale with the war-chest clamped.
        self.assertEqual({"gold_max": 400}, manifest["scenarios"]["assault_wrath"]["carryover"])
        with self.assertRaises(campaign.CampaignError):
            campaign.next_scenario(manifest, "rescue", "completed")


class RoutingTest(unittest.TestCase):
    def test_next_scenario_routes_outcomes(self):
        manifest = manifest_fixture()
        self.assertEqual("two", campaign.next_scenario(manifest, "one", "completed"))
        self.assertEqual("aside", campaign.next_scenario(manifest, "one", "sidetracked"))

    def test_next_scenario_terminal_returns_none_for_any_outcome(self):
        self.assertIsNone(campaign.next_scenario(manifest_fixture(), "two", "completed"))
        self.assertIsNone(campaign.next_scenario(manifest_fixture(), "two", "anything"))

    def test_next_scenario_rejects_unknown_scenario_and_unrouted_outcome(self):
        with self.assertRaises(campaign.CampaignError):
            campaign.next_scenario(manifest_fixture(), "missing", "completed")
        with self.assertRaises(campaign.CampaignError):
            campaign.next_scenario(manifest_fixture(), "one", "unrouted")


class CarryoverTest(unittest.TestCase):
    def test_no_policy_carries_everything(self):
        player = FakePlayer(gold=500, items=("sword", "cursedIdol"))
        campaign.apply_carryover(player, None)
        campaign.apply_carryover(player, {})
        self.assertEqual(500, player.getGold())
        self.assertEqual(["cursedIdol", "sword"], player.item_names())

    def test_gold_max_clamps_only_above_the_cap(self):
        rich = FakePlayer(gold=500)
        poor = FakePlayer(gold=50)
        campaign.apply_carryover(rich, {"gold_max": 100})
        campaign.apply_carryover(poor, {"gold_max": 100})
        self.assertEqual(100, rich.getGold())
        self.assertEqual(50, poor.getGold())

    def test_items_allow_keeps_only_listed_items(self):
        player = FakePlayer(items=("sword", "sword", "cursedIdol", "LifePotion"))
        campaign.apply_carryover(player, {"items_allow": ["sword"]})
        self.assertEqual(["sword", "sword"], player.item_names())

    def test_items_deny_strips_listed_items(self):
        player = FakePlayer(items=("sword", "cursedIdol", "cursedIdol"))
        campaign.apply_carryover(player, {"items_deny": ["cursedIdol"]})
        self.assertEqual(["sword"], player.item_names())


class CampaignStateStoreTest(unittest.TestCase):
    def test_begin_advance_finish_round_trip(self):
        store = campaign.CampaignStateStore(FakePlayer())
        self.assertFalse(store.active())

        store.begin("trial", "one")
        self.assertTrue(store.active())
        self.assertEqual("trial", store.campaign_id())
        self.assertEqual("one", store.scenario())
        self.assertFalse(store.finished())

        store.advance("two")
        self.assertEqual("two", store.scenario())

        store.finish()
        self.assertTrue(store.finished())
        self.assertFalse(store.active())

    def test_history_records_outcomes_in_order(self):
        store = campaign.CampaignStateStore(FakePlayer())
        store.begin("trial", "one")
        store.record_outcome("one", "completed")
        store.record_outcome("two", "good_ending")
        self.assertEqual([("one", "completed"), ("two", "good_ending")], store.history())

    def test_vars_round_trip_with_default(self):
        store = campaign.CampaignStateStore(FakePlayer())
        self.assertEqual("no", store.get_var("spared_cultist", default="no"))
        store.set_var("spared_cultist", "yes")
        self.assertEqual("yes", store.get_var("spared_cultist", default="no"))
        with self.assertRaises(campaign.CampaignError):
            store.set_var("not an identifier", "value")


class CompleteScenarioTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.root, ignore_errors=True))
        campaign_dir = self.root / "trial"
        campaign_dir.mkdir(parents=True)
        (campaign_dir / campaign.CAMPAIGN_MANIFEST_NAME).write_text(json.dumps(manifest_fixture()), encoding="utf-8")
        self._original_root = campaign.campaigns_root
        campaign.campaigns_root = lambda: self.root
        self.addCleanup(self._restore_root)

    def _restore_root(self):
        campaign.campaigns_root = self._original_root

    def start_campaign(self, gold=500, items=("sword", "cursedIdol")):
        player = FakePlayer(gold=gold, items=items)
        game = FakeGame(player)
        campaign.CampaignStateStore(player).begin("trial", "one")
        return game, player

    def test_inactive_campaign_falls_back_to_legacy_map_change(self):
        game = FakeGame(FakePlayer())

        self.assertIsNone(campaign.complete_scenario(game, "completed", fallback_map="legacy"))
        self.assertEqual(["legacy"], game.map_changes)

        self.assertIsNone(campaign.complete_scenario(game, "completed"))
        self.assertEqual(["legacy"], game.map_changes)

    def test_completed_outcome_advances_and_applies_carryover(self):
        game, player = self.start_campaign()

        result = campaign.complete_scenario(game, "completed", fallback_map="legacy")

        self.assertEqual("two", result)
        store = campaign.CampaignStateStore(player)
        self.assertEqual("two", store.scenario())
        self.assertEqual([("one", "completed")], store.history())
        self.assertEqual(["mapTwo"], game.map_changes)
        self.assertEqual(100, player.getGold())
        self.assertEqual(["sword"], player.item_names())
        self.assertIn("Onward.", game.gui_handler.messages)
        self.assertIn("Chapter II. End.", game.gui_handler.messages)

    def test_branching_outcome_routes_to_alternate_scenario(self):
        game, player = self.start_campaign()

        self.assertEqual("aside", campaign.complete_scenario(game, "sidetracked"))
        self.assertEqual(["mapAside"], game.map_changes)
        self.assertEqual("aside", campaign.CampaignStateStore(player).scenario())

    def test_terminal_scenario_finishes_the_campaign(self):
        game, player = self.start_campaign()
        campaign.CampaignStateStore(player).advance("two")

        result = campaign.complete_scenario(game, "completed")

        self.assertEqual("", result)
        store = campaign.CampaignStateStore(player)
        self.assertTrue(store.finished())
        self.assertFalse(store.active())
        self.assertEqual([], game.map_changes)
        self.assertIn("The trial ends.", game.gui_handler.messages)

        # A repeated completion report after the campaign finished is inert.
        self.assertIsNone(campaign.complete_scenario(game, "completed"))
        self.assertEqual([], game.map_changes)

    def test_presentation_screens_flow_with_begin_continue_return_labels(self):
        # [EPIC_10][STORY_04][SUBSTORY_01] With a screen-capable GUI handler the driver
        # presents epilogues (CONTINUE), the next briefing (BEGIN), and the terminal
        # completion (RETURN) as blocking campaign screens, in order, and never falls
        # back to showMessage. A scenario without an epilogue shows no CONTINUE screen.
        game, player = self.start_campaign()
        game.gui_handler = ScreenFakeGuiHandler()

        self.assertEqual("two", campaign.complete_scenario(game, "completed"))
        self.assertEqual(
            [
                ("Chapter I", "Onward.", "CONTINUE"),
                ("Chapter II", "End.", "BEGIN"),
            ],
            game.gui_handler.screens,
        )
        self.assertEqual([], game.gui_handler.messages, "screen-capable handlers bypass showMessage")

        # Terminal completion: scenario two has no epilogue, so the only screen is
        # the campaign completion with RETURN.
        game.gui_handler.screens.clear()
        self.assertEqual("", campaign.complete_scenario(game, "completed"))
        self.assertEqual(
            [("Trial Campaign", "The trial ends.", "RETURN")],
            game.gui_handler.screens,
        )
        self.assertEqual([], game.gui_handler.messages)

    def test_unrouted_outcome_raises(self):
        game, _player = self.start_campaign()

        with self.assertRaises(campaign.CampaignError):
            campaign.complete_scenario(game, "unrouted")
        self.assertEqual([], game.map_changes)


if __name__ == "__main__":
    unittest.main()
