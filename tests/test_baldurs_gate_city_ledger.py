# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source inventory/mapping contracts only; no native execution, coverage or classic-parity credit."""

import copy
import json
from pathlib import Path
import unittest

from scripts.build_baldurs_gate_city_ledger import buildLedger, fingerprint, validateLedger

WARNING_PATH = "tests/fixtures/baldurs_gate_seven_suns_warning.json"
DOPMER_PATH = "tests/fixtures/baldurs_gate_seven_suns_merchants.json"
STOCK_PATH = "tests/fixtures/baldurs_gate_seven_suns_stock.json"

ROOT = Path(__file__).resolve().parents[1]


def readJson(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expectedIds(source, quests, warning=None, dopmer=None, stock=None):
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
    if warning is not None:
        result.update(f"DOPPSM.DLG#state{index}" for index in range(9))
        result.update(f"DOPPSM.DLG#edge{index}" for index in range(17))
        result.update({"DOPPSM.DLG#journal26986", "DOPPSM.DLG#globalAskedForTour", "DOPPSM.DLG#globalCheckedSevenSuns"})
    if dopmer is not None:
        result.update(f"DOPMER.DLG#state{index}" for index in range(14))
        result.update(f"DOPMER.DLG#edge{index}" for index in range(24))
        result.update("DOPMER.DLG#global" + name for name in ("CheckedSevenSuns", "Doppleganger", "Laola"))
        result.update(
            "DOPMER.DLG#talkCounter:" + actor
            for actor in ("AR0601#actor1", "AR0601#actor3", "AR0602#actor1", "AR0602#actor2")
        )
        result.update({"SPWI993.SPL#replacement", "DOPPSS.CRE#stock:S1-12", "DOPPSS.CRE#stock:RNDTRE05"})
    if stock is not None:
        result.update({"BOLT05:item", "SCRL1J:item", "SCRL2I:item"})
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


class BaldursGateSevenSunsWarningLedgerTest(unittest.TestCase):
    """Factual source graph and mapping contracts only; no native or parity acceptance."""

    @classmethod
    def setUpClass(cls):
        cls.warning = readJson(ROOT / WARNING_PATH)
        cls.dopmer = readJson(ROOT / DOPMER_PATH)
        cls.stock = readJson(ROOT / STOCK_PATH)
        cls.full_source = readJson(ROOT / "tests/fixtures/baldurs_gate_city_source.json")
        cls.full_quests = readJson(ROOT / "tests/fixtures/baldurs_gate_city_quests.json")

    def mappedInputs(self):
        source, quests, config, script = minimalInputs()
        source["references"]["DOPPSM.DLG"] = copy.deepcopy(self.full_source["references"]["DOPPSM.DLG"])
        source["creatures"]["DOPPSM"] = {**source["creatures"]["RESIDENT"], "dialogue": "DOPPSM"}
        source["areas"]["AR0601"] = {
            "sha256": source["areas"]["AR0100"]["sha256"],
            "doors": [],
            "containers": [],
            "regions": [],
            "spawns": [],
            "actors": [
                {
                    "sourceId": "AR0601#actor2",
                    "creature": "DOPPSM",
                    "dialogue": "DOPPSM",
                    "position": [1, 0],
                    "schedule": 0,
                    "flags": 0,
                }
            ],
        }
        config["cityAr0601Actor2"] = {
            "class": "CCreature",
            "properties": {
                "sourceActor": "AR0601#actor2",
                "sourceArea": "AR0601",
                "sourceCreature": "DOPPSM",
                "sourceDialogue": "DOPPSM",
            },
        }
        config["cityClock"]["properties"]["sevenSunsWarningDefinition"] = json.dumps(
            {
                "version": 1,
                "dialogue": "DOPPSM",
                "fingerprint": self.warning["sources"]["dialogueFingerprint"]["sha256"],
                "journalQuest": "citySevenSunsWarningLead",
            }
        )
        config["citySevenSunsWarningLead"] = {"class": "BaldursGateSevenSunsWarningLeadQuest", "properties": {}}
        script += "    def isSevenSunsWarningActor(self): pass\n"
        script += "    def conversationSevenSunsWarning(self): pass\n"
        script += "    def validSevenSunsWarningView(self): pass\n"
        script += "class BaldursGateSevenSunsWarningLeadQuest: pass\n"
        return source, quests, config, script

    def warningRows(self, ledger):
        return {row["id"]: row for row in ledger["entries"] if row["id"].startswith("DOPPSM.DLG#")}

    def testWarningAddsExactly29RowsWithoutShrinking7471ExistingIds(self):
        source, quests = self.full_source, self.full_quests
        original = buildLedger(source, quests, {}, "")
        updated = buildLedger(source, quests, {}, "", warning=self.warning)
        old_ids = {row["id"] for row in original["entries"]}
        new_ids = {row["id"] for row in updated["entries"]}
        self.assertEqual(7471, len(old_ids))
        self.assertEqual(7500, len(new_ids))
        self.assertTrue(old_ids < new_ids)
        self.assertEqual(expectedIds(source, quests, self.warning), new_ids)
        self.assertEqual(29, len(self.warningRows(updated)))
        self.assertTrue(all(row["implementation"]["status"] == "planned" for row in self.warningRows(updated).values()))
        self.assertEqual([], validateLedger(updated))

    def testReachablePartialMappingRetainsAllUnreachableRowsAsPlanned(self):
        ledger = buildLedger(*self.mappedInputs(), warning=self.warning)
        rows = self.warningRows(ledger)
        self.assertEqual(29, len(rows))
        self.assertEqual(21, sum(row["implementation"]["status"] == "partial" for row in rows.values()))
        planned = {f"DOPPSM.DLG#state{index}" for index in (4, 5, 6)}
        planned.update(f"DOPPSM.DLG#edge{index}" for index in range(10, 15))
        self.assertEqual(planned, {key for key, row in rows.items() if row["implementation"]["status"] == "planned"})
        for key in planned:
            self.assertFalse(rows[key]["implementation"]["targets"])
            self.assertTrue(any("No path" in gap or "No audited" in gap for gap in rows[key]["gaps"]), key)
            self.assertNotEqual("excluded", rows[key]["implementation"]["status"])
        records = {row["id"]: row for row in ledger["entries"]}
        for key in ("DOPPSM.DLG:behavior", "AR0601#actor2:conversation"):
            self.assertEqual("partial", records[key]["implementation"]["status"])
            self.assertTrue(any("SSUNGU" in gap and "INITDLG" in gap for gap in records[key]["gaps"]))

    def testMissingExactActorHelperClockOrJournalPreventsPartialWarningCredit(self):
        for missing in ("actor", "identity", "helper", "clock", "versionBool", "versionFloat", "journal", "class"):
            with self.subTest(missing=missing):
                source, quests, config, script = self.mappedInputs()
                if missing == "actor":
                    del config["cityAr0601Actor2"]
                elif missing == "identity":
                    config["cityAr0601Actor2"]["properties"]["sourceActor"] = "AR0601#actor1"
                elif missing == "helper":
                    script = script.replace("def validSevenSunsWarningView", "def unrelatedView")
                elif missing == "clock":
                    del config["cityClock"]["properties"]["sevenSunsWarningDefinition"]
                elif missing in ("versionBool", "versionFloat"):
                    definition = json.loads(config["cityClock"]["properties"]["sevenSunsWarningDefinition"])
                    definition["version"] = True if missing == "versionBool" else 1.0
                    config["cityClock"]["properties"]["sevenSunsWarningDefinition"] = json.dumps(definition)
                elif missing == "journal":
                    del config["citySevenSunsWarningLead"]
                elif missing == "class":
                    config["citySevenSunsWarningLead"]["class"] = "CQuest"
                ledger = buildLedger(source, quests, config, script, warning=self.warning)
                self.assertTrue(
                    all(row["implementation"]["status"] == "planned" for row in self.warningRows(ledger).values())
                )

    def testSourceFingerprintCountAndDroppedGraphMismatchesFailBeforeInventoryCanShrink(self):
        for damage in ("fingerprint", "statesCount", "edgesCount", "state", "edge", "duplicate"):
            with self.subTest(damage=damage):
                source, quests, config, script = self.mappedInputs()
                warning = copy.deepcopy(self.warning)
                if damage == "fingerprint":
                    warning["sources"]["dialogueFingerprint"]["sha256"] = "f" * 64
                elif damage == "statesCount":
                    source["references"]["DOPPSM.DLG"]["states"] = 8
                elif damage == "edgesCount":
                    source["references"]["DOPPSM.DLG"]["transitions"] = 16
                elif damage == "state":
                    warning["states"].pop(4)
                elif damage == "edge":
                    warning["states"][4]["transitions"].pop()
                else:
                    warning["states"][4]["transitions"][0]["id"] = 0
                with self.assertRaisesRegex(ValueError, "Seven Suns warning"):
                    buildLedger(source, quests, config, script, warning=warning)

    def testWarningEffectsConditionsGlobalsJournalFlagsAndEvidenceStayFactual(self):
        ledger = buildLedger(*self.mappedInputs(), warning=self.warning)
        rows = self.warningRows(ledger)
        self.assertEqual(29, len(rows))
        self.assertEqual(
            [{"op": "Global", "args": ["AskedForTour", "GLOBAL", 1]}],
            rows["DOPPSM.DLG#edge5"]["prerequisites"]["conditions"],
        )
        self.assertEqual(
            [
                {"op": "SetGlobal", "args": ["AskedForTour", "GLOBAL", 1]},
                {"op": "SetGlobal", "args": ["CheckedSevenSuns", "GLOBAL", 2]},
            ],
            rows["DOPPSM.DLG#edge1"]["effects"]["actions"],
        )
        self.assertEqual([{"op": "Enemy", "args": []}], rows["DOPPSM.DLG#edge14"]["effects"]["actions"])
        self.assertEqual(["SSUNGU", 5], rows["DOPPSM.DLG#edge13"]["effects"]["next"])
        journal = rows["DOPPSM.DLG#journal26986"]
        self.assertEqual(92, journal["effects"]["rawFlags"])
        self.assertIn("BG2-only", journal["nativeConversion"]["classic"]["journalRaw92Status"])
        for name in ("AskedForTour", "CheckedSevenSuns"):
            row = rows["DOPPSM.DLG#global" + name]
            self.assertEqual("GLOBAL", row["facts"]["scope"])
            self.assertIn("case-insensitive", row["prerequisites"]["variableNames"])
            self.assertIn("Preserve unknown integer", row["effects"]["existingIntegers"])
            self.assertFalse(row["ownership"]["privateWarningReceiptIsAuthoritative"])
        self.assertEqual(fingerprint(self.warning), ledger["inputs"][WARNING_PATH])
        for row in rows.values():
            for evidence in row["evidence"]:
                if evidence["fixture"] == WARNING_PATH:
                    value = self.warning
                    for component in evidence["pointer"].lstrip("/").split("/"):
                        value = value[int(component)] if isinstance(value, list) else value[component]
                    self.assertIsNotNone(value)
            self.assertEqual("pending", row["testStatus"]["native"])
            self.assertEqual("not established", row["testStatus"]["coverage"])
            self.assertTrue(row["ownership"])
            self.assertTrue(row["timers"])
        self.assertFalse(ledger["acceptanceReady"])
        self.assertFalse(ledger["originalParityEstablished"])
        self.assertEqual([], validateLedger(ledger))
        self.assertTrue(validateLedger(ledger, require_acceptance=True))

    def testWarningProofNeedsItsInputFingerprintAndKnownFixturePointer(self):
        ledger = buildLedger(*self.mappedInputs(), warning=self.warning)
        rows = self.warningRows(ledger)
        self.assertEqual(29, len(rows))
        del ledger["inputs"][WARNING_PATH]
        self.assertTrue(any("Missing warning input fingerprint" in item for item in validateLedger(ledger)))
        ledger = buildLedger(*self.mappedInputs(), warning=self.warning)
        self.warningRows(ledger)["DOPPSM.DLG#state0"]["evidence"][0]["fixture"] = "untrusted.json"
        self.assertTrue(any("Invalid source pointer" in item for item in validateLedger(ledger)))

    def dopmerInputs(self):
        source, quests, config, _script = minimalInputs()
        source["references"]["DOPMER.DLG"] = copy.deepcopy(self.full_source["references"]["DOPMER.DLG"])
        for name in ("DOPMER", "DOPPSS"):
            source["creatures"][name] = copy.deepcopy(self.full_source["creatures"][name])
        for name in ("S1-12", "RNDTRE05"):
            source["items"][name] = copy.deepcopy(self.full_source["items"][name])
        for area in ("AR0601", "AR0602"):
            source["areas"][area] = copy.deepcopy(self.full_source["areas"][area])
        for lineage in self.dopmer["lineages"]:
            config[lineage["id"]] = {
                "class": "CCreature",
                "properties": {
                    **{key: value for key, value in lineage.items() if key != "id"},
                    "sourceAllegiance": 128,
                },
            }
        config["cityClock"]["properties"]["sevenSunsMerchantDefinition"] = "city-json:" + json.dumps(
            {
                "version": 1,
                "dialogue": "DOPMER",
                "fingerprint": self.dopmer["dialogueFingerprint"]["sha256"],
                "stockContract": "doppss-native-v1",
            }
        )
        script = """class BaldursGateDialog:
    def isSevenSunsMerchantActor(self): pass
    def validSevenSunsMerchantView(self): pass
    def conversationSevenSunsMerchant(self): pass
    def talk(self): self.conversationSevenSunsMerchantFlow()
class BaldursGateClock:
    def settleSevenSunsMerchants(self): pass
    def onTurn(self): self.settleSevenSunsMerchantsFlow()
"""
        return source, quests, config, script

    def dopmerRows(self, ledger):
        old = expectedIds(self.full_source, self.full_quests, self.warning)
        return {
            row["id"]: row
            for row in ledger["entries"]
            if row["id"] not in old
            and (
                row["id"].startswith("DOPMER.DLG#")
                or row["id"] in {"SPWI993.SPL#replacement", "DOPPSS.CRE#stock:S1-12", "DOPPSS.CRE#stock:RNDTRE05"}
            )
        }

    def testDopmerAddsExactly48WithoutRemovingOrReclassifying7500Rows(self):
        original = buildLedger(self.full_source, self.full_quests, {}, "", warning=self.warning)
        updated = buildLedger(self.full_source, self.full_quests, {}, "", warning=self.warning, dopmer=self.dopmer)
        before = {row["id"]: row for row in original["entries"]}
        after = {row["id"]: row for row in updated["entries"]}
        self.assertEqual(7500, len(before))
        self.assertEqual(7548, len(after))
        self.assertEqual(before, {key: after[key] for key in before})
        self.assertEqual(expectedIds(self.full_source, self.full_quests, self.warning, self.dopmer), set(after))
        rows = self.dopmerRows(updated)
        self.assertEqual(48, len(rows))
        self.assertTrue(all(row["implementation"]["status"] == "planned" for row in rows.values()))
        self.assertEqual([], validateLedger(updated))
        self.assertFalse(updated["acceptanceReady"])
        self.assertFalse(updated["originalParityEstablished"])

    def testDopmerMappingsNeedExactLineagesTypedAllegianceDefinitionAndActualWiring(self):
        original = self.dopmerInputs()
        ledger = buildLedger(*original, dopmer=self.dopmer)
        rows = self.dopmerRows(ledger)
        self.assertEqual(45, sum(row["implementation"]["status"] == "partial" for row in rows.values()))
        self.assertEqual(
            {"SPWI993.SPL#replacement", "DOPPSS.CRE#stock:S1-12", "DOPPSS.CRE#stock:RNDTRE05"},
            {key for key, row in rows.items() if row["implementation"]["status"] == "planned"},
        )
        source, quests, config, script = copy.deepcopy(original)
        config["citySevenSunsRevealedDoppss"] = {"class": "CCreature", "properties": {}}
        config["citySevenSunsDoppssWeapon"] = {"class": "CWeapon", "properties": {}}
        configured = self.dopmerRows(buildLedger(source, quests, config, script, dopmer=self.dopmer))
        self.assertTrue(all(row["implementation"]["status"] == "partial" for row in configured.values()))
        for missing in (
            "actor",
            "identity",
            "ea",
            "eaBool",
            "definition",
            "versionBool",
            "helper",
            "talkWiring",
            "turnWiring",
            "settle",
        ):
            with self.subTest(missing=missing):
                source, quests, config, script = copy.deepcopy(original)
                actor = config["cityAr0601Actor1"]["properties"]
                if missing == "actor":
                    del config["cityAr0601Actor1"]
                elif missing == "identity":
                    actor["sourceActor"] = "AR0601#actor2"
                elif missing == "ea":
                    actor["sourceAllegiance"] = 255
                elif missing == "eaBool":
                    actor["sourceAllegiance"] = True
                elif missing == "definition":
                    del config["cityClock"]["properties"]["sevenSunsMerchantDefinition"]
                elif missing == "versionBool":
                    definition = json.loads(
                        config["cityClock"]["properties"]["sevenSunsMerchantDefinition"].removeprefix("city-json:")
                    )
                    definition["version"] = True
                    config["cityClock"]["properties"]["sevenSunsMerchantDefinition"] = json.dumps(definition)
                elif missing == "helper":
                    script = script.replace("def validSevenSunsMerchantView", "def unrelated")
                elif missing == "talkWiring":
                    script = script.replace("self.conversationSevenSunsMerchantFlow()", "pass")
                elif missing == "turnWiring":
                    script = script.replace("self.settleSevenSunsMerchantsFlow()", "pass")
                elif missing == "settle":
                    script = script.replace("def settleSevenSunsMerchants", "def unrelatedSettlement")
                result = buildLedger(source, quests, config, script, dopmer=self.dopmer)
                self.assertTrue(
                    all(row["implementation"]["status"] == "planned" for row in self.dopmerRows(result).values())
                )

    def testDopmerLiteralBindingsDroppedGraphAndFalseReplacementFailClosed(self):
        for damage in (
            "sourceFingerprint",
            "fixtureFingerprint",
            "floatBytes",
            "state",
            "edge",
            "duplicateState",
            "duplicateEdge",
            "stateOwnership",
            "entryCounter",
            "lineage",
            "sharedScope",
            "spell",
            "creature",
            "weapon",
            "effectiveWeapon",
            "random",
            "opcode",
            "styleBool",
            "effectValue",
            "effectOrder",
        ):
            with self.subTest(damage=damage):
                source, quests, config, script = self.dopmerInputs()
                fixture = copy.deepcopy(self.dopmer)
                if damage == "sourceFingerprint":
                    source["references"]["DOPMER.DLG"]["sha256"] = "f" * 64
                elif damage == "fixtureFingerprint":
                    fixture["dialogueFingerprint"]["sha256"] = "f" * 64
                elif damage == "floatBytes":
                    fixture["dialogueFingerprint"]["bytes"] = 1687.0
                elif damage == "state":
                    fixture["states"].pop()
                elif damage == "edge":
                    fixture["edges"].pop()
                elif damage == "duplicateState":
                    fixture["states"][1]["id"] = 0
                elif damage == "duplicateEdge":
                    fixture["edges"][1]["id"] = 0
                elif damage == "stateOwnership":
                    fixture["states"][0]["edges"] = []
                elif damage == "entryCounter":
                    fixture["entriesByPriorSourceTalkCount"]["2"] = 7
                elif damage == "lineage":
                    fixture["lineages"].pop()
                elif damage == "sharedScope":
                    fixture["sharedGlobals"]["scope"] = "global"
                elif damage in {"spell", "creature", "weapon", "random"}:
                    binding = {
                        "spell": "spell",
                        "creature": "replacementCreature",
                        "weapon": "weapon",
                        "random": "randomPlaceholder",
                    }[damage]
                    fixture["sourceBindings"][binding]["base"]["sha256"] = "f" * 64
                elif damage == "effectiveWeapon":
                    fixture["sourceBindings"]["weapon"]["effective"] = fixture["sourceBindings"]["weapon"]["base"]
                elif damage == "opcode":
                    fixture["replacement"]["opcode"] = 168
                elif damage == "styleBool":
                    fixture["replacement"]["style"] = False
                elif damage == "effectValue":
                    fixture["edges"][0]["orderedActions"][0]["arguments"][2]["value"] = 3
                elif damage == "effectOrder":
                    fixture["edges"][12]["orderedActions"].reverse()
                with self.assertRaises(ValueError):
                    buildLedger(source, quests, config, script, dopmer=fixture)

    def testDopmerAllSourceActionsCounterCancellationAndOwnershipRemainExplicit(self):
        ledger = buildLedger(*self.dopmerInputs(), dopmer=self.dopmer)
        rows = self.dopmerRows(ledger)
        self.assertEqual(14, sum(row["family"] == "dialogueState" for row in rows.values()))
        self.assertEqual(24, sum(row["family"] == "dialogueEdge" for row in rows.values()))
        for edge in self.dopmer["edges"]:
            self.assertEqual(edge["orderedActions"], rows[f"DOPMER.DLG#edge{edge['id']}"]["effects"]["orderedActions"])
        for lineage in self.dopmer["lineages"]:
            row = rows["DOPMER.DLG#talkCounter:" + lineage["sourceActor"]]
            self.assertEqual(lineage["id"], row["ownership"]["owner"])
            self.assertEqual("plugin_cityDopmerTalkCount", row["prerequisites"]["authoritativeField"])
            self.assertEqual({"0": 0, "1": 7, "2": 10}, row["facts"]["entriesByPriorSourceTalkCount"])
            self.assertIn("cancellation", row["timers"])
            self.assertIn("pending", row["timers"]["sourceScheduling"])
        self.assertEqual(3, sum(row["family"] == "sourceGlobal" for row in rows.values()))
        replacement = rows["SPWI993.SPL#replacement"]
        self.assertEqual({"death": False, "xp": 0, "loot": []}, replacement["effects"]["quietRetirementCredit"])
        self.assertEqual(0, replacement["facts"]["style"])
        weapon = rows["DOPPSS.CRE#stock:S1-12"]
        self.assertFalse(weapon["facts"]["sourceBinding"]["baseEffectiveEqual"])
        self.assertNotEqual(weapon["facts"]["sourceBinding"]["base"], weapon["facts"]["sourceBinding"]["effective"])
        self.assertTrue(rows["DOPPSS.CRE#stock:RNDTRE05"]["effects"]["placeholderIsNotActualStockProof"])
        self.assertTrue(
            all(
                row["testStatus"]["native"] == "pending" and row["testStatus"]["coverage"] == "not established"
                for row in rows.values()
            )
        )

    def testDopmerRouteCallbacksAreRecordedOnlyFromSuppliedActualFunctionDefinitions(self):
        routes = "def sevenSunsMerchantRoute(): pass\ndef merchantCounterRoute(): pass\nnot_a_function='merchantScheduleRoute'\n"
        ledger = buildLedger(*self.dopmerInputs(), dopmer=self.dopmer, routes=routes)
        self.assertIn("DOPMER.DLG#state0", self.dopmerRows(ledger))
        callbacks = self.dopmerRows(ledger)["DOPMER.DLG#state0"]["implementation"]["callbacks"]
        self.assertIn("tests/gameplay_routes_baldurs_gate.py:sevenSunsMerchantRoute", callbacks)
        self.assertIn("tests/gameplay_routes_baldurs_gate.py:merchantCounterRoute", callbacks)
        self.assertFalse(any(name.endswith(":merchantScheduleRoute") for name in callbacks))
        self.assertEqual(fingerprint(self.dopmer), ledger["inputs"][DOPMER_PATH])
        self.assertIn("tests/gameplay_routes_baldurs_gate.py", ledger["inputs"])
        no_routes = buildLedger(*self.dopmerInputs(), dopmer=self.dopmer)
        self.assertFalse(
            any(
                ".py:" in callback
                for callback in self.dopmerRows(no_routes)["DOPMER.DLG#state0"]["implementation"]["callbacks"]
            )
        )

    def testDopmerProofPointersAndPendingEvidenceCannotBeForged(self):
        source, quests, config, script = self.dopmerInputs()
        ledger = buildLedger(source, quests, config, script, dopmer=self.dopmer)
        self.assertIn("DOPMER.DLG#state0", self.dopmerRows(ledger))
        fixtures = {DOPMER_PATH: self.dopmer, "tests/fixtures/baldurs_gate_city_source.json": source}
        for row in self.dopmerRows(ledger).values():
            for proof in row["evidence"]:
                value = fixtures[proof["fixture"]]
                for part in proof["pointer"].lstrip("/").split("/"):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                self.assertIsNotNone(value)
        for damage in ("input", "fixture", "native", "coverage"):
            result = copy.deepcopy(ledger)
            row = next(row for row in result["entries"] if row["id"] == "DOPMER.DLG#state0")
            if damage == "input":
                del result["inputs"][DOPMER_PATH]
            elif damage == "fixture":
                row["evidence"][0]["fixture"] = "unknown.json"
            else:
                row["testStatus"][damage] = "passed"
            self.assertTrue(validateLedger(result), damage)

    def testDopmerMainOptionallyLoadsFixtureAndRoutesWithoutWritingLedger(self):
        import contextlib
        import io
        import tempfile
        from unittest.mock import patch
        import scripts.build_baldurs_gate_city_ledger as generator

        source, quests, config, script = self.dopmerInputs()
        routes = "def sevenSunsMerchantRoute(): pass\n"
        expected = buildLedger(
            self.full_source, quests, config, script, dopmer=self.dopmer, routes=routes, stock=self.stock
        )
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for path, content in (
                (generator.SCRIPT_PATH, script),
                (DOPMER_PATH, "{}"),
                (STOCK_PATH, "{}"),
                ("tests/gameplay_routes_baldurs_gate.py", routes),
                (generator.OUTPUT_PATH, "{}"),
            ):
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8")
            values = {
                generator.SOURCE_PATH: self.full_source,
                generator.QUEST_PATH: quests,
                generator.CONFIG_PATH: config,
                DOPMER_PATH: self.dopmer,
                STOCK_PATH: self.stock,
                generator.OUTPUT_PATH: expected,
            }
            calls = []
            actual_builder = buildLedger

            def capture(*args, **kwargs):
                calls.append(kwargs)
                return actual_builder(*args, **kwargs)

            with patch.object(generator, "ROOT", root), patch.object(
                generator, "readJson", side_effect=lambda path: values[path.relative_to(root).as_posix()]
            ), patch.object(generator, "buildLedger", side_effect=capture), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, generator.main(["--check"]))
            self.assertEqual("{}", (root / generator.OUTPUT_PATH).read_text(encoding="utf-8"))
            self.assertEqual(self.dopmer, calls[0].get("dopmer"))
            self.assertEqual(routes, calls[0].get("routes"))
            self.assertEqual(self.stock, calls[0].get("stock"))

    def testDopmerStockAddsOnlyThreeMissingItemsAndPreservesAll7500OldRows(self):
        original = buildLedger(self.full_source, self.full_quests, {}, "", warning=self.warning)
        updated = buildLedger(
            self.full_source, self.full_quests, {}, "", warning=self.warning, dopmer=self.dopmer, stock=self.stock
        )
        before = {row["id"]: row for row in original["entries"]}
        after = {row["id"]: row for row in updated["entries"]}
        self.assertEqual(7551, len(after))
        self.assertEqual(before, {key: after[key] for key in before})
        self.assertEqual(
            expectedIds(self.full_source, self.full_quests, self.warning, self.dopmer, self.stock), set(after)
        )
        new_items = {key for key in after.keys() - before.keys() if after[key]["family"] == "itemBehavior"}
        self.assertEqual({"BOLT05:item", "SCRL1J:item", "SCRL2I:item"}, new_items)
        self.assertEqual([], validateLedger(updated))
        self.assertFalse(updated["acceptanceReady"])
        for key in new_items:
            self.assertEqual("planned", after[key]["implementation"]["status"])
            self.assertEqual("pending", after[key]["testStatus"]["native"])
            self.assertEqual("not established", after[key]["testStatus"]["coverage"])

    def testDopmerStockMapsOwnershipOnlyAndRetains97AbilityGapsAndBaseFacts(self):
        config = {}
        for code in ("BOLT05", "SCRL1J", "SCRL2I"):
            item = self.stock["items"][code]
            config[item["resourceId"]] = {
                "class": "CItem",
                "properties": {
                    "plugin_citySourceItem": code,
                    "plugin_citySourceItemFingerprint": item["baseSha256"],
                    "plugin_cityAbilitiesPending": True,
                },
            }
        ledger = buildLedger(self.full_source, self.full_quests, config, "", stock=self.stock)
        rows = {row["id"]: row for row in ledger["entries"]}
        for code in ("BOLT05", "SCRL1J", "SCRL2I"):
            key = code + ":item"
            self.assertTrue(key in rows)
            row = rows[key]
            self.assertEqual("partial", row["implementation"]["status"])
            self.assertEqual(self.stock["items"][code]["headerEvidence"], row["facts"]["headerEvidence"])
            self.assertFalse(row["effects"]["sourceAbilitiesInterpreted"])
            self.assertTrue(row["ownership"]["sourceAbilitiesRemainPending"])
            self.assertEqual("pending", row["testStatus"]["native"])
            proof = row["evidence"][0]
            self.assertEqual(STOCK_PATH, proof["fixture"])
            self.assertEqual(self.stock["items"][code]["baseSha256"], proof["sha256"])
        combined = buildLedger(self.full_source, self.full_quests, {}, "", dopmer=self.dopmer, stock=self.stock)
        self.assertIn("DOPPSS.CRE#stock:RNDTRE05", self.dopmerRows(combined))
        facts = self.dopmerRows(combined)["DOPPSS.CRE#stock:RNDTRE05"]["facts"]["finiteNativeConversion"]
        self.assertEqual(97, len(facts["concreteItems"]))
        self.assertEqual(17, len(facts["effectiveOverridesExcluded"]))
        self.assertFalse(facts["abilitiesEstablished"])
        self.assertFalse(facts["sourceDiceRuleEstablished"])
        self.assertEqual(self.stock["rows"], facts["selectionRows"])
        self.assertEqual(fingerprint(self.stock), combined["inputs"][STOCK_PATH])
        fixtures = {
            DOPMER_PATH: self.dopmer,
            STOCK_PATH: self.stock,
            "tests/fixtures/baldurs_gate_city_source.json": self.full_source,
        }
        selected_rows = list(self.dopmerRows(combined).values()) + [
            rows[code + ":item"] for code in ("BOLT05", "SCRL1J", "SCRL2I")
        ]
        for row in selected_rows:
            for proof in row["evidence"]:
                value = fixtures[proof["fixture"]]
                for part in proof["pointer"].lstrip("/").split("/"):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                self.assertIsNotNone(value)
        self.assertEqual(
            {"weapon": 1, "metadataOnly": True, "immunityOrBonusEstablished": False}, facts["sourceEnchantment"]
        )

        broken = copy.deepcopy(ledger)
        del broken["inputs"][STOCK_PATH]
        self.assertTrue(any("stock input fingerprint" in problem for problem in validateLedger(broken)))

    def testDopmerStockRejectsDroppedSourcesWrongPinsAndAbilityOrOriginalCredit(self):
        for damage in ("dropped", "sourceMismatch", "basePin", "charges", "effects", "dice", "abilities", "original"):
            with self.subTest(damage=damage):
                source, stock = copy.deepcopy(self.full_source), copy.deepcopy(self.stock)
                if damage == "dropped":
                    del stock["items"]["SCRL1J"]
                elif damage == "sourceMismatch":
                    source["items"]["WAND05"]["sha256"] = "f" * 64
                elif damage == "basePin":
                    stock["items"]["BOLT05"]["baseSha256"] = "f" * 64
                elif damage == "charges":
                    stock["items"]["WAND05"]["charges"] = [10, 10, 0]
                elif damage == "effects":
                    stock["items"]["BOLT05"]["abilityEffectCounts"] = [0]
                elif damage == "dice":
                    stock["sourceDiceRuleEstablished"] = True
                elif damage == "abilities":
                    stock["itemAbilitiesEstablished"] = True
                else:
                    stock["originalParity"] = True
                with self.assertRaises(ValueError):
                    buildLedger(source, self.full_quests, {}, "", stock=stock)


class BaldursGateCityLedgerFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = readJson(ROOT / "tests/fixtures/baldurs_gate_city_source.json")
        cls.quests = readJson(ROOT / "tests/fixtures/baldurs_gate_city_quests.json")
        cls.config = readJson(ROOT / "res/maps/baldursGate/config.json")
        cls.script = (ROOT / "res/maps/baldursGate/script.py").read_text(encoding="utf-8")
        cls.ledger = readJson(ROOT / "tests/fixtures/baldurs_gate_city_ledger.json")
        cls.warning = readJson(ROOT / WARNING_PATH) if (ROOT / WARNING_PATH).is_file() else None
        cls.dopmer = readJson(ROOT / DOPMER_PATH) if (ROOT / DOPMER_PATH).is_file() else None
        cls.stock = readJson(ROOT / STOCK_PATH) if (ROOT / STOCK_PATH).is_file() else None
        cls.routes = (
            (ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8")
            if cls.dopmer is not None
            else None
        )
        cls.expected = buildLedger(
            cls.source,
            cls.quests,
            cls.config,
            cls.script,
            warning=cls.warning,
            dopmer=cls.dopmer,
            routes=cls.routes,
            stock=cls.stock,
        )

    def testSavedLedgerCoversEverySourceObligationAndMatchesCurrentInputs(self):
        self.assertEqual(
            expectedIds(self.source, self.quests, self.warning, self.dopmer, self.stock),
            {row["id"] for row in self.ledger["entries"]},
        )
        self.assertEqual([], validateLedger(self.ledger, expected=self.expected))
        self.assertEqual(212, len(self.source["areas"]))
        self.assertGreater(len(self.ledger["entries"]), 7000)

    def testEveryEvidencePointerResolvesAndFingerprintIsAvailable(self):
        fixtures = {
            "tests/fixtures/baldurs_gate_city_source.json": self.source,
            "tests/fixtures/baldurs_gate_city_quests.json": self.quests,
            **({WARNING_PATH: self.warning} if self.warning is not None else {}),
            **({DOPMER_PATH: self.dopmer} if self.dopmer is not None else {}),
            **({STOCK_PATH: self.stock} if self.stock is not None else {}),
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
