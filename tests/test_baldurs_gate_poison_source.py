# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual projected map callbacks over native-shaped doubles; not native/MCP/save/visual acceptance."""

from copy import deepcopy
from hashlib import sha256
import importlib.abc
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class NoNative(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in ("game", "_game", "play"):
            raise AssertionError("Native import forbidden for source-only evidence")


from tests.test_baldurs_gate_custody_source import Creature, Fixture, NativeObject, CompactMap, CompactGame


def addExp(actor, value):
    actor.setNumericProperty("exp", actor.getNumericProperty("exp") + value)


def removeItem(actor, predicate):
    for item in list(actor.items):
        if predicate(item):
            actor.items.remove(item)
            return


class BaldursGatePoisonSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "res/maps/baldursGate/script.py").read_text(encoding="utf8")
        cls.config = json.loads((ROOT / "res/maps/baldursGate/config.json").read_text(encoding="utf8"))
        cls.definitions = json.loads(
            cls.config["cityClock"]["properties"]["poisonSourceDefinitions"].removeprefix("city-json:")
        )

    def setUp(self):
        finder = NoNative()
        sys.meta_path.insert(0, finder)
        self.addCleanup(sys.meta_path.remove, finder)
        stats = NativeObject()
        stats.setNumericProperty("intelligence", 12)
        stats.setNumericProperty("agility", 16)
        self.stats = stats
        self.patchers = [
            patch.object(CompactGame, "getContext", lambda game: game.fixture.context, create=True),
            patch.object(Creature, "addExp", addExp, create=True),
            patch.object(Creature, "addItem", lambda actor, item: actor.items.append(item), create=True),
            patch.object(Creature, "removeQuestItem", removeItem, create=True),
            patch.object(Creature, "getGold", lambda actor: actor.getNumericProperty("gold"), create=True),
            patch.object(
                Creature,
                "addGold",
                lambda actor, value: actor.setNumericProperty("gold", actor.getNumericProperty("gold") + value),
                create=True,
            ),
            patch.object(Creature, "getStats", lambda actor: stats, create=True),
            patch.object(Creature, "getEffects", lambda actor: [], create=True),
            patch.object(
                Creature,
                "setController",
                lambda actor, controller: setattr(actor, "controller", controller),
                create=True,
            ),
            patch.object(
                NativeObject, "hasTag", lambda actor, tag: tag in actor.properties.get("tags", []), create=True
            ),
            patch.object(CompactMap, "getTile", self.tile, create=True),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.fixture = Fixture(source=self.source)
        # Match the engine's resource-plugin builtin surface while retaining the fake game importer.
        safe_names = {
            "__build_class__",
            "abs",
            "all",
            "any",
            "bool",
            "callable",
            "classmethod",
            "dict",
            "enumerate",
            "Exception",
            "float",
            "frozenset",
            "getattr",
            "hasattr",
            "int",
            "isinstance",
            "len",
            "list",
            "max",
            "min",
            "print",
            "property",
            "range",
            "RuntimeError",
            "set",
            "setattr",
            "staticmethod",
            "sorted",
            "str",
            "sum",
            "super",
            "tuple",
            "type",
            "TypeError",
            "ValueError",
            "__import__",
        }
        plugin_builtins = self.fixture.namespace["__builtins__"]
        for name in list(plugin_builtins):
            if name not in safe_names:
                del plugin_builtins[name]
        self.clock, self.player, self.world = self.fixture.clock, self.fixture.player, self.fixture.world
        self.world.setStringProperty("mapName", "baldursGate")
        ordinary_factory = self.fixture.game.createObject

        def createConfiguredObject(name):
            row = self.config.get(name, {})
            if row.get("class") in ("BaldursGateQuest", "BaldursGateDialog"):
                obj = self.fixture.classes[row["class"]]()
                obj.game, obj.kind = self.fixture.game, name
                obj.properties.update(deepcopy(row["properties"]))
                return obj
            obj = ordinary_factory(name)
            if name.startswith("cityItem"):
                obj.properties.update(deepcopy(self.config[name].get("properties", {})))
            return obj

        self.fixture.game.createObject = createConfiguredObject
        importer = self.fixture.namespace["__builtins__"]["__import__"]
        for cell in importer.__closure__:
            if isinstance(cell.cell_contents, dict) and "CCreature" in cell.cell_contents:
                actual_base_api = (
                    "addTag",
                    "clone",
                    "getBoolProperty",
                    "getGame",
                    "getName",
                    "getNumericProperty",
                    "getObjectProperty",
                    "getStringProperty",
                    "getType",
                    "getTypeId",
                    "hasTag",
                    "incProperty",
                    "notifyPropertyChanged",
                    "ptr",
                    "removeTag",
                    "setBoolProperty",
                    "setNumericProperty",
                    "setObjectProperty",
                    "setStringProperty",
                )
                native_base = type(
                    "BoundGameObjectApi",
                    (),
                    {
                        name: staticmethod(getattr(NativeObject, name))
                        for name in actual_base_api
                        if hasattr(NativeObject, name)
                    },
                )
                cell.cell_contents.update(CEffect=NativeObject, CMapObject=NativeObject, CGameObject=native_base)
        clock_props = self.config["cityClock"]["properties"]
        for key in ("poisonSourceDefinitions", "poisonAuthoredText", "areaAtlas", "questDefinitions"):
            self.clock.setStringProperty(key, clock_props[key])
        self.clock.setBoolProperty("plugin_cityPoisonSourceEnabled", True)
        self.notices = []
        self.fixture.game.getGuiHandler = lambda: type(
            "Gui", (), {"notify": lambda _self, text: self.notices.append(text)}
        )()
        self.fixture.clock.initializeActor = self.installInventory
        for row in self.definitions["initialActors"]:
            props = deepcopy(self.config[row["typeId"]]["properties"])
            self.fixture.catalog[row["id"]] = props
            actor = self.fixture.createObject(row["id"])
            self.world.addObject(actor)
            self.installInventory(actor)
        for code, row in self.definitions["factories"].items():
            self.fixture.catalog[row["typeId"]] = deepcopy(self.config[row["typeId"]]["properties"])
        self.player.setNumericProperty("gold", 5000)
        self.clock.poisonInitializeSource()

    def tile(self, *args):
        result = NativeObject()
        result.setBoolProperty("canStep", True)
        return result

    def installInventory(self, actor):
        if actor.getBoolProperty("plugin_cityInventoryInitialized"):
            return
        for index, row in enumerate(json.loads(actor.getStringProperty("sourceInventory").removeprefix("city-json:"))):
            item = self.fixture.createObject("cityItem" + row["item"][:1].upper() + row["item"][1:].lower())
            item.setStringProperty("plugin_citySourceItem", row["item"])
            item.setStringProperty("plugin_cityCharges", "city-json:" + json.dumps(row["charges"]))
            item.setStringProperty("name", actor.getName() + "Stock" + str(index))
            actor.items.append(item)
        actor.setBoolProperty("plugin_cityInventoryInitialized", True)

    def state(self):
        return json.loads(self.clock.getStringProperty("plugin_cityPoisonSourceState").removeprefix("city-json:"))

    def writeState(self, data):
        self.clock.setStringProperty("plugin_cityPoisonSourceState", "city-json:" + json.dumps(data))

    def actor(self, resource):
        state = self.state()
        return next(
            self.world.getObjectByName(name)
            for name, row in state["actors"].items()
            if row["resource"] == resource and not row["retired"] and not row["dead"]
        )

    def globalValue(self, name, value):
        state = self.state()
        state["globals"][name] = value
        self.writeState(state)

    def create(self, resource, area, point, operation):
        binding = self.clock.poisonCapture()
        state = self.clock.poisonRead(binding)
        name = self.clock.poisonCreateSourceActor(binding, state, resource, operation, area, point)
        self.clock.poisonWrite(binding, state)
        return self.world.getObjectByName(name)

    def give(self, owner, code):
        item = self.fixture.createObject("cityItem" + code[:1].upper() + code[1:].lower())
        item.setStringProperty("plugin_citySourceItem", code)
        item.setStringProperty("plugin_cityCharges", "city-json:[0,0,0]")
        owner.items.append(item)
        return item

    def testCompiledSevenGraphsAndRealInitialOwners(self):
        self.assertEqual(
            (7, 84, 135), tuple(self.clock.poisonGraphs().coverage()[key] for key in ("graphs", "states", "edges"))
        )
        self.assertEqual(5, len(self.state()["actors"]))
        self.assertEqual(
            [],
            [item for item in self.actor("MAREK").items if item.getStringProperty("plugin_citySourceItem") == "POTN47"],
        )

    def testActualNormalLothanderTerminalBeforeTakeAndCoherentCureAfterDeparture(self):
        lothander = self.create("LOTHAN", "AR0700", [2361, 1090], "AR0700.BCS#spawn4")
        self.globalValue("LothanderMove", 2)
        scroll = self.give(self.player, "SCRLJALA")
        session = self.clock.poisonBeginDialogue(lothander)
        self.assertTrue(self.clock.poisonChooseEdge(session, 21))
        self.assertTrue(self.clock.poisonChooseEdge(session, 23))
        self.assertNotIn(scroll, self.player.items)
        self.assertIsNone(self.world.getObjectByName(lothander.getName()))
        self.assertEqual(1519, self.player.getNumericProperty("exp"))
        self.assertEqual(
            1, sum(item.getStringProperty("plugin_citySourceItem") == "LOPOTN20" for item in self.player.items)
        )
        receipt = next(row for row in self.state()["receipts"].values() if row.get("source") == "LOTHAN.DLG:edge23")
        operations = [step["operation"] for step in receipt["steps"]]
        self.assertLess(operations.index("AddexperienceParty"), operations.index("TakePartyItem"))
        marek = self.create("MAREK1", "AR0115", [406, 344], "AR0115.BCS#spawn0")
        antidote = next(item for item in marek.items if item.getStringProperty("plugin_citySourceItem") == "POTN47")
        self.assertTrue(self.clock.transferPoisonSourceItem(marek, self.player, antidote))
        self.assertEqual(
            11519, self.player.getNumericProperty("exp")
        )  # Source-model native killXP is deliberately separate.
        self.assertEqual(
            [9, 0, 0], json.loads(antidote.getStringProperty("plugin_cityCharges").removeprefix("city-json:"))
        )
        self.assertEqual(44, self.state()["journal"][-1]["sourceConsumer"])

    def testGenuinePriestDeathFallbackHasZeroGeasXpAndNoScroll(self):
        priest = self.actor("PUMBERL")
        priest.hp = 0
        self.world.removeObject(priest)  # Matches actual CMap erasure-before-onDestroy ordering.
        self.assertTrue(self.clock.poisonRecordDeath(priest))
        lothander = self.create("LOTHAN", "AR0700", [2361, 1090], "AR0700.BCS#spawn4")
        self.globalValue("LothanderMove", 2)
        session = self.clock.poisonBeginDialogue(lothander)
        for edge in (19, 25, 26):
            self.assertTrue(self.clock.poisonChooseEdge(session, edge))
        self.assertEqual(19, self.player.getNumericProperty("exp"))
        self.assertEqual(
            1, sum(item.getStringProperty("plugin_citySourceItem") == "LOPOTN20" for item in self.player.items)
        )

    def testBothMarekLineagesAggregateDeadAliasWhileFinalOwnerIsAlive(self):
        initial = self.actor("MAREK")
        marek = self.create("MAREK1", "AR0115", [406, 344], "AR0115.BCS#spawn0")
        initial.hp = 0
        self.world.removeObject(initial)
        self.clock.poisonRecordDeath(initial)
        antidote = next(item for item in marek.items if item.getStringProperty("plugin_citySourceItem") == "POTN47")
        self.clock.transferPoisonSourceItem(marek, self.player, antidote)
        self.assertTrue(marek.isAlive())
        self.assertEqual(43, self.state()["journal"][-1]["sourceConsumer"])

    def testNativePartyScrollAndBookChecksIncludeActualFollower(self):
        follower = self.fixture.object(Creature, "realFollower")
        self.clock.setStringProperty("plugin_cityRoster", json.dumps(["realFollower"]))
        self.clock.setObjectProperty("plugin_cityCompanion_realFollower", follower)
        self.give(follower, "SCRLJALA")
        lothander = self.create("LOTHAN", "AR0700", [2361, 1090], "AR0700.BCS#spawn4")
        self.globalValue("LothanderMove", 2)
        session = self.clock.poisonBeginDialogue(lothander)
        self.clock.poisonChooseEdge(session, 21)
        self.clock.poisonChooseEdge(session, 23)
        self.assertEqual([], follower.items)
        self.assertEqual(1519, self.player.getNumericProperty("exp"))

    def testJalanthaReceivesActualReturnedBookAndRetainsItForLaterTheft(self):
        jalantha = self.create("JALANT", "AR0609", [216, 677], "templeJalanthaSourceCreation")
        book = self.give(self.player, "BOOK08")
        session = self.clock.poisonBeginDialogue(jalantha)
        self.clock.poisonChooseEdge(session, 14)
        self.clock.poisonChooseEdge(session, 19)
        self.assertNotIn(book, self.player.items)
        self.assertTrue(any(item is book for item in jalantha.items))
        self.assertEqual(
            1, sum(item.getStringProperty("plugin_citySourceItem") == "SCRLJALA" for item in self.player.items)
        )

    def testSourceCureConsumerRequiresOnlyLocalMarkerAndRemovesOneHalfPerPartySlot(self):
        first = self.give(self.player, "LOPOTN20")
        first.setStringProperty("name", "aFirstHalf")
        second = self.give(self.player, "LOPOTN20")
        second.setStringProperty("name", "bSecondHalf")
        follower = self.fixture.object(Creature, "halfFollower")
        self.clock.setStringProperty("plugin_cityRoster", json.dumps(["halfFollower"]))
        self.clock.setObjectProperty("plugin_cityCompanion_halfFollower", follower)
        follower_half = self.give(follower, "LOPOTN20")
        self.player.setNumericProperty("plugin_cityBdmarek", 1)
        self.assertEqual({}, self.state()["antidoteStock"])
        self.assertTrue(self.clock.observePoisonAcquisition())
        self.assertNotIn(first, self.player.items)
        self.assertIn(second, self.player.items)
        self.assertNotIn(follower_half, follower.items)
        self.assertEqual(10019, self.player.getNumericProperty("exp"))

    def testSameEpochReplacementCannotRebindSourceOwner(self):
        actual = self.actor("CHANTH")
        clone = self.fixture.createObject(actual.getTypeId())
        clone.properties = deepcopy(actual.properties)
        self.world.removeObject(actual)
        self.world.addObject(clone)
        with self.assertRaisesRegex(RuntimeError, "replaced within the same live map epoch"):
            self.clock.poisonBeginDialogue(clone)

    def testLegacyProgressRefusesWithoutResettingRewardOrStage(self):
        self.clock.setStringProperty("plugin_cityPoisonSourceState", "")
        self.world.setStringProperty("plugin_cityQuest_lothanderGeas", "completed")
        before = deepcopy(
            (self.player.properties, self.world.properties, [item.properties for item in self.player.items])
        )
        with self.assertRaisesRegex(RuntimeError, "preserved pending explicit migration"):
            self.clock.poisonInitializeSource()
        self.assertEqual(
            before, (self.player.properties, self.world.properties, [item.properties for item in self.player.items])
        )
        self.assertEqual("", self.clock.getStringProperty("plugin_cityPoisonSourceState"))

    def testActualSourceDialogueUiStartsFromAuthoredMeaningAndKeepsCancelCursor(self):
        marek = self.actor("MAREK")
        flow = self.clock.poisonDialogueFlow(marek)
        request = next(flow)
        self.assertEqual("showReader", request["operation"])
        self.assertNotIn("MAREK.DLG", request["args"][-1])
        request = flow.send(None)
        self.assertEqual("choose", request["operation"])
        with self.assertRaises(StopIteration):
            flow.send(None)
        cursor = next(iter(self.state()["cursors"].values()))
        self.assertFalse(cursor["done"])
        self.assertEqual(1, marek.getNumericProperty("plugin_cityPoisonTalkCount"))

    def testWaitPersistsUntilFirstNativeTurnAtOrAfterTenSourceSeconds(self):
        priest = self.actor("PUMBERL")
        session = self.clock.poisonBeginDialogue(priest)
        self.clock.poisonChooseEdge(session, 1)
        self.clock.poisonChooseEdge(session, 6)
        waiting = self.state()
        operation = waiting["cursors"][session]["waiting"]
        self.assertEqual(10, waiting["continuations"][operation]["due"])
        self.assertEqual("waiting", waiting["receipts"][operation]["status"])
        self.assertIsNone(priest.controller)
        self.writeState(deepcopy(waiting))  # JSON roundtrip only; this is not a native save test.
        self.world.setNumericProperty("plugin_cityTicks", 1)
        self.clock.poisonResumeContinuations()
        self.assertIsNone(priest.controller)
        self.world.setNumericProperty("plugin_cityTicks", 2)
        self.clock.poisonResumeContinuations()
        self.assertEqual("player", priest.controller.getStringProperty("target"))
        done = self.state()
        self.assertEqual({}, done["continuations"])
        self.assertEqual(["Wait", "Enemy"], [row["operation"] for row in done["receipts"][operation]["steps"]])
        self.assertTrue(done["cursors"][session]["done"])
        self.clock.poisonResumeContinuations()
        self.assertEqual(done, self.state())

    def testWaitingHostilityCancelsOnGenuineProspectiveOwnerDeath(self):
        priest = self.actor("PUMBERL")
        session = self.clock.poisonBeginDialogue(priest)
        self.clock.poisonChooseEdge(session, 1)
        self.clock.poisonChooseEdge(session, 6)
        operation = self.state()["cursors"][session]["waiting"]
        priest.hp = 0
        self.world.removeObject(priest)
        self.clock.poisonRecordDeath(priest)
        self.world.setNumericProperty("plugin_cityTicks", 2)
        self.clock.poisonResumeContinuations()
        self.assertIsNone(priest.controller)
        state = self.state()
        self.assertEqual({}, state["continuations"])
        self.assertEqual("cancelledByOwnerDeath", state["receipts"][operation]["status"])
        self.assertEqual(["Wait"], [row["operation"] for row in state["receipts"][operation]["steps"]])
        self.assertTrue(state["cursors"][session]["done"])

    def drive(self, flow, replies):
        requests, pending = [], iter(replies)
        try:
            request = next(flow)
            for _step in range(50):
                requests.append(request)
                answer = next(pending, None) if request["operation"] == "choose" else None
                request = flow.send(answer)
        except StopIteration:
            return requests
        self.fail("Source UI exceeded its bounded test route")

    def testActualDialogCallbacksCreateAndAddressGenuineJalantha(self):
        priest = self.actor("PUMBERL")
        requests = self.drive(self.clock.poisonDialogueFlow(priest), ["PUMBERL.DLG:edge0", "PUMBERL.DLG:edge5", None])
        jalantha = self.actor("JALANT")
        self.assertEqual("JALANT", jalantha.getStringProperty("sourceCreature"))
        self.assertEqual(4950, self.player.getNumericProperty("gold"))
        self.assertEqual([], self.state()["queuedDialogs"])
        self.assertEqual(1, jalantha.getNumericProperty("plugin_cityPoisonTalkCount"))
        displayed = [row for row in requests if row["operation"] == "showReader"]
        self.assertTrue(any(row["args"][-2] == "Jalantha Mistmyr" for row in displayed))
        self.assertEqual(0, self.player.getNumericProperty("plugin_cityBdmarek"))

    def testActualStartStoreUsesDedicatedAuditedServiceDialog(self):
        chanthalas = self.actor("CHANTH")
        requests = self.drive(self.clock.poisonDialogueFlow(chanthalas), ["CHANTH.DLG:edge1"])
        shown = [row for row in requests if row["operation"] == "gui.showDialog"]
        self.assertEqual(1, len(shown))
        self.assertEqual("cityPoisonStoreTEM0132Dialog", shown[0]["args"][0].getTypeId())
        self.assertEqual([], self.state()["queuedStores"])
        self.assertEqual(5000, self.player.getNumericProperty("gold"))

    def testShadowedPythonReadCannotReplaceAuthoredGraphsOrPresentation(self):
        expected = self.clock.poisonGraphs().coverage()
        marek = self.actor("MAREK")
        self.clock.getStringProperty = lambda key: "city-json:{}"
        self.assertEqual(expected, self.clock.poisonGraphs().coverage())
        session = self.clock.poisonBeginDialogue(marek)
        self.assertIsNotNone(session)
        requests = self.drive(self.clock.poisonDialogueFlow(marek), [None])
        self.assertEqual("showReader", requests[0]["operation"])
        self.assertTrue(requests[0]["args"][-1])

    def testTurnAcquisitionCompletesRealQuestLogWithAuditedAliveJournal(self):
        self.player.setNumericProperty("plugin_cityBdmarek", 1)
        self.assertTrue(self.clock.observePoisonAcquisition())
        main = [obj for obj in self.player.getCompletedQuests() if obj.getTypeId() == "cityMarekPoisonQuest"]
        self.assertEqual(1, len(main))
        self.assertEqual([], self.player.getQuests())
        self.assertIn("Deception", main[0].getObjective())
        self.assertIn("10,000", main[0].getReward())
        self.assertEqual(10019, self.player.getNumericProperty("exp"))

    def testActualTheftCallbackActivatesSingleOwnedAntidoteImmediately(self):
        marek = self.create("MAREK1", "AR0115", [406, 344], "AR0115.BCS#spawn0")
        point = marek.getCoords()
        self.player.properties["coords"] = [point.x, point.y, point.z]
        antidote = next(item for item in marek.items if item.getStringProperty("plugin_citySourceItem") == "POTN47")
        dialog = self.fixture.game.createObject(marek.getName() + "Dialog")
        flow = dialog.pickPocketFlow()
        request = next(flow)
        self.assertEqual("choose", request["operation"])
        with self.assertRaises(StopIteration):
            flow.send(antidote.getName())
        self.assertNotIn(antidote, marek.items)
        self.assertIn(antidote, self.player.items)
        self.assertTrue(antidote.getBoolProperty("plugin_cityStolen"))
        self.assertEqual(1, self.state()["globals"].get("PartyCured", 0))
        self.assertEqual(10019, self.player.getNumericProperty("exp"))
        self.assertEqual(
            [9, 0, 0], json.loads(antidote.getStringProperty("plugin_cityCharges").removeprefix("city-json:"))
        )

    def testCoordinatorObservesAcquisitionBeforeAcceptedPoisonQuest(self):
        marek = self.create("MAREK1", "AR0115", [406, 344], "AR0115.BCS#spawn0")
        antidote = next(item for item in marek.items if item.getStringProperty("plugin_citySourceItem") == "POTN47")
        marek.items.remove(antidote)
        self.player.items.append(antidote)
        self.world.setBoolProperty("plugin_cityInitialized", True)
        list(self.clock.onTurnFlow(None))
        self.assertEqual(10019, self.player.getNumericProperty("exp"))
        self.assertEqual(1, self.state()["globals"]["PartyCured"])
        self.assertEqual(0, len(self.state()["timers"]))
        self.assertEqual(1, len(self.player.getCompletedQuests()))

    def testSourceTokenCloneAcrossGenuineOwnersCannotGrantCure(self):
        marek = self.create("MAREK1", "AR0115", [406, 344], "AR0115.BCS#spawn0")
        actual = next(item for item in marek.items if item.getStringProperty("plugin_citySourceItem") == "POTN47")
        clone = self.fixture.createObject(actual.getTypeId())
        clone.properties = deepcopy(actual.properties)
        self.player.items.append(clone)
        before = deepcopy(self.state())
        with self.assertRaisesRegex(self.clock.PoisonBindingChanged, "distinct actual owned instances"):
            self.clock.observePoisonAcquisition()
        self.assertEqual(before, self.state())
        self.assertIn(actual, marek.items)
        self.assertEqual(19, self.player.getNumericProperty("exp"))
        self.assertEqual(0, self.player.getNumericProperty("plugin_cityBdmarek"))

    def testUncertainNativeXpAcknowledgementQuarantinesInsteadOfRepeatingAward(self):
        self.player.setNumericProperty("plugin_cityBdmarek", 1)

        def loseAcknowledgement(actor, value):
            addExp(actor, value)
            raise RuntimeError("native reward acknowledgement lost")

        with patch.object(Creature, "addExp", loseAcknowledgement):
            with self.assertRaisesRegex(RuntimeError, "acknowledgement lost"):
                self.clock.observePoisonAcquisition()
        self.assertEqual(10019, self.player.getNumericProperty("exp"))
        self.assertEqual("pending", self.state()["receipts"]["cure:bdmarek"]["status"])
        for _repeat in range(2):
            with self.assertRaisesRegex(self.clock.PoisonBindingChanged, "quarantined"):
                self.clock.observePoisonAcquisition()
        self.assertEqual(10019, self.player.getNumericProperty("exp"))

    def testGeneratedResourcesHoldActivationAndKeepActualAntidoteStock(self):
        self.assertFalse(self.config["cityClock"]["properties"]["plugin_cityPoisonSourceEnabled"])
        initial = self.config["cityAr0300Actor29"]["properties"]
        final = self.config["cityPoisonMarek1"]["properties"]
        street = json.loads(initial["sourceInventory"].removeprefix("city-json:"))
        stock = json.loads(final["sourceInventory"].removeprefix("city-json:"))
        self.assertFalse(any(item["item"] == "POTN47" for item in street))
        antidotes = [item for item in stock if item["item"] == "POTN47"]
        self.assertEqual(1, len(antidotes))
        self.assertEqual([10, 0, 0], antidotes[0]["charges"])
        self.assertEqual((650, 201), (final["sourceKillXp"], final["gold"]))
        self.assertEqual(12, len(self.definitions["positions"]))

    def testEveryFiniteActionPointUsesAnExistingWalkableNativeCell(self):
        document = json.loads((ROOT / "res/maps/baldursGate/map.json").read_text(encoding="utf8"))
        layers = {
            int(layer["properties"]["level"]): layer for layer in document["layers"] if layer["type"] == "tilelayer"
        }
        for key, point in self.definitions["positions"].items():
            with self.subTest(sourcePoint=key):
                x, y, z = point
                layer = layers[z]
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLess(x, layer["width"])
                self.assertLess(y, layer["height"])
                self.assertNotEqual(12, layer["data"][y * layer["width"] + x])

    def testUnsupportedShoutBranchRemainsInGraphAndRefusesBeforeAnyMutation(self):
        jalantha = self.create("JALANT", "AR0609", [216, 677], "templeJalanthaSourceCreation")
        self.give(self.player, "BOOK08")
        session = self.clock.poisonBeginDialogue(jalantha)
        self.clock.poisonChooseEdge(session, 13)
        before = deepcopy(self.state())
        self.assertFalse(self.clock.poisonChooseEdge(session, 18))
        self.assertEqual(before, self.state())
        self.assertEqual(9, self.state()["cursors"][session]["state"])
        self.assertIsNone(jalantha.controller)
        held = {"JALANT.DLG:edge18": "internal source listener hold"}
        flow = self.clock.showPoisonSourceStateFlow("JALANT.DLG:state9", ["JALANT.DLG:edge18"], held)
        next(flow)
        choice = flow.send(None)
        self.assertFalse(choice["args"][2][0]["enabled"])
        with self.assertRaises(StopIteration) as stopped:
            flow.send("JALANT.DLG:edge18")
        self.assertIsNone(stopped.exception.value)

    def testFreshAdmissionRefusesUnaccountedSourceGraphOwnersWithoutResetting(self):
        actual = self.actor("CHANTH")
        extra = self.fixture.createObject(actual.getTypeId())
        extra.properties = deepcopy(actual.properties)
        extra.setStringProperty("name", "unaccountedSourceOwner")
        self.world.addObject(extra)
        self.clock.setStringProperty("plugin_cityPoisonSourceState", "")
        before = deepcopy((self.player.properties, self.world.properties, [item.properties for item in actual.items]))
        with self.assertRaisesRegex(RuntimeError, "additional source graph owner"):
            self.clock.poisonInitializeSource()
        self.assertEqual(
            before, (self.player.properties, self.world.properties, [item.properties for item in actual.items])
        )
        self.assertEqual("", self.clock.getStringProperty("plugin_cityPoisonSourceState"))

    def testActualInitializerCannotSeedCondensedHalfBeforeSourceDelivery(self):
        lothander = self.actor("LOTHAN")
        lothander.items.clear()
        lothander.setBoolProperty("plugin_cityInventoryInitialized", False)
        lothander.setBoolProperty("plugin_cityHooksInstalled", True)
        actual_initializer = self.fixture.classes["BaldursGateClock"].initializeActor
        slots = SimpleNamespace(getFittingSlots=lambda item: [])
        with patch.object(self.fixture.game, "getSlotConfiguration", lambda: slots, create=True):
            actual_initializer(self.clock, lothander)
        codes = [item.getStringProperty("plugin_citySourceItem") for item in lothander.items]
        self.assertNotIn("LOPOTN20", codes)
        self.assertEqual(7, len(codes))
        self.assertEqual(19, self.player.getNumericProperty("exp"))

    def createTwoSourceJalanthas(self):
        priest = self.actor("PUMBERL")
        created = []
        for occurrence in range(2):
            session = self.clock.poisonBeginDialogue(priest)
            state = self.state()
            # State10/edge16 is retained but unlinked in this seven-graph closure. This arranges its
            # typed action unit boundary; it does not claim an entry-reachable gameplay route.
            state["cursors"][session]["state"] = 10
            self.writeState(state)
            self.assertTrue(self.clock.poisonChooseEdge(session, 16))
            state = self.state()
            names = [name for name, row in state["actors"].items() if row["resource"] == "JALANT"]
            self.assertEqual(occurrence + 1, len(names))
            created.append(self.world.getObjectByName(names[-1]))
        return created

    def testTwoSourceCreateCallsBindSelfDialogueAndIndependentActualStock(self):
        first, second = self.createTwoSourceJalanthas()
        self.assertIsNot(first, second)
        self.assertNotEqual(first.getName(), second.getName())
        self.assertEqual(first.getTypeId(), second.getTypeId())
        self.assertNotEqual(
            first.getStringProperty("plugin_cityPoisonOwnerCreation"),
            second.getStringProperty("plugin_cityPoisonOwnerCreation"),
        )
        self.assertEqual([first.getName(), second.getName()], self.state()["queuedDialogs"])
        first_scroll = next(
            item for item in first.items if item.getStringProperty("plugin_citySourceItem") == "SCRLJALA"
        )
        second_scroll = next(
            item for item in second.items if item.getStringProperty("plugin_citySourceItem") == "SCRLJALA"
        )
        self.assertIsNot(first_scroll, second_scroll)
        for actor in (first, second):
            dialog = self.clock.poisonMakeActorDialog(actor)
            self.assertEqual(actor.getName(), dialog.getStringProperty("actorId"))
            self.assertIs(actor, dialog.actor())
        hook = self.fixture.object(self.fixture.classes["BaldursGatePersonTrigger"], "sourcePersonEntryTest")
        flow = hook.triggerFlow(second, SimpleNamespace(getCause=lambda: self.player))
        request = next(flow)
        self.assertEqual("gui.showDialog", request["operation"])
        self.assertIs(second, request["args"][0].actor())
        with self.assertRaises(StopIteration):
            flow.send(None)
        self.give(self.player, "BOOK08")
        first_session = self.clock.poisonBeginDialogue(first)
        self.clock.poisonChooseEdge(first_session, 13)
        self.assertIn(first_scroll, self.player.items)
        self.assertIn(second_scroll, second.items)
        second_session = self.clock.poisonBeginDialogue(second)
        self.clock.poisonChooseEdge(second_session, 13)
        self.assertIn(second_scroll, self.player.items)
        self.assertNotEqual(first_session, second_session)
        self.assertEqual(first_session, self.clock.poisonBeginDialogue(first))
        self.assertEqual(
            2, sum(item.getStringProperty("plugin_citySourceItem") == "SCRLJALA" for item in self.player.items)
        )
        self.assertEqual(
            [],
            [
                item
                for item in first.items + second.items
                if item.getStringProperty("plugin_citySourceItem") == "SCRLJALA"
            ],
        )

    def testModelRestoreRebindsMultipleCreatedOwnersAndRetainsSeparateCursorStock(self):
        first, second = self.createTwoSourceJalanthas()
        self.give(self.player, "BOOK08")
        sessions = [self.clock.poisonBeginDialogue(actor) for actor in (first, second)]
        self.clock.poisonChooseEdge(sessions[0], 13)
        snapshot = deepcopy(self.state())
        restored = []
        for actor in (first, second):
            replacement = self.fixture.createObject(actor.getTypeId())
            replacement.properties = deepcopy(actor.properties)
            for item in actor.items:
                copy = self.fixture.createObject(item.getTypeId())
                copy.properties = deepcopy(item.properties)
                replacement.items.append(copy)
            self.world.removeObject(actor)
            self.world.addObject(replacement)
            restored.append(replacement)
        # A native verified load changes map binding epoch; this is only a JSON/object-double restore control.
        self.fixture.game.map_epoch += 1
        self.writeState(json.loads(json.dumps(snapshot)))
        list(self.clock.resumeAfterVerifiedLoadFlow())
        for index, actor in enumerate(restored):
            self.assertEqual(sessions[index], self.clock.poisonBeginDialogue(actor))
            self.assertIs(actor, self.clock.poisonMakeActorDialog(actor).actor())
        self.assertFalse(
            any(item.getStringProperty("plugin_citySourceItem") == "SCRLJALA" for item in restored[0].items)
        )
        second_scroll = next(
            item for item in restored[1].items if item.getStringProperty("plugin_citySourceItem") == "SCRLJALA"
        )
        self.clock.poisonChooseEdge(sessions[1], 13)
        self.assertIn(second_scroll, self.player.items)
        third = self.create("JALANT", "AR0609", [216, 677], "PUMBERL.DLG:edge16:third")
        self.assertEqual("cityAr0609ScriptActorJalantCreated3", third.getName())
        self.assertEqual(3, self.state()["factorySerials"]["JALANT"])
        self.assertEqual(19, self.player.getNumericProperty("exp"))

    def testSavedFiniteSourceBindingCannotChangeScriptAliasOrFingerprint(self):
        actor = self.actor("CHANTH")
        state = self.state()
        state["actors"][actor.getName()]["scriptName"] = "Marek"
        self.writeState(state)
        before = deepcopy(self.state())
        talks = actor.getNumericProperty("plugin_cityPoisonTalkCount")
        with self.assertRaisesRegex(self.clock.PoisonBindingChanged, "finite CRE/dialogue binding"):
            self.clock.poisonBeginDialogue(actor)
        self.assertEqual(before, self.state())
        self.assertEqual(talks, actor.getNumericProperty("plugin_cityPoisonTalkCount"))

    def testMapOwnershipUsesActualBoundMapObjectApiInsteadOfUnboundBaseMethod(self):
        native_base = type(
            "BoundGameObjectApi",
            (),
            {
                name: staticmethod(value)
                for name, value in NativeObject.__dict__.items()
                if callable(value) and not name.startswith("__") and name != "getMap"
            },
        )
        self.assertFalse(hasattr(native_base, "getMap"))
        importer = self.fixture.namespace["__builtins__"]["__import__"]
        for cell in importer.__closure__:
            if isinstance(cell.cell_contents, dict) and "CCreature" in cell.cell_contents:
                cell.cell_contents["CGameObject"] = native_base
        failure = None
        binding = None
        try:
            binding = self.clock.poisonCapture()
            self.clock.poisonRequire(binding)
        except AttributeError as error:
            failure = str(error)
        self.assertIsNone(failure, "The actual CGameObject Python API has no getMap descriptor")
        self.assertIs(binding["objectClass"], native_base)
        self.assertIs(binding["mapObjectClass"], NativeObject)
        self.assertIsNotNone(self.clock.poisonBeginDialogue(self.actor("CHANTH")))
        marek = self.create("MAREK1", "AR0115", [406, 344], "AR0115.BCS#spawn0")
        antidote = next(item for item in marek.items if item.getStringProperty("plugin_citySourceItem") == "POTN47")
        self.assertTrue(self.clock.transferPoisonSourceItem(marek, self.player, antidote))
        self.assertEqual(10019, self.player.getNumericProperty("exp"))

    def testLootObservationWaitsForActualQueuedDeathProducerBeforeJournalChoice(self):
        marek = self.create("MAREK1", "AR0115", [406, 344], "AR0115.BCS#spawn0")
        antidote = next(item for item in marek.items if item.getStringProperty("plugin_citySourceItem") == "POTN47")
        marek.items.remove(antidote)
        self.player.items.append(antidote)
        marek.hp = 0
        self.world.removeObject(marek)
        before = deepcopy(self.state())
        self.assertFalse(self.clock.observePoisonAcquisition())
        self.assertEqual(before, self.state())
        self.assertEqual(19, self.player.getNumericProperty("exp"))
        self.assertEqual(
            [10, 0, 0], json.loads(antidote.getStringProperty("plugin_cityCharges").removeprefix("city-json:"))
        )
        self.assertTrue(self.clock.poisonRecordDeath(marek))
        self.assertTrue(self.clock.observePoisonAcquisition())
        self.assertEqual(43, self.state()["journal"][-1]["sourceConsumer"])
        self.assertEqual(10019, self.player.getNumericProperty("exp"))

    def testActualDeathCallbackRetainsGenuineCorpseBeforeOwnershipObservation(self):
        marek = self.create("MAREK1", "AR0115", [406, 344], "AR0115.BCS#spawn0")
        original = next(item for item in marek.items if item.getStringProperty("plugin_citySourceItem") == "POTN47")
        clone = self.fixture.createObject(original.getTypeId())
        clone.properties = deepcopy(original.properties)
        self.player.items.append(clone)
        marek.hp = 0
        self.world.removeObject(marek)
        trigger = self.fixture.object(self.fixture.classes["BaldursGateDeathTrigger"], "sourceActualDeathCallback")
        with self.assertRaisesRegex(self.clock.PoisonBindingChanged, "distinct actual owned instances"):
            list(trigger.triggerFlow(marek, None))
        self.assertIs(marek, self.clock.getObjectProperty("plugin_cityCorpse_" + marek.getName()))
        self.assertEqual(19, self.player.getNumericProperty("exp"))
        self.assertEqual(0, self.state()["globals"].get("PartyCured", 0))
        self.assertFalse(self.clock.poisonRecordDeath(marek))

    def testDisabledSourcePortDoesNotGuardLegacyQuestTextWithPlayerLiveness(self):
        self.clock.setBoolProperty("plugin_cityPoisonSourceEnabled", False)
        self.player.hp = 0
        before = deepcopy((self.clock.properties, self.world.properties, self.player.properties))
        problem = None
        try:
            self.assertIsNone(self.clock.poisonQuestPresentation("marekPoison"))
            quest_object = self.fixture.game.createObject("cityMarekPoisonQuest")
            self.assertIsInstance(quest_object.getObjective(), str)
        except RuntimeError as error:
            problem = str(error)
        self.assertIsNone(problem, "Disabled source presentation must preserve the existing legacy read path")
        self.assertEqual(before, (self.clock.properties, self.world.properties, self.player.properties))

    def testDisabledLegacyDialogRowsRetainOriginalQuestAndServiceReturnStates(self):
        expected = {
            "cityAr0300Actor28Dialog": "2749ba601a94bc36fedb12ca73093975d19faad49bca0c27c9e81f23c8abc0ae",
            "cityAr0300Actor29Dialog": "1eb60025fc86a627a528dba0c3c2dcf31dde7008da60a23d6a0d387f1bacb245",
            "cityAr0132Actor1Dialog": "bcb52a033d1554005841ff933c6d75919deef3343e0e5cbeb32bf74cc65b598c",
            "cityAr0726Actor1Dialog": "03d72de8658baca021deb2e62b2b49ed95a11c863807be79aa887143f66a0e1a",
            "cityAr0609Actor1Dialog": "d11209586693ecac401f5f8b3dee1b89644bd01f620d60edc7452a1609020e08",
            "cityAr0609ScriptActorJalantDialog": "7b5c4a43fab7b1aeec2985662ceacfd3fa08f81c659430193122f06da005530f",
        }
        changed = [
            identity
            for identity, digest in expected.items()
            if sha256(json.dumps(self.config[identity], ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
            != digest
        ]
        self.assertEqual([], changed, "Default-off legacy dialogs must remain byte-equivalent as JSON")
        for row in self.definitions["initialActors"]:
            self.assertNotEqual(row["id"] + "Dialog", row["dialogId"])
            dialog = self.config[row["dialogId"]]
            talk = [
                option
                for state in dialog["properties"]["states"]
                for option in state["properties"].get("options", [])
                if option["properties"].get("action") == "talk"
            ]
            self.assertEqual(["EXIT"], [option["properties"]["nextStateId"] for option in talk])

    def testDisabledSourceFlagUsesActualLegacyPersonTriggerAndLoreTalk(self):
        self.clock.setBoolProperty("plugin_cityPoisonSourceEnabled", False)
        actor = self.actor("MAREK")
        hook = self.fixture.object(self.fixture.classes["BaldursGatePersonTrigger"], "legacyPersonEntryTest")
        flow = hook.triggerFlow(actor, SimpleNamespace(getCause=lambda: self.player))
        request = next(flow)
        dialog = request["args"][0]
        self.assertEqual(actor.getTypeId() + "Dialog", dialog.getTypeId())
        with self.assertRaises(StopIteration):
            flow.send(None)
        before = deepcopy(self.state())
        lore = dialog.talkFlow()
        self.assertEqual("showReader", next(lore)["operation"])
        with self.assertRaises(StopIteration):
            lore.send(None)
        self.assertEqual(1, actor.getNumericProperty("plugin_cityTalkCount"))
        self.assertEqual(0, actor.getNumericProperty("plugin_cityPoisonTalkCount"))
        self.assertEqual(before, self.state())

    def testIndependentXpPolicyDoesNotReadPoisonStateOrRequireLivingHero(self):
        self.clock.setBoolProperty("plugin_cityPoisonSourceEnabled", False)
        self.clock.setStringProperty("plugin_cityPoisonSourceState", "unreadable-poison-state")
        self.player.hp = 0
        before = deepcopy((self.clock.properties, self.player.properties))
        self.assertTrue(self.clock.ensureCitySourceKillXp())
        self.assertTrue(self.world.getBoolProperty("plugin_citySourceKillXp"))
        self.assertEqual(before, (self.clock.properties, self.player.properties))

    def testIndependentXpPolicyCanResumeWithoutAssignedHeroAndKeepsForeignMaps(self):
        self.world.player = None
        self.world.objects.pop("player")
        self.assertTrue(self.clock.ensureCitySourceKillXp())
        self.world.setBoolProperty("plugin_citySourceKillXp", False)
        self.world.setStringProperty("mapName", "candlekeep")
        self.assertFalse(self.clock.ensureCitySourceKillXp())
        self.assertFalse(self.world.getBoolProperty("plugin_citySourceKillXp"))

    def testIndependentXpPolicyChecksEpochAfterActualFlagWrite(self):
        importer = self.fixture.namespace["__builtins__"]["__import__"]
        for cell in importer.__closure__:
            if isinstance(cell.cell_contents, dict) and "CCreature" in cell.cell_contents:
                base = cell.cell_contents["CGameObject"]
                methods = {
                    name: staticmethod(getattr(base, name)) for name in base.__dict__ if not name.startswith("__")
                }

                def staleWrite(owner, key, value):
                    NativeObject.setBoolProperty(owner, key, value)
                    if key == "plugin_citySourceKillXp":
                        self.fixture.game.map_epoch += 1

                methods["setBoolProperty"] = staticmethod(staleWrite)
                cell.cell_contents["CGameObject"] = type("StaleXpWriteApi", (), methods)
        with self.assertRaisesRegex(self.clock.PoisonBindingChanged, "actual game/map/clock binding"):
            self.clock.ensureCitySourceKillXp()
        self.assertEqual(19, self.player.getNumericProperty("exp"))

    def journalHelpScenario(self):
        lothander = self.create("LOTHAN", "AR0700", [2361, 1090], "AR0700.BCS#spawn4")
        self.globalValue("LothanderMove", 3)
        requests = self.drive(
            self.clock.poisonDialogueFlow(lothander),
            ["LOTHAN.DLG:edge1", "LOTHAN.DLG:edge3", "LOTHAN.DLG:edge10"],
        )
        self.assertTrue(requests)
        self.assertEqual(1, self.state()["globals"]["HelpLothander"])
        return lothander

    def journalPresentation(self, key):
        identities = {
            "marekPoison": "cityMarekPoisonQuest",
            "lothanderGeas": "cityLothanderGeasQuest",
            "divinerPoison": "cityDivinerPoisonQuest",
        }
        obj = self.fixture.game.createObject(identities[key])

        def snapshot():
            return deepcopy(
                {
                    "clock": self.clock.properties,
                    "world": self.world.properties,
                    "player": self.player.properties,
                    "items": [(item.getName(), item.getTypeId(), item.properties) for item in self.player.items],
                    "active": [(q.getName(), q.getTypeId(), q.properties) for q in self.player.getQuests()],
                    "completed": [(q.getName(), q.getTypeId(), q.properties) for q in self.player.getCompletedQuests()],
                    "notices": self.notices,
                }
            )

        before = snapshot()
        result = {"objective": obj.getObjective(), "reward": obj.getReward(), "hint": obj.getHint()}
        self.assertEqual(before, snapshot())
        self.assertEqual(result, {"objective": obj.getObjective(), "reward": obj.getReward(), "hint": obj.getHint()})
        self.assertEqual(before, snapshot())
        return result

    def testActiveSourceJournalUsesKnownDivinerLeadWithoutTempleSpoilers(self):
        self.journalHelpScenario()
        for key in ("marekPoison", "lothanderGeas"):
            with self.subTest(key=key):
                row = self.journalPresentation(key)
                self.assertIn("geas", row["objective"])
                self.assertIn("Diviner", row["hint"])
                self.assertIn("market square", row["hint"])
                self.assertNotIn(": active", row["objective"])
                self.assertNotIn("source items", row["hint"])
                for clue in ("Jalantha", "Water Queen", "Blade and Stars", "Blushing Mermaid"):
                    self.assertNotIn(clue, " ".join(row.values()))
        self.assertEqual(5000, self.player.getNumericProperty("gold"))
        self.assertEqual(19, self.player.getNumericProperty("exp"))

    def testCompletedDivinerJournalUsesHeardTempleClueBeforeInnLocation(self):
        self.journalHelpScenario()
        requests = self.drive(
            self.clock.poisonDialogueFlow(self.actor("DIVINE")), ["DIVINE.DLG:edge1", "DIVINE.DLG:edge4"]
        )
        self.assertTrue(any("Jalantha" in str(row.get("args", [])) for row in requests))
        self.assertEqual(1, self.state()["globals"]["DivinerAsked"])
        self.assertEqual(4950, self.player.getNumericProperty("gold"))
        self.assertEqual(19, self.player.getNumericProperty("exp"))
        for key in ("marekPoison", "lothanderGeas", "divinerPoison"):
            with self.subTest(key=key):
                row = self.journalPresentation(key)
                self.assertIn("Jalantha", row["objective"])
                self.assertIn("Water Queen's House", row["objective"])
                self.assertNotIn("Blade and Stars", " ".join(row.values()))
                self.assertNotIn("Blushing Mermaid", " ".join(row.values()))
        diviner = self.journalPresentation("divinerPoison")
        self.assertEqual("The reading cost 50 gold and grants no experience.", diviner["reward"])
        self.assertIn("Tell Lothander", diviner["hint"])

    def testActiveGeasJournalRevealsInnOnlyAfterLothanderNamesIt(self):
        lothander = self.journalHelpScenario()
        self.drive(self.clock.poisonDialogueFlow(self.actor("DIVINE")), ["DIVINE.DLG:edge1", "DIVINE.DLG:edge4"])
        self.drive(self.clock.poisonDialogueFlow(lothander), [])
        self.assertEqual(2, self.state()["globals"]["DivinerAsked"])
        for key in ("marekPoison", "lothanderGeas"):
            row = self.journalPresentation(key)
            self.assertIn("Jalantha", row["objective"])
            self.assertIn("Blade and Stars Inn", row["hint"])
            self.assertNotIn("Blushing Mermaid", " ".join(row.values()))
        self.assertEqual(4950, self.player.getNumericProperty("gold"))
        self.assertEqual(19, self.player.getNumericProperty("exp"))

    def testWrongDivinerQuestionDoesNotRevealGeasAnswerOrCompleteItsTask(self):
        self.journalHelpScenario()
        self.drive(self.clock.poisonDialogueFlow(self.actor("DIVINE")), ["DIVINE.DLG:edge1", "DIVINE.DLG:edge5"])
        self.assertEqual(9, self.state()["globals"]["LothanderMove"])
        self.assertEqual(0, self.state()["globals"].get("DivinerAsked", 0))
        self.assertFalse(any(q.getTypeId() == "cityDivinerPoisonQuest" for q in self.player.getCompletedQuests()))
        for key in ("marekPoison", "lothanderGeas"):
            row = self.journalPresentation(key)
            self.assertIn("another question", row["objective"])
            self.assertIn("one question each day", row["hint"])
            self.assertNotIn("Jalantha", " ".join(row.values()))
            self.assertNotIn("Water Queen", " ".join(row.values()))
        self.assertEqual(4950, self.player.getNumericProperty("gold"))
        self.assertEqual(19, self.player.getNumericProperty("exp"))

    def testLaterAntidoteLeadRequiresLothanderOutcomeWithoutCompletingPoison(self):
        self.journalHelpScenario()
        for outcome in ("scrollReturned", "priestsDeadNoRelease"):
            state = self.state()
            state["geasOutcome"] = outcome
            self.writeState(state)
            row = self.journalPresentation("marekPoison")
            self.assertIn("Blushing Mermaid Inn", row["objective"])
            self.assertIn("Marek", row["hint"])
            self.assertEqual(0, self.state()["globals"].get("PartyCured", 0))
            self.assertFalse(any(q.getTypeId() == "cityMarekPoisonQuest" for q in self.player.getCompletedQuests()))

    def testExistingCompletedCureAndGeasPresentationRemainsExact(self):
        for outcome, expected in (
            (
                "scrollReturned",
                {
                    "objective": "The geas-removal scroll was returned to Lothander; he left an antidote half.",
                    "reward": "Returning the scroll grants 1,500 experience and an antidote half.",
                },
            ),
            (
                "priestsDeadNoRelease",
                {
                    "objective": "The priests could not provide the scroll. Lothander left an antidote half and departed.",
                    "reward": "The geas remains unresolved. This fallback grants an antidote half and no experience.",
                },
            ),
        ):
            state = self.state()
            state["geasOutcome"] = outcome
            self.writeState(state)
            self.assertEqual(expected, self.clock.poisonQuestPresentation("lothanderGeas"))
        state = self.state()
        state["globals"]["PartyCured"] = 1
        state["journal"].append({"sourceConsumer": 44, "text": "Retained actual cure journal witness."})
        self.writeState(state)
        self.assertEqual(
            {
                "objective": "Retained actual cure journal witness.",
                "reward": "The cure grants 10,000 experience once.",
            },
            self.clock.poisonQuestPresentation("marekPoison"),
        )

    def testDisabledLegacyQuestHintReturnsBeforeLivingSourceBinding(self):
        self.clock.setBoolProperty("plugin_cityPoisonSourceEnabled", False)
        self.player.hp = 0
        self.clock.poisonCapture = lambda: self.fail("Disabled legacy hint entered the source binding")
        before = deepcopy((self.clock.properties, self.world.properties, self.player.properties))
        quest = self.fixture.game.createObject("cityMarekPoisonQuest")
        self.assertEqual("Follow the named people, source items and city journal.", quest.getHint())
        quest.setStringProperty("hint", "Existing custom legacy hint.")
        self.assertEqual("Existing custom legacy hint.", quest.getHint())
        self.assertEqual(before, (self.clock.properties, self.world.properties, self.player.properties))

    def testProfitAnswerDoesNotInventMoveNineOrAHeardGeasClue(self):
        self.journalHelpScenario()
        self.drive(self.clock.poisonDialogueFlow(self.actor("DIVINE")), ["DIVINE.DLG:edge1", "DIVINE.DLG:edge3"])
        self.assertEqual(1, self.state()["globals"]["LothanderMove"])
        self.assertEqual(0, self.state()["globals"].get("DivinerAsked", 0))
        self.assertFalse(any(q.getTypeId() == "cityDivinerPoisonQuest" for q in self.player.getCompletedQuests()))
        for key in ("marekPoison", "lothanderGeas"):
            row = self.journalPresentation(key)
            self.assertIn("geas", row["objective"])
            self.assertIn("Diviner", row["hint"])
            self.assertNotIn("Jalantha", " ".join(row.values()))
            self.assertNotIn("Water Queen", " ".join(row.values()))
        self.assertEqual(4950, self.player.getNumericProperty("gold"))
        self.assertEqual(19, self.player.getNumericProperty("exp"))

    def testBeforeAgreeingToGeasHelpJournalDoesNotInventDivinerClue(self):
        lothander = self.create("LOTHAN", "AR0700", [2361, 1090], "AR0700.BCS#spawn4")
        self.globalValue("LothanderMove", 3)
        session = self.clock.poisonBeginDialogue(lothander)
        self.assertTrue(self.clock.poisonChooseEdge(session, 1))
        self.assertEqual(0, self.state()["globals"].get("HelpLothander", 0))
        row = self.journalPresentation("marekPoison")
        self.assertIn("Speak with Lothander", row["objective"])
        for clue in ("Diviner", "Jalantha", "Water Queen", "Blade and Stars", "Blushing Mermaid"):
            self.assertNotIn(clue, " ".join(row.values()))
        self.assertIsNone(self.clock.poisonQuestPresentation("lothanderGeas"))


if __name__ == "__main__":
    unittest.main()
