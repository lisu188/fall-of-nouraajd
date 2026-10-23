# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Native suspension source contracts; behavioral C++ cases require CI execution."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def functionBody(source, signature):
    start = source.index("{", source.index(signature))
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1 : index]
    raise AssertionError("Unterminated selected native function")


class PlayerControllerSuspensionSourceTest(unittest.TestCase):
    def testSuspensionIsAnOptInSerializedBooleanWithBoundedDisabledHotPaths(self):
        header = (ROOT / "src/core/CController.h").read_text(encoding="utf-8")
        source = (ROOT / "src/core/CController.cpp").read_text(encoding="utf-8")
        self.assertRegex(
            header,
            r"V_PROPERTY\(CPlayerController, bool, movementSuspended, getMovementSuspended, setMovementSuspended\)",
        )
        self.assertIn("bool movementSuspended = false;", header)
        setter = functionBody(source, "void CPlayerController::setMovementSuspended(")
        self.assertIn('recordDirectPropertyChanged("movementSuspended")', setter)
        self.assertIn("if (movementSuspended == value)", setter)
        for signature, work in (
            ("void CPlayerController::setTarget(", "clearPath();"),
            ("vstd::task<Coords> CPlayerController::controlAsync(", "canContinue(player)"),
            ("std::pair<bool, Coords::Direction> CPlayerController::isOnPath(", "const auto map"),
        ):
            body = functionBody(source, signature)
            self.assertLess(body.index("if (movementSuspended)"), body.index(work), signature)
        tests = (ROOT / "tests/unit/test_controller.cpp").read_text(encoding="utf-8")
        for name in (
            "testPlayerControllerMovementSuspensionBlocksRequestsAndResumes",
            "testPlayerControllerMovementSuspensionRoundTripsWithLegacyDefault",
        ):
            self.assertEqual(1, tests.count("void " + name + "()"))
            self.assertEqual(1, tests.count("    " + name + "();"))
        self.assertIn(
            "repeat < 128", functionBody(tests, "void testPlayerControllerMovementSuspensionBlocksRequestsAndResumes(")
        )

    def testCacheRestorationPreservesActualControllersAndCommitChecksSuspension(self):
        source = (ROOT / "src/core/CMap.cpp").read_text(encoding="utf-8")
        body = functionBody(source, "std::shared_ptr<CPlayer> CMap::getPlayer()")
        for class_name, getter, setter in (
            ("CPlayerController", "getController", "setController"),
            ("CPlayerFightController", "getFightController", "setFightController"),
        ):
            self.assertRegex(
                body,
                r"if \(!std::dynamic_pointer_cast<"
                + class_name
                + r">\(player->"
                + getter
                + r"\(\)\)\)\s*\{\s*player->"
                + setter,
            )
        self.assertGreaterEqual(source.count("player_controller->getMovementSuspended()"), 2)
        tests = (ROOT / "tests/unit/test_map.cpp").read_text(encoding="utf-8")
        for name in (
            "testMapPlayerCacheMissPreservesValidControllerIdentity",
            "testMapMoveRejectsPlayerPlanSuspendedBeforeCommit",
            "testMapPausedPlayerControllerRoundTripsWithoutReset",
        ):
            self.assertEqual(1, tests.count("void " + name + "()"))
            self.assertIn('nativeTestProfile().run("' + name + '"', tests)
        snapshot = functionBody(tests, "void testMapPausedPlayerControllerRoundTripsWithoutReset(")
        self.assertIn('"plugin_cityPalaceSequenceOriginalController"', snapshot)
        self.assertIn('"plugin_cityPalaceSequencePauseControllerName"', snapshot)
        self.assertNotRegex(snapshot, r'setObjectProperty.*"plugin_cityPalaceSequencePauseController"')
        self.assertIn("paused_definitions == 1 && original_definitions == 1", snapshot)

    def testLeaveHookCannotCommitAControllerPlanSuspendedDuringItsAwait(self):
        header = (ROOT / "src/object/CMapObject.h").read_text(encoding="utf-8")
        source = (ROOT / "src/object/CMapObject.cpp").read_text(encoding="utf-8")
        self.assertIn("std::move_only_function<bool()> commitAllowed = {}", header)
        body = functionBody(source, "vstd::task<void> CMapObject::moveOwnedAsync(")
        self.assertLess(body.index("co_await moveable->beforeMoveAsync()"), body.index("commitAllowed()"))
        self.assertLess(body.index("commitAllowed()"), body.index("object->posx = target.x"))
        guard = body[body.index("if (commitAllowed && !commitAllowed())") : body.index("Coords oldCoords")]
        self.assertIn("moveable->cancelMove()", guard)
        self.assertIn("co_return", guard)
        map_source = (ROOT / "src/core/CMap.cpp").read_text(encoding="utf-8")
        self.assertIn("creature->getController() == controller_ptr", map_source)
        self.assertIn("!player_controller->getMovementSuspended()", map_source)
        self.assertIn("moveToAsync(target, {}, presenter, std::move(commitAllowed))", map_source)
        tests = (ROOT / "tests/unit/test_map.cpp").read_text(encoding="utf-8")
        name = "testMapMoveRejectsPlayerPlanSuspendedDuringLeaveHook"
        self.assertEqual(1, tests.count("void " + name + "()"))
        self.assertIn('nativeTestProfile().run("' + name + '"', tests)
        fixture = functionBody(tests, "void " + name + "(")
        self.assertIn("CGameEvent::CType::onLeave", fixture)
        self.assertIn("co_await vstd::post", fixture)
        self.assertIn("controller->setMovementSuspended(true)", fixture)
        self.assertIn("player->moveToAsync(target)", fixture)
        self.assertIn("player->relocateWithoutMoveHooks(origin)", fixture)

    def testPerformanceGuardKeepsPausedRequestsSearchesCachesAndMovesBounded(self):
        source = (ROOT / "tests/unit/test_engine_hotspot_performance.cpp").read_text(encoding="utf-8")
        name = "testSuspendedPlayerNavigationWorkIsBounded"
        self.assertEqual(1, source.count("void " + name + "()"))
        self.assertEqual(1, source.count("    " + name + "();"))
        body = functionBody(source, "void " + name + "(")
        self.assertIn("constexpr int ATTEMPTS = 128", body)
        for counter in (
            "getRequestSerial()",
            "getOverlayLookupCount()",
            "searchCount()",
            "budget()->used()",
            "budget()->peak()",
            "targetFlowCacheSize()",
            "getObjectCacheEntryCountForTesting()",
        ):
            self.assertIn(counter, body)
        self.assertIn("controller->setMovementSuspended(false)", body)
        self.assertIn("searches + 1", body)
        self.assertIn("fixture.map->getTurn() == turn + 2", body)
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("tests/unit/test_engine_hotspot_performance.cpp", cmake)
        self.assertIn('NAME "performance.performance_guard_tests" COMMAND performance_guard_tests', cmake)

    def testPerformanceFixtureRegistersTheNativeFactoriesUsedByPlayerAssignment(self):
        import re

        source = (ROOT / "tests/unit/test_engine_hotspot_performance.cpp").read_text(encoding="utf-8")
        fixture = functionBody(source, "void testSuspendedPlayerNavigationWorkIsBounded(")
        assignment = functionBody((ROOT / "src/core/CMap.cpp").read_text(encoding="utf-8"), "void CMap::setPlayer(")
        for class_name in ("CPlayerController", "CPlayerFightController"):
            self.assertIn("getGame()->createObject<" + class_name + ">()", assignment)
            registration = re.search(
                r'fixture\.game->getObjectHandler\(\)->registerType\(\s*"'
                + class_name
                + r'"\s*,\s*\[\]\s*\{\s*return std::make_shared<'
                + class_name
                + r">\(\);\s*\}\s*\)",
                fixture,
            )
            self.assertIsNotNone(registration, "The isolated fixture must supply the actual " + class_name + " factory")
            self.assertLess(registration.end(), fixture.index("fixture.map->setPlayer(player)"))

    def testMovementCommitGuardUsesThePortableCallbackType(self):
        import re

        map_source = (ROOT / "src/core/CMap.cpp").read_text(encoding="utf-8")
        header = (ROOT / "src/object/CMapObject.h").read_text(encoding="utf-8")
        declarations = [line.strip() for line in map_source.splitlines() if "commitAllowed;" in line]
        self.assertIn("vstd::move_only_function<bool()> commitAllowed;", declarations)
        self.assertFalse(
            re.search(r"\bstd::move_only_function", map_source), "Map callbacks must use the portable type"
        )
        self.assertTrue(
            "vstd::move_only_function<bool()> commitAllowed" in header,
            "The caller and movement API must use the same portable callback type",
        )
