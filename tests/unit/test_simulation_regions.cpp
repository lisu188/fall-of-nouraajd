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
    void onTurnEnded(std::shared_ptr<CCreature>) override { ++turnEnds; }

    Coords step = ZERO;
    std::function<void()> onPlan;
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

    std::function<void()> onTick;
    int callbacks = 0;
};

class RegionPortal : public CBuilding {
  public:
    void onEnter(std::shared_ptr<CGameEvent>) override {
        ++entries;
        getMap()->setStringProperty("activeSimulationRegion", "south");
    }

    int entries = 0;
};

struct RegionFixture {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    std::shared_ptr<CMap> map = std::make_shared<CMap>();
    std::vector<std::shared_ptr<RegionActor>> actors;

    RegionFixture() {
        game->setMap(map);
        map->setGame(game);
        game->getObjectHandler()->registerType("CPlayerController", [] { return std::make_shared<CPlayerController>(); });
        game->getObjectHandler()->registerType("CPlayerFightController", [] {
            return std::make_shared<CPlayerFightController>();
        });
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
        actor->setCoords(coords);
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
    expect_true(coordinator->callbacks == 1 && south->callbacks == 0 && fixture.controller(north)->controls == 0 &&
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
                    resident->getNumericProperty("plugin_cityConversationCount") == 7 && restored->isSimulationActive(resident),
                "the existing serializer must preserve region, global override and resident state together");
    (*serialized)["properties"].erase("activeSimulationRegion");
    CSerialization::StrictScope legacyStrict("simulation-region-legacy");
    auto legacy = std::dynamic_pointer_cast<CMap>(ObjectJson::deserialize(fixture.game, serialized, legacyStrict));
    expect_true(legacy && legacy->getActiveSimulationRegion().empty() &&
                    legacy->isSimulationActive(legacy->getObjectByName("persistentResident")),
                "old saves without an active region must retain the legacy all-objects behavior");
}

void testSyntheticCityRegionCallbackAndControlBudget() {
    constexpr int WARD_ACTORS = 545;
    constexpr int GLOBAL_ACTORS = 3;
    constexpr int INTERIOR_ACTORS = 724;
    constexpr int ACTIVE_WARD_ACTORS = 61;
    RegionFixture fixture;
    for (int index = 0; index < WARD_ACTORS; ++index) {
        fixture.actor("wardResident" + std::to_string(index), "ward" + std::to_string(index % 9));
    }
    for (int index = 0; index < GLOBAL_ACTORS; ++index) {
        auto global = fixture.actor("globalCoordinator" + std::to_string(index), "outside");
        global->setBoolProperty("alwaysSimulate", true);
    }
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
    for (int index = 0; index < INTERIOR_ACTORS; ++index) {
        fixture.actor("interiorResident" + std::to_string(index), "interior" + std::to_string(index % 100));
    }
    fixture.map->move();
    const auto expanded = totals();
    expect_true(expanded.first - firstActive.first == budget && expanded.second - firstActive.second == budget &&
                    fixture.map->getObjects().size() == WARD_ACTORS + GLOBAL_ACTORS + INTERIOR_ACTORS,
                "adding 724 dormant interior actors must not increase active callback or controller work or discard state");
    std::cout << "synthetic city simulation region guard: wardActors=" << WARD_ACTORS
              << " globals=" << GLOBAL_ACTORS << " addedInteriorActors=" << INTERIOR_ACTORS
              << " legacyCallbacks=" << legacy.first << " legacyControls=" << legacy.second
              << " activeCallbacks=" << firstActive.first - legacy.first
              << " activeControls=" << firstActive.second - legacy.second
              << " expandedCallbacks=" << expanded.first - firstActive.first
              << " expandedControls=" << expanded.second - firstActive.second << " callbackAndControlBudget=" << budget
              << " (synthetic fixture, not a measured source city run)\n";
}
} // namespace

void run_simulation_region_tests() {
    testDefaultAndOptInRegionTurns();
    testInactiveMovementAndPlayerExemption();
    testRegionActivationDuringCallbacksConsumesOneTurnWithoutMixingRegions();
    testRegionRoundTripInvalidatesPendingControllerPlans();
    testPortalRegionChangeRetainsTheFirstCommittedMoveAndDropsRemainingPlans();
    testSimulationPropertiesRoundTripWithoutChangingLegacyDefaults();
    testSyntheticCityRegionCallbackAndControlBudget();
}
