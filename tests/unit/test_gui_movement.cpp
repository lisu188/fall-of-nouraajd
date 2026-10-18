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
#include "core/CRuntimeBridge.h"
#include "core/CStats.h"
#include "core/CTypes.h"
#include "gui/CAnimation.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CMovementAnimation.h"
#include "gui/object/CMapGraphicsObject.h"
#include "handler/CObjectHandler.h"
#include "object/CCreature.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <limits>
#include <stdexcept>
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
        co_await CCreature::afterMoveAsync();
    }

    int arrivals = 0;
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
    auto context = fixture.game->getContext();
    std::weak_ptr<CGame> owner = fixture.game;
    auto movement = context->spawnTask(gui->moveMapTurnAsync());
    auto loop = vstd::event_loop<>::instance();
    loop->runUntilIdle();
    expect_true(!movement.finished() && fixture.map->isMoving() && player->getCoords() == Coords(1, 0, 0) &&
                    player->getPendingMoveOrigin().has_value(),
                "owner destruction must interrupt an actual committed step waiting for GUI presentation");
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

int main() {
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    SDL_setenv("SDL_RENDER_DRIVER", "software", 1);
    pybind11::scoped_interpreter interpreter;
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");
    testMovementSamplesStartMiddleAndFinalFrames();
    testMovementClockWrapBackwardFramesAndReducedMotion();
    testMapWaitsForEachActorPresentationBeforeArrivalAndNextActor();
    testEmptyPresenterPreservesHeadlessTurnsWithoutFrames();
    testPendingGuiMovementDoesNotRetainTheGameOwner();
    testStalePresentationNeverDispatchesOldArrival();
    testPresentationFailureAndCancellationClearTurnAndMoveState();
    testWrappedStepsPresentButRelocationAndUnregisteredObjectsDoNot();
    return finish_tests();
}
