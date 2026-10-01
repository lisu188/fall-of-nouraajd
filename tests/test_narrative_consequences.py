"""Campaign consequences using source scripts and transactional journey doubles."""

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "res") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "res"))

import campaign
import narrative


class PropertyObject:
    def __init__(self, game=None):
        self.game = game
        self.properties = {}
        self.coords = types.SimpleNamespace(x=4, y=5, z=0)

    def getGame(self):
        return self.game

    def getMap(self):
        return self.game.getMap()

    def getStringProperty(self, name):
        return self.properties.get(name, "")

    def setStringProperty(self, name, value):
        self.properties[name] = value

    def getBoolProperty(self, name):
        return self.properties.get(name, False)

    def setBoolProperty(self, name, value):
        self.properties[name] = value

    def getCoords(self):
        return self.coords


class Player(PropertyObject):
    def __init__(self, game=None, class_id="Warrior"):
        super().__init__(game)
        self.class_id = class_id
        self.gold = 0
        self.items = []

    def getPlayerClassId(self):
        return self.class_id

    def getGold(self):
        return self.gold

    def addGold(self, amount):
        if self.game.map.map_name == "ritual":
            assert self.game.map.getBoolProperty("reward_claimed"), "claim must precede the ritual payout"
        self.gold += amount

    def addItem(self, item):
        self.items.append(item)

    def getItems(self):
        return set(self.items)

    def hasItem(self, predicate):
        return any(predicate(item) for item in self.items)

    def removeQuestItem(self, predicate):
        self.items.remove(next(item for item in self.items if predicate(item)))

    def checkQuests(self):
        self.game.events.append("checkQuests")


class Map(PropertyObject):
    def __init__(self, game, player):
        super().__init__(game)
        self.player = player
        self.map_name = "ritual"
        self.objects = {"ritualCaptive": PropertyObject(game)}

    def getPlayer(self):
        return self.player

    def getMapName(self):
        return self.map_name

    def getObjectByName(self, name):
        return self.objects.get(name)

    def getObjectsAtCoords(self, coords):
        return []


class Game:
    def __init__(self, class_id="Warrior"):
        self.events = []
        self.player = Player(self, class_id)
        self.map = Map(self, self.player)
        self.pending = None
        self.messages = []

    def getMap(self):
        return self.map

    def getGuiHandler(self):
        return types.SimpleNamespace(showMessage=self.messages.append, notify=self.messages.append)

    def changeMapWithPreparation(self, map_name, before_entry, completion):
        self.events.append("transition")
        self.pending = (map_name, before_entry, completion)
        return True

    def finishTransition(self, success):
        map_name, before_entry, completion = self.pending
        self.pending = None
        if success:
            before_entry()
            self.map.map_name = map_name
        completion(success)


def loadMapClasses(map_name):
    registered = {}

    def register(context):
        def decorate(cls):
            registered[cls.__name__] = cls
            return cls

        return decorate

    fake_module = types.ModuleType("game")
    fake_module.campaign = campaign
    fake_module.narrative = narrative
    fake_module.register = register
    fake_module.trigger = lambda *args: register(None)
    fake_module.showReader = lambda *args: None
    fake_module.rewardSnapshot = lambda player: player.gold
    fake_module.showRewardReceipt = lambda *args: None
    fake_module.requirementMessage = lambda *args: None
    fake_module.logger = lambda *args: None
    fake_module.randint = lambda low, high: low
    fake_module.CTag = types.SimpleNamespace(WAND="wand")
    fake_module.claim_once = lambda obj, flag: (
        False if obj.getBoolProperty(flag) else obj.setBoolProperty(flag, True) or True
    )
    for name in ("CDialog", "CEvent", "CQuest", "CTrigger", "CCreature"):
        setattr(fake_module, name, type(name, (PropertyObject,), {}))
    script_path = REPO_ROOT / "res/maps" / map_name / "script.py"
    spec = importlib.util.spec_from_file_location(map_name + "NarrativeFixture", script_path)
    script = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"game": fake_module}):
        spec.loader.exec_module(script)
        script.load(None, None)
    return registered


