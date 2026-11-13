# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual selected early Tamoko methods with source-model objects; no engine or city generation."""

import ast
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from quest_state import mapQuest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "res/maps/baldursGate/script.py"
BUILDER = ROOT / "scripts/build_baldurs_gate_city.py"
DIALOGS = ROOT / "scripts/build_baldurs_gate_city_dialogs.py"
INVENTORY = ROOT / "tests/fixtures/baldurs_gate_city_tamoko_dialogue.json"
QUESTS = ROOT / "tests/fixtures/baldurs_gate_city_quests.json"
FINAL_TEST = ROOT / "tests/test_baldurs_gate_tamoko_final_meeting.py"
ROUTES = ROOT / "tests/gameplay_routes_baldurs_gate.py"
ACTOR = "cityAr0800ScriptActorTamoko"


def selectedQuest():
    text = QUESTS.read_text(encoding="utf-8")
    marker = '"id": "cythandriaDiary"'
    if not (text.count(marker) == 1):
        raise AssertionError("Source-model precondition failed")
    start = text.rfind("{", 0, text.index(marker))
    row, count = json.JSONDecoder().raw_decode(text[start : start + 8192])
    if not (count < 8192 and row["id"] == "cythandriaDiary" and (row["acceptEffects"] == {})):
        raise AssertionError("Source-model precondition failed")
    return row


@lru_cache(maxsize=4)
def selectedCode(source):
    tree = ast.parse(source)
    load = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load")
    helpers = {
        "decodeData",
        "questId",
        "firstMatch",
        "pairedValues",
        "scheduleSlot",
        "world",
        "hero",
        "clock",
        "custody",
        "read",
        "write",
        "definitions",
        "quest",
        "stage",
        "setStage",
        "matches",
    }
    nodes = [
        deepcopy(node)
        for parent in (tree, load)
        for node in parent.body
        if isinstance(node, ast.FunctionDef) and node.name in helpers
    ]
    classes = {}
    for owner, names in (
        ("BaldursGateCustody", set()),
        ("BaldursGateClock", {"sceneEligible", "relocateActors", "applySchedules"}),
        ("BaldursGateDialog", None),
    ):
        row = next(node for node in load.body if isinstance(node, ast.ClassDef) and node.name == owner)
        if owner == "BaldursGateDialog":
            names = {
                node.name
                for node in row.body
                if isinstance(node, ast.FunctionDef)
                and (
                    "tamoko" in node.name.lower()
                    and "final" not in node.name.lower()
                    or node.name in {"attack", "syncTamokoJournal", "canAcceptQuest", "acceptQuest", "canQuestOutcome"}
                )
            }
            names -= {
                "canAcceptTamokoMercy",
                "acceptTamokoMercy",
                "canQuestTamokoMercyComplete",
                "questTamokoMercyComplete",
                "canQuestTamokoMercyFight",
                "questTamokoMercyFight",
            }
        selected = [deepcopy(node) for node in row.body if isinstance(node, ast.FunctionDef) and node.name in names]
        classes[owner] = [node.name for node in selected]
        nodes.extend(selected)
    table = deepcopy(
        next(node for node in load.body if isinstance(node, ast.FunctionDef) and node.name == "tamokoJournalEntries")
    )
    journal_class = deepcopy(
        next(
            node
            for node in load.body
            if isinstance(node, ast.ClassDef) and node.name == "BaldursGateTamokoJournalQuest"
        )
    )
    journal_class.decorator_list = []
    nodes[:0] = [table, journal_class]
    for node in nodes:
        node.decorator_list = []
    return (
        compile(
            ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
            "selected early Tamoko callbacks",
            "exec",
        ),
        classes,
    )


class SourceObject:
    def __init__(self, game, name="", **values):
        self.game, self.name, self.values, self.game_map = game, name, values, None

    def getGame(self):
        return self.game

    def getMap(self):
        return self.game_map or self.game.getMap()

    def getName(self):
        return self.name

    def getTypeId(self):
        return self.name

    def getStringProperty(self, name):
        return self.values.get(name, "")

    def setStringProperty(self, name, value):
        self.values[name] = value

    def getNumericProperty(self, name):
        return self.values.get(name, 0)

    def setNumericProperty(self, name, value):
        self.values[name] = value

    def getBoolProperty(self, name):
        return bool(self.values.get(name, False))

    def setBoolProperty(self, name, value):
        self.values[name] = value

    def getObjectProperty(self, name):
        return self.values.get(name)

    def setObjectProperty(self, name, value):
        self.values[name] = value

    def globalValue(self, name, scope="GLOBAL"):
        raw = self.game.getMap().getStringProperty("plugin_cityCustodyGlobals") or "city-json:{}"
        return json.loads(raw.removeprefix("city-json:")).get(scope + ":" + name, 0)

    def setGlobal(self, name, scope, value):
        game_map = self.game.getMap()
        raw = game_map.getStringProperty("plugin_cityCustodyGlobals") or "city-json:{}"
        values = json.loads(raw.removeprefix("city-json:"))
        values[scope + ":" + name] = value
        game_map.setStringProperty("plugin_cityCustodyGlobals", "city-json:" + json.dumps(values))

    def journal(self, number, add=True):
        raise AssertionError("Tamoko must use its captured journal projection, not the generic custody callback")

    def captureJournal(self, completed):
        self.setNumericProperty("questJournalVersion", 1)
        self.setStringProperty("questJournalOrigin", "baldursGate")
        self.setBoolProperty("questJournalCompleted", completed)
        for key, value in (
            ("Description", self.getStringProperty("description")),
            ("Objective", self.getObjective()),
            ("Reward", self.getReward()),
            ("Hint", self.getHint()),
        ):
            self.setStringProperty("questJournal" + key, value)

    def getDescription(self):
        return self.getStringProperty("description")

    def getCoords(self):
        return SimpleNamespace(x=self.values.get("x", 0), y=self.values.get("y", 0), z=self.values.get("z", 0))

    def relocateWithoutMoveHooks(self, coords):
        self.values.update(x=coords.x, y=coords.y, z=coords.z)


JOURNAL_IDS = ("cityTamokoWarningJournalQuest", "cityTamokoRefusalJournalQuest", "cityTamokoInformedJournalQuest")


@lru_cache(maxsize=2)
def modelJournalClass(source):
    tree = ast.parse(source)
    load = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load")
    selected = [
        deepcopy(node)
        for node in load.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        and node.name in ("tamokoJournalEntries", "BaldursGateTamokoJournalQuest")
    ]
    for node in selected:
        node.decorator_list = []
    namespace = {"CQuest": SourceObject}
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), str(SCRIPT), "exec"), namespace)
    return mapQuest("baldursGate")(namespace["BaldursGateTamokoJournalQuest"]), namespace["tamokoJournalEntries"]()


def modelJournal(game, qid):
    cls, table = modelJournalClass(SCRIPT.read_text(encoding="utf-8"))
    number, row = next((number, row) for number, row in table.items() if row[0] == qid)
    return cls(game, qid, description=row[1], sourceJournalId=number, sourceJournalRawFlags=92, sourceDialogue="TAMOKO")


