# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source inventory/mapping contracts only; no native execution, coverage or classic-parity credit."""

import copy
import json
from pathlib import Path
import unittest

from scripts.build_baldurs_gate_city_ledger import buildLedger, validateLedger

ROOT = Path(__file__).resolve().parents[1]


def readJson(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expectedIds(source, quests):
    """Enumerate audited records independently from implementation/config mapping."""
    result = set()
    for area_id, area in source["areas"].items():
        if area.get("rest_interruptions"):
            result.add(area_id + ":restInterruptions")
        for index, actor in enumerate(area["actors"], 1):
            key = actor.get("sourceId", f"{area_id}#actor{index}")
            result.add(key)
            creature = source["creatures"].get(actor.get("creatureMetadata", actor["creature"]), {})
            if actor.get("dialogue") or creature.get("dialogue"):
                result.add(key + ":conversation")
        for family, kind in (
            ("doors", "door"),
            ("containers", "container"),
            ("regions", "region"),
            ("spawns", "spawnPoint"),
        ):
            for index, row in enumerate(area.get(family, []), 1):
                result.add(row.get("sourceId", f"{area_id}#{kind}{index}"))
    result.update(f"WORLDMAP.WMP#cityLink{index}" for index in range(1, len(source["worldMapLinks"]) + 1))
    result.update(row["sourceId"] for row in source["scriptedActors"])
    for row in source.get("campaignNpcs", []):
        result.add(row["sourceId"])
        creature = source["creatures"].get(row.get("creatureMetadata", row["creature"]), {})
        if creature.get("dialogue"):
            result.add(row["sourceId"] + ":conversation")
    result.update(resource + ":behavior" for resource in source["references"] if resource.endswith((".DLG", ".BCS")))
    result.update(creature_id + ":creature" for creature_id in source["creatures"])
    result.update(item_id + ":item" for item_id in source["items"])
    result.update(resource + ":rule" for resource in source.get("numericSourceRules", {}))
    for store_id, store in source["stores"].items():
        result.add(store_id + ":store")
        for family, kind in (("stock", "stock"), ("drinks", "drink"), ("cures", "cure"), ("room_prices", "room")):
            result.update(f"{store_id}:{kind}{index}" for index in range(1, len(store[family]) + 1))
    for quest in quests["quests"]:
        result.add(f"quest:{quest['id']}:accept")
        result.update(f"quest:{quest['id']}:{choice['id']}" for choice in quest["outcomes"])
    return result


def minimalInputs():
    sha256 = "a" * 64
    item = {"item": "RING16", "expiration": 3, "charges": [1, 2, 4], "flags": 10}
    creature = {
        "sha256": sha256,
        "items": [item],
        "dialogue": "RESIDENT",
        "gold": 9,
        "allegiance": 128,
        "scripts": ["ACT01"],
        "known_spells": ["SPWI112"],
        "memorized_spells": [],
        "effect_count": 1,
        "effects_interpreted": False,
    }
    source = {
        "sourceEdition": "supporting EE base archives",
        "worldMapSha256": sha256,
        "areas": {
            "AR0100": {
                "sha256": sha256,
                "actors": [
                    {
                        "sourceId": "AR0100#actor1",
                        "creature": "RESIDENT",
                        "position": [100, 200],
                        "schedule": 12,
                        "flags": 1,
                    }
                ],
                "doors": [{"name": "Door1", "flags": 2, "lock_difficulty": 30, "key": "KEY01"}],
                "containers": [
                    {
                        "sourceId": "AR0100#container1",
                        "name": "Chest",
                        "items": [item],
                        "flags": 1,
                        "lock_difficulty": 40,
                        "owner": "resident",
                        "trapped": 1,
                    }
                ],
                "regions": [
                    {
                        "sourceId": "AR0100#region1",
                        "name": "Trap1",
                        "type": 0,
                        "trapped": 1,
                        "destination": "",
                        "script": "TRAP01",
                    }
                ],
                "spawns": [{"name": "Spawn1", "creatures": ["RESIDENT"], "enabled": 1, "method": 2}],
            }
        },
        "creatures": {"RESIDENT": creature},
        "items": {"RING16": {"sha256": sha256, "ability_count": 1}},
        "stores": {
            "SHOP": {
                "sha256": sha256,
                "flags": 64,
                "store_type": 1,
                "steal_failure": 100,
                "purchased_types": [1],
                "sell_markup": 130,
                "buy_markup": 80,
                "depreciation": 10,
                "identify_price": 100,
                "stock": [dict(item, stock=1, infinite=False)],
                "drinks": [{"price": 1, "strength": 30}],
                "cures": [{"spell": "SPPR101", "price": 10}],
                "room_flags": 1,
                "room_prices": [1, 3, 5, 8],
            }
        },
        "references": {
            "RESIDENT.DLG": {"sha256": sha256, "states": 2, "transitions": 3},
            "ACT01.BCS": {"sha256": sha256},
        },
        "scriptedActors": [
            {
                "sourceId": "ACT01.BCS#spawn0",
                "sourceResource": "ACT01.BCS",
                "sourceSha256": sha256,
                "creature": "RESIDENT",
                "position": [-1, -1],
                "areas": ["AR0100", "AR0200"],
                "conditions": [{"signature": "Opened(O:Object*)"}],
                "conditionSemanticsEvaluated": False,
            }
        ],
        "worldMapLinks": [
            {
                "source": "AR0100",
                "destination": "AR0200",
                "direction": "east",
                "entrance": "Entry",
                "outsideCity": False,
                "travel_time_quarters": 1,
            }
        ],
    }
    quests = {
        "quests": [
            {
                "id": "sample",
                "phase": 5,
                "givers": [{"label": "Resident", "area": "AR0100"}],
                "deadlineHours": 240,
                "acceptConditions": {"history": {"outsideQuest": True}},
                "outcomes": [
                    {
                        "id": "complete",
                        "conditions": {"minSocial": 12},
                        "effects": {"gold": 10, "takeItems": [{"item": "RING16", "count": 1}]},
                    }
                ],
                "sources": ["https://www.forgottenwars.com/bg1/ar0100.htm"],
            }
        ]
    }
    config = {
        "resident": {
            "class": "BaldursGateCreature",
            "properties": {
                "label": "Resident",
                "sourceActor": "AR0100#actor1",
                "sourceArea": "AR0100",
                "sourceCreature": "RESIDENT",
                "sourceDialogue": "RESIDENT",
                "sourceStore": "SHOP",
            },
        },
        "residentDialog": {
            "class": "BaldursGateDialog",
            "properties": {
                "actorId": "resident",
                "states": [
                    {
                        "options": [
                            {"action": "talk"},
                            {"action": "acceptSample", "condition": "canAcceptSample"},
                            {"action": "questSampleComplete", "condition": "canQuestSampleComplete"},
                        ]
                    }
                ],
            },
        },
        "cityClock": {"properties": {"storeDefinitions": json.dumps(source["stores"])}},
    }
    script = """class BaldursGateDialog:
    def talk(self): pass
    def acceptSample(self): pass
    def canAcceptSample(self): pass
    def questSampleComplete(self): pass
    def canQuestSampleComplete(self): pass
    def browseServices(self): pass
"""
    return source, quests, config, script


class BaldursGateCityLedgerUnitTest(unittest.TestCase):
    def setUp(self):
        self.source, self.quests, self.config, self.script = minimalInputs()

    def ledger(self):
        return buildLedger(self.source, self.quests, self.config, self.script)

    def records(self):
        return {row["id"]: row for row in self.ledger()["entries"]}

    def testAllSourceFamiliesAppearEvenWhenNativeMappingsAreAbsent(self):
        ledger = self.ledger()
        self.assertEqual(expectedIds(self.source, self.quests), {row["id"] for row in ledger["entries"]})
        records = self.records()
        for key in ("AR0100#region1", "AR0100#container1", "AR0100#door1", "AR0100#spawnPoint1", "ACT01.BCS#spawn0"):
            self.assertEqual("missing", records[key]["implementation"]["status"], key)
        self.assertTrue(validateLedger(ledger, require_mapped=True))
        self.assertFalse(validateLedger(ledger))

    def testAddingSourceActorCreatesMissingObligationWithoutChangingConfiguration(self):
        actor = copy.deepcopy(self.source["areas"]["AR0100"]["actors"][0])
        actor["sourceId"] = "AR0100#actor2"
        self.source["areas"]["AR0100"]["actors"].append(actor)
        records = self.records()
        self.assertEqual("missing", records[actor["sourceId"]]["implementation"]["status"])
        self.assertEqual("missing", records[actor["sourceId"] + ":conversation"]["implementation"]["status"])

    def testGenericSpeakNeverClaimsSourceConversationCoverage(self):
        self.config["residentDialog"]["properties"]["states"] = [{"options": [{"action": "talk"}]}]
        records = self.records()
        self.assertEqual("partial", records["AR0100#actor1"]["implementation"]["status"])
        self.assertEqual("missing", records["AR0100#actor1:conversation"]["implementation"]["status"])
        self.assertEqual("planned", records["RESIDENT.DLG:behavior"]["implementation"]["status"])
        self.assertEqual("planned", records["quest:sample:accept"]["implementation"]["status"])

    def testQuestChoiceRequiresActorDialogAndBothConcreteCallbacks(self):
        self.assertEqual("partial", self.records()["quest:sample:complete"]["implementation"]["status"])
        self.script = self.script.replace("    def canQuestSampleComplete(self): pass\n", "")
        row = self.records()["quest:sample:complete"]
        self.assertEqual("planned", row["implementation"]["status"])
        self.assertTrue(any("callback" in gap for gap in row["gaps"]))

    def testSourceOwnershipAndConditionsArePreservedWithoutEvaluatingThem(self):
        records = self.records()
        actor = records["AR0100#actor1"]
        self.assertEqual(self.source["creatures"]["RESIDENT"]["items"], actor["ownership"]["items"])
        self.assertEqual(12, actor["timers"]["scheduleMask"])
        self.assertEqual([1, 2, 4], actor["ownership"]["items"][0]["charges"])
        spawned = records["ACT01.BCS#spawn0"]
        self.assertFalse(spawned["prerequisites"]["conditionSemanticsEvaluated"])
        self.assertEqual(["AR0100", "AR0200"], spawned["facts"]["areas"])
        choice = records["quest:sample:accept"]
        self.assertEqual({"history": {"outsideQuest": True}}, choice["prerequisites"])
        self.assertEqual(240, choice["timers"]["deadlineHours"])
        self.assertEqual(5, choice["phase"]["adaptation"])

    def testAuthoredSpawnPolicyRetainsSourceConditionsAndActualPrerequisites(self):
        self.config["spawnedResident"] = {"properties": {"sourceSpawnFact": "ACT01.BCS#spawn0"}}
        policy = {"id": "spawnedResident", "phase": 7, "requiresQuest": {"sample": "active"}, "x": 1, "y": 2, "z": 3}
        self.config["cityClock"]["properties"]["actorDefinitions"] = json.dumps([policy])
        row = self.records()["ACT01.BCS#spawn0"]
        self.assertEqual("partial", row["implementation"]["status"])
        self.assertEqual([policy], row["nativeConversion"]["authoredPolicies"])
        self.assertFalse(row["prerequisites"]["conditionSemanticsEvaluated"])

    def testAssignedNativeLockChecksAreRecordedAlongsideSourceDifficulty(self):
        self.config["door"] = {
            "properties": {"sourceDoor": "AR0100#door1", "lockAgility": 12, "forceStrength": 12, "forbidPicking": False}
        }
        row = self.records()["AR0100#door1"]
        self.assertEqual(30, row["prerequisites"]["lock_difficulty"])
        self.assertEqual(12, row["nativeConversion"]["assignedChecks"][0]["lockAgility"])

    def testCampaignRecruitmentMappingPreservesOutsideHistoryBoundary(self):
        self.source["campaignNpcs"] = [
            {
                "sourceId": "BALDUR.GAM#npc13",
                "sourceSha256": "b" * 64,
                "creature": "RESIDENT",
                "area": "AR0900",
                "position": [483, 803],
                "scopeClassification": "boundaryHistory",
                "selection_flags": 0,
                "party_order": 0,
                "talk_count": 0,
            }
        ]
        self.config["historyFollower"] = {"properties": {"sourceGameNpc": "BALDUR.GAM#npc13"}}
        records = self.records()
        row = records["BALDUR.GAM#npc13"]
        self.assertEqual("partial", row["implementation"]["status"])
        self.assertTrue(row["nativeConversion"]["explicitHistoryRequired"])
        self.assertTrue(row["nativeConversion"]["outsidePlayableAreaForbidden"])
        self.assertEqual("missing", records["BALDUR.GAM#npc13:conversation"]["implementation"]["status"])
        self.assertNotIn("AR0900", self.source["areas"])

    def testNumericSourceRulesRequireActualStagedCellsAndNativeCallback(self):
        rule = {
            "sha256": "c" * 64,
            "columns": ["MONEY_CHURCH", "BASE_CHURCH"],
            "rows": {"10": {"MONEY_CHURCH": 10, "BASE_CHURCH": 300}},
            "default": 0,
        }
        self.source["numericSourceRules"] = {"REPUTATI.2DA": rule}
        self.assertEqual("missing", self.records()["REPUTATI.2DA:rule"]["implementation"]["status"])
        self.config["cityClock"]["properties"]["numericSourceRules"] = json.dumps(self.source["numericSourceRules"])
        self.assertEqual("planned", self.records()["REPUTATI.2DA:rule"]["implementation"]["status"])
        self.script += "    def donate(self): pass\n"
        row = self.records()["REPUTATI.2DA:rule"]
        self.assertEqual("partial", row["implementation"]["status"])
        self.assertEqual(rule["rows"], row["facts"]["rows"])

    def testStoreReferencesArePlannedUntilReachableNativeServiceMethodsExist(self):
        self.assertEqual("partial", self.records()["SHOP:drink1"]["implementation"]["status"])
        self.script = "class BaldursGateDialog: pass"
        self.assertEqual("planned", self.records()["SHOP:drink1"]["implementation"]["status"])
        self.config["cityClock"]["properties"]["storeDefinitions"] = "{}"
        self.assertEqual("missing", self.records()["SHOP:store"]["implementation"]["status"])

    def testKnownEditionExclusionIsExplicitAndNeverAwardsClassicParity(self):
        self.source["editionExcludedCreatures"] = {"RESIDENT": "Known EE addition."}
        row = self.records()["AR0100#actor1"]
        self.assertEqual("excluded", row["implementation"]["status"])
        self.assertIn("Known EE addition.", row["editionDifferences"])
        self.assertFalse(self.ledger()["originalParityEstablished"])
        self.assertTrue(validateLedger(self.ledger(), require_acceptance=True))

    def testOmittedDuplicateOrStaleObligationFailsClosed(self):
        expected = self.ledger()
        damaged = copy.deepcopy(expected)
        removed = damaged["entries"].pop()
        self.assertIn("Missing obligation: " + removed["id"], validateLedger(damaged, expected=expected))
        damaged = copy.deepcopy(expected)
        damaged["entries"].append(copy.deepcopy(damaged["entries"][0]))
        self.assertIn("Duplicate obligation IDs", validateLedger(damaged))
        damaged = copy.deepcopy(expected)
        damaged["entries"][0]["effects"] = {"invented": "reward"}
        self.assertTrue(validateLedger(damaged, expected=expected))

    def testMetadataCannotAwardNativeOrCoverageEvidence(self):
        ledger = self.ledger()
        self.assertFalse(ledger["acceptanceReady"])
        self.assertTrue(all(row["testStatus"]["coverage"] == "not established" for row in ledger["entries"]))
        ledger["entries"][0]["testStatus"]["native"] = "passed"
        self.assertTrue(any("cannot be awarded" in problem for problem in validateLedger(ledger)))

    def testCountsFingerprintsAndPartialTargetsCannotBeForged(self):
        ledger = self.ledger()
        ledger["counts"]["families"]["actor"] = 0
        self.assertIn("Ledger family count mismatch", validateLedger(ledger))
        ledger = self.ledger()
        row = next(row for row in ledger["entries"] if row["implementation"]["status"] == "partial")
        row["implementation"]["targets"] = []
        self.assertTrue(any("no implementation target" in problem for problem in validateLedger(ledger)))
        ledger = self.ledger()
        ledger["entries"][0]["evidence"][0]["sha256"] = "invented"
        self.assertTrue(any("Invalid source fingerprint" in problem for problem in validateLedger(ledger)))
        ledger = self.ledger()
        ledger["entries"][0]["testStatus"]["coverage"] = "100%"
        self.assertTrue(any("Coverage cannot be awarded" in problem for problem in validateLedger(ledger)))


class BaldursGateCityLedgerFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = readJson(ROOT / "tests/fixtures/baldurs_gate_city_source.json")
        cls.quests = readJson(ROOT / "tests/fixtures/baldurs_gate_city_quests.json")
        cls.config = readJson(ROOT / "res/maps/baldursGate/config.json")
        cls.script = (ROOT / "res/maps/baldursGate/script.py").read_text(encoding="utf-8")
        cls.ledger = readJson(ROOT / "tests/fixtures/baldurs_gate_city_ledger.json")
        cls.expected = buildLedger(cls.source, cls.quests, cls.config, cls.script)

    def testSavedLedgerCoversEverySourceObligationAndMatchesCurrentInputs(self):
        self.assertEqual(expectedIds(self.source, self.quests), {row["id"] for row in self.ledger["entries"]})
        self.assertEqual([], validateLedger(self.ledger, expected=self.expected))
        self.assertEqual(212, len(self.source["areas"]))
        self.assertGreater(len(self.ledger["entries"]), 7000)

    def testEveryEvidencePointerResolvesAndFingerprintIsAvailable(self):
        fixtures = {
            "tests/fixtures/baldurs_gate_city_source.json": self.source,
            "tests/fixtures/baldurs_gate_city_quests.json": self.quests,
        }
        for row in self.ledger["entries"]:
            for evidence in row["evidence"]:
                value = fixtures[evidence["fixture"]]
                for component in evidence["pointer"].lstrip("/").split("/"):
                    value = value[int(component)] if isinstance(value, list) else value[component]
                self.assertIsNotNone(value, row["id"])
                self.assertRegex(evidence["sha256"], r"^[a-f0-9]{64}$", row["id"])

    def testIncompleteAdaptationAndClassicSourceGapsRemainVisible(self):
        self.assertFalse(self.ledger["acceptanceReady"])
        self.assertFalse(self.ledger["originalParityEstablished"])
        self.assertTrue(self.ledger["unresolvedSourceReferences"])
        self.assertTrue(validateLedger(self.ledger, require_mapped=True))
        self.assertTrue(validateLedger(self.ledger, require_acceptance=True))
        self.assertGreater(self.ledger["counts"]["implementation"].get("missing", 0), 0)
        for row in self.ledger["entries"]:
            self.assertEqual("pending", row["testStatus"]["native"])
            self.assertNotEqual("implemented", row["implementation"]["status"])


if __name__ == "__main__":
    unittest.main()
