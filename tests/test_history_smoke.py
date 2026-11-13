# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression checks for historical startup evidence and watchdog handling."""

from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

from scripts import verify_history as verify


def pngBytes():
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    return (
        verify.PNG_SIGNATURE
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0\xff\0\xff\0\xff"))
        + chunk(b"IEND", b"")
    )


class HistoricalSmokeTest(unittest.TestCase):
    def runFixture(self, code, timeout=2):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        fixture = root / "fixture.py"
        fixture.write_text(code, encoding="utf-8")
        return verify.runSmoke([sys.executable, str(fixture)], root, root / "artifacts", timeout=timeout, isolate=False)

    def producer(self, *, checks=None, image=None):
        checks = {name: True for name in verify.REQUIRED_CHECKS} if checks is None else checks
        image = pngBytes() if image is None else image
        return (
            "import json, os\nfrom pathlib import Path\n"
            "report = Path(os.environ['GAME_RECOVERY_SMOKE_REPORT'])\n"
            f"report.with_suffix('.png').write_bytes({image!r})\n"
            f"checks = {checks!r}\n"
            "report.write_text(json.dumps({'schemaVersion': 1, 'status': 'ready', 'checks': checks, "
            "'frame': {'path': str(report.with_suffix('.png')), 'width': 2, 'height': 1}}))\n"
        )

    def testCleanExitWithoutGameReadinessFails(self):
        result = self.runFixture("raise SystemExit(0)\n")
        self.assertEqual("failed", result["status"])
        self.assertIn("without a startup-readiness report", result["reason"])

    def testValidFrameAndAllGameChecksPass(self):
        result = self.runFixture(self.producer())
        self.assertEqual("success", result["status"], result)
        self.assertEqual(0, result["returnCode"])

    def testMissingMapOrPlayerFails(self):
        for missing in ("map", "player", "eventLoop", "renderedFrame"):
            with self.subTest(missing=missing):
                checks = {name: name != missing for name in verify.REQUIRED_CHECKS}
                result = self.runFixture(self.producer(checks=checks))
                self.assertEqual("failed", result["status"])
                self.assertIn("evidence", result["reason"])

    def testInvalidFrameFails(self):
        for image in (b"", b"not a png", pngBytes()[:-4]):
            with self.subTest(image=image):
                self.assertEqual("failed", self.runFixture(self.producer(image=image))["status"])

    def testCrashOverridesReadinessReport(self):
        result = self.runFixture(self.producer() + "raise SystemExit(7)\n")
        self.assertEqual("failed", result["status"])
        self.assertIn("exit 7", result["reason"])

    def testTimeoutCannotBeReportedAsSuccess(self):
        result = self.runFixture(self.producer() + "import time\ntime.sleep(30)\n", timeout=0.15)
        self.assertEqual("failed", result["status"])
        self.assertTrue(result["timedOut"])
        self.assertIn("watchdog", result["reason"])

    def testObserverDoesNotReplaceHistoricalMain(self):
        source = verify.SMOKE_SOURCE.read_text(encoding="utf-8")
        self.assertIn("Q_COREAPP_STARTUP_FUNCTION", source)
        self.assertNotIn("int main(", source)

    def testPngDimensionsMustMatchReport(self):
        code = self.producer() + (
            "value = json.loads(report.read_text())\n"
            "value['frame']['width'] = 3\n"
            "report.write_text(json.dumps(value))\n"
        )
        result = self.runFixture(code)
        self.assertEqual("failed", result["status"])
        self.assertIn("dimensions", result["reason"])

    def testFrameCannotEscapeArtifactDirectory(self):
        code = self.producer() + (
            "value = json.loads(report.read_text())\n"
            "outside = report.parent.parent / 'outside.png'\n"
            "outside.write_bytes(report.with_suffix('.png').read_bytes())\n"
            "value['frame']['path'] = str(outside)\n"
            "report.write_text(json.dumps(value))\n"
        )
        result = self.runFixture(code)
        self.assertEqual("failed", result["status"])
        self.assertIn("escapes", result["reason"])

    def testWindowsAndLinuxPythonLibraryNamesSelectTheMatchingAbi(self):
        recipes = [{"id": f"python-{abi}", "pythonAbi": abi} for abi in ("none", "2.7", "3.3", "3.4")]
        for link, expected in (("-lpython3.4m", "3.4"), ("C:/Python33/libs/python33.lib", "3.3"), ("", "none")):
            with self.subTest(link=link), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "Game.pro").write_text("LIBS += " + link)
                self.assertEqual(expected, verify.selectRecipe(recipes, root, None)["pythonAbi"])

    def testUnknownPythonAbiRequiresAnExplicitRecipe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Game.pro").write_text("LIBS += -lboost_python")
            (root / "scripting.cpp").write_text("#include <boost/python.hpp>")
            with self.assertRaisesRegex(verify.VerificationError, "cannot be inferred"):
                verify.selectRecipe([{"id": "none", "pythonAbi": "none"}], root, None)

    def testPythonTwoModuleInitializationSelectsPythonTwo(self):
        recipes = [{"id": f"python-{abi}", "pythonAbi": abi} for abi in ("none", "2.7", "3.3", "3.4")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Game.pro").write_text("LIBS += -lboost_python")
            (root / "scripting.cpp").write_text('Py_InitModule("game", methods);')
            self.assertEqual("2.7", verify.selectRecipe(recipes, root, None)["pythonAbi"])

    def testIncludedProjectFragmentDeclaresPythonThreeMinor(self):
        recipes = [{"id": f"python-{abi}", "pythonAbi": abi} for abi in ("none", "2.7", "3.3", "3.4")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Game.pro").write_text("include(python.pri)")
            (root / "python.pri").write_text("LIBS += -lpython3.4m")
            (root / "scripting.cpp").write_text("PyModuleDef definition;")
            self.assertEqual("3.4", verify.selectRecipe(recipes, root, None)["pythonAbi"])

    def testQmakeVersionUsesItsSupportedVersionFlag(self):
        completed = mock.Mock(returncode=0, stdout="QMake version 3.0", stderr="")
        with mock.patch.object(verify.shutil, "which", return_value="/usr/bin/qmake"), mock.patch.object(
            verify.subprocess, "run", return_value=completed
        ) as run:
            verify.toolchainFingerprint({"qmakeCommand": "qmake"}, {})
        self.assertEqual(["/usr/bin/qmake", "-v"], run.call_args.args[0])

    def testIdenticalTreesAreSplitWhenCommitRepairsDiffer(self):
        catalog = {"trees": [{"tree": "same-tree", "commits": ["aaa", "bbb", "ccc"]}]}
        overrides = {"entries": [{"commit": "bbb", "path": "game.cpp", "source": "repair.cpp"}]}
        selected = verify.selectTrees(catalog, overrides)
        self.assertEqual([["aaa", "ccc"], ["bbb"]], [tree["commits"] for tree in selected])
        self.assertEqual(["bbb"], verify.selectTrees(catalog, overrides, "bb")[0]["commits"])


if __name__ == "__main__":
    unittest.main()
