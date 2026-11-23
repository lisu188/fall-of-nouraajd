# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Hash gates, immutable originals and native regression for the original #340 macro defect."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import history_prepare_reflection as replay
from scripts import history_source_prep as preparation
from scripts import verify_history as verify


class HistoricalReflectionPreparationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.inputs = {
            "CReflection.h": (
                b"#pragma once\n#define Q_DECLARE_METATYPE(T)\n#define UNIQUE_NAME(X) X\n"
                b"inline int &registrationCount() { static int count=0; return count; }\n"
                b"template<class T> class CReflectionHelper { public: CReflectionHelper() { ++registrationCount(); } };\n"
                b"#define REFLECT(CLASS) CReflectionHelper<CLASS> UNIQUE_NAME(CLASS##BASE)(#CLASS);\n"
            ),
            "ReflectTypes.cpp": b'#include "CReflection.h"\nREFLECT(int)\nint main() { return registrationCount()==2 ? 0 : 1; }\n',
            "handler/CTypeHandler.cpp": b"// Original factory translation unit is retained.\n",
        }
        for name, data in self.inputs.items():
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        mock = patch.object(
            replay, "INPUTS", {name: hashlib.sha256(data).hexdigest() for name, data in self.inputs.items()}
        )
        mock.start()
        self.addCleanup(mock.stop)

    def runCommand(self, *args):
        self.fail("Reflection compatibility preparation must not execute or remove original translation units")

    def prepare(self):
        return preparation.prepareSources(self.source, self.root / "proof", {}, {}, self.runCommand)

    def testExactInputsSelectExplicitArgumentAndAddOnlyOneHeader(self):
        recipe = {"id": "fixture", "pythonAbi": "none", "qmakeArguments": ["QMAKE_CXX=g++-5"]}
        selected = verify.selectRecipe([recipe], self.source, "fixture")
        self.assertEqual(["QMAKE_CXX=g++-5", replay.ARGUMENT], selected["qmakeArguments"])
        result = self.prepare()
        self.assertEqual("success", result["status"])
        self.assertEqual([replay.ARGUMENT], result["qmakeArguments"])
        self.assertEqual(["reflectionRegistration"], [step["name"] for step in result["steps"]])
        self.assertEqual([replay.TARGET], [output["path"] for output in result["outputs"]])
        self.assertIsNone(result["outputs"][0]["before"])
        self.assertEqual(self.inputs, {name: (self.source / name).read_bytes() for name in self.inputs})
        again = self.prepare()
        self.assertEqual(again["outputs"][0]["before"], again["outputs"][0]["after"])

    def testDifferentSourceStateReceivesNoCompatibilityOrRecipeChange(self):
        for name, data in self.inputs.items():
            with self.subTest(name=name):
                (self.source / name).write_bytes(data + b"\n")
                self.assertFalse(preparation.preparationRequired(self.source))
                self.assertEqual([], preparation.preparationArguments(self.source))
                self.assertEqual("not-required", self.prepare()["status"])
                self.assertFalse((self.source / replay.TARGET).exists())
                (self.source / name).write_bytes(data)

    def portableFixture(self):
        result = self.prepare()
        evidence = self.source / "recovery"
        evidence.mkdir()
        (evidence / "source-preparation.json").write_text(json.dumps(result))
        (evidence / replay.ATTACHMENT).write_bytes(replay.HEADER)
        (self.source / replay.TARGET).unlink()
        return evidence

    def testPortableReplayPreservesOriginalsAndRejectsChangedProofOrInputs(self):
        evidence = self.portableFixture()
        self.assertTrue(replay.prepareReflection(self.source, evidence))
        self.assertFalse(replay.prepareReflection(self.source, evidence))
        self.assertEqual(self.inputs, {name: (self.source / name).read_bytes() for name in self.inputs})
        (self.source / replay.TARGET).unlink()
        original = self.source / "CReflection.h"
        original.write_bytes(original.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "original inputs"):
            replay.prepareReflection(self.source, evidence)
        original.write_bytes(self.inputs["CReflection.h"])
        (evidence / replay.ATTACHMENT).write_bytes(b"changed macro")
        with self.assertRaisesRegex(ValueError, "reviewed bytes"):
            replay.prepareReflection(self.source, evidence)
        self.assertFalse((self.source / replay.TARGET).exists())

    def testSymlinkAndConflictingOutputAreRejected(self):
        target = self.source / replay.TARGET
        protected = self.root / "protected"
        protected.write_bytes(b"preserve")
        target.symlink_to(protected)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            self.prepare()
        self.assertEqual(b"preserve", protected.read_bytes())
        target.unlink()
        target.write_bytes(b"preexisting user bytes")
        with self.assertRaisesRegex(ValueError, "differs"):
            self.prepare()
        self.assertEqual(b"preexisting user bytes", target.read_bytes())

    @unittest.skipUnless(shutil.which("c++"), "A native C++ compiler is needed for the registration regression")
    def testOriginalNamedConstructorFailsThenParentMacroRegistersBothTypes(self):
        source = self.source / "ReflectTypes.cpp"
        binary = self.root / "registration"
        command = [shutil.which("c++"), "-std=c++11", "-I" + str(self.source), str(source), "-o", str(binary)]
        before = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(0, before.returncode)
        self.assertIn("CReflectionHelper", before.stderr)
        self.prepare()
        after = subprocess.run(
            [command[0], "-include", str(self.source / replay.TARGET), *command[1:]],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(0, after.returncode, after.stderr)
        self.assertEqual(0, subprocess.run([str(binary)], timeout=10).returncode)


if __name__ == "__main__":
    unittest.main()
