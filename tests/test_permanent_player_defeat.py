# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Focused source and header-only syntax checks; native defeat/save tests require the real engine."""

import ast
from pathlib import Path
import os
import re
import shutil
import subprocess
import unittest

from tests.cpp_bindings import CPP_TOKENS, registrationBody

ROOT = Path(__file__).resolve().parents[1]
MAP_CASES = (
    "testMapPermanentPlayerDeathPreservesOptInNativeDefeat",
    "testMapPermanentPlayerDeathRoundTripsThroughNativeSerialization",
    "testDefeatedPlayerSurvivesNativeSavedMapRestorationWithoutResurrection",
    "testDefeatedPlayerRestorationRejectsInvalidAliasesWithoutChangingTheActiveMap",
)


def cppRegion(source, marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 1
    for token in CPP_TOKENS.finditer(source, opening + 1):
        if token.group() == "{":
            depth += 1
        elif token.group() == "}":
            depth -= 1
            if depth == 0:
                return source[start : token.end()]
    raise ValueError("Unclosed C++ region: " + marker)


def jsonFixtureProbeSource(source=None):
    source = source if source is not None else (ROOT / "tests/unit/test_map.cpp").read_text(encoding="utf-8")
    policy = cppRegion(source, "void testMapPermanentPlayerDeathRoundTripsThroughNativeSerialization()")
    start = policy.find("const auto &stored_policy")
    if start < 0:
        start = policy.index("expect_true(document->at")
    policy = policy[start : policy.index('"map snapshots must persist', start)]
    policy += '"map snapshots must persist the opt-in death policy as a typed boolean");'
    retained = cppRegion(source, "void testDefeatedPlayerSurvivesNativeSavedMapRestorationWithoutResurrection()")
    walker = cppRegion(retained, "const auto find_definition") + ";"
    appends = re.findall(r'properties\["objects"\][^;\n]*;', retained)
    if len(appends) != 2:
        raise ValueError("The fixture must retain both actual registered-player array mutations")
    return (
        '#include "core/CJson.h"\n#include <memory>\n#include <vector>\n'
        "void expect_true(bool, const char *);\n"
        "void probe(std::shared_ptr<json> document, json &properties, json reference, json actor_definition, "
        "int player_id, bool permanent_death) {\n"
        + policy
        + "\n"
        + walker
        + "\n(void)find_definition(*document);\n"
        + "\n".join(appends)
        + "\n}\n"
    )


class PermanentPlayerDefeatSourceTest(unittest.TestCase):
    def source(self, path):
        return (ROOT / path).read_text(encoding="utf-8")

    def testPermanentDefeatIsTypedOptInAndKeepsTheDefaultRecoveryBranch(self):
        header = self.source("src/core/CMap.h")
        self.assertIn(
            "V_PROPERTY(CMap, bool, permanentPlayerDeath, getPermanentPlayerDeath, setPermanentPlayerDeath)", header
        )
        self.assertIn("bool permanentPlayerDeath = false;", header)
        self.assertIn(
            "V_PROPERTY(CMap, std::shared_ptr<CPlayer>, defeatedPlayer, getDefeatedPlayer, setDefeatedPlayer)", header
        )
        source = self.source("src/core/CMap.cpp")
        trigger = cppRegion(source, "void CMap::registerPlayerTriggers()")
        self.assertLess(trigger.index("if (map->getPermanentPlayerDeath())"), trigger.index("map->addObject(_player)"))
        self.assertIn("map->setDefeatedPlayer(_player);", trigger)
        self.assertIn("_player->relocateWithoutMoveHooks(map->getEntry());", trigger)
        self.assertNotIn("baldursGate", trigger)
        self.assertNotIn("plugin_cityAlliedCombat", trigger)

    def testTerminalRestoreAndRemovalRequireTheExactDeadOwner(self):
        source = self.source("src/core/CMap.cpp")
        restore = cppRegion(source, "bool CMap::restorePlayerAfterLoad(")
        for token in (
            "if (!permanentPlayerDeath)",
            'restoredPlayerCount != 0 || getObjectByName("player")',
            'defeatedPlayer->getName() != "player" || defeatedPlayer->isAlive()',
            "defeatedPlayer->getGame() != getGame()",
            "owner && owner.get() != this",
            "player = defeatedPlayer;",
        ):
            self.assertIn(token, restore)
        guard = cppRegion(source, "bool CMap::keepsDefeatedPlayerOwner(")
        for token in (
            "player == defeatedPlayer",
            "!defeatedPlayer->isAlive()",
            "defeatedPlayer->owningMap.lock().get() == this",
        ):
            self.assertIn(token, guard)
        removal = cppRegion(source, "vstd::task<void> CMap::removeObjectAsync(")
        self.assertEqual(2, removal.count("keepsDefeatedPlayerOwner(object)"))

    def testTerminalPublicSettersRejectDestructiveWritesBeforeMutation(self):
        source = self.source("src/core/CMap.cpp")
        for marker, mutation, notification in (
            (
                "void CMap::setPermanentPlayerDeath(",
                "permanentPlayerDeath = permanent;",
                'recordDirectPropertyChanged("permanentPlayerDeath")',
            ),
            (
                "void CMap::setDefeatedPlayer(",
                "defeatedPlayer = std::move(defeated);",
                'recordDirectPropertyChanged("defeatedPlayer")',
            ),
        ):
            self.assertIn(marker, source)
            setter = cppRegion(source, marker)
            self.assertIn("hasRetainedTerminalPlayer()", setter)
            self.assertLess(setter.index("throw std::logic_error"), setter.index(mutation))
            self.assertLess(setter.index("throw std::logic_error"), setter.index(notification))
            self.assertLess(setter.index("return;"), setter.index("throw std::logic_error"))
        boundary = cppRegion(source, "bool CMap::hasRetainedTerminalPlayer()")
        self.assertIn('keepsDefeatedPlayerOwner(defeatedPlayer) && !getObjectByName("player")', boundary)
        native = cppRegion(
            self.source("tests/unit/test_map.cpp"), "void testMapTerminalPlayerSettersPreserveInstalledSnapshot()"
        )
        for token in (
            "for (const bool reflective : {false, true})",
            '{"disable", "clear", "replace"}',
            'setBoolProperty("permanentPlayerDeath", false)',
            'setObjectProperty<CPlayer>("defeatedPlayer", value)',
            "probe->retainedNotifications == retained_notifications",
            "probe->policyNotifications == policy_notifications",
            "terminalSnapshotRestores(fixture)",
        ):
            self.assertIn(token, native)

    def testDeliberatePrivateResetReleasesOnlyTheReplacedMapOwner(self):
        source = self.source("src/core/CMap.cpp")
        header = self.source("src/core/CMap.h")
        self.assertIn("void resetDefeatedPlayerForAssignment(", header)
        self.assertGreater(header.index("void resetDefeatedPlayerForAssignment("), header.index("  private:"))
        reset = cppRegion(source, "void CMap::resetDefeatedPlayerForAssignment(")
        for token in (
            "if (!defeatedPlayer)",
            "if (defeatedPlayer != replacement)",
            "defeatedPlayer->clearOwningMap(this->ptr<CMap>());",
            "defeatedPlayer.reset();",
            'recordDirectPropertyChanged("defeatedPlayer")',
        ):
            self.assertIn(token, reset)
        for marker in (
            "void CMap::setPlayer(",
            "vstd::task<void> CMap::setPlayerAsync(",
            "std::shared_ptr<CPlayer> CMap::detachPlayer()",
            "void CMap::attachPlayer(std::shared_ptr<CPlayer> player, Coords",
            "vstd::task<void> CMap::attachPlayerAsync(std::shared_ptr<CPlayer> player, Coords",
        ):
            method = cppRegion(source, marker)
            self.assertIn("resetDefeatedPlayerForAssignment(", method)
            self.assertNotIn("setDefeatedPlayer(nullptr)", method)
        native = cppRegion(
            self.source("tests/unit/test_map.cpp"),
            "void testExplicitPlayerReplacementReleasesRetainedTerminalOwnership()",
        )
        for token in (
            '{"set", "setAsync", "attach", "attachAsync", "detach"}',
            "player->getMap() == sentinel",
            "probe->retainedNotifications == retained_notifications + 1",
            "restored->restorePlayerAfterLoad(error)",
            "restored->getPlayer()->isAlive()",
        ):
            self.assertIn(token, native)

    def testTerminalSetterAndResetNativeCasesAreRegisteredOnce(self):
        native = self.source("tests/unit/test_map.cpp")
        tree = ast.parse(self.source("tests/test_native_test_profile.py"))
        additional = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "ADDITIONAL_CASES" for t in node.targets)
        )
        for name in (
            "testMapTerminalPlayerSettersPreserveInstalledSnapshot",
            "testExplicitPlayerReplacementReleasesRetainedTerminalOwnership",
        ):
            self.assertEqual(1, native.count("void " + name + "()"))
            self.assertEqual(
                1, len(re.findall(r'nativeTestProfile\(\).run\("' + name + r'",\s*' + name + r"\);", native))
            )
            self.assertEqual(1, additional["map"].count(name))
        fixture = cppRegion(native, "TerminalPlayerFixture makeTerminalPlayerFixture()")
        self.assertIn("CFightHandler::fightManyResult(player, {enemy})", fixture)

    def testTerminalPerformanceGuardUsesFixedLookupAndSnapshotBudgets(self):
        source = self.source("tests/unit/test_serialization_performance.cpp")
        marker = "void testRetainedTerminalPlayerWorkIsBounded()"
        self.assertIn(marker, source)
        guard = cppRegion(source, marker)
        for token in (
            "constexpr int LOOKUPS = 128;",
            "constexpr int SNAPSHOTS = 4;",
            "constexpr std::size_t ACTOR_DEFINITIONS = 1;",
            "EFFECT_GRAPH_BYTES_PER_ACTOR * 2",
            "ObjectJson::serialize(map)",
            "ObjectJson::deserialize(game, document, strict)",
            "restored->restorePlayerAfterLoad(restore_error)",
            "countTerminalPlayerTriggers(restored) == restored_triggers",
            "map->getNavigationRevision() == revision",
            "map->getObjects().size() == objects",
            "TerminalSerializationProbe::serializationVisits == visits_before + ACTOR_DEFINITIONS",
            "TerminalSerializationProbe::serializationVisits == SNAPSHOTS * ACTOR_DEFINITIONS",
        ):
            self.assertIn(token, guard)
        self.assertNotIn("steady_clock", guard)
        self.assertNotIn("sleep", guard)
        self.assertIn('restored->getObjectProperty<CGameObject>("terminalPlayerAlias") == actual', guard)

    def testTerminalGuardIsInTheExistingNativePerformanceTarget(self):
        source = self.source("tests/unit/test_serialization_performance.cpp")
        runner = cppRegion(source, "void run_serialization_performance_tests()")
        self.assertEqual(1, runner.count("testRetainedTerminalPlayerWorkIsBounded();"))
        for original in (
            "testTypedCodecWorkIsBoundedPerOperation",
            "test_map_load_property_notifications_are_bounded_per_object",
            "testMutualEffectGraphSerializationHasBoundedActorDefinitions",
            "testScalarPropertyMetadataWorkIsBounded",
            "testRejectedSaveAdmissionHasZeroSnapshotWork",
            "testSnapshotAdmissionRejectsEncountersBeforeMutation",
        ):
            self.assertEqual(1, runner.count(original + "();"))
        cmake = self.source("CMakeLists.txt")
        target = cmake[cmake.index("add_executable(performance_guard_tests") :]
        self.assertIn("tests/unit/test_serialization_performance.cpp", target)
        self.assertIn('LABELS "performance;performance_guard_tests"', target)
        self.assertIn("run_serialization_performance_tests();", self.source("tests/unit/test_performance.cpp"))

    def testPublishedPausedControllerRestorationRemainsGuarded(self):
        source = self.source("src/core/CMap.cpp")
        cached = cppRegion(source, "std::shared_ptr<CPlayer> CMap::getPlayer()")
        restored = cppRegion(source, "bool CMap::restorePlayerAfterLoad(")
        self.assertIn("!std::dynamic_pointer_cast<CPlayerController>(player->getController())", cached)
        self.assertIn("!std::dynamic_pointer_cast<CPlayerFightController>(player->getFightController())", cached)
        self.assertIn("!std::dynamic_pointer_cast<CPlayerController>(restoredPlayer->getController())", restored)
        self.assertIn(
            "!std::dynamic_pointer_cast<CPlayerFightController>(restoredPlayer->getFightController())", restored
        )

    def testFourRealNativeCasesAreRegisteredOnceAndUseSupportedJsonOperations(self):
        native = self.source("tests/unit/test_map.cpp")
        tree = ast.parse(self.source("tests/test_native_test_profile.py"))
        additional = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "ADDITIONAL_CASES" for t in node.targets)
        )
        for name in MAP_CASES:
            self.assertEqual(1, native.count("void " + name + "()"))
            self.assertEqual(
                1, len(re.findall(r'nativeTestProfile\(\).run\("' + name + r'",\s*' + name + r"\);", native))
            )
            self.assertEqual(1, additional["map"].count(name))
        selected = "\n".join(cppRegion(native, "void " + name + "()") for name in MAP_CASES)
        self.assertIn("stored_policy.is_boolean() && stored_policy.get<bool>() == permanent_death", selected)
        self.assertIn('node->at("effectActorId").is_number_integer()', selected)
        self.assertIn('node->at("effectActorId").get<int>() == player_id', selected)
        self.assertIn("pending.push_back(&entry.second);", selected)
        self.assertNotIn("&entry.value()", selected)
        self.assertNotIn('properties["objects"].push_back', selected)
        self.assertIn('properties["objects"][properties["objects"].size()] = reference;', selected)
        self.assertIn('properties["objects"][properties["objects"].size()] = actor_definition;', selected)
        self.assertIn("CFightHandler::fightManyResult(player, {enemy})", selected)
        self.assertIn("CGameLoader::loadSavedGame(restored_game, slot)", selected)


class PermanentDefeatJsonSyntaxTest(unittest.TestCase):
    def testActualDefeatFixtureJsonOperationsMatchTheProjectHeader(self):
        if os.name != "posix":
            self.skipTest("Header-only syntax regression requires a POSIX C++ compiler")
        compiler = shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")
        if not compiler:
            self.skipTest("No C++ compiler is available for the header-only syntax regression")
        result = subprocess.run(
            [compiler, "-std=c++23", "-fsyntax-only", "-x", "c++", "-", "-I" + str(ROOT / "src")],
            input=jsonFixtureProbeSource(),
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
