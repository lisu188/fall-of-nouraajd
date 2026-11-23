# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Original-coordinate hash compatibility preserves the authored hasher and source bytes."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import history_prepare_coordinates as replay
from scripts import history_source_prep as preparation
from scripts import verify_history as verify


class HistoricalCoordinatePreparationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.inputs = {
            "map/coords.h": (
                b"#pragma once\n#include <cstddef>\n"
                b"struct Coords { int x,y,z; bool operator==(const Coords &v) const { return x==v.x && y==v.y && z==v.z; } };\n"
                b"struct CoordsHasher { std::size_t operator()(const Coords &v) const; };\n"
            ),
            "map/coords.cpp": b'#include "coords.h"\nstd::size_t CoordsHasher::operator()(const Coords &v) const { return v.x*17+v.y*3+v.z; }\n',
            "pathfinder/smartpathfinder.cpp": (
                b'#include "map/coords.h"\n#include <unordered_map>\n'
                b"int main() { Coords v{2,3,1}; std::unordered_map<Coords,int> values; values[v]=7; "
                b"return std::hash<Coords>()(v)==CoordsHasher()(v) && values[v]==7 ? 0 : 1; }\n"
            ),
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
        self.fail("Hash compatibility preparation cannot execute historical programs")

    def prepare(self):
        return preparation.prepareSources(self.source, self.root / "proof", {}, {}, self.runCommand)

    def testOnlyExactOriginalInputsReceiveTheArgumentAndSeparateHeader(self):
        recipe = {"id": "fixture", "pythonAbi": "none", "qmakeArguments": []}
        selected = verify.selectRecipe([recipe], self.source, "fixture")
        self.assertEqual([replay.ARGUMENT], selected["qmakeArguments"])
        result = self.prepare()
        self.assertEqual("success", result["status"])
        self.assertEqual([replay.TARGET], [entry["path"] for entry in result["outputs"]])
        self.assertEqual(self.inputs, {name: (self.source / name).read_bytes() for name in self.inputs})
        self.assertEqual(["coordinatesHash"], [step["name"] for step in result["steps"]])
        for name, data in self.inputs.items():
            (self.source / name).write_bytes(data + b"\n")
            self.assertIsNone(replay.coordinateHashPlan(self.source))
            self.assertEqual([], preparation.preparationArguments(self.source))
            (self.source / name).write_bytes(data)

    def testPortableReplayIsIdempotentAndRejectsChangedOriginalHasher(self):
        result = self.prepare()
        evidence = self.source / "recovery"
        evidence.mkdir()
        (evidence / "source-preparation.json").write_text(json.dumps(result))
        (evidence / replay.ATTACHMENT).write_bytes(replay.HEADER)
        (self.source / replay.TARGET).unlink()
        self.assertTrue(replay.prepareCoordinateHash(self.source, evidence))
        self.assertFalse(replay.prepareCoordinateHash(self.source, evidence))
        (self.source / replay.TARGET).unlink()
        (self.source / "map/coords.cpp").write_bytes(b"changed hasher")
        with self.assertRaisesRegex(ValueError, "original inputs"):
            replay.prepareCoordinateHash(self.source, evidence)
        self.assertFalse((self.source / replay.TARGET).exists())

    def testConflictingAndSymlinkedOutputsArePreserved(self):
        target = self.source / replay.TARGET
        protected = self.root / "protected"
        protected.write_bytes(b"preserve")
        target.symlink_to(protected)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            self.prepare()
        self.assertEqual(b"preserve", protected.read_bytes())
        target.unlink()
        target.write_bytes(b"user bytes")
        with self.assertRaisesRegex(ValueError, "differs"):
            self.prepare()
        self.assertEqual(b"user bytes", target.read_bytes())

    @unittest.skipUnless(shutil.which("c++"), "A native C++ compiler is needed for the hashing regression")
    def testUnorderedMapFailsBeforeThenUsesTheAuthoredHasherAfter(self):
        binary = self.root / "coordinates"
        command = [
            shutil.which("c++"),
            "-std=c++11",
            "-I" + str(self.source),
            str(self.source / "pathfinder/smartpathfinder.cpp"),
            str(self.source / "map/coords.cpp"),
            "-o",
            str(binary),
        ]
        before = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(0, before.returncode)
        self.assertIn("hash", before.stderr)
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
