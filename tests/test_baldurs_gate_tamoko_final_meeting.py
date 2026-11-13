# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual selected Tamoko callback tests with bounded source-model objects; no engine or generator imports."""

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
QUESTS = ROOT / "tests/fixtures/baldurs_gate_city_quests.json"
BUILDER = ROOT / "scripts/build_baldurs_gate_city_dialogs.py"
CONFIG = ROOT / "res/maps/baldursGate/config.json"
ACTOR = "cityAr0800ScriptActorTamoko"


def selectedQuest():
    source = QUESTS.read_text(encoding="utf-8")
    marker = '"id": "tamokoMercy"'
    if not (source.count(marker) == 1):
        raise AssertionError("Source-model precondition failed")
    start = source.rfind("{", 0, source.index(marker))
    row, consumed = json.JSONDecoder().raw_decode(source[start : start + 8192])
    if not (consumed < 8192 and row["id"] == "tamokoMercy"):
        raise AssertionError("Source-model precondition failed")
    return row


def configuredDialog():
    data = CONFIG.read_bytes()
    marker = ('"' + ACTOR + 'Dialog":').encode()
    if not (data.count(marker) == 1):
        raise AssertionError("Source-model precondition failed")
    start = data.index(marker) + len(marker)
    row, consumed = json.JSONDecoder().raw_decode(data[start : start + 8192].decode("utf-8").lstrip())
    if not (consumed < 8192 and row["class"] == "BaldursGateDialog"):
        raise AssertionError("Source-model precondition failed")
    return row


@lru_cache(maxsize=2)
def callbackCode(source, filename):
    tree = ast.parse(source)
    names = {
        "decodeData",
        "questId",
        "firstMatch",
        "pairedValues",
        "world",
        "hero",
        "clock",
        "read",
        "write",
        "definitions",
        "quest",
        "stage",
        "matches",
        "actors",
        "social",
        "currentArea",
        "possessions",
        "sourceCode",
        "quantity",
        "hasItems",
        "findItems",
        "applyCondition",
        "recordMatches",
        "setStanding",
        "applyEffects",
        "custody",
        "canInteract",
        "attack",
        "canQuestOutcome",
        "syncTamokoJournal",
        "tamokoFinalBinding",
        "canDiscussTamokoFinalMeeting",
        "commitTamokoFinalMeeting",
        "discussTamokoFinalMeeting",
    }
    load = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load")
    functions = [node for parent in (tree, load) for node in parent.body if isinstance(node, ast.FunctionDef)]
    for owner in ("BaldursGateDialog", "BaldursGateCustody"):
        source_class = next(node for node in load.body if isinstance(node, ast.ClassDef) and node.name == owner)
        functions.extend(node for node in source_class.body if isinstance(node, ast.FunctionDef))
    names |= {"tamokoFinalScore", "tamokoFinalOutcome", "tamokoFinalUiRequest"} & {node.name for node in functions}
    nodes = [deepcopy(node) for node in functions if node.name in names]
    if not ({node.name for node in nodes} == names):
        raise AssertionError("Source-model precondition failed")
    if not (len(nodes) == len(names)):
        raise AssertionError("Source-model precondition failed")
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
    return compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), filename, "exec")


def actualNamespace():
    namespace = {
        "json": json,
        "CITY_JSON_PREFIX": "city-json:",
        "TAMOKO_JOURNAL_VERSION": 1,
        "CCreature": SourceCreature,
        "CQuest": SourceObject,
        "flowGame": lambda game: game,
        "uiRequest": lambda operation, *args: {"operation": operation, "args": args},
        "freezeHistory": lambda obj: None,
        "crime": lambda obj, actor: None,
    }
    exec(callbackCode(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT)), namespace)
    return namespace


class SourceObject:
    def __init__(self, game, name="", **properties):
        self.game, self.name, self.properties = game, name, properties
        self.game_map = None

    def getGame(self):
        return self.game

    def getMap(self):
        return self.game_map

    def getName(self):
        return self.name

    def getTypeId(self):
        return self.name

    def getStringProperty(self, key):
        return self.properties.get(key, "")

    def setStringProperty(self, key, value):
        self.properties[key] = value

    def getNumericProperty(self, key):
        return self.properties.get(key, 0)

    def setNumericProperty(self, key, value):
        self.properties[key] = value

    def getBoolProperty(self, key):
        return bool(self.properties.get(key, False))

    def setBoolProperty(self, key, value):
        self.properties[key] = value

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
        return SimpleNamespace(x=self.properties.get("x", 0), y=self.properties.get("y", 0), z=0)


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
    def __init__(self, game, name, **properties):
        super().__init__(game, name, hp=70, phaseMin=7, phaseMax=7, **properties)
        self.items, self.equipped = [], {}

    def isPlayer(self):
        return self.name == "player"

    def isNpc(self):
        return self.getBoolProperty("npc")

    def isAlive(self):
        return self.getNumericProperty("hp") > 0

    def getItems(self):
        return list(self.items)

    def getEquipped(self):
        return dict(self.equipped)

    def setController(self, controller):
        self.properties["controller"] = controller


class SourcePlayer(SourceCreature):
    def __init__(self, game, score):
        super().__init__(game, "player", gold=100, exp=0, level=10)
        self.base_intelligence, self.equipment_bonus = score, 0
        self.stats = SimpleNamespace(
            getNumericProperty=lambda key: (
                self.base_intelligence + self.equipment_bonus if key == "intelligence" else 10
            )
        )
        self.quests, self.completed = [SourceObject(game, "cityTamokoMercyQuest")], []

    def getStats(self):
        return self.stats

    def getGold(self):
        return self.getNumericProperty("gold")

    def addGold(self, amount):
        self.setNumericProperty("gold", self.getGold() + amount)

    def addExp(self, amount):
        self.setNumericProperty("exp", self.getNumericProperty("exp") + amount)

    def getQuests(self):
        return list(self.quests)

    def addQuest(self, name):
        self.quests.append(modelJournal(self.game, name))

    def setQuests(self, entries):
        self.quests = list(entries)

    def getCompletedQuests(self):
        return list(self.completed)

    def checkQuests(self):
        resolved = [entry for entry in self.quests if entry.getTypeId() == "cityTamokoMercyQuest"]
        self.completed.extend(resolved)
        self.quests = [entry for entry in self.quests if entry not in resolved]


