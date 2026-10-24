# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute authored city callbacks with native-shaped doubles; no native gameplay credit."""

import ast
import builtins
import json
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.build_baldurs_gate_city import decodeCityData
from scripts.build_baldurs_gate_city_dialogs import prepareStores, questDialogRows, renderCallbacks, storeDialogRows
from scripts.build_baldurs_gate_city_relocations import buildRelocations
from tests.hook_flow_support import installHookFlows
from tests.test_candlekeep_content import ModelMap, ModelObject, ModelPlayer

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "res/maps/baldursGate/script.py"
DOCUMENT = json.loads((ROOT / "tests/fixtures/baldurs_gate_city_quests.json").read_text(encoding="utf-8"))


def nativePluginBuiltins():
    source = (ROOT / "src/core/CLoader.cpp").read_text(encoding="utf-8")
    declaration = re.search(r"const std::vector<std::string> allowedNames = \{(.*?)\};", source, re.S)
    if not declaration:
        raise ValueError("Cannot locate native resource builtin contract")
    result = {name: getattr(builtins, name) for name in re.findall(r'"([^"\\]+)"', declaration.group(1))}

    def resourceImport(name, globals=None, locals=None, fromlist=(), level=0):
        if level or name not in ("game", "json"):
            raise ImportError("Native resource plugins may only import game and json")
        return builtins.__import__(name, globals, locals, fromlist, level)

    result["__import__"] = resourceImport
    return result


def relocationFixture():
    ids = (
        "AR0153.BCS#spawn6",
        "AR0153.BCS#spawn7",
        "AR0300.BCS#spawn3",
        "AR1300.BCS#spawn3",
        "AR0128.BCS#spawn0",
        "AR1100.BCS#spawn9",
        "AR0123.BCS#spawn0",
        "AR1100.BCS#spawn8",
        "AR0800.BCS#spawn7",
    )
    source = json.loads((ROOT / "tests/fixtures/baldurs_gate_city_source.json").read_text(encoding="utf-8"))
    return {
        "scriptedActors": [row for row in source["scriptedActors"] if row["sourceId"] in ids],
        "stores": source["stores"],
        "items": source["items"],
        "stackContainers": [
            container
            for area in ("AR0111", "AR0136", "AR0308", "AR0700")
            for container in source["areas"][area]["containers"]
            if container["sourceId"]
            in ("AR0111#container1", "AR0136#container2", "AR0308#container1", "AR0700#container10")
        ],
        "stackNpcPotion": next(row for row in source["creatures"]["GSARCH01"]["items"] if row["item"] == "POTN08"),
    }


RELOCATION_SOURCE = relocationFixture()


class CityObject(ModelObject):
    def __getattribute__(self, key):
        if key in {"getExp", "hasProperty", "setPosX", "setPosY", "setPosZ", "setNpc", "setName"}:
            raise AttributeError("No such native binding: " + key)
        return super().__getattribute__(key)

    def __getattr__(self, key):
        properties = object.__getattribute__(self, "properties")
        if key in properties:
            return properties[key]
        raise AttributeError(key)

    def __setattr__(self, key, value):
        if key not in {
            "game",
            "name",
            "properties",
            "items",
            "equipped",
            "effects",
            "stats",
            "base_stats",
            "quests",
            "completed",
        } and isinstance(value, (dict, list, set)):
            raise TypeError("Unsupported CGameObject property type")
        object.__setattr__(self, key, value)

    def setName(self, value):
        self.name = value

    def addTag(self, value):
        self.properties.setdefault("tags", []).append(value)

    def relocateWithoutMoveHooks(self, point):
        self.moveTo(point.x, point.y, point.z)


class CityCreature(ModelPlayer, CityObject):
    def __init__(self, game=None, name="", **properties):
        ModelPlayer.__init__(self, game)
        self.name = name
        self.properties.update(properties)

    def isPlayer(self):
        return False

    def equipItem(self, slot, item):
        previous = self.equipped.pop(slot, None)
        if previous:
            self.items.append(previous)
        if item:
            self.items.remove(item)
            self.equipped[slot] = item


class CityPlayer(ModelPlayer, CityObject):
    def getPlayerClassId(self):
        return self.getStringProperty("classId") or "Warrior"


class CityMap(ModelMap):
    def removeObject(self, obj):
        super().removeObject(obj)
        for hook in self.registered_triggers:
            if hook.getStringProperty("event") == "onDestroy" and hook.getStringProperty("object") == obj.getName():
                hook.trigger(obj, None)