class NarrativeConsequenceTest(unittest.TestCase):
    def testLegacyAndStandaloneDefaultsPreservePricesAndBounty(self):
        game = Game()
        self.assertEqual(100, narrative.beerSalePercent(game))
        self.assertEqual(500, narrative.siegeRewardGold(game))
        self.assertEqual("", narrative.siegeSummary(game))
        narrative.snapshotTown(game, "not_started")
        self.assertEqual("notAttempted", narrative.getVariable(game, "nouraajdVictorOutcome"))

    def testFirstGateAndVictorChoicesPersistAcrossReloadAndCannotBeRewritten(self):
        game = Game()
        narrative.recordGateApproach(game, "threatened")
        narrative.recordGateApproach(game, "cooperative")
        narrative.recordVictorConfrontation(game, "forceful")
        narrative.recordVictorConfrontation(game, "deescalated")
        reloaded = Game()
        reloaded.player.properties = json.loads(json.dumps(game.player.properties))
        self.assertEqual(105, narrative.beerSalePercent(reloaded))
        self.assertEqual(475, narrative.siegeRewardGold(reloaded))
        self.assertIn("blow", narrative.victorResponse(reloaded))
        self.assertIn("25 gold", narrative.townRecap(reloaded))

    def testCooperativeAndDeescalatedChoicesKeepBaselineEconomy(self):
        game = Game()
        narrative.recordGateApproach(game, "cooperative")
        narrative.recordVictorConfrontation(game, "deescalated")
        self.assertEqual(100, narrative.beerSalePercent(game))
        self.assertEqual(500, narrative.siegeRewardGold(game))
        self.assertIn("listened", narrative.victorResponse(game))

    def testTownSnapshotSeparatesOptionalVictorOutcomesAndOnlyThePlayersOwnDeed(self):
        for state, outcome in (("good_end", "rescued"), ("bad_end", "lost"), ("encounter_active", "unresolved")):
            with self.subTest(state=state):
                game = Game()
                narrative.snapshotTown(game, state)
                self.assertEqual(outcome, narrative.getVariable(game, "nouraajdVictorOutcome"))
        for class_id, (flag, deed, text) in narrative.CLASS_DEEDS.items():
            with self.subTest(class_id=class_id):
                game = Game(class_id)
                for foreign_flag, _, _ in narrative.CLASS_DEEDS.values():
                    game.player.setBoolProperty(foreign_flag, True)
                game.player.setBoolProperty(flag, False)
                narrative.snapshotTown(game, "not_started")
                self.assertEqual("none", narrative.getVariable(game, "nouraajdClassDeed"))
                game.player.setBoolProperty(flag, True)
                narrative.snapshotTown(game, "not_started")
                self.assertEqual(deed, narrative.getVariable(game, "nouraajdClassDeed"))
                self.assertIn(text, narrative.townRecap(game))

    def testBothRitualOutcomesRouteToExistingSiegeAndHaveDifferentSummaries(self):
        manifest = campaign.get_manifest("fallOfNouraajd")
        summaries = []
        for outcome, route in (("good", "good_ending"), ("bad", "bad_ending")):
            game = Game()
            narrative.recordRitualOutcome(game, outcome)
            summaries.append(narrative.siegeSummary(game))
            self.assertEqual("siege", campaign.next_scenario(manifest, "cleansing", route))
        self.assertNotEqual(*summaries)

    def testWitnessContextIsAppendedOnce(self):
        dialog = PropertyObject()
        state = PropertyObject()
        state.properties = {"stateId": "ENTRY", "text": "The chapel is occupied."}
        dialog.getStates = lambda: [state]
        narrative.appendDialogContext(dialog, "ENTRY", "Victor was heard.")
        narrative.appendDialogContext(dialog, "ENTRY", "Victor was heard.")
        self.assertEqual(1, state.getStringProperty("text").count("Victor was heard."))


class RitualResolutionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classes = loadMapClasses("ritual")

    def setUp(self):
        self.game = Game()
        self.map = self.game.map
        self.dialog = self.classes["CapturedSoulDialog"](self.game)
        self.map.properties = {"bad_ending": True, "captive_lost": True}

    def testTimeoutAloneDoesNotCompleteResolutionOrPayOrAdvance(self):
        self.dialog.continueAfterLoss()
        self.assertFalse(self.classes["FinalResolutionQuest"](self.game).isCompleted())
        self.assertFalse(self.classes["RitualQuest"](self.game).isCompleted())
        self.assertEqual(0, self.game.player.gold)
        self.assertIsNone(self.game.pending)

    def testLossContinuationRequiresBothObjectivesAndActualCaptivePosition(self):
        for anchors, leader, at_captive in ((False, True, True), (True, False, True), (True, True, False)):
            with self.subTest(anchors=anchors, leader=leader, at_captive=at_captive):
                self.map.setBoolProperty("anchors_destroyed", anchors)
                self.map.setBoolProperty("leader_defeated", leader)
                self.game.player.coords.x = 4 if at_captive else 3
                self.dialog.continueAfterLoss()
                self.assertEqual(0, self.game.player.gold)
                self.assertFalse(self.map.getBoolProperty("ritual_resolution_chosen"))
                self.assertIsNone(self.game.pending)

    def testBadResolutionPaysOnceSettlesQuestsAndRetriesOnlyFailedJourney(self):
        self.map.setBoolProperty("anchors_destroyed", True)
        self.map.setBoolProperty("leader_defeated", True)
        store = campaign.CampaignStateStore(self.game.player)
        store.begin("fallOfNouraajd", "cleansing")
        self.dialog.continueAfterLoss()
        self.assertEqual(100, self.game.player.gold)
        self.assertEqual([], self.game.player.items)
        self.assertTrue(self.classes["FinalResolutionQuest"](self.game).isCompleted())
        self.assertTrue(self.classes["RitualQuest"](self.game).isCompleted())
        self.assertEqual(["checkQuests", "transition"], self.game.events)
        self.dialog.continueAfterLoss()
        self.assertEqual(100, self.game.player.gold)
        self.game.finishTransition(False)
        self.assertTrue(campaign.hasPendingTransition(self.game))
        self.assertEqual("cleansing", store.scenario())
        self.assertEqual("bad", narrative.getVariable(self.game, "ritualOutcome"))
        campaign.retryPending(self.game)
        self.game.finishTransition(True)
        self.assertEqual("siege", store.scenario())
        self.assertEqual([("cleansing", "bad_ending")], store.history())
        self.assertEqual(100, self.game.player.gold)

    def testLegacyPaidLossCanContinueWithoutASecondReward(self):
        self.map.setBoolProperty("anchors_destroyed", True)
        self.map.setBoolProperty("leader_defeated", True)
        self.map.setBoolProperty("reward_claimed", True)
        self.game.player.gold = 100
        self.dialog.continueAfterLoss()
        self.assertEqual(100, self.game.player.gold)
        self.assertIsNotNone(self.game.pending)
        self.game.finishTransition(True)

    def testGoodResolutionKeepsItsExistingRewardAndGuard(self):
        self.map.properties = {"anchors_destroyed": True, "leader_defeated": True}
        self.dialog.free_captive()
        self.dialog.free_captive()
        self.assertEqual(300, self.game.player.gold)
        self.assertEqual(["LifePotion"], self.game.player.items)
        self.assertEqual("good", narrative.getVariable(self.game, "ritualOutcome"))
        self.assertTrue(self.classes["FinalResolutionQuest"](self.game).isCompleted())
        self.game.finishTransition(True)

    def testLeaderDeathAfterLossDoesNotClaimContinuationReward(self):
        self.map.setBoolProperty("anchors_destroyed", True)
        self.classes["RitualLeaderTrigger"](self.game).trigger(self.map, None)
        self.assertTrue(self.map.getBoolProperty("leader_defeated"))
        self.assertFalse(self.map.getBoolProperty("reward_claimed"))
        self.assertEqual(0, self.game.player.gold)
        self.assertIsNone(self.game.pending)


class SiegeBreachTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classes = loadMapClasses("siege")

    def setUp(self):
        self.game = Game()
        self.game.map.map_name = "siege"
        self.gate = self.classes["SpawnPoint"](self.game)
        self.gate.properties = {"enabled": True, "canStep": True}
        self.wand = types.SimpleNamespace(hasTag=lambda tag: tag == "wand")
        self.game.player.items = [self.wand]

    def testRemotePlayerCannotSealOrConsumeAWand(self):
        self.game.player.coords.x -= 1
        self.assertFalse(self.gate.sealBreach())
        self.assertEqual([self.wand], self.game.player.items)
        self.assertFalse(self.gate.getBoolProperty("destroyed"))

    def testMissingWandAndInactiveGateCannotSeal(self):
        self.game.player.items = []
        self.assertFalse(self.gate.sealBreach())
        self.game.player.items = [self.wand]
        self.gate.setBoolProperty("enabled", False)
        self.assertFalse(self.gate.sealBreach())
        self.assertEqual([self.wand], self.game.player.items)

    def testSealConsumesOneOwnedWandCompletesOnceAndCannotRepeat(self):
        self.game.player.items.append(self.wand)
        self.assertTrue(self.gate.sealBreach())
        self.assertEqual([self.wand], self.game.player.items)
        self.assertTrue(self.gate.getBoolProperty("destroyed"))
        self.assertFalse(self.gate.getBoolProperty("enabled"))
        self.assertFalse(self.gate.getBoolProperty("canStep"))
        self.assertEqual(["checkQuests"], self.game.events)
        self.assertFalse(self.gate.sealBreach())
        self.assertEqual([self.wand], self.game.player.items)
        self.assertEqual(["checkQuests"], self.game.events)

    def testBountyDescriptionAndClaimedPayoutUseTheSamePersistentChoice(self):
        for threatened, expected in ((False, 500), (True, 475)):
            with self.subTest(threatened=threatened):
                game = Game()
                game.map.map_name = "siege"
                if threatened:
                    narrative.recordGateApproach(game, "threatened")
                quest = self.classes["DefendSiegeQuest"](game)
                self.assertTrue(quest.getReward().startswith(str(expected)))
                quest.onComplete()
                quest.onComplete()
                self.assertEqual(expected, game.player.gold)
                self.assertTrue(game.map.getBoolProperty("campaign_completed"))


class NarrativeRouteTest(unittest.TestCase):
    def testEveryMandatoryRitualLandmarkHasAnAdjacentAuthoredRoute(self):
        from tests.narrative_walkthrough import authoredRegion
        from tests.castle_walkthrough import TransitRoutes, shortestRoute

        objects, walkable = authoredRegion("ritual")
        document = json.loads((REPO_ROOT / "res/maps/ritual/map.json").read_text())
        here = tuple(int(document["properties"][axis]) for axis in "xyz")
        length = 0
        for name in ("anchorNorth", "anchorCrypt", "anchorSanctum", "ritualCaptive"):
            route = shortestRoute(walkable, TransitRoutes(), here, objects[name])
            self.assertTrue(route, name)
            cursor = here
            for step, arrival in route:
                self.assertEqual(1, sum(abs(a - b) for a, b in zip(step, cursor)))
                self.assertEqual(step, arrival)
                cursor = arrival
            length += len(route)
            here = objects[name]
        self.assertLess(length, 70, "The shortest good route must fit the unchanged five-turn ritual countdown")


if __name__ == "__main__":
    unittest.main()
