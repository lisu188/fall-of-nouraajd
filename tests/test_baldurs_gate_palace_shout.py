# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure supplemental-source contract tests; no native, gameplay, or parity credit."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import audit_baldurs_gate_palace_shout as audit

FIXTURE = Path(__file__).parent / "fixtures" / "baldurs_gate_city_palace_shout.json"
PROJECT = Path(__file__).resolve().parents[1]
PALACE = PROJECT / "tests/fixtures/baldurs_gate_palace_scene_audit.json"


class PalaceShoutEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(FIXTURE.read_text(encoding="utf8"))
        cls.palace = json.loads(PALACE.read_text(encoding="utf8"))

    def contract(self, evidence=None, palace=None):
        return audit.compileShoutContract(
            self.evidence if evidence is None else evidence, self.palace if palace is None else palace
        )

    def testReviewedFactsMatchPinnedDigestWithoutAcceptanceCredit(self):
        self.assertEqual(audit.REVIEWED_EVIDENCE_SHA256, audit.digest(self.evidence))
        self.assertEqual(22, len(self.evidence["resourceFingerprints"]))
        self.assertEqual(12, len(self.evidence["scriptHearingInventory"]))
        contract = self.contract()
        self.assertEqual(11, len(contract["listenerObligations"]))
        self.assertEqual(audit.FALSE_ACCEPTANCE, contract["acceptance"])
        self.assertTrue(all(value is False for value in contract["acceptance"].values()))

    def testOriginal43ResourceManifestRemainsUnchangedAndIsCrossBound(self):
        before = deepcopy(self.palace)
        raw = PALACE.read_bytes()
        self.contract()
        self.assertEqual(before, self.palace)
        self.assertEqual(raw, PALACE.read_bytes())
        pins = self.palace["resourceFingerprints"]
        self.assertEqual(43, len(pins))
        self.assertEqual(audit.digest(pins), self.evidence["palaceManifest"]["sha256"])
        for resource in self.evidence["palaceManifest"]["overlapResources"]:
            self.assertEqual(pins[resource]["sha256"], self.evidence["resourceFingerprints"][resource]["sha256"])
            self.assertEqual(pins[resource]["bytes"], self.evidence["resourceFingerprints"][resource]["bytes"])
        self.assertNotIn("SARRUN.BCS", pins)
        self.assertIn("SARRUN.BCS", self.evidence["resourceFingerprints"])

    def testSourceEventIsActualSarevokShout2AndNotPlayerOrCustodyAngelo(self):
        row = self.contract()["sourceShout"]
        self.assertEqual("SAREVO.DLG#state8/transition9/action16", row["sourceId"])
        self.assertEqual({"op": "Shout", "args": [2]}, row["sourceAction"])
        self.assertEqual("SAREVO2", row["speakerCreature"])
        self.assertEqual("Sarevok", row["speakerDeathVariable"])
        self.assertEqual(
            [
                {"op": "Dead", "args": ["Liia"]},
                {"op": "Dead", "args": ["Belt"]},
                {"op": "AreaCheck", "args": ["AR0108"]},
                {"not": {"op": "Global", "args": ["SarevokBehavior", "GLOBAL", 3]}},
            ],
            row["sourceStateConditions"],
        )

    def testOriginalGuardsAttackSarevokWithoutBecomingSpawnedFlame(self):
        guards = [row for row in self.contract()["listenerObligations"] if row["actor"]["sourceCreature"] == "FLAM10"]
        self.assertEqual(6, len(guards))
        self.assertEqual(
            ["cityAr0108Actor" + str(n) for n in range(1, 7)], [r["actor"]["proposedNativeId"] for r in guards]
        )
        for row in guards:
            block = row["sourceBlock"]
            self.assertEqual(1, len(block["conditions"]))
            self.assertEqual("Heard", block["conditions"][0]["operation"])
            self.assertEqual(2, block["conditions"][0]["integers"][0])
            self.assertEqual("Sarevok", block["conditions"][0]["selectors"][0]["name"])
            self.assertEqual(["Attack"], [action["operation"] for action in block["actions"]])
            self.assertEqual("Sarevok", block["actions"][0]["selectors"][1]["name"])
            self.assertFalse(block["semanticsEvaluated"])

    def testAreaClassOverrideReplacesCorrectCreatureSlotForFourthGuardOnly(self):
        actors = self.evidence["areaActors"]
        self.assertEqual(
            ["SHOUT", "FLAM10", "SEEENEMY", "NONE", "WDASIGHT"], self.evidence["creatureScripts"]["FLAM10"]["scripts"]
        )
        for index, actor in enumerate(actors[:6]):
            slots = actor["selectedScriptsBySlot"]
            expected = "FLAM10A" if index == 3 else "FLAM10"
            self.assertEqual(expected, slots["class"]["resource"])
            self.assertEqual("area" if index == 3 else "creature", slots["class"]["origin"])
            self.assertEqual("SHOUT", slots["override"]["resource"])
            self.assertEqual("SEEENEMY", slots["race"]["resource"])
            self.assertEqual("", slots["general"]["resource"])
        special = actors[3]["shout2Listeners"]
        self.assertEqual([{"slot": "class", "script": "FLAM10A", "blockSourceId": "FLAM10A.BCS#block3"}], special)

    def testFiveOrdinaryNoblesUseSpecificAreaScriptAndShout50ThenEscape(self):
        nobles = self.contract()["listenerObligations"][6:]
        self.assertEqual(
            ["NOBW5", "NOBW5", "NOBL12", "NOBL12", "NOBL12"], [r["actor"]["sourceCreature"] for r in nobles]
        )
        for row in nobles:
            self.assertEqual(
                {"slot": "specific", "script": "SARRUN", "blockSourceId": "SARRUN.BCS#block1"}, row["listener"]
            )
            self.assertEqual(
                {"resource": "SARRUN", "origin": "area"}, row["actor"]["selectedScriptsBySlot"]["specific"]
            )
            block = row["sourceBlock"]
            self.assertEqual("SARRUN.BCS#offset235", block["conditions"][0]["sourceId"])
            self.assertEqual(["Shout", "EscapeArea"], [r["operation"] for r in block["actions"]])
            self.assertEqual(
                ["SARRUN.BCS#offset309", "SARRUN.BCS#offset430"], [r["sourceId"] for r in block["actions"]]
            )
            self.assertEqual(50, block["actions"][0]["integers"][0])

    def testNewEnforcersAreNotMisclassifiedAsOriginalShout2Listeners(self):
        rows = self.contract()["spawnedActorNonListeners"]
        self.assertEqual({"FLAME", "ANGELO"}, set(rows))
        for code, row in rows.items():
            self.assertEqual([], row["matchingHeard2"])
            source_scripts = sorted(
                {audit.scriptName(n) for n in self.evidence["creatureScripts"][code]["scripts"]} - {""}
            )
            self.assertEqual(source_scripts, row["referencedScripts"])
            for script in source_scripts:
                summary = self.evidence["scriptHearingInventory"][script]
                self.assertEqual(summary["operationCounts"].get("Heard", 0), len(summary["heardTriggers"]))
                self.assertFalse(any(r["integers"][0] == 2 for r in summary["heardTriggers"]))
        self.assertEqual(
            [99], sorted({r["integers"][0] for r in self.evidence["scriptHearingInventory"]["SHOUT"]["heardTriggers"]})
        )
        self.assertEqual(
            [111], [r["integers"][0] for r in self.evidence["scriptHearingInventory"]["WTASIGHT"]["heardTriggers"]]
        )

    def testBaseAndEffectiveSourcesAreSeparatelyFingerprinted(self):
        for name, row in self.evidence["resourceFingerprints"].items():
            self.assertEqual(64, len(row["sha256"]), name)
            self.assertEqual("key_biff", row["baseOrigin"]["source"])
            self.assertEqual(row["bytes"], row["baseOrigin"]["size"])
            self.assertEqual(row["sha256"] == row["effectiveSha256"], row["baseEqualsEffective"])
            self.assertIn(row["effectiveOrigin"]["source"], ("key_biff", "override"))
            self.assertEqual(row["overridePresent"], row["effectiveOrigin"]["source"] == "override")

    def testRadiusDocumentationKeepsEditionsAndNativeConversionSeparate(self):
        radius = self.contract()["documentedRadiusEvidence"]
        self.assertEqual((448, 28), (radius["BG1"]["pixels"], radius["BG1"]["feet"]))
        self.assertEqual(
            (1.5, 672, 42),
            (radius["BGEE"]["visualRangeMultiplier"], radius["BGEE"]["defaultPixels"], radius["BGEE"]["defaultFeet"]),
        )
        self.assertFalse(radius["installedRadiusAudited"])
        self.assertIsNone(radius["nativeRadiusConversion"])
        self.assertTrue(any("Shout50" in row for row in self.evidence["limitations"]))

    def testFunctionalFactAndCrossBindingMutationsFailClosed(self):
        mutations = {
            "guardTarget": lambda e: e["selectedListenerBlocks"]["FLAM10"]["actions"][0]["selectors"][1].update(
                name="Player1"
            ),
            "guardOperation": lambda e: e["selectedListenerBlocks"]["FLAM10A"]["actions"][0].update(operation="Enemy"),
            "nobleShout": lambda e: e["selectedListenerBlocks"]["SARRUN"]["actions"][0]["integers"].__setitem__(0, 2),
            "nobleOrder": lambda e: e["selectedListenerBlocks"]["SARRUN"]["actions"].reverse(),
            "overrideSlot": lambda e: e["areaActors"][3]["areaScripts"].__setitem__(2, "FLAM10"),
            "guardIdentity": lambda e: e["areaActors"][0].update(sourceCreature="FLAME"),
            "duplicateActor": lambda e: e["areaActors"][1].update(sourceId=e["areaActors"][0]["sourceId"]),
            "missingActor": lambda e: e["areaActors"].pop(),
            "fakeFingerprint": lambda e: e["resourceFingerprints"]["SARRUN.BCS"].update(sha256="0" * 64),
            "missingFingerprint": lambda e: e["resourceFingerprints"].pop("SARRUN.BCS"),
            "falseAbsence": lambda e: e["spawnedActorNonListeners"]["FLAME"].update(matchingHeard2=[{}]),
            "incompleteInventory": lambda e: e["scriptHearingInventory"]["SHOUT"]["heardTriggers"].pop(),
            "wrongSpeaker": lambda e: e["sourceShout"].update(speakerCreature="SAREVO"),
            "wrongShoutAction": lambda e: e["sourceShout"].update(sourceId="SAREVO.DLG#state8/transition9/action17"),
            "classicRadiusReplaced": lambda e: e["documentedRadiusEvidence"]["BG1"].update(pixels=672),
            "readiness": lambda e: e["acceptance"].update(nativeImplementationReady=True),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                evidence = deepcopy(self.evidence)
                mutate(evidence)
                with self.assertRaisesRegex(ValueError, "Unreviewed supplemental"):
                    self.contract(evidence=evidence)

    def testSynchronizedSummariesCannotForgeReviewedSourceAuthority(self):
        evidence = deepcopy(self.evidence)
        actor = evidence["areaActors"][3]
        actor["areaScripts"][2] = "FLAM10"
        actor["selectedScriptsBySlot"] = audit.sourceScripts(
            actor["areaScripts"], evidence["creatureScripts"]["FLAM10"]["scripts"]
        )
        actor["shout2Listeners"] = [{"slot": "class", "script": "FLAM10", "blockSourceId": "FLAM10.BCS#block2"}]
        evidence["resourceFingerprints"]["AR0108.ARE"]["sha256"] = "1" * 64
        with self.assertRaisesRegex(ValueError, "Unreviewed supplemental"):
            self.contract(evidence=evidence)

    def testChangedOriginalManifestKeyOrNonoverlappingPinIsRejected(self):
        for mutation in ("key", "newPin", "removePin", "unrelatedPin", "overlappingPin"):
            with self.subTest(mutation=mutation):
                palace = deepcopy(self.palace)
                pins = palace["resourceFingerprints"]
                if mutation == "key":
                    palace["keySha256"] = "0" * 64
                elif mutation == "newPin":
                    pins["SARRUN.BCS"] = {"bytes": 765, "sha256": "0" * 64}
                elif mutation == "removePin":
                    pins.pop("BELT.DLG")
                else:
                    pins["BELT.DLG" if mutation == "unrelatedPin" else "FLAM10.BCS"]["sha256"] = "0" * 64
                with self.assertRaisesRegex(ValueError, "manifest|fingerprints|KEY"):
                    self.contract(palace=palace)

    def testContradictoryPalaceSpeakerAndFailureSummariesCannotPassWithUnchangedFingerprints(self):
        for mutation in ("speaker", "shout", "entryConditions"):
            with self.subTest(mutation=mutation):
                palace = deepcopy(self.palace)
                if mutation == "speaker":
                    palace["identities"]["SAREVO2"]["deathVariable"] = "TempleSarevok"
                else:
                    state = palace["sceneFacts"]["failureTransitions"]["bothDukesDead"]
                    if mutation == "shout":
                        state["edges"][0]["actions"][16]["args"] = [99]
                    else:
                        state["entryConditions"] = []
                with self.assertRaisesRegex(ValueError, "cross-binding|speaker|summary"):
                    self.contract(palace=palace)

    def testReturnedContractIsDetachedAndDeterministic(self):
        before = deepcopy(self.evidence)
        first = self.contract()
        second = self.contract()
        self.assertEqual(first, second)
        first["listenerObligations"][0]["sourceBlock"]["actions"][0]["selectors"][1]["name"] = "forged"
        first["listenerObligations"][1]["actor"]["sourcePosition"][0] = 0
        self.assertEqual(before, self.evidence)
        self.assertEqual(second, self.contract())
        self.assertEqual(
            "Sarevok", first["listenerObligations"][1]["sourceBlock"]["actions"][0]["selectors"][1]["name"]
        )

    def testEvidenceIsBoundedFactsWithoutOriginalScriptOrDialogueDumps(self):
        self.assertLessEqual(FIXTURE.stat().st_size, audit.MAX_OUTPUT_BYTES)

        def inspect(value):
            if isinstance(value, dict):
                self.assertTrue({"compiled_text", "raw", "text_strref", "text", "dialogueText"}.isdisjoint(value))
                for child in value.values():
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)

        inspect(self.evidence)

    def testScriptSlotsHandleDifferentOrdersAndExplicitAreaNoneWithoutFallback(self):
        creature = ["OVERRIDE", "CLASS", "RACE", "GENERAL", "DEFAULT"]
        result = audit.sourceScripts(["", "AREA_GENERAL", "", "", "", "AREA_SPECIFIC"], creature)
        self.assertEqual({"resource": "CLASS", "origin": "creature"}, result["class"])
        self.assertEqual({"resource": "AREA_GENERAL", "origin": "area"}, result["general"])
        self.assertEqual({"resource": "AREA_SPECIFIC", "origin": "area"}, result["specific"])
        cleared = audit.sourceScripts(["NONE", "", "", "", "", ""], creature)
        self.assertEqual({"resource": "", "origin": "area"}, cleared["override"])
        self.assertEqual({"resource": "", "origin": "none"}, cleared["specific"])
        with self.assertRaisesRegex(ValueError, "slot-width|slot width"):
            audit.sourceScripts([""] * 5, creature)

    def testCliRefusesOverwriteAndOutputCapWithoutWritingArtifacts(self):
        original = FIXTURE.read_bytes()
        args = [
            "--game-root",
            "unused",
            "--project-root",
            str(PROJECT),
            "--palace-audit",
            str(PALACE),
            "--output",
            str(FIXTURE),
        ]
        with patch.object(audit, "buildEvidence", return_value=deepcopy(self.evidence)):
            with self.assertRaisesRegex(ValueError, "overwrite"):
                audit.main(args)
            with patch.object(audit, "MAX_OUTPUT_BYTES", 10):
                with self.assertRaisesRegex(ValueError, "cap"):
                    audit.main(args)
        self.assertEqual(original, FIXTURE.read_bytes())

    def testOutputRaceCannotOverwriteRetainedEvidence(self):
        with tempfile.TemporaryDirectory(prefix="palace-shout-output-") as directory:
            output = Path(directory) / "retained.json"
            retained = b"retained evidence\n"
            output.write_bytes(retained)
            original_exists = Path.exists

            def racedExists(path):
                return False if path == output else original_exists(path)

            args = [
                "--game-root",
                "unused",
                "--project-root",
                str(PROJECT),
                "--palace-audit",
                str(PALACE),
                "--output",
                str(output),
            ]
            with patch.object(audit, "buildEvidence", return_value=deepcopy(self.evidence)):
                with patch.object(Path, "exists", racedExists):
                    with self.assertRaises(FileExistsError):
                        audit.main(args)
            self.assertEqual(retained, output.read_bytes())


if __name__ == "__main__":
    unittest.main()
