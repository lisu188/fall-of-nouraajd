"""Recover the original entry callback using actual missing-body code and a real Qt timeline.

The small domain fixture isolates animation dispatch; full historical game startup
and rendered-map proof remain separate verification evidence.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/history-movement-195"
PAYLOAD_KEYS = ["42e7bd06f1d9c1ef12947df5fc216c8b6a337bc1", "1635542d44e479a5f3e54a6210ca74cf8cde3e42"]
ENTRIES = {
    entry.get("originalBlob"): entry for entry in json.loads((ROOT / "recovery/overrides.json").read_text())["entries"]
}
PAYLOADS = [ROOT / "recovery" / ENTRIES[key]["source"] for key in PAYLOAD_KEYS if key in ENTRIES]


def functionBlock(text, signature):
    """Extract braces only from these fixed reviewed callback/movement bodies."""
    start = text.index(signature)
    cursor = text.index("{", start) + 1
    depth = 1
    while depth:
        if text[cursor] == "{":
            depth += 1
        if text[cursor] == "}":
            depth -= 1
        cursor += 1
    return text[start:cursor]


def recoveredFunctions(payload):
    text = payload.read_text()
    return (
        functionBlock(text, "class ReconstructedPlayerAnimation")
        + ";\n"
        + functionBlock(text, "void ReconstructedPlayerAnimation::afterAnimationStep")
        + "\n"
        + functionBlock(text, "void MapObject::moveTo(")
    )


class HistoricalMovementCompletionTest(unittest.TestCase):
    def testRecoveredBodiesPreserveOriginalCompletionCallback(self):
        self.assertTrue(PAYLOADS, "The recovered #195 movement body must be present")
        original = functionBlock(
            (FIXTURE / "original-playeranimation.cpp").read_text(), "void PlayerAnimation::afterAnimationStep"
        ).replace("void PlayerAnimation::afterAnimationStep", "void ReconstructedPlayerAnimation::afterAnimationStep")
        for payload in PAYLOADS:
            with self.subTest(payload=payload.name):
                text = payload.read_text()
                self.assertEqual(original, functionBlock(text, "void ReconstructedPlayerAnimation::afterAnimationStep"))
                self.assertIn("new ReconstructedPlayerAnimation(this)", functionBlock(text, "void MapObject::moveTo("))

    @unittest.skipUnless(os.name == "posix", "Native Qt callback regression requires a POSIX Xvfb environment")
    def testRealTimelineDispatchesEntryExactlyOnceAfterMovement(self):
        compiler = shutil.which("g++-5") or shutil.which("g++") or shutil.which("c++")
        qmake = shutil.which("qmake")
        if not all([compiler, qmake, shutil.which("xvfb-run"), shutil.which("xauth")]):
            self.skipTest("A C++ compiler, Qt5 qmake, Xvfb and xauth are needed for the native callback regression")
        version = subprocess.check_output([qmake, "-query", "QT_VERSION"], text=True).strip()
        if not version.startswith("5."):
            self.skipTest("This historical regression requires Qt5")
        headers = Path(subprocess.check_output([qmake, "-query", "QT_INSTALL_HEADERS"], text=True).strip())
        libraries = Path(subprocess.check_output([qmake, "-query", "QT_INSTALL_LIBS"], text=True).strip())
        flags = [
            "-I" + str(headers),
            *["-I" + str(headers / name) for name in ["QtWidgets", "QtGui", "QtCore"]],
            "-L" + str(libraries),
            "-lQt5Widgets",
            "-lQt5Gui",
            "-lQt5Core",
            "-lpthread",
        ]
        cases = [
            ("before", (FIXTURE / "before-move.cpp").read_text(), 10, '"entered":0'),
            ("after", recoveredFunctions(PAYLOADS[0]), 0, '"entered":1'),
        ]
        with tempfile.TemporaryDirectory(prefix="history-movement-") as temporary:
            for name, functions, expected_code, expected_events in cases:
                with self.subTest(case=name):
                    source = Path(temporary) / (name + ".cpp")
                    source.write_text((FIXTURE / "domain.cpp").read_text().replace("// RECOVERED_FUNCTIONS", functions))
                    binary = Path(temporary) / name
                    compiled = subprocess.run(
                        [compiler, "-std=c++11", "-fPIC", "-O2", str(source), "-o", str(binary), *flags],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self.assertEqual(0, compiled.returncode, compiled.stderr)
                    result = subprocess.run(
                        ["xvfb-run", "-a", "--server-args=-screen 0 1280x720x24", str(binary)],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1"},
                    )
                    self.assertEqual(expected_code, result.returncode, result.stdout + result.stderr)
                    self.assertIn(expected_events, result.stdout)
                    self.assertIn('"pixelX":50', result.stdout)


if __name__ == "__main__":
    unittest.main()
