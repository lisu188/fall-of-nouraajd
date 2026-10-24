# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import csv
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
# Ordered native cases on main e3d3c90, before adding diagnostic wrappers.
BASELINE_CASES = {
    "handler": (36, "133d76b3db645f21a09e2b55fc738f481318a97c42532b80bb67edba5354a89d"),
    "map": (49, "17f592c7f09a057f9c3249babde697470899143ffda78688662f61ab5cfbdf9e"),
}
ADDITIONAL_CASES = {
    "handler": (
        "testScriptFlowBootstrapDoesNotRequireGameplayModule",
        "testSyncGuiWaitReleasesLastGameOwner",
        "testObjectEntryTracePreservesActualCauseAndContactBeforeNpcDeparture",
        "testObjectEntryTraceRequiresOptInAndCanonicalColocatedCause",
        "testAsyncObjectEntryTraceWaitsForHooksAndPreservesContactOnResume",
        "testEffectTickCappingAndExpiryIgnoreAllocationOrder",
        "testEffectTickLethalityTimingAndCasterIgnoreAllocationOrder",
        "testDuplicateDefeatRejectsDuringRealLootAndRemoval",
        "testConcurrentPlayerDefeatPublishesOnlyRecoveredReceipt",
        "testDefeatCancellationAndFailureDrainOwnedRecovery",
        "testRecursiveDefeatRejectsBeforeItsOwnRecovery",
        "testOverlappingEncounterCannotStartSharedControllers",
        "testDefeatAdmissionRefusalAndAbandonedOwnersPreserveBoundaries",
        "testFailedOrdinaryDefeatRequiresVerifiedRestore",
        "testDefeatCallbackShutdownKeepsContextTaskAncestry",
        "testEncounterParticipantClaimsReleaseAfterThrowAndCancel",
        "testEncounterOwnershipIgnoresSanitizedIneligibleCandidates",
        "testDefeatRecoveryCertificationRejectsReplacedOrUnfinishedOwners",
        "testInternalDefeatLeaseSurvivesParentControllerCleanup",
        "testAsyncCombatAwaitsLootWithoutPumpingOrGrantingRewardsEarly",
        "testWorkerStartedCombatDefersControllerAndPanelCreationToMain",
        "testCancelledLootSettlesStartedRewardsOnceAndSkipsQueuedCombat",
        "testAsyncEventsAwaitOrderedTriggerSnapshotsAfterObjectHooks",
        "testAsyncLeaveHooksRejectStaleMovesAndCleanCancellation",
        "testArrivalHooksRejectChangedMapAndGeneration",
        "testAsyncNamedSpawnsAwaitEntryWithoutPumping",
        "testDisposableItemCommitConsumesBeforeReceiptsAndCancellation",
        "testScriptCallbackFlowUsesInitializedUiModule",
        "testItemPositionCommitOwnsConsumptionBeforeArrivalCancellation",
        "testIndividualQuestCancellationHonorsExplicitRewardCommit",
        "testAsyncRemovalAwaitsDestroyHooksAndFinalizesCancellation",
        "testAsyncEventHooksStopAfterContextShutdown",
        "testAsyncCombatTraceCapturesResourcesBeforeControllerSuspension",
        "testSaveAdmissionRejectsBeforeQuestAndGraphWork",
        "testSaveAdmissionOwnersMovesAndSnapshots",
        "testSaveAdmissionSurvivesMapAndGameOwnerChanges",
        "testSaveAdmissionQuarantineRequiresVerifiedInstall",
        "testAuthoredNativeSavePolicyIsStrictAndPrecedesObjects",
        "testVerifiedRestoreReappliesAuthoritativeNativeSavePolicy",
        "testVerifiedLoadResumePolicyIsStrictAndPrecedesObjects",
        "testVerifiedLoadResumesActualFlowOnlyAfterPostedLeaseRelease",
        "testVerifiedLoadResumeRejectsSupersededWeakBindings",
        "testUnverifiedOrRejectedLoadsNeverDispatchResume",
        "testWaitStateSnapshotsPreserveRemainingDurationWithoutRebasingLiveTime",
        "testWaitStateRejectsInvalidDurationsMutationsAndDuplicateLeases",
        "testScriptWaitFlowCompletesAndRejectsInvalidObjectArguments",
        "testScriptWaitSurvivesFailedSaveResourceBindingWithoutDispatchingMapChanges",
        "testScriptWaitCancellationAndMapBindingLossFreezeRemainingTime",
        "testSyncScriptWaitReleasesTheFinalGameOwner",
    ),
    "map": (
        "testNewSessionClearsQuitLatch",
        "testMapMoveDiscardsReplacedControllerPlan",
        "testMapMoveSnapshotsActorsBeforeInlinePlans",
        "testCancelledAsyncCombatRestoresPlayerOrigin",
        "testMapMoveRejectsPlayerPlanCapturedBeforeSynchronousRespawn",
        "testMapPlayerCacheMissPreservesValidControllerIdentity",
        "testMapMoveRejectsPlayerPlanSuspendedBeforeCommit",
        "testMapMoveRejectsPlayerPlanSuspendedDuringLeaveHook",
        "testMapPausedPlayerControllerRoundTripsWithoutReset",
        "testMapPermanentPlayerDeathPreservesOptInNativeDefeat",
        "testMapPermanentPlayerDeathRoundTripsThroughNativeSerialization",
        "testDefeatedPlayerSurvivesNativeSavedMapRestorationWithoutResurrection",
        "testDefeatedPlayerRestorationRejectsInvalidAliasesWithoutChangingTheActiveMap",
        "testMapTerminalPlayerSettersPreserveInstalledSnapshot",
        "testExplicitPlayerReplacementReleasesRetainedTerminalOwnership",
        "test_scene_manager_awaits_preparation_and_rolls_back_errors",
        "testSceneCompletionOwnsSkippedLazyChildren",
        "testSceneCommitRunsAfterPreparationAndBeforeQueuedObservers",
        "testAsyncGameStartOwnsSuspendedEntryAndRollsBackCancellation",
        "testAsyncRandomEncountersStopBeforeAnotherStaleRoomOrRngDraw",
        "testAsyncObjectCreationSuspendsWithoutNestedPumpingAndRejectsStaleMovement",
    ),
}


