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
#include "core/CNavigation.h"
#include "core/CRuntimeBridge.h"
#include "core/CStats.h"
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "gui/CAnimation.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/object/CProxyGraphicsObject.h"
#include "handler/CObjectHandler.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <array>
#include <algorithm>
#include <vector>

namespace {
Coords resolvePlan(vstd::task<Coords> plan) {
    return game_async::run(std::move(plan), game_async::WaitMode::PostedWork);
}

class SolidMovementAnimation : public CStaticAnimation {
  public:
    inline static std::vector<SDL_Rect> actorRects;
    inline static std::vector<const CGameObject *> actorInstances;
    inline static std::string rightClickTarget;

    void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int) override {
        const auto object = getObject();
        if (!object)
            return;
        const bool actor = object->getName() == "movingColorActor";
        if (actor) {
            actorRects.push_back(*rect);
            actorInstances.push_back(object.get());
        }
        const auto renderer = gui->getRenderer();
        SDL_SetRenderDrawColor(renderer, actor ? 255 : 0, actor ? 0 : 200, 0, 255);
        expect_true(SDL_RenderFillRect(renderer, rect.get()) == 0, "solid movement fixtures must render opaque cells");
    }

    bool mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) override {
        if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_RIGHT) {
            const auto object = getObject();
            rightClickTarget = object ? object->getName() : std::string();
            return true;
        }
        return CAnimation::mouseEvent(std::move(gui), type, button, x, y);
    }
};

std::array<Uint8, 4> readPixel(const std::shared_ptr<CGui> &gui, int x, int y) {
    std::array<Uint8, 4> pixel{};
    SDL_Rect rect{x, y, 1, 1};
    expect_true(SDL_RenderReadPixels(gui->getRenderer(), &rect, SDL_PIXELFORMAT_RGBA32, pixel.data(), 4) == 0,
                "rendered movement pixels must be readable from the software renderer");
    return pixel;
}

bool isActorPixel(const std::shared_ptr<CGui> &gui, int x, int y) {
    const auto pixel = readPixel(gui, x, y);
    return pixel[0] == 255 && pixel[1] == 0 && pixel[2] == 0;
}

bool isTerrainPixel(const std::shared_ptr<CGui> &gui, int x, int y) {
    const auto pixel = readPixel(gui, x, y);
    return pixel[0] == 0 && pixel[1] == 200 && pixel[2] == 0;
}

struct PreviewFixture {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    std::shared_ptr<CMap> map = std::make_shared<CMap>();
    std::shared_ptr<CPlayer> player = std::make_shared<CPlayer>();
    std::shared_ptr<CPlayerController> controller = std::make_shared<CPlayerController>();
    std::shared_ptr<CGui> gui;
    std::shared_ptr<CMapGraphicsObject> world;
    Uint32 frameTime = 1000;

    explicit PreviewFixture(int width = 8, bool withGui = true) {
        for (const auto &[name, builder] : *CTypes::builders())
            game->getObjectHandler()->registerType(name, builder);
        game->setMap(map);
        map->setGame(game);
        map->setXBounds({{0, width - 1}});
        map->setYBounds({{0, 1}});
        for (int x = 0; x < width; ++x) {
            for (int y = 0; y < 2; ++y) {
                auto tile = std::make_shared<CTile>();
                tile->setGame(game);
                tile->setCanStep(true);
                map->addTile(tile, x, y, 0);
            }
        }
        player->setGame(game);
        auto stats = std::make_shared<CStats>();
        stats->setMainStat("stamina");
        stats->setStamina(10);
        player->setBaseStats(stats);
        map->setPlayer(player);
        controller->setGame(game);
        player->setController(controller);
        if (withGui) {
            gui = std::make_shared<CGui>();
            game->setGui(gui);
            gui->setGame(game);
            gui->setLayout(std::make_shared<CLayout>());
            gui->getLayout()->setRect(0, 0, 1280, 720);
            world = std::make_shared<CMapGraphicsObject>();
            world->setGame(game);
            world->setLayout(std::make_shared<CLayout>());
            world->getLayout()->setRect(0, 0, 1280, 720);
            gui->pushChild(world);
        }
    }

    ~PreviewFixture() { game->getContext()->shutdown(); }

