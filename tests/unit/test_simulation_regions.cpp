/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/

#include "core/CAsync.h"
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CSerialization.h"
#include "core/CStats.h"
#include "core/CTypes.h"
#include "handler/CObjectHandler.h"
#include "object/CBuilding.h"
#include "object/CCreature.h"
#include "object/CMapObject.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "test_harness.h"

#include <algorithm>
#include <functional>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

namespace {
class RegionController : public CController {
  public:
    vstd::task<Coords> controlAsync(std::shared_ptr<CCreature> actor) override {
        ++controls;
        if (onPlan) {
            onPlan();
        }
        co_return actor->getCoords() + step;
    }

    void interrupt(std::shared_ptr<CCreature>) override { ++interrupts; }
    void onStepCommitted(std::shared_ptr<CCreature>, const Coords &) override { ++commits; }
    void onTurnEnded(std::shared_ptr<CCreature>) override {
        ++turnEnds;
        if (onEnd) {
            onEnd();
        }
    }

    Coords step = ZERO;
    std::function<void()> onPlan;
    std::function<void()> onEnd;
    int controls = 0;
    int interrupts = 0;
    int commits = 0;
    int turnEnds = 0;
};

class RegionActor : public CCreature {
  public:
    void onTurn(std::shared_ptr<CGameEvent>) override {
        ++callbacks;
        if (onTick) {
            onTick();
        }
    }

    void onLeave(std::shared_ptr<CGameEvent>) override { ++departures; }

    std::function<void()> onTick;
    int callbacks = 0;
    int departures = 0;
};

class RegionPortal : public CBuilding {
  public:
    void onEnter(std::shared_ptr<CGameEvent>) override {
        ++entries;
        getMap()->setStringProperty("activeSimulationRegion", "south");
    }

    int entries = 0;
};

class RegionPropertyObject : public CMapObject {
    V_META(RegionPropertyObject, CMapObject,
           V_PROPERTY(RegionPropertyObject, std::string, simulationRegion, getSimulationRegion, setSimulationRegion))

  public:
    std::string getSimulationRegion() {
        ++regionReads;
        return readRegion ? readRegion() : region;
    }
    void setSimulationRegion(std::string value) {
        region = std::move(value);
        recordDirectPropertyChanged("simulationRegion");
        if (afterSet) {
            afterSet();
        }
    }

    void onTurn(std::shared_ptr<CGameEvent>) override { ++callbacks; }

    std::string region = "south";
    std::function<void()> afterSet;
    std::function<std::string()> readRegion;
    int callbacks = 0;
    int regionReads = 0;
};

struct RegionFixture {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    std::shared_ptr<CMap> map = std::make_shared<CMap>();
    std::vector<std::shared_ptr<RegionActor>> actors;

    RegionFixture() {
        game->setMap(map);
        map->setGame(game);
        game->getObjectHandler()->registerType("CPlayerController",
                                               [] { return std::make_shared<CPlayerController>(); });
        game->getObjectHandler()->registerType("CPlayerFightController",
                                               [] { return std::make_shared<CPlayerFightController>(); });
    }

    std::shared_ptr<RegionActor> actor(const std::string &name, const std::string &region, Coords coords = ZERO) {
        auto actor = std::make_shared<RegionActor>();
        actor->setGame(game);
        actor->setName(name);
        actor->setNpc(true);
        actor->getBaseStats()->setMainStat("stamina");
        actor->getBaseStats()->setStamina(10);
        actor->setLevel(1);
        actor->setHp(70);
        actor->relocateWithoutMoveHooks(coords);
        actor->setStringProperty("simulationRegion", region);
        actor->setController(std::make_shared<RegionController>());
        map->addObject(actor);
        actors.push_back(actor);
        return actor;
    }

    void floor(Coords coords) {
        auto tile = std::make_shared<CTile>();
        tile->setGame(game);
        tile->setCanStep(true);
        map->addTile(tile, coords.x, coords.y, coords.z);
    }

    std::shared_ptr<RegionController> controller(const std::shared_ptr<CCreature> &actor) {
        return std::dynamic_pointer_cast<RegionController>(actor->getController());
    }

