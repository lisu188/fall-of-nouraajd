/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CNavigation.h"
#include "core/CRuntimeBridge.h"
#include "core/CStats.h"
#include "core/CTypes.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/object/CMapGraphicsObject.h"
#include "handler/CObjectHandler.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "test_harness.h"

#include <pybind11/embed.h>

namespace {
struct PreviewFixture {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    std::shared_ptr<CMap> map = std::make_shared<CMap>();
    std::shared_ptr<CPlayer> player = std::make_shared<CPlayer>();
    std::shared_ptr<CPlayerController> controller = std::make_shared<CPlayerController>();
    std::shared_ptr<CGui> gui;
    std::shared_ptr<CMapGraphicsObject> world;

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

    void commit() {
        SDL_Event event{};
        event.type = SDL_KEYDOWN;
        event.key.keysym.sym = SDLK_RETURN;
        gui->event(&event);
        event.type = SDL_KEYUP;
        gui->event(&event);
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
    const auto first = fixture.controller->control(fixture.player)->get();
    expect_true(first == Coords(1, 0, 0), "an unrelated graph edit preserves the next legal committed step");
    fixture.player->moveTo(first);
    fixture.controller->onStepCommitted(fixture.player, first);
    expect_true(fixture.controller->isOnPath(fixture.player, Coords(1, 0, 0)).first,
                "the current route cell remains visible after its step commits");
    const auto second = fixture.controller->control(fixture.player)->get();
    fixture.player->moveTo(second);
    fixture.controller->onStepCommitted(fixture.player, second);
    expect_true(!fixture.controller->isOnPath(fixture.player, Coords(1, 0, 0)).first &&
                    fixture.controller->isOnPath(fixture.player, second).first,
                "overlay indices discard cells behind the current route position");
    fixture.map->getTile(Coords(3, 0, 0))->setCanStep(false);
    expect_true(fixture.controller->control(fixture.player)->get() == second,
                "a blocked next step stops the committed route");
    fixture.map->getTile(Coords(3, 0, 0))->setCanStep(true);
    expect_true(fixture.controller->control(fixture.player)->get() == second &&
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
                    fixture.controller->control(fixture.player)->get() == ZERO,
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
    const auto first = controller->control(fixture.player)->get();
    expect_true(first == Coords(0, 1, 0) && service->searchCount() == searches + 1,
                "NPC wandering uses one exact session search and the cheaper weighted detour");
    const auto bytes = budget->used();
    for (int sample = 0; sample < 256; ++sample)
        expect_true(controller->control(fixture.player)->get() == first, "a retained NPC route remains stable");
    expect_true(service->searchCount() == searches + 1 && budget->used() == bytes,
                "warm NPC route reads neither search again nor allocate retained storage");
    fixture.map->getTile(first)->setCanStep(false);
    expect_true(controller->control(fixture.player)->get() == ZERO && service->searchCount() == searches + 1,
                "a blocked NPC route is abandoned without another random search in the same control call");
    expect_true(budget->used() < bytes, "blocked NPC cancellation releases its charged route storage");
    fixture.map->getTile(first)->setCanStep(true);
    vstd::rng() = route_rng;
    expect_true(controller->control(fixture.player)->get() == first && service->searchCount() == searches + 2,
                "a later wandering decision searches independently instead of resuming the old route");
    fixture.game->getContext()->advanceTransitionGeneration();
    expect_true(controller->control(fixture.player)->get() == ZERO && service->searchCount() == searches + 2,
                "a changed session generation abandons the NPC route without planning in that call");
    vstd::rng() = route_rng;
    expect_true(controller->control(fixture.player)->get() == first, "a fresh request can plan in the new generation");
    const auto latestSearch = service->searchCount();
    fixture.player->setController(std::make_shared<CNpcRandomController>());
    expect_true(controller->control(fixture.player)->get() == ZERO && service->searchCount() == latestSearch,
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
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");
    testPreviewAndCommitReuseOneSearch();
    testPreviewRejectsChangedRequestControllerGraphOriginAndSession();
    testCommittedLegalRoutesSurviveUnrelatedGraphChangesAndStopPermanentlyWhenBlocked();
    testOverlayLookupsAndRetainedStorageAreBounded();
    testCompletedPollingAbandonsBlockedRouteBeforeMovement();
    testNpcRoutesUseSessionBudgetAndDoNotReplanDuringBlockedOrStaleControl();
    return finish_tests();
}
