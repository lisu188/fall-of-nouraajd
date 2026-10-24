# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable bounded actual custody patrol methods; no native authority claim."""

from copy import deepcopy
import json
import unittest

from tests import test_baldurs_gate_custody_source as model


def fixture(values=None):
    m = model.Fixture()
    cls = m.classes["BaldursGateCustody"]
    method = cls.updatePatrols
    cls.updatePatrols = lambda _: None
    try:
        m.installCustody()
    finally:
        cls.updatePatrols = method
    m.created.clear()
    m.events = []
    m.world.setStringProperty("plugin_cityCustodyGlobals", json.dumps(values or {}))
    m.player.items.append(object())
    m.constructor_callback = None

    def staged(name):
        m.created.append(name)
        m.events.append(("construct", name, m.owner.globalValue("Capture800", "GLOBAL")))
        obj = model.Creature() if name in m.catalog else model.NativeObject()
        obj.game, obj.kind = m.game, name
        obj.properties.update(m.catalog.get(name, {}))
        # Real CGame.createObject creates a game-attached object; CMap.addObject registers it later.
        obj.setStringProperty("name", name)
        if m.constructor_callback:
            m.constructor_callback(name, obj)
        return obj

    m.game.createObject = staged
    return m


def registered(m, area="AR0800"):
    return [name for name in m.data["patrols"][area]["actors"] if m.world.getObjectByName(name)]


def updateData(m, change):
    data = deepcopy(m.data)
    change(data)
    m.owner.setStringProperty("custodyDefinitions", json.dumps(data))


