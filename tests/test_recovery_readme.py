# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
import hashlib
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

from scripts.recovery_readme import snapshotDocumentation
from scripts import history_source_prep
from scripts.verify_history import EDITOR_CHECKS, REQUIRED_CHECKS, VerificationError
from tests.test_history_smoke import pngBytes


class RecoveryReadmeTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.evidence = Path(temporary.name)
        startup = {
            "schemaVersion": 1,
            "status": "ready",
            "checks": {name: True for name in REQUIRED_CHECKS},
            "frame": {
                "path": "/original/build/startup.png",
                "width": 2,
                "height": 1,
                "sha256": hashlib.sha256(pngBytes()).hexdigest(),
            },
        }
        self.report = {
            "sourceCommit": "a" * 40,
            "sourceTree": "b" * 40,
            "status": "success",
            "restoration": {
                "sourceCommit": "a" * 40,
                "sourceTree": "b" * 40,
                "status": "complete",
                "unresolved": [],
                "restoredFilesFingerprint": "c" * 64,
                "restored": [{"path": "map.cpp", "method": "reconstruction", "provenance": "Header-based recovery"}],
            },
            "configure": {"command": ["qmake", "/original/Game.pro"], "returnCode": 0, "timedOut": False},
            "build": {"command": ["make", "-j8"], "returnCode": 0, "timedOut": False},
            "smoke": {
                "command": ["xvfb-run", "-a", "--server-args=-screen 0 1920x1080x24", "Game"],
                "status": "success",
                "returnCode": 0,
                "timedOut": False,
                "startup": startup,
            },
            "toolchain": {
                "qmakeCommand": {"version": "QMake version 3.1\nUsing Qt 5.15"},
                "compilerCommand": {"version": "g++ 15.2"},
            },
            "recipe": {"pythonAbi": "none"},
        }
        (self.evidence / "startup.json").write_text(json.dumps(startup))
        (self.evidence / "startup.png").write_bytes(pngBytes())

    def testVerifiedSnapshotGetsActualImageAndPortableLinks(self):
        files = snapshotDocumentation(self.report, self.evidence)
        self.assertEqual({"README.md", "recovery/startup.png", "recovery/verification.json"}, set(files))
        self.assertIn(b"![Actual startup", files["README.md"])
        self.assertIn(b"qmake Game.pro", files["README.md"])
        self.assertIn(b"Header-based recovery", files["README.md"])
        self.assertEqual(pngBytes(), files["recovery/startup.png"])
        metadata = json.loads(files["recovery/verification.json"])
        self.assertEqual("startup.png", metadata["smoke"]["startup"]["frame"]["path"])
        self.assertEqual("/original/build/startup.png", self.report["smoke"]["startup"]["frame"]["path"])

    def testConsoleShutdownIsDescribedOnlyForTheReviewedOriginalMain(self):
        from scripts import verify_history

        self.assertNotIn(b"Shutdown used", snapshotDocumentation(self.report, self.evidence)["README.md"])
        shutdown = {
            "mode": "closeWindowAndJoinConsole",
            "inputs": dict(verify_history.CONSOLE_SHUTDOWN_MAINS),
            "validationBoundary": verify_history.CONSOLE_SHUTDOWN_BOUNDARY,
        }
        self.report["adapter"] = {"mode": "game", "shutdown": shutdown}
        readme = snapshotDocumentation(self.report, self.evidence)["README.md"].decode()
        self.assertIn("closed the game window as a\nplayer would", readme)
        shutdown["inputs"] = {"src/main.cpp": "0" * 64}
        with self.assertRaisesRegex(VerificationError, "reviewed original main"):
            snapshotDocumentation(self.report, self.evidence)
        shutdown["inputs"] = dict(verify_history.CONSOLE_SHUTDOWN_MAINS)
        self.report["adapter"]["mode"] = "editor"
        with self.assertRaisesRegex(VerificationError, "reviewed original main"):
            snapshotDocumentation(self.report, self.evidence)

    def reflectionReport(self):
        helper = history_source_prep.reflection_prep
        compatibility = {
            "path": helper.TARGET,
            "sha256": hashlib.sha256(helper.HEADER).hexdigest(),
            "inputs": helper.INPUTS,
            "qmakeArgument": helper.ARGUMENT,
            "provenance": helper.PROVENANCE,
            "validationBoundary": helper.BOUNDARY,
            "replaySha256": hashlib.sha256(Path(helper.__file__).read_bytes()).hexdigest(),
        }
        outputs = [
            {"path": helper.TARGET, "before": None, "after": {"kind": "file", "sha256": compatibility["sha256"]}}
        ]
        preparation = {
            "status": "success",
            "steps": [
                {
                    "name": "reflectionRegistration",
                    "command": ["prepare-reflection-registration"],
                    "returnCode": 0,
                    "timedOut": False,
                }
            ],
            "outputs": outputs,
            "qmakeArguments": [helper.ARGUMENT],
            "identity": {"implementationSha256": "d" * 64, "reflectionRegistration": compatibility, "outputs": outputs},
        }
        self.report["sourcePreparation"] = preparation
        self.report["startupCompatibility"] = "parentReflectionRegistration"
        self.report["startupSelection"] = {"mode": "game", "boundary": helper.BOUNDARY}
        self.report["recipe"]["qmakeArguments"] = [helper.ARGUMENT]
        (self.evidence / "source-preparation.json").write_text(json.dumps(preparation))
        (self.evidence / "source-preparation.log").write_text("Generated exact parent registration macro header\n")
        (self.evidence / helper.ATTACHMENT).write_bytes(helper.HEADER)
        return helper

    def testReflectionCompatibilityHasExplicitBoundaryHeaderAndPortableCommand(self):
        helper = self.reflectionReport()
        files = snapshotDocumentation(self.report, self.evidence)
        self.assertEqual(helper.HEADER, files["recovery/" + helper.ATTACHMENT])
        self.assertEqual(Path(helper.__file__).read_bytes(), files["recovery/prepare_reflection_registration.py"])
        readme = files["README.md"].decode()
        self.assertIn("Every original source file and translation unit is", readme)
        self.assertIn("python3 recovery/prepare_reflection_registration.py", readme)
        qmake = next(line for line in readme.splitlines() if line.startswith("qmake "))
        self.assertIn(helper.ARGUMENT, shlex.split(qmake))

    def testReflectionCompatibilityRejectsChangedHeaderInputsAndMissingFlag(self):
        helper = self.reflectionReport()
        (self.evidence / helper.ATTACHMENT).write_bytes(b"changed macro")
        with self.assertRaisesRegex(VerificationError, "reviewed header"):
            snapshotDocumentation(self.report, self.evidence)
        (self.evidence / helper.ATTACHMENT).write_bytes(helper.HEADER)
        self.report["recipe"]["qmakeArguments"] = []
        with self.assertRaisesRegex(VerificationError, "qmake argument"):
            snapshotDocumentation(self.report, self.evidence)
        self.report["recipe"]["qmakeArguments"] = [helper.ARGUMENT]
        metadata = self.report["sourcePreparation"]["identity"]["reflectionRegistration"]
        metadata["inputs"] = {**metadata["inputs"], "CReflection.h": "0" * 64}
        with self.assertRaisesRegex(VerificationError, "reviewed inputs"):
            snapshotDocumentation(self.report, self.evidence)

    def testProgressRejectsTamperedReflectionProofAndLabelsCompatibility(self):
        from scripts import history_workbench as workbench

        helper = self.reflectionReport()
        image = "sha256:" + "d" * 64
        self.report["toolchainImage"] = image
        commit = self.report["sourceCommit"]
        tree = {"tree": self.report["sourceTree"]}
        repository = self.evidence / "repository"
        evidence = repository / "recovery/evidence" / commit
        evidence.mkdir(parents=True)
        for path in list(self.evidence.iterdir()):
            if path.is_file():
                (evidence / path.name).write_bytes(path.read_bytes())
        (evidence / "verification.json").write_text(json.dumps(self.report))
        with (
            patch.object(workbench, "REPO", repository),
            patch.object(workbench, "ROOTFS", None),
            patch.object(workbench, "TREE_OF", {commit: tree}),
            patch.object(workbench, "ORDER", [commit]),
            patch.object(workbench, "CATALOG", {"trees": [tree]}),
            patch.dict(workbench.os.environ, {"HISTORY_TOOLCHAIN_IMAGE_ID": image}),
            patch.object(workbench.rh, "loadOverrides", return_value={}),
            patch.object(workbench.rh, "GitObjects"),
            patch.object(
                workbench.rh,
                "prepareSnapshot",
                return_value=(
                    None,
                    {"restoredFilesFingerprint": self.report["restoration"]["restoredFilesFingerprint"]},
                ),
            ),
        ):
            workbench.progress()
            progress = json.loads((repository / "recovery/progress.json").read_text())
            self.assertEqual(1, progress["validatedCommitCount"])
            self.assertEqual("parentReflectionRegistration", progress["snapshots"][0]["startupCompatibility"])
            (evidence / helper.ATTACHMENT).write_bytes(b"changed header")
            workbench.progress()
            progress = json.loads((repository / "recovery/progress.json").read_text())
            self.assertEqual(0, progress["validatedCommitCount"])

    def coordinatesReport(self):
        helper = history_source_prep.coordinates_prep
        compatibility = {
            "path": helper.TARGET,
            "sha256": hashlib.sha256(helper.HEADER).hexdigest(),
            "inputs": helper.INPUTS,
            "qmakeArgument": helper.ARGUMENT,
            "provenance": helper.PROVENANCE,
            "validationBoundary": helper.BOUNDARY,
            "replaySha256": hashlib.sha256(Path(helper.__file__).read_bytes()).hexdigest(),
        }
        outputs = [
            {"path": helper.TARGET, "before": None, "after": {"kind": "file", "sha256": compatibility["sha256"]}}
        ]
        preparation = {
            "status": "success",
            "steps": [
                {
                    "name": "coordinatesHash",
                    "command": ["prepare-coordinates-hash"],
                    "returnCode": 0,
                    "timedOut": False,
                }
            ],
            "outputs": outputs,
            "qmakeArguments": [helper.ARGUMENT],
            "identity": {"implementationSha256": "d" * 64, "coordinatesHash": compatibility, "outputs": outputs},
        }
        self.report["sourcePreparation"] = preparation
        self.report["startupCompatibility"] = "originalCoordinateHash"
        self.report["startupSelection"] = {"mode": "game", "boundary": helper.BOUNDARY}
        self.report["recipe"]["qmakeArguments"] = [helper.ARGUMENT]
        (self.evidence / "source-preparation.json").write_text(json.dumps(preparation))
        (self.evidence / "source-preparation.log").write_text("Generated exact parent registration macro header\n")
        (self.evidence / helper.ATTACHMENT).write_bytes(helper.HEADER)
        return helper

    def testCoordinateHashCompatibilityHasExplicitBoundaryHeaderAndPortableCommand(self):
        helper = self.coordinatesReport()
        files = snapshotDocumentation(self.report, self.evidence)
        self.assertEqual(helper.HEADER, files["recovery/" + helper.ATTACHMENT])
        self.assertEqual(Path(helper.__file__).read_bytes(), files["recovery/prepare_coordinates_hash.py"])
        readme = files["README.md"].decode()
        self.assertIn("the original hash algorithm and all original source files remain unchanged.", readme)
        self.assertIn("python3 recovery/prepare_coordinates_hash.py", readme)
        qmake = next(line for line in readme.splitlines() if line.startswith("qmake "))
        self.assertIn(helper.ARGUMENT, shlex.split(qmake))

    def testCoordinateHashCompatibilityRejectsChangedHeaderInputsAndMissingFlag(self):
        helper = self.coordinatesReport()
        (self.evidence / helper.ATTACHMENT).write_bytes(b"changed macro")
        with self.assertRaisesRegex(VerificationError, "reviewed header"):
            snapshotDocumentation(self.report, self.evidence)
        (self.evidence / helper.ATTACHMENT).write_bytes(helper.HEADER)
        self.report["recipe"]["qmakeArguments"] = []
        with self.assertRaisesRegex(VerificationError, "qmake argument"):
            snapshotDocumentation(self.report, self.evidence)
        self.report["recipe"]["qmakeArguments"] = [helper.ARGUMENT]
        metadata = self.report["sourcePreparation"]["identity"]["coordinatesHash"]
        metadata["inputs"] = {**metadata["inputs"], "CCoordinateHash.h": "0" * 64}
        with self.assertRaisesRegex(VerificationError, "reviewed inputs"):
            snapshotDocumentation(self.report, self.evidence)

    def testProgressRejectsTamperedCoordinateHashProofAndLabelsCompatibility(self):
        from scripts import history_workbench as workbench

        helper = self.coordinatesReport()
        image = "sha256:" + "d" * 64
        self.report["toolchainImage"] = image
        commit = self.report["sourceCommit"]
        tree = {"tree": self.report["sourceTree"]}
        repository = self.evidence / "repository"
        evidence = repository / "recovery/evidence" / commit
        evidence.mkdir(parents=True)
        for path in list(self.evidence.iterdir()):
            if path.is_file():
                (evidence / path.name).write_bytes(path.read_bytes())
        (evidence / "verification.json").write_text(json.dumps(self.report))
        with (
            patch.object(workbench, "REPO", repository),
            patch.object(workbench, "ROOTFS", None),
            patch.object(workbench, "TREE_OF", {commit: tree}),
            patch.object(workbench, "ORDER", [commit]),
            patch.object(workbench, "CATALOG", {"trees": [tree]}),
            patch.dict(workbench.os.environ, {"HISTORY_TOOLCHAIN_IMAGE_ID": image}),
            patch.object(workbench.rh, "loadOverrides", return_value={}),
            patch.object(workbench.rh, "GitObjects"),
            patch.object(
                workbench.rh,
                "prepareSnapshot",
                return_value=(
                    None,
                    {"restoredFilesFingerprint": self.report["restoration"]["restoredFilesFingerprint"]},
                ),
            ),
        ):
            workbench.progress()
            progress = json.loads((repository / "recovery/progress.json").read_text())
            self.assertEqual(1, progress["validatedCommitCount"])
            self.assertEqual("originalCoordinateHash", progress["snapshots"][0]["startupCompatibility"])
            (evidence / helper.ATTACHMENT).write_bytes(b"changed header")
            workbench.progress()
            progress = json.loads((repository / "recovery/progress.json").read_text())
            self.assertEqual(0, progress["validatedCommitCount"])

    def aliasReport(self):
        helper = history_source_prep.aliases_prep
        compatibility = {
            "aliases": {
                target: {"source": source, "sha256": helper.INPUTS[source]}
                for target, source in sorted(helper.ALIASES.items())
            },
            "inputs": helper.INPUTS,
            "provenance": helper.PROVENANCE,
            "validationBoundary": helper.BOUNDARY,
            "replaySha256": hashlib.sha256(Path(helper.__file__).read_bytes()).hexdigest(),
        }
        outputs = [
            {"path": target, "before": None, "after": {"kind": "file", "sha256": helper.INPUTS[source]}}
            for target, source in sorted(helper.ALIASES.items())
        ]
        preparation = {
            "status": "success",
            "steps": [
                {
                    "name": "resourceAliases",
                    "command": ["prepare-resource-aliases"],
                    "returnCode": 0,
                    "timedOut": False,
                }
            ],
            "outputs": outputs,
            "identity": {"implementationSha256": "d" * 64, "resourceAliases": compatibility, "outputs": outputs},
        }
        self.report["sourcePreparation"] = preparation
        self.report["startupCompatibility"] = "renamedResourceAliases"
        self.report["startupSelection"] = {"mode": "game", "boundary": helper.BOUNDARY}
        (self.evidence / "source-preparation.json").write_text(json.dumps(preparation))
        (self.evidence / "source-preparation.log").write_text("Supplied manifest-named resource aliases\n")
        return helper

    def testResourceAliasCompatibilityHasExplicitBoundaryAndPortableCommand(self):
        helper = self.aliasReport()
        files = snapshotDocumentation(self.report, self.evidence)
        self.assertEqual(Path(helper.__file__).read_bytes(), files["recovery/prepare_resource_aliases.py"])
        readme = files["README.md"].decode()
        self.assertIn("The original manifest, sources and images remain unchanged.", readme)
        self.assertIn("python3 recovery/prepare_resource_aliases.py", readme)

    def testResourceAliasCompatibilityRejectsChangedInputsOutputsAndLabels(self):
        helper = self.aliasReport()
        metadata = self.report["sourcePreparation"]["identity"]["resourceAliases"]
        original = dict(metadata["inputs"])
        metadata["inputs"] = {**original, "creatures.qrc": "0" * 64}
        with self.assertRaisesRegex(VerificationError, "reviewed original inputs"):
            snapshotDocumentation(self.report, self.evidence)
        metadata["inputs"] = original
        target = sorted(helper.ALIASES)[0]
        self.report["sourcePreparation"]["outputs"][0]["after"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(VerificationError, "exact preparation fingerprints"):
            snapshotDocumentation(self.report, self.evidence)
        self.report["sourcePreparation"]["outputs"][0]["after"]["sha256"] = helper.INPUTS[helper.ALIASES[target]]
        self.report["startupCompatibility"] = None
        with self.assertRaisesRegex(VerificationError, "reviewed original inputs"):
            snapshotDocumentation(self.report, self.evidence)

    def conflictReport(self):
        helper = history_source_prep.conflicts_prep
        files = {
            name: {"beforeSha256": digest, "afterSha256": hashlib.sha256(name.encode()).hexdigest()}
            for name, digest in sorted(helper.INPUTS.items())
        }
        recorded = {
            "files": files,
            "supplied": {helper.SUPPLIED_PATH: {"sha256": helper.SUPPLIED_SHA256, "sourceCommit": helper.SUPPLIED_COMMIT}},
            "side": helper.SIDE,
            "provenance": helper.PROVENANCE,
            "validationBoundary": helper.BOUNDARY,
            "replaySha256": hashlib.sha256(Path(helper.__file__).read_bytes()).hexdigest(),
        }
        outputs = [
            {
                "path": name,
                "before": {"kind": "file", "sha256": hashes["beforeSha256"]},
                "after": {"kind": "file", "sha256": hashes["afterSha256"]},
            }
            for name, hashes in files.items()
        ]
        outputs.append(
            {"path": helper.SUPPLIED_PATH, "before": None, "after": {"kind": "file", "sha256": helper.SUPPLIED_SHA256}}
        )
        preparation = {
            "status": "success",
            "steps": [
                {
                    "name": "conflictResolution",
                    "command": ["resolve-whitespace-conflicts"],
                    "returnCode": 0,
                    "timedOut": False,
                }
            ],
            "outputs": outputs,
            "identity": {"implementationSha256": "d" * 64, "conflictResolution": recorded, "outputs": outputs},
        }
        self.report["sourcePreparation"] = preparation
        self.report["startupCompatibility"] = "whitespaceConflictResolution"
        self.report["startupSelection"] = {"mode": "game", "boundary": helper.BOUNDARY}
        (self.evidence / "source-preparation.json").write_text(json.dumps(preparation))
        (self.evidence / "source-preparation.log").write_text("Resolved whitespace-only conflict hunks\n")
        return helper

    def testConflictResolutionHasExplicitBoundaryAndPortableCommand(self):
        helper = self.conflictReport()
        files = snapshotDocumentation(self.report, self.evidence)
        self.assertEqual(Path(helper.__file__).read_bytes(), files["recovery/prepare_conflict_resolution.py"])
        readme = files["README.md"].decode()
        self.assertIn("in every hunk both sides differ only in whitespace", readme)
        self.assertIn("python3 recovery/prepare_conflict_resolution.py", readme)
        self.assertIn("also omitted `pathfinder/pathfindercache.cpp`", readme)

    def testConflictResolutionRejectsChangedInputsOutputsAndSide(self):
        helper = self.conflictReport()
        recorded = self.report["sourcePreparation"]["identity"]["conflictResolution"]
        recorded["side"] = "HEAD"
        with self.assertRaisesRegex(VerificationError, "reviewed original inputs"):
            snapshotDocumentation(self.report, self.evidence)
        recorded["side"] = helper.SIDE
        first = sorted(helper.INPUTS)[0]
        self.report["sourcePreparation"]["outputs"][0]["after"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(VerificationError, "exact preparation fingerprints"):
            snapshotDocumentation(self.report, self.evidence)
        self.report["sourcePreparation"]["outputs"][0]["after"]["sha256"] = recorded["files"][first]["afterSha256"]
        recorded["files"][first]["beforeSha256"] = "0" * 64
        with self.assertRaisesRegex(VerificationError, "reviewed original inputs"):
            snapshotDocumentation(self.report, self.evidence)

    def forwarderReport(self):
        helper = history_source_prep.forwarders_prep
        state = sorted(helper.STATES)[0]
        names = helper.STATES[state]["forwarders"]
        forwarders = {
            name: {
                "includes": list(helper.FORWARDERS[name]),
                "sha256": hashlib.sha256(helper.forwarderBytes(name)).hexdigest(),
            }
            for name in names
        }
        recorded = {
            "state": state,
            "forwarders": forwarders,
            "inputs": {**helper.INCLUDERS, **helper.STATES[state]["targets"]},
            "provenance": helper.PROVENANCE,
            "validationBoundary": helper.BOUNDARY,
            "replaySha256": hashlib.sha256(Path(helper.__file__).read_bytes()).hexdigest(),
        }
        outputs = [
            {"path": name, "before": None, "after": {"kind": "file", "sha256": forwarders[name]["sha256"]}}
            for name in names
        ]
        preparation = {
            "status": "success",
            "steps": [
                {
                    "name": "forwardingHeaders",
                    "command": ["prepare-forwarding-headers"],
                    "returnCode": 0,
                    "timedOut": False,
                }
            ],
            "outputs": outputs,
            "identity": {"implementationSha256": "d" * 64, "forwardingHeaders": recorded, "outputs": outputs},
        }
        self.report["sourcePreparation"] = preparation
        self.report["startupCompatibility"] = "mergedHeaderForwarders"
        self.report["startupSelection"] = {"mode": "game", "boundary": helper.BOUNDARY}
        (self.evidence / "source-preparation.json").write_text(json.dumps(preparation))
        (self.evidence / "source-preparation.log").write_text("Created forwarding headers\n")
        return helper

    def testForwarderCompatibilityHasExplicitBoundaryAndPortableCommand(self):
        helper = self.forwarderReport()
        files = snapshotDocumentation(self.report, self.evidence)
        self.assertEqual(Path(helper.__file__).read_bytes(), files["recovery/prepare_forwarding_headers.py"])
        readme = files["README.md"].decode()
        self.assertIn("Each forwarder only", readme)
        self.assertIn("python3 recovery/prepare_forwarding_headers.py", readme)

    def testForwarderCompatibilityRejectsChangedInputsOutputsAndState(self):
        helper = self.forwarderReport()
        recorded = self.report["sourcePreparation"]["identity"]["forwardingHeaders"]
        original = recorded["inputs"]
        recorded["inputs"] = {**original, "src/main.cpp": "0" * 64}
        with self.assertRaisesRegex(VerificationError, "reviewed original inputs"):
            snapshotDocumentation(self.report, self.evidence)
        recorded["inputs"] = original
        self.report["sourcePreparation"]["outputs"][0]["after"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(VerificationError, "exact preparation fingerprints"):
            snapshotDocumentation(self.report, self.evidence)
        first = self.report["sourcePreparation"]["outputs"][0]["path"]
        self.report["sourcePreparation"]["outputs"][0]["after"]["sha256"] = recorded["forwarders"][first]["sha256"]
        recorded["state"] = "f" * 40
        with self.assertRaisesRegex(VerificationError, "reviewed original inputs"):
            snapshotDocumentation(self.report, self.evidence)

    def resourceReport(self):
        resource = (
            '<RCC>\n    <qresource prefix="/">\n'
            + "".join(f"        <file>{name}</file>\n" for name in sorted(history_source_prep.SUPPLEMENTAL_IMAGES))
            + "    </qresource>\n</RCC>\n"
        ).encode()
        digest = hashlib.sha256(resource).hexdigest()
        boundary = "Game startup with supplemental Qt resource compatibility; original manifest unchanged"
        helper = Path(history_source_prep.__file__).with_name("history_prepare_resources.py").read_bytes()
        output = {
            "path": history_source_prep.SUPPLEMENTAL_QRC,
            "before": None,
            "after": {"kind": "file", "sha256": digest},
            "purpose": "supplemental Qt resources",
        }
        preparation = {
            "status": "success",
            "outputs": [output],
            "steps": [
                {
                    "name": "supplementalResources",
                    "command": ["history_source_prep.py", "generate-supplemental-qrc"],
                    "returnCode": 0,
                    "timedOut": False,
                    "log": "/original/preparation.log",
                }
            ],
            "qmakeArguments": [history_source_prep.SUPPLEMENTAL_QMAKE_ARGUMENT],
            "identity": {
                "implementationSha256": "a" * 64,
                "outputs": [output],
                "supplementalResources": {
                    "path": history_source_prep.SUPPLEMENTAL_QRC,
                    "sha256": digest,
                    "inputs": {**history_source_prep.SUPPLEMENTAL_INPUTS, **history_source_prep.SUPPLEMENTAL_IMAGES},
                    "qmakeArgument": history_source_prep.SUPPLEMENTAL_QMAKE_ARGUMENT,
                    "provenance": history_source_prep.SUPPLEMENTAL_PROVENANCE,
                    "validationBoundary": boundary,
                    "resourceReplaySha256": hashlib.sha256(helper).hexdigest(),
                },
            },
        }
        self.report.update(
            sourcePreparation=preparation,
            startupCompatibility="supplementalQtResources",
            startupSelection={"mode": "game", "boundary": boundary},
        )
        self.report["recipe"]["qmakeArguments"] = [history_source_prep.SUPPLEMENTAL_QMAKE_ARGUMENT]
        (self.evidence / "source-preparation.json").write_text(json.dumps(preparation))
        (self.evidence / "source-preparation.log").write_text("Supplemental resources prepared from original images\n")
        (self.evidence / "supplemental_images.qrc").write_bytes(resource)

    def testResourceCompatibilityDocumentationIncludesPinnedReplayAndItsBoundary(self):
        self.resourceReport()
        files = snapshotDocumentation(self.report, self.evidence)
        readme = files["README.md"].decode()
        self.assertIn("Startup used supplemental Qt resource compatibility", readme)
        self.assertIn("original manifest, provider and configuration remain unchanged", readme)
        self.assertIn("python3 recovery/prepare_supplemental_resources.py", readme)
        self.assertEqual(
            (self.evidence / "supplemental_images.qrc").read_bytes(), files["recovery/supplemental_images.qrc"]
        )
        self.assertIn("recovery/prepare_supplemental_resources.py", files)
        qmake = next(line for line in readme.splitlines() if line.startswith("qmake "))
        self.assertIn(history_source_prep.SUPPLEMENTAL_QMAKE_ARGUMENT, shlex.split(qmake))

    def testResourceCompatibilityCannotLoseItsPinsBoundaryArgumentOrAttachment(self):
        self.resourceReport()
        original = copy.deepcopy(self.report)
        for change in ["marker", "boundary", "image", "provenance", "output", "argument", "helper"]:
            with self.subTest(change=change):
                self.report = copy.deepcopy(original)
                supplement = self.report["sourcePreparation"]["identity"]["supplementalResources"]
                if change == "marker":
                    self.report.pop("startupCompatibility")
                elif change == "boundary":
                    self.report["startupSelection"]["boundary"] = "Authored game startup"
                elif change == "image":
                    supplement["inputs"][next(iter(history_source_prep.SUPPLEMENTAL_IMAGES))] = "d" * 64
                elif change == "provenance":
                    supplement["provenance"] = {}
                elif change == "output":
                    self.report["sourcePreparation"]["outputs"][0]["after"]["sha256"] = "d" * 64
                elif change == "argument":
                    self.report["recipe"]["qmakeArguments"] = []
                else:
                    supplement["resourceReplaySha256"] = "d" * 64
                (self.evidence / "source-preparation.json").write_text(json.dumps(self.report["sourcePreparation"]))
                with self.assertRaises(VerificationError):
                    snapshotDocumentation(self.report, self.evidence)
        self.report = original
        (self.evidence / "source-preparation.json").write_text(json.dumps(self.report["sourcePreparation"]))
        (self.evidence / "supplemental_images.qrc").write_bytes(b"changed attachment")
        with self.assertRaisesRegex(VerificationError, "verified output"):
            snapshotDocumentation(self.report, self.evidence)

    def editorReport(self):
        self.report["startupMode"] = "editor"
        self.report["startupSelection"] = {
            "mode": "editor",
            "originalInputs": [
                {"path": name, "blob": "d" * 40, "sha256": "e" * 64} for name in ("main.cpp", "config/init.json")
            ],
        }
        startup = self.report["smoke"]["startup"]
        startup.update(mode="editor", checks={name: True for name in EDITOR_CHECKS})
        (self.evidence / "startup.json").write_text(json.dumps(startup))

    def testAuthoredEditorDocumentationStatesItsValidationBoundary(self):
        self.editorReport()
        files = snapshotDocumentation(self.report, self.evidence)
        readme = files["README.md"].decode()
        self.assertIn("# Recovered editor snapshot", readme)
        self.assertIn("Gameplay and player behavior were not verified", readme)
        self.assertNotIn("healthy player", readme)
        self.assertIn("config/init.json", readme)

    def testEditorDocumentationRequiresOriginalEntrypointAndConfigurationPins(self):
        self.editorReport()
        for change in ("mode", "missing", "hash", "duplicate"):
            with self.subTest(change=change):
                report = copy.deepcopy(self.report)
                selection = report["startupSelection"]
                if change == "mode":
                    selection["mode"] = "game"
                elif change == "missing":
                    selection["originalInputs"].pop()
                elif change == "hash":
                    selection["originalInputs"][0]["sha256"] = "bad"
                else:
                    selection["originalInputs"].append(selection["originalInputs"][0])
                with self.assertRaises(VerificationError):
                    snapshotDocumentation(report, self.evidence)

    def testEditorModeCannotReplaceGameReadinessInDocumentation(self):
        self.editorReport()
        self.report["startupMode"] = "game"
        with self.assertRaises(VerificationError):
            snapshotDocumentation(self.report, self.evidence)

    def testReviewedForcedIncludeRemainsOnePortableQmakeArgument(self):
        flag = "QMAKE_CXXFLAGS+=-include functional"
        self.report["recipe"]["qmakeArguments"] = ["QMAKE_CXX=g++-5", flag]
        files = snapshotDocumentation(self.report, self.evidence)
        line = next(line for line in files["README.md"].decode().splitlines() if line.startswith("qmake "))
        self.assertEqual(
            ["qmake", "Game.pro", "QMAKE_CXX=g++-5", flag, "-after", "TARGET=RecoveryGame", "DESTDIR=."],
            shlex.split(line),
        )

    def testReviewedProviderIncludePreservesLiteralQmakeExpansion(self):
        flag = "INCLUDEPATH+=$$_PRO_FILE_PWD_/provider"
        self.report["recipe"]["qmakeArguments"] = [flag]
        files = snapshotDocumentation(self.report, self.evidence)
        line = next(line for line in files["README.md"].decode().splitlines() if line.startswith("qmake "))
        self.assertEqual(
            ["qmake", "Game.pro", flag, "-after", "TARGET=RecoveryGame", "DESTDIR=."],
            shlex.split(line),
        )

    def testUnreviewedCompilerWhitespaceAndShellFragmentsAreRejected(self):
        for flag in (
            "QMAKE_CXXFLAGS+=-include unreviewed",
            "QMAKE_CXXFLAGS+=-include functional;id",
            "QMAKE_CXXFLAGS+=$(id)",
            "QMAKE_CXXFLAGS+=`id`",
            "INCLUDEPATH+=$$_PRO_FILE_PWD_/provider;id",
            "INCLUDEPATH+=$(id)/provider",
            "QMAKE_CXXFLAGS+=-include functional\nid",
        ):
            with self.subTest(flag=flag):
                self.report["recipe"]["qmakeArguments"] = [flag]
                with self.assertRaisesRegex(VerificationError, "reviewed portable command"):
                    snapshotDocumentation(self.report, self.evidence)

    def testUnverifiedOrIncompleteRecoveryCannotAttachDocumentation(self):
        for modification in ("status", "restore", "configure", "build", "smoke", "fingerprint"):
            with self.subTest(modification=modification):
                report = copy.deepcopy(self.report)
                if modification == "status":
                    report["status"] = "blocked"
                elif modification == "restore":
                    report["restoration"]["unresolved"] = [{"path": "map.cpp"}]
                elif modification == "fingerprint":
                    report["restoration"].pop("restoredFilesFingerprint")
                else:
                    report[modification]["returnCode"] = 2
                with self.assertRaises(VerificationError):
                    snapshotDocumentation(report, self.evidence)

    def testMissingInvalidOrMismatchedFrameFails(self):
        for image in (b"", b"fake screenshot", pngBytes()[:-5]):
            with self.subTest(image=image):
                (self.evidence / "startup.png").write_bytes(image)
                with self.assertRaises(VerificationError):
                    snapshotDocumentation(self.report, self.evidence)

    def testReadinessReportMustBelongToTheSameRun(self):
        (self.evidence / "startup.json").write_text("{}")
        with self.assertRaisesRegex(VerificationError, "differs"):
            snapshotDocumentation(self.report, self.evidence)

    def testScreenshotBytesMustMatchTheCapturedFingerprint(self):
        self.report["smoke"]["startup"]["frame"]["sha256"] = "d" * 64
        (self.evidence / "startup.json").write_text(json.dumps(self.report["smoke"]["startup"]))
        with self.assertRaisesRegex(VerificationError, "actual verified image bytes"):
            snapshotDocumentation(self.report, self.evidence)

    def testVisibleDesktopStartupCannotBePublishedAsVerified(self):
        self.report["smoke"]["command"] = ["Game"]
        with self.assertRaisesRegex(VerificationError, "Xvfb"):
            snapshotDocumentation(self.report, self.evidence)

    def addSourcePreparation(self):
        generated = {"path": "gen/prop.h", "before": None, "after": {"kind": "file", "sha256": "d" * 64}}
        changed = {
            "path": "src/Stats.h",
            "before": {"kind": "file", "sha256": "e" * 64},
            "after": {"kind": "file", "sha256": "f" * 64},
        }
        preparation = {
            "status": "success",
            "steps": [
                {"name": "interpreter", "command": ["python2.7", "--version"], "returnCode": 0, "timedOut": False},
                {
                    "name": "generator",
                    "command": ["python2.7", "-B", "preprocessor.py"],
                    "returnCode": 0,
                    "timedOut": False,
                },
            ],
            "outputs": [generated, changed],
            "identity": {
                "implementationSha256": "1" * 64,
                "interpreter": "Python 2.7.18",
                "inputs": {
                    "preprocessor.py": {"kind": "file", "sha256": "2" * 64},
                    "classes.json": {"kind": "file", "sha256": "3" * 64},
                },
                "outputs": [generated, changed],
            },
        }
        self.report["sourcePreparation"] = preparation
        (self.evidence / "source-preparation.json").write_text(json.dumps(preparation))
        (self.evidence / "source-preparation.log").write_bytes(b"Python 2.7.18\nOriginal generator completed\n")

    def testOriginalGeneratorInstructionsAndProofAreAttachedBeforeQmake(self):
        self.addSourcePreparation()
        before = copy.deepcopy(self.report)
        files = snapshotDocumentation(self.report, self.evidence)
        readme = files["README.md"].decode()
        self.assertIn("separate build copy", readme)
        self.assertLess(readme.index("python2.7 -B preprocessor.py"), readme.index("qmake Game.pro"))
        self.assertIn("before/after hashes", readme)
        for name in ("source-preparation.json", "source-preparation.log"):
            self.assertEqual((self.evidence / name).read_bytes(), files["recovery/" + name])
            attached = json.loads(files["recovery/verification.json"])["attachedSourcePreparation"][name]
            self.assertEqual(hashlib.sha256(files["recovery/" + name]).hexdigest(), attached["sha256"])
        self.assertEqual(before, self.report)

    def testSourcePreparationRequiresSuccessfulMatchingProofAndLog(self):
        for modification in (
            "failed",
            "failed-command",
            "wrong-interpreter",
            "missing-report",
            "different-report",
            "missing-log",
        ):
            with self.subTest(modification=modification):
                self.addSourcePreparation()
                if modification == "failed":
                    self.report["sourcePreparation"]["status"] = "failed"
                elif modification == "failed-command":
                    self.report["sourcePreparation"]["steps"][1]["returnCode"] = 1
                elif modification == "wrong-interpreter":
                    self.report["sourcePreparation"]["identity"]["interpreter"] = "Python 3.12.9"
                elif modification == "missing-report":
                    (self.evidence / "source-preparation.json").unlink()
                elif modification == "different-report":
                    (self.evidence / "source-preparation.json").write_text("{}")
                else:
                    (self.evidence / "source-preparation.log").unlink()
                with self.assertRaises(VerificationError):
                    snapshotDocumentation(self.report, self.evidence)

    def testTreesWithoutGeneratorsKeepTheSameDocumentationBytes(self):
        expected = snapshotDocumentation(self.report, self.evidence)
        self.report["sourcePreparation"] = {"status": "not-required", "steps": [], "outputs": [], "identity": {}}
        actual = snapshotDocumentation(self.report, self.evidence)
        self.assertEqual(expected["README.md"], actual["README.md"])
        self.assertEqual(set(expected), set(actual))

    def addIncludePreparation(self):
        source = self.evidence / "build-source"
        (source / "view").mkdir(parents=True)
        (source / "view/gamescene.cpp").write_bytes(b'#include "view\\playerlistview.h"\n')
        (source / "view/playerlistview.h").write_text("struct PlayerListView {};\n")
        preparation = history_source_prep.prepareSources(source, self.evidence / "preparation", {}, {}, None)
        self.report["sourcePreparation"] = preparation
        (self.evidence / "source-preparation.json").write_text(json.dumps(preparation))
        (self.evidence / "source-preparation.log").write_bytes(Path(preparation["steps"][0]["log"]).read_bytes())

    def testIncludeOnlyPreparationAttachesHashPinnedHelperWithoutGeneratorClaims(self):
        self.addIncludePreparation()
        files = snapshotDocumentation(self.report, self.evidence)
        readme = files["README.md"].decode()
        self.assertLess(readme.index("python3 recovery/prepare_build_sources.py"), readme.index("qmake Game.pro"))
        self.assertIn("separate build copy", readme)
        self.assertNotIn("python2.7 -B preprocessor.py", readme)
        self.assertIn("recovery/prepare_build_sources.py", files)
        metadata = json.loads(files["recovery/verification.json"])
        self.assertEqual(
            hashlib.sha256(files["recovery/prepare_build_sources.py"]).hexdigest(),
            metadata["attachedSourcePreparation"]["prepare_build_sources.py"]["sha256"],
        )

    def testPortableHelperMustMatchTheVerifiedPreparationSemantics(self):
        self.addIncludePreparation()
        self.report["sourcePreparation"]["identity"]["includeReplaySha256"] = "0" * 64
        with self.assertRaisesRegex(VerificationError, "verified semantics"):
            snapshotDocumentation(self.report, self.evidence)

    def testRuntimeSavePrerequisiteIsRecordedAndExplainedWithoutSourceEdits(self):
        self.report["runtimePreparation"] = {
            "status": "ready",
            "directories": [{"path": "save", "created": True, "preservedExisting": False}],
            "identity": {
                "directories": [
                    {
                        "path": "save",
                        "requiredBy": [
                            {
                                "source": "view/gamescene.cpp",
                                "sha256": "4" * 64,
                                "line": 50,
                                "operation": 'fopen("save/game.sav", "w+")',
                            }
                        ],
                    }
                ]
            },
        }
        files = snapshotDocumentation(self.report, self.evidence)
        readme = files["README.md"].decode()
        self.assertLess(readme.index("mkdir -p save"), readme.index("./RecoveryGame"))
        self.assertIn("without changing source files or replacing existing save data", readme)
        self.assertEqual(
            self.report["runtimePreparation"], json.loads(files["recovery/verification.json"])["runtimePreparation"]
        )
        self.report["runtimePreparation"]["identity"]["directories"][0]["path"] = "../save"
        with self.assertRaisesRegex(VerificationError, "contained runtime"):
            snapshotDocumentation(self.report, self.evidence)


if __name__ == "__main__":
    unittest.main()