    void frame() {
        world->renderObject(gui, world->getLayout()->getRect(world), static_cast<int>(frameTime));
        frameTime += 75;
        auto loop = vstd::event_loop<>::instance();
        loop->runFrame();
        loop->runUntilIdle();
    }

    void finishMovement() {
        for (int frames = 0; frames < 128 && (world->isTravelling() || map->isMoving()); ++frames)
            frame();
        expect_true(!world->isTravelling() && !map->isMoving(),
                    "animated GUI movement must finish within bounded frames");
    }

    bool clickDestination(Coords destination) {
        const auto delta = map->getShortestDelta(player->getCoords(), destination);
        auto graphics = world->getProxiedObjects(gui, gui->getTileCountX() / 2 + delta.x + 1,
                                                 gui->getTileCountY() / 2 + delta.y + 1);
        expect_true(!graphics.empty(), "a destination click must target an actual tile animation");
        if (graphics.empty())
            return false;
        const bool handled = graphics.front()->mouseEvent(gui, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT, 0, 0);
        graphics.front()->mouseEvent(gui, SDL_MOUSEBUTTONUP, SDL_BUTTON_LEFT, 0, 0);
        return handled;
    }

    void initializeSolidProxyGrid() {
        game->getObjectHandler()->registerType("CAnimation", [] { return std::make_shared<SolidMovementAnimation>(); });
        game->getObjectHandler()->registerType("CStaticAnimation",
                                               [] { return std::make_shared<SolidMovementAnimation>(); });
        world->setProxyLayout("CProxyGraphicsLayout");
        world->initialize();
        vstd::event_loop<>::instance()->runUntilIdle();
    }

    void commit() {
        SDL_Event event{};
        event.type = SDL_KEYDOWN;
        event.key.keysym.sym = SDLK_RETURN;
        gui->event(&event);
        event.type = SDL_KEYUP;
        gui->event(&event);
        vstd::event_loop<>::instance()->runUntilIdle();
        finishMovement();
    }
};

void testPreviewAndCommitReuseOneSearch() {
    PreviewFixture fixture;
    const auto service = fixture.map->getNavigationService();
    const auto before = service->searchCount();
    const auto turn = fixture.map->getTurn();
    const auto hp = fixture.player->getHp();
    const auto mana = fixture.player->getMana();
    const auto items = fixture.player->getItems();
    fixture.world->previewDestination(fixture.gui, Coords(3, 0, 0));
    fixture.world->previewDestination(fixture.gui, Coords(3, 0, 0));
    expect_true(service->searchCount() == before + 1, "unchanged repeated destination previews perform one search");
    expect_true(fixture.player->getCoords() == ZERO && fixture.map->getTurn() == turn &&
                    fixture.player->getHp() == hp && fixture.player->getMana() == mana &&
                    fixture.player->getItems() == items,
                "previewing and reading a route leave gameplay state untouched");
    fixture.commit();
    expect_true(fixture.player->getCoords() == Coords(3, 0, 0), "Enter commits the previewed real player route");
    expect_true(service->searchCount() == before + 1, "committing an unchanged preview does not repeat its search");
}

void testOneClickWalksEveryStepWithoutEnterAndStopsAtDestination() {
    PreviewFixture fixture;
    const auto turn = fixture.map->getTurn();
    const auto searches = fixture.map->getNavigationService()->searchCount();
    expect_true(fixture.clickDestination(Coords(3, 0, 0)), "one left click starts the selected route");
    vstd::event_loop<>::instance()->runUntilIdle();
    expect_true(fixture.world->isTravelling() && fixture.map->isMoving() && fixture.map->getTurn() == turn &&
                    fixture.player->getCoords() == Coords(1, 0, 0),
                "posted-work draining must leave the first committed step waiting for its visible animation");
    fixture.finishMovement();
    expect_true(fixture.player->getCoords() == Coords(3, 0, 0) && fixture.map->getTurn() == turn + 3,
                "a single click walks three real steps and consumes exactly three turns without Enter");
    expect_true(fixture.map->getNavigationService()->searchCount() == searches + 1,
                "automatic step presentation must reuse the selected route instead of replanning every frame");
    fixture.frame();
    fixture.frame();
    expect_true(fixture.player->getCoords() == Coords(3, 0, 0) && fixture.map->getTurn() == turn + 3,
                "completed travel must not continue producing idle turns on later frames");
}

