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
#include "core/CMovementPresenter.h"
#include "core/CPythonOverrides.h"
#include "core/CRuntimeBridge.h"
#include "core/CStats.h"
#include "core/CTypes.h"
#include "core/CWrapper.h"
#include "gui/CAnimation.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CMovementAnimation.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/object/CProxyGraphicsObject.h"
#include "handler/CObjectHandler.h"
#include "object/CCreature.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
bool pointEquals(SDL_Point point, int x, int y) { return point.x == x && point.y == y; }

void testMovementSamplesStartMiddleAndFinalFrames() {
    CMovementAnimation movement;
    expect_true(movement.isCompleted(), "an unused movement must not block presentation");
    movement.begin(EAST, 1000, false, true);
    expect_true(!movement.isCompleted() && pointEquals(movement.cameraOffset(64), 64, 0) &&
                    pointEquals(movement.actorOffset(64), -64, 0),
                "the first camera and actor offsets preserve the player's original visible position");
    movement.advance(1075);
    expect_true(!movement.isCompleted() && pointEquals(movement.cameraOffset(64), 32, 0) &&
                    pointEquals(movement.actorOffset(64), -32, 0),
                "halfway through a 150 ms step both camera and actor have a real intermediate offset");
    movement.advance(1149);
    expect_true(!movement.isCompleted(), "the step must not finish before its final 150 ms frame");
    movement.advance(1150);
    expect_true(movement.isCompleted() && pointEquals(movement.cameraOffset(64), 0, 0) &&
                    pointEquals(movement.actorOffset(64), 0, 0),
                "the final frame must place the camera and actor at their committed cells");

    movement.begin(NORTH, 2000, false, false);
    expect_true(pointEquals(movement.cameraOffset(64), 0, 0) && pointEquals(movement.actorOffset(64), 0, 64),
                "a visible non-player actor starts at its source without moving the camera");
    movement.advance(2075);
    expect_true(pointEquals(movement.actorOffset(64), 0, 32),
                "a non-player actor must interpolate independently halfway to its committed cell");
    movement.advance(2200);
    expect_true(movement.isCompleted() && pointEquals(movement.actorOffset(64), 0, 0),
                "late frames clamp to the destination rather than overshooting");
}

void testMovementClockWrapBackwardFramesAndReducedMotion() {
    CMovementAnimation movement;
    movement.begin(WEST, 1000, false, true);
    movement.advance(999);
    expect_true(!movement.isCompleted() && pointEquals(movement.cameraOffset(64), -64, 0),
                "a backward timestamp must not underflow into a completed movement");
    movement.advance(1075);
    movement.advance(1025);
    expect_true(!movement.isCompleted() && pointEquals(movement.cameraOffset(64), -32, 0),
                "out-of-order frames cannot move an animation backward");
    movement.advance(1150);
    movement.advance(1000);
    expect_true(movement.isCompleted(), "a completed movement cannot be resurrected by an old frame");

    constexpr auto start = std::numeric_limits<Uint32>::max() - 49;
    movement.begin(SOUTH, start, false, false);
    movement.advance(start + Uint32{75});
    expect_true(!movement.isCompleted() && pointEquals(movement.actorOffset(64), 0, -32),
                "SDL clock wrap must retain a halfway movement frame");
    movement.advance(start + CMovementAnimation::DURATION_MS);
    expect_true(movement.isCompleted(), "SDL clock wrap must finish at exactly the step duration");

    movement.begin(EAST, 3000, true, true);
    expect_true(!movement.isCompleted() && pointEquals(movement.actorOffset(64), 0, 0) &&
                    pointEquals(movement.cameraOffset(64), 0, 0),
                "reduced motion snaps geometry while retaining readable step pacing");
    movement.advance(3149);
    expect_true(!movement.isCompleted(), "reduced motion must still wait for its complete step interval");
    movement.advance(3150);
    expect_true(movement.isCompleted(), "reduced motion finishes at the same deterministic 150 ms boundary");
}

class ArrivalProbeCreature : public CCreature {
  public:
    vstd::task<void> afterMoveAsync() override {
        ++arrivals;
        if (trace)
            trace->push_back("arrival:" + getName());
        co_await CCreature::afterMoveAsync();
    }

    int arrivals = 0;
    std::vector<std::string> *trace = nullptr;
};

class EastStepController : public CController {
  public:
    vstd::task<Coords> controlAsync(std::shared_ptr<CCreature> actor) override { co_return actor->getCoords() + EAST; }
};

struct MovementFixture {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    std::shared_ptr<CMap> map = std::make_shared<CMap>();
    std::vector<std::shared_ptr<ArrivalProbeCreature>> actors;

    explicit MovementFixture(int actorCount = 1) {
        for (const auto &[name, builder] : *CTypes::builders())
            game->getObjectHandler()->registerType(name, builder);
        game->setMap(map);
        map->setGame(game);
        map->setXBounds({{0, 7}});
        map->setYBounds({{0, 2}});
        for (int x = 0; x < 8; ++x) {
            for (int y = 0; y < 3; ++y) {
                auto tile = std::make_shared<CTile>();
                tile->setGame(game);
                tile->setCanStep(true);
                map->addTile(tile, x, y, 0);
            }
        }
        for (int index = 0; index < actorCount; ++index) {
            auto actor = std::make_shared<ArrivalProbeCreature>();
            actor->setGame(game);
            actor->setName("movementActor" + std::to_string(index));
            actor->setNpc(true);
            auto stats = std::make_shared<CStats>();
            stats->setMainStat("stamina");
            stats->setStamina(10);
            actor->setBaseStats(stats);
            actor->setHp(actor->getHpMax());
            actor->setController(std::make_shared<EastStepController>());
            actor->setPosX(1);
            actor->setPosY(index);
            map->addObject(actor);
            actor->arrivals = 0;
            actors.push_back(actor);
        }
        vstd::event_loop<>::instance()->runUntilIdle();
    }

    ~MovementFixture() {
        if (game)
            game->getContext()->shutdown();
    }
};

struct PresenterGate {
    std::vector<std::shared_ptr<CMapObject>> actors;
    std::vector<Coords> origins;
    std::vector<Coords> destinations;
    std::size_t permits = 0;
    std::size_t completed = 0;
    bool fail = false;
};