class SourceMap(SourceObject):
    mapName = "baldursGate"

    def __init__(self, game):
        super().__init__(
            game,
            "baldursGate",
            plugin_cityPhase=7,
            plugin_cityTamokoMove=2,
            plugin_cityFlag_tamokoMove2=True,
            plugin_cityFlag_palaceCleared=True,
            plugin_cityQuest_tamokoMercy="active",
            activeSimulationRegion="AR0123",
        )
        self.objects = {}
        self.player = SourcePlayer(game, 12)
        self.addObject(self.player)

    def getPlayer(self):
        return self.player

    def getObjectByName(self, name):
        return self.objects.get(name)

    def getObjects(self):
        return list(self.objects.values())

    def addObject(self, value):
        self.objects[value.name] = value
        value.game_map = self


class TamokoFixture:
    def __init__(self, *, score=12):
        self.created, self.operations, self.parked = [], [], []
        self.failure = None
        self.game = SimpleNamespace(
            getMap=lambda: self.game_map, createObject=self.createObject, getMapBindingEpoch=lambda: 0
        )
        self.game_map = SourceMap(self.game)
        self.player = self.game_map.player
        self.player.base_intelligence = score
        self.actor = SourceCreature(
            self.game,
            ACTOR,
            sourceCreature="TAMOKO",
            sourceArea="AR0123",
            label="Tamoko",
            npc=True,
            affiliation="cityResidents",
        )
        self.actor.items = [SourceObject(self.game, code) for code in ("PLAT05", "SHLD06", "BLUN03")]
        self.actor.equipped = {
            "armor": self.actor.items[0],
            "shield": self.actor.items[1],
            "weapon": self.actor.items[2],
        }
        self.game_map.addObject(self.actor)
        self.registry = SourceObject(self.game, "cityClock")
        self.registry.setStringProperty(
            "questDefinitions", "city-json:" + json.dumps({"quests": [selectedQuest()], "excursions": []})
        )
        self.registry.setStringProperty("areaAtlas", 'city-json:{"AR0123":{"bounds":[0,0,0,10,10]}}')
        self.registry.spawnActors = lambda: self.operations.append("spawnActors")
        self.registry.applySchedules = self.applySchedules
        self.game_map.addObject(self.registry)
        self.namespace = actualNamespace()
        source_type = type("ActualCustodyMethods", (SourceObject,), {})
        self.source = source_type(self.game, "cityCustody")
        self.game_map.addObject(self.source)
        self.source.setGlobal("OTHER", "GLOBAL", 7)
        self.source.setGlobal("TamokoMove", "GLOBAL", 2)
        self.source.setGlobal("TamokoMove", "AR0800", 3)
        self.namespace["write"](self.game_map, "plugin_cityCustodyJournal", [111, 27461, 27462, 27463, 999, 27461])
        self.player.quests.extend(modelJournal(self.game, qid) for qid in JOURNAL_IDS)
        for entry in self.player.quests[1:]:
            entry.captureJournal(False)
        method_names = (
            "attack",
            "syncTamokoJournal",
            "canInteract",
            "canQuestOutcome",
            "tamokoFinalBinding",
            "canDiscussTamokoFinalMeeting",
            "commitTamokoFinalMeeting",
            "discussTamokoFinalMeeting",
        )
        method_names += tuple(
            name
            for name in ("tamokoFinalScore", "tamokoFinalOutcome", "tamokoFinalUiRequest")
            if name in self.namespace
        )
        dialog_type = type(
            "ActualTamokoMethods", (SourceObject,), {name: self.namespace[name] for name in method_names}
        )
        self.dialog = dialog_type(self.game, ACTOR + "Dialog", actorId=ACTOR)
        self.dialog.actor = lambda: self.game_map.getObjectByName(self.dialog.getStringProperty("actorId"))

    def createObject(self, name):
        self.created.append(name)
        if self.failure:
            raise self.failure
        return SourceObject(self.game, name)

    def applySchedules(self):
        self.operations.append("applySchedules")
        if self.actor.getBoolProperty("plugin_cityDeparted"):
            self.parked.append(self.actor)
            self.game_map.objects.pop(self.actor.name, None)

    def snapshot(self):
        return (
            deepcopy(self.game_map.properties),
            dict(self.actor.properties),
            tuple(self.actor.items),
            dict(self.actor.equipped),
            tuple(self.player.quests),
            tuple(self.player.completed),
            self.player.getGold(),
            self.player.getNumericProperty("exp"),
            tuple(self.operations),
            tuple(self.created),
        )

    def settle(self, choices):
        flow = self.dialog.discussTamokoFinalMeeting()
        offered, readers, replies = [], [], iter(choices)
        response = None
        try:
            while True:
                try:
                    request = flow.send(response)
                except StopIteration as result:
                    return result.value, offered, readers
                if request["operation"] == "choose":
                    offered.append([row["id"] for row in request["args"][2]])
                    response = next(replies)
                elif request["operation"] == "gui.checkQuests":
                    if not (self.game_map.getStringProperty("plugin_cityQuest_tamokoMercy") == "completed"):
                        raise AssertionError("Source-model precondition failed")
                    if not (self.namespace["read"](self.game_map, "plugin_cityCustodyJournal", []) == [111, 999]):
                        raise AssertionError("Source-model precondition failed")
                    self.player.checkQuests()
                    response = None
                else:
                    if not (request["operation"] == "showReader"):
                        raise AssertionError("Source-model precondition failed")
                    readers.append(request["args"][2])
                    response = None
        finally:
            flow.close()


def questRows(fixture):
    document = fixture.namespace["read"](fixture.registry, "questDefinitions", [])
    return document.get("quests", []) if isinstance(document, dict) else document