class BaldursGateCustodyPatrolSourceTest(unittest.TestCase):
    def assertOwnershipFailure(self, callback):
        try:
            callback()
        except Exception as error:
            self.assertIsInstance(error, ValueError)
            self.assertIn("ownership changed", str(error))
        else:
            self.fail("Patrol mutation continued after ownership changed")

    def testProjectionRetainsEveryAuditedAssignedValue(self):
        m = fixture()
        for area, source in model.boundedFixture()["patrols"].items():
            self.assertEqual(source["oneShotValue"], m.data["patrols"][area].get("oneShotValue"))
            self.assertEqual(source["conditions"], m.data["patrols"][area]["conditions"])

    def testAssignmentPrecedesBothConstructorsAndRepeatedTurnsDoNotRespawn(self):
        m = fixture()
        m.owner.updatePatrols()
        self.assertEqual(1, m.owner.globalValue("Capture800", "GLOBAL"))
        self.assertEqual(m.data["patrols"]["AR0800"]["actors"], registered(m))
        self.assertEqual([1, 1], [event[2] for event in m.events])
        before = tuple(m.created)
        for _ in range(16):
            m.owner.updatePatrols()
        self.assertEqual(before, tuple(m.created))
        self.assertEqual(2, len(before))

    def testPresetMarkerWithoutRetainedPatrolPreventsRespawn(self):
        m = fixture({"GLOBAL:Capture800": 1})
        m.owner.updatePatrols()
        self.assertEqual([], registered(m))
        self.assertEqual([], m.created)
        self.assertEqual(1, m.owner.globalValue("Capture800", "GLOBAL"))

    def testPhaseAndAreaMustMatchAuditedSpawnConditions(self):
        for phase, area, expected in ((6, "AR0800", 0), (7, "AR0800", 2), (8, "AR0800", 0), (7, "AR9999", 0)):
            with self.subTest(phase=phase, area=area):
                m = fixture()
                m.world.setNumericProperty("plugin_cityPhase", phase)
                m.world.setStringProperty("activeSimulationRegion", area)
                m.owner.updatePatrols()
                self.assertEqual(expected, len(m.created))
                self.assertEqual(int(expected == 2), m.owner.globalValue("Capture800", "GLOBAL"))

    def testDukeThanksSuppressesSpawnAndRetiresExistingWithoutDeath(self):
        m = fixture({"GLOBAL:DukeThanks": 1})
        m.owner.updatePatrols()
        self.assertEqual([], m.created)
        m = fixture()
        m.owner.updatePatrols()
        actors = [m.world.getObjectByName(name) for name in registered(m)]
        m.owner.setGlobal("DukeThanks", "GLOBAL", 1)
        m.world.setNumericProperty("plugin_cityPhase", 8)
        m.owner.updatePatrols()
        self.assertEqual([], registered(m))
        self.assertTrue(all(actor.isAlive() for actor in actors))
        self.assertEqual(0, m.world.getNumericProperty("plugin_cityGuardKills"))

    def testSourceIntegerConditionsDoNotUseTruthyDukeOrCapturedValues(self):
        m = fixture({"GLOBAL:DukeThanks": 2})
        m.owner.updatePatrols()
        self.assertEqual([], m.created)
        for captured, hostile in ((0, False), (1, True), (2, False)):
            m = fixture({"GLOBAL:Captured": captured})
            m.owner.updatePatrols()
            actors = [m.world.getObjectByName(name) for name in registered(m)]
            self.assertEqual(2, len(actors))
            self.assertEqual(
                [hostile, hostile], [actor.getStringProperty("affiliation") == "cityWatch" for actor in actors]
            )

    def testNativePalaceClearedBridgeStillRetiresWithoutLootOrReward(self):
        m = fixture()
        before = m.player.getItems(), m.player.getNumericProperty("gold"), m.player.getNumericProperty("exp")
        m.owner.updatePatrols()
        m.world.setBoolProperty("plugin_cityFlag_palaceCleared", True)
        m.owner.updatePatrols()
        self.assertEqual([], registered(m))
        self.assertEqual(
            before, (m.player.getItems(), m.player.getNumericProperty("gold"), m.player.getNumericProperty("exp"))
        )
        self.assertEqual(0, m.world.getNumericProperty("plugin_cityGuardKills"))

    def testSourceMarkerPersistsWhenEitherConstructorThrowsAndDoesNotReplay(self):
        for failed_index in (1, 2):
            with self.subTest(failed_index=failed_index):
                m = fixture()
                original = RuntimeError("native constructor failed")

                def fail(_name, _actor):
                    if len(m.created) == failed_index:
                        raise original

                m.constructor_callback = fail
                with self.assertRaises(RuntimeError) as raised:
                    m.owner.updatePatrols()
                self.assertIs(original, raised.exception)
                self.assertEqual(1, m.owner.globalValue("Capture800", "GLOBAL"))
                self.assertEqual(failed_index - 1, len(registered(m)))
                before = tuple(m.created)
                m.constructor_callback = None
                m.owner.updatePatrols()
                self.assertEqual(before, tuple(m.created))

    def testConstructorReentrySeesConsumedMarkerAndConstructsOnlyTwo(self):
        m = fixture()
        entered = False

        def reenter(*_):
            nonlocal entered
            if not entered:
                entered = True
                m.owner.updatePatrols()

        m.constructor_callback = reenter
        try:
            m.owner.updatePatrols()
        except Exception as error:
            self.fail("Constructor reentry must not duplicate or replace an admitted patrol: " + str(error))
        self.assertEqual(2, len(m.created))
        self.assertEqual(2, len(registered(m)))

    def testConstructorMapReplacementCannotAttachToReplacement(self):
        m = fixture()
        old_map = m.world
        replacement = model.CompactMap()
        replacement.game = m.game
        m.constructor_callback = lambda *_: setattr(m, "world", replacement)
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(1, len(m.created))
        self.assertFalse(any("cityCustodyPatrol" in name for name in replacement.objects))
        self.assertFalse(any("cityCustodyPatrol" in name for name in old_map.objects))
        self.assertEqual(0, replacement.getNumericProperty("plugin_cityTicks"))

    def testSameMapGenerationChangeStopsBeforeActorRegistration(self):
        m = fixture()
        m.constructor_callback = lambda *_: setattr(m.context, "generation", m.context.generation + 1)
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual([], registered(m))
        self.assertEqual(1, len(m.created))

    def testMarkerSetterRebindingStopsBeforeConstructors(self):
        m = fixture()
        old_map = m.world
        setter = old_map.setStringProperty
        replacement = model.CompactMap()
        replacement.game = m.game

        def setAndReplace(key, value):
            setter(key, value)
            if key == "plugin_cityCustodyGlobals":
                m.world = replacement

        old_map.setStringProperty = setAndReplace
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual([], m.created)
        self.assertEqual({}, replacement.properties)
        self.assertIn('"GLOBAL:Capture800":1', old_map.getStringProperty("plugin_cityCustodyGlobals"))

    def testUnsupportedSourceConditionFailsBeforeAnyMutation(self):
        for mutation in (
            lambda row: row.update(signature="GlobalGT(S:Name*,S:Area*,I:Value*)"),
            lambda row: row.update(opcode=999),
            lambda row: row.update(negated=True),
            lambda row: row.update(strings=["AR0800Capture800", ""]),
            lambda row: row.update(integerFields=[0, 99, 0, 0]),
            lambda row: row.update(integerFields=[False, 0, 0, 0]),
        ):
            with self.subTest(mutation=mutation):
                m = fixture()
                updateData(m, lambda data: mutation(data["patrols"]["AR0800"]["conditions"][1]))
                before = deepcopy(m.world.properties)
                with self.assertRaisesRegex(ValueError, "Unsupported custody patrol source condition"):
                    m.owner.updatePatrols()
                self.assertEqual(before, m.world.properties)
                self.assertEqual([], m.created)

    def testFreshCoordinatorRetainsSerializedMarkerAndActorsWithoutNewItems(self):
        m = fixture()
        before = m.player.getItems()
        m.owner.updatePatrols()
        names = registered(m)
        actor_objects = [m.world.getObjectByName(name) for name in names]
        saved_globals = m.world.getStringProperty("plugin_cityCustodyGlobals")
        saved_owner_properties = dict(m.owner.properties)
        m.owner = m.object(m.classes["BaldursGateCustody"], "cityCustody")
        m.owner.properties.update(saved_owner_properties)
        m.world.setStringProperty("plugin_cityCustodyGlobals", saved_globals)
        m.owner.updatePatrols()
        self.assertEqual(2, len(m.created))
        self.assertEqual(actor_objects, [m.world.getObjectByName(name) for name in names])
        self.assertEqual(before, m.player.getItems())

    def testInitializationRebindKeepsReplacementUntouchedAndDoesNotConstructSecond(self):
        m = fixture()
        old_map = m.world
        replacement = model.CompactMap()
        replacement.game = m.game
        m.clock.initializeActor = lambda *_: setattr(m, "world", replacement)
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(1, len(m.created))
        self.assertEqual({}, replacement.objects)
        self.assertEqual(1, len([name for name in old_map.objects if "cityCustodyPatrol" in name]))

    def testMissingOrForeignClockRejectsBeforeAnySourceMutation(self):
        for mode in ("missing", "foreign", "wrong-type"):
            with self.subTest(mode=mode):
                m = fixture()
                if mode == "missing":
                    m.world.objects.pop("cityClock")
                elif mode == "foreign":
                    m.clock.game = object()
                else:
                    m.world.objects["cityClock"] = m.object(model.NativeObject, "cityClock")
                before = deepcopy(m.world.properties)
                self.assertOwnershipFailure(m.owner.updatePatrols)
                self.assertEqual(before, m.world.properties)
                self.assertEqual([], m.created)

    def testAdmissionUsesRegisteredLiveNativePlayerWithoutLazyPlayerGetter(self):
        for mode in ("healthy", "missing", "dead", "foreign", "non-player"):
            with self.subTest(mode=mode):
                m = fixture()
                calls = []

                def forbidden():
                    calls.append("getPlayer")
                    raise AssertionError("Patrol admission must not lazily repair player/controllers/triggers")

                m.world.getPlayer = forbidden
                if mode == "missing":
                    m.world.objects.pop("player")
                elif mode == "dead":
                    m.player.hp = 0
                elif mode == "foreign":
                    m.player.game = object()
                elif mode == "non-player":
                    m.world.objects["player"] = m.object(model.Creature, "player")
                before = deepcopy(m.world.properties)
                if mode == "healthy":
                    m.owner.updatePatrols()
                    self.assertEqual(2, len(registered(m)))
                else:
                    self.assertOwnershipFailure(m.owner.updatePatrols)
                    self.assertEqual(before, m.world.properties)
                    self.assertEqual([], m.created)
                self.assertEqual([], calls)

    def testRetainedActorRequiresExactCreatureSourceAreaAndGameBinding(self):
        for mode in ("non-creature", "wrong-source", "wrong-area", "foreign-game"):
            with self.subTest(mode=mode):
                m = fixture({"GLOBAL:Captured": 1, "GLOBAL:Capture800": 1})
                name = m.data["patrols"]["AR0800"]["actors"][0]
                actor = m.object(model.NativeObject if mode == "non-creature" else model.Creature, name)
                actor.properties.update(m.catalog[name])
                if mode == "wrong-source":
                    actor.setStringProperty("sourceCreature", "NEB")
                elif mode == "wrong-area":
                    actor.setStringProperty("sourceArea", "AR0607")
                elif mode == "foreign-game":
                    actor.game = object()
                before = dict(actor.properties)
                try:
                    m.owner.updatePatrols()
                except Exception as error:
                    self.assertIsInstance(error, ValueError)
                    self.assertIn("custody patrol", str(error).casefold())
                else:
                    self.fail("A non-source or foreign actor was adopted as an audited patrol")
                self.assertEqual(before, actor.properties)
                self.assertEqual([], m.created)

    def testInitializationReplacingSameNamePatrolRejectsBeforeSecondConstructor(self):
        m = fixture()

        def replace(actor):
            other = model.Creature()
            other.game = m.game
            other.properties.update(actor.properties)
            m.world.objects[actor.getName()] = other

        m.clock.initializeActor = replace
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(1, len(m.created))

    def testHearingTailPassesTheRetainedPatrolScopeToRelocation(self):
        m = fixture({"GLOBAL:Capture800": 1})
        m.world.setBoolProperty("plugin_cityFlag_custodyHearing", True)
        capture, relocate, bindings, forwarded = m.owner.captureCustodyBinding, m.owner.relocateParty, [], []

        def retain(*args, **kwargs):
            result = capture(*args, **kwargs)
            bindings.append(result)
            return result

        def receive(stage, binding=None):
            forwarded.append(binding)
            return relocate(stage, binding=binding)

        m.owner.captureCustodyBinding = retain
        m.owner.relocateParty = receive
        m.owner.updatePatrols()
        self.assertEqual(1, len(bindings))
        self.assertEqual(1, len(forwarded))
        self.assertIs(bindings[0], forwarded[0])
        self.assertEqual(m.data["hearing"]["partyPositions"][0], m.player.properties["coords"])

    def assertHearingCaptureChangeStopsRelocation(self, fault):
        m = fixture({"GLOBAL:Capture800": 1})
        m.world.setBoolProperty("plugin_cityFlag_custodyHearing", True)
        capture, original_player, observed = m.owner.captureCustodyBinding, m.player, []
        before = deepcopy(m.world.properties)
        original_position = deepcopy(m.player.properties.get("coords", [0, 0, 0]))

        def changed(*args, **kwargs):
            if fault == "context":
                m.context = model.CompactContext()
            elif fault == "player":
                replacement = m.object(model.Player, "player")
                replacement.properties.update(original_player.properties)
                m.world.player = replacement
                observed.append(replacement)
            elif fault == "clock":
                replacement = m.object(m.classes["BaldursGateClock"], "cityClock")
                replacement.properties.update(m.clock.properties)
            else:
                data = deepcopy(m.data)
                data["hearing"]["partyPositions"][0] = [999, 998, 1]
                m.owner.setStringProperty("custodyDefinitions", json.dumps(data))
            return capture(*args, **kwargs)

        m.owner.captureCustodyBinding = changed
        with self.assertRaises((ValueError, RuntimeError)):
            m.owner.updatePatrols()
        for actor in [original_player, *observed]:
            self.assertEqual(original_position, actor.properties.get("coords", [0, 0, 0]))
        self.assertEqual(before, m.world.properties)
        self.assertEqual([], m.created)

    def testHearingTailRejectsContextChangedDuringCaptureBeforeMoving(self):
        self.assertHearingCaptureChangeStopsRelocation("context")

    def testHearingTailRejectsPlayerChangedDuringCaptureBeforeMoving(self):
        self.assertHearingCaptureChangeStopsRelocation("player")

    def testHearingTailRejectsClockChangedDuringCaptureBeforeMoving(self):
        self.assertHearingCaptureChangeStopsRelocation("clock")

    def testHearingTailRejectsChangedSourceTargetsDuringCaptureBeforeMoving(self):
        self.assertHearingCaptureChangeStopsRelocation("metadata")

    def testPortablePrisonPinAllowsLineEndingsWithoutChangingEvidenceOrCap(self):
        from unittest import mock

        raw = model.FIXTURE.read_bytes()
        canonical = raw.replace(b"\r\n", b"\n")
        expected = json.loads(canonical)
        for payload in (canonical, canonical.replace(b"\n", b"\r\n")):
            with self.subTest(lineEnding="CRLF" if b"\r\n" in payload else "LF"):
                with mock.patch.object(model.Path, "read_bytes", return_value=payload):
                    error, actual = None, None
                    try:
                        actual = model.boundedFixture()
                    except Exception as caught:
                        error = caught
                    self.assertIsNone(error, "The same pinned source facts must survive ordinary checkout line endings")
                    self.assertEqual(expected, actual)
        for payload in (canonical.replace(b"Capture800", b"Capture801", 1), b" " * (192 * 1024 + 1)):
            with self.subTest(rejectedBytes=len(payload)):
                self.assertNotEqual(canonical, payload)
                with mock.patch.object(model.Path, "read_bytes", return_value=payload):
                    with self.assertRaises(ValueError):
                        model.boundedFixture()

    def patrolRawAwayBack(self, m):
        original, context, generation = m.world, m.context, m.context.generation
        replacement = model.CompactMap()
        replacement.game = m.game
        m.game.setMap(replacement)
        m.game.setMap(original)
        self.assertIs(original, m.world)
        self.assertIs(context, m.context)
        self.assertEqual(generation, m.context.generation)

    def testPatrolEpochPrecedesFirstMapObservation(self):
        m = fixture()
        original, reads = m.game.getMap, []

        def reflected():
            result = original()
            if not reads:
                reads.append(result)
                self.patrolRawAwayBack(m)
            return result

        m.game.getMap = reflected
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(0, m.owner.globalValue("Capture800", "GLOBAL"))
        self.assertEqual([], m.created)

    def testPatrolEpochRejectsMetadataGetterAwayBackBeforeSourceMutation(self):
        m = fixture()
        original, callbacks = m.owner.getStringProperty, []

        def reflected(key):
            result = original(key)
            if key == "custodyDefinitions" and not callbacks:
                callbacks.append(key)
                self.patrolRawAwayBack(m)
            return result

        m.owner.getStringProperty = reflected
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(["custodyDefinitions"], callbacks)
        self.assertEqual(0, m.owner.globalValue("Capture800", "GLOBAL"))
        self.assertEqual([], m.created)

    def testPatrolEpochRejectsMarkerSetterAwayBackWithoutReplayingSourceAssignment(self):
        m = fixture()
        original, writes = m.world.setStringProperty, []

        def reflected(key, value):
            result = original(key, value)
            if key == "plugin_cityCustodyGlobals" and not writes:
                writes.append(value)
                self.patrolRawAwayBack(m)
            return result

        m.world.setStringProperty = reflected
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(1, len(writes))
        self.assertEqual(1, m.owner.globalValue("Capture800", "GLOBAL"))
        self.assertEqual([], m.created)
        m.owner.updatePatrols()
        self.assertEqual([], m.created)

    def testPatrolEpochRejectsConstructorAwayBackBeforeRegistrationOrSecondActor(self):
        m = fixture()
        m.constructor_callback = lambda _name, _actor: self.patrolRawAwayBack(m)
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(1, len(m.created))
        self.assertEqual([], registered(m))
        self.assertEqual(1, m.owner.globalValue("Capture800", "GLOBAL"))

    def testPatrolEpochRejectsFreshHearingBindingAfterPriorPatrolScopeExpired(self):
        m = fixture({"GLOBAL:Capture800": 1})
        m.world.setBoolProperty("plugin_cityFlag_custodyHearing", True)
        original = m.owner.captureCustodyBinding
        position = deepcopy(m.player.properties.get("coords", [0, 0, 0]))

        def rebound(*args, **kwargs):
            self.patrolRawAwayBack(m)
            return original(*args, **kwargs)

        m.owner.captureCustodyBinding = rebound
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(position, m.player.properties.get("coords", [0, 0, 0]))
        self.assertEqual([], m.created)

    def testPatrolEpochUsesUnboundNativeQueryDespiteInstanceOverride(self):
        m = fixture()
        captured = model.CompactGame.getMapBindingEpoch(m.game)
        m.game.getMapBindingEpoch = lambda: captured
        original, callbacks = m.owner.getStringProperty, []

        def reflected(key):
            result = original(key)
            if key == "custodyDefinitions" and not callbacks:
                callbacks.append(key)
                self.patrolRawAwayBack(m)
            return result

        m.owner.getStringProperty = reflected
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(0, m.owner.globalValue("Capture800", "GLOBAL"))
        self.assertEqual([], m.created)

    def testPatrolEpochSamePointerAndFreshInvocationAfterTransitionRemainEligible(self):
        for prior_transition in (False, True):
            with self.subTest(prior_transition=prior_transition):
                m = fixture()
                if prior_transition:
                    self.patrolRawAwayBack(m)
                original, callbacks = m.owner.getStringProperty, []
                epoch = model.CompactGame.getMapBindingEpoch(m.game)

                def same_pointer(key):
                    result = original(key)
                    if key == "custodyDefinitions" and not callbacks:
                        callbacks.append(key)
                        m.game.setMap(m.world)
                    return result

                m.owner.getStringProperty = same_pointer
                m.owner.updatePatrols()
                self.assertEqual(epoch, model.CompactGame.getMapBindingEpoch(m.game))
                self.assertEqual(2, len(m.created))
                self.assertEqual(1, m.owner.globalValue("Capture800", "GLOBAL"))

    def testAssignedPlayerPatrolRejectsNullAndMismatchedCacheBeforeSourceMarker(self):
        for mismatch in (False, True):
            with self.subTest(mismatch=mismatch):
                m = fixture()
                m.world.player = m.object(model.Player, "alternateAssignedPlayer") if mismatch else None
                self.assertOwnershipFailure(m.owner.updatePatrols)
                self.assertEqual(0, m.stored("plugin_cityCustodyGlobals", {}).get("GLOBAL:Capture800", 0))
                self.assertEqual([], m.created)
                self.assertIs(m.player, m.world.getObjectByName("player"))

    def testAssignedPlayerPatrolRejectsMetadataGetterCacheChangeBeforeSourceMarker(self):
        m = fixture()
        original, callbacks = m.owner.getStringProperty, []

        def reflected(key):
            value = original(key)
            if key == "custodyDefinitions" and not callbacks:
                callbacks.append(key)
                m.world.player = None
            return value

        m.owner.getStringProperty = reflected
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(["custodyDefinitions"], callbacks)
        self.assertEqual(0, m.stored("plugin_cityCustodyGlobals", {}).get("GLOBAL:Capture800", 0))
        self.assertEqual([], m.created)

    def testAssignedPlayerPatrolRechecksCacheAfterLatePlayerGetter(self):
        m = fixture()
        original, callbacks = m.player.isAlive, []
        data, metadata = m.owner.data, []

        def reflected():
            value = original()
            if not callbacks:
                callbacks.append("alive")
                m.world.player = None
            return value

        m.player.isAlive = reflected

        def observed_data():
            metadata.append("custodyDefinitions")
            return data()

        m.owner.data = observed_data
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(["alive"], callbacks)
        self.assertEqual([], metadata)
        self.assertEqual(0, m.stored("plugin_cityCustodyGlobals", {}).get("GLOBAL:Capture800", 0))
        self.assertEqual([], m.created)

    def testAssignedPlayerPatrolMarkerSetterCacheChangeStopsCreationWithoutReplayingAssignment(self):
        m = fixture()
        original, writes = m.world.setStringProperty, []

        def reflected(key, value):
            result = original(key, value)
            if key == "plugin_cityCustodyGlobals" and not writes:
                writes.append(value)
                m.world.player = None
            return result

        m.world.setStringProperty = reflected
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(1, len(writes))
        self.assertEqual(1, m.stored("plugin_cityCustodyGlobals", {}).get("GLOBAL:Capture800", 0))
        self.assertEqual([], m.created)
        m.world.player = m.player
        m.owner.updatePatrols()
        self.assertEqual([], m.created)

    def testAssignedPlayerPatrolConstructorCacheChangeStopsRegistrationAndSecondActor(self):
        m = fixture()
        m.constructor_callback = lambda _name, _actor: setattr(m.world, "player", None)
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(1, len(m.created))
        self.assertEqual([], registered(m))
        self.assertEqual(1, m.stored("plugin_cityCustodyGlobals", {}).get("GLOBAL:Capture800", 0))

    def testAssignedPlayerPatrolHearingBindingCacheChangeCannotRelocateParty(self):
        m = fixture({"GLOBAL:Capture800": 1})
        m.world.setBoolProperty("plugin_cityFlag_custodyHearing", True)
        original = m.owner.captureCustodyBinding
        position = deepcopy(m.player.properties.get("coords", [0, 0, 0]))

        def reflected(*args, **kwargs):
            binding = original(*args, **kwargs)
            m.world.player = None
            return binding

        m.owner.captureCustodyBinding = reflected
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(position, m.player.properties.get("coords", [0, 0, 0]))
        self.assertEqual([], m.created)

    def testAssignedPlayerPatrolUsesUnboundQueryDespiteInstanceSpoof(self):
        m = fixture()
        m.world.getAssignedPlayer = lambda: m.player
        original, callbacks = m.owner.getStringProperty, []

        def reflected(key):
            value = original(key)
            if key == "custodyDefinitions" and not callbacks:
                callbacks.append(key)
                m.world.player = None
            return value

        m.owner.getStringProperty = reflected
        self.assertOwnershipFailure(m.owner.updatePatrols)
        self.assertEqual(0, m.stored("plugin_cityCustodyGlobals", {}).get("GLOBAL:Capture800", 0))
        self.assertEqual([], m.created)

    def testAssignedPlayerPatrolStableCachePreservesOneShotAndNeverUsesLazyRecovery(self):
        m = fixture()
        calls = []
        m.world.getPlayer = lambda: calls.append("getPlayer")
        m.owner.updatePatrols()
        first = tuple(m.created)
        self.assertEqual(2, len(first))
        self.assertEqual(1, m.stored("plugin_cityCustodyGlobals", {}).get("GLOBAL:Capture800", 0))
        m.owner.updatePatrols()
        self.assertEqual(first, tuple(m.created))
        self.assertIs(m.player, m.world.player)
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