vstd::task<void> presentGatedStep(std::shared_ptr<PresenterGate> gate, std::shared_ptr<CMapObject> actor, Coords origin,
                                  Coords destination) {
    gate->actors.push_back(actor);
    gate->origins.push_back(origin);
    gate->destinations.push_back(destination);
    const auto number = gate->actors.size();
    co_await vstd::until(vstd::event_loop<>::instance(), [gate, number] { return gate->permits >= number; });
    if (gate->fail)
        throw std::runtime_error("movement presenter failed");
    ++gate->completed;
}

CMovementPresenter gatedPresenter(const std::shared_ptr<PresenterGate> &gate) {
    return [gate](std::shared_ptr<CMapObject> actor, Coords origin, Coords destination) {
        return presentGatedStep(gate, std::move(actor), origin, destination);
    };
}

class HeadlessMovementGui : public CGui {
  public:
    HeadlessMovementGui() : CGui(WithoutWindow{}) {}
};

struct BatchLifecycleProbe {
    std::vector<std::string> trace;
    int beforeCalls = 0;
    int presented = 0;
    int finishCalls = 0;
    int cancelled = 0;
    bool allowBefore = false;
    bool allowFinish = false;
    bool failPresentation = false;
};

class BatchOrderController : public EastStepController {
  public:
    explicit BatchOrderController(std::shared_ptr<BatchLifecycleProbe> probe) : probe(std::move(probe)) {}

    void onStepCommitted(std::shared_ptr<CCreature> actor, const Coords &) override {
        probe->trace.push_back("committed:" + actor->getName());
    }

    void onTurnEnded(std::shared_ptr<CCreature> actor) override { probe->trace.push_back("ended:" + actor->getName()); }

  private:
    std::shared_ptr<BatchLifecycleProbe> probe;
};

vstd::task<void> batchBeforeStep(std::shared_ptr<BatchLifecycleProbe> probe, std::shared_ptr<CMapObject> actor,
                                 Coords origin, Coords destination) {
    ++probe->beforeCalls;
    probe->trace.push_back("before:" + actor->getName());
    expect_true(actor->getCoords() == origin && destination == origin + EAST,
                "the batch dependency barrier must precede the actor's position commit");
    co_await vstd::until(vstd::event_loop<>::instance(), [probe] { return probe->allowBefore; });
}

vstd::task<void> batchPresentStep(std::shared_ptr<BatchLifecycleProbe> probe, std::shared_ptr<CMapObject> actor, Coords,
                                  Coords destination) {
    ++probe->presented;
    probe->trace.push_back("present:" + actor->getName());
    expect_true(actor->getCoords() == destination, "the batch collector must receive the committed actor position");
    if (probe->failPresentation)
        throw std::runtime_error("batch presentation failed");
    co_return;
}

vstd::task<void> batchFinish(std::shared_ptr<BatchLifecycleProbe> probe) {
    ++probe->finishCalls;
    probe->trace.push_back("finish");
    co_await vstd::until(vstd::event_loop<>::instance(), [probe] { return probe->allowFinish; });
    probe->trace.push_back("finished");
}

CMovementPresentation lifecyclePresentation(const std::shared_ptr<BatchLifecycleProbe> &probe) {
    CMovementPresentation presentation;
    presentation.beforeStep = [probe](std::shared_ptr<CMapObject> actor, Coords origin, Coords destination) {
        return batchBeforeStep(probe, std::move(actor), origin, destination);
    };
    presentation.presentStep = [probe](std::shared_ptr<CMapObject> actor, Coords origin, Coords destination) {
        return batchPresentStep(probe, std::move(actor), origin, destination);
    };
    presentation.finish = [probe] { return batchFinish(probe); };
    presentation.cancel = [probe] {
        ++probe->cancelled;
        probe->trace.push_back("cancel");
    };
    return presentation;
}

void logBatchTraceMismatch(const std::vector<std::string> &expected, const std::vector<std::string> &actual) {
    if (expected == actual)
        return;
    std::cerr << "[batch-order] expected:";
    for (const auto &entry : expected)
        std::cerr << ' ' << entry;
    std::cerr << "\n[batch-order] actual:";
    for (const auto &entry : actual)
        std::cerr << ' ' << entry;
    std::cerr << '\n';
}

void testBatchDescriptorPreservesLogicalOrderAndFinishesBeforeTurnCommit() {
    MovementFixture fixture(3);
    auto probe = std::make_shared<BatchLifecycleProbe>();
    for (const auto &actor : fixture.actors) {
        actor->trace = &probe->trace;
        actor->setController(std::make_shared<BatchOrderController>(probe));
    }
    fixture.map->move();
    const auto legacy_trace = probe->trace;
    probe->trace.clear();
    for (const auto &actor : fixture.actors) {
        actor->relocateWithoutMoveHooks(Coords(1, actor->getPosY(), 0));
        actor->arrivals = 0;
    }
    const auto turn = fixture.map->getTurn();
    auto movement =
        fixture.game->getContext()->spawnTask(fixture.map->movePresentedAsync(lifecyclePresentation(probe)));
    auto loop = vstd::event_loop<>::instance();
    loop->runUntilIdle();
    expect_true(!movement.finished() && probe->beforeCalls == 1 && probe->presented == 0,
                "the first dependency barrier must suspend before any batch position commit");
    for (const auto &actor : fixture.actors)
        expect_true(actor->getPosX() == 1 && actor->arrivals == 0,
                    "a blocked beforeStep must leave all actor positions and arrival hooks untouched");
    probe->allowBefore = true;
    loop->runUntilIdle();
    std::vector<std::string> expected;
    for (const auto &entry : legacy_trace) {
        if (entry.starts_with("arrival:")) {
            const auto name = entry.substr(std::string("arrival:").size());
            expected.push_back("before:" + name);
            expected.push_back("present:" + name);
            expected.push_back(entry);
            expected.push_back("committed:" + name);
        }
    }
    expected.push_back("finish");
    logBatchTraceMismatch(expected, probe->trace);
    expect_true(probe->trace == expected && !movement.finished() && fixture.map->isMoving() &&
                    fixture.map->getTurn() == turn && probe->finishCalls == 1,
                "batch collection must preserve logical actor order and wait before turn-end notifications");
    probe->allowFinish = true;
    loop->runUntilIdle();
    expected.push_back("finished");
    for (const auto &entry : legacy_trace)
        if (entry.starts_with("ended:"))
            expected.push_back(entry);
    logBatchTraceMismatch(expected, probe->trace);
    expect_true(movement.finished() && probe->trace == expected && fixture.map->getTurn() == turn + 1 &&
                    !fixture.map->isMoving() && probe->cancelled == 0,
                "one successful finish barrier must precede ordered turn-end hooks and exactly one turn commit");
    if (movement.finished())
        movement.get();
}

