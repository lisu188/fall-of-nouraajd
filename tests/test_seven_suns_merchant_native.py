# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source/model contracts; these checks grant no native execution or classic parity credit."""

from pathlib import Path
import re
import unittest

from tests.cpp_bindings import registrationTokens

ROOT = Path(__file__).resolve().parents[1]
PATHS = (
    (0, (0, 3), False),
    (0, (1, 4, 8), False),
    (0, (1, 5, 9, 7), False),
    (0, (1, 5, 10, 8), False),
    (0, (1, 5, 11, 12), True),
    (0, (1, 6, 7), False),
    (0, (2, 7), False),
    (7, (13, 16), False),
    (7, (14, 17), True),
    (7, (15, 17), True),
    (10, (18, 21), True),
    (10, (19, 22), True),
    (10, (20, 23), True),
)


class SevenSunsMerchantNativeSourceTest(unittest.TestCase):
    def source(self, name="src/handler/CSevenSunsMerchantDialogue.cpp"):
        path = ROOT / name
        self.assertTrue(path.is_file(), f"Missing finite merchant source: {name}")
        return path.read_text(encoding="utf-8")

    def tokens(self, name="src/handler/CSevenSunsMerchantDialogue.cpp"):
        return registrationTokens(self.source(name))

    def testAllThirteenAuditedPathsCoverExactlyTwentyFourNativeEdges(self):
        source = self.source().split("constexpr std::array<Edge, 24> Edges", 1)[1].split("void require", 1)[0]
        rows = re.findall(
            r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(true|false)\s*,\s*(true|false)\s*,\s*(true|false)\s*\}",
            source,
        )
        edges = {
            int(index): (int(origin), int(target), checked == "true", reveal == "true", end == "true")
            for index, origin, target, checked, reveal, end in rows
        }
        self.assertEqual(list(range(24)), list(edges))
        covered = set()
        for entry, path, reveal in PATHS:
            cursor = entry
            effects = []
            for index, edge in enumerate(path):
                origin, target, checked, changes_reveal, terminal = edges[edge]
                self.assertEqual(cursor, origin)
                self.assertEqual(index == len(path) - 1, terminal)
                if checked:
                    effects.append(("CheckedSevenSuns", 2))
                if changes_reveal:
                    effects.extend((("Doppleganger", 1), ("Laola", 1)))
                cursor = target
                covered.add(edge)
            self.assertEqual(reveal, edges[path[-1]][3])
            self.assertLessEqual(len(path), 4)
            self.assertEqual(1 if entry == 0 else 0, effects.count(("CheckedSevenSuns", 2)))
        self.assertEqual(set(range(24)), covered)
        self.assertEqual(6, sum(path[2] for path in PATHS))

        def terminal_paths(state, prefix=()):
            for edge, (origin, target, checked, reveal, terminal) in edges.items():
                if origin != state:
                    continue
                if terminal:
                    yield prefix + (edge,), reveal
                else:
                    yield from terminal_paths(target, prefix + (edge,))

        actual = {(entry, path, reveal) for entry in (0, 7, 10) for path, reveal in terminal_paths(entry)}
        self.assertEqual(set(PATHS), actual)

    def testInitiationCounterIsSeparateCommittedAndNotSaturatedOrLegacyInferred(self):
        source = self.tokens()
        for expression in (
            'CountKey="plugin_cityDopmerTalkCount"',
            'returnrefuse("legacyCountUnknown",n,revision)',
            "if(n>=3)",
            'returnrefuse("noAuditedEntry",n,revision)',
            "value->count.write(n+1,check)",
            'value->row["entry"]=n==0?0:n==1?7:10',
        ):
            self.assertIn(expression, source)
        begin = source.split("CSevenSunsMerchantDialogue::begin(", 1)[1].split("::requireCurrent()", 1)[0]
        self.assertLess(begin.index('returnrefuse("noAuditedEntry"'), begin.index("value->count.write(n+1"))
        self.assertNotIn("std::min(n,2)", begin)

    def testNativeSharedGlobalNamesAndWriteOrderPreserveClassicScope(self):
        source = self.tokens()
        self.assertIn('GlobalsKey="plugin_citySourceGlobals"', source)
        self.assertIn('source.at("GLOBAL").items()', source)
        self.assertIn("canonical(key)==canonical(name)", source)
        self.assertIn("std::from_chars", source)
        self.assertIn("numeric>=std::numeric_limits<int>::min()&&numeric<=std::numeric_limits<int>::max()", source)
        advance = source.split("::advance(intrevision,intedgeIndex)", 1)[1].split("::close()", 1)[0]
        self.assertLess(advance.index('writeGlobal("Doppleganger",1'), advance.index('writeGlobal("Laola",1'))
        self.assertLess(
            advance.index('writeGlobal("CheckedSevenSuns",2'), advance.index('writeGlobal("Doppleganger",1')
        )
        self.assertNotIn(".get<int>()", advance)

    def testDialogueTerminalDoesNotPerformReplacementBeforeCoordinatorTurn(self):
        source = self.tokens()
        advance = source.split("::advance(intrevision,intedgeIndex)", 1)[1].split("::close()", 1)[0]
        self.assertIn('edge->terminal?"closed":"active"', advance)
        self.assertNotIn("publish(", advance)
        self.assertNotIn("::settle(", advance)
        self.assertNotIn("MerchantStock::prepare", advance)
        settle = source.split("CSevenSunsMerchantDialogue::settle(", 1)[1]
        self.assertIn("for(constauto&identity:Lineages)", settle)
        self.assertIn("++checked;if(area!=identity.area)continue", settle)
        self.assertIn('value->global("Doppleganger")!=1', settle)
        self.assertIn("std::optional<int>{128}", settle)
        self.assertIn('CPlaytestTrace::record("seven_suns_merchants_settle",result)', settle)

    def testExactFourLineagesExcludeWarningJhassoAndBasementIdentity(self):
        source = self.source().split("constexpr std::array<Lineage, 4>", 1)[1].split("struct Edge", 1)[0]
        for name in ("cityAr0601Actor1", "cityAr0601Actor3", "cityAr0602Actor1", "cityAr0602Actor2"):
            self.assertEqual(1, source.count(name))
        for name in ("cityAr0601Actor2", "cityAr0603Actor1", "cityAr0603Actor2"):
            self.assertNotIn(name, source)

    def testAllCallbackBoundariesPinExactMapPlayerClockSourceAndAllegiance(self):
        source = self.tokens()
        for expected in (
            "map->getGame()==owner",
            "player->getGame()==owner",
            "clock->getGame()==owner",
            "owner->getMapBindingEpoch()==epoch",
            "regionEpoch(owner,map)==region",
            "context->isTransitionGenerationCurrent(generation)",
            "allegiance.check()",
            "receipt.check()",
            "oldRef.check()",
            "newRef.check()",
            "std::weak_ptr<CGame>game",
        ):
            self.assertIn(expected, source)
        self.assertIn("found->second->poisoned=true", source)
        self.assertIn("lease->isSaveAdmissionHealthy()", source)
        self.assertIn("lease->quarantine()", source)

    def testFixedStockPreparedAndSettledValidationHaveDifferentAuthority(self):
        source = self.tokens()
        self.assertEqual(2, source.count("CSevenSunsMerchantStock::validatePrepared("))
        self.assertIn("CSevenSunsMerchantStock::validateSettled(", source)
        self.assertIn("[this]{check(false);}", source)
        settle = source.split("CSevenSunsMerchantDialogue::settle(", 1)[1]
        self.assertLess(settle.index("oldRef.write(candidate,check)"), settle.index("MerchantStock::prepare("))
        self.assertLess(settle.index("MerchantStock::prepare("), settle.index("publish(game,map"))
        self.assertLess(settle.index("publish(game,map"), settle.rindex("MerchantStock::validatePrepared("))
        self.assertIn("beginDefeatConstruction(check)", settle)

    def testPrivateScenePublicationKeepsOldLifetimeAndNeverFiresLifecycleEvents(self):
        self.source()
        scene = self.tokens("src/core/CSceneManager.cpp").split("::replaceObjectWithoutEvents(", 1)[1]
        self.assertIn("retireObjectWithoutEvents(game,map,oldObject,requireCurrent)", scene)
        self.assertIn("map->addObjectWithoutEvents(newObject)", scene)
        self.assertIn("sceneRetiredLifetimeOwners.insert(newObject)", scene)
        self.assertIn("newObject->clearOwningMap(map)", scene)
        self.assertNotIn("gameEvent(", scene)
        self.assertNotIn("onDestroy", scene)

    def testStagedLifetimeAnchorIsPrivateAndHasNoSerializedOrLifecycleEffect(self):
        self.source()
        scene = self.tokens("src/core/CSceneManager.cpp")
        staged = scene.split("::retainStagedObjectLifetime(", 1)[1].split("::sceneRegionRevision(", 1)[0]
        self.assertIn("sceneRetiredLifetimeOwners.insert(candidate)", staged)
        self.assertIn("candidate->owningMap.expired()", staged)
        self.assertNotIn("sceneRetiredObjects.insert", staged)
        self.assertNotIn("removeObject", staged)
        self.assertNotIn("gameEvent", staged)
        self.assertNotIn("addExp", staged)
        header = self.tokens("src/core/CSceneManager.h")
        self.assertIn("friendclassCSevenSunsMerchantStock;", header)
        self.assertGreater(header.index("voidretainStagedObjectLifetime("), header.index("private:"))

    def testActiveCombatAndClosedAdmissionRetryBeforeSourceWrites(self):
        source = self.tokens()
        settle = source.split("CSevenSunsMerchantDialogue::settle(", 1)[1]
        self.assertLess(settle.index("combatOwned(candidate)"), settle.index("tryBeginUnsafeOperation()"))
        self.assertIn("if(!lease){retry=true;continue;}", settle)
        self.assertIn("!combatOwned(candidate)&&lease->isSaveAdmissionHealthy()", settle)
        helper = self.tokens("src/handler/CFightHandler.cpp")
        self.assertIn("returnCCombatParticipantGuard::isOwned(actor)", helper)

    def testReadonlyCapabilityIsTheOnlyNewPythonBindingSurface(self):
        self.source()
        bindings = self.tokens("src/core/bindings/CModuleWorld.cpp")
        self.assertEqual(
            1, bindings.count('.def("supportsSevenSunsMerchants",&CGuiHandler::supportsSevenSunsMerchants,')
        )
        self.assertNotRegex(bindings, r'\.def(?:_static)?\("(?:begin|advance|end|settle)SevenSunsMerchant')
        header = self.tokens("src/handler/CGuiHandler.h")
        self.assertIn("boolsupportsSevenSunsMerchants()const;", header)
        dispatch = self.tokens("src/handler/CGuiHandler.cpp")
        for operation in (
            "beginSevenSunsMerchant",
            "advanceSevenSunsMerchant",
            "endSevenSunsMerchant",
            "settleSevenSunsMerchants",
        ):
            self.assertEqual(1, dispatch.count('operation=="' + operation + '"'))
        self.assertIn("sevenSunsMerchant->requireCurrent()", dispatch)

    def testAttackAttemptBoundaryIsExplicitlyUnavailableWithoutDamageProxy(self):
        source = self.tokens()
        self.assertGreaterEqual(source.count('{"attackRevealSupported",false}'), 3)
        settle = source.split("CSevenSunsMerchantDialogue::settle(", 1)[1]
        for proxy in ("->hurt(", "CType::onDestroy", "getHp()<", "getHp()>"):
            self.assertNotIn(proxy, settle)

    def testDedicatedDefeatAuthorityIsPrivateReadOnlyAndRequiresExactCommittedOwners(self):
        header = self.tokens("src/handler/CSevenSunsMerchantDialogue.h")
        self.assertGreater(header.index("staticboolisSettledReplacement("), header.index("private:"))
        self.assertIn("friendclassCFightHandler;", header)
        source = self.tokens().split("::isSettledReplacement(", 1)[1].split("::readInteger(", 1)[0]
        for required in (
            'map->getMapName()!="baldursGate"',
            'actor->getTypeId()!="citySevenSunsRevealedDoppss"',
            "map->getObjectByName(identity->name)==actor",
            "oldActor&&oldActor!=actor",
            "value.phase==State::Phase::Replaced",
            "value.replacement==actor",
            "value.check();",
        ):
            self.assertIn(required, source)
        for mutation in ("writeRow(", "publish(", "tryBeginUnsafeOperation(", "addExp(", "addExpScaled(", ".claim("):
            self.assertNotIn(mutation, source)

    def testBeginAndSettlementRevisionCapacityPreflightPrecedesMutation(self):
        source = self.tokens()
        begin = source.split("CSevenSunsMerchantDialogue::begin(", 1)[1].split("::requireCurrent()", 1)[0]
        self.assertLess(begin.index('returnrefuse("revisionLimit"'), begin.index("value->count.write(n+1"))
        settle = source.split("CSevenSunsMerchantDialogue::settle(", 1)[1]
        self.assertLess(
            settle.index('integer(value->row.at("revision"))>=999999'), settle.index("MerchantStock::prepare(")
        )


if __name__ == "__main__":
    unittest.main()
