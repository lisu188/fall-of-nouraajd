# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression checks for the exact original Qt resource omission at catalog #98."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from scripts import history_source_prep as preparation
from scripts import history_prepare_resources as replay
from scripts import verify_history as verify


class HistoricalResourcePreparationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.output = self.root / "preparation"
        self.inputs = {
            "images.qrc": b'<RCC><qresource prefix="/"><file>images/base.png</file></qresource></RCC>\n',
            "animation/animationprovider.cpp": b'path=":/"+path;\n',
            "config/interactions.json": b'{"Attack":{"anim":"images/interactions/attack/"}}\n',
        }
        self.images = {"images/interactions/attack/0.png": b"original-image-bytes"}
        for name, data in {**self.inputs, **self.images}.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for name, values in [("SUPPLEMENTAL_INPUTS", self.inputs), ("SUPPLEMENTAL_IMAGES", self.images)]:
            mock = patch.object(
                preparation, name, {name: hashlib.sha256(data).hexdigest() for name, data in values.items()}
            )
            mock.start()
            self.addCleanup(mock.stop)

    def runCommand(self, *args):
        self.fail("Resource preparation must not execute a historical program")

    def testRecipeSelectionRecordsOnlyTheExactSupplementalArgument(self):
        recipe = {"id": "fixture", "pythonAbi": "none", "qmakeArguments": ["QMAKE_CXX=g++-5"]}
        selected = verify.selectRecipe([recipe], self.source, "fixture")
        self.assertEqual(["QMAKE_CXX=g++-5", preparation.SUPPLEMENTAL_QMAKE_ARGUMENT], selected["qmakeArguments"])
        self.assertEqual(["QMAKE_CXX=g++-5"], recipe["qmakeArguments"])

    def testIdenticalGeneratedOutputCanBeReusedForAnIncrementalBuild(self):
        first = preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
        original = preparation.sourceManifest(self.source)
        second = preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
        self.assertEqual("success", second["status"])
        self.assertEqual(original, preparation.sourceManifest(self.source))
        self.assertEqual(first["qmakeArguments"], second["qmakeArguments"])
        self.assertEqual(second["outputs"][0]["before"], second["outputs"][0]["after"])

    def portableFixture(self):
        result = preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
        evidence = self.source / "recovery"
        evidence.mkdir()
        (evidence / "source-preparation.json").write_text(json.dumps(result))
        resource = self.source / preparation.SUPPLEMENTAL_QRC
        (evidence / "supplemental_images.qrc").write_bytes(resource.read_bytes())
        resource.unlink()
        return evidence

    def testPortableReplayCreatesOnlyTheRecordedManifestAndPreservesOriginalInputs(self):
        evidence = self.portableFixture()
        original = {name: (self.source / name).read_bytes() for name in [*self.inputs, *self.images]}
        helper = evidence / "prepare_supplemental_resources.py"
        shutil.copyfile(Path(replay.__file__), helper)
        for message in ["Created", "Verified existing"]:
            result = subprocess.run(
                [sys.executable, str(helper)], cwd=self.source, capture_output=True, text=True, timeout=10
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn(message, result.stdout)
        self.assertEqual(original, {name: (self.source / name).read_bytes() for name in original})
        self.assertEqual(
            (evidence / "supplemental_images.qrc").read_bytes(),
            (self.source / preparation.SUPPLEMENTAL_QRC).read_bytes(),
        )

    def testPortableReplayRejectsTamperedInputsAndOutputBeforeWriting(self):
        evidence = self.portableFixture()
        metadata = json.loads((evidence / "source-preparation.json").read_text())
        resource = evidence / "supplemental_images.qrc"
        original_resource = resource.read_bytes()
        image = self.source / next(iter(self.images))
        image.write_bytes(b"changed input")
        with self.assertRaisesRegex(ValueError, "input differs"):
            replay.prepareResources(self.source, evidence)
        image.write_bytes(next(iter(self.images.values())))
        resource.write_bytes(b"changed output")
        with self.assertRaisesRegex(ValueError, "verified bytes"):
            replay.prepareResources(self.source, evidence)
        resource.write_bytes(original_resource)
        metadata["identity"]["supplementalResources"]["inputs"]["../escape"] = "a" * 64
        (evidence / "source-preparation.json").write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, "paths are unexpected"):
            replay.prepareResources(self.source, evidence)
        self.assertFalse((self.source / preparation.SUPPLEMENTAL_QRC).exists())

    def testOriginalMissingAliasFailsBeforeAndIsPresentAfterPreparation(self):
        original = {name: (self.source / name).read_bytes() for name in self.inputs}

        def aliases(path):
            return {entry.text for entry in ET.fromstring(path.read_bytes()).findall("./qresource/file")}

        self.assertNotIn(next(iter(self.images)), aliases(self.source / "images.qrc"))
        self.assertTrue(preparation.preparationRequired(self.source))
        result = preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
        self.assertEqual("success", result["status"])
        output = self.source / preparation.SUPPLEMENTAL_QRC
        self.assertEqual(set(self.images), aliases(output))
        self.assertEqual(original, {name: (self.source / name).read_bytes() for name in self.inputs})
        self.assertEqual("supplementalResources", result["steps"][0]["name"])
        supplement = result["identity"]["supplementalResources"]
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), supplement["sha256"])
        self.assertEqual(set(self.inputs) | set(self.images), set(supplement["inputs"]))
        self.assertIn("compatibility", supplement["validationBoundary"])
        self.assertEqual([preparation.SUPPLEMENTAL_QMAKE_ARGUMENT], result["qmakeArguments"])
        self.assertEqual(result["qmakeArguments"], preparation.preparationArguments(self.source))
        self.assertEqual(
            [
                {
                    "path": preparation.SUPPLEMENTAL_QRC,
                    "before": None,
                    "after": {"kind": "file", "sha256": supplement["sha256"]},
                    "purpose": "supplemental Qt resources",
                }
            ],
            result["outputs"],
        )

    def testDifferentOrAlreadyRepairedOriginalKeepsItsRecipeAndFiles(self):
        for name in self.inputs:
            with self.subTest(name=name):
                path = self.source / name
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                self.assertEqual([], preparation.preparationArguments(self.source))
                result = preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
                self.assertEqual("not-required", result["status"])
                self.assertFalse((self.source / preparation.SUPPLEMENTAL_QRC).exists())
                path.write_bytes(original)
        self.assertFalse(self.output.exists())

    def testMissingOrModifiedImageFailsBeforeAnyOutput(self):
        image = self.source / next(iter(self.images))
        for payload in [None, b"replacement"]:
            with self.subTest(payload=payload):
                if payload is None:
                    image.unlink()
                else:
                    image.write_bytes(payload)
                with self.assertRaisesRegex(ValueError, "image differs"):
                    preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
                self.assertFalse(self.output.exists())
                self.assertFalse((self.source / preparation.SUPPLEMENTAL_QRC).exists())

    def testSymlinkedInputsAndExistingOutputAreNeverOverwritten(self):
        image = self.source / next(iter(self.images))
        image.rename(self.root / "original.png")
        image.symlink_to(self.root / "original.png")
        with self.assertRaisesRegex(ValueError, "symlink"):
            preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
        self.assertFalse(self.output.exists())
        image.unlink()
        image.write_bytes(next(iter(self.images.values())))
        target = self.source / preparation.SUPPLEMENTAL_QRC
        for symlink in [False, True]:
            with self.subTest(symlink=symlink):
                if symlink:
                    target.symlink_to(self.root / "original.png")
                else:
                    target.write_bytes(b"preserved original")
                with self.assertRaisesRegex(ValueError, "already exists|symlink"):
                    preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
                self.assertEqual(b"original-image-bytes" if symlink else b"preserved original", target.read_bytes())
                target.unlink()

    def testIncludeOverlayAndResourceManifestAreBothRecordedWithoutEditingTheOriginalManifest(self):
        (self.source / "view").mkdir()
        (self.source / "view/gamescene.cpp").write_bytes(b'#include "view\\scene.h"\n')
        (self.source / "view/scene.h").write_bytes(b"#pragma once\n")
        original = (self.source / "images.qrc").read_bytes()
        result = preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
        self.assertEqual(
            {"view/gamescene.cpp", preparation.SUPPLEMENTAL_QRC}, {item["path"] for item in result["outputs"]}
        )
        self.assertEqual(
            {"windowsIncludeSeparators", "supplementalResources"}, {step["name"] for step in result["steps"]}
        )
        self.assertEqual(original, (self.source / "images.qrc").read_bytes())


if __name__ == "__main__":
    unittest.main()