void testBatchDescriptorCleansFailureCancellationStaleAndQuit() {
    auto loop = vstd::event_loop<>::instance();
    for (int failure = 0; failure < 4; ++failure) {
        MovementFixture fixture;
        auto probe = std::make_shared<BatchLifecycleProbe>();
        probe->allowBefore = failure < 2;
        probe->failPresentation = failure == 0;
        auto movement =
            fixture.game->getContext()->spawnTask(fixture.map->movePresentedAsync(lifecyclePresentation(probe)));
        loop->runUntilIdle();
        if (failure == 1) {
            expect_true(probe->finishCalls == 1 && !movement.finished(),
                        "the cancellation fixture must suspend in the final batch presentation barrier");
            movement.requestStop();
        } else if (failure == 2) {
            fixture.game->getContext()->advanceTransitionGeneration();
            probe->allowBefore = true;
        } else if (failure == 3) {
            SDL_Event event{};
            event.type = SDL_QUIT;
            expect_true(SDL_PushEvent(&event) == 1, "the batch quit fixture must queue a quit event");
            loop->runReady();
            probe->allowBefore = true;
        }
        loop->runUntilIdle();
        bool expected_failure = failure >= 2;
        if (movement.finished()) {
            try {
                movement.get();
            } catch (const vstd::task_cancelled &) {
                expected_failure = failure != 0;
            } catch (const std::runtime_error &error) {
                expected_failure = failure == 0 && std::string(error.what()) == "batch presentation failed";
            }
        }
        loop->resetQuit();
        expect_true(movement.finished() && expected_failure && !fixture.map->isMoving() && probe->cancelled == 1 &&
                        fixture.map->getTurn() == 0 && !fixture.actors.front()->getPendingMoveOrigin(),
                    "failed, cancelled, stale and quit batches must settle once and clear movement state");
        if (failure >= 2)
            expect_true(fixture.actors.front()->getPosX() == 1 && fixture.actors.front()->arrivals == 0,
                        "stale or quit beforeStep continuations cannot commit old actor movement");
    }
}

class CountingMapGraphicsObject : public CMapGraphicsObject {
  public:
    std::size_t refreshCalls = 0;

    std::list<std::shared_ptr<CGameGraphicsObject>> getProxiedObjects(std::shared_ptr<CGui> gui, int x,
                                                                      int y) override {
        ++refreshCalls;
        return CMapGraphicsObject::getProxiedObjects(std::move(gui), x, y);
    }
};

struct BatchGuiFixture {
    MovementFixture core{0};
    std::shared_ptr<CPlayer> player = std::make_shared<CPlayer>();
    std::shared_ptr<CGui> gui;
    std::shared_ptr<CountingMapGraphicsObject> world;
    std::vector<std::shared_ptr<CCreature>> actors;

    explicit BatchGuiFixture(const std::vector<Coords> &origins, bool reducedMotion = false, bool wrap = false) {
        core.map->setXBounds({{0, 15}});
        if (wrap)
            core.map->setWrapX({{0, 1}});
        for (int x = 8; x < 16; ++x) {
            for (int y = 0; y < 3; ++y) {
                auto tile = std::make_shared<CTile>();
                tile->setGame(core.game);
                tile->setCanStep(true);
                core.map->addTile(tile, x, y, 0);
            }
        }
        core.game->getObjectHandler()->registerType("CAnimation", [] { return std::make_shared<CAnimation>(); });
        core.game->getObjectHandler()->registerType("CStaticAnimation",
                                                    [] { return std::make_shared<CStaticAnimation>(); });
        core.game->getObjectHandler()->registerType("CGameObject", [] { return std::make_shared<CGameObject>(); });
        core.game->getObjectHandler()->registerType("CLayout", [] { return std::make_shared<CLayout>(); });
        core.game->getObjectHandler()->registerType("CPlayerController",
                                                    [] { return std::make_shared<CPlayerController>(); });
        core.game->getObjectHandler()->registerType("CPlayerFightController",
                                                    [] { return std::make_shared<CPlayerFightController>(); });
        player->setGame(core.game);
        auto stats = std::make_shared<CStats>();
        stats->setMainStat("stamina");
        stats->setStamina(10);
        player->setBaseStats(stats);
        player->setHp(player->getHpMax());
        core.map->setPlayer(player);
        player->relocateWithoutMoveHooks(Coords(0, 2, 0));
        for (const auto origin : origins) {
            auto actor = std::make_shared<CCreature>();
            actor->setGame(core.game);
            actor->setName("batchActor" + std::to_string(actors.size()));
            actor->setNpc(true);
            auto actor_stats = std::make_shared<CStats>();
            actor_stats->setMainStat("stamina");
            actor_stats->setStamina(10);
            actor->setBaseStats(actor_stats);
            actor->setHp(actor->getHpMax());
            actor->setController(std::make_shared<CController>());
            actor->setPosX(origin.x);
            actor->setPosY(origin.y);
            actor->setPosZ(origin.z);
            core.map->addObject(actor);
            actors.push_back(actor);
        }
        gui = std::make_shared<CGui>();
        gui->setGame(core.game);
        core.game->setGui(gui);
        expect_true(gui->applyUiPreferences(json{{"reducedMotion", reducedMotion}}.dump()),
                    "the batch GUI fixture must apply isolated motion preferences");
        gui->setWidth(1280);
        gui->setHeight(720);
        gui->setTileSize(64);
        gui->setLayout(std::make_shared<CLayout>());
        gui->getLayout()->setRect(0, 0, 1280, 720);
        world = std::make_shared<CountingMapGraphicsObject>();
        world->setType("CMapGraphicsObject");
        world->setGame(core.game);
        world->setLayout(std::make_shared<CLayout>());
        world->getLayout()->setRect(0, 0, 1280, 720);
        gui->pushChild(world);
        vstd::event_loop<>::instance()->runUntilIdle();
    }

