# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual bounded custody callbacks over compact doubles; no native/save/parity evidence."""

import ast
import builtins
from copy import deepcopy
from functools import wraps
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from weakref import ref

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get("CUSTODY_SCRIPT_PATH", ROOT / "res/maps/baldursGate/script.py"))
BUILDER = ROOT / "scripts/build_baldurs_gate_city.py"
FIXTURE = ROOT / "tests/fixtures/baldurs_gate_city_prison_source.json"
PIN = "11bd856e1a5bffd4a2ab4b8b34d4b31e8cf54240f7dd4de78e2329d2c3bd3449"


def boundedFixture():
    payload = FIXTURE.read_bytes()
    if len(payload) > 192 * 1024 or sha256(payload.replace(b"\r\n", b"\n")).hexdigest() != PIN:
        raise ValueError("Fixed bounded prison evidence changed")
    return json.loads(payload)


def loadHelper():
    spec = importlib.util.spec_from_file_location(
        "bounded_custody_helper", ROOT / "scripts/build_baldurs_gate_city_custody.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def selectedSupport(path, names, namespace):
    """Execute actual generic decorators only; no engine or whole-city generator import."""
    source = path.read_text(encoding="utf-8")
    nodes = [node for node in ast.parse(source).body if getattr(node, "name", None) in names]
    if {node.name for node in nodes} != set(names):
        raise AssertionError("Missing selected generic support")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)


class NativeObject:
    def __init__(self):
        self.properties = {}
        self.game = None
        self.kind = ""
        self.controller = None
        self.hp = 10
        self.items = []
        self.quests = []
        self.completed = []

    def __getattr__(self, name):
        if name in self.properties:
            return self.properties[name]
        raise AttributeError(name)

    def getGame(self):
        return self.game

    def getMap(self):
        return self.game.getMap()

    def getName(self):
        return self.properties.get("name", "")

    def getTypeId(self):
        return self.kind

    def getStringProperty(self, key):
        return self.properties.get(key, "")

    def getNumericProperty(self, key):
        return self.properties.get(key, 0)

    def getBoolProperty(self, key):
        return bool(self.properties.get(key, False))

    def getObjectProperty(self, key):
        return self.properties.get(key)

    def setStringProperty(self, key, value):
        self.properties[key] = value

    setNumericProperty = setStringProperty
    setBoolProperty = setStringProperty
    setObjectProperty = setStringProperty

    def isAlive(self):
        return self.hp > 0

    def setHp(self, value):
        before, self.hp = self.hp, value
        if before > 0 and value <= 0 and self.game.fixture.death_trigger:
            list(self.game.fixture.death_trigger.triggerFlow(self, None))

    def getController(self):
        return self.controller

    def setController(self, value):
        self.controller = value

    def getCoords(self):
        return SimpleNamespace(**dict(zip(("x", "y", "z"), self.properties.get("coords", (0, 0, 0)))))

    def relocateWithoutMoveHooks(self, point):
        self.properties["coords"] = [point.x, point.y, point.z]

    def isPlayer(self):
        return self.getBoolProperty("player")

    def getItems(self):
        return list(self.items)

    def getEquipped(self):
        return {}

    def getQuests(self):
        return list(self.quests)

    def getCompletedQuests(self):
        return list(self.completed)

    def addQuest(self, key):
        self.quests.append(self.game.createObject(key))

    def checkQuests(self):
        for quest in tuple(self.quests):
            if quest.isCompleted():
                quest.captureJournal(True)
                self.quests.remove(quest)
                self.completed.append(quest)


class Creature(NativeObject):
    pass


class Player(Creature):
    pass


class CompactContext:
    def __init__(self):
        self.generation = 0
        self.active = True

    def getTransitionGeneration(self):
        return self.generation

    def isTransitionGenerationCurrent(self, value):
        return self.active and value == self.generation


class CompactGame:
    """A model of the separately pinned native API, not native execution evidence."""

    def __init__(self, fixture):
        self.fixture = fixture
        self.map_epoch = 0

    def getMap(self):
        return self.fixture.world

    def getMapBindingEpoch(self):
        return self.map_epoch

    def setMap(self, game_map):
        if self.fixture.world is not game_map:
            self.map_epoch += 1
            self.fixture.world = game_map


class Quest(NativeObject):
    def isCompleted(self):
        return False

    def getObjective(self):
        return ""

    getReward = getObjective
    getHint = getObjective


class CompactMap(NativeObject):
    mapName = "baldursGate"

    def __init__(self):
        super().__init__()
        self.objects = {}

    def addObject(self, obj):
        self.objects[obj.getName()] = obj

    def removeObject(self, obj):
        self.objects.pop(obj.getName(), None)

    def getObjectByName(self, name):
        return self.objects.get(name)

    def getObjects(self):
        return set(self.objects.values())

    def getAssignedPlayer(self):
        """Explicit double of query API9f6df499; no native cache execution proof."""
        return self.player

    def getPlayer(self):
        return self.player


def compactSource(audit, helper):
    areas = {name: {"actors": []} for name in [*helper.DISTRICTS, "AR0607"]}
    for index, row in enumerate(audit["prison"]["actors"], 1):
        areas["AR0607"]["actors"].append(
            {"creature": row["creature"], "nativeId": helper.identity("AR0607#actor" + str(index))}
        )
    return {"areas": areas, "creatures": deepcopy(audit["creatures"])}


class Fixture:
    """No native object, GUI reply, geometry, serialization or controller scheduling is simulated as proof."""

    def __init__(self, source=None):
        self.classes = {}
        self.created = []
        self.death_trigger = None
        self.world = CompactMap()
        self.game = CompactGame(self)
        self.game.createObject = self.createObject
        self.game.fixture = self
        self.context = CompactContext()
        self.game.getContext = lambda: self.context
        self.world.game = self.game
        support = Path(os.environ.get("CUSTODY_GENERIC_ROOT", ROOT))
        generic = {"wraps": wraps, "ref": ref, "uiGame": lambda obj: obj, "runUiFlow": lambda *_: None}
        selectedSupport(
            support / "res/ui.py", {"ResumableHook", "UiFlowGame", "resumableHook", "uiRequest", "flowGame"}, generic
        )
        selectedSupport(support / "res/game.py", {"register"}, generic)
        quest_generic = {"wraps": wraps, "QUEST_JOURNAL_VERSION": 1, "QUEST_JOURNAL_UNAVAILABLE_HINT": "Unavailable"}
        selectedSupport(support / "quest_state.py", {"mapQuest"}, quest_generic)
        exports = {
            "CBuilding": NativeObject,
            "CCreature": Creature,
            "CGameObject": NativeObject,
            "CGame": CompactGame,
            "CMap": CompactMap,
            "CPlayer": Player,
            "CDialog": NativeObject,
            "CEvent": NativeObject,
            "CQuest": Quest,
            "CTrigger": NativeObject,
            "Coords": lambda x, y, z: SimpleNamespace(x=x, y=y, z=z),
            "mapQuest": quest_generic["mapQuest"],
            "claim_once": self.claimOnce,
            "randint": lambda _low, _high: self.roll,
            **{name: generic[name] for name in ("register", "resumableHook", "uiRequest", "flowGame")},
        }
        self.imported = []

        def restrictedImport(name, *args, **kwargs):
            self.imported.append(name)
            if name == "game":
                return SimpleNamespace(**exports)
            if name == "json":
                return json
            raise ImportError("Map plugin import is not permitted: " + name)

        namespace = {"__builtins__": {**vars(builtins), "__import__": restrictedImport}}
        source = source if source is not None else SCRIPT.read_text(encoding="utf-8")
        exec(compile(source, str(SCRIPT), "exec"), namespace)
        context = SimpleNamespace(getObjectHandler=lambda: SimpleNamespace(registerType=self.classes.__setitem__))
        namespace["load"](None, context)
        self.namespace = namespace
        self.roll = 3
        self.player = self.object(Player, "player")
        self.player.setBoolProperty("player", True)
        self.player.setNumericProperty("gold", 27)
        self.player.setNumericProperty("exp", 19)
        self.world.player = self.player
        self.clock = self.object(self.classes["BaldursGateClock"], "cityClock")
        self.clock.initializeActor = lambda _actor: None
        self.clock.advanceTicks = lambda count: self.world.setNumericProperty(
            "plugin_cityTicks", self.world.getNumericProperty("plugin_cityTicks") + count
        )
        self.schedules = 0
        self.clock.applySchedules = self.applySchedules
        self.world.setNumericProperty("plugin_cityPhase", 7)
        self.world.setStringProperty("activeSimulationRegion", "AR0800")
        self.world.setBoolProperty("plugin_cityHistoryFrozen", True)
        self.owner = None
        self.data = {}
        self.catalog = {}

    def applySchedules(self):
        self.schedules += 1

    @staticmethod
    def claimOnce(obj, key):
        if obj.getBoolProperty(key):
            return False
        obj.setBoolProperty(key, True)
        return True

    def object(self, cls, name):
        obj = cls()
        obj.game, obj.kind = self.game, name
        obj.setStringProperty("name", name)
        self.world.addObject(obj)
        return obj

    def createObject(self, name):
        self.created.append(name)
        cls = (
            self.classes["BaldursGateCustodyQuest"]
            if name == "cityCustodyQuest"
            else Creature if name in self.catalog else NativeObject
        )
        obj = cls()
        obj.game, obj.kind = self.game, name
        obj.setStringProperty("name", name)
        obj.properties.update(self.catalog.get(name, {}))
        return obj

    def installCustody(self):
        if "BaldursGateCustody" not in self.classes:
            raise AssertionError("Actual custody class is not registered")
        self.helper, audit = loadHelper(), boundedFixture()
        source = compactSource(audit, self.helper)
        self.helper.prepareCustodyActors(source, audit)
        allocated = set()

        def project(area, point, reserve=False):
            x, y, z = point[0] // 32, point[1] // 32, int(area[2:])
            while reserve and (x, y, z) in allocated:
                x += 1
            if reserve:
                allocated.add((x, y, z))
            return x, y, z

        self.data = self.helper.custodyDefinitions(audit, project)
        self.owner = self.object(self.classes["BaldursGateCustody"], "cityCustody")
        self.owner.setStringProperty("custodyDefinitions", json.dumps(self.data))
        rows = []
        for area, entry in source["areas"].items():
            for row in entry["actors"]:
                code = row["creature"]
                props = {
                    "sourceArea": area,
                    "sourceCreature": code,
                    "sourceDialogue": row.get("dialogue") or audit["creatures"].get(code, {}).get("dialogue", ""),
                    "label": "Flaming Fist" if code.startswith(("FLAM", "FFH")) else code,
                    "npc": True,
                }
                self.catalog[row["nativeId"]] = props
                if row.get("scriptedPolicy"):
                    rows.append(
                        {"id": row["nativeId"], "x": 0, "y": 0, "z": 0, "phase": 7, "custodyRole": row["custodyRole"]}
                    )
                else:
                    self.world.addObject(self.createObject(row["nativeId"]))
        self.clock.setStringProperty("actorDefinitions", json.dumps(rows))
        self.death_trigger = self.object(self.classes["BaldursGateDeathTrigger"], "deathTrigger")
        self.owner.updatePatrols()
        return self.owner.participant(self.data["patrols"]["AR0800"]["actors"][0])

    def dialog(self, actor):
        obj = self.object(self.classes["BaldursGateDialog"], "dialog")
        obj.setStringProperty("actorId", actor.getName())
        return obj

    def runDialogue(self, actor, choices=()):
        pending, answer, requests = iter(choices), None, []
        flow = self.owner.conversationFlow(actor)
        for _index in range(128):
            try:
                request = flow.send(answer)
            except StopIteration:
                if list(pending):
                    raise AssertionError("Unused planned source answers")
                return requests
            requests.append(request)
            if request["operation"] == "choose":
                answer = next(pending, "")
                if answer not in ["", *(row["id"] for row in request["args"][2])]:
                    raise AssertionError("Answer not offered by actual callback")
            elif request["operation"] == "gui.checkQuests":
                answer = self.player.checkQuests()
            elif request["operation"] == "showReader":
                answer = None
            else:
                raise AssertionError("Unexpected source UI request")
        raise AssertionError("Actual callback exceeded focused test budget")

    def stored(self, key, default):
        return self.namespace["decodeData"](self.world.getStringProperty(key) or json.dumps(default))


