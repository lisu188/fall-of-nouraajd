# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tiny source-contract checks only; no native module, runtime or city generator."""

from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import audit_baldurs_gate_palace_listener_closure as audit
from scripts import baldurs_gate_palace_listener_closure_contract as review

HERE = Path(__file__).resolve().parent
PROJECT = Path(__file__).resolve().parents[1]


class PalaceListenerClosureEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = (HERE / "fixtures" / review.REVIEWED_FILENAME).read_bytes()
        cls.evidence = json.loads(cls.payload)
        cls.fixtures = {
            name: (PROJECT / "tests" / "fixtures" / name).read_bytes()
            for name in ("baldurs_gate_palace_scene_audit.json", "baldurs_gate_city_palace_shout.json")
        }

    def assertMutationRejected(self, evidence):
        with self.assertRaisesRegex(ValueError, "Unreviewed"):
            review.validateReview(json.dumps(evidence).encode("utf8"), self.fixtures)

    def testReviewedCanonicalHelpersMatchDeliveredSource(self):
        actual = {
            name: audit.sourceTextFingerprint((PROJECT / "scripts" / name).read_bytes())
            for name in self.evidence["sourceHelpers"]
        }
        self.assertEqual(self.evidence["sourceHelpers"], actual)

    def testReviewedClosure(self):
        result = review.validateReview(self.payload, self.fixtures)
        self.assertEqual(result["counts"], review.EXPECTED_COUNTS)
        self.assertFalse(result["scriptSchedulingResolved"])
        self.assertTrue(all(value is False for value in result["acceptance"].values()))
        self.assertEqual(len(result["candidateListenerSourceIds"]), 4)

    def testAcceptanceCannotBeExpanded(self):
        value = deepcopy(self.evidence)
        value["acceptance"]["originalAcceptanceReady"] = True
        self.assertMutationRejected(value)

    def testLiveMutantsCannotBeDropped(self):
        value = deepcopy(self.evidence)
        del value["creatures"]["GDOPP7"]
        self.assertMutationRejected(value)

    def testGuardEnemyCannotBeErased(self):
        value = deepcopy(self.evidence)
        value["preemptionAndBehavior3Facts"]["FLAM10"]["actions"] = []
        self.assertMutationRejected(value)

    def testMutantSourceAllegianceCannotStayEnemy(self):
        value = deepcopy(self.evidence)
        value["preemptionAndBehavior3Facts"]["SARDOPP"]["behavior3AllegianceBlock"]["actions"][0]["integers"][0] = 255
        self.assertMutationRejected(value)

    def testHeard50CannotRebroadcast(self):
        value = deepcopy(self.evidence)
        value["selectedHeard2And50Blocks"]["SARRUN.BCS#block2"]["actions"][0]["operation"] = "Shout"
        self.assertMutationRejected(value)

    def testChangedOriginalFixtureRejected(self):
        fixtures = dict(self.fixtures)
        name = "baldurs_gate_palace_scene_audit.json"
        fixtures[name] = fixtures[name][:-1] + b" "
        with self.assertRaisesRegex(ValueError, "fixture digest mismatch"):
            review.validateReview(self.payload, fixtures)

    def testLogicalEvidenceWithoutDigest(self):
        self.assertTrue(review.validateLogicalEvidence(self.evidence))

    def testNamedSlotPrecedenceAndExplicitNoneSuppressor(self):
        area = {slot: "" for slot in review.ARE_SLOTS}
        creature = dict(zip(review.CRE_SLOTS, ("SHOUT", "FLAM10", "SEEENEMY", "NONE", "WDASIGHT")))
        area["class"] = "FLAM10A"
        selected = review.selectedSlots(area, creature)
        self.assertEqual(selected["class"], {"resource": "FLAM10A", "origin": "area"})
        self.assertEqual(selected["override"], {"resource": "SHOUT", "origin": "creature"})
        area["override"] = "NONE"
        self.assertEqual(review.selectedSlots(area, creature)["override"], {"resource": "", "origin": "area"})

    def testLogicalSlotMutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        row = value["areaActors"][3]
        row["areaScripts"]["override"] = row["areaScripts"]["class"]
        row["areaScripts"]["class"] = ""
        with self.assertRaisesRegex(ValueError, "ARE physical slot"):
            review.validateLogicalEvidence(value)

    def testLogicalPrecedenceMutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["areaActors"][3]["selectedScriptsBySlot"]["override"]["resource"] = "FLAM10A"
        with self.assertRaisesRegex(ValueError, "slot precedence"):
            review.validateLogicalEvidence(value)

    def testLogicalGuardConditionMutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["preemptionAndBehavior3Facts"]["FLAM10"]["conditions"][1]["integers"][0] = 0
        with self.assertRaisesRegex(ValueError, "integer arguments"):
            review.validateLogicalEvidence(value)

    def testLogicalForeignRecordOwnershipRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["preemptionAndBehavior3Facts"]["FLAM10"]["conditions"][1]["sourceId"] = "FLAM10A.BCS#offset69"
        with self.assertRaisesRegex(ValueError, "record ownership"):
            review.validateLogicalEvidence(value)

    def testLogicalMissingTransitiveDependencyRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        del value["sourceHelpers"]["build_baldurs_gate_source_fixture.py"]
        with self.assertRaisesRegex(ValueError, "dependency inventory"):
            review.validateLogicalEvidence(value)

    def testHelperFingerprintIsIndependentOfCheckoutLineEndings(self):
        self.assertEqual(
            audit.sourceTextFingerprint(b"line1\nline2\n"), audit.sourceTextFingerprint(b"line1\r\nline2\r\n")
        )
        self.assertNotEqual(
            audit.sourceTextFingerprint(b"line1\nline2\n"), audit.sourceTextFingerprint(b"line1\nchanged\n")
        )

    def testResourceOriginsAreIndependentOfHostSeparators(self):
        expected = {"source": "override", "path": "override\\SAREVO.ITM"}
        self.assertEqual(
            audit.canonicalOrigin(expected),
            audit.canonicalOrigin({"source": "override", "path": "override/SAREVO.ITM"}),
        )
        self.assertEqual(expected, audit.canonicalOrigin(expected))

    def testUnreviewedOutputIsNotWritten(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder = Path(temporary).resolve()
            self.assertTrue(folder.is_relative_to(HERE))
            reviewed = folder / "reviewed.json"
            reviewed.write_bytes(b"{}")
            output = folder / "new.json"
            with patch.object(audit, "buildEvidence", return_value=self.evidence):
                with self.assertRaisesRegex(ValueError, "differs from reviewed"):
                    audit.main(
                        [
                            "--game-root",
                            str(folder),
                            "--project-root",
                            str(PROJECT),
                            "--reviewed-evidence",
                            str(reviewed),
                            "--output",
                            str(output),
                        ]
                    )
            self.assertFalse(output.exists())

    def testOverBudgetMetadataIsRejectedBeforeOptionalWrite(self):
        value = deepcopy(self.evidence)
        value["unresolvedBoundaries"].append("x" * audit.MAX_OUTPUT_BYTES)
        acceptance = deepcopy(value["acceptance"])
        with self.assertRaisesRegex(ValueError, "metadata output exceeded limit"):
            audit.evidenceBytes(value)
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder = Path(temporary).resolve()
            self.assertTrue(folder.is_relative_to(HERE))
            output = folder / "over-budget.json"
            with patch.object(audit, "buildEvidence", return_value=value):
                with self.assertRaisesRegex(ValueError, "metadata output exceeded limit"):
                    audit.main(
                        [
                            "--game-root",
                            str(folder),
                            "--project-root",
                            str(PROJECT),
                            "--reviewed-evidence",
                            str(HERE / "fixtures" / review.REVIEWED_FILENAME),
                            "--output",
                            str(output),
                        ]
                    )
            self.assertFalse(output.exists())
        self.assertEqual(acceptance, value["acceptance"])
        self.assertTrue(all(flag is False for flag in value["acceptance"].values()))

    def testExistingOutputIsNotOverwritten(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder = Path(temporary).resolve()
            self.assertTrue(folder.is_relative_to(HERE))
            output = folder / "existing.json"
            output.write_bytes(b"retained")
            with patch.object(audit, "buildEvidence", return_value=self.evidence):
                with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                    audit.main(
                        [
                            "--game-root",
                            str(folder),
                            "--project-root",
                            str(PROJECT),
                            "--reviewed-evidence",
                            str(HERE / "fixtures" / review.REVIEWED_FILENAME),
                            "--output",
                            str(output),
                        ]
                    )
            self.assertEqual(b"retained", output.read_bytes())

    def testOutputRaceCannotOverwriteRetainedEvidence(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder = Path(temporary).resolve()
            self.assertTrue(folder.is_relative_to(HERE))
            output = folder / "appeared-during-check.json"
            retained = b"retained evidence from another writer"
            output.write_bytes(retained)
            original_exists = Path.exists

            def racedExists(path):
                return False if path == output else original_exists(path)

            with patch.object(audit, "buildEvidence", return_value=self.evidence):
                with patch.object(Path, "exists", racedExists):
                    with self.assertRaises(FileExistsError):
                        audit.main(
                            [
                                "--game-root",
                                str(folder),
                                "--project-root",
                                str(PROJECT),
                                "--reviewed-evidence",
                                str(HERE / "fixtures" / review.REVIEWED_FILENAME),
                                "--output",
                                str(output),
                            ]
                        )
            self.assertEqual(retained, output.read_bytes())

    def testChangedFixtureRejectedBeforeExpandingItsResourcePins(self):
        calls = []

        def read(name, ext, view):
            calls.append((name, ext, view))
            return b"", {"source": "mock"}

        index = types.SimpleNamespace(key_hash=self.evidence["keySha256"], overrides={}, read=read)
        source = types.SimpleNamespace(ResourceIndex=lambda path: index, parseIds=lambda data: {})
        modules = {
            "audit_candlekeep_source": source,
            "audit_baldurs_gate_palace": object(),
            "audit_baldurs_gate_palace_shout": object(),
        }
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder = Path(temporary).resolve()
            self.assertTrue(folder.is_relative_to(HERE))
            fixtures = folder / "tests" / "fixtures"
            fixtures.mkdir(parents=True)
            (fixtures / "baldurs_gate_city_palace_shout.json").write_bytes(b"unreviewed")
            with self.assertRaisesRegex(ValueError, "Unreviewed source fixture"):
                audit.buildWithHelpers(folder, folder, modules)
        self.assertEqual({"ACTION", "TRIGGER", "EA", "OBJECT"}, {row[0] for row in calls})
        self.assertTrue(all(row[1] == "IDS" for row in calls))

    def testPrivateImportsAreFreshAndLeaveNoBytecodeOrGlobalAliases(self):
        before_modules = set(sys.modules)
        before_path = list(sys.path)
        before_bytecode = sys.dont_write_bytecode
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            root = Path(temporary).resolve()
            self.assertTrue(root.is_relative_to(HERE))
            folder = root / "scripts"
            folder.mkdir()
            for value in ("first", "second"):
                for name in audit.SOURCE_HELPERS:
                    (folder / (name + ".py")).write_text("VALUE = " + repr(value) + "\n", encoding="utf8")
                with audit.loadSourceHelpers(root) as modules:
                    self.assertEqual({value}, {module.VALUE for module in modules.values()})
                self.assertFalse((folder / "__pycache__").exists())
        self.assertEqual(before_path, sys.path)
        self.assertEqual(before_bytecode, sys.dont_write_bytecode)
        self.assertEqual(
            set(),
            {name for name in set(sys.modules) - before_modules if name.startswith("_palaceListenerAuditSources_")},
        )

    def testLogicalNobleSpecificSlotMutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["areaActors"][6]["areaScripts"]["specific"] = ""
        value["areaActors"][6]["areaScripts"]["override"] = "SARRUN"
        with self.assertRaisesRegex(ValueError, "ARE physical slot"):
            review.validateLogicalEvidence(value)

    def testLogicalNobleEarlierConditionMutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["preemptionAndBehavior3Facts"]["SARRUN"]["conditions"][0]["integers"][0] = 0
        with self.assertRaisesRegex(ValueError, "integer arguments"):
            review.validateLogicalEvidence(value)

    def testLogicalCrossguardSummaryMutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["higherAndFallbackScriptCrossguards"]["blocks"]["SHOUT"][0]["actions"][0]["operation"] = "Continue"
        with self.assertRaisesRegex(ValueError, "Crossguard operation summary"):
            review.validateLogicalEvidence(value)

    def testLogicalHeardInventoryMutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["scripts"]["SARRUN"]["heard"][0]["negated"] = True
        with self.assertRaisesRegex(ValueError, "condition/inventory cross-binding"):
            review.validateLogicalEvidence(value)

    def testLogicalHeard50RebroadcastRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["selectedHeard2And50Blocks"]["SARRUN.BCS#block2"]["actions"][0]["operation"] = "Shout"
        with self.assertRaisesRegex(ValueError, "operation/offset"):
            review.validateLogicalEvidence(value)

    def testLogicalMutantEA28MutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["preemptionAndBehavior3Facts"]["SARDOPP"]["behavior3AllegianceBlock"]["actions"][0]["integers"][0] = 255
        with self.assertRaisesRegex(ValueError, "integer arguments"):
            review.validateLogicalEvidence(value)

    def testLogicalWeightMutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["preemptionAndBehavior3Facts"]["SARDOPP"]["behavior3WeightedResponses"][0]["weight"] = 25
        with self.assertRaisesRegex(ValueError, "Weighted response"):
            review.validateLogicalEvidence(value)

    def testLogicalWeightedTargetMutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["preemptionAndBehavior3Facts"]["SARDOPP"]["behavior3WeightedResponses"][1]["actions"][0]["selectors"][1][
            "ids"
        ][8] = 1
        with self.assertRaisesRegex(ValueError, "Weighted attack target"):
            review.validateLogicalEvidence(value)

    def testLogicalSelfSummaryMutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["scripts"]["SARRUN"]["operationCounts"]["Heard"] = 3
        with self.assertRaisesRegex(ValueError, "Record summary"):
            review.validateLogicalEvidence(value)

    def testLogicalCountsMutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["closureCounts"]["directActorBCS"] = 21
        with self.assertRaisesRegex(ValueError, "Logical closure counts"):
            review.validateLogicalEvidence(value)

    def testLogicalAcceptanceMutationRejectedWithoutDigest(self):
        value = deepcopy(self.evidence)
        value["acceptance"]["nativeImplementationReady"] = 0
        with self.assertRaisesRegex(ValueError, "exactly false"):
            review.validateLogicalEvidence(value)

    def testNoCompiledBodiesOrDialogueProseFields(self):
        def visit(value):
            if isinstance(value, dict):
                self.assertFalse({"compiled_text", "raw", "text", "replyText"}.intersection(value))
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(self.evidence)


if __name__ == "__main__":
    unittest.main()