void testNewClickAndEscapeInterruptAtTheNextStepBoundary() {
    PreviewFixture fixture;
    const auto turn = fixture.map->getTurn();
    fixture.world->startTravel(fixture.gui, Coords(6, 0, 0));
    vstd::event_loop<>::instance()->runUntilIdle();
    fixture.world->startTravel(fixture.gui, Coords(1, 1, 0));
    fixture.finishMovement();
    expect_true(fixture.player->getCoords() == Coords(1, 1, 0) && fixture.map->getTurn() == turn + 2,
                "a new destination replaces the old route after the already committed step finishes");
    fixture.world->startTravel(fixture.gui, Coords(6, 1, 0));
    vstd::event_loop<>::instance()->runUntilIdle();
    SDL_Event escape{};
    escape.type = SDL_KEYDOWN;
    escape.key.keysym.sym = SDLK_ESCAPE;
    fixture.gui->event(&escape);
    fixture.finishMovement();
    expect_true(fixture.player->getCoords() == Coords(2, 1, 0) && fixture.map->getTurn() == turn + 3,
                "Escape finishes the committed animation and prevents another route step");
}

void testPlayerAndVisibleActorsUseInterpolatedViewOffsets() {
    for (int kind = 0; kind < 3; ++kind) {
        PreviewFixture fixture;
        std::shared_ptr<CCreature> actor = fixture.player;
        if (kind != 0) {
            actor = std::make_shared<CCreature>();
            actor->setGame(fixture.game);
            actor->setName(kind == 1 ? "visibleNpc" : "visibleEnemy");
            actor->setNpc(kind == 1);
            actor->setBaseStats(fixture.player->getBaseStats());
            actor->setHp(actor->getHpMax());
            actor->setPosX(4);
            actor->setPosY(1);
            fixture.map->addObject(actor);
        }
        const auto destination = actor->getCoords() + EAST;
        auto movement = fixture.game->getContext()->spawnTask(
            actor->moveToAsync(destination, {}, fixture.world->movementPresenter(fixture.gui)));
        auto rect = fixture.world->getLayout()->getRect(fixture.world);
        fixture.world->renderObject(fixture.gui, rect, 1000);
        auto actorOffset = fixture.world->getActorOffset(actor, 64);
        auto cameraOffset = fixture.world->getCameraOffset(64);
        expect_true(!movement.finished() && actor->getCoords() == destination && actorOffset.x == -64 &&
                        actorOffset.y == 0 && cameraOffset.x == (kind == 0 ? 64 : 0) && cameraOffset.y == 0,
                    "visible player, NPC and enemy presentation starts at the source after the real position commits");
        fixture.world->renderObject(fixture.gui, rect, 1075);
        actorOffset = fixture.world->getActorOffset(actor, 64);
        cameraOffset = fixture.world->getCameraOffset(64);
        expect_true(actorOffset.x == -32 && actorOffset.y == 0 && cameraOffset.x == (kind == 0 ? 32 : 0),
                    "visible actors interpolate halfway while only player movement scrolls the camera");
        fixture.world->renderObject(fixture.gui, rect, 1150);
        actorOffset = fixture.world->getActorOffset(actor, 64);
        cameraOffset = fixture.world->getCameraOffset(64);
        expect_true(actorOffset.x == 0 && actorOffset.y == 0 && cameraOffset.x == 0 && cameraOffset.y == 0,
                    "the final rendered frame exposes committed geometry before arrival resumes");
        auto loop = vstd::event_loop<>::instance();
        loop->runFrame();
        loop->runUntilIdle();
        expect_true(movement.finished() && !actor->getPendingMoveOrigin(),
                    "arrival resumes after the final visible actor frame without retaining pending movement");
        if (movement.finished())
            movement.get();
    }
}