class NativeTestProfileSourceTest(unittest.TestCase):

    def testDirectEncounterAdmissionUsesAnArmedTopLevelSnapshotProbe(self):
        source = (ROOT / "tests/unit/test_allied_combat.cpp").read_text(encoding="utf-8")
        self.assertIn("class EncounterAdmissionSnapshotMap : public CMap", source)
        probe = source.split("class EncounterAdmissionSnapshotMap : public CMap", 1)[1].split("struct Fixture", 1)[0]
        self.assertEqual(2, probe.count("stopArmedGraph();"))
        self.assertEqual(2, probe.count("return CMap::meta();"))
        self.assertIn("if (std::exchange(stopNextGraph, false))", probe)
        self.assertIn("++graphVisits;", probe)
        self.assertIn("intentional top-level encounter snapshot stop before resource writes", probe)
        direct = source.split("void testDirectEncounterSaveAdmissionAndLegacyDefault() {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("auto observedMap = std::make_shared<EncounterAdmissionSnapshotMap>();", direct)
        self.assertIn("Fixture fixture(observedMap);", direct)
        self.assertEqual(2, direct.count("observedMap->meta() == observedMap->CMap::meta()"))
        self.assertIn("work.graph->visits == 0", direct)

    def testDirectEncounterAdmissionProbeIsScopedToTheRealSaveAttempt(self):
        source = (ROOT / "tests/unit/test_allied_combat.cpp").read_text(encoding="utf-8")
        self.assertIn("explicit Fixture(std::shared_ptr<CMap> providedMap = {})", source)
        fixture = source.split("struct Fixture", 1)[1].split("std::shared_ptr<ProbeController> probe(", 1)[0]
        self.assertIn("if (providedMap)", fixture)
        self.assertLess(fixture.index("game->setMap(providedMap)"), fixture.index("hero = std::make_shared<CPlayer>"))
        work = source.split("struct EncounterAdmissionWork", 1)[1].split("class EncounterAdmissionEffect", 1)[0]
        self.assertIn("std::dynamic_pointer_cast<EncounterAdmissionSnapshotMap>(map)", work)
        self.assertIn("owner->stopNextGraph = true;", work)
        self.assertIn("~SnapshotGraphStop()", work)
        self.assertIn("owner->stopNextGraph = false;", work)
        self.assertLess(work.index("} graphStop(map);"), work.index("CMapLoader::saveWithResult(map,"))
        self.assertEqual(1, work.count("CMapLoader::saveWithResult(map,"))
        self.assertIn("an encounter save must reject or hit the intentional graph stop without writing", work)

    def testDirectEncounterAdmissionKeepsFiveBoundariesAndExactWorkBudgets(self):
        source = (ROOT / "tests/unit/test_allied_combat.cpp").read_text(encoding="utf-8")
        direct = source.split("void testDirectEncounterSaveAdmissionAndLegacyDefault() {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("for (const bool optedIn : {false, true})", direct)
        self.assertEqual(5, direct.count("work.attempt();"))
        self.assertRegex(
            direct, r"work\.quest->captures == expectedWork\s*&&\s*observedMap->graphVisits == expectedWork"
        )
        for callback in (
            "fixture.heroController->starting",
            "probe(enemy)->starting",
            "fixture.heroController->action",
            "fixture.heroController->ending",
            "probe(enemy)->ending",
        ):
            self.assertIn(callback, direct)
        for obligation in (
            "const int expectedWork = optedIn ? 0 : 5;",
            "result.outcome == CFightOutcome::Cancelled",
            "work.attempts == 5",
            "work.quest->captures == expectedWork",
            "observedMap->graphVisits == expectedWork",
            "fixture.heroController->ends == 1",
            "probe(enemy)->ends == 1",
            "fixture.map->tryBeginSaveSnapshot().has_value()",
        ):
            self.assertIn(obligation, direct)
        for diagnostic in (
            "optedIn=%d",
            "outcome=%d",
            "attempts=%d",
            "journal=%d",
            "graph=%d",
            "nestedGraph=%d",
            "starts=%d/%d",
            "actions=%d/%d",
            "ends=%d/%d",
            "expectedWork=%d",
            "armed=%d",
        ):
            self.assertIn(diagnostic, direct)

    def testVerifiedResumeFixtureUsesAnAuthoredConfiguration(self):
        handler = (ROOT / "tests/unit/test_handler.cpp").read_text(encoding="utf-8")
        resume = handler.split("struct VerifiedResumeFixture {", 1)[1].split("\nint main() {", 1)[0]
        constructor = resume.split("    VerifiedResumeFixture() {", 1)[1].split("    void cleanup(", 1)[0]
        map_name = re.findall(r'game->getMap\(\)->setMapName\("([^"]+)"\);', constructor)
        self.assertEqual(["test"], map_name)
        configuration = f"maps/{map_name[0]}/map.json"
        self.assertTrue((ROOT / "res" / configuration).is_file(), configuration)
        self.assertEqual([configuration] * 3, re.findall(r'getConfiguration\("([^"]+)"\)', resume))
        self.assertLess(constructor.index("setMapName("), constructor.index("getConfiguration("))
        self.assertLess(constructor.index("getConfiguration("), constructor.index("CMapLoader::saveWithResult("))

    def testVerifiedResumeConsumersStopWhenNativeFixtureSetupFails(self):
        handler = (ROOT / "tests/unit/test_handler.cpp").read_text(encoding="utf-8")
        resume = handler.split("struct VerifiedResumeFixture {", 1)[1].split("\nint main() {", 1)[0]
        constructor = resume.split("    VerifiedResumeFixture() {", 1)[1].split("    void cleanup(", 1)[0]
        self.assertIn("bool ready = false;", resume.split("VerifiedResumeFixture()", 1)[0])
        self.assertIn("if (!authored || !authored->is_object()) {\n            return;\n        }", constructor)
        self.assertEqual(1, constructor.count("ready = CMapLoader::saveWithResult(game->getMap(), slot);"))
        self.assertIn('expect_true(ready, "resume fixture must use an actual native save");', constructor)
        for name in (
            "testVerifiedLoadResumesActualFlowOnlyAfterPostedLeaseRelease",
            "testVerifiedLoadResumeRejectsSupersededWeakBindings",
            "testUnverifiedOrRejectedLoadsNeverDispatchResume",
        ):
            body = resume.split(f"void {name}() {{", 1)[1].split("\n}\n", 1)[0]
            self.assertRegex(
                body,
                r"VerifiedResumeFixture fixture;\s+if \(!fixture\.ready\) \{\s+"
                r"fixture\.cleanup\(false\);\s+return;\s+\}",
                name,
            )
            self.assertLess(body.index("if (!fixture.ready)"), body.index("fixture.game"), name)
        self.assertEqual(3, resume.count("if (!fixture.ready)"))

    def testVerifiedResumeFixtureKeepsAllInstallationAndRejectionCases(self):
        handler = (ROOT / "tests/unit/test_handler.cpp").read_text(encoding="utf-8")
        resume = handler.split("struct VerifiedResumeFixture {", 1)[1].split("\nint main() {", 1)[0]
        self.assertIn("constexpr int INSTALLATIONS = 8;", resume)
        self.assertIn("for (int index = 0; index < INSTALLATIONS; ++index)", resume)
        self.assertIn("const bool backup_recovery = index == INSTALLATIONS / 2;", resume)
        self.assertIn("for (int mode = 0; mode < 6; ++mode)", resume)
        self.assertIn("for (int mode = 0; mode < 7; ++mode)", resume)
        self.assertIn("seven rejected, unverified or disabled load paths have a zero authored-dispatch budget", resume)
        main = handler[handler.rindex("int main() {") :]
        for name in (
            "testVerifiedLoadResumePolicyIsStrictAndPrecedesObjects",
            "testVerifiedLoadResumesActualFlowOnlyAfterPostedLeaseRelease",
            "testVerifiedLoadResumeRejectsSupersededWeakBindings",
            "testUnverifiedOrRejectedLoadsNeverDispatchResume",
        ):
            self.assertEqual(1, len(re.findall(rf'nativeTestProfile\(\)\.run\("{name}",', main)), name)

    def testDefeatOwnershipStaysInlineAndRejectsDuplicatesBeforeEffects(self):
        source = (ROOT / "src/handler/CFightHandler.cpp").read_text(encoding="utf-8")
        self.assertIn("vstd::task<void> CFightHandler::resolveOwnedDefeatAsync(", source)
        public = source.split("vstd::task<void> CFightHandler::defeatedCreatureAsync(", 1)[1]
        public = public.split("vstd::task<void> CFightHandler::resolveOwnedDefeatAsync(", 1)[0]
        self.assertIn("return resolveOwnedDefeatAsync(std::move(a), std::move(b), {});", public)
        owned = source.split("vstd::task<void> CFightHandler::resolveOwnedDefeatAsync(", 1)[1]
        self.assertNotIn("task_group", source)
        self.assertNotIn("task_detail", source)
        self.assertIn("defeat recovery already owns a participant", owned)
        self.assertLess(owned.index("b->defeatResolutionInProgress"), owned.index("a->addExpScaled("))
        self.assertLess(owned.index("b->defeatResolutionInProgress = true;"), owned.index("a->addExpScaled("))
        self.assertIn("b->defeatResolutionInProgress = false;", owned)

    def testPrivateEncounterFinalizerRequiresBothParticipantClaims(self):
        source = (ROOT / "src/handler/CFightHandler.cpp").read_text(encoding="utf-8")
        header = (ROOT / "src/handler/CFightHandler.h").read_text(encoding="utf-8")
        self.assertIn("  private:", header)
        private = header.split("  private:", 1)[1]
        self.assertIn("resolveOwnedDefeatAsync", private)
        self.assertNotIn("encounterOwner", header.split("  private:", 1)[0])
        self.assertIn("winnerClaim != encounterOwner || loserClaim != encounterOwner", source)
        self.assertEqual(2, source.count("co_await CCombatParticipantGuard::resolveDefeat("))
        self.assertEqual(
            15,
            len(
                re.findall(
                    r"co_await (?:resolve_defeat_async|defeat_attacker_async|remove_dead_allies_async|remove_dead_opponents_async)\([^;]*?encounterOwner\)",
                    source,
                )
            ),
        )
        creature = (ROOT / "src/object/CCreature.h").read_text(encoding="utf-8")
        reflected = creature.split("V_META(CCreature,", 1)[1].split("  public:", 1)[0]
        for name in (
            "activeCombatOwner",
            "defeatResolutionInProgress",
            "defeatResolutionUncertain",
            "activeDefeatRecipientCount",
        ):
            self.assertNotIn(name, reflected)
            self.assertIn(name, creature.split("  private:", 1)[1])

    def testParticipantClaimsPrecedeStatusAndControllerCallbacks(self):
        source = (ROOT / "src/handler/CFightHandler.cpp").read_text(encoding="utf-8")
        body = source.split("vstd::task<CFightResult> resolveFightManyAsync(", 1)[1]
        body = body.split("vstd::task<CFightResult> resolveConfiguredFightAsync(", 1)[0]
        self.assertIn("CCombatParticipantGuard participantGuard(", body)
        claim = body.index("CCombatParticipantGuard participantGuard(")
        early = body.split("{", 1)[1].split("auto encounterMap =", 1)[0]
        self.assertNotIn("encounterOpponents", early)
        self.assertNotIn("encounterAllies", early)
        for boundary in (
            "clear_combat_status(encounterMap)",
            "CFightHandler::resetCombatHistory(encounterMap)",
            "attackerController->setOpponents(",
            "FightControllerEndGuard controllerEndGuard;",
        ):
            self.assertLess(claim, body.index(boundary), boundary)
        self.assertIn("participants.insert(participants.end(), allies.begin(), allies.end());", body)
        self.assertIn("participant->activeCombatOwner.lock() == identity", source)
        self.assertIn("participant->activeDefeatRecipientCount != 0", source)

    def testActualDefeatLeaseAndUncertaintyCoverEveryMapThroughRecovery(self):
        source = (ROOT / "src/handler/CFightHandler.cpp").read_text(encoding="utf-8")
        self.assertIn("vstd::task<void> CFightHandler::resolveOwnedDefeatAsync(", source)
        owned = source.split("vstd::task<void> CFightHandler::resolveOwnedDefeatAsync(", 1)[1]
        self.assertIn("auto admission = encounterMap->tryBeginUnsafeOperation();", owned)
        self.assertLess(
            owned.index("auto admission = encounterMap->tryBeginUnsafeOperation();"), owned.index("a->addExpScaled(")
        )
        self.assertNotIn('getBoolProperty("guardNativeEncounterSaves")', owned)
        self.assertIn("if (!workStarted || (recoverySettled && admission->isCurrent()))", owned)
        self.assertLess(owned.index("b->defeatResolutionUncertain = true;"), owned.index("a->addExpScaled("))
        self.assertLess(
            owned.index('b->setStringProperty("uiDefeatReceipt", receipt.dump());'),
            owned.index("recoverySettled = true;"),
        )
        self.assertLess(owned.index("recoverySettled = true;"), owned.index("b->defeatResolutionUncertain = false;"))
        after_loot = owned.split("co_await rng->addRandomLootAsync(a, items);", 1)[1]
        self.assertLess(after_loot.index("!ownerIsCurrent()"), after_loot.index("encounterMap->removeObjectAsync(b)"))
        after_removal = after_loot.split("co_await encounterMap->removeObjectAsync(b);", 1)[1]
        self.assertIn("const auto recoveryIsComplete = [&]", after_removal)
        self.assertIn("!a->isAlive() || !is_registered_on_map(encounterMap, a)", after_removal)
        self.assertIn(
            "encounterMap->player == b && b->isAlive() && is_registered_on_map(encounterMap, b)", after_removal
        )
        self.assertIn(
            "encounterMap->getDefeatedPlayer() == b && encounterMap->hasRetainedTerminalPlayer()", after_removal
        )
        self.assertIn("std::ranges::none_of(encounterMap->getObjects()", after_removal)
        self.assertLess(after_removal.index("if (!recoveryIsComplete())"), after_removal.index("json receipt = {"))
        after_receipt = after_removal.split('b->setStringProperty("uiDefeatReceipt", receipt.dump());', 1)[1]
        self.assertLess(after_receipt.index("!recoveryIsComplete()"), after_receipt.index("if (showDefeat)"))
        self.assertIn("encounterOwner->defeatAdmission.emplace(std::move(*admission));", owned)
        settle = source.split("const auto settle_result = [&](CFightResult value) {", 1)[1].split("return value;", 1)[0]
        self.assertLess(settle.index("certifyCleanup();"), settle.index("ownedParticipants->settleDefeatAdmission();"))
        self.assertIn("std::optional<CGameContext::UnsafeOperationLease> defeatAdmission;", source)
        self.assertIn("DefeatScopeExit(const DefeatScopeExit &) = delete;", source)
        self.assertIn("DefeatScopeExit(DefeatScopeExit &&) = delete;", source)

    def testDefeatRacesExerciseRealRewardRemovalAndShutdownCallbacks(self):
        source = (ROOT / "tests/unit/test_handler.cpp").read_text(encoding="utf-8")
        for name in (
            "testDuplicateDefeatRejectsDuringRealLootAndRemoval",
            "testConcurrentPlayerDefeatPublishesOnlyRecoveredReceipt",
            "testDefeatCancellationAndFailureDrainOwnedRecovery",
            "testRecursiveDefeatRejectsBeforeItsOwnRecovery",
            "testOverlappingEncounterCannotStartSharedControllers",
            "testDefeatAdmissionRefusalAndAbandonedOwnersPreserveBoundaries",
            "testFailedOrdinaryDefeatRequiresVerifiedRestore",
            "testDefeatCallbackShutdownKeepsContextTaskAncestry",
            "testEncounterParticipantClaimsReleaseAfterThrowAndCancel",
            "testEncounterOwnershipIgnoresSanitizedIneligibleCandidates",
            "testDefeatRecoveryCertificationRejectsReplacedOrUnfinishedOwners",
            "testInternalDefeatLeaseSurvivesParentControllerCleanup",
        ):
            self.assertIn(f"void {name}() {{", source)
            self.assertEqual(1, source.count(f'nativeTestProfile().run("{name}",'))
        self.assertIn("co_await nativeRestart->triggerAsync(object, event);", source)
        self.assertIn('receipt.at("hp").get<int>() == 1', source)
        self.assertIn("for (const bool optedIn : {false, true})", source)
        self.assertIn("for (const int mode : {0, 1, 2, 3})", source)
        self.assertIn("owner->end_count == 1 && rejected->start_count == 0 && rejected->end_count == 0", source)
        self.assertIn("context->shutdown();\n            callbackReturned = true;", source)
        self.assertIn("weakLoser.expired()", source)
        self.assertIn("for (int mode = 0; mode < 7; ++mode)", source)
        self.assertIn("auto nativeRestart = std::make_shared<CCustomTrigger>(*registeredRestart);", source)
        self.assertRegex(source, r"\*registeredRestart\s*=\s*CCustomTrigger\(")
        recovery = source.split("void testConcurrentPlayerDefeatPublishesOnlyRecoveredReceipt() {", 1)[1]
        recovery = recovery.split("void testDefeatCancellationAndFailureDrainOwnedRecovery()", 1)[0]
        self.assertLess(recovery.index("auto player = add_test_player(game);"), recovery.index("player->setHp(-500);"))
        self.assertNotIn("getPlayer()", recovery.split("co_await nativeRestart->triggerAsync(object, event);", 1)[1])
        self.assertIn("startSaveAllowed == !optedIn && !endSaveAllowed", source)

    def testDefeatRejectionGuardKeepsFixedDeterministicWorkBudgets(self):
        source = (ROOT / "tests/unit/test_engine_hotspot_performance.cpp").read_text(encoding="utf-8")
        self.assertIn("void testDefeatResolutionRejectionsAndParticipantClaimsAreBounded() {", source)
        body = source.split("void testDefeatResolutionRejectionsAndParticipantClaimsAreBounded() {", 1)[1]
        body = body.split("void testMinimapTerrainCacheBuildsOnlyOnRelevantChanges()", 1)[0]
        for literal in (
            "constexpr int RECOVERIES = 4;",
            "constexpr int DUPLICATES_PER_RECOVERY = 32;",
            "constexpr int OVERLAPS_PER_RECOVERY = 32;",
            "duplicateRejections += rejectedDuplicate;",
            "duplicateRejections == RECOVERIES * DUPLICATES_PER_RECOVERY",
            "blockedController->starts == 0 && blockedController->actions == 0 && blockedController->ends == 0",
            "winner->getExp() == experience && winner->getHp() == hp",
            "fixture.map->getObjects().size() == 4 && fixture.map->getTurn() == turn",
            "independentController->actions == recovery + 1",
        ):
            self.assertIn(literal, body)
        self.assertEqual(1, source.count("    testDefeatResolutionRejectionsAndParticipantClaimsAreBounded();"))

    def testConfiguredFixtureIsRequiredByNativeAndGameplayValidation(self):
        import test as runner

        names = runner.discover_unittest_test_names(["test.py", "NativeTestProfileRuntimeTest"])
        self.assertEqual(5, len(names))
        self.assertEqual([], runner.filter_test_names_by_suite(names, "fast"))
        for suite in ("gameplay", "coverage-safe", "full"):
            self.assertEqual(names, runner.filter_test_names_by_suite(names, suite))
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("add_executable(native_test_profile_fixture tests/unit/native_test_profile_fixture.cpp)", cmake)
        self.assertIn("configure_cpp_target(native_test_profile_fixture)", cmake)
        self.assertIn("list(APPEND GAME_UNIT_TEST_TARGETS native_test_profile_fixture)", cmake)
        self.assertIn('add_test(NAME "for_unit_tests.native_test_profile_contracts"', cmake)
        self.assertIn("NativeTestProfileRuntimeTest -v", cmake)
        self.assertIn(
            'ENVIRONMENT "GAME_NATIVE_TEST_PROFILE_FIXTURE=$<TARGET_FILE:native_test_profile_fixture>"', cmake
        )
        self.assertRegex(cmake, r'LABELS "for_unit_tests;unit;native_test_profile_contracts"\s+TIMEOUT 60')
        fixture = (ROOT / "tests/unit/native_test_profile_fixture.cpp").read_text(encoding="utf-8")
        self.assertIn("for (int attempt = 0; attempt < 256; ++attempt)", fixture)
        self.assertIn("return samples == 768 ? 0 : 5", fixture)

    def testExplicitMissingCompiledFixtureCannotSkipMandatoryContracts(self):
        class MissingFixture(NativeTestProfileRuntimeTest):
            pass

        with tempfile.TemporaryDirectory(prefix="nouraajd-profile-preflight-") as directory:
            missing = Path(directory) / "missing-fixture"
            with mock.patch.dict(os.environ, {"GAME_NATIVE_TEST_PROFILE_FIXTURE": str(missing)}):
                with self.assertRaisesRegex(AssertionError, "Configured native profiling fixture is unavailable"):
                    MissingFixture.setUpClass()

    def testEveryExistingCaseKeepsItsOrderAndMetadataComesFirst(self):
        for suite, (count, digest) in BASELINE_CASES.items():
            source = (ROOT / f"tests/unit/test_{suite}.cpp").read_text(encoding="utf-8")
            main = source[source.rindex("int main() {") :]
            calls = re.findall(
                r'nativeTestProfile\(\)\.run\("(test\w+)",\s*'
                r'(?:(test\w+)\);|\[&\] \{\s*runTimedGuiCancellationTest\("(test\w+)",\s*(test\w+)\);\s*\}\);)',
                main,
            )
            additions = ADDITIONAL_CASES.get(suite, ())
            self.assertEqual(count + len(additions), len(calls), suite)
            self.assertTrue(
                all(
                    name == callback if callback else name == timed_name == timed_callback
                    for name, callback, timed_name, timed_callback in calls
                ),
                suite,
            )
            names = [name for name, *_callbacks in calls]
            self.assertEqual(additions, tuple(name for name in names if name in additions), suite)
            baseline_names = [name for name in names if name not in additions]
            self.assertEqual(count, len(baseline_names), suite)
            self.assertEqual(digest, hashlib.sha256("\n".join(baseline_names).encode()).hexdigest(), suite)
            self.assertFalse(re.search(r"^\s+(test\w+)\(\);", main, re.MULTILINE), suite)
            self.assertIn("return finish_tests();", main)
            if suite == "handler":
                self.assertEqual("testGameplayMetadataIsAvailableBeforePluginLoading", names[0])
                self.assertEqual(3, sum(bool(timed_name) for _name, _callback, timed_name, _timed_callback in calls))

    def testProfilesGoIntoTheUploadedSourceCoverageDirectoryWithoutChangingLimits(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        for suite in BASELINE_CASES:
            self.assertRegex(
                cmake,
                rf"target_compile_definitions\({suite}_unit_tests PRIVATE\s+"
                r'GAME_NATIVE_TEST_PROFILE_DIR="\$\{CMAKE_CURRENT_SOURCE_DIR\}/coverage/native-test-profiles"\)',
            )
        self.assertRegex(cmake, r'LABELS "for_unit_tests;unit;\$\{target_name\}"\s+TIMEOUT 60')
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        self.assertIn("coverage/", workflow)

    def testMeasuredHotCasesKeepTheirSamplingCountsAndExposeNestedPhases(self):
        handler = (ROOT / "tests/unit/test_handler.cpp").read_text(encoding="utf-8")
        self.assertTrue('nativeTestProfile().run("primeEncounterFixtureLevels",' in handler)
        for test_name, phases, loops in (
            (
                "test_rng_handler_encounter_candidates_stay_in_stable_power_buckets",
                ("CRngHandler::CRngHandler", "encounter samples(full-budget)", "encounter samples(tight-budget)"),
                2,
            ),
            (
                "test_rng_handler_excludes_player_templates_from_encounters",
                ("CRngHandler::CRngHandler", "encounter samples(player-exclusion)"),
                1,
            ),
        ):
            body = handler.split(f"void {test_name}() {{", 1)[1].split("\n}\n", 1)[0]
            self.assertEqual(loops, body.count("for (int attempt = 0; attempt < 256; attempt++)"))
            for phase in phases:
                self.assertTrue(f'nativeTestProfile().run("{phase}",' in body)
        map_source = (ROOT / "tests/unit/test_map.cpp").read_text(encoding="utf-8")
        race_case = map_source.split("void test_loader_race_overloads_preserve_default_and_attach_race() {", 1)[1]
        race_case = race_case.split("\n}\n", 1)[0]
        self.assertEqual(3, race_case.count('nativeTestProfile().run("CGameLoader::startGameWithPlayer",'))
        self.assertTrue('nativeTestProfile().run("CGameLoader::startRandomGameWithPlayer",' in race_case)
        self.assertEqual(1, race_case.count("CGameLoader::startRandomGameWithPlayer(random_game"))


class NativeTestProfileRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        explicit_fixture = os.environ.get("GAME_NATIVE_TEST_PROFILE_FIXTURE")
        if explicit_fixture:
            binary = Path(explicit_fixture)
            if not binary.is_file():
                raise AssertionError("Configured native profiling fixture is unavailable: " + str(binary))
        else:
            build_root = Path(os.environ.get("GAME_BUILD_DIR", ROOT / "cmake-build-release"))
            if not build_root.is_absolute():
                build_root = ROOT / build_root
            executable_name = "native_test_profile_fixture.exe" if os.name == "nt" else "native_test_profile_fixture"
            build_config = os.environ.get("GAME_BUILD_CONFIG")
            candidates = [build_root / build_config / executable_name] if build_config else []
            if os.name == "nt" and not build_config:
                candidates.append(build_root / "Release" / executable_name)
            candidates.append(build_root / executable_name)
            binary = next((path for path in candidates if path.is_file()), None)
            if binary is None:
                raise unittest.SkipTest("Build native_test_profile_fixture through the for_unit_tests target")
        scratch_root = ROOT / "build"
        scratch_root.mkdir(exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix="native-profile-check-", dir=scratch_root)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.scratch = Path(cls.temporary.name)
        cls.output = cls.scratch / "source coverage" / "profiles"
        cls.binary = binary.resolve()

    def runFixture(self, mode):
        return subprocess.run([str(self.binary), mode, str(self.output)], capture_output=True, text=True, timeout=5)

    def records(self):
        with (self.output / "fixture.tsv").open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream, delimiter="\t"))

    def testReturnsReferencesNestedCallsAndOriginalExceptionsArePreserved(self):
        result = self.runFixture("success")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        records = self.records()
        self.assertEqual(
            [
                ("START", "outer"),
                ("START", "setup"),
                ("DONE", "setup"),
                ("DONE", "outer"),
                ("START", "reference"),
                ("DONE", "reference"),
                ("START", "throws"),
                ("EXCEPTION", "throws"),
                ("START", "flush"),
                ("DONE", "flush"),
            ],
            [(record["event"], record["name"]) for record in records],
        )
        for record in records:
            self.assertEqual("fixture", record["suite"])
            self.assertGreaterEqual(float(record["wallMs"]), 0)
            if os.name == "nt" and record["event"] != "START":
                self.assertEqual(-1, float(record["cpuMs"]))
            else:
                self.assertGreaterEqual(float(record["cpuMs"]), 0)

    def testInterruptedActionsRetainTheirFlushedStart(self):
        result = self.runFixture("interrupt")
        self.assertEqual(23, result.returncode, result.stdout + result.stderr)
        self.assertEqual([("START", "interrupted")], [(row["event"], row["name"]) for row in self.records()])

    def testReturnCodeIsUnchanged(self):
        result = self.runFixture("return-code")
        self.assertEqual(17, result.returncode, result.stdout + result.stderr)
        self.assertEqual(["START", "DONE"], [row["event"] for row in self.records()])

    def testNestedSamplingBatchesRunEveryIterationOnce(self):
        result = self.runFixture("sampling-batches")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(
            [
                ("START", "unchanged-sampling"),
                ("START", "full-budget"),
                ("DONE", "full-budget"),
                ("START", "tight-budget"),
                ("DONE", "tight-budget"),
                ("START", "player-exclusion"),
                ("DONE", "player-exclusion"),
                ("DONE", "unchanged-sampling"),
            ],
            [(record["event"], record["name"]) for record in self.records()],
        )

    def testUnavailableDiagnosticOutputDoesNotChangeTheAction(self):
        if self.output.exists():
            shutil.rmtree(self.output)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text("a file blocks the directory", encoding="utf-8")
        try:
            result = self.runFixture("unavailable")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("profiling file is unavailable", result.stderr)
        finally:
            self.output.unlink()


if __name__ == "__main__":
    unittest.main()