    ~RegionFixture() { game->getContext()->shutdown(); }
};

std::vector<std::shared_ptr<RegionActor>> snapshotOrder(RegionFixture &fixture) {
    std::vector<std::shared_ptr<RegionActor>> result;
    fixture.map->forObjects([&](auto object) {
        if (auto actor = std::dynamic_pointer_cast<RegionActor>(object)) {
            result.push_back(actor);
        }
    });
    return result;
}

void testRegionFixtureSetupDoesNotRunMovementHooks() {
    RegionFixture fixture;
    performance_guard::resetMapCoordinateLookupProbe();
    auto first = fixture.actor("firstResident", "north");
    auto second = fixture.actor("secondResident", "north");
    const auto setupProbes = performance_guard::mapCoordinateLookupProbeCount();
    performance_guard::disableMapCoordinateLookupProbe();
    expect_true(first->departures == 0 && second->departures == 0 && setupProbes == 0,
                "initial resident placement must not run leave/contact hooks against previously inserted residents");
}

void testDefaultAndOptInRegionTurns() {
    RegionFixture fixture;
    auto north = fixture.actor("north", "north");
    auto south = fixture.actor("south", "south");
    auto global = fixture.actor("global", "");
    auto follower = fixture.actor("follower", "south");
    follower->setBoolProperty("alwaysSimulate", true);
    fixture.map->move();
    expect_true(north->callbacks == 1 && south->callbacks == 1 && global->callbacks == 1 && follower->callbacks == 1,
                "an empty active region must preserve all legacy turn callbacks");
    fixture.map->setStringProperty("activeSimulationRegion", "north");
    fixture.map->move();
    expect_true(north->callbacks == 2 && south->callbacks == 1 && global->callbacks == 2 && follower->callbacks == 2,
                "only the active region, untagged coordinators and explicit followers receive turns");
    expect_true(fixture.controller(south)->controls == 1 && fixture.controller(south)->turnEnds == 1 &&
                    fixture.controller(north)->controls == 2 && fixture.controller(north)->turnEnds == 2,
                "dormant controllers must receive neither control nor turn-ended callbacks");
    fixture.map->setStringProperty("activeSimulationRegion", "south");
    fixture.map->move();
    expect_true(north->callbacks == 2 && south->callbacks == 2 && fixture.map->getObjects().size() == 4 &&
                    fixture.map->getTurn() == 3,
                "reactivation resumes the same objects and state on the next consumed turn");
    fixture.map->setActiveSimulationRegion("");
    fixture.map->move();
    expect_true(north->callbacks == 3 && south->callbacks == 3 && global->callbacks == 4 && follower->callbacks == 4,
                "clearing the active region must restore legacy simulation without rebuilding actors");
}

void testInactiveMovementAndPlayerExemption() {
    RegionFixture fixture;
    fixture.floor(ZERO);
    fixture.floor(EAST);
    auto sleeper = fixture.actor("sleeper", "south", Coords(0, 2, 0));
    fixture.floor(Coords(0, 2, 0));
    fixture.floor(Coords(1, 2, 0));
    fixture.controller(sleeper)->step = EAST;
    auto player = std::make_shared<CPlayer>();
    player->setGame(fixture.game);
    player->getBaseStats()->setMainStat("stamina");
    player->getBaseStats()->setStamina(10);
    player->setHp(70);
    fixture.map->setPlayer(player);
    player->setStringProperty("simulationRegion", "south");
    auto playerController = std::make_shared<RegionController>();
    playerController->step = EAST;
    player->setController(playerController);
    fixture.map->setActiveSimulationRegion("north");
    fixture.map->move();
    expect_true(player->getCoords() == EAST && playerController->controls == 1 && playerController->commits == 1,
                "the actual player must remain simulated despite an old or absent region tag");
    expect_true(sleeper->getCoords() == Coords(0, 2, 0) && fixture.controller(sleeper)->controls == 0,
                "inactive actors must retain their coordinates without running controller work");
}

void testRegionActivationDuringCallbacksConsumesOneTurnWithoutMixingRegions() {
    RegionFixture fixture;
    auto north = fixture.actor("north", "north");
    auto south = fixture.actor("south", "south");
    auto coordinator = fixture.actor("coordinator", "north");
    coordinator->setBoolProperty("alwaysSimulate", true);
    coordinator->onTick = [map = std::weak_ptr<CMap>(fixture.map)] {
        map.lock()->setStringProperty("activeSimulationRegion", "south");
    };
    fixture.map->setActiveSimulationRegion("north");
    fixture.map->move();
    expect_true(
        coordinator->callbacks == 1 && south->callbacks == 0 && fixture.controller(north)->controls == 0 &&
            fixture.controller(south)->controls == 0 && fixture.map->getTurn() == 1 && !fixture.map->isMoving(),
        "a region change during onTurn must consume one turn without planning either stale or newly active actors");
    fixture.map->move();
    expect_true(south->callbacks == 1 && fixture.controller(south)->controls == 1 && fixture.map->getTurn() == 2,
                "the next complete turn must simulate the newly active region");
}

void testRegionRoundTripInvalidatesPendingControllerPlans() {
    RegionFixture fixture;
    fixture.floor(ZERO);
    fixture.floor(EAST);
    auto actor = fixture.actor("roundTrip", "north");
    auto controller = fixture.controller(actor);
    controller->step = EAST;
    controller->onPlan = [map = std::weak_ptr<CMap>(fixture.map)] {
        map.lock()->setActiveSimulationRegion("south");
        map.lock()->setActiveSimulationRegion("north");
    };
    fixture.map->setActiveSimulationRegion("north");
    fixture.map->move();
    expect_true(actor->getCoords() == ZERO && controller->controls == 1 && controller->interrupts == 1 &&
                    controller->commits == 0 && controller->turnEnds == 0 && fixture.map->getTurn() == 1,
                "changing away and back must invalidate a pending plan even when the final region string matches");
    controller->onPlan = {};
    fixture.map->move();
    expect_true(actor->getCoords() == EAST && controller->commits == 1 && fixture.map->getTurn() == 2,
                "the interrupted actor must be able to plan and move normally on the following turn");
}

void testPortalRegionChangeRetainsTheFirstCommittedMoveAndDropsRemainingPlans() {
    RegionFixture fixture;
    std::vector<std::shared_ptr<RegionPortal>> portals;
    for (int y : {0, 2}) {
        fixture.floor(Coords(0, y, 0));
        fixture.floor(Coords(1, y, 0));
        auto portal = std::make_shared<RegionPortal>();
        portal->setGame(fixture.game);
        portal->setName("regionPortal" + std::to_string(y));
        portal->setCoords(Coords(1, y, 0));
        portal->setStringProperty("simulationRegion", "north");
        fixture.map->addObject(portal);
        portals.push_back(portal);
    }
    auto first = fixture.actor("first", "north", ZERO);
    auto second = fixture.actor("second", "north", Coords(0, 2, 0));
    auto sleeping = fixture.actor("sleeping", "south", Coords(0, 4, 0));
    fixture.controller(first)->step = fixture.controller(second)->step = EAST;
    fixture.map->setActiveSimulationRegion("north");
    fixture.map->move();
    const int moved = (first->getCoords() == EAST ? 1 : 0) + (second->getCoords() == Coords(1, 2, 0) ? 1 : 0);
    expect_true(moved == 1 && portals[0]->entries + portals[1]->entries == 1 && fixture.map->getTurn() == 1 &&
                    fixture.map->getActiveSimulationRegion() == "south" && !fixture.map->isMoving(),
                "onEnter must retain the committed portal step and consume exactly one same-map turn");
    expect_true(fixture.controller(first)->interrupts >= 1 && fixture.controller(second)->interrupts >= 1 &&
                    fixture.controller(sleeping)->controls == 0 && sleeping->callbacks == 0,
                "remaining stale plans must be interrupted without admitting newly active actors during that turn");
}

void testSimulationPropertiesRoundTripWithoutChangingLegacyDefaults() {
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CMapObject, CGameObject>();
    CTypes::register_type<CMap, CGameObject>();
    RegionFixture fixture;
    for (const auto &[name, builder] : *CTypes::builders()) {
        fixture.game->getObjectHandler()->registerType(name, builder);
    }
    auto object = std::make_shared<CMapObject>();
    object->setGame(fixture.game);
    object->setName("persistentResident");
    object->setStringProperty("simulationRegion", "interior:elvsongUpper");
    object->setBoolProperty("alwaysSimulate", true);
    object->setNumericProperty("plugin_cityConversationCount", 7);
    fixture.map->addObject(object);
    fixture.map->setActiveSimulationRegion("east");
    using ObjectJson = CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>;
    auto serialized = ObjectJson::serialize(fixture.map);
    CSerialization::StrictScope strict("simulation-region-roundtrip");
    auto restored = std::dynamic_pointer_cast<CMap>(ObjectJson::deserialize(fixture.game, serialized, strict));
    auto resident = restored ? restored->getObjectByName("persistentResident") : nullptr;
    expect_true(restored && restored->getActiveSimulationRegion() == "east" && resident &&
                    resident->getStringProperty("simulationRegion") == "interior:elvsongUpper" &&
                    resident->getBoolProperty("alwaysSimulate") &&
                    resident->getNumericProperty("plugin_cityConversationCount") == 7 &&
                    restored->isSimulationActive(resident),
                "the existing serializer must preserve region, global override and resident state together");
    (*serialized)["properties"].erase("activeSimulationRegion");
    CSerialization::StrictScope legacyStrict("simulation-region-legacy");
    auto legacy = std::dynamic_pointer_cast<CMap>(ObjectJson::deserialize(fixture.game, serialized, legacyStrict));
    expect_true(legacy && legacy->getActiveSimulationRegion().empty() &&
                    legacy->isSimulationActive(legacy->getObjectByName("persistentResident")),
                "old saves without an active region must retain the legacy all-objects behavior");
}

void testBatchedActivationPreservesTheUnvisitedSnapshotSuffix() {
    RegionFixture fixture;
    for (int index = 0; index < 4; ++index) {
        fixture.actor("changingResident" + std::to_string(index), "south");
    }
    auto order = snapshotOrder(fixture);
    order[1]->setStringProperty("simulationRegion", "north");
    order[3]->setStringProperty("simulationRegion", "north");
    fixture.map->setActiveSimulationRegion("north");
    fixture.map->move();
    order[1]->onTick = [&] {
        order[0]->setStringProperty("simulationRegion", "north");
        order[2]->setBoolProperty("alwaysSimulate", true);
        order[3]->setStringProperty("simulationRegion", "south");
    };
    {
        CGameObject::PropertyNotificationBatch earlierBatch(*order[0]);
        CGameObject::PropertyNotificationBatch laterBatch(*order[2]);
        CGameObject::PropertyNotificationBatch inactiveBatch(*order[3]);
        performance_guard::resetMapTurnSelectionProbe();
        fixture.map->move();
        const auto work = performance_guard::mapTurnSelectionProbeStats();
        performance_guard::disableMapTurnSelectionProbe();
        expect_true(order[0]->callbacks == 0 && order[1]->callbacks == 2 && order[2]->callbacks == 1 &&
                        order[3]->callbacks == 1 && work.fallbackVisits == 2,
                    "batched activation must revisit only the unvisited original suffix and honor later deactivation");
        expect_true(fixture.controller(order[0])->controls == 1 && fixture.controller(order[2])->controls == 1 &&
                        fixture.controller(order[3])->controls == 1 && fixture.controller(order[0])->turnEnds == 1 &&
                        fixture.controller(order[2])->turnEnds == 1,
                    "controller and end phases must see changed activity before batched notifications are delivered");
    }
    order[1]->onTick = {};
    fixture.map->move();
    expect_true(order[0]->callbacks == 1 && order[2]->callbacks == 2 && order[3]->callbacks == 1,
                "an earlier newly active object must receive its first turn on the following snapshot");
}

void testRemovedAndNewObjectsRetainTheirPhaseMembership() {
    RegionFixture fixture;
    for (int index = 0; index < 3; ++index) {
        fixture.actor("originalResident" + std::to_string(index), "north");
    }
    auto order = snapshotOrder(fixture);
    order[1]->setStringProperty("simulationRegion", "south");
    fixture.map->setActiveSimulationRegion("north");
    std::shared_ptr<RegionActor> added;
    order[0]->onTick = [&] {
        fixture.map->removeObject(order[1]);
        order[1]->setBoolProperty("alwaysSimulate", true);
        added = fixture.actor("newResident", "north");
    };
    fixture.map->move();
    expect_true(order[0]->callbacks == 1 && order[1]->callbacks == 1 && order[2]->callbacks == 1 && added &&
                    added->callbacks == 0 && !fixture.map->getObjectByName(order[1]->getName()),
                "onTurn must retain removed snapshot objects and exclude arrivals even after callback mutation");
    expect_true(fixture.controller(order[1])->controls == 0 && fixture.controller(order[1])->turnEnds == 0 &&
                    fixture.controller(added)->controls == 1 && fixture.controller(added)->turnEnds == 1,
                "later phases must refresh membership and exclude removed actors while admitting new actors");
}

void testRegistryReplacementRetainsTheOriginalTurnSnapshot() {
    RegionFixture fixture;
    auto replacement = fixture.actor("replacement", "north");
    fixture.map->removeObject(replacement);
    for (int index = 0; index < 3; ++index) {
        fixture.actor("replacedResident" + std::to_string(index), "north");
    }
    auto order = snapshotOrder(fixture);
    order[0]->onTick = [&] { fixture.map->setObjects({replacement}); };
    fixture.map->setActiveSimulationRegion("north");
    fixture.map->move();
    expect_true(order[0]->callbacks == 1 && order[1]->callbacks == 1 && order[2]->callbacks == 1 &&
                    replacement->callbacks == 0 && fixture.map->getObjects().size() == 1,
                "setObjects during a callback must preserve original onTurn membership and exclude replacements");
    expect_true(fixture.controller(order[1])->controls == 0 && fixture.controller(order[2])->turnEnds == 0 &&
                    fixture.controller(replacement)->controls == 1 && fixture.controller(replacement)->turnEnds == 1,
                "controller and end phases must use the replacement registry");
}

void testEndCallbacksUseTheirOwnMutableSelectionSnapshot() {
    RegionFixture fixture;
    for (int index = 0; index < 3; ++index) {
        fixture.actor("endResident" + std::to_string(index), "north");
    }
    auto order = snapshotOrder(fixture);
    order[1]->setStringProperty("simulationRegion", "south");
    fixture.map->setActiveSimulationRegion("north");
    std::shared_ptr<RegionActor> added;
    fixture.controller(order[0])->onEnd = [&] {
        order[1]->setStringProperty("simulationRegion", "north");
        fixture.map->removeObject(order[2]);
        added = fixture.actor("endArrival", "north");
    };
    fixture.map->move();
    expect_true(order[1]->callbacks == 0 && fixture.controller(order[1])->controls == 0 &&
                    fixture.controller(order[1])->turnEnds == 1 && fixture.controller(order[2])->turnEnds == 1 &&
                    added && fixture.controller(added)->turnEnds == 0,
                "end callbacks must activate later snapshot entries, retain removed entries and exclude arrivals");
    fixture.controller(order[0])->onEnd = {};
    auto endingOrder = snapshotOrder(fixture);
    std::vector<int> previousEnds;
    for (const auto &actor : endingOrder) {
        previousEnds.push_back(fixture.controller(actor)->turnEnds);
    }
    fixture.controller(endingOrder.front())->onEnd = [&] {
        fixture.map->setActiveSimulationRegion("south");
        fixture.map->setActiveSimulationRegion("north");
    };
    const auto turn = fixture.map->getTurn();
    fixture.map->move();
    expect_true(fixture.map->getTurn() == turn + 1 && !fixture.map->isMoving(),
                "an end-phase region round trip must still consume one turn and interrupt stale remaining work");
    for (std::size_t index = 0; index < endingOrder.size(); ++index) {
        expect_true(fixture.controller(endingOrder[index])->turnEnds == previousEnds[index] + (index == 0 ? 1 : 0),
                    "a changed region revision must suppress every remaining end callback even after a round trip");
    }
}

void testSelectionInvalidatesBeforeReentrantSetterWork() {
    CTypes::register_type_metadata<RegionPropertyObject, CMapObject>();
    RegionFixture fixture;
    auto object = std::make_shared<RegionPropertyObject>();
    object->setGame(fixture.game);
    object->setName("registeredRegion");
    fixture.map->addObject(object);
    fixture.map->setActiveSimulationRegion("north");
    fixture.map->move();
    object->afterSet = [&] { fixture.map->move(); };
    {
        CGameObject::PropertyNotificationBatch batch(*object);
        object->setStringProperty("simulationRegion", "north");
    }
    expect_true(object->callbacks == 1,
                "a registered setter must invalidate selection before reentrant work despite suppressed notifications");
    object->afterSet = {};
    object->region = "south";
    object->notifyPropertiesChanged({"simulationRegion"});
    fixture.map->move();
    expect_true(object->callbacks == 1, "explicit batched property notifications must invalidate active selection");
    object->region = "north";
    object->notifyPropertyChanged("simulationRegion");
    fixture.map->move();
    expect_true(object->callbacks == 2, "explicit property notifications must invalidate active selection");
}

void testAssignedPlayerInvalidatesAnInactiveSelection() {
    RegionFixture fixture;
    auto player = std::make_shared<CPlayer>();
    player->setGame(fixture.game);
    player->setName("player");
    player->setLevel(1);
    player->getBaseStats()->setMainStat("stamina");
    player->getBaseStats()->setStamina(10);
    player->setHp(70);
    player->setStringProperty("simulationRegion", "south");
    fixture.map->addObject(player);
    fixture.map->setActiveSimulationRegion("north");
    fixture.map->move();
    expect_true(!fixture.map->getAssignedPlayer(), "an inactive loaded player must not be adopted by selection alone");
    expect_true(fixture.map->getPlayer() == player, "the canonical loaded player must be adopted on demand");
    auto controller = std::make_shared<RegionController>();
    player->setController(controller);
    fixture.map->move();
    expect_true(controller->controls == 1 && controller->turnEnds == 1,
                "lazy player assignment must invalidate the previous dormant selection without a membership change");
}

void testRehomedEntriesRemainLiveInRetainedRegistries() {
    RegionFixture fixture;
    auto actor = fixture.actor("rehomedResident", "south");
    fixture.map->setActiveSimulationRegion("north");
    fixture.map->move();
    auto destination = std::make_shared<CMap>();
    destination->setGame(fixture.game);
    destination->addObject(actor);
    fixture.map->move();
    expect_true(actor->getMap() == destination && actor->callbacks == 0,
                "rehoming must preserve a dormant entry in the original registry");
    actor->setStringProperty("simulationRegion", "north");
    fixture.map->move();
    expect_true(actor->callbacks == 1 && fixture.controller(actor)->controls == 0 &&
                    fixture.controller(actor)->turnEnds == 1,
                "a retained foreign entry must keep live turn filtering while ownership still excludes planning");
    actor->setStringProperty("simulationRegion", "south");
    actor->setBoolProperty("alwaysSimulate", true);
    fixture.map->move();
    expect_true(actor->callbacks == 2 && fixture.controller(actor)->controls == 0 &&
                    fixture.controller(actor)->turnEnds == 2,
                "foreign-owner property changes must remain visible in every retaining map");
    destination->removeObject(actor);
    actor->setBoolProperty("alwaysSimulate", false);
    fixture.map->move();
    expect_true(actor->callbacks == 2, "an ownerless retained entry must still honor dormant filtering");
    actor->setStringProperty("simulationRegion", "north");
    fixture.map->move();
    expect_true(actor->callbacks == 3 && fixture.controller(actor)->controls == 1 &&
                    fixture.controller(actor)->turnEnds == 3,
                "ownerless entries must stay live when property notifications have no explicit map to invalidate");
}

void testRegisteredActivityGettersRemainLiveWithoutNotifications() {
    CTypes::register_type_metadata<RegionPropertyObject, CMapObject>();
    RegionFixture fixture;
    auto object = std::make_shared<RegionPropertyObject>();
    object->setGame(fixture.game);
    object->setName("computedRegion");
    fixture.map->addObject(object);
    fixture.map->setActiveSimulationRegion("north");
    std::string computedRegion = "south";
    object->readRegion = [&] { return computedRegion; };
    fixture.map->move();
    expect_true(object->callbacks == 0 && object->regionReads == 1,
                "selection building must not evaluate registered activity getters ahead of turn callbacks");
    computedRegion = "north";
    fixture.map->move();
    expect_true(object->callbacks == 1 && object->regionReads == 2,
                "a registered getter backed by external state must be reevaluated without setter notifications");
}

void testInvalidatedSnapshotsReleaseRemovedOwners() {
    RegionFixture fixture;
    auto object = std::make_shared<CMapObject>();
    object->setGame(fixture.game);
    object->setName("cachedOwner");
    fixture.map->addObject(object);
    fixture.map->move();
    std::weak_ptr<CMapObject> removed = object;
    fixture.map->removeObject(object);
    object.reset();
    vstd::event_loop<>::instance()->runReady();
    expect_true(removed.expired(), "invalidated object and active snapshots must not retain removed owners");
    object = std::make_shared<CMapObject>();
    object->setGame(fixture.game);
    object->setName("replacedOwner");
    fixture.map->addObject(object);
    fixture.map->move();
    removed = object;
    fixture.map->setObjects({});
    object.reset();
    expect_true(removed.expired(), "registry replacement must release cached owners outside in-flight snapshots");
}

void testForObjectsRetainsItsSnapshotAcrossNestedMutation() {
    RegionFixture fixture;
    for (int index = 0; index < 3; ++index) {
        fixture.actor("iterationResident" + std::to_string(index), "north");
    }
    auto order = snapshotOrder(fixture);
    std::vector<std::shared_ptr<RegionActor>> visited;
    std::vector<std::shared_ptr<RegionActor>> nested;
    std::shared_ptr<RegionActor> added;
    fixture.map->forObjects([&](auto object) {
        visited.push_back(std::dynamic_pointer_cast<RegionActor>(object));
        if (object == order.front()) {
            fixture.map->removeObject(order.back());
            added = fixture.actor("nestedArrival", "north");
            nested = snapshotOrder(fixture);
        }
    });
    expect_true(visited == order && std::ranges::find(nested, order.back()) == nested.end() &&
                    std::ranges::find(nested, added) != nested.end(),
                "nested forObjects calls must see new membership without mutating the outer snapshot");
}

void testSyntheticCityRegionCallbackAndControlBudget() {
    constexpr int WARD_ACTORS = 545;
    constexpr int GLOBAL_ACTORS = 3;
    constexpr int INTERIOR_ACTORS = 724;
    constexpr int ACTIVE_WARD_ACTORS = 61;
    RegionFixture fixture;
    std::cout << "synthetic city simulation region setup: actors=" << WARD_ACTORS + GLOBAL_ACTORS << std::endl;
    performance_guard::resetMapCoordinateLookupProbe();
    for (int index = 0; index < WARD_ACTORS; ++index) {
        fixture.actor("wardResident" + std::to_string(index), "ward" + std::to_string(index % 9));
    }
    for (int index = 0; index < GLOBAL_ACTORS; ++index) {
        auto global = fixture.actor("globalCoordinator" + std::to_string(index), "outside");
        global->setBoolProperty("alwaysSimulate", true);
    }
    const auto wardSetupProbes = performance_guard::mapCoordinateLookupProbeCount();
    performance_guard::disableMapCoordinateLookupProbe();
    expect_true(wardSetupProbes == 0,
                "city fixture setup must not scan colocated residents or dispatch movement before its first turn");
    std::cout << "synthetic city simulation region setup: coordinateProbes=" << wardSetupProbes << " budget=0"
              << std::endl;
    auto totals = [&fixture] {
        std::pair<int, int> counts;
        for (const auto &actor : fixture.actors) {
            counts.first += actor->callbacks;
            counts.second += fixture.controller(actor)->controls;
        }
        return counts;
    };
    fixture.map->move();
    const auto legacy = totals();
    expect_true(legacy.first == WARD_ACTORS + GLOBAL_ACTORS && legacy.second == legacy.first,
                "the fixed legacy baseline must dispatch exactly one callback and control request per actor");
    fixture.map->setActiveSimulationRegion("ward0");
    fixture.map->move();
    const auto firstActive = totals();
    const int budget = ACTIVE_WARD_ACTORS + GLOBAL_ACTORS;
    expect_true(firstActive.first - legacy.first == budget && firstActive.second - legacy.second == budget,
                "active ward work must stay at exactly its 61 residents plus three global actors");
    std::cout << "synthetic city simulation region setup: addedInteriorActors=" << INTERIOR_ACTORS << std::endl;
    performance_guard::resetMapCoordinateLookupProbe();
    for (int index = 0; index < INTERIOR_ACTORS; ++index) {
        fixture.actor("interiorResident" + std::to_string(index), "interior" + std::to_string(index % 100));
    }
    const auto interiorSetupProbes = performance_guard::mapCoordinateLookupProbeCount();
    performance_guard::disableMapCoordinateLookupProbe();
    expect_true(interiorSetupProbes == 0,
                "adding dormant interiors must not perform quadratic contact work during fixture setup");
    std::cout << "synthetic city simulation region setup: interiorCoordinateProbes=" << interiorSetupProbes
              << " budget=0" << std::endl;
    fixture.map->move();
    const auto expanded = totals();
    expect_true(
        expanded.first - firstActive.first == budget && expanded.second - firstActive.second == budget &&
            fixture.map->getObjects().size() == WARD_ACTORS + GLOBAL_ACTORS + INTERIOR_ACTORS,
        "adding 724 dormant interior actors must not increase active callback or controller work or discard state");
    constexpr int WARM_TURNS = 8;
    performance_guard::resetMapTurnSelectionProbe();
    for (int index = 0; index < WARM_TURNS; ++index) {
        fixture.map->move();
    }
    const auto selectionWork = performance_guard::mapTurnSelectionProbeStats();
    performance_guard::disableMapTurnSelectionProbe();
    expect_true(selectionWork.objectSnapshotBuilds == 0 && selectionWork.objectSnapshotEntries == 0 &&
                    selectionWork.selectionBuilds == 0 && selectionWork.fallbackVisits == 0 &&
                    selectionWork.candidateVisits == 3 * budget * WARM_TURNS &&
                    selectionWork.simulationChecks == 5 * budget * WARM_TURNS,
                "stable turns must reuse their snapshots and inspect only active residents in all three phases");
    const auto warmed = totals();
    expect_true(warmed.first - expanded.first == budget * WARM_TURNS &&
                    warmed.second - expanded.second == budget * WARM_TURNS,
                "selection reuse must retain exactly one callback and control request per active actor per turn");
    std::cout << "synthetic city selection guard: warmTurns=" << WARM_TURNS
              << " snapshotBuilds=" << selectionWork.objectSnapshotBuilds
              << " snapshotEntries=" << selectionWork.objectSnapshotEntries
              << " selectionBuilds=" << selectionWork.selectionBuilds << " candidates=" << selectionWork.candidateVisits
              << " candidateBudget=" << 3 * budget * WARM_TURNS << " predicates=" << selectionWork.simulationChecks
              << " predicateBudget=" << 5 * budget * WARM_TURNS << " fallback=" << selectionWork.fallbackVisits << "\n";
    std::cout << "synthetic city simulation region guard: wardActors=" << WARD_ACTORS << " globals=" << GLOBAL_ACTORS
              << " addedInteriorActors=" << INTERIOR_ACTORS << " legacyCallbacks=" << legacy.first
              << " legacyControls=" << legacy.second << " activeCallbacks=" << firstActive.first - legacy.first
              << " activeControls=" << firstActive.second - legacy.second
              << " expandedCallbacks=" << expanded.first - firstActive.first
              << " expandedControls=" << expanded.second - firstActive.second
              << " wardSetupCoordinateProbes=" << wardSetupProbes
              << " interiorSetupCoordinateProbes=" << interiorSetupProbes << " callbackAndControlBudget=" << budget
              << " (synthetic fixture, not a measured source city run)\n";
}
} // namespace