    void renderAt(int timestamp) {
        world->renderObject(gui, CUtil::rect(0, 0, 1280, 720), timestamp);
        auto loop = vstd::event_loop<>::instance();
        const auto previous_fps = loop->getFps();
        loop->setFps(1000000);
        loop->runFrame();
        loop->setFps(previous_fps);
        loop->runUntilIdle();
    }
};

vstd::task<void> streamGuiBatch(std::vector<std::shared_ptr<CCreature>> actors, CMovementPresentation presentation,
                                bool synchronizeRouteOnCommit = false) {
    try {
        for (const auto &actor : actors) {
            const auto origin = actor->getCoords();
            const auto destination = actor->getMap()->normalizeCoords(origin + EAST);
            co_await presentation.beforeStep(actor, origin, destination);
            if (synchronizeRouteOnCommit) {
                // This direct GUI fixture has no moving map to protect a temporarily stale route cursor.
                co_await actor->moveToAsync(
                    destination, [actor, destination] { actor->getController()->onStepCommitted(actor, destination); },
                    presentation.presentStep);
            } else {
                co_await actor->moveToAsync(destination, {}, presentation.presentStep);
                actor->getController()->onStepCommitted(actor, destination);
            }
        }
        co_await presentation.finish();
    } catch (...) {
        presentation.cancel();
        throw;
    }
}

void testNpcBatchRefreshesOnlyMotionEndpoints() {
    for (const bool wrap : {false, true}) {
        BatchGuiFixture fixture({Coords(1, 1, 0), Coords(6, 1, 0), Coords(11, 1, 0)}, false, wrap);
        fixture.core.game->getObjectHandler()->registerType("CProxyGraphicsLayout",
                                                            [] { return std::make_shared<CProxyGraphicsLayout>(); });
        fixture.world->setProxyLayout("CProxyGraphicsLayout");
        fixture.world->refresh();
        const auto proxyCount = fixture.world->getChildren().size();
        const auto endpointsPerBoundary = fixture.actors.size() * 2 * (wrap ? 2 : 1);
        expect_true(proxyCount > endpointsPerBoundary * 2,
                    "the NPC refresh guard must contain more cells than the complete endpoint budget");
        fixture.world->refreshCalls = 0;
        auto movement = fixture.core.game->getContext()->spawnTask(
            streamGuiBatch(fixture.actors, fixture.world->movementPresentation(fixture.gui)));
        vstd::event_loop<>::instance()->runUntilIdle();
        expect_true(!movement.finished() && fixture.world->refreshCalls > 0 &&
                        fixture.world->refreshCalls <= endpointsPerBoundary,
                    "starting an NPC batch must refresh only its source and destination proxies");
        fixture.renderAt(1000);
        fixture.renderAt(1150);
        expect_true(movement.finished() && fixture.world->refreshCalls <= endpointsPerBoundary * 2 &&
                        fixture.world->getChildren().size() == proxyCount,
                    "finishing an NPC batch must restore endpoint proxies without rebuilding the viewport");
        if (movement.finished())
            movement.get();
        const auto playerCoords = fixture.player->getCoords();
        for (const auto &child : fixture.world->getChildren()) {
            const auto proxy = std::dynamic_pointer_cast<CProxyGraphicsObject>(child);
            if (!proxy)
                continue;
            const auto actual = fixture.core.map->normalizeCoords(
                Coords(playerCoords.x - fixture.gui->getTileCountX() / 2 + proxy->getX() - 1,
                       playerCoords.y - fixture.gui->getTileCountY() / 2 + proxy->getY() - 1, playerCoords.z));
            const auto graphics = proxy->getChildren();
            for (const auto &actor : fixture.actors) {
                const bool represented = std::any_of(graphics.begin(), graphics.end(), [&](const auto &graphic) {
                    const auto animation = std::dynamic_pointer_cast<CAnimation>(graphic);
                    return animation && animation->getObject() == actor;
                });
                expect_true(represented == (actual == actor->getCoords()),
                            "every normal or wrapped actor proxy must be restored exactly at its destination");
            }
        }
    }
}

void testDistantGuiActorsShareOneAnimationInterval() {
    for (const bool reduced_motion : {false, true}) {
        BatchGuiFixture fixture({Coords(1, 1, 0), Coords(6, 1, 0), Coords(11, 1, 0)}, reduced_motion);
        const auto baseline_children = fixture.world->getChildren().size();
        auto movement = fixture.core.game->getContext()->spawnTask(
            streamGuiBatch(fixture.actors, fixture.world->movementPresentation(fixture.gui)));
        vstd::event_loop<>::instance()->runUntilIdle();
        expect_true(!movement.finished() && fixture.world->getChildren().size() == baseline_children + 3,
                    "three distant actor overlays must coexist before a shared animation interval");
        fixture.renderAt(1000);
        for (const auto &actor : fixture.actors)
            expect_true(pointEquals(fixture.world->getActorOffset(actor, 64), reduced_motion ? 0 : -64, 0) &&
                            !actor->getPendingMoveOrigin(),
                        "independent batch actors must share a start timestamp after their logical arrivals");
        fixture.renderAt(1075);
        for (const auto &actor : fixture.actors)
            expect_true(pointEquals(fixture.world->getActorOffset(actor, 64), reduced_motion ? 0 : -32, 0),
                        "every distant actor must reach the same halfway frame together");
        fixture.renderAt(1149);
        expect_true(!movement.finished(), "one shared interval must retain its last incomplete frame");
        fixture.renderAt(1150);
        expect_true(movement.finished() && fixture.world->getChildren().size() == baseline_children &&
                        pointEquals(fixture.world->getCameraOffset(64), 0, 0),
                    "all distant actor overlays must finish and clean up after one 150 ms interval");
        if (movement.finished())
            movement.get();
    }
}

