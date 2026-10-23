# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Source-only guards for the owned defeat continuation; no engine or map-resource imports."""

import ast
import os
from pathlib import Path
import re
import unittest

ROOT = Path(os.environ.get("DEFEAT_CONTINUATION_ROOT", Path(__file__).resolve().parents[1]))
CASES = (
    "testOwnedDefeatStopsAfterCallbackPublicationBeforeFurtherRewards",
    "testOwnedDefeatLootContinuationRejectsStalePublicationAndCancellation",
    "testOwnedDefeatRemovalCannotCertifyAnAwayBackPublication",
    "testOwnedDefeatGuardsLazyRngFactoryEnumeration",
    "testOwnedDefeatStopsBeforeSecondRandomLootFactory",
    "testOwnedDefeatNestedFactoryStopsBeforeNextPropertyAndConstructor",
    "testOwnedDefeatFirstMetadataCallbackStopsBeforeSecondMetadataAndSetter",
    "testOwnedDefeatCodecBoundaryPreservesOriginalFailureAndStopsContinuation",
    "testOwnedDefeatGraphActorBindingPreservesPrimaryBeforeRootAndProperties",
)


def cppBlock(source, marker):
    start = source.index(marker)
    cursor = source.index("{", start) + 1
    depth, quote, escape = 1, None, False
    while depth:
        char = source[cursor]
        if quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
        elif source.startswith("//", cursor):
            cursor = source.index("\n", cursor)
        elif source.startswith("/*", cursor):
            cursor = source.index("*/", cursor + 2) + 1
        elif char in "\"'":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        cursor += 1
    return source[start:cursor]


class DefeatContinuationSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fight = (ROOT / "src/handler/CFightHandler.cpp").read_text()
        cls.rng = (ROOT / "src/handler/CRngHandler.cpp").read_text()
        cls.header = (ROOT / "src/handler/CRngHandler.h").read_text()
        cls.native = (ROOT / "tests/unit/test_handler.cpp").read_text()
        cls.profile = (ROOT / "tests/test_native_test_profile.py").read_text()
        cls.body = cppBlock(cls.fight, "vstd::task<void> CFightHandler::resolveOwnedDefeatAsync(")

    def requiredBlock(self, source, marker):
        self.assertIn(marker, source)
        return cppBlock(source, marker)

    def testPublicEpochAndActiveContextAreCapturedBeforeWork(self):
        body = self.body
        self.assertIn("initialGame->getMapBindingEpoch()", body)
        owner = self.requiredBlock(body, "const auto ownerIsCurrent =")
        self.assertIn("initialContext->isActive()", owner)
        self.assertIn("game->getMapBindingEpoch() == initialEpoch", owner)
        self.assertIn("initialContext->isTransitionGenerationCurrent(initialGeneration)", owner)
        self.assertIn("b->defeatResolutionInProgress", owner)
        self.assertIn("a->activeDefeatRecipientCount != 0", owner)
        self.assertIn("game->getMap() == encounterMap", owner)
        self.assertIn("encounterMap->getGame() == game", owner)
        self.assertNotIn("getPlayer()", owner)
        self.assertNotIn("getAssignedPlayer()", owner)
        self.assertLess(body.index("initialGame->getMapBindingEpoch()"), body.index("workStarted = true"))

    def testFormatterAndScaleMustBeCheckedBeforeExperience(self):
        text = " ".join(self.body.split())
        self.assertIn(
            "const auto winnerDescription = a->to_string(); requireDefeatCurrent(); const auto loserDescription = b->to_string(); requireDefeatCurrent();",
            text,
        )
        self.assertIn(
            "loserDescription); requireDefeatCurrent(); const auto rewardScale = b->getScale(); requireDefeatCurrent(); a->addExpScaled(rewardScale); requireDefeatCurrent();",
            text,
        )
        guard = self.requiredBlock(self.body, "const auto requireDefeatCurrent =")
        self.assertIn("!a->isAlive() || b->isAlive()", guard)
        self.assertIn("!is_registered_on_map(encounterMap, a)", guard)
        self.assertIn("!is_registered_on_map(encounterMap, b)", guard)

    def testGatheringAndItemMetadataAreCheckedBeforeTransfer(self):
        text = " ".join(self.body.split())
        self.assertIn('getBoolProperty("plugin_cityFixedLoot"); requireDefeatCurrent();', text)
        self.assertIn("b->getAllItems() : b->getInInventory(); requireDefeatCurrent(); for", text)
        self.assertIn('getBoolProperty("plugin_cityUndroppable"); requireDefeatCurrent(); if (undroppable)', text)
        self.assertIn("item->hasTag(CTag::Quest); requireDefeatCurrent(); if (!retainedQuestItem)", text)
        self.assertIn("b->removeItem(item); requireDefeatCurrent();", text)
        self.assertIn("b->setGold(0); requireDefeatCurrent(); a->addGold(ownedGold); requireDefeatCurrent();", text)

    def testCancellationCompensationRequiresCurrentOwnerBeforeAnyGrant(self):
        body = self.body
        self.assertIn("cancellation = std::current_exception();\n        requireDefeatCurrent();", body)
        catch = body[body.index("cancellation = std::current_exception();") : body.index("if (cancellation) {")]
        self.assertLess(
            catch.index("requireDefeatCurrent();"), catch.index("std::set<std::shared_ptr<CItem>> pendingItems")
        )
        self.assertIn(
            "requireDefeatCurrent(); a->addItems(std::move(pendingItems)); requireDefeatCurrent();",
            " ".join(catch.split()),
        )
        self.assertIn("std::rethrow_exception(cancellation);", body)

    def testOnlyPrivateFriendDefeatRngCanReceiveTheGuard(self):
        public = cppBlock(self.rng, "vstd::task<void> CRngHandler::addRandomLootAsync(")
        self.assertIn("return addDefeatLootAsync(std::move(creature), std::move(items), {});", public)
        self.assertNotIn("requireCurrent", public)
        private = self.header[self.header.index("  private:") :]
        self.assertIn("friend class CFightHandler;", private)
        self.assertIn("addDefeatLootAsync", private)
        self.assertIn("std::function<void()> requireCurrent", private)
        self.assertNotIn("addDefeatLootAsync", self.header[: self.header.index("  private:")])
        self.assertIn("rng->addDefeatLootAsync(a, items, requireDefeatCurrent)", self.body)

    def testChildChecksBothNormalAndCancelledGrantsAndLazyPlayerClassification(self):
        child = self.requiredBlock(self.rng, "vstd::task<void> CRngHandler::addDefeatLootAsync(")
        text = " ".join(child.split())
        self.assertIn(
            "if (requireCurrent) { requireCurrent(); } const bool player = creature->isPlayer(); if (requireCurrent) { requireCurrent(); }",
            text,
        )
        self.assertIn(
            "catch (const vstd::task_cancelled &) { if (requireCurrent) { requireCurrent(); } creature->addItems(items); throw;",
            text,
        )
        self.assertIn("} if (requireCurrent) { requireCurrent(); } creature->addItems(items);", text)
        self.assertEqual(child.count("creature->addItems(items)"), 2)
        self.assertIn("std::function<void()> requireCurrent) -> vstd::task<void>", child)
        self.assertIn("std::move(requireCurrent)", child)

    def testGuardCopiesNoStrongGameOrStackReferenceAcrossTheAwait(self):
        owner = self.requiredBlock(self.body, "const auto ownerIsCurrent =")
        captures = owner[: owner.index("{")]
        self.assertNotIn("[&]", captures)
        self.assertIn("expectedGame", captures)
        self.assertNotRegex(captures, r"\bgame\b")
        guard = self.requiredBlock(self.body, "const auto requireDefeatCurrent =")
        self.assertNotIn("[&]", guard[: guard.index("{")])
        before = self.body[: self.body.index("co_await rng->addDefeatLootAsync")]
        self.assertLess(before.rindex("game.reset();"), len(before))
        self.assertNotIn("getPlayer()", guard)

    def testRemovalAndFinalCertificateCannotIgnoreEpochButKeepStablePlayerPolicy(self):
        body = self.body
        self.assertIn("co_await removal.waitFinished();\n        requireOwnerCurrent();", body)
        self.assertIn("co_await encounterMap->removeObjectAsync(b);\n    }\n    requireOwnerCurrent();", body)
        self.assertIn("capturedPlayer != defeatedPlayer || encounterMap->getAssignedPlayer() != defeatedPlayer", body)
        self.assertIn("const bool playerDefeat = defeatedPlayer != nullptr;", body)
        self.assertNotIn("b->isPlayer()", body)
        self.assertIn("encounterOwner->defeatAdmission.emplace(std::move(*admission))", body)
        self.assertIn("if (!workStarted || (recoverySettled && admission->isCurrent()))", body)
        self.assertIn("b->defeatResolutionUncertain = false;", body)
        old_case = self.requiredBlock(
            self.native, "void testDefeatRecoveryCertificationRejectsReplacedOrUnfinishedOwners("
        )
        self.assertIn("mode < 7", old_case)
        self.assertIn("mode == 6", old_case)
        self.assertIn("map->addObject(player)", old_case)

    def testAdversarialCasesUseActualCallbacksModalAndCanonicalRestart(self):
        first = self.requiredBlock(self.native, "void " + CASES[0] + "(")
        self.assertIn("loser->formatting = callback", first)
        self.assertIn("loser->gathering = callback", first)
        self.assertIn("publication : {0, 1, 2, 3}", first)
        self.assertIn("experienceAtCallback", first)
        self.assertIn("unit defeat callback primary failure", first)
        loot = self.requiredBlock(self.native, "void " + CASES[1] + "(")
        self.assertIn('findChild("CGameLootPanel")', loot)
        self.assertIn("owner.requestStop()", loot)
        self.assertIn("panel->close()", loot)
        self.assertIn("!winner->hasInInventory(item) && !loser->hasInInventory(item)", loot)
        recovery = self.requiredBlock(self.native, "void " + CASES[2] + "(")
        self.assertIn("auto player = add_test_player(game);", recovery)
        self.assertIn("std::make_shared<CCustomTrigger>(*restart)", recovery)
        self.assertIn("co_await nativeRestart->triggerAsync(object, event)", recovery)
        self.assertIn("game->setMap(replacement);\n            game->setMap(map);", recovery)
        self.assertIn('player->getStringProperty("uiDefeatReceipt").empty() == stale', recovery)

    def testOrderedNativeProfileIncludesNewCasesExactlyOnce(self):
        assignments = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in ast.parse(self.profile).body
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"BASELINE_CASES", "ADDITIONAL_CASES"}
        }
        self.assertEqual(
            assignments["BASELINE_CASES"]["handler"],
            (36, "133d76b3db645f21a09e2b55fc738f481318a97c42532b80bb67edba5354a89d"),
        )
        self.assertEqual(
            assignments["BASELINE_CASES"]["map"],
            (49, "17f592c7f09a057f9c3249babde697470899143ffda78688662f61ab5cfbdf9e"),
        )
        catalog = assignments["ADDITIONAL_CASES"]["handler"]
        for case in CASES:
            self.assertEqual(catalog.count(case), 1)
            self.assertEqual(len(re.findall(r"void " + case + r"\(\)", self.native)), 1)
            self.assertEqual(self.native.count('nativeTestProfile().run("' + case + '"'), 1)
        start = catalog.index("testInternalDefeatLeaseSurvivesParentControllerCleanup") + 1
        self.assertEqual(tuple(catalog[start : start + len(CASES)]), CASES)

    def testGuardedServiceAcquisitionIsPrivateAndNeverCallsGuardUnderMutex(self):
        context = (ROOT / "src/core/CGameContext.cpp").read_text()
        header = (ROOT / "src/core/CGameContext.h").read_text()
        self.assertIn("getDefeatRngHandler", header[header.rindex("  private:") :])
        self.assertIn("friend class CFightHandler;", header)
        private = self.requiredBlock(context, "std::shared_ptr<CRngHandler> CGameContext::getDefeatRngHandler(")
        self.assertIn("new CRngHandler(owner, requireCurrent)", private)
        self.assertLess(private.index("requireCurrent();"), private.index("cached = rngHandler;"))
        self.assertIn("auto created =", private)
        self.assertIn("requireCurrent();\n    {\n        std::lock_guard", private)
        # Both critical sections contain only concrete native cache/admission operations.
        for marker in ("std::lock_guard lock(*resourceMutex);",):
            for start in [match.start() for match in re.finditer(re.escape(marker), private)]:
                end = private.index("\n    }", start)
                self.assertNotIn("requireCurrent();", private[start:end])
        self.assertIn("initialContext->getDefeatRngHandler(requireDefeatCurrent)", self.body)
        self.assertNotIn("getRngHandler()", self.body)

    def testEveryPrototypeAndInitializationFactoryHasImmediateChecks(self):
        objects = (ROOT / "src/handler/CObjectHandler.cpp").read_text()
        header = (ROOT / "src/handler/CObjectHandler.h").read_text()
        self.assertIn("friend class CRngHandler;", header)
        self.assertIn("getDefeatSubTypes", header[header.rindex("  private:") :])
        method = self.requiredBlock(objects, "std::vector<std::string> CObjectHandler::getDefeatSubTypes(")
        self.assertIn(
            "if (requireCurrent) { requireCurrent(); } auto prototype = getType(getClass(type)); if (requireCurrent) { requireCurrent(); }",
            " ".join(method.split()),
        )
        constructor = self.requiredBlock(
            self.rng,
            "CRngHandler::CRngHandler(const std::shared_ptr<CGame> &game, std::function<void()> requireCurrent)",
        )
        text = " ".join(constructor.split())
        for selected in ("CItem", "CCreature"):
            self.assertIn('getDefeatSubTypes("' + selected + '", requireCurrent)', text)
        self.assertIn("game->createObject<CItem>(type); checkCurrent();", text)
        self.assertIn("game->createObject<CCreature>(type); checkCurrent();", text)
        self.assertIn("getType(game->getObjectHandler()->getClass(type)); checkCurrent();", text)
        self.assertNotIn("->getAllSubTypes(", constructor)

    def testGeneratedFactoryIsCheckedBeforeAnotherConstructionOrLocalRetention(self):
        private = self.requiredBlock(self.rng, "std::set<std::shared_ptr<CItem>> CRngHandler::calculateDefeatLoot(")
        text = " ".join(private.split())
        self.assertIn(
            "if (requireCurrent) { requireCurrent(); } auto item = currentGame->createObject<CItem>(*vstd::random_element(possible_names)); if (requireCurrent) { requireCurrent(); } loot.insert(std::move(item));",
            text,
        )
        self.assertIn("items = lootRng->calculateDefeatLoot(randomLootScale, requireDefeatCurrent);", self.body)
        self.assertIn(
            "const auto randomLootScale = b->getScale(); requireDefeatCurrent();", " ".join(self.body.split())
        )
        self.assertIn("value = clampRandomValue(value);", private)
        self.assertIn("itemPowerTable | std::views::keys", private)
        self.assertIn("itemPowerTable.equal_range(pow)", private)
        self.assertIn("value -= pow;", private)
        public = self.requiredBlock(self.rng, "std::set<std::shared_ptr<CItem>> CRngHandler::getRandomLoot(")
        self.assertEqual(
            "std::set<std::shared_ptr<CItem>> CRngHandler::getRandomLoot(int value) const { return calculateRandomLoot(value); }",
            public,
        )
        wrapper = self.requiredBlock(self.rng, "std::set<std::shared_ptr<CItem>> CRngHandler::calculateRandomLoot(")
        self.assertIn("return calculateDefeatLoot(value, {});", wrapper)

    def testNativeFactoriesUseRealRegistrationsAndAnArmedSecondConstructorSentinel(self):
        lazy = self.requiredBlock(self.native, "void " + CASES[3] + "(")
        self.assertIn("phase : {0, 1, 2, 3}", lazy)
        self.assertIn("publication : {0, 1, 2, 3}", lazy)
        self.assertEqual(lazy.count("objects->registerType("), 4)
        self.assertIn("firstItem == phase + 1", lazy)
        self.assertIn("firstCreature == 4", lazy)
        self.assertIn("sentinelAfter == sentinelAtCallback", lazy)
        self.assertNotIn("game->getRngHandler()", lazy)
        generated = self.requiredBlock(self.native, "void " + CASES[4] + "(")
        self.assertLess(generated.index("auto rng = game->getRngHandler();"), generated.index("armed = true;"))
        self.assertIn("loser->setSw(2);", generated)
        self.assertIn("item->setPower(1);", generated)
        self.assertIn("factories == 2 && secondConstructor == 1", generated)
        self.assertIn("factories == 1 && secondConstructor == 0", generated)
        self.assertIn("!map->tryBeginSaveSnapshot()", generated)
        self.assertIn("unit generated loot factory primary failure", generated)

    def testConfiguredSentinelsAreReachableBeforeArmingNativeWork(self):
        lazy = self.requiredBlock(self.native, "void testOwnedDefeatGuardsLazyRngFactoryEnumeration(")
        self.assertIn('objects->registerConfig(name, std::make_shared<json>(json{{"class", name}}))', lazy)
        self.assertIn("objects->getConfig(name) && objects->getClass(name) == name", lazy)
        self.assertLess(lazy.index("objects->registerConfig("), lazy.index("auto owner ="))
        generated = self.requiredBlock(self.native, "void testOwnedDefeatStopsBeforeSecondRandomLootFactory(")
        self.assertLess(generated.index("registerConfig("), generated.index("auto rng ="))
        self.assertIn('getClass("AUnitTwoFactoryItem") == "AUnitTwoFactoryItem"', generated)

    def testFactoryScopeIsPrivateValueOwnedAndRestoresExactPreviousState(self):
        objects = (ROOT / "src/handler/CObjectHandler.cpp").read_text()
        header = (ROOT / "src/handler/CObjectHandler.h").read_text()
        private = header[header.rindex("  private:") :]
        self.assertIn("beginDefeatConstruction", private)
        self.assertIn("static thread_local std::shared_ptr<DefeatConstructionState>", private)
        self.assertIn("std::function<void()> requireCurrent", objects)
        self.assertIn("state->parent = previous;", objects)
        self.assertIn("state->requireCurrent = std::move(requireCurrent);", objects)
        destructor = self.requiredBlock(objects, "CObjectHandler::DefeatConstructionScope::~DefeatConstructionScope()")
        self.assertIn("defeatConstructionState = std::move(previous);", destructor)
        self.assertIn("std::exchange(other.owned, false)", objects)
        self.assertNotIn("getContext(", destructor)
        self.assertNotIn("getObjectHandler(", destructor)
        self.assertIn("state(previous)", objects)

    def testCentralConstructorPinsAndLatchesFirstFailureBeforeAnotherFactory(self):
        objects = (ROOT / "src/handler/CObjectHandler.cpp").read_text()
        factory = self.requiredBlock(objects, "std::shared_ptr<CGameObject> CObjectHandler::getType(")
        text = " ".join(factory.split())
        self.assertIn("auto construction = defeatConstructionState; if (construction) { construction->check(); }", text)
        self.assertIn(
            "auto object = constructors[name](); if (construction) { construction->check(); } return object;", text
        )
        self.assertIn("construction->remember(std::current_exception()); construction->rethrowFailure();", text)
        state = self.requiredBlock(objects, "struct CObjectHandler::DefeatConstructionState")
        self.assertIn("if (!failure)", state)
        self.assertIn("parent->remember(primary);", state)
        self.assertIn("parent->rethrowFailure();", state)
        self.assertIn("remember(std::move(primary));", state)
        for marker in (
            "CRngHandler::CRngHandler(const std::shared_ptr<CGame> &game,",
            "std::set<std::shared_ptr<CItem>> CRngHandler::calculateDefeatLoot(",
        ):
            method = self.requiredBlock(self.rng, marker)
            self.assertIn("beginDefeatConstruction(requireCurrent)", method)
            self.assertIn("factories.rethrowFailure();", method)

    def testSerializerChecksLatchedFailureBeforeLegacySkipAndAfterCodecBeforeSetter(self):
        source = (ROOT / "src/core/CSerialization.cpp").read_text()
        method = self.requiredBlock(
            source,
            "std::shared_ptr<CGameObject> object_deserialize(const std::shared_ptr<CGame> &game, const json *config,",
        )
        text = " ".join(method.split())
        self.assertIn("CSerializationConstructionGuard::check(); try { CSerialization::setProperty", text)
        self.assertIn(
            "catch (const std::exception &exception) { CSerializationConstructionGuard::rethrowFailure(); CSerializationConstructionGuard::check(); if (context.isStrict())",
            text,
        )
        self.assertIn("if (context.isStrict())", method)
        other = self.requiredBlock(source, "void CSerialization::setOtherProperty(")
        self.assertIn(
            "codec->deserialize(object->getGame(), payload, context));\n        CSerializationConstructionGuard::check();",
            other,
        )
        self.assertLess(other.index("codec->deserialize"), other.index("CSerializationConstructionGuard::callback([&]"))
        self.assertEqual(other.count("CSerializationConstructionGuard::rethrowFailure();"), 2)
        self.assertIn("CSerializationConstructionGuard::callback([&] {", other)
        self.assertNotIn("StrictScope", method)

    def testInitializationAndBothMetadataCallsAreGuardedWithoutLazyLookup(self):
        source = (ROOT / "src/core/CSerialization.cpp").read_text()
        for marker in (
            "    void initialize(const std::shared_ptr<CGameObject> &object)",
            "    void finish(const std::shared_ptr<CGame> &game, CSerializationReadContext &context)",
        ):
            method = self.requiredBlock(source, marker)
            self.assertIn("CSerializationConstructionGuard::metadata(object)", method)
            self.assertIn("CSerializationConstructionGuard::initialize([&]", method)
        header = (ROOT / "src/object/CGameObject.h").read_text()
        setter = self.requiredBlock(header, "    template <typename T> void setProperty(std::string name, T property)")
        text = " ".join(setter.split())
        self.assertIn("auto metadata = this->meta(); game_detail::requireCurrentDefeatConstruction();", text)
        self.assertIn(
            "const bool registered = metadata->has_property(name, object); game_detail::requireCurrentDefeatConstruction();",
            text,
        )
        self.assertIn("auto setterMetadata = this->meta(); game_detail::requireCurrentDefeatConstruction();", text)
        self.assertEqual(setter.count("this->meta()"), 2)
        self.assertIn("directPropertyNotificationSuppressedNames.pop_back();", setter)
        self.assertIn("game_detail::preserveDefeatCallbackFailure(primary);", setter)
        self.assertIn("recordPropertyChanged(name);", setter)
        for forbidden in ("getContext(", "getObjectHandler(", "getPlayer(", "getAssignedPlayer("):
            self.assertNotIn(forbidden, setter)
        self.assertIn('#include "core/CExport.h"', header)
        self.assertIn("GAME_CORE_EXPORT void requireCurrentDefeatConstruction();", header)

    def testNestedNativeWitnessChecksActualOrderNonVacuousFirstAndLegacySkip(self):
        method = self.requiredBlock(
            self.native, "void testOwnedDefeatNestedFactoryStopsBeforeNextPropertyAndConstructor("
        )
        for token in (
            "properties.items()",
            '"aFirstChild"',
            '"mAfterFirstScalar"',
            '"zSecondChild"',
            "constructed && firstConstructor == 1",
            "secondConstructor == 0",
            "secondConstructor == 1",
            'getNumericProperty("mAfterFirstScalar") == 0',
            'getNumericProperty("mAfterFirstScalar") == 123',
            "constructed->getPower() == 1",
            "winner->getExp() == experienceAtCallback",
            'objects->getType("AUnitNestedRootItem") != nullptr',
            "!map->tryBeginSaveSnapshot()",
            "unit nested factory primary failure",
        ):
            self.assertIn(token, method)
        self.assertLess(method.index("auto rng ="), method.index("armed = true;"))
        self.assertIn("getClass(name) == name", method)
        self.assertIn("publication : {0, 1, 2, 3}", method)

    def testNativeFirstMetaWitnessUsesActualSetterAndStopsBeforeSecondCall(self):
        definition = self.requiredBlock(self.native, "class DefeatMetaBarrierItem")
        self.assertIn("std::shared_ptr<vstd::meta> meta() override", definition)
        method = self.requiredBlock(
            self.native, "void testOwnedDefeatFirstMetadataCallbackStopsBeforeSecondMetadataAndSetter("
        )
        for token in (
            'item->setNumericProperty("unitMetaTarget", 123)',
            "metadataCallsAtSetterExit == 1",
            "metadataCallsAtSetterExit == 2",
            'getNumericProperty("unitMetaTarget") == 0',
            'getNumericProperty("unitMetaTarget") == 123',
            "constructed && callbacks == 1",
            "winner->getExp() == experienceAtCallback",
            "unit metadata callback primary failure",
        ):
            self.assertIn(token, method)
        self.assertLess(method.index("auto rng ="), method.index("armed = true;"))
        self.assertIn('registerConfig("AUnitMetadataBarrierItem"', method)

    def testEmptyPublicWrappersAndNoScopeSkipRemainAvailable(self):
        objects = (ROOT / "src/handler/CObjectHandler.cpp").read_text()
        check = self.requiredBlock(objects, "void CObjectHandler::checkDefeatConstruction()")
        self.assertIn("if (auto state = defeatConstructionState)", check)
        self.assertNotIn("else", check)
        public = self.requiredBlock(self.rng, "std::set<std::shared_ptr<CItem>> CRngHandler::calculateRandomLoot(")
        self.assertIn("return calculateDefeatLoot(value, {});", public)
        source = (ROOT / "src/core/CSerialization.cpp").read_text()
        callback = self.requiredBlock(source, "    template <typename Callback> static void callback(")
        self.assertIn("preserveDefeatConstructionCallbackFailure(std::current_exception())", callback)
        self.assertNotIn("rememberDefeatConstructionFailure", callback)
        fallback = self.requiredBlock(
            objects,
            "std::shared_ptr<CGameObject> CObjectHandler::_createObject(std::shared_ptr<CGame> game, const std::string &type,\n",
        )
        self.assertIn('{"class", type}', fallback)

    def testCodecBoundaryPreservesPrimaryBeforeCheckingOrWrapping(self):
        source = (ROOT / "src/core/CSerialization.cpp").read_text()
        method = self.requiredBlock(source, "void CSerialization::setOtherProperty(")
        for catch in ("catch (const CSerializationException &exception)", "catch (const std::exception &exception)"):
            body = self.requiredBlock(method, catch)
            self.assertIn("preserveCallbackFailure(std::current_exception())", body)
            self.assertIn("CSerializationConstructionGuard::check();", body)
            self.assertLess(
                body.index("preserveCallbackFailure(std::current_exception())"),
                body.index("CSerializationConstructionGuard::check();"),
            )
        native = self.requiredBlock(
            self.native, "void testOwnedDefeatCodecBoundaryPreservesOriginalFailureAndStopsContinuation("
        )
        for token in (
            "CTypes::findCodec(typeid(int))",
            "CTypes::registerCodec(typeid(int), probe)",
            "CTypes::registerCodec(typeid(int), original)",
            "~RestoreCodec()",
            "constructed && calls == 1",
            'getNumericProperty("zAfterCodec") == 0',
            'getNumericProperty("zAfterCodec") == 123',
            "unit codec boundary primary failure",
        ):
            self.assertIn(token, native)

    def testPreallocatedGraphActorBindingAndRemainingReadMetadataUseTheSameLatch(self):
        source = (ROOT / "src/core/CSerialization.cpp").read_text()
        method = self.requiredBlock(source, "    void prepare(const std::shared_ptr<CGame> &game, const json *config)")
        self.assertIn("CSerializationConstructionGuard::initialize([&] { actor->setGame(game); });", method)
        self.assertLess(method.index("actor->setGame(game)"), method.index("actors.emplace"))
        reference = self.requiredBlock(source, "    std::shared_ptr<CCreature> reference(")
        self.assertIn("CSerializationConstructionGuard::typeName(actor)", reference)
        compatible = self.requiredBlock(source, "template <typename T> bool isCompatiblePrimitiveObjectConfig(")
        self.assertIn("CSerializationConstructionGuard::metadata(type)", compatible)
        native = self.requiredBlock(
            self.native, "void testOwnedDefeatGraphActorBindingPreservesPrimaryBeforeRootAndProperties("
        )
        for token in (
            '"effectGraph"',
            '"effectActorId"',
            "graphActor && callbacks == 1",
            "rootFactories == 0",
            "rootFactories == 1",
            'getNumericProperty("unitAfterBinding") == 0',
            'getNumericProperty("unitAfterBinding") == 123',
            "unit graph actor binding primary failure",
            "publication : {0, 1, 2, 3}",
            "!map->tryBeginSaveSnapshot()",
        ):
            self.assertIn(token, native)


if __name__ == "__main__":
    unittest.main()