class SourceCreature(SourceObject):
    def __init__(self, game, name, **values):
        super().__init__(game, name, hp=70, phaseMin=7, phaseMax=7, **values)
        self.items, self.quests, self.completed = [], [], []
        self.gold, self.exp = 37, 43

    def isNpc(self):
        return self.getBoolProperty("npc")

    def isAlive(self):
        return self.getNumericProperty("hp") > 0

    def isPlayer(self):
        return self.name == "player"

    def getQuests(self):
        return list(self.quests)

    def setQuests(self, entries):
        self.quests = list(entries)

    def getCompletedQuests(self):
        return list(self.completed)

    def addQuest(self, name):
        self.quests.append(modelJournal(self.game, name) if name in JOURNAL_IDS else SourceObject(self.game, name))

    def getGold(self):
        return self.gold

    def addGold(self, amount):
        self.gold += amount

    def addExp(self, amount):
        self.exp += amount


class SourceMap(SourceObject):
    mapName = "baldursGate"

    def __init__(self, game):
        super().__init__(game, "baldursGate", plugin_cityPhase=7)
        self.objects, self.operations = {}, []

    def getObjectByName(self, name):
        return self.objects.get(name)

    def getObjects(self):
        return list(self.objects.values())

    def getPlayer(self):
        return self.getObjectByName("player")

    def addObject(self, obj):
        self.objects[obj.name] = obj
        obj.game_map = self

    def removeObject(self, obj):
        self.operations.append(("remove", obj.name))
        self.objects.pop(obj.name, None)
        obj.game_map = None


class EarlyFixture:
    def __init__(self, meeting="first", rescued=0, properties=None):
        self.meeting, self.notifications = meeting, []
        self.game = SimpleNamespace(getMap=lambda: self.game_map, getMapBindingEpoch=lambda: 0)
        self.game_map = SourceMap(self.game)
        self.namespace = self.namespaceForScript()
        code, classes = selectedCode(SCRIPT.read_text(encoding="utf-8"))
        self.player = SourceCreature(self.game, "player")
        self.actor = SourceCreature(
            self.game,
            ACTOR,
            sourceCreature="TAMOKO",
            sourceArea="AR0800" if meeting == "first" else "AR1100",
            label="Tamoko",
            npc=True,
            affiliation="cityResidents",
            x=1,
        )
        self.game_map.addObject(self.player)
        self.game_map.addObject(self.actor)
        self.game_map.setStringProperty("activeSimulationRegion", self.actor.getStringProperty("sourceArea"))
        source_type = type(
            "ActualEarlySource", (SourceObject,), {name: self.namespace[name] for name in classes["BaldursGateCustody"]}
        )
        clock_type = type(
            "ActualEarlyClock", (SourceObject,), {name: self.namespace[name] for name in classes["BaldursGateClock"]}
        )
        dialog_type = type(
            "ActualEarlyDialog", (SourceObject,), {name: self.namespace[name] for name in classes["BaldursGateDialog"]}
        )
        for name in classes["BaldursGateDialog"]:
            if name.startswith(("discuss", "finish", "hear", "decline", "acceptTamoko", "refuse")):
                setattr(dialog_type, name + "Flow", self.namespace[name])
        self.source = source_type(self.game, "cityCustody")
        self.registry = clock_type(self.game, "cityClock")
        self.registry.spawnActors = lambda: self.game_map.operations.append(("spawnActors",))
        self.dialog = dialog_type(self.game, ACTOR + "Dialog", actorId=ACTOR)
        self.dialog.actor = lambda: self.game_map.getObjectByName(ACTOR)
        self.dialog.canInteract = (
            lambda: self.actor.getGame() is self.game
            and self.game_map.getObjectByName(ACTOR) is self.actor
            and self.player.isAlive()
        )
        self.game_map.addObject(self.source)
        self.game_map.addObject(self.registry)
        self.namespace["write"](self.registry, "questDefinitions", {"quests": [selectedQuest()], "excursions": []})
        scenes = [
            {
                "id": "undercity",
                "sourceArea": "AR0123",
                "x": 1,
                "y": 0,
                "z": 0,
                "phaseMin": 7,
                "phaseMax": 7,
                "conditions": {"flags": ["tamokoMove2", "palaceCleared"]},
            },
            {
                "id": "southwest",
                "sourceArea": "AR1100",
                "x": 1,
                "y": 0,
                "z": 0,
                "phaseMin": 7,
                "phaseMax": 7,
                "conditions": {"flags": ["tamokoMove1"], "absentFlags": ["tamokoMove2"]},
            },
            {
                "id": "east",
                "sourceArea": "AR0800",
                "x": 1,
                "y": 0,
                "z": 0,
                "phaseMin": 7,
                "phaseMax": 7,
                "conditions": {"absentFlags": ["tamokoMove1", "tamokoMove2"]},
            },
        ]
        self.namespace["write"](
            self.registry,
            "relocationDefinitions",
            [{"id": "tamoko", "canonicalActorId": ACTOR, "sourceCreature": "TAMOKO", "scenes": scenes}],
        )
        self.source.setGlobal("OTHER", "GLOBAL", 77)
        self.source.setGlobal("TamokoMove", "AR0800", 9)
        self.source.setGlobal("TamokoMove", "GLOBAL", 0 if meeting == "first" else 1)
        self.source.setGlobal("RescuedEltan", "GLOBAL", rescued)
        self.game_map.setBoolProperty("plugin_cityFlag_tamokoMove1", meeting == "second")
        self.game_map.setNumericProperty("plugin_cityTamokoMove", 0 if meeting == "first" else 1)
        if properties is not None:
            self.game_map.values = deepcopy(properties)
        self.initial_items, self.initial_gold, self.initial_exp = (
            list(self.player.items),
            self.player.gold,
            self.player.exp,
        )

    def namespaceForScript(self):
        namespace = {
            "json": json,
            "CITY_JSON_PREFIX": "city-json:",
            "TAMOKO_JOURNAL_VERSION": 1,
            "CCreature": SourceCreature,
            "CQuest": SourceObject,
            "CQuest": SourceObject,
            "Coords": lambda x, y, z: SimpleNamespace(x=x, y=y, z=z),
            "flowGame": lambda game: game,
            "uiRequest": lambda operation, *args: {"operation": operation, "args": args},
        }
        code, _ = selectedCode(SCRIPT.read_text(encoding="utf-8"))
        exec(code, namespace)
        namespace.update(
            freezeHistory=lambda obj: None,
            seedRewardStock=lambda obj, actor: None,
            notify=lambda obj, text: self.notifications.append(text),
            applyEffects=lambda obj, effects, owner: effects == {},
            crime=lambda obj, actor: None,
        )

        def condition(obj, row):
            if not (not set(row) - {"flags", "absentFlags", "kills", "items"}):
                raise AssertionError(row)
            game_map = obj.getGame().getMap()
            return (
                all(game_map.getBoolProperty("plugin_cityFlag_" + name) for name in row.get("flags", []))
                and not any(game_map.getBoolProperty("plugin_cityFlag_" + name) for name in row.get("absentFlags", []))
                and (not row.get("kills") or game_map.getBoolProperty("modelCythandriaKilled"))
                and (
                    not row.get("items")
                    or any(item.getStringProperty("sourceResource") == "SCRL3F" for item in self.player.items)
                )
            )

        namespace["applyCondition"] = condition
        return namespace

    def state(self):
        return self.source.globalValue("TamokoMove", "GLOBAL")

    def journal(self):
        return self.namespace["read"](self.game_map, "plugin_cityCustodyJournal", [])

    def checkpoint(self):
        return self.namespace["read"](self.game_map, "plugin_cityTamokoEarlyDialogue", {})

    def snapshot(self):
        return (
            deepcopy(self.game_map.values),
            tuple(self.game_map.operations),
            tuple(self.player.quests),
            tuple(self.player.items),
            self.player.gold,
            self.player.exp,
        )

    def flow(self):
        return self.dialog.discussTamokoEarlyMeeting(self.meeting)

    def settle(self, choices):
        flow = self.flow()
        replies = iter(choices)
        response = None
        views = []
        try:
            while True:
                try:
                    request = flow.send(response)
                except StopIteration as result:
                    return result.value, views
                views.append(request)
                response = next(replies) if request["operation"] == "choose" else None
        finally:
            flow.close()