void testGuiBatchPlayerOwnsTheSingleCameraMotion() {
    BatchGuiFixture fixture({Coords(6, 1, 0), Coords(11, 1, 0)});
    auto actors = fixture.actors;
    actors.insert(actors.begin(), fixture.player);
    auto movement = fixture.core.game->getContext()->spawnTask(
        streamGuiBatch(actors, fixture.world->movementPresentation(fixture.gui)));
    vstd::event_loop<>::instance()->runUntilIdle();
    fixture.renderAt(1000);
    expect_true(pointEquals(fixture.world->getCameraOffset(64), 64, 0),
                "a batched player step must own exactly one source-preserving camera offset");
    fixture.renderAt(1075);
    expect_true(pointEquals(fixture.world->getCameraOffset(64), 32, 0),
                "other moving actors cannot replace or multiply the player's halfway camera offset");
    for (const auto &actor : actors)
        expect_true(pointEquals(fixture.world->getActorOffset(actor, 64), -32, 0),
                    "the player and distant actors must retain independent halfway sprite offsets");
    fixture.renderAt(1150);
    expect_true(movement.finished() && pointEquals(fixture.world->getCameraOffset(64), 0, 0),
                "the camera must finish with the shared player and actor interval");
    if (movement.finished())
        movement.get();
}

void testNearbyAndWrappedGuiPathsKeepOrderedAnimationIntervals() {
    for (const bool wrap : {false, true}) {
        const std::vector<Coords> origins = wrap ? std::vector<Coords>{Coords(0, 1, 0), Coords(14, 1, 0)}
                                                 : std::vector<Coords>{Coords(1, 1, 0), Coords(3, 1, 0)};
        BatchGuiFixture fixture(origins, false, wrap);
        auto movement = fixture.core.game->getContext()->spawnTask(
            streamGuiBatch(fixture.actors, fixture.world->movementPresentation(fixture.gui)));
        vstd::event_loop<>::instance()->runUntilIdle();
        expect_true(fixture.actors[0]->getCoords() == origins[0] + EAST &&
                        fixture.actors[1]->getCoords() == origins[1] && !movement.finished(),
                    "nearby swept paths must finish the earlier animation before committing the later actor");
        fixture.renderAt(1000);
        fixture.renderAt(1150);
        expect_true(!movement.finished() &&
                        fixture.actors[1]->getCoords() == fixture.core.map->normalizeCoords(origins[1] + EAST) &&
                        pointEquals(fixture.world->getActorOffset(fixture.actors[1], 64), -64, 0),
                    "normal and wrapped interaction neighborhoods must start a separate second animation interval");
        fixture.renderAt(2000);
        fixture.renderAt(2150);
        expect_true(movement.finished(), "two dependent actors must settle after exactly two animation intervals");
        if (movement.finished())
            movement.get();
    }
}

void testGuiBatchCancellationAndStaleContextClearEveryOverlay() {
    for (const bool cancel : {false, true}) {
        BatchGuiFixture fixture({Coords(1, 1, 0), Coords(6, 1, 0), Coords(11, 1, 0)});
        const auto baseline_children = fixture.world->getChildren().size();
        auto movement = fixture.core.game->getContext()->spawnTask(
            streamGuiBatch(fixture.actors, fixture.world->movementPresentation(fixture.gui)));
        auto loop = vstd::event_loop<>::instance();
        loop->runUntilIdle();
        expect_true(!movement.finished() && fixture.world->getChildren().size() == baseline_children + 3,
                    "the cleanup fixture must retain three pending actor overlays");
        if (cancel) {
            movement.requestStop();
            loop->runUntilIdle();
        } else {
            fixture.core.game->getContext()->advanceTransitionGeneration();
            fixture.renderAt(1000);
        }
        expect_true(movement.finished() && fixture.world->getChildren().size() == baseline_children,
                    "cancellation and stale context must release every pending actor overlay");
        for (const auto &actor : fixture.actors)
            expect_true(!actor->getPendingMoveOrigin() && pointEquals(fixture.world->getActorOffset(actor, 64), 0, 0),
                        "batch cleanup cannot leave ghost sprite offsets or pending movement origins");
        if (movement.finished()) {
            if (cancel) {
                bool stopped = false;
                try {
                    movement.get();
                } catch (const vstd::task_cancelled &) {
                    stopped = true;
                }
                expect_true(stopped, "cancelling an animated batch must propagate cancellation");
            } else {
                movement.get();
            }
        }
    }
}

bool isFootprintGraphic(const std::shared_ptr<CGameGraphicsObject> &graphic) {
    const auto animation = std::dynamic_pointer_cast<CAnimation>(graphic);
    const auto object = animation ? animation->getObject() : nullptr;
    return object && object->getAnimation() == "images/footprint";
}

bool currentPlayerCellHasFootprint(BatchGuiFixture &fixture) {
    const auto graphics = fixture.world->getProxiedObjects(fixture.gui, fixture.gui->getTileCountX() / 2 + 1,
                                                           fixture.gui->getTileCountY() / 2 + 1);
    return std::any_of(graphics.begin(), graphics.end(), isFootprintGraphic);
}

bool cachedProxyHasFootprint(const std::shared_ptr<CProxyGraphicsObject> &proxy) {
    const auto children = proxy->getChildren();
    return std::any_of(children.begin(), children.end(), isFootprintGraphic);
}