void testMovingActorRendersAboveAdjacentTerrainAndReceivesVisibleRightClicks() {
    for (int direction : {-1, 1}) {
        PreviewFixture fixture;
        fixture.gui->setWidth(1280);
        fixture.gui->setHeight(720);
        fixture.gui->setTileSize(64);
        fixture.game->getObjectHandler()->registerType("CAnimation",
                                                       [] { return std::make_shared<SolidMovementAnimation>(); });
        fixture.game->getObjectHandler()->registerType("CStaticAnimation",
                                                       [] { return std::make_shared<SolidMovementAnimation>(); });
        auto actor = std::make_shared<CCreature>();
        actor->setGame(fixture.game);
        actor->setName("movingColorActor");
        actor->setLabel("Moving actor");
        actor->setNpc(true);
        actor->setBaseStats(fixture.player->getBaseStats());
        const Coords origin(direction > 0 ? 3 : 4, 1, 0);
        const Coords destination = origin + direction * EAST;
        actor->setPosX(origin.x);
        actor->setPosY(origin.y);
        fixture.map->addObject(actor);
        actor->getGraphicsObject()->setPriority(5);
        fixture.initializeSolidProxyGrid();
        const int tile = fixture.gui->getTileSize();
        const int sourceX = fixture.gui->getTileCountX() / 2 + origin.x + 1;
        const int sourceY = fixture.gui->getTileCountY() / 2 + origin.y + 1;
        std::shared_ptr<CProxyGraphicsObject> sourceProxy;
        for (const auto &child : fixture.world->getChildren()) {
            auto proxy = vstd::cast<CProxyGraphicsObject>(child);
            if (proxy && proxy->getX() == sourceX && proxy->getY() == sourceY)
                sourceProxy = proxy;
        }
        expect_true(sourceProxy != nullptr, "the pixel regression must use a real authored source-cell proxy");
        if (!sourceProxy)
            continue;
        // Render the vacated source after the destination so proxy allocation order cannot hide the regression.
        fixture.world->removeChild(sourceProxy);
        sourceProxy->setPriority(2);
        fixture.world->addChild(sourceProxy);
        const auto sourceRect = *sourceProxy->getLayout()->getRect(sourceProxy);
        auto movement = fixture.game->getContext()->spawnTask(
            actor->moveToAsync(destination, {}, fixture.world->movementPresenter(fixture.gui)));
        for (const Uint32 elapsed : {Uint32{0}, Uint32{75}, Uint32{150}}) {
            SolidMovementAnimation::actorRects.clear();
            fixture.gui->render(static_cast<int>(1000 + elapsed));
            const int actorLeft = sourceRect.x + direction * static_cast<int>(elapsed) * tile / 150;
            const int middleY = sourceRect.y + tile / 2;
            expect_true(SolidMovementAnimation::actorRects.size() == 1,
                        "a moving actor must render once through the actual proxy and overlay trees");
            expect_true(isActorPixel(fixture.gui, actorLeft + tile / 4, middleY) &&
                            isActorPixel(fixture.gui, actorLeft + 3 * tile / 4, middleY),
                        "both halves of the interpolated actor must stay visible above opaque adjacent terrain");
            if (elapsed == 75) {
                const int outsideX = direction > 0 ? sourceRect.x + tile / 4 : sourceRect.x + 3 * tile / 4;
                expect_true(isTerrainPixel(fixture.gui, outsideX, middleY),
                            "the vacated half-cell must show terrain rather than a second stationary actor copy");
                SolidMovementAnimation::rightClickTarget.clear();
                SDL_Event click{};
                click.type = SDL_MOUSEBUTTONDOWN;
                click.button.button = SDL_BUTTON_RIGHT;
                click.button.x = actorLeft + (direction > 0 ? tile / 4 : 3 * tile / 4);
                click.button.y = middleY;
                fixture.gui->event(&click);
                expect_true(SolidMovementAnimation::rightClickTarget == actor->getName(),
                            "right-click inspection must target the visible actor above source-cell terrain");
            }
        }
        auto loop = vstd::event_loop<>::instance();
        loop->runFrame();
        loop->runUntilIdle();
        expect_true(movement.finished(),
                    "the pixel regression must finish presentation after its final rendered frame");
        if (movement.finished())
            movement.get();
        SolidMovementAnimation::actorRects.clear();
        fixture.gui->render(1200);
        expect_true(SolidMovementAnimation::actorRects.size() == 1,
                    "completion must restore exactly one ordinary proxy actor after removing its motion overlay");
    }
}

