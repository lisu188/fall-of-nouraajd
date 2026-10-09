# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure contract regressions for the natural-play MCP driver."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests.gameplay_branch_driver import (
    FORBIDDEN_METHODS,
    GameplayBranchDriver,
    authoredRoadCells,
    canonicalNativeState,
    campaignCheckpointState,
    readNewNativeTrace,
)
from tests.gameplay_branch_types import RouteCase


class GameplayBranchDriverTest(unittest.TestCase):
    def testNativeSetComparisonsIgnoreAllocationOrderAndPreserveFullIdentity(self):
        first = {
            "items": [
                {"properties": {"name": "sword", "typeId": "Sword", "power": 2, "tags": ["owned", "sharp"]}},
                {"properties": {"name": "potion", "typeId": "LifePotion", "power": 1}},
            ],
            "quests": [{"properties": {"name": "questA"}}, {"properties": {"name": "questB"}}],
            "completedQuests": [{"properties": {"name": "oldA"}}, {"properties": {"name": "oldB"}}],
            "equipped": {"weapon": {"properties": {"name": "sword", "coveredSlots": ["weapon", "offhand"]}}},
            "campaign_history": "first:won,second:left",
            "orderedRoute": ["north", "south"],
        }
        reordered = deepcopy(first)
        for key in ("items", "quests", "completedQuests"):
            reordered[key].reverse()
        reordered["items"][1]["properties"]["tags"].reverse()
        reordered["equipped"]["weapon"]["properties"]["coveredSlots"].reverse()
        self.assertEqual(canonicalNativeState(first), canonicalNativeState(reordered))
        self.assertEqual(["north", "south"], canonicalNativeState(first)["orderedRoute"])
        self.assertEqual("first:won,second:left", canonicalNativeState(first)["campaign_history"])
        self.assertEqual("sword", canonicalNativeState(first)["equipped"]["weapon"]["properties"]["name"])
        for difference in ("missing", "changed", "extra", "duplicate", "differentIdentity", "ordered", "slot"):
            changed = deepcopy(reordered)
            if difference == "missing":
                changed["items"].pop()
            elif difference == "changed":
                changed["items"][0]["properties"]["power"] += 1
            elif difference == "extra":
                changed["quests"].append({"properties": {"name": "extra"}})
            elif difference == "duplicate":
                changed["items"].append(deepcopy(changed["items"][0]))
            elif difference == "differentIdentity":
                changed["items"][0]["properties"]["name"] = "other-instance"
            elif difference == "ordered":
                changed["orderedRoute"].reverse()
            elif difference == "slot":
                changed["equipped"]["offhand"] = changed["equipped"].pop("weapon")
            with self.subTest(difference=difference):
                self.assertNotEqual(canonicalNativeState(first), canonicalNativeState(changed))
        self.assertEqual(["owned", "sharp"], first["items"][0]["properties"]["tags"])

    def testCampaignCheckpointUsesNativeDefaultsWithoutDroppingNonemptyProgress(self):
        driver = self.driver()
        native = {"campaign_id": "wardensRoad", "campaign_history": "hearthfall:mercy"}
        driver.call = Mock(
            side_effect=lambda actor, method, key: native.get(key, False if method == "getBoolProperty" else "")
        )
        before = {**native, "campaign_pendingTransition": "", "campaign_var_cleared": ""}
        expected = campaignCheckpointState(driver, before)
        self.assertEqual(expected, campaignCheckpointState(driver, native))
        self.assertEqual("", expected["campaign_pendingTransition"])
        self.assertFalse(expected["campaign_finished"])
        for key, value in (
            ("campaign_pendingTransition", "{pending}"),
            ("campaign_var_choice", "wrath"),
            ("campaign_history", "hearthfall:wrath"),
            ("campaign_finished", True),
        ):
            with self.subTest(key=key):
                changed = {**native, key: value}
                driver.call.side_effect = lambda actor, method, name, values=changed: values.get(
                    name, False if method == "getBoolProperty" else ""
                )
                self.assertNotEqual(expected, campaignCheckpointState(driver, changed))
        self.assertNotEqual(canonicalNativeState({"other": ""}), canonicalNativeState({}))
        self.assertNotEqual(canonicalNativeState({"campaign_unrecognized": ""}), canonicalNativeState({}))

    def driver(self):
        case = RouteCase("unit", "unit", ("test",), ("unit.branch",), lambda driver: None)
        driver = GameplayBranchDriver(self, Mock(), None, case, "Warrior", Path("."))
        driver.game = {"__handle__": "game"}
        driver.game_map = {"__handle__": "map"}
        driver.player = {"__handle__": "player"}
        driver.map_name = "test"
        driver._rawCall = Mock()
        return driver

    def roadDriver(self, *, roads, origin=(0, 0, 0), hp=2, hp_max=5, mana=1, mana_max=3, actors=()):
        driver = self.driver()
        controller, loop = ({"__handle__": name} for name in ("controller", "loop"))
        state = {
            "coords": tuple(origin),
            "hp": hp,
            "hpMax": hp_max,
            "mana": mana,
            "manaMax": mana_max,
            "turn": 0,
            "roads": set(roads),
            "blocked": set(),
            "actors": {actor["name"]: dict(actor) for actor in actors},
            "objects": {},
            "targets": [],
            "defeatReceipt": "",
            "onMove": None,
        }
        source_roads = patch(
            "tests.gameplay_branch_driver.authoredRoadCells", side_effect=lambda map_id: state["roads"]
        )
        source_roads.start()
        self.addCleanup(source_roads.stop)

        def coords(handle=None):
            if handle is None or handle == driver.player:
                return state["coords"]
            return handle.get("coords") or state["actors"][handle["__handle__"]]["coords"]

        def rawCall(handle, method, *args):
            if method in {"getHp", "getHpMax", "getMana", "getManaMax"}:
                return state[method[3:4].lower() + method[4:]]
            if method == "getHpRatio":
                return int(100 * state["hp"] / state["hpMax"])
            if method == "getItems":
                return []
            if method == "getGold":
                return 50
            if method == "getStringProperty":
                if handle == driver.player:
                    return state["defeatReceipt"] if args[0] == "uiDefeatReceipt" else "heroes"
                return state["actors"][handle["__handle__"]].get("affiliation", "")
            if method == "getObjects":
                return [
                    {"__handle__": name, "__type__": actor.get("type", "CCreature")}
                    for name, actor in state["actors"].items()
                ]
            if method in {"isAlive", "isNpc"}:
                return state["actors"][handle["__handle__"]].get(
                    "alive" if method == "isAlive" else "npc", method == "isAlive"
                )
            if method == "getTile":
                return {"__handle__": "tile", "coords": tuple(args)}
            if method == "getTypeId":
                return "RoadTile" if handle["coords"] in state["roads"] else "GrassTile"
            if method == "canStep":
                return args[0]["coords"] not in state["blocked"]
            if method == "getController":
                return controller
            if method == "setTarget":
                self.assertEqual(driver.player, args[0])
                state["target"] = args[1]["coords"]
                state["targets"].append(state["target"])
                return
            if method == "getTurn":
                return state["turn"]
            if method == "move":
                state["turn"] += 1
                if not state.get("stall"):
                    origin, target = state["coords"], state["target"]
                    axis = next((index for index in (0, 1) if origin[index] != target[index]), None)
                    if axis is not None:
                        arrival = list(origin)
                        arrival[axis] += 1 if target[axis] > origin[axis] else -1
                        state["coords"] = tuple(arrival)
                    if state["coords"] in state["roads"]:
                        state["hp"] = min(state["hpMax"], state["hp"] + 1)
                state["mana"] = min(state["manaMax"], state["mana"] + 1)
                if state["onMove"]:
                    state["onMove"]()
                return
            if method == "run":
                return
            if method == "getObjectByName":
                return state["objects"].get(args[0])
            if method == "getCoords":
                return {"__handle__": "target-coords", "coords": coords(handle)}
            if method == "getNavigationNeighbors":
                return []
            self.fail(("Unexpected fake native call", handle, method, args))

        driver.coords = coords
        driver._coordinateHandle = lambda value: {"__handle__": "point", "coords": tuple(value)}
        driver._rawCall.side_effect = rawCall
        driver.engine = Mock(return_value=loop)
        driver.refresh = Mock()
        return driver, state

    def testRoadRecoveryUsesNativeControllerAndRealTurnsToRestoreObservedResources(self):
        driver, state = self.roadDriver(roads={(x, 0, 0) for x in range(7)})
        self.assertEqual(3, driver.recoverOnAuthoredRoad())
        self.assertEqual((3, 0, 0), state["coords"])
        self.assertEqual((5, 3), (state["hp"], state["mana"]))
        self.assertEqual((3, 3, 3), (state["turn"], driver.turns, driver.steps))
        methods = [call.args[1] for call in driver._rawCall.call_args_list]
        self.assertEqual(3, methods.count("setTarget"))
        self.assertEqual(3, methods.count("move"))
        self.assertEqual(9, methods.count("run"))
        self.assertFalse(set(methods) & (FORBIDDEN_METHODS | {"moveTo", "useItem", "equipItem"}))

    def testUnresolvedNativePlayerCombatsFailBeforeAnotherMovementAndRemainLatched(self):
        for outcome in (0, 3, 4, None, 99, True):
            for role in ("attacker", "opponent"):
                with self.subTest(outcome=outcome, role=role), tempfile.TemporaryDirectory() as directory:
                    driver, state = self.roadDriver(roads={(x, 0, 0) for x in range(4)})
                    driver.trace_path = Path(directory) / "native.trace.jsonl"
                    state["objects"]["goal"] = {"__handle__": "goal", "coords": (2, 0, 0)}
                    player, enemy = {"name": "hero", "isPlayer": True}, {"name": "enemy", "isPlayer": False}
                    record = {
                        "seq": 1,
                        "event": "combat_finished",
                        "map": "test",
                        "outcome": outcome,
                        "attacker": player if role == "attacker" else enemy,
                        "opponents": [enemy if role == "attacker" else player],
                        "survivor": player,
                    }
                    state["onMove"] = lambda: driver.trace_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(AssertionError, "Unresolved native player combat"):
                        driver.navigateTo("goal")
                    self.assertEqual(1, state["turn"], "The unresolved encounter must not be retried")
                    record.update(seq=2, outcome=1)
                    driver.trace_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(AssertionError, "Unresolved native player combat"):
                        driver.assertSurvival()

    def testResolvedNativePlayerWinsAndUnrelatedUnresolvedCombatsDoNotFailSurvival(self):
        with tempfile.TemporaryDirectory() as directory:
            driver, state = self.roadDriver(roads={(0, 0, 0)})
            driver.trace_path = Path(directory) / "native.trace.jsonl"
            player, enemy = {"isPlayer": True}, {"isPlayer": False}
            records = [
                {"seq": 1, "event": "combat_finished", "outcome": 1, "attacker": player, "opponents": [enemy]},
                {"seq": 2, "event": "combat_finished", "outcome": 2, "attacker": enemy, "opponents": [player]},
                {"seq": 3, "event": "combat_finished", "outcome": 3, "attacker": enemy, "opponents": [enemy]},
                {"seq": 4, "event": "movement", "outcome": 0, "attacker": player},
            ]
            driver.trace_path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
            driver.assertSurvival()
            driver.assertSurvival()
            self.assertEqual(0, state["turn"])

    def testNativeCombatGuardInspectsRotatedFailureBeforeLaterResolvedEncounter(self):
        with tempfile.TemporaryDirectory() as directory:
            driver, _ = self.roadDriver(roads={(0, 0, 0)})
            driver.trace_path = Path(directory) / "native.trace.jsonl"
            record = {"seq": 1, "event": "movement"}
            driver.trace_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            driver.assertSurvival()
            record.update(seq=2, event="combat_finished", outcome=4, attacker={"isPlayer": True}, opponents=[])
            with driver.trace_path.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record) + "\n")
            driver.trace_path.replace(Path(str(driver.trace_path) + ".1"))
            record.update(seq=3, outcome=1)
            driver.trace_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "Unresolved native player combat"):
                driver.assertSurvival()

    def testNativeTraceReaderKeepsIndependentIncrementalCursorsAcrossRotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path, positions = Path(directory) / "native.trace.jsonl", {}
            path.write_text(json.dumps({"seq": 1, "event": "movement"}) + "\n", encoding="utf-8")
            self.assertEqual([1], [record["seq"] for record in readNewNativeTrace(path, positions)])
            self.assertEqual((), readNewNativeTrace(path, positions, after_seq=1))
            path.replace(Path(str(path) + ".1"))
            path.write_text(json.dumps({"seq": 2, "event": "combat_finished"}) + "\n", encoding="utf-8")
            self.assertEqual([2], [record["seq"] for record in readNewNativeTrace(path, positions, after_seq=1)])
            with path.open("a", encoding="utf-8") as output:
                output.write(json.dumps({"seq": 3, "event": "movement"}) + "\n")
            self.assertEqual([3], [record["seq"] for record in readNewNativeTrace(path, positions, after_seq=2)])
            self.assertEqual([1, 2, 3], [record["seq"] for record in readNewNativeTrace(path, {})])

    def testPotionObservationCommitsCursorBeforeChecksAndLatchesInvalidEvidence(self):
        for invalid in (False, True):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as directory:
                driver = self.driver()
                driver.trace_path = Path(directory) / "native.trace.jsonl"
                driver.trace_path.write_text(json.dumps({"seq": 1, "event": "item_used"}) + "\n", encoding="utf-8")

                def observe(observed_driver, records, **kwargs):
                    self.assertEqual(1, observed_driver._combat_trace_seq)
                    self.assertEqual([1], [record["seq"] for record in records])
                    if invalid:
                        raise AssertionError("A malformed consumed identity cannot be discarded")
                    observed_driver.assertNativeCombatOutcomes()

                with patch("tests.gameplay_branch_driver.observePotionConsumptions", side_effect=observe) as observer:
                    if invalid:
                        with self.assertRaisesRegex(AssertionError, "Invalid native potion evidence"):
                            driver.assertNativeCombatOutcomes()
                        with self.assertRaisesRegex(AssertionError, "Invalid native potion evidence"):
                            driver.assertNativeCombatOutcomes()
                    else:
                        driver.assertNativeCombatOutcomes()
                    observer.assert_called_once()

    def testNativeTraceReaderDeduplicatesIdenticalRotatedRecordsAndRejectsConflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.trace.jsonl"
            record = {"seq": 1, "event": "combat_finished", "outcome": 3}
            for candidate in (path, Path(str(path) + ".1")):
                candidate.write_text(json.dumps(record) + "\n", encoding="utf-8")
            self.assertEqual((record,), readNewNativeTrace(path, {}))
            record["outcome"] = 1
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "Conflicting native trace records"):
                readNewNativeTrace(path, {})

    def testNativeTraceReaderCommitsCursorsOnlyAfterCompleteValidation(self):
        for failure in ("gap", "malformed-current", "conflict"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "native.trace.jsonl"
                backup = Path(str(path) + ".1")
                backup.write_text(json.dumps({"seq": 1, "event": "movement"}) + "\n", encoding="utf-8")
                if failure == "gap":
                    contents = json.dumps({"seq": 3, "event": "movement"}) + "\n"
                elif failure == "malformed-current":
                    contents = "{bad-json\n"
                else:
                    contents = json.dumps({"seq": 1, "event": "different-event"}) + "\n"
                path.write_text(contents, encoding="utf-8")
                positions = {}
                for _attempt in range(2):
                    with self.assertRaises((AssertionError, ValueError)):
                        readNewNativeTrace(path, positions)
                    self.assertEqual({}, positions, "Rejected evidence must not advance either file cursor")

    def testNativeTraceDisappearanceAfterObservedRecordsFailsAndRemainsLatched(self):
        with tempfile.TemporaryDirectory() as directory:
            driver, _ = self.roadDriver(roads={(0, 0, 0)})
            driver.trace_path = Path(directory) / "native.trace.jsonl"
            driver.assertSurvival()  # Before the first native event the trace need not exist yet.
            driver.trace_path.write_text(json.dumps({"seq": 1, "event": "movement"}) + "\n", encoding="utf-8")
            driver.assertSurvival()
            driver.trace_path.unlink()
            with self.assertRaisesRegex(AssertionError, "Native trace files disappeared"):
                driver.assertSurvival()
            driver.trace_path.write_text(json.dumps({"seq": 2, "event": "movement"}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "Native trace files disappeared"):
                driver.assertSurvival()

    def testFinishedRouteRequiresObservedNativeTraceRecordsAndLatchesMissingEvidence(self):
        for missing in (True, False):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                driver, _ = self.roadDriver(roads={(0, 0, 0)})
                driver.trace_path = Path(directory) / "native.trace.jsonl"
                if not missing:
                    driver.trace_path.write_text("", encoding="utf-8")
                driver.branches = {"unit.branch": {}}
                driver.assertSurvival()  # Empty pre-event startup reads remain valid.
                with patch("tests.gameplay_branch_driver.verifyJournals"):
                    with self.assertRaisesRegex(AssertionError, "No observed native trace records"):
                        driver.finish()
                driver.trace_path.write_text(json.dumps({"seq": 1, "event": "movement"}) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(AssertionError, "No observed native trace records"):
                    driver.assertSurvival()

    def testFinishedRouteAcceptsObservedNativeTraceRecords(self):
        with tempfile.TemporaryDirectory() as directory:
            driver, _ = self.roadDriver(roads={(0, 0, 0)})
            driver.trace_path = Path(directory) / "native.trace.jsonl"
            driver.trace_path.write_text(json.dumps({"seq": 1, "event": "movement"}) + "\n", encoding="utf-8")
            driver.branches = {"unit.branch": {}}
            with patch("tests.gameplay_branch_driver.verifyJournals"):
                driver.finish()
            self.assertEqual(1, driver._combat_trace_seq)

    def testNativeTraceGapsAndUnreadableRecordsFailSurvivalAndCannotBeClearedByLaterSuccess(self):
        for failure in ("initial-gap", "later-gap", "malformed"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                driver, _ = self.roadDriver(roads={(0, 0, 0)})
                driver.trace_path = Path(directory) / "native.trace.jsonl"
                if failure == "later-gap":
                    driver.trace_path.write_text(json.dumps({"seq": 1, "event": "movement"}) + "\n", encoding="utf-8")
                    driver.assertSurvival()
                contents = (
                    "{bad-json\n"
                    if failure == "malformed"
                    else json.dumps(
                        {"seq": 3, "event": "combat_finished", "outcome": 1, "attacker": {"isPlayer": True}}
                    )
                    + "\n"
                )
                driver.trace_path.write_text(contents, encoding="utf-8")
                message = (
                    "Native combat evidence unavailable" if failure == "malformed" else "Native trace evidence was lost"
                )
                with self.assertRaisesRegex(AssertionError, message):
                    driver.assertSurvival()
                driver.trace_path.write_text(json.dumps({"seq": 1, "event": "movement"}) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(AssertionError, message):
                    driver.assertSurvival()

    def testRoadRecoveryRereadsHostilesAndMovesAwayWithoutEnteringTheirCells(self):
        driver, state = self.roadDriver(
            roads={(x, 0, 0) for x in range(-4, 5)},
            hp=3,
            actors=({"name": "pursuer", "coords": (2, 0, 0)},),
        )
        state["onMove"] = lambda: state["actors"]["pursuer"].update(coords=(-3, 0, 0))
        self.assertEqual(2, driver.recoverOnAuthoredRoad())
        self.assertEqual([(-1, 0, 0), (0, 0, 0)], state["targets"])

    def testRoadRecoveryExcludesDeadNpcAffiliatedAndOtherLevelActorsFromThreats(self):
        driver, state = self.roadDriver(
            roads={(0, 0, 0), (1, 0, 0)},
            hp=4,
            mana=3,
            actors=(
                {"name": "dead", "coords": (1, 0, 0), "alive": False},
                {"name": "npc", "coords": (1, 0, 0), "npc": True},
                {"name": "ally", "coords": (1, 0, 0), "affiliation": "heroes"},
                {"name": "other-level", "coords": (1, 0, 1)},
                {"name": "event", "coords": (1, 0, 0), "type": "CEvent"},
            ),
        )
        self.assertEqual(1, driver.recoverOnAuthoredRoad())
        self.assertEqual([(1, 0, 0)], state["targets"])

    def testRoadRecoveryRejectsBlockedNonroadHostileAndApproachingTargetsBeforeMovement(self):
        for violation in ("blocked", "nonroad", "hostile", "approaching", "corridor"):
            with self.subTest(violation=violation):
                driver, state = self.roadDriver(roads={(0, 0, 0), (1, 0, 0)})
                options = {}
                if violation == "blocked":
                    state["blocked"].add((1, 0, 0))
                elif violation == "nonroad":
                    state["roads"].remove((1, 0, 0))
                elif violation in {"hostile", "approaching"}:
                    state["actors"]["enemy"] = {"coords": (1 if violation == "hostile" else 4, 0, 0)}
                else:
                    options["road_cells"] = {(0, 0, 0)}
                self.assertIsNone(driver.roadRecoveryTarget(**options))
                with self.assertRaisesRegex(AssertionError, "No safe adjacent authored road"):
                    driver.recoverOnAuthoredRoad(**options)
                self.assertEqual(0, state["turn"])
                self.assertFalse(state["targets"])

    def testRoadRecoveryReturnsImmediatelyWhenBothResourcesAreAlreadyFull(self):
        driver, state = self.roadDriver(roads=set(), hp=5, mana=3)
        self.assertEqual(0, driver.recoverOnAuthoredRoad())
        self.assertEqual(0, state["turn"])
        self.assertFalse(state["targets"])

    def testRoadRecoveryKeepsItsFiniteTurnAndUnchangedNativeStallLimits(self):
        for stalled in (False, True):
            with self.subTest(stalled=stalled):
                driver, state = self.roadDriver(roads={(x, 0, 0) for x in range(6)}, hp=1)
                state["stall"] = stalled
                limit, message = (128, "Native road recovery stalled") if stalled else (2, "recovery budget exhausted")
                with self.assertRaisesRegex(AssertionError, message):
                    driver.recoverOnAuthoredRoad(limit=limit)
                self.assertEqual(24 if stalled else 2, state["turn"])
                self.assertEqual(state["turn"], driver.turns)
        for invalid in (0, -1, True, 129):
            driver, state = self.roadDriver(roads={(0, 0, 0), (1, 0, 0)})
            with self.subTest(limit=invalid), self.assertRaisesRegex(AssertionError, "at most 128 real turns"):
                driver.recoverOnAuthoredRoad(limit=invalid)
            self.assertEqual(0, state["turn"])

    def testRoadRecoveryPreservesGlobalTurnAndActionBudgets(self):
        driver, state = self.roadDriver(roads={(x, 0, 0) for x in range(6)}, hp=1)
        driver.turns = 19999
        with self.assertRaisesRegex(AssertionError, "Route turn budget exhausted"):
            driver.recoverOnAuthoredRoad()
        self.assertEqual((20000, 1), (driver.turns, state["turn"]))
        driver, state = self.roadDriver(roads={(0, 0, 0), (1, 0, 0)})
        with tempfile.TemporaryDirectory() as directory:
            driver.action_path = Path(directory) / "actions.jsonl"
            driver._recorded_actions = 50000
            with self.assertRaisesRegex(AssertionError, "Gameplay action budget exhausted"):
                driver.recoverOnAuthoredRoad()
        self.assertEqual(0, state["turn"])
        self.assertFalse(state["targets"])

    def testRoadRecoveryRejectsDefeatAndUnexpectedMapTransitions(self):
        for violation in ("defeat", "map"):
            with self.subTest(violation=violation):
                driver, state = self.roadDriver(roads={(x, 0, 0) for x in range(6)})

                def intervene():
                    if violation == "defeat":
                        state.update(hp=1, defeatReceipt="native defeat receipt")
                    else:
                        driver.map_name = "other-map"

                state["onMove"] = intervene
                with self.assertRaisesRegex(AssertionError, "defeated/respawned|Road recovery left its map"):
                    driver.recoverOnAuthoredRoad()
                self.assertEqual(1, state["turn"])

    def testNavigationAfterTickHookObservesCompletedNativeTurnAndDefaultRouteIsUnchanged(self):
        for observed in (False, True):
            with self.subTest(observed=observed):
                driver, state = self.roadDriver(roads={(x, 0, 0) for x in range(4)})
                state["objects"]["goal"] = {"__handle__": "goal", "coords": (2, 0, 0)}
                observations = []

                def afterTick():
                    driver.assertSurvival()
                    observations.append((driver.turns, driver.steps, state["coords"]))

                driver.navigateTo("goal", after_tick=afterTick if observed else None)
                self.assertEqual([(2, 0, 0)], state["targets"])
                self.assertEqual((2, 0, 0), state["coords"])
                self.assertEqual([(1, 1, (1, 0, 0)), (2, 2, (2, 0, 0))] if observed else [], observations)

    def testNavigationAfterTickHookDoesNotRunAfterNativeDefeat(self):
        driver, state = self.roadDriver(roads={(x, 0, 0) for x in range(4)})
        state["objects"]["goal"] = {"__handle__": "goal", "coords": (2, 0, 0)}
        state["onMove"] = lambda: state.update(hp=1, defeatReceipt="native defeat receipt")
        callback = Mock()
        with self.assertRaisesRegex(AssertionError, "defeated/respawned"):
            driver.navigateTo("goal", after_tick=callback)
        callback.assert_not_called()

    def testAuthoredRoadPrefilterReadsExplicitTileIdentityAndLevels(self):
        document = {
            "width": 2,
            "tilesets": [
                {"firstgid": 1, "tileproperties": {"0": {"type": "GrassTile"}, "1": {"type": "RoadTile"}}},
                {"firstgid": 20, "tileproperties": {"3": {"type": "RoadTile"}}},
            ],
            "layers": [
                {"type": "tilelayer", "properties": {"level": "0"}, "data": [0, 2, 1, 2]},
                {"type": "tilelayer", "properties": {"level": "1"}, "data": [23, 0, 0, 0]},
                {"type": "objectgroup", "properties": {"level": "0"}, "objects": []},
            ],
        }
        with tempfile.TemporaryDirectory() as directory, patch("tests.gameplay_branch_driver.ROOT", Path(directory)):
            path = Path(directory) / "res/maps/prefilter/map.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(document), encoding="utf-8")
            authoredRoadCells.cache_clear()
            self.addCleanup(authoredRoadCells.cache_clear)
            self.assertEqual(frozenset({(1, 0, 0), (1, 1, 0), (0, 0, 1)}), authoredRoadCells("prefilter"))

    def testRoadRecoveryDoesNotMaterializeTerrainOutsideAuthoredRoadMembership(self):
        driver, state = self.roadDriver(roads={(0, 0, 0), (1, 0, 0)})
        self.assertEqual((1, 0, 0), driver.roadRecoveryTarget())
        tiles = [call.args[2:] for call in driver._rawCall.call_args_list if call.args[1] == "getTile"]
        self.assertEqual([(1, 0, 0)], tiles)

    def testProgressAndResourceActionsAreIncludedInTheDurableActionSequence(self):
        driver = self.driver()
        driver.record = Mock()
        for method in ("useAction", "sealBreach", "checkQuests"):
            with self.subTest(method=method):
                driver.call(driver.player, method)
                self.assertTrue(driver.record.call_args.kwargs["replay"])
                self.assertEqual(method, driver.record.call_args.args[0]["method"])

    def testDurableNavigationTargetRetainsCoordinatesAfterHandleReleaseWithoutExtraReads(self):
        driver = self.driver()
        point, coordinates, controller = ({"__handle__": name} for name in ("point", "coords", "controller"))
        driver._rawCall.side_effect = lambda handle, method, *args: {
            "createObject": point,
            "setNumericProperty": None,
            "getCoords": coordinates,
            "setTarget": None,
        }[method]
        with tempfile.TemporaryDirectory() as directory:
            driver.action_path = Path(directory) / "actions.jsonl"
            driver.call(controller, "setTarget", driver.player, driver._coordinateHandle((12, 7, 1)))
            actions = [json.loads(line) for line in driver.action_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(1, len(actions))
        self.assertEqual("setTarget", actions[0]["method"])
        self.assertEqual([12, 7, 1], actions[0]["targetCoordinates"])
        self.assertEqual(6, driver._rawCall.call_count)
        self.assertFalse(driver._ephemeral_handles)
        self.assertFalse(driver._coordinate_values)
        driver.harness._mcp_tool.assert_called_once_with(None, "engine_release_handles", {"handles": ["coords"]})

    def testCastleDefenderSelectionUsesCurrentAuthoredDistanceAndRetainsUnreachableObligations(self):
        from tests.castle_walkthrough import TransitRoutes
        from tests.gameplay_routes_campaigns import castleNearestDefender

        objects = {
            "west": {"coords": (0, 0, 0)},
            "east": {"coords": (4, 0, 0)},
            "disconnected": {"coords": (9, 9, 0)},
        }
        remaining = set(objects)
        walkable = {(x, 0, 0) for x in range(5)} | {(9, 9, 0)}
        portals = TransitRoutes()
        reserved = (20, 20, 0)
        self.assertEqual("west", castleNearestDefender(remaining, objects, walkable, portals, (1, 0, 0), reserved))
        self.assertEqual("east", castleNearestDefender(remaining, objects, walkable, portals, (3, 0, 0), reserved))
        visited = []
        origin = (1, 0, 0)
        while selected := castleNearestDefender(remaining, objects, walkable, portals, origin, reserved):
            visited.append(selected)
            remaining.remove(selected)
            origin = objects[selected]["coords"]
        self.assertEqual(["west", "east"], visited)
        self.assertEqual({"disconnected"}, remaining)

    def testCastleDefenderSelectionUsesWalkableConnectorsAndReservedObjective(self):
        from tests.castle_walkthrough import TransitRoutes
        from tests.gameplay_routes_campaigns import castleNearestDefender

        objects = {"near": {"coords": (2, 0, 0)}, "portal": {"coords": (9, 0, 1)}}
        walkable = {(0, 0, 0), (1, 0, 0), (2, 0, 0), (9, 0, 1)}
        portals = TransitRoutes()
        portals.passages[(0, 0, 0)] = {(9, 0, 1)}
        self.assertEqual("portal", castleNearestDefender(objects, objects, walkable, portals, (0, 0, 0), (20, 0, 0)))
        self.assertEqual("near", castleNearestDefender(objects, objects, walkable, portals, (0, 0, 0), (9, 0, 1)))

    def testFixtureMutationsAreRejectedBeforeDispatch(self):
        driver = self.driver()
        for method in sorted(FORBIDDEN_METHODS):
            with self.subTest(method=method), self.assertRaises(AssertionError):
                driver.call(driver.player, method)
        driver._rawCall.assert_not_called()

    def testMovementRequiresActualPlayerAndOneNativeStep(self):
        driver = self.driver()
        driver.coords = Mock(return_value=(2, 3, 0))
        for target, destination in ((driver.player, (4, 3, 0)), ({"__handle__": "npc"}, (3, 3, 0))):
            with self.subTest(target=target, destination=destination), self.assertRaises(AssertionError):
                driver.call(target, "moveTo", *destination)
        driver._rawCall.assert_not_called()
        driver.call(driver.player, "moveTo", 3, 3, 0)
        driver._rawCall.assert_called_once_with(driver.player, "moveTo", 3, 3, 0)

    def testConsumablesAndEquipmentMustBeOwned(self):
        for method, prefix in (("useItem", ()), ("equipItem", ("weapon",))):
            with self.subTest(method=method):
                driver = self.driver()
                owned, borrowed = {"__handle__": "owned"}, {"__handle__": "shop-stock"}
                driver._rawCall.side_effect = lambda handle, action, *args: [owned] if action == "getItems" else True
                with self.assertRaises(AssertionError):
                    driver.call(driver.player, method, *prefix, borrowed)
                self.assertEqual(["getItems"], [call.args[1] for call in driver._rawCall.call_args_list])
                driver.call(driver.player, method, *prefix, owned)
                driver._rawCall.assert_called_with(driver.player, method, *prefix, owned)

    def testCastleCaptureRejectsRemoteOrNoncanonicalInteractions(self):
        for violation in ("remote", "otherLevel", "otherMap", "detached", "otherPlayer", "notObjective"):
            with self.subTest(violation=violation):
                driver = self.driver()
                marker = {"__handle__": "marker"}
                marker_coords = (
                    (5, 5, 1) if violation == "otherLevel" else (7, 5, 0) if violation == "remote" else (6, 5, 0)
                )
                driver.coords = lambda handle=None: marker_coords if handle == marker else (5, 5, 0)

                def rawCall(handle, method, *args):
                    if method == "getMap":
                        return {"__handle__": "old-map"} if violation == "otherMap" else driver.game_map
                    if method == "getName":
                        return "objective"
                    if method == "getObjectByName":
                        return {"__handle__": "canonical-marker"} if violation == "detached" else marker
                    if method == "getStringProperty":
                        return "" if violation == "notObjective" else "objective"
                    raise AssertionError(("Rejected capture reached native dispatch", method))

                driver._rawCall.side_effect = rawCall
                player = {"__handle__": "npc"} if violation == "otherPlayer" else driver.player
                with self.assertRaises(AssertionError):
                    driver.call(marker, "capture", player)
                self.assertFalse(any(call.args[1] == "capture" for call in driver._rawCall.call_args_list))

    def testCastleCaptureAllowsCanonicalAdjacentPlayerInteraction(self):
        driver = self.driver()
        marker = {"__handle__": "marker"}
        driver.coords = lambda handle=None: (6, 6, 0) if handle == marker else (5, 5, 0)
        values = {
            "getMap": driver.game_map,
            "getName": "objective",
            "getObjectByName": marker,
            "getStringProperty": "objective",
            "capture": False,
        }
        driver._rawCall.side_effect = lambda handle, method, *args: values[method]
        self.assertFalse(driver.call(marker, "capture", driver.player))
        driver._rawCall.assert_called_with(marker, "capture", driver.player)

    def testCastleCaptureAllowlistIsNarrow(self):
        import mcp

        self.assertEqual({"capture"}, mcp.MCP_ALLOWED_HANDLE_METHODS["CastleObjective"])
        self.assertNotIn("capture", mcp.MCP_ALLOWED_HANDLE_METHODS.get("CMapObject", set()))
        self.assertNotIn("capture", mcp.MCP_ALLOWED_HANDLE_METHODS.get("CBuilding", set()))

    def testSuccessfulHotAssertionsDoNotSerializeSnapshots(self):
        driver = self.driver()
        actor = {"__handle__": "enemy"}
        driver._rawCall.side_effect = lambda handle, method, *args: {
            "getObjectByName": actor,
            "getHp": 10,
            "getStringProperty": "",
        }[method]
        driver.snapshot = Mock(side_effect=AssertionError("Unexpected eager snapshot"))
        self.assertEqual(actor, driver.object("enemy"))
        driver.assertSurvival()
        driver.snapshot.assert_not_called()

    def testSuccessfulCombatDoesNotSerializeFailureSnapshot(self):
        driver = self.driver()
        actor = {"__handle__": "enemy"}
        state = {"alive": True, "exp": 0}
        driver.object = Mock(side_effect=lambda name, required=True: actor if state["alive"] else None)
        driver._rawCall.side_effect = lambda handle, method, *args: (
            state["alive"] if method == "isAlive" else state["exp"]
        )

        def defeat(name):
            state.update(alive=False, exp=10)

        driver.navigateTo = defeat
        driver.snapshot = Mock(side_effect=AssertionError("Unexpected eager snapshot"))
        driver.fight("enemy")
        self.assertEqual(1, driver.combats)
        driver.snapshot.assert_not_called()

    def testOrdinaryAdjacentCellIsNotAPortalArrival(self):
        driver = self.driver()
        for arrival in ((4, 5, 0), (5, 5, 0), (6, 5, 0)):
            self.assertFalse(driver._traversedTarget((5, 5, 0), arrival))
        driver._rawCall.assert_not_called()

    def testPortalArrivalRequiresAuthoredNavigationEdge(self):
        driver = self.driver()
        driver._coordinateHandle = Mock(return_value={"__handle__": "point"})
        driver._rawCall.return_value = [(5, 5, 1), (20, 8, 0)]
        self.assertTrue(driver._traversedTarget((5, 5, 0), (5, 5, 1)))
        self.assertTrue(driver._traversedTarget((5, 5, 0), (20, 8, 0)))
        driver._rawCall.return_value = []
        self.assertFalse(driver._traversedTarget((5, 5, 0), (20, 8, 0)))

    def testPositiveMovementCostDoesNotProveAuthoredRelocation(self):
        driver = self.driver()
        driver._coordinateHandle = lambda coords: {"__handle__": "point", "coords": tuple(coords)}
        driver._rawCall.side_effect = lambda handle, method, *args: (7 if method == "lookupNavigationStepCost" else [])
        self.assertFalse(driver._traversedTarget((5, 5, 0), (20, 8, 0)))
        with self.assertRaisesRegex(AssertionError, "Unexpected unauthored relocation"):
            driver._validateMovement((5, 5, 0), (20, 8, 0))
        with self.assertRaisesRegex(AssertionError, "Unexpected unauthored relocation"):
            driver._validateMovement((5, 5, 0), (5, 5, 1))

    def testMovementValidationAllowsCardinalStepAndRequiresEnabledDirectionalNeighborsForTransit(self):
        driver = self.driver()
        driver._coordinateHandle = lambda coords: {"__handle__": "point", "coords": tuple(coords)}
        origin, entrance, arrival = (5, 5, 0), (6, 5, 0), (20, 8, 1)
        for adjacent in (origin, entrance, (4, 5, 0), (5, 4, 0), (5, 6, 0)):
            driver._validateMovement(origin, adjacent)
        driver._rawCall.assert_not_called()
        driver._rawCall.side_effect = lambda handle, method, *args: ([arrival] if args[0]["coords"] == entrance else [])
        driver._validateMovement(origin, arrival)
        self.assertTrue(driver._traversedTarget(entrance, arrival))
        self.assertFalse(driver._traversedTarget(arrival, entrance))
        driver._rawCall.side_effect = lambda handle, method, *args: [
            (args[0]["coords"][0] + 1, args[0]["coords"][1], args[0]["coords"][2])
        ]
        with self.assertRaisesRegex(AssertionError, "Unexpected unauthored relocation"):
            driver._validateMovement(origin, (7, 5, 0))

    def testMcpNavigationNeighborsExposeOnlyCoordinateValuesWithoutLeakingHandles(self):
        import mcp

        neighbors = [SimpleNamespace(x=6, y=5, z=0), SimpleNamespace(x=20, y=8, z=1)]
        native_map = type("CMap", (), {"getNavigationNeighbors": lambda self, coords: neighbors})()
        server = mcp.EngineMcpServer(Path("."), Path("."))
        map_handle = server._serialize_result(native_map)
        source_handle = server._serialize_result(SimpleNamespace(x=5, y=5, z=0))
        baseline = len(server.handles)
        result = server._engine_handle_call(
            {"handle": map_handle["__handle__"], "method": "getNavigationNeighbors", "args": [source_handle]}
        )
        self.assertFalse(result["isError"])
        self.assertEqual([[6, 5, 0], [20, 8, 1]], result["structuredContent"]["result"])
        self.assertEqual(baseline, len(server.handles))
        self.assertIn("getNavigationNeighbors", mcp.MCP_ALLOWED_HANDLE_METHODS["CMap"])
        for mutation in ("registerNavigationEdge", "unregisterNavigationEdgesForObject"):
            self.assertNotIn(mutation, mcp.MCP_ALLOWED_HANDLE_METHODS["CMap"])
        neighbors.append(SimpleNamespace(x="bad", y=8, z=1))
        result = server._engine_handle_call(
            {"handle": map_handle["__handle__"], "method": "getNavigationNeighbors", "args": [source_handle]}
        )
        self.assertTrue(result["isError"])
        self.assertEqual(baseline, len(server.handles))

    def testCanStepReleasesItsTemporaryCoordinatesOnSuccessAndFailure(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                driver = self.driver()
                point = {"__handle__": "coords"}
                driver._coordinateHandle = Mock(return_value=point)
                driver._ephemeral_handles.add("coords")
                driver._rawCall.side_effect = RuntimeError("native failed") if failure else None
                driver._rawCall.return_value = True
                if failure:
                    with self.assertRaisesRegex(RuntimeError, "native failed"):
                        driver.canStep((5, 6, 0))
                else:
                    self.assertTrue(driver.canStep((5, 6, 0)))
                driver._coordinateHandle.assert_called_once_with((5, 6, 0))
                driver._rawCall.assert_called_once_with(driver.game_map, "canStep", point)
                driver.harness._mcp_tool.assert_called_once_with(
                    None, "engine_release_handles", {"handles": ["coords"]}
                )
                self.assertFalse(driver._ephemeral_handles)

    def testNavigateCoordsReachesTargetRatherThanStoppingAdjacent(self):
        driver = self.driver()
        position = [0, 0, 0]
        driver.coords = lambda handle=None: tuple(position)
        driver._coordinateHandle = Mock(return_value={"__handle__": "point"})
        controller = {"__handle__": "controller"}
        driver._rawCall.side_effect = lambda handle, method, *args: (
            controller if method == "getController" else [] if method == "getNavigationNeighbors" else 0
        )

        def advance():
            position[0] += 1

        driver.tick = Mock(side_effect=advance)
        driver.step = Mock(side_effect=AssertionError("Ordinary navigation switched to legacy adjacent steps"))
        driver.snapshot = Mock(side_effect=AssertionError("Unexpected eager snapshot"))
        driver.navigateCoords((3, 0, 0))
        self.assertEqual((3, 0, 0), driver.coords())
        self.assertEqual(3, driver.tick.call_count)
        driver.snapshot.assert_not_called()
        driver.step.assert_not_called()
        self.assertEqual(1, sum(call.args[1] == "setTarget" for call in driver._rawCall.call_args_list))

    def testPursuitCommitsApproachAcrossAlternatingActualNpcCoordinates(self):
        # The b920 CI trace showed this exact parallel two-cell oscillation at Victor's courtyard.
        driver = self.driver()
        position, enemy = [46, 99, 0], [47, 100, 0]
        actor, controller = {"__handle__": "leader"}, {"__handle__": "controller"}
        state = {"alive": True, "path": [], "targets": [], "turns": 0}
        driver.object = Mock(side_effect=lambda name, required=True: actor if state["alive"] else None)
        driver.coords = lambda handle=None: tuple(enemy if handle == actor else position)
        driver.snapshot = Mock(return_value={"coords": position})
        driver._traversedTarget = Mock(return_value=False)

        def rawCall(handle, method, *args):
            if method == "getController":
                return controller
            if method == "getCoords":
                return {"__handle__": "coords", "coords": tuple(enemy)}
            if method == "setTarget":
                target = args[-1]["coords"]
                state["targets"].append(target)
                path, cursor = [], list(position)
                for axis in (0, 1):
                    while cursor[axis] != target[axis]:
                        cursor[axis] += 1 if cursor[axis] < target[axis] else -1
                        path.append(tuple(cursor))
                state["path"] = path
                return
            raise AssertionError(method)

        def advance():
            state["turns"] += 1
            enemy[0] = 46 if enemy[0] == 47 else 47
            if state["path"]:
                arrival = state["path"].pop(0)
                if arrival == tuple(enemy):
                    state["alive"] = False
                    state["path"].clear()  # Native combat restores the player's pre-step origin.
                else:
                    position[:] = arrival

        driver._rawCall.side_effect = rawCall
        driver.tick = Mock(side_effect=advance)
        driver.step = Mock(side_effect=AssertionError("Pursuit bypassed the native controller"))
        driver.navigateTo("cultLeaderQuest")
        self.assertFalse(state["alive"])
        self.assertEqual(2, state["turns"])
        self.assertEqual([(47, 100, 0)], state["targets"])
        driver.step.assert_not_called()

    def testCoordinateNavigationRetargetsAfterCombatInterruptsTheNativePath(self):
        driver = self.driver()
        position = [18, 53, 0]
        state = {"path": False, "enemyAlive": True}
        controller = {"__handle__": "controller"}
        driver.coords = lambda handle=None: tuple(position)
        driver._coordinateHandle = lambda coords: {"__handle__": "point", "coords": tuple(coords)}

        def rawCall(handle, method, *args):
            if method == "getController":
                return controller
            if method == "setTarget":
                self.assertEqual((19, 53, 0), args[-1]["coords"])
                state["path"] = True

        def advance():
            if not state["path"]:
                return
            if state["enemyAlive"]:
                # CCreature::afterMove restores the origin; CMap::move interrupts the controller.
                state.update(enemyAlive=False, path=False)
            else:
                position[0] += 1

        driver._rawCall.side_effect = rawCall
        driver.tick = Mock(side_effect=advance)
        driver.step = Mock(side_effect=AssertionError("Navigation bypassed the native controller"))
        driver.snapshot = Mock(return_value={"coords": [18, 53, 0]})
        driver.navigateCoords((19, 53, 0))
        self.assertFalse(state["enemyAlive"])
        self.assertEqual((19, 53, 0), driver.coords())
        self.assertEqual(2, driver.tick.call_count)
        self.assertEqual(2, sum(call.args[1] == "setTarget" for call in driver._rawCall.call_args_list))
        driver.step.assert_not_called()
        driver.snapshot.assert_not_called()

    def testBlockedCoordinateNavigationKeepsItsFiniteStallBudget(self):
        driver = self.driver()
        controller = {"__handle__": "controller"}
        driver.coords = lambda handle=None: (18, 53, 0)
        driver._coordinateHandle = Mock(return_value={"__handle__": "point"})
        driver._rawCall.side_effect = lambda handle, method, *args: controller if method == "getController" else None
        driver.tick = Mock()
        driver.snapshot = Mock(return_value={"map": "test"})
        with self.assertRaisesRegex(AssertionError, "Native navigation stalled"):
            driver.navigateCoords((19, 53, 0))
        self.assertEqual(24, driver.tick.call_count)
        self.assertEqual(24, sum(call.args[1] == "setTarget" for call in driver._rawCall.call_args_list))

    def testNavigateToRecognizesPortalAfterEnteringTarget(self):
        driver = self.driver()
        portal, controller, target = ({"__handle__": identity} for identity in ("portal", "controller", "target"))
        position = [0, 0, 0]
        driver.object = Mock(return_value=portal)
        driver._coordinateHandle = Mock(return_value=target)
        driver.coords = lambda handle=None: (1, 0, 0) if handle == portal else tuple(position)
        driver._rawCall.side_effect = lambda handle, method, *args: {
            "getController": controller,
            "getCoords": target,
            "setTarget": None,
            "getNavigationNeighbors": [(9, 0, 1)],
        }[method]

        def enterPortal():
            position[:] = (9, 0, 1)

        driver.tick = Mock(side_effect=enterPortal)
        driver.snapshot = Mock(side_effect=AssertionError("Unexpected eager snapshot"))
        driver.navigateTo("portal")
        self.assertEqual((9, 0, 1), driver.coords())
        driver.tick.assert_called_once()
        driver.snapshot.assert_not_called()
        targets = [action for action in driver.actions if action.get("method") == "setTarget"]
        self.assertEqual([(1, 0, 0)], [action["targetCoordinates"] for action in targets])
        self.assertFalse(driver._coordinate_values)

    def testStepClearsStaleTargetAtActualPortalArrivalBeforeTurn(self):
        for arrival in ((1, 0, 0), (9, 0, 1)):
            with self.subTest(arrival=arrival):
                driver = self.driver()
                position = [0, 0, 0]
                controller = {"__handle__": "controller"}
                driver.coords = lambda handle=None: tuple(position)
                driver.recover = Mock()
                driver.pump = Mock()
                driver._validateMovement = Mock()
                driver._coordinateHandle = lambda coords: {"__handle__": "point", "coords": coords}
                targets = []

                def rawCall(handle, method, *args):
                    if method == "moveTo":
                        position[:] = arrival
                    elif method == "getController":
                        return controller
                    elif method == "setTarget":
                        targets.append(args[-1]["coords"])

                driver._rawCall.side_effect = rawCall
                driver.tick = Mock(side_effect=lambda: self.assertEqual([arrival], targets))
                driver.step((1, 0, 0))
                driver._validateMovement.assert_called_once_with((0, 0, 0), arrival)
                driver.tick.assert_called_once()

    def testAdjacentCombatPumpsBeforeBoundaryRecoveryAndNextNativeMapTurn(self):
        driver = self.driver()
        position, events, state = [0, 0, 0], [], {"turn": 0}
        controller, point, loop = ({"__handle__": name} for name in ("controller", "point", "loop"))
        driver.coords = lambda handle=None: tuple(position)
        driver.recover = Mock()
        driver.assertSurvival = Mock()
        driver.refresh = Mock()
        driver._captureHuntMovement = Mock()
        driver._validateMovement = Mock()
        driver._coordinateHandle = Mock(return_value=point)
        driver.engine = Mock(return_value=loop)
        driver._hunt_adapter = SimpleNamespace(recover_before_map_turn=lambda: events.append("boundaryRecovery"))

        def rawCall(handle, method, *args):
            if method == "moveTo":
                position[:] = args
                events.append("moveTo")
            elif method == "getController":
                return controller
            elif method == "run":
                events.append("pump")
            elif method == "getTurn":
                return state["turn"]
            elif method == "move":
                events.append("mapMove")
                state["turn"] += 1

        driver._rawCall.side_effect = rawCall
        driver.step((1, 0, 0))
        self.assertLess(events.index("moveTo"), events.index("pump"))
        self.assertLess(events.index("pump"), events.index("boundaryRecovery"))
        self.assertLess(events.index("boundaryRecovery"), events.index("mapMove"))
        self.assertEqual(1, events.count("boundaryRecovery"))
        self.assertEqual(1, state["turn"])

    def testHuntAdapterUsesLegacyAdjacentRouteOnlyForAnActiveCombatBoundary(self):
        from tests.test_octobogz_mcp import OctobogzMcpWalkthroughTest

        driver = self.driver()
        driver.session = {"proc": object()}
        driver.navigateTo = Mock()
        driver.object = Mock(return_value={"__handle__": "alpha"})
        with patch.object(
            OctobogzMcpWalkthroughTest,
            "defeat",
            lambda instance, name: instance.walkTo(name, allow_removed=True),
        ), patch.object(OctobogzMcpWalkthroughTest, "walkRoute", return_value="adjacent-route") as adjacent, patch(
            "tests.narrative_walkthrough.authoredRegion", return_value=({}, {(0, 0, 0), (1, 0, 0)})
        ):
            driver.hunt("defeat", "alpha")
            driver.navigateTo.assert_called_once_with("alpha")
            adjacent.assert_not_called()
            driver._hunt_adapter.recover_before_map_turn = Mock()
            self.assertEqual("adjacent-route", driver.hunt("defeat", "alpha"))
            adjacent.assert_called_once_with("alpha", allow_removed=True)
            driver.navigateTo.assert_called_once_with("alpha")

    def testLongNavigationReusesDetachedPointAndReleasesConsumedCoordinates(self):
        driver = self.driver()
        point, controller = {"__handle__": "point"}, {"__handle__": "controller"}
        live_coordinates = set()
        state = {"created": 0, "coordinates": 0, "released": 0, "maximumLive": 0}

        def rawCall(handle, method, *args):
            if method == "createObject":
                self.assertEqual(("CMapObject",), args)
                state["created"] += 1
                return point
            if method == "setNumericProperty":
                self.assertEqual(point, handle)
            elif method == "getCoords":
                state["coordinates"] += 1
                identity = "coords-" + str(state["coordinates"])
                live_coordinates.add(identity)
                state["maximumLive"] = max(state["maximumLive"], len(live_coordinates))
                return {"__handle__": identity}
            elif method in {"setTarget", "canStep"}:
                self.assertIn(args[-1]["__handle__"], live_coordinates)
                return True

        def release(session, method, arguments):
            self.assertEqual("engine_release_handles", method)
            live_coordinates.difference_update(arguments["handles"])
            state["released"] += len(arguments["handles"])

        driver._rawCall = rawCall
        driver.harness._mcp_tool = release
        for index in range(10002):
            coordinates = driver._coordinateHandle((index, 1, 0))
            if index % 2:
                driver.call(controller, "setTarget", driver.player, coordinates)
            else:
                driver.call(driver.game_map, "canStep", coordinates)
            self.assertFalse(driver._ephemeral_handles)
            self.assertFalse(driver._coordinate_values)
        self.assertEqual(1, state["created"])
        self.assertEqual(10002, state["released"])
        self.assertEqual(1, state["maximumLive"])
        self.assertFalse(live_coordinates)

    def testActualDialogResolvesNestedInheritedOptions(self):
        driver = self.driver()
        driver.map_name = "nouraajd"
        states = driver._dialogStates("tavernDialog1")
        options = [entry["properties"] for entry in states["INKEEPER_ABOUT_CULTISTS"]["options"]]
        beer = next(option for option in options if option.get("action") == "sell_beer")
        self.assertEqual("EXIT", beer["nextStateId"])
        self.assertTrue(any(option.get("action") == "asked_about_girl" for option in options))
        self.assertNotIn("ref", beer)

    def testActualNestedDialogActionIsReachableAndExecutedOnce(self):
        driver = self.driver()
        driver.map_name = "nouraajd"
        dialog = {"__handle__": "dialog"}
        driver._rawCall.return_value = dialog
        driver.pump = Mock()
        selected = driver.choose("tavernDialog1", "sell_beer")
        self.assertEqual("sell_beer", selected["action"])
        actions = [call.args for call in driver._rawCall.call_args_list if call.args[1] == "invokeAction"]
        self.assertEqual([(dialog, "invokeAction", "sell_beer")], actions)
        self.assertEqual("EXIT", driver._dialog_positions[("nouraajd", "tavernDialog1")])

    def testActualDialogChecksVisibilityBeforeAction(self):
        driver = self.driver()
        driver.map_name = "ninemarches"
        dialog = {"__handle__": "dialog"}
        driver._rawCall.side_effect = lambda handle, method, *args: dialog if method == "createObject" else False
        driver.pump = Mock()
        with self.assertRaisesRegex(AssertionError, "Authored option is unavailable"):
            driver.choose("knightDialog", "banter", condition="is_joined")
        self.assertFalse(any(call.args[1] == "invokeAction" for call in driver._rawCall.call_args_list))
        driver.pump.assert_not_called()

    def testActualDialogAfterConditionSelectsPostActionState(self):
        for leaves in (False, True):
            with self.subTest(leaves=leaves):
                driver = self.driver()
                driver.map_name = "ninemarches"
                dialog = {"__handle__": "dialog"}
                state = {"acted": False}

                def rawCall(handle, method, *args):
                    if method == "createObject":
                        return dialog
                    if method == "invokeCondition":
                        return args[0] == "is_joined" or (args[0] == "has_left" and state["acted"] and leaves)
                    if method == "invokeAction":
                        state["acted"] = True

                driver._rawCall.side_effect = rawCall
                driver.pump = Mock()
                driver.choose("knightDialog", "banter", condition="is_joined")
                self.assertTrue(state["acted"])
                self.assertEqual(
                    "GONE" if leaves else "LOYAL", driver._dialog_positions[("ninemarches", "knightDialog")]
                )
                methods = [call.args[1:] for call in driver._rawCall.call_args_list]
                self.assertLess(
                    methods.index(("invokeAction", "banter")), methods.index(("invokeCondition", "has_left"))
                )


if __name__ == "__main__":
    unittest.main()