class BaldursGateCustodySourceTest(unittest.TestCase):
    def setUp(self):
        self.model = Fixture()

    def testExistingDialogRejectsHearingWithoutNewOptionalArgument(self):
        m = self.model
        actor = m.object(Creature, "guard")
        dialog = m.dialog(actor)
        m.world.setStringProperty("plugin_cityCustodyState", "hearing")
        self.assertFalse(dialog.canInteract())

    def testExistingPortalRejectsHearingBeforeTravel(self):
        m = self.model
        portal = m.object(m.classes["BaldursGatePortal"], "portal")
        portal.setStringProperty("destinationArea", "AR0800")
        portal.setNumericProperty("targetX", 2)
        m.world.setStringProperty("plugin_cityCustodyState", "hearing")
        self.assertFalse(portal.usable())

    def testExistingTalkDelegatesActualCustodyConversation(self):
        m = self.model
        actor = m.object(Creature, "guard")
        actor.setStringProperty("sourceDialogue", "FFHUNT")
        owner = m.object(NativeObject, "cityCustody")
        owner.data = lambda: {"dialogues": {"FFHUNT": []}}
        owner.conversationFlow = lambda _actor: iter([{"operation": "source-custody-model-marker"}])
        self.assertEqual("source-custody-model-marker", next(m.dialog(actor).talkFlow())["operation"])

    def testExistingDeathTriggerDoesNotCountPlotExecutionAsGuardCrime(self):
        m = self.model
        actor = m.object(Creature, "escort")
        actor.hp = 0
        actor.setStringProperty("label", "Flaming Fist escort")
        actor.setStringProperty("sourceArea", "AR0607")
        actor.setBoolProperty("plugin_cityPlotExecution", True)
        trigger = m.object(m.classes["BaldursGateDeathTrigger"], "death")
        list(trigger.triggerFlow(actor, None))
        self.assertEqual(0, m.world.getNumericProperty("plugin_cityGuardKills"))
        self.assertFalse(m.world.getBoolProperty("plugin_cityCombatObserved_AR0607"))
        self.assertIs(actor, m.clock.getObjectProperty("plugin_cityCorpse_escort"))
        self.assertIn("escort", m.stored("plugin_cityDeaths", {}))

    def testExistingSpawnDefersOnlyCustodyActors(self):
        m = self.model
        rows = [
            {"id": "guard", "x": 0, "y": 0, "z": 0, "phase": 7, "custodyRole": "patrol"},
            {"id": "ordinary", "x": 1, "y": 0, "z": 0, "phase": 7},
        ]
        m.clock.setStringProperty("actorDefinitions", json.dumps(rows))
        m.clock.spawnActors()
        self.assertIsNone(m.world.getObjectByName("guard"))
        self.assertIsNotNone(m.world.getObjectByName("ordinary"))

    def testExistingTurnUpdatesCustodyBetweenTicksAndObservation(self):
        m, events = self.model, []
        owner = m.object(NativeObject, "cityCustody")
        owner.updatePatrols = lambda: events.append("custody")
        m.clock.advanceTicks = lambda _count: events.append("ticks")
        m.clock.observeRegionsFlow = lambda: iter([{"operation": "observed"}])
        m.world.setBoolProperty("plugin_cityInitialized", True)
        flow = m.clock.onTurnFlow(None)
        self.assertEqual({"operation": "observed"}, next(flow))
        self.assertEqual(["ticks", "custody"], events)
        flow.close()

    def testFullRestrictedPluginLoadUsesConstructibleBaseAndActualDecorators(self):
        m = self.model
        self.assertIn("BaldursGateCustody", m.classes)
        self.assertIn("BaldursGateCustodyQuest", m.classes)
        self.assertTrue(issubclass(m.classes["BaldursGateCustody"], NativeObject))
        self.assertTrue(issubclass(m.classes["BaldursGateCustodyQuest"], Quest))
        self.assertEqual({"game", "json"}, set(m.imported))
        self.assertNotIn("BaldursGateActor", m.classes)
        load = next(
            node for node in ast.parse(SCRIPT.read_text(encoding="utf-8")).body if getattr(node, "name", None) == "load"
        )
        classes = {node.name: node for node in load.body if isinstance(node, ast.ClassDef)}
        for name, base, decorators in (
            ("BaldursGateCustody", "CBuilding", ["register(context)"]),
            ("BaldursGateCustodyQuest", "CQuest", ["register(context)", "mapQuest('baldursGate')"]),
        ):
            self.assertEqual([base], [ast.unparse(node) for node in classes[name].bases])
            self.assertEqual(decorators, [ast.unparse(node) for node in classes[name].decorator_list])
            self.assertNotIn("__init__", [getattr(node, "name", None) for node in classes[name].body])
        m.installCustody()
        m.owner.ensureQuest()
        self.assertEqual(["cityCustodyQuest"], [entry.getTypeId() for entry in m.player.getQuests()])
        self.assertIn("Flaming Fist", m.player.getQuests()[0].getObjective())

    def testHearingResumeRequiresActualCursorOwnerAndHeadquarters(self):
        m = self.model
        m.runDialogue(m.installCustody(), ["0", ""])
        angelo = m.owner.participant("ANGELO")
        dialog = m.dialog(angelo)
        self.assertFalse(dialog.canInteract())
        self.assertTrue(dialog.canInteract(resume_custody=True))
        m.world.setStringProperty("activeSimulationRegion", "AR0800")
        self.assertFalse(dialog.canInteract(resume_custody=True))
        m.world.setStringProperty("activeSimulationRegion", "AR0607")
        other = m.dialog(m.owner.participant("FLAME1"))
        self.assertFalse(other.canInteract(resume_custody=True))

    def testOrdinaryDeathStillRecordsGuardCrimeExactlyOnce(self):
        m = self.model
        actor = m.object(Creature, "guard")
        actor.hp = 0
        actor.setStringProperty("label", "Flaming Fist")
        actor.setStringProperty("sourceArea", "AR0800")
        trigger = m.object(m.classes["BaldursGateDeathTrigger"], "death")
        list(trigger.triggerFlow(actor, None))
        list(trigger.triggerFlow(actor, None))
        self.assertEqual(1, m.world.getNumericProperty("plugin_cityGuardKills"))
        self.assertTrue(m.world.getBoolProperty("plugin_cityCombatObserved_AR0800"))

    def testSurrenderPreservesPossessionsAndZeroRewardsUsingActualGraph(self):
        m = self.model
        guard = m.installCustody()
        item = object()
        m.player.items.append(item)
        before = m.player.getNumericProperty("gold"), m.player.getNumericProperty("exp")
        m.runDialogue(guard, ["0", "5"])
        self.assertEqual("jailed", m.world.getStringProperty("plugin_cityCustodyState"))
        self.assertEqual(1, m.owner.globalValue("Captured", "GLOBAL"))
        self.assertEqual(100, m.world.getNumericProperty("plugin_cityTicks"))
        self.assertEqual(before, (m.player.getNumericProperty("gold"), m.player.getNumericProperty("exp")))
        self.assertEqual([item], m.player.getItems())
        self.assertEqual([26844, 26842, 26841], m.stored("plugin_cityCustodyJournal", []))

    def testCancelledHearingRetainsCursorWithoutRepeatingArrest(self):
        m = self.model
        m.runDialogue(m.installCustody(), ["0", ""])
        self.assertEqual("hearing", m.world.getStringProperty("plugin_cityCustodyState"))
        self.assertEqual("ANGELO", m.stored("plugin_cityCustodyDialogue", {})["code"])
        m.runDialogue(m.owner.participant("ANGELO"), ["5"])
        self.assertEqual("jailed", m.world.getStringProperty("plugin_cityCustodyState"))
        self.assertEqual(100, m.world.getNumericProperty("plugin_cityTicks"))

    def testNebCorrectAnswerAndAttackUseDistinctSourceJournals(self):
        for attacked in (False, True):
            with self.subTest(attacked=attacked):
                m = Fixture()
                m.runDialogue(m.installCustody(), ["0", "5"])
                neb = m.owner.participant("NEB")
                if attacked:
                    neb.properties["coords"] = list(vars(m.player.getCoords()).values())
                    list(m.dialog(neb).attackFlow())
                else:
                    neb.setNumericProperty("plugin_cityTalkCount", 3)
                    m.runDialogue(neb, ["9", "15"])
                self.assertEqual("escaped", m.world.getStringProperty("plugin_cityCustodyState"))
                self.assertEqual([32175 if attacked else 27317], m.stored("plugin_cityCustodyJournal", []))
                self.assertTrue(neb.isAlive())
                self.assertIsNone(m.world.getObjectByName(neb.getName()))

    def testSharTeelReleaseRetiresWitnessesAndExecutesOnlyTwoEscorts(self):
        m = self.model
        guard = m.installCustody()
        companion = m.object(Creature, "sharteel")
        companion.setStringProperty("sourceCreature", "SHARTEEL")
        m.clock.setStringProperty("plugin_cityRoster", '["sharteel"]')
        m.clock.setObjectProperty("plugin_cityCompanion_sharteel", companion)
        m.runDialogue(guard, ["0", "0"])
        self.assertEqual("released", m.world.getStringProperty("plugin_cityCustodyState"))
        self.assertTrue(companion.isAlive())
        for name in ("FLAME1", "FLAME2"):
            self.assertFalse(m.owner.participant(name).isAlive())
        for name in ("FLAME3", "FLAME4", "DICKSMOK"):
            self.assertTrue(m.owner.participant(name).isAlive())
            self.assertIsNone(m.world.getObjectByName(m.owner.participant(name).getName()))
        self.assertEqual(0, m.world.getNumericProperty("plugin_cityGuardKills"))

    def testExecutionRetainsVictimAndDoesNotTransferItsInventory(self):
        m = self.model
        m.installCustody()
        victim = m.object(Creature, "companion")
        item = object()
        victim.items.append(item)
        m.clock.setStringProperty("plugin_cityRoster", '["companion"]')
        m.clock.setObjectProperty("plugin_cityCompanion_companion", victim)
        m.owner.killByAngelo(victim)
        self.assertIs(victim, m.owner.getObjectProperty("plugin_cityExecutedCompanion"))
        self.assertIs(victim, m.clock.getObjectProperty("plugin_cityCorpse_companion"))
        self.assertEqual([item], victim.getItems())
        self.assertEqual([], m.player.getItems())
        self.assertIsNone(m.world.getObjectByName("companion"))

    def testUnknownConditionAndActionFailClosed(self):
        m = self.model
        guard = m.installCustody()
        with self.assertRaisesRegex(ValueError, "Unaudited custody condition"):
            m.owner.condition({"op": "NewCondition"}, guard)
        with self.assertRaisesRegex(ValueError, "Unaudited custody action"):
            m.owner.applyAction({"op": "NewAction"}, guard)
        with self.assertRaisesRegex(ValueError, "MoveBetweenAreas"):
            m.owner.applyAction({"op": "MoveBetweenAreas"}, guard)

    def testKnownSmugglerTargetBoundaryIsExplicitAndDoesNotInventAnActor(self):
        m = self.model
        m.installCustody()
        edge = next(
            row for state in boundedFixture()["dialogues"]["FLAMC7"] for row in state["transitions"] if row["id"] == 12
        )
        action = next(row for row in edge["effects"] if row["op"] == "ActionOverride")
        self.assertEqual("smuggler", action["args"][0])
        self.assertEqual("MoveBetweenAreas", action["args"][1]["op"])
        self.assertIsNone(m.owner.participant("smuggler"))
        self.assertNotIn("smuggler", m.data["namedActors"])

    def testPrisonFixturePinsAndSourceOnlyAcceptanceRemainFalse(self):
        audit = boundedFixture()
        self.assertFalse(audit["originalParityVerified"])
        self.assertFalse(audit["textExported"])
        self.assertFalse(audit["scriptTextExported"])
        self.assertEqual(
            (39, 87),
            (
                sum(map(len, audit["dialogues"].values())),
                sum(len(s["transitions"]) for states in audit["dialogues"].values() for s in states),
            ),
        )
        self.assertTrue(audit["sourceFingerprints"])

    def testProjectionUsesExactAuditedActorsWithoutChangingInventory(self):
        helper, audit = loadHelper(), boundedFixture()
        source = compactSource(audit, helper)
        original_creatures = deepcopy(source["creatures"])
        helper.prepareCustodyActors(source, audit)
        added = [row for area in source["areas"].values() for row in area["actors"] if row.get("scriptedPolicy")]
        self.assertEqual(23, len(added))
        self.assertEqual(23, len({row["nativeId"] for row in added}))
        self.assertEqual(18, sum(row["custodyRole"] == "patrol" for row in added))
        self.assertEqual(original_creatures, source["creatures"])
        self.assertTrue(all(row["scriptedPolicy"]["phase"] == 7 for row in added))
        self.assertTrue(all(row["creature"] not in {"Sorcerer", "Warrior", "Assasin"} for row in added))

    def testProjectionRejectsMissingMetadataOrDuplicateActorBeforeMutation(self):
        helper, audit = loadHelper(), boundedFixture()
        for fault in ("metadata", "duplicate", "neb"):
            with self.subTest(fault=fault):
                source = compactSource(audit, helper)
                if fault == "metadata":
                    source["creatures"].pop("FLAME2")
                elif fault == "duplicate":
                    source["areas"]["AR0800"]["actors"].append({"nativeId": helper.ANGELO_ID, "creature": "ANGELO"})
                else:
                    source["areas"]["AR0607"]["actors"].append({"nativeId": "extraNeb", "creature": "NEB"})
                before = deepcopy(source)
                with self.assertRaises(ValueError):
                    helper.prepareCustodyActors(source, audit)
                self.assertEqual(before, source)

    def testEveryAuditedStateAndEdgeIsProjectedWithSameFactsAndParaphrasedText(self):
        helper, audit = loadHelper(), boundedFixture()
        projected = helper.authoredDialogues(audit)
        for code, states in audit["dialogues"].items():
            self.assertEqual(len(states), len(projected[code]))
            for source, authored in zip(states, projected[code]):
                self.assertEqual(source["id"], authored["id"])
                self.assertTrue(authored["text"])
                self.assertEqual(len(source["transitions"]), len(authored["transitions"]))
                for old_edge, new_edge in zip(source["transitions"], authored["transitions"]):
                    self.assertEqual(
                        {k: v for k, v in old_edge.items() if k != "actionSha256"},
                        {k: v for k, v in new_edge.items() if k != "reply"},
                    )
                    self.assertEqual(old_edge["replyStrref"] is None, new_edge["reply"] is None)
        self.assertEqual(audit["dialogues"], boundedFixture()["dialogues"])

    def testBuilderDeclaresRealClassesAndSelectedBoundedFixtureWithoutNewNativeApi(self):
        source = BUILDER.read_text(encoding="utf-8")
        module = ast.parse(source)
        self.assertIn('definition("BaldursGateContainer" if corpse else "CCreature", **props)', source)
        self.assertNotIn('definition("BaldursGateActor"', source)
        targets = {}
        for node in ast.walk(module):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "config"
                        and isinstance(target.slice, ast.Constant)
                    ):
                        targets[target.slice.value] = node.value
        self.assertEqual("BaldursGateCustody", targets["cityCustody"].args[0].value)
        self.assertEqual("BaldursGateCustodyQuest", targets["cityCustodyQuest"].args[0].value)
        self.assertIn('CUSTODY_SOURCE = ROOT / "tests/fixtures/baldurs_gate_city_prison_source.json"', source)
        self.assertNotIn("beginMapOperation", SCRIPT.read_text(encoding="utf-8"))
        self.assertNotIn("mapOperationCleanup", SCRIPT.read_text(encoding="utf-8"))
        self.assertNotIn("fightOneRound", SCRIPT.read_text(encoding="utf-8"))

    def testActualSelectedBuilderStatementsCreateRealCoordinatorAndQuestDefinitions(self):
        source = BUILDER.read_text(encoding="utf-8")
        module = ast.parse(source)
        compiler = next(node for node in module.body if getattr(node, "name", None) == "compileCity")
        body = compiler.body
        start = next(
            index
            for index, node in enumerate(body)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "custody_data" for target in node.targets)
        )
        selected = body[start : start + 4]
        self.assertEqual(["Assign", "Assign", "Expr", "Assign"], [type(node).__name__ for node in selected])
        namespace = {
            "CITY_JSON_PREFIX": "city-json:",
            "json": json,
            "config": {},
            "custody_source": boundedFixture(),
            "custodyDefinitions": loadHelper().custodyDefinitions,
            "usablePosition": lambda area, point, reserve=False: [*point, int(area[2:])],
            "place": lambda key, point: None,
        }
        functions = [node for node in module.body if getattr(node, "name", None) in {"protectCityData", "definition"}]
        exec(compile(ast.Module(body=[*functions, *selected], type_ignores=[]), str(BUILDER), "exec"), namespace)
        self.assertEqual({"cityCustody", "cityCustodyQuest"}, set(namespace["config"]))
        owner = namespace["config"]["cityCustody"]
        quest = namespace["config"]["cityCustodyQuest"]
        self.assertEqual("BaldursGateCustody", owner["class"])
        self.assertEqual("BaldursGateCustodyQuest", quest["class"])
        actual = self.model.namespace["decodeData"](owner["properties"]["custodyDefinitions"])
        self.assertEqual(39, sum(map(len, actual["dialogues"].values())))
        self.assertEqual("cityAr0607Actor2", actual["namedActors"]["NEB"])
        self.assertFalse(actual["sourceOriginalParityVerified"])

    def custodyConversationSnapshot(self, m, game_map=None):
        game_map = game_map or m.world
        return {
            key: game_map.properties.get(key)
            for key in (
                "plugin_cityCustodyState",
                "plugin_cityCustodyGlobals",
                "plugin_cityCustodyTrace",
                "plugin_cityCustodyTransitionCount",
                "plugin_cityCustodyJournal",
                "plugin_cityTicks",
            )
        }

    def pauseCustodyChoice(self, m, actor=None, code="", state=None):
        actor = actor or m.installCustody()
        flow = m.owner.conversationFlow(actor, code, state)
        self.assertEqual("showReader", next(flow)["operation"])
        offered = flow.send(None)
        self.assertEqual("choose", offered["operation"])
        return flow, offered, actor

    def replaceCustodyWorld(self, m):
        replacement = CompactMap()
        replacement.game = m.game
        m.world = replacement
        m.player = m.object(Player, "player")
        m.player.setBoolProperty("player", True)
        replacement.player = m.player
        if m.clock:
            replacement.objects["cityClock"] = m.clock
        if m.owner:
            replacement.objects["cityCustody"] = m.owner
        replacement.setNumericProperty("plugin_cityPhase", 7)
        replacement.setStringProperty("activeSimulationRegion", "AR0800")
        return replacement

    def settleCustodyWithoutNewRequest(self, flow, answer):
        try:
            request = flow.send(answer)
        except StopIteration:
            return
        finally:
            flow.close()
        self.fail("Stale custody flow produced another request: " + request["operation"])

    def testConversationRejectsWorldReplacementAfterReaderBeforeChoosing(self):
        m = Fixture()
        guard = m.installCustody()
        flow = m.owner.conversationFlow(guard)
        self.assertEqual("showReader", next(flow)["operation"])
        old, before = m.world, self.custodyConversationSnapshot(m)
        replacement = self.replaceCustodyWorld(m)
        self.settleCustodyWithoutNewRequest(flow, None)
        self.assertEqual(before, self.custodyConversationSnapshot(m, old))
        self.assertIsNone(replacement.properties.get("plugin_cityCustodyTrace"))
        self.assertIsNone(replacement.properties.get("plugin_cityCustodyState"))

    def testConversationRejectsWorldReplacementAfterChooserWithoutEffects(self):
        m = Fixture()
        flow, _, _ = self.pauseCustodyChoice(m)
        old, before = m.world, self.custodyConversationSnapshot(m)
        replacement = self.replaceCustodyWorld(m)
        self.settleCustodyWithoutNewRequest(flow, "0")
        self.assertEqual(before, self.custodyConversationSnapshot(m, old))
        self.assertIsNone(replacement.properties.get("plugin_cityCustodyGlobals"))
        self.assertIsNone(replacement.properties.get("plugin_cityCustodyTransitionCount"))

    def testConversationRejectsSameNamedSpeakerReplacementAfterChooser(self):
        m = Fixture()
        flow, _, guard = self.pauseCustodyChoice(m)
        before = self.custodyConversationSnapshot(m)
        replacement = m.object(Creature, guard.getName())
        replacement.properties.update(guard.properties)
        self.settleCustodyWithoutNewRequest(flow, "0")
        self.assertEqual(before, self.custodyConversationSnapshot(m))
        self.assertIs(m.world.getObjectByName(guard.getName()), replacement)

    def testConversationRejectsReplacedPlayerOwnerClockOrGame(self):
        for fault in ("player", "owner", "clock", "missingClock", "game"):
            with self.subTest(fault=fault):
                m = Fixture()
                flow, _, guard = self.pauseCustodyChoice(m)
                before = self.custodyConversationSnapshot(m)
                if fault == "player":
                    replacement = m.object(Player, "player")
                    replacement.setBoolProperty("player", True)
                    m.world.player = replacement
                elif fault == "owner":
                    m.object(m.classes["BaldursGateCustody"], "cityCustody")
                elif fault == "clock":
                    m.object(m.classes["BaldursGateClock"], "cityClock")
                elif fault == "missingClock":
                    m.world.removeObject(m.clock)
                else:
                    guard.game = SimpleNamespace(getMap=lambda: m.world)
                self.settleCustodyWithoutNewRequest(flow, "0")
                self.assertEqual(before, self.custodyConversationSnapshot(m))

    def testConversationRejectsChangedMetadataAndFreshSpeakerCounters(self):
        for fault in (
            "definitions",
            "actors",
            "quests",
            "sourceArea",
            "sourceCreature",
            "sourceDialogue",
            "talk",
            "count",
            "dead",
        ):
            with self.subTest(fault=fault):
                m = Fixture()
                flow, _, actor = self.pauseCustodyChoice(m)
                if fault == "definitions":
                    m.owner.setStringProperty(
                        "custodyDefinitions", m.owner.getStringProperty("custodyDefinitions") + " "
                    )
                elif fault in ("actors", "quests"):
                    m.clock.setStringProperty("actorDefinitions" if fault == "actors" else "questDefinitions", "[] ")
                elif fault in ("sourceArea", "sourceCreature", "sourceDialogue"):
                    actor.setStringProperty(fault, "replacement")
                elif fault == "talk":
                    actor.setNumericProperty("plugin_cityTalkCount", 99)
                elif fault == "count":
                    m.world.setNumericProperty("plugin_cityCustodyTransitionCount", 99)
                else:
                    actor.hp = 0
                before = self.custodyConversationSnapshot(m)
                self.settleCustodyWithoutNewRequest(flow, "0")
                self.assertEqual(before, self.custodyConversationSnapshot(m))

    def testConversationRechecksOfferedPartyConditionAfterAnswer(self):
        m = Fixture()
        m.installCustody()
        m.owner.beginCustody()
        actor = m.owner.participant("ANGELO")
        companion = m.object(Creature, "party2")
        m.clock.setStringProperty("plugin_cityRoster", '["party2"]')
        m.clock.setObjectProperty("plugin_cityCompanion_party2", companion)
        flow, offered, _ = self.pauseCustodyChoice(m, actor, "ANGELO", 0)
        self.assertIn("0", [row["id"] for row in offered["args"][2]])
        companion.hp = 0
        self.assertFalse(m.owner.condition({"op": "NumInPartyAliveGT", "args": [1]}, actor))
        before = self.custodyConversationSnapshot(m)
        self.settleCustodyWithoutNewRequest(flow, "0")
        self.assertEqual(before, self.custodyConversationSnapshot(m))

    def testConversationRechecksTheSameRetainedRandomRollWithoutAnotherDraw(self):
        m = Fixture()
        m.installCustody()
        m.owner.beginCustody()
        party = [m.object(Creature, "party" + str(index)) for index in range(2, 7)]
        m.clock.setStringProperty("plugin_cityRoster", json.dumps([actor.getName() for actor in party]))
        for actor in party:
            m.clock.setObjectProperty("plugin_cityCompanion_" + actor.getName(), actor)
        m.roll = 3
        draws, rolls = [], []
        original_import = m.namespace["__builtins__"]["__import__"]

        def countedImport(name, *args, **kwargs):
            module = original_import(name, *args, **kwargs)
            if name == "game":
                original = module.randint
                module.randint = lambda low, high: (draws.append((low, high)), original(low, high))[1]
            return module

        m.namespace["__builtins__"]["__import__"] = countedImport
        original_condition = m.owner.condition

        def changingCondition(row, actor, roll=None, **kwargs):
            if row.get("op") == "RandomNum":
                rolls.append(roll)
            result = original_condition(row, actor, roll, **kwargs)
            if result and row.get("op") == "RandomNum":
                m.roll = 5
            return result

        m.owner.condition = changingCondition
        actor = m.owner.participant("ANGELO")
        flow = m.owner.conversationFlow(actor, "ANGELO", 9)
        self.assertEqual("showReader", next(flow)["operation"])
        try:
            request = flow.send(None)
        except StopIteration:
            request = None
        flow.close()
        self.assertIsNotNone(request, "A valid retained random source branch must reach its next reader")
        self.assertEqual("showReader", request["operation"])
        self.assertEqual([(1, 5)], draws)
        self.assertTrue(rolls and all(value == 3 for value in rolls))
        self.assertGreaterEqual(rolls.count(3), 6)
        self.assertEqual(23, m.stored("plugin_cityCustodyTrace", [])[-1]["edge"])
        self.assertFalse(party[2].isAlive())
        self.assertTrue(party[0].isAlive())

    def testConversationRejectsMapChangeFromDefinitionGetterBeforeFirstUi(self):
        m = Fixture()
        actor = m.installCustody()
        original = m.owner.getStringProperty
        entered = []

        def getter(key):
            result = original(key)
            if key == "custodyDefinitions" and not entered:
                entered.append(key)
                self.replaceCustodyWorld(m)
            return result

        m.owner.getStringProperty = getter
        flow = m.owner.conversationFlow(actor)
        self.settleCustodyWithoutNewRequest(flow, None)
        self.assertEqual(["custodyDefinitions"], entered)
        self.assertIsNone(m.world.properties.get("plugin_cityCustodyTrace"))
        self.assertIsNone(m.world.properties.get("plugin_cityCustodyDialogue"))

    def testConversationRequestConstructionCannotPublishIntoAReplacementWorld(self):
        for operation in ("showReader", "choose"):
            with self.subTest(operation=operation):
                m = Fixture()
                guard = m.installCustody()
                cls = m.classes["BaldursGateCustody"]
                actual = getattr(cls, "custodyRequest", cls.conversationFlow)
                request_cell = dict(zip(actual.__code__.co_freevars, actual.__closure__, strict=True))["uiRequest"]
                original_request = request_cell.cell_contents

                def changingRequest(name, *args, **kwargs):
                    request = original_request(name, *args, **kwargs)
                    if name == operation:
                        self.replaceCustodyWorld(m)
                    return request

                request_cell.cell_contents = changingRequest
                flow = m.owner.conversationFlow(guard)
                if operation == "choose":
                    self.assertEqual("showReader", next(flow)["operation"])
                self.settleCustodyWithoutNewRequest(flow, None)
                self.assertIsNone(m.world.properties.get("plugin_cityCustodyTrace"))
                self.assertIsNone(m.world.properties.get("plugin_cityCustodyState"))

    def testConversationReflectiveTraceReadCannotCommitAfterMapReplacement(self):
        m = Fixture()
        flow, _, _ = self.pauseCustodyChoice(m)
        old, before, original = m.world, self.custodyConversationSnapshot(m), m.world.getStringProperty
        entered = []

        def getter(key):
            result = original(key)
            if key == "plugin_cityCustodyTrace" and not entered:
                entered.append(key)
                self.replaceCustodyWorld(m)
            return result

        old.getStringProperty = getter
        self.settleCustodyWithoutNewRequest(flow, "0")
        self.assertEqual(["plugin_cityCustodyTrace"], entered)
        self.assertEqual(before, self.custodyConversationSnapshot(m, old))
        self.assertIsNone(m.world.properties.get("plugin_cityCustodyTrace"))

    def testConversationReflectionCannotSwapSpeakerDuringChosenCondition(self):
        m = Fixture()
        flow, _, guard = self.pauseCustodyChoice(m)
        original_condition = m.owner.condition
        entered = []

        def changingCondition(row, actor, roll=None, **kwargs):
            result = original_condition(row, actor, roll, **kwargs)
            if not entered:
                entered.append(True)
                replacement = m.object(Creature, guard.getName())
                replacement.properties.update(guard.properties)
            return result

        # Use a real source edge with a condition; FFHUNT's normal reply edges are unconditional.
        flow.close()
        m.owner.beginCustody()
        actor = m.owner.participant("ANGELO")
        companion = m.object(Creature, "party2")
        m.clock.setStringProperty("plugin_cityRoster", '["party2"]')
        m.clock.setObjectProperty("plugin_cityCompanion_party2", companion)
        flow, _, _ = self.pauseCustodyChoice(m, actor, "ANGELO", 0)
        guard = actor
        m.owner.condition = changingCondition
        before = self.custodyConversationSnapshot(m)
        self.settleCustodyWithoutNewRequest(flow, "0")
        self.assertEqual(before, self.custodyConversationSnapshot(m))

    def testConversationPrimitiveGlobalAndJournalReadsCannotWriteReplacementWorld(self):
        for method, key, args in (
            ("setGlobal", "plugin_cityCustodyGlobals", ("Captured", "GLOBAL", 1)),
            ("journal", "plugin_cityCustodyJournal", (26844,)),
        ):
            with self.subTest(method=method):
                m = Fixture()
                m.installCustody()
                old, original = m.world, m.world.getStringProperty
                before_value = old.properties.get(key)
                entered = []

                def getter(name):
                    value = original(name)
                    if name == key and not entered:
                        entered.append(name)
                        self.replaceCustodyWorld(m)
                    return value

                old.getStringProperty = getter
                try:
                    getattr(m.owner, method)(*args)
                except RuntimeError:
                    pass
                self.assertEqual([key], entered)
                self.assertIsNone(m.world.properties.get(key))
                self.assertEqual(before_value, old.properties.get(key))

    def testConversationPrimitiveQuestGetterCannotContinueCustodyInReplacementWorld(self):
        m = Fixture()
        m.installCustody()
        old_player, original = m.player, m.player.getQuests

        def getter():
            value = original()
            self.replaceCustodyWorld(m)
            return value

        m.player.getQuests = getter
        try:
            m.owner.beginCustody()
        except RuntimeError:
            pass
        self.assertIsNone(m.world.properties.get("plugin_cityCustodyState"))
        self.assertIsNone(m.world.properties.get("plugin_cityTicks"))
        self.assertEqual([], m.player.quests)
        self.assertEqual([], old_player.quests)

    def testConversationRejectsUnchangedReplyAfterExternalCursorChange(self):
        m = Fixture()
        flow, _, _ = self.pauseCustodyChoice(m)
        m.world.setStringProperty("plugin_cityCustodyDialogue", '{"actorId":"other","code":"NEB","state":0}')
        before = self.custodyConversationSnapshot(m)
        self.settleCustodyWithoutNewRequest(flow, "0")
        self.assertEqual(before, self.custodyConversationSnapshot(m))

    def testConversationCancellationKeepsTheSameActorCursorWithoutTransitionEffects(self):
        m = Fixture()
        flow, _, actor = self.pauseCustodyChoice(m)
        before = self.custodyConversationSnapshot(m)
        cursor = m.world.getStringProperty("plugin_cityCustodyDialogue")
        self.settleCustodyWithoutNewRequest(flow, "")
        self.assertEqual(before, self.custodyConversationSnapshot(m))
        self.assertEqual(cursor, m.world.getStringProperty("plugin_cityCustodyDialogue"))
        self.assertIs(m.world.getObjectByName(actor.getName()), actor)

    def testConversationRejectsNativeContextInvalidationOnTheSameMap(self):
        for fault in ("generation", "context", "closed"):
            with self.subTest(fault=fault):
                m = Fixture()
                flow, _, _ = self.pauseCustodyChoice(m)
                original_map = m.world
                before = self.custodyConversationSnapshot(m)
                if fault == "generation":
                    m.context.generation += 1
                elif fault == "context":
                    m.context = CompactContext()
                else:
                    m.context.active = False
                self.settleCustodyWithoutNewRequest(flow, "0")
                self.assertIs(original_map, m.world)
                self.assertEqual(before, self.custodyConversationSnapshot(m))

    def testConversationValidationDoesNotInvokeLazyPlayerRecovery(self):
        m = Fixture()
        actor = m.installCustody()
        called = []

        def lazyGetter():
            called.append("getPlayer")
            raise AssertionError("Conversation guard invoked lazy player recovery")

        m.world.getPlayer = lazyGetter
        m.player.isPlayer = lazyGetter
        flow, _, _ = self.pauseCustodyChoice(m, actor)
        self.settleCustodyWithoutNewRequest(flow, "")
        self.assertEqual([], called)

    def testConversationRejectsGenericCreatureMasqueradingAsTheCanonicalPlayer(self):
        m = Fixture()
        actor = m.installCustody()
        impostor = m.object(Creature, "player")
        impostor.setBoolProperty("player", True)
        flow = m.owner.conversationFlow(actor)
        self.settleCustodyWithoutNewRequest(flow, None)
        self.assertEqual([], m.stored("plugin_cityCustodyTrace", []))

    def testConversationDetectsGenerationInvalidationInsideMetadataGetter(self):
        m = Fixture()
        actor = m.installCustody()
        original = m.owner.getStringProperty
        entered = []

        def getter(key):
            value = original(key)
            if key == "custodyDefinitions" and not entered:
                entered.append(key)
                m.context.generation += 1
            return value

        m.owner.getStringProperty = getter
        self.settleCustodyWithoutNewRequest(m.owner.conversationFlow(actor), None)
        self.assertEqual(["custodyDefinitions"], entered)
        self.assertIsNone(m.world.properties.get("plugin_cityCustodyDialogue"))

    def testConversationPrimitiveRetirementRejectsAReplacedTargetBeforeMutation(self):
        for method in ("retire", "killByAngelo"):
            with self.subTest(method=method):
                m = Fixture()
                actor = m.installCustody()
                replacement = m.object(Creature, actor.getName())
                replacement.properties.update(actor.properties)
                try:
                    getattr(m.owner, method)(actor)
                except RuntimeError:
                    pass
                self.assertIs(m.world.getObjectByName(replacement.getName()), replacement)
                self.assertFalse(actor.getBoolProperty("plugin_cityDeparted"))
                self.assertTrue(actor.isAlive())

    def freshCustodyEscort(self, m):
        m.installCustody()
        name = m.data["actorIds"]["escorts"][0]
        previous = m.world.getObjectByName(name)
        if previous:
            m.world.removeObject(previous)
        m.owner.properties.pop("plugin_cityActor_" + name, None)
        return name

    def callCustodyWithoutLeakingError(self, callback):
        try:
            return callback(), None
        except Exception as error:
            return None, error

    def testFactoryConstructionSupportsAttachedUnregisteredActor(self):
        m = Fixture()
        name = self.freshCustodyEscort(m)
        factory, observed, initialized = m.game.createObject, [], []

        def create(native_id):
            actor = factory(native_id)
            observed.append((actor, actor.getGame(), m.world.getObjectByName(native_id)))
            return actor

        m.game.createObject = create
        m.clock.initializeActor = initialized.append
        actor, error = self.callCustodyWithoutLeakingError(lambda: m.owner.spawnActor(name))
        self.assertIsNone(error)
        self.assertEqual(1, len(observed))
        self.assertIs(m.game, observed[0][1])
        self.assertIsNone(observed[0][2])
        self.assertIs(actor, m.world.getObjectByName(name))
        self.assertIs(actor, m.owner.getObjectProperty("plugin_cityActor_" + name))
        self.assertEqual([actor], initialized)
        self.assertEqual(name, actor.getTypeId())

    def testFactoryConstructorRebindStopsPlacementAndRegistration(self):
        for fault in ("world", "generation", "foreignGame", "wrongType", "alreadyRegistered"):
            with self.subTest(fault=fault):
                m = Fixture()
                name = self.freshCustodyEscort(m)
                old_map, factory, created, initialized = m.world, m.game.createObject, [], []
                m.clock.initializeActor = initialized.append

                def create(native_id):
                    actor = factory(native_id)
                    created.append(actor)
                    if fault == "world":
                        self.replaceCustodyWorld(m)
                    elif fault == "generation":
                        m.context.generation += 1
                    elif fault == "foreignGame":
                        actor.game = object()
                    elif fault == "wrongType":
                        actor.kind = "unrelated"
                    else:
                        old_map.addObject(actor)
                    return actor

                m.game.createObject = create
                _actor, error = self.callCustodyWithoutLeakingError(lambda: m.owner.spawnActor(name))
                self.assertIsInstance(error, m.owner.CustodyBindingChanged)
                self.assertEqual([], initialized)
                self.assertIsNone(m.owner.getObjectProperty("plugin_cityActor_" + name))
                self.assertNotIn("posx", created[0].properties)
                if fault != "alreadyRegistered":
                    self.assertIsNone(old_map.getObjectByName(name))

    def testFactoryPlacementRebindStopsRemainingSettersAndRetention(self):
        for key in ("name", "posx", "posy", "posz"):
            with self.subTest(key=key):
                m = Fixture()
                name = self.freshCustodyEscort(m)
                factory, created, calls, initialized = m.game.createObject, [], [], []
                old_map = m.world
                m.clock.initializeActor = initialized.append

                def create(native_id):
                    actor = factory(native_id)
                    created.append(actor)

                    def setter(field, value):
                        calls.append(field)
                        NativeObject.setStringProperty(actor, field, value)
                        if field == key:
                            self.replaceCustodyWorld(m)

                    actor.setStringProperty = actor.setNumericProperty = setter
                    return actor

                m.game.createObject = create
                _actor, error = self.callCustodyWithoutLeakingError(lambda: m.owner.spawnActor(name))
                self.assertIsInstance(error, m.owner.CustodyBindingChanged)
                self.assertEqual(
                    ["name", "posx", "posy", "posz"][: ["name", "posx", "posy", "posz"].index(key) + 1], calls
                )
                self.assertIsNone(old_map.getObjectByName(name))
                self.assertEqual([], initialized)
                self.assertIsNone(m.owner.getObjectProperty("plugin_cityActor_" + name))

    def testFactoryAddAndInitializeRebindStopAliasPromotion(self):
        for boundary in ("add", "initialize"):
            with self.subTest(boundary=boundary):
                m = Fixture()
                name = self.freshCustodyEscort(m)
                old_map, initialized, factory, created = m.world, [], m.game.createObject, []

                def create(native_id):
                    actor = factory(native_id)
                    created.append(actor)
                    return actor

                def initialize(actor):
                    initialized.append(actor)
                    if boundary == "initialize":
                        self.replaceCustodyWorld(m)

                original_add = old_map.addObject

                def add(actor):
                    original_add(actor)
                    self.replaceCustodyWorld(m)

                m.game.createObject = create
                m.clock.initializeActor = initialize
                if boundary == "add":
                    old_map.addObject = add
                _actor, error = self.callCustodyWithoutLeakingError(lambda: m.owner.spawnActor(name))
                self.assertIsInstance(error, m.owner.CustodyBindingChanged)
                self.assertIs(created[0], old_map.getObjectByName(name))
                self.assertEqual([] if boundary == "add" else created, initialized)
                self.assertIsNone(m.owner.getObjectProperty("plugin_cityActor_" + name))
                self.assertIsNone(m.world.getObjectByName(name))

    def testUnregisteredActorGetsNoGeneralCustodyCallAllowance(self):
        m = Fixture()
        name = self.freshCustodyEscort(m)
        actor = m.game.createObject(name)
        binding = m.owner.captureCustodyBinding()
        _result, error = self.callCustodyWithoutLeakingError(
            lambda: m.owner.custodyCall(binding, actor, "setNumericProperty", "exp", 99)
        )
        self.assertIsInstance(error, m.owner.CustodyBindingChanged)
        self.assertEqual(0, actor.getNumericProperty("exp"))

    def testInitialClockRequiresActualClockTypeBeforeCustodyEffects(self):
        m = Fixture()
        m.installCustody()
        fake = NativeObject()
        fake.game, fake.properties = m.game, dict(m.clock.properties)
        m.world.addObject(fake)
        before = self.custodyConversationSnapshot(m)

        def enter():
            binding = m.owner.captureCustodyBinding()
            return m.owner.beginCustody(binding=binding)

        _result, error = self.callCustodyWithoutLeakingError(enter)
        self.assertIsInstance(error, m.owner.CustodyBindingChanged)
        self.assertEqual(before, self.custodyConversationSnapshot(m))
        self.assertFalse(m.world.getBoolProperty("plugin_cityFlag_custodyHearing"))

    def testLateReflectedSpeakerReplacementInvalidatesBinding(self):
        m = Fixture()
        actor = m.installCustody()
        binding = m.owner.captureCustodyBinding(actor)
        original, reads = actor.getStringProperty, []

        def reflected(key):
            value = original(key)
            if key == "sourceDialogue":
                reads.append(key)
                if len(reads) == 2:
                    replacement = Creature()
                    replacement.game, replacement.properties = m.game, dict(actor.properties)
                    m.world.addObject(replacement)
            return value

        actor.getStringProperty = reflected
        self.assertFalse(m.owner.custodyBindingCurrent(binding))
        self.assertEqual(2, len(reads))
        self.assertIsNot(actor, m.world.getObjectByName(actor.getName()))

    def testLateSpeakerAndDataChangesStopOwnPrimitiveCounterWrite(self):
        for field in (
            "registry",
            "cursor",
            "sourceCreature",
            "sourceArea",
            "sourceDialogue",
            "actorDefinitions",
            "questDefinitions",
            "custodyDefinitions",
            "phase",
            "counter",
            "talkCount",
        ):
            with self.subTest(field=field):
                m = Fixture()
                actor = m.installCustody()
                binding = m.owner.captureCustodyBinding(actor)
                original, reads, own_writes = actor.getStringProperty, [], []
                original_set = m.world.setNumericProperty

                def counted_set(key, value):
                    if key == "plugin_cityCustodyTransitionCount":
                        own_writes.append(value)
                    original_set(key, value)

                m.world.setNumericProperty = counted_set

                def reflected(key):
                    value = original(key)
                    if key == "sourceDialogue":
                        reads.append(key)
                        if len(reads) == 4:
                            if field == "registry":
                                replacement = Creature()
                                replacement.game, replacement.properties = m.game, dict(actor.properties)
                                m.world.addObject(replacement)
                            elif field == "cursor":
                                m.world.setStringProperty("plugin_cityCustodyDialogue", '{"changed":true}')
                            elif field in ("sourceCreature", "sourceArea", "sourceDialogue"):
                                actor.setStringProperty(field, "REPLACED")
                            elif field in ("actorDefinitions", "questDefinitions"):
                                m.clock.setStringProperty(field, "[] ")
                            elif field == "custodyDefinitions":
                                m.owner.setStringProperty(field, "{} ")
                            elif field == "phase":
                                NativeObject.setNumericProperty(m.world, "plugin_cityPhase", 6)
                            elif field == "counter":
                                NativeObject.setNumericProperty(m.world, "plugin_cityCustodyTransitionCount", 90)
                            else:
                                actor.setNumericProperty("plugin_cityTalkCount", 90)
                    return value

                actor.getStringProperty = reflected
                _result, error = self.callCustodyWithoutLeakingError(
                    lambda: m.owner.custodyCall(
                        binding,
                        m.world,
                        "setNumericProperty",
                        "plugin_cityCustodyTransitionCount",
                        binding["counter"] + 1,
                    )
                )
                self.assertIsInstance(error, m.owner.CustodyBindingChanged)
                self.assertEqual([], own_writes)
                self.assertEqual(4, len(reads))

    def testNativeSnapshotRejectsForgedReflectedDynamicValues(self):
        m = Fixture()
        actor = m.installCustody()
        binding = m.owner.captureCustodyBinding(actor)
        original = m.clock.getStringProperty
        m.clock.setStringProperty("actorDefinitions", "[] ")
        m.clock.getStringProperty = lambda key: (
            binding["actorDefinitions"] if key == "actorDefinitions" else original(key)
        )
        self.assertFalse(m.owner.custodyBindingCurrent(binding))

    def testLateAliveCallbackMustNotPublishCounterAfterNativeDeath(self):
        for target in ("player", "speaker"):
            with self.subTest(target=target):
                m = Fixture()
                actor = m.installCustody()
                binding = m.owner.captureCustodyBinding(actor)
                original, reads, own_writes = actor.isAlive, [], []
                original_set = m.world.setNumericProperty

                def counted_set(key, value):
                    if key == "plugin_cityCustodyTransitionCount":
                        own_writes.append(value)
                    original_set(key, value)

                def reflected_alive():
                    alive = original()
                    reads.append(alive)
                    if len(reads) == 4:
                        (m.player if target == "player" else actor).hp = 0
                    return alive

                m.world.setNumericProperty = counted_set
                actor.isAlive = reflected_alive
                _result, error = self.callCustodyWithoutLeakingError(
                    lambda: m.owner.custodyCall(
                        binding,
                        m.world,
                        "setNumericProperty",
                        "plugin_cityCustodyTransitionCount",
                        binding["counter"] + 1,
                    )
                )
                self.assertIsInstance(error, m.owner.CustodyBindingChanged)
                self.assertEqual([], own_writes)
                self.assertEqual(4, len(reads))

    def testStagingAuthorityRejectsUnauthoredPlacementAndMetadataMutation(self):
        for fault in ("reward", "position", "source", "row"):
            with self.subTest(fault=fault):
                m = Fixture()
                name = self.freshCustodyEscort(m)
                binding = m.owner.captureCustodyBinding()
                row = next(row for row in json.loads(binding["actorDefinitions"]) if row["id"] == name)
                actor = m.game.createObject(name)
                if not hasattr(m.owner, "stageCustodyActor"):
                    # V2 has no construction protocol: this is an assertion failure, not missing-API evidence.
                    self.fail("Attached unregistered construction has no scoped placement authority")
                m.owner.stageCustodyActor(binding, actor, row)
                if fault == "source":
                    actor.setStringProperty("sourceCreature", "REPLACED")
                elif fault == "row":
                    m.clock.setStringProperty("actorDefinitions", "[] ")
                args = (
                    ("setNumericProperty", "exp", 99)
                    if fault == "reward"
                    else (
                        ("setNumericProperty", "posx", row["x"] + 1)
                        if fault == "position"
                        else ("setStringProperty", "name", name)
                    )
                )
                _result, error = self.callCustodyWithoutLeakingError(
                    lambda: m.owner.placeCustodyActor(binding, actor, *args)
                )
                self.assertIsInstance(error, m.owner.CustodyBindingChanged)
                self.assertEqual(0, actor.getNumericProperty("exp"))
                self.assertNotIn("posx", actor.properties)

    def rawCustodyAwayBack(self, m):
        original, context, generation = m.world, m.context, m.context.generation
        replacement = CompactMap()
        replacement.game = m.game
        m.game.setMap(replacement)
        m.game.setMap(original)
        self.assertIs(original, m.world)
        self.assertIs(context, m.context)
        self.assertEqual(generation, m.context.generation)

    def testEpochIsCapturedBeforeFirstMapObservation(self):
        m = Fixture()
        actor = m.installCustody()
        original, reads = m.game.getMap, []

        def reflected_map():
            game_map = original()
            reads.append(game_map)
            if len(reads) == 1:
                self.rawCustodyAwayBack(m)
            return game_map

        m.game.getMap = reflected_map
        _binding, error = self.callCustodyWithoutLeakingError(lambda: m.owner.captureCustodyBinding(actor))
        self.assertIsInstance(error, m.owner.CustodyBindingChanged)
        self.assertEqual(0, m.world.getNumericProperty("plugin_cityCustodyTransitionCount"))

    def testEpochRejectsAwayBackDuringCaptureMetadataGetter(self):
        m = Fixture()
        actor = m.installCustody()
        original, callbacks = m.owner.getStringProperty, []

        def reflected(key):
            value = original(key)
            if key == "custodyDefinitions" and not callbacks:
                callbacks.append(key)
                self.rawCustodyAwayBack(m)
            return value

        m.owner.getStringProperty = reflected
        _binding, error = self.callCustodyWithoutLeakingError(lambda: m.owner.captureCustodyBinding(actor))
        self.assertIsInstance(error, m.owner.CustodyBindingChanged)
        self.assertEqual(["custodyDefinitions"], callbacks)
        self.assertEqual(0, m.world.getNumericProperty("plugin_cityCustodyTransitionCount"))

    def testEpochRejectsRawAwayBackAtReaderAndChooserResume(self):
        for boundary in ("reader", "chooser"):
            with self.subTest(boundary=boundary):
                m = Fixture()
                actor = m.installCustody()
                flow = m.owner.conversationFlow(actor)
                self.assertEqual("showReader", next(flow)["operation"])
                if boundary == "chooser":
                    self.assertEqual("choose", flow.send(None)["operation"])
                before = self.custodyConversationSnapshot(m)
                self.rawCustodyAwayBack(m)
                self.settleCustodyWithoutNewRequest(flow, "0" if boundary == "chooser" else None)
                self.assertEqual(before, self.custodyConversationSnapshot(m))

    def testEpochRejectsLateGetterAwayBackBeforeOwnedPrimitiveWrite(self):
        m = Fixture()
        actor = m.installCustody()
        binding = m.owner.captureCustodyBinding(actor)
        original, reads, writes = actor.getStringProperty, [], []
        setter = m.world.setNumericProperty

        def reflected(key):
            value = original(key)
            if key == "sourceDialogue":
                reads.append(key)
                if len(reads) == 4:
                    self.rawCustodyAwayBack(m)
            return value

        def counted(key, value):
            if key == "plugin_cityCustodyTransitionCount":
                writes.append(value)
            setter(key, value)

        actor.getStringProperty = reflected
        m.world.setNumericProperty = counted
        _result, error = self.callCustodyWithoutLeakingError(
            lambda: m.owner.custodyCall(binding, m.world, "setNumericProperty", "plugin_cityCustodyTransitionCount", 1)
        )
        self.assertIsInstance(error, m.owner.CustodyBindingChanged)
        self.assertEqual(4, len(reads))
        self.assertEqual([], writes)
        self.assertEqual(0, m.world.getNumericProperty("plugin_cityCustodyTransitionCount"))

    def testEpochRejectsRequestConstructorRawAwayBackBeforePublishingRequest(self):
        for operation in ("showReader", "choose"):
            with self.subTest(operation=operation):
                m = Fixture()
                actor = m.installCustody()
                actual = m.classes["BaldursGateCustody"].custodyRequest
                cell = dict(zip(actual.__code__.co_freevars, actual.__closure__, strict=True))["uiRequest"]
                original = cell.cell_contents

                def constructing(name, *args, **kwargs):
                    request = original(name, *args, **kwargs)
                    if name == operation:
                        self.rawCustodyAwayBack(m)
                    return request

                cell.cell_contents = constructing
                flow = m.owner.conversationFlow(actor)
                if operation == "choose":
                    self.assertEqual("showReader", next(flow)["operation"])
                self.settleCustodyWithoutNewRequest(flow, None)
                self.assertEqual(0, m.world.getNumericProperty("plugin_cityCustodyTransitionCount"))
                self.assertIsNone(m.world.properties.get("plugin_cityCustodyTrace"))

    def testEpochQueryUsesUnboundNativeMethodRatherThanInstanceOverride(self):
        m = Fixture()
        flow, _offered, _actor = self.pauseCustodyChoice(m)
        before = self.custodyConversationSnapshot(m)
        captured = CompactGame.getMapBindingEpoch(m.game)
        self.rawCustodyAwayBack(m)
        m.game.getMapBindingEpoch = lambda: captured
        self.settleCustodyWithoutNewRequest(flow, "0")
        self.assertEqual(before, self.custodyConversationSnapshot(m))

    def testEpochStableAndSamePointerRemainEligibleAndFreshCaptureCanFollowPriorTransition(self):
        m = Fixture()
        actor = m.installCustody()
        binding = m.owner.captureCustodyBinding(actor)
        epoch = CompactGame.getMapBindingEpoch(m.game)
        m.game.setMap(m.world)
        self.assertEqual(epoch, CompactGame.getMapBindingEpoch(m.game))
        self.assertTrue(m.owner.custodyBindingCurrent(binding))
        self.rawCustodyAwayBack(m)
        self.assertGreater(CompactGame.getMapBindingEpoch(m.game), epoch)
        fresh = m.owner.captureCustodyBinding(actor)
        self.assertTrue(m.owner.custodyBindingCurrent(fresh))
        m.owner.custodyCall(fresh, m.world, "setNumericProperty", "plugin_cityCustodyTransitionCount", 1)
        self.assertEqual(1, m.world.getNumericProperty("plugin_cityCustodyTransitionCount"))

    def alternateCustodyAssignedPlayer(self, m):
        return m.object(Player, "alternateAssignedPlayer")

    def testAssignedPlayerInitialNullAndRegistryMismatchRejectBeforeCustodyReads(self):
        for mismatch in (False, True):
            with self.subTest(mismatch=mismatch):
                m = Fixture()
                actor = m.installCustody()
                m.world.player = self.alternateCustodyAssignedPlayer(m) if mismatch else None
                original, metadata = m.owner.getStringProperty, []

                def reflected(key):
                    metadata.append(key)
                    return original(key)

                m.owner.getStringProperty = reflected
                _binding, error = self.callCustodyWithoutLeakingError(lambda: m.owner.captureCustodyBinding(actor))
                self.assertIsInstance(error, m.owner.CustodyBindingChanged)
                self.assertEqual([], metadata)
                self.assertEqual(0, m.world.getNumericProperty("plugin_cityCustodyTransitionCount"))
                self.assertIs(m.player, m.world.getObjectByName("player"))

    def testAssignedPlayerCaptureMetadataChangeCannotAdmitStaleCache(self):
        m = Fixture()
        actor = m.installCustody()
        original, reads = m.owner.getStringProperty, []

        def reflected(key):
            value = original(key)
            if key == "custodyDefinitions" and not reads:
                reads.append(key)
                m.world.player = None
            return value

        m.owner.getStringProperty = reflected
        _binding, error = self.callCustodyWithoutLeakingError(lambda: m.owner.captureCustodyBinding(actor))
        self.assertIsInstance(error, m.owner.CustodyBindingChanged)
        self.assertEqual(["custodyDefinitions"], reads)
        self.assertEqual(0, m.world.getNumericProperty("plugin_cityCustodyTransitionCount"))

    def testAssignedPlayerLateGetterChangeStopsOwnedPrimitiveCounterWrite(self):
        for mismatch in (False, True):
            with self.subTest(mismatch=mismatch):
                m = Fixture()
                actor = m.installCustody()
                binding = m.owner.captureCustodyBinding(actor)
                replacement = self.alternateCustodyAssignedPlayer(m) if mismatch else None
                original, reads, writes = actor.getStringProperty, [], []
                setter = m.world.setNumericProperty

                def reflected(key):
                    value = original(key)
                    if key == "sourceDialogue":
                        reads.append(key)
                        if len(reads) == 4:
                            m.world.player = replacement
                    return value

                def counted(key, value):
                    if key == "plugin_cityCustodyTransitionCount":
                        writes.append(value)
                    setter(key, value)

                actor.getStringProperty = reflected
                m.world.setNumericProperty = counted
                _result, error = self.callCustodyWithoutLeakingError(
                    lambda: m.owner.custodyCall(
                        binding, m.world, "setNumericProperty", "plugin_cityCustodyTransitionCount", 1
                    )
                )
                self.assertIsInstance(error, m.owner.CustodyBindingChanged)
                self.assertEqual(4, len(reads))
                self.assertEqual([], writes)
                self.assertEqual(0, m.world.getNumericProperty("plugin_cityCustodyTransitionCount"))

    def testAssignedPlayerReaderAndChooserResumeRejectNullAndMismatchedCache(self):
        for boundary in ("reader", "chooser"):
            for mismatch in (False, True):
                with self.subTest(boundary=boundary, mismatch=mismatch):
                    m = Fixture()
                    actor = m.installCustody()
                    flow = m.owner.conversationFlow(actor)
                    self.assertEqual("showReader", next(flow)["operation"])
                    if boundary == "chooser":
                        self.assertEqual("choose", flow.send(None)["operation"])
                    before = self.custodyConversationSnapshot(m)
                    m.world.player = self.alternateCustodyAssignedPlayer(m) if mismatch else None
                    self.settleCustodyWithoutNewRequest(flow, "0" if boundary == "chooser" else None)
                    self.assertEqual(before, self.custodyConversationSnapshot(m))

    def testAssignedPlayerUnboundQueryRejectsSpoofedInstanceGetter(self):
        m = Fixture()
        actor = m.installCustody()
        binding = m.owner.captureCustodyBinding(actor)
        m.world.player = None
        m.world.getAssignedPlayer = lambda: m.player
        self.assertFalse(m.owner.custodyBindingCurrent(binding))
        self.assertFalse(m.owner.custodyNativeSnapshotCurrent(binding))

    def testAssignedPlayerFinalNativeTailRechecksAfterMapGetter(self):
        m = Fixture()
        actor = m.installCustody()
        binding = m.owner.captureCustodyBinding(actor)
        original, reads = m.game.getMap, []

        def reflected():
            value = original()
            if not reads:
                reads.append(value)
                m.world.player = None
            return value

        m.game.getMap = reflected
        self.assertFalse(m.owner.custodyNativeSnapshotCurrent(binding))
        self.assertEqual([m.world], reads)
        self.assertEqual(0, m.world.getNumericProperty("plugin_cityCustodyTransitionCount"))

    def testAssignedPlayerRequestConstructionCacheChangePublishesNoStaleUiRequest(self):
        for operation in ("showReader", "choose"):
            with self.subTest(operation=operation):
                m = Fixture()
                actor = m.installCustody()
                actual = m.classes["BaldursGateCustody"].custodyRequest
                cell = dict(zip(actual.__code__.co_freevars, actual.__closure__, strict=True))["uiRequest"]
                original = cell.cell_contents

                def constructing(name, *args, **kwargs):
                    request = original(name, *args, **kwargs)
                    if name == operation:
                        m.world.player = None
                    return request

                cell.cell_contents = constructing
                flow = m.owner.conversationFlow(actor)
                if operation == "choose":
                    self.assertEqual("showReader", next(flow)["operation"])
                self.settleCustodyWithoutNewRequest(flow, None)
                self.assertEqual(0, m.world.getNumericProperty("plugin_cityCustodyTransitionCount"))
                self.assertIsNone(m.world.properties.get("plugin_cityCustodyTrace"))

    def testAssignedPlayerChecksNeverUseLazyRecoveryToRepairNullCache(self):
        m = Fixture()
        actor = m.installCustody()
        calls = []

        def lazy_recovery():
            calls.append("getPlayer")
            m.world.player = m.player
            return m.player

        m.world.getPlayer = lazy_recovery
        m.world.player = None
        _binding, error = self.callCustodyWithoutLeakingError(lambda: m.owner.captureCustodyBinding(actor))
        self.assertIsInstance(error, m.owner.CustodyBindingChanged)
        self.assertEqual([], calls)
        self.assertIsNone(m.world.player)
        self.assertEqual(0, m.world.getNumericProperty("plugin_cityCustodyTransitionCount"))

    def testAssignedPlayerStableCacheKeepsEligibleCounterCommitWithoutLazyLookup(self):
        m = Fixture()
        actor = m.installCustody()
        calls = []
        m.world.getPlayer = lambda: calls.append("getPlayer")
        binding = m.owner.captureCustodyBinding(actor)
        self.assertIs(m.player, binding["player"])
        self.assertTrue(m.owner.custodyBindingCurrent(binding))
        self.assertTrue(m.owner.custodyNativeSnapshotCurrent(binding))
        m.owner.custodyCall(binding, m.world, "setNumericProperty", "plugin_cityCustodyTransitionCount", 1)
        self.assertEqual(1, m.world.getNumericProperty("plugin_cityCustodyTransitionCount"))
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