void testClippedOverscanCannotStartTravelOutsideTheMapViewport() {
    PreviewFixture fixture(64);
    fixture.gui->setWidth(800);
    fixture.gui->setHeight(600);
    fixture.gui->setTileSize(64);
    fixture.world->getLayout()->setRect(100, 80, 800, 600);
    fixture.player->relocateWithoutMoveHooks(Coords(20, 1, 0));
    fixture.initializeSolidProxyGrid();
    const auto turn = fixture.map->getTurn();
    const int tile = fixture.gui->getTileSize();
    const int y = 80 + fixture.gui->getTileCountY() / 2 * tile + tile / 2;
    fixture.gui->render(1000);
    const auto clippedPixel = readPixel(fixture.gui, 100 - tile / 2, y);
    expect_true(clippedPixel[0] == 0 && clippedPixel[1] == 0 && clippedPixel[2] == 0,
                "the opaque overscan tile outside the map viewport must actually be clipped from rendering");
    SDL_Event click{};
    click.type = SDL_MOUSEBUTTONDOWN;
    click.button.button = SDL_BUTTON_LEFT;
    click.button.x = 100 - tile / 2;
    click.button.y = y;
    expect_true(!fixture.gui->event(&click), "clipped overscan must not consume mouse input outside the map viewport");
    vstd::event_loop<>::instance()->runUntilIdle();
    expect_true(!fixture.world->isTravelling() && fixture.player->getCoords() == Coords(20, 1, 0) &&
                    fixture.map->getTurn() == turn,
                "clicking an invisible but otherwise walkable overscan cell must not move or advance a turn");
    click.button.x = 100 + tile / 2;
    expect_true(fixture.gui->event(&click), "an adjacent visible cell must retain normal mouse travel");
    fixture.finishMovement();
    expect_true(fixture.player->getCoords() == Coords(20 - fixture.gui->getTileCountX() / 2, 1, 0),
                "the same viewport boundary must map a visible click to the correct authored destination");
}

void testWrappedMapKeepsEveryVisibleActorAliasDuringPresentation() {
    PreviewFixture fixture;
    fixture.gui->setWidth(1280);
    fixture.gui->setHeight(720);
    fixture.gui->setTileSize(64);
    fixture.map->setWrapX({{0, 1}});
    fixture.game->getObjectHandler()->registerType("CAnimation",
                                                   [] { return std::make_shared<SolidMovementAnimation>(); });
    fixture.game->getObjectHandler()->registerType("CStaticAnimation",
                                                   [] { return std::make_shared<SolidMovementAnimation>(); });
    auto actor = std::make_shared<CCreature>();
    actor->setGame(fixture.game);
    actor->setName("movingColorActor");
    actor->setNpc(true);
    actor->setBaseStats(fixture.player->getBaseStats());
    actor->setPosX(3);
    actor->setPosY(1);
    fixture.map->addObject(actor);
    actor->getGraphicsObject()->setPriority(5);
    fixture.initializeSolidProxyGrid();
    const auto viewport = *fixture.world->getLayout()->getRect(fixture.world);
    auto captureActors = [&](int timestamp) {
        SolidMovementAnimation::actorRects.clear();
        SolidMovementAnimation::actorInstances.clear();
        fixture.gui->render(timestamp);
        std::vector<SDL_Rect> visible;
        for (std::size_t index = 0; index < SolidMovementAnimation::actorRects.size(); ++index) {
            const auto &rect = SolidMovementAnimation::actorRects[index];
            if (SDL_HasIntersection(&viewport, &rect)) {
                expect_true(SolidMovementAnimation::actorInstances[index] == actor.get(),
                            "every wrapped image must retain the identity of the same real actor");
                visible.push_back(rect);
            }
        }
        std::sort(visible.begin(), visible.end(), [](const auto &left, const auto &right) { return left.x < right.x; });
        return visible;
    };
    const auto original = captureActors(900);
    expect_true(original.size() > 1, "the torus regression must start with multiple visible images of one actor");
    auto movement = fixture.game->getContext()->spawnTask(
        actor->moveToAsync(Coords(4, 1, 0), {}, fixture.world->movementPresenter(fixture.gui)));
    const int tile = fixture.gui->getTileSize();
    for (const int elapsed : {0, 75, 150}) {
        const auto visible = captureActors(1000 + elapsed);
        expect_true(visible.size() == original.size(),
                    "animation must preserve every legitimate visible torus alias without adding ghost copies");
        for (std::size_t index = 0; index < std::min(visible.size(), original.size()); ++index) {
            const auto &before = original[index];
            const auto &now = visible[index];
            const int expectedX = before.x + elapsed * tile / 150;
            expect_true(now.x == expectedX && now.y == before.y && now.w == before.w && now.h == before.h &&
                            isActorPixel(fixture.gui, expectedX + tile / 4, now.y + tile / 2) &&
                            isActorPixel(fixture.gui, expectedX + 3 * tile / 4, now.y + tile / 2),
                        "all repeated actor images must interpolate together above the actual opaque proxy terrain");
            if (elapsed == 75)
                expect_true(isTerrainPixel(fixture.gui, before.x + tile / 4, before.y + tile / 2),
                            "none of the wrapped source cells may retain a stationary actor ghost");
        }
        if (elapsed == 75 && !visible.empty()) {
            SolidMovementAnimation::rightClickTarget.clear();
            SDL_Event click{};
            click.type = SDL_MOUSEBUTTONDOWN;
            click.button.button = SDL_BUTTON_RIGHT;
            click.button.x = visible.front().x + tile / 4;
            click.button.y = visible.front().y + tile / 2;
            fixture.gui->event(&click);
            expect_true(SolidMovementAnimation::rightClickTarget == actor->getName(),
                        "right-clicking a repeated motion image must inspect the same canonical actor");
        }
    }
    auto loop = vstd::event_loop<>::instance();
    loop->runFrame();
    loop->runUntilIdle();
    expect_true(movement.finished(), "wrapped presentation must finish after its final rendered aliases");
    if (movement.finished())
        movement.get();
    const auto restored = captureActors(1200);
    expect_true(restored.size() == original.size(),
                "completion must restore the ordinary wrapped aliases without leaving motion overlays");
}