void testPlayerArrivalFootprintClearsBeforeLaterActorBatchFinishes() {
    for (const bool reduced_motion : {false, true}) {
        BatchGuiFixture fixture({Coords(3, 2, 0)}, reduced_motion);
        fixture.core.game->getObjectHandler()->registerType("CProxyGraphicsLayout",
                                                            [] { return std::make_shared<CProxyGraphicsLayout>(); });
        fixture.world->setProxyLayout("CProxyGraphicsLayout");
        fixture.world->refresh();
        std::shared_ptr<CProxyGraphicsObject> player_proxy;
        for (const auto &child : fixture.world->getChildren()) {
            const auto proxy = std::dynamic_pointer_cast<CProxyGraphicsObject>(child);
            if (proxy && proxy->getX() == fixture.gui->getTileCountX() / 2 + 1 &&
                proxy->getY() == fixture.gui->getTileCountY() / 2 + 1)
                player_proxy = proxy;
        }
        expect_true(player_proxy != nullptr, "the footprint fixture must retain the real player-cell proxy");
        if (!player_proxy)
            continue;
        const auto controller = std::dynamic_pointer_cast<CPlayerController>(fixture.player->getController());
        controller->setTarget(fixture.player, Coords(1, 2, 0));
        expect_true(!controller->isCompleted(fixture.player), "the footprint fixture must create a real player route");
        std::vector<std::shared_ptr<CCreature>> actors{fixture.player, fixture.actors.front()};
        auto movement = fixture.core.game->getContext()->spawnTask(
            streamGuiBatch(std::move(actors), fixture.world->movementPresentation(fixture.gui), true));
        vstd::event_loop<>::instance()->runUntilIdle();
        expect_true(fixture.player->getCoords() == Coords(1, 2, 0) && !movement.finished(),
                    "the final route step must commit while its dependent actor still waits");
        fixture.renderAt(1000);
        fixture.renderAt(1149);
        expect_true(
            cachedProxyHasFootprint(player_proxy) == !reduced_motion,
            "the current-cell footprint lasts until visual arrival, or disappears immediately for reduced motion");
        // Observe the retained proxy before queued completion callbacks can refresh the entire batch.
        fixture.world->renderObject(fixture.gui, CUtil::rect(0, 0, 1280, 720), 1150);
        expect_true(!movement.finished() && fixture.actors.front()->getCoords() == Coords(3, 2, 0) &&
                        !cachedProxyHasFootprint(player_proxy),
                    "the rendered player proxy must lose its footprint on the arrival frame before later turn work");
        fixture.renderAt(1150);
        expect_true(!movement.finished() && fixture.actors.front()->getCoords() == Coords(4, 2, 0) &&
                        !currentPlayerCellHasFootprint(fixture),
                    "the final route footprint must disappear on player arrival while a later actor still animates");
        fixture.renderAt(2000);
        fixture.renderAt(2150);
        expect_true(movement.finished() && !currentPlayerCellHasFootprint(fixture),
                    "a completed later batch cannot resurrect the player's cleared arrival footprint");
        if (movement.finished())
            movement.get();
    }
}

void testDirectPythonTileHookFlushesPreviousBatchAndWaitsForItsOwnStep() {
    const auto native_module = pybind11::module_::import("_game");
    pybind11::dict scope;
    scope["native"] = native_module;
    scope["__name__"] = "_nouraajd_movement_test";
    BatchGuiFixture fixture({Coords(1, 1, 0), Coords(11, 1, 0)});
    pybind11::exec(R"(
class DirectMovementTile(native.CTile):
    def __init__(self):
        super().__init__()
        self.steps = 0

    def onStep(self, actor):
        self.steps += 1

tile = DirectMovementTile()
)",
                   scope);
    const auto tile_object = scope["tile"].cast<pybind11::object>();
    const auto tile = tile_object.cast<std::shared_ptr<CTile>>();
    expect_true(typeid(*tile) == typeid(CWrapper<CTile>) && CPythonOverrides::find(tile.get()) == nullptr,
                "the Python tile regression must use a direct trampoline instance outside the override registry");
    expect_true(static_cast<bool>(pybind11::get_override(tile.get(), "onStep")),
                "the direct Python tile must expose an actual pybind11 onStep override");
    tile->setGame(fixture.core.game);
    tile->setCanStep(true);
    fixture.core.map->removeTile(12, 1, 0);
    expect_true(fixture.core.map->addTile(tile, 12, 1, 0) && fixture.core.map->getTile(12, 1, 0) == tile,
                "the scripted tile must replace the existing fixture destination cell");
    auto movement = fixture.core.game->getContext()->spawnTask(
        streamGuiBatch(fixture.actors, fixture.world->movementPresentation(fixture.gui)));
    vstd::event_loop<>::instance()->runUntilIdle();
    expect_true(!movement.finished() && fixture.actors[0]->getPosX() == 2 && fixture.actors[1]->getPosX() == 11 &&
                    tile_object.attr("steps").cast<int>() == 0,
                "a distant Python tile hook must flush the preceding batch before its actor position commits");
    fixture.renderAt(1000);
    fixture.renderAt(1149);
    expect_true(fixture.actors[1]->getPosX() == 11 && tile_object.attr("steps").cast<int>() == 0,
                "the scripted step cannot begin while the earlier actor is still visibly moving");
    fixture.renderAt(1150);
    expect_true(
        !movement.finished() && fixture.actors[1]->getPosX() == 12 &&
            fixture.actors[1]->getPendingMoveOrigin().has_value() && tile_object.attr("steps").cast<int>() == 0,
        "the scripted actor must retain legacy presentation-before-arrival timing after the dependency barrier");
    fixture.renderAt(2000);
    fixture.renderAt(2149);
    expect_true(tile_object.attr("steps").cast<int>() == 0,
                "Python onStep must wait for the scripted actor's complete animation interval");
    fixture.renderAt(2150);
    expect_true(movement.finished() && tile_object.attr("steps").cast<int>() == 1 &&
                    !fixture.actors[1]->getPendingMoveOrigin(),
                "the direct Python tile hook must execute exactly once after its own final animation frame");
    if (movement.finished())
        movement.get();
}

