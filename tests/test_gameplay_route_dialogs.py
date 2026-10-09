# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authored route sequencing regressions, without native gameplay credit."""

import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.gameplay_branch_driver import GameplayBranchDriver
from tests.gameplay_branch_types import RouteCase
from tests import gameplay_routes_ninemarches as marches
from tests import gameplay_routes_nouraajd as nouraajd


def authoredFunction(source, function_name, *, class_id=None, **namespace):
    path = Path(__file__).resolve().parents[1] / source
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if class_id:
        tree = next(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == class_id)
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == function_name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), source, "exec"), namespace)
    return namespace[function_name]


class GameplayRouteDialogTest(unittest.TestCase):
    def driver(self, map_name):
        case = RouteCase("dialog-regression", "unit", (map_name,), ("unit.branch",), lambda d: None)
        driver = GameplayBranchDriver(self, Mock(), None, case, "Warrior", Path("."))
        driver.harness._mcp_engine_call.return_value = True
        driver.map_name = map_name
        driver.game = {"__handle__": "game"}
        driver.game_map = {"__handle__": "map"}
        driver.player = {"__handle__": "player"}
        driver.trace_path = Path(__file__).with_name("absent-unit-native.trace.jsonl")
        driver.pump = Mock()
        driver.record = Mock()
        driver.navigateTo = Mock()
        driver.revisit = Mock()
        return driver

    def deedDriver(self, class_id, *, exp_delta=750, scroll_mode="correct"):
        driver = self.driver("nouraajd")
        driver.class_id = class_id
        state = {"exp": 100, "opened": False, "turn": 0, "coords": (0, 0, 0), "ASKED_ABOUT_GIRL": False}
        for _place, _dialog, _action, _condition, flag, counter in nouraajd.DEEDS.values():
            state.update({flag: False, counter: 0})
        inventory = {"starter": {"__handle__": "starter", "type": "LongSword"}}
        equipped = {"0": inventory["starter"]}
        contacts, attempted, performed = [], [], []
        objects = {
            "nouraajdDoor": {"__handle__": "nouraajdDoor", "type": "CBuilding", "coords": (44, 106, 0)},
            **{
                "nouraajdDoorTrigger"
                + str(index): {
                    "__handle__": "nouraajdDoorTrigger" + str(index),
                    "type": "CMapObject",
                    "coords": (42 + index, 105, 0),
                    "canStep": False,
                }
                for index in range(1, 4)
            },
        }
        for index, (place, *_rest) in enumerate(nouraajd.DEEDS.values()):
            objects.setdefault(place, {"__handle__": place, "type": "CBuilding", "coords": (100 + index, 0, 0)})
        removed, gate_probes = [], []

        def addItem(type_id):
            self.assertEqual("Scroll", type_id)
            if scroll_mode == "missing":
                return
            if scroll_mode == "identity-loss":
                inventory.pop("starter")
            for index in range(2 if scroll_mode == "duplicate" else 1):
                identity = "reward-" + str(index)
                inventory[identity] = {
                    "__handle__": identity,
                    "type": "ManaPotion" if scroll_mode == "wrong" else type_id,
                }
            if scroll_mode == "equipment-change":
                equipped.clear()

        player = SimpleNamespace(
            isPlayer=lambda: True,
            getPlayerClassId=lambda: class_id,
            getBoolProperty=lambda name: state[name],
            incProperty=lambda name, amount: state.__setitem__(name, state[name] + amount),
            setBoolProperty=lambda name, value: state.__setitem__(name, value),
            addExp=lambda amount: state.__setitem__("exp", state["exp"] + exp_delta),
            addItem=addItem,
        )

        def removeAll(predicate):
            for name in list(objects):
                if predicate(SimpleNamespace(getName=lambda name=name: name)):
                    removed.append(name)
                    objects.pop(name)

        game_map = SimpleNamespace(
            getPlayer=lambda: player,
            removeAll=removeAll,
            getObjectByName=lambda name: SimpleNamespace(
                setBoolProperty=lambda key, value: state.__setitem__(key, value)
            ),
            setBoolProperty=lambda name, value: state.__setitem__(name, value),
        )
        show_dialog = Mock()
        game = SimpleNamespace(
            getMap=lambda: game_map,
            getGuiHandler=lambda: SimpleNamespace(showDialog=show_dialog),
            createObject=lambda type_id: type_id,
        )
        door = SimpleNamespace(getGame=lambda: game, getBoolProperty=lambda name: state[name])
        door_trigger = authoredFunction("res/maps/nouraajd/script.py", "trigger", class_id="NouraajdDoorTrigger")
        open_door_method = authoredFunction(
            "res/maps/nouraajd/script.py",
            "open_door",
            class_id="DoorDialog",
            narrative=SimpleNamespace(recordGateApproach=Mock()),
        )
        open_door = lambda: open_door_method(SimpleNamespace(getGame=lambda: game))
        conditions, actions = {}, {}
        for owner, (_place, dialog_id, action, condition, _flag, _counter) in nouraajd.DEEDS.items():
            source_class = {
                "doorDialog": "DoorDialog",
                "tavernDialog1": "TavernDialog1",
                "berenDialog": "BerenDialog",
                "townHallDialog": "TownHallDialog",
            }[dialog_id]
            dialog = SimpleNamespace(getGame=lambda: game)
            condition_method = authoredFunction("res/maps/nouraajd/script.py", condition, class_id=source_class)
            conditions[condition] = lambda dialog=dialog, method=condition_method: method(dialog)
            setattr(dialog, condition, conditions[condition])
            dialog.open_door = open_door
            dialog.asked_about_girl = lambda: state.__setitem__("ASKED_ABOUT_GIRL", True)
            action_method = authoredFunction(
                "res/maps/nouraajd/script.py",
                action,
                class_id=source_class,
                rewardSnapshot=lambda _player: {"exp": state["exp"]},
                showRewardReceipt=Mock(),
            )
            actions[action] = lambda dialog=dialog, method=action_method: method(dialog)
        actions["open_door"] = open_door

        def call(handle, method, *args):
            if method == "createObject":
                return {"__handle__": args[0]}
            if method == "invokeCondition":
                return conditions.get(args[0], lambda: False)()
            if method == "invokeAction":
                if args[0] != "open_door":
                    performed.append(args[0])
                return actions[args[0]]()
            if method in {"getBoolProperty", "getNumericProperty"}:
                if args[0] == "canStep":
                    return handle["canStep"]
                return state[args[0]]
            if method == "getItems":
                return list(inventory.values())
            if method == "getTypeId":
                return class_id if handle == driver.player else handle["type"]
            if method == "getType":
                return "CPlayer" if handle == driver.player else handle["type"]
            if method == "getName":
                return handle["__handle__"]
            if method == "getEquipped":
                return copy.deepcopy(equipped)
            if method == "getTurn":
                return state["turn"]
            raise AssertionError((handle, method, args))

        choose = driver.choose

        def chooseAtContact(dialog_id, action, condition=None, **kwargs):
            if action and action != "open_door":
                landmark = next(value[0] for value in nouraajd.DEEDS.values() if value[2] == action)
                self.assertEqual(landmark, contacts[-1], "Every deed selector probe needs actual landmark contact")
                if action == "brace_gate":
                    self.assertFalse(state["opened"], "The closed-gate dialogue is unavailable after opening")
                    self.assertEqual(("doorDialog",), tuple(call.args[0] for call in show_dialog.call_args_list))
                    gate_probes.append((state["turn"], state["coords"], tuple(objects)))
                attempted.append(action)
            return choose(dialog_id, action, condition, **kwargs)

        def navigateTo(name):
            contacts.append(name)
            state.update(turn=state["turn"] + 1, coords=objects[name]["coords"])
            driver._combat_trace_seq += 1
            driver._player_entries.append(
                {
                    "seq": driver._combat_trace_seq,
                    "map": driver.map_name,
                    "target": driver._nativeObjectIdentity(objects[name]),
                    "cause": driver._nativeObjectIdentity(driver.player),
                    "targetCoords": dict(zip("xyz", state["coords"])),
                    "causeCoords": dict(zip("xyz", state["coords"])),
                }
            )
            if name == "nouraajdDoor":
                door_trigger(None, door, SimpleNamespace(getCause=lambda: player))

        def objectByName(name, required=True):
            if required:
                self.assertIn(name, objects, "Required authored gate or landmark is missing")
            return objects.get(name)

        driver.call = call
        driver.choose = chooseAtContact
        driver.navigateTo = navigateTo
        driver.startCampaign = Mock()
        driver.hunt = Mock()
        driver.object = objectByName
        driver.coords = lambda handle=None: state["coords"] if handle is None else handle["coords"]
        driver.properties = lambda handle: copy.deepcopy({**state, "items": inventory, "equipped": equipped})
        driver.saveAndReload = Mock()
        driver.questNames = lambda completed=False: ["mainQuest"] if completed else []
        driver.check = lambda branch, condition, **evidence: self.assertTrue(condition, branch)
        driver.assertNativeCombatOutcomes = Mock()
        driver._deed_objects = objects
        driver._deed_gate_probes = gate_probes
        driver._deed_removed = removed
        driver._deed_show_dialog = show_dialog
        driver._deed_door_trigger = lambda cause: door_trigger(None, door, SimpleNamespace(getCause=lambda: cause))
        return driver, state, inventory, equipped, attempted, performed, actions

    def testWarriorDeedRejectsMissingAndIncorrectAuthoredExperience(self):
        for exp_delta in (0, 749, 751):
            with self.subTest(exp_delta=exp_delta):
                driver, *_rest = self.deedDriver("Warrior", exp_delta=exp_delta)
                with self.assertRaises(AssertionError):
                    nouraajd.start(driver, deed=True)

    def testWarriorDeedEarnsExactlyOnceAndRemainsUnavailable(self):
        driver, state, *_rest, actions = self.deedDriver("Warrior")
        nouraajd.start(driver, deed=True)
        self.assertEqual(850, state["exp"])
        self.assertEqual(1, state["warrior_barricades"])
        before = copy.deepcopy(state)
        actions["brace_gate"]()
        self.assertEqual(before, state)
        self.assertFalse(driver.condition("doorDialog", "can_brace_gate"))
        self.assertEqual(before, state)

    def testSorcererDeedRejectsMissingWrongDuplicateAndDestructiveScrollRewards(self):
        for scroll_mode in ("missing", "wrong", "duplicate", "identity-loss", "equipment-change"):
            with self.subTest(scroll_mode=scroll_mode):
                driver, *_rest = self.deedDriver("Sorcerer", scroll_mode=scroll_mode)
                with self.assertRaises(AssertionError):
                    nouraajd.performDeed(driver)

    def testSorcererDeedAddsOneOwnedScrollAndPreservesExistingInventoryAndEquipment(self):
        driver, state, inventory, equipped, *_rest, actions = self.deedDriver("Sorcerer")
        nouraajd.performDeed(driver)
        self.assertEqual({"starter", "reward-0"}, set(inventory))
        self.assertEqual("Scroll", inventory["reward-0"]["type"])
        self.assertEqual({"0": inventory["starter"]}, equipped)
        self.assertEqual(850, state["exp"])
        before = (copy.deepcopy(state), copy.deepcopy(inventory), copy.deepcopy(equipped))
        actions["decode_stained_glass_ward"]()
        self.assertEqual(before, (state, inventory, equipped))

    def testEveryDeedRoutePhysicallyRejectsAllOtherClassSelectorsWithoutInvokingActions(self):
        for class_id in nouraajd.DEEDS:
            with self.subTest(class_id=class_id):
                driver, _state, _inventory, _equipped, attempted, performed, _actions = self.deedDriver(class_id)
                with patch.object(nouraajd, "prepareRolf"):
                    nouraajd.deedRoute(driver)
                own_action = nouraajd.DEEDS[class_id][2]
                self.assertEqual([own_action], performed)
                self.assertEqual({value[2] for value in nouraajd.DEEDS.values()}, set(attempted))
                self.assertEqual(5, len(attempted), "Each owner must attempt exactly four unavailable class options")
                self.assertEqual(1, len(driver._deed_gate_probes), "The gate option must be tested only before opening")
                self.assertEqual((1, (44, 106, 0)), driver._deed_gate_probes[0][:2])
                self.assertEqual(
                    {"nouraajdDoorTrigger" + str(index) for index in range(1, 4)}, set(driver._deed_removed)
                )

    def testGateDeedRequiresFreshActualPlayerContactAndAllThreeClosedBlockers(self):
        for corruption in (
            "missing-entry",
            "stale-entry",
            "wrong-player",
            "wrong-door",
            "replaced-door",
            "not-contact",
            "opened",
            "missing-blocker",
            "walkable-blocker",
        ):
            with self.subTest(corruption=corruption):
                driver, state, *_rest = self.deedDriver("Sorcerer")
                navigate = driver.navigateTo

                def corruptContact(name):
                    navigate(name)
                    if corruption == "missing-entry":
                        driver._player_entries.clear()
                    elif corruption == "stale-entry":
                        driver._player_entries[-1]["seq"] = 0
                    elif corruption == "wrong-player":
                        driver._player_entries[-1]["cause"]["name"] = "anotherPlayer"
                    elif corruption == "wrong-door":
                        driver._player_entries[-1]["target"]["name"] = "anotherDoor"
                    elif corruption == "replaced-door":
                        driver._deed_objects["nouraajdDoor"] = {
                            **driver._deed_objects["nouraajdDoor"],
                            "__handle__": "replacementDoor",
                        }
                    elif corruption == "not-contact":
                        state["coords"] = (44, 107, 0)
                    elif corruption == "opened":
                        state["opened"] = True
                    elif corruption == "missing-blocker":
                        driver._deed_objects.pop("nouraajdDoorTrigger1")
                    elif corruption == "walkable-blocker":
                        driver._deed_objects["nouraajdDoorTrigger1"]["canStep"] = True

                driver.navigateTo = corruptContact
                with self.assertRaises(AssertionError):
                    nouraajd.start(driver, deed=True)
                self.assertFalse(state["decoded_stained_glass_ward"])

    def testAuthoredDoorTriggerPresentsClosedGateOnlyForActualPlayerAndOpeningConsumesBlockers(self):
        driver, state, *_rest, actions = self.deedDriver("Sorcerer")
        driver._deed_door_trigger(SimpleNamespace(isPlayer=lambda: False))
        driver._deed_show_dialog.assert_not_called()
        driver._deed_door_trigger(SimpleNamespace(isPlayer=lambda: True))
        driver._deed_show_dialog.assert_called_once_with("doorDialog")
        actions["open_door"]()
        self.assertTrue(state["opened"])
        self.assertEqual(3, len(driver._deed_removed))
        driver._deed_show_dialog.reset_mock()
        driver._deed_door_trigger(SimpleNamespace(isPlayer=lambda: True))
        driver._deed_show_dialog.assert_not_called()

    def testOtherClassWarriorProbeAfterOpeningIsNotAnAuthoredGateVisit(self):
        driver, _state, *_rest = self.deedDriver("Sorcerer")
        nouraajd.start(driver)
        with self.assertRaisesRegex(AssertionError, "closed-gate dialogue is unavailable"):
            driver.choose("doorDialog", "brace_gate", condition="can_brace_gate")

    def testRejectedOtherClassSelectorCannotChangePlayerDeedTurnOrDialogState(self):
        for mutation in (
            "exp",
            "braced_nouraajd_gate",
            "warrior_barricades",
            "turn",
            "cursor",
            "opened",
            "door",
            "blocker",
            "canStep",
        ):
            with self.subTest(mutation=mutation):
                driver, state, *_rest = self.deedDriver("Sorcerer")
                choose = driver.choose

                def corruptRejection(dialog_id, action, condition=None, **kwargs):
                    if action == "brace_gate":
                        if mutation == "cursor":
                            driver._dialog_positions[(driver.map_name, dialog_id)] = "WARRIOR_GATE"
                        elif mutation == "door":
                            driver._deed_objects["nouraajdDoor"] = {
                                **driver._deed_objects["nouraajdDoor"],
                                "__handle__": "replacementDoor",
                            }
                        elif mutation == "blocker":
                            driver._deed_objects.pop("nouraajdDoorTrigger1")
                        elif mutation == "canStep":
                            driver._deed_objects["nouraajdDoorTrigger1"]["canStep"] = True
                        else:
                            state[mutation] += 1
                        raise AssertionError("Authored option is unavailable")
                    return choose(dialog_id, action, condition, **kwargs)

                driver.choose = corruptRejection
                expected = "Rejected gate deed changed the closed-gate state" if mutation == "door" else ""
                with patch.object(nouraajd, "prepareRolf"), self.assertRaisesRegex(AssertionError, expected):
                    nouraajd.deedRoute(driver)

    def testDeedRouteStillRejectsLostPersistedCounter(self):
        driver, state, *_rest = self.deedDriver("Warrior")
        driver.saveAndReload = lambda label: state.__setitem__("warrior_barricades", 0)
        with patch.object(nouraajd, "prepareRolf"), self.assertRaisesRegex(AssertionError, "persisted"):
            nouraajd.deedRoute(driver)

    def testThreatenedGateRouteClosesRejectionBeforeOpeningTheGate(self):
        driver = self.driver("nouraajd")
        driver.startCampaign = Mock()
        driver.hunt = Mock()
        driver.object = Mock(return_value={"__handle__": "door"})
        actions = []

        def call(handle, method, *args):
            if method == "createObject":
                return {"__handle__": args[0]}
            if method == "invokeAction":
                actions.append(args[0])
            elif method == "getBoolProperty":
                return "open_door" in actions
            elif method == "invokeCondition":
                return False

        driver.call = call
        nouraajd.start(driver, gate="threatened")
        self.assertEqual(["threatenGate", "open_door"], actions)
        self.assertEqual("EXIT", driver._dialog_positions[("nouraajd", "doorDialog")])

    def testCompanionRouteClosesAcceptanceReminderAndRecruitmentBeforeBanter(self):
        for item_first in (False, True):
            with self.subTest(item_first=item_first):
                driver = self.driver("ninemarches")
                state = {"started": False, "joined": False, "item": False, "gift": 0, "reputation": 0}
                actions = []

                def call(handle, method, *args):
                    if method == "createObject":
                        return {"__handle__": args[0]}
                    if method == "getNumericProperty":
                        return state[args[0]]
                    if method == "invokeCondition":
                        return {
                            "not_met": not state["started"],
                            "can_recruit": state["started"] and state["item"] and not state["joined"],
                            "is_joined": state["joined"],
                            "has_left": False,
                            "questInProgress": state["started"] and not state["item"] and not state["joined"],
                        }[args[0]]
                    if method == "invokeAction":
                        actions.append(args[0])
                        if args[0] == "start":
                            state["started"] = True
                        elif args[0] == "recruit":
                            state["joined"] = True
                            state["reputation"] += 2
                            state["gift"] += 1

                driver.call = call
                driver.navigateTo = lambda name, **kwargs: state.update(item=True) if name == "banditCache" else None
                driver.flag = lambda name: state["started"]
                driver.count = lambda item: int(state["item"]) if item == "banditLedger" else state["gift"]
                driver.questNames = lambda completed=False: ["haldaQuest"] if state["joined"] and completed else []
                with patch.object(marches, "verifyJournals"):
                    marches.recruit(driver, "halda", item_first=item_first)
                driver.choose("knightDialog", "banter", condition="is_joined")
                driver.select("knightDialog", "LOYAL", 0)
                self.assertEqual(["start", "recruit", "banter"], actions)
                self.assertEqual("EXIT", driver._dialog_positions[("ninemarches", "knightDialog")])

    def testDirectVictorRouteUsesTheAuthoredCourtyardPathState(self):
        driver = self.driver("nouraajd")
        driver.object = Mock(return_value={"__handle__": "tavern"})
        actions = []

        def call(handle, method, *args):
            if method == "createObject":
                return {"__handle__": args[0]}
            if method == "getNumericProperty":
                return 0
            if method == "getTurn":
                return 51
            if method == "invokeCondition":
                return False
            if method == "invokeAction":
                actions.append(args[0])

        driver.call = call
        driver.flag = lambda name: "talked_to_victor" in actions
        driver.string = lambda name: "encounter_active" if "spawn_cultists" in actions else "met_victor"
        nouraajd.meetVictor(driver, "forceful", direct=True, ask_girl=False)
        self.assertEqual(["confrontVictorForcefully", "talked_to_victor", "spawn_cultists"], actions)
        self.assertEqual("EXIT", driver._dialog_positions[("nouraajd", "tavernDialog2")])

    def testCompletedContractCannotReopenUntilAcknowledgementExits(self):
        driver = self.driver("nouraajd")
        driver.call = lambda handle, method, *args: (
            {"__handle__": args[0]}
            if method == "createObject"
            else args[0] == "contract_completed" if method == "invokeCondition" else None
        )
        driver.choose("dialog", "accept_quest", condition="contract_completed")
        with self.assertRaisesRegex(AssertionError, "No reachable authored dialog option"):
            driver.choose("dialog", "accept_quest", condition="contract_completed")
        driver.select("dialog", "COMPLETED_THANKS", 0)
        driver.choose("dialog", "accept_quest", condition="contract_completed")
        self.assertEqual("COMPLETED_THANKS", driver._dialog_positions[("nouraajd", "dialog")])

    def testVictorFleeUsesTheTurnObservedByTheAuthoredTimer(self):
        state = {"turn": 84, "quest": "encounter_active", "position": (60, 110, 0), "leader": True}
        quest = SimpleNamespace(
            get_state=lambda name: state["quest"],
            mark_victor_bad_end=lambda: state.update(quest="bad_end"),
        )
        game_map = SimpleNamespace(
            getNumericProperty=lambda name: 10,
            getTurn=lambda: state["turn"],
            getGame=lambda: None,
            getObjects=lambda: [{"__handle__": "player"}] + ([{"__handle__": "leader"}] if state["leader"] else []),
        )
        expire = authoredFunction(
            "res/maps/nouraajd/script.py",
            "_expire_victor_search",
            _get_quest_system=lambda game_map: quest,
            _clear_victor_encounter=lambda game_map: state.update(leader=False),
            VICTOR_COURTYARD_TIMEOUT_TURNS=75,
            showReader=Mock(),
        )

        def step(target):
            state["position"] = target
            # CMap::move dispatches synchronous onTurn callbacks before turn++.
            expire(game_map)
            state["turn"] += 1

        def call(handle, method, *args):
            if handle is game_map:
                return getattr(handle, method)(*args)
            return {"getType": "CCreature", "isAlive": True, "isNpc": False, "getStringProperty": ""}[method]

        driver = SimpleNamespace(
            test=self,
            game_map=game_map,
            player={"__handle__": "player"},
            number=lambda name: 10,
            call=call,
            coords=lambda handle=None: (45, 100, 0) if handle else state["position"],
            object=lambda name, required=False: "leader" if name == "cultLeaderQuest" and state["leader"] else None,
            canStep=lambda target: True,
            step=step,
            string=lambda name: state["quest"],
        )
        nouraajd.fleeCourtyardUntil(driver, 75, allow_timeout=True)
        self.assertEqual(85, state["turn"])
        self.assertEqual("encounter_active", state["quest"])
        self.assertTrue(state["leader"])
        nouraajd.fleeCourtyardUntil(driver, 76, allow_timeout=True)
        self.assertEqual(86, state["turn"])
        self.assertEqual("bad_end", state["quest"])
        self.assertFalse(state["leader"])

    def testVictorFleePrefersTheLongRunwayAtTheObservedSouthernBoundary(self):
        from tests.narrative_walkthrough import authoredRegion

        document = json.loads(
            (Path(__file__).resolve().parents[1] / "res/maps/nouraajd/map.json").read_text(encoding="utf-8")
        )
        layer = next(value for value in document["layers"] if value["type"] == "tilelayer")
        bounds = (int(layer["properties"]["xBound"]), int(layer["properties"]["yBound"]))
        self.assertEqual((199, 120), bounds)
        _objects, tiles = authoredRegion("nouraajd")
        self.assertTrue({(x, 120, 0) for x in range(44, 101)} <= tiles)
        self.assertFalse(any(y == 120 and x >= 44 for x, y, _z in _objects.values()))

        for x_first in (True, False):
            with self.subTest(x_first=x_first):
                # Actual 514c7300/job113861450475: end of turn791, seq19041..19057.
                state = {"turn": 792, "quest": "encounter_active", "position": (44, 120, 0)}
                actors = {
                    "cultLeaderQuest": (44, 117, 0),
                    "victorCultist3": (44, 116, 0),
                    "victorCultist4": (44, 118, 0),
                }
                steps = []
                quest = SimpleNamespace(
                    get_state=lambda name: state["quest"],
                    mark_victor_bad_end=lambda: state.update(quest="bad_end"),
                )
                game_map = SimpleNamespace(
                    getNumericProperty=lambda name: 772,
                    getTurn=lambda: state["turn"],
                    getGame=lambda: None,
                    getObjects=lambda: [{"__handle__": "player"}] + [{"__handle__": name} for name in actors],
                )
                expire = authoredFunction(
                    "res/maps/nouraajd/script.py",
                    "_expire_victor_search",
                    _get_quest_system=lambda game_map: quest,
                    _clear_victor_encounter=lambda game_map: actors.clear(),
                    VICTOR_COURTYARD_TIMEOUT_TURNS=75,
                    showReader=Mock(),
                )

                def step(target):
                    origin = state["position"]
                    self.assertEqual(1, sum(abs(a - b) for a, b in zip(origin, target)))
                    self.assertTrue(canStep(target))
                    planned = {}
                    # A source model of both cardinal chase tie orders, not a native receipt.
                    # Controllers plan against the same pre-turn player cell; either apply
                    # order is harmless only while no planned pursuer can enter that cell.
                    for name, position in actors.items():
                        point = list(position)
                        for axis in ((0, 1) if x_first else (1, 0)):
                            if point[axis] != origin[axis]:
                                point[axis] += 1 if point[axis] < origin[axis] else -1
                                break
                        planned[name] = tuple(point)
                        self.assertNotEqual(origin, planned[name], "A source pursuit reached the stationary hero")
                    actors.update(planned)
                    state["position"] = target
                    self.assertTrue(
                        all(sum(abs(a - b) for a, b in zip(target, point)) >= 2 for point in actors.values())
                    )
                    steps.append(target)
                    expire(game_map)
                    state["turn"] += 1

                def canStep(target):
                    return 0 <= target[0] <= bounds[0] and 0 <= target[1] <= bounds[1] and target in tiles

                def call(handle, method, *args):
                    if handle is game_map:
                        return getattr(handle, method)(*args)
                    return {"getType": "CCreature", "isAlive": True, "isNpc": False, "getStringProperty": ""}[method]

                driver = SimpleNamespace(
                    test=self,
                    game_map=game_map,
                    player={"__handle__": "player"},
                    number=lambda name: 772,
                    call=call,
                    coords=lambda handle=None: actors[handle["__handle__"]] if handle else state["position"],
                    object=lambda name, required=False: name if name in actors else None,
                    canStep=canStep,
                    step=step,
                    string=lambda name: state["quest"],
                )
                nouraajd.fleeCourtyardUntil(driver, 74)
                self.assertEqual((98, 120, 0), state["position"])
                self.assertEqual((45, 120, 0), steps[0], "Equal-safe escape must use the longer eastern runway")
                self.assertEqual(846, state["turn"])
                self.assertEqual("encounter_active", state["quest"])
                nouraajd.fleeCourtyardUntil(driver, 75, allow_timeout=True)
                self.assertEqual("encounter_active", state["quest"])
                self.assertEqual(847, state["turn"])
                nouraajd.fleeCourtyardUntil(driver, 76, allow_timeout=True)
                self.assertEqual((100, 120, 0), state["position"])
                self.assertEqual("bad_end", state["quest"])
                self.assertEqual(848, state["turn"])
                self.assertEqual(56, len(steps))
                self.assertFalse(actors)

    def fleeRosterFixture(self, actors, *, affiliation=""):
        state = {"actors": actors, "affiliation": affiliation, "position": (66, 107, 0)}
        calls, coordinate_reads = [], []
        game_map, player = {"__handle__": "map"}, {"__handle__": "player"}

        def call(handle, method, *args):
            identity = handle["__handle__"]
            calls.append((identity, method, args))
            if identity == "map":
                self.assertEqual("getObjects", method)
                return [{"__handle__": "player", "__type__": "CPlayer"}] + [
                    {
                        "__handle__": name,
                        "__type__": actor.get("type", "CCreature"),
                        "pythonMethods": actor.get("pythonMethods", []),
                    }
                    for name, actor in state["actors"].items()
                ]
            if identity == "player":
                self.assertEqual(("getStringProperty", ("affiliation",)), (method, args))
                return state["affiliation"]
            actor = state["actors"][identity]
            values = {
                "getType": actor.get("type", "CCreature"),
                "getName": actor.get("name", identity),
                "isAlive": actor.get("alive", True),
                "isNpc": actor.get("npc", False),
                "getStringProperty": actor.get("affiliation", ""),
            }
            if method == "getStringProperty":
                self.assertEqual(("affiliation",), args)
            return values[method]

        def coords(handle=None):
            if handle is None:
                return state["position"]
            identity = handle["__handle__"]
            coordinate_reads.append(identity)
            return state["actors"][identity]["coords"]

        driver = SimpleNamespace(test=self, game_map=game_map, player=player, call=call, coords=coords)
        return driver, state, calls, coordinate_reads

    def testVictorFleeAvoidsThePritzPursuitConeDespiteNativePassability(self):
        # 28ba9d9e/job113882090624: a Pritz victory restored (66,107), then the
        # leader reached that stationary hero. The earlier three-cell separation
        # below exercises prevention; it does not claim a reconstructed trace.
        driver, state, calls, coordinate_reads = self.fleeRosterFixture(
            {
                "cultLeaderQuest": {"coords": (62, 105, 0)},
                "pritz": {"coords": (67, 107, 0)},
            }
        )
        state.update(turn=805, position=(64, 107, 0), quest="encounter_active", steps=[])
        roster_call = driver.call

        def call(handle, method, *args):
            if handle is driver.game_map and method == "getTurn":
                return state["turn"]
            return roster_call(handle, method, *args)

        def step(target):
            state["steps"].append(target)
            state.update(position=target, turn=state["turn"] + 1)

        driver.call = call
        driver.number = lambda name: 777
        driver.object = lambda name, required=False: {"__handle__": name} if name == "cultLeaderQuest" else None
        driver.canStep = lambda target: True
        driver.step = step
        driver.string = lambda name: state["quest"]
        self.assertTrue(driver.canStep((67, 107, 0)), "Native walkability does not reject a hostile occupied cell")
        nouraajd.fleeCourtyardUntil(driver, 29)
        self.assertEqual([(64, 108, 0)], state["steps"])
        self.assertEqual((806, "encounter_active"), (state["turn"], state["quest"]))
        self.assertEqual(1, sum(method == "getObjects" for _identity, method, _args in calls))
        self.assertEqual(["cultLeaderQuest", "pritz"], coordinate_reads)

    def testVictorFleeSnapshotSupportsPythonCreaturesAndTheNativeAffiliationPredicate(self):
        driver, state, calls, coordinate_reads = self.fleeRosterFixture(
            {
                "pritz": {"coords": (67, 107, 0)},
                "pythonRaider": {
                    "coords": (64, 106, 0),
                    "type": "AuthoredPythonRaider",
                    "pythonMethods": [{"name": "isAlive", "signature": "(self)"}],
                },
                "dead": {"coords": (68, 107, 0), "alive": False},
                "neutral": {"coords": (69, 107, 0), "npc": True},
                "ally": {"coords": (70, 107, 0), "affiliation": "wardens"},
                "elsewhere": {"coords": (66, 107, 1)},
                "building": {"coords": (66, 107, 0), "type": "CBuilding"},
            },
            affiliation="wardens",
        )
        cache = {}
        self.assertEqual([(67, 107, 0), (64, 106, 0)], nouraajd.fleeHostileCoords(driver, cache))
        self.assertEqual(["pritz", "pythonRaider", "elsewhere"], coordinate_reads)
        self.assertFalse(any(identity == "building" and method == "isAlive" for identity, method, _args in calls))
        state["affiliation"] = ""
        state["actors"]["ally"]["affiliation"] = ""
        coordinate_reads.clear()
        self.assertEqual([(67, 107, 0), (64, 106, 0), (70, 107, 0)], nouraajd.fleeHostileCoords(driver, cache))
        self.assertIn("ally", coordinate_reads, "Two empty affiliations do not make native creatures allied")
        self.assertEqual(len(state["actors"]), sum(method == "getType" for _identity, method, _args in calls))

    def testVictorFleeRevalidatesMutableActorFlagsAndReplacementHandlesEveryStep(self):
        driver, state, calls, coordinate_reads = self.fleeRosterFixture(
            {
                "old": {"coords": (67, 107, 0), "name": "sameAuthoredName"},
                "changing": {"coords": (68, 107, 0), "npc": True},
            },
            affiliation="wardens",
        )
        cache = {}
        self.assertEqual([(67, 107, 0)], nouraajd.fleeHostileCoords(driver, cache))
        state["actors"]["old"]["alive"] = False
        state["actors"]["changing"].update(npc=False, affiliation="wardens")
        self.assertEqual([], nouraajd.fleeHostileCoords(driver, cache))
        state["actors"]["changing"].update(affiliation="raiders", coords=(69, 108, 0))
        self.assertEqual([(69, 108, 0)], nouraajd.fleeHostileCoords(driver, cache))
        self.assertEqual(2, sum(method == "getType" for _identity, method, _args in calls))
        del state["actors"]["old"]
        state["actors"]["new"] = {"coords": (70, 108, 0), "name": "sameAuthoredName"}
        coordinate_reads.clear()
        self.assertEqual([(69, 108, 0), (70, 108, 0)], nouraajd.fleeHostileCoords(driver, cache))
        self.assertNotIn("old", cache)
        self.assertIn("new", cache)
        self.assertEqual(["changing", "new"], coordinate_reads)
        self.assertEqual(3, sum(method == "getType" for _identity, method, _args in calls))

    def testVictorFleeFailsBeforeMovementIfItsRequiredEncounterActorsAreAbsent(self):
        driver, _state, _calls, coordinate_reads = self.fleeRosterFixture({"pritz": {"coords": (67, 107, 0)}})
        roster_call = driver.call
        driver.call = lambda handle, method, *args: (
            807 if handle is driver.game_map and method == "getTurn" else roster_call(handle, method, *args)
        )
        driver.number = lambda name: 777
        driver.object = lambda name, required=False: None
        driver.step = Mock()
        with self.assertRaisesRegex(AssertionError, "real timed encounter must remain present"):
            nouraajd.fleeCourtyardUntil(driver, 31)
        driver.step.assert_not_called()
        self.assertEqual([], coordinate_reads)

    def testVictorFleeRejectsAnOversizedCreatureRosterBeforeReadingCoordinates(self):
        driver, _state, calls, coordinate_reads = self.fleeRosterFixture(
            {"actor" + str(index): {"coords": (index, 0, 0)} for index in range(64)}
        )
        with self.assertRaisesRegex(AssertionError, "creature roster exceeds 64") as raised:
            nouraajd.fleeHostileCoords(driver, {})
        self.assertIn("actor63", str(raised.exception))
        self.assertEqual([], coordinate_reads)
        self.assertFalse(any(method in {"isAlive", "isNpc"} for _identity, method, _args in calls))

    def testVictorFleeRetainsEveryHostileWithinTheCreatureEnvelope(self):
        for count in (44, 63):
            with self.subTest(hostiles=count):
                driver, _state, calls, coordinate_reads = self.fleeRosterFixture(
                    {"actor" + str(index): {"coords": (index, 0, 0)} for index in range(count)}
                )
                self.assertEqual([(index, 0, 0) for index in range(count)], nouraajd.fleeHostileCoords(driver, {}))
                self.assertEqual(count, len(coordinate_reads))
                self.assertEqual(count, sum(method == "isAlive" for _identity, method, _args in calls))

    def testVictorFleeRejectsAnAdjacentPritzBeforeItsCombatCanRestoreTheDepartureCell(self):
        driver, state, _calls, _coordinate_reads = self.fleeRosterFixture(
            {
                "cultLeaderQuest": {"coords": (62, 105, 0)},
                "pritz": {"coords": (67, 107, 0)},
            }
        )
        state.update(turn=807, quest="encounter_active")
        roster_call = driver.call
        driver.call = lambda handle, method, *args: (
            state["turn"] if handle is driver.game_map and method == "getTurn" else roster_call(handle, method, *args)
        )
        driver.number = lambda name: 777
        driver.object = lambda name, required=False: {"__handle__": name} if name == "cultLeaderQuest" else None
        driver.canStep = lambda target: True
        driver.step = Mock(side_effect=lambda target: state.update(turn=809, quest="good_end"))
        driver.string = lambda name: state["quest"]
        with self.assertRaisesRegex(AssertionError, "No natural escape step remains"):
            nouraajd.fleeCourtyardUntil(driver, 31)
        driver.step.assert_not_called()

    def testVictorFleeRejectsAMapRosterThatLostTheActualPlayer(self):
        driver, _state, _calls, coordinate_reads = self.fleeRosterFixture({"cultLeaderQuest": {"coords": (62, 105, 0)}})
        driver.call = lambda handle, method, *args: [{"__handle__": "cultLeaderQuest"}]
        with self.assertRaisesRegex(AssertionError, "active player in the map roster"):
            nouraajd.fleeHostileCoords(driver, {})
        self.assertEqual([], coordinate_reads)

    def testPairedPortalsReenterTheArrivalObjectBeforeTestingItsReverse(self):
        driver = self.driver("ninemarches")
        definitions = json.loads(
            (Path(__file__).resolve().parents[1] / "res/maps/ninemarches/config.json").read_text(encoding="utf-8")
        )
        names = ("monolithHub", "monolithCoast", "monolithAsh", "monolithCold")
        positions = {name: (10 * index, 0, 0) for index, name in enumerate(names, 1)}
        state = {"position": (0, 0, 0)}
        entered = []
        on_enter = authoredFunction(
            "res/plugins/object.py", "onEnter", class_id="WayPoint", active_waypoint_causes=set()
        )

        class Creature:
            def setCoords(self, coords):
                state.update(position=coords)

        creature = Creature()
        event = SimpleNamespace(getCause=lambda: creature)

        def navigateTo(name, **kwargs):
            if state["position"] == positions[name]:
                return
            state["position"] = positions[name]
            entered.append(name)
            exit_name = definitions[name]["properties"]["exit"]
            on_enter(SimpleNamespace(getExit=lambda: positions[exit_name]), event)

        driver.object = lambda name: name
        driver.coords = lambda handle=None: positions[handle] if handle else state["position"]
        driver.navigateCoords = lambda coords: state.update(position=coords)
        driver.navigateTo = navigateTo
        driver._coordinateHandle = lambda coords: coords
        driver.call = lambda handle, method, *args: True if method == "canStep" else None
        driver.revisit = lambda name: GameplayBranchDriver.revisit(driver, name)
        driver.check = lambda branch_id, condition, **evidence: self.assertTrue(condition, branch_id)
        with patch.object(marches, "start"):
            marches.portals(driver)
        self.assertEqual(list(names), entered)