void testPreviewRejectsChangedRequestControllerGraphOriginAndSession() {
    for (int change = 0; change < 6; ++change) {
        PreviewFixture fixture;
        fixture.world->previewDestination(fixture.gui, Coords(3, 0, 0));
        if (change == 0)
            fixture.controller->setTarget(fixture.player, Coords(3, 0, 0));
        else if (change == 1)
            fixture.controller->interrupt(fixture.player);
        else if (change == 2)
            fixture.player->setController(std::make_shared<CPlayerController>());
        else if (change == 3)
            fixture.map->getTile(Coords(7, 1, 0))->setMovementCost(3);
        else if (change == 4)
            fixture.player->moveTo(Coords(0, 1, 0));
        else
            fixture.game->getContext()->advanceTransitionGeneration();
        const auto origin = fixture.player->getCoords();
        const auto turn = fixture.map->getTurn();
        const auto searches = fixture.map->getNavigationService()->searchCount();
        fixture.commit();
        expect_true(fixture.player->getCoords() == origin && fixture.map->getTurn() == turn,
                    "a changed request, controller, graph, origin or session cannot commit an obsolete preview");
        expect_true(fixture.map->getNavigationService()->searchCount() == searches,
                    "rejecting an obsolete preview must not silently replan another route");
    }
}

void testCommittedLegalRoutesSurviveUnrelatedGraphChangesAndStopPermanentlyWhenBlocked() {
    PreviewFixture fixture(8, false);
    fixture.controller->setTarget(fixture.player, Coords(6, 0, 0));
    const auto searches = fixture.map->getNavigationService()->searchCount();
    fixture.map->getTile(Coords(7, 1, 0))->setMovementCost(2);
    const auto first = resolvePlan(fixture.controller->controlAsync(fixture.player));
    expect_true(first == Coords(1, 0, 0), "an unrelated graph edit preserves the next legal committed step");
    fixture.player->moveTo(first);
    fixture.controller->onStepCommitted(fixture.player, first);
    expect_true(fixture.controller->isOnPath(fixture.player, Coords(1, 0, 0)).first,
                "the current route cell remains visible after its step commits");
    const auto second = resolvePlan(fixture.controller->controlAsync(fixture.player));
    fixture.player->moveTo(second);
    fixture.controller->onStepCommitted(fixture.player, second);
    expect_true(!fixture.controller->isOnPath(fixture.player, Coords(1, 0, 0)).first &&
                    fixture.controller->isOnPath(fixture.player, second).first,
                "overlay indices discard cells behind the current route position");
    fixture.map->getTile(Coords(3, 0, 0))->setCanStep(false);
    expect_true(resolvePlan(fixture.controller->controlAsync(fixture.player)) == second,
                "a blocked next step stops the committed route");
    fixture.map->getTile(Coords(3, 0, 0))->setCanStep(true);
    expect_true(resolvePlan(fixture.controller->controlAsync(fixture.player)) == second &&
                    fixture.controller->isCompleted(fixture.player),
                "removing the obstacle does not resurrect the abandoned route");
    expect_true(fixture.map->getNavigationService()->searchCount() == searches,
                "legal route continuation and blocked-route cancellation do not trigger new searches");
}

