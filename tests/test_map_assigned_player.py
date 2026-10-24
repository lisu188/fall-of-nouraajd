# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Assigned cache observation; native/extension behavior is a separate CI gate."""

from hashlib import sha256
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.cpp_bindings import registrationBody, registrationTokens

ROOT = Path(__file__).resolve().parents[1]


def functionBody(source, signature):
    opening = source.index("{", source.index(signature))
    depth = 0
    for index in range(opening, len(source)):
        depth += (source[index] == "{") - (source[index] == "}")
        if not depth:
            return source[opening + 1 : index]
    raise AssertionError("Unclosed selected function")


class MapAssignedPlayerSourceTest(unittest.TestCase):
    def testAssignedQueryIsConstAndOutsideSerializedMetadata(self):
        header = (ROOT / "src/core/CMap.h").read_text(encoding="utf-8")
        self.assertIn("std::shared_ptr<CPlayer> getAssignedPlayer() const;", header)
        self.assertIn("std::shared_ptr<CPlayer> player;", header.split("  private:", 1)[1])
        self.assertNotRegex(header, r"V_PROPERTY\([^\n]*[Aa]ssignedPlayer")
        self.assertIn("Engine owner thread", header)

    def testAssignedQueryOnlyCopiesCurrentCacheWithoutAdoptionOrCallbacks(self):
        source = (ROOT / "src/core/CMap.cpp").read_text(encoding="utf-8")
        signature = "std::shared_ptr<CPlayer> CMap::getAssignedPlayer() const"
        self.assertIn(signature, source)
        body = functionBody(source, signature)
        self.assertEqual("return player;", " ".join(body.split()))
        # A getter-only mutex cannot synchronize existing unlocked assignment writers.
        self.assertNotIn("lock", body)
        self.assertNotIn("getPlayer", body)
        self.assertNotIn("getObject", body)

    def testExistingLazyGetterKeepsItsExplicitRecoveryPolicy(self):
        source = (ROOT / "src/core/CMap.cpp").read_text(encoding="utf-8")
        body = functionBody(source, "std::shared_ptr<CPlayer> CMap::getPlayer()")
        for policy in (
            "restorePlayerAfterLoad",
            "player = vstd::cast<CPlayer>(object)",
            "setController",
            "setFightController",
            "registerPlayerTriggers",
        ):
            self.assertIn(policy, body)
        self.assertNotIn("getAssignedPlayer", body)

    def testOrdinaryNativeCasesCoverUnassignedMismatchRemovalAndTransfer(self):
        source = (ROOT / "tests/unit/test_map.cpp").read_text(encoding="utf-8")
        names = (
            "testMapAssignedPlayerQueryDoesNotAdoptOrRepairRegisteredPlayer",
            "testMapAssignedPlayerQueryExposesMismatchAndTracksExplicitTransfers",
        )
        for name in names:
            self.assertEqual(1, source.count("void " + name + "()"))
            self.assertIn('nativeTestProfile().run("' + name + '"', source)
        first = functionBody(source, "void " + names[0] + "()")
        for action in (
            "const CMap &observed",
            "map->addObject(player)",
            "map->removeObject(player)",
            "player->getController() == movement",
            "count_player_event_triggers(map) == triggers",
            "map->getPlayer() == player",
        ):
            self.assertIn(action, first)
        second = functionBody(source, "void " + names[1] + "()")
        for action in (
            "map->setPlayer(canonical)",
            "map->setPlayer(assigned)",
            'map->getObjectByName("player") == canonical',
            "observed.getAssignedPlayer() == assigned",
            "map->detachPlayer() == assigned",
            "map->attachPlayer(canonical",
        ):
            self.assertIn(action, second)

    def testDeterministicQueryGuardIsRegisteredWithZeroMutationBudgets(self):
        source = (ROOT / "tests/unit/test_engine_hotspot_performance.cpp").read_text(encoding="utf-8")
        name = "testAssignedPlayerQueriesAreMutationAndCallbackBounded"
        self.assertIn("void " + name + "()", source)
        body = functionBody(source, "void " + name + "()")
        for guard in (
            "constexpr int READS_PER_PHASE = 256;",
            "reads == 2 * READS_PER_PHASE",
            "getObjects() == objects",
            "getTriggers() == triggers",
            "getNavigationRevision() == revision",
            "getTurn() == turn",
            "getPendingTaskCount() == pending",
            "getDelayedTaskCount() == delayed",
            "properties_changed_calls == callbacks",
            "CTypes::register_type<CPlayerController>()",
            "CTypes::register_type<CPlayerFightController>()",
        ):
            self.assertIn(guard, body)
        self.assertEqual(1, source.count("    " + name + "();"))

    def testQueryGuardRegistersSessionFactoriesBeforeAttachmentAndSnapshot(self):
        source = (ROOT / "tests/unit/test_engine_hotspot_performance.cpp").read_text(encoding="utf-8")
        body = functionBody(source, "void testAssignedPlayerQueriesAreMutationAndCallbackBounded()")
        attachment = body.index("fixture.map->attachPlayer(player, Coords(0, 0, 0))")
        snapshot = body.index("const auto current_movement = player->getController()")
        query = body.index("for (int read = 0; read < READS_PER_PHASE; ++read)")
        for native_type, counter, variable in (
            ("CPlayerController", "movement_constructions", "current_movement"),
            ("CPlayerFightController", "fight_constructions", "current_fight"),
        ):
            registration = 'fixture.game->getObjectHandler()->registerType("' + native_type + '"'
            self.assertIn(registration, body, "global CTypes metadata does not populate a fresh session's constructors")
            factory = body.index(registration)
            self.assertLess(factory, attachment)
            self.assertLess(attachment, snapshot)
            self.assertIn("[" + counter + "]", body[factory:attachment])
            self.assertIn("++*" + counter + ";", body[factory:attachment])
            self.assertIn("return std::make_shared<" + native_type + ">();", body[factory:attachment])
            self.assertIn("*" + counter + " == (assigned ? 1 : 0)", body[:query])
            native_controller = "std::dynamic_pointer_cast<" + native_type + ">(" + variable + ") != nullptr"
            self.assertIn(native_controller, body[snapshot:query])
            self.assertIn("const auto " + counter + "_before = *" + counter + ";", body[:query])
            self.assertIn("*" + counter + " == " + counter + "_before", body[query:])
        self.assertEqual(1, body.count("observed.getAssignedPlayer()"))

    def testQueryGuardReportsActualPerPhaseValuesWithoutReplacingZeroWorkAssertions(self):
        source = (ROOT / "tests/unit/test_engine_hotspot_performance.cpp").read_text(encoding="utf-8")
        body = functionBody(source, "void testAssignedPlayerQueriesAreMutationAndCallbackBounded()")
        query = body.index("for (int read = 0; read < READS_PER_PHASE; ++read)")
        self.assertIn('"assigned player query phase: assigned="', body)
        diagnostics = body.index('"assigned player query phase: assigned="')
        assertion = body.index("expect_true(fixture.map->getObjects() == objects")
        self.assertLess(query, diagnostics)
        self.assertLess(diagnostics, assertion)
        observed_samples = " ".join(body[diagnostics:assertion].split())
        for sample in (
            "after_objects == objects",
            "after_triggers == triggers",
            "revision << '/' << after_revision",
            "turn << '/' << after_turn",
            "after_movement == current_movement",
            "after_fight == current_fight",
            "pending << '/' << after_pending",
            "delayed << '/' << after_delayed",
            "callbacks << '/' << after_callbacks",
            "movement_constructions_before << '/' << *movement_constructions",
            "fight_constructions_before << '/' << *fight_constructions",
        ):
            self.assertIn(sample, observed_samples)
        self.assertIn("budget-registry/controller/hook/turn/queue/callback-deltas=0; observations above", body)
        self.assertIn("256 queries per phase must add zero registry/controller/hook/turn/queue/callback work", body)

    def testGetterOnlyWorldBindingMatchesReviewedContract(self):
        source = (ROOT / "src/core/bindings/CModuleWorld.cpp").read_text(encoding="utf-8")
        self.assertIn('.def("getAssignedPlayer", &CMap::getAssignedPlayer,', source)
        contract = json.loads((ROOT / "tests/fixtures/python_binding_contract.json").read_text(encoding="utf-8"))
        group = next(row for row in contract["groups"] if row["registration"] == "bindGraphicsAndWorld")
        self.assertEqual(
            group["registrationTokenSha256"],
            sha256(registrationTokens(registrationBody(source, "bindGraphicsAndWorld")).encode()).hexdigest(),
        )
        self.assertIn("assignedPlayerQueryReview", contract)
        self.assertIn("mapBindingEpochReview", contract)

    def testSourceAndLazyExtensionFixturesAreRegisteredInTheirOwnSuites(self):
        source = (ROOT / "test.py").read_text(encoding="utf-8")
        fast = source.split("FAST_TEST_PREFIXES", 1)[1].split(")", 1)[0]
        self.assertIn('"MapAssignedPlayerSourceTest."', fast)
        self.assertNotIn('"MapAssignedPlayerRuntimeTest."', fast)
        for name in ("MapAssignedPlayerSourceTest", "MapAssignedPlayerRuntimeTest"):
            self.assertIn("class " + name + "(_" + name + "):", source)
            self.assertIn(name + " as _" + name, source)
        self.assertIn("del _MapAssignedPlayerSourceTest, _MapAssignedPlayerRuntimeTest", source)

    def testIsolatedExtensionAdapterAllowsOnlyUnconfiguredMissingBuildSkip(self):
        runtime = MapAssignedPlayerRuntimeTest()
        target = "tests.test_python_callback_lifecycle.PythonCallbackLifecycleTest.runChild"
        with patch(target, return_value="native-output") as child:
            self.assertEqual("native-output", runtime.runChild("bounded-child-program"))
            child.assert_called_once_with(runtime, "bounded-child-program")
        for required in (None, "GAME_BUILD_DIR", "GAME_BUILD_CONFIG", "GAME_MCP_BRANCH_REQUIRED", "explicit"):
            with self.subTest(required=required):
                environment = {"GAME_BUILD_DIR": "", "GAME_BUILD_CONFIG": "", "GAME_MCP_BRANCH_REQUIRED": ""}
                if required and required != "explicit":
                    environment[required] = "1" if required == "GAME_MCP_BRANCH_REQUIRED" else "configured"
                with patch.dict(os.environ, environment), patch(target, side_effect=unittest.SkipTest("missing _game")):
                    if required:
                        error = None
                        try:
                            runtime.runChild("never-launched", required=required == "explicit")
                        except (unittest.SkipTest, AssertionError) as observed:
                            error = observed
                        self.assertIsInstance(error, AssertionError)
                        self.assertIn("Configured native build must run", str(error))
                    else:
                        with self.assertRaises(unittest.SkipTest):
                            runtime.runChild("never-launched")


