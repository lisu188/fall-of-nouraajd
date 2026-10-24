# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable API regression plus an opt-in tiny probe; neither builds the game."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def diagnosticsSource():
    source = (ROOT / "src/core/CLoader.cpp").read_text(encoding="utf-8")
    start = source.index("class SaveStageDiagnostics {")
    return source[start : source.index("\n};", start) + len("\n};")]


def controllerSnapshotProbeSource():
    source = (ROOT / "tests/unit/test_map.cpp").read_text(encoding="utf-8")
    start = source.index("void testMapPausedPlayerControllerRoundTripsWithoutReset()")
    begin = source.index("    int paused_definitions = 0;", start)
    end = source.index("    expect_true(paused_definitions", begin)
    walk = source[begin:end]
    return (
        '#include "core/CJson.h"\n#include <memory>\n'
        + "struct Named { std::string name; const std::string &getName() const { return name; } };\n"
        + "int main() {\n"
        + '    auto original = std::make_shared<Named>(Named{"original"});\n'
        + '    auto paused = std::make_shared<Named>(Named{"paused"});\n'
        + "    auto document = std::make_shared<json>(json::object());\n"
        + walk
        + "    return paused_definitions + original_definitions;\n}\n"
    )


def nativeProbeSource():
    return (
        '#include "core/CJson.h"\n#include <chrono>\n#include <cstdio>\n#include <cstdlib>\n'
        + diagnosticsSource()
        + r"""
int main(int argc, char **argv) {
    if (argc != 2)
        return 2;
    const int shape = std::atoi(argv[1]);
    json snapshot;
    switch (shape) {
    case 0: snapshot = json::object(); break;
    case 1: snapshot = json::array({1, 2}); break;
    case 2: snapshot = {{"properties", 5}}; break;
    case 3: snapshot = {{"properties", json::object()}}; break;
    case 4:
        snapshot = {{"properties", {{"objects", json::array({1, 2, 3})}, {"tiles", json::array({4, 5})}}}};
        break;
    case 5:
        snapshot = {{"properties", {{"objects", {{"privatePayload", "never log this"}}}, {"tiles", "bad rows"}}}};
        break;
    case 6: snapshot = {{"properties", {{"objects", json::array()}}}}; break;
    case 7: snapshot = {{"properties", {{"objects", false}, {"tiles", json::array({1, 2})}}}}; break;
    case 8: snapshot = {{"properties", {{"tiles", json::array({1, 2, 3})}}}}; break;
    default: return 3;
    }
    const auto before = snapshot.dump();
    SaveStageDiagnostics diagnostics;
    diagnostics.graphFinished(snapshot);
    if (snapshot.dump() != before)
        return 4;
    return 0;
}
"""
    )


class SaveStageJsonApiSourceTest(unittest.TestCase):
    def testDiagnosticMemberCallsBelongToTheRepositoryJsonApi(self):
        header = (ROOT / "src/core/CJson.h").read_text(encoding="utf-8")
        public_api = header.split("class json {", 1)[1].split("  private:", 1)[0]
        methods = set(
            re.findall(r"^\s*(?:static\s+)?(?:const\s+)?[\w:<>]+[ \t&*]+(\w+)\s*\(", public_api, re.MULTILINE)
        )
        diagnostics = diagnosticsSource()
        graph = diagnostics[diagnostics.index("void graphFinished(") : diagnostics.index("\n  private:")]
        calls = set(re.findall(r"(?:\.|->)\s*(\w+)\s*\(", graph))
        self.assertTrue({"contains", "at", "is_object", "is_array", "size"}.issubset(methods))
        self.assertEqual(set(), calls - methods, "Save diagnostics must use the actual repository JSON API")

    def testControllerSnapshotWalkCompilesAgainstActualJsonHeader(self):
        if os.name != "posix":
            self.skipTest("Header-only syntax regression requires a POSIX C++ compiler")
        compiler = shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")
        if not compiler:
            self.skipTest("No C++ compiler is available for the header-only syntax regression")
        result = subprocess.run(
            [compiler, "-std=c++23", "-fsyntax-only", "-x", "c++", "-", "-I" + str(ROOT / "src")],
            input=controllerSnapshotProbeSource(),
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr[-1800:])


@unittest.skipUnless(os.environ.get("GAME_RUN_SAVE_JSON_API_PROBE") == "1", "Tiny native JSON probe is opt-in")
class SaveStageJsonApiNativeProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name != "posix":
            raise unittest.SkipTest("The isolated GNU/Clang link probe requires a POSIX compiler")
        compiler = shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")
        if not compiler:
            raise unittest.SkipTest("No C++ compiler is available for the isolated JSON probe")
        cls.temporary = tempfile.TemporaryDirectory(prefix="nouraajd-save-json-api-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.executable = Path(cls.temporary.name) / "save-json-api"
        command = [
            compiler,
            "-std=c++23",
            "-O0",
            "-ffunction-sections",
            "-fdata-sections",
            "-I" + str(ROOT / "src"),
            "-I" + str(ROOT / "third_party/simdjson"),
            "-x",
            "c++",
            "-",
            str(ROOT / "src/core/CJson.cpp"),
            "-Wl,--gc-sections",
            "-o",
            str(cls.executable),
        ]
        result = subprocess.run(command, input=nativeProbeSource(), text=True, capture_output=True, timeout=60)
        if result.returncode:
            raise AssertionError("Actual JSON diagnostics probe failed to compile:\n" + result.stderr[-900:])

    def runProbe(self, shape, flag):
        environment = os.environ.copy()
        environment.pop("GAME_SAVE_STAGE_DIAGNOSTICS", None)
        if flag is not None:
            environment["GAME_SAVE_STAGE_DIAGNOSTICS"] = flag
        result = subprocess.run(
            [str(self.executable), str(shape)], env=environment, text=True, capture_output=True, timeout=5
        )
        self.assertEqual(0, result.returncode, result.stderr[-900:])
        self.assertEqual("", result.stdout)
        return result.stderr

    def testDiagnosticsStaySilentUnlessExactlyEnabledEvenForMalformedShapes(self):
        for flag in (None, "", "0", "01", "10", "true"):
            for shape in (0, 1, 2, 4, 5):
                with self.subTest(flag=flag, shape=shape):
                    self.assertEqual("", self.runProbe(shape, flag))

    def testEnabledCountsUseOnlyArrayRowsAndKeepEverySnapshotUnchanged(self):
        for shape, expected in enumerate(((0, 0), (0, 0), (0, 0), (0, 0), (3, 2), (0, 0), (0, 0), (0, 2), (0, 3))):
            with self.subTest(shape=shape):
                records = self.runProbe(shape, "1").splitlines()
                self.assertEqual(1, len(records))
                record = json.loads(records[0])
                self.assertEqual(expected, (record["objects"], record["tiles"]))
                self.assertEqual("save-stage", record["diagnostic"])
                self.assertEqual("graph.end", record["stage"])
                self.assertEqual(0, record["bytes"])
                self.assertIs(True, record["success"])
                self.assertGreaterEqual(record["elapsedMicroseconds"], 0)
                self.assertNotIn("privatePayload", records[0])


if __name__ == "__main__":
    unittest.main()