void testOverlayLookupsAndRetainedStorageAreBounded() {
    PreviewFixture fixture(4097, false);
    auto service = fixture.map->getNavigationService();
    auto budget = service->budget();
    fixture.controller->setTarget(fixture.player, Coords(4096, 0, 0));
    const auto searches = service->searchCount();
    const auto bytes = budget->used();
    const auto probes = fixture.controller->getOverlayLookupCount();
    const auto turn = fixture.map->getTurn();
    constexpr int queries = 20'000;
    for (int index = 0; index < queries; ++index)
        expect_true(fixture.controller->isOnPath(fixture.player, Coords(1 + (index * 17) % 4096, 0, 0)).first,
                    "every selected route coordinate remains available through the occurrence index");
    const auto lookupWork = fixture.controller->getOverlayLookupCount() - probes;
    expect_true(lookupWork == queries,
                "overlay lookup work is one coordinate probe per query, independent of route length");
    expect_true(budget->used() == bytes && bytes <= budget->limit() && service->searchCount() == searches,
                "warm overlay queries allocate no retained navigation storage and perform no searches");
    expect_true(fixture.map->getTurn() == turn && fixture.player->getCoords() == ZERO,
                "overlay reads do not move the player or advance a turn");
    fixture.controller->interrupt(fixture.player);
    expect_true(budget->used() < bytes, "interrupting the route releases its charged vector and occurrence index");
    const auto free = budget->limit() - budget->used();
    const auto reserved = free > 64 ? free - 64 : 0;
    expect_true(budget->tryReserve(reserved),
                "the bounded-allocation regression can reserve the available session budget");
    const auto constrained = budget->used();
    fixture.controller->setTarget(fixture.player, Coords(4096, 0, 0));
    expect_true(fixture.controller->isCompleted(fixture.player) && budget->used() <= constrained + 64,
                "insufficient session memory fails safely without an unaccounted retained route");
    budget->release(reserved);
    std::cout << "[player route overlay] route=4096 queries=" << queries << " index_probes=" << lookupWork
              << " probe_budget=" << queries << " retained_bytes=" << bytes << '\n';
}

void testCompletedPollingAbandonsBlockedRouteBeforeMovement() {
    PreviewFixture fixture(8, false);
    fixture.controller->setTarget(fixture.player, Coords(6, 0, 0));
    const auto searches = fixture.map->getNavigationService()->searchCount();
    const auto turn = fixture.map->getTurn();
    fixture.map->getTile(Coords(1, 0, 0))->setCanStep(false);
    expect_true(fixture.controller->isCompleted(fixture.player),
                "the travel-loop completion guard detects the blocked next step before polling control");
    fixture.map->getTile(Coords(1, 0, 0))->setCanStep(true);
    expect_true(fixture.controller->isCompleted(fixture.player) &&
                    resolvePlan(fixture.controller->controlAsync(fixture.player)) == ZERO,
                "reopening a route stopped by completion polling cannot resurrect its old order");
    expect_true(fixture.map->getTurn() == turn && fixture.map->getNavigationService()->searchCount() == searches,
                "completion polling abandons routing state without movement, turns or another search");
}