def routes(start):
    rows = {
        row["state"]: row for row in json.loads(INVENTORY.read_text(encoding="utf-8"))["states"] if row["state"] < 20
    }
    result = []

    def visit(state, choices):
        options = [edge for edge in rows[state]["edges"] if edge["replyId"] is not None]
        if not options:
            result.append((choices, state))
            return
        for edge in options:
            visit(edge["targetState"], choices + [edge["replyId"]])

    visit(start, [])
    return result


class BaldursGateTamokoEarlyMeetingTest(unittest.TestCase):
    def testAllTwentyStatesAndThirtyChoicesMatchTheSelectedSourceInventory(self):
        fixture = EarlyFixture()
        data = json.loads(INVENTORY.read_text(encoding="utf-8"))
        data["states"] = [row for row in data["states"] if row["state"] < 20]
        self.assertEqual(list(range(20)), [row["state"] for row in data["states"]])
        self.assertEqual(30, sum(edge["replyId"] is not None for row in data["states"] for edge in row["edges"]))
        for row in data["states"]:
            node = fixture.dialog.tamokoEarlyNode(row["state"])
            self.assertEqual(row["npcParaphrase"], node["text"])
            self.assertEqual(
                [
                    (edge["replyId"], edge["paraphrase"], edge["targetState"])
                    for edge in row["edges"]
                    if edge["replyId"] is not None
                ],
                node["options"],
            )

    def testEveryFirstMeetingBranchJournalsAndActuallyLeavesForTheNextScene(self):
        for choices, terminal in routes(0):
            with self.subTest(choices=choices):
                f = EarlyFixture()
                result, views = f.settle(choices)
                self.assertTrue(result)
                self.assertIn(terminal, (6, 7))
                self.assertEqual([27461], f.journal())
                self.assertEqual(1, f.state())
                self.assertEqual("AR1100", f.actor.getStringProperty("sourceArea"))
                self.assertIs(f.actor, f.game_map.getObjectByName(ACTOR))
                self.assertIn(("remove", ACTOR), f.game_map.operations)
                self.assertFalse(f.actor.getBoolProperty("plugin_cityDeparted"))
                self.assertEqual((37, 43, []), (f.player.gold, f.player.exp, f.player.items))
                self.assertEqual(["cityTamokoWarningJournalQuest"], [entry.getTypeId() for entry in f.player.quests])
                self.assertEqual({}, f.checkpoint())
                self.assertEqual(77, f.source.globalValue("OTHER", "GLOBAL"))
                self.assertEqual(9, f.source.globalValue("TamokoMove", "AR0800"))

    def testBothStateEightEdgesSetMoveThreeBeforeTheFirstChoice(self):
        for rescued in (0, 1):
            f = EarlyFixture("second", rescued)
            flow = f.flow()
            self.assertEqual("showReader", next(flow)["operation"])
            request = flow.send(None)
            if rescued:
                self.assertEqual("showReader", request["operation"])
                request = flow.send(None)
            self.assertEqual("choose", request["operation"])
            self.assertEqual(3, f.state())
            self.assertEqual([], f.journal())
            self.assertEqual(["threaten", "questionPromise", "promise"], [row["id"] for row in request["args"][2]])
            self.assertEqual(
                "rescued" if rescued else "notRescued", f.game_map.getStringProperty("plugin_cityTamokoEltanDiscussion")
            )
            flow.close()

    def testEverySecondBranchSeparatesRefusalFromInformedAgreementWithoutRewards(self):
        for choices, terminal in routes(10):
            with self.subTest(choices=choices):
                f = EarlyFixture("second")
                result, _ = f.settle(choices)
                self.assertTrue(result)
                self.assertEqual(2, f.state())
                self.assertEqual([27462 if terminal == 12 else 27463], f.journal())
                self.assertEqual(
                    0 if terminal == 12 else 1,
                    len([entry for entry in f.player.quests if entry.getTypeId() not in JOURNAL_IDS]),
                )
                self.assertEqual(
                    "notStarted" if terminal == 12 else "active", f.namespace["stage"](f.dialog, "cythandriaDiary")
                )
                self.assertEqual((37, 43, []), (f.player.gold, f.player.exp, f.player.items))
                self.assertTrue(f.actor.isAlive())
                self.assertIsNone(f.game_map.getObjectByName(ACTOR))
                self.assertIs(f.actor, f.registry.getObjectProperty("plugin_cityRelocationActor_tamoko"))
                self.assertFalse(f.actor.getBoolProperty("plugin_cityDeparted"))

    def testPresentSourceGlobalsWinOverLegacyFlagsAndUnsupportedRescuedValuesHaveNoExit(self):
        for value in (2, -1, True, "1", None):
            f = EarlyFixture("second", value)
            f.game_map.setBoolProperty("plugin_cityFlag_eltanCarried", True)
            self.assertFalse(f.settle([])[0])
            self.assertEqual(1, f.state())
            self.assertEqual([], f.journal())
            self.assertEqual([], f.player.quests)
        f = EarlyFixture("second", 0)
        f.game_map.setBoolProperty("plugin_cityFlag_eltanSafe", True)
        _, views = f.settle(["threaten"])
        self.assertEqual(2, len([view for view in views if view["operation"] == "showReader"]))
        f = EarlyFixture()
        f.game_map.setNumericProperty("plugin_cityTamokoMove", 2)
        f.game_map.setBoolProperty("plugin_cityFlag_tamokoMove2", True)
        self.assertEqual(0, f.dialog.tamokoEarlyValues(f.dialog.tamokoEarlyBinding("first"))[0])

    def testMissingLegacyMigrationHasExplicitPriorityAndRejectsContradictions(self):
        cases = (
            ({"plugin_cityTamokoMove": 2, "plugin_cityFlag_tamokoSpared": True}, 4),
            ({"plugin_cityTamokoMove": 0, "plugin_cityFlag_tamokoMove1": True}, 1),
            (
                {
                    "plugin_cityTamokoMove": 3,
                    "plugin_cityFlag_tamokoMove1": True,
                    "plugin_cityFlag_tamokoDiscussed": True,
                },
                3,
            ),
            ({"plugin_cityTamokoMove": 1, "plugin_cityFlag_tamokoMove2": True}, None),
            (
                {
                    "plugin_cityTamokoMove": 2,
                    "plugin_cityFlag_tamokoSpared": True,
                    "plugin_cityFlag_tamokoFought": True,
                },
                None,
            ),
            ({"plugin_cityTamokoMove": 9}, None),
            ({"plugin_cityTamokoMove": 0, "plugin_cityFlag_tamokoFought": True}, None),
            ({"plugin_cityTamokoMove": 1, "plugin_cityFlag_tamokoFought": True}, None),
            ({"plugin_cityTamokoMove": 2, "plugin_cityFlag_tamokoFought": True}, 2),
        )
        for changes, expected in cases:
            f = EarlyFixture()
            values = f.namespace["read"](f.game_map, "plugin_cityCustodyGlobals", {})
            values.pop("GLOBAL:TamokoMove")
            f.namespace["write"](f.game_map, "plugin_cityCustodyGlobals", values)
            f.game_map.values.update(changes)
            self.assertEqual(expected, f.dialog.tamokoEarlyValues(f.dialog.tamokoEarlyBinding("first"))[0])
            self.assertEqual([], f.journal())
            self.assertEqual([], f.player.quests)

    def testCancellationAndFreshObjectReloadResumeFiniteCheckpointsWithoutReplayingStateEight(self):
        for meeting, prefix in (("first", ["askIdentity"]), ("second", []), ("second", ["promise"])):
            f = EarlyFixture(meeting)
            flow = f.flow()
            request = next(flow)
            while request["operation"] != "choose":
                request = flow.send(None)
            for reply in prefix:
                request = flow.send(reply)
            self.assertEqual("choose", request["operation"])
            saved = deepcopy(f.game_map.values)
            flow.close()
            replacement = EarlyFixture(meeting, properties=saved)
            self.assertIsNot(f.actor, replacement.actor)
            self.assertIsNot(f.player, replacement.player)
            resumed = replacement.flow()
            first = next(resumed)
            self.assertEqual("choose", first["operation"])
            self.assertEqual(request["args"][1:3], first["args"][1:3])
            self.assertEqual([], replacement.journal())
            resumed.close()

    def testUnknownRepliesAndCloseAtEveryReachableChoiceDoNotAdvanceTheCheckpoint(self):
        for meeting, start in (("first", 0), ("second", 10)):
            for choices, _terminal in routes(start):
                for length in range(len(choices)):
                    for reply in (None, "unknown", {}):
                        f = EarlyFixture(meeting)
                        flow = f.flow()
                        request = next(flow)
                        while request["operation"] != "choose":
                            request = flow.send(None)
                        for selected in choices[:length]:
                            request = flow.send(selected)
                        before = f.snapshot()
                        with self.assertRaises(StopIteration) as stopped:
                            flow.send(reply)
                        self.assertFalse(stopped.exception.value)
                        self.assertEqual(before, f.snapshot())
                        flow.close()

    def testFreshBindingsRejectReplacementAtEveryAwaitWithoutWritingTheReplacementMap(self):
        mutations = ("map", "player", "actor", "source", "clock", "area", "phase", "dead")
        for mutation in mutations:
            f = EarlyFixture("second")
            flow = f.flow()
            next(flow)
            request = flow.send(None)
            self.assertEqual("choose", request["operation"])
            if mutation == "map":
                f.game_map = SourceMap(f.game)
            elif mutation == "player":
                f.game_map.addObject(SourceCreature(f.game, "player"))
            elif mutation == "actor":
                f.game_map.addObject(SourceCreature(f.game, ACTOR, sourceCreature="TAMOKO", sourceArea="AR1100"))
            elif mutation in ("source", "clock"):
                f.game_map.addObject(SourceObject(f.game, "cityCustody" if mutation == "source" else "cityClock"))
            elif mutation == "area":
                f.actor.setStringProperty("sourceArea", "AR0800")
            elif mutation == "phase":
                f.game_map.setNumericProperty("plugin_cityPhase", 5)
            else:
                f.player.setNumericProperty("hp", 0)
            before = deepcopy(f.game_map.values)
            with self.assertRaises(StopIteration) as stopped:
                flow.send("threaten")
            self.assertFalse(stopped.exception.value)
            self.assertEqual(before, f.game_map.values)
            flow.close()

    def testLegacyBooleanCallbacksCannotBypassTheFullChooserOrAcceptTheLead(self):
        for method, args in (
            ("finishTamokoFirstMeeting", (True,)),
            ("hearTamokoWarning", ()),
            ("declineTamokoFirstMeeting", ()),
        ):
            f = EarlyFixture()
            flow = getattr(f.dialog, method)(*args)
            self.assertEqual("choose", next(flow)["operation"])
            self.assertEqual(0, f.state())
            flow.close()
        for method, args in (
            ("finishTamokoSecondMeeting", (True,)),
            ("acceptTamokoRequest", ()),
            ("refuseTamokoRequest", ()),
            ("discussTamokoRequest", ()),
        ):
            f = EarlyFixture("second")
            flow = getattr(f.dialog, method)(*args)
            self.assertEqual("showReader", next(flow)["operation"])
            self.assertEqual([], f.player.quests)
            flow.close()
        f = EarlyFixture("second")
        f.game_map.setBoolProperty("plugin_cityFlag_tamokoDiscussed", True)
        self.assertFalse(f.dialog.acceptQuest("cythandriaDiary"))
        self.assertEqual([], f.player.quests)

    def testLegacyDiscussedFlagCannotGrantKnowledgeFromTheLaterActor(self):
        f = EarlyFixture("second")
        f.actor.setStringProperty("sourceArea", "AR0123")
        f.game_map.setStringProperty("activeSimulationRegion", "AR0123")
        f.game_map.setBoolProperty("plugin_cityFlag_tamokoDiscussed", True)
        f.source.setGlobal("TamokoMove", "GLOBAL", 2)
        self.assertFalse(f.dialog.acceptQuest("cythandriaDiary"))
        self.assertEqual([], f.player.quests)
        self.assertEqual("notStarted", f.namespace["stage"](f.dialog, "cythandriaDiary"))

    def testLaterInformedAcceptancePreservesAnAlreadyOwnedDiaryAndExistingKillProgress(self):
        f = EarlyFixture("second")
        diary = SourceObject(f.game, "ownedDiary", sourceResource="SCRL3F")
        f.player.items = [diary]
        f.game_map.setBoolProperty("modelCythandriaKilled", True)
        f.game_map.setBoolProperty("plugin_cityFlag_palaceCleared", True)
        success, _ = f.settle(["promise", "askHow", "askDivinity", "trySpare", "thankForLead"])
        self.assertTrue(success)
        self.assertEqual("active", f.namespace["stage"](f.dialog, "cythandriaDiary"))
        self.assertEqual([diary], f.player.items)
        f.game_map.setStringProperty("activeSimulationRegion", "AR0123")
        self.assertTrue(f.dialog.canQuestOutcome("cythandriaDiary", "complete"))
        self.assertEqual([diary], f.player.items)
        self.assertEqual((37, 43), (f.player.gold, f.player.exp))

    def testTerminalRecoverySkipsAlreadyWrittenJournalGlobalAndQuestLead(self):
        f = EarlyFixture("second")
        flow = f.flow()
        next(flow)
        flow.send(None)
        flow.send("promise")
        flow.send("askHow")
        flow.send("askDivinity")
        flow.send("trySpare")
        flow.send("thankForLead")
        flow.close()
        self.assertEqual(18, f.checkpoint()["state"])
        calls = []
        old = f.game_map.setStringProperty

        def recorded(name, value):
            if name == "plugin_cityCustodyJournal":
                calls.append(json.loads(value.removeprefix("city-json:")))
            return old(name, value)

        f.game_map.setStringProperty = recorded
        self.assertTrue(f.settle([])[0])
        self.assertEqual([[27463]], calls)
        self.assertEqual(1, len([entry for entry in f.player.quests if entry.getTypeId() not in JOURNAL_IDS]))
        self.assertEqual([27463], f.journal())
        self.assertFalse(f.settle([])[0])
        self.assertEqual([[27463]], calls)
        self.assertEqual(1, len([entry for entry in f.player.quests if entry.getTypeId() not in JOURNAL_IDS]))

    def testCapturedStoreCallbacksCannotWriteTheReplacementMap(self):
        for store, call in (
            (
                "plugin_cityCustodyGlobals",
                lambda f, binding: f.dialog.writeTamokoEarlyGlobal(binding, "second", "TamokoMove", 3),
            ),
            (
                "plugin_cityCustodyJournal",
                lambda f, binding: f.dialog.writeTamokoEarlyJournal(binding, "second", 27463),
            ),
            (
                "plugin_cityTamokoEarlyDialogue",
                lambda f, binding: f.dialog.saveTamokoEarlyCheckpoint(binding, "second", 10, 3),
            ),
        ):
            for at in ("get", "set"):
                with self.subTest(store=store, at=at):
                    f = EarlyFixture("second")
                    binding = f.dialog.tamokoEarlyBinding("second")
                    old_map, replacement = f.game_map, SourceMap(f.game)
                    baseline = deepcopy(replacement.values)
                    if at == "get":
                        saved = old_map.getStringProperty

                        def changed(name):
                            value = saved(name)
                            if name == store:
                                f.game_map = replacement
                            return value

                        old_map.getStringProperty = changed
                    else:
                        saved = old_map.setStringProperty

                        def changed(name, value):
                            saved(name, value)
                            if name == store:
                                f.game_map = replacement

                        old_map.setStringProperty = changed
                    self.assertFalse(call(f, binding))
                    self.assertEqual(baseline, replacement.values)
                    self.assertEqual([], replacement.operations)
                    self.assertEqual([], old_map.operations)
                    self.assertEqual([], f.player.quests)

    def testTerminalReplayAfterPartialJournalWriteDoesNotRepeatLeadJournalOrGlobal(self):
        f = EarlyFixture("second")
        flow = f.flow()
        next(flow)
        flow.send(None)
        for reply in ("promise", "askHow", "askDivinity", "trySpare", "thankForLead"):
            request = flow.send(reply)
        self.assertEqual("showReader", request["operation"])
        writes = []
        saved = f.game_map.setStringProperty
        failed = False

        def interrupted(name, value):
            nonlocal failed
            writes.append(name)
            saved(name, value)
            if name == "plugin_cityCustodyJournal" and not failed:
                failed = True
                raise RuntimeError("after retained journal")

        f.game_map.setStringProperty = interrupted
        with self.assertRaisesRegex(RuntimeError, "after retained journal"):
            flow.send(None)
        self.assertEqual(18, f.checkpoint()["state"])
        self.assertEqual([27463], f.journal())
        self.assertEqual(1, len([entry for entry in f.player.quests if entry.getTypeId() not in JOURNAL_IDS]))
        self.assertEqual(3, f.state())
        self.assertTrue(f.settle([])[0])
        self.assertEqual(1, writes.count("plugin_cityCustodyJournal"))
        self.assertEqual(1, writes.count("plugin_cityQuest_cythandriaDiary"))
        self.assertEqual(1, writes.count("plugin_cityCustodyGlobals"))
        self.assertEqual(1, len([entry for entry in f.player.quests if entry.getTypeId() not in JOURNAL_IDS]))
        self.assertEqual(2, f.state())
        self.assertFalse(f.settle([])[0])

    def testInterruptedTemporaryRemovalResumesOnlyTheSameCanonicalActor(self):
        for replace in (False, True):
            f = EarlyFixture("second")
            saved = f.game_map.removeObject

            def interrupted(actor):
                saved(actor)
                raise RuntimeError("after actual temporary removal")

            f.game_map.removeObject = interrupted
            with self.assertRaisesRegex(RuntimeError, "after actual temporary removal"):
                f.settle(["promise", "askHow", "askDivinity", "trySpare", "thankForLead"])
            self.assertIsNone(f.game_map.getObjectByName(ACTOR))
            self.assertIs(f.actor, f.registry.getObjectProperty("plugin_cityRelocationActor_tamoko"))
            self.assertEqual(18, f.checkpoint()["state"])
            self.assertEqual([27463], f.journal())
            self.assertEqual(2, f.state())
            f.game_map.removeObject = saved
            if replace:
                f.registry.setObjectProperty(
                    "plugin_cityRelocationActor_tamoko", SourceCreature(f.game, "differentActor")
                )
                before = f.snapshot()
                self.assertFalse(f.settle([])[0])
                self.assertEqual(before, f.snapshot())
            else:
                self.assertTrue(f.settle([])[0])
                self.assertEqual({}, f.checkpoint())
                self.assertEqual(1, len([entry for entry in f.player.quests if entry.getTypeId() not in JOURNAL_IDS]))
                self.assertEqual([27463], f.journal())
                self.assertEqual(1, f.game_map.operations.count(("remove", ACTOR)))
                self.assertFalse(f.actor.getBoolProperty("plugin_cityDeparted"))

    def testPendingDiscussionGettersAndRequestConstructionStopBeforeFurtherSideEffects(self):
        for target in ("plugin_cityTamokoEltanDiscussion", "plugin_cityFlag_tamokoDiscussed"):
            f = EarlyFixture("second")
            flow = f.flow()
            self.assertEqual("showReader", next(flow)["operation"])
            old, replacement = f.game_map, SourceMap(f.game)
            before = deepcopy(replacement.values)
            stopped_at = []
            method = "getStringProperty" if target.endswith("Discussion") else "getBoolProperty"
            saved = getattr(old, method)

            def rebind(name):
                value = saved(name)
                if name == target:
                    stopped_at.append(deepcopy(old.values))
                    f.game_map = replacement
                return value

            setattr(old, method, rebind)
            with self.assertRaises(StopIteration) as stopped:
                flow.send(None)
            self.assertIs(False, stopped.exception.value)
            self.assertEqual(1, len(stopped_at))
            self.assertEqual(stopped_at[0], old.values)
            self.assertEqual(before, replacement.values)
            self.assertEqual([], old.operations)
        for target in ("flowGame", "uiRequest"):
            f = EarlyFixture()
            old, replacement = f.game_map, SourceMap(f.game)
            before = deepcopy(old.values)
            saved = f.namespace[target]

            def rebind(*args):
                value = saved(*args)
                f.game_map = replacement
                return value

            f.namespace[target] = rebind
            with self.assertRaises(StopIteration) as stopped:
                next(f.flow())
            self.assertIs(False, stopped.exception.value)
            self.assertEqual(before, old.values)
            self.assertEqual([], old.operations)

    def testLeadSettlementUsesOnlyCapturedMetadataAndStageAfterFreshChecks(self):
        for target in ("questDefinitions", "plugin_cityQuest_cythandriaDiary"):
            f = EarlyFixture("second")
            flow = f.flow()
            next(flow)
            flow.send(None)
            for reply in ("promise", "askHow", "askDivinity", "trySpare", "thankForLead"):
                flow.send(reply)
            old, replacement = f.game_map, SourceMap(f.game)
            before = deepcopy(old.values)
            foreign_before = deepcopy(replacement.values)
            owner = f.registry if target == "questDefinitions" else old
            saved = owner.getStringProperty

            def rebind(name):
                value = saved(name)
                if name == target:
                    f.game_map = replacement
                return value

            owner.getStringProperty = rebind
            with self.assertRaises(StopIteration) as stopped:
                flow.send(None)
            self.assertIs(False, stopped.exception.value)
            self.assertEqual(before, old.values)
            self.assertEqual(foreign_before, replacement.values)
            self.assertEqual([], f.player.quests)
        f = EarlyFixture("second")

        def forbidden(*args):
            raise AssertionError("generic lazy quest helper entered")

        f.dialog.canAcceptQuest = forbidden
        f.namespace["stage"] = forbidden
        f.namespace["quest"] = forbidden
        self.assertTrue(f.settle(["promise", "askHow", "askDivinity", "trySpare", "thankForLead"])[0])
        self.assertEqual(1, len([entry for entry in f.player.quests if entry.getTypeId() not in JOURNAL_IDS]))

    def testCapturedMetadataAcceptsTheAuthoredDocumentAndExplicitLegacyList(self):
        for legacy in (False, True):
            f = EarlyFixture("second")
            document = f.namespace["read"](f.registry, "questDefinitions", [])
            self.assertIsInstance(document, dict)
            self.assertEqual([], document["excursions"])
            if legacy:
                f.namespace["write"](f.registry, "questDefinitions", document["quests"])
            self.assertTrue(f.settle(["promise", "askHow", "askDivinity", "trySpare", "thankForLead"])[0])
            self.assertEqual(1, len([entry for entry in f.player.quests if entry.getTypeId() not in JOURNAL_IDS]))
            self.assertEqual([27463], f.journal())
            self.assertEqual(2, f.state())

    def testActorReplacementInsideTheFinalBindingGetterStopsBeforeCheckpointWrite(self):
        for replacement in (False, True):
            f = EarlyFixture()
            binding = f.dialog.tamokoEarlyBinding("first")
            saved = f.actor.getStringProperty
            fired = False

            def replaceActor(name):
                nonlocal fired
                value = saved(name)
                if name == "sourceArea" and not fired:
                    fired = True
                    if replacement:
                        f.game_map.addObject(
                            SourceCreature(f.game, ACTOR, sourceCreature="TAMOKO", sourceArea="AR0800", x=1)
                        )
                    else:
                        f.game_map.objects.pop(ACTOR)
                return value

            f.actor.getStringProperty = replaceActor
            before = deepcopy(f.game_map.values)
            self.assertFalse(f.dialog.saveTamokoEarlyCheckpoint(binding, "first", 1))
            self.assertTrue(fired)
            self.assertEqual(before, f.game_map.values)
            self.assertEqual({}, f.checkpoint())

    def testMalformedCursorsAndSourceMoveThreeWithoutAnAdaptedCursorFailClosed(self):
        cases = [
            {"version": True, "meeting": "second", "state": 10, "move": None},
            {"version": 1, "meeting": "second", "state": 10.0, "move": None},
            {"version": 1, "meeting": "second", "state": 10, "move": 3.0},
            {"version": 1, "meeting": "second", "state": 10, "move": True},
            {"version": 1, "meeting": "second", "state": 11, "move": 3},
            {"version": 1, "meeting": "second", "state": 10, "move": None, "extra": 1},
        ]
        for cursor in cases:
            f = EarlyFixture("second")
            f.namespace["write"](f.game_map, "plugin_cityTamokoEarlyDialogue", cursor)
            before = f.snapshot()
            self.assertFalse(f.settle([])[0])
            self.assertEqual(before, f.snapshot())
        f = EarlyFixture("second")
        f.source.setGlobal("TamokoMove", "GLOBAL", 3)
        self.assertFalse(f.dialog.canTamokoSecondMeeting())
        self.assertFalse(f.settle([])[0])
        self.assertEqual({}, f.checkpoint())

    def testMissingLegacyRescuedAndDiscussedMigrationAreExplicitAndDoNotInventSourceEntries(self):
        for name in ("", "eltanCarried", "eltanSafe"):
            f = EarlyFixture("second")
            values = f.namespace["read"](f.game_map, "plugin_cityCustodyGlobals", {})
            del values["GLOBAL:RescuedEltan"]
            f.namespace["write"](f.game_map, "plugin_cityCustodyGlobals", values)
            if name:
                f.game_map.setBoolProperty("plugin_cityFlag_" + name, True)
            flow = f.flow()
            next(flow)
            request = flow.send(None)
            if name:
                self.assertEqual("showReader", request["operation"])
                request = flow.send(None)
            self.assertEqual("choose", request["operation"])
            self.assertEqual(1 if name else 0, f.source.globalValue("RescuedEltan", "GLOBAL"))
            flow.close()
        f = EarlyFixture("second")
        values = f.namespace["read"](f.game_map, "plugin_cityCustodyGlobals", {})
        del values["GLOBAL:TamokoMove"]
        f.namespace["write"](f.game_map, "plugin_cityCustodyGlobals", values)
        f.game_map.setBoolProperty("plugin_cityFlag_tamokoDiscussed", True)
        f.game_map.setNumericProperty("plugin_cityTamokoMove", 3)
        flow = f.flow()
        self.assertEqual("choose", next(flow)["operation"])
        self.assertEqual(10, f.checkpoint()["state"])
        self.assertEqual(3, f.state())
        self.assertEqual([], f.journal())
        self.assertEqual([], f.player.quests)
        flow.close()

    def testCommittedSupplementMapsAllTwentySixStatesAndFiftyEdgesWithoutClosingTheMatrix(self):
        data = json.loads(INVENTORY.read_text(encoding="utf-8"))
        self.assertLess(INVENTORY.stat().st_size, 96 * 1024)
        self.assertEqual(list(range(26)), [row["state"] for row in data["states"]])
        edges = [edge for row in data["states"] for edge in row["edges"]]
        self.assertEqual(list(range(50)), [edge["edge"] for edge in edges])
        targets = [
            1,
            3,
            2,
            4,
            5,
            3,
            1,
            3,
            5,
            4,
            7,
            6,
            7,
            6,
            None,
            None,
            9,
            10,
            10,
            12,
            13,
            11,
            12,
            14,
            None,
            12,
            11,
            12,
            15,
            12,
            16,
            17,
            12,
            17,
            18,
            19,
            None,
            None,
            22,
            21,
            23,
            None,
            21,
            21,
            23,
            21,
            25,
            24,
            None,
            None,
        ]
        self.assertEqual(targets, [edge["targetState"] for edge in edges])
        self.assertEqual(
            {14: 27461, 15: 27461, 24: 27462, 36: 27463, 37: 27463},
            {edge["edge"]: edge["journalStrref"] for edge in edges[:38] if edge.get("journalStrref") is not None},
        )
        self.assertEqual(
            {0: 0, 8: 1, 20: 2},
            {
                row["state"]: row["condition"]["globalNumericFacts"][0]["value"]
                for row in data["states"]
                if row["condition"]
            },
        )
        for edge_number, rescued in ((16, 1), (17, 0)):
            edge = edges[edge_number]
            self.assertEqual(
                [{"operation": "Global", "name": "RescuedEltan", "scope": "GLOBAL", "value": rescued}],
                edge["condition"]["globalNumericFacts"],
            )
            self.assertEqual(
                [{"operation": "SetGlobal", "name": "TamokoMove", "scope": "GLOBAL", "value": 3}],
                edge["action"]["globalNumericFacts"],
            )
        methods = {
            node.name
            for node in ast.walk(ast.parse(SCRIPT.read_text(encoding="utf-8")))
            if isinstance(node, ast.FunctionDef)
        }
        final_tests = {
            node.name
            for node in ast.walk(ast.parse(FINAL_TEST.read_text(encoding="utf-8")))
            if isinstance(node, ast.FunctionDef)
        }
        route_methods = {
            node.name
            for node in ast.walk(ast.parse(ROUTES.read_text(encoding="utf-8")))
            if isinstance(node, ast.FunctionDef)
        }
        for edge in edges:
            self.assertIn(edge["callback"], methods)
            self.assertIn(edge["implementation"], methods)
            self.assertIn(edge["plannedNativeRoute"]["method"], route_methods)
            self.assertIs(False, edge["plannedNativeRoute"]["executed"])
            for mapping in edge["modelTests"]:
                owner, name = mapping.split(".")
                self.assertTrue(
                    hasattr(type(self), name) if owner.endswith("EarlyMeetingTest") else name in final_tests
                )
        self.assertTrue(all(value is False for value in data["acceptance"].values()))
        self.assertTrue(any("7471" in value for value in data["openObligations"]))
        self.assertEqual("unresolved", data["classicEditionBoundary"]["originOfMismatch"])
        self.assertEqual(
            "a79ca097443a9fbe126201f4ee9102f2eaff254c1ed13ee74153961c40bd5a27",
            data["dialogFingerprint"]["effectiveSha256"],
        )
        self.assertEqual(
            "Installed EE archives with effective override equality; authenticated original BG1 unavailable.",
            data["sourceEdition"],
        )

    def testBuilderNaturalRowsEnterFullFlowsAndRemoveTheGenericKnowledgeBypass(self):
        tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If) and ast.unparse(node.test) == "actor['creature'] == 'TAMOKO'"
        )
        loop = next(node for node in branch.body if isinstance(node, ast.For))
        rows = ast.literal_eval(loop.iter)
        self.assertEqual(
            (
                ("Discuss Tamoko's first meeting.", "discussTamokoFirstMeeting", "canTamokoFirstMeeting"),
                ("Continue Tamoko's request.", "discussTamokoSecondMeeting", "canTamokoSecondMeeting"),
            ),
            rows,
        )
        tree = ast.parse(DIALOGS.read_text(encoding="utf-8"))
        nodes = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in ("upperFirst", "selectorMatches", "questDialogRows")
        ]
        namespace = {}
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), "selected builder metadata", "exec"
            ),
            namespace,
        )
        for area in ("AR1100", "AR0123"):
            rows = namespace["questDialogRows"](
                [selectedQuest()], {"sourceCreature": "TAMOKO", "sourceArea": area}, ACTOR
            )
            self.assertNotIn("acceptCythandriaDiary", [row["action"] for row in rows])
            self.assertIn("questCythandriaDiaryComplete", [row["action"] for row in rows])

    def testNoCoroutineOrControllerIsSerializedAndTheLoopIsFinite(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "discussTamokoEarlyMeeting"
        )
        self.assertTrue(
            any(isinstance(node, ast.Call) and ast.unparse(node) == "range(12)" for node in ast.walk(method))
        )
        text = ast.unparse(method)
        self.assertNotIn("setController", text)
        self.assertNotIn("admitted", text)
        binding = next(
            node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "tamokoEarlyBinding"
        )
        self.assertIn("getObjectByName('player')", ast.unparse(binding))
        self.assertNotIn("getPlayer()", ast.unparse(binding))
        assignments = [
            node.value
            for node in ast.walk(binding)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "binding" for target in node.targets)
        ]
        self.assertEqual(
            ["game_map", "player", "actor", "source", "registry", "epoch"], [value.id for value in assignments[0].elts]
        )

    def testTerminalNotesAreVisibleOwnedUnrewardedAndTravelWithThePlayer(self):
        for meeting, choices, number in (
            ("first", ["hearInformation", "defendGorion", "askRelative"], 27461),
            ("second", ["threaten"], 27462),
            ("second", ["promise", "askHow", "askDivinity", "trySpare", "thankForLead"], 27463),
        ):
            with self.subTest(number=number):
                f = EarlyFixture(meeting)
                unrelated = SourceObject(f.game, "unrelatedActive", questJournalObjective="captured original")
                completed = SourceObject(f.game, "unrelatedCompleted", questJournalCompleted=True)
                f.player.quests.append(unrelated)
                f.player.completed.append(completed)
                before = (deepcopy(unrelated.values), deepcopy(completed.values))
                self.assertTrue(f.settle(choices)[0])
                notes = [entry for entry in f.player.quests if entry.getNumericProperty("sourceJournalId") == number]
                self.assertEqual(1, len(notes))
                owned = notes[0]
                self.assertEqual("TAMOKO", owned.getStringProperty("sourceDialogue"))
                self.assertEqual(92, owned.getNumericProperty("sourceJournalRawFlags"))
                self.assertEqual(1, owned.getNumericProperty("questJournalVersion"))
                self.assertEqual("baldursGate", owned.getStringProperty("questJournalOrigin"))
                self.assertFalse(owned.isCompleted())
                self.assertEqual("No reward.", owned.getReward())
                self.assertTrue(owned.getObjective())
                self.assertTrue(owned.getHint())
                saved = json.loads(json.dumps(owned.values))
                restored = modelJournal(f.game, owned.getTypeId())
                restored.values = saved
                off_map = SourceMap(f.game)
                off_map.mapName = "anotherMap"
                off_map.addObject(f.player)
                f.player.quests[f.player.quests.index(owned)] = restored
                f.game_map = off_map
                self.assertEqual(saved["questJournalObjective"], restored.getObjective())
                self.assertEqual(saved["questJournalHint"], restored.getHint())
                self.assertEqual("No reward.", restored.getReward())
                self.assertFalse(restored.isCompleted())
                self.assertEqual(before, (unrelated.values, completed.values))
                self.assertIn(unrelated, f.player.quests)
                self.assertEqual([completed], f.player.completed)
                self.assertEqual((37, 43, []), (f.player.gold, f.player.exp, f.player.items))

    def testJournalProjectionRejectsCompletedDuplicateAndIncompleteCapture(self):
        for fault in ("completed", "noop", "partial", "throw", "wrongMetadata", "completedSnapshot"):
            with self.subTest(fault=fault):
                f = EarlyFixture()
                binding = f.dialog.tamokoEarlyBinding("first")
                note = modelJournal(f.game, JOURNAL_IDS[0])
                if fault == "completed":
                    f.player.completed.append(note)
                else:

                    def add(name):
                        self.assertEqual(JOURNAL_IDS[0], name)
                        f.player.quests.append(note)

                    f.player.addQuest = add
                    if fault in ("noop", "partial", "throw"):

                        def capture(completed):
                            if fault == "partial":
                                note.setNumericProperty("questJournalVersion", 1)
                            if fault == "throw":
                                raise RuntimeError("owned capture failure")

                        note.captureJournal = capture
                    elif fault == "wrongMetadata":
                        note.setNumericProperty("sourceJournalRawFlags", 0)
                    else:
                        note.setNumericProperty("questJournalVersion", 1)
                        note.setStringProperty("questJournalOrigin", "baldursGate")
                        note.setBoolProperty("questJournalCompleted", True)
                if fault in ("wrongMetadata", "completedSnapshot", "noop", "partial"):
                    with self.assertRaises(ValueError):
                        f.dialog.writeTamokoEarlyJournal(binding, "first", 27461)
                elif fault == "throw":
                    with self.assertRaisesRegex(RuntimeError, "owned capture failure"):
                        f.dialog.writeTamokoEarlyJournal(binding, "first", 27461)
                else:
                    self.assertFalse(f.dialog.writeTamokoEarlyJournal(binding, "first", 27461))
                self.assertEqual([27461], f.journal())
                self.assertEqual("notStarted", f.namespace["stage"](f.dialog, "cythandriaDiary"))
                self.assertFalse(f.game_map.getBoolProperty("plugin_cityFlag_tamokoMove1"))
                self.assertEqual((37, 43), (f.player.gold, f.player.exp))

    def testCapturedEarlyEpochUsesValueEqualityAndRejectsMalformedOrOldTuples(self):
        f = EarlyFixture()
        f.game.getMapBindingEpoch = lambda: int("1000")
        binding = f.dialog.tamokoEarlyBinding("first")
        copy = (*binding[:-1], int("1000"))
        self.assertIsNot(binding[-1], copy[-1])
        self.assertIsNotNone(f.dialog.tamokoEarlyBinding("first", copy))
        for invalid in (
            (),
            binding[:-1],
            (*binding[:-1], True),
            (*binding[:-1], "1000"),
            (*binding[:-1], 1001),
            list(binding),
        ):
            with self.subTest(invalid=invalid):
                self.assertIsNone(f.dialog.tamokoEarlyBinding("first", invalid))

    def testAwayAndBackEpochRejectsEarlyUiGetterAndJournalCallback(self):
        for at in ("ui", "getter", "capture"):
            with self.subTest(at=at):
                f = EarlyFixture()
                epoch = [1000]
                f.game.getMapBindingEpoch = lambda: epoch[0]
                binding = f.dialog.tamokoEarlyBinding("first")
                if at == "ui":
                    flow = f.flow()
                    next(flow)
                    epoch[0] += 2
                    with self.assertRaises(StopIteration) as ended:
                        flow.send("hearInformation")
                    self.assertFalse(ended.exception.value)
                    self.assertEqual([], f.journal())
                elif at == "getter":
                    saved = f.actor.getStringProperty

                    def get(name):
                        value = saved(name)
                        if name == "sourceCreature":
                            epoch[0] += 2
                        return value

                    f.actor.getStringProperty = get
                    self.assertIsNone(f.dialog.tamokoEarlyBinding("first", binding))
                    self.assertEqual([], f.journal())
                else:
                    note = modelJournal(f.game, JOURNAL_IDS[0])

                    def add(name):
                        f.player.quests.append(note)

                    f.player.addQuest = add
                    saved = note.captureJournal

                    def capture(completed):
                        saved(completed)
                        epoch[0] += 2

                    note.captureJournal = capture
                    with self.assertRaisesRegex(RuntimeError, "binding changed"):
                        f.dialog.writeTamokoEarlyJournal(binding, "first", 27461)
                self.assertEqual(0, f.game_map.getNumericProperty("plugin_cityTamokoMove"))
                self.assertEqual((37, 43), (f.player.gold, f.player.exp))

    def testHostileTamokoCannotStartOrResumeAnEarlyConversation(self):
        for key, value in (("npc", False), ("affiliation", "cityHostile")):
            for resume in (False, True):
                with self.subTest(key=key, resume=resume):
                    f = EarlyFixture()
                    flow = f.flow()
                    if resume:
                        next(flow)
                    f.actor.values[key] = value
                    before = f.snapshot()
                    self.assertFalse(f.dialog.canTamokoFirstMeeting())
                    if resume:
                        with self.assertRaises(StopIteration) as stopped:
                            flow.send("hearInformation")
                        self.assertFalse(stopped.exception.value)
                    else:
                        self.assertFalse(f.settle([])[0])
                    self.assertEqual(before, f.snapshot())

    def testAuthoredAttackInvalidatesThePendingFriendlyEarlyChoice(self):
        f = EarlyFixture()
        self.assertTrue(f.dialog.canTamokoFirstMeeting())
        flow = f.flow()
        next(flow)
        # Exercise the actual authored attack callback; history/crime are model leaves here.
        f.dialog.canInteract = lambda: True
        with self.assertRaises(StopIteration) as attack:
            next(f.dialog.attack())
        self.assertTrue(attack.exception.value)
        self.assertFalse(f.actor.isNpc())
        self.assertEqual("cityHostile", f.actor.getStringProperty("affiliation"))
        before = f.snapshot()
        with self.assertRaises(StopIteration) as rejected:
            flow.send("hearInformation")
        self.assertFalse(rejected.exception.value)
        self.assertEqual(before, f.snapshot())
        self.assertFalse(f.dialog.canTamokoFirstMeeting())

    def testTamokoResourceUsesTheActualNativeSandboxContract(self):
        from quest_state import QUEST_JOURNAL_VERSION
        from tests.test_baldurs_gate_city_content import nativePluginBuiltins, unsupportedPluginBuiltins

        text = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(text)
        self.assertEqual([], unsupportedPluginBuiltins(text, nativePluginBuiltins()))
        version = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "TAMOKO_JOURNAL_VERSION" for target in node.targets)
        )
        self.assertEqual(QUEST_JOURNAL_VERSION, ast.literal_eval(version))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, ("game", "json"))
                self.assertEqual(0, node.level)
            elif isinstance(node, ast.Import):
                self.assertTrue(all(alias.name in ("game", "json") for alias in node.names))

    def testRecognizedMapAliasesRejectChangedIdentityOrEpochBeforeFurtherWork(self):
        for name in ("tamokoEarlyState", "activateTamokoEarlyLead", "discussTamokoEarlyMeeting"):
            for bounce in (False, True):
                with self.subTest(method=name, bounce=bounce):
                    f = EarlyFixture("second")
                    epoch = [1000]
                    f.game.getMapBindingEpoch = lambda: epoch[0]
                    binding = f.dialog.tamokoEarlyBinding("second")
                    before = f.snapshot()
                    replacement = SourceMap(f.game)
                    foreign_reads = []

                    def forbidden(*args):
                        foreign_reads.append(args)
                        raise AssertionError("Captured-map alias must reject before reading a replacement")

                    replacement.getObjectByName = forbidden
                    replacement.getBoolProperty = forbidden

                    def changedMap():
                        if bounce:
                            epoch[0] += 2
                            return f.game_map
                        return replacement

                    f.game.getMap = changedMap
                    if name == "tamokoEarlyState":
                        self.assertIsNone(f.dialog.tamokoEarlyState("second", binding))
                    elif name == "activateTamokoEarlyLead":
                        self.assertFalse(f.dialog.activateTamokoEarlyLead(binding))
                    else:
                        f.dialog.tamokoEarlyResumeBinding = lambda meeting: binding
                        with self.assertRaises(StopIteration) as stopped:
                            next(f.dialog.discussTamokoEarlyMeeting("second"))
                        self.assertFalse(stopped.exception.value)
                    self.assertEqual([], foreign_reads)
                    self.assertEqual(before, f.snapshot())


if __name__ == "__main__":
    unittest.main()