class MapAssignedPlayerRuntimeTest(unittest.TestCase):
    def runChild(self, code, *, required=False):
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        try:
            return PythonCallbackLifecycleTest.runChild(self, code)
        except unittest.SkipTest:
            if (
                required
                or os.environ.get("GAME_BUILD_DIR")
                or os.environ.get("GAME_BUILD_CONFIG")
                or os.environ.get("GAME_MCP_BRANCH_REQUIRED") == "1"
            ):
                self.fail("Configured native build must run the assigned-player extension fixture")
            raise

    def testExtensionQueryObservesActualCacheWithoutAdoptingRegisteredPlayer(self):
        output = self.runChild("""
            owner = game.CGameLoader.loadGame()
            try:
                game.CGameLoader.startGameWithPlayer(owner, 'test', 'Warrior')
                assert owner.getGui() is None
                game_map = owner.getMap()
                player = game.CMap.getAssignedPlayer(game_map)
                assert isinstance(player, game.CPlayer)
                assert player is game_map.getObjectByName('player')
                assert player is game_map.detachPlayer()
                assert game.CMap.getAssignedPlayer(game_map) is None
                game_map.addObject(player)
                movement, fight = player.getController(), player.getFightController()
                before_turn = game_map.getTurn()
                for _read in range(128):
                    assert game.CMap.getAssignedPlayer(game_map) is None
                assert player is game_map.getObjectByName('player')
                assert movement is player.getController()
                assert fight is player.getFightController()
                assert before_turn == game_map.getTurn()
                game_map.attachPlayer(player)
                assert player is game.CMap.getAssignedPlayer(game_map)
                assert player is game_map.detachPlayer()
                assert game.CMap.getAssignedPlayer(game_map) is None
                print('assigned player cache observer verified', flush=True)
            finally:
                owner.getContext().shutdown()
            """)
        self.assertIn("assigned player cache observer verified", output)