def replaceQuestRows(fixture, rows):
    document = fixture.namespace["read"](fixture.registry, "questDefinitions", [])
    if isinstance(document, dict):
        document["quests"] = rows
    else:
        document = rows
    fixture.namespace["write"](fixture.registry, "questDefinitions", document)


class BaldursGateTamokoFinalMeetingTest(unittest.TestCase):
    def testEveryInitialAndSecondChoiceReachesItsOwnAuditedTerminal(self):
        routes = (
            (["threaten"], 21),
            (["appealChoice", "removeObstacle"], 21),
            (["appealChoice", "unavoidableFight"], 21),
            (["appealChoice", "notEnemy", "forgivingFight"], 21),
            (["refuseHarm", "forgivingFight"], 21),
            (["appealChoice", "notEnemy", "philosophy"], 25),
            (["refuseHarm", "philosophy"], 25),
        )
        for choices, terminal in routes:
            with self.subTest(choices=choices):
                fixture = TamokoFixture()
                success, panels, readers = fixture.settle(choices)
                self.assertTrue(success)
                self.assertEqual(["appealChoice", "threaten", "refuseHarm"], panels[0])
                if choices[0] == "appealChoice":
                    self.assertEqual(["removeObstacle", "unavoidableFight", "notEnemy"], panels[1])
                self.assertEqual(1, len(readers))
                self.assertEqual(terminal == 25, fixture.game_map.getBoolProperty("plugin_cityFlag_tamokoSpared"))
                self.assertEqual(terminal != 25, fixture.game_map.getBoolProperty("plugin_cityFlag_tamokoFought"))

    def testReactionBoundariesOfferOnlySourceEligibleRepliesAndKeepOrdinaryAppealHostile(self):
        for score in (6, 7, 11, 12):
            with self.subTest(score=score):
                fixture = TamokoFixture(score=score)
                choice = "philosophy" if score >= 7 else "forgivingFight"
                success, panels, readers = fixture.settle(["refuseHarm", choice])
                self.assertTrue(success)
                self.assertEqual(["forgivingFight"] + (["philosophy"] if score >= 7 else []), panels[-1])
                self.assertEqual(score >= 12, fixture.game_map.getBoolProperty("plugin_cityFlag_tamokoSpared"))
                if 7 <= score < 12:
                    self.assertIn("reasoning", readers[0])

    def testCurrentComposedStatsAreRereadAfterTheAwaitedPhilosophyChoice(self):
        for before, after, expected in ((7, 12, "complete"), (12, 11, "fight"), (7, 6, None), (6, 12, None)):
            with self.subTest(before=before, after=after):
                fixture = TamokoFixture(score=before)
                flow = fixture.dialog.discussTamokoFinalMeeting()
                next(flow)
                request = flow.send("refuseHarm")
                self.assertEqual(before >= 7, "philosophy" in [row["id"] for row in request["args"][2]])
                fixture.player.equipment_bonus = after - before
                try:
                    request = flow.send("philosophy")
                except StopIteration as result:
                    self.assertIsNone(expected)
                    self.assertFalse(result.value)
                else:
                    self.assertIsNotNone(expected)
                    self.assertEqual("gui.checkQuests", request["operation"])
                    self.assertTrue(fixture.game_map.getBoolProperty("plugin_cityOutcome_tamokoMercy_" + expected))
                finally:
                    flow.close()

    def testCancellationAndUnknownRepliesAtEveryChoiceHaveNoTerminalEffects(self):
        for prefix in ([], ["appealChoice"], ["refuseHarm"], ["appealChoice", "notEnemy"]):
            for reply in (None, "unknown"):
                with self.subTest(prefix=prefix, reply=reply):
                    fixture = TamokoFixture()
                    before = fixture.snapshot()
                    result, _, _ = fixture.settle(prefix + [reply])
                    self.assertFalse(result)
                    self.assertEqual(before, fixture.snapshot())
            fixture = TamokoFixture()
            before = fixture.snapshot()
            flow = fixture.dialog.discussTamokoFinalMeeting()
            next(flow)
            for reply in prefix:
                flow.send(reply)
            flow.close()
            self.assertEqual(before, fixture.snapshot())

    def testReplacedMapPlayerActorQuestCoordinatorOrAreaCannotCommitAfterAnyChoice(self):
        mutations = {
            "map": lambda f: setattr(f, "game_map", SourceMap(f.game)),
            "player": lambda f: f.game_map.addObject(SourcePlayer(f.game, 12)),
            "actor": lambda f: f.game_map.addObject(
                SourceCreature(f.game, ACTOR, sourceCreature="TAMOKO", sourceArea="AR0123")
            ),
            "quest": lambda f: setattr(f.player, "quests", [SourceObject(f.game, "cityTamokoMercyQuest")]),
            "questRemoved": lambda f: f.player.quests.clear(),
            "questDuplicate": lambda f: f.player.quests.append(SourceObject(f.game, "cityTamokoMercyQuest")),
            "source": lambda f: f.game_map.addObject(SourceObject(f.game, "cityCustody")),
            "clock": lambda f: f.game_map.addObject(SourceObject(f.game, "cityClock")),
            "area": lambda f: f.actor.setStringProperty("sourceArea", "AR0800"),
            "unusedCreature": lambda f: f.actor.setStringProperty("sourceCreature", "TAMOKO2"),
            "playerArea": lambda f: (
                f.player.setNumericProperty("x", 20),
                f.game_map.setStringProperty("activeSimulationRegion", "AR0800"),
            ),
            "phase": lambda f: f.game_map.setNumericProperty("plugin_cityPhase", 5),
            "palace": lambda f: f.game_map.setBoolProperty("plugin_cityFlag_palaceCleared", False),
            "dead": lambda f: f.actor.setNumericProperty("hp", 0),
        }
        for prefix in ([], ["appealChoice"], ["appealChoice", "notEnemy"]):
            for name, mutate in mutations.items():
                with self.subTest(prefix=prefix, mutation=name):
                    fixture = TamokoFixture()
                    original_map = fixture.game_map
                    flow = fixture.dialog.discussTamokoFinalMeeting()
                    next(flow)
                    for reply in prefix:
                        flow.send(reply)
                    mutate(fixture)
                    with self.assertRaises(StopIteration) as completed:
                        flow.send("philosophy" if len(prefix) == 2 else "threaten" if not prefix else "removeObstacle")
                    self.assertFalse(completed.exception.value)
                    self.assertFalse(original_map.getBoolProperty("plugin_cityFlag_tamokoSpared"))
                    self.assertFalse(original_map.getBoolProperty("plugin_cityFlag_tamokoFought"))
                    self.assertEqual([], fixture.operations)

    def testAllTerminalsEraseOnlyAuditedSourceJournalIdsAndPeacefulSetsSharedMoveGlobal(self):
        for score, choices, peaceful in (
            (12, ["threaten"], False),
            (7, ["refuseHarm", "philosophy"], False),
            (12, ["refuseHarm", "philosophy"], True),
        ):
            fixture = TamokoFixture(score=score)
            self.assertTrue(fixture.settle(choices)[0])
            read = fixture.namespace["read"]
            self.assertEqual([111, 999], read(fixture.game_map, "plugin_cityCustodyJournal", []))
            self.assertEqual(
                {"GLOBAL:OTHER": 7, "GLOBAL:TamokoMove": 4 if peaceful else 2, "AR0800:TamokoMove": 3},
                read(fixture.game_map, "plugin_cityCustodyGlobals", {}),
            )
            self.assertEqual(4 if peaceful else 2, fixture.game_map.getNumericProperty("plugin_cityTamokoMove"))

    def testDialogueNeverAwardsGoldExperienceOrItemsAndPreservesActualActorInventory(self):
        for choices in (["threaten"], ["refuseHarm", "philosophy"]):
            fixture = TamokoFixture()
            inventory, equipment = tuple(fixture.actor.items), dict(fixture.actor.equipped)
            self.assertTrue(fixture.settle(choices)[0])
            self.assertEqual(
                (100, 0, []), (fixture.player.getGold(), fixture.player.getNumericProperty("exp"), fixture.player.items)
            )
            self.assertEqual(inventory, tuple(fixture.actor.items))
            self.assertEqual(equipment, fixture.actor.equipped)
            self.assertTrue(fixture.actor.isAlive())
            self.assertNotIn("TAMOKO", fixture.created)
            self.assertFalse(any(key.startswith("plugin_cityDeath_") for key in fixture.game_map.properties))

    def testRepeatedCompletedConversationDoesNotRepeatAnyTerminalOperation(self):
        for choices in (["threaten"], ["refuseHarm", "philosophy"]):
            fixture = TamokoFixture()
            self.assertTrue(fixture.settle(choices)[0])
            before = fixture.snapshot()
            self.assertFalse(fixture.dialog.canDiscussTamokoFinalMeeting())
            self.assertEqual((False, [], []), fixture.settle([]))
            self.assertEqual(before, fixture.snapshot())

    def testRejectedAndPartiallyFailedExistingEffectsDoNotWriteSourceTerminalMarkers(self):
        for outcome_key, unknown in (
            ("fight", {"gold": 1}),
            ("fight", {"xp": 1}),
            ("fight", {"standing": 1}),
            ("complete", {"items": []}),
            ("complete", {"clearTimer": True}),
        ):
            fixture = TamokoFixture()
            rows = questRows(fixture)
            outcome = next(row for row in rows[0]["outcomes"] if row["id"] == outcome_key)
            outcome["effects"].update(unknown)
            replaceQuestRows(fixture, rows)
            before = fixture.snapshot()
            choices = ["threaten"] if outcome_key == "fight" else ["refuseHarm", "philosophy"]
            self.assertFalse(fixture.settle(choices)[0])
            self.assertEqual(before, fixture.snapshot())
        fixture = TamokoFixture()
        original = fixture.actor.setStringProperty

        def failAfterAffiliation(name, value):
            original(name, value)
            if name == "affiliation":
                raise RuntimeError("partial captured hostility")

        fixture.actor.setStringProperty = failAfterAffiliation
        with self.assertRaisesRegex(RuntimeError, "partial captured hostility"):
            fixture.settle(["threaten"])
        self.assertFalse(fixture.game_map.getBoolProperty("plugin_cityFlag_tamokoFought"))
        self.assertEqual("fight", fixture.game_map.getStringProperty("plugin_cityTamokoFinalAttempt"))
        self.assertEqual("cityHostile", fixture.actor.getStringProperty("affiliation"))
        self.assertEqual([111, 999], fixture.namespace["read"](fixture.game_map, "plugin_cityCustodyJournal", []))
        self.assertFalse(fixture.game_map.getBoolProperty("plugin_cityOutcome_tamokoMercy_fight"))
        self.assertEqual("active", fixture.game_map.getStringProperty("plugin_cityQuest_tamokoMercy"))
        self.assertFalse(fixture.dialog.canDiscussTamokoFinalMeeting())

    def testNativeControllerAndJournalFailuresPreserveTheExceptionAndPreventReplay(self):
        for failure_at in ("controller", "journal"):
            fixture = TamokoFixture()
            failure = RuntimeError("actual helper failure")
            if failure_at == "controller":
                fixture.failure = failure
            else:
                original = fixture.game_map.setStringProperty

                def failingJournal(name, value):
                    original(name, value)
                    if name == "plugin_cityCustodyJournal":
                        raise failure

                fixture.game_map.setStringProperty = failingJournal
            with self.assertRaises(RuntimeError) as caught:
                fixture.settle(["threaten"])
            self.assertIs(failure, caught.exception)
            self.assertFalse(fixture.game_map.getBoolProperty("plugin_cityOutcome_tamokoMercy_fight"))
            remaining = fixture.namespace["read"](fixture.game_map, "plugin_cityCustodyJournal", [])
            self.assertEqual(
                [111, 999] if failure_at == "controller" else [111, 27462, 27463, 999],
                remaining,
            )
            self.assertEqual(
                2, fixture.namespace["read"](fixture.game_map, "plugin_cityCustodyGlobals", {})["GLOBAL:TamokoMove"]
            )
            self.assertFalse(fixture.dialog.canDiscussTamokoFinalMeeting())
            before = fixture.snapshot()
            self.assertEqual((False, [], []), fixture.settle([]))
            self.assertEqual(before, fixture.snapshot())

    def testRebindingDuringEffectsOrJournalStopsFurtherSourceAndQuestWrites(self):
        for at in ("effects", "journal"):
            fixture = TamokoFixture()
            old = fixture.game_map
            if at == "effects":
                original = old.setBoolProperty

                def rebindEffects(name, value):
                    original(name, value)
                    if name == "plugin_cityFlag_tamokoFought":
                        fixture.game_map = SourceMap(fixture.game)

                old.setBoolProperty = rebindEffects
            else:
                original = old.setStringProperty

                def rebindJournal(name, value):
                    original(name, value)
                    if name == "plugin_cityCustodyJournal":
                        fixture.game_map = SourceMap(fixture.game)

                old.setStringProperty = rebindJournal
            self.assertFalse(fixture.settle(["threaten"])[0])
            self.assertFalse(old.getBoolProperty("plugin_cityOutcome_tamokoMercy_fight"))
            self.assertEqual("active", old.getStringProperty("plugin_cityQuest_tamokoMercy"))
            self.assertEqual("active", fixture.game_map.getStringProperty("plugin_cityQuest_tamokoMercy"))
            remaining = fixture.namespace["read"](old, "plugin_cityCustodyJournal", [])
            self.assertEqual([111, 999] if at == "effects" else [111, 27462, 27463, 999], remaining)

    def testRebindingInsideTheJournalGetterCannotTouchOrReadTheReplacementMap(self):
        fixture = TamokoFixture()
        old = fixture.game_map
        replacement = SourceMap(fixture.game)
        fixture.namespace["write"](replacement, "plugin_cityCustodyJournal", [700])
        before = deepcopy(replacement.properties)
        foreign_reads = []
        for method in ("getObjectByName", "getPlayer", "getBoolProperty", "getNumericProperty", "getStringProperty"):
            saved = getattr(replacement, method)

            def observed(*args, _method=method, _saved=saved):
                foreign_reads.append((_method, args))
                return _saved(*args)

            setattr(replacement, method, observed)
        saved = old.getStringProperty
        fired = False

        def changed(name):
            nonlocal fired
            value = saved(name)
            if name == "plugin_cityCustodyJournal" and not fired:
                fired = True
                fixture.game_map = replacement
            return value

        old.getStringProperty = changed
        raised = None
        result = None
        try:
            result = fixture.settle(["threaten"])[0]
        except Exception as error:
            raised = error
        self.assertTrue(fired)
        self.assertIsNone(raised, repr(raised))
        self.assertIs(False, result)
        self.assertEqual(before, replacement.properties)
        self.assertEqual([], foreign_reads)
        self.assertEqual(
            [111, 27461, 27462, 27463, 999, 27461], fixture.namespace["read"](old, "plugin_cityCustodyJournal", [])
        )
        self.assertFalse(old.getBoolProperty("plugin_cityOutcome_tamokoMercy_fight"))

    def testRebindingInsideTheFirstSparedSetterCannotTouchOrReadTheReplacementMap(self):
        fixture = TamokoFixture()
        old = fixture.game_map
        replacement = SourceMap(fixture.game)
        before = deepcopy(replacement.properties)
        foreign_reads = []
        for method in ("getObjectByName", "getPlayer", "getBoolProperty", "getNumericProperty", "getStringProperty"):
            saved = getattr(replacement, method)

            def observed(*args, _method=method, _saved=saved):
                foreign_reads.append((_method, args))
                return _saved(*args)

            setattr(replacement, method, observed)
        saved = old.setBoolProperty
        fired = False

        def changed(name, value):
            nonlocal fired
            saved(name, value)
            if name == "plugin_cityFlag_tamokoSpared" and not fired:
                fired = True
                fixture.game_map = replacement

        old.setBoolProperty = changed
        raised = None
        result = None
        try:
            result = fixture.settle(["refuseHarm", "philosophy"])[0]
        except Exception as error:
            raised = error
        self.assertTrue(fired)
        self.assertIsNone(raised, repr(raised))
        self.assertIs(False, result)
        self.assertEqual(before, replacement.properties)
        self.assertEqual([], foreign_reads)
        self.assertFalse(old.getBoolProperty("plugin_cityFlag_tamokoMove4"))
        self.assertFalse(old.getBoolProperty("plugin_cityOutcome_tamokoMercy_complete"))

    def testActorReplacementInsideMetadataGetterInvalidatesTheCapturedBinding(self):
        for replace in (False, True):
            f = TamokoFixture()
            binding = f.dialog.tamokoFinalBinding()
            saved = f.registry.getStringProperty
            fired = False

            def changed(name):
                nonlocal fired
                value = saved(name)
                if name == "questDefinitions" and not fired:
                    fired = True
                    if replace:
                        f.game_map.addObject(
                            SourceCreature(f.game, ACTOR, sourceCreature="TAMOKO", sourceArea="AR0123", label="Tamoko")
                        )
                    else:
                        f.game_map.objects.pop(ACTOR)
                return value

            f.registry.getStringProperty = changed
            self.assertIsNone(f.dialog.tamokoFinalBinding(binding))
            self.assertTrue(fired)
            self.assertFalse(f.game_map.getBoolProperty("plugin_cityFlag_tamokoFought"))
            self.assertFalse(f.game_map.getBoolProperty("plugin_cityFlag_tamokoSpared"))

    def testAnOppositeOutcomeInjectedByTheFirstFlagSetterStopsFinalization(self):
        for complete in (False, True):
            for outcome_marker in (False, True):
                f = TamokoFixture()
                selected = "tamokoSpared" if complete else "tamokoFought"
                opposite = (
                    "plugin_cityOutcome_tamokoMercy_" + ("fight" if complete else "complete")
                    if outcome_marker
                    else "plugin_cityFlag_" + ("tamokoFought" if complete else "tamokoSpared")
                )
                saved = f.game_map.setBoolProperty

                def contradict(name, value):
                    saved(name, value)
                    if name == "plugin_cityFlag_" + selected:
                        saved(opposite, True)

                f.game_map.setBoolProperty = contradict
                choices = ["refuseHarm", "philosophy"] if complete else ["threaten"]
                self.assertFalse(f.settle(choices)[0])
                self.assertTrue(f.game_map.getBoolProperty("plugin_cityFlag_" + selected))
                self.assertTrue(f.game_map.getBoolProperty(opposite))
                self.assertEqual("active", f.game_map.getStringProperty("plugin_cityQuest_tamokoMercy"))
                self.assertEqual(
                    [111, 999],
                    f.namespace["read"](f.game_map, "plugin_cityCustodyJournal", []),
                )
                self.assertEqual(
                    4 if complete else 2,
                    f.namespace["read"](f.game_map, "plugin_cityCustodyGlobals", {})["GLOBAL:TamokoMove"],
                )
                self.assertEqual([] if complete else ["CTargetController"], f.created)
                self.assertEqual(complete, f.actor.getBoolProperty("plugin_cityDeparted"))
                self.assertEqual(complete, f.game_map.getObjectByName(ACTOR) is None)
                self.assertFalse(f.dialog.canDiscussTamokoFinalMeeting())

    def testCapturedMetadataAcceptsTheAuthoredDocumentAndExplicitLegacyList(self):
        for legacy in (False, True):
            f = TamokoFixture()
            document = f.namespace["read"](f.registry, "questDefinitions", [])
            self.assertIsInstance(document, dict)
            self.assertEqual([], document["excursions"])
            if legacy:
                f.namespace["write"](f.registry, "questDefinitions", document["quests"])
            self.assertIsNotNone(f.dialog.tamokoFinalBinding())
            self.assertTrue(f.settle(["refuseHarm", "philosophy"])[0])
        for invalid in ({"quests": {}}, {"excursions": []}, None):
            f = TamokoFixture()
            f.namespace["write"](f.registry, "questDefinitions", invalid)
            before = f.snapshot()
            self.assertFalse(f.dialog.canDiscussTamokoFinalMeeting())
            self.assertEqual((False, [], []), f.settle([]))
            self.assertEqual(before, f.snapshot())

    def testCapturedPreflightRetainsAuthoredConditionsAndAvoidsLazyHelpers(self):
        fixture = TamokoFixture()

        def forbidden(*args):
            raise AssertionError("generic lazy helper entered")

        native_membership_player = fixture.game_map.getPlayer
        fixture.game_map.getPlayer = forbidden
        fixture.player.getItems = forbidden
        fixture.actor.getItems = forbidden
        fixture.namespace["applyEffects"] = forbidden
        fixture.source.journal = forbidden
        fixture.source.setGlobal = forbidden
        self.assertTrue(fixture.dialog.canDiscussTamokoFinalMeeting())
        # The real mapQuest journal wrapper reads active membership through getPlayer.
        fixture.game_map.getPlayer = native_membership_player
        self.assertTrue(fixture.settle(["refuseHarm", "philosophy"])[0])
        for key, value in (
            ("plugin_cityFlag_cityCompleted", True),
            ("plugin_cityFlag_poisonFatal", True),
            ("plugin_cityCustodyState", "hearing"),
            ("plugin_cityQuest_tamokoMercy", "notStarted"),
        ):
            f = TamokoFixture()
            f.game_map.properties[key] = value
            before = f.snapshot()
            self.assertFalse(f.dialog.canDiscussTamokoFinalMeeting())
            self.assertEqual((False, [], []), f.settle([]))
            self.assertEqual(before, f.snapshot())
        for target in (
            "giver",
            "fightConditions",
            "actorLabel",
            "petrified",
            "actorPhase",
            "rowPhase",
            "acceptConditions",
            "acceptEffects",
        ):
            f = TamokoFixture()
            if target in ("giver", "fightConditions", "rowPhase", "acceptConditions", "acceptEffects"):
                rows = questRows(f)
                if target == "giver":
                    rows[0]["givers"] = [{"label": "Somebody else", "area": "AR0123"}]
                elif target == "rowPhase":
                    rows[0]["phase"] = 6
                elif target == "acceptConditions":
                    rows[0]["acceptConditions"]["flags"].append("newUnreviewedFlag")
                elif target == "acceptEffects":
                    rows[0]["acceptEffects"] = {"gold": 1}
                else:
                    next(row for row in rows[0]["outcomes"] if row["id"] == "fight")["conditions"] = {
                        "flags": ["newUnreviewedFlag"]
                    }
                replaceQuestRows(f, rows)
            elif target == "actorLabel":
                f.actor.setStringProperty("label", "Somebody else")
            elif target == "petrified":
                f.actor.setBoolProperty("plugin_cityPetrified", True)
            else:
                f.actor.setNumericProperty("phaseMax", 6)
            before = f.snapshot()
            self.assertFalse(f.dialog.canDiscussTamokoFinalMeeting())
            self.assertEqual((False, [], []), f.settle([]))
            self.assertEqual(before, f.snapshot())

    def testRequestConstructionAndMalformedRepliesCannotAdvanceAStaleFlow(self):
        for target in ("flowGame", "uiRequest"):
            f = TamokoFixture()
            old, replacement = f.game_map, SourceMap(f.game)
            before = deepcopy(old.properties)
            saved = f.namespace[target]

            def rebind(*args):
                request = saved(*args)
                f.game_map = replacement
                return request

            f.namespace[target] = rebind
            with self.assertRaises(StopIteration) as stopped:
                next(f.dialog.discussTamokoFinalMeeting())
            self.assertIs(False, stopped.exception.value)
            self.assertEqual(before, old.properties)
            self.assertEqual([], f.operations)
        for reply in ({"id": "threaten"}, ["threaten"], True):
            f = TamokoFixture()
            before = f.snapshot()
            self.assertFalse(f.settle([reply])[0])
            self.assertEqual(before, f.snapshot())

    def testPostcommitAwaitRechecksContextBeforeSchedulesOrFurtherReaderRequests(self):
        for at in ("questUi", "reader"):
            fixture = TamokoFixture()
            flow = fixture.dialog.discussTamokoFinalMeeting()
            next(flow)
            self.assertEqual("gui.checkQuests", flow.send("threaten")["operation"])
            if at == "reader":
                fixture.player.checkQuests()
                self.assertEqual("showReader", flow.send(None)["operation"])
            old = fixture.game_map
            previous_operations = list(fixture.operations)
            fixture.game_map = SourceMap(fixture.game)
            with self.assertRaises(StopIteration) as stopped:
                flow.send(None)
            self.assertFalse(stopped.exception.value)
            self.assertTrue(old.getBoolProperty("plugin_cityOutcome_tamokoMercy_fight"))
            self.assertEqual(previous_operations, fixture.operations)

    def testNaturalAuthoredRowsEnterTheSequenceAndKeepDirectCallbacksCompatibilityOnly(self):
        builder = ast.parse(BUILDER.read_text(encoding="utf-8"))
        row_method = next(
            node for node in builder.body if isinstance(node, ast.FunctionDef) and node.name == "questDialogRows"
        )
        branches = [
            node
            for node in ast.walk(row_method)
            if isinstance(node, ast.If) and ast.unparse(node.test) == "quest['id'] == 'tamokoMercy'"
        ]
        self.assertEqual(1, len(branches))
        entries = [ast.literal_eval(node) for node in ast.walk(branches[0]) if isinstance(node, ast.Dict)]
        self.assertEqual(
            [
                {
                    "text": "Discuss Tamoko's final stand.",
                    "action": "discussTamokoFinalMeeting",
                    "condition": "canDiscussTamokoFinalMeeting",
                    "questId": "tamokoMercy",
                }
            ],
            entries,
        )
        self.assertTrue(any(isinstance(node, ast.Continue) for node in branches[0].body))
        definition = configuredDialog()
        state = definition["properties"]["states"][0]["properties"]
        actions = [row["properties"].get("action") for row in state["options"]]
        self.assertEqual(1, actions.count("discussTamokoFinalMeeting"))
        self.assertNotIn("questTamokoMercyComplete", actions)
        self.assertNotIn("questTamokoMercyFight", actions)
        self.assertIn("acceptTamokoMercy", actions)
        source = SCRIPT.read_text(encoding="utf-8")
        for name in ("questTamokoMercyComplete", "questTamokoMercyFight"):
            method = next(
                node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name == name
            )
            self.assertIn("performQuestOutcomeFlow", ast.get_source_segment(source, method))

    def testLegacyMirrorFinalErasesNeverCreateMissingInformationalNotes(self):
        for choices in (["threaten"], ["refuseHarm", "philosophy"]):
            f = TamokoFixture()
            f.player.quests = f.player.quests[:1]
            unrelated = SourceObject(f.game, "unrelatedActive", questJournalObjective="original")
            completed = SourceObject(f.game, "unrelatedCompleted", questJournalCompleted=True)
            f.player.quests.append(unrelated)
            f.player.completed.append(completed)

            def forbidden(name):
                self.fail("Source EraseJournalEntry must not add a note: " + name)

            f.player.addQuest = forbidden
            self.assertTrue(f.settle(choices)[0])
            self.assertEqual([unrelated], f.player.quests)
            self.assertEqual({completed, f.player.completed[-1]}, set(f.player.completed))
            self.assertEqual("original", unrelated.getStringProperty("questJournalObjective"))
            self.assertEqual([111, 999], f.namespace["read"](f.game_map, "plugin_cityCustodyJournal", []))
            self.assertEqual([] if len(choices) == 2 else ["CTargetController"], f.created)

    def testFinalSourceWritesPrecedeOutcomePublicationAndFailuresNeverCompleteTheQuest(self):
        for terminal, score in ((21, 12), (24, 9), (25, 12)):
            successful = TamokoFixture(score=score)
            writes = []

            def instrument(f, target=None, when=None):
                count = [0]

                def wrap(obj, method, qualifies):
                    saved = getattr(obj, method)

                    def call(*args):
                        if qualifies(args):
                            count[0] += 1
                            ordinal = count[0]
                            writes.append((terminal, method, args[0] if args else "EscapeArea"))
                            self.assertEqual("active", f.game_map.getStringProperty("plugin_cityQuest_tamokoMercy"))
                            self.assertFalse(f.game_map.getBoolProperty("plugin_cityOutcome_tamokoMercy_complete"))
                            self.assertFalse(f.game_map.getBoolProperty("plugin_cityOutcome_tamokoMercy_fight"))
                            if ordinal == target and when == "before":
                                raise failure
                            value = saved(*args)
                            if ordinal == target and when == "after":
                                raise failure
                            return value
                        return saved(*args)

                    setattr(obj, method, call)

                wrap(
                    f.game_map,
                    "setStringProperty",
                    lambda a: a[0] in ("plugin_cityCustodyJournal", "plugin_cityCustodyGlobals"),
                )
                wrap(f.game_map, "setNumericProperty", lambda a: a[0] == "plugin_cityTamokoMove")
                wrap(f.actor, "setBoolProperty", lambda a: a[0] in ("npc", "plugin_cityDeparted"))
                wrap(f.actor, "setStringProperty", lambda a: a[0] == "affiliation")
                wrap(f.actor, "setController", lambda a: True)
                wrap(f.registry, "applySchedules", lambda a: True)
                return count

            failure = RuntimeError("source terminal write failure")
            count = instrument(successful)
            self.assertTrue(
                successful.dialog.commitTamokoFinalMeeting(successful.dialog.tamokoFinalBinding(), terminal)
            )
            sequence = [entry[2] for entry in writes]
            self.assertEqual(["plugin_cityCustodyJournal"] * 3, sequence[:3])
            self.assertEqual("plugin_cityCustodyGlobals" if terminal == 25 else "npc", sequence[3])
            if terminal == 25:
                self.assertEqual(["plugin_cityTamokoMove", "plugin_cityDeparted", "EscapeArea"], sequence[4:])
            total = count[0]
            for ordinal in range(1, total + 1):
                for when in ("before", "after"):
                    with self.subTest(terminal=terminal, ordinal=ordinal, when=when):
                        f = TamokoFixture(score=score)
                        instrument(f, ordinal, when)
                        with self.assertRaises(RuntimeError) as caught:
                            f.dialog.commitTamokoFinalMeeting(f.dialog.tamokoFinalBinding(), terminal)
                        self.assertIs(failure, caught.exception)
                        self.assertEqual("active", f.game_map.getStringProperty("plugin_cityQuest_tamokoMercy"))
                        self.assertFalse(f.game_map.getBoolProperty("plugin_cityFlag_tamokoSpared"))
                        self.assertFalse(f.game_map.getBoolProperty("plugin_cityFlag_tamokoFought"))
                        self.assertFalse(f.game_map.getBoolProperty("plugin_cityOutcome_tamokoMercy_complete"))
                        self.assertFalse(f.game_map.getBoolProperty("plugin_cityOutcome_tamokoMercy_fight"))
                        self.assertFalse(f.dialog.canDiscussTamokoFinalMeeting())
                        self.assertEqual((100, 0), (f.player.getGold(), f.player.getNumericProperty("exp")))
                        self.assertEqual([], f.player.completed)

    def testCapturedFinalEpochUsesValueEqualityAndRejectsMalformedOrOldTuples(self):
        f = TamokoFixture()
        f.game.getMapBindingEpoch = lambda: int("1000")
        binding = f.dialog.tamokoFinalBinding()
        copy = (*binding[:-1], int("1000"))
        self.assertIsNot(binding[-1], copy[-1])
        self.assertIsNotNone(f.dialog.tamokoFinalBinding(copy))
        for invalid in (
            (),
            binding[:-1],
            (*binding[:-1], True),
            (*binding[:-1], "1000"),
            (*binding[:-1], 1001),
            list(binding),
        ):
            with self.subTest(invalid=invalid):
                self.assertIsNone(f.dialog.tamokoFinalBinding(invalid))

    def testAwayAndBackEpochStopsFinalUiStatsAndFirstSourceWrite(self):
        for at in ("ui", "stats", "setter"):
            with self.subTest(at=at):
                f = TamokoFixture()
                epoch = [1000]
                f.game.getMapBindingEpoch = lambda: epoch[0]
                binding = f.dialog.tamokoFinalBinding()
                if at == "ui":
                    flow = f.dialog.discussTamokoFinalMeeting()
                    next(flow)
                    epoch[0] += 2
                    with self.assertRaises(StopIteration) as ended:
                        flow.send("threaten")
                    self.assertFalse(ended.exception.value)
                elif at == "stats":
                    saved = f.player.stats.getNumericProperty

                    def stat(name):
                        epoch[0] += 2
                        return saved(name)

                    f.player.stats.getNumericProperty = stat
                    self.assertIsNone(f.dialog.tamokoFinalScore(binding))
                else:
                    saved = f.game_map.setStringProperty

                    def write(name, value):
                        saved(name, value)
                        if name == "plugin_cityTamokoFinalAttempt":
                            epoch[0] += 2

                    f.game_map.setStringProperty = write
                    self.assertFalse(f.dialog.commitTamokoFinalMeeting(binding, 21))
                self.assertEqual(
                    [111, 27461, 27462, 27463, 999, 27461],
                    f.namespace["read"](f.game_map, "plugin_cityCustodyJournal", []),
                )
                self.assertEqual("active", f.game_map.getStringProperty("plugin_cityQuest_tamokoMercy"))
                self.assertEqual([], f.created)

    def testHostileTamokoCannotStartOrResumeAFinalConversation(self):
        for key, value in (("npc", False), ("affiliation", "cityHostile")):
            for resume in (False, True):
                with self.subTest(key=key, resume=resume):
                    f = TamokoFixture()
                    flow = f.dialog.discussTamokoFinalMeeting()
                    if resume:
                        next(flow)
                    f.actor.properties[key] = value
                    before = f.snapshot()
                    self.assertFalse(f.dialog.canDiscussTamokoFinalMeeting())
                    if resume:
                        with self.assertRaises(StopIteration) as stopped:
                            flow.send("threaten")
                        self.assertFalse(stopped.exception.value)
                    else:
                        self.assertFalse(f.settle([])[0])
                    self.assertEqual(before, f.snapshot())

    def testAuthoredAttackInvalidatesThePendingFriendlyFinalChoice(self):
        f = TamokoFixture()
        self.assertTrue(f.dialog.canDiscussTamokoFinalMeeting())
        flow = f.dialog.discussTamokoFinalMeeting()
        next(flow)
        with self.assertRaises(StopIteration) as attack:
            next(f.dialog.attack())
        self.assertTrue(attack.exception.value)
        self.assertFalse(f.actor.isNpc())
        self.assertEqual("cityHostile", f.actor.getStringProperty("affiliation"))
        before = f.snapshot()
        with self.assertRaises(StopIteration) as rejected:
            flow.send("threaten")
        self.assertFalse(rejected.exception.value)
        self.assertEqual(before, f.snapshot())
        self.assertFalse(f.dialog.canDiscussTamokoFinalMeeting())

    def testCanonicalEntryHasFullTamokoActionsInsteadOfGenericSpeak(self):
        options = configuredDialog()["properties"]["states"][0]["properties"]["options"]
        actions = [option["properties"].get("action") for option in options]
        self.assertNotIn("talk", actions, "Tamoko cannot offer the unrelated generic city Speak path")
        self.assertEqual(list(range(len(options))), [option["properties"]["number"] for option in options])
        for name in (
            "discussTamokoFirstMeeting",
            "discussTamokoSecondMeeting",
            "discussTamokoFinalMeeting",
            "showInventory",
            "pickPocket",
            "attack",
            "acceptTamokoMercy",
            "questCythandriaDiaryComplete",
        ):
            self.assertEqual(1, actions.count(name))
        self.assertEqual(
            1,
            sum(
                option["properties"].get("nextStateId") == "EXIT" and "action" not in option["properties"]
                for option in options
            ),
        )


if __name__ == "__main__":
    unittest.main()
