# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import history_source_prep as source_prep
from scripts import recovery_readme
from scripts import verify_history
from tests import test_recovery_readme as readme_tests


class LegacyTimingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nouraajd-timing-integration-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        shutil.copytree(Path(__file__).parent / "fixtures/history-timing-128", self.root)
        self.evidence = Path(self.temp.name) / "evidence"
        self.evidence.mkdir()
        self.fixture = readme_tests.RecoveryReadmeTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.report = copy.deepcopy(self.fixture.report)

    def prepare(self):
        self.assertTrue(source_prep.preparationRequired(self.root))
        preparation = source_prep.prepareSources(
            self.root,
            self.evidence / "steps",
            {"pythonAbi": "none"},
            {},
            lambda *args, **kwargs: self.fail("Legacy timing aliases need no external generator"),
        )
        self.report["sourcePreparation"] = preparation
        self.report["startupCompatibility"] = "legacyTimingResources"
        self.report["startupSelection"] = {"boundary": source_prep.timing_prep.BOUNDARY}
        self.report["recipe"]["qmakeArguments"] = ["QMAKE_CXXFLAGS+=-include functional"]
        self.writePreparation()
        return preparation

    def writePreparation(self):
        target = self.fixture.evidence
        preparation = self.report["sourcePreparation"]
        (target / "source-preparation.json").write_text(json.dumps(preparation))
        (target / "source-preparation.log").write_text("Created three exact legacy timing aliases\n")

    def testPreparationRecordsOnlyThreeNewFilesAndKeepsInputs(self):
        before = source_prep.sourceManifest(self.root)
        preparation = self.prepare()
        self.assertEqual(preparation["status"], "success")
        self.assertEqual([step["name"] for step in preparation["steps"]], ["legacyTimingResources"])
        self.assertEqual(source_prep.preparationArguments(self.root), [])
        self.assertNotIn("qmakeArguments", preparation)
        self.assertEqual(len(preparation["outputs"]), 3)
        after = source_prep.sourceManifest(self.root)
        self.assertEqual({name: after[name] for name in before}, before)
        for output in preparation["outputs"]:
            self.assertIsNone(output["before"])
            self.assertEqual(output["after"], after[output["path"]])
            self.assertIn("byte-identical", output["purpose"])

    def testUnmatchedOrdinarySnapshotStillNeedsNoPreparation(self):
        (self.root / "creatures.qrc").write_text("<RCC/>\n")
        self.assertFalse(source_prep.preparationRequired(self.root))
        preparation = source_prep.prepareSources(self.root, self.evidence, {}, {}, self.fail)
        self.assertEqual(preparation["status"], "not-required")
        self.assertEqual(preparation["outputs"], [])

    def testPortableReadmeReplaysAliasesWithExplicitBoundary(self):
        self.prepare()
        files = recovery_readme.snapshotDocumentation(self.report, self.fixture.evidence)
        self.assertEqual(
            files["recovery/prepare_legacy_timing.py"], Path(source_prep.timing_prep.__file__).read_bytes()
        )
        readme = files["README.md"].decode()
        self.assertIn("python3 recovery/prepare_legacy_timing.py", readme)
        self.assertIn("21 surviving bytes", readme)
        self.assertIn("animation timing", readme)
        self.assertIn("original", readme.lower())
        self.assertIn("qmake Game.pro 'QMAKE_CXXFLAGS+=-include functional'", readme)
        replay_root = Path(self.temp.name) / "portable"
        shutil.copytree(Path(__file__).parent / "fixtures/history-timing-128", replay_root)
        evidence = replay_root / "recovery"
        evidence.mkdir()
        for name, data in files.items():
            if name.startswith("recovery/"):
                (replay_root / name).write_bytes(data)
        self.assertTrue(source_prep.timing_prep.prepareLegacyTiming(replay_root, evidence))
        self.assertFalse(source_prep.timing_prep.prepareLegacyTiming(replay_root, evidence))

    def testReadmeRejectsMissingCompatibilityLabelAndChangedBoundary(self):
        self.prepare()
        del self.report["startupCompatibility"]
        with self.assertRaisesRegex(verify_history.VerificationError, "Legacy timing resources differ"):
            recovery_readme.snapshotDocumentation(self.report, self.fixture.evidence)
        self.report["startupCompatibility"] = "legacyTimingResources"
        self.report["startupSelection"]["boundary"] = "Authored startup"
        with self.assertRaisesRegex(verify_history.VerificationError, "Legacy timing resources differ"):
            recovery_readme.snapshotDocumentation(self.report, self.fixture.evidence)

    def testReadmeRejectsSelfConsistentOutputHashTampering(self):
        preparation = self.prepare()
        output = preparation["outputs"][0]
        output["after"]["sha256"] = hashlib.sha256(b"forged").hexdigest()
        self.writePreparation()
        with self.assertRaisesRegex(verify_history.VerificationError, "new-file preparation fingerprints"):
            recovery_readme.snapshotDocumentation(self.report, self.fixture.evidence)

    def testReadmeRejectsExtraOutputAndQmakeArgument(self):
        preparation = self.prepare()
        preparation["outputs"].append(
            {"path": "src/extra.h", "before": None, "after": {"kind": "file", "sha256": "0" * 64}}
        )
        self.writePreparation()
        with self.assertRaisesRegex(verify_history.VerificationError, "three reviewed aliases"):
            recovery_readme.snapshotDocumentation(self.report, self.fixture.evidence)
        preparation["outputs"].pop()
        preparation["qmakeArguments"] = ["RESOURCES-=creatures.qrc"]
        self.writePreparation()
        with self.assertRaisesRegex(verify_history.VerificationError, "Legacy timing resources differ"):
            recovery_readme.snapshotDocumentation(self.report, self.fixture.evidence)

    def testReadmeRejectsChangedInputAndReplayIdentity(self):
        preparation = self.prepare()
        identity = preparation["identity"]["legacyTimingResources"]
        for field in ["replaySha256", "validationBoundary"]:
            with self.subTest(field=field):
                original = identity[field]
                identity[field] = "changed"
                self.writePreparation()
                with self.assertRaisesRegex(verify_history.VerificationError, "Legacy timing resources differ"):
                    recovery_readme.snapshotDocumentation(self.report, self.fixture.evidence)
                identity[field] = original

    def testVerifierExportRefusesAlteredGeneratedAlias(self):
        self.prepare()
        (self.root / "images/monsters/pritz/time.txt").write_bytes(b"forged")
        result = {
            **self.report,
            "artifactDir": str(self.root),
            "restoration": {"outputDir": str(self.root)},
            "fingerprint": "a" * 64,
        }
        result["smoke"]["startupReport"] = str(self.fixture.evidence / "startup.json")
        with patch.object(verify_history, "validateSmokeReport", return_value=self.report["smoke"]["startup"]):
            with self.assertRaisesRegex(ValueError, "generated output differs"):
                verify_history.exportEvidence(result, self.evidence)


if __name__ == "__main__":
    unittest.main()