void testMapWaitsForEachActorPresentationBeforeArrivalAndNextActor() {
    MovementFixture fixture(3);
    auto gate = std::make_shared<PresenterGate>();
    const int turn = fixture.map->getTurn();
    auto movement = fixture.game->getContext()->spawnTask(fixture.map->moveAsync(gatedPresenter(gate)));
    auto loop = vstd::event_loop<>::instance();
    for (std::size_t index = 0; index < fixture.actors.size(); ++index) {
        loop->runUntilIdle();
        expect_true(!movement.finished() && fixture.map->isMoving() && fixture.map->getTurn() == turn &&
                        gate->actors.size() == index + 1 && gate->completed == index,
                    "one map turn must wait for the current actor rather than committing later actors");
        if (gate->actors.size() != index + 1)
            break;
        auto actor = std::dynamic_pointer_cast<ArrivalProbeCreature>(gate->actors[index]);
        expect_true(actor && actor->getCoords() == gate->destinations[index] && actor->arrivals == 0 &&
                        actor->getPendingMoveOrigin() == std::optional<Coords>{gate->origins[index]},
                    "position commits before presentation, while arrival hooks and move origin remain pending");
        expect_true(gate->destinations[index] == gate->origins[index] + EAST,
                    "the presenter must receive the actual source and committed destination");
        ++gate->permits;
    }
    gate->permits = fixture.actors.size();
    loop->runUntilIdle();
    expect_true(movement.finished() && !fixture.map->isMoving() && fixture.map->getTurn() == turn + 1 &&
                    gate->completed == fixture.actors.size(),
                "all actor presentations must settle before exactly one turn completes");
    if (movement.finished())
        movement.get();
    for (const auto &actor : fixture.actors)
        expect_true(actor->arrivals == 1 && !actor->getPendingMoveOrigin(),
                    "each released actor runs its arrival hooks once and clears its pending origin");
}

void testEmptyPresenterPreservesHeadlessTurnsWithoutFrames() {
    for (bool attachedGui : {false, true}) {
        MovementFixture fixture(3);
        std::shared_ptr<CGui> gui;
        if (attachedGui) {
            gui = std::make_shared<HeadlessMovementGui>();
            gui->setGame(fixture.game);
            fixture.game->setGui(gui);
            expect_true(!gui->getRenderer(), "the attached headless GUI fixture must not create a display renderer");
        }
        int frames = 0;
        auto loop = vstd::event_loop<>::instance();
        auto observer = loop->connectFrameCallback([&frames](int) { ++frames; });
        const int turn = fixture.map->getTurn();
        fixture.map->move();
        expect_true(frames == 0 && !fixture.map->isMoving() && fixture.map->getTurn() == turn + 1,
                    "empty presentation must finish a synchronous turn without pacing, even with an attached GUI");
        for (const auto &actor : fixture.actors)
            expect_true(actor->getPosX() == 2 && actor->arrivals == 1 && !actor->getPendingMoveOrigin(),
                        "empty presentation retains actual actor movement and arrival behavior");
        if (gui) {
            game_async::wait(fixture.game->getContext()->spawnTask(gui->moveMapTurnAsync()),
                             game_async::WaitMode::PostedWork);
            expect_true(frames == 0 && !fixture.map->isMoving() && fixture.map->getTurn() == turn + 2,
                        "a GUI without a renderer must also finish its explicit turn boundary without frames");
        }
    }
}

void testPendingGuiMovementDoesNotRetainTheGameOwner() {
    MovementFixture fixture(0);
    fixture.game->getObjectHandler()->registerType("CAnimation", [] { return std::make_shared<CAnimation>(); });
    fixture.game->getObjectHandler()->registerType("CPlayerController",
                                                   [] { return std::make_shared<CPlayerController>(); });
    fixture.game->getObjectHandler()->registerType("CPlayerFightController",
                                                   [] { return std::make_shared<CPlayerFightController>(); });
    auto player = std::make_shared<CPlayer>();
    player->setGame(fixture.game);
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("stamina");
    stats->setStamina(10);
    player->setBaseStats(stats);
    fixture.map->setPlayer(player);
    auto controller = std::dynamic_pointer_cast<CPlayerController>(player->getController());
    controller->setTarget(player, Coords(2, 0, 0));
    auto gui = std::make_shared<CGui>();
    gui->setGame(fixture.game);
    fixture.game->setGui(gui);
    gui->setLayout(std::make_shared<CLayout>());
    gui->getLayout()->setRect(0, 0, 1280, 720);
    auto world = std::make_shared<CMapGraphicsObject>();
    world->setType("CMapGraphicsObject");
    world->setGame(fixture.game);
    world->setLayout(std::make_shared<CLayout>());
    world->getLayout()->setRect(0, 0, 1280, 720);
    gui->pushChild(world);
    const auto baseline_children = world->getChildren().size();
    auto context = fixture.game->getContext();
    std::weak_ptr<CGame> owner = fixture.game;
    auto movement = context->spawnTask(gui->moveMapTurnAsync());
    auto loop = vstd::event_loop<>::instance();
    loop->runUntilIdle();
    expect_true(!movement.finished() && fixture.map->isMoving() && player->getCoords() == Coords(1, 0, 0) &&
                    !player->getPendingMoveOrigin() && world->getChildren().size() > baseline_children,
                "owner destruction must interrupt an actual committed batch step waiting for GUI presentation");
    fixture.game.reset();
    expect_true(owner.expired() && !context->isActive() && movement.finished() && !fixture.map->isMoving() &&
                    !player->getPendingMoveOrigin() && !gui->isActive(),
                "pending GUI presentation must let the last game owner destruct and cancel the complete turn");
    bool cancelled = false;
    if (movement.finished()) {
        try {
            movement.get();
        } catch (const vstd::task_cancelled &) {
            cancelled = true;
        }
    }
    expect_true(cancelled, "destruction must settle a pending GUI turn as cancelled without another display frame");
    context->shutdown();
}

void testStalePresentationNeverDispatchesOldArrival() {
    for (int change = 0; change < 6; ++change) {
        MovementFixture fixture;
        const auto actor = fixture.actors.front();
        auto gate = std::make_shared<PresenterGate>();
        auto movement =
            fixture.game->getContext()->spawnTask(actor->moveToAsync(Coords(2, 0, 0), {}, gatedPresenter(gate)));
        auto loop = vstd::event_loop<>::instance();
        loop->runUntilIdle();
        expect_true(gate->actors.size() == 1 && !movement.finished() && actor->arrivals == 0,
                    "the stale-arrival fixture must suspend after a real position commit");
        if (change == 0) {
            actor->relocateWithoutMoveHooks(Coords(3, 0, 0));
        } else if (change == 1) {
            fixture.game->getContext()->advanceTransitionGeneration();
        } else if (change == 2) {
            auto replacementMap = std::make_shared<CMap>();
            replacementMap->setGame(fixture.game);
            fixture.game->setMap(replacementMap);
        } else if (change == 3) {
            fixture.map->removeObject(actor);
            auto replacement = std::make_shared<CCreature>();
            replacement->setGame(fixture.game);
            replacement->setName(actor->getName());
            replacement->setNpc(true);
            fixture.map->addObject(replacement);
        } else if (change == 4) {
            actor->setName("renamedMovementActor");
        } else {
            auto otherGame = std::make_shared<CGame>();
            otherGame->setMap(fixture.map);
            actor->setGame(otherGame);
        }
        gate->permits = 1;
        loop->runUntilIdle();
        expect_true(movement.finished() && actor->arrivals == 0 && !actor->getPendingMoveOrigin(),
                    "changed location, generation, map, registry instance, name or owner suppresses old arrival");
        if (movement.finished())
            movement.get();
    }
}