class CityModel:
    def __init__(self, **stats):
        self.types, self.resources, self.readers = {}, {}, []
        self.actor_count = 0
        self.gui = Mock()
        self.player = CityPlayer(self, **stats)
        self.game_map = CityMap(self)
        self.game_map.setNumericProperty("plugin_cityPhase", 5)
        self.game_map.setNumericProperty("plugin_cityReputation", 10)
        self.game_map.setStringProperty("activeSimulationRegion", "AR0100")
        api = ModuleType("game")
        api.CCreature = CityCreature
        for name in ("CDialog", "CBuilding", "CQuest", "CTrigger", "CEvent"):
            setattr(api, name, type(name, (CityObject,), {}))

        def register(_context):
            def save(cls):
                self.types[cls.__name__] = cls
                return cls

            return save

        api.register = register
        api.mapQuest = lambda _map: lambda cls: cls
        api.Coords = lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)

        def claimOnce(obj, key):
            if obj.getBoolProperty(key):
                return False
            obj.setBoolProperty(key, True)
            return True

        api.claim_once = claimOnce
        installHookFlows(api)
        api.showReader = lambda *_args: self.readers.append(_args)
        api.choose = lambda *_args: getattr(self, "choice", "")
        namespace = {"__builtins__": nativePluginBuiltins(), "__name__": "baldursGateResource"}
        with patch.dict(sys.modules, game=api):
            exec(compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec"), namespace)
            namespace["load"](None, self)
        self.namespace = namespace
        self.clock = self.createObject("BaldursGateClock")
        self.clock.setStringProperty("name", "cityClock")
        self.game_map.addObject(self.clock)
        self.clock.setStringProperty("questDefinitions", json.dumps(DOCUMENT))
        self.clock.setStringProperty("areaAtlas", json.dumps({"AR0100": {"bounds": [0, 0, 0, 100, 100]}}))
        for row in DOCUMENT["quests"]:
            self.resources[namespace["questId"](row["id"])] = {
                "class": "BaldursGateQuest",
                "properties": {"questKey": row["id"]},
            }

    def getMap(self):
        return self.game_map

    def getGuiHandler(self):
        return self.gui

    def getSlotConfiguration(self):
        return SimpleNamespace(getFittingSlots=lambda _item: ["rightHand"])

    def createObject(self, name):
        row = self.resources.get(name, {})
        cls = self.types.get(row.get("class", name), CityCreature if row.get("class") == "CCreature" else CityObject)
        properties = {"typeId": name, **row.get("properties", {})}
        if name.startswith("cityItem"):
            code = name[len("cityItem") :].upper()
            properties["plugin_citySourceItem"] = code
            metadata = RELOCATION_SOURCE["items"].get(code, {})
            for key, source in (
                ("plugin_cityStackSize", "stack_size"),
                ("plugin_cityItemType", "item_type"),
                ("plugin_cityValue", "price"),
            ):
                properties.setdefault(key, metadata.get(source, 0))
        return cls(self, name, **properties)

    def actor(self, label, area="AR0100", **properties):
        self.actor_count += 1
        actor = CityCreature(self, "actor" + str(self.actor_count), label=label, sourceArea=area, **properties)
        self.game_map.addObject(actor)
        return actor

    def dialog(self, actor):
        self.player.moveTo(*vars(actor.getCoords()).values())
        dialog = self.createObject("BaldursGateDialog")
        dialog.setStringProperty("actorId", actor.getName())
        return dialog

    def item(self, code, owner=None, **properties):
        item = self.createObject(self.namespace["itemId"](code))
        item.setStringProperty("name", code + str(len((owner or self.player).items)))
        item.properties.update(properties)
        (owner or self.player).addItem(item)
        return item

    def kill(self, actor):
        actor.setHp(0)
        self.createObject("BaldursGateDeathTrigger").trigger(actor, None)
        self.game_map.removeObject(actor)

    def installRelocations(self):
        definitions = buildRelocations(
            RELOCATION_SOURCE, usablePosition=lambda _area, point: (point[0] // 64, point[1] // 64, 0)
        )
        self.clock.setStringProperty("relocationDefinitions", json.dumps(definitions))
        return definitions

    def installLookoutOfficer(self):
        name = "cityAr0300ScriptActorWatchm"
        self.resources[name] = {
            "class": "CCreature",
            "properties": {
                "sourceCreature": "WATCHM",
                "sourceArea": "AR0300",
                "label": "Watchman",
                "sourceSpawnFact": "AR0300.BCS#spawn7",
            },
        }
        self.clock.setStringProperty(
            "actorDefinitions",
            json.dumps(
                [
                    {
                        "id": name,
                        "sourceCreature": "WATCHM",
                        "x": 0,
                        "y": 28,
                        "z": 0,
                        "phase": 5,
                        "phaseMax": 7,
                        "requiresFlag": "narlenOfficerDue",
                    }
                ]
            ),
        )
        return name

    def canonical(self, code):
        definitions = self.installRelocations()
        row = next(entry for entry in definitions if entry["sourceCreature"] == code)
        actor = CityCreature(
            self,
            row["canonicalActorId"],
            label={"NARLEN": "Narlen Darkwalk", "ALDETH": "Aldeth Sashenstar", "TAMOKO": "Tamoko"}[code],
            sourceCreature=code,
            sourceArea=row["scenes"][-1]["sourceArea"],
        )
        self.game_map.addObject(actor)
        self.clock.initializeActor(actor)
        self.clock.applySchedules()
        return actor


class BaldursGateCityContentTest(unittest.TestCase):
    def testResourceCallbacksUseOnlyNativeAllowedBuiltins(self):
        allowed = nativePluginBuiltins()
        unsupported = sorted(
            {
                node.id
                for node in ast.walk(ast.parse(SCRIPT.read_text(encoding="utf-8")))
                if isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id in vars(builtins)
                and node.id not in allowed
            }
        )
        self.assertEqual([], unsupported)
        model = CityModel()
        self.assertEqual(set(allowed), set(model.namespace["__builtins__"]))
        for missing in ("next", "zip", "id", "KeyError"):
            self.assertNotIn(missing, model.namespace["__builtins__"])

    def testNativeIterationHelpersKeepFirstMatchAndShortestPairSemantics(self):
        model = CityModel()
        observed = []

        def values():
            for value in (7, 8, 9):
                observed.append(value)
                yield value

        self.assertEqual(7, model.namespace["firstMatch"](values(), -1))
        self.assertEqual([7], observed)
        self.assertEqual(-1, model.namespace["firstMatch"]([], -1))
        self.assertIsNone(model.namespace["firstMatch"]([]))
        self.assertEqual([(1, "a"), (2, "b")], list(model.namespace["pairedValues"]([1, 2, 3], ("a", "b"))))
        self.assertEqual([], list(model.namespace["pairedValues"]([], [1])))

    def testEveryAuthoredQuestAndExcursionHasRealConcreteCallbacks(self):
        model = CityModel()
        dialog = model.createObject("BaldursGateDialog")
        for quest in DOCUMENT["quests"]:
            for selector in quest["givers"] + [s for row in quest["outcomes"] for s in row.get("at", [])]:
                properties = {
                    "label": selector.get("label", ""),
                    "sourceArea": selector.get("area", ""),
                    "sourceCreature": selector.get("creature", ""),
                }
                for row in questDialogRows(DOCUMENT, properties):
                    self.assertTrue(callable(getattr(dialog, row["action"], None)), row)
                    self.assertTrue(callable(getattr(dialog, row["condition"], None)), row)
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        self.assertNotIn(
            "BaldursGateCreature", {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        )
        self.assertFalse(DOCUMENT["originalParityEstablished"])

    def testInventoryUsesOriginalSourceIndicesAfterExcludedEditionRows(self):
        model = CityModel()
        actor = model.actor(
            "Guard",
            sourceInventory=json.dumps(
                [
                    {"sourceIndex": 0, "item": "MISC01", "flags": 1},
                    {"sourceIndex": 2, "item": "SW1H01", "flags": 15, "expiration": 77, "charges": [3, 4, 5]},
                ]
            ),
            sourceItemSlots=json.dumps([2] + [65535] * 39),
        )
        model.clock.initializeActor(actor)
        sword = actor.getEquipped()["rightHand"]
        self.assertEqual("SW1H01", sword.getStringProperty("plugin_citySourceItem"))
        self.assertEqual([3, 4, 5], decodeCityData(sword.getStringProperty("plugin_cityCharges")))
        self.assertEqual(1, sword.getNumericProperty("plugin_cityQuantity"))
        self.assertEqual(77, sword.getNumericProperty("plugin_cityExpiration"))
        self.assertTrue(sword.getBoolProperty("plugin_cityUnstealable"))
        self.assertTrue(sword.getBoolProperty("plugin_cityUndroppable"))
        self.assertTrue(sword.getBoolProperty("plugin_cityStolen"))
        model.clock.initializeActor(actor)
        self.assertEqual(2, len(actor.items) + len(actor.equipped))

    def testQuestOutcomeCommitsOnceBeforeYieldingTheNativeJournalCheck(self):
        model = CityModel(intelligence=12)
        actor = model.actor("Quinn", "AR0157")
        model.clock.initializeActor(actor)
        dialog = model.dialog(actor)
        self.assertTrue(dialog.acceptQuinnDagger())
        model.item("DAGG06")
        before = model.player.getNumericProperty("exp"), model.player.getGold()
        model.player.checkQuests = Mock(wraps=model.player.checkQuests)
        flow = dialog.performQuestOutcomeFlow("quinnDagger", "complete")
        try:
            pending = next(flow)
            self.assertEqual("gui.checkQuests", pending["operation"])
            self.assertEqual((model.player,), pending["args"])
            model.player.checkQuests.assert_not_called()
            self.assertEqual("completed", model.game_map.getStringProperty("plugin_cityQuest_quinnDagger"))
            expected = before[0] + 950, before[1]
            self.assertEqual(expected, (model.player.getNumericProperty("exp"), model.player.getGold()))
            self.assertFalse(dialog.questQuinnDaggerComplete(), "A suspended journal check cannot grant twice")
            pending["args"][0].checkQuests()
            with self.assertRaises(StopIteration) as completed:
                flow.send(None)
            self.assertIs(True, completed.exception.value)
            model.player.checkQuests.assert_called_once_with()
            self.assertEqual(expected, (model.player.getNumericProperty("exp"), model.player.getGold()))
            self.assertEqual(1, len(model.player.getCompletedQuests()))
        finally:
            flow.close()

    def testRewardStockAndPriorTheftShareOneItemAndDoNotRespawn(self):
        model = CityModel(intelligence=12)
        actor = model.actor("Quinn", "AR0157")
        model.clock.initializeActor(actor)
        reward = next(item for item in actor.items if item.getStringProperty("plugin_citySourceItem") == "MISC32")
        actor.removeQuestItem(lambda item: item == reward)
        model.player.addItem(reward)
        model.clock.initializeActor(actor)
        dialog = model.dialog(actor)
        self.assertTrue(dialog.acceptQuinnDagger())
        model.item("DAGG06")
        before = model.player.getNumericProperty("exp"), model.player.getGold()
        self.assertTrue(dialog.questQuinnDaggerComplete())
        self.assertEqual((before[0] + 950, before[1]), (model.player.getNumericProperty("exp"), model.player.getGold()))
        self.assertEqual(
            [reward],
            [item for item in model.player.items if item.getStringProperty("plugin_citySourceItem") == "MISC32"],
        )
        self.assertFalse(dialog.questQuinnDaggerComplete())
        self.assertEqual("completed", model.game_map.getStringProperty("plugin_cityQuest_quinnDagger"))

    def testSocialBoundarySelectsExactlyOneConditionalReward(self):
        for intelligence, expected_xp, expected_gold in ((11, 400, 80), (12, 900, 0)):
            with self.subTest(intelligence=intelligence):
                model = CityModel(intelligence=intelligence)
                actor = model.actor("Rinnie", "AR0006")
                model.clock.initializeActor(actor)
                dialog = model.dialog(actor)
                self.assertTrue(dialog.acceptRinnieBook())
                model.item("BOOK55")
                before = model.player.getGold()
                eligible = [row for row in DOCUMENT["quests"] if row["id"] == "rinnieBook"][0]
                choices = [row for row in eligible["outcomes"] if dialog.canQuestOutcome("rinnieBook", row["id"])]
                self.assertEqual(1, len(choices))
                self.assertTrue(dialog.performQuestOutcome("rinnieBook", choices[0]["id"]))
                self.assertEqual(expected_xp, model.player.getNumericProperty("exp"))
                self.assertEqual(before + expected_gold, model.player.getGold())

    def testLockThresholdsAndSourceProhibitionsTakePrecedence(self):
        model = CityModel()
        box = model.createObject("BaldursGateContainer")
        box.setStringProperty("name", "box")
        box.setBoolProperty("locked", True)
        model.game_map.addObject(box)
        dialog = model.dialog(box)
        for threshold in (12, 16, 18):
            box.setNumericProperty("lockAgility", threshold)
            model.player.stats.setNumericProperty("agility", threshold - 1)
            self.assertFalse(dialog.canUnlock())
            model.player.stats.setNumericProperty("agility", threshold)
            self.assertTrue(dialog.canUnlock())
        box.setBoolProperty("forbidPicking", True)
        self.assertFalse(dialog.canUnlock())
        for threshold in (12, 14):
            box.setNumericProperty("forceStrength", threshold)
            model.player.stats.setNumericProperty("strength", threshold - 1)
            self.assertFalse(dialog.canForce())
            model.player.stats.setNumericProperty("strength", threshold)
            self.assertTrue(dialog.canForce())
        box.setBoolProperty("magicallyLocked", True)
        self.assertFalse(dialog.canForce())

    def testPoisonStartsAtLothanderAcceptanceAndExpiresAtExactDeadline(self):
        model = CityModel()
        marek = model.actor("Marek")
        model.dialog(marek).talk()
        self.assertEqual("", model.game_map.getStringProperty("plugin_cityDeadlines"))
        lothander = model.actor("Lothander")
        self.assertTrue(model.dialog(lothander).acceptMarekPoison())
        model.clock.advanceTicks(11999)
        self.assertEqual("active", model.game_map.getStringProperty("plugin_cityQuest_marekPoison"))
        model.clock.advanceTicks(1)
        self.assertEqual("failed", model.game_map.getStringProperty("plugin_cityQuest_marekPoison"))
        self.assertTrue(model.game_map.getBoolProperty("plugin_cityFlag_poisonFatal"))

    def testPhaseParkingRetainsSameActorInventoryAndDoesNotRecordDeath(self):
        model = CityModel()
        actor = model.actor("Scar", phaseMin=5, phaseMax=5)
        item = model.item("RING16", actor)
        model.clock.initializeActor(actor)
        model.game_map.setNumericProperty("plugin_cityPhase", 7)
        model.clock.applySchedules()
        self.assertIsNone(model.game_map.getObjectByName(actor.getName()))
        self.assertIs(actor, model.clock.getObjectProperty("plugin_cityParked_" + actor.getName()))
        self.assertFalse(model.game_map.getBoolProperty("plugin_cityDeath_" + actor.getName()))
        model.game_map.setNumericProperty("plugin_cityPhase", 5)
        model.clock.applySchedules()
        self.assertIs(actor, model.game_map.getObjectByName(actor.getName()))
        self.assertIn(item, actor.items)

    def testScheduleBitsUseHalfHourCenteredSourceHours(self):
        model = CityModel()
        slot = model.namespace["scheduleSlot"]
        self.assertEqual(7, slot(0))  # 08:00 belongs to bit7, which spans07:30-08:29.
        self.assertEqual(8, slot(25))
        actor = model.actor("Night watch", sourceSchedule=1 << 23)
        model.game_map.setNumericProperty("plugin_cityTicks", 775)  # 23:30
        model.clock.applySchedules()
        self.assertIs(actor, model.game_map.getObjectByName(actor.getName()))
        model.game_map.setNumericProperty("plugin_cityTicks", 825)  # 00:30
        model.clock.applySchedules()
        self.assertIsNone(model.game_map.getObjectByName(actor.getName()))

    def testExcursionRefusalIsPendingAndSuccessfulItemCannotBeGrantedTwice(self):
        model = CityModel()
        actor = model.actor("Quinn", "AR0157")
        dialog = model.dialog(actor)
        self.assertTrue(dialog.acceptQuinnDagger())
        self.assertTrue(dialog.excursionNesterLater())
        self.assertEqual(0, model.game_map.getNumericProperty("plugin_cityTicks"))
        self.assertEqual([], model.player.items)
        self.assertTrue(dialog.excursionNesterRecover())
        self.assertEqual(1200, model.game_map.getNumericProperty("plugin_cityTicks"))
        self.assertEqual(1, len(model.player.items))
        self.assertFalse(dialog.excursionNesterRecover())
        self.assertEqual("active", model.game_map.getStringProperty("plugin_cityQuest_quinnDagger"))

    def testPalaceNeedsSixRealDeathsButOnlyOneSurvivingDukeAndAlternativeEvidence(self):
        model = CityModel()
        model.game_map.setNumericProperty("plugin_cityPhase", 7)
        belt = model.actor("Belt", "AR0108")
        liia = model.actor("Liia Jannath", "AR0108")
        dialog = model.dialog(belt)
        model.item("MISC78")
        self.assertTrue(dialog.acceptDucalPalace())
        model.game_map.setBoolProperty("plugin_cityFlag_assassinsExposed", True)
        model.kill(liia)
        for index in range(5):
            model.kill(model.actor("Noble", "AR0108", sourceCreature="NOBLPA"))
        self.assertFalse(dialog.canQuestDucalPalaceComplete())
        model.kill(model.actor("Noble", "AR0108", sourceCreature="NOBLPA"))
        self.assertTrue(dialog.canQuestDucalPalaceComplete())
        self.assertTrue(dialog.questDucalPalaceComplete())
        self.assertTrue(model.game_map.getBoolProperty("plugin_cityFlag_palaceCleared"))

    def testFiniteStockInsufficientFundsAndSharedStoreOwnership(self):
        model = CityModel()
        actor = model.actor("Merchant", sourceStore="SHOP")
        dialog = model.dialog(actor)
        model.clock.setStringProperty(
            "storeDefinitions",
            json.dumps(
                {
                    "SHOP": {
                        "flags": 1,
                        "stock": [{"item": "RING16", "flags": 1, "price": 101, "stock": 1, "quantity": 1}],
                        "sell_markup": 100,
                        "buy_markup": 50,
                    }
                }
            ),
        )
        self.assertFalse(dialog.buyStock("SHOP", 0))
        self.assertEqual(100, model.player.getGold())
        model.player.addGold(1)
        self.assertTrue(dialog.buyStock("SHOP", 0))
        self.assertEqual(0, model.player.getGold())
        self.assertFalse(dialog.buyStock("SHOP", 0))
        self.assertEqual(1, len(model.player.items))

    def testBogeymanRewardsAreOwnedByTheCorrectSpeakerAndAppliedOnce(self):
        model = CityModel()
        laerta = model.actor("Laerta", "AR0162")
        voltine = model.actor("Voltine", "AR0162")
        model.clock.initializeActor(laerta)
        model.clock.initializeActor(voltine)
        start = model.dialog(laerta)
        self.assertTrue(start.acceptBogeyman())
        model.kill(model.actor("Gervisse", "AR0162", sourceCreature="GERVIS"))
        reply = model.dialog(voltine)
        self.assertTrue(reply.questBogeymanVoltine())
        self.assertEqual(0, model.player.getNumericProperty("exp"))  # Combat XP belongs to the native resolver.
        self.assertEqual(["WAND09"], [item.getStringProperty("plugin_citySourceItem") for item in model.player.items])
        self.assertFalse(reply.questBogeymanVoltine())
        final = model.dialog(laerta)
        self.assertTrue(final.questBogeymanComplete())
        self.assertEqual(1000, model.player.getNumericProperty("exp"))
        self.assertEqual(
            {"WAND09", "SCRL78"}, {item.getStringProperty("plugin_citySourceItem") for item in model.player.items}
        )

    def testScriptSpawnPersistsActualActorAndNeverRecreatesAfterDeath(self):
        model = CityModel()
        model.resources["scriptGuard"] = {
            "class": "CCreature",
            "properties": {"sourceCreature": "NOBLPA", "sourceArea": "AR0108", "label": "Noble"},
        }
        model.game_map.setNumericProperty("plugin_cityPhase", 7)
        model.game_map.setStringProperty("plugin_cityQuest_ducalPalace", "active")
        model.clock.setStringProperty(
            "actorDefinitions",
            json.dumps(
                [
                    {
                        "id": "scriptGuard",
                        "sourceCreature": "NOBLPA",
                        "x": 1,
                        "y": 2,
                        "z": 0,
                        "phase": 7,
                        "requiresQuest": {"ducalPalace": "active"},
                    }
                ]
            ),
        )
        model.clock.spawnActors()
        actor = model.game_map.getObjectByName("scriptGuard")
        self.assertEqual("cityHostile", actor.getStringProperty("affiliation"))
        self.assertFalse(actor.getBoolProperty("npc"))
        model.clock.spawnActors()
        self.assertIs(actor, model.game_map.getObjectByName("scriptGuard"))
        model.kill(actor)
        model.clock.spawnActors()
        self.assertIsNone(model.game_map.getObjectByName("scriptGuard"))
        self.assertIs(actor, model.clock.getObjectProperty("plugin_cityCorpse_scriptGuard"))

    def testTempleRevivesTheSameFallenCompanionWithoutCloningInventory(self):
        model = CityModel(intelligence=12)
        follower = model.actor("Tiax", sourceCreature="TIAX")
        sword = model.item("SW1H01", follower)
        follower.equipItem("rightHand", sword)
        potion = model.item("POTN08", follower)
        model.clock.initializeActor(follower)
        self.assertTrue(model.dialog(follower).recruit())
        # The city's native fixed-loot policy awards all droppable possessions before the death callback.
        follower.equipItem("rightHand", None)
        follower.removeQuestItem(lambda item: item == sword)
        model.player.addItem(sword)
        follower.removeQuestItem(lambda item: item == potion)
        model.player.addItem(potion)
        model.kill(follower)
        priest = model.actor("Priest", sourceStore="TEMPLE")
        model.clock.setStringProperty(
            "storeDefinitions", json.dumps({"TEMPLE": {"flags": 32, "cures": [{"spell": "SPPR504", "price": 100}]}})
        )
        self.assertTrue(model.dialog(priest).buyService("TEMPLE", 0))
        self.assertIs(follower, model.game_map.getObjectByName(follower.getName()))
        self.assertEqual({}, follower.getEquipped())
        self.assertNotIn(sword, follower.items)
        self.assertNotIn(potion, follower.items)
        self.assertEqual([sword, potion], model.player.items)
        self.assertEqual(1, follower.getHp())
        self.assertTrue(follower.getBoolProperty("alwaysSimulate"))
        self.assertEqual(follower.getName(), model.game_map.getStringProperty("plugin_cityCompanionNames"))
        self.assertEqual(0, model.player.getGold())

    def testAloraNeedsNightStagedTalkAndLookoutAgreement(self):
        model = CityModel(intelligence=12)
        alora = model.actor("Alora", "AR0130", sourceCreature="ALORA")
        dialog = model.dialog(alora)
        for _ in range(3):
            dialog.talk()
        self.assertFalse(dialog.recruit())
        model.game_map.setNumericProperty("plugin_cityTicks", 675)  # 21:30
        self.assertFalse(dialog.recruit())
        self.assertTrue(dialog.helpAloraLookout())
        self.assertTrue(dialog.recruit())
        self.assertTrue(alora.getBoolProperty("alwaysSimulate"))

    def testHistorySpawnsAndRecruitsActualEldothAndRemainsWriteOnce(self):
        model = CityModel(intelligence=12)
        start = model.createObject("BaldursGateStart")
        start.setStringProperty("name", "cityStart")
        model.game_map.addObject(start)
        model.resources["eldoth"] = {
            "class": "CCreature",
            "properties": {"sourceCreature": "ELDOTH", "sourceArea": "AR0800", "label": "Eldoth"},
        }
        model.clock.setStringProperty(
            "actorDefinitions",
            json.dumps(
                [
                    {
                        "id": "eldoth",
                        "sourceCreature": "ELDOTH",
                        "x": 0,
                        "y": 0,
                        "z": 0,
                        "phase": 5,
                        "phaseMax": 7,
                        "requiresFlag": "eldothJoined",
                    }
                ]
            ),
        )
        dialog = model.dialog(start)
        self.assertTrue(dialog.historyEldothJoined())
        eldoth = model.game_map.getObjectByName("eldoth")
        self.assertIs(eldoth, model.clock.getObjectProperty("plugin_cityCompanion_eldoth"))
        self.assertFalse(dialog.historyEldothAbsent())
        model.game_map.setNumericProperty("plugin_cityPhase", 7)
        model.clock.applySchedules()
        self.assertIs(eldoth, model.game_map.getObjectByName("eldoth"))

    def testSourceDonationThresholdAndReputationCeiling(self):
        model = CityModel()
        priest = model.actor("Priest", sourceStore="TEMPLE")
        model.clock.setStringProperty(
            "storeDefinitions", json.dumps({"TEMPLE": {"flags": 16, "cures": [{"spell": "SPPR103", "price": 100}]}})
        )
        dialog = model.dialog(priest)
        model.player.addGold(199)
        self.assertFalse(dialog.donate())
        self.assertEqual(299, model.player.getGold())
        model.player.addGold(1)
        self.assertTrue(dialog.donate())
        self.assertEqual(0, model.player.getGold())
        self.assertEqual(11, model.game_map.getNumericProperty("plugin_cityReputation"))
        model.player.addGold(10000)
        model.game_map.setNumericProperty("plugin_cityReputation", 18)
        self.assertFalse(dialog.donate())
        self.assertEqual(10000, model.player.getGold())

    def testSaleAndBuybackTransferSameInstanceAtAuditedStoreMarkups(self):
        model = CityModel()
        merchant = model.actor("Merchant", sourceStore="SHOP")
        model.clock.setStringProperty(
            "storeDefinitions",
            json.dumps({"SHOP": {"flags": 3, "purchased_types": [10], "buy_markup": 50, "sell_markup": 100}}),
        )
        item = model.item("RING16", plugin_cityTradeable=True, plugin_cityValue=100, plugin_cityItemType=10)
        model.choice = item.getName()
        dialog = model.dialog(merchant)
        self.assertTrue(dialog.sell())
        self.assertNotIn(item, model.player.items)
        self.assertIn(item, merchant.items)
        self.assertEqual(150, model.player.getGold())
        self.assertTrue(dialog.buyBack())
        self.assertIn(item, model.player.items)
        self.assertNotIn(item, merchant.items)
        self.assertEqual(50, model.player.getGold())

    def testFinaleRequiresSarevokDeathAndDoesNotDuplicateActiveJournal(self):
        model = CityModel()
        model.game_map.setBoolProperty("plugin_cityFlag_palaceCleared", True)
        model.player.addQuest("citySarevokFinaleQuest")
        actor = model.actor("Sarevok", "AR0125")
        model.kill(actor)
        self.assertTrue(model.game_map.getBoolProperty("plugin_cityFlag_cityCompleted"))
        self.assertEqual(1, len(model.player.getCompletedQuests()))
        self.assertEqual(0, model.player.getNumericProperty("exp"))
        self.assertEqual([], model.player.getQuests())

    def testPalacePortalRequiresSwitchesThenLockAndLaterInvitation(self):
        model = CityModel(agility=12)
        portal = model.createObject("BaldursGatePortal")
        portal.setStringProperty("name", "palace")
        portal.setStringProperty("destinationArea", "AR0108")
        portal.setNumericProperty("targetX", 10)
        portal.setBoolProperty("locked", True)
        model.game_map.addObject(portal)
        self.assertFalse(portal.usable())
        for index in (1, 2):
            switch = model.createObject("BaldursGateContainer")
            switch.setStringProperty("name", "switch" + str(index))
            switch.setNumericProperty("palaceSwitch", index)
            model.game_map.addObject(switch)
            self.assertTrue(model.dialog(switch).pressPalaceSwitch(index))
        self.assertFalse(portal.usable())
        self.assertTrue(model.dialog(portal).unlock())
        self.assertTrue(portal.usable())
        model.game_map.setNumericProperty("plugin_cityPhase", 7)
        self.assertFalse(portal.usable())
        model.item("MISC78")
        self.assertTrue(portal.usable())

    def testStatueNeedsActualScrollThenVailAwardsHisClueOnlyOnce(self):
        model = CityModel()
        vail = model.actor("Statue", "AR0719", sourceCreature="VAIL")
        model.clock.initializeActor(vail)
        dialog = model.dialog(vail)
        self.assertFalse(dialog.acceptVailClue())
        dialog.talk()
        self.assertEqual("", model.game_map.getStringProperty("plugin_cityTalked"))
        self.assertFalse(dialog.restoreStatue())
        scroll = model.item("SCRLPET")
        self.assertTrue(dialog.restoreStatue())
        self.assertNotIn(scroll, model.player.items)
        self.assertFalse(dialog.restoreStatue())
        self.assertTrue(dialog.acceptVailClue())
        self.assertTrue(dialog.questVailClueHear())
        self.assertEqual(500, model.player.getNumericProperty("exp"))
        self.assertEqual(["SCRLVAIL"], [item.getStringProperty("plugin_citySourceItem") for item in model.player.items])
        self.assertFalse(dialog.questVailClueHear())

    def testAbelaRemainsAUsableSpeakerAfterRagefastDiesAndDepartsOnce(self):
        model = CityModel()
        ragefast = model.actor("Ragefast", "AR0126", sourceCreature="RAGEFA")
        abela = model.actor("Abela the Nymph", "AR0126", sourceCreature="ABELA")
        model.clock.initializeActor(abela)
        model.kill(ragefast)
        dialog = model.dialog(abela)
        self.assertTrue(dialog.acceptRagefastNymph())
        self.assertTrue(dialog.questRagefastNymphComplete())
        self.assertEqual(2000, model.player.getNumericProperty("exp"))
        self.assertEqual(["MISC51"], [item.getStringProperty("plugin_citySourceItem") for item in model.player.items])
        self.assertIsNone(model.game_map.getObjectByName(abela.getName()))
        model.clock.applySchedules()
        self.assertIsNone(model.game_map.getObjectByName(abela.getName()))
        self.assertFalse(model.game_map.getBoolProperty("plugin_cityDeath_" + abela.getName()))

    def testJalanthaAudienceCostsOnceAndSpawnsOneActualPriestess(self):
        model = CityModel()
        attendant = model.actor("Priestess of Umberlee", "AR0609", sourceCreature="PUMBERL")
        model.resources["jalantha"] = {
            "class": "CCreature",
            "properties": {"label": "Jalantha Mistmyr", "sourceCreature": "JALANT", "sourceArea": "AR0609"},
        }
        model.clock.setStringProperty(
            "actorDefinitions",
            json.dumps(
                [
                    {
                        "id": "jalantha",
                        "sourceCreature": "JALANT",
                        "x": 0,
                        "y": 0,
                        "z": 0,
                        "phase": 5,
                        "phaseMax": 7,
                        "requiresFlag": "jalanthaSummoned",
                    }
                ]
            ),
        )
        dialog = model.dialog(attendant)
        model.player.addGold(-51)
        self.assertFalse(dialog.requestJalanthaAudience())
        self.assertEqual(49, model.player.getGold())
        self.assertIsNone(model.game_map.getObjectByName("jalantha"))
        model.player.addGold(1)
        self.assertTrue(dialog.requestJalanthaAudience())
        actual = model.game_map.getObjectByName("jalantha")
        self.assertEqual("JALANT", actual.getStringProperty("sourceCreature"))
        self.assertEqual(0, model.player.getGold())
        self.assertTrue(dialog.requestJalanthaAudience())
        self.assertIs(actual, model.game_map.getObjectByName("jalantha"))

    def testLateGateCompanionSpawnHonorsPhaseRange(self):
        model = CityModel()
        model.game_map.setNumericProperty("plugin_cityPhase", 7)
        model.resources["quayle"] = {
            "class": "CCreature",
            "properties": {"label": "Quayle", "sourceCreature": "QUAYLE", "sourceArea": "AR0800"},
        }
        model.clock.setStringProperty(
            "actorDefinitions",
            json.dumps(
                [
                    {
                        "id": "quayle",
                        "sourceCreature": "QUAYLE",
                        "x": 0,
                        "y": 0,
                        "z": 0,
                        "phase": 5,
                        "phaseMax": 7,
                        "requiresFlag": "quayleAtGate",
                    }
                ]
            ),
        )
        model.game_map.setBoolProperty("plugin_cityFlag_quayleAtGate", True)
        model.clock.spawnActors()
        self.assertIsNotNone(model.game_map.getObjectByName("quayle"))

    def testNarlenGuildTalkCannotFalselyCompleteTheOutdoorLookout(self):
        model = CityModel(agility=12)
        narlen = model.actor("Narlen Darkwalk", "AR0153", sourceCreature="NARLEN")
        dialog = model.dialog(narlen)
        self.assertTrue(dialog.acceptNarlenLookout())
        model.game_map.setNumericProperty("plugin_cityTicks", 700)
        self.assertFalse(dialog.warnNarlen())
        self.assertFalse(dialog.canQuestNarlenLookoutComplete())
        self.assertFalse(model.game_map.getBoolProperty("plugin_cityFlag_narlenWarning"))

    def testCanonicalNarlenMovesByNightAndReturnsWithSameBelongings(self):
        model = CityModel(agility=12)
        narlen = model.canonical("NARLEN")
        ring = model.item("RING16", narlen)
        dialog = model.dialog(narlen)
        self.assertTrue(dialog.acceptNarlenLookout())
        self.assertIsNone(model.game_map.getObjectByName(narlen.getName()))
        self.assertFalse(model.game_map.getBoolProperty("plugin_cityDeath_" + narlen.getName()))
        model.clock.advanceTicks(700)
        self.assertIs(narlen, model.game_map.getObjectByName(narlen.getName()))
        self.assertEqual("AR0300", narlen.getStringProperty("sourceArea"))
        self.assertIn(ring, narlen.items)
        officer_name = model.installLookoutOfficer()
        self.assertTrue(model.dialog(narlen).beginNarlenLookout())
        model.clock.advanceTicks(19)
        self.assertIsNone(model.game_map.getObjectByName(officer_name))
        self.assertFalse(model.dialog(narlen).warnNarlen())
        model.clock.advanceTicks(1)
        self.assertIsNotNone(model.game_map.getObjectByName(officer_name))
        self.assertTrue(model.dialog(narlen).warnNarlen())
        self.assertEqual("AR0153", narlen.getStringProperty("sourceArea"))
        self.assertIs(narlen, model.clock.getObjectProperty("plugin_cityRelocationActor_narlen"))
        dialog = model.dialog(narlen)
        self.assertTrue(dialog.questNarlenLookoutComplete())
        self.assertTrue(dialog.acceptNarlenRogueStone())
        self.assertEqual("AR1300", narlen.getStringProperty("sourceArea"))
        stone = model.item("MISC45")
        model.clock.applySchedules()
        self.assertEqual("AR0153", narlen.getStringProperty("sourceArea"))
        self.assertTrue(model.dialog(narlen).questNarlenRogueStoneComplete())
        self.assertIn(stone, narlen.items)
        for _ in range(3):
            model.clock.applySchedules()
        self.assertIn(ring, narlen.items)
        pearls = [item for item in model.player.items if item.getStringProperty("plugin_citySourceItem") == "MISC36"]
        self.assertEqual(1, len(pearls))
        self.assertEqual(3, pearls[0].getNumericProperty("plugin_cityQuantity"))
        self.assertEqual(200, model.player.getGold())

    def testRelocationRestoreUsesSerializedReferenceWithoutResettingInventory(self):
        model = CityModel(agility=12)
        narlen = model.canonical("NARLEN")
        item = model.item("RING16", narlen)
        narlen.addGold(77)
        model.dialog(narlen).acceptNarlenLookout()
        before = model.clock
        replacement = model.createObject("BaldursGateClock")
        replacement.setStringProperty("name", "cityClock")
        replacement.properties = dict(before.properties)  # Saved object properties retain canonical actor references.
        for key in ("plugin_cityRelocationState", "plugin_cityParkedActors", "relocationDefinitions"):
            replacement.setStringProperty(key, json.dumps(decodeCityData(before.getStringProperty(key))))
        model.game_map.removeObject(before)
        model.game_map.addObject(replacement)
        model.clock = replacement
        replacement.advanceTicks(700)
        self.assertIs(narlen, model.game_map.getObjectByName(narlen.getName()))
        self.assertIn(item, narlen.items)
        self.assertEqual(177, narlen.getGold())
        narlen.moveTo(20, 30, 0)
        replacement.applySchedules()
        self.assertEqual((20, 30), (narlen.getCoords().x, narlen.getCoords().y))
        model.kill(narlen)
        replacement.applySchedules()
        replacement.advanceTicks(1200)
        self.assertIsNone(model.game_map.getObjectByName(narlen.getName()))
        self.assertTrue(decodeCityData(replacement.getStringProperty("plugin_cityRelocationState"))["narlen"]["dead"])

    def testRelocationSuppressesNewSceneCopiesAndParksOldCopiesWithoutDeathCredit(self):
        model = CityModel()
        model.game_map.setNumericProperty("plugin_cityPhase", 7)
        model.installRelocations()
        names = ("cityAr0800ScriptActorTamoko", "formerTamokoUndercity")
        for name in names:
            model.resources[name] = {
                "class": "CCreature",
                "properties": {"label": "Tamoko", "sourceCreature": "TAMOKO", "sourceArea": "AR0800"},
            }
        model.clock.setStringProperty(
            "actorDefinitions",
            json.dumps(
                [{"id": name, "sourceCreature": "TAMOKO", "phase": 7, "x": 1, "y": 1, "z": 0} for name in names]
            ),
        )
        model.clock.spawnActors()
        self.assertIsNone(model.game_map.getObjectByName(names[1]))
        canonical = model.game_map.getObjectByName(names[0])
        old = model.createObject(names[1])
        model.clock.initializeActor(old)
        duplicate_item = model.item("RING16", old)
        model.game_map.addObject(old)
        model.clock.applySchedules()
        self.assertIs(canonical, model.game_map.getObjectByName(names[0]))
        self.assertIsNone(model.game_map.getObjectByName(names[1]))
        self.assertIn(duplicate_item, old.items)
        self.assertNotIn(duplicate_item, canonical.items)
        self.assertEqual([], model.player.items)
        self.assertEqual(0, model.player.getNumericProperty("exp"))
        self.assertFalse(model.game_map.getBoolProperty("plugin_cityDeath_" + old.getName()))

    def testCanonicalRelocationDoesNotPullARecruitedFollowerBackToAScene(self):
        model = CityModel(intelligence=12)
        actor = model.canonical("NARLEN")
        actor.setBoolProperty("plugin_cityRecruitable", True)
        self.assertTrue(model.dialog(actor).recruit())
        actor.moveTo(40, 45, 2)
        model.game_map.setStringProperty("plugin_cityQuest_narlenLookout", "active")
        model.clock.applySchedules()
        self.assertIs(actor, model.game_map.getObjectByName(actor.getName()))
        self.assertEqual((40, 45, 2), tuple(vars(actor.getCoords()).values()))
        self.assertTrue(actor.getBoolProperty("alwaysSimulate"))
        self.assertEqual("player", actor.properties["controller"].getStringProperty("target"))

    def testTamokoConversationsPreserveOneActorAndAllowEitherEltanOrder(self):
        for rescued in (False, True):
            with self.subTest(rescued=rescued):
                model = CityModel(intelligence=12)
                model.game_map.setNumericProperty("plugin_cityPhase", 7)
                tamoko = model.canonical("TAMOKO")
                item = model.item("RING16", tamoko)
                self.assertTrue(model.dialog(tamoko).hearTamokoWarning())
                self.assertEqual("AR1100", tamoko.getStringProperty("sourceArea"))
                model.game_map.setBoolProperty("plugin_cityFlag_eltanSafe", rescued)
                self.assertTrue(model.dialog(tamoko).discussTamokoRequest())
                self.assertEqual(
                    "rescued" if rescued else "notRescued",
                    model.game_map.getStringProperty("plugin_cityTamokoEltanDiscussion"),
                )
                self.assertTrue(model.dialog(tamoko).acceptTamokoRequest())
                self.assertEqual("active", model.game_map.getStringProperty("plugin_cityQuest_cythandriaDiary"))
                self.assertIsNone(model.game_map.getObjectByName(tamoko.getName()))
                model.game_map.setBoolProperty("plugin_cityFlag_palaceCleared", True)
                model.clock.applySchedules()
                self.assertIs(tamoko, model.game_map.getObjectByName(tamoko.getName()))
                self.assertEqual("AR0123", tamoko.getStringProperty("sourceArea"))
                self.assertIn(item, tamoko.items)
                final = model.dialog(tamoko)
                self.assertTrue(final.acceptTamokoMercy())
                self.assertTrue(final.questTamokoMercyComplete())
                self.assertIsNone(model.game_map.getObjectByName(tamoko.getName()))
                self.assertFalse(model.game_map.getBoolProperty("plugin_cityDeath_" + tamoko.getName()))

    def testStartingProfileAndHistoryFreezeAreNotOverwrittenByReentry(self):
        model = CityModel(strength=14, agility=16, intelligence=12)
        start = model.createObject("BaldursGateStart")
        start.setStringProperty("name", "cityStart")
        model.game_map.addObject(start)
        item = model.item("RING16", plugin_cityQuantity=2, plugin_cityCharges="[1,2,3]")
        start.onEnter(SimpleNamespace(getCause=lambda: model.player))
        profile = decodeCityData(model.game_map.getStringProperty("plugin_cityStartingProfile"))
        self.assertEqual((1100, 10000), (profile["gold"], profile["experience"]))
        self.assertEqual("Warrior", profile["classId"])
        self.assertEqual(16, profile["stats"]["agility"])
        self.assertEqual(item.getName(), profile["items"][0]["name"])
        dialog = model.dialog(start)
        self.assertTrue(dialog.historyAldethHelped())
        self.assertTrue(dialog.finishHistoryChoices())
        frozen = model.game_map.getStringProperty("plugin_cityStartingProfile")
        self.assertEqual(
            {"aldeth": "helped", "tenya": "unspecified", "eldoth": "unspecified"}, decodeCityData(frozen)["history"]
        )
        model.player.addGold(25)
        start.onEnter(SimpleNamespace(getCause=lambda: model.player))
        self.assertEqual(1125, model.player.getGold())
        self.assertEqual(10000, model.player.getNumericProperty("exp"))
        self.assertEqual(frozen, model.game_map.getStringProperty("plugin_cityStartingProfile"))
        self.assertFalse(dialog.historyTenyaHelped())

    def testPolygonRegionVisitsOnlyCountActualEntryAndKeepPendingEffectsUntouched(self):
        model = CityModel()
        region = model.createObject("BaldursGateRegion")
        region.setStringProperty("name", "region")
        region.setStringProperty("sourceRegion", "AR0100#region1")
        region.setBoolProperty("regionEnabled", True)
        region.setBoolProperty("trapped", True)
        model.game_map.addObject(region)
        model.clock.setStringProperty(
            "regionDefinitions", json.dumps({"regions": [{"object": "region", "cells": [[2, 2, 0], [3, 2, 0]]}]})
        )
        model.player.moveTo(2, 2, 0)
        model.clock.observeRegions()
        model.player.moveTo(3, 2, 0)
        model.clock.observeRegions()
        self.assertEqual(
            {"AR0100#region1": 1}, decodeCityData(model.game_map.getStringProperty("plugin_cityRegionVisits"))
        )
        self.assertTrue(region.getBoolProperty("trapped"))
        self.assertEqual(100, model.player.getHp())
        self.assertEqual(0, model.player.getNumericProperty("exp"))
        self.assertEqual(1, model.clock.getNumericProperty("plugin_cityRegionIndexBuilds"))
        model.player.moveTo(4, 2, 0)
        model.clock.observeRegions()
        model.player.moveTo(2, 2, 0)
        region.onEnter(SimpleNamespace(getCause=lambda: model.player))
        self.assertEqual(
            {"AR0100#region1": 2}, decodeCityData(model.game_map.getStringProperty("plugin_cityRegionVisits"))
        )

    def testPortalDestroyUnregistersOnlyItsOwnedNavigationEdge(self):
        model = CityModel()
        first, second = (model.createObject("BaldursGatePortal") for _ in range(2))
        for portal, name, x in ((first, "first", 10), (second, "second", 20)):
            portal.setStringProperty("name", name)
            portal.setStringProperty("destinationArea", "AR0101")
            portal.setNumericProperty("targetX", x)
            model.game_map.addObject(portal)
            portal.publishEdge()
        self.assertEqual(2, len(model.game_map.navigation_edges))
        first.onDestroy(None)
        self.assertEqual({"second"}, {row[2] for row in model.game_map.navigation_edges})

    def testCorpsePhaseParkingNeverCallsCreatureMethodsAndBlocksLateInteraction(self):
        model = CityModel()
        corpse = model.createObject("BaldursGateContainer")
        corpse.setStringProperty("name", "emissary")
        corpse.setBoolProperty("sourceCorpse", True)
        corpse.setNumericProperty("phaseMax", 5)
        corpse.isAlive = Mock(side_effect=AssertionError("Source corpse is a building, not a creature"))
        model.game_map.addObject(corpse)
        dialog = model.dialog(corpse)
        self.assertTrue(dialog.canInteract())
        model.game_map.setNumericProperty("plugin_cityPhase", 7)
        self.assertFalse(dialog.canInteract())
        model.clock.applySchedules()
        self.assertIsNone(model.game_map.getObjectByName("emissary"))
        self.assertFalse(model.game_map.getBoolProperty("plugin_cityDeath_emissary"))
        model.game_map.setNumericProperty("plugin_cityPhase", 5)
        model.clock.applySchedules()
        self.assertIs(corpse, model.game_map.getObjectByName("emissary"))
        corpse.isAlive.assert_not_called()

    def testNativePalaceKeyDoesNotOverwriteOrConsumeRawSourceKey(self):
        model = CityModel()
        door = model.createObject("BaldursGateContainer")
        door.setStringProperty("name", "palaceDoor")
        door.setBoolProperty("locked", True)
        door.setStringProperty("sourceKey", "")
        door.setStringProperty("lockKey", "MISC78")
        model.game_map.addObject(door)
        invitation = model.item("MISC78")
        self.assertTrue(model.dialog(door).useKey())
        self.assertFalse(door.getBoolProperty("locked"))
        self.assertEqual("", door.getStringProperty("sourceKey"))
        self.assertIn(invitation, model.player.items)

    def testFinaleCompletionIsAutomaticAndHasNoUnreachableDialogTurnIn(self):
        rows = questDialogRows(DOCUMENT, {"label": "cityStart"}, "cityStart")
        self.assertNotIn("questSarevokFinaleComplete", {row["action"] for row in rows})

    def testRelocationCompilerRejectsAmbiguousSourceArea(self):
        source = json.loads(json.dumps(RELOCATION_SOURCE))
        source["scriptedActors"][0]["areas"].append("AR9999")
        with self.assertRaisesRegex(ValueError, "one source area"):
            buildRelocations(source, usablePosition=lambda _area, point: (*point, 0))

    def testRelocationReusesCanonicalReferencesWithoutRepeatingFullMapCopySearch(self):
        model = CityModel()
        actor = model.canonical("NARLEN")
        original = model.game_map.getObjects
        model.game_map.getObjects = Mock(wraps=original)
        for _ in range(20):
            model.clock.relocateActors()
        model.game_map.getObjects.assert_not_called()
        self.assertIs(actor, model.clock.getObjectProperty("plugin_cityRelocationActor_narlen"))

    def testNarlenOfficerBranchRejectsUnrelatedGuardKillsAndUsesActualWatchman(self):
        model = CityModel(agility=12)
        narlen = model.canonical("NARLEN")
        self.assertTrue(model.dialog(narlen).acceptNarlenLookout())
        model.game_map.setNumericProperty("plugin_cityGuardKills", 10)
        model.clock.applySchedules()
        self.assertIsNone(model.game_map.getObjectByName(narlen.getName()))
        officer = model.actor("Watchman", "AR0300", sourceCreature="WATCHM", sourceSpawnFact="AR0300.BCS#spawn7")
        model.kill(officer)
        model.clock.applySchedules()
        dialog = model.dialog(narlen)
        self.assertTrue(dialog.canQuestNarlenLookoutOfficerKilled())
        self.assertTrue(dialog.questNarlenLookoutOfficerKilled())
        self.assertEqual(400, model.player.getGold())
        self.assertEqual(0, model.player.getNumericProperty("exp"))
        self.assertIsNone(model.game_map.getObjectByName(narlen.getName()))
        self.assertFalse(model.game_map.getBoolProperty("plugin_cityDeath_" + narlen.getName()))

    def testAuditedStorePriceUsesStackQuantityAndNeverWandChargeCount(self):
        source = RELOCATION_SOURCE
        prepared = prepareStores({"STOBLACK": source["stores"]["STOBLACK"]}, source["items"])
        dart = next(row for row in prepared["STOBLACK"]["stock"] if row["item"] == "DART02")
        self.assertEqual((5, 80), (dart["quantity"], dart["price"]))
        prepared = prepareStores(
            {
                "SHOP": {
                    "sell_markup": 200,
                    "stock": [{"item": "BOLT01", "charges": [20, 0, 0]}, {"item": "WAND09", "charges": [5, 4, 3]}],
                }
            },
            source["items"],
        )
        bolts, wand = prepared["SHOP"]["stock"]
        self.assertEqual((20, 1), (bolts["quantity"], bolts["price"]))
        self.assertEqual((1, 30000), (wand["quantity"], wand["price"]))
        self.assertEqual([5, 4, 3], wand["charges"])

    def testStackSaleAndBuybackPayForSameActualFiveDarts(self):
        model = CityModel()
        merchant = model.actor("Black Lily", sourceStore="STOBLACK")
        model.clock.setStringProperty(
            "storeDefinitions", json.dumps({"STOBLACK": RELOCATION_SOURCE["stores"]["STOBLACK"]})
        )
        darts = model.item(
            "DART02",
            plugin_cityTradeable=True,
            plugin_cityValue=8,
            plugin_cityItemType=24,
            plugin_cityStackSize=80,
            plugin_cityQuantity=5,
        )
        model.choice = darts.getName()
        dialog = model.dialog(merchant)
        self.assertTrue(dialog.sell())
        self.assertEqual(120, model.player.getGold())
        self.assertIn(darts, merchant.items)
        self.assertTrue(dialog.buyBack())
        self.assertEqual(40, model.player.getGold())
        self.assertEqual([darts], model.player.items)
        self.assertEqual(5, darts.getNumericProperty("plugin_cityQuantity"))

    def testStorePurchaseCapabilitiesTypesAndFencingRejectWithoutMutation(self):
        model = CityModel()
        merchant = model.actor("Alyth", sourceStore="TAV0705")
        dialog = model.dialog(merchant)
        sword = model.item("SW1H01", plugin_cityTradeable=True, plugin_cityValue=50, plugin_cityItemType=20)
        model.choice = sword.getName()
        source = RELOCATION_SOURCE["stores"]["TAV0705"]
        self.assertEqual((64, []), (source["flags"], source["purchased_types"]))
        for store in (source, {"flags": 2, "purchased_types": []}, {"flags": 2, "purchased_types": [10]}):
            model.clock.setStringProperty("storeDefinitions", json.dumps({"TAV0705": store}))
            self.assertFalse(dialog.sell())
            self.assertEqual(100, model.player.getGold())
            self.assertIn(sword, model.player.items)
            self.assertEqual([], merchant.items)
        sword.setBoolProperty("plugin_cityStolen", True)
        model.clock.setStringProperty(
            "storeDefinitions", json.dumps({"TAV0705": {"flags": 2, "purchased_types": [20]}})
        )
        self.assertFalse(dialog.sell())
        self.assertIn(sword, model.player.items)
        self.assertEqual(100, model.player.getGold())

    def testDeniedStoreCapabilitiesDoNotHealIdentifyTradeOrDonate(self):
        model = CityModel()
        merchant = model.actor("Merchant", sourceStore="SHOP")
        model.clock.setStringProperty(
            "storeDefinitions",
            json.dumps(
                {
                    "SHOP": {
                        "flags": 0,
                        "stock": [{"item": "RING16", "price": 1, "stock": 1}],
                        "drinks": [{"price": 1}],
                        "cures": [{"spell": "SPPR103", "price": 1}],
                        "identify_price": 1,
                        "room_flags": 0,
                    }
                }
            ),
        )
        item = model.item("RING16", plugin_cityUnidentified=True)
        model.player.setHp(50)
        dialog = model.dialog(merchant)
        for call in (
            lambda: dialog.buyStock("SHOP", 0),
            lambda: dialog.buyDrink("SHOP", 0),
            lambda: dialog.buyService("SHOP", 0),
            lambda: dialog.identify("SHOP"),
            dialog.donate,
            lambda: dialog.rest("SHOP", 0),
            dialog.buyBack,
        ):
            self.assertFalse(call())
        self.assertEqual((100, 50), (model.player.getGold(), model.player.getHp()))
        self.assertTrue(item.getBoolProperty("plugin_cityUnidentified"))
        self.assertEqual(
            [],
            storeDialogRows(
                "SHOP",
                {
                    "flags": 0,
                    "stock": [{"item": "RING16"}],
                    "cures": [{"spell": "SPPR103", "price": 1}],
                    "identify_price": 1,
                },
            ),
        )

    def testLeavingStartOrFirstTransactionFreezesNeutralUnchosenHistory(self):
        for action in ("move", "quest", "trade", "theft", "recruit"):
            with self.subTest(action=action):
                model = CityModel(agility=16, intelligence=12)
                start = model.createObject("BaldursGateStart")
                start.setStringProperty("name", "cityStart")
                model.game_map.addObject(start)
                start.onEnter(SimpleNamespace(getCause=lambda: model.player))
                if action == "move":
                    model.player.moveTo(3, 0, 0)
                    model.clock.onTurn(None)
                elif action == "quest":
                    model.dialog(model.actor("Quinn", "AR0157")).acceptQuinnDagger()
                elif action == "trade":
                    merchant = model.actor("Merchant", sourceStore="SHOP")
                    model.clock.setStringProperty(
                        "storeDefinitions",
                        json.dumps({"SHOP": {"flags": 1, "stock": [{"item": "RING16", "price": 1, "stock": 1}]}}),
                    )
                    self.assertTrue(model.dialog(merchant).buyStock("SHOP", 0))
                elif action == "theft":
                    owner = model.actor("Resident")
                    item = model.item("RING16", owner)
                    model.choice = item.getName()
                    self.assertTrue(model.dialog(owner).pickPocket())
                else:
                    self.assertTrue(model.dialog(model.actor("Tiax", sourceCreature="TIAX")).recruit())
                self.assertTrue(model.game_map.getBoolProperty("plugin_cityHistoryFrozen"))
                model.player.moveTo(0, 0, 0)
                self.assertFalse(model.dialog(start).historyAldethHelped())
                self.assertEqual(
                    {"aldeth": "unspecified", "tenya": "unspecified", "eldoth": "unspecified"},
                    decodeCityData(model.game_map.getStringProperty("plugin_cityHistory")),
                )

    def testSourceCannotCloseDoorKeepsOpenStateAndNavigationEdge(self):
        model = CityModel()
        portal = model.createObject("BaldursGatePortal")
        portal.setStringProperty("name", "door")
        portal.setStringProperty("destinationArea", "AR0101")
        portal.setNumericProperty("targetX", 10)
        portal.setBoolProperty("open", True)
        portal.setBoolProperty("forbidClosing", True)
        model.game_map.addObject(portal)
        portal.publishEdge()
        before = set(model.game_map.navigation_edges)
        self.assertFalse(model.dialog(portal).close())
        self.assertTrue(portal.getBoolProperty("open"))
        self.assertEqual(before, model.game_map.navigation_edges)

    def testAuditedContainerGemAndPotionStacksRetainEveryUnit(self):
        expected = {
            "AR0111#container1": ("MISC42", 4),
            "AR0136#container2": ("MISC20", 6),
            "AR0308#container1": ("POTN25", 2),
            "AR0700#container10": ("MISC17", 2),
        }
        for source in RELOCATION_SOURCE["stackContainers"]:
            with self.subTest(container=source["sourceId"]):
                model = CityModel()
                code, count = expected[source["sourceId"]]
                row = next(item for item in source["items"] if item["item"] == code)
                self.assertEqual(count, row["charges"][0])
                container = model.createObject("BaldursGateContainer")
                container.setStringProperty("name", "stackContainer")
                container.setStringProperty("contents", json.dumps([row]))
                model.game_map.addObject(container)
                dialog = model.dialog(container)
                self.assertTrue(dialog.openContainer())
                item = model.player.items[0]
                self.assertGreater(item.getNumericProperty("plugin_cityStackSize"), 1)
                self.assertEqual(count, item.getNumericProperty("plugin_cityQuantity"))
                self.assertEqual(row["charges"], decodeCityData(item.getStringProperty("plugin_cityCharges")))
                self.assertFalse(dialog.openContainer())
                self.assertEqual([item], model.player.items)

    def testAuditedNpcPotionStackPreservesQuantityWithoutMultiplyingWandCharges(self):
        model = CityModel()
        potion = RELOCATION_SOURCE["stackNpcPotion"]
        self.assertEqual(2, potion["charges"][0])
        actor = model.actor(
            "Archer",
            sourceInventory=json.dumps(
                [
                    potion,
                    {"item": "WAND09", "charges": [5, 0, 0]},
                    {"item": "POTN25", "charges": [9, 0, 0], "quantity": 3},
                ]
            ),
        )
        model.clock.initializeActor(actor)
        quantities = {
            item.getStringProperty("plugin_citySourceItem"): item.getNumericProperty("plugin_cityQuantity")
            for item in actor.items
        }
        self.assertEqual({"POTN08": 2, "WAND09": 1, "POTN25": 3}, quantities)
        model.clock.initializeActor(actor)
        self.assertEqual(3, len(actor.items))


if __name__ == "__main__":
    unittest.main()
