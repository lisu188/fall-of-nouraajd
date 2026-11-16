# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source generation must precede qmake and retain an auditable overlay."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import history_source_prep as preparation
from scripts import verify_history as verify


class HistoricalSourcePreparationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="history-source-prep-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        (self.source / "src").mkdir(parents=True)
        self.output = self.root / "preparation"
        self.recipe = {"pythonAbi": "2.7", "environment": {"PYTHONHOME": "/locked/python/2.7.18"}}
        self.calls = []
        self.version = "Python 2.7.18"

    def runCommand(self, command, cwd, environment, timeout, log):
        self.calls.append(command)
        self.assertEqual("/locked/python/2.7.18/bin/python2.7", command[0])
        self.assertEqual("1", environment["PYTHONDONTWRITEBYTECODE"])
        if command[1:] == ["--version"]:
            log.write_text(self.version + "\n")
            return {"command": command, "returnCode": 0, "timedOut": False, "log": str(log)}
        result = subprocess.run([sys.executable, *command[1:]], cwd=cwd, capture_output=True, text=True)
        log.write_text(result.stdout + result.stderr)
        return {"command": command, "returnCode": result.returncode, "timedOut": False, "log": str(log)}

    def generator(self, suffix=""):
        (self.source / "classes.json").write_text(json.dumps({"Damage": [{"name": "normal", "type": "int"}]}))
        (self.source / "macro.conf").write_text("new real helper\n")
        (self.source / "src/Stats.h").write_text('Q_OBJECT\n#include "../gen/prop.h"\nold helper\n')
        (self.source / "preprocessor.py").write_text(
            "import json, os\n"
            "config = json.load(open('classes.json'))\n"
            "try: os.mkdir('gen')\n"
            "except OSError: pass\n"
            "prop = config['Damage'][0]\n"
            "open('gen/prop.h', 'w').write('Q_PROPERTY(%s %s)' % (prop['type'], prop['name']))\n"
            "header = 'src/Stats.h'\n"
            "text = open(header).read().replace('old helper', open('macro.conf').read().strip())\n"
            "open(header, 'w').write(text)\n" + suffix
        )

    def testOriginalGeneratorOutputsAndHeaderOverlayAreHashed(self):
        self.generator()
        before = (self.source / "src/Stats.h").read_bytes()
        result = preparation.prepareSources(self.source, self.output, self.recipe, {}, self.runCommand)
        self.assertEqual("success", result["status"])
        self.assertEqual("Q_PROPERTY(int normal)", (self.source / "gen/prop.h").read_text())
        outputs = {entry["path"]: entry for entry in result["outputs"]}
        self.assertEqual({"gen/prop.h", "src/Stats.h"}, set(outputs))
        self.assertIsNone(outputs["gen/prop.h"]["before"])
        self.assertEqual(hashlib.sha256(before).hexdigest(), outputs["src/Stats.h"]["before"]["sha256"])
        self.assertEqual(
            hashlib.sha256((self.source / "src/Stats.h").read_bytes()).hexdigest(),
            outputs["src/Stats.h"]["after"]["sha256"],
        )
        self.assertEqual(["--version"], self.calls[0][1:])
        self.assertEqual("-B", self.calls[1][1])
        self.assertEqual({"preprocessor.py", "classes.json", "macro.conf"}, set(result["identity"]["inputs"]))

    def testAbsentGeneratorHasNoRuntimeOrSourceSideEffects(self):
        before = preparation.sourceManifest(self.source)
        result = preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
        self.assertEqual("not-required", result["status"])
        self.assertEqual([], self.calls)
        self.assertEqual(before, preparation.sourceManifest(self.source))
        self.assertFalse(self.output.exists())

    def testWrongInterpreterVersionStopsBeforeRunningOriginalCode(self):
        self.generator()
        before = preparation.sourceManifest(self.source)
        self.version = "Python 3.12.9"
        result = preparation.prepareSources(self.source, self.output, self.recipe, {}, self.runCommand)
        self.assertEqual("failed", result["status"])
        self.assertEqual(1, len(self.calls))
        self.assertEqual(before, preparation.sourceManifest(self.source))

    def testGeneratorFailureRetainsPartialOutputAndItsLog(self):
        self.generator("raise RuntimeError('historical generation failed')\n")
        result = preparation.prepareSources(self.source, self.output, self.recipe, {}, self.runCommand)
        self.assertEqual("failed", result["status"])
        self.assertIn("gen/prop.h", [entry["path"] for entry in result["outputs"]])
        self.assertIn("historical generation failed", (self.output / "generator.log").read_text())

    def testUnexpectedDescriptorMutationFailsClosed(self):
        self.generator("open('classes.json', 'w').write('{}')\n")
        result = preparation.prepareSources(self.source, self.output, self.recipe, {}, self.runCommand)
        self.assertEqual("failed", result["status"])
        self.assertIn("classes.json", result["reason"])

    def testMissingGeneratorInputAndWrongAbiFailBeforeExecution(self):
        self.generator()
        for recipe, remove in (({"pythonAbi": "3.3"}, False), (self.recipe, True)):
            if remove:
                (self.source / "macro.conf").unlink()
            with self.subTest(recipe=recipe), self.assertRaises(ValueError):
                preparation.prepareSources(self.source, self.output, recipe, {}, self.runCommand)
        self.assertEqual([], self.calls)

    def testVerifierGeneratesPropertiesBeforeQmakeAndPreservesRestoredInputIdentity(self):
        def restore(repo, catalog, commit, source, overrides):
            self.source = source
            (source / "src").mkdir(parents=True)
            self.generator()
            (source / "game.pro").write_text("LIBS += -lpython2.7\nSOURCES += src/main.cpp\nHEADERS += src/Stats.h\n")
            (source / "src/main.cpp").write_text('int main() {}\nvoid save() { fopen("save/game.sav", "w+"); }\n')
            return {"restoredFilesFingerprint": "original-restored-files"}

        configured = []

        def run(command, cwd, environment, timeout, log):
            if command[0].endswith("python2.7"):
                return self.runCommand(command, cwd, environment, timeout, log)
            if command[0] == "qmake":
                self.assertTrue((self.source / "gen/prop.h").is_file())
                self.assertIn("new real helper", (self.source / "src/Stats.h").read_text())
                configured.append(command)
            if command[0] == "make":
                (cwd / "RecoveryGame").write_bytes(b"fixture executable")
            log.write_text("fixture command succeeded\n")
            return {"command": command, "returnCode": 0, "timedOut": False, "log": str(log)}

        def smoke(command, cwd, *args, **kwargs):
            self.assertTrue((cwd / "save").is_dir())
            self.assertFalse((cwd / "save/game.sav").exists())
            return {"status": "success"}

        with mock.patch("scripts.recover_history.restoreSnapshot", side_effect=restore), mock.patch.object(
            verify, "toolchainFingerprint", return_value={}
        ), mock.patch.object(
            verify, "prepareSmokeAdapter", return_value={"configSha256": "observer"}
        ), mock.patch.object(
            verify, "prepareLibraryAliases", return_value={"aliases": {}}
        ), mock.patch.object(
            verify, "runCommand", side_effect=run
        ), mock.patch.object(
            verify, "runSmoke", side_effect=smoke
        ), mock.patch.object(
            verify, "exportEvidence"
        ):
            result = verify.verifySnapshot(
                self.root, {}, {"commits": ["original"], "tree": "tree"}, self.root / "verification", [self.recipe]
            )
        self.assertEqual("success", result["status"], result)
        self.assertEqual(1, len(configured))
        self.assertEqual("original-restored-files", result["restoration"]["restoredFilesFingerprint"])
        self.assertEqual("success", result["sourcePreparation"]["status"])
        self.assertEqual("ready", result["runtimePreparation"]["status"])
        self.assertEqual("save", result["runtimePreparation"]["identity"]["directories"][0]["path"])
        self.assertEqual(
            {"gen/prop.h", "src/Stats.h"}, {entry["path"] for entry in result["sourcePreparation"]["outputs"]}
        )

    def windowsInclude(self, name=r"view\playerlistview.h"):
        (self.source / "view").mkdir(exist_ok=True)
        (self.source / "view/playerlistview.h").write_text("struct PlayerListView {};\n")
        source = self.source / "view/gamescene.cpp"
        source.write_bytes(('#include "' + name + '"\r\nPlayerListView view;\r\n').encode())
        return source

    def testLiteralWindowsIncludeIsPreparedWithoutPythonAndRetainsExactHashes(self):
        source = self.windowsInclude()
        before = source.read_bytes()
        self.assertTrue(preparation.preparationRequired(self.source))
        result = preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
        self.assertEqual("success", result["status"])
        self.assertEqual([], self.calls)
        self.assertEqual(before.replace(b"view\\playerlistview.h", b"view/playerlistview.h"), source.read_bytes())
        self.assertEqual("windowsIncludeSeparators", result["steps"][0]["name"])
        output = result["outputs"][0]
        self.assertEqual("view/gamescene.cpp", output["path"])
        self.assertEqual(hashlib.sha256(before).hexdigest(), output["before"]["sha256"])
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), output["after"]["sha256"])
        include = result["identity"]["includeSeparators"][0]["includes"][0]
        self.assertEqual("view/playerlistview.h", include["resolvedHeader"])
        self.assertEqual(1, include["line"])
        self.assertIn("view/gamescene.cpp", (self.output / "include-separators.log").read_text())

    def testCommentsStringsAndDefinitelyInactiveIncludesStayByteIdentical(self):
        source = self.windowsInclude()
        ignored = (
            b'/*\n#include "missing\\comment.h"\n*/\n'
            b'// #include "missing\\line.h"\n'
            b'const char *text = R"raw(\n#include "missing\\raw.h"\n)raw";\n'
            b'const char *escaped = "continued\\\n#include \\"missing\\\\string.h\\"";\n'
            b'#if 0\n#include "missing\\disabled.h"\n#endif\n'
        )
        source.write_bytes(ignored + source.read_bytes())
        result = preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
        self.assertEqual("success", result["status"])
        self.assertTrue(source.read_bytes().startswith(ignored))
        self.assertEqual(1, len(result["identity"]["includeSeparators"][0]["includes"]))

    def testEscapingMissingAmbiguousOrSymlinkedIncludesFailBeforeSourceMutation(self):
        for name in (r"C:\private\header.h", r"\private\header.h", r"..\..\outside.h", r"view\absent.h"):
            with self.subTest(include=name):
                self.windowsInclude(name)
                before = preparation.sourceManifest(self.source)
                with self.assertRaises(ValueError):
                    preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
                self.assertEqual(before, preparation.sourceManifest(self.source))
        self.windowsInclude()
        (self.source / "view/view").mkdir()
        (self.source / "view/view/playerlistview.h").write_text("ambiguous local header\n")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
        (self.source / "view/view/playerlistview.h").unlink()
        (self.source / "view/playerlistview.h").unlink()
        external = self.root / "external.h"
        external.write_text("external header\n")
        (self.source / "view/playerlistview.h").symlink_to(external)
        with self.assertRaisesRegex(ValueError, "escapes"):
            preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)

    def testGeneratorAndIncludeCompatibilityShareOneAuditedPreparation(self):
        self.generator()
        self.windowsInclude()
        result = preparation.prepareSources(self.source, self.output, self.recipe, {}, self.runCommand)
        self.assertEqual("success", result["status"])
        self.assertEqual(
            ["windowsIncludeSeparators", "interpreter", "generator"], [step["name"] for step in result["steps"]]
        )
        self.assertEqual(
            {"view/gamescene.cpp", "gen/prop.h", "src/Stats.h"}, {entry["path"] for entry in result["outputs"]}
        )

    @unittest.skipUnless(shutil.which("c++"), "C++ preprocessor unavailable")
    def testActualPreprocessorFailsBeforeAndPassesAfterIncludePreparation(self):
        source = self.windowsInclude()
        command = [shutil.which("c++"), "-E", "-I", str(self.source), str(source)]
        before = subprocess.run(command, capture_output=True)
        self.assertNotEqual(0, before.returncode)
        preparation.prepareSources(self.source, self.output, {}, {}, self.runCommand)
        after = subprocess.run(command, capture_output=True)
        self.assertEqual(0, after.returncode, after.stderr.decode(errors="replace"))

    def testRuntimeSaveDirectoryComesFromTheLiteralOriginalWriterWithoutFileChanges(self):
        original = self.source / "src/scene.cpp"
        original.write_text(
            '// fopen("save/game.sav", "w+")\n'
            'const char *text = R"(fopen("save/game.sav", "w+"))";\n'
            'void save() { FILE *file = fopen("save/game.sav", "w+"); fclose(file); }\n'
        )
        before = preparation.sourceManifest(self.source)
        plan = preparation.runtimeDirectoryPlan(self.source)
        self.assertEqual(1, len(plan[0]["requiredBy"]))
        self.assertEqual(3, plan[0]["requiredBy"][0]["line"])
        result = preparation.prepareRuntimeDirectories(self.source, plan)
        self.assertEqual("ready", result["status"])
        self.assertEqual([{"path": "save", "created": True, "preservedExisting": False}], result["directories"])
        self.assertTrue((self.source / "save").is_dir())
        self.assertEqual(before, preparation.sourceManifest(self.source))

    def testRuntimePreparationPreservesExistingSaveAndRejectsUnsafeDirectory(self):
        plan = [{"path": "save", "requiredBy": [{"source": "scene.cpp"}]}]
        (self.source / "save").mkdir()
        saved = self.source / "save/game.sav"
        saved.write_bytes(b"unique user save")
        result = preparation.prepareRuntimeDirectories(self.source, plan)
        self.assertEqual(b"unique user save", saved.read_bytes())
        self.assertTrue(result["directories"][0]["preservedExisting"])
        saved.unlink()
        (self.source / "save").rmdir()
        (self.source / "save").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            preparation.prepareRuntimeDirectories(self.source, plan)
        with self.assertRaisesRegex(ValueError, "evidenced"):
            preparation.prepareRuntimeDirectories(self.source, [{"path": "../save", "requiredBy": ["invalid"]}])


if __name__ == "__main__":
    unittest.main()