void testNpcRoutesUseSessionBudgetAndDoNotReplanDuringBlockedOrStaleControl() {
    const auto saved_rng = vstd::rng();
    PreviewFixture fixture(5, false);
    for (int x = 1; x <= 3; ++x)
        fixture.map->getTile(Coords(x, 0, 0))->setMovementCost(30);
    auto controller = std::make_shared<CNpcRandomController>();
    fixture.player->setController(controller);
    auto service = fixture.map->getNavigationService();
    auto budget = service->budget();
    auto route_rng = vstd::rng();
    bool target_seed_found = false;
    for (unsigned seed = 0; seed < 1024; ++seed) {
        vstd::rng().seed(seed);
        const auto candidate_rng = vstd::rng();
        const auto dx = vstd::rand(-5, 5);
        const auto dy = vstd::rand(-5, 5);
        if (fixture.map->normalizeCoords(Coords(dx, dy, 0)) == Coords(4, 0, 0)) {
            route_rng = candidate_rng;
            target_seed_found = true;
            break;
        }
    }
    expect_true(target_seed_found,
                "the NPC reuse fixture must select its authored destination without assuming an RNG sequence");
    if (!target_seed_found) {
        vstd::rng() = saved_rng;
        return;
    }
    vstd::rng() = route_rng;
    const auto searches = service->searchCount();
    const auto first = resolvePlan(controller->controlAsync(fixture.player));
    expect_true(first == Coords(0, 1, 0) && service->searchCount() == searches + 1,
                "NPC wandering uses one exact session search and the cheaper weighted detour");
    const auto bytes = budget->used();
    for (int sample = 0; sample < 256; ++sample)
        expect_true(resolvePlan(controller->controlAsync(fixture.player)) == first,
                    "a retained NPC route remains stable");
    expect_true(service->searchCount() == searches + 1 && budget->used() == bytes,
                "warm NPC route reads neither search again nor allocate retained storage");
    fixture.map->getTile(first)->setCanStep(false);
    expect_true(resolvePlan(controller->controlAsync(fixture.player)) == ZERO && service->searchCount() == searches + 1,
                "a blocked NPC route is abandoned without another random search in the same control call");
    expect_true(budget->used() < bytes, "blocked NPC cancellation releases its charged route storage");
    fixture.map->getTile(first)->setCanStep(true);
    vstd::rng() = route_rng;
    expect_true(resolvePlan(controller->controlAsync(fixture.player)) == first &&
                    service->searchCount() == searches + 2,
                "a later wandering decision searches independently instead of resuming the old route");
    fixture.game->getContext()->advanceTransitionGeneration();
    expect_true(resolvePlan(controller->controlAsync(fixture.player)) == ZERO && service->searchCount() == searches + 2,
                "a changed session generation abandons the NPC route without planning in that call");
    vstd::rng() = route_rng;
    expect_true(resolvePlan(controller->controlAsync(fixture.player)) == first,
                "a fresh request can plan in the new generation");
    const auto latestSearch = service->searchCount();
    fixture.player->setController(std::make_shared<CNpcRandomController>());
    expect_true(resolvePlan(controller->controlAsync(fixture.player)) == ZERO && service->searchCount() == latestSearch,
                "a route owned by a replaced NPC controller cannot continue");
    vstd::rng() = saved_rng;
    std::cout << "[NPC route reuse] warm_reads=256 additional_searches=0 additional_retained_bytes=0\n";
}
} // namespace

int main() {
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    SDL_setenv("SDL_RENDER_DRIVER", "software", 1);
    SDL_setenv("GAME_UI_PREFERENCES_PATH", "navigation-preview-preferences.json", 1);
    pybind11::scoped_interpreter interpreter;
    type_registration::registerCoreTypes();
    type_registration::registerObjectTypes();
    type_registration::registerHandlerTypes();
    type_registration::registerGuiTypes();
    type_registration::registerGuiPanelTypes();
    type_registration::registerGuiWidgetTypes();
    type_registration::registerGuiAnimationTypes();
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");
    testPreviewAndCommitReuseOneSearch();
    testOneClickWalksEveryStepWithoutEnterAndStopsAtDestination();
    testNewClickAndEscapeInterruptAtTheNextStepBoundary();
    testPlayerAndVisibleActorsUseInterpolatedViewOffsets();
    testMovingActorRendersAboveAdjacentTerrainAndReceivesVisibleRightClicks();
    testClippedOverscanCannotStartTravelOutsideTheMapViewport();
    testWrappedMapKeepsEveryVisibleActorAliasDuringPresentation();
    testPreviewRejectsChangedRequestControllerGraphOriginAndSession();
    testCommittedLegalRoutesSurviveUnrelatedGraphChangesAndStopPermanentlyWhenBlocked();
    testOverlayLookupsAndRetainedStorageAreBounded();
    testCompletedPollingAbandonsBlockedRouteBeforeMovement();
    testNpcRoutesUseSessionBudgetAndDoNotReplanDuringBlockedOrStaleControl();
    return finish_tests();
}