void run_simulation_region_tests() {
    testRegionFixtureSetupDoesNotRunMovementHooks();
    testDefaultAndOptInRegionTurns();
    testInactiveMovementAndPlayerExemption();
    testRegionActivationDuringCallbacksConsumesOneTurnWithoutMixingRegions();
    testRegionRoundTripInvalidatesPendingControllerPlans();
    testPortalRegionChangeRetainsTheFirstCommittedMoveAndDropsRemainingPlans();
    testSimulationPropertiesRoundTripWithoutChangingLegacyDefaults();
    testBatchedActivationPreservesTheUnvisitedSnapshotSuffix();
    testRemovedAndNewObjectsRetainTheirPhaseMembership();
    testRegistryReplacementRetainsTheOriginalTurnSnapshot();
    testEndCallbacksUseTheirOwnMutableSelectionSnapshot();
    testSelectionInvalidatesBeforeReentrantSetterWork();
    testAssignedPlayerInvalidatesAnInactiveSelection();
    testRehomedEntriesRemainLiveInRetainedRegistries();
    testRegisteredActivityGettersRemainLiveWithoutNotifications();
    testInvalidatedSnapshotsReleaseRemovedOwners();
    testForObjectsRetainsItsSnapshotAcrossNestedMutation();
    testSyntheticCityRegionCallbackAndControlBudget();
}