void testPresentationFailureAndCancellationClearTurnAndMoveState() {
    for (bool cancel : {false, true}) {
        MovementFixture fixture;
        const auto actor = fixture.actors.front();
        auto gate = std::make_shared<PresenterGate>();
        auto movement = fixture.game->getContext()->spawnTask(fixture.map->moveAsync(gatedPresenter(gate)));
        auto loop = vstd::event_loop<>::instance();
        loop->runUntilIdle();
        expect_true(!movement.finished() && fixture.map->isMoving() && actor->getPendingMoveOrigin().has_value(),
                    "failure cleanup must exercise a suspended real movement turn");
        if (cancel) {
            movement.requestStop();
        } else {
            gate->fail = true;
            gate->permits = 1;
        }
        loop->runUntilIdle();
        bool expectedFailure = false;
        if (movement.finished()) {
            try {
                movement.get();
            } catch (const vstd::task_cancelled &) {
                expectedFailure = cancel;
            } catch (const std::runtime_error &error) {
                expectedFailure = !cancel && std::string(error.what()) == "movement presenter failed";
            }
        }
        expect_true(movement.finished() && expectedFailure && !fixture.map->isMoving() && actor->arrivals == 0 &&
                        !actor->getPendingMoveOrigin(),
                    "presentation errors and cancellation propagate while clearing map and actor pending state");
    }
}

void testWrappedStepsPresentButRelocationAndUnregisteredObjectsDoNot() {
    MovementFixture fixture;
    auto actor = fixture.actors.front();
    auto gate = std::make_shared<PresenterGate>();
    gate->permits = 8;
    auto presenter = gatedPresenter(gate);
    auto context = fixture.game->getContext();
    fixture.map->setWrapX({{0, 1}});
    actor->relocateWithoutMoveHooks(Coords(0, 0, 0));
    game_async::wait(context->spawnTask(actor->moveToAsync(Coords(7, 0, 0), {}, presenter)),
                     game_async::WaitMode::PostedWork);
    expect_true(gate->actors.size() == 1 && gate->origins.front() == ZERO &&
                    gate->destinations.front() == Coords(7, 0, 0),
                "a one-cell wrapped step must present its actual normalized coordinates");
    game_async::wait(context->spawnTask(actor->moveToAsync(Coords(4, 0, 0), {}, presenter)),
                     game_async::WaitMode::PostedWork);
    game_async::wait(context->spawnTask(actor->moveToAsync(Coords(4, 0, 1), {}, presenter)),
                     game_async::WaitMode::PostedWork);
    auto detached = std::make_shared<ArrivalProbeCreature>();
    detached->setGame(fixture.game);
    detached->setName("unregisteredMovementActor");
    game_async::wait(context->spawnTask(detached->moveToAsync(Coords(1, 0, 0), {}, presenter)),
                     game_async::WaitMode::PostedWork);
    expect_true(gate->actors.size() == 1,
                "long teleports, floor changes and unregistered actors must not create movement presentation");
}
} // namespace

int main(int argc, char **argv) {
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    SDL_setenv("SDL_RENDER_DRIVER", "software", 1);
    const auto *previous_preferences = SDL_getenv("GAME_UI_PREFERENCES_PATH");
    const std::string previous_preferences_path = previous_preferences ? previous_preferences : "";
    const auto preferences_path =
        std::filesystem::temp_directory_path() /
        ("nouraajd-gui-movement-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) +
         ".json");
    SDL_setenv("GAME_UI_PREFERENCES_PATH", preferences_path.string().c_str(), 1);
    pybind11::scoped_interpreter interpreter;
    if (argc > 0)
        pybind11::module_::import("sys").attr("path").attr("insert")(
            0, std::filesystem::absolute(argv[0]).parent_path().string());
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");
    testMovementSamplesStartMiddleAndFinalFrames();
    testMovementClockWrapBackwardFramesAndReducedMotion();
    testMapWaitsForEachActorPresentationBeforeArrivalAndNextActor();
    testBatchDescriptorPreservesLogicalOrderAndFinishesBeforeTurnCommit();
    testBatchDescriptorCleansFailureCancellationStaleAndQuit();
    testNpcBatchRefreshesOnlyMotionEndpoints();
    testDistantGuiActorsShareOneAnimationInterval();
    testGuiBatchPlayerOwnsTheSingleCameraMotion();
    testNearbyAndWrappedGuiPathsKeepOrderedAnimationIntervals();
    testGuiBatchCancellationAndStaleContextClearEveryOverlay();
    testPlayerArrivalFootprintClearsBeforeLaterActorBatchFinishes();
    testEmptyPresenterPreservesHeadlessTurnsWithoutFrames();
    testPendingGuiMovementDoesNotRetainTheGameOwner();
    testStalePresentationNeverDispatchesOldArrival();
    testPresentationFailureAndCancellationClearTurnAndMoveState();
    testWrappedStepsPresentButRelocationAndUnregisteredObjectsDoNot();
    testDirectPythonTileHookFlushesPreviousBatchAndWaitsForItsOwnStep();
    SDL_setenv("GAME_UI_PREFERENCES_PATH", previous_preferences_path.c_str(), 1);
    std::error_code cleanup_error;
    std::filesystem::remove(preferences_path, cleanup_error);
    std::filesystem::remove(preferences_path.string() + ".tmp", cleanup_error);
    return finish_tests();
}
