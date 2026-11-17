# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression checks for historical startup evidence and watchdog handling."""

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
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
    def runFixture(self, code, timeout=2, startup_mode="game"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        fixture = root / "fixture.py"
        fixture.write_text(code, encoding="utf-8")
        return verify.runSmoke(
            [sys.executable, str(fixture)],
            root,
            root / "artifacts",
            timeout=timeout,
            isolate=False,
            startup_mode=startup_mode,
        )

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

    def editorProducer(self, missing=None):
        code = self.producer(checks={name: name != missing for name in verify.EDITOR_CHECKS})
        return code + (
            "value = json.loads(report.read_text())\n"
            "value['mode'] = 'editor'\n"
            "report.write_text(json.dumps(value))\n"
        )

    def testEditorReportCannotSatisfyGamePlayerRequirements(self):
        result = self.runFixture(self.editorProducer())
        self.assertEqual("failed", result["status"])
        self.assertIn("mode differs", result["reason"])

    def testExplicitEditorRequiresItsOwnMapFrameAndEventLoop(self):
        result = self.runFixture(self.editorProducer(), startup_mode="editor")
        self.assertEqual("success", result["status"], result)
        self.assertNotIn("player", result["startup"]["checks"])
        for missing in verify.EDITOR_CHECKS:
            with self.subTest(missing=missing):
                result = self.runFixture(self.editorProducer(missing), startup_mode="editor")
                self.assertEqual("failed", result["status"])
                self.assertIn("evidence", result["reason"])

    def testGameReportCannotSatisfyAnEditorEntrypoint(self):
        result = self.runFixture(self.producer(), startup_mode="editor")
        self.assertEqual("failed", result["status"])
        self.assertIn("mode differs", result["reason"])

    def testEditorCannotClaimPlayerEvidence(self):
        code = self.editorProducer() + (
            "value = json.loads(report.read_text())\n"
            "value['checks']['player'] = True\n"
            "report.write_text(json.dumps(value))\n"
        )
        result = self.runFixture(code, startup_mode="editor")
        self.assertEqual("failed", result["status"])
        self.assertIn("cannot claim player", result["reason"])

    def editorFixture(self, root, *, editor=True, extra_statement="", registration=""):
        repo = root / "original"
        (repo / "config").mkdir(parents=True)
        (repo / "main.cpp").write_text(
            '#include "view/mapview.h"\n'
            "int main(int argc, char *argv[]) { QApplication a(argc,argv); QGraphicsView *view;"
            + registration
            + 'bool editor=(*ConfigurationProvider::getConfig("config/init.json")).get("editor",false).asBool();'
            "if(editor) { view=new MapView(); } else { view=new GameView(); }"
            + extra_statement
            + "int ret=a.exec(); delete view; return ret; }\n"
        )
        (repo / "config/init.json").write_text(json.dumps({"editor": editor}))
        subprocess.run(["git", "init", "-q", "-b", "recovery-test", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "main.cpp", "config/init.json"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=Recovery Test",
                "-c",
                "user.email=recovery@example.invalid",
                "commit",
                "-qm",
                "Original editor entrypoint",
            ],
            check=True,
        )
        commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
        source = root / "source"
        (source / "config").mkdir(parents=True)
        for name in ("main.cpp", "config/init.json"):
            shutil.copyfile(repo / name, source / name)
        return repo, source, commit

    def testEditorSelectionPinsSurvivingMainAndConfigurationBytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, source, commit = self.editorFixture(Path(temporary))
            original = (source / "main.cpp").read_bytes(), (source / "config/init.json").read_bytes()
            selection = verify.selectStartupMode(repo, commit, source)
            self.assertEqual("editor", selection["mode"])
            self.assertEqual(["main.cpp", "config/init.json"], [item["path"] for item in selection["originalInputs"]])
            self.assertTrue(
                all(len(item["blob"]) == 40 and len(item["sha256"]) == 64 for item in selection["originalInputs"])
            )
            self.assertEqual(original, ((source / "main.cpp").read_bytes(), (source / "config/init.json").read_bytes()))

    def testDonorEditorFlagCannotReplaceTheSurvivingGameConfiguration(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, source, commit = self.editorFixture(Path(temporary), editor=False)
            self.assertEqual("game", verify.selectStartupMode(repo, commit, source)["mode"])
            (source / "config/init.json").write_text(json.dumps({"editor": True}))
            with self.assertRaisesRegex(verify.VerificationError, "differs from surviving original config/init.json"):
                verify.selectStartupMode(repo, commit, source)

    def testDonorGameFlagCannotChangeTheSurvivingEditorRoute(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, source, commit = self.editorFixture(Path(temporary))
            (source / "config/init.json").write_text(json.dumps({"editor": False}))
            with self.assertRaisesRegex(verify.VerificationError, "differs from surviving original config/init.json"):
                verify.selectStartupMode(repo, commit, source)

    def testReconstructedMainCannotSelectTheEditorObserver(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, source, commit = self.editorFixture(Path(temporary))
            with (source / "main.cpp").open("a") as stream:
                stream.write("// reconstructed donor\n")
            with self.assertRaisesRegex(verify.VerificationError, "differs from surviving original main.cpp"):
                verify.selectStartupMode(repo, commit, source)

    def testUnreviewedOriginalEditorRouteFailsClosed(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, source, commit = self.editorFixture(Path(temporary), extra_statement="view->hide();")
            with self.assertRaisesRegex(verify.VerificationError, "explicitly reviewed startup route"):
                verify.selectStartupMode(repo, commit, source)

    def testReviewedRegistrationRouteRequiresItsExactMainBytes(self):
        registrations = (
            "qRegisterMetaType<Weapon>();qRegisterMetaType<Armor>();qRegisterMetaType<Potion>();",
            "registerMetaTypes();",
        )
        for registration in registrations:
            with self.subTest(registration=registration), tempfile.TemporaryDirectory() as temporary:
                repo, source, commit = self.editorFixture(Path(temporary), registration=registration)
                main_hash = hashlib.sha256((source / "main.cpp").read_bytes()).hexdigest()
                with self.assertRaisesRegex(verify.VerificationError, "explicitly reviewed startup route"):
                    verify.selectStartupMode(repo, commit, source)
                with mock.patch.object(verify, "REVIEWED_EDITOR_MAIN_SHA256", frozenset({main_hash}), create=True):
                    selection = verify.selectStartupMode(repo, commit, source)
                    self.assertEqual("editor", selection["mode"])
                    self.assertEqual(main_hash, selection["originalInputs"][0]["sha256"])
                    with (source / "main.cpp").open("a") as stream:
                        stream.write("// changed original entrypoint\n")
                    with self.assertRaisesRegex(verify.VerificationError, "differs from surviving original main.cpp"):
                        verify.selectStartupMode(repo, commit, source)

    def testReviewedRegistrationRoutePinsBothConfigurationModes(self):
        for editor in (False, True):
            with self.subTest(editor=editor), tempfile.TemporaryDirectory() as temporary:
                repo, source, commit = self.editorFixture(
                    Path(temporary), editor=editor, registration="registerMetaTypes();"
                )
                main_hash = hashlib.sha256((source / "main.cpp").read_bytes()).hexdigest()
                with mock.patch.object(verify, "REVIEWED_EDITOR_MAIN_SHA256", frozenset({main_hash}), create=True):
                    self.assertEqual(
                        "editor" if editor else "game", verify.selectStartupMode(repo, commit, source)["mode"]
                    )
                    (source / "config/init.json").write_text(json.dumps({"editor": not editor}))
                    with self.assertRaisesRegex(
                        verify.VerificationError, "differs from surviving original config/init.json"
                    ):
                        verify.selectStartupMode(repo, commit, source)

    def testEditorAdapterUsesTheRealEditorWithoutAnyPlayerDefinition(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "mapscene.h").write_text("class MapScene : public QGraphicsScene { Map *getMap(); };\n")
            (source / "mapview.h").write_text("class MapView : public QGraphicsView {};\n")
            (source / "map.h").write_text(
                "class Map : public std::unordered_map<Coords,std::string> { "
                "bool contains(int x,int y,int z); QGraphicsScene *getScene(); int getTileSize(); };\n"
            )
            adapter = verify.prepareSmokeAdapter(source, root / "observer", "editor")
            config = Path(adapter["config"]).read_text()
            self.assertEqual("classic-editor", adapter["id"])
            self.assertIn("GAME_RECOVERY_EDITOR 1", config)
            self.assertIn("GAME_RECOVERY_SCENE_TYPE MapScene", config)
            self.assertIn("GAME_RECOVERY_VIEW_TYPE MapView", config)
            self.assertNotIn("GAME_RECOVERY_PLAYER_HEADER", config)

    @unittest.skipUnless(shutil.which("g++") and sys.platform.startswith("linux"), "needs a Linux C++ compiler")
    def testWindowsFileLookupResolvesOnlyMissingPathsCaseInsensitively(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "libwindowspaths.so"
            subprocess.run(
                ["g++", "-shared", "-fPIC", "-std=c++11", "-o", str(library), str(verify.WINDOWS_PATHS_SOURCE), "-ldl"],
                check=True,
            )
            (root / "config/items").mkdir(parents=True)
            (root / "config/items/robe.json").write_text("robe")
            (root / "config/items/Robe2.json").write_text("exact")
            probe = (
                "import sys\n"
                "print(open('Config/ITEMS/Robe.json').read(), open('config/items/Robe2.json').read())\n"
                "try:\n open('config/items/absent.json')\nexcept FileNotFoundError:\n print('absent')\n"
            )
            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=root,
                env={**os.environ, "LD_PRELOAD": str(library)},
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(["robe exact", "absent"], result.stdout.split("\n")[:2])

    def testWindowsImportLibrariesAliasOnlyWhatTheProjectLinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            system = root / "system"
            system.mkdir()
            (system / "libz.so").write_bytes(b"zlib")
            source = root / "source"
            source.mkdir()
            (source / "Game.pro").write_text("SOURCES += main.cpp\n")
            with mock.patch.object(verify, "SYSTEM_LIBRARY_DIRS", (str(system),)):
                self.assertEqual({}, verify.prepareLibraryAliases(source, root / "plain")["aliases"])
                (source / "Game.pro").write_text("unix: LIBS += -L$$PWD/lib/ -lzdll\n")
                result = verify.prepareLibraryAliases(source, root / "linked")
            self.assertEqual({"zdll": str(system / "libz.so")}, result["aliases"])
            self.assertEqual(b"zlib", (Path(result["directory"]) / "libzdll.so").read_bytes())

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

    def testLinuxRecipeIgnoresWindowsAndroidAndUnreferencedProjects(self):
        recipes = [{"id": f"python-{abi}", "pythonAbi": abi} for abi in ("none", "2.7", "3.3", "3.4")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Game.pro").write_text(
                "include(game.pri)\nunix:LIBS += -lpython3.4m\n"
                "win32:LIBS += -lpython34\nandroid {\nLIBS -= -lpython3.4m\nLIBS += -lpython3.3m\n}\n"
            )
            (root / "game.pri").write_text(
                "win32 {\nINCLUDEPATH += C:/Python34/include\n}\n"
                "unix:!android {\nINCLUDEPATH += /usr/local/include/python3.4m\n}\n"
            )
            (root / "vendor").mkdir()
            (root / "vendor/python.pro").write_text("LIBS += -lpython2.7\n")
            self.assertEqual("3.4", verify.selectRecipe(recipes, root, None)["pythonAbi"])

    def testDesktopLinkAbiTakesPrecedenceOverWindowsIncludePaths(self):
        recipes = [{"id": f"python-{abi}", "pythonAbi": abi} for abi in ("3.3", "3.4")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Game.pro").write_text("INCLUDEPATH += C:/Python34/include\nunix:LIBS += -lpython3.3m\n")
            self.assertEqual("3.3", verify.selectRecipe(recipes, root, None)["pythonAbi"])

    def testSingleLinePlatformScopeRetainsItsElseBranch(self):
        recipes = [{"id": f"python-{abi}", "pythonAbi": abi} for abi in ("2.7", "3.3")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "game.pro").write_text("win32 { LIBS += -lpython3.3m }\nelse { LIBS += -lpython2.7 }\n")
            self.assertEqual("2.7", verify.selectRecipe(recipes, root, None)["pythonAbi"])
            (root / "game.pro").write_text("win32 { LIBS += -lpython3.3m } else { LIBS += -lpython2.7 }\n")
            with self.assertRaisesRegex(verify.VerificationError, "inline scopes"):
                verify.selectRecipe(recipes, root, None)

    def testDormantPythonSourcesDoNotOverrideTheDeclaredTarget(self):
        recipes = [{"id": f"python-{abi}", "pythonAbi": abi} for abi in ("none", "2.7", "3.3", "3.4")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "game.pro").write_text("SOURCES += current.cpp\n")
            (root / "current.cpp").write_text("int main() {}\n")
            (root / "obsolete.cpp").write_text("PyModuleDef definition;\n")
            self.assertEqual("none", verify.selectRecipe(recipes, root, None)["pythonAbi"])
            (root / "game.pro").write_text("SOURCES += current.cpp\nLIBS += -lpython2.7\n")
            (root / "current.cpp").write_text('Py_InitModule("game", methods);\n')
            self.assertEqual("2.7", verify.selectRecipe(recipes, root, None)["pythonAbi"])

    def testCaseOnlyProjectRenameSelectsTheProjectWhoseSourcesStillExist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Game.pro").write_text("SOURCES += old/main.cpp\n")
            (root / "game.pro").write_text("SOURCES += CMain.cpp\n")
            (root / "CMain.cpp").write_text("int main() {}\n")
            self.assertEqual(root / "game.pro", verify.selectProjects(root)["application"])
            (root / "old").mkdir()
            (root / "old/main.cpp").write_text("int main() {}\n")
            with self.assertRaisesRegex(verify.VerificationError, "qmake project, found 2"):
                verify.selectProjects(root)

    def testReconstructedProjectCanExplicitlySelectTheCurrentApplication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.cpp").write_text("int main() {}\n")
            (root / "Game.pro").write_text("SOURCES += main.cpp\n")
            (root / "game.pro").write_text("SOURCES += main.cpp\nGAME_RECOVERY_APPLICATION = true\n")
            self.assertEqual(root / "game.pro", verify.selectProjects(root)["application"])

    def testMultipleExplicitReconstructedApplicationsFailClosed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("Game.pro", "game.pro"):
                (root / name).write_text("GAME_RECOVERY_APPLICATION = true\n")
            with self.assertRaisesRegex(verify.VerificationError, "Multiple reconstructed historical application"):
                verify.selectProjects(root)

    def testSubdirProjectsUseDeclaredDependencyOrder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "game").mkdir()
            (root / "python").mkdir()
            (root / "game.pro").write_text("TEMPLATE = subdirs\nSUBDIRS = game python\ngame.depends = python\n")
            (root / "game/game.pro").write_text("TEMPLATE = app\nunix:LIBS += -lpython3.3m\n")
            (root / "python/python.pro").write_text("TEMPLATE = lib\nTARGET = python\n")
            projects = verify.selectProjects(root)
            self.assertEqual(root / "game/game.pro", projects["application"])
            self.assertEqual([root / "python/python.pro"], projects["dependencies"])
            recipes = [{"id": "python33", "pythonAbi": "3.3"}]
            self.assertEqual("python33", verify.selectRecipe(recipes, root, None)["id"])

    def testQmakeIncludesCannotEscapeOrCycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            (root.parent / "outside.pri").write_text("LIBS += -lpython2.7\n")
            for include in ("../outside.pri", "game.pro"):
                with self.subTest(include=include):
                    (root / "game.pro").write_text(f"include({include})\n")
                    with self.assertRaisesRegex(verify.VerificationError, "escapes.*or is cyclic"):
                        verify.selectProjects(root)

    def testMultipleGameApplicationsAndCyclicSubdirsFailClosed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("one", "two"):
                (root / name).mkdir()
                (root / name / (name + ".pro")).write_text("TEMPLATE = app\n")
            (root / "game.pro").write_text("TEMPLATE = subdirs\nSUBDIRS = one two\n")
            with self.assertRaisesRegex(verify.VerificationError, "one historical game application"):
                verify.selectProjects(root)
            with (root / "game.pro").open("a") as project:
                project.write("one.depends = two\ntwo.depends = one\n")
            with self.assertRaisesRegex(verify.VerificationError, "cyclic"):
                verify.selectProjects(root)

    def testPrefixedPlayerCanBeDefinedInTheCombinedCreatureHeader(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "CGameScene.h").write_text("class CGameScene : public QGraphicsScene { CMap *getMap(); };\n")
            (source / "CGameView.h").write_text("class CGameView : public QGraphicsView {};\n")
            (source / "CMap.h").write_text("class CMap { bool contains(int x, int y, int z); };\n")
            (source / "CCreature.h").write_text("class CCreature {};\nclass CPlayer : public CCreature {};\n")
            adapter = verify.prepareSmokeAdapter(source, root / "observer")
            self.assertEqual("prefixed-3d", adapter["id"])
            self.assertIn('GAME_RECOVERY_PLAYER_HEADER "CCreature.h"', Path(adapter["config"]).read_text())
            (source / "CCreature.h").write_text("class CCreature {};\nclass CPlayer;\n")
            with self.assertRaisesRegex(verify.VerificationError, "definition header; found 0"):
                verify.prepareSmokeAdapter(source, root / "missing-player")

    def testPrefixedClassNamesCanKeepTheirOriginalLowercaseHeaderNames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "gamescene.h").write_text("class CGameScene : public QGraphicsScene { CMap *getMap(); };\n")
            (source / "gameview.h").write_text("class CGameView : public QGraphicsView {};\n")
            (source / "CMap.h").write_text(
                "class CMap { CPlayer *getPlayer(); bool contains(int x, int y, int z); };\n"
            )
            (source / "creature.h").write_text("class CCreature {};\nclass CPlayer : public CCreature {};\n")
            adapter = verify.prepareSmokeAdapter(source, root / "observer")
            config = Path(adapter["config"]).read_text()
            self.assertEqual("prefixed-3d", adapter["id"])
            self.assertIn('GAME_RECOVERY_SCENE_HEADER "gamescene.h"', config)
            self.assertIn("GAME_RECOVERY_SCENE_TYPE CGameScene", config)

    def testOnlyTheExactOriginalConsoleLoopClosesTheWindowBeforeExit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            (source / "src").mkdir(parents=True)
            (source / "src/gamescene.h").write_text(
                "class GameScene : public QGraphicsScene { static Player* getPlayer(); Map *getMap(); };\n"
            )
            (source / "src/gameview.h").write_text("class GameView : public QGraphicsView {};\n")
            (source / "src/map.h").write_text("class Map { bool contains(int x, int y, int z); };\n")
            (source / "src/player.h").write_text("class Player {};\n")
            altered = verify.CONSOLE_LOOP.replace(b"isVisible()", b"isVisible() && running")
            (source / "src/main.cpp").write_bytes(b"int main() {\n" + altered + b"}\n")
            plain = verify.prepareSmokeAdapter(source, root / "plain")
            self.assertNotIn("shutdown", plain)
            self.assertNotIn("GAME_RECOVERY_CLOSE_BEFORE_EXIT", Path(plain["config"]).read_text())
            main = b"int main() {\n" + verify.CONSOLE_LOOP + b"}\n"
            (source / "src/main.cpp").write_bytes(main)
            adapter = verify.prepareSmokeAdapter(source, root / "console")
            self.assertIn("#define GAME_RECOVERY_CLOSE_BEFORE_EXIT 1\n", Path(adapter["config"]).read_text())
            self.assertEqual(
                {
                    "mode": "closeWindowAndJoinConsole",
                    "main": {"path": "src/main.cpp", "sha256": hashlib.sha256(main).hexdigest()},
                    "consoleLoopSha256": hashlib.sha256(verify.CONSOLE_LOOP).hexdigest(),
                    "consoleLoopSource": verify.CONSOLE_LOOP_SOURCE,
                    "validationBoundary": verify.CONSOLE_SHUTDOWN_BOUNDARY,
                },
                adapter["shutdown"],
            )
            adapted = b"int main() {\n" + verify.CONSOLE_LOOPS[1] + b"}\n"
            (source / "src/main.cpp").write_bytes(adapted)
            self.assertIn(b"ScriptManager::getInstance()->executeScript(script);", verify.CONSOLE_LOOPS[1])
            self.assertEqual(
                hashlib.sha256(verify.CONSOLE_LOOPS[1]).hexdigest(),
                verify.consoleShutdown(source)["consoleLoopSha256"],
            )
            (source / "src/main.cpp").write_bytes(main + verify.CONSOLE_LOOP)
            self.assertIsNone(verify.consoleShutdown(source))
            (source / "src/main.cpp").write_bytes(main + verify.CONSOLE_LOOPS[1])
            self.assertIsNone(verify.consoleShutdown(source))
            (source / "src/main.cpp").unlink()
            (root / "elsewhere.cpp").write_bytes(main)
            (source / "src/main.cpp").symlink_to(root / "elsewhere.cpp")
            self.assertIsNone(verify.consoleShutdown(source))
        observer = verify.SMOKE_SOURCE.read_text(encoding="utf-8")
        self.assertIn("#define GAME_RECOVERY_CLOSE_BEFORE_EXIT 0", observer)
        self.assertIn("waitForDone(10000)", observer)

    def testTheConsoleLoopIsTheSurvivingOriginal(self):
        source = verify.CONSOLE_LOOP_SOURCE
        try:
            original = subprocess.run(
                ["git", "show", f"{source['commit']}:{source['path']}"],
                cwd=verify.REPO_ROOT,
                capture_output=True,
                check=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("Original history is not available in this checkout")
        self.assertEqual(source["sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(1, original.count(verify.CONSOLE_LOOP))

    def testHistoricalProgramsReadAnEmptyStandardInput(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = "import sys\nsys.exit(0 if sys.stdin.read() == '' else 3)\n"
            result = verify.runCommand([sys.executable, "-c", code], root, dict(os.environ), 10, root / "stdin.log")
            self.assertEqual(0, result["returnCode"])

    def testSubdirSnapshotBuildsLibraryBeforeObservedApplication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def restore(repo, catalog, commit, source, overrides):
                for name in ("game", "python"):
                    (source / name).mkdir(parents=True)
                (source / "game.pro").write_text("TEMPLATE = subdirs\nSUBDIRS = python game\ngame.depends = python\n")
                (source / "game/game.pro").write_text("TEMPLATE = app\nLIBS += -lpython3.3m\n")
                (source / "python/python.pro").write_text("TEMPLATE = lib\nTARGET = python\n")
                return {"restoredFilesFingerprint": "restored-files"}

            def run(command, cwd, environment, timeout, log):
                log.write_text("command succeeded\n")
                if command[0] == "make" and cwd.name == "game":
                    (cwd / "RecoveryGame").write_bytes(b"application")
                return {"command": command, "returnCode": 0, "timedOut": False, "log": str(log)}

            with mock.patch("scripts.recover_history.restoreSnapshot", side_effect=restore), mock.patch.object(
                verify, "toolchainFingerprint", return_value={}
            ), mock.patch.object(
                verify, "prepareSmokeAdapter", return_value={"configSha256": "observer"}
            ), mock.patch.object(
                verify, "prepareLibraryAliases", return_value={"aliases": {}}
            ), mock.patch.object(
                verify, "runCommand", side_effect=run
            ) as commands, mock.patch.object(
                verify, "runSmoke", return_value={"status": "success"}
            ) as smoke, mock.patch.object(
                verify, "exportEvidence"
            ):
                result = verify.verifySnapshot(
                    root,
                    {},
                    {"commits": ["original"], "tree": "tree"},
                    root / "output",
                    [{"id": "python33", "pythonAbi": "3.3", "environment": {"LD_LIBRARY_PATH": "/locked/abi"}}],
                )
            self.assertEqual("success", result["status"], result)
            self.assertEqual("game/game.pro", result["project"])
            calls = commands.call_args_list
            self.assertEqual(["qmake", "make", "qmake", "make", "g++"], [call.args[0][0] for call in calls])
            self.assertFalse(any(arg.startswith("SOURCES+=") for arg in calls[0].args[0]))
            self.assertTrue(any(arg.startswith("SOURCES+=") for arg in calls[2].args[0]))
            self.assertEqual("game", smoke.call_args.args[1].name)
            self.assertEqual(
                result["runtimeLibraryDirectories"][0] + ":/locked/abi",
                smoke.call_args.kwargs["environment"]["LD_LIBRARY_PATH"],
            )

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

    def testExplicitMissingOverridesFailRatherThanVerifyDifferentInputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog.json").write_text(json.dumps({"trees": []}))
            (root / "recipes.json").write_text(json.dumps({"recipes": [{"id": "none", "pythonAbi": "none"}]}))
            arguments = [
                "verify_history.py",
                "--all",
                "--catalog",
                str(root / "catalog.json"),
                "--recipes",
                str(root / "recipes.json"),
                "--overrides",
                str(root / "missing.json"),
            ]
            error_output = io.StringIO()
            with mock.patch.object(sys, "argv", arguments), contextlib.redirect_stderr(error_output):
                with self.assertRaises(SystemExit) as failure:
                    verify.main()
            self.assertEqual(2, failure.exception.code)
            self.assertIn("Requested recovery overrides do not exist", error_output.getvalue())


if __name__ == "__main__":
    unittest.main()
